/* تيفو v3 shell (redesign/DESIGN-v3.md): the bar, the two sheets (شارك وأدوات، المزيد), the reader panel for shelf tiles
   (templated sections stamped on first open), deep links, home rails refreshed from app.js's own poll ("tifo:day"),
   the match mini-bar ("tifo:match"), key art, parallax, rail arrows. Runs after app.js; it never re-fetches data. */
(function(){
  "use strict";
  var R = window.TR, B = document.body, PAGE = B.dataset.page, RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function(s, r){ return (r || document).querySelector(s); }, $$ = function(s, r){ return [].slice.call((r || document).querySelectorAll(s)); };
  if (window.PN && R.setNames) R.setNames(window.PN);
  if (window.TAR && R.setClubNames) R.setClubNames(window.TAR);
  R._hasWhy = !!document.querySelector(".why");   // 391

  // ---- top bar: transparent over the hero, solid once the page moves
  var top = $(".top"); function onScroll(){ if (top) top.classList.toggle("solid", window.scrollY > 40); }
  onScroll();

  // ---- sheets + panel: one open at a time, Esc / scrim / close button, focus returns to the opener
  var opener = null, scrim = $("#scrimall");
  // W1.9: an open sheet or panel owns one history entry, so the phone's back gesture closes it instead of leaving the page
  function anyOpen(){ return !!document.querySelector(".sheet:not([hidden]),.panel:not([hidden])"); }
  // W2.9: the page behind an open sheet is inert; closing slides out in 180 ms
  function inert(on){ ["main", ".top", ".tabbar", ".foot", ".mini"].forEach(function(q){ var e = $(q); if (e) e.inert = on; }); }
  function closeAll(fromPop){ var was = anyOpen(); $$(".sheet:not([hidden]),.panel:not([hidden])").forEach(function(s){ if (RM || fromPop === "now"){ s.hidden = true; if (s.id === "panel") unpanel(); return; } s.classList.add("out"); setTimeout(function(){ s.hidden = true; s.classList.remove("out"); var inn = s.firstElementChild; if (inn) inn.style.transform = ""; if (s.id === "panel") unpanel(); }, 180); }); scrim.hidden = true; B.classList.remove("locked"); inert(false); if (opener && opener.focus) opener.focus(); opener = null;
    if (was && fromPop !== true && history.state && history.state.tifoOv) try { history.back(); } catch (e){} }
  function open(el, from){ var had = anyOpen(); if (had) $$(".sheet:not([hidden]),.panel:not([hidden])").forEach(function(s){ s.hidden = true; if (s.id === "panel") unpanel(); }); opener = from || document.activeElement; el.hidden = false; el.classList.remove("out"); scrim.hidden = false; B.classList.add("locked"); inert(true);
    var inn = el.firstElementChild; if (inn && !inn.querySelector(":scope > .grab")){ var g = document.createElement("i"); g.className = "grab"; g.setAttribute("aria-hidden", "true"); inn.insertBefore(g, inn.firstChild); } var f = el.querySelector("button,a,[tabindex]"); if (f) setTimeout(function(){ f.focus({ preventScroll:true }); }, 30);
    if (!(had && history.state && history.state.tifoOv)) try { history.pushState({ tifoOv:1 }, ""); } catch (e){} }
  // W2.9: drag a sheet down by its grab bar or header to close it (80 px or a flick), transform only
  (function(){ var drag = null;
    document.addEventListener("pointerdown", function(e){ var h = e.target.closest(".grab, .sh-h, .pn-h"); if (!h || e.target.closest("button")) return; var inn = h.closest(".sh-in, .pn-in"); if (!inn || matchMedia("(min-width:880px)").matches) return; drag = { inn:inn, y0:e.clientY, t0:performance.now(), dy:0 }; inn.style.transition = "none"; }, { passive:true });
    document.addEventListener("pointermove", function(e){ if (!drag) return; drag.dy = Math.max(0, e.clientY - drag.y0); drag.inn.style.transform = "translateY(" + drag.dy + "px)"; }, { passive:true });
    document.addEventListener("pointerup", function(){ if (!drag) return; var d = drag; drag = null; d.inn.style.transition = ""; var v = d.dy / Math.max(1, performance.now() - d.t0);
      if (d.dy > 80 || v > 0.6) closeAll(); else d.inn.style.transform = ""; }); })();
  window.addEventListener("popstate", function(){ if (anyOpen()) closeAll(true); var sb = $("#srchbox"); if (sb) sb.remove(); });
  // search closes on a tap outside it
  document.addEventListener("click", function(e){ var sb = $("#srchbox"); if (sb && !sb.contains(e.target) && !e.target.closest("#srch")) sb.remove(); });
  document.addEventListener("click", function(e){
    var t = e.target.closest("[data-sheet]"); if (t){ e.preventDefault(); if (window.TifoShare && window.TifoShare.preload) window.TifoShare.preload(); open($("#" + t.dataset.sheet), t); return; }
    if (e.target.closest("[data-close]") || e.target === scrim || (e.target.classList && (e.target.classList.contains("sheet") || e.target.classList.contains("panel")))) { closeAll(); return; }
    var o = e.target.closest("[data-open]"); if (o){ panel(o.dataset.open, o); return; }
    var g = e.target.closest("[data-go]"); if (g){ e.preventDefault(); goTab(g.dataset.go); return; }
    var sg = e.target.closest("[data-seg]"); if (sg){ e.preventDefault(); var ab = $("#arabonly"); if (ab && ab.getAttribute("aria-pressed") !== "true") ab.click(); var mt = $("#matches"); if (mt) mt.scrollIntoView({ behavior:RM ? "auto" : "smooth" }); return; }
    // settings buttons inside المزيد open their own boxes (app.js): close the sheet first
    if (e.target.closest("#more #ctry, #srch")) { $$(".sheet:not([hidden])").forEach(function(s){ s.hidden = true; }); scrim.hidden = true; B.classList.remove("locked"); }
    // client-rendered links to a prototype page stay inside /next/
    var a = e.target.closest("a[href^='/']"); if (a && R.isProto && R.isProto(a.getAttribute("href"))) { e.preventDefault(); location.href = "/next" + a.getAttribute("href"); }
  }, true);
  document.addEventListener("keydown", function(e){ if (e.key === "Escape") closeAll(); });

  // ---- reader panel: a shelf tile's section, stamped from its <template> once, moved back on close
  var cur = null;
  function node(key){ var v = document.getElementById("v-" + key); if (!v) return null;
    if (v.tagName === "TEMPLATE"){ var d = document.createElement("div"); d.className = "vault"; d.id = v.id; d.hidden = true; d.appendChild(v.content.cloneNode(true)); v.parentNode.replaceChild(d, v); R.localize(d); v = d; }
    return v; }
  function panel(key, from){
    var v = node(key); if (!v) return; var body = v.querySelector(".pbody") || $("#panelb .pbody"); if (!body) return;
    var pn = $("#panel"); open(pn, from); cur = { key:key, vault:v, body:body };
    var h2 = body.querySelector("h2"); $("#panelt").textContent = body.dataset.title || (h2 ? h2.firstChild.textContent : "");
    var sm = h2 && h2.querySelector("small"); $("#panels").innerHTML = sm ? sm.innerHTML : "";
    $("#panelb").appendChild(body); $("#panelb").scrollTop = 0;
    if (from && from.dataset.anchor) try { history.replaceState(history.state, "", "#" + from.dataset.anchor); } catch (e){}
  }
  function unpanel(){ if (cur){ cur.vault.appendChild(cur.body); cur = null; } }

  // ---- tabs: deep links (#num, #n-cards, old #goals/#assists), data-go buttons
  function goTab(k){ var b = $('.mtabs button[data-t="' + k + '"]'); if (b){ b.click(); var bar = $(".mtabs"); if (bar) window.scrollTo({ top:bar.getBoundingClientRect().top + window.scrollY - 60, behavior:RM ? "auto" : "smooth" }); } }
  (function deep(){
    var h = ""; try { h = decodeURIComponent(location.hash.slice(1)); } catch (e){} if (!h || !/^[\w-]+$/.test(h)) return;   // an odd hash must never break the page script
    if (h === "story" && $("#storybtn")){ setTimeout(function(){ open($("#share"), $("#storybtn")); }, 300); return; }   // W3.7: «صورة للستوري» from فريقك
    if (h === "nums" && !$('.mtabs button[data-t="nums"]') && $('.mtabs button[data-t="hist"]')) h = "hist";   // W4.3: a national team's numbers live in التاريخ
    if (/^[\w-]+$/.test(h) && $('.mtabs button[data-t="' + h + '"]')){ goTab(h); return; }   // any tab by its key (#hist, #squad, #past…)
    var alias = { goals:["num", "goals"], assists:["num", "assists"], ana:["stats"] }[h];
    if (alias){ goTab(alias[0]); var s = $('.seg button[data-t="' + alias[1] + '"]'); if (s) s.click(); return; }
    var t = $('[data-anchor="' + h + '"]'); if (t){ var p = t.closest("[data-pane]"); if (p) goTab(p.dataset.pane); setTimeout(function(){ panel(t.dataset.open, t); }, 60); }
  })();

  // ---- the share sheet
  var cl = $("#copylink"); if (cl) cl.onclick = function(){ var u = location.href.split("#")[0]; (navigator.clipboard ? navigator.clipboard.writeText(u) : Promise.reject()).then(function(){ cl.textContent = "انتسخ ✓"; setTimeout(function(){ cl.textContent = "انسخ الرابط"; }, 1800); }, function(){ prompt("انسخ الرابط", u); }); };
  var ns = $("#nshare"); if (ns) ns.onclick = function(){ var u = location.href.split("#")[0]; if (navigator.share) navigator.share({ title:document.title, url:u }).catch(function(){}); else if (cl) cl.click(); };
  var sp = $("#secpick"), spl = $("#secpicks");
  if (sp) sp.onclick = function(){
    if (!spl.hidden){ spl.hidden = true; return; }
    var items = $$("[data-open]").map(function(t){ return [t.dataset.open, (t.querySelector(".tt2") || t).textContent.trim()]; });
    $$("[data-pane] section.blk > h2, .daybox > .rail-h h2").forEach(function(h, i){ var s = h.closest("section"); if (!s.closest(".vault")){ s.dataset.pick = "p" + i; items.push(["@p" + i, h.firstChild.textContent.trim()]); } });
    spl.innerHTML = items.length ? items.map(function(x){ return '<button type="button" data-pick="' + x[0] + '">' + R.esc(x[1]) + "</button>"; }).join("") : '<p class="muted small">ما في أقسام في هالصفحة.</p>'; spl.hidden = false;
  };
  if (spl) spl.onclick = function(e){ var b = e.target.closest("button[data-pick]"); if (!b || !window.TifoShare) return; var k = b.dataset.pick, sec;
    if (k.charAt(0) === "@") sec = $('[data-pick="' + k.slice(1) + '"]'); else { var v = node(k); sec = v && v.querySelector("section.blk"); }
    if (!sec) return; var title = b.textContent;
    var lines = $$("li, tbody tr, .th1, .fr, .wt, a.m", sec).slice(0, 8).map(function(e){ return e.textContent.replace(/\s+/g, " ").trim(); }).filter(Boolean);
    if (!lines.length) lines = [sec.textContent.replace(/\s+/g, " ").slice(title.length, title.length + 160)];
    closeAll(); window.TifoShare.card(title, lines); };

  // ---- key art
  var hero = $(".hero"), art = null;
  if (hero && window.TifoArt) (window.requestIdleCallback || function(f){ setTimeout(f, 120); })(function(){   // after first paint: the mosaic never delays the page
    var cv = hero.querySelector("canvas");
    if ((hero.classList.contains("thero") || hero.classList.contains("phero")) && cv){ try { art = window.TifoArt.mount(cv); art.paint(JSON.parse(hero.dataset.art || "[]"), 5); } catch (e){} }
    if (hero.classList.contains("chero") && cv){ try { art = window.TifoArt.mount(cv); art.paint(JSON.parse(hero.dataset.art || "[]"), 11); } catch (e){} }
    if (hero.classList.contains("mhero")){ try { var ms = JSON.parse($("#msum").textContent); art = window.TifoArt.mount(cv); art.set(ms); } catch (e){} }
  }, { timeout:700 });
  // parallax + fade: the art drifts at 0.35x scroll, the title fades as it leaves
  var hin = hero && hero.querySelector(".hero-in"), ticking = false;
  window.addEventListener("scroll", function(){ onScroll(); if (RM || !hero || ticking) return; ticking = true; requestAnimationFrame(function(){ ticking = false; var y = window.scrollY, h = hero.offsetHeight; if (y > h * 1.2) return;
    var c = hero.querySelector("canvas, .lgart, .lgwall"); if (c) c.style.transform = "translate3d(0," + (y * 0.35).toFixed(1) + "px,0)"; if (hin) hin.style.opacity = Math.max(0, 1 - y / (h * 0.85)).toFixed(3); }); }, { passive:true });

  // depth: the league logo leans a few px toward the pointer (desktop only)
  var lg = $(".lglogo"); if (lg && !RM && matchMedia("(pointer:fine)").matches) hero.addEventListener("pointermove", function(e){ var r = hero.getBoundingClientRect(), x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5; lg.style.transform = "translate3d(" + (x * -14).toFixed(1) + "px," + (y * -10).toFixed(1) + "px,0) rotateY(" + (x * 8).toFixed(1) + "deg)"; });
  // ---- match: sticky mini score once the hero leaves; updated from app.js's poll
  var mini = $("#mini");
  function miniDraw(m){ if (!mini || !m) return; var live = R.isLive(m), s = m.score;
    mini.firstElementChild.innerHTML = '<span class="mt">' + R.logo(m.home, "sm") + "<b>" + R.tname(m.home) + '</b></span><span class="ms' + (live ? " live" : "") + '">' + (s ? '<b class="dg">' + s.home + " - " + s.away + "</b>" : '<b class="dg">' + R.tt(m.kickoff_uae) + "</b>") + "<small>" + (live ? R.minute(m) : m.status === "scheduled" ? R.td(m.kickoff_uae) : R.statusText(m)) + '</small></span><span class="mt a"><b>' + R.tname(m.away) + "</b>" + R.logo(m.away, "sm") + '</span>' + (PAGE === "match" ? '<button type="button" class="ib" data-cine aria-label="وضع السينما"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="12"/><path d="M8 21h8"/></svg></button>' : "") + '<button type="button" class="ib" data-sheet="share" aria-label="شارك"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 8l5-5 5 5M5 13v8h14v-8"/></svg></button>'; R.localize(mini); }
  if (mini){ try { miniDraw(JSON.parse($("#msum").textContent)); } catch (e){}
    if ("IntersectionObserver" in window){ var mh = $("#mh"); new IntersectionObserver(function(es){ var on = !es[0].isIntersecting && es[0].boundingClientRect.top < 0; B.classList.toggle("mini-on", on); mini.setAttribute("aria-hidden", !on); }, { threshold:0 }).observe(mh); } }
  document.addEventListener("tifo:match", function(e){ var md = e.detail; if (R.arNames) R.arNames(md); miniDraw(md); if (art) art.set(md);
    if (md.status !== "scheduled"){ var st2 = $('.mtabs [data-t="stats"]'); if (st2) st2.hidden = false; var evb = $("#events"); if (evb) evb.hidden = false;
      var t = $('.mtabs [data-t="events"]'); if (t) t.textContent = "الأحداث"; var g = $('.hero-acts [data-go="events"]'); if (g){ g.dataset.go = "lineups"; g.href = "#lineups"; g.textContent = "التشكيلة"; } } });

  // ---- home: rails from the same day data app.js just fetched
  var RS = {}, JUST = {};
  document.addEventListener("tifo:day", function(e){
    var d = e.detail; R._idx = d.idx; if (d.off !== 0) return;
    var mine = null; try { mine = +localStorage.getItem("tifo.mine") || null; } catch (x){}
    var all = d.ms, ids = {}; all.forEach(function(m){ ids[m.id] = 1; }); var f0 = R.featured(all), r = R.homeRails(all.concat(((d.live || {}).matches || []).filter(function(m){ return !ids[m.id]; })), d.idx, { mine:mine, exclude:f0 && f0.id });
    [["r-live", r.live], ["r-today", r.today], ["r-arab", r.arab]].forEach(function(x){ var s = document.getElementById(x[0]); if (!s) return; var box = s.querySelector(".rail-s"); if (box.innerHTML !== x[1]){ box.innerHTML = x[1]; R.localize(box); } s.hidden = !x[1]; });
    // W3.3: a card whose score just rose keeps a top edge in the scorer's colour for 60 s, and its digits flap once
    var now = Date.now(); all.forEach(function(m){ if (!m.score) return; var p = RS[m.id]; RS[m.id] = { home:m.score.home, away:m.score.away };
      if (p && (m.score.home > p.home || m.score.away > p.away)){ JUST[m.id] = { until:now + 60e3, col:R.colOn((m.score.home > p.home ? m.home : m.away).id), flap:1 }; } });
    Object.keys(JUST).forEach(function(id){ var j = JUST[id]; if (j.until < now){ delete JUST[id]; return; } $$('.rc[data-mid="' + id + '"], #day .m[data-mid="' + id + '"]').forEach(function(c){ c.classList.add("just"); c.style.setProperty("--jc", j.col); if (j.flap){ var dg = c.querySelector(".dg, .chip"); if (dg){ dg.classList.remove("flap"); void dg.offsetWidth; dg.classList.add("flap"); } } }); j.flap = 0; });
    var f = R.featured(all), go = $("#herogo"); if (f && go){ go.href = (R.isProto("/m/" + f.id + "/") ? "/next" : "") + "/m/" + f.id + "/"; }
    setTimeout(function(){ var k = $("#standkick"); if (k && f && mine && (f.home.id === mine || f.away.id === mine) && !R.isLive(f)) k.textContent = "فريقك · " + R.kick(f); else if (k && f) k.textContent = R.kick(f); }, 0);
    fold();
  });
  // the day list: 4 competitions, then «كل المباريات»
  var dayEl = $("#day"), unf = $("#unfold");
  function fold(){ if (!dayEl || !unf) return; var n = dayEl.querySelectorAll(".comp-block").length; unf.hidden = n <= 4 || !dayEl.classList.contains("fold"); }
  if (unf) unf.onclick = function(){ dayEl.classList.remove("fold"); fold(); };
  fold();
  // one segmented control for the day filter: الكل · العرب · المجاني في بلدك (app.js owns the two toggles)
  var sa = $("#segall"), ab = $("#arabonly"), fb = $("#freeonly");
  function segSync(){ if (!sa) return; setTimeout(function(){ sa.setAttribute("aria-pressed", !(ab.getAttribute("aria-pressed") === "true" || fb.getAttribute("aria-pressed") === "true")); }, 0); }
  if (sa){
    ab.addEventListener("click", function(){ if (fb.getAttribute("aria-pressed") === "true") fb.click(); }, true);
    fb.addEventListener("click", function(){ if (ab.getAttribute("aria-pressed") === "true") ab.click(); }, true);
    [ab, fb].forEach(function(b){ b.addEventListener("click", segSync); });
    sa.onclick = function(){ if (ab.getAttribute("aria-pressed") === "true") ab.click(); if (fb.getAttribute("aria-pressed") === "true") fb.click(); segSync(); };
    segSync();
  }

  // ---- rails: arrows from 880px (native scroll otherwise); sections fade up once
  $$(".rail-s").forEach(function(s){ var w = document.createElement("div"); w.className = "rail-a"; w.innerHTML = '<button type="button" aria-label="اللي قبل">›</button><button type="button" aria-label="اللي بعد">‹</button>';
    w.onclick = function(e){ var b = e.target.closest("button"); if (!b) return; var dir = b === w.firstChild ? 1 : -1; s.scrollBy({ left:dir * s.clientWidth * 0.85, behavior:RM ? "auto" : "smooth" });   /* RTL: "next" moves left */ };
    s.parentNode.querySelector(".rail-h").appendChild(w); });
  if (!RM && "IntersectionObserver" in window){ var io = new IntersectionObserver(function(es){ es.forEach(function(e){ if (e.isIntersecting){ e.target.classList.add("in"); io.unobserve(e.target); } }); }, { rootMargin:"0px 0px -8% 0px" });
    $$(".rail, .daybox, .shelf3, [data-pane] > section.blk").forEach(function(el){ if (el.getBoundingClientRect().top < window.innerHeight) return; el.classList.add("fx"); io.observe(el); }); }

  // 356: crest view-transition names are emitted by the renderers (v3.js), so a live re-render keeps them
  // 388: one match in the home hero — while the hero match is live, the national countdown leaves the hero for its rail card
  function cdPlace(){ var cd = $("#uaecd"), hero = $("#stand"); if (!cd || !hero) return; var f = R._idx && window.__feat, live = f && R.isLive(f);
    var a = cd.querySelector("a.cd"), mid = a && (a.getAttribute("href").match(/\/m\/(\d+)\//) || [])[1];
    // the hero keeps the countdown's reserved line either way (visibility, not display), so nothing below moves
    if (!live){ if (!hero.contains(cd)){ var acts = hero.querySelector(".hero-acts"), ph0 = hero.querySelector(".cdph"); acts.parentNode.insertBefore(cd, acts); if (ph0) ph0.remove(); } cd.hidden = false; cd.style.visibility = ""; return; }
    if (mid && f && String(f.id) === mid){ cd.style.visibility = "hidden"; return; }
    var card = mid && $('.rc[data-mid="' + mid + '"]'); if (card){ if (!card.contains(cd)){ if (hero.contains(cd) && !hero.querySelector(".cdph")){ var ph = document.createElement("div"); ph.className = "cdph"; cd.parentNode.insertBefore(ph, cd); } card.appendChild(cd); } cd.hidden = false; cd.style.visibility = ""; } else cd.style.visibility = "hidden"; }
  document.addEventListener("tifo:day", function(e){ if (e.detail.off === 0){ window.__feat = R.featured(e.detail.ms); setTimeout(cdPlace, 0); } });
  if ($("#uaecd") && "MutationObserver" in window) new MutationObserver(function(){ cdPlace(); }).observe($("#uaecd"), { childList:true });
  // 403: «فريقك» empty state — a crest grid of the visitor's country's clubs; a tap makes it your team
  var mineBox = $("#mine");
  function mineEmpty(){ if (!mineBox || !B.dataset.cc || mineBox.querySelector(".favrow") || mineBox.querySelector(".mgrid")) return; if (!mineBox.querySelector(".mine-card")) return;
    var cc = lsGet("tifo.country"); if (!cc){ try { var tz = Intl.DateTimeFormat().resolvedOptions().timeZone, hit = R.COUNTRIES.filter(function(c){ return c[2] === tz; })[0]; cc = hit ? hit[0] : "AE"; } catch (e){ cc = "AE"; } } if (cc === "xx") cc = "AE";
    fetch("/assets/cc." + B.dataset.cc + ".json").then(function(r){ return r.json(); }).then(function(m){ var list = m[cc] || m.AE || []; if (!list.length) return;
      var g = document.createElement("div"); g.className = "mgrid"; g.innerHTML = list.map(function(t){ return '<button type="button" data-t="' + t[0] + '" data-n="' + R.esc(t[1]) + '">' + R.logo({ id:t[0] }, "md") + "<span>" + R.esc(t[1]) + "</span></button>"; }).join("");
      g.onclick = function(e){ var b = e.target.closest("button[data-t]"); if (!b) return; var id = +b.dataset.t, n = b.dataset.n; var f = []; try { f = JSON.parse(localStorage.getItem("tifo.favs") || "[]"); } catch (x){}
        if (!f.some(function(x){ return x.t === "team" && x.id === id; })) f.unshift({ t:"team", id:id, n:n }); lsSet("tifo.favs", JSON.stringify(f)); lsSet("tifo.mine", String(id)); lsSet("tifo.mine.name", n); location.reload(); };
      var p = mineBox.querySelector(".mine-card > p"); if (p) p.textContent = "اختار فريقك، ومبارياته تطلع لك هني أول شي."; mineBox.querySelector(".mine-card").appendChild(g); }).catch(function(){}); }
  if (mineBox && "MutationObserver" in window) new MutationObserver(mineEmpty).observe(mineBox, { childList:true });
  // W1.1e: a page older than 2 minutes dims its live digits and says when it was built, until the first good poll
  (function(){ var H = document.documentElement; if (!H.classList.contains("stale")) return; var hin = $(".hero-in"); if (!hin) return;
    var n = document.createElement("p"); n.className = "stalen"; n.textContent = "آخر تحديث " + new Date(H.dataset.built).toLocaleTimeString("ar-AE-u-nu-latn", { hour:"2-digit", minute:"2-digit", timeZone:"Asia/Dubai" }); hin.appendChild(n);
    document.addEventListener("tifo:fresh", function(){ n.remove(); }, { once:true }); })();
  // W1.10: a cookieless visit ping (path, country, how long since the last visit on this phone); a 404 until the cards Lambda is redeployed is fine
  (function(){ try { var last = +localStorage.getItem("tifo.seen") || 0, now = Date.now(), d = (now - last) / 864e5, ret = !last ? "first" : new Date(last).toDateString() === new Date(now).toDateString() ? "same_day" : d <= 7 ? "d1_7" : "d8p";   // the cards API's buckets
    localStorage.setItem("tifo.seen", now); localStorage.setItem("tifo.ret", ret); if (ret === "first") try { sessionStorage.setItem("tifo.first", "1"); } catch (e){} fetch("/api/tifo/hit", { method:"POST", keepalive:true, headers:{ "content-type":"application/json" }, body:JSON.stringify({ path:location.pathname, country:localStorage.getItem("tifo.country") || "", ret:ret }) }).catch(function(){}); } catch (e){} })();
  // W2.4 country engine (client): the visitor's country first in the crest grid and /competitions/, and المزيد's shortcuts become
  // «دوري بلدك · منتخب بلدك · البطولة الشغالة»
  (function(){ var cc = lsGet("tifo.country"); if (!cc){ try { var tz = Intl.DateTimeFormat().resolvedOptions().timeZone, hit = R.COUNTRIES.filter(function(c){ return c[2] === tz; })[0]; cc = hit ? hit[0] : ""; } catch (e){} }
    if (!cc || cc === "xx") return;
    $$(".cts, main .body").forEach(function(box){ var kids = [].slice.call(box.children).filter(function(k){ return k.dataset && k.dataset.iso === cc; }); for (var i = kids.length - 1; i >= 0; i--) box.insertBefore(kids[i], box.firstChild); });
    /* W2.8: المزيد has fixed entries now; «منتخبك» lives on /national/ and the country's league leads /competitions/ */ })();
  // W2.6: a new event flashes chalk once; the bars get out of the way on a phone (top slides up under the mini-bar, bottom bar hides on scroll-down)
  var seenEv = null;
  document.addEventListener("tifo:match", function(){ var lis = $$("#events li[data-eid]"), ids = lis.map(function(l){ return l.dataset.eid; });
    if (seenEv) lis.forEach(function(l){ if (l.dataset.eid && seenEv.indexOf(l.dataset.eid) < 0 && !RM) l.classList.add("fresh"); }); seenEv = ids; });
  var lastY = window.scrollY; window.addEventListener("scroll", function(){ var y = window.scrollY; if (Math.abs(y - lastY) > 8){ B.classList.toggle("scdown", y > lastY && y > 200); lastY = y; } }, { passive:true });
  // live clock: every ticking minute on the page moves each second (data from the last poll, no extra requests)
  setInterval(function(){ $$(".lmin[data-ps]").forEach(function(el){ var v = R.clock(el.dataset.ps, el.dataset.pb, el.dataset.pl); if (el.textContent !== v) el.textContent = v; }); }, 1000);
  // W3.4: channels for the visitor's country (the prerender shows the UAE's)
  (function(){ var cc = lsGet("tifo.country"); if (!cc){ try { var tz = Intl.DateTimeFormat().resolvedOptions().timeZone, hit = R.COUNTRIES.filter(function(c){ return c[2] === tz; })[0]; cc = hit ? hit[0] : ""; } catch (e){} }
    if (!cc || cc === "AE" || cc === "xx" || !B.dataset.bc) return;
    fetch("/assets/bc." + B.dataset.bc + ".json").then(function(r){ return r.json(); }).then(function(bc){ var m = bc[cc] || {}, map = {}; Object.keys(m).forEach(function(k){ var e = m[k]; if (e && e.b && e.b.length) map[k] = [e.b[0][0], e.b.some(function(x){ return x[1]; }) ? 1 : 0]; }); R.CHN = map;
      $$(".chn[data-comp]").forEach(function(el){ var c = map[el.dataset.comp]; if (!c){ el.remove(); return; } el.innerHTML = R.esc(c[0]) + (c[1] ? " <b>مجاني</b>" : ""); }); }).catch(function(){}); })();
  // W3.5: prayer during a match, in the visitor's city: «العشاء في الرياض 19:52 · حوالي الدقيقة 20» (hero + before kickoff)
  var CITY = { AE:[["أبوظبي", 24.4539, 54.3773], ["دبي", 25.2048, 55.2708], ["العين", 24.2075, 55.7447]], SA:[["الرياض", 24.7136, 46.6753], ["جدة", 21.4858, 39.1925], ["مكة", 21.3891, 39.8579], ["الدمام", 26.4207, 50.0888]], EG:[["القاهرة", 30.0444, 31.2357], ["الإسكندرية", 31.2001, 29.9187]],
    MA:[["الرباط", 34.0209, -6.8416], ["الدار البيضاء", 33.5731, -7.5898]], DZ:[["الجزائر", 36.7538, 3.0588], ["وهران", 35.6971, -0.6308], ["قسنطينة", 36.365, 6.6147]], TN:[["تونس", 36.8065, 10.1815]], IQ:[["بغداد", 33.3152, 44.3661], ["البصرة", 30.5085, 47.7804], ["أربيل", 36.1911, 44.0092]],
    JO:[["عمّان", 31.9454, 35.9284]], KW:[["الكويت", 29.3759, 47.9774]], QA:[["الدوحة", 25.2854, 51.531]], BH:[["المنامة", 26.2285, 50.586]], OM:[["مسقط", 23.588, 58.3829]], LB:[["بيروت", 33.8938, 35.5018]], SY:[["دمشق", 33.5138, 36.2765]], PS:[["القدس", 31.7683, 35.2137]],
    YE:[["صنعاء", 15.3694, 44.191]], LY:[["طرابلس", 32.8872, 13.1913], ["بنغازي", 32.1167, 20.0667]], SD:[["الخرطوم", 15.5007, 32.5599], ["بورتسودان", 19.6158, 37.2164]], MR:[["نواكشوط", 18.0735, -15.9582]], SO:[["مقديشو", 2.0469, 45.3182]], DJ:[["جيبوتي", 11.5721, 43.1456]], KM:[["موروني", -11.7172, 43.2473]] };
  var METH = { AE:[18.2, 18.2], SA:[18.5, "90"], QA:[18, "90"], KW:[18, 17.5], BH:[18.5, 18], OM:[18, 18], EG:[19.5, 17.5], MA:[19, 17], DZ:[18, 17], TN:[18, 18], JO:[18, 18] };
  function prayerTimes(lat, lon, ymd, tzName){ var d2r = Math.PI / 180, p = ymd.split("-").map(Number), jd = Date.UTC(p[0], p[1] - 1, p[2], 12) / 864e5 + 2440587.5, D = jd - 2451545;
    var fa = function(a){ return a - 360 * Math.floor(a / 360); }, g = fa(357.529 + 0.98560028 * D) * d2r, q = fa(280.459 + 0.98564736 * D), L = fa(q + 1.915 * Math.sin(g) + 0.02 * Math.sin(2 * g)) * d2r, e = (23.439 - 0.00000036 * D) * d2r;
    var RA = Math.atan2(Math.cos(e) * Math.sin(L), Math.cos(L)) / d2r / 15, dec = Math.asin(Math.sin(e) * Math.sin(L)), fx = function(h){ h = h - 24 * Math.floor(h / 24); return h; }, EqT = q / 15 - fx(RA);
    if (EqT > 12) EqT -= 24; else if (EqT < -12) EqT += 24;   // q and RA sit either side of 0h near the equinox
    var off = (function(){ var t = new Date(Date.UTC(p[0], p[1] - 1, p[2], 12)); var s = t.toLocaleString("en-US", { timeZone:tzName, hour12:false, hour:"2-digit", minute:"2-digit" }).split(":"); return ((+s[0] % 24) * 60 + +s[1] - 12 * 60) / 60; })();
    var noon = 12 + off - lon / 15 - EqT, la = lat * d2r, T = function(a){ return Math.acos((-Math.sin(a * d2r) - Math.sin(dec) * Math.sin(la)) / (Math.cos(dec) * Math.cos(la))) / d2r / 15; };
    var asrA = Math.atan(1 / (1 + Math.tan(Math.abs(la - dec)))), asr = noon + Math.acos((Math.sin(asrA) - Math.sin(dec) * Math.sin(la)) / (Math.cos(dec) * Math.cos(la))) / d2r / 15;
    return { off:off, t:{ fajr:noon - T(18), dhuhr:noon + 0.05, asr:asr, maghrib:noon + T(0.833), isha:noon + T(17) }, noon:noon, T:T }; }
  function prayLine(m){ if (!m || !m.kickoff_utc || m.time_tbd || !(m.status === "scheduled" || R.isLive(m))) return "";
    var cc = lsGet("tifo.country"); if (!cc){ try { var tz = Intl.DateTimeFormat().resolvedOptions().timeZone, hit = R.COUNTRIES.filter(function(c){ return c[2] === tz; })[0]; cc = hit ? hit[0] : "AE"; } catch (e){ cc = "AE"; } } if (cc === "xx") cc = "AE";
    var row = R.COUNTRIES.filter(function(c){ return c[0] === cc; })[0], list = CITY[cc]; if (!row || !list) return ""; var ci = list.filter(function(c){ return c[0] === lsGet("tifo.city"); })[0] || list[0];
    var ko = Date.parse(m.kickoff_utc), ymd = new Date(ko).toLocaleDateString("en-CA", { timeZone:row[2] }), P = prayerTimes(ci[1], ci[2], ymd, row[2]), me = METH[cc] || [18, 17];
    var t = P.t; t.fajr = P.noon - P.T(me[0]); t.isha = me[1] === "90" ? t.maghrib + 1.5 : P.noon + P.T(me[1]);
    if (cc === "AE"){ t.asr += 2 / 60; t.maghrib += 4 / 60; t.isha += 1 / 60; }   // the UAE Awqaf offsets elyoxe.com/tools and compute/prayer.py use
    var AR = { fajr:"الفجر", dhuhr:"الظهر", asr:"العصر", maghrib:"المغرب", isha:"العشاء" }, base = Date.UTC.apply(null, ymd.split("-").map(function(v, i){ return i === 1 ? +v - 1 : +v; }));
    for (var k in t){ var at = base + (t[k] - P.off) * 36e5, mn = (at - ko) / 6e4; if (mn >= -5 && mn <= 115){ var hh = new Date(at + 30e3).toLocaleTimeString("en-GB", { timeZone:row[2], hour:"2-digit", minute:"2-digit", hour12:false });
      var when = mn < 0 ? "قبل البداية" : mn < 48 ? "حوالي الدقيقة " + Math.max(1, Math.round(mn)) : mn < 63 ? "بين الشوطين" : "حوالي الدقيقة " + Math.min(90, Math.round(45 + mn - 63));
      return AR[k] + " في " + ci[0] + " " + hh + " · " + when; } } return ""; }
  (function(){ if (PAGE !== "match") return; var m0; try { m0 = JSON.parse($("#msum").textContent); } catch (e){ return; } var line = prayLine(m0); if (!line) return;
    var slot = $("#prayl"); if (slot) slot.textContent = line; else { var hin = $(".mhero .hero-in"); if (hin){ var p = document.createElement("p"); p.className = "prayl"; p.textContent = line; hin.insertBefore(p, hin.querySelector(".hero-acts")); } }
    var ww = $("#wwbox"); if (ww && m0.status === "scheduled"){ var p2 = document.createElement("p"); p2.className = "prayl in"; p2.textContent = line; ww.parentNode.insertBefore(p2, ww.nextSibling); } })();
  // the city choice for countries whose capital can be half an hour off (in المزيد)
  (function(){ var cc = lsGet("tifo.country"); if (!cc){ try { var tz = Intl.DateTimeFormat().resolvedOptions().timeZone, hit = R.COUNTRIES.filter(function(c){ return c[2] === tz; })[0]; cc = hit ? hit[0] : ""; } catch (e){} }
    var list = CITY[cc], ms = $("#more .mswitch") || $("#more .mset"); if (!list || list.length < 2 || !ms) return; var sel = document.createElement("select"); sel.id = "prcity"; sel.setAttribute("aria-label", "مدينتك لأوقات الصلاة");
    sel.innerHTML = list.map(function(c){ return '<option value="' + c[0] + '"' + (c[0] === lsGet("tifo.city") ? " selected" : "") + ">" + c[0] + "</option>"; }).join(""); sel.onchange = function(){ lsSet("tifo.city", sel.value); }; ms.appendChild(sel); })();
  // W2.7: the team hero's next match counts down, then says it's on
  (function(){ var ko = $$(".tnm [data-ko]"); if (!ko.length) return;   /* only the team hero's digits: #kitct on /m/<id>/kit/ also carries data-ko */ var t = setInterval(function(){ ko.forEach(function(el){ var d = Date.parse(el.dataset.ko) - Date.now(); if (!isFinite(d)) return;
    if (d <= 0){ el.textContent = "المباراة"; return; } if (d > 36e5 * 48) return; var hh = Math.floor(d / 36e5), mm = Math.floor(d / 6e4) % 60, ss = Math.floor(d / 1e3) % 60, p2 = function(n){ return n < 10 ? "0" + n : n; }; el.textContent = hh + ":" + p2(mm) + ":" + p2(ss); }); }, 1000); })();
  // ================= owner items (2026-09-27): 355 goal moment · 357 match-state hero · 359 cinema · 360 goal sound ·
  // 370 live «لو خلصت الحين» · 373 player card · 376 lineup builder · 379 embed. Everything lives in the sheet, a tab or the hero.
  function lsGet(k){ try { return localStorage.getItem(k); } catch (e){ return null; } }
  function lsSet(k, v){ try { if (v) localStorage.setItem(k, v); else localStorage.removeItem(k); } catch (e){} }
  // 360: goal sound, OFF by default; a short synthesized whistle (no audio file), toggled in المزيد
  var snd = $("#goalsnd"); if (snd){ snd.setAttribute("aria-pressed", lsGet("tifo.goalsnd") === "1"); snd.onclick = function(){ var on = lsGet("tifo.goalsnd") !== "1"; lsSet("tifo.goalsnd", on ? "1" : ""); snd.setAttribute("aria-pressed", on); if (on) whistle(); }; }
  var AC = null;
  // W1.1h: browsers start audio suspended; the first tap wakes it when the goal sound is on
  document.addEventListener("pointerdown", function(){ if (lsGet("tifo.goalsnd") !== "1") return; try { AC = AC || new (window.AudioContext || window.webkitAudioContext)(); if (AC.state === "suspended") AC.resume(); } catch (e){} }, { once:true, passive:true });
  function whistle(){ if (lsGet("tifo.goalsnd") !== "1") return; try { AC = AC || new (window.AudioContext || window.webkitAudioContext)(); var t = AC.currentTime;
    [0, 0.32].forEach(function(d, i){ var o = AC.createOscillator(), g = AC.createGain(), lfo = AC.createOscillator(), lg = AC.createGain(); o.type = "sine"; o.frequency.value = i ? 2350 : 2150; lfo.frequency.value = 38; lg.gain.value = 90; lfo.connect(lg); lg.connect(o.frequency);
      g.gain.setValueAtTime(0, t + d); g.gain.linearRampToValueAtTime(0.18, t + d + 0.02); g.gain.setValueAtTime(0.18, t + d + (i ? 0.5 : 0.22)); g.gain.linearRampToValueAtTime(0, t + d + (i ? 0.56 : 0.26));
      o.connect(g); g.connect(AC.destination); o.start(t + d); lfo.start(t + d); o.stop(t + d + 0.6); lfo.stop(t + d + 0.6); }); } catch (e){} }
  // 355: goal moment — the scoring side's colour flashes, the scorer sweeps across, the score flips like an airport board
  // W3.2 the card-stunt goal: the stand flips from the scorer's side into his colour and spells the score; «هدف» and the scorer slide
  // in from his side. Hero off screen: the mini-bar takes a 1.2 s club stripe. A goal against my team: only the quiet flap.
  // W3.3: in every case only the changed digits flap.
  function flapCells(prev, md){ if (!md.score) return; var nw = String(md.score.home) + String(md.score.away), old = prev ? String(prev.home) + String(prev.away) : "";
    $$("#mh .sc .dg, .hsc .dg, #mini .ms .dg, .cine .cs").forEach(function(box){ var cs = box.querySelectorAll(".cell"); if (!cs.length){ box.classList.remove("flap"); void box.offsetWidth; box.classList.add("flap"); return; }
      [].forEach.call(cs, function(c, i){ if (old[i] !== nw[i]){ c.classList.remove("flap"); void c.offsetWidth; c.classList.add("flap"); } }); }); }
  // W4.6: one polite live region speaks goals and full time only (never the minute)
  function say(t){ var a = $("#alive"); if (!a || B.classList.contains("nospoil")) return; a.textContent = ""; setTimeout(function(){ a.textContent = t; }, 60); }
  function goalMoment(md, side, prev, undone){
    var tm = md[side], ev = (md.events || []).filter(function(e){ return /goal/.test(e.type) && e.team === side; }).pop(), who = ev && ev.player ? ev.player.name : "";
    if (md.score) say((undone ? "انلغى هدف " + (tm.name_ar || tm.name) : "هدف لـ" + (tm.name_ar || tm.name) + (who ? "، " + who : "")) + ". " + (md.home.name_ar || md.home.name) + " " + md.score.home + "، " + (md.away.name_ar || md.away.name) + " " + md.score.away);
    flapCells(prev, md); if (RM) return;
    var mine = +lsGet("tifo.mine") || null, against = mine && (md.home.id === mine || md.away.id === mine) && tm.id !== mine;
    if (against && !undone) return;   // a goal against my team: the flap only
    var hero = $(".hero"), r = hero && hero.getBoundingClientRect(), inView = r && r.bottom > 80 && r.top < innerHeight, cv = hero && hero.querySelector("canvas"), a = cv && window.TifoArt && window.TifoArt.of(cv);
    if (PAGE === "home" && !inView) return;
    if (inView && hero){ if (a && !undone && md.score) a.stunt(side === "home", R.colOn(tm.id), md.score.away + "-" + md.score.home);
      var gt = document.createElement("div"); gt.className = "gtext " + (side === "home" ? "fr" : "fl") + (mine && tm.id === mine ? " mine" : ""); gt.innerHTML = undone ? "<b>انلغى الهدف</b>" : "<b>هدف</b><span>" + R.esc(who || "") + (who ? " · " : "") + R.tname(tm) + "</span>"; hero.appendChild(gt); setTimeout(function(){ gt.remove(); }, 2300); }
    else { var mb = $("#mini"); if (mb && B.classList.contains("mini-on")){ mb.style.setProperty("--gc", R.colOn(tm.id)); mb.classList.remove("gstripe"); void mb.offsetWidth; mb.classList.add("gstripe"); setTimeout(function(){ mb.classList.remove("gstripe"); }, 1300); } }
    if (!undone) whistle();
  }
  var lastScore = {}, lastSt = {};
  function scoreWatch(md){ if (!md || !md.score) return; var k = md.id, p = lastScore[k]; lastScore[k] = { home:md.score.home, away:md.score.away };
    if (lastSt[k] && lastSt[k] !== "finished" && md.status === "finished") say("انتهت. " + (md.home.name_ar || md.home.name) + " " + md.score.home + "، " + (md.away.name_ar || md.away.name) + " " + md.score.away); lastSt[k] = md.status;
    if (p && (md.score.home > p.home || md.score.away > p.away)) goalMoment(md, md.score.home > p.home ? "home" : "away", p);
    else if (p && (md.score.home < p.home || md.score.away < p.away)) goalMoment(md, md.score.home < p.home ? "home" : "away", p, true);   // a disallowed goal flaps back
    tabTitle(md); }
  // W3.3: while live the tab title carries the score and minute, except in بدون حرق
  var T0 = document.title;
  function tabTitle(md){ if (PAGE !== "match") return; if (!R.isLive(md) || B.classList.contains("nospoil") || !md.score){ document.title = T0; return; }
    var mn = String(md.minute || "").replace(/'/g, ""); document.title = md.score.home + "-" + md.score.away + (mn ? " · " + (R.periodAr(mn) || mn + "'") : "") + " " + (md.home.name_ar || md.home.name) + " ضد " + (md.away.name_ar || md.away.name); }
  // 357: the match hero follows the state: countdown before kickoff, a soft pulse in play, the final + recap after
  var cdEl = null, cdT = null;
  function heroState(md){ if (!md || PAGE !== "match") return; var st = R.isLive(md) ? "live" : md.status === "finished" ? "final" : md.status === "scheduled" ? "pre" : "other";
    B.dataset.state = st; var box = $("#mh .sc"); if (!box) return;
    if (st === "pre" && md.kickoff_utc && !md.time_tbd){ if (!cdEl || !box.contains(cdEl)){ cdEl = box.querySelector(".mcd"); if (!cdEl){ cdEl = document.createElement("span"); cdEl.className = "mcd"; box.appendChild(cdEl); } }
      var tick = function(){ var d = Date.parse(md.kickoff_utc) - Date.now(); if (d <= 0){ cdEl.textContent = "على وشك تبدا"; return; } var dd = Math.floor(d / 864e5), hh = Math.floor(d / 36e5) % 24, mm = Math.floor(d / 6e4) % 60, ss = Math.floor(d / 1e3) % 60, p2 = function(n){ return n < 10 ? "0" + n : n; };
        cdEl.innerHTML = "تبدا بعد " + '<bdi dir="ltr" class="num">' + (dd ? dd + "d " : "") + p2(hh) + ":" + p2(mm) + ":" + p2(ss) + "</bdi>"; };
      tick(); clearInterval(cdT); cdT = setInterval(tick, 1000); }
    else { clearInterval(cdT); if (cdEl) cdEl.remove(); cdEl = null; }
  }
  // 359: cinema mode — full screen: score, minute and the last event, for a TV or a phone on its side
  var cine = null;
  function cineDraw(md){ if (!cine || !md) return; var live = R.isLive(md), ev = (md.events || []).filter(function(e){ return e.type !== "added_time" && e.type !== "half"; }).pop();
    var last = ev ? '<bdi dir="ltr">' + R.esc(ev.minute) + "'</bdi> " + ({ goal:"هدف", penalty_goal:"هدف من بلنتي", own_goal:"هدف في مرماه", yellow:"إنذار", red:"طرد", second_yellow:"طرد", sub:"تبديل", missed_penalty:"بلنتي ضايع" }[ev.type] || "") + (ev.player ? " · " + R.esc(ev.player.name) : "") : "";
    cine.querySelector(".ci").innerHTML = '<div class="ct3"><span>' + R.logo(md.home, "xl") + "<b>" + R.tname(md.home) + '</b></span><b class="cs dg">' + (md.score ? md.score.home + " - " + md.score.away : R.hhmm(md.kickoff_uae)) + "</b><span>" + R.logo(md.away, "xl") + "<b>" + R.tname(md.away) + '</b></span></div><p class="cm' + (live ? " live" : "") + '">' + (live ? R.minute(md) : R.statusText(md)) + "</p>" + (last ? '<p class="ce">' + last + "</p>" : ""); }
  // W2.8: cinema lives on the mini-bar now (any [data-cine] button opens it)
  document.addEventListener("click", function(e){ if (e.target.closest("[data-cine]")) cineOpen(); });
  function cineOpen(){ closeAll(); cine = document.createElement("div"); cine.className = "cine"; cine.innerHTML = '<button type="button" class="x" aria-label="سكّر">سكّر</button><div class="ci"></div>'; document.body.appendChild(cine);
    var wlock = null; cine.querySelector(".x").onclick = function(){ if (document.fullscreenElement) document.exitFullscreen().catch(function(){}); if (wlock){ wlock.release().catch(function(){}); wlock = null; } cine.remove(); cine = null; };
    try { cineDraw(window.__md || JSON.parse($("#msum").textContent)); } catch (e){} if (cine.requestFullscreen) cine.requestFullscreen().catch(function(){}); if (navigator.wakeLock) navigator.wakeLock.request("screen").then(function(l){ wlock = l; }).catch(function(){}); };
  // 370: «لو خلصت الحين» — while live, the league table with this score, recomputed on every poll (first tab)
  var ST0 = null;
  function liveTable(md){ var box = $("#ltable"); if (!box) return; if (!R.isLive(md)){ box.innerHTML = ""; return; }
    (ST0 ? Promise.resolve(ST0) : fetch("/v1/comp/" + md.comp + "/standings.json").then(function(r){ return r.ok ? r.json() : null; }).then(function(s){ ST0 = s; return s; })).then(function(st){
      if (!st || !st.groups || !st.groups.length) return; var g = st.groups.filter(function(g){ return (g.rows || []).some(function(r){ return r.team.id === md.home.id; }); })[0]; if (!g) return;
      var lt = R.liveTable({ groups:[g] }, [md]), rows = lt.groups[0].rows, ids = [md.home.id, md.away.id], idx = rows.map(function(r, i){ return ids.indexOf(r.team.id) >= 0 ? i : -1; }).filter(function(i){ return i >= 0; });
      var lo = Math.max(0, Math.min.apply(null, idx) - 2), hi = Math.min(rows.length, Math.max.apply(null, idx) + 3);
      box.innerHTML = '<div class="lt"><b>لو خلصت الحين</b><div class="tblwrap"><table class="st"><tbody>' + rows.slice(lo, hi).map(function(r, i){ var hot = ids.indexOf(r.team.id) >= 0; return '<tr class="' + (hot ? "hot" : "") + '"><td class="rk">' + (lo + i + 1) + '</td><td class="tm">' + R.logo(r.team, "sm") + " " + R.tname(r.team) + "</td><td>" + r.played + '</td><td class="pts">' + r.pts + "</td></tr>"; }).join("") + "</tbody></table></div></div>"; }).catch(function(){}); }
  // owner item 6 (rule 12): a live hero takes one breath when a new minute or score arrives
  var lastBeat = "";
  function breathe(md){ if (!md || !R.isLive(md) || RM) return; var k = (md.score ? md.score.home + "-" + md.score.away : "") + "|" + md.minute; if (k === lastBeat) return; var first = !lastBeat; lastBeat = k; if (first) return;
    var s = $(".mhero .scrim"); if (!s) return; s.classList.remove("breathe"); void s.offsetWidth; s.classList.add("breathe"); }
  document.addEventListener("tifo:match", function(e){ var md = e.detail; window.__md = md; scoreWatch(md); heroState(md); cineDraw(md); liveTable(md); breathe(md); });
  // W1.1a: the prerendered summary never seeds the goal detector (opening a page after a goal must not fire «هدف»); the first fresh tifo:match seeds it
  if (PAGE === "match") try { heroState(JSON.parse($("#msum").textContent)); } catch (e){}
  // the home hero's match: a goal there gets the same moment
  document.addEventListener("tifo:day", function(e){ if (e.detail.off !== 0) return; var f = R.featured(e.detail.ms); if (f && R.isLive(f)){ var p = lastScore[f.id]; if (p && f.score && (f.score.home > p.home || f.score.away > p.away)) goalMoment(f, f.score.home > p.home ? "home" : "away", p); if (f.score) lastScore[f.id] = { home:f.score.home, away:f.score.away }; } });

  // 373: a player's match card (rating, minutes, goals, assists, shots, cards) as a shareable Tifo image
  var pcb = $("#pcardbtn"); if (pcb) pcb.onclick = function(){ var md = window.__md; var list = $("#secpicks");
    if (!md || !md.lineups){ try { md = md || JSON.parse($("#msum").textContent); } catch (e){} }
    if (!md || !md.lineups || !md.lineups.home){ list.innerHTML = '<p class="muted small">التشكيلة للحين مب منشورة.</p>'; list.hidden = false; return; }
    var ps = []; ["home", "away"].forEach(function(s){ (md.lineups[s].starters || []).concat(md.lineups[s].subs || []).forEach(function(p){ if (p.rating != null || p.minutes_on != null || (md.lineups[s].starters || []).indexOf(p) >= 0) ps.push([s, p]); }); });
    ps.sort(function(a, b){ return (b[1].rating || 0) - (a[1].rating || 0); });
    list.innerHTML = ps.map(function(x, i){ return '<button type="button" data-pc="' + i + '">' + R.esc(x[1].name) + (x[1].rating != null ? ' <span class="num">' + Number(x[1].rating).toFixed(1) + "</span>" : "") + "</button>"; }).join(""); list.hidden = false;
    list.onclick = function(ev){ var b = ev.target.closest("[data-pc]"); if (!b) return; var x = ps[+b.dataset.pc]; closeAll(); playerCard(md, x[0], x[1]); }; };
  function playerCard(md, side, p){ if (!window.TifoShare) return; var W = 1080, H = 1350, c = document.createElement("canvas"); c.width = W; c.height = H; var x = c.getContext("2d"), tm = md[side];
    var ev = (md.events || []), g = ev.filter(function(e){ return /goal/.test(e.type) && e.type !== "own_goal" && e.player && e.player.id === p.id; }).length, a = ev.filter(function(e){ return e.assist && e.assist.id === p.id; }).length;
    var sh = (md.shotmap || []).filter(function(s){ return s.player_id === p.id || (s.player && s.player.id === p.id); }), cards = ev.filter(function(e){ return e.player && e.player.id === p.id && /yellow|red/.test(e.type); }).length;
    var mins = p.minutes_off != null ? p.minutes_off - (p.minutes_on || 0) : p.minutes_on != null ? 90 - p.minutes_on : 90;
    var col = R.col(tm.id, 0), NIGHT = "#0A2620", CH = "#F6F7F2";
    x.fillStyle = NIGHT; x.fillRect(0, 0, W, H); for (var r = 0; r < 12; r++) for (var q = 0; q < 27; q++){ x.globalAlpha = 0.55 + ((r * 7 + q * 3) % 5) / 12; x.fillStyle = (q + r) % 7 < 2 ? R.col(tm.id, 1) : col; x.fillRect(q * 40, r * 40, 37, 37); } x.globalAlpha = 1;
    var gr = x.createLinearGradient(0, 200, 0, 520); gr.addColorStop(0, "rgba(10,38,32,0)"); gr.addColorStop(1, NIGHT); x.fillStyle = gr; x.fillRect(0, 200, W, 320);
    x.direction = "rtl"; x.textAlign = "center"; x.fillStyle = CH; x.font = '800 76px "Noto Kufi Arabic"'; x.fillText(p.name, W / 2, 610);
    x.font = '400 38px "Readex Pro"'; x.fillStyle = "#B9C7C0"; x.fillText((tm.name_ar || tm.name) + " · " + (md.home.name_ar || md.home.name) + " " + (md.score ? md.score.home + " - " + md.score.away : "") + " " + (md.away.name_ar || md.away.name), W / 2, 680);
    x.font = '700 260px "Barlow Condensed"'; x.fillStyle = CH; x.fillText(p.rating != null ? Number(p.rating).toFixed(1) : "—", W / 2, 950); x.font = '800 36px "Noto Kufi Arabic"'; x.fillStyle = "#B9C7C0"; x.fillText("تقييم المباراة", W / 2, 1010);
    var stats = [["دقيقة", mins], ["أهداف", g], ["صناعة", a], ["تسديد", sh.length], ["كروت", cards]];
    stats.forEach(function(s, i){ var cx = W - 120 - i * 210; x.font = '700 90px "Barlow Condensed"'; x.fillStyle = CH; x.fillText(String(s[1]), cx, 1150); x.font = '400 32px "Readex Pro"'; x.fillStyle = "#B9C7C0"; x.fillText(s[0], cx, 1200); });
    x.font = '700 38px "Barlow Condensed"'; x.textAlign = "left"; x.fillStyle = "#B9C7C0"; x.fillText("tifo.elyoxe.com", 60, H - 60); x.textAlign = "right"; x.font = '800 54px "Noto Kufi Arabic"'; x.fillStyle = CH; x.fillText("تيفو", W - 60, H - 55);
    (document.fonts ? document.fonts.ready : Promise.resolve()).then(function(){ window.TifoShare.out(c, "tifo-" + md.id + "-" + p.id + ".png"); }); }

  // 376 + W3.10: lineup builder on the pitch — 11 squares in the chosen formation; a square opens the squad (numbers; keepers only in goal),
  // the pick is kept on this phone per team, «شارك تشكيلتي» exports the image
  var lb = $("#xibtn"); if (lb) lb.onclick = function(){ closeAll("now"); var pn = $("#panel"); open(pn, lb); $("#panelt").textContent = "سوّ تشكيلتك"; $("#panels").textContent = "";
    var box = $("#panelb"), TID = B.dataset.id, KEY = "tifo.xi." + TID; box.innerHTML = '<p class="muted small">نحمّل اللاعبين…</p>';
    fetch("/v1/team/" + TID + ".json").then(function(r){ return r.json(); }).then(function(t){ var sq = [], by = {}; (t.squad || []).forEach(function(g){ if (g.group !== "coach") (g.players || []).forEach(function(p){ R.arNames && R.arNames({ lineups:{ home:{ starters:[p] } } }); var q = { id:p.id, name:p.name, no:p.number, g:g.group }; sq.push(q); by[p.id] = q; }); });
      var F = { "4-3-3":[1, 4, 3, 3], "4-4-2":[1, 4, 4, 2], "4-2-3-1":[1, 4, 2, 3, 1], "3-5-2":[1, 3, 5, 2] }, cur = "4-3-3", pick = {};
      try { var sv = JSON.parse(localStorage.getItem(KEY) || "null"); if (sv && F[sv.f]){ cur = sv.f; pick = sv.p || {}; } } catch (e){}
      function save(){ try { localStorage.setItem(KEY, JSON.stringify({ f:cur, p:pick })); } catch (e){} }
      function short(n){ var w = String(n || "").trim().split(/\s+/); if (w.length < 2) return w[0] || ""; var j = /^(عبد|أبو|ابو|بن|ابن|آل|دي|دا|فان)$/.test(w[w.length - 2]); return j ? w[w.length - 2] + " " + w[w.length - 1] : w[w.length - 1]; }
      function slots(){ var rows = F[cur], out = [], n = 0; rows.forEach(function(k, ri){ for (var i = 0; i < k; i++) out.push({ r:ri, i:i, k:k, n:n++ }); }); return out; }
      function draw(){ var rows = F[cur], S = slots(), full = S.filter(function(s){ return by[pick[s.n]]; }).length;
        box.innerHTML = '<div class="seg" role="group" aria-label="الخطة">' + Object.keys(F).map(function(f){ return '<button type="button" data-f="' + f + '" aria-pressed="' + (f === cur) + '">' + f + "</button>"; }).join("") + "</div>" +
          '<div class="pitch xpitch" style="--hc:' + R.colOn(+TID) + ";--hi:" + R.inkOn(R.colOn(+TID)) + '"><i class="half"></i><i class="circle"></i><i class="box t"></i><i class="box b"></i>' + S.map(function(s){ var p = by[pick[s.n]], y = 88 - s.r * (76 / (rows.length - 1)), x = (s.i + 1) * 100 / (s.k + 1);
            return '<button type="button" class="pl xs' + (p ? " on" : "") + '" data-s="' + s.n + '" style="left:' + x.toFixed(1) + "%;top:" + y.toFixed(1) + '%" aria-label="' + (p ? R.esc(p.name) : s.r === 0 ? "اختار الحارس" : "اختار لاعب") + '"><b>' + (p ? (p.no != null ? p.no : "•") : "+") + "</b><span>" + (p ? R.esc(short(p.name)) : s.r === 0 ? "الحارس" : "اختار") + "</span></button>"; }).join("") + "</div>" +
          '<p class="small muted xcount">' + full + " من 11</p>" + '<div class="xpick" hidden></div><p><button type="button" class="cta" id="xishare"' + (full ? "" : " disabled") + ">شارك تشكيلتي</button></p>";
        box.querySelector(".seg").onclick = function(e){ var b = e.target.closest("[data-f]"); if (!b) return; var old = slots(); cur = b.dataset.f; var np = {}, gk = pick[0], rest = old.filter(function(s){ return s.r > 0; }).map(function(s){ return pick[s.n]; }).filter(Boolean); if (gk) np[0] = gk; slots().filter(function(s){ return s.r > 0; }).forEach(function(s, i){ if (rest[i]) np[s.n] = rest[i]; }); pick = np; save(); draw(); };
        $$(".xs", box).forEach(function(btn){ btn.onclick = function(){ picker(+btn.dataset.s); }; });
        $("#xishare").onclick = shareXI; }
      function picker(n){ var gk = n === 0, list = sq.filter(function(p){ return gk ? p.g === "keepers" : p.g !== "keepers"; }), where = {}; Object.keys(pick).forEach(function(k){ where[pick[k]] = +k; });
        var pk = $(".xpick", box); pk.hidden = false; pk.innerHTML = '<div class="xp-h"><b>' + (gk ? "اختار الحارس" : "اختار لاعب") + '</b><button type="button" class="x" data-xc>سكّر</button></div>' + (pick[n] ? '<button type="button" class="xp-r" data-rm>شيل اللاعب من المركز</button>' : "") +
          '<ul class="xp-l">' + list.map(function(p){ var at = where[p.id]; return '<li><button type="button" data-p="' + p.id + '"' + (at === n ? ' aria-current="true"' : "") + '><span class="num">' + (p.no != null ? p.no : "") + "</span><span>" + R.esc(p.name) + "</span>" + (at != null && at !== n ? '<small>في التشكيلة</small>' : "") + "</button></li>"; }).join("") + "</ul>";
        pk.onclick = function(e){ if (e.target.closest("[data-xc]")){ pk.hidden = true; return; } if (e.target.closest("[data-rm]")){ delete pick[n]; save(); draw(); return; }
          var b = e.target.closest("[data-p]"); if (!b) return; var id = +b.dataset.p, from = where[id]; if (from != null && from !== n){ if (pick[n]) pick[from] = pick[n]; else delete pick[from]; } pick[n] = id; save(); draw(); };
        var f = pk.querySelector("[data-p]"); if (f) f.focus({ preventScroll:true }); pk.scrollIntoView({ block:"nearest", behavior:RM ? "auto" : "smooth" }); }
      function shareXI(){ var S = slots(), rows = F[cur];
        var W = 1080, H = 1350, c = document.createElement("canvas"); c.width = W; c.height = H; var x = c.getContext("2d"); x.fillStyle = "#0F3A2F"; x.fillRect(0, 0, W, H);
        x.strokeStyle = "rgba(255,255,255,.35)"; x.lineWidth = 4; x.strokeRect(60, 140, W - 120, H - 260); x.beginPath(); x.moveTo(60, H / 2 + 20); x.lineTo(W - 60, H / 2 + 20); x.stroke();
        x.direction = "rtl"; x.textAlign = "center"; x.fillStyle = "#F6F7F2"; x.font = '800 54px "Noto Kufi Arabic"'; x.fillText("تشكيلتي لـ" + (t.name_ar || t.name) + " (" + cur + ")", W / 2, 95);
        S.forEach(function(s){ var p = by[pick[s.n]], y = H - 180 - s.r * ((H - 380) / (rows.length - 1)), xx = 60 + (s.i + 1) * (W - 120) / (s.k + 1); x.fillStyle = R.col(t.id, 0); x.fillRect(xx - 34, y - 34, 68, 68);
          x.fillStyle = R.inkOn ? R.inkOn(R.col(t.id, 0)) : "#F6F7F2"; x.font = '700 34px "Barlow Condensed"'; x.fillText(p && p.no != null ? String(p.no) : "", xx, y + 12); x.fillStyle = "#F6F7F2"; x.font = '600 30px "Readex Pro"'; x.fillText(p ? short(p.name) : "—", xx, y + 72); });
        x.textAlign = "left"; x.fillStyle = "#B9C7C0"; x.font = '700 36px "Barlow Condensed"'; x.fillText("tifo.elyoxe.com", 60, H - 45);
        (document.fonts ? document.fonts.ready : Promise.resolve()).then(function(){ window.TifoShare && window.TifoShare.out(c, "tifo-xi-" + t.id + ".png"); }); }
      draw(); }).catch(function(){ box.innerHTML = '<p class="muted small">ما قدرنا نحمّل اللاعبين.</p>'; }); };

  // 379: embed code for other sites (league table / live match), iframe with a link back to Tifo
  var eb = $("#embedbtn"); if (eb) eb.onclick = function(){ var u = eb.dataset.src, code = '<iframe src="https://tifo.elyoxe.com' + u + '" width="100%" height="' + (eb.dataset.h || 420) + '" style="border:0" loading="lazy" title="تيفو"></iframe>';
    var l = $("#embout") || $("#secpicks"); l.innerHTML = '<p class="small muted">انسخ الكود وحطه في موقعك:</p><textarea class="embc" rows="4" readonly>' + R.esc(code) + '</textarea><button type="button" class="sa" id="embcopy">انسخ الكود</button>'; l.hidden = false;
    $("#embcopy").onclick = function(){ (navigator.clipboard ? navigator.clipboard.writeText(code) : Promise.reject()).then(function(){ $("#embcopy").textContent = "انتسخ ✓"; }, function(){ l.querySelector("textarea").select(); }); }; };


  // ---- W3.6 install: asked only on a 2nd visit or right after «هذا فريقي», never twice in a session, never again for 30 days after «مب الحين»;
  // Android gets the browser's own prompt, iPhone gets the two taps (Safari has no prompt)
  (function(){
    var SA = (window.matchMedia && matchMedia("(display-mode: standalone)").matches) || navigator.standalone; if (SA) return;
    var ios = /iPhone|iPad|iPod/.test(navigator.userAgent) && !window.MSStream, bip = null, go = $("#instgo"), iosl = $("#instios"), mm = $("#instm");
    function can(){ return !!bip || ios; }
    function paint(){ if (go) go.hidden = !bip; if (iosl) iosl.hidden = !ios || !!bip; if (mm) mm.hidden = !can(); }
    function no(){ lsSet("tifo.inst.no", String(Date.now())); var t = $("#instask"); if (t) t.remove(); }
    function ask(force){ var ss = null, first = null; try { ss = sessionStorage.getItem("tifo.inst.asked"); first = sessionStorage.getItem("tifo.first"); } catch (e){} if (!can() || $("#instask") || ss || (first && !force)) return; var n = +lsGet("tifo.inst.no") || 0; if (Date.now() - n < 30 * 864e5) return;
      try { sessionStorage.setItem("tifo.inst.asked", "1"); } catch (e){}
      var t = document.createElement("div"); t.id = "instask"; t.className = "instask"; t.setAttribute("role", "region"); t.setAttribute("aria-label", "تيفو على شاشة جوالك");
      t.innerHTML = '<span>حط تيفو على شاشة جوالك</span><button type="button" class="cta" data-sheet="inst">كيف؟</button><button type="button" class="x" aria-label="مب الحين">مب الحين</button>';
      t.querySelector(".x").onclick = no; t.querySelector(".cta").addEventListener("click", function(){ t.remove(); }); B.appendChild(t); }
    window.addEventListener("beforeinstallprompt", function(e){ e.preventDefault(); bip = e; paint(); if (lsGet("tifo.ret") && lsGet("tifo.ret") !== "first") setTimeout(ask, 15e3); });
    window.addEventListener("appinstalled", function(){ bip = null; no(); paint(); });
    if (go) go.onclick = function(){ if (!bip) return; bip.prompt(); (bip.userChoice || Promise.resolve({})).then(function(c){ if (c.outcome === "accepted") no(); closeAll(); }); bip = null; paint(); };
    paint(); if (ios && lsGet("tifo.ret") && lsGet("tifo.ret") !== "first") setTimeout(ask, 15e3);
    var mb = $("#mybtn"); if (mb) mb.addEventListener("click", function(){ setTimeout(function(){ if (mb.classList.contains("on") && !("PushManager" in window && "serviceWorker" in navigator)) ask(true); }, 600);   /* where push works, «هذا فريقي» offers the alerts sheet instead */ });
  })();

  // ---- W3.6 offline: the worker serves this page when a page you never opened can't load; it lists what this phone keeps
  if (PAGE === "offline"){ (function(){ var ul = $("#offl"); if (!ul) return;
    window.addEventListener("online", function(){ location.reload(); });
    if (!window.caches){ ul.innerHTML = '<li class="muted">ما في صفحات محفوظة.</li>'; return; }
    caches.open("tifo-pages").then(function(c){ return c.keys().then(function(ks){ return Promise.all(ks.reverse().slice(0, 40).map(function(k){ return c.match(k).then(function(r){ return r.text(); }).then(function(h){ var p = new URL(k.url).pathname, tt = (h.match(/<title>([^<]*)<\/title>/) || [])[1] || p; return { p:p, t:tt.replace(/\s*\|\s*تيفو\s*$/, "").replace(/&amp;/g, "&"), m:/^\/m\/\d+\//.test(p) }; }); })); }); })
      .then(function(L){ L = L.filter(function(x){ return x.p !== "/offline/"; }).sort(function(a, b){ return b.m - a.m; });
        ul.innerHTML = L.length ? L.map(function(x){ return '<li><a href="' + R.esc(x.p) + '">' + R.esc(x.t) + "</a></li>"; }).join("") : '<li class="muted">ما في صفحات محفوظة للحين. افتح مبارياتك وأنت على النت وبتحصلها هني.</li>'; })
      .catch(function(){ ul.innerHTML = '<li class="muted">ما قدرنا نقرا المحفوظ.</li>'; }); })(); }

  // ---- W4.1 /thisday/: today in the visitor's own time zone, أمس/بكرة step one calendar day, the folded days are the source
  (function(){ var box = $("#tdnow"); if (!box) return; var MON = ["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"];
    var today = new Date().toLocaleDateString("en-CA").slice(5), cur = today, body = $("#tdb"), head = $("#tdh");
    function step(md, d){ var t = new Date(Date.UTC(2024, +md.slice(0, 2) - 1, +md.slice(3) + d)); return ("0" + (t.getUTCMonth() + 1)).slice(-2) + "-" + ("0" + t.getUTCDate()).slice(-2); }
    function show(md){ cur = md; var s = $('details.tdm section[data-md="' + md + '"]'), lbl = +md.slice(3) + " " + MON[+md.slice(0, 2) - 1];
      head.textContent = md === today ? "اليوم، " + lbl : md === step(today, -1) ? "أمس، " + lbl : md === step(today, 1) ? "بكرة، " + lbl : lbl; box.dataset.md = md;
      if (s){ var c = s.cloneNode(true), h = c.querySelector("h2"); if (h) h.remove(); body.innerHTML = c.innerHTML; } else body.innerHTML = '<p class="muted">ما عندنا حدث مسجّل في هاليوم.</p>'; }
    if (today !== box.dataset.md) show(today);
    box.addEventListener("click", function(e){ var t = e.target.closest("[data-td]"); if (t) show(step(cur, +t.dataset.td)); }); })();

  // ---- W4.6 tabs: RTL arrow keys (← next, → previous, Home/End) with a roving tabindex
  function rove(bar){ var ts = $$('[role="tab"]', bar), sel = ts.filter(function(t){ return t.getAttribute("aria-selected") === "true"; })[0] || ts[0]; ts.forEach(function(t){ t.tabIndex = t === sel ? 0 : -1; }); }
  $$('[role="tablist"]').forEach(rove);
  document.addEventListener("click", function(e){ var bar = e.target.closest && e.target.closest('[role="tablist"]'); if (bar) setTimeout(function(){ rove(bar); }, 0); });
  document.addEventListener("keydown", function(e){ var t = e.target.closest && e.target.closest('[role="tab"]'); if (!t) return; var bar = t.closest('[role="tablist"]'), ts = $$('[role="tab"]', bar).filter(function(x){ return !x.hidden; }), i = ts.indexOf(t), n = -1;
    if (e.key === "ArrowLeft") n = (i + 1) % ts.length; else if (e.key === "ArrowRight") n = (i - 1 + ts.length) % ts.length; else if (e.key === "Home") n = 0; else if (e.key === "End") n = ts.length - 1; else return;
    e.preventDefault(); ts[n].focus(); ts[n].click(); rove(bar); });

  // ---- W4.6 404: search and today's matches
  (function(){ var s = $("#srch404"); if (s) s.onclick = function(e){ e.stopPropagation(); var b = $("#srch"); if (b) b.click(); };   /* the tap-outside closer must not see this tap */
    var d = $("#day404"); if (!d || !R.dayList) return; var ymd = new Date(Date.now() + 4 * 3600e3).toISOString().slice(0, 10).replace(/-/g, "");
    Promise.all([fetch("/v1/day/" + ymd + ".json").then(function(r){ return r.json(); }), fetch("/v1/index.json").then(function(r){ return r.json(); })]).then(function(r){ var ms = r[0].matches || []; if (!ms.length) return;
      d.innerHTML = "<h2>مباريات اليوم</h2>" + R.dayList(ms, r[1], {}); if (R.localize) R.localize(d); }).catch(function(){}); })();

  // ---- W4.3 /national/: «منتخبك» (the visitor's national team: last result and next match), the day's national matches kept live, then the 22
  (function(){ var fl = $(".natflags"); if (!fl) return; var cc = lsGet("tifo.country"); if (!cc){ try { var tz = Intl.DateTimeFormat().resolvedOptions().timeZone, hit = R.COUNTRIES.filter(function(c){ return c[2] === tz; })[0]; cc = hit ? hit[0] : ""; } catch (e){} }
    var nid = (window.NAT || {})[cc], me = $("#natme"), mb = $("#natmeb");
    if (!nid){ if (me) me.hidden = true; } else fetch("/tn/" + nid + ".json").then(function(r){ return r.json(); }).then(function(t){ mb.innerHTML = '<a class="natme-h" href="/t/' + nid + '/">' + R.logo(t, "md") + "<b>" + R.tname(t) + "</b></a>" + (t.last ? R.matchRow(t.last, { date:true }) : "") + (t.next ? R.matchRow(t.next, { date:true }) : ""); if (R.localize) R.localize(mb);
      var f = fl.querySelector('[data-cc="' + cc + '"]'); if (f) f.classList.add("me"); }).catch(function(){ if (me) me.hidden = true; });
    var nb = $("#natnowb"); if (!nb) return; var ids = nb.dataset.ids.split(",").map(Number);
    (function tick(){ fetch("/v1/live.json", { cache:"no-cache" }).then(function(r){ return r.json(); }).then(function(l){ var by = {}; (l.matches || []).forEach(function(m){ by[m.id] = m; }); var any = false;
      ids.forEach(function(id){ var m = by[id], row = nb.querySelector('[href="/m/' + id + '/"]'); if (!m || !row) return; any = any || R.isLive(m); var tmp = document.createElement("div"); tmp.innerHTML = R.matchRow(m, { date:false }); var nr = tmp.firstElementChild; if (nr && nr.getAttribute("aria-label") !== row.getAttribute("aria-label")) row.replaceWith(nr); });   /* only a real change (score, minute, status) redraws a row */
      if (R.localize) R.localize(nb); setTimeout(tick, any ? 20e3 : 120e3); }).catch(function(){ setTimeout(tick, 120e3); }); })(); })();

  // ---- W4.2 /week/: the pinned «مباراة الأسبوع» counts down to kickoff, then its row follows the live score
  (function(){ var pin = $("#mow"), cd = $("#mowcd"); if (!pin || !cd || !pin.dataset.kick || !R.n) return; var ko = Date.parse(pin.dataset.kick), a = pin.querySelector('a.m[href^="/m/"]'), id = a ? +(a.getAttribute("href").match(/\d+/) || [0])[0] : 0;
    function tick(){ var d = ko - Date.now(); if (d > 0){ var dd = Math.floor(d / 864e5), hh = Math.floor(d / 36e5) % 24, mm = Math.floor(d / 6e4) % 60;
        cd.textContent = "تبدا بعد " + [R.n(dd, ["يوم", "يومين", "أيام", "يوم"]), R.n(hh, ["ساعة", "ساعتين", "ساعات", "ساعة"]), dd ? "" : R.n(mm, ["دقيقة", "دقيقتين", "دقايق", "دقيقة"])].filter(Boolean).join(" و"); setTimeout(tick, 30e3); }
      else { cd.textContent = ""; live(); } }
    function live(){ if (!id) return; fetch("/v1/live.json", { cache:"no-cache" }).then(function(r){ return r.json(); }).then(function(l){ var m = (l.matches || []).filter(function(x){ return x.id === id; })[0]; if (!m){ if (Date.now() - ko < 3 * 36e5) setTimeout(live, 60e3); return; }
      var row = pin.querySelector('a.m[href="/m/' + id + '/"]'), t = document.createElement("div"); t.innerHTML = R.matchRow(m, {}); if (row && t.firstElementChild) row.replaceWith(t.firstElementChild); if (R.localize) R.localize(pin); if (R.isLive(m)) setTimeout(live, 20e3); }).catch(function(){ setTimeout(live, 60e3); }); }
    tick(); })();

  // ---- owner item 9a: push per team (start · goal · end). The toggles live in a sheet on the team page; permission is asked on the first
  // toggle tap (synchronously, Safari rejects it after an await), only after «هذا فريقي». No PushManager (iPhone outside the installed app):
  // the link opens the install sheet instead. Removing the team or turning every toggle off unsubscribes it on the server.
  (function(){ var pbtn = $("#pushbtn"), sheet = $("#pushs"), mb = $("#mybtn"); if (!pbtn || !sheet || PAGE !== "team") return; var TID = +B.dataset.id;
    var ok = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window, iosNoPwa = /iPhone|iPad|iPod/.test(navigator.userAgent) && !navigator.standalone;
    var KEY = null; function key(){ return KEY ? Promise.resolve(KEY) : fetch("/api/tifo/push/key").then(function(r){ return r.json(); }).then(function(j){ KEY = j.publicKey; try { localStorage.setItem("tifo.pushkey", KEY); } catch (e){} return KEY; }); }
    try { KEY = localStorage.getItem("tifo.pushkey"); } catch (e){}
    function st(){ try { return JSON.parse(localStorage.getItem("tifo.push") || "{}"); } catch (e){ return {}; } } function save(s){ try { localStorage.setItem("tifo.push", JSON.stringify(s)); } catch (e){} }
    function isFav(){ var f = []; try { f = JSON.parse(localStorage.getItem("tifo.favs") || "[]"); } catch (e){} return f.some(function(x){ return x.t === "team" && x.id === TID; }); }
    function u8(k){ var p = "=".repeat((4 - k.length % 4) % 4), s = atob((k + p).replace(/-/g, "+").replace(/_/g, "/")), a = new Uint8Array(s.length); for (var i = 0; i < s.length; i++) a[i] = s.charCodeAt(i); return a; }
    function paint(){ var s = st(), ev = (s.teams || {})[TID] || []; $$(".ptg", sheet).forEach(function(b){ b.setAttribute("aria-pressed", ev.indexOf(b.dataset.ev) >= 0 ? "true" : "false"); });
      pbtn.hidden = !isFav() || (!ok && !iosNoPwa); pbtn.textContent = ev.length ? "التنبيهات شغّالة" : "نبّهني بمبارياته"; }
    function send(method, body){ return fetch("/api/tifo/push/sub", { method:method, headers:{ "content-type":"application/json" }, body:JSON.stringify(body), keepalive:true }); }
    function sub(){ return Promise.race([navigator.serviceWorker.ready, new Promise(function(ok, no){ setTimeout(function(){ no(new Error("no worker")); }, 10000); })]).then(function(reg){ return reg.pushManager.getSubscription().then(function(s){ return s || key().then(function(k){ return reg.pushManager.subscribe({ userVisibleOnly:true, applicationServerKey:u8(k) }); }); }); }); }
    function sync(){ var s = st(), ev = ((s.teams || {})[TID] || []).filter(function(x){ return !(B.classList.contains("nospoil") && x !== "start"); }), msg = $("#pushm");   // بدون حرق: no goal or result pushes
      if (!ev.length) return navigator.serviceWorker.ready.then(function(reg){ return reg.pushManager.getSubscription(); }).then(function(x){ if (x) send("DELETE", { team:TID, endpoint:x.endpoint }); }).catch(function(){});
      return sub().then(function(x){ var j = x.toJSON(); return send("POST", { team:TID, events:ev, subscription:{ endpoint:j.endpoint, keys:j.keys } }); }).then(function(r){ if (msg) msg.textContent = r && r.ok !== false ? "تمام، بتوصلك التنبيهات." : "ما قدرنا نشغّلها الحين، جرّب بعد شوي."; })
        .catch(function(){ if (msg) msg.textContent = "ما قدرنا نشغّلها. تأكد إن التنبيهات مسموحة لتيفو في إعدادات جوالك."; }); }
    sheet.addEventListener("click", function(e){ var b = e.target.closest(".ptg"); if (!b) return;
      if (Notification.permission === "default"){ var p = Notification.requestPermission(); if (p && p.then) p.then(function(r){ if (r === "granted") toggle(b); else { var m = $("#pushm"); if (m) m.textContent = "التنبيهات مقفولة. تقدر تسمح لها من إعدادات المتصفح."; } }); return; }
      if (Notification.permission === "denied"){ var m = $("#pushm"); if (m) m.textContent = "التنبيهات مقفولة لتيفو. تقدر تسمح لها من إعدادات المتصفح."; return; }
      toggle(b); });
    function toggle(b){ var s = st(); s.teams = s.teams || {}; var ev = s.teams[TID] || [], k = b.dataset.ev, i = ev.indexOf(k); if (i >= 0) ev.splice(i, 1); else ev.push(k); if (ev.length) s.teams[TID] = ev; else delete s.teams[TID]; save(s); paint(); sync(); }
    pbtn.onclick = function(){ if (!ok && iosNoPwa){ var ib = document.createElement("button"); ib.dataset.sheet = "inst"; ib.hidden = true; B.appendChild(ib); ib.click(); ib.remove(); return; } open(sheet, pbtn); };
    if (mb) mb.addEventListener("click", function(){ setTimeout(function(){ paint(); var s = st();
      if (!isFav() && (s.teams || {})[TID]){ delete s.teams[TID]; save(s); sync(); paint(); return; }   // no longer my team: stop its pushes
      if (isFav() && ok && !(s.teams || {})[TID] && !sessionStorage.getItem("tifo.pushasked")){ try { sessionStorage.setItem("tifo.pushasked", "1"); sessionStorage.setItem("tifo.inst.asked", "1"); } catch (e){} open(sheet, pbtn); } }, 650); });
    paint(); if (ok){ var warm = function(){ if (!KEY) key().catch(function(){}); navigator.serviceWorker.ready.catch(function(){}); }; if ("requestIdleCallback" in window) requestIdleCallback(warm); else setTimeout(warm, 1500); } })();   /* nothing to wait for between the permission and the subscription */

  // ---- owner item 1: «فريقي» in the nav — my crest, opens my team; no team yet: the crest grid of my country in a sheet
  (function(){ var links = $$('[data-nav="mine"]'); if (!links.length) return; var mid = +lsGet("tifo.mine") || 0;
    function pick(g){ var cc = lsGet("tifo.country"); if (!cc || cc === "xx"){ try { var tz = Intl.DateTimeFormat().resolvedOptions().timeZone, hit = R.COUNTRIES.filter(function(c){ return c[2] === tz; })[0]; cc = hit ? hit[0] : "AE"; } catch (e){ cc = "AE"; } }
      fetch("/assets/cc." + B.dataset.cc + ".json").then(function(r){ return r.json(); }).then(function(m){ var list = m[cc] || m.AE || [];
        g.innerHTML = list.map(function(t){ return '<button type="button" data-t="' + t[0] + '" data-n="' + R.esc(t[1]) + '">' + R.logo({ id:t[0] }, "md") + "<span>" + R.esc(t[1]) + "</span></button>"; }).join("");
        g.onclick = function(e){ var b = e.target.closest("button[data-t]"); if (!b) return; var id = +b.dataset.t, n = b.dataset.n, f = []; try { f = JSON.parse(localStorage.getItem("tifo.favs") || "[]"); } catch (x){}
          if (!f.some(function(x){ return x.t === "team" && x.id === id; })) f.unshift({ t:"team", id:id, n:n }); lsSet("tifo.favs", JSON.stringify(f)); lsSet("tifo.mine", String(id)); lsSet("tifo.mine.name", n); location.href = "/t/" + id + "/"; }; }).catch(function(){}); }
    links.forEach(function(a){
      if (mid){ a.href = "/t/" + mid + "/"; var svg = a.querySelector("svg"); if (svg){ var img = document.createElement("img"); img.className = "navcrest"; img.alt = ""; img.width = 22; img.height = 22; img.src = "/logo/96/" + mid + ".webp"; img.onerror = function(){ img.replaceWith(svg); }; svg.replaceWith(img); }
        if (PAGE === "team" && +B.dataset.id === mid){ $$("[data-nav][aria-current]").forEach(function(x){ x.removeAttribute("aria-current"); }); a.setAttribute("aria-current", "page"); } }
      else a.addEventListener("click", function(e){ e.preventDefault(); var g = $("#minegrid"), sh = $("#minesh"); if (!g || !sh){ location.href = a.href; return; } open(sh, a); if (!g.childElementCount) pick(g); }); }); })();

  // W2.8: «كل الأرقام (N)» opens the rest of the tiles in place
  document.addEventListener("click", function(e){ var b = e.target.closest("[data-shall]"); if (!b) return; var m = b.previousElementSibling; if (m && m.classList.contains("shmore")){ m.hidden = false; b.remove(); var f = m.querySelector("button"); if (f) f.focus({ preventScroll:true }); } });
})();
