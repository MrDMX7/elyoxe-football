/* Live check for a match page of a local build: served at tifo.elyoxe.com (routes), /v1 from production.
   Counts /v1/match/<id>.json and /v1/live.json requests over WAIT ms, and reports whether #mh / mini-bar got painted. */
const path = require("path"), fs = require("fs");
const { chromium } = require("/root/workspace/automation/browse/node_modules/playwright-core");
const ROOT = path.resolve(process.argv[2] || "out"), ID = process.argv[3] || "6052085", WAIT = +(process.argv[4] || 30000);
const MIME = { ".html":"text/html; charset=utf-8", ".css":"text/css", ".js":"application/javascript", ".json":"application/json", ".png":"image/png", ".svg":"image/svg+xml" };
(async () => {
  const b = await chromium.launch({ executablePath:"/usr/bin/chromium", args:["--no-sandbox"] });
  const ctx = await b.newContext({ viewport:{ width:390, height:844 }, serviceWorkers:(process.env.SW || "block") });
  await ctx.route(/^https:\/\/tifo\.elyoxe\.com\/(?!v1\/)/, r => { let p = new URL(r.request().url()).pathname; if (p.endsWith("/")) p += "index.html"; const f = path.join(ROOT, p); return fs.existsSync(f) ? r.fulfill({ status:200, body:fs.readFileSync(f), headers:{ "content-type":MIME[path.extname(f)] || "application/octet-stream" } }) : r.continue(); });
  const pg = await ctx.newPage(), hits = { match:0, live:0 }, errs = [];
  pg.on("request", q => { const u = q.url(); if (u.includes("/v1/match/" + ID + ".json")) hits.match++; if (u.includes("/v1/live.json")) hits.live++; });
  pg.on("pageerror", e => errs.push(e.message));
  await pg.goto(`https://tifo.elyoxe.com/m/${ID}/`, { waitUntil:"networkidle" }); await pg.waitForTimeout(WAIT);
  const st = await pg.evaluate(() => ({ score:(document.querySelector("#mh .sc .dg") || {}).textContent, mini:!!document.querySelector("#mini .ms"), tab:(document.querySelector('.mtabs [data-t="events"]') || {}).textContent, sw:navigator.serviceWorker && navigator.serviceWorker.controller ? "controlled" : "registered-or-none" }));
  console.log(JSON.stringify({ hits, st, errs }));
  await b.close();
})();
