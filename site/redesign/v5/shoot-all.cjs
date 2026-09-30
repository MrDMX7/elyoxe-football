/* Every preview page as a phone screenshot, 390x844 @2x, light and dark, from the published preview.
   node site/redesign/v5/shoot-all.cjs --out <dir> [--base https://tifo.elyoxe.com]
   Motion is reduced so segmented thumbs and sheets are captured settled. */
"use strict";
const { chromium } = require(process.env.PW || "C:/Users/requi/workspace/content-pipeline/node_modules/playwright-core");
const args = process.argv.slice(2), opt = (k, d) => { const i = args.indexOf("--" + k); return i >= 0 ? args[i + 1] : d; };
const BASE = opt("base", "https://tifo.elyoxe.com"), OUT = opt("out", "v5-shots");
const tab = t => `document.querySelector('.segbar .seg button[data-t=${t}]').click(); window.scrollTo(0, document.querySelector('.segbar').getBoundingClientRect().top + scrollY - 60)`;
const FAV = 'localStorage.setItem("tifo.favs", JSON.stringify([{t:"team",id:5789,n:"الإمارات"},{t:"team",id:102111,n:"الوصل"},{t:"comp",id:538,n:"دوري أدنوك للمحترفين"}]))';
const SHOTS = [
  ["01-home", "/next/"],
  ["02-home-scrolled", "/next/", "window.scrollTo(0, 620)"],
  ["03-live-match", "/next/m/live/"],
  ["04-live-match-events", "/next/m/live/", "window.scrollTo(0, document.querySelector('.segbar').getBoundingClientRect().top + scrollY - 60)"],
  ["05-finished-match", "/next/m/6052086/"],
  ["06-finished-match-lineups", "/next/m/1000020522/", tab("lu")],
  ["07-finished-match-stats", "/next/m/1000020522/", tab("st")],
  ["08-match-h2h", "/next/m/6052086/", tab("h2h")],
  ["09-prematch", "/next/m/1000020530/"],
  ["10-prematch-details", "/next/m/1000020530/", "window.scrollTo(0, document.querySelector('.segbar').getBoundingClientRect().top + scrollY - 60)"],
  ["11-sheet-share", "/next/m/6052086/", "document.querySelector('[data-sheet=sh-share]').click()"],
  ["12-comp-table", "/next/c/uae-pro-league/"],
  ["13-comp-table-scrolled", "/next/c/uae-pro-league/", "window.scrollTo(0, document.querySelector('.segbar').getBoundingClientRect().top + scrollY - 60)"],
  ["14-comp-fixtures", "/next/c/uae-pro-league/", tab("fx")],
  ["15-comp-stats", "/next/c/uae-pro-league/", tab("num")],
  ["16-comp-predictions", "/next/c/uae-pro-league/", tab("pred")],
  ["17-comp-history", "/next/c/uae-pro-league/", tab("hist")],
  ["18-cup-groups", "/next/c/gulf-cup/", "window.scrollTo(0, document.querySelector('.segbar').getBoundingClientRect().top + scrollY - 60)"],
  ["19-team", "/next/t/102111/"],
  ["20-team-squad", "/next/t/102111/", tab("sq")],
  ["21-team-history", "/next/t/102111/", tab("hi")],
  ["22-national-team", "/next/t/5789/"],
  ["23-player", "/next/p/30893/"],
  ["24-player-ea-card", "/next/p/30893/", "var e=[...document.querySelectorAll('.gh')].find(x=>/EA SPORTS/.test(x.textContent)); window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 70)"],
  ["25-player-career", "/next/p/30893/", tab("ca")],
  ["26-player-injuries", "/next/p/30893/", tab("ca") + "; setTimeout(function(){ var e=[...document.querySelectorAll('.gh')].find(x=>/الإصابات/.test(x.textContent)); if (e) window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 70); }, 50)"],
  ["27-player-matches", "/next/p/721345/", tab("mt")],
  ["28-encyclopedia", "/next/db/"],
  ["29-encyclopedia-search", "/next/db/", "var q=document.getElementById('wq'); q.value='الهلال'; q.dispatchEvent(new Event('input'))", "", 4000],
  ["30-league-champions", "/next/db/league/549/"],
  ["31-league-champions-list", "/next/db/league/549/", "window.scrollTo(0, 1300)"],
  ["32-news", "/next/news/"],
  ["33-search", "/next/search/", "var q=document.getElementById('q'); q.value='العين'; q.dispatchEvent(new Event('input'))", "", 3000],
  ["34-more", "/next/more/"],
  ["35-more-scrolled", "/next/more/", "window.scrollTo(0, 900)"],
  ["36-competitions", "/next/competitions/"],
  ["37-national-teams", "/next/competitions/", tab("n")],
  ["38-mine-empty", "/next/mine/"],
  ["39-mine-following", "/next/mine/", "", FAV, 2500],
  ["40-sheet-filter", "/next/", "document.querySelector('[data-sheet=sh-filter]').click()"],
  ["41-client-rendered-match", "/next/m/?id=5795459", "", "", 2500],
  ["42-client-rendered-team", "/next/t/?id=8456", "", "", 2500],
];
(async () => {
  const fs = require("fs"); fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch({ channel: "msedge" }), log = [];
  for (const sc of ["light", "dark"]) {
    for (const [name, p, act, pre, wait] of SHOTS) {
      const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, colorScheme: sc, reducedMotion: "reduce", serviceWorkers: "block", locale: "ar-AE", timezoneId: "Asia/Dubai" });
      if (pre) await ctx.addInitScript(pre);
      const pg = await ctx.newPage(), errs = []; pg.on("pageerror", e => errs.push(e.message));
      try { await pg.goto(BASE + p, { waitUntil: "networkidle", timeout: 60000 }); } catch (e) { errs.push("timeout"); }
      await pg.waitForTimeout(1500);
      if (act) { try { await pg.evaluate(act); } catch (e) { errs.push("act " + e.message); } }
      await pg.waitForTimeout(wait || 900);
      const f = `${OUT}/${name}-${sc}.png`; await pg.screenshot({ path: f });
      log.push(`${name}-${sc}${errs.length ? " ERR " + errs.join("; ") : ""}`); process.stdout.write(errs.length ? "x" : ".");
      await ctx.close();
    }
  }
  await b.close(); console.log("\n" + log.filter(x => /ERR/.test(x)).join("\n")); console.log(log.length + " screenshots in " + OUT);
})();
