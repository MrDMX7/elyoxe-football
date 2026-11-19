# Tifo graph — phase 2 (awards and honours) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every football award Wikipedia lists, plus each edition's champion, runner-up, top scorer and tournament awards, in `tifo.db` with Arabic-named, linked winners; published as `v1/awards/*` and shown on `/awards/` pages and on player pages.

**Architecture:** A weekly stage `awards` (`graph/awards_fetch.py`) crawls the football-award categories and our competition articles, keeps each article's HTML and the Wikidata facts of every linked item. A pure extractor (`graph/awards_wiki.py`) turns an article into award tables. The graph loader `awards` turns the tables into award competitions, editions and honours; `honours` derives top scorers and runners-up from our own data; `fjelstul` adds the World Cup's awards. The build publishes `v1/awards/`. The site gets `site/lib/awards.cjs` and three page families.

**Tech Stack:** Python 3.13, lxml (in requirements-db), sqlite3; Node (site build), `node --test`.

**Spec:** `docs/superpowers/specs/2026-11-19-tifo-graph-design.md` §7.

## Global Constraints

- Loaders read only caches: the network is touched by `awards_fetch` (and the existing `fetch.martj42`) only.
- Wikipedia and Wikidata: at most one request a second, User-Agent `elyoxe-tifo/0.1 (hello@elyoxe.com)`.
- A winner is a linked article whose Wikidata item is a human (P31 = Q5); never a name match, except a red link, which keeps its text as a name-only player.
- Precedence: Wikipedia > Fjelstul > Wikidata for awards; our count > published scorers files > RSSSF > Wikipedia for top scorers.
- Arabic UI copy, Western digits, the site's v5 tokens (`site/redesign/v5/DESIGN.md`); RTL lint must pass (`npm run lint:rtl` is the elyoxe.com site's, not this one: follow `site/DESIGN.md`).
- Commit only your own paths; `newline="\n"`.

## Review Focus

1. **Merged cells.** A year cell spanning three podium rows must give all three rows that year, with the columns not shifted. Pinned in Task 1 (`test_rowspan_year_covers_the_podium`).
2. **Non-award tables.** «Wins by player», «Wins by club», squad lists and career tables are not awards: no year column, or no person column, or fewer than 3 dated rows. Pinned in Task 1 (`test_summary_tables_are_skipped`).
3. **Same award on two pages.** «1960 Ballon d'Or» and «Ballon d'Or» describe one award; the per-year page's podium merges into the award's year, not a new award. Pinned in Task 3 (`test_year_page_merges_into_its_award`).
4. **A winner we already have.** A Wikipedia winner whose item is a FotMob player's (names qid or Transfermarkt id) must be that player, not a new one. Pinned in Task 3 (`test_winner_links_to_our_player_through_tm_id`).
5. **Fetch failure.** A failed fetch keeps last week's copy; an empty crawl must not wipe the awards. Pinned in Task 2 (`test_failed_page_keeps_the_last_copy`).

---

### Task 1: The table extractor (`graph/awards_wiki.py`)

**Files:** Create `graph/awards_wiki.py`; Test `tests/test_graph_awards_wiki.py`.

**Interfaces — Produces:**
- `grid(table) -> list[list[Cell]]` with merged cells unfolded; `Cell = (text: str, links: list[str])`, links are article titles (`Lionel_Messi`), red links as `"?<text>"`.
- `extract(html: bytes, page: str) -> list[dict]`: one dict per award table: `{"page", "section", "kind", "who": "person"|"team", "rows": [{"season", "rank", "person": title|None, "name", "team": title|None, "value"}]}`; `kind` from §7.1 by keywords (`top_scorer`, `best_goalkeeper`, `best_young`, `coach`, `champion_table`, `winner`).
- `season_label(text) -> str|None`: «1973–74» -> «1973/1974», «2009» -> «2009», «2023–24[16]» -> «2023/2024».

- [ ] **Step 1: Failing tests** (`tests/test_graph_awards_wiki.py`):

```python
from graph.awards_wiki import extract, season_label, grid
from lxml import html as LH

def T(body, head="Winners"):
    return f'<html><body><section><h2>{head}</h2><table class="wikitable">{body}</table></section></body></html>'.encode()

PODIUM = T('<tr><th>Year</th><th>Rank</th><th>Player</th><th>Team</th><th>Points</th></tr>'
           '<tr><td rowspan="3">1956</td><td>1st</td><td><a rel="mw:WikiLink" href="./Stanley_Matthews">Stanley Matthews</a></td><td><a rel="mw:WikiLink" href="./Blackpool_F.C.">Blackpool</a></td><td>47</td></tr>'
           '<tr><td>2nd</td><td><a rel="mw:WikiLink" href="./Alfredo_Di_Stéfano">Di Stéfano</a></td><td>Real Madrid</td><td>44</td></tr>'
           '<tr><td>3rd</td><td><a rel="mw:WikiLink" href="./Raymond_Kopa">Kopa</a></td><td>Real Madrid</td><td>33</td></tr>'
           '<tr><td>1957</td><td>1st</td><td><a rel="mw:WikiLink" href="./Alfredo_Di_Stéfano">Di Stéfano</a></td><td>Real Madrid</td><td>72</td></tr>')

def test_season_label():
    assert season_label("1973–74") == "1973/1974" and season_label("2023–24[16]") == "2023/2024"
    assert season_label("2009") == "2009" and season_label("1999–00") == "1999/2000" and season_label("Total") is None

def test_rowspan_year_covers_the_podium():
    t = extract(PODIUM, "Ballon d'Or")
    assert len(t) == 1 and t[0]["kind"] == "winner" and t[0]["who"] == "person"
    rows = t[0]["rows"]
    assert [(r["season"], r["rank"], r["person"], r["value"]) for r in rows[:3]] == [
        ("1956", 1, "Stanley_Matthews", "47"), ("1956", 2, "Alfredo_Di_Stéfano", "44"), ("1956", 3, "Raymond_Kopa", "33")]
    assert rows[0]["team"] == "Blackpool_F.C." and rows[3]["season"] == "1957"

def test_summary_tables_are_skipped():
    wins = T('<tr><th>Player</th><th>Wins</th></tr>' + ''.join(f'<tr><td><a rel="mw:WikiLink" href="./P{i}">P{i}</a></td><td>{i}</td></tr>' for i in range(5)), "Wins by player")
    assert extract(wins, "Ballon d'Or") == []

def test_kind_and_redlink_and_champion_table():
    sc = T('<tr><th>Season</th><th>Player</th><th>Club</th><th>Goals</th></tr>'
           '<tr><td>1973–74</td><td>Saeed Hareb</td><td><a rel="mw:WikiLink" href="./Al_Ahli">Al Ahli</a></td><td></td></tr>'
           '<tr><td>1974–75</td><td><a rel="mw:WikiLink" href="./Suhail_Salim?action=edit&amp;redlink=1">Suhail Salim</a></td><td>Al Ahli</td><td>14</td></tr>'
           '<tr><td>1975–76</td><td><a rel="mw:WikiLink" href="./Ahmed_X">Ahmed X</a></td><td>Al Ain</td><td>12</td></tr>', "Top scorers by season")
    t = extract(sc, "UAE Pro League")[0]
    assert t["kind"] == "top_scorer" and [r["person"] for r in t["rows"]] == [None, None, "Ahmed_X"]
    assert [r["name"] for r in t["rows"][:2]] == ["Saeed Hareb", "Suhail Salim"] and t["rows"][1]["value"] == "14"
    ch = T('<tr><th>Season</th><th>Champion</th><th>Runner up</th></tr>' + ''.join(
        f'<tr><td>197{i}–7{i + 1}</td><td><a rel="mw:WikiLink" href="./C{i}">C{i}</a></td><td><a rel="mw:WikiLink" href="./R{i}">R{i}</a></td></tr>' for i in range(3, 6)), "List of champions")
    c = extract(ch, "UAE Pro League")[0]
    assert c["kind"] == "champion_table" and c["who"] == "team"
    assert (c["rows"][0]["season"], c["rows"][0]["team"], c["rows"][0]["runner_up"]) == ("1973/1974", "C3", "R3")
```

- [ ] **Step 2:** `python -m pytest tests/test_graph_awards_wiki.py -q` → FAIL (module missing).
- [ ] **Step 3:** Implement. Grid: walk `tr`, keep a `pending` map of column → (cell, rows left) from `rowspan`, expand `colspan`. A table qualifies when its header row has a year/season/edition column and a person column (player, winner, scorer, name, recipient, goalkeeper, manager, coach, «best») or champion/winner + runner-up team columns, and at least 3 rows have a season. Rank from a rank/place column («1st» → 1) else 1 for every row. `kind` from the section heading + page title: `top_scorer` (scorer, golden boot, goalscorer, pichichi, capocannoniere, torjäger), `best_goalkeeper` (goalkeeper, golden glove, yashin), `best_young` (young, golden boy, kopa, rookie, revelation), `coach` (manager, coach), `champion_table` (team tables), else `winner`. Value: goals / points / votes column text.
- [ ] **Step 4:** tests pass. **Step 5:** commit `graph: Wikipedia award tables → rows (merged cells unfolded, summary tables skipped)`.

---

### Task 2: The weekly fetch (`graph/awards_fetch.py`, stage `awards`)

**Files:** Create `graph/awards_fetch.py`; Modify `db/refresh.py` (stage `("awards", "graph.awards_fetch", ["--upload"], 7)` before `graph`); Test `tests/test_graph_awards_fetch.py`.

**Interfaces — Produces:** `crawl(http) -> list[str]` (article titles under the award categories, depth 2), `run(S, http, out_dir, competitions: list[str]) -> dict` writing `out_dir/pages/<sha1(title)>.html.gz` (+ `pages.json` {title: {"fetched", "sha"}}), `out_dir/items.json` {title: {"qid", "human", "born", "ar", "en", "tm_player", "tm_club"}}; `http` is an object with `.get(url) -> bytes` (tests pass a fake). `main()` = `python -m graph.awards_fetch [--upload]`: S3 `state/graph/awards/` restore first, push after.

- [ ] **Step 1: Failing tests:**

```python
import json
from graph import awards_fetch as AF

class FakeHTTP:
    def __init__(self, pages, fail=()):
        self.pages, self.fail, self.calls = pages, set(fail), []
    def get(self, url):
        self.calls.append(url)
        for k, v in self.pages.items():
            if k in url and k not in self.fail:
                return v
        raise OSError("boom " + url)

def test_failed_page_keeps_the_last_copy(tmp_path):
    good = FakeHTTP({"Ballon_d'Or": b"<html>v1</html>"})
    AF.fetch_pages(good, str(tmp_path), ["Ballon d'Or"], max_age_days=0)
    bad = FakeHTTP({}, fail={"Ballon_d'Or"})
    got = AF.fetch_pages(bad, str(tmp_path), ["Ballon d'Or"], max_age_days=0)
    assert got["failed"] == 1 and AF.read_page(str(tmp_path), "Ballon d'Or") == b"<html>v1</html>"

def test_items_resolve_humans_and_tm_ids(tmp_path):
    pp = {"query": {"pages": [{"title": "Lionel Messi", "pageprops": {"wikibase_item": "Q615"}}], "normalized": [{"from": "Lionel_Messi", "to": "Lionel Messi"}]}}
    ent = {"entities": {"Q615": {"labels": {"ar": {"value": "ليونيل ميسي"}, "en": {"value": "Lionel Messi"}},
           "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}], "P569": [{"mainsnak": {"datavalue": {"value": {"time": "+1987-06-24T00:00:00Z"}}}}],
                      "P2446": [{"mainsnak": {"datavalue": {"value": "28003"}}}]}}}}
    http = FakeHTTP({"pageprops": json.dumps(pp).encode(), "wbgetentities": json.dumps(ent).encode()})
    items = AF.resolve(http, str(tmp_path), ["Lionel_Messi"])
    assert items["Lionel_Messi"] == {"qid": "Q615", "human": True, "born": "1987-06-24", "ar": "ليونيل ميسي", "en": "Lionel Messi", "tm_player": "28003", "tm_club": None}
```

- [ ] **Step 2:** FAIL. **Step 3:** implement `fetch_pages` (REST `page/html/<title>`, kept `max_age_days` 30, a failure keeps the old file), `resolve` (pageprops 50 titles a call with `redirects=1`, then `wbgetentities` 50 ids a call, props `labels|claims`, languages `ar|en`; results cached in `items.json`, only new titles asked), `crawl` (categorymembers of the six roots of spec §7.2, depth 2; namespace 0), a 1 s pacer, `main` with S3 restore/push via `Store.get_state/put_state` of a tar.gz (`state/graph/awards/cache.tar.gz`). The competitions' articles: from `v1/history/champions/<comp>.json` `qid` → the item's enwiki sitelink (one `wbgetentities` with `props=sitelinks`).
- [ ] **Step 4:** pass. **Step 5:** commit.

---

### Task 3: The loader (`graph/load/awards.py`)

**Files:** Create `graph/load/awards.py`, `graph/awards.yaml` (overrides: Arabic names of the floor awards in spec §7.2, skips); Modify `graph/build.py` ORDER (append `awards`, `fjelstul`, `honours`); Test `tests/test_graph_load_awards.py`.

**Interfaces — Consumes:** `extract`, the fetch dir (`graph/.cache/awards/` locally, restored from S3 by the stage), `Registry.link/mint`. **Produces:** award competitions (`kind='award'`, key `wiki|<page>|<section>`), editions (`edition_for`), `honour` rows; winners as players.

Rules (each with its test):
- Person → our player: `xref wikidata` qid first, then `tm_player` → `reg.get("player","tm",id)`, else a new player `("player","wikidata",qid)` with ar/en labels and birth date; a red link → `("player","wiki-name", "<page>|<name>")`, name only.
- Team → our team: `tm_club` → `("team","tm",id)`, then db/clubs.py cards (`clubs.json` qid → FotMob id), else `("team","wikidata",qid)`.
- A per-year page («1960 Ballon d'Or», «2022 FIFA World Cup awards») merges into the award whose page its title contains (the year stripped): `test_year_page_merges_into_its_award`.
- A table on a competition article (the article of one of our competitions) gives honours on that competition's editions (`kind` from the table: top_scorer, best_player…, `champion_table` → `champion` + `runner_up`), not an award of its own.
- Every other qualifying table → award competition; Arabic name from `awards.yaml`, else Wikidata's Arabic label of the page's item, else the English title.
- A row whose winner was born after the season's end year is dropped and counted (`sanity_dropped`).

- [ ] **Step 1: Failing tests** (fixtures: a tmp fetch dir with two pages' HTML from Task 1's helpers and an `items.json`):

```python
def test_winner_links_to_our_player_through_tm_id(tmp_path): ...   # items: Stanley_Matthews tm_player "1"; reg has ("player","tm","1") → that pid wins 1956
def test_new_winner_gets_a_wikidata_player_with_arabic_name(tmp_path): ...   # Di Stéfano not ours → player src wikidata, name_ar from items
def test_year_page_merges_into_its_award(tmp_path): ...   # pages «Ballon d'Or» and «1960 Ballon d'Or»: one award competition, edition 1960 from the year page
def test_competition_article_gives_edition_honours(tmp_path): ...   # «UAE Pro League» mapped to FotMob 538: top_scorer + champion/runner_up on 538's editions
def test_born_after_the_year_is_dropped(tmp_path): ...
```
(write each fully, in the style of tests/test_graph_load_s365.py: build tmp dirs, run `awards.load(G, reg, S)`, assert rows.)

- [ ] **Steps 2–5:** FAIL → implement → PASS → commit.

---

### Task 4: World Cup awards (Fjelstul) and derived honours

**Files:** Create `graph/load/fjelstul.py`, `graph/load/honours.py`; Modify `graph/fetch.py` (`fjelstul(S)`: `award_winners.csv`, `players.csv` weekly); Test `tests/test_graph_load_honours.py`.

- `fjelstul`: `WC-1930` → the World Cup edition «1930» under FotMob 77; award names → kinds (Golden Ball → `best_player` ranks 1-3 with Silver/Bronze Ball, Golden Boot → `top_scorer` 1-3, Golden Glove → `best_goalkeeper`, Best Young Player → `best_young`, FIFA Fair Play Trophy → `fair_play` team). Players by name+team within the edition's appearances when our matches have that World Cup, else a `("player","fjelstul",player_id)` player.
- `honours`:
  - `top_scorer` from our events for an edition where ≥ 90% of its finished matches have goal events (count goals minus own goals per player; ties share the rank), value = goals; else from `v1/history/scorers/<fotmob comp>.json` (published, through `S.published`), else RSSSF `history/arab/<code>.json` `scorers`.
  - `runner_up`: a knockout edition's final (round «final») loser in our matches (penalties decide); else rank 2 of the edition's standing.
- Tests: `test_top_scorer_from_events_counts_no_own_goals`, `test_runner_up_from_the_final_on_penalties`, `test_fjelstul_golden_ball_podium`.
- Steps: FAIL → implement → PASS → commit.

---

### Task 5: Publishing and the coverage section

**Files:** Create `graph/publish.py`; Modify `graph/build.py` (after the graph is built: `publish.awards(G, out_dir)`; `publish()` uploads `v1/awards/index.json` and `v1/awards/<key>.json` with `cache="static"`), `graph/coverage.py` (awards section). Test `tests/test_graph_publish.py`.

- `index.json`: `{"generated", "awards": [{"key", "name", "name_ar", "group": world|continent|tournament|league|country, "years": n, "first", "last", "top": [pid, name_ar|name, wins]}]}`; group from scope/country/kind.
- `<key>.json`: `{"key", "name", "name_ar", "years": [{"season", "podium": [{"rank", "pid", "fotmob", "name", "name_ar", "team", "value"}]}], "most": [[pid, name, wins]], "sources": [...]}`; `fotmob` = the FotMob id when the player has one (pages link /p/<id>/).
- `players.json`: `{fotmob id: [[award key, season, rank]]}` for the player block.
- key = a slug of the English name (`ballon-dor`), unique.
- Tests: index/award shape on a small graph; a FotMob-linked winner carries `fotmob`.

---

### Task 6: The pages (`site/lib/awards.cjs`)

**Files:** Create `site/lib/awards.cjs`, `site/lib/awards.test.cjs`; Modify `site/build.cjs` (read `awards/index.json`, each award file, `awards/players.json`; write `/awards/`, `/awards/<key>/`; add «الجوائز» to the footer nav and `/more/`; the «جوائزه» block on `/p/<id>/`), sitemap urls.

- `/awards/`: groups (world, continents, tournaments, leagues, countries), each award a v5 row: Arabic name, years «منذ 1956», the latest winner.
- `/awards/<key>/`: h1 the award, a v5 table of every year (newest first): season, winner (linked to /p/<fotmob>/ when the player has a site page, else plain text with the Latin name in `.lat`), team, value; podium 2nd/3rd smaller; «الأكثر فوزاً» list; sources line («من ويكيبيديا وويكي داتا»).
- Player block: «جوائزه وتكريماته» list: award, season, rank («الثاني»), linked to the award page.
- JSON-LD: breadcrumb only.
- `node --test site/lib/awards.test.cjs`: renders a podium with a linked and an unlinked winner; Arabic ordinal for rank 2; RTL-safe digits in `.num`.

---

### Task 7: Real run and ship

- [ ] Dispatch «Tifo graph dry run» after a manual `awards` fetch run (`gh workflow run tifo-database.yml -f force=awards,graph` publishes; first do the fetch alone with a dry run by adding `--only awards,fjelstul,honours` to check).
- [ ] Read the awards coverage: Ballon d'Or 69 years (1956–2025, no 2020) with podium, Golden Shoe since 1968, World Cup awards 1930–2022, UAE league top scorer 1973/74–, champions and runners-up of the UAE league every season.
- [ ] Sample 30 winners by hand against their Wikipedia pages.
- [ ] Site: build once in a worktree with `FOOTBALL_OUT` (never `site/out` on the laptop: the hourly job), screenshot `/awards/`, `/awards/ballon-dor/`, a player page; send to the owner.
- [ ] Commit, push, memory.
