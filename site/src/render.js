/* تيفو renderers: data (schema v1, docs/SCHEMA.md) -> HTML strings. One copy for both sides: build.cjs prerenders every
   page with it (for Google and no-JS), and app.js re-renders the same blocks in the browser from fresh JSON.
   Times: kickoff_uae is already "+04:00", so HH:MM is sliced from the string (no timezone maths). Digits stay Western.
   Design (site/DESIGN.md): the atom is a flat card; the scoreboard is night pitch; time on the match line flows right->left. */
(function(root){
  "use strict";
  var R = {}, TC = (root && root.TC) || {};
  var MON = ["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"];
  var DAY = ["الأحد","الاثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت"];
  var UAE_COMPS = [538, 11027, 9943, 11026];
  function esc(s){ return s == null ? "" : String(s).replace(/[&<>"']/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]; }); }
  R.esc = esc;
  R.setColors = function(m){ TC = m || {}; };
  R.col = function(id, i){ var c = TC[id]; return c ? (c[i || 0] || c[0]) : (i ? "#F6F7F2" : "#5C6660"); };
  R.logo = function(t, cls){ if (!t || !t.id) return ""; return '<img class="logo' + (cls ? " " + cls : "") + '" src="/logo/' + t.id + '.png" alt="" loading="lazy" width="24" height="24" onerror="this.style.visibility=\'hidden\'">'; };
  R.tname = function(t){ return t ? esc(t.name_ar || t.name) : ""; };
  R.hhmm = function(iso){ return iso ? iso.slice(11, 16) : ""; };
  R.ymd = function(iso){ return iso ? iso.slice(0, 10) : ""; };
  function dparts(ymd, today){
    if (!ymd) return { rel:"", date:"" }; var p = ymd.split("-").map(Number), d = new Date(Date.UTC(p[0], p[1] - 1, p[2]));
    var rel = ""; if (today){ var t = today.split("-").map(Number), diff = Math.round((d - Date.UTC(t[0], t[1] - 1, t[2])) / 864e5); rel = diff === 0 ? "اليوم" : diff === 1 ? "بكرة" : diff === -1 ? "أمس" : ""; }
    return { rel:rel, date:DAY[d.getUTCDay()] + " " + p[2] + " " + MON[p[1] - 1], short:p[2] + " " + MON[p[1] - 1] };
  }
  R.dayParts = dparts;
  R.dayLabel = function(ymd, today){ var x = dparts(ymd, today); return x.rel ? x.rel + "، " + x.date : x.date; };
  R.dayNav = function(ymd, today){ var x = dparts(ymd, today); return x.rel ? x.rel + "<small>" + esc(x.date) + "</small>" : esc(x.date); };
  R.isLive = function(m){ return m.status === "live" || m.status === "ht"; };
  R.minute = function(m){ return m.status === "ht" ? "استراحة" : m.minute ? '<bdi dir="ltr">' + esc(m.minute) + "'</bdi>" : "مباشر"; };
  // a live match is "hot" (feature 35) from the 75th minute while it is level or one goal apart
  R.hot = function(m){ var mn = parseInt(m.minute, 10) || 0; return m.status === "live" && mn >= 75 && m.score && Math.abs(m.score.home - m.score.away) <= 1; };
  // «وش فاتني؟» (34): the match so far in a few plain lines, from the events
  R.catchup = function(md){
    if (!(R.isLive(md) || md.status === "finished") || !md.score) return "";
    var H = md.home.name_ar || md.home.name, A = md.away.name_ar || md.away.name, s = md.score, lines = [], ev = md.events || [];
    var lead = s.home > s.away ? H + " متقدم " + s.home + " - " + s.away : s.away > s.home ? A + " متقدم " + s.away + " - " + s.home : "التعادل " + s.home + " - " + s.away;
    if (md.status === "finished") lead = s.home > s.away ? H + " فاز " + s.home + " - " + s.away : s.away > s.home ? A + " فاز " + s.away + " - " + s.home : "انتهت بالتعادل " + s.home + " - " + s.away;
    lines.push(lead + (R.isLive(md) && md.minute ? " (الدقيقة " + String(md.minute).replace(/'/g, "") + ")" : "") + ".");
    var goals = ev.filter(function(e){ return /goal/.test(e.type) && e.player; });
    if (goals.length) lines.push("الأهداف: " + goals.map(function(e){ return e.player.name + " " + e.minute + "'" + (e.type === "penalty_goal" ? " من بلنتي" : e.type === "own_goal" ? " في مرماه" : ""); }).join("، ") + ".");
    var reds = ev.filter(function(e){ return (e.type === "red" || e.type === "second_yellow") && e.player; });
    if (reds.length) lines.push("طرد: " + reds.map(function(e){ return e.player.name + " (" + (e.team === "home" ? H : A) + ") " + e.minute + "'"; }).join("، ") + ".");
    var miss = ev.filter(function(e){ return e.type === "missed_penalty" && e.player; });
    if (miss.length) lines.push("بلنتي ضايع: " + miss.map(function(e){ return e.player.name + " " + e.minute + "'"; }).join("، ") + ".");
    if (md.halftime_score && md.status === "finished"){ var h = md.halftime_score; if ((h.home > h.away && s.home < s.away) || (h.away > h.home && s.away < s.home)) lines.push("ريمونتادا: كان متأخر بين الشوطين وقلبها."); }
    return '<div class="catchup"><b>' + (R.isLive(md) ? "وش فاتك" : "الخلاصة") + "</b>" + lines.map(function(l){ return "<p>" + esc(l) + "</p>"; }).join("") + "</div>";
  };
  R.statusText = function(m){
    switch (m.status){
      case "live": case "ht": return R.minute(m);
      case "finished": return m.status_detail === "AET" ? "بعد الإضافي" : m.status_detail === "Pen" ? "بالترجيح" : "انتهت";
      case "postponed": return "تأجلت";
      case "cancelled": return "ألغيت";
      case "abandoned": return "توقفت";
      case "awarded": return "قرار إداري";
      default: return m.time_tbd ? "الوقت ما تحدد" : R.hhmm(m.kickoff_uae);
    }
  };
  // score always "home - away" inside RTL text: home's number sits on the right, under the home team
  function sc(s){ return s.home + " - " + s.away; }
  R.chip = function(m, o){
    o = o || {}; var live = R.isLive(m);
    if (live) return '<span class="chip live' + (R.hot(m) ? " hot" : "") + '"><small>' + R.minute(m) + (R.hot(m) ? " حامي" : "") + "</small>" + (m.score ? sc(m.score) : "0 - 0") + "</span>";
    if (m.status === "finished" && m.score) return '<span class="chip">' + sc(m.score) + (m.penalties ? "<small>ترجيح " + sc(m.penalties) + "</small>" : m.status_detail === "AET" ? "<small>بعد الإضافي</small>" : "") + "</span>";
    if (m.status === "scheduled" || !m.status) return '<span class="chip up">' + (m.time_tbd ? "—" : R.hhmm(m.kickoff_uae)) + (o.date ? "<small>" + esc(dparts(R.ymd(m.kickoff_uae)).short) + "</small>" : "") + "</span>";
    return '<span class="chip off">' + R.statusText(m) + "</span>";
  };
  R.matchRow = function(m, o){
    o = o || {}; var fin = m.status === "finished", s = m.score, hw = fin && s && s.home > s.away, aw = fin && s && s.away > s.home;
    var mine = o.mine && (m.home.id === o.mine || m.away.id === o.mine);
    return '<a class="m' + (R.isLive(m) ? " live" : "") + (mine ? " mine" : "") + '" href="/m/' + m.id + '/" data-mid="' + m.id + '">' +
      '<span class="t h' + (hw ? " win" : aw ? " lose" : "") + '">' + R.logo(m.home) + "<span>" + R.tname(m.home) + "</span></span>" + R.chip(m, o) +
      '<span class="t a' + (aw ? " win" : hw ? " lose" : "") + '">' + R.logo(m.away) + "<span>" + R.tname(m.away) + "</span></span></a>";
  };
  R.compOrder = function(index){ var o = {}; (index.competitions || []).forEach(function(c, i){ o[c.id] = i; }); return o; };
  R.compName = function(index, id){ var c = (index.competitions || []).filter(function(c){ return c.id === id; })[0]; return c ? c.name_ar : ""; };
  R.compKey = function(index, id){ var c = (index.competitions || []).filter(function(c){ return c.id === id; })[0]; return c ? c.key : null; };
  R.stageAr = function(s){ if (!s) return ""; var g = /Gr(?:ou)?p\.?\s*([A-Z0-9]+)/i.exec(s); return g ? "المجموعة " + g[1] : s; };
  // matches grouped by competition, my team's competition first, then index order (UAE first)
  R.dayList = function(matches, index, o){
    o = o || {}; var ord = R.compOrder(index), g = {};
    (matches || []).forEach(function(m){ (g[m.comp] = g[m.comp] || []).push(m); });
    var ids = Object.keys(g).map(Number).sort(function(a, b){ return (ord[a] == null ? 999 : ord[a]) - (ord[b] == null ? 999 : ord[b]); });
    if (o.mine){ var has = function(id){ return g[id].some(function(m){ return m.home.id === o.mine || m.away.id === o.mine; }) ? 1 : 0; }; ids.sort(function(a, b){ return has(b) - has(a); }); }
    if (!ids.length) return '<p class="empty">' + (o.empty || "ما في مباريات.") + "</p>";
    return ids.map(function(id){
      var ms = g[id].sort(function(a, b){ return (a.kickoff_utc || "").localeCompare(b.kickoff_utc || ""); }), key = R.compKey(index, id), name = R.compName(index, id) || ms[0].comp_name_ar || "";
      var live = ms.filter(R.isLive).length, grp = ms[0].stage && /Gr(ou)?p/i.test(ms[0].stage) ? R.stageAr(ms[0].stage) : "";
      return '<section class="comp-block"><div class="comp-head">' + (key ? '<a href="/c/' + key + '/">' + esc(name) + "</a>" : esc(name)) + (grp ? '<span class="grp">' + esc(grp) + "</span>" : "") + (live ? '<span class="lv"><i class="cardflip"></i>' + live + " مباشر</span>" : "") + "</div>" +
        ms.map(function(m){ return R.matchRow(m, o); }).join("") + "</section>";
    }).join("");
  };

  // standings
  R.form = function(f){ return '<span class="form" aria-label="آخر النتايج">' + (f || []).slice(-5).map(function(x){ return '<i class="' + esc(x) + '">' + ({W:"ف",D:"ت",L:"خ"}[x] || "") + "</i>"; }).join("") + "</span>"; };
  var ZONE_AR = { "tr_afcchampionsleague":"دوري أبطال آسيا للنخبة", "tr_afcchampionsleaguequal":"ملحق أبطال آسيا للنخبة", "relegation":"الهبوط", "tr_afccup":"دوري أبطال آسيا 2", "championsleague":"دوري أبطال أوروبا", "europaleague":"الدوري الأوروبي", "promotion":"الصعود", "playoff":"الملحق" };
  function ink(c){ var h = String(c).replace("#", ""); if (h.length === 3) h = h.replace(/./g, "$&$&"); var n = parseInt(h, 16); if (isNaN(n)) return "#0E1512"; var l = (0.299 * (n >> 16 & 255) + 0.587 * (n >> 8 & 255) + 0.114 * (n & 255)) / 255; return l > 0.55 ? "#0E1512" : "#F6F7F2"; }
  function zoneName(z){ if (!z) return ""; var k = z.key || ""; if (/AFC Cup|Champions League Two|ACL ?2/i.test(z.label || "")) return "دوري أبطال آسيا 2"; for (var p in ZONE_AR) if (k.indexOf(p) >= 0 && (p !== "tr_afcchampionsleague" || k === p)) return ZONE_AR[p]; if (/relegat/i.test(z.label || k)) return "الهبوط"; if (/qualif|next round|knockout|playoff/i.test(z.label || "")) return "التأهل"; return z.label || ""; }
  R.standings = function(st, o){
    o = o || {}; if (!st || !st.groups || !st.groups.length) return '<p class="empty">ما في ترتيب لهالبطولة.</p>';
    return st.groups.map(function(g){
      var zones = {}; g.rows.forEach(function(r){ if (r.zone && r.zone.color) zones[r.zone.color] = zoneName(r.zone); });
      return (g.name ? "<h3>" + esc(g.name_ar || R.stageAr(g.name)) + "</h3>" : "") + '<div class="tblwrap"><table class="st"><thead><tr><th>#</th><th style="text-align:start">الفريق</th><th>لعب</th><th class="hx">فاز</th><th class="hx">تعادل</th><th class="hx">خسر</th><th class="hx">له - عليه</th><th>الفرق</th><th>نقاط</th><th class="hx">آخر 5</th></tr></thead><tbody>' +
        g.rows.map(function(r){ var z = r.zone && r.zone.color; return '<tr class="' + (o.mine === r.team.id ? "mine " : "") + (r.live ? "live" : "") + '" data-tid="' + r.team.id + '"><td class="rk"><span' + (z ? ' style="background:' + esc(z) + ";color:" + ink(z) + '"' : "") + ">" + r.rank + '</span></td><td class="tm"><a href="/t/' + r.team.id + '/">' + R.logo(r.team, "sm") + R.tname(r.team) + "</a></td><td>" + r.played + '</td><td class="hx">' + r.won + '</td><td class="hx">' + r.drawn + '</td><td class="hx">' + r.lost + '</td><td class="hx">' + r.gf + " - " + r.ga + '</td><td><bdi dir="ltr">' + (r.gd > 0 ? "+" : "") + r.gd + '</bdi></td><td class="pts">' + r.pts + '</td><td class="hx">' + R.form(r.form) + "</td></tr>"; }).join("") +
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
    return '<ol class="lead">' + l.slice(0, n || 20).map(function(p){ return '<li><span class="num muted">' + p.rank + '</span><span class="who">' + R.logo(p.team, "sm") + (p.player.id ? '<a class="lat" href="/p/' + p.player.id + '/">' + esc(p.player.name) + "</a>" : '<span class="lat">' + esc(p.player.name) + "</span>") + ' <span class="muted small">' + R.tname(p.team) + "</span></span><b>" + p.value + "</b></li>"; }).join("") + "</ol>";
  };
  // fixtures by round; opens on the next unplayed round
  R.rounds = function(fx){
    var r = {}, order = []; (fx.matches || []).forEach(function(m){ var k = m.round || m.stage || "—"; if (!r[k]){ r[k] = []; order.push(k); } r[k].push(m); });
    order.sort(function(a, b){ var x = parseFloat(a), y = parseFloat(b); if (!isNaN(x) && !isNaN(y)) return x - y; return (r[a][0].kickoff_utc || "").localeCompare(r[b][0].kickoff_utc || ""); });
    return { order:order, by:r };
  };
  R.roundLabel = function(k){ return isNaN(parseFloat(k)) ? esc(R.stageAr(k)) : "الجولة " + esc(k); };
  R.roundList = function(ms, o){ return ms.slice().sort(function(a, b){ return (a.kickoff_utc || "").localeCompare(b.kickoff_utc || ""); }).map(function(m){ return R.matchRow(m, { date:true, mine:o && o.mine }); }).join(""); };

  // ---- match page
  var EV = { penalty_goal:"بلنتي", own_goal:"في مرماه", missed_penalty:"بلنتي ضايع", yellow:"إنذار", red:"طرد", second_yellow:"إنذار ثاني وطرد", var:"الفار" };
  function evIcon(t){ if (t === "yellow") return '<i class="ico yellow"></i>'; if (t === "red" || t === "second_yellow") return '<i class="ico red"></i>'; if (/goal/.test(t)) return '<i class="ico goal"></i>'; if (t === "sub") return '<i class="ico sub"></i>'; if (t === "missed_penalty") return '<i class="ico miss"></i>'; return '<i class="ico sub"></i>'; }
  R.events = function(md){
    var ev = md.events || []; if (!ev.length) return '<p class="empty">' + (md.status === "scheduled" ? "المباراة ما بدت." : "ما في أحداث مسجّلة.") + "</p>";
    return '<ul class="ev">' + ev.map(function(e){
      if (e.type === "half"){ var hl = { HT:"نهاية الشوط الأول", FT:"نهاية المباراة", AET:"نهاية الوقت الإضافي", EHT:"نهاية الشوط الإضافي الأول", Pen:"ركلات الترجيح" }[e.detail] || esc(e.detail); return '<li class="div">' + hl + (e.score ? ' <span class="num">' + sc(e.score) + "</span>" : "") + "</li>"; }
      if (e.type === "added_time") return '<li class="div">+' + esc(e.detail) + " دقايق وقت بدل ضايع</li>";
      var who = e.player ? '<span class="lat">' + esc(e.player.name) + "</span>" : "";
      var extra = e.type === "sub" && e.player_out ? '<span class="sub">طلع <span class="lat">' + esc(e.player_out.name) + "</span></span>" : e.assist ? '<span class="sub">صناعة <span class="lat">' + esc(e.assist.name) + "</span></span>" : "";
      var body = '<span class="who">' + evIcon(e.type) + who + (/goal/.test(e.type) && e.score ? '<span class="gs">' + sc(e.score) + "</span>" : "") + (EV[e.type] ? '<span class="kind">' + EV[e.type] + "</span>" : "") + "</span>" + extra;
      var mn = '<bdi dir="ltr">' + esc(e.minute) + (e.added ? "+" + esc(e.added) : "") + "'</bdi>";
      return e.team === "home" ? '<li><span class="h">' + body + '</span><span class="mn">' + mn + "</span><span></span></li>" : '<li><span></span><span class="mn">' + mn + "</span><span>" + body + "</span></li>";
    }).join("") + "</ul>";
  };
  // the match line: minute 0 on the RIGHT, time runs left (forward in RTL). Physical `right` on purpose.
  R.timeline = function(md){
    var ev = (md.events || []).filter(function(e){ return /goal|yellow|red/.test(e.type) && e.team; });
    var end = ev.some(function(e){ return e.minute > 90; }) || /AET|Pen/.test(md.status_detail || "") ? 120 : 90;
    var now = md.status === "finished" ? end : R.isLive(md) ? Math.min(end, parseInt(md.minute, 10) || (md.status === "ht" ? 45 : 0)) : 0;
    if (!ev.length && !now) return "";
    var pct = function(m){ return Math.min(100, Math.max(0, m / end * 100)).toFixed(2); };
    return '<div class="timeline"><div class="tl" aria-hidden="true"><i class="axis"></i><i class="played" style="inset-inline-start:0;inline-size:' + pct(now) + '%"></i><i class="ht" style="right:' + pct(45) + '%"></i>' + (end > 90 ? '<i class="ht" style="right:' + pct(90) + '%"></i>' : "") +
      ev.map(function(e){ var k = /goal/.test(e.type) ? "goal" : e.type === "yellow" ? "yellow" : "red"; return '<i class="ev ' + k + " " + (e.team === "home" ? "h" : "a") + '" style="right:' + pct(e.minute + (e.added ? Math.min(e.added, 5) / 10 : 0)) + '%" title="' + esc(e.minute) + "'" + '"></i>'; }).join("") +
      '</div><div class="tl-lbl"><span>0</span><span>45</span><span>' + end + "</span></div></div>";
  };
  function rt(r){ if (r == null) return ""; var c = r >= 7.5 ? "hi" : r >= 6.5 ? "mid" : "lo"; return '<span class="rt ' + c + '">' + Number(r).toFixed(1) + "</span>"; }
  function players(list){ return "<ul>" + (list || []).map(function(p){ return '<li><span class="no">' + esc(p.number || "") + '</span><span class="lat">' + esc(p.name) + "</span>" + (p.captain ? ' <span class="muted small">كابتن</span>' : "") + (p.country && p.country !== "UAE" ? ' <span class="flag">' + esc(p.country) + "</span>" : "") + rt(p.rating) + "</li>"; }).join("") + "</ul>"; }
  function surname(n){ var p = String(n || "").trim().split(/\s+/); return p.length > 1 ? p.slice(1).join(" ") : p[0]; }
  // FotMob position_id: leading digits = depth row (1 keeper .. 11 striker), last digit = lateral slot (1..9).
  function pitchSide(s, away){
    return (s.starters || []).map(function(p){
      var id = p.position_id; if (!id) return "";
      var row = Math.floor(id / 10), lat = id % 10, x = row === 1 ? 50 : away ? lat * 10 : 100 - lat * 10;   // row 1 = keeper, always central
      var y = away ? 7 + (row - 1) / 10 * 38 : 93 - (row - 1) / 10 * 38;
      return '<div class="pl' + (away ? " away" : "") + '" style="left:' + x + "%;top:" + y + '%"><b>' + esc(p.number || "") + "</b><span class=\"lat\">" + esc(surname(p.name)) + "</span>" + (p.rating != null ? rt(p.rating) : "") + "</div>";
    }).join("");
  }
  R.lineups = function(md){
    var L = md.lineups; if (!L || !L.home) return '<p class="empty">التشكيلة تنزل قبل المباراة بساعة تقريباً.</p>';
    var ok = [L.home, L.away].every(function(s){ return s && s.starters && s.starters.length === 11 && s.starters.every(function(p){ return p.position_id >= 11; }); });
    function side(s, t){ if (!s) return ""; return '<div><h3><span>' + R.logo(t, "sm") + " " + R.tname(t) + '</span><span class="num muted">' + esc(s.formation || "") + "</span></h3>" + players(s.starters) + (s.subs && s.subs.length ? "<h3>الاحتياط</h3>" + players(s.subs) : "") + (s.coach ? '<p class="muted small">المدرب <span class="lat">' + esc(s.coach.name) + "</span></p>" : "") + (s.unavailable && s.unavailable.length ? '<p class="muted small">غايبين: ' + s.unavailable.map(function(u){ return '<span class="lat">' + esc(u.name) + "</span> (" + (u.type === "injury" ? "إصابة" : u.type === "suspension" ? "إيقاف" : esc(u.type)) + ")"; }).join("، ") + "</p>" : "") + "</div>"; }
    return (L.type === "lastStarting11" ? '<p class="note">هذي آخر تشكيلة لعبوا فيها، مب التشكيلة الرسمية للمباراة.</p>' : "") +
      (ok ? '<div class="pitch"><i class="half"></i><i class="circle"></i><i class="box t"></i><i class="box b"></i><span class="side t">' + R.tname(md.away) + " " + esc(L.away.formation || "") + '</span><span class="side b">' + R.tname(md.home) + " " + esc(L.home.formation || "") + "</span>" + pitchSide(L.home, false) + pitchSide(L.away, true) + "</div>" : "") +
      '<div class="lu">' + side(L.home, md.home) + side(L.away, md.away) + "</div>";
  };
  var STAT_AR = { BallPossesion:"الاستحواذ %", expected_goals:"الأهداف المتوقعة", total_shots:"التسديدات", ShotsOnTarget:"على المرمى", ShotsOffTarget:"برا المرمى", big_chance:"فرص محققة", big_chance_missed_title:"فرص ضايعة", corners:"الركنيات", fouls:"الأخطاء", Offsides:"التسلل", yellow_cards:"الإنذارات", red_cards:"الطرد", passes:"التمريرات", accurate_passes:"تمريرات صحيحة", keeper_saves:"تصديات الحارس", touches_opp_box:"لمسات في منطقة الخصم", blocked_shots:"تسديدات مصدودة", shots_inside_box:"من داخل المنطقة", shots_outside_box:"من برا المنطقة", shots_woodwork:"القائم والعارضة", interceptions:"قطع الكورة", clearances:"إبعاد", "matchstats.headers.tackles":"الافتكاك", duel_won:"التحامات ناجحة", aerials_won:"كرات هوائية", dribbles_succeeded:"مراوغات ناجحة", accurate_crosses:"عرضيات صحيحة", long_balls_accurate:"كرات طويلة صحيحة", player_throws:"رميات تماس", ground_duels_won:"التحامات أرضية" };
  R.stats = function(md){
    if (!(md.stats || [])[0]) return '<p class="empty">الإحصائيات تنزل مع بداية المباراة.</p>';
    var items = []; (md.stats || []).forEach(function(s){ s.items.forEach(function(i){ if (STAT_AR[i.key] && !items.some(function(x){ return x.key === i.key; })) items.push(i); }); });
    // bars: home share from the right (RTL), away share to the left
    return items.map(function(i){ var h = parseFloat(i.home) || 0, a = parseFloat(i.away) || 0, t = h + a || 1; return '<div class="stat"><span class="l">' + STAT_AR[i.key] + '</span><span class="v">' + esc(i.home) + '</span><span class="bar2"><i style="inline-size:' + (h / t * 100).toFixed(1) + '%"></i><i style="inline-size:' + (a / t * 100).toFixed(1) + '%"></i></span><span class="v">' + esc(i.away) + "</span></div>"; }).join("");
  };
  R.h2h = function(md){
    var h = md.h2h; if (!h || !h.summary) return '<p class="empty">ما في مواجهات سابقة مسجّلة.</p>';
    var s = h.summary, k = [md.home.id, md.away.id].sort(function(a, b){ return a - b; }).join("-");
    return ((R.H2HK || (root && root.H2HK) || {})[k] ? '<p><a class="btn" href="/h2h/' + k + '/">كل مواجهاتهم</a></p>' : "") + '<div class="h2hsum"><div><b>' + s.home_wins + "</b>فوز " + R.tname(md.home) + "</div><div><b>" + s.draws + "</b>تعادل</div><div><b>" + s.away_wins + "</b>فوز " + R.tname(md.away) + "</div></div>" +
      (h.matches || []).slice(0, 10).map(function(m){ m.status = m.status || "finished"; return R.matchRow(m, {}); }).join("");
  };
  function band(t){ return '<span class="band" aria-hidden="true"><i style="background:' + R.col(t.id, 0) + '"></i><i style="background:' + R.col(t.id, 1) + '"></i></span>'; }
  R.matchHead = function(md){
    var live = R.isLive(md), st = live ? '<i class="cardflip"></i>' + R.minute(md) : md.status === "scheduled" ? esc(R.dayLabel(R.ymd(md.kickoff_uae))) : R.statusText(md) + (md.halftime_score && md.status === "finished" ? '، الشوط الأول <span class="num">' + sc(md.halftime_score) + "</span>" : "");
    return '<div class="board' + (live ? " live" : "") + '">' + band(md.home) + '<a class="tm" href="/t/' + md.home.id + '/">' + R.logo(md.home, "lg") + R.tname(md.home) + "</a>" +
      '<div class="sc"><span class="dg">' + (md.score ? sc(md.score) : R.hhmm(md.kickoff_uae) || "—") + "</span>" + (md.penalties ? '<span class="pens">ترجيح <span class="num">' + sc(md.penalties) + "</span></span>" : "") + '<span class="st">' + st + "</span></div>" +
      '<a class="tm" href="/t/' + md.away.id + '/">' + R.logo(md.away, "lg") + R.tname(md.away) + "</a>" + band(md.away) + "</div>" + R.timeline(md);
  };
  R.matchFacts = function(md, index){
    var key = R.compKey(index, md.comp), f = [];
    f.push(["البطولة", key ? '<a href="/c/' + key + '/">' + esc(md.comp_name_ar || R.compName(index, md.comp)) + "</a>" : esc(md.comp_name_ar || "")]);
    if (md.round && !isNaN(parseFloat(md.round))) f.push(["الجولة", '<span class="num">' + esc(md.round) + "</span>"]);
    else if (md.stage && /Gr(ou)?p/i.test(md.stage)) f.push(["الدور", esc(R.stageAr(md.stage))]);
    f.push(["الموعد بتوقيت الإمارات", esc(R.dayLabel(R.ymd(md.kickoff_uae))) + ' <span class="num">' + R.hhmm(md.kickoff_uae) + "</span>"]);
    if (md.venue) f.push(["الملعب", esc(md.venue.name_ar || md.venue.name_en || md.venue.name)]);
    if (md.referee) f.push(["الحكم", '<span class="lat">' + esc(md.referee.name || md.referee) + "</span>"]);
    if (md.attendance) f.push(["الحضور", '<span class="num">' + Number(md.attendance).toLocaleString("en-US") + "</span>"]);
    var tiles = "";
    if (md.prayer && md.prayer.clashes && md.prayer.clashes.length){
      var P = { fajr:"الفجر", dhuhr:"الظهر", asr:"العصر", maghrib:"المغرب", isha:"العشاء" }, S = { halftime:"يصادف الاستراحة", first_half:"في الشوط الأول", second_half:"في الشوط الثاني", before:"قبل البداية" };
      md.prayer.clashes.forEach(function(c){ tiles += '<div class="tile pray"><span class="ic">🕌</span><div><b>أذان ' + (P[c.prayer] || esc(c.prayer)) + ' <span class="num">' + esc(c.at_uae) + "</span></b><span>" + (S[c.segment] || "") + (c.segment !== "halftime" && c.minute_of_play != null ? "، حوالي الدقيقة " + c.minute_of_play : "") + (md.prayer.estimated_window ? "، تقريبي" : "") + "</span></div></div>"; });
    }
    var w = md.weather;
    if (w && w.available){ var hot = w.heat_category === "danger" || w.heat_category === "extreme"; tiles += '<div class="tile' + (hot ? " hot" : "") + '"><span class="ic">🌡</span><div><b>وقت ضربة البداية <span class="num">' + Math.round(w.temp_c) + "°</span></b><span>الرطوبة " + Math.round(w.humidity) + "%" + (w.heat_index_c ? "، الإحساس " + Math.round(w.heat_index_c) + "°" : "") + (hot ? "، حر شديد: خذ ماي وايد لو بتحضر" : "") + "</span></div></div>"; }
    return '<dl class="facts">' + f.map(function(x){ return "<div><dt>" + x[0] + "</dt><dd>" + x[1] + "</dd></div>"; }).join("") + "</dl>" + (tiles ? '<div class="tiles">' + tiles + "</div>" : "");
  };

  // ---- team page
  R.teamStrip = function(t){ var h = ""; for (var i = 0; i < 24; i++) h += '<i style="background:' + R.col(t.id, (i % 3 === 1) ? 1 : 0) + '"></i>'; return '<div class="strip" aria-hidden="true">' + h + "</div>"; };
  var GROUP_AR = { keepers:"حراس المرمى", defenders:"الدفاع", midfielders:"الوسط", attackers:"الهجوم", coach:"الجهاز الفني" };
  R.squad = function(t){
    if (!t.squad || !t.squad.length) return '<p class="empty">ما في قائمة لاعبين.</p>';
    return t.squad.filter(function(g){ return g.group !== "coach"; }).map(function(g){ return "<h3>" + (GROUP_AR[g.group] || esc(g.group)) + '</h3><div class="squad">' + g.players.map(function(p){ return '<div><span class="no">' + esc(p.number || "") + '</span><span class="lat">' + esc(p.name) + "</span>" + (p.country && p.country !== t.country ? ' <span class="flag">' + esc(p.country) + "</span>" : "") + (p.club && t.national ? ' <span class="muted small">' + esc(p.club) + "</span>" : "") + (p.injury ? ' <span class="muted small">مصاب</span>' : "") + '<span class="x">' + (p.goals ? p.goals + " هدف" : "") + (p.goals && p.assists ? "، " : "") + (p.assists ? p.assists + " صناعة" : "") + "</span></div>"; }).join("") + "</div>"; }).join("");
  };
  R.teamFixtures = function(t){
    var fx = (t.fixtures || []).slice().sort(function(a, b){ return (a.kickoff_utc || "").localeCompare(b.kickoff_utc || ""); });
    var now = Date.now(), done = function(m){ return m.status === "finished" || m.status === "awarded" || m.status === "abandoned" || (m.status !== "live" && m.status !== "ht" && Date.parse(m.kickoff_utc) < now - 3 * 3600e3); };
    var past = fx.filter(function(m){ return done(m) && m.status !== "cancelled" && m.status !== "postponed"; }).reverse(), next = fx.filter(function(m){ return !done(m) && m.status !== "cancelled"; });
    return { past:past, next:next };
  };
  // the featured match for the stand: live first, then UAE national team / UAE club comps, then the next kickoff
  R.featured = function(ms){
    ms = (ms || []).slice(); if (!ms.length) return null;
    var score = function(m){ var s = 0; if (R.isLive(m)) s += 100; if (m.home.id === 5789 || m.away.id === 5789) s += 50; if (UAE_COMPS.indexOf(m.comp) >= 0) s += 30; if (m.status === "scheduled") s += 10; return s; };
    ms.sort(function(a, b){ return score(b) - score(a) || (a.kickoff_utc || "").localeCompare(b.kickoff_utc || ""); });
    return ms[0];
  };
  R.standCap = function(m){
    if (!m) return "";
    var live = R.isLive(m), mid = live ? '<span class="dg">' + (m.score ? sc(m.score) : "0 - 0") + "</span>" + R.minute(m) : m.score ? '<span class="dg">' + sc(m.score) + "</span>" + R.statusText(m) : '<span class="dg">' + R.hhmm(m.kickoff_uae) + "</span>" + esc(dparts(R.ymd(m.kickoff_uae)).date);
    return '<a class="h" href="/m/' + m.id + '/">' + R.logo(m.home) + "<span>" + R.tname(m.home) + '</span></a><a class="mid' + (live ? " live" : "") + '" href="/m/' + m.id + '/">' + mid + '</a><a class="a" href="/m/' + m.id + '/"><span>' + R.tname(m.away) + "</span>" + R.logo(m.away) + "</a>";
  };
  R.UAE_COMPS = UAE_COMPS;
  if (typeof module !== "undefined" && module.exports) module.exports = R; else root.TR = R;
})(this);
