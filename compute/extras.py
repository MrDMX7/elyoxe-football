"""Tifo extras computed from the ledger, the player tables and the history (docs/SCHEMA.md "Tifo extras").

  cards        Tifo player card: overall + 6 sub-scores (40-99) from per-90 league percentiles
  clutch       points each player added with goals AND assists (winners, equalisers)
  style        team style fingerprint from match stats, nearest European style
  minute_clock goals per minute of play, league and per team
  fortress     home unbeaten runs per stadium (home team's league home games)
  lineup_ages  average age of each starting XI, youngest/oldest per round
  rotation     starting-XI changes between consecutive league games, per coach
  watchability 0-100 score per upcoming match
  record_chase gaps between active players and the all-time scorer list
  summaries    one compact season card per player (share images)
"""
import math

from .facts import team_games, runs

# ---------------------------------------------------------------- player cards
CARD_PARTS = {   # sub-score: (stats averaged by percentile)
    "finishing": ["goals", "ontarget_scoring_att", "total_scoring_att"],
    "creating": ["goal_assist", "big_chance_created", "total_att_assist"],
    "passing": ["accurate_pass", "accurate_long_balls"],
    "dribbling": ["won_contest", "penalty_won"],
    "defending": ["total_tackle", "interception", "effective_clearance", "outfielder_block", "defensive_contributions"],
    "work_rate": ["ball_recovery", "mins_played"],
}
ROLE_WEIGHTS = {
    "FW": {"finishing": .35, "creating": .2, "passing": .1, "dribbling": .2, "defending": .05, "work_rate": .1},
    "MF": {"finishing": .15, "creating": .25, "passing": .25, "dribbling": .1, "defending": .15, "work_rate": .1},
    "DF": {"finishing": .05, "creating": .1, "passing": .25, "dribbling": .05, "defending": .45, "work_rate": .1},
}
GK_PARTS = {"shot_stopping": ["saves", "_save_percentage"], "clean_sheets": ["clean_sheet"],
            "distribution": ["accurate_pass", "accurate_long_balls"]}


def _score(pcts):
    vals = [x for x in pcts if x is not None]
    return round(40 + 59 * (sum(vals) / len(vals)) / 100) if vals else None


def cards(table, roles):
    """table: season.player_table output; roles {player_id: GK/DF/MF/FW} from lineups/squads."""
    out = {}
    for pid, p in table.get("players", {}).items():
        if p["minutes"] < table.get("min_minutes", 270):
            continue
        st = p["stats"]
        pct = lambda k: (st.get(k) or {}).get("pct")  # noqa: E731
        role = roles.get(pid) or "MF"
        if role == "GK":
            subs = {k: _score([pct(x) for x in v]) for k, v in GK_PARTS.items()}
            subs.update({"passing": _score([pct("accurate_pass")]), "work_rate": _score([pct("mins_played")]),
                         "discipline": _score([100 - (pct("fouls") or 50)])})
            vals = [v for v in subs.values() if v is not None]
            overall = round(sum(vals) / len(vals)) if vals else None
        else:
            subs = {k: _score([pct(x) for x in v]) for k, v in CARD_PARTS.items()}
            w = ROLE_WEIGHTS.get(role, ROLE_WEIGHTS["MF"])
            tot = sum(w[k] for k in subs if subs[k] is not None)
            overall = round(sum(subs[k] * w[k] for k in subs if subs[k] is not None) / tot) if tot else None
        rating = (st.get("rating") or {}).get("value")
        if overall is not None and rating:
            overall = round(0.7 * overall + 0.3 * max(40, min(99, (rating - 5.5) * 30 + 40)))
        out[pid] = {"name": p["name"], "team": p["team"], "role": role, "overall": overall, "parts": subs,
                    "minutes": p["minutes"]}
    return {"players": out, "method": "sub-scores = 40 + 59 x mean league percentile (per 90) of their stats; "
            "overall = role-weighted sub-scores (70%) blended with the FotMob season rating (30%)"}


# ---------------------------------------------------------------- clutch
def clutch(ledger):
    """Points added by a goal = final points of the scoring team with the goal minus without it
    (e.g. the winner in 2-1: 3 - 1 = 2; an equaliser in 1-1: 1 - 0 = 1). Scorer and assister both get
    the full value (the owner asked for assists to count)."""
    per = {}
    for e in ledger.values():
        sc = e.get("score")
        if not sc:
            continue
        for g in e.get("goals") or []:
            side = g["side"]
            if side not in ("home", "away"):
                continue
            f, a = (sc["home"], sc["away"]) if side == "home" else (sc["away"], sc["home"])
            pts = lambda x, y: 3 if x > y else 1 if x == y else 0  # noqa: E731
            added = pts(f, a) - pts(f - 1, a)
            if added <= 0:
                continue
            tid = e[side]
            for role, pid in (("goals", g.get("player")), ("assists", g.get("assist"))):
                if not pid or g["type"] == "own_goal" and role == "goals":
                    continue
                r = per.setdefault(str(pid), {"team": tid, "from_goals": 0, "from_assists": 0, "winners": 0, "equalisers": 0,
                                              "matches": []})
                r["from_goals" if role == "goals" else "from_assists"] += added
                r["winners" if added == 2 else "equalisers"] += 1 if role == "goals" else 0
                r["matches"].append(e["id"])
    for r in per.values():
        r["total"] = r["from_goals"] + r["from_assists"]
    rows = sorted(({"id": int(k), **v} for k, v in per.items()), key=lambda r: -r["total"])
    return {"players": rows, "method": "points the team would lose without the goal; scorer and assister both credited"}


# ---------------------------------------------------------------- style
STYLE_KEYS = {"possession": "BallPossesion", "shots": "total_shots", "big_chances": "big_chance",
              "passes": "accurate_passes", "long_balls": "long_balls_accurate", "crosses": "accurate_crosses",
              "tackles": "matchstats.headers.tackles", "interceptions": "interceptions", "corners": "corners",
              "fouls": "fouls", "touches_box": "touches_opp_box", "xg": "expected_goals",
              "opp_half_passes": "opposition_half_passes", "aerials": "aerials_won", "all_passes": "passes"}


def team_style(ledgers: dict):
    """{comp: ledger} -> per team average of STYLE_KEYS (own side) + directness = long balls / passes."""
    teams = {}
    for cid, L in ledgers.items():
        for e in L.values():
            st = e.get("stats") or {}
            for side, i in (("home", 0), ("away", 1)):
                t = teams.setdefault(e[side], {"comp": cid, "n": 0, "sum": {}})
                t["n"] += 1
                for k, key in STYLE_KEYS.items():
                    v = (st.get(key) or [None, None])[i]
                    if v is not None:
                        t["sum"][k] = t["sum"].get(k, 0) + v
                        t["sum"]["_n_" + k] = t["sum"].get("_n_" + k, 0) + 1
                opp = (st.get("passes") or [None, None])[1 - i]
                acts = sum((st.get(k) or [0, 0])[i] or 0 for k in ("matchstats.headers.tackles", "interceptions", "fouls"))
                if opp and acts:     # pressing proxy: opponent passes per defensive action (lower = more pressing)
                    t["sum"]["ppda"] = t["sum"].get("ppda", 0) + opp / acts
                    t["sum"]["_n_ppda"] = t["sum"].get("_n_ppda", 0) + 1
    out = {}
    for tid, t in teams.items():
        if t["n"] < 3:
            continue
        avg = {k: round(t["sum"][k] / t["sum"]["_n_" + k], 2) for k in list(STYLE_KEYS) + ["ppda"] if t["sum"].get("_n_" + k)}
        if avg.get("passes") and avg.get("long_balls") is not None:
            avg["directness"] = round(avg["long_balls"] / max(avg["passes"], 1), 3)
        out[str(tid)] = {"comp": t["comp"], "matches": t["n"], "style": avg}
    return out


def nearest_styles(styles, focus_comp, other_comps, top=3):
    keys = ["possession", "shots", "passes", "directness", "crosses", "ppda", "opp_half_passes", "touches_box", "aerials"]
    pool = [(tid, s) for tid, s in styles.items() if all(k in s["style"] for k in keys)]
    if len(pool) < 5:
        return {}
    n = len(keys)
    mean = [sum(s["style"][k] for _, s in pool) / len(pool) for k in keys]
    sd = [math.sqrt(sum((s["style"][k] - mean[i]) ** 2 for _, s in pool) / len(pool)) or 1 for i, k in enumerate(keys)]
    z = {tid: [(s["style"][k] - mean[i]) / sd[i] for i, k in enumerate(keys)] for tid, s in pool}
    comp = {tid: s["comp"] for tid, s in pool}
    out = {}
    for tid in z:
        if comp[tid] != focus_comp:
            continue
        d = sorted((math.dist(z[tid], z[o]), o) for o in z if comp[o] in other_comps)
        out[tid] = [{"team": int(o), "comp": comp[o], "distance": round(x, 2)} for x, o in d[:top]]
    return {"features": keys, "nearest": out, "method": "Euclidean distance on z-scored per-match team averages"}


# ---------------------------------------------------------------- minute clock
def minute_clock(ledger):
    league = [0] * 121
    teams = {}
    for e in ledger.values():
        for g in e.get("goals") or []:
            m = g.get("m")
            if m is None or g["side"] not in ("home", "away"):
                continue
            m = max(1, min(120, m))
            league[m] += 1
            t = teams.setdefault(str(e[g["side"]]), {"for": [0] * 121, "against": [0] * 121})
            t["for"][m] += 1
            o = teams.setdefault(str(e["away" if g["side"] == "home" else "home"]), {"for": [0] * 121, "against": [0] * 121})
            o["against"][m] += 1
    return {"league": league, "teams": teams, "note": "index = minute (1-120); stoppage goals sit on 45/90 (FotMob gives 90+x as 90)"}


# ---------------------------------------------------------------- fortress
def fortress(history_rows, stadiums, window):
    out = []
    for s in stadiums:
        for tid in s.get("home_of") or []:
            games = team_games(history_rows, int(tid), "home")
            if not games:
                continue
            cur, best, best_season = runs(games, lambda f, a, h: f >= a)
            w = sum(1 for g in games if g[1] > g[2])
            d = sum(1 for g in games if g[1] == g[2])
            out.append({"stadium": s["id"], "name_ar": s.get("name_ar"), "team": int(tid), "home_games": len(games),
                        "won": w, "drawn": d, "lost": len(games) - w - d, "current_unbeaten": cur,
                        "longest_unbeaten": best, "longest_season": best_season})
    return {"since": window, "stadiums": sorted(out, key=lambda r: -r["current_unbeaten"]),
            "note": "league home games of the club that plays at the stadium today (a club that moved grounds "
                    "counts its old home games too)"}


# ---------------------------------------------------------------- lineups
def lineup_ages(ledger):
    by_round = {}
    for e in ledger.values():
        for side in ("home", "away"):
            ages = [pl[5] for pl in (e.get("players") or {}).values()
                    if len(pl) > 6 and pl[6] and pl[2] == e[side] and pl[5]]
            if len(ages) >= 9:
                by_round.setdefault(str(e.get("round")), []).append(
                    {"team": e[side], "match": e["id"], "avg_age": round(sum(ages) / len(ages), 2), "n": len(ages)})
    out = {}
    for rd, xs in by_round.items():
        xs.sort(key=lambda x: x["avg_age"])
        out[rd] = {"youngest": xs[0], "oldest": xs[-1], "all": xs}
    return {"rounds": out}


def rotation(ledger):
    seq = {}
    for e in sorted(ledger.values(), key=lambda e: e.get("ko") or ""):
        for side in ("home", "away"):
            xi = {pid for pid, pl in (e.get("players") or {}).items() if len(pl) > 6 and pl[6] and pl[2] == e[side]}
            if len(xi) >= 9:
                coach = ((e.get("coaches") or {}).get(side) or {})
                seq.setdefault(e[side], []).append((e["id"], xi, coach.get("id"), coach.get("name")))
    teams = {}
    for tid, games in seq.items():
        changes, per_coach = [], {}
        for (m0, xi0, c0, _), (m1, xi1, c1, cn) in zip(games, games[1:]):
            n = len(xi1 - xi0)
            changes.append({"match": m1, "changes": n})
            if c1:
                pc = per_coach.setdefault(str(c1), {"name": cn, "games": 0, "changes": 0})
                pc["games"] += 1
                pc["changes"] += n
        for pc in per_coach.values():
            pc["avg_changes"] = round(pc["changes"] / pc["games"], 2)
        teams[str(tid)] = {"avg_changes": round(sum(c["changes"] for c in changes) / len(changes), 2) if changes else None,
                           "by_match": changes, "by_coach": per_coach}
    return {"teams": teams, "note": "players in the starting XI who did not start the team's previous stored game"}


# ---------------------------------------------------------------- watchability
def watchability(match, p3, derby, sim_teams, form_pts):
    """0-100 = 35 closeness + 20 derby + 30 stakes + 15 form."""
    ph, pd, pa = p3
    closeness = 1 - abs(ph - pa)
    stakes = 0.0
    for tid in (match["home"]["id"], match["away"]["id"]):
        s = (sim_teams or {}).get(str(tid)) or {}
        for k, v in s.items():
            if k in ("title", "relegation") or k.startswith("ranks_"):
                stakes = max(stakes, 4 * v * (1 - v))          # peaks at 50 %: an open race
    form = min(1.0, sum(form_pts) / 30) if form_pts else 0.5  # both teams' last-5 points, 30 = max
    score = round(35 * closeness + 20 * (1 if derby else 0) + 30 * stakes + 15 * form)
    return {"score": score, "closeness": round(closeness, 3), "derby": derby, "stakes": round(stakes, 3),
            "form": round(form, 3)}


# ---------------------------------------------------------------- record chaser and summaries
def record_chase(alltime, active_now):
    """alltime: alltime.yaml doc; active_now {player name: {"id", "team", "goals_this_season"}} for players in
    the current league stats. The all-time totals are as of the Wikipedia revision (not live)."""
    scorers = alltime.get("top_scorers_all_time") or []
    out = []
    for i, s in enumerate(scorers):
        if not str(s.get("years", "")).endswith(("–", "-")):
            continue            # retired
        ahead = scorers[i - 1] if i > 0 else None
        live = active_now.get(s["name"])
        out.append({"name": s["name"], "rank": s["rank"], "goals_all_time": s["goals"],
                    "next_rank_goals": ahead["goals"] if ahead else None, "next_rank_name": ahead["name"] if ahead else None,
                    "needs_to_equal": (ahead["goals"] - s["goals"]) if ahead else None,
                    "needs_to_pass": (ahead["goals"] - s["goals"] + 1) if ahead else None,
                    "player_id": (live or {}).get("id"), "goals_this_season": (live or {}).get("goals")})
    return {"as_of": (alltime.get("source") or {}).get("wikipedia"), "chases": out,
            "note": "all-time totals as published at that Wikipedia revision; this season's goals are shown apart "
                    "because the revision may already include some of them"}


def summaries(table, cards_out, clutch_out, squads_info):
    cl = {str(r["id"]): r for r in clutch_out.get("players", [])}
    out = {}
    for pid, p in table.get("players", {}).items():
        st = p["stats"]
        v = lambda k: (st.get(k) or {}).get("value")  # noqa: E731
        out[pid] = {"name": p["name"], "team": p["team"], "minutes": p["minutes"], "rating": v("rating"),
                    "goals": v("goals") or 0, "assists": v("goal_assist") or 0, "shots": v("total_scoring_att"),
                    "chances_created": v("big_chance_created"), "tackles": v("total_tackle"),
                    "card": (cards_out.get("players", {}).get(pid) or {}).get("overall"),
                    "clutch_points": (cl.get(pid) or {}).get("total"), **(squads_info.get(pid) or {})}
    return out
