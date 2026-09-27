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
function write(rel, html){ const f = path.join(OUT, rel); fs.mkdirSync(path.dirname(f), { recursive:true }); fs.writeFileSync(f, COLOR_V ? html.replace("__CV__", COLOR_V) : html); if (!COLOR_V) EARLY.push(f); }
const EARLY = [];   // pages written before the club colours were known: patched once COLOR_V exists
const hash = s => crypto.createHash("sha1").update(s).digest("hex").slice(0, 10);

let ASSET_V = "", COLOR_V = "";
function page(o){
  const url = SITE + o.path;
  return `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(o.title)}</title><meta name="description" content="${esc(o.desc)}">${PREVIEW ? '<meta name="robots" content="noindex">' : `<link rel="canonical" href="${url}">`}
<meta property="og:title" content="${esc(o.title)}"><meta property="og:description" content="${esc(o.desc)}"><meta property="og:url" content="${url}"><meta property="og:locale" content="ar_AE"><meta name="theme-color" content="#0A2620">
<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700&family=Noto+Kufi+Arabic:wght@800&family=Readex+Pro:wght@400;600&display=swap" rel="stylesheet" media="print" onload="this.media='all'"><noscript><link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700&family=Noto+Kufi+Arabic:wght@800&family=Readex+Pro:wght@400;600&display=swap" rel="stylesheet"></noscript>
<link rel="stylesheet" href="/assets/tifo.${ASSET_V}.css">${o.page === "match" ? '<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"}}</script>' : ""}${o.ld ? `<script type="application/ld+json">${JSON.stringify(o.ld).replace(/</g, "\\u003c")}</script>` : ""}</head>
<body data-page="${o.page}"${o.attrs || ""}>
<header class="bar"><div class="wrap"><a class="brand" href="/" aria-label="تيفو"><span class="mark" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span>تيفو</a><nav>
<a href="/"${o.nav === "home" ? " aria-current" : ""}>اليوم</a><a href="/c/uae-pro-league/"${o.nav === "538" ? " aria-current" : ""}>دوري أدنوك</a><a href="/uae/"${o.nav === "uae" ? " aria-current" : ""}>المنتخب</a><a href="/c/gulf-cup/"${o.nav === "329" ? " aria-current" : ""}>كأس الخليج</a><a href="/competitions/"${o.nav === "comps" ? " aria-current" : ""}>البطولات</a></nav><button type="button" class="spoil" id="spoil" aria-pressed="false" title="يخفي النتايج لين تضغط عليها">بدون حرق</button></div></header>
<main class="wrap">${o.body}</main>
<footer class="foot"><div class="wrap"><span>تيفو، من استوديو <a href="https://elyoxe.com/">Elyoxe</a>. كل المواعيد بتوقيت الإمارات.</span><span><a href="/tv/">شاشة المجلس</a>، <a href="/studio/">ستوديو التيفو</a></span><span class="updated" id="updated"></span><span>البيانات من FotMob ورابطة المحترفين الإماراتية</span></div></footer>
<script src="/assets/colors.__CV__.js"></script><script src="/assets/render.${ASSET_V}.js"></script>${o.page === "home" ? `<script src="/assets/stand.${ASSET_V}.js"></script>` : ""}${o.page === "compare" ? `<script src="/assets/compare.${ASSET_V}.js"></script>` : ""}${["match", "team", "studio"].includes(o.page) ? `<script src="/assets/share.${ASSET_V}.js"></script>` : ""}<script src="/assets/app.${ASSET_V}.js"></script></body></html>`;
}
const tabsHtml = (group, list) => `<div class="tabs" role="tablist" data-tabs="${group}">` + list.map((t, i) => `<button type="button" role="tab" data-t="${t[0]}" aria-selected="${i === 0}">${t[1]}</button>`).join("") + "</div>";
const pane = (group, key, html, first) => `<section data-group="${group}" data-pane="${key}"${first ? "" : " hidden"}>${html}</section>`;

(async () => {
  const t0 = Date.now();
  fs.rmSync(OUT, { recursive:true, force:true }); fs.mkdirSync(path.join(OUT, "assets"), { recursive:true });
  const css = fs.readFileSync(path.join(__dirname, "src/tifo.css"), "utf8"), rjs = fs.readFileSync(path.join(__dirname, "src/render.js"), "utf8"), ajs = fs.readFileSync(path.join(__dirname, "src/app.js"), "utf8"), sjs = fs.readFileSync(path.join(__dirname, "src/stand.js"), "utf8"), cmp = fs.readFileSync(path.join(__dirname, "src/compare.js"), "utf8"), shr = fs.readFileSync(path.join(__dirname, "src/share.js"), "utf8"), p3d = fs.readFileSync(path.join(__dirname, "src/pitch3d.js"), "utf8");
  ASSET_V = hash(css + rjs + ajs + sjs + cmp + shr + p3d); fs.writeFileSync(path.join(OUT, `assets/pitch3d.${ASSET_V}.js`), p3d); fs.writeFileSync(path.join(OUT, `assets/compare.${ASSET_V}.js`), cmp); fs.writeFileSync(path.join(OUT, `assets/share.${ASSET_V}.js`), shr);   // content-hashed file names: CloudFront's cache key ignores query strings
  fs.writeFileSync(path.join(OUT, `assets/tifo.${ASSET_V}.css`), css); fs.writeFileSync(path.join(OUT, `assets/render.${ASSET_V}.js`), rjs); fs.writeFileSync(path.join(OUT, `assets/app.${ASSET_V}.js`), ajs); fs.writeFileSync(path.join(OUT, `assets/stand.${ASSET_V}.js`), sjs);
  // the mark: a 3x3 tifo of cards (chalk, pulse, dune on night pitch)
  const cellsSvg = [["#F6F7F2","#10A04B","#B07A3B"],["#F6F7F2","#B07A3B","#10A04B"],["#10A04B","#B07A3B","#F6F7F2"]].map((row, y) => row.map((c, x) => `<rect x="${4 + x * 8.5}" y="${4 + y * 8.5}" width="7" height="7" fill="${c}"/>`).join("")).join("");
  fs.writeFileSync(path.join(OUT, "favicon.svg"), `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="#0A2620"/>${cellsSvg}</svg>`);

  const index = await get("index.json"); if (!index) throw new Error("no index.json from " + DATA);
  const comps = index.competitions, today = new Date(Date.now() + 4 * 3600e3).toISOString().slice(0, 10);
  const urls = ["/", "/uae/", "/competitions/"], teamIds = new Set(), matchSum = new Map();
  const teamsJson = await get("teams.json"); S.setTeams(teamsJson && teamsJson.teams || {});

  // ---- 1. fetch: competitions (+ every analytics file the pipeline may have written), today, national
  const EXTRA = ["sim", "watch", "bump", "halftime", "xg", "clutch", "cards", "foreigners", "improved", "young-uae", "team-of-round", "minute-clock", "goal-bands", "referees", "lineup-ages", "rotation", "pressure", "style", "fortress", "records", "alltime", "facts", "players", "similar", "tournament-sim", "scenarios", "shots", "fatigue", "coaches"];
  const compData = await pool(comps, 3, async c => {
    const [st, fx, stats] = await Promise.all([c.files && c.files.standings ? get(`comp/${c.id}/standings.json`) : null, get(`comp/${c.id}/fixtures.json`), get(`comp/${c.id}/stats.json`)]);
    const x = {}; await pool(EXTRA, 3, async k => { x[k] = await get(`comp/${c.id}/${k}.json`, 2); });
    return { c, st, fx, stats, x };
  });
  const day = await get(`day/${today.replace(/-/g, "")}.json`) || { matches:[] };
  const [ratings, compare, fifa, qual, abroad, natRatings] = await Promise.all(["ratings/uae-clubs.json", "leagues/compare.json", "national/5789/fifa.json", "national/5789/qualifying.json", "national/uae-abroad.json", "ratings/national.json"].map(f => get(f, 1)));
  const h2hIdx = await get("h2h/index.json", 1), h2hKeys = h2hIdx ? Object.keys(h2hIdx.pairs) : [];
  const h2hData = await pool(h2hKeys, 8, k => get(`h2h/${k}.json`, 1)), H2H = {}; h2hKeys.forEach((k, i) => { if (h2hData[i]) H2H[k] = h2hData[i]; });
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
  const cjs = "window.TC=" + JSON.stringify(colors) + ";window.H2HK=" + JSON.stringify(R.H2HK) + ";"; COLOR_V = hash(cjs); fs.writeFileSync(path.join(OUT, `assets/colors.${COLOR_V}.js`), cjs);

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
    const tablePane = has.table ? (vars.length ? `<div class="tabs" data-tabs="tv"><button type="button" data-t="all" aria-selected="true">الكل</button>` + vars.map(v => `<button type="button" data-t="${v[0]}" aria-selected="false">${v[1]}</button>`).join("") + "</div>" + pane("tv", "all", `<div id="table">${R.standings(st)}</div>`, true) + vars.map(v => pane("tv", v[0], v[2])).join("") : `<div id="table">${R.standings(st)}</div>`) + (x.bump ? S.sec("رحلة الموسم", "", S.bump(x.bump)) : "") : "";
    // predictions (93, 20, 136)
    const pred = [x.watch && fx ? S.sec("أحلى مباريات الجولة الياية", "", S.watch(x.watch, fx)) : "", S.whatif(fx, st) ? S.sec("شو لو؟", "", S.whatif(fx, st)) : "", x.sim && x.sim.teams ? S.sec("توقعات آخر الموسم", "", S.sim(x.sim, st)) : "", st && st.magic ? S.sec("كم يحتاج فريقك؟", "", S.magic(st)) : "", x["tournament-sim"] ? S.sec("من بيفوز بالبطولة؟", "", S.tsim(x["tournament-sim"])) : ""].join("");
    // the numbers (137, 135, 46, 124, 119, 129, 139, 52, 37, 142, 143, 96, 138, 141)
    const num = [
      ["cards", "بطاقات تيفو", S.cards(x.cards, 12)], ["clutch", "منو الحاسم؟", S.clutch(x.clutch)], ["tor", "تشكيلة الجولة", S.teamOfRound(x["team-of-round"])],
      ["foreign", "أفضل محترف أجنبي", S.foreigners(x.foreigners)], ["improved", "الأكثر تطوّر", S.improved(x.improved)], ["young", "المواهب الإماراتية تحت 23", S.young(x["young-uae"])],
      ["clock", "ساعة الأهداف", S.clock(x["minute-clock"])], ["late", "ملوك الدقايق الأخيرة", S.late(x["goal-bands"])],
      ["pressure", "ترمومتر المدربين", S.pressure(x.pressure)], ["style", "بصمة كل فريق", S.style(x.style)], ["fortress", "حصون الملاعب", S.fortress(x.fortress)],
      ["fatigue", "مؤشر الإرهاق", S.fatigue(x.fatigue)], ["coaches", "أنجح المدربين في التاريخ", S.coachesLeague(x.coaches)],
      ["refs", "الحكام", S.referees(x.referees)], ["ages", "أعمار التشكيلات", S.ages(x["lineup-ages"])], ["rot", "مؤشر التدوير", S.rotation(x.rotation)],
      ["rating", "تصنيف تيفو للأندية", c.id === 538 ? S.ratingTable(ratings) : ""], ["world", "الدوري الإماراتي ضد العالم", c.id === 538 ? S.compare(compare, 538) : ""],
    ].filter(v => v[2]);
    const cmpLink = x.cards ? `<p><a class="btn" href="/c/${c.key}/compare/">قارن بين لاعبين أو فريقين</a></p>` : "";
    const numPane = num.length ? cmpLink + `<nav class="chips secnav">` + num.map(v => `<a href="#n-${v[0]}">${v[1]}</a>`).join("") + "</nav>" + num.map(v => S.sec(v[1], "", v[2], "n-" + v[0])).join("") : "";
    const derb = c.id === 538 ? S.derbyList(h2hIdx, H2H) : "";
    const hist = (x.alltime ? S.sec("تاريخ الدوري", "من 1973", S.alltime(x.alltime)) : "") + (derb ? S.sec("سجل المواجهات بين الأندية", "", derb) : "") + (x.records && x.records.chases && x.records.chases.length ? S.sec("أرقام قياسية على المحك", "", S.records(x.records)) : "");
    const tl = [has.table && ["table", "الترتيب"], ["fixtures", "المباريات"], pred && ["pred", "التوقعات"], numPane && ["num", "الأرقام"], has.stats && ["goals", "الهدافين"], has.stats && ["assists", "صناع الأهداف"], hist && ["hist", "التاريخ"]].filter(Boolean);
    const body = `<p class="crumbs"><a href="/competitions/">البطولات</a></p><h1>${esc(c.name_ar)}</h1><p class="season">الموسم <span class="num">${esc(c.season || "")}</span></p>${c.dormant ? '<p class="note">البطولة متوقفة أو خلصت هالموسم. هذي آخر نتايجها.</p>' : ""}` + tabsHtml("c", tl) +
      (has.table ? pane("c", "table", tablePane, true) : "") + pane("c", "fixtures", `<div id="rounds">${rounds || '<p class="empty">ما في مباريات منشورة.</p>'}</div>`, !has.table) +
      (pred ? pane("c", "pred", pred) : "") + (numPane ? pane("c", "num", numPane) : "") +
      (has.stats ? pane("c", "goals", `<div id="goals">${R.leaders(stats, "goals")}</div>`) + pane("c", "assists", `<div id="assists">${R.leaders(stats, "assists")}</div>`) : "") + (hist ? pane("c", "hist", hist) : "");
    write(`c/${c.key}/index.html`, page({ path:`/c/${c.key}/`, page:"comp", attrs:` data-comp="${c.id}"`, nav:String(c.id), title:`${c.name_ar}: الترتيب والمباريات والتوقعات ${c.season || ""} | تيفو`, desc:`ترتيب ${c.name_ar} ومواعيد المباريات بتوقيت الإمارات والنتايج المباشرة، وتوقعات آخر الموسم، والهدافين وبطاقات اللاعبين والأرقام.`, body }));
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
    body:`<section class="stand" id="stand" aria-label="مباراة اليوم"><canvas aria-hidden="true"></canvas><span class="kicker" id="standkick">مباراة اليوم</span><div class="cap" id="standcap">${R.standCap(R.featured(day.matches))}</div></section><div id="uaecd"></div><div class="tools"><a class="btn" href="/tv/">شاشة المجلس</a><a class="btn" href="/studio/">ستوديو التيفو</a></div><div id="mine"></div><div class="daynav"><button type="button" id="prev" aria-label="اليوم اللي قبل">›</button><b id="daytitle">${R.dayNav(today, today)}</b><button type="button" id="next" aria-label="اليوم اللي بعد">‹</button></div><p class="livecount" id="livecount"></p><div id="day">${R.dayList(day.matches, index, { empty:"ما في مباريات اليوم." })}</div>${watchHome}<h2>البطولات</h2><div class="comps">${nav}</div>` }));

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
    const sub = [t.coach ? `المدرب <span class="lat">${esc(t.coach.name)}</span>` : "", t.venue && t.venue.name ? `الملعب <span class="lat">${esc(t.venue.name)}</span>` : ""].filter(Boolean).join("<br>");
    // the club in numbers (91, 36, 96, 135, 137, 141)
    let nums = "";
    if (rhist[i]) nums += S.sec("تصنيف تيفو عبر السنين", "", S.ratingChart(rhist[i], id));
    const row = st538 && st538.st && st538.st.groups[0].rows.find(r => r.team.id === id);
    if (row && row.last_season_same_round){ const l = row.last_season_same_round; nums += S.sec("هالموسم ضد الموسم الماضي", `بعد ${row.played} جولات`, `<div class="pstats"><div><b>${row.pts}</b><span>نقاطه الحين</span></div><div><b>${l.pts}</b><span>نفس الوقت الموسم الماضي</span></div><div><b><bdi dir="ltr">${row.pts - l.pts > 0 ? "+" : ""}${row.pts - l.pts}</bdi></b><span>الفرق</span></div><div><b>${row.gf} - ${row.ga}</b><span>أهدافه الحين</span></div><div><b>${l.gf} - ${l.ga}</b><span>الموسم الماضي</span></div></div>`); }
    if (x538.pressure && x538.pressure.teams && x538.pressure.teams[id]){ const pr = { teams:{} }; pr.teams[id] = x538.pressure.teams[id]; nums += S.sec("الضغط على المدرب", "", S.pressure(pr)); }
    const tc = x538.cards ? S.cards(x538.cards, 11, c => c.team === id) : ""; if (tc) nums += S.sec("بطاقات تيفو للاعبين", "", tc);
    if (x538.clutch && x538.clutch.players){ const cl = S.clutch({ players:x538.clutch.players.filter(p => p.team === id) }); if (cl) nums += S.sec("منو الحاسم في الفريق؟", "", cl); }
    const ln = S.loans(t); if (ln) nums += S.sec("لاعبينه المعارين", "", ln);
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
    }
    const tabs = [["next", "الياية"], ["past", "النتايج"], ["squad", "اللاعبين"], nums && ["nums", id === 5789 ? "المنتخب بالأرقام" : "بالأرقام"]].filter(Boolean);
    const body = `<div class="th"><div class="in">${R.logo(t, "lg")}<div><h1>${R.tname(t)}</h1>${sub ? `<p>${sub}</p>` : ""}</div></div>${R.teamStrip(t)}</div>
<div class="btnrow"><button type="button" class="btn" id="mybtn">هذا فريقي</button><a class="btn" href="/v1/team/${t.id}.ics" id="ics">مبارياته في تقويم جوالك</a><button type="button" class="btn" id="wpbtn" hidden>خلفية للجوال</button></div>${t.id === 5789 ? '<div id="uaecd"></div>' : ""}` +
      tabsHtml("t", tabs) + pane("t", "next", `<div id="next">${f.next.slice(0, 6).map(m => R.matchRow(m, { date:true })).join("") || '<p class="empty">ما في مباريات ياية منشورة.</p>'}</div>`, true) +
      pane("t", "past", `<div id="past">${f.past.slice(0, 10).map(m => R.matchRow(m, { date:true })).join("")}</div>`) + pane("t", "squad", `<div id="squad">${R.squad(t)}</div>`) + (nums ? pane("t", "nums", nums) : "");
    const html = page({ path:`/t/${t.id}/`, page:"team", attrs:` data-id="${t.id}" data-name="${esc(t.name_ar || t.name)}"`, nav:t.id === 5789 ? "uae" : "", title:`${t.name_ar || t.name}: المباريات والنتايج واللاعبين | تيفو`, desc:`مواعيد مباريات ${t.name_ar || t.name} بتوقيت الإمارات، ونتايجه، وقائمة اللاعبين، وأرقامه، واشتراك تقويم يتحدّث بروحه.`, body });
    write(`t/${t.id}/index.html`, html); urls.push(`/t/${t.id}/`);
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
    const pre = (probs ? S.probs(probs, md) : "") + (fa ? S.sec("ضغط المباريات", "", fa) : "") + (facts && facts.length ? S.sec("قبل المباراة", "", S.matchFacts(facts)) : "");
    const body = `<div id="mh">${R.matchHead(md)}</div><div class="tools"><button type="button" class="btn" id="storybtn">صورة للستوري</button><a class="btn" href="/tv/?m=${id}">على شاشة المجلس</a></div><script type="application/json" id="msum">${JSON.stringify(Object.assign({}, sum, { events:undefined, lineups:undefined, stats:undefined, h2h:undefined })).replace(/</g, "\\u003c")}</script><div id="catchup">${R.catchup(md)}</div><div id="facts">${R.matchFacts(md, index)}</div>${pre}` +
      tabsHtml("m", [["events", "الأحداث"], ["lineups", "التشكيلة"], ["stats", "الإحصائيات"], ["h2h", "المواجهات"]]) +
      pane("m", "events", `<div id="events">${R.events(md)}</div>`, true) + pane("m", "lineups", `<div class="tools"><button type="button" class="btn" id="p3dbtn" data-src="/assets/pitch3d.${ASSET_V}.js"${md.lineups && md.lineups.home ? "" : " hidden"}>شوفها على ملعب ثلاثي الأبعاد</button></div><div id="p3d"></div><div id="lineups">${R.lineups(md)}</div>`) + pane("m", "stats", `<div id="stats">${R.stats(md)}</div>`) + pane("m", "h2h", `<div id="h2h">${R.h2h(md)}</div>`);
    const ld = { "@context":"https://schema.org", "@type":"SportsEvent", name:`${md.home.name_ar || md.home.name} ضد ${md.away.name_ar || md.away.name}`, startDate:md.kickoff_utc, sport:"Football", homeTeam:{ "@type":"SportsTeam", name:md.home.name_ar || md.home.name }, awayTeam:{ "@type":"SportsTeam", name:md.away.name_ar || md.away.name }, ...(md.venue ? { location:{ "@type":"Place", name:md.venue.name_ar || md.venue.name_en } } : {}) };
    write(`m/${id}/index.html`, page({ path:`/m/${id}/`, page:"match", attrs:` data-id="${id}"`, title:`${ttl} — ${md.comp_name_ar || R.compName(index, md.comp)} | تيفو`, desc:`${R.tname(md.home)} ضد ${R.tname(md.away)} ${R.dayLabel(R.ymd(md.kickoff_uae))} الساعة ${R.hhmm(md.kickoff_uae)} بتوقيت الإمارات: النتيجة المباشرة والأحداث والتشكيلة والإحصائيات والمواجهات السابقة.`, body, ld }));
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

  // ---- 8. competitions list, robots, sitemap, 404
  const groups = [["uae", "الإمارات"], ["gulf", "الخليج"], ["asia", "آسيا"], ["national", "المنتخبات"], ["arab", "العرب"], ["europe", "أوروبا"], ["world", "العالم"]];
  write("competitions/index.html", page({ path:"/competitions/", page:"comps", nav:"comps", title:"كل البطولات | تيفو", desc:"كل البطولات اللي يغطيها تيفو: الإماراتية والخليجية والآسيوية والعربية والأوروبية.",
    body:"<h1>البطولات</h1>" + groups.map(g => { const cs = comps.filter(c => c.scope === g[0]); return cs.length ? `<h2>${g[1]}</h2><div class="comps">` + cs.map(c => `<a href="/c/${c.key}/"><span>${esc(c.name_ar)}</span><span class="muted small num">${esc(c.season || "")}</span></a>`).join("") + "</div>" : ""; }).join("") }));
  fs.writeFileSync(path.join(OUT, "robots.txt"), PREVIEW ? "User-agent: *\nDisallow: /\n" : `User-agent: *\nAllow: /\nSitemap: ${SITE}/sitemap.xml\n`);
  fs.writeFileSync(path.join(OUT, "sitemap.xml"), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` + urls.map(u => `<url><loc>${SITE}${u}</loc></url>`).join("\n") + "\n</urlset>\n");
  write("404.html", page({ path:"/404", page:"none", title:"الصفحة مب موجودة | تيفو", desc:"", body:'<h1>الصفحة مب موجودة</h1><p><a href="/">رجوع لمباريات اليوم</a></p>' }));
  fs.writeFileSync(path.join(OUT, ".pages"), String(urls.length));
  console.log(`built ${urls.length} pages: ${comps.length} competitions, ${tcount} teams, ${pcount} players, ${mids.length} matches (${D.size} with detail), logos ${logoIds.size} (${dl} new) in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
})().catch(e => { console.error(e); process.exit(1); });
