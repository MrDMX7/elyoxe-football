/* Wave 3 functional check + screenshots on a local build (served at tifo.elyoxe.com, /v1 live from production).
   node redesign/w3check.cjs [dir] [tag]  -> /root/.claude/jobs/abd28f85/tmp/w3_<name>_<tag>.png and a JSON summary */
"use strict";
const path = require("path"), fs = require("fs");
const { chromium } = require("/root/workspace/automation/browse/node_modules/playwright-core");
const ROOT = path.resolve(process.argv[2] || "out"), TAG = process.argv[3] || "new", DST = "/root/.claude/jobs/abd28f85/tmp";
const MIME = { ".html":"text/html; charset=utf-8", ".css":"text/css", ".js":"application/javascript", ".json":"application/json", ".png":"image/png", ".svg":"image/svg+xml", ".webp":"image/webp", ".woff2":"font/woff2", ".webmanifest":"application/manifest+json" };
(async () => {
  const b = await chromium.launch({ executablePath:"/usr/bin/chromium", args:["--no-sandbox"] }), R = {};
  const ctx = await b.newContext({ viewport:{ width:390, height:844 }, serviceWorkers:"block", timezoneId:"Asia/Dubai" });
  await ctx.route(/^https:\/\/tifo\.elyoxe\.com\/(?!v1\/|api\/)/, r => { let p = new URL(r.request().url()).pathname; if (p.endsWith("/")) p += "index.html"; const f = path.join(ROOT, p); return fs.existsSync(f) ? r.fulfill({ status:200, body:fs.readFileSync(f), headers:{ "content-type":MIME[path.extname(f)] || "application/octet-stream" } }) : r.fulfill({ status:404, body:"" }); });
  await ctx.route(/^https:\/\/tifo\.elyoxe\.com\/api\//, r => r.fulfill({ status:204, body:"" }));
  const pg = await ctx.newPage(), errs = []; pg.on("pageerror", e => errs.push(pg.url() + " " + e.message));
  const T = async (name, fn) => { try { R[name] = await fn(); } catch (e){ R[name] = "ERR " + e.message.slice(0, 120); } };
  const shot = (n, o) => pg.screenshot(Object.assign({ path:`${DST}/w3_${n}_${TAG}.png` }, o || {}));
  const go = async (u, w) => { await pg.goto("https://tifo.elyoxe.com" + u, { waitUntil:"networkidle", timeout:90000 }); await pg.waitForTimeout(w || 1500); };
  // فريقك: no favourites (UAE visitor) -> national team + league, then with a favourite club
  await go("/"); await pg.evaluate(() => { localStorage.clear(); localStorage.setItem("tifo.country", "AE"); localStorage.setItem("tifo.seen", String(Date.now() - 2 * 864e5)); }); await go("/", 2500);
  await T("mineFallback", async () => { const el = await pg.$("#r-mine"); await el.scrollIntoViewIfNeeded(); await pg.waitForTimeout(600); await el.screenshot({ path:`${DST}/w3_mine_fallback_${TAG}.png` }); return await pg.$eval("#mine", e => e.innerText.replace(/\s+/g, " ").slice(0, 200)); });
  await pg.evaluate(() => { localStorage.setItem("tifo.favs", JSON.stringify([{ t:"team", id:8696, n:"راسينغ سانتاندير" }, { t:"team", id:101918, n:"النصر" }])); localStorage.setItem("tifo.mine", "8696"); localStorage.setItem("tifo.lastvisit", String(Date.now() - 3 * 864e5)); sessionStorage.clear(); });
  await go("/", 2500);
  await T("mineFavs", async () => { const el = await pg.$("#r-mine"); await el.scrollIntoViewIfNeeded(); await pg.waitForTimeout(600); await el.screenshot({ path:`${DST}/w3_mine_favs_${TAG}.png` }); return await pg.$eval("#mine", e => e.innerText.replace(/\s+/g, " ").slice(0, 260)); });
  // search: empty state, then context sublines
  await T("searchEmpty", async () => { await pg.evaluate(() => window.scrollTo(0, 0)); await pg.click("#srch"); await pg.waitForTimeout(900); await shot("search_empty"); return await pg.$eval("#sr", e => e.innerText.replace(/\s+/g, " ").slice(0, 160)); });
  await T("searchNasr", async () => { await pg.fill("#sq", "النصر"); await pg.waitForTimeout(700); await shot("search_nasr"); return await pg.$$eval("#sr li", l => l.slice(0, 4).map(x => x.innerText.replace(/\s+/g, " "))); });
  await T("searchMatch", async () => { await pg.fill("#sq", "الجزائر"); await pg.waitForTimeout(700); await shot("search_match"); return await pg.$$eval("#sr li", l => l.slice(0, 4).map(x => x.innerText.replace(/\s+/g, " "))); });
  await T("searchNick", async () => { await pg.fill("#sq", "العالمي"); await pg.waitForTimeout(700); return await pg.$$eval("#sr li", l => l.slice(0, 2).map(x => x.innerText.replace(/\s+/g, " "))); });
  await T("searchCoach", async () => { await pg.fill("#sq", "مدرب"); await pg.waitForTimeout(500); await pg.fill("#sq", "والتر"); await pg.waitForTimeout(700); return await pg.$$eval("#sr li", l => l.slice(0, 3).map(x => x.innerText.replace(/\s+/g, " "))); });
  await pg.keyboard.press("Escape");
  // install sheet (no beforeinstallprompt in headless: open it directly) + footer promise
  await T("installSheet", async () => { await pg.evaluate(() => { const a = document.createElement("button"); a.dataset.sheet = "inst"; a.id = "tstinst"; document.body.appendChild(a); }); await pg.click("#tstinst", { force:true }); await pg.waitForTimeout(500); await shot("install_sheet"); const t = await pg.$eval("#inst", e => e.innerText.replace(/\s+/g, " ")); await pg.keyboard.press("Escape"); return t.slice(0, 160); });
  await T("footerNoBet", async () => pg.$eval(".foot .nobet", e => e.textContent));
  await T("manifest", async () => pg.evaluate(() => fetch("/manifest.webmanifest").then(r => r.json()).then(j => j.short_name + " " + j.dir + " " + j.shortcuts.length + " shortcuts, " + j.icons.length + " icons")));
  // prayer line on a scheduled match (UAE visitor, Abu Dhabi) + its layout shift
  await pg.evaluate(() => { localStorage.setItem("tifo.country", "AE"); localStorage.removeItem("tifo.city"); });
  await T("prayer", async () => { await go("/m/6040358/", 2500); await shot("prayer_hero"); return await pg.$$eval(".prayl", l => l.map(x => x.textContent)); });
  await T("prayerCLS", async () => { const p2 = await ctx.newPage(); await p2.addInitScript(() => { window.__cls = 0; new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type:"layout-shift", buffered:true }); });
    await p2.goto("https://tifo.elyoxe.com/m/6040358/", { waitUntil:"networkidle", timeout:90000 }); await p2.waitForTimeout(2500); const v = await p2.evaluate(() => window.__cls); await p2.close(); return +v.toFixed(3); });
  // team: the lineup builder on the pitch, hosted in اللاعبين; calendar link in the hero
  await go("/t/102124/", 2000);
  await T("calLink", async () => pg.$eval(".hero #ics", a => a.getAttribute("href")));
  await T("xi", async () => { await pg.click('.mtabs button[data-t="squad"]'); await pg.waitForTimeout(300); await pg.click("#xibtn"); await pg.waitForTimeout(1500); await shot("xi_pitch");
    await pg.click('.xs[data-s="0"]'); await pg.waitForTimeout(400); await shot("xi_picker"); await pg.click(".xpick [data-p]"); await pg.waitForTimeout(300);
    await pg.click('.xs[data-s="5"]'); await pg.waitForTimeout(300); await pg.click(".xpick li:nth-child(3) [data-p]"); await pg.waitForTimeout(300); await shot("xi_picked");
    return (await pg.$$eval(".xpitch .xs", s => s.length)) + " squares, " + (await pg.$$eval(".xpitch .xs.on", s => s.length)) + " picked, saved=" + !!(await pg.evaluate(() => localStorage.getItem("tifo.xi.102124"))); });
  await pg.keyboard.press("Escape");
  // /arabs/ front, /arabs/europe/
  await T("arabs", async () => { await go("/arabs/", 2000); await shot("arabs", { fullPage:true }); return await pg.$$eval(".agc", l => l.map(x => x.innerText.replace(/\s+/g, " ").slice(0, 70))); });
  await T("europe", async () => { await go("/arabs/europe/", 1500); await shot("europe"); return (await pg.$$eval("tr[data-c]", r => r.length)) + " rows"; });
  // leaders: الأعلى تقييم + الحراس
  await T("leaders", async () => { await go("/c/uae-pro-league/", 2000); const segs = await pg.$$eval('[data-tabs="lead"] button', l => l.map(x => x.textContent));
    const tab = await pg.$('[data-tabs="lead"]'); if (!tab) return segs; const pane = await pg.evaluate(() => { const s = document.querySelector('[data-tabs="lead"]').closest("[data-pane]"); return s ? s.dataset.pane : ""; });
    if (pane){ const tb = await pg.$('.mtabs button[data-t="' + pane + '"]'); if (tb) await tb.click(); } await pg.waitForTimeout(400);
    await pg.click('[data-tabs="lead"] button[data-t="rated"]'); await pg.waitForTimeout(300); await (await pg.$('[data-tabs="lead"]')).scrollIntoViewIfNeeded(); await shot("leaders_rated"); return segs; });
  await T("offline", async () => { await go("/offline/", 800); await shot("offline"); return await pg.$eval("#offl", e => e.innerText.slice(0, 80)); });
  await T("hscroll", async () => { const out = {}; for (const w of [390, 880, 1440]){ await pg.setViewportSize({ width:w, height:900 }); for (const u of ["/", "/arabs/", "/arabs/europe/", "/t/102124/", "/m/6040358/", "/offline/"]){ await go(u, 700); const x = await pg.evaluate(() => document.documentElement.scrollWidth - innerWidth); if (x > 0) out[w + u] = x; } } return Object.keys(out).length ? out : "none"; });
  R.errors = errs.slice(0, 8);
  console.log(JSON.stringify(R, null, 1)); await b.close();
})();
