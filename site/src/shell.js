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
  function closeAll(){ $$(".sheet:not([hidden]),.panel:not([hidden])").forEach(function(s){ s.hidden = true; if (s.id === "panel") unpanel(); }); scrim.hidden = true; B.classList.remove("locked"); if (opener && opener.focus) opener.focus(); opener = null; }
  function open(el, from){ closeAll(); opener = from || document.activeElement; el.hidden = false; scrim.hidden = false; B.classList.add("locked"); var f = el.querySelector("button,a,[tabindex]"); if (f) setTimeout(function(){ f.focus({ preventScroll:true }); }, 30); }
  document.addEventListener("click", function(e){
    var t = e.target.closest("[data-sheet]"); if (t){ e.preventDefault(); open($("#" + t.dataset.sheet), t); return; }
    if (e.target.closest("[data-close]") || e.target === scrim || (e.target.classList && (e.target.classList.contains("sheet") || e.target.classList.contains("panel")))) { closeAll(); return; }
    var o = e.target.closest("[data-open]"); if (o){ panel(o.dataset.open, o); return; }
    var g = e.target.closest("[data-go]"); if (g){ e.preventDefault(); goTab(g.dataset.go); return; }
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
    mini.firstElementChild.innerHTML = '<span class="mt">' + R.logo(m.home, "sm") + "<b>" + R.tname(m.home) + '</b></span><span class="ms' + (live ? " live" : "") + '">' + (s ? '<b class="dg">' + s.home + " - " + s.away + "</b>" : '<b class="dg">' + R.tt(m.kickoff_uae) + "</b>") + "<small>" + (live ? R.minute(m) : m.status === "scheduled" ? R.td(m.kickoff_uae) : R.statusText(m)) + '</small></span><span class="mt a"><b>' + R.tname(m.away) + "</b>" + R.logo(m.away, "sm") + '</span><button type="button" class="ib" data-sheet="share" aria-label="شارك"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 8l5-5 5 5M5 13v8h14v-8"/></svg></button>'; R.localize(mini); }
  if (mini){ try { miniDraw(JSON.parse($("#msum").textContent)); } catch (e){}
    if ("IntersectionObserver" in window){ var mh = $("#mh"); new IntersectionObserver(function(es){ var on = !es[0].isIntersecting && es[0].boundingClientRect.top < 0; B.classList.toggle("mini-on", on); mini.setAttribute("aria-hidden", !on); }, { threshold:0 }).observe(mh); } }
  document.addEventListener("tifo:match", function(e){ var md = e.detail; if (R.arNames) R.arNames(md); miniDraw(md); if (art) art.set(md);
    if (md.status !== "scheduled"){ var t = $('.mtabs [data-t="events"]'); if (t) t.textContent = "الأحداث"; var g = $('.hero-acts [data-go="events"]'); if (g){ g.dataset.go = "lineups"; g.href = "#lineups"; g.textContent = "التشكيلة"; } } });

  // ---- home: rails from the same day data app.js just fetched
  document.addEventListener("tifo:day", function(e){
    var d = e.detail; R._idx = d.idx; if (d.off !== 0) return;
    var mine = null; try { mine = +localStorage.getItem("tifo.mine") || null; } catch (x){}
    var all = d.ms, ids = {}; all.forEach(function(m){ ids[m.id] = 1; }); var r = R.homeRails(all.concat(((d.live || {}).matches || []).filter(function(m){ return !ids[m.id]; })), d.idx, { mine:mine });
    [["r-live", r.live], ["r-today", r.today], ["r-arab", r.arab]].forEach(function(x){ var s = document.getElementById(x[0]); if (!s) return; var box = s.querySelector(".rail-s"); if (box.innerHTML !== x[1]){ box.innerHTML = x[1]; R.localize(box); } s.hidden = !x[1]; });
    var f = R.featured(all), go = $("#herogo"); if (f && go){ go.href = (R.isProto("/m/" + f.id + "/") ? "/next" : "") + "/m/" + f.id + "/"; }
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
    w.onclick = function(e){ var b = e.target.closest("button"); if (!b) return; var dir = b === w.firstChild ? 1 : -1; s.scrollBy({ left:dir * s.clientWidth * 0.85, behavior:RM ? "auto" : "smooth" });   /* RTL: "next" moves left */ };
    s.parentNode.querySelector(".rail-h").appendChild(w); });
  if (!RM && "IntersectionObserver" in window){ var io = new IntersectionObserver(function(es){ es.forEach(function(e){ if (e.isIntersecting){ e.target.classList.add("in"); io.unobserve(e.target); } }); }, { rootMargin:"0px 0px -8% 0px" });
    $$(".rail, .daybox, .shelf3, [data-pane] > section.blk").forEach(function(el){ if (el.getBoundingClientRect().top < window.innerHeight) return; el.classList.add("fx"); io.observe(el); }); }

  // 356: hero crests carry a view-transition name, so a crest morphs into the team page hero (same-origin navigations)
  $$(".hero img.logo").forEach(function(img){ var m = (img.getAttribute("src") || "").match(/\/logo\/(\d+)\.png/); if (m && !$$(".hero img.logo").some(function(o){ return o !== img && o.getAttribute("src") === img.getAttribute("src"); })) img.style.viewTransitionName = "crest-" + m[1]; });
  // 388: one match in the home hero — while the hero match is live, the national countdown leaves the hero for its rail card
  function cdPlace(){ var cd = $("#uaecd"), hero = $("#stand"); if (!cd || !hero) return; var f = R._idx && window.__feat, live = f && R.isLive(f);
    var a = cd.querySelector("a.cd"), mid = a && (a.getAttribute("href").match(/\/m\/(\d+)\//) || [])[1];
    if (!live){ if (!hero.contains(cd)){ var acts = hero.querySelector(".hero-acts"); acts.parentNode.insertBefore(cd, acts); } cd.hidden = false; return; }
    if (mid && f && String(f.id) === mid){ cd.hidden = true; return; }
    var card = mid && $('.rc[data-mid="' + mid + '"]'); if (card){ if (!card.contains(cd)) card.appendChild(cd); cd.hidden = false; } else cd.hidden = true; }
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
      var p = mineBox.querySelector(".mine-card p"); if (p) p.textContent = "اختار فريقك، ومبارياته تطلع لك هني أول شي."; mineBox.querySelector(".mine-card").appendChild(g); }).catch(function(){}); }
  if (mineBox && "MutationObserver" in window) new MutationObserver(mineEmpty).observe(mineBox, { childList:true });
  // ================= owner items (2026-09-27): 355 goal moment · 357 match-state hero · 359 cinema · 360 goal sound ·
  // 370 live «لو خلصت الحين» · 373 player card · 376 lineup builder · 379 embed. Everything lives in the sheet, a tab or the hero.
  function lsGet(k){ try { return localStorage.getItem(k); } catch (e){ return null; } }
  function lsSet(k, v){ try { if (v) localStorage.setItem(k, v); else localStorage.removeItem(k); } catch (e){} }
  // 360: goal sound, OFF by default; a short synthesized whistle (no audio file), toggled in المزيد
  var snd = $("#goalsnd"); if (snd){ snd.setAttribute("aria-pressed", lsGet("tifo.goalsnd") === "1"); snd.onclick = function(){ var on = lsGet("tifo.goalsnd") !== "1"; lsSet("tifo.goalsnd", on ? "1" : ""); snd.setAttribute("aria-pressed", on); if (on) whistle(); }; }
  var AC = null;
  function whistle(){ if (lsGet("tifo.goalsnd") !== "1") return; try { AC = AC || new (window.AudioContext || window.webkitAudioContext)(); var t = AC.currentTime;
    [0, 0.32].forEach(function(d, i){ var o = AC.createOscillator(), g = AC.createGain(), lfo = AC.createOscillator(), lg = AC.createGain(); o.type = "sine"; o.frequency.value = i ? 2350 : 2150; lfo.frequency.value = 38; lg.gain.value = 90; lfo.connect(lg); lg.connect(o.frequency);
      g.gain.setValueAtTime(0, t + d); g.gain.linearRampToValueAtTime(0.18, t + d + 0.02); g.gain.setValueAtTime(0.18, t + d + (i ? 0.5 : 0.22)); g.gain.linearRampToValueAtTime(0, t + d + (i ? 0.56 : 0.26));
      o.connect(g); g.connect(AC.destination); o.start(t + d); lfo.start(t + d); o.stop(t + d + 0.6); lfo.stop(t + d + 0.6); }); } catch (e){} }
  // 355: goal moment — the scoring side's colour flashes, the scorer sweeps across, the score flips like an airport board
  function goalMoment(md, side){
    var tm = md[side], ev = (md.events || []).filter(function(e){ return /goal/.test(e.type) && e.team === side; }).pop(), who = ev && ev.player ? ev.player.name : "";
    var fx = document.createElement("div"); fx.className = "goalfx"; fx.style.setProperty("--gc", R.col(tm.id, 0));
    fx.innerHTML = '<b>هدف</b><span>' + R.esc(who ? who + " " : "") + R.tname(tm) + "</span>"; document.body.appendChild(fx);
    setTimeout(function(){ fx.remove(); }, RM ? 1800 : 1400);
    $$("#mh .sc .dg, #mini .ms .dg, .cine .cs").forEach(function(d){ d.classList.remove("flip"); void d.offsetWidth; d.classList.add("flip"); });
    whistle();
  }
  var lastScore = {};
  function scoreWatch(md){ if (!md || !md.score) return; var k = md.id, p = lastScore[k]; lastScore[k] = { home:md.score.home, away:md.score.away };
    if (p && (md.score.home > p.home || md.score.away > p.away)) goalMoment(md, md.score.home > p.home ? "home" : "away"); }
  // 357: the match hero follows the state: countdown before kickoff, a soft pulse in play, the final + recap after
  var cdEl = null, cdT = null;
  function heroState(md){ if (!md || PAGE !== "match") return; var st = R.isLive(md) ? "live" : md.status === "finished" ? "final" : md.status === "scheduled" ? "pre" : "other";
    B.dataset.state = st; var box = $("#mh .sc"); if (!box) return;
    if (st === "pre" && md.kickoff_utc && !md.time_tbd){ if (!cdEl || !box.contains(cdEl)){ cdEl = document.createElement("span"); cdEl.className = "mcd"; box.appendChild(cdEl); }
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
  var cb2 = $("#cinebtn"); if (cb2) cb2.onclick = function(){ closeAll(); cine = document.createElement("div"); cine.className = "cine"; cine.innerHTML = '<button type="button" class="x" aria-label="سكّر">سكّر</button><div class="ci"></div>'; document.body.appendChild(cine);
    cine.querySelector(".x").onclick = function(){ if (document.fullscreenElement) document.exitFullscreen().catch(function(){}); cine.remove(); cine = null; };
    try { cineDraw(window.__md || JSON.parse($("#msum").textContent)); } catch (e){} if (cine.requestFullscreen) cine.requestFullscreen().catch(function(){}); if (navigator.wakeLock) navigator.wakeLock.request("screen").catch(function(){}); };
  // 370: «لو خلصت الحين» — while live, the league table with this score, recomputed on every poll (first tab)
  var ST0 = null;
  function liveTable(md){ var box = $("#ltable"); if (!box) return; if (!R.isLive(md)){ box.innerHTML = ""; return; }
    (ST0 ? Promise.resolve(ST0) : fetch("/v1/comp/" + md.comp + "/standings.json").then(function(r){ return r.ok ? r.json() : null; }).then(function(s){ ST0 = s; return s; })).then(function(st){
      if (!st || !st.groups || !st.groups.length) return; var g = st.groups.filter(function(g){ return (g.rows || []).some(function(r){ return r.team.id === md.home.id; }); })[0]; if (!g) return;
      var lt = R.liveTable({ groups:[g] }, [md]), rows = lt.groups[0].rows, ids = [md.home.id, md.away.id], idx = rows.map(function(r, i){ return ids.indexOf(r.team.id) >= 0 ? i : -1; }).filter(function(i){ return i >= 0; });
      var lo = Math.max(0, Math.min.apply(null, idx) - 2), hi = Math.min(rows.length, Math.max.apply(null, idx) + 3);
      box.innerHTML = '<div class="lt"><b>لو خلصت الحين</b><div class="tblwrap"><table class="st"><tbody>' + rows.slice(lo, hi).map(function(r, i){ var hot = ids.indexOf(r.team.id) >= 0; return '<tr class="' + (hot ? "hot" : "") + '"><td class="rk">' + (lo + i + 1) + '</td><td class="tm">' + R.logo(r.team, "sm") + " " + R.tname(r.team) + "</td><td>" + r.played + '</td><td class="pts">' + r.pts + "</td></tr>"; }).join("") + "</tbody></table></div></div>"; }).catch(function(){}); }
  document.addEventListener("tifo:match", function(e){ var md = e.detail; window.__md = md; scoreWatch(md); heroState(md); cineDraw(md); liveTable(md); });
  if (PAGE === "match") try { var m0 = JSON.parse($("#msum").textContent); lastScore[m0.id] = m0.score ? { home:m0.score.home, away:m0.score.away } : { home:0, away:0 }; heroState(m0); } catch (e){}
  // the home hero's match: a goal there gets the same moment
  document.addEventListener("tifo:day", function(e){ if (e.detail.off !== 0) return; var f = R.featured(e.detail.ms); if (f && R.isLive(f)){ var p = lastScore[f.id]; if (p && f.score && (f.score.home > p.home || f.score.away > p.away)) goalMoment(f, f.score.home > p.home ? "home" : "away"); if (f.score) lastScore[f.id] = { home:f.score.home, away:f.score.away }; } });

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

  // 376: lineup builder — pick your XI from the squad (team pages), share it as an image
  var lb = $("#xibtn"); if (lb) lb.onclick = function(){ closeAll(); var pn = $("#panel"); open(pn, lb); $("#panelt").textContent = "سوّ تشكيلتك"; $("#panels").textContent = "";
    var box = $("#panelb"); box.innerHTML = '<p class="muted small">نحمّل اللاعبين…</p>';
    fetch("/v1/team/" + B.dataset.id + ".json").then(function(r){ return r.json(); }).then(function(t){ var sq = []; (t.squad || []).forEach(function(g){ if (g.group !== "coach") (g.players || []).forEach(function(p){ R.arNames && R.arNames({ lineups:{ home:{ starters:[p] } } }); sq.push({ id:p.id, name:p.name, no:p.number, g:g.group }); }); });
      var F = { "4-3-3":[1, 4, 3, 3], "4-4-2":[1, 4, 4, 2], "4-2-3-1":[1, 4, 2, 3, 1], "3-5-2":[1, 3, 5, 2] }, cur = "4-3-3";
      function draw(){ var rows = F[cur], slots = [], n = 0; rows.forEach(function(k, ri){ for (var i = 0; i < k; i++) slots.push([ri, i, k, n++]); });
        box.innerHTML = '<div class="seg" role="group">' + Object.keys(F).map(function(f){ return '<button type="button" data-f="' + f + '" aria-pressed="' + (f === cur) + '">' + f + "</button>"; }).join("") + '</div><div class="xi">' + rows.map(function(k, ri){ return '<div class="xr">' + slots.filter(function(s){ return s[0] === ri; }).map(function(s){ return '<select data-s="' + s[3] + '" aria-label="اللاعب">' + '<option value="">—</option>' + sq.map(function(p){ return '<option value="' + p.id + '">' + R.esc(p.name) + "</option>"; }).join("") + "</select>"; }).join("") + "</div>"; }).reverse().join("") + '</div><p><button type="button" class="cta" id="xishare">شارك تشكيلتي</button></p>';
        box.querySelector(".seg").onclick = function(e){ var b = e.target.closest("[data-f]"); if (b){ cur = b.dataset.f; draw(); } };
        $("#xishare").onclick = function(){ var sel = $$("select[data-s]", box).map(function(s){ var p = sq.filter(function(q){ return String(q.id) === s.value; })[0]; return p ? p.name : ""; });
          var W = 1080, H = 1350, c = document.createElement("canvas"); c.width = W; c.height = H; var x = c.getContext("2d"); x.fillStyle = "#0F3A2F"; x.fillRect(0, 0, W, H);
          x.strokeStyle = "rgba(255,255,255,.35)"; x.lineWidth = 4; x.strokeRect(60, 140, W - 120, H - 260); x.beginPath(); x.moveTo(60, H / 2 + 20); x.lineTo(W - 60, H / 2 + 20); x.stroke();
          x.direction = "rtl"; x.textAlign = "center"; x.fillStyle = "#F6F7F2"; x.font = '800 54px "Noto Kufi Arabic"'; x.fillText("تشكيلتي لـ" + (t.name_ar || t.name) + " (" + cur + ")", W / 2, 95);
          var rows = F[cur], k = 0; rows.forEach(function(nr, ri){ var y = H - 180 - ri * ((H - 380) / (rows.length - 1)); for (var i = 0; i < nr; i++){ var xx = W - 60 - (i + 1) * (W - 120) / (nr + 1); x.fillStyle = R.col(t.id, 0); x.fillRect(xx - 34, y - 34, 68, 68); x.fillStyle = "#F6F7F2"; x.font = '600 30px "Readex Pro"'; x.fillText(sel[k] || "—", xx, y + 72); k++; } });
          x.textAlign = "left"; x.fillStyle = "#B9C7C0"; x.font = '700 36px "Barlow Condensed"'; x.fillText("tifo.elyoxe.com", 60, H - 45);
          (document.fonts ? document.fonts.ready : Promise.resolve()).then(function(){ window.TifoShare && window.TifoShare.out(c, "tifo-xi-" + t.id + ".png"); }); }; }
      draw(); }).catch(function(){ box.innerHTML = '<p class="muted small">ما قدرنا نحمّل اللاعبين.</p>'; }); };

  // 379: embed code for other sites (league table / live match), iframe with a link back to Tifo
  var eb = $("#embedbtn"); if (eb) eb.onclick = function(){ var u = eb.dataset.src, code = '<iframe src="https://tifo.elyoxe.com' + u + '" width="100%" height="' + (eb.dataset.h || 420) + '" style="border:0" loading="lazy" title="تيفو"></iframe>';
    var l = $("#secpicks"); l.innerHTML = '<p class="small muted">انسخ الكود وحطه في موقعك:</p><textarea class="embc" rows="4" readonly>' + R.esc(code) + '</textarea><button type="button" class="sa" id="embcopy">انسخ الكود</button>'; l.hidden = false;
    $("#embcopy").onclick = function(){ (navigator.clipboard ? navigator.clipboard.writeText(code) : Promise.reject()).then(function(){ $("#embcopy").textContent = "انتسخ ✓"; }, function(){ l.querySelector("textarea").select(); }); }; };

})();
