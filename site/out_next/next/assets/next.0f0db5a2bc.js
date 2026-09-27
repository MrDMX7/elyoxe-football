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
  // times: the build prints UAE time (kickoff_uae is "+04:00"); in the browser R.TZ is the visitor's country time zone (203)
  // and every <time class="tt|td"> is rewritten by R.localize(). kickoff_uae strings parse to the right instant anywhere.
  R.TZ = null;
  var fmtCache = {};
  function inTz(iso, opt){ var k = R.TZ + JSON.stringify(opt); if (!fmtCache[k]) fmtCache[k] = new Intl.DateTimeFormat("en-CA", Object.assign({ timeZone:R.TZ, hourCycle:"h23" }, opt)); return fmtCache[k].format(new Date(iso)); }
  R.hhmm = function(iso){ if (!iso) return ""; if (R.TZ){ try { return inTz(iso, { hour:"2-digit", minute:"2-digit" }).replace(/^24/, "00"); } catch (e){} } return iso.slice(11, 16); };
  R.ymd = function(iso){ if (!iso) return ""; if (R.TZ && iso.length > 10){ try { return inTz(iso, { year:"numeric", month:"2-digit", day:"2-digit" }); } catch (e){} } return iso.slice(0, 10); };
  R.tt = function(iso){ return iso ? '<time class="tt" data-u="' + esc(iso) + '">' + R.hhmm(iso) + "</time>" : ""; };
  R.td = function(iso, full){ if (!iso) return ""; var p = dparts(R.ymd(iso)); return '<time class="td" data-u="' + esc(iso) + '"' + (full ? ' data-f="1"' : "") + ">" + esc(full ? p.date : p.short) + "</time>"; };
  R.localize = function(root){ if (!R.TZ) return; (root || document).querySelectorAll("time.tt[data-u]").forEach(function(t){ t.textContent = R.hhmm(t.dataset.u); }); (root || document).querySelectorAll("time.td[data-u]").forEach(function(t){ var p = dparts(R.ymd(t.dataset.u)); t.textContent = t.dataset.f ? p.date : p.short; }); };
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
  // «شو فاتني؟» (34): the match so far in a few plain lines, from the events
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
    return '<div class="catchup"><b>' + (R.isLive(md) ? "شو فاتك" : "الخلاصة") + "</b>" + lines.map(function(l){ return "<p>" + esc(l) + "</p>"; }).join("") + "</div>";
  };
  R.statusText = function(m){
    switch (m.status){
      case "live": case "ht": return R.minute(m);
      case "finished": return m.status_detail === "AET" ? "بعد الإضافي" : m.status_detail === "Pen" ? "بالترجيح" : "انتهت";
      case "postponed": return "تأجلت";
      case "cancelled": return "ألغيت";
      case "abandoned": return "توقفت";
      case "awarded": return "قرار إداري";
      default: return m.time_tbd ? "الوقت ما تحدد" : R.tt(m.kickoff_uae);
    }
  };
  // score always "home - away" inside RTL text: home's number sits on the right, under the home team
  function sc(s){ return s.home + " - " + s.away; }
  R.chip = function(m, o){
    o = o || {}; var live = R.isLive(m);
    if (live) return '<span class="chip live' + (R.hot(m) ? " hot" : "") + '"><small>' + R.minute(m) + (R.hot(m) ? " حامي" : "") + "</small>" + (m.score ? sc(m.score) : "0 - 0") + "</span>";
    if (m.status === "finished" && m.score) return '<span class="chip">' + sc(m.score) + (m.penalties ? "<small>ترجيح " + sc(m.penalties) + "</small>" : m.status_detail === "AET" ? "<small>بعد الإضافي</small>" : "") + "</span>";
    if (m.status === "scheduled" || !m.status) return '<span class="chip up">' + (m.time_tbd ? "—" : R.tt(m.kickoff_uae)) + (o.date ? "<small>" + R.td(m.kickoff_uae) + "</small>" : "") + "</span>";
    return '<span class="chip off">' + R.statusText(m) + "</span>";
  };
  R.matchRow = function(m, o){
    o = o || {}; var fin = m.status === "finished", s = m.score, hw = fin && s && s.home > s.away, aw = fin && s && s.away > s.home;
    var mine = o.mine && (m.home.id === o.mine || m.away.id === o.mine);
    return '<a class="m' + (R.isLive(m) ? " live" : "") + (mine ? " mine" : "") + '" href="/m/' + m.id + '/" data-mid="' + m.id + '">' +
      '<span class="t h' + (hw ? " win" : aw ? " lose" : "") + '">' + R.logo(m.home) + "<span>" + R.tname(m.home) + "</span></span>" + R.chip(m, o) +
      '<span class="t a' + (aw ? " win" : hw ? " lose" : "") + '">' + R.logo(m.away) + "<span>" + R.tname(m.away) + "</span></span></a>";
  };
  // 281: TV guide for one country (guide/{iso2}.json): the next 3 days, each match with its broadcasters there
  R.guide = function(g){
    if (!g || !g.matches || !g.matches.length) return '<p class="empty">ما لقينا مباريات منقولة في الأيام الياية.</p>';
    var days = {}, order = []; g.matches.slice().sort(function(a, b){ return a.kickoff_utc.localeCompare(b.kickoff_utc); }).forEach(function(m){ var d = R.ymd(R.TZ ? m.kickoff_utc : (m.kickoff_uae || m.kickoff_utc)); if (!days[d]){ days[d] = []; order.push(d); } days[d].push(m); });
    return order.map(function(d){ return "<h3>" + esc(R.dayLabel(d)) + "</h3>" + days[d].map(function(m){ var mm = { id:m.match, comp:m.comp, kickoff_utc:m.kickoff_utc, kickoff_uae:m.kickoff_uae, status:m.status, score:m.score, home:m.home, away:m.away };
      return '<div class="gm">' + R.matchRow(mm, {}) + '<p class="bc"><span class="muted small">' + esc(m.comp_name_ar || "") + "</span> " + (m.broadcasters || []).map(function(b){ return "<b>" + esc(b.name_ar || b.name_en) + "</b>" + (b.free ? ' <span class="free">مجاني</span>' : ""); }).join("، ") + "</p></div>"; }).join(""); }).join("");
  };
  R.compOrder = function(index){ var o = {}; (index.competitions || []).forEach(function(c, i){ o[c.id] = i; }); return o; };
  R.compName = function(index, id){ var c = (index.competitions || []).filter(function(c){ return c.id === id; })[0]; return c ? c.name_ar : ""; };
  R.compKey = function(index, id){ var c = (index.competitions || []).filter(function(c){ return c.id === id; })[0]; return c ? c.key : null; };
  R.stageAr = function(s){ if (!s) return ""; var g = /Gr(?:ou)?p\.?\s*([A-Z0-9]+)/i.exec(s); return g ? "المجموعة " + g[1] : s; };
  // the 22 Arab League countries (203, 199): time zone and name; "xx" = outside the Arab world (browser time zone)
  R.COUNTRIES = [["AE","الإمارات","Asia/Dubai"],["SA","السعودية","Asia/Riyadh"],["EG","مصر","Africa/Cairo"],["MA","المغرب","Africa/Casablanca"],["DZ","الجزائر","Africa/Algiers"],["TN","تونس","Africa/Tunis"],["IQ","العراق","Asia/Baghdad"],["JO","الأردن","Asia/Amman"],["KW","الكويت","Asia/Kuwait"],["QA","قطر","Asia/Qatar"],["BH","البحرين","Asia/Bahrain"],["OM","عُمان","Asia/Muscat"],["LB","لبنان","Asia/Beirut"],["SY","سوريا","Asia/Damascus"],["PS","فلسطين","Asia/Hebron"],["YE","اليمن","Asia/Aden"],["LY","ليبيا","Africa/Tripoli"],["SD","السودان","Africa/Khartoum"],["MR","موريتانيا","Africa/Nouakchott"],["SO","الصومال","Africa/Mogadishu"],["DJ","جيبوتي","Africa/Djibouti"],["KM","جزر القمر","Indian/Comoro"]];
  var KEYC = { "uae-":"AE", "saudi-":"SA", "qatar-":"QA", "egyptian-":"EG", "botola":"MA", "moroccan-":"MA", "algerian-":"DZ", "tunisian-":"TN", "iraqi-":"IQ", "oman":"OM", "kuwait":"KW", "bahrain":"BH", "jordan":"JO", "libya":"LY", "sudan":"SD", "lebanon":"LB" };
  R.compCountry = function(c){ if (!c) return null; if (c.country) return c.country.iso || c.country.iso2 || c.country; for (var k in KEYC) if ((c.key || "").indexOf(k) === 0) return KEYC[k]; return null; };
  // matches grouped by competition, my team's competition first, then index order (UAE first)
  R.dayList = function(matches, index, o){
    o = o || {}; var ord = R.compOrder(index), g = {};
    (matches || []).forEach(function(m){ (g[m.comp] = g[m.comp] || []).push(m); });
    var ids = Object.keys(g).map(Number).sort(function(a, b){ return (ord[a] == null ? 999 : ord[a]) - (ord[b] == null ? 999 : ord[b]); });
    if (o.country){ var cc = {}; (index.competitions || []).forEach(function(c){ cc[c.id] = R.compCountry(c); }); var natIds = o.natIds || []; var hc = function(id){ return cc[id] === o.country || g[id].some(function(m){ return natIds.indexOf(m.home.id) >= 0 || natIds.indexOf(m.away.id) >= 0; }) ? 1 : 0; }; ids.sort(function(a, b){ return hc(b) - hc(a); }); }
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
    }).join("") + '</ul><p class="src"><a href="/laws/">ليش ألغى الحكم هدف أو صفّر بلنتي؟ قانون الكورة بالإماراتي</a></p>';
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
    var live = R.isLive(md), st = live ? '<i class="cardflip"></i>' + R.minute(md) : md.status === "scheduled" ? R.td(md.kickoff_uae, true) : R.statusText(md) + (md.halftime_score && md.status === "finished" ? '، الشوط الأول <span class="num">' + sc(md.halftime_score) + "</span>" : "");
    return '<div class="board' + (live ? " live" : "") + '">' + band(md.home) + '<a class="tm" href="/t/' + md.home.id + '/">' + R.logo(md.home, "lg") + R.tname(md.home) + "</a>" +
      '<div class="sc"><span class="dg">' + (md.score ? sc(md.score) : R.tt(md.kickoff_uae) || "—") + "</span>" + (md.penalties ? '<span class="pens">ترجيح <span class="num">' + sc(md.penalties) + "</span></span>" : "") + '<span class="st">' + st + "</span></div>" +
      '<a class="tm" href="/t/' + md.away.id + '/">' + R.logo(md.away, "lg") + R.tname(md.away) + "</a>" + band(md.away) + "</div>" + R.timeline(md);
  };
  R.matchFacts = function(md, index){
    var key = R.compKey(index, md.comp), f = [];
    f.push(["البطولة", key ? '<a href="/c/' + key + '/">' + esc(md.comp_name_ar || R.compName(index, md.comp)) + "</a>" : esc(md.comp_name_ar || "")]);
    if (md.round && !isNaN(parseFloat(md.round))) f.push(["الجولة", '<span class="num">' + esc(md.round) + "</span>"]);
    else if (md.stage && /Gr(ou)?p/i.test(md.stage)) f.push(["الدور", esc(R.stageAr(md.stage))]);
    f.push(["الموعد بتوقيت بلدك", R.td(md.kickoff_uae, true) + ' <span class="num">' + R.tt(md.kickoff_uae) + "</span>"]);
    if (md.venue) f.push(["الملعب", esc(md.venue.name_ar || md.venue.name_en || md.venue.name)]);
    if (md.venue && md.venue.distance_km){ var EM = [["abu-dhabi","أبوظبي"],["dubai","دبي"],["sharjah","الشارقة"],["ajman","عجمان"],["umm-al-quwain","أم القيوين"],["ras-al-khaimah","رأس الخيمة"],["fujairah","الفجيرة"],["al-ain","العين"]];
      f.push(["المسافة من", '<span class="dist" data-km=\'' + esc(JSON.stringify(md.venue.distance_km)) + '\'><select class="emsel" aria-label="إمارتك">' + EM.map(function(e){ return '<option value="' + e[0] + '"' + (e[0] === "dubai" ? " selected" : "") + ">" + e[1] + "</option>"; }).join("") + '</select> <b class="num dk">' + Math.round(md.venue.distance_km.dubai) + '</b> كم <span class="muted small dt"></span></span>']); }
    if (md.referee) f.push(["الحكم", md.referee.id ? '<a class="lat" href="/r/' + md.referee.id + '/">' + esc(md.referee.name) + "</a>" : '<span class="lat">' + esc(md.referee.name || md.referee) + "</span>"]);
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
    var live = R.isLive(m), mid = live ? '<span class="dg">' + (m.score ? sc(m.score) : "0 - 0") + "</span>" + R.minute(m) : m.score ? '<span class="dg">' + sc(m.score) + "</span>" + R.statusText(m) : '<span class="dg">' + R.tt(m.kickoff_uae) + "</span>" + R.td(m.kickoff_uae, true);
    return '<a class="h" href="/m/' + m.id + '/">' + R.logo(m.home) + "<span>" + R.tname(m.home) + '</span></a><a class="mid' + (live ? " live" : "") + '" href="/m/' + m.id + '/">' + mid + '</a><a class="a" href="/m/' + m.id + '/"><span>' + R.tname(m.away) + "</span>" + R.logo(m.away) + "</a>";
  };
  R.UAE_COMPS = UAE_COMPS;
  if (typeof module !== "undefined" && module.exports) module.exports = R; else root.TR = R;
})(this);

;
/* تيفو v3 renderer layer (redesign/DESIGN-v3.md). Loaded after src/render.js on both sides (build_next.cjs requires it and
   the browser gets it after render.js). It never edits render.js: it wraps a few R functions and adds the v3 pieces.
   - BASE: every asset under /next/ (crests too), with a fallback to the production crest if a copy is missing.
   - Arabic player names (names/players_ar.json) on player-shaped nodes only: events, lineups. Latin stays the fallback.
   - Events: substitutions of one team in the same minute collapse into one line.
   - Rail cards, the hero, the competition key-art data. */
(function(root){
  "use strict";
  var R = (typeof module !== "undefined" && module.exports) ? require("../../src/render.js") : root.TR;
  var esc = R.esc, BASE = "/next/";
  R.BASE = BASE;
  // the prototype pages; links to them stay inside /next/, everything else goes to production
  R.PROTO = { "/":1, "/m/1000020522/":1, "/m/6052085/":1, "/c/uae-pro-league/":1, "/c/saudi-pro-league/":1, "/c/premier-league/":1, "/competitions/":1 };
  R.nx = function(href){ return R.PROTO[href] ? BASE.slice(0, -1) + href : href; };
  R.logo = function(t, cls){ if (!t || !t.id) return ""; return '<img class="logo' + (cls ? " " + cls : "") + '" src="' + BASE + "logo/" + t.id + '.png" alt="" loading="lazy" width="24" height="24" onerror="if(!this.dataset.f){this.dataset.f=1;this.src=\'/logo/' + t.id + '.png\'}else this.style.visibility=\'hidden\'">'; };

  // ---- Arabic names: PN = { playerId: "الاسم" }
  var PN = (root && root.PN) || {};
  R.setNames = function(m){ PN = m || {}; };
  function ar(p){ if (p && p.id && PN[p.id] && !p._ar){ p.name_en = p.name; p.name = PN[p.id]; p._ar = 1; } }
  R.arNames = function(md){
    if (!md || md._arn) return md; md._arn = 1;
    (md.events || []).forEach(function(e){ ar(e.player); ar(e.assist); ar(e.player_out); });
    var L = md.lineups; if (L) ["home", "away"].forEach(function(s){ if (!L[s]) return; (L[s].starters || []).concat(L[s].subs || [], L[s].unavailable || []).forEach(ar); });
    return md;
  };
  // scorer / assister lists (app.js re-renders them from fresh stats.json)
  var lead0 = R.leaders; R.leaders = function(stats){ if (stats && stats.lists) Object.keys(stats.lists).forEach(function(k){ (stats.lists[k] || []).forEach(function(r){ ar(r.player); }); }); return lead0.apply(R, arguments); };
  ["lineups", "catchup"].forEach(function(k){ var f = R[k]; R[k] = function(md){ return f.apply(R, [R.arNames(md)].concat([].slice.call(arguments, 1))); }; });

  // ---- events: same minute + same team substitutions on one line
  var EV = { penalty_goal:"بلنتي", own_goal:"في مرماه", missed_penalty:"بلنتي ضايع", yellow:"إنذار", red:"طرد", second_yellow:"إنذار ثاني وطرد", var:"الفار" };
  function evIcon(t){ if (t === "yellow") return '<i class="ico yellow"></i>'; if (t === "red" || t === "second_yellow") return '<i class="ico red"></i>'; if (/goal/.test(t)) return '<i class="ico goal"></i>'; if (t === "missed_penalty") return '<i class="ico miss"></i>'; return '<i class="ico sub"></i>'; }
  function sc(s){ return s.home + " - " + s.away; }
  function nm(p){ return p ? '<span class="lat">' + esc(p.name) + "</span>" : ""; }
  R.events = function(md){
    R.arNames(md);
    var ev = md.events || []; if (!ev.length) return '<p class="empty">' + (md.status === "scheduled" ? "المباراة ما بدت." : "ما في أحداث مسجّلة.") + "</p>";
    var rows = [];
    ev.forEach(function(e){ var last = rows[rows.length - 1];
      if (e.type === "sub" && last && last.sub && last.team === e.team && last.minute === e.minute && (last.added || 0) === (e.added || 0)){ last.list.push(e); return; }
      rows.push(e.type === "sub" ? { sub:true, team:e.team, minute:e.minute, added:e.added, list:[e] } : { e:e }); });
    return '<ul class="ev">' + rows.map(function(r){
      var e = r.e;
      if (e && e.type === "half"){ var hl = { HT:"نهاية الشوط الأول", FT:"نهاية المباراة", AET:"نهاية الوقت الإضافي", EHT:"نهاية الشوط الإضافي الأول", Pen:"ركلات الترجيح" }[e.detail] || esc(e.detail); return '<li class="div">' + hl + (e.score ? ' <span class="num">' + sc(e.score) + "</span>" : "") + "</li>"; }
      if (e && e.type === "added_time") return '<li class="div">+' + esc(e.detail) + " دقايق وقت بدل ضايع</li>";
      var body, team, mn;
      if (r.sub){
        team = r.team; mn = '<bdi dir="ltr">' + esc(r.minute) + (r.added ? "+" + esc(r.added) : "") + "'</bdi>";
        body = '<span class="who">' + evIcon("sub") + '<span class="kind">' + (r.list.length > 1 ? r.list.length + " تبديلات" : "تبديل") + "</span></span>" +
          '<span class="sub subs"><span class="in">دخل ' + r.list.map(function(x){ return nm(x.player); }).join("، ") + '</span><span class="out">طلع ' + r.list.map(function(x){ return nm(x.player_out); }).join("، ") + "</span></span>";
      } else {
        team = e.team; mn = '<bdi dir="ltr">' + esc(e.minute) + (e.added ? "+" + esc(e.added) : "") + "'</bdi>";
        var extra = e.assist ? '<span class="sub">صناعة ' + nm(e.assist) + "</span>" : "";
        body = '<span class="who">' + evIcon(e.type) + nm(e.player) + (/goal/.test(e.type) && e.score ? '<span class="gs">' + sc(e.score) + "</span>" : "") + (EV[e.type] ? '<span class="kind">' + EV[e.type] + "</span>" : "") + "</span>" + extra;
      }
      var k = e && /goal/.test(e.type) ? " g" : "";
      return team === "home" ? '<li class="' + k + '"><span class="h">' + body + '</span><span class="mn">' + mn + "</span><span></span></li>" : '<li class="' + k + '"><span></span><span class="mn">' + mn + "</span><span>" + body + "</span></li>";
    }).join("") + '</ul><p class="src"><a href="/laws/">ليش ألغى الحكم هدف أو صفّر بلنتي؟ قانون الكورة بالإماراتي</a></p>';
  };

  // ---- rail card: a match as a key-art card (club colour bands on the outer edges)
  R.railCard = function(m, o){
    o = o || {}; var live = R.isLive(m), fin = m.status === "finished", s = m.score;
    var mid = live ? '<b class="dg">' + (s ? sc(s) : "0 - 0") + '</b><span class="st live"><i class="cardflip"></i>' + R.minute(m) + "</span>"
      : s ? '<b class="dg">' + sc(s) + '</b><span class="st">' + R.statusText(m) + "</span>"
      : '<b class="dg">' + (m.time_tbd ? "—" : R.tt(m.kickoff_uae)) + '</b><span class="st">' + R.td(m.kickoff_uae) + "</span>";
    var mine = o.mine && (m.home.id === o.mine || m.away.id === o.mine);
    return '<a class="rc' + (live ? " live" : "") + (mine ? " mine" : "") + '" href="' + R.nx("/m/" + m.id + "/") + '" data-mid="' + m.id + '" style="--hc:' + R.col(m.home.id, 0) + ";--ac:" + R.col(m.away.id, 0) + '">' +
      '<span class="cp">' + esc(o.comp || m.comp_name_ar || "") + "</span>" +
      '<span class="rt3"><span class="t' + (fin && s && s.home > s.away ? " win" : "") + '">' + R.logo(m.home, "md") + "<span>" + R.tname(m.home) + '</span></span><span class="mid">' + mid + '</span><span class="t' + (fin && s && s.away > s.home ? " win" : "") + '">' + R.logo(m.away, "md") + "<span>" + R.tname(m.away) + "</span></span></span></a>";
  };
  R.rail = function(id, title, cards, more, slot){
    return '<section class="rail" id="' + id + '" data-slot="' + (slot || "rail") + '"' + (cards ? "" : " hidden") + '><div class="rail-h"><h2>' + title + "</h2>" + (more || "") + '</div><div class="rail-s" tabindex="0">' + (cards || "") + "</div></section>";
  };
  // home rails from one day's matches (build prerender + app.js "tifo:day" refresh)
  var ARABC = {}; R.COUNTRIES.forEach(function(c){ ARABC[c[0]] = 1; });
  R.homeRails = function(ms, index, o){
    o = o || {}; var cn = {}, cc = {}; (index.competitions || []).forEach(function(c){ cn[c.id] = c.name_ar; cc[c.id] = R.compCountry(c); });
    var AT = o.arabT || (root && root.ARABT) || {}, card = function(m){ return R.railCard(m, { comp:cn[m.comp], mine:o.mine }); };
    var sorted = (ms || []).slice().sort(function(a, b){ return (a.kickoff_utc || "").localeCompare(b.kickoff_utc || ""); });
    var live = sorted.filter(R.isLive), now = Date.now();
    var up = sorted.filter(function(m){ return m.status === "scheduled" && Date.parse(m.kickoff_utc) > now - 3 * 3600e3; });
    var fin = sorted.filter(function(m){ return m.status === "finished"; }).reverse();
    var arab = sorted.filter(function(m){ return (ARABC[cc[m.comp]] || AT[m.home.id] || AT[m.away.id] || [329, 10242, 11156, 10474].indexOf(m.comp) >= 0) && !R.isLive(m); });
    var ord = R.compOrder(index), big = function(a, b){ return (ord[a.comp] == null ? 99 : ord[a.comp]) - (ord[b.comp] == null ? 99 : ord[b.comp]); };
    return { live:live.map(card).join(""), today:up.slice().sort(big).slice(0, 14).map(card).join("") + fin.slice(0, 6).map(card).join(""), arab:arab.slice(0, 16).map(card).join(""), n:{ live:live.length, up:up.length, arab:arab.length } };
  };
  // hero choice: live (UAE / Arab first) -> the visitor's team today -> tonight's biggest (UAE national, Arab national, UAE clubs, big European)
  R.heroPick = function(ms, index, mine){
    ms = (ms || []).filter(function(m){ return m.status !== "cancelled"; }); if (!ms.length) return null;
    var cc = {}; (index.competitions || []).forEach(function(c){ cc[c.id] = R.compCountry(c); });
    var AT = (root && root.ARABT) || {};
    var w = function(m){ var s = 0; if (R.isLive(m)) s += 1000; if (mine && (m.home.id === mine || m.away.id === mine)) s += 500; if (m.home.id === 5789 || m.away.id === 5789) s += 120;
      if ([329, 10242, 11156, 290, 10197].indexOf(m.comp) >= 0) s += 80; if (R.UAE_COMPS.indexOf(m.comp) >= 0) s += 60; if ([525, 42].indexOf(m.comp) >= 0) s += 40; if (ARABC[cc[m.comp]]) s += 20;
      if (m.status === "scheduled") s += 15; if (m.status === "finished") s -= 10; return s; };
    return ms.slice().sort(function(a, b){ return w(b) - w(a) || (a.kickoff_utc || "").localeCompare(b.kickoff_utc || ""); })[0];
  };
  R.heroLine = function(m, index){
    if (!m) return "";
    var live = R.isLive(m), s = m.score, cn = R.compName(index || {}, m.comp) || m.comp_name_ar || "";
    var mid = live ? '<b class="dg big">' + (s ? sc(s) : "0 - 0") + '</b><span class="st live"><i class="cardflip"></i>' + R.minute(m) + "</span>"
      : s ? '<b class="dg big">' + sc(s) + '</b><span class="st">' + R.statusText(m) + "</span>"
      : '<b class="dg big">' + (m.time_tbd ? "—" : R.tt(m.kickoff_uae)) + '</b><span class="st">' + R.td(m.kickoff_uae, true) + "</span>";
    return '<p class="hk">' + esc(cn) + (m.stage && /Gr(ou)?p/i.test(m.stage) ? "، " + esc(R.stageAr(m.stage)) : "") + "</p>" +
      '<div class="hl"><a class="htm h" href="' + R.nx("/t/" + m.home.id + "/") + '">' + R.logo(m.home, "xl") + "<span>" + R.tname(m.home) + '</span></a><a class="hsc' + (live ? " live" : "") + '" href="' + R.nx("/m/" + m.id + "/") + '">' + mid + '</a><a class="htm a" href="' + R.nx("/t/" + m.away.id + "/") + '">' + R.logo(m.away, "xl") + "<span>" + R.tname(m.away) + "</span></a></div>";
  };
  if (typeof module !== "undefined" && module.exports) module.exports = R;
  else {
    // app.js drives the home hero through R.featured + R.standCap + TifoStand; v3 swaps in its own pick and title treatment
    var mine = function(){ try { return +localStorage.getItem("tifo.mine") || null; } catch (e){ return null; } };
    R.featured = function(ms){ return R.heroPick(ms, R._idx || {}, mine()); };
    R.standCap = function(m){ return R.heroLine(m, R._idx); };
  }
})(this);

;
/* تيفو images (phase 3): story card for a result or a coming match (12, 60), phone wallpaper of a club's fixtures (44),
   and the Tifo studio banner (152). All drawn on canvas in the Tifo identity (night pitch, card mosaic, Kufi + Barlow),
   from same-origin logos so the canvas stays exportable. Shared with navigator.share when the phone supports files,
   otherwise downloaded. */
(function(){
  "use strict";
  var R = window.TR, NIGHT = "#0A2620", NIGHT2 = "#123A31", CHALK = "#F6F7F2", DUNE = "#B07A3B", PULSE = "#10A04B";
  function col(id, i){ var c = (window.TC || {})[id]; return c ? (c[i || 0] || c[0]) : (i ? "#F6F7F2" : "#5C6660"); }
  function img(src){ return new Promise(function(ok){ var i = new Image(); i.onload = function(){ ok(i); }; i.onerror = function(){ ok(null); }; i.src = src; }); }
  function fonts(){ return (document.fonts && document.fonts.ready) ? Promise.all([document.fonts.load('800 60px "Noto Kufi Arabic"'), document.fonts.load('700 60px "Barlow Condensed"'), document.fonts.load('400 30px "Readex Pro"')]).catch(function(){}) : Promise.resolve(); }
  function seed(n){ return function(){ n = (n * 16807) % 2147483647; return n / 2147483647; }; }
  // the stand: a band of cards in two clubs' colours, home on the right
  function stand(x, X, Y, W, H, cs, hid, aid, s){
    var rnd = seed(s || 7), cols = Math.ceil(W / cs), rows = Math.ceil(H / cs);
    for (var r = 0; r < rows; r++) for (var c = 0; c < cols; c++){
      var home = c >= cols / 2, id = home ? hid : aid, stripe = ((home ? cols - c : c) + r) % 7 < 2, k = 0.88 + rnd() * 0.2;
      x.globalAlpha = k > 1 ? 1 : k; x.fillStyle = aid == null ? col(hid, stripe ? 1 : 0) : col(id, stripe ? 1 : 0);
      x.fillRect(X + c * cs, Y + r * cs, cs - 3, cs - 3);
    }
    x.globalAlpha = 1;
  }
  function text(x, s, X, Y, font, color, align, dir){ x.font = font; x.fillStyle = color; x.textAlign = align || "center"; x.direction = dir || "rtl"; x.fillText(s, X, Y); }
  function fit(x, s, font, max){ var size = parseInt(font.match(/(\d+)px/)[1], 10); x.font = font; while (x.measureText(s).width > max && size > 20){ size -= 2; x.font = font.replace(/\d+px/, size + "px"); } return x.font; }
  function mark(x, X, Y, s){ var cl = [[CHALK, PULSE, DUNE], [CHALK, DUNE, PULSE], [PULSE, DUNE, CHALK]]; for (var r = 0; r < 3; r++) for (var c = 0; c < 3; c++){ x.fillStyle = cl[r][c]; x.fillRect(X + c * s * 1.2, Y + r * s * 1.2, s, s); } }
  function footer(x, W, H){ mark(x, W - 230, H - 130, 22); text(x, "تيفو", W - 330, H - 72, '800 64px "Noto Kufi Arabic"', CHALK, "right"); text(x, "tifo.elyoxe.com", 70, H - 78, '700 40px "Barlow Condensed"', "#B9C7C0", "left"); }
  function out(canvas, name){
    return new Promise(function(ok){ canvas.toBlob(function(b){
      var f = new File([b], name, { type:"image/png" });
      if (navigator.canShare && navigator.canShare({ files:[f] })) navigator.share({ files:[f] }).then(ok, function(){ dl(); ok(); }); else { dl(); ok(); }
      function dl(){ var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = name; document.body.appendChild(a); a.click(); setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); }, 2000); }
    }, "image/png"); });
  }
  // story (1080x1920): result, live or coming match (+ probabilities for a coming one)
  function story(md){
    var W = 1080, H = 1920, c = document.createElement("canvas"); c.width = W; c.height = H; var x = c.getContext("2d");
    return fonts().then(function(){ return Promise.all([img("/logo/" + md.home.id + ".png"), img("/logo/" + md.away.id + ".png")]); }).then(function(L){
      x.fillStyle = NIGHT; x.fillRect(0, 0, W, H);
      stand(x, 0, 0, W, 560, 36, md.home.id, md.away.id, md.id % 997 + 3);
      x.fillStyle = NIGHT; x.fillRect(0, 560, W, H - 560);
      var comp = md.comp_name_ar || ""; text(x, comp, W / 2, 680, '400 40px "Readex Pro"', "#B9C7C0");
      if (L[0]) x.drawImage(L[0], W - 330, 760, 220, 220); if (L[1]) x.drawImage(L[1], 110, 760, 220, 220);
      text(x, md.home.name_ar || md.home.name, W - 220, 1060, fit(x, md.home.name_ar || md.home.name, '800 56px "Noto Kufi Arabic"', 420), CHALK);
      text(x, md.away.name_ar || md.away.name, 220, 1060, fit(x, md.away.name_ar || md.away.name, '800 56px "Noto Kufi Arabic"', 420), CHALK);
      var live = R.isLive(md);
      if (md.score){ text(x, String(md.score.home), W / 2 + 130, 960, '700 230px "Barlow Condensed"', live ? "#5BE08F" : CHALK); text(x, "-", W / 2, 940, '700 160px "Barlow Condensed"', "#B9C7C0"); text(x, String(md.score.away), W / 2 - 130, 960, '700 230px "Barlow Condensed"', live ? "#5BE08F" : CHALK); }
      else text(x, R.hhmm(md.kickoff_uae), W / 2, 930, '700 170px "Barlow Condensed"', CHALK);
      var st = live ? "مباشر " + (md.minute || "") + "'" : md.status === "finished" ? "انتهت" : R.dayLabel(R.ymd(md.kickoff_uae));
      text(x, st, W / 2, 1180, '800 46px "Noto Kufi Arabic"', live ? "#5BE08F" : DUNE);
      var y = 1300;
      if (md.status === "finished" || live){
        (md.events || []).filter(function(e){ return /goal/.test(e.type) && e.player; }).slice(0, 8).forEach(function(e){ var s = e.team === "home" ? e.minute + "'  " + e.player.name : e.player.name + "  " + e.minute + "'"; text(x, s, e.team === "home" ? W - 90 : 90, y, '400 36px "Readex Pro"', CHALK, e.team === "home" ? "right" : "left", "ltr"); y += 56; });
      } else if (md.probs){
        var p = md.probs, bw = W - 180, hx = 90;
        x.fillStyle = col(md.away.id); x.fillRect(hx, y, bw * p.away, 34); x.fillStyle = "#9BA39E"; x.fillRect(hx + bw * p.away + 4, y, bw * p.draw - 8, 34); x.fillStyle = col(md.home.id); x.fillRect(hx + bw * (p.away + p.draw), y, bw * p.home, 34);
        text(x, "فوز " + (md.home.name_ar || "") + " " + Math.round(p.home * 100) + "%", W - 90, y + 100, '400 36px "Readex Pro"', CHALK, "right");
        text(x, "فوز " + (md.away.name_ar || "") + " " + Math.round(p.away * 100) + "%", 90, y + 100, '400 36px "Readex Pro"', CHALK, "left");
        text(x, "تعادل " + Math.round(p.draw * 100) + "%", W / 2, y + 160, '400 36px "Readex Pro"', "#B9C7C0");
        text(x, "توقعات تيفو", W / 2, y + 240, '800 34px "Noto Kufi Arabic"', DUNE);
      }
      if (md.venue && md.venue.name_ar) text(x, md.venue.name_ar, W / 2, H - 260, '400 34px "Readex Pro"', "#B9C7C0");
      footer(x, W, H);
      return window.TifoShare.out(c, "tifo-" + md.id + ".png");
    });
  }
  // phone wallpaper (1080x2340): the club's next matches on its own colours
  function wallpaper(t, next){
    var W = 1080, H = 2340, c = document.createElement("canvas"); c.width = W; c.height = H; var x = c.getContext("2d");
    return fonts().then(function(){ return img("/logo/" + t.id + ".png"); }).then(function(L){
      x.fillStyle = NIGHT; x.fillRect(0, 0, W, H); stand(x, 0, 0, W, 760, 40, t.id, null, t.id % 991 + 5);
      x.fillStyle = NIGHT; x.fillRect(W / 2 - 170, 470, 340, 340); if (L) x.drawImage(L, W / 2 - 140, 500, 280, 280);
      text(x, t.name, W / 2, 930, fit(x, t.name, '800 80px "Noto Kufi Arabic"', W - 160), CHALK);
      var y = 1060;
      next.slice(0, 5).forEach(function(m){
        var home = m.home.id === t.id, opp = home ? m.away : m.home;
        x.fillStyle = NIGHT2; x.fillRect(70, y, W - 140, 170);
        text(x, (home ? "ضد " : "في ملعب ") + (opp.name_ar || opp.name), W - 110, y + 75, fit(x, opp.name_ar || opp.name, '800 44px "Noto Kufi Arabic"', 560), CHALK, "right");
        text(x, (m.comp_name_ar || ""), W - 110, y + 135, '400 30px "Readex Pro"', "#B9C7C0", "right");
        text(x, R.hhmm(m.kickoff_uae), 110, y + 85, '700 70px "Barlow Condensed"', DUNE, "left");
        var dp = R.dayParts(R.ymd(m.kickoff_uae)); text(x, dp.date, 110, y + 140, '400 30px "Readex Pro"', "#B9C7C0", "left");
        y += 200;
      });
      footer(x, W, H);
      return window.TifoShare.out(c, "tifo-" + t.id + "-wallpaper.png");
    });
  }
  // Tifo studio banner (3000x1000, print-ready): the club's colours as a card mosaic with the fans' words
  function banner(id, words){
    var W = 3000, H = 1000, c = document.createElement("canvas"); c.width = W; c.height = H; var x = c.getContext("2d");
    return fonts().then(function(){ return img("/logo/" + id + ".png"); }).then(function(L){
      x.fillStyle = NIGHT; x.fillRect(0, 0, W, H); stand(x, 0, 0, W, H, 50, id, null, id % 983 + 11);
      x.fillStyle = "rgba(10,38,32,.86)"; x.fillRect(260, 250, W - 520, 500);
      if (L) x.drawImage(L, W - 700, 330, 340, 340);
      text(x, words || "", W / 2 - 180, 580, fit(x, words || "", '800 190px "Noto Kufi Arabic"', W - 1300), CHALK);
      return c;
    });
  }
  // 250: any section as a square card (title + its first lines)
  function card(title, lines){
    var W = 1080, H = 1080, c = document.createElement("canvas"); c.width = W; c.height = H; var x = c.getContext("2d");
    return fonts().then(function(){
      x.fillStyle = NIGHT; x.fillRect(0, 0, W, H); var cl = [CHALK, PULSE, DUNE]; for (var i = 0; i < 27; i++){ x.fillStyle = cl[i % 3]; x.globalAlpha = .9; x.fillRect(i * 40, 0, 36, 36); } x.globalAlpha = 1;
      text(x, title, W - 80, 170, fit(x, title, '800 64px "Noto Kufi Arabic"', W - 160), CHALK, "right");
      var y = 280; lines.slice(0, 8).forEach(function(l){ x.fillStyle = NIGHT2; x.fillRect(70, y - 52, W - 140, 78); text(x, l, W - 100, y, fit(x, l, '400 36px "Readex Pro"', W - 220), CHALK, "right"); y += 92; });
      footer(x, W, H); return window.TifoShare.out(c, "tifo-card.png");
    });
  }
  // 291: the coming round with Tifo odds; 314: the week's matches in the visitor's time zone with channels
  function listCard(title, sub, rows, name){
    var W = 1080, H = Math.max(1080, 320 + rows.length * 120 + 160), c = document.createElement("canvas"); c.width = W; c.height = H; var x = c.getContext("2d");
    return fonts().then(function(){ return Promise.all(rows.map(function(r){ return Promise.all([r.h ? img("/logo/" + r.h + ".png") : null, r.a ? img("/logo/" + r.a + ".png") : null]); })); }).then(function(L){
      x.fillStyle = NIGHT; x.fillRect(0, 0, W, H); var cl = [CHALK, PULSE, DUNE]; for (var i = 0; i < 27; i++){ x.fillStyle = cl[i % 3]; x.fillRect(i * 40, 0, 36, 36); }
      text(x, title, W - 70, 150, fit(x, title, '800 60px "Noto Kufi Arabic"', W - 140), CHALK, "right"); if (sub) text(x, sub, W - 70, 210, '400 32px "Readex Pro"', "#B9C7C0", "right");
      var y = 270; rows.forEach(function(r, i){ x.fillStyle = NIGHT2; x.fillRect(60, y, W - 120, 104);
        if (L[i][0]) x.drawImage(L[i][0], W - 140, y + 22, 60, 60); if (L[i][1]) x.drawImage(L[i][1], 80, y + 22, 60, 60);
        text(x, r.home, W - 160, y + 50, fit(x, r.home, '800 34px "Noto Kufi Arabic"', 300), CHALK, "right"); text(x, r.away, 160, y + 50, fit(x, r.away, '800 34px "Noto Kufi Arabic"', 300), CHALK, "left");
        text(x, r.mid, W / 2, y + 50, '700 40px "Barlow Condensed"', DUNE); if (r.low) text(x, r.low, W / 2, y + 88, '400 26px "Readex Pro"', "#B9C7C0");
        y += 120; });
      footer(x, W, H); return window.TifoShare.out(c, name || "tifo-list.png"); });
  }
  window.TifoShare = { story:story, wallpaper:wallpaper, banner:banner, out:out, card:card, listCard:listCard };
})();

;
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
  function Art(canvas){
    this.c = canvas; this.x = canvas.getContext("2d"); this.cells = []; this.waves = []; this.run = false; this.bands = [];
    var self = this;
    canvas.addEventListener("pointerdown", function(e){ var r = canvas.getBoundingClientRect(); self.wave((e.clientX - r.left) / self.cs, (e.clientY - r.top) / self.cs, 0.9); });
    window.addEventListener("resize", function(){ clearTimeout(self.rt); self.rt = setTimeout(function(){ if (self.c.clientWidth !== self.w){ self.layout(); self.draw(performance.now(), true); } }, 150); });
  }
  // bands: [[colour, stripe colour], ...] from right to left
  Art.prototype.paint = function(bands, seed){ this.bands = bands.map(function(b){ return [hex(b[0]), hex(b[1] || b[0])]; }); this.seed = seed || 7; this.layout(); if (!this.shown){ this.shown = true; this.intro(); } else this.draw(performance.now(), true); };
  Art.prototype.set = function(m){   // match
    var TC = window.TC || {}, prev = this.m; this.m = m;
    var h = TC[m.home.id] || ["#8A938D", "#F6F7F2"], a = TC[m.away.id] || ["#3D4A44", "#F6F7F2"];
    if (!prev || prev.id !== m.id) this.paint([h, a], m.id % 997 + 3);
    else if (prev.score && m.score && (m.score.home !== prev.score.home || m.score.away !== prev.score.away)) this.wave(m.score.home > prev.score.home ? this.cols : 0, this.rows / 2, 1.6);
  };
  Art.prototype.layout = function(){
    var c = this.c, w = c.clientWidth, h = c.clientHeight, dpr = Math.min(2, window.devicePixelRatio || 1); this.w = w;
    c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); this.x.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.cs = w < 500 ? 11 : w < 1000 ? 13 : 16; this.cols = Math.ceil(w / this.cs); this.rows = Math.ceil(h / this.cs);
    var cols = this.cols, rows = this.rows, nb = this.bands.length || 1, seed = this.seed, cells = [];
    function rnd(){ seed = (seed * 16807) % 2147483647; return seed / 2147483647; }
    for (var y = 0; y < rows; y++) for (var x = 0; x < cols; x++){
      var bi = Math.min(nb - 1, Math.floor((cols - 1 - x) / cols * nb)), pal = this.bands[bi] || [hex("#5C6660"), hex("#F6F7F2")];
      var rel = (cols - 1 - x) - Math.floor(bi * cols / nb), stripe = (rel + y) % 7 < 2, base = pal[stripe ? 1 : 0], k = 0.82 + rnd() * 0.22;
      cells.push({ x:x, y:y, col:rgb(base, lum(base) > 0.85 ? k * 0.9 : k), d:(cols - 1 - x) / cols * 0.9 + rnd() * 0.15 });
    }
    this.cells = cells;
  };
  Art.prototype.intro = function(){ if (RM){ this.draw(0, true); return; } this.t0 = performance.now(); this.introOn = true; this.loop(); };
  Art.prototype.wave = function(cx, cy, amp){ if (RM) return; this.waves.push({ cx:cx, cy:cy, t:performance.now(), amp:amp }); this.loop(); };
  Art.prototype.loop = function(){ if (this.run) return; this.run = true; var self = this; requestAnimationFrame(function f(now){ if (self.draw(now)) requestAnimationFrame(f); else self.run = false; }); };
  Art.prototype.draw = function(now, still){
    var x = this.x, cs = this.cs, gap = 2, active = false;
    x.fillStyle = NIGHT; x.fillRect(0, 0, this.c.clientWidth, this.c.clientHeight);
    var intro = this.introOn && !still ? (now - this.t0) / 1000 : 9, waves = this.waves.filter(function(w){ return now - w.t < 2600; });
    this.waves = waves; if (intro < 1.8 || waves.length) active = true; else this.introOn = false;
    for (var i = 0; i < this.cells.length; i++){
      var c = this.cells[i], sy = 1, lift = 0;
      if (intro < 1.8){ var p = Math.min(1, Math.max(0, (intro - c.d) / 0.4)); if (p <= 0) continue; sy = Math.abs(Math.cos((1 - p) * Math.PI)) * p; }
      for (var j = 0; j < waves.length; j++){ var w = waves[j], dist = Math.hypot(c.x - w.cx, (c.y - w.cy) * 1.4), ph = (now - w.t) / 1000 * 38 - dist; if (ph > 0 && ph < 6){ var s = Math.sin(ph / 6 * Math.PI); sy *= 1 - 0.85 * s * Math.min(1, w.amp); lift = Math.max(lift, s * w.amp); } }
      var hgt = (cs - gap) * sy; x.fillStyle = c.col; x.fillRect(c.x * cs, c.y * cs + (cs - gap - hgt) / 2 - lift * 2.5, cs - gap, Math.max(0.6, hgt));
    }
    return active;
  };
  window.TifoStand = { mount:function(canvas){ return new Art(canvas); } };
  window.TifoArt = { mount:function(canvas){ return new Art(canvas); } };
})();

;
/* تيفو client: refreshes the prerendered blocks from /v1 JSON, polls live data every 20 s while something is live,
   and keeps «فريقي» (my team) in localStorage. The page type and ids come from <body data-page data-id data-comp>. */
(function(){
  "use strict";
  var R = window.TR, B = document.body, PAGE = B.dataset.page, ID = B.dataset.id, V = "/v1/";
  var $ = function(s){ return document.querySelector(s); };
  // 347: sampled error beacon (1 in 5 page views, at most 3 reports): message, file path and line only
  (function(){ if (Math.random() > 0.2) return; var n = 0; function send(m, s, l, c){ if (n++ >= 3) return; try { fetch("/api/tifo/err", { method:"POST", keepalive:true, headers:{ "content-type":"application/json" }, body:JSON.stringify({ m:String(m || "").slice(0, 300), s:s || "", l:l || null, c:c || null, p:location.pathname, v:(document.querySelector('script[src*="/assets/app."]') || {}).src ? document.querySelector('script[src*="/assets/app."]').src.split("app.")[1].slice(0, 10) : "" }) }).catch(function(){}); } catch (e){} }
    window.addEventListener("error", function(e){ if (e.filename && e.filename.indexOf(location.origin) !== 0) return; send(e.message, e.filename, e.lineno, e.colno); });
    window.addEventListener("unhandledrejection", function(e){ var r = e.reason; send(r && r.message ? r.message : r, r && r.stack ? String(r.stack).split("\n")[1] : "", null, null); }); })();
  function get(p){ return fetch(V + p, { cache:"no-cache" }).then(function(r){ if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function mine(){ try { return +localStorage.getItem("tifo.mine") || null; } catch (e){ return null; } }
  function setMine(id, name){ try { if (id) { localStorage.setItem("tifo.mine", id); localStorage.setItem("tifo.mine.name", name || ""); } else { localStorage.removeItem("tifo.mine"); } } catch (e){} }
  function uaeToday(off){ var d = new Date(Date.now() + 4 * 3600e3 + (off || 0) * 864e5); return d.toISOString().slice(0, 10); }
  function set(sel, html){ var el = $(sel); if (el){ el.innerHTML = html; R.localize(el); } }
  // ---- country (203, 199): time zone + what comes first; guessed from the browser's time zone, changeable in the header
  function country(){ try { var c = localStorage.getItem("tifo.country"); if (c) return c; } catch (e){} var tz = ""; try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e){} var hit = R.COUNTRIES.filter(function(c){ return c[2] === tz; })[0]; return hit ? hit[0] : "xx"; }
  function applyCountry(){ var c = country(), row = R.COUNTRIES.filter(function(x){ return x[0] === c; })[0]; try { R.TZ = row ? row[2] : Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e){ R.TZ = "Asia/Dubai"; }
    var b = $("#ctry"); if (b) b.textContent = row ? row[1] : "بلدك"; R.localize(document); }
  applyCountry();
  var cb = $("#ctry"); if (cb) cb.onclick = function(){ var box = $("#ctrybox"); if (box){ box.remove(); return; }
    box = document.createElement("div"); box.id = "ctrybox"; box.className = "ctrybox"; var cur = country();
    box.innerHTML = '<p class="small">اختار بلدك: المواعيد تطلع بتوقيته، ومبارياته أول شي.</p><div class="cgrid">' + R.COUNTRIES.map(function(c){ return '<button type="button" data-c="' + c[0] + '"' + (c[0] === cur ? ' aria-pressed="true"' : "") + ">" + c[1] + "</button>"; }).join("") + '<button type="button" data-c="xx"' + (cur === "xx" ? ' aria-pressed="true"' : "") + ">برا الوطن العربي</button></div>";
    box.onclick = function(e){ var t = e.target.closest("button[data-c]"); if (!t) return; try { localStorage.setItem("tifo.country", t.dataset.c); } catch (x){} box.remove(); applyCountry(); if (PAGE === "home") home(); };
    document.body.appendChild(box); };
  // ---- search (167): one small index, loaded on first open; Arabic normalised (أ إ آ ا، ة ه، ى ي) and Latin both matched
  var SIDX = null, sb0 = $("#srch");
  function norm(t){ return String(t || "").toLowerCase().replace(/[أإآ]/g, "ا").replace(/ة/g, "ه").replace(/ى/g, "ي").replace(/[\u064b-\u0652]/g, "").normalize("NFD").replace(/[\u0300-\u036f]/g, ""); }
  if (sb0) sb0.onclick = function(){ var box = $("#srchbox"); if (box){ box.remove(); return; }
    box = document.createElement("div"); box.id = "srchbox"; box.className = "ctrybox"; box.innerHTML = '<input id="sq" placeholder="نادي، لاعب، بطولة…" aria-label="بحث" autocomplete="off"><div id="sr"></div>'; document.body.appendChild(box);
    var q = $("#sq"); q.focus();
    (SIDX ? Promise.resolve(SIDX) : fetch("/next/assets/search." + sb0.dataset.v + ".json").then(function(r){ return r.json(); }).then(function(x){ SIDX = x.map(function(i){ return i.concat([norm(i[1]), norm(i[2])]); }); return SIDX; })).then(function(){
      var TY = { c:"بطولة", t:"نادي", p:"لاعب", r:"صفحة" };
      q.oninput = function(){ var v = norm(q.value.trim()); if (v.length < 2){ set("#sr", ""); return; }
        var hits = SIDX.filter(function(i){ return i[4].indexOf(v) >= 0 || i[5].indexOf(v) >= 0; }).sort(function(a, b){ var o = { c:0, t:1, r:2, p:3 }; return (a[4].indexOf(v) === 0 || a[5].indexOf(v) === 0 ? 0 : 1) - (b[4].indexOf(v) === 0 || b[5].indexOf(v) === 0 ? 0 : 1) || o[a[0]] - o[b[0]]; }).slice(0, 20);
        set("#sr", hits.length ? "<ul>" + hits.map(function(i){ return '<li><a href="' + i[3] + '"><span>' + R.esc(i[1] || i[2]) + (i[1] && i[2] ? ' <span class="muted small lat">' + R.esc(i[2]) + "</span>" : "") + '</span><span class="muted small">' + TY[i[0]] + "</span></a></li>"; }).join("") + "</ul>" : '<p class="muted small">ما لقينا شي.</p>'); };
    }); };
  document.addEventListener("keydown", function(e){ if (e.key === "Escape"){ ["#srchbox", "#ctrybox"].forEach(function(s){ var b = $(s); if (b) b.remove(); }); } });
  // ---- favourites (179): several clubs and players; the first club stays «فريقي»
  function favs(){ try { return JSON.parse(localStorage.getItem("tifo.favs") || "[]"); } catch (e){ return []; } }
  function setFavs(f){ try { localStorage.setItem("tifo.favs", JSON.stringify(f)); } catch (e){} }
  (function migrate(){ var m = mine(), f = favs(); if (m && !f.some(function(x){ return x.t === "team" && x.id === m; })){ f.unshift({ t:"team", id:m, n:(localStorage.getItem("tifo.mine.name") || "") }); setFavs(f); } })();
  function stamp(g){ var el = $("#updated"); if (el && g) el.textContent = "آخر تحديث " + new Date(g).toLocaleTimeString("ar-AE-u-nu-latn", { hour:"2-digit", minute:"2-digit", timeZone:"Asia/Dubai" }); }
  function tabs(root){ (root || document).querySelectorAll(".tabs[data-tabs]").forEach(function(t){ t.addEventListener("click", function(e){ var b = e.target.closest("button[data-t]"); if (!b) return; t.querySelectorAll("button").forEach(function(x){ x.setAttribute("aria-selected", x === b ? "true" : "false"); }); document.querySelectorAll("[data-pane]").forEach(function(p){ if (p.dataset.group === t.dataset.tabs) p.hidden = p.dataset.pane !== b.dataset.t; }); try { history.replaceState(null, "", "#" + b.dataset.t); } catch (e){} }); var h = location.hash.slice(1), b = h && t.querySelector('button[data-t="' + h + '"]'); if (b) b.click(); }); }
  var timer = null; function poll(fn, ms){ clearTimeout(timer); timer = setTimeout(function(){ if (document.hidden){ poll(fn, ms); return; } fn(); }, ms); }
  document.addEventListener("visibilitychange", function(){ if (!document.hidden && timer){ clearTimeout(timer); run(); } });

  var INDEX = null;
  function index(){ return INDEX ? Promise.resolve(INDEX) : get("index.json").then(function(x){ INDEX = x; return x; }); }

  // ---- home: day list + live polling + my team
  var dayOff = 0;
  function home(){
    return Promise.all([index(), get("day/" + uaeToday(dayOff).replace(/-/g, "") + ".json").catch(function(){ return { matches:[] }; }), get("live.json").catch(function(){ return { matches:[] }; })]).then(function(r){
      var idx = r[0], day = r[1], live = r[2], by = {}; (live.matches || []).forEach(function(m){ by[m.id] = m; });
      var ms = (day.matches || []).map(function(m){ return by[m.id] || m; });
      if (freeOnly() && BCD) ms = ms.filter(function(m){ return freeIn(String(m.comp)); });
      if (arabOnly()){ var AT = window.ARABT || {}, ar = {}; R.COUNTRIES.forEach(function(c){ ar[c[0]] = 1; }); var cc = {}; (idx.competitions || []).forEach(function(c){ cc[c.id] = R.compCountry(c); }); ms = ms.filter(function(m){ return ar[cc[m.comp]] || AT[m.home.id] || AT[m.away.id]; }); }
      set("#daytitle", R.dayNav(uaeToday(dayOff), uaeToday(0)));
      var natIds = []; try { natIds = JSON.parse(localStorage.getItem("tifo.natids") || "{}")[country()] || []; } catch (e){}
      set("#day", R.dayList(ms, idx, { mine:mine(), country:country(), natIds:natIds, empty:"ما في مباريات في هاليوم." })); document.dispatchEvent(new CustomEvent("tifo:day", { detail:{ ms:ms, idx:idx, live:live, off:dayOff } }));
      var lv = (live.matches || []); set("#livecount", lv.length ? '<i class="cardflip"></i>' + lv.length + " مباراة مباشرة الحين" : "");
      if (dayOff === 0) stand(R.featured(ms));
      stamp(live.generated || day.generated);
      myCard(idx); countdown();
      poll(home, lv.length || ms.some(function(m){ var t = Date.parse(m.kickoff_utc); return m.status === "scheduled" && t - Date.now() < 15 * 60e3 && t > Date.now() - 3 * 3600e3; }) ? 20e3 : 120e3);
    });
  }
  var ST = null;
  function stand(m){
    var box = $("#stand"); if (!box || !m || !window.TifoStand) return;
    set("#standcap", R.standCap(m)); var k = $("#standkick"); if (k) k.textContent = R.isLive(m) ? "مباشر الحين" : m.status === "finished" ? "انتهت" : "مباراة اليوم";
    if (!ST) ST = window.TifoStand.mount(box.querySelector("canvas"));
    ST.set(m);
  }
  function myCard(idx){
    var el = $("#mine"); if (!el) return; var teams = favs().filter(function(x){ return x.t === "team"; });
    if (!teams.length){ el.innerHTML = '<div class="mine-card"><div class="h">مفضلتي</div><p class="small" style="margin:0">افتح صفحة أي نادي واضغط «هذا فريقي»، وضيف كم فريق تبا، ومبارياتهم تطلع لك أول شي هنا.</p></div>'; return; }
    // tn/{id}.json: next and last match per team, written by the build for every club on the site
    Promise.all(teams.slice(0, 6).map(function(x){ return fetch("/tn/" + x.id + ".json").then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; }); })).then(function(rs){
      var h = rs.map(function(t, i){ if (!t) return ""; return '<div class="favrow"><a class="h" href="/t/' + t.id + '/">' + R.logo(t) + " " + R.tname(t) + (i === 0 ? " <small>فريقي</small>" : "") + "</a>" + (t.next ? R.matchRow(t.next, { date:true }) : "") + (!t.next && t.last ? R.matchRow(t.last, { date:true }) : "") + "</div>"; }).join("");
      el.innerHTML = '<div class="mine-card">' + h + '<button type="button" class="btn copy" id="themebtn">ألوان فريقي على الموقع</button></div>'; R.localize(el);
    });
  }

  // ---- competition: standings (live), fixtures, leaders
  function comp(){
    var cid = +B.dataset.comp;
    return Promise.all([get("comp/" + cid + "/standings.json").catch(function(){ return null; }), get("comp/" + cid + "/fixtures.json").catch(function(){ return null; }), get("comp/" + cid + "/stats.json").catch(function(){ return null; }), get("live.json").catch(function(){ return { matches:[] }; })]).then(function(r){
      var st = r[0], fx = r[1], stats = r[2], live = (r[3].matches || []).filter(function(m){ return m.comp === cid; });
      if (st){ var lt = R.liveTable(st, live); set("#table", (lt.is_live ? '<p class="note"><i class="cardflip"></i>الترتيب اللحظي: لو انتهت المباريات الحين</p>' : "") + R.standings(lt, { mine:mine() })); }
      if (fx){ var by = {}; live.forEach(function(m){ by[m.id] = m; }); fx.matches = fx.matches.map(function(m){ return by[m.id] || m; }); roundsUI(fx); }
      if (stats){ set("#goals", R.leaders(stats, "goals")); set("#assists", R.leaders(stats, "assists")); }
      if (st && fx) whatif(st, fx);
      stamp((fx && fx.generated) || (st && st.generated));
      poll(comp, live.length ? 20e3 : 300e3);
    });
  }
  // «شو لو؟» (feature 11) and final day (118): pick 1/X/2 for the coming rounds, the table re-sorts
  var WI = { picks:{}, round:null, st:null, fx:null };
  function whatif(st, fx){
    var box = $("#whatif"); if (!box) return; WI.st = st; WI.fx = fx;
    var rounds = box.dataset.rounds.split(","), rr = R.rounds(fx); if (!WI.round || rounds.indexOf(WI.round) < 0) WI.round = rounds[0];
    set("#wi-r", rounds.map(function(k){ return '<button type="button" data-r="' + R.esc(k) + '"' + (k === WI.round ? ' aria-pressed="true"' : "") + ">" + R.roundLabel(k) + "</button>"; }).join(""));
    var ms = (rr.by[WI.round] || []).filter(function(m){ return m.status === "scheduled"; });
    set("#wi-m", ms.map(function(m){ var p = WI.picks[m.id]; var b = function(v, t){ return '<button type="button" data-m="' + m.id + '" data-v="' + v + '" aria-pressed="' + (p === v) + '">' + t + "</button>"; };
      return '<div class="wi"><span class="t">' + R.logo(m.home, "sm") + " " + R.tname(m.home) + '</span><span class="pick">' + b("H", "فوز") + b("D", "تعادل") + b("A", "فوز") + '</span><span class="t a">' + R.tname(m.away) + " " + R.logo(m.away, "sm") + "</span></div>"; }).join("") || '<p class="empty">ما في مباريات باقية في هالجولة.</p>');
    var rows = JSON.parse(JSON.stringify(st.groups[0].rows)), by = {}; rows.forEach(function(r){ r.was = r.rank; by[r.team.id] = r; });
    (fx.matches || []).forEach(function(m){ var p = WI.picks[m.id]; if (!p) return; var h = by[m.home.id], a = by[m.away.id]; if (!h || !a) return;
      var hs = p === "H" ? 1 : 0, as = p === "A" ? 1 : 0; [[h, hs, as], [a, as, hs]].forEach(function(x){ var r = x[0]; r.played++; r.gf += x[1]; r.ga += x[2]; r.gd = r.gf - r.ga; r.pts += x[1] > x[2] ? 3 : x[1] === x[2] ? 1 : 0; }); });
    rows.sort(function(x, y){ return y.pts - x.pts || y.gd - x.gd || y.gf - x.gf || x.was - y.was; });
    set("#wi-t", '<div class="tblwrap"><table class="st"><thead><tr><th>#</th><th style="text-align:start">الفريق</th><th>لعب</th><th>الفرق</th><th>نقاط</th></tr></thead><tbody>' + rows.map(function(r, i){ var d = r.was - (i + 1); return '<tr class="' + (mine() === r.team.id ? "mine" : "") + '"><td>' + (i + 1) + (d ? '<span class="mv ' + (d > 0 ? "up" : "dn") + '">' + (d > 0 ? "▲" : "▼") + Math.abs(d) + "</span>" : "") + '</td><td class="tm">' + R.logo(r.team, "sm") + " " + R.tname(r.team) + "</td><td>" + r.played + '</td><td><bdi dir="ltr">' + (r.gd > 0 ? "+" : "") + r.gd + '</bdi></td><td class="pts">' + r.pts + "</td></tr>"; }).join("") + "</tbody></table></div>");
    if (!box._wired){ box._wired = true; box.addEventListener("click", function(e){ var b = e.target.closest("button"); if (!b) return; if (b.dataset.r){ WI.round = b.dataset.r; } else if (b.dataset.m){ WI.picks[b.dataset.m] = WI.picks[b.dataset.m] === b.dataset.v ? undefined : b.dataset.v; } whatif(WI.st, WI.fx); }); }
  }
  var curRound = null;
  function roundsUI(fx){
    var rr = R.rounds(fx), el = $("#rounds"); if (!el) return;
    if (curRound == null || rr.order.indexOf(curRound) < 0) curRound = fx.next_round && rr.by[fx.next_round] ? fx.next_round : (function(){ var k = rr.order.filter(function(k){ return rr.by[k].some(function(m){ return m.status !== "finished"; }); })[0]; return k || rr.order[rr.order.length - 1]; })();
    var ck = (location.pathname.match(/^\/c\/([^/]+)\//) || [])[1];
    el.innerHTML = (ck && !isNaN(parseFloat(curRound)) ? '<p class="small"><a href="/c/' + ck + "/r/" + R.esc(curRound) + '/">صفحة الجولة ' + R.esc(curRound) + "</a></p>" : "") + '<div class="chips">' + rr.order.map(function(k){ return '<button type="button" data-r="' + R.esc(k) + '"' + (k === curRound ? ' aria-pressed="true"' : "") + ">" + (isNaN(parseFloat(k)) ? R.esc(k) : k) + "</button>"; }).join("") + '</div><div id="roundlist">' + (rr.by[curRound] ? R.roundList(rr.by[curRound], { mine:mine() }) : "") + "</div>";
    var cur = el.querySelector('[aria-pressed="true"]'); if (cur) cur.scrollIntoView({ block:"nearest", inline:"center" });
    el.onclick = function(e){ var b = e.target.closest("button[data-r]"); if (!b) return; curRound = b.dataset.r; roundsUI(fx); };
  }

  // ---- match: detail, live every 20 s
  var MD = null; try { var ms0 = document.getElementById("msum"); if (ms0) MD = JSON.parse(ms0.textContent); } catch (e){}
  // 3D lineup pitch (103): three.js loads only on demand
  var FULL = null, P3 = null, pbtn = $("#p3dbtn");
  if (pbtn) pbtn.onclick = function(){
    var box = $("#p3d"); if (!FULL || !box) return;
    if (P3){ P3.dispose(); P3 = null; box.innerHTML = ""; box.classList.remove("p3d"); pbtn.textContent = "شوفها على ملعب ثلاثي الأبعاد"; return; }
    pbtn.disabled = true; pbtn.textContent = "نجهّز الملعب…";
    import(pbtn.dataset.src).then(function(m){ P3 = m.mount(box, FULL); pbtn.textContent = "سكّر الملعب"; pbtn.disabled = false; box.scrollIntoView({ block:"nearest" }); })
      .catch(function(){ pbtn.textContent = "ما قدرنا نفتح الملعب، جرّب مرة ثانية"; pbtn.disabled = false; });
  };
  var sb = $("#storybtn"); if (sb) sb.onclick = function(){ if (MD && window.TifoShare){ sb.disabled = true; window.TifoShare.story(MD).then(function(){ sb.disabled = false; }); } };
  function match(){
    return Promise.all([index(), get("match/" + ID + ".json")]).then(function(r){
      var idx = r[0], md = r[1];
      MD = md; FULL = md; document.dispatchEvent(new CustomEvent("tifo:match", { detail:md })); setTimeout(dist, 0); var pb = $("#p3dbtn"); if (pb) pb.hidden = !(md.lineups && md.lineups.home);
      set("#mh", R.matchHead(md)); set("#facts", R.matchFacts(md, idx)); set("#catchup", R.catchup(md)); set("#events", R.events(md)); set("#lineups", R.lineups(md)); set("#stats", R.stats(md)); set("#h2h", R.h2h(md));
      stamp(md.generated);
      var t = Date.parse(md.kickoff_utc), soon = md.status === "scheduled" && t - Date.now() < 90 * 60e3 && t > Date.now() - 3 * 3600e3;
      if (R.isLive(md) || soon) poll(match, 20e3);
    }).catch(function(){ /* no detail yet: keep the prerendered summary */ });
  }

  // ---- team
  function team(){
    var btn = $("#mybtn");
    function isFav(){ return favs().some(function(x){ return x.t === "team" && x.id === +ID; }); }
    function paint(){ if (!btn) return; var on = isFav(); btn.textContent = on ? (mine() === +ID ? "فريقي ✓" : "في مفضلتي ✓") : (favs().length ? "ضيفه لمفضلتي" : "هذا فريقي"); btn.classList.toggle("on", on); }
    if (btn){ btn.onclick = function(){ var f = favs(); if (isFav()){ f = f.filter(function(x){ return !(x.t === "team" && x.id === +ID); }); if (mine() === +ID){ var nx = f.filter(function(x){ return x.t === "team"; })[0]; setMine(nx ? nx.id : null, nx ? nx.n : ""); } } else { f.push({ t:"team", id:+ID, n:B.dataset.name }); if (!mine()) setMine(+ID, B.dataset.name); } setFavs(f); paint(); }; paint(); }
    return get("team/" + ID + ".json").then(function(t){
      var f = R.teamFixtures(t);
      set("#next", f.next.length ? f.next.slice(0, 6).map(function(m){ return R.matchRow(m, { date:true }); }).join("") : '<p class="empty">ما في مباريات ياية منشورة.</p>');
      set("#past", f.past.length ? f.past.slice(0, 10).map(function(m){ return R.matchRow(m, { date:true }); }).join("") : '<p class="empty">ما في نتايج.</p>');
      set("#squad", R.squad(t)); stamp(t.generated);
      var wp = $("#wpbtn"); if (wp && window.TifoShare){ wp.hidden = !f.next.length; wp.onclick = function(){ wp.disabled = true; window.TifoShare.wallpaper({ id:t.id, name:t.name_ar || t.name }, f.next).then(function(){ wp.disabled = false; }); }; }
    }).catch(function(){});
  }

  var pv = $("#prev"), nx = $("#next");
  if (pv && nx && PAGE === "home"){ pv.onclick = function(){ dayOff--; home(); }; nx.onclick = function(){ dayOff++; home(); }; }
  var ics = $("#ics"); if (ics) ics.href = "webcal://" + location.host + "/v1/team/" + ID + ".ics";
  // ---- countdown to the national team's next match (62), on home and /uae/
  var CD = null;
  function countdown(){
    var el = $("#uaecd"); if (!el) return;
    (CD ? Promise.resolve(CD) : get("team/5789.json").then(function(t){ CD = R.teamFixtures(t).next.filter(function(m){ return m.kickoff_utc && !m.time_tbd; })[0] || null; return CD; })).then(function(m){
      if (!m){ el.innerHTML = ""; return; }
      if (R.isLive(m) || Date.parse(m.kickoff_utc) <= Date.now()){ el.innerHTML = '<a class="cd" href="/m/' + m.id + '/"><b>المنتخب يلعب الحين</b><span class="dg">مباشر</span></a>'; return; }
      var tick = function(){ var d = Math.max(0, Date.parse(m.kickoff_utc) - Date.now()), dd = Math.floor(d / 864e5), hh = Math.floor(d / 36e5) % 24, mm = Math.floor(d / 6e4) % 60, ss = Math.floor(d / 1e3) % 60, p2 = function(n){ return n < 10 ? "0" + n : n; };
        var opp = m.home.id === 5789 ? m.away : m.home;
        el.innerHTML = '<a class="cd" href="/m/' + m.id + '/"><span><b>' + R.tname(m.home) + ' ضد ' + R.tname(m.away) + '</b><br><span class="small">' + R.esc(R.dayLabel(R.ymd(m.kickoff_uae))) + " " + R.hhmm(m.kickoff_uae) + '</span></span><span class="dg">' + (dd ? dd + " يوم " : "") + p2(hh) + ":" + p2(mm) + ":" + p2(ss) + "</span></a>"; };
      tick(); clearInterval(el._t); el._t = setInterval(tick, 1000);
    }).catch(function(){});
  }

  // ---- majlis TV (22) and matches side by side (131): /tv/ and /tv/?m=id,id
  function tv(){
    var pins = []; try { pins = (new URLSearchParams(location.search).get("m") || "").split(",").filter(Boolean).map(Number); } catch (e){}
    var box = $("#tv"); if (!box) return Promise.resolve();
    var load = pins.length ? Promise.all(pins.map(function(id){ return get("match/" + id + ".json").catch(function(){ return null; }); })) : Promise.all([get("day/" + uaeToday(0).replace(/-/g, "") + ".json").catch(function(){ return { matches:[] }; }), get("live.json").catch(function(){ return { matches:[] }; })]).then(function(r){ var by = {}; (r[1].matches || []).forEach(function(m){ by[m.id] = m; }); return (r[0].matches || []).map(function(m){ return by[m.id] || m; }).sort(function(a, b){ return (R.isLive(b) - R.isLive(a)) || (a.kickoff_utc || "").localeCompare(b.kickoff_utc || ""); }); });
    return load.then(function(ms){
      ms = ms.filter(Boolean); box.className = "tvgrid" + (pins.length ? " pin" : "");
      box.innerHTML = ms.length ? ms.map(function(m){ var live = R.isLive(m), big = m.score ? m.score.home + " - " + m.score.away : R.hhmm(m.kickoff_uae);
        var ev = pins.length ? "<ul>" + (m.events || []).filter(function(e){ return /goal|red|second_yellow/.test(e.type) && e.player; }).reverse().map(function(e){ return "<li>" + e.minute + "' " + (/goal/.test(e.type) ? "⚽ " : "🟥 ") + R.esc(e.player.name) + " (" + R.tname(e.team === "home" ? m.home : m.away) + ")</li>"; }).join("") + "</ul>" : "";
        return '<a class="tvt' + (live ? " live" : "") + '" href="/m/' + m.id + '/"><span class="cmp">' + R.esc(m.comp_name_ar || "") + '</span><span class="row"><span class="tn">' + R.logo(m.home) + R.tname(m.home) + '</span><span class="big">' + big + '</span><span class="tn a">' + R.logo(m.away) + R.tname(m.away) + '</span></span><span class="st">' + (live ? R.minute(m) + (R.hot(m) ? " حامي" : "") : R.statusText(m)) + "</span>" + ev + "</a>"; }).join("") : '<p class="empty">ما في مباريات اليوم.</p>';
      stamp(new Date().toISOString()); poll(tv, 20e3);
    });
  }
  function tvFull(){ var b = $("#fsbtn"); if (b) b.onclick = function(){ var d = document.documentElement; if (!document.fullscreenElement && d.requestFullscreen) d.requestFullscreen(); else if (document.exitFullscreen) document.exitFullscreen(); }; }

  // ---- Tifo studio (152)
  function studio(){
    var sel = $("#sclub"), txt = $("#stext"), cv = $("#sprev"), btn = $("#sdl"); if (!sel || !window.TifoShare) return Promise.resolve();
    var draw = function(){ window.TifoShare.banner(+sel.value, txt.value.trim()).then(function(c){ var x = cv.getContext("2d"); cv.width = 1500; cv.height = 500; x.drawImage(c, 0, 0, 1500, 500); cv._full = c; }); };
    var t = null; sel.onchange = draw; txt.oninput = function(){ clearTimeout(t); t = setTimeout(draw, 250); };
    btn.onclick = function(){ if (cv._full) window.TifoShare.out(cv._full, "tifo-banner.png"); };
    draw(); return Promise.resolve();
  }

  // ---- no-spoiler mode (41): scores blurred until tapped
  var sp = $("#spoil");
  function spoilSet(on){ document.body.classList.toggle("nospoil", on); if (sp) sp.setAttribute("aria-pressed", on); try { localStorage.setItem("tifo.nospoil", on ? "1" : ""); } catch (e){} }
  try { spoilSet(localStorage.getItem("tifo.nospoil") === "1"); } catch (e){}
  if (sp) sp.onclick = function(){ spoilSet(!document.body.classList.contains("nospoil")); };
  document.addEventListener("click", function(e){ if (!document.body.classList.contains("nospoil")) return; var t = e.target.closest(".chip,.board .dg"); if (t && !t.classList.contains("shown")){ e.preventDefault(); t.classList.add("shown"); } }, true);

  // distance from your emirate (45): remembered choice, rough driving time at ~90 km/h
  function dist(){ var em = "dubai"; try { em = localStorage.getItem("tifo.emirate") || "dubai"; } catch (e){}
    document.querySelectorAll(".dist").forEach(function(d){ var km = JSON.parse(d.dataset.km || "{}"), sel = d.querySelector("select"); if (!sel) return; sel.value = em;
      var paint = function(){ var k = km[sel.value];
        document.querySelectorAll(".leave[data-kick]").forEach(function(l){ if (k == null){ l.textContent = "—"; return; } var t = Date.parse(l.dataset.kick) - (Math.round(k / 90 * 60) + 45) * 6e4; l.textContent = R.hhmm(new Date(t).toISOString()); }); d.querySelector(".dk").textContent = k != null ? Math.round(k) : "—"; d.querySelector(".dt").textContent = k != null ? "حوالي " + Math.max(5, Math.round(k / 90 * 60 / 5) * 5) + " دقيقة سواقة" : ""; };
      sel.onchange = function(){ try { localStorage.setItem("tifo.emirate", sel.value); } catch (e){} em = sel.value; dist(); }; paint(); }); }
  // copy buttons (thread posts, press sheet)
  document.addEventListener("click", function(e){ var b = e.target.closest("[data-copy],[data-copy-from]"); if (!b) return; var t = b.dataset.copy || ((document.querySelector(b.dataset.copyFrom) || {}).innerText || "");
    (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(function(){ var o = b.textContent; b.textContent = "انسخ ✓"; setTimeout(function(){ b.textContent = o; }, 1500); }, function(){}); });
  // «اسأل تيفو» (76)
  var af = $("#askf"); if (af) af.onsubmit = function(e){ e.preventDefault(); var q = $("#askq").value.trim(); if (q.length < 4) return; set("#aska", '<p class="muted">لحظة…</p>');
    fetch("/api/tifo/ask", { method:"POST", headers:{ "content-type":"application/json" }, body:JSON.stringify({ q:q }) }).then(function(r){ return r.json().then(function(j){ return { ok:r.ok, j:j }; }); })
      .then(function(x){ set("#aska", x.ok ? '<div class="ai"><p>' + R.esc(x.j.answer) + "</p></div>" : '<p class="note">' + R.esc((x.j && (x.j.error || x.j.message)) || "ما قدرنا نجاوب الحين") + "</p>"); })
      .catch(function(){ set("#aska", '<p class="note">ما قدرنا نجاوب الحين، جرّب بعد شوي.</p>'); }); };
  // commentator mode (177): the press sheet full screen, big type, the live score on top, facts cycling every 8 s
  document.addEventListener("click", function(e){ var b = e.target.closest("#commbtn"); if (!b) return; var p = $(".press"); if (!p) return;
    var on = !document.body.classList.contains("comm"); document.body.classList.toggle("comm", on); b.textContent = on ? "سكّر وضع المعلّق" : "وضع المعلّق";
    clearInterval(window._commT); if (!on) return; var lis = p.querySelectorAll("li"), i = 0; lis.forEach(function(l){ l.classList.remove("hot1"); });
    window._commT = setInterval(function(){ lis.forEach(function(l){ l.classList.remove("hot1"); }); if (lis[i]) { lis[i].classList.add("hot1"); lis[i].scrollIntoView({ block:"center", behavior:"smooth" }); } i = (i + 1) % lis.length; }, 8000); });
  // service worker (202)
  /* v3 preview: no service worker */
  // «بس مباريات العرب» (234)
  function arabOnly(){ try { return localStorage.getItem("tifo.arab") === "1"; } catch (e){ return false; } }
  var ab = $("#arabonly"); if (ab){ ab.setAttribute("aria-pressed", arabOnly()); ab.onclick = function(){ try { localStorage.setItem("tifo.arab", arabOnly() ? "" : "1"); } catch (e){} ab.setAttribute("aria-pressed", arabOnly()); home(); }; }
  // second screen (223): only the scoreboard, the match line and the numbers, big, screen kept awake
  var sb2 = $("#secondbtn"), wl = null;
  if (sb2) sb2.onclick = function(){ var on = !document.body.classList.contains("second"); document.body.classList.toggle("second", on); sb2.textContent = on ? "سكّر الشاشة الثانية" : "الشاشة الثانية";
    if (on && navigator.wakeLock) navigator.wakeLock.request("screen").then(function(l){ wl = l; }).catch(function(){}); else if (wl){ wl.release(); wl = null; } };
  /* v3: per-section share buttons replaced by the page sheet's «صورة لأي قسم» (next.js) */
  // 235 round story: the table re-sorts as each result lands (FLIP via --i row index)
  (function(){ var d = $("#storydata"); if (!d) return; var snaps = JSON.parse(d.textContent), rows = {}; document.querySelectorAll(".stbl li").forEach(function(li){ rows[li.dataset.t] = li; });
    function show(k){ (snaps[k] || []).forEach(function(x, i){ var li = rows[x[0]]; if (!li) return; li.style.setProperty("--i", i); li.querySelector(".rk").textContent = i + 1; li.querySelector(".pt").textContent = x[1]; li.classList.toggle("moved", k > 0 && snaps[k - 1] && snaps[k - 1].findIndex(function(y){ return y[0] === x[0]; }) !== i); }); }
    if ("IntersectionObserver" in window){ var io = new IntersectionObserver(function(es){ es.forEach(function(e){ if (e.isIntersecting){ document.querySelectorAll(".step.on").forEach(function(s){ s.classList.remove("on"); }); e.target.classList.add("on"); show(+e.target.dataset.s); } }); }, { rootMargin:"-45% 0px -45% 0px" }); document.querySelectorAll(".step").forEach(function(s){ io.observe(s); }); } else show(snaps.length - 1); })();
  // 204/205: where to watch in the visitor's country (research/broadcast_by_country.json); UAE list with a note when missing
  var BCD = null; function bcData(){ return BCD ? Promise.resolve(BCD) : fetch("/next/assets/bc." + B.dataset.bc + ".json").then(function(r){ return r.json(); }).then(function(x){ BCD = x; return x; }).catch(function(){ return {}; }); }
  function freeIn(comp){ var c = country(); return BCD && BCD[c] && BCD[c][comp] && BCD[c][comp].b.some(function(b){ return b[1]; }); }
  (function(){ var box = $("#wwbox"); if (!box) return; var c = country(); if (c === "AE" || c === "xx") return;
    bcData().then(function(d){ var row = R.COUNTRIES.filter(function(x){ return x[0] === c; })[0], e = d[c] && d[c][box.dataset.comp]; if (!e || !e.b.length) { var n = box.querySelector("h2"); if (n) n.insertAdjacentHTML("afterend", '<p class="note">ما لقينا معلومة مؤكدة لـ' + (row ? row[1] : "بلدك") + '، وهذي القنوات في الإمارات.</p>'); return; }
      box.innerHTML = '<section class="blk"><h2>وين تنقل في ' + (row ? row[1] : "بلدك") + '</h2><ul class="bc">' + e.b.map(function(b){ return "<li><b>" + R.esc(b[0]) + "</b>" + (b[1] ? ' <span class="ok">مجاني</span>' : "") + (b[2] ? ' <span class="num">' + b[2] + "</span> " + R.esc(b[3] || "") : "") + (b[4] ? ' <a class="src" href="' + R.esc(b[4]) + '" rel="noopener">المصدر</a>' : "") + "</li>"; }).join("") + "</ul>" + (e.q && e.q !== "high" ? '<p class="src">ثقة المعلومة: ' + (e.q === "medium" ? "متوسطة" : "قليلة") + "، تأكد من القناة قبل المباراة.</p>" : "") + "</section>"; }); })();
  function freeOnly(){ try { return localStorage.getItem("tifo.free") === "1"; } catch (e){ return false; } }
  var fb = $("#freeonly"); if (fb){ fb.setAttribute("aria-pressed", freeOnly()); fb.onclick = function(){ try { localStorage.setItem("tifo.free", freeOnly() ? "" : "1"); } catch (e){} fb.setAttribute("aria-pressed", freeOnly()); bcData().then(function(){ home(); }); }; if (freeOnly()) bcData(); }
  // 291: the coming round's odds as one image
  var rpb = $("#rpbtn"); if (rpb) rpb.onclick = function(){ var d = JSON.parse($("#rpreds").textContent); window.TifoShare.listCard("توقعات تيفو للجولة " + d[0].r, (document.querySelector("h1") || {}).textContent || "", d.map(function(m){ return { h:m.h, a:m.a, home:m.home, away:m.away, mid:Math.round(m.p[0] * 100) + "%   " + Math.round(m.p[1] * 100) + "%   " + Math.round(m.p[2] * 100) + "%", low:"فوز      تعادل      فوز" }; }), "tifo-round-odds.png"); };
  // 314: the week in the visitor's time zone, with their country's channel when known
  var wkb = $("#wkbtn"); if (wkb) wkb.onclick = function(){ var d = JSON.parse($("#wkdata").textContent), c = country(), row = R.COUNTRIES.filter(function(x){ return x[0] === c; })[0];
    bcData().then(function(bc){ window.TifoShare.listCard("مباريات الأسبوع", "بتوقيت " + (row ? row[1] : "بلدك"), d.map(function(m){ var e = bc[c] && bc[c][String(m.comp)], ch = e && e.b[0] ? e.b[0][0] : ""; return { h:m.h, a:m.a, home:m.home, away:m.away, mid:R.hhmm(m.ko), low:R.dayParts(R.ymd(m.ko)).date + (ch ? "، " + ch : "") }; }), "tifo-week.png"); }); };
  // 313: kickoff time and channel in every Arab country
  (function(){ var k = $("#kitct"); if (!k) return; var ko = k.dataset.ko, comp = k.dataset.comp, keep = R.TZ;
    bcData().then(function(bc){ var rows = R.COUNTRIES.map(function(c){ R.TZ = c[2]; var t = R.hhmm(ko), d = R.dayParts(R.ymd(ko)).short, e = bc[c[0]] && bc[c[0]][comp]; return "<tr><td>" + c[1] + '</td><td class="num">' + t + '</td><td class="small">' + d + "</td><td>" + (e && e.b.length ? e.b.map(function(b){ return R.esc(b[0]) + (b[1] ? " (مجاني)" : ""); }).join("، ") : '<span class="muted">غير معروف</span>') + "</td></tr>"; }).join(""); R.TZ = keep;
      k.innerHTML = '<div class="tblwrap"><table class="st"><thead><tr><th style="text-align:start">الدولة</th><th>الساعة</th><th>اليوم</th><th style="text-align:start">القناة</th></tr></thead><tbody>' + rows + '</tbody></table></div><button type="button" class="btn copy" data-copy-from="#kitct">انسخ الجدول</button>'; }); })();
  // 315: coach compare
  (function(){ var a = $("#ca"), b = $("#cb"); if (!a || !b) return; fetch("/assets/coaches.json").then(function(r){ return r.json(); }).then(function(C){
    var ids = Object.keys(C).sort(function(x, y){ return C[y].r.length - C[x].r.length; }), opts = ids.map(function(id){ return '<option value="' + id + '">' + R.esc(C[id].n) + "</option>"; }).join(""); a.innerHTML = b.innerHTML = opts; a.value = ids[0]; b.value = ids[1];
    try { var q = new URLSearchParams(location.search); if (q.get("a") && C[q.get("a")]) a.value = q.get("a"); } catch (e){}
    function tot(id){ var t = { g:0, w:0, d:0, l:0, s:{}, c:{} }; C[id].r.forEach(function(r){ t.w += r[3]; t.d += r[4]; t.l += r[5]; t.s[r[0]] = 1; t.c[r[2]] = 1; }); t.g = t.w + t.d + t.l; t.ppg = t.g ? (3 * t.w + t.d) / t.g : 0; return t; }
    function line(l, x, y, dir, f){ var w = x === y ? 0 : (x > y) === (dir > 0) ? 1 : 2; return '<div class="cmpt"><b class="' + (w === 1 ? "w" : "") + '">' + f(x) + "</b><span>" + l + '</span><b class="' + (w === 2 ? "w" : "") + '">' + f(y) + "</b></div>"; }
    function draw(){ var x = tot(a.value), y = tot(b.value), i = function(v){ return v; }, f2 = function(v){ return v.toFixed(2); };
      $("#cout").innerHTML = line("مباريات", x.g, y.g, 1, i) + line("فوز", x.w, y.w, 1, i) + line("تعادل", x.d, y.d, 0, i) + line("خسارة", x.l, y.l, -1, i) + line("نقاط بالمباراة", x.ppg, y.ppg, 1, f2) + line("مواسم", Object.keys(x.s).length, Object.keys(y.s).length, 1, i) + '<p class="small">' + R.esc(C[a.value].n) + ": " + R.esc(Object.keys(x.c).join("، ")) + '</p><p class="small">' + R.esc(C[b.value].n) + ": " + R.esc(Object.keys(y.c).join("، ")) + "</p>"; }
    a.onchange = b.onchange = draw; draw(); }); })();
  // 292: since your last visit, for your favourite clubs
  (function(){ var el = $("#since"); if (!el) return; var last = 0; try { last = +localStorage.getItem("tifo.lastvisit") || 0; localStorage.setItem("tifo.lastvisit", Date.now()); } catch (e){}
    var teams = favs().filter(function(x){ return x.t === "team"; }); if (!last || !teams.length || Date.now() - last < 3 * 3600e3) return;
    Promise.all(teams.slice(0, 6).map(function(x){ return fetch("/tn/" + x.id + ".json").then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; }); })).then(function(rs){
      var lines = []; rs.forEach(function(t){ if (!t) return; (t.recent || []).filter(function(m){ return m && m.score && Date.parse(m.kickoff_utc) > last; }).forEach(function(m){ var h = m.home.id === t.id, a = h ? m.score.home : m.score.away, b = h ? m.score.away : m.score.home, o = h ? m.away : m.home; lines.push('<li><a href="/m/' + m.id + '/">' + R.tname(t) + " " + (a > b ? "فاز على" : a === b ? "تعادل مع" : "خسر من") + " " + R.tname(o) + ' <b class="num">' + a + " - " + b + "</b></a></li>"); });
        var prev = null; try { prev = JSON.parse(localStorage.getItem("tifo.rank." + t.id) || "null"); } catch (e){} if (t.table){ if (prev && prev.rank !== t.table.rank) lines.push("<li>" + R.tname(t) + " " + (t.table.rank < prev.rank ? "طلع" : "نزل") + " من المركز " + prev.rank + " للمركز " + t.table.rank + " في " + R.esc(t.table.comp_ar) + "</li>"); try { localStorage.setItem("tifo.rank." + t.id, JSON.stringify(t.table)); } catch (e){} } });
      if (lines.length) el.innerHTML = '<section class="blk"><h2>من آخر زيارة لك</h2><ul class="facts-l">' + lines.join("") + "</ul></section>"; }); })();
  // 293: a toast when a favourite club scores while any page is open (skipped in no-spoiler mode)
  (function(){ var teams = favs().filter(function(x){ return x.t === "team"; }).map(function(x){ return x.id; }); if (!teams.length) return; var seen = {};
    function check(){ if (document.hidden) return; fetch("/v1/live.json", { cache:"no-cache" }).then(function(r){ return r.json(); }).then(function(l){ (l.matches || []).forEach(function(m){ [["home", m.home], ["away", m.away]].forEach(function(x){ if (teams.indexOf(x[1].id) < 0 || !m.score) return; var k = m.id + x[0], g = m.score[x[0]]; if (seen[k] != null && g > seen[k] && !document.body.classList.contains("nospoil")) toast("⚽ هدف لـ" + R.tname(x[1]) + "! " + m.score.home + " - " + m.score.away, "/m/" + m.id + "/"); seen[k] = g; }); }); }).catch(function(){}); }
    function toast(t, href){ var d = document.createElement("a"); d.className = "toast"; d.href = href; d.textContent = t; document.body.appendChild(d); setTimeout(function(){ d.remove(); }, 9000); }
    check(); setInterval(check, 30000); })();
  // 294: optional club colours from the first favourite
  function theme(){ var on = false; try { on = localStorage.getItem("tifo.theme") === "1"; } catch (e){} var f = favs().filter(function(x){ return x.t === "team"; })[0], c = f && (window.TC || {})[f.id];
    var st = document.documentElement.style; if (on && c){ var h = c[0], n = parseInt(h.slice(1), 16), l = (0.299 * (n >> 16 & 255) + 0.587 * (n >> 8 & 255) + 0.114 * (n & 255)) / 255; st.setProperty("--dune", l > 0.7 ? "#6E4000" : h); st.setProperty("--dune-soft", h + "26"); document.body.classList.add("clubtheme"); document.body.style.setProperty("--club2", c[1] || h); } else { st.removeProperty("--dune"); st.removeProperty("--dune-soft"); document.body.classList.remove("clubtheme"); } }
  theme(); document.addEventListener("click", function(e){ if (!e.target.closest("#themebtn")) return; try { localStorage.setItem("tifo.theme", localStorage.getItem("tifo.theme") === "1" ? "" : "1"); } catch (x){} theme(); });
  // 184 newsletter: form anywhere with .nlform; confirm/unsubscribe results via ?ok= / ?bye=
  (function(){ var m = $("#nlmsg"), q = null; try { q = new URLSearchParams(location.search); } catch (e){}
    if (m && q){ if (q.has("ok")) m.innerHTML = '<p class="note">' + (q.get("ok") === "1" ? "تم اشتراكك، النشرة توصلك كل خميس." : "الرابط مب صحيح أو انتهى.") + "</p>"; if (q.has("bye")) m.innerHTML = '<p class="note">' + (q.get("bye") === "1" ? "انلغى اشتراكك." : "الرابط مب صحيح.") + "</p>"; }
    document.querySelectorAll(".nlform").forEach(function(f){ f.onsubmit = function(e){ e.preventDefault(); var em = f.querySelector("input[type=email]").value.trim(), out = f.previousElementSibling && f.previousElementSibling.id === "nlmsg" ? f.previousElementSibling : null;
      var say = function(t){ if (out) out.innerHTML = '<p class="note">' + R.esc(t) + "</p>"; else alert(t); };
      fetch("/api/tifo/subscribe", { method:"POST", headers:{ "content-type":"application/json" }, body:JSON.stringify({ email:em, country:country() }) }).then(function(r){ return r.json().then(function(j){ return { ok:r.ok, j:j }; }); })
        .then(function(x){ if (x.ok) say(x.j.already ? "أنت مشترك من قبل." : "وصلك إيميل تأكيد، افتحه واضغط الزر."); else say((x.j && (x.j.error || x.j.message)) || "صار خطأ، جرّب مرة ثانية."); }).catch(function(){ say("صار خطأ، جرّب مرة ثانية."); }); }; }); })();
  // 333 watch mode: the favourite club's live or next match, big
  (function(){ var box = $("#wbox"); if (!box) return; var t = favs().filter(function(x){ return x.t === "team"; })[0]; if (!t) return;
    function tick(){ Promise.all([fetch("/tn/" + t.id + ".json").then(function(r){ return r.json(); }), fetch("/v1/live.json", { cache:"no-cache" }).then(function(r){ return r.json(); }).catch(function(){ return { matches:[] }; })]).then(function(r){ var tn = r[0], lv = (r[1].matches || []).filter(function(m){ return m.home.id === t.id || m.away.id === t.id; })[0], m = lv || tn.next || tn.last; if (!m) return;
      box.innerHTML = '<a href="/m/' + m.id + '/" class="wb"><span class="wt">' + R.tname(m.home) + '</span><span class="ws2 num">' + (m.score ? m.score.home + " - " + m.score.away : R.hhmm(m.kickoff_uae)) + '</span><span class="wt">' + R.tname(m.away) + '</span><span class="wst">' + (R.isLive(m) ? R.minute(m) : m.score ? "انتهت" : R.dayLabel(R.ymd(m.kickoff_uae))) + "</span></a>"; }); }
    tick(); setInterval(tick, 20000); })();
  // 332 car mode: speak favourite clubs' goals, kickoffs and full-times (speechSynthesis, Arabic voice)
  (function(){ var b = $("#carbtn"); if (!b || !window.speechSynthesis) { if (b) b.hidden = true; return; } var on = false, T = null, seen = {};
    function say(t){ var u = new SpeechSynthesisUtterance(t); u.lang = "ar-AE"; var v = speechSynthesis.getVoices().filter(function(v){ return /^ar/i.test(v.lang); })[0]; if (v) u.voice = v; speechSynthesis.speak(u); }
    function poll(){ var ids = favs().filter(function(x){ return x.t === "team"; }).map(function(x){ return x.id; }); fetch("/v1/live.json", { cache:"no-cache" }).then(function(r){ return r.json(); }).then(function(l){ (l.matches || []).forEach(function(m){ if (ids.indexOf(m.home.id) < 0 && ids.indexOf(m.away.id) < 0) return; var k = m.id, prev = seen[k], H = R.tname(m.home), A = R.tname(m.away), sc = m.score ? m.score.home + " " + m.score.away : "";
      if (!prev) { if (on && m.minute && parseInt(m.minute, 10) < 3) say("بدت مباراة " + H + " و" + A); } else { if (m.score && prev.score && (m.score.home !== prev.score.home || m.score.away !== prev.score.away)) say("هدف! " + H + " " + m.score.home + "، " + A + " " + m.score.away); }
      seen[k] = m; }); Object.keys(seen).forEach(function(k){ if (!(l.matches || []).some(function(m){ return String(m.id) === k; })){ var m = seen[k]; if (m.score) say("خلصت: " + R.tname(m.home) + " " + m.score.home + "، " + R.tname(m.away) + " " + m.score.away); delete seen[k]; } }); }).catch(function(){}); }
    b.onclick = function(){ on = !on; b.setAttribute("aria-pressed", on); b.textContent = on ? "وضع السيارة شغال" : "وضع السيارة"; clearInterval(T); if (on){ say("وضع السيارة شغال. بقولك الأهداف أول بأول"); poll(); T = setInterval(poll, 20000); } }; })();
  // 334 voice search + 174 voice ask: webkitSpeechRecognition ar-AE (hidden when unsupported)
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  function listen(input, done){ var r = new SR(); r.lang = "ar-AE"; r.interimResults = false; r.onresult = function(e){ input.value = e.results[0][0].transcript; input.dispatchEvent(new Event("input")); if (done) done(); }; r.start(); }
  document.addEventListener("click", function(e){ if (e.target.id === "srch" && SR) setTimeout(function(){ var q = $("#sq"); if (q && !$("#sqmic")){ var m = document.createElement("button"); m.type = "button"; m.id = "sqmic"; m.className = "btn copy"; m.textContent = "🎤 تكلّم"; m.onclick = function(){ listen(q); }; q.insertAdjacentElement("afterend", m); } }, 50); });
  (function(){ var f = $("#askf"); if (!f) return; var q = $("#askq");
    if (SR){ var m = document.createElement("button"); m.type = "button"; m.className = "btn"; m.textContent = "🎤"; m.setAttribute("aria-label", "اسأل بصوتك"); m.onclick = function(){ listen(q, function(){ f.requestSubmit ? f.requestSubmit() : f.onsubmit(new Event("submit")); }); }; f.appendChild(m); }
    new MutationObserver(function(){ var a = $("#aska .ai p"); if (!a || $("#aska .listen")) return; var b = document.createElement("button"); b.type = "button"; b.className = "btn copy listen"; b.textContent = "اسمع الجواب"; b.onclick = function(){ b.disabled = true;
      fetch("/api/tifo/tts", { method:"POST", headers:{ "content-type":"application/json" }, body:JSON.stringify({ lang:"ar", voice:"f", paras:[a.textContent] }) }).then(function(r){ return r.json(); }).then(function(j){ if (j.mp3) new Audio("data:audio/mpeg;base64," + j.mp3).play(); b.disabled = false; }).catch(function(){ b.disabled = false; }); };
      a.parentNode.appendChild(b); }).observe($("#aska"), { childList:true, subtree:true }); })();
  // 189 replay slider
  (function(){ var r = $("#rpr"); if (!r) return; var ev = JSON.parse($("#rpev").textContent), IC = { goal:"⚽", penalty_goal:"⚽", own_goal:"⚽", yellow:"🟨", red:"🟥", second_yellow:"🟥" };
    function draw(){ var t = +r.value, sc = [0, 0]; $("#rpm").textContent = t; var list = ev.filter(function(e){ return e[0] <= t; }); list.forEach(function(e){ if (e[4]) sc = e[4]; }); $("#rps").textContent = sc[0] + " - " + sc[1]; $("#rpe").innerHTML = list.slice().reverse().map(function(e){ return "<li>" + Math.floor(e[0]) + "' " + (IC[e[1]] || "") + ' <span class="lat">' + R.esc(e[3] || "") + "</span></li>"; }).join(""); }
    r.oninput = draw; draw(); })();
  // 230 countdown timers
  (function(){ var els = document.querySelectorAll(".cdt[data-u]"); if (!els.length) return; function tick(){ els.forEach(function(el){ var d = Math.max(0, Date.parse(el.dataset.u) - Date.now()), dd = Math.floor(d / 864e5), hh = Math.floor(d / 36e5) % 24, mm = Math.floor(d / 6e4) % 60; el.textContent = (dd ? dd + " يوم " : "") + (hh < 10 ? "0" : "") + hh + ":" + (mm < 10 ? "0" : "") + mm; }); } tick(); setInterval(tick, 30000); })();
  // Arab pages (build_arabs.cjs): country filters, nations head-to-head, TV guide, results archive, birthdays and club anniversaries
  [["#abf", "tr[data-c]"], ["#trf", "li[data-c]"]].forEach(function(x){ var s = $(x[0]); if (!s) return; s.onchange = function(){ document.querySelectorAll(x[1]).forEach(function(r){ r.hidden = !!s.value && r.dataset.c !== s.value; }); }; });
  (function(){ var a = $("#nha"), b = $("#nhb"), d = $("#nhdata"); if (!a || !d) return; var D = JSON.parse(d.textContent), c = country();
    a.value = D.n[c] ? c : "AE"; b.value = a.value === "SA" ? "AE" : "SA";
    function show(){ var x = D.m[a.value] && D.m[a.value][b.value], A = D.n[a.value], Bn = D.n[b.value], o = $("#nhout");
      if (a.value === b.value){ o.innerHTML = '<p class="empty">اختار منتخبين مختلفين.</p>'; return; }
      if (!x){ o.innerHTML = '<p class="empty">ما تقابل ' + A + " و" + Bn + " في بياناتنا.</p>"; return; }
      o.innerHTML = '<div class="h2hsum"><div><b>' + x.w + "</b>فوز " + A + "</div><div><b>" + x.d + "</b>تعادل</div><div><b>" + x.l + "</b>فوز " + Bn + '</div></div><p>تقابلوا <b class="num">' + x.p + '</b> مرة، والأهداف <bdi dir="ltr" class="num">' + x.gf + "-" + x.ga + "</bdi> لـ" + A + (x.last ? '. آخر مواجهة <span class="num">' + x.last + "</span>" : "") + '.</p><p class="tools"><a class="btn" href="/national/' + a.value.toLowerCase() + '/">منتخب ' + A + '</a><a class="btn" href="/national/' + b.value.toLowerCase() + '/">منتخب ' + Bn + "</a></p>"; }
    a.onchange = b.onchange = show; show(); })();
  (function(){ var s = $("#gsel"), box = $("#guide"), fr = $("#gfree"); if (!s || !box) return;
    function free(){ box.querySelectorAll(".gm").forEach(function(g){ g.hidden = fr.checked && !g.querySelector(".free"); }); }
    function load(c){ box.innerHTML = '<p class="empty">نحمّل…</p>'; get("guide/" + c + ".json").then(function(g){ box.innerHTML = R.guide(g); R.localize(box); free(); }).catch(function(){ box.innerHTML = '<p class="empty">ما عندنا دليل لهالدولة للحين.</p>'; }); }
    var c = country(); if (c !== "xx" && c !== "AE" && R.COUNTRIES.some(function(x){ return x[0] === c; })){ s.value = c; load(c); } else R.localize(box);
    s.onchange = function(){ load(s.value); }; fr.onchange = free; })();
  (function(){ var s = $("#exs"), cs = $("#exc"), q = $("#ext"), out = $("#exout"); if (!s || !out) return; var CN = JSON.parse($("#excomps").textContent), T = null, cur = null;
    function nm(id){ var t = T && T[id]; return t ? (t.name_ar || t.name || "") : ""; }
    function draw(){ if (!cur) return; var c = cs.value, w = q.value.trim().toLowerCase(), rows = cur.matches.filter(function(m){ return (!c || String(m[2]) === c) && (!w || [m[3], m[4]].some(function(id){ var t = T && T[id]; return t && ((t.name_ar || "").indexOf(w) >= 0 || (t.name || "").toLowerCase().indexOf(w) >= 0); })); }).slice().reverse();
      out.innerHTML = rows.length ? '<p class="muted small">' + rows.length + " مباراة" + (rows.length > 300 ? "، نعرض أحدث 300" : "") + '</p><ul class="exl">' + rows.slice(0, 300).map(function(m){ var hw = m[5] > m[6], aw = m[6] > m[5]; return '<li><span class="muted small num">' + m[1] + '</span><span class="' + (hw ? "win" : "") + '">' + R.esc(nm(m[3])) + '</span><bdi dir="ltr" class="num sc">' + m[5] + "-" + m[6] + '</bdi><span class="' + (aw ? "win" : "") + '">' + R.esc(nm(m[4])) + '</span><span class="muted small">' + R.esc(CN[m[2]] || "") + "</span></li>"; }).join("") + "</ul>" : '<p class="empty">ما في نتايج بهالبحث.</p>'; }
    function load(){ out.innerHTML = '<p class="empty">نحمّل…</p>'; Promise.all([T ? Promise.resolve(T) : get("teams.json").then(function(t){ T = t.teams || {}; return T; }), get("archive/all/" + s.value + ".json")]).then(function(r){ cur = r[1]; var ids = {}; cur.matches.forEach(function(m){ ids[m[2]] = 1; }); var v = cs.value; cs.innerHTML = '<option value="">كل البطولات</option>' + Object.keys(ids).filter(function(k){ return CN[k]; }).map(function(k){ return '<option value="' + k + '">' + R.esc(CN[k]) + "</option>"; }).join(""); cs.value = ids[v] ? v : ""; draw(); }).catch(function(){ out.innerHTML = '<p class="empty">ما قدرنا نحمّل هالموسم.</p>'; }); }
    s.onchange = load; cs.onchange = draw; q.oninput = draw; load(); })();
  (function(){ var el = $("#bdays"); if (!el) return; var md = R.ymd(new Date().toISOString()).slice(5), yr = +R.ymd(new Date().toISOString()).slice(0, 4), items = [];
    try { var an = JSON.parse(el.dataset.an || "{}")[md] || []; an.forEach(function(a){ items.push("<li>ذكرى تأسيس " + '<a href="/t/' + a[0] + '/">' + R.esc(a[1]) + '</a> <span class="muted">(' + (yr - a[2]) + " سنة، من " + a[2] + ")</span></li>"); }); } catch (e){}
    function draw(){ if (items.length) el.innerHTML = '<section class="blk"><h2>اليوم في التقويم</h2><ul class="facts-l">' + items.join("") + "</ul></section>"; }
    get("players/birthdays/" + md + ".json").then(function(b){ (b.players || []).slice(0, 8).forEach(function(p){ var age = p.dob ? yr - +p.dob.slice(0, 4) : null; items.push("<li>عيد ميلاد " + (p.name_ar ? R.esc(p.name_ar) : '<span class="lat">' + R.esc(p.name) + "</span>") + (age ? ' <span class="muted">(' + age + " سنة)</span>" : "") + "</li>"); }); draw(); }).catch(draw); })();
  function run(){ var f = { home:home, comp:comp, match:match, team:team, tv:tv, studio:studio }[PAGE]; if (f) f().catch(function(){}); if (PAGE === "team" && ID === "5789") countdown(); }
  tvFull();
  tabs(); run(); dist();
})();

;
/* تيفو v3 shell (redesign/DESIGN-v3.md): the bar, the two sheets (شارك وأدوات، المزيد), the reader panel for shelf tiles
   (templated sections stamped on first open), deep links, home rails refreshed from app.js's own poll ("tifo:day"),
   the match mini-bar ("tifo:match"), key art, parallax, rail arrows. Runs after app.js; it never re-fetches data. */
(function(){
  "use strict";
  var R = window.TR, B = document.body, PAGE = B.dataset.page, RM = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function(s, r){ return (r || document).querySelector(s); }, $$ = function(s, r){ return [].slice.call((r || document).querySelectorAll(s)); };
  if (window.PN && R.setNames) R.setNames(window.PN);

  // ---- top bar: transparent over the hero, solid once the page moves
  var top = $(".top"); function onScroll(){ if (top) top.classList.toggle("solid", window.scrollY > 40); }
  onScroll();

  // ---- sheets + panel: one open at a time, Esc / scrim / close button, focus returns to the opener
  var opener = null, scrim = $("#scrimall");
  function closeAll(){ $$(".sheet:not([hidden]),.panel:not([hidden])").forEach(function(s){ s.hidden = true; if (s.id === "panel") unpanel(); }); scrim.hidden = true; B.classList.remove("locked"); if (opener && opener.focus) opener.focus(); opener = null; }
  function open(el, from){ closeAll(); opener = from || document.activeElement; el.hidden = false; scrim.hidden = false; B.classList.add("locked"); var f = el.querySelector("button,a,[tabindex]"); if (f) setTimeout(function(){ f.focus({ preventScroll:true }); }, 30); }
  document.addEventListener("click", function(e){
    var t = e.target.closest("[data-sheet]"); if (t){ e.preventDefault(); open($("#" + t.dataset.sheet), t); return; }
    if (e.target.closest("[data-close]") || e.target === scrim || (e.target.classList && (e.target.classList.contains("sheet") || e.target.classList.contains("panel")))) { closeAll(); return; }
    var o = e.target.closest("[data-open]"); if (o){ panel(o.dataset.open, o); return; }
    var g = e.target.closest("[data-go]"); if (g){ e.preventDefault(); goTab(g.dataset.go); return; }
    // settings buttons inside المزيد open their own boxes (app.js): close the sheet first
    if (e.target.closest("#more #ctry, #srch")) { $$(".sheet:not([hidden])").forEach(function(s){ s.hidden = true; }); scrim.hidden = true; B.classList.remove("locked"); }
    // client-rendered links to a prototype page stay inside /next/
    var a = e.target.closest("a[href^='/']"); if (a && R.PROTO && R.PROTO[a.getAttribute("href")]) { e.preventDefault(); location.href = "/next" + a.getAttribute("href"); }
  }, true);
  document.addEventListener("keydown", function(e){ if (e.key === "Escape") closeAll(); });

  // ---- reader panel: a shelf tile's section, stamped from its <template> once, moved back on close
  var cur = null;
  function node(key){ var v = document.getElementById("v-" + key); if (!v) return null;
    if (v.tagName === "TEMPLATE"){ var d = document.createElement("div"); d.className = "vault"; d.id = v.id; d.hidden = true; d.appendChild(v.content.cloneNode(true)); v.parentNode.replaceChild(d, v); R.localize(d); v = d; }
    return v; }
  function panel(key, from){
    var v = node(key); if (!v) return; var body = v.querySelector(".pbody") || $("#panelb .pbody"); if (!body) return;
    var pn = $("#panel"); open(pn, from); cur = { key:key, vault:v, body:body };
    var h2 = body.querySelector("h2"); $("#panelt").textContent = body.dataset.title || (h2 ? h2.firstChild.textContent : "");
    var sm = h2 && h2.querySelector("small"); $("#panels").innerHTML = sm ? sm.innerHTML : "";
    $("#panelb").appendChild(body); $("#panelb").scrollTop = 0;
    if (from && from.dataset.anchor) try { history.replaceState(null, "", "#" + from.dataset.anchor); } catch (e){}
  }
  function unpanel(){ if (cur){ cur.vault.appendChild(cur.body); cur = null; } }

  // ---- tabs: deep links (#num, #n-cards, old #goals/#assists), data-go buttons
  function goTab(k){ var b = $('.mtabs button[data-t="' + k + '"]'); if (b){ b.click(); var bar = $(".mtabs"); if (bar) window.scrollTo({ top:bar.getBoundingClientRect().top + window.scrollY - 60, behavior:RM ? "auto" : "smooth" }); } }
  (function deep(){
    var h = decodeURIComponent(location.hash.slice(1)); if (!h) return;
    var alias = { goals:["num", "goals"], assists:["num", "assists"] }[h];
    if (alias){ goTab(alias[0]); var s = $('.seg button[data-t="' + alias[1] + '"]'); if (s) s.click(); return; }
    var t = $('[data-anchor="' + h + '"]'); if (t){ var p = t.closest("[data-pane]"); if (p) goTab(p.dataset.pane); setTimeout(function(){ panel(t.dataset.open, t); }, 60); }
  })();

  // ---- the share sheet
  var cl = $("#copylink"); if (cl) cl.onclick = function(){ var u = location.href.split("#")[0]; (navigator.clipboard ? navigator.clipboard.writeText(u) : Promise.reject()).then(function(){ cl.textContent = "انتسخ ✓"; setTimeout(function(){ cl.textContent = "انسخ الرابط"; }, 1800); }, function(){ prompt("انسخ الرابط", u); }); };
  var ns = $("#nshare"); if (ns) ns.onclick = function(){ var u = location.href.split("#")[0]; if (navigator.share) navigator.share({ title:document.title, url:u }).catch(function(){}); else if (cl) cl.click(); };
  var sp = $("#secpick"), spl = $("#secpicks");
  if (sp) sp.onclick = function(){
    if (!spl.hidden){ spl.hidden = true; return; }
    var items = $$("[data-open]").map(function(t){ return [t.dataset.open, (t.querySelector(".tt2") || t).textContent.trim()]; });
    $$("[data-pane] section.blk > h2, .daybox > .rail-h h2").forEach(function(h, i){ var s = h.closest("section"); if (!s.closest(".vault")){ s.dataset.pick = "p" + i; items.push(["@p" + i, h.firstChild.textContent.trim()]); } });
    spl.innerHTML = items.length ? items.map(function(x){ return '<button type="button" data-pick="' + x[0] + '">' + R.esc(x[1]) + "</button>"; }).join("") : '<p class="muted small">ما في أقسام في هالصفحة.</p>'; spl.hidden = false;
  };
  if (spl) spl.onclick = function(e){ var b = e.target.closest("button[data-pick]"); if (!b || !window.TifoShare) return; var k = b.dataset.pick, sec;
    if (k.charAt(0) === "@") sec = $('[data-pick="' + k.slice(1) + '"]'); else { var v = node(k); sec = v && v.querySelector("section.blk"); }
    if (!sec) return; var title = b.textContent;
    var lines = $$("li, tbody tr, .th1, .fr, .wt, a.m", sec).slice(0, 8).map(function(e){ return e.textContent.replace(/\s+/g, " ").trim(); }).filter(Boolean);
    if (!lines.length) lines = [sec.textContent.replace(/\s+/g, " ").slice(title.length, title.length + 160)];
    closeAll(); window.TifoShare.card(title, lines); };

  // ---- key art
  var hero = $(".hero"), art = null;
  if (hero && window.TifoArt){
    var cv = hero.querySelector("canvas");
    if (hero.classList.contains("chero") && cv){ try { art = window.TifoArt.mount(cv); art.paint(JSON.parse(hero.dataset.art || "[]"), 11); } catch (e){} }
    if (hero.classList.contains("mhero")){ try { var ms = JSON.parse($("#msum").textContent); art = window.TifoArt.mount(cv); art.set(ms); } catch (e){} }
  }
  // parallax + fade: the art drifts at 0.35x scroll, the title fades as it leaves
  var hin = hero && hero.querySelector(".hero-in"), ticking = false;
  window.addEventListener("scroll", function(){ onScroll(); if (RM || !hero || ticking) return; ticking = true; requestAnimationFrame(function(){ ticking = false; var y = window.scrollY, h = hero.offsetHeight; if (y > h * 1.2) return;
    var c = hero.querySelector("canvas, .lgart, .lgwall"); if (c) c.style.transform = "translate3d(0," + (y * 0.35).toFixed(1) + "px,0)"; if (hin) hin.style.opacity = Math.max(0, 1 - y / (h * 0.85)).toFixed(3); }); }, { passive:true });

  // depth: the league logo leans a few px toward the pointer (desktop only)
  var lg = $(".lglogo"); if (lg && !RM && matchMedia("(pointer:fine)").matches) hero.addEventListener("pointermove", function(e){ var r = hero.getBoundingClientRect(), x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5; lg.style.transform = "translate3d(" + (x * -14).toFixed(1) + "px," + (y * -10).toFixed(1) + "px,0) rotateY(" + (x * 8).toFixed(1) + "deg)"; });
  // ---- match: sticky mini score once the hero leaves; updated from app.js's poll
  var mini = $("#mini");
  function miniDraw(m){ if (!mini || !m) return; var live = R.isLive(m), s = m.score;
    mini.firstElementChild.innerHTML = '<span class="mt">' + R.logo(m.home, "sm") + "<b>" + R.tname(m.home) + '</b></span><span class="ms' + (live ? " live" : "") + '">' + (s ? '<b class="dg">' + s.home + " - " + s.away + "</b>" : '<b class="dg">' + R.tt(m.kickoff_uae) + "</b>") + "<small>" + (live ? R.minute(m) : m.status === "scheduled" ? R.td(m.kickoff_uae) : R.statusText(m)) + '</small></span><span class="mt a"><b>' + R.tname(m.away) + "</b>" + R.logo(m.away, "sm") + '</span><button type="button" class="ib" data-sheet="share" aria-label="شارك"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 8l5-5 5 5M5 13v8h14v-8"/></svg></button>'; R.localize(mini); }
  if (mini){ try { miniDraw(JSON.parse($("#msum").textContent)); } catch (e){}
    if ("IntersectionObserver" in window){ var mh = $("#mh"); new IntersectionObserver(function(es){ var on = !es[0].isIntersecting && es[0].boundingClientRect.top < 0; B.classList.toggle("mini-on", on); mini.setAttribute("aria-hidden", !on); }, { threshold:0 }).observe(mh); } }
  document.addEventListener("tifo:match", function(e){ var md = e.detail; if (R.arNames) R.arNames(md); miniDraw(md); if (art) art.set(md);
    if (md.status !== "scheduled"){ var t = $('.mtabs [data-t="events"]'); if (t) t.textContent = "الأحداث"; var g = $('.hero-acts [data-go="events"]'); if (g){ g.dataset.go = "lineups"; g.href = "#lineups"; g.textContent = "التشكيلة"; } } });

  // ---- home: rails from the same day data app.js just fetched
  document.addEventListener("tifo:day", function(e){
    var d = e.detail; R._idx = d.idx; if (d.off !== 0) return;
    var mine = null; try { mine = +localStorage.getItem("tifo.mine") || null; } catch (x){}
    var all = d.ms, ids = {}; all.forEach(function(m){ ids[m.id] = 1; }); var r = R.homeRails(all.concat(((d.live || {}).matches || []).filter(function(m){ return !ids[m.id]; })), d.idx, { mine:mine });
    [["r-live", r.live], ["r-today", r.today], ["r-arab", r.arab]].forEach(function(x){ var s = document.getElementById(x[0]); if (!s) return; var box = s.querySelector(".rail-s"); if (box.innerHTML !== x[1]){ box.innerHTML = x[1]; R.localize(box); } s.hidden = !x[1]; });
    var f = R.featured(all), go = $("#herogo"); if (f && go){ go.href = (R.PROTO["/m/" + f.id + "/"] ? "/next" : "") + "/m/" + f.id + "/"; }
    setTimeout(function(){ var k = $("#standkick"); if (k && f && mine && (f.home.id === mine || f.away.id === mine) && !R.isLive(f)) k.textContent = "فريقك"; else if (k && f && f.status === "scheduled") k.textContent = "الليلة"; }, 0);
    fold();
  });
  // the day list: 4 competitions, then «كل المباريات»
  var dayEl = $("#day"), unf = $("#unfold");
  function fold(){ if (!dayEl || !unf) return; var n = dayEl.querySelectorAll(".comp-block").length; unf.hidden = n <= 4 || !dayEl.classList.contains("fold"); }
  if (unf) unf.onclick = function(){ dayEl.classList.remove("fold"); fold(); };
  fold();
  // one segmented control for the day filter: الكل · العرب · المجاني في بلدك (app.js owns the two toggles)
  var sa = $("#segall"), ab = $("#arabonly"), fb = $("#freeonly");
  function segSync(){ if (!sa) return; setTimeout(function(){ sa.setAttribute("aria-pressed", !(ab.getAttribute("aria-pressed") === "true" || fb.getAttribute("aria-pressed") === "true")); }, 0); }
  if (sa){
    ab.addEventListener("click", function(){ if (fb.getAttribute("aria-pressed") === "true") fb.click(); }, true);
    fb.addEventListener("click", function(){ if (ab.getAttribute("aria-pressed") === "true") ab.click(); }, true);
    [ab, fb].forEach(function(b){ b.addEventListener("click", segSync); });
    sa.onclick = function(){ if (ab.getAttribute("aria-pressed") === "true") ab.click(); if (fb.getAttribute("aria-pressed") === "true") fb.click(); segSync(); };
    segSync();
  }

  // ---- rails: arrows from 880px (native scroll otherwise); sections fade up once
  $$(".rail-s").forEach(function(s){ var w = document.createElement("div"); w.className = "rail-a"; w.innerHTML = '<button type="button" aria-label="اللي قبل">›</button><button type="button" aria-label="اللي بعد">‹</button>';
    w.onclick = function(e){ var b = e.target.closest("button"); if (!b) return; var dir = b === w.firstChild ? 1 : -1; s.scrollBy({ left:dir * s.clientWidth * 0.85, behavior:RM ? "auto" : "smooth" });   /* RTL: "next" moves left */ };
    s.parentNode.querySelector(".rail-h").appendChild(w); });
  if (!RM && "IntersectionObserver" in window){ var io = new IntersectionObserver(function(es){ es.forEach(function(e){ if (e.isIntersecting){ e.target.classList.add("in"); io.unobserve(e.target); } }); }, { rootMargin:"0px 0px -8% 0px" });
    $$(".rail, .daybox, .shelf3, [data-pane] > section.blk").forEach(function(el){ if (el.getBoundingClientRect().top < window.innerHeight) return; el.classList.add("fx"); io.observe(el); }); }
})();
