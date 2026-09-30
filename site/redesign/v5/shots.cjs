/* Phone screenshots of the v5 preview: 390x844 @2x, light and dark (prefers-color-scheme), service workers blocked.
   node site/redesign/v5/shots.cjs --base http://localhost:8795 --out <dir> [--full] [--scheme light|dark|both] [--w 390 --h 844]
        [--act "js to run before the shot"] name=path [name=path ...] */
"use strict";
const PW = process.env.PW || "C:/Users/requi/workspace/content-pipeline/node_modules/playwright-core";
const { chromium } = require(PW);
const args = process.argv.slice(2), opt = (k, d) => { const i = args.indexOf("--" + k); return i >= 0 ? args[i + 1] : d; }, flag = k => args.includes("--" + k);
const BASE = opt("base", "http://localhost:8795"), OUT = opt("out", "."), FULL = flag("full"), SCH = opt("scheme", "both"), W = +opt("w", 390), H = +opt("h", 844), ACT = opt("act", ""), PRE = opt("pre", ""), WAIT = +opt("wait", 700);
const VALUED = new Set(["--base", "--out", "--scheme", "--w", "--h", "--act", "--pre", "--wait"]);
const items = args.filter((a, i) => /=/.test(a) && !a.startsWith("--") && !VALUED.has(args[i - 1]));
(async () => {
  const fs = require("fs"); fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch({ channel: "msedge" });
  const schemes = SCH === "both" ? ["light", "dark"] : [SCH];
  for (const sc of schemes) {
    const ctx = await b.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, colorScheme: sc, serviceWorkers: "block", locale: "ar-AE", timezoneId: "Asia/Dubai" });
    if (PRE) await ctx.addInitScript(PRE);   // e.g. followed teams in localStorage before the page loads
    const pg = await ctx.newPage(); const errs = [];
    pg.on("pageerror", e => errs.push("pageerror " + e.message)); pg.on("console", m => { if (m.type() === "error") errs.push("console " + m.text()); });
    for (const it of items) {
      const [name, p] = [it.slice(0, it.indexOf("=")), it.slice(it.indexOf("=") + 1)];
      errs.length = 0;
      try { await pg.goto(BASE + p, { waitUntil: "networkidle", timeout: 60000 }); } catch (e) { console.log("nav timeout", p); }
      await pg.waitForTimeout(700);
      if (ACT) { try { await pg.evaluate(ACT); await pg.waitForTimeout(WAIT); } catch (e) { console.log("act failed", e.message); } }
      const f = `${OUT}/${name}-${sc}.png`;
      await pg.screenshot({ path: f, fullPage: FULL });
      const sw = await pg.evaluate(() => [document.documentElement.scrollWidth, innerWidth, document.documentElement.scrollHeight]);
      console.log(f, "scrollW/innerW/H", sw.join("/"), errs.length ? "ERR " + errs.slice(0, 3).join(" | ") : "");
    }
    await ctx.close();
  }
  await b.close();
})();
