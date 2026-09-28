/* Batch D check (W2.5 home, W2.8 subtractions, W3.8 stakes, desktop match page). node redesign/wdcheck.cjs [dir] [tag] */
"use strict";
const path = require("path"), fs = require("fs");
const { chromium } = require("/root/workspace/automation/browse/node_modules/playwright-core");
const ROOT = path.resolve(process.argv[2] || "out"), TAG = process.argv[3] || "new", DST = "/root/.claude/jobs/abd28f85/tmp";
const MIME = { ".html":"text/html; charset=utf-8", ".css":"text/css", ".js":"application/javascript", ".json":"application/json", ".png":"image/png", ".svg":"image/svg+xml", ".webp":"image/webp", ".woff2":"font/woff2" };
(async () => {
  const b = await chromium.launch({ executablePath:"/usr/bin/chromium", args:["--no-sandbox"] }), R = {};
  const mk = async (w, h) => { const ctx = await b.newContext({ viewport:{ width:w, height:h }, serviceWorkers:"block", timezoneId:"Asia/Dubai" });
    await ctx.route(/^https:\/\/tifo\.elyoxe\.com\/(?!v1\/|api\/)/, r => { let p = new URL(r.request().url()).pathname; if (p.endsWith("/")) p += "index.html"; let f = path.join(ROOT, p); if (!fs.existsSync(f)) f = path.join(ROOT, "404.html"); return r.fulfill({ status:200, body:fs.readFileSync(f), headers:{ "content-type":MIME[path.extname(f)] || "application/octet-stream" } }); });
    await ctx.route(/^https:\/\/tifo\.elyoxe\.com\/api\//, r => r.fulfill({ status:204, body:"" })); await ctx.addInitScript(() => { try { localStorage.setItem("tifo.country", "AE"); } catch (e){} }); return ctx; };
  const errs = [], T = async (name, fn) => { try { R[name] = await fn(); } catch (e){ R[name] = "ERR " + e.message.slice(0, 140); } };
  for (const [w, h] of [[390, 844], [880, 1000], [1440, 900]]){ const ctx = await mk(w, h), pg = await ctx.newPage(); pg.on("pageerror", e => errs.push(pg.url() + " " + e.message));
    await pg.goto("https://tifo.elyoxe.com/", { waitUntil:"networkidle" }); await pg.waitForTimeout(1500); await pg.screenshot({ path:`${DST}/wd_home_${w}_${TAG}.png` });
    R["home" + w] = await pg.evaluate(() => { const hero = document.querySelector(".hero"), first = document.querySelector("main .body > section"); return { hero:Math.round(hero.getBoundingClientRect().height), firstRail:first && first.id, firstTop:first && Math.round(first.getBoundingClientRect().top), fold:innerHeight, rails:[...document.querySelectorAll("main .body > section.rail")].map(s => s.id || s.className).slice(0, 5) }; }); await ctx.close(); }
  const ctx = await mk(390, 844), pg = await ctx.newPage(); pg.on("pageerror", e => errs.push(pg.url() + " " + e.message));
  const go = async (u, w) => { await pg.goto("https://tifo.elyoxe.com" + u, { waitUntil:"networkidle", timeout:90000 }); await pg.waitForTimeout(w || 1200); };
  await T("more", async () => { await go("/"); await pg.click('.tabbar [data-sheet="more"]'); await pg.waitForTimeout(500); await pg.screenshot({ path:`${DST}/wd_more_${TAG}.png` }); return { entries:await pg.evaluate(() => document.querySelectorAll("#more .mctry button, #more .ml a").length + 1), ctry:await pg.$eval("#ctry", e => e.textContent), links:await pg.$$eval("#more .ml a", l => l.map(a => a.textContent)) }; });
  await pg.keyboard.press("Escape");
  await T("share", async () => { await go("/m/1000020522/"); await pg.click('.hero [data-sheet="share"]'); await pg.waitForTimeout(600); await pg.screenshot({ path:`${DST}/wd_share_${TAG}.png` }); return await pg.$$eval("#share .shr b", l => l.map(x => x.textContent)); });
  await pg.keyboard.press("Escape");
  await T("numFeat", async () => { await go("/c/uae-pro-league/#num"); const vis = await pg.$$eval('[data-pane="num"] .shelf3:not(.shmore) .sht', l => l.length); const btn = await pg.$eval("[data-shall]", b => b.textContent); await (await pg.$("[data-shall]")).scrollIntoViewIfNeeded(); await pg.screenshot({ path:`${DST}/wd_num_${TAG}.png` }); await pg.click("[data-shall]"); await pg.waitForTimeout(300); return { featured:vis, btn, after:await pg.$$eval('[data-pane="num"] .sht', l => l.filter(x => x.offsetParent).length) }; });
  await T("stakes", async () => { await go("/m/1000020530/"); const s = await pg.$("#stakes"); if (!s) return "no stakes"; await s.scrollIntoViewIfNeeded(); await pg.screenshot({ path:`${DST}/wd_stakes_${TAG}.png` }); return await pg.$$eval("#stakes li", l => l.map(x => x.textContent)); });
  await ctx.close();
  const c2 = await mk(1440, 900), p2 = await c2.newPage(); p2.on("pageerror", e => errs.push(p2.url() + " " + e.message));
  await T("desktop", async () => { await p2.goto("https://tifo.elyoxe.com/m/1000020530/", { waitUntil:"networkidle" }); await p2.waitForTimeout(1500); await p2.evaluate(() => window.scrollTo(0, 700)); await p2.waitForTimeout(400); await p2.screenshot({ path:`${DST}/wd_desktop_match_${TAG}.png` });
    return await p2.evaluate(() => { const s = document.querySelector(".mside"); return s ? { shown:getComputedStyle(s).display, width:Math.round(s.getBoundingClientRect().width), heads:[...s.querySelectorAll("h2")].map(h => h.textContent) } : "none"; }); });
  await c2.close();
  R.errors = errs.slice(0, 8); console.log(JSON.stringify(R, null, 1)); await b.close();
})();
