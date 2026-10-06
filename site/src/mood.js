/* تيفو «نبض الجمهور» (owner bold idea 9, 2026-10-06: «عادي خله يقرا»): how each side's fans feel during the match, from their
   posts on X, read by news/xmood.js on the laptop and published as /v1/mood/<match>.json (counts only: happy, angry, tense per
   side, in 5-minute steps from kickoff, and the last 10 minutes). Here: the mood of each side now (the last 10 minutes when they
   hold 5 posts or more, else the whole match), as a word, an emoji and a bar of the three moods, then a strip of 5-minute squares
   coloured by each side's leading mood. Labelled as what it is: «من منشورات X بالعربي، تقريبي». Polled every minute from 40
   minutes before kickoff (a page opened earlier waits for it) until 4 hours after; before there are 6 posts with a mood it
   says it is collecting. Light Emirati, Western digits. */
(function () {
  "use strict";
  var D = document, B = D.body, U = window.U5, V = window.V5 || {};
  if (!B || B.dataset.page !== "match" || !U || !V.id || !V.ko || !window.fetch) return;
  var KO = Date.parse(V.ko), BOX = null, TIMER = null, HOUR = 36e5;
  var COL = { happy: "#34C759", tense: "#FF9F0A", angry: "#FF3B30" }, WORD = { happy: "فرحان", tense: "متوتر", angry: "معصّب" }, EMO = { happy: "😄", tense: "😬", angry: "😡" };
  var K3 = ["happy", "tense", "angry"], esc = U.esc;
  var of = function (arr) { return { happy: arr[0], angry: arr[1], tense: arr[2], n: arr[3] }; };
  var moodsIn = function (s) { return (s.happy || 0) + (s.tense || 0) + (s.angry || 0); };
  var lead = function (s) { var k = K3.slice().sort(function (x, y) { return (s[y] || 0) - (s[x] || 0); }); return (s[k[0]] || 0) > (s[k[1]] || 0) ? k[0] : null; };

  function mount() {
    BOX = D.createElement("section"); BOX.className = "grp"; BOX.id = "fanmood";
    var after = D.getElementById("fanmosaic") || D.getElementById("motm") || D.querySelector("[data-predict]") || (D.getElementById("ev") && D.getElementById("ev").closest("section"));
    var pane = D.querySelector('.pane[data-p="ov"]');
    if (after && after.parentNode) after.parentNode.insertBefore(BOX, after.nextSibling); else if (pane) pane.insertBefore(BOX, pane.firstChild); else { BOX = null; return false; }
    return true;
  }
  function side(name, now, total) {
    var s = moodsIn(now) >= 5 ? now : total, m = moodsIn(s), k = lead(s);
    var bar = K3.map(function (x) { var w = m ? Math.round((s[x] || 0) / m * 100) : 0; return w ? '<i style="width:' + w + "%;background:" + COL[x] + '" title="' + WORD[x] + " " + w + '%"></i>' : ""; }).join("");
    return '<div class="row"><span class="rt"><b>' + esc(name) + "</b><small>" + (k ? EMO[k] + " " + WORD[k] + (m ? " · " + Math.round((s[k] || 0) / m * 100) + "%" : "") : "ما بان مزاج واضح") + "</small></span>" +
      '<span class="rv" style="min-width:42%"><span style="display:flex;height:8px;border-radius:4px;overflow:hidden;background:var(--fill2)">' + bar + "</span>" +
      '<small style="display:block;margin-top:4px;color:var(--label2)" class="num">' + total.n + " منشور</small></span></div>";
  }
  function strip(steps, key) {
    return '<span style="display:flex;gap:2px;flex-wrap:wrap" dir="ltr">' + steps.map(function (st) {
      var s = of(st[key]), k = lead(s);
      return '<i title="' + (st.b * 5) + "'" + '" style="width:9px;height:9px;border-radius:2px;background:' + (k ? COL[k] : "var(--fill2)") + (st.b === 0 ? ";outline:1.5px solid var(--label);outline-offset:1px" : "") + '"></i>';
    }).join("") + "</span>";
  }
  function draw(j) {
    if (!j || !j.total || (!BOX && !mount())) return;
    var h = j.total.home, a = j.total.away, enough = moodsIn(h) + moodsIn(a) >= 6;
    var body = !enough ? '<div class="card lc"><p class="empty">نجمع نبض الجمهور من X… يطلع هني أول ما تتجمع منشورات كافية.</p></div>' :
      '<div class="card">' + side(h.name, j.now.home, h) + side(a.name, j.now.away, a) + "</div>" +
      (j.steps && j.steps.length > 1 ? '<div class="card lc" style="margin-top:8px"><p class="gf" style="margin:0 0 6px">كل مربع 5 دقايق، واللي عليه إطار بداية المباراة</p>' +
        '<p style="margin:0 0 4px;display:flex;align-items:center;gap:8px"><small style="min-width:64px">' + esc(h.name) + "</small>" + strip(j.steps, "h") + "</p>" +
        '<p style="margin:0;display:flex;align-items:center;gap:8px"><small style="min-width:64px">' + esc(a.name) + "</small>" + strip(j.steps, "a") + "</p>" +
        '<p class="gf" style="margin:8px 0 0">' + K3.map(function (x) { return '<span style="display:inline-flex;align-items:center;gap:4px;margin-inline-end:10px"><i style="width:9px;height:9px;border-radius:2px;background:' + COL[x] + '"></i>' + WORD[x] + "</span>"; }).join("") + "</p></div>" : "");
    BOX.innerHTML = '<div class="gh"><h2>نبض الجمهور</h2><span class="num" style="font-size:12px">من منشورات X بالعربي، تقريبي</span></div>' + body;
  }
  function poll() {
    if (D.hidden) return;
    fetch("/v1/mood/" + V.id + ".json", { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : null; }).then(draw).catch(function () {});
  }
  function start() {
    var now = Date.now();
    if (now < KO - 40 * 60e3) { var w = KO - 40 * 60e3 - now; if (w < 30 * HOUR) setTimeout(start, w + 1000); return; }   // a page opened early waits for it
    poll();
    if (now < KO + 4 * HOUR && !TIMER) TIMER = setInterval(poll, 60e3);
    D.addEventListener("visibilitychange", function () { if (!D.hidden) poll(); });
  }
  start();
})();
