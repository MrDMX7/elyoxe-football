"""worldfootballR_data's results files (graph/fbref_fetch.py: db/.cache/fbref.json.gz, 47 countries' leagues and 39 cups,
frozen in September 2025) fill what the graph's copies of those games lack: the referee, the ground and the attendance. The
big leagues from about 1990 and the World Cup from 1930 are the gain: before 2010 hardly a game of ours named its referee
(research/tifo-sources-2026-11-24.md §1.4). No game, club or ground is minted.

  * a club or a national team: the one the games of the same day and score vote for (3 votes, three times the next, and the
    file's first choice for that team); then, against a side already known, 2 votes, or 1 when the name agrees too;
  * a game: the one of those two teams on the day ±1 with that score, home and away either way round;
  * a referee or a ground: the one our copies of his games already name (2 votes and three times the next); else the only
    one of that name; else, for a referee, the file's own. A ground no copy names and no name finds is left out.

Runs after the copies of a game are one (twins_last) and before tidy, which joins a referee two sources wrote twice."""
import gzip, json, os
from collections import Counter, defaultdict
from graph.link import _days
from graph.load.teams import alike
from graph.load.wikidata_facts import fold

FILE = "fbref.json.gz"
SRC = "fbref"


def read(S):
    p = os.path.join(S.db, FILE)
    if not os.path.exists(p):
        return None
    with gzip.open(p, "rt", encoding="utf-8") as z:
        return json.load(z)


def top(c, n, lead=3):
    """the first choice of a count when it has n votes and lead times the next"""
    t = c.most_common(2)
    return t[0][0] if t and t[0][1] >= n and (len(t) == 1 or t[0][1] >= lead * t[1][1]) else None


def load(G, reg, S):
    rows = read(S)
    if rows is None:
        return {"skipped": "no fbref pack"}
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    n = Counter()
    by_score, by_pair, name_of = defaultdict(list), defaultdict(list), dict(q("SELECT tid, name FROM team"))
    for mid, d, h, a, hs, as_ in q("SELECT mid, substr(date,1,10), home, away, hs, as_ FROM match WHERE date IS NOT NULL AND hs IS NOT NULL AND as_ IS NOT NULL"):
        by_score[(d, hs, as_)].append((h, a))
        by_pair[(d, h, a)].append((mid, hs, as_))

    # 1. each file's names for a team
    votes = defaultdict(Counter)
    for f, d, hn, an, hs, as_, *_ in rows:
        for dd in _days(d):
            for h, a in by_score.get((dd, hs, as_), ()):
                votes[(f, hn)][h] += 1
                votes[(f, an)][a] += 1
    first = defaultdict(Counter)                 # (file, team) -> the names that chose it
    for k, c in votes.items():
        for t, v in c.items():
            first[(k[0], t)][k[1]] = v
    team = {}
    for k, c in votes.items():
        t = top(c, 3)
        if t is not None and top(first[(k[0], t)], 3) == k[1]:
            team[k] = t
    n["teams_by_games"] = len(team)
    for _ in range(2):                           # against a side already known
        votes = defaultdict(Counter)
        for f, d, hn, an, hs, as_, *_ in rows:
            th, ta = team.get((f, hn)), team.get((f, an))
            if (th is None) == (ta is None):
                continue
            for dd in _days(d):
                for h, a in by_score.get((dd, hs, as_), ()):
                    if th is not None and h == th:
                        votes[(f, an)][a] += 1
                    elif ta is not None and a == ta:
                        votes[(f, hn)][h] += 1
        taken, new = {(f, t) for (f, _), t in team.items()}, {}
        for k, c in votes.items():
            t = top(c, 2) or next((x for x in [top(c, 1)] if x is not None and alike(k[1], name_of.get(x))), None)
            if t is not None and (k[0], t) not in taken:
                new[k] = t
        if not new:
            break
        team.update(new)
        n["teams_by_opponent"] += len(new)

    # 2. each row's game
    found = []
    for f, d, hn, an, hs, as_, ref, ven, att in rows:
        th, ta = team.get((f, hn)), team.get((f, an))
        if th is None or ta is None:
            n["team_unknown"] += 1
            continue
        hit = [mid for dd in _days(d) for mid, x, y in by_pair.get((dd, th, ta), ()) if (x, y) == (hs, as_)]
        hit = hit or [mid for dd in _days(d) for mid, x, y in by_pair.get((dd, ta, th), ()) if (x, y) == (as_, hs)]
        if len(hit) != 1:
            n["no_game" if not hit else "two_games"] += 1
            continue
        found.append((hit[0], ref, ven, att))
    n["games"] = len(found)

    # 3. his name and the ground's, by the copies that already name them
    have = {mid: (rid, sid) for mid, rid, sid in q("SELECT mid, rid, sid FROM match WHERE rid IS NOT NULL OR sid IS NOT NULL")}
    vr, vs = defaultdict(Counter), defaultdict(Counter)
    for mid, ref, ven, _ in found:
        rid, sid = have.get(mid, (None, None))
        if ref and rid:
            vr[ref][rid] += 1
        if ven and sid:
            vs[ven][sid] += 1
    known = {}
    for t, key in (("referee", "rid"), ("stadium", "sid")):
        known[t] = defaultdict(list)
        for i, nm in q(f"SELECT {key}, name FROM {t}"):
            known[t][fold(nm)].append(i)
    one = lambda t, nm: known[t][fold(nm)][0] if fold(nm) and len(known[t].get(fold(nm)) or ()) == 1 else None
    refs, grounds = {}, {}

    def referee(nm):
        if nm not in refs:
            rid = top(vr[nm], 2) or one("referee", nm)
            if rid is None and fold(nm):
                rid = reg.get("referee", SRC, nm) or reg.mint("referee", SRC, nm)
                G.put("referee", {"rid": rid, "name": nm}, SRC)
                G.xref("referee", rid, SRC, nm, f"{SRC}-native")
                known["referee"][fold(nm)].append(rid)
                n["referees_own"] += 1
            refs[nm] = rid
        return refs[nm]

    def ground(nm):
        if nm not in grounds:
            grounds[nm] = top(vs[nm], 2) or one("stadium", nm)
            n["grounds_unknown"] += grounds[nm] is None
        return grounds[nm]

    # 4. what the game lacks
    for mid, ref, ven, att in found:
        if ref and referee(ref):
            n["referee"] += G.c.execute("UPDATE match SET rid=? WHERE mid=? AND rid IS NULL", (referee(ref), mid)).rowcount
        if ven and ground(ven):
            n["ground"] += G.c.execute("UPDATE match SET sid=? WHERE mid=? AND sid IS NULL", (ground(ven), mid)).rowcount
        if att:
            n["attendance"] += G.c.execute("UPDATE match SET attendance=? WHERE mid=? AND attendance IS NULL", (att, mid)).rowcount
    return dict(n)
