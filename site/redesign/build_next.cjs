/* تيفو v3 prototype build (redesign/DESIGN-v3.md). A SEPARATE build: it never touches build.cjs, src/*, deploy.sh or ai/*;
   it requires src/render.js + src/stats.js read-only (through redesign/src/rx.js) and writes only to site/out_next/next/.
   node redesign/build_next.cjs [--data https://tifo.elyoxe.com/v1]
   Pages: /next/ · /next/m/1000020522/ · /next/m/6052085/ · /next/c/uae-pro-league/ · /next/c/saudi-pro-league/
   Every page: noindex, no service worker, assets under /next/assets/, crests under /next/logo/ (copied from cache/logo, read-only).
   Home editorial blocks that come from build_arabs.cjs / post-build patches are lifted from the snapshot of the current home
   (redesign/snap/old/index.html) by <h2>; rollout turns them into proper slot renderers. */
"use strict";
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const SITE = path.resolve(__dirname, ".."), HERE = __dirname, CACHE = path.join(SITE, "cache");
const R = require("./src/rx.js"), S = require("../src/stats.js");
const args = process.argv.slice(2), arg = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const DATA = arg("--data", "https://tifo.elyoxe.com/v1").replace(/\/$/, ""), OUT = path.join(SITE, "out_next/next"), BASE = "/next/";
const esc = R.esc, hash = s => crypto.createHash("sha1").update(s).digest("hex").slice(0, 10);
const MATCHES = [1000020522, 6052085], COMPS_ARG = (arg => arg ? arg.split(",") : null)((process.argv.find(a => a.startsWith("--comps=")) || "").slice(8));

async function get(p, tries = 3){
  for (let i = 0; i < tries; i++){
    try { const r = await fetch(DATA + "/" + p, { signal:AbortSignal.timeout(25000) }); if (r.status === 404 || r.status === 403) return null; if (!r.ok) throw new Error(r.status + " " + p); return await r.json(); }
    catch (e){ if (i === tries - 1){ console.error("fetch failed", p, e.message); return null; } await new Promise(s => setTimeout(s, 1200 * (i + 1))); }
  }
}
async function pool(items, n, fn){ const out = new Array(items.length); let i = 0; await Promise.all(Array.from({ length:n }, async () => { while (i < items.length){ const k = i++; out[k] = await fn(items[k], k); } })); return out; }
const readJ = (f, d) => { try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch (e){ return d; } };
const RSD = path.join(process.env.HOME, "workspace/research/tifo-2026-09-27"), readRes = f => readJ(path.join(RSD, f), {});

// ---- split rendered HTML into its <section class="blk"> blocks (depth-counted), keeping what sits between them
function blocks(html){
  const out = [], rest = []; let i = 0;
  while (i < html.length){
    const s = html.indexOf('<section class="blk"', i); if (s < 0){ rest.push(html.slice(i)); break; }
    rest.push(html.slice(i, s)); let d = 0, j = s; const re = /<(\/?)section\b[^>]*>/g; re.lastIndex = s; let m;
    while ((m = re.exec(html))){ d += m[1] ? -1 : 1; if (!d){ j = re.lastIndex; break; } }
    const full = html.slice(s, j), h2 = (full.match(/<h2>([\s\S]*?)<\/h2>/) || [])[1] || "";
    const title = h2.replace(/<small>[\s\S]*<\/small>/, "").replace(/<[^>]+>/g, "").trim(), sub = (h2.match(/<small>([\s\S]*)<\/small>/) || [])[1] || "";
    const id = (full.match(/^<section class="blk" id="([^"]+)"/) || [])[1] || "";
    out.push({ title, sub, id, full, inner:full.replace(/^<section[^>]*>\s*<h2>[\s\S]*?<\/h2>/, "").replace(/<\/section>$/, "") }); i = j;
  }
  return { secs:out, rest:rest.join("") };
}
// ids that app.js wires once at start-up: a section holding one stays live DOM (moved into the panel), never a <template>
const LIVE_IDS = ["whatif", "rpbtn", "rpreds", "rpr", "rpev", "wwbox", "kitct", "bdays", "storydata", "commbtn"];
const isLive = h => LIVE_IDS.some(id => h.includes('id="' + id + '"'));
const strip = h => h.replace(/<(script|style|template)[\s\S]*?<\/\1>/g, "").replace(/<[^>]+>/g, " ").replace(/&[a-z#0-9]+;/g, " ").replace(/\s+/g, " ").trim();
function teaser(sec){ const m = sec.inner.match(/<(li|p)\b[^>]*>([\s\S]*?)<\/\1>/); let t = m ? strip(m[2]) : ""; if (!t || t.length < 8) return ""; return t.length > 90 ? t.slice(0, 88).replace(/\s\S*$/, "") + "…" : t; }
// the tile's small tifo: 3x3 cards in club colours (never pulse/dune: those mean live and my team)
let PALETTE = [["#5C6660", "#F6F7F2"]];
function tifoIcon(seed){ let s = 7; for (const ch of seed) s = (s * 31 + ch.charCodeAt(0)) % 2147483647; const rnd = () => { s = (s * 16807) % 2147483647; return s / 2147483647; };
  const a = PALETTE[Math.floor(rnd() * PALETTE.length)], b = PALETTE[Math.floor(rnd() * PALETTE.length)];
  return '<span class="ti" aria-hidden="true">' + Array.from({ length:9 }, (_, i) => `<i style="background:${[a[0], a[1], b[0]][Math.floor(rnd() * 3)] || a[0]}"></i>`).join("") + "</span>"; }
// a shelf: tiles that open the reader panel. Templated content by default; live DOM for sections app.js wires at start-up.
let SEQ = 0;
function shelf(secs, o){
  o = o || {}; if (!secs.length) return "";
  const vault = [];
  const tiles = secs.map(sc => {
    const key = sc.id || "s" + (++SEQ), live = isLive(sc.full), body = `<div class="pbody" data-title="${esc(sc.title)}">${sc.full}</div>`;
    vault.push(live ? `<div class="vault" id="v-${key}" hidden>${body}</div>` : `<template id="v-${key}">${body}</template>`);
    const tz = teaser(sc);
    return `<button type="button" class="sht" data-open="${key}"${sc.id ? ` data-anchor="${sc.id}"` : ""}>${tifoIcon(sc.title)}<span class="tt2">${esc(sc.title)}</span>${tz ? `<span class="tz">${esc(tz)}</span>` : sc.sub ? `<span class="tz">${sc.sub.replace(/<a[\s\S]*?<\/a>/g, "").replace(/<[^>]+>/g, "")}</span>` : ""}</button>`;
  });
  return `<div class="shelf-h"><h3>${o.title || "بعد في هالتبويب"}</h3><span class="muted small num">${secs.length}</span></div><div class="shelf3">${tiles.join("")}</div>${vault.join("")}`;
}
const tabsBar = (group, list) => `<div class="tabs mtabs" role="tablist" data-tabs="${group}" data-slot="tabs">` + list.map((t, i) => `<button type="button" role="tab" data-t="${t[0]}" aria-selected="${i === 0}">${t[1]}</button>`).join("") + "</div>";
const segBar = (group, list) => `<div class="tabs seg" role="tablist" data-tabs="${group}">` + list.map((t, i) => `<button type="button" role="tab" data-t="${t[0]}" aria-selected="${i === 0}">${t[1]}</button>`).join("") + "</div>";
const pane = (group, key, html, first) => `<section data-group="${group}" data-pane="${key}" data-slot="tab:${key}"${first ? "" : " hidden"}>${html}</section>`;

// ---- icons (inline SVG, stroke = currentColor)
const IC = {
  today:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
  comps:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>',
  nat:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 21V4h11l-2 4 2 4H5"/></svg>',
  week:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 18h3V9H4zM10.5 18h3V5h-3zM17 18h3v-6h-3z"/></svg>',
  more:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="4" height="4"/><rect x="10" y="4" width="4" height="4"/><rect x="16" y="4" width="4" height="4"/><rect x="4" y="10" width="4" height="4"/><rect x="10" y="10" width="4" height="4"/><rect x="16" y="10" width="4" height="4"/></svg>',
  search:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/></svg>',
  share:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 8l5-5 5 5M5 13v8h14v-8"/></svg>',
};

let ASSET = { css:"", js:"" }, SEARCH_V = "", BC_V = "", COLOR_F = "", PNAMES = {};
function page(o){
  const nav = [["home", BASE, "اليوم", IC.today], ["comps", "/competitions/", "البطولات", IC.comps], ["nat", "/national/", "المنتخبات", IC.nat], ["week", "/week/", "الأسبوع", IC.week]];
  const navHtml = nav.map(n => `<a href="${n[1]}"${o.nav === n[0] ? ' aria-current="page"' : ""}>${n[3]}<span>${n[2]}</span></a>`).join("") + `<button type="button" data-sheet="more" aria-haspopup="dialog">${IC.more}<span>المزيد</span></button>`;
  const shareSheet = `<div class="sheet" id="share" data-slot="sheet" role="dialog" aria-modal="true" aria-label="شارك وأدوات" hidden><div class="sh-in"><div class="sh-h"><h2>شارك وأدوات</h2><button type="button" class="x" data-close aria-label="سكّر">سكّر</button></div>
<div class="sh-g"><button type="button" class="sa" id="copylink">انسخ الرابط</button><button type="button" class="sa" id="nshare">شارك الصفحة</button>${o.tools || ""}<button type="button" class="sa" id="secpick">صورة لأي قسم</button></div><div id="secpicks" class="sh-list" hidden></div></div></div>`;
  const G = (t, items) => `<div class="mg"><h3>${t}</h3><div class="ml">${items.join("")}</div></div>`, L = (h, t) => `<a href="${h}">${t}</a>`;
  const moreSheet = `<div class="sheet" id="more" data-slot="more" role="dialog" aria-modal="true" aria-label="المزيد" hidden><div class="sh-in"><div class="sh-h"><h2>المزيد</h2><button type="button" class="x" data-close aria-label="سكّر">سكّر</button></div>
<div class="mset"><button type="button" class="spoil sa" id="ctry" title="بلدك: التوقيت وترتيب المباريات">بلدك</button><button type="button" class="spoil sa" id="spoil" aria-pressed="false" title="يخفي النتايج لين تضغط عليها">بدون حرق</button><button type="button" class="spoil sa" id="carbtn">وضع السيارة</button></div>
${G("اختصارات", [L("/c/uae-pro-league/", "دوري أدنوك"), L("/uae/", "المنتخب"), L("/c/gulf-cup/", "كأس الخليج"), L("/today/", "مباريات اليوم"), L("/tomorrow/", "مباريات بكرة"), L("/week/", "مباريات الأسبوع"), L("/countdowns/", "كم باقي؟")])}
${G("الشاشات", [L("/tv/", "شاشة المجلس"), L("/w/", "وضع المتابعة"), L("/watch/", "وين تنقل"), L("/stadiums/", "الملاعب")])}
${G("اقرا وتعلّم", [L("/legends/", "الأساطير"), L("/memorable/", "مباريات لا تُنسى"), L("/thisday/", "هذا اليوم"), L("/laws/", "قانون الكورة"), L("/academy/", "الأكاديمية"), L("/glossary/", "القاموس")])}
${G("سوّ بنفسك", [L("/studio/", "ستوديو التيفو"), L("/lab/", "المختبر"), L("/ask/", "اسأل تيفو"), L("/cast/", "تيفو كاست"), L("/newsletter/", "النشرة")])}</div></div>`;
  return `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>${esc(o.title)}</title><meta name="description" content="${esc(o.desc)}"><meta name="robots" content="noindex"><meta name="theme-color" content="#0A2620">
<link rel="icon" href="${BASE}favicon.svg" type="image/svg+xml"><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700&family=Noto+Kufi+Arabic:wght@800&family=Readex+Pro:wght@400;600&display=swap" rel="stylesheet" media="print" onload="this.media='all'"><noscript><link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700&family=Noto+Kufi+Arabic:wght@800&family=Readex+Pro:wght@400;600&display=swap" rel="stylesheet"></noscript>
<link rel="stylesheet" href="${BASE}assets/next.${ASSET.css}.css">${o.page === "match" ? '<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"}}</script>' : ""}${(o.ld ? [].concat(o.ld) : []).map(l => `<script type="application/ld+json">${JSON.stringify(l).replace(/</g, "\\u003c")}</script>`).join("")}</head>
<body class="v3" data-page="${o.page}" data-bc="${BC_V}"${o.attrs || ""}>
<a class="skip" href="#main">تخطَّ للمحتوى</a>
<header class="top" data-slot="nav"><div class="wrap"><a class="brand" href="${BASE}" aria-label="تيفو"><span class="mark" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span>تيفو</a><nav class="pnav" aria-label="الأقسام">${navHtml}</nav><div class="acts"><button type="button" class="ib" id="srch" aria-label="بحث" data-v="${SEARCH_V}">${IC.search}<span class="vh">بحث</span></button><button type="button" class="ib" data-sheet="share" aria-haspopup="dialog" aria-label="شارك">${IC.share}<span class="vh">شارك</span></button></div></div></header>
<main id="main">${o.body}</main>
<footer class="foot" data-slot="footer"><div class="wrap"><div class="fbrand"><span class="mark" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span><span>تيفو، من استوديو <a href="https://elyoxe.com/">Elyoxe</a>. المواعيد بتوقيت بلدك.</span></div>
<div class="fl"><a href="/tv/">شاشة المجلس</a><a href="/studio/">ستوديو التيفو</a><a href="/week/">مباريات الأسبوع</a><a href="/legends/">الأساطير</a><a href="/memorable/">مباريات لا تُنسى</a><a href="/thisday/">هذا اليوم</a><a href="/laws/">قانون الكورة</a><a href="/watch/">وين تنقل</a><a href="/stadiums/">الملاعب</a><a href="/lab/">المختبر</a><a href="/academy/">الأكاديمية</a><a href="/glossary/">القاموس</a><a href="/w/">وضع المتابعة</a><a href="/countdowns/">كم باقي؟</a><a href="/newsletter/">النشرة</a></div>
<p class="small muted"><span class="updated" id="updated"></span> البيانات من FotMob ورابطة المحترفين الإماراتية. <span class="pv">نسخة تجريبية من التصميم اليديد.</span></p></div></footer>
<nav class="tabbar" aria-label="الأقسام" data-slot="nav">${navHtml}</nav>
${shareSheet}${moreSheet}
<div class="panel" id="panel" role="dialog" aria-modal="true" aria-labelledby="panelt" hidden><div class="pn-in"><div class="pn-h"><h2 id="panelt"></h2><span class="pn-sub" id="panels"></span><button type="button" class="x" data-close aria-label="سكّر">سكّر</button></div><div class="pn-b" id="panelb"></div></div></div>
<div class="scrimall" id="scrimall" hidden></div>
<script>window.PN=${JSON.stringify(o.names || {}).replace(/</g, "\\u003c")}</script><script src="${BASE}assets/${COLOR_F}"></script><script src="${BASE}assets/next.${ASSET.js}.js"></script></body></html>`;
}
function write(rel, html){
  // links to the other prototype pages stay inside /next/
  html = html.replace(/href="(\/(?:m\/(?:1000020522|6052085)|c\/[a-z0-9-]+|competitions))\/(#[^"]*)?"/g, (m, p, h) => `href="${BASE.slice(0, -1)}${p}/${h || ""}"`);
  const f = path.join(OUT, rel); fs.mkdirSync(path.dirname(f), { recursive:true }); fs.writeFileSync(f, html);
}

(async () => {
  const t0 = Date.now();
  fs.rmSync(OUT, { recursive:true, force:true }); fs.mkdirSync(path.join(OUT, "assets"), { recursive:true }); fs.mkdirSync(path.join(OUT, "logo"), { recursive:true });
  const index = await get("index.json"); if (!index) throw new Error("no index.json");
  const comps = index.competitions, COMPS = COMPS_ARG || comps.map(c => c.key), today = new Date(Date.now() + 4 * 3600e3).toISOString().slice(0, 10);
  const teamsJson = await get("teams.json") || { teams:{} }; S.setTeams(teamsJson.teams || {});
  const colors = readJ(path.join(CACHE, "colors.json"), {}); R.setColors(colors);
  // competition logos (redesign/league_logos.py: FotMob league crests, dark variant preferred, own cache) + their colours
  try { require("child_process").execFileSync("python3", [path.join(HERE, "league_logos.py"), ...index.competitions.map(c => String(c.id))], { stdio:"ignore" }); } catch (e){ console.error("league_logos.py failed: mosaic fallback"); }
  const LCOL = readJ(path.join(HERE, "cache/league_colors.json"), {}), LOGO = id => fs.existsSync(path.join(HERE, "cache/leaguelogo", id + ".png"));
  fs.mkdirSync(path.join(OUT, "lg"), { recursive:true }); for (const c of index.competitions) if (LOGO(c.id)) fs.copyFileSync(path.join(HERE, "cache/leaguelogo", c.id + ".png"), path.join(OUT, "lg", c.id + ".png"));
  // the glow colour: the most saturated of the two, else chalk (a white crest glows white)
  const sat = h => { const n = parseInt(h.slice(1), 16), r = n >> 16, g = n >> 8 & 255, b = n & 255, mx = Math.max(r, g, b), mn = Math.min(r, g, b); return mx ? (mx - mn) / mx : 0; };
  const glow = id => { const cs = (LCOL[id] || []).slice().sort((a, b) => sat(b) - sat(a)); return [cs[0] && sat(cs[0]) > .25 ? cs[0] : "#F6F7F2", cs[1] && sat(cs[1]) > .25 ? cs[1] : (cs[0] && sat(cs[0]) > .25 ? cs[0] : "#5C7A70")]; };
  const NAMES_AR = readJ(path.join(SITE, "../names/players_ar.json"), {}), nameOf = id => (NAMES_AR[id] || {}).ar || null;
  const APPROVED = readJ(path.join(SITE, "ai/approved.json"), {});
  const AI = k => { const d = path.join(CACHE, "ai", k), o = {}; if (fs.existsSync(d)) for (const f of fs.readdirSync(d)) if (f.endsWith(".json")) o[f.slice(0, -5)] = readJ(path.join(d, f), null); return o; };
  const AIS = AI("summary"), AIP = AI("preview"), AICM = AI("commentary"), AIPW = AI("power");
  const SUSR = {}; Object.values(readRes("suspension_rules.json")).forEach(v => { if (v && v.fotmob_id) SUSR[v.fotmob_id] = v; });
  const ATS = {}; Object.values((readRes("alltime_scorers.json").leagues) || {}).forEach(l => { if (l.fotmob_league_id) ATS[l.fotmob_league_id] = l; });
  const BC = readRes("broadcast.json"), HLT = readRes("highlights.json"), STAD = {}; ((readRes("stadiums.json").stadiums) || []).forEach(x => { STAD[x.id] = x; });

  // ---- data: the two leagues + the comps of the two matches, full analytics; the rest only standings (crest grid colours)
  const EXTRA = ["sim", "watch", "bump", "halftime", "xg", "clutch", "cards", "foreigners", "improved", "young-uae", "team-of-round", "minute-clock", "goal-bands", "referees", "lineup-ages", "rotation", "pressure", "style", "fortress", "records", "alltime", "facts", "players", "similar", "tournament-sim", "scenarios", "shots", "fatigue", "coaches", "transfers", "records-book", "seasons", "milestones", "upsets", "projections", "bracket-sim", "local-minutes", "suspensions", "first-goal", "dropped", "dependence", "xi", "signings", "absences", "alltime-table", "promoted", "late-goals", "champion-path", "games-in-hand"];
  const md0 = await pool(MATCHES, 2, id => get(`match/${id}.json`));
  const full = new Set(comps.filter(c => COMPS.includes(c.key)).map(c => c.id)); md0.forEach(m => m && full.add(m.comp));
  const compData = {};
  await pool(comps.filter(c => !c.dormant || full.has(c.id)), 3, async c => {
    const deep = full.has(c.id);
    const [st, fx, stats] = await Promise.all([c.files && c.files.standings ? get(`comp/${c.id}/standings.json`, 2) : null, deep || !(c.files && c.files.standings) ? get(`comp/${c.id}/fixtures.json`, 2) : null, deep ? get(`comp/${c.id}/stats.json`) : null]);
    const x = {}; if (deep) await pool(EXTRA, 3, async k => { x[k] = await get(`comp/${c.id}/${k}.json`, 1); });
    compData[c.id] = { c, st, fx, stats, x };
  });
  const day = await get(`day/${today.replace(/-/g, "")}.json`) || { matches:[] }, live = await get("live.json") || { matches:[] };
  const byLive = {}; (live.matches || []).forEach(m => { byLive[m.id] = m; }); day.matches = (day.matches || []).map(m => byLive[m.id] || m);
  const [ratings, compare] = await Promise.all(["ratings/uae-clubs.json", "leagues/compare.json"].map(f => get(f, 1)));
  const h2hIdx = await get("h2h/index.json", 1), H2H = {};
  if (h2hIdx) { const ks = Object.keys(h2hIdx.pairs || {}); const hs = await pool(ks, 4, k => get(`h2h/${k}.json`, 1)); ks.forEach((k, i) => { if (hs[i]) H2H[k] = hs[i]; }); }
  R.H2HK = {}; Object.keys(H2H).forEach(k => { R.H2HK[k] = 1; });
  // players: Arabic names applied to the player files the analytics renderers read (ids are player ids here, never clubs)
  const allPlayers = {};
  Object.values(compData).forEach(({ c, x }) => { if (x.players && x.players.players) for (const [pid, pp] of Object.entries(x.players.players)) allPlayers[pid] = Object.assign({ comp:c.id }, pp); if (x.cards && x.cards.players) for (const [id, cc] of Object.entries(x.cards.players)) allPlayers[id] = Object.assign({ name:cc.name, team:cc.team }, allPlayers[id] || {}); });
  for (const [pid, p] of Object.entries(allPlayers)) if (nameOf(pid)) { p.name_en = p.name; p.name = nameOf(pid); }
  Object.values(compData).forEach(({ x, stats }) => {
    if (x.cards && x.cards.players) for (const [id, cc] of Object.entries(x.cards.players)) if (nameOf(id)) cc.name = nameOf(id);
    if (stats && stats.lists) for (const l of Object.values(stats.lists)) (l || []).forEach(r => { if (r.player && nameOf(r.player.id)) r.player.name = nameOf(r.player.id); });
  });
  S.setPlayers(allPlayers);

  // ---- assets: v3 CSS = v2 tifo.css re-themed for a night ground + next.css; JS = render + rx + share + keyart + app (patched) + next
  let css = fs.readFileSync(path.join(SITE, "src/tifo.css"), "utf8");
  const bgSwap = (v, to) => { css = css.replace(new RegExp(`(background(?:-color)?\\s*:[^;}]*?)var\\(--${v}\\)`, "g"), `$1var(--${to})`); };
  bgSwap("chalk", "surf"); bgSwap("night", "board"); bgSwap("ink", "inkbg"); bgSwap("concrete-2", "surf-2"); bgSwap("concrete", "bg");
  css = css.replace(/background:#fff;font-size:1rem/, "background:var(--surf);font-size:1rem");
  css += "\n" + fs.readFileSync(path.join(HERE, "src/next.css"), "utf8");
  let app = fs.readFileSync(path.join(SITE, "src/app.js"), "utf8");
  const patch = (from, to, label) => { if (typeof from === "string" ? !app.includes(from) : !from.test(app)) throw new Error("app.js patch did not apply: " + label); app = app.replace(from, to); };
  patch(/\s*if \("serviceWorker" in navigator\) try \{ navigator\.serviceWorker\.register\("\/sw\.js"\); \} catch \(e\)\{\}/, "\n  /* v3 preview: no service worker */", "sw");
  patch(/  \/\/ 250: a share button on every numbers section[\s\S]*?h\.appendChild\(b\); \}\);\n/, "  /* v3: per-section share buttons replaced by the page sheet's «صورة لأي قسم» (next.js) */\n", "per-section share");
  patch('fetch("/assets/search." + sb0.dataset.v', 'fetch("' + BASE + 'assets/search." + sb0.dataset.v', "search");
  patch('fetch("/assets/bc." + B.dataset.bc', 'fetch("' + BASE + 'assets/bc." + B.dataset.bc', "bc");
  patch(/(set\("#day", R\.dayList\(ms, idx, \{[^;]*\}\)\);)/, '$1 document.dispatchEvent(new CustomEvent("tifo:day", { detail:{ ms:ms, idx:idx, live:live, off:dayOff } }));', "day event");
  patch("'<a class=\"cd\" href=\"/m/' + m.id + '/\"><span><b>الإمارات ضد ' + R.tname(opp) + '</b>".replace(/\\"/g, '"'), "'<a class=\"cd\" href=\"/m/' + m.id + '/\"><span><b>' + R.tname(m.home) + ' ضد ' + R.tname(m.away) + '</b>".replace(/\\"/g, '"'), "countdown order (home first)");
  patch("MD = md; FULL = md;", 'MD = md; FULL = md; document.dispatchEvent(new CustomEvent("tifo:match", { detail:md }));', "match event");
  const js = [fs.readFileSync(path.join(SITE, "src/render.js"), "utf8"), fs.readFileSync(path.join(HERE, "src/rx.js"), "utf8"), fs.readFileSync(path.join(SITE, "src/share.js"), "utf8"), fs.readFileSync(path.join(HERE, "src/keyart.js"), "utf8"), app, fs.readFileSync(path.join(HERE, "src/next.js"), "utf8")].join("\n;\n");
  ASSET = { css:hash(css), js:hash(js) };
  fs.writeFileSync(path.join(OUT, `assets/next.${ASSET.css}.css`), css); fs.writeFileSync(path.join(OUT, `assets/next.${ASSET.js}.js`), js);
  const p3 = fs.readFileSync(path.join(SITE, "src/pitch3d.js"), "utf8"), P3V = hash(p3); fs.writeFileSync(path.join(OUT, `assets/pitch3d.${P3V}.js`), p3.replace(/(["'])\/logo\//g, "$1" + BASE + "logo/"));
  // client data files from the snapshot of the current build (same versions production serves)
  for (const f of fs.readdirSync(path.join(HERE, "snap/assets"))){ fs.copyFileSync(path.join(HERE, "snap/assets", f), path.join(OUT, "assets", f)); const m = f.match(/^(search|bc|colors)\.([0-9a-f]+)\.(json|js)$/); if (m){ if (m[1] === "search") SEARCH_V = m[2]; if (m[1] === "bc") BC_V = m[2]; if (m[1] === "colors") COLOR_F = f; } }

  // ---- 1. competition pages
  const factsByMatch = {}; Object.values(compData).forEach(({ x }) => { if (x.facts && x.facts.matches) Object.assign(factsByMatch, x.facts.matches); });
  const stIdsOf = st => st && !st.composite && st.groups && st.groups[0] ? st.groups[0].rows.map(r => r.team.id) : [];
  for (const key of COMPS){
    const c = comps.find(cc => cc.key === key), { st, fx, stats, x } = compData[c.id]; SEQ = 0;
    const ids = stIdsOf(st); PALETTE = ids.map(id => colors[id]).filter(Boolean); if (!PALETTE.length) PALETTE = [["#5C6660", "#F6F7F2"]];
    let rounds = "";
    if (fx && fx.matches && fx.matches.length){ const rr = R.rounds(fx), cur = fx.next_round && rr.by[fx.next_round] ? fx.next_round : (rr.order.find(k => rr.by[k].some(m => m.status !== "finished")) || rr.order[rr.order.length - 1]); rounds = `<div class="chips">` + rr.order.map(k => `<button type="button" data-r="${esc(k)}"${k === cur ? ' aria-pressed="true"' : ""}>${esc(k)}</button>`).join("") + `</div><div id="roundlist">${R.roundList(rr.by[cur] || [])}</div>`; }
    const has = { table:!!(st && st.groups && st.groups.length), stats:!!(stats && stats.lists) };
    // table + variants (segmented), the season journey as the tab's shelf
    const vars = has.table && !st.composite ? S.tables(st, x.halftime, x.xg) : [];
    if (has.table && !st.composite){ const ft = S.formTable(fx, st), gh = S.gamesInHand(st); if (ft) vars.push(["form", "الفورمة", ft]); if (gh) vars.push(["hand", "المؤجلة", gh]); }
    const tableLead = has.table ? (vars.length ? segBar("tv", [["all", "الكل"]].concat(vars.map(v => [v[0], v[1]]))) + pane("tv", "all", `<div id="table">${R.standings(st)}</div>`, true).replace(/ data-slot="tab:all"/, "") + vars.map(v => pane("tv", v[0], v[2]).replace(/ data-slot="tab:[^"]*"/, "")).join("") : `<div id="table">${R.standings(st)}</div>`) : "";
    const tableShelf = x.bump ? shelf([blocks(S.sec("رحلة الموسم", "", S.bump(x.bump))).secs[0]], { title:"الموسم بالرسم" }) : "";
    // predictions
    const rmap = c.id === 538 ? S.ratingMap(ratings) : (x.ratings ? S.ratingMap(x.ratings) : {});
    const fdrHtml = st && !st.composite ? S.fdr(st, fx, rmap) : "", roadHtml = st && !st.composite ? S.roadTitle(st, fx, rmap, x.sim) : "";
    const clockHtml = S.seasonClock(fx, st, x.watch), projHtml = S.projections(stats, st);
    const nextR = (() => { if (!fx || !fx.matches) return []; const rr = R.rounds(fx), k = rr.order.find(k => rr.by[k].some(m => m.status === "scheduled" && m.probs)); return k ? rr.by[k].filter(m => m.status === "scheduled" && m.probs).map(m => ({ h:m.home.id, a:m.away.id, home:m.home.name_ar || m.home.name, away:m.away.name_ar || m.away.name, p:[m.probs.home, m.probs.draw, m.probs.away], ko:m.kickoff_uae, r:k })) : []; })();
    const powK = APPROVED.power ? Object.keys(AIPW).filter(k => k.startsWith(c.id + "-")).sort().pop() : null;
    const G = k => `<a href="/glossary/#${k}">شو يعني؟</a>`;
    const predSecs = blocks([clockHtml ? S.sec("ساعة الموسم", "", clockHtml) : "", roadHtml ? S.sec("الطريق للقب", "", roadHtml) : "", fdrHtml ? S.sec("صعوبة المباريات الياية", G("difficulty"), fdrHtml) : "", x.watch && fx ? S.sec("أحلى مباريات الجولة الياية", "", S.watch(x.watch, fx)) : "", S.whatif(fx, st) ? S.sec("شو لو؟", "", S.whatif(fx, st)) : "", x.sim && x.sim.teams ? S.sec("توقعات آخر الموسم", G("simulator"), S.sim(x.sim, st)) : "", st && st.magic ? S.sec("كم يحتاج فريقك؟", G("magic-number"), S.magic(st)) : "", x["tournament-sim"] ? S.sec("من بيفوز بالبطولة؟", "", S.tsim(x["tournament-sim"])) : "", projHtml ? S.sec("كم بيسجل الهدافين لآخر الموسم؟", "", projHtml) : "", st && st.bracket && st.bracket.length ? S.sec("شجرة البطولة", "", S.bracket(st, null)) : "", x.scenarios ? S.sec("حاسبة التأهل", "", S.groupCalc(x.scenarios)) : "", S.absences(x.absences) ? S.sec("غيابات الجولة" + (x.absences.round ? " " + esc(x.absences.round) : ""), "", S.absences(x.absences)) : "", S.gihFile(x["games-in-hand"]) ? S.sec("المباريات المؤجلة", G("games-in-hand"), S.gihFile(x["games-in-hand"])) : ""].join("")).secs;
    const leadP = predSecs.findIndex(s => s.title === "توقعات آخر الموسم");
    const predLead = leadP >= 0 ? predSecs.splice(leadP, 1)[0].full : "";
    const predPane = predLead + shelf(predSecs, { title:"بعد في التوقعات" });
    // numbers: scorers/assisters lead (segmented), 26 sections as a shelf
    const num = [
      ["cards", "بطاقات تيفو", S.cards(x.cards, 12)], ["clutch", "منو الحاسم؟", S.clutch(x.clutch)], ["tor", "تشكيلة الجولة", S.teamOfRound(x["team-of-round"])],
      ["foreign", "أفضل محترف أجنبي", S.foreigners(x.foreigners)], ["improved", "الأكثر تطوّر", S.improved(x.improved)], ["young", "المواهب الإماراتية تحت 23", S.young(x["young-uae"])],
      ["clock", "ساعة الأهداف", S.clock(x["minute-clock"])], ["late", "ملوك الدقايق الأخيرة", S.late(x["goal-bands"])],
      ["pressure", "ترمومتر المدربين", S.pressure(x.pressure)], ["style", "بصمة كل فريق", S.style(x.style)], ["fortress", "حصون الملاعب", S.fortress(x.fortress)],
      ["fatigue", "مؤشر الإرهاق", S.fatigue(x.fatigue)], ["coaches", "أنجح المدربين في التاريخ", S.coachesLeague(x.coaches)],
      ["transfers", "سوق الانتقالات", S.transfers(x.transfers)], ["susp", "الإيقافات", S.suspensions(SUSR[c.id], x.suspensions)],
      ["refs", "الحكام", S.referees(x.referees)], ["ages", "أعمار التشكيلات", S.ages(x["lineup-ages"])], ["rot", "مؤشر التدوير", S.rotation(x.rotation)],
      ["fgoal", "منو يسجل أول؟", S.firstGoal(x["first-goal"])], ["dropped", "نقاط ضاعت ونقاط رجعت", S.dropped(x.dropped)], ["depend", "الاعتماد على الهداف", S.dependence(x.dependence)],
      ["late90", "أهداف بعد الدقيقة 90", S.lateGoals(x["late-goals"])], ["sign", "أحسن صفقات الموسم", S.signings(x.signings)], ["miles", "أرقام شخصية قريبة", S.milestones(x.milestones, ids)],
      ["rating", "تصنيف تيفو للأندية", c.id === 538 ? S.ratingTable(ratings) : ""], ["world", "الدوري الإماراتي ضد العالم", c.id === 538 ? S.compare(compare, 538) : ""],
    ].filter(v => v[2]);
    const GL = { cards:"tifo-card", clutch:"clutch", pressure:"pressure-index", style:"ppda", rot:"rotation", fatigue:"fatigue", rating:"tifo-rating" };
    const numSecs = num.map(v => blocks(S.sec(v[1], GL[v[0]] ? G(GL[v[0]]) : "", v[2], "n-" + v[0])).secs[0]);
    const numLead = has.stats ? segBar("lead", [["goals", "الهدافين"], ["assists", "صناع الأهداف"]]) + pane("lead", "goals", `<div id="goals">${R.leaders(stats, "goals")}</div>`, true).replace(/ data-slot="tab:goals"/, "") + pane("lead", "assists", `<div id="assists">${R.leaders(stats, "assists")}</div>`).replace(/ data-slot="tab:assists"/, "") : "";
    const numPane = numLead + shelf(numSecs, { title:"الأرقام كلها" });
    // history
    const derb = c.id === 538 ? S.derbyList(h2hIdx, H2H) : "";
    const hist = (x["champion-path"] ? (h => h ? S.sec("طريق البطل", "", h) : "")(S.championPath(x["champion-path"])) : "") + (ATS[c.id] ? S.sec("الهدافين التاريخيين", "", S.alltimeScorers(ATS[c.id])) : "") + (h => h ? S.sec("الجدول التاريخي", "من " + esc((x["alltime-table"] || {}).since || ""), h) : "")(S.alltimeTable(x["alltime-table"])) + (h => h ? S.sec("الدوري موسم بموسم", "", h) : "")(S.seasons(x.seasons, c.season)) + (h => h ? S.sec("الصاعدين هالموسم", "", h) : "")(S.promoted(x.promoted)) + (x.alltime ? S.sec("تاريخ الدوري", "من 1973", S.alltime(x.alltime)) : "") + (derb ? S.sec("سجل المواجهات بين الأندية", "", derb) : "") + (x.records && x.records.chases && x.records.chases.length ? S.sec("أرقام قياسية على المحك", "", S.records(x.records)) : "") + (x["records-book"] ? S.sec("كتاب الأرقام القياسية", "من " + esc(x["records-book"].since || ""), S.recordsBook(x["records-book"])) : "");
    const histSecs = blocks(hist).secs;
    const tl = [has.table && ["table", "الترتيب"], ["fixtures", "المباريات"], (numLead || numSecs.length) && ["num", "الأرقام"], (predLead || predSecs.length) && ["pred", "التوقعات"], histSecs.length && ["hist", "التاريخ"]].filter(Boolean);
    // hero: key art = the clubs' colours in table order, the leader, the next round
    const lead = has.table && !st.composite ? st.groups[0].rows[0] : null;
    const upcoming = (fx && fx.matches || []).filter(m => m.status === "scheduled" && m.kickoff_utc).sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc))[0];
    const liveN = (live.matches || []).filter(m => m.comp === c.id).length;
    const fin = (fx && fx.matches || []).filter(m => m.status === "finished").length, tot = (fx && fx.matches || []).length;
    const heroFacts = [lead ? `<div><dt>المتصدر</dt><dd><a href="/t/${lead.team.id}/">${R.logo(lead.team, "sm")} ${R.tname(lead.team)}</a> <b class="num">${lead.pts}</b> <small>نقطة</small></dd></div>` : "",
      upcoming ? `<div><dt>الجولة الياية</dt><dd><b class="num">${esc(upcoming.round || "")}</b> ${R.td(upcoming.kickoff_uae, true)}</dd></div>` : "",
      tot ? `<div><dt>الموسم</dt><dd><b class="num">${fin}</b> <small>من</small> <b class="num">${tot}</b> <small>مباراة</small></dd><i class="prog" style="--p:${(fin / tot * 100).toFixed(1)}%"></i></div>` : ""].join("");
    const artBands = JSON.stringify((ids.length ? ids : []).map(id => colors[id] || ["#5C6660", "#F6F7F2"]));
    const tools = `${nextR.length ? `<button type="button" class="sa" id="rpbtn">صورة توقعات الجولة ${esc(nextR[0].r)}</button>` : ""}${x.cards ? `<a class="sa" href="/c/${c.key}/compare/">قارن بين لاعبين أو فريقين</a>` : ""}${powK ? `<a class="sa" href="/c/${c.key}/power/">ترتيب القوة هالأسبوع</a>` : ""}`;
    const g = glow(c.id), hasLogo = LOGO(c.id);
    const art = hasLogo ? `<div class="lgart" aria-hidden="true"><i class="bloom"></i><i class="bloom b2"></i><img class="lglogo" src="${BASE}lg/${c.id}.png" alt="" width="192" height="192"></div>` : `<canvas aria-hidden="true"></canvas>`;
    const body = `<section class="hero chero${hasLogo ? " haslogo" : ""}" data-slot="hero" data-art='${esc(artBands)}' style="--g1:${g[0]};--g2:${g[1]}">${art}<div class="scrim"></div><div class="hero-in wrap">
<p class="hk"><a href="/competitions/">البطولات</a>${c.country ? `، ${esc(c.country.name_ar)}` : ""}${liveN ? ` <span class="lv"><i class="cardflip"></i>${liveN} مباشر</span>` : ""}</p><h1>${esc(c.name_ar)}</h1><p class="season">الموسم <span class="num">${esc(c.season || "")}</span></p>${c.dormant ? '<p class="note">البطولة متوقفة أو خلصت هالموسم. هذي آخر نتايجها.</p>' : ""}
<dl class="hfacts">${heroFacts}</dl><div class="hero-acts"><a class="cta" href="#fixtures" data-go="fixtures">${upcoming ? "مباريات الجولة" : "المباريات"}</a><button type="button" class="ghost" data-sheet="share">شارك</button></div></div></section>
${nextR.length ? `<script type="application/json" id="rpreds">${JSON.stringify(nextR).replace(/</g, "\\u003c")}</script>` : ""}<div class="wrap body">` + tabsBar("c", tl) +
      (has.table ? pane("c", "table", tableLead + tableShelf, true) : "") + pane("c", "fixtures", `<div id="rounds">${rounds || '<p class="empty">ما في مباريات منشورة.</p>'}</div>`, !has.table) +
      ((numLead || numSecs.length) ? pane("c", "num", numPane) : "") + ((predLead || predSecs.length) ? pane("c", "pred", predPane) : "") + (histSecs.length ? pane("c", "hist", shelf(histSecs, { title:"التاريخ والأرقام القياسية" })) : "") + "</div>";
    const names = {}; if (stats && stats.lists) Object.values(stats.lists).forEach(l => (l || []).forEach(r => { if (r.player && nameOf(r.player.id)) names[r.player.id] = nameOf(r.player.id); }));
    write(`c/${c.key}/index.html`, page({ path:`/c/${c.key}/`, page:"comp", nav:"comps", attrs:` data-comp="${c.id}"`, tools, names, title:`${c.name_ar}: الترتيب والمباريات والتوقعات ${c.season || ""} | تيفو`, desc:`ترتيب ${c.name_ar} ومواعيد المباريات والنتايج المباشرة والتوقعات والأرقام.`, body }));
  }

  // ---- 2. match pages
  const compX = id => (compData[id] || {}).x || {};
  for (const md of md0.filter(Boolean)){
    const id = md.id; SEQ = 0; R.arNames(md);
    const cd = compData[md.comp] || {}, cx = compX(md.comp), x538 = compX(538), index2 = index;
    PALETTE = [colors[md.home.id], colors[md.away.id]].filter(Boolean); if (!PALETTE.length) PALETTE = [["#5C6660", "#F6F7F2"]];
    const sum = Object.assign({}, (cd.fx && cd.fx.matches || []).find(m => m.id === id) || {}, md);
    const uaeMatch = R.UAE_COMPS.indexOf(md.comp) >= 0 || md.home.id === 5789 || md.away.id === 5789;
    const probs = md.status === "scheduled" ? (md.probs || sum.probs) : null, facts = md.status === "scheduled" ? factsByMatch[id] : null;
    const fa = md.status === "scheduled" && md.comp === 538 && x538.fatigue ? S.fatigue(x538.fatigue, [md.home.id, md.away.id]) : "";
    const aiSum = APPROVED.summary && AIS[id] ? S.aiSummary(AIS[id]) : "", aiPre = APPROVED.preview && md.status === "scheduled" && AIP[id] ? S.sec("تحليل ما قبل المباراة", "", S.aiPreview(AIP[id])) : "";
    const press = md.status === "scheduled" && uaeMatch ? S.pressSheet(md, cd.st, cd.stats, factsByMatch[id], cx.fatigue, md) : "";
    const thread = APPROVED.thread && AIS[id] ? S.aiThread(AIS[id]) : "";
    const opp = md.status === "scheduled" ? S.oppReport(md, cx, cd.stats) : "";
    const ww = md.status !== "finished" ? S.watchWhere(BC[md.comp]) : "", hl = md.status === "finished" ? S.highlight(HLT[md.comp], md) : "";
    const mdy = md.venue && STAD[md.venue.id] ? S.matchDay(md, STAD[md.venue.id]) : "";
    const sgrid = probs ? S.scoreGrid(probs, md) : "";
    const L2 = md.lineups, tac = L2 && L2.home && L2.away ? (() => { const subs = side => (md.events || []).filter(e => e.type === "sub" && e.team === side), f = side => { const sb = subs(side); return `${R.tname(md[side])}: خطة <span class="num">${esc(L2[side].formation || "—")}</span>، ${sb.length} تبديلات${sb.length ? `، أولها الدقيقة <span class="num">${sb[0].minute}</span>` : ""}.`; }; return `<ul class="facts-l"><li>${f("home")}</li><li>${f("away")}</li></ul>`; })() : "";
    const replay = md.status === "finished" && (md.events || []).some(e => /goal|red|yellow/.test(e.type)) ? '<div class="replay"><label>اسحب لأي دقيقة: <b class="num" id="rpm">90</b></label><input type="range" id="rpr" min="0" max="' + ((md.events || []).some(e => e.minute > 90) ? 120 : 90) + '" value="' + ((md.events || []).some(e => e.minute > 90) ? 120 : 90) + '" aria-label="الدقيقة"><div class="rpsc"><span>' + R.tname(md.home) + '</span><b class="num" id="rps">' + (md.score ? md.score.home + " - " + md.score.away : "") + '</b><span>' + R.tname(md.away) + '</span></div><ul class="facts-l" id="rpe"></ul><script type="application/json" id="rpev">' + JSON.stringify((md.events || []).filter(e => /goal|red|yellow|second/.test(e.type)).map(e => [e.minute + (e.added ? e.added / 10 : 0), e.type, e.team, e.player && e.player.name, e.score ? [e.score.home, e.score.away] : null])).replace(/</g, "\\u003c") + "</script></div>" : "";
    // analysis shelf (every analytics section of the old page, one tile each)
    const anaHtml = [aiSum ? S.sec("الخلاصة بالذكاء الاصطناعي", "", aiSum) : "", aiPre, S.winprob(md) ? S.sec("فرص الفوز دقيقة بدقيقة", "", S.winprob(md)) : "", sgrid ? S.sec("أرجح النتايج بالضبط", "", sgrid) : "", opp ? S.sec("تقرير الفريقين", "", opp) : "", press ? S.sec("ورقة الصحفي", "", press) : "", thread ? S.sec("ثريد إكس", "", thread) : "", tac ? S.sec("الخطط والتبديلات", "", tac) : "", APPROVED.commentary && S.aiCommentary(AICM[id]) ? S.sec("التعليق المكتوب", "", S.aiCommentary(AICM[id])) : "", S.firsts(md) ? S.sec("أوائل", "", S.firsts(md)) : "", replay ? S.sec("إعادة المباراة", "", replay) : "", fa ? S.sec("ضغط المباريات", "", fa) : "", facts && facts.length ? S.sec("قبل المباراة", "", S.matchFacts(facts)) : "", mdy ? S.sec("رايح الملعب؟", "", mdy) : ""].join("");
    const anaSecs = blocks(anaHtml).secs;
    const leadIdx = anaSecs.findIndex(s => s.title === "فرص الفوز دقيقة بدقيقة"); const anaLead = leadIdx >= 0 ? anaSecs.splice(leadIdx, 1)[0].full : "";
    const faqQ = S.faq(md, (BC[md.comp] && BC[md.comp].broadcasters || []).map(b => b.name_ar).join("، "), md.venue && (md.venue.name_ar || md.venue.name_en));
    const faqHtml = faqQ.length ? `<details class="faq wrap" data-slot="footer-faq"><summary><h2>أسئلة عن المباراة</h2></summary><dl class="gl">${faqQ.map(q => `<dt>${esc(q[0])}</dt><dd>${esc(q[1])}</dd>`).join("")}</dl></details>` : "";
    const sched = md.status === "scheduled", liveNow = R.isLive(md);
    const firstTab = sched ? "قبل المباراة" : "الأحداث";
    const eventsPane = `<div id="catchup">${R.catchup(md)}</div>` + (hl ? `<p class="hlink">${hl}</p>` : "") + (sched ? `<div id="wwbox" data-comp="${md.comp}">${ww ? S.sec("وين تنقل في الإمارات", "", ww) : ""}</div>` + (probs ? S.probs(probs, md) : "") : "") +
      `<div id="events">${R.events(md)}</div>` + (!sched && ww ? `<div id="wwbox" data-comp="${md.comp}">${S.sec("وين تنقل في الإمارات", "", ww)}</div>` : "") + `<h3 class="sub-h">تفاصيل المباراة</h3><div id="facts">${R.matchFacts(md, index2)}</div>`;
    const sumJ = JSON.stringify(Object.assign({}, sum, { events:undefined, lineups:undefined, stats:undefined, h2h:undefined })).replace(/</g, "\\u003c");
    const cname = md.comp_name_ar || R.compName(index, md.comp), ckey = R.compKey(index, md.comp);
    const tools = `<button type="button" class="sa" id="storybtn">صورة للستوري</button><button type="button" class="sa" id="secondbtn">الشاشة الثانية</button><a class="sa" href="/tv/?m=${id}">على شاشة المجلس</a>${uaeMatch ? `<a class="sa" href="/m/${id}/kit/">عدّة صانع المحتوى</a>` : ""}`;
    const body = `<section class="hero mhero" data-slot="hero" id="mhero"><canvas aria-hidden="true"></canvas><div class="scrim"></div><div class="hero-in wrap">
<p class="hk">${ckey ? `<a href="/c/${ckey}/">${esc(cname)}</a>` : esc(cname)}${md.round && !isNaN(parseFloat(md.round)) ? `، الجولة <span class="num">${esc(md.round)}</span>` : md.stage ? "، " + esc(R.stageAr(md.stage)) : ""}</p>
<div id="mh">${R.matchHead(md)}</div><div class="hero-acts"><button type="button" class="cta" data-sheet="share">شارك وأدوات</button>${sched ? `<a class="ghost" href="#events" data-go="events">وين تنقل</a>` : `<a class="ghost" href="#lineups" data-go="lineups">التشكيلة</a>`}</div></div></section>
<div class="mini" id="mini" aria-hidden="true"><div class="wrap"></div></div>
<script type="application/json" id="msum">${sumJ}</script><div class="wrap body">` +
      tabsBar("m", [["events", firstTab], ["lineups", "التشكيلة"], ["stats", "الإحصائيات"], ["ana", "التحليل"], ["h2h", "المواجهات"]]) +
      pane("m", "events", eventsPane, true) +
      pane("m", "lineups", `<div class="tools"><button type="button" class="btn" id="p3dbtn" data-src="${BASE}assets/pitch3d.${P3V}.js"${md.lineups && md.lineups.home ? "" : " hidden"}>شوفها على ملعب ثلاثي الأبعاد</button></div><div id="p3d"></div><div id="lineups">${R.lineups(md)}</div>`) +
      pane("m", "stats", `<div id="stats">${R.stats(md)}</div>`) +
      pane("m", "ana", (anaLead || "") + (anaSecs.length ? shelf(anaSecs, { title:"التحليل كله" }) : "") || '<p class="empty">التحليل ينزل مع قرب المباراة.</p>') +
      pane("m", "h2h", `<div id="h2h">${R.h2h(md)}</div>`) + "</div>" + faqHtml;
    const ld = { "@context":"https://schema.org", "@type":"SportsEvent", name:`${md.home.name_ar || md.home.name} ضد ${md.away.name_ar || md.away.name}`, startDate:md.kickoff_utc, sport:"Football", homeTeam:{ "@type":"SportsTeam", name:md.home.name_ar || md.home.name }, awayTeam:{ "@type":"SportsTeam", name:md.away.name_ar || md.away.name } };
    const names = {}; for (const tid of [md.home.id, md.away.id]){ const tj = await get(`team/${tid}.json`, 2); ((tj && tj.squad) || []).forEach(g => (g.players || []).forEach(p => { if (p && p.id && nameOf(p.id)) names[p.id] = nameOf(p.id); })); }
    (md.events || []).forEach(e => [e.player, e.assist, e.player_out].forEach(p => { if (p && p.id && nameOf(p.id)) names[p.id] = nameOf(p.id); })); if (md.lineups) ["home", "away"].forEach(s => md.lineups[s] && [].concat(md.lineups[s].starters || [], md.lineups[s].subs || [], md.lineups[s].unavailable || []).forEach(p => { if (p && p.id && nameOf(p.id)) names[p.id] = nameOf(p.id); }));
    const ttl = `${R.tname(md.home)} ${md.score ? md.score.home + "-" + md.score.away : "ضد"} ${R.tname(md.away)}`;
    write(`m/${id}/index.html`, page({ path:`/m/${id}/`, page:"match", nav:"home", attrs:` data-id="${id}"`, tools, names, title:`${ttl} — ${cname} | تيفو`, desc:`${R.tname(md.home)} ضد ${R.tname(md.away)}: النتيجة المباشرة والأحداث والتشكيلة والإحصائيات والتحليل والمواجهات.`, body, ld:faqQ.length ? [ld, { "@context":"https://schema.org", "@type":"FAQPage", mainEntity:faqQ.map(q => ({ "@type":"Question", name:q[0], acceptedAnswer:{ "@type":"Answer", text:q[1] } })) }] : ld }));
  }

  // ---- 3. home: hero, rails, the day list, the crest grid, the editorial rail
  PALETTE = Object.values(colors).slice(0, 60);
  const heroM = R.heroPick(day.matches, index, null);
  const seen = new Set(day.matches.map(m => m.id)), railMs = day.matches.concat((live.matches || []).filter(m => !seen.has(m.id)));
  const rails = R.homeRails(railMs, index, {});
  const snapHome = fs.readFileSync(path.join(HERE, "snap/old/index.html"), "utf8"), oldMain = snapHome.slice(snapHome.indexOf("<main"), snapHome.indexOf("</main>"));
  const bdays = (oldMain.match(/<div id="bdays"[^>]*><\/div>/) || [""])[0];
  const ed = blocks(oldMain).secs.filter(s => s.title && s.title !== "البطولات");
  SEQ = 0;
  const edCards = ed.map(s => { const more = (s.sub.match(/<a [^>]*>[\s\S]*?<\/a>/) || [""])[0]; const key = "e" + (++SEQ); const tz = teaser(s);
    return { card:`<button type="button" class="ed" data-open="${key}">${tifoIcon(s.title)}<span class="tt2">${esc(s.title)}</span>${tz ? `<span class="tz">${esc(tz)}</span>` : ""}${more ? `<span class="em">${more.replace(/<[^>]+>/g, "")}</span>` : ""}</button>`, vault:isLive(s.full) ? `<div class="vault" id="v-${key}" hidden><div class="pbody" data-title="${esc(s.title)}">${s.full}</div></div>` : `<template id="v-${key}"><div class="pbody" data-title="${esc(s.title)}">${s.full}</div></template>` }; });
  const edLinks = [["/legends/", "الأساطير", "مسيرة وأرقام أبرز لاعبين في تاريخ الكورة الإماراتية"], ["/memorable/", "مباريات لا تُنسى", "المباريات اللي صنعت تاريخ الكورة الإماراتية"], ["/cast/", "تيفو كاست", "الجولة بصوت إماراتي، كل أسبوع"], ["/laws/", "قانون الكورة", "ليش ألغى الحكم الهدف؟ بالإماراتي"], ["/tv/", "شاشة المجلس", "كل المباريات على تلفزيون المجلس"], ["/studio/", "ستوديو التيفو", "صمّم لافتة فريقك للمدرج"]]
    .map(l => `<a class="ed" href="${l[0]}">${tifoIcon(l[1])}<span class="tt2">${l[1]}</span><span class="tz">${l[2]}</span></a>`).join("");
  // crest grid: every running competition as a tile of its clubs' colours
  const run = comps.filter(c => !c.dormant);
  const tileOf = c => { if (LOGO(c.id)){ const g = glow(c.id); return `<a class="ct lgt" href="/c/${c.key}/" style="--g1:${g[0]};--g2:${g[1]}"><span class="cl" aria-hidden="true"><img src="${BASE}lg/${c.id}.png" alt="" loading="lazy" width="96" height="96"></span><b>${esc(c.name_ar)}</b><small>${esc((c.country && c.country.name_ar) || { gulf:"الخليج", asia:"آسيا", europe:"أوروبا", arab:"العرب", africa:"أفريقيا", world:"العالم", national:"المنتخبات", uae:"الإمارات" }[c.scope] || "")}</small></a>`; } const d = compData[c.id] || {}; let tids = stIdsOf(d.st); if (!tids.length && d.fx && d.fx.matches) tids = [...new Set(d.fx.matches.flatMap(m => [m.home.id, m.away.id]))]; const cols = tids.slice(0, 12).map(id => (colors[id] || ["#123A31"])[0]); while (cols.length && cols.length < 12) cols.push(...cols.slice(0, 12 - cols.length));
    return `<a class="ct" href="/c/${c.key}/"><span class="cm" aria-hidden="true">${(cols.length ? cols : Array.from({ length:12 }, (_, i) => ["#1B4A3F", "#123A31", "#2A5A4E"][i % 3])).map(cl => `<i style="background:${cl}"></i>`).join("")}</span><b>${esc(c.name_ar)}</b><small>${esc((c.country && c.country.name_ar) || { gulf:"الخليج", asia:"آسيا", europe:"أوروبا", arab:"العرب", africa:"أفريقيا", world:"العالم", national:"المنتخبات", uae:"الإمارات" }[c.scope] || "")}</small></a>`; };
  const heroHtml = `<section class="hero hhero" data-slot="hero" id="stand"><canvas aria-hidden="true"></canvas><div class="scrim"></div><div class="hero-in wrap"><span class="kick" id="standkick">${heroM ? (R.isLive(heroM) ? "مباشر الحين" : heroM.status === "finished" ? "انتهت" : "الليلة") : "اليوم"}</span><div class="cap" id="standcap">${R.heroLine(heroM, index)}</div><div id="uaecd"></div>
<div class="hero-acts">${heroM ? `<a class="cta" id="herogo" href="${R.nx("/m/" + heroM.id + "/")}">تابع المباراة</a>` : ""}<button type="button" class="ghost" data-sheet="share">شارك</button></div></div></section><div id="since" class="wrap"></div>`;
  const mineRail = `<section class="rail rmine" id="r-mine" data-slot="rail"><div class="rail-h"><h2>فريقك</h2></div><div id="mine"></div></section>`;
  const dayBox = `<section class="daybox" id="matches" data-slot="list"><div class="rail-h"><h2>كل المباريات</h2><p class="livecount" id="livecount"></p></div>
<div class="daynav"><button type="button" id="prev" aria-label="اليوم اللي قبل">›</button><b id="daytitle">${R.dayNav(today, today)}</b><button type="button" id="next" aria-label="اليوم اللي بعد">‹</button></div>
<div class="seg segf" role="group" aria-label="اعرض"><button type="button" id="segall" aria-pressed="true">الكل</button><button type="button" id="arabonly" aria-pressed="false">العرب</button><button type="button" id="freeonly" aria-pressed="false">المجاني في بلدك</button></div>
<div id="day" class="fold">${R.dayList(day.matches, index, { empty:"ما في مباريات اليوم." })}</div><button type="button" class="unfold" id="unfold">كل المباريات</button></section>`;
  const body = heroHtml + `<div class="wrap body">` +
    R.rail("r-live", '<i class="cardflip"></i>مباشر الحين', rails.live) +
    R.rail("r-today", "اليوم", rails.today, `<a class="more-l" href="/today/">مباريات اليوم</a>`) +
    R.rail("r-arab", "مباريات العرب", rails.arab, `<a class="more-l" href="/tomorrow/">مباريات بكرة</a>`) +
    mineRail + dayBox +
    `<section class="rail cgrid3" data-slot="grid"><div class="rail-h"><h2>البطولات</h2><a class="more-l" href="/competitions/">كل البطولات</a></div><div class="cts">${run.slice(0, 18).map(tileOf).join("")}</div></section>` +
    `<section class="rail edr" data-slot="rail"><div class="rail-h"><h2>من تيفو</h2></div><div class="rail-s" tabindex="0">${edCards.map(e => e.card).join("")}${bdays.replace('<div id="bdays"', '<div class="ed edb" id="bdays"')}${edLinks}</div>${edCards.map(e => e.vault).join("")}</section></div>`;
  write("index.html", page({ path:"/", page:"home", nav:"home", title:"تيفو — مباريات اليوم مباشر لكل العرب", desc:"نتايج المباريات مباشر بتوقيت بلدك: الدوريات العربية والمنتخبات والبطولات الكبيرة.", body }));

  // ---- competitions list: grouped like the production page, every competition a logo tile
  { const groups = [["uae", "الإمارات"], ["gulf", "الخليج"], ["arab", "العرب"], ["asia", "آسيا"], ["africa", "أفريقيا"], ["national", "المنتخبات"], ["europe", "أوروبا"], ["world", "العالم"]];
    const body = `<section class="hero lhero" data-slot="hero"><div class="lgwall" aria-hidden="true">${comps.filter(c => LOGO(c.id)).slice(0, 24).map(c => `<img src="${BASE}lg/${c.id}.png" alt="" width="64" height="64">`).join("")}</div><div class="scrim"></div><div class="hero-in wrap"><p class="hk">تيفو</p><h1>البطولات</h1><p class="season">كل البطولات اللي نغطيها، <span class="num">${comps.length}</span> بطولة</p></div></section><div class="wrap body">` +
      groups.map(g => { const cs = comps.filter(c => c.scope === g[0]); return cs.length ? `<section class="rail cgrid3" data-slot="grid"><div class="rail-h"><h2>${g[1]}</h2></div><div class="cts all">${cs.map(tileOf).join("")}</div></section>` : ""; }).join("") + "</div>";
    write("competitions/index.html", page({ path:"/competitions/", page:"comps", nav:"comps", title:"كل البطولات | تيفو", desc:"كل البطولات اللي يغطيها تيفو.", body })); }
  // ---- crests actually referenced + the day's teams (client re-renders may show them)
  const need = new Set(); for (const f of [["index.html"], ["competitions", "index.html"], ...COMPS.map(k => ["c", k, "index.html"]), ...MATCHES.map(id => ["m", String(id), "index.html"])]){ const p = path.join(OUT, ...f); if (fs.existsSync(p)) (fs.readFileSync(p, "utf8").match(/\/next\/logo\/(\d+)\.png/g) || []).forEach(s => need.add(s.match(/(\d+)\.png/)[1])); }
  (day.matches || []).forEach(m => { need.add(String(m.home.id)); need.add(String(m.away.id)); });
  let nl = 0; for (const id of need){ const f = path.join(CACHE, "logo", id + ".png"); if (fs.existsSync(f)){ fs.copyFileSync(f, path.join(OUT, "logo", id + ".png")); nl++; } }
  const cells = [["#F6F7F2","#10A04B","#B07A3B"],["#F6F7F2","#B07A3B","#10A04B"],["#10A04B","#B07A3B","#F6F7F2"]].map((row, y) => row.map((c, x) => `<rect x="${4 + x * 8.5}" y="${4 + y * 8.5}" width="7" height="7" fill="${c}"/>`).join("")).join("");
  fs.writeFileSync(path.join(OUT, "favicon.svg"), `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="#0A2620"/>${cells}</svg>`);
  fs.writeFileSync(path.join(OUT, "robots.txt"), "User-agent: *\nDisallow: /\n");
  console.log(`next: 5 pages, ${nl} crests, css ${(css.length / 1024).toFixed(0)}KB js ${(js.length / 1024).toFixed(0)}KB in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
})().catch(e => { console.error(e); process.exit(1); });
