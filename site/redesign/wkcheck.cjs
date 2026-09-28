/* 417 «تيفو الأسبوع» card on /week/: prerendered, client-drawn, and 404 cases. node redesign/wkcheck.cjs [dir] [tag] */
"use strict";
const path = require("path"), fs = require("fs");
const { chromium } = require("/root/workspace/automation/browse/node_modules/playwright-core");
const ROOT = path.resolve(process.argv[2] || "out"), TAG = process.argv[3] || "new", DST = "/root/.claude/jobs/abd28f85/tmp";
const MIME = { ".html":"text/html; charset=utf-8", ".css":"text/css", ".js":"application/javascript", ".json":"application/json", ".png":"image/png", ".svg":"image/svg+xml", ".webp":"image/webp", ".woff2":"font/woff2" };
(async () => {
  const b = await chromium.launch({ executablePath:"/usr/bin/chromium", args:["--no-sandbox"] }), R = {}, errs = [];
  const run = async (name, w, opts) => { const ctx = await b.newContext({ viewport:{ width:w, height:900 }, serviceWorkers:"block", timezoneId:"Asia/Dubai" });
    await ctx.route(/^https:\/\/tifo\.elyoxe\.com\/(?!v1\/|api\/)/, r => { let p = new URL(r.request().url()).pathname; if (p.endsWith("/")) p += "index.html"; const f = path.join(ROOT, p);
      if (p === "/og/week-latest.json" && opts.json === 404) return r.fulfill({ status:404, body:"" });
      if (p === "/og/week-latest.json" && opts.json === "newer"){ const j = JSON.parse(fs.readFileSync(f, "utf8")); j.week = "2026-40"; j.items = j.items.slice(0, 2); return r.fulfill({ status:200, body:JSON.stringify(j), headers:{ "content-type":"application/json" } }); }
      let h = fs.existsSync(f) ? fs.readFileSync(f) : null; if (h && p === "/week/index.html" && opts.strip) h = Buffer.from(h.toString().replace(/<section class="blk wkcard"[\s\S]*?<\/section>/, ""));
      return h ? r.fulfill({ status:200, body:h, headers:{ "content-type":MIME[path.extname(f)] || "application/octet-stream" } }) : r.fulfill({ status:404, body:"" }); });
    await ctx.route(/^https:\/\/tifo\.elyoxe\.com\/api\//, r => r.fulfill({ status:204, body:"" }));
    const pg = await ctx.newPage(); pg.on("pageerror", e => errs.push(name + " " + e.message));
    const cls = []; await pg.addInitScript(() => { window.__cls = 0; new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type:"layout-shift", buffered:true }); });
    await pg.goto("https://tifo.elyoxe.com/week/", { waitUntil:"networkidle" }); await pg.waitForTimeout(1500);
    const card = await pg.$("#wkcard"); if (card && opts.shot){ await card.scrollIntoViewIfNeeded(); await pg.screenshot({ path:`${DST}/wk_${name}_${TAG}.png` }); }
    R[name] = await pg.evaluate(() => { const c = document.getElementById("wkcard"); return c ? { week:c.dataset.week, rows:c.querySelectorAll(".wkr").length, links:c.querySelectorAll("a.wkr").length, dl:[...c.querySelectorAll(".wkdl a")].map(a => a.textContent), cls:+window.__cls.toFixed(3) } : { card:false, cls:+window.__cls.toFixed(3) }; });
    await ctx.close(); };
  await run("prerendered390", 390, { shot:true }); await run("prerendered1440", 1440, { shot:true });
  await run("client", 390, { strip:true, shot:true }); await run("newer", 390, { json:"newer" }); await run("missing", 390, { strip:true, json:404 });
  R.errors = errs; console.log(JSON.stringify(R, null, 1)); await b.close();
})();
