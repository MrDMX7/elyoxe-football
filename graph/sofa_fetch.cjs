// SofaScore's player of the match per finished match (graph/sofa.py runs this on the laptop: SofaScore answers a browser,
// not a script). node graph/sofa_fetch.cjs <jobs.json> <out dir> <budget>
// jobs: [{ut, skip: ["2023/2024", ...]}]; out: <ut>_<season>.json {ut, season, year, rated, events: [{id, ts, home, away, hs, as, potm}]}.
// One request a second; a season's player-of-the-match calls stop at the budget and go on next run.
"use strict";
const fs = require("fs"), path = require("path"), { chromium } = require("playwright");
const [, , jobsFile, out, budgetArg] = process.argv;
let budget = +budgetArg || 2500;
const label = y => { const m = String(y).match(/^(\d{2})\/(\d{2})$/); return m ? `20${m[1]}/20${m[2]}`.replace(/^20(9\d)/, "19$1") : String(y); };
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const jobs = JSON.parse(fs.readFileSync(jobsFile, "utf8"));
  fs.mkdirSync(out, { recursive: true });
  // a real Chrome with a profile of its own (graph/.cache/sofa_profile: its cookies carry over from run to run), the window
  // off-screen; the owner allowed it (2026-11-20). A headless browser gets SofaScore's challenge.
  const b = await chromium.launchPersistentContext(path.join(out, "..", "sofa_profile"), { headless: false, channel: "chrome",
    args: ["--window-position=-2400,0", "--window-size=1200,800"] });
  const p = b.pages()[0] || await b.newPage();
  await p.goto("https://www.sofascore.com/football", { waitUntil: "networkidle", timeout: 90000 }).catch(() => {});
  await sleep(4000);
  if (process.env.SOFA_DIAG) {                                  // what the site shows this browser (the owner's diagnosis request)
    await p.screenshot({ path: path.join(out, "..", "sofa_diag.png") });
    const r = await p.evaluate(async () => { const x = await fetch("/api/v1/unique-tournament/955/seasons"); return [x.status, (await x.text()).slice(0, 200)]; });
    console.log("diag", JSON.stringify(r), await p.title());
    await b.close();
    return;
  }
  const J = async u => { await sleep(2000); return p.evaluate(async u => { const x = await fetch(u); return x.status === 200 ? x.json() : { status: x.status }; }, u); };
  const stats = { seasons: 0, events: 0, potm: 0, calls: 0 };
  for (const job of jobs) {
    const ss = await J(`/api/v1/unique-tournament/${job.ut}/seasons`);
    if (!ss.seasons) console.error("seasons", job.ut, JSON.stringify(ss).slice(0, 120));
    for (const s of ss.seasons || []) {                        // newest first; an unrated season ends this league's walk back
      const lab = label(s.year), f = path.join(out, `${job.ut}_${s.id}.json`);
      if ((job.skip || []).includes(lab)) continue;
      let doc = fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : { ut: job.ut, season: s.id, year: lab, rated: null, events: [] };
      if (doc.rated === false) break;
      if (!doc.events.length || doc.open) {
        const seen = new Map(doc.events.map(e => [e.id, e]));
        for (let page = 0; page < 40; page++) {
          const r = await J(`/api/v1/unique-tournament/${job.ut}/season/${s.id}/events/last/${page}`);
          for (const e of r.events || []) {
            if (!e.status || e.status.type !== "finished" || seen.has(e.id)) continue;
            seen.set(e.id, { id: e.id, ts: new Date(e.startTimestamp * 1000).toISOString(), home: [e.homeTeam.id, e.homeTeam.name], away: [e.awayTeam.id, e.awayTeam.name],
              hs: (e.homeScore || {}).current, as: (e.awayScore || {}).current });
          }
          if (!r.hasNextPage) break;
        }
        doc.events = [...seen.values()];
        doc.open = Date.now() / 1000 - Math.max(0, ...doc.events.map(e => Date.parse(e.ts) / 1000)) < 120 * 86400;   // a season still being played
      }
      stats.seasons++;
      for (const e of doc.events) {
        if (e.potm !== undefined) continue;
        if (budget <= 0) break;
        const r = await J(`/api/v1/event/${e.id}/best-players/summary`); budget--; stats.calls++;
        const pm = r && r.playerOfTheMatch;
        e.potm = pm ? { id: pm.player.id, name: pm.player.name, value: pm.value } : null;
        doc.checked = (doc.checked || 0) + 1;
        if (pm) { doc.rated = true; stats.potm++; }
        else if (doc.rated !== true && doc.checked >= 5) { doc.rated = false; break; }   // five matches with no pick: not a rated season
        if (stats.calls % 25 === 0) fs.writeFileSync(f, JSON.stringify(doc));
      }
      stats.events += doc.events.length;
      fs.writeFileSync(f, JSON.stringify(doc));
      if (doc.rated === false || budget <= 0) break;
    }
    if (budget <= 0) break;
  }
  console.log(JSON.stringify(stats));
  await b.close();
})().catch(e => { console.error(e); process.exit(1); });
