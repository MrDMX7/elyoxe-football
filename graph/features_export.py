"""Tifo archive: what one pass over every match gives (24 Nov 2026: 1,516,772 matches, 147,399 pairs of teams) — the files of
the archive job's feature pages (site/archive/features.cjs), written next to graph/archive_export.py's.

  vs/names.json          {tid: [name, FotMob id or 0, 1 for a national team]} of every team in a file below
  vs/pairs/<n>.json      {"<lo>-<hi>": [[day, competition, season, 1 when lo is at home, home goals, away goals, Tifo match id,
                         FotMob match id or 0, (home kicks, away kicks)], ...]} oldest first, for the pairs that met `min_pair`
                         times; n = lo % SHARDS. A competition is the number its season files carry (archive_export.PUB).
  vs/teams/<n>.json      {tid: {tot: [p, w, d, l, gf, ga], first, last, opp: [[opponent, p, w, d, l, gf, ga], ...],
                         run: {win|unbeaten|lost|winless|scored|clean: [games, from, to]}, elo: {now, peak: [v, day],
                         low: [v, day], yr: [[year, rating at its end], ...]}}} for the teams of `min_team` games
  elo/nations.json       {now: [[tid, rating, peak, day of the peak, games], ...], peaks: [[tid, peak, day], ...]}
  elo/leagues.json       {competition: [[tid, rating, peak, day of the peak], ...]} the sides of each league's latest season
  vs/index.json          {pairs: {"<lo>-<hi>": meetings}, hubs: {tid: games}} what has a file above: the pages to link

One meeting a day (two sources, one match). The rating is World Football Elo's: r += K * G * (S - E), E from the two ratings
and the home side's 100 (60 between clubs, none at a finals), G the goal difference's weight; K is 20 between clubs and for a
friendly, 30 to 60 for the national teams' competitions, and double in a side's first 30 games (every side starts at 1500).
"""
import json
import os
import re
from collections import defaultdict

SHARDS = 500
BASE, PROVISIONAL = 1500.0, 30
MAJOR = re.compile(r"^(?:uefa )?euro$|^copa am[eé]rica$|^africa cup of nations$|^asian cup$|gold cup$|^concacaf championship$|^oceania nations cup$|confederations cup$", re.I)
NOT_SENIOR = re.compile(r"\d|\(W\)|women|olympic|amateur|\bB\b", re.I)
RUNS = ("win", "unbeaten", "lost", "winless", "scored", "clean")


def _dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def weight(name, kind, scope, national):
    """(K, the home side's points) of a match of this competition"""
    if not national:
        return 20, 0 if kind == "supercup" else 60
    n = (name or "").strip()
    if re.search(r"friendl", n, re.I) or kind == "friendly":
        return 20, 100
    if re.search(r"qualif", n, re.I):
        return 40, 100
    if scope == "world" and re.fullmatch(r"(?:fifa )?world cup", n, re.I):
        return 60, 0
    if MAJOR.search(n):
        return 50, 0
    return 30, 100


def gd_weight(gd):
    gd = abs(gd)
    return 1.0 if gd <= 1 else 1.5 if gd == 2 else (11 + gd) / 8


class Side:
    __slots__ = ("r", "n", "peak", "low", "yr", "tot", "first", "last", "cur", "best")

    def __init__(self):
        self.r, self.n, self.peak, self.low, self.yr = BASE, 0, None, None, []
        self.tot, self.first, self.last = [0, 0, 0, 0, 0, 0], None, None
        self.cur = {k: [0, None] for k in RUNS}        # the run now: games, its first day
        self.best = {}

    def played(self, day, f, a):
        t = self.tot
        t[0] += 1
        t[1 if f > a else 2 if f == a else 3] += 1
        t[4] += f
        t[5] += a
        self.first, self.last = self.first or day, day
        on = {"win": f > a, "unbeaten": f >= a, "lost": f < a, "winless": f <= a, "scored": f > 0, "clean": a == 0}
        for k in RUNS:
            c = self.cur[k]
            if on[k]:
                c[0] += 1
                c[1] = c[1] or day
                b = self.best.get(k)
                if b is None or c[0] > b[0]:
                    self.best[k] = [c[0], c[1], day]
            else:
                c[0], c[1] = 0, None

    def rated(self, day, r):
        self.r, self.n = r, self.n + 1
        y = int(day[:4])
        if self.yr and self.yr[-1][0] == y:
            self.yr[-1][1] = round(r)
        else:
            self.yr.append([y, round(r)])
        if self.n >= PROVISIONAL:
            if self.peak is None or r > self.peak[0]:
                self.peak = [round(r), day]
            if self.low is None or r < self.low[0]:
                self.low = [round(r), day]


def versus(G, out, min_pair=2, min_team=30):
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    fm = lambda t: {a: int(b) for a, b in q(f"SELECT tifo_id, source_id FROM xref WHERE type='{t}' AND source='fotmob'") if str(b).isdigit()}
    fm_c, fm_t, fm_m = fm("competition"), fm("team"), fm("match")
    team = {t: (a or n, k == "national", n or "") for t, n, a, k in q("SELECT tid, name, name_ar, kind FROM team")}
    comp = {c: (n, k, s) for c, n, k, s in q("SELECT cid, name, kind, scope FROM competition")}
    ed = {e: (c, s) for e, c, s in q("SELECT eid, cid, season FROM edition")}
    sides, pairs, seen = defaultdict(Side), defaultdict(list), set()
    opp = defaultdict(dict)
    latest = {}                                    # a league's latest season: cid -> [last day, eid, its sides]
    for mid, eid, day, h, a, hs, as_, ph, pa in q("""SELECT mid, eid, substr(date,1,10), home, away, hs, as_, pen_h, pen_a FROM match
            WHERE hs IS NOT NULL AND as_ IS NOT NULL AND length(date) >= 10 AND home IS NOT NULL AND away IS NOT NULL AND home <> away ORDER BY date, mid"""):
        lo, hi = (h, a) if h < a else (a, h)
        if (day, lo, hi) in seen or h not in team or a not in team:
            continue
        seen.add((day, lo, hi))
        cid, season = ed.get(eid, (None, None))
        name, kind, scope = comp.get(cid, (None, None, None))
        row = [day, fm_c.get(cid, 0), season or "", 1 if h == lo else 0, hs, as_, mid, fm_m.get(mid, 0) if fm_m.get(mid, 0) < 2_000_000_000 else 0]
        if ph is not None and pa is not None:
            row += [ph, pa]
        pairs[(lo, hi)].append(row)
        H, A = sides[h], sides[a]
        H.played(day, hs, as_)
        A.played(day, as_, hs)
        for me, op, f, ag in ((h, a, hs, as_), (a, h, as_, hs)):
            o = opp[me].get(op)
            if o is None:
                o = opp[me][op] = [op, 0, 0, 0, 0, 0, 0]
            o[1] += 1
            o[2 if f > ag else 3 if f == ag else 4] += 1
            o[5] += f
            o[6] += ag
        k, home = weight(name, kind, scope, team[h][1] and team[a][1])
        e = 1 / (1 + 10 ** (-(H.r + home - A.r) / 400))
        s = 1.0 if hs > as_ else 0.5 if hs == as_ else 0.0
        d = k * gd_weight(hs - as_) * (s - e)
        H.rated(day, H.r + d * (2 if H.n < PROVISIONAL else 1))
        A.rated(day, A.r - d * (2 if A.n < PROVISIONAL else 1))
        if kind == "league" and cid in fm_c:
            L = latest.get(cid)
            if L is None or L[1] != eid:
                L = latest[cid] = [day, eid, set()]
            L[0] = day
            L[2].update((h, a))
    today = max((s.last for s in sides.values()), default="")
    names, kept = {}, 0

    def named(t):
        names[t] = [team[t][0] or "", fm_t.get(t, 0), 1 if team[t][1] else 0]

    shards, index = defaultdict(dict), {"pairs": {}, "hubs": {}}
    for (lo, hi), ms in pairs.items():
        if len(ms) >= min_pair:
            shards[lo % SHARDS][f"{lo}-{hi}"] = ms
            index["pairs"][f"{lo}-{hi}"] = len(ms)
            named(lo)
            named(hi)
            kept += 1
    for n, d in shards.items():
        _dump(os.path.join(out, "vs", "pairs", f"{n}.json"), d)
    shards, hubs = defaultdict(dict), 0
    for t, s in sides.items():
        if s.tot[0] < min_team:
            continue
        rows = sorted(opp[t].values(), key=lambda r: (-r[1], r[0]))
        for r in rows:
            named(r[0])
        named(t)
        shards[t % SHARDS][str(t)] = {"tot": s.tot, "first": s.first, "last": s.last, "opp": rows,
                                      "run": {k: v for k, v in s.best.items() if v[0] >= 3},
                                      "elo": {"now": round(s.r), "peak": s.peak, "low": s.low, "yr": s.yr}}
        index["hubs"][str(t)] = s.tot[0]
        hubs += 1
    for n, d in shards.items():
        _dump(os.path.join(out, "vs", "teams", f"{n}.json"), d)
    since = lambda years: f"{int(today[:4]) - years}{today[4:]}" if today else ""
    senior = [t for t, s in sides.items() if team[t][1] and s.peak and not NOT_SENIOR.search(team[t][2])]
    now = sorted(([t, round(sides[t].r), sides[t].peak[0], sides[t].peak[1], sides[t].n] for t in senior if sides[t].last >= since(4)), key=lambda r: (-r[1], r[0]))
    peaks = sorted(([t] + sides[t].peak for t in senior), key=lambda r: (-r[1], r[2]))[:100]
    for r in now + peaks:
        named(r[0])
    _dump(os.path.join(out, "elo", "nations.json"), {"day": today, "now": now, "peaks": peaks})
    leagues = {}
    for cid, (day, eid, ts) in latest.items():
        if day < since(2) or len(ts) < 6:
            continue
        rows = sorted(([t, round(sides[t].r)] + (sides[t].peak or [None, None]) for t in ts), key=lambda r: (-r[1], r[0]))
        for r in rows:
            named(r[0])
        leagues[str(fm_c[cid])] = rows
    _dump(os.path.join(out, "elo", "leagues.json"), leagues)
    _dump(os.path.join(out, "vs", "names.json"), {str(t): v for t, v in names.items()})
    _dump(os.path.join(out, "vs", "index.json"), index)
    return {"pairs": kept, "team_hubs": hubs, "rated_nations": len(now), "rated_leagues": len(leagues)}
