"""Tournament simulator for national-team tournaments with groups + knockout (Gulf Cup 329, Asian Cup
290): comp/{id}/tournament-sim.json.

Groups: remaining group games drawn from national-Elo W/D/L probabilities; positions by points,
then current goal difference, then random. Best third-placed teams (when the bracket uses slots like
"3BEF") are ranked by points then random and placed into the slots whose group letters allow them.
Knockout: slots "1A"/"2C" resolve from the simulated groups, later rounds pair winners in bracket
order; a knockout draw is settled 50/50 (extra time and penalties are not modelled). Matchups FotMob
already fixed (real teams, or a known winner) are respected. The host gets home advantage.
"""
import itertools, random, re

from . import rating as R


def _grp_letter(name):
    m = re.search(r"([A-Z])\s*$", name or "")
    return m.group(1) if m else None


def simulate(groups, group_fixtures, bracket, ratings, params, host=None, n=10000, seed=0):
    """groups: [{"letter", "rows": standings rows}], group_fixtures: [(home, away)] remaining,
    bracket: standings["bracket"] (FotMob playoff rounds), ratings {team_id: elo}."""
    p = {**R.DEFAULTS, **params}
    rng = random.Random(seed)
    letters = [g["letter"] for g in groups]
    teams = [r["team"]["id"] for g in groups for r in g["rows"]]
    pts0 = {r["team"]["id"]: r["pts"] or 0 for g in groups for r in g["rows"]}
    gd0 = {r["team"]["id"]: r.get("gd") or 0 for g in groups for r in g["rows"]}
    base = p["newcomer"]

    def pr(h, a):
        neutral = host not in (h, a)
        if host == a:
            h, a = a, h
            ph, pd, pa = R.probs(ratings.get(h, base), ratings.get(a, base), p, False)
            return pa, pd, ph
        return R.probs(ratings.get(h, base), ratings.get(a, base), p, neutral)

    gfx = [(h, a, *pr(h, a)[:2]) for h, a in group_fixtures if h in pts0 and a in pts0]
    rounds = bracket or []
    first = rounds[0]["ties"] if rounds else []
    stage_names = [r["stage"] for r in rounds]
    reach = {t: dict.fromkeys(stage_names + ["winner"], 0) for t in teams}
    gpos = {t: [0] * 4 for t in teams}
    slots_per_third = [re.match(r"^3([A-Z]+)$", t["home"]["name"] or "") or re.match(r"^3([A-Z]+)$", t["away"]["name"] or "")
                       for t in first]
    n_thirds = sum(1 for t in first for side in ("home", "away") if re.match(r"^3[A-Z]+$", t[side]["name"] or ""))
    for _ in range(n):
        pts = dict(pts0)
        for h, a, ph, pd in gfx:
            u = rng.random()
            if u < ph:
                pts[h] += 3
            elif u < ph + pd:
                pts[h] += 1
                pts[a] += 1
            else:
                pts[a] += 3
        pos = {}
        thirds = []
        for g in groups:
            order = sorted((r["team"]["id"] for r in g["rows"]), key=lambda t: (-pts[t], -gd0[t], rng.random()))
            for i, t in enumerate(order):
                gpos[t][min(i, 3)] += 1
                pos[f"{i + 1}{g['letter']}"] = t
            if len(order) >= 3:
                thirds.append((g["letter"], order[2]))
        best3 = sorted(thirds, key=lambda x: (-pts[x[1]], -gd0[x[1]], rng.random()))[:n_thirds] if n_thirds else []
        third_slots = [(i, side, t[side]["name"][1:]) for i, t in enumerate(first) for side in ("home", "away")
                       if re.match(r"^3[A-Z]+$", t[side]["name"] or "")]
        assign = {}
        if best3:
            for perm in itertools.permutations(best3):
                if all(g in allowed for (g, _), (_, _, allowed) in zip(perm, third_slots)):
                    assign = {(i, side): t for (g, t), (i, side, _) in zip(perm, third_slots)}
                    break
        winners = []
        for ri, rd in enumerate(rounds):
            nxt = []
            ties = rd["ties"]
            for ti, tie in enumerate(ties):
                if ri == 0:
                    sides = []
                    for side in ("home", "away"):
                        nm = tie[side]["name"] or ""
                        if not tie.get("tbd") and tie[side]["id"] in pts0:
                            sides.append(tie[side]["id"])
                        elif re.match(r"^[12][A-Z]$", nm):
                            sides.append(pos.get(nm))
                        else:
                            sides.append(assign.get((ti, side)))
                    h, a = sides
                else:
                    h, a = (winners[2 * ti], winners[2 * ti + 1]) if 2 * ti + 1 < len(winners) else (None, None)
                if h is None or a is None:
                    nxt.append(h or a)
                    continue
                reach[h][rd["stage"]] += 1
                reach[a][rd["stage"]] += 1
                if tie.get("winner") in (h, a) and ri == 0:
                    w = tie["winner"]
                else:
                    ph, pd, pa = pr(h, a)
                    w = h if rng.random() < ph + pd / 2 else a
                nxt.append(w)
            winners = nxt
        if len(winners) == 1 and winners[0]:
            reach[winners[0]]["winner"] += 1
    out = {str(t): {"group_positions": [round(c / n, 4) for c in gpos[t]],
                    **{f"reach_{k}": round(v / n, 4) for k, v in reach[t].items()}} for t in teams}
    return {"sims": n, "seed": seed, "stages": stage_names, "teams": out, "host": host,
            "method": "national Elo W/D/L for group games; knockout draws settled 50/50; thirds by points then random"}
