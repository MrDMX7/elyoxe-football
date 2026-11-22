// node site/qa/site_qa.cjs [--per 12] [--out report.json] [--base https://tifo.elyoxe.com]
// The whole site at a phone's width (390 px), a sample of every page kind from the sitemaps plus the pages people open most:
// sideways overflow, stray text (undefined/null/NaN/[object/«اللقب … والعشرون»), broken images, empty sections, console errors,
// and the page's own internal links (each checked once). The owner, 22 Nov 2026: «جيك كل شي اختبر كل شي لين نوصل لنتيجة ان تيفو كامل
// بدون عيوب وسهل الاستخدام». Needs playwright-core and a Chrome (CHROME env, else the usual Windows/Linux paths).
"use strict";
const fs = require("fs");
const { chromium } = require(process.env.PW_CORE || "playwright-core");

const arg = (k, d) => { const i = process.argv.indexOf("--" + k); return i > 0 ? process.argv[i + 1] : d; };
const BASE = arg("base", "https://tifo.elyoxe.com"), PER = +arg("per", 12), OUT = arg("out", "site_qa.json"), ONLY = arg("only", "");
const CHROME = process.env.CHROME || ["C:/Program Files/Google/Chrome/Application/chrome.exe", "/opt/pw-browsers/chromium", "/usr/bin/google-chrome"].find(p => fs.existsSync(p));
const ALWAYS = ["/", "/today/", "/competitions/", "/c/uae-pro-league/", "/c/uae-pro-league/seasons/", "/c/premier-league/seasons/", "/c/laliga/seasons/",
  "/c/uae-pro-league/s/2024-2025/", "/c/premier-league/s/2015-2016/", "/c/laliga/s/1988-1989/", "/t/8650/", "/p/30981/", "/awards/", "/transfers/uae-pro-league/"];

// a page's kind from its path: /c/<key>/s/<season>/ is «c/*/s», /m/k12/ is «m/k», /p/123/ is «p»
function kind(path) {
  const p = path.replace(/^\/|\/$/g, "").split("/");
  if (!p[0]) return "home";
  if (p[0] === "c" && p.length > 2) return "c/*/" + p[2];
  if (["m", "p", "t"].includes(p[0]) && p.length > 1) return p[0] + (p[1].startsWith("k") ? "/k" : "") + (p.length > 2 ? "/" + p[2] : "");
  return p[0];
}

const STRAY = [/\bundefined\b/, /\bnull\b/, /\bNaN\b/, /\[object /, /اللقب (الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|[^\s]+ و[^\s]+ون)/,
  /\{\{|\}\}/, /&amp;[a-z]+;/, /\b\d+(st|nd|rd|th) title\b/i];

async function sitemapPaths() {
  const out = new Set(), get = async u => { try { const r = await fetch(u); return r.ok ? await r.text() : ""; } catch (e) { return ""; } };
  const idx = await get(BASE + "/robots.txt"), maps = [...idx.matchAll(/Sitemap:\s*(\S+)/g)].map(m => m[1]);
  for (const m of maps) for (const x of (await get(m)).matchAll(/<loc>([^<]+)<\/loc>/g)) out.add(x[1].replace(BASE, ""));
  return [...out];
}

function sample(paths) {
  const by = new Map();
  for (const p of paths) { const k = kind(p); if (!by.has(k)) by.set(k, []); by.get(k).push(p); }
  const pick = [];
  for (const [k, ps] of by) { const step = Math.max(1, Math.floor(ps.length / PER)); for (let i = 0; i < ps.length && pick.filter(x => kind(x) === k).length < PER; i += step) pick.push(ps[i]); }
  return [...new Set(ALWAYS.concat(pick))].filter(p => !ONLY || new RegExp(ONLY).test(p));
}

(async () => {
  const paths = sample(await sitemapPaths());
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, locale: "ar-AE" });
  const linkSeen = new Map(), results = [];
  const checkLink = async href => { if (linkSeen.has(href)) return linkSeen.get(href); let st = 0;
    try { st = (await fetch(BASE + href, { method: "HEAD", redirect: "manual" })).status; } catch (e) { st = -1; } linkSeen.set(href, st); return st; };
  for (const path of paths) {
    const page = await ctx.newPage(), errors = [];
    page.on("pageerror", e => errors.push(String(e.message || e).slice(0, 160)));
    let status = 0;
    try { const r = await page.goto(BASE + path, { waitUntil: "networkidle", timeout: 45000 }); status = r ? r.status() : 0; } catch (e) { errors.push("load: " + e.message.slice(0, 120)); }
    const m = await page.evaluate(() => {
      const iw = innerWidth, wide = [...document.querySelectorAll("main *")].filter(e => { const r = e.getBoundingClientRect(); return r.width > iw + 2 && getComputedStyle(e).overflowX !== "auto" && !e.closest("[style*='overflow'],.tblw,.hs,.chips,.seg"); })
        .slice(0, 4).map(e => e.tagName.toLowerCase() + "." + String(e.className).slice(0, 30) + " " + Math.round(e.getBoundingClientRect().width));
      const text = (document.querySelector("main") || document.body).innerText;
      const imgs = [...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.src && !i.src.startsWith("data:")).map(i => i.src).slice(0, 4);
      const empty = [...document.querySelectorAll("section.grp")].filter(s => !s.innerText.replace(/\s+/g, "").length || (s.querySelector(".card") && !s.querySelector(".card").innerText.trim())).length;
      const links = [...new Set([...document.querySelectorAll("main a[href^='/']")].map(a => a.getAttribute("href").split("#")[0]).filter(h => h && !h.startsWith("/v1/")))];
      return { sw: document.documentElement.scrollWidth, iw, wide, text, imgs, empty, links, title: document.title };
    }).catch(e => ({ err: e.message }));
    const stray = m.text ? STRAY.map(r => (m.text.match(r) || [])[0]).filter(Boolean) : [];
    const bad = [];
    for (const h of (m.links || []).slice(0, 60)) { const st = await checkLink(h); if (st >= 400 || st < 0) bad.push(`${h} ${st}`); }
    const r = { path, kind: kind(path), status, title: m.title, overflow: m.sw > m.iw + 2 ? m.sw - m.iw : 0, wide: m.wide || [], stray, imgs: m.imgs || [],
      empty: m.empty || 0, errors, badLinks: bad.slice(0, 8) };
    r.ok = status === 200 && !r.overflow && !r.wide.length && !stray.length && !r.imgs.length && !r.empty && !errors.length && !bad.length;
    results.push(r);
    process.stdout.write(`${r.ok ? "ok " : "BAD"} ${path}${r.ok ? "" : " " + JSON.stringify({ o: r.overflow, w: r.wide, s: stray, i: r.imgs.length, e: r.empty, x: errors.length, l: bad.length })}\n`);
    await page.close();
  }
  await browser.close();
  const sum = {}; for (const r of results) { sum[r.kind] = sum[r.kind] || { pages: 0, bad: 0 }; sum[r.kind].pages++; if (!r.ok) sum[r.kind].bad++; }
  fs.writeFileSync(OUT, JSON.stringify({ base: BASE, at: new Date().toISOString(), pages: results.length, bad: results.filter(r => !r.ok).length, kinds: sum, results }, null, 1));
  console.log(`\n${results.length} pages, ${results.filter(r => !r.ok).length} with defects -> ${OUT}`);
})();
