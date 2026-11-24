// The archive job's pages (docs/superpowers/specs/2026-11-22-tifo-archive-static-design.md): every season of every competition
// as the current season shows (lib/season_view.cjs -> src/v5/pages.js P.comp), its seasons list, and every archive match page
// (lib/match_view.cjs -> P.match), from graph/archive_export.py's files, inside the site's own shell (state/site/shells.json).
//
//   node site/archive/build.cjs --data work/data --shell work/archive.html --index work/index.json --known work/known.json
//        --out work/out [--comps 47,87]
//
// known.json: {"m": [...], "p": [...], "t": [...]} the site's own pages (its sitemaps): a match, a man or a club with one links
// there; any other links to the archive's /m/k<id>/ (built here) or is left plain (a man or a club the archive has no page for yet).
"use strict";
const fs = require("fs"), path = require("path");
const U = require("../src/v5/ui.js"), P5 = require("../src/v5/pages.js"), SV = require("../lib/season_view.cjs"), MV = require("../lib/match_view.cjs"),
  HP = require("../lib/history_pages.cjs"), MA = require("../lib/match_archive.cjs"), PV = require("../lib/person_view.cjs"), EV = require("../lib/entity_view.cjs"),
  VV = require("../lib/versus_view.cjs");

const arg = (k, d) => { const i = process.argv.indexOf("--" + k); return i > 0 ? process.argv[i + 1] : d; };
const SITE = "https://tifo.elyoxe.com";
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const readJ = f => { try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch (e) { return null; } };
const bcLd = items => ({ "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: items.filter(x => x && x[0]).map((x, i) => Object.assign({ "@type": "ListItem", position: i + 1, name: x[0] }, x[1] ? { item: SITE + x[1] } : {})) });

// the match for the search engines and the language models: a finished SportsEvent with its teams, day, ground and score
function eventLd(m, c, pth) {
  const team = s => Object.assign({ "@type": "SportsTeam", name: s[1] }, s[0] ? { url: `${SITE}/t/${s[0]}/` } : {});
  return Object.assign({ "@type": "SportsEvent", name: `${m.h[1]} ${m.s[0]}-${m.s[1]} ${m.a[1]}`, startDate: m.date, sport: "Soccer",
    eventStatus: "https://schema.org/EventScheduled", url: SITE + pth, homeTeam: team(m.h), awayTeam: team(m.a),
    superEvent: { "@type": "SportsEvent", name: `${c.name_ar} ${m.season || ""}`.trim() } },
    m.venue ? { location: { "@type": "Place", name: m.venue } } : {});
}

// the shell carries the site's footer; a view's own (the site's page bodies end with one) would be a second (23 Nov 2026)
const noFoot = body => String(body).replace(/<footer class="foot">[\s\S]*?<\/footer>/g, "");

function shellPage(shell, o) {
  // the site's own page() output with placeholders (site/build.cjs writes _shells/archive.html): head, nav, footer, assets
  // a thin page (a result and no more) is for the visitor, not the search engines: noindex, and out of the sitemaps
  const s = o.noindex ? shell.replace("<head>", '<head><meta name="robots" content="noindex,follow">') : shell;
  return s.split("/__PATH__/").join(o.path).split("__TITLE__").join(esc(o.title)).split("__DESC__").join(esc(o.desc))
    .split("__BACKL__").join(o.nav.backLabel).split("__BACK__").join(o.nav.back).split("__NAVT__").join(o.nav.title)
    .split('{"__LD__":1}').join(JSON.stringify(o.ld || {}).replace(/</g, "\\u003c")).split("__BODY__").join(noFoot(o.body));
}

// the archive's competitions by where they are played: the world's and the continents' first, then every country by its name
const REGIONS = [["world", "العالم"], ["international", "بطولات دولية"], ["europe", "أوروبا"], ["asia", "آسيا"], ["africa", "أفريقيا"], ["americas", "الأمريكيتين"],
  ["oceania", "أوقيانوسيا"], ["arab", "العرب"], ["gulf", "الخليج"]];
const KINDS = { league: "دوري", cup: "كأس", supercup: "كأس سوبر", tournament: "بطولة", friendly: "وديات" };
function directory(cs) {
  const num = v => `<span class="num">${esc(v)}</span>`, by = new Map();
  for (const c of cs) { const g = c.country ? c.country.name_ar : (REGIONS.find(r => r[0] === c.scope) || REGIONS[1])[1]; if (!by.has(g)) by.set(g, []); by.get(g).push(c); }
  const reg = REGIONS.map(r => r[1]).filter(g => by.has(g)), rest = [...by.keys()].filter(g => !reg.includes(g)).sort((a, b) => a.localeCompare(b, "ar"));
  const row = c => { const r = c.cat || {}; return U.row({ href: `/c/${c.key}/`, t: esc(c.name_ar), sub: [KINDS[c.kind], r.seasons ? `${num(r.seasons)} موسم` : "",
    r.first ? (r.first === r.last ? num(r.first) : `${num(r.first)} - ${num(r.last)}`) : "", r.matches ? `${num(r.matches)} مباراة` : ""].filter(Boolean).join(" · ") }); };
  const grp = g => U.grp(`${esc(g)} ${num(by.get(g).length)}`, by.get(g).slice().sort((a, b) => ((a.cat || {}).tier || 9) - ((b.cat || {}).tier || 9) || ((b.cat || {}).matches || 0) - ((a.cat || {}).matches || 0)).map(row).join(""));
  return `<div class="lt"><h1>${esc("أرشيف البطولات")}</h1><p>${num(cs.length)} بطولة من كل العالم: مواسمها وأبطالها ومبارياتها. البطولات اللي نتابعها يوم بيوم في <a href="/competitions/">صفحة البطولات</a>.</p></div>` +
    reg.concat(rest).map(grp).join("");
}

function build(o) {
  const index = readJ(o.index) || { competitions: [] }, known = readJ(o.known) || {}, shell = fs.readFileSync(o.shell, "utf8");
  const KM = new Set((known.m || []).map(String)), KP = new Set((known.p || []).map(String)), KT = new Set((known.t || []).map(String));
  const PH = known.ph || {};                     // the archive men's photos (v1/ph/index.json, k<id> keys)
  // one page per man (23 Nov 2026): a FotMob man's encyclopedia facts (tools/archive_job.py fm_profiles) and FotMob's clubs' names
  const FMP = readJ(path.join(o.data, "fmp.json")) || {}, FMT = readJ(path.join(o.data, "fm_teams.json")) || {};
  const KR = new Set((known.r || []).map(String));
  // every referee of 5 games and every club FotMob has no page for (graph/archive_export referees, clubs): /r/k<id>/, /t/k<id>/
  const REFS = readJ(path.join(o.data, "referees.json")) || {}, CLUBS = readJ(path.join(o.data, "clubs.json")) || {};
  for (const [rid, r] of Object.entries(REFS)) if (r.fm && KR.has(String(r.fm))) delete REFS[rid];
  for (const [tid, c] of Object.entries(CLUBS)) if (c.fm && KT.has(String(c.fm))) delete CLUBS[tid];      // the site's /t/<FotMob id>/ is its page
  // one page per club (24 Nov 2026): a club with the encyclopedia's /db/club/<FotMob id>/ is shown there, its history with it
  // (_club_history.json -> v1/archive/club_history.json, read by the site build's lib/club_pages.cjs); no /t/k page of its own
  const KDB = new Set((known.dbclub || []).map(String)), HIST = {};
  for (const [tid, c] of Object.entries(CLUBS)) if (c.fm && KDB.has(String(c.fm))) { HIST[String(c.fm)] = c; delete CLUBS[tid]; }
  // every coach with a bench or an award (graph/archive_export.coaches): /coach/k<id>/, unless the site has his /coach/<FotMob id>/
  const COACHES = readJ(path.join(o.data, "coaches.json")) || {}, KC = new Set((known.coach || []).map(String));
  for (const c of Object.values(COACHES)) if (c.fm && KC.has(String(c.fm))) c.site = `/coach/${c.fm}/`;
  const coachHref = kid => { const c = kid != null && COACHES[String(kid)]; return c ? c.site || `/coach/k${kid}/` : null; };
  // every competition the site has no page for (24 Nov 2026: 1,568 of them, 1,143,246 matches): its seasons at /c/k<Tifo id>/,
  // from graph/archive_export's competitions.json; the site's own keep their key and their /c/<key>/seasons/
  const SITEC = new Set(index.competitions.map(c => +c.id));
  const ARCH = (readJ(path.join(o.data, "competitions.json")) || []).filter(r => !SITEC.has(+r.id)).map(r => ({ id: r.id, key: `k${r.cid}`, arch: 1,
    name_ar: r.name_ar || r.name, name_en: r.name, kind: r.kind || null, scope: r.scope || null, cat: r,
    country: r.country ? { iso2: r.country, name_ar: r.country_ar || r.country } : null }));
  const ALL = index.competitions.concat(ARCH);
  const comps = ALL.filter(c => !o.comps || o.comps.includes(+c.id));
  U.cfg.base = ""; U.cfg.pre = null; U.cfg.cn = {}; ALL.forEach((c, i) => { U.cfg.cn[c.id] = [c.key, c.name_ar, (c.country && c.country.iso2) || "", i]; });
  fs.mkdirSync(o.out, { recursive: true });
  fs.writeFileSync(path.join(o.out, "_club_history.json"), JSON.stringify(HIST));
  const written = new Set(), urls = [];        // urls: the indexable pages (the sitemaps)
  const FM2K = {}, FM2P = {};                               // FotMob id -> Tifo id of a match the site has no page for: its page is /m/k<id>/
  // every man with a record beyond a name gets /p/k<Tifo id>/ (graph/archive_export.persons), unless the site has his page
  const pdir = path.join(o.data, "people"), PERS = new Set();
  const shards = fs.existsSync(pdir) ? fs.readdirSync(pdir).filter(f => /^\d+\.json$/.test(f)) : [];
  for (const f of shards) for (const [pid, p] of Object.entries(readJ(path.join(pdir, f)) || {})) if (!(p.fm && KP.has(String(p.fm)))) PERS.add(pid);
  // a club whose page is the encyclopedia's is linked there: every renderer writes /t/<FotMob id>/, set right as the page is written
  const hasT = id => KT.has(String(id)) || KDB.has(String(id));
  const toDb = html => (KDB.size ? html.replace(/\/t\/(\d+)\/(?=["#?])/g, (m, id) => (!KT.has(id) && KDB.has(id) ? `/db/club/${id}/` : m)) : html);
  const write = (p, html) => { html = toDb(html); const f = path.join(o.out, p.replace(/^\//, ""), "index.html"); fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, html); written.add(p); };
  // a match links to the site's page when it has one, else to this archive's; a man or a club to the site's, else nothing yet
  const mHref = m => (KM.has(String(m.id)) ? `/m/${m.id}/` : `/m/k${m.k}/`);
  // what one pass over every match gives (graph/features_export.py, a full run only): two teams' every meeting at
  // /vs/<lo>-<hi>/ (the site's /h2h/<key>/ where it has the pair: one page per pair), a team's record at /vs/<tid>/, /elo/
  const vdir = path.join(o.data, "vs"), VX = (!o.comps && readJ(path.join(vdir, "index.json"))) || { pairs: {}, hubs: {} }, VN = readJ(path.join(vdir, "names.json")) || {};
  const ELOL = (!o.comps && readJ(path.join(o.data, "elo", "leagues.json"))) || {}, KH = new Set((known.h2h || []).map(String));
  const vkey = t => (VN[t] && VN[t][1] ? String(VN[t][1]) : `k${t}`);
  const siteH2h = (x, y) => { const a = vkey(x), b = vkey(y); return KH.has(`${a}-${b}`) ? `/h2h/${a}-${b}/` : KH.has(`${b}-${a}`) ? `/h2h/${b}-${a}/` : null; };
  const pairHref = (x, y) => { if (x == null || y == null) return null; const lo = Math.min(x, y), hi = Math.max(x, y); return siteH2h(lo, hi) || (VX.pairs[`${lo}-${hi}`] ? `/vs/${lo}-${hi}/` : null); };
  const hubHref = t => (VX.hubs[t] ? `/vs/${t}/` : null);
  const teamHref = t => { const fm = VN[t] && VN[t][1]; return fm && hasT(fm) ? `/t/${fm}/` : CLUBS[String(t)] ? `/t/k${t}/` : null; };
  const relink = ms => ms.map(m => {
    const side = s => [s[0] && hasT(s[0]) ? s[0] : s[2] != null && CLUBS[String(s[2])] ? `k${s[2]}` : null, s[1], s[2]];
    const man = (id, pid) => (id && KP.has(String(id)) ? id : pid != null && PERS.has(String(pid)) ? `k${pid}` : null);
    return Object.assign({}, m, { id: KM.has(String(m.id)) ? m.id : `k${m.k}`, fm: /^\d+$/.test(String(m.id)) ? String(m.id) : null, h: side(m.h), a: side(m.a), rh: m.rk != null && REFS[String(m.rk)] ? `/r/k${m.rk}/` : null,
      chref: m.ck ? { h: coachHref(m.ck.h), a: coachHref(m.ck.a) } : null,
      ev: (m.ev || []).map(e => [e[0], e[1], e[2], e[3], e[4], man(e[5], e[6]), e[6]]),          // e[6]: the man's Tifo id (the season's leaders)
      lu: m.lu ? Object.fromEntries(Object.entries(m.lu).map(([k, v]) => [k, v.map(p => [p[0], man(p[1], p[4]), p[2], p[3]].concat(p[5] != null ? [p[5]] : []))])) : null });
  });
  const hpo = { team: hasT, player: id => KP.has(String(id)), person: pid => PERS.has(String(pid)), coach: kid => coachHref(kid), coachName: () => null,
    teamName: () => null, playerName: () => null };
  let nSeasons = 0, nMatches = 0;
  const DIR = "/c/archive/", DIRT = "أرشيف البطولات", ARCHW = [];
  for (const c of comps) {
    const ed0 = readJ(path.join(o.data, "editions", `${c.id}.json`)), mdir = path.join(o.data, "matches", String(c.id));
    const MSEA = new Map();
    if (fs.existsSync(mdir)) for (const f of fs.readdirSync(mdir)) { const d = readJ(path.join(mdir, f)); if (d && d.matches) MSEA.set(`${c.id}|${f.replace(/\.json$/, "")}`, relink(d.matches)); }
    if (!ed0 && !MSEA.size) continue;
    const ed = Object.assign({}, ed0 || { seasons: [] }, { seasons: SV.seasons(ed0 || { seasons: [] }, MSEA, c.id) });
    // the two clubs' meetings in this competition (lib/match_view.cjs pairs/h2h), keyed by the site's club id, else k<Tifo id>
    const tkey = s => (s[0] ? String(s[0]) : `k${s[2]}`);
    const PAIRS = MV.pairs([...MSEA.values()].map(ms => ms.map(m => Object.assign({}, m, { h: [tkey(m.h), m.h[1]], a: [tkey(m.a), m.a[1]] }))), () => c.name_ar);
    const ss = ed.seasons, arch = c.arch ? `/c/${c.key}/` : `/c/${c.key}/seasons/`, msOf = s => MSEA.get(`${c.id}|${HP.slug(s.season)}`) || [];
    const sNav = (title, back, label) => ({ back, backLabel: label, title });
    const AT = MSEA.size >= 3 ? SV.alltime([...MSEA.values()]) : [], atp = `${arch}alltime/`;
    const bare = !ss.some(s => s.champion || (s.parts || []).some(p => p.champion));      // qualifiers, friendlies: seasons of games and no champion
    const up = c.arch ? [DIRT, DIR] : [c.name_ar, `/c/${c.key}/`];        // above the seasons list: the competition's page, else the directory
    write(arch, shellPage(shell, { path: arch, nav: sNav(c.arch ? esc(c.name_ar) : "كل المواسم", up[1], esc(up[0])),
      title: bare ? `${c.name_ar}: كل المواسم والمباريات | تيفو` : `أبطال ${c.name_ar} عبر التاريخ: كل المواسم والهدافين | تيفو`,
      desc: bare ? `كل مواسم ${c.name_ar} ومبارياتها: ${ss.length} موسم.` : `كل مواسم ${c.name_ar}: البطل والوصيف والهداف في ${ss.length} موسم.`,
      body: `<div class="lt"><h1>${esc(c.name_ar)}: كل المواسم</h1>${ss.length ? `<p>${bare ? "المباريات" : "البطل والوصيف والهداف"} في كل موسم، من <span class="num">${esc(ss[ss.length - 1].season)}</span> لين <span class="num">${esc(ss[0].season)}</span>.</p>` : ""}${AT.length >= 4 || ELOL[c.id] ? `<p>${AT.length >= 4 ? `<a class="chip" href="${atp}">الترتيب التاريخي</a>` : ""}${ELOL[c.id] ? `<a class="chip" href="/elo/${c.key}/">تصنيف الأندية</a>` : ""}</p>` : ""}</div>` + HP.seasonsBody(ed, c, Object.assign({ page: s => HP.seasonRich(s) || msOf(s).length, bare, count: s => msOf(s).length }, hpo)),
      ld: bcLd(c.arch ? [up, [c.name_ar, arch]] : [up, ["كل المواسم", arch]]) }));
    urls.push(arch);
    if (c.arch) ARCHW.push(c);
    if (AT.length >= 4) {                                   // the all-time table, under the seasons list (a path the archive owns)
      write(atp, shellPage(shell, { path: atp, nav: sNav("الترتيب التاريخي", arch, "كل المواسم"),
        title: `الترتيب التاريخي لـ${c.name_ar}: كل الفرق عبر كل المواسم | تيفو`,
        desc: `الترتيب التاريخي لـ${c.name_ar}: ${AT.length} فريق، مباريات كل فريق وانتصاراته وأهدافه في ${MSEA.size} موسم من أرشيف تيفو.`,
        body: `<div class="lt"><h1>الترتيب التاريخي: ${esc(c.name_ar)}</h1><p>كل مباراة في أرشيف تيفو من <span class="num">${MSEA.size}</span> موسم، و<span class="num">3</span> نقاط للفوز في كل الأزمنة عشان تنقاس المواسم بمقياس واحد.</p></div>` +
          U.table(AT, { full: 1 }) + '<p class="src">محسوب من نتايج المباريات في قاعدة تيفو؛ المواسم اللي ما وصلتنا مبارياتها مب داخلة.</p>',
        ld: bcLd(c.arch ? [up, [c.name_ar, arch], ["الترتيب التاريخي", atp]] : [up, ["كل المواسم", arch], ["الترتيب التاريخي", atp]]) }));
      urls.push(atp);
    }
    for (const s of ss.filter(s => HP.seasonRich(s) || msOf(s).length)) {
      const sp = `/c/${c.key}/s/${HP.slug(s.season)}/`, ms = msOf(s), nb = SV.around(ss, s.season);
      const sLink = (x, t) => `<a class="chip" href="/c/${c.key}/s/${HP.slug(x)}/">${t} <span class="num">${esc(x)}</span></a>`;
      const cd = SV.cards(ms), segs = [["y", "الإنذارات", cd.yellow], ["r", "الطرد", cd.red]].filter(z => z[2].length).map(z => [z[0], z[1], U.leaders(z[2], 10)]);
      const v5s = P5.comp(Object.assign({}, c, { season: s.season, dormant: false }), { st: SV.standings(s, ms), fx: SV.fixtures(ms, c.arch ? MA.indexable : null), stats: SV.stats(s, ms), archive: 1, x: { leadSegs: segs,
        crumbs: c.arch ? `<a href="${arch}">${esc(c.name_ar)}: كل المواسم</a>` : `<a href="/c/${c.key}/">${esc(c.name_ar)}</a>، <a href="${arch}">كل المواسم</a>`,
        chips: [nb.older && sLink(nb.older, "الموسم اللي قبله"), nb.newer && (nb.newer === c.season ? `<a class="chip" href="/c/${c.key}/">الموسم الحالي</a>` : sLink(nb.newer, "اللي بعده")),
          `<a class="chip" href="${arch}">كل المواسم</a>`].filter(Boolean).join(""),
        note: (s.note ? `<p class="note mt">${esc(s.note)}</p>` : "") + (s.table_from_matches ? '<p class="note mt">الترتيب محسوب من نتايج مباريات الموسم، بنظام النقاط في زمانه.</p>' : ""),
        table: "", fx: "", num: "", hist: HP.seasonBody(Object.assign({}, s, { table: [], top_scorers: [] }), c, hpo) } });
      const chN = s.champion && s.champion.name;
      const okS = !!((s.table || []).length || (s.top_scorers || []).length || ms.length);
      write(sp, shellPage(shell, { path: sp, nav: sNav(`موسم ${esc(s.season)}`, arch, "كل المواسم"), body: v5s.body, noindex: !okS,
        title: `${c.name_ar} ${s.season}: البطل والترتيب والهدافين | تيفو`, desc: `موسم ${s.season} من ${c.name_ar}${chN ? `: البطل ${chN}` : ""}، والترتيب النهائي والمباريات والهدافين.`,
        ld: bcLd(c.arch ? [[c.name_ar, arch], [s.season, sp]] : [[c.name_ar, `/c/${c.key}/`], ["كل المواسم", arch], [s.season, sp]]) }));
      if (okS) urls.push(sp);
      nSeasons++;
      for (const m of ms) {
        if (KM.has(String(m.id))) continue;                      // the site's own page
        if (c.arch && !MA.indexable(m)) continue;                // a result and no more: it is on its season's page, no page of its own
        const pth = `/m/${m.id}/`, md = MV.md(m), hk = tkey(m.h), ak = tkey(m.a);
        md.h2h = MV.h2h(PAIRS.get([hk, ak].sort().join("-")), Object.assign({}, md, { home: Object.assign({}, md.home, { id: hk }) }));
        const vs = pairHref(m.h[2], m.a[2]);
        const v5m = P5.match(md, { archive: 1, x: { lu: MV.lineups(m, md), h2h: null, share: "",
          ana: (vs ? `<p><a class="chip" href="${vs}">كل مواجهات الفريقين عبر التاريخ</a></p>` : "") + '<p class="src">من أرشيف تيفو: النتيجة والأحداث والتشكيلات من FotMob وTransfermarkt وRSSSF وقواعد بيانات الكورة المفتوحة، حسب ما يتوفر لكل مباراة.</p>' } });
        const okM = MA.indexable(m);
        write(pth, shellPage(shell, { path: pth, nav: sNav(`${esc(m.h[1])} - ${esc(m.a[1])}`, sp, `موسم ${esc(s.season)}`), body: v5m.body, noindex: !okM,
          title: MA.title(m, c), desc: `${m.h[1]} ${m.s[0]}-${m.s[1]} ${m.a[1]}، ${m.date}، ${c.name_ar} ${m.season || ""}: النتيجة والأهداف والتشكيلة من أرشيف تيفو.`,
          ld: { "@context": "https://schema.org", "@graph": [Object.assign(bcLd([[c.name_ar, `/c/${c.key}/`], [s.season, sp], [`${m.h[1]} - ${m.a[1]}`, pth]]), { "@context": undefined }),
            eventLd(m, c, pth)] } }));
        if (okM) urls.push(pth);
        if (m.fm) FM2K[m.fm] = m.k;                              // the site sends its links to this FotMob match here
        nMatches++;
      }
    }
  }
  // the men's profiles
  let nPersons = 0;
  const BYID = new Map(ALL.map(c => [+c.id, c]));
  const compOf = fid => { const c = BYID.get(+fid); return c ? { key: c.key } : null; };
  for (const f of shards) for (const [pid, p] of Object.entries(readJ(path.join(pdir, f)) || {})) {
    if (!PERS.has(pid)) continue;
    const pth = `/p/k${pid}/`, nm = PV.nameOf(p), ok = PV.indexable(p);
    write(pth, shellPage(shell, { path: pth, nav: { back: "/", backLabel: "تيفو", title: esc(nm) }, noindex: !ok, title: PV.title(p), desc: PV.desc(p),
      body: PV.body(p, { team: hasT, comp: compOf, photo: PH[`k${pid}`] ? Object.assign({ src: `/v1/ph/k${pid}.webp` }, PH[`k${pid}`]) : null,
        fm: p.fm ? FMP[p.fm] : null, teamName: id => FMT[id] }),
      ld: { "@context": "https://schema.org", "@graph": [Object.assign(PV.ld(p, pth), { "@context": undefined }), Object.assign(bcLd([[nm, pth]]), { "@context": undefined })] } }));
    if (ok) urls.push(pth);
    if (p.fm) FM2P[p.fm] = +pid;                       // the site sends its links to this FotMob man here, and the encyclopedia's page
    nPersons++;
  }
  // the referees' and the old clubs' pages
  const eo = { team: hasT, comp: compOf };
  for (const [rid, r] of Object.entries(REFS)) {
    const pth = `/r/k${rid}/`, nm = EV.nameOf(r), ok = EV.refIndexable(r);
    write(pth, shellPage(shell, { path: pth, nav: { back: "/", backLabel: "تيفو", title: esc(nm) }, noindex: !ok, title: `الحكم ${nm}: مبارياته وكروته | تيفو`,
      desc: `الحكم ${nm}: كل مبارياته في أرشيف تيفو موسم بموسم، والإنذارات والطرد.`, body: EV.referee(r, eo),
      ld: { "@context": "https://schema.org", "@graph": [{ "@type": "Person", name: nm, jobTitle: "Football referee", url: SITE + pth }, Object.assign(bcLd([[nm, pth]]), { "@context": undefined })] } }));
    if (ok) urls.push(pth);
  }
  for (const [tid, c] of Object.entries(CLUBS)) {
    const pth = `/t/k${tid}/`, nm = EV.nameOf(c), ok = EV.clubIndexable(c);
    write(pth, shellPage(shell, { path: pth, nav: { back: "/", backLabel: "تيفو", title: esc(nm) }, noindex: !ok, title: `${nm}: تاريخه ونتايجه موسم بموسم | تيفو`,
      desc: `${nm}: كل مواسمه في أرشيف تيفو، ألقابه ونتايجه ومبارياته.`,
      body: EV.club(c, eo) + (hubHref(tid) ? U.grp("", U.row({ href: hubHref(tid), t: "سجله ضد كل خصم", sub: "وأطول سلاسله وتصنيفه سنة بسنة" })) : ""),
      ld: { "@context": "https://schema.org", "@graph": [{ "@type": "SportsTeam", name: nm, sport: "Soccer", url: SITE + pth }, Object.assign(bcLd([[nm, pth]]), { "@context": undefined })] } }));
    if (ok) urls.push(pth);
  }
  // his own photo (c<id>), else the one of his playing days (k<his player id>)
  const coachPhoto = (kid, c) => (PH[`c${kid}`] ? Object.assign({ src: `/v1/ph/c${kid}.webp` }, PH[`c${kid}`])
    : c.pid != null && PH[`k${c.pid}`] ? Object.assign({ src: `/v1/ph/k${c.pid}.webp` }, PH[`k${c.pid}`]) : null);
  let nCoaches = 0;
  for (const [kid, c] of Object.entries(COACHES)) {
    const pth = `/coach/k${kid}/`, nm = EV.nameOf(c), ok = EV.coachIndexable(c);
    if (c.site) {      // the site has his page: this path points there (the site's own pages link every coach by /coach/k<id>/)
      write(pth, `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="robots" content="noindex,follow"><link rel="canonical" href="${SITE}${c.site}">` +
        `<meta http-equiv="refresh" content="0;url=${c.site}"><title>${esc(nm)}</title></head><body><a href="${c.site}">${esc(nm)}</a></body></html>`);
      continue;
    }
    write(pth, shellPage(shell, { path: pth, nav: { back: "/", backLabel: "تيفو", title: esc(nm) }, noindex: !ok, title: `المدرب ${nm}: مسيرته التدريبية | تيفو`,
      desc: `المدرب ${nm}: كل فرقه في أرشيف تيفو وسجله معها، وجوائزه وآخر مبارياته.`, body: EV.coach(c, Object.assign({}, eo, { person: pid => PERS.has(String(pid)), photo: coachPhoto(kid, c) })),
      ld: { "@context": "https://schema.org", "@graph": [Object.assign({ "@type": "Person", name: nm, jobTitle: "Football coach", url: SITE + pth }, c.b ? { birthDate: c.b } : {}),
        Object.assign(bcLd([[nm, pth]]), { "@context": undefined })] } }));
    if (ok) urls.push(pth);
    nCoaches++;
  }
  // every pair's meetings, every team's record, the ratings
  let nVs = 0;
  if (Object.keys(VX.pairs).length) {
    const compX = n => { const c = BYID.get(+n); return c ? { key: c.key, name: c.name_ar, season: s => { const p = `/c/${c.key}/s/${HP.slug(s)}/`; return written.has(p) ? p : null; } } : null; };
    const vo = { team: teamHref, hub: hubHref, pair: pairHref, comp: compX,
      match: m => (m[7] && KM.has(String(m[7])) ? `/m/${m[7]}/` : written.has(`/m/k${m[6]}/`) ? `/m/k${m[6]}/` : null) };
    const nmOf = t => (VN[t] && VN[t][0]) || `#${t}`, files = d => (fs.existsSync(d) ? fs.readdirSync(d).filter(f => /^\d+\.json$/.test(f)).map(f => path.join(d, f)) : []);
    for (const f of files(path.join(vdir, "pairs"))) for (const [k, ms] of Object.entries(readJ(f) || {})) {
      const [lo, hi] = k.split("-").map(Number);
      if (siteH2h(lo, hi)) continue;                           // the site's /h2h/<key>/ is this pair's page
      const pth = `/vs/${k}/`, ok = ms.length >= 3, hub = hubHref(lo);      // the owner, 24 Nov 2026: three meetings for the search engines
      write(pth, shellPage(shell, { path: pth, nav: { back: hub || "/", backLabel: hub ? esc(nmOf(lo)) : "تيفو", title: `${esc(nmOf(lo))} - ${esc(nmOf(hi))}` }, noindex: !ok,
        title: VV.pairTitle(lo, hi, VN), desc: VV.pairDesc(lo, hi, ms, VN), body: VV.pair(lo, hi, ms, VN, vo), ld: bcLd([[`${nmOf(lo)} ضد ${nmOf(hi)}`, pth]]) }));
      if (ok) urls.push(pth);
      nVs++;
    }
    for (const f of files(path.join(vdir, "teams"))) for (const [tid, d] of Object.entries(readJ(f) || {})) {
      const pth = `/vs/${tid}/`, nm = nmOf(tid), ok = d.tot[0] >= 100, th = teamHref(tid);
      write(pth, shellPage(shell, { path: pth, nav: { back: th || "/", backLabel: th ? esc(nm) : "تيفو", title: `سجل ${esc(nm)}` }, noindex: !ok,
        title: `سجل ${nm} التاريخي: ضد كل خصم وأطول السلاسل | تيفو`, desc: `${nm} في ${d.tot[0]} مباراة من ${d.first.slice(0, 4)}: سجله ضد كل خصم، أطول سلاسله، وتصنيفه سنة بسنة.`,
        body: VV.team(+tid, d, VN, vo), ld: bcLd(th ? [[nm, th], ["السجل التاريخي", pth]] : [[`سجل ${nm}`, pth]]) }));
      if (ok) urls.push(pth);
      nVs++;
    }
    const nat = readJ(path.join(o.data, "elo", "nations.json"));
    if (nat && nat.now.length) {
      const ls = Object.entries(ELOL).map(([n, rows]) => ({ c: BYID.get(+n), rows })).filter(x => x.c).sort((x, y) => String(x.c.name_ar).localeCompare(String(y.c.name_ar), "ar"));
      for (const { c, rows } of ls) {
        const pth = `/elo/${c.key}/`;
        write(pth, shellPage(shell, { path: pth, nav: { back: "/elo/", backLabel: "التصنيف", title: esc(c.name_ar) }, title: `تصنيف أندية ${c.name_ar}: أقوى الفرق حسب Elo | تيفو`,
          desc: `${rows.length} فريق من ${c.name_ar} مرتبين بتصنيف تيفو (Elo) المحسوب من كل نتايجهم، وأعلى تصنيف وصله كل فريق.`,
          body: VV.eloLeague({ key: c.key, name: c.name_ar }, rows, VN, vo), ld: bcLd([["تصنيف تيفو", "/elo/"], [c.name_ar, pth]]) }));
        urls.push(pth);
      }
      write("/elo/", shellPage(shell, { path: "/elo/", nav: { back: "/", backLabel: "تيفو", title: "تصنيف تيفو" }, title: "تصنيف تيفو للمنتخبات والأندية (Elo): الأقوى الحين وفي التاريخ | تيفو",
        desc: `${nat.now.length} منتخب مرتبين بقوتهم بتصنيف Elo المحسوب من كل مباراة في قاعدة تيفو، وأقوى المنتخبات في التاريخ، وتصنيف أندية ${ls.length} دوري.`,
        body: VV.eloHub(nat, ls.map(x => ({ key: x.c.key, name: x.c.name_ar, n: x.rows.length })), VN, vo), ld: bcLd([["تصنيف تيفو", "/elo/"]]) }));
      urls.push("/elo/");
    }
  }
  // the directory of the competitions whose only pages are the archive's, and the list the site build reads to link them
  // (_comps.json -> v1/archive/comps.json); a partial run knows some of them only and writes neither
  if (!o.comps && ARCHW.length) {
    write(DIR, shellPage(shell, { path: DIR, nav: { back: "/competitions/", backLabel: "البطولات", title: DIRT }, title: `${DIRT}: كل دوري وكأس وبطولة بمواسمها | تيفو`,
      desc: `${ARCHW.length} بطولة من كل العالم في أرشيف تيفو: مواسمها وأبطالها ومبارياتها.`, body: directory(ARCHW) + (written.has("/elo/") ? U.grp("", U.row({ href: "/elo/", t: "تصنيف تيفو للمنتخبات والأندية", sub: "Elo محسوب من كل مباراة في الأرشيف" })) : ""), ld: bcLd([["البطولات", "/competitions/"], [DIRT, DIR]]) }));
    urls.push(DIR);
    fs.writeFileSync(path.join(o.out, "_comps.json"), JSON.stringify({ n: ARCHW.length, keys: ARCHW.map(c => c.key), fm: Object.fromEntries(ARCHW.filter(c => +c.id < 2e9).map(c => [c.id, c.key])) }));
  }
  // links to pages neither the site nor this run has become plain text (the site build's own rule)
  const OWN = /^\/(m|p|t|c|coach|r|s|vs|elo)\//, SKIP = /^\/(v1|assets|logo|lg|og|api|embed|next)\//;
  let dead = 0;
  for (const p of written) {
    const f = path.join(o.out, p.replace(/^\//, ""), "index.html"), h = fs.readFileSync(f, "utf8");
    const h2 = h.replace(/(<script\b[\s\S]*?<\/script>)|<a\b([^>]*?)\shref="(\/[^"#?]*)(?:[?#][^"]*)?"([^>]*)>([\s\S]*?)<\/a>/g, (m0, sc, pre, href, post, inner) => {
      if (sc || SKIP.test(href) || !OWN.test(href) || written.has(href)) return m0;
      const seg = href.split("/"), kind = seg[1], id = seg[2] || "";
      if ((kind === "m" && KM.has(id)) || (kind === "p" && KP.has(id)) || (kind === "t" && KT.has(id)) || (kind === "c" && seg.length <= 4) || kind === "coach" || (kind === "r" && !/^k/.test(id)) || kind === "s") return m0;
      dead++; return `<span${pre}${post}>${inner}</span>`; });
    if (h2 !== h) fs.writeFileSync(f, h2);
  }
  fs.writeFileSync(path.join(o.out, "_archive_urls.json"), JSON.stringify(urls));
  fs.writeFileSync(path.join(o.out, "_fm2k.json"), JSON.stringify(FM2K));
  fs.writeFileSync(path.join(o.out, "_fm2p.json"), JSON.stringify(FM2P));
  return { seasons: nSeasons, matches: nMatches, persons: nPersons, coaches: nCoaches, versus: nVs, pages: written.size, dead };
}

if (require.main === module) {
  const out = build({ data: arg("data"), shell: arg("shell"), index: arg("index"), known: arg("known"), out: arg("out"),
    comps: arg("comps") ? arg("comps").split(",").map(Number) : null });
  console.log(JSON.stringify(out));
}
module.exports = { build, shellPage };
