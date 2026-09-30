/* تيفو v5 in the browser: the shell's behaviour (large title -> compact bar, segmented controls, sheets, favourites,
   settings), live refresh with the same renderers as the build, and pages for ids outside the prerendered set.
   Storage keys are the live site's (tifo.favs, tifo.mine, tifo.country, tifo.nospoil, tifo.sq, tifo.picks), so a
   visitor's teams carry over both ways. */
(function () {
  "use strict";
  var U = window.U5, P = window.P5, cfg = U.cfg, V = window.V5 || {}, C = window.V5C || {}, B = document.body;
  var $ = function (s, r) { return (r || document).querySelector(s); }, $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };
  cfg.pre = C.pre || cfg.pre; cfg.cn = C.cn || {}; cfg.cc = C.cc || {}; cfg.ph = C.ph || {}; cfg.pn = V.pn || {}; cfg.tc = V.tc || {}; cfg.tn = V.tn || {};
  cfg.now = V.snap ? V.now : Date.now();
  var ARAB = {}; (C.arab || []).forEach(function (id) { ARAB[id] = 1; });
  var ls = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
    del: function (k) { try { localStorage.removeItem(k); } catch (e) {} },
    json: function (k, d) { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } }
  };
  function get(p, fresh) { return fetch("/v1/" + p, fresh ? { cache: "no-cache" } : undefined).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }
  var toastT; function toast(t) { var el = $("#toast"); if (!el) return; el.textContent = t; el.classList.add("on"); clearTimeout(toastT); toastT = setTimeout(function () { el.classList.remove("on"); }, 1800); }

  // ------------------------------------------------------------------ time zone: the chosen country, else the device
  var TZS = { AE: "Asia/Dubai", SA: "Asia/Riyadh", EG: "Africa/Cairo", MA: "Africa/Casablanca", DZ: "Africa/Algiers", TN: "Africa/Tunis", IQ: "Asia/Baghdad", JO: "Asia/Amman", KW: "Asia/Kuwait", QA: "Asia/Qatar", BH: "Asia/Bahrain", OM: "Asia/Muscat", LB: "Asia/Beirut", SY: "Asia/Damascus", PS: "Asia/Hebron", YE: "Asia/Aden", LY: "Africa/Tripoli", SD: "Africa/Khartoum", MR: "Africa/Nouakchott", SO: "Africa/Mogadishu", DJ: "Africa/Djibouti", KM: "Indian/Comoro" };
  var CCN = { AE: "الإمارات", SA: "السعودية", EG: "مصر", MA: "المغرب", DZ: "الجزائر", TN: "تونس", IQ: "العراق", JO: "الأردن", KW: "الكويت", QA: "قطر", BH: "البحرين", OM: "عُمان", LB: "لبنان", SY: "سوريا", PS: "فلسطين", YE: "اليمن", LY: "ليبيا", SD: "السودان", MR: "موريتانيا", SO: "الصومال", DJ: "جيبوتي", KM: "جزر القمر" };
  function devTz() { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Dubai"; } catch (e) { return "Asia/Dubai"; } }
  function country() { var c = ls.get("tifo.country", ""); if (c && TZS[c]) return c; var tz = devTz(); for (var k in TZS) if (TZS[k] === tz) return k; return ""; }
  function applyTz() { var c = country(); cfg.tz = c ? TZS[c] : devTz(); cfg.today = U.ymd(new Date(cfg.now).toISOString()); localize(); var v = $("#ccv"); if (v) v.textContent = CCN[c] || "حسب جوالك"; $$("[data-cc]").forEach(function (b) { var on = b.dataset.cc === c; var m = $("[data-ccv]", b); if (m) m.hidden = !on; b.setAttribute("aria-pressed", on); }); }
  function localize(root) { $$("time[data-u]", root).forEach(function (t) { var f = t.dataset.f; t.textContent = f === "ago" ? U.ago(t.dataset.u) : U.timeText(t.dataset.u, f); }); }

  // ------------------------------------------------------------------ nav bar: the large title (or entity header) scrolls under it
  var NAV = $("#nav");
  function navH() { return NAV ? NAV.getBoundingClientRect().height : 52; }
  function observeNav() {
    if (!NAV || !("IntersectionObserver" in window)) return;
    var tgt = $(".lt h1") || $("#mh .mh") || $(".hdr h1") || $(".hdr");
    if (tgt) new IntersectionObserver(function (es) { es.forEach(function (e) { NAV.classList.toggle("stuck", !e.isIntersecting); }); }, { rootMargin: "-" + Math.round(navH()) + "px 0px 0px 0px" }).observe(tgt);
    $$(".segbar").forEach(function (sb) { var s = document.createElement("i"); s.style.cssText = "display:block;height:1px;margin-bottom:-1px"; sb.parentNode.insertBefore(s, sb);
      new IntersectionObserver(function (es) { es.forEach(function (e) { var st = !e.isIntersecting && e.boundingClientRect.top < navH() + 2; sb.classList.toggle("stuck", st); NAV.style.setProperty("--nb", st ? "0" : ""); if (NAV) NAV.classList.toggle("merge", st); }); }, { rootMargin: "-" + Math.round(navH()) + "px 0px 0px 0px" }).observe(s); });
  }

  // ------------------------------------------------------------------ segmented controls
  function selectSeg(seg, key, user) {
    var btns = $$("button[data-t]", seg), i = -1; btns.forEach(function (b, j) { if (b.dataset.t === key) i = j; }); if (i < 0) return;
    btns.forEach(function (b, j) { b.setAttribute("aria-selected", String(j === i)); }); seg.style.setProperty("--i", i);
    var g = seg.dataset.seg;
    if (g === "f") return homeFilter(key); if (g === "pick") return pickSave(key); if (g === "nk") return newsFilter(key);
    $$('.pane[data-g="' + g + '"]').forEach(function (p) { p.hidden = p.dataset.p !== key; });
    if (user && /^(m|c|t|p|cs|w)$/.test(g)) { try { history.replaceState(null, "", location.pathname + location.search + "#" + key); } catch (e) {}
      var sb = seg.closest(".segbar"); if (sb && sb.classList.contains("stuck")) window.scrollTo({ top: sb.getBoundingClientRect().top + scrollY - navH() + 1 }); }
    if (g === "w" && key === "k") dbClubs();
    var pane = $('.pane[data-g="' + g + '"][data-p="' + key + '"]'); if (pane) { lazyNews(pane); var rb = $("#rounds button[aria-selected=true]", pane); if (rb) rb.scrollIntoView({ inline: "center", block: "nearest" }); }
  }
  function deepLink() { var h = (location.hash || "").slice(1); if (!h) return; var seg = $(".segbar .seg"); if (!seg) return; var b = $('button[data-t="' + h + '"]', seg); if (b) selectSeg(seg, h, false); }

  // ------------------------------------------------------------------ sheets (<dialog>): open, close, swipe down
  function openSheet(id) { var d = document.getElementById(id); if (!d) return; d.classList.remove("closing"); if (d.showModal) { try { d.showModal(); } catch (e) { d.setAttribute("open", ""); } } else d.setAttribute("open", ""); B.style.overflow = "hidden"; var q = $("input", d); if (q && id === "sh-pick") setTimeout(function () { q.focus(); }, 350); }
  function closeSheet(d) { if (!d || d.classList.contains("closing")) return; d.classList.add("closing"); setTimeout(function () { if (d.close) d.close(); else d.removeAttribute("open"); d.classList.remove("closing"); d.style.transform = ""; B.style.overflow = ""; }, 300); }
  $$("dialog.sheet").forEach(function (d) {
    d.addEventListener("click", function (e) { if (e.target === d) closeSheet(d); });
    d.addEventListener("cancel", function (e) { e.preventDefault(); closeSheet(d); });
    var y0 = null, dy = 0, grab = $(".sh-hd", d);
    [grab, $(".sh-grab", d)].forEach(function (h) { if (!h) return;
      h.addEventListener("touchstart", function (e) { y0 = e.touches[0].clientY; dy = 0; d.style.transition = "none"; }, { passive: true });
      h.addEventListener("touchmove", function (e) { if (y0 == null) return; dy = Math.max(0, e.touches[0].clientY - y0); d.style.transform = "translateY(" + dy + "px)"; }, { passive: true });
      h.addEventListener("touchend", function () { d.style.transition = ""; if (dy > 90) closeSheet(d); else d.style.transform = ""; y0 = null; }); });
  });

  // ------------------------------------------------------------------ favourites (tifo.favs: [{t:"team"|"comp", id, n}]; tifo.mine = the first team)
  function favs() { var f = ls.json("tifo.favs", []); var m = +ls.get("tifo.mine", 0); if (m && !f.some(function (x) { return x.t === "team" && +x.id === m; })) f.push({ t: "team", id: m, n: ls.get("tifo.mine.name", "") }); return f; }
  function setFavs(f) { ls.set("tifo.favs", JSON.stringify(f)); var t = f.filter(function (x) { return x.t === "team"; })[0]; if (t) { ls.set("tifo.mine", String(t.id)); ls.set("tifo.mine.name", t.n || ""); } else { ls.del("tifo.mine"); ls.del("tifo.mine.name"); } }
  function isFav(kind, id) { return favs().some(function (x) { return x.t === kind && +x.id === +id; }); }
  function toggleFav(kind, id, n) { var f = favs().filter(function (x) { return !(x.t === kind && +x.id === +id); }); var on = !isFav(kind, id); if (on) f.unshift({ t: kind, id: +id, n: n || "" }); setFavs(f); return on; }
  function mineMap() { var o = null; favs().forEach(function (x) { if (x.t === "team") { o = o || {}; o[x.id] = 1; } }); return o; }
  function paintFav() { $$("[data-fav]").forEach(function (b) { var p = b.dataset.fav.split(":"), on = isFav(p[0] === "t" ? "team" : "comp", p[1]); b.classList.toggle("on", on); b.classList.toggle("pri", !on && b.dataset.fav[0] === "t"); var s = $("span", b); if (s) s.textContent = on ? "متابَع" : "تابع"; var svg = $("svg", b); if (svg) svg.outerHTML = U.icon(on ? "starf" : "star", "", 2); }); $$("[data-pick]").forEach(function (b) { b.setAttribute("aria-pressed", String(isFav("team", b.dataset.pick))); }); }

  // ------------------------------------------------------------------ settings switches (the live site's keys)
  var PREF = { nospoil: "tifo.nospoil", free: "tifo.freeonly", goalsnd: "tifo.goalsnd", theme: "tifo.theme", car: "tifo.car" };
  function prefOn(k) { return ls.get(PREF[k], "") === "1"; }
  function paintPrefs() { $$("[data-pref]").forEach(function (b) { b.setAttribute("aria-checked", String(prefOn(b.dataset.pref))); }); B.classList.toggle("nospoil", prefOn("nospoil")); applyTheme(); }
  // «ألوان فريقي»: the app's tint becomes the first followed club's colour, darkened for light mode and lightened for dark until it reads
  function applyTheme() {
    var old = document.getElementById("v5theme"), t = favs().filter(function (x) { return x.t === "team"; })[0];
    if (!prefOn("theme") || !t) { if (old) old.remove(); return; }
    var go = function (TC) { var c = (TC || {})[t.id]; if (!c) return; var hex = function (h) { var n = parseInt(h.slice(1, 7), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }, lum = function (r) { var f = function (v) { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(r[0]) + .7152 * f(r[1]) + .0722 * f(r[2]); };
      var mixTo = function (r, t2, k) { return r.map(function (v, i) { return Math.round(v + (t2[i] - v) * k); }); }, css = function (r) { return "rgb(" + r.join(",") + ")"; };
      var base = hex(c[0]), L = base, D = base, k = 0; while (k < 1 && (1.05) / (lum(L) + .05) < 4) { k += .05; L = mixTo(base, [0, 0, 0], k); } k = 0; while (k < 1 && (lum(D) + .05) / .05 < 6) { k += .05; D = mixTo(base, [255, 255, 255], k); }
      var st = old || document.createElement("style"); st.id = "v5theme"; st.textContent = ":root{--accent:" + css(L) + ";--accent-bg:rgba(" + L.join(",") + ",.12);--on-accent:#fff}@media (prefers-color-scheme:dark){:root{--accent:" + css(D) + ";--accent-bg:rgba(" + D.join(",") + ",.16);--on-accent:#000}}"; if (!old) document.head.appendChild(st); };
    if (window.TC) go(window.TC); else if (cfg.tc && cfg.tc[t.id]) go(cfg.tc); else colorsLoad().then(function () { go(window.TC); });
  }

  // ------------------------------------------------------------------ one click handler for the whole shell
  document.addEventListener("click", function (e) {
    var t = e.target, b;
    if ((b = t.closest(".seg button[data-t]"))) { selectSeg(b.parentNode, b.dataset.t, true); return; }
    if ((b = t.closest("[data-sheet]"))) { e.preventDefault(); openSheet(b.dataset.sheet); return; }
    if ((b = t.closest("[data-close]"))) { closeSheet(b.closest("dialog")); return; }
    if ((b = t.closest("[data-act]"))) { var a = b.dataset.act; if (a === "share") { if (navigator.share) navigator.share({ title: document.title, url: location.href }).catch(function () {}); else copyLink(); } else if (a === "copy") copyLink(); return; }
    if ((b = t.closest("[data-fav]"))) { var p = b.dataset.fav.split(":"), on = toggleFav(p[0] === "t" ? "team" : "comp", p[1], b.dataset.n); paintFav(); toast(on ? "صار في «فريقي»" : "شلناه من «فريقي»"); return; }
    if ((b = t.closest("[data-pick]"))) { var on2 = toggleFav("team", b.dataset.pick, b.dataset.n); paintFav(); if (B.dataset.page === "mine") mineRender(); toast(on2 ? "صار في «فريقي»" : "شلناه من «فريقي»"); return; }
    if ((b = t.closest("[data-pref]"))) { var k = b.dataset.pref; ls.set(PREF[k], prefOn(k) ? "" : "1"); paintPrefs(); if (k === "free" || k === "nospoil") renderHome(); return; }
    if ((b = t.closest("[data-cc]"))) { ls.set("tifo.country", b.dataset.cc); applyTz(); chBox(); if (B.dataset.page === "home") renderHome(); toast("المواعيد بتوقيت " + (CCN[b.dataset.cc] || "")); return; }
    if ((b = t.closest("#days .day"))) { selectDay(b); return; }
    if ((b = t.closest("#rounds button[data-r]"))) { selectRound(b); return; }
    if ((b = t.closest("[data-back]")) && history.length > 1 && document.referrer && document.referrer.indexOf(location.host) >= 0) { e.preventDefault(); history.back(); return; }
    if (B.classList.contains("nospoil") && (b = t.closest(".mr,.fc")) && !b.dataset.shown) { var sc = $(".sc:not(.ko):not(.tbd)", b); if (sc) { e.preventDefault(); b.dataset.shown = 1; b.classList.add("shown"); } }
  });
  function copyLink() { var u = location.href; (navigator.clipboard ? navigator.clipboard.writeText(u) : Promise.reject()).then(function () { toast("انتسخ الرابط"); }, function () { toast(u); }); }

  // ------------------------------------------------------------------ home: day strip, filter, live refresh
  var H = { ms: null, day: V.day, filter: "all", todayN: V.day };
  function renderHome() { var box = $("#homelist"); if (!box || !H.ms) return; var ms = H.ms; if (prefOn("free") && BC) { var cc = country() || "AE", row = BC[cc] || {}; ms = ms.filter(function (m) { var e = row[m.comp]; return e && e.b && e.b.some(function (x) { return x[1]; }); }); }
    box.innerHTML = P.homeList(ms, { filter: H.filter, arab: ARAB, mine: mineMap(), spoil: prefOn("nospoil") }); localize(box);
    var n = H.ms.filter(U.isLive).length, c = $("#livecnt"); if (c) { c.textContent = n; c.hidden = !n; } }
  function homeFilter(k) { H.filter = k; renderHome(); }
  function selectDay(b) { $$("#days .day").forEach(function (x) { x.setAttribute("aria-selected", String(x === b)); }); H.day = b.dataset.d; var s = $("#daysub"); if (s) s.textContent = U.dname(H.day.replace(/(\d{4})(\d\d)(\d\d)/, "$1-$2-$3") + "T12:00:00+04:00");
    b.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" }); var box = $("#homelist"); if (box) box.style.opacity = ".45";
    get("day/" + H.day + ".json", H.day === H.todayN).then(function (j) { H.ms = j.matches || []; if (box) box.style.opacity = ""; renderHome(); }).catch(function () { if (box) { box.style.opacity = ""; box.innerHTML = '<div class="card"><p class="empty">ما قدرنا نحمّل هاليوم.</p></div>'; } }); }
  function homeInit() {
    // the page may be days old: "today" is the UAE day now (the day files are UAE days)
    var t = new Date(Date.now() + 4 * 36e5).toISOString().slice(0, 10), tn = t.replace(/-/g, "");
    if (tn !== V.day) { H.day = H.todayN = tn; var dd = $("#days"); if (dd) dd.outerHTML = P.days(t); var s = $("#daysub"); if (s) s.textContent = U.dname(t + "T12:00:00+04:00"); }
    get("day/" + H.day + ".json", true).then(function (j) { H.ms = j.matches || []; return mergeLive(); }).then(renderHome).catch(function () {});
    var sel = $("#days .day[aria-selected=true]"); if (sel) sel.scrollIntoView({ inline: "center", block: "nearest" });
    setInterval(function () { if (document.hidden || H.day !== H.todayN || !H.ms) return; mergeLive().then(renderHome); }, 20000);
  }
  function mergeLive() { return get("live.json", true).then(function (l) { var L = {}; (l.matches || []).forEach(function (m) { L[m.id] = m; }); cfg.now = Date.now(); H.ms = H.ms.map(function (m) { return L[m.id] ? Object.assign({}, m, L[m.id]) : m; }); }).catch(function () {}); }

  // ------------------------------------------------------------------ match: live refresh every 20 s, the pick, channels in the visitor's country
  // a page is prerendered hourly at most, and a preview is looked at for days: what changes is fetched again when the page is old
  var AGE = V.built ? Date.now() - Date.parse(V.built) : 0;
  function matchInit() {
    var pk = $("#pick"); if (pk) { var s = ls.json("tifo.picks", {})[pk.dataset.mid]; if (s && s.p) selectSegOnly($(".seg", pk), s.p); }
    if (V.snap || !V.id) return;
    var cat = function (st) { return st === "live" || st === "ht" ? "L" : st === "finished" || st === "awarded" ? "F" : "S"; }, cur = V.status, timer = null;
    var run = function (first) { if (document.hidden && !first) return; get("match/" + V.id + ".json", true).then(function (md) { cfg.now = Date.now();
      if (cur && cat(md.status) !== cat(cur)) { var tb = $('.segbar .seg button[aria-selected="true"]'), key = tb && tb.dataset.t; mount(P.match(md, { ch: "" })); chBox(); if (key && $('.segbar .seg button[data-t="' + key + '"]')) selectSeg($(".segbar .seg"), key, false); }
      else { var mh = $("#mh"); if (mh) mh.innerHTML = U.matchHead(md); var ev = $("#ev"); if (ev) ev.innerHTML = U.events(md);
        var st = $("#stx"); if (st && md.stats && md.stats.length) st.innerHTML = U.stats(md) + (U.momentum(md) ? U.grp("الضغط", '<div style="padding:12px 12px 4px">' + U.momentum(md) + "</div>") : "");
        var nt = $("#navt"); if (nt) nt.innerHTML = '<span dir="rtl">' + U.esc(U.matchTitle(md)) + "</span>"; localize(); }
      cur = md.status;
      var soon = md.status === "scheduled" && Date.parse(md.kickoff_utc) - Date.now() < 3 * 36e5;
      if ((U.isLive(md) || soon) && !timer) timer = setInterval(run, 20000); else if (!U.isLive(md) && !soon && timer) { clearInterval(timer); timer = null; } }).catch(function () {}); };
    if (V.live || AGE > 12e4) run(true);
  }
  function teamInit() { if (AGE < 30 * 60e3 || !$("#tfx")) return; get("team/" + V.id + ".json", true).then(function (t) { var tf = P.teamFx(t); $("#tfeat").innerHTML = tf.feat; $("#tfx").innerHTML = tf.fx; localize(); }).catch(function () {}); }
  function compInit() {
    if (AGE < 30 * 60e3 || !V.comp) return; var box = $("#ctab");
    if (box) get("comp/" + V.comp + "/standings.json", true).then(function (st) { var b = $('.seg[data-seg="tv"] button[aria-selected="true"]'); box.innerHTML = P.compTable(st, box.dataset.single === "1", b && b.dataset.t); localize(box); }).catch(function () {});
    var rl = $("#roundlist"); if (rl) get("comp/" + V.comp + "/fixtures.json", true).then(function (j) { FX = U.rounds(j); var b = $("#rounds button[aria-selected=true]"), k = b ? b.dataset.r : FX.cur; rl.innerHTML = U.roundMatches(FX.by[k] || []); localize(rl); }).catch(function () {});
  }
  function selectSegOnly(seg, key) { if (!seg) return; var btns = $$("button[data-t]", seg); btns.forEach(function (b, j) { var on = b.dataset.t === key; b.setAttribute("aria-selected", String(on)); if (on) seg.style.setProperty("--i", j); }); }
  function pickSave(k) { var pk = $("#pick"); if (!pk) return; var o = ls.json("tifo.picks", {}); o[pk.dataset.mid] = { p: k, ko: pk.dataset.kick, h: +pk.dataset.h, a: +pk.dataset.a }; ls.set("tifo.picks", JSON.stringify(o)); toast("توقعك انحفظ في جوالك"); }
  var BC = null;
  function chBox() { var box = $("#chbox"); if (!box || !C.av || !C.av.bc) return; var go = function () { var cc = country() || "AE", e = (BC[cc] || {})[box.dataset.comp];
      box.innerHTML = e && e.b && e.b.length ? e.b.slice(0, 4).map(function (x) { return '<div class="row"><span class="rt">' + U.esc(x[0]) + (x[5] ? "<small>" + U.esc(x[5]) + "</small>" : "") + "</span>" + (x[1] ? '<span class="chip" style="background:var(--accent-bg);color:var(--accent)">مجاني</span>' : "") + "</div>"; }).join("") : '<div class="row"><span class="rt muted">ما عندنا القناة في ' + (CCN[cc] || "بلدك") + "</span></div>"; };
    if (BC) go(); else fetch("/assets/bc." + C.av.bc + ".json").then(function (r) { return r.json(); }).then(function (j) { BC = j; go(); }).catch(function () {}); }
  function loadBC() { if (BC || !C.av || !C.av.bc) return; fetch("/assets/bc." + C.av.bc + ".json").then(function (r) { return r.json(); }).then(function (j) { BC = j; }).catch(function () {}); }

  // ------------------------------------------------------------------ competition: rounds from the season's fixtures (fetched once)
  var FX = null;
  function selectRound(b) { $$("#rounds button").forEach(function (x) { x.setAttribute("aria-selected", String(x === b)); }); b.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
    var box = $("#roundlist"), cid = $("#rounds").dataset.comp; box.style.opacity = ".45";
    (FX ? Promise.resolve(FX) : get("comp/" + cid + "/fixtures.json").then(function (j) { FX = U.rounds(j); return FX; })).then(function (R) { box.innerHTML = U.roundMatches(R.by[b.dataset.r] || []); box.style.opacity = ""; localize(box); }).catch(function () { box.style.opacity = ""; }); }

  // ------------------------------------------------------------------ news: a club's or player's stories load when their tab opens
  function lazyNews(root) { $$(".enews[data-e]", root).forEach(function (box) { if (box.dataset.done) return; box.dataset.done = 1;
    Promise.all([get("news/e/" + box.dataset.e + ".json").catch(function () { return { stories: [] }; }), box.dataset.social ? get("news/social/" + box.dataset.social + ".json").catch(function () { return { videos: [] }; }) : Promise.resolve({ videos: [] })]).then(function (r) {
      var st = (r[0].stories || []).slice(0, 20), vs = (r[1].videos || []).slice(0, 12);
      box.innerHTML = st.length || vs.length ? (st.length ? '<div class="card sepd">' + st.map(U.newsCard).join("") + "</div>" : "") + (vs.length ? '<div class="gh mt2"><h2>من حساباته الرسمية</h2></div>' + U.vids(vs) : "") : '<div class="card"><p class="empty">ما في أخبار عنه هالأيام. <a style="color:var(--accent)" href="' + cfg.base + '/news/">كل الأخبار</a></p></div>'; }); }); }
  var NEWS = null, NK = "all";
  function newsFilter(k) { NK = k; var box = $("#nlist"); if (box && NEWS) box.innerHTML = P.newsList(NEWS, k); }
  function newsInit() {
    get("news/latest.json", true).then(function (d) { NEWS = d.stories || []; newsFilter(NK); }).catch(function () {});
    get("news/social.json").then(function (d) { var vs = (d.videos || []).slice(0, 12); if (vs.length) { $("#nsocb").innerHTML = U.vids(vs); $("#nsoc").hidden = false; } }).catch(function () {});
    var mine = favs().filter(function (x) { return x.t === "team"; }).slice(0, 3); if (mine.length) Promise.all(mine.map(function (x) { return get("news/e/team-" + x.id + ".json").catch(function () { return { stories: [] }; }); })).then(function (rs) { var st = []; rs.forEach(function (r) { st = st.concat((r.stories || []).slice(0, 3)); }); if (st.length) { var s = $("#mynews"); s.innerHTML = '<div class="gh"><h2>أخبار فريقك</h2></div><div class="card sepd">' + st.slice(0, 5).map(U.newsCard).join("") + "</div>"; s.hidden = false; } });
  }

  // ------------------------------------------------------------------ فريقي: every followed team from its small /tn/<id>.json
  function mineRender() {
    var box = $("#minebox"); if (!box) return; var F = favs().filter(function (x) { return x.t === "team"; }), CF = favs().filter(function (x) { return x.t === "comp"; });
    if (!F.length && !CF.length) return;
    box.innerHTML = F.map(function (x) { return '<section class="grp" data-tn="' + x.id + '"><a class="card hd-row" href="' + U.link("t", x.id) + '">' + U.crest({ id: x.id }, "md") + '<span class="rt"><span>' + U.esc(x.n || "") + "</span></span>" + U.chev + "</a></section>"; }).join("") +
      (CF.length ? U.grp("بطولاتك", CF.map(function (x) { return '<a class="row ins" href="' + U.link("c", x.id) + '">' + U.lg(x.id) + '<span class="rt">' + U.esc(x.n || "") + "</span>" + U.chev + "</a>"; }).join("")) : "") +
      U.grp("", U.row({ btn: 1, t: "أضف فريق", attrs: ' data-sheet="sh-pick"', cls: "link" }), { cls: "mt2" });
    // /tn/<id>.json is written by the hourly build: live.json corrects the status and score of anything played since
    var LIVE = get("live.json", true).then(function (l) { var o = {}; (l.matches || []).forEach(function (m) { o[m.id] = m; }); return o; }).catch(function () { return {}; });
    var fix = function (m, L) { return m && L[m.id] ? Object.assign({}, m, L[m.id]) : m; };
    F.forEach(function (x) { Promise.all([fetch("/tn/" + x.id + ".json").then(function (r) { if (!r.ok) throw 0; return r.json(); }), LIVE]).then(function (r) { var t = r[0], L = r[1]; t.next = fix(t.next, L); t.last = fix(t.last, L); if (t.next && t.next.status === "finished") { t.last = t.next; t.next = null; } return t; }).then(function (t) { var sec = $('[data-tn="' + x.id + '"]', box); if (!sec) return;
      var head = '<a class="card hd-row" href="' + U.link("t", x.id) + '" style="border-radius:var(--r) var(--r) 0 0">' + U.crest({ id: x.id }, "md") + '<span class="rt"><span>' + U.esc(t.name_ar || x.n || "") + "</span>" + (t.table ? "<small>" + U.esc(t.table.comp_ar) + " · المركز " + t.table.rank + "</small>" : "") + "</span>" + U.chev + "</a>";
      var rows = [t.next && U.mrow(t.next, { date: 1 }), t.last && U.mrow(t.last, { date: 1, team: x.id })].filter(Boolean).join("");
      sec.innerHTML = '<div class="card">' + head.replace('class="card hd-row"', 'class="hd-row"').replace(' style="border-radius:var(--r) var(--r) 0 0"', "") + rows + U.row({ btn: 1, icon: "bell", c: "#FF3B30", t: "نبّهني بمبارياته", attrs: ' onclick="location.href=\'' + U.link("t", x.id) + '#fx\'"' }) + "</div>"; localize(sec); }).catch(function () {}); });
  }
  function pickFilter() { var q = $("#pickq"); if (!q) return; q.addEventListener("input", function () { var s = q.value.trim(); $$("#sh-pick [data-pick]").forEach(function (b) { b.hidden = s && (b.dataset.n || "").indexOf(s) < 0; }); }); }

  // ------------------------------------------------------------------ search: the live site's index, loaded on first focus
  function fold(s) { return String(s || "").toLowerCase().replace(/[أإآا]/g, "ا").replace(/ة/g, "ه").replace(/ى/g, "ي").replace(/[ً-ْـ]/g, "").trim(); }
  var SIDX = null;
  function searchInit() {
    var q = $("#q"), x = $("#qx"), out = $("#sres"), idle = $("#sidle"); if (!q) return;
    var map = function (u) { var m; if ((m = /^\/c\/([^/]+)\/$/.exec(u))) return cfg.pre.c[m[1]] ? cfg.base + u : u; if ((m = /^\/(t|p|m)\/(\d+)\/$/.exec(u))) return U.link(m[1], +m[2]); return u; };
    var TY = { c: "البطولات", t: "الفرق والمنتخبات", p: "اللاعبين", m: "المباريات", k: "المدربين", f: "الحكام", r: "المواجهات" }, ORD = ["t", "c", "p", "m", "k", "r", "f"];
    var recent = function () { return ls.json("tifo.sq", []); }, remember = function (v) { v = String(v || "").trim(); if (v.length < 2) return; var r = recent().filter(function (y) { return y !== v; }); r.unshift(v); ls.set("tifo.sq", JSON.stringify(r.slice(0, 6))); };
    var paintRecent = function () { var r = recent(), sec = $("#recent"); if (!sec) return; sec.hidden = !r.length; $("#recentl").innerHTML = r.map(function (v) { return '<button type="button" class="row" data-q="' + U.esc(v) + '">' + U.icon("hist", "", 1.8).replace('class=""', 'class="" style="width:20px;height:20px;color:var(--label2)"') + '<span class="rt">' + U.esc(v) + "</span>" + U.chev + "</button>"; }).join(""); };
    paintRecent();
    var load = function () { if (SIDX || !C.av || !C.av.search) return Promise.resolve(SIDX); return fetch("/assets/search." + C.av.search + ".json").then(function (r) { return r.json(); }).then(function (j) { var S = j.s || []; SIDX = (j.i || []).map(function (i) { return { t: i[0], ar: i[1], la: i[2], u: map(i[3]), sub: (typeof i[4] === "number" ? S[i[4]] : i[4]) || "", ko: i[6] || "", k: fold(i[1]) + " " + fold(i[2]) }; }); return SIDX; }); };
    var run = function () { var v = fold(q.value); x.hidden = !q.value; if (v.length < 2) { out.innerHTML = ""; idle.hidden = false; return; } idle.hidden = true; if (!SIDX) { out.innerHTML = '<div class="card"><p class="empty">نحمّل…</p></div>'; load().then(run); return; }
      var hits = SIDX.filter(function (i) { return i.k.indexOf(v) >= 0; }), by = {}; hits.forEach(function (i) { (by[i.t] = by[i.t] || []).push(i); });
      var starts = function (i) { return (fold(i.ar).indexOf(v) === 0 || fold(i.la).indexOf(v) === 0) ? 0 : 1; };
      out.innerHTML = ORD.filter(function (t) { return by[t]; }).map(function (t) { var list = by[t].sort(function (a, b) { return starts(a) - starts(b); }).slice(0, t === "p" ? 12 : 8); return U.grp(TY[t] + ' <span class="num">' + by[t].length + "</span>", list.map(function (i) { var img = i.t === "t" ? U.crest({ id: +((/\/(\d+)\/?$/.exec(i.u) || /id=(\d+)/.exec(i.u) || [])[1]) }, "md").replace('class="cr md"', 'class="lg"') : "";
        return '<a class="row' + (img ? " ins" : "") + '" href="' + U.esc(i.u) + '" data-rem="' + U.esc(i.ar) + '">' + (i.t === "t" ? img : "") + '<span class="rt">' + U.esc(i.ar) + (i.sub || i.la ? "<small>" + U.esc([i.sub, i.ar !== i.la ? i.la : ""].filter(Boolean).join(" · ")) + "</small>" : "") + "</span>" + U.chev + "</a>"; }).join("")); }).join("") || '<div class="card"><p class="empty">ما لقينا شي باسم «' + U.esc(q.value) + "».</p></div>"; };
    q.addEventListener("focus", function () { load(); }, { once: true }); q.addEventListener("input", run);
    x.addEventListener("click", function () { q.value = ""; run(); q.focus(); });
    out.addEventListener("click", function (e) { var a = e.target.closest("[data-rem]"); if (a) remember(q.value); });
    document.addEventListener("click", function (e) { var r = e.target.closest("[data-q]"); if (r) { q.value = r.dataset.q; run(); } var c = e.target.closest("#rclr"); if (c) { ls.set("tifo.sq", "[]"); paintRecent(); } });
    var qs = new URLSearchParams(location.search).get("q"); if (qs) { q.value = qs; run(); } else if (matchMedia("(hover:hover)").matches) q.focus();
  }

  // ------------------------------------------------------------------ the encyclopedia: search across clubs and players, clubs by country on demand
  var WD = null;
  function dbLoad() { return WD ? Promise.resolve(WD) : Promise.all([get("world/index.json"), get("world/leagues.json"), get("s365/index.json").catch(function () { return null; })]).then(function (x) { WD = { I: x[0], L: x[1].leagues, S: x[2], players: null }; return WD; }); }
  function dbInit() {
    var q = $("#wq"), out = $("#wr"), idle = $("#widle"), x = $("#wqx"); if (!q) return;
    var run = function () { var v = fold(q.value); x.hidden = !q.value; if (v.length < 2) { out.innerHTML = ""; idle.hidden = false; return; } idle.hidden = true;
      if (!WD || !WD.players) { out.innerHTML = '<div class="card"><p class="empty">نحمّل الموسوعة…</p></div>'; dbLoad().then(function () { return WD.players ? null : get("world/players.json").then(function (P2) { WD.players = (P2.players || []).map(function (p) { return { t: "p", id: p[0], ar: p[1], en: p[2], club: p[3], k: fold(p[1]) + " " + fold(p[2]) }; }).concat((WD.S ? WD.S.players : []).map(function (p) { return { t: "a", id: p[0], ar: p[1], en: p[2], club: p[3], k: fold(p[1]) + " " + fold(p[2]) }; })); }); }).then(run).catch(function () { out.innerHTML = '<div class="card"><p class="empty">ما قدرنا نحمّل الموسوعة.</p></div>'; }); return; }
      if (!WD.clubs) { WD.clubs = WD.I.clubs.map(function (c) { return { t: "c", id: c[0], ar: c[1], en: c[2], k: fold(c[1]) + " " + fold(c[2]) }; }).concat(WD.S ? WD.S.teams.filter(function (t) { return !t[4]; }).map(function (t) { return { t: "s", id: t[0], ar: t[1], en: t[2], k: fold(t[1]) + " " + fold(t[2]) }; }) : []); WD.cname = {}; WD.I.clubs.forEach(function (c) { WD.cname[c[0]] = c[1]; }); WD.sname = {}; if (WD.S) WD.S.teams.forEach(function (t) { WD.sname[t[0]] = t[1]; }); }
      var hc = WD.clubs.filter(function (c) { return c.k.indexOf(v) >= 0; }).slice(0, 20), hp = WD.players.filter(function (p) { return p.k.indexOf(v) >= 0; }).slice(0, 30);
      out.innerHTML = (hc.length ? U.grp("أندية", hc.map(function (c) { return '<a class="row' + (c.t === "c" ? " ins" : "") + '" href="' + (c.t === "c" ? U.link("t", c.id) : "/db/team/?id=" + c.id) + '">' + (c.t === "c" ? U.crest({ id: c.id }, "md").replace('class="cr md"', 'class="lg"') : "") + '<span class="rt">' + U.esc(c.ar) + '<small class="lat">' + U.esc(c.en || "") + "</small></span>" + U.chev + "</a>"; }).join("")) : "") +
        (hp.length ? U.grp("لاعبين", hp.map(function (p) { return '<a class="row" href="' + (p.t === "p" ? U.link("p", p.id) : "/db/athlete/?id=" + p.id) + '"><span class="rt">' + U.esc(p.ar) + "<small>" + U.esc((p.t === "a" ? WD.sname : WD.cname)[p.club] || "") + "</small></span>" + U.chev + "</a>"; }).join("")) : "") || '<div class="card"><p class="empty">ما لقينا شي.</p></div>'; };
    q.addEventListener("input", run); q.addEventListener("focus", function () { dbLoad().catch(function () {}); }, { once: true }); x.addEventListener("click", function () { q.value = ""; run(); });
    if (location.hash === "#champs") { var d = $("#champs details"); if (d) d.open = true; }
  }
  function dbClubs() { var box = $("#wclubs"); if (!box || box.dataset.done) return; box.dataset.done = 1; dbLoad().then(function () { var cname = {}; WD.I.clubs.forEach(function (c) { cname[c[0]] = c[1]; }); var by = {}; WD.L.forEach(function (l) { (by[l.cc] = by[l.cc] || { n: l.country_ar || l.cc, ls: [] }).ls.push(l); });
    box.innerHTML = '<div class="card cardlist">' + Object.keys(by).sort(function (a, b) { return by[a].n.localeCompare(by[b].n, "ar"); }).map(function (cc) { var c = by[cc]; return '<details class="dz"><summary class="row"><span class="rt">' + U.esc(c.n) + '</span><span class="rv num">' + c.ls.reduce(function (a, l) { return a + l.clubs.length; }, 0) + "</span>" + U.chev + "</summary>" + c.ls.map(function (l) { return '<div class="gh" style="padding-top:10px">' + U.esc(l.name_ar || l.name) + '</div><div class="sepd">' + l.clubs.map(function (k) { return '<a class="row" href="' + U.link("t", k) + '">' + U.crest({ id: k }, "md").replace('class="cr md"', 'class="lg"') + '<span class="rt">' + U.esc(cname[k] || k) + "</span>" + U.chev + "</a>"; }).join("") + "</div>"; }).join("") + "</details>"; }).join("") + "</div>"; }).catch(function () { box.innerHTML = '<div class="card"><p class="empty">ما قدرنا نحمّل الأندية.</p></div>'; }); }

  // ------------------------------------------------------------------ pages for ids outside the prerendered set (same renderers as the build)
  function metaLoad() { return V.meta ? fetch(cfg.base + "/assets/meta." + V.meta + ".json").then(function (r) { return r.json(); }).then(function (m) { cfg.tn = m.tn || {}; }).catch(function () {}) : Promise.resolve(); }
  function namesFor(tids) { return Promise.all(tids.filter(Boolean).map(function (t) { return fetch(cfg.base + "/n/t/" + t + ".json").then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; }); })).then(function (rs) { rs.forEach(function (m) { for (var k in m) if (!cfg.pn[k]) cfg.pn[k] = m[k]; }); }); }
  function colorsLoad() { return C.av && C.av.colors ? new Promise(function (ok) { var s = document.createElement("script"); s.src = "/assets/colors." + C.av.colors + ".js"; s.onload = function () { if (window.TC) cfg.tc = window.TC; ok(); }; s.onerror = ok; document.head.appendChild(s); }) : Promise.resolve(); }
  function mount(pg) {
    document.title = pg.title; $("#main").innerHTML = pg.body; var nt = $("#navt"); if (nt) nt.innerHTML = pg.nav.title || "";
    var lead = $(".nav-lead"); if (lead && pg.nav.back) lead.innerHTML = U.nav(pg.nav).match(/<div class="nav-lead">([\s\S]*?)<\/div><div class="nav-title"/)[1];
    var tr = $(".nav-trail"); if (tr) tr.innerHTML = pg.nav.trail || "";
    if (pg.sheets) { var d = document.createElement("div"); d.innerHTML = pg.sheets; $$("dialog", d).forEach(function (x) { var old = document.getElementById(x.id); if (old) old.remove(); document.body.appendChild(x); x.addEventListener("click", function (e) { if (e.target === x) closeSheet(x); }); }); }
    localize(); observeNav(); paintFav(); paintPrefs(); deepLink();
  }
  function fail(t) { $("#main").innerHTML = '<div class="lt"><h1>ما لقيناها</h1></div><div class="card">' + U.empty(t) + "</div>"; }
  function genInit() {
    var q = new URLSearchParams(location.search), id = q.get("id"), kind = B.dataset.gen; if (!id) return fail("ما حددت شي.");
    Promise.all([metaLoad(), colorsLoad()]).then(function () {
      if (kind === "match") return get("match/" + id + ".json").then(function (md) { return namesFor([md.home.id, md.away.id]).then(function () { V.id = +id; V.live = U.isLive(md) ? 1 : 0; mount(P.match(md, { ch: "" })); matchInit(); }); });
      // a club: its team file when the pipeline tracks it, else the encyclopedia's card (squad, titles) + the live site's small /tn/<id>.json (next, last, table)
      if (kind === "team") return Promise.all([get("team/" + id + ".json").catch(function () { return null; }), get("world/club/" + id + ".json").catch(function () { return null; }), fetch("/tn/" + id + ".json").then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })]).then(function (r) {
        var t = r[0], w = r[1], tn = r[2]; if (!t && !w && !tn) throw new Error("none");
        if (!t) { var GR = {}; ((w && w.squad) || []).forEach(function (m) { if (m[3] === "coach") return; (GR[m[3]] = GR[m[3]] || []).push({ id: m[0], name: m[1], number: m[2] || null }); });
          t = { id: +id, name: (w && w.name) || (tn && tn.name) || "", name_ar: (w && w.name_ar) || (tn && tn.name_ar) || cfg.tn[id] || "", squad: ["keepers", "defenders", "midfielders", "attackers"].filter(function (g) { return GR[g]; }).map(function (g) { return { group: g, players: GR[g] }; }),
            fixtures: tn ? [tn.next].concat(tn.recent || [tn.last]).filter(Boolean) : [] }; }
        var d = { trophies: w && (w.trophies || []).some(function (x) { return x.won > 0; }) ? w.trophies.filter(function (x) { return x.won > 0; }).map(function (x) { return [x.name, x.won, x.seasons || []]; }) : null, card: w && w.venue && w.venue.name ? [{ t: "الملعب", v: U.esc(w.venue.name) + (w.venue.capacity ? ' · <span class="num">' + U.nf(w.venue.capacity) + "</span>" : "") }] : null };
        var tb = tn && tn.table; return Promise.all([namesFor([t.id]), tb ? get("comp/" + tb.comp + "/standings.json").catch(function () { return null; }) : null]).then(function (x) { var st = x[1];
          if (tb && st && st.groups && st.groups[0]) { var row = st.groups[0].rows.filter(function (q) { return q.team.id === +id; })[0]; if (row) { d.row = { c: { id: tb.comp, name_ar: tb.comp_ar }, r: row }; d.st = st; } }
          mount(P.team(t, d)); }); });
      if (kind === "player") return Promise.all([get("player/" + id + "/profile.json").catch(function () { return null; }), get("player/" + id + ".json").catch(function () { return null; }), get("player/" + id + "/tm.json").catch(function () { return null; }), get("player/" + id + "/log.json").catch(function () { return null; }), get("ea/s/" + (+id % 100) + ".json").catch(function () { return null; })]).then(function (r) {
        var prof = r[0], card = r[1]; if (!prof && !card) throw new Error("none"); var b = (prof && prof.bio) || {}, tid = b.team || (card && card.team);
        return namesFor([tid]).then(function () { mount(P.player(+id, { name: cfg.pn[id] || null, latin: b.name || (card && card.name) || "", team: tid ? { id: tid, name_ar: cfg.tn[tid] || "" } : null, pos: b.pos, num: b.shirt, cc: b.cc, card: card ? { goals: card.goals, assists: card.assists, minutes: card.minutes, rating: card.rating } : null, prof: prof, tm: r[2], log: r[3], ea: r[4] && r[4].cards ? r[4].cards[id] : null, photo: cfg.ph[id] ? "/v1/ph/" + id + ".webp" : null })); }); });
      if (kind === "comp") { var c = null; for (var k in cfg.cn) if (String(k) === String(id)) c = cfg.cn[k]; return get("index.json").then(function (ix) { var ce = (ix.competitions || []).filter(function (x) { return String(x.id) === String(id); })[0]; if (!ce) throw new Error("none"); return Promise.all([ce.files && ce.files.standings ? get("comp/" + id + "/standings.json").catch(function () { return null; }) : null, get("comp/" + id + "/fixtures.json"), get("comp/" + id + "/stats.json").catch(function () { return null; })]).then(function (r) { V.comp = ce.id; mount(P.comp(ce, { st: r[0], fx: r[1], stats: r[2] })); }); }); }
      if (kind === "league") return get("s365/comp/" + id + ".json").then(function (c) { mount(P.league(c, { logo: "https://imagecache.365scores.com/image/upload/f_png,w_128,h_128,c_limit,q_auto:eco,dpr_2,d_Competitions:default1.png/Competitions/" + id })); });
    }).catch(function (e) { if (window.console) console.warn("tifo v5:", e && (e.stack || e.message || e)); fail("ما لقينا هالصفحة في بيانات تيفو."); });
  }

  // ------------------------------------------------------------------ boot
  applyTz(); observeNav(); paintFav(); paintPrefs(); deepLink(); pickFilter();
  var pg = B.dataset.page;
  if (B.dataset.gen) genInit();
  else if (pg === "home") { homeInit(); loadBC(); }
  else if (pg === "match") { matchInit(); chBox(); }
  else if (pg === "team") teamInit();
  else if (pg === "comp") compInit();
  else if (pg === "news") newsInit();
  else if (pg === "mine") mineRender();
  else if (pg === "search") searchInit();
  else if (pg === "db") dbInit();
  var cur = $(".pane:not([hidden])"); if (cur) lazyNews(cur);
  var rs = $("#rounds button[aria-selected=true]"); if (rs) rs.scrollIntoView({ inline: "center", block: "nearest" });
})();
