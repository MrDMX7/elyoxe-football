/* تيفو «مباريات اليوم والقنوات الناقلة والمعلقين» (owner 2026-10-06, item 9): one UAE day of every match, v1/all/<ymd>.json
   (compute/allday.py: FotMob's whole day list + 365Scores' Arab leagues, ours first), with each match's channel and commentator
   from v1/tv/<ymd>.json (news/commentators.py, Kooora's daily table ~01:00 UAE) and each competition's channels per country
   (research broadcast_by_country.json, the build's /assets/bc.<v>.json).
   One copy for both sides, like src/render.js: site/lib/seo_days.cjs prerenders /today/, /tomorrow/, /yesterday/ and
   /matches/<yyyy-mm-dd>/ with it (the UAE, Saudi, Egyptian and Moroccan kick-off times printed in the HTML), and the browser
   re-renders the same blocks: the visitor's clock and country first, live scores every 30 s, the day file every 2 min, the
   commentators when they land, and the next day at midnight without waiting for the hourly build.
   Markup follows v5's components (site/redesign/v5/src/ui.js: section.grp > .gh + .card, a.mr match rows, .sc score run)
   so the v5 shell styles it as is; src/seo.css styles it under the v3 shell. Scores are one dir="rtl" run «1 - 0». */
(function(root){
  "use strict";
  var D = {};
  var esc = D.esc = function(s){ return s == null ? "" : String(s).replace(/[&<>"']/g, function(c){ return { "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]; }); };
  var DAY = ["الأحد","الاثنين","الثلاثاء","الأربعاء","الخميس","الجمعة","السبت"];
  var MON = ["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"];
  // the four clocks every match prints (owner: «UAE/KSA/Egypt/Morocco times in the static HTML»)
  D.ZONES = [["AE","الإمارات","Asia/Dubai"],["SA","السعودية","Asia/Riyadh"],["EG","مصر","Africa/Cairo"],["MA","المغرب","Africa/Casablanca"]];
  // the 22 Arab League countries: code, name, time zone (the same list as render.js R.COUNTRIES)
  D.COUNTRIES = [["AE","الإمارات","Asia/Dubai"],["SA","السعودية","Asia/Riyadh"],["EG","مصر","Africa/Cairo"],["MA","المغرب","Africa/Casablanca"],["DZ","الجزائر","Africa/Algiers"],["TN","تونس","Africa/Tunis"],["IQ","العراق","Asia/Baghdad"],["JO","الأردن","Asia/Amman"],["KW","الكويت","Asia/Kuwait"],["QA","قطر","Asia/Qatar"],["BH","البحرين","Asia/Bahrain"],["OM","عُمان","Asia/Muscat"],["LB","لبنان","Asia/Beirut"],["SY","سوريا","Asia/Damascus"],["PS","فلسطين","Asia/Hebron"],["YE","اليمن","Asia/Aden"],["LY","ليبيا","Africa/Tripoli"],["SD","السودان","Africa/Khartoum"],["MR","موريتانيا","Africa/Nouakchott"],["SO","الصومال","Africa/Mogadishu"],["DJ","جيبوتي","Africa/Djibouti"],["KM","جزر القمر","Indian/Comoro"]];
  var ARAB_CC = "UAE KSA QAT KUW BHR OMA IRQ JOR SYR LBN LIB PLE YEM EGY SUD LBY TUN ALG MAR MTN SOM DJI COM".split(" ");
  var LIVE = { live:1, ht:1 };
  var S365 = "https://imagecache.365scores.com/image/upload/f_png,w_48,h_48,c_limit,q_auto:eco,dpr_2,d_Competitors:default1.png/v1/Competitors/";

  // ------------------------------------------------------------------ dates and clocks (Intl: correct summer time for every zone)
  var FMT = {};
  function fmt(k, tz, o){ return FMT[k + tz] || (FMT[k + tz] = new Intl.DateTimeFormat(k === "d" ? "en-CA" : "en-GB", Object.assign({ timeZone:tz }, o))); }
  D.hm = function(utc, tz){ var t = Date.parse(utc); if (isNaN(t)) return ""; return fmt("t", tz || "Asia/Dubai", { hour:"2-digit", minute:"2-digit", hourCycle:"h23" }).format(new Date(t)).replace(/^24/, "00"); };
  D.ymdIn = function(utc, tz){ var t = Date.parse(utc); if (isNaN(t)) return ""; return fmt("d", tz || "Asia/Dubai", { year:"numeric", month:"2-digit", day:"2-digit" }).format(new Date(t)).replace(/-/g, ""); };
  D.uaeYmd = function(off, now){ return new Date((now || Date.now()) + 4 * 3600e3 + (off || 0) * 864e5).toISOString().slice(0, 10).replace(/-/g, ""); };
  D.iso = function(ymd){ return ymd.slice(0, 4) + "-" + ymd.slice(4, 6) + "-" + ymd.slice(6, 8); };
  D.shift = function(ymd, k){ var d = new Date(Date.UTC(+ymd.slice(0, 4), +ymd.slice(4, 6) - 1, +ymd.slice(6, 8) + k)); return d.toISOString().slice(0, 10).replace(/-/g, ""); };
  // «الثلاثاء 6 أكتوبر 2026» (Western digits, as everywhere on Tifo)
  D.fullDate = function(ymd, noYear){ var y = +ymd.slice(0, 4), m = +ymd.slice(4, 6), d = +ymd.slice(6, 8); return DAY[new Date(Date.UTC(y, m - 1, d)).getUTCDay()] + " " + d + " " + MON[m - 1] + (noYear ? "" : " " + y); };
  D.dayMonth = function(ymd){ return +ymd.slice(6, 8) + " " + MON[+ymd.slice(4, 6) - 1]; };
  // the four clocks of a kick-off, equal ones together: «الإمارات 22:00 · السعودية ومصر 21:00 · المغرب 19:00»
  // a clock that falls on another calendar day than the UAE's (the day the files and pages are cut by) says so: «المغرب 23:00 (أمس)»
  D.clocks = function(utc){ var g = [], base = D.ymdIn(utc, "Asia/Dubai"); D.ZONES.forEach(function(z){ var t = D.hm(utc, z[2]), dy = D.ymdIn(utc, z[2]), k = t + dy, x = g.filter(function(y){ return y.k === k; })[0]; if (!t) return;
      if (x) x.n.push(z[1]); else g.push({ k:k, t:t, n:[z[1]], o:dy !== base ? (dy < base ? "أمس" : "بكرة") : "" }); });
    return g.map(function(x){ return x.n.join(" و") + ' <b class="num">' + x.t + "</b>" + (x.o ? " (" + x.o + ")" : ""); }).join(" · "); };
  D.clocksText = function(utc){ var g = []; D.ZONES.forEach(function(z){ var t = D.hm(utc, z[2]), x = g.filter(function(y){ return y.t === t; })[0]; if (x) x.n.push(z[1]); else g.push({ t:t, n:[z[1]] }); });
    return g.map(function(x, i){ return (i ? "" : "الساعة ") + x.t + " بتوقيت " + x.n.join(" و"); }).join("، "); };

  // ------------------------------------------------------------------ labels
  var ORD = { A:"الأولى", B:"الثانية", C:"الثالثة", D:"الرابعة", E:"الخامسة", F:"السادسة", G:"السابعة", H:"الثامنة", I:"التاسعة", J:"العاشرة", K:"الحادية عشرة", L:"الثانية عشرة", "1":"الأولى", "2":"الثانية", "3":"الثالثة", "4":"الرابعة", "5":"الخامسة", "6":"السادسة", "7":"السابعة", "8":"الثامنة" };
  D.group = function(g){ var s = String(g || "").trim(), m = /^Gr(?:ou)?p\.?\s*([A-Za-z0-9]{1,2})$/i.exec(s); if (m) return "المجموعة " + (ORD[m[1].toUpperCase()] || m[1]);
    if (/^(1\/2|semi)/i.test(s)) return "نصف النهائي"; if (/^(1\/4|quarter)/i.test(s)) return "ربع النهائي"; if (/^(1\/8|round of 16)/i.test(s)) return "دور الـ16"; if (/^final$/i.test(s)) return "النهائي";
    if (/play-?off/i.test(s)) return "الملحق"; if (/^(east|west)$/i.test(s)) return /^e/i.test(s) ? "منطقة الشرق" : "منطقة الغرب"; return /[؀-ۿ]/.test(s) ? s : ""; };
  D.isArab = function(lg){ return ARAB_CC.indexOf(lg.cc) >= 0 || lg.src === "365" || /^365:/.test(String(lg.id)); };
  var STATUS_AR = { postponed:"تأجلت", cancelled:"ألغيت", abandoned:"توقفت", suspended:"توقفت", interrupted:"توقفت", awarded:"قرار إداري" };

  // ------------------------------------------------------------------ one match
  function scoreRun(h, a){ return '<span class="sc" dir="rtl">' + esc(h) + " - " + esc(a) + "</span>"; }
  function hasScore(m){ return m.home && m.away && m.home.length > 2 && m.away.length > 2 && m.home[2] != null && m.away[2] != null; }
  D.minute = function(m){ return m.status === "ht" ? "استراحة" : m.minute ? '<bdi dir="ltr" class="num">' + esc(String(m.minute).replace(/'/g, "")) + "'</bdi>" : "مباشر"; };
  // the middle of the row: the kick-off (a <time> the browser rewrites in the visitor's zone), the live score and minute, the result
  D.mid = function(m, ctx){
    var s = m.status;
    if (LIVE[s]) return (hasScore(m) ? scoreRun(m.home[2], m.away[2]) : scoreRun(0, 0)) + '<span class="st live"><i class="dot"></i>' + D.minute(m) + "</span>";
    if (s === "finished" && hasScore(m)) return scoreRun(m.home[2], m.away[2]) + '<span class="st">' + (m.pen ? 'ترجيح <span class="num" dir="rtl">' + esc(m.pen[0]) + " - " + esc(m.pen[1]) + "</span>" : m.sd === "AET" ? "بعد الإضافي" : "انتهت") + "</span>";
    if (STATUS_AR[s]) return (hasScore(m) ? scoreRun(m.home[2], m.away[2]) : '<span class="sc tbd">—</span>') + '<span class="st">' + STATUS_AR[s] + "</span>";
    if (s !== "scheduled" || !m.utc) return '<span class="sc tbd">—</span>';
    if (m.tbd) return '<span class="sc tbd">—</span><span class="st">الساعة ما تحددت</span>';
    // a kick-off on another calendar day in the visitor's zone (or a fixture days away) says which day
    var tz = (ctx && ctx.tz) || "Asia/Dubai", ky = D.ymdIn(m.utc, tz), other = "";
    if (ctx && ctx.ymd && ky !== ctx.ymd) other = ky === D.shift(ctx.ymd, 1) ? "بكرة" : ky === D.shift(ctx.ymd, -1) ? "أمس" : D.dayMonth(ky);
    return '<span class="sc ko"><time data-u="' + esc(m.utc) + '" data-f="t">' + D.hm(m.utc, tz) + "</time></span>" + (other ? '<span class="st">' + other + "</span>" : "");
  };
  D.href = function(m, lg, ctx){ var id = String(m.id);
    if (id.indexOf("365:") === 0) return "/db/game/?id=" + id.slice(4);
    if ((m.ours || lg.ours) && (!ctx.hasPage || ctx.hasPage(id))) return "/m/" + id + "/";
    return "/live/?id=" + id + "&d=" + ctx.ymd; };
  function crest(t, own, ctx){ var id = String(t[0] == null ? "" : t[0]); if (!id) return "";
    if (id.indexOf("365:") === 0) return '<img class="cr" src="' + S365 + id.slice(4) + '" alt="" width="24" height="24" loading="lazy" onerror="this.style.visibility=\'hidden\'">';
    if (!own || (ctx.logoOk && !ctx.logoOk(+id))) return "";
    return '<img class="cr" src="/logo/96/' + id + '.webp" alt="" width="24" height="24" loading="lazy" onerror="if(!this.dataset.f){this.dataset.f=1;this.src=\'/logo/' + id + '.png\'}else this.style.visibility=\'hidden\'">'; }
  // a match's channel and voice from the commentators file: the visitor's country first, then pan-Arab networks, a named voice first
  D.lead = function(es, cc){ var rk = function(e){ return (e.country && e.country === cc ? 0 : !e.country ? 1 : 2) + (e.commentator || (e.commentators || []).length ? 0 : .5); };
    return (es || []).map(function(e, i){ return [rk(e), i, e]; }).sort(function(a, b){ return a[0] - b[0] || a[1] - b[1]; }).map(function(x){ return x[2]; }); };
  function voices(e){ var n = e.commentators && e.commentators.length ? e.commentators : e.commentator ? [e.commentator] : []; return n.map(esc).join(" و"); }
  D.chan = function(m, ctx, plain){ var es = ctx.tv && ctx.tv[String(m.id)]; if (!es || !es.length) return "";
    var s = D.lead(es, ctx.cc), top = s[0], v = voices(s.filter(function(e){ return voices(e); })[0] || {}), chs = [];
    s.forEach(function(e){ if (e.channel && chs.indexOf(e.channel) < 0 && chs.length < 2) chs.push(e.channel); });
    if (plain) return { ch:chs.join("، "), v:v.replace(/&amp;/g, "&") };
    return '<span class="tvx">' + (chs.length ? "📺 " + chs.map(esc).join("، ") : "") + (v ? (chs.length ? " · " : "") + "🎙 " + v : "") + "</span>"; };
  // compact: the competitions outside ours, the Arab world and the international ones (lower divisions abroad, the long tail)
  // keep the row and drop the clocks line, so a 700-match Saturday stays a light page
  D.row = function(m, lg, ctx, compact){
    var s = m.status, fin = s === "finished" && hasScore(m), hs = fin ? m.home[2] : 0, as = fin ? m.away[2] : 0;
    var hw = fin && (hs > as || (hs === as && m.pen && m.pen[0] > m.pen[1])), aw = fin && (as > hs || (hs === as && m.pen && m.pen[1] > m.pen[0]));
    var own = !!(lg.ours || m.ours), live = !!LIVE[s];
    var side = function(t, k, w, l){ var n = '<span class="tn">' + esc(t[1] || "") + (t[3] ? '<i class="rcd" title="طرد" aria-label="' + t[3] + ' طرد"></i>' : "") + "</span>", c = crest(t, own, ctx);
      return '<span class="mr-t ' + k + (w ? " w" : l ? " l" : "") + '">' + (k === "h" ? n + c : c + n) + "</span>"; };
    var x = [];
    if (!compact && ((s === "scheduled" && !m.tbd && m.utc) || live)) x.push('<span class="clk">' + D.clocks(m.utc) + "</span>");
    var ch = D.chan(m, ctx); if (ch) x.push(ch);
    var mid = String(m.id);
    return '<div class="mw' + (live ? " is-live" : "") + '" id="m' + esc(mid.replace(/\D/g, "")) + '" data-mid="' + esc(mid) + '"><a class="mr' + (live ? " is-live" : "") + '" href="' + D.href(m, lg, ctx) + '">' + side(m.home || [], "h", hw, aw) + '<span class="mr-m">' + D.mid(m, ctx) + "</span>" + side(m.away || [], "a", aw, hw) + "</a>" +
      (x.length ? '<p class="mx">' + x.join("") + "</p>" : "") + "</div>";
  };

  // ------------------------------------------------------------------ one competition
  // its channels in the four countries (and the visitor's), countries with the same channels together
  D.bcLine = function(lgId, ctx){ var bc = ctx.bc; if (!bc) return ""; var key = String(lgId), out = [], seen = {};
    var order = D.ZONES.map(function(z){ return z[0]; }); if (ctx.cc && order.indexOf(ctx.cc) < 0 && bc[ctx.cc]) order.unshift(ctx.cc); else if (ctx.cc && order.indexOf(ctx.cc) > 0){ order.splice(order.indexOf(ctx.cc), 1); order.unshift(ctx.cc); }
    order.forEach(function(iso){ var e = bc[iso] && bc[iso][key]; if (!e || !e.b || !e.b.length) return; var t = e.b.slice(0, 2).map(function(x){ return esc(x[0]) + (x[1] ? " (مجانية)" : ""); }).join("، ");
      var nm = (D.COUNTRIES.filter(function(c){ return c[0] === iso; })[0] || [iso, iso])[1]; if (seen[t]){ seen[t].n.push(nm); return; } seen[t] = { n:[nm], t:t }; out.push(seen[t]); });
    if (!out.length) return "";
    return '<p class="gf bcx">وين تنقل: ' + out.map(function(x){ return x.n.join(" و") + " " + x.t; }).join(" · ") + "</p>"; };
  D.lgHref = function(lg, ctx){ var id = String(lg.id);
    if (id.indexOf("365:") === 0){ var s = id.slice(4); return ctx.l365 && ctx.l365.indexOf(+s) >= 0 ? "/db/league/" + s + "/" : "/db/league/?id=" + s; }
    return lg.ours && ctx.keys && ctx.keys[id] ? "/c/" + ctx.keys[id] + "/" : ""; };
  // Arabic counting: 1 مباراة, 2 مباراتين, 3-10 مباريات, 11+ مباراة (plain text with html=false)
  D.nMatches = function(n, plain){ return n === 1 ? "مباراة وحدة" : n === 2 ? "مباراتين" : (plain ? n : '<span class="num">' + n + "</span>") + " " + (n >= 3 && n <= 10 ? "مباريات" : "مباراة"); };
  D.full = function(lg){ return !!(lg.ours || D.isArab(lg) || lg.cc === "INT"); };
  D.league = function(lg, ctx){
    var ms = (lg.matches || []).slice(), name = lg.name_ar || lg.name || "", href = D.lgHref(lg, ctx), live = 0, rows = "", cur = null, full = D.full(lg);
    if (ms.some(function(m){ return m.g; })) ms.sort(function(a, b){ return String(a.g || "~").localeCompare(String(b.g || "~"), "en", { numeric:true }) || String(a.utc || "").localeCompare(String(b.utc || "")); });
    ms.forEach(function(m){ if (LIVE[m.status]) live++; var g = m.g ? D.group(m.g) : ""; if (g !== cur){ cur = g; if (g) rows += '<p class="gsub">' + esc(g) + "</p>"; } rows += D.row(m, lg, ctx, !full); });
    var head = "<h2>" + (href ? '<a href="' + href + '">' + esc(name) + "</a>" : esc(name)) + (lg.country_ar && lg.country_ar !== name ? " <small>" + esc(lg.country_ar) + "</small>" : "") + "</h2>" +
      (live ? '<span class="lvn"><i class="dot"></i><span class="num">' + live + "</span> مباشر</span>" : '<span class="nn">' + D.nMatches(ms.length) + "</span>");
    var attrs = ' data-lg="' + esc(String(lg.id)) + '"' + (lg.ours ? ' data-ours="1"' : "") + (D.isArab(lg) ? ' data-arab="1"' : "");
    // the long tail is folded (still in the HTML); a live match or the visitor's own opening unfolds it
    if (!full) return '<details class="grp dl dz' + (live ? " has-live" : "") + '"' + attrs + ((live || (ctx.open && ctx.open[String(lg.id)])) ? " open" : "") + '><summary class="gh">' + head + '</summary><div class="card">' + rows + "</div>" + D.bcLine(lg.id, ctx) + "</details>";
    return '<section class="grp dl' + (live ? " has-live" : "") + '"' + attrs + '><div class="gh">' + head + '</div><div class="card">' + rows + "</div>" + D.bcLine(lg.id, ctx) + "</section>";
  };
  D.counts = function(doc){ var n = 0, live = 0, lgs = 0; ((doc && doc.leagues) || []).forEach(function(lg){ if (!(lg.matches || []).length) return; lgs++; lg.matches.forEach(function(m){ n++; if (LIVE[m.status]) live++; }); }); return { n:n, live:live, leagues:lgs }; };
  // the whole list: the first `open` competitions in full, the rest folded by kind (still in the HTML for search engines)
  D.body = function(doc, ctx){
    var lgs = ((doc && doc.leagues) || []).filter(function(lg){ return (lg.matches || []).length; });
    if (!lgs.length) return '<div class="card"><p class="empty">ما في مباريات منشورة لهاليوم.</p></div>';
    return lgs.map(function(lg){ return D.league(lg, ctx); }).join("");
  };
  // a match in the site's own shape (fixtures, team files: home/away objects, score object) as an all-day row
  D.fromMatch = function(m){ var sc = m.score && (m.status === "finished" || LIVE[m.status]); return { id:m.id, utc:m.kickoff_utc, status:m.status, minute:m.minute, ours:true, tbd:!!m.time_tbd,
    home:[m.home.id, m.home.name_ar || m.home.name].concat(sc ? [m.score.home] : []), away:[m.away.id, m.away.name_ar || m.away.name].concat(sc ? [m.score.away] : []),
    pen:m.penalties ? [m.penalties.home, m.penalties.away] : undefined, sd:m.status_detail || undefined }; };
  // live rows (v1/all/live.json) onto the day document
  D.merge = function(doc, live){ if (!doc || !live || !live.matches) return doc; var by = {}; live.matches.forEach(function(m){ by[String(m.id)] = m; });
    (doc.leagues || []).forEach(function(lg){ (lg.matches || []).forEach(function(m, i){ var l = by[String(m.id)]; if (!l) return; var o = {}; for (var k in m) o[k] = m[k];
      ["status", "minute", "home", "away", "pen", "sd"].forEach(function(k){ if (k in l) o[k] = l[k]; else if (k === "minute" || k === "pen" || k === "sd") delete o[k]; }); lg.matches[i] = o; }); });
    return doc; };

  if (typeof module !== "undefined" && module.exports){ module.exports = D; return; }
  root.TD = D;

  // ================================================================== the browser
  var box = document.getElementById("days"); if (!box || !window.fetch) return;
  var $ = function(s, r){ return (r || document).querySelector(s); };
  var list = $("#dlist"), kind = box.dataset.kind, ctx = {}, doc = null, liveDoc = null, timers = {}, OFF = { today:0, tomorrow:1, yesterday:-1 };
  try { ctx = JSON.parse(($("#dctx") || {}).textContent || "{}"); } catch (e){ ctx = {}; }
  ctx.ymd = box.dataset.ymd;
  function country(){ try { var c = localStorage.getItem("tifo.country"); if (c) return c; } catch (e){} var tz = ""; try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e){}
    var hit = D.COUNTRIES.filter(function(c){ return c[2] === tz; })[0]; return hit ? hit[0] : "xx"; }
  function zone(cc){ var row = D.COUNTRIES.filter(function(c){ return c[0] === cc; })[0]; if (row) return row[2]; try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Dubai"; } catch (e){ return "Asia/Dubai"; } }
  function setCountry(){ ctx.cc = country(); ctx.tz = zone(ctx.cc); }
  setCountry();
  function get(u){ return fetch(u, { cache:"no-cache" }).then(function(r){ if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function later(k, fn, ms){ clearTimeout(timers[k]); timers[k] = setTimeout(function(){ if (document.hidden){ later(k, fn, 15e3); return; } fn(); }, ms); }
  // the visitor's clock on the prerendered rows straight away (the build printed the UAE's)
  function localize(root){ (root || document).querySelectorAll("#days time[data-u]").forEach(function(t){ if (t.dataset.f === "t") t.textContent = D.hm(t.dataset.u, ctx.tz); }); }
  localize();
  if (!list) return;   // «مباراة <فريق> اليوم»: the visitor's clock only
  // the list is redrawn only once the day file and the channel table are both in (or failed): no flash of rows without channels
  var bcDone = !document.body.dataset.bc;
  function draw(){
    if (!doc || !bcDone) return;
    var d = D.merge(JSON.parse(JSON.stringify(doc)), liveDoc), html = D.body(d, ctx);
    if (list._h !== html){ list._h = html; list.innerHTML = html; }
    var c = D.counts(d), lb = $("#dflive"); if (lb){ lb.querySelector(".num").textContent = c.live || ""; lb.hidden = !c.live && list.dataset.f !== "live"; }
  }
  function today(){ return D.uaeYmd(0); }
  function isToday(){ return ctx.ymd === today(); }
  function loadDoc(){ var y = ctx.ymd;
    return get("/v1/all/" + y + ".json").then(function(j){ if (y !== ctx.ymd) return; doc = j; draw(); }).catch(function(){}).then(function(){ if (isToday()) later("doc", loadDoc, 120e3); else if (ctx.ymd > today()) later("doc", loadDoc, 600e3); }); }
  function soon(){ var t = Date.now(), hit = false; ((doc && doc.leagues) || []).forEach(function(lg){ (lg.matches || []).forEach(function(m){ var k = Date.parse(m.utc); if (m.status === "scheduled" && k - t < 15 * 60e3 && k - t > -30 * 60e3) hit = true; }); }); return hit; }
  function loadLive(){ if (!isToday()){ liveDoc = null; return; }
    get("/v1/all/live.json").then(function(j){ liveDoc = j; draw(); }).catch(function(){}).then(function(){ var c = doc ? D.counts(D.merge(JSON.parse(JSON.stringify(doc)), liveDoc)) : { live:0 }; later("live", loadLive, c.live || soon() ? 30e3 : 120e3); }); }
  // the commentators land ~01:00 UAE and are edited during the day: every 2 min until 03:00, then every 10
  function loadTv(){ var y = ctx.ymd; if (y < "20260930") return;
    get("/v1/tv/" + y + ".json").then(function(j){ if (y !== ctx.ymd) return; ctx.tv = (j && j.matches) || {}; draw(); }).catch(function(){})
      .then(function(){ if (ctx.ymd >= today()){ var h = new Date(Date.now() + 4 * 3600e3).getUTCHours(); later("tv", loadTv, h < 3 ? 120e3 : 600e3); } }); }
  function loadBc(){ var v = document.body.dataset.bc; if (!v) return; get("/assets/bc." + v + ".json").then(function(j){ ctx.bc = j; }).catch(function(){}).then(function(){ bcDone = true; draw(); }); }
  // a new UAE day (midnight, or a page built before it): /today/, /tomorrow/ and /yesterday/ follow the calendar
  function rollover(){ if (!(kind in OFF)) return false; var want = D.uaeYmd(OFF[kind]); if (want === ctx.ymd) return false; ctx.ymd = want; box.dataset.ymd = want; doc = null; liveDoc = null; ctx.tv = {};
    var h1 = document.getElementById("dh1"), sub = document.getElementById("dsub"), w = { today:"مباريات اليوم", tomorrow:"مباريات بكرة", yesterday:"نتائج مباريات أمس" }[kind];
    if (h1) h1.textContent = w + " " + D.fullDate(want); if (sub) sub.textContent = "المواعيد بتوقيت بلدك"; document.title = w + " " + D.fullDate(want) + " | تيفو";
    loadDoc(); loadTv(); loadLive(); return true; }
  later("roll", function tick(){ rollover(); later("roll", tick, 60e3); }, 60e3);
  // «الكل · مباشر الحين · العرب»
  var seg = $("#dfil"); if (seg) seg.addEventListener("click", function(e){ var b = e.target.closest("button[data-f]"); if (!b) return; seg.querySelectorAll("button").forEach(function(x){ x.setAttribute("aria-pressed", x === b ? "true" : "false"); }); list.dataset.f = b.dataset.f; draw(); });
  // a folded competition the visitor opened stays open across redraws
  ctx.open = {}; list.addEventListener("toggle", function(e){ var d = e.target; if (d && d.matches && d.matches("details.dl")){ if (d.open) ctx.open[d.dataset.lg] = 1; else delete ctx.open[d.dataset.lg]; list._h = ""; } }, true);
  document.addEventListener("tifo:country", function(){ setCountry(); localize(); list._h = ""; draw(); });
  document.addEventListener("visibilitychange", function(){ if (!document.hidden && isToday()) loadLive(); });
  loadBc(); if (!rollover()){ loadDoc(); loadLive(); if (ctx.ymd >= today()) later("tv", loadTv, 120e3); }   // the build embedded this day's commentators (ctx.tv)
})(this);
