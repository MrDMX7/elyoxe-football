"""The graph database (spec §3.1): a fresh SQLite file each build. put() applies the source precedence: the first
source to state a field keeps it, a later one fills only empty fields, and a disagreement on a checked field is logged."""
import json, os, sqlite3
from collections import Counter

SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
SRC_RANK = {"fotmob": 0, "names": 0, "s365": 1, "uaefa": 1, "espn": 2, "uefa": 2, "fifa": 2, "tm": 2, "fjelstul": 3, "rsssf": 3, "sch": 4, "martj42": 5, "wikidata": 6}
KEYS = {"team": "tid", "player": "pid", "coach": "kid", "referee": "rid", "stadium": "sid", "competition": "cid", "edition": "eid", "match": "mid"}
# where each entity's id is referenced (remap after a merge)
REFS = {"team": [("match", "home"), ("match", "away"), ("appearance", "tid"), ("event", "tid"), ("standing", "tid"), ("honour", "tid"),
                 ("transfer", "from_tid"), ("transfer", "to_tid"), ("spell", "tid"), ("player_season", "tid"), ("match_award", "tid")],
        "player": [("appearance", "pid"), ("event", "pid"), ("event", "pid2"), ("honour", "pid"), ("transfer", "pid"), ("spell", "pid"),
                   ("player_season", "pid"), ("injury", "pid"), ("coach", "pid"), ("intl_record", "pid"), ("match_award", "pid")],
        "coach": [("match_coach", "kid"), ("honour", "kid")], "referee": [("match", "rid")], "stadium": [("match", "sid"), ("team", "sid")],
        "competition": [("edition", "cid"), ("player_season", "cid")], "edition": [("match", "eid"), ("standing", "eid"), ("honour", "eid")],
        "match": [("appearance", "mid"), ("event", "mid"), ("match_coach", "mid"), ("match_award", "mid")]}
# table -> [(column, entity type)]: the columns of a row written after a merge that may name a folded record
COLS_OF = {}
for _t, _refs in REFS.items():
    for _table, _col in _refs:
        COLS_OF.setdefault(_table, []).append((_col, _t))
for _t, _k in KEYS.items():
    COLS_OF.setdefault(_t, []).append((_k, _t))
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
        self.merged = {}                          # {type: {drop: keep}}: every remap, for the pages that forward

    def _last(self, t, x):
        m = self.merged.get(t)
        n = 0
        while m and x in m and n < 50:
            x, n = m[x], n + 1
        return x

    def _kept(self, table, row):
        """a row written after a merge names the kept record, never the folded one (24 Nov 2026: official_motm put back a
        second, empty Thierry Henry from his Wikidata item, which the registry still gives his folded id)"""
        if not self.merged:
            return row
        out = None
        for col, t in COLS_OF.get(table, ()):
            v = row.get(col)
            # a match folded into its twin keeps its late rows apart: the kept one has its own goals, never a second copy
            if v is not None and t != "match" and t in self.merged and v in self.merged[t]:
                out = dict(row) if out is None else out
                out[col] = self._last(t, v)
        return out or row

    def put(self, table, row, src):
        k = KEYS[table]
        row = self._kept(table, row)
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
        if self.merged:
            rows = [self._kept(table, r) for r in rows]
        cols = [c for c in self.cols[table] if c != "src"]
        self.c.executemany(f"INSERT OR IGNORE INTO {table}({','.join(cols + ['src'])}) VALUES({','.join('?' * (len(cols) + 1))})",
                           [[r.get(c) for c in cols] + [src] for r in rows])
        self.stats[f"{table}:{src}"] += len(rows)

    def xref(self, t, tifo_id, source, source_id, method, conf=1.0):
        tifo_id = self._last(t, tifo_id) if self.merged else tifo_id
        self.c.execute("INSERT OR REPLACE INTO xref VALUES(?,?,?,?,?,?)", (t, tifo_id, source, str(source_id), method, conf))

    def conflict(self, t, tifo_id, field, kept, kept_src, other, other_src):
        self.c.execute("INSERT INTO conflict VALUES(?,?,?,?,?,?,?)", (t, tifo_id, field, str(kept), kept_src, str(other), other_src))

    def meta(self, k, v):
        self.c.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, json.dumps(v, ensure_ascii=False)))

    def remap(self, t, drop, keep):
        """Entity `drop` was merged into `keep`: its row fills keep's empty fields (or becomes keep's row), and every
        reference moves; a link row that would duplicate one of keep's is dropped."""
        k = KEYS[t]
        row = self.c.execute(f"SELECT * FROM {t} WHERE {k}=?", (drop,)).fetchone()
        if row:
            r = dict(zip(self.cols[t], row))
            src = r.pop("src")
            r.pop("filled", None)
            r[k] = keep
            self.put(t, r, src)
            self.c.execute(f"DELETE FROM {t} WHERE {k}=?", (drop,))
        for table, col in REFS.get(t, ()):
            self.c.execute(f"UPDATE OR IGNORE {table} SET {col}=? WHERE {col}=?", (keep, drop))
            self.c.execute(f"DELETE FROM {table} WHERE {col}=?", (drop,))
        self.c.execute("UPDATE OR IGNORE xref SET tifo_id=? WHERE type=? AND tifo_id=?", (keep, t, drop))
        self.c.execute("DELETE FROM xref WHERE type=? AND tifo_id=?", (t, drop))
        self.merged.setdefault(t, {})[drop] = keep

    def merges(self):
        """{type: {drop: the record it ended in}}: a record folded into one later folded again forwards to the last
        (tools/archive_job.py writes a forward page where a folded record had one)"""
        out = {}
        for t, m in self.merged.items():
            def last(x, seen=0):
                while x in m and seen < 50:
                    x, seen = m[x], seen + 1
                return x
            out[t] = {d: last(k) for d, k in m.items()}
        return out

    def remap_many(self, t, pairs):
        """remap for many (drop, keep) pairs at once: each referencing table is read once for all of them (a loop of remap
        reads the unindexed ones, event.pid2 and transfer among them, once a pair). No keep may itself be a drop."""
        pairs = list(pairs)
        if not pairs:
            return
        k = KEYS[t]
        for drop, keep in pairs:
            row = self.c.execute(f"SELECT * FROM {t} WHERE {k}=?", (drop,)).fetchone()
            if row:
                r = dict(zip(self.cols[t], row))
                src = r.pop("src")
                r.pop("filled", None)
                r[k] = keep
                self.put(t, r, src)
        self.c.execute("CREATE TEMP TABLE remap_m(d INTEGER PRIMARY KEY, k INTEGER NOT NULL)")
        self.c.executemany("INSERT INTO remap_m VALUES(?, ?)", pairs)
        self.c.execute(f"DELETE FROM {t} WHERE {k} IN (SELECT d FROM remap_m)")
        for table, col in REFS.get(t, ()):
            self.c.execute(f"UPDATE OR IGNORE {table} SET {col}=(SELECT k FROM remap_m WHERE d={table}.{col}) WHERE {col} IN (SELECT d FROM remap_m)")
            self.c.execute(f"DELETE FROM {table} WHERE {col} IN (SELECT d FROM remap_m)")
        self.c.execute("UPDATE OR IGNORE xref SET tifo_id=(SELECT k FROM remap_m WHERE d=xref.tifo_id) WHERE type=? AND tifo_id IN (SELECT d FROM remap_m)", (t,))
        self.c.execute("DELETE FROM xref WHERE type=? AND tifo_id IN (SELECT d FROM remap_m)", (t,))
        self.merged.setdefault(t, {}).update(pairs)
        self.c.execute("DROP TABLE remap_m")

    def close(self):
        self.c.commit()
        self.c.close()
