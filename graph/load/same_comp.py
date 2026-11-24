"""One competition, one record (the competitions side of graph/load/same_club.py). 24 Nov 2026: a league stood as up to three
records no loader tied: the one its games sit under (Transfermarkt's code «SC1», schochastics' slug «hungary», martj42's
name), 365Scores' record (its names and champions, no game) and the record FotMob's trophy lists made (champions, no row at
all: 171 competitions with 4,580 editions and no name). The site publishes a competition by its FotMob id, so 1,014,454 of
1,525,099 games sat under competitions no page showed.

Rules:
  * a competition FotMob's trophy lists made and no loader described gets its row (FotMob's league list: name, Arabic
    name, country) and its FotMob id in xref;
  * graph/same_comp.yaml `same` names a source's competition and the FotMob competition it is (by FotMob's league id);
    the FotMob record is made when no loader made it;
  * two records with champion lists are one when of the seasons both list (5 or more; a calendar-year label may sit a
    year off a split-season one) 80% have the same champion, each is the other's best match, and their names or
    countries do not say otherwise;
  * a record with games and a record with a champion list are one when in 70% of 8 or more seasons the list's champion
    tops the table of the games (a league), or in 80% plays the last game (a cup), and no second record comes close;
  * never two numbers of one numbering source (FotMob, 365Scores, Transfermarkt, schochastics: 365Scores lists the
    league's champions under Poland's Super Cup too), never a pair `apart` keeps;
  * the FotMob record is kept, else 365Scores', else the better source's (graph.db SRC_RANK), else the lower id.
Rebuilt in every build and never written to the registry; graph/load/seasons.py then makes one edition of each season."""
import os
import re
from collections import Counter, defaultdict

import yaml

from graph.db import SRC_RANK
from graph.load.teams import fold, squash

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CURATED = os.path.join(ROOT, "graph", "same_comp.yaml")
LISTS, LIST_SHARE = 5, 0.8                 # two champion lists
SEASONS, TABLE_SHARE, FINAL_SHARE = 8, 0.7, 0.8
ONE_ID = ("fotmob", "s365", "tm", "sch", "espn")   # two numbers of one of these are two competitions
CLEAR = 0.6                                # the second-best record has at most this share of the best's seasons
YEAR = re.compile(r"\s*(\d{4})(?:\s*[/-]\s*(\d{2,4}))?")
CUP = re.compile(r"\b(cup|copa|coppa|coupe|pokal|beker|taca|trophy|shield|supercopa|supercoppa|supercup|super cup|kupa|cupa|kup)\b")


def end_year(season):
    m = YEAR.match(season or "")
    if not m:
        return None
    a, b = m.group(1), m.group(2)
    if not b:
        return int(a)
    return int(b) if len(b) == 4 else int(a[:2] + b) + (100 if int(b) < int(a[2:]) else 0)


def curated(path=CURATED):
    d = yaml.safe_load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    return (d or {}).get("same") or {}, [tuple(p) for p in (d or {}).get("apart") or []]


def candidates(c, keys=None, fixed=(), never=frozenset(), explain=None):
    """[(drop, keep)] for one graph's connection (read-only). keys: {cid: {(source, source id)}} of the registry (xref's
    when None); fixed: (a, b) pairs the curated list names; never: frozenset pairs kept apart; explain: a list that takes
    one line of evidence a join."""
    q = lambda s, p=(): c.execute(s, p).fetchall()
    if keys is None:
        keys = defaultdict(set)
        for cid, source, sid in q("SELECT tifo_id, source, source_id FROM xref WHERE type='competition'"):
            keys[cid].add((source, str(sid)))
    fm = {cid for cid, ks in keys.items() if any(s == "fotmob" for s, _ in ks)}
    comp = {cid: (name, kind, country, src) for cid, name, kind, country, src in q("SELECT cid, name, kind, country, src FROM competition")}
    tname = {tid: squash(name) for tid, name in q("SELECT tid, name FROM team")}
    champ = defaultdict(dict)                 # cid -> {end year: champion}
    for cid, season, tid in q("""SELECT e.cid, e.season, h.tid FROM honour h JOIN edition e ON e.eid=h.eid
                                 WHERE h.kind='champion' AND h.rank=1 AND h.tid IS NOT NULL"""):
        y = end_year(season)
        if y:
            champ[cid][y] = tid
    pts, sides, last, games = defaultdict(Counter), defaultdict(set), {}, Counter()
    for cid, season, h, a, hs, as_ in q("""SELECT e.cid, e.season, m.home, m.away, m.hs, m.as_ FROM match m JOIN edition e ON e.eid=m.eid
                                           WHERE m.hs IS NOT NULL AND m.as_ IS NOT NULL AND m.home IS NOT NULL AND m.away IS NOT NULL
                                           ORDER BY m.date"""):
        y = end_year(season)
        if y is None:
            continue
        k = (cid, y)
        games[cid] += 1
        pts[k][h] += 3 if hs > as_ else 1 if hs == as_ else 0
        pts[k][a] += 3 if as_ > hs else 1 if hs == as_ else 0
        sides[k] |= {h, a}
        last[k] = (h, a)
    years = defaultdict(set)
    for cid, y in pts:
        years[cid].add(y)
    same_team = lambda a, b: a == b or bool(tname.get(a)) and tname.get(a) == tname.get(b)

    parent = {}
    members = defaultdict(set)

    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def group(x):
        return members.get(find(x)) or {x}

    def allowed(a, b):
        ga, gb = group(a), group(b)
        ia, ib = defaultdict(set), defaultdict(set)
        for own, g in ((ia, ga), (ib, gb)):
            for m in g:
                for s, i in keys.get(m, ()):
                    if s in ONE_ID:
                        own[s].add(i)
        if any(ia[s] != ib[s] for s in ia.keys() & ib.keys()):
            return False
        return not any(frozenset((x, y)) in never for x in ga for y in gb)

    def join(a, b, why):
        a, b = find(a), find(b)
        if a == b:
            return False
        keep, drop = (a, b) if a < b else (b, a)
        members[keep] = group(keep) | group(drop)
        members.pop(drop, None)
        parent[drop] = keep
        if explain is not None:
            explain.append(why)
        return True

    label = lambda x: f"{x} «{(comp.get(x) or ('?',))[0]}» [{(comp.get(x) or (0, 0, 0, '-'))[3]}]"
    for a, b in fixed:
        if allowed(a, b):
            join(a, b, f"curated  {label(a)} = {label(b)}")
        elif explain is not None and find(a) != find(b):
            explain.append(f"REFUSED  {label(a)} = {label(b)}: each holds its own id of one source")

    def lists():
        out = defaultdict(dict)
        for cid, ys in champ.items():
            out[find(cid)].update(ys)
        return out

    # two champion lists
    for _ in range(4):
        cl = lists()
        best = {}                              # root -> (same, shared, other)
        rows = []
        big = [r for r, ys in cl.items() if len(ys) >= LISTS]
        for i, a in enumerate(big):
            for b in big[i + 1:]:
                top = (0, 0)
                for sh in (0, 1, -1):
                    shared = [y for y in cl[a] if y + sh in cl[b]]
                    if len(shared) >= LISTS:
                        top = max(top, (sum(same_team(cl[a][y], cl[b][y + sh]) for y in shared), len(shared)))
                if top[1] and top[0] >= LIST_SHARE * top[1]:
                    rows.append((top, a, b))
                    for x, o in ((a, b), (b, a)):
                        if top > best.get(x, ((0, 0), None))[0]:
                            best[x] = (top, o)
        joined = 0
        for top, a, b in sorted(rows, reverse=True):
            if best[a][1] == b and best[b][1] == a and allowed(a, b) and not strangers(comp, group(a), group(b)):
                joined += join(a, b, f"lists    {label(a)} = {label(b)} same champion {top[0]}/{top[1]}")
        if not joined:
            break

    # a record with games and a champion list
    for _ in range(3):
        cl = lists()
        held = defaultdict(set)                # root -> the records of it with games
        for cid in years:
            held[find(cid)].add(cid)
        joined = 0
        for x in sorted(held, key=lambda r: -sum(games[m] for m in held[r])):
            if find(x) != x:
                continue
            ms = held[x]
            lead, final = {}, {}               # year -> the table's leader, the sides of the last games
            for s in {s for m in ms for s in years[m]}:
                ks = [(m, s) for m in ms if len(sides.get((m, s), ())) >= 4]
                if ks:
                    table = Counter()
                    for k in ks:
                        table.update(pts[k])
                    lead[s] = table.most_common(1)[0][0]
                    final[s] = {z for k in ks for z in last[k]}
            if len(lead) < SEASONS:
                continue
            scored = []
            for y, ys in cl.items():
                if find(y) == x or len(ys) < SEASONS:
                    continue
                top = (0, 0, 0)
                for sh in (0, 1, -1):
                    ss = [s for s in ys if s + sh in lead]
                    if len(ss) < SEASONS:
                        continue
                    tb = sum(same_team(lead[s + sh], ys[s]) for s in ss)
                    fn = sum(any(same_team(z, ys[s]) for z in final[s + sh]) for s in ss)
                    top = max(top, (max(tb, fn), len(ss), tb))
                if top[0]:
                    scored.append((top, y))
            if not scored:
                continue
            scored.sort(reverse=True)
            (hit, n, tb), y = scored[0]
            share = TABLE_SHARE if tb == hit else FINAL_SHARE
            if n < SEASONS or hit < share * n:
                continue
            if len(scored) > 1 and scored[1][0][0] > CLEAR * hit:
                continue
            if allowed(x, y) and not strangers(comp, group(x), group(y)):
                joined += join(x, y, f"{'table' if tb == hit else 'final'}    {label(x)} = {label(y)} {hit}/{n} seasons, {sum(games[m] for m in ms)} games")
        if not joined:
            break

    out = []
    for ms in members.values():
        if len(ms) > 1:
            keep = min(ms, key=lambda x: (x not in fm, {"s365": 0}.get((comp.get(x) or (0, 0, 0, None))[3], 1),
                                          SRC_RANK.get((comp.get(x) or (0, 0, 0, None))[3], 9), x))
            out += [(x, keep) for x in ms if x != keep]
    return sorted(out)


def strangers(comp, ga, gb):
    """The names say a league and a cup: two competitions whatever their champions (a double winner's country)."""
    cup = lambda g: {bool(CUP.search(fold(comp[x][0]))) for x in g if comp.get(x) and comp[x][0] and " " in comp[x][0].strip()}
    ca, cb = cup(ga), cup(gb)
    return bool(ca) and bool(cb) and not (ca & cb)


def describe(G, reg, S):
    """A row and a FotMob id for each competition only FotMob's trophy lists made. Returns {cid: FotMob id} of all."""
    from graph import fm as fmlib
    info = fmlib.comp_info(S) if S is not None else {}
    fm, keys = {}, defaultdict(set)
    for k, v in reg.map.items():
        t, src, sid = k.split("|", 2)
        if t != "competition":
            continue
        cid = reg.resolve("competition", v)
        keys[cid].add((src, sid))
        if src == "fotmob" and sid.lstrip("-").isdigit():
            fm.setdefault(cid, int(sid))
    have = {cid for (cid,) in G.c.execute("SELECT cid FROM competition")}
    used = {cid for (cid,) in G.c.execute("SELECT DISTINCT cid FROM edition")}
    linked = {cid for (cid,) in G.c.execute("SELECT tifo_id FROM xref WHERE type='competition' AND source='fotmob'")}
    made = 0
    for cid, lid in sorted(fm.items()):
        d = info.get(lid) or {}
        if cid not in have and cid in used:
            G.put("competition", {"cid": cid, "name": d.get("name") or f"FotMob {lid}", "name_ar": d.get("name_ar"), "kind": d.get("kind"),
                                  "scope": d.get("scope"), "country": d.get("country")}, "fotmob")
            have.add(cid)
            made += 1
        if cid in have and cid not in linked:
            G.xref("competition", cid, "fotmob", lid, "fotmob-trophy")
    return fm, keys, made, info


def load(G, reg, S):
    fm, keys, made, info = describe(G, reg, S)
    same, apart = curated()
    cid_of = lambda key: reg.get("competition", *str(key).split("|", 1))
    fixed, minted = [], 0
    have = {cid for (cid,) in G.c.execute("SELECT cid FROM competition")}
    for key, lid in same.items():
        a = cid_of(key)
        if a is None or a not in have:
            continue
        if isinstance(lid, str):               # another source's record of it, where FotMob has none
            b = cid_of(lid)
            if b is not None and b in have and b != a:
                fixed.append((a, b))
            continue
        b = reg.mint("competition", "fotmob", int(lid))
        if b not in have:                      # FotMob's league no loader made: its record starts here
            d = info.get(int(lid)) or {}
            G.put("competition", {"cid": b, "name": d.get("name") or f"FotMob {lid}", "name_ar": d.get("name_ar"), "kind": d.get("kind"),
                                  "scope": d.get("scope"), "country": d.get("country")}, "fotmob")
            G.xref("competition", b, "fotmob", int(lid), "curated")
            have.add(b)
            minted += 1
        keys[b].add(("fotmob", str(lid)))
        fixed.append((a, b))
    never = {frozenset(x for x in (cid_of(a), cid_of(b)) if x is not None) for a, b in apart}
    G.c.commit()
    why = []
    merged = candidates(G.c, keys=keys, fixed=fixed, never={p for p in never if len(p) == 2}, explain=why)
    G.remap_many("competition", merged)
    for a, b in merged:                         # the joined source's own record is this competition (seasons.py keeps its old seasons)
        for src, sid in keys.get(a, ()):
            if src != "fotmob" and not G.c.execute("SELECT 1 FROM xref WHERE type='competition' AND source=? AND source_id=?", (src, str(sid))).fetchone():
                G.xref("competition", b, src, sid, "same-comp")
    for line in why:
        print("  same_comp " + line, flush=True)
    return {"described": made, "made": minted, "merged": len(merged), "competitions": len({k for _, k in merged})}
