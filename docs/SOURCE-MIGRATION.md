# Source migration: FotMob to API-Football

**Why this exists.** Tifo runs on FotMob's free, undocumented JSON (item 343). It can change shape, rate-limit or disappear
without notice. The outage alert (`poller.source_watch`) tells the owner within about 15 minutes. This document is the
plan for moving to a paid, documented source. The adapter seam already exists: `sources/apifootball.py`.

Prices and plan limits below come from memory of API-Football's public pricing page. The agent writing this could not
browse the web, so **every price and quota is marked "verify"**. Check <https://www.api-football.com/pricing> and
<https://www.api-football.com/documentation-v3> before buying.

## 1. How the switch works (nothing outside `sources/` changes)

1. **Implement the adapter.** `sources/apifootball.py` implements `day`, `competition`, `match` and `team`. It returns
   exactly the normalized shapes in `docs/SCHEMA.md` (`Match`, `MatchDetail`, `Standings`, `Leaders`, `Team`), with the
   same status mapping as its docstring. `sources/http.py` already counts ok and failed calls per host, so the outage
   alert works for any host once it is added to `Poller.SOURCE_KEYS`.
2. **Map the ids once.**
   - **Competitions:** add `ids: {apifootball: <league id>}` to each of the 46 entries in `competitions.yaml`.
   - **Teams:** build `teams_apifootball.yaml` (API-Football team id → FotMob team id) by name + country, then review the
     14 Pro League clubs and the Arab big clubs by hand.
   - **Players and matches:** new ids are allowed, but the ledgers, h2h files and `player/{id}` paths are keyed by
     FotMob ids. Keep FotMob ids canonical for anything already published. Use the provider's id only for new objects,
     with `ext_id: "apifootball:<id>"`, the convention uaepl.ae fixtures already use.
3. **Run both side by side for 2 weeks.** Add a `--shadow` option to `poller.py` that runs the new adapter into
   `out-shadow/` locally. Diff the day files, standings and match events against the live FotMob files every hour.
4. **Flip one competition at a time.** `competitions.yaml` gets `source: apifootball` per competition. Construct both
   adapters in `Poller.load()` and pick one per competition. Start with a European league, then 538 last.
5. **Keep FotMob for what API-Football lacks:**
   - the Arabic name map (`translationmapping`)
   - xG shot maps where FotMob has them
   - FotMob match ratings (API-Football has its own `players.rating`, on a different scale)

## 2. Endpoint map: our files → API-Football v3

The base URL is `https://v3.football.api-sports.io`, with the header `x-apisports-key`.

| our file(s) | today (FotMob) | API-Football v3 | calls |
|---|---|---|---|
| `live.json`, `day/{d}.json` | `/api/data/matches?date=` (one call, every competition) | `/fixtures?live=all` while live; `/fixtures?date=YYYY-MM-DD&timezone=Asia/Dubai` otherwise (filter our league ids) | 1 per pass |
| `match/{id}.json` (events, lineups, stats, referee, venue) | `matchDetails?matchId=` | `/fixtures?ids=A-B-C…` (up to 20 fixtures per call, with events, lineups, statistics and players inside) | 1 per 20 live matches per pass |
| `match/{id}.json` → `h2h` | inside `matchDetails` | `/fixtures/headtohead?h2h=A-B&last=30` | 1 per match, cache 7 days |
| `match/{id}.json` → `lineups.*.unavailable`, `comp/{id}/absences.json` | inside `matchDetails` | `/injuries?fixture=F` or `/injuries?league=L&season=Y` | 1 per league per day |
| `comp/{id}/standings.json` (+ `magic`, form, zones) | `/api/data/leagues?id=` | `/standings?league=L&season=Y` | 1 |
| `comp/{id}/fixtures.json`, `team/{id}.ics` | `/api/data/leagues?id=` | `/fixtures?league=L&season=Y` | 1 |
| bracket (`standings.bracket`), `draws/{id}.json` | `playoff` in the league page | `/fixtures/rounds?league=L&season=Y` + `/fixtures?league&round=` | 1–2 |
| `comp/{id}/stats.json` (leaders) | `fetchAllUrl` lists | `/players/topscorers`, `/players/topassists` (and `topyellowcards`, `topredcards`) | 2–4 |
| `comp/{id}/players.json`, cards, similar, finishing, u21, radar | ~29 per-player season lists | `/players?league=L&season=Y&page=N` (20 players per page, every stat per player) | ≈ 25–35 pages per league |
| `comp/{id}/transfers.json`, `transfers/latest.json` | league page transfers | `/transfers?team=T` (per team only) | 1 per club, weekly |
| `team/{id}.json` squad, coach, venue | `/api/data/teams?id=` | `/players/squads?team=T` + `/coachs?team=T` + `/teams?id=T` | 3 per team, daily |
| `national/uae-abroad.json`, `arabs/abroad.json`, careers | `playerData?id=` | `/players?id=P&season=Y` + `/players/teams?player=P` | 1–2 per player, weekly |
| history (ratings, records, archive, 2010/11+) | season fixtures per league | `/fixtures?league=L&season=Y` per past season | ≈ 550 once, then 0 |
| `comp/{id}/referees.json`, `referee_profile` | `infoBox.Referee` | `fixture.referee` (a name string, no id) | inside `/fixtures` |
| `xg.json`, `shots.json`, shot maps, `goal-types` body parts | shot map (xG coverage) | **no shot map, no xG per shot**. `statistics.expected_goals` per team where covered (verify) | n/a |
| Arabic names | `translationmapping?locale=ar` | not offered | keep FotMob or `teams_ar.yaml` |

Tifo files computed from our own data are unchanged: ratings, sims, facts, happiness, records and the rest of
`analytics.py` / `more.py` / `extra2.py`.

## 3. Request volume per day for our 46 competitions

**Measured today (FotMob, CloudWatch, 24 h to 2026-09-27 12:40 UTC).** The poller logged 1,040 runs and 3,553 requests,
peaking at 80 in one run. The analytics function logged 111 runs and 1,764 requests. That is **5,317 requests a day in
all**, including uaepl.ae and Open-Meteo. It was an international-break day, so it is a low day for live matches.

**The same work on API-Football, busy match day (for example a Saturday with the European leagues, Saudi, Qatar and
the UAE):**

| work | model | requests/day |
|---|---|---|
| live passes | ≈ 900 live minutes on a peak day (15,800 live minutes/month, about 37% of minutes, peaks at 2× average) × 3 passes × (1 `live=all` + 1 batched `fixtures?ids=`) | ≈ 5,400 |
| pre-match (lineups, the 75 min before kickoff) | 60 tracked matches × 38 two-minute checks, batched 20 per call | ≈ 120 |
| competitions (standings + fixtures) | 46 × 2 hourly while in season (≈ 30 in season) + dormant daily | ≈ 1,500 |
| leaders | 46 × 2 hourly (reduce to 3-hourly: ≈ 740) | ≈ 2,200 |
| player season tables | 16 `player_stats_comps` × ≈ 30 pages, daily | ≈ 480 |
| teams (focus clubs + national team) | ≈ 30 × 3, daily | ≈ 90 |
| h2h, injuries, abroad players, careers | cached daily or weekly | ≈ 400 |
| history backfill | ≈ 550, once | 0 after week 1 |
| **total, busy day** | | **≈ 10,000** (≈ 8,500 with 3-hourly leaders) |
| **total, quiet day** | no live matches | **≈ 3,000** |

## 4. Plan tier (all prices: verify)

**The rule:** pick the smallest plan whose **daily cap is at least 2× the busy day**, so at least 20,000 requests a day.
Also check the per-minute limit against the live burst: about 6 requests a minute from the poller, plus up to about 60
in a minute while the hourly competition refresh runs.

| plan (API-Football, monthly) | requests/day | price/month | fits? |
|---|---|---|---|
| Free | 100 (verify) | $0 | no. Only enough to write and test the adapter |
| Pro | 7,500 (verify) | ≈ $19 (verify) | no. Below the busy day even before the 2× margin |
| **Ultra** | **75,000 (verify)** | **≈ $29 (verify)** | **yes, with about 7× headroom. Choose this one** |
| Mega | 150,000 (verify) | ≈ $39 (verify) | only if we add every Arab league's second division |

- **Start:** Free to build and shadow-test the adapter on a few competitions, since the shadow run can be throttled to
  about 90 calls a day. Buy Ultra the week of the flip.
- **Downgrade path:** trim leaders to 3-hourly and the dormant competitions to daily, which gives about 8,500 on a busy
  day. That still does not fit Pro with the 2× margin, so Ultra stays the floor.

**Coverage to verify on the key before paying** (league ids are not verified either):
- The UAE Pro League, League Cup and President's Cup, with lineups and events for 538.
- The Arab leagues where FotMob is thin: Iraq (524), Kuwait (529), Algeria (516), Tunisia (544) and Morocco (530).
  FotMob gives them results only, with no lineups, referees or substitutions.
- AFC Champions League Elite / Two and the CAF competitions.

API-Football's per-league `coverage` flags (`/leagues?id=L`: `events`, `lineups`, `statistics_fixtures`, `players`)
answer this with one call per league.

## 5. What gets better, and what gets worse

- **Better:**
  - a contract and documentation
  - referee names on every covered match
  - `injuries`
  - lineups for leagues where FotMob has none (to verify)
  - ISO kickoff times, with no Oslo-time trap
- **Worse:**
  - no shot maps or per-shot xG, so `shots.json`, `goal-types` body parts and `finishing` fall back to the proxy
  - no FotMob ratings: cards, `team-of-round` and `form` need re-calibration against `players.rating`
  - no Arabic names

## 6. Checklist for the flip

1. Buy Ultra (verify the price). Store the key in SSM as `/elyoxe/football/apifootball_key`. The Lambda reads it at cold
   start; never put it in the repo.
2. Map the ids (`competitions.yaml` `ids.apifootball`, `teams_apifootball.yaml`) and review the teams.
3. Add a fixtures test: record 5 API-Football responses into `tests/fixtures/` and assert the normalized shapes.
4. Run the 2-week shadow diff.
5. Flip one competition at a time. `health.json` shows `source:fotmob` / `source:apifootball` per run.
6. Keep the FotMob adapter as the fallback for 3 months.
