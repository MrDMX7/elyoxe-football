# Open football datasets that fill Tifo's gaps: tested 2026-11-22

Scope: ready-made datasets and plain-GET APIs that add something Tifo does not already hold (FotMob 2010+, 365Scores,
dcaribou Transfermarkt, RSSSF, schochastics, engsoccerdata England, martj42, Fjelstul, Wikidata/Wikipedia, Understat,
Club Elo, EA FC, UAE FA API, uaepl). Tested from the Windows laptop on home internet (Etisalat) with Python urllib and curl,
a Chrome User-Agent and no challenge-solving. Total: about 500 requests. The logged scripted ones (328) were at least
1.2 s apart per host; the most to one host was 136, to `*.api.espn.com`. GitHub raw and API calls were not logged: about 85
football-data mirror files at 0.4 s spacing on the GitHub CDN, plus about 60 more. Kaggle downloads came to 8, QLever and
Commons to 6. Coverage claims come only from responses I fetched. Anything else is marked **n/t** (not tested).

Gap numbers (from the brief): **G1** detail before 2010 (line-ups, scorers with minutes, cards, referees, attendance) ·
**G2** results for missing Arab seasons and cups · **G3** top scorers (Germany before 1963, Argentina per tournament, Arab
cups) · **G4** photos and crests with a reusable licence · **G5** transfer and injury history.

**Main findings**
1. **ESPN's undocumented JSON API** (`site.api.espn.com`, plain GET, no key) is the biggest find for **G1 Europe**.
   England 2001/02+, Spain, Italy, Germany and France from about 2002/03 have match-day squads with starters, goals with
   minutes, cards and subs per player. Referee and attendance are there for England throughout, and for the other four
   until about 2005/06. One call per month gives every
   match, so roughly 17k calls cover the big 5 from 2001 to 2010. It also covers the AFC Champions League 2006+, AFCON
   2004+ and the Asian Cup 2007, which include Arab clubs and national teams. Saudi starts only in 2022, and Egypt, UAE,
   Qatar and Morocco are not in ESPN.
2. **salimt/football-datasets** (GitHub, also on Kaggle, stated CC0, built from Transfermarkt with the same player ids as
   dcaribou) solves most of **G5**: 143,195 injury records (none in Tifo today) and 1,101,440 transfers. That includes
   37,382 in the 1990s and 197,859 in the 2000s, against 76 and 6,165 in dcaribou's `transfers.csv.gz`.
3. **football-data.co.uk** fills the G1 statistics for Europe: half-time from 1995/96, EPL referee, shots, cards and corners
   from 2000/01, and the other big leagues from 2003–2006. **Etisalat blocks it on this laptop** (category "Gambling"). Load
   it from GitHub Actions or AWS instead.
4. **G2 (Arab results from the 1970s to the 1990s, Arab cups) has no bulk dataset anywhere I looked.** kooora, ESPN,
   openfootball, TheSportsDB, Kaggle, Hugging Face and the federation sites all start in 2007 or later, or hold tables only.
   RSSSF, Wikipedia and newspapers stay the only route. 11v11 and national-football-teams add **line-ups for Arab national
   teams** (sample from 1989) but not club history.
5. **G4.** Wikidata/Commons has 68,860 of 393,282 footballers with a photo. The share is low for the Gulf (UAE 44 of 660,
   Kuwait 13 of 458) and higher for North Africa and Lebanon. **Crests of Arab clubs are almost absent** on Commons and in
   P154 (0–13 per country), because logos are non-free and sit on local Wikipedias.

---

## 1. Ranked table

| # | Source | Adds (gap) | Leagues / seasons (tested) | Format / URL pattern | Access | Licence / terms | Effort |
|---|---|---|---|---|---|---|---|
| 1 | **ESPN site API** | **G1** Europe: match-day squads + starters, goals with minute, cards and subs per player, venue; referee and attendance for England throughout, for ESP/ITA/GER/FRA mostly 2001/02–2005/06. Also Arab clubs and national teams in ACL 2006+, AFCON 2004+, Asian Cup 2007 | eng.1 from 2001/02 (2000-08-19: 0 events); esp/ita/ger/fra seasons listed from 2000, details from 2001/02, starters flagged from ~2002/03; some matches empty (eng Feb 2003 2/4, ger Feb 2003 3/4 empty) | JSON. `…/apis/site/v2/sports/soccer/{league}/scoreboard?dates=YYYYMM&limit=500` (month) + `…/summary?event={id}`; seasons: `sports.core.api.espn.com/v2/sports/soccer/leagues/{league}/seasons` | **plain GET** | none stated (undocumented API; ESPN terms) | **med** (~17k summaries for big-5 2001–10) |
| 2 | **salimt/football-datasets** (= Kaggle `xfkzujqjvx97n/football-datasets`) | **G5** injuries (143k) and transfers (1.10M, 1990s 37k, 2000s 198k); also player profiles, national-team stats, market values | Transfermarkt player ids (same as dcaribou); injuries mostly 2007/08+ (218–397 per season before 2007) | CSV in GitHub `datalake/transfermarkt/<table>/<table>.csv` (some files via LFS) or Kaggle per-file download | **plain GET** (GitHub raw; Kaggle download works anonymously) | stated **CC0**; data scraped from Transfermarkt | **low** |
| 3 | **football-data.co.uk** | **G1** Europe stats: HT, referee (EPL), shots, cards, corners, attendance (2000–02) | E0-E3 + top divisions of ESP/ITA/GER/FRA/NED/BEL/POR/SCO/TUR/GRE from 1993/94; see §2.3 for fill rates | CSV `https://www.football-data.co.uk/mmz4281/{yyyy}/{E0,SP1,I1,D1,F1…}.csv` | **blocked by Etisalat on the laptop** (1st request OK, then TLS reset; HTTP → `safe.etisalat.ae` "Gambling"); fine from CI (n/t) | n/t (notes.txt unreachable) | **low** |
| 4 | **Wikidata P18/P154 + Commons extmetadata** (via QLever) | **G4** photos of players, referees, stadiums, some crests, with licence + author | 68,860 footballers and 1,432 referees with P18; Arab-country counts in §2.10 | SPARQL `https://qlever.cs.uni-freiburg.de/api/wikidata?query=` + `commons.wikimedia.org/w/api.php?action=query&prop=imageinfo&iiprop=extmetadata` (50 titles/call) | **plain GET** (WDQS itself rate-limited 1 req/min and 502 today) | per file: 48/50 sampled need attribution, all CC/PD | **low–med** |
| 5 | **footballcsv/cache.footballsquads** | **G1** season squads (shirt no., DOB, birthplace, previous club) → **G5** partial | ENG 1993/94+, GER/ITA/ESP 1995/96+, FRA/SCO 1998/99+, POR/AUS/NED(holland) 2001/02+, ARG 2004/05+, ~30 countries 2004+; national: Euro 1980+, AFCON 2004+, Copa 2004+ | text/CSV, 17,521 files `https://raw.githubusercontent.com/footballcsv/cache.footballsquads/master/{country}/{season}/{comp}/{club}.txt` | **plain GET** | repo CC0 (copy of footballsquads.co.uk) | **low** |
| 6 | **RSSSF `argtops.html` + de.wikipedia Oberliga list** (sources Tifo already uses) | **G3** Argentina per tournament 1891→ (AAm/FAF/LAF, Met/Nac, Ape/Cla, Ini/Fin) + cups page; Germany Oberligen 1947–63 | argtops 23 KB; dewiki 73 season rows ×5 Oberligen | HTML `rsssf.org/tablesa/argtops.html`, `argcuptops.html`; dewiki `action=parse&page=Liste_der_Torschützenkönige_der_Fußball-Oberliga` | **plain GET** | RSSSF credit; CC BY-SA | **low** |
| 7 | **11v11.com** | **G1** England (sample 2003/04) and internationals incl. **Arab national teams** (sample 1989): XI, subs with min, cards with min, scorers with min, referee, venue, attendance | "all English league matches since 1872" (site text; detail depth per era n/t) | HTML, one page per match `/matches/{slug}-{id}/`; season lists `/teams/{team}/tab/matches/season/{yyyy}/` | **plain GET**; robots allows `/matches/` | n/t (AFS site) | **high** (scrape) |
| 8 | **Kaggle European Soccer Database** (`hugomathien/soccer`) | **G1** 2008/09–2009/10 line-ups for 11 leagues (with X/Y positions); goal/card XML for ENG/ESP/ITA/GER | 25,979 matches 2008–2016; 11,060 players | SQLite 313 MB (34 MB zip) `https://www.kaggle.com/api/v1/datasets/download/hugomathien/soccer` | **plain GET, no account** (302 → signed GCS) | "Database: ODbL, Contents: © Original Authors" | **low** (but mostly superseded by ESPN) |
| 9 | **kooora.com Opta JSON** | **G2** only for 2007/08+: results, HT, Arabic club names, Opta ids; **no scorers/line-ups** | KSA, EGY, MAR, TUN, ALG, JOR, QAT list 2007/08→2026/27; AFC CL and CAF CL 2007→ | JSON `https://www.kooora.com/api/competition-matches?id={comp}&seasonId={sid}&gameSetTypeIds=`; match `__NEXT_DATA__` | **plain GET**; robots no Disallow | n/t | **low** (validate season by `startDate`) |
| 10 | **StatsBomb open-data** | **G1** full events + line-ups, but only 231 matches before 2011 | La Liga 2004/05–2010/11 Barcelona only (7–35/season), PL 2003/04 Arsenal (38), single finals (UCL 1970–2011, Copa del Rey, Arg 1981/1997, Serie A 1986/87) | JSON on GitHub `data/{competitions,matches,lineups,events}/…json` | **plain GET** | StatsBomb user agreement (LICENSE.pdf), attribution | **low** |
| 11 | **national-football-teams.com** | **G1/G5** national-team squads per year, caps/goals, DOB, birthplace, Arabic names, clubs; match line-ups (WC 1990 sample) | Egypt 1990: 82 players, 18 matches | HTML `/country/{id}/{year}/{name}.html`, `/player/{id}/…`, `/matches/report/{id}/…` | GET works, but **robots disallows AI agents (anthropic-ai, Claude-User, Claude-Web…) and sets Crawl-delay 60 for others** | n/t | **high** |
| 12 | **engsoccerdata (non-England)** | G1 minor: HT for Spain 1928→ (23,155/27,335 rows), European Cup 1955–2017 with HT/aet/pens/aggregate | ESP 1928–2024, ITA 1929–, FRA 1932–, NED 1956–, GER 1963–, BEL/POR/GRE/TUR/SCO 1994/95–, MLS, S. Africa | CSV `raw.githubusercontent.com/jalapic/engsoccerdata/master/data-raw/{country}.csv` | **plain GET** | no LICENSE in repo (GitHub API: null) | **low** (mostly duplicates schochastics) |
| 13 | **OpenLigaDB** | G1 Bundesliga goals with scorer + minute, attendance, stadium | only from 2009/10 (2005/06: 306 matches, 0 goals; 2002: 9 matches) | JSON `https://api.openligadb.de/getmatchdata/bl1/{yyyy}` | **plain GET** | n/t | low (tiny gain) |
| 14 | **openfootball / football.json** | nothing new: results + HT + kick-off; Arab leagues only 2023/24+ (Saudi 2024/25 only) | England archive 1992/93+, football.json 2010/11+ | Football.TXT / JSON on GitHub | plain GET | public domain | low |
| 15 | **TheSportsDB** (free key `123`) | crests/badges (n/t); events: no goal/line-up fields on free key | Egypt PL, Morocco, Qatar SL + Emir Cup, Kuwait PL/Emir/Crown Prince, Iraq, Jordan, Tunisia, Algeria listed; free key returns 5 seasons (2019+) and 15 events/season | JSON `/api/v1/json/123/{search_all_leagues,search_all_seasons,eventsseason}.php` | plain GET (full data needs paid key) | robots `Content-Signal: ai-train=no` | low |
| 16 | **Kaggle Arab datasets** | Egypt only: final tables 2000/01–2021/22 (328 rows); champions/runners-up 1948–2024 (xlsx, 140 rows); Egypt 2015/16+ goals/referees | none pre-2010 at match level | CSV/XLSX via Kaggle API | plain GET, no account | ODbL / CC BY-SA | low |
| 17 | **Arab federation / league sites** | nothing before 2010 found | SAFF 2019/20+; SPL 2011/12+ (Deltatre API); others blocked, down or no data (§2.13) | — | mixed | — | — |
| — | **Blocked / skip** | worldfootball.net, weltfussball.de, zerozero.pt, playmakerstats, football-lineups.com, fbref.com, footystats.org, efa.com.eg, frmf.ma: Cloudflare 403 "Just a moment…"; transfermarkt.com: 202, empty body; api.sofascore.com: 403; eu-football.info: 200 with 0 bytes; fussballdaten.de: robots disallows ClaudeBot/anthropic-ai, `Content-Signal: use=reference` | | | | | |

---

## 2. Per source: what I fetched and what came back

### 2.1 ESPN site API (rank 1)

- `https://sports.core.api.espn.com/v2/sports/soccer/leagues?limit=1000` → 200, **220 league codes**. Arab-relevant:
  `ksa.1`, `ksa.kings.cup`, `global.gulf_cup`, `afc.champions`, `afc.cup`, `afc.asian.cup`, `fifa.worldq.afc`,
  `caf.champions`, `caf.confed`, `caf.nations`. `egy.1`, `uae.1`, `qat.1` and `mar.1` → **400** (not in ESPN).
- `…/leagues/{code}/seasons?limit=200` → years: eng.1 2001–2026 (26); esp/ita/ger/fra/arg.1 2000–2026 (27);
  uefa.champions 2001+; **ksa.1 2022+**, ksa.kings.cup 2023+, global.gulf_cup 2024 and 2026 only; afc.champions
  **2006+**; caf.champions 2017+; caf.nations 2004+ (12); afc.asian.cup 2007+; fifa.worldq.afc 2006+; fifa.world 1930+.
- `…/site/v2/sports/soccer/eng.1/scoreboard?dates=20030816` → 7 events, each with attendance and `details` (goals and
  cards). `…/eng.1/summary?event=107368` (Arsenal 2–1 Everton, 2003-08-16) → keys `boxscore, gameInfo, rosters,
  keyEvents, commentary…`. Venue Highbury, attendance 38,014, officials `['M Halsey']`. Rosters of 16 (11 `starter:true`)
  with jersey, position, subbedIn/Out and per-player `plays` (clock, scoringPlay, yellowCard, redCard, substitution,
  penaltyKick, ownGoal). keyEvents: `34' Penalty - Scored`, `58' Goal`, `84' Goal`, substitutions with minutes.
- **The month query works:** `scoreboard?dates=YYYYMM&limit=500` (a `YYYYMMDD-YYYYMMDD` range → 400). Oct 2002: eng 32
  events, esp 31, ita 27, ger 33, fra 30. **Every scoring match had goal details with a named scorer.** Attendance was set
  on 31/32, 31/31, 27/27, 25/33 and 29/30. Oct 2007: 31/38/40/27/30 events, all scoring matches with details. Attendance was on
  31/31 England matches and 0 in the other four leagues.
- Summaries sampled (2001–2007):

| Sample | Rosters | Starters flagged | Referee | Attendance |
|---|---|---|---|---|
| esp.1 2000-10-29 | 0 | – | – | 0 (results only) |
| eng.1 2001-10-20 | 16/16 | 11/11 | U Rennie | 38,108 |
| esp/ita/ger/fra 2001-10-20/21 | 18 or 16 | **0** (squad only; cards/goals/subs per player) | yes | yes (ita, ger, fra) |
| esp/ita 2003-10-26 | 18/18 | 11/11 | ita yes | yes |
| ger/fra 2003-10-25 | **0/0** (first event of day) | – | – | – |
| Feb 2003, 4 random per league | eng 2/4, esp 4/4, ita 4/4, ger 1/4, fra 4/4 with rosters | 11/11 where present | mostly | mostly |
| Feb 2007, 4 random per league | 20/20 with rosters | 11/11 | England 3/4; **0/16 elsewhere** | England 4/4; **0/16 elsewhere** |
| afc.champions 2007-03-07, 2009-03-10 | 20/20, 18/18 | 11/11 | Naser Al-Ghafary; Mohammed Omar Al Saeedi | 30,000; 10,312 |
| caf.nations 2006-01-20 Egypt 3–0 Libya | 23/23 | 11/11 | – | 50,000 |
| afc.asian.cup 2007-07-10 Indonesia 2–1 Bahrain | 23/20 | 11/11 | Lim Kia Tong | 65,000 |
| fifa.worldq.afc 2004-03-31 | 0 events | | | |

- Caveats: undocumented, so it can change. Some matches have no rosters, so check each one. In 2001/02 starters are not
  flagged outside England. Outside England, referee and attendance mostly drop out after about 2006. robots.txt on both API hosts → 403.

### 2.2 salimt/football-datasets = Kaggle `xfkzujqjvx97n/football-datasets` (rank 2)

- Kaggle `GET /api/v1/datasets/list?search=football+injuries` → listed "5.7M+ Records - Most Comprehensive Football
  Dataset", 85,313,220 B, **CC0: Public Domain**, updated 2025-09-15. `GET /api/v1/datasets/list/xfkzujqjvx97n/football-datasets`
  lists `player_injuries.csv` 8.05 MB, `transfer_history.csv` 81.07 MB, `player_profiles.csv` 26.4 MB,
  `player_market_value.csv` 23.9 MB, `player_national_performances.csv` 5.1 MB, `player_performances.csv` 157.6 MB,
  `player_teammates_played_with.csv` 47.7 MB, `team_competitions_seasons.csv` 17.1 MB, `team_details.csv`,
  `team_children.csv`.
- Download: `https://www.kaggle.com/api/v1/datasets/download/xfkzujqjvx97n/football-datasets/player_injuries%2Fplayer_injuries.csv`
  → 302 → GCS, **no account**. An unescaped `/` in the file path returns an HTML page instead.
- `player_injuries.csv`: **143,195 rows, 34,561 players**. Columns `player_id, season_name, injury_reason, from_date,
  end_date, days_missed, games_missed`. Sample: `10,15/16,Hand injury,2016-04-19,2016-04-29,11.0,2` (TM id 10 = Klose).
  Per season: 00/01 218 … 06/07 397, 07/08 1,386, 08/09 1,993, 09/10 1,772, then rising to 15,102 in 24/25. A few in the
  1970s–1990s.
- `transfer_history.csv`: **1,101,440 rows, 117,944 players**. Columns `player_id, season_name, transfer_date,
  from_team_id, from_team_name, to_team_id, to_team_name, transfer_type, value_at_transfer, transfer_fee`. By decade:
  1980s 2,584 · **1990s 37,382 · 2000s 197,859** · 2010s 477,174 · 2020s 385,821. dcaribou `transfers.csv.gz` (fetched
  for comparison) has 175,165 rows: 1990s 76, 2000s 6,165. Rows touching Arab-named clubs (a rough regex): 1990s 79,
  2000s 1,036.
- GitHub `repos/salimt/football-datasets`: pushed 2026-09-29; README "93000+ players from Transfermarkt", badge "Last
  Updated October 2025"; there is also `player_injuries_updated_20260929.csv` (9.46 MB). `transfer_history.csv` and
  `player_performances.csv` in git are 133–134 B pointers, so take those from Kaggle. The repo has no LICENSE file (GitHub
  API returned no licence).

### 2.3 football-data.co.uk (rank 3)

- `https://www.football-data.co.uk/mmz4281/0001/E0.csv` → 200, 62,076 B, redirected to `football-data.co.uk`. Header:
  `Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,Attendance,Referee,HS,AS,HST,AST,HHW,AHW,HC,AC,HF,AF,HO,AO,HY,AY,HR,AR,HBP,ABP,GBH,…`.
  Row: `E0,19/08/00,Charlton,Man City,4,0,H,2,0,H,20043,Rob Harris,17,8,14,4,…`. `…/0102/E0.csv` → 380 rows, HT 380,
  Referee 380, Attendance 379, shots/cards/corners 380.
- **Every later request (32) failed**, with and without `www`: TLS reset (curl exit 35, `schannel: failed to receive
  handshake`). `http://www.football-data.co.uk/…` → 200 with an iframe to
  `safe.etisalat.ae/?…&urlclassname=R2FtYmxpbmc=` ("Gambling"). **The ISP blocks it, not the site.** I did not try to get
  around the block.
- Fill rates were checked on the GitHub mirror **jokecamp/FootballData** (465 original CSVs, last commit 2023-12-12; the
  files run to 2013/14):

| League | HT score | Referee | Shots, cards (HS, HY) | Corners | Attendance |
|---|---|---|---|---|---|
| EPL (E0) | 1995/96+ | **2000/01+** | 2000/01+ | 2000/01+ | 2000/01–2001/02 only |
| Bundesliga (D1) | 1995/96+ | 2000/01–2001/02 | 2000/01–01/02, 2003/04+ | same | 2000/01–2001/02 |
| Serie A (I1) | 1995/96+ | 2005/06–2006/07 | 2005/06+ | 2005/06+ | — |
| La Liga (SP1) | 1995/96+ | — | 2005/06+ | 2005/06+ | — |
| Ligue 1 (F1) | 1995/96+ (1995/96 311/380, 1996/97 353/380, 1997/98 272/306) | — | 2005/06+ | 2006/07+ | — |

  1993/94 and 1994/95: results only (28 columns, mostly odds). The mirror also has BEL, NED, POR, SCO, TUR and GRE.
  The site's "extra leagues" (`/new/*.csv`), its terms and `notes.txt` were n/t because of the block.

### 2.4 Wikidata + Commons (rank 4)

- WDQS `query.wikidata.org/sparql`: the first query (Arab-country footballers) → 200. The next ones → **429 "Aggressively
  rate-limiting to 1 req / min … during active wdqs outage"**, then 502. I switched to **QLever**
  (`qlever.cs.uni-freiburg.de/api/wikidata`, plain GET, 1–2 s per query).
- Footballers (P106 = Q937857) by citizenship, with P18: Saudi 2,267 / 100 · Algeria 2,098 / 292 · Morocco 1,399 / 480 ·
  Egypt 1,092 / 220 · Tunisia 1,091 / 268 · UAE 660 / 44 · Iraq 547 / 124 · Bahrain 490 / 16 · Qatar 480 / 88 · Kuwait
  458 / 13 · Lebanon 320 / 168 · Jordan 295 / 34 · Syria 257 / 52 · Oman 175 / 17. Worldwide: **393,282 footballers,
  68,860 with photo; 7,960 referees (Q859528), 1,432 with photo.**
- Clubs (P31 = Q476028) by country, with logo P154 and with image P18: Iraq 292 / 0 / 1 · Algeria 217 / 11 / 5 · Morocco
  201 / 10 / 14 · Saudi 198 / 8 / 1 · Tunisia 159 / 5 / 4 · Egypt 130 / 1 / 5 · UAE 60 / 1 / 1 · Lebanon 55 / 2 / 2 ·
  Jordan 43 / 0 / 0 · Syria 42 / 13 / 1 · Oman 34 / 1 / 0 · Qatar 23 / 0 / 1 · Bahrain 19 / 0 / 1 · Kuwait 17 / 1 / 1.
  **Crests are close to absent.** Commons `categoryinfo`: "Association football logos of Saudi Arabia" 18 files, "…of
  Egypt" 6, "…of Morocco" 33.
- Stadiums (P31 = Q483110), with image: Algeria 66 / 37, Iraq 52 / 5, Morocco 50 / 23, Tunisia 35 / 15, Saudi 32 / 14,
  Egypt 30 / 12, UAE 27 / 11, Qatar 23 / 10, Kuwait 17 / 4, Syria 17 / 15, Lebanon 13 / 9, Jordan 10 / 4, Oman 9 / 4,
  Bahrain 5 / 1.
- Licences: 50 P18 files of Arab-country players, one Commons call
  (`prop=imageinfo&iiprop=extmetadata|url|size&iiextmetadatafilter=LicenseShortName|UsageTerms|Artist|AttributionRequired`).
  Result: CC BY-SA 4.0 22, CC BY 2.0 10, CC BY-SA 3.0 8, CC BY 4.0 4, CC BY-SA 2.0 2, CC BY 3.0 2, CC0 1, PD 1.
  **AttributionRequired true on 48 of 50.** Store `Artist` and `LicenseShortName` with each image.
- Bulk recipe: QLever SPARQL for `?entity ?P18|?P154` in pages of thousands, then Commons `extmetadata` for 50 titles per
  call, then thumbnails via `Special:FilePath/<name>?width=…`.

### 2.5 footballcsv/cache.footballsquads (rank 5)

- `gh api repos/footballcsv/cache.footballsquads/git/trees/HEAD?recursive=1` → 17,521 files. Season folders per country:
  eng 31 (1993-1994…2023-2024), ger 29 (1995-1996…), italy 29 (1995-1996…), spain 29 (1995-1996…), france 26
  (1998-1999…), scots 26 (1998-1999…), portugal 23 (2001-2002…), holland 10 (2001-02…2010-11) + netherl 13, usa 24,
  arg 21 (2004-2005…, Apertura/Clausura folders), brazil 20, and about 20 more from 2004/05. National: eurocham euro1980
  onwards, africacn acn2004…acn2023, copaamer ca2004…, confed, worldcup.
- `eng/1995-1996/faprem/liverpool.txt` → `Number, Name, Pos, Height, Weight, Date of Birth, Birth Place, Previous Club`,
  e.g. `1, David James, G, 6'05", 14 02, 01-08-70, Welwyn, Watford`. README says names and dates are copied as is.
  LICENSE.md is CC0 1.0.

### 2.6 Top scorers (rank 6: G3)

- `https://www.rsssf.org/tablesa/argtops.html` → 200, 23 KB. **Amateur era from 1891** (`1891 Archer, Frederic, Buenos
  Aires & Rosario Railways 7`; `1934 AAF Lupo, Oscar, Defensores de Belgrano 21`), then per tournament with codes
  Met/Nac/Ape/Cla/Ini/Fin/LAF through 2014+ (`1985 Nac Comas Romero…12`, `1991/92 Ape Díaz, Ramón Ángel`). The cups
  page is `argcuptops.html` (n/t).
- `https://www.rsssf.org/tablesd/duittops.html` starts at **1963/64** (Uwe Seeler 30). `duit-ol-west4563.html` and
  `duit-ol-west4748.html` give Oberliga results only, with no scorers.
- de.wikipedia `Liste der Torschützenkönige der Fußball-Oberliga` (API `action=parse`) → 30,904 chars. Sections Nord,
  West, Südwest, Süd, Stadtliga Berlin; **73 season rows from 1947/48**. **German championship before 1945** (final
  rounds and Gauligen): no list found (n/t beyond this search). worldfootball "goalgetter" pages exist but are behind
  Cloudflare.
- Arab cups top scorers: no source found.

### 2.7 11v11.com (rank 7)

- `/teams/arsenal/tab/matches/season/2004/` → 200, 188 match links. The page says "all English league matches since 1872,
  and all England (and most other) internationals".
- `/matches/arsenal-v-blackburn-rovers-14-december-2003-18187/` → referee Andy D'Urso, venue Highbury, attendance
  37,677, manager, scorer with minute (Bergkamp 11), both starting XIs with positions, subs with minutes (Parlour for
  Bergkamp 74), cards with minutes (Gilberto Silva 29 Y), bench, unused subs.
- `/teams/saudi-arabia/tab/matches/season/1990/` → 5 matches. `/matches/qatar-v-saudi-arabia-16-october-1989-242083/`
  (WC qualifier) → referee Zoran Petrović, venue Kallang, attendance 15,510, scorers with minutes (Mansoor Muftah 87,
  Saadoun Al Suwaiti 3), both XIs, subs with minutes.
- robots.txt has 46 lines, only forum/CMS paths disallowed, no AI rules and no crawl-delay. One page per match, so this is
  heavy scraping.

### 2.8 Kaggle European Soccer Database (rank 8)

- `GET /api/v1/datasets/view/hugomathien/soccer` → 200: "25k+ matches…", 313,090,048 B, licence "Database: Open
  Database, Contents: © Original Authors". Download without an account → 34,297,253 B zip → `database.sqlite`.
- Tables `Match` (115 columns incl. `home_player_1..11` with X/Y and `goal, shoton, shotoff, foulcommit, card, cross,
  corner, possession` as XML), `Player` (11,060), `Team`, `League`, `Player_Attributes`, `Team_Attributes`. 25,979
  matches.
- 2008/09 and 2009/10 (matches / with line-ups / with goal XML / with card XML): EPL 380/380/349/363 and
  380/380/355/356; La Liga 380/371/366/376 and 380/376/351/373; Serie A 380/380/364/372 and 380/380/352/376;
  Bundesliga 306/294/291/300 and 306/306/280/288; Ligue 1 380/375/0/0 and 380/378/0/0; NED, POR, BEL, SCO, SUI, POL:
  line-ups partial in 2008/09 (61–228) and fuller in 2009/10, no events. Goal XML holds `elapsed`, `player1` (scorer),
  `player2` (assist) and `subtype`.

### 2.9 kooora Opta JSON (rank 9)

- The navigation on a 404 page lists competition ids: KSA `ea0h6cf3bhl698hkxhpulh2zz`, EGY `8k1xcsyvxapl4jlsluh3eomre`,
  MAR `1eruend45vd20g9hbrpiggs5u`, TUN `f4jc2cc5nq7flaoptpi5ua4k4`, ALG `57nu0wygurzkp6fuy5hhrtaa2`, JOR
  `145hkd59i6foieuwr4mwi6wlq`, QAT `xaouuwuk8qyhv1libkeexwjh`, UAE `f39uq10c8xhg5e6rwwcf6lhgc`, AFC CL
  `1fedahp0rws09tj451onten8r`, CAF CL `cse5oqqt2pzfcy8uz6yz3tkbj`, plus the big-5 Europe, UCL and UEL.
- The competition pages (`/كرة-القدم/مسابقة/<slug>/<id>`, `__NEXT_DATA__`) list seasons. **Every Arab league starts at
  2007/2008**: KSA 20 seasons, EGY 20, MAR 20, TUN 20, ALG 20, JOR 19, QAT 20, all up to 2026/2027. AFC CL and CAF CL
  start at 2007.
- `competition-matches`: KSA 2007/08 → 22 gamesets, 132 matches; EGY 2008/09 → 31 gamesets, 241; MAR 2007/08 → 30,
  240. Match keys: `id, startDate, competition, gameset, status, teamA, teamB (Arabic names, Opta ids), redCards, score,
  aggregateScore, penaltyScore, link, venue (null)`.
- **The cache trap is still there with the empty `gameSetTypeIds=`.** KSA 2009/10 (`RPwpmPIFsdWaCy_YpOan4`) returned the
  correct season once (first match 2009-08-18) and the **2007/08 copy** twice, including with an extra `&t=1`. Accept a
  response only when `startDate` falls inside the season.
- Match pages: EGY 2009-01-31 الجيش 2–2 الأهلي → `halfTime {1,1}`, `scorers {teamA:[],teamB:[]}`, `lineups` null.
  MAR 2008-01-19 → same. KSA 2007-11-06 النصر 1–3 الهلال → scorers empty. **Results + HT + Arabic names only**, the same
  as the UAE finding.

### 2.10 StatsBomb open data (rank 10)

- `data/competitions.json` → 80 competition-seasons. Before 2011 (`data/matches/{comp}/{season}.json`): La Liga
  2004/05 7, 05/06 17, 06/07 26, 07/08 27, 08/09 31, 09/10 35, 10/11 33 (all Barcelona); PL 2003/04 38 (all Arsenal);
  one match each for UCL finals (1970/71, 71/72, 72/73, 99/00, 03/04, 04/05, 06/07, 08/09, 09/10, 10/11), Copa del Rey
  (77/78, 82/83, 83/84), La Liga 1973/74, Serie A 1986/87, Argentina 1981 and 1997/98. **Total 231.**
- `data/lineups/3749493.json` (Arsenal–Everton 2003-08-16): Everton 14 and Arsenal 13 players with positions from/to,
  cards (`Wayne Rooney Yellow Card 76:54`), substitution reasons. Licence: `LICENSE.pdf` (user agreement).

### 2.11 national-football-teams.com (rank 11)

- `/continent/2/Africa.html` → Egypt id 57, Algeria 3, Morocco 125, Tunisia 190, Libya 106, Sudan 176.
  `/country/57/1990/Egypt.html` → 82 player links, 18 match links. `/player/12994/Hossam_Hassan.html` → Arabic name
  "حسام حسن حسين", DOB 1966-08-10, birthplace, height, FIFA matches 173, a clubs tab.
  `/matches/report/20742/Netherlands_Egypt.html` (WC 1990) → both XIs with caps/goals, subs, coach.
- robots.txt: a long AI-agent list (`anthropic-ai`, `Claude-SearchBot`, `Claude-User`, `Claude-Web`, GPTBot…) gets
  `Disallow: /`; everyone else gets `Crawl-delay: 60`. I read robots.txt after fetching 5 pages. **Do not use it through
  an AI agent.** A normal crawler at one page per minute is slow.

### 2.12 engsoccerdata non-England, OpenLigaDB, openfootball, TheSportsDB (ranks 12–15)

- engsoccerdata `data-raw/` (GitHub API) holds belgium, champs, france, germany, germany2, greece, holland, italy, mls,
  portugal, safrica, scotland, spain, turkey, england5, england_nonleague (+ `dfbpokal.csv` with 4 rows). Downloads: spain
  27,335 rows 1928–2024 (`Date,Season,home,visitor,HT,FT,…`, HT 23,155 filled); italy 28,824 1929–2024; france 29,558
  1932–2024; germany 38,918 1963–2024 (tiers 1–2); holland 20,776 1956–2024; champs 6,556 1955–2017 (HT 4,851, aet,
  pens, aggregates, countries); belgium, portugal, greece, turkey 1994/95–2024; scotland 22,079 1994–2024 (tiers 1–4);
  mls 1996–2016; safrica 2002–2019. **No scorers anywhere.**
- OpenLigaDB `getmatchdata/bl1/2002` → 9 matches, goals unnamed; `/2005` → 306 matches, 0 goals; `/2009` → 306 matches,
  697 goals all with scorer and minute, attendance, stadium.
- openfootball: 37 repos (GitHub API). `world` has Africa (Algeria, Egypt, Morocco 2023/24–2024/25), middle-east (Saudi
  2024/25, Israel), no Gulf or Levant. `england` has archive 1992/93–1999/00, then 2000/01+. `2005-06/1-premierleague.txt`
  holds results + HT + kick-off, no scorers. `football.json` starts 2010-11.
- TheSportsDB `search_all_leagues.php?c=…&s=Soccer`: "Saudi-Arabia" and "United-Arab-Emirates" → empty. Egypt: Egyptian
  Premier League (4829, formed 1948) + League Cup. Morocco: Botola + Botola 2. Qatar: Stars League, Emir Cup (4971,
  1972), QSL Cup. Kuwait: PL, Emir Cup, Crown Prince Cup, Div 1. Iraq 5056, Jordan 5055, Tunisia 4828, Algeria 4753.
  `search_all_seasons` → 5 seasons (2019-2020…2023-2024). `eventsseason` → 15 events per season with goal details,
  line-ups, referee and spectators all null.

### 2.13 Kaggle / Hugging Face / GitHub searches for Arab football (rank 16)

- The Kaggle anonymous `datasets/list?search=` was run for 15 terms (Saudi, Egypt, Botola, Qatar, UAE, Arabian Gulf, Arab,
  Tunisia, Algeria, Iraq, Kuwait, Gulf Cup, AFC CL…). Football-relevant hits:
  - `ahmedibrahim72/egyptian-premier-league-from-2000-till-2022` (final tables, 328 rows: `Season,Pos,Team,Pld,W,D,L,
    GF,GA,GD,Pts,…`)
  - `eslamsheha/egyptian-premier-league-history-19482024` (xlsx A1:L141: champions and runners-up, notes such as
    "1962(Two_Groups)", "1971(Not_Completed)")
  - `ahmedaelgohary/10-seasons-egyptian-league` (goals and referee CSVs, 2015/16–2024/25)
  - `rossi14/saudi-pro-league-transfers` and `mohammedalsubaie/transfer-of-players-in-saudi-league` (2023–24)
  - `saudidata2030/spl-stats-last-4-years`
  - `ronaldoaf/football-matches-with-odds-from-oddsportal`: its `leagues.csv` has Algeria 2016/17+, Bahrain 2015/16+,
    Egypt 2015/16+, Jordan 2016/17+, Morocco 2018/19+
  - "Al Hilal Archive Scores" (one club, 1961–2019, seen via a Baselight mirror), `yousefalaqil/al-hilal-archive-scores`
    → 403 (wrong slug, n/t)
  - **Nothing at match level before 2010 for any Arab league.**
- Hugging Face `api/datasets?search=` for saudi league, egyptian league, botola, football lineups history → 0 results.
  "soccer historical" → 1 (odds sample). `gh search repos "saudi league dataset"` → 0.

### 2.14 Arab federation / league / confederation sites (rank 17)

| Site | Result |
|---|---|
| `www.spl.com.sa/` | 404; `/ar` and `spl.com.sa/en` → 200, 1.3 MB Next.js. Config `SDP_API_URL_WITH_VERSION: https://api-sdp.spl.com.sa/v1/` (Deltatre-style, `spl::Football_Season::…` ids) and `dapi.spl.com.sa/v2/content/…`; **seasonName 2011/2012…2026/2027 only**. Endpoints n/t |
| `www.saff.com.sa` | 200 (cp1256 PHP). `championships.php` lists about 50 `championship.php?id=` (434 King's Cup, 415 Roshn League, 455 Super Cup). The King's Cup season selector runs **2019-2020…2026-2027** only |
| `www.qsl.com.qa`, `/ar` | timeout (WinError 10060) twice |
| `www.qfa.qa` | 200, 241 KB; only `api.fifa.com` flag images found; no data API |
| `www.efa.com.eg`, `www.frmf.ma` | 403 Cloudflare challenge |
| `www.lnfp.ma` | 200, a static current-season page with tabs, no data endpoints |
| `www.ftf.org.tn` | 200, WordPress 4.9; `/fr/wp-json/wp/v2/types` → post, page, attachment only (no match types) |
| `www.lfp.dz`, `www.faf.dz` | timeout |
| `www.kfa.org.kw`, `www.ofa.om` | DNS failure (wrong domain or down; n/t further) |
| `www.bfa.bh`, `www.uafa.com` | 200, 4–5 KB placeholder pages |
| `www.jfa.jo`, `www.cafonline.com` | 200 (81 KB, 113 KB); not explored (n/t) |
| `www.the-afc.com` | 200, Nuxt; references `https://api.the-afc.com/sportdb-connector/api/v1/` (endpoints not found in the HTML, 66 JS bundles not opened; n/t) |
| Iraq, Syria, Lebanon federations | n/t |
| `www.alahlyegypt.com/ar/football/results` | 200, app-router page with no `__NEXT_DATA__`; season depth n/t |
| `www.filgoal.com/matches/20000` | 200 coverage page (Mallorca–Osasuna, La Liga), no line-up/scorer text server-side; depth n/t |

### 2.15 Blocked or restricted (checked once, then moved on)

- Cloudflare 403 "Just a moment…": worldfootball.net, weltfussball.de, zerozero.pt, playmakerstats.com,
  football-lineups.com, fbref.com, footystats.org (datasets page), efa.com.eg, frmf.ma.
- transfermarkt.com → **202 with an empty body** (AWS WAF). api.sofascore.com → 403 (48 B). eu-football.info → 200 with
  **0 bytes**.
- fussballdaten.de → 200 with full detail: a 1995/96 match page has referee Hans-Jürgen Kasper, attendance 42,800,
  scorers, cards and substitutions. But **robots.txt disallows ClaudeBot, anthropic-ai and Claude-Web** and sets
  `Content-Signal: search=yes, ai-train=no, use=reference` for everyone. I fetched 3 pages before reading robots.txt. Not
  usable as a bulk source.
- footballdatabase.eu → 200 (Cloudflare script present but no challenge); robots blocks only `/ajax/`, `/xml` and similar.
  Arab depth n/t.
- Power BI "publish to web": search results show only EPL, SPFL, top-5 and UCL reports built from football-data.co.uk,
  FBref and sports-statistics.com. **Nothing Tifo lacks.** No Arab league report found.

---

## 3. Recommended loading order (top 5)

1. **ESPN site API, big 5 from 2001/02 to 2009/10 plus UCL, ACL 2006–09, AFCON 2004–08 and Asian Cup 2007.** It is the
   only plain-GET source with line-ups, scorer minutes, cards and subs for the 2000s at scale. One month call plus one
   summary per match, about 17k calls at 1/s, run in stages that can resume.
2. **salimt/football-datasets: injuries and transfer_history.** It fills G5 almost on its own (143k injuries, 1.1M
   transfers, 30× dcaribou's 2000s coverage), it is keyed on the same Transfermarkt ids Tifo already uses, and it is a few
   CSVs.
3. **football-data.co.uk, from CI rather than the laptop.** HT from 1995/96 and EPL referees and stats from 2000/01 for
   about 20 files per season. It cross-checks ESPN and covers 1995–2001, which ESPN lacks.
4. **Wikidata P18/P154 via QLever + Commons extmetadata.** About 69k player photos with machine-readable licence and
   author, in a few hundred calls. Expect few Gulf photos and almost no Arab crests, so crests still need another plan.
5. **RSSSF `argtops.html` / `argcuptops.html` + dewiki Oberliga top-scorer list, then footballsquads.** These are cheap G3
   wins from sources Tifo already parses. footballsquads (CC0) adds shirt numbers, DOB and previous club for big-5 squads
   from 1993–98.

Then, by hand or targeted: 11v11 for England before 2001 and for Arab national-team line-ups (one page per match, polite
rate). G2 (Arab 1970s–1990s results and cups) has **no bulk source**; it stays RSSSF + Wikipedia + newspaper work.

## 4. Scripts and raw responses (not in the repo)

Scripts are in `%TEMP%/fbs_scripts/` (`f.py` fetch helper with per-host spacing, `espn_*.py`, `kooora_*.py`, `jc.py`,
`kaggle_*.py`, `qlever.py`, `site_probe.py`; `requests.log`). Raw responses are in `%TEMP%/fbs_dl/` (ESPN JSON, kooora
season JSON, engsoccerdata CSVs, Kaggle files incl. `esd/database.sqlite`, `kag/player_injuries.csv`,
`kag/transfer_history.csv`).
