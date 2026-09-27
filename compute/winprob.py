"""In-game win probability: `winprob: [[minute, pH, pD, pA], ...]` in match/{id}.json.

Model (independent Poisson remaining goals):
  1. From the pre-match W/D/L probabilities (Tifo club rating, national Elo, else league base rates)
     solve the full-match goal rates (lam_h, lam_a) whose Poisson outcome probabilities match them
     (grid search, total goals fixed at the league mean 2.7 when the probabilities are the base-rate prior).
  2. At minute t with score (h, a): remaining rates = lam x (T - t) / T with T = 93 (average stoppage),
     each red card scales the carded team's rate by 0.70 and the opponent's by 1.20 (per card).
  3. P(final result) = P(h + X > a + Y) etc. with X ~ Poisson(rem_h), Y ~ Poisson(rem_a).
The whole curve is rebuilt from the event list at every poll (deterministic, no stored state), one
point per minute and one at every goal or red card, so finished matches get the same curve.
Extra time and penalties are not modelled: the curve stops at 90+.
"""
import math

T = 93.0
PRIOR = (0.45, 0.26, 0.29)       # home/draw/away base rates (UAE Pro League 2010-2022: 0.434/0.230/0.336)
RED_OWN, RED_OPP = 0.70, 1.20


def _pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def outcome(h, a, rem_h, rem_a, cap=10):
    ph = [_pois(i, rem_h) for i in range(cap + 1)]
    pa = [_pois(i, rem_a) for i in range(cap + 1)]
    w = d = 0.0
    for i in range(cap + 1):
        for j in range(cap + 1):
            p = ph[i] * pa[j]
            if h + i > a + j:
                w += p
            elif h + i == a + j:
                d += p
    s = w + d
    return w, d, max(0.0, 1 - s)


_CACHE = {}


def rates(p3):
    """(pH, pD, pA) -> (lam_h, lam_a) by grid search on total goals and share."""
    key = tuple(round(x, 3) for x in p3)
    if key in _CACHE:
        return _CACHE[key]
    best = None
    for tot in [x / 10 for x in range(16, 41, 2)]:
        for sh in [x / 100 for x in range(20, 81, 2)]:
            lh, la = tot * sh, tot * (1 - sh)
            w, d, l_ = outcome(0, 0, lh, la, cap=8)
            err = (w - p3[0]) ** 2 + (d - p3[1]) ** 2 + (l_ - p3[2]) ** 2
            if best is None or err < best[0]:
                best = (err, lh, la)
    _CACHE[key] = (best[1], best[2])
    return _CACHE[key]


def curve(events, prematch=None, upto=None):
    """events: normalized match events; upto: current minute (live) or None (finished: to 90)."""
    p3 = prematch or PRIOR
    lh, la = rates(p3)
    marks = []      # (minute, kind, side)
    for e in events or []:
        t = e.get("type")
        side = e.get("team")
        if side not in ("home", "away") or e.get("minute") is None:
            continue
        m = min(90, e["minute"]) + (0.01 * (e.get("added") or 0))
        if t in ("goal", "penalty_goal", "own_goal"):
            sc = e.get("score")
            marks.append((m, "goal", sc))
        elif t in ("red", "second_yellow"):
            marks.append((m, "red", side))
    marks.sort(key=lambda x: x[0])
    end = 90 if upto is None else max(0, min(90, int(upto)))
    pts, h = [], 0
    a = 0
    reds = {"home": 0, "away": 0}
    mi = 0

    def point(t):
        f = max(0.0, T - t) / T
        rh = lh * f * (RED_OWN ** reds["home"]) * (RED_OPP ** reds["away"])
        ra = la * f * (RED_OWN ** reds["away"]) * (RED_OPP ** reds["home"])
        w, d, l_ = outcome(h, a, rh, ra)
        return [round(t, 2), round(w, 3), round(d, 3), round(l_, 3)]

    pts.append([0, round(p3[0], 3), round(p3[1], 3), round(p3[2], 3)])
    for minute in range(1, end + 1):
        while mi < len(marks) and marks[mi][0] <= minute:
            m, kind, x = marks[mi]
            if kind == "goal":
                if x:
                    h, a = x["home"], x["away"]
            else:
                reds[x] += 1
            pts.append(point(m))
            mi += 1
        pts.append(point(minute))
    return pts
