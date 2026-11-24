"""The last pass: what no loader owns and every build should be rid of (graph/integrity.py counts what is left).
A move from a club to itself is no move (Transfermarkt's rows, and two records of a club made one after the moves were
read); a move dated a millennium ahead takes the year of its season («3026-06-30» of 2025/2026). A man or a club a loader wrote
without a name (a scorer Transfermarkt's lineups do not list, a club its games leave blank) takes the name the source
gives somewhere else."""
import datetime
import os
import re

from graph.load.tm import rows

SEASON_END = re.compile(r"(\d{4})\s*$")


NUMBERED = re.compile(r"\s*\(\d+\)\s*$")           # Transfermarkt tells two men of one name apart: «Danilo (3)»
COUNTRY = re.compile(r"\s*\([^)]*\)\s*$")           # schochastics' key for a club: «Aiglon (Martinique)»


def nameless(G, reg, table, key, src):
    """the source's id -> the Tifo id of each record of this kind that has no name in any script"""
    bare = {i for (i,) in G.c.execute(f"SELECT {key} FROM {table} WHERE coalesce(name, '') = '' AND coalesce(name_ar, '') = ''")}
    pre, out = f"{table}|{src}|", {}
    for k, i in reg.map.items():
        if k.startswith(pre) and bare:
            i = reg.resolve(table, i)
            if i in bare:
                out[k[len(pre):]] = i
    return out


def named(G, table, key, want, pairs):
    """pairs: (the source's id, a name) as the source's files give them; the first name found is written"""
    n = 0
    for sid, name in pairs:
        if not want:
            break
        name = NUMBERED.sub("", name or "").strip()
        if name and sid in want:
            G.c.execute(f"UPDATE {table} SET name=? WHERE {key}=?", (name, want.pop(sid)))
            n += 1
    return n


def names(G, reg, S):
    db = getattr(S, "db", None)
    if not db:
        return {}
    tm = lambda f: rows(os.path.join(db, "tm", f))
    men = nameless(G, reg, "player", "pid", "tm")
    n = {"players_named": named(G, "player", "pid", men, ((r["player_id"], r.get("player_name")) for f in ("tm_game_lineups.csv.gz", "tm_appearances.csv.gz")
                                                           for r in rows(os.path.join(db, f))))}
    n["players_named"] += named(G, "player", "pid", men, ((r["player_id"], r.get("player_name")) for r in tm("player_profiles.csv")))
    clubs = nameless(G, reg, "team", "tid", "tm")
    n["clubs_named"] = named(G, "team", "tid", clubs, ((r.get(a + "_team_id"), r.get(a + "_team_name")) for r in tm("transfer_history.csv") for a in ("from", "to")))
    n["clubs_named"] += named(G, "team", "tid", clubs, ((r.get("team_id"), r.get("team_name")) for r in tm("player_performances.csv")))
    n["clubs_named"] += named(G, "team", "tid", clubs, ((r.get(a + "_club_id"), r.get(a + "_club_name")) for r in rows(os.path.join(db, "tm_games.csv.gz")) for a in ("home", "away")))
    sch = nameless(G, reg, "team", "tid", "sch")
    n["clubs_named"] += named(G, "team", "tid", sch, [(k, COUNTRY.sub("", k)) for k in list(sch)])
    return n


def load(G, reg, S, today=None):
    ahead = str((today or datetime.date.today()).year + 2)
    n = {"moves_to_itself": G.c.execute("DELETE FROM transfer WHERE from_tid = to_tid").rowcount, "dates_set_right": 0, "dates_dropped": 0}
    for pid, date, to, season in G.c.execute("SELECT pid, date, to_tid, season FROM transfer WHERE substr(date, 1, 4) > ?", (ahead,)).fetchall():
        m = SEASON_END.search(season or "")
        right = m and m.group(1) + date[4:]
        where = "pid=? AND date=? AND to_tid IS ?"
        if right and right[:4] <= ahead and not G.c.execute(f"SELECT 1 FROM transfer WHERE {where}", (pid, right, to)).fetchone():
            G.c.execute(f"UPDATE transfer SET date=? WHERE {where}", (right, pid, date, to))
            n["dates_set_right"] += 1
        else:
            G.c.execute(f"DELETE FROM transfer WHERE {where}", (pid, date, to))
            n["dates_dropped"] += 1
    n.update(names(G, reg, S))
    G.c.commit()
    return n
