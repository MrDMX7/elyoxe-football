/* تيفو v3 shell (redesign/DESIGN-v3.md): the bar, the two sheets (شارك وأدوات، المزيد), the reader panel for shelf tiles
   (templated sections stamped on first open), deep links, home rails refreshed from app.js's own poll ("tifo:day"),
   the match mini-bar ("tifo:match"), key art, parallax, rail arrows. Runs after app.js; it never re-fetches data. */
(function(){
  "use strict";
  var R = window.TR, B = document.body, PAGE = B.dataset.page, RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function(s, r){ return (r || document).querySelector(s); }, $$ = function(s, r){ return [].slice.call((r || document).querySelectorAll(s)); };
  if (window.PN && R.setNames) R.setNames(window.PN);

  // ---- top bar: transparent over the hero, solid once the page moves
  var top = $(".top"); function onScroll(){ if (top) top.classList.toggle("solid", window.scrollY > 40); }
  onScroll();

  // ---- sheets + panel: one open at a time, Esc / scrim / close button, focus returns to the opener
  var opener = null, scrim = $("#scrimall");
  function closeAll(){ $$(".sheet:not([hidden]),.panel:not([hidden])").forEach(function(s){ s.hidden = true; if (s.id === "panel") unpanel(); }); scrim.hidden = true; B.classList.remove("locked"); if (opener && opener.focus) opener.focus(); opener = null; }
  function open(el, from){ closeAll(); opener = from || document.activeElement; el.hidden = false; scrim.hidden = false; B.classList.add("locked"); var f = el.querySelector("button,a,[tabindex]"); if (f) setTimeout(function(){ f.focus({ preventScroll:true }); }, 30); }
  document.addEventListener("click", function(e){
    var t = e.target.closest("[data-sheet]"); if (t){ e.preventDefault(); open($("#" + t.dataset.sheet), t); return; }
    if (e.target.closest("[data-close]") || e.target === scrim) { closeAll(); return; }
    var o = e.target.closest("[data-open]"); if (o){ panel(o.dataset.open, o); return; }
    var g = e.target.closest("[data-go]"); if (g){ e.preventDefault(); goTab(g.dataset.go); return; }
    // settings buttons inside المزيد open their own boxes (app.js): close the sheet first
    if (e.target.closest("#more #ctry, #srch")) { $$(".sheet:not([hidden])").forEach(function(s){ s.hidden = true; }); scrim.hidden = true; B.classList.remove("locked"); }
    // client-rendered links to a prototype page stay inside /next/
    var a = e.target.closest("a[href^='/']"); if (a && R.PROTO && R.PROTO[a.getAttribute("href")]) { e.preventDefault(); location.href = "/next" + a.getAttribute("href"); }
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
    if (from && from.dataset.anchor) try { history.replaceState(null, "", "#" + from.dataset.anchor); } catch (e){}
  }
  function unpanel(){ if (cur){ cur.vault.appendChild(cur.body); cur = null; } }

  // ---- tabs: deep links (#num, #n-cards, old #goals/#assists), data-go buttons
  function goTab(k){ var b = $('.mtabs button[data-t="' + k + '"]'); if (b){ b.click(); var bar = $(".mtabs"); if (bar) window.scrollTo({ top:bar.getBoundingClientRect().top + window.scrollY - 60, behavior:RM ? "auto" : "smooth" }); } }
  (function deep(){
    var h = decodeURIComponent(location.hash.slice(1)); if (!h) return;
    var alias = { goals:["num", "goals"], assists:["num", "assists"] }[h];
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
  if (hero && window.TifoArt){
    var cv = hero.querySelector("canvas");
    if (hero.classList.contains("chero")){ try { art = window.TifoArt.mount(cv); art.paint(JSON.parse(hero.dataset.art || "[]"), 11); } catch (e){} }
    if (hero.classList.contains("mhero")){ try { var ms = JSON.parse($("#msum").textContent); art = window.TifoArt.mount(cv); art.set(ms); } catch (e){} }
  }
  // parallax + fade: the art drifts at 0.35x scroll, the title fades as it leaves
  var hin = hero && hero.querySelector(".hero-in"), ticking = false;
  window.addEventListener("scroll", function(){ onScroll(); if (RM || !hero || ticking) return; ticking = true; requestAnimationFrame(function(){ ticking = false; var y = window.scrollY, h = hero.offsetHeight; if (y > h * 1.2) return;
    var c = hero.querySelector("canvas"); if (c) c.style.transform = "translate3d(0," + (y * 0.35).toFixed(1) + "px,0)"; if (hin) hin.style.opacity = Math.max(0, 1 - y / (h * 0.85)).toFixed(3); }); }, { passive:true });

  // ---- match: sticky mini score once the hero leaves; updated from app.js's poll
  var mini = $("#mini");
  function miniDraw(m){ if (!mini || !m) return; var live = R.isLive(m), s = m.score;
    mini.firstElementChild.innerHTML = '<span class="mt">' + R.logo(m.home, "sm") + "<b>" + R.tname(m.home) + '</b></span><span class="ms' + (live ? " live" : "") + '">' + (s ? '<b class="dg">' + s.home + " - " + s.away + "</b>" : '<b class="dg">' + R.tt(m.kickoff_uae) + "</b>") + "<small>" + (live ? R.minute(m) : R.statusText(m)) + '</small></span><span class="mt a"><b>' + R.tname(m.away) + "</b>" + R.logo(m.away, "sm") + '</span><button type="button" class="ib" data-sheet="share" aria-label="شارك"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 8l5-5 5 5M5 13v8h14v-8"/></svg></button>'; R.localize(mini); }
  if (mini){ try { miniDraw(JSON.parse($("#msum").textContent)); } catch (e){}
    if ("IntersectionObserver" in window){ var mh = $("#mh"); new IntersectionObserver(function(es){ var on = !es[0].isIntersecting && es[0].boundingClientRect.top < 0; B.classList.toggle("mini-on", on); mini.setAttribute("aria-hidden", !on); }, { threshold:0 }).observe(mh); } }
  document.addEventListener("tifo:match", function(e){ var md = e.detail; if (R.arNames) R.arNames(md); miniDraw(md); if (art) art.set(md); });

  // ---- home: rails from the same day data app.js just fetched
  document.addEventListener("tifo:day", function(e){
    var d = e.detail; R._idx = d.idx; if (d.off !== 0) return;
    var mine = null; try { mine = +localStorage.getItem("tifo.mine") || null; } catch (x){}
    var all = d.ms, r = R.homeRails(all, d.idx, { mine:mine });
    [["r-live", r.live], ["r-today", r.today], ["r-arab", r.arab]].forEach(function(x){ var s = document.getElementById(x[0]); if (!s) return; var box = s.querySelector(".rail-s"); if (box.innerHTML !== x[1]){ box.innerHTML = x[1]; R.localize(box); } s.hidden = !x[1]; });
    var f = R.featured(all), go = $("#herogo"); if (f && go){ go.href = (R.PROTO["/m/" + f.id + "/"] ? "/next" : "") + "/m/" + f.id + "/"; }
    setTimeout(function(){ var k = $("#standkick"); if (k && f && mine && (f.home.id === mine || f.away.id === mine) && !R.isLive(f)) k.textContent = "فريقك"; else if (k && f && f.status === "scheduled") k.textContent = "الليلة"; }, 0);
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
    w.onclick = function(e){ var b = e.target.closest("button"); if (!b) return; var dir = b === w.firstChild ? 1 : -1; s.scrollBy({ left:-dir * s.clientWidth * 0.85 * (document.dir === "rtl" ? 1 : -1) * -1, behavior:RM ? "auto" : "smooth" }); };
    s.parentNode.querySelector(".rail-h").appendChild(w); });
  if (!RM && "IntersectionObserver" in window){ var io = new IntersectionObserver(function(es){ es.forEach(function(e){ if (e.isIntersecting){ e.target.classList.add("in"); io.unobserve(e.target); } }); }, { rootMargin:"0px 0px -8% 0px" });
    $$(".rail, .daybox, .shelf3, [data-pane] > section.blk").forEach(function(el){ el.classList.add("fx"); io.observe(el); }); }
})();
