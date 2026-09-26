/* The stand — تيفو's one signature moment (site/DESIGN.md). The featured match drawn as a tifo: a stand of fans each holding
   one flat card. Home colours on the RIGHT, away on the LEFT (RTL), the score or kickoff in chalk pixel digits in the middle.
   Motion answers something only: the load-in flips the cards right->left once; a touch sends a wave out from that point;
   a goal (score change in live data) sends a wave across the whole stand from the scoring side. Nothing animates when idle.
   prefers-reduced-motion -> the same mosaic, drawn once, static. Canvas 2D, redraws only while a wave is running. */
(function(){
  "use strict";
  var FONT = { "0":"111101101101111", "1":"010110010010111", "2":"111001111100111", "3":"111001111001111", "4":"101101111001001", "5":"111100111001111", "6":"111100111101111", "7":"111001001001001", "8":"111101111101111", "9":"111101111001111", "-":"000000111000000", ":":"000010000010000", " ":"000000000000000" };
  var RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var NIGHT = "#0A2620", CHALK = "#F6F7F2";
  function hex(c){ c = (c || "#5C6660").replace("#", ""); return [parseInt(c.slice(0, 2), 16), parseInt(c.slice(2, 4), 16), parseInt(c.slice(4, 6), 16)]; }
  function rgb(a, k){ return "rgb(" + Math.max(0, Math.min(255, a[0] * k | 0)) + "," + Math.max(0, Math.min(255, a[1] * k | 0)) + "," + Math.max(0, Math.min(255, a[2] * k | 0)) + ")"; }
  function lum(a){ return (0.299 * a[0] + 0.587 * a[1] + 0.114 * a[2]) / 255; }
  function Stand(canvas){
    this.c = canvas; this.x = canvas.getContext("2d"); this.cells = []; this.t0 = 0; this.run = false; this.waves = [];
    var self = this;
    canvas.addEventListener("pointerdown", function(e){ var r = canvas.getBoundingClientRect(); self.wave((e.clientX - r.left) / self.cs, (e.clientY - r.top) / self.cs, 0.9); });
    window.addEventListener("resize", function(){ clearTimeout(self.rt); self.rt = setTimeout(function(){ self.layout(); self.draw(performance.now()); }, 150); });
  }
  Stand.prototype.set = function(m){
    var prev = this.m; this.m = m; var TC = window.TC || {};
    this.hc = (TC[m.home.id] || ["#8A938D", "#F6F7F2"]).map(hex); this.ac = (TC[m.away.id] || ["#3D4A44", "#F6F7F2"]).map(hex);
    var s = m.score, txt = s ? s.away + " - " + s.home : (m.kickoff_uae || "").slice(11, 16);   // drawn left->right: away on the left, home on the right
    this.txt = txt.replace(/ /g, "");
    this.layout();
    if (!prev) { this.intro(); return; }
    if (prev.score && s && (s.home !== prev.score.home || s.away !== prev.score.away)){ this.wave(s.home > prev.score.home ? this.cols : 0, this.rows / 2, 1.6); }
    else this.draw(performance.now());
  };
  Stand.prototype.layout = function(){
    var c = this.c, w = c.clientWidth, h = c.clientHeight, dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = w * dpr; c.height = h * dpr; this.x.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.cs = w < 500 ? 8 : w < 900 ? 10 : 12; this.cols = Math.ceil(w / this.cs); this.rows = Math.ceil(h / this.cs);
    var cols = this.cols, rows = this.rows, cells = [], mid = cols / 2;
    // digits block: pixel font scaled so the text is ~5 cells per unit row, centred
    var g = this.txt.split(""), units = g.length * 4 - 1, scale = Math.max(1, Math.min(Math.floor(rows * 0.6 / 5), Math.floor(cols * 0.42 / units))), gw = 3 * scale, gap = scale, tw = g.length * gw + (g.length - 1) * gap, th = 5 * scale;
    var ox = Math.round(mid - tw / 2), oy = Math.round(rows / 2 - th / 2), pad = scale + 1, digit = {};
    g.forEach(function(ch, i){ var f = FONT[ch] || FONT[" "]; for (var yy = 0; yy < 5; yy++) for (var xx = 0; xx < 3; xx++) if (f[yy * 3 + xx] === "1") for (var sy = 0; sy < scale; sy++) for (var sx = 0; sx < scale; sx++) digit[(ox + i * (gw + gap) + xx * scale + sx) + "," + (oy + yy * scale + sy)] = 1; });
    var hc = this.hc, ac = this.ac, seed = 7;
    function rnd(){ seed = (seed * 16807) % 2147483647; return seed / 2147483647; }
    for (var y = 0; y < rows; y++) for (var x = 0; x < cols; x++){
      var inPanel = x >= ox - pad && x < ox + tw + pad && y >= oy - pad && y < oy + th + pad;
      var home = x >= mid, pal = home ? hc : ac, stripe = ((home ? cols - x : x) + y) % 7 < 2;   // diagonal supporter stripes
      var base = pal[stripe && pal[1] ? 1 : 0], col, k = 0.9 + rnd() * 0.18;
      if (inPanel) col = digit[x + "," + y] ? CHALK : NIGHT;
      else col = rgb(base, lum(base) > 0.85 ? k * 0.92 : k);
      cells.push({ x:x, y:y, col:col, d:(cols - 1 - x) / cols * 0.9 + rnd() * 0.12, p:inPanel });
    }
    this.cells = cells;
  };
  Stand.prototype.intro = function(){ if (RM){ this.draw(0, true); return; } this.t0 = performance.now(); this.introOn = true; this.loop(); };
  Stand.prototype.wave = function(cx, cy, amp){ if (RM) return; this.waves.push({ cx:cx, cy:cy, t:performance.now(), amp:amp }); this.loop(); };
  Stand.prototype.loop = function(){ if (this.run) return; this.run = true; var self = this; requestAnimationFrame(function f(now){ var more = self.draw(now); if (more) requestAnimationFrame(f); else self.run = false; }); };
  Stand.prototype.draw = function(now, still){
    var x = this.x, cs = this.cs, active = false, gapPx = 1.2;
    x.fillStyle = NIGHT; x.fillRect(0, 0, this.c.clientWidth, this.c.clientHeight);
    var intro = this.introOn && !still ? (now - this.t0) / 1000 : 9, waves = this.waves.filter(function(w){ return now - w.t < 2600; });
    this.waves = waves; if (intro < 1.6 || waves.length) active = true; else this.introOn = false;
    for (var i = 0; i < this.cells.length; i++){
      var c = this.cells[i], sy = 1, lift = 0;
      if (intro < 1.6){ var p = Math.min(1, Math.max(0, (intro - c.d) / 0.35)); sy = p < 1 ? Math.abs(Math.cos((1 - p) * Math.PI / 2 * 2)) * p : 1; if (p <= 0) continue; }
      for (var j = 0; j < waves.length; j++){ var w = waves[j], dist = Math.hypot(c.x - w.cx, (c.y - w.cy) * 1.4), ph = (now - w.t) / 1000 * 38 - dist; if (ph > 0 && ph < 6){ var s = Math.sin(ph / 6 * Math.PI); sy *= 1 - 0.85 * s * Math.min(1, w.amp); lift = Math.max(lift, s * w.amp); } }
      var hgt = (cs - gapPx) * sy, top = c.y * cs + (cs - gapPx - hgt) / 2 - lift * 2.5;
      x.fillStyle = c.col; x.fillRect(c.x * cs, top, cs - gapPx, Math.max(0.6, hgt));
    }
    return active;
  };
  window.TifoStand = { mount:function(canvas){ return new Stand(canvas); } };
})();
