/* Build تيفو — static pages prerendered from the /v1 data (docs/SCHEMA.md) with src/render.js, then hydrated by src/app.js.
   node build.cjs [--data https://…cloudfront.net] [--out out] [--preview]
   -> out/index.html, out/c/<key>/, out/m/<id>/, out/t/<id>/, out/uae/, out/competitions/, out/logo/<id>.png, sitemap.xml
   --preview adds noindex (the *.cloudfront.net preview must not be indexed). Logos are cached in cache/logo/ and self-hosted
   (never hotlinked: visitor requests would carry our referer to FotMob). */
"use strict";
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const R = require("./src/render.js"), S = require("./src/stats.js");
const args = process.argv.slice(2), arg = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const DATA = (arg("--data", process.env.TIFO_DATA || "https://d1n5aqaqkowltp.cloudfront.net")).replace(/\/$/, "");
const OUT = path.resolve(__dirname, arg("--out", "out")), PREVIEW = args.includes("--preview");
const SITE = "https://tifo.elyoxe.com", CACHE = path.join(__dirname, "cache");
const esc = R.esc;

async function get(p, tries = 4){
  for (let i = 0; i < tries; i++){
    try { const r = await fetch(DATA + "/" + p, { signal:AbortSignal.timeout(25000) }); if (r.status === 404 || r.status === 403) return null; if (!r.ok) throw new Error(r.status + " " + p); return await r.json(); }
    catch (e){ if (i === tries - 1) { console.error("fetch failed", p, e.message); return null; } await new Promise(s => setTimeout(s, 1500 * (i + 1))); }
  }
}
async function pool(items, n, fn){ const out = new Array(items.length); let i = 0; await Promise.all(Array.from({ length:n }, async () => { while (i < items.length){ const k = i++; out[k] = await fn(items[k], k); } })); return out; }
function write(rel, html){ const f = path.join(OUT, rel); fs.mkdirSync(path.dirname(f), { recursive:true }); fs.writeFileSync(f, COLOR_V ? html.replace("__CV__", COLOR_V) : html); if (!COLOR_V) EARLY.push(f); ALLP.push(f); }
const ALLP = [], OGJ = [];   // share-preview jobs for og.py (169)   // every page: the search index version is known only at the end, patched in then
const EARLY = [];   // pages written before the club colours were known: patched once COLOR_V exists
const hash = s => crypto.createHash("sha1").update(s).digest("hex").slice(0, 10);

let ASSET_V = "", COLOR_V = "", SEARCH_V = "", BC_V = "";
function page(o){
  const url = SITE + o.path;
  return `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(o.title)}</title><meta name="description" content="${esc(o.desc)}">${PREVIEW ? '<meta name="robots" content="noindex">' : `<link rel="canonical" href="${url}">`}
<meta property="og:title" content="${esc(o.title)}"><meta property="og:description" content="${esc(o.desc)}"><meta property="og:url" content="${url}"><meta property="og:locale" content="ar_AE">${o.og ? `<meta property="og:image" content="${SITE}/og/${o.og}.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image">` : ""}<meta name="theme-color" content="#0A2620">
<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700&family=Noto+Kufi+Arabic:wght@800&family=Readex+Pro:wght@400;600&display=swap" rel="stylesheet" media="print" onload="this.media='all'"><noscript><link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700&family=Noto+Kufi+Arabic:wght@800&family=Readex+Pro:wght@400;600&display=swap" rel="stylesheet"></noscript>
<link rel="stylesheet" href="/assets/tifo.${ASSET_V}.css">${o.page === "match" ? '<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"}}</script>' : ""}${o.ld ? `<script type="application/ld+json">${JSON.stringify(o.ld).replace(/</g, "\\u003c")}</script>` : ""}</head>
<body data-page="${o.page}" data-bc="${BC_V}"${o.attrs || ""}>
<header class="bar"><div class="wrap"><a class="brand" href="/" aria-label="تيفو"><span class="mark" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span>تيفو</a><nav>
<a href="/"${o.nav === "home" ? " aria-current" : ""}>اليوم</a><a href="/c/uae-pro-league/"${o.nav === "538" ? " aria-current" : ""}>دوري أدنوك</a><a href="/uae/"${o.nav === "uae" ? " aria-current" : ""}>المنتخب</a><a href="/c/gulf-cup/"${o.nav === "329" ? " aria-current" : ""}>كأس الخليج</a><a href="/week/"${o.nav === "week" ? " aria-current" : ""}>الأسبوع</a><a href="/competitions/"${o.nav === "comps" ? " aria-current" : ""}>البطولات</a></nav><button type="button" class="spoil" id="srch" aria-label="بحث" data-v="__SV__">بحث</button><button type="button" class="spoil" id="ctry" title="بلدك: التوقيت وترتيب المباريات">بلدك</button><button type="button" class="spoil" id="spoil" aria-pressed="false" title="يخفي النتايج لين تضغط عليها">بدون حرق</button></div></header>
<main class="wrap">${o.body}</main>
<footer class="foot"><div class="wrap"><span>تيفو، من استوديو <a href="https://elyoxe.com/">Elyoxe</a>. المواعيد بتوقيت بلدك.</span><span><a href="/tv/">شاشة المجلس</a>، <a href="/studio/">ستوديو التيفو</a>، <a href="/week/">مباريات الأسبوع</a>، <a href="/legends/">الأساطير</a>، <a href="/memorable/">مباريات لا تُنسى</a>، <a href="/thisday/">هذا اليوم</a>، <a href="/laws/">قانون الكورة</a>، <a href="/watch/">وين تنقل</a>، <a href="/stadiums/">الملاعب</a>، <a href="/lab/">المختبر</a>، <a href="/academy/">الأكاديمية</a>، <a href="/glossary/">القاموس</a></span><span class="updated" id="updated"></span><span>البيانات من FotMob ورابطة المحترفين الإماراتية</span></div></footer>
<script src="/assets/colors.__CV__.js"></script><script src="/assets/render.${ASSET_V}.js"></script>${o.page === "home" ? `<script src="/assets/stand.${ASSET_V}.js"></script>` : ""}${o.page === "compare" ? `<script src="/assets/compare.${ASSET_V}.js"></script>` : ""}${o.page !== "tv" ? `<script src="/assets/share.${ASSET_V}.js"></script>` : ""}${o.page === "lab" ? `<script src="/assets/lab.${ASSET_V}.js"></script>` : ""}<script src="/assets/app.${ASSET_V}.js"></script></body></html>`;
}
const tabsHtml = (group, list) => `<div class="tabs" role="tablist" data-tabs="${group}">` + list.map((t, i) => `<button type="button" role="tab" data-t="${t[0]}" aria-selected="${i === 0}">${t[1]}</button>`).join("") + "</div>";
const pane = (group, key, html, first) => `<section data-group="${group}" data-pane="${key}"${first ? "" : " hidden"}>${html}</section>`;

(async () => {
  const t0 = Date.now();
  fs.rmSync(OUT, { recursive:true, force:true }); fs.mkdirSync(path.join(OUT, "assets"), { recursive:true });
  const css = fs.readFileSync(path.join(__dirname, "src/tifo.css"), "utf8"), rjs = fs.readFileSync(path.join(__dirname, "src/render.js"), "utf8"), ajs = fs.readFileSync(path.join(__dirname, "src/app.js"), "utf8"), sjs = fs.readFileSync(path.join(__dirname, "src/stand.js"), "utf8"), cmp = fs.readFileSync(path.join(__dirname, "src/compare.js"), "utf8"), shr = fs.readFileSync(path.join(__dirname, "src/share.js"), "utf8"), p3d = fs.readFileSync(path.join(__dirname, "src/pitch3d.js"), "utf8"), labjs = fs.readFileSync(path.join(__dirname, "src/lab.js"), "utf8");
  ASSET_V = hash(css + rjs + ajs + sjs + cmp + shr + p3d + labjs); fs.writeFileSync(path.join(OUT, `assets/lab.${ASSET_V}.js`), labjs); fs.writeFileSync(path.join(OUT, `assets/pitch3d.${ASSET_V}.js`), p3d); fs.writeFileSync(path.join(OUT, `assets/compare.${ASSET_V}.js`), cmp); fs.writeFileSync(path.join(OUT, `assets/share.${ASSET_V}.js`), shr);   // content-hashed file names: CloudFront's cache key ignores query strings
  fs.writeFileSync(path.join(OUT, `assets/tifo.${ASSET_V}.css`), css); fs.writeFileSync(path.join(OUT, `assets/render.${ASSET_V}.js`), rjs); fs.writeFileSync(path.join(OUT, `assets/app.${ASSET_V}.js`), ajs); fs.writeFileSync(path.join(OUT, `assets/stand.${ASSET_V}.js`), sjs);
  // the mark: a 3x3 tifo of cards (chalk, pulse, dune on night pitch)
  const cellsSvg = [["#F6F7F2","#10A04B","#B07A3B"],["#F6F7F2","#B07A3B","#10A04B"],["#10A04B","#B07A3B","#F6F7F2"]].map((row, y) => row.map((c, x) => `<rect x="${4 + x * 8.5}" y="${4 + y * 8.5}" width="7" height="7" fill="${c}"/>`).join("")).join("");
  fs.writeFileSync(path.join(OUT, "favicon.svg"), `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="#0A2620"/>${cellsSvg}</svg>`);

  const index = await get("index.json"); if (!index) throw new Error("no index.json from " + DATA);
  const comps = index.competitions, today = new Date(Date.now() + 4 * 3600e3).toISOString().slice(0, 10);
  const urls = ["/", "/uae/", "/competitions/"], teamIds = new Set(), matchSum = new Map();
  const teamsJson = await get("teams.json"); S.setTeams(teamsJson && teamsJson.teams || {});

  // ---- 1. fetch: competitions (+ every analytics file the pipeline may have written), today, national
  const EXTRA = ["sim", "watch", "bump", "halftime", "xg", "clutch", "cards", "foreigners", "improved", "young-uae", "team-of-round", "minute-clock", "goal-bands", "referees", "lineup-ages", "rotation", "pressure", "style", "fortress", "records", "alltime", "facts", "players", "similar", "tournament-sim", "scenarios", "shots", "fatigue", "coaches", "transfers", "records-book", "seasons", "milestones", "upsets", "projections", "bracket", "local-minutes"];
  // phase 5: generated content (ai/gen.py) is published only for kinds the owner approved (ai/approved.json)
  const APPROVED = JSON.parse(fs.readFileSync(path.join(__dirname, "ai/approved.json"), "utf8"));
  const AI = k => { const d = path.join(CACHE, "ai", k), o = {}; if (fs.existsSync(d)) for (const f of fs.readdirSync(d)) if (f.endsWith(".json")) o[f.slice(0, -5)] = JSON.parse(fs.readFileSync(path.join(d, f), "utf8")); return o; };
  const AIS = AI("summary"), AIP = AI("preview"), AIR = AI("round"), AIC = AI("podcast");
  const RSD = path.join(process.env.HOME, "workspace/research/tifo-2026-09-27"), readRes = f => { try { return JSON.parse(fs.readFileSync(path.join(RSD, f), "utf8")); } catch (e){ return {}; } };
  const CLUBS = {}; Object.values((readRes("arab_clubs.json").clubs) || {}).forEach(c => { if (c.fotmob_id) CLUBS[c.fotmob_id] = c; });
  const ATS = {}; Object.values((readRes("alltime_scorers.json").leagues) || {}).forEach(l => { if (l.fotmob_league_id) ATS[l.fotmob_league_id] = l; });
  // 204: where to watch per visitor country, compacted for the client: {ISO:{comp:[[name_ar, free, price, currency, url]], ...}}
  { const bbc = readRes("broadcast_by_country.json"), out = {}; for (const [iso, v] of Object.entries(bbc)){ if (iso === "_meta" || !v.competitions) continue; out[iso] = { _c:v.currency || "" }; for (const [k, c] of Object.entries(v.competitions)){ const key = /^dom_/.test(k) ? String(v.own_league_key) : k; out[iso][key] = { b:(c.broadcasters || []).map(x => [x.name_ar || x.name_en, x.free ? 1 : 0, x.price, x.currency, x.url]), q:c.confidence || "" }; } }
    const bj = JSON.stringify(out); BC_V = hash(bj); fs.writeFileSync(path.join(OUT, `assets/bc.${BC_V}.json`), bj); }
  const BC = readRes("broadcast.json"), HLT = readRes("highlights.json"), STAD = {}; ((readRes("stadiums.json").stadiums) || []).forEach(x => { STAD[x.id] = x; });
  const compData = await pool(comps, 3, async c => {
    const [st, fx, stats] = await Promise.all([c.files && c.files.standings ? get(`comp/${c.id}/standings.json`) : null, get(`comp/${c.id}/fixtures.json`), get(`comp/${c.id}/stats.json`)]);
    const x = {}; await pool(EXTRA, 3, async k => { x[k] = await get(`comp/${c.id}/${k}.json`, 2); });
    return { c, st, fx, stats, x };
  });
  const day = await get(`day/${today.replace(/-/g, "")}.json`) || { matches:[] };
  const [ratings, compare, fifa, qual, abroad, natRatings] = await Promise.all(["ratings/uae-clubs.json", "leagues/compare.json", "national/5789/fifa.json", "national/5789/qualifying.json", "national/uae-abroad.json", "ratings/national.json"].map(f => get(f, 1)));
  const h2hIdx = await get("h2h/index.json", 1), h2hKeys = h2hIdx ? Object.keys(h2hIdx.pairs) : [];
  const h2hData = await pool(h2hKeys, 8, k => get(`h2h/${k}.json`, 1)), H2H = {}; h2hKeys.forEach((k, i) => { if (h2hData[i]) H2H[k] = h2hData[i]; });
  let NAMES_AR = {}; try { NAMES_AR = JSON.parse(fs.readFileSync(path.join(__dirname, "../names/players_ar.json"), "utf8")); } catch (e){}
  const allPlayers = {}; compData.forEach(({ c, x }) => { if (x.players && x.players.players) for (const [pid, pp] of Object.entries(x.players.players)) allPlayers[pid] = Object.assign({ comp:c.id }, pp); if (x.cards && x.cards.players) for (const [id, c] of Object.entries(x.cards.players)) allPlayers[id] = Object.assign({ name:c.name, team:c.team }, allPlayers[id] || {}); });
  S.setPlayers(allPlayers);
  for (const { st, fx } of compData){
    (fx && fx.matches || []).forEach(m => { matchSum.set(m.id, m); [m.home, m.away].forEach(t => { if (t && t.id) teamIds.add(t.id); }); });
    (st && st.groups || []).forEach(g => g.rows.forEach(r => teamIds.add(r.team.id)));
  }
  (day.matches || []).forEach(m => { if (!matchSum.has(m.id)) matchSum.set(m.id, m); [m.home, m.away].forEach(t => { if (t && t.id) teamIds.add(t.id); }); });

  // ---- 2. logos (self-hosted copies) + club colours from them, before any page that paints colour
  fs.mkdirSync(path.join(CACHE, "logo"), { recursive:true }); fs.mkdirSync(path.join(OUT, "logo"), { recursive:true });
  const logoIds = new Set([...teamIds]); for (const m of matchSum.values()){ logoIds.add(m.home.id); logoIds.add(m.away.id); }
  let dl = 0;
  await pool([...logoIds], 8, async id => {
    const f = path.join(CACHE, "logo", id + ".png");
    if (!fs.existsSync(f)){ try { const r = await fetch(`https://images.fotmob.com/image_resources/logo/teamlogo/${id}.png`); if (r.ok){ fs.writeFileSync(f, Buffer.from(await r.arrayBuffer())); dl++; } } catch (e){} }
    if (fs.existsSync(f)) fs.copyFileSync(f, path.join(OUT, "logo", id + ".png"));
  });
  try { require("child_process").execFileSync("python3", [path.join(__dirname, "logo_colors.py")], { stdio:"ignore" }); } catch (e){ console.error("logo_colors.py failed; neutral colours"); }
  let colors = {}; try { colors = JSON.parse(fs.readFileSync(path.join(CACHE, "colors.json"), "utf8")); } catch (e){}
  R.setColors(colors); R.H2HK = {}; Object.keys(H2H).forEach(k => { R.H2HK[k] = 1; });
  const ARABC = new Set(R.COUNTRIES.map(c => c[0])), ARABT = {};
  compData.forEach(({ c, st, fx }) => { const iso = R.compCountry(c); if (!(ARABC.has(iso) || [329, 10242, 11156, 10474].includes(c.id))) return; (fx && fx.matches || []).forEach(m => { ARABT[m.home.id] = 1; ARABT[m.away.id] = 1; }); (st && st.groups || []).forEach(g => g.rows.forEach(r => { ARABT[r.team.id] = 1; })); });
  const cjs = "window.TC=" + JSON.stringify(colors) + ";window.H2HK=" + JSON.stringify(R.H2HK) + ";window.ARABT=" + JSON.stringify(ARABT) + ";"; COLOR_V = hash(cjs); fs.writeFileSync(path.join(OUT, `assets/colors.${COLOR_V}.js`), cjs);

  // ---- 3. competition pages
  const factsByMatch = {}, probsByMatch = {}, compX = {};
  for (const { c, st, fx, stats, x } of compData){
    compX[c.id] = x;
    if (x.facts && x.facts.matches) Object.assign(factsByMatch, x.facts.matches);
    let rounds = "";
    if (fx && fx.matches && fx.matches.length){ const rr = R.rounds(fx), cur = fx.next_round && rr.by[fx.next_round] ? fx.next_round : (rr.order.find(k => rr.by[k].some(m => m.status !== "finished")) || rr.order[rr.order.length - 1]); rounds = `<div class="chips">` + rr.order.map(k => `<button type="button" data-r="${esc(k)}"${k === cur ? ' aria-pressed="true"' : ""}>${esc(k)}</button>`).join("") + `</div><div id="roundlist">${R.roundList(rr.by[cur] || [])}</div>`; }
    const has = { table: !!(st && st.groups && st.groups.length), stats: !!(stats && stats.lists) };
    // table + its variants (140, 51, 50) + season journey (114)
    const vars = has.table && !st.composite ? S.tables(st, x.halftime, x.xg) : [];
    if (has.table && !st.composite){ const ft = S.formTable(fx, st), gh = S.gamesInHand(st); if (ft) vars.push(["form", "الفورمة", ft]); if (gh) vars.push(["hand", "المؤجلة", gh]); }
    const tablePane = has.table ? (vars.length ? `<div class="tabs" data-tabs="tv"><button type="button" data-t="all" aria-selected="true">الكل</button>` + vars.map(v => `<button type="button" data-t="${v[0]}" aria-selected="false">${v[1]}</button>`).join("") + "</div>" + pane("tv", "all", `<div id="table">${R.standings(st)}</div>`, true) + vars.map(v => pane("tv", v[0], v[2])).join("") : `<div id="table">${R.standings(st)}</div>`) + (x.bump ? S.sec("رحلة الموسم", "", S.bump(x.bump)) : "") : "";
    // predictions (93, 20, 136)
    const rmap = c.id === 538 ? S.ratingMap(ratings) : (x.ratings ? S.ratingMap(x.ratings) : {});
    const fdrHtml = st && !st.composite ? S.fdr(st, fx, rmap) : "", roadHtml = st && !st.composite ? S.roadTitle(st, fx, rmap, x.sim) : "";
    const clockHtml = S.seasonClock(fx, st, x.watch), projHtml = S.projections(stats, st);
    const pred = [clockHtml ? S.sec("ساعة الموسم", "", clockHtml) : "", roadHtml ? S.sec("الطريق للقب", "", roadHtml) : "", fdrHtml ? S.sec("صعوبة المباريات الياية", '<a href="/glossary/#difficulty">شو يعني؟</a>', fdrHtml) : "", x.watch && fx ? S.sec("أحلى مباريات الجولة الياية", "", S.watch(x.watch, fx)) : "", S.whatif(fx, st) ? S.sec("شو لو؟", "", S.whatif(fx, st)) : "", x.sim && x.sim.teams ? S.sec("توقعات آخر الموسم", '<a href="/glossary/#simulator">شو يعني؟</a>', S.sim(x.sim, st)) : "", st && st.magic ? S.sec("كم يحتاج فريقك؟", '<a href="/glossary/#magic-number">شو يعني؟</a>', S.magic(st)) : "", x["tournament-sim"] ? S.sec("من بيفوز بالبطولة؟", "", S.tsim(x["tournament-sim"])) : "", projHtml ? S.sec("كم بيسجل الهدافين لآخر الموسم؟", "", projHtml) : "", st && st.bracket && st.bracket.length ? S.sec("شجرة البطولة", "", S.bracket(st, null)) : "", x.scenarios ? S.sec("حاسبة التأهل", "", S.groupCalc(x.scenarios)) : ""].join("");
    // the numbers (137, 135, 46, 124, 119, 129, 139, 52, 37, 142, 143, 96, 138, 141)
    const num = [
      ["cards", "بطاقات تيفو", S.cards(x.cards, 12)], ["clutch", "منو الحاسم؟", S.clutch(x.clutch)], ["tor", "تشكيلة الجولة", S.teamOfRound(x["team-of-round"])],
      ["foreign", "أفضل محترف أجنبي", S.foreigners(x.foreigners)], ["improved", "الأكثر تطوّر", S.improved(x.improved)], ["young", "المواهب الإماراتية تحت 23", S.young(x["young-uae"])],
      ["clock", "ساعة الأهداف", S.clock(x["minute-clock"])], ["late", "ملوك الدقايق الأخيرة", S.late(x["goal-bands"])],
      ["pressure", "ترمومتر المدربين", S.pressure(x.pressure)], ["style", "بصمة كل فريق", S.style(x.style)], ["fortress", "حصون الملاعب", S.fortress(x.fortress)],
      ["fatigue", "مؤشر الإرهاق", S.fatigue(x.fatigue)], ["coaches", "أنجح المدربين في التاريخ", S.coachesLeague(x.coaches)],
      ["transfers", "سوق الانتقالات", S.transfers(x.transfers)],
      ["refs", "الحكام", S.referees(x.referees)], ["ages", "أعمار التشكيلات", S.ages(x["lineup-ages"])], ["rot", "مؤشر التدوير", S.rotation(x.rotation)],
      ["rating", "تصنيف تيفو للأندية", c.id === 538 ? S.ratingTable(ratings) : ""], ["world", "الدوري الإماراتي ضد العالم", c.id === 538 ? S.compare(compare, 538) : ""],
    ].filter(v => v[2]);
    const cmpLink = x.cards ? `<p><a class="btn" href="/c/${c.key}/compare/">قارن بين لاعبين أو فريقين</a></p>` : "";
    const GL = { cards:"tifo-card", clutch:"clutch", pressure:"pressure-index", style:"ppda", rot:"rotation", fatigue:"fatigue", rating:"tifo-rating" };
    const numPane = num.length ? cmpLink + `<nav class="chips secnav">` + num.map(v => `<a href="#n-${v[0]}">${v[1]}</a>`).join("") + "</nav>" + num.map(v => S.sec(v[1], GL[v[0]] ? `<a href="/glossary/#${GL[v[0]]}">شو يعني؟</a>` : "", v[2], "n-" + v[0])).join("") : "";
    const ats = ATS[c.id] ? S.sec("الهدافين التاريخيين", "", S.alltimeScorers(ATS[c.id])) : "";
    const derb = c.id === 538 ? S.derbyList(h2hIdx, H2H) : "";   // (records book renders in hist too)
    const hist = ats + (x.alltime ? S.sec("تاريخ الدوري", "من 1973", S.alltime(x.alltime)) : "") + (derb ? S.sec("سجل المواجهات بين الأندية", "", derb) : "") + (x.records && x.records.chases && x.records.chases.length ? S.sec("أرقام قياسية على المحك", "", S.records(x.records)) : "") + (x["records-book"] ? S.sec("كتاب الأرقام القياسية", "من " + esc(x["records-book"].since || ""), S.recordsBook(x["records-book"])) : "");
    const tl = [has.table && ["table", "الترتيب"], ["fixtures", "المباريات"], pred && ["pred", "التوقعات"], numPane && ["num", "الأرقام"], has.stats && ["goals", "الهدافين"], has.stats && ["assists", "صناع الأهداف"], hist && ["hist", "التاريخ"]].filter(Boolean);
    const body = `<p class="crumbs"><a href="/competitions/">البطولات</a></p><h1>${esc(c.name_ar)}</h1><p class="season">الموسم <span class="num">${esc(c.season || "")}</span></p>${c.dormant ? '<p class="note">البطولة متوقفة أو خلصت هالموسم. هذي آخر نتايجها.</p>' : ""}` + tabsHtml("c", tl) +
      (has.table ? pane("c", "table", tablePane, true) : "") + pane("c", "fixtures", `<div id="rounds">${rounds || '<p class="empty">ما في مباريات منشورة.</p>'}</div>`, !has.table) +
      (pred ? pane("c", "pred", pred) : "") + (numPane ? pane("c", "num", numPane) : "") +
      (has.stats ? pane("c", "goals", `<div id="goals">${R.leaders(stats, "goals")}</div>`) + pane("c", "assists", `<div id="assists">${R.leaders(stats, "assists")}</div>`) : "") + (hist ? pane("c", "hist", hist) : "");
    OGJ.push({ key:"c-" + c.id, home:c.name_ar, sub:"الترتيب والمباريات والتوقعات", hc:["#123A31", "#1B6F5A"] });
    write(`c/${c.key}/index.html`, page({ og:"c-" + c.id, path:`/c/${c.key}/`, page:"comp", attrs:` data-comp="${c.id}"`, nav:String(c.id), title:`${c.name_ar}: الترتيب والمباريات والتوقعات ${c.season || ""} | تيفو`, desc:`ترتيب ${c.name_ar} ومواعيد المباريات بتوقيت الإمارات والنتايج المباشرة، وتوقعات آخر الموسم، والهدافين وبطاقات اللاعبين والأرقام.`, body }));
    urls.push(`/c/${c.key}/`);
    if (x.cards){
      write(`c/${c.key}/compare/index.html`, page({ path:`/c/${c.key}/compare/`, page:"compare", attrs:` data-comp="${c.id}"`, nav:String(c.id), title:`قارن بين لاعبين أو فريقين في ${c.name_ar} | تيفو`, desc:`قارن أي لاعبين في ${c.name_ar} على رادار واحد وأرقامهم في كل 90 دقيقة، أو قارن بين فريقين.`,
        body:`<p class="crumbs"><a href="/c/${c.key}/">${esc(c.name_ar)}</a></p><h1>قارن</h1>` + tabsHtml("k", [["players", "لاعبين"], ["clubs", "فريقين"]]) + pane("k", "players", `<div class="cmpsel"><select id="pa" aria-label="اللاعب الأول"></select><select id="pb" aria-label="اللاعب الثاني"></select></div><div id="pout"><p class="empty">نحمّل الأرقام…</p></div>`, true) + pane("k", "clubs", `<div class="cmpsel"><select id="ta" aria-label="الفريق الأول"></select><select id="tb" aria-label="الفريق الثاني"></select></div><div id="tout"></div>`) }));
      urls.push(`/c/${c.key}/compare/`);
    }
  }
  // derby / head-to-head pages (38)
  for (const [k, h] of Object.entries(H2H)){
    const [a, b] = k.split("-"), na = (teamsJson.teams[a] || {}).name_ar || a, nb = (teamsJson.teams[b] || {}).name_ar || b;
    write(`h2h/${k}/index.html`, page({ path:`/h2h/${k}/`, page:"h2h", title:`${na} و${nb}: كل المواجهات | تيفو`, desc:`سجل مواجهات ${na} و${nb}: كم فاز كل فريق وكم تعادلوا، وكل النتايج.`, body:`<p class="crumbs"><a href="/c/uae-pro-league/#hist">تاريخ الدوري</a></p><h1>${esc(na)} و${esc(nb)}</h1>` + S.h2hPage(h) }));
    urls.push(`/h2h/${k}/`);
  }

  // ---- 4. home
  const nav = comps.filter(c => !c.dormant).map(c => `<a href="/c/${c.key}/"><span>${esc(c.name_ar)}</span><span class="muted small num">${esc(c.season || "")}</span></a>`).join("");
  const w538 = compX[538] && compX[538].watch, fx538 = compData.find(d => d.c.id === 538);
  const watchHome = w538 && fx538 ? S.sec("أحلى مباريات الجولة الياية في دوري أدنوك", "", S.watch(w538, fx538.fx)) : "";
  write("index.html", page({ path:"/", page:"home", nav:"home", title:"تيفو — نتايج مباريات اليوم مباشر، الدوري الإماراتي والمنتخب وكل البطولات", desc:"نتايج المباريات مباشر بتوقيت الإمارات: دوري أدنوك، والمنتخب، وكأس الخليج، وأبطال آسيا، والدوريات الكبيرة. الأحداث والتشكيلات والترتيب والتوقعات أول بأول.",
    body:`<section class="stand" id="stand" aria-label="مباراة اليوم"><canvas aria-hidden="true"></canvas><span class="kicker" id="standkick">مباراة اليوم</span><div class="cap" id="standcap">${R.standCap(R.featured(day.matches))}</div></section><div id="uaecd"></div><div class="tools"><a class="btn" href="/tv/">شاشة المجلس</a><a class="btn" href="/studio/">ستوديو التيفو</a></div><div id="mine"></div><div class="daynav"><button type="button" id="prev" aria-label="اليوم اللي قبل">›</button><b id="daytitle">${R.dayNav(today, today)}</b><button type="button" id="next" aria-label="اليوم اللي بعد">‹</button></div><p class="tools"><button type="button" class="btn" id="arabonly" aria-pressed="false">بس مباريات العرب</button><button type="button" class="btn" id="freeonly" aria-pressed="false">بس المجاني في بلدك</button><a class="btn" href="/today/">مباريات اليوم</a><a class="btn" href="/tomorrow/">مباريات بكرة</a></p><p class="livecount" id="livecount"></p><div id="day">${R.dayList(day.matches, index, { empty:"ما في مباريات اليوم." })}</div>${watchHome}<h2>البطولات</h2><div class="comps">${nav}</div>` }));

  // ---- 5. teams
  const tlist = [...teamIds];
  const full = new Set(index.focus_teams || []); compData.filter(d => d.c.scope === "uae").forEach(d => (d.st && d.st.groups || []).forEach(g => g.rows.forEach(r => full.add(r.team.id))));
  const teams = await pool(tlist, 8, id => full.has(id) ? get(`team/${id}.json`) : null);
  const rhist = await pool(tlist, 8, id => full.has(id) && id !== 5789 ? get(`ratings/team/${id}.json`, 1) : null);
  const st538 = compData.find(d => d.c.id === 538), x538 = compX[538] || {};
  let tcount = 0;
  const byTeam = new Map(); for (const m of matchSum.values()) for (const side of [m.home, m.away]) if (side && side.id){ if (!byTeam.has(side.id)) byTeam.set(side.id, { side, ms:[] }); byTeam.get(side.id).ms.push(m); }
  tlist.forEach((id, i) => {
    let t = teams[i];
    if (!t){ const b = byTeam.get(id); if (!b) return; t = { id, name:b.side.name, name_ar:b.side.name_ar, fixtures:b.ms, squad:[], partial:true }; }
    tcount++;
    const f = R.teamFixtures(t);
    { const slim = m => m && { id:m.id, comp:m.comp, kickoff_utc:m.kickoff_utc, kickoff_uae:m.kickoff_uae, status:m.status, minute:m.minute, score:m.score, home:m.home, away:m.away, time_tbd:m.time_tbd };   // favourites card (179)
      const tf = path.join(OUT, "tn", t.id + ".json"); fs.mkdirSync(path.dirname(tf), { recursive:true }); fs.writeFileSync(tf, JSON.stringify({ id:t.id, name:t.name, name_ar:t.name_ar, next:slim(f.next[0]), last:slim(f.past[0]) })); }
    const sub = [t.coach ? `المدرب <span class="lat">${esc(t.coach.name)}</span>` : "", t.venue && t.venue.name ? `الملعب <span class="lat">${esc(t.venue.name)}</span>` : ""].filter(Boolean).join("<br>");
    // the club in numbers (91, 36, 96, 135, 137, 141)
    let nums = "";
    if (rhist[i]) nums += S.sec("تصنيف تيفو عبر السنين", "", S.ratingChart(rhist[i], id));
    const row = st538 && st538.st && st538.st.groups[0].rows.find(r => r.team.id === id);
    if (row && row.last_season_same_round){ const l = row.last_season_same_round; nums += S.sec("هالموسم ضد الموسم الماضي", `بعد ${row.played} جولات`, `<div class="pstats"><div><b>${row.pts}</b><span>نقاطه الحين</span></div><div><b>${l.pts}</b><span>نفس الوقت الموسم الماضي</span></div><div><b><bdi dir="ltr">${row.pts - l.pts > 0 ? "+" : ""}${row.pts - l.pts}</bdi></b><span>الفرق</span></div><div><b>${row.gf} - ${row.ga}</b><span>أهدافه الحين</span></div><div><b>${l.gf} - ${l.ga}</b><span>الموسم الماضي</span></div></div>`); }
    if (x538.pressure && x538.pressure.teams && x538.pressure.teams[id]){ const pr = { teams:{} }; pr.teams[id] = x538.pressure.teams[id]; nums += S.sec("الضغط على المدرب", "", S.pressure(pr)); }
    const tc = x538.cards ? S.cards(x538.cards, 11, c => c.team === id) : ""; if (tc) nums += S.sec("بطاقات تيفو للاعبين", "", tc);
    if (x538.clutch && x538.clutch.players){ const cl = S.clutch({ players:x538.clutch.players.filter(p => p.team === id) }); if (cl) nums += S.sec("منو الحاسم في الفريق؟", "", cl); }
    const chh = S.clubHistory(CLUBS[id]); if (chh) nums = S.sec("خزانة البطولات والتاريخ", "", chh) + nums;
    const ln = S.loans(t); if (ln) nums += S.sec("لاعبينه المعارين", "", ln);
    const tv2 = S.travel(t, t.fixtures); if (tv2) nums += S.sec("سافر مع فريقك", "مباريات آسيا برا الدولة", tv2);
    const co = S.coachesTeam(x538.coaches, id); if (co) nums += S.sec("مدربين النادي عبر التاريخ", "في الدوري", co);
    if (x538.fortress && x538.fortress.stadiums){ const fs2 = x538.fortress.stadiums.filter(s => s.team === id); if (fs2.length) nums += S.sec("حصن الملعب", "", S.fortress({ since:x538.fortress.since, stadiums:fs2 })); }
    // national team (144, 145, 59, 39)
    if (id === 5789){
      const x329 = compX[329] || {};
      if (x329.scenarios) { const sc = S.scenarios(x329.scenarios, 5789); if (sc) nums += S.sec("سيناريوهات كأس الخليج", "", sc); }
      if (x329["tournament-sim"]) nums += S.sec("فرص الإمارات في كأس الخليج", "", S.tsim(x329["tournament-sim"]));
      const x290 = compX[290] || {}; if (x290["tournament-sim"]) nums += S.sec("فرص الإمارات في كأس آسيا", "", S.tsim(x290["tournament-sim"]));
      if (fifa) nums += S.sec("تصنيف فيفا", "من 1992", S.fifa(fifa));
      if (natRatings && natRatings.uae) nums += S.sec("تصنيف تيفو للمنتخبات", "", `<p>الإمارات في المركز <b class="num">${natRatings.uae_world_rank}</b> عالمياً بتصنيف تيفو (<span class="num">${Math.round(natRatings.uae)}</span> نقطة).</p>`);
      if (abroad) { const ab = S.abroad(abroad); if (ab) nums += S.sec("الإماراتيين المحترفين برا", "", ab); }
      const nc = S.natClubs(t); if (nc) nums += S.sec("لاعبي المنتخب في أنديتهم", "", nc);
    }
    const tabs = [["next", "الياية"], ["past", "النتايج"], ["squad", "اللاعبين"], nums && ["nums", id === 5789 ? "المنتخب بالأرقام" : "بالأرقام"]].filter(Boolean);
    const body = `<div class="th"><div class="in">${R.logo(t, "lg")}<div><h1>${R.tname(t)}</h1>${sub ? `<p>${sub}</p>` : ""}</div></div>${R.teamStrip(t)}</div>
<div class="btnrow"><button type="button" class="btn" id="mybtn">هذا فريقي</button><a class="btn" href="/v1/team/${t.id}.ics" id="ics">مبارياته في تقويم جوالك</a><button type="button" class="btn" id="wpbtn" hidden>خلفية للجوال</button><a class="btn" href="/t/${t.id}/poster/">بوستر الموسم للطباعة</a></div>${t.id === 5789 ? '<div id="uaecd"></div>' : ""}` +
      tabsHtml("t", tabs) + pane("t", "next", `<div id="next">${f.next.slice(0, 6).map(m => R.matchRow(m, { date:true })).join("") || '<p class="empty">ما في مباريات ياية منشورة.</p>'}</div>`, true) +
      pane("t", "past", `<div id="past">${f.past.slice(0, 10).map(m => R.matchRow(m, { date:true })).join("")}</div>`) + pane("t", "squad", `<div id="squad">${R.squad(t)}</div>`) + (nums ? pane("t", "nums", nums) : "");
    const tog = full.has(id); if (tog) OGJ.push({ key:"t-" + id, home:t.name_ar || t.name, home_id:id, hc:colors[id], sub:"المباريات والنتايج واللاعبين" });
    const html = page({ og:tog ? "t-" + id : null, path:`/t/${t.id}/`, page:"team", attrs:` data-id="${t.id}" data-name="${esc(t.name_ar || t.name)}"`, nav:t.id === 5789 ? "uae" : "", title:`${t.name_ar || t.name}: المباريات والنتايج واللاعبين | تيفو`, desc:`مواعيد مباريات ${t.name_ar || t.name} بتوقيت الإمارات، ونتايجه، وقائمة اللاعبين، وأرقامه، واشتراك تقويم يتحدّث بروحه.`, body });
    write(`t/${t.id}/index.html`, html); urls.push(`/t/${t.id}/`);
    if ((t.fixtures || []).length) write(`t/${t.id}/poster/index.html`, page({ path:`/t/${t.id}/poster/`, page:"poster", title:`جدول مباريات ${t.name_ar || t.name} للطباعة | تيفو`, desc:`جدول مباريات ${t.name_ar || t.name} للموسم كامل بتوقيت بلدك، جاهز للطباعة.`, body:S.poster(t) }));
    if (t.id === 5789) write("uae/index.html", html.replace(`<link rel="canonical" href="${SITE}/t/5789/">`, `<link rel="canonical" href="${SITE}/uae/">`));
  });

  // ---- 6. players (135, 120, 137, 149): every player the league files name
  const pids = Object.keys(allPlayers);
  const uaeP = new Set(Object.keys((compX[538] && compX[538].players && compX[538].players.players) || {}));   // the pipeline writes player/{id}.json for the UAE league
  const pjs = await pool(pids, 8, id => uaeP.has(id) ? get(`player/${id}.json`, 1) : null);
  let pcount = 0;
  pids.forEach((id, i) => {
    const ap = allPlayers[id] || {}, sv = k => ap.stats && ap.stats[k] ? ap.stats[k].value : null;
    const p = pjs[i] || { name:ap.name, team:ap.team, comp:ap.comp, minutes:ap.minutes, goals:sv("goals"), assists:sv("goal_assist"), rating:sv("rating") }; if (!p || !p.name) return; pcount++;
    const tm = p.team || allPlayers[id].team, cx = compX[p.comp || 538] || x538, card = cx.cards && cx.cards.players && cx.cards.players[id];
    const cl = cx.clutch && cx.clutch.players && cx.clutch.players.find(c => String(c.id) === id);
    const tt = { id:tm, name_ar:(S && teamsJson && teamsJson.teams[tm] && teamsJson.teams[tm].name_ar) || "" };
    const st = `<div class="pstats"><div><b>${p.goals ?? "—"}</b><span>أهداف</span></div><div><b>${p.assists ?? "—"}</b><span>صناعة</span></div><div><b>${p.minutes ?? "—"}</b><span>دقيقة</span></div><div><b>${p.rating != null ? Number(p.rating).toFixed(1) : "—"}</b><span>التقييم</span></div>${cl ? `<div><b>${cl.total}</b><span>نقاط جابها</span></div>` : ""}</div>`;
    const body = `<p class="crumbs"><a href="/t/${tm}/">${esc(tt.name_ar)}</a></p><h1 class="lat">${esc(p.name)}</h1><p class="season">${[p.position && `المركز <span class="lat">${esc(p.position.split(",")[0])}</span>`, p.number && `الرقم <span class="num">${esc(p.number)}</span>`, p.country && `<span class="flag">${esc(p.country)}</span>`].filter(Boolean).join("، ")}</p>` +
      (card ? S.card(id, card).replace('class="tcard"', 'class="tcard big"') : "") + S.sec("موسمه", esc(p.season || ""), st) + (cx.similar ? (() => { const sm = S.similar(cx.similar, id); return sm ? S.sec("منو يلعب مثله؟", "", sm) : ""; })() : "") +
      (cx.shots && cx.shots.available !== false && cx.shots.players && cx.shots.players[id] ? S.sec("خريطة تسديداته", "", S.shotmap(cx.shots.players[id])) : "") +
      (card ? `<p><a class="btn" href="/c/${(comps.find(cc => cc.id === (p.comp || 538)) || {}).key || "uae-pro-league"}/compare/?a=${id}">قارنه بلاعب ثاني</a></p>` : "");
    write(`p/${id}/index.html`, page({ path:`/p/${id}/`, page:"player", title:`${p.name}: أرقامه هالموسم | تيفو`, desc:`${p.name}، ${tt.name_ar}: أهدافه وصناعته وتقييمه وبطاقة تيفو، واللاعبين اللي يلعبون مثله.`, body }));
    urls.push(`/p/${id}/`);
  });

  // ---- 7. matches: summary for all, full detail where stored; probabilities (92) and records at stake (94, 95)
  const mids = [...matchSum.keys()];
  const withDetail = new Set(mids.filter(id => { const m = matchSum.get(id); return m.status === "finished" || R.isLive(m) || (Date.parse(m.kickoff_utc) - Date.now() < 3 * 864e5 && Date.parse(m.kickoff_utc) > Date.now() - 864e5); }));
  const det = await pool([...withDetail], 8, id => get(`match/${id}.json`, 1));
  const D = new Map(); [...withDetail].forEach((id, i) => { if (det[i]) D.set(id, det[i]); });
  for (const id of mids){
    const md = D.get(id) || matchSum.get(id), sum = matchSum.get(id), ttl = `${R.tname(md.home)} ${md.score ? md.score.home + "-" + md.score.away : "ضد"} ${R.tname(md.away)}`;
    const probs = md.status === "scheduled" ? (md.probs || sum.probs) : null, facts = md.status === "scheduled" ? factsByMatch[id] : null;
    const fa = md.status === "scheduled" && md.comp === 538 && x538.fatigue ? S.fatigue(x538.fatigue, [md.home.id, md.away.id]) : "";
    const ai = (APPROVED.summary && AIS[id] ? S.aiSummary(AIS[id]) : "") + (APPROVED.preview && md.status === "scheduled" && AIP[id] ? S.sec("تحليل ما قبل المباراة", "", S.aiPreview(AIP[id])) : "");
    const cx = compX[md.comp] || {}, cdata = compData.find(d => d.c.id === md.comp) || {};
    const uaeMatch = R.UAE_COMPS.indexOf(md.comp) >= 0 || md.home.id === 5789 || md.away.id === 5789;
    const press = md.status === "scheduled" && uaeMatch ? S.pressSheet(md, cdata.st, cdata.stats, factsByMatch[id], cx.fatigue, D.get(id)) : "";
    const thread = APPROVED.thread && AIS[id] ? S.aiThread(AIS[id]) : "";
    const opp = md.status === "scheduled" ? S.oppReport(md, cx, cdata.stats) : "";
    const ww = md.status !== "finished" ? S.watchWhere(BC[md.comp]) : "", hl = md.status === "finished" ? S.highlight(HLT[md.comp], md) : "";
    const mdy = md.venue && STAD[md.venue.id] ? S.matchDay(md, STAD[md.venue.id]) : "";
    const sg = mdy ? S.sec("رايح الملعب؟", "", mdy) : "";
    const sgrid = probs ? S.scoreGrid(probs, md) : "";
    const pre = ai + (hl ? `<p>${hl}</p>` : "") + (md.status !== "finished" ? `<div id="wwbox" data-comp="${md.comp}">` + (ww ? S.sec("وين تنقل في الإمارات", "", ww) : "") + "</div>" : "") + sg + (probs ? S.probs(probs, md) + (sgrid ? S.sec("أرجح النتايج بالضبط", "", sgrid) : "") : "") + (fa ? S.sec("ضغط المباريات", "", fa) : "") + (facts && facts.length ? S.sec("قبل المباراة", "", S.matchFacts(facts)) : "");
    const body = `<div id="mh">${R.matchHead(md)}</div><div class="tools"><button type="button" class="btn" id="secondbtn">الشاشة الثانية</button><button type="button" class="btn" id="storybtn">صورة للستوري</button><a class="btn" href="/tv/?m=${id}">على شاشة المجلس</a></div><script type="application/json" id="msum">${JSON.stringify(Object.assign({}, sum, { events:undefined, lineups:undefined, stats:undefined, h2h:undefined })).replace(/</g, "\\u003c")}</script><div id="catchup">${R.catchup(md)}</div><div id="facts">${R.matchFacts(md, index)}</div>${pre}` +
      tabsHtml("m", [["events", "الأحداث"], ["lineups", "التشكيلة"], ["stats", "الإحصائيات"], ["h2h", "المواجهات"], opp && ["opp", "تقرير الفريقين"], press && ["press", "ورقة الصحفي"], thread && ["thread", "ثريد إكس"]].filter(Boolean)) + (opp ? pane("m", "opp", opp) : "") + (press ? pane("m", "press", press) : "") + (thread ? pane("m", "thread", thread) : "") +
      pane("m", "events", `<div id="events">${R.events(md)}</div>`, true) + pane("m", "lineups", `<div class="tools"><button type="button" class="btn" id="p3dbtn" data-src="/assets/pitch3d.${ASSET_V}.js"${md.lineups && md.lineups.home ? "" : " hidden"}>شوفها على ملعب ثلاثي الأبعاد</button></div><div id="p3d"></div><div id="lineups">${R.lineups(md)}</div>`) + pane("m", "stats", `<div id="stats">${R.stats(md)}</div>`) + pane("m", "h2h", `<div id="h2h">${R.h2h(md)}</div>`);
    const ld = { "@context":"https://schema.org", "@type":"SportsEvent", name:`${md.home.name_ar || md.home.name} ضد ${md.away.name_ar || md.away.name}`, startDate:md.kickoff_utc, sport:"Football", homeTeam:{ "@type":"SportsTeam", name:md.home.name_ar || md.home.name }, awayTeam:{ "@type":"SportsTeam", name:md.away.name_ar || md.away.name }, ...(md.venue ? { location:{ "@type":"Place", name:md.venue.name_ar || md.venue.name_en } } : {}) };
    const recent = Date.parse(md.kickoff_utc || 0), ogOn = uaeMatch || (recent > Date.now() - 3 * 864e5 && recent < Date.now() + 7 * 864e5 && [538, 11027, 329, 525, 9469, 536, 47, 87, 42].includes(md.comp));
    if (ogOn) OGJ.push({ key:"m-" + id, home:md.home.name_ar || md.home.name, away:md.away.name_ar || md.away.name, home_id:md.home.id, away_id:md.away.id, hc:colors[md.home.id], ac:colors[md.away.id], comp:md.comp_name_ar || R.compName(index, md.comp), score:md.score ? `${md.score.away} - ${md.score.home}` : null, time:md.score ? null : R.hhmm(md.kickoff_uae), sub:md.score ? (md.status === "finished" ? "انتهت" : "مباشر") : R.dayLabel(R.ymd(md.kickoff_uae)) + " بتوقيت الإمارات" });
    write(`m/${id}/index.html`, page({ og:ogOn ? "m-" + id : null, path:`/m/${id}/`, page:"match", attrs:` data-id="${id}"`, title:`${ttl} — ${md.comp_name_ar || R.compName(index, md.comp)} | تيفو`, desc:`${R.tname(md.home)} ضد ${R.tname(md.away)} ${R.dayLabel(R.ymd(md.kickoff_uae))} الساعة ${R.hhmm(md.kickoff_uae)} بتوقيت الإمارات: النتيجة المباشرة والأحداث والتشكيلة والإحصائيات والمواجهات السابقة.`, body, ld }));
    urls.push(`/m/${id}/`);
  }

  // ---- 7b. majlis TV (22, 131) and the Tifo studio (152)
  write("tv/index.html", page({ path:"/tv/", page:"tv", title:"شاشة المجلس: كل المباريات مباشر على شاشة كبيرة | تيفو", desc:"افتحها على تلفزيون المجلس أو القهوة: كل مباريات اليوم مباشر بخط كبير، تتحدّث بروحها كل 20 ثانية.",
    body:'<div class="tvbar"><h1>شاشة المجلس</h1><button type="button" class="btn" id="fsbtn">ملء الشاشة</button></div><div id="tv" class="tvgrid"><p class="empty">نحمّل المباريات…</p></div><p class="muted small">افتح هالصفحة على تلفزيون المجلس. تتحدّث بروحها كل 20 ثانية. ولمتابعة مباراتين جنب بعض، افتح أي مباراة واضغط «على شاشة المجلس».</p>' }));
  urls.push("/tv/");
  const clubs = [5789].concat(((compData.find(d => d.c.id === 538) || {}).st || { groups:[{ rows:[] }] }).groups[0].rows.map(r => r.team.id));
  write("studio/index.html", page({ path:"/studio/", page:"studio", title:"ستوديو التيفو: صمّم لافتة فريقك للمدرج | تيفو", desc:"اختار فريقك واكتب عبارتك، وتطلع لك لافتة بألوان النادي جاهزة للطباعة وتاخذها للملعب.",
    body:`<h1>ستوديو التيفو</h1><p class="muted">اختار فريقك واكتب عبارتك، وتطلع لك لافتة بألوان ناديك (3000×1000) جاهزة للطباعة.</p><div class="studio"><div class="cmpsel"><select id="sclub" aria-label="الفريق">${clubs.map(id => `<option value="${id}">${esc((teamsJson.teams[id] || {}).name_ar || id)}</option>`).join("")}</select><input id="stext" maxlength="40" value="ما نمشي بروحنا" aria-label="العبارة"></div><canvas id="sprev" width="1500" height="500"></canvas><div class="tools"><button type="button" class="btn" id="sdl">نزّل اللافتة</button></div></div>` }));
  urls.push("/studio/");

  // ---- 7c. Tifo Cast (19, 161): only approved kinds; audio copied next to the pages
  const casts = [];
  if (APPROVED.podcast) for (const [k, p] of Object.entries(AIC)) if (fs.existsSync(path.join(CACHE, "ai/podcast", k + ".mp3"))) casts.push({ kind:"podcast", key:k, title:p.title, file:`/audio/podcast-${k}.mp3`, src:path.join(CACHE, "ai/podcast", k + ".mp3"), lines:p.lines });
  if (APPROVED.round) for (const [k, r] of Object.entries(AIR)) if (fs.existsSync(path.join(CACHE, "ai/round", k + ".mp3"))) casts.push({ kind:"round", key:k, title:r.title, file:`/audio/round-${k}.mp3`, src:path.join(CACHE, "ai/round", k + ".mp3"), text:r.script });
  if (casts.length){
    fs.mkdirSync(path.join(OUT, "audio"), { recursive:true }); casts.forEach(c => fs.copyFileSync(c.src, path.join(OUT, c.file)));
    casts.sort((a, b) => b.key.localeCompare(a.key));
    write("cast/index.html", page({ path:"/cast/", page:"cast", title:"تيفو كاست: الجولة بصوت إماراتي | تيفو", desc:"خلاصة كل جولة من دوري أدنوك بصوت زايد، وبودكاست تيفو كاست الأسبوعي بصوت زايد وهلا.",
      body:"<h1>تيفو كاست</h1>" + casts.map(c => S.sec(esc(c.title), c.kind === "podcast" ? "بودكاست الأسبوع" : "خلاصة الجولة", `<audio controls preload="none" src="${c.file}"></audio><details class="more"><summary>النص</summary>${c.lines ? c.lines.map(l => `<p><b>${l.who === "zayd" ? "زايد" : "هلا"}:</b> ${esc(l.text)}</p>`).join("") : `<p>${esc(c.text)}</p>`}</details>`)).join("") }));
    urls.push("/cast/");
  }
  // ---- 7d. matches of the week (25): the next 7 days, UAE first, then by what's at stake
  const in7 = [...matchSum.values()].filter(m => m.status === "scheduled" && m.kickoff_utc && Date.parse(m.kickoff_utc) > Date.now() && Date.parse(m.kickoff_utc) < Date.now() + 7 * 864e5);
  const wscore = m => { let v = 0; if (R.UAE_COMPS.indexOf(m.comp) >= 0) v += 100; if (m.home.id === 5789 || m.away.id === 5789) v += 150; const w = compX[m.comp] && compX[m.comp].watch && compX[m.comp].watch.matches[m.id]; if (w) v += w.score; const st = (compData.find(d => d.c.id === m.comp) || {}).st; if (st && st.groups && !st.composite){ const rk = id => { const r = st.groups[0].rows.find(r => r.team.id === id); return r ? r.rank : 20; }; v += Math.max(0, 40 - 2 * (rk(m.home.id) + rk(m.away.id))); } if ([42, 525].includes(m.comp)) v += 20; return v; };
  const picks = in7.map(m => ({ m, v:wscore(m) })).sort((a, b) => b.v - a.v).slice(0, 12).sort((a, b) => a.m.kickoff_utc.localeCompare(b.m.kickoff_utc));
  write("week/index.html", page({ path:"/week/", page:"week", title:"مباريات الأسبوع اللي تستاهل تسهر لها | تيفو", desc:"أهم 12 مباراة في الأسبوع الياي بتوقيت الإمارات: الإماراتية أول، وبعدها اللي الترتيب فيها على المحك.",
    body:"<h1>مباريات الأسبوع</h1><p class=\"muted\">أهم مباريات الأيام السبعة الياية بتوقيت الإمارات: مباريات الإمارات أول، وبعدها اللي فيها الترتيب على المحك أو الفريقين من فوق الجدول.</p>" + (picks.length ? picks.map(x => `<div class="wk"><span class="muted small">${esc(x.m.comp_name_ar || R.compName(index, x.m.comp))}</span>${R.matchRow(x.m, { date:true })}</div>`).join("") : '<p class="empty">ما في مباريات في الأيام الياية.</p>') }));
  urls.push("/week/");

  // ---- 224 records tonight (home), 226 referee pages, 227 coach pages, 228 round pages
  { const tonight = (day.matches || []).flatMap(m => (factsByMatch[m.id] || []).filter(f => f.record_at_stake).map(f => ({ m, f })));
    const rt = S.recordsTonight(tonight); if (rt){ const hf = path.join(OUT, "index.html"); fs.writeFileSync(hf, fs.readFileSync(hf, "utf8").replace('<h2>البطولات</h2>', S.sec("أرقام ممكن تنكسر اليوم", "", rt) + "<h2>البطولات</h2>")); } }
  const byIdM = id => matchSum.get(id) || D.get(id);
  const stIds = cid => { const d = compData.find(x => x.c.id === cid); return d && d.st && !d.st.composite && d.st.groups && d.st.groups[0] ? d.st.groups[0].rows.map(r => r.team.id) : []; };
  const refs = new Map(); compData.forEach(({ c, x }) => ((x.referees && x.referees.referees) || []).forEach(r => { if (!refs.has(r.id)) refs.set(r.id, Object.assign({ comp:c }, r)); }));
  for (const [rid, r] of refs){ write(`r/${rid}/index.html`, page({ path:`/r/${rid}/`, page:"ref", title:`الحكم ${r.name}: كروته وبلنتياته ومبارياته | تيفو`, desc:`سجل الحكم ${r.name} في ${r.comp.name_ar}: الإنذارات والطرد وضربات الجزاء بالمباراة، وكل مبارياته.`, body:`<p class="crumbs"><a href="/c/${r.comp.key}/#num">${esc(r.comp.name_ar)}</a></p><h1 class="lat">${esc(r.name)}</h1><p class="season">حكم${r.country ? ` <span class="flag">${esc(r.country)}</span>` : ""}</p>` + S.refPage(r, byIdM) })); urls.push(`/r/${rid}/`); }
  const coachRows = new Map(); compData.forEach(({ x }) => { const ct = x.coaches && x.coaches.teams; if (!ct) return; for (const [tid, t] of Object.entries(ct)){ (t.history || []).forEach(h => { const k = h.id || h.name; if (!coachRows.has(k)) coachRows.set(k, { name:h.name, rows:[] }); coachRows.get(k).rows.push(Object.assign({ team:+tid }, h)); }); if (t.current){ const k = t.current.id || t.current.name; if (!coachRows.has(k)) coachRows.set(k, { name:t.current.name, rows:[] }); coachRows.get(k).current = +tid; } } });
  for (const [cid, co] of coachRows){ if (!co.rows.length) continue; co.rows.sort((a, b) => String(b.season).localeCompare(String(a.season)));
    write(`coach/${cid}/index.html`, page({ path:`/coach/${cid}/`, page:"ref", title:`المدرب ${co.name}: مسيرته في الدوري | تيفو`, desc:`مسيرة المدرب ${co.name} في الدوري: الأندية والمواسم والفوز والتعادل والخسارة ومعدل النقاط.`, body:`<h1 class="lat">${esc(co.name)}</h1>${co.current ? `<p class="season">يدرّب الحين <a href="/t/${co.current}/">${esc((teamsJson.teams[co.current] || {}).name_ar || "")}</a></p>` : ""}` + S.coachPage(co.name, co.rows) })); urls.push(`/coach/${cid}/`); }
  for (const { c, fx, x } of compData){ if (!fx || !fx.matches) continue; const rr = R.rounds(fx);
    for (const k of rr.order){ if (isNaN(parseFloat(k))) continue; const ms = rr.by[k], fin = ms.filter(m => m.status === "finished"), goals = fin.reduce((a, m) => a + (m.score ? m.score.home + m.score.away : 0), 0);
      const tor = x["team-of-round"] && x["team-of-round"].rounds && x["team-of-round"].rounds[k] ? S.teamOfRound({ rounds:{ [k]:x["team-of-round"].rounds[k] } }) : "";
      write(`c/${c.key}/r/${k}/index.html`, page({ path:`/c/${c.key}/r/${k}/`, page:"ref", nav:String(c.id), title:`${c.name_ar}: الجولة ${k} ${c.season || ""} | تيفو`, desc:`نتايج ومواعيد الجولة ${k} من ${c.name_ar} بتوقيت بلدك، والأهداف وتشكيلة الجولة.`,
        body:`<p class="crumbs"><a href="/c/${c.key}/">${esc(c.name_ar)}</a></p><h1>الجولة ${esc(k)}</h1>` + (fin.length && stIds(c.id).length ? S.sec("قصة الجولة", "انزل وشوف", S.roundStory(fx, k, stIds(c.id))) : "") + (fin.length ? `<div class="pstats"><div><b>${fin.length}</b><span>مباراة خلصت</span></div><div><b>${goals}</b><span>هدف</span></div><div><b>${fin.length ? (goals / fin.length).toFixed(1) : 0}</b><span>بالمباراة</span></div></div>` : "") + R.roundList(ms) + (tor ? S.sec("تشكيلة الجولة", "", tor) : "") + `<p class="tools">${rr.order.indexOf(k) > 0 ? `<a class="btn" href="/c/${c.key}/r/${rr.order[rr.order.indexOf(k) - 1]}/">الجولة اللي قبل</a>` : ""}${rr.order.indexOf(k) < rr.order.length - 1 ? `<a class="btn" href="/c/${c.key}/r/${rr.order[rr.order.indexOf(k) + 1]}/">الجولة اللي بعد</a>` : ""}</p>` })); urls.push(`/c/${c.key}/r/${k}/`); } }

  // ---- 198: pages for the most-searched phrases
  { const tmr = new Date(Date.now() + 4 * 3600e3 + 864e5).toISOString().slice(0, 10), dayT = await get(`day/${tmr.replace(/-/g, "")}.json`) || { matches:[] };
    [["today", "اليوم", today, day], ["tomorrow", "بكرة", tmr, dayT]].forEach(([slug, word, d, dd]) => {
      write(`${slug}/index.html`, page({ path:`/${slug}/`, page:"daypage", nav:"home", title:`مباريات ${word} ${R.dayLabel(d)}: المواعيد والقنوات الناقلة | تيفو`, desc:`كل مباريات ${word} ${R.dayLabel(d)} بتوقيت بلدك: الدوريات العربية، والدوري الإنجليزي والإسباني، وأبطال آسيا وأوروبا، مع القنوات الناقلة والنتايج مباشر.`,
        body:`<h1>مباريات ${word}</h1><p class="season">${esc(R.dayLabel(d))}، والمواعيد بتوقيت بلدك</p>` + R.dayList(dd.matches, index, { empty:"ما في مباريات." }) + '<p><a class="btn" href="/watch/">وين تنقل كل بطولة</a></p>' })); urls.push(`/${slug}/`); }); }

  // ---- 262 glossary, 251 lab, 289 academy
  const GLOSS = require("./src/glossary.js");
  write("glossary/index.html", page({ path:"/glossary/", page:"ref", title:"قاموس مصطلحات الكورة بالإماراتي | تيفو", desc:"شرح بسيط لكل مصطلح في تيفو: الأهداف المتوقعة، الضغط، تصنيف تيفو، محاكي الموسم، التسلل، الفار وغيرها.", body:"<h1>قاموس المصطلحات</h1><p class=\"muted\">شرح بسيط لكل مصطلح يطلع في تيفو.</p><dl class=\"gl\">" + GLOSS.map(g => `<dt id="${g[0]}">${esc(g[1])}</dt><dd>${esc(g[2])}</dd>`).join("") + "</dl>" })); urls.push("/glossary/");
  const labComps = compData.filter(d => d.x.players && d.x.players.players && Object.keys(d.x.players.players).length > 20).map(d => d.c);
  if (labComps.length){ write("lab/index.html", page({ path:"/lab/", page:"lab", title:"مختبر تيفو: قارن أي رقمين لكل لاعبين الدوري | تيفو", desc:"اختار أي رقمين (تسديدات، أهداف، مراوغات، افتكاك…) وشوف كل لاعبين الدوري على رسم واحد.", body:'<h1>مختبر تيفو</h1><p class="muted">اختار الدوري ورقمين، وكل لاعب يطلع نقطة. اللي فوق وعلى اليسار أحسن في الرقمين.</p><div class="labsel"><select id="lcomp" aria-label="الدوري">' + labComps.map(c => `<option value="${c.id}">${esc(c.name_ar)}</option>`).join("") + '</select><select id="lx" aria-label="الرقم الأفقي"></select><select id="ly" aria-label="الرقم العمودي"></select><input id="lq" placeholder="ظلّل لاعب بالاسم" aria-label="ظلّل لاعب"></div><div id="lplot"><p class="empty">نحمّل…</p></div>' })); urls.push("/lab/"); }
  { const x5 = compX[538] || {}, lessons = [];
    const topR = ratings && ratings.teams && ratings.teams.filter(t => t.in_league)[0]; if (topR) lessons.push(["tifo-rating", "تصنيف تيفو: منو أقوى فريق؟", `كل فريق له رقم قوة يتغيّر بعد كل مباراة. الحين أقوى فريق في دوري أدنوك ${esc(topR.name_ar)} بـ<b class="num">${Math.round(topR.rating)}</b>، والفريق المتوسط حوالي 1500.`, "/c/uae-pro-league/#num"]);
    const nm = [...matchSum.values()].find(m => m.status === "scheduled" && m.probs && m.comp === 538); if (nm) lessons.push(["probabilities", "نسب الفوز: مب توقع أكيد", `مباراة ${R.tname(nm.home)} و${R.tname(nm.away)}: تيفو يعطي فوز ${R.tname(nm.home)} <b class="num">${Math.round(nm.probs.home * 100)}%</b>. يعني لو انلعبت 100 مرة، بيفوز تقريباً ${Math.round(nm.probs.home * 100)} مرة، مب إنه أكيد بيفوز.`, `/m/${nm.id}/`]);
    const sim = x5.sim; if (sim){ const best = Object.entries(sim.teams).sort((a, b) => b[1].title - a[1].title)[0]; lessons.push(["simulator", "محاكي الموسم", `لعبنا باقي الموسم ${Number(sim.sims).toLocaleString("en-US")} مرة. ${esc((teamsJson.teams[best[0]] || {}).name_ar || "")} خلص أول في <b class="num">${Math.round(best[1].title * 100)}%</b> منها، وهذي فرصته للبطولة.`, "/c/uae-pro-league/#pred"]); }
    const xgl = compX[47] && compX[47].xg && compX[47].xg.rows; if (xgl){ const lk = xgl.slice().sort((a, b) => b.luck - a.luck)[0]; lessons.push(["xg", "الأهداف المتوقعة والحظ", `في الدوري الإنجليزي، ${esc((teamsJson.teams[lk.team] || {}).name_ar || "")} جمع <b class="num">${lk.pts}</b> نقطة، والمتوقع من أدائه <b class="num">${lk.xpts.toFixed(1)}</b>. الفرق هو «الحظ».`, "/c/premier-league/#table"]); }
    const sty = x5.style && x5.style.teams; if (sty){ const pr = Object.entries(sty).filter(([, v]) => v.style.ppda != null).sort((a, b) => a[1].style.ppda - b[1].style.ppda)[0]; if (pr) lessons.push(["ppda", "الضغط: الرقم الأقل أقوى", `${esc((teamsJson.teams[pr[0]] || {}).name_ar || "")} يخلّي الخصم يلعب بس <b class="num">${pr[1].style.ppda.toFixed(1)}</b> تمريرة قبل ما يحاول يقطع الكورة، وهذا أعلى ضغط في الدوري.`, "/c/uae-pro-league/#num"]); }
    const cl = x5.clutch && x5.clutch.players && x5.clutch.players[0]; if (cl) lessons.push(["clutch", "منو الحاسم؟", `${esc(((allPlayers[cl.id] || {}).name) || "")} جاب لفريقه <b class="num">${cl.total}</b> نقاط بأهدافه وصناعته، يعني نقاط ما كانت بتجي بدونه.`, `/p/${cl.id}/`]);
    lessons.push(["difficulty", "صعوبة المباريات", "كل مباراة ياية لها لون: الفاتح سهلة والغامق صعبة، حسب تصنيف الخصم ووين تنلعب. تنفعك تعرف منو جدوله أسهل للقب.", "/c/uae-pro-league/#pred"]);
    write("academy/index.html", page({ path:"/academy/", page:"ref", title:"أكاديمية تيفو: كيف تقرا أرقام الكورة | تيفو", desc:"دروس قصيرة بالإماراتي: تصنيف تيفو، نسب الفوز، محاكي الموسم، الأهداف المتوقعة، الضغط، الحاسم، والصعوبة، بأمثلة حقيقية.", body:"<h1>أكاديمية تيفو</h1><p class=\"muted\">كيف تقرا أرقامنا، في دروس قصيرة وأمثلة من مباريات حقيقية.</p>" + lessons.map((l, i) => `<section class="lesson"><h2>${i + 1}. ${l[1]}</h2><p class="ex">${l[2]}</p><p class="small"><a href="${l[3]}">شوفها في الموقع</a>، أو <a href="/glossary/#${l[0]}">في القاموس</a></p></section>`).join("") })); urls.push("/academy/"); }

  // ---- 7e. phase 4 reference pages (research/tifo-2026-09-27 + Arabic from ai/history_ar.py)
  const RS = path.join(process.env.HOME, "workspace/research/tifo-2026-09-27"), HC = path.join(CACHE, "history");
  const rj = (f) => { try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch (e){ return null; } };
  const hl = rj(path.join(HC, "legends.json")) || {}, hm = rj(path.join(HC, "memorable.json")) || {}, ht = rj(path.join(HC, "thisday.json")) || {}, hw = rj(path.join(HC, "laws.json")) || {};
  const legRaw = ((rj(path.join(RS, "legends.json")) || {}).players || []).filter(p => !/Mohamed Salem/i.test(p.name_en || ""));   // ambiguous: waits for the owner
  const memRaw = (rj(path.join(RS, "memorable.json")) || {}).matches || [], tdRaw = (rj(path.join(RS, "thisday.json")) || {}).events || [], lawRaw = (rj(path.join(RS, "laws.json")) || {}).topics || [];
  const refPage = (p, title, desc, h1, lead, body) => { if (!body) return; write(p.slice(1) + "index.html", page({ path:p, page:"ref", title, desc, body:`<h1>${h1}</h1><p class="muted">${lead}</p>` + body })); urls.push(p); };
  refPage("/legends/", "أساطير الكورة الإماراتية | تيفو", "الطلياني وإسماعيل مطر وعمر عبدالرحمن وعلي مبخوت وغيرهم: مسيرتهم وأرقامهم، مع المصادر.", "أساطير الكورة الإماراتية", "مسيرة وأرقام أبرز لاعبين في تاريخ الكورة الإماراتية، وكل معلومة معها مصدرها.", S.legends(legRaw, hl));
  refPage("/memorable/", "مباريات لا تُنسى في تاريخ الكورة الإماراتية | تيفو", "من تصفيات 1990 لين نهائي آسيا 2024: المباريات اللي صنعت تاريخ الكورة الإماراتية.", "مباريات لا تُنسى", "مباريات صنعت تاريخ الكورة الإماراتية، من الأحدث للأقدم.", S.memorable(memRaw, hm));
  refPage("/laws/", "قانون الكورة بالإماراتي: التسلل، اللمسة، البلنتي، الفار | تيفو", "ليش ألغى الحكم الهدف؟ شرح قوانين الكورة الرسمية (IFAB 2026/27) بالإماراتي: التسلل، لمسة اليد، البلنتي، الفار، والوقت بدل الضايع.", "قانون الكورة بالإماراتي", "شرح بسيط لقوانين الكورة من النص الرسمي لـIFAB (نسخة 2026/27)، وتحت كل شرح الجملة الرسمية نفسها.", S.laws(lawRaw, hw));
  const mmddToday = today.slice(5);
  const tdToday = S.thisday(tdRaw, ht, mmddToday, 8);
  const tdAll = [...new Set(tdRaw.map(e => e["mm-dd"]))].sort().map(md => { const x = S.thisday(tdRaw, ht, md, 20); if (!x) return ""; const [mo, dd] = md.split("-").map(Number); return `<section class="blk"><h2>${dd} ${["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"][mo - 1]}</h2>${x}</section>`; }).join("");
  refPage("/thisday/", "هذا اليوم في تاريخ الكورة الإماراتية | تيفو", "كل يوم في السنة وشو صار فيه في تاريخ الكورة الإماراتية: مباريات وبطولات ومواليد الأساطير.", "هذا اليوم في كورة الإمارات", "أحداث من تاريخ الكورة الإماراتية لكل يوم في السنة، ومع كل حدث مصدره.", tdAll);

  if (tdToday){ const hf = path.join(OUT, "index.html"); fs.writeFileSync(hf, fs.readFileSync(hf, "utf8").replace('<h2>البطولات</h2>', S.sec("هذا اليوم في كورة الإمارات", '<a href="/thisday/">كل الأيام</a>', tdToday) + "<h2>البطولات</h2>")); }

  // «اسأل تيفو» (76): only after the owner approves sample answers
  if (APPROVED.ask){ write("ask/index.html", page({ path:"/ask/", page:"ask", title:"اسأل تيفو: أي سؤال عن الكورة الإماراتية | تيفو", desc:"اسأل بالعامية عن الدوري الإماراتي والمنتخب: الترتيب، الهدافين، البطولات، المواجهات. الجواب من بيانات تيفو.",
    body:'<h1>اسأل تيفو</h1><p class="muted">اسأل بالعامية عن الدوري الإماراتي والمنتخب، والجواب من بيانات تيفو بس.</p><form id="askf" class="ask"><input id="askq" maxlength="200" placeholder="مثلاً: متى آخر مرة فاز الوصل على العين؟" aria-label="سؤالك"><button class="btn" type="submit">اسأل</button></form><div id="aska"></div><p class="src">الجواب يكتبه نموذج ذكاء اصطناعي من أرقام تيفو، وممكن يغلط. 25 سؤال باليوم لكل شخص.</p>' })); urls.push("/ask/"); }

  // stadium guide pages (8) + where-to-watch page (7)
  for (const [sid, x] of Object.entries(STAD)){
    const nm = (x.name_ar && x.name_ar.value) || (x.name_en && x.name_en.value) || sid;
    write(`s/${sid}/index.html`, page({ path:`/s/${sid}/`, page:"ref", title:`${nm}: الموقع والمواقف والتذاكر | تيفو`, desc:`دليل ${nm}: السعة والعنوان والخريطة والمواصلات ومنصة التذاكر، من المصادر الرسمية.`, body:`<p class="crumbs"><a href="/stadiums/">الملاعب</a></p><h1>${esc(nm)}</h1>` + S.stadium(x) }));
    urls.push(`/s/${sid}/`);
  }
  if (Object.keys(STAD).length){ write("stadiums/index.html", page({ path:"/stadiums/", page:"ref", title:"دليل ملاعب دوري أدنوك | تيفو", desc:"كل ملاعب دوري أدنوك للمحترفين: السعة والمواقع والمواصلات والتذاكر.", body:'<h1>دليل الملاعب</h1><div class="comps">' + Object.entries(STAD).map(([sid, x]) => `<a href="/s/${sid}/"><span>${esc((x.name_ar && x.name_ar.value) || sid)}</span><span class="muted small num">${x.capacity && x.capacity.value ? Number(x.capacity.value).toLocaleString("en-US") : ""}</span></a>`).join("") + "</div>" })); urls.push("/stadiums/"); }
  const wrows = comps.filter(c => BC[c.id] && BC[c.id].broadcasters && BC[c.id].broadcasters.length).map(c => S.sec(esc(c.name_ar), "", S.watchWhere(BC[c.id]))).join("");
  if (wrows){ write("watch/index.html", page({ path:"/watch/", page:"ref", title:"وين تنقل المباريات في الإمارات: القنوات والباقات والأسعار | تيفو", desc:"كل بطولة وين تنقل في الإمارات: أبوظبي الرياضية، دبي الرياضية، الشارقة الرياضية، beIN، STARZPLAY، شاهد وغيرها، مع المجاني والأسعار.", body:'<h1>وين تنقل المباريات في الإمارات</h1><p class="muted">القنوات والتطبيقات لكل بطولة هالموسم، مع المجاني والأسعار المنشورة ومصدر كل معلومة. تحققنا منها في 27 سبتمبر 2026.</p>' + wrows })); urls.push("/watch/"); }

  // ---- search index (167): clubs, competitions, players, reference pages; loaded only when the visitor opens search
  { const items = []; const seen = new Set(); const add = (t, id, ar, la, u) => { const k = t + id; if (seen.has(k) || !(ar || la)) return; seen.add(k); items.push([t, ar || "", la || "", u]); };
    comps.forEach(c => add("c", c.id, c.name_ar, c.name_en, `/c/${c.key}/`));
    for (const id of teamIds){ const tj = teamsJson.teams[id] || {}; const sm = byTeam.get(id); add("t", id, tj.name_ar || (sm && sm.side.name_ar), tj.name || (sm && sm.side.name), `/t/${id}/`); }
    for (const [pid, p] of Object.entries(allPlayers)) add("p", pid, (NAMES_AR[pid] || {}).ar || "", p.name, `/p/${pid}/`);
    [["legends", "أساطير الكورة الإماراتية"], ["memorable", "مباريات لا تُنسى"], ["thisday", "هذا اليوم في كورة الإمارات"], ["laws", "قانون الكورة: التسلل، لمسة اليد، الفار"], ["watch", "وين تنقل المباريات"], ["stadiums", "دليل الملاعب"], ["week", "مباريات الأسبوع"], ["tv", "شاشة المجلس"], ["studio", "ستوديو التيفو"]].forEach(([k, n]) => add("r", k, n, "", `/${k}/`));
    const sj = JSON.stringify(items); SEARCH_V = hash(sj); fs.writeFileSync(path.join(OUT, `assets/search.${SEARCH_V}.json`), sj); }

  // ---- 8. competitions list, robots, sitemap, 404
  const groups = [["uae", "الإمارات"], ["gulf", "الخليج"], ["asia", "آسيا"], ["national", "المنتخبات"], ["arab", "العرب"], ["europe", "أوروبا"], ["world", "العالم"]];
  write("competitions/index.html", page({ path:"/competitions/", page:"comps", nav:"comps", title:"كل البطولات | تيفو", desc:"كل البطولات اللي يغطيها تيفو: الإماراتية والخليجية والآسيوية والعربية والأوروبية.",
    body:"<h1>البطولات</h1>" + groups.map(g => { const cs = comps.filter(c => c.scope === g[0]); return cs.length ? `<h2>${g[1]}</h2><div class="comps">` + cs.map(c => `<a href="/c/${c.key}/"><span>${esc(c.name_ar)}</span><span class="muted small num">${esc(c.season || "")}</span></a>`).join("") + "</div>" : ""; }).join("") }));
  fs.mkdirSync(path.join(OUT, "og"), { recursive:true }); fs.writeFileSync(path.join(OUT, "og/jobs.json"), JSON.stringify(OGJ));
  try { process.stdout.write(require("child_process").execFileSync("python3", [path.join(__dirname, "og.py")]).toString()); } catch (e){ console.error("og.py failed", e.message); }
  for (const f of ALLP){ const h = fs.readFileSync(f, "utf8"); if (h.includes("__SV__")) fs.writeFileSync(f, h.replace("__SV__", SEARCH_V)); }
  fs.writeFileSync(path.join(OUT, "sw.js"), fs.readFileSync(path.join(__dirname, "src/sw.js"), "utf8").replace("__V__", ASSET_V));
  fs.writeFileSync(path.join(OUT, "robots.txt"), PREVIEW ? "User-agent: *\nDisallow: /\n" : `User-agent: *\nAllow: /\nSitemap: ${SITE}/sitemap.xml\n`);
  fs.writeFileSync(path.join(OUT, "sitemap.xml"), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` + urls.map(u => `<url><loc>${SITE}${u}</loc></url>`).join("\n") + "\n</urlset>\n");
  write("404.html", page({ path:"/404", page:"none", title:"الصفحة مب موجودة | تيفو", desc:"", body:'<h1>الصفحة مب موجودة</h1><p><a href="/">رجوع لمباريات اليوم</a></p>' }));
  fs.writeFileSync(path.join(OUT, ".pages"), String(urls.length));
  console.log(`built ${urls.length} pages: ${comps.length} competitions, ${tcount} teams, ${pcount} players, ${mids.length} matches (${D.size} with detail), logos ${logoIds.size} (${dl} new) in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
})().catch(e => { console.error(e); process.exit(1); });
