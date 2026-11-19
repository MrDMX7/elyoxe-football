# Tifo graph: one connected football database — spec

**Date:** 2026-11-19. Approach A approved by the owner the same day («نعم أوافق»), order: phase 1, then 2 and 3.

**Status:** phase 1 built 2026-11-19: 1.43M matches, 106k players, 27.6k teams, one competition per competition across sources (`docs/GRAPH-COVERAGE-2026-11-19.md`); the `graph` stage of the nightly database job publishes `tifo.db` (S3 `graph/`, private) and `v1/graph/coverage.json`.

**The owner's words (2026-11-19):** «اريد نخليه موقع متكامل… الاحصائيات و النتايج والانتقالات وكل شي مأرشف عندنا، اريد
البيانات بأصولها لأقدم مدى نقدر عليه وكل شي مربوط ببعضه… مدربين واندية ومنتخبات و مباريات و احصائيات وبطولات… كلهم شبكة»;
individual awards (Ballon d'Or, Golden Boot), a sub-section for man of the match, every tournament with its best player and
top scorer; «يوم نقول احصائية او ننشر خبر او مقال، احصائياتنا تكون كافية ما نحتاج مصادر خارجية، نصير احنا المصدر»; a match's
stats move into the database at the final whistle.

**Success:** any football fact Tifo publishes (page, article, post) is answered from one database of ours, with its source
recorded; every entity page links to every entity it touches; a finished match is in that database within minutes.

## 0. Where we start (measured 2026-11-19)

The data is large but split into islands, each with its own ids and its own pages:

| source | what we hold | ids |
|---|---|---|
| FotMob match details (`db/.cache/fm/mx/`) | 92,409 matches since 2010/11; lineups from ~2016, full player stats in recent seasons | FotMob |
| FotMob profiles / world (`fm/p`, `fm/t`) | 65,533 players, 4,067 clubs, ~300 leagues | FotMob |
| schochastics `games.parquet` | 1.3M league and continental results since 1888, score only | name strings «Club (Country)» |
| 365Scores (`s365/`) | champions of ~640 competitions, Arab final tables, Arab leagues FotMob lacks | 365 |
| Transfermarkt salimt CSVs (`tm/`) | 92.7k profiles, 1.88M season lines, 168k injuries | TM (mapped to FotMob by `tmdata.py`) |
| Transfermarkt dcaribou (`tm_games`, `tm_game_events`) | games and events since 2012, big leagues | TM |
| RSSSF (`rsssf/`) | old seasons of the Arab leagues | names |
| martj42 | every men's international since 1872 | names |

Links between islands exist only pairwise and partly: `crosswalk.json` (669 clubs FotMob↔schochastics), `fmmap.json`
(FotMob↔365 teams), `history/tm/index.json` (FotMob↔TM players). The same club has three page families (`/t/`,
`/db/team/`, `/db/club/`); encyclopedia pages render in the browser with `noindex`.

**Missing entirely:** individual awards; man of the match as the source names it; per-edition honours beyond the champion
(best player, top scorer, best goalkeeper, young player); coach tenures with dates; player career and encyclopedia
updates before the next daily run (04:10 UAE).

Checked the same day, free and working: Wikidata SPARQL with Arabic labels (Ballon d'Or: 47 winners of ~70, so incomplete
on its own); jfjelstul/worldcup (every World Cup since 1930 with matches, goals, cards, squads, managers and `award_winners`);
dcaribou transfermarkt-datasets on its public R2 bucket (`appearances.csv.gz` 45 MB).

## 1. The programme

| phase | delivers | depends on |
|---|---|---|
| **1. Core** (this spec) | `tifo.db`: Tifo ids, the crosswalk, every source we already hold loaded with provenance, a coverage report | — |
| 2. Awards and honours | individual awards (Ballon d'Or, European Golden Shoe, The Best, Golden Boy, Yashin, AFC/CAF player of the year, tournament Golden Ball/Boot/Glove), per-edition honours (champion, runner-up, top scorer, best player, best goalkeeper, young player); `/awards/` | 1 |
| 3. Man of the match | FotMob's player of the match for every match it names, the top rating where it does not; counts by season, competition, coach, opponent; `/motm/`, beside the fans' vote | 1 |
| 4. Depth | the World Cup since 1930 (Fjelstul), internationals since 1872, leagues since 1888, lineups since 2012 (dcaribou), season top scorers (RSSSF) | 1 |
| 5. Coaches | tenures with dates (Wikidata P286 qualifiers, Transfermarkt), each tenure's record computed from our matches | 1, 4 |
| 6. At the whistle | the poller applies a finished match to the graph's published files within minutes | 1 |
| 7. Pages | one static page per entity, all cross-linked, indexed only above a richness floor | 1–5 |
| 8. Tifo the source | articles, «اسأل تيفو» and the social cards take their numbers from the graph | 1–7 |

Each phase gets its own spec section, plan and implementation; this document details phase 1 and fixes the frame the
later phases build on (ids, tables, provenance, where it runs).

## 2. Architecture (all phases)

- **Store:** one SQLite file, `tifo.db` (stdlib `sqlite3` 3.50; DuckDB is already installed for heavy reads over it and
  over parquet). It is a build artefact, rebuilt from the source caches, never edited by hand.
- **Where it runs:** a new stage `graph` in `db/refresh.py`, daily on GitHub Actions (`tifo-database.yml`), after every
  stage that fills a cache it reads and before `audit`. Cost: $0 (the runner and actions/cache we already use).
- **Persistence:** the id registry (§3.2) is the only state that must survive; it lives in S3 `state/graph/registry.json.gz`
  and in actions/cache. `tifo.db.gz` is also kept in S3 `graph/` (private, not under `v1/`) so the laptop, phase 6 and
  phase 8 can read it.
- **Publishing:** phase 1 publishes only the coverage report (`v1/graph/coverage.json`). Entity files and pages are
  phase 7; until then nothing the site reads changes.
- **One function for batch and live:** the code that turns a match into rows (phase 1) is the code phase 6 runs at the
  whistle, so the nightly build and the live update can never disagree.

## 3. Phase 1 in detail

### 3.1 Entities and tables

Every row carries `src` (which source said it) and, where the source has one, `src_id`.

| table | key | content |
|---|---|---|
| `team` | `tid` | name, name_ar, kind (club / national / youth), country, founded, stadium `sid` |
| `player` | `pid` | name, name_ar, native-script name, born, birthplace, nationality, second nationality, position, height, foot |
| `coach` | `kid` | name, name_ar, born, nationality , `pid` (nullable: the same person's player id when they also played) |
| `referee` | `rid` | name, country |
| `stadium` | `sid` | name, name_ar, city, country, lat/lon, capacity |
| `competition` | `cid` | name, name_ar, kind (league / cup / tournament / supercup), scope, country, tier |
| `edition` | `eid` | `cid` + season label (the source's own: «2026/2027», «2026»), start, end |
| `match` | `mid` | `eid`, round, date (UTC), home/away `tid`, score, half-time score, extra time, penalties, status, `sid`, `rid`, attendance |
| `appearance` | `mid, pid` | team, started, minutes, position, shirt, captain, rating, goals, assists, cards, the stats blob |
| `event` | `mid, seq` | minute, added, type (the poller's event types), team, `pid`, second `pid` (assist / player off) |
| `match_coach` | `mid, side` | `kid` on the bench |
| `standing` | `eid, group, rank` | final or current table row |
| `honour` | `eid, kind, rank` | kind: champion, runner_up, … (phase 2 adds top_scorer, best_player…); `tid` or `pid` |
| `transfer` | id | `pid`, from/to `tid`, date, fee, type (loan, free, return) |
| `spell` | `pid, tid, from` | membership of a squad with dates, apps, goals (FotMob career, TM season lines) |
| `player_season` | — | Transfermarkt's season × competition × club lines: apps, minutes, goals, assists, cards, clean sheets |
| `injury` | id | `pid`, from, to, kind, games missed |
| `xref` | `type, tifo_id, source, source_id` | the crosswalk: method (`fotmob-native`, `vote`, `birthdate+name`, `wikidata`, `manual`), confidence |
| `conflict` | id | the same fact from two sources that disagree: both values, both sources, which one the graph keeps and why |

**Precedence when sources disagree** (a fact is kept from the first source that has it, the others go to `conflict`
when they differ): FotMob > 365Scores > Transfermarkt > Fjelstul / RSSSF > schochastics > martj42 > Wikidata. Phase 2 sets
its own order for awards (official body page > Wikipedia list > Wikidata).

### 3.2 Tifo ids

- Integers, one sequence per entity type, never reused. The registry maps `(type, source, source_id) → tifo_id`.
- **Minting:** an entity seen first time gets the next number; FotMob-native entities are minted first, in FotMob id
  order, so the first build is deterministic.
- **Merging:** when linking later finds that two Tifo ids are one entity, the lower id survives and the other is kept as
  `merged_into`, so a published link never breaks.
- **Stability test:** two builds from the same caches give byte-identical registries; a build after a new source adds
  ids without changing any existing one.

### 3.3 Linking (entity resolution)

Never by name alone; every link records its method.

| pair | rule (existing code reused) |
|---|---|
| FotMob ↔ schochastics clubs | `db/history.py` vote: same date ±1 day and same score, ≥ 5 votes, ≥ 70 %, both directions agree |
| FotMob ↔ 365 teams | `db/scores365.py` fmmap (same country, name equal in English or Arabic, one to one) |
| FotMob ↔ Transfermarkt players | `db/tmdata.py` (birth date + name rules) |
| FotMob ↔ TM clubs | the transfers' club pairs already mapped in `history/.cache/tm_clubmap.json` |
| matches across sources | same date ±1 day, both teams linked, same score; a match found in two sources is one `mid` with two `xref` rows |
| national teams ↔ martj42 | the 22 Arab teams' existing map in `compute/national.py`, extended to every country by FIFA code |

The build prints and stores per pair: candidates, linked, ambiguous (left unlinked), and 20 sampled links for a manual
look.

### 3.4 Loaders

One module per source under `graph/load/`, each a function `load(db, cache_dir)`:
`fotmob_matches` (mx records → match, appearance, event, referee, stadium, coach from lineups), `fotmob_profiles`
(players, teams, career spells), `world` (leagues, clubs), `s365` (champions → honour, tables → standing, Arab leagues'
matches), `schochastics` (results 1888–), `rsssf`, `tm_salimt` (profiles, season lines, injuries), `tm_dcaribou` (games,
events), `martj42`, `transfers` (FotMob all-transfers + TM). A loader reads caches only, never the network; a missing cache
makes it skip with a line in the report, never fail the build.

### 3.5 The coverage report

`docs/GRAPH-COVERAGE-<date>.md` and `v1/graph/coverage.json`, written each build:

- per competition × edition: matches known, with score, with lineups, with events, with player stats, with ratings;
  champion known, runner-up known, final table known;
- per entity type: count, share linked to each other source, share with Arabic name, with birth date, with photo;
- the gaps ranked by what the site shows most (the competitions in `competitions.yaml` first), so phases 2–5 start from
  the biggest hole;
- `conflict` counts per source pair.

### 3.6 Query helper

`python -m graph.q "<sql>"` and `graph.q.query(sql, params)` over `tifo.db` (read-only connection), for checking facts by
hand now and for phase 8.

### 3.7 Not in phase 1

No new sources, no change to the poller, no new or changed page, no change to any published file except
`v1/graph/coverage.json`.

## 4. Error handling

- A loader that raises is caught: the build continues, the report lists the loader as failed with its error, and the
  stage exits non-zero only when the FotMob loader fails (without it the graph is meaningless).
- The registry is written only after a build that passes the stability checks (§3.2); otherwise the previous one stays.
- `tifo.db` is published to S3 only when its match count is ≥ 95 % of the previous build's (the same guard idea as the
  site's 85 % page guard).

## 5. Testing

- pytest in `tests/test_graph_*.py` on small fixture caches (a handful of mx records, profile files, parquet rows):
  table rows per loader, precedence and `conflict`, id minting and merging, build determinism.
- On the real caches (laptop): build time (target under 45 min on the Actions runner), row counts against the source
  counts in §0, the 20-sample link checks read by hand.

## 6. Owner checkpoints

- After phase 1: the coverage report, read with him. It decides the order inside phases 2–5.
- Each later phase: its own short spec section and a look at its first pages before they go live.

## 7. Phase 2: awards and honours

**Owner's words (2026-11-19):** «أريد نسوي شي للجوائز الفردية من بالاندور وحذاء ذهبي … البطولات كلها نحط فيها افضل لاعب وافضل هداف».

**Success:** for every award in the catalogue, every year it was given is in the graph with its winner (and podium where the
award has one), each winner a player of the graph with an Arabic name; for every edition of every competition the graph
holds, the champion, runner-up and top scorer when any source has them, and the tournament's own awards (best player,
golden boot, best goalkeeper, best young player) where they exist. Every row cites its source; two sources that disagree
leave a `conflict`.

### 7.1 Model (no new tables)

- **An award is a competition** with `kind = 'award'` (`competition` row: name, name_ar, scope = world / continent / country,
  country). Each year it was given is an `edition` (season = the year or the season it was given for, as the award
  states it: «1956», «2023/2024»). Its result is `honour(kind = 'winner', rank = 1, 2, 3…)` with `pid` (or `tid` for a
  team award, `kid` for a coach award) and `value` (points, goals: what the source gives).
- **A tournament's or league's own awards** are honours on that competition's edition: `best_player`, `top_scorer`
  (`value` = goals; ranks 1..n), `top_assist`, `best_goalkeeper`, `best_young`, `fair_play` (`tid`), plus `runner_up` and
  `third` beside the existing `champion`.
- A winner not yet in the graph (a 1960s Ballon d'Or winner) becomes a `player` with source `wikidata` (its Wikidata item,
  English and Arabic labels, birth date), linked by the item: FotMob players already carry 12,989 Wikidata ids (phase 1).

### 7.2 The catalogue (`graph/awards.yaml`)

**Owner 2026-11-19: «كل الجوايز اللي نقدر نحصل عليها».** So the catalogue is discovered, not hand-written: every article
under English Wikipedia's football award categories (player, top scorer, goalkeeper, young player and manager of the year
awards, trophies and awards: 115 categories, about 1,400 articles measured 2026-11-19) and every competition article of
ours is read, and every table that pairs a year or season with a linked person (or a club, for champion / runner-up
tables) becomes an award or an edition honour (§7.3). `graph/awards.yaml` only overrides: the Arabic name of an award,
a table to skip, a wrong kind. The table below is the floor the discovered catalogue must cover:

| group | awards |
|---|---|
| world | Ballon d'Or (1956–, podium), FIFA World Player of the Year (1991–2009) / FIFA Ballon d'Or (2010–15) / The Best FIFA Men's Player (2016–), European Golden Shoe (1968–), Golden Boy (2003–), Kopa Trophy (2018–), Yashin Trophy (2019–), Gerd Müller Trophy (2021–), The Best FIFA Goalkeeper (2017–), FIFA Puskás Award (2009–) |
| continents | AFC Asian Player of the Year (1994–), African Footballer of the Year (CAF 1992–, France Football 1970–94), UEFA Men's Player of the Year (2011–) and Club Footballer (1998–2010), South American Footballer of the Year (1971–) |
| tournaments | World Cup (Golden Ball, Golden Boot, Golden Glove, Best Young Player, Fair Play: Fjelstul since 1930), EURO, Copa América, AFCON, Asian Cup, Gulf Cup, Arab Cup, Club World Cup, Champions League, AFC Champions League: best player and top scorer each |
| leagues | top scorer of every league season we can source (our own counts, the published scorers files, RSSSF, Wikipedia's per-league lists: Pichichi, Capocannoniere, Golden Boot, the UAE, Saudi and other Arab leagues' scorers); best player where the league names one (Premier League Player of the Season, LaLiga Best Player, Serie A MVP, Bundesliga Player of the Season, Ligue 1 UNFP, the UAE Pro League's and Saudi Pro League's awards where a list exists) |

### 7.3 Sources and precedence

1. **Wikipedia's list tables** (English, REST HTML, read with the page's links, so a winner is the article he links to,
   not a name; merged cells unfolded into a grid first). A person is a link whose Wikidata item is a human (P31 Q5); a red
   link keeps the name only. A linked person reaches our player through the item: the Wikidata ids phase 1 holds, then
   the item's Transfermarkt player id (P2446) through the Transfermarkt links; a club through its Transfermarkt club id
   (P7223) or db/clubs.py's cards; a competition article through db/champions.py's competition items. Measured 2026-11-19: Ballon d'Or 283 podium rows since 1956, Golden Shoe 63, Golden Boy 24, African
   Footballer 123, Pichichi 102, the UAE Pro League's top scorer by season 52. A linked article gives the Wikidata item
   through the page's `pageprops`. This is the primary list.
2. **Wikidata** P166 «award received» with P585 «point in time»: the second source, checked against the first (alone it
   is far short: Ballon d'Or 48 winners, Golden Shoe 25, Golden Boy 8).
3. **Fjelstul** `award_winners.csv` for the World Cup (every award since 1930).
4. **Our own counts** for top scorers of the editions with full events (FotMob since about 2016), then `v1/history/scorers/`
   (Transfermarkt since 2012 and FotMob's leader lists), then RSSSF's Arab scorers.
5. **Runner-up:** the final's loser for a knockout edition in our matches, rank 2 of a final table, and Wikidata's
   season winners statements with «runner-up» (P2501) that db/champions.py reads today and drops.

Precedence for a disagreement: Wikipedia > Fjelstul > Wikidata for awards; our own count > the published scorers files >
RSSSF > Wikipedia for top scorers (a count from full events is checkable, a list may be stale).

### 7.4 Fetching

A stage of its own, `awards` (weekly in db/refresh.py, before `graph`): the category crawl, each article's HTML (kept 30
days), the links' Wikidata items (P31, P569, ar/en labels, P2446, P7223) in batches of 50, at most one request a second,
all kept in `graph/.cache/awards/` and S3 `state/graph/awards/` (the last good copy is used when a fetch fails). The
loader `awards` reads only those files, as every loader does.

### 7.5 Checks

- **Completeness per award:** years held vs the years the catalogue says it was given; a missing year is a coverage line,
  not a failure.
- **Agreement:** each award year with two sources compares the winner (by Wikidata item); a disagreement is a `conflict`.
- **Sanity:** a winner born after the award year, or a podium with a repeated player, is dropped and reported.
- The coverage report gains an «awards» section: per award, years held / expected, sources agreeing, conflicts.

### 7.6 Publishing

`v1/awards/index.json` (every award: names, scope, years held) and `v1/awards/<key>.json` (every year: winner, podium,
values, player ids and Arabic names), and the pages ship with this phase (owner 2026-11-19 «الحين»): `/awards/` (every award, grouped:
world, continents, tournaments, leagues, countries), `/awards/<key>/` (every year with its podium, each winner linked to his
player page, most wins), and a «جوائزه» block on the player pages that have honours. In Tifo's v5 design, Arabic.

## 8. Phase 3: man of the match

**Owner 2026-11-19:** «اريد يكون مكان فرعي لرجل المباراة»; the design below approved («yes») the same night.

- **The pick:** FotMob's «Player of the Match» is the match's highest FotMob rating, so the graph takes, for every match with
  ratings, the player with the highest rating (ties: more goals + assists, then more minutes, then the lower Tifo id).
  Source `fotmob-rating`. A match without ratings has no pick (no guess).
- **Table:** `match_award(mid, kind, pid, tid, value, src)`, kind `motm`, value = the rating.
- **Counts per player:** total, per season, per competition, per opponent; the last ten picks.
- **Files:** `v1/motm/index.json` (leaders this season and all time, overall and per competition we cover; per club for the
  site's clubs) and `v1/motm/players.json` ({FotMob id: {total, seasons, comps, recent}}).
- **Pages:** `/motm/` (the leaders, this season first, per competition and club) and a «رجل المباراة» block on player pages;
  the match page's fans' vote stays as it is, beside the rating.
- **Timing:** nightly with the graph; phase 6 brings it to the final whistle.
