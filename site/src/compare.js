/* تيفو compare (features 16 + 61): two players on one radar (the six Tifo-card parts) plus per-90 numbers,
   or two clubs side by side. Data: comp/{id}/cards.json, players.json, style.json, standings.json (+ ratings for 538). */
(function(){
  "use strict";
  var R = window.TR, CID = +document.body.dataset.comp, V = "/v1/", $ = function(s){ return document.querySelector(s); };
  function get(p){ return fetch(V + p).then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; }); }
  var PARTS = [["finishing","إنهاء"],["creating","صناعة"],["passing","تمرير"],["dribbling","مراوغة"],["defending","دفاع"],["work_rate","مجهود"]];
  var P90 = [["goals","أهداف"],["goal_assist","صناعة"],["total_scoring_att","تسديد"],["big_chance_created","فرص صنعها"],["accurate_pass","تمريرات صحيحة"],["won_contest","مراوغات"],["total_tackle","افتكاك"],["interception","قطع"]];
  var TS = [["possession","استحواذ %",1],["shots","تسديد بالمباراة",1],["big_chances","فرص محققة",1],["passes","تمريرات",1],["tackles","افتكاك",1],["ppda","ضغط (الأقل أقوى)",-1]];
  Promise.all([get("comp/" + CID + "/cards.json"), get("comp/" + CID + "/players.json"), get("comp/" + CID + "/style.json"), get("comp/" + CID + "/standings.json"), CID === 538 ? get("ratings/uae-clubs.json") : null, get("teams.json")]).then(function(d){
    var cards = d[0] && d[0].players || {}, PNm = window.PN || {}; Object.keys(cards).forEach(function(id){ if (PNm[id]) cards[id].name = PNm[id]; });
    var pl = d[1] && d[1].players || {}, style = d[2] && d[2].teams || {}, st = d[3], rat = d[4], teams = d[5] && d[5].teams || {};
    var ids = Object.keys(cards).sort(function(a, b){ return cards[b].overall - cards[a].overall; });
    var opts = ids.map(function(id){ return '<option value="' + id + '">' + R.esc(cards[id].name) + " (" + R.esc((teams[cards[id].team] || {}).name_ar || "") + ")</option>"; }).join("");
    var pa = $("#pa"), pb = $("#pb"); pa.innerHTML = pb.innerHTML = opts; pa.value = ids[0]; pb.value = ids[1];
    var rows = st && st.groups && st.groups[0].rows || [];
    var topts = rows.map(function(r){ return '<option value="' + r.team.id + '">' + R.tname(r.team) + "</option>"; }).join("");
    var ta = $("#ta"), tb = $("#tb"); ta.innerHTML = tb.innerHTML = topts; if (rows[0]) ta.value = rows[0].team.id; if (rows[1]) tb.value = rows[1].team.id;
    try { var q = new URLSearchParams(location.search); if (q.get("a") && cards[q.get("a")]) pa.value = q.get("a"); if (q.get("b") && cards[q.get("b")]) pb.value = q.get("b"); } catch (e){}
    function radar(a, b){
      var W = 320, c = W / 2, r = 120, n = PARTS.length, ang = function(i){ return -Math.PI / 2 - i * 2 * Math.PI / n; };   // counter-clockwise from the top: reads right-to-left
      var pt = function(i, v){ return [c + r * v / 100 * Math.cos(ang(i)), c + r * v / 100 * Math.sin(ang(i))]; };
      var grid = [25, 50, 75, 100].map(function(v){ return '<polygon class="grid" points="' + PARTS.map(function(_, i){ return pt(i, v).join(","); }).join(" ") + '"/>'; }).join("");
      var lab = PARTS.map(function(p, i){ var q = pt(i, 118); return '<text x="' + q[0].toFixed(0) + '" y="' + (q[1] + 4).toFixed(0) + '" text-anchor="middle">' + p[1] + "</text>"; }).join("");
      var ca = R.colOn(a.team), cb = R.colOn(b.team); if (ca === cb) cb = "#F6F7F2";
      var poly = function(x, col){ return '<polygon class="pa" points="' + PARTS.map(function(p, i){ return pt(i, x.parts[p[0]] || 0).join(","); }).join(" ") + '" fill="' + col + '" stroke="' + col + '"/>'; };
      return '<div class="radar"><svg viewBox="0 0 ' + W + " " + W + '">' + grid + poly(a, ca) + poly(b, cb) + lab + '</svg></div><p class="legend"><span><i style="background:' + ca + '"></i>' + R.esc(a.name) + " " + a.overall + '</span><span><i style="background:' + cb + '"></i>' + R.esc(b.name) + " " + b.overall + "</span></p>";
    }
    function line(label, va, vb, dir, fmt){ var w = va == null || vb == null || va === vb ? 0 : (va > vb) === (dir > 0) ? 1 : 2; return '<div class="cmpt"><b class="' + (w === 1 ? "w" : "") + '">' + fmt(va) + "</b><span>" + label + '</span><b class="' + (w === 2 ? "w" : "") + '">' + fmt(vb) + "</b></div>"; }
    var f1 = function(v){ return v == null ? "—" : Number(v).toFixed(2); }, f0 = function(v){ return v == null ? "—" : Number(v).toFixed(v % 1 ? 1 : 0); };
    function players(){
      var a = cards[pa.value], b = cards[pb.value]; if (!a || !b) return;
      var sa = (pl[pa.value] || {}).stats || {}, sb = (pl[pb.value] || {}).stats || {};
      // QA 50: a player with minutes and no entry for a stat has 0 of it (FotMob lists only non-zero values)
      var z = function(s, who){ var out = {}; P90.forEach(function(k){ out[k[0]] = s[k[0]] || ((pl[who] || {}).minutes > 0 ? { per90:0, value:0 } : null); }); Object.keys(s).forEach(function(k){ if (!(k in out)) out[k] = s[k]; }); return out; };
      sa = z(sa, pa.value); sb = z(sb, pb.value);
      // 377: a verdict from the numbers — who leads in how many of the per-90 lines and the six card parts
      var wa = 0, wb = 0; P90.forEach(function(k){ var x = sa[k[0]] && sa[k[0]].per90, y = sb[k[0]] && sb[k[0]].per90; if (x != null && y != null && x !== y){ if (x > y) wa++; else wb++; } }); PARTS.forEach(function(p){ var x = a.parts[p[0]], y = b.parts[p[0]]; if (x != null && y != null && x !== y){ if (x > y) wa++; else wb++; } });
      var tot = wa + wb, rq = tot >= 3 && tot <= 10 ? "أرقام" : "رقم", verdict = !tot ? "" : wa === wb ? "متعادلين: كل واحد أحسن في " + wa + " من " + tot + " " + rq + "." : (wa > wb ? a.name : b.name) + " أحسن في " + Math.max(wa, wb) + " من " + tot + " " + rq + "، و" + (wa > wb ? b.name : a.name) + " في " + Math.min(wa, wb) + ".";
      $("#pout").innerHTML = (verdict ? '<p class="verdict"><b>الحكم بالأرقام</b> ' + R.esc(verdict) + "</p>" : "") + radar(a, b) + "<h3>كل 90 دقيقة</h3>" + P90.map(function(k){ var x = sa[k[0]], y = sb[k[0]]; return line(k[1], x && x.per90, y && y.per90, 1, f1); }).join("") + line("الدقايق", (pl[pa.value] || {}).minutes, (pl[pb.value] || {}).minutes, 1, f0);
      try { history.replaceState(null, "", "?a=" + pa.value + "&b=" + pb.value + location.hash); } catch (e){}
    }
    function clubs(){
      var A = +ta.value, B = +tb.value, ra = rows.filter(function(r){ return r.team.id === A; })[0], rb = rows.filter(function(r){ return r.team.id === B; })[0]; if (!ra || !rb) return;
      var sa = (style[A] || {}).style || {}, sb = (style[B] || {}).style || {}, ea = rat && rat.teams.filter(function(t){ return t.team === A; })[0], eb = rat && rat.teams.filter(function(t){ return t.team === B; })[0];
      $("#tout").innerHTML = line("المركز", ra.rank, rb.rank, -1, f0) + line("النقاط", ra.pts, rb.pts, 1, f0) + line("له", ra.gf, rb.gf, 1, f0) + line("عليه", ra.ga, rb.ga, -1, f0) + (ea && eb ? line("تصنيف تيفو", Math.round(ea.rating), Math.round(eb.rating), 1, f0) : "") + TS.map(function(k){ return line(k[1], sa[k[0]], sb[k[0]], k[2], f0); }).join("");
    }
    [pa, pb].forEach(function(e){ e.addEventListener("change", players); }); [ta, tb].forEach(function(e){ e.addEventListener("change", clubs); });
    players(); clubs();
  });
})();
