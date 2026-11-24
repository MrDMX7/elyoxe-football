"""One club, one record, by its name in its own league or by its name and its men (after graph/load/comp_meta.py, when every competition has its country):
graph/load/same_club.py joins two records by the games both hold, so two records of one club whose games never fall on one
day stayed two — RSSSF's «MA Hussein Dey» and «MA Hussein-Dey», «Al-Ramtha» and «Al Ramtha» of Jordan's league, schochastics'
two «Police FC» of Trinidad, Transfermarkt's cup ties of «Alemannia Aachen» beside FotMob's league seasons.

Rules:
  * the same name letter for letter once accents, case and punctuation are gone;
  * both have a game in one competition of one country (a league or a cup: two clubs of one name in two countries meet in
    a continental cup, never in a domestic one), or the same men are on both books (a transfer, a spell or a line-up: the
    club Transfermarkt's transfers name and the one FotMob's games name) — two men, or one where he is a quarter of the
    smaller book; a name of one word («Nacional») needs three and the quarter;
  * no record of the one ever met a record of the other;
  * clubs only; two numbers of one numbering source are two clubs; the guards of graph/load/same_club.py hold (a UAE
    historic club, a club FotMob keeps under a later name, a pair graph/team_aliases.yaml keeps apart);
  * the FotMob record is kept, else the better source's, else the lower id;
  * a record with no game and no man (an honour roll's «Olaria», a table's «JS Bordj-Menaïel») is the one club of its name
    that has them, when no other club carries the name and the country of the one is not against the other's; a name of
    one word needs its country known.
graph/load/twins_last.py then makes each game held twice one."""
import re
import unicodedata
from collections import defaultdict

from graph.db import SRC_RANK
from graph.load.comp_meta import lands
from graph.load.same_club import ONE_ID
from graph.load.teams import _country, apart, guarded, settle_conflicts
from graph.load.teams import fold as loose


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def candidates(c, era=None, never=None, kept=None):
    q = lambda s, p=(): c.execute(s, p).fetchall()
    team = {tid: (name, src) for tid, name, src in q("SELECT tid, name, src FROM team WHERE ifnull(kind, 'club') != 'national'")}
    kept = guarded()[0] if kept is None else kept
    if era is None:
        era = {t for (t,) in q(f"""SELECT tifo_id FROM xref WHERE type='team' AND source='fotmob' AND source_id IN
                                   ({','.join(repr(str(e)) for e in guarded()[1]) or "''"})""")}
    never = apart() if never is None else never
    ids = defaultdict(lambda: defaultdict(set))
    for tid, source, sid in q("SELECT tifo_id, source, source_id FROM xref WHERE type='team'"):
        if source in ONE_ID:
            ids[tid][source].add(sid)
    home = {eid: (cid, country) for eid, cid, country in q("""SELECT e.eid, e.cid, c.country FROM edition e JOIN competition c ON c.cid = e.cid
                                          WHERE ifnull(c.country, '') != '' AND c.kind IN ('league', 'cup', 'supercup')""")}
    plays, met, land, en = defaultdict(set), set(), defaultdict(set), lands()[0]
    for eid, h, a in q("SELECT eid, home, away FROM match WHERE home IS NOT NULL AND away IS NOT NULL"):
        met.add((h, a) if h < a else (a, h))
        if eid in home:
            for t in (h, a):
                plays[t].add(home[eid][0])
                land[t].add(_country(en.get(home[eid][1], home[eid][1])))
    men = defaultdict(set)
    for sql in ("SELECT from_tid, pid FROM transfer", "SELECT to_tid, pid FROM transfer", "SELECT tid, pid FROM spell", "SELECT DISTINCT tid, pid FROM appearance"):
        for tid, pid in q(sql):
            if tid in team and pid is not None:
                men[tid].add(pid)

    def same_men(a, b, key):
        n, least = len(men[a] & men[b]), min(len(men[a]), len(men[b]))
        return n >= 3 and n * 4 >= least if " " not in key else n >= 2 or (n == 1 and least <= 4)

    by = defaultdict(list)
    for tid, (name, _) in sorted(team.items()):
        if (tid in plays or tid in men) and tid not in era and fold(name) and loose(name) not in kept:
            by[fold(name)].append(tid)
    out = []
    for key, tids in sorted(by.items()):
        if len(tids) < 2 or (loose(key), loose(key)) in never:
            continue
        groups = []
        for t in tids:
            for g in groups:
                if (any(plays[t] & plays[m] or same_men(t, m, key) for m in g) and not any(((t, m) if t < m else (m, t)) in met for m in g)
                        and not any(ids[t][s] != ids[m][s] for m in g for s in ids[t].keys() & ids[m].keys())):
                    g.append(t)
                    break
            else:
                groups.append([t])
        for g in groups:
            if len(g) > 1:
                keep = min(g, key=lambda t: ("fotmob" not in ids[t], SRC_RANK.get(team[t][1], 9), t))
                out += [(t, keep) for t in g if t != keep]
    one = dict(out)
    own = {tid: _country(country) for tid, country in q("SELECT tid, country FROM team WHERE ifnull(country, '') != ''")}
    for tid, country in own.items():
        land[tid].add(country)
    for t, keep in out:
        land[keep] |= land[t]
    idle = defaultdict(list)
    for tid, (name, _) in sorted(team.items()):
        if tid not in plays and tid not in men and tid not in era and fold(name) and loose(name) not in kept:
            idle[fold(name)].append(tid)
    for key, tids in sorted(idle.items()):
        clubs = {one.get(t, t) for t in by.get(key, ())}
        if len(clubs) != 1 or (loose(key), loose(key)) in never:
            continue
        keep = clubs.pop()
        for t in tids:
            if (not (t in own and land[keep] and own[t] not in land[keep]) and (" " in key or t in own)
                    and not any(ids[t][s] != ids[keep][s] for s in ids[t].keys() & ids[keep].keys())):
                out.append((t, keep))
    return sorted(out)


def load(G, reg, S):
    merged = candidates(G.c)
    G.remap_many("team", merged)
    return {"merged": len(merged), "clubs": len({k for _, k in merged}), "conflicts_settled": settle_conflicts(G, merged)}
