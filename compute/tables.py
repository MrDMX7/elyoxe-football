"""Table tools: live table, final-round scenarios, position-by-round (bump chart)."""
import itertools

ORDER_NOTE = "computed: points, goal difference, goals for (the official tie-break may differ)"


def _key(r):
    return (-r["pts"], -((r.get("gf") or 0) - (r.get("ga") or 0)), -(r.get("gf") or 0))


def live_table(rows, live_scores):
    """rows: standings rows (FotMob already counts a live match in `played`/`pts` with the score in
    `ongoing`); live_scores {match_id: {"home","away"}} newer than the table fetch.
    -> rows adjusted to the newer scores and re-ordered; rank_before = the table's rank."""
    out = []
    for r in rows:
        r = dict(r)
        og = r.get("ongoing")
        new = live_scores.get(og["match"]) if og and og.get("match") else None
        if og and new and (new["home"], new["away"]) != (og.get("hs"), og.get("as")):
            side = "home" if og["home"] == r["team"]["id"] else "away"
            f_old, a_old = (og["hs"], og["as"]) if side == "home" else (og["as"], og["hs"])
            f_new, a_new = (new["home"], new["away"]) if side == "home" else (new["away"], new["home"])
            pts = lambda f, a: 3 if f > a else 1 if f == a else 0  # noqa: E731
            r["pts"] = (r["pts"] or 0) - pts(f_old or 0, a_old or 0) + pts(f_new, a_new)
            r["gf"] = (r.get("gf") or 0) - (f_old or 0) + f_new
            r["ga"] = (r.get("ga") or 0) - (a_old or 0) + a_new
            r["gd"] = r["gf"] - r["ga"]
        r["rank_before"] = r["rank"]
        out.append(r)
    out.sort(key=_key)
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out


def scenarios(rows, remaining, max_matches=8, legend=None):
    """Enumerate every W/D/L combination of the remaining fixtures (<= max_matches, 3^8 = 6561).
    Per team: best and worst possible final position (ties on points counted both ways), and for a
    team with remaining games, the range given each result of its NEXT game."""
    fx = [(h, a) for h, a in remaining]
    if not fx or len(fx) > max_matches:
        return None
    teams = [r["team"]["id"] for r in rows]
    pts0 = {r["team"]["id"]: r["pts"] or 0 for r in rows}
    if any(h not in pts0 or a not in pts0 for h, a in fx):
        return None
    best = {t: len(teams) for t in teams}
    worst = dict.fromkeys(teams, 1)
    nxt = {}
    for t in teams:
        for i, (h, a) in enumerate(fx):
            if t in (h, a):
                nxt[t] = i
                break
    cond = {t: {"W": [99, 0], "D": [99, 0], "L": [99, 0]} for t in nxt}
    for outcome in itertools.product((0, 1, 2), repeat=len(fx)):
        pts = dict(pts0)
        for (h, a), o in zip(fx, outcome):
            if o == 0:
                pts[h] += 3
            elif o == 1:
                pts[h] += 1
                pts[a] += 1
            else:
                pts[a] += 3
        for t in teams:
            above = sum(1 for u in teams if pts[u] > pts[t])
            tied = sum(1 for u in teams if u != t and pts[u] == pts[t])
            b, w = above + 1, above + tied + 1
            best[t] = min(best[t], b)
            worst[t] = max(worst[t], w)
            if t in nxt:
                h, a = fx[nxt[t]]
                o = outcome[nxt[t]]
                res = "D" if o == 1 else ("W" if (o == 0) == (t == h) else "L")
                c = cond[t][res]
                c[0], c[1] = min(c[0], b), max(c[1], w)
    return {"remaining": [{"home": h, "away": a} for h, a in fx], "combinations": 3 ** len(fx),
            "teams": {str(t): {"best": best[t], "worst": worst[t],
                               "next_result": ({k: {"best": v[0], "worst": v[1]} for k, v in cond[t].items()} if t in cond else None)}
                      for t in teams},
            "note": "positions assume ties on points can go either way (goal difference not modelled)"}


def bump(matches):
    """Position of each team after every round, from the season's finished matches with numeric rounds."""
    rounds = sorted({int(m["round"]) for m in matches if str(m.get("round") or "").isdigit()})
    table, out = {}, {}
    names = {}
    for m in matches:
        for side in ("home", "away"):
            if m[side]["id"]:
                table.setdefault(m[side]["id"], {"pts": 0, "gf": 0, "ga": 0})
                names[m[side]["id"]] = m[side]["name"]
    done = []
    for rd in rounds:
        played = [m for m in matches if str(m.get("round")) == str(rd) and m["status"] == "finished" and m.get("score")]
        if not played:
            break
        for m in played:
            hs, as_ = m["score"]["home"], m["score"]["away"]
            for tid, f, a in ((m["home"]["id"], hs, as_), (m["away"]["id"], as_, hs)):
                t = table[tid]
                t["gf"] += f
                t["ga"] += a
                t["pts"] += 3 if f > a else 1 if f == a else 0
        order = sorted(table, key=lambda t: (_key(table[t]), names.get(t) or ""))
        for i, t in enumerate(order, 1):
            out.setdefault(str(t), []).append(i)
        done.append(rd)
    return {"rounds": done, "positions": out, "order": ORDER_NOTE}
