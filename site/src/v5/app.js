/* تيفو v5 in the browser (site/redesign/v5/DESIGN.md; what lives where: ROLLOUT.md). One deferred bundle with ui.js + pages.js:
   - the shell: the nav bar that turns to glass, segmented controls (their panes stamped on first open), sheets (<dialog>, swipe
     down, the back gesture closes them), favourites and settings (the live site's localStorage keys, so nothing a visitor chose is
     lost), the visitor's country and time zone, «آخر تحديث», stale-page dimming
   - live pages with the same renderers as the build: اليوم (day strip, «الكل · مباشر · العرب», every match in the world), the match
     (score, events, lineups, stats every 20 s; the goal moment; «لو خلصت الحين»), team, competition, player, news, فريقي, بحث, الموسوعة
   - the features the owner picked: «جزيرة المباراة», the first-visit setup, app-like navigation (view transitions, prefetch), the
     install prompt and offline copies of your team, the audit badge (server-rendered)
   - the v3 shell's features that pages still use (share images, embed code, player card, lineup builder, push per team, cinema,
     prayer line, channels by country, /thisday/, /national/, /week/, the visit ping, the error beacon)
   The legacy bundle (render.js + v3.js + app.js) loads after this on pages with the old widgets and leaves the shell to v5
   (body[data-v5]). Events kept for the other scripts: tifo:match, tifo:day, tifo:country, tifo:fresh, tifo:nospoil. */
(function () {
  "use strict";
  var U = window.U5, P = window.P5, cfg = U.cfg, V = window.V5 || {}, C = window.V5C || {}, B = document.body, D = document;
  var $ = function (s, r) { return (r || D).querySelector(s); }, $$ = function (s, r) { return [].slice.call((r || D).querySelectorAll(s)); };
  var RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches, PG = B.dataset.page || "", NOW = function () { return Date.now(); };
  cfg.base = ""; cfg.pre = null; cfg.cn = C.cn || {}; cfg.pn = window.PN || {}; cfg.tc = window.TC || {}; cfg.tn = window.TAR || {}; cfg.now = NOW();
  var ls = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; } },
    set: function (k, v) { try { if (v == null || v === "") localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} },
    json: function (k, d) { try { return JSON.parse(localStorage.getItem(k)) || d; } catch (e) { return d; } }
  };
  var ss = { get: function (k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } }, set: function (k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} } };
  function get(p, fresh) { return fetch("/v1/" + p, fresh ? { cache: "no-cache" } : undefined).then(function (r) { if (!r.ok) { var e = new Error(r.status); e.status = r.status; throw e; } return r.json(); }); }
  function getx(u) { return fetch(u).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function fire(name, detail) { try { D.dispatchEvent(new CustomEvent(name, { detail: detail })); } catch (e) {} }
  var toastT; function toast(t, href) { var el = $("#toast"); if (!el) return; el.innerHTML = href ? '<a href="' + U.esc(href) + '">' + U.esc(t) + "</a>" : U.esc(t); el.classList.toggle("lnk", !!href); el.classList.add("on"); clearTimeout(toastT); toastT = setTimeout(function () { el.classList.remove("on"); }, href ? 6000 : 1900); }
  var idle = window.requestIdleCallback || function (f) { return setTimeout(f, 400); };
  var BOT = navigator.webdriver || /bot|crawl|spider|slurp|headless|lighthouse|preview|facebookexternalhit|whatsapp/i.test(navigator.userAgent || "");
  var LEGACY = !!D.querySelector('script[src*="/assets/legacy."]');   // the old widgets' bundle loads after this one on some pages

  // 347: sampled error beacon (1 in 5 page views, at most 3 reports): message, file and line only (the legacy bundle has its own)
  if (!LEGACY && Math.random() < 0.2) (function () { var n = 0; function send(m, s, l, c) { if (n++ >= 3) return; try { fetch("/api/tifo/err", { method: "POST", keepalive: true, headers: { "content-type": "application/json" }, body: JSON.stringify({ m: String(m || "").slice(0, 300), s: s || "", l: l || null, c: c || null, p: location.pathname, v: "v5" }) }).catch(function () {}); } catch (e) {} }
    window.addEventListener("error", function (e) { if (e.filename && e.filename.indexOf(location.origin) !== 0) return; send(e.message, e.filename, e.lineno, e.colno); }); })();

  // ------------------------------------------------------------------ the visitor's country and time zone (the saved choice, else the phone's zone)
  var CTRY = {}; (C.countries || []).forEach(function (c) { CTRY[c[0]] = c; });
  function devTz() { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Dubai"; } catch (e) { return "Asia/Dubai"; } }
  function country() { var c = ls.get("tifo.country", ""); if (c && (CTRY[c] || c === "xx")) return c; var tz = devTz(); for (var k in CTRY) if (CTRY[k][2] === tz) return k; return ""; }
  function ccName(c) { return (CTRY[c] || [])[1] || ""; }
  function localize(root) { $$("time[data-u]", root).forEach(function (t) { var f = t.dataset.f; t.textContent = f === "ago" ? U.ago(t.dataset.u) : U.timeText(t.dataset.u, f); }); }
  function applyTz() { var c = country(); cfg.tz = c && CTRY[c] ? CTRY[c][2] : devTz(); cfg.today = U.ymd(new Date().toISOString()); localize();
    $$("#ccv").forEach(function (v) { v.textContent = ccName(c) || "حسب جوالك"; });
    $$("button[data-cc]").forEach(function (b) { var on = b.dataset.cc === c, m = $("[data-ccv]", b); if (m) m.hidden = !on; b.setAttribute("aria-pressed", String(on)); }); }

  // ------------------------------------------------------------------ freshness: «آخر تحديث» in the footer, and a page older than 2 minutes dims its live digits
  function stamp(g) { var el = $("#updated"); if (el && g) { var d = new Date(g), t = d.toLocaleTimeString("ar-AE-u-nu-latn", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: cfg.tz || "Asia/Dubai" });
      el.textContent = "آخر تحديث " + (U.ymd(d.toISOString()) === cfg.today ? "" : U.dname(d.toISOString(), 1) + " ") + t + "."; }
    D.documentElement.classList.remove("stale"); fire("tifo:fresh", g); }
  (function () { var H = D.documentElement; if (!H.classList.contains("stale") || !H.dataset.built || !/^(home|daypage|all|match)$/.test(PG)) return; var n = D.createElement("p"); n.className = "stalen"; n.textContent = "آخر تحديث للصفحة " + new Date(H.dataset.built).toLocaleTimeString("ar-AE-u-nu-latn", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "Asia/Dubai" }) + "، نجيب الجديد…";
    var at = $(".hdr") || $(".lt"); if (at) at.appendChild(n); D.addEventListener("tifo:fresh", function () { n.remove(); }, { once: true }); setTimeout(function () { n.remove(); }, 15000); })();

  // ------------------------------------------------------------------ nav bar: the large title (or entity header) scrolls under it
  var NAV = $("#nav");
  function navH() { return NAV ? NAV.getBoundingClientRect().height : 52; }
  function observeNav() {
    if (!NAV || !("IntersectionObserver" in window)) return;
    var tgt = $(".lt h1") || $("#mh") || $(".hdr h1") || $(".hdr");
    if (tgt) new IntersectionObserver(function (es) { es.forEach(function (e) { NAV.classList.toggle("stuck", !e.isIntersecting); }); }, { rootMargin: "-" + Math.round(navH()) + "px 0px 0px 0px" }).observe(tgt); else NAV.classList.add("stuck");
    $$(".segbar").forEach(function (sb) { if (sb._obs) return; sb._obs = 1; var s = D.createElement("i"); s.style.cssText = "display:block;height:1px;margin-bottom:-1px"; sb.parentNode.insertBefore(s, sb);
      new IntersectionObserver(function (es) { es.forEach(function (e) { var st = !e.isIntersecting && e.boundingClientRect.top < navH() + 2; sb.classList.toggle("stuck", st); if (NAV) NAV.classList.toggle("merge", st); }); }, { rootMargin: "-" + Math.round(navH()) + "px 0px 0px 0px" }).observe(s); });
  }

  // ------------------------------------------------------------------ segmented controls; a pane's <template class="lazyp"> is stamped the first time it shows
  var OLD = { events: "ov", lineups: "lu", stats: "st", fixtures: "fx", next: "fx", past: "fx", squad: "sq", news: "nw", chist: "hi", nums: "hi", week: "hi", ana: "st", matches: "all" };
  function stampIn(root) { $$("template.lazyp, template.lazys", root).forEach(function (t) { var f = t.content.cloneNode(true); t.parentNode.replaceChild(f, t); }); localize(root); wire(root); }
  function selectSeg(seg, key, user) {
    var btns = $$("button[data-t]", seg), i = -1; btns.forEach(function (b, j) { if (b.dataset.t === key && !b.hidden) i = j; }); if (i < 0) return false;
    btns.forEach(function (b, j) { b.setAttribute("aria-selected", String(j === i)); b.tabIndex = j === i ? 0 : -1; }); seg.style.setProperty("--i", i); seg.classList.remove("none");
    var g = seg.dataset.seg;
    if (g === "f") return homeFilter(key, user), true; if (g === "pick") return pickSave(key), true; if (g === "nk") return newsFilter(key), true;
    $$('.pane[data-g="' + g + '"]').forEach(function (p) { var on = p.dataset.p === key; p.hidden = !on; if (on) stampIn(p); });
    if (user && /^(m|c|t|p|cs|w)$/.test(g)) { try { history.replaceState(history.state, "", location.pathname + location.search + "#" + key); } catch (e) {}
      var sb = seg.closest(".segbar"); if (sb && sb.classList.contains("stuck")) window.scrollTo({ top: sb.getBoundingClientRect().top + scrollY - navH() + 1 }); }
    if (g === "w" && key === "k") dbClubs();
    var pane = $('.pane[data-g="' + g + '"][data-p="' + key + '"]'); if (pane) { lazyNews(pane); playerMounts(pane); var rb = $("#rounds button[aria-selected=true]", pane); if (rb) rb.scrollIntoView({ inline: "center", block: "nearest" }); }
    return true;
  }
  function selectSegOnly(seg, key) { if (!seg) return; $$("button[data-t]", seg).forEach(function (b, j) { var on = b.dataset.t === key; b.setAttribute("aria-selected", String(on)); if (on) { seg.style.setProperty("--i", j); seg.classList.remove("none"); } }); }
  // deep links: a segment by its key (old v3 keys too), a block's row by its anchor (its pane opens, then its sheet), #story, #second
  function deepLink() {
    var h = ""; try { h = decodeURIComponent((location.hash || "").slice(1)); } catch (e) {} if (!h || !/^[\w-]+$/.test(h)) return;
    var seg = $(".segbar .seg"), k = h, sub = { goals: ["num", "g"], assists: ["num", "a"] }[h];
    if (sub) { k = sub[0]; }
    if (seg) { if (!$('button[data-t="' + k + '"]', seg) && OLD[h]) k = OLD[h]; if ($('button[data-t="' + k + '"]', seg) && selectSeg(seg, k, false)) { if (sub) { var ls2 = $('.seg[data-seg="ld"]'); if (ls2) selectSeg(ls2, sub[1], false); } return; } }
    if (h === "story" || h === "second") { setTimeout(function () { openSheet("sh-share"); }, 300); return; }
    var row = $('[data-anchor="' + h + '"]'); if (row) { var p = row.closest(".pane"), sg = p && $('.seg[data-seg="' + p.dataset.g + '"]'); if (sg) selectSeg(sg, p.dataset.p, false); setTimeout(function () { row.scrollIntoView({ block: "center" }); openSheet(row.dataset.sheet, row); }, 120); return; }
    var el = D.getElementById(h); if (el) { var p2 = el.closest(".pane"), sg2 = p2 && $('.seg[data-seg="' + p2.dataset.g + '"]'); if (sg2) selectSeg(sg2, p2.dataset.p, false); setTimeout(function () { el.scrollIntoView({ block: "start" }); }, 60); }
  }
  // RTL arrow keys between tabs (← next, → previous, Home/End), with a roving tabindex
  D.addEventListener("keydown", function (e) { var t = e.target.closest && e.target.closest('[role="tab"]'); if (!t) return; var bar = t.closest('[role="tablist"]'), ts = $$('[role="tab"]', bar).filter(function (x) { return !x.hidden; }), i = ts.indexOf(t), n = -1;
    if (e.key === "ArrowLeft") n = (i + 1) % ts.length; else if (e.key === "ArrowRight") n = (i - 1 + ts.length) % ts.length; else if (e.key === "Home") n = 0; else if (e.key === "End") n = ts.length - 1; else return;
    e.preventDefault(); ts[n].focus(); ts[n].click(); });

  // ------------------------------------------------------------------ sheets (<dialog>): open, close, swipe down; the back gesture closes the open one
  var SHEET = null, OPENER = null;
  function openSheet(id, from) {
    var d = typeof id === "string" ? D.getElementById(id) : id; if (!d) return;
    if (SHEET && SHEET !== d) closeSheet(SHEET, true);
    stampIn(d); d.classList.remove("closing"); OPENER = from || D.activeElement;
    if (d.showModal) { try { if (!d.open) d.showModal(); } catch (e) { d.setAttribute("open", ""); } } else d.setAttribute("open", "");
    SHEET = d; B.classList.add("sheet-on"); fire("tifo:sheet", d);
    if (!(history.state && history.state.v5sheet)) try { history.pushState({ v5sheet: d.id }, ""); } catch (e) {}
    var q = d.id === "sh-pick" || d.id === "sh-onb" ? $("input", d) : null; if (q && matchMedia("(hover:hover)").matches) setTimeout(function () { q.focus(); }, 350);
  }
  function closeSheet(d, quiet) {
    if (!d || d.classList.contains("closing")) return; d.classList.add("closing");
    var done = function () { if (d.close) { try { d.close(); } catch (e) { d.removeAttribute("open"); } } else d.removeAttribute("open"); d.classList.remove("closing"); d.style.transform = ""; if (SHEET === d) SHEET = null; if (!SHEET) B.classList.remove("sheet-on"); if (OPENER && OPENER.focus && !quiet) try { OPENER.focus({ preventScroll: true }); } catch (e) {} };
    if (RM || quiet) done(); else setTimeout(done, 280);
    if (!quiet && history.state && history.state.v5sheet) try { history.back(); } catch (e) {}
  }
  window.addEventListener("popstate", function () { if (SHEET) closeSheet(SHEET, true); var mv = $(".mvsh:not([hidden])"); if (mv) mv.hidden = true; });
  function wireSheet(d) { if (d._w) return; d._w = 1;
    d.addEventListener("click", function (e) { if (e.target === d) closeSheet(d); });
    d.addEventListener("cancel", function (e) { e.preventDefault(); closeSheet(d); });
    var y0 = null, dy = 0, t0 = 0;
    [$(".sh-hd", d), $(".sh-grab", d)].forEach(function (h) { if (!h) return;
      h.addEventListener("touchstart", function (e) { if (e.target.closest("button")) return; y0 = e.touches[0].clientY; dy = 0; t0 = NOW(); d.style.transition = "none"; }, { passive: true });
      h.addEventListener("touchmove", function (e) { if (y0 == null) return; dy = Math.max(0, e.touches[0].clientY - y0); d.style.transform = "translateY(" + dy + "px)"; }, { passive: true });
      h.addEventListener("touchend", function () { if (y0 == null) return; d.style.transition = ""; if (dy > 90 || dy / Math.max(1, NOW() - t0) > 0.6) closeSheet(d); else d.style.transform = ""; y0 = null; }); }); }
  $$("dialog.sheet").forEach(wireSheet);
  // src/media.js (official videos) and older code open <div class="sheet"> through window.TifoSheet: shown above a scrim, closed the same ways
  var SCRIM = null;
  window.TifoSheet = { open: function (el, from) { if (!el) return; if (el.tagName === "DIALOG") return openSheet(el, from); if (!SCRIM) { SCRIM = D.createElement("div"); SCRIM.className = "scrim5"; SCRIM.hidden = true; B.appendChild(SCRIM); SCRIM.onclick = function () { window.TifoSheet.close(); }; }
      el.hidden = false; SCRIM.hidden = false; B.classList.add("sheet-on"); el._v5 = 1; el.addEventListener("click", function (e) { if (e.target.closest("[data-close]")) window.TifoSheet.close(); });
      try { history.pushState({ v5sheet: el.id || "div" }, ""); } catch (e) {} },
    close: function () { $$(".sheet:not(dialog)").forEach(function (s) { if (s._v5) s.hidden = true; }); if (SCRIM) SCRIM.hidden = true; if (!SHEET) B.classList.remove("sheet-on"); if (SHEET) closeSheet(SHEET); } };
  D.addEventListener("keydown", function (e) { if (e.key === "Escape" && SCRIM && !SCRIM.hidden) window.TifoSheet.close(); });

  // ------------------------------------------------------------------ favourites (tifo.favs: [{t:"team"|"comp", id, n}]; tifo.mine = the first team) and settings
  function favs() { var f = ls.json("tifo.favs", []); var m = +ls.get("tifo.mine", 0); if (m && !f.some(function (x) { return x.t === "team" && +x.id === m; })) f.unshift({ t: "team", id: m, n: ls.get("tifo.mine.name", "") }); return f; }
  function setFavs(f) { ls.set("tifo.favs", JSON.stringify(f)); var t = f.filter(function (x) { return x.t === "team"; })[0]; if (t) { ls.set("tifo.mine", String(t.id)); ls.set("tifo.mine.name", t.n || ""); } else { ls.set("tifo.mine", ""); ls.set("tifo.mine.name", ""); } }
  function isFav(kind, id) { return favs().some(function (x) { return x.t === kind && +x.id === +id; }); }
  function toggleFav(kind, id, n) { var on = !isFav(kind, id), f = favs().filter(function (x) { return !(x.t === kind && +x.id === +id); }); if (on) f.push({ t: kind, id: +id, n: n || "" }); setFavs(f); if (kind === "team") { pushTeamChanged(+id, on); offlineKeep(); } return on; }
  function teamIds() { return favs().filter(function (x) { return x.t === "team"; }).map(function (x) { return +x.id; }); }
  function mineMap() { var o = null; teamIds().forEach(function (id) { o = o || {}; o[id] = 1; }); return o; }
  function paintFav() { $$("[data-fav]").forEach(function (b) { var p = b.dataset.fav.split(":"), on = isFav(p[0] === "t" ? "team" : "comp", p[1]); b.classList.toggle("on", on); if (b.dataset.fav[0] === "t") b.classList.toggle("pri", !on); var s = $("span", b); if (s) s.textContent = on ? "متابَع" : "تابع"; var svg = $("svg", b); if (svg) svg.outerHTML = U.icon(on ? "starf" : "star", "", 2); });
    $$("[data-pick]").forEach(function (b) { b.setAttribute("aria-pressed", String(isFav("team", b.dataset.pick))); }); }
  var PREF = { nospoil: "tifo.nospoil", goalsnd: "tifo.goalsnd", theme: "tifo.theme", car: "tifo.car", island: "tifo.island.off" };
  function prefOn(k) { var v = ls.get(PREF[k], "") === "1"; return k === "island" ? !v : v; }   // the island is on unless turned off
  function prefSet(k, on) { ls.set(PREF[k], (k === "island" ? !on : on) ? "1" : ""); }
  function paintPrefs() { $$("[data-pref]").forEach(function (b) { b.setAttribute("aria-checked", String(prefOn(b.dataset.pref))); }); var was = B.classList.contains("nospoil"); B.classList.toggle("nospoil", prefOn("nospoil")); if (was !== prefOn("nospoil")) fire("tifo:nospoil", prefOn("nospoil")); applyTheme(); }
  // «ألوان فريقي»: the app's tint becomes the first followed club's colour, darkened for light mode and lightened for dark until it reads
  function applyTheme() {
    var old = D.getElementById("v5theme"), t = favs().filter(function (x) { return x.t === "team"; })[0], TC = window.TC || cfg.tc || {};
    if (!prefOn("theme") || !t || !TC[t.id]) { if (old) old.remove(); return; }
    var hex = function (h) { var n = parseInt(String(h).slice(1, 7), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }, lum = function (r) { var f = function (v) { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(r[0]) + .7152 * f(r[1]) + .0722 * f(r[2]); };
    var mixTo = function (r, t2, k) { return r.map(function (v, i) { return Math.round(v + (t2[i] - v) * k); }); }, css = function (r) { return "rgb(" + r.join(",") + ")"; };
    var base = hex(TC[t.id][0]), Lc = base, Dc = base, k = 0; while (k < 1 && 1.05 / (lum(Lc) + .05) < 4) { k += .05; Lc = mixTo(base, [0, 0, 0], k); } k = 0; while (k < 1 && (lum(Dc) + .05) / .05 < 6) { k += .05; Dc = mixTo(base, [255, 255, 255], k); }
    var st = old || D.createElement("style"); st.id = "v5theme"; st.textContent = ":root{--accent:" + css(Lc) + ";--accent-bg:rgba(" + Lc.join(",") + ",.12);--on-accent:#fff}@media (prefers-color-scheme:dark){:root{--accent:" + css(Dc) + ";--accent-bg:rgba(" + Dc.join(",") + ",.16);--on-accent:#000}}"; if (!old) D.head.appendChild(st);
  }

  // ------------------------------------------------------------------ one click handler for the whole shell
  D.addEventListener("click", function (e) {
    var t = e.target, b;
    if (!t.closest) return;
    if ((b = t.closest(".seg button[data-t]"))) { selectSeg(b.parentNode, b.dataset.t, true); return; }
    if ((b = t.closest("[data-sheet]"))) { e.preventDefault(); openSheet(b.dataset.sheet, b); return; }
    if ((b = t.closest("dialog [data-close]"))) { closeSheet(b.closest("dialog")); return; }
    if ((b = t.closest("[data-act]"))) { var a = b.dataset.act; if (a === "share") { if (navigator.share) navigator.share({ title: D.title, url: location.href.split("#")[0] }).catch(function () {}); else copyLink(); } else if (a === "copy") copyLink(); return; }
    if ((b = t.closest("[data-fav]"))) { var p = b.dataset.fav.split(":"), on = toggleFav(p[0] === "t" ? "team" : "comp", p[1], b.dataset.n); paintFav(); toast(on ? "صار في «فريقي»" : "شلناه من «فريقي»"); if (on && p[0] === "t") afterFollow(+p[1]); return; }
    if ((b = t.closest("[data-pick]"))) { var on2 = toggleFav("team", b.dataset.pick, b.dataset.n); paintFav(); if (PG === "mine") mineRender(); if (!b.closest("#sh-onb")) toast(on2 ? "صار في «فريقي»" : "شلناه من «فريقي»"); return; }
    if ((b = t.closest("[data-pref]"))) { var k = b.dataset.pref; prefSet(k, !prefOn(k)); paintPrefs(); if (k === "nospoil") renderHome(); if (k === "car") carMode(); if (k === "island") island(); if (k === "goalsnd" && prefOn("goalsnd")) whistle(); return; }
    if ((b = t.closest("button[data-cc]")) && !b.closest("#sh-onb")) { ls.set("tifo.country", b.dataset.cc); applyTz(); chBox(); prayer(); if (PG === "home" || PG === "daypage" || PG === "all") renderHome(); fire("tifo:country", { cc: b.dataset.cc }); toast("المواعيد بتوقيت " + (ccName(b.dataset.cc) || "بلدك")); return; }
    if ((b = t.closest("[data-onb]"))) { e.preventDefault(); onbOpen(true); return; }
    if ((b = t.closest("#days .day"))) { selectDay(b); return; }
    if ((b = t.closest("#rounds button[data-r]"))) { selectRound(b); return; }
    if ((b = t.closest("[data-back]")) && history.length > 1 && D.referrer && D.referrer.indexOf(location.host) >= 0 && !e.metaKey && !e.ctrlKey) { e.preventDefault(); history.back(); return; }
    if (B.classList.contains("nospoil") && (b = t.closest(".mr,.fc,.island")) && !b.classList.contains("shown")) { var sc = $(".sc:not(.ko):not(.tbd)", b); if (sc) { e.preventDefault(); b.classList.add("shown"); } }
  });
  function copyLink() { var u = location.href.split("#")[0]; (navigator.clipboard ? navigator.clipboard.writeText(u) : Promise.reject()).then(function () { toast("انتسخ الرابط"); }, function () { try { prompt("انسخ الرابط", u); } catch (e) {} }); }
  // things the build or a re-render put on the page that need a script: switches, the live minute, countdowns
  function wire(root) { $$("[data-pref]", root).forEach(function (b) { b.setAttribute("aria-checked", String(prefOn(b.dataset.pref))); }); $$("dialog.sheet", root).forEach(wireSheet); }

  // ------------------------------------------------------------------ countdowns ([data-ko] on a feature card or a hero line) and the live minute
  function cdText(ms) { var d = Math.max(0, ms), dd = Math.floor(d / 864e5), hh = Math.floor(d / 36e5) % 24, mm = Math.floor(d / 6e4) % 60, s = Math.floor(d / 1e3) % 60, p2 = function (n) { return (n < 10 ? "0" : "") + n; };
    return (dd ? (dd === 1 ? "يوم" : dd === 2 ? "يومين" : dd + (dd <= 10 ? " أيام" : " يوم")) + " و" : "") + '<bdi dir="ltr" class="num">' + p2(hh) + ":" + p2(mm) + ":" + p2(s) + "</bdi>"; }
  setInterval(function () { $$("[data-cdko]").forEach(function (el) { var d = Date.parse(el.dataset.cdko) - NOW(); if (d <= 0) { el.innerHTML = "على وشك تبدا"; el.removeAttribute("data-cdko"); return; } el.innerHTML = (el.dataset.cdl || "تبدا بعد") + " " + cdText(d); }); }, 1000);
  function cdAttach(root) { $$(".fc[data-mid]", root).forEach(function (a) { if ($(".fc-cd", a)) return; var m = (H.ms || []).concat((TF && TF.fixtures) || []).filter(function (x) { return String(x.id) === a.dataset.mid; })[0];
    if (!m || m.status !== "scheduled" || m.time_tbd || !m.kickoff_utc) return; var d = Date.parse(m.kickoff_utc) - NOW(); if (d <= 0 || d > 4 * 864e5) return;
    var el = D.createElement("div"); el.className = "fc-cd"; el.dataset.cdko = m.kickoff_utc; el.innerHTML = "تبدا بعد " + cdText(d); a.appendChild(el); }); }

  // ================================================================== اليوم: day strip, filter, our matches + the world's, live refresh
  var H = { ms: null, day: V.day, filter: "all", todayN: V.day, world: null, wlv: {}, open: ls.json("tifo.allopen", {}) }, BC = null, ARAB = {}, ARABC = {}, TF = null;
  (V.arab || []).forEach(function (id) { ARAB[id] = 1; }); (V.arabComp || []).forEach(function (id) { ARABC[id] = 1; });
  function ymdOf(n) { return n.replace(/(\d{4})(\d\d)(\d\d)/, "$1-$2-$3"); }
  // a day is the visitor's own calendar day (v3's QA 23, lost in the v5 rollout and restored 2026-10-06): the poller's day files are
  // UAE days, so a visitor west of the UAE needs that day's file and the next one (Morocco's evening is the UAE's night), east of it
  // the one before; the matches kept are the ones that kick off on the visitor's date (a match with no time yet, by its UAE date)
  function dShift(Y, k) { var p = ymdOf(Y).split("-").map(Number); return new Date(Date.UTC(p[0], p[1] - 1, p[2] + k)).toISOString().slice(0, 10).replace(/-/g, ""); }
  function tzOff(Y) { var iso = ymdOf(Y) + "T12:00:00.000Z", p = U.parts(iso); return p ? Math.round((Date.UTC(p.y, p.mo - 1, p.d, +p.h, +p.mi) - Date.parse(iso)) / 60000) : 240; }
  function loadDay(Y, fresh) {
    var off = tzOff(Y), files = off < 240 ? [Y, dShift(Y, 1)] : off > 240 ? [dShift(Y, -1), Y] : [Y], want = ymdOf(Y);
    return Promise.all(files.map(function (f) { return get("day/" + f + ".json", fresh).catch(function () { return null; }); })).then(function (js) {
      if (!js.some(Boolean)) throw new Error("no day file");
      var seen = {}, out = [];
      js.forEach(function (j) { ((j && j.matches) || []).forEach(function (m) { if (seen[m.id]) return; seen[m.id] = 1;
        var d = m.time_tbd || !m.kickoff_utc ? String(m.kickoff_uae || "").slice(0, 10) : U.ymd(m.kickoff_utc); if (d === want) out.push(m); }); });
      return { matches: out }; });
  }
  // a redraw that keeps every row whose score and state did not change (same node: nothing repaints, nothing moves); a list with
  // other rows or another order is drawn again whole
  function patchList(box, html) {
    var t = D.createElement("div"); t.innerHTML = html; localize(t); var A = [].slice.call(box.children), Bn = [].slice.call(t.children);
    if (!A.length || A.length !== Bn.length || A.some(function (x, i) { return x.id !== Bn[i].id; })) { box.innerHTML = html; return; }
    var heads = function (r) { return $$(".gh, .hd-row", r).map(function (x) { return x.textContent; }).join("|"); }, key = function (r) { var m = $(".mr-m", r) || $(".fc-body", r) || r, f = $(".fc-top .st", r); return m.textContent + "|" + (f ? f.textContent : ""); };
    A.forEach(function (o, s) { var n = Bn[s], a = $$("[data-mid]", o), b = $$("[data-mid]", n);
      if (a.length !== b.length || heads(o) !== heads(n) || a.some(function (x, i) { return x.dataset.mid !== b[i].dataset.mid || x.tagName !== b[i].tagName || x.className.replace(/\s*shown/, "") !== b[i].className; })) { o.parentNode.replaceChild(n, o); return; }
      a.forEach(function (x, i) { if (key(x) !== key(b[i])) x.parentNode.replaceChild(b[i], x); }); });
  }
  function renderHome() {
    var box = $("#homelist"); if (!box || !H.ms) return;
    patchList(box, P.homeList(H.ms, { filter: H.filter, arab: ARAB, arabComp: ARABC, mine: mineMap(), spoil: prefOn("nospoil"), world: !!H.world, featId: !mineMap() && NOW() < H.pinUntil ? H.pinFeat : null })); localize(box); cdAttach(box); natCountdown();
    var n = H.ms.filter(U.isLive).length + (H.world ? worldLive() : 0), c = $("#livecnt"); if (c) { c.textContent = n; c.hidden = !n; }
    renderWorld(); mineHome(); fire("tifo:day", { ms: H.ms, off: H.day === H.todayN ? 0 : 1, live: { matches: H.ms.filter(U.isLive) } });
  }
  // the first data of the page: the build's list stays (no redraw, so nothing moves and the first paint stays the largest) when it
  // shows the same matches the same way: same day and data, no favourites to put first, no hidden scores
  function homeFresh() { var box = $("#homelist");
    if (!box || H.day !== V.day || !V.sig || U.sig(H.ms) !== V.sig || H.filter !== "all" || mineMap() || prefOn("nospoil")) return renderHome();
    cdAttach(box); natCountdown(); var n = H.ms.filter(U.isLive).length, c = $("#livecnt"); if (c) { c.textContent = n; c.hidden = !n; }
    renderWorld(); mineHome(); fire("tifo:day", { ms: H.ms, off: H.day === H.todayN ? 0 : 1, live: { matches: H.ms.filter(U.isLive) } }); }
  function worldLive() { var n = 0; (H.world && H.world.leagues || []).forEach(function (lg) { if (lg.ours) return; lg.matches.forEach(function (m) { var l = H.wlv[m.id], s = (l && l.status) || m.status; if (s === "live" || s === "ht") n++; }); }); return n; }
  function renderWorld() { var box = $("#world"); if (!box) return; if (!H.world) { if (!box.dataset.open) box.innerHTML = ""; return; }
    var ours = {}; (H.ms || []).forEach(function (m) { ours[m.id] = 1; });
    var w = P.worldList(H.world, { filter: H.filter, open: H.open, openAll: !!box.dataset.open, ymd: H.day, lv: H.wlv, skip: ours, spoil: prefOn("nospoil") }); box.innerHTML = w.html; localize(box);
    $$("details.wl", box).forEach(function (d) { d.addEventListener("toggle", function () { if (H.filter !== "all") return; H.open[d.dataset.lg] = d.open ? 1 : 0; ls.set("tifo.allopen", JSON.stringify(H.open)); }); }); }
  function homeFilter(k, user) { H.filter = k; renderHome(); if (user) ss.set("tifo.home." + location.pathname, H.day + "|" + k); if (k !== "all" && !H.world) worldLoad(); }
  function selectDay(b) { $$("#days .day").forEach(function (x) { x.setAttribute("aria-selected", String(x === b)); }); H.day = b.dataset.d; var s = $("#daysub"); if (s) s.textContent = U.dname(ymdOf(H.day) + "T12:00:00+04:00");
    b.scrollIntoView({ inline: "center", block: "nearest", behavior: RM ? "auto" : "smooth" }); var box = $("#homelist"); if (box) box.classList.add("dim");
    ss.set("tifo.home." + location.pathname, H.day + "|" + H.filter); H.world = null; H.wlv = {};
    loadDay(H.day, H.day === H.todayN).then(function (j) { H.ms = j.matches || []; return H.day === H.todayN ? mergeLive() : null; }).then(function () { if (box) box.classList.remove("dim"); renderHome(); worldMaybe(); })
      .catch(function () { if (box) { box.classList.remove("dim"); box.innerHTML = '<div class="card"><p class="empty">ما قدرنا نحمّل هاليوم.</p></div>'; } }); }
  function mergeLive() { return get("live.json", true).then(function (l) { var Lm = {}; (l.matches || []).forEach(function (m) { Lm[m.id] = m; }); cfg.now = NOW(); H.ms = H.ms.map(function (m) { return Lm[m.id] ? Object.assign({}, m, Lm[m.id]) : m; }); stamp(l.generated); }).catch(function () {}); }
  function worldLoad() { var y = H.day; return get("all/" + y + ".json", y === H.todayN).then(function (doc) { if (y !== H.day) return; H.world = doc; renderHome(); }).catch(function () { var box = $("#world"); if (box && box.dataset.open) box.innerHTML = ""; }); }
  function worldLiveLoad() { if (!H.world || H.day !== H.todayN) return Promise.resolve(); return get("all/live.json", true).then(function (lv) { var by = {}; (lv.matches || []).forEach(function (r) { by[r.id] = r; }); H.wlv = by; }).catch(function () {}); }
  function worldMaybe() { var box = $("#world"); if (!box) return; if (box.dataset.open) { worldLoad(); return; }
    idle(function () { if ("IntersectionObserver" in window) { var io = new IntersectionObserver(function (es) { if (es.some(function (e) { return e.isIntersecting; })) { io.disconnect(); if (!H.world) worldLoad(); } }, { rootMargin: "600px 0px" }); io.observe(box); } else worldLoad(); }); }   // after the page settles: the world list is the biggest file
  function homeInit() {
    var t = U.ymd(new Date(NOW()).toISOString()) || new Date(NOW() + 4 * 36e5).toISOString().slice(0, 10), tn = t.replace(/-/g, ""), box = $("#homelist");   // the visitor's date
    var isTomorrow = PG === "daypage" && /\/tomorrow\//.test(location.pathname), want = isTomorrow ? dShift(tn, 1) : tn;
    H.todayN = tn; var f0 = $("#feat .fc[data-mid]"); H.pinFeat = f0 && f0.dataset.mid; H.pinUntil = NOW() + 60e3;   // the build's featured match holds for a minute
    var saved = (ss.get("tifo.home." + location.pathname) || "").split("|");   // back to this page: the day and filter it was on
    if (saved[0] && /^\d{8}$/.test(saved[0])) want = saved[0]; if (saved[1] && /^(all|live|arab)$/.test(saved[1])) H.filter = saved[1];
    var q = new URLSearchParams(location.search); if (q.get("f") === "live") H.filter = "live"; var qd = { yesterday: -1, tomorrow: 1 }[q.get("d")]; if (qd) want = dShift(tn, qd);
    if (want !== V.day || tn !== V.today.replace(/-/g, "")) { H.day = want; var dd = $("#days"); if (dd) dd.outerHTML = P.days(ymdOf(want)); var s = $("#daysub"); if (s) s.textContent = U.dname(ymdOf(want) + "T12:00:00+04:00"); if (box && want !== V.day) box.classList.add("dim"); }
    if (H.filter !== "all") selectSegOnly($('.seg[data-seg="f"]'), H.filter);
    loadDay(H.day, true).then(function (j) { H.ms = j.matches || []; return H.day === H.todayN ? mergeLive() : null; }).then(function () { if (box) box.classList.remove("dim"); homeFresh(); worldMaybe(); }).catch(function () { if (box) box.classList.remove("dim"); });
    var sel = $("#days .day[aria-selected=true]"); if (sel) sel.scrollIntoView({ inline: "center", block: "nearest" });
    // live: our list every 20 s and the world's every 30 s while something is live or about to start, every 2 minutes otherwise
    (function tick() { var live = (H.ms || []).some(function (m) { var k = Date.parse(m.kickoff_utc); return U.isLive(m) || (m.status === "scheduled" && k - NOW() < 15 * 60e3 && k > NOW() - 3 * 36e5); }) || (H.world && worldLive());
      setTimeout(function () { if (D.hidden || H.day !== H.todayN || !H.ms) return tick(); Promise.all([mergeLive(), worldLiveLoad()]).then(function () { renderHome(); tick(); }); }, live ? 20000 : 120000); })();
    D.addEventListener("visibilitychange", function () { if (!D.hidden && H.day === H.todayN && H.ms) Promise.all([mergeLive(), worldLiveLoad()]).then(renderHome); });
    bdays();   // the channels file (bc) loads only where a page shows channels
  }
  // «فريقك» on اليوم: each followed team not already on today's list — live, the result of the last day, or the next match
  var TN = {}; function tnGet(id) { return TN[id] || (TN[id] = fetch("/tn/" + id + ".json").then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })); }
  function mineHome() { var box = $("#minehome"); if (!box) return; var ids = teamIds().slice(0, 4), on = {}; (H.ms || []).forEach(function (m) { on[m.home.id] = on[m.away.id] = 1; });
    var rest = ids.filter(function (id) { return !on[id]; }); if (!rest.length || H.day !== H.todayN || H.filter !== "all") { box.hidden = true; return; }
    Promise.all(rest.map(tnGet)).then(function (ts) { var rows = ts.filter(Boolean).map(function (t) { var nx = t.next, la = t.last, m = la && la.status === "finished" && NOW() - Date.parse(la.kickoff_utc) < 30 * 36e5 ? la : nx || la; if (!m) return "";
        return '<a class="hd-row" href="/t/' + t.id + '/">' + U.crest({ id: t.id }, "") + '<span class="rt"><span>' + U.esc(t.name_ar || t.name) + "</span>" + (t.table ? "<small>المركز " + t.table.rank + " · " + U.esc(t.table.comp_ar) + "</small>" : "") + "</span>" + U.chev + "</a>" + U.mrow(m, { date: 1, team: m.status === "finished" ? t.id : null, spoil: prefOn("nospoil") }); }).filter(Boolean);
      if (!rows.length) { box.hidden = true; return; } box.innerHTML = '<div class="gh"><h2>فريقك</h2><a href="/mine/">فريقي</a></div><div class="card">' + rows.join("") + "</div>"; localize(box); box.hidden = false; }); }
  // the visitor's national team counts down under the featured card when its next match is within four days (#uaecd in v3)
  function natCountdown() { var box = $("#natcd"); if (!box || H.day !== H.todayN) return; var nid = (window.NAT || {})[country() || "AE"]; if (!nid) return;
    tnGet(nid).then(function (t) { var m = t && t.next; if (!m || m.time_tbd || !m.kickoff_utc || $('.fc[data-mid="' + m.id + '"]')) return; var d = Date.parse(m.kickoff_utc) - NOW(); if (d <= 0 || d > 4 * 864e5) return;
      box.innerHTML = '<a class="card natcd" href="/m/' + m.id + '/"><span class="rt"><b>' + U.tname(m.home) + " ضد " + U.tname(m.away) + '</b><small data-cdko="' + U.esc(m.kickoff_utc) + '" data-cdl="منتخبك يلعب بعد">منتخبك يلعب بعد ' + cdText(d) + "</small></span>" + U.chev + "</a>"; }); }
  // «اليوم في التقويم»: players' birthdays and club anniversaries (#bdays carries the anniversaries; birthdays from players/birthdays/<mm-dd>.json)
  function bdays() { var el = $("#bdays"); if (!el) return; var now = new Date(), md = U.ymd(now.toISOString()).slice(5), yr = +U.ymd(now.toISOString()).slice(0, 4), items = [];
    try { (JSON.parse(el.dataset.an || "{}")[md] || []).forEach(function (a) { items.push('<li>ذكرى تأسيس <a href="/t/' + a[0] + '/">' + U.esc(a[1]) + '</a> <span class="muted">(<span class="num">' + (yr - a[2]) + "</span> سنة، من " + a[2] + ")</span></li>"); }); } catch (e) {}
    var draw = function () { if (!items.length) return; el.innerHTML = '<ul class="facts-l">' + items.join("") + "</ul>"; var g = $("#bdaysg"); if (g) g.hidden = false; };
    get("players/birthdays/" + md + ".json").then(function (b) { (b.players || []).slice(0, 8).forEach(function (p) { var age = p.dob ? yr - +p.dob.slice(0, 4) : null; items.push("<li>عيد ميلاد " + (p.name_ar ? U.esc(p.name_ar) : '<span class="lat">' + U.esc(p.name) + "</span>") + (age ? ' <span class="muted">(<span class="num">' + age + "</span> سنة)</span>" : "") + "</li>"); }); draw(); }).catch(draw); }

  // ================================================================== the match: live every 20 s, the goal moment, the pick, channels and prayer for the visitor
  var MD = null, LASTSC = null, LASTST = null, T0 = D.title;
  try { var ms0 = $("#msum"); if (ms0) MD = JSON.parse(ms0.textContent); } catch (e) {}
  function cat(st) { return st === "live" || st === "ht" ? "L" : st === "finished" || st === "awarded" ? "F" : "S"; }
  function matchInit() {
    pickInit(); chBox(); prayer(); rememberOpened();
    // 357: before kickoff the header counts down (within four days), then the live score takes over
    if (MD && MD.status === "scheduled" && !MD.time_tbd && MD.kickoff_utc) { var dko = Date.parse(MD.kickoff_utc) - NOW(), mh0 = $("#mh"); if (mh0 && dko > 0 && dko < 4 * 864e5) { var cdp = D.createElement("p"); cdp.className = "mh-cd"; cdp.dataset.cdko = MD.kickoff_utc; cdp.innerHTML = "تبدا بعد " + cdText(dko); mh0.after(cdp); } }
    if (!V.id) return;
    var timer = null, run = function (first) { if (D.hidden && !first) return;
      get("match/" + V.id + ".json", true).then(function (md) { cfg.now = NOW(); var was = MD; MD = md; matchPaint(md, was); stamp(md.generated);
        var soon = md.status === "scheduled" && Date.parse(md.kickoff_utc) - NOW() < 90 * 60e3 && Date.parse(md.kickoff_utc) > NOW() - 4 * 36e5;
        if ((U.isLive(md) || soon) && !timer) timer = setInterval(run, 20000); else if (!U.isLive(md) && !soon && timer) { clearInterval(timer); timer = null; } }).catch(function () {}); };
    var age = V.built ? NOW() - Date.parse(V.built) : 0;
    if (V.live || age > 12e4) run(true);
    else if (V.ko && V.status === "scheduled") { var d = Date.parse(V.ko) - NOW() - 75 * 60e3; if (d > 0 && d < 2147483000) setTimeout(function () { run(true); }, d); }   // a page opened long before kickoff wakes 75 minutes before
    setInterval(function () { if (MD && U.isLive(MD) && !D.hidden) { cfg.now = NOW(); var mh = $("#mh"); if (mh) mh.innerHTML = U.matchHead(MD); } }, 30000);   // the minute moves between polls
    D.addEventListener("visibilitychange", function () { if (!D.hidden && MD && (U.isLive(MD) || MD.status === "scheduled")) run(true); });
  }
  function matchPaint(md, was) {
    if (was && !was._seen && was.status === "finished" && md.status === "finished" && was.score && md.score && was.score.home === md.score.home && was.score.away === md.score.away) { md._seen = 1; stamp(md.generated); fire("tifo:match", md); return; }   // nothing new since the build
    md._seen = 1;
    if (was && cat(was.status) === "S" && cat(md.status) !== "S") matchGoesLive();
    var mh = $("#mh"); if (mh) mh.innerHTML = U.matchHead(md);
    meylis(md);
    var ev = $("#ev"); if (ev) ev.innerHTML = U.events(md);
    var st = $("#stx"); if (st && md.stats && md.stats.length) st.innerHTML = U.stats(md) + (U.momentum(md) ? U.grp("الضغط", '<div style="padding:12px 12px 4px">' + U.momentum(md) + "</div>") : "");
    var lu = $("#lu"); if (lu && md.lineups && md.lineups.home && (md.lineups.home.starters || []).length) { var sel = $('.seg[data-seg="lu"] button[aria-selected="true"]'), k = sel && sel.dataset.t; lu.innerHTML = U.lineups(md); if (k) selectSegOnly($('.seg[data-seg="lu"]', lu), k), $$('.pane[data-g="lu"]', lu).forEach(function (p) { p.hidden = p.dataset.p !== k; }); }
    var cu = $("#catchup"); if (cu && window.TR && window.TR.catchup && cat(md.status) !== "S") { var h = window.TR.catchup(md); if (h) { cu.innerHTML = h; cu.hidden = false; } }
    var nt = $("#navt"); if (nt) nt.innerHTML = '<span dir="rtl">' + U.esc(U.matchTitle(md)) + "</span>";
    ["#mh", "#ev", "#lu", "#stx"].forEach(function (s) { unlinkDead($(s)); }); localize(); goalWatch(md); liveTable(md); pickSettle(md); fire("tifo:match", md);
  }
  // الميلس (meylis.elyoxe.com): the match's voice room, offered from 3 h before kickoff until full time (v3's shell.js had it, 2026-10-06)
  function meylis(md) {
    var hd = $("header.hdr"), box = hd && $(".mh-ml", hd), ko = Date.parse(md.kickoff_utc || "");
    var near = U.isLive(md) || (md.status === "scheduled" && ko > 0 && ko - NOW() < 3 * 36e5);
    if (hd && near && !box) { box = D.createElement("div"); box.className = "th-acts mh-ml";
      box.innerHTML = '<a class="pill" data-mid="' + U.esc(String(V.id || md.id)) + '" href="https://meylis.elyoxe.com/r/' + encodeURIComponent(V.id || md.id) + '" rel="noopener">سولفها فالميلس</a>';
      var meta = $(".mh-meta", hd); if (meta) meta.after(box); else hd.appendChild(box); mlCount(); }
    else if (box && !near) box.remove();
  }
  /* how many are in the match's room right now (meylis /v1/live, CORS *), every minute while the pill shows (owner 2026-10-09, item 6) */
  var mlT = 0;
  function mlCount() {
    clearTimeout(mlT); var a = $("header.hdr .mh-ml a[data-mid]"); if (!a) return;
    fetch("https://meylis.elyoxe.com/v1/live", { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (j) { var n = j["m-" + a.dataset.mid] || 0; a.textContent = n ? "سولفها فالميلس · " + n + " داخل الحين" : "سولفها فالميلس"; })
      .catch(function () {}).then(function () { mlT = setTimeout(mlCount, 60e3); });
  }
  // a player without a page is plain text (window.PP: the players of this page that have one), as the build's dead-link pass leaves it
  function unlinkDead(root) { var PP = window.PP; if (!PP || !root) return; $$('a[href^="/p/"]', root).forEach(function (a) { var m = /^\/p\/(\d+)\//.exec(a.getAttribute("href")); if (!m || PP[m[1]]) return;
    var s = D.createElement("span"); for (var i = 0; i < a.attributes.length; i++) if (a.attributes[i].name !== "href") s.setAttribute(a.attributes[i].name, a.attributes[i].value); while (a.firstChild) s.appendChild(a.firstChild); a.parentNode.replaceChild(s, a); }); }
  // kickoff on an open page: المباراة gets its events block, الأرقام appears, the pick and «شو على المحك» step aside
  function matchGoesLive() {
    var ov = $('.pane[data-g="m"][data-p="ov"]'); if (ov && !$("#ev")) { var s = D.createElement("section"); s.className = "grp"; s.innerHTML = '<div class="gh"><h2>الأحداث</h2></div><div id="ev"></div>'; ov.insertBefore(s, ov.firstChild); var lt = D.createElement("div"); lt.id = "ltable"; s.after(lt); }
    var seg = $('.seg[data-seg="m"]'); if (seg) { var b0 = $('button[data-t="ov"] .sl', seg); if (b0) b0.textContent = "المباراة";
      if (!$('button[data-t="st"]', seg)) { var b = D.createElement("button"); b.type = "button"; b.setAttribute("role", "tab"); b.dataset.t = "st"; b.setAttribute("aria-selected", "false"); b.innerHTML = '<span class="sl">الأرقام</span>'; var h2h = $('button[data-t="h2h"]', seg); seg.insertBefore(b, h2h); seg.style.setProperty("--n", $$("button[data-t]", seg).length);
        var lup = $('.pane[data-g="m"][data-p="lu"]'), p = D.createElement("section"); p.className = "pane"; p.dataset.g = "m"; p.dataset.p = "st"; p.hidden = true; p.innerHTML = '<div id="stx"></div>'; if (lup) lup.after(p); } }
    var cd0 = $(".mh-cd"); if (cd0) cd0.remove();
    ["#pick", "#stakes"].forEach(function (s) { var el = $(s); if (el) { var g = el.closest(".grp") || el; g.hidden = true; } });
  }
  // the goal moment: the score flips, the header flashes in the scorer's colour, «هدف» slides in from his side; one polite announcement; the whistle
  function say(t) { var a = $("#alive"); if (!a || B.classList.contains("nospoil")) return; a.textContent = ""; setTimeout(function () { a.textContent = t; }, 60); }
  function goalWatch(md) {
    if (!md || !md.score) { LASTST = md && md.status; return; }
    var p = LASTSC; LASTSC = { home: md.score.home, away: md.score.away };
    if (LASTST && LASTST !== "finished" && md.status === "finished") say("انتهت. " + U.tnameT(md.home) + " " + md.score.home + "، " + U.tnameT(md.away) + " " + md.score.away);
    LASTST = md.status;
    if (p && (md.score.home > p.home || md.score.away > p.away)) goalMoment(md, md.score.home > p.home ? "home" : "away");
    else if (p && (md.score.home < p.home || md.score.away < p.away)) { say("انلغى هدف. " + U.tnameT(md.home) + " " + md.score.home + "، " + U.tnameT(md.away) + " " + md.score.away); }
    D.title = U.isLive(md) && !B.classList.contains("nospoil") ? md.score.home + "-" + md.score.away + " · " + U.tnameT(md.home) + " ضد " + U.tnameT(md.away) : T0;
  }
  function goalMoment(md, side) {
    var tm = md[side], ev = (md.events || []).filter(function (e) { return /goal/.test(e.type) && e.team === side; }).pop(), who = ev && ev.player ? U.pnameT(ev.player) : "";
    say("هدف لـ" + U.tnameT(tm) + (who ? "، " + who : "") + ". " + U.tnameT(md.home) + " " + md.score.home + "، " + U.tnameT(md.away) + " " + md.score.away);
    whistle(); if (RM) return;
    var hdr = $(".hdr"); if (!hdr) return; hdr.style.setProperty("--gc", U.col(tm.id)); hdr.style.setProperty("--gci", U.ink(U.col(tm.id))); hdr.classList.remove("goal"); void hdr.offsetWidth; hdr.classList.add("goal");
    var g = D.createElement("div"); g.className = "gtext " + (side === "home" ? "fr" : "fl"); g.innerHTML = "<b>هدف</b><span>" + U.esc(who) + (who ? " · " : "") + U.tname(tm) + "</span>"; hdr.appendChild(g); setTimeout(function () { g.remove(); hdr.classList.remove("goal"); }, 2400);
  }
  // 360: the goal sound, off by default: a short synthesized whistle (no audio file); browsers start audio suspended, the first tap wakes it
  var AC = null;
  D.addEventListener("pointerdown", function () { if (!prefOn("goalsnd")) return; try { AC = AC || new (window.AudioContext || window.webkitAudioContext)(); if (AC.state === "suspended") AC.resume(); } catch (e) {} }, { once: true, passive: true });
  function whistle() { if (!prefOn("goalsnd")) return; try { AC = AC || new (window.AudioContext || window.webkitAudioContext)(); var t = AC.currentTime;
    [0, 0.32].forEach(function (d, i) { var o = AC.createOscillator(), g = AC.createGain(), lfo = AC.createOscillator(), lg = AC.createGain(); o.type = "sine"; o.frequency.value = i ? 2350 : 2150; lfo.frequency.value = 38; lg.gain.value = 90; lfo.connect(lg); lg.connect(o.frequency);
      g.gain.setValueAtTime(0, t + d); g.gain.linearRampToValueAtTime(0.18, t + d + 0.02); g.gain.setValueAtTime(0.18, t + d + (i ? 0.5 : 0.22)); g.gain.linearRampToValueAtTime(0, t + d + (i ? 0.56 : 0.26));
      o.connect(g); g.connect(AC.destination); o.start(t + d); lfo.start(t + d); o.stop(t + d + 0.6); lfo.stop(t + d + 0.6); }); } catch (e) {} }
  // 370: «لو خلصت الحين» while live: the league table with this score, the rows around both teams
  var ST0 = null;
  function liveTable(md) { var box = $("#ltable"); if (!box) return; if (!U.isLive(md) || !md.score) { box.innerHTML = ""; return; }
    (ST0 ? Promise.resolve(ST0) : get("comp/" + md.comp + "/standings.json").then(function (s) { ST0 = s; return s; })).then(function (st) {
      var g = st && !st.composite && (st.groups || []).filter(function (g) { return (g.rows || []).some(function (r) { return r.team.id === md.home.id; }) && g.rows.some(function (r) { return r.team.id === md.away.id; }); })[0]; if (!g) return;
      var rows = JSON.parse(JSON.stringify(g.rows)), H2 = md.score.home, A2 = md.score.away; rows.forEach(function (r) { var me = r.team.id === md.home.id ? [H2, A2] : r.team.id === md.away.id ? [A2, H2] : null; if (!me) return; r.played++; r.gf += me[0]; r.ga += me[1]; r.gd = r.gf - r.ga; r.pts += me[0] > me[1] ? 3 : me[0] === me[1] ? 1 : 0; r.live = 1; });
      rows.sort(function (a, b) { return b.pts - a.pts || b.gd - a.gd || b.gf - a.gf || a.rank - b.rank; }); rows.forEach(function (r, i) { r.rank = i + 1; });
      var ix = rows.map(function (r, i) { return r.live ? i : -1; }).filter(function (i) { return i >= 0; }), lo = Math.max(0, Math.min.apply(null, ix) - 1), hi = Math.min(rows.length, Math.max.apply(null, ix) + 2), hl = {}; hl[md.home.id] = hl[md.away.id] = 1;
      box.innerHTML = U.grp("لو خلصت الحين", U.table(rows.slice(lo, hi), { hl: hl }), { foot: "الترتيب لو انتهت المباراة بهالنتيجة." }); }).catch(function () {}); }
  // «منو بيفوز؟»: the pick stays on this phone (tifo.picks: {mid: {p, ko, h, a, r}}); closed at kickoff, settled when the result is in
  function pickInit() { var pk = $("#pick"); if (!pk) return; var s = ls.json("tifo.picks", {})[pk.dataset.mid]; if (s && s.p) { selectSegOnly($(".seg", pk), s.p); pickMsg(s); }
    var ko = Date.parse(pk.dataset.kick); if (ko && ko <= NOW()) { var g = pk.closest(".grp"); if (g) g.hidden = true; } else if (ko) setTimeout(function () { var g = pk.closest(".grp"); if (g) g.hidden = true; }, Math.min(ko - NOW(), 2147483000)); }
  function pickMsg(s) { var m = $("#pickm"); if (!m) return; var nm = s.p === "d" ? "تعادل" : ($('.seg[data-seg="pick"] button[data-t="' + s.p + '"] .sl') || {}).textContent || ""; m.textContent = "توقعك: " + nm + ". نشوف بعد النهاية."; }
  function pickSave(k) { var pk = $("#pick"); if (!pk) return; if (Date.parse(pk.dataset.kick) <= NOW()) return; var o = ls.json("tifo.picks", {}); o[pk.dataset.mid] = { p: k, ko: pk.dataset.kick, h: +pk.dataset.h, a: +pk.dataset.a }; ls.set("tifo.picks", JSON.stringify(o)); pickMsg(o[pk.dataset.mid]); toast("توقعك انحفظ في جوالك"); }
  function pickSettle(md) { if (!md || md.status !== "finished" || !md.score) return; var o = ls.json("tifo.picks", {}), p = o[md.id]; if (!p || p.r != null) { if (p && p.r != null) pickShow(p); return; }
    var r = md.score.home > md.score.away ? "h" : md.score.home < md.score.away ? "a" : "d"; p.r = p.p === r ? 1 : 0; o[md.id] = p; ls.set("tifo.picks", JSON.stringify(o)); pickShow(p); }
  function pickShow(p) { if ($(".pickres")) return; var h = $(".hdr"); if (!h) return; var n = D.createElement("p"); n.className = "pickres" + (p.r ? " ok" : ""); n.textContent = p.r ? "توقعك طلع صح" : "توقعك طلع غلط"; h.appendChild(n); }
  // where to watch in the visitor's country (the build shows the UAE's); a paid channel is marked «مشفرة», never «مجاني»
  function loadBC() { if (BC || !B.dataset.bc) return Promise.resolve(BC); return getx("/assets/bc." + B.dataset.bc + ".json").then(function (j) { BC = j; return j; }).catch(function () { return null; }); }
  function chBox() { var box = $("#chbox"); if (!box) return; var cc = country() || "AE"; if (cc === "AE" || cc === "xx") { var h0 = $("#chcc"); if (h0) h0.textContent = ""; return; }
    loadBC().then(function (bc) { if (!bc) return; var e = (bc[cc] || {})[box.dataset.comp], h = $("#chcc"); if (h) h.textContent = "في " + ccName(cc);
      box.innerHTML = e && e.b && e.b.length ? e.b.slice(0, 4).map(function (x) { return '<div class="row"><span class="rt">' + U.esc(x[0]) + (x[5] ? "<small>" + U.esc(x[5]) + "</small>" : "") + "</span>" + (x[1] ? "" : '<span class="chip enc">مشفرة</span>') + "</div>"; }).join("") : '<div class="row"><span class="rt muted">ما عندنا القناة في ' + U.esc(ccName(cc) || "بلدك") + "</span></div>"; }); }
  // W3.5: the prayer that falls during the match, in the visitor's city («العشاء في الرياض 19:52 · حوالي الدقيقة 20»)
  var CITY = { AE: [["أبوظبي", 24.4539, 54.3773], ["دبي", 25.2048, 55.2708], ["العين", 24.2075, 55.7447]], SA: [["الرياض", 24.7136, 46.6753], ["جدة", 21.4858, 39.1925], ["مكة", 21.3891, 39.8579], ["الدمام", 26.4207, 50.0888]], EG: [["القاهرة", 30.0444, 31.2357], ["الإسكندرية", 31.2001, 29.9187]],
    MA: [["الرباط", 34.0209, -6.8416], ["الدار البيضاء", 33.5731, -7.5898]], DZ: [["الجزائر", 36.7538, 3.0588], ["وهران", 35.6971, -0.6308]], TN: [["تونس", 36.8065, 10.1815]], IQ: [["بغداد", 33.3152, 44.3661], ["البصرة", 30.5085, 47.7804]],
    JO: [["عمّان", 31.9454, 35.9284]], KW: [["الكويت", 29.3759, 47.9774]], QA: [["الدوحة", 25.2854, 51.531]], BH: [["المنامة", 26.2285, 50.586]], OM: [["مسقط", 23.588, 58.3829]], LB: [["بيروت", 33.8938, 35.5018]], SY: [["دمشق", 33.5138, 36.2765]], PS: [["القدس", 31.7683, 35.2137]],
    YE: [["صنعاء", 15.3694, 44.191]], LY: [["طرابلس", 32.8872, 13.1913]], SD: [["الخرطوم", 15.5007, 32.5599]], MR: [["نواكشوط", 18.0735, -15.9582]], SO: [["مقديشو", 2.0469, 45.3182]], DJ: [["جيبوتي", 11.5721, 43.1456]], KM: [["موروني", -11.7172, 43.2473]] };
  var METH = { AE: [18.2, 18.2], SA: [18.5, "90"], QA: [18, "90"], KW: [18, 17.5], BH: [18.5, 18], OM: [18, 18], EG: [19.5, 17.5], MA: [19, 17], DZ: [18, 17], TN: [18, 18], JO: [18, 18] };
  function prayerTimes(lat, lon, ymd, tzName) { var d2r = Math.PI / 180, p = ymd.split("-").map(Number), jd = Date.UTC(p[0], p[1] - 1, p[2], 12) / 864e5 + 2440587.5, Dd = jd - 2451545;
    var fa = function (a) { return a - 360 * Math.floor(a / 360); }, g = fa(357.529 + 0.98560028 * Dd) * d2r, q = fa(280.459 + 0.98564736 * Dd), Lm = fa(q + 1.915 * Math.sin(g) + 0.02 * Math.sin(2 * g)) * d2r, e = (23.439 - 0.00000036 * Dd) * d2r;
    var RA = Math.atan2(Math.cos(e) * Math.sin(Lm), Math.cos(Lm)) / d2r / 15, dec = Math.asin(Math.sin(e) * Math.sin(Lm)), fx = function (h) { return h - 24 * Math.floor(h / 24); }, EqT = q / 15 - fx(RA);
    if (EqT > 12) EqT -= 24; else if (EqT < -12) EqT += 24;
    var off = (function () { var t = new Date(Date.UTC(p[0], p[1] - 1, p[2], 12)); var s = t.toLocaleString("en-US", { timeZone: tzName, hour12: false, hour: "2-digit", minute: "2-digit" }).split(":"); return ((+s[0] % 24) * 60 + +s[1] - 12 * 60) / 60; })();
    var noon = 12 + off - lon / 15 - EqT, la = lat * d2r, T = function (a) { return Math.acos((-Math.sin(a * d2r) - Math.sin(dec) * Math.sin(la)) / (Math.cos(dec) * Math.cos(la))) / d2r / 15; };
    var asrA = Math.atan(1 / (1 + Math.tan(Math.abs(la - dec)))), asr = noon + Math.acos((Math.sin(asrA) - Math.sin(dec) * Math.sin(la)) / (Math.cos(dec) * Math.cos(la))) / d2r / 15;
    return { off: off, t: { fajr: noon - T(18), dhuhr: noon + 0.05, asr: asr, maghrib: noon + T(0.833), isha: noon + T(17) }, noon: noon, T: T }; }
  function prayer() { var slot = $("#prayl"); if (!slot || !MD || !MD.kickoff_utc || MD.time_tbd || !(MD.status === "scheduled" || U.isLive(MD))) return;
    var cc = country(); if (!cc || cc === "xx") cc = "AE"; var row = CTRY[cc], list = CITY[cc]; if (!row || !list) return; var ci = list.filter(function (c) { return c[0] === ls.get("tifo.city", ""); })[0] || list[0];
    var ko = Date.parse(MD.kickoff_utc), ymd = new Date(ko).toLocaleDateString("en-CA", { timeZone: row[2] }), Pt = prayerTimes(ci[1], ci[2], ymd, row[2]), me = METH[cc] || [18, 17], t = Pt.t;
    t.fajr = Pt.noon - Pt.T(me[0]); t.isha = me[1] === "90" ? t.maghrib + 1.5 : Pt.noon + Pt.T(me[1]); if (cc === "AE") { t.asr += 2 / 60; t.maghrib += 4 / 60; t.isha += 1 / 60; }
    var AR = { fajr: "الفجر", dhuhr: "الظهر", asr: "العصر", maghrib: "المغرب", isha: "العشاء" }, base = Date.UTC.apply(null, ymd.split("-").map(function (v, i) { return i === 1 ? +v - 1 : +v; }));
    for (var k in t) { var at = base + (t[k] - Pt.off) * 36e5, mn = (at - ko) / 6e4; if (mn >= -5 && mn <= 115) { var hh = new Date(at + 30e3).toLocaleTimeString("en-GB", { timeZone: row[2], hour: "2-digit", minute: "2-digit", hour12: false });
      slot.textContent = AR[k] + " في " + ci[0] + " " + hh + " · " + (mn < 0 ? "قبل البداية" : mn < 48 ? "حوالي الدقيقة " + Math.max(1, Math.round(mn)) : mn < 63 ? "بين الشوطين" : "حوالي الدقيقة " + Math.min(90, Math.round(45 + mn - 63))); return; } }
    slot.textContent = ""; }
  function rememberOpened() { if (!V.id || !V.ko) return; var o = ls.json("tifo.opened", []).filter(function (x) { return x.id !== V.id && NOW() - Date.parse(x.ko) < 864e5; }); o.unshift({ id: V.id, ko: V.ko }); ls.set("tifo.opened", JSON.stringify(o.slice(0, 8))); }

  // ================================================================== team, competition, player
  function teamInit() {
    if (!$("#tfx")) return; var ids = {}; $$("#tfeat [data-mid], #tfx [data-mid]").forEach(function (a) { ids[a.dataset.mid] = 1; }); var age = V.built ? NOW() - Date.parse(V.built) : 0;
    cdAttachTeam();
    get("live.json", true).then(function (l) { var Lm = {}, hit = false; (l.matches || []).forEach(function (m) { Lm[m.id] = m; if (ids[m.id]) hit = true; });
      if (!hit && age < 30 * 60e3) { D.documentElement.classList.remove("stale"); return; }
      return get("team/" + V.id + ".json", true).then(function (t) { cfg.now = NOW(); t.fixtures = (t.fixtures || []).map(function (m) { return m && Lm[m.id] ? Object.assign({}, m, Lm[m.id]) : m; }); TF = t; var tf = P.teamFx(t); $("#tfeat").innerHTML = tf.feat; $("#tfx").innerHTML = tf.fx; localize(); cdAttachTeam(); stamp(t.generated); }); }).catch(function () {});
    var ics = $("#ics"); if (ics && /Android/i.test(navigator.userAgent)) { ics.href = "https://calendar.google.com/calendar/r?cid=" + encodeURIComponent("webcal://" + location.host + "/v1/team/" + V.id + ".ics"); ics.target = "_blank"; ics.rel = "noopener"; } else if (ics) ics.href = "webcal://" + location.host + "/v1/team/" + V.id + ".ics";
    pushInit();
  }
  function cdAttachTeam() { var a = $("#tfeat .fc[data-mid]"); if (!a || $(".fc-cd", a)) return; var t = D.querySelector("#tfeat time[data-u]"), sc = $(".sc.ko", a); if (!t || !sc) return; var ko = t.dataset.u, d = Date.parse(ko) - NOW(); if (!(d > 0 && d < 4 * 864e5)) return;
    var el = D.createElement("div"); el.className = "fc-cd"; el.dataset.cdko = ko; el.innerHTML = "تبدا بعد " + cdText(d); a.appendChild(el); }
  function compInit() {
    var age = V.built ? NOW() - Date.parse(V.built) : 0; if (age < 30 * 60e3 || !V.comp) { D.documentElement.classList.remove("stale"); return; } var box = $("#ctab");
    if (box) get("comp/" + V.comp + "/standings.json", true).then(function (st) { var b = $('.seg[data-seg="tv"] button[aria-selected="true"]'); box.innerHTML = P.compTable(st, box.dataset.single === "1", b && b.dataset.t); localize(box); stamp(st.generated); }).catch(function () {});
    var rl = $("#roundlist"); if (rl) get("comp/" + V.comp + "/fixtures.json", true).then(function (j) { FX = U.rounds(j); var b = $("#rounds button[aria-selected=true]"), k = b ? b.dataset.r : FX.cur; rl.innerHTML = U.roundMatches(FX.by[k] || []); localize(rl); }).catch(function () {});
  }
  var FX = null;
  function selectRound(b) { $$("#rounds button").forEach(function (x) { x.setAttribute("aria-selected", String(x === b)); }); b.scrollIntoView({ inline: "center", block: "nearest", behavior: RM ? "auto" : "smooth" });
    var box = $("#roundlist"), rs = $("#rounds"), cid = rs.dataset.comp, key = rs.dataset.key, r = b.dataset.r; box.classList.add("dim");
    var lk = $("#rdlink"); if (lk && key) { if (/^\d+$/.test(r)) { lk.href = "/c/" + key + "/r/" + r + "/"; var tt = $(".rt", lk); if (tt) tt.firstChild.textContent = "صفحة الجولة " + r; lk.hidden = false; } else lk.hidden = true; }
    (FX ? Promise.resolve(FX) : get("comp/" + cid + "/fixtures.json").then(function (j) { FX = U.rounds(j); return FX; })).then(function (R) { box.innerHTML = U.roundMatches(R.by[r] || []); box.classList.remove("dim"); localize(box); }).catch(function () { box.classList.remove("dim"); }); }
  // a player's career and match log load from his own files the first time their segment opens (or now, when the page opens on it)
  function playerMounts(root) {
    var pc = $("#pcar1", root); if (pc && !pc.dataset.done) { pc.dataset.done = 1; Promise.all([V.prof ? get("player/" + V.id + "/profile.json").catch(function () { return null; }) : null, V.tm ? get("player/" + V.id + "/tm.json").catch(function () { return null; }) : null]).then(function (r) {
      var h = P.playerCareer({ prof: r[0], tm: r[1] }); pc.innerHTML = h || (!$("#pcar .grp") ? '<div class="card">' + U.empty("ما عندنا مسيرته للحين.") + "</div>" : ""); localize(pc); }); }
    var pl = $("#plg", root); if (pl && !pl.dataset.done) { pl.dataset.done = 1; get("player/" + V.id + "/log.json").then(function (lg) { var h = P.playerGames(lg); pl.innerHTML = h || '<div class="card">' + U.empty("ما عندنا مبارياته للحين.") + "</div>"; if (lg && !$(".tiles")) tilesFromLog(lg); }).catch(function () { pl.innerHTML = '<div class="card">' + U.empty("ما عندنا مبارياته للحين.") + "</div>"; }); }
  }
  function tilesFromLog(lg) { var s = lg.seasons && lg.seasons[0]; if (!s) return; var at = $(".segbar"); if (!at) return; var sec = D.createElement("section"); sec.className = "grp";
    sec.innerHTML = '<div class="gh"><h2>آخر موسم</h2><span class="num">' + U.esc(s.season) + '</span></div><div class="tiles">' + [[s.g, "أهداف"], [s.a, "صناعة"], [s.apps, "مباراة"], [s.rn ? (s.rs / s.rn).toFixed(1) : "—", "التقييم"]].map(function (x) { return '<div class="tile"><b>' + x[0] + "</b><span>" + x[1] + "</span></div>"; }).join("") + "</div>"; at.parentNode.insertBefore(sec, at); }

  // ================================================================== news, فريقي, search, the encyclopedia
  function lazyNews(root) { $$(".enews[data-e]", root).forEach(function (box) { if (box.dataset.done) return; box.dataset.done = 1;
    Promise.all([get("news/e/" + box.dataset.e + ".json").catch(function () { return { stories: [] }; }), box.dataset.social ? get("news/social/" + box.dataset.social + ".json").catch(function () { return { videos: [] }; }) : Promise.resolve({ videos: [] })]).then(function (r) {
      var st = (r[0].stories || []).slice(0, 20), vs = (r[1].videos || []).slice(0, 12);
      box.innerHTML = st.length || vs.length ? (st.length ? '<div class="card sepd">' + st.map(U.newsCard).join("") + "</div>" : "") + (vs.length ? '<div class="gh mt2"><h2>من حساباته الرسمية</h2></div>' + U.vids(vs) : "") : '<div class="card"><p class="empty">ما في أخبار عنه هالأيام. <a style="color:var(--accent)" href="/news/">كل الأخبار</a></p></div>'; localize(box); }); }); }
  var NEWS = null, NK = "all", NSHOW = 30;
  function newsFilter(k, more) { if (k !== NK) NSHOW = 30; NK = k; if (more) NSHOW += 30; var box = $("#nlist"); if (!box || !NEWS) return;
    var xs = NEWS.filter(function (s) { return k === "all" || s.kind === k || (k === "statement" && (s.kind === "presser" || s.kind === "official")); });
    box.innerHTML = P.newsList(xs.slice(0, NSHOW), "all") + (xs.length > NSHOW ? '<div class="card mt">' + U.row({ btn: 1, t: "أخبار أقدم", cls: "link", attrs: " data-nmore" }) + "</div>" : ""); localize(box); }
  D.addEventListener("click", function (e) { if (e.target.closest && e.target.closest("[data-nmore]")) newsFilter(NK, true); });
  function newsInit() {
    get("news/latest.json", true).then(function (d) { NEWS = d.stories || []; var box = $("#nlist"), first = box && box.querySelector(".nw h3 a"); if (NK === "all" && first && NEWS[0] && first.textContent === NEWS[0].title && +box.dataset.n === NEWS.length) { if (NEWS.length > NSHOW) box.insertAdjacentHTML("beforeend", '<div class="card mt">' + U.row({ btn: 1, t: "أخبار أقدم", cls: "link", attrs: " data-nmore" }) + "</div>"); return; } newsFilter(NK); stamp(d.generated); }).catch(function () {});
    get("news/social.json").then(function (d) { var vs = (d.videos || []).slice(0, 12); if (vs.length) { $("#nsocb").innerHTML = U.vids(vs); $("#nsoc").hidden = false; } }).catch(function () {});
    var mine = teamIds().slice(0, 3); if (mine.length) Promise.all(mine.map(function (id) { return get("news/e/team-" + id + ".json").catch(function () { return { stories: [] }; }); })).then(function (rs) { var st = []; rs.forEach(function (r) { st = st.concat((r.stories || []).slice(0, 3)); }); if (st.length) { var s = $("#mynews"); s.innerHTML = '<div class="gh"><h2>أخبار فريقك</h2></div><div class="card sepd">' + st.slice(0, 5).map(U.newsCard).join("") + "</div>"; s.hidden = false; localize(s); } });
  }
  var LIVEO = null; function liveMap() { return LIVEO || (LIVEO = get("live.json", true).then(function (l) { var o = {}; (l.matches || []).forEach(function (m) { o[m.id] = m; }); return o; }).catch(function () { return {}; })); }
  function mineRender() {
    var box = $("#minebox"); if (!box) return; var F = favs().filter(function (x) { return x.t === "team"; }), CF = favs().filter(function (x) { return x.t === "comp"; });
    if (!F.length && !CF.length) return;
    box.innerHTML = F.map(function (x) { return '<section class="grp" data-tn="' + x.id + '"><a class="card hd-row" href="/t/' + x.id + '/">' + U.crest({ id: x.id }, "md") + '<span class="rt"><span>' + U.esc(x.n || cfg.tn[x.id] || "") + "</span></span>" + U.chev + "</a></section>"; }).join("") +
      (CF.length ? U.grp("بطولاتك", CF.map(function (x) { return '<a class="row ins" href="' + U.link("c", x.id) + '">' + U.lg(x.id) + '<span class="rt">' + U.esc(x.n || "") + "</span>" + U.chev + "</a>"; }).join("")) : "") +
      U.grp("", U.row({ btn: 1, t: "أضف فريق", attrs: ' data-sheet="sh-pick"', cls: "link" }), { cls: "mt2" });
    var fix = function (m, Lm) { return m && Lm[m.id] ? Object.assign({}, m, Lm[m.id]) : m; };
    var verify = function (m, Lm) { if (!m || Lm[m.id] || !(U.isLive(m) || (m.status === "scheduled" && Date.parse(m.kickoff_utc) < NOW()))) return Promise.resolve(m); return get("match/" + m.id + ".json", true).then(function (d) { return Object.assign({}, m, { status: d.status, score: d.score, minute: d.minute, period: d.period, period_start: d.period_start, period_base: d.period_base, penalties: d.penalties }); }).catch(function () { return m; }); };
    F.forEach(function (x) { Promise.all([tnGet(x.id), liveMap()]).then(function (r) { var t = r[0], Lm = r[1]; if (!t) throw 0; t.next = fix(t.next, Lm); t.last = fix(t.last, Lm);
      return Promise.all([verify(t.next, Lm), verify(t.last, Lm)]).then(function (v) { t.next = v[0]; t.last = v[1]; if (t.next && t.next.status === "finished") { t.last = t.next; t.next = null; } return t; }); }).then(function (t) { var sec = $('[data-tn="' + x.id + '"]', box); if (!sec) return;
      var head = '<a class="hd-row" href="/t/' + x.id + '/">' + U.crest({ id: x.id }, "md") + '<span class="rt"><span>' + U.esc(t.name_ar || x.n || "") + "</span>" + (t.table ? "<small>" + U.esc(t.table.comp_ar) + " · المركز " + t.table.rank + "</small>" : "") + "</span>" + U.chev + "</a>";
      var rows = [t.next && U.mrow(t.next, { date: 1 }), t.last && U.mrow(t.last, { date: 1, team: x.id })].filter(Boolean).join("");
      sec.innerHTML = '<div class="card">' + head + rows + U.row({ href: "/t/" + x.id + "/#nw", icon: "news", c: "#0A84FF", t: "أخباره" }) + U.row({ btn: 1, icon: "bell", c: "#FF3B30", t: "نبّهني بمبارياته", attrs: ' data-go="/t/' + x.id + '/?notify=1"' }) + "</div>"; localize(sec); }).catch(function () {}); });
  }
  D.addEventListener("click", function (e) { var g = e.target.closest && e.target.closest("[data-go]"); if (g && /^\//.test(g.dataset.go)) { location.href = g.dataset.go; } });
  function pickFilter() { var q = $("#pickq"); if (!q) return; q.addEventListener("input", function () { var s = fold(q.value); $$("#sh-pick [data-pick]").forEach(function (b) { b.hidden = s && fold(b.dataset.n || "").indexOf(s) < 0; }); }); }
  function fold(s) { return String(s || "").toLowerCase().replace(/[أإآٱا]/g, "ا").replace(/ة/g, "ه").replace(/ى/g, "ي").replace(/[ً-ْـ]/g, "").normalize("NFD").replace(/[̀-ͯ]/g, "").trim(); }
  // search: the site's index (assets/search.<v>.json), loaded on first focus; matches, teams, players, competitions, coaches, referees, pages
  var SIDX = null;
  function sidx() { if (SIDX) return Promise.resolve(SIDX); var v = B.dataset.sv;   /* the index's version: on <body> before 2026-10-07, in /search-v.json since */
    return (v && !/^_/.test(v) ? Promise.resolve(v) : getx("/search-v.json").then(function (j) { if (!j || !j.v) throw 0; return j.v; })).then(function (v) { return getx("/assets/search." + v + ".json"); }).then(function (j) { var S = j.s || []; SIDX = (j.i || []).map(function (i) { return { t: i[0], ar: i[1], la: i[2], u: i[3], sub: (typeof i[4] === "number" ? S[i[4]] : i[4]) || "", cc: i[5] || "", ko: i[6] || "", k: fold(i[1]) + " " + fold(i[2]) }; }); return SIDX; }); }
  function searchInit() {
    var q = $("#q"), x = $("#qx"), out = $("#sres"), idleBox = $("#sidle"); if (!q) return;
    var TY = { c: "البطولات", t: "الفرق والمنتخبات", p: "اللاعبين", m: "المباريات", k: "المدربين", f: "الحكام", r: "الصفحات" }, ORD = ["t", "c", "m", "p", "k", "r", "f"], CC = country();
    var recent = function () { return ls.json("tifo.sq", []); }, remember = function (v) { v = String(v || "").trim(); if (v.length < 2) return; var r = recent().filter(function (y) { return y !== v; }); r.unshift(v); ls.set("tifo.sq", JSON.stringify(r.slice(0, 6))); };
    var paintRecent = function () { var r = recent(), sec = $("#recent"); if (!sec) return; sec.hidden = !r.length; $("#recentl").innerHTML = r.map(function (v) { return '<button type="button" class="row" data-q="' + U.esc(v) + '">' + U.icon("hist", "rh", 1.8) + '<span class="rt">' + U.esc(v) + "</span>" + U.chev + "</button>"; }).join(""); };
    paintRecent();
    var run = function () { var v = fold(q.value); x.hidden = !q.value; if (v.length < 2) { out.innerHTML = ""; idleBox.hidden = false; return; } idleBox.hidden = true; if (!SIDX) { out.innerHTML = '<div class="card"><p class="empty">نحمّل…</p></div>'; sidx().then(run, function () { out.innerHTML = '<div class="card"><p class="empty">ما قدرنا نحمّل البحث، تأكد من النت.</p></div>'; }); return; }
      var toks = v.split(/\s+/).filter(function (w) { return w.length >= 2; }), now = NOW();
      var hits = SIDX.filter(function (i) { return (i.k.indexOf(v) >= 0 || (toks.length > 1 && toks.every(function (w) { return i.k.indexOf(w) >= 0; }))) && (i.t !== "m" || !i.ko || Date.parse(i.ko) > now - 3 * 36e5); }), by = {}; hits.forEach(function (i) { (by[i.t] = by[i.t] || []).push(i); });
      var starts = function (i) { return (fold(i.ar).indexOf(v) === 0 || fold(i.la).indexOf(v) === 0) ? 0 : 1; };
      out.innerHTML = ORD.filter(function (t) { return by[t]; }).map(function (t) { var list = by[t].sort(function (a, b) { return starts(a) - starts(b) || (a.cc === CC ? 0 : 1) - (b.cc === CC ? 0 : 1) || (t === "m" ? Date.parse(a.ko) - Date.parse(b.ko) : 0); }).slice(0, t === "p" ? 12 : 8); return U.grp(TY[t] + ' <span class="num">' + by[t].length + "</span>", list.map(function (i) { var img = i.t === "t" ? U.crest({ id: +((/\/(\d+)\/?$/.exec(i.u) || [])[1]) }, "md").replace('class="cr md"', 'class="lg"') : "";
        var sub = i.t === "m" && i.ko ? (i.sub ? i.sub + " · " : "") + U.timeText(i.ko, "dt") : i.sub; return '<a class="row' + (img ? " ins" : "") + '" href="' + U.esc(i.u) + '" data-rem>' + img + '<span class="rt">' + U.esc(i.ar || i.la) + (sub || (i.la && i.ar !== i.la) ? "<small>" + U.esc([sub, i.ar && i.la !== i.ar ? i.la : ""].filter(Boolean).join(" · ")) + "</small>" : "") + "</span>" + U.chev + "</a>"; }).join("")); }).join("") || '<div class="card"><p class="empty">ما لقينا شي باسم «' + U.esc(q.value) + "».</p></div>"; };
    q.addEventListener("focus", function () { sidx().catch(function () {}); }, { once: true }); q.addEventListener("input", run);
    q.form && q.form.addEventListener("submit", function (e) { e.preventDefault(); var a = $("#sres a"); if (a) location.href = a.href; });
    q.addEventListener("keydown", function (e) { if (e.key === "Enter") { var a = $("#sres a"); if (a) { remember(q.value); location.href = a.href; } } });
    x.addEventListener("click", function () { q.value = ""; run(); q.focus(); });
    out.addEventListener("click", function (e) { if (e.target.closest("[data-rem]")) remember(q.value); });
    D.addEventListener("click", function (e) { var r = e.target.closest && e.target.closest("[data-q]"); if (r) { q.value = r.dataset.q; run(); } var c = e.target.closest && e.target.closest("#rclr"); if (c) { ls.set("tifo.sq", "[]"); paintRecent(); } });
    var qs = new URLSearchParams(location.search).get("q"); if (qs) { q.value = qs; run(); } else if (matchMedia("(hover:hover)").matches) q.focus();
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition; if (SR) { var mic = D.createElement("button"); mic.type = "button"; mic.className = "clr mic"; mic.setAttribute("aria-label", "دوّر بصوتك"); mic.innerHTML = U.icon("mic", "", 2); mic.onclick = function () { var r = new SR(); r.lang = "ar-AE"; r.onresult = function (ev) { q.value = ev.results[0][0].transcript; run(); }; r.start(); }; q.parentNode.appendChild(mic); }
  }
  var WD = null;
  function dbLoad() { return WD ? Promise.resolve(WD) : Promise.all([get("world/index.json"), get("world/leagues.json"), get("s365/index.json").catch(function () { return null; })]).then(function (x) { WD = { I: x[0], L: x[1].leagues, S: x[2], players: null }; return WD; }); }
  function dbInit() {
    var q = $("#wq"), out = $("#wr"), idleBox = $("#widle"), x = $("#wqx"); if (!q) return;
    var run = function () { var v = fold(q.value); x.hidden = !q.value; if (v.length < 2) { out.innerHTML = ""; idleBox.hidden = false; return; } idleBox.hidden = true;
      if (!WD || !WD.players) { out.innerHTML = '<div class="card"><p class="empty">نحمّل الموسوعة…</p></div>'; dbLoad().then(function () { return WD.players ? null : get("world/players.json").then(function (P2) { WD.players = (P2.players || []).map(function (p) { return { t: "p", id: p[0], ar: p[1], en: p[2], club: p[3], k: fold(p[1]) + " " + fold(p[2]) }; }).concat((WD.S ? WD.S.players : []).map(function (p) { return { t: "a", id: p[0], ar: p[1], en: p[2], club: p[3], k: fold(p[1]) + " " + fold(p[2]) }; })); }); }).then(run).catch(function () { out.innerHTML = '<div class="card"><p class="empty">ما قدرنا نحمّل الموسوعة.</p></div>'; }); return; }
      if (!WD.clubs) { WD.clubs = WD.I.clubs.map(function (c) { return { t: "c", id: c[0], ar: c[1], en: c[2], k: fold(c[1]) + " " + fold(c[2]) }; }).concat(WD.S ? WD.S.teams.filter(function (t) { return !t[4]; }).map(function (t) { return { t: "s", id: t[0], ar: t[1], en: t[2], k: fold(t[1]) + " " + fold(t[2]) }; }) : []); WD.cname = {}; WD.I.clubs.forEach(function (c) { WD.cname[c[0]] = c[1]; }); WD.sname = {}; if (WD.S) WD.S.teams.forEach(function (t) { WD.sname[t[0]] = t[1]; }); }
      var hc = WD.clubs.filter(function (c) { return c.k.indexOf(v) >= 0; }).slice(0, 20), hp = WD.players.filter(function (p) { return p.k.indexOf(v) >= 0; }).slice(0, 30);
      out.innerHTML = (hc.length ? U.grp("أندية", hc.map(function (c) { return '<a class="row' + (c.t === "c" ? " ins" : "") + '" href="' + (c.t === "c" ? "/db/club/?id=" + c.id : "/db/team/?id=" + c.id) + '">' + (c.t === "c" ? U.crest({ id: c.id }, "md").replace('class="cr md"', 'class="lg"') : "") + '<span class="rt">' + U.esc(c.ar) + '<small class="lat">' + U.esc(c.en || "") + "</small></span>" + U.chev + "</a>"; }).join("")) : "") +
        (hp.length ? U.grp("لاعبين", hp.map(function (p) { return '<a class="row" href="' + (p.t === "p" ? "/db/player/?id=" + p.id : "/db/athlete/?id=" + p.id) + '"><span class="rt">' + U.esc(p.ar) + "<small>" + U.esc((p.t === "a" ? WD.sname : WD.cname)[p.club] || "") + "</small></span>" + U.chev + "</a>"; }).join("")) : "") || '<div class="card"><p class="empty">ما لقينا شي.</p></div>'; };
    q.addEventListener("input", run); q.addEventListener("focus", function () { dbLoad().catch(function () {}); }, { once: true }); x.addEventListener("click", function () { q.value = ""; run(); });
    if (location.hash === "#champs") { var d = $("#champs details"); if (d) d.open = true; }
  }
  function dbClubs() { var box = $("#wclubs"); if (!box || box.dataset.done) return; box.dataset.done = 1; dbLoad().then(function () { var cname = {}; WD.I.clubs.forEach(function (c) { cname[c[0]] = c[1]; }); var by = {}; WD.L.forEach(function (l) { (by[l.cc] = by[l.cc] || { n: l.country_ar || l.cc, ls: [] }).ls.push(l); });
    box.innerHTML = '<div class="card cardlist">' + Object.keys(by).sort(function (a, b) { return by[a].n.localeCompare(by[b].n, "ar"); }).map(function (cc) { var c = by[cc]; return '<details class="dz"><summary class="row"><span class="rt">' + U.esc(c.n) + '</span><span class="rv num">' + c.ls.reduce(function (a, l) { return a + l.clubs.length; }, 0) + "</span>" + U.chev + "</summary>" + c.ls.map(function (l) { return '<div class="gh" style="padding-top:10px">' + U.esc(l.name_ar || l.name) + '</div><div class="sepd">' + l.clubs.map(function (k) { return '<a class="row" href="/db/club/?id=' + k + '">' + U.crest({ id: k }, "md").replace('class="cr md"', 'class="lg"') + '<span class="rt">' + U.esc(cname[k] || k) + "</span>" + U.chev + "</a>"; }).join("") + "</div>"; }).join("") + "</details>"; }).join("") + "</div>"; }).catch(function () { box.innerHTML = '<div class="card"><p class="empty">ما قدرنا نحمّل الأندية.</p></div>'; }); }

  // ================================================================== «جزيرة المباراة»: the live score of a followed team (or a match you opened) on top of every page
  // Small sources only (v1/live.json, ~2 KB, and v1/all/live.json for matches outside our competitions), polled every 25 s and only
  // while one of them is live; otherwise one look at load and one at the next kickoff we know. × hides it for that match; the
  // «جزيرة المباراة» switch in المزيد turns it off for good.
  var IS = { t: null, m: null, ids: null, seen: null };
  function islandCands() { var ids = {}; teamIds().forEach(function (id) { ids["t" + id] = 1; }); ls.json("tifo.opened", []).forEach(function (o) { if (NOW() - Date.parse(o.ko) < 4 * 36e5 && Date.parse(o.ko) - NOW() < 15 * 60e3) ids["m" + o.id] = 1; }); return ids; }
  function island() {
    var el = $("#island"); if (!el) return; clearTimeout(IS.t);
    if (!prefOn("island")) { el.hidden = true; B.classList.remove("island-on"); return; }
    var c = islandCands(); if (!Object.keys(c).length) { el.hidden = true; B.classList.remove("island-on"); return; }
    Promise.all([get("live.json", true).catch(function () { return { matches: [] }; }), teamIds().length ? get("all/live.json", true).catch(function () { return { matches: [] }; }) : { matches: [] }]).then(function (r) {
      var x = ls.json("tifo.island.x", {}), mine = teamIds(), list = [];
      (r[0].matches || []).forEach(function (m) { if (!U.isLive(m) || x[m.id]) return; var rank = mine.indexOf(m.home.id) >= 0 ? mine.indexOf(m.home.id) : mine.indexOf(m.away.id) >= 0 ? mine.indexOf(m.away.id) : c["m" + m.id] ? 50 : -1; if (rank >= 0) list.push([rank, m]); });
      (r[1].matches || []).forEach(function (w) { if (!(w.status === "live" || w.status === "ht") || x[w.id] || list.some(function (z) { return String(z[1].id) === String(w.id); })) return; var h = +w.home[0], a = +w.away[0], rank = mine.indexOf(h) >= 0 ? mine.indexOf(h) : mine.indexOf(a) >= 0 ? mine.indexOf(a) : c["m" + w.id] ? 50 : -1; if (rank < 0) return;
        list.push([rank + 0.5, { id: w.id, status: w.status, minute: w.minute, comp: w.lg, href: String(w.id).indexOf("365:") === 0 ? "/db/game/?id=" + String(w.id).slice(4) : "/live/?id=" + w.id, home: { id: h, name_ar: w.home[1], name: w.home[1], nocrest: true }, away: { id: a, name_ar: w.away[1], name: w.away[1], nocrest: true }, score: w.home[2] != null ? { home: w.home[2], away: w.away[2] } : null }]); });
      list.sort(function (a, b) { return a[0] - b[0]; });
      var m = list.length ? list[0][1] : null, here = PG === "match" && m && String(V.id) === String(m.id);
      if (!m || here) { el.hidden = true; B.classList.remove("island-on"); IS.m = null; if (m || list.length) IS.t = setTimeout(island, 25000); else islandLater(); return; }
      var prev = IS.m && String(IS.m.id) === String(m.id) ? IS.m : null, goal = prev && prev.score && m.score && (m.score.home > prev.score.home || m.score.away > prev.score.away); IS.m = m; cfg.now = NOW();
      el.href = m.href || "/m/" + m.id + "/"; el.dataset.mid = m.id; el.setAttribute("aria-label", "مباشر: " + U.tnameT(m.home) + " " + (m.score ? m.score.home + " - " + m.score.away : "") + " " + U.tnameT(m.away));
      el.innerHTML = '<span class="is-t">' + U.crest(m.home, "") + '<span class="is-n">' + U.esc(short(U.tnameT(m.home))) + "</span></span>" + '<span class="is-m">' + (m.score ? U.score(m.score, prefOn("nospoil") ? "hide" : "") : '<span class="sc">—</span>') + '<span class="st live"><i class="dot"></i>' + U.minute(m) + "</span></span>" + '<span class="is-t a"><span class="is-n">' + U.esc(short(U.tnameT(m.away))) + "</span>" + U.crest(m.away, "") + "</span>" + (list.length > 1 ? '<span class="is-more num">+' + (list.length - 1) + "</span>" : "") + '<button type="button" class="is-x" aria-label="سكّر الجزيرة لهالمباراة">' + U.icon("close", "", 2.6) + "</button>";
      el.hidden = false; B.classList.add("island-on");
      if (goal && !prefOn("nospoil")) { el.classList.remove("goal"); void el.offsetWidth; el.classList.add("goal"); var side = m.score.home > prev.score.home ? m.home : m.away; say("هدف لـ" + U.tnameT(side) + ". " + U.tnameT(m.home) + " " + m.score.home + "، " + U.tnameT(m.away) + " " + m.score.away); whistle(); setTimeout(function () { el.classList.remove("goal"); }, 3000); }
      IS.t = setTimeout(island, 25000);
    });
  }
  function short(n) { n = String(n || ""); return n.length > 12 ? n.split(" ")[0] : n; }
  // nothing live now: look again at the next kickoff of a followed team (from /tn/), at most twelve hours ahead
  function islandLater() { var ids = teamIds(); if (!ids.length) return; Promise.all(ids.slice(0, 6).map(tnGet)).then(function (ts) { var ko = ts.filter(function (t) { return t && t.next && t.next.kickoff_utc && !t.next.time_tbd; }).map(function (t) { return Date.parse(t.next.kickoff_utc); }).filter(function (t) { return t > NOW() - 3 * 36e5; }).sort()[0];
    if (!ko) return; var d = Math.max(60e3, ko - NOW() + 30e3); if (d < 12 * 36e5) IS.t = setTimeout(island, d); }); }
  D.addEventListener("click", function (e) { var x = e.target.closest && e.target.closest(".is-x"); if (!x) return; e.preventDefault(); e.stopPropagation(); var el = $("#island"), o = ls.json("tifo.island.x", {}); o[el.dataset.mid] = NOW(); Object.keys(o).forEach(function (k) { if (NOW() - o[k] > 864e5) delete o[k]; }); ls.set("tifo.island.x", JSON.stringify(o)); el.hidden = true; B.classList.remove("island-on"); toast("سكّرناها لهالمباراة. توقفها للأبد من «المزيد»"); }, true);
  D.addEventListener("visibilitychange", function () { if (!D.hidden && $("#island")) island(); });

  // ================================================================== the first visit: ten seconds to make اليوم yours (teams + country)
  function onbOpen(force) {
    var sh = $("#sh-onb"); if (!sh) { if (force) location.href = "/mine/"; return; }
    var grid = $("#onbpicks"), cc = $("#onbcc");
    var fill = function (picks) { if (!grid || grid.childElementCount || !picks) return; grid.innerHTML = P.picks(picks.slice(0, 30).map(function (p) { return { id: p[0], name_ar: p[1] }; })).replace(/^<div class="picks">|<\/div>$/g, ""); paintFav(); };
    if (grid && !grid.childElementCount) { if (C.picks) fill(C.picks); else getx("/picks.json").then(fill, function () {}); }   /* in the config before 2026-10-07 */
    if (cc && !cc.childElementCount) { var cur = country(); cc.innerHTML = (C.countries || []).map(function (c) { return '<button type="button" class="ccb" data-occ="' + c[0] + '" aria-pressed="' + (c[0] === cur) + '">' + U.esc(c[1]) + "</button>"; }).join(""); }
    paintFav(); openSheet(sh);
    var q = $("#onbq"), out = $("#onbr");
    if (q && !q._w) { q._w = 1; q.addEventListener("input", function () { var v = fold(q.value); if (v.length < 2) { out.innerHTML = ""; $("#onbpop").hidden = false; return; } $("#onbpop").hidden = true;
      sidx().then(function (I) { var hits = I.filter(function (i) { return i.t === "t" && i.k.indexOf(v) >= 0; }).slice(0, 18); out.innerHTML = hits.length ? P.picks(hits.map(function (i) { return { id: +((/\/t\/(\d+)\//.exec(i.u) || [])[1]), name_ar: i.ar || i.la }; }).filter(function (t) { return t.id; })) : '<p class="empty">ما لقينا فريق بهالاسم.</p>'; paintFav(); }, function () { out.innerHTML = '<p class="empty">ما قدرنا نحمّل البحث.</p>'; }); }); }
  }
  D.addEventListener("click", function (e) { var t = e.target.closest && e.target.closest("#sh-onb [data-occ], #onbok, #onbskip"); if (!t) return;
    if (t.dataset.occ) { ls.set("tifo.country", t.dataset.occ); $$("#onbcc [data-occ]").forEach(function (b) { b.setAttribute("aria-pressed", String(b === t)); }); applyTz(); fire("tifo:country", { cc: t.dataset.occ }); return; }
    ls.set("tifo.onb", t.id === "onbok" ? "done" : "skip"); closeSheet($("#sh-onb")); if (t.id === "onbok") { renderHome(); island(); offlineKeep(); toast(teamIds().length ? "تمام، «اليوم» صار لك" : "تقدر تختار فريقك أي وقت من «فريقي»"); } });
  function onbMaybe() { if (PG !== "home" || BOT || ls.get("tifo.onb", "") || teamIds().length || ss.get("tifo.onb.seen")) return; ss.set("tifo.onb.seen", "1"); setTimeout(function () { if (!SHEET) onbOpen(false); }, 1200); }

  // ================================================================== app-like navigation: prefetch on intent and in view (where speculation rules aren't), scroll
  var SPEC = !!(window.HTMLScriptElement && HTMLScriptElement.supports && HTMLScriptElement.supports("speculationrules")), PREF2 = {};
  function prefetch(href) { if (SPEC || !href || PREF2[href]) return; try { var u = new URL(href, location.href); if (u.origin !== location.origin || /^\/(v1|api|assets)\//.test(u.pathname) || u.pathname === location.pathname) return; } catch (e) { return; }
    var c = navigator.connection; if (c && (c.saveData || /2g/.test(c.effectiveType || ""))) return; PREF2[href] = 1; var l = D.createElement("link"); l.rel = "prefetch"; l.href = href; D.head.appendChild(l); }
  ["touchstart", "mouseover"].forEach(function (ev) { D.addEventListener(ev, function (e) { var a = e.target.closest && e.target.closest("a[href^='/']"); if (!a) return; if (ev === "mouseover") { var tm = setTimeout(function () { prefetch(a.href); }, 70); a.addEventListener("mouseleave", function () { clearTimeout(tm); }, { once: true }); } else prefetch(a.href); }, { passive: true, capture: true }); });
  // the likeliest next pages (the first live or featured match, the tab you're on): fetched when the browser is idle on a fast connection
  idle(function () { if (SPEC || !("IntersectionObserver" in window)) return; var n = 0, io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting && n < 4) { n++; prefetch(e.target.href); io.unobserve(e.target); } }); }); $$("main a.fc, main a.mr.is-live, main a.mr").slice(0, 8).forEach(function (a) { io.observe(a); }); });
  try { history.scrollRestoration = "auto"; } catch (e) {}

  // ================================================================== install (PWA) and offline copies
  var BIP = null, STANDALONE = (window.matchMedia && matchMedia("(display-mode: standalone)").matches) || navigator.standalone, IOS = /iPhone|iPad|iPod/.test(navigator.userAgent) && !window.MSStream;
  function instPaint() { var go = $("#instgo"), io = $("#instios"), dn = $("#instdone"), mm = $("#instm"); if (go) go.hidden = !BIP; if (io) io.hidden = !IOS || !!BIP || STANDALONE; if (dn) dn.hidden = !STANDALONE; if (mm) mm.hidden = !(BIP || IOS) || STANDALONE; }
  window.addEventListener("beforeinstallprompt", function (e) { e.preventDefault(); BIP = e; instPaint(); instAsk(); });
  window.addEventListener("appinstalled", function () { BIP = null; ls.set("tifo.inst.no", String(NOW())); instPaint(); var a = $("#instask"); if (a) a.remove(); toast("تيفو صار على شاشة جوالك"); });
  D.addEventListener("click", function (e) { var g = e.target.closest && e.target.closest("#instgo"); if (!g || !BIP) return; BIP.prompt(); (BIP.userChoice || Promise.resolve({})).then(function (c) { if (c.outcome === "accepted") ls.set("tifo.inst.no", String(NOW())); closeSheet($("#sh-install")); }); BIP = null; instPaint(); });
  // the ask: a quiet card above the tab bar, on a second visit only, once a session, never again for 30 days after «مب الحين»
  function instAsk() { if (STANDALONE || BOT || !(BIP || IOS) || $("#instask") || ss.get("tifo.inst.asked")) return; var ret = ls.get("tifo.ret", ""); if (!ret || ret === "first") return; if (NOW() - (+ls.get("tifo.inst.no", 0) || 0) < 30 * 864e5) return;
    setTimeout(function () { if (SHEET || $("#instask")) return; ss.set("tifo.inst.asked", "1"); var t = D.createElement("div"); t.id = "instask"; t.className = "instask"; t.setAttribute("role", "region"); t.setAttribute("aria-label", "ثبّت تيفو");
      t.innerHTML = '<img src="/icons/app-256.png" alt="" width="40" height="40"><span><b>ثبّت تيفو</b><small>يفتح مثل التطبيق، وصفحاتك تشتغل بدون نت</small></span><button type="button" class="pill pri" data-sheet="sh-install">ثبّت</button><button type="button" class="is-x" aria-label="مب الحين">' + U.icon("close", "", 2.6) + "</button>";
      t.querySelector(".is-x").onclick = function () { ls.set("tifo.inst.no", String(NOW())); t.remove(); }; t.querySelector(".pill").addEventListener("click", function () { t.remove(); }); B.appendChild(t); }, 12000); }
  // the service worker (src/sw.js): pages you opened keep working with a weak signal; the followed teams' cards and tables are fetched
  // when the phone is idle so the offline page can show them
  if ("serviceWorker" in navigator && !BOT) try { navigator.serviceWorker.register("/sw.js"); } catch (e) {}
  function offlineKeep() { if (!("serviceWorker" in navigator) || BOT || (navigator.connection && navigator.connection.saveData)) return; idle(function () { teamIds().slice(0, 4).forEach(function (id) { tnGet(id).then(function (t) { if (t && t.table && t.table.comp) fetch("/v1/comp/" + t.table.comp + "/standings.json").catch(function () {}); }); }); }); }
  function offlinePage() {
    var ul = $("#offl"); if (!ul) return; window.addEventListener("online", function () { location.reload(); });
    var mine = $("#offmine"), ids = teamIds().slice(0, 4);
    if (mine && ids.length) Promise.all(ids.map(function (id) { return fetch("/tn/" + id + ".json").then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); })).then(function (ts) { var html = ts.filter(Boolean).map(function (t) {
        return '<div class="card">' + '<div class="hd-row">' + U.crest({ id: t.id }, "md") + '<span class="rt"><span>' + U.esc(t.name_ar || t.name) + "</span>" + (t.table ? "<small>" + U.esc(t.table.comp_ar) + " · المركز " + t.table.rank + " · " + t.table.pts + " نقطة</small>" : "") + "</span></div>" + (t.next ? U.mrow(t.next, { date: 1 }) : "") + (t.recent || [t.last]).filter(Boolean).slice(0, 4).map(function (m) { return U.mrow(m, { date: 1, team: t.id }); }).join("") + "</div>" +
          (t.table && t.table.comp ? '<div class="offst" data-st="' + t.id + '" data-c="' + t.table.comp + '"></div>' : ""); }).join("");
      if (!html) return; mine.innerHTML = '<div class="gh"><h2>فريقك</h2></div><div class="stack">' + html + "</div>"; mine.hidden = false; localize(mine);
      // the table around each team, from the copy the phone kept (offlineKeep)
      $$(".offst", mine).forEach(function (el) { fetch("/v1/comp/" + el.dataset.c + "/standings.json").then(function (r) { return r.ok ? r.json() : null; }).then(function (st) { var tid = +el.dataset.st;
        var g = st && !st.composite && (st.groups || []).filter(function (g) { return (g.rows || []).some(function (r) { return r.team.id === tid; }); })[0]; if (!g) return;
        var i = g.rows.findIndex(function (r) { return r.team.id === tid; }), lo = Math.max(0, i - 2), hl = {}; hl[tid] = 1;
        el.innerHTML = U.grp("", U.table(g.rows.slice(lo, Math.min(g.rows.length, lo + 5)), { hl: hl }), { foot: "الترتيب من آخر مرة فتحت تيفو على النت." }); }).catch(function () {}); }); });
    if (!window.caches) { ul.innerHTML = '<div class="row"><span class="rt muted">ما في صفحات محفوظة.</span></div>'; return; }
    caches.open("tifo-pages").then(function (c) { return c.keys().then(function (ks) { return Promise.all(ks.reverse().slice(0, 40).map(function (k) { return c.match(k).then(function (r) { return r.text(); }).then(function (h) { var p = new URL(k.url).pathname, tt = (h.match(/<title>([^<]*)<\/title>/) || [])[1] || p; return { p: p, t: tt.replace(/\s*\|\s*تيفو\s*$/, "").replace(/&amp;/g, "&"), m: /^\/m\/\d+\//.test(p) }; }); })); }); })
      .then(function (Lst) { Lst = Lst.filter(function (x) { return x.p !== "/offline/"; }).sort(function (a, b) { return b.m - a.m; });
        ul.innerHTML = Lst.length ? Lst.map(function (x) { return U.row({ href: x.p, t: U.esc(x.t) }); }).join("") : '<div class="row"><span class="rt muted">ما في صفحات محفوظة للحين. افتح مبارياتك وأنت على النت وبتحصلها هني.</span></div>'; })
      .catch(function () { ul.innerHTML = '<div class="row"><span class="rt muted">ما قدرنا نقرا المحفوظ.</span></div>'; }); }

  // ================================================================== car mode: favourite clubs' kickoffs, goals and full times read aloud (speechSynthesis)
  var CAR = { t: null, seen: {} };
  function carMode() { clearInterval(CAR.t); var row = $(".carrow"); if (!window.speechSynthesis) { if (row) row.hidden = true; return; } if (!prefOn("car")) return;
    var sayIt = function (t) { var u = new SpeechSynthesisUtterance(t); u.lang = "ar-AE"; var v = speechSynthesis.getVoices().filter(function (v) { return /^ar/i.test(v.lang); })[0]; if (v) u.voice = v; speechSynthesis.speak(u); };
    var poll = function () { var ids = teamIds(); if (!ids.length) return; get("live.json", true).then(function (l) { (l.matches || []).forEach(function (m) { if (ids.indexOf(m.home.id) < 0 && ids.indexOf(m.away.id) < 0) return; var p = CAR.seen[m.id], Hn = U.tnameT(m.home), An = U.tnameT(m.away);
      if (!p) { if (m.minute && parseInt(m.minute, 10) < 3) sayIt("بدت مباراة " + Hn + " و" + An); } else if (m.score && p.score && (m.score.home !== p.score.home || m.score.away !== p.score.away)) sayIt("هدف! " + Hn + " " + m.score.home + "، " + An + " " + m.score.away); CAR.seen[m.id] = m; });
      Object.keys(CAR.seen).forEach(function (k) { if (!(l.matches || []).some(function (m) { return String(m.id) === k; })) { var m = CAR.seen[k]; if (m.score) sayIt("خلصت: " + U.tnameT(m.home) + " " + m.score.home + "، " + U.tnameT(m.away) + " " + m.score.away); delete CAR.seen[k]; } }); }).catch(function () {}); };
    poll(); CAR.t = setInterval(poll, 20000); }

  // ================================================================== push per team (start · goal · end) from the team's «نبّهني» sheet
  var PUSHOK = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window, PKEY = ls.get("tifo.pushkey", "");
  function pushSt() { return ls.json("tifo.push", {}); }
  function u8(k) { var p = "=".repeat((4 - k.length % 4) % 4), s = atob((k + p).replace(/-/g, "+").replace(/_/g, "/")), a = new Uint8Array(s.length); for (var i = 0; i < s.length; i++) a[i] = s.charCodeAt(i); return a; }
  function pushKey() { return PKEY ? Promise.resolve(PKEY) : getx("/api/tifo/push/key").then(function (j) { PKEY = j.publicKey; ls.set("tifo.pushkey", PKEY); return PKEY; }); }
  function pushSend(method, body) { return fetch("/api/tifo/push/sub", { method: method, headers: { "content-type": "application/json" }, body: JSON.stringify(body), keepalive: true }); }
  function pushSub() { return Promise.race([navigator.serviceWorker.ready, new Promise(function (ok, no) { setTimeout(function () { no(new Error("no worker")); }, 10000); })]).then(function (reg) { return reg.pushManager.getSubscription().then(function (s) { return s || pushKey().then(function (k) { return reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: u8(k) }); }); }); }); }
  function pushSync(tid) { var ev = ((pushSt().teams || {})[tid] || []).filter(function (x) { return !(prefOn("nospoil") && x !== "start"); }), msg = $("#pushm");
    if (!ev.length) return navigator.serviceWorker.ready.then(function (reg) { return reg.pushManager.getSubscription(); }).then(function (x) { if (x) pushSend("DELETE", { team: tid, endpoint: x.endpoint }); }).catch(function () {});
    return pushSub().then(function (x) { var j = x.toJSON(); return pushSend("POST", { team: tid, events: ev, subscription: { endpoint: j.endpoint, keys: j.keys } }); }).then(function (r) { if (msg) msg.textContent = r && r.ok !== false ? "تمام، بتوصلك التنبيهات." : "ما قدرنا نشغّلها الحين، جرّب بعد شوي."; })
      .catch(function () { if (msg) msg.textContent = "ما قدرنا نشغّلها. تأكد إن التنبيهات مسموحة لتيفو في إعدادات جوالك."; }); }
  function pushPaint() { var tid = +V.id, ev = (pushSt().teams || {})[tid] || []; $$("[data-push]").forEach(function (b) { b.setAttribute("aria-checked", String(ev.indexOf(b.dataset.push) >= 0)); }); }
  function pushInit() { var sh = $("#sh-notify"); if (!sh || PG !== "team") return; var tid = +V.id;
    if (!PUSHOK) { var m = $("#pushm"); if (m) m.innerHTML = IOS && !STANDALONE ? 'التنبيهات في آيفون تشتغل لما تثبّت تيفو على الشاشة الرئيسية. <a href="#" data-sheet="sh-install">شلون؟</a>' : "متصفحك ما يدعم التنبيهات."; $$("[data-push]", sh).forEach(function (b) { b.disabled = true; }); }
    pushPaint();
    sh.addEventListener("click", function (e) { var b = e.target.closest("[data-push]"); if (!b || !PUSHOK) return; var go = function () { var s = pushSt(); s.teams = s.teams || {}; var ev = s.teams[tid] || [], k = b.dataset.push, i = ev.indexOf(k); if (i >= 0) ev.splice(i, 1); else ev.push(k); if (ev.length) s.teams[tid] = ev; else delete s.teams[tid]; ls.set("tifo.push", JSON.stringify(s)); pushPaint(); pushSync(tid); if (ev.length && !isFav("team", tid)) { toggleFav("team", tid, B.dataset.name); paintFav(); } };
      if (Notification.permission === "default") { var p = Notification.requestPermission(); if (p && p.then) p.then(function (r) { if (r === "granted") go(); else { var m2 = $("#pushm"); if (m2) m2.textContent = "التنبيهات مقفولة. تقدر تسمح لها من إعدادات المتصفح."; } }); return; }
      if (Notification.permission === "denied") { var m3 = $("#pushm"); if (m3) m3.textContent = "التنبيهات مقفولة لتيفو. تقدر تسمح لها من إعدادات المتصفح."; return; } go(); });
    if (new URLSearchParams(location.search).get("notify") === "1") setTimeout(function () { openSheet(sh); }, 300);
    if (PUSHOK) idle(function () { if (!PKEY) pushKey().catch(function () {}); }); }
  // src/notify.js (TifoNotify, owner item 7) owns the subscription where it is loaded: it also sends the video switch and the quiet
  // hours, which a sync from here would drop
  function pushTeamChanged(tid, on) { if (on || !PUSHOK) return; if (window.TifoNotify) { try { window.TifoNotify.set(tid, []).catch(function () {}); } catch (e) {} return; } var s = pushSt(); if ((s.teams || {})[tid]) { delete s.teams[tid]; ls.set("tifo.push", JSON.stringify(s)); pushSync(tid); } }
  // after «تابع» on a team: where push works, offer its alerts once a session; elsewhere the install card
  function afterFollow(tid) { if (PG === "team" && PUSHOK && !ss.get("tifo.pushasked") && !(pushSt().teams || {})[tid]) { ss.set("tifo.pushasked", "1"); setTimeout(function () { openSheet("sh-notify"); }, 600); } else instAsk(); }
  D.addEventListener("tifo:nospoil", function () { if (!PUSHOK || window.TifoNotify) return; Object.keys(pushSt().teams || {}).forEach(function (tid) { pushSync(+tid); }); });   // TifoNotify resyncs on its own

  // ================================================================== the share sheet's tools: an image of any section, the embed code, a player's card, cinema
  function closeShare() { var d = $("#sh-share"); if (d && d.open) closeSheet(d, true); }
  D.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("#secpick, #embedbtn, #pcardbtn, [data-cine], #xibtn"); if (!b) return;
    if (b.id === "secpick") { var spl = $("#secpicks"); if (!spl) return; if (!spl.hidden) { spl.hidden = true; return; }
      var items = $$("main section.grp > .gh h2").map(function (h, i) { var s = h.closest("section"); s.dataset.pick = "p" + i; return ["@p" + i, h.textContent.trim()]; }).concat($$("dialog.sheet[id^='sx-']").map(function (d) { return [d.id, ($(".sh-hd h2", d) || {}).textContent || ""]; })).filter(function (x) { return x[1]; });
      spl.innerHTML = items.length ? items.map(function (x) { return '<button type="button" class="row" data-pk="' + x[0] + '"><span class="rt">' + U.esc(x[1]) + "</span>" + U.chev + "</button>"; }).join("") : '<div class="row"><span class="rt muted">ما في أقسام في هالصفحة.</span></div>'; spl.hidden = false;
      spl.onclick = function (ev) { var r = ev.target.closest("[data-pk]"); if (!r || !window.TifoShare) return; var k = r.dataset.pk, sec = k.charAt(0) === "@" ? $('[data-pick="' + k.slice(1) + '"]') : (function () { var d = D.getElementById(k); if (d) stampIn(d); return d && $(".sh-bd", d); })(); if (!sec) return;
        var title = $(".rt", r).textContent, lines = $$("li, tbody tr, .row .rt, .str, .mr", sec).slice(0, 8).map(function (x) { return x.textContent.replace(/\s+/g, " ").trim(); }).filter(Boolean); if (!lines.length) lines = [sec.textContent.replace(/\s+/g, " ").trim().slice(0, 160)]; closeShare(); window.TifoShare.card(title, lines); }; return; }
    if (b.id === "embedbtn") { var u = b.dataset.src, code = '<iframe src="https://tifo.elyoxe.com' + u + '" width="100%" height="' + (b.dataset.h || 420) + '" style="border:0" loading="lazy" title="تيفو"></iframe>', l = $("#embout") || $("#secpicks"); if (!l) return;
      l.innerHTML = '<p class="gf" style="padding:12px 16px 0">انسخ الكود وحطه في موقعك:</p><textarea class="embc" rows="4" readonly>' + U.esc(code) + '</textarea><button type="button" class="row link" id="embcopy"><span class="rt">انسخ الكود</span></button>'; l.hidden = false;
      $("#embcopy").onclick = function () { (navigator.clipboard ? navigator.clipboard.writeText(code) : Promise.reject()).then(function () { toast("انتسخ الكود"); }, function () { $("textarea", l).select(); }); }; return; }
    if (b.id === "pcardbtn") { var list = $("#secpicks"); var md = MD && MD.lineups ? MD : null; var go2 = function (md2) { if (!md2 || !md2.lineups || !md2.lineups.home) { list.innerHTML = '<div class="row"><span class="rt muted">التشكيلة للحين مب منشورة.</span></div>'; list.hidden = false; return; }
        var ps = []; ["home", "away"].forEach(function (s) { (md2.lineups[s].starters || []).concat(md2.lineups[s].subs || []).forEach(function (p) { if (p.rating != null || p.minutes_on != null || (md2.lineups[s].starters || []).indexOf(p) >= 0) ps.push([s, p]); }); }); ps.sort(function (a, c) { return (c[1].rating || 0) - (a[1].rating || 0); });
        list.innerHTML = ps.map(function (x, i) { return '<button type="button" class="row" data-pc="' + i + '"><span class="rt">' + U.pname(x[1]) + "</span>" + (x[1].rating != null ? '<span class="rv num">' + Number(x[1].rating).toFixed(1) + "</span>" : "") + "</button>"; }).join(""); list.hidden = false;
        list.onclick = function (ev) { var r = ev.target.closest("[data-pc]"); if (!r) return; var x = ps[+r.dataset.pc]; closeShare(); playerCard(md2, x[0], x[1]); }; };
      if (md) go2(md); else get("match/" + V.id + ".json").then(function (m) { MD = m; go2(m); }).catch(function () { go2(null); }); return; }
    if (b.hasAttribute("data-cine")) { closeShare(); cineOpen(); return; }
    if (b.id === "xibtn") { lineupBuilder(); return; }
  });
  // 373: a player's match card (rating, minutes, goals, assists, shots, cards) as a shareable image (src/share.js draws and saves it)
  function playerCard(md, side, p) { if (!window.TifoShare) return; var W = 1080, Hh = 1350, c = D.createElement("canvas"); c.width = W; c.height = Hh; var x = c.getContext("2d"), tm = md[side];
    var ev = md.events || [], g = ev.filter(function (e) { return /goal/.test(e.type) && e.type !== "own_goal" && e.player && e.player.id === p.id; }).length, a = ev.filter(function (e) { return e.assist && e.assist.id === p.id; }).length;
    var sh = (md.shotmap || []).filter(function (s) { return s.player_id === p.id || (s.player && s.player.id === p.id); }), cards = ev.filter(function (e) { return e.player && e.player.id === p.id && /yellow|red/.test(e.type); }).length;
    var mins = p.minutes_off != null ? p.minutes_off - (p.minutes_on || 0) : p.minutes_on != null ? 90 - p.minutes_on : 90, col = U.col(tm.id, 0), BG = "#0B3D24", CH = "#F6F7F2";
    x.fillStyle = BG; x.fillRect(0, 0, W, Hh); for (var r = 0; r < 12; r++) for (var q = 0; q < 27; q++) { x.globalAlpha = 0.55 + ((r * 7 + q * 3) % 5) / 12; x.fillStyle = (q + r) % 7 < 2 ? U.col(tm.id, 1) : col; x.fillRect(q * 40, r * 40, 37, 37); } x.globalAlpha = 1;
    var gr = x.createLinearGradient(0, 200, 0, 520); gr.addColorStop(0, "rgba(11,61,36,0)"); gr.addColorStop(1, BG); x.fillStyle = gr; x.fillRect(0, 200, W, 320);
    x.direction = "rtl"; x.textAlign = "center"; x.fillStyle = CH; x.font = '800 76px "Noto Kufi Arabic"'; x.fillText(U.pnameT(p), W / 2, 610);
    x.font = '400 38px "Readex Pro"'; x.fillStyle = "#C7D5CD"; x.fillText(U.tnameT(tm) + " · " + U.tnameT(md.home) + " " + (md.score ? md.score.home + " - " + md.score.away : "") + " " + U.tnameT(md.away), W / 2, 680);
    x.font = '700 260px "Barlow Condensed"'; x.fillStyle = CH; x.fillText(p.rating != null ? Number(p.rating).toFixed(1) : "—", W / 2, 950); x.font = '800 36px "Noto Kufi Arabic"'; x.fillStyle = "#C7D5CD"; x.fillText("تقييم المباراة", W / 2, 1010);
    [["دقيقة", mins], ["أهداف", g], ["صناعة", a], ["تسديد", sh.length], ["كروت", cards]].forEach(function (s, i) { var cx = W - 120 - i * 210; x.font = '700 90px "Barlow Condensed"'; x.fillStyle = CH; x.fillText(String(s[1]), cx, 1150); x.font = '400 32px "Readex Pro"'; x.fillStyle = "#C7D5CD"; x.fillText(s[0], cx, 1200); });
    x.font = '700 38px "Barlow Condensed"'; x.textAlign = "left"; x.fillStyle = "#C7D5CD"; x.fillText("tifo.elyoxe.com", 60, Hh - 60); x.textAlign = "right"; x.font = '800 54px "Noto Kufi Arabic"'; x.fillStyle = CH; x.fillText("تيفو", W - 60, Hh - 55);
    (D.fonts ? Promise.all(['800 60px "Noto Kufi Arabic"', '700 60px "Barlow Condensed"', '400 30px "Readex Pro"'].map(function (f) { return D.fonts.load(f).catch(function () {}); })) : Promise.resolve()).then(function () { window.TifoShare.out(c, "tifo-" + md.id + "-" + p.id + ".png"); }); }
  // 359: cinema mode — the score, the minute and the last event, full screen, the screen kept awake
  function cineOpen() { var md = MD; if (!md) return; var el = D.createElement("div"); el.className = "cine"; el.innerHTML = '<button type="button" class="is-x" aria-label="سكّر">' + U.icon("close", "", 2.6) + '</button><div class="ci"></div>'; B.appendChild(el); var wl = null;
    var draw = function () { var m = MD || md, ev = (m.events || []).filter(function (e) { return e.type !== "added_time" && e.type !== "half"; }).pop(); $(".ci", el).innerHTML = '<div class="ct3"><span>' + U.crest(m.home, "xl") + "<b>" + U.tname(m.home) + '</b></span><span class="cs">' + U.mid(m) + '</span><span>' + U.crest(m.away, "xl") + "<b>" + U.tname(m.away) + "</b></span></div><p>" + (U.isLive(m) ? U.minute(m) : U.statusWord(m) || U.timeText(m.kickoff_utc, "dt")) + "</p>" + (ev ? '<p class="ce"><bdi dir="ltr">' + ev.minute + "'</bdi> " + U.pname(ev.player || {}) + "</p>" : ""); localize(el); };
    draw(); var t = setInterval(draw, 5000), shut = function () { clearInterval(t); if (D.fullscreenElement) D.exitFullscreen().catch(function () {}); if (wl) { wl.release().catch(function () {}); wl = null; } el.remove(); D.removeEventListener("keydown", esc2); }, esc2 = function (e) { if (e.key === "Escape") shut(); };
    $(".is-x", el).onclick = shut; D.addEventListener("keydown", esc2); if (el.requestFullscreen) el.requestFullscreen().catch(function () {}); if (navigator.wakeLock) navigator.wakeLock.request("screen").then(function (l) { wl = l; }).catch(function () {}); }
  // 376: lineup builder — the team's squad on a pitch in the chosen formation, kept on this phone, shared as an image
  function lineupBuilder() {
    var id = "sh-xi", d = D.getElementById(id); if (!d) { var w = D.createElement("div"); w.innerHTML = U.sheet(id, "سوّ تشكيلتك", '<div id="xib"><div class="card">' + U.empty("نحمّل اللاعبين…") + "</div></div>"); d = w.firstChild; B.appendChild(d); wireSheet(d); }
    openSheet(d); var box = $("#xib", d), TID = +V.id, KEY = "tifo.xi." + TID;
    get("team/" + TID + ".json").then(function (t) { var sq = [], by = {}; (t.squad || []).forEach(function (g) { if (g.group !== "coach") (g.players || []).forEach(function (p) { var q = { id: p.id, name: U.pnameT(p), no: p.number, g: g.group }; sq.push(q); by[p.id] = q; }); });
      var F = { "4-3-3": [1, 4, 3, 3], "4-4-2": [1, 4, 4, 2], "4-2-3-1": [1, 4, 2, 3, 1], "3-5-2": [1, 3, 5, 2] }, cur = "4-3-3", pick = {}, sv = ls.json(KEY, null); if (sv && F[sv.f]) { cur = sv.f; pick = sv.p || {}; }
      var save = function () { ls.set(KEY, JSON.stringify({ f: cur, p: pick })); }, slots = function () { var out = [], n = 0; F[cur].forEach(function (k, ri) { for (var i = 0; i < k; i++) out.push({ r: ri, i: i, k: k, n: n++ }); }); return out; };
      var shortN = function (n) { var w2 = String(n || "").trim().split(/\s+/); return w2.length < 2 ? w2[0] || "" : w2[w2.length - 1]; }, col = U.col(TID), ink = U.ink(col);
      var draw = function () { var rows = F[cur], S = slots(), full = S.filter(function (s) { return by[pick[s.n]]; }).length;
        box.innerHTML = U.seg("xf", Object.keys(F).map(function (f) { return [f, f]; }), cur, { sm: 1 }) + '<div class="card pitchw mt"><div class="pitch" dir="ltr"><i class="ln out"></i><i class="ln half"></i><i class="ln cc"></i><i class="ln box1"></i><i class="ln box2"></i>' + S.map(function (s) { var p = by[pick[s.n]], y = 92 - s.r * (82 / (rows.length - 1)), x = (s.i + 1) * 100 / (s.k + 1);
          return '<button type="button" class="pp xs" data-s="' + s.n + '" style="left:' + x.toFixed(1) + "%;top:" + y.toFixed(1) + '%" aria-label="' + (p ? U.esc(p.name) : s.r === 0 ? "اختار الحارس" : "اختار لاعب") + '"><span class="sh" style="--pc:' + (p ? col : "rgba(255,255,255,.25)") + ";--pci:" + (p ? ink : "#fff") + '">' + (p ? (p.no != null ? p.no : "•") : "+") + '</span><span class="nm">' + (p ? U.esc(shortN(p.name)) : s.r === 0 ? "الحارس" : "اختار") + "</span></button>"; }).join("") + "</div></div>" +
          '<p class="gf">' + full + ' من 11</p><div id="xpick"></div>' + U.grp("", U.row({ btn: 1, icon: "share", c: "#0A84FF", t: "شارك تشكيلتي", attrs: ' id="xishare"' + (full ? "" : " disabled") }), { cls: "mt" }); };
      var picker = function (n) { var gk = n === 0, list = sq.filter(function (p) { return gk ? p.g === "keepers" : p.g !== "keepers"; }), where = {}; Object.keys(pick).forEach(function (k) { where[pick[k]] = +k; });
        $("#xpick", box).innerHTML = U.grp(gk ? "اختار الحارس" : "اختار لاعب", (pick[n] ? U.row({ btn: 1, t: "شيل اللاعب من المركز", cls: "link", attrs: " data-xrm" }) : "") + list.map(function (p) { var at = where[p.id]; return U.row({ btn: 1, t: '<span class="num muted">' + (p.no != null ? p.no : "") + "</span> " + U.esc(p.name), sub: at != null && at !== n ? "في التشكيلة" : "", attrs: ' data-xp="' + p.id + '"' }); }).join(""), { cls: "mt" }); $("#xpick", box).dataset.n = n; $("#xpick", box).scrollIntoView({ block: "nearest", behavior: RM ? "auto" : "smooth" }); };
      box.onclick = function (e) { var f = e.target.closest('.seg[data-seg="xf"] button[data-t]'); if (f) { var old = slots(), gk = pick[0], rest = old.filter(function (s) { return s.r > 0; }).map(function (s) { return pick[s.n]; }).filter(Boolean); cur = f.dataset.t; var np = {}; if (gk) np[0] = gk; slots().filter(function (s) { return s.r > 0; }).forEach(function (s, i) { if (rest[i]) np[s.n] = rest[i]; }); pick = np; save(); draw(); return; }
        var s = e.target.closest(".xs"); if (s) { picker(+s.dataset.s); return; } var n = +($("#xpick", box).dataset.n || 0);
        if (e.target.closest("[data-xrm]")) { delete pick[n]; save(); draw(); return; } var pp = e.target.closest("[data-xp]"); if (pp) { var pid = +pp.dataset.xp, from = null; Object.keys(pick).forEach(function (k) { if (pick[k] === pid) from = +k; }); if (from != null && from !== n) { if (pick[n]) pick[from] = pick[n]; else delete pick[from]; } pick[n] = pid; save(); draw(); return; }
        if (e.target.closest("#xishare")) shareXI(); };
      var shareXI = function () { if (!window.TifoShare) return; var S = slots(), rows = F[cur], W = 1080, Hh = 1350, c = D.createElement("canvas"); c.width = W; c.height = Hh; var x = c.getContext("2d"); x.fillStyle = "#1F5E36"; x.fillRect(0, 0, W, Hh);
        x.strokeStyle = "rgba(255,255,255,.35)"; x.lineWidth = 4; x.strokeRect(60, 140, W - 120, Hh - 260); x.beginPath(); x.moveTo(60, Hh / 2 + 20); x.lineTo(W - 60, Hh / 2 + 20); x.stroke();
        x.direction = "rtl"; x.textAlign = "center"; x.fillStyle = "#F6F7F2"; x.font = '800 54px "Noto Kufi Arabic"'; x.fillText("تشكيلتي لـ" + U.tnameT(t) + " (" + cur + ")", W / 2, 95);
        S.forEach(function (s) { var p = by[pick[s.n]], y = Hh - 180 - s.r * ((Hh - 380) / (rows.length - 1)), xx = 60 + (s.i + 1) * (W - 120) / (s.k + 1); x.fillStyle = col; x.beginPath(); x.arc(xx, y, 36, 0, 7); x.fill();
          x.fillStyle = ink; x.font = '700 34px "Barlow Condensed"'; x.fillText(p && p.no != null ? String(p.no) : "", xx, y + 12); x.fillStyle = "#F6F7F2"; x.font = '600 30px "Readex Pro"'; x.fillText(p ? shortN(p.name) : "—", xx, y + 76); });
        x.textAlign = "left"; x.fillStyle = "#C7D5CD"; x.font = '700 36px "Barlow Condensed"'; x.fillText("tifo.elyoxe.com", 60, Hh - 45);
        (D.fonts ? D.fonts.ready : Promise.resolve()).then(function () { window.TifoShare.out(c, "tifo-xi-" + t.id + ".png"); }); };
      draw(); }).catch(function () { box.innerHTML = '<div class="card">' + U.empty("ما قدرنا نحمّل اللاعبين.") + "</div>"; }); }

  // ================================================================== pages that keep their v3 bodies: what the v3 shell (shell.js) did for them
  function legacyPages() {
    // /thisday/: today in the visitor's own time zone, أمس/بكرة step one calendar day, the folded days are the source
    (function () { var box = $("#tdnow"); if (!box) return; var MON = U.MON, today = new Date().toLocaleDateString("en-CA").slice(5), cur = today, body = $("#tdb"), head = $("#tdh");
      var step = function (md, d) { var t = new Date(Date.UTC(2024, +md.slice(0, 2) - 1, +md.slice(3) + d)); return ("0" + (t.getUTCMonth() + 1)).slice(-2) + "-" + ("0" + t.getUTCDate()).slice(-2); };
      var show = function (md) { cur = md; var s = $('details.tdm section[data-md="' + md + '"]'), lbl = +md.slice(3) + " " + MON[+md.slice(0, 2) - 1]; head.textContent = md === today ? "اليوم، " + lbl : md === step(today, -1) ? "أمس، " + lbl : md === step(today, 1) ? "بكرة، " + lbl : lbl; box.dataset.md = md;
        if (s) { var c = s.cloneNode(true), h = c.querySelector("h2"); if (h) h.remove(); body.innerHTML = c.innerHTML; } else body.innerHTML = '<p class="muted">ما عندنا حدث مسجّل في هاليوم.</p>'; };
      if (today !== box.dataset.md) show(today); box.addEventListener("click", function (e) { var t = e.target.closest("[data-td]"); if (t) show(step(cur, +t.dataset.td)); }); })();
    // /national/: «منتخبك» (the visitor's national team: last result and next match) and the day's national matches kept live
    (function () { var fl = $(".natflags"); if (!fl) return; var cc = country(), nid = (window.NAT || {})[cc], me = $("#natme"), mb = $("#natmeb");
      if (!nid) { if (me) me.hidden = true; } else tnGet(nid).then(function (t) { if (!t || !mb) return; mb.innerHTML = '<a class="hd-row" href="/t/' + nid + '/">' + U.crest(t, "md") + '<span class="rt"><span>' + U.tname(t) + "</span></span>" + U.chev + "</a>" + (t.last ? U.mrow(t.last, { date: 1, team: nid }) : "") + (t.next ? U.mrow(t.next, { date: 1 }) : ""); localize(mb); var f = fl.querySelector('[data-cc="' + cc + '"]'); if (f) f.classList.add("me"); }); })();
    // /week/: the pinned «مباراة الأسبوع» counts down to its kickoff
    // 417: «تيفو الأسبوع» on /week/ when the build had no weekly file yet, or a newer week is out (render.js draws it)
    (function () { var pair = $("#wkpair"), T = window.TR; if (!pair || !T || !T.weekCard) return; var have = $("#wkcard");
      fetch("/og/week-latest.json", { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (j) { if (!j || !(j.items || []).length || (have && have.dataset.week === j.week)) return;
        var t = D.createElement("div"); t.innerHTML = T.weekCard(j, { links: false }); var card = t.firstElementChild; if (!card) return; if (have) have.replaceWith(card); else pair.appendChild(card); if (T.localize) T.localize(card); }).catch(function () {}); })();
    (function () { var pin = $("#mow"), cd = $("#mowcd"); if (!pin || !cd || !pin.dataset.kick) return; cd.dataset.cdko = pin.dataset.kick; })();
    // QA 70/78: «مباراة الليلة في 60 ثانية» follows the viewer's clock
    $$("b[data-kick]").forEach(function (el) { if (window.TR && window.TR.dayWord) { el.textContent = "مباراة " + window.TR.dayWord(el.dataset.kick) + " في 60 ثانية"; return; } var t = Date.parse(el.dataset.kick), w = U.relDay(new Date(t).toISOString()) || U.dname(new Date(t).toISOString()); if (w) el.textContent = "مباراة " + (w === "اليوم" && new Date(t).getHours() >= 17 ? "الليلة" : w) + " في 60 ثانية"; });
    // W3.4: the visitor's channel on every row that shows one (.chn[data-comp]); the prerender shows the UAE's
    (function () { var els = $$(".chn[data-comp]"); if (!els.length) return; var cc = country(); if (!cc || cc === "AE" || cc === "xx") return; loadBC().then(function (bc) { var m = (bc || {})[cc] || {}; els.forEach(function (el) { var e = m[el.dataset.comp]; if (!e || !e.b || !e.b.length) { el.hidden = true; return; } el.hidden = false; el.innerHTML = U.esc(e.b[0][0]) + (e.b.some(function (x) { return x[1]; }) ? "" : " <b>مشفرة</b>"); }); }); })();
    // the live clock on legacy rows (render.js .lmin): each ticking minute moves every second between polls
    if ($(".lmin[data-ps]")) setInterval(function () { if (!window.TR || !window.TR.clock) return; $$(".lmin[data-ps]").forEach(function (el) { var v = window.TR.clock(el.dataset.ps, el.dataset.pb, el.dataset.pl); if (el.textContent !== v) el.textContent = v; }); }, 1000);
    // 404: today's matches under the links
    (function () { var d = $("#day404"); if (!d) return; get("day/" + new Date(NOW() + 4 * 36e5).toISOString().slice(0, 10).replace(/-/g, "") + ".json").then(function (j) { var ms = j.matches || []; if (!ms.length) return; d.innerHTML = '<section class="grp mt2"><div class="gh"><h2>مباريات اليوم</h2></div><div class="stack">' + U.dayList(ms, {}) + "</div></section>"; localize(d); }).catch(function () {}); })();
  }

  // W1.10: a cookieless visit ping (path, country, how long since the last visit on this phone); crawlers and headless browsers are not visitors
  (function () { try { if (BOT) return; var cc0 = country() || "", last = +ls.get("tifo.seen", 0) || 0, now = NOW(), d = (now - last) / 864e5, ret = !last ? "first" : new Date(last).toDateString() === new Date(now).toDateString() ? "same_day" : d <= 7 ? "d1_7" : "d8p";
    ls.set("tifo.seen", String(now)); ls.set("tifo.ret", ret); if (ret === "first") ss.set("tifo.first", "1"); fetch("/api/tifo/hit", { method: "POST", keepalive: true, headers: { "content-type": "application/json" }, body: JSON.stringify({ path: location.pathname, country: cc0 === "xx" ? "" : cc0, ret: ret }) }).catch(function () {}); } catch (e) {} })();

  // tv.js, media.js and share.js read a few helpers from window.TR (render.js, in the legacy bundle); pages without it get these
  if (!LEGACY && !window.TR) window.TR = { esc: U.esc, COUNTRIES: (C.countries || []).map(function (c) { return [c[0], c[1], c[2]]; }), isLive: U.isLive, localize: localize,
    hhmm: function (iso) { return U.hhmm(iso); }, ymd: function (iso) { return iso && iso.length > 10 ? U.ymd(iso) : String(iso || "").slice(0, 10); },
    dayParts: function (ymd, today) { if (!ymd) return { rel: "", date: "" }; var p = ymd.split("-").map(Number), d = new Date(Date.UTC(p[0], p[1] - 1, p[2])), rel = "";
      if (today) { var t = today.split("-").map(Number), k = Math.round((d - Date.UTC(t[0], t[1] - 1, t[2])) / 864e5); rel = k === 0 ? "اليوم" : k === 1 ? "بكرة" : k === -1 ? "أمس" : ""; }
      return { rel: rel, date: U.DAY[d.getUTCDay()] + " " + p[2] + " " + U.MON[p[1] - 1], short: p[2] + " " + U.MON[p[1] - 1] }; },
    dayLabel: function (ymd, today) { var x = window.TR.dayParts(ymd, today); return x.rel ? x.rel + "، " + x.date : x.date; },
    hl: function (md) { var u = md && md.highlights && md.highlights.url; return u && /^https:\/\//.test(u) ? '<p class="hlink"><a class="btn hlbtn" href="' + U.esc(u) + '" target="_blank" rel="noopener">▶ الملخص</a></p>' : ""; } };
  // share images (src/share.js: story, wallpaper, any section, lists) load the first time one is asked for
  // «الأرقام مدققة»: the footer's badge from the last data audit (db/audit.py, v1/audit/latest.json), only when it passed; filled here
  // and not in the page since 2026-10-07, so an audit never changes every page
  idle(function () {
    var el = $("#auditb"); if (!el) return;
    getx("/v1/audit/latest.json").then(function (a) {
      if (!a || a.ok !== true || !a.generated || a.errors > 0) return;
      el.innerHTML = '<span class="ab">' + U.icon("check", "", 2.6) + "الأرقام مدققة</span> آخر تدقيق " + U.tm(a.generated, "dt") + (a.checked ? ' · <span class="num">' + U.nf(a.checked) + "</span> رقم" : "");
      el.hidden = false;
    }).catch(function () {});
  });
  if (!window.TifoShare && C.share) (function () { var pr = null, load = function () { return pr || (pr = new Promise(function (ok, no) { var s = D.createElement("script"); s.src = "/assets/share." + C.share + ".js"; s.onload = function () { ok(window.TifoShare); }; s.onerror = function () { pr = null; no(new Error("share.js")); }; D.head.appendChild(s); })); };
    var st = { lazy: true, preload: function () { load().catch(function () {}); } }; ["story", "wallpaper", "banner", "out", "card", "listCard"].forEach(function (k) { st[k] = function () { var a = arguments; return load().then(function (T) { return T[k].apply(T, a); }); }; }); window.TifoShare = st; })();
  D.addEventListener("click", function (e) { if (e.target.closest && e.target.closest('[data-sheet="sh-share"]') && window.TifoShare && window.TifoShare.preload) window.TifoShare.preload(); }, true);
  // 223: the second screen — the header and the events only, big, the screen kept awake; one button to leave it
  var WL2 = null;
  function second(on) { B.classList.toggle("second", on); var x = $("#second-x"); if (on && !x) { x = D.createElement("button"); x.type = "button"; x.id = "second-x"; x.className = "pill second-x"; x.textContent = "سكّر الشاشة الثانية"; x.onclick = function () { second(false); }; B.appendChild(x); } else if (!on && x) x.remove();
    if (on && navigator.wakeLock) navigator.wakeLock.request("screen").then(function (l) { WL2 = l; }).catch(function () {}); else if (!on && WL2) { WL2.release().catch(function () {}); WL2 = null; }
    if (on) { var seg = $('.seg[data-seg="m"]'); if (seg) selectSeg(seg, "ov", false); window.scrollTo(0, 0); } }
  D.addEventListener("click", function (e) { if (e.target.closest && e.target.closest("#secondbtn")) { closeShare(); second(!B.classList.contains("second")); } });
  D.addEventListener("keydown", function (e) { if (e.key === "Escape" && B.classList.contains("second")) second(false); });

  // ------------------------------------------------------------------ boot
  applyTz(); observeNav(); paintFav(); paintPrefs(); wire(D); deepLink(); pickFilter();
  if (PG === "home" || PG === "daypage" || PG === "all") homeInit();
  else if (PG === "match") matchInit();
  else if (PG === "team") teamInit();
  else if (PG === "comp") compInit();
  else if (PG === "news") newsInit();
  else if (PG === "mine") mineRender();
  else if (PG === "search") searchInit();
  else if (PG === "db") dbInit();
  else if (PG === "offline") offlinePage();
  if (LEGACY) D.addEventListener("DOMContentLoaded", legacyPages); else legacyPages();   // render.js (window.TR) runs after this bundle
  var cur = $(".pane:not([hidden])"); if (cur) { lazyNews(cur); playerMounts(cur); }
  var rs = $("#rounds button[aria-selected=true]"); if (rs) rs.scrollIntoView({ inline: "center", block: "nearest" });
  island(); onbMaybe(); carMode(); instPaint(); instAsk(); offlineKeep();
})();
