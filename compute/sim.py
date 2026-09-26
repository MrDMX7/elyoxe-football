"""Monte Carlo season simulator (comp/{id}/sim.json).

Each remaining fixture is drawn home/draw/away from the Tifo rating probabilities (compute/rating.py)
with ratings held at today's values; 10,000 seasons by default. Ties on points are broken by the
CURRENT goal difference, then at random: the simulator does not model goals, so it can differ from
the league's official head-to-head rule. The random generator is seeded from (season, matches
played), so the numbers only change when a result comes in.
Bands (title, Asian places, relegation) come from the standings legend, as for the magic numbers.
"""
import random

from . import rating as R


def simulate(rows, remaining, ratings, params, n=10000, seed=0, legend=None):
    teams = [r["team"]["id"] for r in rows]
    pts0 = {r["team"]["id"]: r["pts"] or 0 for r in rows}
    gd0 = {r["team"]["id"]: r.get("gd") or 0 for r in rows}
    p = {**R.DEFAULTS, **(params or {})}
    base = p["newcomer"]
    fx = []
    for h, a, neutral in remaining:
        if h not in pts0 or a not in pts0:
            continue
        ph, pd, _ = R.probs(ratings.get(h, base), ratings.get(a, base), p, neutral)
        fx.append((h, a, ph, ph + pd))
    rng = random.Random(seed)
    nt = len(teams)
    pos = {t: [0] * nt for t in teams}
    exp = dict.fromkeys(teams, 0.0)
    rnd = rng.random
    for _ in range(n):
        pts = dict(pts0)
        for h, a, c1, c2 in fx:
            u = rnd()
            if u < c1:
                pts[h] += 3
            elif u < c2:
                pts[h] += 1
                pts[a] += 1
            else:
                pts[a] += 3
        order = sorted(teams, key=lambda t: (-pts[t], -gd0[t], rnd()))
        for i, t in enumerate(order):
            pos[t][i] += 1
            exp[t] += pts[t]
    bands = [("title", 1)]
    for lg in legend or []:
        ranks = sorted(lg.get("ranks") or [])
        if ranks:
            key = "relegation" if "releg" in ((lg.get("key") or "") + (lg.get("label") or "")).lower() else f"ranks_{ranks[0]}_{ranks[-1]}"
            bands.append((key, ranks))
    out = {}
    for t in teams:
        dist = [round(c / n, 4) for c in pos[t]]
        row = {"exp_pts": round(exp[t] / n, 1), "positions": dist}
        for key, b in bands:
            ranks = [b] if isinstance(b, int) else b
            row[key] = round(sum(dist[r - 1] for r in ranks if r - 1 < nt), 4)
        out[str(t)] = row
    return {"sims": n, "seed": seed, "remaining_fixtures": len(fx),
            "bands": [{"key": k, "ranks": [b] if isinstance(b, int) else b} for k, b in bands],
            "teams": out,
            "method": "10k seasons; fixtures drawn from Tifo-rating W/D/L probabilities at today's ratings; "
                      "ties: current goal difference, then random (not the official head-to-head rule)"}
