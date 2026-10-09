# Transfers for every club and every player, past and future — design

Owner, 2026-10-09: «الانتقالات موجودة بس للفرق العربية، نقدر نخليه لجميع اندية العالم وجميع اللاعبين سابقا ومستقبليا؟» → three
phases, all approved («الثلاث كلهن», design approved «نعم موافق»). Each phase ships on its own.

## What exists (measured 2026-10-09)

- `/transfers/`: the 10 Arab leagues, last 60 days, arrivals only (`more.py transfers_feed` → `v1/transfers/latest.json`).
- `/c/<key>/` «سوق الانتقالات»: the league page's ~100 latest moves (`comp/<cid>/transfers.json`, hourly).
- `/t/<id>/` «أغلى الصفقات في تاريخه»: Transfermarkt's top 5 bought/sold (`history/transfers.json`, weekly), only for clubs and
  players it matched.
- FotMob's `teams?id=` → `transfers.allTransfers` (this season's windows, January 2026 on) and `allRumours` (with a
  probability) for every club: db/world.py and db/fotmob_profiles.py already fetch it for ~4,000 clubs (cache
  `db/.cache/fm/t/`, 6-day TTL) and keep 150 moves in `world/club/<id>.json`, shown only on `/db/club/`, in the browser.
  Sample of 1,500 clubs: 7,050 rows, 5,888 distinct moves (each move is listed by both clubs), 417 contract extensions,
  1,054 with a fee.
- FotMob's `playerData` → `careerHistory.careerItems.senior.teamEntries`: every club of a player's career with its start
  date and transfer type (free, loan, …), no fee. `player/<id>/profile.json` keeps the career for site and world players.
- The news journal tags transfer stories with a stage (rumour < talks < agreed < here_we_go < official), keeps them 10
  days, and writes `news/transfers.json`, which no page reads.

## Phase 1 — the transfer market of every club in the world

**Data: `db/transfers_world.py`, stage `transfers_world` in db/refresh.py, daily.**
- Clubs: every club of `world/index.json` and of the site's `teams.json`.
- In a transfer window (June–September, January–February) each club's `teams?id=` is fetched again once it is older than
  20 hours (≈3,700 FotMob requests a day, 4 threads, spread over the run); outside the windows the 6-day cache serves.
  Risk flagged to the owner: FotMob may throttle; on errors the cached answer is used and the stage still publishes.
- Ledger: one row per move (a move listed by both clubs is one row: player + day + from + to), contract extensions out:
  `[date, player id, player name (Arabic first), from id, from name, to id, to name, fee EUR | null, kind, market value | null,
  nationality code | null, position | null]`; kind ∈ `fee`, `loan`, `free`, `undisclosed`, `` (unknown). Nationality from the
  clubs' squads (the `ccode` of each member).
- Out: `v1/transfers/all.json` `{generated, since, clubs: {id: [name, league id]}, moves: [...]}`, newest first.

**Site.**
- `/transfers/` (replaces the Arab-only page): the season's biggest fees, the latest moves worldwide, the Arab players'
  moves (Arab nationality, any league), and one link per league page.
- `/transfers/<league key>/` for each league competition the site tracks: this season's moves by club, arrivals and
  departures, money spent and received. In the sitemap.
- `/t/<id>/`: «انتقالات هالموسم» in the club's history tab (arrivals, departures, totals), from the same ledger.
- «هالموسم» = since 1 June (the previous year's June before June).
- Players link to `/p/<id>/` (the link check moves them to `/db/player/<id>/` when that is the page that exists), clubs to
  `/t/<id>/` (or `/db/club/?id=`).

## Phase 2 — every player's full transfer history

- From the career in `player/<id>/profile.json` (kept by db/fotmob_profiles.py and db/world.py): one move per club change
  (from the previous club to this one, on its start date, with FotMob's transfer type); a fee where Transfermarkt
  (`history/transfers.json`) or the phase 1 ledger has the same move.
- `/p/<id>/`: the full list (today the last 10, Transfermarkt only); `/db/player/<id>/`: the same list (today nothing).
- The profiles must keep each career entry's start date and transfer type (verify; add if dropped).

## Phase 3 — rumours and what comes next

- A lasting rumour ledger (`state/` private, `v1/transfers/rumours.json` public): player, from, to, the furthest stage, first and
  last seen, how many sources, credibility, and the outcome: «صدقت» when the phase 1 ledger shows the move, «ما صدقت» when the
  window closed without it. Sources: the news journal's transfer stories (players linked by `news/entities.py`) and FotMob's
  `allRumours` (with its probability).
- `/transfers/rumours/`, and «إشاعات» on club and player pages.
- «ينتهي عقده الصيف الياي»: players whose contract ends by next 30 June (`bio.contract`), by league.
- No AI at first: the keyword stages and the entity dictionary; Gemini Flash-Lite only if the from/to clubs prove too
  inaccurate (cents a day).
- Later (player follow phase 2): stage alerts read this ledger.

## Constraints

- Arabic copy, plain (no slogans); Western digits; fees as «€12.5 مليون».
- Nothing that changes every build on every page (no timestamps in shared markup).
- Uploads by the parallel boto3 path (`store.put_json` already).
- Every new pure function has a test; the site check is a limited build (`TIFO_ONLY`).
