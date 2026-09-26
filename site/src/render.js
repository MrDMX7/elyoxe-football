/* تيفو renderers: data (schema v1, docs/SCHEMA.md) -> HTML strings. One copy for both sides: build.mjs prerenders every
   page with it (for Google and no-JS), and app.js re-renders the same blocks in the browser from fresh JSON.
   Times: kickoff_uae is already "+04:00", so HH:MM is sliced from the string (no timezone maths). Digits stay Western. */
(function(root){
  "use strict";
  var R = {};
  var MON = ["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"];
  var DAY = ["الأحد","الاثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت"];
  var UAE_COMPS = [538, 11027, 9943, 11026];
  function esc(s){ return s == null ? "" : String(s).replace(/[&<>"']/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]; }); }
  R.esc = esc;
  R.logo = function(t, cls){ if (!t || !t.id) return ""; return '<img class="logo' + (cls ? " " + cls : "") + '" src="/logo/' + t.id + '.png" alt="" loading="lazy" width="24" height="24" onerror="this.style.visibility=\'hidden\'">'; };
  R.tname = function(t){ return t ? esc(t.name_ar || t.name) : ""; };
  R.hhmm = function(iso){ return iso ? iso.slice(11, 16) : ""; };
  R.ymd = function(iso){ return iso ? iso.slice(0, 10) : ""; };
  R.dayLabel = function(ymd, today){
    if (!ymd) return ""; var p = ymd.split("-").map(Number), d = new Date(Date.UTC(p[0], p[1] - 1, p[2]));
    var rel = ""; if (today){ var t = today.split("-").map(Number), diff = Math.round((d - Date.UTC(t[0], t[1] - 1, t[2])) / 864e5); rel = diff === 0 ? "اليوم" : diff === 1 ? "بكرة" : diff === -1 ? "أمس" : ""; }
    var s = DAY[d.getUTCDay()] + " " + p[2] + " " + MON[p[1] - 1]; return rel ? rel + " · " + s : s;
  };
  R.isLive = function(m){ return m.status === "live" || m.status === "ht"; };
  R.statusText = function(m){
    switch (m.status){
      case "live": return m.minute ? '<bdi dir="ltr">' + esc(m.minute) + "'</bdi>" : "مباشر";
      case "ht": return "استراحة";
      case "finished": return m.status_detail === "AET" ? "بعد الإضافي" : m.status_detail === "Pen" ? "بالترجيح" : "انتهت";
      case "postponed": return "تأجلت";
      case "cancelled": return "ألغيت";
      case "abandoned": return "توقفت";
      case "awarded": return "قرار إداري";
      default: return m.time_tbd ? "لم يحدد" : R.hhmm(m.kickoff_uae);
    }
  };
  function scoreStr(m){ return m.score ? m.score.home + " - " + m.score.away : "–"; }
  R.matchRow = function(m, o){
    o = o || {}; var live = R.isLive(m), fin = m.status === "finished", s = m.score, hw = fin && s && s.home > s.away, aw = fin && s && s.away > s.home;
    var mine = o.mine && (m.home.id === o.mine || m.away.id === o.mine);
    return '<a class="m' + (live ? " live" : "") + (mine ? " mine" : "") + '" href="/m/' + m.id + '/" data-mid="' + m.id + '">' +
      '<span class="st">' + (live ? '<i class="livedot"></i>' : "") + R.statusText(m) + (o.date && !live && !fin ? '<br><span class="small">' + esc(R.dayLabel(R.ymd(m.kickoff_uae)).split(" ").slice(1).join(" ")) + "</span>" : "") + "</span>" +
      '<span class="t h' + (hw ? " win" : "") + '">' + R.logo(m.home) + "<span>" + R.tname(m.home) + "</span></span>" +
      '<span class="sc">' + (m.score ? scoreStr(m) : '<span class="muted">' + (m.status === "scheduled" ? "×" : "–") + "</span>") + (m.penalties ? '<br><span class="small muted">(' + m.penalties.home + " - " + m.penalties.away + ")</span>" : "") + "</span>" +
      '<span class="t a' + (aw ? " win" : "") + '">' + R.logo(m.away) + "<span>" + R.tname(m.away) + "</span></span></a>";
  };
  R.compOrder = function(index){ var o = {}; (index.competitions || []).forEach(function(c, i){ o[c.id] = i; }); return o; };
  R.compName = function(index, id){ var c = (index.competitions || []).filter(function(c){ return c.id === id; })[0]; return c ? c.name_ar : ""; };
  R.compKey = function(index, id){ var c = (index.competitions || []).filter(function(c){ return c.id === id; })[0]; return c ? c.key : null; };
  // matches grouped by competition, UAE first, then index order
  R.dayList = function(matches, index, o){
    o = o || {}; var ord = R.compOrder(index), g = {};
    (matches || []).forEach(function(m){ (g[m.comp] = g[m.comp] || []).push(m); });
    var ids = Object.keys(g).map(Number).sort(function(a, b){ return (ord[a] == null ? 999 : ord[a]) - (ord[b] == null ? 999 : ord[b]); });
    if (o.mine){ ids.sort(function(a, b){ var fa = g[a].some(function(m){ return m.home.id === o.mine || m.away.id === o.mine; }), fb = g[b].some(function(m){ return m.home.id === o.mine || m.away.id === o.mine; }); return (fb ? 1 : 0) - (fa ? 1 : 0); }); }
    if (!ids.length) return '<p class="empty">' + (o.empty || "ما في مباريات.") + "</p>";
    return ids.map(function(id){
      var ms = g[id].sort(function(a, b){ return (a.kickoff_utc || "").localeCompare(b.kickoff_utc || ""); }), key = R.compKey(index, id), name = R.compName(index, id) || ms[0].comp_name_ar || "";
      var live = ms.filter(R.isLive).length;
      return '<section class="comp-block"><div class="comp-head">' + (key ? '<a href="/c/' + key + '/">' + esc(name) + "</a>" : esc(name)) + (ms[0].stage && /Gr(ou)?p/i.test(ms[0].stage) ? ' <span class="muted">' + esc(R.stageAr(ms[0].stage)) + "</span>" : "") + (live ? ' <span class="muted"><i class="livedot"></i>' + live + " مباشر</span>" : "") + "</div>" +
        ms.map(function(m){ return R.matchRow(m, o); }).join("") + "</section>";
    }).join("");
  };

  // standings
  R.form = function(f){ return '<span class="form">' + (f || []).slice(-5).map(function(x){ return '<i class="' + esc(x) + '">' + ({W:"ف",D:"ت",L:"خ"}[x] || "") + "</i>"; }).join("") + "</span>"; };
  var ZONE_AR = { "tr_afcchampionsleague":"دوري أبطال آسيا للنخبة", "tr_afcchampionsleaguequal":"ملحق أبطال آسيا للنخبة", "relegation":"الهبوط", "tr_afccup":"دوري أبطال آسيا 2", "championsleague":"دوري أبطال أوروبا", "europaleague":"الدوري الأوروبي", "promotion":"الصعود", "playoff":"الملحق" };
  R.stageAr = function(s){ if (!s) return ""; var g = /Gr(?:ou)?p\.?\s*([A-Z0-9]+)/i.exec(s); return g ? "المجموعة " + g[1] : s; };
  function zoneName(z){ if (!z) return ""; var k = z.key || ""; if (/AFC Cup|Champions League Two|ACL ?2/i.test(z.label || "")) return "دوري أبطال آسيا 2"; for (var p in ZONE_AR) if (k.indexOf(p) >= 0 && (p !== "tr_afcchampionsleague" || k === p)) return ZONE_AR[p]; if (/relegat/i.test(z.label || k)) return "الهبوط"; if (/qualif|next round|knockout|playoff/i.test(z.label || "")) return "التأهل"; return z.label || ""; }
  R.standings = function(st, o){
    o = o || {}; if (!st || !st.groups || !st.groups.length) return '<p class="empty">ما في ترتيب لهالبطولة.</p>';
    return st.groups.map(function(g){
      var zones = {}; g.rows.forEach(function(r){ if (r.zone && r.zone.color) zones[r.zone.color] = zoneName(r.zone); });
      return (g.name ? "<h3>" + esc(g.name_ar || R.stageAr(g.name)) + "</h3>" : "") + '<div class="tblwrap"><table class="st"><thead><tr><th>#</th><th style="text-align:start">الفريق</th><th>لعب</th><th class="hx">ف</th><th class="hx">ت</th><th class="hx">خ</th><th class="hx">له/عليه</th><th>فرق</th><th>نقاط</th><th class="hx">آخر 5</th></tr></thead><tbody>' +
        g.rows.map(function(r){ return '<tr class="' + (o.mine === r.team.id ? "mine " : "") + (r.live ? "live" : "") + '" data-tid="' + r.team.id + '"><td class="rk">' + (r.zone && r.zone.color ? '<i style="background:' + esc(r.zone.color) + '"></i>' : "") + r.rank + '</td><td class="tm"><a href="/t/' + r.team.id + '/">' + R.logo(r.team, "sm") + R.tname(r.team) + "</a></td><td>" + r.played + '</td><td class="hx">' + r.won + '</td><td class="hx">' + r.drawn + '</td><td class="hx">' + r.lost + '</td><td class="hx">' + r.gf + " - " + r.ga + '</td><td><bdi dir="ltr">' + (r.gd > 0 ? "+" : "") + r.gd + '</bdi></td><td class="pts">' + r.pts + '</td><td class="hx">' + R.form(r.form) + "</td></tr>"; }).join("") +
        "</tbody></table></div>" + (Object.keys(zones).length ? '<div class="legend">' + Object.keys(zones).map(function(c){ return '<span><i style="background:' + esc(c) + '"></i>' + esc(zones[c]) + "</span>"; }).join("") + "</div>" : "");
    }).join("");
  };
  // live table: standings adjusted by live scores (feature 117)
  R.liveTable = function(st, live){
    if (!st || !st.groups || !live || !live.length) return st;
    var copy = JSON.parse(JSON.stringify(st)), changed = false;
    copy.groups.forEach(function(g){
      var by = {}; g.rows.forEach(function(r){ by[r.team.id] = r; });
      live.forEach(function(m){
        var h = by[m.home.id], a = by[m.away.id]; if (!h || !a || !m.score) return; changed = true;
        var hs = m.score.home, as = m.score.away; [[h, hs, as], [a, as, hs]].forEach(function(x){ var r = x[0]; r.played++; r.gf += x[1]; r.ga += x[2]; r.gd = r.gf - r.ga; if (x[1] > x[2]){ r.won++; r.pts += 3; } else if (x[1] === x[2]){ r.drawn++; r.pts += 1; } else r.lost++; r.live = true; });
      });
      g.rows.sort(function(x, y){ return y.pts - x.pts || y.gd - x.gd || y.gf - x.gf || x.rank - y.rank; });
      g.rows.forEach(function(r, i){ r.rank = i + 1; });
    });
    copy.is_live = changed; return copy;
  };
  R.leaders = function(stats, key, n){
    var l = stats && stats.lists && stats.lists[key]; if (!l || !l.length) return '<p class="empty">للحين ما في أرقام.</p>';
    return '<ol class="lead">' + l.slice(0, n || 20).map(function(p){ return '<li><span class="num muted">' + p.rank + '</span><span class="who">' + R.logo(p.team, "sm") + '<span class="lat">' + esc(p.player.name) + '</span> <span class="muted small">' + R.tname(p.team) + "</span></span><b>" + p.value + "</b></li>"; }).join("") + "</ol>";
  };
  // fixtures by round; opens on the next unplayed round
  R.rounds = function(fx){
    var r = {}, order = []; (fx.matches || []).forEach(function(m){ var k = m.round || m.stage || "—"; if (!r[k]){ r[k] = []; order.push(k); } r[k].push(m); });
    order.sort(function(a, b){ var x = parseFloat(a), y = parseFloat(b); if (!isNaN(x) && !isNaN(y)) return x - y; return (r[a][0].kickoff_utc || "").localeCompare(r[b][0].kickoff_utc || ""); });
    return { order:order, by:r };
  };
  R.roundLabel = function(k){ return isNaN(parseFloat(k)) ? esc(k) : "الجولة " + esc(k); };
  R.roundList = function(ms, o){ return ms.slice().sort(function(a, b){ return (a.kickoff_utc || "").localeCompare(b.kickoff_utc || ""); }).map(function(m){ return R.matchRow(m, { date:true, mine:o && o.mine }); }).join(""); };

  // match page
  var EV = { goal:"هدف", penalty_goal:"هدف من بلنتي", own_goal:"هدف في مرماه", missed_penalty:"بلنتي ضايع", yellow:"إنذار", red:"طرد", second_yellow:"إنذار ثاني وطرد", sub:"تبديل", var:"الفار" };
  function evIcon(t){ if (t === "yellow") return '<i class="ico yellow"></i>'; if (t === "red" || t === "second_yellow") return '<i class="ico red"></i>'; if (/goal/.test(t)) return "⚽"; if (t === "sub") return "⇄"; if (t === "missed_penalty") return "✕"; if (t === "var") return "📺"; return "•"; }
  R.events = function(md){
    var ev = md.events || []; if (!ev.length) return '<p class="empty">' + (md.status === "scheduled" ? "المباراة ما بدت." : "ما في أحداث مسجّلة.") + "</p>";
    return '<ul class="ev">' + ev.map(function(e){
      if (e.type === "half"){ var hl = { HT:"نهاية الشوط الأول", FT:"نهاية المباراة", AET:"نهاية الوقت الإضافي", "EHT":"نهاية الشوط الإضافي الأول", Pen:"ركلات الترجيح" }[e.detail] || esc(e.detail); return '<li class="div">' + hl + (e.score ? ' <span class="num">' + e.score.home + " - " + e.score.away + "</span>" : "") + "</li>"; }
      if (e.type === "added_time") return '<li class="div">+' + esc(e.detail) + " دقايق وقت بدل ضايع</li>";
      var who = e.player ? '<span class="lat">' + esc(e.player.name) + "</span>" : "";
      var extra = e.type === "sub" && e.player_out ? '<span class="sub">طلع: <span class="lat">' + esc(e.player_out.name) + "</span></span>" : e.assist ? '<span class="sub">صناعة: <span class="lat">' + esc(e.assist.name) + "</span></span>" : "";
      var body = evIcon(e.type) + " " + who + (/goal/.test(e.type) && e.score ? ' <b class="num">' + e.score.home + " - " + e.score.away + "</b>" : "") + (e.type !== "goal" && e.type !== "sub" && EV[e.type] ? ' <span class="muted small">' + EV[e.type] + "</span>" : "") + extra;
      var mn = '<bdi dir="ltr">' + esc(e.minute) + (e.added ? "+" + esc(e.added) : "") + "'</bdi>";
      return e.team === "home" ? '<li><span class="h">' + body + '</span><span class="mn">' + mn + "</span><span></span></li>" : '<li><span></span><span class="mn">' + mn + "</span><span>" + body + "</span></li>";
    }).join("") + "</ul>";
  };
  function rt(r){ if (r == null) return ""; var c = r >= 7.5 ? "hi" : r >= 6.5 ? "mid" : "lo"; return '<span class="rt ' + c + '">' + Number(r).toFixed(1) + "</span>"; }
  function players(list){ return "<ul>" + (list || []).map(function(p){ return '<li><span class="no">' + esc(p.number || "") + '</span><span class="lat">' + esc(p.name) + "</span>" + (p.captain ? ' <span class="muted small">(C)</span>' : "") + (p.country && p.country !== "UAE" ? ' <span class="flag">' + esc(p.country) + "</span>" : "") + rt(p.rating) + "</li>"; }).join("") + "</ul>"; }
  R.lineups = function(md){
    var L = md.lineups; if (!L || !L.home) return '<p class="empty">التشكيلة تنزل قبل المباراة بساعة تقريباً.</p>';
    function side(s, t){ if (!s) return ""; return '<div><h3><span>' + R.logo(t, "sm") + " " + R.tname(t) + '</span><span class="num muted">' + esc(s.formation || "") + "</span></h3>" + players(s.starters) + (s.subs && s.subs.length ? '<p class="muted small">الاحتياط</p>' + players(s.subs) : "") + (s.coach ? '<p class="muted small">المدرب: <span class="lat">' + esc(s.coach.name) + "</span></p>" : "") + (s.unavailable && s.unavailable.length ? '<p class="muted small">غايبين: ' + s.unavailable.map(function(u){ return '<span class="lat">' + esc(u.name) + "</span> (" + (u.type === "injury" ? "إصابة" : u.type === "suspension" ? "إيقاف" : esc(u.type)) + ")"; }).join("، ") + "</p>" : "") + "</div>"; }
    return (L.type === "lastStarting11" ? '<p class="note">هذي آخر تشكيلة لعبوا فيها، مب التشكيلة الرسمية للمباراة.</p>' : "") + '<div class="lu">' + side(L.home, md.home) + side(L.away, md.away) + "</div>";
  };
  var STAT_AR = { BallPossesion:"الاستحواذ %", total_shots:"التسديدات", ShotsOnTarget:"على المرمى", ShotsOffTarget:"برا المرمى", big_chance:"فرص محققة", big_chance_missed_title:"فرص ضايعة", corners:"الركنيات", fouls:"الأخطاء", Offsides:"التسلل", yellow_cards:"الإنذارات", red_cards:"الطرد", passes:"التمريرات", accurate_passes:"تمريرات صحيحة", keeper_saves:"تصديات الحارس", touches_opp_box:"لمسات في منطقة الخصم", expected_goals:"الأهداف المتوقعة", blocked_shots:"تسديدات مصدودة", shots_inside_box:"تسديدات من داخل المنطقة", shots_outside_box:"تسديدات من برا المنطقة", shots_woodwork:"القائم والعارضة", interceptions:"قطع الكورة", clearances:"إبعاد", "matchstats.headers.tackles":"الافتكاك", duel_won:"التحامات ناجحة", aerials_won:"كرات هوائية", dribbles_succeeded:"مراوغات ناجحة", accurate_crosses:"عرضيات صحيحة", long_balls_accurate:"كرات طويلة صحيحة", player_throws:"رميات تماس", own_half_passes:"تمريرات في نصه", opposition_half_passes:"تمريرات في نص الخصم", ground_duels_won:"التحامات أرضية", shot_blocks:"صدّ تسديدات" };
  R.stats = function(md){
    var g = (md.stats || [])[0]; if (!g) return '<p class="empty">الإحصائيات تنزل مع بداية المباراة.</p>';
    var items = []; (md.stats || []).forEach(function(s){ s.items.forEach(function(i){ if (STAT_AR[i.key] && !items.some(function(x){ return x.key === i.key; })) items.push(i); }); });
    return items.map(function(i){ var h = parseFloat(i.home) || 0, a = parseFloat(i.away) || 0, t = h + a || 1; return '<div class="stat"><span class="l">' + STAT_AR[i.key] + '</span><span class="v">' + esc(i.home) + '</span><span class="bar2"><i style="inline-size:' + (h / t * 100).toFixed(1) + '%"></i><i style="inline-size:' + (a / t * 100).toFixed(1) + '%"></i></span><span class="v">' + esc(i.away) + "</span></div>"; }).join("");
  };
  R.h2h = function(md){
    var h = md.h2h; if (!h || !h.summary) return '<p class="empty">ما في مواجهات سابقة مسجّلة.</p>';
    var s = h.summary;
    return '<div class="h2hsum"><div><b>' + s.home_wins + "</b>" + R.tname(md.home) + "</div><div><b>" + s.draws + "</b>تعادل</div><div><b>" + s.away_wins + "</b>" + R.tname(md.away) + "</div></div>" +
      (h.matches || []).slice(0, 10).map(function(m){ m.status = m.status || "finished"; return R.matchRow(m, { date:true }).replace('<span class="st">', '<span class="st"><span class="small">' + esc(R.ymd(m.kickoff_uae || m.kickoff_utc)) + "</span><br>"); }).join("");
  };
  R.matchHead = function(md){
    var live = R.isLive(md);
    return '<div class="mh' + (live ? " live" : "") + '"><a class="tm" href="/t/' + md.home.id + '/">' + R.logo(md.home, "lg") + R.tname(md.home) + "</a>" +
      "<div>" + (md.score ? '<div class="score">' + md.score.home + " - " + md.score.away + "</div>" : '<div class="score">' + R.hhmm(md.kickoff_uae) + "</div>") +
      (md.penalties ? '<div class="pens">الترجيح ' + md.penalties.home + " - " + md.penalties.away + "</div>" : "") +
      '<div class="status">' + (live ? '<i class="livedot"></i>' : "") + (md.status === "scheduled" ? esc(R.dayLabel(R.ymd(md.kickoff_uae))) : R.statusText(md)) + (md.halftime_score && md.status === "finished" ? ' · الشوط الأول <span class="num">' + md.halftime_score.home + " - " + md.halftime_score.away + "</span>" : "") + "</div></div>" +
      '<a class="tm" href="/t/' + md.away.id + '/">' + R.logo(md.away, "lg") + R.tname(md.away) + "</a></div>";
  };
  R.matchFacts = function(md, index){
    var f = [], key = R.compKey(index, md.comp);
    f.push(key ? '<a href="/c/' + key + '/">' + esc(md.comp_name_ar || R.compName(index, md.comp)) + "</a>" : esc(md.comp_name_ar || ""));
    if (md.round && !isNaN(parseFloat(md.round))) f.push("الجولة " + esc(md.round));
    f.push(esc(R.dayLabel(R.ymd(md.kickoff_uae))) + " · " + R.hhmm(md.kickoff_uae) + " بتوقيت الإمارات");
    if (md.venue) f.push("🏟 " + esc(md.venue.name_ar || md.venue.name_en || md.venue.name));
    if (md.referee) f.push("الحكم: <span class=\"lat\">" + esc(md.referee.name || md.referee) + "</span>");
    if (md.attendance) f.push("الحضور: <span class=\"num\">" + Number(md.attendance).toLocaleString("en-US") + "</span>");
    var notes = "";
    if (md.prayer && md.prayer.clashes && md.prayer.clashes.length){
      var P = { fajr:"الفجر", dhuhr:"الظهر", asr:"العصر", maghrib:"المغرب", isha:"العشاء" }, S = { halftime:"وقت الاستراحة", first_half:"في الشوط الأول", second_half:"في الشوط الثاني", before:"قبل البداية" };
      notes += '<div class="note pray">🕌 ' + md.prayer.clashes.map(function(c){ return "أذان " + (P[c.prayer] || esc(c.prayer)) + " الساعة <span class=\"num\">" + esc(c.at_uae) + "</span> — " + (S[c.segment] || "") + (c.segment !== "halftime" && c.minute_of_play != null ? " (حوالي الدقيقة " + c.minute_of_play + ")" : ""); }).join("<br>") + (md.prayer.estimated_window ? ' <span class="muted small">(تقريبي)</span>' : "") + "</div>";
    }
    var w = md.weather; if (w && w.available){ notes += '<div class="note">🌡 وقت ضربة البداية: <span class="num">' + Math.round(w.temp_c) + "°</span>، الرطوبة <span class=\"num\">" + Math.round(w.humidity) + "%</span>" + (w.heat_index_c ? "، الإحساس <span class=\"num\">" + Math.round(w.heat_index_c) + "°</span>" : "") + (w.heat_category === "danger" || w.heat_category === "extreme" ? " — <b>حر شديد، خذ ماي وايد لو بتحضر</b>" : "") + "</div>"; }
    return '<div class="facts">' + f.join("<span class=\"muted\">·</span>") + "</div>" + notes;
  };

  // team page blocks
  var GROUP_AR = { keepers:"حراس المرمى", defenders:"الدفاع", midfielders:"الوسط", attackers:"الهجوم", coach:"الجهاز الفني" };
  R.squad = function(t){
    if (!t.squad || !t.squad.length) return '<p class="empty">ما في قائمة لاعبين.</p>';
    return t.squad.filter(function(g){ return g.group !== "coach"; }).map(function(g){ return "<h3>" + (GROUP_AR[g.group] || esc(g.group)) + '</h3><div class="squad">' + g.players.map(function(p){ return '<div><span class="no">' + esc(p.number || "") + '</span><span class="lat">' + esc(p.name) + "</span>" + (p.country && p.country !== t.country ? ' <span class="flag">' + esc(p.country) + "</span>" : "") + (p.club && t.national ? ' <span class="muted small">' + esc(p.club) + "</span>" : "") + (p.injury ? ' <span title="مصاب">🩹</span>' : "") + '<span class="x">' + (p.goals ? p.goals + "⚽ " : "") + (p.assists ? p.assists + "🅰" : "") + "</span></div>"; }).join("") + "</div>"; }).join("");
  };
  R.teamFixtures = function(t, o){
    var fx = (t.fixtures || []).slice().sort(function(a, b){ return (a.kickoff_utc || "").localeCompare(b.kickoff_utc || ""); });
    var now = Date.now(), done = function(m){ return m.status === "finished" || m.status === "awarded" || m.status === "abandoned" || (m.status !== "live" && m.status !== "ht" && Date.parse(m.kickoff_utc) < now - 3 * 3600e3); };
    var past = fx.filter(function(m){ return done(m) && m.status !== "cancelled" && m.status !== "postponed"; }).reverse(), next = fx.filter(function(m){ return !done(m) && m.status !== "cancelled"; });
    return { past:past, next:next };
  };
  R.UAE_COMPS = UAE_COMPS;
  if (typeof module !== "undefined" && module.exports) module.exports = R; else root.TR = R;
})(this);
