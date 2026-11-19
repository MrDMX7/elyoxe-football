# Tifo graph: one connected football database — spec

**Date:** 2026-11-19. Approach A approved by the owner the same day («نعم أوافق»), order: phase 1, then 2 and 3.

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
