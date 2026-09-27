/* Build تيفو — static pages prerendered from the /v1 data (docs/SCHEMA.md) with src/render.js, then hydrated by src/app.js.
   node build.cjs [--data https://…cloudfront.net] [--out out] [--preview]
   -> out/index.html, out/c/<key>/, out/m/<id>/, out/t/<id>/, out/uae/, out/competitions/, out/logo/<id>.png, sitemap.xml
   --preview adds noindex (the *.cloudfront.net preview must not be indexed). Logos are cached in cache/logo/ and self-hosted
   (never hotlinked: visitor requests would carry our referer to FotMob). */
"use strict";
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const R = require("./src/render.js"), S = require("./src/stats.js"); require("./src/v3.js");   // v3 layer (redesign/DESIGN-v3.md) patches R in place
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
// W1.7: visible text never shows null / undefined / [object Object] / raw pipeline keys; stripped and counted, never fatal
let GRPS = 0;   // Latin group letters that reached the page (fixed in write(), reported as a warning)
const LEAK = /\b(?:null|undefined|NaN)\b|\[object Object\]|\b(?:club|last_day|red_card)_[a-z0-9_]+\b/g; let LEAKS = 0;
const WRITTEN = new Set();   // W1.9: every page path written, for the post-build link check
function write(rel, html){ WRITTEN.add("/" + rel.replace(/index\.html$/, "").replace(/\.html$/, ""));
  // W2.10: «لـال» -> «لل», and ISO dates in visible text become Arabic dates
  html = html.replace(/(<body[\s\S]*)$/, b => b.replace(/(<script\b[\s\S]*?<\/script>)|>([^<>]*(?:لـ ?ال|\b20\d\d-\d\d-\d\d\b|\d\.0\b)[^<>]*)(?=<)/g, (m, sc, t) => sc ? m : ">" + t.replace(/(\d)\.0\b(?![.\d])/g, "$1").replace(/لـ ?ال/g, "لل").replace(/\b(20\d\d)-(\d\d)-(\d\d)\b/g, (_, y, mo, d) => `${+d} ${MON_AR[+mo - 1]} ${y}`)));
  html = html.replace(/(<body[\s\S]*)$/, b => b.replace(/(<script\b[\s\S]*?<\/script>)|>([^<>]*(?:المجموعة [A-J]\b|\bGrp\b)[^<>]*)(?=<)/g, (m, sc, t) => { if (sc) return m; GRPS++; return ">" + t.replace(/المجموعة ([A-J])\b/g, (_, l) => R.groupOrd(l)).replace(/\bGrp\.?\s*([A-J])\b/g, (_, l) => R.groupOrd(l)).replace(/\bGrp\.?/g, "المجموعة"); }));
  html = html.replace(/(<body[\s\S]*)$/, b => b.replace(/(<script\b[\s\S]*?<\/script>|<style\b[\s\S]*?<\/style>)|>([^<>]+)(?=<)/g, (m, sc, t) => { if (sc || !LEAK.test(t)) return m; LEAK.lastIndex = 0; LEAKS++; return ">" + t.replace(LEAK, "").replace(/\s{2,}/g, " "); }));
  const f = path.join(OUT, rel); fs.mkdirSync(path.dirname(f), { recursive:true }); fs.writeFileSync(f, COLOR_V ? html.replace("__CV__", COLOR_V) : html); if (!COLOR_V) EARLY.push(f); ALLP.push(f); }
const ALLP = [], OGJ = [];   // share-preview jobs for og.py (169)   // every page: the search index version is known only at the end, patched in then
const EARLY = [];   // pages written before the club colours were known: patched once COLOR_V exists
const hash = s => crypto.createHash("sha1").update(s).digest("hex").slice(0, 10);

const BUILT = new Date().toISOString(); let BCBY = {}; const FONTS = {};   // W1.1e: pages older than 2 min dim their live digits until the first good poll
let CC_V = "", ASSET_V = "", COLOR_V = "", SEARCH_V = "", BC_V = "";
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
// v3 shell (redesign/DESIGN-v3.md): top bar + 5-item nav (bottom tab bar on phones), one «شارك وأدوات» sheet, the «المزيد» sheet,
// the reader panel. v3 templates (o.v3) bring their own hero and .wrap; the others sit in a padded .wrap under the bar.
const IC = {
  today:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
  comps:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>',
  nat:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 21V4h11l-2 4 2 4H5"/></svg>',
  week:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 18h3V9H4zM10.5 18h3V5h-3zM17 18h3v-6h-3z"/></svg>',
  more:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="4" height="4"/><rect x="10" y="4" width="4" height="4"/><rect x="16" y="4" width="4" height="4"/><rect x="4" y="10" width="4" height="4"/><rect x="10" y="10" width="4" height="4"/><rect x="16" y="10" width="4" height="4"/></svg>',
  search:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/></svg>',
  share:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 8l5-5 5 5M5 13v8h14v-8"/></svg>',
};
const MON_AR = ["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"];
const POS_AR = { GK:"حارس مرمى", CB:"قلب دفاع", LB:"ظهير أيسر", RB:"ظهير أيمن", LWB:"ظهير أيسر", RWB:"ظهير أيمن", DM:"وسط دفاعي", CDM:"وسط دفاعي", CM:"وسط", LM:"وسط أيسر", RM:"وسط أيمن", AM:"وسط هجومي", CAM:"وسط هجومي", LW:"جناح أيسر", RW:"جناح أيمن", ST:"مهاجم", CF:"مهاجم", SS:"مهاجم ثاني", DF:"مدافع", MF:"وسط", FW:"مهاجم", GOALKEEPER:"حارس مرمى", DEFENDER:"مدافع", MIDFIELDER:"وسط", FORWARD:"مهاجم", ATTACKER:"مهاجم" };
const MARK = '<span class="mark" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span>';
// stages 4-6: a v2 body gets a compact key-art hero from its leading crumbs + h1 + season line, and its action rows
// (rows of buttons only) move into the page's single sheet. Link rows (pagers, "see also") stay in place.
const NOHERO = new Set(["tv", "w", "poster", "none"]), SHELF_PATH = /^\/(year|worldcup-arabs|calendars)\/$|^\/national\/[a-z]{2}\/$/;
function legacy(o){
  let body = o.body, hero = "", tools = o.tools || "";
  body = body.replace(/<p class="tools(?: noprint)?">((?:\s*<button\b[^>]*>[^<]*<\/button>)+)\s*<\/p>/g, (m, bs) => { tools += bs.replace(/class="btn"/g, 'class="sa"'); return ""; });
  const m = NOHERO.has(o.page) ? null : body.match(/^\s*(<p class="crumbs">[\s\S]*?<\/p>)?\s*(<h1\b[^>]*>[\s\S]*?<\/h1>)\s*(<p class="season">[\s\S]*?<\/p>)?/);
  if (m){
    const bands = JSON.stringify(o.art || [["#123A31", "#1B4A3F"], ["#0F3129", "#2A5A4E"]]);
    hero = `<section class="hero phero${o.lg ? " haslogo" : ""}" data-slot="hero" data-art='${esc(bands)}'${o.lg ? ` style="--g1:${o.lg[1]};--g2:${o.lg[2]}"` : ` style="--mos:url(${mosaicURI(o.art || [["#123A31", "#1B4A3F"], ["#0F3129", "#2A5A4E"]], 5)})"`}>${o.lg ? `<div class="lgart" aria-hidden="true"><i class="bloom"></i><img class="lglogo" src="/lg/${o.lg[0]}.png" alt="" width="192" height="192"></div>` : '<canvas aria-hidden="true"></canvas>'}<div class="scrim"></div><div class="hero-in wrap">${m[1] ? m[1].replace('class="crumbs"', 'class="hk"') : ""}${m[2]}${m[3] || ""}${o.heroExtra || ""}</div></section>`;
    body = body.slice(m[0].length);
  }
  // hub pages with many sections: the sections become shelf tiles (DESIGN-v3 rule 6), the rest stays inline
  if (SHELF_PATH.test(o.path || "")){ const b = blocks(body); if (b.secs.length >= 4){ SEQ = 0; body = b.rest + shelf(b.secs, { title:"كل الأقسام" }); } }
  return { main:hero + `<div class="wrap body${hero ? "" : " legacy"}">${body}</div>`, tools };
}
function page(o){
  if (!o.v3){ const l = legacy(o); o = Object.assign({}, o, { body:l.main, tools:l.tools, v3:true }); }
  const url = SITE + o.path, p0 = o.path || "", nk = /^\d+$/.test(o.nav || "") ? "comps" : o.nav === "uae" ? "nat" : o.nav || (p0 === "/" || /^\/(today|tomorrow|m)\//.test(p0) ? "home" : /^\/(competitions|c)\//.test(p0) ? "comps" : /^\/(national|uae)\//.test(p0) ? "nat" : /^\/week\//.test(p0) ? "week" : "");   // W1.9: the tab bar knows where it is
  const nav = [["home", "/", "اليوم", IC.today], ["comps", "/competitions/", "البطولات", IC.comps], ["nat", "/national/", "المنتخبات", IC.nat], ["week", "/week/", "الأسبوع", IC.week]];
  const navHtml = nav.map(n => `<a href="${n[1]}"${nk === n[0] ? ' aria-current="page"' : ""}>${n[3]}<span>${n[2]}</span></a>`).join("") + `<button type="button" data-sheet="more" aria-haspopup="dialog">${IC.more}<span>المزيد</span></button>`;
  const G = (t, items) => `<div class="mg"><h3>${t}</h3><div class="ml">${items.join("")}</div></div>`, L = (h, t) => `<a href="${h}">${t}</a>`;
  const sheets = `<div class="sheet" id="share" data-slot="sheet" role="dialog" aria-modal="true" aria-label="شارك وأدوات" hidden><div class="sh-in"><div class="sh-h"><h2>شارك وأدوات</h2><button type="button" class="x" data-close aria-label="سكّر">سكّر</button></div>
<div class="sh-g"><button type="button" class="sa" id="copylink">انسخ الرابط</button><button type="button" class="sa" id="nshare">شارك الصفحة</button>${o.tools || ""}<button type="button" class="sa" id="secpick">صورة لأي قسم</button></div><div id="secpicks" class="sh-list" hidden></div></div></div>
<div class="sheet" id="more" data-slot="more" role="dialog" aria-modal="true" aria-label="المزيد" hidden><div class="sh-in"><div class="sh-h"><h2>المزيد</h2><button type="button" class="x" data-close aria-label="سكّر">سكّر</button></div>
<div class="mset"><button type="button" class="spoil sa" id="ctry" title="بلدك: التوقيت وترتيب المباريات">بلدك</button><button type="button" class="spoil sa" id="spoil" aria-pressed="false" title="يخفي النتايج لين تضغط عليها">بدون حرق</button><button type="button" class="spoil sa" id="carbtn">وضع السيارة</button><button type="button" class="spoil sa" id="goalsnd" aria-pressed="false" title="صفارة قصيرة لما ينسجل هدف في المباراة اللي فاتحها">صوت الهدف</button><button type="button" class="spoil sa" data-sheet="inst" id="instm" hidden>تيفو على جوالك</button></div>
${G("اختصارات", [L("/c/uae-pro-league/", "دوري أدنوك"), L("/uae/", "المنتخب"), L("/c/gulf-cup/", "كأس الخليج"), L("/today/", "مباريات اليوم"), L("/tomorrow/", "مباريات بكرة"), L("/week/", "مباريات الأسبوع"), L("/countdowns/", "كم باقي؟")])}
${G("الشاشات", [L("/tv/", "شاشة المجلس"), L("/w/", "وضع المتابعة"), L("/watch/", "وين تنقل"), L("/stadiums/", "الملاعب")])}
${G("اقرا وتعلّم", [L("/legends/", "الأساطير"), L("/memorable/", "مباريات ما تنتسى"), L("/thisday/", "هذا اليوم"), L("/laws/", "قانون الكورة"), L("/academy/", "الأكاديمية"), L("/glossary/", "القاموس")])}
${G("سوّ بنفسك", [L("/studio/", "ستوديو التيفو"), L("/lab/", "المختبر"), L("/ask/", "اسأل تيفو"), L("/cast/", "تيفو كاست"), L("/newsletter/", "النشرة")])}</div></div>
<div class="sheet" id="inst" role="dialog" aria-modal="true" aria-label="تيفو على شاشة جوالك" hidden><div class="sh-in"><div class="sh-h"><h2>تيفو على شاشة جوالك</h2><button type="button" class="x" data-close aria-label="سكّر">سكّر</button></div>
<p class="inst-l">يفتح مثل التطبيق، بدون متجر وبدون حساب، والصفحات اللي فتحتها تشتغل حتى لو النت ضعيف في الملعب.</p><div class="sh-g"><button type="button" class="sa" id="instgo" hidden>ثبّت تيفو</button></div><p class="inst-ios" id="instios" hidden>في آيفون: اضغط <b>شارك</b> ← <b>أضف للشاشة الرئيسية</b></p><p class="nobet">تيفو بدون مراهنات.</p></div></div>
<div class="panel" id="panel" role="dialog" aria-modal="true" aria-labelledby="panelt" hidden><div class="pn-in"><div class="pn-h"><h2 id="panelt"></h2><span class="pn-sub" id="panels"></span><button type="button" class="x" data-close aria-label="سكّر">سكّر</button></div><div class="pn-b" id="panelb"></div></div></div>
<div class="scrimall" id="scrimall" hidden></div>`;
  const art = o.page !== "tv";
  const liveish = ["home", "match", "comp", "team", "daypage"].includes(o.page);
  return `<!doctype html><html lang="ar" dir="rtl"${liveish ? ` data-built="${BUILT}"` : ""}><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">${liveish ? '<script>(function(){var h=document.documentElement;if(Date.now()-Date.parse(h.dataset.built)>12e4)h.classList.add("stale")})()</script>' : ""}
<title>${esc(o.title)}</title><meta name="description" content="${esc(o.desc)}">${PREVIEW || o.noindex ? '<meta name="robots" content="noindex">' : `<link rel="canonical" href="${url}">`}
<meta property="og:title" content="${esc(o.title)}"><meta property="og:description" content="${esc(o.desc)}"><meta property="og:url" content="${url}"><meta property="og:locale" content="ar_AE">${(o = Object.assign({}, o, { og:o.og || "tifo" })).og ? `<meta property="og:image" content="${SITE}/og/${o.og}.png${o.ogv ? "?v=" + o.ogv : ""}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image">` : ""}<meta name="theme-color" content="#0A2620">
<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="manifest" href="/manifest.webmanifest"><link rel="apple-touch-icon" href="/icons/apple-touch-icon.png"><link rel="preload" href="${FONTS.kufi}" as="font" type="font/woff2" crossorigin><link rel="preload" href="${FONTS.readex}" as="font" type="font/woff2" crossorigin><link rel="preload" href="${FONTS.barlow}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/tifo.${ASSET_V}.css">${o.page === "match" ? '<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"}}</script>' : ""}${(o.ld ? [].concat(o.ld) : []).map(l => `<script type="application/ld+json">${JSON.stringify(l).replace(/</g, "\\u003c")}</script>`).join("")}</head>
<script type="speculationrules">{"prefetch":[{"source":"document","where":{"and":[{"href_matches":"/*"},{"not":{"href_matches":"/v1/*"}}]},"eagerness":"moderate"}]}</script>
<body class="v3" data-page="${o.page}" data-bc="${BC_V}"${o.page === "home" && CC_V ? ` data-cc="${CC_V}"` : ""}${o.attrs || ""}>
<a class="skip" href="#main">تخطَّ للمحتوى</a>
<header class="top" data-slot="nav"><div class="wrap"><a class="brand" href="/" aria-label="تيفو">${MARK}تيفو</a><nav class="pnav" aria-label="الأقسام">${navHtml}</nav><div class="acts"><button type="button" class="ib" id="srch" aria-label="بحث" data-v="__SV__">${IC.search}<span class="vh">بحث</span></button><button type="button" class="ib" data-sheet="share" aria-haspopup="dialog" aria-label="شارك">${IC.share}<span class="vh">شارك</span></button></div></div></header>
<main id="main">${o.v3 ? o.body : `<div class="wrap body legacy">${o.body}</div>`}</main>
<footer class="foot" data-slot="footer"><div class="wrap"><div class="fbrand">${MARK}<span>تيفو، من استوديو <a href="https://elyoxe.com/">Elyoxe</a>. المواعيد بتوقيت بلدك.</span></div><p class="nobet">تيفو بدون مراهنات.</p>
<div class="fcols">${[["مباريات", [["/", "اليوم"], ["/today/", "مباريات اليوم"], ["/tomorrow/", "مباريات بكرة"], ["/week/", "مباريات الأسبوع"], ["/countdowns/", "كم باقي؟"], ["/watch/", "وين تنقل"]]], ["بطولات", [["/competitions/", "كل البطولات"], ["/c/uae-pro-league/", "دوري أدنوك"], ["/national/", "المنتخبات"], ["/arabs/", "العرب"], ["/legends/", "الأساطير"], ["/memorable/", "مباريات ما تنتسى"], ["/thisday/", "هذا اليوم"]]], ["أدوات", [["/tv/", "شاشة المجلس"], ["/w/", "وضع المتابعة"], ["/studio/", "ستوديو التيفو"], ["/lab/", "المختبر"], ["/stadiums/", "الملاعب"]]], ["عن تيفو", [["/laws/", "قانون الكورة"], ["/academy/", "الأكاديمية"], ["/glossary/", "القاموس"], ["/cast/", "تيفو كاست"], ["/newsletter/", "النشرة"], ["https://elyoxe.com/", "Elyoxe"]]]].map(c => `<div><h3>${c[0]}</h3>${c[1].map(l => `<a href="${l[0]}">${l[1]}</a>`).join("")}</div>`).join("")}</div>
<p class="small muted"><span class="updated" id="updated"></span> البيانات من FotMob ورابطة المحترفين الإماراتية</p></div></footer>
<nav class="tabbar" aria-label="الأقسام" data-slot="nav">${navHtml}</nav>
${sheets}
${o.names ? `<script>window.PN=${JSON.stringify(o.names).replace(/</g, "\\u003c")}${o.pp ? ";window.PP=" + JSON.stringify(o.pp) : ""}</script>` : ""}<script src="/assets/colors.__CV__.js"></script><script src="/assets/render.${ASSET_V}.js"></script><script src="/assets/v3.${ASSET_V}.js"></script>${art ? `<script src="/assets/keyart.${ASSET_V}.js"></script>` : ""}${o.page === "compare" ? `<script src="/assets/compare.${ASSET_V}.js"></script>` : ""}${o.page !== "tv" ? `<script src="/assets/share.${ASSET_V}.js"></script>` : ""}${o.page === "lab" ? `<script src="/assets/lab.${ASSET_V}.js"></script>` : ""}<script src="/assets/app.${ASSET_V}.js"></script><script src="/assets/shell.${ASSET_V}.js"></script></body></html>`;
}
const tabsHtml = (group, list) => `<div class="tabs" role="tablist" data-tabs="${group}">` + list.map((t, i) => `<button type="button" role="tab" data-t="${t[0]}" aria-selected="${i === 0}">${t[1]}</button>`).join("") + "</div>";
const pane = (group, key, html, first) => `<section data-group="${group}" data-pane="${key}"${first ? "" : " hidden"}>${html}</section>`;

// ---- v3 building blocks (redesign/DESIGN-v3.md §3): sections -> shelf tiles that open the reader panel, lazily stamped
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
const LIVE_IDS = ["whatif", "rpbtn", "rpreds", "rpr", "rpev", "wwbox", "kitct", "bdays", "storydata", "commbtn"];   // app.js wires these once at start-up
const isLiveSec = h => LIVE_IDS.some(id => h.includes('id="' + id + '"'));
const stripT = h => h.replace(/<(script|style|template)[\s\S]*?<\/\1>/g, "").replace(/<[^>]+>/g, " ").replace(/&[a-z#0-9]+;/g, " ").replace(/\s+/g, " ").trim();
function teaser(sec){ const m = sec.inner.match(/<(li|p)\b[^>]*>([\s\S]*?)<\/\1>/); const t = m ? stripT(m[2]) : ""; if (!t || t.length < 8) return ""; return t.length > 90 ? t.slice(0, 88).replace(/\s\S*$/, "") + "…" : t; }
let PALETTE = [["#5C6660", "#F6F7F2"]];   // tile icons in club colours (never pulse/dune)
function tifoIcon(seed){ let s = 7; for (const ch of seed) s = (s * 31 + ch.charCodeAt(0)) % 2147483647; const rnd = () => { s = (s * 16807) % 2147483647; return s / 2147483647; };
  const a = PALETTE[Math.floor(rnd() * PALETTE.length)] || ["#5C6660"], b = PALETTE[Math.floor(rnd() * PALETTE.length)] || a;
  return '<span class="ti" aria-hidden="true">' + Array.from({ length:9 }, () => `<i style="background:${[a[0], a[1] || a[0], b[0]][Math.floor(rnd() * 3)]}"></i>`).join("") + "</span>"; }
let SEQ = 0;
function vault(key, sc){ const body = `<div class="pbody" data-title="${esc(sc.title)}">${sc.full}</div>`; return isLiveSec(sc.full) ? `<div class="vault" id="v-${key}" hidden>${body}</div>` : `<template id="v-${key}">${body}</template>`; }
function shelf(secs, o){
  o = o || {}; secs = secs.filter(sc => stripT(sc.inner).length > 2); if (!secs.length) return ""; const vs = [];   // W1.8: an empty section never becomes a tile
  const tiles = secs.map(sc => { const key = sc.id || "s" + (++SEQ); vs.push(vault(key, sc)); const tz = teaser(sc);
    return `<button type="button" class="sht" data-open="${key}"${sc.id ? ` data-anchor="${sc.id}"` : ""}>${tifoIcon(sc.title)}<span class="tt2">${esc(sc.title)}</span>${tz ? `<span class="tz">${esc(tz)}</span>` : sc.sub ? `<span class="tz">${sc.sub.replace(/<a[\s\S]*?<\/a>/g, "").replace(/<[^>]+>/g, "")}</span>` : ""}</button>`; });
  return `<div class="shelf-h"><h3>${o.title || "بعد في هالتبويب"}</h3><span class="muted small num">${secs.length}</span></div><div class="shelf3">${tiles.join("")}</div>${vs.join("")}`;
}
const tabsBar = (group, list) => `<div class="tabs mtabs" role="tablist" data-tabs="${group}" data-slot="tabs">` + list.map((t, i) => `<button type="button" role="tab" data-t="${t[0]}" aria-selected="${i === 0}">${t[1]}</button>`).join("") + "</div>";
const segBar = (group, list) => `<div class="tabs seg" role="tablist" data-tabs="${group}">` + list.map((t, i) => `<button type="button" role="tab" data-t="${t[0]}" aria-selected="${i === 0}">${t[1]}</button>`).join("") + "</div>";
// new pipeline files (2026-09-27): upsets, the Arab clubs rating, cup draws. Small renderers; each becomes a shelf tile
const tlink = id => `<a class="tl" href="/t/${id}/">${R.logo({ id }, "sm")}<span>${esc((S_TEAMS[id] || {}).name_ar || "")}</span></a>`;
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
const vpane = (group, key, html, first) => `<section data-group="${group}" data-pane="${key}" data-slot="tab:${key}"${first ? "" : " hidden"}>${html}</section>`;

(async () => {
  const t0 = Date.now();
  fs.rmSync(OUT, { recursive:true, force:true }); fs.mkdirSync(path.join(OUT, "assets"), { recursive:true });
  let css = fs.readFileSync(path.join(__dirname, "src/tifo.css"), "utf8"); const rjs = fs.readFileSync(path.join(__dirname, "src/render.js"), "utf8"), ajs = fs.readFileSync(path.join(__dirname, "src/app.js"), "utf8"), sjs = fs.readFileSync(path.join(__dirname, "src/stand.js"), "utf8"), cmp = fs.readFileSync(path.join(__dirname, "src/compare.js"), "utf8"), shr = fs.readFileSync(path.join(__dirname, "src/share.js"), "utf8"), p3d = fs.readFileSync(path.join(__dirname, "src/pitch3d.js"), "utf8"), labjs = fs.readFileSync(path.join(__dirname, "src/lab.js"), "utf8");
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
  ASSET_V = hash(css + rjs + ajs + sjs + cmp + shr + p3d + labjs + v3js + kajs + shjs); fs.writeFileSync(path.join(OUT, `assets/v3.${ASSET_V}.js`), v3js); fs.writeFileSync(path.join(OUT, `assets/keyart.${ASSET_V}.js`), kajs); fs.writeFileSync(path.join(OUT, `assets/shell.${ASSET_V}.js`), shjs); fs.writeFileSync(path.join(OUT, `assets/lab.${ASSET_V}.js`), labjs); fs.writeFileSync(path.join(OUT, `assets/pitch3d.${ASSET_V}.js`), p3d); fs.writeFileSync(path.join(OUT, `assets/compare.${ASSET_V}.js`), cmp); fs.writeFileSync(path.join(OUT, `assets/share.${ASSET_V}.js`), shr);   // content-hashed file names: CloudFront's cache key ignores query strings
  fs.writeFileSync(path.join(OUT, `assets/tifo.${ASSET_V}.css`), css); fs.writeFileSync(path.join(OUT, `assets/render.${ASSET_V}.js`), rjs); fs.writeFileSync(path.join(OUT, `assets/app.${ASSET_V}.js`), ajs); fs.writeFileSync(path.join(OUT, `assets/stand.${ASSET_V}.js`), sjs);
  // the mark: a 3x3 tifo of cards (chalk, pulse, dune on night pitch)
  const cellsSvg = [["#F6F7F2","#10A04B","#B07A3B"],["#F6F7F2","#B07A3B","#10A04B"],["#10A04B","#B07A3B","#F6F7F2"]].map((row, y) => row.map((c, x) => `<rect x="${4 + x * 8.5}" y="${4 + y * 8.5}" width="7" height="7" fill="${c}"/>`).join("")).join("");
  fs.writeFileSync(path.join(OUT, "favicon.svg"), `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="#0A2620"/>${cellsSvg}</svg>`);

  const index = await get("index.json"); if (!index) throw new Error("no index.json from " + DATA);
  const comps = index.competitions, today = new Date(Date.now() + 4 * 3600e3).toISOString().slice(0, 10);
  const urls = ["/", "/uae/", "/competitions/"], teamIds = new Set(), matchSum = new Map();
  const teamsJson = await get("teams.json"); S.setTeams(teamsJson && teamsJson.teams || {}); S_TEAMS = (teamsJson && teamsJson.teams) || {};

  // ---- 1. fetch: competitions (+ every analytics file the pipeline may have written), today, national
  const EXTRA = ["sim", "watch", "bump", "halftime", "xg", "clutch", "cards", "foreigners", "improved", "young-uae", "team-of-round", "minute-clock", "goal-bands", "referees", "lineup-ages", "rotation", "pressure", "style", "fortress", "records", "alltime", "facts", "players", "similar", "tournament-sim", "scenarios", "shots", "fatigue", "coaches", "transfers", "records-book", "seasons", "milestones", "upsets", "projections", "bracket-sim", "local-minutes", "suspensions", "first-goal", "dropped", "dependence", "xi", "signings", "absences", "alltime-table", "promoted", "late-goals", "champion-path", "games-in-hand"];
  // phase 5: generated content (ai/gen.py) is published only for kinds the owner approved (ai/approved.json)
  const APPROVED = JSON.parse(fs.readFileSync(path.join(__dirname, "ai/approved.json"), "utf8"));
  const AI = k => { const d = path.join(CACHE, "ai", k), o = {}; if (fs.existsSync(d)) for (const f of fs.readdirSync(d)) if (f.endsWith(".json")) o[f.slice(0, -5)] = JSON.parse(fs.readFileSync(path.join(d, f), "utf8")); return o; };
  const AIS = AI("summary"), AIP = AI("preview"), AIC = AI("podcast"), AID5 = AI("daily5"), AICM = AI("commentary"), AIDG = AI("digest"), AIPW = AI("power"), AIWHY = AI("why"), AIQK = AI("quick");
  const RSD = path.join(process.env.HOME, "workspace/research/tifo-2026-09-27"), readRes = f => { try { return JSON.parse(fs.readFileSync(path.join(RSD, f), "utf8")); } catch (e){ return {}; } };
  const CLUBS = {}; Object.values((readRes("arab_clubs.json").clubs) || {}).forEach(c => { if (c.fotmob_id) CLUBS[c.fotmob_id] = c; });
  const SUSR = {}; Object.values(readRes("suspension_rules.json")).forEach(v => { if (v && v.fotmob_id) SUSR[v.fotmob_id] = v; });
  const ACC = {}; Object.values((readRes("club_accounts.json").entities) || {}).forEach(v => { if (v.fotmob_id) ACC[v.fotmob_id] = v; });
  const ATS = {}; Object.values((readRes("alltime_scorers.json").leagues) || {}).forEach(l => { if (l.fotmob_league_id) ATS[l.fotmob_league_id] = l; });
  // 204: where to watch per visitor country, compacted for the client: {ISO:{comp:[[name_ar, free, price, currency, url]], ...}}
  { const bbc = readRes("broadcast_by_country.json"), out = {}; for (const [iso, v] of Object.entries(bbc)){ if (iso === "_meta" || !v.competitions) continue; out[iso] = { _c:v.currency || "" }; for (const [k, c] of Object.entries(v.competitions)){ const key = /^dom_/.test(k) ? String(v.own_league_key) : k; out[iso][key] = { b:(c.broadcasters || []).map(x => [x.name_ar || x.name_en, x.free ? 1 : 0, x.price, x.currency, x.url, x.package_ar || ""]), q:c.confidence || "" }; } }
    // W1.2a: the UAE rows fall back to broadcast.json (the verified UAE list) wherever the per-country file has none (e.g. the Gulf Cup)
    { const bu = readRes("broadcast.json"); out.AE = out.AE || { _c:"AED" }; for (const [cid, e] of Object.entries(bu)){ if (cid === "_meta" || !e || !(e.broadcasters || []).length || (out.AE[cid] && out.AE[cid].b.length)) continue; out.AE[cid] = { b:e.broadcasters.map(x => [x.name_ar || x.name_en, x.free ? 1 : 0, x.price_aed, "AED", x.url]), q:"broadcast.json" }; } }
    BCBY = out; const bj = JSON.stringify(out); BC_V = hash(bj); fs.writeFileSync(path.join(OUT, `assets/bc.${BC_V}.json`), bj); }
  let CLUB_AR = {}, REF_AR = {}; try { CLUB_AR = JSON.parse(fs.readFileSync(path.join(__dirname, "../names/clubs_ar.json"), "utf8")); } catch (e){} try { REF_AR = JSON.parse(fs.readFileSync(path.join(__dirname, "../names/referees_ar.json"), "utf8")); } catch (e){}
  const TAR = {}; for (const [id, v] of Object.entries(CLUB_AR)) if (v.ar) TAR[id] = v.ar; R.setClubNames(TAR);
  const refAr = r => r && r.id && REF_AR[r.id] && REF_AR[r.id].ar ? REF_AR[r.id].ar : null;
  const BC = readRes("broadcast.json"), HLT = readRes("highlights.json"), STAD = {}; ((readRes("stadiums.json").stadiums) || []).forEach(x => { STAD[x.id] = x; });
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
  const day = await get(`day/${today.replace(/-/g, "")}.json`) || { matches:[] };
  const arabRatings = await get("ratings/arab-clubs.json", 1);
  const [ratings, compare, fifa, qual, abroad, natRatings] = await Promise.all(["ratings/uae-clubs.json", "leagues/compare.json", "national/5789/fifa.json", "national/5789/qualifying.json", "national/uae-abroad.json", "ratings/national.json"].map(f => get(f, 1)));
  const h2hIdx = await get("h2h/index.json", 1), h2hKeys = h2hIdx ? Object.keys(h2hIdx.pairs) : [];
  const DERBIES = await get("derbies.json"); ((DERBIES && DERBIES.derbies) || []).forEach(d => { const k = String(d.h2h || "").replace(/^h2h\/|\.json$/g, ""); if (k && !h2hKeys.includes(k)) h2hKeys.push(k); });   // 209: the big Arab derbies get the same page
  const h2hData = await pool(h2hKeys, 8, k => get(`h2h/${k}.json`, 1)), H2H = {}; h2hKeys.forEach((k, i) => { if (h2hData[i]) H2H[k] = h2hData[i]; });
  let NAMES_AR = {}; try { NAMES_AR = JSON.parse(fs.readFileSync(path.join(__dirname, "../names/players_ar.json"), "utf8")); } catch (e){}
  // coaches (names/coaches_ar.json) and stadiums (stadiums.yaml fotmob_name/name_en + research stadiums.json) in Arabic; Latin stays the fallback
  let COACH_AR = {}; try { COACH_AR = JSON.parse(fs.readFileSync(path.join(__dirname, "../names/coaches_ar.json"), "utf8")); } catch (e){}
  const coachAr = co => co && co.id && COACH_AR[co.id] && COACH_AR[co.id].ar ? COACH_AR[co.id].ar : null;
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
  // a fixture that still says live/ht 3 h after kickoff is stale input: take a non-live copy from the fresher files, or say nothing live
  const unstale = m => { if (!m || !R.isLive(m) || !(Date.now() - Date.parse(m.kickoff_utc) > 3 * 3600e3)) return m; const s = matchSum.get(m.id); return s && s !== m && !R.isLive(s) ? Object.assign({}, m, { status:s.status, score:s.score, minute:null }) : Object.assign({}, m, { status:"unknown", minute:null }); };
  day.matches = (day.matches || []).map(unstale); compData.forEach(d => { if (d.fx && d.fx.matches) d.fx.matches = d.fx.matches.map(unstale); });

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
  // W2.11: 96 px webp crests for rows (logo_webp.py caches them in cache/logo96)
  try { require("child_process").execFileSync("python3", [path.join(__dirname, "logo_webp.py")], { stdio:"ignore", timeout:300000 }); fs.mkdirSync(path.join(OUT, "logo/96"), { recursive:true }); for (const f of fs.readdirSync(path.join(CACHE, "logo96"))) fs.copyFileSync(path.join(CACHE, "logo96", f), path.join(OUT, "logo/96", f)); } catch (e){ console.error("logo_webp.py failed; rows fall back to png"); }
  let colors = {}; try { colors = JSON.parse(fs.readFileSync(path.join(CACHE, "colors.json"), "utf8")); } catch (e){}
  R.setColors(colors); R.H2HK = {}; Object.keys(H2H).forEach(k => { R.H2HK[k] = 1; });
  const ARABC = new Set(R.COUNTRIES.map(c => c[0])), ARABT = {};
  compData.forEach(({ c, st, fx }) => { const iso = R.compCountry(c); if (!(ARABC.has(iso) || [329, 10242, 11156, 10474].includes(c.id))) return; (fx && fx.matches || []).forEach(m => { ARABT[m.home.id] = 1; ARABT[m.away.id] = 1; }); (st && st.groups || []).forEach(g => g.rows.forEach(r => { ARABT[r.team.id] = 1; })); });
  // W2.4 country engine: iso2 -> national team (arabs/national.json), iso2 -> top league, and the tournament being played now
  const NATJ = await get("arabs/national.json", 1), NAT = {}; ((NATJ && NATJ.teams) || []).forEach(t => { if (t.iso2 && t.team) NAT[t.iso2] = t.team; }); if (!NAT.AE) NAT.AE = 5789;
  // W3.4: the UAE's first channel per competition (the prerender); the client swaps in the visitor's country
  const CHN_AE = {}; for (const [cid, e] of Object.entries(BCBY.AE || {})) if (cid !== "_c" && e && e.b && e.b.length) CHN_AE[cid] = [e.b[0][0], e.b.some(x => x[1]) ? 1 : 0]; R.CHN = CHN_AE;
  // W2.7: clubs sharing an Arabic name carry their country
  const DUP = {}; { const by = {}; for (const [id, t] of Object.entries((teamsJson && teamsJson.teams) || {})) if (t.name_ar && !t.national) (by[t.name_ar] = by[t.name_ar] || []).push([id, t]); for (const list of Object.values(by)) if (list.length > 1 && new Set(list.map(x => (x[1].country || {}).iso2)).size > 1) list.forEach(([id, t]) => { if (t.country && t.country.name_ar) DUP[id] = t.country.name_ar; }); }
  R.setDup(DUP);
  const CL = {}; compData.forEach(({ c }) => { const iso = c.country && c.country.iso2; if (iso && c.kind === "league" && !CL[iso] && !c.dormant) CL[iso] = [c.key, c.name_ar]; });
  const NOWT = (() => { const now = Date.now(); for (const { c, fx } of compData){ if (c.kind === "league" || c.dormant) continue; if ((fx && fx.matches || []).some(m => Math.abs(Date.parse(m.kickoff_utc) - now) < 3 * 864e5)) return [c.key, c.name_ar]; } return null; })();
  const cjs = "window.TC=" + JSON.stringify(colors) + ";window.H2HK=" + JSON.stringify(R.H2HK) + ";window.ARABT=" + JSON.stringify(ARABT) + ";window.TAR=" + JSON.stringify(TAR) + ";window.NAT=" + JSON.stringify(NAT) + ";window.DUP=" + JSON.stringify(DUP) + ";window.CHN_AE=" + JSON.stringify(CHN_AE) + ";window.CL=" + JSON.stringify(CL) + ";window.NOWT=" + JSON.stringify(NOWT) + ";"; COLOR_V = hash(cjs); fs.writeFileSync(path.join(OUT, `assets/colors.${COLOR_V}.js`), cjs);

  const stIdsOf = st => st && !st.composite && st.groups && st.groups[0] ? st.groups[0].rows.map(r => r.team.id) : [];

  // competition logos (league_logos.py: FotMob league crests, dark variant preferred, cached in cache/leaguelogo) + their colours
  try { require("child_process").execFileSync("python3", [path.join(__dirname, "league_logos.py"), ...comps.map(c => String(c.id))], { stdio:"ignore", timeout:120000 }); } catch (e){ console.error("league_logos.py failed: mosaic fallback"); }
  let LCOL = {}; try { LCOL = JSON.parse(fs.readFileSync(path.join(CACHE, "league_colors.json"), "utf8")); } catch (e){}
  const LOGO = id => fs.existsSync(path.join(CACHE, "leaguelogo", id + ".png"));
  fs.mkdirSync(path.join(OUT, "lg"), { recursive:true }); comps.forEach(c => { if (LOGO(c.id)) fs.copyFileSync(path.join(CACHE, "leaguelogo", c.id + ".png"), path.join(OUT, "lg", c.id + ".png")); });
  const sat = h => { const n = parseInt(h.slice(1), 16), r = n >> 16, g = n >> 8 & 255, b = n & 255, mx = Math.max(r, g, b), mn = Math.min(r, g, b); return mx ? (mx - mn) / mx : 0; };
  const glow = id => { const cs = (LCOL[id] || []).slice().sort((a, b) => sat(b) - sat(a)); return [cs[0] && sat(cs[0]) > .25 ? cs[0] : "#F6F7F2", cs[1] && sat(cs[1]) > .25 ? cs[1] : (cs[0] && sat(cs[0]) > .25 ? cs[0] : "#5C7A70")]; };
  const scopeAr = { gulf:"الخليج", asia:"آسيا", europe:"أوروبا", arab:"العرب", africa:"أفريقيا", world:"العالم", national:"المنتخبات", uae:"الإمارات" };
  const tileOf = c => { const sub = esc((c.country && c.country.name_ar) || scopeAr[c.scope] || "");
    if (LOGO(c.id)){ const g = glow(c.id); return `<a class="ct lgt" data-iso="${(c.country && c.country.iso2) || ""}" href="/c/${c.key}/" style="--g1:${g[0]};--g2:${g[1]}"><span class="cl" aria-hidden="true"><img src="/lg/${c.id}.png" alt="" loading="lazy" width="96" height="96"></span><b>${esc(c.name_ar)}</b><small>${sub}</small></a>`; }
    const d = compData.find(x => x.c.id === c.id) || {}; let tids = stIdsOf(d.st); if (!tids.length && d.fx && d.fx.matches) tids = [...new Set(d.fx.matches.flatMap(m => [m.home.id, m.away.id]))];
    const cols = tids.slice(0, 12).map(id => (colors[id] || ["#123A31"])[0]); while (cols.length && cols.length < 12) cols.push(...cols.slice(0, 12 - cols.length));
    return `<a class="ct" data-iso="${(c.country && c.country.iso2) || ""}" href="/c/${c.key}/"><span class="cm" aria-hidden="true">${(cols.length ? cols : Array.from({ length:12 }, (_, i) => ["#1B4A3F", "#123A31", "#2A5A4E"][i % 3])).map(cl => `<i style="background:${cl}"></i>`).join("")}</span><b>${esc(c.name_ar)}</b><small>${sub}</small></a>`; };
  // Arabic player names (names/players_ar.json) on player-shaped nodes only (ids are player ids here, never clubs)
  const nameOf = id => (NAMES_AR[id] || {}).ar || null;
  { const pn = {}; for (const [k, v] of Object.entries(NAMES_AR)) if (v.ar) pn[k] = v.ar; for (const [k, v] of Object.entries(COACH_AR)) if (v.ar) pn[k] = v.ar; R.setNames(pn); }   // the prerender uses the same Arabic names as the client
  for (const [pid, p] of Object.entries(allPlayers)) if (nameOf(pid) && !p.name_en){ p.name_en = p.name; p.name = nameOf(pid); }
  compData.forEach(({ x, stats }) => { if (x.cards && x.cards.players) for (const [id, cc] of Object.entries(x.cards.players)) if (nameOf(id)) cc.name = nameOf(id);
    if (stats && stats.lists) for (const l of Object.values(stats.lists)) (l || []).forEach(r => { if (r.player && nameOf(r.player.id)) r.player.name = nameOf(r.player.id); }); });
  // ---- 3. competition pages
  const factsByMatch = {}, probsByMatch = {}, compX = {};
  for (const { c, st, fx, stats, x } of compData){
    compX[c.id] = x;
    if (x.facts && x.facts.matches) Object.assign(factsByMatch, x.facts.matches);
    let rounds = "";
    if (fx && fx.matches && fx.matches.length){ const rr = R.rounds(fx), cur = fx.next_round && rr.by[fx.next_round] ? fx.next_round : (rr.order.find(k => rr.by[k].some(m => m.status !== "finished")) || rr.order[rr.order.length - 1]); rounds = `<div class="chips">` + rr.order.map(k => `<button type="button" data-r="${esc(k)}"${k === cur ? ' aria-pressed="true"' : ""}>${esc(k)}</button>`).join("") + `</div><div id="roundlist">${R.roundList(rr.by[cur] || [])}</div>`; }
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
    const predSecs = blocks([clockHtml ? S.sec("ساعة الموسم", "", clockHtml) : "", roadHtml ? S.sec("الطريق للقب", "", roadHtml) : "", fdrHtml ? S.sec("صعوبة المباريات الياية", G("difficulty"), fdrHtml) : "", x.watch && fx ? S.sec("أحلى مباريات الجولة الياية", "", S.watch(x.watch, fx)) : "", S.whatif(fx, st) ? S.sec("شو لو؟", "", S.whatif(fx, st)) : "", x.sim && x.sim.teams ? S.sec("توقعات آخر الموسم", G("simulator"), S.sim(x.sim, st)) : "", st && st.magic ? S.sec("كم يحتاج فريقك؟", G("magic-number"), S.magic(st)) : "", x["tournament-sim"] ? S.sec("من بيفوز بالبطولة؟", "", S.tsim(x["tournament-sim"])) : "", projHtml ? S.sec("كم بيسجل الهدافين لآخر الموسم؟", "", projHtml) : "", st && st.bracket && st.bracket.length ? S.sec("شجرة البطولة", "", S.bracket(st, null)) : "", x.scenarios ? S.sec("حاسبة التأهل", "", S.groupCalc(x.scenarios)) : "", S.absences(x.absences) ? S.sec("غيابات الجولة" + (x.absences.round ? " " + esc(x.absences.round) : ""), "", S.absences(x.absences)) : "", S.gihFile(x["games-in-hand"]) ? S.sec("المباريات المؤجلة", G("games-in-hand"), S.gihFile(x["games-in-hand"])) : "", drawHtml(x.draws) ? S.sec("القرعة", "", drawHtml(x.draws)) : ""].join("")).secs;
    const leadP = predSecs.findIndex(sc => sc.title === "توقعات آخر الموسم"), predLead = leadP >= 0 ? predSecs.splice(leadP, 1)[0].full : "";
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
      ["upsets", "أكبر المفاجآت", upsetsHtml(x.upsets)], ["arabr", "ترتيبهم بين الأندية العربية", arabRankHtml(arabRatings, ids)],
      ["rating", "تصنيف تيفو للأندية", c.id === 538 ? S.ratingTable(ratings) : ""], ["world", "الدوري الإماراتي ضد العالم", c.id === 538 ? S.compare(compare, 538) : ""],
    ].filter(v => v[2]);
    const GL = { cards:"tifo-card", clutch:"clutch", pressure:"pressure-index", style:"ppda", rot:"rotation", fatigue:"fatigue", rating:"tifo-rating" };
    const numSecs = num.map(v => blocks(S.sec(v[1], GL[v[0]] ? G(GL[v[0]]) : "", v[2], "n-" + v[0])).secs[0]);
    const NA = { referees:"الحكام", "goal-bands":"توقيت الأهداف", shots:"التسديدات", xg:"الأهداف المتوقعة", "first-goal":"أول هدف" };
    const naNote = x._na && x._na.length ? `<p class="na">ما عندنا بيانات عن ${x._na.map(k => NA[k] || k).join("، ")} في هالبطولة.</p>` : "";
    // W3.12: «الأعلى تقييم» and «الحراس» join the scorers control, from comp/<id>/players.json (rating; clean sheets then saves)
    const PJ = x.players && x.players.players ? x.players : null, pMin = (PJ && PJ.min_minutes) || 270, pTeam = id => Object.assign({ id }, teamsJson.teams[id] || {});
    const pv = (p, k) => p.stats && p.stats[k] && p.stats[k].value;
    const ratedL = PJ ? Object.entries(PJ.players).filter(([, p]) => pv(p, "rating") && (p.minutes || 0) >= pMin).map(([id, p]) => ({ player:{ id:+id, name:p.name }, team:pTeam(p.team), value:+Number(pv(p, "rating")).toFixed(2), minutes:p.minutes })) : [];
    const keepL = PJ ? Object.entries(PJ.players).filter(([, p]) => pv(p, "saves") != null && (p.minutes || 0) >= pMin).map(([id, p]) => ({ player:{ id:+id, name:p.name }, team:pTeam(p.team), value:pv(p, "clean_sheet") || 0, saves:pv(p, "saves"), minutes:p.minutes })).sort((a, b) => b.value - a.value || b.saves - a.saves) : [];
    const leadSegs = [["goals", "الهدافين"], ["assists", "صناع الأهداف"]].concat(ratedL.length >= 3 ? [["rated", "الأعلى تقييم"]] : [], keepL.length >= 2 ? [["keepers", "الحراس"]] : []);
    const numLead = has.stats ? segBar("lead", leadSegs) + pane("lead", "goals", `<div id="goals">${R.leaders(stats, "goals")}</div>`, true) + pane("lead", "assists", `<div id="assists">${R.leaders(stats, "assists")}</div>`) +
      (ratedL.length >= 3 ? pane("lead", "rated", R.leaders({ lists:{ rated:ratedL } }, "rated") + `<p class="src">متوسط تقييم FotMob للاعبين اللي لعبوا ${pMin} دقيقة أو أكثر.</p>`) : "") +
      (keepL.length >= 2 ? pane("lead", "keepers", R.leaders({ lists:{ keepers:keepL } }, "keepers") + `<p class="src">الرقم = مباريات بشباك نظيفة، للحراس اللي لعبوا ${pMin} دقيقة أو أكثر.</p>`) : "") : "";
    const derb = c.id === 538 ? S.derbyList(h2hIdx, H2H) : "";
    const histSecs = blocks((x["champion-path"] ? (h => h ? S.sec("طريق البطل", "", h) : "")(S.championPath(x["champion-path"])) : "") + (ATS[c.id] ? S.sec("الهدافين التاريخيين", "", S.alltimeScorers(ATS[c.id])) : "") + (h => h ? S.sec("الجدول التاريخي", "من " + esc((x["alltime-table"] || {}).since || ""), h) : "")(S.alltimeTable(x["alltime-table"])) + (h => h ? S.sec("الدوري موسم بموسم", "", h) : "")(S.seasons(x.seasons, c.season)) + (h => h ? S.sec("الصاعدين هالموسم", "", h) : "")(S.promoted(x.promoted)) + (x.alltime ? S.sec("تاريخ الدوري", "من 1973", S.alltime(x.alltime)) : "") + (derb ? S.sec("سجل المواجهات بين الأندية", "", derb) : "") + (x.records && x.records.chases && x.records.chases.length ? S.sec("أرقام قياسية على المحك", "", S.records(x.records)) : "") + (x["records-book"] ? S.sec("كتاب الأرقام القياسية", "من " + esc(x["records-book"].since || ""), S.recordsBook(x["records-book"])) : "")).secs;
    const tl = [has.table && ["table", "الترتيب"], ["fixtures", "المباريات"], (numLead || numSecs.length) && ["num", "الأرقام"], (predLead || predSecs.length) && ["pred", "التوقعات"], histSecs.length && ["hist", "التاريخ"]].filter(Boolean);
    const lead = has.table && !st.composite && st.groups.length === 1 ? st.groups[0].rows[0] : null;
    const upcoming = (fx && fx.matches || []).filter(m => m.status === "scheduled" && m.kickoff_utc).sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc))[0];
    const fin = (fx && fx.matches || []).filter(m => m.status === "finished").length, tot = (fx && fx.matches || []).length;
    const ORD = ["الأولى", "الثانية", "الثالثة", "الرابعة", "الخامسة", "السادسة", "السابعة", "الثامنة"];
    const gLead = has.table && st.groups.length > 1 ? st.groups.slice(0, 4).map((gr, gi) => { const r0 = gr.rows && gr.rows[0]; return r0 ? `<div><dt>متصدر المجموعة ${ORD[gi] || gi + 1}</dt><dd><a href="/t/${r0.team.id}/">${R.logo(r0.team, "sm")} ${R.tname(r0.team)}</a> <b class="num">${r0.pts}</b></dd></div>` : ""; }).join("") : "";
    const heroFacts = [gLead, lead ? `<div><dt>المتصدر</dt><dd><a href="/t/${lead.team.id}/">${R.logo(lead.team, "sm")} ${R.tname(lead.team)}</a> <b class="num">${lead.pts}</b> <small>نقطة</small></dd></div>` : "",
      upcoming ? `<div><dt>الجولة الياية</dt><dd><b class="num">${esc(upcoming.round || "")}</b> ${R.td(upcoming.kickoff_uae, true)}</dd></div>` : "",
      tot ? `<div><dt>الموسم</dt><dd><b class="num">${fin}</b> <small>من</small> <b class="num">${tot}</b> <small>مباراة</small></dd><i class="prog" style="--p:${(fin / tot * 100).toFixed(1)}%"></i></div>` : ""].join("");
    const g = glow(c.id), hasLogo = LOGO(c.id), artBands = JSON.stringify((ids.length ? ids : [...new Set(((st && st.groups) || []).flatMap(g => (g.rows || []).map(r => r.team.id)).concat((fx && fx.matches || []).flatMap(m => [m.home.id, m.away.id])))].slice(0, 16)).map(id => colors[id] || ["#5C6660", "#F6F7F2"]));   // W1.8: cups take their group / fixture teams
    const art = hasLogo ? `<div class="lgart" aria-hidden="true"><i class="bloom"></i><i class="bloom b2"></i><img class="lglogo" src="/lg/${c.id}.png" alt="" width="192" height="192" fetchpriority="high"></div>` : `<canvas aria-hidden="true"></canvas>`;
    const tools = `${nextR.length ? `<button type="button" class="sa" id="rpbtn">صورة توقعات الجولة ${esc(nextR[0].r)}</button>` : ""}${x.cards ? `<a class="sa" href="/c/${c.key}/compare/">قارن بين لاعبين أو فريقين</a>` : ""}${powK ? `<a class="sa" href="/c/${c.key}/power/">ترتيب القوة هالأسبوع</a>` : ""}${has.table ? `<button type="button" class="sa" id="embedbtn" data-src="/embed/t/?c=${c.id}" data-h="560">ضمّن الترتيب في موقعك</button>` : ""}`;
    const body = `<section class="hero chero${hasLogo ? " haslogo" : ""}" data-slot="hero" data-art='${esc(artBands)}' style="--g1:${g[0]};--g2:${g[1]}${hasLogo ? "" : `;--mos:url(${mosaicURI(JSON.parse(artBands), 11)})`}">${art}<div class="scrim"></div><div class="hero-in wrap">
<p class="hk"><a href="/competitions/">البطولات</a>${c.country ? `، ${esc(c.country.name_ar)}` : ""}</p><h1>${esc(c.name_ar)}</h1><p class="season">الموسم <span class="num">${esc(c.season || "")}</span></p>${c.dormant ? '<p class="note">البطولة متوقفة أو خلصت هالموسم. هذي آخر نتايجها.</p>' : ""}
<dl class="hfacts">${heroFacts}</dl><div class="hero-acts"><a class="cta" href="#fixtures" data-go="fixtures">${upcoming ? "مباريات الجولة" : "المباريات"}</a><button type="button" class="ghost" data-sheet="share">شارك</button></div></div></section>
${nextR.length ? `<script type="application/json" id="rpreds">${JSON.stringify(nextR).replace(/</g, "\\u003c")}</script>` : ""}<div class="wrap body">` + tabsBar("c", tl) +
      (has.table ? vpane("c", "table", tableLead + tableShelf, true) : "") + vpane("c", "fixtures", `<div id="rounds">${rounds || '<p class="empty">ما في مباريات منشورة.</p>'}</div>`, !has.table) +
      ((numLead || numSecs.length) ? vpane("c", "num", numLead + shelf(numSecs, { title:"الأرقام كلها" }) + naNote) : "") + ((predLead || predSecs.length) ? vpane("c", "pred", predLead + shelf(predSecs, { title:"بعد في التوقعات" })) : "") + (histSecs.length ? vpane("c", "hist", shelf(histSecs, { title:"التاريخ والأرقام القياسية" })) : "") + "</div>";
    const names = {}; if (stats && stats.lists) Object.values(stats.lists).forEach(l => (l || []).forEach(r => { if (r.player && nameOf(r.player.id)) names[r.player.id] = nameOf(r.player.id); }));
    OGJ.push({ key:"c-" + c.id, home:c.name_ar, sub:"الترتيب والمباريات والتوقعات", hc:["#123A31", "#1B6F5A"] });
    write(`c/${c.key}/index.html`, page({ v3:true, og:"c-" + c.id, path:`/c/${c.key}/`, page:"comp", attrs:` data-comp="${c.id}"`, nav:"comps", tools, names, title:`${c.name_ar}: الترتيب والمباريات والتوقعات ${c.season || ""} | تيفو`, desc:`ترتيب ${c.name_ar} ومواعيد المباريات بتوقيت بلدك والنتايج المباشرة، وتوقعات آخر الموسم، والهدافين وبطاقات اللاعبين والأرقام.`, body }));
    urls.push(`/c/${c.key}/`);
    if (powK){ const pw = AIPW[powK]; write(`c/${c.key}/power/index.html`, page({ path:`/c/${c.key}/power/`, page:"ref", nav:String(c.id), title:`ترتيب القوة في ${c.name_ar} هالأسبوع | تيفو`, desc:`ترتيب أندية ${c.name_ar} حسب تصنيف تيفو هالأسبوع، مع سطر عن كل نادي من أرقامه.`,
      body:`<p class="crumbs"><a href="/c/${c.key}/">${esc(c.name_ar)}</a></p><h1>ترتيب القوة</h1><p class="season">الأسبوع <span class="num">${esc(pw.week || "")}</span></p>` + S.aiPower(pw) })); urls.push(`/c/${c.key}/power/`); }
    if (x.cards){
      write(`c/${c.key}/compare/index.html`, page({ names:Object.fromEntries(Object.keys(x.cards.players || {}).filter(pid => nameOf(pid)).map(pid => [pid, nameOf(pid)])), path:`/c/${c.key}/compare/`, page:"compare", attrs:` data-comp="${c.id}"`, nav:String(c.id), title:`قارن بين لاعبين أو فريقين في ${c.name_ar} | تيفو`, desc:`قارن أي لاعبين في ${c.name_ar} على رادار واحد وأرقامهم في كل 90 دقيقة، أو قارن بين فريقين.`,
        body:`<p class="crumbs"><a href="/c/${c.key}/">${esc(c.name_ar)}</a></p><h1>قارن</h1>` + tabsHtml("k", [["players", "لاعبين"], ["clubs", "فريقين"]]) + pane("k", "players", `<div class="cmpsel"><select id="pa" aria-label="اللاعب الأول"></select><select id="pb" aria-label="اللاعب الثاني"></select></div><div id="pout"><p class="empty skel">نحمّل الأرقام…</p></div>`, true) + pane("k", "clubs", `<div class="cmpsel"><select id="ta" aria-label="الفريق الأول"></select><select id="tb" aria-label="الفريق الثاني"></select></div><div id="tout"></div>`) }));
      urls.push(`/c/${c.key}/compare/`);
    }
  }
  // derby / head-to-head pages (38)
  const DZ = {}; ((DERBIES && DERBIES.derbies) || []).forEach(d => { DZ[String(d.h2h || "").replace(/^h2h\/|\.json$/g, "")] = d.name_ar; });
  for (const [k, h] of Object.entries(H2H)){
    const [a, b] = k.split("-"), na = (teamsJson.teams[a] || {}).name_ar || a, nb = (teamsJson.teams[b] || {}).name_ar || b;
    write(`h2h/${k}/index.html`, page({ art:[colors[a] || ["#5C6660"], colors[b] || ["#3D4A44"]], path:`/h2h/${k}/`, page:"h2h", title:`${na} و${nb}: كل المواجهات | تيفو`, desc:`سجل مواجهات ${na} و${nb}: كم فاز كل فريق وكم تعادلوا، وكل النتايج.`, body:`<p class="crumbs">${DZ[k] ? '<a href="/derbies/">الديربيات العربية</a>' : '<a href="/c/uae-pro-league/#hist">تاريخ الدوري</a>'}</p><h1>${DZ[k] ? esc(DZ[k]) : esc(na) + " و" + esc(nb)}</h1>` + S.h2hPage(h) }));
    urls.push(`/h2h/${k}/`);
  }

  // ---- 4. home (v3 fixed slots, DESIGN-v3.md §3.2): written last, once every editorial block (ED) is known
  const w538 = compX[538] && compX[538].watch, fx538 = compData.find(d => d.c.id === 538);
  const ED = []; if (arabRatings && arabRatings.teams && arabRatings.teams.length) ED.push(S.sec("أقوى الأندية العربية", '<a href="/arabs/">عالم العرب</a>', arabRankHtml(arabRatings, arabRatings.teams.slice(0, 20).map(t => t.team))));
  if (w538 && fx538) ED.push(S.sec("أحلى مباريات الجولة الياية في دوري أدنوك", "", S.watch(w538, fx538.fx)));
  const writeHome = () => {
    SEQ = 0; PALETTE = Object.values(colors).slice(0, 60);
    { const cc = {}; compData.forEach(({ c, st }) => { const iso = c.country && c.country.iso2; if (!iso || c.kind !== "league" || cc[iso]) return; const ids = stIdsOf(st); if (ids.length) cc[iso] = ids.slice(0, 20).map(id => [id, (teamsJson.teams[id] || {}).name_ar || TAR[id] || (teamsJson.teams[id] || {}).name || ""]); });
      const cj = JSON.stringify(cc); CC_V = hash(cj); fs.writeFileSync(path.join(OUT, `assets/cc.${CC_V}.json`), cj); }
    const heroM = R.heroPick(day.matches, index, null, null), rails = R.homeRails(day.matches, index, { arabT:ARABT, exclude:heroM && heroM.id });
    const edHtml = ED.join(""), bdays = (edHtml.match(/<div id="bdays"[^>]*><\/div>/) || [""])[0];
    const ed = blocks(edHtml).secs.filter(sc => sc.title);
    const edCards = ed.map(sc => { const more = (sc.sub.match(/<a [^>]*>[\s\S]*?<\/a>/) || [""])[0], key = "e" + (++SEQ), tz = teaser(sc);
      return { card:`<button type="button" class="ed" data-open="${key}">${edIcon(sc.title)}<span class="tt2">${esc(sc.title)}</span>${tz ? `<span class="tz">${esc(tz)}</span>` : ""}${more ? `<span class="em">${more.replace(/<[^>]+>/g, "")}</span>` : ""}</button>`, vault:vault(key, sc) }; });
    const edLinks = [["/legends/", "الأساطير", "مسيرة وأرقام أبرز لاعبين في تاريخ الكورة الإماراتية"], ["/memorable/", "مباريات ما تنتسى", "المباريات اللي صنعت تاريخ الكورة الإماراتية"], ["/cast/", "تيفو كاست", "الجولة بصوت إماراتي، كل أسبوع"], ["/laws/", "قانون الكورة", "ليش ألغى الحكم الهدف؟ بالإماراتي"], ["/tv/", "شاشة المجلس", "كل المباريات على تلفزيون المجلس"], ["/studio/", "ستوديو التيفو", "صمّم لافتة فريقك للمدرج"]]
      .map(l => `<a class="ed" href="${l[0]}">${edIcon(l[1])}<span class="tt2">${l[1]}</span><span class="tz">${l[2]}</span></a>`).join("");
    const heroHtml = `<section class="hero hhero" data-slot="hero" id="stand"${heroM ? ` style="--mos:url(${mosaicURI([colors[heroM.home.id] || ["#8A938D"], colors[heroM.away.id] || ["#3D4A44"]], heroM.id % 997 + 3)})"` : ""}><canvas aria-hidden="true"></canvas><div class="scrim"></div><div class="hero-in wrap"><span class="kick" id="standkick">${R.kick(heroM)}</span><div class="cap" id="standcap">${R.heroLine(heroM, index)}</div><div id="uaecd"></div>
<div class="hero-acts">${heroM ? `<a class="cta" id="herogo" href="/m/${heroM.id}/">تابع المباراة</a>` : ""}${heroM && APPROVED.quick && heroM.status === "scheduled" && AIQK[heroM.id] ? `<a class="ghost" href="/m/${heroM.id}/#quick">في 60 ثانية</a>` : ""}<button type="button" class="ghost" data-sheet="share">شارك</button></div></div></section>`;
    const dayBox = `<section class="daybox" id="matches" data-slot="list"><div class="rail-h"><h2>كل المباريات</h2><p class="livecount" id="livecount"></p></div>
<div class="daynav"><button type="button" id="prev" aria-label="اليوم اللي قبل">›</button><b id="daytitle">${R.dayNav(today, today)}</b><button type="button" id="next" aria-label="اليوم اللي بعد">‹</button></div>
<div class="seg segf" role="group" aria-label="اعرض"><button type="button" id="segall" aria-pressed="true">الكل</button><button type="button" id="arabonly" aria-pressed="false">العرب</button><button type="button" id="freeonly" aria-pressed="false">المجاني في بلدك</button></div>
<div id="day" class="fold">${R.dayList(day.matches, index, { empty:"ما في مباريات اليوم." })}</div><button type="button" class="unfold" id="unfold">كل المباريات</button></section>`;
    const body = heroHtml + `<div class="wrap body">` +
      R.rail("r-live", '<i class="cardflip"></i>مباشر الحين', rails.live) +
      R.rail("r-today", "اليوم", rails.today, `<a class="more-l" href="/today/">مباريات اليوم</a>`) +
      R.rail("r-arab", "مباريات العرب", rails.arab, `<a class="more-l" href="#matches" data-seg="arab">كل مباريات العرب</a>`) +
      `<section class="rail rmine" id="r-mine" data-slot="rail"><div class="rail-h"><h2>فريقك</h2></div><div id="mine"></div></section>` + dayBox +
      `<section class="rail cgrid3" data-slot="grid"><div class="rail-h"><h2>البطولات</h2><a class="more-l" href="/competitions/">كل البطولات</a></div><div class="cts">${comps.filter(c => !c.dormant).slice(0, 18).map(tileOf).join("")}</div></section>` +
      `<section class="rail edr" data-slot="rail"><div class="rail-h"><h2>من تيفو</h2></div><div class="rail-s" tabindex="0">${edCards.map(e => e.card).join("")}${bdays.replace('<div id="bdays"', '<div class="ed edb" id="bdays"')}${edLinks}</div>${edCards.map(e => e.vault).join("")}</section></div>`;
    write("index.html", page({ v3:true, path:"/", page:"home", nav:"home", title:"تيفو — نتايج مباريات اليوم مباشر لكل العرب", desc:"نتايج المباريات مباشر بتوقيت بلدك: دوري أدنوك، والمنتخب، وكأس الخليج، وأبطال آسيا، والدوريات الكبيرة. الأحداث والتشكيلات والترتيب والتوقعات أول بأول.", body }));
  };

  // ---- 5. teams
  const tlist = [...teamIds], teamPages = new Set(), playerPages = new Set();
  const full = new Set(index.focus_teams || []); compData.filter(d => d.c.scope === "uae").forEach(d => (d.st && d.st.groups || []).forEach(g => g.rows.forEach(r => full.add(r.team.id))));
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
  const byTeam = new Map(); for (const m of matchSum.values()) for (const side of [m.home, m.away]) if (side && side.id){ if (!byTeam.has(side.id)) byTeam.set(side.id, { side, ms:[] }); byTeam.get(side.id).ms.push(m); }
  tlist.forEach((id, i) => {
    let t = teams[i]; if (t && t.fixtures) t.fixtures = t.fixtures.map(unstale);
    if (!t){ const b = byTeam.get(id); if (!b) return; t = { id, name:b.side.name, name_ar:b.side.name_ar, fixtures:b.ms, squad:[], partial:true }; }
    if (/^(winner|loser)\b/i.test(t.name || "") || /^[1-4][A-Z]{1,4}(\/[1-4]?[A-Z]{1,4})?$/.test(t.name || "")) return;   // bracket placeholders («Winner SF 2», «3CDE») get no page
    tcount++; teamPages.add(+t.id);
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
    const acc = S.accounts(ACC[id]); if (acc) nums = S.sec("حسابات النادي الرسمية", "", acc) + nums;
    const ln = S.loans(t); if (ln) nums += S.sec("لاعبينه المعارين", "", ln);
    { const tf = tfiles[i] || {}, rc = S.teamRecords(tf.rec), hm = S.heatmap(tf.hist), cu = S.callups(tf.cu), xi = S.xiTeam(xOf("xi", id), id);
      const tw = TWINS && TWINS.clubs && S.twins(TWINS.clubs[id]); if (tw) nums += S.sec("توأم فريقك", "أقرب الأندية في أسلوب اللعب", tw);
      const ml = (tmonth[i] || []).filter(mo => mo && mo.results && mo.results.length); if (ml.length) nums = S.sec("تقرير الشهر", "", '<p class="tools">' + ml.map(mo => `<a class="btn" href="/t/${id}/month/${mo.month}/">${["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"][+mo.month.slice(5) - 1]}</a>`).join("") + "</p>") + nums;
      if (rc) nums += S.sec("سجل النادي", "من 2010", rc); if (hm) nums += S.sec("كل نتايجه موسم بموسم", "", hm); if (xi) nums += S.sec("التشكيلة المعتادة", "هالموسم", xi); if (cu) nums += S.sec("لاعبينه في المنتخبات", "", cu); }
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
    const wkd = APPROVED.digest ? S.aiDigest(AIDG[id]) : "";
    // v3 team page (stage 3): club key art hero, 5 tabs at most, «بالأرقام» as a shelf, tools in the sheet
    SEQ = 0; PALETTE = [colors[id] || ["#5C6660", "#F6F7F2"]];
    const numSecs = nums ? blocks(nums).secs : [];
    const tabs = [["next", "الياية"], ["past", "النتايج"], ["squad", "اللاعبين"], numSecs.length && ["nums", id === 5789 ? "المنتخب بالأرقام" : "بالأرقام"], wkd && ["week", "ملخص أسبوعك"]].filter(Boolean);
    const nxt = f.next[0];
    // W2.7: the kicker is the club's league and place; a 5-square form strip from the table
    const lrow = (() => { for (const d of compData){ const g = d.st && !d.st.composite && d.st.groups && d.st.groups[0]; const r = g && g.rows.find(r => r.team.id === t.id); if (r && d.c.kind === "league") return { c:d.c, r }; } return null; })();
    const tcol = colors[id] || ["#5C6660", "#F6F7F2"];
    const body = `<section class="hero thero" data-slot="hero" data-art='${esc(JSON.stringify([tcol, [tcol[1] || tcol[0], tcol[0]]]))}' style="--g1:${tcol[0]};--mos:url(${mosaicURI([tcol, [tcol[1] || tcol[0], tcol[0]]], 5)})"><canvas aria-hidden="true"></canvas><div class="scrim"></div><div class="hero-in wrap">
<div class="tid">${R.logo(t, "xl").replace("<img ", `<img style="view-transition-name:crest-${t.id}" `)}<div><h1>${R.tname(t)}</h1>${sub ? `<p class="season">${sub}</p>` : ""}</div></div>
${lrow ? `<p class="tkick"><a href="/c/${lrow.c.key}/?hl=${t.id}#table">${esc(lrow.c.name_ar)} · المركز ${lrow.r.rank}</a></p>${tformHtml(lrow.r.form)}` : ""}
${nxt ? `<a class="tnm" href="/m/${nxt.id}/">${R.logo(nxt.home, "md")}<span class="mid"><b class="dg" data-ko="${esc(nxt.kickoff_utc || "")}">${nxt.time_tbd ? "—" : R.hhmm(nxt.kickoff_uae)}</b><small>${R.tname(nxt.home)} ضد ${R.tname(nxt.away)} · ${R.td(nxt.kickoff_uae, true)}</small></span>${R.logo(nxt.away, "md")}</a>` : ""}${t.id === 5789 ? '<div id="uaecd"></div>' : ""}
<div class="hero-acts"><button type="button" class="cta" id="mybtn">هذا فريقي</button><button type="button" class="ghost" data-sheet="share">شارك</button></div><p class="calk"><a href="/v1/team/${t.id}.ics" id="ics">مبارياته في تقويم جوالك</a></p></div></section><div class="wrap body">` +
      tabsBar("t", tabs) + vpane("t", "next", `<div id="next">${f.next.slice(0, 6).map(m => R.matchRow(m, { date:true, crest:true })).join("") || '<p class="empty">ما في مباريات ياية منشورة.</p>'}</div>`, true) +
      vpane("t", "past", `<div id="past">${f.past.slice(0, 10).map(m => R.matchRow(m, { date:true, crest:true })).join("")}</div>`) + vpane("t", "squad", `${(t.squad || []).length ? '<p class="xih"><button type="button" class="lnk" id="xibtn">سوّ تشكيلتك على الملعب</button></p>' : ""}<div id="squad">${(R.PP = Object.fromEntries([].concat(...(t.squad || []).map(g => (g.players || []).filter(p => p && allPlayers[p.id]).map(p => [p.id, 1])))), R.squad(t))}</div>`) + (numSecs.length ? vpane("t", "nums", shelf(numSecs, { title:id === 5789 ? "المنتخب بالأرقام" : "النادي بالأرقام" })) : "") + (wkd ? vpane("t", "week", wkd) : "") + "</div>";
    const tools = `<button type="button" class="sa" id="wpbtn" hidden>خلفية للجوال</button><a class="sa" href="/t/${t.id}/poster/">بوستر الموسم للطباعة</a>`;
    const names = {}; ((t.squad) || []).forEach(g => (g.players || []).forEach(p => { if (p && p.id && nameOf(p.id)) names[p.id] = nameOf(p.id); }));
    const pp = {}; ((t.squad) || []).forEach(g => (g.players || []).forEach(p => { if (p && p.id && allPlayers[p.id]) pp[p.id] = 1; }));
    const tog = full.has(id); if (tog) OGJ.push({ key:"t-" + id, home:t.name_ar || t.name, home_id:id, hc:colors[id], sub:"المباريات والنتايج واللاعبين" });
    const html = page({ v3:true, og:tog ? "t-" + id : null, path:`/t/${t.id}/`, page:"team", tools, names, pp, attrs:` data-id="${t.id}" data-name="${esc(t.name_ar || t.name)}"`, nav:t.id === 5789 ? "uae" : "", title:`${t.name_ar || t.name}: المباريات والنتايج واللاعبين | تيفو`, desc:`مواعيد مباريات ${t.name_ar || t.name} بتوقيت بلدك، ونتايجه، وقائمة اللاعبين، وأرقامه، واشتراك تقويم يتحدّث بروحه.`, body });
    write(`t/${t.id}/index.html`, html); urls.push(`/t/${t.id}/`);
    if ((t.fixtures || []).length) write(`t/${t.id}/poster/index.html`, page({ path:`/t/${t.id}/poster/`, page:"poster", title:`جدول مباريات ${t.name_ar || t.name} للطباعة | تيفو`, desc:`جدول مباريات ${t.name_ar || t.name} للموسم كامل بتوقيت بلدك، جاهز للطباعة.`, body:S.poster(t) }));
    (tmonth[i] || []).forEach(mo => { if (!mo || !mo.results || !mo.results.length) return; const [yy, mm] = mo.month.split("-").map(Number), mname = ["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"][mm - 1] + " " + yy;
      write(`t/${t.id}/month/${mo.month}/index.html`, page({ path:`/t/${t.id}/month/${mo.month}/`, page:"poster", title:`${t.name_ar || t.name} في ${mname}: تقرير الشهر | تيفو`, desc:`نتايج ${t.name_ar || t.name} في ${mname}، وأحسن اللاعبين، والترتيب في بداية الشهر ونهايته.`, body:`<p class="crumbs"><a href="/t/${t.id}/">${R.tname(t)}</a></p><h1>${R.tname(t)} في ${mname}</h1>` + S.monthReport(mo) + '<p class="tools noprint"><button type="button" class="btn" onclick="print()">اطبعه</button></p>' }));
      urls.push(`/t/${t.id}/month/${mo.month}/`); });
    if (t.id === 5789) write("uae/index.html", html.replace(`<link rel="canonical" href="${SITE}/t/5789/">`, `<link rel="canonical" href="${SITE}/uae/">`));
  });

  // ---- 6. players (135, 120, 137, 149): every player the league files name
  const pids = Object.keys(allPlayers);
  const uaeP = new Set(Object.keys((compX[538] && compX[538].players && compX[538].players.players) || {}));   // the pipeline writes player/{id}.json for the UAE league
  const pjs = await pool(pids, 8, id => uaeP.has(id) ? get(`player/${id}.json`, 1) : null);
  const topP = new Set(); compData.forEach(({ stats }) => ["goals", "assists"].forEach(k => ((stats && stats.lists && stats.lists[k]) || []).slice(0, 30).forEach(r => r.player && topP.add(String(r.player.id)))));
  const pcar = await pool(pids, 8, id => topP.has(id) ? get(`player/${id}/career.json`, 1) : null);
  let pcount = 0;
  pids.forEach((id, i) => {
    const ap = allPlayers[id] || {}, sv = k => ap.stats && ap.stats[k] ? ap.stats[k].value : null;
    const p = pjs[i] || { name:ap.name, team:ap.team, comp:ap.comp, minutes:ap.minutes, goals:sv("goals"), assists:sv("goal_assist"), rating:sv("rating") }; if (!p || !p.name) return; pcount++;
    const tm = p.team || allPlayers[id].team, cx = compX[p.comp || 538] || x538, card = cx.cards && cx.cards.players && cx.cards.players[id];
    const cl = cx.clutch && cx.clutch.players && cx.clutch.players.find(c => String(c.id) === id);
    const tt = { id:tm, name_ar:(S && teamsJson && teamsJson.teams[tm] && teamsJson.teams[tm].name_ar) || "" };
    // W2.7: one 4-across row; a missing count is 0 (from the league's players.json when the player file has none), never «—»
    const z = (a, b2) => a != null ? a : b2 != null ? b2 : 0;
    const st = `<div class="pstats four"><div><b>${z(p.goals, sv("goals"))}</b><span>أهداف</span></div><div><b>${z(p.assists, sv("goal_assist"))}</b><span>صناعة</span></div><div><b>${z(p.minutes, ap.minutes)}</b><span>دقيقة</span></div><div><b>${p.rating != null ? Number(p.rating).toFixed(1) : "—"}</b><span>التقييم</span></div>${cl ? `<div><b>${cl.total}</b><span>نقاط جابها</span></div>` : ""}</div>`;
    const body = `<p class="crumbs"><a href="/t/${tm}/">${esc(tt.name_ar)}</a></p><h1 class="lat">${esc(p.name)}</h1><p class="season">${[p.position && `المركز ${esc(POS_AR[p.position.split(",")[0].trim().toUpperCase()] || p.position.split(",")[0])}`, p.number && `الرقم <span class="num">${esc(p.number)}</span>`, p.country && R.flag(p.country) && `<span class="flag" title="${esc(p.country)}">${R.flag(p.country)}</span>`].filter(Boolean).join("، ")}</p>` +
      (card ? S.card(id, card).replace('class="tcard"', 'class="tcard big"') : "") + S.sec("موسمه", esc(p.season || ""), st) + (S.form(p.form) ? S.sec("فورمته", "آخر المباريات", S.form(p.form)) : "") + (S.career(pcar[i]) ? S.sec("مسيرته", "", S.career(pcar[i])) : "") + (cx.similar ? (() => { const sm = S.similar(cx.similar, id); return sm ? S.sec("منو يلعب مثله؟", "", sm) : ""; })() : "") +
      (cx.shots && cx.shots.available !== false && cx.shots.players && cx.shots.players[id] ? S.sec("خريطة تسديداته", "", S.shotmap(cx.shots.players[id])) : "") +
      (card ? `<p><a class="btn" href="/c/${(comps.find(cc => cc.id === (p.comp || 538)) || {}).key || "uae-pro-league"}/compare/?a=${id}">قارنه بلاعب ثاني</a></p>` : "");
    playerPages.add(String(id)); write(`p/${id}/index.html`, page({ heroExtra:p.number ? `<span class="shirt" style="--sc:${R.colOn(tm)}" aria-label="الرقم ${esc(p.number)}">${esc(p.number)}</span>` : "", art:colors[tm] ? [colors[tm], [colors[tm][1] || colors[tm][0], colors[tm][0]]] : null, path:`/p/${id}/`, page:"player", title:`${p.name}: أرقامه هالموسم | تيفو`, desc:`${p.name}، ${tt.name_ar}: أهدافه وصناعته وتقييمه وبطاقة تيفو، واللاعبين اللي يلعبون مثله.`, body }));
    urls.push(`/p/${id}/`);
  });

  // ---- 7. matches: summary for all, full detail where stored; probabilities (92) and records at stake (94, 95)
  const mids = [...matchSum.keys()].filter(id => id != null && id !== "null");   // W1.4: a fixture without an id gets no page and no link
  const withDetail = new Set(mids.filter(id => { const m = matchSum.get(id); return m.status === "finished" || R.isLive(m) || (Date.parse(m.kickoff_utc) - Date.now() < 3 * 864e5 && Date.parse(m.kickoff_utc) > Date.now() - 864e5); }));
  const det = await pool([...withDetail], 8, id => get(`match/${id}.json`, 1));
  const D = new Map(); [...withDetail].forEach((id, i) => { if (det[i]) D.set(id, det[i]); });
  for (const id of mids){
    const md0 = D.get(id) || matchSum.get(id), uaeMatchTop = R.UAE_COMPS.indexOf(md0.comp) >= 0 || md0.home.id === 5789 || md0.away.id === 5789;
    const md = md0, sum = matchSum.get(id), ttl = `${R.tname(md.home)} ${md.score ? md.score.home + "-" + md.score.away : "ضد"} ${R.tname(md.away)}`;
    const probs = md.status === "scheduled" ? (md.probs || sum.probs) : null, facts = md.status === "scheduled" ? factsByMatch[id] : null;
    const fa = md.status === "scheduled" && md.comp === 538 && x538.fatigue ? S.fatigue(x538.fatigue, [md.home.id, md.away.id]) : "";
    // v3 match page (DESIGN-v3.md): club-colour key art hero, sticky mini-bar, 5 tabs, analysis as shelf tiles, one sheet
    if (md.venue && !md.venue.name_ar){ const va = VENUE_AR.get(md.venue.name_en || md.venue.name); if (va) md.venue.name_ar = va; }
    SEQ = 0; R.arNames(md); PALETTE = [colors[md.home.id], colors[md.away.id]].filter(Boolean); if (!PALETTE.length) PALETTE = [["#5C6660", "#F6F7F2"]];
    const cx = compX[md.comp] || {}, cdata = compData.find(d => d.c.id === md.comp) || {};
    const uaeMatch = R.UAE_COMPS.indexOf(md.comp) >= 0 || md.home.id === 5789 || md.away.id === 5789;
    const aiSum = APPROVED.summary && AIS[id] ? S.aiSummary(AIS[id]) : "", aiPre = APPROVED.preview && md.status === "scheduled" && AIP[id] ? S.sec("تحليل ما قبل المباراة", "", S.aiPreview(AIP[id])) : "";
    const press = md.status === "scheduled" && uaeMatch ? S.pressSheet(md, cdata.st, cdata.stats, factsByMatch[id], cx.fatigue, D.get(id)) : "";
    const thread = APPROVED.thread && AIS[id] ? S.aiThread(AIS[id]) : "", comm = APPROVED.commentary ? S.aiCommentary(AICM[id]) : "";
    const opp = md.status === "scheduled" ? S.oppReport(md, cx, cdata.stats) : "";
    if (md.referee && refAr(md.referee)){ md.referee.name_en = md.referee.name; md.referee.name = refAr(md.referee); }
    const ww = md.status !== "finished" ? S.watchWhere(BC[md.comp]) : "", hl = md.status === "finished" ? S.highlight(HLT[md.comp], md).replace(/ \((?:[^()]|\([^()]*\))*\)(?=<\/a>)/, m => { const ch = /bein/i.test(m) ? "بي إن سبورتس" : /AFC/.test(m) ? "قناة الاتحاد الآسيوي" : /Pro League/i.test(m) ? "قناة رابطة المحترفين" : /CAF/.test(m) ? "قناة الاتحاد الأفريقي" : /UEFA|Champions/i.test(m) ? "قناة اليويفا" : ""; return ch ? " على " + ch : ""; }) : "";
    const mdy = md.venue && STAD[md.venue.id] ? S.matchDay(md, STAD[md.venue.id]) : "";
    const sgrid = probs ? S.scoreGrid(probs, md) : "";
    const L2 = md.lineups; const tac = L2 && L2.home && L2.away ? (() => { const subs = side => (md.events || []).filter(e => e.type === "sub" && e.team === side), f = side => { const sb = subs(side); return `${R.tname(md[side])}: خطة <span class="num">${esc(L2[side].formation || "—")}</span>${sb.length ? `، ${sb.length === 1 ? "تبديل واحد" : sb.length === 2 ? "تبديلين" : sb.length + " تبديلات"}، أولها الدقيقة <span class="num">${sb[0].minute}</span>` : ""}.`; }; return `<ul class="facts-l"><li>${f("home")}</li><li>${f("away")}</li></ul>`; })() : "";
    const replay = md.status === "finished" && (md.events || []).some(e => /goal|red|yellow/.test(e.type)) ? '<div class="replay"><label>اسحب لأي دقيقة: <b class="num" id="rpm">90</b></label><input type="range" id="rpr" min="0" max="' + ((md.events || []).some(e => e.minute > 90) ? 120 : 90) + '" value="' + ((md.events || []).some(e => e.minute > 90) ? 120 : 90) + '" aria-label="الدقيقة"><div class="rpsc"><span>' + R.tname(md.home) + '</span><b class="num" id="rps">' + (md.score ? md.score.home + " - " + md.score.away : "") + '</b><span>' + R.tname(md.away) + '</span></div><ul class="facts-l" id="rpe"></ul><script type="application/json" id="rpev">' + JSON.stringify((md.events || []).filter(e => /goal|red|yellow|second/.test(e.type)).map(e => [e.minute + (e.added ? e.added / 10 : 0), e.type, e.team, e.player && e.player.name, e.score ? [e.score.home, e.score.away] : null])).replace(/</g, "\\u003c") + "</script></div>" : "";
    // التحليل: win probability leads; commentary (196), AI summary/preview, opponent report, press sheet (with commentator mode), X thread … as tiles
    const tlHtml = R.timeline(md), momHtml = momentumSvg(md);
    const anaSecs = blocks([momHtml ? S.sec("الضغط", "مين كان مسيطر دقيقة بدقيقة", momHtml) : "", tlHtml ? S.sec("خط المباراة", "الأهداف والكروت دقيقة بدقيقة", tlHtml) : "", comm ? S.sec("التعليق", "", comm) : "", aiSum ? S.sec("الخلاصة بالذكاء الاصطناعي", "", aiSum) : "", aiPre, S.winprob(md) ? S.sec("فرص الفوز دقيقة بدقيقة", "", S.winprob(md)) : "", sgrid ? S.sec("أرجح النتايج بالضبط", "", sgrid) : "", opp ? S.sec("تقرير الفريقين", "", opp) : "", press ? S.sec("ورقة الصحفي", "", press) : "", thread ? S.sec("ثريد إكس", "", thread) : "", S.firsts(md) ? S.sec("أوائل", "", S.firsts(md)) : "", replay ? S.sec("إعادة المباراة", "", replay) : "", fa ? S.sec("ضغط المباريات", "", fa) : "", facts && facts.length ? S.sec("قبل المباراة", "", S.matchFacts(facts)) : "", mdy ? S.sec("رايح الملعب؟", "", mdy) : ""].join("")).secs;
    const li = anaSecs.findIndex(sc => sc.title === "فرص الفوز دقيقة بدقيقة"), anaLead = li >= 0 ? anaSecs.splice(li, 1)[0].full : "";
    const faqQ = S.faq(md, (BC[md.comp] && BC[md.comp].broadcasters || []).map(b => b.name_ar).join("، "), md.venue && (md.venue.name_ar || md.venue.name_en));
    const faqHtml = faqQ.length ? `<details class="faq wrap"><summary><h2>أسئلة عن المباراة</h2></summary><dl class="gl">${faqQ.map(q => `<dt>${esc(q[0])}</dt><dd>${esc(q[1])}</dd>`).join("")}</dl></details>` : "";
    const sched = md.status === "scheduled";
    // 369 «ليش هالنتيجة؟» (finished: the first tab's lead) and 372 «مباراة الليلة في 60 ثانية» (before kickoff: a card)
    const why = APPROVED.why && md.status === "finished" && AIWHY[id] && (AIWHY[id].lines || []).length ? `<div class="why"><b>ليش هالنتيجة؟</b>${AIWHY[id].lines.map(l => `<p>${esc(l)}</p>`).join("")}</div>` : "";
    const quick = APPROVED.quick && sched && AIQK[id] && (AIQK[id].lines || []).length ? `<div class="quick" id="quick"><b>مباراة الليلة في 60 ثانية</b><ol>${AIQK[id].lines.map(l => `<li>${esc(l)}</li>`).join("")}</ol></div>` : "";
    R._hasWhy = !!why; const catchHtml = R.catchup(md); R._hasWhy = false;
    // W2.6: before kickoff the first tab reads وين تنقل -> lineup status -> 3 facts; after kickoff the events lead
    const luState = sched ? (md.lineups && md.lineups.home && md.lineups.type !== "lastStarting11" ? '<p class="lus">التشكيلة الرسمية نزلت. <a href="#lineups" data-go="lineups">شوفها</a></p>' : '<p class="lus muted">التشكيلة تنزل قبل المباراة بساعة تقريباً.</p>') : "";
    const facts3 = sched && facts && facts.length ? `<ul class="facts-l f3">${facts.slice(0, 3).map(f => `<li>${esc(String(f.text_ar).replace(/\s*\(بيانات FotMob\)/g, ""))}</li>`).join("")}</ul>` : "";
    const eventsPane = sched ? `<div id="wwbox" data-comp="${md.comp}">${ww ? S.sec("وين تنقل في الإمارات", "", ww) : ""}</div>` + luState + quick + facts3 + (probs ? S.probs(probs, md) : "") + `<div id="catchup"></div><div id="ltable"></div>` + (anaSecs.length ? shelf(anaSecs, { title:"قبل المباراة بالتفصيل" }) : "") + `<div id="events" hidden>${R.events(md)}</div><h3 class="sub-h">تفاصيل المباراة</h3><div id="facts">${R.matchFacts(md, index)}</div>`
      : why + quick + `<div id="catchup">${catchHtml}</div>` + (hl ? `<p class="hlink">${hl}</p>` : "") + `<div id="events">${R.events(md)}</div><div id="ltable"></div>` + (md.status !== "finished" ? `<div id="wwbox" data-comp="${md.comp}">${ww ? S.sec("وين تنقل في الإمارات", "", ww) : ""}</div>` : "") + `<h3 class="sub-h">تفاصيل المباراة</h3><div id="facts">${R.matchFacts(md, index)}</div>`;
    const cname = md.comp_name_ar || R.compName(index, md.comp), ckey = R.compKey(index, md.comp);
    const tools = `<button type="button" class="sa" id="storybtn">صورة للستوري</button><button type="button" class="sa" id="secondbtn">الشاشة الثانية</button><button type="button" class="sa" id="cinebtn">وضع السينما</button>${md.lineups && md.lineups.home ? '<button type="button" class="sa" id="pcardbtn">بطاقة أداء لاعب</button>' : ""}<button type="button" class="sa" id="embedbtn" data-src="/embed/m/?id=${id}" data-h="260">ضمّن المباراة في موقعك</button><a class="sa" href="/tv/?m=${id}">على شاشة المجلس</a>${uaeMatchTop ? `<a class="sa" href="/m/${id}/kit/">عدّة صانع المحتوى</a>` : ""}`;
    const body = `<section class="hero mhero" data-slot="hero" id="mhero" style="--mos:url(${mosaicURI([colors[md.home.id] || ["#8A938D"], colors[md.away.id] || ["#3D4A44"]], md.id % 997 + 3)})"><canvas aria-hidden="true"></canvas><div class="scrim"></div><div class="hero-in wrap">
<p class="hk">${ckey ? `<a href="/c/${ckey}/">${esc(cname)}</a>` : esc(cname)}${md.round && !isNaN(parseFloat(md.round)) ? `، الجولة <span class="num">${esc(md.round)}</span>` : md.stage ? "، " + esc(R.stageAr(md.stage)) : ""}</p>
<div id="mh">${R.matchHead(md)}</div>${sched || R.isLive(md) ? '<p class="prayl" id="prayl"></p>' : ""}<div class="hero-acts">${sched ? `<a class="cta" href="#events" data-go="events">وين تنقل</a>` : md.status === "finished" && hl ? `<a class="cta" href="${esc((hl.match(/href="([^"]+)"/) || [])[1] || "#events")}" rel="noopener">الملخص</a>` : `<a class="cta" href="#lineups" data-go="lineups">التشكيلة</a>`}<button type="button" class="ghost" data-sheet="share">شارك وأدوات</button></div></div></section>
<div class="mini" id="mini" aria-hidden="true"><div class="wrap"></div></div>
<script type="application/json" id="msum">${JSON.stringify(Object.assign({}, sum, { events:undefined, lineups:undefined, stats:undefined, h2h:undefined })).replace(/</g, "\\u003c")}</script><div class="wrap body">` +
      tabsBar("m", [["events", sched ? "قبل المباراة" : "الأحداث"], ["lineups", "التشكيلة"], ["stats", "الأرقام"], ["h2h", "المواجهات"]]).replace('data-t="stats"', sched ? 'data-t="stats" hidden' : 'data-t="stats"') +   // W2.6: 4 tabs; الأرقام appears at kickoff
      vpane("m", "events", eventsPane, true) +
      vpane("m", "lineups", `<div class="tools"><button type="button" class="btn" id="p3dbtn" data-src="/assets/pitch3d.${ASSET_V}.js"${md.lineups && md.lineups.home ? "" : " hidden"}>شوفها على ملعب ثلاثي الأبعاد</button></div><div id="p3d"></div><div id="lineups">${R.lineups(md)}</div>`) +
      vpane("m", "stats", `<div id="stats">${R.stats(md)}</div>` + (sched ? "" : anaLead + (anaSecs.length ? shelf(anaSecs, { title:"التحليل" }) : ""))) +
      vpane("m", "h2h", `<div id="h2h">${R.h2h(md)}</div>`) + "</div>" + faqHtml;
    const names = {}; if (md.venue && md.venue.name_ar) names.venue = md.venue.name_ar; if (md.referee && md.referee.name_en) names.ref = md.referee.name;
    if (md.lineups) ["home", "away"].forEach(sd => { const co = md.lineups[sd] && md.lineups[sd].coach; if (coachAr(co)) names[co.id] = coachAr(co); });
    (md.events || []).forEach(e => [e.player, e.assist, e.player_out].forEach(p => { if (p && p.id && nameOf(p.id)) names[p.id] = nameOf(p.id); }));
    if (md.lineups) ["home", "away"].forEach(sd => md.lineups[sd] && [].concat(md.lineups[sd].starters || [], md.lineups[sd].subs || [], md.lineups[sd].unavailable || []).forEach(p => { if (p && p.id && nameOf(p.id)) names[p.id] = nameOf(p.id); }));
    [md.home.id, md.away.id].forEach(tid => { const tj = teamById.get(tid); ((tj && tj.squad) || []).forEach(g => (g.players || []).forEach(p => { if (p && p.id && nameOf(p.id)) names[p.id] = nameOf(p.id); })); });   // squads: live subs/scorers stay Arabic
    const ld = (() => { const st = { postponed:"https://schema.org/EventPostponed", cancelled:"https://schema.org/EventCancelled" }[md.status] || "https://schema.org/EventScheduled", H = md.home.name_ar || md.home.name, A = md.away.name_ar || md.away.name, v = md.venue || {};   // 348
      return { "@context":"https://schema.org", "@type":"SportsEvent", name:`${H} ضد ${A}`, url:`${SITE}/m/${id}/`, startDate:md.kickoff_uae || md.kickoff_utc, sport:"Football", eventStatus:st, eventAttendanceMode:"https://schema.org/OfflineEventAttendanceMode",
        homeTeam:{ "@type":"SportsTeam", name:H }, awayTeam:{ "@type":"SportsTeam", name:A }, competitor:[{ "@type":"SportsTeam", name:H }, { "@type":"SportsTeam", name:A }],
        superEvent:{ "@type":"SportsEvent", name:md.comp_name_ar || R.compName(index, md.comp) },
        ...(v.name_ar || v.name_en || v.name ? { location:{ "@type":"StadiumOrArena", name:v.name_ar || v.name_en || v.name, ...(v.city || v.country || v.in_uae ? { address:{ "@type":"PostalAddress", ...(v.city ? { addressLocality:v.city } : {}), ...(v.country || v.in_uae ? { addressCountry:v.in_uae ? "AE" : v.country } : {}) } } : {}), ...(v.lat != null ? { geo:{ "@type":"GeoCoordinates", latitude:v.lat, longitude:v.lon } } : {}) } } : {}),
        ...(md.status === "finished" && md.score ? { description:`انتهت ${H} ${md.score.home} - ${md.score.away} ${A}` } : {}) }; })();
    const recent = Date.parse(md.kickoff_utc || 0), ogOn = uaeMatch || (recent > Date.now() - 3 * 864e5 && recent < Date.now() + 7 * 864e5 && [538, 11027, 329, 525, 9469, 536, 47, 87, 42].includes(md.comp));
    if (ogOn) OGJ.push({ key:"m-" + id, home:md.home.name_ar || md.home.name, away:md.away.name_ar || md.away.name, home_id:md.home.id, away_id:md.away.id, hc:colors[md.home.id], ac:colors[md.away.id], comp:md.comp_name_ar || R.compName(index, md.comp), score:md.score && md.status === "finished" ? `${md.score.away} - ${md.score.home}` : null, time:md.score && md.status === "finished" ? null : R.hhmm(md.kickoff_uae), sub:md.score && md.status === "finished" ? "انتهت" : R.dayLabel(R.ymd(md.kickoff_uae)) + " بتوقيت الإمارات", ...(md.status === "finished" ? { sizes:["story", "feed", "x"] } : {}) });   // 381: platform sizes for results
    const sized = ogOn && md.status === "finished" ? [["story", "ستوري 1080×1920"], ["feed", "بوست 1080×1350"], ["x", "إكس 1600×900"]].map(z => `<a class="sa" href="/og/m-${id}-${z[0]}.png" download="tifo-${id}-${z[0]}.png">صورة جاهزة: ${z[1]}</a>`).join("") : "";
    write(`m/${id}/index.html`, page({ v3:true, og:ogOn ? "m-" + id : null, ogv:ogOn && md.status === "finished" && md.score ? `ft-${md.score.home}-${md.score.away}` : "", path:`/m/${id}/`, page:"match", nav:"home", attrs:` data-id="${id}"`, tools:tools + sized, names, title:`${ttl} — ${md.comp_name_ar || R.compName(index, md.comp)} | تيفو`, desc:`${R.tname(md.home)} ضد ${R.tname(md.away)} ${R.dayLabel(R.ymd(md.kickoff_uae))} الساعة ${R.hhmm(md.kickoff_uae)} بتوقيت الإمارات: النتيجة المباشرة والأحداث والتشكيلة والإحصائيات والمواجهات السابقة.`, body, ld:faqQ.length ? [ld, { "@context":"https://schema.org", "@type":"FAQPage", mainEntity:faqQ.map(q => ({ "@type":"Question", name:q[0], acceptedAnswer:{ "@type":"Answer", text:q[1] } })) }] : ld }));
    urls.push(`/m/${id}/`);
    if (uaeMatch && (md.status === "scheduled" || Date.parse(md.kickoff_utc) > Date.now() - 3 * 864e5)){
      const nums = [probs ? `توقعات تيفو: ${Math.round(probs.home * 100)}% فوز ${md.home.name_ar}، ${Math.round(probs.draw * 100)}% تعادل، ${Math.round(probs.away * 100)}% فوز ${md.away.name_ar}.` : "", ...((factsByMatch[id] || []).map(f => String(f.text_ar).replace(/\s*\(بيانات FotMob\)/g, "")))].filter(Boolean);
      write(`m/${id}/kit/index.html`, page({ art:[colors[md.home.id] || ["#5C6660"], colors[md.away.id] || ["#3D4A44"]], path:`/m/${id}/kit/`, page:"kit", attrs:` data-id="${id}"`, title:`عدّة صانع المحتوى: ${R.tname(md.home)} و${R.tname(md.away)} | تيفو`, desc:`أرقام جاهزة للنسخ وصور للمشاركة وموعد المباراة في كل دولة عربية مع القناة الناقلة.`,
        body:`<p class="crumbs"><a href="/m/${id}/">المباراة</a></p><h1>عدّة صانع المحتوى</h1><p class="season">${R.tname(md.home)} و${R.tname(md.away)}</p><script type="application/json" id="msum">${JSON.stringify(Object.assign({}, sum, { events:undefined, lineups:undefined, stats:undefined, h2h:undefined })).replace(/</g, "\\u003c")}</script>` +
          S.sec("أرقام جاهزة للنسخ", "", nums.length ? '<ol class="thread">' + nums.map(n => `<li><p>${esc(n)}</p><button type="button" class="btn copy" data-copy="${esc(n)}">انسخ</button></li>`).join("") + "</ol>" : '<p class="empty">ما في أرقام للحين.</p>') +
          '<p class="tools"><button type="button" class="btn" id="storybtn">صورة ستوري للمباراة</button></p>' +
          S.sec("الموعد والقناة في كل دولة عربية", "", `<div id="kitct" data-comp="${md.comp}" data-ko="${esc(md.kickoff_uae || "")}"><p class="empty skel">نجهّز الجدول…</p></div>`) }));
    }
  }

  // ---- 7b. majlis TV (22, 131) and the Tifo studio (152)
  write("tv/index.html", page({ path:"/tv/", page:"tv", title:"شاشة المجلس: كل المباريات مباشر على شاشة كبيرة | تيفو", desc:"افتحها على تلفزيون المجلس أو القهوة: كل مباريات اليوم مباشر بخط كبير، تتحدّث بروحها كل 20 ثانية.",
    body:'<div class="tvbar"><h1>شاشة المجلس</h1><button type="button" class="btn" id="fsbtn">الشاشة كاملة</button></div><div id="tv" class="tvgrid"><p class="empty skel">نحمّل المباريات…</p></div><p class="muted small">افتح هالصفحة على تلفزيون المجلس. تتحدّث بروحها كل 20 ثانية. ولمتابعة مباراتين جنب بعض، افتح أي مباراة واضغط «على شاشة المجلس».</p>' }));
  urls.push("/tv/");
  const clubs = [5789].concat(((compData.find(d => d.c.id === 538) || {}).st || { groups:[{ rows:[] }] }).groups[0].rows.map(r => r.team.id));
  write("studio/index.html", page({ path:"/studio/", page:"studio", title:"ستوديو التيفو: صمّم لافتة فريقك للمدرج | تيفو", desc:"اختار فريقك واكتب عبارتك، وتطلع لك لافتة بألوان النادي جاهزة للطباعة وتاخذها للملعب.",
    body:`<h1>ستوديو التيفو</h1><p class="muted">اختار فريقك واكتب عبارتك، وتطلع لك لافتة بألوان ناديك (3000×1000) جاهزة للطباعة.</p><div class="studio"><div class="cmpsel"><select id="sclub" aria-label="الفريق">${clubs.map(id => `<option value="${id}">${esc((teamsJson.teams[id] || {}).name_ar || id)}</option>`).join("")}</select><input id="stext" maxlength="40" value="ما نمشي بروحنا" aria-label="العبارة"></div><canvas id="sprev" width="1500" height="500"></canvas><div class="tools"><button type="button" class="btn" id="sdl">نزّل اللافتة</button></div></div>` }));
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
    body:`<p class="tools"><button type="button" class="btn" id="wkbtn">صورة جدول الأسبوع بتوقيت بلدك</button></p><script type="application/json" id="wkdata">${JSON.stringify(picks.map(x => ({ h:x.m.home.id, a:x.m.away.id, home:x.m.home.name_ar || x.m.home.name, away:x.m.away.name_ar || x.m.away.name, ko:x.m.kickoff_uae, comp:x.m.comp }))).replace(/</g, "\\u003c")}</script>` + "<h1>مباريات الأسبوع</h1><p class=\"muted\">أهم مباريات الأيام السبعة الياية بتوقيت الإمارات: مباريات الإمارات أول، وبعدها اللي فيها الترتيب على المحك أو الفريقين من فوق الجدول.</p>" + (picks.length ? picks.map(x => `<div class="wk"><span class="muted small">${esc(x.m.comp_name_ar || R.compName(index, x.m.comp))}</span>${R.matchRow(x.m, { date:true })}</div>`).join("") : '<p class="empty">ما في مباريات في الأيام الياية.</p>') }));
  urls.push("/week/");

  // ---- 224 records tonight (home), 226 referee pages, 227 coach pages, 228 round pages
  { const tonight = (day.matches || []).flatMap(m => (factsByMatch[m.id] || []).filter(f => f.record_at_stake).map(f => ({ m, f })));
    const rt = S.recordsTonight(tonight); if (rt) ED.push(S.sec("أرقام ممكن تنكسر اليوم", "", rt)); }
  const byIdM = id => matchSum.get(id) || D.get(id);
  const stIds = cid => { const d = compData.find(x => x.c.id === cid); return d && d.st && !d.st.composite && d.st.groups && d.st.groups[0] ? d.st.groups[0].rows.map(r => r.team.id) : []; };
  const refs = new Map(); compData.forEach(({ c, x }) => ((x.referees && x.referees.referees) || []).forEach(r => { if (r.id && !refs.has(r.id)) refs.set(r.id, Object.assign({ comp:c }, r)); }));
  for (const [rid, r] of refs){ write(`r/${rid}/index.html`, page({ path:`/r/${rid}/`, page:"ref", title:`الحكم ${r.name}: كروته وبلنتياته ومبارياته | تيفو`, desc:`سجل الحكم ${r.name} في ${r.comp.name_ar}: الإنذارات والطرد وضربات الجزاء بالمباراة، وكل مبارياته.`, body:`<p class="crumbs"><a href="/c/${r.comp.key}/#num">${esc(r.comp.name_ar)}</a></p><h1 class="lat">${esc(r.name)}</h1><p class="season">حكم${r.country ? ` <span class="flag">${esc(r.country)}</span>` : ""}</p>` + S.refPage(r, byIdM) })); urls.push(`/r/${rid}/`); }
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
    write("coach/compare/index.html", page({ attrs:` data-cv="${CV}"`, path:"/coach/compare/", page:"coachcmp", title:"قارن بين مدربين | تيفو", desc:"قارن أي مدربين درّبوا في الدوري: المباريات والفوز ومعدل النقاط والأندية.", body:'<h1>قارن بين مدربين</h1><div class="cmpsel"><select id="ca" aria-label="المدرب الأول"></select><select id="cb" aria-label="المدرب الثاني"></select></div><div id="cout"></div>' })); urls.push("/coach/compare/"); }
  for (const [cid, co] of coachRows){ if (!co.rows.length) continue; co.rows.sort((a, b) => String(b.season).localeCompare(String(a.season)));
    write(`coach/${cid}/index.html`, page({ path:`/coach/${cid}/`, page:"ref", title:`المدرب ${co.name}: مسيرته التدريبية | تيفو`, desc:`مسيرة المدرب ${co.name}: الأندية والمواسم والفوز والتعادل والخسارة ومعدل النقاط.`, body:`<h1 class="lat">${esc(co.name)}</h1><p><a class="btn" href="/coach/compare/?a=${cid}">قارنه بمدرب ثاني</a></p>${co.current ? `<p class="season">يدرّب الحين <a href="/t/${co.current}/">${esc((teamsJson.teams[co.current] || {}).name_ar || "")}</a></p>` : ""}` + S.coachPage(co.name, co.rows) + (CH2H.has(cid) ? S.sec("ضد المدربين", "هالموسم", '<div class="tblwrap"><table class="st wrapn"><thead><tr><th style="text-align:start">المدرب</th><th>فوز</th><th>تعادل</th><th>خسارة</th></tr></thead><tbody>' + CH2H.get(cid).sort((a, b) => (b.w + b.d + b.l) - (a.w + a.d + a.l)).map(o => `<tr><td class="tm">${coachRows.has(o.op) ? `<a class="lat" href="/coach/${o.op}/">${esc(o.name || "")}</a>` : `<span class="lat">${esc(o.name || "")}</span>`}</td><td>${o.w}</td><td>${o.d}</td><td>${o.l}</td></tr>`).join("") + "</tbody></table></div>") : "") })); urls.push(`/coach/${cid}/`); }
  for (const { c, fx, x } of compData){ if (!fx || !fx.matches) continue; const rr = R.rounds(fx);
    for (const k of rr.order){ if (isNaN(parseFloat(k))) continue; const ms = rr.by[k], fin = ms.filter(m => m.status === "finished"), goals = fin.reduce((a, m) => a + (m.score ? m.score.home + m.score.away : 0), 0);
      const tor = x["team-of-round"] && x["team-of-round"].rounds && x["team-of-round"].rounds[k] ? S.teamOfRound({ rounds:{ [k]:x["team-of-round"].rounds[k] } }) : "";
      write(`c/${c.key}/r/${k}/index.html`, page({ lg:LOGO(c.id) ? [c.id].concat(glow(c.id)) : null, path:`/c/${c.key}/r/${k}/`, page:"ref", nav:String(c.id), title:`${c.name_ar}: الجولة ${k} ${c.season || ""} | تيفو`, desc:`نتايج ومواعيد الجولة ${k} من ${c.name_ar} بتوقيت بلدك، والأهداف وتشكيلة الجولة.`,
        body:`<p class="crumbs"><a href="/c/${c.key}/">${esc(c.name_ar)}</a></p><h1>الجولة ${esc(k)}</h1>` + (fin.length && stIds(c.id).length ? S.sec("قصة الجولة", "انزل وشوف", S.roundStory(fx, k, stIds(c.id))) : "") + (fin.length ? `<div class="pstats"><div><b>${fin.length}</b><span>مباراة خلصت</span></div><div><b>${goals}</b><span>هدف</span></div><div><b>${fin.length ? (goals / fin.length).toFixed(1) : 0}</b><span>بالمباراة</span></div></div>` : "") + R.roundList(ms) + (tor ? S.sec("تشكيلة الجولة", "", tor) : "") + `<p class="tools">${rr.order.indexOf(k) > 0 ? `<a class="btn" href="/c/${c.key}/r/${rr.order[rr.order.indexOf(k) - 1]}/">الجولة اللي قبل</a>` : ""}${rr.order.indexOf(k) < rr.order.length - 1 ? `<a class="btn" href="/c/${c.key}/r/${rr.order[rr.order.indexOf(k) + 1]}/">الجولة اللي بعد</a>` : ""}</p>` })); urls.push(`/c/${c.key}/r/${k}/`); } }

  // ---- 198: pages for the most-searched phrases
  { const tmr = new Date(Date.now() + 4 * 3600e3 + 864e5).toISOString().slice(0, 10), dayT = await get(`day/${tmr.replace(/-/g, "")}.json`) || { matches:[] };
    [["today", "اليوم", today, day], ["tomorrow", "بكرة", tmr, dayT]].forEach(([slug, word, d, dd]) => {
      write(`${slug}/index.html`, page({ path:`/${slug}/`, page:"daypage", nav:"home", title:`مباريات ${word} ${R.dayLabel(d)}: المواعيد والقنوات الناقلة | تيفو`, desc:`كل مباريات ${word} ${R.dayLabel(d)} بتوقيت بلدك: الدوريات العربية، والدوري الإنجليزي والإسباني، وأبطال آسيا وأوروبا، مع القنوات الناقلة والنتايج مباشر.`,
        body:`<h1>مباريات ${word}</h1><p class="season">${esc(R.dayLabel(d))}، والمواعيد بتوقيت بلدك</p>` + `<div id="day">${R.dayList(dd.matches, index, { empty:"ما في مباريات." })}</div>` + '<p><a class="btn" href="/watch/">وين تنقل كل بطولة</a></p>' })); urls.push(`/${slug}/`); }); }

  // ---- 262 glossary, 251 lab, 289 academy
  const GLOSS = require("./src/glossary.js");
  write("glossary/index.html", page({ path:"/glossary/", page:"ref", title:"قاموس مصطلحات الكورة بالإماراتي | تيفو", desc:"شرح بسيط لكل مصطلح في تيفو: الأهداف المتوقعة، الضغط، تصنيف تيفو، محاكي الموسم، التسلل، الفار وغيرها.", body:"<h1>قاموس المصطلحات</h1><p class=\"muted\">شرح بسيط لكل مصطلح يطلع في تيفو.</p><dl class=\"gl\">" + GLOSS.map(g => `<dt id="${g[0]}">${esc(g[1])}</dt><dd>${esc(g[2])}</dd>`).join("") + "</dl>" })); urls.push("/glossary/");
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
    write("academy/index.html", page({ path:"/academy/", page:"ref", title:"أكاديمية تيفو: كيف تقرا أرقام الكورة | تيفو", desc:"دروس قصيرة بالإماراتي: تصنيف تيفو، نسب الفوز، محاكي الموسم، الأهداف المتوقعة، الضغط، الحاسم، والصعوبة، بأمثلة حقيقية.", body:"<h1>أكاديمية تيفو</h1><p class=\"muted\">كيف تقرا أرقامنا، في دروس قصيرة وأمثلة من مباريات حقيقية.</p>" + lessons.map((l, i) => `<section class="lesson"><h2>${i + 1}. ${l[1]}</h2><p class="ex">${l[2]}</p><p class="small"><a href="${l[3]}">شوفها في الموقع</a>، أو <a href="/glossary/#${l[0]}">في القاموس</a></p></section>`).join("") })); urls.push("/academy/"); }

  // 184 newsletter, 333 watch mode, 230 countdowns
  write("newsletter/index.html", page({ path:"/newsletter/", page:"newsletter", title:"نشرة تيفو الأسبوعية | تيفو", desc:"كل خميس في إيميلك: نتايج الأسبوع، والترتيب، ومباريات الأسبوع الياي بتوقيت بلدك.", body:'<h1>نشرة تيفو</h1><p class="muted">كل خميس في إيميلك: النتايج، والترتيب، ومباريات الأسبوع الياي بتوقيت بلدك. بدون إزعاج، وتقدر تلغي بضغطة.</p><div id="nlmsg"></div><form class="ask nlform"><input type="email" name="email" required placeholder="إيميلك" aria-label="إيميلك"><button class="btn" type="submit">اشترك</button></form>' })); urls.push("/newsletter/");
  write("w/index.html", page({ path:"/w/", page:"watch", title:"وضع المتابعة | تيفو", desc:"نتيجة فريقك بخط كبير، تتحدّث بروحها.", body:'<div id="wbox" class="wbox"><p class="empty">اختار فريقك من صفحة النادي، وبعدها افتح هالصفحة.</p></div>' }));
  { const soon = [...matchSum.values()].filter(m => m.status === "scheduled" && m.kickoff_utc && Date.parse(m.kickoff_utc) > Date.now() && Date.parse(m.kickoff_utc) < Date.now() + 60 * 864e5);
    const big = soon.filter(m => { const nat = [m.home.id, m.away.id].some(t => (teamsJson.teams[t] || {}).national) || m.home.id === 5789 || m.away.id === 5789; const k = [m.home.id, m.away.id].sort((a, b) => a - b).join("-"); const w = compX[m.comp] && compX[m.comp].watch && compX[m.comp].watch.matches[m.id]; return nat || R.H2HK[k] || (w && w.score >= 80) || /final|نهائي/i.test(m.stage || ""); }).sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc)).slice(0, 20);
    write("countdowns/index.html", page({ path:"/countdowns/", page:"countdowns", title:"عدّادات المباريات الكبيرة | تيفو", desc:"كم باقي على الديربيات ومباريات المنتخبات والنهائيات، بتوقيت بلدك.", body:"<h1>كم باقي؟</h1>" + (big.length ? big.map(m => `<a class="cd" href="/m/${m.id}/"><span><b>${R.tname(m.home)} و${R.tname(m.away)}</b><br><span class="small">${esc(m.comp_name_ar || R.compName(index, m.comp))}، ${R.td(m.kickoff_uae, true)}</span></span><span class="dg cdt" data-u="${esc(m.kickoff_utc)}">—</span></a>`).join("") : '<p class="empty">ما في مباريات كبيرة قريبة.</p>') })); urls.push("/countdowns/"); }

  // ---- 7e. phase 4 reference pages (research/tifo-2026-09-27 + Arabic from ai/history_ar.py)
  const RS = path.join(process.env.HOME, "workspace/research/tifo-2026-09-27"), HC = path.join(CACHE, "history");
  const rj = (f) => { try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch (e){ return null; } };
  const hl = rj(path.join(HC, "legends.json")) || {}, hm = rj(path.join(HC, "memorable.json")) || {}, ht = rj(path.join(HC, "thisday.json")) || {}, hw = rj(path.join(HC, "laws.json")) || {};
  const legRaw = (rj(path.join(RS, "legends.json")) || {}).players || [];
  const memRaw = (rj(path.join(RS, "memorable.json")) || {}).matches || [], tdRaw = (rj(path.join(RS, "thisday.json")) || {}).events || [], lawRaw = (rj(path.join(RS, "laws.json")) || {}).topics || [];
  const refPage = (p, title, desc, h1, lead, body) => { if (!body) return; write(p.slice(1) + "index.html", page({ path:p, page:"ref", title, desc, body:`<h1>${h1}</h1><p class="muted">${lead}</p>` + body })); urls.push(p); };
  refPage("/legends/", "أساطير الكورة الإماراتية | تيفو", "الطلياني وإسماعيل مطر وعمر عبدالرحمن وعلي مبخوت وغيرهم: مسيرتهم وأرقامهم، مع المصادر.", "أساطير الكورة الإماراتية", "مسيرة وأرقام أبرز لاعبين في تاريخ الكورة الإماراتية، وكل معلومة معها مصدرها.", S.legends(legRaw, hl));
  refPage("/memorable/", "مباريات ما تنتسى في تاريخ الكورة الإماراتية | تيفو", "من تصفيات 1990 لين نهائي آسيا 2024: المباريات اللي صنعت تاريخ الكورة الإماراتية.", "مباريات ما تنتسى", "مباريات صنعت تاريخ الكورة الإماراتية، من الأحدث للأقدم.", S.memorable(memRaw, hm));
  refPage("/laws/", "قانون الكورة بالإماراتي: التسلل، اللمسة، البلنتي، الفار | تيفو", "ليش ألغى الحكم الهدف؟ شرح قوانين الكورة الرسمية (IFAB 2026/27) بالإماراتي: التسلل، لمسة اليد، البلنتي، الفار، والوقت بدل الضايع.", "قانون الكورة بالإماراتي", "شرح بسيط لقوانين الكورة من النص الرسمي لـIFAB (نسخة 2026/27)، وتحت كل شرح الجملة الرسمية نفسها.", S.laws(lawRaw, hw));
  const mmddToday = today.slice(5);
  const tdToday = S.thisday(tdRaw, ht, mmddToday, 8);
  const tdAll = [...new Set(tdRaw.map(e => e["mm-dd"]))].sort().map(md => { const x = S.thisday(tdRaw, ht, md, 20); if (!x) return ""; const [mo, dd] = md.split("-").map(Number); return `<section class="blk"><h2>${dd} ${["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"][mo - 1]}</h2>${x}</section>`; }).join("");
  refPage("/thisday/", "هذا اليوم في تاريخ الكورة الإماراتية | تيفو", "كل يوم في السنة وشو صار فيه في تاريخ الكورة الإماراتية: مباريات وبطولات ومواليد الأساطير.", "هذا اليوم في كورة الإمارات", "أحداث من تاريخ الكورة الإماراتية لكل يوم في السنة، ومع كل حدث مصدره.", tdAll);

  { const d5 = APPROVED.daily5 && AID5[today.replace(/-/g, "")]; if (d5 && d5.items) ED.unshift(S.sec("أهم 5 أشياء اليوم", "", '<ol class="facts-l">' + d5.items.map(x => `<li>${esc(x)}</li>`).join("") + "</ol>")); }
  if (tdToday) ED.push(S.sec("هذا اليوم في كورة الإمارات", '<a href="/thisday/">كل الأيام</a>', tdToday));

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

  // ---- Arab-world pages (build_arabs.cjs): national teams, Arabs abroad, derbies, clashes, streaks, guide, archive…
  const AW = await require("./build_arabs.cjs")({ get, pool, write, page, urls, shelf, blocks, R, S, esc, index, teamsJson, teamPages, playerPages, matchPages:new Set(mids), NAMES_AR, fs, path, OUT, CACHE, H2H, BC });
  ED.push(["brk", "mow", "tonight", "streaks"].map(k => AW.home[k] || "").join("") + (AW.home.days || ""));
  writeHome();

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
    [["legends", "أساطير الكورة الإماراتية"], ["memorable", "مباريات ما تنتسى"], ["thisday", "هذا اليوم في كورة الإمارات"], ["laws", "قانون الكورة: التسلل، لمسة اليد، الفار"], ["watch", "وين تنقل المباريات"], ["stadiums", "دليل الملاعب"], ["week", "مباريات الأسبوع"], ["tv", "شاشة المجلس"], ["studio", "ستوديو التيفو"]].forEach(([k, n]) => add("r", k, n, "", `/${k}/`));
    AW.search.forEach(x => items.push(x.length > 4 ? x : x.concat(["", ""])));
    // W3.11: sublines go in one table ({s:[…], i:[[type, ar, latin, url, sub#, cc, kickoff?]]}); a latin equal to the Arabic is dropped
    const subs = [], si = new Map(); for (const it of items){ if (it[2] === it[1]) it[2] = ""; const s = it[4] || ""; if (!si.has(s)){ si.set(s, subs.length); subs.push(s); } it[4] = si.get(s); }
    const sj = JSON.stringify({ s:subs, i:items }); SEARCH_V = hash(sj); fs.writeFileSync(path.join(OUT, `assets/search.${SEARCH_V}.json`), sj); }

  // ---- 379: embeds for other sites (iframe): a league table and a live match, fetched from /v1, a link back to Tifo
  { const ehead = t => `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>${t}</title><style>@font-face{font-family:"Readex Pro";src:url(${FONTS.readex}) format("woff2");font-weight:400 600;font-display:swap}@font-face{font-family:"Barlow Condensed";src:url(${FONTS.barlow}) format("woff2");font-weight:700;font-display:swap}</style><style>:root{--ground:#0A2620;--text:#F6F7F2;--text-2:#B9C7C0;--text-3:#A7B6AF;--rule-2:#F6F7F214;--live-text:#5BE08F}body{margin:0;background:var(--ground);color:var(--text);font:400 14px "Readex Pro",system-ui,sans-serif}a{color:inherit;text-decoration:none}.w{padding:10px 12px}.h{display:flex;justify-content:space-between;align-items:center;font-weight:600;margin-bottom:6px}.h a{font-size:12px;color:var(--text-2)}table{width:100%;border-collapse:collapse}td,th{padding:6px 4px;border-bottom:1px solid var(--rule-2);text-align:center;font:700 15px "Barlow Condensed",sans-serif}th{font:400 11px "Readex Pro";color:var(--text-3)}td.t{text-align:start;font:400 14px "Readex Pro"}img{width:18px;height:18px;vertical-align:-4px;margin-inline-end:6px}.m{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:8px;text-align:center}.m img{width:44px;height:44px;display:block;margin:0 auto 6px}.s{font:700 44px "Barlow Condensed",sans-serif}.st{font-size:12px;color:var(--text-2)}.live{color:var(--live-text)}</style></head><body><div class="w" id="w">…</div>`;
    const erun = js => `<script>(function(){var W=document.getElementById("w"),q=new URLSearchParams(location.search),E=function(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});},L=function(t){return '<img src="/logo/'+t.id+'.png" alt="" onerror="this.style.display=\\'none\\'">';},N=function(t){return E(t.name_ar||t.name);};${js}})();</script></body></html>`;
    fs.mkdirSync(path.join(OUT, "embed/t"), { recursive:true }); fs.mkdirSync(path.join(OUT, "embed/m"), { recursive:true });
    fs.writeFileSync(path.join(OUT, "embed/t/index.html"), ehead("الترتيب | تيفو") + erun(`var c=+q.get("c");Promise.all([fetch("/v1/comp/"+c+"/standings.json").then(function(r){return r.json();}),fetch("/v1/index.json").then(function(r){return r.json();})]).then(function(d){var st=d[0],cc=(d[1].competitions||[]).filter(function(x){return x.id===c;})[0]||{};W.innerHTML='<div class="h"><span>'+E(cc.name_ar)+'</span><a href="https://tifo.elyoxe.com/c/'+E(cc.key)+'/" target="_blank" rel="noopener">على تيفو</a></div>'+(st.groups||[]).map(function(g){return (g.name&&st.groups.length>1?'<p class="st">'+E(g.name)+'</p>':'')+'<table><tr><th>#</th><th style="text-align:start">الفريق</th><th>لعب</th><th>الفارق</th><th>نقاط</th></tr>'+g.rows.map(function(r){return '<tr><td>'+r.rank+'</td><td class="t">'+L(r.team)+N(r.team)+'</td><td>'+r.played+'</td><td><bdi dir="ltr">'+r.gd+'</bdi></td><td>'+r.pts+'</td></tr>';}).join("")+'</table>';}).join("");}).catch(function(){W.textContent="ما قدرنا نحمّل الترتيب.";});`));
    fs.writeFileSync(path.join(OUT, "embed/m/index.html"), ehead("المباراة | تيفو") + erun(`var id=q.get("id");function go(){fetch("/v1/match/"+id+".json",{cache:"no-cache"}).then(function(r){return r.json();}).then(function(m){var live=m.status==="live"||m.status==="ht",s=m.score?m.score.home+" - "+m.score.away:(m.kickoff_uae||"").slice(11,16);W.innerHTML='<div class="h"><span>'+E(m.comp_name_ar||"")+'</span><a href="https://tifo.elyoxe.com/m/'+E(id)+'/" target="_blank" rel="noopener">على تيفو</a></div><div class="m"><div>'+L(m.home)+N(m.home)+'</div><div><div class="s'+(live?" live":"")+'"><bdi dir="ltr">'+E(s)+'</bdi></div><div class="st'+(live?" live":"")+'">'+(live?(m.status==="ht"?"استراحة":E(m.minute)+"'"):m.status==="finished"?"انتهت":"")+'</div></div><div>'+L(m.away)+N(m.away)+'</div></div>';if(live)setTimeout(go,30000);}).catch(function(){W.textContent="ما قدرنا نحمّل المباراة.";});}go();`)); }

  // W1.2e: warn (never fail) about competitions playing in the next 72 h with no channel row for some Arab countries
  { const soon = new Set([...matchSum.values()].filter(m => m.status === "scheduled" && Date.parse(m.kickoff_utc) - Date.now() < 72 * 3600e3 && Date.parse(m.kickoff_utc) > Date.now()).map(m => String(m.comp)));
    const gaps = [...soon].map(cid => [cid, R.COUNTRIES.filter(c => !(BCBY[c[0]] && BCBY[c[0]][cid] && BCBY[c[0]][cid].b.length)).length]).filter(x => x[1]);
    if (gaps.length) console.error("warn: channels missing in the next 72h: " + gaps.map(g => `${g[0]} (${g[1]}/22 countries)`).join(", ")); }

  OGJ.push({ key:"tifo", home:"تيفو", sub:"نتايج المباريات مباشر لكل العرب، بتوقيت بلدك", hc:["#0A2620", "#123A31"] });   // W1.10: the default share image

  // ---- 8. competitions list, robots, sitemap, 404
  const groups = [["uae", "الإمارات"], ["gulf", "الخليج"], ["asia", "آسيا"], ["africa", "أفريقيا"], ["national", "المنتخبات"], ["arab", "العرب"], ["europe", "أوروبا"], ["world", "العالم"]];
  { const byC = {}; comps.forEach(c => { const cc = c.country && c.country.iso2; if (cc && R.COUNTRIES.some(x => x[0] === cc)) (byC[cc] = byC[cc] || []).push(c); });
    const grp = (t, cs) => cs.length ? `<section class="rail cgrid3" data-slot="grid" data-iso="${(cs[0].country && cs[0].country.iso2) || ""}"><div class="rail-h"><h2>${t}</h2></div><div class="cts all">${cs.map(tileOf).join("")}</div></section>` : "";
    const lists = Object.keys(byC).sort((a, b) => R.COUNTRIES.findIndex(x => x[0] === a) - R.COUNTRIES.findIndex(x => x[0] === b)).map(cc => grp(esc(byC[cc][0].country.name_ar), byC[cc])).join("") + groups.map(g => grp(g[1], comps.filter(c => c.scope === g[0] && !(c.country && R.COUNTRIES.some(x => x[0] === c.country.iso2))))).join("");
    write("competitions/index.html", page({ v3:true, path:"/competitions/", page:"comps", nav:"comps", title:"كل البطولات | تيفو", desc:"كل البطولات اللي يغطيها تيفو: الإماراتية والخليجية والآسيوية والعربية والأوروبية.",
      body:`<section class="hero lhero" data-slot="hero"><div class="lgwall" aria-hidden="true">${comps.filter(c => LOGO(c.id)).slice(0, 24).map(c => `<img src="/lg/${c.id}.png" alt="" width="64" height="64">`).join("")}</div><div class="scrim"></div><div class="hero-in wrap"><p class="hk">تيفو</p><h1>البطولات</h1><p class="season">كل البطولات اللي نغطيها، <span class="num">${comps.length}</span> بطولة</p></div></section><div class="wrap body">${lists}</div>` })); }
  fs.mkdirSync(path.join(OUT, "og"), { recursive:true }); fs.writeFileSync(path.join(OUT, "og/jobs.json"), JSON.stringify(OGJ));
  try { process.stdout.write(require("child_process").execFileSync("python3", [path.join(__dirname, "og.py")]).toString()); } catch (e){ console.error("og.py failed", e.message); }
  // W1.9: internal links to pages this build did not write become plain text (reported, never fatal)
  { const SKIP = /^\/(v1|assets|logo|lg|og|audio|api|embed|next)\/|^\/(sw\.js|favicon\.svg|robots\.txt|sitemap\.xml)$|^\/cast\/(feed\.xml|cover\.jpg)$/; let dead = 0; const seen = {};
    for (const f of ALLP){ const h = fs.readFileSync(f, "utf8");
      const h2 = h.replace(/(<script\b[\s\S]*?<\/script>|<template\b[^>]*>)|<a\b([^>]*?)\shref="(\/[^"#?]*)(?:[?#][^"]*)?"([^>]*)>([\s\S]*?)<\/a>/g, (m, sc, pre, href, post, inner) => { if (sc) return m; if (SKIP.test(href) || WRITTEN.has(href) || WRITTEN.has(href.replace(/\/$/, ""))) return m; dead++; seen[href.split("/")[1]] = (seen[href.split("/")[1]] || 0) + 1; return `<span${pre}${post}>${inner}</span>`; });
      if (h2 !== h) fs.writeFileSync(f, h2); }
    if (dead) console.error(`warn: ${dead} links to pages that don't exist were unlinked (${Object.entries(seen).map(([k, n]) => "/" + k + "/ " + n).join(", ")})`);
    if (LEAKS) console.error(`warn: ${LEAKS} text nodes with null/undefined/raw keys were cleaned`);
    if (GRPS) console.error(`warn: ${GRPS} text nodes with «المجموعة A» / «Grp» were rewritten to ordinals (fix the source)`); }
  for (const f of ALLP){ const h = fs.readFileSync(f, "utf8"); if (h.includes("__SV__")) fs.writeFileSync(f, h.replace("__SV__", SEARCH_V)); }
  fs.writeFileSync(path.join(OUT, "sw.json"), JSON.stringify({ off:false }));
  // W3.6: installable (manifest in Arabic/RTL, maskable mark, shortcuts) and an offline page listing what this phone has cached
  fs.mkdirSync(path.join(OUT, "icons"), { recursive:true }); for (const f of fs.readdirSync(path.join(__dirname, "icons"))) fs.copyFileSync(path.join(__dirname, "icons", f), path.join(OUT, "icons", f));
  fs.writeFileSync(path.join(OUT, "manifest.webmanifest"), JSON.stringify({ name:"تيفو — مباريات اليوم مباشر", short_name:"تيفو", lang:"ar", dir:"rtl", start_url:"/?s=pwa", scope:"/", display:"standalone", background_color:"#0A2620", theme_color:"#0A2620",
    icons:[{ src:"/icons/icon-192.png", sizes:"192x192", type:"image/png" }, { src:"/icons/icon-512.png", sizes:"512x512", type:"image/png" }, { src:"/icons/maskable-512.png", sizes:"512x512", type:"image/png", purpose:"maskable" }],
    shortcuts:[{ name:"مباشر الحين", url:"/?s=pwa#matches" }, { name:"اليوم", url:"/today/?s=pwa" }] }));
  write("offline/index.html", page({ path:"/offline/", page:"offline", noindex:true, title:"ما في نت | تيفو", desc:"", body:'<h1>ما في نت الحين</h1><p class="season">هذي الصفحات اللي فتحتها قبل ومحفوظة في جوالك:</p><ul class="facts-l" id="offl"><li class="muted">نشوف المحفوظ…</li></ul>' }));   // W1.11: the service worker's kill switch
  fs.writeFileSync(path.join(OUT, "sw.js"), fs.readFileSync(path.join(__dirname, "src/sw.js"), "utf8").replace("__V__", ASSET_V));
  fs.writeFileSync(path.join(OUT, "robots.txt"), PREVIEW ? "User-agent: *\nDisallow: /\n" : `User-agent: *\nDisallow: /next/\nAllow: /\nSitemap: ${SITE}/sitemap.xml\n`);
  fs.writeFileSync(path.join(OUT, "sitemap.xml"), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` + urls.map(u => `<url><loc>${SITE}${u}</loc></url>`).join("\n") + "\n</urlset>\n");
  write("404.html", page({ path:"/404", page:"none", title:"الصفحة مب موجودة | تيفو", desc:"", body:'<h1>الصفحة مب موجودة</h1><p><a href="/">رجوع لمباريات اليوم</a></p>' }));
  fs.writeFileSync(path.join(OUT, ".pages"), String(urls.length));
  console.log(`built ${urls.length} pages: ${comps.length} competitions, ${tcount} teams, ${pcount} players, ${mids.length} matches (${D.size} with detail), logos ${logoIds.size} (${dl} new) in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
})().catch(e => { console.error(e); process.exit(1); });
