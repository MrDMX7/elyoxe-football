/* تيفو: the world encyclopedia (/db/, owner 2026-09-30 «ابغي الموقع يشمل كل الاندية… وكل اللاعبين»). One template per kind,
   filled in the browser from db/world.py's files: every club of ~300 leagues in 94 countries and every player of their
   squads. A club or player the live site already covers is sent to its /t/ or /p/ page. */
(function(){
  "use strict";
  var R = window.TR, $ = function(s){ return document.querySelector(s); }, V = "/v1/";
  var esc = R.esc, box = $("#world"); if (!box) return;
  var kind = box.dataset.kind, q = new URLSearchParams(location.search), id = q.get("id");
  function get(p){ return fetch(V + p).then(function(r){ if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function has(url){ return fetch(url, { method:"HEAD" }).then(function(r){ return r.ok; }).catch(function(){ return false; }); }
  var eur = function(v){ return v == null ? "—" : v >= 1e6 ? "€" + (Math.round(v / 1e5) / 10) + " مليون" : "€" + Math.round(v / 1e3) + " ألف"; };
  var FOOT = { left:"اليسرى", right:"اليمنى", both:"الثنتين" };
  var clubUrl = function(c){ return "/db/club/?id=" + c; }, playerUrl = function(p){ return "/db/player/?id=" + p; };
  function title(t){ document.title = t + " | موسوعة تيفو"; var h = $("#wt"); if (h) h.textContent = t; }
  var IMG = "https://imagecache.365scores.com/image/upload/f_png,w_64,h_64,c_limit,q_auto:eco,dpr_2,d_";
  var leagueUrl = function(c){ return "/db/league/?id=" + c; }, teamUrl = function(t){ return "/db/team/?id=" + t; }, gameUrl = function(g){ return "/db/game/?id=" + g; }, athUrl = function(p){ return "/db/athlete/?id=" + p; };
  var logo = function(kind, i){ return '<img class="wlogo" src="' + IMG + kind + ":default1.png/" + kind + "/" + i + '" alt="" width="32" height="32" loading="lazy" onerror="this.remove()">'; };
  var dstr = function(s){ var d = s ? new Date(s) : null; return d && !isNaN(d) ? d.toLocaleDateString("ar-AE-u-nu-latn", { year:"numeric", month:"short", day:"numeric" }) : ""; };
  var src365 = '<p class="src">من 365Scores. <a href="/db/">الموسوعة</a></p>';

  // ---------------------------------------------------------------- search + browse
  if (kind === "index"){
    Promise.all([get("world/index.json"), get("world/leagues.json"), get("s365/index.json").catch(function(){ return null; })]).then(function(x){
      var I = x[0], L = x[1].leagues, S = x[2], inp = $("#wq"), out = $("#wr");
      var fold = function(s){ return String(s || "").toLowerCase().replace(/[أإآ]/g, "ا").replace(/ة/g, "ه").replace(/ى/g, "ي").replace(/[ً-ْـ]/g, ""); };
      var clubs = I.clubs.map(function(c){ return { t:"c", id:c[0], ar:c[1], en:c[2], cc:c[3], k:fold(c[1]) + " " + fold(c[2]) }; });
      var players = I.players.map(function(p){ return { t:"p", id:p[0], ar:p[1], en:p[2], club:p[3], k:fold(p[1]) + " " + fold(p[2]) }; });
      var cname = {}; I.clubs.forEach(function(c){ cname[c[0]] = c[1]; });
      var sname = {};
      if (S){ S.teams.forEach(function(t){ sname[t[0]] = t[1]; });
        clubs = clubs.concat(S.teams.filter(function(t){ return !t[4]; }).map(function(t){ return { t:"s", id:t[0], ar:t[1], en:t[2], cc:t[3], k:fold(t[1]) + " " + fold(t[2]) }; }));
        players = players.concat(S.players.map(function(p){ return { t:"a", id:p[0], ar:p[1], en:p[2], club:p[3], k:fold(p[1]) + " " + fold(p[2]) }; }));
        var wc = $("#wcomp");
        if (wc){ var CN = S.countries || {}, byCC = {}, nC = 0;
          S.comps.filter(function(c){ return c[5] > 0 && !c[11]; }).forEach(function(c){ (byCC[c[3]] = byCC[c[3]] || []).push(c); nC++; });
          var AR = [124, 122, 115, 131, 127, 139, 135, 114, 126, 119, 123, 125, 161, 130, 116, 117, 226, 170];
          var keys = Object.keys(byCC).map(Number).sort(function(a, b){ var ia = AR.indexOf(a), ib = AR.indexOf(b); if (ia >= 0 || ib >= 0) return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
            return ((CN[a] || [""])[0] || "").localeCompare((CN[b] || [""])[0] || "", "ar"); });
          wc.innerHTML = '<p class="muted small"><span class="num">' + nC + "</span> بطولة، كل أبطالها من أول موسم</p>" + keys.map(function(cc){ var cs = byCC[cc].sort(function(a, b){ return b[5] - a[5]; });
            return '<details class="wc"><summary>' + esc((CN[cc] || [""])[0] || "") + ' <span class="muted small num">' + cs.length + '</span></summary><ul class="mlist cols">' + cs.map(function(c){
              return '<li><a href="' + (c[5] >= 5 && !c[11] ? "/db/league/" + c[0] + "/" : leagueUrl(c[0])) + '">' + esc(c[1]) + '</a> <span class="muted small num">' + esc(c[6]) + " – " + esc(c[7]) + "</span>" + (c[8] ? ' <span class="muted small">سيدات</span>' : "") + "</li>"; }).join("") + "</ul></details>"; }).join(""); } }
      $("#wn").textContent = clubs.length.toLocaleString("en") + " نادي و" + players.length.toLocaleString("en") + " لاعب في " + L.length + " دوري" + (S ? " و" + S.comps.length + " بطولة بأبطالها" : "");
      inp.oninput = function(){ var s = fold(inp.value.trim()); if (s.length < 2){ out.innerHTML = ""; return; }
        var hc = clubs.filter(function(c){ return c.k.indexOf(s) >= 0; }).slice(0, 30), hp = players.filter(function(p){ return p.k.indexOf(s) >= 0; }).slice(0, 40);
        out.innerHTML = (hc.length ? "<h3>أندية</h3><ul class=\"mlist cols\">" + hc.map(function(c){ return '<li><a href="' + (c.t === "s" ? teamUrl : clubUrl)(c.id) + '">' + esc(c.ar) + '</a> <span class="muted small lat">' + esc(c.en) + "</span></li>"; }).join("") + "</ul>" : "") +
          (hp.length ? "<h3>لاعبين</h3><ul class=\"mlist cols\">" + hp.map(function(p){ return '<li><a href="' + (p.t === "a" ? athUrl : playerUrl)(p.id) + '">' + esc(p.ar) + '</a> <span class="muted small">' + esc((p.t === "a" ? sname : cname)[p.club] || "") + "</span></li>"; }).join("") + "</ul>" : "") || '<p class="empty">ما لقينا شي.</p>'; };
      var byC = {}; L.forEach(function(l){ (byC[l.cc] = byC[l.cc] || { name:l.country_ar || l.cc, ls:[] }).ls.push(l); });
      $("#wb").innerHTML = Object.keys(byC).sort(function(a, b){ return byC[a].name.localeCompare(byC[b].name, "ar"); }).map(function(cc){ var c = byC[cc];
        return '<details class="wc"><summary>' + esc(c.name) + ' <span class="muted small num">' + c.ls.reduce(function(a, l){ return a + l.clubs.length; }, 0) + "</span></summary>" + c.ls.map(function(l){
          return "<h4>" + esc(l.name_ar || l.name) + '</h4><p class="wl">' + l.clubs.map(function(k){ return '<a href="' + clubUrl(k) + '">' + esc(cname[k] || k) + "</a>"; }).join(" · ") + "</p>"; }).join("") + "</details>"; }).join("");
    }).catch(function(){ box.innerHTML = '<p class="empty">ما قدرنا نحمّل الموسوعة الحين.</p>'; });
    return;
  }
  if (!id){ box.innerHTML = '<p class="empty">ما حددت نادي أو لاعب. <a href="/db/">ارجع للموسوعة</a></p>'; return; }

  // ================================================================ 365Scores (db/scores365.py): every competition's champions
  // through history, Arab final tables, and the Arab leagues FotMob doesn't cover in full (squads, matches, player cards)
  function gameRow(g, N){ // [id, date, season, round, home, away, hs, as, status, lineups]
    var sc = g[6] == null ? '<span class="muted">' + esc((g[1] || "").slice(11, 16)) + "</span>" : '<bdi dir="rtl" class="num">' + g[6] + " - " + g[7] + "</bdi>";
    return '<li><span class="num muted small">' + esc(dstr(g[1])) + '</span> <a href="' + teamUrl(g[4]) + '">' + esc(N[g[4]] || "") + "</a> " + (g[8] === 4 ? '<a href="' + gameUrl(g[0]) + '">' + sc + "</a>" : sc) + ' <a href="' + teamUrl(g[5]) + '">' + esc(N[g[5]] || "") + "</a></li>"; }
  function tableHtml(rows, N){ return '<div class="tscroll"><table class="tbl"><thead><tr><th>#</th><th>الفريق</th><th>لعب</th><th>فوز</th><th>تعادل</th><th>خسارة</th><th>له-عليه</th><th>نقاط</th></tr></thead><tbody>' +
    rows.map(function(r){ return '<tr><td class="num">' + (r[0] == null ? "" : r[0]) + '</td><td><a href="' + teamUrl(r[1]) + '">' + esc(N[r[1]] || "") + "</a>" + (r[9] != null ? ' <span class="muted small">' + esc(r[9]) + "</span>" : "") + '</td><td class="num">' + (r[2] == null ? "" : r[2]) + '</td><td class="num">' + (r[3] == null ? "" : r[3]) + '</td><td class="num">' + (r[4] == null ? "" : r[4]) + '</td><td class="num">' + (r[5] == null ? "" : r[5]) +
      '</td><td class="num"><bdi dir="ltr">' + (r[6] == null ? "" : r[6]) + "-" + (r[7] == null ? "" : r[7]) + '</bdi></td><td class="num">' + (r[8] == null ? "" : Math.round(r[8])) + "</td></tr>"; }).join("") + "</tbody></table></div>"; }

  if (kind === "league"){
    if (!/\/db\/league\/\d+\/$/.test(location.pathname)) has("/db/league/" + id + "/").then(function(live){ if (live) location.replace("/db/league/" + id + "/" + location.hash); });
    get("s365/comp/" + id + ".json").then(function(c){
      title(c.name); var N = c.names || {}, CH = c.champions || [], won = CH.filter(function(r){ return r[1]; });
      var html = '<p class="season">' + logo("Competitions", c.id) + [c.country && esc(c.country), c.name_en && '<span class="lat">' + esc(c.name_en) + "</span>",
        won.length && "أبطالها من <b class=\"num\">" + esc(CH[CH.length - 1][0]) + "</b> لين <b class=\"num\">" + esc(CH[0][0]) + "</b>"].filter(Boolean).join(" · ") + "</p>";
      var L = c.live;
      if (L && L.table && L.table.length) html += '<section class="blk"><h2>الترتيب الحين</h2>' + tableHtml(L.table, N) + "</section>";
      if (L && L.results && L.results.length) html += '<section class="blk"><h2>آخر النتايج <small>' + L.results.length + '</small></h2><ul class="mlist wgm">' + L.results.slice(0, 40).map(function(g){ return gameRow(g, N); }).join("") + "</ul>" +
        (L.results.length > 40 ? '<details><summary>كل النتايج (' + L.results.length + ')</summary><ul class="mlist wgm">' + L.results.slice(40).map(function(g){ return gameRow(g, N); }).join("") + "</ul></details>" : "") + "</section>";
      if (L && L.fixtures && L.fixtures.length) html += '<section class="blk"><h2>المباريات الجاية</h2><ul class="mlist wgm">' + L.fixtures.slice(0, 30).map(function(g){ return gameRow(g, N); }).join("") + "</ul></section>";
      if (L && L.scorers && Object.keys(L.scorers).length) html += '<section class="blk"><h2>الهدافين هالموسم</h2><div class="hbig">' + Object.keys(L.scorers).map(function(k){
        return "<div><h3>" + esc(k) + '</h3><ol class="mlist">' + L.scorers[k].map(function(r){ return '<li><a href="' + athUrl(r[0]) + '">' + esc(r[1] || "") + '</a> <span class="muted small">' + esc(N[r[2]] || "") + '</span> <b class="num">' + esc(r[3] == null ? "" : r[3]) + "</b></li>"; }).join("") + "</ol></div>"; }).join("") + "</div></section>";
      if (won.length){
        var cnt = {}; won.forEach(function(r){ cnt[r[1]] = (cnt[r[1]] || 0) + 1; });
        var top = Object.keys(cnt).sort(function(a, b){ return cnt[b] - cnt[a]; }), mx = cnt[top[0]];
        html += '<section class="blk"><h2>الأكثر تتويجاً</h2><ul class="bars">' + top.slice(0, 15).map(function(t){ return '<li><span><a href="' + teamUrl(t) + '">' + esc(N[t] || "") + '</a></span><i style="--w:' + Math.round(cnt[t] / mx * 100) + '%"></i><b class="num">' + cnt[t] + "</b></li>"; }).join("") + "</ul></section>";
        var cols = c.cols || [], T = c.tables || {};
        html += '<section class="blk"><h2>كل الأبطال <small>' + won.length + '</small></h2><div class="tscroll"><table class="tbl"><thead><tr><th>الموسم</th><th>البطل</th>' + cols.map(function(x){ return "<th>" + esc(x) + "</th>"; }).join("") + "<th></th></tr></thead><tbody>" +
          CH.map(function(r){ return '<tr><td class="num">' + esc(r[0]) + "</td><td>" + (r[1] ? '<a href="' + teamUrl(r[1]) + '">' + esc(N[r[1]] || "") + "</a>" : '<span class="muted">—</span>') + "</td>" + cols.map(function(x, i){ return '<td class="num">' + esc((r[2] || [])[i] == null ? "" : r[2][i]) + "</td>"; }).join("") +
            "<td>" + (T[r[0]] ? '<a href="#t-' + encodeURIComponent(r[0]) + '" class="small">الجدول</a>' : "") + "</td></tr>"; }).join("") + "</tbody></table></div></section>";
        var seasons = Object.keys(T);
        if (seasons.length){
          seasons.sort().reverse();
          html += '<section class="blk" id="wtab"><h2>الترتيب النهائي موسم بموسم</h2><p><select id="wts" aria-label="الموسم">' + seasons.map(function(s){ return '<option value="' + esc(s) + '">' + esc(s) + "</option>"; }).join("") + '</select></p><div id="wtt"></div></section>';
        }
      }
      box.innerHTML = html + src365;
      var sel = $("#wts");
      if (sel){ var show = function(){ $("#wtt").innerHTML = tableHtml(c.tables[sel.value], N); }; sel.onchange = show;
        var h = decodeURIComponent((location.hash || "").replace(/^#t-/, "")); if (h && c.tables[h]) sel.value = h; show();
        box.addEventListener("click", function(e){ var a = e.target.closest && e.target.closest('a[href^="#t-"]'); if (!a) return; e.preventDefault(); sel.value = decodeURIComponent(a.getAttribute("href").slice(3)); show(); $("#wtab").scrollIntoView({ behavior:"smooth" }); }); }
    }).catch(function(){ box.innerHTML = '<p class="empty">ما لقينا هالبطولة. <a href="/db/">الموسوعة</a></p>'; });
    return;
  }

  if (kind === "team"){
    get("s365/team/" + id + ".json").then(function(t){
      title(t.name || t.name_en || "");
      var html = '<p class="season">' + logo("Competitors", t.id) + [t.country && "من " + esc(t.country), t.name_en && '<span class="lat">' + esc(t.name_en) + "</span>"].filter(Boolean).join(" · ") + "</p>";
      if (t.fotmob) html += '<p><a class="btn" id="wfm" href="/db/club/?id=' + t.fotmob + '">صفحته الكاملة في تيفو ←</a></p>';
      var T = t.titles || [];
      if (T.length) html += '<section class="blk"><h2>ألقابه <small>' + T.reduce(function(a, x){ return a + x[2].length; }, 0) + '</small></h2><ul class="chon">' + T.map(function(x){
        return '<li><b><a href="' + leagueUrl(x[0]) + '">' + esc(x[1]) + '</a></b> <span class="num">' + x[2].length + '</span><span class="muted small yrs">' + esc(x[2].join("، ")) + "</span></li>"; }).join("") + "</ul></section>";
      var S = t.squad || [];
      if (S.length){ var groups = {}, order = []; S.forEach(function(p){ var g = p[3] || "—"; if (!groups[g]){ groups[g] = []; order.push(g); } groups[g].push(p); });
        html += '<section class="blk"><h2>اللاعبين <small>' + S.length + "</small></h2>" + order.map(function(g){ return "<h3>" + esc(g) + '</h3><ul class="mlist cols">' + groups[g].map(function(p){
          return "<li>" + (p[2] > 0 ? '<span class="num muted">' + p[2] + "</span> " : "") + '<a href="' + athUrl(p[0]) + '">' + esc(p[1] || "") + "</a>" + (p[5] ? ' <span class="muted small num">' + p[5] + "</span>" : "") + "</li>"; }).join("") + "</ul>"; }).join("") + "</section>"; }
      var G = t.games || [], N = t.names || {};
      if (G.length) html += '<section class="blk"><h2>مبارياته <small>' + G.length + '</small></h2><ul class="mlist wgm">' + G.map(function(g){ return gameRow(g, N); }).join("") + "</ul></section>";
      box.innerHTML = html + src365;
      if (t.fotmob) has("/t/" + t.fotmob + "/").then(function(live){ if (live){ var a = $("#wfm"); if (a) a.href = "/t/" + t.fotmob + "/"; } });
    }).catch(function(){ box.innerHTML = '<p class="empty">ما لقينا هالفريق. <a href="/db/">الموسوعة</a></p>'; });
    return;
  }

  if (kind === "game"){
    get("s365/game/" + id + ".json").then(function(m){
      var hn = m.home[1] || "", an = m.away[1] || ""; title(hn + " " + (m.home[2] == null ? "" : m.home[2]) + " - " + (m.away[2] == null ? "" : m.away[2]) + " " + an);
      var html = '<div class="wmh"><a href="' + teamUrl(m.home[0]) + '">' + esc(hn) + '</a><bdi dir="rtl" class="num wsc">' + (m.home[2] == null ? "" : m.home[2]) + " - " + (m.away[2] == null ? "" : m.away[2]) + '</bdi><a href="' + teamUrl(m.away[0]) + '">' + esc(an) + "</a></div>" +
        '<p class="season">' + [m.comp_name && '<a href="' + leagueUrl(m.comp) + '">' + esc(m.comp_name) + "</a>" + (m.round ? " · الجولة " + m.round : ""), dstr(m.date), m.venue && (/^(ملعب|استاد|ستاد)/.test(m.venue) ? "" : "ملعب ") + esc(m.venue), m.referee && "الحكم " + esc(m.referee)].filter(Boolean).join(" · ") + "</p>";
      var EV = { g:"هدف", y:"إنذار", r:"طرد", s:"تبديل" };
      if ((m.events || []).length) html += '<section class="blk"><h2>أحداث المباراة</h2><ul class="mlist wev">' + m.events.map(function(e){
        var who = e[3] ? '<a href="' + athUrl(e[3]) + '">' + esc(e[4] || "") + "</a>" : esc(e[4] || "");
        var extra = e[1] === "g" ? (e[7] && !/ميدان/.test(e[7]) ? " (" + esc(e[7]) + ")" : "") + (e[5] ? ' · صناعة <a href="' + athUrl(e[5]) + '">' + esc(e[6] || "") + "</a>" : "") : e[1] === "s" && e[6] ? " · " + esc(e[6]) : "";
        return '<li class="' + e[2] + '"><span class="num">' + esc(e[0]) + '′</span> <span class="ev ' + e[1] + '">' + (EV[e[1]] || "") + "</span> " + who + extra + ' <span class="muted small">' + esc(e[2] === "h" ? hn : an) + "</span></li>"; }).join("") + "</ul></section>";
      var L = m.lineups || {};
      if (L.h || L.a) html += '<section class="blk"><h2>التشكيلة</h2><div class="hbig">' + ["h", "a"].map(function(s){ var t = L[s]; if (!t) return "<div></div>";
        return "<div><h3>" + esc(s === "h" ? hn : an) + (t.formation ? ' <span class="muted small num">' + esc(t.formation) + "</span>" : "") + '</h3><ol class="mlist wlu">' + t.players.map(function(p){
          return "<li" + (p[4] ? "" : ' class="sub"') + ">" + (p[2] > 0 ? '<span class="num muted">' + esc(p[2]) + "</span> " : "") + '<a href="' + athUrl(p[0]) + '">' + esc(p[1] || "") + "</a>" + ' <span class="muted small">' + esc(p[3] || "") + "</span>" +
            (p[5] != null ? ' <span class="num muted small">' + p[5] + "′</span>" : "") + (+p[6] ? ' <span class="ev g">' + p[6] + "</span>" : "") + (+p[7] ? ' <span class="muted small">صناعة ' + p[7] + "</span>" : "") + "</li>"; }).join("") + "</ol></div>"; }).join("") + "</div></section>";
      box.innerHTML = html + src365;
    }).catch(function(){ box.innerHTML = '<p class="empty">ما لقينا تفاصيل هالمباراة. <a href="/db/">الموسوعة</a></p>'; });
    return;
  }

  if (kind === "athlete"){
    get("s365/player/" + id + ".json").then(function(d){
      title(d.name || d.en || ""); var N = d.names || {};
      var rows = [d.pos && ["المركز", esc(d.pos) + (d.pos2 && d.pos2 !== d.pos ? ' <span class="muted small">' + esc(d.pos2) + "</span>" : "")], d.age && ["العمر", d.age + " سنة" + (d.born ? ' <span class="muted small num">' + esc(d.born) + "</span>" : "")],
        d.height && ["الطول", esc(d.height) + " م"], d.foot && ["القدم", esc(d.foot)], d.nat && ["الجنسية", esc(d.nat)], d.shirt > 0 && ["الرقم", d.shirt],
        d.club && ["النادي", '<a href="' + teamUrl(d.club) + '">' + esc(N[d.club] || "") + "</a>"], d.contract && ["نهاية العقد", '<span class="num">' + esc(d.contract.slice(0, 7)) + "</span>"],
        d.nat_text && ["مع المنتخب", esc(d.nat_text)]].filter(Boolean);
      var html = (d.en ? '<p class="season lat">' + esc(d.en) + "</p>" : "") + (rows.length ? '<dl class="pbio">' + rows.map(function(r){ return "<div><dt>" + r[0] + "</dt><dd>" + r[1] + "</dd></div>"; }).join("") + "</dl>" : "") + (d.bio ? "<p>" + esc(d.bio) + "</p>" : "");
      var C = d.career || [];
      if (C.length) html += '<section class="blk"><h2>مسيرته موسم بموسم</h2><div class="tscroll"><table class="tbl"><thead><tr><th>الموسم</th><th>مع</th><th>البطولة</th><th>مباريات</th><th>أساسي</th><th>أهداف</th><th>صناعة</th><th>صفراء</th><th>حمراء</th></tr></thead><tbody>' +
        C.map(function(r){ return '<tr><td class="num">' + esc(r[0] || "") + '</td><td class="small">' + esc(r[1] || "") + "</td><td>" + esc(r[2] || "") + "</td>" + [3, 4, 5, 6, 7, 8].map(function(i){ return '<td class="num">' + esc(r[i] == null ? "" : r[i]) + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table></div></section>";
      var TR = d.trophies || [];
      if (TR.length) html += '<section class="blk"><h2>ألقابه <small>' + TR.reduce(function(a, t){ return a + (+t[2] || 0); }, 0) + '</small></h2><ul class="chon">' + TR.map(function(t){
        return "<li><b>" + esc(t[1] || "") + '</b> <span class="num">' + esc(t[2]) + '</span><span class="muted small yrs">' + esc(t[3].map(function(x){ return (x[1] || "") + (x[0] ? " (" + x[0] + ")" : ""); }).join("، ")) + "</span></li>"; }).join("") + "</ul></section>";
      var X = d.transfers || [];
      if (X.length) html += '<section class="blk"><h2>انتقالاته</h2><ul class="mlist">' + X.map(function(t){ return '<li><span class="num">' + esc(t[0]) + '</span> <a href="' + teamUrl(t[1]) + '">' + esc(N[t[1]] || "") + '</a> <span class="muted small">' + esc(t[2] || "") + (t[3] ? " · " + esc(t[3]) : "") + "</span></li>"; }).join("") + "</ul></section>";
      box.innerHTML = html + src365;
    }).catch(function(){ box.innerHTML = '<p class="empty">ما لقينا هاللاعب. <a href="/db/">الموسوعة</a></p>'; });
    return;
  }

  // ---------------------------------------------------------------- a club
  if (kind === "club"){
    has("/t/" + id + "/").then(function(live){ if (live){ location.replace("/t/" + id + "/"); return; }
      get("world/club/" + id + ".json").then(function(c){
        var nm = c.name_ar || c.name; title(nm);
        var v = c.venue || {}, facts = [c.country_ar && "من " + esc(c.country_ar), c.league_ar && "يلعب في " + esc(c.league_ar) + (c.position ? " (المركز " + c.position + ")" : ""),
          v.name && "ملعبه " + esc(v.name) + (v.capacity ? " (" + Number(v.capacity).toLocaleString("en") + " متفرج)" : ""), v.city && "في " + esc(v.city), v.opened && "افتُتح " + v.opened].filter(Boolean);
        var html = '<p class="season">' + facts.join(" · ") + (c.name_ar && c.name ? ' <span class="muted small lat">' + esc(c.name) + "</span>" : "") + "</p>";
        var tro = (c.trophies || []).filter(function(t){ return t.won > 0; });
        if (tro.length) html += '<section class="blk"><h2>ألقابه <small>' + tro.reduce(function(a, t){ return a + t.won; }, 0) + '</small></h2><ul class="chon">' + tro.map(function(t){ return "<li><b>" + esc(t.name || "") + '</b> <span class="num">' + t.won + '</span><span class="muted small yrs">' + esc(t.seasons.join("، ")) + "</span></li>"; }).join("") + "</ul></section>";
        var sq = (c.squad || []).filter(function(m){ return m[3] !== "coach"; }), coach = (c.squad || []).filter(function(m){ return m[3] === "coach"; });
        var GR = { keepers:"حراس المرمى", defenders:"الدفاع", midfielders:"الوسط", attackers:"الهجوم" }, groups = {};
        sq.forEach(function(m){ (groups[m[3]] = groups[m[3]] || []).push(m); });
        if (sq.length) html += '<section class="blk"><h2>اللاعبين <small>' + sq.length + "</small></h2>" + (coach.length ? "<p>المدرب: " + esc(coach[0][1]) + "</p>" : "") + Object.keys(groups).map(function(g){
          return "<h3>" + esc(GR[g] || g) + '</h3><ul class="mlist cols">' + groups[g].map(function(m){ return "<li>" + (m[2] ? '<span class="num muted">' + m[2] + "</span> " : "") + '<a href="' + playerUrl(m[0]) + '">' + esc(m[1]) + "</a></li>"; }).join("") + "</ul>"; }).join("") + "</section>";
        var RK = (c.ranks || []).filter(function(r){ return r[1]; });
        if (RK.length) html += '<section class="blk"><h2>ترتيبه في الدوري موسم بموسم</h2><table class="tbl"><thead><tr><th>الموسم</th><th>المركز</th><th>من</th><th>النقاط</th></tr></thead><tbody>' + RK.slice().reverse().map(function(r){ return '<tr><td class="num">' + esc(r[0]) + '</td><td class="num">' + r[1] + '</td><td class="num">' + (r[2] || "") + '</td><td class="num">' + (r[3] == null ? "" : r[3]) + "</td></tr>"; }).join("") + "</tbody></table></section>";
        var T = c.transfers || [];
        if (T.length) html += '<section class="blk"><h2>آخر انتقالاته</h2><ul class="mlist">' + T.slice(0, 30).map(function(t){ var inb = t[5] === +id; return '<li><span class="num">' + esc(t[0]) + "</span> " + (t[1] ? '<a href="' + playerUrl(t[1]) + '">' + esc(t[2] || "") + "</a>" : esc(t[2] || "")) + ' <span class="muted small">' + (inb ? "جاه من " + esc(t[4] || "") : "راح إلى " + esc(t[6] || "")) + (t[8] ? " · " + esc(t[8]) : "") + "</span></li>"; }).join("") + "</ul></section>";
        html += '<p class="src">من FotMob. <a href="/db/">الموسوعة</a></p>';
        box.innerHTML = html;
        // 365Scores' titles (every competition from its first season) replace FotMob's list when they count more
        get("s365/fmmap.json").then(function(mp){ var sid = (mp.map || {})[id]; if (!sid) return;
          return get("s365/team/" + sid + ".json").then(function(t){ var T = t.titles || [], n365 = T.reduce(function(a, x){ return a + x[2].length; }, 0), nfm = tro.reduce(function(a, x){ return a + x.won; }, 0);
            if (n365 <= nfm) return;
            var sec = '<section class="blk" id="w365t"><h2>ألقابه <small>' + n365 + '</small></h2><ul class="chon">' + T.map(function(x){ return '<li><b><a href="' + leagueUrl(x[0]) + '">' + esc(x[1]) + '</a></b> <span class="num">' + x[2].length + '</span><span class="muted small yrs">' + esc(x[2].join("، ")) + "</span></li>"; }).join("") +
              '</ul><p class="src">الألقاب من 365Scores. <a href="' + teamUrl(sid) + '">صفحته هناك في الموسوعة</a></p></section>';
            var old = [].filter.call(box.querySelectorAll("section.blk"), function(x){ var h = x.querySelector("h2"); return h && /^ألقابه/.test(h.textContent); })[0];
            if (old) old.outerHTML = sec; else box.insertAdjacentHTML("afterbegin", sec); }); }).catch(function(){});
        get("history/club/" + id + ".json").then(function(h){ box.insertAdjacentHTML("beforeend", '<section class="blk"><h2>تاريخه</h2><p>من <b class="num">' + h.since.slice(0, 4) + "</b>: " + h.total.p + " مباراة، " + h.total.w + " فوز، " + h.total.d + " تعادل، " + h.total.l + ' خسارة.</p><p class="src">النتايج من قاعدة schochastics/football-data.</p></section>'); }).catch(function(){});
      }).catch(function(){ box.innerHTML = '<p class="empty">ما لقينا هالنادي في الموسوعة. <a href="/db/">دوّر من جديد</a></p>'; });
    });
    return;
  }

  // ---------------------------------------------------------------- a match (any match since 2010: v1/matchx/<id>.json, db/matches.py)
  if (kind === "match"){
    has("/m/" + id + "/").then(function(live){ if (live){ location.replace("/m/" + id + "/"); return; }
      get("matchx/" + id + ".json").then(function(m){
        var N = m.names || {}, hn = N.home || m.home[1], an = N.away || m.away[1];
        title(hn + " " + m.home[2] + " - " + m.away[2] + " " + an);
        var dt = m.date ? new Date(m.date) : null;
        var html = '<div class="wmh"><a href="' + clubUrl(m.home[0]) + '">' + esc(hn) + '</a><bdi dir="rtl" class="num wsc">' + m.home[2] + " - " + m.away[2] + '</bdi><a href="' + clubUrl(m.away[0]) + '">' + esc(an) + "</a></div>" +
          '<p class="season">' + [N.comp && esc(N.comp) + (m.round ? " · الجولة " + esc(m.round) : ""), dt && dt.toLocaleDateString("ar-AE-u-nu-latn", { year:"numeric", month:"long", day:"numeric" }), m.stadium && m.stadium[0] && (/^(ملعب|استاد|ستاد)/.test(m.stadium[0]) ? "" : "ملعب ") + esc(m.stadium[0]),
            m.referee && "الحكم " + esc(m.referee), m.attendance && Number(m.attendance).toLocaleString("en") + " متفرج"].filter(Boolean).join(" · ") + "</p>";
        var EV = { g:"هدف", y:"إنذار", r:"طرد", s:"تبديل" };
        if ((m.events || []).length) html += '<section class="blk"><h2>أحداث المباراة</h2><ul class="mlist wev">' + m.events.map(function(e){
          var who = e[3] ? '<a href="' + playerUrl(e[3]) + '">' + esc(e[4] || "") + "</a>" : esc(e[4] || "");
          var extra = e[1] === "g" ? (e[6] === "pen" ? " (جزاء)" : e[6] === "own" ? " (عكسي)" : "") + (e[5] ? " · صناعة " + '<a href="' + playerUrl(e[5]) + '">←</a>' : "") : e[1] === "s" ? " بدال " + esc(e[6] || "") : "";
          return '<li class="' + e[2] + '"><span class="num">' + e[0] + '′</span> <span class="ev ' + e[1] + '">' + (EV[e[1]] || "") + "</span> " + who + extra + ' <span class="muted small">' + esc(e[2] === "h" ? hn : an) + "</span></li>"; }).join("") + "</ul></section>";
        var L = m.lineups || {};
        if (L.h || L.a) html += '<section class="blk"><h2>التشكيلة</h2><div class="hbig">' + ["h", "a"].map(function(s){ var t = L[s]; if (!t) return "<div></div>";
          return "<div><h3>" + esc(s === "h" ? hn : an) + (t.formation ? ' <span class="muted small num">' + esc(t.formation) + "</span>" : "") + '</h3><ol class="mlist wlu">' + t.players.map(function(p){
            return "<li" + (p[4] ? "" : ' class="sub"') + ">" + (p[2] ? '<span class="num muted">' + esc(p[2]) + "</span> " : "") + '<a href="' + playerUrl(p[0]) + '">' + esc(p[1] || "") + "</a>" + (p[5] ? ' <span class="num rt">' + Number(p[5]).toFixed(1) + "</span>" : "") + "</li>"; }).join("") + "</ol></div>"; }).join("") + "</div></section>";
        var P = m.ps || {}, ids = Object.keys(P);
        if (ids.length){
          var nm = {}; ["h", "a"].forEach(function(s){ ((L[s] || {}).players || []).forEach(function(p){ nm[p[0]] = p[1]; }); });
          var pr = function(v){ return Array.isArray(v) ? v[0] + "/" + v[1] : v == null ? "" : v; };
          ids.sort(function(a, b){ return (P[b].r || 0) - (P[a].r || 0); });
          html += '<section class="blk"><h2>أرقام كل لاعب</h2><div class="tscroll"><table class="tbl"><thead><tr><th>اللاعب</th><th>دقايق</th><th>التقييم</th><th>أهداف</th><th>صناعة</th><th>تسديدات</th><th>لمسات</th><th>تمريرات صحيحة</th><th>فرص</th><th>مراوغات</th><th>افتكاك</th><th>التحامات</th></tr></thead><tbody>' +
            ids.map(function(k){ var x = P[k]; return '<tr><td><a href="' + playerUrl(k) + '">' + esc(nm[k] || nm[+k] || k) + '</a></td><td class="num">' + pr(x.min) + '</td><td class="num">' + (x.r ? Number(x.r).toFixed(1) : "") + '</td><td class="num">' + pr(x.g) + '</td><td class="num">' + pr(x.a) + '</td><td class="num">' + pr(x.sh) + '</td><td class="num">' + pr(x.tch) + '</td><td class="num">' + pr(x.pas) + '</td><td class="num">' + pr(x.kp) + '</td><td class="num">' + pr(x.dr) + '</td><td class="num">' + pr(x.tk) + '</td><td class="num">' + pr(x.dw) + "</td></tr>"; }).join("") +
            "</tbody></table></div></section>";
        }
        html += '<p class="src">من FotMob. <a href="/db/">الموسوعة</a></p>';
        box.innerHTML = html;
      }).catch(function(){ box.innerHTML = '<p class="empty">ما لقينا تفاصيل هالمباراة. <a href="/db/">الموسوعة</a></p>'; });
    });
    return;
  }

  // ---------------------------------------------------------------- a player
  if (kind === "player"){
    has("/p/" + id + "/").then(function(live){ if (live){ location.replace("/p/" + id + "/"); return; }
      get("player/" + id + "/profile.json").then(function(d){
        var b = d.bio || {}, nm = b.name || ""; title(nm);
        var age = b.born ? Math.floor((Date.now() - Date.parse(b.born)) / 31557600000) : null;
        var rows = [b.pos && ["المركز", esc(b.pos)], b.born && ["العمر", age + " سنة (" + esc(b.born) + ")"], b.h && ["الطول", b.h + " سم"], b.foot && ["القدم", FOOT[b.foot] || esc(b.foot)],
          b.cc && ["الجنسية", esc(b.cc)], b.shirt && ["الرقم", b.shirt], b.mv && ["القيمة السوقية", eur(b.mv)], b.contract && ["نهاية العقد", esc(b.contract.slice(0, 7))]].filter(Boolean);
        var html = rows.length ? '<dl class="pbio">' + rows.map(function(r){ return "<div><dt>" + r[0] + "</dt><dd>" + r[1] + "</dd></div>"; }).join("") + "</dl>" : "";
        var C = d.career || {};
        [["senior", "مسيرته مع الأندية"], ["national team", "مع المنتخب"]].forEach(function(k){ var c = C[k[0]]; if (!c || !c.seasons || !c.seasons.length) return;
          html += '<section class="blk"><h2>' + k[1] + '</h2><table class="tbl"><thead><tr><th>الموسم</th><th>الفريق</th><th>مباريات</th><th>أهداف</th><th>صناعة</th></tr></thead><tbody>' + c.seasons.map(function(s){ return '<tr><td class="num">' + esc(s[0] || "") + '</td><td><a href="' + clubUrl(s[1]) + '">' + esc(s[2] || "") + '</a></td><td class="num">' + (s[3] || 0) + '</td><td class="num">' + (s[4] || 0) + '</td><td class="num">' + (s[5] || 0) + "</td></tr>"; }).join("") + "</tbody></table></section>"; });
        var tro = (d.trophies || []).filter(function(t){ return t[4].length; });
        if (tro.length) html += '<section class="blk"><h2>ألقابه</h2><ul class="chon">' + tro.map(function(t){ return "<li><b>" + esc(t[3] || "") + '</b> <span class="num">' + t[4].length + '</span><span class="muted small yrs">' + esc(t[1] || "") + " · " + esc(t[4].join("، ")) + "</span></li>"; }).join("") + "</ul></section>";
        html += '<p class="src">من FotMob. <a href="/db/">الموسوعة</a></p>';
        box.innerHTML = html;
        get("player/" + id + "/tm.json").then(function(t){ var h = R.tmSections(t); if (h){ var src = box.querySelector(".src"); if (src) src.insertAdjacentHTML("beforebegin", h); else box.insertAdjacentHTML("beforeend", h); } }).catch(function(){});
        get("ea/s/" + (+id % 100) + ".json").then(function(e){ var c = (e.cards || {})[id]; if (c){ var dl = box.querySelector(".pbio"); if (dl) dl.insertAdjacentHTML("afterend", R.eaCard(c)); else box.insertAdjacentHTML("afterbegin", R.eaCard(c)); } }).catch(function(){});
      }).catch(function(){ box.innerHTML = '<p class="empty">ما لقينا هاللاعب في الموسوعة. <a href="/db/">دوّر من جديد</a></p>'; });
    });
  }
})();
