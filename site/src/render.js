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
  // W2.3: a club colour that reads on night pitch: c1, mixed toward chalk until it reaches 3:1 against #0A2620 (bands, bars, radar, lineup squares)
  var ON = {}; function lumi(h){ var n = parseInt(h.slice(1, 7), 16), f = function(v){ v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(n >> 16 & 255) + 0.7152 * f(n >> 8 & 255) + 0.0722 * f(n & 255); }
  function mix(h, k){ var n = parseInt(h.slice(1, 7), 16), m = function(v){ return Math.round(v + (246 - v) * k); }; var r = m(n >> 16 & 255), g = m(n >> 8 & 255), b = m(n & 255); return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1); }
  R.colOn = function(id){ if (ON[id]) return ON[id]; var c = R.col(id, 0), L0 = lumi("#0A2620"), k = 0, x = c; while (k <= 1 && (lumi(x) + 0.05) / (L0 + 0.05) < 3){ k += 0.1; x = mix(c, k); } return (ON[id] = x); };
  R.inkOn = function(h){ return lumi(h) > 0.35 ? "#0A2620" : "#F6F7F2"; };
  // W2.11: rows get a 96px webp; hero crests the full png, eager and high priority
  R.logo = function(t, cls){ if (!t || !t.id) return ""; var hero = /\b(lg|xl)\b/.test(cls || ""); return '<img class="logo' + (cls ? " " + cls : "") + '" src="/logo/' + (hero ? t.id + ".png" : "96/" + t.id + ".webp") + '" alt="" ' + (hero ? 'fetchpriority="high"' : 'loading="lazy"') + ' width="24" height="24" onerror="if(!this.dataset.f){this.dataset.f=1;this.src=\'/logo/' + t.id + '.png\'}else this.style.visibility=\'hidden\'">'; };
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
    var mn0 = String(md.minute || "").replace(/'/g, ""), per = R.periodAr ? R.periodAr(md.status === "ht" ? "HT" : mn0) : "";
    lines.push(lead + (R.isLive(md) && (md.minute || md.status === "ht") ? (per ? " (" + per + ")" : " (الدقيقة " + mn0 + ")") : "") + ".");
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
    if (live) return '<span class="chip live"><small>' + R.minute(m) + "</small>" + (m.score ? sc(m.score) : "0 - 0") + "</span>";
    if (m.status === "finished" && m.score) return '<span class="chip">' + sc(m.score) + (m.penalties ? "<small>ترجيح " + sc(m.penalties) + "</small>" : m.status_detail === "AET" ? "<small>بعد الإضافي</small>" : "") + "</span>";
    if (m.status === "scheduled" || !m.status) return '<span class="chip up">' + (m.time_tbd ? "—" : R.tt(m.kickoff_uae)) + (o.date ? "<small>" + R.td(m.kickoff_uae) + "</small>" : "") + "</span>";
    return '<span class="chip off">' + R.statusText(m) + "</span>";
  };
  R.matchRow = function(m, o){
    o = o || {}; var fin = m.status === "finished", s = m.score, hw = fin && s && s.home > s.away, aw = fin && s && s.away > s.home;
    var mine = o.mine && (m.home.id === o.mine || m.away.id === o.mine);
    var tag = m.id ? "a" : "div", attr = m.id ? ' href="/m/' + m.id + '/" data-mid="' + m.id + '"' : ' title="الموعد ما تأكد"';
    return "<" + tag + ' class="m' + (R.isLive(m) ? " live" : "") + (mine ? " mine" : "") + (m.id ? "" : " nolink") + '"' + attr + ">" +
      '<span class="t h' + (hw ? " win" : aw ? " lose" : "") + '">' + R.logo(m.home) + "<span>" + R.tname(m.home) + "</span></span>" + (m.id || m.status !== "scheduled" ? R.chip(m, o) : '<span class="chip up"><small>الموعد ما تأكد</small></span>') +
      '<span class="t a' + (aw ? " win" : hw ? " lose" : "") + '">' + R.logo(m.away) + "<span>" + R.tname(m.away) + "</span></span></" + tag + ">";
  };
  // 281: TV guide for one country (guide/{iso2}.json): the next 3 days, each match with its broadcasters there
  R.guide = function(g){
    if (!g || !g.matches || !g.matches.length) return '<p class="empty">ما لقينا مباريات منقولة في الأيام الياية.</p>';
    var days = {}, order = []; g.matches.slice().sort(function(a, b){ return a.kickoff_utc.localeCompare(b.kickoff_utc); }).forEach(function(m){ var d = R.ymd(R.TZ ? m.kickoff_utc : (m.kickoff_uae || m.kickoff_utc)); if (!days[d]){ days[d] = []; order.push(d); } days[d].push(m); });
    return order.map(function(d){ return "<h3>" + esc(R.dayLabel(d)) + "</h3>" + days[d].map(function(m){ var mm = { id:m.match, comp:m.comp, kickoff_utc:m.kickoff_utc, kickoff_uae:m.kickoff_uae, status:m.status, score:m.score, home:m.home, away:m.away };
      return '<div class="gm">' + R.matchRow(mm, {}) + '<p class="bc"><span class="muted small">' + esc(m.comp_name_ar || "") + "</span> " + (m.broadcasters || []).map(function(b){ return "<b>" + esc(b.name_ar || b.name_en) + "</b>" + (b.free ? "" : ' <span class="enc">مشفرة</span>'); }).join("، ") + "</p></div>"; }).join(""); }).join("");
  };
  R.compOrder = function(index){ var o = {}; (index.competitions || []).forEach(function(c, i){ o[c.id] = i; }); return o; };
  R.compName = function(index, id){ var c = (index.competitions || []).filter(function(c){ return c.id === id; })[0]; return c ? c.name_ar : ""; };
  R.compKey = function(index, id){ var c = (index.competitions || []).filter(function(c){ return c.id === id; })[0]; return c ? c.key : null; };
  var ORD = { A:"الأولى", B:"الثانية", C:"الثالثة", D:"الرابعة", E:"الخامسة", F:"السادسة", G:"السابعة", H:"الثامنة", I:"التاسعة", J:"العاشرة", K:"الحادية عشرة", L:"الثانية عشرة", "1":"الأولى", "2":"الثانية", "3":"الثالثة", "4":"الرابعة", "5":"الخامسة", "6":"السادسة", "7":"السابعة", "8":"الثامنة" };
  // QA 7: every stage name the feeds send, in Arabic ("Group Stage - Round 3", "bronze", "1st Preliminary Round", "Winner SF 1")
  var KO = [[/group stage\s*-\s*round\s*(\d+)/i, function(m){ return "الجولة " + m[1]; }], [/^(1st|first)\s+preliminary/i, "الدور التمهيدي الأول"], [/^(2nd|second)\s+preliminary/i, "الدور التمهيدي الثاني"], [/^(3rd|third)\s+preliminary/i, "الدور التمهيدي الثالث"],
    [/^bronze$|^3rd$/i, "مباراة المركز الثالث"], [/^prelim-1$/i, "الدور التمهيدي الأول"], [/^prelim-2$/i, "الدور التمهيدي الثاني"], [/^prelim-3$/i, "الدور التمهيدي الثالث"], [/^prelim$/i, "الدور التمهيدي"], [/^west$/i, "منطقة الغرب"], [/^east$/i, "منطقة الشرق"], [/^1\/64|round of 128/i, "دور الـ128"], [/^1\/32|round of 64/i, "دور الـ64"], [/^1\/16|round of 32/i, "دور الـ32"], [/^1\/8|round of 16|last 16/i, "دور الـ16"], [/^1\/4|quarter/i, "ربع النهائي"], [/^1\/2|semi/i, "نصف النهائي"], [/best.*(3rd|third)/i, "أفضل أصحاب المركز الثالث"], [/(3rd|third).*(place|play)/i, "مباراة المركز الثالث"], [/^final$|^the final$|^final\b/i, "النهائي"], [/play-?off/i, "الملحق"], [/^preliminary/i, "الدور التمهيدي"], [/^qualif/i, "التصفيات"], [/^group stage$/i, "دور المجموعات"]];
  R.groupOrd = function(x, i){ x = String(x == null ? "" : x).replace(/^Gr(?:ou)?p\.?\s*/i, "").trim(); if (/^west$/i.test(x)) return "منطقة الغرب"; if (/^east$/i.test(x)) return "منطقة الشرق"; return "المجموعة " + (ORD[x.toUpperCase()] || (i != null ? ORD[String(i + 1)] || i + 1 : x)); };
  R.stageAr = function(s){ if (!s) return ""; s = String(s); var g = /Gr(?:ou)?p\.?\s*([A-Za-z0-9]{1,2})\b/.exec(s) || /group\s*([A-Za-z0-9]{1,2})\b/i.exec(s); if (g) return "المجموعة " + (ORD[g[1].toUpperCase()] || g[1]); if (/^Gr(?:ou)?p\.?$/i.test(s.trim())) return "المجموعة";
    for (var i = 0; i < KO.length; i++){ var mm = KO[i][0].exec(s.trim()); if (mm) return typeof KO[i][1] === "function" ? KO[i][1](mm) : KO[i][1]; } return s; };
  // «Winner SF 1» / «Loser QF 2» placeholders in brackets and fixtures
  R.slotAr = function(n){ var m = /^(winner|loser)\s+(sf|qf|r16|semi[- ]?final|quarter[- ]?final)\s*(\d+)/i.exec(String(n || "")); if (!m) return null; var st = /^s/i.test(m[2]) ? "نص النهائي" : /^q/i.test(m[2]) ? "ربع النهائي" : "دور الـ16"; return (/^w/i.test(m[1]) ? "الفايز من " : "الخسران من ") + st + " " + m[3]; };
  // round keys sort as numbers first (1, 2, 3), then the knockout stages in play order
  var STO = [/preliminary|^prelim/i, /group|^\d+$/i, /1\/64|128/i, /1\/32|of 64/i, /1\/16|of 32/i, /1\/8|of 16|last 16/i, /1\/4|quarter/i, /1\/2|semi/i, /bronze|3rd|third/i, /final/i];
  R.stageRank = function(k){ k = String(k); if (/play-?off/i.test(k)) return 1.5; for (var i = 0; i < STO.length; i++) if (STO[i].test(k)) return i; return 1; };
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
      // QA 1: the group goes in the block head only when every match shares it; otherwise each group gets its own small heading
      var live = ms.filter(R.isLive).length, isG = function(m){ return m.stage && /Gr(ou)?p/i.test(m.stage); }, stages = ms.map(function(m){ return isG(m) ? m.stage : ""; }), same = stages.every(function(s){ return s === stages[0]; }), grp = same && stages[0] ? R.stageAr(stages[0]) : "";
      var rows = same ? ms.map(function(m){ return R.matchRow(m, o); }).join("") : (function(){ var out = "", cur = null; ms.slice().sort(function(a, b){ return (isG(a) ? a.stage : "~").localeCompare(isG(b) ? b.stage : "~") || (a.kickoff_utc || "").localeCompare(b.kickoff_utc || ""); }).forEach(function(m){ var s = isG(m) ? m.stage : ""; if (s !== cur){ cur = s; if (s) out += '<p class="grp-sub">' + esc(R.stageAr(s)) + "</p>"; } out += R.matchRow(m, o); }); return out; })();
      return '<section class="comp-block"><div class="comp-head">' + (key ? '<a href="/c/' + key + '/">' + esc(name) + "</a>" : esc(name)) + (grp ? '<span class="grp">' + esc(grp) + "</span>" : "") + (live ? '<span class="lv"><i class="cardflip"></i>' + live + " مباشر</span>" : "") + "</div>" + rows + "</section>";
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
      var hasForm = g.rows.some(function(r){ return r.form && r.form.length; });   /* QA 85: no empty «آخر 5» column */
      return (g.name ? "<h3>" + esc(String(g.name_ar || R.stageAr(g.name)).replace(/المجموعة ([A-J])\b/, function(_, l){ return R.groupOrd(l); })) + "</h3>" : "") + '<div class="tblwrap"><table class="st"><thead><tr><th>#</th><th style="text-align:start">الفريق</th><th>لعب</th><th class="hx">فاز</th><th class="hx">تعادل</th><th class="hx">خسر</th><th class="hx">له - عليه</th><th>الفارق</th><th>نقاط</th>' + (hasForm ? '<th class="hx">آخر 5</th>' : "") + "</tr></thead><tbody>" +
        g.rows.map(function(r){ var z = r.zone && r.zone.color; return '<tr class="' + (o.mine === r.team.id ? "mine " : "") + (r.live ? "live" : "") + '" data-tid="' + r.team.id + '"><td class="rk"><span' + (z ? ' style="background:' + esc(z) + ";color:" + ink(z) + '"' : "") + ">" + r.rank + '</span></td><td class="tm"><a href="/t/' + r.team.id + '/">' + R.logo(r.team, "sm") + R.tname(r.team) + "</a></td><td>" + r.played + '</td><td class="hx">' + r.won + '</td><td class="hx">' + r.drawn + '</td><td class="hx">' + r.lost + '</td><td class="hx">' + r.gf + " - " + r.ga + '</td><td><bdi dir="ltr">' + (r.gd > 0 ? "+" : "") + r.gd + '</bdi></td><td class="pts">' + r.pts + "</td>" + (hasForm ? '<td class="hx">' + R.form(r.form) + "</td>" : "") + "</tr>"; }).join("") +
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
    // W2.7: players level on the value share a rank, fewer minutes first
    l = l.slice().sort(function(a, b){ return (b.value - a.value) || ((a.minutes || 1e9) - (b.minutes || 1e9)); }); var rk = 0, last = null; l.forEach(function(p, i){ if (p.value !== last){ rk = i + 1; last = p.value; } p._rk = rk; });
    return '<ol class="lead">' + l.slice(0, n || 20).map(function(p){ return '<li><span class="num muted">' + p._rk + '</span><span class="who">' + R.logo(p.team, "sm") + (p.player.id ? '<a class="lat" href="/p/' + p.player.id + '/">' + esc(p.player.name) + "</a>" : '<span class="lat">' + esc(p.player.name) + "</span>") + ' <span class="muted small">' + R.tname(p.team) + "</span></span><b>" + p.value + "</b></li>"; }).join("") + "</ol>";
  };
  // fixtures by round; opens on the next unplayed round
  R.rounds = function(fx){
    var r = {}, order = []; (fx.matches || []).forEach(function(m){ var k = m.round || m.stage || "—"; if (!r[k]){ r[k] = []; order.push(k); } r[k].push(m); });
    // QA 7: plain numbers are league rounds; anything else ("1/2", "Quarter-finals", "bronze") sorts by stage, then by its first kickoff
    var num = function(k){ return /^\d+$/.test(String(k)); }, first = function(k){ return r[k].map(function(m){ return m.kickoff_utc || "9"; }).sort()[0]; };
    order.sort(function(a, b){ if (num(a) && num(b)) return +a - +b; var ra = num(a) ? 1 : R.stageRank(a), rb = num(b) ? 1 : R.stageRank(b); return ra - rb || first(a).localeCompare(first(b)); });
    return { order:order, by:r };
  };
  R.roundLabel = function(k){ return /^\d+$/.test(String(k)) ? "الجولة " + esc(k) : esc(R.stageAr(k)); };
  R.roundChip = function(k){ return /^\d+$/.test(String(k)) ? esc(k) : esc(R.stageAr(k)); };   // chips: «1 · 2 · 3 · نصف النهائي · النهائي»
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
      // how the goal went in (compute/goal_how.py, from 2026-09-30): «رأسية من ركنية»; a penalty or own goal already says so
      var how = e.type === "goal" && e.how && e.how.ar ? '<span class="sub how" data-how="' + esc(e.how.key) + '">' + esc(e.how.ar) + "</span>" : "";
      var body = '<span class="who">' + evIcon(e.type) + who + (/goal/.test(e.type) && e.score ? '<span class="gs">' + sc(e.score) + "</span>" : "") + (EV[e.type] ? '<span class="kind">' + EV[e.type] + "</span>" : "") + "</span>" + extra + how;
      var mn = '<bdi dir="ltr">' + esc(e.minute) + (e.added ? "+" + esc(e.added) : "") + "'</bdi>";
      // hook for goal clips: data-goal-key="<minute as shown, 45+2>-<player id>"
      var gk = /goal/.test(e.type) && !/^shootout/.test(e.type) ? ' data-goal-key="' + esc(e.minute + (e.added ? "+" + e.added : "") + "-" + ((e.player && e.player.id) || 0)) + '"' : "";
      return e.team === "home" ? "<li" + gk + '><span class="h">' + body + '</span><span class="mn">' + mn + "</span><span></span></li>" : "<li" + gk + '><span></span><span class="mn">' + mn + "</span><span>" + body + "</span></li>";
    }).join("") + '</ul><p class="src"><a href="/laws/">ليش ألغى الحكم هدف أو صفّر بلنتي؟ قانون الكورة بالإماراتي</a></p>';
  };
  // «الملخص»: the official highlights video FotMob links (match file "highlights"; the poller re-polls after full time
  // until it appears), opened in a new tab
  R.hl = function(md){ var h = md && md.highlights, u = h && h.url; if (!u || !/^https:\/\//.test(u)) return "";
    return '<p class="hlink"><a class="btn hlbtn" href="' + esc(u) + '" target="_blank" rel="noopener">الملخص' + (/youtu/.test(u) ? ' <span class="small">على يوتيوب</span>' : "") + "</a></p>"; };
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
  var FIFA2 = "UAE:AE,KSA:SA,QAT:QA,BHR:BH,KUW:KW,OMA:OM,IRQ:IQ,JOR:JO,SYR:SY,LBN:LB,PLE:PS,YEM:YE,EGY:EG,LBY:LY,TUN:TN,ALG:DZ,MAR:MA,SUD:SD,MTN:MR,SOM:SO,DJI:DJ,COM:KM,IRN:IR,TUR:TR,UZB:UZ,TJK:TJ,KAZ:KZ,KGZ:KG,JPN:JP,KOR:KR,PRK:KP,CHN:CN,AUS:AU,IND:IN,THA:TH,VIE:VN,IDN:ID,MAS:MY,PHI:PH,SIN:SG,BRA:BR,ARG:AR,URU:UY,PAR:PY,COL:CO,CHI:CL,PER:PE,ECU:EC,VEN:VE,BOL:BO,MEX:MX,USA:US,CAN:CA,CRC:CR,HON:HN,JAM:JM,PAN:PA,HAI:HT,POR:PT,ESP:ES,FRA:FR,ITA:IT,GER:DE,NED:NL,BEL:BE,SUI:CH,AUT:AT,DEN:DK,SWE:SE,NOR:NO,FIN:FI,ISL:IS,POL:PL,CZE:CZ,SVK:SK,SVN:SI,CRO:HR,SRB:RS,BIH:BA,MNE:ME,MKD:MK,ALB:AL,KVX:XK,GRE:GR,BUL:BG,ROU:RO,HUN:HU,UKR:UA,RUS:RU,BLR:BY,GEO:GE,ARM:AM,AZE:AZ,IRL:IE,ISR:IL,CYP:CY,LUX:LU,SEN:SN,CIV:CI,GHA:GH,NGA:NG,CMR:CM,MLI:ML,BFA:BF,GUI:GN,GAB:GA,COD:CD,CGO:CG,ANG:AO,ZAM:ZM,ZIM:ZW,RSA:ZA,KEN:KE,TAN:TZ,UGA:UG,ETH:ET,BEN:BJ,TOG:TG,NIG:NE,GAM:GM,GNB:GW,CPV:CV,MOZ:MZ,MAD:MG,EQG:GQ,NZL:NZ".split(","), F2 = {}; FIFA2.forEach(function(x){ var a = x.split(":"); F2[a[0]] = a[1]; });
  var FLAGX = { ENG:"🏴", SCO:"🏴", WAL:"🏴", NIR:"🏴" };
  R.flag = function(code){ code = String(code || "").toUpperCase(); if (FLAGX[code]) return FLAGX[code]; var iso = F2[code] || (code.length === 2 ? code : ""); if (!iso) return ""; return String.fromCodePoint.apply(String, iso.split("").map(function(c){ return 0x1F1E6 + c.charCodeAt(0) - 65; })); };
  function players(list){ return "<ul>" + (list || []).map(function(p){ return '<li><span class="no">' + esc(p.number || "") + '</span><span class="lat">' + esc(p.name) + "</span>" + (p.captain ? ' <span class="muted small">كابتن</span>' : "") + (p.country && p.country !== "UAE" && R.flag(p.country) ? ' <span class="flag" title="' + esc(p.country) + '">' + R.flag(p.country) + "</span>" : "") + rt(p.rating) + "</li>"; }).join("") + "</ul>"; }
  function surname(n){ var p = String(n || "").trim().split(/\s+/); if (!/[\u0600-\u06FF]/.test(n)) return p.length > 1 ? p.slice(1).join(" ") : p[0];
    // Arabic: glue عبد/أبو/بن/ابن/آل to the next word and any word to a following الله/الدين/الرحمن, then show the last unit
    var u = []; for (var i = 0; i < p.length; i++){ var w = p[i]; if (/^(عبد|أبو|ابو|بن|ابن|آل)$/.test(w) && i + 1 < p.length){ w += " " + p[++i]; } if (i + 1 < p.length && /^(الله|الدين|الرحمن)$/.test(p[i + 1])){ w += " " + p[++i]; } u.push(w); }
    return u.length > 1 ? u[u.length - 1] : u[0]; }
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
    var items = []; (md.stats || []).forEach(function(s){ s.items.forEach(function(i){ if (STAT_AR[i.key] && !items.some(function(x){ return x.key === i.key; })) items.push(Object.assign({}, i)); }); });
    if ((md.events || []).length){ var cnt = function(side, re){ return (md.events || []).filter(function(e){ return e.team === side && re.test(e.type); }).length; };
      items.forEach(function(i){ if (i.key === "yellow_cards"){ i.home = cnt("home", /^yellow$/); i.away = cnt("away", /^yellow$/); } if (i.key === "red_cards"){ i.home = cnt("home", /^(red|second_yellow)$/); i.away = cnt("away", /^(red|second_yellow)$/); } }); }
    if (md.coverage_events && md.coverage_events.cards === false) items = items.filter(function(i){ return !/cards$/.test(i.key); });   // the source sent no cards for this match
    items = items.filter(function(i){ return i.key === "BallPossesion" || (parseFloat(i.home) || 0) + (parseFloat(i.away) || 0) > 0; });
    // W2.6: six key rows, the rest behind «كل الأرقام»
    var KEY = ["BallPossesion", "expected_goals", "total_shots", "ShotsOnTarget", "big_chance", "corners"]; items.sort(function(a, b){ var x = KEY.indexOf(a.key), y = KEY.indexOf(b.key); return (x < 0 ? 99 : x) - (y < 0 ? 99 : y); });
    var row = function(i){ var h = parseFloat(i.home) || 0, a = parseFloat(i.away) || 0, t = h + a || 1; return '<div class="stat"><span class="l">' + STAT_AR[i.key] + '</span><span class="v">' + esc(i.home) + '</span><span class="bar2"><i style="inline-size:' + (h / t * 100).toFixed(1) + '%"></i><i style="inline-size:' + (a / t * 100).toFixed(1) + '%"></i></span><span class="v">' + esc(i.away) + "</span></div>"; };
    return items.slice(0, 6).map(row).join("") + (items.length > 6 ? '<details class="more-stats"><summary>كل الأرقام</summary>' + items.slice(6).map(row).join("") + "</details>" : "");
    // bars: home share from the right (RTL), away share to the left
    return items.map(function(i){ var h = parseFloat(i.home) || 0, a = parseFloat(i.away) || 0, t = h + a || 1; return '<div class="stat"><span class="l">' + STAT_AR[i.key] + '</span><span class="v">' + esc(i.home) + '</span><span class="bar2"><i style="inline-size:' + (h / t * 100).toFixed(1) + '%"></i><i style="inline-size:' + (a / t * 100).toFixed(1) + '%"></i></span><span class="v">' + esc(i.away) + "</span></div>"; }).join("");
  };
  R.h2h = function(md){
    var h = md.h2h; if (!h || !h.summary) return '<p class="empty">ما في مواجهات سابقة مسجّلة.</p>';
    var s = h.summary, k = [md.home.id, md.away.id].sort(function(a, b){ return a - b; }).join("-");
    return ((R.H2HK || (root && root.H2HK) || {})[k] ? '<p><a class="btn" href="/h2h/' + k + '/">كل مواجهاتهم</a></p>' : "") + '<div class="h2hsum"><div><b>' + s.home_wins + "</b>فوز " + R.tname(md.home) + "</div><div><b>" + s.draws + "</b>تعادل</div><div><b>" + s.away_wins + "</b>فوز " + R.tname(md.away) + "</div></div>" +
      (function(){ var now = Date.now(), fut = (h.matches || []).filter(function(m){ return m.id !== md.id && (m.status === "scheduled" || (!m.score && Date.parse(m.kickoff_utc) > now)); }), past = (h.matches || []).filter(function(m){ return m.id !== md.id && fut.indexOf(m) < 0 && m.score; });   /* QA 9: never a scoreless «انتهت» */
        return (fut.length ? "<h3>الياية</h3>" + fut.map(function(m){ return R.matchRow(m, { date:true }); }).join("") + "<h3>اللي فاتت</h3>" : "") + past.slice(0, 10).map(function(m){ m.status = m.status || "finished"; return R.matchRow(m, { date:true }); }).join(""); })();
  };
  function band(t){ return '<span class="band" aria-hidden="true"><i style="background:' + R.col(t.id, 0) + '"></i><i style="background:' + R.col(t.id, 1) + '"></i></span>'; }
  R.matchHead = function(md){
    var live = R.isLive(md), st = live ? '<i class="cardflip"></i>' + R.minute(md) : md.status === "scheduled" ? R.td(md.kickoff_uae, true) : R.statusText(md) + (md.halftime_score && md.status === "finished" ? '، الشوط الأول <span class="num">' + sc(md.halftime_score) + "</span>" : "");
    return '<div class="board' + (live ? " live" : "") + '">' + band(md.home) + '<a class="tm" href="/t/' + md.home.id + '/">' + R.logo(md.home, "lg") + R.tname(md.home) + "</a>" +
      '<div class="sc"><span class="dg">' + (md.score ? sc(md.score) : md.time_tbd ? "—" : R.tt(md.kickoff_uae) || "—") + "</span>" + (md.penalties ? '<span class="pens">ترجيح <span class="num">' + sc(md.penalties) + "</span></span>" : "") + '<span class="st">' + st + "</span></div>" +
      '<a class="tm" href="/t/' + md.away.id + '/">' + R.logo(md.away, "lg") + R.tname(md.away) + "</a>" + band(md.away) + "</div>" + R.timeline(md);
  };
  R.matchFacts = function(md, index){
    var key = R.compKey(index, md.comp), f = [];
    f.push(["البطولة", key ? '<a href="/c/' + key + '/">' + esc(md.comp_name_ar || R.compName(index, md.comp)) + "</a>" : esc(md.comp_name_ar || "")]);
    if (md.round && !isNaN(parseFloat(md.round))) f.push(["الجولة", '<span class="num">' + esc(md.round) + "</span>"]);
    else if (md.stage && /Gr(ou)?p/i.test(md.stage)) f.push(["الدور", esc(R.stageAr(md.stage))]);
    f.push(["الموعد بتوقيت بلدك", R.td(md.kickoff_uae, true) + ' <span class="num">' + R.tt(md.kickoff_uae) + "</span>"]);
    if (md.venue && (md.venue.name_ar || /[\u0600-\u06FF]/.test(md.venue.name || ""))) f.push(["الملعب", esc(md.venue.name_ar || md.venue.name)]);   /* QA 65: no Latin-only venue in the Arabic facts */
    if (md.venue && md.venue.distance_km && md.venue.in_uae !== false){ var EM = [["abu-dhabi","أبوظبي"],["dubai","دبي"],["sharjah","الشارقة"],["ajman","عجمان"],["umm-al-quwain","أم القيوين"],["ras-al-khaimah","رأس الخيمة"],["fujairah","الفجيرة"],["al-ain","العين"]];
      f.push(["المسافة من", '<span class="dist" data-km=\'' + esc(JSON.stringify(md.venue.distance_km)) + '\'><select class="emsel" aria-label="إمارتك">' + EM.map(function(e){ return '<option value="' + e[0] + '"' + (e[0] === "dubai" ? " selected" : "") + ">" + e[1] + "</option>"; }).join("") + '</select> <b class="num dk">' + Math.round(md.venue.distance_km.dubai) + '</b> كم <span class="muted small dt"></span></span>']); }
    if (md.referee) f.push(["الحكم", md.referee.id ? '<a class="lat" href="/r/' + md.referee.id + '/">' + esc(md.referee.name) + "</a>" : '<span class="lat">' + esc(md.referee.name || md.referee) + "</span>"]);
    if (md.attendance) f.push(["الحضور", '<span class="num">' + Number(md.attendance).toLocaleString("en-US") + "</span>"]);
    var tiles = "";
    if (md.prayer && md.prayer.clashes && md.prayer.clashes.length){
      var P = { fajr:"الفجر", dhuhr:"الظهر", asr:"العصر", maghrib:"المغرب", isha:"العشاء" }, S = { halftime:"يصادف الاستراحة", first_half:"في الشوط الأول", second_half:"في الشوط الثاني", before:"قبل البداية" };
      md.prayer.clashes.forEach(function(c){ tiles += '<div class="tile pray"><span class="ic">🕌</span><div><b>أذان ' + (P[c.prayer] || esc(c.prayer)) + (md.venue && md.venue.name_ar ? " في " + esc(md.venue.name_ar) : "") + ' <span class="num">' + esc(c.at_uae) + "</span></b><span>" + (S[c.segment] || "") + (c.segment !== "halftime" && c.minute_of_play != null ? "، حوالي الدقيقة " + c.minute_of_play : "") + (md.prayer.estimated_window ? "، تقريبي" : "") + "</span></div></div>"; });
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
    return t.squad.filter(function(g){ return g.group !== "coach"; }).map(function(g){ return "<h3>" + (GROUP_AR[g.group] || esc(g.group)) + '</h3><div class="squad">' + g.players.map(function(p){ return '<div><span class="no">' + esc(p.number || "") + "</span>" + ((R.PP || (root && root.PP) || {})[p.id] ? '<a class="lat" href="/p/' + p.id + '/">' + esc(p.name) + "</a>" : '<span class="lat">' + esc(p.name) + "</span>") + (p.position && R.pos ? ' <span class="muted small">' + esc(R.pos(p.position)) + "</span>" : "") + (p.age ? ' <span class="muted small num">' + p.age + "</span>" : "") + (p.country && p.country !== t.country && R.flag(p.country) ? ' <span class="flag" title="' + esc(p.country) + '">' + R.flag(p.country) + "</span>" : "") + (p.club && t.national ? ' <span class="muted small">' + (p.club_id ? R.tname({ id:p.club_id, name:p.club, name_ar:p.club_ar }) : esc(p.club_ar || p.club)) + "</span>" : "") + (p.injury ? ' <span class="muted small">مصاب</span>' : "") + '<span class="x">' + (p.goals ? p.goals + " هدف" : "") + (p.goals && p.assists ? "، " : "") + (p.assists ? p.assists + " صناعة" : "") + "</span></div>"; }).join("") + "</div>"; }).join("");
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
  // the player's EA SPORTS FC 27 card (db/eafc.py): [overall, position, [6 face stats], skill moves, weak foot, foot, [29 attributes],
  // [PlayStyles], EA id, EA team, goalkeeper, [5 goalkeeping attributes]]
  var EA_FACE = ["السرعة", "التسديد", "التمرير", "المراوغة", "الدفاع", "البدنية"], EA_GKF = ["الارتماء", "الإمساك", "ركل الكرة", "ردة الفعل", "السرعة", "التمركز"];
  var EA_ATTR = ["التسارع", "السرعة القصوى", "التمركز الهجومي", "إنهاء الهجمات", "قوة التسديد", "التسديد البعيد", "الكرات الطائرة", "ضربات الجزاء", "الرؤية", "العرضيات",
    "الركلات الحرة", "التمرير القصير", "التمرير الطويل", "الانحناء", "الرشاقة", "التوازن", "ردة الفعل", "التحكم بالكرة", "المراوغة", "الهدوء", "قطع الكرات", "الرأسيات",
    "الوعي الدفاعي", "الافتكاك", "التدخل الانزلاقي", "القفز", "التحمّل", "القوة", "الشراسة"];
  var EA_GROUPS = [["السرعة", 0, 2], ["التسديد", 2, 8], ["التمرير", 8, 14], ["المراوغة", 14, 20], ["الدفاع", 20, 25], ["البدنية", 25, 29]];
  var EA_GK = ["الارتماء", "الإمساك", "ركل الكرة", "ردة الفعل", "التمركز"];
  var EA_PS = { "Aerial Fortress":"حصن الكرات العالية", "Technical":"تقني", "Long Ball Pass":"الكرات الطويلة", "Intercept":"قطع الكرات", "Rapid":"سريع", "Precision Header":"الرأسية الدقيقة",
    "Finesse Shot":"التسديدة الملتفة", "Slide Tackle":"التدخل الانزلاقي", "Whipped Pass":"العرضية المقوّسة", "Quick Step":"الانطلاقة السريعة", "Incisive Pass":"التمريرة القاتلة",
    "Anticipate":"قراءة اللعب", "Relentless":"ما يتعب", "Block":"صد التسديدات", "Bruiser":"قوي في الالتحام", "Jockey":"المراقبة اللصيقة", "Press Proven":"يتحمّل الضغط",
    "Long Throw":"رمية التماس الطويلة", "Inventive":"مبتكر", "First Touch":"اللمسة الأولى", "Dead Ball":"الكرات الثابتة", "Footwork":"حركة القدمين", "Low Driven Shot":"التسديدة الأرضية",
    "Gamechanger":"صانع الفارق", "Enforcer":"صاحب الهيبة", "Power Shot":"التسديدة القوية", "Cross Claimer":"صيّاد العرضيات", "Far Throw":"الرمية البعيدة", "Pinged Pass":"التمريرة المشدودة",
    "Tiki Taka":"تيكي تاكا", "Acrobatic":"الأكروبات", "Chip Shot":"اللوب", "Trickster":"الحيل", "Deflector":"مبعد الكرات", "Rush Out":"الخروج من المرمى", "Far Reach":"الامتداد الطويل" };
  R.eaCard = function(c){
    if (!c || !c[0]) return "";
    var gk = c[10], face = gk ? EA_GKF : EA_FACE, stars = function(n){ n = +n || 0; return '<span class="eas" aria-label="' + n + ' من 5">' + "★★★★★".slice(0, n) + '<i>' + "★★★★★".slice(n) + "</i></span>"; };
    var bar = function(label, v){ return "<li><span>" + label + '</span><i style="--w:' + (+v || 0) + '%"></i><b class="num">' + (v == null ? "—" : v) + "</b></li>"; };
    var ps = (c[7] || []).map(function(p){ var plus = /\+$/.test(p), k = p.replace(/\+$/, ""); return '<span class="eap' + (plus ? " plus" : "") + '">' + esc(EA_PS[k] || k) + (plus ? "+" : "") + "</span>"; }).join("");
    var all = gk ? '<ul class="bars eab">' + EA_GK.map(function(l, i){ return bar(l, (c[11] || [])[i]); }).join("") + "</ul>" :
      EA_GROUPS.map(function(g){ return "<h4>" + g[0] + '</h4><ul class="bars eab">' + EA_ATTR.slice(g[1], g[2]).map(function(l, i){ return bar(l, (c[6] || [])[g[1] + i]); }).join("") + "</ul>"; }).join("");
    return '<section class="blk eac"><h2>في EA SPORTS FC 27</h2><div class="eag"><div class="eao"><b class="num">' + c[0] + '</b><span>' + esc(c[1] || "") + '</span></div><ul class="bars eab">' +
      face.map(function(l, i){ return bar(l, (c[2] || [])[i]); }).join("") + "</ul></div>" +
      '<p class="muted small">المهارات ' + stars(c[3]) + " · القدم الضعيفة " + stars(c[4]) + (c[5] ? " · يلعب " + (c[5] === 2 ? "باليسرى" : "باليمنى") : "") + "</p>" +
      (ps ? '<p class="eaps">' + ps + "</p>" : "") + "<details><summary>كل الخصائص</summary>" + all + "</details>" + '<p class="src">التقييم من EA SPORTS FC 27' + (c[9] ? " (" + esc(c[9]) + ")" : "") + ".</p></section>";
  };
  // the player's Transfermarkt record (db/tmdata.py): every season by competition, the injury record, birthplace, agent…
  var TM_COMP = { FAC:"كأس الاتحاد الإنجليزي", CGB:"كأس الرابطة الإنجليزية", CIT:"كأس إيطاليا", FRC:"كأس فرنسا", CDR:"كأس ملك إسبانيا", TRP:"كأس تركيا", DFB:"كأس ألمانيا",
    GBFL:"كأس EFL", BRC:"كأس البرازيل", ELQ:"تصفيات الدوري الأوروبي", CL:"دوري أبطال أوروبا", IT1:"الدوري الإيطالي", EL:"الدوري الأوروبي", IT2:"الدرجة الثانية الإيطالية",
    GB1:"الدوري الإنجليزي الممتاز", GB2:"التشامبيونشيب", BRA1:"الدوري البرازيلي", ES1:"الدوري الإسباني", ES2:"الدرجة الثانية الإسبانية", POPO:"كأس البرتغال", GB3:"الدرجة الثالثة الإنجليزية",
    FR1:"الدوري الفرنسي", NLP:"كأس هولندا", CLQ:"تصفيات دوري أبطال أوروبا", FRL:"كأس الرابطة الفرنسية", L1:"الدوري الألماني", CCB:"كأس بلجيكا", FR2:"الدرجة الثانية الفرنسية",
    TR1:"الدوري التركي", GB21:"الدوري الإنجليزي تحت 21", IT3A:"الدرجة الثالثة الإيطالية", IT3B:"الدرجة الثالثة الإيطالية", IT3C:"الدرجة الثالثة الإيطالية", GB4:"الدرجة الرابعة الإنجليزية",
    NL1:"الدوري الهولندي", RUP:"كأس روسيا", SCC:"كأس سويسرا", L2:"الدرجة الثانية الألمانية", UEFA:"كأس الاتحاد الأوروبي", BE1:"الدوري البلجيكي", MLS1:"الدوري الأمريكي", PO1:"الدوري البرتغالي",
    POPU:"كأس بولندا", CLI:"كأس ليبرتادوريس", BRA2:"الدرجة الثانية البرازيلية", MEXA:"الدوري المكسيكي (أبيرتورا)", MEX1:"الدوري المكسيكي (كلاوسورا)", GRP:"كأس اليونان", PL1:"الدوري البولندي",
    JEMP:"كأس الإمبراطور الياباني", ARCA:"كأس الأرجنتين", UNGP:"كأس المجر", SFA:"كأس اسكتلندا", POCP:"كأس الرابطة البرتغالية", MLSP:"كأس أمريكا المفتوحة", SCP:"كأس الرابطة الاسكتلندية",
    CS:"كوبا سودأمريكانا", UKRP:"كأس أوكرانيا", NL2:"الدرجة الثانية الهولندية", TR2:"الدرجة الأولى التركية", PO2:"الدرجة الثانية البرتغالية", FR3:"الدرجة الثالثة الفرنسية", DKP:"كأس الدنمارك",
    SC1:"الدوري الاسكتلندي", "19YL":"دوري الشباب الأوروبي", ECLQ:"تصفيات دوري المؤتمر", UKR1:"الدوري الأوكراني", RU1:"الدوري الروسي", SEC:"كأس السويد", L3:"الدرجة الثالثة الألمانية",
    JAPC:"كأس الرابطة اليابانية", GR1:"الدوري اليوناني", ofb:"كأس النمسا", DK1:"الدوري الدنماركي", C1:"الدوري السويسري", UNG1:"الدوري المجري", JAP1:"الدوري الياباني", SE1:"الدوري السويدي",
    NO1:"الدوري النرويجي", CSL:"الدوري الصيني", A1:"الدوري النمساوي", AFCL:"دوري أبطال آسيا", KR1:"الدوري الكرواتي", RKPO:"كأس كوريا", CHFA:"كأس الصين", CCL:"دوري أبطال الكونكاكاف",
    POUS:"أدوار الدوري الأمريكي الإقصائية", RSK1:"الدوري الكوري", UEQ:"تصفيات كأس الاتحاد الأوروبي", SLO1:"الدوري السلوفاكي", UI:"كأس إنترتوتو", USMX:"كأس الدوريات", KRC:"كأس كرواتيا",
    AUS1:"الدوري الأسترالي", UCOL:"دوري المؤتمر الأوروبي", RO1:"الدوري الروماني", ZYP1:"الدوري القبرصي", QSL:"دوري نجوم قطر", KLUB:"كأس العالم للأندية", SER1:"الدوري الصربي",
    BU1:"الدوري البلغاري", TS1:"الدوري التشيكي", AR1N:"الدوري الأرجنتيني", ARG1:"الدوري الأرجنتيني (أبيرتورا)", ARGC:"الدوري الأرجنتيني (كلاوسورا)", CDLP:"كأس الرابطة الأرجنتينية",
    SA1:"الدوري السعودي", UAE1:"الدوري الإماراتي", EGY1:"الدوري المصري", MAR1:"الدوري المغربي", TUN1:"الدوري التونسي", ALG1:"الدوري الجزائري", SC2:"الدرجة الأولى الاسكتلندية",
    A2:"الدرجة الثانية النمساوية", C2:"الدرجة الثانية السويسرية", BE2:"الدرجة الثانية البلجيكية", ARG2:"الدرجة الثانية الأرجنتينية", BRA3:"الدرجة الثالثة البرازيلية", JAP2:"الدرجة الثانية اليابانية",
    RU2:"الدرجة الأولى الروسية", UKR2:"الدرجة الأولى الأوكرانية", SE2:"الدرجة الثانية السويدية", NO2:"الدرجة الثانية النرويجية", DK2:"الدرجة الأولى الدنماركية", GR2:"الدرجة الثانية اليونانية",
    PL2:"الدرجة الأولى البولندية", ROMP:"كأس رومانيا", CNAT:"الدوري الوطني الإنجليزي", FAYC:"كأس الشباب الإنجليزي", GB18:"الدوري الإنجليزي تحت 18", IJ1:"دوري بريمافيرا الإيطالي",
    USC:"السوبر الأوروبي", SUC:"كأس السوبر الإسباني", DFL:"كأس السوبر الألماني", SCI:"كأس السوبر الإيطالي", FRSC:"كأس الأبطال الفرنسي", GBCS:"الدرع الخيرية" };
  var TM_INJ = { "unknown injury":"إصابة غير معلنة", "muscle injury":"إصابة عضلية", "hamstring injury":"إصابة في العضلة الخلفية", "knee injury":"إصابة في الركبة", "muscular problems":"مشاكل عضلية",
    "ankle injury":"إصابة في الكاحل", "ill":"مرض", "cruciate ligament tear":"قطع في الرباط الصليبي", "knock":"كدمة", "corona virus":"كورونا", "knee problems":"مشاكل في الركبة", "thigh problems":"مشاكل في الفخذ",
    "torn muscle fiber":"تمزق في ألياف العضلة", "fitness":"اللياقة", "shoulder injury":"إصابة في الكتف", "calf injury":"إصابة في السمانة", "adductor pain":"ألم في العضلة الضامة", "foot injury":"إصابة في القدم",
    "adductor injury":"إصابة في العضلة الضامة", "groin injury":"إصابة في الفخذ الداخلي", "hamstring strain":"شد في العضلة الخلفية", "rest":"راحة", "ankle sprain":"التواء في الكاحل", "minor knock":"كدمة خفيفة",
    "calf problems":"مشاكل في السمانة", "knee surgery":"عملية في الركبة", "back problems":"مشاكل في الظهر", "flu":"إنفلونزا", "leg injury":"إصابة في الساق", "meniscus injury":"إصابة في الغضروف الهلالي",
    "muscle fatigue":"إجهاد عضلي", "concussion":"ارتجاج", "influenza":"إنفلونزا", "hip injury":"إصابة في الورك", "groin problems":"مشاكل في الفخذ الداخلي", "bruise":"كدمة", "achilles tendon problems":"مشاكل في وتر أكيليس",
    "hamstring muscle injury":"إصابة في العضلة الخلفية", "ankle problems":"مشاكل في الكاحل", "cruciate ligament injury":"إصابة في الرباط الصليبي", "metatarsal fracture":"كسر في مشط القدم",
    "torn muscle bundle":"تمزق في حزمة عضلية", "strain":"شد عضلي", "back injury":"إصابة في الظهر", "dead leg":"كدمة في الفخذ", "quarantine":"حجر صحي", "muscle tear":"تمزق عضلي",
    "injury to the ankle":"إصابة في الكاحل", "muscle strain":"شد عضلي", "cold":"زكام", "head injury":"إصابة في الرأس", "achilles tendon rupture":"قطع في وتر أكيليس", "fever":"حمى",
    "stomach flu":"إنفلونزا المعدة", "hip problems":"مشاكل في الورك", "ligament injury":"إصابة في الأربطة", "meniscus tear":"تمزق في الغضروف الهلالي", "torn ankle ligaments":"تمزق في أربطة الكاحل",
    "torn thigh muscle":"تمزق في عضلة الفخذ", "surgery":"عملية جراحية", "calf strain":"شد في السمانة", "infection":"التهاب", "inner ligament injury":"إصابة في الرباط الداخلي",
    "torn lateral knee ligament":"تمزق في الرباط الجانبي للركبة", "broken nose bone":"كسر في الأنف", "inflammation of pubic bone":"التهاب عظم العانة", "toe injury":"إصابة في إصبع القدم",
    "broken fibula":"كسر في الشظية", "cruciate ligament surgery":"عملية في الرباط الصليبي", "foot bruise":"كدمة في القدم", "broken collarbone":"كسر في الترقوة", "calf muscle tear":"تمزق في عضلة السمانة",
    "ankle surgery":"عملية في الكاحل", "bruised ribs":"كدمة في الأضلاع", "broken foot":"كسر في القدم", "torn lateral ankle ligament":"تمزق في الرباط الجانبي للكاحل", "virus":"فيروس",
    "knee bruise":"كدمة في الركبة", "groin surgery":"عملية في الفخذ الداخلي", "meniscus damage":"ضرر في الغضروف الهلالي", "broken toe":"كسر في إصبع القدم", "rib fracture":"كسر في الأضلاع",
    "pubalgia":"آلام العانة", "torn knee ligaments":"تمزق في أربطة الركبة", "hand injury":"إصابة في اليد", "ligament stretching":"تمدد في الأربطة", "knee medial ligament tear":"تمزق في الرباط الإنسي للركبة",
    "syndesmotic ligament tear":"تمزق في الرباط الظنبوبي الشظوي", "groin strain":"شد في الفخذ الداخلي", "broken hand":"كسر في اليد", "muscle stiffness":"تيبس عضلي", "inner knee ligament tear":"تمزق في الرباط الداخلي للركبة",
    "elbow injury":"إصابة في الكوع", "inner ligament stretch of the knee":"تمدد في الرباط الداخلي للركبة", "torn muscle fiber in the adductor area":"تمزق في ألياف العضلة الضامة", "capsular injury":"إصابة في المحفظة المفصلية",
    "cartilage damage":"ضرر في الغضروف", "inguinal hernia":"فتق إربي", "abdominal muscle strain":"شد في عضلات البطن", "tendonitis":"التهاب في الوتر", "heel injury":"إصابة في الكعب",
    "injury to abdominal muscles":"إصابة في عضلات البطن", "lumbago":"ألم أسفل الظهر", "muscle fiber tear":"تمزق في ألياف العضلة", "metacarpal fracture":"كسر في مشط اليد", "broken finger":"كسر في الإصبع",
    "patellar tendon problems":"مشاكل في وتر الرضفة", "broken tibia":"كسر في الظنبوب", "broken cheekbone":"كسر في عظم الوجنة", "tendon rupture":"قطع في الوتر", "achilles tendon irritation":"تهيج في وتر أكيليس",
    "contracture":"تقلص عضلي", "torn ligaments":"تمزق في الأربطة", "broken ankle":"كسر في الكاحل", "sprain":"التواء", "shin injury":"إصابة في قصبة الساق", "outer ligament tear":"تمزق في الرباط الخارجي",
    "heart problems":"مشاكل في القلب", "stomach problems":"مشاكل في المعدة", "achilles tendon surgery":"عملية في وتر أكيليس", "broken arm":"كسر في الذراع", "herniated disc":"انزلاق غضروفي",
    "foot surgery":"عملية في القدم", "bone edema":"وذمة عظمية", "internal ligament tear":"تمزق في الرباط الداخلي", "tonsillitis":"التهاب اللوزتين", "broken leg":"كسر في الساق", "finger injury":"إصابة في الإصبع",
    "arm injury":"إصابة في الذراع", "syndesmosis ligament tear":"تمزق في الرباط الظنبوبي الشظوي", "thigh muscle strain":"شد في عضلة الفخذ", "calf muscle strain":"شد في عضلة السمانة", "shoulder dislocation":"خلع في الكتف" };
  var tmSeason = function(s){ var m = /^(\d{2})\/(\d{2})$/.exec(s || ""); return m ? (+m[1] > 60 ? "19" : "20") + m[1] + "/" + m[2] : s || ""; };
  R.tmSections = function(d){
    if (!d) return "";
    var N = d.names_ar || {}, out = "", dd = function(x){ return x ? '<span class="num">' + esc(String(x).slice(0, 10)) + "</span>" : ""; };
    var info = [d.born_in && (d.born_in[0] || d.born_in[1]) && ["مكان الميلاد", esc([d.born_in[0], d.born_in[1]].filter(Boolean).join("، "))],
      d.citizenship && d.citizenship.length > 1 && ["الجنسيات", esc(d.citizenship.join("، "))], d.native && /[^\x00-ɏ]/.test(d.native) && ["اسمه بلغته", esc(d.native)],
      d.agent && ["الوكيل", esc(d.agent)], d.outfitter && ["حذاؤه من", esc(d.outfitter)], d.joined && ["انضم لناديه", dd(d.joined)], d.contract && ["عقده لين", dd(d.contract)],
      d.option && ["خيار التمديد", esc(d.option)], d.extended && ["آخر تجديد", dd(d.extended)], d.loan_from && ["معار من", esc(d.loan_from)], d.died && ["توفي", dd(d.died)]].filter(Boolean);
    if (info.length) out += '<section class="blk"><h2>بطاقته عند Transfermarkt</h2><dl class="pbio">' + info.map(function(r){ return "<div><dt>" + r[0] + "</dt><dd>" + r[1] + "</dd></div>"; }).join("") + "</dl></section>";
    var C = d.career || [];
    if (C.length){
      var byC = {}, T = { a:0, g:0, as:0, y:0, r:0 };
      C.forEach(function(r){ var k = r[1] || r[2]; var b = byC[k] = byC[k] || { name:TM_COMP[r[1]] || r[2], a:0, g:0, as:0, s:0 }; b.a += r[6] || 0; b.g += r[7] || 0; b.as += r[8] || 0; b.s++;
        T.a += r[6] || 0; T.g += r[7] || 0; T.as += r[8] || 0; T.y += r[10] || 0; T.r += (r[11] || 0) + (r[12] || 0); });
      var comps = Object.keys(byC).sort(function(a, b){ return byC[b].a - byC[a].a; });
      out += '<section class="blk"><h2>مسيرته كاملة حسب البطولة <small>لين ' + esc(tmSeason(C[0][0])) + "</small></h2>" +
        '<p><b class="num">' + T.a + '</b> مباراة · <b class="num">' + T.g + '</b> هدف · <b class="num">' + T.as + '</b> صناعة · <span class="num">' + T.y + '</span> إنذار · <span class="num">' + T.r + "</span> طرد</p>" +
        '<div class="tscroll"><table class="tbl"><thead><tr><th>البطولة</th><th>مواسم</th><th>مباريات</th><th>أهداف</th><th>صناعة</th></tr></thead><tbody>' + comps.slice(0, 15).map(function(k){ var b = byC[k];
          return "<tr><td>" + esc(b.name) + '</td><td class="num">' + b.s + '</td><td class="num">' + b.a + '</td><td class="num">' + b.g + '</td><td class="num">' + b.as + "</td></tr>"; }).join("") + "</tbody></table></div>" +
        '<details><summary>كل المواسم (<span class="num">' + C.length + '</span> سطر)</summary><div class="tscroll"><table class="tbl"><thead><tr><th>الموسم</th><th>الفريق</th><th>البطولة</th><th>مباريات</th><th>أهداف</th><th>صناعة</th><th>دقيقة لكل هدف</th><th>إنذار</th><th>طرد</th><th>دخل بديل</th><th>طلع بديل</th></tr></thead><tbody>' +
        C.map(function(r){ return '<tr><td class="num">' + esc(tmSeason(r[0])) + "</td><td>" + esc(N[r[3]] || r[4] || "") + "</td><td>" + esc(TM_COMP[r[1]] || r[2] || "") + '</td><td class="num">' + (r[6] || 0) + '</td><td class="num">' + (r[7] || 0) +
          '</td><td class="num">' + (r[8] || 0) + '</td><td class="num">' + (r[9] == null ? "" : r[9]) + '</td><td class="num">' + (r[10] || 0) + '</td><td class="num">' + ((r[11] || 0) + (r[12] || 0)) + '</td><td class="num">' + (r[13] || 0) + '</td><td class="num">' + (r[14] || 0) + "</td></tr>"; }).join("") +
        "</tbody></table></div></details></section>";
    }
    var I = d.injuries || [];
    if (I.length){
      var days = I.reduce(function(a, x){ return a + (x[4] || 0); }, 0), games = I.reduce(function(a, x){ return a + (x[5] || 0); }, 0);
      out += '<section class="blk"><h2>سجل الإصابات <small>' + I.length + "</small></h2><p>غاب بسببها <b class=\"num\">" + days.toLocaleString("en") + '</b> يوم و<b class="num">' + games + "</b> مباراة.</p>" +
        '<div class="tscroll"><table class="tbl"><thead><tr><th>الموسم</th><th>الإصابة</th><th>من</th><th>أيام</th><th>غاب عن</th></tr></thead><tbody>' +
        I.map(function(x){ return '<tr><td class="num">' + esc(tmSeason(x[0])) + "</td><td>" + esc(TM_INJ[String(x[1] || "").toLowerCase()] || x[1] || "") + "</td><td>" + dd(x[2]) + '</td><td class="num">' + (x[4] == null ? "" : x[4]) + '</td><td class="num">' + (x[5] == null ? "" : x[5] + " مباراة") + "</td></tr>"; }).join("") +
        "</tbody></table></div></section>";
    }
    return out ? out + '<p class="src">من Transfermarkt عبر مجموعة salimt/football-datasets المفتوحة. المسيرة حسب البطولة لين آخر موسم كامل عندهم؛ المواسم الأحدث من FotMob فوق.</p>' : "";
  };
  R.UAE_COMPS = UAE_COMPS;
  if (typeof module !== "undefined" && module.exports) module.exports = R; else root.TR = R;
})(this);
