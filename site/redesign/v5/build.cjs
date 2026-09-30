/* تيفو v5 preview generator (site/redesign/v5/DESIGN.md).
   node site/redesign/v5/build.cjs [--fresh] [--snap <dir>]
   Reads the live data (https://tifo.elyoxe.com/v1/, cached in v5/cache/ for 30 min; --fresh refetches) and writes
   site/redesign/v5/out/** for s3://elyoxe-tifo-site-574771023173/next/. It reads production files (names/, the live
   site's hashed assets) and never writes them. Pages outside the prerendered set are rendered in the browser from the
   same data by src/app.js with the same src/ui.js + src/pages.js. */
"use strict";
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const U = require("./src/ui.js"), P = require("./src/pages.js");
const ROOT = __dirname, OUT = path.join(ROOT, "out"), CACHE = path.join(ROOT, "cache"), REPO = path.resolve(ROOT, "../../..");
const SITE = "https://tifo.elyoxe.com", BASE = "/next";
const args = process.argv.slice(2), FRESH = args.includes("--fresh"), TTL = FRESH ? 0 : 30 * 60e3, SNAP = (i => i >= 0 ? args[i + 1] : null)(args.indexOf("--snap"));
const esc = U.esc, cfg = U.cfg;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const hash = s => crypto.createHash("sha1").update(s).digest("hex").slice(0, 10);
const readJ = f => { try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch (e) { return null; } };
const save = (f, t) => { fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, t); };
let NREQ = 0;
async function getUrl(url, key, ttl) {
  const f = path.join(CACHE, key);
  try { const st = fs.statSync(f); if (Date.now() - st.mtimeMs < (ttl == null ? TTL : ttl)) { const t = fs.readFileSync(f, "utf8"); return t === "null" ? null : t; } } catch (e) {}
  for (let i = 0; i < 3; i++) {
    try { NREQ++; const r = await fetch(url, { signal: AbortSignal.timeout(40000) });
      if (r.status === 404 || r.status === 403) { save(f, "null"); return null; }
      if (!r.ok) throw new Error("HTTP " + r.status);
      const t = await r.text(); save(f, t); return t;
    } catch (e) { if (i === 2) { console.error("fetch failed", url, e.message); return null; } await sleep(1200 * (i + 1)); }
  }
}
async function get(p, ttl) { const t = await getUrl(SITE + "/v1/" + p, "v1/" + p.replace(/[?&=]/g, "_"), ttl); if (!t) return null; try { return JSON.parse(t); } catch (e) { return null; } }
async function pool(items, n, fn) { const out = new Array(items.length); let i = 0; await Promise.all(Array.from({ length: n }, async () => { while (i < items.length) { const k = i++; out[k] = await fn(items[k], k); } })); return out; }
const W = [];   // written paths
// the live build's text fixes (build.cjs write()): family names take «آل» («استاد آل نهيان»), never a raw null/undefined
const fixAl = t => t.replace(/(^|[\s«(>])ال (نهيان|مكتوم|قاسمي|نعيمي|معلا|شرقي|خليفة|ثاني|سعود|صباح)(?=$|[\s»),.،<])/g, "$1آل $2");
function write(rel, html) {
  html = html.replace(/(<body[\s\S]*)$/, b => b.replace(/(<script\b[\s\S]*?<\/script>)|>([^<>]+)(?=<)/g, (m, sc, t) => sc ? m : ">" + fixAl(t).replace(/\b(?:null|undefined|NaN)\b/g, "")));
  const f = path.join(OUT, rel); fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, html); W.push(rel); }

(async () => {
  const t0 = Date.now();
  fs.rmSync(OUT, { recursive: true, force: true }); fs.mkdirSync(OUT, { recursive: true });

  // ---------------------------------------------------------------- the live site's hashed assets (colours, channels, search index)
  const home0 = await getUrl(SITE + "/", "site-home.html", 10 * 60e3) || "";
  const AV = { colors: (/assets\/colors\.([0-9a-f]+)\.js/.exec(home0) || [])[1], search: (/data-v="([0-9a-f]+)"/.exec(home0) || [])[1], bc: (/data-bc="([0-9a-f]+)"/.exec(home0) || [])[1] };
  const colJs = AV.colors ? await getUrl(SITE + "/assets/colors." + AV.colors + ".js", "assets/colors." + AV.colors + ".js", 864e5 * 30) : "";
  const TC = (() => { const m = /window\.TC=(\{[\s\S]*?\});window\./.exec(colJs || ""); try { return m ? JSON.parse(m[1]) : {}; } catch (e) { return {}; } })();
  const ARABT = (() => { const m = /window\.ARABT=(\{[\s\S]*?\});window\./.exec(colJs || ""); try { return m ? JSON.parse(m[1]) : {}; } catch (e) { return {}; } })();
  const BCBY = AV.bc ? JSON.parse(await getUrl(SITE + "/assets/bc." + AV.bc + ".json", "assets/bc." + AV.bc + ".json", 864e5 * 30) || "{}") : {};
  console.log("live assets", AV, "colours", Object.keys(TC).length, "arab teams", Object.keys(ARABT).length);

  // ---------------------------------------------------------------- names (the same sources as the production build)
  const PNAR = readJ(path.join(REPO, "names/players_ar.json")) || {}, CLUB_AR = readJ(path.join(REPO, "names/clubs_ar.json")) || {}, COACH_AR = readJ(path.join(REPO, "names/coaches_ar.json")) || {}, REF_AR = readJ(path.join(REPO, "names/referees_ar.json")) || {};
  const FMN = Object.assign({ teams: {}, players: {}, comps: {}, countries: {} }, (await get("history/fm/names_ar.json", 864e5)) || {});
  const pnOf = id => (PNAR[id] && PNAR[id].ar) || FMN.players[id] || null;
  const TAR = {}; for (const [id, v] of Object.entries(CLUB_AR)) if (v && v.ar) TAR[id] = v.ar;
  const fillT = (o, k) => { if (!o || typeof o !== "object") return; if (Array.isArray(o)) { o.forEach(x => fillT(x, k)); return; } if ((k === "home" || k === "away" || k === "team" || k === "opponent") && o.id != null && !o.name_ar) { const a = TAR[o.id] || FMN.teams[o.id]; if (a) o.name_ar = a; } for (const kk in o) if (o[kk] && typeof o[kk] === "object") fillT(o[kk], kk); };
  const getT = async (p, ttl) => { const j = await get(p, ttl); fillT(j); return j; };
  cfg.cc = FMN.countries || {};
  cfg.tc = TC;

  // ---------------------------------------------------------------- index, days, competitions
  const index = await getT("index.json", 5 * 60e3); if (!index) throw new Error("no index.json");
  const comps = index.competitions;
  comps.forEach((c, i) => { cfg.cn[c.id] = [c.key, c.name_ar, (c.country && c.country.iso2) || "", i]; });
  const now = Date.now(), today = new Date(now + 4 * 36e5).toISOString().slice(0, 10), ymdN = d => d.replace(/-/g, "");
  const dayOff = k => new Date(Date.parse(today + "T00:00:00Z") + k * 864e5).toISOString().slice(0, 10);
  cfg.today = today; cfg.now = now;
  const days = {}; for (const k of [-1, 0, 1]) days[dayOff(k)] = (await getT("day/" + ymdN(dayOff(k)) + ".json", k === 0 ? 2 * 60e3 : 30 * 60e3)) || { matches: [] };
  const live = await getT("live.json", 60e3);
  // a live copy is fresher than the day file
  if (live && live.matches) { const L = {}; live.matches.forEach(m => { L[m.id] = m; }); for (const d of Object.values(days)) d.matches = (d.matches || []).map(m => L[m.id] ? Object.assign({}, m, L[m.id]) : m); }
  const CD = {};
  await pool(comps, 6, async c => { const [st, fx, stats] = await Promise.all([c.files && c.files.standings ? getT(`comp/${c.id}/standings.json`) : null, getT(`comp/${c.id}/fixtures.json`), getT(`comp/${c.id}/stats.json`)]); CD[c.id] = { c, st, fx, stats }; });
  const sim538 = await get("comp/538/sim.json");
  const S365 = (await get("s365/fm.json", 864e5)) || { comps: {}, teams: {}, titles: {} }, S365I = (await get("s365/index.json", 864e5)) || { comps: [], countries: {} };
  const SID2F = {}; for (const [f, s] of Object.entries(S365.teams || {})) SID2F[s] = +f;
  const CH = {}; await pool(comps, 8, async c => { const d = await get(`history/champions/${c.id}.json`, 864e5); if (d && d.champions && d.champions.length) CH[c.id] = d; });
  const teamsJson = (await getT("teams.json", 60 * 60e3)) || { teams: {} }, TEAMS = teamsJson.teams || {};
  for (const [id, t] of Object.entries(TEAMS)) if (t && !t.name_ar && (TAR[id] || FMN.teams[id])) t.name_ar = TAR[id] || FMN.teams[id];

  // ---------------------------------------------------------------- what gets a prerendered page
  const matchSum = new Map(); for (const { fx } of Object.values(CD)) (fx && fx.matches || []).forEach(m => { if (m.id) matchSum.set(m.id, m); });
  for (const d of Object.values(days)) (d.matches || []).forEach(m => { if (m.id) matchSum.set(m.id, Object.assign({}, matchSum.get(m.id) || {}, m)); });
  const MIDS = new Set();
  for (const d of Object.values(days)) (d.matches || []).forEach(m => m.id && MIDS.add(m.id));
  const rr = cid => { const fx = CD[cid] && CD[cid].fx; if (!fx || !fx.matches) return; const R = U.rounds(fx), i = R.order.indexOf(R.cur); [R.order[i - 1], R.cur, R.order[i + 1]].forEach(k => (R.by[k] || []).forEach(m => m.id && MIDS.add(m.id))); };
  [538, 11027, 329, 536, 525, 9469].forEach(rr);
  (CD[329] && CD[329].fx && CD[329].fx.matches || []).forEach(m => m.id && MIDS.add(m.id));
  const UAE = 5789, TIDS = new Set([UAE]);
  const stRows = cid => { const st = CD[cid] && CD[cid].st; return st && st.groups ? st.groups.flatMap(g => g.rows || []) : []; };
  [538, 11027, 329, 536].forEach(cid => stRows(cid).forEach(r => TIDS.add(r.team.id)));
  const NATJ = (await getT("arabs/national.json", 864e5)) || { teams: [] };
  (NATJ.teams || []).forEach(t => t.team && TIDS.add(+t.team));
  for (const d of Object.values(days)) (d.matches || []).forEach(m => { TIDS.add(m.home.id); TIDS.add(m.away.id); });
  // match details
  const MD = new Map(); await pool([...MIDS], 8, async id => { const m = await getT(`match/${id}.json`, 5 * 60e3); if (m) MD.set(id, m); });
  // teams (only those with a team file get a prerendered page; the rest render in the browser)
  const TD = new Map(); await pool([...TIDS], 8, async id => { const t = await getT(`team/${id}.json`); if (t && t.id) TD.set(id, t); });
  // a team file is a daily snapshot patched at kick-off and full time; the day files and fixtures are fresher, so their copy of a
  // match wins (status, score, minute), and a match still «live» three hours after kick-off is not shown as live
  for (const t of TD.values()) t.fixtures = (t.fixtures || []).map(m => { const s = m && matchSum.get(m.id); let x = s && s.status ? Object.assign({}, m, { status: s.status, status_detail: s.status_detail, score: s.score, penalties: s.penalties, minute: s.minute, period: s.period, period_start: s.period_start, period_base: s.period_base }) : m;
    if (x && U.isLive(x) && Date.now() - Date.parse(x.kickoff_utc) > 3 * 36e5) x = Object.assign({}, x, { status: x.score ? "finished" : "unknown", minute: null }); return x; });
  // players: the UAE squad, tonight's line-ups, the Pro League's top scorers and assisters
  const PIDS = new Set();
  ((TD.get(UAE) || {}).squad || []).forEach(g => (g.players || []).forEach(p => p.id && PIDS.add(p.id)));
  for (const d of Object.values(days)) (d.matches || []).filter(m => m.home.id === UAE || m.away.id === UAE || m.comp === 329).forEach(m => { const md = MD.get(m.id); if (md && md.lineups) ["home", "away"].forEach(s => md.lineups[s] && [].concat(md.lineups[s].starters || [], md.lineups[s].subs || []).forEach(p => p.id && PIDS.add(p.id))); });
  ["goals", "assists"].forEach(k => (((CD[538] || {}).stats || {}).lists || {})[k] && CD[538].stats.lists[k].slice(0, 12).forEach(r => r.player && r.player.id && PIDS.add(r.player.id)));
  [30981, 30893].forEach(id => PIDS.add(id));   // Messi and Ronaldo: search suggestions
  const PH = ((await get("ph/index.json", 864e5)) || {}).players || {};
  const EAC = ((await get("ea/cards.json", 864e5)) || {}).cards || {};
  const WIKI = (await get("history/wiki_ar.json", 864e5)) || { players: {}, clubs: {} };
  const TRH = (await get("history/transfers.json", 864e5)) || { players: {}, clubs: {} };
  const FMT = ((await get("history/fm/teams.json", 864e5)) || {}).teams || {};
  const CCARD = ((await get("history/clubs.json", 864e5)) || {}).clubs || {};
  const PD = new Map(); await pool([...PIDS], 8, async id => { const [prof, card, tm, log] = await Promise.all([get(`player/${id}/profile.json`, 864e5), get(`player/${id}.json`, 6 * 36e5), get(`player/${id}/tm.json`, 864e5), get(`player/${id}/log.json`, 864e5)]); if (prof || card) PD.set(id, { prof, card, tm, log }); });
  // league champion pages (365Scores): the competitions we cover that 365 maps, plus the Gulf Cup
  const LIDS = new Set([549, 5452]); for (const x of Object.values(S365.comps || {})) if (x && x.id) LIDS.add(x.id);
  const LD = new Map(); await pool([...LIDS], 8, async id => { const d = await get(`s365/comp/${id}.json`, 864e5); if (d && (d.champions || []).length) LD.set(id, d); });
  const news = await get("news/latest.json", 10 * 60e3);
  const worldI = await get("world/index.json", 864e5);
  console.log(`data: ${MD.size} matches, ${TD.size} teams, ${PD.size} players, ${LD.size} league pages, ${NREQ} requests`);

  // ---------------------------------------------------------------- snapshot: a real live state saved during a match (the live-page preview)
  let SNAPM = null;
  if (SNAP && fs.existsSync(SNAP)) { const fsn = fs.readdirSync(SNAP).filter(f => /^m6052086_\d+\.json$/.test(f)).sort(); const pick = fsn.map(f => [f, readJ(path.join(SNAP, f))]).filter(x => x[1] && x[1].status === "live").sort((a, b) => Math.abs(+a[1].minute - 80) - Math.abs(+b[1].minute - 80))[0];
    if (pick) { SNAPM = pick[1]; fillT(SNAPM); const hh = pick[0].match(/_(\d\d)(\d\d)(\d\d)\.json$/); SNAPM._at = hh ? new Date(Date.parse(today + "T" + hh[1] + ":" + hh[2] + ":" + hh[3] + "Z")).toISOString() : null; console.log("snapshot", pick[0], SNAPM.minute, SNAPM.score); } }

  // ---------------------------------------------------------------- prerender sets -> links
  cfg.pre.m = {}; for (const id of MD.keys()) cfg.pre.m[id] = 1;
  cfg.pre.t = {}; for (const id of TD.keys()) cfg.pre.t[id] = 1;
  cfg.pre.p = {}; for (const id of PD.keys()) cfg.pre.p[id] = 1;
  cfg.pre.c = {}; comps.forEach(c => { if (CD[c.id] && CD[c.id].fx) cfg.pre.c[c.key] = 1; });
  cfg.pre.l = {}; for (const id of LD.keys()) cfg.pre.l[id] = 1;
  cfg.ph = {}; for (const id of PIDS) if (PH[id]) cfg.ph[id] = 1;

  // ---------------------------------------------------------------- assets: CSS, one JS bundle, the shared config
  fs.mkdirSync(path.join(OUT, "assets"), { recursive: true });
  const css = fs.readFileSync(path.join(ROOT, "src/app.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\n\s*/g, "\n").replace(/\n+/g, "\n");
  const CSSV = hash(css); fs.writeFileSync(path.join(OUT, `assets/app.${CSSV}.css`), css);
  let js = ["ui.js", "pages.js", "app.js"].map(f => fs.readFileSync(path.join(ROOT, "src", f), "utf8")).join("\n;\n");
  // minified with a local esbuild when one is on the machine (ESBUILD=<module dir>); the unminified bundle works the same
  try { const eb = require(process.env.ESBUILD || "C:/Users/requi/workspace/studio/Remotion_Studio/node_modules/esbuild"); js = eb.transformSync(js, { minify: true, target: "es2017", charset: "utf8" }).code; } catch (e) { console.log("js not minified:", e.message.split("\n")[0]); }
  const JSV = hash(js); fs.writeFileSync(path.join(OUT, `assets/app.${JSV}.js`), js);
  const shared = { pre: cfg.pre, cn: cfg.cn, cc: cfg.cc, av: AV, ph: cfg.ph, arab: Object.keys(ARABT).map(Number) };
  const cfgJs = "window.V5C=" + JSON.stringify(shared) + ";"; const CFGV = hash(cfgJs); fs.writeFileSync(path.join(OUT, `assets/cfg.${CFGV}.js`), cfgJs);
  // team-name fills and per-club Arabic player names, for pages the browser renders (outside the prerendered set)
  const tnFill = {}; for (const [id, a] of Object.entries(FMN.teams || {})) tnFill[id] = a; Object.assign(tnFill, TAR);
  const metaJ = JSON.stringify({ tn: tnFill }); const METAV = hash(metaJ); fs.writeFileSync(path.join(OUT, `assets/meta.${METAV}.json`), metaJ);
  { const FMP = ((await get("history/fm/players.json", 864e5)) || {}).players || {}, byT = {};
    for (const [pid, b] of Object.entries(FMP)) { const a = pnOf(pid); if (a && b && b.team) (byT[b.team] = byT[b.team] || {})[pid] = a; }
    for (const t of TD.values()) (t.squad || []).forEach(g => (g.players || []).forEach(p => { const a = pnOf(p.id); if (a) (byT[t.id] = byT[t.id] || {})[p.id] = a; }));
    for (const [tid, m] of Object.entries(byT)) save(path.join(OUT, "n/t", tid + ".json"), JSON.stringify(m));
    console.log("name files", Object.keys(byT).length); }

  // ---------------------------------------------------------------- the document
  const colorsFor = ids => { const o = {}; ids.forEach(id => { if (id != null && TC[id]) o[id] = TC[id]; }); return o; };
  function doc(pg, o) {
    o = o || {};
    const page = Object.assign({ page: o.page, id: o.id || null, today, built: new Date().toISOString(), tc: o.tc || {}, pn: o.pn || {} }, o.extra || {});
    return `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>${esc(pg.title)}</title><meta name="robots" content="noindex,nofollow"><meta name="color-scheme" content="light dark"><meta name="theme-color" content="#F2F2F7" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-status-bar-style" content="default">
<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="apple-touch-icon" href="/icons/apple-touch-icon.png"><link rel="stylesheet" href="${BASE}/assets/app.${CSSV}.css"></head>
<body data-page="${o.page}"${o.id != null ? ` data-id="${esc(o.id)}"` : ""}${o.gen ? ` data-gen="${o.gen}"` : ""}${o.attrs || ""}>
<a class="skip" href="#main">تخطَّ للمحتوى</a>
${U.nav(pg.nav)}
<main id="main">${pg.body}</main>
${U.tabbar(pg.tab)}
${pg.sheets || ""}<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script>window.V5=${JSON.stringify(page).replace(/</g, "\\u003c")}</script><script src="${BASE}/assets/cfg.${CFGV}.js" defer></script><script src="${BASE}/assets/app.${JSV}.js" defer></script>
</body></html>`;
  }
  const namesFor = ids => { const o = {}; ids.forEach(id => { const a = pnOf(id); if (a) o[id] = a; }); return o; };
  const coachesInto = (o, ids) => ids.forEach(id => { if (id && COACH_AR[id] && COACH_AR[id].ar) o[id] = COACH_AR[id].ar; });
  const setPage = (pn, tc) => { cfg.pn = pn || {}; cfg.tc = Object.assign({}, TC); };

  // ---------------------------------------------------------------- home
  {
    const d = days[today], ms = d.matches || [];
    const arab = {}; ms.forEach(m => [m.home.id, m.away.id].forEach(id => { if (ARABT[id]) arab[id] = 1; }));
    setPage({});
    const pg = P.home({ matches: ms, ymd: today, arab });
    write("index.html", doc(pg, { page: "home", tc: colorsFor(ms.flatMap(m => [m.home.id, m.away.id])), extra: { day: ymdN(today), arab: ARABT_small(ms, ARABT) } }));
  }
  function ARABT_small(ms, A) { const o = {}; ms.forEach(m => [m.home.id, m.away.id].forEach(id => { if (A[id]) o[id] = 1; })); return o; }

  // ---------------------------------------------------------------- matches
  const refAr = r => r && r.id && REF_AR[r.id] && REF_AR[r.id].ar ? REF_AR[r.id].ar : null;
  const chFor = (cid, cc) => { const e = BCBY[cc || "AE"] && BCBY[cc || "AE"][cid]; if (!e || !e.b || !e.b.length) return ""; return e.b.slice(0, 4).map(x => `<div class="row"><span class="rt">${esc(x[0])}${x[5] ? `<small>${esc(x[5])}</small>` : ""}</span>${x[1] ? '<span class="chip" style="background:var(--accent-bg);color:var(--accent)">مجاني</span>' : ""}</div>`).join(""); };
  function matchPage(md, extra) {
    if (md.referee && refAr(md.referee)) md.referee = Object.assign({}, md.referee, { name: refAr(md.referee) });
    if (md.venue && !md.venue.name_ar && md.venue.name_en) md.venue = Object.assign({}, md.venue);
    const ids = []; ["home", "away"].forEach(s => { const L = md.lineups && md.lineups[s]; if (L) [].concat(L.starters || [], L.subs || [], L.unavailable || []).forEach(p => p && ids.push(p.id)); });
    (md.events || []).forEach(e => [e.player, e.assist, e.player_out].forEach(p => p && ids.push(p.id)));
    (md.firsts || []).forEach(f => f.player && ids.push(f.player));
    [md.home.id, md.away.id].forEach(tid => { const t = TD.get(tid); ((t && t.squad) || []).forEach(g => (g.players || []).forEach(p => ids.push(p.id))); });
    const pn = namesFor(ids); if (md.lineups) coachesInto(pn, ["home", "away"].map(s => md.lineups[s] && md.lineups[s].coach && md.lineups[s].coach.id));
    setPage(pn);
    const cd = CD[md.comp] || {};
    const sum = matchSum.get(md.id); if (sum && sum.probs && !md.probs) md.probs = sum.probs;
    const pg = P.match(md, { st: cd.st, ch: chFor(md.comp, "AE"), og: 0 });
    return { pg, pn };
  }
  for (const [id, md] of MD) {
    const { pg, pn } = matchPage(md);
    write(`m/${id}/index.html`, doc(pg, { page: "match", id, pn, tc: colorsFor([md.home.id, md.away.id]), extra: { live: U.isLive(md) || (md.status === "scheduled" && Date.parse(md.kickoff_utc) - now < 3 * 36e5 && Date.parse(md.kickoff_utc) - now > -3 * 36e5) ? 1 : 0, comp: md.comp, status: md.status } }));
  }
  if (SNAPM) {   // the live-state preview: a real snapshot saved during UAE v Qatar, frozen (no polling)
    cfg.now = Date.parse(SNAPM._at || SNAPM.period_start || now);
    const { pg, pn } = matchPage(SNAPM);
    pg.body = `<p class="pv">${U.icon("info", "", 2).replace('class=""', 'class="" style="width:20px;height:20px;flex:none;color:var(--accent)"')}<span><b>معاينة الحالة المباشرة:</b> لقطة حقيقية من مباراة الإمارات وقطر وهي مباشرة (30 سبتمبر). الصفحة نفسها تتحدّث كل 20 ثانية وقت أي مباراة مباشرة.</span></p>` + pg.body;
    write("m/live/index.html", doc(pg, { page: "match", id: SNAPM.id, pn, tc: colorsFor([SNAPM.home.id, SNAPM.away.id]), extra: { snap: 1, now: cfg.now, comp: SNAPM.comp } }));
    cfg.now = now;
  }

  // ---------------------------------------------------------------- competitions
  const champsFor = c => {
    const x = S365.comps && S365.comps[c.id], d = CH[c.id];
    if (x && (x.champions || []).filter(r => r[1]).length >= (d ? d.champions.length : 0)) {
      const rows = x.champions.filter(r => r[1]).map(r => [r[0], r[2] ? "f" + r[2] : "s" + r[4], r[1]]), nm = {}; rows.forEach(r => { nm[r[1]] = r[1][0] === "f" && TEAMS[r[1].slice(1)] ? (TEAMS[r[1].slice(1)].name_ar || r[2]) : r[2]; });
      return { rows, name: k => nm[k] || "", link: k => k[0] === "f" ? U.link("t", k.slice(1)) : "/db/team/?id=" + k.slice(1), l365: x.id, src: "من 365Scores." };
    }
    if (d) { const rows = d.champions.slice().reverse().map(r => [r[0], r[3] ? "f" + r[3] : "q" + r[1], r[2] || r[1]]), nm = {}; rows.forEach(r => { nm[r[1]] = r[1][0] === "f" && TEAMS[r[1].slice(1)] ? (TEAMS[r[1].slice(1)].name_ar || r[2]) : r[2]; }); return { rows, name: k => nm[k] || "", link: k => k[0] === "f" ? U.link("t", k.slice(1)) : "#", src: "من ويكي داتا.", l365: x && x.id }; }
    return null;
  };
  for (const c of comps) {
    const d = CD[c.id]; if (!d || !d.fx) continue;
    const pn = {}; const lists = (d.stats && d.stats.lists) || {}; ["goals", "assists"].forEach(k => (lists[k] || []).slice(0, 10).forEach(r => { const a = pnOf(r.player && r.player.id); if (a) pn[r.player.id] = a; }));
    setPage(pn);
    const pg = P.comp(c, { st: d.st, fx: d.fx, stats: d.stats, champs: champsFor(c), sim: c.id === 538 ? sim538 : null });
    write(`c/${c.key}/index.html`, doc(pg, { page: "comp", id: c.id, pn, extra: { comp: c.id } }));
  }

  // ---------------------------------------------------------------- teams
  const leagueRow = id => { for (const c of comps) { if (c.kind !== "league") continue; const st = CD[c.id] && CD[c.id].st; const g = st && !st.composite && st.groups && st.groups[0]; const r = g && g.rows.find(r => r.team.id === id); if (r) return { c, r, st }; } return null; };
  const T365 = S365.titles || {};
  const trophiesFor = id => {
    const fm = ((FMT[id] && FMT[id].trophies) || []).filter(t => t.won > 0).map(t => [/[\u0600-\u06FF]/.test(t.name || "") ? t.name : t.name, t.won, (t.seasons || []).slice()]);
    const s = (T365[id] || []).map(x => [x[1], x[2].length, x[2]]);
    const pickS = s.reduce((a, x) => a + x[1], 0) > fm.reduce((a, x) => a + x[1], 0);
    return { list: (pickS ? s : fm).sort((a, b) => b[1] - a[1]), src: pickS ? "الألقاب من 365Scores." : fm.length ? "الألقاب من FotMob." : "" };
  };
  const cardFor = id => { const c = CCARD[id], v = FMT[id] && FMT[id].venue; const rows = [];
    if (c && c.founded) rows.push({ t: "تأسس", v: '<span class="num">' + esc(c.founded) + "</span>" });
    const vn = (v && v.name) || (c && c.stadium && (c.stadium.ar || c.stadium.en)); if (vn) rows.push({ t: "الملعب", v: esc(vn) + ((v && v.capacity) ? ' · <span class="num">' + U.nf(v.capacity) + "</span>" : "") });
    if (c && c.city) rows.push({ t: "المدينة", v: esc(c.city) });
    if (c && c.nick && c.nick.length) rows.push({ t: "يلقبونه", v: esc(c.nick.slice(0, 2).join("، ")) });
    if (c && c.web) rows.push({ t: "موقعه الرسمي", href: c.web, ext: 1 });
    return rows.length ? rows : null; };
  const wikiOf = w => w && w[1] ? esc(w[1].length > 520 ? w[1].slice(0, w[1].lastIndexOf(" ", 510)) + "…" : w[1]) + ` <a href="https://ar.wikipedia.org/wiki/${encodeURIComponent(w[0].replace(/ /g, "_"))}" rel="noopener">ويكيبيديا</a>` : "";
  for (const [id, t] of TD) {
    const ids = []; (t.squad || []).forEach(g => (g.players || []).forEach(p => ids.push(p.id)));
    const pn = namesFor(ids); coachesInto(pn, [t.coach && t.coach.id]);
    // clubs of national-team players in Arabic
    const nat = !!t.national; if (nat) (t.squad || []).forEach(g => (g.players || []).forEach(p => { if (p.club_id && TEAMS[p.club_id] && TEAMS[p.club_id].name_ar) cfg.tn[p.club_id] = TEAMS[p.club_id].name_ar; }));
    setPage(pn);
    const row = leagueRow(id), tr = trophiesFor(id);
    // the live site writes a month report for clubs of the Arab leagues: the month of the latest result has one
    const ARABL = ["AE", "SA", "QA", "EG", "MA", "DZ", "TN", "IQ", "KW"], lastFin = U.teamFixtures(t).past[0];
    const month = row && ARABL.includes((row.c.country || {}).iso2) && lastFin ? U.ymd(lastFin.kickoff_uae || lastFin.kickoff_utc).slice(0, 7) : null;
    const pg = P.team(t, { row, st: row && row.st, month, trophies: tr.list.length ? tr.list : null, trophiesSrc: tr.src, card: cardFor(id), wiki: wikiOf(WIKI.clubs && WIKI.clubs[id]) });
    write(`t/${id}/index.html`, doc(pg, { page: "team", id, pn, tc: colorsFor([id].concat((t.fixtures || []).flatMap(m => [m.home.id, m.away.id]))) }));
  }
  cfg.tn = {};

  // ---------------------------------------------------------------- players
  for (const [id, d] of PD) {
    const b = (d.prof && d.prof.bio) || {}, card = d.card || {}, tid = b.team || card.team, team = tid ? Object.assign({ id: tid }, TEAMS[tid] || {}) : null;
    const pn = {}; const nm = pnOf(id); if (nm) pn[id] = nm;
    setPage(pn);
    // clubs named in the career, trophies and match log, in Arabic (the source files carry Latin names)
    const tids = new Set(); const C0 = (d.prof && d.prof.career) || {}; Object.values(C0).forEach(c => (c && c.seasons || []).forEach(s => s[1] && tids.add(s[1]))); ((d.prof && d.prof.trophies) || []).forEach(t => t[0] && tids.add(t[0])); Object.keys((d.log && d.log.teams) || {}).forEach(k => tids.add(k));
    (((TRH.players || {})[id]) || []).forEach(m => { if (m[3]) tids.add(m[3]); if (m[5]) tids.add(m[5]); });
    const tn = {}; tids.forEach(k => { const a = (TEAMS[k] && TEAMS[k].name_ar) || TAR[k] || FMN.teams[k]; if (a) tn[k] = a; }); cfg.tn = tn;
    if (d.log && d.log.teams) for (const k of Object.keys(d.log.teams)) if (tn[k]) d.log.teams[k] = tn[k];
    const ph = PH[id] ? { url: "/v1/ph/" + id + ".webp", who: (PH[id].artist || "").replace(/\s+/g, " ").trim().slice(0, 40), lic: PH[id].license || "", page: PH[id].page || "" } : null;
    const pg = P.player(id, { name: nm, latin: b.name || card.name || (d.log && d.log.name) || "", team, pos: b.pos || card.position, num: b.shirt || card.number, cc: b.cc || card.nationality, card: d.card ? { goals: card.goals, assists: card.assists, minutes: card.minutes, rating: card.rating } : null, prof: d.prof, tm: d.tm, log: d.log, ea: EAC[id] || null, photo: ph && ph.url, credit: ph ? `الصورة: <a href="${esc(ph.page)}" rel="noopener">${esc(ph.who)}${ph.lic ? " · " + esc(ph.lic) : ""}</a>` : "", wiki: wikiOf(WIKI.players && WIKI.players[id]), transfers: (TRH.players || {})[id] || null });
    write(`p/${id}/index.html`, doc(pg, { page: "player", id, pn, tc: colorsFor([tid]), extra: { tn: cfg.tn } }));
  }
  cfg.tn = {};

  // ---------------------------------------------------------------- the tabs: competitions, news, mine, more, search
  {
    setPage({});
    const nats = (NATJ.teams || []).map(t => ({ id: +t.team, name_ar: t.name_ar, name: t.name_en, sub: t.fifa && t.fifa.rank ? "تصنيف فيفا " + '<span class="num">' + t.fifa.rank + "</span>" : "" })).sort((a, b) => (a.id === UAE ? -1 : b.id === UAE ? 1 : 0));
    write("competitions/index.html", doc(P.comps(index, nats), { page: "comps" }));
    write("news/index.html", doc(P.news(news || { stories: [] }), { page: "news" }));
    const pop = [UAE].concat(nats.filter(t => t.id !== UAE).map(t => t.id), stRows(538).map(r => r.team.id), stRows(536).slice(0, 4).map(r => r.team.id), stRows(519).slice(0, 2).map(r => r.team.id), stRows(47).slice(0, 3).map(r => r.team.id), stRows(87).slice(0, 2).map(r => r.team.id));
    const popT = [...new Set(pop)].map(id => Object.assign({ id }, TEAMS[id] || {})).filter(t => t.name_ar || t.name);
    write("mine/index.html", doc(P.mine(popT), { page: "mine" }));
    write("more/index.html", doc(P.more(), { page: "more" }));
    const sugg = [["الإمارات", U.link("t", UAE)], ["دوري أدنوك", BASE + "/c/uae-pro-league/"], ["كأس الخليج", BASE + "/c/gulf-cup/"], ["العين", U.link("t", 102117)], ["الوصل", U.link("t", 102111)], ["الهلال", U.link("t", 2529)], ["الأهلي المصري", U.link("t", 101745)], ["ميسي", U.link("p", 30981)], ["رونالدو", U.link("p", 30893)]];
    write("search/index.html", doc(P.search(sugg), { page: "search" }));
  }

  // ---------------------------------------------------------------- the encyclopedia and league champion pages
  {
    setPage({});
    const CN = S365I.countries || {}, by = {};
    (S365I.comps || []).filter(c => c[5] > 0 && !c[11]).forEach(c => { (by[c[3]] = by[c[3]] || []).push(c); });
    const AR = [124, 122, 115, 131, 127, 139, 135, 114, 126, 119, 123, 125, 161, 130, 116, 117, 226, 170];
    const keys = Object.keys(by).map(Number).sort((a, b) => { const ia = AR.indexOf(a), ib = AR.indexOf(b); if (ia >= 0 || ib >= 0) return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib); return ((CN[a] || [""])[0] || "").localeCompare((CN[b] || [""])[0] || "", "ar"); });
    const byCountry = keys.map(cc => [(CN[cc] || [""])[0] || "دولية", by[cc].sort((a, b) => b[5] - a[5]).map(c => [c[0], c[1], c[6], c[7], c[5], c[8]])]);
    const nComps = (S365I.comps || []).length, nClubs = ((worldI && worldI.clubs) || []).length + ((S365I.teams || []).filter(t => !t[4]).length), nPlayers = ((worldI && worldI.n_players) || 0) + (S365I.players || []).length;
    write("db/index.html", doc(P.db({ nClubs, nPlayers, nComps, byCountry }), { page: "db" }));
    const logo365 = id => "https://imagecache.365scores.com/image/upload/f_png,w_128,h_128,c_limit,q_auto:eco,dpr_2,d_Competitions:default1.png/Competitions/" + id;
    const teamLink = t => SID2F[t] && TD.has(SID2F[t]) ? U.link("t", SID2F[t]) : SID2F[t] ? U.link("t", SID2F[t]) : "/db/team/?id=" + t;
    for (const [id, c] of LD) { const names = Object.assign({}, c.names || {}); for (const k of Object.keys(names)) { const f = SID2F[k]; if (f && TEAMS[f] && TEAMS[f].name_ar) names[k] = TEAMS[f].name_ar; } c.names = names;
      write(`db/league/${id}/index.html`, doc(P.league(c, { team: teamLink, logo: logo365(id) }), { page: "league", id })); }
  }

  // ---------------------------------------------------------------- generic shells: any id outside the prerendered set renders in the browser
  const shell = (page, title, back) => ({ title: title + " | تيفو", nav: { back: back || BASE + "/", backLabel: "رجوع", title: "" }, body: '<div class="card" style="margin-top:12px">' + U.empty("نحمّل…") + "</div>", tab: page === "match" ? "today" : "comps", sheets: "" });
  write("m/index.html", doc(shell("match", "مباراة"), { page: "match", gen: "match", extra: { meta: METAV } }));
  write("t/index.html", doc(shell("team", "فريق"), { page: "team", gen: "team", extra: { meta: METAV } }));
  write("p/index.html", doc(shell("player", "لاعب"), { page: "player", gen: "player", extra: { meta: METAV } }));
  write("c/index.html", doc(shell("comp", "بطولة"), { page: "comp", gen: "comp", extra: { meta: METAV } }));
  write("db/league/index.html", doc(shell("league", "بطولة", BASE + "/db/"), { page: "league", gen: "league", extra: { meta: METAV } }));
  write("404.html", doc({ title: "ما لقينا الصفحة | تيفو", nav: { back: BASE + "/", backLabel: "اليوم" }, body: '<div class="lt"><h1>ما لقينا الصفحة</h1></div><div class="card">' + U.row({ href: BASE + "/", t: "ارجع لليوم" }) + "</div>", tab: "", sheets: "" }, { page: "404" }));
  fs.writeFileSync(path.join(OUT, "robots.txt"), "User-agent: *\nDisallow: /\n");
  fs.writeFileSync(path.join(OUT, "build.json"), JSON.stringify({ built: new Date().toISOString(), today, pages: W.length, matches: MD.size, teams: TD.size, players: PD.size, leagues: LD.size, css: CSSV, js: JSV, snap: !!SNAPM }, null, 1));
  const gz = f => require("zlib").gzipSync(fs.readFileSync(f)).length;
  console.log(`wrote ${W.length} pages in ${((Date.now() - t0) / 1000).toFixed(1)} s; css ${gz(path.join(OUT, `assets/app.${CSSV}.css`))} B gz, js ${gz(path.join(OUT, `assets/app.${JSV}.js`))} B gz, cfg ${gz(path.join(OUT, `assets/cfg.${CFGV}.js`))} B gz`);
})().catch(e => { console.error(e); process.exit(1); });
