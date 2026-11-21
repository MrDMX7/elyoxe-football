"""One player, one record (spec §3.2, the people side): a player who reached us from several sources (Wikipedia's award
lists, martj42's internationals, Fjelstul's World Cups, Transfermarkt, FotMob) under ids no crosswalk joins is folded into
one record here. Ismail Matar was three (FotMob, his awards, his international goals), Adnan Al Talyani two.

Rules, by the folded name (accents, case, hyphens and dots gone):
  * the same birth date: one player; two birth dates: two players;
  * a record without a birth date joins the one record that played for one of its teams, or for its country (a national
    team's record and a record of that country's clubs), within 8 years of it, and only when exactly one fits (two possible
    owners: it stays apart);
  * a record with only a birth date (an award list's profile, no matches) joins the only player of that name, when he played
    between 15 and 45;
  * a record with neither (a title holder from Wikipedia: «Youssouf Atiq», top scorer 1991/92) joins the only player of that
    name who played in a competition his titles are from;
  * two records FotMob knows are never folded together (each has its own page).
The kept record is the one FotMob knows, else the lower id. Rebuilt in every build from these rules and never written to
the registry, so a rule fixed tomorrow undoes today's mistake."""
import re
import unicodedata
from collections import defaultdict, namedtuple
from datetime import date

Person = namedtuple("Person", "pid name born teams first last fotmob clubs_c nat_c comps", defaults=(frozenset(), frozenset(), frozenset()))
YEARS = 8


def fold(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _close(a_first, a_last, b_first, b_last):
    if not (a_first and a_last and b_first and b_last):
        return False
    d = lambda s: date.fromisoformat(s[:10])
    gap = max((d(b_first) - d(a_last)).days, (d(a_first) - d(b_last)).days, 0)
    return gap <= YEARS * 366


def pairs(people):
    """[(drop, keep)] for one list of records (any names: grouped here)."""
    groups = defaultdict(list)
    for p in people:
        if p.name:
            groups[p.name].append(p)
    out = []
    for g in groups.values():
        if len(g) < 2:
            continue
        clusters = []
        by_born = defaultdict(list)
        for p in g:
            if p.born:
                by_born[p.born[:10]].append(p)
        for ps in by_born.values():
            clusters.append({"ps": list(ps), "teams": set().union(*(p.teams for p in ps)),
                             "clubs_c": set().union(*(p.clubs_c for p in ps)), "nat_c": set().union(*(p.nat_c for p in ps)),
                             "comps": set().union(*(p.comps for p in ps)),
                             "first": min((p.first for p in ps if p.first), default=None),
                             "last": max((p.last for p in ps if p.last), default=None), "born": True})
        for p in sorted((p for p in g if not p.born), key=lambda p: (p.first or "9", p.pid)):
            fits = [c for c in clusters if (c["teams"] & p.teams or c["clubs_c"] & p.nat_c or c["nat_c"] & p.clubs_c)
                    and _close(c["first"], c["last"], p.first, p.last)]
            if len(fits) == 1:
                c = fits[0]
                c["ps"].append(p)
                c["teams"] |= p.teams
                c["clubs_c"] |= p.clubs_c
                c["nat_c"] |= p.nat_c
                c["comps"] |= p.comps
                c["first"] = min(x for x in (c["first"], p.first) if x)
                c["last"] = max(x for x in (c["last"], p.last) if x)
            elif not fits:
                clusters.append({"ps": [p], "teams": set(p.teams), "clubs_c": set(p.clubs_c), "nat_c": set(p.nat_c), "comps": set(p.comps),
                                 "first": p.first, "last": p.last, "born": False})
        profiles = [c for c in clusters if c["born"] and not c["first"]]
        for prof in profiles if len(profiles) == 1 else []:
            others = [c for c in clusters if c is not prof and c["first"]]
            if len(others) != 1 or others[0]["born"]:
                continue
            o, y = others[0], int(prof["ps"][0].born[:4])
            if y + 15 <= int(o["first"][:4]) and int(o["last"][:4]) <= y + 45:
                o["ps"] += prof["ps"]
                prof["ps"] = []
        bare = [c for c in clusters if not c["born"] and not c["first"] and c["ps"]]
        for b in bare if len(bare) == 1 else []:
            fits = [c for c in clusters if c is not b and c["first"] and c["comps"] & b["comps"]]
            if len(fits) == 1:
                fits[0]["ps"] += b["ps"]
                b["ps"] = []
        for c in clusters:
            if len(c["ps"]) < 2:
                continue
            fm = sorted(p.pid for p in c["ps"] if p.fotmob)
            keep = fm[0] if fm else min(p.pid for p in c["ps"])
            out += [(p.pid, keep) for p in c["ps"] if p.pid != keep and not p.fotmob]
    return sorted(out)


def load(G, reg, S):
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    names = defaultdict(list)
    for pid, name, born in q("SELECT pid, name, born FROM player"):
        f = fold(name)
        if f:
            names[f].append((pid, born))
    dup = {pid: (f, born) for f, rows in names.items() if len(rows) > 1 for pid, born in rows}
    if not dup:
        return {"candidates": 0, "merged": 0}
    G.c.execute("CREATE TEMP TABLE people_dup(pid INTEGER PRIMARY KEY)")
    G.c.executemany("INSERT INTO people_dup VALUES(?)", [(p,) for p in dup])
    teams, span, clubs_c, nat_c = defaultdict(set), {}, defaultdict(set), defaultdict(set)
    tk = {t: (k, c) for t, k, c in q("SELECT tid, kind, country FROM team")}
    for pid, tid, first, last in q("""SELECT a.pid, a.tid, min(substr(m.date,1,10)), max(substr(m.date,1,10)) FROM appearance a
                                      JOIN people_dup d ON d.pid=a.pid JOIN match m ON m.mid=a.mid
                                      WHERE a.played=1 AND m.date IS NOT NULL GROUP BY a.pid, a.tid"""):
        teams[pid].add(tid)
        kind, country = tk.get(tid, (None, None))
        if country:
            (nat_c if kind == "national" else clubs_c)[pid].add(country)
        f0, l0 = span.get(pid, (first, last))
        span[pid] = (min(f0, first), max(l0, last))
    fm = {p for (p,) in q("SELECT DISTINCT x.tifo_id FROM xref x JOIN people_dup d ON d.pid=x.tifo_id WHERE x.type='player' AND x.source='fotmob'")}
    comps = defaultdict(set)                  # the competitions each one played in or holds a title of
    for pid, cid in q("""SELECT DISTINCT a.pid, e.cid FROM appearance a JOIN people_dup d ON d.pid=a.pid JOIN match m ON m.mid=a.mid
                         JOIN edition e ON e.eid=m.eid UNION
                         SELECT DISTINCT h.pid, e.cid FROM honour h JOIN people_dup d ON d.pid=h.pid JOIN edition e ON e.eid=h.eid"""):
        comps[pid].add(cid)
    G.c.execute("DROP TABLE people_dup")
    rows = [Person(pid, f, born, frozenset(teams.get(pid, ())), *span.get(pid, (None, None)), pid in fm,
                   frozenset(clubs_c.get(pid, ())), frozenset(nat_c.get(pid, ())), frozenset(comps.get(pid, ()))) for pid, (f, born) in dup.items()]
    merged = pairs(rows)
    G.remap_many("player", merged)
    return {"candidates": len(rows), "merged": len(merged)}
