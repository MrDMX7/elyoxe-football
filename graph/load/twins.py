"""One game held twice (after the team merges, graph/load/teams.py and people): two records of one day with the same two teams
and the same score were one game the loaders could not tie while its teams were still two records (2,373 on 21 Nov: FotMob
and RSSSF, RSSSF and schochastics…). The better source's record is kept (graph.db SRC_RANK, then the fuller one); it takes
what only the other has (a round, a lineup, a man of the match), never a second copy of what it holds (no goal counted
twice). Other scores, or three records on one day, stay as they are: two games (Argentina–Uruguay, 15 August 1916)."""
from collections import defaultdict
from graph.db import SRC_RANK

DETAIL = ("event", "appearance", "match_coach", "match_award")


def load(G, reg, S):
    groups = defaultdict(list)
    for mid, day, h, a, hs, as_, src in G.c.execute("SELECT mid, substr(date,1,10), home, away, hs, as_, src FROM match WHERE date IS NOT NULL AND hs IS NOT NULL"):
        lo, hi = min(h, a), max(h, a)
        groups[(day, lo, hi)].append((mid, (hs, as_) if h == lo else (as_, hs), src))
    held = defaultdict(int)
    for t in DETAIL:
        for mid, n in G.c.execute(f"SELECT mid, count(*) FROM {t} GROUP BY mid"):
            held[mid] += n
    home = dict(G.c.execute("SELECT mid, home FROM match"))
    pairs, turned = [], []
    for ms in groups.values():
        if len(ms) != 2 or ms[0][1] != ms[1][1]:
            continue
        keep, drop = sorted(ms, key=lambda m: (SRC_RANK.get(m[2], 9), -held.get(m[0], 0), m[0]))
        pairs.append((drop[0], keep[0]))
        if home[drop[0]] != home[keep[0]]:
            turned.append((drop[0],))
    # a record filed the other way round is turned first (its sides with it), so the merge sees no false disagreement
    G.c.executemany("UPDATE match SET home=away, away=home, hs=as_, as_=hs, ht_h=ht_a, ht_a=ht_h, pen_h=pen_a, pen_a=pen_h WHERE mid=?", turned)
    for t in ("event", "match_coach"):        # through «x»: match_coach holds one row a side, so h and a never swap in one pass
        for a, b in (("h", "x"), ("a", "h"), ("x", "a")):
            G.c.executemany(f"UPDATE {t} SET side='{b}' WHERE mid=? AND side='{a}'", turned)
    for t in DETAIL:                          # what the kept record holds already is never copied: a goal counted once
        G.c.executemany(f"DELETE FROM {t} WHERE mid=? AND EXISTS(SELECT 1 FROM {t} k WHERE k.mid=?)", pairs)
    G.remap_many("match", pairs)
    return {"merged": len(pairs)}
