"""Danger index: an xG proxy for competitions where FotMob has no xG (UAE Pro League: "ratings" coverage).

  xg_proxy = b0 + b1*shots_on_target + b2*big_chances + b3*shots_inside_box + b4*corners   (per team, per match)
Fitted by ordinary least squares against FotMob's own team xG on every stored match that has it
(Saudi, Qatar, the big five, UEFA ...), refitted daily, published with its fit statistics in
models/danger.json: n, R^2 against xG, and the correlation with goals scored of the proxy vs real xG.
"""
import math

FEATURES = [("shots_on_target", "ShotsOnTarget"), ("big_chances", "big_chance"),
            ("shots_inside_box", "shots_inside_box"), ("corners", "corners")]


def _rows(ledgers, need_xg):
    for L in ledgers:
        for e in L.values():
            st = e.get("stats") or {}
            if not all(k in st for _, k in FEATURES):
                continue
            xg = st.get("expected_goals")
            if need_xg and not xg:
                continue
            sc = e.get("score") or {}
            for i, side in ((0, "home"), (1, "away")):
                x = [st[k][i] for _, k in FEATURES]
                if any(v is None for v in x):
                    continue
                yield x, (xg[i] if xg else None), sc.get(side)


def _solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-12:
            return None
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [a - f * bb for a, bb in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


def _corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = math.sqrt(sum((x - ma) ** 2 for x in a))
    vb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb) if va and vb else None


def fit(ledgers, min_rows=200):
    data = list(_rows(ledgers, True))
    if len(data) < min_rows:
        return None
    X = [[1.0] + [float(v) for v in x] for x, _, _ in data]
    y = [float(t) for _, t, _ in data]
    k = len(X[0])
    A = [[sum(r[i] * r[j] for r in X) for j in range(k)] for i in range(k)]
    b = [sum(r[i] * t for r, t in zip(X, y)) for i in range(k)]
    coef = _solve(A, b)
    if not coef:
        return None
    pred = [sum(c * v for c, v in zip(coef, r)) for r in X]
    my = sum(y) / len(y)
    ss_res = sum((t - p_) ** 2 for t, p_ in zip(y, pred))
    ss_tot = sum((t - my) ** 2 for t in y)
    goals = [g for _, _, g in data]
    ok = [i for i, g in enumerate(goals) if g is not None]
    return {"intercept": round(coef[0], 4), "coef": {name: round(c, 4) for (name, _), c in zip(FEATURES, coef[1:])},
            "n_team_matches": len(y), "r2_vs_xg": round(1 - ss_res / ss_tot, 3) if ss_tot else None,
            "corr_goals_proxy": round(_corr([pred[i] for i in ok], [goals[i] for i in ok]) or 0, 3),
            "corr_goals_xg": round(_corr([y[i] for i in ok], [goals[i] for i in ok]) or 0, 3)}


def proxy(stats, i, model):
    x = [(stats.get(k) or [None, None])[i] for _, k in FEATURES]
    if any(v is None for v in x):
        return None
    v = model["intercept"] + sum(model["coef"][name] * xi for (name, _), xi in zip(FEATURES, x))
    return round(max(0.0, v), 3)


def with_proxy_xg(ledger, model):
    """Copy of the ledger where matches without xG get {"home","away"} proxies (and nothing else changes)."""
    out = {}
    for k, e in ledger.items():
        if not e.get("xg") and e.get("stats"):
            h, a = proxy(e["stats"], 0, model), proxy(e["stats"], 1, model)
            if h is not None and a is not None:
                e = {**e, "xg": {"home": h, "away": a}}
        out[k] = e
    return out
