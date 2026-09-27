/* تيفو v3 key art: the stand mosaic as the hero's backdrop (DESIGN-v3.md §2). No digits in the cards: the score is set in
   type above it. Match: home colours on the RIGHT, away on the LEFT. League: one band per club in table order, the leader on
   the right. Motion only answers: the cards flip in right->left once, a touch sends a wave, a goal sends one from the
   scorer's side. prefers-reduced-motion: drawn once, static. Canvas 2D; redraws only while something moves.
   Same API as src/stand.js (window.TifoStand.mount(canvas).set(match)), so app.js drives it unchanged. */
(function(){
  "use strict";
  var RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches, NIGHT = "#0A2620";
  function hex(c){ c = (c || "#5C6660").replace("#", ""); if (c.length === 3) c = c.replace(/./g, "$&$&"); return [parseInt(c.slice(0, 2), 16), parseInt(c.slice(2, 4), 16), parseInt(c.slice(4, 6), 16)]; }
  function lum(a){ return (0.299 * a[0] + 0.587 * a[1] + 0.114 * a[2]) / 255; }
  function rgb(a, k){ return "rgb(" + Math.max(0, Math.min(255, a[0] * k | 0)) + "," + Math.max(0, Math.min(255, a[1] * k | 0)) + "," + Math.max(0, Math.min(255, a[2] * k | 0)) + ")"; }
  // 387: calmer stand — each card ~35% toward night pitch and grey, the brightness spread halved, so the score stays the hero
  function calm(c, k){ var g = (c[0] + c[1] + c[2]) / 3, n = [10, 38, 32], kk = 0.93 + (k - 0.93) * 0.5, out = [];
    for (var i = 0; i < 3; i++){ var v = c[i] + (g - c[i]) * 0.3; v = v + (n[i] - v) * 0.35; out.push(v * kk); } return rgb(out, 1); }
  function Art(canvas){
    this.c = canvas; canvas._art = this; this.x = canvas.getContext("2d"); this.cells = []; this.waves = []; this.run = false; this.bands = [];
    var self = this;
    canvas.addEventListener("click", function(e){ var r = canvas.getBoundingClientRect(); self.wave((e.clientX - r.left) / self.cs, (e.clientY - r.top) / self.cs, 0.9); });
    window.addEventListener("resize", function(){ clearTimeout(self.rt); self.rt = setTimeout(function(){ if (self.c.clientWidth !== self.w){ self.layout(); self.paintBuf(); self.blit(1); } }, 150); });
  }
  // bands: [[colour, stripe colour], ...] from right to left
  Art.prototype.paint = function(bands, seed){ this.bands = bands.map(function(b){ return [hex(b[0]), hex(b[1] || b[0])]; }); this.seed = seed || 7; this.layout(); if (!this.shown){ this.shown = true; this.intro(); } else { this.paintBuf(); this.blit(1); } };
  Art.prototype.set = function(m){   // match
    var TC = window.TC || {}, prev = this.m; this.m = m;
    var h = TC[m.home.id] || ["#8A938D", "#F6F7F2"], a = TC[m.away.id] || ["#3D4A44", "#F6F7F2"];
    if (!prev || prev.id !== m.id) this.paint([h, a], m.id % 997 + 3);
    // a goal is the shell's card stunt (W3.2), not a wave
  };
  Art.prototype.layout = function(){
    var c = this.c, w = c.clientWidth, h = c.clientHeight, dpr = 1; this.w = w;   // W2.11: key art at DPR 1 (it sits under a scrim)
    c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); this.x.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.cs = w < 500 ? 12 : w < 1000 ? 14 : 18; this.cols = Math.ceil(w / this.cs); this.rows = Math.ceil(h / this.cs);
    var cols = this.cols, rows = this.rows, nb = this.bands.length || 1, seed = this.seed, cells = [];
    function rnd(){ seed = (seed * 16807) % 2147483647; return seed / 2147483647; }
    for (var y = 0; y < rows; y++) for (var x = 0; x < cols; x++){
      var bi = Math.min(nb - 1, Math.floor((cols - 1 - x) / cols * nb)), pal = this.bands[bi] || [hex("#5C6660"), hex("#F6F7F2")];
      var rel = (cols - 1 - x) - Math.floor(bi * cols / nb), stripe = (rel + y) % 7 < 2, base = pal[stripe ? 1 : 0], k = 0.82 + rnd() * 0.22;
      cells.push({ x:x, y:y, col:calm(base, k), d:(cols - 1 - x) / cols * 0.9 + rnd() * 0.15 });
    }
    this.cells = cells;
  };
  // the still mosaic is painted once into a buffer; the load-in is a right->left reveal of that buffer (one drawImage per
  // frame), so the intro costs almost nothing on the main thread. Only a wave (touch / goal) walks the cells.
  Art.prototype.paintBuf = function(){ var c = this.c, b = this.buf || (this.buf = document.createElement("canvas")); b.width = c.width; b.height = c.height; var x = b.getContext("2d"), dpr = c.width / (c.clientWidth || 1), cs = this.cs, gap = 2;
    x.setTransform(dpr, 0, 0, dpr, 0, 0); x.fillStyle = NIGHT; x.fillRect(0, 0, c.clientWidth, c.clientHeight);
    for (var i = 0; i < this.cells.length; i++){ var e = this.cells[i]; x.fillStyle = e.col; x.fillRect(e.x * cs, e.y * cs, cs - gap, cs - gap); } };
  // W3.1: the card raise plays on a session's first page only; after that the stand is simply there
  Art.prototype.intro = function(){ this.paintBuf(); var seen = false; try { seen = sessionStorage.getItem("tifo.raised") === "1"; sessionStorage.setItem("tifo.raised", "1"); } catch (e){} if (RM || seen){ this.blit(1); return; } var self = this, t0 = 0;
    var go = function(){ requestAnimationFrame(function f(now){ if (!t0) t0 = now; var p = Math.min(1, (now - t0) / 1100); self.blit(1 - Math.pow(1 - p, 3)); if (p < 1) requestAnimationFrame(f); }); };
    if ("requestIdleCallback" in window) requestIdleCallback(go, { timeout:600 }); else setTimeout(go, 200); };
  Art.prototype.blit = function(p){ var c = this.c, w = c.clientWidth, h = c.clientHeight, x = this.x; if (!c._on){ c._on = 1; c.classList.add("on"); if (c.parentNode) c.parentNode.classList.add("painted"); } x.fillStyle = NIGHT; x.fillRect(0, 0, w, h);
    var sx = Math.round(c.width * (1 - p)); if (c.width - sx > 0) x.drawImage(this.buf, sx, 0, c.width - sx, c.height, w * (1 - p), 0, w * p, h); };
  Art.prototype.wave = function(cx, cy, amp){ if (RM) return; this.waves.push({ cx:cx, cy:cy, t:performance.now(), amp:amp }); this.loop(); };
  Art.prototype.loop = function(){ if (this.run) return; this.run = true; var self = this; requestAnimationFrame(function f(now){ if (self.draw(now)) requestAnimationFrame(f); else self.run = false; }); };
  Art.prototype.draw = function(now, still){
    var x = this.x, cs = this.cs, gap = 2, active = false;
    x.fillStyle = NIGHT; x.fillRect(0, 0, this.c.clientWidth, this.c.clientHeight);
    var intro = 9, waves = this.waves.filter(function(w){ return now - w.t < 2600; });
    this.waves = waves; if (intro < 1.8 || waves.length) active = true; else this.introOn = false;
    var st = this.st, se = st ? (now - st.t0) / 1000 : 0; if (st && se > st.end){ this.st = st = null; } if (st) active = true;
    for (var i = 0; i < this.cells.length; i++){
      var c = this.cells[i], sy = 1, lift = 0;
      if (intro < 1.8){ var p = Math.min(1, Math.max(0, (intro - c.d) / 0.4)); if (p <= 0) continue; sy = Math.abs(Math.cos((1 - p) * Math.PI)) * p; }
      for (var j = 0; j < waves.length; j++){ var w = waves[j], dist = Math.hypot(c.x - w.cx, (c.y - w.cy) * 1.4), ph = (now - w.t) / 1000 * 38 - dist; if (ph > 0 && ph < 6){ var s = Math.sin(ph / 6 * Math.PI); sy *= 1 - 0.85 * s * Math.min(1, w.amp); lift = Math.max(lift, s * w.amp); } }
      var col = c.col;
      if (st){ var dl = (st.right ? (this.cols - 1 - c.x) : c.x) / this.cols * 0.6, fin = (se - dl) / 0.25, fout = (se - dl - 0.85 - st.hold) / 0.25;
        if (fin > 0 && fout < 1){ var on = fin >= 0.5 && fout < 0.5, ph2 = fin < 1 ? fin : fout > 0 ? fout : 1; sy *= fin < 1 || fout > 0 ? Math.abs(Math.cos(Math.min(1, ph2) * Math.PI)) : 1;
          if (on) col = st.mask[c.y * this.cols + c.x] ? "#F6F7F2" : st.col; } }
      var hgt = (cs - gap) * sy; x.fillStyle = col; x.fillRect(c.x * cs, c.y * cs + (cs - gap - hgt) / 2 - lift * 2.5, cs - gap, Math.max(0.6, hgt));
    }
    return active;
  };
  // W3.2 the card stunt: columns flip from the scorer's side into his colour and spell the new score, hold 2 s, flip back
  Art.prototype.stunt = function(fromRight, col, text){ if (RM || !this.cols) return; var m = document.createElement("canvas"); m.width = this.cols; m.height = this.rows; var g = m.getContext("2d");
    g.fillStyle = "#fff"; g.textAlign = "center"; g.textBaseline = "middle"; g.font = "700 " + Math.floor(this.rows * 0.78) + 'px "Barlow Condensed",sans-serif'; g.fillText(text, this.cols / 2, this.rows / 2 + 1);
    var d = g.getImageData(0, 0, this.cols, this.rows).data, mask = new Uint8Array(this.cols * this.rows); for (var i = 0; i < mask.length; i++) mask[i] = d[i * 4 + 3] > 110 ? 1 : 0;
    this.st = { t0:performance.now(), right:!!fromRight, col:col, mask:mask, hold:2, end:0.6 + 0.85 + 2 + 0.6 + 0.25 }; this.loop(); };
  window.TifoStand = { mount:function(canvas){ return new Art(canvas); } };
  window.TifoArt = { mount:function(canvas){ return new Art(canvas); }, of:function(canvas){ return canvas && canvas._art; } };
})();
