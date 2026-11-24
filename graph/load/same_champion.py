"""One club, one record, by its titles (the honours side of graph/load/same_club.py, which joins records by their games and
so never sees a record without one). 24 Nov 2026: 365Scores' champion lists made 1,387 club records of their own, each with
titles and no game («Gor Mahia» with 21 Kenyan titles beside the «Gor Mahia» of 764 games; «Petro Luanda» beside «Petro
Atletico»): the club page showed no title, the title hung on a record no page showed, and graph/load/same_comp.py could not
see that the list's champion topped the table of the games.

Rules, for a record with titles and fewer than 5 games (a list's record):
  * its country is the country of the competitions it won (its own country when they have none);
  * a club is a candidate when it played in a competition of that country in the seasons of the titles (a calendar-year
    label may sit a year off a split-season one);
  * the two are one club when the candidate played in 60% of those seasons (2 or more) and the names agree (the same once
    folded, close letter by letter, one inside the other, the same Arabic name, or a name schochastics or RSSSF knows the
    candidate by), or when the candidate topped a league table of the country in 60% of the seasons of the record's
    league titles (3 or more; 75% and 4 or more with no name to go by), or when a club of the country's games has the
    very name, whatever the seasons of its games (a second-division title of a season the games do not hold);
  * one candidate only: two of the same strength and as many tables topped leave the record alone (the same name, then
    a namesake of other seasons, then a name and the tables, then the tables, then a loose name);
  * the strongest pairs are joined first, and a later one is refused when the club then holds another number of the
    record's numbering source or a title of the same champion list (one list never names a club twice);
  * never a record of `ALONE_IDS`, a national team, a reserve or youth side with a first team, a UAE club of the `historic` and `rename` lists or
    a pair graph/team_aliases.yaml keeps `apart`;
  * the record with the games is kept.
Rebuilt in every build and never written to the registry; runs before graph/load/same_comp.py, whose table rule then finds
the list's champions on top of the games' tables."""
import re
from collections import Counter, defaultdict

from graph.countries import canon
from graph.load.same_comp import CUP, end_year
from graph.load.teams import SIDE, alike, apart, fold, guarded, settle_conflicts, squash

ONE_ID = ("fotmob", "tm", "s365", "espn")
GAMES = 5                                  # a record with fewer games is a list's record
SHARE = 0.6
SEASONS, TOPS = 2, 3
ALONE, ALONE_SHARE = 4, 0.75                # the tables with no name to go by
INSIDE, LONG = 5, 8                        # letters of the shorter name inside the other: as whole words, as its start or end
# a list's record that is nobody's namesake: 365Scores' number -> who it is
ALONE_IDS = {"98093": "River Plate FC of Montevideo (1897-1925), not the River Plate of 1932",
             "85141": "Alumni, the champions of 1900-1911, not Boca Alumni",
             "85142": "Porteño, the champions of 1912 and 1914, not Estudiantil Porteño",
             "7116": "Estudiantes of Caseros, not Estudiantes de La Plata",
             "11899": "Talleres of Remedios de Escalada, not Talleres of Córdoba"}
STRENGTH = ("", "loose", "table", "named+table", "namesake", "name")


def names_of(name, keys):
    """A record's names: its own and the ones schochastics and RSSSF know it by («Talleres Cordoba (Argentina)»)."""
    out = [name] if name else []
    for source, sid in keys:
        if source == "sch":
            out.append(re.sub(r"\s*\([^()]*\)\s*$", "", sid))
        elif source == "rsssf-name":
            out.append(sid.split("|", 1)[-1])
    return [n for n in out if n and fold(n)]


def named(a, b, ar_a=None, ar_b=None):
    """0 no, 1 loosely, 2 the same folded name."""
    fa, fb = fold(a), fold(b)
    if not fa or not fb or bool(SIDE.search(fa)) != bool(SIDE.search(fb)):
        return 0
    if fa == fb or squash(a) == squash(b) != "":
        return 2
    if alike(a, b) or (ar_a and not fold(ar_a) and ar_a.strip() == (ar_b or "").strip()):
        return 1
    ja, jb = sorted((squash(a), squash(b)), key=len)
    if len(ja) >= LONG and (jb.startswith(ja) or jb.endswith(ja)):
        return 1
    wa, wb = sorted((set(fa.split()), set(fb.split())), key=len)
    return 1 if len(ja) >= INSIDE and ja in jb and wa <= wb else 0


def candidates(c, never=None, kept=None, explain=None):
    """[(drop, keep)] for one graph's connection (read-only)."""
    q = lambda s, p=(): c.execute(s, p).fetchall()
    team = {tid: (name, name_ar, kind, canon(country)) for tid, name, name_ar, kind, country in q("SELECT tid, name, name_ar, kind, country FROM team")}
    never = apart() if never is None else never
    kept = guarded()[0] if kept is None else kept
    ids, keys = defaultdict(lambda: defaultdict(set)), defaultdict(list)
    for tid, source, sid in q("SELECT tifo_id, source, source_id FROM xref WHERE type='team'"):
        keys[tid].append((source, str(sid)))
        if source in ONE_ID:
            ids[tid][source].add(str(sid))
    comp = {cid: (name, kind, canon(country)) for cid, name, kind, country in q("SELECT cid, name, kind, country FROM competition")}
    league = lambda cid: (comp.get(cid) or (0, 0))[1] not in ("cup", "supercup") and not CUP.search(fold((comp.get(cid) or ("",))[0]))
    games = Counter()
    pts, sides = defaultdict(Counter), defaultdict(set)     # (country, year, cid) -> table; (country, year) -> clubs
    lands = defaultdict(Counter)                # club -> the countries of its games
    for cid, season, h, a, hs, as_ in q("""SELECT e.cid, e.season, m.home, m.away, m.hs, m.as_ FROM match m LEFT JOIN edition e ON e.eid=m.eid
                                           WHERE m.home IS NOT NULL AND m.away IS NOT NULL"""):
        games[h] += 1
        games[a] += 1
        land, y = (comp.get(cid) or (0, 0, None))[2], end_year(season)
        if not land or y is None:
            continue
        sides[(land, y)] |= {h, a}
        lands[h][land] += 1
        lands[a][land] += 1
        if hs is not None and as_ is not None and league(cid):
            t = pts[(land, y, cid)]
            t[h] += 3 if hs > as_ else 1 if hs == as_ else 0
            t[a] += 3 if as_ > hs else 1 if hs == as_ else 0
    home = defaultdict(set)                     # country -> the clubs most of whose games are its own
    for t, n in lands.items():
        home[n.most_common(1)[0][0]].add(t)
    tops = defaultdict(set)                    # (country, year) -> the leaders of its league tables
    for (land, y, cid), t in pts.items():
        if len(t) >= 4:
            tops[(land, y)].add(t.most_common(1)[0][0])
    won, lists = defaultdict(list), defaultdict(set)   # list's record -> [(country, year, a league title?)]; record -> {(list, source)}
    for tid, cid, season, kind, rank, src in q("""SELECT h.tid, e.cid, e.season, h.kind, h.rank, h.src FROM honour h JOIN edition e ON e.eid=h.eid
                                                  WHERE h.tid IS NOT NULL"""):
        if tid not in team:
            continue
        if kind == "champion" and rank == 1:
            lists[tid].add((cid, src))
        if games[tid] >= GAMES or team[tid][2] == "national":
            continue
        y = end_year(season)
        land = (comp.get(cid) or (0, 0, None))[2] or team[tid][3]
        if y and land:
            won[tid].append((land, y, kind == "champion" and rank == 1 and league(cid)))
    alias = {}
    known = lambda t: alias.get(t) or alias.setdefault(t, names_of(team[t][0], keys[t]))
    side = lambda n: bool(SIDE.search(fold(n or "")))
    grade = lambda r: (5 if r[2] else 4) if r[0] == 2 else 3 if r[0] and r[1] else 2 if r[1] else 1
    spelt = {}                                  # country -> {a name, letters only: its clubs with games}
    def namesakes(land, name):
        if land not in spelt:
            spelt[land] = defaultdict(set)
            for t in home[land]:
                if t in team and games[t] >= GAMES and team[t][2] != "national" and team[t][0]:
                    for x in known(t):
                        spelt[land][squash(x)].add(t)
        return spelt[land].get(squash(name), ())
    offers = []                                 # (strength, record, candidate, evidence)
    for g, rows in sorted(won.items()):
        name, name_ar = team[g][0], team[g][1]
        if not name or fold(name) in kept or ids[g]["s365"] & ALONE_IDS.keys():
            continue
        best = {}                               # candidate -> (how named, tables topped, seasons there, seasons, league seasons)
        for sh in (0, 1, -1):
            ys = {(land, y + sh) for land, y, _ in rows if (land, y + sh) in sides}
            ls = {(land, y + sh) for land, y, lg in rows if lg and (land, y + sh) in tops}
            there, top = Counter(), Counter()
            for k in ys:
                there.update(sides[k])
            for k in ls:
                top.update(tops[k])
            for t, n in there.items():
                if t == g or t not in team or games[t] < GAMES or team[t][2] == "national" or not team[t][0]:
                    continue
                how = max(named(name, x, name_ar, team[t][1]) for x in known(t))
                by_name = how and len(ys) >= SEASONS and n >= SHARE * len(ys)
                by_table = len(ls) >= TOPS and top[t] >= max(TOPS, SHARE * len(ls)) and side(name) == side(team[t][0])
                if by_table and not by_name and top[t] < max(ALONE, ALONE_SHARE * len(ls)):
                    by_table = False
                if not (by_name or by_table):
                    continue
                row = (how if by_name else 0, top[t] if by_table else 0, n, len(ys), len(ls))
                if row > best.get(t, (-1,)):
                    best[t] = row
        for land in {land for land, _, _ in rows}:      # the same name in the country, whatever the seasons of its games
            for t in namesakes(land, name):
                if t != g and best.get(t, (0,))[0] < 2 and side(name) == side(team[t][0]):
                    best[t] = (2, best.get(t, (0, 0))[1], 0, len(rows), 0)
        ranked = sorted(best.items(), key=lambda kv: (-grade(kv[1]), -kv[1][1], -kv[1][2]))
        if not ranked:
            continue
        if len(ranked) > 1 and (grade(ranked[0][1]), ranked[0][1][1]) == (grade(ranked[1][1]), ranked[1][1][1]):
            if explain is not None:
                explain.append(f"AMBIGUOUS {g} «{name}»: " + ", ".join(f"{t} «{team[t][0]}»" for t, _ in ranked[:3]))
            continue
        offers.append((grade(ranked[0][1]), g, ranked[0][0], ranked[0][1]))
    out = []
    for strength, g, t, (how, tp, n, ny, nl) in sorted(offers, key=lambda o: (-o[0], -o[3][1], -o[3][2], o[1])):
        name = team[g][0]
        if any(tuple(sorted((fold(name), fold(x)))) in never for x in known(t)) or fold(team[t][0]) in kept:
            continue
        if any(ids[g][s] != ids[t][s] for s in ids[g].keys() & ids[t].keys()):       # two numbers of one source
            continue
        if lists[g] & lists[t]:                 # one champion list names both: two clubs
            continue
        out.append((g, t))
        for s, v in ids[g].items():
            ids[t][s] |= v
        lists[t] |= lists[g]
        if explain is not None:
            explain.append(f"{STRENGTH[strength]}  {g} «{name}» = {t} «{team[t][0]}» there {n}/{ny}, top {tp}/{nl}")
    return sorted(out)


def load(G, reg, S):
    why = []
    merged = candidates(G.c, explain=why)
    G.remap_many("team", merged)
    return {"merged": len(merged), "left": sum(w.startswith("AMBIGUOUS") for w in why), "conflicts_settled": settle_conflicts(G, merged)}
