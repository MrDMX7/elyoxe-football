/* Wave 4 functional check + screenshots on a local build (served at tifo.elyoxe.com, /v1 live from production).
   node redesign/w4check.cjs [dir] [tag] */
"use strict";
const path = require("path"), fs = require("fs");
const { chromium } = require("/root/workspace/automation/browse/node_modules/playwright-core");
const ROOT = path.resolve(process.argv[2] || "out"), TAG = process.argv[3] || "new", DST = "/root/.claude/jobs/abd28f85/tmp";
const MIME = { ".html":"text/html; charset=utf-8", ".css":"text/css", ".js":"application/javascript", ".json":"application/json", ".png":"image/png", ".svg":"image/svg+xml", ".webp":"image/webp", ".woff2":"font/woff2", ".webmanifest":"application/manifest+json" };
(async () => {
  const b = await chromium.launch({ executablePath:"/usr/bin/chromium", args:["--no-sandbox"] }), R = {};
  const ctx = await b.newContext({ viewport:{ width:390, height:844 }, serviceWorkers:"block", timezoneId:"Asia/Dubai" });
  await ctx.route(/^https:\/\/tifo\.elyoxe\.com\/(?!v1\/|api\/)/, r => { let p = new URL(r.request().url()).pathname; if (p.endsWith("/")) p += "index.html"; let f = path.join(ROOT, p); if (!fs.existsSync(f)) f = path.join(ROOT, "404.html"); return r.fulfill({ status:fs.existsSync(f) ? 200 : 404, body:fs.existsSync(f) ? fs.readFileSync(f) : "", headers:{ "content-type":MIME[path.extname(f)] || "application/octet-stream" } }); });
  await ctx.route(/^https:\/\/tifo\.elyoxe\.com\/api\//, r => r.fulfill({ status:204, body:"" }));
  const pg = await ctx.newPage(), errs = []; pg.on("pageerror", e => errs.push(pg.url() + " " + e.message));
  const T = async (name, fn) => { try { R[name] = await fn(); } catch (e){ R[name] = "ERR " + e.message.slice(0, 140); } };
  const shot = (n, o) => pg.screenshot(Object.assign({ path:`${DST}/w4_${n}_${TAG}.png` }, o || {}));
  const go = async (u, w) => { await pg.goto("https://tifo.elyoxe.com" + u, { waitUntil:"networkidle", timeout:90000 }); await pg.waitForTimeout(w || 1200); };
  await go("/"); await pg.evaluate(() => { localStorage.clear(); localStorage.setItem("tifo.country", "AE"); }); 
  await T("thisday", async () => { await go("/thisday/"); await shot("thisday"); const a = await pg.$eval("#tdh", e => e.textContent); await pg.click('[data-td="-1"]'); await pg.waitForTimeout(200); const b2 = await pg.$eval("#tdh", e => e.textContent); await pg.click('[data-td="1"]'); await pg.click('[data-td="1"]'); const c = await pg.$eval("#tdh", e => e.textContent); return [a, b2, c, (await pg.$$("details.tdm")).length + " months"]; });
  await T("round", async () => { await go("/c/uae-pro-league/r/5/"); const order = await pg.$$eval("main .pstats, main .rlist, main .m, main .story", l => l.slice(0, 3).map(x => x.className)); await pg.click("#stplay"); await pg.waitForTimeout(3200); await (await pg.$(".story")).scrollIntoViewIfNeeded(); await shot("round_play"); return { order, now:(await pg.$eval("#stnow", e => e.innerText.replace(/\s+/g, " "))).slice(0, 80) }; });
  await T("h2h", async () => { await go("/h2h/102101-102124/"); await shot("h2h"); return { next:!!(await pg.$(".h2hnext")), bar:await pg.$eval(".h2hbar", e => e.getAttribute("aria-label")), date:await pg.$eval(".h2hd", e => e.textContent) }; });
  await T("coach", async () => { await go("/coach/2642/"); return await pg.$eval(".scope", e => e.textContent).catch(() => "no scope line"); });
  await T("referee", async () => { await go("/r/1001073690/"); await shot("referee"); return { h1:await pg.$eval("h1", e => e.textContent), var:await pg.$$eval(".facts dt", l => l.map(x => x.textContent)), line:await pg.$eval(".h2hd", e => e.textContent) }; });
  await T("transfers", async () => { await go("/transfers/"); return { sel:await pg.$eval("#trf", s => s.value), shown:await pg.$$eval(".trl li:not([hidden])", l => l.length), more:await pg.$eval("#trmore", e => !e.hidden).catch(() => "none") }; });
  await T("page404", async () => { await go("/no-such-page/", 2500); await shot("404"); return { btn:!!(await pg.$("#srch404")), rows:await pg.$$eval("#day404 .m", l => l.length) }; });
  await T("ariaRows", async () => { await go("/", 2500); return await pg.$$eval("#day a.m[aria-label]", l => l.slice(0, 3).map(a => a.getAttribute("aria-label"))); });
  await T("liveRegion", async () => pg.$eval("#alive", e => e.getAttribute("aria-live")));
  await T("h1s", async () => { const h = await pg.$$eval("h1", l => l.map(x => x.textContent)); await go("/m/6040358/"); return [h, await pg.$$eval("h1", l => l.map(x => x.textContent))]; });
  await T("tabKeys", async () => { await go("/c/uae-pro-league/"); const first = await pg.$('.mtabs [role="tab"][tabindex="0"]'); await first.focus(); await pg.keyboard.press("ArrowLeft"); await pg.waitForTimeout(200); return await pg.evaluate(() => [document.activeElement.textContent, document.activeElement.getAttribute("aria-selected"), document.querySelectorAll('.mtabs [role="tab"][tabindex="0"]').length]); });
  await T("hscroll", async () => { const out = {}; for (const w of [390, 880, 1440]){ await pg.setViewportSize({ width:w, height:900 }); for (const u of ["/", "/thisday/", "/c/uae-pro-league/r/5/", "/h2h/102101-102124/", "/r/1001073690/", "/transfers/", "/c/uae-pro-league/", "/m/6040358/"]){ await go(u, 600); const x = await pg.evaluate(() => document.documentElement.scrollWidth - innerWidth); if (x > 0) out[w + u] = x; } } return Object.keys(out).length ? out : "none"; });
  await pg.setViewportSize({ width:390, height:844 }); await go("/", 1500); await shot("home_labels");
  R.errors = errs.slice(0, 8); console.log(JSON.stringify(R, null, 1)); await b.close();
})();
