# UAE top-flight history 1973/74 – 2014/15: free sources, tested 2026-11-22

Scope: every top-tier match (date, home, away, score; then scorers + minutes, line-ups, subs, cards, referees, venue,
attendance, coaches). Tested from the Windows laptop on home internet: curl and Python urllib, a normal Chrome UA, at least
2 s between requests to the same host, no challenge-solving. Coverage claims below come only from responses I actually
fetched (≈330 requests in total). Anything I did not fetch is marked "not tested".

**Main finding.** The UAE FA's own JSON API (`www.uaefa.ae/api/…`, behind the Angular site) holds **every top-tier match
from 2003/04**. For each one it has the starting XI and bench (full Arabic and English names, FA player ids), substitutions
with minutes, yellow and red cards with minutes, goals with minute, side and type, the full referee team, the venue and the
kick-off time. Getting the match ids is cheap: for 2008/09 onward, uaepl.ae's fixture list carries the FA id of every match
(`id="matchList_<fa_id>"`). For 2003/04–2007/08 the ids come in contiguous blocks that can be found by scanning ids.

Legend: **R** results · **D** date · **K** kick-off time · **V** venue · **S** scorers (+min = with minutes) · **L** line-ups
(XI + bench) · **Sub** substitutions with minute · **C** cards with minute · **Ref** referee team · **Co** coaches ·
**HT** half-time score · **T** final table · **TS** top scorers · "—" nothing found · "n/t" not tested.

## 1. Coverage matrix

| Seasons | RSSSF | Wikipedia EN / AR | UAE FA API | uaepl.ae | kooora (Opta) | Soccerway | Newspapers |
|---|---|---|---|---|---|---|---|
| 1973/74 | group lists + play-off R (no D) [R1] | n/t | — (earliest 2003/04) [F5] | — [U1] | — [K2] | — [W2] | n/t |
| 1974/75 | T only [R1] | AR article, no table [P2] | — | — | — | — | n/t |
| 1975/76–1981/82 | **no season pages** (uae76…uae82 not linked) [R0] | EN articles with T (1975–76 ✔; 1980–81 no T) [P1] | — | — | — | — | n/t |
| 1982/83 | top-2 points only [R1] | n/t | — | — | — | — | n/t |
| 1983/84–1993/94 | T (some incomplete; 1984/85 and 1990/91 pages missing); a few R (e.g. last round of 1988/89) [R1] | EN 1985–86 T; AR 1985–86 T [P1][P2]; EN 1990–91 article missing | — | — | — | — | n/t |
| 1994/95–1995/96 | T + dated R of the top-6 final stage only; TS [R1] | n/t | — | — | — | — | n/t |
| 1996/97–1997/98 | R round by round, no D, scorers only sporadic [R1] | EN 1996–97 T [P1] | — | — | — | — | n/t |
| 1998/99–1999/00 | R + S (+min) [R1] | EN 1999–2000 T [P1]; AR missing | — | — | — | 1999/00 → 404 [W2] | n/t |
| 2000/01–2002/03 | R + D + S (+min) [R1] | n/t | — | — | — | R + D/K (UTC timestamp); ~106 of 132 rows server-rendered [W2] | Gulf News prose, 2002 ✔ [N1] |
| **2003/04–2004/05** | R + D + S (+min) [R1] | EN 2003–04 T [P1]; AR missing | **R D K V L Sub C S(+min, side) Ref(5)** [F3][F6] | — | — | R + D/K [W2] | n/t |
| **2005/06–2007/08** | R + D, no scorers [R1] | EN T (2005–06, 2007–08) [P1] | **same as above** [F6][F7] | — | 2007/08: R + D/K only, all 132 [K3][K4] | R + D/K (n/t per season) | Al Bayan prose 2005+ ✔ [N2] |
| **2008/09–2011/12** | R + D, no scorers [R1] | EN results matrix 2009–10…2011–12; AR 2009–10 matrix + TS [P1][P2] | **same as above**; all ids known [F1][F2][F4] | R D K V for all matches + FA id; timeline only for isolated matches [U2][U3] | R + D/K only [K3] | R (2008/09 ✔) [W2] | Al Ittihad 2009 ✔, The National ✔ [N3][N4] |
| **2012/13–2013/14** | R + D, no scorers [R1] | EN results matrix + TS (2012–13) [P1] | **+ HT, shirt numbers, positions; Co in 2012/13 sample** [F4] | as above [U2] | R + D/K only (2013/14 ✔ 182) [K3][K4] | n/t | n/t |
| 2014/15 (FotMob already) | R + D [R1] | n/t | + 7 officials, Co [F4] | as above [U2] | n/t | n/t | n/t |

**Never available in any source I tested:** per-match **attendance** (FA `attended` is `"0"` on every match checked, uaepl
shows no attendance, Wikipedia has stadium capacities only), and per-match **coaches** before 2012/13 (the FA team
`official` list is empty in every sample from 2003/04 to 2011/12 and in 2013/14).

## 2. Sources in detail

### 2.1 UAE FA API — `https://www.uaefa.ae/api/` (best source, 2003/04 → today)

Found by reading the site bundle `https://www.uaefa.ae/main-L55PPFMW.js` (the service class sets `url="api/"`). Plain
GET, JSON, no key, no cookies. `robots.txt`: `User-Agent: * / Disallow:` (empty), plus 30 sitemaps that list news only.
No terms page seen. About 150 requests at 2 s intervals: no block and no rate-limit response. A missing id returns
**HTTP 500**, which simply means a gap in the id range.

Endpoints (all tested):

| Endpoint | Gives |
|---|---|
| `match_report?match_id=N` | `attributes`: date, kick-off (`match_time`, local), `competition_full_en/ar`, season, round, `Stadium_en/ar` ("Al Nasr Club / Al Maktoum Stadium"), `competition_id`. `team1/team2`: `name_en/ar`, score, `score_h1/h2` (from 2012/13), `active.player[]` (11) and `substitute.player[]` (7), each with `player_id`, full 4-part `name_en/name_ar`, `shortname_*`, `cat_en` (UAE Citizen / Foreign), Professional/Amateur, plus `subs_in/subs_out {time}`, `ycard/rcard {time, reason_id}`; shirt number and position from 2012/13. `official[]` = coaches/managers (only in some seasons). `match_official[]` = Referee, 1st/2nd Assistant, Fourth Referee, Referees Assessor (2014/15: 7, adding the additional referees), with Arabic and English names. |
| `match_highlights2?lang=en\|ar&match_id=N` | `event[]`: `type` goal/subs/ycard/rcard, `time`, `fulltime` ("90+4"), `club_dir` H/A, `player_id`, `player_name`, `in_player_*`, `goal_type` (1 seen in old seasons, 2 in 2026; codes not yet mapped), `reason_id`; `attributes.attended` (always "0"), `playground_latlng`. |
| `competition_scorer?lang=en\|ar&competition_id=C`, `competition_y_cards?…`, `competition_r_cards?…` | season scorer and card totals per player. These work for old competitions: 2003/04 (C=287) 90 scorers, 2004/05 (275) 148, 2005/06 (266) 132, 2006/07 (227) 125, 2007/08 (209) 129, 2008/09 (192) 123. |
| `matches?lang=en&competition_id=C` / `&date_from=&date_to=` / `&club_id=` | **current season only**. Old competitions return `matches: []`, so they cannot be used to enumerate old matches. |
| `competitions?lang=en` | active season only (`season_id` is ignored). |
| `standings?competition_id=192` | `[]` for old competitions. |
| `event_by_day?date_from=D&date_to=D` | match count per day across all FA competitions, even old ones (2007-02-17 → 21 matches); no ids. |

**What I fetched and checked (claims in the matrix):**
- [F1] `match_report?match_id=15192` (2008-09-19 Al Nasr 2-4 Shabab Al Ahli Dubai): XI 11+11, bench 7+7, subs with
  minutes, Y 46', R 70', 5 match officials (Referee Ali Hamad Al Badwawi …), venue Arabic and English.
- [F2] `match_highlights2?lang=en&match_id=15192`: 6 goals with minute and H/A, 6 subs, cards. They agree with uaepl's
  timeline for the same match.
- [F3] Earliest season: an id probe across 1…100000. 2003/04 runs roughly from id 22270 to 23830 (`22500`, `23000`, `23700`,
  `23810`, `23830` are all 2003/04). Nothing older was found anywhere in the range. Ids 1–14000 hold 2010–2015, 14000–23840
  hold 2003/04–2008/09 (with some 2014/15 interleaved, e.g. 17360–17744 and 19400), and ids above 24000 hold 2015 onward.
- [F4] `match_report` and `match_highlights2` for 11673 (2009/10), 7840 (2010/11), 7325 (2011/12), 833 (2012/13), 4522
  (2013/14) and 9781 (2014/15): XI 11/11 and bench 7/7 in every one, referee team in every one except 833 (empty), coaches
  in 833 (Bruno Metsu, Branko Ivankovic, both as "Technical Director") and 9781, HT score and shirt numbers/positions in
  833, 4522 and 9781.
- [F5] The 2003/04 top tier was found: `22390` (2004-03-21 Al Shabab 1-0 Sharjah, "2003/2004 - First Division league -
  First Stage (Groups League)") and `22430`, each with full XI, bench, events and 5 officials.
- [F6] `20960` (2004/05 Al Nasr 5-1 Emirates), `19550`/`19580`/`19610`/`19640` (2005/06), `17840` (2006/07 Al Wasl 1-0
  Sharjah) and `15750` (2007/08 Emirates 1-2 Al Ain): all have line-ups, events and officials.
- [F7] Block scan, 2006/07: ids 17768–17888 (step 8) are all "2006/2007 Etisalat First Division league". 17752/17760 are
  gaps and 17896 is the Second Division, so the block is about 17761–17893, about 132 ids, which fits a 12-team double
  round robin. Approximate other blocks: 2005/06 ≈ 19540–19665, 2004/05 includes 20920–21000, 2003/04 includes
  22390–22430, 2007/08 includes 15750, 2008/09 ≈ 15001 and 15192–15460.
- Consistency: in 18 random matches (3 per season, 2008/09–2013/14; ids from the uaepl lists) the goal events equal the
  final score **18/18**. For 17840 the goal is "محمد العنزي 56' H", and the Al Bayan report of 2007-05-05 [N2] says
  «محمد سالم العنزي «ق56»».
- Scorer totals do not always match other lists. FA 2008/09 has João Fernando Nelo (= Fernando Baiano) with 24, English
  Wikipedia says 25. Reconcile before publishing season records.

**Naming traps.**
- **"First Division league" is the top tier only up to 2007/08** ("Etisalat First Division league" 2005/06–2007/08). From
  2008/09 the top tier is "Etisalat Proleague" (2008/09–2011/12), "Etisalat Pro League" (2012/13) or "Arabian Gulf League"
  (2013/14–2014/15), and "First Division league" means the second tier (id 6000: 2011/12 Al Orooba–Fujairah). The second
  tier before 2008/09 is "Second Division league". Filter on season and name together.
- Clubs use their current names for the past: "Shabab Al Ahli Dubai" / «شباب الأهلي دبي» for Al Ahli (Dubai) even in
  2003/04, "Baniyas", "KhorFakkan", "Dibba Al-Hisn".
- Some old players have no English name (2003/04 and 2004/05 top scorers come back with `player_name: null` in `lang=en`,
  but `lang=ar` gives «محمد علي كريمي»). Some officials have only Arabic short names inside `_en` fields ("فريد علي").
  Always fetch both languages.
- The kick-off is "22:00" for every 2008/09 GW1–GW2 match and for 2010/11 GW1 in both the FA and uaepl data, which looks
  like a placeholder. 2003/04 times look real (20:00).

**Enumeration plan.**
- 2008/09–2014/15: read the FA ids from the uaepl lists (§2.2): 7 requests, 1,136 matches.
- 2003/04–2007/08: scan ids 14000–23840 with `match_highlights2`, which is about 2 KB per call. That is about 9,800 calls,
  ≈5.5 h at 2 s; run it in stages with saved state. Keep records whose competition is "First Division league" with season
  ≤ 2007/08. A faster route: scan at step 20 (≈500 calls), then walk each top-tier block edge by edge. Expected counts:
  12 teams ⇒ 132 (2006/07, 2007/08); check 2003/04 (group format) and 2004/05 (14 teams ⇒ 182, per RSSSF's 26-game table)
  against RSSSF and Soccerway.

### 2.2 uaepl.ae (official league site, Laravel) — 2008/09 → today

- [U1] `https://www.uaepl.ae/en/fixtures`: the season dropdown runs from **2008/2009** (key 13) to 2026/2027 (19). The page
  embeds `var season = {...}`, which maps every season to its `seasonCompetitionId` values (league, cup, super cup,
  reserves). League ids for the old seasons:
  2008/09 `98a49220-7f1e-11eb-81e1-cfe80e72eb76` · 2009/10 `98a49220-7f1e-11eb-81e1-cfe80e72eb66` ·
  2010/11 `0c8d9c50-6a3f-11eb-abea-f59ee726fay9` · 2011/12 `0c8d9c50-6a3f-11eb-abea-f59ee726fax9` ·
  2012/13 `0c8d9c50-6a3f-11eb-abea-f59ee726fab9` · 2013/14 `c08fa630-6a38-11eb-8498-4dd725155205` ·
  2014/15 `85706d40-6a34-11eb-a1bf-056e272802ea`. (Some ids are not valid UUIDs, e.g. `…fay9`, but they still work.)
- [U2] `GET /en/fixtures/matches?seasonCompetitionId=<id>&weekNumber=&teamId=` with `X-Requested-With: XMLHttpRequest`
  returns `{"html": …}` with **132 / 132 / 132 / 132 / 182 / 182 / 182** match boxes for 2008/09 … 2014/15. Every box has
  a score, the GW, the date, the kick-off time and the stadium, a link `/en/fixtures/<uuid>`, and
  **`id="matchList_<FA match id>"`**. Use `/ar/` for Arabic club and stadium names, and note that the Arabic score is
  AWAY:HOME (already handled in `sources/uaepl.py`).
- [U3] Match centre `/en/fixtures/<uuid>` embeds `var match = {…}`, which includes `fa_match_id`, `match_date_time`, score
  and stadium. Its "Timeline" (goals, cards, subs with minutes, server-rendered) is filled only for isolated old matches:
  1 of 8 in 2008/09 GW1–2 (`7de87767-…`, 14 events) and 0 of 5 sampled in each of 2009/10…2014/15. Line-up tabs are empty
  in every old match. Player names are Latin even on `/ar/`. **Use uaepl for the id map, dates, times and venues, and the
  FA API for the details.**
- Venue = the home club's stadium record (`stadium.team_id` = home team). It may not be historically exact. Naming:
  "Shabab AlAhli" is used for Al Ahli (Dubai) in 2008/09. `robots.txt` has an empty Disallow. No licence text seen.

### 2.3 kooora.com — new Opta-based site; goalzz.com is gone

- [K1] Old URL styles: `https://www.kooora.com/?c=1` → 404, and `https://www.goalzz.com/` redirects to `goal.com/en`.
  **The classic kooora archive (`?c=`, `?m=`) is gone.** The Wayback Machine has scattered `?m=` captures
  (CDX `https://web.archive.org/cdx/search/cdx?url=kooora.com/%3Fm%3D*&from=2008&to=2012`), but the one I opened
  (`/web/20110522173340id_/http://www.kooora.com:80/?m=554602&update=true`, 1.8 KB, cp1256) is a page shell. It is not
  indexed by competition, so it is not usable in bulk.
- [K2] New site, competition `f39uq10c8xhg5e6rwwcf6lhgc` (the same Opta id used by uaepl's widget):
  `https://www.kooora.com/كرة-القدم/مسابقة/دوري-الخليج-العربي/f39uq10c8xhg5e6rwwcf6lhgc` lists seasons
  **2007/2008 → 2026/2027** with ids (2007/08 `OyZUQA-0y3ye_jDEyZBr8`, 2008/09 `5s-i9TjBz4v0w187rp1Z4`, 2009/10
  `ZOcb8w_3d1QNvaq37_ID8`, 2010/11 `OULTc9d5TJOyVL3BlDEO-`, 2011/12 `O-ojzbFUZHKa-3crU5vHi`, 2012/13
  `JsJ4-Ze48HUNhj-n7rokF`, 2013/14 `aQUduRGnJEz5m5f9QIhGA`, 2014/15 `C5SZS96hQDNgzd8wO37hH`).
- [K3] JSON: `https://www.kooora.com/api/competition-matches?id=f39uq10c8xhg5e6rwwcf6lhgc&seasonId=<id>&gameSetTypeIds=`
  returns `gamesets[].matches[]` with id, `startDate` (UTC), Arabic team names and ids, score and `redCards` counts:
  2007/08 22×6 = 132, 2009/10 132, 2013/14 26 rounds / 182. **Trap:** without the empty `gameSetTypeIds=` the response is
  a cached copy of whatever season was asked for recently (seen twice). Cache-Control is `private, max-age≈60–160`.
- [K4] Match page `https://www.kooora.com/كرة-القدم/مباراة/<slug>/<id>`, read from `__NEXT_DATA__`: for 2007/08
  (`حتا-ضد-الشباب/SLesNeYkxZVmNC93_Arzg`) and 2013/14 (`الوصل-ضد-الشارقة/nw4xoQ-A5r-5LU-NMAG8b`), `scorers` is
  empty, `lineups` and `venue` are null, `keyEvents` and `events` are empty, and `halfTime` is null. **Results only.**
  Useful for Arabic club names and as a cross-check. `robots.txt` lists `User-agent: *` and no Disallow lines.

### 2.4 RSSSF — `https://www.rsssf.org/tablesu/uaechamp.html` (Atsushi Fujioka; updated 10 Jul 2026)

- [R0] The champions page links season pages `uae74, uae75, uae83, uae84, uae86–90, uae92–99, uae00–09, uae2010–2026`.
  These have **no page:** 1975/76–1981/82, 1984/85 and 1990/91.
- [R1] All 33 pages from uae74 to uae2015 fetched (plain text in HTML, latin-1). Content as in the matrix:
  - uae74: regional group lists and play-off results.
  - uae75, uae84, uae86, uae90, uae92, uae93: tables. uae83 and uae87: top two only.
  - uae89: last round and table.
  - uae95, uae96: table plus dated results of the top-6 stage, and top scorers.
  - uae97, uae98: "Round N" result lists without dates, and few bracketed scorers.
  - uae99–uae05: dated results with `[scorer min; scorer min]`.
  - uae06–uae2015: dated rounds without scorers (bracket lines there belong to cup sections and top-scorer lists).
- Names are abbreviated and vary ("Ittihad K", "Ahli Dubai", "Ahli Fujeira", "Shabab/Arabi"); `db/rsssf.py` already has
  the UAE alias map. Terms: "(C) Copyright Atsushi Fujioka and RSSSF 1996/2026 … acknowledgement is given to the author.
  All rights reserved." The tables and results the DB holds for 1973–2008 already come from here.

### 2.5 Wikipedia (MediaWiki API, wikitext; CC BY-SA)

- [P1] EN pages checked: "1975–76 / 1980–81 / 1985–86 / 1996–97 / 1999–2000 / 2003–04 / 2005–06 / 2006–07 / 2007–08 UAE
  Football League" all have a league table (except 1980–81) and **no results matrix**. "1990–91 UAE Football League" is
  missing. "2008–09 UAE Pro League" has a table only. 2009–10, 2010–11 and 2011–12 have a results matrix (132 `match_`
  cells), and 2012–13 and 2013–14 have 182 cells. A top-scorer section appears in 2009–10, 2011–12 and 2012–13. No
  referees or attendance in any of them. Results are already in the DB for these seasons, so Wikipedia only adds tables
  for 1975/76–1982/83 (gaps on RSSSF) and the managers that `graph/wiki_managers.py` already reads.
- [P2] AR pages: «الدوري الإماراتي 1974–75» (no table), «الدوري الإماراتي 1985–86» (table), «الدوري الإماراتي 2007–08»
  (1.7 KB stub), «الدوري الإماراتي للمحترفين 2008–09» (table), «الدوري الإماراتي للمحترفين 2009–10» (matrix 132 + top
  scorers), «دوري الخليج العربي 2013–14» (no table template). «الدوري الإماراتي 1999–2000» and «…2003–04» are missing.

### 2.6 Soccerway (now the Flashscore engine)

- [W1] `https://www.soccerway.com/united-arab-emirates/uae-league/archive/` loads (200), but its season list is built in
  JavaScript.
- [W2] `https://www.soccerway.com/united-arab-emirates/uae-league-<YYYY-YYYY>/results/` embeds
  `cjs.initialFeeds['results'] = {data: \`…\`}` in Flashscore's `¬`/`÷` format. Each record has `AA` (match id), `AD`
  (unix kick-off), `ER` ("Round 21"), `AE`/`AF` (home/away), `AG`/`AH` (score). Tested: 2008-2009 (122 `AA÷`), 2003-2004
  ("UAE League - Final Group", 96), 2002-2003 (106 records out of the 132 expected), 2000-2001 ("Play Out", 121).
  **1999-2000 and 1995-1996 → 404.** The rest of a season needs the "show more" feed, which is client-side and signed
  (not attempted).
- Match page `https://www.soccerway.com/match/EZ9AvIYd/` → `/match/al-ain-UX1exRBg/al-nasr-40ZYZrBI/?mid=EZ9AvIYd`
  renders no summary data; scorers, line-ups and referees load client-side. **Not reachable by plain HTTP.**
  `robots.txt` disallows `/standings/`, `/draw/` and others, but not results or match pages.

### 2.7 Sites that block plain requests, or have nothing for this league

- worldfootball.net: `https://www.worldfootball.net/winner/uae-pro-league/`, `/all_matches/uae-pro-league-2008-2009/` and
  `/competition/uae-pro-league/` all return **403 "Just a moment..."** (Cloudflare challenge). Blocked; moved on.
- Transfermarkt: `https://www.transfermarkt.com/uae-pro-league/gesamtspielplan/wettbewerb/UAE1?saison_id=2008` (also
  2003, 1999, 2014) returns **HTTP 202 with an empty body** (bot challenge). Blocked. The open dcaribou dataset the
  project uses (`https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/competitions.csv.gz`) has 31 domestic leagues
  and **no UAE1**.
- BeSoccer: `https://www.besoccer.com/competition/uae_arabian_gulf_league` and `/competition/scores/…/2009` → **406**.
  Blocked.
- footballdatabase.eu: the home page loads (21 KB). `/en/competition/overall/` returns a 1.1 KB ad shell. I did not find a
  UAE league URL (also searched the web), so it is n/t.
- 11v11: `https://www.11v11.com/competitions/` loads and has no UAE entry.
- national-football-teams.com and eu-football.info cover national teams only (eu-football returned an empty body), so
  they are not relevant.
- Flashscore direct: `https://www.flashscore.com/football/united-arab-emirates/uae-league/archive/` → connection
  failed (000).
- FootyStats (`footystats.org/uae/arabian-gulf-league/datasets`): a web search shows CSVs from 2013/14 only. Not fetched.

### 2.8 Newspaper archives (free prose; for spot checks only)

- [N1] Gulf News: `https://gulfnews.com/uae/al-ain-overcome-al-wahda-1.380127` (March 2002 report, 200, ≈2.2 KB of text
  with scorers and minutes). There is no structured search over plain HTTP. Old articles live under `/uae/<slug>-1.<id>`.
- [N2] Al Bayan: `https://www.albayan.ae/five-senses/2007-05-05-1.768797` (200). It is a full Arabic match report with
  scorer and minute («ق56») and the coaches (Zomaria for Al Wasl, Jumaa Rabie for Sharjah). The URL pattern
  `/five-senses/<YYYY-MM-DD>-1.<id>` reaches back to 2005 in search results (2005-09-11, 2005-11-03, 2006-10-07).
- [N3] Al Ittihad: `https://www.alittihad.ae/article/17839/2009` (200, 14 KB of text, about the 2009 title).
- [N4] The National: `https://www.thenationalnews.com/sport/home-still-not-sweet-for-al-ain-1.261384` (200, scorer and
  minute). The paper starts in 2008.
- Al Khaleej: an archive URL from a search result (2010-04-10 «كلاسيكو الإمارات وحداوي») → **404**, link rot. Emarat Al
  Youm: n/t.
- None of these exposes a match index, so they can only patch individual matches (e.g. scorers 1996/97–1997/98, or
  coaches) by hand or with targeted search. They are not a bulk source.

### 2.9 Open datasets

- GitHub (`gh search repos`: "uae pro league", "arabian gulf league", "uae football league", …) finds only
  `muhadkprsnl/UAE-Pro-league` (2025/26 player and stats xlsx), `aryansatwani/UAE_League_Predictions` (one-season CSV,
  6.8 KB) and `griffisben/Post_Match_App` (2024/25–2025/26 match lists). **No historical dataset.**
- Kaggle: no UAE league dataset turned up in web search. Kaggle itself was not queried (n/t).

## 3. Recommended plan (in priority order)

1. **UAE FA API for 2008/09–2014/15 (1,136 matches).**
   - Take the 7 uaepl fixture-list XHRs and read the FA ids from `matchList_<id>` (store uaepl uuid ↔ FA id ↔ our mid).
   - For each FA id, call `match_report` (once; it carries both languages) and `match_highlights2` twice, with `lang=en`
     and `lang=ar`. At 2 s per call that is about 3,400 calls, ≈2 h, in resumable stages.
   - Load: XI and bench, substitutions, cards, goals (minute, side, `goal_type`), the referee team, HT (from 2012/13),
     shirt numbers and positions (from 2012/13), and coaches where present.
   - Join to existing matches on date + home + away; FA H/A follows our home/away. Check `sum(goal events) == score` on
     every match and flag mismatches.
2. **UAE FA API for 2003/04–2007/08 (≈5 seasons, ≈130–180 matches each).**
   - Find the blocks by id scan (§2.1: step-20 pass over 14000–23840, then walk each top-tier block edge to edge).
   - Keep "First Division league" only when the season is ≤ 2007/08.
   - Check counts against RSSSF and Soccerway. RSSSF has scorers for 2003/04–2004/05, so compare the FA scorers with
     them. For 2005/06–2007/08 this fills the scorer gap the DB has now.
   - Also pull `competition_scorer` / `competition_y_cards` per season for season totals (C = 287, 275, 266, 227, 209,
     192; ids for later seasons come from `match_report.attributes.competition_id`).
3. **uaepl.ae** for official kick-off times and Arabic stadium and club names for 2008/09 onward. Treat "22:00" in
   2008/09 GW1–2 and 2010/11 GW1 as unknown.
4. **RSSSF** stays the backbone for 1973/74–2002/03: tables, the results it has, and scorers for 1998/99–2002/03.
   **Soccerway** result pages for 2000/01–2002/03 add a kick-off timestamp and a second check of results (first ~100
   rows per season by plain HTTP).
5. **kooora API** (2007/08–2013/14) for Arabic club names and Opta ids, and to cross-check results. It adds no events.
6. **Wikipedia EN** for league tables of 1975/76–1982/83, where RSSSF has no pages, and for managers. Arabic Wikipedia
   adds little.
7. **Newspapers** (Gulf News 2002+, Al Bayan 2005+, The National 2008+, Al Ittihad 2009+) only for targeted fixes: a
   disputed scorer, a missing coach, the 1996/97–1997/98 scorers.

**What stays impossible from free, plain-HTTP sources:**
- Any per-match data for 1975/76–1993/94: no results anywhere tested, beyond a few matches on RSSSF.
- Most matches of 1994/95–1995/96 (only the top-6 stage is on RSSSF).
- Dates for 1996/97–1997/98.
- Scorers for 1996/97–1997/98, beyond the few on RSSSF.
- Line-ups, cards and referees before 2003/04.
- Attendance for every season.
- Per-match coaches for 2003/04–2011/12 and 2013/14. Season-level managers come from Wikipedia instead.
- Old kooora's archive, which was taken offline.

## 4. Scripts used (not part of the repo)

`%TEMP%/uaescripts/`: `uaepl_sample.py`, `uaepl_gw.py`, `fa_probe.py` (match_report probe), `fa_probe2.py`
(match_highlights2 probe), `fa_detail.py`, `fa_consist.py`, `fa_comp.py`, `kooora_season.py`, `kooora_match.py`,
`rsssf_scan.py`, `wiki_check.py`, `news_check.py`. Raw responses are in `%TEMP%/uaeres/`.
