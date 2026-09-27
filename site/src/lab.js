/* تيفو stats lab (feature 251): any two per-90 numbers of a league's players on one scatter. Data: comp/{id}/players.json. */
(function(){
  "use strict";
  var R = window.TR, $ = function(s){ return document.querySelector(s); };
  var LAB = { goals:"أهداف", _goals_and_goal_assist:"أهداف + صناعة", total_scoring_att:"تسديدات", ontarget_scoring_att:"على المرمى", accurate_pass:"تمريرات صحيحة", accurate_long_balls:"كرات طويلة صحيحة", won_contest:"مراوغات ناجحة", total_tackle:"افتكاك", interception:"قطع", ball_recovery:"استرجاع", effective_clearance:"إبعاد", defensive_contributions:"مساهمات دفاعية", fouls:"أخطاء", big_chance_created:"فرص صنعها", total_att_assist:"تمريرات مفتاحية", goal_assist:"صناعة" };
  var comp = $("#lcomp"), sx = $("#lx"), sy = $("#ly"), box = $("#lplot"), q = $("#lq"), DATA = null;
  function load(){ return fetch("/v1/comp/" + comp.value + "/players.json").then(function(r){ return r.json(); }).then(function(d){ DATA = d; var keys = {}; Object.keys(d.players).forEach(function(id){ Object.keys(d.players[id].stats || {}).forEach(function(k){ if (LAB[k] && d.players[id].stats[k].per90 != null) keys[k] = 1; }); });
    var opts = Object.keys(keys).map(function(k){ return '<option value="' + k + '">' + LAB[k] + "</option>"; }).join(""); var ox = sx.value, oy = sy.value; sx.innerHTML = sy.innerHTML = opts; sx.value = keys[ox] ? ox : (keys.total_scoring_att ? "total_scoring_att" : Object.keys(keys)[0]); sy.value = keys[oy] ? oy : (keys.goals ? "goals" : Object.keys(keys)[1]); draw(); }); }
  function draw(){
    if (!DATA) return; var X = sx.value, Y = sy.value, pts = [];
    Object.keys(DATA.players).forEach(function(id){ var p = DATA.players[id], a = p.stats[X], b = p.stats[Y]; if (a && b && a.per90 != null && b.per90 != null) pts.push({ id:id, n:p.name, t:p.team, x:a.per90, y:b.per90 }); });
    if (!pts.length){ box.innerHTML = '<p class="empty">ما في أرقام كافية.</p>'; return; }
    var W = 640, H = 420, P = 40, mx = Math.max.apply(null, pts.map(function(p){ return p.x; })) || 1, my = Math.max.apply(null, pts.map(function(p){ return p.y; })) || 1, hi = (q.value || "").trim().toLowerCase();
    var X0 = function(v){ return W - P - v / mx * (W - 2 * P); }, Y0 = function(v){ return H - P - v / my * (H - 2 * P); };   // RTL: more is to the LEFT
    var dots = pts.map(function(p){ var on = hi && p.n.toLowerCase().indexOf(hi) >= 0; return '<a href="/p/' + p.id + '/"><circle cx="' + X0(p.x).toFixed(1) + '" cy="' + Y0(p.y).toFixed(1) + '" r="' + (on ? 7 : 4.5) + '" fill="' + (on ? "#B07A3B" : R.col(p.t)) + '" stroke="#0E1512" stroke-width="' + (on ? 2 : .6) + '"><title>' + R.esc(p.n) + ": " + p.x.toFixed(2) + " / " + p.y.toFixed(2) + "</title></circle></a>"; }).join("");
    var top = pts.slice().sort(function(a, b){ return (b.x / mx + b.y / my) - (a.x / mx + a.y / my); }).slice(0, 6).map(function(p){ return '<text x="' + (X0(p.x) - 7).toFixed(0) + '" y="' + (Y0(p.y) + 4).toFixed(0) + '" text-anchor="end">' + R.esc(p.n.split(" ").slice(-1)[0]) + "</text>"; }).join("");
    box.innerHTML = '<svg viewBox="0 0 ' + W + " " + H + '" class="labsvg"><line x1="' + P + '" x2="' + (W - P) + '" y1="' + (H - P) + '" y2="' + (H - P) + '"/><line x1="' + (W - P) + '" x2="' + (W - P) + '" y1="' + P + '" y2="' + (H - P) + '"/><text class="ax" x="' + (W / 2) + '" y="' + (H - 10) + '" text-anchor="middle">' + LAB[X] + ' بالـ90 دقيقة ← أكثر</text><text class="ax" x="' + (W - P + 6) + '" y="' + (P - 12) + '" text-anchor="end">' + LAB[Y] + " ↑</text>" + dots + top + '</svg><p class="src">كل نقطة لاعب لعب ' + (DATA.min_minutes || 270) + " دقيقة أو أكثر. اضغط النقطة وتنفتح صفحته.</p>";
  }
  [sx, sy].forEach(function(e){ e.onchange = draw; }); q.oninput = draw; comp.onchange = load; load();
})();
