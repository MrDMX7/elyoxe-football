"""One club, one record, by its games (after graph/load/teams.py, whose name rule needs a country and a FotMob record): two
records are one club when on the days both have a game they have the same game — the same side, the same score, the same
opponent. 23 Nov 2026: 2,860 records carried 1,302 club names and 12,009 games stood twice (Rijeka's league season under
FotMob's record and under schochastics', Rochdale under Transfermarkt's and engsoccerdata's, Twente, Vitesse, BATE): the
loaders tie a source's clubs to FotMob's games only, so Transfermarkt's, schochastics', ESPN's and RSSSF's records of one
club never met each other, and a club FotMob holds few old games of stayed two.

Rules:
  * a vote is one day on which both records have a game on the same side with the same score against the same opponent:
    the same record, or one joined to it in an earlier round, or one under the same folded name;
  * 3 votes, or 2 when the two records carry the same folded name;
  * of the days both have a game, 85% are the same game (two clubs of one league play the same days with other scores);
  * two records that ever met are two clubs; a national team is left to graph/load/teams.py; two numbers of one numbering
    source (FotMob, Transfermarkt, 365Scores, ESPN) are two clubs; a club FotMob keeps under a later name (teams_ar.yaml
    `era_names`), a UAE club of the `historic` and `rename` lists and a pair graph/team_aliases.yaml keeps `apart` are never
    joined;
  * the FotMob record is kept, else the better source's (graph.db SRC_RANK), else the lower id.
The rounds repeat until none joins (a game whose two clubs were both held twice votes once one of them is joined).
Rebuilt in every build and never written to the registry; graph/load/twins.py then makes each game held twice one."""
from collections import defaultdict

from graph.db import SRC_RANK
from graph.load.teams import apart, fold, guarded, settle_conflicts, squash

ONE_ID = ("fotmob", "tm", "s365", "espn")
VOTES, VOTES_NAMED, SHARE, ROUNDS = 3, 2, 0.85, 8


def candidates(c, era=None, never=None, kept=None):
    """[(drop, keep)] for one graph's connection (read-only)."""
    q = lambda s, p=(): c.execute(s, p).fetchall()
    team = {tid: (name, kind, src) for tid, name, kind, src in q("SELECT tid, name, kind, src FROM team")}
    name = {t: squash(v[0]) for t, v in team.items()}
    folded = {t: fold(v[0]) for t, v in team.items()}
    kept = guarded()[0] if kept is None else kept
    ids = defaultdict(set)                    # tid -> {(source, id)} of the numbering sources
    for tid, source, sid in q("SELECT tifo_id, source, source_id FROM xref WHERE type='team'"):
        if source in ONE_ID:
            ids[tid].add((source, sid))
    if era is None:
        era = {t for (t,) in q(f"""SELECT tifo_id FROM xref WHERE type='team' AND source='fotmob' AND source_id IN
                                   ({','.join(repr(str(e)) for e in guarded()[1]) or "''"})""")}
    never = apart() if never is None else never
    days = defaultdict(dict)                  # tid -> {day: (home?, for, against, opponent)}; None: two games that day
    met = set()
    for d, h, a, hs, as_ in q("""SELECT substr(date,1,10), home, away, hs, as_ FROM match WHERE date IS NOT NULL AND hs IS NOT NULL
                                 AND as_ IS NOT NULL AND home IS NOT NULL AND away IS NOT NULL"""):
        met.add((h, a) if h < a else (a, h))
        for t, row in ((h, (1, hs, as_, a)), (a, (0, as_, hs, h))):
            g = days[t]
            if d not in g:
                g[d] = row
            elif g[d] is not None and g[d][:3] != row[:3]:
                g[d] = None
    national = {t for t, v in team.items() if v[1] == "national"}
    parent = {}
    members = {t: {t} for t in days}

    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def ok(a, b, votes):
        ma, mb = members[a], members[b]
        if (ma | mb) & national or (ma | mb) & era:
            return False
        na, nb = {name[m] for m in ma} - {""}, {name[m] for m in mb} - {""}
        if votes < (VOTES_NAMED if na & nb else VOTES):
            return False
        fa, fb = {folded[m] for m in ma}, {folded[m] for m in mb}
        if (fa | fb) & kept or any(tuple(sorted((x, y))) in never for x in fa for y in fb):
            return False
        ia, ib = defaultdict(set), defaultdict(set)
        for own, ms in ((ia, ma), (ib, mb)):
            for m in ms:
                for s, i in ids[m]:
                    own[s].add(i)
        if any(ia[s] != ib[s] for s in ia.keys() & ib.keys()):
            return False
        if any(((x, y) if x < y else (y, x)) in met for x in ma for y in mb):
            return False
        da, db = days[a], days[b]
        both = [d for d in da.keys() & db.keys() if da[d] is not None and db[d] is not None]
        return sum(da[d][:3] == db[d][:3] for d in both) >= SHARE * len(both)

    for _ in range(ROUNDS):
        bucket = defaultdict(set)
        for r, g in days.items():
            for d, row in g.items():
                if row is None:
                    continue
                ih, gf, ga, opp = row
                bucket[(d, ih, gf, ga, find(opp))].add(r)
                if name.get(opp):
                    bucket[(d, ih, gf, ga, name[opp])].add(r)
        seen = defaultdict(set)
        for key, rs in bucket.items():
            if len(rs) > 1:
                rs = sorted(rs)
                for i, a in enumerate(rs):
                    for b in rs[i + 1:]:
                        seen[(a, b)].add(key[0])
        del bucket
        joined = 0
        for (a, b), ds in sorted(seen.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            a, b = find(a), find(b)
            if a == b or len(ds) < VOTES_NAMED or not ok(a, b, len(ds)):
                continue
            keep, drop = (a, b) if a < b else (b, a)
            parent[drop] = keep
            members[keep] |= members.pop(drop)
            g = days[keep]
            for d, row in days.pop(drop).items():
                if d not in g:
                    g[d] = row
                elif g[d] is not None and (row is None or row[:3] != g[d][:3]):
                    g[d] = None
            joined += 1
        if not joined:
            break
    fm = {t for t in team if any(s == "fotmob" for s, _ in ids[t])}
    out = []
    for ms in members.values():
        if len(ms) > 1:
            keep = min(ms, key=lambda t: (t not in fm, SRC_RANK.get(team[t][2], 9), t))
            out += [(t, keep) for t in ms if t != keep]
    return sorted(out)


def load(G, reg, S):
    merged = candidates(G.c)
    G.remap_many("team", merged)
    return {"merged": len(merged), "clubs": len({k for _, k in merged}), "conflicts_settled": settle_conflicts(G, merged)}
