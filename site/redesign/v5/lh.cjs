/* Lighthouse mobile (simulated slow 4G + 4x CPU, the default) on the published preview and the live page it replaces, one run at a
   time. node site/redesign/v5/lh.cjs [--out lh.json] [paths…]   (needs the lighthouse CLI; CHROME_PATH may point at Edge) */
"use strict";
const { execFileSync } = require("child_process"), fs = require("fs"), os = require("os"), path = require("path");
const args = process.argv.slice(2), oi = args.indexOf("--out"), OUT = oi >= 0 ? args[oi + 1] : "";
const paths = args.filter((a, i) => a.startsWith("/") && !["--out", "--v5", "--live"].includes(args[i - 1]));
const PAGES = paths.length ? paths : ["/", "/m/6052086/", "/c/uae-pro-league/", "/t/102111/", "/p/30893/", "/news/"];
const LH = process.env.LH || path.join(process.env.APPDATA || "", "npm", "node_modules", "lighthouse", "cli", "index.js");
const env = Object.assign({}, process.env, { CHROME_PATH: process.env.CHROME_PATH || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" });
const res = {};
// production rollout: --v5 <origin> --live <origin> compare two local servers of the same data (the new build and the old one)
const og = k => { const i = args.indexOf("--" + k); return i >= 0 ? args[i + 1] : ""; }, V5O = og("v5"), LIVEO = og("live");
for (const p of PAGES) for (const [side, url] of [["v5", V5O ? V5O + p : "https://tifo.elyoxe.com/next" + p], ["live", (LIVEO || "https://tifo.elyoxe.com") + p]]) {
  const f = path.join(os.tmpdir(), "lh_v5_" + side + ".json");
  try {
    try { fs.unlinkSync(f); } catch (e) {}
    // on Windows chrome-launcher often fails to delete its temp profile after the run (EPERM): the report is already written
    try { execFileSync(process.execPath, [LH, url, "--quiet", "--only-categories=performance", "--form-factor=mobile", "--chrome-flags=--headless=new --no-sandbox", "--output=json", "--output-path=" + f], { env, stdio: "ignore", timeout: 240000 }); } catch (e) { if (!fs.existsSync(f)) throw e; }
    const d = JSON.parse(fs.readFileSync(f, "utf8")), a = d.audits;
    const r = { perf: Math.round(d.categories.performance.score * 100), fcp: Math.round(a["first-contentful-paint"].numericValue), lcp: Math.round(a["largest-contentful-paint"].numericValue), tbt: Math.round(a["total-blocking-time"].numericValue), cls: +a["cumulative-layout-shift"].numericValue.toFixed(3), si: Math.round(a["speed-index"].numericValue), bytes: Math.round(a["total-byte-weight"].numericValue / 1024) };
    (res[p] = res[p] || {})[side] = r; console.log(p, side, JSON.stringify(r));
  } catch (e) { (res[p] = res[p] || {})[side] = { error: String(e.message).slice(0, 120) }; console.log(p, side, "error", String(e.message).slice(0, 120)); }
}
if (OUT) fs.writeFileSync(OUT, JSON.stringify(res, null, 1));
