/* تيفو v5 page assemblers: data -> {title, nav, body, tab, sheets}. build.cjs wraps them in the document; app.js uses the
   same functions for pages it renders in the browser. Every page follows one skeleton (DESIGN.md §2):
   nav bar -> large title or entity header -> one segmented control -> grouped lists -> tab bar; secondary actions in sheets. */
(function (root) {
  "use strict";
  var U = root.U5 || (typeof require !== "undefined" ? require("./ui.js") : null), P = {}, esc = U.esc, cfg = U.cfg, I = U.icon, L = U.link, CHEV = U.chev;
  var prod = function (p) { return p; };   // links to pages that keep the current design until the rollout

  // ------------------------------------------------------------------ home (اليوم)
  P.featured = function (ms, o) {
    o = o || {}; var best = null, bv = -1e9, now = cfg.now || Date.now();
    ms.forEach(function (m) { var v = 0, t = Date.parse(m.kickoff_utc || 0);
      if (o.mine && (o.mine[m.home.id] || o.mine[m.away.id])) v += 1000;
      if (m.home.id === 5789 || m.away.id === 5789) v += 300;
      if ([538, 11027, 9943, 11026].indexOf(m.comp) >= 0) v += 120;
      if ([329, 10242, 290, 525, 42].indexOf(m.comp) >= 0) v += 80;
      if (o.arab && (o.arab[m.home.id] || o.arab[m.away.id])) v += 40;
      if (U.isLive(m)) v += 200; else if (m.status === "scheduled") v += 60 - Math.min(59, Math.abs(t - now) / 36e5 * 4); else if (m.status === "finished") v += 20 - Math.min(19, (now - t) / 36e5);
      if (v > bv) { bv = v; best = m; } });
    return best;
  };
  P.days = function (ymd) {   // seven days around the selected one
    var p = ymd.split("-").map(Number), out = [];
    for (var i = -3; i <= 3; i++) { var d = new Date(Date.UTC(p[0], p[1] - 1, p[2] + i)), k = d.toISOString().slice(0, 10), rel = i === 0 ? "اليوم" : i === 1 ? "بكرة" : i === -1 ? "أمس" : U.DAY[d.getUTCDay()].replace("ال", "");
      out.push('<button type="button" class="day' + (k === cfg.today ? " today" : "") + '" role="tab" data-d="' + k.replace(/-/g, "") + '" aria-selected="' + (i === 0) + '" aria-label="' + esc(U.DAY[d.getUTCDay()] + " " + d.getUTCDate() + " " + U.MON[d.getUTCMonth()]) + '"><span>' + rel + '</span><b>' + d.getUTCDate() + "</b></button>"); }
    return '<div class="days" role="tablist" aria-label="الأيام" id="days">' + out.join("") + "</div>";
  };
  P.homeList = function (ms, o) {   // the body under the segmented control; re-rendered in the browser
    o = o || {};
    var f = o.filter || "all", list = ms;
    var isArab = function (m) { return (o.arab && (o.arab[m.home.id] || o.arab[m.away.id])) || (o.arabComp && o.arabComp[m.comp]); };
    if (f === "live") list = ms.filter(U.isLive);
    else if (f === "arab") list = ms.filter(isArab);
    var top = f === "all" && !o.noFeature ? (o.featId && ms.filter(function (m) { return String(m.id) === String(o.featId); })[0]) || P.featured(ms, o) : null, mineM = top && o.mine && (o.mine[top.home.id] || o.mine[top.away.id]);
    var head = top ? '<section class="grp" id="feat"><div class="gh"><h2>' + (mineM ? "فريقك" : U.isLive(top) ? "مباشر الحين" : top.status === "finished" ? "أبرز نتيجة" : "أبرز مباراة") + "</h2></div>" + U.fcard(top) + '<div id="natcd"></div></section>' : "";
    var empty = f === "live" ? "ما في مباريات مباشرة الحين." : f === "arab" ? "ما في مباريات عربية في هاليوم." : "ما في مباريات في هاليوم.";
    return head + '<section class="grp" id="daylist"><div class="gh"><h2>' + (f === "live" ? "مباشر" : f === "arab" ? "مباريات العرب" : "مبارياتنا") + '</h2><span class="num">' + (list.length ? list.length + " مباراة" : "") + "</span></div>" + '<div class="stack">' + U.dayList(list, { mine: o.mine, spoil: o.spoil, empty: o.world && f !== "all" && !list.length ? empty.replace("هاليوم", "بطولاتنا") : empty }) + "</div></section>";
  };
  // every match of the day beyond ours (v1/all/<ymd>.json: FotMob's whole list + 365Scores' Arab leagues), one folded card per league
  var ARAB3 = "UAE KSA QAT KUW BHR OMA IRQ JOR SYR LBN LIB PLE YEM EGY SUD LBY TUN ALG MAR MTN SOM DJI COM".split(" ");
  P.worldArab = function (lg) { return ARAB3.indexOf(lg.cc) >= 0 || lg.src === "365"; };
  P.worldMatch = function (m, lg, ymd) {   // a v1/all row as a match object the v5 renderers draw
    var has = m.home.length > 2 && m.away.length > 2 && m.home[2] != null && m.away[2] != null, s365 = String(m.id).indexOf("365:") === 0;
    var side = function (t) { var id = String(t[0] || ""), x = id.indexOf("365:") === 0; return { id: x ? id : +id || null, name: t[1] || "", name_ar: /[؀-ۿ]/.test(t[1] || "") ? t[1] : "", nocrest: !x && !(lg.ours || m.ours), logo: x ? "https://imagecache.365scores.com/image/upload/f_png,w_48,h_48,c_limit,q_auto:eco,dpr_2,d_Competitors:default1.png/v1/Competitors/" + id.slice(4) : null }; };
    return { id: m.id, comp: lg.id, status: m.status, minute: m.minute, score: has ? { home: m.home[2], away: m.away[2] } : null, penalties: m.pen ? { home: m.pen[0], away: m.pen[1] } : null, status_detail: m.sd, kickoff_utc: m.utc, time_tbd: !!m.tbd, home: side(m.home), away: side(m.away),
      href: s365 ? "/db/game/?id=" + String(m.id).slice(4) : (lg.ours || m.ours) ? "/m/" + m.id + "/" : "/live/?id=" + m.id + "&d=" + ymd };
  };
  P.worldList = function (doc, o) {   // {filter, open: {leagueId: 1}, ymd, lv: live rows by id, skip: {matchId: 1} (ours, already listed)}
    o = o || {}; var f = o.filter || "all", n = 0, out = [];
    (doc.leagues || []).forEach(function (lg) {
      if (lg.ours) return;
      var ms = lg.matches.filter(function (m) { return !(o.skip && o.skip[m.id]); }).map(function (m) { var l = o.lv && o.lv[m.id]; if (l) { m = Object.assign({}, m); ["status", "minute", "home", "away", "pen", "sd"].forEach(function (k) { if (k in l) m[k] = l[k]; }); } return P.worldMatch(m, lg, o.ymd); });
      if (f === "live") ms = ms.filter(U.isLive); else if (f === "arab" && !P.worldArab(lg)) ms = [];
      if (!ms.length) return; n += ms.length;
      var lv = ms.filter(U.isLive).length, open = f !== "all" || lv || (o.open && o.open[lg.id]) || (o.openAll && P.worldArab(lg));
      out.push('<details class="card dz wl" data-lg="' + esc(lg.id) + '"' + (open ? " open" : "") + '><summary class="hd-row"><span class="rt"><span>' + esc(lg.name_ar || lg.name) + "</span>" + (lg.country_ar ? "<small>" + esc(lg.country_ar) + "</small>" : "") + "</span>" + (lv ? '<span class="chip lvc"><i class="dot"></i><span class="num">' + lv + "</span></span>" : '<span class="rv num">' + ms.length + "</span>") + CHEV + "</summary>" +
        ms.sort(U.byKick).map(function (m) { return U.mrow(m, { spoil: o.spoil }); }).join("") + "</details>");
    });
    return { n: n, html: out.length ? '<div class="gh"><h2>كل مباريات العالم</h2><span class="num">' + n + " مباراة</span></div>" + '<div class="stack">' + out.join("") + '</div><p class="gf">القائمة من FotMob، والدوريات العربية اللي ما يغطيها من 365Scores.</p>' : "" };
  };
  if (typeof __TIFO_BROWSER__ === "undefined") {   // build-time assemblers: the browser bundle drops them (build.cjs: esbuild define)
  P.home = function (d) {   // {matches, ymd, arab, arabComp, h1, world: open the world list (the /all/ page), fromTifo: html}
    var ms = d.matches || [], live = ms.filter(U.isLive).length;
    var body = '<div class="lt-row lt"><div><h1>' + esc(d.h1 || "اليوم") + (d.h1x ? '<span class="vh"> ' + esc(d.h1x) + "</span>" : "") + '</h1><p id="daysub">' + esc(U.dname(d.ymd + "T12:00:00+04:00")) + "</p></div></div>" + P.days(d.ymd) +
      '<div class="segbar" id="homeseg">' + U.seg("f", [["all", "الكل"], ["live", 'مباشر<span class="cnt num" id="livecnt"' + (live ? "" : " hidden") + ">" + live + "</span>", "مباشر"], ["arab", "العرب"]], "all") + "</div>" +
      '<section class="grp" id="minehome" hidden></section><div id="homelist">' + P.homeList(ms, { arab: d.arab, arabComp: d.arabComp }) + "</div>" + '<section class="grp" id="world"' + (d.world ? ' data-open="1"' : "") + ">" + (d.world ? '<div class="card">' + U.empty("نحمّل كل مباريات العالم…") + "</div>" : "") + "</section>" +
      (d.fromTifo != null ? d.fromTifo : P.fromTifo()) + U.foot();
    return { title: "تيفو: نتايج مباريات اليوم مباشر لكل العرب", navTitle: "اليوم", nav: { brand: 1, title: esc(d.h1 || "اليوم"), trail: U.navLink("search", "بحث", cfg.base + "/search/") + U.navBtn("filter", "فلتر", ' data-sheet="sh-filter"') }, body: body, tab: "today", sheets: P.filterSheet() };
  };
  // the home page's editorial blocks, one row each under the matches (they open their page; sheets at rollout)
  P.fromTifo = function () {
    return U.grp("من تيفو", U.rows([{ href: "/week/", icon: "star", c: "#FF9500", t: "مباراة الأسبوع", sub: "وأهم مباريات الأيام السبعة الياية" }, { href: "/thisday/", icon: "hist", c: "#5856D6", t: "هذا اليوم في كورة الإمارات" },
      { href: "/c/uae-pro-league/#pred", icon: "target", c: "#FF2D55", t: "أحلى مباريات الجولة الياية", sub: "دوري أدنوك للمحترفين" }, { href: "/streaks/", icon: "fire", c: "#FF3B30", t: "سلاسل شغالة", sub: "انتصارات وخسارات متتالية في الدوريات العربية" },
      { href: "/break/", icon: "flag", c: "#34C759", t: "فترة المنتخبات", sub: "وقت التوقف الدولي" }, { href: "/tv/", icon: "tv", c: "#1C7C54", t: "شاشة المجلس", sub: "كل مباريات اليوم على شاشة كبيرة" }]), { cls: "mt2" });
  };
  P.filterSheet = function () {
    var cc = [["AE", "الإمارات"], ["SA", "السعودية"], ["QA", "قطر"], ["KW", "الكويت"], ["BH", "البحرين"], ["OM", "عُمان"], ["EG", "مصر"], ["MA", "المغرب"], ["DZ", "الجزائر"], ["TN", "تونس"], ["IQ", "العراق"], ["JO", "الأردن"], ["LB", "لبنان"], ["SY", "سوريا"], ["PS", "فلسطين"], ["YE", "اليمن"], ["LY", "ليبيا"], ["SD", "السودان"], ["MR", "موريتانيا"], ["SO", "الصومال"], ["DJ", "جيبوتي"], ["KM", "جزر القمر"]];
    return U.sheet("sh-filter", "العرض", U.grp("", U.row({ btn: 1, icon: "eye", c: "#5856D6", t: "بدون حرق", sub: "النتايج مخفية لين تضغط عليها", sw: 1, attrs: ' role="switch" aria-checked="false" data-pref="nospoil"' })) +
      U.grp("بلدك", '<div class="sepd" id="ccl">' + cc.map(function (c) { return '<button type="button" class="row" data-cc="' + c[0] + '"><span class="rt">' + c[1] + '</span><span class="rv" data-ccv hidden>' + I("check", "", 2.4).replace('class=""', 'class="" style="width:20px;height:20px;color:var(--accent)"') + "</span></button>"; }).join("") + "</div>", { foot: "المواعيد والقنوات حسب بلدك." }));
  };
  }
  // ------------------------------------------------------------------ match
  if (typeof __TIFO_BROWSER__ === "undefined") {   // build-time assemblers: the browser bundle drops them (build.cjs: esbuild define)
  P.shareSheet = function (o) {   // {acts: [[icon, label, attrs, href, download]], rows: [U.row objects], html: rows as HTML, after: HTML under the list, top: HTML above}
    o = o || {}; var acts = [["share", "شارك", ' data-act="share"'], ["copy", "انسخ الرابط", ' data-act="copy"']].concat(o.acts || []);
    var list = (o.rows ? U.rows(o.rows) : "") + (o.html || "");
    return U.sheet("sh-share", "شارك", (o.top || "") + '<div class="acts">' + acts.map(function (a) { return a[3] ? '<a class="act" href="' + esc(a[3]) + '"' + (a[4] ? ' download="' + esc(a[4] === true ? "" : a[4]) + '"' : "") + (a[2] || "") + '><span class="ic">' + I(a[0]) + "</span>" + a[1] + "</a>" : '<button type="button" class="act"' + (a[2] || "") + '><span class="ic">' + I(a[0]) + "</span>" + a[1] + "</button>"; }).join("") + "</div>" + (list ? U.grp("", list, { cls: "mt2" }) : "") + (o.after || ""));
  };
  // «تيفو على شاشة جوالك»: Android gets the browser's own install prompt (#instgo), iPhone the two taps in Safari
  P.installSheet = function () {
    return U.sheet("sh-install", "تيفو على شاشة جوالك", '<div class="inst-hero"><span class="inst-ic" aria-hidden="true"><span class="mark"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span></span><p>يفتح مثل التطبيق، بدون متجر وبدون حساب، والصفحات اللي فتحتها تشتغل حتى لو النت ضعيف في الملعب.</p></div>' +
      U.grp("", U.row({ btn: 1, icon: "download", c: "#34C759", t: "ثبّت تيفو", attrs: ' id="instgo" hidden' }) + '<div class="row inst-ios" id="instios" hidden><span class="rt"><b>في آيفون (سفاري):</b> اضغط ' + '<span class="kbd">' + I("share", "", 2) + "شارك</span> تحت، وبعدها «أضف إلى الشاشة الرئيسية» " + '<span class="kbd">' + I("download", "", 2) + "</span></span></div>" + '<div class="row" id="instdone" hidden><span class="rt">تيفو مثبّت على جوالك.</span></div>', { cls: "mt" }) +
      '<p class="gf">تيفو بدون مراهنات، وبدون إعلانات تلاحقك.</p>');
  };
  // the first visit: pick your team(s) and your country in ten seconds; skippable, never shown again, editable in «فريقي»
  P.onbSheet = function () {
    return U.sheet("sh-onb", "خلّ تيفو لك", '<p class="note">اختار فريقك وبلدك، و«اليوم» يصير لك: مباريات فريقك أول شي، وقنوات بلدك، والمواعيد بتوقيتك.</p>' +
      '<div class="sf mt">' + I("search") + '<input type="search" id="onbq" placeholder="دوّر على فريقك" aria-label="دوّر على فريقك" autocomplete="off" enterkeyhint="search"></div><div id="onbr"></div>' +
      '<section class="grp" id="onbpop"><div class="gh"><h2>الأشهر</h2></div><div class="picks" id="onbpicks"></div></section>' +
      '<section class="grp"><div class="gh"><h2>بلدك</h2></div><div class="ccs" id="onbcc"></div></section>' +
      '<div class="onb-acts"><button type="button" class="pill pri" id="onbok">تم</button><button type="button" class="pill" id="onbskip">بعدين</button></div>');
  };
  function stakes(md, st) {   // «شو على المحك»: the table rows around both teams before kickoff
    if (!st || st.composite || !st.groups || !st.groups[0]) return "";
    var g = st.groups.filter(function (g) { return (g.rows || []).some(function (r) { return r.team.id === md.home.id; }) && g.rows.some(function (r) { return r.team.id === md.away.id; }); })[0]; if (!g || g.rows.length < 4) return "";
    var rk = function (id) { return g.rows.findIndex(function (r) { return r.team.id === id; }); }, a = rk(md.home.id), b = rk(md.away.id), lo = Math.max(0, Math.min(a, b) - 1), hi = Math.min(g.rows.length, Math.max(a, b) + 2), hl = {}; hl[md.home.id] = 1; hl[md.away.id] = 1;
    return U.grp("شو على المحك", U.table(g.rows.slice(lo, hi), { hl: hl }), { foot: "الترتيب قبل المباراة." });
  }
  function scoreGrid(md) {   // exact-score probabilities (6x6), the three likeliest outlined
    var S = md.probs && md.probs.scores; if (!S) return "";
    var flat = []; S.forEach(function (r, h) { r.forEach(function (v, a) { flat.push([v, h, a]); }); }); flat.sort(function (x, y) { return y[0] - x[0]; });
    var top = flat.slice(0, 3).map(function (x) { return x[1] + "-" + x[2]; }), mx = flat[0][0];
    var head = "<tr><th></th>" + [0, 1, 2, 3, 4, 5].map(function (a) { return '<th class="num">' + a + "</th>"; }).join("") + "</tr>";
    var body = S.map(function (r, h) { return '<tr><th class="num">' + h + "</th>" + r.map(function (v, a) { var on = top.indexOf(h + "-" + a) >= 0; return '<td class="num" style="background:color-mix(in srgb,var(--accent) ' + Math.round(v / mx * 55) + '%,transparent);' + (on ? "font-weight:800;box-shadow:inset 0 0 0 2px var(--accent);" : "") + '">' + Math.round(v * 100) + "</td>"; }).join("") + "</tr>"; }).join("");
    return '<div class="card"><div class="tblw"><table class="tbl" style="table-layout:fixed">' + head + body + '</table></div></div><p class="gf">الأرقام نسب مئوية. الصفوف أهداف ' + U.tname(md.home) + "، والأعمدة أهداف " + U.tname(md.away) + ". أرجح نتيجة: " + '<span dir="rtl" class="num">' + flat[0][1] + " - " + flat[0][2] + "</span>.</p>";
  }
  function firstsList(md) {
    var F = md.firsts || []; if (!F.length) return "";
    var K = { first_meeting: "أول مواجهة بين الفريقين من 2010", first_appearance_season: "أول مشاركة هالموسم", first_goal_season: "أول هدف هالموسم" };
    return U.rows(F.map(function (f) { return { t: f.player ? U.pname({ id: f.player, name: f.name }) : "المباراة", sub: (K[f.kind] || f.kind) + (f.minute ? " · الدقيقة " + f.minute : "") + (f.side ? " · " + U.tname(md[f.side]) : ""), href: f.player ? L("p", f.player) : null }; }));
  }
  // ctx: {st, ch, og, hl, x}. ctx.x (production): {top: catch-up / why / 60 seconds / highlights link at the head of المباراة, facts: the
  // three pre-match facts, stakes: «شو على المحك» with what each result does, ana: the old page's analysis blocks as rows that open
  // sheets, faq, p3d: the 3D pitch button, h2h: the pair's page, share: the share sheet, after: data scripts}
  P.match = function (md, ctx) {
    ctx = ctx || {}; var x = ctx.x || null, sched = md.status === "scheduled" || (!md.score && !U.isLive(md) && md.status !== "finished"), id = md.id;
    var c = U.pair(md.home.id, md.away.id);
    var kick = '<a class="hdr-kick" href="' + L("c", md.comp) + '">' + U.lg(md.comp) + "<span>" + esc(U.compName(md.comp, md)) + (U.roundLabel(md) ? " · " + esc(U.roundLabel(md)) : "") + "</span></a>";
    var meta = [md.date_tbd ? "" : U.tm(md.kickoff_uae || md.kickoff_utc, md.time_tbd ? "d" : "dt"), esc(U.venueAr(md.venue))].filter(Boolean).join(" · ");
    var head = '<header class="hdr" style="--h:' + c[0] + ";--a:" + c[1] + '"><div class="hdr-wash"></div><h1 class="vh">' + esc(U.tnameT(md.home) + " ضد " + U.tnameT(md.away)) + "</h1>" + kick + '<div id="mh">' + U.matchHead(md) + '</div><p class="mh-meta">' + meta + '</p><p class="prayl" id="prayl"></p><div class="mslot" data-media-slot></div></header>';
    var tabs = sched ? [["ov", "قبل المباراة"], ["lu", "التشكيلة"], ["h2h", "المواجهات"]] : [["ov", "المباراة"], ["lu", "التشكيلة"], ["st", "الأرقام"], ["h2h", "المواجهات"]];
    var wp = U.probs(md), wpc = U.wpChart(md), mom = U.momentum(md), grid = sched ? scoreGrid(md) : "", fl = firstsList(md);
    var probBlock = wp ? U.grp(sched ? "منو أقرب للفوز؟" : "فرص الفوز", wp + (wpc ? U.row({ btn: 1, t: "فرص الفوز دقيقة بدقيقة", attrs: ' data-sheet="sh-wp"' }) : "") + (grid ? U.row({ btn: 1, t: "أرجح النتايج بالضبط", attrs: ' data-sheet="sh-grid"' }) : "")) : "";
    var more = [mom && { btn: 1, icon: "chart", c: "#34C759", t: "الضغط دقيقة بدقيقة", attrs: ' data-sheet="sh-mom"' }, fl && { btn: 1, icon: "star", c: "#FF9500", t: "أوائل في هالمباراة", attrs: ' data-sheet="sh-firsts"' },
      !x && { href: prod("/m/" + id + "/#stats"), icon: "grid", c: "#8E8E93", t: sched ? "تقرير الفريقين وورقة الصحفي" : "التعليق وإعادة المباراة", sub: "بالتصميم الحالي للحين" }].filter(Boolean);
    var moreHtml = (more.length ? U.grp("بالتفصيل", U.rows(more)) : "") + (x && x.ana ? x.ana : "");
    var pick = sched && !md.time_tbd ? U.grp("منو بيفوز؟", '<div class="card" style="padding:12px"><div id="pick" data-mid="' + id + '" data-kick="' + esc(md.kickoff_utc || "") + '" data-h="' + md.home.id + '" data-a="' + md.away.id + '">' + U.seg("pick", [["h", U.tname(md.home)], ["d", "تعادل"], ["a", U.tname(md.away)]], "none") + "</div></div>", { foot: '<span id="pickm">توقعك يبقى في جوالك بس.</span>' }) : "";
    var chb = ctx.ch != null ? '<section class="grp" id="wwbox" data-comp="' + md.comp + '"><div class="gh"><h2>وين تنقل</h2><span id="chcc"></span></div><div class="card" id="chbox" data-comp="' + md.comp + '">' + (ctx.ch || '<div class="row"><span class="rt muted">ما عندنا القناة الناقلة لهالبطولة.</span></div>') + "</div></section>" : "";
    var info = U.grp("معلومات المباراة", U.info(md, { ch: !sched && U.isLive(md) && ctx.ch ? ctx.ch : "", hl: ctx.hl }));
    // «توقعك للنتيجة» (owner item 8, src/predict.js) replaces the local pick when the build passes it, and stays on live and recent pages
    var tp = x && x.predict != null ? x.predict : null;
    var ov = sched ? (x && x.top ? x.top : "") + chb + (tp != null ? tp : pick) + probBlock + (x && x.stakes != null ? x.stakes : stakes(md, ctx.st)) + (x && x.facts ? x.facts : "") + info + moreHtml
      : (x && x.top ? x.top : "") + '<section class="grp"><div class="gh"><h2>الأحداث</h2></div><div id="ev">' + U.events(md) + '</div></section><div id="ltable"></div>' + (U.isLive(md) ? chb : "") + (tp || "") + probBlock + info + moreHtml;
    var lu = (x && x.p3d ? x.p3d : "") + '<div id="lu">' + U.lineups(md) + "</div>";
    var h2h = U.h2h(md) + (x && x.h2h ? U.grp("", U.row({ href: x.h2h, icon: "swap", c: "#5856D6", t: "كل مواجهاتهم", sub: "كم فاز كل فريق، وكل النتايج" }), { cls: "mt2" }) : "");
    var body = head + U.segbar("m", tabs, "ov") + U.pane("m", "ov", ov, true) + U.pane("m", "lu", lu) + (sched ? "" : U.pane("m", "st", '<div id="stx">' + U.stats(md) + (mom ? U.grp("الضغط", '<div style="padding:12px 12px 4px">' + mom + "</div>") : "") + "</div>")) + U.pane("m", "h2h", h2h) + (x && x.faq ? x.faq : "") + (x && x.after ? x.after : "") + U.foot(x && x.foot ? x.foot : "");
    var og = ctx.og ? ctx.og : "";
    var sheets = (x && x.share != null ? x.share : P.shareSheet({ acts: [["image", "صورة للستوري", "", og ? "/og/m-" + id + "-story.png" : "/m/" + id + "/", !!og], ["tv", "شاشة المجلس", "", "/tv/?m=" + id], ["phone", "الشاشة الثانية", "", "/m/" + id + "/#second"], ["shirt", "عدّة صانع المحتوى", "", "/m/" + id + "/kit/"]] })) +
      (wpc ? U.sheet("sh-wp", "فرص الفوز دقيقة بدقيقة", '<div class="card" style="padding:14px 12px 4px">' + wpc + "</div>") : "") + (grid ? U.sheet("sh-grid", "أرجح النتايج بالضبط", grid) : "") + (mom ? U.sheet("sh-mom", "الضغط دقيقة بدقيقة", '<div class="card" style="padding:14px 12px 4px">' + mom + "</div>") : "") + (fl ? U.sheet("sh-firsts", "أوائل في هالمباراة", '<div class="card">' + fl + "</div>") : "");
    var t = U.matchTitle(md);
    return { title: t + " | تيفو", navTitle: esc(t), nav: { back: cfg.base + "/", backLabel: "اليوم", title: '<span dir="rtl">' + esc(U.tnameT(md.home)) + " " + (md.score && !sched ? md.score.home + " - " + md.score.away : "ضد") + " " + esc(U.tnameT(md.away)) + "</span>", trail: U.navBtn("share", "شارك", ' data-sheet="sh-share"') }, body: body, tab: "today", sheets: sheets };
  };

  }
  // ------------------------------------------------------------------ competition
  P.compTable = function (st, single, sel) {   // one league table in three views (مختصر · كامل · الفورمة); group tables compact
    sel = sel || "s";
    return single ? '<div class="mt">' + U.seg("tv", [["s", "مختصر"], ["f", "كامل"], ["fo", "الفورمة"]], sel, { sm: 1 }) + "</div>" + U.pane("tv", "s", U.standings(st), sel === "s") + U.pane("tv", "f", U.standings(st, { full: 1 }), sel === "f") + U.pane("tv", "fo", U.standings(st, { form: 1 }), sel === "fo") : U.standings(st);
  };
  // d: {st, fx, stats, champs: {rows, name, link, l365, src}, sim, x}. d.x (production) brings each segment's extra blocks, already
  // as rows that open sheets: {table, fx, leadSegs: [[key, label, html]], num, predLead, pred, hist, note, after, share}
  if (typeof __TIFO_BROWSER__ === "undefined") {   // build-time assemblers: the browser bundle drops them (build.cjs: esbuild define)
  P.comp = function (c, d) {
    d = d || {}; var x = d.x || null, st = d.st, fx = d.fx || { matches: [] }, has = { table: !!(st && st.groups && st.groups.length), stats: !!(d.stats && d.stats.lists && (d.stats.lists.goals || []).length) };
    var single = has.table && !st.composite && st.groups.length === 1, lead = single ? st.groups[0].rows[0] : null;
    var R = U.rounds(fx), fin = (fx.matches || []).filter(function (m) { return m.status === "finished"; }).length, tot = (fx.matches || []).length;
    var chips = [lead ? '<a class="chip" href="' + L("t", lead.team.id) + '">' + U.crest(lead.team).replace('class="cr"', 'class="lg"') + "المتصدر " + U.tname(lead.team) + "</a>" : "", R.cur && R.by[R.cur] && R.by[R.cur].some(function (m) { return m.status !== "finished"; }) ? '<span class="chip">' + (/^\d+$/.test(R.cur) ? "الجولة الياية " + '<span class="num">' + esc(R.cur) + "</span>" : esc(U.stageAr(R.cur))) + "</span>" : "", tot ? '<span class="chip"><span class="num">' + fin + "</span>&nbsp;من&nbsp;<span class=\"num\">" + tot + "</span>&nbsp;مباراة</span>" : ""].filter(Boolean).join("");
    var head = '<header class="hdr th">' + (x && x.crumbs ? '<p class="hdr-k">' + x.crumbs + "</p>" : "") + U.lg(c.id, "cr xl") + "<h1>" + esc(c.name_ar) + '</h1><p class="sub">' + [c.country && c.country.name_ar ? esc(c.country.name_ar) : "", c.season ? "الموسم " + '<span class="num">' + esc(c.season) + "</span>" : ""].filter(Boolean).join(" · ") + (c.dormant ? " · متوقفة" : "") + "</p>" + (chips ? '<div class="chips">' + chips + "</div>" : "") +
      '<div class="th-acts"><button type="button" class="pill" data-fav="c:' + c.id + '" data-n="' + esc(c.name_ar) + '">' + I("star", "", 2) + "<span>تابع</span></button>" + '<button type="button" class="pill" data-sheet="sh-share">' + I("share", "", 2) + "<span>شارك</span></button></div></header>" + (x && x.note ? x.note : "");
    var predOn = !!(d.sim || (x && (x.predLead || x.pred))), histOn = !!(d.champs || (x && x.hist)), numOn = has.stats || !!(x && x.num);
    var tabs = [has.table && ["table", "الترتيب"], ["fx", "المباريات"], numOn && ["num", "الأرقام"], predOn && ["pred", "التوقعات"], histOn && ["hist", "التاريخ"]].filter(Boolean);
    var tablePane = has.table ? '<div id="ctab" data-single="' + (single ? 1 : 0) + '">' + P.compTable(st, single) + "</div>" +
      (x ? x.table || "" : single ? U.grp("بعد في الترتيب", U.rows([{ href: prod("/c/" + c.key + "/#table"), icon: "grid", c: "#0A84FF", t: "بملعبه · برا ملعبه · الشوط الأول · العادل", sub: "جداول ثانية، بالتصميم الحالي للحين" }, { href: prod("/c/" + c.key + "/#table"), icon: "chart", c: "#34C759", t: "رحلة الموسم", sub: "مركز كل فريق جولة بجولة" }]), { cls: "mt2" }) : "") : "";
    var rounds = R.order.length > 1 ? '<div class="rounds" role="tablist" id="rounds" data-comp="' + c.id + '" data-key="' + esc(c.key) + '">' + R.order.map(function (k) { return '<button type="button" role="tab" data-r="' + esc(k) + '" aria-selected="' + (k === R.cur) + '">' + U.roundChip(k) + "</button>"; }).join("") + "</div>" : "";
    var fxPane = (tot ? rounds + '<div id="roundlist">' + U.roundMatches(R.by[R.cur] || []) + "</div>" : '<div class="card">' + U.empty("ما في مباريات منشورة.") + "</div>") + (x && x.fx ? x.fx : "");
    var S = d.stats && d.stats.lists || {}, lsegs = [["g", "الهدافين", U.leaders(S.goals, 10)], ["a", "صناع الأهداف", U.leaders(S.assists, 10)]].concat((x && x.leadSegs) || []);
    var numPane = (has.stats ? U.seg("ld", lsegs.map(function (s) { return [s[0], s[1]]; }), "g", { sm: 1 }) + '<div class="mt">' + lsegs.map(function (s, i) { return U.pane("ld", s[0], '<div class="card">' + s[2] + "</div>", !i); }).join("") + "</div>" : "") +
      (x ? x.num || "" : U.grp("كل الأرقام", U.rows([{ href: prod("/c/" + c.key + "/scorers/"), icon: "ball", c: "#34C759", t: "كل الهدافين وصناع الأهداف" }, { href: prod("/c/" + c.key + "/#num"), icon: "chart", c: "#FF9500", t: "بطاقات تيفو ومنو الحاسم وساعة الأهداف", sub: "و25 رقم ثاني، بالتصميم الحالي للحين" }, { href: prod("/c/" + c.key + "/compare/"), icon: "compare", c: "#5856D6", t: "قارن بين لاعبين أو فريقين" }])));
    var predPane = (d.sim ? P.sim(d.sim, st) : "") + (x ? (x.predLead || "") + (x.pred || "") : d.sim ? U.grp("بعد في التوقعات", U.rows([{ href: prod("/c/" + c.key + "/#pred"), icon: "target", c: "#FF2D55", t: "كم يحتاج فريقك؟ وشو لو؟", sub: "بالتصميم الحالي للحين" }])) : "");
    var histPane = (d.champs ? U.grp("الأكثر تتويجاً", U.champs(d.champs.rows, d.champs.name, { link: d.champs.link, top: 10 }), { raw: 1, foot: d.champs.src || "" }) + U.grp("كل الأبطال", '<div class="sepd">' + d.champs.rows.slice(0, 8).map(function (r) { var h = d.champs.link && d.champs.link(r[1]); return (h && h !== "#" ? '<a class="row" href="' + esc(h) + '">' : '<div class="row">') + '<span class="rt">' + esc(d.champs.name(r[1])) + '</span><span class="rv num">' + esc(r[0]) + "</span>" + (h && h !== "#" ? CHEV + "</a>" : "</div>"); }).join("") + "</div>" + (d.champs.l365 ? U.row({ href: L("l", d.champs.l365), t: "كل الأبطال من أول موسم", cls: "link" }) : "")) : "") +
      (x ? x.hist || "" : d.champs ? U.grp("بعد في التاريخ", U.rows([{ href: prod("/c/" + c.key + "/#hist"), icon: "hist", c: "#5856D6", t: "الهدافين التاريخيين وكتاب الأرقام القياسية", sub: "والجدول التاريخي وطريق البطل، بالتصميم الحالي للحين" }])) : "");
    var body = head + U.segbar("c", tabs, tabs[0][0]) + (has.table ? U.pane("c", "table", tablePane, true) : "") + U.pane("c", "fx", fxPane, !has.table) + (numOn ? U.pane("c", "num", numPane) : "") + (predOn ? U.pane("c", "pred", predPane) : "") + (histOn ? U.pane("c", "hist", histPane) : "") + (x && x.after ? x.after : "") + U.foot();
    return { title: c.name_ar + ": الترتيب والمباريات والهدافين | تيفو", nav: { back: cfg.base + "/competitions/", backLabel: "البطولات", title: esc(c.name_ar), trail: U.navLink("search", "بحث", cfg.base + "/search/") + U.navBtn("share", "شارك", ' data-sheet="sh-share"') }, body: body, tab: "comps", sheets: x && x.share != null ? x.share : P.shareSheet({ acts: [["image", "صورة الترتيب", "", "/c/" + c.key + "/"], ["link", "ضمّنه في موقعك", "", "/c/" + c.key + "/#table"]] }) };
  };
  P.sim = function (sim, st) {
    var T = sim && sim.teams; if (!T) return "";
    var rows = Object.keys(T).map(function (id) { return [id, T[id]]; }).sort(function (a, b) { return (b[1].title || 0) - (a[1].title || 0); }).slice(0, 10), mx = rows.length ? rows[0][1].title || 1 : 1;
    var nm = function (id) { var r = st && st.groups && st.groups[0] && st.groups[0].rows.filter(function (r) { return String(r.team.id) === String(id); })[0]; return r ? r.team : { id: +id }; };
    return U.grp("من بيفوز بالدوري؟", '<ol class="card bars">' + rows.map(function (r) { var t = nm(r[0]), p = Math.round((r[1].title || 0) * 1000) / 10; return '<li><a class="bl" href="' + L("t", t.id) + '"><span class="bn">' + U.crest(t) + "<span>" + U.tname(t) + '</span></span><b class="num">' + p + '%</b><i style="--w:' + Math.round((r[1].title || 0) / mx * 100) + '%"></i></a></li>'; }).join("") + "</ol>", { raw: 1, foot: "لعبنا باقي الموسم " + U.nf(sim.sims || 10000) + " مرة بتصنيف تيفو." });
  };

  }
  // ------------------------------------------------------------------ team
  P.teamFx = function (t) {   // the featured card (live, else next, else last) and the fixtures pane; re-rendered in the browser
    var F = U.teamFixtures(t), nx = F.live[0] || F.next[0];
    var feat = nx ? U.grp(U.isLive(nx) ? "مباشر الحين" : "المباراة الياية", U.fcard(nx), { raw: 1 }) : F.past[0] ? U.grp("آخر نتيجة", U.fcard(F.past[0]), { raw: 1 }) : "";
    var fx = (F.live.length ? U.grp("مباشر", F.live.map(function (m) { return U.mrow(m, { date: 1 }); }).join("")) : "") + (F.next.length ? U.grp("الياية", F.next.slice(0, 6).map(function (m) { return U.mrow(m, { date: 1 }); }).join("")) : "") + (F.past.length ? U.grp("النتايج", F.past.slice(0, 10).map(function (m) { return U.mrow(m, { date: 1, team: t.id }); }).join("")) : "") || '<div class="card">' + U.empty("ما في مباريات منشورة.") + "</div>";
    return { feat: feat, fx: fx };
  };
  // d: {row: {c, r} league row, st, trophies:[[name, n, seasons, href]], trophiesSrc, card: rows, wiki, month, x}. d.x (production):
  // {months: [[ym, label]], squad: the squad pane's HTML, hist: HTML after the club card (mounts, numbers as rows), notify: rows,
  //  share: the share sheet, crumbs}
  if (typeof __TIFO_BROWSER__ === "undefined") {   // build-time assemblers: the browser bundle drops them (build.cjs: esbuild define)
  P.team = function (t, d) {
    d = d || {}; var x = d.x || null, F = U.teamFixtures(t), nat = !!t.national, id = t.id;
    var nx = F.live[0] || F.next[0], sub = [d.row ? '<a href="' + L("c", d.row.c.id) + '">' + esc(d.row.c.name_ar) + "</a> · المركز " + '<span class="num">' + d.row.r.rank + "</span>" : nat ? "منتخب" : "", t.coach && t.coach.name ? "المدرب " + (cfg.pn[t.coach.id] ? esc(cfg.pn[t.coach.id]) : '<span class="lat">' + esc(t.coach.name) + "</span>") : ""].filter(Boolean).join(" · ");
    var head = '<header class="hdr th" style="--h:' + U.col(id) + '"><div class="hdr-wash"></div>' + U.crest(t, "xl").replace("<img ", '<img style="view-transition-name:crest-' + esc(id) + '" ') + "<h1>" + U.tname(t) + '</h1><p class="sub">' + sub + "</p>" + (d.row && d.row.r.form ? '<div class="chips">' + U.formChips(d.row.r.form) + "</div>" : "") +
      '<div class="th-acts"><button type="button" class="pill pri" data-fav="t:' + id + '" data-n="' + esc(U.tnameT(t)) + '">' + I("star", "", 2) + "<span>تابع</span></button>" + '<button type="button" class="pill" data-sheet="sh-notify">' + I("bell", "", 2) + "<span>نبّهني</span></button>" + '<button type="button" class="pill" data-sheet="sh-share" aria-label="شارك">' + I("share", "", 2) + "</button></div></header>";
    var tf = P.teamFx(t), feat = tf.feat, fxPane = tf.fx;
    var hiOn = !!(d.trophies || d.card || d.wiki || (x && x.hist));
    var tabs = [["fx", "المباريات"], d.row && d.st && ["tb", "الترتيب"], ["sq", "اللاعبين"], ["nw", "الأخبار"], hiOn && ["hi", "التاريخ"]].filter(Boolean);
    var hl = {}; hl[id] = 1;
    var tbPane = d.row && d.st ? U.grp(esc(d.row.c.name_ar), U.table(d.st.groups[0].rows, { hl: hl }) + U.legend(d.st)) + U.grp("", U.row({ href: L("c", d.row.c.id), t: "صفحة الدوري", cls: "link" })) : "";
    var hiPane = (d.wiki ? U.grp("عن " + (nat ? "المنتخب" : "النادي"), '<p class="wiki">' + d.wiki + "</p>") : "") + (d.card ? U.grp("بطاقة " + (nat ? "المنتخب" : "النادي"), U.rows(d.card)) : "") +
      (d.trophies && d.trophies.length ? U.grp("ألقابه " + '<span class="num">' + d.trophies.reduce(function (a, x) { return a + x[1]; }, 0) + "</span>", d.trophies.map(function (x) { var tag = x[3] ? "a" : "div"; return "<" + tag + ' class="row"' + (x[3] ? ' href="' + esc(x[3]) + '"' : "") + '><span class="rt"><b>' + esc(x[0]) + "</b><small>" + esc((x[2] || []).slice(0, 12).join("، ")) + ((x[2] || []).length > 12 ? "…" : "") + '</small></span><span class="rv num" style="color:var(--label);font-weight:800">' + x[1] + "</span>" + (x[3] ? CHEV : "") + "</" + tag + ">"; }).join(""), { foot: d.trophiesSrc || "" }) : "") +
      (x ? x.hist || "" : U.grp("", U.rows([{ href: prod("/t/" + id + "/#chist"), icon: "hist", c: "#8E8E93", t: "كل نتايجه من أول مباراة، ومدربينه وانتقالاته", sub: "بالتصميم الحالي للحين" }])));
    var month = x ? (x.months && x.months.length ? U.grp("تقارير الشهر", U.rows(x.months.map(function (m) { return { href: cfg.base + "/t/" + id + "/month/" + m[0] + "/", icon: "calendar", c: "#FF3B30", t: "تقرير " + esc(m[1]), sub: "النتايج وأحسن اللاعبين والترتيب" }; })), { cls: "mt2" }) : "")
      : d.row && d.month ? U.grp("", U.rows([{ href: prod("/t/" + id + "/month/" + d.month + "/"), icon: "calendar", c: "#FF3B30", t: "تقرير الشهر", sub: "النتايج وأحسن اللاعبين والترتيب، بالتصميم الحالي للحين" }]), { cls: "mt2" }) : "";
    var body = head + '<div id="tfeat">' + feat + "</div>" + U.segbar("t", tabs, "fx") + U.pane("t", "fx", '<div id="tfx">' + fxPane + "</div>" + month + (x && x.fxExtra ? x.fxExtra : ""), true) + (tbPane ? U.pane("t", "tb", tbPane) : "") + U.pane("t", "sq", x && x.squad != null ? x.squad : U.squad(t)) + U.pane("t", "nw", '<div class="enews" data-e="team-' + id + '" data-social="team-' + id + '"><div class="card">' + U.empty("نحمّل الأخبار…") + "</div></div>") + (hiOn ? U.pane("t", "hi", hiPane) : "") + U.foot();
    var notify = x && x.notify ? x.notify : U.sheet("sh-notify", "نبّهني", '<p class="note">تنبيه على جوالك لمباريات ' + U.tname(t) + " بدون حساب. اختار متى:</p>" + U.grp("", U.rows([{ btn: 1, t: "بداية المباراة", sw: 1, attrs: ' role="switch" aria-checked="false" data-push="start"' }, { btn: 1, t: "كل هدف", sw: 1, attrs: ' role="switch" aria-checked="false" data-push="goal"' }, { btn: 1, t: "النتيجة النهائية", sw: 1, attrs: ' role="switch" aria-checked="false" data-push="end"' }]), { cls: "mt", foot: '<span id="pushm" role="status"></span>' }) +
      U.grp("", U.rows([{ href: "/v1/team/" + id + ".ics", icon: "calendar", c: "#FF3B30", t: "مبارياته في تقويم جوالك", sub: "يتحدّث بروحه", attrs: ' id="ics"' }]), { cls: "mt" }));
    return { title: U.tnameT(t) + ": المباريات والنتايج واللاعبين | تيفو", nav: { back: d.row ? L("c", d.row.c.id) : cfg.base + "/competitions/", backLabel: d.row ? d.row.c.name_ar : "البطولات", title: esc(U.tnameT(t)), trail: U.navLink("search", "بحث", cfg.base + "/search/") + U.navBtn("share", "شارك", ' data-sheet="sh-share"') }, body: body, tab: "comps", sheets: notify + (x && x.share != null ? x.share : P.shareSheet({ acts: [["image", "خلفية للجوال", "", "/t/" + id + "/"], ["calendar", "بوستر الموسم", "", "/t/" + id + "/poster/"]] })) };
  };

  }
  // ------------------------------------------------------------------ player
  // the career pane: FotMob seasons (clubs, national team), trophies, transfers, market value, injuries (Transfermarkt)
  P.playerCareer = function (d) {   // {prof, tm, transfers}
    var C = (d.prof && d.prof.career) || {}, T = d.tm || {};
    var seasons = function (k, title) { var c = C[k]; if (!c || !c.seasons || !c.seasons.length) return ""; var tot = c.seasons.reduce(function (a, x) { a[0] += +x[3] || 0; a[1] += +x[4] || 0; a[2] += +x[5] || 0; return a; }, [0, 0, 0]);
      return U.grp(title + ' <span class="num">' + tot[0] + " مباراة · " + tot[1] + " هدف</span>", '<div class="tblw"><table class="tbl"><thead><tr><th>الموسم</th><th class="tm">الفريق</th><th>مباريات</th><th>أهداف</th><th>صناعة</th></tr></thead><tbody>' + c.seasons.slice(0, 14).map(function (x) { return '<tr><td class="dim">' + esc(x[0] || "") + '</td><td class="tm"><a href="' + L("t", x[1]) + '">' + U.crest({ id: x[1] }) + '<span class="n">' + esc(cfg.tn[x[1]] || x[2] || "") + "</span></a></td><td>" + (x[3] || 0) + "</td><td>" + (x[4] || 0) + "</td><td>" + (x[5] || 0) + "</td></tr>"; }).join("") + "</tbody></table></div>"); };
    var tro = ((d.prof && d.prof.trophies) || []).filter(function (x) { return (x[4] || []).length; });
    var trophies = tro.length ? U.grp("ألقابه " + '<span class="num">' + tro.reduce(function (a, x) { return a + x[4].length; }, 0) + "</span>", tro.map(function (x) { return '<div class="row"><span class="rt"><b>' + esc(x[3] || "") + "</b><small>" + esc((cfg.tn[x[0]] || x[1] || "") + " · " + x[4].join("، ")) + '</small></span><span class="rv num" style="color:var(--label);font-weight:800">' + x[4].length + "</span></div>"; }).join("")) : "";
    var mv = d.prof && d.prof.mv && d.prof.mv.length > 2 ? (function () { var V = d.prof.mv, W = 600, H = 130, t0 = Date.parse(V[0][0]), t1 = Date.parse(V[V.length - 1][0]), mx = Math.max.apply(null, V.map(function (x) { return x[1] || 0; })) || 1;
      var X = function (dt) { return (W - 10 - (Date.parse(dt) - t0) / Math.max(1, t1 - t0) * (W - 20)).toFixed(1); }, Y = function (v) { return (H - 10 - v / mx * (H - 24)).toFixed(1); }, top = V.reduce(function (a, x) { return x[1] > a[1] ? x : a; }, V[0]);
      return U.grp("قيمته السوقية", '<div style="padding:14px 12px 4px"><svg class="chart" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="قيمته السوقية عبر السنين"><path d="' + V.map(function (x, i) { return (i ? "L" : "M") + X(x[0]) + " " + Y(x[1] || 0); }).join("") + '" fill="none" stroke="var(--accent)" stroke-width="2.5"/></svg></div>', { foot: "أعلى قيمة " + U.eur(top[1]) + " في " + '<span class="num">' + esc(top[0].slice(0, 7)) + "</span>، والحين " + U.eur(V[V.length - 1][1]) + "." }); })() : "";
    var INJ = T.injuries || [];
    var injuries = INJ.length ? U.grp("سجل الإصابات " + '<span class="num">' + INJ.length + "</span>", '<div class="tblw"><table class="tbl"><thead><tr><th>الموسم</th><th class="tm">الإصابة</th><th>أيام</th><th>غاب</th></tr></thead><tbody>' + INJ.slice(0, 15).map(function (x) { return '<tr><td class="dim">' + esc(x[0] || "") + '</td><td class="tm"><span><span class="n">' + esc(U.injAr ? U.injAr(x[1]) : x[1] || "") + "</span></span></td><td>" + (x[4] == null ? "" : x[4]) + "</td><td>" + (x[5] == null ? "" : x[5]) + "</td></tr>"; }).join("") + "</tbody></table></div>", { foot: "غاب " + '<span class="num">' + U.nf(INJ.reduce(function (a, x) { return a + (x[4] || 0); }, 0)) + "</span> يوم بسبب الإصابات. من Transfermarkt." }) : "";
    var club = function (nm, id) { var a = id != null && (cfg.tn[id] || ""); return a ? esc(a) : '<span class="lat">' + esc(nm || "") + "</span>"; };
    var trs = d.transfers && d.transfers.length ? U.grp("انتقالاته", d.transfers.slice().reverse().filter(function (m) { return !/without club|retired/i.test(m[4] || ""); }).slice(0, 10).map(function (m) { return '<div class="row"><span class="rt">' + club(m[4], m[5]) + "<small>من " + club(m[2], m[3]) + " · " + U.dateAr(m[0]) + '</small></span><span class="rv">' + (m[6] == null ? "—" : U.eur(m[6])) + "</span></div>"; }).join(""), { foot: "المبالغ من Transfermarkt." }) : "";
    return seasons("senior", "مع الأندية") + seasons("national team", "مع المنتخب") + trophies + trs + mv + injuries;
  };
  // the matches pane: season totals and the latest games (v1/player/<id>/log.json)
  P.playerGames = function (LG) {
    if (!LG || !LG.matches || !LG.matches.length) return ""; var CN = LG.comps || {}, TN = LG.teams || {};
    return (LG.seasons && LG.seasons.length ? U.grp("موسم بموسم", '<div class="tblw"><table class="tbl"><thead><tr><th>الموسم</th><th class="tm">البطولة</th><th>مباريات</th><th>أهداف</th><th>صناعة</th><th>التقييم</th></tr></thead><tbody>' + LG.seasons.slice(0, 10).map(function (x) { return '<tr><td class="dim">' + esc(x.season) + '</td><td class="tm"><span><span class="n">' + esc(CN[x.comp] || x.comp) + "</span></span></td><td>" + x.apps + "</td><td>" + x.g + "</td><td>" + x.a + "</td><td>" + (x.rn ? (x.rs / x.rn).toFixed(1) : "—") + "</td></tr>"; }).join("") + "</tbody></table></div>") : "") +
      U.grp("آخر مبارياته", '<div id="plm">' + LG.matches.slice(0, 15).map(function (r) { var res = r[5] > r[6] ? "W" : r[5] < r[6] ? "L" : "D"; return '<a class="row" href="' + (cfg.pre ? L("m", r[0]) : cfg.base + "/db/match/?id=" + r[0]) + '"><span class="rt">ضد ' + esc(TN[r[4]] || cfg.tn[r[4]] || "") + " <small>" + esc(r[1] || "") + " · " + esc(CN[r[2]] || "") + (r[9] ? " · " + r[9] + " هدف" : "") + (r[10] ? " · " + r[10] + " صناعة" : "") + '</small></span><span class="rv"><span dir="rtl" class="num">' + r[5] + " - " + r[6] + '</span> <i class="rsl ' + res + '">' + { W: "ف", D: "ت", L: "خ" }[res] + "</i></span>" + CHEV + "</a>"; }).join("") + "</div>");
  };
  // d: {name, latin, team, pos, num, cc, card(season), prof, tm, log, ea, photo, credit, wiki, transfers, x}. d.x (production):
  // {mount: career and matches load in the browser (#pcar, #plg), profile: HTML after the card (the old page's blocks as rows),
  //  crumbs, share}
  if (typeof __TIFO_BROWSER__ === "undefined") {   // build-time assemblers: the browser bundle drops them (build.cjs: esbuild define)
  P.player = function (id, d) {
    var x = d.x || null, b = (d.prof && d.prof.bio) || {}, team = d.team, tcol = team ? U.col(team.id) : "#636366";
    var age = b.born && b.born >= "1900" ? Math.floor(((cfg.now || Date.now()) - Date.parse(b.born)) / 31557600000) : null;
    var ava = '<div class="avatar" style="--c:' + tcol + ";--ci:" + U.ink(tcol) + '">' + (d.photo ? '<img src="' + d.photo + '" alt="" width="104" height="104" fetchpriority="high">' : "<b>" + esc(b.shirt || d.num || "") + "</b>") + "</div>";
    var chips = [team ? '<a class="chip" href="' + L("t", team.id) + '">' + U.crest(team).replace('class="cr"', 'class="lg"') + U.tname(team) + "</a>" : "", (d.pos || b.pos) ? '<span class="chip">' + esc(U.posAr(d.pos || b.pos)) + "</span>" : "", (b.cc || d.cc) ? '<span class="chip">' + esc(U.country(b.cc || d.cc)) + "</span>" : ""].filter(Boolean).join("");
    // «تابع فريقه» (owner item 11): the team into «فريقي» right here, and «نبّهني» one tap away on the team page (#notify opens it)
    var follow = team ? '<div class="th-acts"><button type="button" class="pill pri" data-fav="t:' + esc(team.id) + '" data-n="' + esc(U.tnameT(team)) + '">' + I("star", "", 2) + "<span>تابع</span> <bdi>" + esc(U.tnameT(team)) + "</bdi></button>" +
      '<a class="pill" href="' + L("t", team.id) + '#notify">' + I("bell", "", 2) + "<span>نبّهني لمبارياته</span></a></div>" : "";
    var head = '<header class="hdr th" style="--h:' + tcol + '"><div class="hdr-wash"></div>' + (x && x.crumbs ? '<p class="hdr-k">' + x.crumbs + "</p>" : "") + ava + "<h1>" + (d.name ? esc(d.name) : '<span class="lat">' + esc(d.latin || b.name || "") + "</span>") + "</h1>" + (d.name && d.latin && /[A-Za-z]/.test(d.latin) && d.latin !== d.name ? '<p class="sub lat">' + esc(d.latin) + "</p>" : "") + '<div class="chips">' + chips + "</div>" + (d.credit ? '<p class="gf" style="padding:6px 0 0">' + d.credit + "</p>" : "") + (x && x.follow ? follow : "") + "</header>";
    var s = d.card || {}, sv = function (v, dg) { return v == null ? "—" : dg ? Number(v).toFixed(1) : v; };
    // this season's tiles: the league file's card, else the match log, else this season's row of his FotMob career (d.seasonRow)
    var lastS = d.log && d.log.seasons && d.log.seasons[0], sr = d.seasonRow, tiles = d.card ? [[sv(s.goals), "أهداف"], [sv(s.assists), "صناعة"], [s.minutes != null ? s.minutes : "—", "دقيقة"], [sv(s.rating, 1), "التقييم"]]
      : lastS ? [[lastS.g, "أهداف"], [lastS.a, "صناعة"], [lastS.apps, "مباراة"], [lastS.rn ? (lastS.rs / lastS.rn).toFixed(1) : "—", "التقييم"]]
      : sr && sr.apps ? [[sr.g, "أهداف"], [sr.a, "صناعة"], [sr.apps, "مباراة"]] : null;
    var tSeason = !d.card && lastS ? lastS.season : !d.card && !lastS && sr ? sr.season : d.season;
    var tilesHtml = tiles ? '<section class="grp"><div class="gh"><h2>هالموسم</h2>' + (tSeason ? '<span class="num">' + esc(tSeason) + "</span>" : "") + '</div><div class="tiles">' + tiles.map(function (x) { return '<div class="tile"><b>' + x[0] + "</b><span>" + x[1] + "</span></div>"; }).join("") + "</div></section>" : "";
    var introHtml = x && x.intro ? '<section class="grp"><p class="wiki">' + esc(x.intro) + "</p></section>" : "";
    var FOOT = { left: "اليسرى", right: "اليمنى", both: "الثنتين" }, T = d.tm || {};
    var bio = [age != null && { t: "العمر", v: '<span class="num">' + age + "</span> سنة" }, age != null && { t: "تاريخ الميلاد", v: U.dateAr(b.born) }, b.h && { t: "الطول", v: '<span class="num">' + b.h + "</span> سم" }, b.foot && { t: "القدم", v: FOOT[b.foot] || esc(b.foot) }, (b.cc || d.cc) && { t: "الجنسية", v: esc(U.country(b.cc || d.cc)) },
      (b.shirt || d.num) && { t: "الرقم", v: '<span class="num">' + esc(b.shirt || d.num) + "</span>" }, b.mv && { t: "القيمة السوقية", v: U.eur(b.mv) }, b.contract && { t: "نهاية العقد", v: '<span class="num">' + esc(String(b.contract).slice(0, 7)) + "</span>" },
      T.born_in && (T.born_in[0] || T.born_in[1]) && { t: "مكان الميلاد", v: esc([T.born_in[0], T.born_in[1]].filter(Boolean).join("، ")) }, T.agent && { t: "الوكيل", v: esc(T.agent) }, b.loan && { t: "الحالة", v: "معار" }].filter(Boolean);
    var inj = d.prof && d.prof.injury && (d.prof.injury.name || d.prof.injury.type) ? '<p class="note" style="background:var(--live-bg)"><b style="color:var(--live)">مصاب:</b> ' + esc(U.injAr ? U.injAr(d.prof.injury.name || d.prof.injury.type) : d.prof.injury.name || d.prof.injury.type) + (d.prof.injury.expected_return ? " · يرجع " + esc(d.prof.injury.expected_return) : "") + "</p>" : "";
    var profile = (inj ? '<section class="grp">' + inj + "</section>" : "") + (bio.length ? U.grp("البطاقة", U.rows(bio)) : "") + (d.ea ? U.grp("في EA SPORTS FC 27", U.eaCard(d.ea, { name: d.name || d.latin, photo: d.photo })) : "") + (d.wiki ? U.grp("عنه", '<p class="wiki">' + d.wiki + "</p>") : "") + (x && x.profile ? x.profile : "");
    // mounted (production): the browser loads the career from his files; when the build has it (d.prof.career, the career cache)
    // it is in the page already for search engines, and the browser only replaces it with something newer (data-pre)
    var mount = x && x.mount, pre = mount && d.prof && d.prof.career ? P.playerCareer({ prof: d.prof }) : "";
    var career = mount ? '<div id="pcar" data-player="' + esc(id) + '"><div id="pcar1"' + (pre ? ' data-pre="1">' + pre : '><div class="card pend">' + U.empty("نحمّل مسيرته…") + "</div>") + "</div>" + P.playerCareer({ transfers: d.transfers }) + "</div>" : P.playerCareer(d);
    var games = mount ? '<div id="plg" data-player="' + esc(id) + '"><div class="card pend">' + U.empty("نحمّل مبارياته…") + "</div></div>" : P.playerGames(d.log);
    var tabs = [["pf", "الملف"], career && ["ca", "المسيرة"], games && ["mt", "المباريات"], ["nw", "الأخبار"]].filter(Boolean);
    var body = head + introHtml + tilesHtml + U.segbar("p", tabs, "pf") + U.pane("p", "pf", profile || '<div class="card">' + U.empty("ما عندنا تفاصيل أكثر عنه.") + "</div>", true) + (career ? U.pane("p", "ca", career) : "") + (games ? U.pane("p", "mt", games) : "") + U.pane("p", "nw", '<div class="enews" data-e="player-' + id + '"><div class="card">' + U.empty("نحمّل الأخبار…") + "</div></div>") +
      (x ? "" : U.grp("", U.rows([{ href: prod("/p/" + id + "/"), icon: "chart", c: "#8E8E93", t: "خريطة تسديداته ومنو يلعب مثله", sub: "بالتصميم الحالي للحين" }]), { cls: "mt2" })) + U.foot();
    var nm = d.name || d.latin || b.name || "";
    return { title: nm + ": أرقامه ومسيرته | تيفو", nav: { back: team ? L("t", team.id) : cfg.base + "/", backLabel: team ? U.tnameT(team) : "رجوع", title: esc(nm), trail: U.navLink("search", "بحث", cfg.base + "/search/") + U.navBtn("share", "شارك", ' data-sheet="sh-share"') }, body: body, tab: "comps", sheets: x && x.share != null ? x.share : P.shareSheet({ acts: [["image", "بطاقة اللاعب", "", "/p/" + id + "/"], ["compare", "قارنه بلاعب", "", "/c/uae-pro-league/compare/?a=" + id]] }) };
  };
  }
  // ------------------------------------------------------------------ news
  P.newsList = function (stories, kind) { var xs = stories.filter(function (s) { return !kind || kind === "all" || s.kind === kind || (kind === "statement" && (s.kind === "presser" || s.kind === "official")); }); return xs.length ? '<div class="card sepd">' + xs.map(U.newsCard).join("") + "</div>" : '<div class="card">' + U.empty("ما في أخبار من هالنوع الحين.") + "</div>"; };
  if (typeof __TIFO_BROWSER__ === "undefined") {   // build-time assemblers: the browser bundle drops them (build.cjs: esbuild define)
  P.news = function (n) {
    var S = (n && n.stories) || [];
    var body = '<div class="lt"><h1>الأخبار</h1><p>من الصحف والقنوات الرسمية، كل قصة بسطر عربي ومصادرها.</p></div>' + U.segbar("nk", [["all", "الكل"], ["transfer", "انتقالات"], ["injury", "إصابات"], ["statement", "تصريحات"]], "all") +
      '<section class="grp" id="mynews" hidden></section><section class="grp"><div id="nlist" data-n="' + S.length + '">' + P.newsList(S.slice(0, 30), "all") + '</div></section><section class="grp" id="nsoc" hidden><div class="gh"><h2>من الحسابات الرسمية</h2></div><div id="nsocb"></div></section>' + U.foot();
    return { title: "أخبار الكورة اليوم: الانتقالات والإصابات والتصريحات | تيفو", nav: { title: "الأخبار", trail: U.navLink("search", "بحث", cfg.base + "/search/") }, body: body, tab: "news", sheets: "" };
  };

  // ------------------------------------------------------------------ competitions (البطولات)
  P.comps = function (index, nats, o) {   // o: {countries: [[iso2, name_ar]] that have a /country/ page}
    o = o || {}; var C = index.competitions || [], REG = [["uae", "الإمارات"], ["gulf", "الخليج"], ["arab", "العرب"], ["asia", "آسيا"], ["africa", "أفريقيا"], ["europe", "أوروبا"], ["world", "العالم"], ["americas", "الأمريكيتين"], ["national", "المنتخبات"]];
    var reg = function (c) { if (c.scope === "uae") return "uae"; if (c.scope === "national") return "national"; if (c.country && c.country.iso2 && ["SA", "QA", "KW", "BH", "OM"].indexOf(c.country.iso2) >= 0) return "gulf"; if (c.region === "gulf" || c.scope === "gulf") return "gulf"; if (c.country && ["EG", "MA", "DZ", "TN", "IQ", "JO", "LB", "LY", "SD", "SY", "PS", "YE", "MR"].indexOf(c.country.iso2) >= 0) return "arab"; return c.region || c.scope || "world"; };
    var by = {}; C.forEach(function (c) { var r = reg(c); (by[r] = by[r] || []).push(c); });
    var crow = function (c) { return '<a class="row ins" href="' + L("c", c.id) + '" data-iso="' + esc((c.country && c.country.iso2) || "") + '">' + U.lg(c.id) + '<span class="rt">' + esc(c.name_ar) + "<small>" + [c.country && c.country.name_ar ? esc(c.country.name_ar) : "", c.season ? '<span class="num">' + esc(c.season) + "</span>" : "", c.dormant ? "متوقفة" : ""].filter(Boolean).join(" · ") + "</small></span>" + CHEV + "</a>"; };
    var compsPane = '<section class="grp" id="favcomps" hidden></section>' + REG.map(function (r) { var list = (by[r[0]] || []).slice().sort(function (a, b) { return (a.dormant ? 1 : 0) - (b.dormant ? 1 : 0); }); return list.length ? U.grp(r[1] + ' <span class="num">' + list.length + "</span>", list.map(crow).join(""), { id: "rg-" + r[0] }) : ""; }).join("") +
      (o.countries && o.countries.length ? U.grp("الكورة في كل دولة عربية", o.countries.map(function (x) { return '<a class="row" href="' + cfg.base + "/country/" + esc(x[0].toLowerCase()) + '/" data-iso="' + esc(x[0]) + '"><span class="rt">' + esc(x[1]) + "<small>مبارياتها اليوم، دوريها ومنتخبها</small></span>" + CHEV + "</a>"; }).join("")) : "") +
      U.grp("الموسوعة", U.rows([{ href: cfg.base + "/db/", icon: "book", c: "#FF9500", t: "كل أندية ولاعبين العالم", sub: "آلاف الأندية من 94 دولة" }, { href: cfg.base + "/db/#champs", icon: "crown", c: "#FFCC00", t: "أبطال كل بطولة عبر التاريخ" }]));
    var natPane = U.grp("المنتخبات العربية", (nats || []).map(function (t) { return '<a class="row ins" href="' + L("t", t.id) + '">' + U.crest(t, "md").replace('class="cr md"', 'class="lg"') + '<span class="rt">' + U.tname(t) + (t.sub ? "<small>" + t.sub + "</small>" : "") + "</span>" + CHEV + "</a>"; }).join("")) + U.grp("", U.rows([{ href: cfg.base + "/national/", icon: "flag", c: "#34C759", t: "ترتيب المنتخبات العربية", sub: "تصنيف تيفو وفيفا وآخر النتايج" }, { href: cfg.base + "/nations-h2h/", icon: "swap", c: "#5856D6", t: "المنتخبات العربية وجهاً لوجه" }]), { cls: "mt2" });
    var body = '<div class="lt"><h1>البطولات</h1><p><span class="num">' + C.length + "</span> بطولة نغطيها، والدوريات العربية كلها</p></div>" + U.segbar("cs", [["c", "البطولات"], ["n", "المنتخبات"]], "c") + U.pane("cs", "c", compsPane, true) + U.pane("cs", "n", natPane) + U.foot();
    return { title: "كل البطولات والمنتخبات | تيفو", nav: { title: "البطولات", trail: U.navLink("search", "بحث", cfg.base + "/search/") }, body: body, tab: "comps", sheets: "" };
  };

  }
  // ------------------------------------------------------------------ فريقي (the client fills it from localStorage + /tn/<id>.json)
  P.picks = function (teams) { return '<div class="picks">' + teams.map(function (t) { return '<button type="button" class="pk" data-pick="' + t.id + '" data-n="' + esc(U.tnameT(t)) + '" aria-pressed="false">' + U.crest(t, "lg") + "<span>" + U.tname(t) + "</span></button>"; }).join("") + "</div>"; };
  if (typeof __TIFO_BROWSER__ === "undefined") {   // build-time assemblers: the browser bundle drops them (build.cjs: esbuild define)
  P.mine = function (popular) {
    var body = '<div class="lt-row lt"><div><h1>فريقي</h1><p>مبارياته وأخباره أول شي، وتنبيه لكل هدف.</p></div><button type="button" class="pill lt-x" data-sheet="sh-pick" id="editfav">تعديل</button></div>' +
      '<div id="minebox"><section class="grp"><div class="card mine-empty"><div class="mine-ic">' + I("star", "", 1.8) + '</div><b>اختار فريقك</b><p class="muted">تابع أكثر من فريق، ومبارياتهم تطلع لك أول شي في «اليوم».</p></div></section>' +
      U.grp("اختار من هني", P.picks(popular), { raw: 1 }) + "</div>" +
      U.grp("", U.rows([{ href: cfg.base + "/predict/", icon: "target", c: "#34C759", t: "توقعاتي", sub: "توقع النتيجة وتحدى ربعك، بدون تسجيل" }]), { cls: "mt2" }) +
      U.grp("الإعدادات", U.rows([{ btn: 1, icon: "globe", c: "#0A84FF", t: "بلدك", v: '<span id="ccv">حسب جوالك</span>', attrs: ' data-sheet="sh-filter"' }, { btn: 1, icon: "star", c: "#FF9500", t: "خلّ تيفو لك من جديد", sub: "فرقك وبلدك في عشر ثواني", attrs: " data-onb" }]), { cls: "mt2" }) + U.foot();
    return { title: "فريقي | تيفو", nav: { title: "فريقي", trail: U.navLink("search", "بحث", cfg.base + "/search/") }, body: body, tab: "mine", sheets: U.sheet("sh-pick", "اختار فرقك", '<div class="sf">' + I("search") + '<input type="search" id="pickq" placeholder="دوّر على فريق" aria-label="دوّر على فريق" autocomplete="off"></div>' + P.picks(popular)) + P.filterSheet() + P.onbSheet() };
  };

  // ------------------------------------------------------------------ المزيد: every other feature, Settings style
  P.more = function (o) {   // o: {audit: {at, n}}
    o = o || {}; var G = function (t, rows, foot) { return U.grp(t, U.rows(rows.filter(Boolean)), { foot: foot }); };
    var body = '<div class="lt"><h1>المزيد</h1></div>' +
      G("الإعدادات", [{ btn: 1, icon: "globe", c: "#0A84FF", t: "بلدك", v: '<span id="ccv">الإمارات</span>', attrs: ' data-sheet="sh-filter"' }, { btn: 1, icon: "star", c: "#FF9500", t: "فرقي وبلدك", sub: "خلّ «اليوم» لك في عشر ثواني", attrs: " data-onb" }, { btn: 1, icon: "eye", c: "#5856D6", t: "بدون حرق", sw: 1, attrs: ' role="switch" aria-checked="false" data-pref="nospoil"' }, o.voices && { btn: 1, icon: "mic", c: "#FF2D55", t: "معلّقك المفضل", sub: "نعلّم مبارياته في القوائم", attrs: ' data-sheet="sh-voices"' }, { btn: 1, icon: "bell", c: "#FF3B30", t: "جزيرة المباراة", sub: "نتيجة فريقك فوق كل صفحة وقت المباراة", sw: 1, attrs: ' role="switch" aria-checked="true" data-pref="island" data-inv="1"' }, { btn: 1, icon: "sound", c: "#FF2D55", t: "صوت الهدف", sw: 1, attrs: ' role="switch" aria-checked="false" data-pref="goalsnd"' }, { btn: 1, icon: "brush", c: "#FF9500", t: "ألوان فريقي", sub: "لون التطبيق من لون فريقك الأول", sw: 1, attrs: ' role="switch" aria-checked="false" data-pref="theme"' }, { btn: 1, icon: "car", c: "#636366", t: "وضع السيارة", sub: "يقرا لك أهداف فرقك بصوت", sw: 1, attrs: ' role="switch" aria-checked="false" data-pref="car"', cls: "carrow" }, { btn: 1, icon: "phone", c: "#34C759", t: "تيفو على شاشة جوالك", sub: "يفتح مثل التطبيق، بدون متجر", attrs: ' data-sheet="sh-install" id="instm"' }]) +
      G("المباريات", [{ href: cfg.base + "/predict/", icon: "target", c: "#34C759", t: "توقعاتي", sub: "توقع النتيجة وتحدى ربعك، بدون تسجيل" }, { href: cfg.base + "/all/", icon: "globe", c: "#0A84FF", t: "كل مباريات العالم اليوم", sub: "كل الدوريات، مباشر" }, { href: cfg.base + "/week/", icon: "calendar", c: "#FF3B30", t: "مباريات الأسبوع" }, { href: cfg.base + "/countdowns/", icon: "clock", c: "#FF9500", t: "كم باقي؟", sub: "عدّادات المباريات الكبيرة" }, { href: cfg.base + "/watch/", icon: "tv", c: "#AF52DE", t: "وين تنقل", sub: "القنوات والباقات والأسعار" }, { href: cfg.base + "/commentators/", icon: "mic", c: "#FF2D55", t: "منو يعلّق اليوم؟", sub: "المعلق والقناة لكل مباراة" }, { href: cfg.base + "/tv/", icon: "tv", c: "#1C7C54", t: "شاشة المجلس", sub: "كل المباريات على شاشة كبيرة" }, { href: cfg.base + "/tv/?mine=1", icon: "star", c: "#FFCC00", t: "وضع المتابعة" }, { href: cfg.base + "/explore/", icon: "search", c: "#8E8E93", t: "أرشيف النتايج", sub: "كل نتيجة من 2016" }, { href: cfg.base + "/transfers/", icon: "swap", c: "#30B0C7", t: "الانتقالات" }]) +
      G("العرب", [{ href: cfg.base + "/arabs/", icon: "plane", c: "#0A84FF", t: "العرب برا", sub: "المحترفين في أوروبا" }, { href: cfg.base + "/national/", icon: "flag", c: "#34C759", t: "المنتخبات العربية" }, { href: cfg.base + "/derbies/", icon: "fire", c: "#FF3B30", t: "الديربيات العربية" }, { href: cfg.base + "/clashes/", icon: "swap", c: "#FF9500", t: "مواجهات الأندية العربية" }, { href: cfg.base + "/streaks/", icon: "chart", c: "#34C759", t: "أرقام متتالية" }, { href: cfg.base + "/golden-boot/", icon: "ball", c: "#FFCC00", t: "الحذاء الذهبي العربي" }, { href: cfg.base + "/poty/", icon: "medal", c: "#FF9F0A", t: "أفضل لاعب عربي" }, { href: cfg.base + "/nations-h2h/", icon: "flag", c: "#5856D6", t: "المنتخبات العربية وجهاً لوجه" }, { href: cfg.base + "/worldcup-arabs/", icon: "globe", c: "#1C7C54", t: "العرب في كأس العالم" }, { href: cfg.base + "/coefficients/", icon: "chart", c: "#8E8E93", t: "تصنيف الاتحادات" }, { href: cfg.base + "/calendars/", icon: "calendar", c: "#FF2D55", t: "مواعيد الدوريات والتوقف" }, { href: cfg.base + "/guide/", icon: "map", c: "#30B0C7", t: "دليل المشاهدة في بلدك" }]) +
      G("التاريخ", [{ href: cfg.base + "/db/", icon: "book", c: "#FF9500", t: "الموسوعة", sub: "كل أندية ولاعبين العالم" }, { href: cfg.base + "/legends/", icon: "crown", c: "#FFCC00", t: "الأساطير" }, { href: cfg.base + "/memorable/", icon: "star", c: "#FF3B30", t: "مباريات ما تنتسى" }, { href: cfg.base + "/thisday/", icon: "hist", c: "#5856D6", t: "هذا اليوم" }, { href: cfg.base + "/messi/", icon: "target", c: "#0A84FF", t: "متحف ميسي" }, { href: cfg.base + "/year/", icon: "calendar", c: "#34C759", t: "السنة الكروية" }]) +
      G("أدوات", [{ href: cfg.base + "/studio/", icon: "brush", c: "#FF2D55", t: "ستوديو التيفو", sub: "صمّم لافتة فريقك" }, { href: cfg.base + "/lab/", icon: "flask", c: "#30B0C7", t: "المختبر", sub: "قارن أي رقمين" }, { href: cfg.base + "/coach/compare/", icon: "compare", c: "#8E8E93", t: "قارن بين مدربين" }, { href: cfg.base + "/ask/", icon: "chat", c: "#34C759", t: "اسأل تيفو" }, { href: cfg.base + "/cast/", icon: "mic", c: "#AF52DE", t: "تيفو كاست" }, { href: cfg.base + "/newsletter/", icon: "mail", c: "#0A84FF", t: "النشرة الأسبوعية" }]) +
      G("عن تيفو", [o.audit && { icon: "check", c: "#34C759", t: "الأرقام مدققة", sub: "نراجع النتايج والأرقام كل يوم" + (o.audit.n ? "، آخر مرة " + '<span class="num">' + U.nf(o.audit.n) + "</span> رقم" : ""), v: U.tm(o.audit.at, "r"), cls: "auditrow" }, { href: cfg.base + "/laws/", icon: "whistle", c: "#1C7C54", t: "قانون الكورة بالإماراتي" }, { href: cfg.base + "/glossary/", icon: "book", c: "#8E8E93", t: "القاموس" }, { href: cfg.base + "/stadiums/", icon: "map", c: "#34C759", t: "دليل الملاعب" }, { href: "https://elyoxe.com/", icon: "info", c: "#636366", t: "Elyoxe", ext: 1 }], "تيفو بدون مراهنات.") + U.foot();
    return { title: "المزيد | تيفو", nav: { title: "المزيد", trail: U.navLink("search", "بحث", cfg.base + "/search/") }, body: body, tab: "more", sheets: P.filterSheet() + P.onbSheet() + (o.voices ? U.sheet("sh-voices", "معلّقك المفضل", o.voices) : "") };
  };
  // ------------------------------------------------------------------ search (the index is loaded on first focus)
  P.search = function (sugg) {
    var body = '<div class="lt"><h1>بحث</h1></div><div class="sf">' + I("search") + '<input type="search" id="q" placeholder="فريق، لاعب، بطولة، مدرب" aria-label="دوّر في تيفو" autocomplete="off" enterkeyhint="search"><button type="button" class="clr" id="qx" aria-label="امسح" hidden>' + I("close", "", 2.4) + "</button></div>" +
      '<div id="sres"></div><div id="sidle"><section class="grp" id="recent" hidden><div class="gh"><h2>آخر بحث</h2><button type="button" id="rclr" class="tx" style="color:var(--accent);font-size:15px">امسح</button></div><div class="card" id="recentl"></div></section>' +
      U.grp("اقتراحات", '<div class="chips" style="justify-content:flex-start;margin:0">' + (sugg || []).map(function (s) { return '<a class="chip" style="height:34px;padding:0 14px;font-size:15px" href="' + s[1] + '">' + esc(s[0]) + "</a>"; }).join("") + "</div>", { raw: 1 }) +
      U.grp("", U.rows([{ href: cfg.base + "/db/", icon: "book", c: "#FF9500", t: "دوّر في الموسوعة", sub: "أكثر من 60 ألف لاعب" }]), { cls: "mt2" }) + "</div>" + U.foot();
    return { title: "بحث | تيفو", nav: { title: "بحث", back: cfg.base + "/", backLabel: "رجوع", trail: "" }, body: body, tab: "", sheets: "" };
  };

  // ------------------------------------------------------------------ the encyclopedia (/db/): browse is prerendered, search and clubs load on demand
  P.db = function (d) {   // {nClubs, nPlayers, nLeagues, nComps, byCountry: [[country, [[id, name, first, last, n, women]]]]}
    var comps = '<div class="card cardlist">' + d.byCountry.map(function (g) { return '<details class="dz"><summary class="row"><span class="rt">' + esc(g[0]) + '</span><span class="rv num">' + g[1].length + "</span>" + CHEV + '</summary><div class="sepd">' + g[1].map(function (c) { return '<a class="row" href="' + L("l", c[0]) + '"><span class="rt">' + esc(c[1]) + "<small>" + (c[2] ? '<span class="num">' + esc(c[2]) + " – " + esc(c[3]) + "</span> · " : "") + '<span class="num">' + c[4] + "</span> بطل" + (c[5] ? " · سيدات" : "") + "</small></span>" + CHEV + "</a>"; }).join("") + "</div></details>"; }).join("") + "</div>";
    var body = '<div class="lt"><h1>الموسوعة</h1><p>' + '<span class="num">' + U.nf(d.nClubs) + "</span> نادي و" + '<span class="num">' + U.nf(d.nPlayers) + "</span> لاعب، وأبطال " + '<span class="num">' + U.nf(d.nComps) + "</span> بطولة من أول موسم.</p></div>" +
      '<div class="sf">' + I("search") + '<input type="search" id="wq" placeholder="دوّر على نادي أو لاعب، بالعربي أو الإنجليزي" aria-label="دوّر في الموسوعة" autocomplete="off" enterkeyhint="search"><button type="button" class="clr" id="wqx" aria-label="امسح" hidden>' + I("close", "", 2.4) + "</button></div>" +
      '<div id="wr"></div><div id="widle">' + U.segbar("w", [["c", "البطولات وأبطالها"], ["k", "الأندية حسب الدولة"]], "c") + U.pane("w", "c", '<div id="champs" class="stack">' + comps + "</div>", true) + U.pane("w", "k", '<div id="wclubs" class="stack"><div class="card">' + U.empty("نحمّل الأندية…") + "</div></div>") + "</div>" + U.foot('<p>الأبطال من 365Scores، والأندية واللاعبين من FotMob.</p>');
    return { title: "موسوعة تيفو: كل أندية ولاعبين العالم | تيفو", nav: { title: "الموسوعة", back: cfg.base + "/competitions/", backLabel: "البطولات", trail: "" }, body: body, tab: "comps", sheets: "" };
  };
  P.league = function (c, o) {   // s365/comp/<id>.json; o: {team: id365 -> href, logo}
    o = o || {}; var N = c.names || {}, CH = c.champions || [], won = CH.filter(function (r) { return r[1]; }), cols = c.cols || [];
    var tl = function (t) { return o.team ? o.team(t) : "/db/team/?id=" + t; }, nm = function (t) { return N[t] || ""; };
    var cnt = {}; won.forEach(function (r) { cnt[r[1]] = (cnt[r[1]] || 0) + 1; });
    var top = Object.keys(cnt).sort(function (a, b) { return cnt[b] - cnt[a]; }), mx = top.length ? cnt[top[0]] : 1, first = CH.length ? CH[CH.length - 1][0] : "", last = CH.length ? CH[0][0] : "";
    var head = '<header class="hdr th">' + (o.logo ? '<img class="cr xl" src="' + o.logo + '" alt="" width="64" height="64">' : "") + "<h1>أبطال " + esc(c.name) + '</h1><p class="sub">' + [c.country ? esc(c.country) : "", c.name_en ? '<span class="lat">' + esc(c.name_en) + "</span>" : ""].filter(Boolean).join(" · ") + "</p>" +
      (won.length ? '<div class="chips"><span class="chip">من <span class="num">&nbsp;' + esc(first) + "&nbsp;</span> لين <span class=\"num\">&nbsp;" + esc(last) + "</span></span><span class=\"chip\"><span class=\"num\">" + won.length + "</span>&nbsp;موسم</span><span class=\"chip\"><span class=\"num\">" + top.length + "</span>&nbsp;" + (top.length > 10 ? "بطل" : "أبطال") + "</span></div>" : "") + "</header>";
    var lead = top.length ? '<p class="note">فاز فيها <b class="num">' + top.length + "</b> " + (top.length > 10 ? "فريق" : "فرق") + " في <b class=\"num\">" + won.length + "</b> موسم، وأكثرهم " + "<b>" + esc(nm(top[0])) + "</b> بـ<b class=\"num\">" + mx + "</b> " + (mx > 10 ? "لقب" : "ألقاب") + ".</p>" : "";
    var bars = top.length ? U.grp("الأكثر تتويجاً", '<ol class="card bars">' + top.slice(0, 12).map(function (t) { return '<li><a class="bl" href="' + tl(t) + '"><span class="bn"><span>' + esc(nm(t)) + '</span></span><b class="num">' + cnt[t] + '</b><i style="--w:' + Math.round(cnt[t] / mx * 100) + '%"></i></a></li>'; }).join("") + "</ol>", { raw: 1 }) : "";
    var list = CH.length ? U.grp("كل الأبطال " + '<span class="num">' + won.length + "</span>", '<div class="tblw"><table class="tbl"><thead><tr><th>الموسم</th><th class="tm">البطل</th>' + cols.map(function (x) { return "<th>" + esc(x) + "</th>"; }).join("") + "</tr></thead><tbody>" + CH.map(function (r) { return '<tr><td class="dim">' + esc(r[0]) + '</td><td class="tm">' + (r[1] ? '<a href="' + tl(r[1]) + '"><span class="n">' + esc(nm(r[1])) + "</span></a>" : '<span class="muted">—</span>') + "</td>" + cols.map(function (x, i) { return "<td>" + esc((r[2] || [])[i] == null ? "" : r[2][i]) + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table></div>") : "";
    var L2 = c.live, liveT = L2 && L2.table && L2.table.length ? U.grp("الترتيب الحين", '<div class="tblw"><table class="tbl"><thead><tr><th>#</th><th class="tm">الفريق</th><th>لعب</th><th>+/-</th><th>نقاط</th></tr></thead><tbody>' + L2.table.map(function (r) { return '<tr><td class="rk">' + (r[0] == null ? "" : r[0]) + '</td><td class="tm"><a href="' + tl(r[1]) + '"><span class="n">' + esc(nm(r[1])) + "</span></a></td><td>" + (r[2] == null ? "" : r[2]) + '</td><td class="dim"><bdi dir="ltr">' + ((r[6] || 0) - (r[7] || 0) > 0 ? "+" : "") + ((r[6] || 0) - (r[7] || 0)) + '</bdi></td><td class="pts">' + (r[8] == null ? "" : Math.round(r[8])) + "</td></tr>"; }).join("") + "</tbody></table></div>") : "";
    var T = c.tables || {}, seasons = Object.keys(T).sort().reverse(), finals = seasons.length ? U.grp("الترتيب النهائي موسم بموسم", seasons.slice(0, o.all ? 999 : 6).map(function (s, i) { return '<details class="dz"' + (i ? "" : " open") + '><summary class="row"><span class="rt num">' + esc(s) + "</span>" + CHEV + '</summary><div class="tblw"><table class="tbl"><tbody>' + T[s].map(function (r) { return '<tr><td class="rk">' + (r[0] == null ? "" : r[0]) + '</td><td class="tm"><a href="' + tl(r[1]) + '"><span class="n">' + esc(nm(r[1])) + "</span></a></td><td>" + (r[2] == null ? "" : r[2]) + '</td><td class="pts">' + (r[8] == null ? "" : Math.round(r[8])) + "</td></tr>"; }).join("") + "</tbody></table></div></details>"; }).join(""), { foot: seasons.length > 6 && !o.all ? '<a href="/db/league/' + c.id + '/">كل المواسم (' + seasons.length + ")</a>" : "" }) : "";
    var res = o.results && L2 && (L2.results || []).length ? U.grp("آخر النتايج", L2.results.slice(0, 20).map(function (g) { return '<a class="row" href="' + cfg.base + "/db/game/?id=" + esc(g[0]) + '"><span class="rt">' + esc(nm(g[4])) + (g[6] == null ? " ضد " : ' <span dir="rtl" class="num">' + g[6] + " - " + g[7] + "</span> ") + esc(nm(g[5])) + (o.date ? "<small>" + esc(o.date(g[1])) + "</small>" : "") + "</span>" + CHEV + "</a>"; }).join("")) : "";
    var body = head + lead + liveT + res + bars + list + finals + U.foot("<p>من 365Scores." + (c.generated ? " آخر تحديث " + esc(String(c.generated).slice(0, 10)) + "." : "") + "</p>");
    return { title: "أبطال " + c.name + " عبر التاريخ | تيفو", nav: { back: cfg.base + "/db/", backLabel: "الموسوعة", title: "أبطال " + esc(c.name), trail: "" }, body: body, tab: "comps", sheets: "" };
  };

  }
  if (typeof module !== "undefined" && module.exports) module.exports = P; else root.P5 = P;
})(typeof window !== "undefined" ? window : this);
