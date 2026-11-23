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
  * a record without a birth date that fits several records of one man joins them all, when at most one has a birth date and
    no two of them played for two clubs (or two national teams) at once for more than 120 days (Thierry Henry was three on 23
    Nov 2026: Transfermarkt's with France's games, ESPN's with Arsenal and Barcelona, and FotMob's, which fits both);
  * an edition's listed top scorer is the one man of his name who scored in that edition's matches (Batistuta, Qatar 2003/04:
    Wikipedia's honour on one record, his 23 goals on RSSSF's) -- the same folded name, or one name inside the other with the
    same last word («Pauleta», «Pedro Miguel Pauleta»), no other birth date;
  * two records FotMob knows are never folded together (each has its own page).
The rules run twice: here, and again once the teams of the several sources are one (people_again, after teams).
The kept record is the one FotMob knows, else the lower id. Rebuilt in every build from these rules and never written to
the registry, so a rule fixed tomorrow undoes today's mistake."""
import re
import unicodedata
from collections import defaultdict, namedtuple
from datetime import date

Person = namedtuple("Person", "pid name born teams first last fotmob clubs_c nat_c comps stints", defaults=(frozenset(),) * 4)
YEARS = 8
AT_ONCE = 120           # days two clubs' spans of one record may overlap (a transfer in the middle of a season)


def fold(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _close(a_first, a_last, b_first, b_last):
    if not (a_first and a_last and b_first and b_last):
        return False
    d = lambda s: date.fromisoformat(s[:10])
    gap = max((d(b_first) - d(a_last)).days, (d(a_first) - d(b_last)).days, 0)
    return gap <= YEARS * 366


def _days(a, b):
    return (date.fromisoformat(b[:10]) - date.fromisoformat(a[:10])).days


def agree(stint_sets):
    """no two of these records played for two teams of a kind (two clubs, two national teams) at once"""
    sets = [list(x) for x in stint_sets]
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            for ta, fa, la, na in sets[i]:
                for tb, fb, lb, nb in sets[j]:
                    if ta != tb and na == nb and fa and la and fb and lb and _days(max(fa, fb), min(la, lb)) > AT_ONCE:
                        return False
    return True


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
                             "comps": set().union(*(p.comps for p in ps)), "stints": set().union(*(p.stints for p in ps)),
                             "first": min((p.first for p in ps if p.first), default=None),
                             "last": max((p.last for p in ps if p.last), default=None), "born": True})
        def take(c, o):
            c["ps"] += o["ps"]
            for k in ("teams", "clubs_c", "nat_c", "comps", "stints"):
                c[k] |= o[k]
            c["first"] = min((x for x in (c["first"], o["first"]) if x), default=None)
            c["last"] = max((x for x in (c["last"], o["last"]) if x), default=None)
            c["born"] = c["born"] or o["born"]
        for p in sorted((p for p in g if not p.born), key=lambda p: (p.first or "9", p.pid)):
            one = {"ps": [p], "teams": set(p.teams), "clubs_c": set(p.clubs_c), "nat_c": set(p.nat_c), "comps": set(p.comps),
                   "stints": set(p.stints), "first": p.first, "last": p.last, "born": False}
            fits = [c for c in clusters if c["ps"] and (c["teams"] & p.teams or c["clubs_c"] & p.nat_c or c["nat_c"] & p.clubs_c)
                    and _close(c["first"], c["last"], p.first, p.last)]
            if len(fits) > 1 and sum(c["born"] for c in fits) <= 1 and agree([c["stints"] for c in fits] + [p.stints]):
                fits.sort(key=lambda c: not c["born"])             # the bridge: every record it fits is one man
                for o in fits[1:]:
                    take(fits[0], o)
                    o["ps"] = []
                fits = fits[:1]
            if len(fits) == 1:
                take(fits[0], one)
            elif not fits:
                clusters.append(one)
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


def _same_name(a, b):
    """one name, or one inside the other with the same last word («Pauleta», «Pedro Miguel Pauleta»)"""
    x, y = fold(a).split(), fold(b).split()
    if not x or not y:
        return False
    return x == y or x[-1] == y[-1] and (set(x) <= set(y) or set(y) <= set(x))


def scorer_pairs(tops, scorers):
    """[(drop, keep)]: an edition's listed top scorer (eid, pid, name, born) with no goal of his in it, and the one man of his
    name who scored there ({eid: [(pid, name, born)]}); none or two of them: no guess"""
    out = []
    for eid, pid, name, born in tops:
        got = scorers.get(eid) or []
        if any(s[0] == pid for s in got):
            continue
        fits = {s[0] for s in got if _same_name(name, s[1]) and not (born and s[2] and born[:10] != s[2][:10])}
        if len(fits) == 1:
            out.append((fits.pop(), pid))
    return sorted(set(out))


def load(G, reg, S):
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    names = defaultdict(list)
    for pid, name, born in q("SELECT pid, name, born FROM player"):
        f = fold(name)
        if f:
            names[f].append((pid, born))
    dup = {pid: (f, born) for f, rows in names.items() if len(rows) > 1 for pid, born in rows}
    by_qid = wikidata_pairs(S, {pid for rows in names.values() for pid, _ in rows})
    tops = q("SELECT h.eid, h.pid, p.name, p.born FROM honour h JOIN player p ON p.pid=h.pid WHERE h.kind='top_scorer'")
    scorers = defaultdict(list)
    for eid, pid, name, born in q("""SELECT m.eid, v.pid, p.name, p.born FROM event v JOIN match m ON m.mid=v.mid JOIN player p ON p.pid=v.pid
                                     WHERE v.type IN ('goal', 'penalty_goal') AND m.eid IN (SELECT eid FROM honour WHERE kind='top_scorer')
                                     GROUP BY m.eid, v.pid"""):
        scorers[eid].append((pid, name, born))
    by_goals = scorer_pairs(tops, scorers)
    fm_all = {p for (p,) in q("SELECT tifo_id FROM xref WHERE type='player' AND source='fotmob'")}
    if not dup:
        merged = union(by_qid + by_goals, fm_all & {x for pr in by_goals for x in pr})
        G.remap_many("player", merged)
        return {"candidates": 0, "merged": len(merged), "by_wikidata": len(by_qid), "by_goals": len(by_goals)}
    G.c.execute("CREATE TEMP TABLE people_dup(pid INTEGER PRIMARY KEY)")
    G.c.executemany("INSERT INTO people_dup VALUES(?)", [(p,) for p in dup])
    teams, span, clubs_c, nat_c, stints = defaultdict(set), {}, defaultdict(set), defaultdict(set), defaultdict(set)
    tk = {t: (k, c) for t, k, c in q("SELECT tid, kind, country FROM team")}
    for pid, tid, first, last in q("""SELECT a.pid, a.tid, min(substr(m.date,1,10)), max(substr(m.date,1,10)) FROM appearance a
                                      JOIN people_dup d ON d.pid=a.pid JOIN match m ON m.mid=a.mid
                                      WHERE a.played=1 AND m.date IS NOT NULL GROUP BY a.pid, a.tid"""):
        teams[pid].add(tid)
        kind, country = tk.get(tid, (None, None))
        stints[pid].add((tid, first, last, kind == "national"))
        if country:
            (nat_c if kind == "national" else clubs_c)[pid].add(country)
        f0, l0 = span.get(pid, (first, last))
        span[pid] = (min(f0, first), max(l0, last))
    fm = {p for (p,) in q("SELECT DISTINCT x.tifo_id FROM xref x JOIN people_dup d ON d.pid=x.tifo_id WHERE x.type='player' AND x.source='fotmob'")}
    fm |= fm_all & {x for pr in by_goals for x in pr}
    comps = defaultdict(set)                  # the competitions each one played in or holds a title of (a bench place is neither)
    for pid, cid in q("""SELECT DISTINCT a.pid, e.cid FROM appearance a JOIN people_dup d ON d.pid=a.pid AND a.played=1 JOIN match m ON m.mid=a.mid
                         JOIN edition e ON e.eid=m.eid UNION
                         SELECT DISTINCT h.pid, e.cid FROM honour h JOIN people_dup d ON d.pid=h.pid JOIN edition e ON e.eid=h.eid"""):
        comps[pid].add(cid)
    G.c.execute("DROP TABLE people_dup")
    rows = [Person(pid, f, born, frozenset(teams.get(pid, ())), *span.get(pid, (None, None)), pid in fm,
                   frozenset(clubs_c.get(pid, ())), frozenset(nat_c.get(pid, ())), frozenset(comps.get(pid, ())),
                   frozenset(stints.get(pid, ()))) for pid, (f, born) in dup.items()]
    merged = union(pairs(rows) + by_qid + by_goals, fm)
    G.remap_many("player", merged)
    return {"candidates": len(rows), "merged": len(merged), "by_wikidata": len(by_qid), "by_goals": len(by_goals)}


def wikidata_pairs(S, known):
    """Two old players the names job found on one Wikidata item (names/people_ar.json, k<Tifo id>: Ali Daei's caps for
    Iran and his goals for Al Shabab were two records) are one: (drop, keep), the lower id kept."""
    import os
    by = defaultdict(list)
    for k, v in ((S.read(os.path.join(S.names, "people_ar.json")) if S else None) or {}).items():
        if str(k).startswith("k") and str(k)[1:].isdigit() and v.get("qid") and v.get("source") in ("wikidata", "arwiki", "manual"):
            pid = int(k[1:])
            if pid in known:
                by[v["qid"]].append(pid)
    return [(p, min(ps)) for ps in by.values() if len(ps) > 1 for p in ps if p != min(ps)]


def union(prs, fotmob=()):
    """(drop, keep) pairs from several rules as one set of merges: every record of a group goes to one record (the one FotMob
    knows, else the lowest id), and no kept record is itself merged away."""
    parent = {}

    def root(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x
    for a, b in prs:
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    groups = defaultdict(set)
    for x in set(parent) | set(parent.values()):
        groups[root(x)].add(x)
    out = []
    for g in groups.values():
        fm = sorted(p for p in g if p in fotmob)
        keep = fm[0] if fm else min(g)
        out += [(p, keep) for p in g if p != keep and p not in fotmob]
    return sorted(out)
