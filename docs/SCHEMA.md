# Football data: normalized schema v1

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
| `health.json` | per source and file: ok, error, time, last_ok; last run (mode, seconds, requests, written) | every run |

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
| `players.json` | `players: {id: {name, team, minutes, stats: {stat: {value, per90, pct}}}}`, plus `averages` and `min_minutes` (270). Built from FotMob's ~29 per-player season lists (goals, rating, accurate passes, tackles, ...) |
| `foreigners.json` | top 25 non-nationals by FotMob season rating, then goals + assists. Nationality comes from squads and lineups |

The ledger fills as matches finish. A backfill cursor also fetches up to 6 already-finished matches per idle minute (UAE competitions first) until the current season is complete.

## Not available (checked 2026-09-26)

| item | status |
|---|---|
| UAE First Division | Not on FotMob (UAE list: 538, 11027, 9943, 11026), uaepl.ae, TheSportsDB or ESPN |
| President's Cup 2026/27 | FotMob's latest season is 2025/26. The new draw is not published; the file shows last season until it is |
| xG, shot map, momentum for UAE competitions | FotMob coverage for the Pro League is `ratings` and for the League Cup `lower`, so they have no xG, shot map or momentum. `xg.json`/`shots.json` for 538 say `available: false`. They exist for Saudi, Qatar and the European leagues (`xG` coverage) |
| Referee on every match | Present on recent Pro League matches, sometimes empty (e.g. Gulf Cup games) |
| Referee stats scope | FotMob's `source_stats` can describe another competition (a Saudi Pro League match showed a referee's First Division numbers). Our own `referees.json` counts only stored matches |
| Offside as an event | FotMob has no offside events, only VAR decisions (`var_outcome` offside / goal_disallowed_offside) and the `Offsides` team stat |
| Disallowed goals without VAR | Not reported by the source |
| Penalty "given" when not taken | Only scored or missed penalties are events; VAR-cancelled penalties appear as `var` events |
| Injuries | Only what FotMob lists in `lineups.*.unavailable` (pre-match and live) and in squads (`injury`). There is no league-wide injury list |
| Transfers | League pages carry the latest ~100 moves; team pages (focus teams) carry that club's in/out list |
| Player radar | Per-player lists cover only the competitions in `player_stats_comps` (538, 536, 535). FotMob's own percentiles exist per player (`playerData.firstSeasonStats`) but would cost one request per player; `players.json` computes them from the lists instead |
| Highlights fallback | FotMob already links the official `@uaeproleague` YouTube video per match (checked through YouTube oEmbed: author "UAE Pro League"). If that ever disappears, the channel's RSS feed (`youtube.com/feeds/videos.xml?channel_id=<id>`, one request, latest 15 videos) matches on titles of the form «ملخص وأهداف مباراة {home_ar} ضد {away_ar} الجولة {round} من دوري ادنوك للمحترفين». This is not implemented, and YouTube is not scraped |
| World Cup qualifying (AFC) | The 2023/25 cycle (id 10197) is finished, and the next cycle is not published. `qualifying.json` shows the finished group. The Asian Cup 2027 group E (290) and Gulf Cup group B (329) have remaining fixtures |
| Player names in Arabic | Not in any source |
| Kickoff times for later Pro League rounds | FotMob has rounds 1–6 (42 matches). uaepl.ae has all 182 pairings, but rounds 7–26 have no dates yet (`date_tbd`) |

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
