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
        if n >= min_n and n >= share * tot:
            got = reg.link(t, src, k, best)
            if got is not None:
                out[k] = got
    return out


def vote_teams(G, reg, src, games, min_n=5, lead=3, since=None):
    """Link another source's team keys to the graph's FotMob teams by their games, never by name (db/history.py's rule):
    a game on the same date ±1 day with the same score as a FotMob match votes «home key = that match's home» and the same
    for away; a game with one side already linked only counts the FotMob matches of that team. A key and a team are linked
    when each is the other's first choice with min_n votes and lead × the runner-up's. games: [(date, home key, away key,
    hs, as_)]. Returns {key: tifo id} for the new links (written to the registry)."""
    from collections import Counter
    by = defaultdict(list)
    for d, h, a, hs, as_ in G.c.execute("SELECT substr(date,1,10), home, away, hs, as_ FROM match WHERE src='fotmob' AND hs IS NOT NULL"):
        by[(d, hs, as_)].append((h, a))
    votes = defaultdict(Counter)
    for d, hk, ak, hs, as_ in games:
        if hs is None or as_ is None or (since and str(d)[:10] < since):
            continue
        # a key counts as linked only when another source names its entity: the loader's own mints still vote
        lh = reg.get("team", src, hk) if reg.linked("team", src, hk) else None
        la = reg.get("team", src, ak) if reg.linked("team", src, ak) else None
        if lh and la:
            continue
        for dd in _days(str(d)):
            for h, a in by.get((dd, hs, as_), ()):
                if (lh and lh != h) or (la and la != a):
                    continue
                if not lh:
                    votes[hk][h] += 1
                if not la:
                    votes[ak][a] += 1
    best_of_team = defaultdict(Counter)
    for k, c in votes.items():
        for t, n in c.items():
            best_of_team[t][k] = n
    out = {}
    for k in sorted(votes, key=str):
        top = votes[k].most_common(2)
        t, n = top[0]
        second = top[1][1] if len(top) > 1 else 0
        if n < min_n or n < lead * second:
            continue
        tt = best_of_team[t].most_common(2)
        if tt[0][0] != k or (len(tt) > 1 and tt[0][1] < lead * tt[1][1]):
            continue
        got = reg.link("team", src, k, t)
        if got is not None:
            out[k] = got
    return out
