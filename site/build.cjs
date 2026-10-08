/* Build تيفو — static pages prerendered from the /v1 data (docs/SCHEMA.md) with src/render.js, then hydrated by src/app.js.
   node build.cjs [--data https://…cloudfront.net] [--out out] [--preview]
   -> out/index.html, out/c/<key>/, out/m/<id>/, out/t/<id>/, out/uae/, out/competitions/, out/logo/<id>.png, sitemap.xml
   --preview adds noindex (the *.cloudfront.net preview must not be indexed). Logos are cached in cache/logo/ and self-hosted
   (never hotlinked: visitor requests would carry our referer to FotMob). */
"use strict";
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const R = require("./src/render.js"), S = require("./src/stats.js"); require("./src/v3.js");
const LITE = require("./lib/lite.cjs");   // «تيفو خفيف» (second list 1): the guard in every head, the /lite/ page   // v3 layer (redesign/DESIGN-v3.md) patches R in place
const args = process.argv.slice(2), arg = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const DATA = (arg("--data", process.env.TIFO_DATA || "https://d1n5aqaqkowltp.cloudfront.net")).replace(/\/$/, "");
const OUT = path.resolve(__dirname, arg("--out", "out")), PREVIEW = args.includes("--preview");
const SITE = "https://tifo.elyoxe.com", CACHE = path.join(__dirname, "cache");
const esc = R.esc;

// QA 65: a club the feed has no Arabic for (Widad Temara) leaked its Latin name wherever a page reads name_ar || name
// (the /week/ aria-label among them). Once names/clubs_ar.json is loaded, every fetched team object gets its name_ar.
// Only under home/away/team/opponent, so a player whose id equals a club id is never renamed.
let TAR_FILL = null;
function fillAr(o, k){ if (!o || typeof o !== "object") return; if (Array.isArray(o)){ for (const x of o) fillAr(x, k); return; }
  if (TAR_FILL && (k === "home" || k === "away" || k === "team" || k === "opponent") && o.id != null && !o.name_ar && TAR_FILL[o.id]) o.name_ar = TAR_FILL[o.id];
  for (const kk in o) if (o[kk] && typeof o[kk] === "object") fillAr(o[kk], kk); }
// Dev only (never set by the runner or deploy.sh): TIFO_FETCH_CACHE=<dir> keeps every /v1 answer on disk with no expiry, so two
// builds can be compared on the same data and a targeted re-render (TIFO_ONLY) costs no network; delete the folder for fresh data.
const FCACHE = process.env.TIFO_FETCH_CACHE ? path.resolve(process.env.TIFO_FETCH_CACHE) : "";
const ONLY = process.env.TIFO_ONLY ? new RegExp(process.env.TIFO_ONLY) : null;   // dev only: write just the pages whose path matches
async function get(p, tries = 4){
  const cf = FCACHE && path.join(FCACHE, p.replace(/[?&=:]/g, "_"));
  if (cf){ try { const t = fs.readFileSync(cf, "utf8"); if (t === "null") return null; const j = JSON.parse(t); fillAr(j); return j; } catch (e){} }
  for (let i = 0; i < tries; i++){
    try { const r = await fetch(DATA + "/" + p, { signal:AbortSignal.timeout(25000) }); if (r.status === 404 || r.status === 403){ if (cf){ fs.mkdirSync(path.dirname(cf), { recursive:true }); fs.writeFileSync(cf, "null"); } return null; } if (!r.ok) throw new Error(r.status + " " + p); const t = await r.text(); const j = JSON.parse(t); if (cf){ fs.mkdirSync(path.dirname(cf), { recursive:true }); fs.writeFileSync(cf, t); } fillAr(j); return j; }
    catch (e){ if (i === tries - 1) { console.error("fetch failed", p, e.message); return null; } await new Promise(s => setTimeout(s, 1500 * (i + 1))); }
  }
}
async function pool(items, n, fn){ const out = new Array(items.length); let i = 0; await Promise.all(Array.from({ length:n }, async () => { while (i < items.length){ const k = i++; out[k] = await fn(items[k], k); } })); return out; }
// W1.7: visible text never shows null / undefined / [object Object] / raw pipeline keys; stripped and counted, never fatal
let GRPS = 0;   // Latin group letters that reached the page (fixed in write(), reported as a warning)
const LEAK = /\b(?:null|undefined|NaN)\b|\[object Object\]|\b(?:club|last_day|red_card)_[a-z0-9_]+\b/g; let LEAKS = 0;
const WRITTEN = new Set();   // W1.9: every page path written, for the post-build link check
// W4.2/W4.3: an old URL that moved. A true 301 needs the viewer-request function (see the wave 4 report); until then a stub:
// canonical, location.replace() keeping ?query and #hash, meta refresh as the fallback, noindex, never in the sitemap or search
function stub(from, to, title){ const [tp, th] = to.split("#"), u = SITE + tp;
  write(from.replace(/^\//, "") + "index.html", `<!doctype html><html lang="ar" dir="rtl" data-moved="1"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)} | تيفو</title><meta name="robots" content="noindex"><link rel="canonical" href="${u}"><meta http-equiv="refresh" content="0;url=${to}"><script>var s=location.search,t=${JSON.stringify(tp)};location.replace(t+(s&&t.indexOf("?")>=0?"&"+s.slice(1):s)+(location.hash||${JSON.stringify(th ? "#" + th : "")}))</script><style>body{background:#0A2620;color:#F6F7F2;font:16px system-ui;padding:2rem}a{color:#F6F7F2}</style></head><body><p>انتقلت الصفحة: <a href="${to}">${esc(title)}</a></p></body></html>`); }
// W4.7: files copied from cache/ keep the cache file's mtime, so `aws s3 sync` re-uploads only crests and share cards that changed
function cpKeep(src, dst){ fs.copyFileSync(src, dst); try { const s = fs.statSync(src); fs.utimesSync(dst, s.atime, s.mtime); } catch (e){} }
// 426/W1.7: family names take «آل», not «ال» («استاد آل نهيان»), wherever a source spells it without the madda
const fixAl = s => String(s == null ? "" : s).replace(/(^|[\s«(>])ال (نهيان|مكتوم|قاسمي|نعيمي|معلا|شرقي|خليفة|ثاني|سعود|صباح)(?=$|[\s»),.،<])/g, "$1آل $2");
// QA 35/45/64/77: any player link still printing a Latin name gets the Arabic one from names/players_ar.json (one pass for every tile)
let PNAMES = null;
function write(rel, html){ if (ONLY && !ONLY.test("/" + rel)){ fs.mkdirSync(path.dirname(path.join(OUT, rel)), { recursive:true }); return; }   /* dev (TIFO_ONLY): the folder still exists for files written next to the page (cast/feed.xml) */ WRITTEN.add("/" + rel.replace(/index\.html$/, "").replace(/\.html$/, "")); html = fixHtml(html);
  if (/<body[^>]*data-page="match"/.test(html) || rel === "db/match/index.html" || rel === "live/index.html") html = html.replace(/<\/body>(?![\s\S]*<\/body>)/, (write.media = write.media || (() => { const js = fs.readFileSync(path.join(__dirname, "src/media.js"), "utf8"), v = hash(js); fs.mkdirSync(path.join(OUT, "assets"), { recursive:true }); fs.writeFileSync(path.join(OUT, `assets/media.${v}.js`), js); return `<script src="/assets/media.${v}.js" defer></script>`; })()) + "</body>");   // official videos by the goals and the match: src/media.js reads v1/media/<id>.json (news/media.py)
  const f = path.join(OUT, rel); fs.mkdirSync(path.dirname(f), { recursive:true }); if (SEARCH_V) html = html.replace("__SV__", SEARCH_V);   // pages written after the search index (404, offline) get its version too
  fs.writeFileSync(f, COLOR_V ? html.replace("__CV__", COLOR_V) : html); if (!COLOR_V) EARLY.push(f); ALLP.push(f); }
// the visible-text fixes every page gets (write() above; lib/world_stage.cjs's pages, written outside out/, too)
function fixHtml(html){
  // W2.10: «لـال» -> «لل», and ISO dates in visible text become Arabic dates
  html = html.replace(/(<body[\s\S]*)$/, b => b.replace(/(<script\b[\s\S]*?<\/script>)|>([^<>]*(?:لـ ?ال|\b20\d\d-\d\d-\d\d\b|\d\.0\b)[^<>]*)(?=<)/g, (m, sc, t) => sc ? m : ">" + t.replace(/(\d)\.0\b(?![.\d])/g, "$1").replace(/لـ ?ال/g, "لل").replace(/\b(20\d\d)-(\d\d)-(\d\d)\b/g, (_, y, mo, d) => `${+d} ${MON_AR[+mo - 1]} ${y}`)));
  if (PNAMES) html = html.replace(/(<body[\s\S]*)$/, b => b.replace(/(<script\b[\s\S]*?<\/script>)|<a\b([^>]*?)href="\/p\/(\d+)\/"([^>]*)>([^<]*)<\/a>/g, (m, sc, pre, id, post, txt) => { if (sc || /[\u0600-\u06FF]/.test(txt)) return m; const ar = PNAMES[id] && PNAMES[id].ar; return ar ? `<a${pre.replace(/\s*class="lat"/, "")}href="/p/${id}/"${post.replace(/\s*class="lat"/, "")}>${esc(ar)}</a>` : m; }));
  html = html.replace(/(<body[\s\S]*)$/, b => b.replace(/(<script\b[\s\S]*?<\/script>)|>([^<>]*ال (?:نهيان|مكتوم|قاسمي|نعيمي|معلا|شرقي|خليفة|ثاني|سعود|صباح)[^<>]*)(?=<)/g, (m, sc, t) => sc ? m : ">" + fixAl(t)));
  html = html.replace(/(<body[\s\S]*)$/, b => b.replace(/(<script\b[\s\S]*?<\/script>)|>([^<>]*(?:المجموعة [A-J]\b|\bGrp\b)[^<>]*)(?=<)/g, (m, sc, t) => { if (sc) return m; GRPS++; return ">" + t.replace(/المجموعة ([A-J])\b/g, (_, l) => R.groupOrd(l)).replace(/\bGrp\.?\s*([A-J])\b/g, (_, l) => R.groupOrd(l)).replace(/\bGrp\.?/g, "المجموعة"); }));
  html = html.replace(/(<body[\s\S]*)$/, b => b.replace(/(<script\b[\s\S]*?<\/script>|<style\b[\s\S]*?<\/style>)|>([^<>]+)(?=<)/g, (m, sc, t) => { if (sc || !LEAK.test(t)) return m; LEAK.lastIndex = 0; LEAKS++; return ">" + t.replace(LEAK, "").replace(/\s{2,}/g, " "); }));
  return html; }
const ALLP = [], OGJ = [];   // share-preview jobs for og.py (169)   // every page: the search index version is known only at the end, patched in then
const EARLY = [];   // pages written before the club colours were known: patched once COLOR_V exists
const hash = s => crypto.createHash("sha1").update(s).digest("hex").slice(0, 10);

const BUILT = new Date().toISOString(); let BCBY = {}; const FONTS = {};   // W1.1e: pages older than 2 min dim their live digits until the first good poll
let CC_V = "", ASSET_V = "", COLOR_V = "", SEARCH_V = "", BC_V = "", TV_V = "", DAYS_V = "", GS_V = "", ENG = {};
// W3.1: the stand at first paint — each hero's mosaic as a tiny PNG (1 px per card) inlined as a data URI, drawn pixelated under a
// 2 px night grid by CSS before any JS runs; the canvas takes over only for motion. Same bands, stripes and calm palette as keyart.js.
const zlib = require("zlib");
function pngURI(w, h, px){ const crcT = []; for (let n = 0; n < 256; n++){ let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; crcT[n] = c >>> 0; }
  const crc = buf => { let c = 0xffffffff; for (const x of buf) c = crcT[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const chunk = (t, d) => { const l = Buffer.alloc(4); l.writeUInt32BE(d.length); const td = Buffer.concat([Buffer.from(t), d]), c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([l, td, c]); };
  const raw = Buffer.alloc((w * 3 + 1) * h); for (let y = 0; y < h; y++){ raw[y * (w * 3 + 1)] = 0; for (let x = 0; x < w; x++){ const o = y * (w * 3 + 1) + 1 + x * 3, p = px[y * w + x]; raw[o] = p[0]; raw[o + 1] = p[1]; raw[o + 2] = p[2]; } }
  const ih = Buffer.alloc(13); ih.writeUInt32BE(w, 0); ih.writeUInt32BE(h, 4); ih[8] = 8; ih[9] = 2; ih[10] = 0; ih[11] = 0; ih[12] = 0;
  return "data:image/png;base64," + Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ih), chunk("IDAT", zlib.deflateSync(raw, { level:9 })), chunk("IEND", Buffer.alloc(0))]).toString("base64"); }
function mosaicURI(bands, seed){ const cols = 40, rows = 26, hex = c => { c = String(c || "#5C6660").replace("#", ""); if (c.length === 3) c = c.replace(/./g, "$&$&"); return [parseInt(c.slice(0, 2), 16), parseInt(c.slice(2, 4), 16), parseInt(c.slice(4, 6), 16)]; };
  const B = (bands && bands.length ? bands : [["#123A31", "#1B4A3F"]]).map(x => [hex(x[0]), hex(x[1] || x[0])]), nb = B.length; let s = seed || 7; const rnd = () => { s = (s * 16807) % 2147483647; return s / 2147483647; };
  const calm = (c, k) => { const g = (c[0] + c[1] + c[2]) / 3, n = [10, 38, 32], kk = 0.93 + (k - 0.93) * 0.5; return c.map((v, i) => { v = v + (g - v) * 0.3; v = v + (n[i] - v) * 0.35; return Math.max(0, Math.min(255, Math.round(v * kk))); }); };
  const px = []; for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++){ const bi = Math.min(nb - 1, Math.floor((cols - 1 - x) / cols * nb)), rel = (cols - 1 - x) - Math.floor(bi * cols / nb), base = B[bi][(rel + y) % 7 < 2 ? 1 : 0]; px.push(calm(base, 0.82 + rnd() * 0.22)); rnd(); }
  return pngURI(cols, rows, px); }
const MON_AR = ["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"];
const POS_AR = { GK:"حارس مرمى", CB:"قلب دفاع", LB:"ظهير أيسر", RB:"ظهير أيمن", LWB:"ظهير أيسر", RWB:"ظهير أيمن", DM:"وسط دفاعي", CDM:"وسط دفاعي", CM:"وسط", LM:"وسط أيسر", RM:"وسط أيمن", AM:"وسط هجومي", CAM:"وسط هجومي", LW:"جناح أيسر", RW:"جناح أيمن", ST:"مهاجم", CF:"مهاجم", SS:"مهاجم ثاني", DF:"مدافع", MF:"وسط", FW:"مهاجم", GOALKEEPER:"حارس مرمى", DEFENDER:"مدافع", MIDFIELDER:"وسط", FORWARD:"مهاجم", ATTACKER:"مهاجم" };
const LIVE_IDS = ["pnews", "whatif", "rpbtn", "rpreds", "rpr", "rpev", "wwbox", "kitct", "bdays", "storydata", "commbtn"];   // app.js wires these once at start-up
const isLiveSec = h => LIVE_IDS.some(id => h.includes('id="' + id + '"'));

// ================================================================ v5 shell (site/redesign/v5/DESIGN.md; the page() contract: ROLLOUT.md)
// Every page is the iOS-app skeleton: a compact nav bar (back · title · search · share), a large title or an entity header, one
// segmented control, grouped inset lists, a floating 5-tab bar, and sheets (<dialog>) for every secondary action. The big five
// templates (home, match, competition, team, player) and the tab pages render with src/v5/pages.js and pass `v5: {nav, body,
// tab, sheets}`; every other caller passes a v2/v3-shaped `body` (crumbs + h1 + season + <section class="blk">…) and
// lib/v5.cjs legacy5() turns it into the same skeleton. The SEO head (title, description, canonical or noindex, OG, JSON-LD,
// manifest) is the same for both and never depends on the template.
const U = require("./src/v5/ui.js"), P5 = require("./src/v5/pages.js");
// owner items 7, 8, 3 (docs/ENGAGEMENT.md): «نبّهني», «توقع وتحدى ربعك», «المعلقين»; their pure halves prerender here, the browser
// halves load on the pages that use them (page() below)
const NFM = require("./src/notify.js"), TPM = require("./src/predict.js"), VCM = require("./src/voices.js");
U.cfg.base = ""; U.cfg.pre = null;   // production: every entity has a page and links are paths (the dead-link pass unlinks the few that don't)
const V5 = require("./lib/v5.cjs")({ esc, U, LIVE_IDS });
let V5_V = { css:"", js:"", cfg:"", legacy:"" }, AUDIT = null, APPLE_SPLASH = "";   // v5 asset hashes; v1/audit/latest.json when the last data audit passed
// the page's own tools (buttons and links from the body's tool rows and o.tools) as rows of the «شارك» sheet, ids kept for app.js
const toolRows = h => String(h || "").replace(/<(button|a)\b([^>]*)>([\s\S]*?)<\/\1>/g, (m, tag, at, inner) => `<${tag}${at.replace(/\sclass="[^"]*"/, "")} class="row"><span class="rt">${inner}</span>${U.chev}</${tag}>`);
const NOLEGACY = new Set(["home", "daypage", "days", "all", "news", "mine", "more", "search", "comps", "db", "league", "none", "offline"]);   // pages that need none of render.js / app.js
// lib/world_stage.cjs's encyclopedia player pages (legacy bodies) still draw the v3 portrait
// the player's portrait: grey photo over the club colour (luminosity blend), the credit the CC BY licence asks for in small type
function phHtml(id, ph, col){
  const c = (col && col[0]) || "#1B4A3F", who = (ph.artist || "").replace(/\s+/g, " ").trim();
  return `<figure class="pph" style="--pc:${esc(c)}"><img src="/v1/ph/${id}.webp" alt="" width="400" height="500" fetchpriority="high"><figcaption><a href="${esc(ph.page || "")}" rel="noopener">${esc((who ? who.slice(0, 40) + " · " : "") + (ph.license || ""))}</a></figcaption></figure>`;
}
// o: {path, page, title, desc, noindex, og, ogv, ld, names, pp, attrs, nav, near, legacy, v5 | body (+ tools, lg, heroExtra), head, js}
// (site/redesign/v5/ROLLOUT.md §page): head = extra <head> HTML, js = extra script URLs (deferred, after the v5 and legacy bundles)
function page(o){
  if (ONLY && o.path && !ONLY.test(o.path + (o.path.endsWith("/") ? "index.html" : ""))) return "";   // dev only (TIFO_ONLY): a page that will not be written is not assembled
  const v = o.v5 || V5.legacy5(o), url = SITE + (o.path || "/");
  // W4.7: a match page carries the build stamp (and the stale-dimming script) only near kickoff; an old result or a far fixture is
  // byte-identical from build to build, so the hourly sync skips it
  const liveish = ["home", "match", "comp", "team", "daypage"].includes(o.page) && (o.page !== "match" || o.near !== false);
  const og = o.og || "tifo", tools = toolRows((v.tools != null ? v.tools : o.tools) || "");
  const share = /id="sh-share"/.test(v.sheets || "") ? "" : P5.shareSheet({ html:tools + `<button type="button" class="row" id="secpick"><span class="rt">صورة لأي قسم</span>${U.chev}</button>`, after:'<div id="secpicks" class="card mt" hidden></div>' });
  const sheets = (v.sheets || "") + share + P5.installSheet() + (o.page === "home" || o.page === "daypage" ? P5.onbSheet() : "");
  const legacy = !NOLEGACY.has(o.page) || o.legacy;
  // the build time only where the page reads it (v5 app.js: a live page's first poll, a team's fixtures, a table 30 min old): on
  // every page it made every page new every hour (2026-10-06: 30,631 of 34,300 files uploaded each build, 1-2 h each)
  const V5D = Object.assign({ page:o.page, id:null }, liveish ? { built:BUILT } : {}, v.data || {});
  return `<!doctype html><html lang="ar" dir="rtl"${liveish ? ` data-built="${BUILT}"` : ""}><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">${LITE.GUARD}${liveish ? '<script>(function(){var h=document.documentElement;if(Date.now()-Date.parse(h.dataset.built)>12e4)h.classList.add("stale")})()</script>' : ""}
<title>${esc(o.title)}</title><meta name="description" content="${esc(o.desc)}">${PREVIEW || o.noindex ? '<meta name="robots" content="noindex">' : `<link rel="canonical" href="${url}">`}
<meta property="og:title" content="${esc(o.title)}"><meta property="og:description" content="${esc(o.desc)}"><meta property="og:url" content="${url}"><meta property="og:locale" content="ar_AE"><meta property="og:site_name" content="تيفو">${og ? `<meta property="og:image" content="${SITE}/og/${og}.png${o.ogv ? "?v=" + o.ogv : ""}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image">` : ""}
<meta name="color-scheme" content="light dark"><meta name="theme-color" content="#F2F2F7" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-status-bar-style" content="default"><meta name="apple-mobile-web-app-title" content="تيفو">
<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="manifest" href="/manifest.webmanifest"><link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">${["home", "daypage", "all", "mine", "more"].includes(o.page) ? APPLE_SPLASH : ""}
<link rel="stylesheet" href="/assets/app.${V5_V.css}.css">${o.page === "match" || o.page === "messi" ? '<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"}}</script>' : ""}${(o.ld ? [].concat(o.ld) : []).map(l => `<script type="application/ld+json">${JSON.stringify(l).replace(/</g, "\\u003c")}</script>`).join("")}
<script type="speculationrules">{"prefetch":[{"source":"document","where":{"and":[{"href_matches":"/*"},{"not":{"href_matches":"/v1/*"}},{"not":{"href_matches":"/api/*"}}]},"eagerness":"moderate"},{"source":"document","where":{"selector_matches":".tabbar a"},"eagerness":"eager"}]}</script>${o.head || ""}</head>
<body data-page="${o.page}" data-v5="1" data-bc="${BC_V}"${R.DUPCTX ? ` data-dupctx="${esc(R.DUPCTX)}"` : ""}${o.attrs || ""}>
<a class="skip" href="#main">تخطَّ للمحتوى</a><a class="island" id="island" href="/" hidden aria-live="off"></a>
${U.nav(v.nav)}
<main id="main"${v.cls ? ` class="${v.cls}"` : ""}>${v.body}${/<footer class="foot"/.test(v.body) ? "" : U.foot()}</main>
${U.tabbar(v.tab != null ? v.tab : V5.tabOf(o))}
${sheets}<div class="toast" id="toast" role="status" aria-live="polite"></div><div id="alive" class="vh" aria-live="polite" aria-atomic="true"></div>
${o.names ? `<script>window.PN=${JSON.stringify(o.names).replace(/</g, "\\u003c")}${o.pp ? ";window.PP=" + JSON.stringify(o.pp) : ""}</script>` : ""}<script>window.V5=${JSON.stringify(V5D).replace(/</g, "\\u003c")}</script><script src="/assets/colors.__CV__.js" defer></script><script src="/assets/v5cfg.${V5_V.cfg}.js" defer></script><script src="/assets/app5.${V5_V.js}.js" defer></script>${legacy ? `<script src="/assets/legacy.${V5_V.legacy}.js" defer></script>` : ""}${o.page === "compare" ? `<script src="/assets/compare.${ASSET_V}.js" defer></script>` : ""}${o.page === "studio" ? `<script src="/assets/share.${ASSET_V}.js" defer></script>` : ""}${o.page === "lab" ? `<script src="/assets/lab.${ASSET_V}.js" defer></script>` : ""}${o.page === "messi" ? `<script src="/assets/messi.${ASSET_V}.js" defer></script>` : ""}${o.page === "world" ? `<script src="/assets/world.${ASSET_V}.js" defer></script>` : ""}${o.page === "live" ? `<script src="/assets/allmatches.${ASSET_V}.js" defer></script>` : ""}${TV_V && ["home", "match", "daypage", "tvc", "all", "live"].includes(o.page) ? `<script src="/assets/tv.${TV_V}.js" defer></script>` : ""}${o.page === "days" && DAYS_V ? `<script src="/assets/days.${DAYS_V}.js" defer></script>` : ""}${ENG.notify && ["team", "match"].includes(o.page) ? `<script src="${ENG.notify}" defer></script>` : ""}${ENG.predict && ["match", "predict"].includes(o.page) ? `<script src="${ENG.predict}" defer></script>` : ""}${ENG.voices && ["home", "daypage", "days", "all", "tvc", "voice", "more"].includes(o.page) ? `<script src="${ENG.voices}" defer></script>` : ""}${ENG.globe && ["home", "all"].includes(o.page) ? `<script src="${ENG.globe}" defer></script>` : ""}${[].concat(o.js || [], o.scripts || []).map(s => `<script src="${s}" defer></script>`).join("")}</body></html>`;
}
// the v3 tab strip and panes in v5 form (a segmented control and .pane sections); a lazy group's hidden panes are <template>s
// until first shown (W4.7), unless they hold a widget app.js wires at start-up
const tabsHtml = (group, list, sel) => U.segbar(group, list.map(t => [t[0], t[1]]), sel || list[0][0]);
const LAZYG = new Set(["tv", "lead"]);
const pane = (group, key, html, first) => `<section class="pane" data-g="${group}" data-p="${key}"${first ? "" : " hidden"}>${!first && LAZYG.has(group) && !isLiveSec(html) ? `<template class="lazyp">${html}</template>` : html}</section>`;

// ---- v3 building blocks (redesign/DESIGN-v3.md §3): sections -> v5 rows that open sheets (lib/v5.cjs secRows)
function blocks(html){
  const out = [], rest = []; let i = 0;
  while (i < html.length){
    const s = html.indexOf('<section class="blk"', i); if (s < 0){ rest.push(html.slice(i)); break; }
    rest.push(html.slice(i, s)); let d = 0, j = s; const re = /<(\/?)section\b[^>]*>/g; re.lastIndex = s; let m;
    while ((m = re.exec(html))){ d += m[1] ? -1 : 1; if (!d){ j = re.lastIndex; break; } }
    const full = html.slice(s, j), h2 = (full.match(/<h2>([\s\S]*?)<\/h2>/) || [])[1] || "";
    const title = h2.replace(/<small>[\s\S]*<\/small>/, "").replace(/<[^>]+>/g, "").trim(), sub = (h2.match(/<small>([\s\S]*)<\/small>/) || [])[1] || "";
    const id = (full.match(/^<section class="blk" id="([^"]+)"/) || [])[1] || "";
    out.push({ title, sub, id, full, cls:"blk", attrs:"", inner:full.replace(/^<section[^>]*>\s*<h2>[\s\S]*?<\/h2>/, "").replace(/<\/section>$/, "") }); i = j;
  }
  return { secs:out, rest:rest.join("") };
}
const stripT = h => h.replace(/<(script|style|template)[\s\S]*?<\/\1>/g, "").replace(/<[^>]+>/g, " ").replace(/&[a-z#0-9]+;/g, " ").replace(/\s+/g, " ").trim();
function teaser(sec){ const m = sec.inner.match(/<(li|p)\b[^>]*>([\s\S]*?)<\/\1>/); const t = m ? stripT(m[2]) : ""; if (!t || t.length < 8) return ""; return t.length > 90 ? t.slice(0, 88).replace(/\s\S*$/, "") + "…" : t; }
let PALETTE = [["#5C6660", "#F6F7F2"]];   // v3 tile colours (unused by v5; kept so older template code that sets it keeps working)
let SEQ = 0;
// blocks as one grouped list of rows that open sheets; o.feat shows that many and folds the rest under «كل … (N)»
function shelf(secs, o){
  o = o || {}; const sr = V5.secRows(secs.filter(sc => stripT(sc.inner).length > 2), { prefix:"s" }); if (!sr.n) return "";
  let rows = sr.rows;
  if (o.feat && sr.n > o.feat + 1){ const all = rows.split(/(?=<button type="button" class="row)/); rows = all.slice(0, o.feat).join("") + `<details class="dz rest"><summary class="row more-row">كل ${esc(o.title || "الأقسام")} <span class="num">(${sr.n})</span></summary><div class="sepd">${all.slice(o.feat).join("")}</div></details>`; }
  return U.grp(o.title || "بالتفصيل", rows, { cls:"shelfg" }) + sr.sheets;
}
const tabsBar = (group, list, sel) => U.segbar(group, list.map(t => [t[0], t[1]]), sel || list[0][0]);
const segBar = (group, list, sel) => '<div class="mt">' + U.seg(group, list.map(t => [t[0], t[1]]), sel || list[0][0], { sm:1 }) + "</div>";
// new pipeline files (2026-09-27): upsets, the Arab clubs rating, cup draws. Small renderers; each becomes a shelf tile
const tlink = id => `<a class="tl" href="/t/${id}/">${R.logo({ id }, "sm")}<span>${R.tname({ id:+id, name_ar:(S_TEAMS[id] || {}).name_ar || "", name:(S_TEAMS[id] || {}).name || "" })}</span></a>`;   /* QA 73: «الأهلي · مصر» vs «الأهلي · السعودية» */
let S_TEAMS = {};
function upsetsHtml(u){
  if (!u || !u.seasons) return ""; const all = []; for (const [se, list] of Object.entries(u.seasons)) (list || []).forEach(r => all.push(Object.assign({ season:se }, r)));
  if (!all.length) return ""; all.sort((a, b) => a.p_win - b.p_win);
  return '<ol class="facts-l">' + all.slice(0, 10).map(r => `<li>${tlink(r.winner)} فاز على ${tlink(r.loser)}${r.winner_home ? "" : " برا ملعبه"} وفرصته كانت <b class="num">${Math.round(r.p_win * 100)}%</b> <a class="muted small num" href="/m/${r.match}/">${esc(r.date || "")}</a></li>`).join("") + "</ol>";
}
function arabRankHtml(ar, ids){
  if (!ar || !ar.teams || !ids || !ids.length) return ""; const mine = ar.teams.filter(t => ids.includes(t.team)); if (!mine.length) return "";
  return '<div class="tblwrap"><table class="st"><thead><tr><th>عربياً</th><th style="text-align:start">النادي</th><th>التصنيف</th><th>آخر 5</th></tr></thead><tbody>' + mine.slice(0, 20).map(t => `<tr><td>${t.rank}</td><td class="tm">${tlink(t.team)}</td><td>${Math.round(t.rating)}</td><td><bdi dir="ltr">${t.change_5 > 0 ? "+" : ""}${Math.round(t.change_5 || 0)}</bdi></td></tr>`).join("") + "</tbody></table></div>";
}
function drawHtml(d){
  const cur = d && d.current; if (!cur) return ""; const gs = (cur.groups || []).filter(g => (g.teams || []).length), ts = cur.ties || [];
  if (!gs.length && !ts.length) return "";
  return gs.map((g, gi) => `<h3>${esc(R.groupOrd(g.name, gi))}</h3><ul class="facts-l">${g.teams.map(id => `<li>${tlink(id)}</li>`).join("")}</ul>`).join("") + (ts.length ? '<ul class="facts-l">' + ts.map(t => `<li>${tlink(t.home || t[0])} ضد ${tlink(t.away || t[1])}</li>`).join("") + "</ul>" : "");
}
// 402: one line icon per editorial topic (single colour), instead of the repeated mosaic mark
const EDI = {
  trophy:'<path d="M8 4h8v5a4 4 0 0 1-8 0V4zM8 6H5v1a3 3 0 0 0 3 3M16 6h3v1a3 3 0 0 1-3 3M12 13v4M8 20h8M9 17h6"/>',
  whistle:'<circle cx="9" cy="14" r="5"/><path d="M13 11l8-4v3l-6 3M9 14h.01"/>',
  cal:'<rect x="3" y="5" width="18" height="16"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  mic:'<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  tv:'<rect x="3" y="5" width="18" height="12"/><path d="M8 21h8M12 17v4"/>',
  flag:'<path d="M5 21V4h11l-2 4 2 4H5"/>',
  star:'<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
  chart:'<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  fire:'<path d="M12 3c1 4 5 5 5 10a5 5 0 0 1-10 0c0-3 2-4 2-7 2 1 3 3 3 5"/>',
  brush:'<path d="M4 20c3 0 5-2 5-5l9-9a2 2 0 0 0-3-3l-9 9c-3 0-5 2-5 5z"/>',
  ball:'<circle cx="12" cy="12" r="9"/><path d="M12 7l4 3-1.5 4.5h-5L8 10z"/>',
  gift:'<rect x="4" y="9" width="16" height="12"/><path d="M2 9h20M12 9v12M12 9c-2-4-6-4-6-1s6 1 6 1 6 2 6-1-4-3-6 1"/>',
};
// W2.1 (392): the pressure curve (md.momentum: [{minute, value}] or [value…], + = home, − = away), club colours via R.col
function momentumSvg(md){
  const raw = Array.isArray(md.momentum) ? md.momentum : md.momentum && Array.isArray(md.momentum.main) ? md.momentum.main : md.momentum && Array.isArray(md.momentum.data) ? md.momentum.data : null;
  if (!raw || raw.length < 5) return "";
  const pts = raw.map((p, i) => typeof p === "number" ? [i, p] : [p.minute != null ? +p.minute : i, +(p.value != null ? p.value : p.v)]).filter(p => isFinite(p[0]) && isFinite(p[1]));
  if (pts.length < 5) return ""; const W = 600, H = 120, mid = H / 2, maxX = Math.max(90, pts[pts.length - 1][0]), maxY = Math.max(1, ...pts.map(p => Math.abs(p[1])));
  const X = m => (W - m / maxX * W).toFixed(1), Y = v => (mid - v / maxY * (mid - 6)).toFixed(1);   // minute 0 on the right (RTL)
  const area = sign => "M" + X(pts[0][0]) + "," + mid + " " + pts.map(p => "L" + X(p[0]) + "," + Y(sign > 0 ? Math.max(0, p[1]) : Math.min(0, p[1]))).join(" ") + " L" + X(pts[pts.length - 1][0]) + "," + mid + "Z";
  return `<svg class="mom" viewBox="0 0 ${W} ${H}" role="img" aria-label="الضغط خلال المباراة"><path d="${area(1)}" fill="${R.col(md.home.id, 0)}" opacity=".85"/><path d="${area(-1)}" fill="${R.col(md.away.id, 0)}" opacity=".85"/><line x1="0" y1="${mid}" x2="${W}" y2="${mid}" stroke="#F6F7F24d"/></svg><p class="legend"><span><i style="background:${R.col(md.home.id, 0)}"></i>${R.tname(md.home)}</span><span><i style="background:${R.col(md.away.id, 0)}"></i>${R.tname(md.away)}</span></p>`;
}
function tformHtml(f){ const a = Array.isArray(f) ? f : String(f || "").split(""); const x = a.map(v => typeof v === "object" ? (v.result || v.r || "") : v).map(v => String(v).toUpperCase()[0]).filter(v => /[WDL]/.test(v)).slice(-5);
  return x.length ? `<p class="tform" aria-label="آخر ${x.length} مباريات">${x.map(v => `<i class="${v}">${({ W:"ف", D:"ت", L:"خ" })[v]}</i>`).join("")}</p>` : ""; }
function edIcon(t){ const k = /أساطير/.test(t) ? "trophy" : /قانون/.test(t) ? "whistle" : /هذا اليوم|التقويم|أيام/.test(t) ? "cal" : /كاست|بودكاست/.test(t) ? "mic" : /شاشة|المجلس/.test(t) ? "tv" : /منتخب|فترة/.test(t) ? "flag" : /مباراة الأسبوع|أحلى|لا تُنسى/.test(t) ? "star" : /أقوى|تصنيف|أرقام/.test(t) ? "chart" : /سلاسل/.test(t) ? "fire" : /ستوديو/.test(t) ? "brush" : /ذكرى|مواليد/.test(t) ? "gift" : "ball";
  return `<svg class="edi" viewBox="0 0 24 24" aria-hidden="true">${EDI[k]}</svg>`; }
const vpane = (group, key, html, first) => `<section class="pane" data-g="${group}" data-p="${key}"${first ? "" : " hidden"}>${html}</section>`;

(async () => {
  const t0 = Date.now();
  fs.rmSync(OUT, { recursive:true, force:true }); fs.mkdirSync(path.join(OUT, "assets"), { recursive:true });
  let css = fs.readFileSync(path.join(__dirname, "src/tifo.css"), "utf8"); const rjs = fs.readFileSync(path.join(__dirname, "src/render.js"), "utf8"), ajs = fs.readFileSync(path.join(__dirname, "src/app.js"), "utf8"), sjs = fs.readFileSync(path.join(__dirname, "src/stand.js"), "utf8"), cmp = fs.readFileSync(path.join(__dirname, "src/compare.js"), "utf8"), shr = fs.readFileSync(path.join(__dirname, "src/share.js"), "utf8"), p3d = fs.readFileSync(path.join(__dirname, "src/pitch3d.js"), "utf8"), m3d = fs.readFileSync(path.join(__dirname, "src/messi3d.js"), "utf8"), wjs = fs.readFileSync(path.join(__dirname, "src/world.js"), "utf8"), mjs = fs.readFileSync(path.join(__dirname, "src/messi.js"), "utf8"), labjs = fs.readFileSync(path.join(__dirname, "src/lab.js"), "utf8");
  // v3 (redesign/DESIGN-v3.md): v2's surfaces re-mapped for the night ground, then src/v3.css; v3.js / keyart.js / shell.js
  // W2.11: self-hosted font subsets (fonts/*.woff2, 68 KB together), hashed into /assets/
  for (const [k, f] of [["kufi", "kufi-800.woff2"], ["readex", "readex-400-600.woff2"], ["barlow", "barlow-700-digits.woff2"]]){ const buf = fs.readFileSync(path.join(__dirname, "fonts", f)), h = crypto.createHash("sha1").update(buf).digest("hex").slice(0, 10); FONTS[k] = `/assets/${f.replace(".woff2", "")}.${h}.woff2`; fs.writeFileSync(path.join(OUT, FONTS[k].slice(1)), buf); }
  css = `@font-face{font-family:"Noto Kufi Arabic";src:url(${FONTS.kufi}) format("woff2");font-weight:800;font-display:swap}@font-face{font-family:"Readex Pro";src:url(${FONTS.readex}) format("woff2");font-weight:400 600;font-display:swap}@font-face{font-family:"Barlow Condensed";src:url(${FONTS.barlow}) format("woff2");font-weight:700;font-display:swap}\n` + css;
  css += "\n" + fs.readFileSync(path.join(__dirname, "src/v3.css"), "utf8");   // W2.2: one role-based token set (v3.css :root); no regex re-map
  // W2.3 lint (warn only): live green, my-team dune and card colours used outside the selectors that mean them
  { const RULES = [[/var\(--(pulse|live|live-text)\)|#10A04B|#5BE08F/i, /live|pulse|cardflip|arr\.up|\.lt\b|ltable|\.ok\b|free|:root/i, "live"], [/var\(--(dune|mine)\)|#B07A3B/i, /mine|dune|on\b|pressed|selected|current|focus|spoil|\.x\b|pv\b|:root|tnext/i, "mine"], [/var\(--card-(y|r)\)|#F2C230|#D8343F/i, /card|yellow|red|ico|ev\b|bad|hot|miss|tl|:root|legend|zrel/i, "cards"]];
    const bad = []; css.replace(/([^{}]+)\{([^{}]*)\}/g, (m, sel, body) => { for (const [col, ok, name] of RULES) if (col.test(body) && !ok.test(sel)) bad.push(name + ": " + sel.trim().slice(0, 60)); return m; });
    if (bad.length) console.error(`warn: ${bad.length} colour-meaning slips in CSS (e.g. ${bad.slice(0, 4).join(" | ")})`); }
  const v3js = fs.readFileSync(path.join(__dirname, "src/v3.js"), "utf8"), kajs = fs.readFileSync(path.join(__dirname, "src/keyart.js"), "utf8"), shjs = fs.readFileSync(path.join(__dirname, "src/shell.js"), "utf8");
  const alljs = fs.readFileSync(path.join(__dirname, "src/allmatches.js"), "utf8"); css += "\n" + fs.readFileSync(path.join(__dirname, "src/allmatches.css"), "utf8");   // /all/ + /live/ (every match)
  css += "\n" + fs.readFileSync(path.join(__dirname, "src/seo.css"), "utf8");   // owner items 9-11 (2026-10-06): the day pages, the Arab leagues, the encyclopedia (v5 markup dressed for v3)
  ASSET_V = hash(css + rjs + ajs + sjs + cmp + shr + p3d + m3d + mjs + wjs + labjs + v3js + kajs + shjs + alljs); fs.writeFileSync(path.join(OUT, `assets/allmatches.${ASSET_V}.js`), alljs); fs.writeFileSync(path.join(OUT, `assets/v3.${ASSET_V}.js`), v3js); fs.writeFileSync(path.join(OUT, `assets/keyart.${ASSET_V}.js`), kajs); fs.writeFileSync(path.join(OUT, `assets/shell.${ASSET_V}.js`), shjs); fs.writeFileSync(path.join(OUT, `assets/lab.${ASSET_V}.js`), labjs); fs.writeFileSync(path.join(OUT, `assets/pitch3d.${ASSET_V}.js`), p3d); fs.writeFileSync(path.join(OUT, `assets/messi3d.${ASSET_V}.js`), m3d); fs.writeFileSync(path.join(OUT, `assets/messi.${ASSET_V}.js`), mjs); fs.writeFileSync(path.join(OUT, `assets/world.${ASSET_V}.js`), wjs); fs.writeFileSync(path.join(OUT, `assets/compare.${ASSET_V}.js`), cmp); fs.writeFileSync(path.join(OUT, `assets/share.${ASSET_V}.js`), shr);   // content-hashed file names: CloudFront's cache key ignores query strings
  fs.writeFileSync(path.join(OUT, `assets/tifo.${ASSET_V}.css`), css); fs.writeFileSync(path.join(OUT, `assets/render.${ASSET_V}.js`), rjs); fs.writeFileSync(path.join(OUT, `assets/app.${ASSET_V}.js`), ajs); fs.writeFileSync(path.join(OUT, `assets/stand.${ASSET_V}.js`), sjs);
  { const tv = fs.readFileSync(path.join(__dirname, "src/tv.js"), "utf8"); TV_V = hash(tv); fs.writeFileSync(path.join(OUT, `assets/tv.${TV_V}.js`), tv); }   // «منو يعلّق؟»: src/tv.js paints v1/tv/<ymd>.json (news/commentators.py) on match pages, day lists and /commentators/
  // ---- v5 assets (site/redesign/v5/ROLLOUT.md): one stylesheet (src/v5/app.css, then content.css: the old blocks' classes in v5
  // colours under .lc), the share images' three web fonts declared for the canvas (no element uses them, so a page never downloads
  // them), one deferred bundle (src/v5/ui.js + pages.js + app.js) and the legacy bundle (render.js + v3.js + app.js) that pages
  // with the old widgets load after it. Minified with esbuild when one is on the machine; the plain files work the same.
  { const ES = [process.env.ESBUILD, "esbuild", "C:/Users/requi/workspace/studio/Remotion_Studio/node_modules/esbuild"].filter(Boolean);
    let eb = null; for (const m of ES){ try { eb = require(m); break; } catch (e){} }
    const min = (js, define) => { if (!eb) return js; try { return eb.transformSync(js, { minify:true, target:"es2017", charset:"utf8", define:define || {} }).code; } catch (e){ console.error("v5: js not minified:", String(e.message).split("\n")[0]); return js; } };
    let c5 = fs.readFileSync(path.join(__dirname, "src/v5/app.css"), "utf8") + "\n" + fs.readFileSync(path.join(__dirname, "src/v5/content.css"), "utf8");
    { const seo = fs.readFileSync(path.join(__dirname, "src/seo.css"), "utf8"), cut = seo.indexOf("/* ---- v3 dress */");   // the search pages (items 9-11): seo.css's structure, then their v5 dress
      c5 += "\n" + (cut > 0 ? seo.slice(0, cut) : "") + "\n" + fs.readFileSync(path.join(__dirname, "src/v5/sx.css"), "utf8"); }
    c5 = `@font-face{font-family:"Noto Kufi Arabic";src:url(${FONTS.kufi}) format("woff2");font-weight:800;font-display:swap}@font-face{font-family:"Readex Pro";src:url(${FONTS.readex}) format("woff2");font-weight:400 600;font-display:swap}@font-face{font-family:"Barlow Condensed";src:url(${FONTS.barlow}) format("woff2");font-weight:700;font-display:swap}\n`
      + c5.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\n\s*/g, "\n").replace(/\n+/g, "\n");
    V5_V.css = hash(c5); fs.writeFileSync(path.join(OUT, `assets/app.${V5_V.css}.css`), c5);
    const j5 = min(["ui.js", "pages.js", "app.js"].map(f => fs.readFileSync(path.join(__dirname, "src/v5", f), "utf8")).join("\n;\n"), { __TIFO_BROWSER__:"true" });   // drops pages.js's build-time assemblers
    V5_V.js = hash(j5); fs.writeFileSync(path.join(OUT, `assets/app5.${V5_V.js}.js`), j5);
    const lj = min([rjs, v3js, ajs].join("\n;\n")); V5_V.legacy = hash(lj); fs.writeFileSync(path.join(OUT, `assets/legacy.${V5_V.legacy}.js`), lj);
    console.log(`v5 assets: css ${(zlib.gzipSync(c5).length / 1024).toFixed(1)} KB gz, app5 ${(zlib.gzipSync(j5).length / 1024).toFixed(1)} KB gz, legacy ${(zlib.gzipSync(lj).length / 1024).toFixed(1)} KB gz${eb ? "" : " (not minified)"}`); }
  { const dj = fs.readFileSync(path.join(__dirname, "src/days.js"), "utf8"); DAYS_V = hash(dj); fs.writeFileSync(path.join(OUT, `assets/days.${DAYS_V}.js`), dj); }   // owner item 9: the day pages' renderer, shared with lib/seo_days.cjs
  { const gj = fs.readFileSync(path.join(__dirname, "src/goalshare.js"), "utf8"); GS_V = hash(gj); fs.writeFileSync(path.join(OUT, `assets/goalshare.${GS_V}.js`), gj); }   // owner item 11: share one goal from its row
  { const w = f => { const j = fs.readFileSync(path.join(__dirname, `src/${f}.js`), "utf8"), v = hash(j); fs.writeFileSync(path.join(OUT, `assets/${f}.${v}.js`), j); return `/assets/${f}.${v}.js`; };
    ENG = { notify:w("notify"), predict:w("predict"), voices:w("voices"), mosaic:w("mosaic"), motm:w("motm"), globe:w("globe"), poster:w("poster"), trail:w("trail"), rewind:w("rewind"), scout:w("scout"), cam:w("cam"), coach:w("coach"), badges:w("badges"), mood:w("mood"), stream:w("stream") }; }   // items 7, 8, 3; «اصنع التيفو» (bold idea 1); «رجل المباراة بصوت الجمهور» (second list 2); «كل مباراة لوحة فنية» (bold idea 10)
  // the mark: a 3x3 tifo of cards (chalk, pulse, dune on night pitch)
  // the mark: v5's 3x3 «tifo» of rounded cards (white, two quiet, three light pitch green) on pitch green (site/redesign/v5/icons.py)
  const cellsSvg = ["#fff", "#7CF0B4", "#ffffff70", "#fff", "#ffffff70", "#7CF0B4", "#7CF0B4", "#fff", "#fff"].map((c, i) => `<rect x="${7 + (i % 3) * 6.5}" y="${7 + Math.floor(i / 3) * 6.5}" width="5.4" height="5.4" rx="1.3" fill="${c}"/>`).join("");
  fs.writeFileSync(path.join(OUT, "favicon.svg"), `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#0B8246"/>${cellsSvg}</svg>`);
  // iPhone launch screens for the pages people add to the home screen (light and dark, site/redesign/v5/icons.py)
  APPLE_SPLASH = [[1290, 2796, 430, 932, 3], [1206, 2622, 402, 874, 3], [1179, 2556, 393, 852, 3], [1170, 2532, 390, 844, 3], [1125, 2436, 375, 812, 3], [828, 1792, 414, 896, 2], [750, 1334, 375, 667, 2]].map(([w, h, dw, dh, r]) => ["light", "dark"].map(sc => `<link rel="apple-touch-startup-image" media="screen and (device-width:${dw}px) and (device-height:${dh}px) and (-webkit-device-pixel-ratio:${r}) and (orientation:portrait) and (prefers-color-scheme:${sc})" href="/icons/splash-${w}x${h}-${sc}.png">`).join("")).join("");

  const index = await get("index.json"); if (!index) throw new Error("no index.json from " + DATA);
  S._idx = index; const comps = index.competitions, today = new Date(Date.now() + 4 * 3600e3).toISOString().slice(0, 10);
  const urls = ["/", "/competitions/"], teamIds = new Set(), matchSum = new Map();
  const teamsJson = await get("teams.json"); S.setTeams(teamsJson && teamsJson.teams || {}); S_TEAMS = (teamsJson && teamsJson.teams) || {};
  // FotMob's own Arabic names (db/fotmob_profiles.py, from its Arabic site): the fallback for every club and player our curated names miss
  const FMN = Object.assign({ teams:{}, players:{}, comps:{}, countries:{} }, (await get("history/fm/names_ar.json")) || {});
  Object.entries(S_TEAMS).forEach(([k, t]) => { if (t && !t.name_ar && FMN.teams[k]) t.name_ar = FMN.teams[k]; });
  // 463 (owner 2026-09-30 «اللعيبة كل الصور»): free portraits from photos/build.py; only players whose photo passed the identity,
  // licence and face checks are in the index, the rest keep the plain hero
  const PH = ((await get("ph/index.json")) || {}).players || {};

  // ---- 1. fetch: competitions (+ every analytics file the pipeline may have written), today, national
  const EXTRA = ["sim", "watch", "bump", "halftime", "xg", "clutch", "cards", "foreigners", "improved", "young-uae", "team-of-round", "minute-clock", "goal-bands", "referees", "lineup-ages", "rotation", "pressure", "style", "fortress", "records", "alltime", "facts", "players", "similar", "tournament-sim", "scenarios", "shots", "fatigue", "coaches", "transfers", "records-book", "seasons", "milestones", "upsets", "projections", "bracket-sim", "local-minutes", "suspensions", "first-goal", "dropped", "dependence", "xi", "signings", "absences", "alltime-table", "promoted", "late-goals", "champion-path", "games-in-hand", "attendance"];
  // phase 5: generated content (ai/gen.py) is published only for kinds the owner approved (ai/approved.json)
  const APPROVED = JSON.parse(fs.readFileSync(path.join(__dirname, "ai/approved.json"), "utf8"));
  const AI = k => { const d = path.join(CACHE, "ai", k), o = {}; if (fs.existsSync(d)) for (const f of fs.readdirSync(d)) if (f.endsWith(".json")) o[f.slice(0, -5)] = JSON.parse(fs.readFileSync(path.join(d, f), "utf8")); return o; };
  const AIS = AI("summary"), AIP = AI("preview"), AIC = AI("podcast"), AID5 = AI("daily5"), AICM = AI("commentary"), AIDG = AI("digest"), AIPW = AI("power"), AIWHY = AI("why"), AIQK = AI("quick");
  const RSD = path.join(require("os").homedir(), "workspace/research/tifo-2026-09-27"), readRes = f => { try { return JSON.parse(fs.readFileSync(path.join(RSD, f), "utf8")); } catch (e){ return {}; } };
  const CLUBS = {}; Object.values((readRes("arab_clubs.json").clubs) || {}).forEach(c => { if (c.fotmob_id) CLUBS[c.fotmob_id] = c; });
  const SUSR = {}; Object.values(readRes("suspension_rules.json")).forEach(v => { if (v && v.fotmob_id) SUSR[v.fotmob_id] = v; });
  const ACC = {}; Object.values((readRes("club_accounts.json").entities) || {}).forEach(v => { if (v.fotmob_id) ACC[v.fotmob_id] = v; });
  const ATS = {}; Object.values((readRes("alltime_scorers.json").leagues) || {}).forEach(l => { if (l.fotmob_league_id) ATS[l.fotmob_league_id] = l; });
  // 204: where to watch per visitor country, compacted for the client: {ISO:{comp:[[name_ar, free, price, currency, url]], ...}}
  { const bbc = readRes("broadcast_by_country.json"), out = {}; for (const [iso, v] of Object.entries(bbc)){ if (iso === "_meta" || !v.competitions) continue; out[iso] = { _c:v.currency || "" }; for (const [k, c] of Object.entries(v.competitions)){ const key = /^dom_/.test(k) ? String(v.own_league_key) : k; out[iso][key] = { b:(c.broadcasters || []).map(x => [x.name_ar || x.name_en, x.free ? 1 : 0, x.price, x.currency, x.url, x.package_ar || ""]), q:c.confidence || "" }; } }
    // W1.2a: the UAE rows fall back to broadcast.json (the verified UAE list) wherever the per-country file has none (e.g. the Gulf Cup)
    { const bu = readRes("broadcast.json"); out.AE = out.AE || { _c:"AED" }; for (const [cid, e] of Object.entries(bu)){ if (cid === "_meta" || !e || e.disputed || !(e.broadcasters || []).length || (out.AE[cid] && out.AE[cid].b.length)) continue;   /* owner item 14: a row marked disputed (beIN on the AFC Challenge League) is never shown */ out.AE[cid] = { b:e.broadcasters.map(x => [x.name_ar || x.name_en, x.free ? 1 : 0, x.price_aed, "AED", x.url]), q:"broadcast.json" }; } }
    BCBY = out; const bj = JSON.stringify(out); BC_V = hash(bj); fs.writeFileSync(path.join(OUT, `assets/bc.${BC_V}.json`), bj); }
  let CLUB_AR = {}, REF_AR = {}; try { CLUB_AR = JSON.parse(fs.readFileSync(path.join(__dirname, "../names/clubs_ar.json"), "utf8")); } catch (e){} try { REF_AR = JSON.parse(fs.readFileSync(path.join(__dirname, "../names/referees_ar.json"), "utf8")); } catch (e){}
  const TAR = {}; for (const [id, v] of Object.entries(CLUB_AR)) if (v.ar) TAR[id] = v.ar; R.setClubNames(TAR);
  TAR_FILL = TAR; for (const [id, tm] of Object.entries((teamsJson && teamsJson.teams) || {})) if (tm && !tm.name_ar && TAR[id]) tm.name_ar = TAR[id];   // fetched before TAR existed
  const refAr = r => r && r.id && REF_AR[r.id] && REF_AR[r.id].ar ? REF_AR[r.id].ar : null;
  const BC = Object.fromEntries(Object.entries(readRes("broadcast.json")).filter(([k, e]) => !(e && e.disputed))),   // owner item 14: no disputed rows anywhere
    HLT = readRes("highlights.json"), STAD = {}; ((readRes("stadiums.json").stadiums) || []).forEach(x => { STAD[x.id] = x; });
  const compData = await pool(comps, 3, async c => {
    const [st, fx, stats] = await Promise.all([c.files && c.files.standings ? get(`comp/${c.id}/standings.json`) : null, get(`comp/${c.id}/fixtures.json`), get(`comp/${c.id}/stats.json`)]);
    const x = {}; await pool(EXTRA, 3, async k => { x[k] = await get(`comp/${c.id}/${k}.json`, 2); });
    x.draws = c.kind === "league" ? null : await get(`draws/${c.id}.json`, 1);
    // files the pipeline marks `available: false` (with a reason) render as one quiet note, never as an empty block
    // W1.4: a referee listed twice (once without an id, or spelled Al Harmoodi / Alharmoodi) becomes one row
    if (x.referees && x.referees.referees){ const nk = n => String(n || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z]/g, ""), keep = [];
      for (const r of x.referees.referees){ const twin = keep.find(k => nk(k.name) === nk(r.name)); if (!twin){ keep.push(r); continue; }
        const base = twin.id ? twin : r, other = base === twin ? r : twin; ["matches", "yellow", "second_yellow", "red", "penalties", "var"].forEach(f => { if (typeof other[f] === "number") base[f] = (base[f] || 0) + other[f]; });
        base.match_ids = [...new Set([].concat(base.match_ids || [], other.match_ids || []))]; if (base.matches) base.yellow_per_match = (base.yellow || 0) / base.matches; if (base !== twin) keep[keep.indexOf(twin)] = base; }
      x.referees.referees = keep; }
    if (x.referees && x.referees.referees) x.referees.referees.forEach(r => { if (r.id && REF_AR[r.id] && REF_AR[r.id].ar){ r.name_en = r.name; r.name = REF_AR[r.id].ar; } });
    x._na = []; for (const k of Object.keys(x)) if (x[k] && x[k].available === false){ x._na.push(k); x[k] = null; }
    return { c, st, fx, stats, x };
  });
  // 2026-09-28: a fixtures file that failed to fetch dropped its competition's matches in silence, and `sync --delete` then took
  // all 78 UAE match pages off the site (under the 15% page guard in deploy.sh). A competition the index counts matches for must bring them.
  { const lost = compData.filter(({ c, fx }) => (c.matches || 0) > 0 && !(fx && fx.matches && fx.matches.length)).map(({ c }) => c.id);
    if (lost.length){ console.error(`fixtures missing for competition ${lost.join(", ")}: not building, the live site keeps its last good build`); process.exit(3); } }
  const day = await get(`day/${today.replace(/-/g, "")}.json`) || { matches:[] };
  const arabRatings = await get("ratings/arab-clubs.json", 1);
  const [ratings, compare, fifa, qual, abroad, natRatings] = await Promise.all(["ratings/uae-clubs.json", "leagues/compare.json", "national/5789/fifa.json", "national/5789/qualifying.json", "national/uae-abroad.json", "ratings/national.json"].map(f => get(f, 1)));
  const h2hIdx = await get("h2h/index.json", 1), h2hKeys = h2hIdx ? Object.keys(h2hIdx.pairs) : [];
  const DERBIES = await get("derbies.json"); ((DERBIES && DERBIES.derbies) || []).forEach(d => { const k = String(d.h2h || "").replace(/^h2h\/|\.json$/g, ""); if (k && !h2hKeys.includes(k)) h2hKeys.push(k); });   // 209: the big Arab derbies get the same page
  const h2hData = await pool(h2hKeys, 8, k => get(`h2h/${k}.json`, 1)), H2H = {}; h2hKeys.forEach((k, i) => { if (h2hData[i]) H2H[k] = h2hData[i]; });
  let NAMES_AR = {}; try { NAMES_AR = JSON.parse(fs.readFileSync(path.join(__dirname, "../names/players_ar.json"), "utf8")); } catch (e){} for (const [k, v] of Object.entries(FMN.players || {})) if (!(NAMES_AR[k] && NAMES_AR[k].ar)) NAMES_AR[k] = Object.assign({}, NAMES_AR[k] || {}, { ar:v, source:"fotmob" }); PNAMES = NAMES_AR; R.PNAME = id => (NAMES_AR[id] || {}).ar || null;
  // coaches (names/coaches_ar.json) and stadiums (stadiums.yaml fotmob_name/name_en + research stadiums.json) in Arabic; Latin stays the fallback
  let COACH_AR = {}; try { COACH_AR = JSON.parse(fs.readFileSync(path.join(__dirname, "../names/coaches_ar.json"), "utf8")); } catch (e){}
  const coachAr = co => co && co.id && COACH_AR[co.id] && COACH_AR[co.id].ar ? COACH_AR[co.id].ar : null;
  S.setCoaches(COACH_AR);
  const VENUE_AR = {}; { const norm = v => String(v || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
    try { let cur = {}; for (const l of fs.readFileSync(path.join(__dirname, "../stadiums.yaml"), "utf8").split("\n")){ const m = l.match(/^\s*-?\s*(id|name_en|name_ar|fotmob_name):\s*(.+?)\s*(#.*)?$/); if (!m) continue; if (m[1] === "id"){ cur = {}; } cur[m[1]] = m[2]; if (cur.name_ar){ if (cur.name_en) VENUE_AR[norm(cur.name_en)] = cur.name_ar; if (cur.fotmob_name) VENUE_AR[norm(cur.fotmob_name)] = cur.name_ar; } } } catch (e){}
    ((readRes("stadiums.json").stadiums) || []).forEach(x => { if (x.name_ar && x.name_ar.value && x.name_en && x.name_en.value) VENUE_AR[norm(x.name_en.value)] = VENUE_AR[norm(x.name_en.value)] || x.name_ar.value; });
    VENUE_AR.get = n => VENUE_AR[norm(n)] || null; }
  const allPlayers = {}; compData.forEach(({ c, x }) => { if (x.players && x.players.players) for (const [pid, pp] of Object.entries(x.players.players)) allPlayers[pid] = Object.assign({ comp:c.id }, pp); if (x.cards && x.cards.players) for (const [id, c] of Object.entries(x.cards.players)) allPlayers[id] = Object.assign({ name:c.name, team:c.team }, allPlayers[id] || {}); });
  S.setPlayers(allPlayers);
  for (const { st, fx } of compData){
    (fx && fx.matches || []).forEach(m => { matchSum.set(m.id, m); [m.home, m.away].forEach(t => { if (t && t.id) teamIds.add(t.id); }); });
    (st && st.groups || []).forEach(g => g.rows.forEach(r => teamIds.add(r.team.id)));
  }
  (day.matches || []).forEach(m => { if (!matchSum.has(m.id)) matchSum.set(m.id, m); [m.home, m.away].forEach(t => { if (t && t.id) teamIds.add(t.id); }); });
  // QA 10: an h2h file often lacks the pair's latest meetings (via_match and anything since); add the finished ones we hold and count them
  { const byPair = {}; for (const m of matchSum.values()){ if (!m || !m.home || !m.away || m.status !== "finished" || !m.score) continue; const k = [m.home.id, m.away.id].sort((a, b) => a - b).join("-"); (byPair[k] = byPair[k] || []).push(m); }
    for (const [k, h] of Object.entries(H2H)){ const have = new Set((h.matches || []).map(m => m.id)), add = (byPair[k] || []).filter(m => !have.has(m.id)); if (!add.length) continue; h.wins = Object.assign({}, h.wins || {});
      add.forEach(m => { const w = m.score.home > m.score.away ? m.home.id : m.score.home < m.score.away ? m.away.id : "draws"; h.wins[w] = (h.wins[w] || 0) + 1; });
      h.matches = (h.matches || []).concat(add.map(m => ({ id:m.id, kickoff_utc:m.kickoff_utc, comp:m.comp, home:m.home, away:m.away, score:m.score, status:"finished" }))).sort((a, b) => String(b.kickoff_utc || "").localeCompare(String(a.kickoff_utc || ""))); } }
  // a fixture that still says live/ht 3 h after kickoff is stale input: take a non-live copy from the fresher files, or say nothing live
  const unstale = m => { if (!m || !R.isLive(m) || !(Date.now() - Date.parse(m.kickoff_utc) > 3 * 3600e3)) return m; const s = matchSum.get(m.id); return s && s !== m && !R.isLive(s) ? Object.assign({}, m, { status:s.status, score:s.score, minute:null }) : Object.assign({}, m, { status:"unknown", minute:null }); };
  day.matches = (day.matches || []).map(unstale); compData.forEach(d => { if (d.fx && d.fx.matches) d.fx.matches = d.fx.matches.map(unstale); });

  // ---- 2. logos (self-hosted copies) + club colours from them, before any page that paints colour
  fs.mkdirSync(path.join(CACHE, "logo"), { recursive:true }); fs.mkdirSync(path.join(OUT, "logo"), { recursive:true });
  const logoIds = new Set([...teamIds]); for (const m of matchSum.values()){ logoIds.add(m.home.id); logoIds.add(m.away.id); }
  let dl = 0;
  await pool([...logoIds], 8, async id => {
    const f = path.join(CACHE, "logo", id + ".png");
    if (!fs.existsSync(f)){ try { const r = await fetch(`https://images.fotmob.com/image_resources/logo/teamlogo/${id}.png`, { signal:AbortSignal.timeout(20000) }); if (r.ok){ fs.writeFileSync(f, Buffer.from(await r.arrayBuffer())); dl++; } } catch (e){} }
    if (fs.existsSync(f)) cpKeep(f, path.join(OUT, "logo", id + ".png"));
  });
  try { require("child_process").execFileSync("python3", [path.join(__dirname, "logo_colors.py")], { stdio:"ignore" }); } catch (e){ console.error("logo_colors.py failed; neutral colours"); }
  // W2.11: 96 px webp crests for rows (logo_webp.py caches them in cache/logo96)
  try { require("child_process").execFileSync("python3", [path.join(__dirname, "logo_webp.py")], { stdio:"ignore", timeout:300000 }); fs.mkdirSync(path.join(OUT, "logo/96"), { recursive:true }); for (const f of fs.readdirSync(path.join(CACHE, "logo96"))) cpKeep(path.join(CACHE, "logo96", f), path.join(OUT, "logo/96", f)); } catch (e){ console.error("logo_webp.py failed; rows fall back to png"); }
  let colors = {}; try { colors = JSON.parse(fs.readFileSync(path.join(CACHE, "colors.json"), "utf8")); } catch (e){}
  R.setColors(colors); R.H2HK = {}; Object.keys(H2H).forEach(k => { R.H2HK[k] = 1; });
  const ARABC = new Set(R.COUNTRIES.map(c => c[0])), ARABT = {};
  compData.forEach(({ c, st, fx }) => { const iso = R.compCountry(c); if (!(ARABC.has(iso) || [329, 10242, 11156, 10474].includes(c.id))) return; (fx && fx.matches || []).forEach(m => { ARABT[m.home.id] = 1; ARABT[m.away.id] = 1; }); (st && st.groups || []).forEach(g => g.rows.forEach(r => { ARABT[r.team.id] = 1; })); });
  // W2.4 country engine: iso2 -> national team (arabs/national.json), iso2 -> top league, and the tournament being played now
  const NATJ = await get("arabs/national.json", 1), NAT = {}; ((NATJ && NATJ.teams) || []).forEach(t => { if (t.iso2 && t.team) NAT[t.iso2] = t.team; }); if (!NAT.AE) NAT.AE = 5789;
  // owner item 9: «مباراة <فريق> اليوم» pages (lib/seo_days.cjs) for the biggest Arab and European clubs, Messi's, and every Arab national team
  const BIGT = [102117, 102111, 102119, 102124, 102101, 102122, 102123, 2529, 101918, 8577, 2530, 101919, 101916, 101745, 80591, 517894, 102049, 102050, 8153, 6366, 6353, 101895, 203826, 101656, 101659,
    8633, 8634, 9906, 8456, 8650, 10260, 9825, 8455, 9823, 9847, 9885, 8564, 8636, 960720].concat(Object.values(NAT).map(Number)), BIGS = new Set(BIGT);
  // W3.4: the UAE's first channel per competition (the prerender); the client swaps in the visitor's country
  const CHN_AE = {}; for (const [cid, e] of Object.entries(BCBY.AE || {})) if (cid !== "_c" && e && e.b && e.b.length) CHN_AE[cid] = [e.b[0][0], e.b.some(x => x[1]) ? 1 : 0]; R.CHN = CHN_AE;
  // W2.7: clubs sharing an Arabic name carry their country
  const DUP = {}; { const by = {}; for (const [id, t] of Object.entries((teamsJson && teamsJson.teams) || {})) if (t.name_ar && !t.national) (by[t.name_ar] = by[t.name_ar] || []).push([id, t]); for (const list of Object.values(by)) if (list.length > 1 && new Set(list.map(x => (x[1].country || {}).iso2)).size > 1) list.forEach(([id, t]) => { if (t.country && t.country.name_ar) DUP[id] = t.country.name_ar; }); }
  R.setDup(DUP); R.DUPCTX = "";
  // 444: titles and descriptions take the plain Arabic name; the «· الإمارات» tag is for the page, not for Google
  const PN = t => (t && (t.name_ar || TAR[t.id] || t.name)) || "";
  // 447: BreadcrumbList for Google (the visible crumbs stay the page's own)
  const bcLd = items => ({ "@context":"https://schema.org", "@type":"BreadcrumbList", itemListElement:items.filter(x => x && x[0]).map((x, i) => Object.assign({ "@type":"ListItem", position:i + 1, name:x[0] }, x[1] ? { item:SITE + x[1] } : {})) });
  // QA 5/17: «متوقفة» comes from the index; a competition with a kickoff from 3 days ago to 30 days ahead in its own fixtures is running
  { const now = Date.now(); compData.forEach(({ c, fx }) => { if (c.dormant && (fx && fx.matches || []).some(m => { const t = Date.parse(m.kickoff_utc); return t > now - 3 * 864e5 && t < now + 30 * 864e5; })) c.dormant = false; }); }
  // QA 6/39: a tournament simulation older than the competition's latest result is hidden until the pipeline re-runs it
  const simOk = (cid, sim) => { const g = sim && Date.parse(sim.generated); if (!g) return false; const d = compData.find(x => x.c.id === cid); return !((d && d.fx && d.fx.matches) || []).some(m => { const t = Date.parse(m.kickoff_utc) + 2 * 36e5; return m.status === "finished" && t > g && t < Date.now(); }); };
  const CL = {}; compData.forEach(({ c }) => { const iso = c.country && c.country.iso2; if (iso && c.kind === "league" && !CL[iso] && !c.dormant) CL[iso] = [c.key, c.name_ar]; });
  const NOWT = (() => { const now = Date.now(); for (const { c, fx } of compData){ if (c.kind === "league" || c.dormant) continue; if ((fx && fx.matches || []).some(m => Math.abs(Date.parse(m.kickoff_utc) - now) < 3 * 864e5)) return [c.key, c.name_ar]; } return null; })();
  // 2026-10-08: keys sorted, since every page links this file by its hash: NAT follows arabs/national.json's order, and IQ/TN
  // swapping places there re-uploaded all 30k pages. The browser reads these maps by key only
  const SJ = o => JSON.stringify(o && typeof o === "object" && !Array.isArray(o) ? Object.fromEntries(Object.entries(o).sort((a, b) => a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0)) : o);
  const cjs = "window.TC=" + SJ(colors) + ";window.H2HK=" + SJ(R.H2HK) + ";window.ARABT=" + SJ(ARABT) + ";window.TAR=" + SJ(TAR) + ";window.NAT=" + SJ(NAT) + ";window.DUP=" + SJ(DUP) + ";window.CHN_AE=" + SJ(CHN_AE) + ";window.CL=" + SJ(CL) + ";window.NOWT=" + SJ(NOWT) + ";"; COLOR_V = hash(cjs); fs.writeFileSync(path.join(OUT, `assets/colors.${COLOR_V}.js`), cjs);
  // ---- v5 renderer config (src/v5/ui.js U.cfg) for the prerender, and the shared browser config (assets/v5cfg.<hash>.js)
  { U.cfg.cn = {}; comps.forEach((c, i) => { U.cfg.cn[c.id] = [c.key, c.name_ar, (c.country && c.country.iso2) || "", i]; });
    U.cfg.cc = FMN.countries || {}; U.cfg.tc = colors; U.cfg.today = today; U.cfg.now = Date.now();
    const tn = Object.assign({}, FMN.teams || {}, TAR); for (const [k, t] of Object.entries(S_TEAMS)) if (t && t.name_ar) tn[k] = t.name_ar; U.cfg.tn = tn;
    const pn = {}; for (const [k, v] of Object.entries(NAMES_AR)) if (v && v.ar) pn[k] = v.ar; for (const [k, v] of Object.entries(COACH_AR)) if (v && v.ar) pn[k] = v.ar; U.cfg.pn = pn;
    U.injAr = n => (R.injAr ? R.injAr(n) : n); }
  // the daily data audit (published by db/audit.py's job as v1/audit/latest.json: {generated, ok, checked, errors, warnings}):
  // a quiet «الأرقام مدققة» with its time, only when the last audit passed; absent or failed, nothing is said. The footer keeps every
  // link the v3 footer had (crawl paths), as one quiet wrapped list
  { const a = await get("audit/latest.json", 1); AUDIT = a && a.ok === true && a.generated && !(a.errors > 0) ? a : null;
    // 2026-10-07: the badge is filled in the browser from v1/audit/latest.json (app.js): with its time in every page's footer, each
    // audit, and every flip between passed and failed, re-uploaded all 30k pages
    const badge = `<p class="audit" id="auditb" hidden></p>`;
    U.cfg.footer = badge + `<p><span class="updated" id="updated"></span> تيفو بدون مراهنات. البيانات من FotMob ورابطة المحترفين الإماراتية.</p>` +
      `<nav class="fnav" aria-label="روابط تيفو">${[["/", "اليوم"], ["/today/", "مباريات اليوم"], ["/tomorrow/", "مباريات بكرة"], ["/all/", "كل مباريات العالم"], ["/yesterday/", "نتائج أمس"], ["/matches/", "جدول المباريات"], ["/week/", "مباريات الأسبوع"], ["/countdowns/", "كم باقي؟"], ["/watch/", "وين تنقل"], ["/commentators/", "منو يعلّق"], ["/news/", "الأخبار"], ["/competitions/", "كل البطولات"], ["/c/uae-pro-league/", "دوري أدنوك"], ["/national/", "المنتخبات"], ["/arabs/", "العرب"], ["/db/", "موسوعة الأندية واللاعبين"], ["/legends/", "الأساطير"], ["/memorable/", "مباريات ما تنتسى"], ["/thisday/", "هذا اليوم"], ["/tv/", "شاشة المجلس"], ["/tv/?mine=1", "وضع المتابعة"], ["/studio/", "ستوديو التيفو"], ["/lab/", "المختبر"], ["/stadiums/", "الملاعب"], ["/laws/", "قانون الكورة"], ["/glossary/", "القاموس"], ["/cast/", "تيفو كاست"], ["/newsletter/", "النشرة"], ["/more/", "كل الصفحات"]].map(l => `<a href="${l[0]}">${l[1]}</a>`).join("")}</nav>` +
      `<p>من استوديو <a href="https://elyoxe.com/">Elyoxe</a></p>`; }
  // the shared browser config: competitions, the first-visit picks (Arab national teams + the leading clubs of each Arab league),
  // the countries with their time zones, the audit
  { const pick = [], seen = new Set(), add = (id, iso) => { id = +id; if (!id || seen.has(id)) return; const nm = (S_TEAMS[id] || {}).name_ar || TAR[id]; if (!nm) return; seen.add(id); pick.push([id, nm, iso || ""]); };
    const TOPN = { AE:14, SA:8, QA:6, EG:6, MA:4, KW:4, BH:3, OM:3, IQ:4, JO:3, DZ:4, TN:4 };
    R.COUNTRIES.forEach(c => { if (NAT[c[0]]) add(NAT[c[0]], c[0]); });
    R.COUNTRIES.forEach(c => { const d = compData.find(x => x.c.kind === "league" && x.c.country && x.c.country.iso2 === c[0] && x.st && x.st.groups && !x.st.composite); if (!d) return; (d.st.groups[0].rows || []).slice(0, TOPN[c[0]] || 3).forEach(r => add(r.team.id, c[0])); });
    { const cc = {}; compData.forEach(({ c, st }) => { const iso = c.country && c.country.iso2; if (!iso || c.kind !== "league" || cc[iso] || !st || st.composite || !st.groups || !st.groups[0]) return; const ids = st.groups[0].rows.map(r => r.team.id); if (ids.length) cc[iso] = ids.slice(0, 20).map(id => [id, (S_TEAMS[id] || {}).name_ar || TAR[id] || (S_TEAMS[id] || {}).name || ""]); });
      const cj = JSON.stringify(cc); CC_V = hash(cj); fs.writeFileSync(path.join(OUT, `assets/cc.${CC_V}.json`), cj); }   // every Arab league's clubs (the «فريقك» crest grid)
    // 2026-10-08: no page names this file any more. The v5 body carried its hash as data-ccm, read by no code (only the v3 shell.js
    // read data-cc, and v5 does not load it); the clubs come in table order, so each table move re-uploaded all 30k pages
    // 2026-10-07: only what moves rarely, since every page links this file by its hash: the teams to pick from move with the tables
    // (/picks.json, read when the picker opens) and the audit was read by no browser code
    const V5C = { cn:U.cfg.cn, countries:R.COUNTRIES.map(c => [c[0], c[1], c[2]]), share:ASSET_V };   // share: src/share.js, loaded on the first share image
    fs.writeFileSync(path.join(OUT, "picks.json"), JSON.stringify(pick));
    const vj = "window.V5C=" + JSON.stringify(V5C).replace(/</g, "\\u003c") + ";"; V5_V.cfg = hash(vj); fs.writeFileSync(path.join(OUT, `assets/v5cfg.${V5_V.cfg}.js`), vj); }

  const stIdsOf = st => st && !st.composite && st.groups && st.groups[0] ? st.groups[0].rows.map(r => r.team.id) : [];

  // competition logos (league_logos.py: FotMob league crests, dark variant preferred, cached in cache/leaguelogo) + their colours
  try { require("child_process").execFileSync("python3", [path.join(__dirname, "league_logos.py"), ...comps.map(c => String(c.id))], { stdio:"ignore", timeout:120000 }); } catch (e){ console.error("league_logos.py failed: mosaic fallback"); }
  let LCOL = {}; try { LCOL = JSON.parse(fs.readFileSync(path.join(CACHE, "league_colors.json"), "utf8")); } catch (e){}
  const LOGO = id => fs.existsSync(path.join(CACHE, "leaguelogo", id + ".png"));
  fs.mkdirSync(path.join(OUT, "lg"), { recursive:true }); comps.forEach(c => { if (LOGO(c.id)) cpKeep(path.join(CACHE, "leaguelogo", c.id + ".png"), path.join(OUT, "lg", c.id + ".png")); });
  const sat = h => { const n = parseInt(h.slice(1), 16), r = n >> 16, g = n >> 8 & 255, b = n & 255, mx = Math.max(r, g, b), mn = Math.min(r, g, b); return mx ? (mx - mn) / mx : 0; };
  const glow = id => { const cs = (LCOL[id] || []).slice().sort((a, b) => sat(b) - sat(a)); return [cs[0] && sat(cs[0]) > .25 ? cs[0] : "#F6F7F2", cs[1] && sat(cs[1]) > .25 ? cs[1] : (cs[0] && sat(cs[0]) > .25 ? cs[0] : "#5C7A70")]; };
  const scopeAr = { gulf:"الخليج", asia:"آسيا", europe:"أوروبا", arab:"العرب", africa:"أفريقيا", world:"العالم", national:"المنتخبات", uae:"الإمارات", americas:"الأمريكيتين" };
  const tileOf = c => { const sub = esc((c.country && c.country.name_ar) || scopeAr[c.scope] || "");
    if (LOGO(c.id)){ const g = glow(c.id); return `<a class="ct lgt" data-iso="${(c.country && c.country.iso2) || ""}" href="/c/${c.key}/" style="--g1:${g[0]};--g2:${g[1]}"><span class="cl" aria-hidden="true"><img src="/lg/${c.id}.png" alt="" loading="lazy" width="96" height="96"></span><b>${esc(c.name_ar)}</b><small>${sub}</small></a>`; }
    const d = compData.find(x => x.c.id === c.id) || {}; let tids = stIdsOf(d.st); if (!tids.length && d.fx && d.fx.matches) tids = [...new Set(d.fx.matches.flatMap(m => [m.home.id, m.away.id]))];
    const cols = tids.slice(0, 12).map(id => (colors[id] || ["#123A31"])[0]); while (cols.length && cols.length < 12) cols.push(...cols.slice(0, 12 - cols.length));
    return `<a class="ct" data-iso="${(c.country && c.country.iso2) || ""}" href="/c/${c.key}/"><span class="cm" aria-hidden="true">${(cols.length ? cols : Array.from({ length:12 }, (_, i) => ["#1B4A3F", "#123A31", "#2A5A4E"][i % 3])).map(cl => `<i style="background:${cl}"></i>`).join("")}</span><b>${esc(c.name_ar)}</b><small>${sub}</small></a>`; };
  // Arabic player names (names/players_ar.json) on player-shaped nodes only (ids are player ids here, never clubs)
  const nameOf = id => (NAMES_AR[id] || {}).ar || null;
  // transfer history (history/transfermarkt.py, Transfermarkt datasets CC0): a player's moves with fees, a club's record deals
  const TRH = (await get("history/transfers.json")) || { players:{}, clubs:{} };
  // every club's full history (db/history.py: results since 1888 + our FotMob archive); the tab loads its file in the browser
  const HIDX = ((await get("history/index.json")) || {}).clubs || {};
  // every club and squad player complete from FotMob (db/fotmob_profiles.py): trophies with seasons, stadium; bio of every player
  const FMT = ((await get("history/fm/teams.json")) || {}).teams || {}, FMPJ = (await get("history/fm/players.json")) || {}, FMP = FMPJ.players || {};
  const EAC = ((await get("ea/cards.json")) || {}).cards || {};   // EA SPORTS FC 27 cards matched to our players (db/eafc.py)
  const TMI = ((await get("history/tm/index.json")) || {}).players || {};   // players with a Transfermarkt record (db/tmdata.py)
  // Arabic Wikipedia's lead for players and clubs tied to a Wikidata item (db/wiki_ar.py)
  const WIKI = (await get("history/wiki_ar.json")) || {}, WP = WIKI.players || {}, WC = WIKI.clubs || {};
  const wikiHtml = w => w && w[1] ? `<p class="pwiki">${esc(w[1].length > 700 ? w[1].slice(0, w[1].lastIndexOf(" ", 690)) + "…" : w[1])} <a href="https://ar.wikipedia.org/wiki/${encodeURIComponent(w[0].replace(/ /g, "_"))}" rel="noopener">ويكيبيديا</a></p>` : "";
  // the bio fields FotMob leaves empty, from Transfermarkt (db/tmdata.py) and 365Scores (db/scores365.py, the Arab leagues)
  const FILL = Object.assign({}, ((await get("s365/fill.json")) || {}).players || {});
  for (const [k, v] of Object.entries(((await get("history/tm/fill.json")) || {}).players || {})) FILL[k] = Object.assign({}, FILL[k] || {}, v);
  for (const [k, v] of Object.entries(FILL)){ const b = FMP[k]; if (!b) continue; for (const f of ["h", "foot", "contract", "mv", "shirt"]) if (b[f] == null && v[f] != null) b[f] = v[f]; }
  const FOOT = { left:"اليسرى", right:"اليمنى", both:"الثنتين" }, SURF = { grass:"عشب طبيعي", "artificial turf":"عشب صناعي", artificial:"عشب صناعي", hybrid:"عشب هجين" };
  const pbio = id => { const b = FMP[id]; if (!b) return "";
    // a birth date before 1900 is FotMob's placeholder (0001-01-01), not a date: no age from it (audit 2026-09-30: 190 pages said «العمر 2025 سنة»)
    const born = b.born && b.born >= "1900" ? b.born : null, age = born ? Math.floor((Date.now() - Date.parse(born)) / 31557600000) : null;
    const rows = [b.pos && ["المركز", esc(b.pos) + (b.pos2 && b.pos2.length ? `<span class="muted small"> · ${esc(b.pos2.filter(Boolean).join("، "))}</span>` : "")],
      born && ["العمر", `<span class="num">${age}</span> سنة <span class="muted small num">${esc(born)}</span>`], b.h && ["الطول", `<span class="num">${b.h}</span> سم`],
      b.foot && ["القدم", FOOT[b.foot] || esc(b.foot)], b.cc && ["الجنسية", esc((FMN.countries || {})[b.cc] || b.cc)], b.shirt && ["الرقم", `<span class="num">${b.shirt}</span>`],
      b.mv && ["القيمة السوقية", eur(b.mv)], b.contract && ["نهاية العقد", `<span class="num">${esc(b.contract.slice(0, 7))}</span>`], b.loan && ["الحالة", "معار"]].filter(Boolean);
    return rows.length ? `<dl class="pbio">${rows.map(r => `<div><dt>${r[0]}</dt><dd>${r[1]}</dd></div>`).join("")}</dl>` : ""; };
  const fmcard = id => { const c = FMT[id]; if (!c && !T365[id]) return "";
    const v = c && c.venue, wst = CCARD[id] && CCARD[id].stadium;
    const TRN = { "presidents cup":"كأس رئيس الدولة", "president's cup":"كأس رئيس الدولة", "agcff gulf champions league":"دوري أبطال الخليج للأندية", "gulf club champions cup":"كأس الخليج للأندية",
      "cup":"الكأس", "league cup":"كأس الرابطة", "super cup":"السوبر", "federation cup":"كأس الاتحاد", "crown prince cup":"كأس ولي العهد", "king cup":"كأس الملك", "emir cup":"كأس الأمير",
      "gulf cup of nations":"كأس الخليج" };
    // titles per competition (audit 2026-09-30): 365Scores' count for every competition 365 lists for the club, FotMob's for the
    // ones it doesn't (R.mergeTitles in src/render.js, shared with the encyclopedia). Our champions lists no longer raise a count
    // (they gave Al Ahli Jeddah 9 league titles for 3 and Zamalek 20 for 15), and the bigger total no longer wins wholesale
    // (that dropped FotMob-only titles such as Al Ain's 2001 Gulf Club Champions Cup).
    const fm0 = ((c && c.trophies) || []).filter(t => t.won > 0).map(t => Object.assign({}, t, { name:/[\u0600-\u06FF]/.test(t.name || "") ? t.name : (TRN[String(t.name || "").toLowerCase()] || t.name) }));
    const tro = R.mergeTitles(fm0, T365[id] || [], L365), use365 = tro.some(t => t.src === "365"), withFm = use365 && tro.some(t => t.src === "fm");
    const facts = v && v.name ? [`الملعب ${esc((wst && wst.ar) || v.name)}`, v.capacity && `<span class="num">${Number(v.capacity).toLocaleString("en")}</span> متفرج`, v.opened && `افتُتح <span class="num">${esc(String(v.opened))}</span>`,
      v.surface && SURF[String(v.surface).toLowerCase()], v.lat != null && `<a href="https://www.openstreetmap.org/?mlat=${v.lat}&mlon=${v.lon}#map=16/${v.lat}/${v.lon}" rel="noopener">على الخريطة</a>`].filter(Boolean) : [];
    return (facts.length ? `<p class="fmv">${facts.join(" · ")}</p>` : "") + (tro.length ? `<h3>ألقابه (<span class="num">${tro.reduce((a, t) => a + t.won, 0)}</span>)</h3><ul class="chon">${tro.map(t => `<li><b>${t.cid ? `<a href="${lgUrl(t.cid)}">${esc(t.name || "")}</a>` : esc(t.name || "")}</b> <span class="num">${t.won}</span><span class="muted small yrs">${esc(t.seasons.join("، "))}${t.runnerup ? ` · وصيف ${t.runnerup} مرات` : ""}</span></li>`).join("")}</ul><p class="src">${use365 ? `الألقاب من 365Scores، كل بطولة من أول موسم لها${withFm ? "، واللي ما عنده من FotMob" : ""}${facts.length ? "، والملعب من FotMob" : ""}. <a href="/db/team/?id=${M365[id]}">كل ألقابه في الموسوعة</a>` : "الألقاب والملعب من FotMob"}.</p>` : ""); };
  // the club's identity card from Wikidata (db/clubs.py): founded, stadium, city, nickname, every title by competition
  const CCARD = ((await get("history/clubs.json")) || {}).clubs || {};
  const UEFAIDX = new Set((((await get("history/uefa/index.json")) || {}).clubs) || []);   // clubs with a UEFA ranking history (db/uefa.py)
  const XGIDX = new Set((((await get("history/xg/index.json")) || {}).clubs) || []);   // clubs with Understat seasons (db/understat.py)
  // every competition's champions through history (db/champions.py: Wikidata + our archive's points table for recent seasons)
  const CHAMPS = {}; await pool(comps.map(c => c.id), 8, async id => { const d = await get(`history/champions/${id}.json`, 1); if (d && d.champions && d.champions.length) CHAMPS[id] = d; });
  // 365Scores (db/scores365.py): each linked club's titles in ~640 competitions, each site competition's champions from its first season
  const S365 = (await get("s365/fm.json")) || {}, T365 = S365.titles || {}, C365 = S365.comps || {}, M365 = S365.teams || {};
  const S365I = (await get("s365/index.json")) || {}, LG365 = new Set((S365I.comps || []).filter(c => c[5] >= 5 && !c[11]).map(c => c[0]));
  U.cfg.lgs = {}; LG365.forEach(id => { U.cfg.lgs[id] = 1; });   // v5 links: a competition with a champions page gets /db/league/<id>/, the others the browser-rendered one
  const lgUrl = id => LG365.has(+id) ? `/db/league/${id}/` : `/db/league/?id=${id}`, SID2F = Object.fromEntries(Object.entries(M365).map(([f, s]) => [s, +f]));
  const L365 = Object.fromEntries(Object.entries(C365).map(([f, x]) => [f, x.id]));   // FotMob competition id -> 365's, for R.mergeTitles
  // a season's END year from a title: «2019/2020» and «2019-20» -> 2020, «الإمارات 2021» -> 2021, «خليجي 26» -> null (db/champions.py end_year)
  const endYear = s => { const t = String(s == null ? "" : s), m = t.match(/(\d{4})\s*[\/\-–]\s*(\d{4}|\d{2})(?!\d)/);
    if (m){ const a = +m[1], b = m[2].length === 4 ? +m[2] : Math.floor(a / 100) * 100 + +m[2]; return b < a ? b + 100 : b; }
    const y = t.match(/\d{4}/g); return y ? +y[y.length - 1] : null; };
  // a competition's champions (audit 2026-09-30): 365Scores season by season; our list (db/champions.py + db/champions_wiki.py)
  // only fills the seasons 365 lacks inside 365's span — never before its first season, never a season it lists with no winner,
  // never when its seasons name no year («خليجي 26»). The longer list used to win outright, and ours was longer because of
  // duplicated and misplaced seasons (UAE league: «2020 شباب الأهلي», Shabab Al Ahli 13 titles for 9).
  // -> [{y, t (season as written), name, fid, sid (365 team), key, ours («wd» | «wiki» | «table») for our rows}], newest first
  const champRows = id => { const x = C365[id], d = CHAMPS[id];
    const ours = r => ({ y:+r[0], t:String(r[0]), name:r[2] || String(r[1]).replace(/^w:/, ""), fid:r[3], sid:null, key:r[3] ? "f" + r[3] : "q" + r[1], ours:r[4] || "wd" });
    if (!x) return d ? d.champions.map(ours).sort((a, b) => b.y - a.y) : [];
    const all = x.champions.map(r => ({ y:endYear(r[0]), t:r[0], name:r[1], fid:r[2], sid:r[4], key:r[2] ? "f" + r[2] : "s" + r[4], won:!!r[1] }));
    const rows = all.filter(r => r.won);
    if (d && all.length && all.every(r => r.y)){ const first = Math.min(...all.map(r => r.y)), have = new Set(all.map(r => r.y));
      for (const r of d.champions) if (+r[0] >= first && !have.has(+r[0])) rows.push(ours(r)); }
    return rows.sort((a, b) => (b.y || 0) - (a.y || 0)); };
  // 365's champion of each season by end year for «الدوري موسم بموسم»: [FotMob id, name], or null for a season 365 lists with no
  // winner (UAE 2019–20). The computed table's leader stays for the seasons 365 doesn't have (src/stats.js S.seasons).
  const realChamps = id => { const x = C365[id]; if (!x) return null; const o = {};
    for (const r of x.champions){ const y = endYear(r[0]); if (y) o[y] = r[1] ? [r[2], r[1]] : null; } return o; };
  // every season's top scorer and top assister since 2012 (db/scorers.py, Transfermarkt)
  const SCORERS = {}; await pool(comps.map(c => c.id), 8, async id => { const d = await get(`history/scorers/${id}.json`, 1); if (d && d.seasons && Object.keys(d.seasons).length) SCORERS[id] = d; });
  const scorersHtml = id => { const d = SCORERS[id]; if (!d) return "";
    const who = r => r ? (r[0] && allPlayers[r[0]] ? `<a href="/p/${r[0]}/">${esc(r[1])}</a>` : esc(r[1])) + ` <b class="num">${r[2]}</b>` : "—";
    return `<table class="tbl"><thead><tr><th>الموسم</th><th>الهداف</th><th>أكثر واحد صنع</th></tr></thead><tbody>${Object.entries(d.seasons).reverse().map(([s, v]) => `<tr><td class="num">${esc(s)}</td><td>${who(v.goals[0])}</td><td>${who(v.assists[0])}</td></tr>`).join("")}</tbody></table><p class="src">المصدر: Transfermarkt. الأهداف بدون العكسية.</p>`; };
  const champHtml = id => { const rows = champRows(id), x = C365[id]; if (!rows.length) return "";
    const star = r => x ? !!r.ours : r.ours === "table";   // under a 365 list, * marks the seasons ours filled
    const nm = r => r.fid && S_TEAMS[r.fid] ? `<a href="/t/${r.fid}/">${esc(S_TEAMS[r.fid].name_ar || r.name)}</a>` : r.sid ? `<a href="/db/team/?id=${r.sid}">${esc(r.name)}</a>` : esc(r.name || "");
    const cnt = new Map(); rows.forEach(r => { const e = cnt.get(r.key) || { r, n:0 }; e.n++; cnt.set(r.key, e); });
    const top = [...cnt.values()].sort((a, b) => b.n - a.n).slice(0, 10), mx = top.length ? top[0].n : 1, filled = rows.some(star);
    return `<ul class="bars">${top.map(e => `<li><span>${nm(e.r)}</span><i style="--w:${Math.round(e.n / mx * 100)}%"></i><b class="num">${e.n}</b></li>`).join("")}</ul>
<details class="chl"><summary>كل الأبطال من <span class="num">${esc(rows[rows.length - 1].t)}</span> (<span class="num">${rows.length}</span>)</summary><ol class="mlist cols">${rows.map(r => `<li><span class="num">${esc(r.t)}</span> ${nm(r)}${star(r) ? '<span class="muted small"> *</span>' : ""}</li>`).join("")}</ol></details>
<p class="src">${x ? `المصدر: 365Scores${filled ? "، و* مواسم ما عنده من ويكي داتا وويكيبيديا" : ""}. <a href="${lgUrl(x.id)}">صفحة الأبطال كاملة</a> فيها كل موسم${x.cols && x.cols.length ? " بنقاطه" : ""}.` : `المصدر: ويكي داتا وويكيبيديا${filled ? "، و* من جدول النقاط في أرشيف تيفو للمواسم اللي ما سجّلها أحد هناك" : ""}. ممكن تنقصها مواسم.`}</p>`; };
  const ccard = id => { const c = CCARD[id]; if (!c) return "";
    // friendlies, youth and reserve cups are out; a title listed twice (the same years under two items, e.g. «First Division» and
    // «Football League») counts once
    const JUNK = /gamper|herrera|juvenil|youth|junior|u-?1\d|u-?2[0-3]|reserve|b team|trofeo|trophée d|audi cup|emirates cup|carranza|colombino|summer|friendly|ودي|شباب|ناشئ/i, seen = new Set();
    const fmHas = (FMT[id] && (FMT[id].trophies || []).some(t => t.won > 0)) || !!T365[id], fmVen = FMT[id] && FMT[id].venue && FMT[id].venue.name;
    const st = fmVen ? null : c.stadium, hon = fmHas ? [] : Object.values(c.honours || {}).filter(h => h.years && h.years.length && !JUNK.test((h.en || "") + " " + (h.ar || ""))).sort((a, b) => b.years.length - a.years.length)
      .filter(h => { const k = h.years.join(","); if (seen.has(k)) return false; seen.add(k); return true; });
    const facts = [c.founded && `تأسس <b class="num">${esc(c.founded)}</b>`, st && (st.ar || st.en) && `الملعب ${esc(st.ar || st.en)}${st.capacity ? ` (<span class="num">${st.capacity.toLocaleString("en")}</span> متفرج)` : ""}`, c.city && `المدينة ${esc(c.city)}`, c.nick && c.nick.length && `يلقبونه ${esc(c.nick.join("، "))}`].filter(Boolean);
    const SOC = { instagram:["إنستقرام", v => `https://www.instagram.com/${v}/`], x:["إكس", v => `https://x.com/${v}`], facebook:["فيسبوك", v => `https://www.facebook.com/${v}`],
      youtube:["يوتيوب", v => `https://www.youtube.com/channel/${v}`], tiktok:["تيك توك", v => `https://www.tiktok.com/@${v}`] };
    const links = [c.web && `<a href="${esc(c.web)}" rel="noopener nofollow">موقعه الرسمي</a>`].concat(Object.entries(c.social || {}).filter(([k]) => SOC[k]).map(([k, v]) => `<a href="${esc(SOC[k][1](encodeURIComponent(v)))}" rel="noopener nofollow">${SOC[k][0]}</a>`)).filter(Boolean);
    return `<div class="ccard">${facts.length ? `<p>${facts.join(" · ")}</p>` : ""}${links.length ? `<p class="clinks">${links.join(" · ")}</p>` : ""}${hon.length ? `<h3>ألقابه (<span class="num">${hon.reduce((a, h) => a + h.years.length, 0)}</span>)</h3><ul class="chon">${hon.map(h => `<li><b>${esc(h.ar || h.en || "")}</b> <span class="num">${h.years.length}</span><span class="muted small yrs">${esc(h.years.join("، "))}</span></li>`).join("")}</ul>` : ""}<p class="src">من ويكي داتا.</p></div>`; };
  const eur = v => v == null ? "—" : v === 0 ? "مجاناً" : v >= 1e6 ? `<span class="num">€${Math.round(v / 1e5) / 10}</span> مليون` : `<span class="num">€${Math.round(v / 1e3)}</span> ألف`;
  // v5 team pages: the same club card as fmcard() + ccard(), as rows — titles (R.mergeTitles: 365Scores where it lists the
  // competition, FotMob for the rest; Wikidata's honours only when neither has titles), the stadium, founded, city, nicknames, links
  const club5 = id => { const c = FMT[id], cc = CCARD[id], v = c && c.venue, wst = cc && cc.stadium, card = [];
    const TRN = { "presidents cup":"كأس رئيس الدولة", "president's cup":"كأس رئيس الدولة", "agcff gulf champions league":"دوري أبطال الخليج للأندية", "gulf club champions cup":"كأس الخليج للأندية", "cup":"الكأس", "league cup":"كأس الرابطة", "super cup":"السوبر", "federation cup":"كأس الاتحاد", "crown prince cup":"كأس ولي العهد", "king cup":"كأس الملك", "emir cup":"كأس الأمير", "gulf cup of nations":"كأس الخليج" };
    const fm0 = ((c && c.trophies) || []).filter(t => t.won > 0).map(t => Object.assign({}, t, { name:/[؀-ۿ]/.test(t.name || "") ? t.name : (TRN[String(t.name || "").toLowerCase()] || t.name) }));
    let tro = c || T365[id] ? R.mergeTitles(fm0, T365[id] || [], L365).map(t => [t.name || "", t.won, (t.seasons || []).slice(), t.cid ? lgUrl(t.cid) : null]) : [];
    const use365 = c || T365[id] ? R.mergeTitles(fm0, T365[id] || [], L365).some(t => t.src === "365") : false;
    let src = tro.length ? (use365 ? "الألقاب من 365Scores، كل بطولة من أول موسم لها، واللي ما عنده من FotMob." : "الألقاب من FotMob.") : "";
    if (!tro.length && cc && cc.honours){ const JUNK = /gamper|herrera|juvenil|youth|junior|u-?1\d|u-?2[0-3]|reserve|b team|trofeo|trophée d|audi cup|emirates cup|carranza|colombino|summer|friendly|ودي|شباب|ناشئ/i, seen = new Set();
      tro = Object.values(cc.honours).filter(h => h.years && h.years.length && !JUNK.test((h.en || "") + " " + (h.ar || ""))).sort((a, b) => b.years.length - a.years.length).filter(h => { const k = h.years.join(","); if (seen.has(k)) return false; seen.add(k); return true; }).map(h => [h.ar || h.en || "", h.years.length, h.years.map(String), null]);
      if (tro.length) src = "الألقاب من ويكي داتا."; }
    if (cc && cc.founded) card.push({ t:"تأسس", v:`<span class="num">${esc(cc.founded)}</span>` });
    const vn = v && v.name ? (wst && wst.ar) || v.name : wst && (wst.ar || wst.en), cap = (v && v.capacity) || (wst && wst.capacity);
    if (vn) card.push({ t:"الملعب", v:esc(vn) + (cap ? ` · <span class="num">${Number(cap).toLocaleString("en")}</span>` : ""), href:v && v.lat != null ? `https://www.openstreetmap.org/?mlat=${v.lat}&mlon=${v.lon}#map=16/${v.lat}/${v.lon}` : null, ext:1 });
    if (v && v.surface && SURF[String(v.surface).toLowerCase()]) card.push({ t:"الأرضية", v:SURF[String(v.surface).toLowerCase()] });
    if (cc && cc.city) card.push({ t:"المدينة", v:esc(cc.city) });
    if (cc && cc.nick && cc.nick.length) card.push({ t:"يلقبونه", v:esc(cc.nick.slice(0, 3).join("، ")) });
    if (cc && cc.web) card.push({ t:"موقعه الرسمي", href:cc.web, ext:1, icon:"globe", c:"#0A84FF" });
    const SOC = { instagram:["إنستقرام", v => `https://www.instagram.com/${v}/`], x:["إكس", v => `https://x.com/${v}`], facebook:["فيسبوك", v => `https://www.facebook.com/${v}`], youtube:["يوتيوب", v => `https://www.youtube.com/channel/${v}`], tiktok:["تيك توك", v => `https://www.tiktok.com/@${v}`] };
    Object.entries((cc && cc.social) || {}).filter(([k]) => SOC[k]).forEach(([k, s]) => card.push({ t:SOC[k][0], href:SOC[k][1](encodeURIComponent(s)), ext:1, icon:"link", c:"#8E8E93" }));
    return { tro, src:src + (M365[id] && use365 ? ` <a href="/db/team/?id=${M365[id]}">كل ألقابه في الموسوعة</a>` : ""), card, extra:"" }; };
  // Arabic Wikipedia's lead, cut at a word near 520 characters, with its link (wikiHtml() in v5 form)
  const wiki5 = w => w && w[1] ? esc(w[1].length > 520 ? w[1].slice(0, w[1].lastIndexOf(" ", 510)) + "…" : w[1]) + ` <a href="https://ar.wikipedia.org/wiki/${encodeURIComponent(w[0].replace(/ /g, "_"))}" rel="noopener">ويكيبيديا</a>` : "";
  const clubCell = (nm, id) => { const t = id && S_TEAMS[id]; return t ? `<a href="/t/${id}/">${esc(t.name_ar || t.name)}</a>` : `<span class="lat">${esc(nm)}</span>`; };
  const trPlayer = id => { const mv = (TRH.players || {})[id]; if (!mv || !mv.length) return "";
    return `<table class="tbl trh"><thead><tr><th>التاريخ</th><th>من</th><th>إلى</th><th>المبلغ</th><th>قيمته وقتها</th></tr></thead><tbody>${mv.slice().reverse().map(m => `<tr><td class="num">${esc(m[0])}</td><td>${clubCell(m[2], m[3])}</td><td>${clubCell(m[4], m[5])}</td><td>${eur(m[6])}</td><td>${m[7] ? eur(m[7]) : "—"}</td></tr>`).join("")}</tbody></table>`; };
  const trClub = id => { const c = (TRH.clubs || {})[id]; if (!c || !(c.in.length || c.out.length)) return "";
    const row = (r, other) => `<li>${r[1] && allPlayers[r[1]] ? `<a href="/p/${r[1]}/">${esc(nameOf(r[1]) || r[2])}</a>` : esc(nameOf(r[1]) || r[2])} · ${eur(r[3])} · <span class="muted small">${other} ${clubCell(r[4], r[5])}، <span class="num">${esc(r[0].slice(0, 4))}</span></span></li>`;
    return (c.in.length ? `<h3>أغلى من جابهم</h3><ol class="trc">${c.in.slice(0, 5).map(r => row(r, "من")).join("")}</ol>` : "") + (c.out.length ? `<h3>أغلى من باعهم</h3><ol class="trc">${c.out.slice(0, 5).map(r => row(r, "إلى")).join("")}</ol>` : "") + '<p class="src">المبالغ من Transfermarkt.</p>'; };
  { const pn = {}; for (const [k, v] of Object.entries(NAMES_AR)) if (v.ar) pn[k] = v.ar; for (const [k, v] of Object.entries(COACH_AR)) if (v.ar) pn[k] = v.ar; R.setNames(pn); }   // the prerender uses the same Arabic names as the client
  for (const [pid, p] of Object.entries(allPlayers)) if (nameOf(pid) && !p.name_en){ p.name_en = p.name; p.name = nameOf(pid); }
  compData.forEach(({ x, stats }) => { if (x.cards && x.cards.players) for (const [id, cc] of Object.entries(x.cards.players)) if (nameOf(id)) cc.name = nameOf(id);
    if (stats && stats.lists) for (const l of Object.values(stats.lists)) (l || []).forEach(r => { if (r.player && nameOf(r.player.id)) r.player.name = nameOf(r.player.id); }); });
  // ---- 3. competition pages
  const factsByMatch = {}, probsByMatch = {}, compX = {};
  for (const { c, st, fx, stats, x } of compData){
    R.DUPCTX = (c.country && c.country.name_ar) || "";   // 503: a league's own page drops its country's tag
    compX[c.id] = x;
    if (x.facts && x.facts.matches) Object.assign(factsByMatch, x.facts.matches);
    let rounds = "";
    if (fx && fx.matches && fx.matches.length){ const rr = R.rounds(fx), cur = fx.next_round && rr.by[fx.next_round] ? fx.next_round : (rr.order.find(k => rr.by[k].some(m => m.status !== "finished")) || rr.order[rr.order.length - 1]); rounds = `<div class="chips">` + rr.order.map(k => `<button type="button" data-r="${esc(k)}"${k === cur ? ' aria-pressed="true"' : ""}>${R.roundChip(k)}</button>`).join("") + `</div><div id="roundlist">${R.roundList(rr.by[cur] || [])}</div>`; }
    const has = { table: !!(st && st.groups && st.groups.length), stats: !!(stats && stats.lists) };
    // v3 competition page (DESIGN-v3.md): logo hero, 5 tabs, one lead block per tab, every other section a shelf tile
    SEQ = 0; const ids = stIdsOf(st); PALETTE = ids.map(id => colors[id]).filter(Boolean); if (!PALETTE.length) PALETTE = [["#5C6660", "#F6F7F2"]];
    const vars = has.table && !st.composite ? S.tables(st, x.halftime, x.xg) : [];
    if (has.table && !st.composite){ const ft = S.formTable(fx, st), gh = S.gamesInHand(st); if (ft) vars.push(["form", "الفورمة", ft]); if (gh) vars.push(["hand", "المؤجلة", gh]); }
    const tableLead = has.table ? (vars.length ? segBar("tv", [["all", "الكل"]].concat(vars.map(v => [v[0], v[1]]))) + pane("tv", "all", `<div id="table">${R.standings(st)}</div>`, true) + vars.map(v => pane("tv", v[0], v[2])).join("") : `<div id="table">${R.standings(st)}</div>`) : "";
    const tableShelf = x.bump ? shelf(blocks(S.sec("رحلة الموسم", "", S.bump(x.bump))).secs, { title:"الموسم بالرسم" }) : "";
    const rmap = c.id === 538 ? S.ratingMap(ratings) : (x.ratings ? S.ratingMap(x.ratings) : {});
    const fdrHtml = st && !st.composite ? S.fdr(st, fx, rmap) : "", roadHtml = st && !st.composite ? S.roadTitle(st, fx, rmap, x.sim) : "";
    const clockHtml = S.seasonClock(fx, st, x.watch), projHtml = S.projections(stats, st);
    const nextR = (() => { if (!fx || !fx.matches) return []; const rr = R.rounds(fx), k = rr.order.find(k => rr.by[k].some(m => m.status === "scheduled" && m.probs)); return k ? rr.by[k].filter(m => m.status === "scheduled" && m.probs).map(m => ({ h:m.home.id, a:m.away.id, home:m.home.name_ar || m.home.name, away:m.away.name_ar || m.away.name, p:[m.probs.home, m.probs.draw, m.probs.away], ko:m.kickoff_uae, r:k })) : []; })();
    const powK = APPROVED.power ? Object.keys(AIPW).filter(k => k.startsWith(c.id + "-")).sort().pop() : null;
    const G = k => `<a href="/glossary/#${k}">شو يعني؟</a>`;
    const predSecs = blocks([clockHtml ? S.sec("ساعة الموسم", "", clockHtml) : "", roadHtml ? S.sec("الطريق للقب", "", roadHtml) : "", fdrHtml ? S.sec("صعوبة المباريات الياية", G("difficulty"), fdrHtml) : "", x.watch && fx ? S.sec("أحلى مباريات الجولة الياية", "", S.watch(x.watch, fx)) : "", S.whatif(fx, st) ? S.sec("شو لو؟", "", S.whatif(fx, st)) : "", x.sim && x.sim.teams ? S.sec("توقعات آخر الموسم", G("simulator"), S.sim(x.sim, st)) : "", st && st.magic ? S.sec("كم يحتاج فريقك؟", G("magic-number"), S.magic(st)) : "", x["tournament-sim"] && simOk(c.id, x["tournament-sim"]) ? S.sec("من بيفوز بالبطولة؟", "", S.tsim(x["tournament-sim"])) : "", projHtml ? S.sec("كم بيسجل الهدافين لآخر الموسم؟", "", projHtml) : "", st && st.bracket && st.bracket.length ? S.sec("شجرة البطولة", "", S.bracket(st, null)) : "", x.scenarios ? S.sec("حاسبة التأهل", "", S.groupCalc(x.scenarios)) : "", S.absences(x.absences) ? S.sec("غيابات الجولة" + (x.absences.round ? " " + esc(x.absences.round) : ""), "", S.absences(x.absences)) : "", S.gihFile(x["games-in-hand"]) ? S.sec("المباريات المؤجلة", G("games-in-hand"), S.gihFile(x["games-in-hand"])) : "", drawHtml(x.draws) ? S.sec("القرعة", "", drawHtml(x.draws)) : ""].join("")).secs;
    const leadP = predSecs.findIndex(sc => sc.title === "توقعات آخر الموسم"), predLead = leadP >= 0 ? predSecs.splice(leadP, 1)[0].full : "";
    const num = [
      ["cards", "بطاقات تيفو", S.cards(x.cards, 12)], ["clutch", "منو الحاسم؟", S.clutch(x.clutch)], ["tor", "تشكيلة الجولة", S.teamOfRound(x["team-of-round"])],
      ["foreign", "أفضل محترف أجنبي", S.foreigners(x.foreigners)], ["improved", "الأكثر تطوّر", S.improved(x.improved)], ["young", "المواهب الإماراتية تحت 23", S.young(x["young-uae"])],
      ["clock", "ساعة الأهداف", S.clock(x["minute-clock"])], ["late", "ملوك الدقايق الأخيرة", S.late(x["goal-bands"])],
      ["pressure", "ترمومتر المدربين", S.pressure(x.pressure)], ["style", "بصمة كل فريق", S.style(x.style)], ["fortress", "حصون الملاعب", S.fortress(x.fortress)], ["crowd", "الحضور الجماهيري", S.attendance(x.attendance)],
      ["fatigue", "مؤشر الإرهاق", S.fatigue(x.fatigue)], ["coaches", "أنجح المدربين في التاريخ", S.coachesLeague(x.coaches)],
      ["transfers", "سوق الانتقالات", S.transfers(x.transfers)], ["susp", "الإيقافات", S.suspensions(SUSR[c.id], x.suspensions)],
      ["refs", "الحكام", S.referees(x.referees)], ["ages", "أعمار التشكيلات", S.ages(x["lineup-ages"])], ["rot", "مؤشر التدوير", S.rotation(x.rotation)],
      ["fgoal", "منو يسجل أول؟", S.firstGoal(x["first-goal"])], ["dropped", "نقاط ضاعت ونقاط رجعت", S.dropped(x.dropped)], ["depend", "الاعتماد على الهداف", S.dependence(x.dependence)],
      ["late90", "أهداف بعد الدقيقة 90", S.lateGoals(x["late-goals"])], ["sign", "أحسن صفقات الموسم", S.signings(x.signings)], ["miles", "أرقام شخصية قريبة", S.milestones(x.milestones, ids)],
      ["upsets", "أكبر المفاجآت", upsetsHtml(x.upsets)], ["arabr", "ترتيبهم بين الأندية العربية", arabRankHtml(arabRatings, ids)],
      ["rating", "تصنيف تيفو للأندية", c.id === 538 ? S.ratingTable(ratings) : ""], ["world", "الدوري الإماراتي ضد العالم", c.id === 538 ? S.compare(compare, 538) : ""],
    ].filter(v => v[2]);
    const GL = { cards:"tifo-card", clutch:"clutch", pressure:"pressure-index", style:"ppda", rot:"rotation", fatigue:"fatigue", rating:"tifo-rating" };
    // W2.8 (owner item 3): overlapping tiles merge (late goals; the two club ratings), the all-time coaches tile moves to التاريخ,
    // and الأرقام shows 6 featured tiles plus «كل الأرقام (N)»
    const MERGE = [["late", "late90", "الأهداف المتأخرة"], ["rating", "arabr", "تصنيف تيفو للأندية"]], byK = Object.fromEntries(num.map(v => [v[0], v]));
    MERGE.forEach(([a, b, t]) => { if (byK[a] && byK[b]){ byK[a] = [a, t, (byK[a][1] === t ? "" : `<h3>${byK[a][1]}</h3>`) + byK[a][2] + `<h3>${byK[b][1]}</h3>` + byK[b][2]];   /* QA 86: no heading repeating the tile title */ delete byK[b]; } else if (!byK[a] && byK[b]) { byK[b] = [b, t === "الأهداف المتأخرة" ? byK[b][1] : t, byK[b][2]]; } });
    const allTime = byK.coaches; delete byK.coaches;
    const numSecs = num.filter(v => byK[v[0]]).map(v => byK[v[0]]).map(v => blocks(S.sec(v[1], GL[v[0]] ? G(GL[v[0]]) : "", v[2], "n-" + v[0])).secs[0]);
    const NA = { referees:"الحكام", "goal-bands":"توقيت الأهداف", shots:"التسديدات", xg:"الأهداف المتوقعة", "first-goal":"أول هدف" };
    const naNote = x._na && x._na.length ? `<p class="na">ما عندنا بيانات عن ${x._na.map(k => NA[k] || k).join("، ")} في هالبطولة.</p>` : "";
    // W3.12: «الأعلى تقييم» and «الحراس» join the scorers control, from comp/<id>/players.json (rating; clean sheets then saves)
    const PJ = x.players && x.players.players ? x.players : null, pMin = (PJ && PJ.min_minutes) || 270, pTeam = id => Object.assign({ id }, teamsJson.teams[id] || {});
    const pv = (p, k) => p.stats && p.stats[k] && p.stats[k].value;
    const ratedL = PJ ? Object.entries(PJ.players).filter(([, p]) => pv(p, "rating") && (p.minutes || 0) >= pMin).map(([id, p]) => ({ player:{ id:+id, name:p.name }, team:pTeam(p.team), value:+Number(pv(p, "rating")).toFixed(2), minutes:p.minutes })) : [];
    const keepL = PJ ? Object.entries(PJ.players).filter(([, p]) => pv(p, "saves") != null && (p.minutes || 0) >= pMin).map(([id, p]) => ({ player:{ id:+id, name:p.name }, team:pTeam(p.team), value:pv(p, "clean_sheet") || 0, saves:pv(p, "saves"), minutes:p.minutes })).sort((a, b) => b.value - a.value || b.saves - a.saves) : [];
    const scoreP = !!(has.stats && stats && stats.lists && (stats.lists.goals || []).length >= 3);   // 444: /c/<key>/scorers/
    const leadSegs = [["goals", "الهدافين"], ["assists", "صناع الأهداف"]].concat(ratedL.length >= 3 ? [["rated", "الأعلى تقييم"]] : [], keepL.length >= 2 ? [["keepers", "الحراس"]] : []);
    const numLead = has.stats ? segBar("lead", leadSegs) + pane("lead", "goals", `<div id="goals">${R.leaders(stats, "goals")}</div>` + (scoreP && stats.lists.goals.length > 20 ? `<p class="small"><a href="/c/${c.key}/scorers/">كل الهدافين</a></p>` : ""), true) + pane("lead", "assists", `<div id="assists">${R.leaders(stats, "assists")}</div>`) +
      (ratedL.length >= 3 ? pane("lead", "rated", R.leaders({ lists:{ rated:ratedL } }, "rated") + `<p class="src">متوسط تقييم FotMob للاعبين اللي لعبوا ${pMin} دقيقة أو أكثر.</p>`) : "") +
      (keepL.length >= 2 ? pane("lead", "keepers", R.leaders({ lists:{ keepers:keepL } }, "keepers") + `<p class="src">الرقم = مباريات بشباك نظيفة، للحراس اللي لعبوا ${pMin} دقيقة أو أكثر.</p>`) : "") : "";
    const derb = c.id === 538 ? S.derbyList(h2hIdx, H2H) : "";
    const histSecs = blocks((x["champion-path"] ? (h => h ? S.sec("طريق البطل", "", h) : "")(S.championPath(x["champion-path"])) : "") + (ATS[c.id] ? S.sec("الهدافين التاريخيين", "", S.alltimeScorers(ATS[c.id])) : "") + (h => h ? S.sec("الجدول التاريخي", "من " + esc((x["alltime-table"] || {}).since || ""), h) : "")(S.alltimeTable(x["alltime-table"])) + (h => h ? S.sec("الدوري موسم بموسم", "", h) : "")(S.seasons(x.seasons, c.season, realChamps(c.id))) + (h => h ? S.sec("الصاعدين هالموسم", "", h) : "")(S.promoted(x.promoted)) + (x.alltime ? S.sec("تاريخ الدوري", "من 1973", S.alltime(x.alltime)) : "") + (derb ? S.sec("سجل المواجهات بين الأندية", "", derb) : "") + (h => h ? S.sec("الأبطال عبر التاريخ", "", h) : "")(champHtml(c.id)) + (SCORERS[c.id] ? S.sec("هدّاف كل موسم", "من " + Object.keys(SCORERS[c.id].seasons)[0].slice(0, 4), scorersHtml(c.id)) : "") + (x.records && x.records.chases && x.records.chases.length ? S.sec("أرقام قياسية على المحك", "", S.records(x.records)) : "") + (x["records-book"] ? S.sec("كتاب الأرقام القياسية", "من " + esc(x["records-book"].since || ""), S.recordsBook(x["records-book"])) : "") + (allTime ? S.sec(allTime[1], "", allTime[2], "n-coaches") : "")).secs;
    // v5 competition page (src/v5/pages.js P.comp): each segment's v5 lead block (table in three views, rounds, scorers, title odds,
    // champions), and every other block of the v3 page as a row that opens it in a sheet (lib/v5.cjs secRows): same blocks, ids and
    // widgets as before, nothing dropped
    const tools = `${nextR.length ? `<button type="button" id="rpbtn">صورة توقعات الجولة ${esc(nextR[0].r)}</button>` : ""}${x.cards ? `<a href="/c/${c.key}/compare/">قارن بين لاعبين أو فريقين</a>` : ""}${powK ? `<a href="/c/${c.key}/power/">ترتيب القوة هالأسبوع</a>` : ""}${has.table ? `<button type="button" id="embedbtn" data-src="/embed/t/?c=${c.id}" data-h="560">ضمّن الترتيب في موقعك</button>` : ""}`;
    const tSecs = vars.map(v => ({ title:v[1] === "الفورمة" ? "ترتيب الفورمة" : v[1] === "المؤجلة" ? "المباريات المؤجلة في الترتيب" : "الترتيب " + v[1], sub:"", id:"tv-" + v[0], cls:"blk", attrs:"", full:"", inner:v[2] }))
      .concat(x.bump ? blocks(S.sec("رحلة الموسم", "مركز كل فريق جولة بجولة", S.bump(x.bump))).secs : []);
    const champ5 = (() => { const rs = champRows(c.id); if (!rs.length) return null; const nm = {}; rs.forEach(r => { nm[r.key] = r.fid && S_TEAMS[r.fid] ? (S_TEAMS[r.fid].name_ar || r.name) : r.name; });
      const l = C365[c.id] && LG365.has(+C365[c.id].id) ? C365[c.id].id : null;
      return { rows:rs.map(r => [r.t, r.key, nm[r.key]]), name:k => nm[k] || "", link:k => k[0] === "f" ? `/t/${k.slice(1)}/` : k[0] === "s" ? `/db/team/?id=${k.slice(1)}` : "#", l365:l, src:C365[c.id] ? "من 365Scores." : "من ويكي داتا وويكيبيديا." }; })();
    const simT = x.sim && x.sim.teams && Object.keys(x.sim.teams).length ? x.sim : null;
    const predAll = (predLead ? blocks(predLead).secs : []).concat(predSecs);
    const rcur = (() => { if (!fx || !fx.matches || !fx.matches.length) return null; const rr = R.rounds(fx); return fx.next_round && rr.by[fx.next_round] ? fx.next_round : (rr.order.find(k => rr.by[k].some(m => m.status !== "finished")) || rr.order[rr.order.length - 1]); })();
    const ldList = l => (l || []).map((r, i) => Object.assign({ rank:i + 1 }, r));
    const v5 = P5.comp(c, { st, fx, stats, sim:simT, champs:champ5, x:{
      crumbs:`<a href="/competitions/">البطولات</a>${c.country ? "، " + (R.COUNTRIES.some(cc => cc[0] === c.country.iso2) ? `<a href="/country/${c.country.iso2.toLowerCase()}/">${esc(c.country.name_ar)}</a>` : esc(c.country.name_ar)) : ""}`,
      note:c.dormant ? '<p class="note mt">البطولة متوقفة أو خلصت هالموسم. هذي آخر نتايجها.</p>' : "",
      table:tSecs.length ? shelf(tSecs, { title:"بعد في الترتيب" }) : "",
      fx:rcur != null && /^\d+$/.test(String(rcur)) ? U.grp("", U.row({ href:`/c/${c.key}/r/${rcur}/`, icon:"calendar", c:"#FF3B30", t:`صفحة الجولة ${esc(rcur)}`, sub:"النتايج وقصة الجولة وتشكيلتها", attrs:' id="rdlink"' }), { cls:"mt2" }) : "",
      leadSegs:[ratedL.length >= 3 && ["rated", "الأعلى تقييم", U.leaders(ldList(ratedL.slice().sort((a, b) => b.value - a.value)), 10) + `<p class="gf">متوسط تقييم FotMob للاعبين اللي لعبوا <span class="num">${pMin}</span> دقيقة أو أكثر.</p>`],
        keepL.length >= 2 && ["keepers", "الحراس", U.leaders(ldList(keepL), 10) + `<p class="gf">الرقم = مباريات بشباك نظيفة، للحراس اللي لعبوا <span class="num">${pMin}</span> دقيقة أو أكثر.</p>`]].filter(Boolean),
      num:(scoreP ? U.grp("", U.row({ href:`/c/${c.key}/scorers/`, icon:"ball", c:"#34C759", t:"كل الهدافين وصناع الأهداف" }), { cls:"mt2" }) : "") + shelf(numSecs, { title:"كل الأرقام", feat:6 }) + (naNote ? naNote.replace('class="na"', 'class="gf na"') : ""),
      pred:shelf(predAll, { title:simT ? "بعد في التوقعات" : "التوقعات" }),
      hist:shelf(histSecs.filter(sc => !(champ5 && sc.title === "الأبطال عبر التاريخ")), { title:"بعد في التاريخ" }),
      after:nextR.length ? `<script type="application/json" id="rpreds">${JSON.stringify(nextR).replace(/</g, "\\u003c")}</script>` : "",
      share:P5.shareSheet({ html:toolRows(tools) + `<button type="button" class="row" id="secpick"><span class="rt">صورة لأي قسم</span>${U.chev}</button>`, after:'<div id="embout" class="card mt lc" hidden></div><div id="secpicks" class="card mt" hidden></div>' }) } });
    v5.data = { id:c.id, comp:c.id };
    const names = {}; if (stats && stats.lists) Object.values(stats.lists).forEach(l => (l || []).forEach(r => { if (r.player && nameOf(r.player.id)) names[r.player.id] = nameOf(r.player.id); }));
    OGJ.push({ key:"c-" + c.id, home:c.name_ar, sub:"الترتيب والمباريات والتوقعات", hc:["#123A31", "#1B6F5A"] });
    write(`c/${c.key}/index.html`, page({ v5, og:"c-" + c.id, path:`/c/${c.key}/`, page:"comp", attrs:` data-comp="${c.id}"`, nav:"comps", names, title:has.table ? `ترتيب ${c.name_ar} ${c.season || ""} والهدافين ومواعيد المباريات | تيفو` : `${/^مباريات /.test(c.name_ar) ? "" : "مباريات "}${c.name_ar} ${c.season || ""} ونتائجها والهدافين | تيفو`, desc:`ترتيب ${c.name_ar} ومواعيد المباريات بتوقيت بلدك والنتايج المباشرة، وتوقعات آخر الموسم، والهدافين وبطاقات اللاعبين والأرقام.`, ld:bcLd([["البطولات", "/competitions/"], [c.name_ar, `/c/${c.key}/`]]) }));
    urls.push(`/c/${c.key}/`);
    if (scoreP){ write(`c/${c.key}/scorers/index.html`, page({ path:`/c/${c.key}/scorers/`, page:"ref", nav:String(c.id), title:`هداف ${c.name_ar} ${c.season || ""}: ترتيب الهدافين وصناع الأهداف | تيفو`, desc:`ترتيب هدافي ${c.name_ar} ${c.season || ""} وصناع الأهداف، يتحدّث بعد كل مباراة.`,
      ld:bcLd([[c.name_ar, `/c/${c.key}/`], ["الهدافين", `/c/${c.key}/scorers/`]]),
      body:`<p class="crumbs"><a href="/c/${c.key}/">${esc(c.name_ar)}</a></p><h1>هدافين ${esc(c.name_ar)}</h1><p class="season">الموسم <span class="num">${esc(c.season || "")}</span></p>` + S.sec("الهدافين", "", R.leaders(stats, "goals", 50)) + ((stats.lists.assists || []).length ? S.sec("صناع الأهداف", "", R.leaders(stats, "assists", 30)) : "") }));
      urls.push(`/c/${c.key}/scorers/`); }
    if (powK){ const pw = AIPW[powK]; write(`c/${c.key}/power/index.html`, page({ path:`/c/${c.key}/power/`, page:"ref", nav:String(c.id), title:`ترتيب القوة في ${c.name_ar} هالأسبوع | تيفو`, desc:`ترتيب أندية ${c.name_ar} حسب تصنيف تيفو هالأسبوع، مع سطر عن كل نادي من أرقامه.`,
      body:`<p class="crumbs"><a href="/c/${c.key}/">${esc(c.name_ar)}</a></p><h1>ترتيب القوة</h1><p class="season">${(w => { const m = /^(\d{4})-W?(\d{1,2})$/.exec(String(w || "")); if (!m) return w ? "الأسبوع " + esc(w) : ""; const j4 = new Date(Date.UTC(+m[1], 0, 4)), mon = new Date(j4.getTime() - ((j4.getUTCDay() + 6) % 7) * 864e5 + (+m[2] - 1) * 7 * 864e5), sun = new Date(mon.getTime() + 6 * 864e5); return `أسبوع <span class="num">${mon.getUTCDate()}</span> ${MON_AR[mon.getUTCMonth()]} – <span class="num">${sun.getUTCDate()}</span> ${MON_AR[sun.getUTCMonth()]}`; })(pw.week)}</p>`   /* QA 86: a date range, not «2026-39» */ + S.aiPower(pw) })); urls.push(`/c/${c.key}/power/`); }
    if (x.cards){
      write(`c/${c.key}/compare/index.html`, page({ noindex:true, names:Object.fromEntries(Object.keys(x.cards.players || {}).filter(pid => nameOf(pid)).map(pid => [pid, nameOf(pid)])), path:`/c/${c.key}/compare/`, page:"compare", attrs:` data-comp="${c.id}"`, nav:String(c.id), title:`قارن بين لاعبين أو فريقين في ${c.name_ar} | تيفو`, desc:`قارن أي لاعبين في ${c.name_ar} على رادار واحد وأرقامهم في كل 90 دقيقة، أو قارن بين فريقين.`,
        body:`<p class="crumbs"><a href="/c/${c.key}/">${esc(c.name_ar)}</a></p><h1>قارن</h1>` + tabsHtml("k", [["players", "لاعبين"], ["clubs", "فريقين"]]) + pane("k", "players", `<div class="cmpsel"><select id="pa" aria-label="اللاعب الأول"></select><select id="pb" aria-label="اللاعب الثاني"></select></div><div id="pout"><p class="empty skel">نحمّل الأرقام…</p></div>`, true) + pane("k", "clubs", `<div class="cmpsel"><select id="ta" aria-label="الفريق الأول"></select><select id="tb" aria-label="الفريق الثاني"></select></div><div id="tout"></div>`) }));
    }
  }
  R.DUPCTX = "";   // 503: back to no context
  // derby / head-to-head pages (38)
  const DZ = {}; ((DERBIES && DERBIES.derbies) || []).forEach(d => { DZ[String(d.h2h || "").replace(/^h2h\/|\.json$/g, "")] = d.name_ar; });
  for (const [k, h] of Object.entries(H2H)){
    const [a, b] = k.split("-"), na = (teamsJson.teams[a] || {}).name_ar || a, nb = (teamsJson.teams[b] || {}).name_ar || b;
    write(`h2h/${k}/index.html`, page({ art:[colors[a] || ["#5C6660"], colors[b] || ["#3D4A44"]], path:`/h2h/${k}/`, page:"h2h", title:`تاريخ مواجهات ${na} و${nb}: كل النتائج | تيفو`, desc:`سجل مواجهات ${na} و${nb}: كم فاز كل فريق وكم تعادلوا، وكل النتايج.`, body:`<p class="crumbs">${DZ[k] ? '<a href="/derbies/">الديربيات العربية</a>' : '<a href="/c/uae-pro-league/#hist">تاريخ الدوري</a>'}</p><h1>${DZ[k] ? esc(DZ[k]) : esc(na) + " و" + esc(nb)}</h1>` + S.h2hPage(h, (() => { const now = Date.now(), ids = [+a, +b]; let nx = null; for (const m of matchSum.values()) if (m.status === "scheduled" && m.home && m.away && ids.includes(m.home.id) && ids.includes(m.away.id) && Date.parse(m.kickoff_utc) > now && (!nx || m.kickoff_utc < nx.kickoff_utc)) nx = m; return nx; })()) }));
    urls.push(`/h2h/${k}/`);
  }

  // ---- 4. home: one «اليوم» page (src/v5/pages.js P.home) — the day strip, «الكل · مباشر · العرب», the featured match («فريقك» when
  // the visitor's team plays), our competitions, then every other match in the world (v1/all, loaded by the browser), and «من تيفو».
  // /today/, /tomorrow/ and /all/ are the same page with that day (or the world list) open, each with its own title for search.
  const w538 = compX[538] && compX[538].watch, fx538 = compData.find(d => d.c.id === 538);
  const ED = []; if (arabRatings && arabRatings.teams && arabRatings.teams.length) ED.push(S.sec("أقوى الأندية العربية", '<a href="/arabs/">عالم العرب</a>', arabRankHtml(arabRatings, arabRatings.teams.slice(0, 20).map(t => t.team))));
  if (w538 && fx538) ED.push(S.sec("أحلى مباريات الجولة الياية في دوري أدنوك", "", S.watch(w538, fx538.fx)));
  const ARABCOMP = {}; compData.forEach(({ c }) => { const iso = R.compCountry(c); if (ARABC.has(iso) || [329, 10242, 11156, 10474].includes(c.id)) ARABCOMP[c.id] = 1; });
  // «الكرة الحين» (owner bold idea 3): land dots and a point per competition and national team for the home page's globe
  // (lib/globe.cjs, src/globe.js); never fatal: without it the home page simply has no globe
  let GLOBE_URL = "";
  try { const GL = await require("./lib/globe.cjs")({ fs, path, CACHE, get, teams:(teamsJson && teamsJson.teams) || {} });
    if (GL){ const j = JSON.stringify({ d:GL.d, lg:GL.lg, nt:GL.nt, intl:GL.intl, ours:GL.ours }), v = hash(j); fs.writeFileSync(path.join(OUT, `assets/globe.${v}.json`), j); GLOBE_URL = `/assets/globe.${v}.json`; console.log("globe: " + JSON.stringify(GL.stats)); } }
  catch (e){ console.error("globe: " + e.message); }
  const homeV5 = (ymd, ms, o) => { o = o || {}; const arab = {}; (ms || []).forEach(m => [m.home.id, m.away.id].forEach(id => { if (ARABT[id]) arab[id] = 1; }));
    const v = P5.home({ matches:ms || [], ymd, arab, arabComp:ARABCOMP, h1:o.h1, h1x:o.h1x, world:o.world, fromTifo:o.fromTifo || "" });
    v.data = { day:ymd.replace(/-/g, ""), today, world:o.world ? 1 : 0, arab:Object.keys(ARABT).map(Number), arabComp:Object.keys(ARABCOMP).map(Number), sig:U.sig(ms || []), ...(GLOBE_URL ? { globe:GLOBE_URL } : {}) }; return v; };   // sig: the browser keeps this list when its data is the same
  const writeHome = () => {
    const edHtml = ED.join(""), bdays = (edHtml.match(/<div id="bdays"[^>]*><\/div>/) || [""])[0];
    const ed = blocks(edHtml).secs.filter(sc => sc.title);
    const edLinks = [["/week/", "مباريات الأسبوع", "أهم مباريات الأيام السبعة الياية", "star", "#FF9500"], ["/legends/", "الأساطير", "مسيرة وأرقام أبرز لاعبين في تاريخ الكورة الإماراتية", "crown", "#FFCC00"], ["/memorable/", "مباريات ما تنتسى", "المباريات اللي صنعت تاريخ الكورة الإماراتية", "star", "#FF3B30"], ["/cast/", "تيفو كاست", "الجولة بصوت إماراتي، كل أسبوع", "mic", "#AF52DE"], ["/laws/", "قانون الكورة", "ليش ألغى الحكم الهدف؟ بالإماراتي", "whistle", "#1C7C54"], ["/tv/", "شاشة المجلس", "كل المباريات على تلفزيون المجلس", "tv", "#0A84FF"], ["/studio/", "ستوديو التيفو", "صمّم لافتة فريقك للمدرج", "brush", "#FF2D55"]];
    const fromTifo = (ed.length ? shelf(ed, { title:"من تيفو" }) : "") + (bdays ? `<section class="grp" id="bdaysg" hidden><div class="gh"><h2>اليوم في التقويم</h2></div><div class="card lc">${bdays}</div></section>` : "") +
      U.grp(ed.length ? "" : "من تيفو", U.rows(edLinks.map(l => ({ href:l[0], icon:l[3], c:l[4], t:l[1], sub:l[2] }))), { cls:"mt2" });
    write("index.html", page({ v5:homeV5(today, day.matches, { fromTifo, h1x:"نتائج مباريات اليوم مباشر" }), path:"/", page:"home", nav:"home", title:"تيفو — نتايج مباريات اليوم مباشر لكل العرب", desc:"نتايج المباريات مباشر بتوقيت بلدك: دوري أدنوك، والمنتخب، وكأس الخليج، وأبطال آسيا، والدوريات الكبيرة. الأحداث والتشكيلات والترتيب والتوقعات أول بأول." }));
  };
  // ---- 5. teams
  const tlist = [...teamIds], teamPages = new Set(), playerPages = new Set();
  const full = new Set((index.focus_teams || []).concat(Object.values(NAT).map(Number)));   /* QA 11/12: every Arab national team has a team file (squad + all fixtures, friendlies too) */ compData.filter(d => d.c.scope === "uae").forEach(d => (d.st && d.st.groups || []).forEach(g => g.rows.forEach(r => full.add(r.team.id))));
  const teams = await pool(tlist, 8, id => full.has(id) ? get(`team/${id}.json`) : null);
  const teamById = new Map(); tlist.forEach((id, i) => { if (teams[i]) teamById.set(id, teams[i]); });
  { const dayT = [...new Set((day.matches || []).flatMap(m => [m.home.id, m.away.id]))].filter(id => !teamById.has(id)); const tj = await pool(dayT, 6, id => get(`team/${id}.json`, 1)); dayT.forEach((id, i) => { if (tj[i]) teamById.set(id, tj[i]); }); }   // today's squads: Arabic names for live subs and scorers
  const rhist = await pool(tlist, 8, id => full.has(id) && id !== 5789 ? get(`ratings/team/${id}.json`, 1) : null);
  const st538 = compData.find(d => d.c.id === 538), x538 = compX[538] || {};
  // 238, 327, 244: per-club files for the clubs in the analytics leagues
  const AN = new Set(); compData.forEach(({ x }) => { if (x["first-goal"] && x["first-goal"].teams) Object.keys(x["first-goal"].teams).forEach(k => AN.add(+k)); });
  const tfiles = await pool(tlist, 8, async id => AN.has(id) ? { rec:await get(`team/${id}/records.json`, 1), hist:await get(`team/${id}/history.json`, 1), cu:await get(`callups/${id}.json`, 1) } : {});
  const TWINS = await get("arabs/twins.json"), months = [today.slice(0, 7), new Date(Date.parse(today.slice(0, 7) + "-01") - 864e5).toISOString().slice(0, 7)];
  const tmonth = await pool(tlist, 8, async id => AN.has(id) ? Promise.all(months.map(m => get(`team/${id}/month/${m}.json`, 2))) : []);
  const xOf = (k, id) => { for (const { c, x } of compData) if (c.kind === "league" && x[k] && x[k].teams && x[k].teams[id]) return x[k]; return null; };
  let tcount = 0;
  // W4.5: share cards for every Arab national team and every club in an Arab league (og.py skips unchanged cards)
  const NATSET = new Set(Object.values(NAT).map(Number)), OG_ARAB = new Set(NATSET); S.NATU = Object.fromEntries(Object.entries(NAT).map(([iso, tid]) => [iso, `/t/${tid}/`])); { const AR = new Set((R.COUNTRIES || []).map(c => c[0])); compData.forEach(({ c, st }) => { if (c.kind !== "league" || !c.country || !AR.has(c.country.iso2) || !st || !st.groups) return; st.groups.forEach(g => (g.rows || []).forEach(r => { if (r.team) OG_ARAB.add(r.team.id); })); }); }
  const byTeam = new Map(); for (const m of matchSum.values()) for (const side of [m.home, m.away]) if (side && side.id){ if (!byTeam.has(side.id)) byTeam.set(side.id, { side, ms:[] }); byTeam.get(side.id).ms.push(m); }
  tlist.forEach((id, i) => {
    R.DUPCTX = (((teamsJson.teams[id] || {}).country) || {}).name_ar || "";   // 503: a club's own page drops its country's tag
    let t = teams[i]; if (t && t.fixtures) t.fixtures = t.fixtures.map(unstale);
    if (!t){ const b = byTeam.get(id); if (!b) return; t = { id, name:b.side.name, name_ar:b.side.name_ar, fixtures:b.ms, squad:[], partial:true }; }
    if (/^(winner|loser)\b/i.test(t.name || "") || /^[1-4][A-Z]{1,4}(\/[1-4]?[A-Z]{1,4})?$/.test(t.name || "")) return;   // bracket placeholders («Winner SF 2», «3CDE») get no page
    tcount++; teamPages.add(+t.id);
    { const cm = {}; (t.squad || []).forEach(g => (g.players || []).forEach(p => { const n = p && p.club_id && (teamsJson.teams[p.club_id] || {}).name_ar; if (n) cm[p.club_id] = n; })); R.setClubNames(Object.assign({}, cm, TAR)); }   /* QA 46: squad clubs in Arabic */
    // QA 11: national teams play friendlies we don't track as a competition; national.json's next match and last result join the fixtures
    if (NATSET.has(+t.id)){ const nj = ((NATJ && NATJ.teams) || []).find(x => +x.team === +t.id); if (nj){ const have = new Set((t.fixtures || []).map(m => m.id));
      [nj.next_match, nj.last_result].forEach(m => { if (m && m.id && !have.has(m.id) && m.home && m.away){ const mm = matchSum.get(m.id) || m; t.fixtures = (t.fixtures || []).concat([Object.assign({ status:m.score ? "finished" : "scheduled", kickoff_uae:m.kickoff_uae || (m.kickoff_utc ? new Date(Date.parse(m.kickoff_utc) + 4 * 36e5).toISOString().slice(0, 19) + "+04:00" : null) }, mm)]); have.add(m.id); } }); } }
    const f = R.teamFixtures(t);
    { const slim = m => m && { id:m.id, comp:m.comp, kickoff_utc:m.kickoff_utc, kickoff_uae:m.kickoff_uae, status:m.status, minute:m.minute, score:m.score, home:m.home, away:m.away, time_tbd:m.time_tbd, why:AIWHY[m.id] && (AIWHY[m.id].lines || []).length ? 1 : undefined };   // favourites card (179)
      const tf = path.join(OUT, "tn", t.id + ".json"); fs.mkdirSync(path.dirname(tf), { recursive:true }); const rk = (() => { for (const d of compData){ const g = d.st && !d.st.composite && d.st.groups && d.st.groups[0]; const r = g && g.rows.find(r => r.team.id === t.id); if (r && R.compCountry(d.c) && d.c.kind === "league") return { comp:d.c.id, comp_ar:d.c.name_ar, rank:r.rank, pts:r.pts }; } return null; })();
      fs.writeFileSync(tf, JSON.stringify({ id:t.id, name:t.name, name_ar:t.name_ar, next:slim(f.next[0]), last:slim(f.past[0]), recent:f.past.slice(0, 5).map(slim), table:rk })); }
    const cAr = coachAr(t.coach), vAr = t.venue && VENUE_AR.get(t.venue.name);
    const sub = [t.coach ? `المدرب ${cAr ? esc(cAr) : `<span class="lat">${esc(t.coach.name)}</span>`}` : "", t.venue && t.venue.name ? `الملعب ${vAr ? esc(vAr) : `<span class="lat">${esc(t.venue.name)}</span>`}` : ""].filter(Boolean).join("<br>");
    // the club in numbers (91, 36, 96, 135, 137, 141)
    let nums = "";
    if (rhist[i]) nums += S.sec("تصنيف تيفو عبر السنين", "", S.ratingChart(rhist[i], id));
    const row = st538 && st538.st && st538.st.groups[0].rows.find(r => r.team.id === id);
    if (row && row.last_season_same_round){ const l = row.last_season_same_round; nums += S.sec("هالموسم ضد الموسم الماضي", `بعد ${row.played} جولات`, `<div class="pstats"><div><b>${row.pts}</b><span>نقاطه الحين</span></div><div><b>${l.pts}</b><span>نفس الوقت الموسم الماضي</span></div><div><b><bdi dir="ltr">${row.pts - l.pts > 0 ? "+" : ""}${row.pts - l.pts}</bdi></b><span>الفرق</span></div><div><b>${row.gf} - ${row.ga}</b><span>أهدافه الحين</span></div><div><b>${l.gf} - ${l.ga}</b><span>الموسم الماضي</span></div></div>`); }
    if (x538.pressure && x538.pressure.teams && x538.pressure.teams[id]){ const pr = { teams:{} }; pr.teams[id] = x538.pressure.teams[id]; nums += S.sec("الضغط على المدرب", "", S.pressure(pr)); }
    const tc = x538.cards ? S.cards(x538.cards, 11, c => c.team === id) : ""; if (tc) nums += S.sec("بطاقات تيفو للاعبين", "", tc);
    if (x538.clutch && x538.clutch.players){ const cl = S.clutch({ players:x538.clutch.players.filter(p => p.team === id) }); if (cl) nums += S.sec("منو الحاسم في الفريق؟", "", cl); }
    const chh = S.clubHistory(CLUBS[id]); if (chh) nums = S.sec("خزانة البطولات والتاريخ", "", chh) + nums;
    const acc = S.accounts(ACC[id]); if (acc) nums = S.sec(NATSET.has(id) ? "الحسابات الرسمية" : "حسابات النادي الرسمية", "", acc) + nums;
    const ln = S.loans(t); if (ln) nums += S.sec("لاعبينه المعارين", "", ln);
    { const tf = tfiles[i] || {}, rc = S.teamRecords(tf.rec), hm = S.heatmap(tf.hist), cu = S.callups(tf.cu), xi = S.xiTeam(xOf("xi", id), id);
      const tw = TWINS && TWINS.clubs && S.twins(TWINS.clubs[id]); if (tw) nums += S.sec("توأم فريقك", "أقرب الأندية في أسلوب اللعب", tw);
      const ml = (tmonth[i] || []).filter(mo => mo && mo.results && mo.results.length); if (ml.length) nums = S.sec("تقرير الشهر", "", '<p class="tools">' + ml.map(mo => `<a class="btn" href="/t/${id}/month/${mo.month}/">${["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"][+mo.month.slice(5) - 1]}</a>`).join("") + "</p>") + nums;
      { const trc = trClub(id); if (trc) nums += S.sec("أغلى الصفقات في تاريخه", "", trc); }
      if (rc) nums += S.sec("سجل النادي", "من 2010", rc); if (hm) nums += S.sec("كل نتايجه موسم بموسم", "", hm); if (xi) nums += S.sec("التشكيلة المعتادة", "هالموسم", xi); if (cu) nums += S.sec("لاعبينه في المنتخبات", "", cu); }
    const tv2 = S.travel(t, t.fixtures); if (tv2) nums += S.sec("سافر مع فريقك", "مباريات آسيا برا الدولة", tv2);
    const co = S.coachesTeam(x538.coaches, id); if (co) nums += S.sec("مدربين النادي عبر التاريخ", "في الدوري", co);
    if (x538.fortress && x538.fortress.stadiums){ const fs2 = x538.fortress.stadiums.filter(s => s.team === id); if (fs2.length) nums += S.sec("حصن الملعب", "", S.fortress({ since:x538.fortress.since, stadiums:fs2 })); }
    // national team (144, 145, 59, 39)
    if (id === 5789){
      const x329 = compX[329] || {};
      if (x329.scenarios) { const sc = S.scenarios(x329.scenarios, 5789); if (sc) nums += S.sec("سيناريوهات كأس الخليج", "", sc); }
      if (x329["tournament-sim"] && simOk(329, x329["tournament-sim"])) nums += S.sec("فرص الإمارات في كأس الخليج", "", S.tsim(x329["tournament-sim"]));
      const x290 = compX[290] || {}; if (x290["tournament-sim"] && simOk(290, x290["tournament-sim"])) nums += S.sec("فرص الإمارات في كأس آسيا", "", S.tsim(x290["tournament-sim"]));
      if (fifa) nums += S.sec("تصنيف فيفا", "من 1992", S.fifa(fifa));
      if (natRatings && natRatings.uae) nums += S.sec("تصنيف تيفو للمنتخبات", "", `<p>الإمارات في المركز <b class="num">${natRatings.uae_world_rank}</b> عالمياً بتصنيف تيفو (<span class="num">${Math.round(natRatings.uae)}</span> نقطة).</p>`);
      if (abroad) { const ab = S.abroad(abroad); if (ab) nums += S.sec("الإماراتيين المحترفين برا", "", ab); }
      const nc = S.natClubs(t); if (nc) nums += S.sec("لاعبي المنتخب في أنديتهم", "", nc);
    }
    const wkd = APPROVED.digest ? S.aiDigest(AIDG[id]) : "";
    // v5 team page (src/v5/pages.js P.team): the header (crest, name, league · place, coach, form; تابع · نبّهني · شارك), the next match
    // card, then المباريات · الترتيب · اللاعبين · الأخبار · التاريخ. The club's numbers (the v3 «بالأرقام» tab) are rows in التاريخ that
    // open their sheets, with the history mounts app.js fills (club history, UEFA ranking, xG seasons, FotMob's club, Elo)
    SEQ = 0;
    const numSecs = nums ? blocks(nums).secs : [];
    const isNat = NATSET.has(id);
    const lrow = (() => { for (const d of compData){ const g = d.st && !d.st.composite && d.st.groups && d.st.groups[0]; const r = g && g.rows.find(r => r.team.id === t.id); if (r && d.c.kind === "league") return { c:d.c, r, st:d.st }; } return null; })();
    const club = club5(id), cmap = (() => { const cm = {}; (t.squad || []).forEach(g => (g.players || []).forEach(p => { const n = p && p.club_id && (teamsJson.teams[p.club_id] || {}).name_ar; if (n) cm[p.club_id] = n; })); return cm; })();
    if (isNat) Object.assign(U.cfg.tn, cmap);   // a national team's squad names its players' clubs in Arabic
    const squad5 = (t.squad || []).length ? U.grp("", U.row({ btn:1, icon:"shirt", c:"#AF52DE", t:"سوّ تشكيلتك على الملعب", sub:"اختار الخطة واللاعبين وشاركها", attrs:' id="xibtn"' }), { cls:"xih" }) + `<div id="squad"${Object.keys(cmap).length ? ` data-clubs='${esc(JSON.stringify(cmap))}'` : ""}>${U.squad(t)}</div>`
      : `<div id="squad" class="lc">${NATSET.has(id) ? "<!--NATSQ-->" : ""}<p class="empty">ما عندنا قائمة اللاعبين.</p></div>`;
    const mounts = (FMT[id] ? `<div class="fmteam" data-team="${t.id}"></div>` : "") + (UEFAIDX.has(id) ? `<div class="cuefa" data-club="${t.id}"></div>` : "") + (XGIDX.has(id) ? `<div class="cxg" data-club="${t.id}"></div>` : "") + (HIDX[id] ? `<div class="chist" data-club="${t.id}"><section class="blk"><h2>كل نتايجه من أول مباراة</h2><p>تاريخه من <span class="num">${esc(HIDX[id].since)}</span>: <span class="num">${HIDX[id].p}</span> مباراة. نحمّل التفاصيل…</p></section></div>` : "") + (isNat ? `<div class="elo" data-team="${t.id}"></div><!--NATHIST-->` : "");
    const hist5 = (club.extra ? U.grp("", club.extra, { raw:1 }) : "") + (mounts ? `<div class="lc mounts">${mounts}</div>` : "") + shelf(numSecs.concat(wkd ? [{ title:"ملخص أسبوعك", sub:"", id:"week", cls:"blk", attrs:"", full:`<section class="blk" id="week"><h2>ملخص أسبوعك</h2>${wkd}</section>`, inner:wkd }] : []), { title:isNat ? "المنتخب بالأرقام" : "النادي بالأرقام" });
    const months = (tmonth[i] || []).filter(mo => mo && mo.results && mo.results.length).map(mo => [mo.month, MON_AR[+mo.month.slice(5) - 1] + " " + mo.month.slice(0, 4)]);
    const tools = `${f.next.length ? '<button type="button" id="wpbtn">خلفية للجوال بمبارياته</button>' : ""}<a href="/t/${t.id}/poster/">بوستر الموسم للطباعة</a>`;
    const v5 = P5.team(t, { row:lrow, st:lrow && lrow.st, trophies:club.tro.length ? club.tro : null, trophiesSrc:club.src, card:club.card.length ? club.card : null, wiki:WC[id] ? wiki5(WC[id]) : "",
      x:{ months, squad:squad5, hist:hist5, notify:NFM.sheet({ id:t.id, name:t.name_ar || t.name }), fxExtra:BIGS.has(+t.id) ? U.grp("", U.rows([{ href:`/t/${t.id}/today/`, icon:"calendar", c:"#34C759", t:"مباراته اليوم", sub:"الموعد والقناة الناقلة والمعلق" }]), { cls:"mt2" }) : "", share:P5.shareSheet({ html:toolRows(tools) + `<button type="button" class="row" id="secpick"><span class="rt">صورة لأي قسم</span>${U.chev}</button>`, after:'<div id="secpicks" class="card mt" hidden></div>' }) } });
    v5.data = { id:t.id, nat:isNat ? 1 : 0 };
    const names = {}; ((t.squad) || []).forEach(g => (g.players || []).forEach(p => { if (p && p.id && nameOf(p.id)) names[p.id] = nameOf(p.id); }));
    const pp = {}; ((t.squad) || []).forEach(g => (g.players || []).forEach(p => { if (p && p.id && allPlayers[p.id]) pp[p.id] = 1; }));
    const tog = full.has(id) || OG_ARAB.has(id); if (tog) OGJ.push({ key:"t-" + id, home:t.name_ar || t.name, home_id:id, hc:colors[id], sub:"المباريات والنتايج واللاعبين" });
    const thinT = !(t.squad || []).length && !(f.next.length || f.past.length);
    const html = page({ v5, noindex:thinT, og:tog ? "t-" + id : null, path:`/t/${t.id}/`, page:"team", names, pp, attrs:` data-id="${t.id}" data-name="${esc(t.name_ar || t.name)}"`, nav:isNat ? "nat" : "", title:`${t.name_ar || t.name}: مواعيد المباريات القادمة والنتائج واللاعبين | تيفو`, ld:bcLd([lrow && [lrow.c.name_ar, `/c/${lrow.c.key}/`], [t.name_ar || t.name, `/t/${t.id}/`]]), desc:`مواعيد مباريات ${t.name_ar || t.name} بتوقيت بلدك، ونتايجه، وقائمة اللاعبين، وأرقامه، واشتراك تقويم يتحدّث بروحه.` });
    write(`t/${t.id}/index.html`, html); if (!thinT) urls.push(`/t/${t.id}/`);
    if ((t.fixtures || []).length) write(`t/${t.id}/poster/index.html`, page({ path:`/t/${t.id}/poster/`, page:"poster", title:`جدول مباريات ${t.name_ar || t.name} للطباعة | تيفو`, desc:`جدول مباريات ${t.name_ar || t.name} للموسم كامل بتوقيت بلدك، جاهز للطباعة.`, body:S.poster(t) }));
    (tmonth[i] || []).forEach(mo => { if (!mo || !mo.results || !mo.results.length) return; const [yy, mm] = mo.month.split("-").map(Number), mname = ["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"][mm - 1] + " " + yy;
      write(`t/${t.id}/month/${mo.month}/index.html`, page({ path:`/t/${t.id}/month/${mo.month}/`, page:"poster", title:`${t.name_ar || t.name} في ${mname}: تقرير الشهر | تيفو`, desc:`نتايج ${t.name_ar || t.name} في ${mname}، وأحسن اللاعبين، والترتيب في بداية الشهر ونهايته.`, body:`<p class="crumbs"><a href="/t/${t.id}/">${R.tname(t)}</a></p><h1>${R.tname(t)} في ${mname}</h1>` + S.monthReport(mo) + '<p class="tools noprint"><button type="button" class="btn" onclick="print()">اطبعه</button></p>' }));
      urls.push(`/t/${t.id}/month/${mo.month}/`); });
    if (t.id === 5789) stub("/uae/", "/t/5789/", "منتخب الإمارات");   // W4.3: one page per national team; /uae/ was a third self-canonical copy
  });
  R.DUPCTX = "";   // 503: back to no context

  // ---- 6. players (135, 120, 137, 149): every player the league files name
  for (const [k, b] of Object.entries(FMP)) if (!allPlayers[k] && b && b.name && b.team && S_TEAMS[b.team]) allPlayers[k] = { name:b.name, team:b.team, fm:1 };
  const pids = Object.keys(allPlayers);
  const uaeP = new Set(Object.keys((compX[538] && compX[538].players && compX[538].players.players) || {}));   // the pipeline writes player/{id}.json for the UAE league
  const pjs = await pool(pids, 8, id => uaeP.has(id) ? get(`player/${id}.json`, 1) : null);
  const topP = new Set(); compData.forEach(({ stats }) => ["goals", "assists"].forEach(k => ((stats && stats.lists && stats.lists[k]) || []).slice(0, 30).forEach(r => r.player && topP.add(String(r.player.id)))));
  const pcar = await pool(pids, 8, id => topP.has(id) ? get(`player/${id}/career.json`, 1) : null);
  let pcount = 0;
  pids.forEach((id, i) => {
    R.DUPCTX = (((teamsJson.teams[(allPlayers[id] || {}).team] || {}).country) || {}).name_ar || "";   // 503
    const ap = allPlayers[id] || {}, sv = k => ap.stats && ap.stats[k] ? ap.stats[k].value : null;
    const p = pjs[i] || { name:ap.name, team:ap.team, comp:ap.comp, minutes:ap.minutes, goals:sv("goals"), assists:sv("goal_assist"), rating:sv("rating") }; if (!p || !p.name) return; pcount++;
    const tm = p.team || allPlayers[id].team, cx = compX[p.comp || 538] || x538, card = cx.cards && cx.cards.players && cx.cards.players[id];
    const cl = cx.clutch && cx.clutch.players && cx.clutch.players.find(c => String(c.id) === id);
    const tt = { id:tm, name_ar:(S && teamsJson && teamsJson.teams[tm] && teamsJson.teams[tm].name_ar) || "" };
    // W2.7: one 4-across row; a missing count is 0 (from the league's players.json when the player file has none), never «—»
    const z = (a, b2) => a != null ? a : b2 != null ? b2 : 0;
    const st = `<div class="pstats four"><div><b>${z(p.goals, sv("goals"))}</b><span>أهداف</span></div><div><b>${z(p.assists, sv("goal_assist"))}</b><span>صناعة</span></div><div><b>${z(p.minutes, ap.minutes)}</b><span>دقيقة</span></div><div><b>${p.rating != null ? Number(p.rating).toFixed(1) : "—"}</b><span>التقييم</span></div>${cl ? `<div><b>${cl.total}</b><span>نقاط جابها</span></div>` : ""}</div>`;
    const pc = comps.find(cc => cc.id === (p.comp || ap.comp));   // 447
    // v5 player page (src/v5/pages.js P.player): the header (photo or shirt number, Arabic and Latin name, club · position · country),
    // this season's four tiles, then الملف · المسيرة · المباريات · الأخبار. The career and the match log load in the browser from the
    // player's own files (profile.json, tm.json, log.json), as they did; the old page's blocks (Tifo card, form, career in the league,
    // who plays like him, shot map) are rows in الملف that open their sheets
    const ck = (comps.find(cc => cc.id === (p.comp || 538)) || {}).key || "uae-pro-league";
    const pext = blocks([card ? S.sec("بطاقة تيفو", "", S.card(id, card)) : "", S.form(p.form) ? S.sec("فورمته", "آخر المباريات", S.form(p.form)) : "", S.career(pcar[i]) ? S.sec("مسيرته في الدوري", "", S.career(pcar[i])) : "",
      cx.similar ? (() => { const sm = S.similar(cx.similar, id); return sm ? S.sec("منو يلعب مثله؟", "", sm) : ""; })() : "", cx.shots && cx.shots.available !== false && cx.shots.players && cx.shots.players[id] ? S.sec("خريطة تسديداته", "", S.shotmap(cx.shots.players[id])) : "",
      cl ? S.sec("نقاط جابها لفريقه", "", `<p>جاب لفريقه <b class="num">${cl.total}</b> نقاط بأهدافه وصناعته هالموسم.</p>`) : ""].join("")).secs;
    const ph = PH[id], pcrumbs = `${pc ? `<a href="/c/${pc.key}/">${esc(pc.name_ar)}</a>، ` : ""}${tt.name_ar ? `<a href="/t/${tm}/">${esc(tt.name_ar)}</a>` : ""}`;
    const ptools = `${card ? `<a href="/c/${ck}/compare/?a=${id}">قارنه بلاعب ثاني</a>` : ""}${String(id) === "30981" ? '<a href="/messi/">متحف ميسي: كل أهدافه على ملعب ثلاثي الأبعاد</a>' : ""}`;
    const v5 = P5.player(id, { name:nameOf(id), latin:p.name, team:tm ? { id:tm, name_ar:tt.name_ar } : null, pos:p.position, num:p.number, cc:p.country, season:p.season,
      card:ap.fm ? null : { goals:z(p.goals, sv("goals")), assists:z(p.assists, sv("goal_assist")), minutes:z(p.minutes, ap.minutes), rating:p.rating }, prof:FMP[id] ? { bio:FMP[id] } : null, ea:EAC[id] || null,
      photo:ph ? `/v1/ph/${id}.webp` : null, credit:ph ? `الصورة: <a href="${esc(ph.page || "")}" rel="noopener">${esc(((ph.artist || "").replace(/\s+/g, " ").trim().slice(0, 40)) + (ph.license ? " · " + ph.license : ""))}</a>` : "", wiki:WP[id] ? wiki5(WP[id]) : "", transfers:(TRH.players || {})[id] || null,
      x:{ mount:true, crumbs:pcrumbs, profile:(String(id) === "30981" ? U.grp("", U.row({ href:"/messi/", icon:"target", c:"#0A84FF", t:"متحف ميسي", sub:"كل أهدافه على ملعب ثلاثي الأبعاد" }), { cls:"mt2" }) : "") + shelf(pext, { title:"بالتفصيل" }),
        share:P5.shareSheet({ html:toolRows(ptools) + `<button type="button" class="row" id="secpick"><span class="rt">صورة لأي قسم</span>${U.chev}</button>`, after:'<div id="secpicks" class="card mt" hidden></div>' }) } });
    v5.data = { id:+id, prof:FMP[id] ? 1 : 0, tm:TMI[id] ? 1 : 0 };
    const thinP = (p.minutes || 0) < 90 && !S.career(pcar[i]) && !(FMP[id] && FMP[id].n);   // owner item 11: thin pages stay reachable but out of the index
    playerPages.add(String(id)); write(`p/${id}/index.html`, page({ v5, noindex:thinP, path:`/p/${id}/`, page:"player", names:Object.assign(nameOf(id) ? { [id]:nameOf(id) } : {}), title:`${nameOf(id) || p.name}: أهدافه وأرقامه هالموسم${tt.name_ar ? " مع " + tt.name_ar : ""} | تيفو`, ld:bcLd([pc && [pc.name_ar, `/c/${pc.key}/`], tt.name_ar && [tt.name_ar, `/t/${tm}/`], [nameOf(id) || p.name, `/p/${id}/`]]), desc:`${nameOf(id) || p.name}، ${tt.name_ar}: أهدافه وصناعته وتقييمه وبطاقة تيفو، واللاعبين اللي يلعبون مثله.` }));
    if (!thinP) urls.push(`/p/${id}/`);
  });
  R.DUPCTX = "";   // 503: back to no context

  // ---- 7. matches: summary for all, full detail where stored; probabilities (92) and records at stake (94, 95)
  const mids = [...matchSum.keys()].filter(id => id != null && id !== "null");   // W1.4: a fixture without an id gets no page and no link
  const withDetail = new Set(mids.filter(id => { const m = matchSum.get(id); return m.status === "finished" || R.isLive(m) || (Date.parse(m.kickoff_utc) - Date.now() < 3 * 864e5 && Date.parse(m.kickoff_utc) > Date.now() - 864e5); }));
  const det = await pool([...withDetail], 8, id => get(`match/${id}.json`, 1));
  const D = new Map(); [...withDetail].forEach((id, i) => { if (det[i]) D.set(id, det[i]); });
  // «كشّاف تيفو» (owner bold idea 6): the young Arab players' pool and their points per match (lib/scout.cjs), for /scout/ and
  // the Cards Lambda (saas/cards src/tifo_scout.py reads scout/points.json)
  const SCOUT = require("./lib/scout.cjs"), SCD = SCOUT.build(D.values(), { natTeams:new Set(Object.values(NAT).map(Number)), nameOf });
  SCD.pool.players.forEach(p => { if (playerPages.has(String(p.id))) p.pg = 1; });
  write("scout/pool.json", JSON.stringify(SCD.pool)); write("scout/points.json", JSON.stringify(SCD.points));
  console.log(`scout: ${SCD.pool.players.length} young Arab players, ${Object.values(SCD.points.players).reduce((n, m) => n + m.length, 0)} appearances`);
  const OGM = new Set();   // matches with their own share card (og/m-<id>.png); the day pages' SportsEvent images point at them
  // item 11: the share stage (lib/share_stage.cjs): what its last good upload holds, and the goal clips of the last 48 h (news/media.py)
  const SHARE = require("./lib/share_stage.cjs"), SHPUB = SHARE.published({ CACHE, fs, path }), SHJ = [], SHG = [], STUBS = [], CLIPS = {};
  { const mr = await get("media/recent.json", 1), withG = ((mr && mr.matches) || []).filter(m => m.goals > 0).map(m => m.id), mf = await pool(withG, 6, i => get(`media/${i}.json`, 1));
    withG.forEach((i, k) => { if (mf[k] && mf[k].goals) CLIPS[i] = new Set(Object.keys(mf[k].goals)); }); }
  for (const id of mids){
    { const mc = comps.find(cc => cc.id === (matchSum.get(id) || {}).comp); R.DUPCTX = (mc && mc.country && mc.country.name_ar) || ""; }   // 503: a league match drops its own country's tag
    const md0 = D.get(id) || matchSum.get(id), uaeMatchTop = R.UAE_COMPS.indexOf(md0.comp) >= 0 || md0.home.id === 5789 || md0.away.id === 5789;
    const md = md0, sum = matchSum.get(id), ttl = `${R.tname(md.home)} ${md.score ? md.score.home + "-" + md.score.away : "ضد"} ${R.tname(md.away)}`;
    const probs = md.status === "scheduled" ? (md.probs || sum.probs) : null, facts = md.status === "scheduled" ? factsByMatch[id] : null;
    const fa = md.status === "scheduled" && md.comp === 538 && x538.fatigue ? S.fatigue(x538.fatigue, [md.home.id, md.away.id]) : "";
    // v3 match page (DESIGN-v3.md): club-colour key art hero, sticky mini-bar, 5 tabs, analysis as shelf tiles, one sheet
    if (md.venue && !md.venue.name_ar){ const va = VENUE_AR.get(md.venue.name_en || md.venue.name); if (va) md.venue.name_ar = va; }
    SEQ = 0; R.arNames(md); PALETTE = [colors[md.home.id], colors[md.away.id]].filter(Boolean); if (!PALETTE.length) PALETTE = [["#5C6660", "#F6F7F2"]];
    const cx = compX[md.comp] || {}, cdata = compData.find(d => d.c.id === md.comp) || {};
    // QA 2: an upcoming match has no detail file (so no h2h); the pair's h2h file fills «المواجهات»
    { const hk = md.home && md.away ? [md.home.id, md.away.id].sort((a, b) => a - b).join("-") : "", hf = H2H[hk]; if (hf && !(md.h2h && md.h2h.summary)){ const w = hf.wins || {};
      md.h2h = { summary:{ home_wins:w[md.home.id] || 0, draws:w.draws || 0, away_wins:w[md.away.id] || 0 }, matches:(hf.matches || []).filter(m => m.id !== md.id && m.score) }; } }
    const uaeMatch = R.UAE_COMPS.indexOf(md.comp) >= 0 || md.home.id === 5789 || md.away.id === 5789;
    const aiSum = APPROVED.summary && AIS[id] ? S.aiSummary(AIS[id]) : "", aiPre = APPROVED.preview && md.status === "scheduled" && AIP[id] ? S.sec("تحليل ما قبل المباراة", "", S.aiPreview(AIP[id])) : "";
    const press = md.status === "scheduled" && uaeMatch ? S.pressSheet(md, cdata.st, cdata.stats, factsByMatch[id], cx.fatigue, D.get(id)) : "";
    const thread = APPROVED.thread && AIS[id] ? S.aiThread(AIS[id]) : "", comm = APPROVED.commentary ? S.aiCommentary(AICM[id]) : "";
    const opp = md.status === "scheduled" ? S.oppReport(md, cx, cdata.stats) : "";
    if (md.referee && refAr(md.referee)){ md.referee.name_en = md.referee.name; md.referee.name = refAr(md.referee); }
    // QA 26: the channel box falls back to the per-country file's UAE row (the same data as the row chips), so «وين تنقل» never opens empty
    const bcAE = BC[md.comp] || (BCBY.AE && BCBY.AE[md.comp] && BCBY.AE[md.comp].b && BCBY.AE[md.comp].b.length ? { broadcasters:BCBY.AE[md.comp].b.map(x => ({ name_ar:x[0], free:!!x[1] })) } : null);
    const ww = md.status !== "finished" ? S.watchWhere(bcAE) : "", hl = md.status === "finished" ? S.highlight(HLT[md.comp], md).replace(/ \((?:[^()]|\([^()]*\))*\)(?=<\/a>)/, m => { const ch = /bein/i.test(m) ? "بي إن سبورتس" : /AFC/.test(m) ? "قناة الاتحاد الآسيوي" : /Pro League/i.test(m) ? "قناة رابطة المحترفين" : /CAF/.test(m) ? "قناة الاتحاد الأفريقي" : /UEFA|Champions/i.test(m) ? "قناة اليويفا" : ""; return ch ? " على " + ch : ""; }) : "";
    const mdy = md.venue && STAD[md.venue.id] ? S.matchDay(md, STAD[md.venue.id]) : "";
    const sgrid = probs ? S.scoreGrid(probs, md) : "";
    const L2 = md.lineups; const tac = L2 && L2.home && L2.away ? (() => { const subs = side => (md.events || []).filter(e => e.type === "sub" && e.team === side), f = side => { const sb = subs(side); return `${R.tname(md[side])}: خطة <span class="num">${esc(L2[side].formation || "—")}</span>${sb.length ? `، ${sb.length === 1 ? "تبديل واحد" : sb.length === 2 ? "تبديلين" : sb.length + " تبديلات"}، أولها الدقيقة <span class="num">${sb[0].minute}</span>` : ""}.`; }; return `<ul class="facts-l"><li>${f("home")}</li><li>${f("away")}</li></ul>`; })() : "";
    const replay = md.status === "finished" && (md.events || []).some(e => /goal|red|yellow/.test(e.type)) ? '<div class="replay"><label>اسحب لأي دقيقة: <b class="num" id="rpm">90</b></label><input type="range" id="rpr" min="0" max="' + ((md.events || []).some(e => e.minute > 90) ? 120 : 90) + '" value="' + ((md.events || []).some(e => e.minute > 90) ? 120 : 90) + '" aria-label="الدقيقة"><div class="rpsc"><span>' + R.tname(md.home) + '</span><b class="num" id="rps">' + (md.score ? md.score.home + " - " + md.score.away : "") + '</b><span>' + R.tname(md.away) + '</span></div><ul class="facts-l" id="rpe"></ul><script type="application/json" id="rpev">' + JSON.stringify((md.events || []).filter(e => /goal|red|yellow|second/.test(e.type)).map(e => [e.minute + (e.added ? e.added / 10 : 0), e.type, e.team, e.player && e.player.name, e.score ? [e.score.home, e.score.away] : null])).replace(/</g, "\\u003c") + "</script></div>" : "";
    // التحليل: win probability leads; commentary (196), AI summary/preview, opponent report, press sheet (with commentator mode), X thread … as tiles
    const tlHtml = R.timeline(md), momHtml = momentumSvg(md);
    const anaSecs = blocks([momHtml ? S.sec("الضغط", "منو كان مسيطر دقيقة بدقيقة", momHtml) : "", tlHtml ? S.sec("خط المباراة", "الأهداف والكروت دقيقة بدقيقة", tlHtml) : "", comm ? S.sec("التعليق", "", comm) : "", aiSum ? S.sec("الخلاصة بالذكاء الاصطناعي", "", aiSum) : "", aiPre, S.winprob(md) ? S.sec("فرص الفوز دقيقة بدقيقة", "", S.winprob(md)) : "", sgrid ? S.sec("أرجح النتايج بالضبط", "", sgrid) : "", opp ? S.sec("تقرير الفريقين", "", opp) : "", press ? S.sec("ورقة الصحفي", "", press) : "", thread ? S.sec("ثريد إكس", "", thread) : "", S.firsts(md) ? S.sec("أوائل", "", S.firsts(md)) : "", replay ? S.sec("إعادة المباراة", "", replay) : "", fa ? S.sec("ضغط المباريات", "", fa) : "", facts && facts.length ? S.sec("قبل المباراة", "", S.matchFacts(facts)) : "", mdy ? S.sec("رايح الملعب؟", "", mdy) : ""].join("")).secs;
    const li = anaSecs.findIndex(sc => sc.title === "فرص الفوز دقيقة بدقيقة"), anaLead = li >= 0 ? anaSecs.splice(li, 1)[0].full : "";
    const faqQ = S.faq(md, (BC[md.comp] && BC[md.comp].broadcasters || []).map(b => b.name_ar).join("، "), md.venue && (md.venue.name_ar || md.venue.name_en));
    const faqHtml = faqQ.length ? `<details class="faq wrap"><summary><h2>أسئلة عن المباراة</h2></summary><dl class="gl">${faqQ.map(q => `<dt>${esc(q[0])}</dt><dd>${esc(q[1])}</dd>`).join("")}</dl></details>` : "";
    const sched = md.status === "scheduled";
    // 369 «ليش هالنتيجة؟» (finished: the first tab's lead) and 372 «مباراة الليلة في 60 ثانية» (before kickoff: a card)
    const why = APPROVED.why && md.status === "finished" && AIWHY[id] && (AIWHY[id].lines || []).length ? `<div class="why"><b>ليش هالنتيجة؟</b>${AIWHY[id].lines.map(l => `<p>${esc(l)}</p>`).join("")}</div>` : "";
    const quick = APPROVED.quick && sched && AIQK[id] && (AIQK[id].lines || []).length ? `<div class="quick" id="quick"><b data-kick="${esc(md.kickoff_utc || "")}">مباراة ${R.dayWord(md.kickoff_utc)} في 60 ثانية</b><ol>${AIQK[id].lines.map(l => `<li>${esc(l)}</li>`).join("")}</ol></div>` : "";
    R._hasWhy = why ? why.replace(/<[^>]+>/g, " ") : false; const catchHtml = R.catchup(md); R._hasWhy = false;
    // W2.6: before kickoff the first tab reads وين تنقل -> lineup status -> 3 facts; after kickoff the events lead
    const luState = sched ? (md.lineups && md.lineups.home && md.lineups.type !== "lastStarting11" ? '<p class="lus">التشكيلة الرسمية نزلت. <a href="#lineups" data-go="lineups">شوفها</a></p>' : '<p class="lus muted">التشكيلة تنزل قبل المباراة بساعة تقريباً.</p>') : "";
    // W3.8 (owner item 4): «شو على المحك» before kickoff — the table rows around both teams and what each result does to their places.
    // Points arithmetic only (points, then goal difference, then goals as a rough order; the real tie-breaks can differ), nothing decided is claimed
    const stakes = (() => { if (!sched || !cdata.st || cdata.st.composite || !cdata.st.groups) return ""; const g = cdata.st.groups.find(g => (g.rows || []).some(r => r.team.id === md.home.id) && g.rows.some(r => r.team.id === md.away.id)); if (!g || g.rows.length < 4) return "";
      const base = g.rows.map((r, i) => ({ id:r.team.id, t:r.team, pts:r.pts || 0, gd:r.gd || 0, gf:r.gf || 0, p:r.played || 0, rk:r.rank || i + 1 })), rank = rows => rows.slice().sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf || a.rk - b.rk).map(r => r.id);
      // "now" is the official table; a scenario re-sorts by points, goal difference, goals, and the official place last, so a team only moves when the arithmetic moves it
      const at = (ids, id) => ids.indexOf(id) + 1, now = base.slice().sort((a, b) => a.rk - b.rk).map(r => r.id), H = md.home.id, A = md.away.id, nm = t => esc(t.name_ar || t.name);
      const play = (hg, ag) => rank(base.map(r => r.id === H ? Object.assign({}, r, { pts:r.pts + (hg > ag ? 3 : hg === ag ? 1 : 0), gd:r.gd + hg - ag, gf:r.gf + hg }) : r.id === A ? Object.assign({}, r, { pts:r.pts + (ag > hg ? 3 : hg === ag ? 1 : 0), gd:r.gd + ag - hg, gf:r.gf + ag }) : r));
      const move = (ids, id) => { const a = at(now, id), b = at(ids, id); return b < a ? `يطلع للمركز ${b}` : b > a ? `ينزل للمركز ${b}` : `يبقى في المركز ${a}`; };
      const sc = [[1, 0, `لو فاز ${nm(md.home)}`], [1, 1, "لو تعادلوا"], [0, 1, `لو فاز ${nm(md.away)}`]].map(([h, a, l]) => { const ids = play(h, a); return `<li><b>${l}:</b> ${nm(md.home)} ${move(ids, H)}، و${nm(md.away)} ${move(ids, A)}.</li>`; }).join("");
      const lo = Math.max(1, Math.min(at(now, H), at(now, A)) - 1), hi = Math.min(now.length, Math.max(at(now, H), at(now, A)) + 1), byId = Object.fromEntries(base.map(r => [r.id, r]));
      const rows = now.slice(lo - 1, hi).map(id => { const r = byId[id]; return `<tr${id === H || id === A ? ' class="stk"' : ""}><td>${r.rk}</td><td class="tm">${R.logo(r.t, "sm")}${nm(r.t)}</td><td>${r.p}</td><td><bdi dir="ltr">${r.gd > 0 ? "+" + r.gd : r.gd}</bdi></td><td>${r.pts}</td></tr>`; }).join("");
      return `<section class="blk stakes" id="stakes"><h2>شو على المحك<small>${esc(g.name && cdata.st.groups.length > 1 ? R.groupOrd ? String(g.name).replace(/^Grp\.?\s*([A-J])$/, (_, l) => R.groupOrd(l)) : g.name : "الترتيب قبل المباراة")}</small></h2><div class="tblwrap"><table class="st"><thead><tr><th>#</th><th style="text-align:start">الفريق</th><th>لعب</th><th>الفارق</th><th>نقاط</th></tr></thead><tbody>${rows}</tbody></table></div><ul class="facts-l">${sc}</ul><p class="src">حساب نقاط بس على الترتيب الحالي، ومباريات الفرق الثانية ممكن تغيّره. الترتيب هنا بالنقاط ثم فارق الأهداف ثم الأهداف.</p></section>`; })();
    // owner item 5: at 1240px and wider the match page has a sticky side column: the mini lineup, the group table, each team's next match
    const mside = (() => { const L = md.lineups || {}, xi = sd => ((L[sd] && L[sd].starters) || []).map(p => `<li><span class="num">${esc(p.number != null ? p.number : "")}</span>${esc(nameOf(p.id) || p.name || "")}</li>`).join("");
      const lu = L.home && (L.home.starters || []).length ? `<section class="blk"><h2>التشكيلة</h2><div class="mxi"><div><h3>${esc(md.home.name_ar || md.home.name)}${L.home.formation ? ` <small class="num">${esc(L.home.formation)}</small>` : ""}</h3><ol>${xi("home")}</ol></div><div><h3>${esc(md.away.name_ar || md.away.name)}${L.away && L.away.formation ? ` <small class="num">${esc(L.away.formation)}</small>` : ""}</h3><ol>${xi("away")}</ol></div></div></section>` : `<section class="blk"><h2>التشكيلة</h2><p class="muted small">${sched ? "تنزل قبل المباراة بساعة تقريباً." : "ما نزلت."}</p></section>`;
      const g = cdata.st && !cdata.st.composite && cdata.st.groups && cdata.st.groups.find(g => (g.rows || []).some(r => r.team.id === md.home.id));
      const tb = g ? `<section class="blk"><h2>الترتيب</h2><div class="tblwrap"><table class="st"><thead><tr><th>#</th><th style="text-align:start">الفريق</th><th>لعب</th><th>نقاط</th></tr></thead><tbody>${g.rows.slice(0, 20).map(r => `<tr${r.team.id === md.home.id || r.team.id === md.away.id ? ' class="stk"' : ""}><td>${r.rank}</td><td class="tm">${R.logo(r.team, "sm")}${esc(r.team.name_ar || r.team.name)}</td><td>${r.played}</td><td>${r.pts}</td></tr>`).join("")}</tbody></table></div></section>` : "";
      const nx = [md.home, md.away].map(t => { const bt = byTeam.get(t.id), m = bt && bt.ms.filter(x => x.status === "scheduled" && x.id !== md.id && Date.parse(x.kickoff_utc) > Date.parse(md.kickoff_utc || 0)).sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc))[0]; return m ? R.matchRow(m, { date:true }) : ""; }).filter(Boolean).join("");
      return `<aside class="mside" aria-label="على الجنب">${lu}${tb}${nx ? `<section class="blk"><h2>المباراة الياية</h2>${nx}</section>` : ""}</aside>`; })();
    const facts3 = sched && facts && facts.length ? `<ul class="facts-l f3">${facts.slice(0, 3).map(f => `<li>${esc(String(f.text_ar).replace(/\s*\(بيانات FotMob\)/g, ""))}</li>`).join("")}</ul>` : "";
    // owner item 9b: «منو بيفوز؟», one tap before kickoff, kept on this phone only (no crowd %, no points, no accounts)
    const pick = sched && md.kickoff_utc && !md.time_tbd ? `<section class="blk pick" id="pick" data-mid="${id}" data-kick="${esc(md.kickoff_utc)}" data-h="${md.home.id}" data-a="${md.away.id}"><h2>منو بيفوز؟<small>توقعك يبقى في جوالك</small></h2><div class="pickb" role="group" aria-label="توقعك"><button type="button" data-p="h" aria-pressed="false">${esc(md.home.name_ar || md.home.name)}</button><button type="button" data-p="d" aria-pressed="false">تعادل</button><button type="button" data-p="a" aria-pressed="false">${esc(md.away.name_ar || md.away.name)}</button></div><p class="small muted" id="pickm" role="status"></p></section>` : "";
    const eventsPane = sched ? `<div id="wwbox" data-comp="${md.comp}">${ww ? S.sec("وين تنقل في الإمارات", "", ww) : ""}</div>` + luState + quick + pick + stakes + facts3 + (probs ? S.probs(probs, md) : "") + `<div id="catchup"></div><div id="ltable"></div>` + (anaSecs.length ? shelf(anaSecs, { title:"قبل المباراة بالتفصيل" }) : "") + `<div id="events" hidden>${R.events(md)}</div><h3 class="sub-h">تفاصيل المباراة</h3><div id="facts">${R.matchFacts(md, index)}</div>`
      : why + quick + `<div id="catchup">${catchHtml}</div>` + `<div id="hlbtn">${R.hl(md)}</div>` + (hl && !R.hl(md) ? `<p class="hlink">${hl}</p>` : "") + `<div id="events">${R.events(md)}</div><div id="ltable"></div>` + (md.status !== "finished" ? `<div id="wwbox" data-comp="${md.comp}">${ww ? S.sec("وين تنقل في الإمارات", "", ww) : ""}</div>` : "") + `<h3 class="sub-h">تفاصيل المباراة</h3><div id="facts">${R.matchFacts(md, index)}</div>`;
    const names = {}; if (md.venue && md.venue.name_ar) names.venue = md.venue.name_ar; if (md.referee && md.referee.name_en) names.ref = md.referee.name;
    if (md.lineups) ["home", "away"].forEach(sd => { const co = md.lineups[sd] && md.lineups[sd].coach; if (coachAr(co)) names[co.id] = coachAr(co); });
    (md.events || []).forEach(e => [e.player, e.assist, e.player_out].forEach(p => { if (p && p.id && nameOf(p.id)) names[p.id] = nameOf(p.id); }));
    if (md.lineups) ["home", "away"].forEach(sd => md.lineups[sd] && [].concat(md.lineups[sd].starters || [], md.lineups[sd].subs || [], md.lineups[sd].unavailable || []).forEach(p => { if (p && p.id && nameOf(p.id)) names[p.id] = nameOf(p.id); }));
    [md.home.id, md.away.id].forEach(tid => { const tj = teamById.get(tid); ((tj && tj.squad) || []).forEach(g => (g.players || []).forEach(p => { if (p && p.id && nameOf(p.id)) names[p.id] = nameOf(p.id); })); });   // squads: live subs/scorers stay Arabic
    // the players of this match that have a page (window.PP): the browser's live redraws link only those, as the build's dead-link pass does
    const mpp = {}, addP = p => { if (p && p.id && allPlayers[p.id]) mpp[p.id] = 1; }; (md.events || []).forEach(e => [e.player, e.assist, e.player_out].forEach(addP));
    if (md.lineups) ["home", "away"].forEach(sd => md.lineups[sd] && [].concat(md.lineups[sd].starters || [], md.lineups[sd].subs || [], md.lineups[sd].unavailable || []).forEach(addP));
    [md.home.id, md.away.id].forEach(tid => { const tj = teamById.get(tid); ((tj && tj.squad) || []).forEach(g => (g.players || []).forEach(addP)); });
    const recent = Date.parse(md.kickoff_utc || 0), ogOn = uaeMatch || (recent > Date.now() - 3 * 864e5 && recent < Date.now() + 7 * 864e5 && [538, 11027, 329, 525, 9469, 536, 47, 87, 42].includes(md.comp));
    // item 11: every other match gets its card through the share stage (og/s/m-<id>.png, uploaded once, newest first under og.py's
    // budget) and every goal of the last 7 days a card and a share page /m/<id>/g/<n>/; a page shows a staged card once it is published
    const cardJ = { key:"m-" + id, home:md.home.name_ar || md.home.name, away:md.away.name_ar || md.away.name, home_id:md.home.id, away_id:md.away.id, hc:colors[md.home.id], ac:colors[md.away.id], comp:md.comp_name_ar || R.compName(index, md.comp), score:md.score && md.status === "finished" ? `${md.score.away} - ${md.score.home}` : null, time:md.score && md.status === "finished" ? null : R.hhmm(md.kickoff_uae), sub:md.score && md.status === "finished" ? "انتهت" : R.dayLabel(R.ymd(md.kickoff_uae)) + " بتوقيت الإمارات" };
    if (!ogOn) SHJ.push([Math.abs(recent - Date.now()), Object.assign({ stage:true }, cardJ)]);
    const mOg = ogOn ? "m-" + id : SHPUB["og:m-" + id] ? "s/m-" + id : "match";
    const gstub = []; { const gs = (md.events || []).filter(e => /^(goal|penalty_goal|own_goal)$/.test(e.type)), fresh = recent > Date.now() - 7 * 864e5 && md.status !== "scheduled";
      gs.forEach((e, i) => { const n = i + 1, who = (e.player && (nameOf(e.player.id) || e.player.name)) || "", mn = e.minute + (e.added ? "+" + e.added : ""), sc0 = e.score || {}, gk = `${mn}-${(e.player && e.player.id) || 0}`;
        if (!fresh || !e.score){ if (SHPUB[`g:${id}/${n}`]) { gstub.push(n); WRITTEN.add(`/m/${id}/g/${n}`); } return; }   // a goal without the score after it gets no card
        const how = e.type === "penalty_goal" ? "من ركلة جزاء" : e.type === "own_goal" ? "" : (e.how && e.how.ar) || "", clip = !!(CLIPS[id] && CLIPS[id].has(gk));
        SHG.push([recent, { key:`g-${id}-${n}`, kind:"goal", stage:true, home:cardJ.home, away:cardJ.away, home_id:md.home.id, away_id:md.away.id, hc:cardJ.hc, ac:cardJ.ac, comp:cardJ.comp, sh:sc0.home ?? "", sa:sc0.away ?? "", side:e.team, who, minute:mn, how, own:e.type === "own_goal", clip }]);
        // og:image: the share stage puts the goal's own card in place of __GIMG__ once og.py has drawn it, else the match's card
        const gimg = "__GIMG__", H1 = cardJ.home, A1 = cardJ.away, gt = `${e.type === "own_goal" ? "هدف عكسي" : "هدف"} ${who} ${mn}'`, gsc = `${H1} ${sc0.home ?? ""} - ${sc0.away ?? ""} ${A1}`, to = `/m/${id}/#g${n}`;
        STUBS.push({ mid:id, n, card:`g-${id}-${n}`, img:`${SITE}/og/${mOg}.png`, site:SITE, html:`<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(gt)} | ${esc(gsc)} | تيفو</title><meta name="description" content="${esc(`${gt}${how ? "، " + how : ""}: ${gsc} في ${cardJ.comp}.${clip ? " شاهد الهدف على تيفو." : ""}`)}"><meta name="robots" content="noindex"><link rel="canonical" href="${SITE}/m/${id}/">` +
          `<meta property="og:type" content="website"><meta property="og:site_name" content="تيفو"><meta property="og:title" content="${esc(gt)} · ${esc(gsc)}"><meta property="og:description" content="${esc(`${cardJ.comp}${how ? " · " + how : ""}${clip ? " · شاهد الهدف" : ""}`)}"><meta property="og:url" content="${SITE}/m/${id}/g/${n}/"><meta property="og:locale" content="ar_AE"><meta property="og:image" content="${gimg}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image">` +
          `<meta http-equiv="refresh" content="0;url=${to}"><script>location.replace(${JSON.stringify(to)})</script><style>body{background:#0A2620;color:#F6F7F2;font:16px system-ui;padding:2rem}a{color:#F6F7F2}</style></head><body><p><a href="${to}">${esc(gt)}: ${esc(gsc)}</a></p></body></html>` });
        gstub.push(n); WRITTEN.add(`/m/${id}/g/${n}`); }); }
    // 426: one valid SportsEvent — no nested superEvent (Google read it as a second event with no date or place); the competition is the
    // organizer and part of the description; image, endDate (kickoff + 2 h) and performer where the data has them
    const ld = (() => { const st = { postponed:"https://schema.org/EventPostponed", cancelled:"https://schema.org/EventCancelled" }[md.status] || "https://schema.org/EventScheduled", H = md.home.name_ar || md.home.name, A = md.away.name_ar || md.away.name, v = md.venue || {};   // 348
      const cn = md.comp_name_ar || R.compName(index, md.comp) || "", rd = md.round && /^\d+$/.test(String(md.round)) ? "الجولة " + md.round : md.round ? R.stageAr(md.round) : "", t0 = Date.parse(md.kickoff_utc || "");
      const teams = [{ "@type":"SportsTeam", name:H }, { "@type":"SportsTeam", name:A }], vn = fixAl(v.name_ar || v.name_en || v.name || "");
      return { "@context":"https://schema.org", "@type":"SportsEvent", name:`${H} ضد ${A}`, url:`${SITE}/m/${id}/`, startDate:md.kickoff_uae || md.kickoff_utc, ...(t0 && !md.time_tbd ? { endDate:new Date(t0 + 2 * 36e5).toISOString() } : {}), sport:"Football", eventStatus:st, eventAttendanceMode:"https://schema.org/OfflineEventAttendanceMode",
        image:[`${SITE}/og/${mOg}.png`], description:[md.status === "finished" && md.score ? `انتهت ${H} ${md.score.home} - ${md.score.away} ${A}` : `${H} ضد ${A}`, cn, rd].filter(Boolean).join(" · "),
        homeTeam:teams[0], awayTeam:teams[1], competitor:teams, performer:teams, ...(cn ? { organizer:{ "@type":"SportsOrganization", name:cn, url:R.compKey(index, md.comp) ? `${SITE}/c/${R.compKey(index, md.comp)}/` : SITE } } : {}),
        ...(vn ? { location:{ "@type":"StadiumOrArena", name:vn, ...(v.city || v.country || v.in_uae ? { address:{ "@type":"PostalAddress", ...(v.city ? { addressLocality:String(v.city).split(",")[0].trim() } : {}), ...(v.country || v.in_uae ? { addressCountry:v.in_uae ? "AE" : v.country } : {}) } } : {}), ...(v.lat != null ? { geo:{ "@type":"GeoCoordinates", latitude:v.lat, longitude:v.lon } } : {}) } } : {}) }; })();
    if (ogOn && OGM.add(+id)) OGJ.push(Object.assign({}, cardJ, md.status === "finished" ? { sizes:["story", "feed", "x"] } : {}));   // 381: platform sizes for results
    if (mOg !== "match") OGM.add(+id);
    // v5 match page (src/v5/pages.js P.match): the club-colour header with the score, then المباراة (قبل المباراة) · التشكيلة · الأرقام
    // · المواجهات. The v3 page's analysis blocks are rows in «بالتفصيل» that open their sheets; the win-probability curve, the exact
    // scores, the pressure and the firsts are v5's own sheets; the FAQ stays on the page (folded) for search
    const dd = String(md.kickoff_uae || "").slice(0, 10).replace(/-/g, "");
    const ana5 = anaSecs.filter(sc => !["الضغط", "فرص الفوز دقيقة بدقيقة", "أرجح النتايج بالضبط", "أوائل"].includes(sc.title) || (sc.title === "الضغط" && !(md.momentum && md.momentum.length >= 5)));
    const stakes5 = (() => { if (!stakes || !cdata.st || !cdata.st.groups) return null; const g = cdata.st.groups.find(g => (g.rows || []).some(r => r.team.id === md.home.id) && g.rows.some(r => r.team.id === md.away.id)); if (!g || (g.rows || []).length < 4) return null;
      const ix = tid => g.rows.findIndex(r => r.team.id === tid), a = ix(md.home.id), b = ix(md.away.id), lo = Math.max(0, Math.min(a, b) - 1), hi = Math.min(g.rows.length, Math.max(a, b) + 2), hl = { [md.home.id]:1, [md.away.id]:1 };
      const sc = (stakes.match(/<ul class="facts-l">[\s\S]*?<\/ul>/) || [""])[0];
      return U.grp("شو على المحك", U.table(g.rows.slice(lo, hi), { hl }) + (sc ? `<div class="lc stk">${sc}</div>` : ""), { id:"stakes", foot:"حساب نقاط بس على الترتيب الحالي، ومباريات الفرق الثانية ممكن تغيّره. الترتيب بالنقاط ثم فارق الأهداف ثم الأهداف." }); })();
    const top5 = (why ? `<section class="grp"><div class="card lc">${why}</div></section>` : "") + (quick ? `<section class="grp"><div class="card lc">${quick}</div></section>` : "") + (!sched && catchHtml ? `<section class="grp"><div class="gh"><h2>الخلاصة</h2></div><div class="card lc" id="catchup">${catchHtml}</div></section>` : !sched ? '<div id="catchup" class="lc" hidden></div>' : "");
    const faq5 = faqQ.length ? `<section class="grp faqg"><details class="card dz faq"><summary class="row"><span class="rt"><b>أسئلة عن المباراة</b></span>${U.chev}</summary><dl class="lc gl">${faqQ.map(q => `<dt>${esc(q[0])}</dt><dd>${esc(q[1])}</dd>`).join("")}</dl></details></section>` : "";
    const p3d5 = md.lineups && md.lineups.home ? U.grp("", U.row({ btn:1, icon:"grid", c:"#34C759", t:"شوفها على ملعب ثلاثي الأبعاد", attrs:` id="p3dbtn" data-src="/assets/pitch3d.${ASSET_V}.js"` }) + '<div id="p3d"></div>', { cls:"p3dg" }) : "";
    const hk = [md.home.id, md.away.id].sort((a, b) => a - b).join("-");
    const sized5 = ogOn && md.status === "finished" ? `<div class="row ins"><span class="ic" style="--c:#FF2D55">${U.icon("image", "", 2)}</span><span class="rt">صورة النتيجة<small>${[["story", "ستوري"], ["feed", "بوست"], ["x", "إكس"]].map(z => `<a href="/og/m-${id}-${z[0]}.png" download="tifo-${id}-${z[0]}.png">${z[1]}</a>`).join(" · ")}</small></span></div>` : "";
    const posterOn = !!ENG.poster && (md.status === "finished" || md.status === "awarded") && md.score && md.score.home != null && (md.events || []).length > 0 && (() => {   // bold idea 10: src/poster.js draws it from /v1/match/<id>.json
      const n = { home:0, away:0 }; for (const e of md.events || []) if (/^(goal|penalty_goal|own_goal)$/.test(e.type)) n[e.team === "away" ? "away" : "home"]++;
      return n.home === +md.score.home && n.away === +md.score.away; })();   /* only with every goal of the score in the file: its ring places each one */
    const camOn = !!ENG.cam && (R.isLive(md) || (md.status === "scheduled" && !md.time_tbd && Math.abs(Date.parse(md.kickoff_utc) - Date.now()) < 3 * 36e5) || (md.status === "finished" && Date.now() - Date.parse(md.kickoff_utc) < 4 * 36e5));   // bold idea 13: around the match only
    const share5 = P5.shareSheet({ top:`<img class="shprev" src="/og/${mOg}.png" alt="" width="1200" height="630" loading="lazy">`,
      acts:[["image", "صورة للستوري", ' id="storybtn"'], ["tv", "شاشة المجلس", "", `/tv/?m=${id}`], ["phone", "الشاشة الثانية", ' id="secondbtn"']].concat(uaeMatchTop ? [["shirt", "عدّة صانع المحتوى", "", `/m/${id}/kit/`]] : []),
      html:sized5 + (posterOn ? U.row({ btn:1, icon:"brush", c:"#AF52DE", t:"بوستر المباراة", sub:"لوحة من أرقامها، تنزّلها أو تطبعها", attrs:' data-sheet="sh-poster"' }) : "") +
        (camOn ? U.row({ href:`/cam/?m=${id}`, icon:"eye", c:"#FF9500", t:"الكاميرا الذكية (تجريبية)", sub:"وجّه جوالك على التلفزيون، والأرقام فوق الصورة" }) : "") + (md.lineups && md.lineups.home ? U.row({ btn:1, icon:"people", c:"#5856D6", t:"بطاقة لاعب", sub:"أداء أي لاعب في المباراة", attrs:' id="pcardbtn"' }) : "") + U.row({ btn:1, icon:"tv", c:"#1C7C54", t:"وضع السينما", sub:"النتيجة والدقيقة بخط كبير", attrs:" data-cine" }) +
        U.row({ btn:1, icon:"link", c:"#0A84FF", t:"ضمّن المباراة في موقعك", attrs:` id="embedbtn" data-src="/embed/m/?id=${id}&d=${esc(dd)}" data-h="260"` }) + U.row({ btn:1, icon:"image", c:"#8E8E93", t:"صورة لأي قسم", attrs:' id="secpick"' }),
      after:'<div id="embout" class="card mt lc" hidden></div><div id="secpicks" class="card mt" hidden></div>' });
    const hlx = md.status === "finished" && !(md.highlights && md.highlights.url) && hl ? (hl.match(/href="([^"]+)"/) || [])[1] : null;
    const v5 = P5.match(md, { st:cdata.st, ch:ww ? (() => { const e = BCBY.AE && BCBY.AE[md.comp]; return e && e.b && e.b.length ? e.b.slice(0, 4).map(x => `<div class="row"><span class="rt">${esc(x[0])}${x[5] ? `<small>${esc(x[5])}</small>` : ""}</span>${x[1] ? "" : '<span class="chip enc">مشفرة</span>'}</div>`).join("") : (bcAE && bcAE.broadcasters || []).slice(0, 4).map(b => `<div class="row"><span class="rt">${esc(b.name_ar || b.name || "")}</span></div>`).join(""); })() : null, og:ogOn ? 1 : 0, hl:hlx,
      x:{ top:top5, stakes:stakes5, predict:(md.status === "scheduled" && !md.time_tbd) || R.isLive(md) || (md.status === "finished" && Date.now() - Date.parse(md.kickoff_utc || 0) < 3 * 864e5) ? TPM.block(md) : "", facts:facts3 ? `<section class="grp"><div class="gh"><h2>قبل المباراة</h2></div><div class="card lc">${facts3}</div></section>` : "", ana:shelf(ana5, { title:sched ? "قبل المباراة بالتفصيل" : "التحليل" }), faq:faq5, p3d:p3d5, h2h:H2H[hk] ? `/h2h/${hk}/` : null, share:share5,
        after:`<script type="application/json" id="msum">${JSON.stringify(Object.assign({}, sum, { events:undefined, lineups:undefined, stats:undefined, h2h:undefined })).replace(/</g, "\\u003c")}</script>` } });
    v5.data = { id:+id, comp:md.comp, status:md.status, live:R.isLive(md) || (md.status === "scheduled" && Date.parse(md.kickoff_utc) - Date.now() < 3 * 36e5 && Date.parse(md.kickoff_utc) - Date.now() > -3 * 36e5) ? 1 : 0, ko:md.kickoff_utc || null, h:md.home.id, a:md.away.id,
      hn:md.home.name_ar || md.home.name || "", an:md.away.name_ar || md.away.name || "", sc:md.score ? [md.score.home, md.score.away] : null, cn:md.comp_name_ar || "",
      hc:((teamById.get(md.home.id) || {}).squad || []).length ? 1 : 0, ac:((teamById.get(md.away.id) || {}).squad || []).length ? 1 : 0 };   // hc/ac: a squad to pick from (src/coach.js)   // cn: the season trail (src/trail.js)
    // «اصنع التيفو» (src/mosaic.js) opens 3 h before kickoff and closes 2 h after the end: its script goes on the pages of
    // matches within a day of now (rebuilt hourly), not on the archive's thousands
    const fanJs = !md.time_tbd && Math.abs(Date.parse(md.kickoff_utc || 0) - Date.now()) < 30 * 36e5 ? [ENG.mosaic, ENG.mood, ENG.stream] : [];   // the stand, «نبض الجمهور» (bold idea 9: /v1/mood/<id>.json from news/xmood.js) and «شوفها مباشر ببلاش» (/v1/streams.json from news/streams.py)
    // «رجل المباراة بصوت الجمهور» (src/motm.js) votes from the whistle until 48 h after the end: from a day before kickoff to 52 h after
    const coachJs = ENG.coach && !md.time_tbd && Date.parse(md.kickoff_utc || 0) > Date.now() - 2 * 864e5 && Date.parse(md.kickoff_utc || 0) < Date.now() + 3 * 864e5 && (((teamById.get(md.home.id) || {}).squad || []).length || ((teamById.get(md.away.id) || {}).squad || []).length) ? [ENG.coach] : [];   // «مدرّب الدكة» (second list 3): from 3 days before to 2 after
    const koT = Date.parse(md.kickoff_utc || 0), motmJs = !md.time_tbd && koT > Date.now() - 52 * 36e5 && koT < Date.now() + 30 * 36e5 ? [ENG.motm] : [];
    // 444: «موعد مباراة X و Y» before it, «نتيجة مباراة X و Y» once it has a score
    const cN = md.comp_name_ar || R.compName(index, md.comp), H0 = PN(md.home), A0 = PN(md.away), played = !!(md.score && (md.status === "finished" || R.isLive(md)));
    const when = !md.kickoff_uae ? "والموعد ما تأكد" : R.dayLabel(R.ymd(md.kickoff_uae)) + (md.time_tbd ? "، والساعة ما تأكدت" : ` الساعة ${R.hhmm(md.kickoff_uae)} بتوقيت الإمارات`);
    const mT = played ? `نتيجة مباراة ${H0} و${A0} ${md.score.home}-${md.score.away} في ${cN} | تيفو` : `موعد مباراة ${H0} و${A0} في ${cN}${ww ? " والقناة الناقلة" : ""} | تيفو`;
    const mD = played ? `${md.status === "finished" ? "انتهت" : "مباشر:"} مباراة ${H0} و${A0} ${md.score.home}-${md.score.away} في ${cN}: الأهداف والأحداث والتشكيلة والإحصائيات والمواجهات السابقة.` : `موعد مباراة ${H0} و${A0} في ${cN} ${when}${ww ? "، والقناة الناقلة" : ""}، مع التشكيلة والأرقام والمواجهات السابقة.`;
    const mck = (comps.find(cc => cc.id === md.comp) || {}).key, mBc = bcLd([mck && [cN, `/c/${mck}/`], [`${H0} و${A0}`, `/m/${id}/`]]);
    v5.body = v5.body.replace('<div id="ev">', `<div id="ev" data-gstub="${gstub.join(",")}">`);   // item 11: the goals whose page /m/<id>/g/<n>/ was published (src/goalshare.js)
    write(`m/${id}/index.html`, page({ v5, near:R.isLive(md) || (md.status === "finished" && Date.now() - Date.parse(md.kickoff_utc || 0) < 4 * 36e5),   /* QA 4: an upcoming match is never marked stale (its time is not live data) */ og:mOg, ogv:mOg !== "match" && md.status === "finished" && md.score ? `ft-${md.score.home}-${md.score.away}` : "", path:`/m/${id}/`, page:"match", nav:"home", attrs:` data-id="${id}"`, names, pp:mpp, title:mT, desc:mD, js:[`/assets/goalshare.${GS_V}.js`].concat(fanJs, motmJs, posterOn ? [ENG.poster] : [], [ENG.trail], coachJs, [ENG.badges]), ld:[ld].concat(faqQ.length ? [{ "@context":"https://schema.org", "@type":"FAQPage", mainEntity:faqQ.map(q => ({ "@type":"Question", name:q[0], acceptedAnswer:{ "@type":"Answer", text:q[1] } })) }] : [], [mBc]) }));
    urls.push(`/m/${id}/`);
    if (uaeMatch && (md.status === "scheduled" || Date.parse(md.kickoff_utc) > Date.now() - 3 * 864e5)){
      const nums = [probs ? `توقعات تيفو: ${Math.round(probs.home * 100)}% فوز ${md.home.name_ar}، ${Math.round(probs.draw * 100)}% تعادل، ${Math.round(probs.away * 100)}% فوز ${md.away.name_ar}.` : "", ...((factsByMatch[id] || []).map(f => String(f.text_ar).replace(/\s*\(بيانات FotMob\)/g, "")))].filter(Boolean);
      write(`m/${id}/kit/index.html`, page({ art:[colors[md.home.id] || ["#5C6660"], colors[md.away.id] || ["#3D4A44"]], path:`/m/${id}/kit/`, page:"kit", attrs:` data-id="${id}"`, title:`عدّة صانع المحتوى: ${R.tname(md.home)} و${R.tname(md.away)} | تيفو`, desc:`أرقام جاهزة للنسخ وصور للمشاركة وموعد المباراة في كل دولة عربية مع القناة الناقلة.`,
        body:`<p class="crumbs"><a href="/m/${id}/">المباراة</a></p><h1>عدّة صانع المحتوى</h1><p class="season">${R.tname(md.home)} و${R.tname(md.away)}</p><script type="application/json" id="msum">${JSON.stringify(Object.assign({}, sum, { events:undefined, lineups:undefined, stats:undefined, h2h:undefined })).replace(/</g, "\\u003c")}</script>` +
          S.sec("أرقام جاهزة للنسخ", "", nums.length ? '<ol class="thread">' + nums.map(n => `<li><p>${esc(n)}</p><button type="button" class="btn copy" data-copy="${esc(n)}">انسخ</button></li>`).join("") + "</ol>" : '<p class="empty">ما في أرقام للحين.</p>') +
          '<p class="tools"><button type="button" class="btn" id="storybtn">صورة ستوري للمباراة</button><button type="button" class="btn" id="embedbtn" data-src="/embed/m/?id=' + id + '&d=' + String(md.kickoff_uae || "").slice(0, 10).replace(/-/g, "") + '" data-h="260">ضمّن المباراة في موقعك</button></p><div id="embout"></div>' +
          S.sec("الموعد والقناة في كل دولة عربية", "", `<div id="kitct" data-comp="${md.comp}" data-ko="${esc(md.kickoff_uae || "")}"><p class="empty skel">نجهّز الجدول…</p></div>`) }));
    }
  }
  R.DUPCTX = "";   // 503: back to no context

  // ---- 7b. majlis TV (22, 131) and the Tifo studio (152)
  write("tv/index.html", page({ path:"/tv/", page:"tv", title:"شاشة المجلس: كل المباريات مباشر على شاشة كبيرة | تيفو", desc:"افتحها على تلفزيون المجلس أو القهوة: كل مباريات اليوم مباشر بخط كبير، تتحدّث بروحها كل 20 ثانية.",
    body:'<div class="tvbar"><h1>شاشة المجلس</h1><button type="button" class="btn" id="fsbtn">الشاشة كاملة</button></div><div id="tv" class="tvgrid"><p class="empty skel">نحمّل المباريات…</p></div><p class="muted small">افتح هالصفحة على تلفزيون المجلس. تتحدّث بروحها كل 20 ثانية. ولمتابعة مباراتين جنب بعض، افتح أي مباراة، وفي «شارك وأدوات» اختار «تلفزيون المجلس».</p>' }));
  urls.push("/tv/");
  const clubs = [5789].concat(((compData.find(d => d.c.id === 538) || {}).st || { groups:[{ rows:[] }] }).groups[0].rows.map(r => r.team.id));
  write("studio/index.html", page({ path:"/studio/", page:"studio", title:"ستوديو التيفو: صمّم لافتة فريقك للمدرج | تيفو", desc:"اختار فريقك واكتب عبارتك، وتطلع لك لافتة بألوان النادي جاهزة للطباعة وتاخذها للملعب.",
    body:`<h1>ستوديو التيفو</h1><p class="muted">اختار فريقك واكتب عبارتك، وتطلع لك لافتة بألوان ناديك (3000×1000) جاهزة للطباعة.</p><div class="studio"><div class="cmpsel"><select id="sclub" aria-label="الفريق">${clubs.map(id => `<option value="${id}">${esc((teamsJson.teams[id] || {}).name_ar || id)}</option>`).join("")}</select><input id="stext" maxlength="40" value="ما نمشي بروحنا" aria-label="العبارة"></div><canvas id="sprev" width="1500" height="500"></canvas><p class="small"><a href="/lab/">المختبر: قارن أي رقمين لكل لاعبين الدوري</a></p><div class="tools"><button type="button" class="btn" id="sdl">نزّل اللافتة</button></div></div>` }));
  urls.push("/studio/");

  // ---- 7c. Tifo Cast (161): only when approved; audio copied next to the pages (19, the round recap, was dropped 2026-09-27)
  const casts = [];
  if (APPROVED.podcast) for (const [k, p] of Object.entries(AIC)) if (!p.held && fs.existsSync(path.join(CACHE, "ai/podcast", k + ".mp3"))) casts.push({ kind:"podcast", key:k, title:p.title, file:`/audio/podcast-${k}.mp3`, src:path.join(CACHE, "ai/podcast", k + ".mp3"), lines:p.lines });
  if (casts.length){
    fs.mkdirSync(path.join(OUT, "audio"), { recursive:true }); casts.forEach(c => fs.copyFileSync(c.src, path.join(OUT, c.file)));
    casts.sort((a, b) => b.key.localeCompare(a.key));
    write("cast/index.html", page({ path:"/cast/", page:"cast", title:"تيفو كاست: الجولة بصوت إماراتي | تيفو", desc:"بودكاست تيفو كاست الأسبوعي: حامد ومها يسولفون عن جولة دوري أدنوك.",
      body:"<h1>تيفو كاست</h1>" + casts.map(c => S.sec(esc(c.title), "بودكاست الأسبوع", `<audio controls preload="none" src="${c.file}"></audio><details class="more"><summary>النص</summary>${c.lines ? c.lines.map(l => `<p><b>${({ hamed:"حامد", maha:"مها", zayd:"زايد", hala:"هلا" })[l.who] || ""}:</b> ${esc(l.text)}</p>`).join("") : `<p>${esc(c.text)}</p>`}</details>`)).join("") }));
    urls.push("/cast/");
    // 354: podcast RSS for Apple Podcasts / Spotify (the owner submits it himself)
    try { require("child_process").execFileSync("python3", [path.join(__dirname, "cast_cover.py")], { stdio:"ignore" }); fs.copyFileSync(path.join(CACHE, "cast_cover.jpg"), path.join(OUT, "cast/cover.jpg")); } catch (e){ console.error("cast cover failed"); }
    const x = t => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const dur = f => { try { return Math.round(parseFloat(require("child_process").execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]).toString())); } catch (e){ return 0; } };
    const hms = n => [Math.floor(n / 3600), Math.floor(n / 60) % 60, n % 60].map(v => String(v).padStart(2, "0")).join(":");
    const desc = "بودكاست تيفو كاست الأسبوعي: حامد ومها يسولفون عن جولة دوري أدنوك للمحترفين، بالأرقام واللهجة الإماراتية.";
    const items = casts.map(c => { const p = AIC[c.key], size = fs.statSync(c.src).size, d = dur(c.src), when = new Date(p.generated || Date.now()).toUTCString();
      return `<item><title>${x(c.title)}</title><description>${x((p.lines || []).slice(0, 2).map(l => l.text).join(" "))}</description><guid isPermaLink="false">tifo-cast-${c.key}</guid><pubDate>${when}</pubDate><enclosure url="${SITE}${c.file}" length="${size}" type="audio/mpeg"/>${d ? `<itunes:duration>${hms(d)}</itunes:duration>` : ""}<itunes:episodeType>full</itunes:episodeType><itunes:explicit>false</itunes:explicit><link>${SITE}/cast/</link></item>`; }).join("\n");
    fs.writeFileSync(path.join(OUT, "cast/feed.xml"), `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>تيفو كاست</title><link>${SITE}/cast/</link><atom:link href="${SITE}/cast/feed.xml" rel="self" type="application/rss+xml"/><language>ar</language><copyright>Elyoxe</copyright>
<description>${x(desc)}</description><itunes:summary>${x(desc)}</itunes:summary><itunes:author>تيفو</itunes:author><itunes:owner><itunes:name>Elyoxe</itunes:name><itunes:email>hello@elyoxe.com</itunes:email></itunes:owner>
<itunes:image href="${SITE}/cast/cover.jpg"/><image><url>${SITE}/cast/cover.jpg</url><title>تيفو كاست</title><link>${SITE}/cast/</link></image><itunes:category text="Sports"><itunes:category text="Soccer"/></itunes:category><itunes:explicit>false</itunes:explicit><itunes:type>episodic</itunes:type>
${items}
</channel></rss>
`);
  }
  // ---- 7d. matches of the week (25): the next 7 days, UAE first, then by what's at stake
  const in7 = [...matchSum.values()].filter(m => m.status === "scheduled" && m.kickoff_utc && Date.parse(m.kickoff_utc) > Date.now() && Date.parse(m.kickoff_utc) < Date.now() + 7 * 864e5);
  const wscore = m => { let v = 0; if (R.UAE_COMPS.indexOf(m.comp) >= 0) v += 100; if (m.home.id === 5789 || m.away.id === 5789) v += 150; const w = compX[m.comp] && compX[m.comp].watch && compX[m.comp].watch.matches[m.id]; if (w) v += w.score; const st = (compData.find(d => d.c.id === m.comp) || {}).st; if (st && st.groups && !st.composite){ const rk = id => { const r = st.groups[0].rows.find(r => r.team.id === id); return r ? r.rank : 20; }; v += Math.max(0, 40 - 2 * (rk(m.home.id) + rk(m.away.id))); } if ([42, 525].includes(m.comp)) v += 20; return v; };
  const picks = in7.map(m => ({ m, v:wscore(m) })).sort((a, b) => b.v - a.v).slice(0, 12).sort((a, b) => a.m.kickoff_utc.localeCompare(b.m.kickoff_utc));
  write("week/index.html", page({ path:"/week/", page:"week", title:"مباريات الأسبوع اللي تستاهل تسهر لها | تيفو", desc:"أهم 12 مباراة في الأسبوع الياي بتوقيت الإمارات: الإماراتية أول، وبعدها اللي الترتيب فيها على المحك.",
    body:`<p class="tools"><button type="button" class="btn" id="wkbtn">صورة جدول الأسبوع بتوقيت بلدك</button></p><script type="application/json" id="wkdata">${JSON.stringify(picks.map(x => ({ h:x.m.home.id, a:x.m.away.id, home:x.m.home.name_ar || x.m.home.name, away:x.m.away.name_ar || x.m.away.name, ko:x.m.kickoff_uae, comp:x.m.comp }))).replace(/</g, "\\u003c")}</script>` + "<h1>مباريات الأسبوع</h1><!--MOW--><p class=\"muted\">أهم مباريات الأيام السبعة الياية بتوقيت الإمارات: مباريات الإمارات أول، وبعدها اللي فيها الترتيب على المحك أو الفريقين من فوق الجدول.</p>" + (picks.length ? picks.map(x => `<div class="wk"><span class="muted small">${esc(x.m.comp_name_ar || R.compName(index, x.m.comp))}</span>${R.matchRow(x.m, { date:true })}</div>`).join("") : '<p class="empty">ما في مباريات في الأيام الياية.</p>') }));
  urls.push("/week/");

  // ---- 224 records tonight (home), 226 referee pages, 227 coach pages, 228 round pages
  { const tonight = (day.matches || []).flatMap(m => (factsByMatch[m.id] || []).filter(f => f.record_at_stake).map(f => ({ m, f })));
    const rt = S.recordsTonight(tonight); if (rt) ED.push(S.sec("أرقام ممكن تنكسر اليوم", "", rt)); }
  const byIdM = id => matchSum.get(id) || D.get(id);
  const stIds = cid => { const d = compData.find(x => x.c.id === cid); return d && d.st && !d.st.composite && d.st.groups && d.st.groups[0] ? d.st.groups[0].rows.map(r => r.team.id) : []; };
  const refs = new Map(); compData.forEach(({ c, x }) => ((x.referees && x.referees.referees) || []).forEach(r => { if (r.id && !refs.has(r.id)) refs.set(r.id, Object.assign({ comp:c }, r)); }));
  // QA 87: the referee's country in Arabic (the feed sends FIFA codes), never «UAE»
  const C3 = { UAE:"الإمارات", ARE:"الإمارات", KSA:"السعودية", SAU:"السعودية", QAT:"قطر", KUW:"الكويت", KWT:"الكويت", BHR:"البحرين", OMA:"عُمان", OMN:"عُمان", JOR:"الأردن", IRQ:"العراق", SYR:"سوريا", LBN:"لبنان", PLE:"فلسطين", PSE:"فلسطين", EGY:"مصر", MAR:"المغرب", ALG:"الجزائر", DZA:"الجزائر", TUN:"تونس", LBY:"ليبيا", SDN:"السودان", YEM:"اليمن", AUS:"أستراليا", JPN:"اليابان", KOR:"كوريا الجنوبية", CHN:"الصين", IRN:"إيران", UZB:"أوزبكستان", ENG:"إنجلترا", ESP:"إسبانيا", ITA:"إيطاليا", GER:"ألمانيا", FRA:"فرنسا", POR:"البرتغال", NED:"هولندا", BRA:"البرازيل", ARG:"الأرجنتين" };
  for (const [rid, r] of refs){ const thinR = (r.matches || 0) < 3; write(`r/${rid}/index.html`, page({ noindex:thinR, path:`/r/${rid}/`, page:"ref", title:`الحكم ${r.name}: كروته وبلنتياته ومبارياته | تيفو`, desc:`سجل الحكم ${r.name} في ${r.comp.name_ar}: الإنذارات والطرد وضربات الجزاء بالمباراة، وكل مبارياته.`, body:`<p class="crumbs"><a href="/c/${r.comp.key}/#num">${esc(r.comp.name_ar)}</a></p>${refAr(r) ? `<h1>${esc(refAr(r))}</h1>` : `<h1 class="lat">${esc(r.name)}</h1>`}<p class="season">حكم${C3[r.country] ? " من " + C3[r.country] : ""}${refAr(r) && r.name_en && r.name_en !== refAr(r) ? ` · <span class="lat">${esc(r.name_en)}</span>` : ""}</p>` + S.refPage(r, id => D.get(id) || byIdM(id)) })); if (!thinR) urls.push(`/r/${rid}/`); }
  const coachRows = new Map(); compData.forEach(({ x }) => { const ct = x.coaches && x.coaches.teams; if (!ct) return; for (const [tid, t] of Object.entries(ct)){ (t.history || []).forEach(h => { const k = h.id || h.name; if (!coachRows.has(k)) coachRows.set(k, { name:h.name, rows:[] }); coachRows.get(k).rows.push(Object.assign({ team:+tid }, h)); }); if (t.current){ const k = t.current.id || t.current.name; if (!coachRows.has(k)) coachRows.set(k, { name:t.current.name, rows:[] }); coachRows.get(k).current = +tid; } } });
  // 315/316: full careers (coaches/{id}.json) for every coach of the analytics leagues and Arab national teams, and coach-vs-coach records
  const CIDX = await get("coaches/index.json"), CH2H = new Map();
  if (CIDX && CIDX.coaches){ const cf = await pool(CIDX.coaches, 8, c => get(`coaches/${c.id}.json`, 2));
    CIDX.coaches.forEach((c, i) => { const f = cf[i]; if (!f || !f.rows || !f.rows.length) return; const prev = coachRows.get(c.id) || coachRows.get(c.name); if (coachRows.has(c.name) && c.name !== c.id) coachRows.delete(c.name);
      coachRows.set(c.id, { name:f.name, rows:f.rows.map(r => Object.assign({}, r)), current:f.current_team || (prev && prev.current) }); });
    const hs = await pool(CIDX.h2h || [], 8, h => get(`coaches/h2h/${h.pair}.json`, 1));
    hs.forEach(h => { if (!h || !h.coaches) return; const [a, b] = h.coaches; [[a, b], [b, a]].forEach(([me, op]) => { if (!CH2H.has(me)) CH2H.set(me, []); CH2H.get(me).push({ op, name:h.names[op], w:h.wins[me] || 0, d:h.wins.draws || 0, l:h.wins[op] || 0 }); }); }); }
  for (const [cid, co] of coachRows){ const a = COACH_AR[cid] && COACH_AR[cid].ar; if (a && !co.name_en){ co.name_en = co.name; co.name = a; } }
  for (const list of CH2H.values()) list.forEach(o => { const a = COACH_AR[o.op] && COACH_AR[o.op].ar; if (a) o.name = a; });
  { const cj = {}; for (const [cid, co] of coachRows) if (co.rows.length) cj[cid] = { n:co.name, r:co.rows.map(r => [r.season, r.team, (teamsJson.teams[r.team] || {}).name_ar || "", r.won, r.drawn, r.lost]) };
    const cjs2 = JSON.stringify(cj), CV = hash(cjs2); fs.writeFileSync(path.join(OUT, `assets/coaches.${CV}.json`), cjs2);   // W1.11: hashed, since /assets/ is cached for a year
    write("coach/compare/index.html", page({ noindex:true, attrs:` data-cv="${CV}"`, path:"/coach/compare/", page:"coachcmp", title:"قارن بين مدربين | تيفو", desc:"قارن أي مدربين درّبوا في الدوري: المباريات والفوز ومعدل النقاط والأندية.", body:'<h1>قارن بين مدربين</h1><div class="cmpsel"><select id="ca" aria-label="المدرب الأول"></select><select id="cb" aria-label="المدرب الثاني"></select></div><div id="cout"></div>' })); }
  for (const [cid, co] of coachRows){ if (!co.rows.length) continue; co.rows.sort((a, b) => String(b.season).localeCompare(String(a.season)));
    write(`coach/${cid}/index.html`, page({ path:`/coach/${cid}/`, page:"ref", title:`المدرب ${co.name}: مسيرته التدريبية | تيفو`, desc:`مسيرة المدرب ${co.name}: الأندية والمواسم والفوز والتعادل والخسارة ومعدل النقاط.`, body:`<h1 class="lat">${esc(co.name)}</h1><p><a class="btn" href="/coach/compare/?a=${cid}">قارنه بمدرب ثاني</a></p>${co.current ? `<p class="season">يدرّب الحين <a href="/t/${co.current}/">${esc((teamsJson.teams[co.current] || {}).name_ar || "")}</a></p>` : ""}` + S.coachPage(co.name, co.rows, [...new Set(co.rows.map(r => r.comp && R.compName(index, r.comp)).filter(Boolean))].join("، ")) + (CH2H.has(cid) ? S.sec("ضد المدربين", "هالموسم", '<div class="tblwrap"><table class="st wrapn"><thead><tr><th style="text-align:start">المدرب</th><th>فوز</th><th>تعادل</th><th>خسارة</th></tr></thead><tbody>' + CH2H.get(cid).sort((a, b) => (b.w + b.d + b.l) - (a.w + a.d + a.l)).map(o => `<tr><td class="tm">${coachRows.has(o.op) ? `<a class="lat" href="/coach/${o.op}/">${esc(o.name || "")}</a>` : `<span class="lat">${esc(o.name || "")}</span>`}</td><td>${o.w}</td><td>${o.d}</td><td>${o.l}</td></tr>`).join("") + "</tbody></table></div>") : "") })); urls.push(`/coach/${cid}/`); }
  for (const { c, fx, x } of compData){ if (!fx || !fx.matches) continue; R.DUPCTX = (c.country && c.country.name_ar) || ""; const rr = R.rounds(fx);
    for (const k of rr.order){ if (!/^\d+$/.test(String(k))) continue;   /* QA 99: round pages only for numbered rounds (no «3rd Place Final» paths) */ const ms = rr.by[k], fin = ms.filter(m => m.status === "finished"), goals = fin.reduce((a, m) => a + (m.score ? m.score.home + m.score.away : 0), 0);
      const tor = x["team-of-round"] && x["team-of-round"].rounds && x["team-of-round"].rounds[k] ? S.teamOfRound({ rounds:{ [k]:x["team-of-round"].rounds[k] } }) : "";
      write(`c/${c.key}/r/${k}/index.html`, page({ lg:LOGO(c.id) ? [c.id].concat(glow(c.id)) : null, path:`/c/${c.key}/r/${k}/`, page:"ref", nav:String(c.id), title:`نتائج ومواعيد الجولة ${k} من ${c.name_ar} ${c.season || ""} | تيفو`, ld:bcLd([[c.name_ar, `/c/${c.key}/`], [`الجولة ${k}`, `/c/${c.key}/r/${k}/`]]), desc:`نتايج ومواعيد الجولة ${k} من ${c.name_ar} بتوقيت بلدك، والأهداف وتشكيلة الجولة.`,
        body:`<p class="crumbs"><a href="/c/${c.key}/">${esc(c.name_ar)}</a></p><h1>الجولة ${esc(k)}</h1>` + (fin.length ? `<div class="pstats"><div><b>${fin.length}</b><span>مباراة خلصت</span></div><div><b>${goals}</b><span>هدف</span></div><div><b>${fin.length ? (goals / fin.length).toFixed(1) : 0}</b><span>بالمباراة</span></div></div>` : "") + R.roundList(ms) + (fin.length && stIds(c.id).length ? S.sec("قصة الجولة", "الترتيب يتغيّر مع كل نتيجة", S.roundStory(fx, k, stIds(c.id))) : "") + (tor ? S.sec("تشكيلة الجولة", "", tor) : "") + `<p class="tools">${(() => { const nr = rr.order.filter(x => /^\d+$/.test(String(x))), i = nr.indexOf(k); return (i > 0 ? `<a class="btn" href="/c/${c.key}/r/${nr[i - 1]}/">الجولة اللي قبل</a>` : "") + (i >= 0 && i < nr.length - 1 ? `<a class="btn" href="/c/${c.key}/r/${nr[i + 1]}/">الجولة اللي بعد</a>` : ""); })()}</p>` })); urls.push(`/c/${c.key}/r/${k}/`); } }
  R.DUPCTX = "";   // 503: back to no context

  // ---- 198 / owner item 9 (2026-10-06): «مباريات اليوم والقنوات الناقلة والمعلقين» — /today/, /tomorrow/, /yesterday/, /matches/<date>/,
  // /matches/ and «مباراة <فريق> اليوم» (lib/seo_days.cjs over v1/all + v1/tv; rows by src/days.js, which the browser re-runs live)
  const DAYS = await require("./lib/seo_days.cjs")({ get, pool, write, page, esc, SITE, CACHE, fs, path, bcLd, comps, BCBY, LG365, matchSum, details:D, matchPages:new Set(mids.map(String)),
    logoOk:id => logoIds.has(+id), ogOf:id => `${SITE}/og/${OGM.has(+id) ? "m-" + id : "match"}.png`, teamPages, byTeam, S_TEAMS, R, index, bigTeams:BIGT });
  DAYS.urls.forEach(u => urls.push(u));
  // every match of the day (owner 2026-09-30); the browser keeps it live (v1/all/live.json every 30 s)
  write("all/index.html", page({ v5:homeV5(today, day.matches, { h1:"كل المباريات", world:1 }), path:"/all/", page:"all", nav:"home", title:"كل المباريات اليوم مباشر: كل الدوريات في العالم | تيفو",
    desc:"كل مباريات اليوم في العالم مباشر: مئات المباريات من كل الدوريات والبطولات، والدوريات العربية كلها، بالنتيجة والدقيقة أول بأول وبتوقيت بلدك." }));
  urls.push("/all/");
  write("live/index.html", page({ path:"/live/", page:"live", nav:"home", noindex:true, title:"مباراة مباشر | تيفو", desc:"أحداث المباراة والتشكيلة والأرقام مباشر، وكيف انسجل كل هدف.",
    body:'<p class="crumbs"><a href="/all/">كل المباريات</a></p><h1 id="lvt">نحمّل المباراة…</h1><p class="season" id="lvs"></p><div id="allm" data-kind="live"><div id="lvh" class="lvh"></div><div id="lvhl"></div>' +
      tabsHtml("lv", [["events", "الأحداث"], ["lineups", "التشكيلة"], ["stats", "الأرقام"]]) + pane("lv", "events", '<div id="lve"><p class="empty">نحمّل…</p></div>', true) + pane("lv", "lineups", '<div id="lvl"></div>') + pane("lv", "stats", '<div id="lvst"></div>') + '<p class="src" id="lvsrc"></p></div>' }));

  // ---- 262 glossary, 251 lab, 289 academy
  const GLOSS = require("./src/glossary.js");
  const labComps = compData.filter(d => d.x.players && d.x.players.players && Object.keys(d.x.players.players).length > 20).map(d => d.c);
  if (labComps.length){ write("lab/index.html", page({ path:"/lab/", page:"lab", title:"مختبر تيفو: قارن أي رقمين لكل لاعبين الدوري | تيفو", desc:"اختار أي رقمين (تسديدات، أهداف، مراوغات، افتكاك…) وشوف كل لاعبين الدوري على رسم واحد.", body:'<h1>مختبر تيفو</h1><p class="muted">اختار الدوري ورقمين، وكل لاعب يطلع نقطة. اللي فوق وعلى اليسار أحسن في الرقمين.</p><div class="labsel"><select id="lcomp" aria-label="الدوري">' + labComps.map(c => `<option value="${c.id}">${esc(c.name_ar)}</option>`).join("") + '</select><select id="lx" aria-label="الرقم الأفقي"></select><select id="ly" aria-label="الرقم العمودي"></select><input id="lq" placeholder="ظلّل لاعب بالاسم" aria-label="ظلّل لاعب"></div><div id="lplot"><p class="empty skel">نحمّل…</p></div>' })); urls.push("/lab/"); }
  { const x5 = compX[538] || {}, lessons = [];
    const topR = ratings && ratings.teams && ratings.teams.filter(t => t.in_league)[0]; if (topR) lessons.push(["tifo-rating", "تصنيف تيفو: منو أقوى فريق؟", `كل فريق له رقم قوة يتغيّر بعد كل مباراة. الحين أقوى فريق في دوري أدنوك ${esc(topR.name_ar)} بـ<b class="num">${Math.round(topR.rating)}</b>، والفريق المتوسط حوالي 1500.`, "/c/uae-pro-league/#num"]);
    const nm = [...matchSum.values()].find(m => m.status === "scheduled" && m.probs && m.comp === 538); if (nm) lessons.push(["probabilities", "نسب الفوز: مب توقع أكيد", `مباراة ${R.tname(nm.home)} و${R.tname(nm.away)}: تيفو يعطي فوز ${R.tname(nm.home)} <b class="num">${Math.round(nm.probs.home * 100)}%</b>. يعني لو انلعبت 100 مرة، بيفوز تقريباً ${Math.round(nm.probs.home * 100)} مرة، مب إنه أكيد بيفوز.`, `/m/${nm.id}/`]);
    const sim = x5.sim; if (sim){ const best = Object.entries(sim.teams).sort((a, b) => b[1].title - a[1].title)[0]; lessons.push(["simulator", "محاكي الموسم", `لعبنا باقي الموسم ${Number(sim.sims).toLocaleString("en-US")} مرة. ${esc((teamsJson.teams[best[0]] || {}).name_ar || "")} خلص أول في <b class="num">${Math.round(best[1].title * 100)}%</b> منها، وهذي فرصته للبطولة.`, "/c/uae-pro-league/#pred"]); }
    const xgl = compX[47] && compX[47].xg && compX[47].xg.rows; if (xgl){ const lk = xgl.slice().sort((a, b) => b.luck - a.luck)[0]; lessons.push(["xg", "الأهداف المتوقعة والحظ", `في الدوري الإنجليزي، ${esc((teamsJson.teams[lk.team] || {}).name_ar || "")} جمع <b class="num">${lk.pts}</b> نقطة، والمتوقع من أدائه <b class="num">${lk.xpts.toFixed(1)}</b>. الفرق هو «الحظ».`, "/c/premier-league/#table"]); }
    const sty = x5.style && x5.style.teams; if (sty){ const pr = Object.entries(sty).filter(([, v]) => v.style.ppda != null).sort((a, b) => a[1].style.ppda - b[1].style.ppda)[0]; if (pr) lessons.push(["ppda", "الضغط: الرقم الأقل أقوى", `${esc((teamsJson.teams[pr[0]] || {}).name_ar || "")} يخلّي الخصم يلعب بس <b class="num">${pr[1].style.ppda.toFixed(1)}</b> تمريرة قبل ما يحاول يقطع الكورة، وهذا أعلى ضغط في الدوري.`, "/c/uae-pro-league/#num"]); }
    const cl = x5.clutch && x5.clutch.players && x5.clutch.players[0]; if (cl) lessons.push(["clutch", "منو الحاسم؟", `${esc(((allPlayers[cl.id] || {}).name) || "")} جاب لفريقه <b class="num">${cl.total}</b> نقاط بأهدافه وصناعته، يعني نقاط ما كانت بتجي بدونه.`, `/p/${cl.id}/`]);
    lessons.push(["difficulty", "صعوبة المباريات", "كل مباراة ياية لها لون: الفاتح سهلة والغامق صعبة، حسب تصنيف الخصم ووين تنلعب. تنفعك تعرف منو جدوله أسهل للقب.", "/c/uae-pro-league/#pred"]);
    // W4.2: the academy's worked examples sit under their glossary terms now; /academy/ points there
    const EX = {}; lessons.forEach(l => { EX[l[0]] = l; }); const GL2 = GLOSS.map(g => g.concat([EX[g[0]]])).concat(lessons.filter(l => !GLOSS.some(g => g[0] === l[0])).map(l => [l[0], l[1].replace(/:.*$/, ""), "", l]));
    write("glossary/index.html", page({ path:"/glossary/", page:"ref", title:"قاموس مصطلحات الكورة بالإماراتي | تيفو", desc:"شرح بسيط لكل مصطلح في تيفو، ومع كل رقم مثال حقيقي من الدوري: الأهداف المتوقعة، الضغط، تصنيف تيفو، محاكي الموسم، التسلل، الفار وغيرها.", body:"<h1>قاموس المصطلحات</h1><p class=\"muted\">شرح بسيط لكل مصطلح يطلع في تيفو، ومع أرقامنا مثال من مباريات حقيقية.</p><dl class=\"gl\">" + GL2.map(g => `<dt id="${g[0]}">${esc(g[1])}</dt><dd>${g[2] ? esc(g[2]) : ""}${g[3] ? `<p class="ex"><b>مثال:</b> ${g[3][2]} <a href="${g[3][3]}">شوفها في الموقع</a></p>` : ""}</dd>`).join("") + "</dl>" })); urls.push("/glossary/");
    stub("/academy/", "/glossary/", "قاموس المصطلحات"); }

  // 184 newsletter, 333 watch mode, 230 countdowns
  write("newsletter/index.html", page({ path:"/newsletter/", page:"newsletter", title:"نشرة تيفو الأسبوعية | تيفو", desc:"كل خميس في إيميلك: نتايج الأسبوع، والترتيب، ومباريات الأسبوع الياي بتوقيت بلدك.", body:'<h1>نشرة تيفو</h1><p class="muted">كل خميس في إيميلك: النتايج، والترتيب، ومباريات الأسبوع الياي بتوقيت بلدك. بدون إزعاج، وتقدر تلغي بضغطة.</p><div id="nlmsg" role="status"></div><form class="ask nlform"><input type="email" name="email" required dir="ltr" autocomplete="email" placeholder="إيميلك" aria-label="إيميلك"><button class="btn" type="submit">اشترك</button></form>' })); urls.push("/newsletter/");
  stub("/w/", "/tv/?mine=1", "وضع المتابعة");   // W4.2: watch mode is شاشة المجلس with your teams (/tv/?mine=1)
  { const soon = [...matchSum.values()].filter(m => m.status === "scheduled" && m.kickoff_utc && Date.parse(m.kickoff_utc) > Date.now() && Date.parse(m.kickoff_utc) < Date.now() + 60 * 864e5);
    const big = soon.filter(m => { const nat = [m.home.id, m.away.id].some(t => (teamsJson.teams[t] || {}).national) || m.home.id === 5789 || m.away.id === 5789; const k = [m.home.id, m.away.id].sort((a, b) => a - b).join("-"); const w = compX[m.comp] && compX[m.comp].watch && compX[m.comp].watch.matches[m.id]; return nat || R.H2HK[k] || (w && w.score >= 80) || /final|نهائي/i.test(m.stage || ""); }).sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc)).slice(0, 20);
    write("countdowns/index.html", page({ path:"/countdowns/", page:"countdowns", title:"عدّادات المباريات الكبيرة | تيفو", desc:"كم باقي على الديربيات ومباريات المنتخبات والنهائيات، بتوقيت بلدك.", body:"<h1>كم باقي؟</h1>" + (big.length ? big.map(m => `<a class="cd" href="/m/${m.id}/"><span><b>${R.tname(m.home)} و${R.tname(m.away)}</b><br><span class="small">${esc(m.comp_name_ar || R.compName(index, m.comp))}، ${R.td(m.kickoff_uae, true)}</span></span><span class="dg cdt" data-u="${esc(m.kickoff_utc)}">—</span></a>`).join("") : '<p class="empty">ما في مباريات كبيرة قريبة.</p>') })); urls.push("/countdowns/"); }

  // ---- 7e. phase 4 reference pages (research/tifo-2026-09-27 + Arabic from ai/history_ar.py)
  const RS = path.join(require("os").homedir(), "workspace/research/tifo-2026-09-27"), HC = path.join(CACHE, "history");
  const rj = (f) => { try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch (e){ return null; } };
  const hl = rj(path.join(HC, "legends.json")) || {}, hm = rj(path.join(HC, "memorable.json")) || {}, ht = rj(path.join(HC, "thisday.json")) || {}, hw = rj(path.join(HC, "laws.json")) || {};
  const legRaw = (rj(path.join(RS, "legends.json")) || {}).players || [];
  const memRaw = (rj(path.join(RS, "memorable.json")) || {}).matches || [], tdRaw = (rj(path.join(RS, "thisday.json")) || {}).events || [], lawRaw = (rj(path.join(RS, "laws.json")) || {}).topics || [];
  const refPage = (p, title, desc, h1, lead, body) => { if (!body) return; write(p.slice(1) + "index.html", page({ path:p, page:"ref", title, desc, body:`<h1>${h1}</h1><p class="muted">${lead}</p>` + body })); urls.push(p); };
  refPage("/legends/", "أساطير الكورة الإماراتية | تيفو", "الطلياني وإسماعيل مطر وعمر عبدالرحمن وعلي مبخوت وغيرهم: مسيرتهم وأرقامهم، مع المصادر.", "أساطير الكورة الإماراتية", "مسيرة وأرقام أبرز لاعبين في تاريخ الكورة الإماراتية، وكل معلومة معها مصدرها.", S.legends(legRaw, hl, id => playerPages.has(String(id))) + '<p class="tools"><a class="btn" href="/memorable/">مباريات ما تنتسى</a></p>');   // W2.8: memorable matches sit under الأساطير
  refPage("/memorable/", "مباريات ما تنتسى في تاريخ الكورة الإماراتية | تيفو", "من تصفيات 1990 لين نهائي آسيا 2024: المباريات اللي صنعت تاريخ الكورة الإماراتية.", "مباريات ما تنتسى", "مباريات صنعت تاريخ الكورة الإماراتية، من الأحدث للأقدم.", S.memorable(memRaw, hm));
  refPage("/laws/", "قانون الكورة بالإماراتي: التسلل، اللمسة، البلنتي، الفار | تيفو", "ليش ألغى الحكم الهدف؟ شرح قوانين الكورة الرسمية (IFAB 2026/27) بالإماراتي: التسلل، لمسة اليد، البلنتي، الفار، والوقت بدل الضايع.", "قانون الكورة بالإماراتي", "شرح بسيط لقوانين الكورة من النص الرسمي لـIFAB (نسخة 2026/27)، وتحت كل شرح الجملة الرسمية نفسها.", S.laws(lawRaw, hw));
  const mmddToday = today.slice(5);
  const tdToday = S.thisday(tdRaw, ht, mmddToday, 8);
  // W4.1: today first («اليوم، 28 سبتمبر» with أمس/بكرة), every other day folded by month; the client re-picks "today" in the visitor's time zone
  const MON = ["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"], tdDays = [...new Set(tdRaw.map(e => e["mm-dd"]))].sort().map(md => [md, S.thisday(tdRaw, ht, md, 20)]).filter(x => x[1]);
  const tdSec = ([md, x]) => { const [mo, dd] = md.split("-").map(Number); return `<section class="blk" data-md="${md}"><h2>${dd} ${MON[mo - 1]}</h2>${x}</section>`; };
  const tdNear = (() => { const i = tdDays.findIndex(x => x[0] >= mmddToday); return i < 0 ? 0 : i; })(), tdT = tdDays.find(x => x[0] === mmddToday);
  const tdHead = `<section class="blk tdnow" id="tdnow" data-md="${mmddToday}"><div class="tdnav"><button type="button" class="ib" data-td="-1" >أمس</button><h2 id="tdh">اليوم، ${+mmddToday.slice(3)} ${MON[+mmddToday.slice(0, 2) - 1]}</h2><button type="button" class="ib" data-td="1" >بكرة</button></div><div id="tdb">${tdT ? tdT[1] : `<p class="muted">ما عندنا حدث مسجّل في هاليوم. أقرب يوم: ${tdDays.length ? tdSec(tdDays[tdNear]).replace(/^<section[^>]*><h2>([^<]*)<\/h2>[\s\S]*$/, "$1") : "—"}</p>`}</div></section>`;
  const tdAll = tdDays.length ? tdHead + MON.map((mn, i) => { const ds = tdDays.filter(x => +x[0].slice(0, 2) === i + 1); return ds.length ? `<details class="tdm"><summary>${mn} <span class="muted small num">${ds.length}</span></summary>${ds.map(tdSec).join("")}</details>` : ""; }).join("") : "";
  refPage("/thisday/", "هذا اليوم في تاريخ الكورة الإماراتية | تيفو", "كل يوم في السنة وشو صار فيه في تاريخ الكورة الإماراتية: مباريات وبطولات ومواليد الأساطير.", "هذا اليوم في كورة الإمارات", "أحداث من تاريخ الكورة الإماراتية لكل يوم في السنة، ومع كل حدث مصدره.", tdAll);

  { const d5 = APPROVED.daily5 && AID5[today.replace(/-/g, "")]; if (d5 && d5.items) ED.unshift(S.sec("أهم 5 أشياء اليوم", "", '<ol class="facts-l">' + d5.items.map(x => `<li>${esc(x)}</li>`).join("") + "</ol>")); }
  if (tdToday) ED.push(S.sec("هذا اليوم في كورة الإمارات", '<a href="/thisday/">كل الأيام</a>', tdToday));

  // «اسأل تيفو» (76): only after the owner approves sample answers
  // /messi/ — the Messi museum (owner 2026-09-30, lib/messi_page.cjs): rooms prerendered here, 3D and games in the browser
  { const MS = await get("legends/messi/shots.json");
    if (MS && MS.matches && MS.matches.length){
      const [MP, MM, MX, MPL] = await Promise.all([get("legends/messi/play.json"), get("legends/messi/matches.json"), get("legends/messi/extra.json"), get("player/30981.json")]);
      const TN = {}; Object.values(S_TEAMS).forEach(t => { if (t && t.name && t.name_ar && !TN[t.name]) TN[t.name] = t.name_ar; });
      const PNL = {}; Object.values(NAMES_AR).forEach(v => { if (v && v.latin && v.ar && !PNL[v.latin]) PNL[v.latin] = v.ar; });
      const MANUAL = { "Barcelona":"برشلونة", "Paris Saint-Germain":"باريس سان جيرمان", "Argentina":"الأرجنتين", "Inter Miami":"إنتر ميامي", "Inter Miami CF":"إنتر ميامي", "Real Madrid":"ريال مدريد", "Atlético Madrid":"أتلتيكو مدريد",
        // StatsBomb's names for the clubs and countries our data has no Arabic for (relegated since, or outside our leagues)
        "AC Ajaccio":"أجاكسيو", "AS Monaco":"موناكو", "Albacete":"ألباسيتي", "Almería":"ألميريا", "Bordeaux":"بوردو", "CD Numancia de Soria":"نومانسيا",
        "Charlotte":"شارلوت", "Chile":"تشيلي", "Cincinnati":"سينسيناتي", "Clermont Foot":"كليرمون", "Cádiz":"قادش", "Córdoba CF":"قرطبة", "Eibar":"إيبار",
        "Gimnàstic Tarragona":"خيمناستيك", "Girona":"جيرونا", "Granada":"غرناطة", "Huesca":"ويسكا", "Hércules":"هيركوليس", "Iceland":"آيسلندا",
        "LAFC":"لوس أنجلوس إف سي", "Las Palmas":"لاس بالماس", "Leganés":"ليغانيس", "Levante UD":"ليفانتي", "Mallorca":"مايوركا", "Metz":"ميتز",
        "Montpellier":"مونبلييه", "Nantes":"نانت", "Nashville SC":"ناشفيل", "New York Red Bulls":"نيويورك ريد بولز", "OGC Nice":"نيس",
        "Olympique de Marseille":"مارسيليا", "Poland":"بولندا", "RC Deportivo La Coruña":"ديبورتيفو لاكورونيا", "Real Murcia CF":"ريال مورسيا",
        "Real Valladolid":"بلد الوليد", "Real Zaragoza":"سرقسطة", "Recreativo Huelva":"ريكرياتيفو ويلفا", "Saint-Étienne":"سانت إتيان",
        "Sporting Gijón":"سبورتينغ خيخون", "Stade Brestois":"بريست", "Stade de Reims":"ريمس", "Tenerife":"تينيريفي", "Toronto FC":"تورونتو", "Xerez":"خيريز",
        // the museum's own names that neither our data nor Wikidata's exact English label resolve
        "Alexis Sánchez":"أليكسيس سانشيز", "Dani Alves":"داني ألفيش", "Lionel Sebastián Scaloni":"ليونيل سكالوني", "Marc-André ter Stegen":"مارك أندريه تير شتيغن", "Sergi Roberto":"سيرجي روبيرتو", "Xavi":"تشافي" };
      const ar = n => TN[n] || MANUAL[n] || PNL[n] || (MX && MX.names_ar && MX.names_ar[n]) || n;
      // «ميسي الحين»: Inter Miami's last and next match, and his season line from FotMob
      const mt = typeof teamById !== "undefined" && teamById.get(960720), fx = mt ? R.teamFixtures(mt) : null, now = {};
      if (fx && fx.past[0]){ const m = fx.past[0]; now.last = `${R.tname(m.home)} <bdi dir="ltr" class="num">${esc(String((m.score || {}).home ?? ""))}-${esc(String((m.score || {}).away ?? ""))}</bdi> ${R.tname(m.away)}، ${R.td(m.kickoff_uae, true)}`; }
      if (fx && fx.next[0]){ const m = fx.next[0]; now.next = `<a href="/m/${m.id}/">${R.tname(m.home)} ضد ${R.tname(m.away)}</a>، ${R.td(m.kickoff_uae, true)}`; }
      if (MPL && MPL.goals != null) now.season = `هالموسم مع إنتر ميامي: ${MPL.goals} هدف و${MPL.assists} تمريرة حاسمة في ${Math.round((MPL.minutes || 0) / 90)} مباراة كاملة من الدقايق · <a href="/p/30981/">صفحته</a>`;
      const museum = require("./lib/messi_page.cjs")({ shots:MS, play:MP, matches:MM, extra:MX, now, transfersHtml:trPlayer(30981) }, { esc, ar, eur, clubCell, ASSET_V });
      write("messi/index.html", page({ path:"/messi/", page:"messi", title:"متحف ميسي: كل أهدافه وتمريراته وألقابه على ملعب ثلاثي الأبعاد | تيفو", desc:`${museum.total ? museum.total.goals + " هدف" : museum.goals + " هدف"} لليونيل ميسي في متحف تفاعلي: من وين يسجل ووين تروح الكورة بالـ3D، تمريراته وشراكاته، ألقابه وكراته الذهبية، رحلة قطر 2022، وألعاب.`, body:museum.body, ld:bcLd([["ليونيل ميسي", "/p/30981/"], ["متحف ميسي", "/messi/"]]) }));
      write("messi/poster/index.html", page({ path:"/messi/poster/", page:"poster", noindex:true, title:"بوستر متحف ميسي للطباعة | تيفو", desc:"كل أهداف ميسي على ملعب واحد، جاهز للطباعة.", body:museum.poster }));
      urls.push("/messi/");
    } }
  // the world encyclopedia (db/world.py + src/world.js): every club of ~300 leagues and every player of their squads, one template each.
  // v5: the index prerenders the champions by country (365Scores' competitions), search and the clubs by country load in the browser
  { const CN = S365I.countries || {}, by = {}, WI = (await get("world/index.json")) || {};
    (S365I.comps || []).filter(c => c[5] > 0 && !c[11]).forEach(c => { (by[c[3]] = by[c[3]] || []).push(c); });
    const AR = [124, 122, 115, 131, 127, 139, 135, 114, 126, 119, 123, 125, 161, 130, 116, 117, 226, 170];   // 365's ids of the Arab countries, first
    const keys = Object.keys(by).map(Number).sort((a, b) => { const ia = AR.indexOf(a), ib = AR.indexOf(b); if (ia >= 0 || ib >= 0) return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib); return ((CN[a] || [""])[0] || "").localeCompare((CN[b] || [""])[0] || "", "ar"); });
    const byCountry = keys.map(cc => [(CN[cc] || [""])[0] || "دولية", by[cc].sort((a, b) => b[5] - a[5]).map(c => [c[0], c[1], c[6], c[7], c[5], c[8]])]);
    const v5 = P5.db({ nComps:(S365I.comps || []).length, nClubs:(WI.clubs || []).length + (S365I.teams || []).filter(t => !t[4]).length, nPlayers:(WI.n_players || 0) + (S365I.players || []).length, byCountry }); v5.data = {};
    v5.body = v5.body.replace('<div id="widle">', U.grp("", U.row({ href:"/db/players/", icon:"people", c:"#5856D6", t:"اللاعبين حسب الجنسية", sub:"كل دولة ولاعبينها في الموسوعة" })) + '<div id="widle">');   // main's nationality hubs
    write("db/index.html", page({ v5, path:"/db/", page:"db", title:"موسوعة تيفو: كل أندية ولاعبين العالم | تيفو", desc:"آلاف الأندية من 94 دولة وعشرات الآلاف من اللاعبين: الألقاب، الملاعب، التشكيلات، المسيرة موسم بموسم." })); urls.push("/db/"); }
  write("db/club/index.html", page({ path:"/db/club/", page:"world", noindex:true, title:"نادي | موسوعة تيفو", desc:"بطاقة النادي من موسوعة تيفو.", body:'<p class="crumbs"><a href="/db/">الموسوعة</a></p><h1 id="wt">نحمّل…</h1><div id="world" data-kind="club"></div>' }));
  write("db/match/index.html", page({ path:"/db/match/", page:"world", noindex:true, title:"مباراة | موسوعة تيفو", desc:"تفاصيل المباراة من موسوعة تيفو.", body:'<p class="crumbs"><a href="/db/">الموسوعة</a></p><h1 id="wt">نحمّل…</h1><div id="world" data-kind="match"></div>' }));
  write("db/player/index.html", page({ path:"/db/player/", page:"world", noindex:true, title:"لاعب | موسوعة تيفو", desc:"بطاقة اللاعب من موسوعة تيفو.", body:'<p class="crumbs"><a href="/db/">الموسوعة</a></p><h1 id="wt">نحمّل…</h1><div id="world" data-kind="player"></div>' }));
  // every competition's champions through history as a real page (db/scores365.py): 5 champions or more, no youth competitions
  // owner item 10 (2026-10-06): a league with a live season on 365Scores (the Arab leagues FotMob lacks) leads with the season
  // (lib/seo_leagues.cjs: table, next matches, results, scorers), and each of its clubs gets a static /db/team/<id>/
  const LDOCS = {}; await pool([...LG365], 8, async cid => { LDOCS[cid] = await get(`s365/comp/${cid}.json`, 1); });
  const ST365 = new Map(), ST365C = {}; { const SLt = require("./lib/seo_leagues.cjs")({ page, write, SITE, bcLd, teamLink:() => "" }), ids = new Set();
    for (const [cid, d] of Object.entries(LDOCS)){ const s = d && d.live && SLt.season(cid, d); if (s) s.teams.forEach(t => { ids.add(+t); if (!ST365C[t] && !d.ko) ST365C[t] = { id:+cid, name:d.name }; }); }
    const tf = await pool([...ids], 8, id => SID2F[id] && S_TEAMS[SID2F[id]] ? null : get(`s365/team/${id}.json`, 1));   // a club with a FotMob page keeps /t/<id>/
    [...ids].forEach((id, i) => { const t = tf[i]; if (t && t.name && ((t.games || []).length || (t.squad || []).length)) ST365.set(id, t); }); }   // only clubs whose page gets written are linked
  { const tl = t => { const f = SID2F[t]; return f && S_TEAMS[f] ? `/t/${f}/` : ST365.has(+t) ? `/db/team/${t}/` : `/db/team/?id=${t}`; }, CN = S365I.countries || {};
    const SL = require("./lib/seo_leagues.cjs")({ page, write, SITE, bcLd, teamLink:tl });
    const tbl = (rows, N) => `<div class="tscroll"><table class="tbl"><thead><tr><th>#</th><th>الفريق</th><th>لعب</th><th>فوز</th><th>تعادل</th><th>خسارة</th><th>له-عليه</th><th>نقاط</th></tr></thead><tbody>${rows.map(r => `<tr><td class="num">${r[0] == null ? "" : r[0]}</td><td><a href="${tl(r[1])}">${esc(N[r[1]] || "")}</a>${r[9] != null ? ` <span class="muted small">${esc(r[9])}</span>` : ""}</td>${[2, 3, 4, 5].map(i => `<td class="num">${r[i] == null ? "" : r[i]}</td>`).join("")}<td class="num"><bdi dir="ltr">${r[6] == null ? "" : r[6]}-${r[7] == null ? "" : r[7]}</bdi></td><td class="num">${r[8] == null ? "" : Math.round(r[8])}</td></tr>`).join("")}</tbody></table></div>`;
    const dstr = s => { const d = s ? new Date(s) : null; return d && !isNaN(d) ? d.toLocaleDateString("ar-AE-u-nu-latn", { year:"numeric", month:"short", day:"numeric", timeZone:"Asia/Dubai" }) : ""; };
    const grow = (g, N) => `<li><span class="num muted small">${esc(dstr(g[1]))}</span> <a href="${tl(g[4])}">${esc(N[g[4]] || "")}</a> ${g[6] == null ? "" : `<a href="/db/game/?id=${g[0]}"><bdi dir="rtl" class="num">${g[6]} - ${g[7]}</bdi></a>`} <a href="${tl(g[5])}">${esc(N[g[5]] || "")}</a></li>`;
    const logo365 = id => "https://imagecache.365scores.com/image/upload/f_png,w_128,h_128,c_limit,q_auto:eco,dpr_2,d_Competitions:default1.png/Competitions/" + id;
    let nL = 0, nS = 0;
    await pool([...LG365], 8, async cid => { const d = LDOCS[cid]; if (!d || !(d.champions || []).length) return;
      const N = Object.assign({}, d.names || {}), CH = d.champions, won = CH.filter(r => r[1]); if (won.length < 5) return;
      for (const k of Object.keys(N)){ const f = SID2F[k]; if (f && S_TEAMS[f] && S_TEAMS[f].name_ar) N[k] = S_TEAMS[f].name_ar; }   // our Arabic name for a club we know
      const cnt = new Map(); won.forEach(r => cnt.set(r[1], (cnt.get(r[1]) || 0) + 1));
      const top = [...cnt.entries()].sort((a, b) => b[1] - a[1]), mx = top[0][1], first = CH[CH.length - 1][0], last = CH[0][0], cols = d.cols || [], T = d.tables || {}, L = d.live;
      const country = d.country || (CN[d.cc] || [""])[0], SS = L ? SL.season(cid, d) : null;   // item 10: the season first where 365 has one
      if (!SS){ const v5 = P5.league(Object.assign({}, d, { id:cid, names:N, country }), { team:tl, logo:logo365(cid), results:true, all:true, date:dstr }); v5.data = { id:cid };
        write(`db/league/${cid}/index.html`, page({ v5, path:`/db/league/${cid}/`, page:"league", title:`أبطال ${d.name} عبر التاريخ من ${first} | تيفو`, desc:`كل أبطال ${d.name}${country ? " في " + country : ""} من ${first} لين ${last}: ${won.length} موسم، والأكثر تتويجاً ${N[top[0][0]] || ""} بـ${mx} لقب.`, ld:bcLd([["الموسوعة", "/db/"], [`أبطال ${d.name}`, `/db/league/${cid}/`]]) }));
        urls.push(`/db/league/${cid}/`); nL++; return; }
      const body = (SS ? `<p class="crumbs"><a href="/db/">الموسوعة</a>${country ? "، " + esc(country) : ""}</p><h1>${esc(SS.h1)}</h1><p class="season">${SS.sub}</p><div class="sx">${SS.html}</div><h2 class="sxh">أبطال ${esc(d.name)} عبر التاريخ</h2>` +
        `<p>فاز بها <b class="num">${cnt.size}</b> ${cnt.size > 10 ? "فريق" : "فرق"} في <b class="num">${won.length}</b> موسم من <b class="num">${esc(first)}</b> لين <b class="num">${esc(last)}</b>، وأكثرهم ${esc(N[top[0][0]] || "")} بـ<b class="num">${mx}</b> ${mx > 10 ? "لقب" : "ألقاب"}.</p>`
        : `<p class="crumbs"><a href="/db/">الموسوعة</a></p><h1>أبطال ${esc(d.name)}</h1><p class="season">${[country && esc(country), d.name_en && `<span class="lat">${esc(d.name_en)}</span>`, `كل الأبطال من <b class="num">${esc(first)}</b> لين <b class="num">${esc(last)}</b>`].filter(Boolean).join(" · ")}</p>` +
        `<p>فاز بها <b class="num">${cnt.size}</b> ${cnt.size > 10 ? "فريق" : "فرق"} في <b class="num">${won.length}</b> موسم، وأكثرهم ${esc(N[top[0][0]] || "")} بـ<b class="num">${mx}</b> ${mx > 10 ? "لقب" : "ألقاب"}.</p>` +
        (L && (L.table || []).length ? `<section class="blk"><h2>الترتيب الحين</h2>${tbl(L.table, N)}</section>` : "") +
        (L && (L.results || []).length ? `<section class="blk"><h2>آخر النتايج</h2><ul class="mlist wgm">${L.results.slice(0, 20).map(g => grow(g, N)).join("")}</ul></section>` : "")) +
        `<section class="blk"><h2>الأكثر تتويجاً</h2><ul class="bars">${top.slice(0, 15).map(([t, n]) => `<li><span><a href="${tl(t)}">${esc(N[t] || "")}</a></span><i style="--w:${Math.round(n / mx * 100)}%"></i><b class="num">${n}</b></li>`).join("")}</ul></section>` +
        `<section class="blk"><h2>كل الأبطال <small>${won.length}</small></h2><div class="tscroll"><table class="tbl"><thead><tr><th>الموسم</th><th>البطل</th>${cols.map(x => `<th>${esc(x)}</th>`).join("")}</tr></thead><tbody>${CH.map(r => `<tr><td class="num">${esc(r[0])}</td><td>${r[1] ? `<a href="${tl(r[1])}">${esc(N[r[1]] || "")}</a>` : '<span class="muted">—</span>'}</td>${cols.map((x, i) => `<td class="num">${esc((r[2] || [])[i] == null ? "" : r[2][i])}</td>`).join("")}</tr>`).join("")}</tbody></table></div></section>` +
        (Object.keys(T).length ? `<section class="blk"><h2>الترتيب النهائي موسم بموسم</h2>${Object.keys(T).sort().reverse().map((s, i) => `<details${i ? "" : " open"}><summary class="num">${esc(s)}</summary>${tbl(T[s], N)}</details>`).join("")}</section>` : "") +
        `<p class="src">من 365Scores. آخر تحديث <span class="num">${esc(d.generated || "")}</span>.</p>`;
      write(`db/league/${cid}/index.html`, page({ path:`/db/league/${cid}/`, page:"league", title:SS ? SS.title : `أبطال ${d.name} عبر التاريخ من ${first} | تيفو`, desc:SS ? SS.desc : `كل أبطال ${d.name}${country ? " في " + country : ""} من ${first} لين ${last}: ${won.length} موسم، والأكثر تتويجاً ${N[top[0][0]] || ""} بـ${mx} لقب.`,
        ld:bcLd([["الموسوعة", "/db/"], [d.name, `/db/league/${cid}/`]]), body }));
      urls.push(`/db/league/${cid}/`); nL++; if (SS) nS++; });
    // the clubs of those leagues: /db/team/<id>/ (squad, next matches, results, titles)
    let nT = 0; for (const [id, t] of ST365){ const cm = ST365C[id], P = SL.team(t, cm);
      write(`db/team/${id}/index.html`, page({ path:`/db/team/${id}/`, title:P.title, desc:P.desc, ld:bcLd([["الموسوعة", "/db/"], cm && [cm.name, `/db/league/${cm.id}/`], [t.name, `/db/team/${id}/`]]),
        body:`<p class="crumbs"><a href="/db/">الموسوعة</a>${cm ? `، <a href="/db/league/${cm.id}/">${esc(cm.name)}</a>` : ""}</p><h1>${esc(P.h1)}</h1><p class="season">${P.sub}</p><div class="sx">${P.html}<p class="src">من 365Scores.</p></div>` }));
      urls.push(`/db/team/${id}/`); nT++; }
    console.log(`competition champion pages: ${nL} (${nS} lead with their live season), 365 club pages: ${nT}`); }
  for (const [k, t, d] of [["league", "بطولة", "أبطال البطولة من أول موسم، والجداول النهائية، ونتايج الموسم."], ["team", "فريق", "ألقاب الفريق في كل بطولة، ولاعبينه ومبارياته."],
    ["game", "مباراة", "التشكيلة والأهداف والكروت."], ["athlete", "لاعب", "مسيرة اللاعب موسم بموسم وألقابه وانتقالاته."]])
    write(`db/${k}/index.html`, page({ path:`/db/${k}/`, page:"world", noindex:true, title:`${t} | موسوعة تيفو`, desc:d, body:`<p class="crumbs"><a href="/db/">الموسوعة</a></p><h1 id="wt">نحمّل…</h1><div id="world" data-kind="${k}"></div>` }));
  // the journal (news/ in the pipeline): every outlet's story in one Arabic line. v5: the latest 30 prerendered (search engines and a
  // first paint), the browser keeps the list fresh from /v1/news/latest.json, the kinds are a segmented control
  { const nj = (await get("news/latest.json", 2)) || { stories:[] }, v5 = P5.news(nj); v5.data = {};
    write("news/index.html", page({ v5, path:"/news/", page:"news", title:"أخبار الكورة اليوم: الانتقالات والإصابات والتصريحات | تيفو", desc:"آخر أخبار الكورة من الصحف العربية والعالمية والقنوات الرسمية، بخلاصة عربية وكل خبر مربوط بناديه ولاعبيه، ومرحلة كل صفقة من الإشاعة للرسمي." })); urls.push("/news/"); }
  if (APPROVED.ask){ write("ask/index.html", page({ path:"/ask/", page:"ask", title:"اسأل تيفو: أي سؤال عن الكورة الإماراتية | تيفو", desc:"اسأل بالعامية عن الدوري الإماراتي والمنتخب: الترتيب، الهدافين، البطولات، المواجهات. الجواب من بيانات تيفو.",
    body:'<h1>اسأل تيفو</h1><p class="muted">اسأل بالعامية عن الدوري الإماراتي والمنتخب، والجواب من بيانات تيفو بس.</p><form id="askf" class="ask"><input id="askq" maxlength="200" placeholder="مثلاً: متى آخر مرة فاز الوصل على العين؟" aria-label="سؤالك"><button class="btn" type="submit">اسأل</button></form><div id="aska" role="status"></div><p class="src">الجواب يكتبه نموذج ذكاء اصطناعي من أرقام تيفو، وممكن يغلط. 25 سؤال باليوم لكل شخص.</p>' })); urls.push("/ask/"); }

  // stadium guide pages (8) + where-to-watch page (7)
  for (const [sid, x] of Object.entries(STAD)){
    const nm = (x.name_ar && x.name_ar.value) || (x.name_en && x.name_en.value) || sid;
    write(`s/${sid}/index.html`, page({ path:`/s/${sid}/`, page:"ref", title:`${nm}: الموقع والمواقف والتذاكر | تيفو`, desc:`دليل ${nm}: السعة والعنوان والخريطة والمواصلات ومنصة التذاكر، من المصادر الرسمية.`, body:`<p class="crumbs"><a href="/stadiums/">الملاعب</a></p><h1>${esc(nm)}</h1>` + S.stadium(x) }));
    urls.push(`/s/${sid}/`);
  }
  if (Object.keys(STAD).length){ write("stadiums/index.html", page({ path:"/stadiums/", page:"ref", title:"دليل ملاعب دوري أدنوك | تيفو", desc:"كل ملاعب دوري أدنوك للمحترفين: السعة والمواقع والمواصلات والتذاكر.", body:'<h1>دليل الملاعب</h1><div class="comps">' + Object.entries(STAD).map(([sid, x]) => `<a href="/s/${sid}/"><span>${esc((x.name_ar && x.name_ar.value) || sid)}</span><span class="muted small num">${x.capacity && x.capacity.value ? Number(x.capacity.value).toLocaleString("en-US") : ""}</span></a>`).join("") + "</div>" })); urls.push("/stadiums/"); }
  const wrows = comps.filter(c => BC[c.id] && BC[c.id].broadcasters && BC[c.id].broadcasters.length).map(c => S.sec(esc(c.name_ar), "", S.watchWhere(BC[c.id]))).join("");
  if (wrows){ write("watch/index.html", page({ path:"/watch/", page:"ref", title:"وين تنقل المباريات في الإمارات: القنوات والباقات والأسعار | تيفو", desc:"كل بطولة وين تنقل في الإمارات: أبوظبي الرياضية، دبي الرياضية، الشارقة الرياضية، beIN، STARZPLAY، شاهد وغيرها، مع الأسعار المنشورة.", body:'<h1>وين تنقل المباريات في الإمارات</h1><p class="muted">القنوات والتطبيقات لكل بطولة هالموسم، مع الأسعار المنشورة ومصدر كل معلومة. تحققنا منها في 27 سبتمبر 2026.</p>' + wrows + '<p><a class="btn" href="/commentators/">منو يعلّق على مباريات اليوم؟</a></p>' })); urls.push("/watch/"); }
  // «منو يعلّق؟»: the page is a shell; src/tv.js fills #tvall from v1/tv/<today>.json and <tomorrow>.json (news/commentators.py).
  // Owner item 3: under it every famous voice (src/voices.js over v1/tv/commentators.json, news/tvindex.py), and a page for each
  const VIX = (await get("tv/commentators.json", 1)) || { commentators:{}, matches:{} }, VK = Object.entries(VIX.commentators || {}).filter(([k, v]) => v && v.slug && v.name);
  write("commentators/index.html", page({ path:"/commentators/", page:"tvc", title:"معلقين مباريات اليوم وبكرة: منو يعلّق على أي مباراة | تيفو", desc:"منو يعلّق على مباريات اليوم وبكرة وعلى أي قناة: beIN SPORTS، الكأس، أبوظبي الرياضية، الشارقة الرياضية، شاهد، ثمانية وغيرها.", body:'<h1>منو يعلّق اليوم؟</h1><p class="muted">معلقين مباريات اليوم وبكرة والقناة اللي يعلّقون عليها، من جدول القنوات الناقلة والمعلقين اللي ينزل كل يوم بعد نص الليل. المواعيد بتوقيت بلدك.</p><div id="tvall"><p class="muted">نجهّز القائمة…</p></div>' + (VK.length ? VCM.list(VIX) : "") })); urls.push("/commentators/");
  for (const [k, v] of VK){ const p = `/commentators/${encodeURIComponent(v.slug)}/`, nx = (v.next || [])[0], nm = nx && (VIX.matches || {})[nx[0]];
    write(`commentators/${v.slug}/index.html`, page({ v5:{ nav:{ back:"/commentators/", backLabel:"المعلقين", title:esc(v.name), trail:U.navBtn("share", "شارك", ' data-sheet="sh-share"') }, body:VCM.page(VIX, k) + U.foot(), tab:"more", sheets:"", data:{} },
      path:p, page:"voice", title:`المعلق ${v.name}: مبارياته اليوم والياية والقنوات اللي يعلّق عليها | تيفو`,
      desc:`${v.name}: ${nm ? `مباراته الياية ${(nm.h || [])[1] || ""} ضد ${(nm.a || [])[1] || ""} على ${nx[1]}، و` : ""}آخر المباريات اللي علّق عليها والقنوات والبطولات، من جدول المعلقين اليومي.`,
      ld:bcLd([["المعلقين", "/commentators/"], [v.name, p]]) }));
    urls.push(p); }
  // «توقعاتي» (owner item 8): one personal page, filled in the browser by src/predict.js (the player, points, leagues, picks)
  write("predict/index.html", page({ v5:{ nav:{ back:"/more/", backLabel:"المزيد", title:"توقعاتي", trail:"" }, body:'<div class="lt"><h1>توقعاتي</h1><p>توقع النتيجة وتحدى ربعك في دوري خاص بينكم، بدون تسجيل.</p></div><div id="tp-page" data-predict-page><section class="grp"><div class="card"><p class="empty">نحمّل…</p></div></section></div>' + U.foot(), tab:"more", sheets:"", data:{} },
    path:"/predict/", page:"predict", noindex:true, title:"توقعاتي: توقع وتحدى ربعك | تيفو", desc:"توقع نتايج المباريات وتحدى ربعك في دوري خاص بينكم، بدون تسجيل." }));
  // «تيفو ريوايند» (owner bold idea 5): the season as stories, from what the visitor's device kept (src/trail.js, src/rewind.js)
  write("rewind/index.html", page({ v5:{ nav:{ back:"/more/", backLabel:"المزيد", title:"تيفو ريوايند", trail:"" }, body:'<div class="lt"><h1>تيفو ريوايند</h1><p>موسمك مع تيفو قصص تشاركها: المباريات اللي تابعتها، والأهداف اللي شفتها تدخل، وتوقعاتك، وفريقك. تتجمع على جوالك بس، بدون حساب.</p></div><div id="rw"><section class="grp"><div class="card"><p class="empty">نجمع قصتك…</p></div></section></div>' + U.foot(), tab:"more", sheets:"", data:{} },
    path:"/rewind/", page:"rewind", noindex:true, js:[ENG.rewind, ENG.badges], title:"تيفو ريوايند: موسمك مع تيفو | تيفو", desc:"موسمك مع تيفو قصص تشاركها: المباريات اللي تابعتها، والأهداف اللي شفتها، وتوقعاتك. محفوظة على جوالك بدون حساب." }));
  write("lite/index.html", LITE.page());
  // «أوسمة المشجع» (second list 9): quiet badges from what the fan's phone kept (src/badges.js)
  write("badges/index.html", page({ v5:{ nav:{ back:"/more/", backLabel:"المزيد", title:"أوسمتي", trail:"" }, body:'<div class="lt"><h1>أوسمتي</h1><p>أوسمة هادئة على اللي سوّيته في تيفو: المباريات اللي تابعتها، والأهداف اللي شفتها تدخل، وتوقعاتك، والمدرّج. محفوظة على جوالك بس.</p></div><div id="bdg"><section class="grp"><div class="card"><p class="empty">نحسب أوسمتك…</p></div></section></div>' + U.foot(), tab:"more", sheets:"", data:{} },
    path:"/badges/", page:"badges", noindex:true, js:[ENG.badges], title:"أوسمتي | تيفو", desc:"أوسمة هادئة على اللي سوّيته في تيفو، محفوظة على جوالك بدون حساب." }));   // «تيفو خفيف»: a 2G phone or one saving data lands here from any page (lib/lite.cjs)
  // «كشّاف تيفو» (owner bold idea 6): five young Arab players a scout (src/scout.js; the game is the Cards Lambda's)
  { const RU = SCOUT.RULES, rules = [["لعب", RU.played], ["لعب 60 دقيقة أو أكثر", "+" + RU.sixty + " زيادة"], ["سجّل هدف (الجزاء يحسب، العكسي لا)", RU.goal], ["صنع هدف", RU.assist], ["تقييمه 8 أو أكثر", RU.r8], ["تقييمه من 7", RU.r7], ["انطلب للمنتخب (حتى لو ما لعب)", RU.squad]];
    const body = '<div class="lt"><h1>كشّاف تيفو</h1><p>اختر خمس مواهب عربية شابة (' + RU.maxAge + ' سنة وأقل)، وكل ما لمعوا زادت نقاطك: أهداف، ودقايق، وتقييم، واستدعاء للمنتخب. وترتيب لأحسن الكشّافين طول الموسم.</p><p class="note" id="sc-when" hidden></p></div>' +
      '<div id="sc"><p class="note" id="sc-msg" role="status" hidden></p>' +
      '<section class="grp"><div class="gh"><h2>خمستك</h2></div><div id="sc-five"><div class="card"><p class="empty">نحمّل…</p></div></div></section>' +
      `<section class="grp"><div class="gh"><h2>المواهب</h2></div><div class="sf">${U.icon("search")}<input type="search" id="sc-q" placeholder="لاعب أو نادي" aria-label="دوّر لاعب" autocomplete="off"></div><div id="sc-cc" style="display:flex;gap:8px;overflow-x:auto;padding:0 0 12px;scrollbar-width:none"></div><div id="sc-pool"></div></section>` +
      '<section class="grp"><div class="gh"><h2>ترتيب الكشّافين</h2></div><div id="sc-board"></div></section>' +
      `<section class="grp"><div class="gh"><h2>كيف تنحسب النقاط</h2></div><div class="card lc"><p>في كل مباراة للاعب وهو في خمستك:</p><ul>${rules.map(r => `<li>${r[0]}: <b class="num">${typeof r[1] === "number" ? "+" + r[1] : r[1]}</b></li>`).join("")}</ul>` +
      '<p>النقاط تنحسب من لحظة ما تختار اللاعب (مباراة بدأت ما تنحسب) لين ما تشيله، واللي جمعه معك قبل ما تشيله يبقى لك. تقدر تشيل 3 لاعبين في الأسبوع، وتعبئة المكان الفاضي ما تحسب. الأرقام من ملفات مباريات تيفو نفسها، وتتحدّث كل ساعة.</p></div></section></div>' + U.foot();
    write("scout/index.html", page({ v5:{ nav:{ back:"/more/", backLabel:"المزيد", title:"كشّاف تيفو", trail:"" }, body, tab:"more", sheets:"", data:{ cc:Object.fromEntries(R.COUNTRIES.map(c => [c[0], c[1]])) } },
      path:"/scout/", page:"scout", noindex:true, js:[ENG.scout, ENG.badges], title:"كشّاف تيفو: اختر خمس مواهب عربية | تيفو", desc:"اختر خمس مواهب عربية شابة، ونقاطك تزيد كل ما لمعوا: أهداف ودقايق وتقييم واستدعاء للمنتخب. وترتيب لأحسن الكشّافين." })); }
  // «الكاميرا الذكية» (owner bold idea 13, experimental): the live numbers over the phone's camera (src/cam.js)
  write("cam/index.html", page({ v5:{ nav:{ back:"/", backLabel:"اليوم", title:"الكاميرا الذكية", trail:"" }, body:'<div class="lt"><h1>الكاميرا الذكية <small style="font-size:.5em;color:var(--label2)">تجريبية</small></h1><p>وجّه جوالك على التلفزيون، وأرقام المباراة المباشرة تطلع فوق الصورة. وصوّرها وشاركها.</p></div><div id="cam"><section class="grp"><div class="card"><p class="empty">نجهّز الكاميرا…</p></div></section></div>' + U.foot(), tab:"home", sheets:"", data:{} },
    path:"/cam/", page:"cam", noindex:true, js:[ENG.cam], title:"الكاميرا الذكية: أرقام المباراة فوق التلفزيون | تيفو", desc:"وجّه جوالك على التلفزيون، وأرقام المباراة المباشرة تطلع فوق الصورة." }));

  // ---- Arab-world pages (build_arabs.cjs): national teams, Arabs abroad, derbies, clashes, streaks, guide, archive…
  const AW = await require("./build_arabs.cjs")({ get, pool, write, page, urls, shelf, blocks, stub, NAT, coachAr, msum:id => matchSum.get(id), R, S, esc, index, teamsJson, teamPages, playerPages, matchPages:new Set(mids), NAMES_AR, fs, path, OUT, CACHE, H2H, BC });
  ED.push(["brk", "mow", "tonight", "streaks"].map(k => AW.home[k] || "").join("") + (AW.home.days || ""));
  writeHome();
  // W4.2: /match-of-week/ is a pinned card on /week/ now
  // 417: «تيفو الأسبوع» sits beside it, prerendered from weekly.py's cache/week/week-latest.json when there is one (the page script
  // draws it from /og/week-latest.json if a Thursday run lands between two builds, and draws nothing on a 404)
  { const f = path.join(OUT, "week/index.html"); if (fs.existsSync(f)){ const h = fs.readFileSync(f, "utf8"); let wk = null; try { wk = JSON.parse(fs.readFileSync(path.join(CACHE, "week", "week-latest.json"), "utf8")); } catch (e){}
      write("week/index.html", h.replace("<!--MOW-->", `<div class="wkpair" id="wkpair">${AW.mowWeek || ""}${wk ? R.weekCard(wk, { links:true }) : ""}</div>`)); } }
  // W4.3: /national/<cc>/'s content becomes the التاريخ tab of /t/<id>/ (ranks on top, every section a tile)
  // QA 12: a national team whose team file has no squad gets the latest call-up list (national/<id>/squad.json) in اللاعبين
  for (const [tid, sq] of Object.entries(AW.natSq || {})){ const f = path.join(OUT, "t", tid, "index.html"); if (!fs.existsSync(f)) continue; const h = fs.readFileSync(f, "utf8"); if (!h.includes("<!--NATSQ-->")) continue;
    write(`t/${tid}/index.html`, h.replace(/<!--NATSQ-->[\s\S]*?(?=<\/div>)/, `<p class="small muted">آخر قائمة استدعاها المدرب</p>${sq}`)); }
  for (const [tid, parts] of Object.entries(AW.natHist || {})){ const f = path.join(OUT, "t", tid, "index.html"); if (!fs.existsSync(f)) continue; const h = fs.readFileSync(f, "utf8"); if (!h.includes("<!--NATHIST-->")) continue;
    const bl = blocks(parts); bl.secs.forEach((s, i) => { s.id = s.id || "nh" + (i + 1); s.full = s.full.replace(/^<section class="blk"/, `<section class="blk" id="${s.id}"`); }); PALETTE = [colors[tid] || ["#5C6660", "#F6F7F2"]];
    write(`t/${tid}/index.html`, h.replace("<!--NATHIST-->", bl.rest + (bl.secs.length ? shelf(bl.secs, { title:"تاريخ المنتخب" }) : ""))); }

  // ---- search index (167): clubs, competitions, players, reference pages; loaded only when the visitor opens search
  // W3.11: every item carries a subline (the league, the club, the competition and time) and a country for tie-breaks
  // (3 × النصر, 3 × الأهلي); today's and the next 7 days' matches, coaches and referees are searchable too
  { const items = []; const seen = new Set(); const add = (t, id, ar, la, u, sub, cc, ko) => { const k = t + id; if (seen.has(k) || !(ar || la)) return; seen.add(k); const it = [t, ar || "", la || "", u, sub || "", cc || ""]; if (ko) it.push(ko); items.push(it); };
    const tLg = new Map(); compData.forEach(({ c, st }) => { if (c.kind !== "league" || !st || !st.groups) return; st.groups.forEach(g => (g.rows || []).forEach(r => { if (r.team && !tLg.has(r.team.id)) tLg.set(r.team.id, [c.name_ar, (c.country && c.country.iso2) || ""]); })); });
    const natIso = new Map(Object.entries(NAT || {}).map(([iso, id]) => [+id, iso]));
    const tSub = id => natIso.has(id) ? ["منتخب", natIso.get(id)] : tLg.get(id) || (() => { const sm = byTeam.get(id), m = sm && sm.ms[0]; return m ? [R.compName(index, m.comp) || "", ""] : ["", ""]; })();
    comps.forEach(c => add("c", c.id, c.name_ar, c.name_en, `/c/${c.key}/`, (c.country && c.country.name_ar) || "", (c.country && c.country.iso2) || ""));
    for (const id of teamIds){ const tj = teamsJson.teams[id] || {}; const sm = byTeam.get(id), s = tSub(id); add("t", id, tj.name_ar || (sm && sm.side.name_ar), tj.name || (sm && sm.side.name), `/t/${id}/`, s[0], s[1]); }
    { const mp = new Set(mids), t0 = Date.parse(today + "T00:00:00+04:00"), t1 = t0 + 8 * 864e5;
      for (const m of matchSum.values()){ const ko = Date.parse(m.kickoff_utc); if (!mp.has(m.id) || !(ko >= t0 && ko < t1) || !m.home || !m.away) continue; const s = tLg.get(m.home.id) || [];
        add("m", m.id, `${m.home.name_ar || m.home.name} ضد ${m.away.name_ar || m.away.name}`, `${m.home.name} vs ${m.away.name}`, `/m/${m.id}/`, R.compName(index, m.comp) || "", s[1] || "", m.kickoff_utc); } }
    for (const [cid, co] of coachRows){ if (!co.rows.length) continue; const ct = co.current && (teamsJson.teams[co.current] || {}).name_ar; if (!ct) continue;   // coaches in a job only: the index stays small
      add("k", cid, COACH_AR[cid] && COACH_AR[cid].ar || (co.name_en ? co.name : ""), co.name_en || co.name, `/coach/${cid}/`, ct ? "مدرب " + ct : "مدرب", ""); }
    for (const [rid, r] of refs) add("f", rid, refAr(r) || "", r.name, `/r/${rid}/`, "حكم · " + (r.comp.name_ar || ""), (r.comp.country && r.comp.country.iso2) || "");
    for (const [pid, p] of Object.entries(allPlayers)){ const tn = p.team && (teamsJson.teams[p.team] || {}).name_ar, s = p.team ? tSub(p.team) : ["", ""]; add("p", pid, (NAMES_AR[pid] || {}).ar || "", p.name_en || p.name, `/p/${pid}/`, tn || "", s[1]); }
    Object.keys(H2H).forEach(k => { const [a, bb] = k.split("-"), na = (teamsJson.teams[a] || {}).name_ar, nb = (teamsJson.teams[bb] || {}).name_ar; if (na && nb) add("r", "h2h-" + k, `${na} × ${nb}`, "", `/h2h/${k}/`, "كل المواجهات", ""); });   // QA 57
    legRaw.forEach(p => { const k = p.name_en || p.name; if (!k) return; add("r", "leg-" + k, p.name_ar || "", k, `/legends/#${String(k).toLowerCase().replace(/[^a-z]+/g, "-")}`, "من الأساطير", "AE"); });   // QA 56: every legend is searchable by name
    [["legends", "أساطير الكورة الإماراتية"], ["memorable", "مباريات ما تنتسى"], ["thisday", "هذا اليوم في كورة الإمارات"], ["laws", "قانون الكورة: التسلل، لمسة اليد، الفار"], ["watch", "وين تنقل المباريات"], ["stadiums", "دليل الملاعب"], ["week", "مباريات الأسبوع"], ["tv", "شاشة المجلس"], ["studio", "ستوديو التيفو"]].forEach(([k, n]) => add("r", k, n, "", `/${k}/`));
    AW.search.forEach(x => items.push(x.length > 4 ? x : x.concat(["", ""])));
    // W3.11: sublines go in one table ({s:[…], i:[[type, ar, latin, url, sub#, cc, kickoff?]]}); a latin equal to the Arabic is dropped
    const subs = [], si = new Map(); for (const it of items){ if (it[2] === it[1]) it[2] = ""; const s = it[4] || ""; if (!si.has(s)){ si.set(s, subs.length); subs.push(s); } it[4] = si.get(s); }
    const sj = JSON.stringify({ s:subs, i:items }); SEARCH_V = hash(sj); fs.writeFileSync(path.join(OUT, `assets/search.${SEARCH_V}.json`), sj);
    // 2026-10-07: the version lives in /search-v.json (max-age 60), not on every page: the index holds the next 8 days' matches, so it
    // moves with every kickoff change, and as `data-sv` on <body> it made half the hourly builds re-upload all 30k pages
    fs.writeFileSync(path.join(OUT, "search-v.json"), JSON.stringify({ v:SEARCH_V })); }

  // ---- 379: embeds for other sites (iframe): a league table and a live match, fetched from /v1, a link back to Tifo
  { const ehead = t => `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>${t}</title><link rel="icon" href="/favicon.svg" type="image/svg+xml"><style>@font-face{font-family:"Readex Pro";src:url(${FONTS.readex}) format("woff2");font-weight:400 600;font-display:swap}@font-face{font-family:"Barlow Condensed";src:url(${FONTS.barlow}) format("woff2");font-weight:700;font-display:swap}</style><style>:root{--ground:#0A2620;--text:#F6F7F2;--text-2:#B9C7C0;--text-3:#A7B6AF;--rule-2:#F6F7F214;--live-text:#5BE08F}body{margin:0;background:var(--ground);color:var(--text);font:400 14px "Readex Pro",system-ui,sans-serif}a{color:inherit;text-decoration:none}.w{padding:10px 12px}.h{display:flex;justify-content:space-between;align-items:center;font-weight:600;margin-bottom:6px}.h a{font-size:12px;color:var(--text-2)}table{width:100%;border-collapse:collapse}td,th{padding:6px 4px;border-bottom:1px solid var(--rule-2);text-align:center;font:700 15px "Barlow Condensed",sans-serif}th{font:400 11px "Readex Pro";color:var(--text-3)}td.t{text-align:start;font:400 14px "Readex Pro"}img{width:18px;height:18px;vertical-align:-4px;margin-inline-end:6px}.m{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:8px;text-align:center}.m img{width:44px;height:44px;display:block;margin:0 auto 6px}.s{font:700 44px "Barlow Condensed",sans-serif;display:flex;gap:8px;justify-content:center;align-items:center}.s i{font-style:normal}.s .ko{font:600 13px "Readex Pro",sans-serif;color:var(--text-2)}.st{font-size:12px;color:var(--text-2)}.live{color:var(--live-text)}</style></head><body><div class="w" id="w">…</div>`;
    const erun = js => `<script>(function(){var W=document.getElementById("w"),q=new URLSearchParams(location.search),E=function(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});},L=function(t){return '<img src="/logo/'+t.id+'.png" alt="" onerror="this.style.display=\\'none\\'">';},N=function(t){return E(t.name_ar||t.name);};${js}})();</script></body></html>`;
    fs.mkdirSync(path.join(OUT, "embed/t"), { recursive:true }); fs.mkdirSync(path.join(OUT, "embed/m"), { recursive:true });
    fs.writeFileSync(path.join(OUT, "embed/t/index.html"), ehead("الترتيب | تيفو") + erun(`var c=+q.get("c");Promise.all([fetch("/v1/comp/"+c+"/standings.json").then(function(r){return r.json();}),fetch("/v1/index.json").then(function(r){return r.json();})]).then(function(d){var st=d[0],cc=(d[1].competitions||[]).filter(function(x){return x.id===c;})[0]||{};W.innerHTML='<div class="h"><span>'+E(cc.name_ar)+'</span><a href="https://tifo.elyoxe.com/c/'+E(cc.key)+'/" target="_blank" rel="noopener">على تيفو</a></div>'+(st.groups||[]).map(function(g){return (g.name&&st.groups.length>1?'<p class="st">'+E(g.name)+'</p>':'')+'<table><tr><th>#</th><th style="text-align:start">الفريق</th><th>لعب</th><th>الفارق</th><th>نقاط</th></tr>'+g.rows.map(function(r){return '<tr><td>'+r.rank+'</td><td class="t">'+L(r.team)+N(r.team)+'</td><td>'+r.played+'</td><td><bdi dir="ltr">'+r.gd+'</bdi></td><td>'+r.pts+'</td></tr>';}).join("")+'</table>';}).join("");}).catch(function(){W.textContent="ما قدرنا نحمّل الترتيب.";});`));
    fs.writeFileSync(path.join(OUT, "embed/m/index.html"), ehead("المباراة | تيفو") + erun(`var id=q.get("id"),dd=q.get("d"),tz;try{tz=Intl.DateTimeFormat().resolvedOptions().timeZone}catch(e){}
function T(u){if(!u)return"";var d=new Date(u),o={timeZone:tz};return d.toLocaleDateString("ar-AE-u-nu-latn",Object.assign({day:"numeric",month:"long"},o))+" · "+d.toLocaleTimeString("ar-AE-u-nu-latn",Object.assign({hour:"2-digit",minute:"2-digit",hourCycle:"h23"},o));}
function draw(m){var live=m.status==="live"||m.status==="ht",sc=m.score&&m.status!=="scheduled"?'<b>'+E(m.score.home)+'</b><i>-</i><b>'+E(m.score.away)+'</b>':'<span class="ko">'+E(T(m.kickoff_utc))+'</span>';
W.innerHTML='<div class="h"><span>'+E(m.comp_name_ar||"")+'</span><a href="https://tifo.elyoxe.com/m/'+E(id)+'/" target="_blank" rel="noopener">على تيفو</a></div><div class="m"><div>'+L(m.home)+N(m.home)+'</div><div><div class="s'+(live?" live":"")+'">'+sc+'</div><div class="st'+(live?" live":"")+'">'+(live?(m.status==="ht"?"استراحة":E(String(m.minute||"").replace(/'/g,""))+"'"):m.status==="finished"?"انتهت":"")+'</div></div><div>'+L(m.away)+N(m.away)+'</div></div>';
var t=Date.parse(m.kickoff_utc);if(live)setTimeout(go,30000);else if(m.status==="scheduled"&&t-Date.now()<15*60e3&&t>Date.now()-4*36e5)setTimeout(go,60000);}
function day(){if(!dd)return Promise.reject();return fetch("/v1/day/"+dd+".json",{cache:"no-cache"}).then(function(r){if(!r.ok)throw 0;return r.json();}).then(function(j){var m=(j.matches||[]).filter(function(x){return String(x.id)===String(id);})[0];if(!m)throw 0;return m;});}
function go(){fetch("/v1/match/"+id+".json",{cache:"no-cache"}).then(function(r){if(!r.ok)throw 0;return r.json();}).catch(day).then(draw).catch(function(){W.innerHTML='<div class="h"><span>المباراة</span><a href="https://tifo.elyoxe.com/m/'+E(id)+'/" target="_blank" rel="noopener">على تيفو</a></div><p class="st">تفاصيل المباراة تنزل قبل البداية.</p>';});}go();`)); }

  // W1.2e: warn (never fail) about competitions playing in the next 72 h with no channel row for some Arab countries
  { const soon = new Set([...matchSum.values()].filter(m => m.status === "scheduled" && Date.parse(m.kickoff_utc) - Date.now() < 72 * 3600e3 && Date.parse(m.kickoff_utc) > Date.now()).map(m => String(m.comp)));
    const gaps = [...soon].map(cid => [cid, R.COUNTRIES.filter(c => !(BCBY[c[0]] && BCBY[c[0]][cid] && BCBY[c[0]][cid].b.length)).length]).filter(x => x[1]);
    if (gaps.length) console.error("warn: channels missing in the next 72h: " + gaps.map(g => `${g[0]} (${g[1]}/22 countries)`).join(", ")); }

  OGJ.push({ key:"match", home:"مباراة على تيفو", sub:"النتيجة مباشر، التشكيلة، الأحداث، ووين تنقل في بلدك", hc:["#0A2620", "#14403A"] });   // W4.5: the generic match card
  OGJ.push({ key:"tifo", home:"تيفو", sub:"نتايج المباريات مباشر لكل العرب، بتوقيت بلدك", hc:["#0A2620", "#123A31"] });   // W1.10: the default share image

  // ---- owner item 10 (2026-10-06): the encyclopedia's player pages /db/player/<id>/, a stage of their own (lib/world_stage.cjs): it writes only
  // the pages whose content changed into cache/world/delta/, which tools/runner.py uploads; never in out/, so neither rebuilt nor re-synced every hour.
  // Not in --preview (its noindex pages would be recorded as published).
  const WORLD = PREVIEW || process.env.TIFO_WORLD === "0" ? { urls:[], stats:{ skipped:true } } : await require("./lib/world_stage.cjs")({ get, pool, page, esc, SITE, CACHE, fs, path, bcLd,
    finalize:h => fixHtml(h).replace("__SV__", SEARCH_V).replace("__CV__", COLOR_V), written:u => WRITTEN.add(u), NAMES_AR, FMN, WP, PH, phHtml, colors, teamPages, playerPages, S_TEAMS, ASSET_V, fmGen:FMPJ.generated || "" });
  // their crawl path: /db/players/ (every nationality) and /db/players/<cc>/ (its players by club), small and in out/
  { const H = WORLD.hubs || {}, CN = FMN.countries || {}, ccs = Object.keys(H).filter(cc => CN[cc] && H[cc].length).sort((a, b) => H[b].length - H[a].length);
    const pl = n => n === 1 ? "لاعب واحد" : n === 2 ? "لاعبين" : `<span class="num">${n}</span> ${n <= 10 ? "لاعبين" : "لاعب"}`, AR = /[؀-ۿ]/;
    for (const cc of ccs){ const by = new Map(); H[cc].forEach(x => { const k = x[2] || 0; if (!by.has(k)) by.set(k, []); by.get(k).push(x); });
      const groups = [...by.values()].sort((a, b) => b.length - a.length || String(a[0][3]).localeCompare(String(b[0][3]), "ar")), c = CN[cc], p = `/db/players/${cc.toLowerCase()}/`;
      const body = `<p class="crumbs"><a href="/db/">الموسوعة</a>، <a href="/db/players/">اللاعبين حسب الجنسية</a></p><h1>لاعبو ${esc(c)} في أندية العالم</h1><p class="season">${pl(H[cc].length)} لعبوا موسم 2025/26 أو 2026/27</p><div class="sx">` +
        groups.map(g => `<section class="grp"><div class="gh"><h2>${g[0][2] ? (AR.test(g[0][3]) ? esc(g[0][3]) : `<span class="lat">${esc(g[0][3])}</span>`) : "بدون نادي"}</h2><span class="nn">${g.length}</span></div><div class="card">${g.sort((a, b) => String(a[1]).localeCompare(String(b[1]), "ar")).map(x => `<a class="row" href="/db/player/${x[0]}/"><span class="rt"><b>${AR.test(x[1]) ? esc(x[1]) : `<span class="lat">${esc(x[1])}</span>`}</b>${x[4] ? `<small>${esc(x[4])}</small>` : ""}</span></a>`).join("")}</div></section>`).join("") + "</div>";
      write(p.slice(1) + "index.html", page({ path:p, page:"ref", title:`لاعبو ${c} في أندية العالم: الأسماء والمسيرة | تيفو`, desc:`${H[cc].length} لاعب من ${c} لعبوا هالموسم أو اللي قبله في أندية العالم، ولكل واحد صفحة بمسيرته موسم بموسم وأرقامه وألقابه.`, ld:bcLd([["الموسوعة", "/db/"], ["اللاعبين حسب الجنسية", "/db/players/"], [c, p]]), body }));
      urls.push(p); }
    if (ccs.length){ write("db/players/index.html", page({ path:"/db/players/", page:"ref", title:"لاعبين كرة القدم حسب الجنسية: موسوعة تيفو | تيفو", desc:`${Object.values(H).reduce((a, l) => a + l.length, 0)} لاعب من ${ccs.length} دولة لعبوا موسم 2025/26 أو 2026/27، مرتبين حسب الجنسية والنادي.`, ld:bcLd([["الموسوعة", "/db/"], ["اللاعبين حسب الجنسية", "/db/players/"]]),
      body:`<p class="crumbs"><a href="/db/">الموسوعة</a></p><h1>اللاعبين حسب الجنسية</h1><p class="season">${ccs.length} دولة</p><div class="sx"><section class="grp"><div class="card">${ccs.map(cc => `<a class="row" href="/db/players/${cc.toLowerCase()}/"><span class="rt">${esc(CN[cc])}</span><span class="rv">${H[cc].length}</span></a>`).join("")}</div></section></div>` })); urls.push("/db/players/"); } }

  // ---- 8. competitions list, robots, sitemap, 404
  const groups = [["uae", "الإمارات"], ["gulf", "الخليج"], ["asia", "آسيا"], ["africa", "أفريقيا"], ["national", "المنتخبات"], ["arab", "العرب"], ["europe", "أوروبا"], ["americas", "الأمريكيتين"], ["world", "العالم"]];
  { const byC = {}; comps.forEach(c => { const cc = c.country && c.country.iso2; if (cc && R.COUNTRIES.some(x => x[0] === cc)) (byC[cc] = byC[cc] || []).push(c); });
    // v5 tab pages: البطولات (regions, the Arab countries' own pages, the encyclopedia; المنتخبات as the second segment), فريقي,
    // المزيد (settings and every other page, Settings style) and بحث. فريقي, المزيد and بحث are new URLs (no page had them before)
    const nats5 = ((NATJ && NATJ.teams) || []).map(t => ({ id:+t.team, name_ar:t.name_ar, name:t.name_en, sub:t.fifa && t.fifa.rank ? `تصنيف فيفا <span class="num">${t.fifa.rank}</span>` : "" })).filter(t => t.id).sort((a, b) => (a.id === 5789 ? -1 : b.id === 5789 ? 1 : 0));
    const ctry5 = R.COUNTRIES.filter(c => (byC[c[0]] || []).length || NAT[c[0]]).map(c => [c[0], c[1]]);
    { const v5 = P5.comps(index, nats5, { countries:ctry5 }); v5.data = {}; write("competitions/index.html", page({ v5, path:"/competitions/", page:"comps", nav:"comps", title:"كل البطولات | تيفو", desc:"كل البطولات اللي يغطيها تيفو: الإماراتية والخليجية والآسيوية والعربية والأوروبية." })); }
    { const pick = [], seen = new Set(), add = id => { id = +id; if (!id || seen.has(id)) return; const t = S_TEAMS[id]; if (!t || !(t.name_ar || TAR[id])) return; seen.add(id); pick.push({ id, name_ar:t.name_ar || TAR[id], name:t.name }); };
      add(5789); stIdsOf((compData.find(d => d.c.id === 538) || {}).st).forEach(add); R.COUNTRIES.forEach(c => { if (NAT[c[0]]) add(NAT[c[0]]); });
      [536, 519, 47, 87].forEach(cid => stIdsOf((compData.find(d => d.c.id === cid) || {}).st).slice(0, 4).forEach(add));
      const mine = P5.mine(pick.slice(0, 48)); mine.data = {}; write("mine/index.html", page({ v5:mine, path:"/mine/", page:"mine", noindex:true, title:"فريقي | تيفو", desc:"فرقك اللي تتابعها: مبارياتها ونتايجها وترتيبها، وتنبيه لكل هدف." }));
      const more = P5.more({ audit:AUDIT ? { at:AUDIT.generated, n:AUDIT.checked || 0 } : null, voices:VK.length ? VCM.picker(VIX) : "" }); more.data = {};
      { const rw = U.row({ href:"/rewind/", icon:"hist", c:"#FF9500", t:"تيفو ريوايند", sub:"موسمك قصص تشاركها، من جوالك وبدون حساب" }), n0 = more.body.length;   // bold idea 5, under «توقعاتي»
        more.body = more.body.replace(/(<a class="row ins" href="\/predict\/">[\s\S]*?<\/a>)/, "$1" + rw + U.row({ href:"/scout/", icon:"star", c:"#5856D6", t:"كشّاف تيفو", sub:"اختر خمس مواهب عربية، ونقاطك تزيد كل ما لمعوا" }) + U.row({ href:"/badges/", icon:"medal", c:"#FF9F0A", t:"أوسمتي", sub:"على اللي سوّيته في تيفو، من جوالك" }) + U.row({ href:"/lite/", icon:"phone", c:"#8E8E93", t:"تيفو خفيف", sub:"النتايج المباشرة بس، للنت الضعيف" })); if (more.body.length === n0) console.log("warn: the rewind row found no «توقعاتي» row on /more/"); } write("more/index.html", page({ v5:more, path:"/more/", page:"more", title:"كل صفحات تيفو والإعدادات | تيفو", desc:"كل أقسام تيفو في مكان واحد: المباريات، العرب، التاريخ، الأدوات، والإعدادات (بلدك، بدون حرق، صوت الهدف، تيفو على شاشة جوالك)." })); urls.push("/more/");
      const sr = P5.search([["الإمارات", "/t/5789/"], ["دوري أدنوك", "/c/uae-pro-league/"], ["كأس الخليج", "/c/gulf-cup/"], ["العين", "/t/102117/"], ["الوصل", "/t/102111/"], ["الهلال", "/t/2529/"], ["الأهلي المصري", "/t/101745/"], ["ميسي", "/p/30981/"], ["رونالدو", "/p/30893/"]]); sr.data = {};
      write("search/index.html", page({ v5:sr, path:"/search/", page:"search", noindex:true, title:"بحث | تيفو", desc:"دوّر على أي فريق أو لاعب أو بطولة أو مدرب في تيفو." })); }
    // 448: a page per Arab country at /country/<iso>/ (not /<iso>/: /tn/ is the thumbnails folder): the next 7 days of its
    // leagues and national team, the top of its main table, its scorers, the national team, its competitions and clubs.
    // Only what this build already holds; a country with neither a league nor a national team gets no page.
    for (const [iso, cname] of R.COUNTRIES){
      R.DUPCTX = cname;   // 503
      const cs = byC[iso] || [], nat = NAT[iso], lg = cs.find(c => c.kind === "league") || cs[0]; if (!cs.length && !nat) continue;
      const slug = iso.toLowerCase(), now = Date.now(), ids = new Set(cs.map(c => c.id)), isNat = m => nat && m.home && m.away && (m.home.id === nat || m.away.id === nat);
      const soon = [...matchSum.values()].filter(m => m && m.kickoff_utc && m.id != null && (ids.has(m.comp) || isNat(m)) && (R.isLive(m) || (Date.parse(m.kickoff_utc) > now - 3 * 36e5 && Date.parse(m.kickoff_utc) < now + 7 * 864e5))).sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc)).slice(0, 12);
      const d = (lg && compData.find(x => x.c.id === lg.id)) || {}, st = d.st, lst = d.stats;
      const top = st && !st.composite && st.groups && st.groups.length === 1 && st.groups[0].rows ? { groups:[Object.assign({}, st.groups[0], { rows:st.groups[0].rows.slice(0, 6) })] } : null;
      const natM = nat ? [...matchSum.values()].filter(isNat) : [], natNext = natM.filter(m => m.status === "scheduled" && Date.parse(m.kickoff_utc) > now).sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc))[0];
      const natLast = natM.filter(m => m.status === "finished").sort((a, b) => b.kickoff_utc.localeCompare(a.kickoff_utc)).slice(0, 3);
      const clubs = st && st.groups ? [...new Set(st.groups.flatMap(g => (g.rows || []).map(r => r.team.id)))] : [];
      const secL = [soon.length ? S.sec("الأيام الجاية", "", R.dayList(soon, index)) : "",
        top ? S.sec(`ترتيب ${esc(lg.name_ar)}`, "", R.standings(top) + `<p class="small"><a href="/c/${lg.key}/#table">الترتيب كامل</a></p>`) : "",
        lst && lst.lists && (lst.lists.goals || []).length >= 3 ? S.sec(`هدافين ${esc(lg.name_ar)}`, "", R.leaders(lst, "goals", 5) + `<p class="small"><a href="/c/${lg.key}/scorers/">كل الهدافين</a></p>`) : "",
        natNext || natLast.length ? S.sec(`منتخب ${esc(cname)}`, "", [natNext].concat(natLast).filter(Boolean).map(m => R.matchRow(m, { date:true, crest:true })).join("") + `<p class="small"><a href="/t/${nat}/">صفحة المنتخب</a></p>`) : "",
        cs.length ? S.sec("البطولات", "", `<div class="cts all">${cs.map(tileOf).join("")}</div>`) : "",
        clubs.length ? S.sec(`أندية ${esc(lg.name_ar)}`, "", `<ul class="facts-l">${clubs.map(id => `<li>${tlink(id)}</li>`).join("")}</ul>`) : ""].filter(Boolean);
      if (!secL.length) continue; const secs = secL.join(""), thinC = secL.length < 2;   // owner item 11: a one-section page stays for visitors, out of Google
      const what = [lg && lg.name_ar, nat && `منتخب ${cname}`].filter(Boolean);
      write(`country/${slug}/index.html`, page({ noindex:thinC, path:`/country/${slug}/`, page:"ref", nav:"comps", title:`مباريات ${what.join(" و")} اليوم | تيفو`, desc:`مواعيد مباريات ${what.join(" و")} بتوقيت بلدك${top ? "، وترتيب " + lg.name_ar + " والهدافين" : ""}${clubs.length ? "، وكل الأندية" : ""}.`,
        ld:bcLd([["البطولات", "/competitions/"], [cname, `/country/${slug}/`]]),
        body:`<p class="crumbs"><a href="/competitions/">البطولات</a></p><h1>الكورة في ${esc(cname)}</h1><p class="season">${what.map(esc).join(" · ")}</p>` + secs }));
      if (!thinC) urls.push(`/country/${slug}/`);
    }
    R.DUPCTX = ""; }
  // item 11: the staged cards after the hourly ones: the newest goals first, then every other match nearest its kick-off first
  SHG.sort((a, b) => b[0] - a[0]).forEach(x => OGJ.push(x[1])); SHJ.sort((a, b) => a[0] - b[0]).forEach(x => OGJ.push(x[1]));
  fs.mkdirSync(path.join(OUT, "og"), { recursive:true }); fs.writeFileSync(path.join(OUT, "og/jobs.json"), JSON.stringify(OGJ));
  if (!process.env.TIFO_NO_OG) try { process.stdout.write(require("child_process").execFileSync("python3", [path.join(__dirname, "og.py")], { maxBuffer:64 << 20 }).toString()); } catch (e){ console.error("og.py failed", e.message); }   // TIFO_NO_OG: dev builds skip the share images
  const SHST = PREVIEW ? null : SHARE.run({ CACHE, fs, path, stubs:STUBS });   // the cards og.py staged and the goal pages, for tools/runner.py to upload once
  // W1.9: internal links to pages this build did not write become plain text (reported, never fatal)
  if (!ONLY) { const SKIP = /^\/(v1|assets|logo|lg|og|audio|api|embed|next)\/|^\/(sw\.js|favicon\.svg|robots\.txt|sitemap\.xml)$|^\/cast\/(feed\.xml|cover\.jpg)$/; let dead = 0; const seen = {};
    for (const f of ALLP){ const h = fs.readFileSync(f, "utf8");
      const h2 = h.replace(/(<script\b[\s\S]*?<\/script>|<template\b[^>]*>)|<a\b([^>]*?)\shref="(\/[^"#?]*)(?:[?#][^"]*)?"([^>]*)>([\s\S]*?)<\/a>/g, (m, sc, pre, href, post, inner) => { if (sc) return m; if (SKIP.test(href) || WRITTEN.has(href) || WRITTEN.has(href.replace(/\/$/, ""))) return m;
        /* an Arabic path (/commentators/<slug>/) is linked percent-encoded */ const dh = (() => { try { return decodeURIComponent(href); } catch (e){ return href; } })(); if (dh !== href && (WRITTEN.has(dh) || WRITTEN.has(dh.replace(/\/$/, "")))) return m;
        dead++; seen[href.split("/")[1]] = (seen[href.split("/")[1]] || 0) + 1; return `<span${pre}${post}>${inner}</span>`; });
      if (h2 !== h) fs.writeFileSync(f, h2); }
    if (dead) console.error(`warn: ${dead} links to pages that don't exist were unlinked (${Object.entries(seen).map(([k, n]) => "/" + k + "/ " + n).join(", ")})`);
    if (LEAKS) console.error(`warn: ${LEAKS} text nodes with null/undefined/raw keys were cleaned`);
    if (GRPS) console.error(`warn: ${GRPS} text nodes with «المجموعة A» / «Grp» were rewritten to ordinals (fix the source)`); }
  for (const f of ALLP){ const h = fs.readFileSync(f, "utf8"); if (h.includes("__SV__")) fs.writeFileSync(f, h.replace("__SV__", SEARCH_V)); }
  fs.writeFileSync(path.join(OUT, "sw.json"), JSON.stringify({ off:false }));
  // W3.6: installable (manifest in Arabic/RTL, maskable mark, shortcuts) and an offline page listing what this phone has cached
  fs.mkdirSync(path.join(OUT, "icons"), { recursive:true }); for (const f of fs.readdirSync(path.join(__dirname, "icons"))) fs.copyFileSync(path.join(__dirname, "icons", f), path.join(OUT, "icons", f));
  // v5 PWA: installable in Arabic/RTL, the light system ground for the splash (the pages' theme-color follows the scheme), any and
  // maskable icons, shortcuts to اليوم · مباشر · فريقي; a launch from the home screen reuses an open window
  fs.writeFileSync(path.join(OUT, "manifest.webmanifest"), JSON.stringify({ id:"/", name:"تيفو — مباريات اليوم مباشر", short_name:"تيفو", description:"نتايج المباريات مباشر لكل العرب، بتوقيت بلدك.", lang:"ar", dir:"rtl", start_url:"/?s=pwa", scope:"/", display:"standalone", display_override:["standalone"], orientation:"portrait", background_color:"#F2F2F7", theme_color:"#F2F2F7", categories:["sports", "news"], launch_handler:{ client_mode:"navigate-existing" },
    icons:[{ src:"/icons/icon-192.png", sizes:"192x192", type:"image/png", purpose:"any" }, { src:"/icons/icon-512.png", sizes:"512x512", type:"image/png", purpose:"any" }, { src:"/icons/maskable-192.png", sizes:"192x192", type:"image/png", purpose:"maskable" }, { src:"/icons/maskable-512.png", sizes:"512x512", type:"image/png", purpose:"maskable" }],
    shortcuts:[{ name:"اليوم", url:"/?s=pwa", icons:[{ src:"/icons/icon-192.png", sizes:"192x192" }] }, { name:"مباشر الحين", url:"/?s=pwa&f=live", icons:[{ src:"/icons/icon-192.png", sizes:"192x192" }] }, { name:"فريقي", url:"/mine/?s=pwa", icons:[{ src:"/icons/icon-192.png", sizes:"192x192" }] }] }));
  // the offline page (the worker's fallback): your team's next match, last results and place from the copies this phone keeps
  // (/tn/<id>.json, the league table), then every page it has saved; the browser fills both (src/v5/app.js)
  write("offline/index.html", page({ v5:{ nav:{ brand:1, title:"ما في نت" }, tab:"", data:{}, body:'<div class="lt"><h1>ما في نت الحين</h1><p>هذا اللي محفوظ في جوالك من آخر مرة فتحت تيفو.</p></div><section class="grp" id="offmine" hidden></section>' + U.grp("الصفحات المحفوظة", '<div id="offl"><div class="row"><span class="rt muted">نشوف المحفوظ…</span></div></div>') + U.foot() }, path:"/offline/", page:"offline", noindex:true, title:"ما في نت | تيفو", desc:"" }));   // W1.11: the service worker's kill switch
  fs.writeFileSync(path.join(OUT, "sw.js"), fs.readFileSync(path.join(__dirname, "src/sw.js"), "utf8").replace("__V__", ASSET_V));
  fs.writeFileSync(path.join(OUT, "robots.txt"), PREVIEW ? "User-agent: *\nDisallow: /\n" : `User-agent: *\nDisallow: /next/\nAllow: /\nSitemap: ${SITE}/sitemap.xml\nSitemap: ${SITE}/sitemap-recent.xml\nSitemap: ${SITE}/sitemap-days.xml\nSitemap: ${SITE}/sitemap-players.xml\n`);
  // W4.6: the 404 offers search and today's matches instead of a dead end
  write("404.html", page({ v5:{ nav:{ back:"/", backLabel:"اليوم", title:"" }, tab:"", data:{}, body:'<div class="lt"><h1>الصفحة مب موجودة</h1><p>يمكن الرابط تغيّر. دوّر عن اللي تباه، أو شوف مباريات اليوم.</p></div>' + U.grp("", U.rows([{ href:"/search/", icon:"search", c:"#0A84FF", t:"دوّر في تيفو" }, { href:"/", icon:"today", c:"#34C759", t:"مباريات اليوم" }, { href:"/competitions/", icon:"comps", c:"#FF9500", t:"كل البطولات" }])) + '<div id="day404"></div>' + U.foot() }, path:"/404", page:"none", title:"الصفحة مب موجودة | تيفو", desc:"" }));
  // 425: site/static/* is copied to the out/ root unchanged (Search Console's google<token>.html lives there), keeping its mtime
  { const SD = path.join(__dirname, "static"); try { for (const f of fs.readdirSync(SD)){ if (f === "README" || f.startsWith(".")) continue; const src = path.join(SD, f); if (fs.statSync(src).isFile()) cpKeep(src, path.join(OUT, f)); } } catch (e){} }
  // 459: the owner's numbers at an unlisted address (noindex, never in the sitemap, the search index or IndexNow), rebuilt
  // with every build from the /api/tifo/hit counters (cards table, TIFOHIT#<UAE day>). XX = a time zone outside the Arab
  // countries (or none); crawlers are not counted since 2026-09-29 (shell.js). A failed query skips the page, never the build.
  if (!PREVIEW && !process.env.TIFO_NO_DASH && !ONLY) try {
    const DASH = "o-f6546fa79ce5872b", dayAt = i => new Date(Date.now() + 4 * 36e5 - i * 864e5).toISOString().slice(0, 10), days = [...Array(14)].map((_, i) => dayAt(i));
    const q = `SELECT pk, sk, n FROM cards WHERE pk IN [${days.map(d => `'TIFOHIT#${d}'`).join(",")}]`; let items = [], tok = null;
    do { const r = JSON.parse(require("child_process").execFileSync("aws", ["dynamodb", "execute-statement", "--region", "ap-south-1", "--statement", q, "--output", "json"].concat(tok ? ["--next-token", tok] : []), { env:Object.assign({}, process.env, { PYTHONWARNINGS:"ignore" }), timeout:60000 }).toString());
      items = items.concat(r.Items || []); tok = r.NextToken; } while (tok);
    const D = {}; for (const it of items){ (D[it.pk.S.slice(8)] = D[it.pk.S.slice(8)] || {})[it.sk.S] = +((it.n && it.n.N) || 0); }
    const sum = (ds, pre) => { const o = {}; ds.forEach(d => Object.entries(D[d] || {}).forEach(([k, n]) => { if (k.startsWith(pre)) o[k.slice(pre.length)] = (o[k.slice(pre.length)] || 0) + n; })); return Object.entries(o).sort((a, b) => b[1] - a[1]); };
    const nf = n => Number(n || 0).toLocaleString("en-US"), CN = Object.fromEntries(R.COUNTRIES.map(x => [x[0], x[1]])), w7 = days.slice(1, 8);
    const tbl = (head, rows) => `<div class="tblwrap"><table class="st"><thead><tr>${head.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
    const dayRows = days.map((d, i) => { const x = D[d] || {}; return `<tr><td>${i ? `<span class="num">${+d.slice(8)}</span> ${MON_AR[+d.slice(5, 7) - 1]}` : "اليوم (للحين)"}</td><td class="num">${nf(x.N)}</td><td class="num">${nf((x.N || 0) - (x["C#XX"] || 0))}</td><td class="num">${nf(x["C#AE"])}</td><td class="num">${nf(x["RET#first"])}</td><td class="num">${nf((x["RET#same_day"] || 0) + (x["RET#d1_7"] || 0) + (x["RET#d8p"] || 0))}</td></tr>`; });
    const fam = sum(w7, "P#").slice(0, 12).map(([k, n]) => `<tr><td class="lat">${esc(k)}</td><td class="num">${nf(n)}</td></tr>`), cc = sum(w7, "C#").slice(0, 10).map(([k, n]) => `<tr><td>${k === "XX" ? "بلد غير عربي أو ما عرفناه" : esc(CN[k] || k)}</td><td class="num">${nf(n)}</td></tr>`);
    write(`${DASH}/index.html`, page({ noindex:true, path:`/${DASH}/`, page:"none", title:"أرقام تيفو", desc:"",
      body:`<h1>أرقام تيفو</h1><p class="season">يتحدّث مع كل بناء، آخر مرة ${new Date(Date.now() + 4 * 36e5).toISOString().slice(11, 16)} بتوقيت الإمارات. الأرقام مشاهدات صفحات، مب أشخاص. من 29 سبتمبر ما تنحسب البوتات، والبلد من توقيت الجوال لو الزائر ما اختار بلده.</p>` +
        S.sec("آخر 14 يوم", "", tbl(["اليوم", "مشاهدات", "من بلد عربي", "الإمارات", "من زوار جدد", "من زوار رجعوا"], dayRows)) +
        S.sec("أكثر الصفحات", "آخر 7 أيام كاملة", tbl(["الصفحة", "مشاهدات"], fam)) + S.sec("البلدان", "آخر 7 أيام كاملة", tbl(["البلد", "مشاهدات"], cc)) }));
  } catch (e){ console.error("dash skipped:", String(e.message || e).split("\n")[0]); }
  fs.writeFileSync(path.join(OUT, ".pages"), String(urls.length));
  // W4.7: a file whose bytes match the last build keeps that build's mtime, so `aws s3 sync` (size + mtime) uploads only what changed
  if (!ONLY) { const MF = path.join(CACHE, "out_manifest.json"); let prev = {}; try { prev = JSON.parse(fs.readFileSync(MF, "utf8")); } catch (e){}
    const next = {}; let kept = 0, fresh = 0;
    (function walk(d){ for (const e of fs.readdirSync(d, { withFileTypes:true })){ const f = path.join(d, e.name); if (e.isDirectory()){ if (e.name !== "next") walk(f); continue; }
      const rel = path.relative(OUT, f), h = crypto.createHash("md5").update(fs.readFileSync(f)).digest("hex"), p = prev[rel];
      if (p && p[0] === h){ try { const t = new Date(p[1]); fs.utimesSync(f, t, t); next[rel] = p; kept++; } catch (x){ next[rel] = [h, Date.now()]; fresh++; } } else { next[rel] = [h, fs.statSync(f).mtimeMs]; fresh++; } } })(OUT);
    try { fs.writeFileSync(MF, JSON.stringify(next)); } catch (e){} console.log(`out: ${fresh} new or changed files, ${kept} unchanged (they keep their old mtime for s3 sync)`);
    // 446: lastmod is when the page's bytes last changed (the manifest above), never the build time
    const uniq = [...new Set(urls)], relOf = u => (decodeURI(u).replace(/^\//, "") + (u.endsWith("/") ? "index.html" : "")).split("/").join(path.sep), lm = u => { const e = next[relOf(u)]; return e ? new Date(e[1]).toISOString().slice(0, 10) : ""; };
    const sm = list => `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` + list.map(u => `<url><loc>${esc(SITE + encodeURI(decodeURI(u)))}</loc>${lm(u) ? `<lastmod>${lm(u)}</lastmod>` : ""}</url>`)   /* QA 99: encoded, no duplicates */.join("\n") + "\n</urlset>\n";
    fs.writeFileSync(path.join(OUT, "sitemap.xml"), sm(uniq));
    // 446: the pages Google should look at first: matches from 3 days back to 7 ahead, their competitions, today/tomorrow
    const now = Date.now(), recentM = [...matchSum.values()].filter(m => m && m.id != null && m.kickoff_utc && Math.abs(Date.parse(m.kickoff_utc) - now - 2 * 864e5) <= 5 * 864e5).map(m => `/m/${m.id}/`);
    const recentC = [...new Set([...matchSum.values()].filter(m => m && m.kickoff_utc && Math.abs(Date.parse(m.kickoff_utc) - now - 2 * 864e5) <= 5 * 864e5).map(m => m.comp))].map(id => (comps.find(c => c.id === id) || {}).key).filter(Boolean).map(k => `/c/${k}/`);
    const inSm = new Set(uniq); fs.writeFileSync(path.join(OUT, "sitemap-recent.xml"), sm(["/", "/today/", "/tomorrow/", "/yesterday/"].concat(recentC, recentM).filter((u, i, a) => inSm.has(u) && a.indexOf(u) === i)));
    // owner item 9: the day pages on their own short sitemap (the evergreen three, every dated day, the hub, «مباراة <فريق> اليوم»)
    fs.writeFileSync(path.join(OUT, "sitemap-days.xml"), sm(DAYS.urls.filter((u, i, a) => inSm.has(u) && a.indexOf(u) === i)));
    // owner item 10: the encyclopedia's player pages, each with the day its content last changed (lib/world_stage.cjs's manifest)
    fs.writeFileSync(path.join(OUT, "sitemap-players.xml"), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` + WORLD.urls.map(x => `<url><loc>${esc(SITE + x.u)}</loc>${x.lm ? `<lastmod>${x.lm}</lastmod>` : ""}</url>`).join("\n") + "\n</urlset>\n");
    // 445: pages whose bytes changed in this build, for deploy.sh to hand to IndexNow (Bing, Yandex…) after the sync
    fs.writeFileSync(path.join(CACHE, "indexnow.txt"), uniq.filter(u => { const e = next[relOf(u)], p = prev[relOf(u)]; return e && (!p || p[0] !== e[0]); }).concat(WORLD.fresh || []).map(u => SITE + encodeURI(decodeURI(u))).join("\n")); }
  console.log(`built ${urls.length} pages: ${comps.length} competitions, ${tcount} teams, ${pcount} players, ${mids.length} matches (${D.size} with detail), logos ${logoIds.size} (${dl} new) in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
})().catch(e => { console.error(e); process.exit(1); });
