"""Linking across sources (spec §3.3): a game in another source is the graph's match when it is on the same date ±1 day
with the same two (already linked) teams; home and away may be swapped (neutral venues are filed either way). A
competition or edition of another source is ours when the matches it holds overwhelmingly sit in one of ours."""
from collections import defaultdict
from datetime import date, timedelta


def _days(d):
    d0 = date.fromisoformat(d[:10])
    return [str(d0), str(d0 - timedelta(days=1)), str(d0 + timedelta(days=1))]


class MatchIndex:
    def __init__(self, G):
        self.by = defaultdict(list)
        for mid, d, h, a in G.c.execute("SELECT mid, substr(date,1,10), home, away FROM match WHERE date IS NOT NULL"):
            self.by[(h, d)].append((mid, a))

    def add(self, mid, d, h, a):
        self.by[(h, d[:10])].append((mid, a))

    def find(self, d, h, a):
        for dd in _days(d):
            for mid, aa in self.by.get((h, dd), ()):
                if aa == a:
                    return mid, False
            for mid, aa in self.by.get((a, dd), ()):
                if aa == h:
                    return mid, True
        return None, None


def twin(G, idx, d, h, a, hs, as_, src):
    """The graph's match for this game, or None. A different score is logged (the graph keeps the higher source's)."""
    mid, swapped = idx.find(d, h, a)
    if mid is None:
        return None
    x, y = (as_, hs) if swapped else (hs, as_)
    kept = G.c.execute("SELECT hs, as_, src FROM match WHERE mid=?", (mid,)).fetchone()
    if kept and None not in (kept[0], x) and (kept[0], kept[1]) != (x, y):
        G.conflict("match", mid, "score", f"{kept[0]}-{kept[1]}", kept[2], f"{x}-{y}", src)
    return mid


def vote_alias(reg, t, votes, src, min_n=20, share=0.9):
    """votes {source key: Counter{tifo id: matches}} -> {source key: tifo id} for keys with min_n votes and share of them
    on one id; each link is written to the registry (a key already naming another entity is left alone)."""
    out = {}
    for k in sorted(votes):
        c = votes[k]
        tot = sum(c.values())
        if not tot:
            continue
        best, n = c.most_common(1)[0]
        if n >= min_n and n >= share * tot and reg.alias(t, src, k, best):
            out[k] = best
    return out
