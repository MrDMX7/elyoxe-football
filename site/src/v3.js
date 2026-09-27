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
      var k = e && /goal/.test(e.type) ? " g" : "";
      return team === "home" ? '<li class="' + k + '"><span class="h">' + body + '</span><span class="mn">' + mn + "</span><span></span></li>" : '<li class="' + k + '"><span></span><span class="mn">' + mn + "</span><span>" + body + "</span></li>";
    }).join("") + '</ul>' + (noSubs(md) ? '<p class="na">التبديلات ما وصلتنا من المصدر لهالمباراة</p>' : "") + '<p class="src"><a href="/laws/">ليش ألغى الحكم هدف أو صفّر بلنتي؟ قانون الكورة بالإماراتي</a></p>';
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
  // 397: club names the feed has no Arabic for (names/clubs_ar.json via window.TAR)
  var TAR = (root && root.TAR) || {}; R.setClubNames = function(m){ TAR = m || {}; };
  var tname0 = R.tname; R.tname = function(t){ return t && !t.name_ar && TAR[t.id] ? esc(TAR[t.id]) : tname0(t); };
  // 391: when «ليش هالنتيجة؟» is on the page, the catch-up keeps only what it doesn't say (red cards, a missed penalty, a comeback)
  var catch0 = R.catchup; R.catchup = function(md){ var h = catch0.apply(R, arguments); if (!R._hasWhy || !h) return h;
    var keep = (h.match(/<p>[^<]*<\/p>/g) || []).filter(function(p){ return /^<p>(طرد|بلنتي ضايع|ريمونتادا)/.test(p); });
    return keep.length ? '<div class="catchup mini">' + keep.join("") + "</div>" : ""; };
  // 392: the event squares leave the hero (they moved to التحليل as «خط المباراة»); 400: the score in scoreboard cells
  var cells = function(t){ return String(t).replace(/(\d)/g, '<i class="cell">$1</i>'); };
  var head0 = R.matchHead; R.matchHead = function(md){ var h = head0.apply(R, arguments).replace(/<div class="timeline">[\s\S]*$/, "");
    return h.replace(/(<div class="sc"><span class="dg">)([^<]*)(<\/span>)/, function(_, a, t, b){ return a + cells(t) + b; }); };
  var hl0 = R.heroLine; R.heroLine = function(){ return hl0.apply(R, arguments).replace(/(<b class="dg big">)([^<]*)(<\/b>)/, function(_, a, t, b){ return a + cells(t) + b; }); };
  // 395: zones as a thin coloured edge on the row, not a filled square behind the rank
  var st0 = R.standings; R.standings = function(){ return st0.apply(R, arguments).replace(/<td class="rk"><span style="background:([^;"]+);color:[^"]*">/g, '<td class="rk z" style="--z:$1"><span>'); };
  if (typeof module !== "undefined" && module.exports) module.exports = R;
  else {
    // app.js drives the home hero through R.featured + R.standCap + TifoStand; v3 swaps in its own pick and title treatment
    var mine = function(){ try { return +localStorage.getItem("tifo.mine") || null; } catch (e){ return null; } };
    R.featured = function(ms){ return R.heroPick(ms, R._idx || {}, mine()); };
    R.standCap = function(m){ return R.heroLine(m, R._idx); };
  }
})(this);
