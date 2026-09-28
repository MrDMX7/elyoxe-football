/* QA flows on PRODUCTION tifo.elyoxe.com at 390x844 DPR1. Read-only: POST /api/** is answered 204 locally (no analytics pollution,
   no push subscription); notifications are never granted; .ptg toggles never clicked.
   node flows.cjs [onlyFlow,...]  -> qa/flows.json + qa/flows/*.png */
"use strict";
const fs = require("fs");
const { chromium } = require("/root/workspace/automation/browse/node_modules/playwright-core");
const QA = "/root/.claude/jobs/abd28f85/tmp/qa", SHOT = QA + "/flows_local", OUT = QA + "/flows_local.json", LOCAL = process.env.LOCAL, path = require("path"), SITE = "https://tifo.elyoxe.com";
const ONLY = (process.argv[2] || "").split(",").filter(Boolean);
const flows = fs.existsSync(OUT) && ONLY.length ? JSON.parse(fs.readFileSync(OUT, "utf8")) : [];
const save = () => fs.writeFileSync(OUT, JSON.stringify(flows, null, 1));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const clean = s => String(s || "").replace(/\s+/g, " ").trim();

(async () => {
  const b = await chromium.launch({ executablePath:"/usr/bin/chromium", args:["--no-sandbox", "--disable-dev-shm-usage"] });
  try { fs.writeFileSync(QA + "/_scripts/flows.pid", String(b.process().pid)); } catch (e){}
  const blocked = [];
  const mk = async (sw) => {
    const ctx = await b.newContext({ viewport:{ width:390, height:844 }, deviceScaleFactor:1, locale:"ar-AE", timezoneId:"Asia/Dubai", serviceWorkers:sw ? "allow" : "block", isMobile:false, hasTouch:true });
    await ctx.route(/^https:\/\/tifo\.elyoxe\.com\/api\//, r => { const q = r.request(), p = new URL(q.url()).pathname;
      if (q.method() !== "GET" || /push\/sub/.test(p)){ blocked.push(q.method() + " " + p); return r.fulfill({ status:204, body:"" }); } return r.continue(); });
    // local build: every non-/v1, non-/api request is answered from LOCAL (the built out/ dir); /v1 stays production
    if (LOCAL) await ctx.route(/^https:\/\/tifo\.elyoxe\.com\/(?!v1\/|api\/)/, r => { const MIME = { ".html":"text/html; charset=utf-8", ".css":"text/css", ".js":"application/javascript", ".json":"application/json", ".png":"image/png", ".svg":"image/svg+xml", ".webp":"image/webp", ".woff2":"font/woff2", ".webmanifest":"application/manifest+json" };
      let p = new URL(r.request().url()).pathname; if (p.endsWith("/")) p += "index.html"; let f = path.join(LOCAL, decodeURIComponent(p)); let st = 200; if (!fs.existsSync(f)){ f = path.join(LOCAL, "404.html"); st = 404; }
      return r.fulfill({ status:st, body:fs.readFileSync(f), headers:{ "content-type":MIME[path.extname(f)] || "application/octet-stream" } }); });
    return ctx; };
  // one page per flow with its own collectors
  const run = async (ctx, name, fn) => {
    if (ONLY.length && !ONLY.includes(name)) return;
    const pg = await ctx.newPage(), ce = [], fr = [], t0 = Date.now();
    pg.on("console", m => { if (m.type() === "error") ce.push(clean(m.text()).slice(0, 300) + " @" + pg.url().replace(SITE, "")); });
    pg.on("pageerror", e => ce.push("pageerror: " + clean(e.message).slice(0, 300) + " @" + pg.url().replace(SITE, "")));
    pg.on("response", r => { if (r.status() >= 400) fr.push(r.status() + " " + r.url().replace(SITE, "") + (r.request().isNavigationRequest() ? " (document)" : "")); });
    pg.on("requestfailed", q => { const f = q.failure() && q.failure().errorText; if (f === "net::ERR_ABORTED" && /\/v1\//.test(q.url())) fr.push("aborted " + q.url().replace(SITE, "")); else fr.push("failed " + f + " " + q.url().replace(SITE, "")); });
    let res; try { res = await fn(pg, ctx); } catch (e){ res = { pass:false, error:clean(e.message).slice(0, 400) }; }
    const rec = Object.assign({ flow:name, status:res.pass === true ? "PASS" : res.pass === "warn" ? "WARN" : "FAIL" }, res, { console_errors:ce, failed_requests:fr, seconds:Math.round((Date.now() - t0) / 100) / 10 });
    delete rec.pass; const i = flows.findIndex(f => f.flow === name); if (i >= 0) flows[i] = rec; else flows.push(rec); save();
    console.log(rec.status, name, JSON.stringify(res).slice(0, 300));
    await pg.close().catch(() => {});
  };
  const go = async (pg, u, w) => { await pg.goto(SITE + u, { waitUntil:"load", timeout:45000 }); await pg.waitForLoadState("networkidle", { timeout:10000 }).catch(() => {}); await sleep(w || 1200); };
  const shot = (pg, n) => pg.screenshot({ path:`${SHOT}/${n}.png` }).catch(() => {});
  const vis = (pg, sel) => pg.evaluate(s => { const e = document.querySelector(s); return !!(e && !e.hidden && e.offsetParent !== null || (e && getComputedStyle(e).position === "fixed" && !e.hidden)); }, sel);

  // ---------------- context A: stateless UI flows (SW blocked) ----------------
  let ctx = await mk(false);
  await run(ctx, "more_sheet", async pg => {
    await go(pg, "/"); await pg.click('.tabbar [data-sheet="more"]'); await sleep(700); await shot(pg, "more_sheet");
    const r = await pg.evaluate(async () => { const m = document.querySelector("#more"), vis = x => !!(x && !x.hidden && x.getClientRects().length);
      const links = [...m.querySelectorAll(".ml a")].map(a => ({ t:a.textContent.trim(), h:a.getAttribute("href") })), sw = [...m.querySelectorAll(".mswitch button")].filter(vis).map(x => x.textContent.trim());
      const st = await Promise.all(links.map(l => fetch(l.h, { method:"HEAD" }).then(r => r.status).catch(() => 0)));
      return { open:vis(m), ctry:m.querySelectorAll("#ctry").length, ctryText:(m.querySelector("#ctry") || {}).textContent, links:links.map((l, i) => l.t + " " + l.h + " " + st[i]), switchRow:sw, bad:links.filter((l, i) => st[i] !== 200).map(l => l.h) }; });
    const entries = r.ctry + r.links.length + (r.switchRow.length ? 1 : 0);
    return Object.assign({ pass:r.open && entries === 14 && !r.bad.length, entries, expected:14 }, r, { shot:SHOT + "/more_sheet.png" }); });

  await run(ctx, "back_closes_sheet", async pg => {
    await go(pg, "/"); const u0 = pg.url(); await pg.click('.tabbar [data-sheet="more"]'); await sleep(600); const before = await vis(pg, "#more");
    await pg.evaluate(() => history.back()); await sleep(900);
    const after = await pg.evaluate(() => ({ moreHidden:document.querySelector("#more").hidden, scrimHidden:(document.querySelector("#scrimall") || {}).hidden, locked:document.body.classList.contains("locked") }));
    return { pass:before && after.moreHidden && pg.url() === u0 && !after.locked, openedBefore:before, after, urlSame:pg.url() === u0, url:pg.url() }; });

  await run(ctx, "share_sheet", async pg => {
    await go(pg, "/m/1000020522/"); await pg.click('.hero [data-sheet="share"]');
    await pg.waitForSelector("#share .shr", { timeout:8000 }).catch(() => {}); await sleep(600); await shot(pg, "share_sheet");
    const r = await pg.evaluate(() => ({ open:!document.querySelector("#share").hidden, rows:document.querySelectorAll("#share .shr").length, labels:[...document.querySelectorAll("#share .shr")].map(x => x.textContent.replace(/\s+/g, " ").trim().slice(0, 50)), buttons:[...document.querySelectorAll("#share button.sa, #share a.sa")].map(x => x.textContent.trim()).slice(0, 12) }));
    // back closes it too
    await pg.evaluate(() => history.back()); await sleep(900); r.closedByBack = await pg.evaluate(() => document.querySelector("#share").hidden); r.urlAfterBack = pg.url().replace(SITE, "");
    return Object.assign({ pass:r.open && r.rows > 0 }, r, { shot:SHOT + "/share_sheet.png" }); });

  await run(ctx, "search", async pg => {
    await go(pg, "/"); await pg.click("#srch"); await pg.waitForSelector("#sq", { timeout:5000 }); await sleep(800);
    const Q = [["الزعيم", ["العين"]], ["مبخووت", ["مبخوت"]], ["العين الوحدة", ["العين", "الوحدة"]]], out = {}; let ok = true;
    for (const [q, want] of Q){ await pg.fill("#sq", q); await sleep(1100); const top = await pg.$$eval("#sr li", l => l.slice(0, 4).map(x => x.innerText.replace(/\s+/g, " ").trim().slice(0, 90)));
      const hit = top.length && want.every(w => top[0].includes(w)); if (!hit) ok = false; out[q] = { pass:!!hit, expect:want.join("+"), top }; await shot(pg, "search_" + (["zaeem", "mabkhout", "ain_wahda"][Object.keys(out).length - 1])); }
    return { pass:ok, queries:out }; });

  await run(ctx, "match_tabs", async pg => {
    await go(pg, "/m/1000020522/"); const tabs = await pg.$$eval(".mtabs [role=tab]", l => l.map(x => ({ t:x.dataset.t, label:x.textContent.trim() }))); const res = [];
    for (const t of tabs){ await pg.click(`.mtabs [role=tab][data-t="${t.t}"]`); await sleep(450);
      res.push(await pg.evaluate(t => { const b = document.querySelector(`.mtabs [role=tab][data-t="${t}"]`), p = document.querySelector(`[data-pane="${t}"]`); return { t, label:b.textContent.trim(), selected:b.getAttribute("aria-selected") === "true", paneVisible:!!(p && !p.hidden && p.getClientRects().length), paneChars:p ? p.innerText.length : 0, others:[...document.querySelectorAll("[data-pane]")].filter(x => x !== p && !x.hidden && x.getClientRects().length && !p.contains(x) && !x.contains(p)).map(x => x.dataset.pane) }; }, t.t)); }
    await shot(pg, "match_tabs_last");
    return { pass:tabs.length > 1 && res.every(r => r.selected && r.paneVisible && r.paneChars > 0 && !r.others.length), tabs:res }; });

  await run(ctx, "goal_moment", async pg => {
    await go(pg, "/m/1000020522/", 1500); const has = await pg.evaluate(() => !!window.__md);
    await pg.evaluate(() => { const m = JSON.parse(JSON.stringify(window.__md || JSON.parse(document.querySelector("#msum").textContent))); m.score = { home:(m.score ? m.score.home : 0) + 1, away:m.score ? m.score.away : 0 }; m.events = (m.events || []).concat([{ type:"goal", team:"home", minute:91, player:{ id:1, name:"تجربة" } }]); document.dispatchEvent(new CustomEvent("tifo:match", { detail:m })); });
    await sleep(350); await shot(pg, "goal_moment"); const fx = await pg.evaluate(() => ({ goalfx:!!document.querySelector(".goalfx, .gtext"), text:(document.querySelector(".gtext") || {}).textContent || "", flap:!!document.querySelector(".flap"), score:(document.querySelector("#mh .sc .dg") || {}).textContent }));
    fx.scoreBefore = await pg.evaluate(() => { try { const m = window.__md || JSON.parse(document.querySelector("#msum").textContent); return m.score ? m.score.home + " - " + m.score.away : null; } catch (e){ return null; } });
    await sleep(2500); fx.goneAfter3s = await pg.evaluate(() => !document.querySelector(".goalfx")); fx.scoreAfter3s = await pg.evaluate(() => (document.querySelector("#mh .sc .dg") || {}).textContent); await shot(pg, "goal_moment_after3s");
    return Object.assign({ pass:fx.goalfx, mdPresent:has }, fx, { shot:SHOT + "/goal_moment.png" }); });

  await run(ctx, "cinema", async pg => {
    await go(pg, "/", 600); await go(pg, "/m/1000020522/", 1500); const url = pg.url();
    const n = await pg.$$eval("[data-cine]", l => l.length); await pg.evaluate(() => document.querySelector("[data-cine]").click()); await sleep(700); await shot(pg, "cinema_open");
    const opened = await pg.evaluate(() => ({ cine:!!document.querySelector(".cine"), score:(document.querySelector(".cine .cs") || {}).textContent, fs:!!document.fullscreenElement }));
    await pg.click(".cine .x"); await sleep(400); const closedByX = await pg.evaluate(() => !document.querySelector(".cine"));
    // Android back while cinema is open
    await pg.evaluate(() => document.querySelector("[data-cine]").click()); await sleep(500); await pg.evaluate(() => history.back()); await sleep(1500);
    const back = { url:pg.url().replace(SITE, ""), stayedOnMatch:pg.url() === url, cineClosed:await pg.evaluate(() => !document.querySelector(".cine")).catch(() => "n/a") };
    return { pass:opened.cine && closedByX ? (back.stayedOnMatch ? true : "warn") : false, buttons:n, opened, closedByX, androidBack:back, note:back.stayedOnMatch ? "" : "history.back() with cinema open leaves the match page (cinema pushes no history entry)", shot:SHOT + "/cinema_open.png" }; });

  await run(ctx, "lineup_builder", async pg => {
    await go(pg, "/t/102124/", 1500); await pg.click('.mtabs button[data-t="squad"]'); await sleep(400); await pg.click("#xibtn"); await sleep(1500);
    await pg.click('.xs[data-s="0"]'); await sleep(400); await pg.click(".xpick [data-p]"); await sleep(300);
    await pg.click('.xs[data-s="5"]'); await sleep(300); await pg.click(".xpick li:nth-child(3) [data-p]"); await sleep(400); await shot(pg, "lineup_builder");
    const r = await pg.evaluate(() => ({ squares:document.querySelectorAll(".xpitch .xs").length, picked:document.querySelectorAll(".xpitch .xs.on").length, saved:!!localStorage.getItem("tifo.xi.102124") }));
    return Object.assign({ pass:r.squares === 11 && r.picked >= 2 && r.saved }, r, { shot:SHOT + "/lineup_builder.png" }); });

  await run(ctx, "pick_who_wins", async pg => {
    let id = "6040358"; await go(pg, "/m/" + id + "/", 1500); if (!(await pg.$("#pick"))){ id = "1000020530"; await go(pg, "/m/" + id + "/", 1500); }
    const box = await pg.$("#pick"); if (!box) return { pass:false, error:"no #pick on 6040358 or 1000020530" };
    await box.scrollIntoViewIfNeeded(); await pg.click('#pick [data-p="h"]'); await sleep(500); const msg1 = await pg.$eval("#pickm", e => e.textContent); await shot(pg, "pick_before_reload");
    await pg.reload({ waitUntil:"load" }); await sleep(1800); await (await pg.$("#pick")).scrollIntoViewIfNeeded(); await shot(pg, "pick_after_reload");
    const r = await pg.evaluate(id => ({ pressedH:document.querySelector('#pick [data-p="h"]').getAttribute("aria-pressed"), msg:document.querySelector("#pickm").textContent, stored:localStorage.getItem("tifo.picks"), hasId:(localStorage.getItem("tifo.picks") || "").includes(id) }), id);
    return Object.assign({ pass:r.pressedH === "true" && r.hasId, match:id, msgAfterClick:msg1 }, r); });
  await ctx.close();

  // ---------------- context B: فريقي → push (SW allowed, clean storage) ----------------
  ctx = await mk(!LOCAL); let MINE = null;   // local build: a service worker would fetch assets from production, so this context blocks it
  await run(ctx, "mine_no_fav_pick", async pg => {
    await go(pg, "/", 1500); const pre = await pg.evaluate(() => ({ mine:localStorage.getItem("tifo.mine"), href:document.querySelector('.tabbar [data-nav="mine"]').getAttribute("href") }));
    await pg.click('.tabbar [data-nav="mine"]'); await pg.waitForFunction(() => document.querySelectorAll("#minegrid button").length > 0, null, { timeout:8000 }).catch(() => {}); await sleep(600); await shot(pg, "mine_grid");
    const grid = await pg.evaluate(() => ({ sheetOpen:!document.querySelector("#minesh").hidden, n:document.querySelectorAll("#minegrid button").length, first:[...document.querySelectorAll("#minegrid button")].slice(0, 6).map(x => x.dataset.n), imgs:[...document.querySelectorAll("#minegrid img")].slice(0, 12).map(i => i.complete && i.naturalWidth > 0) }));
    if (!grid.n) return { pass:false, pre, grid };
    const btn = await pg.$("#minegrid button"); const pickId = await btn.getAttribute("data-t"), pickName = await btn.getAttribute("data-n");
    await Promise.all([pg.waitForURL(/\/t\/\d+\//, { timeout:15000 }).catch(() => {}), btn.click()]); await sleep(1500); const landed = pg.url().replace(SITE, "");
    MINE = { id:pickId, name:pickName };
    await go(pg, "/", 2500); await pg.waitForFunction(n => (document.querySelector("#mine") || {}).innerText && document.querySelector("#mine").innerText.includes(n), pickName, { timeout:6000 }).catch(() => {});
    const home = await pg.evaluate(() => { const a = document.querySelector('.tabbar [data-nav="mine"]'), img = a && a.querySelector("img.navcrest"), sec = document.querySelector("#r-mine");
      return { navHref:a && a.getAttribute("href"), navCrest:!!img, navCrestLoaded:!!(img && img.complete && img.naturalWidth > 0), navCrestSrc:img && img.getAttribute("src"), mineHead:sec ? (sec.querySelector("h2") || {}).textContent : "no #r-mine", mineText:((document.querySelector("#mine") || {}).innerText || "").replace(/\s+/g, " ").slice(0, 220), favs:localStorage.getItem("tifo.favs") }; });
    const r = await pg.$("#r-mine"); if (r){ await r.scrollIntoViewIfNeeded(); await sleep(400); } await shot(pg, "mine_after_pick");
    await pg.evaluate(() => window.scrollTo(0, 0)); await sleep(300); await pg.locator(".tabbar").screenshot({ path:SHOT + "/mine_navcrest.png" }).catch(() => {});
    const populated = home.mineText.includes(pickName);
    return { pass:grid.sheetOpen && grid.n > 0 && landed === "/t/" + pickId + "/" && populated && home.navCrestLoaded && home.navHref === "/t/" + pickId + "/", pre, grid, picked:MINE, landed, home, mineSectionPopulated:populated }; });

  await run(ctx, "push_sheet", async pg => {
    const tid = MINE ? MINE.id : "102124"; if (!MINE) await pg.evaluate(() => 0);
    await go(pg, "/t/" + tid + "/", 1800);
    const pre = await pg.evaluate(() => ({ btnExists:!!document.querySelector("#pushbtn"), btnVisible:!!document.querySelector("#pushbtn") && !document.querySelector("#pushbtn").hidden, btnText:(document.querySelector("#pushbtn") || {}).textContent, perm:typeof Notification !== "undefined" ? Notification.permission : "none", pushApi:"PushManager" in window, sw:"serviceWorker" in navigator }));
    if (!pre.btnVisible) return { pass:false, team:tid, pre, note:MINE ? "" : "no favourite from previous flow" };
    await pg.click("#pushbtn"); await sleep(700); await shot(pg, "push_sheet");
    const r = await pg.evaluate(() => ({ open:!document.querySelector("#pushs").hidden, title:(document.querySelector("#pusht") || {}).textContent, toggles:[...document.querySelectorAll("#pushs .ptg")].map(b => b.textContent.trim() + ":" + b.getAttribute("aria-pressed")), permAfter:Notification.permission }));
    await pg.keyboard.press("Escape"); await sleep(500); r.closedByEsc = await pg.evaluate(() => document.querySelector("#pushs").hidden);
    return Object.assign({ pass:r.open && r.toggles.length === 3 && r.permAfter === "default" && r.closedByEsc, team:tid, pre, shot:SHOT + "/push_sheet.png", subCalls:blocked.filter(x => /push\/sub/.test(x)) }, r); });
  await ctx.close();

  // ---------------- context C: country switch AE -> SA ----------------
  ctx = await mk(false);
  await run(ctx, "country_switch_SA", async pg => {
    const snap = () => pg.evaluate(() => { const c = s => [...document.querySelectorAll(s)];
      return { ls:localStorage.getItem("tifo.country"), ctry:(document.querySelector("#ctry") || {}).textContent, chn:c(".chn[data-comp]").slice(0, 8).map(e => e.dataset.comp + ":" + e.textContent.trim()), chnCount:c(".chn[data-comp]").length,
        rows:c("#day a.m, main a.m").slice(0, 6).map(e => e.innerText.replace(/\s+/g, " ").trim().slice(0, 80)), times:c("#day a.m .dg, main a.m time, main a.m .t").slice(0, 8).map(e => e.textContent.trim()),
        countdown:c("#uaecd, .cd, [id$=cd]").slice(0, 3).map(e => (e.id || e.className) + ": " + e.innerText.replace(/\s+/g, " ").trim().slice(0, 90)), hero:((document.querySelector(".hero") || {}).innerText || "").replace(/\s+/g, " ").slice(0, 160) }; });
    await go(pg, "/", 2500); const before = await snap(); await shot(pg, "country_before_AE");
    await pg.click('.tabbar [data-sheet="more"]'); await sleep(600); await pg.click("#ctry"); await pg.waitForSelector("#ctrysh:not([hidden]) #ctrybody button", { timeout:4000 }); await sleep(300); await shot(pg, "country_picker");
    const opts = await pg.$$eval("#ctrybody button[data-c]", l => l.length); await pg.click('#ctrybody button[data-c="SA"]'); await sleep(1800);
    const after = await snap(); await shot(pg, "country_after_SA_noreload");
    await pg.reload({ waitUntil:"load" }); await pg.waitForLoadState("networkidle", { timeout:10000 }).catch(() => {}); await sleep(2500); const reloaded = await snap(); await shot(pg, "country_after_SA_reload");
    await go(pg, "/m/6040358/", 1800); const matchPage = await pg.evaluate(() => ({ time:[...document.querySelectorAll(".hero .dg, #mh .dg, .mcd")].slice(0, 4).map(e => e.textContent.trim()), chn:[...document.querySelectorAll(".chn, .tvl, [data-comp].chn")].slice(0, 3).map(e => e.textContent.trim()), prayer:[...document.querySelectorAll(".prayl")].map(e => e.textContent.trim()) }));
    const timesChanged = JSON.stringify(before.times) !== JSON.stringify(after.times), chnChangedNoReload = JSON.stringify(before.chn) !== JSON.stringify(after.chn), chnChangedReload = JSON.stringify(before.chn) !== JSON.stringify(reloaded.chn), cdChanged = JSON.stringify(before.countdown) !== JSON.stringify(reloaded.countdown);
    return { pass:reloaded.ls === "SA" && timesChanged ? (chnChangedReload || !before.chnCount ? true : "warn") : false, options:opts, timesChanged, channelsChangedWithoutReload:chnChangedNoReload, channelsChangedAfterReload:chnChangedReload, countdownChangedAfterReload:cdChanged, before, after, reloaded, matchPage6040358:matchPage }; });
  await ctx.close();

  // ---------------- context D: offline + install (SW allowed, clean) ----------------
  ctx = await mk(true);
  await run(ctx, "offline_page", async (pg, c) => {
    await go(pg, "/offline/", 1000); await shot(pg, "offline_direct"); const direct = await pg.evaluate(() => ({ offl:((document.querySelector("#offl") || {}).innerText || "").replace(/\s+/g, " ").slice(0, 160), h1:(document.querySelector("h1") || {}).textContent }));
    await go(pg, "/", 1500); const ready = await pg.evaluate(() => Promise.race([navigator.serviceWorker.ready.then(r => r.active ? r.active.state : "noactive"), new Promise(r => setTimeout(() => r("timeout"), 15000))]));
    await pg.reload({ waitUntil:"load" }); await sleep(2000); const controlled = await pg.evaluate(() => !!navigator.serviceWorker.controller);
    const cacheKeys = await pg.evaluate(async () => { const ks = await caches.keys(); const o = {}; for (const k of ks){ o[k] = (await (await caches.open(k)).keys()).length; } return o; });
    await c.setOffline(true); const res = {};
    for (const u of ["/", "/laws/", "/c/saudi-pro-league/"]){ let err = ""; await pg.goto(SITE + u, { waitUntil:"load", timeout:20000 }).catch(e => err = clean(e.message).slice(0, 120)); await sleep(1200);
      res[u] = await pg.evaluate(() => ({ title:document.title, offl:!!document.querySelector("#offl"), page:document.body && document.body.dataset.page, chars:document.body ? document.body.innerText.length : 0 })).catch(e => ({ err:clean(e.message).slice(0, 100) })); if (err) res[u].gotoErr = err; }
    await shot(pg, "offline_uncached_nav"); await c.setOffline(false);
    const ok = direct.offl.length > 0 && controlled && res["/laws/"] && (res["/laws/"].offl || res["/laws/"].chars > 200);
    return { pass:ok ? true : direct.offl ? "warn" : false, direct, swReady:ready, controlledAfterReload:controlled, cacheKeys, offlineNav:res }; });

  await run(ctx, "install_manifest", async pg => {
    await go(pg, "/", 1500);
    const r = await pg.evaluate(async () => { const link = document.querySelector('link[rel="manifest"]'); if (!link) return { error:"no manifest link" };
      const resp = await fetch(link.href); const m = await resp.json(); const icons = [];
      for (const ic of m.icons || []){ const x = await fetch(new URL(ic.src, link.href)); let dims = ""; try { const bm = await createImageBitmap(await x.blob()); dims = bm.width + "x" + bm.height; } catch (e){ dims = "decode-fail"; } icons.push({ src:ic.src, sizes:ic.sizes, purpose:ic.purpose || "any", status:x.status, type:x.headers.get("content-type"), actual:dims, match:dims === ic.sizes }); }
      const ati = document.querySelector('link[rel="apple-touch-icon"]'); let atiS = null; if (ati){ const x = await fetch(ati.href); let d = ""; try { const bm = await createImageBitmap(await x.blob()); d = bm.width + "x" + bm.height; } catch (e){} atiS = { status:x.status, dims:d }; }
      const reg = await navigator.serviceWorker.getRegistration(); const sc = [...document.querySelectorAll("#inst, #instm, #instgo")].map(e => e.id + (e.hidden ? ":hidden" : ":shown"));
      const st = await Promise.all((m.shortcuts || []).map(s => fetch(s.url).then(x => s.url + " " + x.status)));
      return { manifestStatus:resp.status, contentType:resp.headers.get("content-type"), name:m.name, short_name:m.short_name, start_url:m.start_url, scope:m.scope, display:m.display, dir:m.dir, lang:m.lang, theme:m.theme_color, bg:m.background_color, icons, appleTouch:atiS, shortcuts:st, sw:reg ? { scope:reg.scope, active:!!reg.active, script:reg.active && reg.active.scriptURL } : null, controlled:!!navigator.serviceWorker.controller, installUi:sc }; });
    const need = r.name && r.short_name && r.start_url && r.display === "standalone" && r.icons && r.icons.some(i => i.sizes === "192x192" && i.status === 200) && r.icons.some(i => i.sizes === "512x512" && i.status === 200);
    const iconsOk = r.icons && r.icons.every(i => i.status === 200 && i.match);
    return Object.assign({ pass:need && iconsOk && r.sw && r.sw.active ? true : need ? "warn" : false, installable_criteria_met:!!need, icons_all_200_and_sized:!!iconsOk, note:"headless Chromium never fires beforeinstallprompt, so #instm/#instgo stay hidden by design; installability judged from manifest + SW" }, r); });
  await ctx.close();

  await b.close();
  console.log("blocked(api, not sent to prod):", JSON.stringify(blocked.reduce((o, x) => (o[x] = (o[x] || 0) + 1, o), {})));
  fs.writeFileSync(QA + "/_scripts/flows.blocked.json", JSON.stringify(blocked));
})().catch(e => { console.error("FATAL", e); process.exit(1); });
