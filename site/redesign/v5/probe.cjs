/* Dev probe: open a preview page and print the result of a JS expression. node probe.cjs <path> "<js body returning a value>" [w] [scheme] */
"use strict";
const { chromium } = require(process.env.PW || "C:/Users/requi/workspace/content-pipeline/node_modules/playwright-core");
(async () => {
  const [pth, js, w, sc] = process.argv.slice(2);
  const b = await chromium.launch({ channel: "msedge" });
  const ctx = await b.newContext({ viewport: { width: +(w || 390), height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, colorScheme: sc || "light", serviceWorkers: "block", timezoneId: "Asia/Dubai" });
  const p = await ctx.newPage(); const errs = [];
  p.on("pageerror", e => errs.push(e.message)); p.on("console", m => { if (m.type() === "error" || m.type() === "warning") errs.push(m.text()); });
  await p.goto((process.env.BASE || "http://localhost:8795") + pth, { waitUntil: "networkidle" });
  await p.waitForTimeout(500);
  const r = await p.evaluate(new Function(js));
  console.log(JSON.stringify(r, null, 1));
  if (errs.length) console.log("ERRORS", errs.slice(0, 5));
  await b.close();
})();
