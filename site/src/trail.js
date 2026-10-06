/* تيفو «تيفو ريوايند» (owner bold idea 5, 2026-10-06): the season's trail, kept on the device, for the rewind stories at
   /rewind/ (src/rewind.js). On every match page: the match (teams, competition, kickoff), how many times it was opened, whether it
   was followed around its live time (from an hour before kickoff to three hours after), the goals seen go in while this page was
   open on the live match (v5's app.js fires tifo:match with the match file on every poll), and the final score once known.
   No account and nothing sent anywhere: localStorage «tifo.trail», {<match id>: {h, a, hn, an, c, cn, ko, t, v, l, g, s}}, the
   last MAX matches kept. */
(function () {
  "use strict";
  var D = document, B = D.body, V = window.V5 || {};
  if (!B || B.dataset.page !== "match" || !V.id || !V.ko || /bot|crawl|spider|lighthouse/i.test(navigator.userAgent || "")) return;
  var K = "tifo.trail", MAX = 800, KO = Date.parse(V.ko), U = window.U5;
  function load() { try { var o = JSON.parse(localStorage.getItem(K) || "{}"); return o && typeof o === "object" ? o : {}; } catch (e) { return {}; } }
  function save(o) {
    try {
      var ids = Object.keys(o);
      if (ids.length > MAX) ids.sort(function (a, b) { return (o[a].t || 0) - (o[b].t || 0); }).slice(0, ids.length - MAX).forEach(function (k) { delete o[k]; });
      localStorage.setItem(K, JSON.stringify(o));
    } catch (e) {}
  }
  var around = function (t) { return t > KO - 36e5 && t < KO + 3 * 36e5; };
  var live = function (md) { return U && U.isLive ? U.isLive(md) : /^(live|ht|1h|2h|et|pen)$/i.test(md.status || ""); };
  var now = Date.now(), o = load(), e = o[V.id] || { t: now };
  e.h = V.h; e.a = V.a; e.hn = V.hn || ""; e.an = V.an || ""; e.c = V.comp; e.cn = V.cn || e.cn || ""; e.ko = V.ko; e.v = (e.v || 0) + 1;
  if (V.live || around(now)) e.l = 1;
  if (V.status === "finished" && V.sc && V.sc[0] != null) e.s = [+V.sc[0], +V.sc[1]];
  o[V.id] = e; save(o);

  // the score to count from is the first live poll's, not the page's (built up to an hour earlier: a goal in between was not seen)
  var last = null, LIVE = e.l || 0;
  D.addEventListener("tifo:match", function (ev) {
    var md = ev.detail || {}, sc = md.score; if (!sc || sc.home == null) return;
    var cur = [+sc.home || 0, +sc.away || 0], g = last && live(md) ? Math.max(0, cur[0] - last[0]) + Math.max(0, cur[1] - last[1]) : 0;
    last = cur;
    if (!g && !(live(md) && !LIVE) && md.status !== "finished") return;   // a poll that changes nothing writes nothing (one every 20 s)
    var o = load(), e = o[V.id]; if (!e) return;
    if (g) e.g = (e.g || 0) + g;
    if (live(md)) e.l = LIVE = 1;
    if (md.status === "finished") { if (e.s && e.s[0] === cur[0] && e.s[1] === cur[1]) return; e.s = cur; }
    o[V.id] = e; save(o);
  });
})();
