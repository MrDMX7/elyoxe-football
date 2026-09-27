# Tifo data: normalized schema v1

Tifo is the brand; it will live at `tifo.elyoxe.com`, but DNS is not set up yet. AWS resource names stay `elyoxe-football-*`.

Every file the poller publishes, and every object the adapters in `sources/` return, follows this
document. The adapters are `fotmob.py` (main), `uaepl.py` (official fallback) and `apifootball.py`
(an interface stub). Nothing outside `sources/` knows which provider supplied the data. To switch
providers, write one adapter that returns these shapes.

- **Base URL:** `https://<distribution>.cloudfront.net/`. It maps to `s3://elyoxe-football-574771023173-ap-south-1/v1/`.
- **Format:** every `.json` is gzip-encoded (`Content-Encoding: gzip`), so use `curl --compressed`. Access is CORS `*`.
- **`.ics`:** stored plain and compressed by CloudFront.

## Conventions

- **Ids:** FotMob's numeric ids (int) are canonical for competitions, teams, players and matches. `competitions.yaml` maps other providers (`ids:`); teams have `teams_ar.yaml` (uaepl slugs). A uaepl.ae fixture that FotMob has not published yet has `id: null` and `ext_id: "uaepl:<uuid>"`.
- **Time:** always two fields.
  - `kickoff_utc` is `2026-10-16T13:05:00Z`, taken from FotMob `status.utcTime`.
  - `kickoff_uae` is `2026-10-16T17:05:00+04:00`.
  - `time_tbd: true` means the date is known but the hour isn't. Asian Cup group games are like this.
  - `date_tbd: true` means neither is known (uaepl.ae rounds 7–26).
- **FotMob's other clock:** strings like `26.09.2026 17:57:03` (period starts, the day feed's `time`) are **Europe/Oslo wall-clock time with daylight saving**.
  - That is UTC+2 from late March to late October and **UTC+1 in winter**. `10.01.2027 15:00` = 14:00Z.
  - The research note's "UTC+2" was only the summer case. `timeutil.parse_fotmob_local` uses zoneinfo, and `tests/test_time.py` pins both cases.
- **UAE day:** `day/YYYYMMDD.json` is a UAE calendar day (FotMob `&timezone=Asia/Dubai`). 21:30Z already belongs to the next day.
- **Order:** tables keep the **source's order** (`"order": "source"`). They are never re-sorted, because tie-breakers differ by league.
  - Computed tables (half-time, xG) say `"order": "computed: ..."`.
- **Names:**
  - `name` is FotMob's English name.
  - `name_ar` comes from FotMob's translation map (`translationmapping?locale=ar`, refreshed daily), overridden by `teams_ar.yaml`. The 14 Pro League clubs use the official uaepl.ae names.
  - Players have **no Arabic names** anywhere. FotMob's map covers teams and competitions only.
- **Logos:** `https://images.fotmob.com/image_resources/logo/teamlogo/{id}.png` (hotlinked, not mirrored yet).

## Cache classes

| class | Cache-Control | used for |
|---|---|---|
| live | max-age=10 | `live.json` |
| hot | max-age=20 | `day/<today>.json`, live `match/{id}.json`, `index.json`, `health.json` |
| warm | max-age=300 | standings, fixtures, stats, other days, upcoming matches |
| static | max-age=3600 | finished matches, teams, `.ics`, aggregates, h2h |

The CloudFront cache policy honours each object's max-age (MinTTL 1 s). Unchanged content is not re-uploaded: an MD5 of the gzip body is kept in state.

## File list

| path | content | refreshed |
|---|---|---|
| `index.json` | competitions (ids, Arabic names, season, next kickoff, dormant flag, file paths), focus teams, live count | every run |
| `live.json` | tracked matches that are live, kick off within 6 h, or finished within 4 h | every 20 s while live, 10 min idle |
| `day/YYYYMMDD.json` | every tracked match on that UAE day | today: 20 s live / 10 min idle; yesterday and tomorrow: hourly |
| `match/{id}.json` | MatchDetail | 20 s while live; at full time; hourly for UAE and national-team matches in the next 48 h; every 2 min in the 75 min before kickoff; backfill for finished matches |
| `comp/{id}/standings.json` | Standings (+ `magic`, `last_season_same_round`) | hourly (daily when dormant; every 2 min while the competition is live) |
| `comp/{id}/fixtures.json` | the season's matches (enriched) | same as standings |
| `comp/{id}/stats.json` | Leaders: top scorers, assists, goals+assists | hourly |
| `comp/{id}/transfers.json` | latest ~100 league transfers grouped by team (in/out) | hourly |
| `comp/{id}/referees.json` | referee aggregates | when the ledger changes (≥ 30 min apart) |
| `comp/{id}/halftime.json` | half-time table | same |
| `comp/{id}/goal-bands.json` | goals for and against in 15-minute bands | same |
| `comp/{id}/xg.json` | xG table and luck index (or `available: false`) | same |
| `comp/{id}/shots.json` | per-player season shot list (or `available: false`) | same |
| `comp/{id}/players.json` | per-player season stats, per-90 values, league percentiles (radar) | daily, for `player_stats_comps` (538, 536, 535) |
| `comp/{id}/foreigners.json` | best non-national players of the league | daily, same competitions |
| `team/{id}.json` | Team: squad, all fixtures, transfers, venue | daily for focus teams (UAE national team + every club in 538/11027) |
| `team/{id}.ics` | iCalendar feed of the team's matches | with every competition refresh; daily for focus teams |
| `teams.json` | every team seen: name, name_ar, logo, competitions | every run |
| `national/5789/qualifying.json` | the UAE's group table and that group's remaining fixtures per qualifying competition | with 290, 329, 10197, 10609 |
| `national/uae-abroad.json` | UAE nationals at clubs outside the UAE, with their main-league season stats | daily |
| `h2h/{a}-{b}.json`, `h2h/index.json` | full head-to-head list for each pair of current Pro League clubs (`a` < `b`) | weekly per pair |
| `health.json` | per source and file: ok, error, time, last_ok; last run (mode, seconds, requests, written). `source:fotmob` = the outage watch (failing for N min: last error) and `source-alert` = the last alert mail (see "Source outage alert") | every run (poller) |
| `health-analytics.json` | the same for the analytics function | every 10 min |

## Objects

### Match (summary): in `day/`, `live.json`, `fixtures.json`, team fixtures

```jsonc
{
  "id": 1000021961, "ext_id": null, "comp": 538, "comp_name_ar": "دوري أدنوك للمحترفين",
  "season": "2026/2027", "round": "6", "stage": null, "group_id": null,
  "kickoff_utc": "2026-10-16T13:05:00Z", "kickoff_uae": "2026-10-16T17:05:00+04:00",
  "time_tbd": false, "date_tbd": false,
  "status": "scheduled",          // scheduled | live | ht | finished | postponed | cancelled | abandoned | awarded | unknown
  "status_detail": null,          // FT, AET, Pen, PP ...
  "minute": null,                 // "67", "45+2", "HT" while live
  "score": null,                  // {"home": 2, "away": 3}
  "penalties": null,              // shoot-out {"home": 3, "away": 4}
  "home": {"id": 102118, "name": "Al-Dhafra", "name_ar": "الظفرة", "logo": "https://..."},
  "away": {"id": 1552577, "name": "United FC", "name_ar": "يونايتد", "logo": "https://..."},
  "venue": {"id": "hamdan-bin-zayed-stadium", "name_ar": "استاد حمدان بن زايد", "name_en": "...",
            "city": "Madinat Zayed", "emirate": "abu-dhabi", "lat": 23.669151, "lon": 53.69423, "in_uae": true},
  "weather": {"available": true, "hour_utc": "...Z", "temp_c": 33, "humidity": 60, "apparent_c": 38,
              "heat_index_c": 41.2, "heat_category": "danger", "precip_prob": 0, "wind_kmh": 12,
              "weather_code": 0, "source": "open-meteo", "fetched": "..."},
  "prayer": {"method": "uae-awqaf-18.2", "estimated_window": true,
             "times_uae": {"fajr": "05:07", "sunrise": "06:20", "dhuhr": "12:14", "asr": "15:32", "maghrib": "18:02", "isha": "19:16"},
             "clashes": [{"prayer": "maghrib", "at_utc": "...", "at_uae": "18:02", "minute_of_play": 57, "segment": "halftime"}]},
  "source": "fotmob"
}
```

- **`venue`, `weather`, `prayer`:** only for UAE club competitions (538, 11027, 9943, 11026), UAE national-team matches, and any match whose venue we know.
- **`weather` and `prayer`:** only when the venue is in the UAE and the kickoff hour is fixed.
- **`weather` unavailable:** `{"available": false, "reason": ...}` beyond Open-Meteo's 16-day horizon.
- **`kickoff_official_uaepl`:** appears when uaepl.ae lists a different kickoff than FotMob.

### MatchDetail (`match/{id}.json`)

Everything in the Match summary, plus the following:

| field | content |
|---|---|
| `coverage` | FotMob coverage level: `xG` (shot map, momentum, xG), `ratings` (UAE Pro League), or `lower` (League Cup) |
| `periods` | real UTC starts and ends of each half (`firstHalfStarted`, ..., `gameEnded`), converted from Oslo time |
| `halftime_score` | `{"home", "away"}`, the score at the HT marker |
| `venue` | resolved stadium (above) plus `distance_km: {abu-dhabi, dubai, ..., al-ain}` in a straight line |
| `referee` | `{id, name, country, source_stats}`. `source_stats` is FotMob's own block: matches, yellow (total, per match, league average per match), red, penalties, fouls, and its scope competition (`scope_comp` may be another competition) |
| `attendance` | when the source has it |
| `events[]` | `{type, minute, added, team: "home"/"away", team_id, player{id,name}, assist{id,name}, player_out, score{home,away}, detail, reason_key, var_outcome, clip}` |
| `lineups` | `{type: "standard"/"lastStarting11", home/away: {formation, coach, starters[], subs[], unavailable[]}}`. Players are `{id, name, number, position_id, country, captain, rating}`; `country` is the nationality. `unavailable[]` is `{id, name, type: injury/suspension, expected_return}` |
| `stats[]` | groups `{key, title, items: [{key, title, home, away}]}`: possession, shots, passes, defence, duels, discipline |
| `xg` | `{"home", "away"}`, or null without xG coverage |
| `shotmap` | `{player_id: {name, team, shots: [{minute, added, result, xg, xgot, x, y, on_target, blocked, body, situation, own_goal, inside_box}]}}`, or null |
| `momentum` | `[{minute, value}]` (+ = home pressure), or null |
| `highlights` | `{url, image, source}`. For UAE matches this is the official `@uaeproleague` YouTube video, as FotMob links it |
| `h2h` | `{summary: {home_wins, draws, away_wins}, matches: [{id, kickoff_utc, comp, home, away, score}]}`, at the full depth FotMob gives (16–27 meetings for Pro League pairs) |
| `weather_source` | FotMob's current-weather block, when present |
| `coverage_events` | `{subs, cards}`: whether the source's event feed reports them for this match. `subs: false` = past 60' (or finished), lineups present, not one substitution event (the source did not report them; it does not mean nobody came on). `cards: false` = the same case with no card either (with subs reported, zero cards is a real zero). The Gulf Cup (329) feed has only goals and half markers live; cards appear later on some matches, substitutions never (checked 2026-09-27 on all 7 matches) |

**Commentary feed:** every event has a stable `event_id`: `{match}-{type}-{minute}-{added}-{player}`, plus `-2`, `-3` for identical repeats.
- It depends only on the event itself, not its position, so an event FotMob adds late does not renumber the others. The site can key generated commentary lines by `event_id`.
- While a match is live each event also gets `first_seen` (UTC, when the poller first saw it). The finished file keeps those stamps.
- The event log is `events[]` in `match/{id}.json`, refreshed every 20 s while live.

`events[].type` takes these values:

- **Goals:** `goal`, `own_goal`, `penalty_goal`, `missed_penalty`.
- **Cards:** `yellow`, `second_yellow`, `red`. `detail`/`reason_key` give the card reason, e.g. "Foul" `card_desc_foul`, "Simulation", "Time wasting".
- **Substitutions:** `sub`. `player` = in, `player_out` = out, `detail: "injury"` when the player went off injured.
- **VAR:** `var`. `reason_key` is FotMob's decision key (e.g. `var_penalty_cancelled`), `detail` is its text, and `var_outcome` is one of `goal_disallowed`, `goal_disallowed_offside`, `offside`, `goal_confirmed`, `penalty_cancelled`, `penalty_awarded`, `card_changed`, `card` or `other`.
- **Match markers:** `half` (`detail` HT/FT), `added_time` (`detail` = minutes added).
- **Shoot-out:** `shootout_goal`, `shootout_miss`.
- **`clip`:** a per-event highlight URL when FotMob has one.

### Standings (`comp/{id}/standings.json`)

```jsonc
{
  "comp": 538, "season": "2026/2027", "composite": false, "order": "source", "source": "fotmob",
  "groups": [{"id": 538, "name": null, "rows": [
    {"rank": 1, "team": {...}, "played": 5, "won": 4, "drawn": 1, "lost": 0, "gf": 11, "ga": 2, "gd": 9, "pts": 13,
     "deduction": null, "form": ["W","W","W","W","D"], "zone": {"label": "AFC Champions League", "color": "#c9dd03"},
     "live": false,                                          // true while that team is playing
     "last_season_same_round": {"played": 5, "pts": 10, "gf": 9, "ga": 4}}   // null if not in the league last season
  ]}],
  "legend": [{"label": "AFC Champions League", "key": "...", "color": "...", "ranks": [1, 2]}, ...],
  "bracket": [{"stage": "1/2", "ties": [{"home": {...}, "away": {...}, "tbd": true, "matches": [6052094], "aggregate": {...}, "winner": null}]}],
  "last_season": "2025/2026",
  "magic": {...}
}
```

- **Group tournaments:** these (Gulf Cup, AFC, UEFA league phase) have several `groups` and `composite: true`.
- **uaepl.ae fallback:** a table built from uaepl.ae has `source: "uaepl"`, no `form` and no `zone`.

`magic` covers round-robin leagues only, where `magic` is not false in competitions.yaml:

```jsonc
{"method": "...", "matches_per_team": 26,
 "bands": [{"key": "title", "top": 1}, {"key": "top2", "label": "AFC Champions League", "top": 2}, ..., {"key": "safety", "top": 12}],
 "teams": {"102101": {"pts": 13, "remaining": 21, "max": 76,
                      "title": {"needed": 64, "state": "open", "own_hands": false, "wins_needed": null}, ...}}}
```

- **`needed`:** the points the team still needs to **guarantee** finishing in the band. It assumes every rival wins every remaining game and that ties go against the team (tie-breakers ignored), so it is conservative.
- **`state`:** `clinched`, `open` or `eliminated`.
- **`own_hands`:** `needed <= 3 × remaining`.
- **Remaining games:** these come from `matches_per_team`, because FotMob publishes only the dated rounds.
- **Bands:** they come from the table legend. The Pro League 2026/27 bands are:
  - 1–2 ACL Elite
  - 3 ACL Elite qualification
  - 4 ACL Two
  - 13–14 relegation

### Leaders (`comp/{id}/stats.json`)

`{comp, season, lists: {goals: [...], assists: [...], goals_assists: [...]}}`. Each entry is `{rank, player{id,name}, team, value, matches, minutes}`: the full list from FotMob's `fetchAllUrl`, or its top three if that fails.

### Team (`team/{id}.json`)

The team fields are `{id, name, name_ar, logo, short_name, country, national, primary_comp, venue{name, city, lat, lon}, coach, source}`, plus these:

- **`squad`:** `[{group: keepers/defenders/midfielders/attackers, players: [{id, name, number, position, country, club, club_id, age, goals, assists, yellow, red, injury, abroad}]}]`.
  - `country` is the nationality (club squads).
  - In the national team `club`/`club_id` are the player's club, and `abroad` = the club is not a UAE Pro League/League Cup club.
- **`fixtures`:** every competition, including friendlies.
- **`transfers`:** `{in: [...], out: [...]}`, each `{player, position, date, from, to, free_agent, fee, fee_eur, loan, type, extension}`.

### Season aggregates (from the ledger of stored final match details)

| file | content |
|---|---|
| `referees.json` | `referees: [{id, name, country, matches, yellow, second_yellow, red, penalties, var, yellow_per_match, penalties_per_match, match_ids, source_stats}]`. `red` includes second yellows; `penalties` = scored + missed |
| `halftime.json` | `rows: [{rank, team, played, won, drawn, lost, gf, ga, gd, pts}]` as if every match ended at half-time |
| `goal-bands.json` | `bands: ["1-15","16-30","31-45+","46-60","61-75","76-90+","extra-time"]`, `teams: {id: {for: {...}, against: {...}, matches}}`. Stoppage time counts in its half's last band, and own goals credit the side that benefited |
| `xg.json` | `rows: [{rank, team, played, xg_for, xg_against, xg_diff, xpts, pts, gf, ga, luck}]`. `xpts` uses independent Poisson goals with the match xG as means; `luck = pts − xpts` |
| `shots.json` | `players: {id: {name, team, shots, goals, xg, list: [[match, minute, xg, result, x, y, xgot], ...]}}` |
| `players.json` | `players: {id: {name, team, minutes, stats: {stat: {value, per90, pct}}}}`, plus `averages` and `min_minutes` (270). Built from FotMob's ~29 per-player season lists (goals, rating, accurate passes, tackles, ...). Lists FotMob publishes **per 90** (title "… per 90": shots, shots on target, accurate passes, long balls, dribbles, tackles, interceptions, clearances, blocks, recoveries, defensive actions, saves, goals conceded, fouls) keep `value` = `per90` = the source rate and add `total` = rate × minutes / 90 (an estimate: the rate is rounded to 0.1). Before 2026-09-27 these were divided by minutes a second time |
| `foreigners.json` | top 25 non-nationals by FotMob season rating, then goals + assists. Nationality comes from squads and lineups |

The ledger fills as matches finish. A backfill cursor also fetches up to 6 already-finished matches per idle minute (UAE competitions first) until the current season is complete.

## Tifo analytics (the `elyoxe-football-analytics` function, every 10 min, never in the live loop)

| path | content |
|---|---|
| `ratings/uae-clubs.json` | Tifo rating table: `teams: [{team, name_ar, rating, rank, change_5, in_league}]`, params, calibration (Brier). Model in docs/TIFO-RATING.md |
| `ratings/team/{id}.json` | rating history for charts: `history: [[date, rating_after, match_id], ...]` since 2010/11 |
| `ratings/national.json` | national-team Elo (martj42 + FotMob): UAE rating, world position, top 60, unmatched names |
| `comp/538/sim.json` | 10k-season Monte Carlo: `teams: {id: {exp_pts, positions: [P(1st)...], title, ranks_1_2, ranks_3_3, ranks_4_4, relegation}}`, `fixtures_check` |
| `comp/{id}/scenarios.json` | any group or league with ≤ 8 games left: every W/D/L combination → per team best/worst position and `next_result: {W,D,L: {best, worst}}` |
| `comp/{id}/live-table.json` | while live (poller, 20 s): the table re-ranked with the newest live scores (`rank_before` = source rank) |
| `comp/{id}/bump.json` | leagues: `positions: {team: [position after round 1, 2, ...]}` (computed order) |
| `comp/{id}/tournament-sim.json` | 329, 290: `teams: {id: {group_positions, reach_1/8 ... reach_final, reach_winner}}` |
| `comp/538/facts.json` | per upcoming match (21 days): items `{team, kind (unbeaten/winning/winless/losing/scoring/clean_sheets/home_unbeaten/away_unbeaten/weekday/h2h), current, record, record_at_stake, text_ar}`. Records are qualified «منذ 2010/2011 (بيانات FotMob)» |
| `comp/538/watch.json` | watchability per upcoming match: `{score 0-100, closeness, derby, stakes, form}` |
| `comp/538/pressure.json` | coach-pressure index per team: `{coach, games, ppg, xppg, losing_streak, winless_streak, index}` (formula in compute/clubs.py) |
| `comp/538/fatigue.json` | per team: `matches_14d, days_since_last, days_to_next, afc_away_trips_30d [{match, venue, city, km}], afc_km_30d` |
| `comp/538/coaches.json` | per club: current coach + FotMob coachHistory (coach, season, W/D/L, ppg) |
| `comp/538/fortress.json` | per stadium: home team's league home record since 2010/11, current and longest unbeaten run |
| `comp/{id}/clutch.json` | points added by goals and assists (winners, equalisers): `players: [{id, team, from_goals, from_assists, total, winners, equalisers}]` |
| `comp/{id}/minute-clock.json` | goals per minute (index 1-120) league-wide and per team (for/against) |
| `comp/{id}/lineup-ages.json` | per round: average age of every starting XI, youngest and oldest |
| `comp/{id}/rotation.json` | starting-XI changes game to game, per team and per coach |
| `comp/{id}/team-of-round.json` | best XI per round (4-3-3) from FotMob match ratings |
| `comp/538/style.json` | team style fingerprint (possession, shots, passes, directness, crosses, ppda pressing proxy, territory, box touches, aerials, xG where present) and the nearest European teams (47, 87, 55, 54, 53) |
| `comp/{id}/cards.json` | Tifo player card: `{overall, parts: {finishing, creating, passing, dribbling, defending, work_rate}}` (keepers: shot_stopping, clean_sheets, distribution ...), 40-99 |
| `comp/{id}/improved.json` | FotMob season rating vs last season: biggest rises and falls |
| `comp/538/young-uae.json` | UAE nationals aged ≤ 23 (date of birth), ranked by rating then (G+A)/90 |
| `comp/538/similar.json` | 8 most similar players (per-90 cosine) for every Pro League player, pool = 538, 536, 535, 47, 87 |
| `player/{id}.json` | season card for share images: minutes, rating, goals, assists, shots, chances, tackles, card overall, clutch points, dob, nationality, number |
| `comp/538/records.json` | all-time scorer chase: `{name, goals_all_time, needs_to_equal, needs_to_pass, next_rank_name, goals_this_season}` (as of the Wikipedia revision in `as_of`) |
| `comp/538/alltime.json` | champions since 1973-74 (with runner-up), titles per club, all-time top 30 scorers: facts from Wikipedia (revision id) citing RSSSF; 2010/11+ cross-checked against FotMob |
| `comp/538/loans.json` | players the UAE clubs loaned out: current club, main-league stats |
| `leagues/compare.json` | 538 vs 536, 535, 47, 87: goals per match, home-win and draw %, average squad age, foreign share, attendance (where reported) |
| `national/5789/fifa.json` | UAE FIFA ranking since 1992: `{date, rank, points, afc_rank, arab_rank}` (FIFA API) + FotMob's current ranking |
| `match/{id}.json` → `winprob` | live and finished matches: `[[minute, pH, pD, pA], ...]`, one point per minute plus one at every goal and red card. `winprob_prematch: {p, source}` with source `tifo-ratings`, `tifo-arab_ratings`, `national-elo` or `base-rates`. Model: Poisson remaining goals (compute/winprob.py) |
| `models/danger.json` | the xG-proxy fit (coefficients, n, R² vs xG, correlation with goals). `comp/{id}/xg.json` then has `"proxy": true` for competitions without source xG |
| `comp/{id}/records-book.json` | the Arab leagues in `records_comps`: `biggest_wins`, `highest_scoring`, `streaks {winning, unbeaten, losing, winless}` (with `from_match`, `to_match`, `current`), `most_goals_in_season`, `hat_tricks`, `fastest_goals`, all with match ids. Result records cover every FotMob season; hat-tricks and fastest goals cover this season's stored events |
| `national/{id}/archive.json` | the 22 Arab national teams: every international result (martj42 since 1872; the UAE from 1972-03-17): `matches: [{date, opponent {name, id, name_ar}, home, neutral, gf, ga, result, competition, venue {city, country}, match}]` and `h2h` per opponent (W/D/L, goals, first, last) |
| `national/archives.json` | index of those archives |
| `national/countries.json` | 22 Arab countries plus the big-5 countries: `iso2`, `name_ar`, `name_en`, `arab`, national `team` id, domestic `competitions` |
| `ratings/arab-clubs.json` | Arab clubs rating (one scale across the Arab leagues, linked by AFC/CAF/Arab club competitions): top 100 with country and trend (docs/TIFO-RATING.md) |
| `match/{id}.json` → `events[].event_id`, `first_seen` | stable event ids for commentary (see "Commentary feed") |
| `match/{id}.json` → `firsts` | inside our data: `first_meeting` (no earlier meeting in FotMob history since 2010/11), `first_appearance_season`, `first_goal_season` (this season's stored matches) |
| `…probs.scores`, `probs.expected_goals` | on every scheduled match with a rated pair: exact-score probabilities, a 6×6 grid [home goals 0–5][away goals 0–5] from the Poisson rates behind the W/D/L probabilities |
| `player/{id}.json` → `form` | last 10 stored appearances, all competitions: `[[match, date, rating, minutes, goals, assists], ...]` |
| `player/{id}/teammates.json` | top 30 teammates by matches together (stored lineups; rolling cursor, up to 3,000 players per run every 3 h, so every player with a stored lineup has one within two runs) |
| `player/{id}/career.json` | FotMob career: `senior` / `national_team` clubs with dates, apps, goals, assists, loan. Written for league top-30 scorers/assisters and Arab players abroad, refreshed weekly |
| `team/{id}/history.json` | every result since 2010/11 across the history competitions: `[date, comp, opponent, gf, ga, result, H/A, match]` (clubs in the analytics leagues, rolling cursor) |
| `comp/{id}/seasons.json` | leagues: per season since 2010/11, the computed final table plus `goals_per_game`, `home_win_pct`, `draw_pct`, `title_margin`, `champion`; `avg_age`/`foreign_share_pct` for the current season |
| `comp/{id}/milestones.json` | players within 5 goals or 10 apps of 50/100/150/200/250/300 for a club or the national team (FotMob career) |
| `comp/{id}/upsets.json` | per season: wins by a side whose pre-match win probability was < 20% (Tifo rating, predicted before the match) |
| `comp/{id}/projections.json` | top scorers and assisters projected to the season end at their current per-match rate |
| `comp/{id}/bracket-sim.json` | knockout cups and continental competitions: Monte Carlo reach probabilities per round (Tifo club rating) and `ties` for two-legged rounds (aggregate, `needs.trailing_needs_to_win_by`, live flag) |
| `comp/{id}/scenarios.json` → `arab_clubs` | AFC/CAF groups list their Arab clubs (group scenarios for every group with ≤ 8 games left) |
| `comp/{id}/games-in-hand.json` | overdue (kickoff passed, not played) matches, games in hand, projected points with overdue games at expected points, adjusted rank |
| `comp/{id}/local-minutes.json` | minutes by nationals vs foreigners per club and league (lineup nationality vs league country). `source_coverage` as in subs; `available: false` when no stored match has a lineup |
| `comp/{id}/first-goal.json` | per team: record when scoring first / conceding first, comebacks |
| `comp/{id}/dropped.json` | points dropped from winning positions and won from losing positions |
| `comp/{id}/red-impact.json` | record when playing 11v10 / 10v11 after the first red card, and points gained or lost after it |
| `comp/{id}/goal-types.json` | per team and player: header / right_foot / left_foot (+set_piece, +outside_box) / penalty / free_kick, with `coverage` (shot map or FotMob goal description). `available: false` + `reason` when no goal has a type. As of 2026-09-27 that is 538, 11027, 525, 9469, 535, 530, 516, 544, 524, 529 and 10721, where FotMob gives neither a shot map nor a goal description, only penalties; 9468 has no goals stored yet. Egypt (519) has xG coverage and is typed |
| `comp/{id}/dependence.json` | share of team goals from the top scorer and top 2 |
| `comp/{id}/subs.json` | substitutes' goals/assists and points added per player and per coach; result-changing sub goals. `source_coverage {matches, with_lineups, with_subs}`; `available: false` + `reason` when FotMob lists no substitutions for the competition |
| `comp/{id}/xi.json` | starts per player, formations used, most common starting XI and the 11 most-used players |
| `comp/{id}/workload.json` | minutes in the last 30 days and last 5 matches (all competitions) with `overload` (≥ 540 min in 30 days, or ≥ 450 min over 5 matches within 18 days). `available: false` + `reason` when the league has no stored lineups |
| `comp/{id}/signings.json` | this season's incoming transfers ranked by FotMob rating × min(1, minutes/900) at the new club |
| `national/{id}/squad.json` | 22 Arab national teams: FotMob's current squad (latest call-up) with each player's club |
| `callups/{club_id}.json` | the club's players currently in an Arab national squad |
| `players/birthdays/MM-DD.json` | players born on that day: FotMob dates of birth + Wikidata P569 for players in `names/players_ar.json` with a QID |
| `transfers/latest.json` | incoming moves at clubs in the Arab leagues, last 60 days, newest first |
| `arabs/abroad.json` | Arab nationals who played in the big five or UEFA club competitions this season: nationality (ISO2 + Arabic), club, apps, minutes, goals, assists, average rating, league season stats |
| `arabs/day/YYYYMMDD.json` | Arab players' appearances abroad that UAE day: minutes, goals, assists, rating, match |
| `arabs/week/YYYY-WW.json`, `arabs/week/latest.json` | star of the week and top 5 (rating + 1×goals + 0.7×assists, last 7 days) |
| `arabs/tonight.json` | next 48 h (and last 30 h) abroad matches with Arab players in either squad; `performance` after the match |
| `arabs/clashes.json` | AFC/CAF/Arab club competition matches between two Arab clubs, ±45 days |
| `arabs/national.json` | 22 Arab national teams: FIFA rank, Tifo national rating and world/Arab position, next match, last result, current qualification groups |
| `arabs/u21.json` | Arab-league players ≤ 21 with ≥ 450 minutes, by rating then (G+A)/90 |
| `arabs/coefficients.json` | AFC association ranking and CAF association + club 5-year ranking (Wikipedia revision + the sources it cites; `arab` flag and Arabic country) |
| `arabs/calendars.json` | per Arab league: first and last published match, breaks of 12+ days; national-team match windows |
| `arabs/streaks.json` | running streaks (≥ 3) across the Arab leagues: unbeaten, winning, clean sheets, winless, losing |
| `derbies.json`, `h2h/{a}-{b}.json` | the 12 big Arab derbies (derbies.yaml) with Arabic names, city and full FotMob head-to-head: `{teams, name_ar, wins {a, b, draws}, matches [{id, kickoff_utc, comp, home, away, score}], via_match, sources [FotMob match page, matchDetails API URL], check {stored_league_meetings, missing_from_list, score_differs}}`. The list is FotMob's h2h block of the latest **finished** meeting plus that meeting itself (the block lists only earlier games); `check` compares it with the league meetings in our season history. A run with no h2h block is retried next run, not in a week |
| `archive/index-all.json`, `archive/all/{season}.json` | every stored result by July–June season: `[id, date, comp, home, away, hs, as]` |
| `guide/{iso2}.json` | per country: the next 3 days of covered matches with their broadcasters (research/tifo-2026-09-27/broadcast_by_country.json × fixtures) and `by_broadcaster` |
| `comp/{id}/referees.json` → `foreign`, `home`, `away`, `available` | referee nationality vs the league's country; yellows, reds and penalties against the home/away side. `available: false` + `reason` where FotMob names no referee (530, 516, 544, 524, 529, 9468, 329 as of 2026-09-27) |
| `national/{id}/team.json` | 22 Arab national teams: the full team object (squad with clubs, fixtures and results in every competition, coach, venue, FIFA rank), as `team/5789.json` |
| `national/{id}/fifa.json` | FIFA ranking history since 1992 for each Arab national team (rank, points, confederation rank, Arab rank), plus FotMob's current rank |
| `arabs/continental-history.json` | every AFC/CAF/Arab club-competition meeting of two Arab clubs FotMob has (since 2010/11, CAF since its first stored season), with a win/draw summary per country pair |
| `arabs/coaches.json` | Arab-nationality head coaches of covered clubs and of the 22 national teams; `abroad` = coaching outside their own country |
| `arabs/referees.json` | Arab-nationality referees of stored AFC/CAF/FIFA matches this season |
| `arabs/friendlies.json` | club friendlies (FotMob 489) of clubs in the covered Arab leagues |
| `team/{id}/month/YYYY-MM.json` | Arab-league clubs, current and previous month: results, W/D/L, top 5 performers (average match rating, goals, assists), Tifo rating at month start/end, table position at month start/end |
| (private) weekly accuracy report | not in v1/: Lambda `elyoxe-football-report` e-mails the owner every Monday 08:00 UAE (hit rate, Brier vs base rates, calibration, biggest misses; report.py) |
| `arabs/match-of-week.json` | the week's pick (Monday, next 7 days) among matches with an Arab club or national team, plus a shortlist; score = 0.6×watchability + derby + stage + Arab-vs-Arab |
| `arabs/golden-boot.json` | league goals by Arab nationals (Arab leagues + big five), raw and weighted by league strength; weight = 10^((mean Tifo club rating of the league − 1500)/800), `league_strength` included |
| `arabs/poty.json` | Arab player of the season race: weight × ((rating − 6)×10 + 4×goals + 3×assists) × min(1, minutes/1800), with `rank_history` (weekly, last 12 weeks) |
| `arabs/abroad.json` → `per90` | per-90 values (goals, assists, shots, shots on target, big chances created, passes, dribbles, tackles, interceptions, recoveries) for the compare page |
| `arabs/continental-odds.json` | Arab clubs still alive in ACL Elite / ACL Two / AFC Challenge League / CAF CL / Confederation Cup: reach and title probabilities from comp/{id}/bracket-sim.json (`available: false` while only a league phase exists) |
| `arabs/nations-h2h.json` | 22×22 matrix of Arab national teams: `matrix[A][B] = {p, w, d, l, gf, ga, last}` (martj42) |
| `comp/{id}/champion-path.json` | Arab leagues: the champion's matches, Tifo rating by month and key moments per month (biggest win, decisive late goal). `status`: `clinched` this season or `season_end` (last completed season) |
| `coaches/{id}.json`, `coaches/h2h/{a}-{b}.json`, `coaches/index.json` | coaches of clubs in the analytics leagues and the Arab national teams: career rows (team, season, W/D/L, ppg) and coach-vs-coach results from stored lineups |
| `arabs/happiness.json` | per club, last 7 days: points − expected points (pre-match Tifo probabilities), `mood` |
| `arabs/twins.json` | for every club in the Arab leagues: the 3 nearest style twins (Arab leagues + big five) and the nearest big-five club |
| `comp/{id}/finishing.json` | players with ≥ 10 shots: `{player, name, team, shots, goals, xg, luck, proxy}`, luck = goals − xG (FotMob player xG, else a fitted proxy; `proxy` flag and `proxy_model`). Shots = FotMob's shots per 90 × minutes / 90 |
| `clubs/anniversaries.json` | founding dates by MM-DD (and year-only list): research/tifo-2026-09-27/arab_clubs.json + Wikidata (unique exact match in the same country) |
| `draws/{comp}.json` | cups and group tournaments: `{comp, events: [{at, groups, ties}], current: {groups, ties}, baseline_at}`. `events` = when groups or knockout pairings changed after `baseline_at` (when we first saw the competition; a draw made before that is not an event); `current` = what the source shows now. Leagues get a file only once an event exists. The analytics function reruns the cup/continental simulations right after an event |
| `calendar/year.json` | the next 12 months: finals, detected draws, league starts and breaks, national-team windows (`not_included`: transfer windows and awards) |
| `comp/{id}/suspensions.json` | `suspended` (red card or yellow threshold reached in the team's last stored match) and `at_risk` (one yellow from a ban), with the competition's rules, confidence and sources (research/tifo-2026-09-27/suspension_rules.json) |
| `comp/{id}/absences.json` | the coming round per team: `unavailable_from_match` (FotMob, near kickoff), `injured_in_squad`, `suspended` |
| `match/{id}.json` → `referee_profile` | upcoming (scheduled) matches once FotMob names the referee (usually 1–2 days before kickoff; none named during the international break): his season numbers in the competition and his stored matches with each of the two teams. Gone once the match is live |
| `comp/{id}/alltime-table.json` | Arab leagues: all-time table since 2010/11 (seasons, P/W/D/L, goals, points, titles in the computed tables) |
| `team/{id}/records.json` | per club: biggest win and loss since 2010/11, longest winning/unbeaten/losing/scoring runs, most appearances and top scorers this season |
| `comp/{id}/promoted.json` | this season's promoted clubs vs past newcomers (final rank and points, and `pts_after_same_games`) |
| `comp/{id}/late-goals.json` | goals after 90' that turned a draw into a win or a loss into a draw, with team counts |
| `arabs/transitions.json` | league-to-league moves since 2016: per pair (e.g. `538->536`) n, median rating change and median (goals+assists)/appearance change, with players. Method: FotMob career rows per season and league (≥ 8 apps both sides). Limits: selection bias, small n, league-relative ratings, per appearance not per 90 |
| `arabs/worldcup.json` | every World Cup finals match of Arab national teams, grouped by team and tournament, with scorers where martj42 goalscorers.csv has them, plus W/D/L summaries |
| `archive/index.json`, `archive/{id}.json` | memorable matches with full event data: derbies (competitions.yaml `derbies`), cup finals, Super Cups since 2016/17 |

- **Competitions (`index.json`, `competitions.yaml`):** each has `country: {iso2, name_ar}`, or `null` plus `region` (gulf, arab, asia, africa, europe, world). `teams.json` and `team/{id}.json` (`country_info`) give each club its domestic country and each national team its own country (`national: true`).
- **Standings rows:** they also carry `home_rows`/`away_rows` per group (home and away tables) and `ongoing` (the live match FotMob counted, with its score).
- **Lineup players:** they carry `role` (GK/DF/MF/FW), `age`, `minutes_on/off`, and `xy`/`xy_h` (0–1 pitch fractions as FotMob draws the vertical and horizontal lineups) for a 3D pitch.
- **Shots:** they carry `goal_y`/`goal_z` (where the ball crossed the goal line), `on_goal {x, y}` and `keeper_id`.
- **Squad players:** they carry `dob`, `height` and `market_value_eur`.

## Not available (checked 2026-09-26)

| item | status |
|---|---|
| Leagues of Jordan, Oman, Bahrain, Lebanon, Libya, Sudan, Syria, Palestine, Yemen | Not on FotMob (checked the country list and search on 2026-09-27). Their national teams are covered through the archive and national Elo |
| UAE First Division | Not on FotMob (UAE list: 538, 11027, 9943, 11026), uaepl.ae, TheSportsDB or ESPN |
| President's Cup 2026/27 | FotMob's latest season is 2025/26. The new draw is not published; the file shows last season until it is |
| xG, shot map, momentum for UAE competitions | FotMob coverage for the Pro League is `ratings` and for the League Cup `lower`, so they have no xG, shot map or momentum. `xg.json`/`shots.json` for 538 say `available: false`. They exist for Saudi, Egypt and the European leagues (`xG` coverage). Qatar (535) is `ratings` coverage in 2026/27 (all 24 stored matches), so it has no shot map |
| Referee on every match | Present on recent Pro League matches, sometimes empty (e.g. Gulf Cup games). Never named for the CAF Confederation Cup (9468), Morocco (530), Algeria (516), Tunisia (544), Iraq (524) and Kuwait (529) matches (infoBox Referee empty) |
| Lineups, substitutions in some Arab leagues | FotMob has results and goal events only for Algeria (516), Iraq (524) and Kuwait (529): no lineups, subs or minutes, so subs, workload, local minutes and red-card impact there are empty (`available: false`). Tunisia (544) gets a "simple" lineup (starters only, no substitutions), sometimes only after full time; ledger entries stored before it appeared are not re-fetched, so its lineup-based files are thin |
| Goal type (body part) | Only from the shot map (xG coverage). The Pro League, League Cup, Qatar, Saudi First Division and the Moroccan, Algerian, Tunisian, Iraqi and Kuwaiti leagues give no `goalDescription` on goal events (checked match 5961821), so `goal-types` there has only penalties |
| `arabs/tonight.json` in an international window | Empty by nature: it lists club matches abroad (big five, UEFA), and there are none in the window |
| AFC/CAF `scenarios.json` → `arab_clubs` | Scenarios exist only for groups with ≤ 8 games left (3^8 outcomes), so continental groups get them in the last rounds only |
| Referee stats scope | FotMob's `source_stats` can describe another competition (a Saudi Pro League match showed a referee's First Division numbers). Our own `referees.json` counts only stored matches |
| Offside as an event | FotMob has no offside events, only VAR decisions (`var_outcome` offside / goal_disallowed_offside) and the `Offsides` team stat |
| Disallowed goals without VAR | Not reported by the source |
| Penalty "given" when not taken | Only scored or missed penalties are events; VAR-cancelled penalties appear as `var` events |
| Injuries | Only what FotMob lists in `lineups.*.unavailable` (pre-match and live) and in squads (`injury`). There is no league-wide injury list |
| Transfers | League pages carry the latest ~100 moves; team pages (focus teams) carry that club's in/out list |
| Player radar | Per-player lists cover only the competitions in `player_stats_comps` (538, 536, 535). FotMob's own percentiles exist per player (`playerData.firstSeasonStats`) but would cost one request per player; `players.json` computes them from the lists instead |
| Highlights fallback | FotMob already links the official `@uaeproleague` YouTube video per match (checked through YouTube oEmbed: author "UAE Pro League"). If that ever disappears, the channel's RSS feed (`youtube.com/feeds/videos.xml?channel_id=<id>`, one request, latest 15 videos) matches on titles of the form «ملخص وأهداف مباراة {home_ar} ضد {away_ar} الجولة {round} من دوري ادنوك للمحترفين». This is not implemented, and YouTube is not scraped |
| World Cup qualifying (AFC) | The 2023/25 cycle (id 10197) is finished, and the next cycle is not published. `qualifying.json` shows the finished group. The Asian Cup 2027 group E (290) and Gulf Cup group B (329) have remaining fixtures |
| Player names in Arabic | Not from FotMob; another agent builds `names/players_ar.json` (Wikidata), used here only for birthdays |
| Most improved / player lists for some leagues | FotMob returns 403 for older rating lists of Morocco, Algeria, Tunisia, Kuwait and has no per-player lists for Iraq |
| Match events before 2016/17, lineups before 2018/19 | FotMob match details are empty for 2014/15 and earlier and have no lineups for 2016/17. The archive starts at 2016/17 |
| UAE league results before 2010/11 | No free machine-readable source. Champions since 1973–74 come from Wikipedia/RSSSF (`alltime.json`) |
| FIFA ranking for 2026 dates | FIFA's API returns empty lists for its newest ids (`FRS_*`). FotMob's current ranking fills in from then on, without AFC/Arab ranks |
| Attendance | FotMob reports none for UAE matches, so `avg_attendance` is null for 538 |
| Coach tenure dates | FotMob gives coach history per season, not appointment dates. Pressure uses the current coach's games this season |
| Distance for AFC away trips | Known only once that match's detail has been fetched (backfill), because the venue comes from the match detail |
| Kickoff times for later Pro League rounds | FotMob has rounds 1–6 (42 matches). uaepl.ae has all 182 pairings, but rounds 7–26 have no dates yet (`date_tbd`) |

## Re-polls after full time (thin coverage)

A finished match whose `coverage_events` has `subs` or `cards` false is fetched again 30, 60, 180 and 1,440 minutes after
full time (`REPOLL_MINUTES`; FotMob filled in Gulf Cup cards a day later). Events the new copy has are published (and
fed to the ledger); an event an earlier copy had that the new one lacks is kept; live `first_seen` stamps are kept. The
re-polls stop early once both flags are true. State: `repoll` in `state/poller.json`.

No second source for substitutions was found (checked 2026-09-27): ESPN lists the Gulf Cup (`global.gulf_cup`) with
scores only (no lineups, key events or commentary, even for finished games); SofaScore's API answers 403; TheSportsDB's
free key returns 3 events a day and no Gulf Cup.

## Analytics steps that were not ready

A step in the analytics function whose inputs are not loaded yet returns `False` (the Arab clubs rating before the
history is complete; happiness and continental history before that rating's aux data exists; transitions before any
career pair; finishing before any table reaches 10 shots). It is retried after 30 minutes (`NOT_READY_RETRY`) instead of
waiting its full cadence (6 h to 24 h) and publishing nothing or an empty file in between. `arabs/coaches.json` is
refreshed hourly (was 6 h), because the club coach data fills in over several runs.

## Source outage alert (poller, item 343)

- Every poller run is classified from this run's FotMob-fed health items (`day:*`, `comp:*:fotmob`, `match:*`,
  `team:*`, `names:fotmob`, `prev-season:*`, `players:*`) and from `sources/http.py`'s per-host ok/failed counters:
  - **good:** any item succeeded
  - **bad:** items failed and none succeeded. This covers errors, and also empty or malformed payloads, since those
    are refused by the validators.
  - **neutral:** it touched none, as in most idle minutes
- **When mail goes out:**
  - **Outage:** once the outage is `source_alert_minutes` old (15), one mail from `tifo@elyoxe.com` to
    `hello@elyoxe.com` (SES ap-south-1).
  - **Recovery:** one mail on the first good run after that.
  - **Neutral runs:** they never start or end an outage.
- **Failed sends:** a send that fails is retried the next run, at most 5 times.
- **State:** `source_watch` in `state/poller.json`: `first_bad_at`, `alerted_at`, `last_error`, `send_failures`.
- **Migration plan:** `docs/SOURCE-MIGRATION.md`.

## Prayer-time method

- **Standard:** the UAE timetable of the General Authority of Islamic Affairs, Endowments and Zakat (Awqaf, formerly GAIWE), not Umm al-Qura.
- **Parameters:** they are identical to elyoxe.com/tools (`saas/tools/src/assets/prayer.js`):
  - adhan "Dubai": Fajr and Isha at 18.2°, Asr Shafi'i, built-in offsets sunrise −3, dhuhr +3, asr +3, maghrib +3
  - the site's measured offsets asr −1, maghrib +1, isha +1
- **Implementation:** `compute/prayer.py` is a port of adhan's algorithm and matches the vendored `adhan.umd.min.js` to the minute on 216 of 216 reference cells (`tools/adhan_reference.js` produces `tests/fixtures/prayer_adhan.json`).
- **Play window:** kickoff to +115 min (45 + 15 + 45 + 10). Actual period times replace the estimate once known (`estimated_window: false`).
- **Location:** times are computed at the stadium's coordinates.

## Swapping the provider

1. Implement `sources/apifootball.py`: `day`, `competition`, `match`, `team` (and optionally `arabic_names`), returning these shapes. Its docstring maps the endpoints and statuses.
2. Map ids onto FotMob's: add `ids: {apifootball: N}` in competitions.yaml, plus a team id map.
3. Construct it in `Poller.load()` instead of `FotMob`. The compute modules, store and files stay as they are.
