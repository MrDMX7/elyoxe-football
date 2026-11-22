"""The graph database (spec §3.1): a fresh SQLite file each build. put() applies the source precedence: the first
source to state a field keeps it, a later one fills only empty fields, and a disagreement on a checked field is logged."""
import json, os, sqlite3
from collections import Counter

SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
SRC_RANK = {"fotmob": 0, "names": 0, "s365": 1, "uaefa": 1, "espn": 2, "tm": 2, "fjelstul": 3, "rsssf": 3, "sch": 4, "martj42": 5, "wikidata": 6}
KEYS = {"team": "tid", "player": "pid", "coach": "kid", "referee": "rid", "stadium": "sid", "competition": "cid", "edition": "eid", "match": "mid"}
# where each entity's id is referenced (remap after a merge)
REFS = {"team": [("match", "home"), ("match", "away"), ("appearance", "tid"), ("event", "tid"), ("standing", "tid"), ("honour", "tid"),
                 ("transfer", "from_tid"), ("transfer", "to_tid"), ("spell", "tid"), ("player_season", "tid")],
        "player": [("appearance", "pid"), ("event", "pid"), ("event", "pid2"), ("honour", "pid"), ("transfer", "pid"), ("spell", "pid"),
                   ("player_season", "pid"), ("injury", "pid"), ("coach", "pid"), ("intl_record", "pid")],
        "coach": [("match_coach", "kid"), ("honour", "kid")], "referee": [("match", "rid")], "stadium": [("match", "sid"), ("team", "sid")],
        "competition": [("edition", "cid"), ("player_season", "cid")], "edition": [("match", "eid"), ("standing", "eid"), ("honour", "eid")],
        "match": [("appearance", "mid"), ("event", "mid"), ("match_coach", "mid"), ("match_award", "mid")]}
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
        self.c.execute("DROP TABLE remap_m")

    def close(self):
        self.c.commit()
        self.c.close()
