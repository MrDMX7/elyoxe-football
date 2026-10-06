/* تيفو «الكرة الحين» (owner bold idea 3, 2026-10-06): a globe on the home page where the world's live matches glow, and a goal
   lights up its place the moment the score moves. No library: Natural Earth's land as dots (site/lib/globe.cjs, built hourly,
   /assets/globe.<v>.json: dots, a point per competition and per national team), projected orthographically on a canvas.
   The live rows come from /v1/all/live.json (the poller, every 30 s at the edge; FotMob's whole day and 365Scores' Arab
   leagues); a goal is a score higher than the last read. A competition stands at its country's label point, an
   international match at its home side's country, so matches of one country are spread a little around it. The globe
   turns slowly (still when motion is reduced), and turns toward a new goal; it starts drawing only near the screen and
   reads only while the page is visible. Tap a light: the match page (Tifo's own competitions) or /live/?id= for any other.
   On the v5 tokens; light Emirati, Western digits; a score between two names is one dir="rtl" run «2 - 1». */
(function () {
  "use strict";
  var D = document, B = D.body, V = window.V5 || {};
  if (!B || !V.globe || !window.fetch || !window.HTMLCanvasElement) return;
  var RM = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var G = null, ROWS = [], LAST = {}, GOALS = [], RINGS = [], OURS = {}, INTL = {}, RAD = Math.PI / 180;
  var rot = 35, tilt = 18, aim = null, cv = null, ctx = null, size = 0, dpr = Math.min(2, window.devicePixelRatio || 1), running = false, seen = false;

  // ------------------------------------------------------------------ the block, before the world's list
  var css = D.createElement("style"); css.id = "gl-css";
  css.textContent = "#globe .gl-card{padding:14px 12px 10px}#globe canvas{display:block;width:100%;max-width:300px;aspect-ratio:1;margin:0 auto;touch-action:manipulation}" +
    "#globe .gl-tick{margin:10px 4px 2px;min-height:40px}#globe .gl-g{display:flex;align-items:baseline;gap:6px;margin:2px 0;color:var(--label,#000);font-size:14px;line-height:20px}" +
    "#globe .gl-g b{color:var(--accent,#0B8246)}#globe .gl-g small{color:var(--label2,#6b6b70)}#globe .gl-q{margin:0;color:var(--label2,#6b6b70);font-size:13px;text-align:center}";
  D.head.appendChild(css);
  var sec = D.createElement("section"); sec.className = "grp"; sec.id = "globe";
  sec.innerHTML = '<div class="gh"><h2>الكرة الحين</h2><span class="num" id="gl-n"></span></div><div class="card gl-card"><canvas id="gl-c" role="img" aria-label="المباريات المباشرة حول العالم على الكرة الأرضية"></canvas>' +
    '<div class="gl-tick" id="gl-tick" aria-live="polite"><p class="gl-q">الأهداف تضوي على الكرة لحظة تسجيلها.</p></div></div>';
  var world = D.getElementById("world"), list = D.getElementById("homelist");
  if (world && world.parentNode) world.parentNode.insertBefore(sec, world);
  else if (list && list.parentNode) list.parentNode.insertBefore(sec, list.nextSibling);
  else return;
  cv = sec.querySelector("canvas"); ctx = cv.getContext("2d");

  // ------------------------------------------------------------------ data
  var hash = function (n) { n = (+n || 0) ^ 0x9e3779b9; n = Math.imul(n ^ (n >>> 16), 0x45d9f3b); n = Math.imul(n ^ (n >>> 16), 0x45d9f3b); return ((n ^ (n >>> 16)) >>> 0) / 4294967296; };
  function where(r) {
    var p = INTL[r.lg] ? (G.nt[r.home[0]] || G.nt[r.away[0]]) : G.lg[r.lg];
    if (!p) return null;
    var a = hash(r.id) * 2 * Math.PI, d = 0.6 + hash(r.id + 7) * 1.8;   // matches of one country spread a little around its point
    return [p[0] + Math.sin(a) * d, p[1] + Math.cos(a) * d / Math.max(0.3, Math.cos(p[0] * RAD))];
  }
  var isLive = function (r) { return r.status === "live" || r.status === "ht"; };
  function read() {
    if (D.hidden) return;
    fetch("/v1/all/live.json", { cache: "no-cache" }).then(function (x) { return x.ok ? x.json() : null; }).then(function (j) {
      if (!j) return;
      ROWS = (j.matches || []).filter(isLive).map(function (r) { return { id: r.id, lg: r.lg, home: r.home, away: r.away, minute: r.minute, at: where(r) }; }).filter(function (r) { return r.at; });
      ROWS.forEach(function (r) {
        var s = [+r.home[2] || 0, +r.away[2] || 0], was = LAST[r.id];
        if (was && (s[0] > was[0] || s[1] > was[1])) goal(r, s[0] > was[0] ? "h" : "a");
        LAST[r.id] = s;
      });
      var n = D.getElementById("gl-n"); if (n) n.textContent = !ROWS.length ? "ما في مباريات مباشرة الحين" : ROWS.length === 1 ? "مباراة وحدة مباشرة" : ROWS.length === 2 ? "مباراتين مباشرتين" : ROWS.length <= 10 ? ROWS.length + " مباريات مباشرة" : ROWS.length + " مباراة مباشرة";
      if (!running) frame();
    }).catch(function () {});
  }
  function goal(r, side) {
    var t = side === "h" ? r.home : r.away;
    GOALS.unshift({ r: r, t: t, at: Date.now() }); GOALS = GOALS.slice(0, 3);
    RINGS.push({ at: r.at, t0: Date.now() });
    aim = r.at[1];
    var tick = D.getElementById("gl-tick");
    if (tick) tick.innerHTML = GOALS.map(function (g) {
      var h = g.r.home, a = g.r.away;
      return '<p class="gl-g"><b>هدف</b><span>' + esc(h[1]) + ' <bdi dir="rtl" class="num">' + (+h[2] || 0) + " - " + (+a[2] || 0) + "</bdi> " + esc(a[1]) + "</span>" + (g.r.minute ? '<small class="num">' + esc(g.r.minute) + "'</small>" : "") + "</p>";
    }).join("");
  }

  // ------------------------------------------------------------------ drawing
  function resize() { var w = cv.getBoundingClientRect().width || 280; size = w; cv.width = Math.round(w * dpr); cv.height = Math.round(w * dpr); }
  function proj(lat, lon) {   // orthographic, the view centred on (tilt, rot): [x, y, front]
    var p = lat * RAD, l = (lon - rot) * RAD, p0 = tilt * RAD, cp = Math.cos(p);
    var x = cp * Math.sin(l), y = Math.cos(p0) * Math.sin(p) - Math.sin(p0) * cp * Math.cos(l), z = Math.sin(p0) * Math.sin(p) + Math.cos(p0) * cp * Math.cos(l);
    return [x, -y, z];
  }
  var col = function (v, f) { var c = getComputedStyle(D.documentElement).getPropertyValue(v).trim(); return c || f; };
  var C = null;
  function draw() {
    if (!C) C = { land: col("--label3", "#8E8E93"), dot: col("--accent", "#0B8246"), ring: col("--live", "#FF3B30"), edge: col("--sep", "#C6C6C8") };
    var r = size / 2 - 4, cx = size / 2, cy = size / 2, now = Date.now();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, size, size);
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, 2 * Math.PI); ctx.strokeStyle = C.edge; ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = C.land;
    for (var i = 0; i < G.d.length; i++) {
      var q = proj(G.d[i][0] / 10, G.d[i][1] / 10); if (q[2] <= 0) continue;
      ctx.globalAlpha = 0.25 + 0.5 * q[2]; ctx.fillRect(cx + q[0] * r - 0.8, cy + q[1] * r - 0.8, 1.6, 1.6);
    }
    var pulse = RM ? 1 : 0.6 + 0.4 * Math.sin(now / 420);
    ctx.fillStyle = C.dot;
    ROWS.forEach(function (m) { var q = proj(m.at[0], m.at[1]); if (q[2] <= 0) return; ctx.globalAlpha = 0.5 + 0.5 * pulse * q[2]; ctx.beginPath(); ctx.arc(cx + q[0] * r, cy + q[1] * r, 2.6, 0, 2 * Math.PI); ctx.fill(); });
    ctx.strokeStyle = C.ring; ctx.lineWidth = 2;
    RINGS = RINGS.filter(function (g) { return now - g.t0 < 4000; });
    RINGS.forEach(function (g) { var q = proj(g.at[0], g.at[1]); if (q[2] <= 0) return; var k = (now - g.t0) / 4000;
      for (var w = 0; w < 2; w++) { var kk = (k + w * 0.35) % 1; ctx.globalAlpha = (1 - kk) * q[2]; ctx.beginPath(); ctx.arc(cx + q[0] * r, cy + q[1] * r, 3 + kk * 22, 0, 2 * Math.PI); ctx.stroke(); } });
    ctx.globalAlpha = 1;
  }
  function frame() {
    running = true;
    if (D.hidden || !seen) { running = false; return; }
    if (aim != null) { var d = ((aim - rot + 540) % 360) - 180; rot += d * 0.06; if (Math.abs(d) < 0.5) aim = null; }
    else if (!RM) rot = (rot + 0.06) % 360;
    draw();
    if (RM && !RINGS.length) { running = false; return; }
    requestAnimationFrame(frame);
  }
  cv.addEventListener("click", function (e) {
    var b = cv.getBoundingClientRect(), x = e.clientX - b.left, y = e.clientY - b.top, r = size / 2 - 4, best = null, bd = 18;
    ROWS.forEach(function (m) { var q = proj(m.at[0], m.at[1]); if (q[2] <= 0) return; var d = Math.hypot(size / 2 + q[0] * r - x, size / 2 + q[1] * r - y); if (d < bd) { bd = d; best = m; } });
    if (best) location.href = OURS[best.lg] ? "/m/" + best.id + "/" : "/live/?id=" + encodeURIComponent(best.id);
  });

  // ------------------------------------------------------------------ start near the screen
  function start() {
    if (G) return;
    fetch(V.globe).then(function (x) { return x.json(); }).then(function (j) {
      G = j; (j.ours || []).forEach(function (id) { OURS[id] = 1; }); (j.intl || []).forEach(function (id) { INTL[id] = 1; });
      resize(); read(); setInterval(read, 30000);
    }).catch(function () {});
  }
  var io = "IntersectionObserver" in window ? new IntersectionObserver(function (es) {
    es.forEach(function (e) { seen = e.isIntersecting; if (seen) { start(); if (G && !running) frame(); } });
  }, { rootMargin: "300px 0px" }) : null;
  if (io) io.observe(sec); else { seen = true; start(); }
  addEventListener("resize", function () { if (G) { resize(); draw(); } });
  D.addEventListener("visibilitychange", function () { if (!D.hidden && G) { read(); if (!running) frame(); } });
})();
