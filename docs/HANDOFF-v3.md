# Tifo v3: handoff (stopped 2026-09-28, about 13:30 UAE)

Stopped at the coordinator's request because the phone battery was draining. There was no work in progress: the worktree `~/workspace/saas/football-v3` (branch `v3`) is clean. Everything below was committed and was already merged to main and deployed before the stop.

- **Last commits:**
  - `a5fbb5a` QA fixes
  - `2c9401d` merge of main into v3
  - `d939d64` the 301 draft
- **Production:** the last deploy from main at `2c9401d` finished at about 13:10 UAE with every check at 200.
- **Nothing running:** no build, deploy or Chromium process is left from this session.

## QA 2026-09-28 (docs/QA-2026-09-28.json): site-side status

The QA list numbers bugs 0–104 (the order of `bugs[]`). "Fixed" means the change is in the code and deployed.

### Highs (0–18): all fixed on the site side
| # | bug | status |
|---|-----|--------|
| 0 | المزيد country switch freezes the page (inert never cleared) | fixed: the country picker and search are real sheets (`#ctrysh`, `#srchsh`), opened and closed through `window.TifoSheet` (shell.js, app.js) |
| 1 | Day-list group label taken from the first match | fixed: a block head only when every match shares the group, else a `.grp-sub` per group (render.js `R.dayList`) |
| 2 | Upcoming «المواجهات» says the clubs never met | fixed: the build fills `md.h2h` from the pair file; the client keeps it when the detail file has no h2h (build.cjs, app.js) |
| 3, 18 | Mini-bar share icon wraps onto the tabs | fixed: `.mini .wrap` uses `grid-auto-flow:column` (v3.css) |
| 4, 62 | Upcoming match pages stuck «stale» | fixed: no `data-built` for scheduled matches; the chip uses 24 h time (build.cjs, shell.js) |
| 5, 17 | Gulf Cup / Premier League «متوقفة» | fixed on the site: dormant is recomputed from fixtures (−3…+30 days); the pipeline also rechecks hourly |
| 6 | Stale Gulf Cup sim | fixed on the site: the sim is hidden when older than the competition's latest result (`simOk`); the pipeline reruns it |
| 7 | English knockout stage names and order | fixed: `R.stageAr` covers every key, plus `R.roundChip`, `R.stageRank` and `R.slotAr` for «Winner SF 1» (render.js) |
| 8 | «يوم الحسم» at round 6 of 26 | fixed: uses `fx.rounds_left`, otherwise rounds with unfinished matches (stats.js `S.whatif`) |
| 9, 61 | h2h lists the upcoming meeting as «انتهت» | fixed: only played meetings are listed (stats.js `S.h2hPage`, render.js `R.h2h`) |
| 10 | h2h files miss the latest meeting | fixed on the site: our finished matches for the pair are merged in and counted (build.cjs); the pipeline also fixed the files |
| 11 | National teams show the wrong next match (friendlies) | fixed: `national.json` next/last join the fixtures, and every Arab national team's `team/<id>.json` is fetched |
| 12 | National اللاعبين tab says «ما في قائمة لاعبين» | fixed: the tab falls back to `national/<id>/squad.json` (the `<!--NATSQ-->` patch), and «آخر قائمة» is dropped from التاريخ |
| 13, 16 | Embed widget shows reversed scores | fixed: the score is 3 cells in DOM order; upcoming matches fall back to the day file (`&d=` in embed codes) and poll near kickoff |
| 14 | A match page opened early never goes live | fixed: `wake()` fires 75 min before kickoff, `nearKick()` retries/overlays, and the visibility handler re-runs (app.js) |
| 15 | Offline pages lose their CSS/JS after a deploy | fixed: one unversioned `tifo-assets` cache (LRU 160), and the old per-version caches fold into it (sw.js) |

### Mediums and lows
- **Fixed:** 19–31, 34–43 (site side), 45 (every linked player name goes through the build's PNAMES pass), 46–50, 52–60, 63, 64, 66–70, 72–79, 81–95, 97–104.
- **Half-done:**
  - **35 / 45:** player names that are *not links* (plain `<span class="lat">`) can still be Latin when names/players_ar.json has no entry. Coach names in team tiles still need coachAr in `S.coachesTeam` (stats.js).
  - **65:** venue, coach and referee are fixed. «Widad Temara» needs `name_ar` in teams.json (pipeline).
  - **38 / 66:** the colour glows are gone. The logo's one-time entry animation (`logoIn`) was kept on purpose (page entry, off under reduced motion).
  - **31:** English stadium notes are hidden, not translated. Translating them means editing stadiums.yaml / research data.
- **Pipeline (data), not site:** 32, 33, 44, 51, 71, 80, 96 (and the root causes of 5, 6, 10, 11, 43). The pipeline agent reports all of these deployed in `9dd79de`.

## Found right at the stop (look at this first)
- **`/m/1000020530/` returns 404 on production** (الشارقة ضد الظفرة, كأس رابطة المحترفين, 1 Oct). The worktree build has the page; main's deployed build does not (`out/m` has 5,071 pages, and the sitemap lacks the id). It's probably a data difference between the worktree cache and main's cache, or the fixture moving between hourly runs.
  - **Steps:** rebuild main locally, check `mids` for 1000020530, and compare `comp/11027/fixtures.json` with `day/*.json`. The `pages` count in deploy.sh's partial-build guard was fine.

## Pending items the coordinator listed
- **426 JSON-LD:** done and deployed (build.cjs, the `ld` block).
  - `superEvent` is dropped. `organizer` is a SportsOrganization.
  - Added: `description` (result · competition · round), `image` (og card), `endDate` (kickoff + 2 h), `performer`.
  - `fixAl()` turns «ال نهيان/مكتوم…» into «آل …» in page text and JSON-LD, and stadiums.yaml is fixed at the source (the poller picks that up on its next deploy).
  - A local sweep of 400 match pages found no invalid SportsEvent (the other 400 blocks were FAQPage, which the sweep also counted). **Still to do:** re-run Google's Rich Results test on /m/1000020522/ once CloudFront has the new page.
- **425 static passthrough:** done. Every file in `site/static/` (except README and dotfiles) is copied to the `out/` root with its mtime kept (build.cjs, just before `.pages`). `googled74cf310ae100255.html` is copied. deploy.sh's `--exclude "google*.html"` (d69bb40) stays.
- **417 /week/ «تيفو الأسبوع» card:** deployed.
  - It renders from `cache/week/week-latest.json` at build time, and from `/og/week-latest.json` in the browser. It draws nothing on a 404.
  - The first real data arrives with weekly.py on Thursday 2026-10-01 15:00. The worktree's cache has a local fixture (week 2026-39); production's cache does not.

## Gates on the deployed build
- Inventory: 0 missing (placement.json got renames for «محسن مصبح», «مباريات المنتخبات اليوم», and the `week|mount:#wwbox` drop).
- featcheck: pass.
- QA flows against the local build (`site/redesign/qaflows.cjs` with `LOCAL=<out dir>`): 14 of 14 pass.
  - The copy follows the new country sheet (`#ctrysh`/`#ctrybody`).
  - With LOCAL set, the favourites context blocks the service worker, because a service worker would fetch assets from production.
- Suites w3/w4/w4b/wc/wd/wk: pass, no page errors, no horizontal scroll.
- Layout shift: at most 0.0225 (/national/).
- Paired FCP, old vs new: new is at or below old on all 4 pages. The load average was 17, so absolute numbers mean little. Lighthouse was not run (load 17+).

## Next
1. The /m/1000020530/ 404 above.
2. Re-run Google's Rich Results test (426) on production.
3. The half-done items above.
4. Remove the worktree when done: keep branch `v3`; the worktree's `site/cache` is a real copy, not a symlink.

## Pipeline

Status at 2026-09-28 13:12 UAE (pipeline agent, stopped on the owner's signal). Last deploy 11:19 UAE; nothing pending.

**QA 2026-09-28 data bugs: done (deployed, commits 9dd79de + fc7848d)**
- #10 h2h leaves out via_match: files rebuilt once with it (UAE pairs 2 per idle minute, Arab derbies 4/h); `matches` = results only.
- #9/#61 upcoming meeting shown as finished: future meetings moved to `upcoming[]`.
- #2 «المواجهات» empty on upcoming matches: `match/<id>.json` now exists for the next 7 days (`minimal: true`, `h2h` from the pair file); also #14/#102 (404 before prematch).
- #97 derbies without file: Baghdad, Kuwait, Algiers have data (building); derbies.json never links a missing file (`h2h: null` + `missing`). Amman: Jordan not on FotMob (cannot fix).
- #5/#17 Gulf Cup and PL «متوقفة»: dormant rechecked hourly (both active again); fixtures fall back to last good when FotMob omits them.
- #6/#39 stale Gulf Cup sim: national step re-runs after any national-competition result (first rerun at the next Gulf Cup result, 29 Sep; the daily run also refreshes it).
- #7/#99 round keys: normalised (no spaces), `round_ar`, bracket `stage_ar`, TBD slots `placeholder: true` with «الفايز من نص النهائي 1».
- #11/#12/#71 national teams: `team/<id>.json` for the 21 other Arab national teams (squad + friendlies), Arab national matches tracked; #20/#41 Tunisia swap fixed in arabs/national.json.
- #43 Asian Cup time TBD carried from team pages to fixtures/day/match files.
- #32 foreign share now by minutes (70.3% for 538; headcount = `foreign_squad_pct`); #33 bump ends on the table order; #8 `rounds_left` in fixtures (site must use it); #51 match of the week rescored (national teams, cross-country Arab, stakes); #80 player id 0 -> null; birthdays for all 366 days; PL bump restored.
- Health items that failed once now clear on success (329/47 fixtures, careers).

**Left / needs the site or a later run**
- #44 UAE squad goals / «آخر 10 نتايج» miss 27 Sep: team file refresh after full time is in (next focus refresh), archive merge of FotMob results newer than martj42 not verified live yet.
- Site-side use of the new fields (round_ar, upcoming, rounds_left, team/<id>.json for national teams, minimal match files): design agent notified.
- 14:00 verification (sim, team/6719.json, UAE archive) was cancelled by the stop: check first on resume.

**424 push test (production)**: not completed. A real Mozilla subscription to Zimbabwe (6290) and DR Congo (6321), match 6040262 at 20:00 UAE, was registered via /api/tifo/push/sub at 07:39 UAE; listener stopped (no pushes yet: kickoff not reached). The subscription was DELETED (API 204; DynamoDB TIFOPUSH#6290/#6321 count 0); the autopush unregister timed out (harmless: no longer in our table). Resume: `PYTHONPATH=<pip target> python3 tools/push_e2e.py setup <a> <b>`, `listen <until-UTC> --stop-on-end`, `teardown` (tools/push_e2e.py; the aarch64 deps can be installed with `pip install --target /tmp/pwtest -r requirements-push-binary.txt` (platform flags) and `--no-deps -r requirements-push-pure.txt`).
