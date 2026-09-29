/* تيفو phase 2 — the numbers (docs/ROADMAP.md, phase 2). Renderers for the analytics files the pipeline writes
   (sim, magic, watch, bump, clutch, cards, style, fortress, referees, ratings, fifa…). Prerendered by build.cjs; the site
   rebuilds hourly, and the analytics files themselves refresh every 10 minutes. Charts are inline SVG, time flows
   right->left (RTL). Player names stay Latin (the source has no Arabic names); club names come from teams.json. */
(function(root){
  "use strict";
  var R = (typeof module !== "undefined" && module.exports) ? require("./render.js") : root.TR;
  var S = {}, T = {}, P = {}, C = {}, esc = R.esc;
  S.setTeams = function(m){ T = m || {}; };
  S.setPlayers = function(m){ P = m || {}; };
  S.setCoaches = function(m){ C = m || {}; };   // names/coaches_ar.json; Latin stays the fallback (QA 35/45)
  function coachA(a){ var ar = C[a.id] && C[a.id].ar; return "<a" + (ar ? "" : ' class="lat"') + ' href="/coach/' + esc(a.id) + '/">' + esc(ar || a.name) + "</a>"; }
  function team(id){ var t = T[id] || {}; return { id:+id, name:t.name, name_ar:t.name_ar || t.name || "" }; }
  function tl(id, cls){ var t = team(id); return '<a class="tl" href="/t/' + t.id + '/">' + R.logo(t, cls || "sm") + "<span>" + R.tname(t) + "</span></a>"; }
  function pname(id, fallback){ var p = P[id]; return p && p.name ? p.name : fallback || ""; }
  function pl(id, name){ return '<a class="lat" href="/p/' + id + '/">' + esc(name || pname(id)) + "</a>"; }
  function fx(v, n){ return v == null || isNaN(v) ? "—" : Number(v).toFixed(n); }
  function pct(x){ if (x == null) return "—"; var v = x * 100; return v >= 99.5 && v < 100 ? '<small>فوق</small> 99' : v > 0 && v < 0.5 ? '<small>أقل من</small> 1' : Math.round(v) + ""; }
  function bar(x, cls){ return '<span class="pbar' + (cls ? " " + cls : "") + '"><i style="inline-size:' + Math.max(0, Math.min(100, x * 100)).toFixed(1) + '%"></i></span>'; }
  function sec(title, sub, body, id){ return '<section class="blk"' + (id ? ' id="' + id + '"' : "") + "><h2>" + title + (sub ? "<small>" + sub + "</small>" : "") + "</h2>" + body + "</section>"; }
  S.sec = sec;
  function noteSrc(t){ return '<p class="src">' + t + "</p>"; }

  // ---- predictions: season simulator (93) + magic numbers (20) + watchability (136) + match probabilities (92)
  S.sim = function(sim, st){
    if (!sim || !sim.teams) return "";
    var bands = {}; (sim.bands || []).forEach(function(b){ bands[b.key] = b; });
    var rows = Object.keys(sim.teams).map(function(id){ var x = sim.teams[id]; x.id = id; return x; }).sort(function(a, b){ return b.exp_pts - a.exp_pts; });
    var cols = [["title", "البطولة"], ["ranks_1_2", "أبطال آسيا للنخبة"], ["relegation", "الهبوط"]].filter(function(c){ return bands[c[0]]; });
    return '<div class="tblwrap"><table class="st sim"><thead><tr><th style="text-align:start">الفريق</th><th>النقاط المتوقعة</th>' + cols.map(function(c){ return "<th>" + c[1] + " %</th>"; }).join("") + "</tr></thead><tbody>" +
      rows.map(function(x){ return '<tr><td class="tm">' + tl(x.id) + "</td><td>" + fx(x.exp_pts, 0) + "</td>" + cols.map(function(c){ var v = x[c[0]]; return '<td><span class="pv">' + pct(v) + "</span>" + bar(v, c[0] === "relegation" ? "bad" : c[0] === "title" ? "gold" : "") + "</td>"; }).join("") + "</tr>"; }).join("") +
      "</tbody></table></div>" + noteSrc("لعبنا باقي الموسم " + Number(sim.sims).toLocaleString("en-US") + " مرة بتصنيف تيفو للأندية، وعدّينا كم مرة خلص كل فريق في كل مركز. " + (sim.remaining_fixtures || "") + " مباراة باقية.");
  };
  var MAGIC = { title:"البطولة", top2:"أبطال آسيا للنخبة", top3:"ملحق أبطال آسيا", top4:"أبطال آسيا 2", safety:"البقاء" };
  S.magic = function(st, mine){
    var m = st && st.magic; if (!m || !m.teams) return "";
    var rows = (st.groups[0].rows || []).map(function(r){ return { id:r.team.id, t:m.teams[r.team.id] }; }).filter(function(x){ return x.t; });
    var bands = (m.bands || []).filter(function(b){ return MAGIC[b.key]; });
    return '<div class="tblwrap"><table class="st magic"><thead><tr><th style="text-align:start">الفريق</th><th>باقي</th>' + bands.map(function(b){ return "<th>" + MAGIC[b.key] + "</th>"; }).join("") + "</tr></thead><tbody>" +
      rows.map(function(x){ return '<tr class="' + (mine === x.id ? "mine" : "") + '"><td class="tm">' + tl(x.id) + "</td><td>" + x.t.remaining + "</td>" + bands.map(function(b){ var v = x.t[b.key]; if (!v) return "<td>—</td>"; if (v.state === "clinched") return '<td><span class="ok">ضمن</span></td>'; if (v.state === "eliminated") return '<td><span class="no">خلاص</span></td>'; return "<td>" + (v.needed - x.t.pts) + (v.own_hands ? "" : '<small class="muted">*</small>') + "</td>"; }).join("") + "</tr>"; }).join("") +
      '</tbody></table></div><p class="src">الرقم: كم نقطة زيادة يحتاجها الفريق <b>عشان يضمن</b> المركز حتى لو كل منافسيه فازوا بكل مبارياتهم. * يعني يحتاج غيره يتعثر. «ضمن» خلاص تأكد، و«خلاص» ما عاد يقدر يوصله.</p>';
  };
  S.probs = function(p, m){
    if (!p) return ""; var h = p.home, d = p.draw, a = p.away;
    return '<div class="probs"><div class="pr3"><i style="inline-size:' + (h * 100).toFixed(1) + '%;background:' + R.col(m.home.id) + '"></i><i class="d" style="inline-size:' + (d * 100).toFixed(1) + '%"></i><i style="inline-size:' + (a * 100).toFixed(1) + '%;background:' + R.col(m.away.id) + '"></i></div><div class="pr3l"><span>فوز ' + R.tname(m.home) + ' <b class="num">' + Math.round(h * 100) + '%</b></span><span>تعادل <b class="num">' + Math.round(d * 100) + '%</b></span><span>فوز ' + R.tname(m.away) + ' <b class="num">' + Math.round(a * 100) + "%</b></span></div></div>";
  };
  S.watch = function(w, fx){
    if (!w || !w.matches || !fx) return ""; var by = {}; (fx.matches || []).forEach(function(m){ by[m.id] = m; });
    var list = Object.keys(w.matches).map(function(id){ return { m:by[id], s:w.matches[id] }; }).filter(function(x){ return x.m; }).sort(function(a, b){ return b.s.score - a.s.score; });
    if (!list.length) return "";
    return list.map(function(x){ var tags = []; if (x.s.derby) tags.push("ديربي"); if (x.s.closeness > 0.85) tags.push("متقاربين"); if (x.s.stakes > 0.9) tags.push("الترتيب على المحك"); if (x.s.form > 0.6) tags.push("الفريقين في فورمة"); return '<div class="wt"><span class="ws"><b>' + x.s.score + "</b><small>متعة</small></span>" + R.matchRow(x.m, { date:true }) + (tags.length ? '<span class="tags">' + tags.map(function(t){ return "<i>" + t + "</i>"; }).join("") + "</span>" : "") + "</div>"; }).join("") + noteSrc("مؤشر المتعة من 100: تقارب مستوى الفريقين، والديربي، وشو على المحك في الترتيب، وفورمة الفريقين.");
  };

  // ---- the season's shape: bump chart (114), alternative tables (140, 51, 50)
  S.bump = function(b){
    if (!b || !b.positions || !b.rounds || b.rounds.length < 2) return "";
    var ids = Object.keys(b.positions), n = ids.length, rs = b.rounds, W = 640, rowH = 22, H = n * rowH + 30, padR = 30, padL = 120;
    var x = function(i){ return W - padR - i * (W - padR - padL) / (rs.length - 1); }, y = function(p){ return 16 + (p - 1) * rowH; };
    var lines = ids.map(function(id){ var ps = b.positions[id]; var d = ps.map(function(p, i){ return (i ? "L" : "M") + x(i).toFixed(1) + " " + y(p); }).join(" "); var c = R.col(id); var last = ps[ps.length - 1];
      return '<g class="bl" data-t="' + id + '"><path d="' + d + '" stroke="' + c + '" /><circle cx="' + x(ps.length - 1) + '" cy="' + y(last) + '" r="4" fill="' + c + '"/><text x="' + (x(ps.length - 1) - 8) + '" y="' + (y(last) + 4) + '" text-anchor="end">' + esc(team(id).name_ar) + "</text></g>"; }).join("");
    var axis = rs.map(function(r, i){ return '<text class="ax" x="' + x(i) + '" y="' + (H - 4) + '" text-anchor="middle">' + r + "</text>"; }).join("");
    return '<div class="bump"><svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="مراكز الفرق جولة بجولة">' + lines + axis + "</svg></div>" + noteSrc("مركز كل فريق بعد كل جولة. الجولة الأولى على اليمين.");
  };
  function miniTable(rows, cols){ return '<div class="tblwrap"><table class="st"><thead><tr><th>#</th><th style="text-align:start">الفريق</th>' + cols.map(function(c){ return "<th>" + c[1] + "</th>"; }).join("") + "</tr></thead><tbody>" + rows.map(function(r, i){ return "<tr><td>" + (r.rank || i + 1) + '</td><td class="tm">' + tl(r.team && r.team.id || r.team) + "</td>" + cols.map(function(c){ var v = typeof c[0] === "function" ? c[0](r) : r[c[0]]; return "<td>" + v + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table></div>"; }
  var gd = function(r){ var v = r.gd != null ? r.gd : r.gf - r.ga; return '<bdi dir="ltr">' + (v > 0 ? "+" : "") + v + "</bdi>"; };
  S.tables = function(st, ht, xg){
    var g = st && st.groups && st.groups[0], out = [];
    if (g && g.home_rows) out.push(["home", "بملعبه", miniTable(g.home_rows, [["played", "لعب"], [gd, "الفرق"], ["pts", "نقاط"]])]);
    if (g && g.away_rows) out.push(["away", "برا ملعبه", miniTable(g.away_rows, [["played", "لعب"], [gd, "الفرق"], ["pts", "نقاط"]])]);
    if (ht && ht.rows && ht.rows.length) out.push(["ht", "الشوط الأول", miniTable(ht.rows, [["played", "لعب"], [gd, "الفرق"], ["pts", "نقاط"]]) + noteSrc("الترتيب لو كل مباراة خلصت بين الشوطين.")]);
    if (xg && xg.available && xg.rows) out.push(["xg", "العادل", miniTable(xg.rows, [[function(r){ return fx(r.xpts, 1); }, "نقاط متوقعة"], ["pts", "نقاطه"], [function(r){ var l = r.luck; return '<span class="' + (l > 1 ? "lk-up" : l < -1 ? "lk-dn" : "") + '"><bdi dir="ltr">' + (l > 0 ? "+" : "") + fx(l, 1) + "</bdi></span>"; }, "الحظ"]]) + noteSrc("الترتيب لو كل مباراة انتهت حسب الأهداف المتوقعة. «الحظ» = نقاطه الحقيقية ناقص المتوقعة." + (xg.proxy ? ' هالبطولة ما فيها أهداف متوقعة من المصدر، فحسبناها من <a href="/glossary/#danger-index">مؤشر الخطورة</a>.' : ""))]);
    return out;
  };

  // ---- players: clutch (137), cards (135), foreigners (46), improved (124), young (119), team of the round (129)
  S.clutch = function(c){
    if (!c || !c.players || !c.players.length) return "";
    var named = c.players.filter(function(p){ return p.name || pname(p.id) || (R.PNAME && R.PNAME(p.id)); });   /* QA 34: a row with no name at all is dropped */ if (!named.length) return "";
    return '<ol class="lead">' + named.slice(0, 15).map(function(p, i){ return '<li><span class="num muted">' + (i + 1) + '</span><span class="who">' + R.logo(team(p.team), "sm") + pl(p.id, p.name || (R.PNAME && R.PNAME(p.id))) + ' <span class="muted small">' + p.from_goals + " من أهدافه، " + p.from_assists + " من صناعته" + (p.winners ? "، " + p.winners + " هدف فوز" : "") + "</span></span><b>" + p.total + "</b></li>"; }).join("") + "</ol>" + noteSrc("النقاط اللي جابها اللاعب لفريقه: كل هدف أو صناعة غيّرت النتيجة (من خسارة لتعادل أو من تعادل لفوز) تنحسب نقاطها.");
  };
  var PARTS = { finishing:"إنهاء", creating:"صناعة", passing:"تمرير", dribbling:"مراوغة", defending:"دفاع", work_rate:"مجهود" };
  var ROLE = { GK:"حارس", DF:"دفاع", MF:"وسط", FW:"هجوم" };
  S.card = function(id, c){
    if (!c) return "";
    return '<a class="tcard" href="/p/' + id + '/" style="--c1:' + R.col(c.team) + ";--c2:" + R.col(c.team, 1) + '"><span class="ov">' + c.overall + '</span><span class="rl">' + (ROLE[c.role] || esc(c.role)) + "</span>" + R.logo(team(c.team), "sm") + '<b class="lat">' + esc(c.name) + '</b><span class="pts6">' + Object.keys(PARTS).map(function(k){ return "<i><em>" + (c.parts[k] == null ? "—" : c.parts[k]) + "</em>" + PARTS[k] + "</i>"; }).join("") + "</span></a>";
  };
  S.cards = function(cards, n, filter){
    if (!cards || !cards.players) return "";
    var ids = Object.keys(cards.players).filter(function(id){ return !filter || filter(cards.players[id]); }).sort(function(a, b){ return cards.players[b].overall - cards.players[a].overall; }).slice(0, n || 12);
    return ids.length ? '<div class="tcards">' + ids.map(function(id){ return S.card(id, cards.players[id]); }).join("") + "</div>" + noteSrc("التقييم من أرقام اللاعب الحقيقية هالموسم مقارنة بلاعبي الدوري في نفس المركز، ويتحدّث كل جولة.") : "";
  };
  S.players = function(list, fmt, n){ if (!list || !list.length) return ""; return '<ol class="lead">' + list.slice(0, n || 10).map(function(p, i){ return '<li><span class="num muted">' + (i + 1) + '</span><span class="who">' + R.logo(team(p.team), "sm") + pl(p.id, p.name) + ' <span class="muted small">' + fmt(p) + "</span></span><b>" + (p.rating != null ? fx(p.rating, 1) : "") + "</b></li>"; }).join("") + "</ol>"; };
  S.foreigners = function(f){ return f && S.players(f.players, function(p){ return (R.flag && R.flag(p.country) ? '<span class="flag" title="' + esc(p.country) + '">' + R.flag(p.country) + "</span> " : "") + R.cnt(p.goals, ["هدف", "هدفين", "أهداف", "هدف"], "بدون أهداف") + "، " + R.cnt(p.assists, ["صناعة", "صناعتين", "صناعات", "صناعة"], "بدون صناعة"); }, 10);   /* QA 35/79: a flag, not «BRA»; counted words */ };
  S.improved = function(f){ return f && f.players && f.players.length ? S.players(f.players, function(p){ return "كان " + fx(p.prev_rating, 1) + ' الموسم الماضي <b class="up">+' + fx(p.delta, 2) + "</b>"; }, 10) + noteSrc("التقييم هالموسم مقارنة بالموسم الماضي، لمن لعب " + f.min_matches + " مباريات أو أكثر.") : ""; };
  S.young = function(f){ if (!f) return ""; if (!f.players || !f.players.length) return '<p class="empty">للحين ما في لاعب إماراتي تحت ' + f.max_age + " سنة لعب " + f.min_minutes + " دقيقة أو أكثر هالموسم.</p>"; return S.players(f.players, function(p){ return p.age + " سنة"; }, 10); };
  var ROWY = { GK:92, DF:72, MF:48, FW:22 };
  S.teamOfRound = function(t){
    if (!t || !t.rounds) return ""; var ks = Object.keys(t.rounds).sort(function(a, b){ return b - a; }), r = t.rounds[ks[0]]; if (!r || !r.players) return "";
    var g = {}; r.players.forEach(function(p){ (g[p.role] = g[p.role] || []).push(p); });
    var dots = Object.keys(g).map(function(role){ var ps = g[role]; return ps.map(function(p, i){ var x = 100 - (i + 1) * 100 / (ps.length + 1); var ar = R.PNAME ? R.PNAME(p.id) : (root && root.PN && root.PN[p.id]) || null, nm = ar ? String(ar).split(" ").slice(-1)[0] : String(p.name).split(" ").slice(-1)[0];   /* QA 64: Arabic short name; the rating is plain text, not a score box */
      return '<div class="pl tor" style="left:' + fx(x, 1) + "%;top:" + ROWY[role] + '%"><span class="rt0">' + fx(p.rating, 1) + "</span>" + (p.id ? '<a href="/p/' + p.id + '/"' + (ar ? "" : ' class="lat"') + ">" + esc(nm) + "</a>" : '<span class="lat">' + esc(nm) + "</span>") + '<span class="tn">' + R.tname(team(p.team)) + "</span></div>"; }).join(""); }).join("");
    return '<p class="muted small">الجولة <span class="num">' + ks[0] + '</span>، خطة <span class="num">' + esc(r.formation) + '</span>: أعلى تقييم في كل مركز.</p><div class="pitch half"><i class="half"></i><i class="box b"></i>' + dots + "</div>";
  };

  // ---- goals and time (139, 52)
  S.clock = function(mc){
    if (!mc || !mc.league) return ""; var a = mc.league.slice(0, 91), max = Math.max.apply(null, a) || 1, cx = 160, cy = 160, r0 = 70, r1 = 140, out = "";
    for (var i = 1; i <= 90; i++){ var v = a[i] || 0; if (!v) continue; var ang = (i - 0.5) / 90 * 2 * Math.PI - Math.PI / 2, rr = r0 + (r1 - r0) * v / max; out += '<line x1="' + (cx + r0 * Math.cos(ang)).toFixed(1) + '" y1="' + (cy + r0 * Math.sin(ang)).toFixed(1) + '" x2="' + (cx + rr * Math.cos(ang)).toFixed(1) + '" y2="' + (cy + rr * Math.sin(ang)).toFixed(1) + '"' + (i === 45 || i === 90 ? ' class="st"' : "") + "/>"; }
    var lab = [[0, "0"], [15, "15"], [30, "30"], [45, "45"], [60, "60"], [75, "75"]].map(function(x){ var ang = x[0] / 90 * 2 * Math.PI - Math.PI / 2; return '<text x="' + (cx + 56 * Math.cos(ang)).toFixed(1) + '" y="' + (cy + 56 * Math.sin(ang) + 4).toFixed(1) + '" text-anchor="middle">' + x[1] + "</text>"; }).join("");
    var peak = a.indexOf(max);
    return '<div class="clock"><svg viewBox="0 0 320 320" role="img" aria-label="دقايق الأهداف"><circle cx="160" cy="160" r="70" class="ring"/>' + out + lab + '</svg><p>أكثر دقيقة انسجل فيها: <b class="num">' + peak + "</b>" + (peak === 45 || peak === 90 ? " (مع الوقت بدل الضايع)" : "") + '</p></div>' + noteSrc("كل خط دقيقة من المباراة، وطوله عدد الأهداف فيها. " + mc.matches_counted + " مباراة.");
  };
  S.late = function(gb){
    if (!gb || !gb.teams) return ""; var rows = Object.keys(gb.teams).map(function(id){ var t = gb.teams[id]; return { id:id, f:t.for["76-90+"] || 0, a:t.against["76-90+"] || 0 }; });
    var f = rows.slice().sort(function(x, y){ return y.f - x.f; }).slice(0, 5), a = rows.slice().sort(function(x, y){ return y.a - x.a; }).slice(0, 5);
    var li = function(x, k){ return '<li><span class="who">' + tl(x.id) + "</span><b>" + x[k] + "</b></li>"; };
    return '<div class="two"><div><h3>يسجلون في الآخر</h3><ol class="lead">' + f.map(function(x){ return li(x, "f"); }).join("") + '</ol></div><div><h3>ينصادون في الآخر</h3><ol class="lead">' + a.map(function(x){ return li(x, "a"); }).join("") + "</ol></div></div>" + noteSrc("الأهداف من الدقيقة 76 لين نهاية الوقت بدل الضايع.");
  };

  // ---- referees (37), lineup ages (142), rotation (143), coach pressure (96), style (138), fortress (141)
  S.referees = function(rf){
    if (!rf || !rf.referees || !rf.referees.length) return "";
    return '<div class="tblwrap"><table class="st"><thead><tr><th style="text-align:start">الحكم</th><th>مباريات</th><th>إنذار بالمباراة</th><th>طرد</th><th>بلنتي</th></tr></thead><tbody>' + rf.referees.slice().sort(function(a, b){ return b.matches - a.matches; }).map(function(r){ var s = r.source_stats && rf.comp != null && r.source_stats.scope_comp === rf.comp ? r.source_stats : null; return '<tr><td class="tm">' + (r.id ? '<a class="lat" href="/r/' + r.id + '/">' + esc(r.name) + "</a>" : '<span class="lat">' + esc(r.name) + "</span>") + "</td><td>" + (s ? s.matches : r.matches) + "</td><td>" + (s ? s.yellow_per_match : r.yellow_per_match).toFixed(1) + "</td><td>" + (s ? s.red : r.red) + "</td><td>" + (s ? s.penalties : r.penalties) + "</td></tr>"; }).join("") + "</tbody></table></div>";
  };
  S.ages = function(la){
    if (!la || !la.rounds) return ""; var k = Object.keys(la.rounds).filter(function(k){ return la.rounds[k] && la.rounds[k].all; }).sort(function(a, b){ return b - a; })[0], r = la.rounds[k]; if (!r) return "";
    return '<p class="muted small">الجولة <span class="num">' + k + '</span>: متوسط عمر التشكيلة الأساسية</p><ol class="lead">' + r.all.map(function(x, i){ return '<li><span class="num muted">' + (i + 1) + '</span><span class="who">' + tl(x.team) + "</span><b>" + fx(x.avg_age, 1) + "</b></li>"; }).join("") + "</ol>";
  };
  S.rotation = function(ro){
    if (!ro || !ro.teams) return ""; var rows = Object.keys(ro.teams).map(function(id){ return { id:id, t:ro.teams[id] }; }).filter(function(x){ return x.t.avg_changes != null; }).sort(function(a, b){ return b.t.avg_changes - a.t.avg_changes; });
    return '<ol class="lead">' + rows.map(function(x, i){ var c = x.t.by_coach && Object.values(x.t.by_coach)[0]; return '<li><span class="num muted">' + (i + 1) + '</span><span class="who">' + tl(x.id) + (c ? ' <span class="muted small lat">' + esc(c.name) + "</span>" : "") + "</span><b>" + fx(x.t.avg_changes, 1) + "</b></li>"; }).join("") + "</ol>" + noteSrc("كم تغيير يسويه المدرب في تشكيلته الأساسية من مباراة للي بعدها، بالمتوسط.");
  };
  S.pressure = function(pr){
    if (!pr || !pr.teams) return ""; var rows = Object.keys(pr.teams).map(function(id){ return { id:id, t:pr.teams[id] }; }).filter(function(x){ return x.t && x.t.index != null; }); if (!rows.length) return ""; rows = rows.sort(function(a, b){ return b.t.index - a.t.index; });
    return '<div class="thermo">' + rows.map(function(x){ var v = x.t.index; return '<div class="th1"><span class="who">' + tl(x.id) + '</span><span class="tbar"><i style="inline-size:' + v + "%;background:" + (v >= 70 ? "var(--card-r)" : v >= 45 ? "var(--dune)" : "var(--pulse)") + '"></i></span><b class="num">' + v + '</b><small class="muted">' + fx(x.t.ppg, 1) + " نقطة بالمباراة، المتوقع " + fx(x.t.xppg, 1) + (x.t.winless_streak > 1 ? "، " + x.t.winless_streak + " بدون فوز" : "") + "</small></div>"; }).join("") + "</div>" + noteSrc("الضغط من 100: نقاط الفريق مقارنة باللي كان متوقع منه بتصنيفه، وسلسلة النتايج السلبية. كل ما زاد الرقم زاد الضغط على المدرب.");
  };
  S.style = function(sy){
    if (!sy || !sy.teams) return ""; var rows = Object.keys(sy.teams).map(function(id){ return { id:id, s:sy.teams[id].style }; }).sort(function(a, b){ return b.s.possession - a.s.possession; });
    return '<div class="tblwrap"><table class="st"><thead><tr><th style="text-align:start">الفريق</th><th>استحواذ %</th><th>تسديد</th><th>كرات طويلة</th><th>ضغط*</th></tr></thead><tbody>' + rows.map(function(x){ return '<tr><td class="tm">' + tl(x.id) + "</td><td>" + fx(x.s.possession, 0) + "</td><td>" + fx(x.s.shots, 1) + "</td><td>" + fx(x.s.long_balls, 0) + "</td><td>" + (x.s.ppda != null ? fx(x.s.ppda, 1) : "—") + "</td></tr>"; }).join("") + "</tbody></table></div>" + noteSrc("بالمتوسط في المباراة. *الضغط = كم تمريرة يخلّي الخصم يلعبها قبل ما يحاول يقطع الكورة: الأقل يعني ضغط أعلى.");
  };
  S.fortress = function(f){
    if (!f || !f.stadiums) return ""; return '<ol class="lead">' + f.stadiums.slice().sort(function(a, b){ return b.current_unbeaten - a.current_unbeaten; }).slice(0, 10).map(function(s, i){ return '<li><span class="num muted">' + (i + 1) + '</span><span class="who">' + R.logo(team(s.team), "sm") + "<span>" + esc(s.name_ar) + '</span> <span class="muted small">' + R.tname(team(s.team)) + "، أطول سلسلة " + s.longest_unbeaten + " (" + esc(s.longest_season) + ")</span></span><b>" + s.current_unbeaten + "</b></li>"; }).join("") + "</ol>" + noteSrc("كم مباراة متتالية ما خسر فيها صاحب الملعب على أرضه في الدوري، من موسم " + esc(f.since) + ".");
  };
  S.records = function(rc){
    if (!rc || !rc.chases || !rc.chases.length) return "";
    return '<ul class="facts-l">' + rc.chases.filter(function(c){ return c.needs_to_equal != null; }).map(function(c){ return '<li><b class="lat">' + esc(c.name) + "</b> عنده " + c.goals_all_time + " هدف في تاريخ الدوري (المركز " + c.rank + "). يحتاج <b class=\"num\">" + c.needs_to_equal + "</b> عشان يعادل <span class=\"lat\">" + esc(c.next_rank_name) + "</span>.</li>"; }).join("") + "</ul>";
  };
  S.alltime = function(at){
    if (!at || !at.titles_by_club) return "";
    var clubs = Object.keys(at.titles_by_club).sort(function(a, b){ return at.titles_by_club[b] - at.titles_by_club[a]; }), max = at.titles_by_club[clubs[0]];
    var idOf = {}; (at.champions || []).forEach(function(c){ if (c.champion_id) idOf[c.champion] = c.champion_id; });
    var titles = '<div class="thermo">' + clubs.map(function(c){ var n = at.titles_by_club[c], id = idOf[c]; return '<div class="th1"><span class="who">' + (id ? tl(id) : '<span class="lat">' + esc(c) + "</span>") + '</span><span class="tbar"><i style="inline-size:' + (n / max * 100) + "%;background:" + (id ? R.col(id) : "var(--stone)") + '"></i></span><b class="num">' + n + "</b></div>"; }).join("") + "</div>";
    var champs = '<details class="more"><summary>كل الأبطال من ' + esc(at.champions[0].season) + "</summary><ol class=\"lead\">" + at.champions.slice().reverse().map(function(c){ return '<li><span class="num muted">' + esc(c.season) + '</span><span class="who">' + (c.cancelled ? '<span class="muted">' + esc(c.cancelled) + "</span>" : c.champion_id ? tl(c.champion_id) : esc(c.champion_ar || c.champion)) + "</span><b></b></li>"; }).join("") + "</ol></details>";
    var sc = (at.top_scorers_all_time || []).slice(0, 10);
    return "<h3>البطولات</h3>" + titles + champs + (sc.length ? "<h3>الهدافين التاريخيين</h3><ol class=\"lead\">" + sc.map(function(s){ return '<li><span class="num muted">' + s.rank + '</span><span class="who"><span class="lat">' + esc(s.name) + '</span> <span class="muted small"><bdi dir="ltr">' + esc(s.years) + "</bdi></span></span><b>" + s.goals + "</b></li>"; }).join("") + "</ol>" : "") + '<p class="src">المصادر: <a href="' + esc(at.source.champions_cited_source.replace(/^.*\((.*)\)$/, "$1")) + '" rel="noopener">RSSSF</a> و<a href="' + esc(at.source.wikipedia) + '" rel="noopener">ويكيبيديا</a>. ألقاب «الأهلي» قبل 2017 محسوبة لشباب الأهلي.</p>';
  };
  S.compare = function(c, here){
    if (!c || !c.leagues) return ""; var ids = Object.keys(c.leagues);
    return '<div class="tblwrap"><table class="st"><thead><tr><th style="text-align:start">الدوري</th><th>أهداف بالمباراة</th><th>فوز صاحب الأرض %</th><th>تعادل %</th><th>متوسط العمر</th></tr></thead><tbody>' + ids.map(function(id){ var l = c.leagues[id]; return '<tr class="' + (+id === here ? "mine" : "") + '"><td class="tm">' + esc(l.name_ar) + "</td><td>" + fx(l.goals_per_match, 2) + "</td><td>" + fx(l.home_win_pct, 0) + "</td><td>" + fx(l.draw_pct, 0) + "</td><td>" + (l.avg_age ? fx(l.avg_age, 1) : "—") + "</td></tr>"; }).join("") + "</tbody></table></div>" + noteSrc("من مباريات الموسم الحالي في كل دوري.");
  };

  // ---- Tifo rating (91)
  S.ratingTable = function(r){
    if (!r || !r.teams) return "";
    return '<ol class="lead">' + r.teams.filter(function(t){ return t.in_league; }).map(function(t){ var ch = t.change_5; return '<li><span class="num muted">' + t.rank + '</span><span class="who">' + tl(t.team) + ' <span class="small ' + (ch > 0 ? "up" : ch < 0 ? "dn" : "muted") + '"><bdi dir="ltr">' + (ch > 0 ? "+" : "") + fx(ch, 0) + "</bdi></span></span><b>" + Math.round(t.rating) + "</b></li>"; }).join("") + "</ol>" + noteSrc("تصنيف تيفو: نقاط قوة لكل نادي تطلع وتنزل بعد كل مباراة حسب النتيجة وقوة الخصم، من " + esc(r.since) + ". الرقم الصغير = التغيّر في آخر 5 مباريات. دقة التوقع مجرّبة على " + r.calibration.n_test + " مباراة ما شافها النموذج.");
  };
  S.ratingChart = function(h, id, name){
    var pts = (h && h.history) || []; if (pts.length < 3) return "";
    var W = 640, H = 200, t0 = Date.parse(pts[0][0]), t1 = Date.parse(pts[pts.length - 1][0]), vs = pts.map(function(p){ return p[1]; }), lo = Math.min.apply(null, vs) - 20, hi = Math.max.apply(null, vs) + 20;
    var x = function(d){ return W - 10 - (Date.parse(d) - t0) / (t1 - t0 || 1) * (W - 20); }, y = function(v){ return H - 20 - (v - lo) / (hi - lo) * (H - 40); };
    var d = pts.map(function(p, i){ return (i ? "L" : "M") + x(p[0]).toFixed(1) + " " + y(p[1]).toFixed(1); }).join(" ");
    var years = {}, ax = ""; pts.forEach(function(p){ var yr = p[0].slice(0, 4); if (!years[yr]){ years[yr] = 1; if (+yr % 2 === 0) ax += '<text class="ax" x="' + x(yr + "-01-01").toFixed(0) + '" y="' + (H - 4) + '" text-anchor="middle">' + yr + "</text>"; } });
    var last = pts[pts.length - 1];
    return '<div class="rchart"><svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="تصنيف تيفو عبر السنين"><line class="base" x1="10" x2="' + (W - 10) + '" y1="' + y(1500) + '" y2="' + y(1500) + '"/><path d="' + d + '" stroke="' + R.col(id) + '"/><circle cx="' + x(last[0]) + '" cy="' + y(last[1]) + '" r="5" fill="' + R.col(id) + '"/>' + ax + '</svg><p class="muted small">الحين <b class="num">' + Math.round(last[1]) + "</b>. الخط الأفقي 1500 = نادي متوسط. أحدث تاريخ على اليسار.</p></div>";
  };

  // ---- match extras: records/facts (94, 95)
  S.matchFacts = function(list){ if (!list || !list.length) return ""; return '<ul class="facts-l">' + list.map(function(f){ return "<li>" + esc(String(f.text_ar).replace(/\s*\(بيانات FotMob\)/g, "")) + (f.record_at_stake ? ' <b class="rec">رقم قياسي على المحك</b>' : "") + "</li>"; }).join("") + "</ul>"; };

  // ---- national team: FIFA (144), tournament sim (145), scenarios (59), abroad (39)
  S.fifa = function(f){
    var h = f && f.history; if (!h || h.length < 3) return "";
    var W = 640, H = 200, t0 = Date.parse(h[0].date), t1 = Date.parse(h[h.length - 1].date), rs = h.map(function(x){ return x.rank; }), lo = 1, hi = Math.max.apply(null, rs) + 5;
    var x = function(d){ return W - 10 - (Date.parse(d) - t0) / (t1 - t0 || 1) * (W - 20); }, y = function(v){ return 12 + (v - lo) / (hi - lo) * (H - 36); };
    var d = h.map(function(p, i){ return (i ? "L" : "M") + x(p.date).toFixed(1) + " " + y(p.rank).toFixed(1); }).join(" "), best = h.reduce(function(a, b){ return b.rank < a.rank ? b : a; }), last = h[h.length - 1];
    var ax = ""; [1995, 2000, 2005, 2010, 2015, 2020, 2025].forEach(function(yr){ var dd = yr + "-01-01"; if (Date.parse(dd) > t0 && Date.parse(dd) < t1) ax += '<text class="ax" x="' + x(dd).toFixed(0) + '" y="' + (H - 4) + '" text-anchor="middle">' + yr + "</text>"; });
    return '<div class="rchart"><svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="تصنيف فيفا للمنتخب"><path d="' + d + '" stroke="#D8343F"/><circle cx="' + x(last.date) + '" cy="' + y(last.rank) + '" r="5" fill="#D8343F"/>' + ax + '</svg><p class="muted small">المركز الحين <b class="num">' + last.rank + "</b> عالمياً" + (last.afc_rank ? "، و<b class=\"num\">" + last.afc_rank + "</b> في آسيا" : "") + (last.arab_rank ? "، و<b class=\"num\">" + last.arab_rank + "</b> عربياً" : "") + '. أحسن مركز <b class="num">' + best.rank + "</b> (" + best.date.slice(0, 4) + "). فوق = أحسن، وأحدث تاريخ على اليسار.</p></div>";
  };
  var STAGE = { "1/2":"نص النهائي", "1/4":"ربع النهائي", "1/8":"دور الـ16", final:"النهائي", winner:"البطل" };
  S.tsim = function(ts){
    if (!ts || !ts.teams) return ""; var st = (ts.stages || []).concat(["winner"]);
    var rows = Object.keys(ts.teams).map(function(id){ return { id:id, t:ts.teams[id] }; }).sort(function(a, b){ return (b.t.reach_winner || 0) - (a.t.reach_winner || 0); });
    return '<div class="tblwrap"><table class="st sim"><thead><tr><th style="text-align:start">المنتخب</th>' + st.map(function(s){ return "<th>" + (STAGE[s] || esc(s)) + " %</th>"; }).join("") + "</tr></thead><tbody>" + rows.map(function(x){ return '<tr class="' + (+x.id === 5789 ? "mine" : "") + '"><td class="tm">' + tl(x.id) + "</td>" + st.map(function(s){ var v = x.t["reach_" + s]; return '<td><span class="pv">' + pct(v) + "</span>" + bar(v || 0, s === "winner" ? "gold" : "") + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table></div>" + noteSrc("لعبنا البطولة " + Number(ts.sims).toLocaleString("en-US") + " مرة بتصنيف تيفو للمنتخبات.");
  };
  S.scenarios = function(sc, id){
    if (!sc || !sc.groups) return ""; var out = "";
    sc.groups.forEach(function(g){ var t = g.teams[id]; if (!t) return; var nr = t.next_result || {};
      out += '<div class="scen"><p>في ' + esc(R.stageAr(g.group)) + ": أحسن مركز ممكن <b class=\"num\">" + t.best + '</b> وأسوأ مركز <b class="num">' + t.worst + "</b>.</p>" + (nr.W ? '<div class="scn3"><div class="w"><b>لو فاز</b>المركز ' + (nr.W.best === nr.W.worst ? nr.W.best : nr.W.best + " أو " + nr.W.worst) + '</div><div class="d"><b>لو تعادل</b>المركز ' + (nr.D.best === nr.D.worst ? nr.D.best : nr.D.best + " أو " + nr.D.worst) + '</div><div class="l"><b>لو خسر</b>المركز ' + (nr.L.best === nr.L.worst ? nr.L.best : nr.L.best + " لين " + nr.L.worst) + "</div></div>" : "") + "</div>"; });
    return out ? out + noteSrc("كل الاحتمالات لباقي مباريات المجموعة. لو تساووا بالنقاط حسبناها ممكن تروح لأي طرف.") : "";
  };
  S.abroad = function(a){ if (!a || !a.players || !a.players.length) return ""; return '<ol class="lead">' + a.players.map(function(p){ var s = p.league && p.league.stats || {}; return '<li><span class="num muted">' + (s.matches_uppercase || "") + '</span><span class="who">' + R.logo(p.team, "sm") + '<span class="lat">' + esc(p.name) + '</span> <span class="muted small">' + R.tname(p.team) + (p.on_loan ? "، معار" : "") + "، " + (s.minutes_played || 0) + " دقيقة</span></span><b>" + (s.rating ? fx(s.rating, 1) : "") + "</b></li>"; }).join("") + "</ol>"; };

  // ---- player page (135, 120, 149)
  S.similar = function(sm, id){ var x = sm && sm.players && sm.players[id]; if (!x || !x.similar || !x.similar.length) return ""; return '<ol class="lead">' + x.similar.slice(0, 5).map(function(s, i){ return '<li><span class="num muted">' + (i + 1) + '</span><span class="who">' + R.logo(team(s.team), "sm") + pl(s.id, s.name) + ' <span class="muted small">' + R.tname(team(s.team)) + "</span></span><b>" + Math.round(s.score * 100) + "%</b></li>"; }).join("") + "</ol>" + noteSrc("التشابه من أرقام كل 90 دقيقة: تسديد، صناعة، تمرير، مراوغة، دفاع."); };

  // ---- «شو لو؟» (11) and final day (118): the shell; app.js makes it interactive
  S.whatif = function(fx, st){
    if (!fx || !fx.matches || !st || !st.groups || st.composite) return "";
    var rr = R.rounds(fx), open = rr.order.filter(function(k){ return rr.by[k].some(function(m){ return m.status === "scheduled" && m.kickoff_utc; }); });
    if (!open.length) return "";
    var left = rr.order.filter(function(k){ return rr.by[k].some(function(m){ return m.status !== "finished" && m.status !== "cancelled"; }); }), last = open.length === 1 && (fx.rounds_left != null ? fx.rounds_left <= 1 : left.length === 1);   /* QA 8: dateless rounds still count */
    return '<div id="whatif" data-rounds="' + esc(open.slice(0, 4).join(",")) + '"><p class="muted small">' + (last ? "باقي جولة وحدة: <b>يوم الحسم</b>. " : "") + "اختار نتيجة كل مباراة، والترتيب يتغيّر قدامك. الأسهم تقارن بالترتيب الحين.</p><div class=\"chips\" id=\"wi-r\"></div><div id=\"wi-m\"></div><h3>الترتيب لو صارت هالنتايج</h3><div id=\"wi-t\"></div><p class=\"src\">الفوز نحسبه 1-0 والتعادل 0-0 عشان فرق الأهداف. ترتيب التساوي بالنقاط ثم فرق الأهداف ثم الأهداف.</p></div>";
  };
  // ---- shot map (43): FotMob x runs 0..105 toward goal, y 0..68 across. Half pitch, goal at the top.
  S.shotmap = function(sp){
    if (!sp || !sp.list || !sp.list.length) return "";
    var W = 340, H = 260, dots = sp.list.map(function(s){ var x = s[4], y = s[5], xg = s[2] || 0.05, goal = /Goal/i.test(s[3]) && !/Own/i.test(s[3]); var cx = (y / 68) * W, cy = ((105 - x) / 52.5) * H; return '<circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) + '" r="' + (4 + Math.sqrt(xg) * 14).toFixed(1) + '" class="' + (goal ? "g" : "m") + '"><title>د ' + s[1] + "، أهداف متوقعة " + fx(xg, 2) + "</title></circle>"; }).join("");
    return '<div class="shotmap"><svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="خريطة التسديدات"><rect x="0" y="0" width="' + W + '" height="' + H + '" class="pitchbg"/><rect x="' + (W * 0.2) + '" y="0" width="' + (W * 0.6) + '" height="' + (H * 0.31) + '" class="ln"/><rect x="' + (W * 0.37) + '" y="0" width="' + (W * 0.26) + '" height="' + (H * 0.1) + '" class="ln"/><line x1="' + (W * 0.44) + '" x2="' + (W * 0.56) + '" y1="1" y2="1" class="goal"/>' + dots + '</svg><p class="muted small"><b class="num">' + sp.shots + "</b> تسديدة، <b class=\"num\">" + sp.goals + "</b> هدف، أهداف متوقعة <b class=\"num\">" + fx(sp.xg, 1) + '</b>. الدائرة المعبّاة هدف، وحجمها قد فرصة التسجيل.</p></div>';
  };
  // ---- loans (147)
  S.loans = function(t){
    var o = t && t.transfers && t.transfers.out; if (!o) return ""; var l = o.filter(function(x){ return x.loan; });
    if (!l.length) return "";
    return '<ol class="lead">' + l.map(function(x){ return '<li><span class="num muted"></span><span class="who">' + (x.to ? R.logo(x.to, "sm") : "") + '<a class="lat" href="/p/' + x.player.id + '/">' + esc(x.player.name) + '</a> <span class="muted">معار لـ ' + (x.to ? R.tname(x.to) : "") + (x.date ? "، من " + esc(R.dayParts(x.date.slice(0, 10)).short) : "") + "</span></span><b></b></li>"; }).join("") + "</ol>";
  };
  // ---- derbies / head to head (38)
  // W4.4: a date line over each result (no 5.5rem column that clipped «الشار…»), the next meeting, and one wins/draws/wins bar
  var MONS = ["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"];
  function dline(iso){ var d = String(iso || "").slice(0, 10).split("-"); return d.length === 3 ? '<span class="num">' + (+d[2]) + "</span> " + MONS[+d[1] - 1] + ' <span class="num">' + d[0] + "</span>" : ""; }
  S.h2hPage = function(h, next){
    var a = team(h.teams[0]), b = team(h.teams[1]), w = h.wins || {}, wa = w[a.id] || 0, wd = w.draws || 0, wb = w[b.id] || 0;
    var list = (h.matches || []).filter(function(m){ return m.score && !(Date.parse(m.kickoff_utc) > Date.now()); }).sort(function(x, y){ return (y.kickoff_utc || "").localeCompare(x.kickoff_utc || ""); }).map(function(m){ m.status = m.status || "finished"; m.kickoff_uae = m.kickoff_uae || m.kickoff_utc; return '<div class="h2hrow"><p class="h2hd muted small">' + dline(m.kickoff_uae) + "</p>" + R.matchRow(m, {}) + "</div>"; }).join("");
    var bar = wa + wd + wb ? '<div class="h2hbar" role="img" aria-label="' + esc((R.li || String)(wa + " فوز لـ" + (a.name_ar || a.name || "") + "، " + wd + " تعادل، " + wb + " فوز لـ" + (b.name_ar || b.name || ""))) + '">' + (wa ? '<i style="flex:' + wa + ";background:" + R.colOn(a.id) + '"></i>' : "") + (wd ? '<i class="d" style="flex:' + wd + '"></i>' : "") + (wb ? '<i style="flex:' + wb + ";background:" + R.colOn(b.id) + '"></i>' : "") + "</div>" : "";
    var nx = next ? '<div class="h2hnext"><span class="kicker">المواجهة الياية</span>' + R.matchRow(next, { date:true }) + "</div>" : "";
    return nx + '<div class="h2hsum"><div><b>' + wa + "</b>فوز " + R.tname(a) + "</div><div><b>" + wd + "</b>تعادل</div><div><b>" + wb + "</b>فوز " + R.tname(b) + "</div></div>" + bar + list;
  };
  S.derbyList = function(idx, have){
    if (!idx || !idx.pairs) return ""; var ps = Object.keys(idx.pairs).filter(function(k){ return have[k]; }).sort(function(x, y){ return idx.pairs[y] - idx.pairs[x]; });
    return ps.length ? '<div class="comps">' + ps.map(function(k){ var t = k.split("-"); return '<a href="/h2h/' + k + '/"><span>' + R.tname(team(t[0])) + " و" + R.tname(team(t[1])) + '</span><span class="muted small num">' + idx.pairs[k] + " مواجهة</span></a>"; }).join("") + "</div>" : "";
  };

  // ---- fatigue (121) and coach impact (123)
  S.fatigue = function(f, only){
    if (!f || !f.teams) return ""; var ids = Object.keys(f.teams).filter(function(id){ return !only || only.indexOf(+id) >= 0; });
    ids.sort(function(a, b){ var x = f.teams[a], y = f.teams[b]; return (y.matches_14d - x.matches_14d) || ((y.afc_km_30d || 0) - (x.afc_km_30d || 0)); });
    var afc = ids.some(function(id){ return f.teams[id].afc_km_30d; });   /* QA 84: the travel column only where Asian travel exists */
    return '<div class="tblwrap"><table class="st"><thead><tr><th style="text-align:start">الفريق</th><th>مباريات آخر 14 يوم</th><th>أيام راحة</th><th>للياية</th>' + (afc ? "<th>سفر آسيا (كم)</th>" : "") + "</tr></thead><tbody>" + ids.map(function(id){ var t = f.teams[id]; return '<tr><td class="tm">' + tl(id) + "</td><td>" + t.matches_14d + "</td><td>" + (t.days_since_last == null ? "—" : t.days_since_last) + "</td><td>" + (t.days_to_next == null ? "—" : t.days_to_next) + "</td>" + (afc ? "<td>" + (t.afc_km_30d ? Number(t.afc_km_30d).toLocaleString("en-US") : "—") + "</td>" : "") + "</tr>"; }).join("") + "</tbody></table></div>" + noteSrc("ضغط المباريات: كم لعب الفريق في آخر أسبوعين، وكم يوم ارتاح" + (afc ? "، وكم كيلو سافر في أبطال آسيا آخر 30 يوم." : "."));
  };
  function coachAgg(hist, comp){ var by = {}; (hist || []).filter(function(h){ return !comp || h.comp === comp; }).forEach(function(h){ var k = h.id || h.name; var a = by[k] = by[k] || { id:k, name:h.name, w:0, d:0, l:0, seasons:[] }; a.w += h.won || 0; a.d += h.drawn || 0; a.l += h.lost || 0; if (a.seasons.indexOf(h.season) < 0) a.seasons.push(h.season); }); return Object.keys(by).map(function(k){ var a = by[k], g = a.w + a.d + a.l; a.g = g; a.ppg = g ? (3 * a.w + a.d) / g : 0; return a; }); }
  S.coachesTeam = function(c, id){
    var t = c && c.teams && c.teams[id]; if (!t || !t.history || !t.history.length) return "";
    var rows = coachAgg(t.history, 538).filter(function(a){ return a.g >= 5; }).sort(function(a, b){ return b.ppg - a.ppg; });
    return '<ol class="lead">' + rows.map(function(a, i){ var cur = t.current && t.current.name === a.name; return '<li><span class="num muted">' + (i + 1) + '</span><span class="who">' + coachA(a) + (cur ? ' <b class="rec">الحالي</b>' : "") + ' <span class="muted">' + a.g + " مباراة: " + a.w + " فوز، " + a.d + " تعادل، " + a.l + " خسارة (" + esc(a.seasons[0]) + (a.seasons.length > 1 ? " لين " + esc(a.seasons[a.seasons.length - 1]) : "") + ")</span></span><b>" + a.ppg.toFixed(2) + "</b></li>"; }).join("") + "</ol>" + noteSrc("نقاط بالمباراة لكل مدرب درّب النادي في الدوري، لمن درّب 5 مباريات أو أكثر.");
  };
  S.coachesLeague = function(c){
    if (!c || !c.teams) return ""; var all = [];
    Object.keys(c.teams).forEach(function(id){ coachAgg(c.teams[id].history, 538).forEach(function(a){ a.team = id; all.push(a); }); });
    all = all.filter(function(a){ return a.g >= 30; }).sort(function(a, b){ return b.ppg - a.ppg; }).slice(0, 12);
    return all.length ? '<ol class="lead">' + all.map(function(a, i){ return '<li><span class="num muted">' + (i + 1) + '</span><span class="who">' + coachA(a) + " " + R.logo(team(a.team), "sm") + ' <span class="muted">' + R.tname(team(a.team)) + "، " + a.g + " مباراة</span></span><b>" + a.ppg.toFixed(2) + "</b></li>"; }).join("") + "</ol>" + noteSrc("أعلى معدل نقاط بالمباراة لمدرب مع نادي في الدوري، لمن درّب 30 مباراة أو أكثر مع نفس النادي.") : "";
  };

  // ---- phase 5 blocks (only rendered when ai/approved.json allows the kind)
  S.aiSummary = function(a){ if (!a) return ""; return '<div class="ai"><b>' + esc(a.headline) + "</b><p>" + esc(a.summary) + '</p><span class="aisrc">كتبها تيفو من أرقام المباراة</span></div>'; };
  S.aiThread = function(a){ if (!a || !a.thread) return ""; return '<ol class="thread">' + a.thread.map(function(t, i){ return '<li><p>' + esc(t) + '</p><button type="button" class="btn copy" data-copy="' + esc(t) + '">انسخ</button></li>'; }).join("") + '</ol><button type="button" class="btn copy" data-copy="' + esc(a.thread.join("\n\n")) + '">انسخ الثريد كامل</button>'; };
  // QA 29: labels come from the file's keyed items ({key, label, text}); an older file without items prints its lines unlabelled
  S.aiPreview = function(a){ if (!a || !(a.items || a.lines)) return ""; var li = a.items && a.items.length ? a.items.map(function(x){ return "<li><b>" + esc(x.label) + ":</b> " + esc(x.text) + "</li>"; }) : a.lines.map(function(l){ return "<li>" + esc(l) + "</li>"; });
    return '<div class="ai"><ul class="prev">' + li.join("") + '</ul><span class="aisrc">كتبها تيفو من الأرقام</span></div>'; };
  // ---- 79: the journalist sheet (numbers only, no AI)
  S.pressSheet = function(m, st, stats, facts, fat, md){
    var rows = st && st.groups && st.groups[0] ? st.groups[0].rows : [], by = {}; rows.forEach(function(r){ by[r.team.id] = r; });
    var side = function(t){ var r = by[t.id], out = "<h3>" + R.tname(t) + "</h3><ul>";
      if (r) out += "<li>المركز " + r.rank + " برصيد " + R.cnt(r.pts, ["نقطة", "نقطتين", "نقاط", "نقطة"], "بدون نقاط") + " من " + R.cnt(r.played, ["مباراة", "مباراتين", "مباريات", "مباراة"]) + " (" + r.won + " فوز، " + r.drawn + " تعادل، " + r.lost + " خسارة)، له " + r.gf + " وعليه " + r.ga + ".</li><li>آخر النتايج: " + (r.form || []).map(function(x){ return { W:"فوز", D:"تعادل", L:"خسارة" }[x]; }).join("، ") + ".</li>";
      var g = stats && stats.lists && (stats.lists.goals || []).filter(function(p){ return p.team && p.team.id === t.id; }).slice(0, 2);
      if (g && g.length) out += "<li>هدافه: " + g.map(function(p){ return '<span class="lat">' + esc(p.player.name) + "</span> (" + p.value + ")"; }).join("، ") + ".</li>";
      var f = fat && fat.teams && fat.teams[t.id]; if (f) out += "<li>لعب " + R.cnt(f.matches_14d, ["مباراة", "مباراتين", "مباريات", "مباراة"]) + " في آخر أسبوعين" + (f.days_since_last != null ? "، وارتاح " + f.days_since_last + " أيام" : "") + (f.afc_km_30d ? "، وسافر " + Number(f.afc_km_30d).toLocaleString("en-US") + " كم في آسيا" : "") + ".</li>";
      return out + "</ul>"; };
    var h = md && md.h2h && md.h2h.summary, p = m.probs || (md && md.probs);
    var body = side(m.home) + side(m.away) + "<h3>بين الفريقين</h3><ul>" + (h ? "<li>المواجهات السابقة: " + h.home_wins + " فوز لـ" + R.tname(m.home) + "، و" + h.draws + " تعادل، و" + h.away_wins + " فوز لـ" + R.tname(m.away) + ".</li>" : "") + (p ? "<li>توقعات تيفو: " + Math.round(p.home * 100) + "% فوز " + R.tname(m.home) + "، " + Math.round(p.draw * 100) + "% تعادل، " + Math.round(p.away * 100) + "% فوز " + R.tname(m.away) + ".</li>" : "") + (facts || []).map(function(f){ return "<li>" + esc(String(f.text_ar).replace(/\s*\(بيانات FotMob\)/g, "")) + "</li>"; }).join("") + "</ul>";
    return '<div class="press">' + body + '<p class="tools"><button type="button" class="btn" id="commbtn">وضع المعلّق</button><button type="button" class="btn" onclick="window.print()">اطبعها</button><button type="button" class="btn copy" data-copy-from=".press">انسخ النص</button></p>' + noteSrc("كل رقم هني من بيانات تيفو (FotMob ورابطة المحترفين). جاهزة للمعلقين والصحفيين.") + "</div>";
  };
  // ---- 58: transfers
  S.transfers = function(tr){
    var l = [], seen = {}; Object.keys((tr && tr.teams) || {}).forEach(function(id){ var t = tr.teams[id]; (t["in"] || []).forEach(function(x){ var k = (x.player && x.player.id) + (x.date || ""); if (!seen[k] && !x.extension){ seen[k] = 1; l.push(x); } }); });
    l.sort(function(a, b){ return (b.date || "").localeCompare(a.date || ""); }); if (!l.length) return "";
    return '<ol class="lead">' + l.slice(0, 30).map(function(x){ return '<li><span class="num muted">' + esc((x.date || "").slice(5, 10)) + '</span><span class="who"><span class="lat">' + esc(x.player && x.player.name) + '</span> <span class="muted">من ' + (x.from ? R.tname(x.from) : "—") + " لـ" + (x.to ? R.tname(x.to) : "—") + (x.loan ? "، إعارة" : x.free_agent ? "، حر" : "") + (x.fee_eur ? "، " + Math.round(x.fee_eur / 1e5) / 10 + " مليون يورو" : "") + "</span></span><b></b></li>"; }).join("") + "</ol>";
  };
  // ---- 27: national team players at their clubs
  S.natClubs = function(t){
    if (!t || !t.squad) return ""; var ps = []; t.squad.forEach(function(g){ if (g.group !== "coach") g.players.forEach(function(p){ ps.push(p); }); });
    if (!ps.length) return "";
    return '<ol class="lead">' + ps.map(function(p){ return '<li><span class="num muted">' + esc(p.number || "") + '</span><span class="who"><a class="lat" href="/p/' + p.id + '/">' + esc(p.name) + '</a> <span class="muted">' + (p.club_id ? '<a href="/t/' + p.club_id + '/">' + esc(p.club || "") + "</a>" : esc(p.club || "")) + (p.abroad ? "، يلعب برا" : "") + "</span></span><b>" + (p.goals || 0) + "</b></li>"; }).join("") + "</ol>" + noteSrc("الرقم على اليسار أهدافه مع المنتخب في هالقائمة.");
  };

  // ---- phase 4 reference pages: legends (106), memorable (108), this day (40), laws (53)
  function srcs(list){ return (list || []).map(function(u){ return typeof u === "string" ? u : u && u.url; }).filter(function(u){ return u && /^https?:/.test(u); }).slice(0, 3).map(function(u, i){ return '<a href="' + esc(u) + '" rel="noopener">' + (i + 1) + "</a>"; }).join(" "); }
  S.legends = function(raw, ar, hasPage){
    return raw.map(function(p){ var k = p.name_en || p.name, a = ar[k]; if (!a) return ""; return '<section class="blk legend" id="' + esc(String(k).toLowerCase().replace(/[^a-z]+/g, "-")) + '"><h2>' + esc(p.name_ar || k) + '<small class="lat">' + esc(k) + "</small></h2><p>" + esc(a.bio) + "</p><ul class=\"facts-l\">" + (a.facts || []).map(function(f){ return "<li>" + esc(f) + "</li>"; }).join("") + '</ul><p class="src">المصادر: ' + srcs(p.sources) + (p.fotmob_id && (!hasPage || hasPage(p.fotmob_id)) ? ' · <a href="/p/' + p.fotmob_id + '/">صفحته في تيفو</a>' : "")   /* QA 56: no label left behind when he has no page */ + "</p></section>"; }).join("");
  };
  // W2.1 (397): competition names in Arabic on /memorable/
  function compAr(c){ c = String(c || ""); var y = (c.match(/^(\d{4}(?:[-–]\d{2})?)/) || [])[1] || "", n = (c.match(/^(\d+)(?:st|nd|rd|th) Arabian Gulf Cup/) || [])[1];
    if (n) return "كأس الخليج " + n; var k = /World Cup qualification/.test(c) ? "تصفيات كأس العالم" : /Club World Cup/.test(c) ? "كأس العالم للأندية" : /FIFA World Cup/.test(c) ? "كأس العالم" : /Asian Cup/.test(c) ? "كأس آسيا" : /Champions League/.test(c) ? "دوري أبطال آسيا" : /Olympics/.test(c) ? "الألعاب الأولمبية" : "";
    return k ? k + (y ? " " + y.replace("-", "/") : "") : (/[\u0600-\u06FF]/.test(c) ? c : ""); }
  S.memorable = function(raw, ar){
    return raw.slice().sort(function(a, b){ return (b.date || "").localeCompare(a.date || ""); }).map(function(m){ var a = ar[m.id]; if (!a) return ""; return '<section class="blk mem"><h2>' + esc(a.title) + '<small class="num">' + esc(m.date) + '</small></h2><p class="score"><span class="lat">' + esc(m.home) + '</span> <b class="num">' + esc(m.score) + '</b> <span class="lat">' + esc(m.away) + "</span>" + (m.pens ? ' <span class="muted">(ترجيح ' + esc(m.pens) + ")</span>" : "") + '</p><p>' + esc(a.why) + '</p><p class="src">' + esc(compAr(m.competition)) + (compAr(m.competition) ? "، " : "") + "المصادر: " + srcs(m.sources) + "</p></section>"; }).join("");
  };
  S.thisday = function(events, ar, mmdd, n){
    var k = function(e){ return e["mm-dd"] + "-" + e.year + "-" + (e.text_en_neutral || "").slice(0, 30); };
    var list = events.filter(function(e){ return e["mm-dd"] === mmdd && ar[k(e)]; }).sort(function(a, b){ return (a.tier === "headline" ? 0 : 1) - (b.tier === "headline" ? 0 : 1) || a.year - b.year; }).slice(0, n || 5);
    return list.length ? '<ul class="facts-l">' + list.map(function(e){ return "<li>" + esc(ar[k(e)].line) + ' <span class="src">' + srcs(e.sources) + "</span></li>"; }).join("") + "</ul>" : "";
  };
  S.laws = function(raw, ar){
    return raw.map(function(t){ var a = ar[t.id]; if (!a) return ""; var q = (t.key_quotes || t.quotes || [])[0]; return '<section class="blk law" id="' + esc(t.id) + '"><h2>' + esc(a.title_ar) + '<small class="lat">' + esc(t.law || "") + "</small></h2><p>" + esc(a.summary) + "</p>" + (a.disallowed && a.disallowed.length ? "<h3>" + (/^(law-?(11|12|14|15|16|8|5)|offside|handball|penalt|throw|goal-kick|kick-off|referee)/i.test(String(t.id)) || /11|12\.1|14|16|15|8\.2|5\.4/.test(String(t.law || "")) ? "ليش ألغى الهدف؟" : "متى ينطبق؟") + "</h3><ul class=\"facts-l\">" + a.disallowed.map(function(x){ return "<li>" + esc(x) + "</li>"; }).join("") + "</ul>" : "") + (q ? '<blockquote class="lat" dir="ltr">' + esc(q.text || q.quote || "") + '</blockquote><p class="src">النص الرسمي: <a href="' + esc(q.url || (t.sources || [])[0] || "") + '" rel="noopener">IFAB</a></p>' : "") + "</section>"; }).join("");
  };

  // ---- 7: where to watch in the UAE; 63: official highlights; 8: stadium guide
  S.watchWhere = function(b){
    if (!b || !b.broadcasters || !b.broadcasters.length) return "";
    return '<ul class="bc">' + b.broadcasters.map(function(x){ return '<li><b>' + esc(x.name_ar || x.name_en) + "</b>" + (x.free ? ' <span class="ok">مجاني</span>' : "") + (x.package_ar || (x.package && /[\u0600-\u06FF]/.test(x.package)) ? ' <span class="muted small">' + esc(x.package_ar || x.package) + "</span>" : "") + (x.price_aed ? ' <span class="num">' + x.price_aed + "</span> درهم" : "") + (x.url ? ' <a class="src" href="' + esc(x.url) + '" rel="noopener">المصدر</a>' : "") + "</li>"; }).join("") + "</ul>" + (b.confidence && b.confidence !== "high" ? '<p class="src">المعلومة من الصحافة، ما لقينا إعلان رسمي للموسم.</p>' : "");
  };
  S.highlight = function(h, md){
    var ch = h && h.channels && h.channels.filter(function(c){ return c.search_url_template && c.posts_per_match_highlights !== false; })[0]; if (!ch) return "";
    var q = "ملخص مباراة " + (md.home.name_ar || md.home.name) + " " + (md.away.name_ar || md.away.name);
    return '<a class="btn" href="' + esc(ch.search_url_template.replace("{q}", encodeURIComponent(q))) + '" rel="noopener" target="_blank">شوف الملخص الرسمي (' + esc(ch.name) + ")</a>";
  };
  function v(f){ return f && f.value != null && f.value !== "" ? f.value : null; }
  function va(f){ return f && f.value_ar ? f.value_ar : v(f); }   // QA 31: research notes carry value_ar next to the English value
  function priceAr(p){ if (p && typeof p === "object"){ var a = p.min, z = p.max || p.max_on_sale; return a != null && z != null && +a !== +z ? a + " - " + z : String(a != null ? a : z); } return String(p); }   // QA 31: «20 درهم», not «20 - 20»
  function enAr(t){ return String(t).replace(/Parking available \(paid\/free not published\)/i, "في مواقف، وما منشور إذا مجانية أو بفلوس").replace(/Free parking/i, "مواقف مجانية").replace(/(\d+)\s*minutes?\s*walking distance/i, "$1 دقايق مشي").replace(/^Nearest station:?\s*/i, "أقرب محطة: ").replace(/^Metro:\s*no.*$/i, "ما في مترو قريب").replace(/^Metro:\s*yes,?\s*/i, "مترو: ").replace(/^Bus:\s*yes,?\s*about\s*([\d.]+)\s*km/i, "باص على بعد حوالي $1 كم").replace(/^Bus:\s*no.*$/i, "ما في باص قريب").replace(/^Parking:\s*/i, "مواقف: "); }
  S.stadium = function(x, T2){
    var L = x.location || {}, G = x.getting_there || {}, K = x.tickets || {}, F = x.facilities || {}, rows = [];
    if (v(x.capacity)) rows.push(["السعة", '<span class="num">' + Number(v(x.capacity)).toLocaleString("en-US") + "</span> مقعد"]);
    if (v(x.opened)) rows.push(["افتُتح", '<span class="num">' + v(x.opened) + "</span>"]);
    var clubs = (x.home_clubs || []).map(function(c){ var t = c.value || {}; return t.fotmob_id ? '<a href="/t/' + t.fotmob_id + '/">' + esc(t.name_ar || t.name_en) + "</a>" : esc(t.name_ar || t.name_en); }).filter(Boolean);
    if (clubs.length) rows.push(["ملعب", clubs.join("، ")]);
    var addr = v(L.address_ar) || v(L.address_en); if (addr) rows.push(["العنوان", esc(addr)]);
    var gm = v(L.google_maps); if (gm) rows.push(["الخريطة", '<a href="' + esc(gm) + '" rel="noopener">افتحه في خرايط قوقل</a>']);
    var AR = function(t){ t = t == null ? "" : String(enAr(t)); return /[\u0600-\u06FF]/.test(t) ? t : ""; };   // W1.7: raw Latin research notes never reach the page
    var metro = AR(va(G.metro_official)); if (metro) rows.push(["المترو", esc(metro)]);
    var bus = (G.bus || []).map(va).filter(Boolean).map(AR).filter(Boolean); if (bus.length) rows.push(["الباص", esc(bus.join("، "))]);
    var park = AR(va(G.parking)); rows.push(["المواقف", park ? esc(park) : '<span class="muted">ما في معلومة منشورة</span>']);
    var pf = v(K.platform); if (pf){ var pn = String(pf.name || pf).split(/\s*[(+]/)[0]; rows.push(["التذاكر", pf.url ? '<a class="lat" href="' + esc(pf.url) + '" rel="noopener">' + esc(pn) + "</a>" : esc(pn)]); }
    var pr = v(K.price_range_aed); if (pr) rows.push(["أسعار التذاكر", '<span class="num">' + esc(priceAr(pr)) + "</span> درهم"]);
    var fac = [["air_conditioned_stands", "مدرجات مكيّفة"], ["covered_seating", "مدرجات مظللة"], ["family_section", "قسم عائلات"], ["prayer_room", "مصلى"]].filter(function(f){ return v(F[f[0]]) === true; }).map(function(f){ return f[1]; });
    if (fac.length) rows.push(["فيه", fac.join("، ")]);
    var src = []; ["capacity", "opened"].forEach(function(k){ (x[k] && x[k].sources || []).forEach(function(u){ if (src.indexOf(u) < 0) src.push(u); }); });
    return '<dl class="facts">' + rows.map(function(r){ return "<div><dt>" + r[0] + "</dt><dd>" + r[1] + "</dd></div>"; }).join("") + '</dl><p class="src">المصادر: ' + srcs(src) + "، وتاريخ التحقق " + esc(x.checked || "") + ".</p>";
  };

  // ---- 180: match day for fans going to the stadium
  S.matchDay = function(md, x){
    if (!x || md.status !== "scheduled") return "";
    var G = x.getting_there || {}, K = x.tickets || {}, rows = [];
    if (md.venue && md.venue.distance_km) rows.push('<li>اطلع من بيتك الساعة <b class="leave num" data-kick="' + esc(md.kickoff_utc) + '">—</b> <span class="muted small">(على حسب إمارتك فوق، والأبواب تفتح قبل المباراة بساعتين)</span></li>');
    var pf = v(K.platform); if (pf) rows.push('<li>التذاكر: ' + (pf.url ? '<a class="lat" href="' + esc(pf.url) + '" rel="noopener">' + esc(String(pf.name || "").split(/\s*[(+]/)[0]) + "</a>" : esc(pf.name)) + (v(K.price_range_aed) ? ' <span class="muted small">(' + esc(priceAr(v(K.price_range_aed))) + " درهم)</span>" : "") + "</li>");
    var fe = v(K.free_entry); if (fe) rows.push("<li>الدخول مجاني للأطفال والنساء وكبار المواطنين حسب الرابطة، والتذاكر تنصرف من أكشاك الملعب يوم المباراة.</li>");
    // QA 31: a note still in English after enAr() is left out (no English sentences in the Arabic page)
    var park = va(G.parking), parkAr = park ? enAr(park) : ""; rows.push("<li>المواقف: " + (parkAr && /[\u0600-\u06FF]/.test(parkAr) && !/[A-Za-z]{4,}\s+[A-Za-z]{3,}/.test(parkAr) ? esc(parkAr) : '<span class="muted">ما في معلومة منشورة</span>') + "</li>");
    var metro = va(G.metro_official), metroAr = metro ? enAr(metro) : ""; if (metroAr && /[\u0600-\u06FF]/.test(metroAr) && !/[A-Za-z]{4,}\s+[A-Za-z]{3,}/.test(metroAr)) rows.push("<li>" + esc(metroAr) + "</li>");
    return '<ul class="facts-l md">' + rows.join("") + '</ul><p><a href="/s/' + esc(x.id) + '/">دليل الملعب كامل</a></p>';
  };
  // ---- 175: travel with your club (continental away matches)
  S.travel = function(t, ms){
    var away = (ms || []).filter(function(m){ return m.away && m.away.id === t.id && [525, 9469, 9470, 10622].indexOf(m.comp) >= 0 && Date.parse(m.kickoff_utc) > Date.now(); });
    if (!away.length) return "";
    return '<ul class="facts-l">' + away.slice(0, 4).map(function(m){ var d = (m.kickoff_uae || "").slice(0, 10), dep = new Date(Date.parse(m.kickoff_utc) - 2 * 864e5).toISOString().slice(0, 10), q = encodeURIComponent("Flights from Dubai to the home city of " + (m.home.name || "") + " on " + dep);
      return "<li>" + R.tname(m.home) + " ضد " + R.tname(t) + ' <span class="muted small">' + R.td(m.kickoff_uae, true) + '</span> <a class="btn copy" href="https://www.google.com/travel/flights?q=' + q + '" rel="noopener" target="_blank">شوف الرحلات</a></li>'; }).join("") + '</ul><p class="src">الرحلات من قوقل فلايتس، قبل المباراة بيومين من دبي. غيّر المدينة والتاريخ من هناك.</p>';
  };

  // ---- 220 fixture difficulty, 222 road to the title (from the Tifo rating; home advantage 40 points like the model)
  function diff(rm, opp, home){ var r = rm[opp]; if (r == null) return 3; var x = r + (home ? -40 : 40); return x < 1480 ? 1 : x < 1560 ? 2 : x < 1640 ? 3 : x < 1720 ? 4 : 5; }
  S.ratingMap = function(r){ var m = {}; ((r && r.teams) || []).forEach(function(t){ m[t.team] = t.rating; }); return m; };
  function nextOf(fx, id, n){ return (fx.matches || []).filter(function(m){ return m.status === "scheduled" && (m.home.id === id || m.away.id === id); }).sort(function(a, b){ return (a.kickoff_utc || "9").localeCompare(b.kickoff_utc || "9"); }).slice(0, n || 5); }
  // QA 83: a whole short name, never a word cut by letter count («شباب الأهلي» → «شباب الأهلي», «الوحدة» stays whole)
  function shortAr(n){ n = String(n || ""); var w = n.split(" "); if (w.length <= 2 && n.length <= 12) return n; var m = { "شباب الأهلي":"شباب الأهلي", "الإمارات":"الإمارات" }; if (m[n]) return m[n]; return w.length > 2 ? w.slice(0, 2).join(" ") : n; }
  function fdrCells(fx, id, rm, n){ return nextOf(fx, id, n).map(function(m){ var h = m.home.id === id, o = h ? m.away : m.home, d = diff(rm, o.id, h); return '<i class="fd f' + d + '" title="' + esc(R.tname(o)) + '">' + esc(shortAr(o.name_ar || o.name)) + "<small>" + (h ? "أرض" : "برا") + "</small></i>"; }).join(""); }
  S.fdr = function(st, fx, rm){
    var rows = st && st.groups && st.groups[0] && st.groups[0].rows; if (!rows || !fx || !Object.keys(rm).length) return "";
    return '<div class="fdr">' + rows.map(function(r){ return '<div class="fr"><span class="who">' + tl(r.team.id) + '</span><span class="fds">' + fdrCells(fx, r.team.id, rm, 5) + "</span></div>"; }).join("") + '</div><p class="legend"><span><i class="fd f1"></i>سهلة</span><span><i class="fd f3"></i>متوسطة</span><span><i class="fd f5"></i>صعبة</span></p>' + noteSrc("الصعوبة من تصنيف تيفو للخصم، مع حساب الأرض والجمهور. المباريات الخمس الياية من اليمين.");
  };
  S.roadTitle = function(st, fx, rm, sim){
    var rows = st && st.groups && st.groups[0] && st.groups[0].rows; if (!rows || !fx || !Object.keys(rm).length) return "";
    var top = rows.slice(0, 4);
    return top.map(function(r){ var ms = nextOf(fx, r.team.id, 99), avg = ms.length ? ms.reduce(function(a, m){ var h = m.home.id === r.team.id; return a + diff(rm, (h ? m.away : m.home).id, h); }, 0) / ms.length : 0, t = sim && sim.teams && sim.teams[r.team.id];
      return '<div class="road"><div class="rh">' + tl(r.team.id) + ' <b class="num">' + r.pts + '</b> نقطة' + (t ? ' <span class="pv">فرصة البطولة ' + pct(t.title) + "%</span>" : "") + '</div><div class="fds">' + fdrCells(fx, r.team.id, rm, 6) + '</div><p class="small muted">متوسط صعوبة باقي مبارياته المنشورة: <b class="num">' + Number(avg).toFixed(1) + "</b> من 5</p></div>"; }).join("");
  };
  // ---- 221 opponent report for fans
  S.oppReport = function(md, cx, stats){
    var gb = cx["goal-bands"] && cx["goal-bands"].teams, sty = cx.style && cx.style.teams, side = function(t){ var out = [], g = gb && gb[t.id], y = sty && sty[t.id] && sty[t.id].style;
      if (g){ var f = g["for"], a = g.against, bands = Object.keys(f), bf = bands.reduce(function(x, k){ return f[k] > f[x] ? k : x; }, bands[0]), ba = bands.reduce(function(x, k){ return a[k] > a[x] ? k : x; }, bands[0]); if (f[bf] > 0) out.push("أكثر وقت يسجل فيه: الدقايق " + bf + " (" + f[bf] + " أهداف)."); if (a[ba] > 0) out.push("أكثر وقت يستقبل فيه: الدقايق " + ba + " (" + a[ba] + " أهداف)."); }
      if (y) out.push("يستحوذ " + fx(y.possession, 0) + "% ويسدد " + fx(y.shots, 1) + " بالمباراة" + (y.ppda != null ? "، وضغطه " + (y.ppda < 11 ? "عالي" : y.ppda < 15 ? "متوسط" : "خفيف") : "") + ".");
      var sc = stats && stats.lists && (stats.lists.goals || []).filter(function(p){ return p.team && p.team.id === t.id; })[0]; if (sc) out.push("أخطر لاعب: " + (sc.player.id ? '<a class="lat" href="/p/' + sc.player.id + '/">' + esc(sc.player.name) + "</a>" : '<span class="lat">' + esc(sc.player.name) + "</span>") + " (" + R.cnt(sc.value, ["هدف", "هدفين", "أهداف", "هدف"]) + ").");
      return out.length ? "<h3>" + R.tname(t) + '</h3><ul class="facts-l">' + out.map(function(x){ return "<li>" + x + "</li>"; }).join("") + "</ul>" : ""; };
    var nat = (T[md.home.id] || {}).national || (T[md.away.id] || {}).national;
    var h = side(md.home) + side(md.away); return h ? h + noteSrc(nat ? "من أرقام الفريقين في هالبطولة." : "من أرقام الفريقين هالموسم في " + (R.compName && S._idx ? R.compName(S._idx, md.comp) || "الدوري" : "الدوري") + ".") : "";
  };
  // ---- 224 records that could fall tonight
  S.recordsTonight = function(list){ if (!list.length) return ""; return '<ul class="facts-l">' + list.map(function(x){ return '<li><a href="/m/' + x.m.id + '/">' + R.tname(x.m.home) + " و" + R.tname(x.m.away) + "</a>: " + esc(String(x.f.text_ar).replace(/\s*\(بيانات FotMob\)/g, "")) + "</li>"; }).join("") + "</ul>"; };
  // ---- 226 referee page, 227 coach page
  S.refPage = function(r, byId){
    var s = r.source_stats && r.comp && r.source_stats.scope_comp === r.comp.id ? r.source_stats : null, rows = [["مباريات هالموسم", r.matches], ["إنذار بالمباراة", fx(r.yellow_per_match, 1)], ["طرد", r.red], ["بلنتي", r.penalties]].concat(r["var"] != null ? [["قرارات الفار", r["var"]]] : []);
    if (s && s.fouls_per_match) rows.push(["أخطاء بالمباراة", fx(s.fouls_per_match, 1) + " (معدل الدوري " + fx(s.fouls_league_avg_per_match, 1) + ")"]);
    return '<dl class="facts">' + rows.map(function(x){ return "<div><dt>" + x[0] + '</dt><dd class="num">' + x[1] + "</dd></div>"; }).join("") + "</dl><h2>مبارياته</h2>" + (r.match_ids || []).map(function(id){ var m = byId(id); if (!m) return ""; var ev = m.events && !(m.coverage_events && m.coverage_events.cards === false) ? m.events : [], y = ev.filter(function(e){ return e.type === "yellow"; }).length, rd = ev.filter(function(e){ return e.type === "red" || e.type === "second_yellow"; }).length;
      return '<div class="h2hrow"><p class="h2hd muted small">' + dline(m.kickoff_uae || m.kickoff_utc) + (ev.length ? ' · <i class="rcard y" aria-hidden="true"></i>' + (y ? '<span class="num">' + y + "</span> " + (y >= 3 && y <= 10 ? "إنذارات" : "إنذار") : "بدون إنذار") + ' · <i class="rcard r" aria-hidden="true"></i>' + (rd ? '<span class="num">' + rd + "</span> طرد" : "بدون طرد") : "") + "</p>" + R.matchRow(m, {}) + "</div>"; }).reverse().join("");
  };
  S.coachPage = function(name, rows, scope){
    var tot = rows.reduce(function(a, x){ a.w += x.won || 0; a.d += x.drawn || 0; a.l += x.lost || 0; return a; }, { w:0, d:0, l:0 }), g = tot.w + tot.d + tot.l;
    return (scope ? '<p class="src scope">الأرقام من مباريات الدوري بس: ' + esc(scope) + ". الكؤوس والمنتخبات مب محسوبة.</p>" : "") + '<div class="pstats"><div><b>' + g + "</b><span>مباراة</span></div><div><b>" + tot.w + "</b><span>فوز</span></div><div><b>" + tot.d + "</b><span>تعادل</span></div><div><b>" + tot.l + "</b><span>خسارة</span></div><div><b>" + fx(g ? (3 * tot.w + tot.d) / g : 0, 2) + '</b><span>نقطة بالمباراة</span></div></div><div class="tblwrap"><table class="st"><thead><tr><th>الموسم</th><th style="text-align:start">النادي</th><th>ف</th><th>ت</th><th>خ</th><th>نقاط بالمباراة</th></tr></thead><tbody>' + rows.map(function(x){ return "<tr><td>" + esc(x.season) + '</td><td class="tm">' + tl(x.team) + "</td><td>" + x.won + "</td><td>" + x.drawn + "</td><td>" + x.lost + "</td><td>" + fx(x.ppg, 2) + "</td></tr>"; }).join("") + "</tbody></table></div>";
  };

  // ================= batch 235-264 =================
  function finished(fx){ return (fx && fx.matches || []).filter(function(m){ return m.status === "finished" && m.score; }).sort(function(a, b){ return (a.kickoff_utc || "").localeCompare(b.kickoff_utc || ""); }); }
  function tableFrom(ms, ids){ var t = {}; (ids || []).forEach(function(id){ t[id] = { id:id, p:0, w:0, d:0, l:0, gf:0, ga:0, pts:0 }; });
    ms.forEach(function(m){ [[m.home.id, m.score.home, m.score.away], [m.away.id, m.score.away, m.score.home]].forEach(function(x){ var r = t[x[0]] = t[x[0]] || { id:x[0], p:0, w:0, d:0, l:0, gf:0, ga:0, pts:0 }; r.p++; r.gf += x[1]; r.ga += x[2]; if (x[1] > x[2]){ r.w++; r.pts += 3; } else if (x[1] === x[2]){ r.d++; r.pts++; } else r.l++; }); });
    return Object.keys(t).map(function(k){ return t[k]; }).sort(function(a, b){ return b.pts - a.pts || (b.gf - b.ga) - (a.gf - a.ga) || b.gf - a.gf; }); }
  S.tableFrom = tableFrom;
  // 236 form table: last 5 league matches per team
  S.formTable = function(fx, st){
    var ids = st && st.groups && st.groups[0] && st.groups[0].rows.map(function(r){ return r.team.id; }); if (!ids || st.composite) return "";
    var fin = finished(fx), last = [];
    ids.forEach(function(id){ fin.filter(function(m){ return m.home.id === id || m.away.id === id; }).slice(-5).forEach(function(m){ if (last.indexOf(m) < 0) last.push(m); }); });
    var rows = ids.map(function(id){ var ms = fin.filter(function(m){ return m.home.id === id || m.away.id === id; }).slice(-5), t = tableFrom(ms, [id]).filter(function(r){ return r.id === id; })[0] || { p:0, pts:0, gf:0, ga:0 }; t.form = ms.map(function(m){ var h = m.home.id === id, a = h ? m.score.home : m.score.away, b = h ? m.score.away : m.score.home; return a > b ? "W" : a === b ? "D" : "L"; }); return t; })
      .sort(function(a, b){ return b.pts - a.pts || (b.gf - b.ga) - (a.gf - a.ga); });
    if (!rows.some(function(r){ return r.p; })) return "";
    return miniTable(rows.map(function(r, i){ return { rank:i + 1, team:r.id, p:r.p, gd:r.gf - r.ga, pts:r.pts, form:r.form }; }), [["p", "لعب"], [gd, "الفرق"], ["pts", "نقاط"], [function(r){ return R.form(r.form); }, "الفورمة"]]) + noteSrc("الترتيب من آخر 5 مباريات لكل فريق بس: منو الساخن الحين ومنو طايح.");
  };
  // 258 games in hand: points per game carried to the same number of games
  S.gamesInHand = function(st){
    var rows = st && st.groups && st.groups[0] && st.groups[0].rows; if (!rows || st.composite) return "";
    var mx = Math.max.apply(null, rows.map(function(r){ return r.played; })); if (rows.every(function(r){ return r.played === mx; })) return "";
    var list = rows.map(function(r){ return { team:r.team.id, played:r.played, hand:mx - r.played, pts:r.pts, proj:r.played ? r.pts + (mx - r.played) * r.pts / r.played : r.pts }; }).sort(function(a, b){ return b.proj - a.proj; });
    return miniTable(list.map(function(r, i){ return Object.assign({ rank:i + 1 }, r); }), [["played", "لعب"], [function(r){ return r.hand ? '<b class="up">' + r.hand + "</b>" : "—"; }, "مباريات بيده"], ["pts", "نقاطه"], [function(r){ return fx(r.proj, 1); }, "لو فاز بنفس معدله"]]) + noteSrc("لو كل فريق لعب مبارياته المؤجلة بنفس معدل نقاطه هالموسم. تقدير بس، مب ترتيب رسمي.");
  };
  // 259 season clock
  S.seasonClock = function(fx, st, watch){
    var all = (fx && fx.matches) || [], done = all.filter(function(m){ return m.status === "finished"; }).length, total = all.length; if (!total) return "";
    var mpt = st && st.magic && st.magic.matches_per_team, teams = st && st.groups && st.groups[0] ? st.groups[0].rows.length : 0, full = mpt && teams ? mpt * teams / 2 : total, pctv = Math.min(1, done / full);
    var last = all.filter(function(m){ return m.kickoff_utc; }).map(function(m){ return m.kickoff_utc; }).sort().pop();
    return '<div class="clock2"><div class="pbar big"><i style="inline-size:' + (pctv * 100).toFixed(1) + '%"></i></div><p><b class="num">' + Math.round(pctv * 100) + "%</b> من الموسم خلص: <b class=\"num\">" + done + "</b> مباراة من <b class=\"num\">" + Math.round(full) + "</b>." + (last ? " آخر مباراة منشورة " + R.td(last, true) + "." : "") + "</p></div>";
  };
  // 254 end-of-season projections for the top scorers
  S.projections = function(stats, st){
    var l = stats && stats.lists && stats.lists.goals, mpt = st && st.magic && st.magic.matches_per_team, rows = st && st.groups && st.groups[0] && st.groups[0].rows; if (!l || !l.length || !mpt || !rows) return "";
    var pl = {}; rows.forEach(function(r){ pl[r.team.id] = r.played; });
    var list = l.slice(0, 10).map(function(p){ var tp = pl[p.team && p.team.id] || 0; return { p:p, proj:tp ? p.value / tp * mpt : null }; }).filter(function(x){ return x.proj; }).sort(function(a, b){ return b.proj - a.proj; });
    return list.length ? '<ol class="lead">' + list.map(function(x, i){ return '<li><span class="num muted">' + (i + 1) + '</span><span class="who">' + R.logo(x.p.team, "sm") + (x.p.player.id ? '<a class="lat" href="/p/' + x.p.player.id + '/">' + esc(x.p.player.name) + "</a>" : esc(x.p.player.name)) + ' <span class="muted small">عنده ' + x.p.value + " الحين</span></span><b>" + Math.round(x.proj) + "</b></li>"; }).join("") + "</ol>" + noteSrc("كم هدف بيوصل كل لاعب في آخر الموسم لو كمّل بنفس معدله مع فريقه (" + mpt + " مباراة).") : "";
  };
  // 252 exact-score probabilities: the two Poisson means that reproduce Tifo's home/draw/away odds, then the grid
  function pois(l, k){ var p = Math.exp(-l); for (var i = 1; i <= k; i++) p *= l / i; return p; }
  function fitLambdas(pr){ var best = null; for (var h = 0.2; h <= 3.6; h += 0.05) for (var a = 0.2; a <= 3.6; a += 0.05){ var ph = 0, pd = 0, pa = 0; for (var i = 0; i < 9; i++) for (var j = 0; j < 9; j++){ var q = pois(h, i) * pois(a, j); if (i > j) ph += q; else if (i === j) pd += q; else pa += q; } var e = Math.pow(ph - pr.home, 2) + Math.pow(pd - pr.draw, 2) + Math.pow(pa - pr.away, 2); if (!best || e < best.e) best = { h:h, a:a, e:e }; } return best; }
  S.scoreGrid = function(pr, md){
    if (!pr || pr.home == null) return ""; var L = fitLambdas(pr), cells = [];
    for (var i = 0; i <= 4; i++) for (var j = 0; j <= 4; j++) cells.push({ h:i, a:j, p:pois(L.h, i) * pois(L.a, j) });
    var top = cells.slice().sort(function(x, y){ return y.p - x.p; }).slice(0, 6), mx = top[0].p;
    return '<div class="sgrid">' + top.map(function(c){ return '<div><b class="num">' + c.h + " - " + c.a + '</b><span class="pbar"><i style="inline-size:' + (c.p / mx * 100).toFixed(0) + '%"></i></span><small class="num">' + Math.round(c.p * 100) + "%</small></div>"; }).join("") + "</div>" + noteSrc("أرجح النتايج بالضبط: أهداف " + R.tname(md.home) + " على اليمين. محسوبة من توقعات تيفو للمباراة، وتقديرية.");
  };
  // 190 league records book
  S.recordsBook = function(rb){
    if (!rb) return ""; var m = function(x){ return '<a href="/m/' + x.match + '/">' + esc(x.home_ar) + " " + '<b class="num">' + x.score[0] + " - " + x.score[1] + "</b> " + esc(x.away_ar) + '</a> <span class="muted small">' + esc(x.season) + "</span>"; }, out = "";
    if (rb.biggest_wins && rb.biggest_wins.length) out += "<h3>أكبر فوز</h3><ol class=\"facts-l\">" + rb.biggest_wins.slice(0, 5).map(function(x){ return "<li>" + m(x) + "</li>"; }).join("") + "</ol>";
    if (rb.highest_scoring && rb.highest_scoring.length) out += "<h3>أكثر مباراة فيها أهداف</h3><ol class=\"facts-l\">" + rb.highest_scoring.slice(0, 5).map(function(x){ return "<li>" + m(x) + ' <span class="muted small">(' + x.goals + " أهداف)</span></li>"; }).join("") + "</ol>";
    var sk = rb.streaks || {}, SK = { winning:"أطول سلسلة انتصارات", unbeaten:"أطول سلسلة بدون خسارة", losing:"أطول سلسلة خسارات" };
    Object.keys(SK).forEach(function(k){ if (sk[k] && sk[k].length) out += "<h3>" + SK[k] + '</h3><ol class="facts-l">' + sk[k].filter(function(x){ return x.length != null; }).slice(0, 3).map(function(x){ return "<li>" + (x.team_ar ? esc(x.team_ar) : R.tname(team(x.team))) + ' <b class="num">' + x.length + "</b> مباريات" + (x.current ? ' <b class="rec">مستمرة</b>' : "") + "</li>"; }).join("") + "</ol>"; });
    var mg = rb.most_goals_in_season; if (mg) out += "<h3>أكثر أهداف في موسم</h3><p>" + esc(mg.team_ar) + ' <b class="num">' + mg.goals + "</b> هدف في موسم " + esc(mg.season) + "</p>";
    if (rb.hat_tricks && rb.hat_tricks.length) out += "<h3>الهاتريك</h3><ol class=\"facts-l\">" + rb.hat_tricks.slice(-8).reverse().map(function(x){ return '<li><a class="lat" href="/p/' + x.player + '/">' + esc(x.name) + '</a> <span class="muted small">' + esc(x.date) + '</span> <a href="/m/' + x.match + '/">المباراة</a></li>'; }).join("") + "</ol>";
    return out + noteSrc("من كل مباريات الدوري المسجّلة من " + esc(rb.since) + " (" + rb.matches + " مباراة).");
  };
  // 247 printable season poster
  S.poster = function(t){
    var fx = (t.fixtures || []).slice().sort(function(a, b){ return (a.kickoff_utc || "9").localeCompare(b.kickoff_utc || "9"); });
    return '<div class="poster" style="--c1:' + R.col(t.id) + ";--c2:" + R.col(t.id, 1) + '"><div class="ph">' + R.logo(t, "lg") + "<h1>" + R.tname(t) + '</h1><span>مباريات الموسم</span></div><table><tbody>' + fx.map(function(m){ var h = m.home.id === t.id, o = h ? m.away : m.home; return "<tr><td>" + (m.kickoff_uae ? R.td(m.kickoff_uae, true) : "لم يحدد") + "</td><td>" + (m.kickoff_uae && !m.time_tbd ? R.tt(m.kickoff_uae) : "") + "</td><td>" + (h ? "ضد" : "في ملعب") + " " + R.tname(o) + '</td><td class="muted">' + esc(m.comp_name_ar || "") + "</td><td>" + (m.score ? '<b class="num">' + (h ? m.score.home + " - " + m.score.away : m.score.away + " - " + m.score.home) + "</b>" : "") + "</td></tr>"; }).join("") + '</tbody></table><p class="pf">tifo.elyoxe.com</p></div><p class="tools noprint"><button type="button" class="btn" onclick="window.print()">اطبع</button></p>';
  };

  // 235 round story: the table before the round, then one step per result in kickoff order (app.js animates)
  S.roundStory = function(fx, rk, ids){
    var all = finished(fx), n = parseFloat(rk), before = all.filter(function(m){ return parseFloat(m.round) < n; }), inr = all.filter(function(m){ return m.round === rk; });
    if (!inr.length || !ids || !ids.length) return "";
    var snaps = [], acc = before.slice(); var snap = function(){ return tableFrom(acc, ids).map(function(r){ return [r.id, r.pts, r.gf - r.ga]; }); };
    snaps.push(snap()); inr.forEach(function(m){ acc.push(m); snaps.push(snap()); });
    var rows = snaps[0].map(function(x, i){ return '<li data-t="' + x[0] + '" style="--i:' + i + '"><span class="rk">' + (i + 1) + "</span>" + tl(x[0]) + '<b class="num pt">' + x[1] + "</b></li>"; }).join("");
    // W4.4: «شغّل الجولة» plays the round on the table (one result every 1.4 s); the results stay listed for reading
    var steps = '<div class="step" data-s="0"><p>قبل الجولة.</p></div>' + inr.map(function(m, i){ return '<div class="step" data-s="' + (i + 1) + '">' + R.matchRow(m, {}) + "</div>"; }).join("");
    return '<div class="story auto"><div class="sthead"><button type="button" class="cta" id="stplay">شغّل الجولة</button><div class="stnow" id="stnow" aria-live="polite"><p class="muted">الترتيب قبل الجولة. اضغط وشوف كل نتيجة شو غيّرت.</p></div></div><ol class="stbl">' + rows + '</ol><div class="steps" hidden>' + steps + '</div></div><script type="application/json" id="storydata">' + JSON.stringify(snaps) + "</script>";
  };
  // 256 cup bracket (+ reach odds when the tournament sim exists)
  var STG = { "1/64":"دور الـ128", "1/32":"دور الـ64", "1/16":"دور الـ32", "1/8":"دور الـ16", "1/4":"ربع النهائي", "1/2":"نص النهائي", "final":"النهائي" };
  S.bracket = function(st, sim){
    var b = st && st.bracket; if (!b || !b.length) return "";
    var POS = { "1":"أول", "2":"ثاني", "3":"ثالث" }, nm = function(t){ var g = t && /^(\d)([A-Z])$/.exec(t.name || ""); if (g) return (POS[g[1]] || g[1]) + " " + R.groupOrd(g[2]); var a = t && t.name_ar ? String(t.name_ar).replace(/المجموعة ([A-Z])\b/g, function(_, l){ return R.groupOrd(l); }) : ""; return a || (t && t.name) || "—"; };
    var fix = function(t){ var sl = t && R.slotAr && R.slotAr(t.name); if (sl) return sl; return t && /^\d[A-Z]$/.test(t.name || "") ? (t.name[0] === "1" ? "أول" : t.name[0] === "2" ? "ثاني" : "ثالث") + " " + R.groupOrd(t.name[1]) : nm(t); };
    return '<div class="bracket">' + b.map(function(stg){ return '<div class="bs"><h3>' + (STG[stg.stage] || esc(stg.stage)) + "</h3>" + stg.ties.map(function(t){ var a = t.aggregate || {}; return '<div class="tie' + (t.winner ? " done" : "") + '"><span>' + esc(fix(t.home)) + '</span><b class="num">' + (t.tbd ? "–" : (a.homeScore + " - " + a.awayScore)) + "</b><span>" + esc(fix(t.away)) + "</span>" + (t.matches && t.matches[0] ? '<a href="/m/' + t.matches[0] + '/">المباراة</a>' : "") + "</div>"; }).join("") + "</div>"; }).join("") + "</div>" + (sim ? S.tsim(sim) : "");
  };
  // 257 qualification calculator for group competitions (scenarios.json)
  S.groupCalc = function(sc){
    if (!sc || !sc.groups || !sc.groups.length) return "";
    return sc.groups.map(function(g){ var ids = Object.keys(g.teams); return "<h3>" + esc(R.stageAr(g.group)) + '</h3><div class="tblwrap"><table class="st"><thead><tr><th style="text-align:start">الفريق</th><th>أحسن مركز</th><th>أسوأ مركز</th><th>لو فاز</th><th>لو تعادل</th><th>لو خسر</th></tr></thead><tbody>' + ids.map(function(id){ var t = g.teams[id], nr = t.next_result || {}, f = function(x){ return x ? (x.best === x.worst ? x.best : x.best + "-" + x.worst) : "—"; };
      return '<tr><td class="tm">' + tl(id) + "</td><td>" + t.best + "</td><td>" + t.worst + '</td><td><bdi dir="ltr">' + f(nr.W) + '</bdi></td><td><bdi dir="ltr">' + f(nr.D) + '</bdi></td><td><bdi dir="ltr">' + f(nr.L) + "</bdi></td></tr>"; }).join("") + "</tbody></table></div>"; }).join("") + noteSrc("كل الاحتمالات لباقي مباريات المجموعة. المراكز بين أحسن وأسوأ حالة.");
  };

  // 212 + 260: club history and trophy cabinet (research/arab_clubs.json); disputed counts shown with every source
  var CUP_AR = { "Egypt Cup":"كأس مصر", "Egyptian Super Cup":"السوبر المصري", "CAF Champions League":"دوري أبطال أفريقيا", "CAF Confederation Cup":"كأس الكونفدرالية الأفريقية", "African Cup Winners' Cup":"كأس الكؤوس الأفريقية", "CAF Super Cup":"السوبر الأفريقي", "AFC Champions League":"دوري أبطال آسيا", "AFC Champions League Elite":"دوري أبطال آسيا للنخبة", "AFC Cup":"كأس الاتحاد الآسيوي", "Asian Cup Winners' Cup":"كأس الكؤوس الآسيوية", "King's Cup":"كأس الملك", "King Cup":"كأس الملك", "Crown Prince Cup":"كأس ولي العهد", "Saudi Super Cup":"كأس السوبر السعودي", "Arab Club Champions Cup":"البطولة العربية للأندية", "Throne Cup":"كأس العرش", "Emir Cup":"كأس الأمير", "Amir Cup":"كأس الأمير", "President's Cup":"كأس رئيس الدولة", "UAE President's Cup":"كأس رئيس الدولة", "Qatar Cup":"كأس قطر", "Algerian Cup":"كأس الجزائر", "Tunisian Cup":"كأس تونس", "Iraq FA Cup":"كأس العراق", "Kuwait Emir Cup":"كأس أمير الكويت", "Crown Prince Cup (Kuwait)":"كأس ولي العهد", "Jordan FA Cup":"كأس الأردن", "Sultan Qaboos Cup":"كأس السلطان قابوس", "King's Cup (Bahrain)":"كأس ملك البحرين", "League Cup":"كأس الرابطة", "Super Cup":"السوبر", "UAE League Cup":"كأس رابطة المحترفين", "UAE Super Cup":"كأس السوبر الإماراتي", "Arabian Gulf Cup":"كأس الخليج", "GCC Champions League":"دوري أبطال الخليج" };
  S.clubHistory = function(c){
    if (!c) return ""; var out = [], cnt = function(x){ if (!x) return ""; var alts = (x.alt || []).filter(function(a){ return a.count != null && a.count !== x.count; }); return '<b class="num">' + x.count + "</b>" + (alts.length ? ' <span class="muted small">(مصادر ثانية تقول ' + alts.map(function(a){ return '<a href="' + esc(a.source) + '" rel="noopener">' + a.count + "</a>"; }).join(" و") + ")</span>" : "") + ' <a class="src" href="' + esc(x.source) + '" rel="noopener">المصدر</a>'; };
    var shelf = [];
    if (c.league_titles && c.league_titles.count != null) shelf.push(["الدوري", cnt(c.league_titles)]);
    (c.domestic_cups || []).forEach(function(d){ if (d.count != null) shelf.push([esc(d.name_ar || CUP_AR[d.name_en] || d.name_en), cnt(d)]); });
    (c.continental || []).forEach(function(d){ if (d.years && d.years.length) shelf.push([esc(d.competition_ar || CUP_AR[d.competition] || d.competition), '<b class="num">' + d.years.length + '</b> <span class="muted small"><bdi dir="ltr">' + d.years.join("، ") + "</bdi></span>"]); });
    if (shelf.length) out.push('<div class="shelf">' + shelf.map(function(x){ return '<div class="cup"><i aria-hidden="true"></i><span>' + x[0] + "</span>" + x[1] + "</div>"; }).join("") + "</div>");
    var rows = []; if (c.founded && c.founded.year) rows.push(["التأسيس", '<span class="num">' + (c.founded.date || c.founded.year) + "</span>"]); if (c.city_ar) rows.push(["المدينة", esc(c.city_ar)]); if (c.stadium && c.stadium.name_ar) rows.push(["الملعب", esc(c.stadium.name_ar) + (c.stadium.capacity ? ' <span class="num muted">' + Number(c.stadium.capacity).toLocaleString("en-US") + "</span>" : "")]); if (c.nicknames_ar && c.nicknames_ar.length) rows.push(["الألقاب", esc(c.nicknames_ar.slice(0, 4).join("، "))]);
    if (rows.length) out.push('<dl class="facts">' + rows.map(function(r){ return "<div><dt>" + r[0] + "</dt><dd>" + r[1] + "</dd></div>"; }).join("") + "</dl>");
    if (c.notable_facts && c.notable_facts.length) out.push('<ul class="facts-l">' + c.notable_facts.map(function(f){ return "<li>" + esc(f.text_ar) + ' <a class="src" href="' + esc(f.source) + '" rel="noopener">المصدر</a></li>'; }).join("") + "</ul>");
    return out.join("");
  };
  // 261: all-time scorers of an Arab league (research/alltime_scorers.json)
  S.alltimeScorers = function(l){
    if (!l || !l.players || !l.players.length) return "";
    var low = /low/.test(l.confidence || "");
    return (low ? '<p class="note">المصادر لهالقائمة قليلة أو مختلفة، فخذها كتقريب.</p>' : "") + '<ol class="lead">' + l.players.slice(0, 15).map(function(p){ return '<li><span class="num muted">' + p.rank + '</span><span class="who"><span>' + esc(p.name_ar || p.name_en) + '</span> <span class="muted small">' + esc((p.clubs || []).join("، ")) + (p.years ? ' <bdi dir="ltr">' + esc(p.years) + "</bdi>" : "") + "</span></span><b>" + p.goals + "</b></li>"; }).join("") + '</ol><p class="src">' + esc(l.era_scope ? "" : "") + "المصادر: " + (l.sources || []).slice(0, 3).map(function(u, i){ return '<a href="' + esc(u) + '" rel="noopener">' + (i + 1) + "</a>"; }).join(" ") + "، حتى " + esc(l.as_of || "") + ".</p>";
  };

  // 219: suspension rules (research/suspension_rules.json) + at-risk list when comp/{id}/suspensions.json exists
  S.suspensions = function(r, sus){
    var out = "";
    if (sus && sus.players && sus.players.length){ var ban = sus.players.filter(function(p){ return p.suspended; }), risk = sus.players.filter(function(p){ return !p.suspended && p.at_risk; });
      if (ban.length) out += "<h3>موقوفين الجولة الياية</h3>" + '<ol class="lead">' + ban.map(function(p){ return '<li><span class="num muted"></span><span class="who">' + R.logo(team(p.team), "sm") + pl(p.id, p.name) + ' <span class="muted">' + esc(p.reason_ar || (p.reason === "red" ? "طرد" : "إنذارات")) + "</span></span><b></b></li>"; }).join("") + "</ol>";
      if (risk.length) out += "<h3>إنذار واحد ويوقف</h3>" + '<ol class="lead">' + risk.map(function(p){ return '<li><span class="num muted"></span><span class="who">' + R.logo(team(p.team), "sm") + pl(p.id, p.name) + ' <span class="muted">' + p.yellows + " إنذارات</span></span><b></b></li>"; }).join("") + "</ol>"; }
    if (!r) return out;
    if (!r.rules || !r.rules.length) return out + '<p class="note">ما لقينا لائحة رسمية لإيقافات هالبطولة.</p>';
    var ar = function(t){ return t && /[\u0600-\u06FF]/.test(t) ? t : ""; };
    var li = r.rules.filter(function(x){ return x.ban_matches != null && (x.repeat_every || x.yellows); }).map(function(x){ return "<li>" + (x.repeat_every ? "كل " + x.repeat_every + " إنذارات" : "عند الإنذار " + x.yellows) + " = إيقاف " + x.ban_matches + (x.ban_matches === 1 ? " مباراة" : x.ban_matches === 2 ? " مباراتين" : " مباريات") + (ar(x.until) ? ' <span class="muted small">(لين ' + esc(x.until) + ")</span>" : "") + "</li>"; });
    if (r.second_yellow_ban && r.second_yellow_ban.matches) li.push("<li>الإنذار الثاني في نفس المباراة (طرد) = إيقاف " + r.second_yellow_ban.matches + " مباراة.</li>");
    if (r.red_ban && r.red_ban.min_matches) li.push("<li>الطرد المباشر = إيقاف " + r.red_ban.min_matches + " مباراة على الأقل.</li>");
    return out + "<h3>قانون الإيقاف</h3><ul class=\"facts-l\">" + li.join("") + "</ul>" + (/low|medium/.test(r.confidence || "") ? '<p class="src">المصدر غير رسمي بالكامل، تأكد من لائحة البطولة.</p>' : "") + '<p class="src">المصادر: ' + srcs(r.sources) + "</p>";
  };
  // 232: official accounts (verified on the club's own site, the league page or YouTube's badge) + YouTube uploads embed
  var OKV = { site_footer:1, league_page:1, yt_badge:1 };
  function pickAcc(list){ list = (list || []).filter(function(a){ return OKV[a.verified_via]; }); return list.filter(function(a){ return a.verified_via === "site_footer"; })[0] || list[0]; }
  S.accounts = function(e){
    if (!e || !/high|medium/.test(e.confidence || "")) return "";
    var L = [], w = e.website; if (w && w.status === "live" && w.url) L.push('<a class="btn" href="' + esc(w.url) + '" rel="noopener">الموقع الرسمي</a>');
    var x = pickAcc(e.x), ig = pickAcc(e.instagram), yt = pickAcc(e.youtube);
    if (x) L.push('<a class="btn" href="' + esc(x.url) + '" rel="noopener">إكس @' + esc(x.handle) + "</a>"); if (ig) L.push('<a class="btn" href="' + esc(ig.url) + '" rel="noopener">إنستقرام</a>'); if (yt) L.push('<a class="btn" href="' + esc(yt.url) + '" rel="noopener">يوتيوب</a>');
    if (!L.length) return "";
    var emb = yt && yt.channel_id ? '<div class="yt"><iframe loading="lazy" title="آخر فيديوهات النادي" src="https://www.youtube-nocookie.com/embed/videoseries?list=UU' + esc(yt.channel_id.slice(2)) + '" allowfullscreen></iframe></div>' : "";
    return '<p class="tools">' + L.join("") + "</p>" + emb + noteSrc("الحسابات متحقق منها من موقع النادي أو صفحة الرابطة.");
  };
  // 331: questions and answers from our data only (static: UAE channels + the general beIN note)
  S.faq = function(md, ww, stadName){
    var q = [], H = md.home.name_ar || md.home.name, A = md.away.name_ar || md.away.name;
    if (md.kickoff_uae) q.push(["متى مباراة " + H + " و" + A + "؟", R.dayLabel(R.ymd(md.kickoff_uae)) + " الساعة " + md.kickoff_uae.slice(11, 16) + " بتوقيت الإمارات، والموقع يعرضها بتوقيت بلدك."]);
    if (ww) q.push(["وين تنقل مباراة " + H + " و" + A + "؟", "في الإمارات: " + ww + ". في باقي الدول العربية شوف قسم «وين تنقل» في الصفحة، ومعظم البطولات الأوروبية والآسيوية على beIN."]);
    if (stadName) q.push(["وين تنلعب المباراة؟", stadName + "."]);
    if (md.referee && md.referee.name) q.push(["منو حكم المباراة؟", md.referee.name + "."]);
    var h = md.h2h && md.h2h.summary, T = function(k){ return k === 0 ? "ولا مرة" : R.n ? R.n(k, ["مرة وحدة", "مرتين", "مرات", "مرة"]) : k + " مرات"; };   // W2.10: counts agree
    if (h) q.push(["كم مرة تقابلوا؟", "فاز " + H + " " + T(h.home_wins) + "، و" + A + " " + T(h.away_wins) + "، وتعادلوا " + T(h.draws) + " في المواجهات المسجّلة."]);
    return q;
  };
  // 187: win probability through the match (match.winprob [[minute, pH, pD, pA]]); kickoff on the right like the page reads
  S.winprob = function(md){
    var w = md.winprob; if (!w || w.length < 5) return "";
    var W = 640, H = 170, max = Math.max(90, w[w.length - 1][0]), x = function(m){ return (W - m / max * W).toFixed(1); };
    var top = w.map(function(p){ return [x(p[0]), (p[1] * H).toFixed(1)]; }), mid = w.map(function(p){ return [x(p[0]), ((p[1] + p[2]) * H).toFixed(1)]; });
    var poly = function(a, b){ return a.map(function(p){ return p.join(","); }).concat(b.slice().reverse().map(function(p){ return p.join(","); })).join(" "); };
    var edge = function(y){ return w.map(function(p){ return [x(p[0]), y]; }); };
    var hc = R.col(md.home.id, 0), ac = R.col(md.away.id, 0); if (hc === ac) ac = R.col(md.away.id, 1);
    var marks = (md.events || []).filter(function(e){ return /^(goal|own_goal|penalty_goal|red|second_yellow)$/.test(e.type) && e.minute != null; }).map(function(e){ var red = /red|second_yellow/.test(e.type), xx = x(Math.min(e.minute, max)); return '<line x1="' + xx + '" x2="' + xx + '" y1="0" y2="' + H + '" class="' + (red ? "wr" : "wg") + '"/><text x="' + xx + '" y="' + (H + 14) + '" text-anchor="middle" class="ax">' + e.minute + (e.added ? "+" + e.added : "") + "'</text>"; }).join("");   /* QA 82 */
    var ax = [0, 45, 90].map(function(m){ return '<text x="' + x(m) + '" y="' + (H + 28) + '" text-anchor="' + (m === 0 ? "end" : m === max ? "start" : "middle") + '" class="ax">' + m + "'</text>"; }).join("");
    var pre = md.winprob_prematch, base = pre && pre.source === "base-rates";
    return '<div class="wp"><svg viewBox="0 -2 ' + W + " " + (H + 34) + '" role="img" aria-label="فرص الفوز خلال المباراة"><polygon points="' + poly(edge(0), top) + '" fill="' + hc + '"/><polygon points="' + poly(top, mid) + '" class="wd"/><polygon points="' + poly(mid, edge(H)) + '" fill="' + ac + '"/>' + marks + ax + '</svg><p class="legend"><span><i style="background:' + hc + '"></i>فوز ' + R.tname(md.home) + '</span><span><i class="wd"></i>تعادل</span><span><i style="background:' + ac + '"></i>فوز ' + R.tname(md.away) + "</span></p>" +
      noteSrc("كل دقيقة نحسب فرص كل نتيجة من الأهداف الباقية المتوقعة. البداية على اليمين، والخطوط أهداف أو طرد." + (base ? " قبل المباراة ما كان عندنا تصنيف للفريقين، فبدينا بالمعدل العام." : "")) + "</div>";
  };
  // 243: firsts inside our data (match.firsts)
  S.firsts = function(md){
    var f = md.firsts; if (!f || !f.length) return "";
    var li = f.map(function(x){ var who = x.player ? '<span class="lat">' + esc(x.name) + "</span>" : "";
      if (x.kind === "first_meeting") return "";   // W2.1 (391): «أوائل» is for milestones only
      if (!x.player) return "";
      if (x.kind === "first_goal_season") return "<li>أول هدف لـ" + who + " هالموسم.</li>";
      if (x.kind === "first_appearance_season") return "<li>أول مشاركة لـ" + who + " هالموسم.</li>";
      return ""; }).filter(Boolean);
    return li.length ? '<ul class="facts-l">' + li.join("") + "</ul>" : "";
  };
  // ---- per-competition analytics files (265-274, 239/248, 241, 312, 325-330); each renders nothing while its file is empty
  function tb(heads, rows){ return '<div class="tblwrap"><table class="st wrapn"><thead><tr>' + heads.map(function(h, i){ return "<th" + (i ? "" : ' style="text-align:start"') + ">" + h + "</th>"; }).join("") + "</tr></thead><tbody>" + rows.join("") + "</tbody></table></div>"; }
  function wdl(x){ return x && x.played ? '<bdi dir="ltr" class="num">' + x.W + "-" + x.D + "-" + x.L + "</bdi>" : "—"; }
  S.firstGoal = function(f){
    if (!f || !f.teams || !Object.keys(f.teams).length) return "";
    var ids = Object.keys(f.teams).sort(function(a, b){ return (f.teams[b].scored_first.win_pct || 0) - (f.teams[a].scored_first.win_pct || 0); });
    return tb(["الفريق", "لما سجل أول", "لما استقبل أول", "قلبها فوز"], ids.map(function(id){ var t = f.teams[id]; return '<tr><td class="tm">' + tl(id) + "</td><td>" + wdl(t.scored_first) + "</td><td>" + wdl(t.conceded_first) + "</td><td>" + (t.comebacks_won || 0) + "</td></tr>"; })) + noteSrc("الأرقام من اليسار: فوز-تعادل-خسارة. «قلبها فوز» = استقبل أول وفاز.");
  };
  S.dropped = function(d){
    if (!d || !d.teams) return ""; var ids = Object.keys(d.teams); if (!ids.some(function(id){ return d.teams[id].dropped_from_winning || d.teams[id].won_from_losing; })) return "";
    var lst = function(k){ return '<ol class="lead">' + ids.filter(function(id){ return d.teams[id][k] > 0; }).sort(function(a, b){ return d.teams[b][k] - d.teams[a][k]; }).slice(0, 6).map(function(id, i){ return '<li><span class="num muted">' + (i + 1) + '</span><span class="who">' + tl(id) + "</span><b>" + d.teams[id][k] + "</b></li>"; }).join("") + "</ol>"; };
    return "<h3>نقاط ضاعت وهو متقدّم</h3>" + lst("dropped_from_winning") + "<h3>نقاط جابها وهو متأخر</h3>" + lst("won_from_losing");
  };
  S.dependence = function(d){
    if (!d || !d.teams) return ""; var ids = Object.keys(d.teams).filter(function(id){ return d.teams[id].goals >= 3 && d.teams[id].top_scorer; }); if (!ids.length) return "";
    ids.sort(function(a, b){ return d.teams[b].top1_share - d.teams[a].top1_share; });
    return '<ol class="lead">' + ids.map(function(id, i){ var t = d.teams[id]; return '<li><span class="num muted">' + (i + 1) + '</span><span class="who">' + R.logo(team(id), "sm") + pl(t.top_scorer.player) + ' <span class="muted small">' + t.top_scorer.goals + " من " + t.goals + " أهداف " + R.tname(team(id)) + "</span></span><b>" + Math.round(t.top1_share) + "%</b></li>"; }).join("") + "</ol>" + noteSrc("نسبة أهداف الفريق اللي سجلها هدافه. كل ما زادت، يعتمد عليه أكثر.");
  };
  S.xiTeam = function(xi, id){
    var t = xi && xi.teams && xi.teams[id]; if (!t || !t.matches) return "";
    var fm = Object.keys(t.formations || {}).sort(function(a, b){ return t.formations[b] - t.formations[a]; });
    return (fm.length ? "<p>الخطط: " + fm.map(function(f){ return '<bdi dir="ltr" class="num">' + esc(f) + "</bdi> (" + t.formations[f] + ")"; }).join("، ") + " من " + t.matches + " مباريات.</p>" : "") +
      (t.most_used_xi && t.most_used_xi.length ? "<h3>أكثر 11 لعبوا أساسيين</h3><ul class=\"sq\">" + t.most_used_xi.map(function(p){ var s = (t.starts || []).filter(function(x){ return x.player === p; })[0]; return "<li>" + pl(p, s && s.name) + (s ? ' <span class="muted small">' + s.starts + " مرة</span>" : "") + "</li>"; }).join("") + "</ul>" : "");
  };
  S.signings = function(s){
    if (!s || !s.signings || !s.signings.length) return "";
    return '<ol class="lead">' + s.signings.filter(function(x){ return x.minutes > 0; }).slice(0, 10).map(function(x, i){ return '<li><span class="num muted">' + (i + 1) + '</span><span class="who">' + R.logo(team(x.team), "sm") + pl(x.player.id, x.player.name) + ' <span class="muted small">' + R.tname(team(x.team)) + (x.from && x.from.id ? "، من " + R.tname(x.from) : "") + "، " + x.minutes + " دقيقة</span></span><b>" + fx(x.rating, 1) + "</b></li>"; }).join("") + "</ol>" + noteSrc("صفقات هالموسم مرتبة بتقييم اللاعب مع ناديه اليديد، وتقل للي لعب أقل من 900 دقيقة.");
  };
  var CHG = { draw_to_win:"قلب التعادل فوز", loss_to_draw:"قلب الخسارة تعادل" };
  S.lateGoals = function(l){
    if (!l || !l.goals || !l.goals.length) return "";
    return '<ul class="facts-l">' + l.goals.slice().sort(function(a, b){ return b.date.localeCompare(a.date); }).map(function(g){ return "<li>" + pl(g.player) + " (" + R.tname(team(g.team)) + ') في الدقيقة <bdi dir="ltr" class="num">90+' + g.added + "</bdi>: " + (CHG[g.change] || "") + ' <a href="/m/' + g.match + '/">المباراة</a></li>'; }).join("") + "</ul>";
  };
  S.milestones = function(m, ids){
    if (!m || !m.items) return ""; var ok = m.items.filter(function(x){ return x.scope === "national" || ids.indexOf(+x.team) >= 0; }); if (!ok.length) return "";
    return '<ul class="facts-l">' + ok.map(function(x){ var what = x.stat === "goals" ? "هدف" : "مباراة"; return "<li>" + pl(x.player, x.name) + " يحتاج <b class=\"num\">" + x.needs + "</b> ويوصل " + x.target + " " + what + " " + (x.scope === "national" ? "مع المنتخب" : "مع " + R.tname(team(x.team))) + ' <span class="muted small">(الحين ' + x.now + ")</span></li>"; }).join("") + "</ul>";
  };
  S.seasons = function(s, cur){
    if (!s || !s.seasons) return ""; var ks = Object.keys(s.seasons).sort().reverse(); if (ks.length < 2) return "";
    var now = s.seasons[cur], line = now && (now.avg_age || now.foreign_share_pct) ? "<p>هالموسم: متوسط أعمار التشكيلات " + (now.avg_age ? '<b class="num">' + fx(now.avg_age, 1) + "</b> سنة" : "") + (now.foreign_share_pct != null ? '، ونسبة دقايق المحترفين الأجانب <b class="num">' + Math.round(now.foreign_share_pct) + "%</b>" : "") + ".</p>" : "";
    return line + tb(["الموسم", "البطل", "الفارق", "أهداف/مباراة", "فوز الأرض", "تعادل"], ks.map(function(k){ var x = s.seasons[k], live = k === cur; return '<tr><td class="num">' + esc(k) + '</td><td class="tm">' + (x.champion ? tl(x.champion) + (live ? ' <span class="muted small">(المتصدر)</span>' : "") : "") + "</td><td>" + (x.title_margin != null ? x.title_margin : "") + "</td><td>" + fx(x.goals_per_game, 2) + "</td><td>" + Math.round(x.home_win_pct) + "%</td><td>" + Math.round(x.draw_pct) + "%</td></tr>"; })) + noteSrc("من جداول محسوبة من نتايج كل موسم. الفارق = نقاط البطل ناقص الثاني.");
  };
  S.alltimeTable = function(a){
    if (!a || !a.table || !a.table.length) return "";
    return tb(["الفريق", "مواسم", "لعب", "فوز", "تعادل", "خسارة", "الفارق", "النقاط", "ألقاب"], a.table.slice(0, 20).map(function(r){ return '<tr><td class="tm"><span class="num muted">' + r.rank + "</span> " + tl(r.team) + "</td><td>" + r.seasons + "</td><td>" + r.played + "</td><td>" + r.won + "</td><td>" + r.drawn + "</td><td>" + r.lost + '</td><td><bdi dir="ltr">' + r.gd + "</bdi></td><td><b>" + r.pts + "</b></td><td>" + (r.titles || "") + "</td></tr>"; })) + noteSrc("مجموع جداول كل موسم من " + esc(a.since || "") + "، والألقاب = المركز الأول في الجداول المحسوبة.");
  };
  S.promoted = function(p){
    if (!p || !p.promoted_now || !p.promoted_now.length) return "";
    var past = (p.past_promoted || []).filter(function(x){ return x.pts_after_same_games != null; }), avg = past.length ? past.reduce(function(a, x){ return a + x.pts_after_same_games; }, 0) / past.length : null;
    return '<ul class="facts-l">' + p.promoted_now.map(function(t){ return "<li>" + tl(t.team) + ': <b class="num">' + t.pts + "</b> نقطة من " + t.played + " مباريات، المركز " + t.rank + ".</li>"; }).join("") + "</ul>" +
      (avg != null ? "<p>الصاعدين من قبل (" + past.length + ' فريق) كان معدلهم <b class="num">' + fx(avg, 1) + "</b> نقطة بعد نفس عدد المباريات.</p>" : "");
  };
  S.championPath = function(c){
    if (!c || !c.champion || !c.matches || !c.matches.length) return "";
    var ms = c.matches, w = ms.filter(function(m){ return m.gf > m.ga; }).length, d = ms.filter(function(m){ return m.gf === m.ga; }).length;
    var strip = '<div class="cpath">' + ms.map(function(m){ var r = m.gf > m.ga ? "W" : m.gf === m.ga ? "D" : "L"; return '<a class="f' + r + '" href="/m/' + m.match + '/" title="' + esc(m.opponent_ar || "") + " " + m.gf + "-" + m.ga + '"></a>'; }).join("") + "</div>";
    var km = Object.keys(c.key_moments || {}).sort().map(function(k){ var x = c.key_moments[k], b = x.biggest_win, l = x.decisive_late_goal; return b || l ? "<li><b>" + ["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"][+k.slice(5) - 1] + "</b>: " + (b ? 'أكبر فوز <bdi dir="ltr" class="num">' + b.gf + "-" + b.ga + "</bdi> على " + esc(b.opponent_ar || "") : "") + (l ? (b ? "، و" : "") + "هدف متأخر حسم المباراة" : "") + "</li>" : ""; }).join("");
    return "<p>" + tl(c.champion) + " " + (c.status === "clinched" ? "حسم اللقب هالموسم" : "بطل موسم " + esc(c.season)) + ': <b class="num">' + w + "</b> فوز و<b class=\"num\">" + d + "</b> تعادل و<b class=\"num\">" + (ms.length - w - d) + "</b> خسارة.</p>" + strip + (km ? '<ul class="facts-l">' + km + "</ul>" : "");
  };
  S.absences = function(a){
    if (!a || !a.teams) return ""; var nm = function(p){ return typeof p === "object" ? pl(p.id || p.player, p.name) + (p.reason ? ' <span class="muted small">' + esc(p.reason) + "</span>" : "") : esc(String(p)); };
    var rows = Object.keys(a.teams).map(function(id){ var t = a.teams[id], all = [].concat(t.unavailable_from_match || [], t.injured_in_squad || []), s = t.suspended || []; return all.length || s.length ? "<li>" + tl(id) + ": " + all.map(nm).concat(s.map(function(p){ return nm(p) + " (موقوف)"; })).join("، ") + "</li>" : ""; }).join("");
    return rows ? '<ul class="facts-l">' + rows + "</ul>" + noteSrc("من قوائم الغيابات والإصابات في FotMob، وتنشر عادة قريب من المباراة.") : "";
  };
  S.gihFile = function(g){
    if (!g || !g.overdue || !g.overdue.length || !g.teams) return "";
    return tb(["الفريق", "المركز", "مؤجلة", "النقاط", "المتوقع", "المركز المعدّل"], g.teams.filter(function(t){ return t.games_in_hand; }).map(function(t){ return '<tr><td class="tm">' + tl(t.team) + "</td><td>" + t.rank + "</td><td>" + t.games_in_hand + "</td><td>" + t.pts + "</td><td>" + fx(t.projected_pts_with_overdue, 1) + "</td><td>" + t.adjusted_rank + "</td></tr>"; })) + noteSrc("المتوقع = نقاطه الحين + النقاط المتوقعة من مبارياته المؤجلة حسب تصنيف تيفو.");
  };
  // 327 club records (team/{id}/records.json), 238 results heatmap (team/{id}/history.json), 244 call-ups
  var STK = { winning:"فوز ورا فوز", unbeaten:"بدون خسارة", losing:"خسارة ورا خسارة", scoring:"يسجل في كل مباراة" };
  S.teamRecords = function(r){
    if (!r || !r.matches) return ""; var li = [];
    if (r.biggest_win) li.push('أكبر فوز <bdi dir="ltr" class="num">' + r.biggest_win.gf + "-" + r.biggest_win.ga + "</bdi> على " + R.tname(team(r.biggest_win.opponent)) + ' <span class="muted small"><bdi dir="ltr">' + esc(r.biggest_win.date) + "</bdi></span>");
    if (r.biggest_loss) li.push('أكبر خسارة <bdi dir="ltr" class="num">' + r.biggest_loss.gf + "-" + r.biggest_loss.ga + "</bdi> من " + R.tname(team(r.biggest_loss.opponent)) + ' <span class="muted small"><bdi dir="ltr">' + esc(r.biggest_loss.date) + "</bdi></span>");
    Object.keys(STK).forEach(function(k){ var s = r.streaks && r.streaks[k]; if (s && s.length) li.push("أطول سلسلة " + STK[k] + ': <b class="num">' + s.length + "</b> مباراة" + (s.current ? ' <span class="muted small">(الحين ' + s.current + ")</span>" : "")); });
    var top = (r.top_scorers || []).filter(function(p){ return p.goals; }).slice(0, 3);
    return '<ul class="facts-l">' + li.map(function(x){ return "<li>" + x + "</li>"; }).join("") + (top.length ? "<li>هدافين هالموسم: " + top.map(function(p){ return "<bdi>" + pl(p.player, p.name) + '</bdi> <b class="num">' + p.goals + "</b>"; }).join("، ") + "</li>" : "") + "</ul>" + noteSrc(r.matches + ' مباراة من <bdi dir="ltr">' + esc(r.since || "") + "</bdi> في كل البطولات المسجّلة.");
  };
  S.heatmap = function(h){
    var ms = h && h.matches; if (!ms || ms.length < 20) return "";
    var by = {}; ms.forEach(function(m){ var y = +m[0].slice(0, 4), mo = +m[0].slice(5, 7), s = mo >= 7 ? y : y - 1; (by[s] = by[s] || []).push(m); });
    var ks = Object.keys(by).sort().reverse();
    return '<div class="hm">' + ks.map(function(k){ var r = by[k], w = r.filter(function(m){ return m[5] === "W"; }).length, d = r.filter(function(m){ return m[5] === "D"; }).length; return '<div class="hmr"><span class="num muted small">' + k + "/" + String(+k + 1).slice(2) + '</span><span class="hmc">' + r.map(function(m){ return '<i class="f' + m[5] + '" title="' + esc(m[0]) + " " + m[3] + "-" + m[4] + '"></i>'; }).join("") + '</span><span class="num small">' + Math.round((3 * w + d) / (3 * r.length) * 100) + "%</span></div>"; }).join("") + "</div>" + noteSrc("كل مربع مباراة (فوز، تعادل، خسارة) في كل البطولات، والنسبة = من النقاط الممكنة.");
  };
  S.callups = function(c){
    if (!c || !c.callups || !c.callups.length) return "";
    return '<ul class="facts-l">' + c.callups.map(function(p){ return "<li>" + pl(p.player, p.name) + (p.iso2 ? ' مع <a href="' + ((S.NATU && S.NATU[p.iso2]) || "/national/" + p.iso2.toLowerCase() + "/") + '">منتخب ' + esc(p.name_ar || "") + "</a>" : "") + "</li>"; }).join("") + "</ul>";
  };
  // 275 career (player/{id}/career.json) and 237 form (player.form: last 10 [match, date, rating, minutes, goals, assists])
  S.career = function(c){
    if (!c || !c.senior || !c.senior.length) return "";
    var row = function(x){ return '<tr><td class="tm">' + (T[x.team] ? tl(x.team) : '<span class="lat">' + esc(x.name) + "</span>") + (x.loan ? ' <span class="muted small">معار</span>' : "") + '</td><td class="small">' + (x.end ? '<bdi dir="ltr">' + esc((x.start || "").slice(0, 4)) + "–" + esc(x.end.slice(0, 4)) + "</bdi>" : "من " + esc((x.start || "").slice(0, 4))) + "</td><td>" + (x.apps ?? "") + "</td><td>" + (x.goals ?? "") + "</td></tr>"; };
    return tb(["النادي", "السنوات", "مباريات", "أهداف"], c.senior.filter(function(x){ return x.apps; }).map(row).concat((c.national_team || []).map(function(x){ return row(Object.assign({}, x, { loan:false })); }))) + noteSrc("من سجل اللاعب في FotMob، كل البطولات.");
  };
  S.form = function(f){
    if (!f || f.length < 3) return ""; var W = 320, H = 110, n = f.length, x = function(i){ return (W - 16 - i / (n - 1) * (W - 32)).toFixed(1); }, y = function(r){ return (H - 12 - (Math.max(5, Math.min(10, r)) - 5) / 5 * (H - 24)).toFixed(1); };
    var pts = f.filter(function(r){ return r[2] != null; }); if (pts.length < 3) return "";
    var d = f.map(function(r, i){ return r[2] == null ? null : [x(i), y(r[2])]; }).filter(Boolean).map(function(p, i){ return (i ? "L" : "M") + p[0] + " " + p[1]; }).join(" ");
    return '<div class="rchart"><svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="تقييمه في آخر المباريات"><line class="base" x1="0" x2="' + W + '" y1="' + y(7) + '" y2="' + y(7) + '"/><path d="' + d + '" stroke="#0A2620"/>' + f.map(function(r, i){ return r[2] == null ? "" : '<circle cx="' + x(i) + '" cy="' + y(r[2]) + '" r="' + (r[4] ? 6 : 4) + '" fill="' + (r[4] ? "#B07A3B" : "#0A2620") + '"><title>' + esc(r[1]) + " " + fx(r[2], 1) + "</title></circle>"; }).join("") + '</svg><p class="muted small">تقييمه في آخر ' + n + " مباريات، والأحدث على اليسار. الخط المتقطع = 7، والنقطة الكبيرة مباراة سجل فيها.</p></div>";
  };
  S.twins = function(t){
    if (!t || !t.twins || !t.twins.length) return "";
    return '<ul class="facts-l">' + t.twins.map(function(x){ return "<li>" + (T[x.team] ? tl(x.team) : esc(x.team_ar || "")) + "</li>"; }).join("") + (t.twin_in_big5 ? "<li>وفي الدوريات الخمس الكبيرة: " + tl(t.twin_in_big5.team) + "</li>" : "") + "</ul>" + noteSrc("الأقرب في الاستحواذ والتسديد والتمرير والمباشرة والعرضيات والضغط واللمسات في منطقة الخصم.");
  };
  // 302 monthly club report (team/{id}/month/YYYY-MM.json), printable
  S.monthReport = function(mo){
    var r = mo.record || {}, tp = mo.table_position || {}, rt = mo.rating || {};
    var st = '<div class="pstats"><div><b>' + (r.W || 0) + "</b><span>فوز</span></div><div><b>" + (r.D || 0) + "</b><span>تعادل</span></div><div><b>" + (r.L || 0) + "</b><span>خسارة</span></div>" + (tp.end ? "<div><b>" + tp.end + "</b><span>المركز" + (tp.start && tp.start !== tp.end ? " (كان " + tp.start + ")" : "") + "</span></div>" : "") + (rt.end ? "<div><b>" + Math.round(rt.end) + "</b><span>تصنيف تيفو" + (rt.start ? " (" + (rt.end >= rt.start ? "+" : "") + Math.round(rt.end - rt.start) + ")" : "") + "</span></div>" : "") + "</div>";
    var res = mo.results.map(function(m){ m.status = m.status || "finished"; m.id = m.id || m.match; return R.matchRow(m, {}); }).join("");
    var top = (mo.top_performers || []).length ? '<ol class="lead">' + mo.top_performers.map(function(p, i){ return '<li><span class="num muted">' + (i + 1) + '</span><span class="who">' + pl(p.player, p.name) + ' <span class="muted small">' + p.matches + " مباريات، " + p.goals + " أهداف، " + p.assists + " صناعة</span></span><b>" + fx(p.avg_rating, 1) + "</b></li>"; }).join("") + "</ol>" : "";
    return st + sec("النتايج", "", res) + (top ? sec("أحسن اللاعبين", "بمتوسط التقييم", top) : "");
  };
  // 196, 197, 231: approved generated text (ai/gen.py), each behind its approved.json key in build.cjs
  S.aiCommentary = function(c){
    if (!c || !c.lines || !c.lines.length) return "";
    return '<ol class="comm">' + c.lines.slice().reverse().map(function(l){ return '<li><b class="num"><bdi dir="ltr">' + (l.min != null ? l.min + "'" : "") + "</bdi></b><span>" + esc(l.text) + "</span></li>"; }).join("") + "</ol>" + noteSrc("كتبها تيفو من أحداث المباراة، والأحدث فوق.");
  };
  S.aiDigest = function(d){
    if (!d || !d.paras || !d.paras.length) return "";
    return "<h3>" + esc(d.title) + "</h3>" + d.paras.map(function(p){ return "<p>" + esc(p) + "</p>"; }).join("") + noteSrc("كتبها تيفو من أرقام الأسبوع.");
  };
  S.aiPower = function(p){
    if (!p || !p.rows || !p.rows.length) return "";
    return '<p class="note">الترتيب حسب تصنيف تيفو لمستوى الفريق على مدى أطول، مب حسب جدول الدوري.</p><ol class="lead pow">' + p.rows.map(function(r, i){ var ch = r.rating_change_last5; return '<li><span class="num muted">' + (i + 1) + '</span><span class="who">' + tl(r.team_id) + '<br><span class="small">' + esc(r.line) + '</span></span><b>' + r.tifo_rating + "</b></li>"; }).join("") + "</ol>" + noteSrc('الرقم = <a href="/glossary/#tifo-rating">تصنيف تيفو</a>. الأسطر كتبها تيفو من الأرقام.');
  };
  if (typeof module !== "undefined" && module.exports) module.exports = S; else root.TS = S;
})(this);
