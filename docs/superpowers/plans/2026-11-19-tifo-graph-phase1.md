# Tifo graph — phase 1 (core) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `tifo.db`, one SQLite database holding every football fact the Tifo caches already hold, under stable Tifo ids, with every source's id crosswalked and every disagreement recorded, plus a coverage report.

**Architecture:** A new package `graph/` in `saas/football`. A registry mints Tifo ids per `(type, source, source id)` and is the only state kept between builds. One loader per source reads the existing caches (`db/.cache`, `history/.cache`, `names/`) or our own published files, and writes rows through `Graph.put`, which applies the source precedence and logs conflicts. `graph.build` runs the loaders in precedence order, checks id stability, writes the coverage report and publishes. It runs as a new `db.refresh` stage on GitHub Actions.

**Tech Stack:** Python 3.13, stdlib `sqlite3` (3.50), DuckDB (already in `requirements-db.txt`) for the parquet, pytest, boto3 through the repo's `store.py`.

**Spec:** `docs/superpowers/specs/2026-11-19-tifo-graph-design.md`

## Global Constraints

- Loaders never touch the network. The only fetch is `graph/fetch.py` (martj42 CSV), run by the build before the loaders.
- Every row carries `src`. The precedence order is `fotmob > s365 > tm > fjelstul/rsssf > sch > martj42 > wikidata` (§3.1). Phase 1 adds `names` at FotMob's rank.
- Linking is never by name alone (§3.3). Every `xref` row has a `method`.
- Tifo ids are never reused. A merge keeps the lower id, and the higher one resolves to it.
- Nothing the site reads changes, except the new `v1/graph/coverage.json`.
- Writes use `newline="\n"` (Windows CRLF trap) and file paths use forward slashes.
- This repo has other sessions' uncommitted work on `main`. Commit only your own paths (`git commit -- <paths>`).
- Tests: `python -m pytest tests/test_graph_*.py -q`, run from `saas/football`.

## Review Focus

1. **A rebuild must not renumber.** Building twice from the same caches gives byte-identical registries, and adding a source keeps every old id. Pinned in Task 1 (`test_registry_roundtrip_identical`) and Task 11 (`test_build_twice_same_ids`).
2. **Two sources, one match.** A Transfermarkt or schochastics game already in FotMob must become one `mid` with two `xref` rows, never two matches. The date may sit one day off (time zones), and home and away may be swapped at a neutral venue. Pinned in Task 6 (`test_find_one_day_off_and_swapped`).
3. **Different score, same game.** It is kept once, with FotMob's score, and a `conflict` row is written. Pinned in Task 6 (`test_twin_with_other_score_logs_conflict`).
4. **A missing cache must not kill the build.** The build skips that loader and the report says so. Only a failed FotMob loader fails the stage. Pinned in Task 11 (`test_missing_cache_skips_loader`).
5. **An unused substitute is not an appearance with minutes.** They get a row with `played = 0`, so a player's appearance count never counts the bench. Pinned in Task 3 (`test_unused_sub_not_played`).

---

## File Structure

| file | responsibility |
|---|---|
| `graph/__init__.py` | package marker, `ROOT` |
| `graph/schema.sql` | every table of spec §3.1 (plus `player_season`, `meta`) |
| `graph/ids.py` | `Registry`: mint, alias, merge, resolve, save/load, stability check |
| `graph/db.py` | `Graph`: open fresh db, `put` with precedence + conflicts, `many`, `xref`, `conflict` |
| `graph/src.py` | `Sources`: cache paths, gz/plain JSON reader, published files (local mirror, else S3) |
| `graph/fm.py` | FotMob helpers: season label per match (offline), competition info, iso dates |
| `graph/rows.py` | `match_rows(rec, eid, reg)`: one FotMob compact match → rows (phase 6 reuses it) |
| `graph/link.py` | `MatchIndex` (find a match's twin) and `vote_alias` (link competitions/editions by their matches) |
| `graph/load/*.py` | one loader per source: `fotmob_matches`, `fotmob_profiles`, `names`, `schochastics`, `s365`, `rsssf`, `tm`, `martj42`, `transfers` |
| `graph/fetch.py` | the one network step (martj42 results CSV, weekly) |
| `graph/coverage.py` | coverage numbers → `docs/GRAPH-COVERAGE-<date>.md` and `coverage.json` |
| `graph/build.py` | orchestration, stability check, publish |
| `graph/q.py` | read-only query helper |
| `tests/test_graph_*.py` | tests, building tiny caches in `tmp_path` |
| `db/refresh.py` | new stage `graph` before `audit` |
| `.github/workflows/tifo-database.yml` | `graph/.cache` in the cached paths |

---

### Task 1: Core — schema, registry, Graph, query helper

**Files:**
- Create: `graph/__init__.py`, `graph/schema.sql`, `graph/ids.py`, `graph/db.py`, `graph/q.py`
- Test: `tests/test_graph_core.py`

**Interfaces:**
- Produces: `Registry(data=None)` with `.mint(t, src, sid) -> int`, `.get(t, src, sid) -> int|None`, `.alias(t, src, sid, tifo_id) -> bool`, `.merge(t, a, b) -> int`, `.resolve(t, i) -> int`, `.save(path)`, `Registry.load(path)`, `.moved(old: Registry) -> list[str]`; `Graph(path)` with `.put(table, row: dict, src) -> bool` (True = inserted), `.many(table, rows: list[dict], src)`, `.xref(t, tifo_id, source, source_id, method, conf=1.0)`, `.conflict(t, tifo_id, field, kept, kept_src, other, other_src)`, `.meta(k, v)`, `.close()`, attribute `.c` (sqlite3 connection); `KEYS` dict type→key column; `q.query(sql, params=(), path=None) -> list[tuple]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_graph_core.py
import gzip, json, sqlite3
from graph.ids import Registry
from graph.db import Graph


def test_mint_is_stable_and_per_type():
    r = Registry()
    assert r.mint("team", "fotmob", 8456) == 1
    assert r.mint("team", "fotmob", 9825) == 2
    assert r.mint("player", "fotmob", 8456) == 1
    assert r.mint("team", "fotmob", 8456) == 1


def test_alias_and_refusal():
    r = Registry()
    t = r.mint("team", "fotmob", 1)
    assert r.alias("team", "sch", "Al Ain (UAE)", t) is True
    assert r.get("team", "sch", "Al Ain (UAE)") == t
    u = r.mint("team", "fotmob", 2)
    assert r.alias("team", "sch", "Al Ain (UAE)", u) is False      # already names another entity: never silently merged
    assert r.get("team", "sch", "Al Ain (UAE)") == t


def test_merge_keeps_lower_and_old_ids_resolve():
    r = Registry()
    a, b = r.mint("player", "fotmob", 10), r.mint("player", "tm", "99")
    assert r.merge("player", b, a) == a
    assert r.get("player", "tm", "99") == a
    assert r.resolve("player", b) == a


def test_registry_roundtrip_identical(tmp_path):
    r = Registry()
    for i in (5, 3, 9):
        r.mint("team", "fotmob", i)
    p1, p2 = tmp_path / "a.json.gz", tmp_path / "b.json.gz"
    r.save(p1)
    Registry.load(p1).save(p2)
    assert p1.read_bytes() == p2.read_bytes()


def test_moved_reports_renumbering():
    old = Registry(); old.mint("team", "fotmob", 1); old.mint("team", "fotmob", 2)
    new = Registry(json.loads(json.dumps(old.to_json())))
    assert new.moved(old) == []
    new.map["team|fotmob|2"] = 7
    assert new.moved(old) == ["team|fotmob|2"]


def test_put_precedence_fill_and_conflict(tmp_path):
    g = Graph(str(tmp_path / "t.db"))
    assert g.put("match", {"mid": 1, "hs": 2, "as_": 1, "attendance": None}, "fotmob") is True
    assert g.put("match", {"mid": 1, "hs": 2, "as_": 0, "attendance": 9000}, "sch") is False
    row = g.c.execute("select hs, as_, attendance, src, filled from match where mid=1").fetchone()
    assert row[:4] == (2, 1, 9000, "fotmob")
    assert json.loads(row[4]) == {"attendance": "sch"}
    assert g.c.execute("select field, kept, kept_src, other, other_src from conflict").fetchall() == [("as_", "1", "fotmob", "0", "sch")]


def test_many_ignores_duplicates(tmp_path):
    g = Graph(str(tmp_path / "t.db"))
    rows = [{"mid": 1, "pid": 2, "tid": 3, "played": 1}, {"mid": 1, "pid": 2, "tid": 3, "played": 1}]
    g.many("appearance", rows, "fotmob")
    assert g.c.execute("select count(*) from appearance").fetchone()[0] == 1
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_graph_core.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'graph'`

- [ ] **Step 3: Write the implementation**

`graph/__init__.py`:
```python
"""Tifo graph: one connected football database (docs/superpowers/specs/2026-11-19-tifo-graph-design.md)."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

`graph/schema.sql`:
```sql
CREATE TABLE team(tid INTEGER PRIMARY KEY, name TEXT, name_ar TEXT, kind TEXT, country TEXT, founded INTEGER, sid INTEGER, src TEXT NOT NULL, filled TEXT);
CREATE TABLE player(pid INTEGER PRIMARY KEY, name TEXT, name_ar TEXT, name_native TEXT, born TEXT, died TEXT, birthplace TEXT, nationality TEXT, nationality2 TEXT, position TEXT, height INTEGER, foot TEXT, src TEXT NOT NULL, filled TEXT);
CREATE TABLE coach(kid INTEGER PRIMARY KEY, name TEXT, name_ar TEXT, born TEXT, nationality TEXT, pid INTEGER, src TEXT NOT NULL, filled TEXT);
CREATE TABLE referee(rid INTEGER PRIMARY KEY, name TEXT, name_ar TEXT, country TEXT, src TEXT NOT NULL, filled TEXT);
CREATE TABLE stadium(sid INTEGER PRIMARY KEY, name TEXT, name_ar TEXT, city TEXT, country TEXT, lat REAL, lon REAL, capacity INTEGER, src TEXT NOT NULL, filled TEXT);
CREATE TABLE competition(cid INTEGER PRIMARY KEY, name TEXT, name_ar TEXT, kind TEXT, scope TEXT, country TEXT, tier INTEGER, src TEXT NOT NULL, filled TEXT);
CREATE TABLE edition(eid INTEGER PRIMARY KEY, cid INTEGER NOT NULL, season TEXT NOT NULL, start TEXT, end TEXT, src TEXT NOT NULL, filled TEXT);
CREATE INDEX edition_cid ON edition(cid, season);
CREATE TABLE match(mid INTEGER PRIMARY KEY, eid INTEGER, round TEXT, date TEXT, home INTEGER, away INTEGER, hs INTEGER, as_ INTEGER,
  ht_h INTEGER, ht_a INTEGER, et INTEGER, pen_h INTEGER, pen_a INTEGER, status TEXT, sid INTEGER, rid INTEGER, attendance INTEGER, src TEXT NOT NULL, filled TEXT);
CREATE INDEX match_date ON match(date);
CREATE INDEX match_home ON match(home, date);
CREATE INDEX match_away ON match(away, date);
CREATE INDEX match_eid ON match(eid);
CREATE TABLE appearance(mid INTEGER, pid INTEGER, tid INTEGER, played INTEGER, started INTEGER, minutes INTEGER, position INTEGER, shirt TEXT,
  captain INTEGER, rating REAL, goals INTEGER, assists INTEGER, yellow INTEGER, red INTEGER, stats TEXT, src TEXT NOT NULL, PRIMARY KEY(mid, pid));
CREATE INDEX appearance_pid ON appearance(pid);
CREATE TABLE event(mid INTEGER, seq INTEGER, minute INTEGER, added INTEGER, type TEXT, side TEXT, tid INTEGER, pid INTEGER, pid2 INTEGER,
  detail TEXT, src TEXT NOT NULL, PRIMARY KEY(mid, seq));
CREATE INDEX event_pid ON event(pid);
CREATE TABLE match_coach(mid INTEGER, side TEXT, kid INTEGER, src TEXT NOT NULL, PRIMARY KEY(mid, side));
CREATE TABLE standing(eid INTEGER, grp TEXT, rank INTEGER, tid INTEGER, played INTEGER, won INTEGER, drawn INTEGER, lost INTEGER,
  gf INTEGER, ga INTEGER, pts REAL, src TEXT NOT NULL, PRIMARY KEY(eid, grp, rank));
CREATE TABLE honour(eid INTEGER, kind TEXT, rank INTEGER, tid INTEGER, pid INTEGER, kid INTEGER, value TEXT, src TEXT NOT NULL, PRIMARY KEY(eid, kind, rank));
CREATE TABLE transfer(pid INTEGER, from_tid INTEGER, to_tid INTEGER, date TEXT, season TEXT, fee INTEGER, type TEXT, src TEXT NOT NULL, PRIMARY KEY(pid, date, to_tid));
CREATE TABLE spell(pid INTEGER, tid INTEGER, start TEXT, end TEXT, apps INTEGER, goals INTEGER, assists INTEGER, loan INTEGER, national INTEGER, youth INTEGER,
  src TEXT NOT NULL, PRIMARY KEY(pid, tid, start, src));
CREATE TABLE player_season(pid INTEGER, season TEXT, comp TEXT, cid INTEGER, tid INTEGER, apps INTEGER, minutes INTEGER, goals INTEGER, assists INTEGER,
  yellow INTEGER, red INTEGER, clean_sheets INTEGER, conceded INTEGER, src TEXT NOT NULL);
CREATE INDEX player_season_pid ON player_season(pid);
CREATE TABLE injury(pid INTEGER, season TEXT, kind TEXT, start TEXT, end TEXT, days INTEGER, games INTEGER, src TEXT NOT NULL);
CREATE TABLE xref(type TEXT, tifo_id INTEGER, source TEXT, source_id TEXT, method TEXT, confidence REAL, PRIMARY KEY(type, source, source_id));
CREATE INDEX xref_tifo ON xref(type, tifo_id);
CREATE TABLE conflict(type TEXT, tifo_id INTEGER, field TEXT, kept TEXT, kept_src TEXT, other TEXT, other_src TEXT);
CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
```

`graph/ids.py`:
```python
"""Tifo ids (spec §3.2): one integer sequence per entity type, never reused. The registry maps (type, source, source id)
to the id and keeps merges, so an id once published always leads to its entity."""
import gzip, json, os

TYPES = ("team", "player", "coach", "referee", "stadium", "competition", "edition", "match")


class Registry:
    def __init__(self, data=None):
        d = data or {}
        self.next = dict(d.get("next") or {})
        self.map = dict(d.get("map") or {})
        self.merged = dict(d.get("merged") or {})

    @staticmethod
    def key(t, src, sid):
        return f"{t}|{src}|{sid}"

    def resolve(self, t, i):
        for _ in range(64):
            j = self.merged.get(f"{t}|{i}")
            if j is None:
                return i
            i = j
        raise ValueError(f"merge cycle at {t} {i}")

    def get(self, t, src, sid):
        i = self.map.get(self.key(t, src, sid))
        return None if i is None else self.resolve(t, i)

    def mint(self, t, src, sid):
        if t not in TYPES:
            raise ValueError(f"unknown type {t}")
        i = self.get(t, src, sid)
        if i is not None:
            return i
        i = self.next.get(t, 0) + 1
        self.next[t] = i
        self.map[self.key(t, src, sid)] = i
        return i

    def alias(self, t, src, sid, tifo_id):
        """(src, sid) names entity tifo_id. False when it already names another one: a link is never turned into a merge."""
        cur = self.get(t, src, sid)
        if cur is None:
            self.map[self.key(t, src, sid)] = tifo_id
            return True
        return cur == self.resolve(t, tifo_id)

    def merge(self, t, a, b):
        a, b = self.resolve(t, a), self.resolve(t, b)
        if a == b:
            return a
        keep, drop = min(a, b), max(a, b)
        self.merged[f"{t}|{drop}"] = keep
        return keep

    def to_json(self):
        return {"next": dict(sorted(self.next.items())), "map": dict(sorted(self.map.items())), "merged": dict(sorted(self.merged.items()))}

    def save(self, path):
        body = json.dumps(self.to_json(), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        tmp = f"{path}.tmp"
        with open(tmp, "wb") as f, gzip.GzipFile(fileobj=f, mode="wb", mtime=0, compresslevel=6) as z:
            z.write(body)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path):
        if not os.path.exists(path):
            return cls()
        with gzip.open(path, "rb") as f:
            return cls(json.loads(f.read()))

    def moved(self, old):
        """Keys of the old registry whose entity changed: the old id no longer leads where the key now points."""
        out = []
        for k, i in old.map.items():
            t = k.split("|", 1)[0]
            if self.map.get(k) is None or self.resolve(t, self.map[k]) != self.resolve(t, old.resolve(t, i)):
                out.append(k)
        return sorted(out)
```

`graph/db.py`:
```python
"""The graph database (spec §3.1): a fresh SQLite file each build. put() applies the source precedence: the first
source to state a field keeps it, a later one fills only empty fields, and a disagreement on a checked field is logged."""
import json, os, sqlite3
from collections import Counter

SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
SRC_RANK = {"fotmob": 0, "names": 0, "s365": 1, "tm": 2, "fjelstul": 3, "rsssf": 3, "sch": 4, "martj42": 5, "wikidata": 6}
KEYS = {"team": "tid", "player": "pid", "coach": "kid", "referee": "rid", "stadium": "sid", "competition": "cid", "edition": "eid", "match": "mid"}
CHECK = {"match": ("hs", "as_"), "player": ("born",), "team": (), "edition": ("cid", "season")}


def same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 1e-6
    return str(a).strip().casefold() == str(b).strip().casefold()


class Graph:
    def __init__(self, path):
        if os.path.exists(path):
            os.remove(path)
        self.path = path
        self.c = sqlite3.connect(path)
        self.c.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA temp_store=MEMORY; PRAGMA cache_size=-200000;")
        self.c.executescript(open(SCHEMA, encoding="utf-8").read())
        self.cols = {t: [r[1] for r in self.c.execute(f"PRAGMA table_info({t})")]
                     for (t,) in self.c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        self.stats = Counter()

    def put(self, table, row, src):
        k = KEYS[table]
        i = row[k]
        cur = self.c.execute(f"SELECT * FROM {table} WHERE {k}=?", (i,)).fetchone()
        if cur is None:
            cols = [c for c in row if c in self.cols[table] and c not in ("src", "filled")]
            self.c.execute(f"INSERT INTO {table}({','.join(cols + ['src'])}) VALUES({','.join('?' * (len(cols) + 1))})", [row[c] for c in cols] + [src])
            self.stats[f"{table}:{src}"] += 1
            return True
        cur = dict(zip(self.cols[table], cur))
        filled = json.loads(cur.get("filled") or "{}")
        new_wins = SRC_RANK.get(src, 9) < SRC_RANK.get(cur["src"], 9)
        upd = {}
        for c, v in row.items():
            if c == k or c not in self.cols[table] or c in ("src", "filled") or v is None or v == "":
                continue
            old = cur.get(c)
            if old is None or old == "":
                upd[c] = v
                filled[c] = src
            elif not same(old, v):
                old_src = filled.get(c, cur["src"])
                if c in CHECK.get(table, ()):
                    if new_wins:
                        self.conflict(table, i, c, v, src, old, old_src)
                    else:
                        self.conflict(table, i, c, old, old_src, v, src)
                if new_wins:
                    upd[c] = v
                    filled[c] = src
        if upd:
            upd["filled"] = json.dumps(filled, sort_keys=True)
            self.c.execute(f"UPDATE {table} SET {','.join(f'{c}=?' for c in upd)} WHERE {k}=?", list(upd.values()) + [i])
        return False

    def many(self, table, rows, src):
        if not rows:
            return
        cols = [c for c in self.cols[table] if c != "src"]
        self.c.executemany(f"INSERT OR IGNORE INTO {table}({','.join(cols + ['src'])}) VALUES({','.join('?' * (len(cols) + 1))})",
                           [[r.get(c) for c in cols] + [src] for r in rows])
        self.stats[f"{table}:{src}"] += len(rows)

    def xref(self, t, tifo_id, source, source_id, method, conf=1.0):
        self.c.execute("INSERT OR REPLACE INTO xref VALUES(?,?,?,?,?,?)", (t, tifo_id, source, str(source_id), method, conf))

    def conflict(self, t, tifo_id, field, kept, kept_src, other, other_src):
        self.c.execute("INSERT INTO conflict VALUES(?,?,?,?,?,?,?)", (t, tifo_id, field, str(kept), kept_src, str(other), other_src))

    def meta(self, k, v):
        self.c.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, json.dumps(v, ensure_ascii=False)))

    def close(self):
        self.c.commit()
        self.c.close()
```

`graph/q.py`:
```python
"""Read-only questions to tifo.db: python -m graph.q "select count(*) from match" """
import os, sqlite3, sys

DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "tifo.db")


def query(sql, params=(), path=None):
    c = sqlite3.connect(f"file:{(path or DEFAULT).replace(os.sep, '/')}?mode=ro", uri=True)
    try:
        return c.execute(sql, params).fetchall()
    finally:
        c.close()


if __name__ == "__main__":
    for row in query(sys.argv[1]):
        print("\t".join("" if v is None else str(v) for v in row))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_graph_core.py -q`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add graph/__init__.py graph/schema.sql graph/ids.py graph/db.py graph/q.py tests/test_graph_core.py
git commit -m "graph: core — schema, Tifo id registry, precedence-aware Graph, query helper" -- graph/__init__.py graph/schema.sql graph/ids.py graph/db.py graph/q.py tests/test_graph_core.py
```

---

### Task 2: Sources and FotMob helpers

**Files:**
- Create: `graph/src.py`, `graph/fm.py`
- Test: `tests/test_graph_src.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `Sources(root, mirror=None, s3=True)` with `.db` (path of `db/.cache`), `.hist` (`history/.cache`), `.names` (`names/`), `.read(path) -> obj|None` (gz or plain), `.published(key) -> obj|None`; `fm.iso(s) -> str|None` (`'2026-08-20T22:00:00Z'`), `fm.season_map(S) -> (dict[int, str], set[int])`, `fm.comp_info(S) -> dict[int, dict]` (keys `name, name_ar, kind, scope, country`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_graph_src.py
import gzip, json, os
from graph.src import Sources
from graph import fm


def mk(tmp_path):
    db = tmp_path / "db" / ".cache"
    (db / "fm" / "seasons" / "538").mkdir(parents=True)
    (db / "fm" / "seasons" / "538" / "_seasons.json").write_text(json.dumps(["2025/2026", "2024/2025"]))
    (db / "fm" / "seasons" / "538" / "2024-2025.json").write_text(json.dumps([111, 112]))
    (db / "fm" / "seasons" / "77").mkdir(parents=True)
    (db / "fm" / "seasons" / "77" / "_seasons.json").write_text(json.dumps(["2026", "2022"]))
    (db / "fm" / "seasons" / "77" / "2022.json").write_text(json.dumps([222]))
    (db / "fm_allleagues.json").write_text(json.dumps({"popular": [], "international": [{"ccode": "INT", "name": "International", "leagues": [{"id": 77, "name": "World Cup"}]}],
                                                       "countries": [{"ccode": "ARE", "name": "United Arab Emirates", "leagues": [{"id": 538, "name": "Pro League"}]}]}))
    (db / "fm_ar.json").write_text(json.dumps({"LeagueMapping": {"77": "76"}, "TournamentTemplates": {"76": "كأس العالم"}, "Participants": {}}))
    return Sources(str(tmp_path), mirror=str(tmp_path / "mirror"), s3=False)


def test_read_gz_and_plain(tmp_path):
    S = mk(tmp_path)
    p = tmp_path / "x.json.gz"
    p.write_bytes(gzip.compress(b'{"a": 1}'))
    q = tmp_path / "y.json"
    q.write_text('{"b": 2}')
    assert S.read(str(p)) == {"a": 1} and S.read(str(q)) == {"b": 2} and S.read(str(tmp_path / "none.json")) is None


def test_season_map_and_calendar(tmp_path):
    labels, calendar = fm.season_map(mk(tmp_path))
    assert labels[111] == "2024/2025" and labels[222] == "2022"
    assert 77 in calendar and 538 not in calendar


def test_comp_info_names(tmp_path):
    info = fm.comp_info(mk(tmp_path))
    assert info[77]["name"] == "World Cup" and info[77]["name_ar"] == "كأس العالم" and info[77]["country"] == "INT"
    assert info[538]["country"] == "ARE" and info[538]["name_ar"] == "دوري أدنوك للمحترفين"   # competitions.yaml wins


def test_iso():
    assert fm.iso("2026-08-20T22:00:00.000Z") == "2026-08-20T22:00:00Z"
    assert fm.iso("2010-06-26") == "2010-06-26" and fm.iso(None) is None


def test_published_reads_mirror(tmp_path):
    S = mk(tmp_path)
    m = tmp_path / "mirror" / "s365"
    m.mkdir(parents=True)
    (m / "index.json").write_text('{"teams": []}')
    assert S.published("s365/index.json") == {"teams": []}
    assert S.published("s365/none.json") is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_graph_src.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'graph.src'`

- [ ] **Step 3: Write the implementation**

`graph/src.py`:
```python
"""Where the loaders read: the stages' caches (db/.cache, history/.cache, names/) and our own published files (v1/...),
read from a local mirror (graph/.cache/v1/) refreshed from S3 once a build. Loaders never reach other sites."""
import gzip, json, os, time
from graph import ROOT


class Sources:
    def __init__(self, root=ROOT, mirror=None, s3=True):
        self.root = root
        self.db = os.path.join(root, "db", ".cache")
        self.hist = os.path.join(root, "history", ".cache")
        self.names = os.path.join(root, "names")
        self.mirror = mirror or os.path.join(root, "graph", ".cache", "v1")
        self.s3 = s3
        self._store = None

    @staticmethod
    def read(path):
        try:
            raw = open(path, "rb").read()
        except OSError:
            return None
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        try:
            return json.loads(raw)
        except ValueError:
            return None

    def store(self):
        if self._store is None:
            import sys
            sys.path.insert(0, self.root)
            from store import Store, S3Backend
            self._store = Store(S3Backend(os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")))
        return self._store

    def published(self, key, max_age_h=20):
        """v1/<key>: the mirror when fresh, else S3 (saved to the mirror), else a stale mirror copy, else None."""
        p = os.path.join(self.mirror, key)
        if os.path.exists(p) and (not self.s3 or time.time() - os.path.getmtime(p) < max_age_h * 3600):
            return self.read(p)
        if self.s3:
            try:
                d = self.store().get_json(key)
            except Exception as e:
                print(f"published {key}: {type(e).__name__} {str(e)[:120]}", flush=True)
                d = None
            if d is not None:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8", newline="\n") as f:
                    json.dump(d, f, ensure_ascii=False)
                return d
        return self.read(p) if os.path.exists(p) else None
```

`graph/fm.py`:
```python
"""FotMob helpers for the graph, offline: the season label of each match (db/matches.py's own cache of FotMob's season
pages), the competitions' names, and ISO dates."""
import os, re
from graph.src import Sources

STEM = lambda lab: re.sub(r"[^0-9A-Za-z]+", "-", str(lab))


def _label(s):
    m = re.match(r"^\s*(\d{4}(?:/\d{4})?)", str(s or ""))
    return m.group(1) if m else (str(s) if s else None)


def iso(s):
    if not s:
        return None
    s = str(s)
    return s[:19] + "Z" if len(s) >= 19 and "T" in s else s[:10]


def season_map(S: Sources):
    """({match id: season label}, {calendar-year competitions}) from db/.cache/fm/seasons/<comp>/."""
    base = os.path.join(S.db, "fm", "seasons")
    out, calendar = {}, set()
    for cdir in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if not cdir.isdigit():
            continue
        labels = S.read(os.path.join(base, cdir, "_seasons.json")) or []
        if labels and sum(1 for x in labels if "/" not in str(x)) * 2 >= len(labels):
            calendar.add(int(cdir))
        by_stem = {STEM(lab): _label(lab) for lab in labels}
        for f in sorted(os.listdir(os.path.join(base, cdir))):
            stem = f[:-5]
            if f == "_seasons.json" or not f.endswith(".json"):
                continue
            lab = by_stem.get(stem) or (stem.replace("-", "/") if re.fullmatch(r"\d{4}-\d{4}", stem) else stem)
            for i in S.read(os.path.join(base, cdir, f)) or []:
                out.setdefault(int(i), lab)
    return out, calendar


def season_of(mid, date, comp, labels, calendar):
    """FotMob's label when we hold it, else the calendar year or the July-June season (db/matches.py's rule)."""
    lab = labels.get(mid)
    if lab:
        return lab
    y, mo = int(date[:4]), int(date[5:7])
    if comp in calendar:
        return str(y)
    return f"{y}/{y + 1}" if mo >= 7 else f"{y - 1}/{y}"


def comp_info(S: Sources):
    """{FotMob competition id: {name, name_ar, kind, scope, country}}: FotMob's league list, its Arabic map, and
    competitions.yaml (house names, kind, scope) over both."""
    out = {}
    al = S.read(os.path.join(S.db, "fm_allleagues.json")) or {}
    for grp in (al.get("international") or []) + (al.get("countries") or []):
        for lg in grp.get("leagues") or []:
            out[int(lg["id"])] = {"name": lg.get("name"), "name_ar": None, "kind": None, "scope": None, "country": grp.get("ccode")}
    ar = S.read(os.path.join(S.db, "fm_ar.json")) or {}
    lm, tt = ar.get("LeagueMapping") or {}, ar.get("TournamentTemplates") or {}
    for cid, d in out.items():
        d["name_ar"] = tt.get(str(lm.get(str(cid), cid)))
    try:
        import config
        for c in config.competitions():
            d = out.setdefault(int(c["id"]), {"name": c.get("name"), "name_ar": None, "kind": None, "scope": None, "country": None})
            d.update({k: v for k, v in (("name_ar", c.get("name_ar")), ("kind", c.get("kind")), ("scope", c.get("scope"))) if v})
    except Exception as e:
        print(f"competitions.yaml not read: {e}", flush=True)
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_graph_src.py -q`
Expected: 5 passed. `test_comp_info_names` reads the real `competitions.yaml` through `config`; 538's `name_ar` there is «دوري أدنوك للمحترفين». If the yaml name differs, assert against `config.competition(538)["name_ar"]` instead.

- [ ] **Step 5: Commit**

```bash
git commit -m "graph: sources (caches, published mirror) and offline FotMob season/competition helpers" -- graph/src.py graph/fm.py tests/test_graph_src.py
```

(`git add` both new files first.)

---

### Task 3: One FotMob match → rows

**Files:**
- Create: `graph/rows.py`
- Test: `tests/test_graph_rows.py`

**Interfaces:**
- Consumes: `Registry.mint` (Task 1), `fm.iso` (Task 2), `db.matches.est_minutes(m, pid, started)` (existing).
- Produces: `match_rows(rec: dict, eid: int, reg: Registry) -> dict[str, list]` with keys `team, player, referee, stadium, match` (entity rows, each with its key column), `appearance, event` (link rows), `xref` (tuples `(type, tifo_id, source, source_id, method, conf)`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_graph_rows.py
from graph.ids import Registry
from graph.rows import match_rows

REC = {"id": 900, "date": "2026-08-20T22:00:00.000Z", "comp": 538, "round": "1", "home": [10, "Al Ain", 2], "away": [20, "Al Wahda", 1],
       "stadium": ["Hazza Bin Zayed", "Al Ain"], "referee": "Ali X", "attendance": "12,345",
       "lineups": {"h": {"formation": "4-3-3", "players": [[1, "Keeper", "1", 11, 1, 7.1], [2, "Striker", "9", 115, 1, 8.4], [3, "Bench", "20", None, 0, None], [4, "Sub", "17", None, 0, 6.5]]},
                   "a": {"formation": "4-4-2", "players": [[5, "Away GK", "1", 11, 1, 6.0]]}},
       "events": [[30, "g", "h", 2, "Striker", 4, None], [55, "s", "h", 4, "Sub", 2, "Striker"], [60, "g", "a", 5, "Away GK", None, "own"],
                  [70, "y", "a", 5, "Away GK", None, "Yellow"], [80, "g", "a", 7, "Unknown", None, "pen"], [88, "r", "h", 4, "Sub", None, "YellowRed"]],
       "ps": {"2": {"r": 8.4, "min": 55, "g": 1, "a": 0, "t": 10}}}


def rows():
    return match_rows(REC, 1, Registry())


def test_match_row():
    m = rows()["match"][0]
    assert (m["hs"], m["as_"], m["date"], m["attendance"], m["status"]) == (2, 1, "2026-08-20T22:00:00Z", 12345, "finished")
    assert m["home"] == 1 and m["away"] == 2


def test_appearances_and_minutes():
    ap = {a["pid"]: a for a in rows()["appearance"]}
    assert ap[2]["minutes"] == 55 and ap[2]["goals"] == 1 and ap[2]["rating"] == 8.4 and ap[2]["started"] == 1
    assert ap[4]["played"] == 1 and ap[4]["started"] == 0 and ap[4]["red"] == 1


def test_unused_sub_not_played():
    ap = {a["pid"]: a for a in rows()["appearance"]}
    assert ap[3]["played"] == 0 and ap[3]["minutes"] in (None, 0)


def test_own_goal_not_credited_and_scorer_without_lineup_kept():
    r = rows()
    ap = {a["pid"]: a for a in r["appearance"]}
    assert ap[5]["goals"] == 0
    types = [e["type"] for e in r["event"]]
    assert types == ["goal", "sub", "own_goal", "yellow", "penalty_goal", "second_yellow"]
    assert any(a["pid"] for a in r["appearance"] if a["pid"] not in (1, 2, 3, 4, 5))   # player 7 scored with no lineup row


def test_xref_native():
    x = rows()["xref"]
    assert ("match", 1, "fotmob", "900", "fotmob-native", 1.0) in x
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_graph_rows.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'graph.rows'`

- [ ] **Step 3: Write the implementation**

`graph/rows.py`:
```python
"""One finished FotMob match (db/matches.py's compact record) as graph rows. The nightly build and, in phase 6, the
poller at the final whistle both call match_rows, so the two can never count differently."""
import json, re
from collections import Counter, defaultdict
from graph.fm import iso

GOAL = {None: "goal", "own": "own_goal", "pen": "penalty_goal"}


def _minute(v):
    m = re.match(r"(\d+)(?:\+(\d+))?", str(v if v is not None else ""))
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (None, 0)


def _int(v):
    try:
        return int(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def match_rows(rec, eid, reg):
    from db.matches import est_minutes
    out, seen = defaultdict(list), set()

    def ent(t, src_id, row, method="fotmob-native", src="fotmob"):
        i = reg.mint(t, src, src_id)
        if (t, i) not in seen:
            seen.add((t, i))
            out["xref"].append((t, i, src, str(src_id), method, 1.0))
            row = dict(row)
            row[{"team": "tid", "player": "pid", "referee": "rid", "stadium": "sid", "match": "mid"}[t]] = i
            out[t].append(row)
        return i

    h, a = rec["home"], rec["away"]
    side_t = {"h": ent("team", h[0], {"name": h[1]}), "a": ent("team", a[0], {"name": a[1]})}
    st = rec.get("stadium") or [None, None]
    sid = ent("stadium", f"{st[0]}|{st[1] or ''}", {"name": st[0], "city": st[1]}, "fotmob-name", "fotmob-name") if st[0] else None
    rid = ent("referee", rec["referee"], {"name": rec["referee"]}, "fotmob-name", "fotmob-name") if rec.get("referee") else None
    mid = ent("match", rec["id"], {"eid": eid, "round": rec.get("round"), "date": iso(rec.get("date")), "home": side_t["h"], "away": side_t["a"],
                                   "hs": h[2], "as_": a[2], "status": "finished", "sid": sid, "rid": rid, "attendance": _int(rec.get("attendance"))})
    events = rec.get("events") or []
    ps = rec.get("ps") or {}
    goals, assists, yellow, red, came_on = Counter(), Counter(), Counter(), Counter(), set()
    for e in events:
        if e[1] == "g" and e[6] != "own":
            goals[e[3]] += 1
            if e[5]:
                assists[e[5]] += 1
        elif e[1] == "y":
            yellow[e[3]] += 1
        elif e[1] == "r":
            red[e[3]] += 1
        elif e[1] == "s" and e[3]:
            came_on.add(e[3])
    in_lineup = set()

    def appear(fid, name, side, shirt=None, position=None, started=None, rating=None):
        pid = ent("player", fid, {"name": name})
        s = ps.get(str(fid)) or {}
        minutes = s.get("min")
        if minutes is None and started is not None:
            minutes = est_minutes(rec, fid, started)
        if started:
            played = 1
        elif started == 0:
            played = 1 if (fid in came_on or (minutes or 0) > 0) else (0 if any(e[1] == "s" for e in events) or ps else None)
        else:
            played = 1
        stats = {k: v for k, v in s.items() if k != "t"}
        out["appearance"].append({"mid": mid, "pid": pid, "tid": side_t[side], "played": played, "started": started,
                                  "minutes": minutes if played else (0 if played == 0 else None), "position": position, "shirt": shirt,
                                  "rating": s.get("r") if s.get("r") is not None else rating,
                                  "goals": s["g"] if s.get("g") is not None else goals[fid], "assists": s["a"] if s.get("a") is not None else assists[fid],
                                  "yellow": yellow[fid], "red": red[fid], "stats": json.dumps(stats, sort_keys=True) if stats else None})

    for side in ("h", "a"):
        for p in ((rec.get("lineups") or {}).get(side) or {}).get("players") or []:
            if p[0] and p[0] not in in_lineup:
                in_lineup.add(p[0])
                appear(p[0], p[1], side, p[2], p[3], int(bool(p[4])), p[5])
    for e in events:                                   # a scorer or assister whose side has no lineup row for him
        if e[1] == "g":
            side = e[2] if e[6] != "own" else ("a" if e[2] == "h" else "h")
            for fid, nm in ((e[3], e[4]),) + (((e[5], None),) if e[6] != "own" and e[5] else ()):
                if fid and fid not in in_lineup:
                    in_lineup.add(fid)
                    appear(fid, nm, side)
    for seq, e in enumerate(events):
        mn, add = _minute(e[0])
        if e[1] == "g":
            tp, pid2, det = GOAL.get(e[6], "goal"), (ent("player", e[5], {"name": None}) if e[5] else None), (e[7] if len(e) > 7 else None)
        elif e[1] == "s":
            tp, pid2, det = "sub", (ent("player", e[5], {"name": e[6]}) if e[5] else None), None
        else:
            tp = {"y": "yellow", "r": "second_yellow" if e[6] == "YellowRed" else "red"}.get(e[1], "card")
            pid2, det = None, e[6]
        out["event"].append({"mid": mid, "seq": seq, "minute": mn, "added": add, "type": tp, "side": e[2], "tid": side_t.get(e[2]),
                             "pid": ent("player", e[3], {"name": e[4]}) if e[3] else None, "pid2": pid2, "detail": det})
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_graph_rows.py -q`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git commit -m "graph: match_rows — one FotMob match as appearances, events and entities (shared with the live path)" -- graph/rows.py tests/test_graph_rows.py
```

---

### Task 4: FotMob matches loader

**Files:**
- Create: `graph/load/__init__.py`, `graph/load/fotmob_matches.py`
- Test: `tests/test_graph_load_fotmob.py`

**Interfaces:**
- Consumes: `Graph`, `Registry`, `Sources`, `fm.season_map/season_of/comp_info`, `match_rows`.
- Produces: `load(G, reg, S, limit=None) -> dict` (`{"matches": n, "skipped": n}`); after it, every FotMob competition, edition, team, player, referee, stadium and match is in the graph. Convention for every loader: `load(G, reg, S) -> dict` of counts.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graph_load_fotmob.py
import gzip, json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import fotmob_matches
from tests.test_graph_rows import REC


def test_loads_two_matches(tmp_path):
    mx = tmp_path / "db" / ".cache" / "fm" / "mx"
    mx.mkdir(parents=True)
    (mx / "900.json").write_bytes(gzip.compress(json.dumps(REC).encode()))
    other = dict(REC, id=901, home=[20, "Al Wahda", 0], away=[10, "Al Ain", 0], date="2027-01-10T15:00:00.000Z")
    (mx / "901.json").write_text(json.dumps(other))
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    n = fotmob_matches.load(G, reg, Sources(str(tmp_path), s3=False))
    assert n["matches"] == 2
    assert G.c.execute("select count(*) from team").fetchone()[0] == 2
    assert G.c.execute("select season from edition order by season").fetchall() == [("2026/2027",)]
    assert G.c.execute("select count(*) from appearance where played=1").fetchone()[0] >= 5
    assert G.c.execute("select count(*) from xref where type='match'").fetchone()[0] == 2
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_graph_load_fotmob.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'graph.load'`

- [ ] **Step 3: Write the implementation**

`graph/load/__init__.py`:
```python
"""One loader per source: load(G, reg, S) -> counts. Run by graph.build in precedence order."""
```

`graph/load/fotmob_matches.py`:
```python
"""Every finished match in FotMob detail (db/.cache/fm/mx/, 92k since 2010/11) with its competition, edition, teams,
players, referee and stadium. FotMob ids are minted first and in id order, so the first registry is deterministic."""
import os
from graph import fm
from graph.rows import match_rows

ENT = ("team", "player", "referee", "stadium", "match")


def load(G, reg, S, limit=None):
    base = os.path.join(S.db, "fm", "mx")
    files = sorted((f for f in os.listdir(base) if f.split(".")[0].isdigit()), key=lambda f: int(f.split(".")[0])) if os.path.isdir(base) else []
    if limit:
        files = files[:limit]
    labels, calendar = fm.season_map(S)
    comps, done_c, done_e = fm.comp_info(S), set(), set()
    n = skipped = 0
    for f in files:
        rec = S.read(os.path.join(base, f))
        if not rec or not rec.get("home") or not rec.get("away") or not rec.get("date") or rec["home"][0] is None:
            skipped += 1
            continue
        c = rec.get("comp")
        cid = reg.mint("competition", "fotmob", c)
        if cid not in done_c:
            done_c.add(cid)
            info = comps.get(int(c)) if c is not None else None
            G.put("competition", {"cid": cid, **(info or {"name": f"FotMob {c}"})}, "fotmob")
            G.xref("competition", cid, "fotmob", c, "fotmob-native")
        season = fm.season_of(rec["id"], rec["date"], c, labels, calendar)
        eid = reg.mint("edition", "fotmob", f"{c}|{season}")
        if eid not in done_e:
            done_e.add(eid)
            G.put("edition", {"eid": eid, "cid": cid, "season": season}, "fotmob")
            G.xref("edition", eid, "fotmob", f"{c}|{season}", "fotmob-native")
        rows = match_rows(rec, eid, reg)
        for t in ENT:
            for r in rows.get(t, ()):
                G.put(t, r, "fotmob")
        G.many("appearance", rows.get("appearance"), "fotmob")
        G.many("event", rows.get("event"), "fotmob")
        for x in rows.get("xref", ()):
            G.xref(*x)
        n += 1
        if n % 10000 == 0:
            print(f"fotmob matches: {n}", flush=True)
            G.c.commit()
    G.c.execute("""UPDATE edition SET start=(SELECT min(substr(date,1,10)) FROM match WHERE match.eid=edition.eid),
                   end=(SELECT max(substr(date,1,10)) FROM match WHERE match.eid=edition.eid)""")
    return {"matches": n, "skipped": skipped}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m pytest tests/test_graph_load_fotmob.py -q`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git commit -m "graph: FotMob matches loader (competitions, editions, matches, appearances, events)" -- graph/load/__init__.py graph/load/fotmob_matches.py tests/test_graph_load_fotmob.py
```

---

### Task 5: FotMob profiles and Arabic names

**Files:**
- Create: `graph/load/fotmob_profiles.py`, `graph/load/names.py`
- Test: `tests/test_graph_load_profiles.py`

**Interfaces:**
- Consumes: Task 1–2 APIs.
- Produces: `fotmob_profiles.load(G, reg, S)` fills `player` bios, creates `coach` rows (`isCoach`) and `spell` rows (`careerItems.senior/youth/national team` teamEntries); `names.load(G, reg, S)` fills `name_ar` for teams (teams_ar.yaml, `names/clubs_ar.json`, FotMob `Participants`), players (`names/players_ar.json`, Wikidata `xref` from its `qid`), coaches and referees.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_graph_load_profiles.py
import gzip, json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import fotmob_profiles, names

PROFILE = {"id": 77, "name": "Omar A", "isCoach": False, "birthDate": {"utcTime": "1991-10-01T00:00:00.000Z"},
           "positionDescription": {"positions": [{"strPos": {"label": "Striker"}, "isMainPosition": True}]},
           "playerInformation": [{"title": "Height", "value": {"numberValue": 182}}, {"title": "Preferred foot", "value": {"key": "left"}},
                                 {"title": "Country", "value": {"fallback": "United Arab Emirates"}, "countryCode": "ARE"}],
           "careerHistory": {"careerItems": {"senior": {"teamEntries": [{"teamId": 10, "team": "Al Ain", "startDate": "2008-07-01T00:00:00", "endDate": None,
                                                                          "appearances": "300", "goals": "120", "assists": "80", "transferType": None}]},
                                             "national team": {"teamEntries": [{"teamId": 5789, "team": "UAE", "startDate": "2011-01-01T00:00:00", "endDate": None, "appearances": "90", "goals": "40", "assists": None}]}}}}
COACH = {"id": 88, "name": "Coach K", "isCoach": True, "birthDate": {"utcTime": "1970-01-01T00:00:00.000Z"}, "playerInformation": [], "careerHistory": {}}


def mk(tmp_path):
    p = tmp_path / "db" / ".cache" / "fm" / "p"
    p.mkdir(parents=True)
    (p / "77.json.gz").write_bytes(gzip.compress(json.dumps(PROFILE).encode()))
    (p / "88.json.gz").write_bytes(gzip.compress(json.dumps(COACH).encode()))
    n = tmp_path / "names"
    n.mkdir()
    (n / "players_ar.json").write_text(json.dumps({"77": {"latin": "Omar A", "ar": "عمر أ", "source": "wikidata", "qid": "Q1"}}), encoding="utf-8")
    (n / "clubs_ar.json").write_text(json.dumps({"10": {"latin": "Al Ain", "ar": "العين", "source": "wikidata", "qid": None}}), encoding="utf-8")
    (n / "coaches_ar.json").write_text("{}")
    (n / "referees_ar.json").write_text("{}")
    return Sources(str(tmp_path), s3=False)


def test_profiles_and_names(tmp_path):
    S, G, reg = mk(tmp_path), Graph(str(tmp_path / "t.db")), Registry()
    fotmob_profiles.load(G, reg, S)
    names.load(G, reg, S)
    pid = reg.get("player", "fotmob", 77)
    row = G.c.execute("select born, nationality, height, foot, position, name_ar from player where pid=?", (pid,)).fetchone()
    assert row == ("1991-10-01", "ARE", 182, "left", "Striker", "عمر أ")
    assert G.c.execute("select count(*) from spell where pid=?", (pid,)).fetchone()[0] == 2
    assert G.c.execute("select national from spell where pid=? and apps=90", (pid,)).fetchone()[0] == 1
    assert G.c.execute("select name from coach").fetchall() == [("Coach K",)]
    assert G.c.execute("select source_id from xref where type='player' and source='wikidata'").fetchall() == [("Q1",)]
    assert G.c.execute("select name_ar from team where tid=?", (reg.get("team", "fotmob", 10),)).fetchone()[0] == "العين"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_graph_load_profiles.py -q`
Expected: FAIL, `ImportError: cannot import name 'fotmob_profiles'`

- [ ] **Step 3: Write the implementation**

`graph/load/fotmob_profiles.py`:
```python
"""FotMob player and coach profiles (db/.cache/fm/p/, ~65k): bio and career spells. A coach's profile makes a coach row;
FotMob gives no club tenure dates for coaches (phase 5 adds them)."""
import os

INFO = {"Height": "height", "Preferred foot": "foot", "Country": "nationality"}


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def bio(d):
    row = {"name": d.get("name"), "born": ((d.get("birthDate") or {}).get("utcTime") or "")[:10] or None}
    if row["born"] == "0001-01-01":
        row["born"] = None
    for it in d.get("playerInformation") or []:
        k, v = INFO.get(it.get("title")), it.get("value") or {}
        if k == "height":
            row[k] = v.get("numberValue")
        elif k == "foot":
            row[k] = v.get("key")
        elif k == "nationality":
            row[k] = it.get("countryCode") or v.get("fallback")
    pos = [p for p in (d.get("positionDescription") or {}).get("positions") or [] if p.get("isMainPosition")]
    row["position"] = ((pos[0].get("strPos") or {}).get("label")) if pos else None
    return row


def load(G, reg, S):
    base = os.path.join(S.db, "fm", "p")
    files = sorted((f for f in os.listdir(base) if f.split(".")[0].isdigit()), key=lambda f: int(f.split(".")[0])) if os.path.isdir(base) else []
    n = coaches = spells = 0
    for f in files:
        d = S.read(os.path.join(base, f))
        if not d or not d.get("id"):
            continue
        b = bio(d)
        if d.get("isCoach"):
            kid = reg.mint("coach", "fotmob", d["id"])
            G.put("coach", {"kid": kid, "name": b["name"], "born": b["born"], "nationality": b.get("nationality"),
                            "pid": reg.get("player", "fotmob", d["id"])}, "fotmob")
            G.xref("coach", kid, "fotmob", d["id"], "fotmob-native")
            coaches += 1
            continue
        pid = reg.mint("player", "fotmob", d["id"])
        G.put("player", {"pid": pid, **b}, "fotmob")
        G.xref("player", pid, "fotmob", d["id"], "fotmob-native")
        n += 1
        for kind, entries in ((d.get("careerHistory") or {}).get("careerItems") or {}).items():
            for e in entries.get("teamEntries") or []:
                if not e.get("teamId"):
                    continue
                tid = reg.mint("team", "fotmob", e["teamId"])
                G.put("team", {"tid": tid, "name": e.get("team"), "kind": "national" if kind == "national team" else None}, "fotmob")
                G.xref("team", tid, "fotmob", e["teamId"], "fotmob-native")
                G.many("spell", [{"pid": pid, "tid": tid, "start": (e.get("startDate") or "")[:10] or None, "end": (e.get("endDate") or "")[:10] or None,
                                  "apps": _int(e.get("appearances")), "goals": _int(e.get("goals")), "assists": _int(e.get("assists")),
                                  "loan": 1 if "loan" in str(e.get("transferType") or "").lower() else 0,
                                  "national": 1 if kind == "national team" else 0, "youth": 1 if kind == "youth" else 0}], "fotmob")
                spells += 1
    return {"players": n, "coaches": coaches, "spells": spells}
```

`graph/load/names.py`:
```python
"""Arabic names: the house spellings (teams_ar.yaml), names/*_ar.json (Wikidata, Arabic Wikipedia, then generated) and
FotMob's Arabic map for teams. Run after the FotMob loaders: it fills name_ar, never a name."""
import os


def load(G, reg, S):
    n = {"team": 0, "player": 0, "coach": 0, "referee": 0, "wikidata": 0}
    teams = {}
    try:
        import config
        for k, v in (config.team_overrides() or {}).items():
            if isinstance(v, dict) and v.get("name_ar"):
                teams.setdefault(str(k), v["name_ar"])
            elif isinstance(v, str):
                teams.setdefault(str(k), v)
    except Exception as e:
        print(f"teams_ar.yaml not read: {e}", flush=True)
    for k, v in (S.read(os.path.join(S.names, "clubs_ar.json")) or {}).items():
        if v.get("ar"):
            teams.setdefault(str(k), v["ar"])
    for k, v in ((S.read(os.path.join(S.db, "fm_ar.json")) or {}).get("Participants") or {}).items():
        teams.setdefault(str(k), v)
    for k, ar in sorted(teams.items()):
        tid = reg.get("team", "fotmob", int(k)) if k.isdigit() else None
        if tid:
            G.put("team", {"tid": tid, "name_ar": ar}, "names")
            n["team"] += 1
    for t, f in (("player", "players_ar.json"), ("coach", "coaches_ar.json")):
        for k, v in sorted((S.read(os.path.join(S.names, f)) or {}).items()):
            i = reg.get(t, "fotmob", int(k)) if k.isdigit() else None
            if i and v.get("ar"):
                G.put(t, {{"player": "pid", "coach": "kid"}[t]: i, "name_ar": v["ar"]}, "names")
                n[t] += 1
            if i and v.get("qid"):
                if reg.alias(t, "wikidata", v["qid"], i):
                    G.xref(t, i, "wikidata", v["qid"], "names-" + str(v.get("source")))
                    n["wikidata"] += 1
    for k, v in sorted((S.read(os.path.join(S.names, "referees_ar.json")) or {}).items()):
        rid = reg.get("referee", "fotmob-name", v.get("latin")) if v.get("latin") else None
        if rid and v.get("ar"):
            G.put("referee", {"rid": rid, "name_ar": v["ar"]}, "names")
            reg.alias("referee", "fotmob", k, rid)
            G.xref("referee", rid, "fotmob", k, "same-name-same-source")
            n["referee"] += 1
    return n
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m pytest tests/test_graph_load_profiles.py -q`
Expected: 1 passed. If `config.team_overrides()` returns a different shape, print one item and adapt the two `isinstance` branches; the test does not depend on it.

- [ ] **Step 5: Commit**

```bash
git commit -m "graph: FotMob profiles (bios, coaches, career spells) and Arabic names with Wikidata links" -- graph/load/fotmob_profiles.py graph/load/names.py tests/test_graph_load_profiles.py
```

---

### Task 6: Match linking and the schochastics results (1888–)

**Files:**
- Create: `graph/link.py`, `graph/load/schochastics.py`
- Test: `tests/test_graph_link.py`

**Interfaces:**
- Consumes: `Graph`, `Registry`.
- Produces: `MatchIndex(G)` with `.find(date, h, a) -> (mid, swapped: bool) | (None, None)` and `.add(mid, date, h, a)`; `twin(G, idx, date, h, a, hs, as_, src) -> mid|None` (finds, compares the score, logs a conflict, returns the mid or None); `vote_alias(reg, t, votes: dict[src_key, Counter[tifo_id]], src, min_n, share) -> dict[src_key, tifo_id]`; `schochastics.load(G, reg, S)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_graph_link.py
from collections import Counter
from graph.db import Graph
from graph.ids import Registry
from graph.link import MatchIndex, twin, vote_alias


def g_with_match(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    G.put("match", {"mid": 1, "date": "2020-05-02T19:00:00Z", "home": 10, "away": 20, "hs": 2, "as_": 1}, "fotmob")
    return G


def test_find_one_day_off_and_swapped(tmp_path):
    idx = MatchIndex(g_with_match(tmp_path))
    assert idx.find("2020-05-03", 10, 20) == (1, False)
    assert idx.find("2020-05-02", 20, 10) == (1, True)
    assert idx.find("2020-05-05", 10, 20) == (None, None)


def test_twin_with_other_score_logs_conflict(tmp_path):
    G = g_with_match(tmp_path)
    idx = MatchIndex(G)
    assert twin(G, idx, "2020-05-02", 10, 20, 2, 0, "sch") == 1
    assert G.c.execute("select field, kept, other, other_src from conflict").fetchall() == [("score", "2-1", "2-0", "sch")]
    assert twin(G, idx, "2020-05-02", 20, 10, 1, 2, "sch") == 1          # swapped sides, same score: no new conflict
    assert G.c.execute("select count(*) from conflict").fetchone()[0] == 1


def test_vote_alias_needs_majority():
    reg = Registry()
    a, b = reg.mint("competition", "fotmob", 47), reg.mint("competition", "fotmob", 48)
    got = vote_alias(reg, "competition", {"england": Counter({a: 95, b: 5}), "mixed": Counter({a: 50, b: 50})}, "sch", min_n=20, share=0.9)
    assert got == {"england": a}
    assert reg.get("competition", "sch", "england") == a and reg.get("competition", "sch", "mixed") is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_graph_link.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'graph.link'`

- [ ] **Step 3: Write the implementation**

`graph/link.py`:
```python
"""Linking across sources (spec §3.3): a game in another source is the graph's match when it is on the same date ±1 day
with the same two (already linked) teams; home and away may be swapped (neutral venues are filed either way). A
competition or edition of another source is ours when the matches it holds overwhelmingly sit in one of ours."""
from collections import defaultdict
from datetime import date, timedelta


def _days(d):
    d0 = date.fromisoformat(d[:10])
    return [str(d0), str(d0 - timedelta(days=1)), str(d0 + timedelta(days=1))]


class MatchIndex:
    def __init__(self, G):
        self.by = defaultdict(list)
        for mid, d, h, a in G.c.execute("SELECT mid, substr(date,1,10), home, away FROM match WHERE date IS NOT NULL"):
            self.by[(h, d)].append((mid, a))

    def add(self, mid, d, h, a):
        self.by[(h, d[:10])].append((mid, a))

    def find(self, d, h, a):
        for dd in _days(d):
            for mid, aa in self.by.get((h, dd), ()):
                if aa == a:
                    return mid, False
            for mid, aa in self.by.get((a, dd), ()):
                if aa == h:
                    return mid, True
        return None, None


def twin(G, idx, d, h, a, hs, as_, src):
    """The graph's match for this game, or None. A different score is logged (the graph keeps the higher source's)."""
    mid, swapped = idx.find(d, h, a)
    if mid is None:
        return None
    x, y = (as_, hs) if swapped else (hs, as_)
    kept = G.c.execute("SELECT hs, as_, src FROM match WHERE mid=?", (mid,)).fetchone()
    if kept and None not in (kept[0], x) and (kept[0], kept[1]) != (x, y):
        G.conflict("match", mid, "score", f"{kept[0]}-{kept[1]}", kept[2], f"{x}-{y}", src)
    return mid


def vote_alias(reg, t, votes, src, min_n=20, share=0.9):
    """votes {source key: Counter{tifo id: matches}} -> {source key: tifo id} for keys with min_n votes and share of them
    on one id; each link is written to the registry (a key already naming another entity is left alone)."""
    out = {}
    for k in sorted(votes):
        c = votes[k]
        tot = sum(c.values())
        if not tot:
            continue
        best, n = c.most_common(1)[0]
        if n >= min_n and n >= share * tot and reg.alias(t, src, k, best):
            out[k] = best
    return out
```

`graph/load/schochastics.py`:
```python
"""schochastics/football-data (db/.cache/games.parquet, 1.3M league and continental results since 1888): a result
already in the graph becomes an xref of that match; the rest are new matches. Clubs link through db/history.py's
crosswalk (date+score votes, crosswalk.json); a competition (or a season of it) links to ours when 90% of its linked
games sit in one of ours. Hygiene as db/history.py: one copy per game, no placeholder teams, no «X v X»."""
import os
from collections import Counter, defaultdict
from graph.link import MatchIndex, twin, vote_alias


def _season(d):
    return f"{d.year}/{d.year + 1}" if d.month >= 7 else f"{d.year - 1}/{d.year}"


def load(G, reg, S):
    import duckdb
    from db.history import BLANK
    pq = os.path.join(S.db, "games.parquet").replace("\\", "/")
    if not os.path.exists(pq):
        return {"skipped": "no games.parquet"}
    cw = S.read(os.path.join(S.db, "crosswalk.json")) or {}
    for fid, key in sorted(cw.items(), key=lambda x: int(x[0])):
        tid = reg.mint("team", "fotmob", int(fid))
        if reg.alias("team", "sch", key, tid):
            G.xref("team", tid, "sch", key, "vote")
    rows = duckdb.sql(f"""select date, home_ident, away_ident, gh, ga, competition, level, home, away, home_code
        from read_parquet('{pq}') where gh is not null and ga is not null and home_ident <> away_ident
          and home_ident not in {BLANK} and away_ident not in {BLANK}
        qualify row_number() over (partition by date, home_ident, away_ident, gh, ga, competition order by level) = 1
        order by date, competition, home_ident, away_ident""").fetchall()
    idx = MatchIndex(G)
    eid_of = {mid: eid for mid, eid in G.c.execute("SELECT mid, eid FROM match")}
    cid_of = {eid: cid for eid, cid in G.c.execute("SELECT eid, cid FROM edition")}
    # pass 1: twins, and the competitions/editions their twins vote for
    twins, cvotes, evotes = {}, defaultdict(Counter), defaultdict(Counter)
    for i, (d, hi, ai, gh, ga, comp, lvl, hn, an, cc) in enumerate(rows):
        h, a = reg.get("team", "sch", hi), reg.get("team", "sch", ai)
        if h and a:
            mid = twin(G, idx, str(d), h, a, gh, ga, "sch")
            if mid:
                twins[i] = mid
                e = eid_of.get(mid)
                if e:
                    cvotes[comp][cid_of[e]] += 1
                    evotes[f"{comp}|{_season(d)}"][e] += 1
    vote_alias(reg, "competition", cvotes, "sch", min_n=20, share=0.9)
    vote_alias(reg, "edition", evotes, "sch", min_n=5, share=0.9)
    # pass 2: rows
    new = linked = 0
    done = set()
    for i, (d, hi, ai, gh, ga, comp, lvl, hn, an, cc) in enumerate(rows):
        if i in twins:
            G.xref("match", twins[i], "sch", f"{d}|{hi}|{ai}", "date+teams")
            linked += 1
            continue
        cid = reg.get("competition", "sch", comp) or reg.mint("competition", "sch", comp)
        if ("c", cid) not in done:
            done.add(("c", cid))
            G.put("competition", {"cid": cid, "name": comp, "kind": "league" if lvl == "national" else None,
                                  "scope": None if lvl == "national" else lvl, "country": cc if lvl == "national" else None}, "sch")
            G.xref("competition", cid, "sch", comp, "vote" if reg.get("competition", "sch", comp) in cid_of.values() else "sch-native")
        sk = f"{comp}|{_season(d)}"
        eid = reg.get("edition", "sch", sk) or reg.mint("edition", "sch", sk)
        if ("e", eid) not in done:
            done.add(("e", eid))
            G.put("edition", {"eid": eid, "cid": cid, "season": _season(d)}, "sch")
            G.xref("edition", eid, "sch", sk, "sch-native")
        h = reg.get("team", "sch", hi) or reg.mint("team", "sch", hi)
        a = reg.get("team", "sch", ai) or reg.mint("team", "sch", ai)
        for tid, key, nm in ((h, hi, hn), (a, ai, an)):
            if ("t", tid) not in done:
                done.add(("t", tid))
                G.put("team", {"tid": tid, "name": nm, "kind": "club"}, "sch")
                if not G.c.execute("SELECT 1 FROM xref WHERE type='team' AND source='sch' AND source_id=?", (key,)).fetchone():
                    G.xref("team", tid, "sch", key, "sch-native")
        mid = reg.mint("match", "sch", f"{d}|{hi}|{ai}")
        G.put("match", {"mid": mid, "eid": eid, "date": str(d), "home": h, "away": a, "hs": gh, "as_": ga, "status": "finished"}, "sch")
        G.xref("match", mid, "sch", f"{d}|{hi}|{ai}", "sch-native")
        idx.add(mid, str(d), h, a)
        new += 1
        if new % 100000 == 0:
            print(f"schochastics: {new} new", flush=True)
            G.c.commit()
    return {"rows": len(rows), "linked": linked, "new": new, "comps_linked": sum(1 for k in cvotes if reg.get("competition", "sch", k))}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_graph_link.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git commit -m "graph: cross-source match linking and the schochastics results since 1888" -- graph/link.py graph/load/schochastics.py tests/test_graph_link.py
```

---

### Task 7: 365Scores — teams, champions, final tables, Arab leagues

**Files:**
- Create: `graph/load/s365.py`
- Test: `tests/test_graph_load_s365.py`

**Interfaces:**
- Consumes: `Sources.published`, `vote_alias`, `MatchIndex`, `twin`.
- Produces: `load(G, reg, S)`. Teams: `index.json` teams `[id, ar, en, country id, fotmob id]` (a FotMob id links; no FotMob id means a new team). Competitions: linked to a FotMob competition when the same country and the same normalised English name appear in `fm_allleagues.json`, else new. `champions` → `honour(kind='champion', rank=1)`, `tables` → `standing` (only for editions with no standing yet), `live.results` → matches.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graph_load_s365.py
import json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import s365


def mk(tmp_path):
    m = tmp_path / "mirror" / "s365"
    (m / "comp").mkdir(parents=True)
    (m / "index.json").write_text(json.dumps({
        "countries": {"119": ["الأردن", "Jordan"], "1": ["إنجلترا", "England"]},
        "comps": [[565, "الدوري الأردني", "Pro League", 119, 0, 10, "1944", "2025/2026", 0, 0, 0, 0],
                  [7, "الدوري الإنجليزي", "Premier League", 1, 0, 127, "1888/1889", "2025/2026", 0, 0, 0, 0]],
        "teams": [[8285, "الحسين إربد", "Al Hussein", 119, None], [8276, "الفيصلي", "Al Faisaly", 119, None], [5, "أرسنال", "Arsenal", 1, 9825]]}), encoding="utf-8")
    (m / "comp" / "565.json").write_text(json.dumps({"id": "565", "champions": [["2024/2025", 8285, ["16", "5", "1", "53"], 135]],
        "tables": {"2024/2025": [[1, 8285, 22, 16, 5, 1, 50, 10, 53.0], [2, 8276, 22, 15, 5, 2, 45, 15, 50.0]]},
        "live": {"results": [[1, "2026-10-24T20:30", 137, 6, 8285, 8276, 2, 1, 4, 1]]}}), encoding="utf-8")
    (m / "comp" / "7.json").write_text(json.dumps({"id": "7", "champions": [["1888/1889", 5, [], 1]], "tables": {}, "live": {}}), encoding="utf-8")
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    (db / "fm_allleagues.json").write_text(json.dumps({"popular": [], "international": [], "countries": [{"ccode": "ENG", "name": "England", "leagues": [{"id": 47, "name": "Premier League"}]}]}))
    return Sources(str(tmp_path), mirror=str(tmp_path / "mirror"), s3=False)


def test_s365(tmp_path):
    S, G, reg = mk(tmp_path), Graph(str(tmp_path / "t.db")), Registry()
    arsenal = reg.mint("team", "fotmob", 9825)
    pl = reg.mint("competition", "fotmob", 47)
    out = s365.load(G, reg, S)
    assert reg.get("team", "s365", 5) == arsenal
    assert reg.get("competition", "s365", 7) == pl
    assert out["champions"] == 2
    jo = reg.get("competition", "s365", 565)
    assert G.c.execute("select count(*) from standing s join edition e on e.eid=s.eid where e.cid=?", (jo,)).fetchone()[0] == 2
    assert G.c.execute("select count(*) from match where src='s365'").fetchone()[0] == 1
    assert G.c.execute("select name_ar from team where tid=?", (reg.get("team", "s365", 8276),)).fetchone()[0] == "الفيصلي"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_graph_load_s365.py -q`
Expected: FAIL, `ImportError: cannot import name 's365'`

- [ ] **Step 3: Write the implementation**

`graph/load/s365.py`:
```python
"""365Scores, read from what db/scores365.py publishes (v1/s365/): every competition's champions (the Premier League from
1888/89, the UAE league from 1973/74), the Arab final tables, and this season's results of the Arab leagues FotMob lacks.
A 365 team links through the FotMob id db/scores365.py found for it; a 365 competition links when FotMob lists one with
the same English name in the same country."""
import os, re, unicodedata
from graph.link import MatchIndex, twin


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def load(G, reg, S):
    ix = S.published("s365/index.json")
    if not ix:
        return {"skipped": "no s365/index.json"}
    countries = {str(k): v for k, v in (ix.get("countries") or {}).items()}
    fm_by = {}
    al = S.read(os.path.join(S.db, "fm_allleagues.json")) or {}
    for grp in al.get("countries") or []:
        for lg in grp.get("leagues") or []:
            fm_by.setdefault((fold(grp.get("name")), fold(lg.get("name"))), []).append(int(lg["id"]))
    n = {"teams": 0, "teams_linked": 0, "comps": 0, "comps_linked": 0, "champions": 0, "standings": 0, "matches": 0, "matches_linked": 0}
    for sid, ar, en, cc, fid in sorted(ix.get("teams") or [], key=lambda r: r[0]):
        if fid:
            tid = reg.mint("team", "fotmob", int(fid))
            if reg.alias("team", "s365", sid, tid):
                G.xref("team", tid, "s365", sid, "s365-fmmap")
                n["teams_linked"] += 1
        tid = reg.get("team", "s365", sid) or reg.mint("team", "s365", sid)
        G.put("team", {"tid": tid, "name": en or None, "name_ar": ar or None, "country": (countries.get(str(cc)) or [None, None])[1]}, "s365")
        if not fid:
            G.xref("team", tid, "s365", sid, "s365-native")
        n["teams"] += 1
    eids = {}
    for row in sorted(ix.get("comps") or [], key=lambda r: r[0]):
        cid_s, ar, en, cc, ko = row[0], row[1], row[2], row[3], row[4]
        cname = (countries.get(str(cc)) or [None, None])[1]
        cands = fm_by.get((fold(cname), fold(en)), [])
        if len(cands) == 1 and reg.alias("competition", "s365", cid_s, reg.mint("competition", "fotmob", cands[0])):
            G.xref("competition", reg.get("competition", "s365", cid_s), "s365", cid_s, "country+name")
            n["comps_linked"] += 1
        cid = reg.get("competition", "s365", cid_s) or reg.mint("competition", "s365", cid_s)
        G.put("competition", {"cid": cid, "name": en, "name_ar": ar, "kind": "cup" if ko else "league", "country": cname}, "s365")
        if not cands:
            G.xref("competition", cid, "s365", cid_s, "s365-native")
        n["comps"] += 1
        d = S.published(f"s365/comp/{cid_s}.json") or {}

        def edition(season):
            k = (cid, season)
            if k not in eids:
                hit = G.c.execute("SELECT eid FROM edition WHERE cid=? AND season=?", (cid, season)).fetchone()
                eids[k] = hit[0] if hit else reg.mint("edition", "s365", f"{cid_s}|{season}")
                if not hit:
                    G.put("edition", {"eid": eids[k], "cid": cid, "season": season}, "s365")
                    G.xref("edition", eids[k], "s365", f"{cid_s}|{season}", "s365-native")
            return eids[k]

        def team(sid):
            return reg.get("team", "s365", sid) or reg.mint("team", "s365", sid)

        for season, winner, vals, *_ in d.get("champions") or []:
            if winner:
                eid = edition(season)
                G.c.execute("INSERT OR IGNORE INTO honour(eid, kind, rank, tid, value, src) VALUES(?,?,?,?,?,?)",
                            (eid, "champion", 1, team(winner), ",".join(map(str, vals or [])) or None, "s365"))
                n["champions"] += 1
        for season, rows in sorted((d.get("tables") or {}).items()):
            eid = edition(season)
            if G.c.execute("SELECT 1 FROM standing WHERE eid=?", (eid,)).fetchone():
                continue
            for pos, t, p, w, dr, l, gf, ga, pts in rows:
                G.c.execute("INSERT OR IGNORE INTO standing VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (eid, "", pos, team(t), p, w, dr, l, gf, ga, pts, "s365"))
                n["standings"] += 1
        res = (d.get("live") or {}).get("results") or []
        if res:
            idx = MatchIndex(G)
            for gid, ko, sn, rnd, h, a, hs, as_, *_ in res:
                if hs is None or as_ is None:
                    continue
                th, ta = team(h), team(a)
                mid = twin(G, idx, ko[:10], th, ta, hs, as_, "s365")
                if mid:
                    reg.alias("match", "s365", gid, mid)
                    G.xref("match", mid, "s365", gid, "date+teams")
                    n["matches_linked"] += 1
                    continue
                y, mo = int(ko[:4]), int(ko[5:7])
                mid = reg.mint("match", "s365", gid)
                G.put("match", {"mid": mid, "eid": edition(f"{y}/{y + 1}" if mo >= 7 else f"{y - 1}/{y}"), "round": str(rnd) if rnd is not None else None,
                                "date": ko + ":00Z" if len(ko) == 16 else ko, "home": th, "away": ta, "hs": hs, "as_": as_, "status": "finished"}, "s365")
                G.xref("match", mid, "s365", gid, "s365-native")
                idx.add(mid, ko, th, ta)
                n["matches"] += 1
    return n
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m pytest tests/test_graph_load_s365.py -q`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git commit -m "graph: 365Scores — teams, competitions, champions since 1888, Arab final tables and leagues" -- graph/load/s365.py tests/test_graph_load_s365.py
```

---

### Task 8: RSSSF — the Arab leagues' old seasons

**Files:**
- Create: `graph/load/rsssf.py`
- Test: `tests/test_graph_load_rsssf.py`

**Interfaces:**
- Consumes: `db/.cache/rsssf_clubs.json` (`{fotmob club id: {"positions": [[season, pos, played?, pts, …, "rsssf"]], "matches": [...]}}`, written by `db/rsssf.py`), `Sources.published("history/arab/index.json")` when present.
- Produces: `load(G, reg, S)`: a `spell`-free loader that writes each club's final position per season into `standing` under a per-country league edition (`competition` key `rsssf|<country code>`), skipping editions that already have a standing.

The positions row shape must be read from the real file first, because `db/rsssf.py` documents the matches but not the column order of `positions`.

- [ ] **Step 1: Read the real shape and pin it in the test**

Run:
```bash
python -c "import json; d=json.load(open('db/.cache/rsssf_clubs.json',encoding='utf-8')); k=next(iter(d)); print(k, list(d[k]), d[k]['positions'][:2], str(d[k].get('matches'))[:300])"
grep -n "positions" db/rsssf.py | head
```
Expected: a row like `['1999/2000', 1, 12, 47, 22, 13, 7, 2, 48, 25, 'rsssf']`. Read the line in `db/rsssf.py` that appends to `positions` and write its column order down. The rest of this task assumes `[season, rank, teams_in_league, pts, played, won, drawn, lost, gf, ga, source]`. If the code says otherwise, use its order in both the test and the loader.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_graph_load_rsssf.py
import json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import rsssf


def test_rsssf_positions(tmp_path):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    (db / "rsssf_clubs.json").write_text(json.dumps({"102117": {"positions": [["1999/2000", 1, 12, 47, 22, 13, 7, 2, 48, 25, "rsssf"]], "country": "ARE"}}))
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    reg.mint("team", "fotmob", 102117)
    out = rsssf.load(G, reg, Sources(str(tmp_path), s3=False))
    assert out["rows"] == 1
    row = G.c.execute("select rank, played, won, drawn, lost, gf, ga, pts from standing").fetchone()
    assert row == (1, 22, 13, 7, 2, 48, 25, 47)
```

- [ ] **Step 3: Run it to verify it fails**

Run: `python -m pytest tests/test_graph_load_rsssf.py -q`
Expected: FAIL, `ImportError: cannot import name 'rsssf'`

- [ ] **Step 4: Write the implementation**

`graph/load/rsssf.py`:
```python
"""RSSSF's Arab league tables before the other sources start (db/rsssf.py → db/.cache/rsssf_clubs.json, per FotMob club):
each club's final position per season, as standings of its country's top league. A season the graph already has a table
for (FotMob, 365Scores) is left as it is."""
import os


def load(G, reg, S):
    d = S.read(os.path.join(S.db, "rsssf_clubs.json"))
    if not d:
        return {"skipped": "no rsssf_clubs.json"}
    country_of = {}
    try:
        import config
        for fid in d:
            c = config.country_of_team(int(fid)) if fid.isdigit() else None
            if c:
                country_of[fid] = c.get("code") or c.get("fotmob") or c.get("id")
    except Exception as e:
        print(f"countries.yaml not read: {e}", flush=True)
    n = 0
    have = {eid for (eid,) in G.c.execute("SELECT DISTINCT eid FROM standing")}
    for fid in sorted(d, key=lambda x: int(x) if x.isdigit() else 0):
        if not fid.isdigit():
            continue
        cc = d[fid].get("country") or country_of.get(fid) or "arab"
        tid = reg.mint("team", "fotmob", int(fid))
        cid = reg.get("competition", "rsssf", cc) or reg.mint("competition", "rsssf", cc)
        G.put("competition", {"cid": cid, "name": f"{cc} top league (RSSSF)", "kind": "league", "country": cc}, "rsssf")
        G.xref("competition", cid, "rsssf", cc, "rsssf-native")
        for season, rank, teams, pts, p, w, dr, l, gf, ga, *_ in d[fid].get("positions") or []:
            eid = reg.get("edition", "rsssf", f"{cc}|{season}") or reg.mint("edition", "rsssf", f"{cc}|{season}")
            if eid in have:
                continue
            G.put("edition", {"eid": eid, "cid": cid, "season": season}, "rsssf")
            G.c.execute("INSERT OR IGNORE INTO standing VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (eid, "", rank, tid, p, w, dr, l, gf, ga, pts, "rsssf"))
            n += 1
    return {"rows": n}
```

- [ ] **Step 5: Run it to verify it passes, then commit**

Run: `python -m pytest tests/test_graph_load_rsssf.py -q` → 1 passed.

```bash
git commit -m "graph: RSSSF final positions of the Arab leagues before the other sources" -- graph/load/rsssf.py tests/test_graph_load_rsssf.py
```

---

### Task 9: Transfermarkt — bios, season lines, injuries, and the 2012+ games with their managers

**Files:**
- Create: `graph/load/tm.py`
- Test: `tests/test_graph_load_tm.py`

**Interfaces:**
- Consumes: `db/.cache/tm/player_profiles.csv`, `player_performances.csv`, `player_injuries.csv` (salimt); `history/.cache/tm_playermap.json` (`{tm player id: fotmob id}`), `history/.cache/tm_clubmap.json` (`{tm club id: fotmob id}`), `Sources.published("history/tm/index.json")` (`players {fotmob id: tm id}`); `db/.cache/tm_games.csv.gz`, `tm_game_events.csv.gz` (dcaribou); `MatchIndex`, `twin`.
- Produces: `load(G, reg, S)`: player xref (`birthdate+name`), bio fill (birthplace, nationality2, native name, height, foot, died), `player_season` rows, `injury` rows, TM games linked or added, `match_coach` from the managers' names.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graph_load_tm.py
import csv, gzip, io, json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import tm


def write_csv(path, header, rows, gz=False):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    data = buf.getvalue().encode()
    path.write_bytes(gzip.compress(data) if gz else data)


def mk(tmp_path):
    db, h = tmp_path / "db" / ".cache", tmp_path / "history" / ".cache"
    (db / "tm").mkdir(parents=True)
    h.mkdir(parents=True)
    write_csv(db / "tm" / "player_profiles.csv", ["player_id", "player_name", "name_in_home_country", "date_of_birth", "place_of_birth", "citizenship", "height", "foot", "date_of_death"],
              [["5", "Omar A (1)", "عمر", "1991-10-01", "Al Ain", "United Arab Emirates  Bahrain", "1,82", "left", ""]])
    write_csv(db / "tm" / "player_performances.csv", ["player_id", "season_name", "competition_id", "competition_name", "team_id", "team_name", "nb_on_pitch", "goals", "assists",
              "yellow_cards", "second_yellow_cards", "direct_red_cards", "minutes_played", "goals_conceded", "clean_sheets"],
              [["5", "15/16", "UAE1", "UAE Pro League", "100", "Al Ain", "25", "10.0", "8", "2", "0", "0", "2100", "", "0"]])
    write_csv(db / "tm" / "player_injuries.csv", ["player_id", "season_name", "injury_reason", "from_date", "end_date", "days_missed", "games_missed"],
              [["5", "15/16", "Knee", "2016-01-01", "2016-02-01", "31", "4"]])
    (h / "tm_playermap.json").write_text(json.dumps({"5": "77"}))
    (h / "tm_clubmap.json").write_text(json.dumps({"100": 10, "200": 20}))
    write_csv(db / "tm_games.csv.gz", ["game_id", "competition_id", "season", "round", "date", "home_club_id", "away_club_id", "home_club_goals", "away_club_goals",
              "home_club_manager_name", "away_club_manager_name", "stadium", "attendance", "referee"],
              [["1", "UAE1", "2015", "1", "2016-01-10", "100", "200", "2", "1", "Zlatko D", "Coach B", "Hazza", "9000", "Ref"],
               ["2", "UAE1", "2015", "2", "2016-01-20", "200", "100", "0", "0", "Coach B", "Zlatko D", "X", "", ""]], gz=True)
    write_csv(db / "tm_game_events.csv.gz", ["game_event_id", "date", "game_id", "minute", "type", "club_id", "player_id", "description", "player_in_id", "player_assist_id"], [], gz=True)
    return Sources(str(tmp_path), s3=False)


def test_tm(tmp_path):
    S, G, reg = mk(tmp_path), Graph(str(tmp_path / "t.db")), Registry()
    pid = reg.mint("player", "fotmob", 77)
    G.put("player", {"pid": pid, "name": "Omar A"}, "fotmob")
    t10, t20 = reg.mint("team", "fotmob", 10), reg.mint("team", "fotmob", 20)
    G.put("match", {"mid": reg.mint("match", "fotmob", 1), "date": "2016-01-10T16:00:00Z", "home": t10, "away": t20, "hs": 2, "as_": 1}, "fotmob")
    out = tm.load(G, reg, S)
    assert reg.get("player", "tm", "5") == pid
    assert G.c.execute("select birthplace, nationality2, name_native, height from player where pid=?", (pid,)).fetchone() == ("Al Ain", "Bahrain", "عمر", 182)
    assert G.c.execute("select season, goals, minutes from player_season").fetchone() == ("2015/2016", 10, 2100)
    assert G.c.execute("select days, games from injury").fetchone() == (31, 4)
    assert out["games_linked"] == 1 and out["games_new"] == 1
    assert G.c.execute("select count(*) from match_coach").fetchone()[0] == 4
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_graph_load_tm.py -q`
Expected: FAIL, `ImportError: cannot import name 'tm'`

- [ ] **Step 3: Write the implementation**

`graph/load/tm.py`:
```python
"""Transfermarkt. salimt/football-datasets (db/.cache/tm/): bios, season × competition × club lines, injuries, for the
players db/tmdata.py and history/transfermarkt.py matched to FotMob (birth date + name rules). dcaribou games and events
(db/.cache/tm_games.csv.gz, 2012+): a game already in the graph becomes its xref, the rest are new matches; each side's
manager is recorded for the match (a name: a coach links to FotMob's only when the name and the club agree)."""
import csv, gzip, os, re, unicodedata
from graph.link import MatchIndex, twin


def fold(s):
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()).strip()


def rows(path):
    if not os.path.exists(path):
        return
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def season(s):
    """«15/16» -> «2015/2016», «2015» (dcaribou: the start year) -> «2015/2016»."""
    s = str(s or "").strip()
    m = re.fullmatch(r"(\d{2})/(\d{2})", s)
    if m:
        a = int(m.group(1))
        y = (1900 if a > 50 else 2000) + a
        return f"{y}/{y + 1}"
    return f"{s}/{int(s) + 1}" if s.isdigit() else (s or None)


def _i(v):
    try:
        return int(float(str(v).replace(",", ".").strip())) if str(v).strip() else None
    except ValueError:
        return None


def load(G, reg, S):
    n = {"players_linked": 0, "seasons": 0, "injuries": 0, "games_linked": 0, "games_new": 0, "coaches": 0}
    pmap = {str(k): str(v) for k, v in (S.read(os.path.join(S.hist, "tm_playermap.json")) or {}).items()}
    for fid, tmid in ((S.published("history/tm/index.json") or {}).get("players") or {}).items():
        pmap.setdefault(str(tmid), str(fid))
    for tmid, fid in sorted(pmap.items()):
        pid = reg.get("player", "fotmob", int(fid)) if fid.isdigit() else None
        if pid and reg.alias("player", "tm", tmid, pid):
            G.xref("player", pid, "tm", tmid, "birthdate+name")
            n["players_linked"] += 1
    cmap = {str(k): v for k, v in (S.read(os.path.join(S.hist, "tm_clubmap.json")) or {}).items()}
    for tmc, fid in sorted(cmap.items()):
        tid = reg.mint("team", "fotmob", int(fid))
        if reg.alias("team", "tm", tmc, tid):
            G.xref("team", tid, "tm", tmc, "transfers-clubmap")

    def team(tmc, name=None):
        tid = reg.get("team", "tm", str(tmc))
        if tid is None:
            tid = reg.mint("team", "tm", str(tmc))
            G.put("team", {"tid": tid, "name": name}, "tm")
            G.xref("team", tid, "tm", tmc, "tm-native")
        return tid

    for r in rows(os.path.join(S.db, "tm", "player_profiles.csv")):
        pid = reg.get("player", "tm", r["player_id"])
        if not pid:
            continue
        cit = [c.strip() for c in re.split(r"\s{2,}", r.get("citizenship") or "") if c.strip()]
        h = r.get("height") or ""
        G.put("player", {"pid": pid, "name_native": r.get("name_in_home_country") or None, "born": (r.get("date_of_birth") or "")[:10] or None,
                         "birthplace": r.get("place_of_birth") or None, "nationality2": cit[1] if len(cit) > 1 else None,
                         "height": _i(h.replace(",", "")) if h else None, "foot": r.get("foot") or None, "died": r.get("date_of_death") or None}, "tm")
    for r in rows(os.path.join(S.db, "tm", "player_performances.csv")):
        pid = reg.get("player", "tm", r["player_id"])
        if not pid:
            continue
        G.many("player_season", [{"pid": pid, "season": season(r.get("season_name")), "comp": r.get("competition_name") or r.get("competition_id"),
                                  "cid": reg.get("competition", "tm", r.get("competition_id")), "tid": team(r["team_id"], r.get("team_name")) if r.get("team_id") else None,
                                  "apps": _i(r.get("nb_on_pitch")), "minutes": _i(r.get("minutes_played")), "goals": _i(r.get("goals")), "assists": _i(r.get("assists")),
                                  "yellow": _i(r.get("yellow_cards")), "red": (_i(r.get("second_yellow_cards")) or 0) + (_i(r.get("direct_red_cards")) or 0),
                                  "clean_sheets": _i(r.get("clean_sheets")), "conceded": _i(r.get("goals_conceded"))}], "tm")
        n["seasons"] += 1
    for r in rows(os.path.join(S.db, "tm", "player_injuries.csv")):
        pid = reg.get("player", "tm", r["player_id"])
        if pid:
            G.many("injury", [{"pid": pid, "season": season(r.get("season_name")), "kind": r.get("injury_reason"), "start": r.get("from_date") or None,
                               "end": r.get("end_date") or None, "days": _i(r.get("days_missed")), "games": _i(r.get("games_missed"))}], "tm")
            n["injuries"] += 1
    coach_by = {}
    for kid, name in G.c.execute("SELECT kid, name FROM coach"):
        coach_by.setdefault(fold(name), []).append(kid)
    idx = MatchIndex(G)
    for r in rows(os.path.join(S.db, "tm_games.csv.gz")):
        if not r.get("home_club_goals") or not r.get("date"):
            continue
        th, ta, hs, as_ = team(r["home_club_id"], r.get("home_club_name")), team(r["away_club_id"], r.get("away_club_name")), _i(r["home_club_goals"]), _i(r["away_club_goals"])
        mid = twin(G, idx, r["date"], th, ta, hs, as_, "tm")
        if mid:
            reg.alias("match", "tm", r["game_id"], mid)
            G.xref("match", mid, "tm", r["game_id"], "date+teams")
            n["games_linked"] += 1
        else:
            cid = reg.get("competition", "tm", r["competition_id"]) or reg.mint("competition", "tm", r["competition_id"])
            G.put("competition", {"cid": cid, "name": r["competition_id"]}, "tm")
            eid = reg.get("edition", "tm", f"{r['competition_id']}|{r['season']}") or reg.mint("edition", "tm", f"{r['competition_id']}|{r['season']}")
            G.put("edition", {"eid": eid, "cid": cid, "season": season(r["season"])}, "tm")
            mid = reg.mint("match", "tm", r["game_id"])
            G.put("match", {"mid": mid, "eid": eid, "round": r.get("round"), "date": r["date"], "home": th, "away": ta, "hs": hs, "as_": as_,
                            "status": "finished", "attendance": _i(r.get("attendance"))}, "tm")
            G.xref("match", mid, "tm", r["game_id"], "tm-native")
            idx.add(mid, r["date"], th, ta)
            n["games_new"] += 1
        for side, col in (("h", "home_club_manager_name"), ("a", "away_club_manager_name")):
            nm = (r.get(col) or "").strip()
            if not nm:
                continue
            cands = coach_by.get(fold(nm), [])
            kid = cands[0] if len(cands) == 1 else (reg.get("coach", "tm-name", fold(nm)) or reg.mint("coach", "tm-name", fold(nm)))
            if not cands or len(cands) > 1:
                G.put("coach", {"kid": kid, "name": nm}, "tm")
            G.c.execute("INSERT OR IGNORE INTO match_coach VALUES(?,?,?,?)", (mid, side, kid, "tm"))
            n["coaches"] += 1
    return n
```

A coach row made from a Transfermarkt name alone is a separate coach (`coach|tm-name|<folded name>`). Phase 5 links these to FotMob coaches using club and dates. Phase 1 links one only when exactly one FotMob coach has that folded name.

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m pytest tests/test_graph_load_tm.py -q`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git commit -m "graph: Transfermarkt — bios, season lines, injuries, 2012+ games with their managers" -- graph/load/tm.py tests/test_graph_load_tm.py
```

---

### Task 10: Internationals since 1872 and transfers

**Files:**
- Create: `graph/fetch.py`, `graph/load/martj42.py`, `graph/load/transfers.py`
- Test: `tests/test_graph_load_intl.py`

**Interfaces:**
- Consumes: `compute.national.dataset_name(fotmob_name, known)`, `MatchIndex`, `twin`; `history/.cache/transfers.json` (TM: `players {tm id: [[date, season, from, from_fotmob, to, to_fotmob, fee, mv]]}`); `Sources.published("transfers/all.json")` (FotMob: `moves [[date, fotmob pid, name, from id, from name, to id, to name, fee, type, …]]`).
- Produces: `fetch.martj42(S) -> path` (download when older than 7 days); `martj42.load(G, reg, S)`; `transfers.load(G, reg, S)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_graph_load_intl.py
import json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import martj42, transfers


def test_martj42_links_and_adds(tmp_path):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    (db / "martj42_results.csv").write_text("date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"
                                            "1972-03-17,United Arab Emirates,Qatar,1,0,Friendly,Dubai,United Arab Emirates,FALSE\n"
                                            "2019-01-05,United Arab Emirates,Bahrain,1,1,AFC Asian Cup,Abu Dhabi,United Arab Emirates,FALSE\n", encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    uae, bah = reg.mint("team", "fotmob", 5789), reg.mint("team", "fotmob", 5794)
    G.put("team", {"tid": uae, "name": "United Arab Emirates", "kind": "national"}, "fotmob")
    G.put("team", {"tid": bah, "name": "Bahrain", "kind": "national"}, "fotmob")
    G.put("match", {"mid": 1, "date": "2019-01-05T16:00:00Z", "home": uae, "away": bah, "hs": 1, "as_": 1}, "fotmob")
    out = martj42.load(G, reg, Sources(str(tmp_path), s3=False))
    assert out == {"rows": 2, "linked": 1, "new": 1, "teams_linked": 2}
    assert G.c.execute("select count(*) from match where src='martj42'").fetchone()[0] == 1


def test_transfers(tmp_path):
    h = tmp_path / "history" / ".cache"
    h.mkdir(parents=True)
    (h / "transfers.json").write_text(json.dumps({"players": {"5": [["2019-07-01", "19/20", "Al Ain", 10, "Al Hilal", None, 5000000, 9000000]]}}))
    m = tmp_path / "mirror" / "transfers"
    m.mkdir(parents=True)
    (m / "all.json").write_text(json.dumps({"moves": [["2026-11-16", 77, "Omar A", 10, "العين", 2, "Free agent", None, "free", 0, None, "FW"]]}), encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    pid = reg.mint("player", "fotmob", 77)
    reg.alias("player", "tm", "5", pid)
    reg.mint("team", "fotmob", 10)
    out = transfers.load(G, reg, Sources(str(tmp_path), mirror=str(tmp_path / "mirror"), s3=False))
    assert out == {"tm": 1, "fotmob": 1}
    assert G.c.execute("select fee, season from transfer where src='tm'").fetchone() == (5000000, "2019/2020")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_graph_load_intl.py -q`
Expected: FAIL, `ImportError: cannot import name 'martj42'`

- [ ] **Step 3: Write the implementation**

`graph/fetch.py`:
```python
"""The graph's one network step, before the loaders: martj42's internationals (CC0), weekly."""
import os, time, urllib.request

MARTJ42 = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"


def martj42(S, max_age_days=7):
    p = os.path.join(S.db, "martj42_results.csv")
    if not os.path.exists(p) or time.time() - os.path.getmtime(p) > max_age_days * 86400:
        data = urllib.request.urlopen(urllib.request.Request(MARTJ42, headers={"User-Agent": "elyoxe-tifo/0.1"}), timeout=120).read()
        tmp = p + ".tmp"
        open(tmp, "wb").write(data)
        os.replace(tmp, p)
    return p
```

`graph/load/martj42.py`:
```python
"""Every men's international since 1872 (martj42/international_results). A national team links when FotMob's name maps to
the dataset's (compute/national.py's aliases); a result FotMob already has becomes its xref, the rest are new matches in
a competition per tournament name."""
import csv, os
from graph.link import MatchIndex, twin


def load(G, reg, S):
    from compute.national import dataset_name
    p = os.path.join(S.db, "martj42_results.csv")
    if not os.path.exists(p):
        return {"skipped": "no martj42_results.csv"}
    data = list(csv.DictReader(open(p, encoding="utf-8", newline="")))
    known = {r["home_team"] for r in data} | {r["away_team"] for r in data}
    tl = 0
    for tid, name in G.c.execute("SELECT tid, name FROM team WHERE kind='national' ORDER BY tid").fetchall():
        dn = dataset_name(name, known)
        if dn and reg.alias("team", "martj42", dn, tid):
            G.xref("team", tid, "martj42", dn, "fotmob-name-alias")
            tl += 1
    idx = MatchIndex(G)
    linked = new = 0
    for r in data:
        try:
            hs, as_ = int(r["home_score"]), int(r["away_score"])
        except (ValueError, KeyError):
            continue
        h, a = (reg.get("team", "martj42", r["home_team"]) or reg.mint("team", "martj42", r["home_team"]),
                reg.get("team", "martj42", r["away_team"]) or reg.mint("team", "martj42", r["away_team"]))
        for tid, nm in ((h, r["home_team"]), (a, r["away_team"])):
            G.put("team", {"tid": tid, "name": nm, "kind": "national"}, "martj42")
        key = f"{r['date']}|{r['home_team']}|{r['away_team']}"
        mid = twin(G, idx, r["date"], h, a, hs, as_, "martj42")
        if mid:
            G.xref("match", mid, "martj42", key, "date+teams")
            linked += 1
            continue
        cid = reg.get("competition", "martj42", r["tournament"]) or reg.mint("competition", "martj42", r["tournament"])
        G.put("competition", {"cid": cid, "name": r["tournament"], "scope": "international"}, "martj42")
        y = r["date"][:4]
        eid = reg.get("edition", "martj42", f"{r['tournament']}|{y}") or reg.mint("edition", "martj42", f"{r['tournament']}|{y}")
        G.put("edition", {"eid": eid, "cid": cid, "season": y}, "martj42")
        mid = reg.mint("match", "martj42", key)
        G.put("match", {"mid": mid, "eid": eid, "date": r["date"], "home": h, "away": a, "hs": hs, "as_": as_, "status": "finished"}, "martj42")
        G.xref("match", mid, "martj42", key, "martj42-native")
        idx.add(mid, r["date"], h, a)
        new += 1
    return {"rows": len(data), "linked": linked, "new": new, "teams_linked": tl}
```

`graph/load/transfers.py`:
```python
"""Moves: Transfermarkt's full histories (history/.cache/transfers.json, dcaribou) for the players matched to FotMob, and
FotMob's moves of this season (v1/transfers/all.json). A club is linked when the source carries its FotMob id; else the
move keeps the source's club name only in the team table as a new team (one per source name)."""
import os
from graph.load.tm import season


def load(G, reg, S):
    n = {"tm": 0, "fotmob": 0}

    def club(fid, name, src):
        if fid:
            return reg.mint("team", "fotmob", int(fid))
        if not name:
            return None
        tid = reg.get("team", f"{src}-name", name) or reg.mint("team", f"{src}-name", name)
        G.put("team", {"tid": tid, "name": name}, src)
        return tid

    for tmid, moves in sorted(((S.read(os.path.join(S.hist, "transfers.json")) or {}).get("players") or {}).items()):
        pid = reg.get("player", "tm", str(tmid))
        if not pid:
            continue
        for d, sn, fr, fr_id, to, to_id, fee, mv, *_ in moves:
            G.c.execute("INSERT OR IGNORE INTO transfer VALUES(?,?,?,?,?,?,?,?)",
                        (pid, club(fr_id, fr, "tm"), club(to_id, to, "tm"), d, season(sn), fee, "free" if fee == 0 else None, "tm"))
            n["tm"] += 1
    for m in (S.published("transfers/all.json") or {}).get("moves") or []:
        d, fpid, name, fr_id, fr, to_id, to, fee, typ = m[:9]
        pid = reg.mint("player", "fotmob", int(fpid))
        G.put("player", {"pid": pid, "name": name}, "fotmob")
        y, mo = int(d[:4]), int(d[5:7])
        G.c.execute("INSERT OR IGNORE INTO transfer VALUES(?,?,?,?,?,?,?,?)",
                    (pid, club(fr_id if fr_id not in (2, None) else None, fr, "fotmob"), club(to_id if to_id not in (2, None) else None, to, "fotmob"),
                     d, f"{y}/{y + 1}" if mo >= 7 else f"{y - 1}/{y}", fee, typ, "fotmob"))
        n["fotmob"] += 1
    return n
```

(FotMob's id `2` is its «Free agent» pseudo-club and is stored as no club.)

- [ ] **Step 4: Run them to verify they pass**

Run: `python -m pytest tests/test_graph_load_intl.py -q`
Expected: 2 passed. If `dataset_name` needs a different `known` shape, read `compute/national.py:68` and pass what it expects.

- [ ] **Step 5: Commit**

```bash
git commit -m "graph: internationals since 1872 (martj42) and transfers (Transfermarkt history + FotMob this season)" -- graph/fetch.py graph/load/martj42.py graph/load/transfers.py tests/test_graph_load_intl.py
```

---

### Task 11: Coverage report, build, stage and workflow

**Files:**
- Create: `graph/coverage.py`, `graph/build.py`
- Modify: `db/refresh.py` (STAGES: add `("graph", "graph.build", ["--upload"], 1)` right before `("audit", …)`), `.github/workflows/tifo-database.yml` (add `graph/.cache` to both cache `path:` blocks), `.gitignore` (add `graph/.cache/`)
- Test: `tests/test_graph_build.py`

**Interfaces:**
- Consumes: every loader, `Registry`, `Graph`, `Sources`, `fetch.martj42`.
- Produces: `coverage.compute(G) -> dict`, `coverage.markdown(cov, date) -> str`; `build.run(S, out_dir, prev_registry_path, upload=False, loaders=None) -> dict` (the run record) and the CLI `python -m graph.build [--upload] [--out DIR] [--only a,b]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_graph_build.py
import gzip, json, os
from graph import build
from graph.src import Sources
from tests.test_graph_rows import REC


def caches(tmp_path):
    mx = tmp_path / "db" / ".cache" / "fm" / "mx"
    mx.mkdir(parents=True)
    (mx / "900.json").write_bytes(gzip.compress(json.dumps(REC).encode()))
    return Sources(str(tmp_path), mirror=str(tmp_path / "mirror"), s3=False)


def test_build_twice_same_ids(tmp_path):
    S = caches(tmp_path)
    r1 = build.run(S, str(tmp_path / "o1"), str(tmp_path / "reg.json.gz"), fetch=False)
    b1 = (tmp_path / "reg.json.gz").read_bytes()
    r2 = build.run(S, str(tmp_path / "o2"), str(tmp_path / "reg.json.gz"), fetch=False)
    assert (tmp_path / "reg.json.gz").read_bytes() == b1
    assert r1["counts"]["match"] == r2["counts"]["match"] == 1 and r2["moved"] == 0


def test_missing_cache_skips_loader(tmp_path):
    S = caches(tmp_path)
    r = build.run(S, str(tmp_path / "o"), str(tmp_path / "reg.json.gz"), fetch=False)
    assert r["loaders"]["fotmob_matches"]["ok"] is True
    assert r["loaders"]["schochastics"]["ok"] is True and "skipped" in r["loaders"]["schochastics"]["out"]
    assert os.path.exists(tmp_path / "o" / "coverage.json")


def test_fotmob_failure_fails_build(tmp_path, monkeypatch):
    S = caches(tmp_path)
    from graph.load import fotmob_matches
    monkeypatch.setattr(fotmob_matches, "load", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r = build.run(S, str(tmp_path / "o"), str(tmp_path / "reg.json.gz"), fetch=False)
    assert r["ok"] is False and not os.path.exists(tmp_path / "reg.json.gz")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_graph_build.py -q`
Expected: FAIL, `ImportError: cannot import name 'build'`

- [ ] **Step 3: Write the implementation**

`graph/coverage.py`:
```python
"""What the graph holds, per competition × edition and per entity type (spec §3.5): the report phases 2-5 start from."""
TYPES = ("team", "player", "coach", "referee", "stadium", "competition", "edition", "match")


def compute(G):
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    counts = {t: q(f"SELECT count(*) FROM {t}")[0][0] for t in TYPES + ("appearance", "event", "standing", "honour", "transfer", "spell", "player_season", "injury", "match_coach")}
    by_src = {t: dict(q(f"SELECT src, count(*) FROM {t} GROUP BY src")) for t in TYPES}
    linked = {t: dict(q("SELECT source, count(DISTINCT tifo_id) FROM xref WHERE type=? GROUP BY source", (t,))) for t in TYPES}
    arabic = {t: q(f"SELECT count(*) FROM {t} WHERE name_ar IS NOT NULL")[0][0] for t in ("team", "player", "coach", "referee", "competition")}
    born = q("SELECT count(*) FROM player WHERE born IS NOT NULL")[0][0]
    editions = q("""SELECT c.cid, coalesce(c.name_ar, c.name), e.season, count(m.mid),
          sum(m.hs IS NOT NULL),
          sum(EXISTS(SELECT 1 FROM appearance a WHERE a.mid=m.mid)),
          sum(EXISTS(SELECT 1 FROM event v WHERE v.mid=m.mid)),
          sum(EXISTS(SELECT 1 FROM appearance a WHERE a.mid=m.mid AND a.stats IS NOT NULL)),
          sum(EXISTS(SELECT 1 FROM appearance a WHERE a.mid=m.mid AND a.rating IS NOT NULL)),
          EXISTS(SELECT 1 FROM honour h WHERE h.eid=e.eid AND h.kind='champion'),
          EXISTS(SELECT 1 FROM honour h WHERE h.eid=e.eid AND h.kind='runner_up'),
          EXISTS(SELECT 1 FROM standing s WHERE s.eid=e.eid)
        FROM edition e JOIN competition c ON c.cid=e.cid LEFT JOIN match m ON m.eid=e.eid
        GROUP BY e.eid ORDER BY c.cid, e.season""")
    conflicts = q("SELECT type, field, kept_src, other_src, count(*) FROM conflict GROUP BY 1,2,3,4 ORDER BY 5 DESC")
    return {"counts": counts, "by_src": by_src, "linked": linked, "arabic": arabic, "player_born": born,
            "editions": [dict(zip(("cid", "name", "season", "matches", "scores", "lineups", "events", "stats", "ratings", "champion", "runner_up", "table"), r)) for r in editions],
            "conflicts": [dict(zip(("type", "field", "kept_src", "other_src", "n"), r)) for r in conflicts]}


def markdown(cov, day, run=None):
    c = cov["counts"]
    out = [f"# Tifo graph coverage — {day}", ""]
    if run:
        out += [f"Built in {run.get('secs')} s. Loaders: " + ", ".join(f"{k} {'ok' if v['ok'] else 'FAILED'} ({v['secs']} s)" for k, v in run["loaders"].items()), ""]
    out += ["## Totals", "", "| table | rows | by source |", "|---|---|---|"]
    for t, n in c.items():
        out.append(f"| {t} | {n:,} | {', '.join(f'{s} {k:,}' for s, k in sorted(cov['by_src'].get(t, {}).items()))} |")
    out += ["", "## Links between sources (distinct Tifo ids with a row in xref)", "", "| type | " + " | ".join(["source", "ids"]) + " |", "|---|---|---|"]
    for t, d in cov["linked"].items():
        for s, k in sorted(d.items()):
            out.append(f"| {t} | {s} | {k:,} |")
    out += ["", f"Arabic names: " + ", ".join(f"{t} {n:,} of {c[t]:,}" for t, n in cov["arabic"].items()) + f". Players with a birth date: {cov['player_born']:,} of {c['player']:,}.", ""]
    out += ["## Editions", "", "| competition | season | matches | scores | lineups | events | player stats | ratings | champion | runner-up | table |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in cov["editions"]:
        yn = lambda v: "yes" if v else "—"
        out.append(f"| {e['name']} ({e['cid']}) | {e['season']} | {e['matches']} | {e['scores'] or 0} | {e['lineups'] or 0} | {e['events'] or 0} | {e['stats'] or 0} | {e['ratings'] or 0} | {yn(e['champion'])} | {yn(e['runner_up'])} | {yn(e['table'])} |")
    out += ["", "## Conflicts", "", "| type | field | kept | other | n |", "|---|---|---|---|---|"]
    out += [f"| {x['type']} | {x['field']} | {x['kept_src']} | {x['other_src']} | {x['n']:,} |" for x in cov["conflicts"]]
    return "\n".join(out) + "\n"
```

`graph/build.py`:
```python
"""Build tifo.db from the caches (spec §2, §4): loaders in precedence order, the registry checked for renumbering, the
coverage report written, then (--upload) published: the registry to S3 state, tifo.db.gz to S3 graph/ (private), the
coverage to v1/graph/coverage.json.

    python -m graph.build [--upload] [--out DIR] [--only fotmob_matches,names] [--no-fetch]
"""
import argparse, gzip, importlib, json, os, shutil, sys, time, traceback
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from graph import coverage, fetch  # noqa: E402
from graph.db import Graph  # noqa: E402
from graph.ids import Registry  # noqa: E402
from graph.src import Sources  # noqa: E402

ORDER = ["fotmob_matches", "fotmob_profiles", "names", "s365", "tm", "rsssf", "schochastics", "martj42", "transfers"]
REQUIRED = {"fotmob_matches"}
CACHE = os.path.join(HERE, ".cache")
REG_STATE = "graph/registry.json.gz"


def run(S, out_dir, reg_path, upload=False, loaders=None, fetch=True):
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    old = Registry.load(reg_path)
    reg = Registry(json.loads(json.dumps(old.to_json())))
    db_path = os.path.join(out_dir, "tifo.db")
    G = Graph(db_path)
    if fetch:
        try:
            fetch_mod().martj42(S)
        except Exception as e:
            print(f"martj42 fetch: {e}", flush=True)
    rec = {"started": datetime.now(timezone.utc).isoformat()[:19] + "Z", "loaders": {}, "ok": True}
    for name in loaders or ORDER:
        t = time.time()
        try:
            mod = importlib.import_module(f"graph.load.{name}")
            out = mod.load(G, reg, S)
            rec["loaders"][name] = {"ok": True, "secs": round(time.time() - t), "out": out}
        except Exception as e:
            traceback.print_exc()
            rec["loaders"][name] = {"ok": False, "secs": round(time.time() - t), "out": f"{type(e).__name__}: {str(e)[:300]}"}
            if name in REQUIRED:
                rec["ok"] = False
        G.c.commit()
        print(f"{name}: {rec['loaders'][name]}", flush=True)
    moved = reg.moved(old)
    rec["moved"] = len(moved)
    if moved:
        rec["ok"] = False
        rec["moved_sample"] = moved[:20]
    cov = coverage.compute(G)
    rec["counts"] = cov["counts"]
    G.meta("build", {k: v for k, v in rec.items() if k != "loaders"})
    G.close()
    rec["secs"] = round(time.time() - t0)
    day = rec["started"][:10]
    json.dump({"generated": rec["started"], **cov}, open(os.path.join(out_dir, "coverage.json"), "w", encoding="utf-8", newline="\n"), ensure_ascii=False)
    open(os.path.join(out_dir, "coverage.md"), "w", encoding="utf-8", newline="\n").write(coverage.markdown(cov, day, rec))
    if rec["ok"]:
        reg.save(reg_path)
        if upload:
            publish(S, out_dir, reg_path, rec, cov)
    return rec


def fetch_mod():
    return fetch


def publish(S, out_dir, reg_path, rec, cov):
    st = S.store()
    prev = st.get_state("graph/last.json") or {}
    if prev.get("matches") and cov["counts"]["match"] < 0.95 * prev["matches"]:
        print(f"not published: {cov['counts']['match']} matches < 95% of the last build's {prev['matches']}", flush=True)
        return
    st.put_state(REG_STATE, json.loads(gzip.decompress(open(reg_path, "rb").read())))
    gz = os.path.join(out_dir, "tifo.db.gz")
    with open(os.path.join(out_dir, "tifo.db"), "rb") as f, gzip.open(gz, "wb", compresslevel=6) as z:
        shutil.copyfileobj(f, z, 16 << 20)
    st.b.client.upload_file(gz, st.b.bucket, "graph/tifo.db.gz") if hasattr(st.b, "client") else None
    st.put_json("graph/coverage.json", {"generated": rec["started"], "counts": cov["counts"], "linked": cov["linked"], "arabic": cov["arabic"],
                                        "editions": cov["editions"]}, cache="static")
    st.put_state("graph/last.json", {"at": rec["started"], "matches": cov["counts"]["match"], "secs": rec["secs"]})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--out", default=CACHE)
    ap.add_argument("--only", default="")
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args(argv)
    S = Sources()
    reg_path = os.path.join(CACHE, "registry.json.gz")
    os.makedirs(CACHE, exist_ok=True)
    if not os.path.exists(reg_path) and a.upload:
        d = S.store().get_state(REG_STATE)
        if d:
            Registry(d).save(reg_path)
    rec = run(S, a.out, reg_path, upload=a.upload, loaders=[x for x in a.only.split(",") if x] or None, fetch=not a.no_fetch)
    day = rec["started"][:10]
    if a.out == CACHE:
        shutil.copyfile(os.path.join(a.out, "coverage.md"), os.path.join(os.path.dirname(HERE), "docs", f"GRAPH-COVERAGE-{day}.md"))
    print(json.dumps({k: v for k, v in rec.items() if k != "loaders"}, ensure_ascii=False))
    return 0 if rec["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
```

Check `S3Backend` in `store.py` for the client attribute name (`self.client` or `self.s3`) before relying on `st.b.client`. Use whatever attribute holds the boto3 client.

Modify `db/refresh.py` STAGES, inserting before the `audit` line:
```python
    ("graph", "graph.build", ["--upload"], 1),                        # the connected database (docs/superpowers/specs/2026-11-19-tifo-graph-design.md): tifo.db + coverage
```

Modify `.github/workflows/tifo-database.yml`: in both `path: |` blocks add the line `graph/.cache` after `history/.cache`.

Add to `.gitignore`: `graph/.cache/`

- [ ] **Step 4: Run all graph tests**

Run: `python -m pytest tests/test_graph_*.py -q`
Expected: all pass (about 30)

- [ ] **Step 5: Commit**

```bash
git add graph/coverage.py graph/build.py tests/test_graph_build.py
git commit -m "graph: build (precedence order, renumbering guard, 95% publish guard), coverage report, daily stage" -- graph/coverage.py graph/build.py tests/test_graph_build.py db/refresh.py .github/workflows/tifo-database.yml .gitignore
```

---

### Task 12: First real build and the coverage report

**Files:**
- Create: `docs/GRAPH-COVERAGE-<date>.md` (written by the build)
- Modify: `docs/superpowers/specs/2026-11-19-tifo-graph-design.md` (phase 1 status line)

- [ ] **Step 1: Build on the laptop's caches, FotMob first**

Run: `python -m graph.build --only fotmob_matches,fotmob_profiles,names --no-fetch`
Expected: exit 0, about 92k matches. Write down the time it took.

- [ ] **Step 2: Full build**

Run: `python -m graph.build`
Expected: exit 0. Every loader `ok`. Write down the counts and the time.

- [ ] **Step 3: Read samples by hand**

```bash
python -m graph.q "select x.source, t.name, t.name_ar from xref x join team t on t.tid=x.tifo_id where x.type='team' and x.source='sch' and x.method='vote' order by random() limit 20"
python -m graph.q "select m.date, h.name, a.name, m.hs, m.as_, group_concat(x.source) from match m join team h on h.tid=m.home join team a on a.tid=m.away join xref x on x.type='match' and x.tifo_id=m.mid group by m.mid having count(*)>2 order by random() limit 20"
python -m graph.q "select * from conflict order by random() limit 20"
python -m graph.q "select c.name, count(*) from match m join edition e on e.eid=m.eid join competition c on c.cid=e.cid where c.name like '%Pro League%' group by c.cid"
```
Expected: the linked pairs are the same club or the same game. Any wrong link is a bug in its loader: fix it (with a test) before going on.

- [ ] **Step 4: The second build keeps every id**

Run: `python -m graph.build --no-fetch`
Expected: `"moved": 0`, registry bytes unchanged.

- [ ] **Step 5: Commit the report and update the spec status**

Add under the spec's title: `**Status:** phase 1 built <date>: <n> matches, <n> players, … (docs/GRAPH-COVERAGE-<date>.md).`

```bash
git add docs/GRAPH-COVERAGE-*.md
git commit -m "graph: first build — coverage report" -- docs/GRAPH-COVERAGE-*.md docs/superpowers/specs/2026-11-19-tifo-graph-design.md
git push origin HEAD
```

- [ ] **Step 6: First run on GitHub Actions**

Run: `gh workflow run tifo-database.yml -R MrDMX7/elyoxe-football -f force=graph`, then watch it with `gh run watch`.
Expected: the `graph` stage gets `rc=0` with its time in the log, `s3://…/graph/tifo.db.gz` exists, and `v1/graph/coverage.json` is served.
