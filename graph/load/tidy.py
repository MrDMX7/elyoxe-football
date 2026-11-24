"""The last pass: what no loader owns and every build should be rid of (graph/integrity.py counts what is left).
A move from a club to itself is no move (Transfermarkt's rows, and two records of a club made one after the moves were
read); a move dated a millennium ahead takes the year of its season («3026-06-30» of 2025/2026). A man or a club a loader wrote
without a name (a scorer Transfermarkt's lineups do not list, a club its games leave blank) takes the name the source
gives somewhere else. A season left with no game, champion, table or note (a list's winner no record answers to) is no season, and a competition known by a
source's number alone, left with no season, is none. A birth date that is no date is no birth date. A man in a game before
he was thirteen, or past fifty in one a source matched to him by his name, is another man of that name (Hassan El Shazly of
1963 under the one born in 1995): those games go to a record of their own; where the source knew him by its own number, the
birth date is the doubt and leaves. A referee or a ground written twice under one name (an accent, a hyphen, a dot after an
initial; a ground with its city and without) is one: grounds of one name in two cities stay two, and a referee known by
an initial joins his namesake only where both took games of one competition. A coach each source wrote under its own number
is one man where the name is one, no two birth dates or countries differ and the two never sat on a bench the same day."""
import datetime
import os
import re
import unicodedata

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


BY_NAME = ("martj42", "espn", "rsssf", "fjelstul", "worldcup", "intl_goals")       # sources that know a man by his name alone


def namesakes(G, reg):
    n = {"births_dropped": G.c.execute("UPDATE player SET born=NULL WHERE born IS NOT NULL AND (born NOT GLOB '[12][0-9][0-9][0-9]*' OR born < '1840')").rowcount,
         "namesakes": 0}
    age = "cast(substr(m.date, 1, 4) AS int) - cast(substr(p.born, 1, 4) AS int)"
    odd = {}
    for t in ("appearance", "event"):
        for pid, mid, src, a in G.c.execute(f"""SELECT a.pid, a.mid, a.src, {age} FROM {t} a JOIN player p ON p.pid = a.pid JOIN match m ON m.mid = a.mid
                                               WHERE p.born IS NOT NULL AND m.date IS NOT NULL AND ({age} < 13 OR ({age} > 50 AND a.src IN ({",".join("?" * len(BY_NAME))})))
                                               AND (a.src IN ({",".join("?" * len(BY_NAME))}) OR {age} < 13)""", BY_NAME * 2):
            odd.setdefault(pid, {}).setdefault(src in BY_NAME, set()).add(mid)
    for pid, by in sorted(odd.items()):
        if by.get(False):                             # the source's own number for him: the date is wrong, not the man
            G.c.execute("UPDATE player SET born=NULL WHERE pid=?", (pid,))
            n["births_dropped"] += 1
            continue
        name, ar = G.c.execute("SELECT name, name_ar FROM player WHERE pid=?", (pid,)).fetchone()
        new = reg.mint("player", "namesake", str(pid))
        G.put("player", {"pid": new, "name": name, "name_ar": ar}, "namesake")
        G.xref("player", new, "namesake", str(pid), "age")
        for mid in sorted(by[True]):
            G.c.execute("UPDATE OR IGNORE appearance SET pid=? WHERE pid=? AND mid=?", (new, pid, mid))
            G.c.execute("DELETE FROM appearance WHERE pid=? AND mid=?", (pid, mid))
            G.c.execute("UPDATE event SET pid=? WHERE pid=? AND mid=?", (new, pid, mid))
            G.c.execute("UPDATE event SET pid2=? WHERE pid2=? AND mid=?", (new, pid, mid))
        n["namesakes"] += 1
    return n


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def twice(G, reg):
    """referees, grounds and coaches one source or two wrote twice"""
    n, pairs = {"referees_joined": 0, "grounds_joined": 0, "coaches_joined": 0}, {"referee": [], "stadium": [], "coach": []}
    by = {}
    for kid, name, born, nat, pid in G.c.execute("SELECT kid, name, born, nationality, pid FROM coach ORDER BY kid"):
        if fold(name):
            by.setdefault(fold(name), []).append((kid, born, nat, pid))
    days = lambda kid: {d for (d,) in G.c.execute("SELECT DISTINCT substr(m.date, 1, 10) FROM match_coach c JOIN match m ON m.mid = c.mid WHERE c.kid=?", (kid,))}
    for key, group in sorted(by.items()):
        if len(group) < 2 or any(len({r[i] for r in group if r[i]}) > 1 for i in (1, 2, 3)):
            continue
        keep, sat = group[0][0], days(group[0][0])
        for kid, *_ in group[1:]:
            his = days(kid)
            if sat & his:
                continue
            sat |= his
            pairs["coach"].append((kid, reg.merge("coach", keep, kid)))
    by = {}
    for rid, name, country in G.c.execute("SELECT rid, name, country FROM referee ORDER BY rid"):
        if fold(name):
            by.setdefault(fold(name), []).append((rid, country))
    took = lambda rid: {c for (c,) in G.c.execute("SELECT DISTINCT e.cid FROM match m JOIN edition e ON e.eid = m.eid WHERE m.rid=?", (rid,))}
    for key, group in sorted(by.items()):
        if len(group) < 2 or len({c for _, c in group if c}) > 1:
            continue
        keep = group[0][0]
        initial = len(key.split()[0]) == 1
        for rid, _ in group[1:]:
            if initial and not took(keep) & took(rid):
                continue
            pairs["referee"].append((rid, reg.merge("referee", keep, rid)))
    by = {}
    for sid, name, city in G.c.execute("SELECT sid, name, city FROM stadium ORDER BY sid"):
        if fold(name):
            by.setdefault(fold(name), []).append((sid, fold(city)))
    for key, group in sorted(by.items()):
        if len(group) < 2:
            continue
        towns = []                                    # each town's records; a town is one where one name opens the other
        for sid, city in group:
            if city:
                for t in towns:
                    if any(c.startswith(city) or city.startswith(c) for c in t["names"]):
                        t["names"].add(city), t["ids"].append(sid)
                        break
                else:
                    towns.append({"names": {city}, "ids": [sid]})
        if len(towns) > 1:                            # two grounds of one name: a record with no city could be either
            groups = [t["ids"] for t in towns]
        else:
            groups = [[sid for sid, _ in group]]
        for ids in groups:
            for sid in ids[1:]:
                pairs["stadium"].append((sid, reg.merge("stadium", min(ids), sid)))
    for t, k in (("referee", "referees_joined"), ("stadium", "grounds_joined"), ("coach", "coaches_joined")):
        G.remap_many(t, pairs[t])
        n[k] = len(pairs[t])
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
    G.c.execute("""CREATE TEMP TABLE bare AS SELECT eid FROM edition e WHERE e.note IS NULL AND NOT EXISTS(SELECT 1 FROM match m WHERE m.eid = e.eid)
                   AND NOT EXISTS(SELECT 1 FROM honour h WHERE h.eid = e.eid) AND NOT EXISTS(SELECT 1 FROM standing s WHERE s.eid = e.eid)""")
    G.c.execute("DELETE FROM xref WHERE type = 'edition' AND tifo_id IN (SELECT eid FROM bare)")
    n["empty_seasons"] = G.c.execute("DELETE FROM edition WHERE eid IN (SELECT eid FROM bare)").rowcount
    G.c.execute("DROP TABLE bare")
    G.c.execute("CREATE TEMP TABLE bare AS SELECT cid FROM competition c WHERE (ifnull(name, '') = '' OR name GLOB 'FotMob [0-9]*') AND NOT EXISTS(SELECT 1 FROM edition e WHERE e.cid = c.cid)")
    G.c.execute("DELETE FROM xref WHERE type = 'competition' AND tifo_id IN (SELECT cid FROM bare)")
    n["empty_competitions"] = G.c.execute("DELETE FROM competition WHERE cid IN (SELECT cid FROM bare)").rowcount
    G.c.execute("DROP TABLE bare")
    n.update(namesakes(G, reg))
    n.update(twice(G, reg))
    G.c.commit()
    return n
