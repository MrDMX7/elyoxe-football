/* Screenshots of the /next/ prototype without uploading: pages are requested at https://tifo.elyoxe.com/next/… and served
   from out_next/next by page.route, so /v1 data and root crests stay live same-origin. One browser, closed at the end.
   node redesign/shots.cjs [tag] [page-key ...]   -> /root/.claude/jobs/abd28f85/tmp/next_<key>_<w>[_<tag>].png */
"use strict";
const path = require("path"), fs = require("fs");
const { chromium } = require("/root/workspace/automation/browse/node_modules/playwright-core");
const ROOT = path.join(__dirname, "../out_next/next"), DST = "/root/.claude/jobs/abd28f85/tmp";
const PAGES = { home:"/next/", match:"/next/m/1000020522/", live:"/next/m/6052085/", comp:"/next/c/uae-pro-league/", saudi:"/next/c/saudi-pro-league/", pl:"/next/c/premier-league/", comps:"/next/competitions/" };
if (process.env.PAGES) for (const k of Object.keys(PAGES)) delete PAGES[k]; (process.env.PAGES || "").split(",").filter(Boolean).forEach(x => { PAGES[x] = "/next/c/" + x + "/"; });
const W = process.env.W ? process.env.W.split(",").map(Number) : [390, 880, 1440], tag = process.argv[2] && process.argv[2] !== "-" ? "_" + process.argv[2] : "", only = process.argv.slice(3);
const MIME = { ".html":"text/html; charset=utf-8", ".css":"text/css", ".js":"application/javascript", ".json":"application/json", ".png":"image/png", ".txt":"text/plain" };
(async () => {
  const b = await chromium.launch({ executablePath:"/usr/bin/chromium", args:["--no-sandbox", "--disable-dev-shm-usage"] });
  const report = [];
  try {
    for (const w of W){
      const ctx = await b.newContext({ viewport:{ width:w, height:w < 500 ? 844 : w < 1000 ? 1000 : 900 }, deviceScaleFactor:1, locale:"ar-AE", timezoneId:"Asia/Dubai", serviceWorkers:"block" });
      await ctx.route("https://tifo.elyoxe.com/next/**", async r => { let p = new URL(r.request().url()).pathname.replace(/^\/next/, ""); if (p.endsWith("/")) p += "index.html"; const f = path.join(ROOT, p); if (fs.existsSync(f)) return r.fulfill({ status:200, body:fs.readFileSync(f), headers:{ "content-type":MIME[path.extname(f)] || "application/octet-stream" } }); return r.fulfill({ status:404, body:"nf" }); });
      for (const [k, u] of Object.entries(PAGES)){
        if (only.length && !only.includes(k)) continue;
        const pg = await ctx.newPage(), errs = []; pg.on("pageerror", e => errs.push(e.message)); pg.on("response", r => { if (r.status() >= 400) errs.push(r.status() + " " + r.url()); });
        await pg.goto("https://tifo.elyoxe.com" + u, { waitUntil:"networkidle", timeout:60000 }).catch(e => errs.push("goto " + e.message));
        await pg.waitForTimeout(2000); await pg.screenshot({ path:`${DST}/next_${k}_${w}${tag}.png` }); await pg.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 500){ window.scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); } window.scrollTo(0, 0); }); await pg.waitForTimeout(600);
        const m = await pg.evaluate(() => ({ sw:document.documentElement.scrollWidth, cw:document.documentElement.clientWidth, h:document.documentElement.scrollHeight, over:[...document.querySelectorAll("body *")].filter(e => { const r = e.getBoundingClientRect(); return r.width && (r.right > document.documentElement.clientWidth + 1 || r.left < -1) && !e.closest(".rail-s,.cts,.tblwrap,.seg,.chips,.tabs,.mine-card,.sheet,.panel,[hidden]"); }).slice(0, 5).map(e => e.tagName + "." + e.className + " " + Math.round(e.getBoundingClientRect().left) + ".." + Math.round(e.getBoundingClientRect().right)) }));
        await pg.screenshot({ path:`${DST}/next_${k}_${w}_full${tag}.png`, fullPage:true });
        if (process.env.ACT){   // interaction states: panel, sheet, mini-bar
          const act = async (n, fn) => { try { await fn(); await pg.waitForTimeout(700); await pg.screenshot({ path:`${DST}/next_${k}_${w}_${n}${tag}.png` }); await pg.keyboard.press("Escape"); await pg.waitForTimeout(300); } catch (e){ errs.push("act " + n + " " + e.message.slice(0, 80)); } };
          if (k === "comp" || k === "saudi"){ await act("numtab", async () => { await pg.click('.mtabs [data-t="num"]'); await pg.evaluate(() => window.scrollTo(0, document.querySelector(".mtabs").offsetTop - 40)); }); await act("panel", async () => { await pg.click('.mtabs [data-t="num"]'); await pg.click("[data-pane=num] .sht"); }); }
          if (k === "match" || k === "live"){ await act("sheet", async () => { await pg.click('.hero [data-sheet="share"]'); }); await act("scrolled", async () => { await pg.click('.mtabs [data-t="ana"]'); await pg.evaluate(() => window.scrollTo(0, 700)); }); await act("lineups", async () => { await pg.click('.mtabs [data-t="lineups"]'); await pg.evaluate(() => window.scrollTo(0, 600)); }); }
          if (k === "home"){ await act("more", async () => { await pg.click('[data-sheet="more"]:visible'); }); await act("edpanel", async () => { await pg.click(".edr .ed[data-open]"); }); await act("rails", async () => { await pg.evaluate(() => window.scrollTo(0, document.querySelector("#r-today").offsetTop - 80)); }); }
        }
        report.push({ k, w, hscroll:m.sw > m.cw, height:m.h, over:m.over, errs:errs.slice(0, 4) });
        await pg.close();
      }
      await ctx.close();
    }
  } finally { await b.close(); }
  console.log(JSON.stringify(report, null, 0).replace(/\},\{/g, "},\n{"));
})();
