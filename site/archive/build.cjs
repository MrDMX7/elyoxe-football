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
  HP = require("../lib/history_pages.cjs"), MA = require("../lib/match_archive.cjs");

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

function shellPage(shell, o) {
  // the site's own page() output with placeholders (site/build.cjs writes _shells/archive.html): head, nav, footer, assets
  // a thin page (a result and no more) is for the visitor, not the search engines: noindex, and out of the sitemaps
  const s = o.noindex ? shell.replace("<head>", '<head><meta name="robots" content="noindex,follow">') : shell;
  return s.split("/__PATH__/").join(o.path).split("__TITLE__").join(esc(o.title)).split("__DESC__").join(esc(o.desc))
    .split("__BACKL__").join(o.nav.backLabel).split("__BACK__").join(o.nav.back).split("__NAVT__").join(o.nav.title)
    .split('{"__LD__":1}').join(JSON.stringify(o.ld || {}).replace(/</g, "\\u003c")).split("__BODY__").join(o.body);
}

function build(o) {
  const index = readJ(o.index) || { competitions: [] }, known = readJ(o.known) || {}, shell = fs.readFileSync(o.shell, "utf8");
  const KM = new Set((known.m || []).map(String)), KP = new Set((known.p || []).map(String)), KT = new Set((known.t || []).map(String));
  const comps = index.competitions.filter(c => !o.comps || o.comps.includes(+c.id));
  U.cfg.base = ""; U.cfg.pre = null; U.cfg.cn = {}; index.competitions.forEach((c, i) => { U.cfg.cn[c.id] = [c.key, c.name_ar, (c.country && c.country.iso2) || "", i]; });
  const written = new Set(), urls = [];        // urls: the indexable pages (the sitemaps)
  const write = (p, html) => { const f = path.join(o.out, p.replace(/^\//, ""), "index.html"); fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, html); written.add(p); };
  // a match links to the site's page when it has one, else to this archive's; a man or a club to the site's, else nothing yet
  const mHref = m => (KM.has(String(m.id)) ? `/m/${m.id}/` : `/m/k${m.k}/`);
  const relink = ms => ms.map(m => {
    const side = s => [s[0] && KT.has(String(s[0])) ? s[0] : null, s[1], s[2]];
    const man = (id, pid) => (id && KP.has(String(id)) ? id : null);
    return Object.assign({}, m, { id: KM.has(String(m.id)) ? m.id : `k${m.k}`, h: side(m.h), a: side(m.a),
      ev: (m.ev || []).map(e => [e[0], e[1], e[2], e[3], e[4], man(e[5], e[6]), e[6]]),          // e[6]: the man's Tifo id (the season's leaders)
      lu: m.lu ? Object.fromEntries(Object.entries(m.lu).map(([k, v]) => [k, v.map(p => [p[0], man(p[1], p[4]), p[2], p[3]])])) : null });
  });
  const hpo = { team: id => KT.has(String(id)), player: id => KP.has(String(id)), person: () => false, coach: () => null, coachName: () => null,
    teamName: () => null, playerName: () => null };
  let nSeasons = 0, nMatches = 0;
  for (const c of comps) {
    const ed0 = readJ(path.join(o.data, "editions", `${c.id}.json`)), mdir = path.join(o.data, "matches", String(c.id));
    const MSEA = new Map();
    if (fs.existsSync(mdir)) for (const f of fs.readdirSync(mdir)) { const d = readJ(path.join(mdir, f)); if (d && d.matches) MSEA.set(`${c.id}|${f.replace(/\.json$/, "")}`, relink(d.matches)); }
    if (!ed0 && !MSEA.size) continue;
    const ed = Object.assign({}, ed0 || { seasons: [] }, { seasons: SV.seasons(ed0 || { seasons: [] }, MSEA, c.id) });
    // the two clubs' meetings in this competition (lib/match_view.cjs pairs/h2h), keyed by the site's club id, else k<Tifo id>
    const tkey = s => (s[0] ? String(s[0]) : `k${s[2]}`);
    const PAIRS = MV.pairs([...MSEA.values()].map(ms => ms.map(m => Object.assign({}, m, { h: [tkey(m.h), m.h[1]], a: [tkey(m.a), m.a[1]] }))), () => c.name_ar);
    const ss = ed.seasons, arch = `/c/${c.key}/seasons/`, msOf = s => MSEA.get(`${c.id}|${HP.slug(s.season)}`) || [];
    const sNav = (title, back, label) => ({ back, backLabel: label, title });
    write(arch, shellPage(shell, { path: arch, nav: sNav("كل المواسم", `/c/${c.key}/`, esc(c.name_ar)),
      title: `أبطال ${c.name_ar} عبر التاريخ: كل المواسم والهدافين | تيفو`, desc: `كل مواسم ${c.name_ar}: البطل والوصيف والهداف في ${ss.length} موسم.`,
      body: `<div class="lt"><h1>${esc(c.name_ar)}: كل المواسم</h1>${ss.length ? `<p>البطل والوصيف والهداف في كل موسم، من <span class="num">${esc(ss[ss.length - 1].season)}</span> لين <span class="num">${esc(ss[0].season)}</span>.</p>` : ""}</div>` + HP.seasonsBody(ed, c, Object.assign({ page: s => HP.seasonRich(s) || msOf(s).length }, hpo)) + U.foot(),
      ld: bcLd([[c.name_ar, `/c/${c.key}/`], ["كل المواسم", arch]]) }));
    urls.push(arch);
    for (const s of ss.filter(s => HP.seasonRich(s) || msOf(s).length)) {
      const sp = `/c/${c.key}/s/${HP.slug(s.season)}/`, ms = msOf(s), nb = SV.around(ss, s.season);
      const sLink = (x, t) => `<a class="chip" href="/c/${c.key}/s/${HP.slug(x)}/">${t} <span class="num">${esc(x)}</span></a>`;
      const cd = SV.cards(ms), segs = [["y", "الإنذارات", cd.yellow], ["r", "الطرد", cd.red]].filter(z => z[2].length).map(z => [z[0], z[1], U.leaders(z[2], 10)]);
      const v5s = P5.comp(Object.assign({}, c, { season: s.season, dormant: false }), { st: SV.standings(s, ms), fx: SV.fixtures(ms), stats: SV.stats(s, ms), archive: 1, x: { leadSegs: segs,
        crumbs: `<a href="/c/${c.key}/">${esc(c.name_ar)}</a>، <a href="${arch}">كل المواسم</a>`,
        chips: [nb.older && sLink(nb.older, "الموسم اللي قبله"), nb.newer && (nb.newer === c.season ? `<a class="chip" href="/c/${c.key}/">الموسم الحالي</a>` : sLink(nb.newer, "اللي بعده")),
          `<a class="chip" href="${arch}">كل المواسم</a>`].filter(Boolean).join(""),
        note: (s.note ? `<p class="note mt">${esc(s.note)}</p>` : "") + (s.table_from_matches ? '<p class="note mt">الترتيب محسوب من نتايج مباريات الموسم، بنظام النقاط في زمانه.</p>' : ""),
        table: "", fx: "", num: "", hist: HP.seasonBody(Object.assign({}, s, { table: [], top_scorers: [] }), c, hpo) } });
      const chN = s.champion && s.champion.name;
      const okS = !!((s.table || []).length || (s.top_scorers || []).length || ms.length);
      write(sp, shellPage(shell, { path: sp, nav: sNav(`موسم ${esc(s.season)}`, arch, "كل المواسم"), body: v5s.body, noindex: !okS,
        title: `${c.name_ar} ${s.season}: البطل والترتيب والهدافين | تيفو`, desc: `موسم ${s.season} من ${c.name_ar}${chN ? `: البطل ${chN}` : ""}، والترتيب النهائي والمباريات والهدافين.`,
        ld: bcLd([[c.name_ar, `/c/${c.key}/`], ["كل المواسم", arch], [s.season, sp]]) }));
      if (okS) urls.push(sp);
      nSeasons++;
      for (const m of ms) {
        if (KM.has(String(m.id))) continue;                      // the site's own page
        const pth = `/m/${m.id}/`, md = MV.md(m), hk = tkey(m.h), ak = tkey(m.a);
        md.h2h = MV.h2h(PAIRS.get([hk, ak].sort().join("-")), Object.assign({}, md, { home: Object.assign({}, md.home, { id: hk }) }));
        const v5m = P5.match(md, { archive: 1, x: { lu: MV.lineups(m, md), h2h: null, share: "",
          ana: '<p class="src">من أرشيف تيفو: النتيجة والأحداث والتشكيلات من FotMob وTransfermarkt وRSSSF وقواعد بيانات الكورة المفتوحة، حسب ما يتوفر لكل مباراة.</p>' } });
        const okM = MA.indexable(m);
        write(pth, shellPage(shell, { path: pth, nav: sNav(`${esc(m.h[1])} - ${esc(m.a[1])}`, sp, `موسم ${esc(s.season)}`), body: v5m.body, noindex: !okM,
          title: MA.title(m, c), desc: `${m.h[1]} ${m.s[0]}-${m.s[1]} ${m.a[1]}، ${m.date}، ${c.name_ar} ${m.season || ""}: النتيجة والأهداف والتشكيلة من أرشيف تيفو.`,
          ld: { "@context": "https://schema.org", "@graph": [Object.assign(bcLd([[c.name_ar, `/c/${c.key}/`], [s.season, sp], [`${m.h[1]} - ${m.a[1]}`, pth]]), { "@context": undefined }),
            eventLd(m, c, pth)] } }));
        if (okM) urls.push(pth);
        nMatches++;
      }
    }
  }
  // links to pages neither the site nor this run has become plain text (the site build's own rule)
  const OWN = /^\/(m|p|t|c|coach|r|s)\//, SKIP = /^\/(v1|assets|logo|lg|og|api|embed|next)\//;
  let dead = 0;
  for (const p of written) {
    const f = path.join(o.out, p.replace(/^\//, ""), "index.html"), h = fs.readFileSync(f, "utf8");
    const h2 = h.replace(/(<script\b[\s\S]*?<\/script>)|<a\b([^>]*?)\shref="(\/[^"#?]*)(?:[?#][^"]*)?"([^>]*)>([\s\S]*?)<\/a>/g, (m0, sc, pre, href, post, inner) => {
      if (sc || SKIP.test(href) || !OWN.test(href) || written.has(href)) return m0;
      const seg = href.split("/"), kind = seg[1], id = seg[2] || "";
      if ((kind === "m" && KM.has(id)) || (kind === "p" && KP.has(id)) || (kind === "t" && KT.has(id)) || (kind === "c" && seg.length <= 4) || kind === "coach" || kind === "r" || kind === "s") return m0;
      dead++; return `<span${pre}${post}>${inner}</span>`; });
    if (h2 !== h) fs.writeFileSync(f, h2);
  }
  fs.writeFileSync(path.join(o.out, "_archive_urls.json"), JSON.stringify(urls));
  return { seasons: nSeasons, matches: nMatches, pages: written.size, dead };
}

if (require.main === module) {
  const out = build({ data: arg("data"), shell: arg("shell"), index: arg("index"), known: arg("known"), out: arg("out"),
    comps: arg("comps") ? arg("comps").split(",").map(Number) : null });
  console.log(JSON.stringify(out));
}
module.exports = { build, shellPage };
