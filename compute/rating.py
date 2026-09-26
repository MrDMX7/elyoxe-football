"""Tifo rating: an Elo-style strength rating for UAE clubs, and pre-match W/D/L probabilities.

Data: every UAE club match FotMob has (Pro League 2010/11 onward, President's Cup 2018/19+, League
Cup and Super Cup 2025/26+), in kickoff order. No free machine-readable source goes further back
(TheSportsDB's free tier caps lists at 5 rows; ESPN and openfootball have no UAE league), so the
rating starts in August 2010 with every club at BASE.

Update (World Football Elo style): r += K * G * (S - E), with
  E = 1 / (1 + 10^(-(r_home + H - r_away) / 400)), H = home advantage (0 at neutral venues:
  the Super Cup and cup finals), S = 1 / 0.5 / 0, G = goal-difference multiplier
  (1 for 0-1 goals, 1.5 for 2, (11 + n) / 8 for n >= 3).
Between seasons every rating moves REGRESS of the way back to BASE. A club seen for the first time
(promoted) starts at NEWCOMER.
Probabilities: draw = D0 * exp(-(d / S)^2) with d = r_home + H - r_away (draws are likeliest between
equals); home = E - draw / 2, away = 1 - E - draw / 2 (floored at 2 %, renormalized).
Parameters are fitted offline by tools/calibrate_rating.py (out-of-sample Brier) and stored in
competitions.yaml `rating:`.
"""
import math

DEFAULTS = {"base": 1500, "newcomer": 1420, "k": 24, "home": 70, "regress": 0.25, "d0": 0.30, "ds": 350}
UAE_CLUB_COMPS = (538, 11027, 9943, 11026)


def gd_mult(gd):
    gd = abs(gd)
    return 1 if gd <= 1 else 1.5 if gd == 2 else (11 + gd) / 8


def probs(r_home, r_away, p, neutral=False):
    d = r_home + (0 if neutral else p["home"]) - r_away
    e = 1 / (1 + 10 ** (-d / 400))
    draw = p["d0"] * math.exp(-(d / p["ds"]) ** 2)
    h, a = e - draw / 2, 1 - e - draw / 2
    h, a, draw = max(h, 0.02), max(a, 0.02), max(draw, 0.02)
    s = h + draw + a
    return h / s, draw / s, a / s


def is_neutral(m):
    return m.get("comp") == 11026 or str(m.get("round") or "").lower() == "final"


def season_key(m):
    return m.get("season") or ""


def run(matches, p=None, predict_from=None):
    """matches: slim dicts {id, ko, comp, season, round, h, a, hs, as} (finished only), any order.
    Returns (ratings, history, predictions) where predictions are pre-match probabilities for matches
    with ko >= predict_from: [{id, ko, p: (h, d, a), outcome: 0/1/2}]."""
    p = {**DEFAULTS, **(p or {})}
    ratings, history, preds = {}, {}, []
    last_season = None
    ordered = sorted(matches, key=lambda m: (m["ko"] or "", m["id"]))
    first_season = season_key(ordered[0]) if ordered else None
    for m in ordered:
        s = season_key(m)
        if last_season is not None and s != last_season and s > last_season:
            for t in ratings:
                ratings[t] += p["regress"] * (p["base"] - ratings[t])
        last_season = s if last_season is None or s > last_season else last_season
        h, a = m["h"], m["a"]
        start = p["base"] if s == first_season else p["newcomer"]
        rh = ratings.setdefault(h, start)
        ra = ratings.setdefault(a, start)
        neutral = is_neutral(m)
        ph, pd, pa = probs(rh, ra, p, neutral)
        outcome = 0 if m["hs"] > m["as"] else 1 if m["hs"] == m["as"] else 2
        if predict_from is None or (m["ko"] or "") >= predict_from:
            preds.append({"id": m["id"], "ko": m["ko"], "season": s, "h": h, "a": a, "p": (ph, pd, pa), "outcome": outcome})
        e = 1 / (1 + 10 ** (-(rh + (0 if neutral else p["home"]) - ra) / 400))
        sc = 1 if outcome == 0 else 0.5 if outcome == 1 else 0
        delta = p["k"] * gd_mult(m["hs"] - m["as"]) * (sc - e)
        ratings[h] = rh + delta
        ratings[a] = ra - delta
        for t, r in ((h, ratings[h]), (a, ratings[a])):
            history.setdefault(t, []).append([m["ko"][:10] if m["ko"] else None, round(r, 1), m["id"]])
    return ratings, history, preds


def brier(preds):
    """Mean 3-class Brier score (sum over home/draw/away of squared error; 0 = perfect, 2 = worst)."""
    if not preds:
        return None
    tot = 0.0
    for x in preds:
        y = [0, 0, 0]
        y[x["outcome"]] = 1
        tot += sum((x["p"][i] - y[i]) ** 2 for i in range(3))
    return tot / len(preds)


def base_rate_brier(train, test):
    n = len(train) or 1
    f = [sum(1 for x in train if x["outcome"] == i) / n for i in range(3)]
    return brier([{"p": f, "outcome": x["outcome"]} for x in test]), f


def expected_points(p3, side):
    ph, pd, pa = p3
    return 3 * (ph if side == "home" else pa) + pd
