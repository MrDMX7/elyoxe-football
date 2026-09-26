/* Build تيفو — static pages prerendered from the /v1 data (docs/SCHEMA.md) with src/render.js, then hydrated by src/app.js.
   node build.cjs [--data https://…cloudfront.net] [--out out] [--preview]
   -> out/index.html, out/c/<key>/, out/m/<id>/, out/t/<id>/, out/uae/, out/competitions/, out/logo/<id>.png, sitemap.xml
   --preview adds noindex (the *.cloudfront.net preview must not be indexed). Logos are cached in cache/logo/ and self-hosted
   (never hotlinked: visitor requests would carry our referer to FotMob). */
"use strict";
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const R = require("./src/render.js");
const args = process.argv.slice(2), arg = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const DATA = (arg("--data", process.env.TIFO_DATA || "https://d1n5aqaqkowltp.cloudfront.net")).replace(/\/$/, "");
const OUT = path.resolve(__dirname, arg("--out", "out")), PREVIEW = args.includes("--preview");
const SITE = "https://tifo.elyoxe.com", CACHE = path.join(__dirname, "cache");
const esc = R.esc;

async function get(p, tries = 3){
  for (let i = 0; i < tries; i++){
    try { const r = await fetch(DATA + "/" + p); if (r.status === 404 || r.status === 403) return null; if (!r.ok) throw new Error(r.status + " " + p); return await r.json(); }
    catch (e){ if (i === tries - 1) { console.error("fetch failed", p, e.message); return null; } await new Promise(s => setTimeout(s, 800 * (i + 1))); }
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
<link rel="stylesheet" href="/assets/tifo.${ASSET_V}.css">${o.ld ? `<script type="application/ld+json">${JSON.stringify(o.ld).replace(/</g, "\\u003c")}</script>` : ""}</head>
<body data-page="${o.page}"${o.attrs || ""}>
<header class="bar"><div class="wrap"><a class="brand" href="/" aria-label="تيفو"><span class="mark" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span>تيفو</a><nav>
<a href="/"${o.nav === "home" ? " aria-current" : ""}>اليوم</a><a href="/c/uae-pro-league/"${o.nav === "538" ? " aria-current" : ""}>دوري أدنوك</a><a href="/uae/"${o.nav === "uae" ? " aria-current" : ""}>المنتخب</a><a href="/c/gulf-cup/"${o.nav === "329" ? " aria-current" : ""}>كأس الخليج</a><a href="/competitions/"${o.nav === "comps" ? " aria-current" : ""}>البطولات</a></nav></div></header>
<main class="wrap">${o.body}</main>
<footer class="foot"><div class="wrap"><span>تيفو، من استوديو <a href="https://elyoxe.com/">Elyoxe</a>. كل المواعيد بتوقيت الإمارات.</span><span class="updated" id="updated"></span><span>البيانات من FotMob ورابطة المحترفين الإماراتية</span></div></footer>
<script src="/assets/colors.__CV__.js"></script><script src="/assets/render.${ASSET_V}.js"></script>${o.page === "home" ? `<script src="/assets/stand.${ASSET_V}.js"></script>` : ""}<script src="/assets/app.${ASSET_V}.js"></script></body></html>`;
}
const tabsHtml = (group, list) => `<div class="tabs" role="tablist" data-tabs="${group}">` + list.map((t, i) => `<button type="button" role="tab" data-t="${t[0]}" aria-selected="${i === 0}">${t[1]}</button>`).join("") + "</div>";
const pane = (group, key, html, first) => `<section data-group="${group}" data-pane="${key}"${first ? "" : " hidden"}>${html}</section>`;

(async () => {
  const t0 = Date.now();
  fs.rmSync(OUT, { recursive:true, force:true }); fs.mkdirSync(path.join(OUT, "assets"), { recursive:true });
  const css = fs.readFileSync(path.join(__dirname, "src/tifo.css"), "utf8"), rjs = fs.readFileSync(path.join(__dirname, "src/render.js"), "utf8"), ajs = fs.readFileSync(path.join(__dirname, "src/app.js"), "utf8"), sjs = fs.readFileSync(path.join(__dirname, "src/stand.js"), "utf8");
  ASSET_V = hash(css + rjs + ajs + sjs);   // content-hashed file names: CloudFront's cache key ignores query strings
  fs.writeFileSync(path.join(OUT, `assets/tifo.${ASSET_V}.css`), css); fs.writeFileSync(path.join(OUT, `assets/render.${ASSET_V}.js`), rjs); fs.writeFileSync(path.join(OUT, `assets/app.${ASSET_V}.js`), ajs); fs.writeFileSync(path.join(OUT, `assets/stand.${ASSET_V}.js`), sjs);
  // the mark: a 3x3 tifo of cards (chalk, pulse, dune on night pitch)
  const cellsSvg = [["#F6F7F2","#10A04B","#B07A3B"],["#F6F7F2","#B07A3B","#10A04B"],["#10A04B","#B07A3B","#F6F7F2"]].map((row, y) => row.map((c, x) => `<rect x="${4 + x * 8.5}" y="${4 + y * 8.5}" width="7" height="7" fill="${c}"/>`).join("")).join("");
  fs.writeFileSync(path.join(OUT, "favicon.svg"), `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="#0A2620"/>${cellsSvg}</svg>`);

  const index = await get("index.json"); if (!index) throw new Error("no index.json from " + DATA);
  const comps = index.competitions, today = new Date(Date.now() + 4 * 3600e3).toISOString().slice(0, 10);
  const urls = ["/", "/uae/", "/competitions/"], teamIds = new Set(), matchSum = new Map(), teamName = new Map();

  // competitions
  const compData = await pool(comps, 6, async c => {
    const [st, fx, stats] = await Promise.all([c.files && c.files.standings ? get(`comp/${c.id}/standings.json`) : null, get(`comp/${c.id}/fixtures.json`), get(`comp/${c.id}/stats.json`)]);
    return { c, st, fx, stats };
  });
  for (const { c, st, fx, stats } of compData){
    (fx && fx.matches || []).forEach(m => { matchSum.set(m.id, m); [m.home, m.away].forEach(t => { if (t && t.id){ teamIds.add(t.id); teamName.set(t.id, t.name_ar || t.name); } }); });
    (st && st.groups || []).forEach(g => g.rows.forEach(r => { teamIds.add(r.team.id); teamName.set(r.team.id, r.team.name_ar || r.team.name); }));
    let rounds = "";
    if (fx && fx.matches && fx.matches.length){ const rr = R.rounds(fx), cur = fx.next_round && rr.by[fx.next_round] ? fx.next_round : (rr.order.find(k => rr.by[k].some(m => m.status !== "finished")) || rr.order[rr.order.length - 1]); rounds = `<div class="chips">` + rr.order.map(k => `<button type="button" data-r="${esc(k)}"${k === cur ? ' aria-pressed="true"' : ""}>${esc(k)}</button>`).join("") + `</div><div id="roundlist">${R.roundList(rr.by[cur] || [])}</div>`; }
    const has = { table: !!(st && st.groups && st.groups.length), stats: !!(stats && stats.lists) };
    const tl = [has.table && ["table", "الترتيب"], ["fixtures", "المباريات"], has.stats && ["goals", "الهدافين"], has.stats && ["assists", "صناع الأهداف"]].filter(Boolean);
    const body = `<p class="crumbs"><a href="/competitions/">البطولات</a></p><h1>${esc(c.name_ar)}</h1><p class="season">الموسم <span class="num">${esc(c.season || "")}</span></p>${c.dormant ? '<p class="note">البطولة متوقفة أو خلصت هالموسم. هذي آخر نتايجها.</p>' : ""}` + tabsHtml("c", tl) +
      (has.table ? pane("c", "table", `<div id="table">${R.standings(st)}</div>`, true) : "") + pane("c", "fixtures", `<div id="rounds">${rounds || '<p class="empty">ما في مباريات منشورة.</p>'}</div>`, !has.table) +
      (has.stats ? pane("c", "goals", `<div id="goals">${R.leaders(stats, "goals")}</div>`) + pane("c", "assists", `<div id="assists">${R.leaders(stats, "assists")}</div>`) : "");
    write(`c/${c.key}/index.html`, page({ path:`/c/${c.key}/`, page:"comp", attrs:` data-comp="${c.id}"`, nav:String(c.id), title:`${c.name_ar}: الترتيب والمباريات والهدافين ${c.season || ""} | تيفو`, desc:`ترتيب ${c.name_ar} ومواعيد المباريات بتوقيت الإمارات والنتايج المباشرة والهدافين وصناع الأهداف، أول بأول.`, body }));
    urls.push(`/c/${c.key}/`);
  }

  // today (home)
  const day = await get(`day/${today.replace(/-/g, "")}.json`) || { matches:[] };
  (day.matches || []).forEach(m => { if (!matchSum.has(m.id)) matchSum.set(m.id, m); [m.home, m.away].forEach(t => { if (t && t.id) teamIds.add(t.id); }); });
  const nav = comps.filter(c => !c.dormant).map(c => `<a href="/c/${c.key}/"><span>${esc(c.name_ar)}</span><span class="muted small num">${esc(c.season || "")}</span></a>`).join("");
  write("index.html", page({ path:"/", page:"home", nav:"home", title:"تيفو — نتايج مباريات اليوم مباشر، الدوري الإماراتي والمنتخب وكل البطولات", desc:"نتايج المباريات مباشر بتوقيت الإمارات: دوري أدنوك، والمنتخب، وكأس الخليج، وأبطال آسيا، والدوريات الكبيرة. الأحداث والتشكيلات والترتيب أول بأول.",
    body:`<section class="stand" id="stand" aria-label="مباراة اليوم"><canvas aria-hidden="true"></canvas><span class="kicker" id="standkick">مباراة اليوم</span><div class="cap" id="standcap">${R.standCap(R.featured(day.matches))}</div></section><div id="mine"></div><div class="daynav"><button type="button" id="prev" aria-label="اليوم اللي قبل">›</button><b id="daytitle">${R.dayNav(today, today)}</b><button type="button" id="next" aria-label="اليوم اللي بعد">‹</button></div><p class="livecount" id="livecount"></p><div id="day">${R.dayList(day.matches, index, { empty:"ما في مباريات اليوم." })}</div><h2>البطولات</h2><div class="comps">${nav}</div>` }));

  // logos (self-hosted copies) + club colours from them, before any page that paints colour
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
  R.setColors(colors); const cjs = "window.TC=" + JSON.stringify(colors) + ";"; COLOR_V = hash(cjs); fs.writeFileSync(path.join(OUT, `assets/colors.${COLOR_V}.js`), cjs);
  for (const f of EARLY) fs.writeFileSync(f, fs.readFileSync(f, "utf8").replace("__CV__", COLOR_V));

  // teams
  const tlist = [...teamIds];
  const full = new Set(index.focus_teams || []); compData.filter(x => x.c.scope === "uae").forEach(x => (x.st && x.st.groups || []).forEach(g => g.rows.forEach(r => full.add(r.team.id))));
  const teams = await pool(tlist, 8, id => full.has(id) ? get(`team/${id}.json`) : null);
  let tcount = 0;
  const byTeam = new Map(); for (const m of matchSum.values()) for (const side of [m.home, m.away]) if (side && side.id){ if (!byTeam.has(side.id)) byTeam.set(side.id, { side, ms:[] }); byTeam.get(side.id).ms.push(m); }
  tlist.forEach((id, i) => {
    let t = teams[i];
    if (!t){ const b = byTeam.get(id); if (!b) return; t = { id, name:b.side.name, name_ar:b.side.name_ar, fixtures:b.ms, squad:[], partial:true }; }
    tcount++;
    const f = R.teamFixtures(t);
    const sub = [t.coach ? `المدرب <span class="lat">${esc(t.coach.name)}</span>` : "", t.venue && t.venue.name ? `الملعب <span class="lat">${esc(t.venue.name)}</span>` : ""].filter(Boolean).join("<br>");
    const body = `<div class="th"><div class="in">${R.logo(t, "lg")}<div><h1>${R.tname(t)}</h1>${sub ? `<p>${sub}</p>` : ""}</div></div>${R.teamStrip(t)}</div>
<div class="btnrow"><button type="button" class="btn" id="mybtn">هذا فريقي</button><a class="btn" href="/v1/team/${t.id}.ics" id="ics">مبارياته في تقويم جوالك</a></div>` +
      tabsHtml("t", [["next", "الياية"], ["past", "النتايج"], ["squad", "اللاعبين"]]) + pane("t", "next", `<div id="next">${f.next.slice(0, 6).map(m => R.matchRow(m, { date:true })).join("") || '<p class="empty">ما في مباريات ياية منشورة.</p>'}</div>`, true) +
      pane("t", "past", `<div id="past">${f.past.slice(0, 10).map(m => R.matchRow(m, { date:true })).join("")}</div>`) + pane("t", "squad", `<div id="squad">${R.squad(t)}</div>`);
    const html = page({ path:`/t/${t.id}/`, page:"team", attrs:` data-id="${t.id}" data-name="${esc(t.name_ar || t.name)}"`, nav:t.id === 5789 ? "uae" : "", title:`${t.name_ar || t.name}: المباريات والنتايج واللاعبين | تيفو`, desc:`مواعيد مباريات ${t.name_ar || t.name} بتوقيت الإمارات، ونتايجه، وقائمة اللاعبين، واشتراك تقويم يتحدّث بروحه.`, body });
    write(`t/${t.id}/index.html`, html); urls.push(`/t/${t.id}/`);
    if (t.id === 5789) write("uae/index.html", html.replace(`<link rel="canonical" href="${SITE}/t/5789/">`, `<link rel="canonical" href="${SITE}/uae/">`));
  });

  // matches: summary for all, full detail where the pipeline has stored it
  const mids = [...matchSum.keys()];
  const withDetail = new Set(mids.filter(id => { const m = matchSum.get(id); return m.status === "finished" || R.isLive(m) || (Date.parse(m.kickoff_utc) - Date.now() < 3 * 864e5 && Date.parse(m.kickoff_utc) > Date.now() - 864e5); }));
  const det = await pool([...withDetail], 8, id => get(`match/${id}.json`, 1));
  const D = new Map(); [...withDetail].forEach((id, i) => { if (det[i]) D.set(id, det[i]); });
  for (const id of mids){
    const md = D.get(id) || matchSum.get(id), ttl = `${R.tname(md.home)} ${md.score ? md.score.home + "-" + md.score.away : "ضد"} ${R.tname(md.away)}`;
    const body = `<div id="mh">${R.matchHead(md)}</div><div id="facts">${R.matchFacts(md, index)}</div>` +
      tabsHtml("m", [["events", "الأحداث"], ["lineups", "التشكيلة"], ["stats", "الإحصائيات"], ["h2h", "المواجهات"]]) +
      pane("m", "events", `<div id="events">${R.events(md)}</div>`, true) + pane("m", "lineups", `<div id="lineups">${R.lineups(md)}</div>`) + pane("m", "stats", `<div id="stats">${R.stats(md)}</div>`) + pane("m", "h2h", `<div id="h2h">${R.h2h(md)}</div>`);
    const ld = { "@context":"https://schema.org", "@type":"SportsEvent", name:`${md.home.name_ar || md.home.name} ضد ${md.away.name_ar || md.away.name}`, startDate:md.kickoff_utc, sport:"Football", homeTeam:{ "@type":"SportsTeam", name:md.home.name_ar || md.home.name }, awayTeam:{ "@type":"SportsTeam", name:md.away.name_ar || md.away.name }, ...(md.venue ? { location:{ "@type":"Place", name:md.venue.name_ar || md.venue.name_en } } : {}) };
    write(`m/${id}/index.html`, page({ path:`/m/${id}/`, page:"match", attrs:` data-id="${id}"`, title:`${ttl} — ${md.comp_name_ar || R.compName(index, md.comp)} | تيفو`, desc:`${R.tname(md.home)} ضد ${R.tname(md.away)} ${R.dayLabel(R.ymd(md.kickoff_uae))} الساعة ${R.hhmm(md.kickoff_uae)} بتوقيت الإمارات: النتيجة المباشرة والأحداث والتشكيلة والإحصائيات والمواجهات السابقة.`, body, ld }));
    urls.push(`/m/${id}/`);
  }

  // competitions list
  const groups = [["uae", "الإمارات"], ["gulf", "الخليج"], ["asia", "آسيا"], ["national", "المنتخبات"], ["arab", "العرب"], ["europe", "أوروبا"], ["world", "العالم"]];
  write("competitions/index.html", page({ path:"/competitions/", page:"comps", nav:"comps", title:"كل البطولات | تيفو", desc:"كل البطولات اللي يغطيها تيفو: الإماراتية والخليجية والآسيوية والعربية والأوروبية.",
    body:"<h1>البطولات</h1>" + groups.map(g => { const cs = comps.filter(c => c.scope === g[0]); return cs.length ? `<h2>${g[1]}</h2><div class="comps">` + cs.map(c => `<a href="/c/${c.key}/"><span>${esc(c.name_ar)}</span><span class="muted small num">${esc(c.season || "")}</span></a>`).join("") + "</div>" : ""; }).join("") }));

  fs.writeFileSync(path.join(OUT, "robots.txt"), PREVIEW ? "User-agent: *\nDisallow: /\n" : `User-agent: *\nAllow: /\nSitemap: ${SITE}/sitemap.xml\n`);
  fs.writeFileSync(path.join(OUT, "sitemap.xml"), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` + urls.map(u => `<url><loc>${SITE}${u}</loc></url>`).join("\n") + "\n</urlset>\n");
  write("404.html", page({ path:"/404", page:"none", title:"الصفحة مب موجودة | تيفو", desc:"", body:'<h1>الصفحة مب موجودة</h1><p><a href="/">رجوع لمباريات اليوم</a></p>' }));
  console.log(`built ${urls.length} pages: ${comps.length} competitions, ${tcount} teams, ${mids.length} matches (${D.size} with detail), logos ${logoIds.size} (${dl} new) in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
})().catch(e => { console.error(e); process.exit(1); });
