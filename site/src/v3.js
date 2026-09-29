/* تيفو v3 renderer layer (production copy of redesign/src/rx.js, BASE "/") (redesign/DESIGN-v3.md). Loaded after src/render.js on both sides (build_next.cjs requires it and
   the browser gets it after render.js). It never edits render.js: it wraps a few R functions and adds the v3 pieces.
   - Arabic player names (names/players_ar.json) on player-shaped nodes only: events, lineups. Latin stays the fallback.
   - Events: substitutions of one team in the same minute collapse into one line.
   - Rail cards, the hero, the competition key-art data. */
(function(root){
  "use strict";
  var R = (typeof module !== "undefined" && module.exports) ? require("./render.js") : root.TR;
  var esc = R.esc, BASE = "/";
  R.BASE = BASE;
  // W4.7: share.js (the canvas cards) loads on first use; until then callers get a stand-in whose methods load it and return a promise
  if (root && root.document && !root.TifoShare){ var me = root.document.currentScript, ssrc = me && me.src ? me.src.replace(/\/v3\.([^/]+)\.js(\?.*)?$/, "/share.$1.js") : "";
    if (ssrc && ssrc !== me.src){ var spr = null, sload = function(){ return spr || (spr = new Promise(function(ok, no){ var s = root.document.createElement("script"); s.src = ssrc; s.onload = function(){ ok(root.TifoShare); }; s.onerror = function(){ spr = null; no(new Error("share.js")); }; root.document.head.appendChild(s); })); };
      var stand = { lazy:true, preload:function(){ sload().catch(function(){}); } }; ["story", "wallpaper", "banner", "out", "card", "listCard"].forEach(function(k){ stand[k] = function(){ var a = arguments; return sload().then(function(T){ return T[k].apply(T, a); }); }; }); root.TifoShare = stand; } }
  // the prototype pages; links to them stay inside /next/, everything else goes to production
  R.PROTO = {};
  R.isProto = function(){ return false; };
  R.nx = function(href){ return href; };

  // ---- Arabic names: PN = { playerId: "الاسم" }
  var PN = (root && root.PN) || {};
  R.setNames = function(m){ PN = m || {}; };
  function ar(p){ if (p && p.id && PN[p.id] && !p._ar){ p.name_en = p.name; p.name = PN[p.id]; p._ar = 1; } }
  R.arNames = function(md){
    if (!md || md._arn) return md; md._arn = 1;
    if (md.venue && !md.venue.name_ar && PN.venue) md.venue.name_ar = PN.venue;
    if (md.referee && PN.ref && md.referee.name !== PN.ref){ md.referee.name_en = md.referee.name; md.referee.name = PN.ref; }
    (md.events || []).forEach(function(e){ ar(e.player); ar(e.assist); ar(e.player_out); });
    var L = md.lineups; if (L) ["home", "away"].forEach(function(s){ if (!L[s]) return; (L[s].starters || []).concat(L[s].subs || [], L[s].unavailable || [], L[s].coach ? [L[s].coach] : []).forEach(ar); });
    return md;
  };
  // scorer / assister lists (app.js re-renders them from fresh stats.json)
  var lead0 = R.leaders; R.leaders = function(stats){ if (stats && stats.lists) Object.keys(stats.lists).forEach(function(k){ (stats.lists[k] || []).forEach(function(r){ ar(r.player); }); }); return lead0.apply(R, arguments); };
  // squads (team pages): app.js re-renders #squad from fresh team json
  var squad0 = R.squad; R.squad = function(t){ ((t && t.squad) || []).forEach(function(g){ (g.players || []).forEach(ar); }); return squad0.apply(R, arguments); };
  // W2.3: lineup squares in each club's readable colour
  var lu0 = R.lineups; R.lineups = function(md){ var h = lu0.apply(R, arguments); if (!md || !md.home) return h; var hc = R.colOn(md.home.id), ac = R.colOn(md.away.id);
    return h.replace('<div class="pitch">', '<div class="pitch" style="--hc:' + hc + ";--hi:" + R.inkOn(hc) + ";--ac:" + ac + ";--ai:" + R.inkOn(ac) + '">'); };
  ["lineups", "catchup", "matchFacts"].forEach(function(k){ var f = R[k]; R[k] = function(md){ return f.apply(R, [R.arNames(md)].concat([].slice.call(arguments, 1))); }; });

  // ---- events: same minute + same team substitutions on one line
  var EV = { penalty_goal:"بلنتي", own_goal:"في مرماه", missed_penalty:"بلنتي ضايع", yellow:"إنذار", red:"طرد", second_yellow:"إنذار ثاني وطرد", var:"الفار" };
  function evIcon(t){ if (t === "yellow") return '<i class="ico yellow"></i>'; if (t === "red" || t === "second_yellow") return '<i class="ico red"></i>'; if (/goal/.test(t)) return '<i class="ico goal"></i>'; if (t === "missed_penalty") return '<i class="ico miss"></i>'; return '<i class="ico sub"></i>'; }
  function sc(s){ return s.home + " - " + s.away; }
  function nm(p){ return p ? '<span class="lat">' + esc(p.name) + "</span>" : ""; }
  // the source sends no substitutions for some competitions (Gulf Cup): say so in one quiet line instead of implying none were made
  function noSubs(md){ var ce = md.coverage_events; if (ce && ce.subs === false) return true; if (ce && ce.subs === true) return false;
    var mn = parseInt(md.minute, 10) || 0, late = md.status === "finished" || (R.isLive(md) && mn >= 60);
    return late && md.lineups && md.lineups.home && !(md.events || []).some(function(e){ return e.type === "sub"; }); }
  R.events = function(md){
    R.arNames(md);
    var ev = md.events || []; if (!ev.length) return '<p class="empty">' + (md.status === "scheduled" ? "المباراة ما بدت." : "ما في أحداث مسجّلة.") + "</p>";
    var rows = [];
    ev.forEach(function(e){ var last = rows[rows.length - 1];
      if (e.type === "sub" && last && last.sub && last.team === e.team && last.minute === e.minute && (last.added || 0) === (e.added || 0)){ last.list.push(e); return; }
      rows.push(e.type === "sub" ? { sub:true, team:e.team, minute:e.minute, added:e.added, list:[e] } : { e:e }); });
    if (R.isLive(md)) rows.reverse();   // W2.6: while live, the newest event on top
    return '<ul class="ev">' + rows.map(function(r){
      var e = r.e;
      if (e && e.type === "half"){ var hl = { HT:"نهاية الشوط الأول", FT:"نهاية المباراة", AET:"نهاية الوقت الإضافي", EHT:"نهاية الشوط الإضافي الأول", Pen:"ركلات الترجيح" }[e.detail] || esc(e.detail); return '<li class="div">' + hl + (e.score ? ' <span class="num">' + sc(e.score) + "</span>" : "") + "</li>"; }
      if (e && e.type === "added_time") return '<li class="div">+' + esc(e.detail) + " دقايق وقت بدل ضايع</li>";
      var body, team, mn;
      if (r.sub){
        team = r.team; mn = '<bdi dir="ltr">' + esc(r.minute) + (r.added ? "+" + esc(r.added) : "") + "'</bdi>";
        body = '<span class="sub subs"><span class="in"><i class="arr up" aria-label="دخل">↑</i>' + r.list.map(function(x){ return nm(x.player); }).join("، ") + '</span><span class="out"><i class="arr dn" aria-label="طلع">↓</i>' + r.list.map(function(x){ return nm(x.player_out); }).join("، ") + "</span></span>";
      } else {
        team = e.team; mn = '<bdi dir="ltr">' + esc(e.minute) + (e.added ? "+" + esc(e.added) : "") + "'</bdi>";
        var extra = e.assist ? '<span class="sub">صناعة ' + nm(e.assist) + "</span>" : "";
        body = '<span class="who">' + evIcon(e.type) + nm(e.player) + (/goal/.test(e.type) && e.score ? '<span class="gs">' + sc(e.score) + "</span>" : "") + (EV[e.type] ? '<span class="kind">' + EV[e.type] + "</span>" : "") + "</span>" + extra;
      }
      var k = e && /goal/.test(e.type) ? " g" : "", eid = esc((e && e.event_id) || (r.list ? r.list.map(function(x){ return x.event_id || ""; }).join("+") : ""));
      return team === "home" ? '<li class="' + k + '" data-eid="' + eid + '"><span class="h">' + body + '</span><span class="mn">' + mn + "</span><span></span></li>" : '<li class="' + k + '" data-eid="' + eid + '"><span></span><span class="mn">' + mn + "</span><span>" + body + "</span></li>";
    }).join("") + '</ul>' + (noSubs(md) ? '<p class="na">التبديلات ما وصلتنا من المصدر لهالمباراة</p>' : "") + '<p class="src"><a href="/laws/">ليش ألغى الحكم هدف أو صفّر بلنتي؟ قانون الكورة بالإماراتي</a></p>';
  };

  // ---- rail card: a match as a key-art card (club colour bands on the outer edges)
  R.railCard = function(m, o){
    o = o || {}; var live = R.isLive(m), fin = m.status === "finished", s = m.score;
    var mid = live ? '<b class="dg">' + (s ? sc(s) : "0 - 0") + '</b><span class="st live"><i class="cardflip"></i>' + R.minute(m) + "</span>"
      : s ? '<b class="dg">' + sc(s) + '</b><span class="st">' + R.statusText(m) + "</span>"
      : '<b class="dg">' + (m.time_tbd ? "—" : R.tt(m.kickoff_uae)) + '</b><span class="st">' + R.td(m.kickoff_uae) + "</span>";
    var mine = o.mine && (m.home.id === o.mine || m.away.id === o.mine);
    return '<a class="rc' + (live ? " live" : "") + (mine ? " mine" : "") + '" href="' + R.nx("/m/" + m.id + "/") + '" data-mid="' + m.id + '" style="--hc:' + R.colOn(m.home.id) + ";--ac:" + R.colOn(m.away.id) + '">' +
      '<span class="cp">' + esc(o.comp || m.comp_name_ar || "") + "</span>" +
      '<span class="rt3"><span class="t' + (fin && s && s.home > s.away ? " win" : "") + '">' + R.logo(m.home, "md") + "<span>" + R.tname(m.home) + '</span></span><span class="mid">' + mid + '</span><span class="t' + (fin && s && s.away > s.home ? " win" : "") + '">' + R.logo(m.away, "md") + "<span>" + R.tname(m.away) + "</span></span></span>" + R.chan(m) + "</a>";
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
    // W2.5: the hero match is in no rail, and a match appears in one rail at most (live, then today, then Arab)
    var used = {}; if (o.exclude) used[o.exclude] = 1; var take = function(list, n){ var out = []; list.forEach(function(m){ if (out.length < n && !used[m.id]){ used[m.id] = 1; out.push(m); } }); return out; };
    var L = take(live, 20), T = take(up.slice().sort(big), 14).concat(take(fin, 6)), A = take(arab, 16);
    return { live:L.map(card).join(""), today:T.map(card).join(""), arab:A.map(card).join(""), n:{ live:L.length, up:T.length, arab:A.length } };
  };
  // hero choice: live (UAE / Arab first) -> the visitor's team today -> tonight's biggest (UAE national, Arab national, UAE clubs, big European)
  // W2.1 (388): one rule for the hero, at build time and in the browser, no hard-coded team:
  // 1) my team live · 2) my team or my country's national team from 3 h before kickoff to 6 h after · 3) an Arab match live · 4) tonight's biggest
  R.heroPick = function(ms, index, mine, nat){
    ms = (ms || []).filter(function(m){ return m.status !== "cancelled"; }); if (!ms.length) return null;
    var cc = {}; (index.competitions || []).forEach(function(c){ cc[c.id] = R.compCountry(c); });
    var AT = R.ARABT || (root && root.ARABT) || {}, now = Date.now(), has = function(m, id){   /* QA 19: the build sets R.ARABT, so its pick matches the browser's */ return id && (m.home.id === id || m.away.id === id); };
    var near = function(m){ var t = Date.parse(m.kickoff_utc); return R.isLive(m) || (t - now < 3 * 3600e3 && now - t < 8 * 3600e3); };
    var arab = function(m){ return ARABC[cc[m.comp]] || AT[m.home.id] || AT[m.away.id] || [329, 10242, 11156, 10474].indexOf(m.comp) >= 0; };
    var tier = function(m){ if (R.isLive(m) && has(m, mine)) return 4; if ((has(m, mine) || has(m, nat)) && near(m)) return 3; if (R.isLive(m) && arab(m)) return 2; return 1; };
    var big = function(m){ var s = 0; if ([329, 10242, 11156, 290, 10197, 77].indexOf(m.comp) >= 0) s += 80; if (arab(m)) s += 40; if ([525, 42, 47, 87].indexOf(m.comp) >= 0) s += 30; if (R.isLive(m)) s += 25; if (m.status === "scheduled") s += 15; if (m.status === "finished") s -= 20; return s; };
    return ms.slice().sort(function(a, b){ return tier(b) - tier(a) || big(b) - big(a) || (a.kickoff_utc || "").localeCompare(b.kickoff_utc || ""); })[0];
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
  // W4.8 feed: the live clock ticks between polls: period_base + time since period_start (frozen when period_start is null)
  R.clock = function(ps, pb, pl){ var e = Math.max(0, Math.floor((Date.now() - Date.parse(ps)) / 60000)); pl = +pl || 45; pb = +pb || 0; return e < pl ? (pb + e + 1) + "'" : (pb + pl) + "+" + (e - pl + 1) + "'"; };
  // period codes in Arabic everywhere (a feed minute of "HT" never reaches the page)
  var PER = { "1H":"الشوط الأول", "2H":"الشوط الثاني", ET1:"الشوط الإضافي الأول", ET2:"الشوط الإضافي الثاني", HT:"استراحة", BREAK:"استراحة", PEN:"ركلات الترجيح", PENS:"ركلات الترجيح", FT:"انتهت", AET:"بعد الإضافي", ET:"الوقت الإضافي" };
  R.periodAr = function(c){ return PER[String(c || "").toUpperCase()] || ""; };
  var min0 = R.minute; R.minute = function(m){ if (m && (m.status === "ht" || R.periodAr(m.minute) || (m.period && /^(HT|break)$/i.test(m.period)))) return R.periodAr(m.status === "ht" ? "HT" : m.minute) || R.periodAr(m.period) || "استراحة"; if (m && m.period_start && m.period_base != null && /^(1H|2H|ET1|ET2)$/.test(m.period || "")) return '<bdi dir="ltr" class="lmin" data-ps="' + esc(m.period_start) + '" data-pb="' + m.period_base + '" data-pl="' + (m.period_length || 45) + '">' + R.clock(m.period_start, m.period_base, m.period_length) + "</bdi>"; return min0(m); };
  // W2.7: positions in Arabic (squads, player pages)
  var POS = { GK:"حارس", G:"حارس", CB:"قلب دفاع", LB:"ظهير أيسر", RB:"ظهير أيمن", LWB:"ظهير أيسر", RWB:"ظهير أيمن", DM:"وسط دفاعي", CDM:"وسط دفاعي", CM:"وسط", LM:"وسط أيسر", RM:"وسط أيمن", AM:"وسط هجومي", CAM:"وسط هجومي", LW:"جناح أيسر", RW:"جناح أيمن", ST:"مهاجم", CF:"مهاجم", SS:"مهاجم ثاني", D:"مدافع", DF:"مدافع", M:"وسط", MF:"وسط", F:"مهاجم", FW:"مهاجم", GOALKEEPER:"حارس", KEEPER:"حارس", DEFENDER:"مدافع", MIDFIELDER:"وسط", FORWARD:"مهاجم", ATTACKER:"مهاجم" };
  R.pos = function(p){ var k = String(p || "").split(",")[0].trim().toUpperCase(); return POS[k] || (/[\u0600-\u06FF]/.test(p) ? p : ""); };
  R.PP = (root && root.PP) || null;
  // W2.7: on team pages every fixture row carries its competition's crest
  var mr0 = R.matchRow; R.matchRow = function(m, o){ var h = mr0.apply(R, arguments).replace(/<\/(a|div)>$/, function(x){ return R.chan(m) + x; }), team = (o && o.crest) || (root && root.document && root.document.body && root.document.body.dataset.page === "team");
    // W4.6: one spoken line per row («اليمن 0، قطر 1، مباشر الدقيقة 86»); client re-renders rebuild it with the row
    if (m && m.home && m.away && /^<a /.test(h)){ var hn = m.home.name_ar || m.home.name || "", an = m.away.name_ar || m.away.name || "", s = m.score, mn = String(m.minute || "").replace(/'/g, ""), st = R.isLive(m) ? "مباشر" + (mn ? " " + ((R.periodAr && R.periodAr(mn)) || "الدقيقة " + mn) : "") : m.status === "finished" ? "انتهت" : m.status === "scheduled" ? (m.time_tbd ? "الموعد مب محدد" : "الساعة " + R.hhmm(m.kickoff_uae)) : "";
      var lbl = s && m.status !== "scheduled" ? hn + " " + s.home + "، " + an + " " + s.away : hn + " ضد " + an; h = h.replace(/^<a /, '<a aria-label="' + esc(lbl + (st ? "، " + st : "")) + '" '); }
    return team && m && m.comp ? h.replace(/(<span class="t h[^"]*">)/, '$1<img class="clg" src="/lg/' + m.comp + '.png" alt="" loading="lazy" onerror="this.remove()">') : h; };
  // W3.4: the visitor's channel on every upcoming or live row: the first broadcaster in their country (+ «مشفرة» when none of its broadcasters is free; owner 2026-09-30: never «مجاني»); UAE in the prerender
  R.CHN = (root && root.CHN_AE) || {};
  R.chan = function(m){ if (!m || m.status === "finished" || !m.comp) return ""; var c = R.CHN[m.comp]; if (!c) return ""; return '<span class="chn" data-comp="' + m.comp + '">' + esc(c[0]) + (c[1] ? "" : ' <b>مشفرة</b>') + "</span>"; };
  // W2.10: Arabic counts — 1 and 2 have their own forms, 3–10 take the plural, 11+ the singular; 0 hides the line
  R.n = function(k, f){ k = +k || 0; if (!k) return ""; if (k === 1) return f[0]; if (k === 2) return f[1]; return k + " " + (k <= 10 ? f[2] : f[3]); };
  // W2.10: one kicker for a match everywhere: مباشر الحين / انتهت / الليلة / اليوم 15:00 / بكرة / the weekday
  R.kick = function(m){ if (!m) return "اليوم"; if (R.isLive(m)) return "مباشر الحين"; if (m.status === "finished") return "انتهت"; if (!m.kickoff_uae) return "الموعد ما تأكد";
    var today = R.TZ ? R.ymd(new Date().toISOString()) : new Date(Date.now() + 4 * 3600e3).toISOString().slice(0, 10), d = R.ymd(m.kickoff_uae), diff = Math.round((Date.parse(d) - Date.parse(today)) / 864e5), hh = +R.hhmm(m.kickoff_uae).slice(0, 2);
    if (diff <= 0) return hh >= 17 ? "الليلة" : "اليوم " + R.hhmm(m.kickoff_uae); if (diff === 1) return "بكرة"; return String(R.dayLabel(d)).split(" ")[0]; };
  // W2.10: «لـال…» -> «لل…»
  R.li = function(s){ return String(s).replace(/لـال/g, "لل").replace(/لـ ال/g, "لل"); };
  // 397: club names the feed has no Arabic for (names/clubs_ar.json via window.TAR)
  var TAR = (root && root.TAR) || {}; R.setClubNames = function(m){ TAR = m || {}; };
  var DUP = (root && root.DUP) || {}; R.setDup = function(m){ DUP = m || {}; };
  // 503: no country tag on a page whose context is that country (its league, rounds, clubs, players, their matches): the build sets R.DUPCTX, the page carries data-dupctx
  function dupCtx(){ if (R.DUPCTX != null) return R.DUPCTX; var b = root && root.document && root.document.body; return (b && b.dataset && b.dataset.dupctx) || ""; }
  var tname0 = R.tname; R.tname = function(t){ var sl = t && !t.name_ar && R.slotAr && R.slotAr(t.name); if (sl) return esc(sl); var n = t && !t.name_ar && TAR[t.id] ? esc(TAR[t.id]) : tname0(t); return t && DUP[t.id] && DUP[t.id] !== dupCtx() ? n + " ·\u00a0" + esc(DUP[t.id]) : n; };   /* QA 101: the dot stays with its country; 503: the line may break before it (a long name + country tag pushed the away team off a phone match header) */   // W2.7: «النصر · السعودية»
  // 391: when «ليش هالنتيجة؟» is on the page, the catch-up keeps only what it doesn't say (red cards, a missed penalty, a comeback)
  var catch0 = R.catchup; R.catchup = function(md){ var h = catch0.apply(R, arguments); if (!R._hasWhy || !h) return h;
    // QA 81: a kept line the why text already tells (the missed penalty, the red card, the minute) goes too
    var wt = typeof R._hasWhy === "string" ? R._hasWhy : "", told = function(p){ if (!wt) return false; var t = p.replace(/<[^>]+>/g, ""), mn = (t.match(/(\d+)/) || [])[1];
      return (/بلنتي/.test(t) && /بلنتي|ركلة جزاء/.test(wt)) || (/طرد/.test(t) && /طرد|الأحمر|بعشرة/.test(wt)) || (/ريمونتادا/.test(t) && /ريمونتادا|قلب/.test(wt)) || (mn && new RegExp("(^|[^0-9])" + mn + "([^0-9]|$)").test(wt) && /دقيقة|د\s*\d/.test(wt)); };
    var keep = (h.match(/<p>[^<]*<\/p>/g) || []).filter(function(p){ return /^<p>(طرد|بلنتي ضايع|ريمونتادا)/.test(p) && !told(p); });
    return keep.length ? '<div class="catchup mini">' + keep.join("") + "</div>" : ""; };
  // 392: the event squares leave the hero (they moved to التحليل as «خط المباراة»); 400: the score in scoreboard cells
  var cells = function(t){ return String(t).replace(/(\d)/g, '<i class="cell">$1</i>'); };
  var vt = function(h){ var n = 0; return h.replace(/<img class="logo (lg|xl)" src="[^"]*\/logo\/(\d+)\.png"/g, function(m, c, id){ return n++ < 2 ? m + ' style="view-transition-name:crest-' + id + '"' : m; }); };
  var head0 = R.matchHead; R.matchHead = function(md){ var h = vt(head0.apply(R, arguments).replace(/<div class="timeline">[\s\S]*$/, ""));
    h = h.replace(/(<div class="sc"><span class="dg">)([^<]*)(<\/span>)/, function(_, a, t, b){ return a + cells(t) + b; });
    // the countdown's line is part of the first paint (it used to be appended after load and moved the hero)
    if (md && md.status === "scheduled" && md.kickoff_utc && !md.time_tbd) h = h.replace(/(<div class="sc">[\s\S]*?<span class="st">[\s\S]*?<\/span>)(<\/div>)/, '$1<span class="mcd"></span>$2');
    return h; };
  var hl0 = R.heroLine; R.heroLine = function(){ return vt(hl0.apply(R, arguments)).replace(/(<b class="dg big">)([^<]*)(<\/b>)/, function(_, a, t, b){ return a + cells(t) + b; }); };
  // 395: zones as a thin coloured edge on the row, not a filled square behind the rank
  var TIER = ["#F6F7F2", "#F6F7F2A6", "#F6F7F266", "#A7B6AF"];
  var st0 = R.standings; R.standings = function(){ var h = st0.apply(R, arguments), order = [];
    (h.match(/<td class="rk"><span style="background:[^;"]+/g) || []).forEach(function(x){ var c = x.split("background:")[1]; if (order.indexOf(c) < 0) order.push(c); });
    var red = function(c){ var n = parseInt(String(c).replace("#", "").slice(0, 6), 16), r = n >> 16, g = n >> 8 & 255, b = n & 255; return r > 150 && g < 110 && b < 110; };
    var tierOf = function(c){ if (red(c)) return "rel"; var i = order.filter(function(x){ return !red(x); }).indexOf(c); return TIER[Math.min(i, TIER.length - 1)]; };
    return h.replace(/<td class="rk"><span style="background:([^;"]+);color:[^"]*">/g, function(_, c){ var t = tierOf(c); return t === "rel" ? '<td class="rk z rel"><span>' : '<td class="rk z" style="--z:' + t + '"><span>'; })
      .replace(/<span><i style="background:([^"]+)"><\/i>/g, function(_, c){ var t = tierOf(c); return t === "rel" ? '<span><i class="zrel"></i>' : '<span><i style="background:' + t + '"></i>'; }); };
  // QA 70/75/79/88: one Arabic counting helper: 0 → the zero phrase, 1 → singular, 2 → dual, 3–10 → «N plural», 11+ → «N singular»
  R.cnt = function(n, f, zero){ n = +n || 0; if (!n) return zero != null ? zero : "0 " + f[3]; return R.n(n, f); };
  // QA 70/78: «الليلة» only for today from 17:00, «اليوم» earlier today, «بكرة», else the weekday (the rule in gen.py day_word), in the viewer's zone
  var WD = ["الأحد","الإثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت"];
  R.dayWord = function(ko, now){ var t = Date.parse(ko); if (!t) return "اليوم"; var tz = R.TZ || "Asia/Dubai", ymd = function(ms){ return new Date(ms).toLocaleDateString("en-CA", { timeZone:tz }); }, n = now || Date.now();
    var h = +new Date(t).toLocaleTimeString("en-GB", { timeZone:tz, hour:"2-digit", hourCycle:"h23" }).slice(0, 2);
    if (ymd(t) === ymd(n)) return h >= 17 ? "الليلة" : "اليوم"; if (ymd(t) === ymd(n + 864e5)) return "بكرة";
    return WD[+new Date(new Date(t).toLocaleDateString("en-CA", { timeZone:tz }) + "T12:00:00Z").getUTCDay()]; };
  // 417 «تيفو الأسبوع» on /week/: the week in up to 5 numbers (weekly.py -> /og/week-latest.json). The build prerenders it with links
  // (the dead-link pass cleans any that have no page); the browser only draws it when the build had no file yet, and then without links.
  // Scores keep the scoreboard chip; counts are plain numerals (rule 13).
  var WMON = ["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"];
  function wdate(s){ var p = String(s || "").split("-"); return p.length === 3 ? '<span class="num">' + (+p[2]) + "</span> " + WMON[+p[1] - 1] : ""; }
  function wunit(k, v){ var n = parseFloat(v); if (isNaN(n)) return ""; if (k === "top_scorer") return n === 1 ? "هدف" : n === 2 ? "هدفين" : n <= 10 ? "أهداف" : "هدف";
    if (k === "streak") return n === 1 ? "مباراة" : n === 2 ? "مباراتين" : n <= 10 ? "مباريات" : "مباراة"; if (k === "leader_change") return n === 1 ? "نقطة" : n === 2 ? "نقطتين" : n <= 10 ? "نقاط" : "نقطة"; if (k === "arab_star") return "التقييم"; return ""; }
  R.weekCard = function(j, o){ o = o || {}; var it = (j && j.items) || []; if (!it.length) return "";
    var rows = it.slice(0, 5).map(function(x){ var score = x.kind === "biggest_win" && /^\d+\s*-\s*\d+$/.test(String(x.value || "")), u = wunit(x.kind, x.value);
      var val = score ? '<b class="wkv sc"><bdi dir="ltr">' + esc(x.value) + "</bdi></b>" : x.kind === "arab_star" ? '<b class="wkv"><small>' + u + '</small> <span class="num">' + esc(x.value) + "</span></b>" : '<b class="wkv"><span class="num">' + esc(x.value) + "</span>" + (u ? " <small>" + u + "</small>" : "") + "</b>";
      var href = o.links ? (x.match ? "/m/" + x.match + "/" : x.player ? "/p/" + x.player + "/" : x.team ? "/t/" + x.team + "/" : "") : "", tag = href ? "a" : "div";
      return "<" + tag + ' class="wkr"' + (href ? ' href="' + href + '"' : "") + ">" + (x.team ? R.logo({ id:x.team }, "sm") : '<span class="wkdot" aria-hidden="true"></span>') + '<span class="wkt"><small>' + esc(x.label || "") + "</small><b>" + esc(x.text || "") + "</b>" + (x.sub ? "<span>" + esc(x.sub) + "</span>" : "") + "</span>" + val + "</" + tag + ">"; }).join("");
    var star = it.some(function(x){ return x.kind === "arab_star"; });
    return '<section class="blk wkcard" id="wkcard" data-week="' + esc(j.week || "") + '"><h2>تيفو الأسبوع<small>' + wdate(j.from) + " – " + wdate(j.to) + "</small></h2>" + rows +
      '<p class="wkdl"><a href="/og/week-latest-story.png" download="tifo-week-' + esc(j.week || "") + '-story.png">صورة ستوري</a><a href="/og/week-latest-feed.png" download="tifo-week-' + esc(j.week || "") + '-feed.png">صورة بوست</a>' + (star ? '<a href="/og/arab-star-latest.png" download="tifo-arab-star-' + esc(j.week || "") + '.png">بطاقة نجم العرب</a>' : "") + "</p></section>"; };

  if (typeof module !== "undefined" && module.exports) module.exports = R;
  else {
    // app.js drives the home hero through R.featured + R.standCap + TifoStand; v3 swaps in its own pick and title treatment
    var mine = function(){ try { return +localStorage.getItem("tifo.mine") || null; } catch (e){ return null; } };
    var nat = function(){ var c = null; try { c = localStorage.getItem("tifo.country"); } catch (e){} if (!c){ try { var tz = Intl.DateTimeFormat().resolvedOptions().timeZone, hit = R.COUNTRIES.filter(function(x){ return x[2] === tz; })[0]; c = hit ? hit[0] : null; } catch (e){} } return c && root.NAT ? root.NAT[c] : null; };
    R.featured = function(ms){ return R.heroPick(ms, R._idx || {}, mine(), nat()); };
    R.standCap = function(m){ return R.heroLine(m, R._idx); };
  }
})(this);
