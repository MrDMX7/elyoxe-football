"""Player-level extras built on the per-player season tables (compute/season.player_table):
young UAE talent, player similarity, most improved, team of the round, league comparison."""
import math
from datetime import date

SIM_STATS = ["goals", "goal_assist", "total_scoring_att", "ontarget_scoring_att", "big_chance_created", "total_att_assist",
             "accurate_pass", "accurate_long_balls", "won_contest", "total_tackle", "interception",
             "effective_clearance", "ball_recovery", "defensive_contributions", "fouls"]
ROLE_OF_POS = {"GK": "GK", "DF": "DF", "MF": "MF", "FW": "FW"}
FORMATION = {"GK": 1, "DF": 4, "MF": 3, "FW": 3}


def age_on(dob, on: date):
    try:
        y, m, d = map(int, dob[:10].split("-"))
    except (TypeError, ValueError, AttributeError):
        return None
    return on.year - y - ((on.month, on.day) < (m, d))


def young_uae(table, squads, today: date, max_age=23, min_minutes=270, top=30):
    """UAE nationals aged <= max_age today in the league's squads, ranked by rating then G+A per 90."""
    info = {}
    for tid, groups in squads.items():
        for g in groups or []:
            for p in g.get("players") or []:
                if p.get("country") == "UAE":
                    info[str(p["id"])] = {"dob": p.get("dob"), "team": int(tid), "position": p.get("position")}
    rows = []
    for pid, pl in table.get("players", {}).items():
        i = info.get(pid)
        if not i or pl["minutes"] < min_minutes:
            continue
        age = age_on(i["dob"], today)
        if age is None or age > max_age:
            continue
        s = pl["stats"]
        ga90 = sum((s.get(k) or {}).get("per90") or 0 for k in ("goals", "goal_assist"))
        rows.append({"id": int(pid), "name": pl["name"], "team": i["team"], "dob": i["dob"], "age": age,
                     "position": i["position"], "minutes": pl["minutes"], "rating": (s.get("rating") or {}).get("value"),
                     "ga_per90": round(ga90, 2), "goals": (s.get("goals") or {}).get("value") or 0,
                     "assists": (s.get("goal_assist") or {}).get("value") or 0})
    rows.sort(key=lambda r: (-(r["rating"] or 0), -r["ga_per90"]))
    return {"max_age": max_age, "min_minutes": min_minutes, "players": rows[:top],
            "note": "UAE nationals from the league squads, age from date of birth; ranked by FotMob season rating, then (goals+assists) per 90"}


def similar(tables: dict, focus_comp: int, min_minutes=450, top=8):
    """tables {comp: player_table}. Per-90 vectors on SIM_STATS, z-scored over the pooled players,
    cosine similarity; for every focus-league player, the most similar players in any table."""
    pool = []
    for cid, t in tables.items():
        for pid, p in t.get("players", {}).items():
            if p["minutes"] < min_minutes:
                continue
            v = [((p["stats"].get(k) or {}).get("per90")) for k in SIM_STATS]
            if sum(x is None for x in v) > 4:
                continue
            pool.append((int(cid), int(pid), p["name"], p["team"], [x or 0.0 for x in v]))
    if len(pool) < 10:
        return None
    n = len(SIM_STATS)
    mean = [sum(r[4][i] for r in pool) / len(pool) for i in range(n)]
    sd = [math.sqrt(sum((r[4][i] - mean[i]) ** 2 for r in pool) / len(pool)) or 1 for i in range(n)]
    z = [[(r[4][i] - mean[i]) / sd[i] for i in range(n)] for r in pool]
    norm = [math.sqrt(sum(x * x for x in v)) or 1 for v in z]
    out = {}
    for i, r in enumerate(pool):
        if r[0] != focus_comp:
            continue
        sims = []
        for j, s in enumerate(pool):
            if i == j:
                continue
            c = sum(a * b for a, b in zip(z[i], z[j])) / (norm[i] * norm[j])
            sims.append((c, j))
        sims.sort(reverse=True)
        out[str(r[1])] = {"name": r[2], "team": r[3],
                          "similar": [{"id": pool[j][1], "name": pool[j][2], "team": pool[j][3], "comp": pool[j][0],
                                       "score": round(c, 3)} for c, j in sims[:top]]}
    return {"stats": SIM_STATS, "min_minutes": min_minutes, "pool": len(pool), "players": out,
            "method": "per-90 vectors z-scored over all players in the pooled leagues, cosine similarity"}


def improved(cur_list, prev_list, min_matches=5, top=25):
    """FotMob season rating lists (entries {player, team_id, value, matches}) -> biggest rating rises."""
    prev = {str(e["player"]["id"]): e for e in prev_list if (e.get("matches") or 0) >= min_matches}
    rows = []
    for e in cur_list:
        p = prev.get(str(e["player"]["id"]))
        if not p or (e.get("matches") or 0) < min_matches or e["value"] is None or p["value"] is None:
            continue
        rows.append({"id": e["player"]["id"], "name": e["player"]["name"], "team": e.get("team_id"),
                     "rating": e["value"], "prev_rating": p["value"], "delta": round(e["value"] - p["value"], 2),
                     "matches": e.get("matches"), "prev_matches": p.get("matches")})
    rows.sort(key=lambda r: -r["delta"])
    return {"min_matches": min_matches, "players": rows[:top], "declined": sorted(rows, key=lambda r: r["delta"])[:10]}


def team_of_round(ledger: dict):
    """Best XI (4-3-3) per round from FotMob match ratings in the stored lineups."""
    by_round = {}
    for e in ledger.values():
        rd = str(e.get("round") or "")
        for pid, pl in (e.get("players") or {}).items():
            if len(pl) < 5 or pl[3] is None or not pl[4]:
                continue
            by_round.setdefault(rd, []).append({"id": int(pid), "name": pl[0], "team": pl[2], "rating": pl[3],
                                                "role": pl[4], "match": e["id"]})
    out = {}
    for rd, ps in by_round.items():
        xi = []
        for role, k in FORMATION.items():
            xi += sorted([p for p in ps if p["role"] == role], key=lambda p: -p["rating"])[:k]
        if len(xi) == 11:
            out[rd] = {"formation": "4-3-3", "players": xi}
    return {"rounds": out, "note": "highest FotMob match rating per role (role = the player's usual position)"}


def league_profile(fixtures, ledger, squads_by_team: dict, country):
    fin = [m for m in fixtures if m["status"] == "finished" and m.get("score")]
    goals = sum(m["score"]["home"] + m["score"]["away"] for m in fin)
    hw = sum(1 for m in fin if m["score"]["home"] > m["score"]["away"])
    dr = sum(1 for m in fin if m["score"]["home"] == m["score"]["away"])
    ages, foreign, total = [], 0, 0
    for sq in squads_by_team.values():
        ages += sq.get("ages", [])
        foreign += sq.get("foreign", 0)
        total += sq.get("n", 0)
    att = [e["att"] for e in ledger.values() if isinstance(e.get("att"), (int, float)) and e["att"] > 0]
    return {"matches": len(fin), "goals_per_match": round(goals / len(fin), 2) if fin else None,
            "home_win_pct": round(100 * hw / len(fin), 1) if fin else None,
            "draw_pct": round(100 * dr / len(fin), 1) if fin else None,
            "squad_players": total, "avg_age": round(sum(ages) / len(ages), 1) if ages else None,
            "foreign_share_pct": round(100 * foreign / total, 1) if total else None,
            "teams_with_squads": len(squads_by_team), "country": country,
            "avg_attendance": round(sum(att) / len(att)) if att else None, "attendance_matches": len(att)}
