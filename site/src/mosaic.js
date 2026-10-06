/* تيفو «اصنع التيفو» (bold idea 1, owner 2026-10-06): during a match every fan on the site raises one card for his side, and the
   two crests fill in card by card in front of everyone: the more fans, the clearer the crest; a goal makes the scoring side's
   whole stand erupt. Server: saas/cards src/tifo_fans.py (POST /api/tifo/fans/tile, GET /api/tifo/fans/tiles?match=, the
   counts cached 10 s at the edge: site/template.yaml ApiFansCache).
   Each crest is its own image (/logo/<id>.png, same origin) read into an N×N grid (the club's colour where the crest is
   transparent); the cards light in one shuffled order seeded by the match and the side, so every fan sees the same stand, his
   own card ringed. The device key is a random string in localStorage (tifo.fan), never an account; the card it raised is
   remembered per match (tifo.fan.<id>). Open from 3 h before kickoff until 2 h after the end, as the server; drawn on the v5
   match page under «توقعك للنتيجة», on the v5 tokens. Copy: light Emirati, Western digits. */
(function () {
  "use strict";
  var D = document, B = D.body;
  if (!B || B.dataset.page !== "match" || !window.fetch || !window.HTMLCanvasElement) return;
  var V = window.V5 || {}, MID = +(V.id || B.dataset.id || 0);
  if (!MID || !V.h || !V.a || !V.ko) return;
  var N = 24, CELL = 6, GAP = 1, API = "/api/tifo/fans/", POLL = 20000, HOUR = 36e5;
  var RM = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  var ls = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var status = V.status || "scheduled";

  function isOpen() {
    var ko = Date.parse(V.ko), t = Date.now();
    if (!ko || /postponed|cancelled|abandoned/.test(status)) return false;
    if (t < ko - 3 * HOUR) return false;
    if (status === "finished" || status === "awarded") return t < ko + 4 * HOUR;
    return t < ko + 6 * HOUR;
  }
  if (!isOpen()) return;

  // ------------------------------------------------------------------ the stand: one shuffled order per side
  function order(seed) {
    var a = [], i, s = seed >>> 0;
    var rnd = function () { s = (s + 0x6D2B79F5) | 0; var t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    for (i = 0; i < N * N; i++) a.push(i);
    for (i = a.length - 1; i > 0; i--) { var j = Math.floor(rnd() * (i + 1)), x = a[i]; a[i] = a[j]; a[j] = x; }
    return a;
  }
  var hex = function (c) { c = String(c || "#8E8E93").replace("#", ""); if (c.length === 3) c = c.replace(/./g, "$&$&"); return [parseInt(c.slice(0, 2), 16) || 0, parseInt(c.slice(2, 4), 16) || 0, parseInt(c.slice(4, 6), 16) || 0]; };
  var S = {};
  ["h", "a"].forEach(function (k, n) {
    var id = k === "h" ? V.h : V.a, tc = (window.TC || {})[id] || [];
    S[k] = { id: id, name: k === "h" ? V.hn : V.an, order: order(MID * 2 + n + 7), count: 0, cells: null, club: hex(tc[0] || (n ? "#3A3A3C" : "#8E8E93")), canvas: null, flash: 0 };
  });

  // the crest into N×N colours: the image's own colour where it is drawn, the club's colour where it is transparent; a crest
  // that does not load leaves two bands of the club's colours
  function cells(side, done) {
    var s = S[side], fill = function (px) { s.cells = px; done(); };
    var img = new Image();
    img.onload = function () {
      try {
        var c = D.createElement("canvas"); c.width = c.height = N;
        var x = c.getContext("2d"); x.fillStyle = "rgb(" + s.club.join(",") + ")"; x.fillRect(0, 0, N, N);
        var pad = 2; x.drawImage(img, pad, pad, N - 2 * pad, N - 2 * pad);
        var d = x.getImageData(0, 0, N, N).data, px = [];
        for (var i = 0; i < N * N; i++) px.push([d[i * 4], d[i * 4 + 1], d[i * 4 + 2]]);
        fill(px);
      } catch (e) { fill(bands(s)); }
    };
    img.onerror = function () { fill(bands(s)); };
    img.src = "/logo/" + s.id + ".png";
  }
  function bands(s) {
    var tc = (window.TC || {})[s.id] || [], a = s.club, b = hex(tc[1] || "#F2F2F7"), px = [];
    for (var y = 0; y < N; y++) for (var x = 0; x < N; x++) px.push(((x + y) >> 2) % 2 ? b : a);
    return px;
  }

  // ------------------------------------------------------------------ drawing
  var SIZE = N * (CELL + GAP) + GAP, DPR = Math.min(2, window.devicePixelRatio || 1);
  function draw(side) {
    var s = S[side], c = s.canvas; if (!c || !s.cells) return;
    var x = c.getContext("2d"), lit = {}, n = Math.min(s.count, N * N), mine = myCard(side), now = Date.now();
    for (var k = 0; k < n; k++) lit[s.order[k]] = 1;
    var me = mine ? s.order[(mine.i - 1) % (N * N)] : -1;
    // a goal: a wave from the middle of the stand lights every card for a moment (one flash when motion is reduced)
    var f = s.flash && now < s.flash ? 1 - (s.flash - now) / 1600 : -1;
    x.setTransform(DPR, 0, 0, DPR, 0, 0); x.clearRect(0, 0, SIZE, SIZE);
    for (var i = 0; i < N * N; i++) {
      var cx = i % N, cy = (i / N) | 0, p = s.cells[i], on = !!lit[i];
      if (f >= 0) { var d = Math.hypot(cx - N / 2, cy - N / 2) / (N * 0.72); if (RM || Math.abs(f - d) < 0.22) on = true; }
      x.globalAlpha = on ? 1 : 0.16;
      x.fillStyle = "rgb(" + p[0] + "," + p[1] + "," + p[2] + ")";
      x.fillRect(GAP + cx * (CELL + GAP), GAP + cy * (CELL + GAP), CELL, CELL);
    }
    x.globalAlpha = 1;
    if (me >= 0) {
      x.lineWidth = 1.5; x.strokeStyle = getComputedStyle(D.documentElement).getPropertyValue("--accent").trim() || "#0B8246";
      x.strokeRect(GAP + (me % N) * (CELL + GAP) - 1, GAP + ((me / N) | 0) * (CELL + GAP) - 1, CELL + 2, CELL + 2);
    }
    if (f >= 0 && f < 1) requestAnimationFrame(function () { draw(side); }); else s.flash = 0;
  }
  function erupt(side) {
    S[side].flash = Date.now() + (RM ? 600 : 1600); draw(side);
    setTimeout(function () { draw(side); }, RM ? 650 : 1650);   // the stand settles even where animation frames are paused (a tab in the background)
  }

  // ------------------------------------------------------------------ the device, its card, the counts
  function dev() {
    var k = ls.get("tifo.fan");
    if (!k || !/^[A-Za-z0-9_-]{16,64}$/.test(k)) {
      var a = new Uint8Array(18); (window.crypto || {}).getRandomValues ? crypto.getRandomValues(a) : a.forEach(function (_, i) { a[i] = Math.random() * 256; });
      k = "f" + Array.prototype.map.call(a, function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
      ls.set("tifo.fan", k);
    }
    return k;
  }
  function cards(n) { return n === 0 ? "ما في كروت للحين" : n === 1 ? "كرت واحد" : n === 2 ? "كرتين" : n <= 10 ? n + " كروت" : n + " كرت"; }
  function myCard(side) { try { var c = JSON.parse(ls.get("tifo.fan." + MID) || "null"); return c && (!side || c.side === side) ? c : null; } catch (e) { return null; } }
  function counts(j) {
    if (!j) return;
    S.h.count = +j.h || 0; S.a.count = +j.a || 0;
    ["h", "a"].forEach(function (k) { var b = D.getElementById("fm-n-" + k); if (b) b.textContent = cards(S[k].count); draw(k); });
  }
  function poll() {
    if (D.hidden) return;
    fetch(API + "tiles?match=" + MID).then(function (r) { return r.ok ? r.json() : null; }).then(counts).catch(function () {});
  }
  function raise(side, btn) {
    var acts = D.getElementById("fm-acts"), msg = D.getElementById("fm-msg");
    if (acts) [].forEach.call(acts.querySelectorAll("button"), function (b) { b.disabled = true; });
    fetch(API + "tile", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ match: MID, side: side, dev: dev() }) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (x) {
        if (!x.ok) throw new Error((x.j && x.j.error) || "");
        ls.set("tifo.fan." + MID, JSON.stringify({ side: x.j.side, i: x.j.i }));
        counts(x.j); mine();
      })
      .catch(function (e) {
        if (acts) [].forEach.call(acts.querySelectorAll("button"), function (b) { b.disabled = false; });
        if (msg) msg.textContent = e && e.message ? e.message : "ما قدرنا نرفع كرتك، جرّب بعد شوي";
      });
  }
  function mine() {
    var c = myCard(), acts = D.getElementById("fm-acts"), msg = D.getElementById("fm-msg");
    if (!c) return;
    if (acts) acts.hidden = true;
    if (msg) msg.textContent = "كرتك رقم " + c.i + " في مدرج " + (S[c.side] ? S[c.side].name : "") + ". خلّ ربعك يرفعون كروتهم.";
    draw("h"); draw("a");
  }

  // ------------------------------------------------------------------ the block
  var css = D.createElement("style"); css.id = "fm-css";
  css.textContent = "#fanmosaic .fm-row{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:14px 12px 4px}" +
    "#fanmosaic figure{margin:0;text-align:center}#fanmosaic canvas{display:block;width:100%;max-width:200px;height:auto;margin:0 auto;border-radius:var(--r-s,10px);background:var(--fill3,#7676801f)}" +
    "#fanmosaic figcaption{margin-top:8px;color:var(--label2,#6b6b70);font-size:13px}#fanmosaic figcaption b{display:block;color:var(--label,#000);font-size:15px;font-weight:600}" +
    "#fanmosaic .fm-acts{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;padding:8px 12px 4px}#fanmosaic .fm-msg{margin:0;padding:6px 16px 14px;text-align:center;color:var(--label,#000);font-size:14px;line-height:20px}";
  D.head.appendChild(css);
  var sec = D.createElement("section"); sec.className = "grp"; sec.id = "fanmosaic";
  sec.innerHTML = '<div class="gh"><h2>اصنع التيفو</h2></div><div class="card"><div class="fm-row">' +
    ["h", "a"].map(function (k) { return '<figure><canvas width="' + SIZE * DPR + '" height="' + SIZE * DPR + '" data-fm="' + k + '" role="img" aria-label="' + esc("مدرج " + (S[k].name || "")) + '"></canvas><figcaption><b>' + esc(S[k].name || "") + '</b><span id="fm-n-' + k + '" class="num">ما في كروت للحين</span></figcaption></figure>'; }).join("") +
    '</div><div class="fm-acts" id="fm-acts">' + ["h", "a"].map(function (k) { return '<button type="button" class="pill" data-side="' + k + '">أنا مع ' + esc(S[k].name || "") + "</button>"; }).join("") +
    '</div><p class="fm-msg" id="fm-msg" aria-live="polite">ارفع كرتك مع فريقك: كل ما زاد الجمهور، وضح الشعار.</p></div>';
  var after = D.querySelector("[data-predict]") || (D.getElementById("ev") && D.getElementById("ev").closest("section"));
  var pane = D.querySelector('.pane[data-p="ov"]');
  if (after && after.parentNode) after.parentNode.insertBefore(sec, after.nextSibling);
  else if (pane) pane.insertBefore(sec, pane.firstChild);
  else return;
  ["h", "a"].forEach(function (k) { S[k].canvas = sec.querySelector('canvas[data-fm="' + k + '"]'); cells(k, function () { draw(k); }); });
  sec.addEventListener("click", function (e) { var b = e.target.closest && e.target.closest("button[data-side]"); if (b) raise(b.dataset.side, b); });
  mine(); poll();
  setInterval(poll, POLL);
  D.addEventListener("visibilitychange", function () { if (!D.hidden) poll(); });

  // a goal on the page's live data (v5's app.js fires tifo:match with the match file on every poll); counted from the first
  // poll's score, not the page's: the page is built up to an hour earlier, and a goal in between must not erupt on opening it
  var last = null;
  D.addEventListener("tifo:match", function (e) {
    var md = e.detail || {}, sc = md.score; if (md.status) status = md.status;
    if (!sc) return;
    var now = { h: +sc.home || 0, a: +sc.away || 0 };
    if (last) { if (now.h > last.h) erupt("h"); if (now.a > last.a) erupt("a"); }
    last = now;
  });
})();
