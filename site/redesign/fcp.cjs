/* 386 gate: first render (FCP) on a mid-range phone profile — CPU x4 slower, 12 Mbps / 60 ms RTT — from a gzip server
   of the local build (as CloudFront serves it). Median of 3 runs per page; exits 1 if any page is at 1000 ms or more.
   node redesign/fcp.cjs [dir] [/path ...] */
"use strict";
const http = require("http"), fs = require("fs"), path = require("path"), zlib = require("zlib");
const { chromium } = require("/root/workspace/automation/browse/node_modules/playwright-core");
const ROOT = path.resolve(process.argv[2] || "out"), PAGES = process.argv.slice(3).length ? process.argv.slice(3) : ["/", "/m/6052085/", "/c/uae-pro-league/", "/t/5789/"];
const MIME = { ".html":"text/html; charset=utf-8", ".css":"text/css", ".js":"application/javascript", ".json":"application/json", ".png":"image/png", ".svg":"image/svg+xml" };
const srv = http.createServer((q, r) => { let p = decodeURIComponent(q.url.split("?")[0]); if (p.endsWith("/")) p += "index.html"; const f = path.join(ROOT, p);
  if (!f.startsWith(ROOT) || !fs.existsSync(f)){ r.writeHead(404); return r.end(); } const ext = path.extname(f), b = fs.readFileSync(f);
  if (/html|css|javascript|json|svg/.test(MIME[ext] || "")){ r.writeHead(200, { "content-type":MIME[ext], "content-encoding":"gzip" }); r.end(zlib.gzipSync(b)); } else { r.writeHead(200, { "content-type":MIME[ext] || "application/octet-stream" }); r.end(b); } });
srv.listen(8803, async () => {
  const b = await chromium.launch({ executablePath:"/usr/bin/chromium", args:["--no-sandbox"] }); const res = {}, ext = {}, warns = []; let bad = 0;
  try {
    for (const p of PAGES){ const xs = [];
      for (let i = 0; i < 3; i++){
        const ctx = await b.newContext({ viewport:{ width:412, height:823 }, serviceWorkers:"block" }), pg = await ctx.newPage(), cdp = await ctx.newCDPSession(pg);
        // W4.7: LCP, CLS and blocking time too (long tasks over 50 ms, summed past 50 ms each, from FCP to load + 2.5 s)
        await pg.addInitScript(() => { window.__m = { lcp:0, cls:0, tbt:0 }; try { new PerformanceObserver(l => { for (const e of l.getEntries()) window.__m.lcp = e.startTime; }).observe({ type:"largest-contentful-paint", buffered:true });
          new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__m.cls += e.value; }).observe({ type:"layout-shift", buffered:true });
          new PerformanceObserver(l => { const f = (performance.getEntriesByName("first-contentful-paint")[0] || {}).startTime || 0; for (const e of l.getEntries()) if (e.startTime >= f && e.duration > 50) window.__m.tbt += e.duration - 50; }).observe({ type:"longtask", buffered:true }); } catch (e){} });
        await cdp.send("Network.enable"); await cdp.send("Network.emulateNetworkConditions", { offline:false, latency:60, downloadThroughput:12e6 / 8, uploadThroughput:3e6 / 8 }); await cdp.send("Emulation.setCPUThrottlingRate", { rate:4 });
        await pg.route(/fonts\.(googleapis|gstatic)|cdn\.jsdelivr|\/v1\//, r => r.abort());   // third parties and live data are outside first render
        await pg.goto("http://127.0.0.1:8803" + p, { waitUntil:"load" }); await pg.waitForTimeout(2500);
        xs.push(await pg.evaluate(() => [Math.round((performance.getEntriesByName("first-contentful-paint")[0] || {}).startTime || -1), Math.round(window.__m.lcp), +window.__m.cls.toFixed(3), Math.round(window.__m.tbt)])); await ctx.close();
      }
      const med = k => xs.map(x => x[k]).sort((a, c) => a - c)[1]; res[p] = med(0); ext[p] = { lcp:med(1), cls:med(2), tbt:med(3) }; if (!(res[p] > 0 && res[p] < 1000)) bad++;
      const w = [ext[p].lcp > 2500 && "LCP " + ext[p].lcp + " ms", ext[p].cls > 0.05 && "CLS " + ext[p].cls, ext[p].tbt > 300 && "TBT " + ext[p].tbt + " ms"].filter(Boolean); if (w.length) warns.push(p + ": " + w.join(", "));
    }
  } finally { await b.close(); srv.close(); }
  console.log("fcp(ms, median of 3):", JSON.stringify(res), bad ? "FAIL" : "PASS"); console.log("lcp/cls/tbt (median):", JSON.stringify(ext)); if (warns.length) console.log("warn (never blocks a deploy): " + warns.join(" | ")); process.exitCode = bad ? 1 : 0;
});
