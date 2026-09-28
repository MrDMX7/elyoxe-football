/* Wave 4 batch B check: redirect stubs, national team pages, merged pages, lazy panes, lazy share.js. node redesign/w4bcheck.cjs [dir] [tag] */
"use strict";
const path = require("path"), fs = require("fs");
const { chromium } = require("/root/workspace/automation/browse/node_modules/playwright-core");
const ROOT = path.resolve(process.argv[2] || "out"), TAG = process.argv[3] || "new", DST = "/root/.claude/jobs/abd28f85/tmp";
const MIME = { ".html":"text/html; charset=utf-8", ".css":"text/css", ".js":"application/javascript", ".json":"application/json", ".png":"image/png", ".svg":"image/svg+xml", ".webp":"image/webp", ".woff2":"font/woff2" };
(async () => {
  const b = await chromium.launch({ executablePath:"/usr/bin/chromium", args:["--no-sandbox"] }), R = {};
  const ctx = await b.newContext({ viewport:{ width:390, height:844 }, serviceWorkers:"block", timezoneId:"Asia/Dubai" }); const loaded = [];
  await ctx.route(/^https:\/\/tifo\.elyoxe\.com\/(?!v1\/|api\/)/, r => { let p = new URL(r.request().url()).pathname; loaded.push(p); if (p.endsWith("/")) p += "index.html"; let f = path.join(ROOT, p); if (!fs.existsSync(f)) f = path.join(ROOT, "404.html"); return r.fulfill({ status:200, body:fs.readFileSync(f), headers:{ "content-type":MIME[path.extname(f)] || "application/octet-stream" } }); });
  await ctx.route(/^https:\/\/tifo\.elyoxe\.com\/api\//, r => r.fulfill({ status:204, body:"" }));
  const pg = await ctx.newPage(), errs = []; pg.on("pageerror", e => errs.push(pg.url() + " " + e.message));
  const T = async (name, fn) => { try { R[name] = await fn(); } catch (e){ R[name] = "ERR " + e.message.slice(0, 140); } };
  const shot = (n, o) => pg.screenshot(Object.assign({ path:`${DST}/w4b_${n}_${TAG}.png` }, o || {}));
  const go = async (u, w) => { await pg.goto("https://tifo.elyoxe.com" + u, { waitUntil:"networkidle", timeout:90000 }); await pg.waitForTimeout(w || 1200); };
  await go("/"); await pg.evaluate(() => { localStorage.clear(); localStorage.setItem("tifo.country", "MA"); localStorage.setItem("tifo.favs", JSON.stringify([{ t:"team", id:8696, n:"راسينغ سانتاندير" }, { t:"team", id:101918, n:"النصر" }])); });
  for (const [k, u] of [["uae", "/uae/"], ["natMA", "/national/ma/"], ["mow", "/match-of-week/"], ["w", "/w/"], ["year", "/year/"], ["academy", "/academy/"], ["uaeHash", "/uae/#squad"]]) await T("redir_" + k, async () => { await go(u, 1500); return pg.url().replace("https://tifo.elyoxe.com", "") + " | tab=" + (await pg.$eval('.mtabs [aria-selected="true"]', e => e.textContent).catch(() => "-")); });
  await T("natTabs", async () => { await go("/t/6262/#hist", 1500); await shot("nat_hist"); return { tabs:await pg.$$eval(".mtabs [role=tab]", l => l.map(x => x.textContent)), tiles:await pg.$$eval('[data-pane="hist"] .sht .tt2', l => l.map(x => x.textContent)), h1:await pg.$eval("h1", e => e.textContent) }; });
  await T("natTile", async () => { const t = await pg.$('[data-pane="hist"] .sht'); await t.click(); await pg.waitForTimeout(600); await shot("nat_tile"); const r = await pg.$eval("#panelt", e => e.textContent); await pg.keyboard.press("Escape"); return r; });
  await T("natLanding", async () => { await go("/national/", 2500); await shot("national"); return { me:await pg.$eval("#natmeb", e => e.innerText.replace(/\s+/g, " ").slice(0, 120)), first:await pg.$eval(".natflags a", e => e.textContent), flags:(await pg.$$(".natflags a")).length, now:!!(await pg.$("#natnow")) }; });
  await T("week", async () => { await go("/week/#mow", 2000); await shot("week_mow"); return { pin:!!(await pg.$("#mow")), cd:await pg.$eval("#mowcd", e => e.textContent).catch(() => "none"), ww:!!(await pg.$("#mow #wwbox")) }; });
  await T("tvMine", async () => { await go("/tv/?mine=1", 2500); await shot("tv_mine"); return { h1:await pg.$eval("h1", e => e.textContent), tiles:await pg.$$eval("#tv .tvt", l => l.length) }; });
  await T("calendars", async () => { await go("/calendars/#year", 1500); return await pg.$$eval(".shelf-h h3", l => l.map(x => x.textContent)); });
  await T("glossary", async () => { await go("/glossary/", 1200); return (await pg.$$(".gl .ex")).length + " examples"; });
  await T("lazyPanes", async () => { await go("/c/uae-pro-league/", 2000); const before = await pg.evaluate(() => document.querySelectorAll("*").length); const tpl = await pg.$$eval("template.lazyp", l => l.length);
    const b2 = await pg.$('[data-tabs="tv"] button:nth-child(2)'); let stamped = "no tv tabs"; if (b2){ await b2.click(); await pg.waitForTimeout(300); stamped = await pg.$$eval('[data-group="tv"]:not([hidden]) tr', l => l.length); }
    return { nodes:before, templates:tpl, rowsAfterClick:stamped }; });
  await T("lazyShare", async () => { loaded.length = 0; await go("/m/6052085/", 2000); const had = loaded.some(p => /\/share\./.test(p)); await pg.click('.hero [data-sheet="share"]'); await pg.waitForTimeout(800); const got = loaded.some(p => /\/share\./.test(p)); await pg.keyboard.press("Escape"); return { onLoad:had, afterSheet:got, lazy:await pg.evaluate(() => !window.TifoShare.lazy) }; });
  R.errors = errs.slice(0, 8); console.log(JSON.stringify(R, null, 1)); await b.close();
})();
