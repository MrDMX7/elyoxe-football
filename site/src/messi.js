/* تيفو: the Messi museum's live parts (/messi/, loaded only there). The rooms are prerendered by lib/messi_page.cjs;
   this adds the 3D pitch and the season layers (src/messi3d.js, loaded when their room scrolls into view), the games
   (stand in his spot, where will he shoot, the quiz, this day), the birthday mode, the world map, and the keepsakes
   (a phone wallpaper and a card for any goal, drawn on the visitor's device). */
(function(){
  "use strict";
  var $ = function(s){ return document.querySelector(s); }, $$ = function(s){ return Array.prototype.slice.call(document.querySelectorAll(s)); };
  var DATA = {}; try { DATA = JSON.parse(($("#mdata") || {}).textContent || "{}"); } catch (e){}
  var NM = DATA.names || {}, nm = function(n){ return NM[n] || n; };
  var esc = function(s){ return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){ return { "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]; }); };
  function when(el, fn){ if (!el) return; var done = false, go = function(){ if (!done){ done = true; fn(); } };
    if (!("IntersectionObserver" in window)) return go(); var io = new IntersectionObserver(function(es){ if (es[0].isIntersecting){ io.disconnect(); go(); } }, { rootMargin:"300px" }); io.observe(el); }

  // ---- the entrance: the count climbs once
  var cnt = $(".mcount b[data-count]");
  if (cnt && !matchMedia("(prefers-reduced-motion: reduce)").matches){ var to = +cnt.dataset.count, t0 = 0; cnt.textContent = "0";
    requestAnimationFrame(function step(t){ if (!t0) t0 = t; var k = Math.min(1, (t - t0) / 1800); cnt.textContent = Math.round(to * (1 - Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(step); }); }

  // ---- birthday (24 June): the date comes from Wikidata through the page data
  (function(){ var d = DATA.dob, b = $("#mbday"); if (!d || !b) return; var now = new Date(Date.now() + 4 * 3600e3).toISOString().slice(5, 10);
    if (now !== d.slice(5, 10)) return; b.hidden = false; b.className = "mbday"; b.innerHTML = "<b>اليوم عيد ميلاد ميسي الـ" + (new Date().getFullYear() - +d.slice(0, 4)) + "</b> · المتحف كله له."; document.body.classList.add("mbday-on"); })();

  // ---- the goals pitch (3D)
  var box = $("#m3dc"), api = null, cur = 0, OPP = {}, st = $("#m3ds"), rg = $("#m3dr"), cardBtn = $("#mcard");
  try { OPP = JSON.parse((box && box.dataset.opp) || "{}"); } catch (e){}
  var KIND = { "Free Kick":" · ضربة حرة", "Penalty":" · جزاء" };
  function step(n, g, tot){ rg.max = tot; rg.value = n; cur = g ? g : null; if (cardBtn) cardBtn.disabled = !g;
    st.textContent = g ? "الهدف " + n + " من " + tot + " · " + g.season + " · ضد " + (OPP[g.opp] || nm(g.opp)) + " · الدقيقة " + g.min + (KIND[g.kind] || "") : ""; }
  var pending = [];
  function use(fn){ if (api) fn(api); else pending.push(fn); }
  when(box, function(){
    Promise.all([import(box.dataset.src), fetch(box.dataset.json).then(function(r){ return r.json(); })]).then(function(x){
      api = x[0].mount(box, x[1], { onStep:step }); window.__messi = api; pending.splice(0).forEach(function(f){ f(api); });
    }).catch(function(){ box.innerHTML = '<p class="empty">ما قدرنا نحمّل الملعب الثلاثي الأبعاد على هالجهاز.</p>'; });
  });
  $$(".m3d-ctl [data-v]").forEach(function(b){ b.onclick = function(){ use(function(a){ a.view(b.dataset.v); }); $$(".m3d-ctl [data-v]").forEach(function(o){ o.setAttribute("aria-pressed", String(o === b)); }); }; });
  $$(".m3d-ctl [data-f]").forEach(function(b){ b.onclick = function(){ use(function(a){ a.filter(b.dataset.f); }); $$(".m3d-ctl [data-f]").forEach(function(o){ o.setAttribute("aria-pressed", String(o === b)); }); }; });
  if ($("#m3dplay")) $("#m3dplay").onclick = function(){ use(function(a){ a.play(); }); };
  if ($("#m3dmiss")) $("#m3dmiss").onchange = function(e){ use(function(a){ a.misses(e.target.checked); }); };
  if (rg) rg.oninput = function(){ use(function(a){ a.seek(+rg.value); }); };
  $$("[data-goal]").forEach(function(b){ b.onclick = function(){ var r = $("#r-goals"); if (r) r.scrollIntoView({ behavior:"smooth", block:"start" }); use(function(a){ $$(".m3d-ctl [data-f]").forEach(function(o){ o.setAttribute("aria-pressed", String(o.dataset.f === "all")); }); a.focus(+b.dataset.goal); }); }; });

  // ---- the season layers (3D, the second climax)
  var lay = $("#m3dl");
  when(lay, function(){ Promise.all([import(lay.dataset.src), fetch(lay.dataset.json).then(function(r){ return r.json(); })]).then(function(x){ x[0].layers(lay, x[1]); })
    .catch(function(){ lay.innerHTML = '<p class="empty">ما قدرنا نحمّل الطبقات على هالجهاز.</p>'; }); });

  // ---- drawing helpers for the keepsakes (2D canvas, on the visitor's device)
  function pitch2d(ctx, x0, y0, w){ var h = w * 60 / 80, s = w / 80; ctx.save(); ctx.translate(x0, y0); ctx.fillStyle = "#123a2f"; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = "rgba(246,247,242,.45)"; ctx.lineWidth = Math.max(1, w / 400); ctx.strokeRect(0, 0, w, h); ctx.strokeRect(18 * s, 0, 44 * s, 18 * s); ctx.strokeRect(30 * s, 0, 20 * s, 6 * s);
    ctx.beginPath(); ctx.arc(40 * s, 60 * s, 10 * s, Math.PI, 2 * Math.PI); ctx.stroke(); ctx.restore(); return s; }
  function arc2d(ctx, x0, y0, s, g){ var a = g.y * s, b = (120 - g.x) * s, c = Math.min(43.8, Math.max(36.2, g.ey == null ? 40 : g.ey)) * s; ctx.beginPath(); ctx.moveTo(x0 + a, y0 + b); ctx.quadraticCurveTo(x0 + (a + c) / 2, y0 + b / 2 - 4 * s, x0 + c, y0); ctx.stroke(); }
  var COLS = { L:"rgba(240,188,90,", R:"rgba(233,236,228,", H:"rgba(92,201,164,", O:"rgba(167,173,164," };
  function save(canvas, name){ canvas.toBlob(function(b){ var f = new File([b], name, { type:"image/png" });
    if (navigator.canShare && navigator.canShare({ files:[f] })) navigator.share({ files:[f], title:"ميسي · تيفو" }).catch(function(){});
    else { var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = name; a.click(); setTimeout(function(){ URL.revokeObjectURL(a.href); }, 5000); } }, "image/png"); }
  function allGoals(){ return fetch(box.dataset.json).then(function(r){ return r.json(); }).then(function(d){ var o = []; d.matches.forEach(function(m){ m.shots.forEach(function(s){ if (s.goal) o.push(Object.assign({ season:m.season, opp:m.opp }, s)); }); }); return o; }); }
  if ($("#mwall")) $("#mwall").onclick = function(){ allGoals().then(function(gs){
    var c = document.createElement("canvas"); c.width = 1170; c.height = 2532; var x = c.getContext("2d"); x.fillStyle = "#0B1512"; x.fillRect(0, 0, c.width, c.height);
    var w = 1050, x0 = 60, y0 = 900, s = pitch2d(x, x0, y0, w); x.lineWidth = 1.6;
    gs.forEach(function(g){ x.strokeStyle = (COLS[g.body] || COLS.O) + ".38)"; arc2d(x, x0, y0, s, g); });
    x.fillStyle = "#F0BC5A"; x.font = "700 150px 'Noto Kufi Arabic', sans-serif"; x.textAlign = "center"; x.fillText("ميسي", 585, 560);
    x.fillStyle = "rgba(246,247,242,.7)"; x.font = "500 48px 'Noto Kufi Arabic', sans-serif"; x.fillText(gs.length + " هدف من مكانها · tifo.elyoxe.com", 585, 700);
    save(c, "messi-tifo.png"); }); };
  if (cardBtn) cardBtn.onclick = function(){ if (!cur) return; var g = cur;
    var c = document.createElement("canvas"); c.width = 1080; c.height = 1350; var x = c.getContext("2d"); x.fillStyle = "#0B1512"; x.fillRect(0, 0, 1080, 1350);
    var s = pitch2d(x, 90, 380, 900); x.lineWidth = 7; x.strokeStyle = (COLS[g.body] || COLS.O) + "1)"; arc2d(x, 90, 380, s, g);
    x.fillStyle = "#F0BC5A"; x.beginPath(); x.arc(90 + g.y * s, 380 + (120 - g.x) * s, 12, 0, 7); x.fill();
    x.textAlign = "center"; x.fillStyle = "#F6F7F2"; x.font = "700 76px 'Noto Kufi Arabic', sans-serif"; x.fillText("ميسي ضد " + (OPP[g.opp] || nm(g.opp)), 540, 170);
    x.font = "500 44px 'Noto Kufi Arabic', sans-serif"; x.fillStyle = "rgba(246,247,242,.75)"; x.fillText(g.season + " · الدقيقة " + g.min + (KIND[g.kind] || ""), 540, 250);
    x.fillText("tifo.elyoxe.com/messi", 540, 1290); save(c, "messi-goal.png"); };

  // ---- stand in his spot: every shot within 3 yards of the tap
  var spot = $("#spot svg");
  if (spot) spot.addEventListener("click", function(e){ var pt = spot.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY; var p = pt.matrixTransform(spot.getScreenCTM().inverse());
    var X = 120 - p.y, Y = p.x, sh = 0, gl = 0; $$("#spot circle.pt").forEach(function(c){ var dx = +c.getAttribute("cx") - p.x, dy = +c.getAttribute("cy") - p.y; if (dx * dx + dy * dy <= 9){ sh++; if (c.classList.contains("L")) gl++; } });
    var mk = spot.querySelector(".you") || document.createElementNS("http://www.w3.org/2000/svg", "circle"); mk.setAttribute("class", "you"); mk.setAttribute("r", "3"); mk.setAttribute("cx", p.x.toFixed(1)); mk.setAttribute("cy", p.y.toFixed(1)); spot.appendChild(mk);
    var d = Math.round(Math.hypot(120 - X, 40 - Y) * 0.9144);
    $("#spotr").textContent = sh ? "من هنا (على بعد " + d + " متر من المرمى) سدد ميسي " + sh + " مرة وسجل " + gl + (gl ? " (" + Math.round(gl / sh * 100) + "٪)" : "") + "." : "ميسي ما سدد من هالمكان في بياناتنا. جرّب أقرب للمنطقة."; });

  // ---- where will he shoot: six zones of the goal mouth
  (function(){ var el = $("#guess"), G = DATA.game || []; if (!el || !G.length) return; var score = [0, 0];
    function zone(g){ return (g[2] < 38.7 ? 0 : g[2] > 41.3 ? 2 : 1) + (g[3] > 1.2 ? 3 : 0); }
    var LBL = ["يسار تحت", "النص تحت", "يمين تحت", "يسار فوق", "النص فوق", "يمين فوق"];
    function round(){ var g = G[Math.floor(Math.random() * G.length)];
      var a = g[1], b = 120 - g[0]; el.innerHTML = '<svg class="mp sm" viewBox="-1 -3 82 64" aria-hidden="true"><rect x="0" y="0" width="80" height="60" class="g"/><path class="l" d="M0 0H80M18 0V18H62V0M30 0V6H50V0"/><circle cx="' + a.toFixed(1) + '" cy="' + b.toFixed(1) + '" r="1.6" class="pt L"/></svg>' +
        '<div class="gz" role="group" aria-label="وين راحت الكورة">' + [3, 4, 5, 0, 1, 2].map(function(z){ return '<button type="button" data-z="' + z + '">' + LBL[z] + "</button>"; }).join("") + '</div><p class="small" aria-live="polite"></p>';
      el.querySelectorAll("[data-z]").forEach(function(b){ b.onclick = function(){ var ok = +b.dataset.z === zone(g); score[0] += ok ? 1 : 0; score[1]++;
        el.querySelector('[data-z="' + zone(g) + '"]').classList.add("right"); if (!ok) b.classList.add("wrong"); el.querySelectorAll("[data-z]").forEach(function(x){ x.disabled = true; });
        el.querySelector("p").innerHTML = (ok ? "صح! " : "لا، راحت " + LBL[zone(g)] + ". ") + esc(g[4]) + " ضد " + esc(nm(g[5])) + "، الدقيقة " + g[6] + " · نتيجتك " + score[0] + " من " + score[1] + ' <button type="button" class="lnk" id="gnext">اللي بعده</button>';
        $("#gnext").onclick = round; }; }); }
    round(); })();

  // ---- the quiz (questions built from the data at build time; answers shuffled here)
  (function(){ var el = $("#quiz"), Q = DATA.quiz || []; if (!el || !Q.length) return; var i = 0, right = 0;
    function show(){ if (i >= Q.length){ el.innerHTML = "<p><b>" + right + " من " + Q.length + "</b>" + (right === Q.length ? " · تعرف ميسي مثل ما يعرف الكورة." : "") + ' <button type="button" class="lnk" id="qagain">من جديد</button></p>'; $("#qagain").onclick = function(){ i = 0; right = 0; show(); }; return; }
      var q = Q[i], opts = q.a.map(function(a, k){ return [a, k === q.c]; }).sort(function(){ return Math.random() - 0.5; });
      el.innerHTML = '<p class="qq">' + esc(q.q) + '</p><div class="qa">' + opts.map(function(o, k){ return '<button type="button" data-k="' + k + '">' + esc(o[0]) + "</button>"; }).join("") + "</div>";
      el.querySelectorAll("[data-k]").forEach(function(b){ b.onclick = function(){ var ok = opts[+b.dataset.k][1]; if (ok) right++; b.classList.add(ok ? "right" : "wrong");
        el.querySelectorAll("[data-k]").forEach(function(x, k){ x.disabled = true; if (opts[k][1]) x.classList.add("right"); }); setTimeout(function(){ i++; show(); }, 1100); }; }); }
    show(); })();

  // ---- this day in his career (UAE date)
  (function(){ var el = $("#today"), D = DATA.days || {}; if (!el) return; var d = new Date(Date.now() + 4 * 3600e3).toISOString().slice(5, 10), L = D[d] || [];
    el.innerHTML = L.length ? "<ul class=\"mlist\">" + L.sort(function(a, b){ return a[0] - b[0]; }).map(function(x){ return "<li>" + x[0] + " · هدف ضد " + esc(nm(x[1])) + " في الدقيقة " + x[2] + (x[3] ? " (مع الأرجنتين)" : "") + "</li>"; }).join("") + "</ul>"
      : '<p class="small">ما سجل ميسي في مثل هاليوم في بياناتنا. ارجع بكرة.</p>'; })();

  // ---- the world map of his international goals (d3-geo + world-atlas from jsDelivr; the list stays if they fail)
  (function(){ var el = $("#mmap"); if (!el) return; when(el, function(){
    var C = {}; try { C = JSON.parse(el.dataset.c || "{}"); } catch (e){}
    var ALIAS = { "United States":"United States of America", "Bolivia":"Bolivia", "Venezuela":"Venezuela", "Russia":"Russia", "South Korea":"South Korea", "Czech Republic":"Czechia", "Bosnia and Herzegovina":"Bosnia and Herz." };
    Promise.all([import("https://cdn.jsdelivr.net/npm/d3-geo@3/+esm"), import("https://cdn.jsdelivr.net/npm/topojson-client@3/+esm"), fetch("https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json").then(function(r){ return r.json(); })]).then(function(x){
      var geo = x[0], topo = x[1], w = x[2], land = topo.feature(w, w.objects.countries), proj = geo.geoNaturalEarth1().fitSize([600, 320], land), path = geo.geoPath(proj);
      var by = {}; land.features.forEach(function(f){ by[f.properties.name] = f; }); var mx = Math.max.apply(null, Object.values(C).concat([1]));
      var dots = Object.keys(C).map(function(k){ var f = by[ALIAS[k] || k]; if (!f) return ""; var c = path.centroid(f); if (!isFinite(c[0])) return ""; return '<circle cx="' + c[0].toFixed(1) + '" cy="' + c[1].toFixed(1) + '" r="' + (3 + Math.sqrt(C[k] / mx) * 14).toFixed(1) + '" class="md"><title>' + esc(k) + ": " + C[k] + "</title></circle>"; }).join("");
      el.insertAdjacentHTML("afterbegin", '<svg class="wmap" viewBox="0 0 600 320" role="img" aria-label="خريطة أهدافه الدولية"><path d="' + path(land) + '" class="land"/>' + dots + "</svg>");
    }).catch(function(){}); }); })();
})();
