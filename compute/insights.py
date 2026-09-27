"""Ledger- and history-derived insights (items 237-277). Pure functions: no I/O.

Ledger entry fields used (compute/season.ledger_entry, v4): id, ko, round, season, home, away, score, ht,
goals [{m, add, side, type, player, assist, detail, shot}], reds [[m, added, side]], subs [[m, side, in, out]],
players {pid: [name, country, team, rating, role, age, starter, minutes, minute_on]}, coaches, formations.
History rows (compute/history.slim): id, ko, comp, season, h, a, hs, as, st.
"""
import math
from collections import Counter
from datetime import timedelta

from timeutil import parse_utc


def _pts(f, a):
    return 3 if f > a else 1 if f == a else 0


def _res(f, a):
    return "W" if f > a else "D" if f == a else "L"


def _goal_seq(e):
    """Goals in order as (minute, side) with the running score after each."""
    out, h, a = [], 0, 0
    for g in sorted(e.get("goals") or [], key=lambda g: ((g.get("m") or 0), (g.get("add") or 0))):
        if g["side"] == "home":
            h += 1
        elif g["side"] == "away":
            a += 1
        else:
            continue
        out.append((g.get("m") or 0, g["side"], h, a, g))
    return out


# ---------------------------------------------------------------- 237 form, 272 workload, 273 teammates
def appearances(ledgers):
    """{pid: [(ko, match, comp, team, rating, minutes, goals, assists, starter)]} across every ledger."""
    out = {}
    for cid, L in ledgers.items():
        for e in L.values():
            g, a = Counter(), Counter()
            for x in e.get("goals") or []:
                if x.get("player") and x["type"] != "own_goal":
                    g[str(x["player"])] += 1
                if x.get("assist"):
                    a[str(x["assist"])] += 1
            for pid, pl in (e.get("players") or {}).items():
                mins = pl[7] if len(pl) > 7 else None
                if mins == 0:
                    continue
                out.setdefault(pid, []).append((e.get("ko") or "", e["id"], cid, pl[2], pl[3], mins, g[pid], a[pid],
                                                pl[6] if len(pl) > 6 else None))
    for v in out.values():
        v.sort()
    return out


def form(apps_of_player, n=10):
    return [[m, ko[:10], r, mins, g, a] for ko, m, _c, _t, r, mins, g, a, _s in apps_of_player[-n:]]


WORKLOAD_30D, WORKLOAD_LAST5 = 540, 450


def workload(apps, team_ids, now):
    out = {}
    for pid, xs in apps.items():
        mine = [x for x in xs if x[3] in team_ids]
        if not mine:
            continue
        last30 = sum(x[5] or 0 for x in xs if x[0] and now - parse_utc(x[0]) <= timedelta(days=30))
        last5 = sum(x[5] or 0 for x in xs[-5:])
        span = (parse_utc(xs[-1][0]) - parse_utc(xs[-5][0])).days if len(xs) >= 5 and xs[-5][0] else None
        out[pid] = {"team": mine[-1][3], "minutes_30d": last30, "minutes_last5": last5, "days_for_last5": span,
                    "matches_30d": sum(1 for x in xs if x[0] and now - parse_utc(x[0]) <= timedelta(days=30)),
                    "overload": last30 >= WORKLOAD_30D or (last5 >= WORKLOAD_LAST5 and span is not None and span <= 18)}
    return out


def teammates(ledgers, top=30):
    pair = {}
    for L in ledgers.values():
        for e in L.values():
            by_team = {}
            for pid, pl in (e.get("players") or {}).items():
                if (pl[7] if len(pl) > 7 else 1):
                    by_team.setdefault(pl[2], []).append(pid)
            for ps in by_team.values():
                for p in ps:
                    c = pair.setdefault(p, Counter())
                    for q in ps:
                        if q != p:
                            c[q] += 1
    return {p: [[int(q), n] for q, n in c.most_common(top)] for p, c in pair.items()}


# ---------------------------------------------------------------- 238, 239/248 history
def team_history(rows, tid, comp_names):
    out = []
    for r in sorted(rows, key=lambda r: r["ko"] or ""):
        if tid not in (r["h"], r["a"]):
            continue
        home = r["h"] == tid
        gf, ga = (r["hs"], r["as"]) if home else (r["as"], r["hs"])
        out.append([(r["ko"] or "")[:10], r["comp"], r["a"] if home else r["h"], gf, ga, _res(gf, ga), "H" if home else "A", r["id"]])
    return out


def season_tables(rows_by_season):
    out = {}
    for season, rows in sorted(rows_by_season.items()):
        t = {}
        for r in rows:
            for tid, gf, ga, home in ((r["h"], r["hs"], r["as"], True), (r["a"], r["as"], r["hs"], False)):
                x = t.setdefault(tid, {"team": tid, "played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0, "pts": 0})
                x["played"] += 1
                x["gf"] += gf
                x["ga"] += ga
                x["pts"] += _pts(gf, ga)
                x[{"W": "won", "D": "drawn", "L": "lost"}[_res(gf, ga)]] += 1
        table = sorted(t.values(), key=lambda x: (-x["pts"], -(x["gf"] - x["ga"]), -x["gf"]))
        for i, x in enumerate(table, 1):
            x["rank"], x["gd"] = i, x["gf"] - x["ga"]
        n = len(rows)
        goals = sum(r["hs"] + r["as"] for r in rows)
        out[season] = {"table": table, "matches": n, "goals_per_game": round(goals / n, 2) if n else None,
                       "home_win_pct": round(100 * sum(1 for r in rows if r["hs"] > r["as"]) / n, 1) if n else None,
                       "draw_pct": round(100 * sum(1 for r in rows if r["hs"] == r["as"]) / n, 1) if n else None,
                       "title_margin": (table[0]["pts"] - table[1]["pts"]) if len(table) > 1 else None,
                       "champion": table[0]["team"] if table else None}
    return out


# ---------------------------------------------------------------- 252 score grid, 253 upsets, 254 projections
def score_grid(lh, la, n=5):
    p = lambda k, lam: math.exp(-lam) * lam ** k / math.factorial(k)  # noqa: E731
    return [[round(p(i, lh) * p(j, la), 4) for j in range(n + 1)] for i in range(n + 1)]


def upsets(preds, threshold=0.20):
    out = {}
    for x in preds:
        o = x["outcome"]
        if o == 1:
            continue
        pw = x["p"][0] if o == 0 else x["p"][2]
        if pw < threshold:
            out.setdefault(x.get("season"), []).append({"match": x["id"], "date": (x["ko"] or "")[:10], "comp": x.get("comp"),
                                                        "winner": x["h"] if o == 0 else x["a"], "loser": x["a"] if o == 0 else x["h"],
                                                        "winner_home": o == 0, "p_win": round(pw, 3)})
    for v in out.values():
        v.sort(key=lambda u: u["p_win"])
    return out


def projections(stat_list, played_by_team, matches_per_team, top=20):
    rows = []
    for e in stat_list or []:
        mp = e.get("matches") or 0
        tid = e.get("team_id")
        if not mp or tid not in played_by_team or not matches_per_team:
            continue
        rem = max(0, matches_per_team - played_by_team[tid])
        rate = (e["value"] or 0) / mp
        rows.append({"player": e["player"], "team": tid, "now": e["value"], "matches": mp, "per_match": round(rate, 3),
                     "team_remaining": rem, "projected": round((e["value"] or 0) + rate * rem, 1)})
    rows.sort(key=lambda r: -r["projected"])
    return rows[:top]


# ---------------------------------------------------------------- 258 games in hand
def games_in_hand(rows, fixtures, now, probs=None):
    played = {r["team"]["id"]: r["played"] or 0 for r in rows}
    most = max(played.values()) if played else 0
    overdue = [m for m in fixtures if m["status"] in ("postponed", "scheduled", "cancelled") and m.get("kickoff_utc")
               and parse_utc(m["kickoff_utc"]) < now - timedelta(hours=3)]
    out = []
    for r in rows:
        tid = r["team"]["id"]
        mine = [m for m in overdue if tid in (m["home"]["id"], m["away"]["id"])]
        xp = 0.0
        for m in mine:
            p = (probs or {}).get(m.get("id"))
            if p:
                xp += 3 * (p[0] if m["home"]["id"] == tid else p[2]) + p[1]
            else:
                xp += 1.35
        out.append({"team": tid, "rank": r["rank"], "played": played[tid], "pts": r["pts"], "games_in_hand": most - played[tid],
                    "overdue_matches": [m["id"] for m in mine], "pts_per_game": round(r["pts"] / played[tid], 2) if played[tid] else None,
                    "projected_pts_with_overdue": round(r["pts"] + xp, 1)})
    adj = sorted(out, key=lambda x: -x["projected_pts_with_overdue"])
    for i, x in enumerate(adj, 1):
        x["adjusted_rank"] = i
    return {"teams": out, "overdue": [m["id"] for m in overdue]}


# ---------------------------------------------------------------- 264 local minutes
def local_minutes(L, country_code):
    per = {}
    for e in L.values():
        for pid, pl in (e.get("players") or {}).items():
            mins = pl[7] if len(pl) > 7 else None
            if not mins:
                continue
            t = per.setdefault(pl[2], {"national": 0, "foreign": 0, "unknown": 0})
            k = "unknown" if not pl[1] else "national" if pl[1] == country_code else "foreign"
            t[k] += mins
    league = {"national": 0, "foreign": 0, "unknown": 0}
    for v in per.values():
        for k in league:
            league[k] += v[k]
        tot = sum(v.values())
        v["national_pct"] = round(100 * v["national"] / tot, 1) if tot else None
    tot = sum(league.values())
    league["national_pct"] = round(100 * league["national"] / tot, 1) if tot else None
    return {"league": league, "teams": per}


# ---------------------------------------------------------------- 265-271
def first_goal(L):
    t = {}
    for e in L.values():
        seq = _goal_seq(e)
        sc = e.get("score")
        if not seq or not sc:
            continue
        first = seq[0][1]
        for side in ("home", "away"):
            tid = e[side]
            f, a = (sc["home"], sc["away"]) if side == "home" else (sc["away"], sc["home"])
            x = t.setdefault(tid, {"scored_first": Counter(), "conceded_first": Counter(), "comebacks_won": 0, "comebacks_drawn": 0})
            key = "scored_first" if first == side else "conceded_first"
            x[key][_res(f, a)] += 1
            if first != side and f >= a:
                x["comebacks_won" if f > a else "comebacks_drawn"] += 1
    out = {}
    for tid, x in t.items():
        row = {}
        for k in ("scored_first", "conceded_first"):
            n = sum(x[k].values())
            row[k] = {"played": n, **{r: x[k][r] for r in "WDL"},
                      "win_pct": round(100 * x[k]["W"] / n, 1) if n else None}
        row.update(comebacks_won=x["comebacks_won"], comebacks_drawn=x["comebacks_drawn"])
        out[str(tid)] = row
    return out


def dropped(L):
    t = {}
    for e in L.values():
        seq = _goal_seq(e)
        sc = e.get("score")
        if not sc:
            continue
        for side in ("home", "away"):
            tid = e[side]
            led = any((h > a) if side == "home" else (a > h) for _, _, h, a, _ in seq)
            trailed = any((h < a) if side == "home" else (a < h) for _, _, h, a, _ in seq)
            f, a = (sc["home"], sc["away"]) if side == "home" else (sc["away"], sc["home"])
            x = t.setdefault(str(tid), {"dropped_from_winning": 0, "won_from_losing": 0, "led_matches": 0, "trailed_matches": 0})
            if led:
                x["led_matches"] += 1
                x["dropped_from_winning"] += 3 - _pts(f, a)
            if trailed:
                x["trailed_matches"] += 1
                x["won_from_losing"] += _pts(f, a)
    return t


def red_impact(L):
    t = {}
    for e in L.values():
        reds = sorted(e.get("reds") or [], key=lambda r: (r[0] or 0))
        sc = e.get("score")
        if not reds or not sc:
            continue
        m0, _, side0 = reds[0]
        seq = _goal_seq(e)
        at = next(((h, a) for mm, _, h, a, _ in reversed(seq) if mm <= (m0 or 0)), (0, 0))
        for side in ("home", "away"):
            tid = e[side]
            state = "10v11" if side == side0 else "11v10"
            f, a = (sc["home"], sc["away"]) if side == "home" else (sc["away"], sc["home"])
            fb, ab = at if side == "home" else (at[1], at[0])
            x = t.setdefault(str(tid), {"11v10": Counter(), "10v11": Counter()})
            x[state][_res(f, a)] += 1
            x[state]["pts_after_red"] += _pts(f, a) - _pts(fb, ab) + 0
            x[state]["n"] += 1
    return {tid: {k: dict(v) for k, v in x.items()} for tid, x in t.items()}


def goal_types(L):
    teams, players, cov = {}, {}, {"goals": 0, "with_shot": 0, "with_detail": 0}
    for e in L.values():
        for g in e.get("goals") or []:
            if g["type"] == "own_goal" or g["side"] not in ("home", "away"):
                continue
            cov["goals"] += 1
            shot = g.get("shot") or {}
            kind = None
            if g["type"] == "penalty_goal":
                kind = "penalty"
            elif shot.get("body"):
                cov["with_shot"] += 1
                kind = {"Header": "header", "RightFoot": "right_foot", "LeftFoot": "left_foot"}.get(shot["body"], "other")
                if shot.get("situation") in ("SetPiece", "FromCorner", "FreeKick", "ThrowInSetPiece"):
                    kind += "+set_piece"
                if shot.get("inside_box") is False:
                    kind += "+outside_box"
            elif g.get("detail"):
                cov["with_detail"] += 1
                kind = {"Header": "header", "Direct freekick": "free_kick"}.get(g["detail"], g["detail"].lower())
            kind = kind or "unknown"
            tid = e[g["side"]]
            teams.setdefault(str(tid), Counter())[kind] += 1
            if g.get("player"):
                players.setdefault(str(g["player"]), Counter())[kind] += 1
    cov["coverage_pct"] = round(100 * (cov["with_shot"] + cov["with_detail"]) / cov["goals"], 1) if cov["goals"] else None
    return {"coverage": cov, "teams": {k: dict(v) for k, v in teams.items()}, "players": {k: dict(v) for k, v in players.items()}}


def dependence(L):
    per = {}
    for e in L.values():
        for g in e.get("goals") or []:
            if g["side"] in ("home", "away") and g["type"] != "own_goal" and g.get("player"):
                per.setdefault(str(e[g["side"]]), Counter())[str(g["player"])] += 1
    out = {}
    for tid, c in per.items():
        tot = sum(c.values())
        top = c.most_common(2)
        out[tid] = {"goals": tot, "top_scorer": {"player": int(top[0][0]), "goals": top[0][1]},
                    "top1_share": round(100 * top[0][1] / tot, 1),
                    "top2_share": round(100 * sum(n for _, n in top) / tot, 1)}
    return out


def subs(L):
    players, coaches, changed = {}, {}, 0
    for e in L.values():
        sc = e.get("score")
        if not sc:
            continue
        subs_ = {pid for pid, pl in (e.get("players") or {}).items() if len(pl) > 8 and not pl[6] and (pl[7] or 0) > 0}
        for g in e.get("goals") or []:
            side = g["side"]
            if side not in ("home", "away"):
                continue
            f, a = (sc["home"], sc["away"]) if side == "home" else (sc["away"], sc["home"])
            worth = _pts(f, a) - _pts(f - 1, a)
            for role, pid in (("goals", g.get("player")), ("assists", g.get("assist"))):
                if not pid or str(pid) not in subs_ or (role == "goals" and g["type"] == "own_goal"):
                    continue
                x = players.setdefault(str(pid), {"team": e[side], "goals": 0, "assists": 0, "points_added": 0})
                x[role] += 1
                x["points_added"] += worth
                coach = ((e.get("coaches") or {}).get(side) or {})
                if coach.get("id"):
                    c = coaches.setdefault(str(coach["id"]), {"name": coach.get("name"), "team": e[side], "sub_goals": 0,
                                                              "sub_assists": 0, "points_added": 0})
                    c["sub_goals" if role == "goals" else "sub_assists"] += 1
                    c["points_added"] += worth
                if worth > 0 and role == "goals":
                    changed += 1
    return {"players": dict(sorted(players.items(), key=lambda kv: -(kv[1]["goals"] + kv[1]["assists"]))),
            "coaches": coaches, "result_changing_sub_goals": changed}


def xi(L):
    teams = {}
    for e in L.values():
        for side in ("home", "away"):
            tid = e[side]
            starters = frozenset(pid for pid, pl in (e.get("players") or {}).items() if pl[2] == tid and len(pl) > 6 and pl[6])
            if len(starters) < 9:
                continue
            t = teams.setdefault(str(tid), {"n": 0, "starts": Counter(), "xis": Counter(), "formations": Counter(), "names": {}})
            t["n"] += 1
            t["starts"].update(starters)
            t["xis"][starters] += 1
            f = (e.get("formations") or {}).get(side)
            if f:
                t["formations"][f] += 1
            for pid in starters:
                t["names"][pid] = e["players"][pid][0]
    out = {}
    for tid, t in teams.items():
        common, n_common = t["xis"].most_common(1)[0]
        out[tid] = {"matches": t["n"], "formations": dict(t["formations"].most_common()),
                    "starts": [{"player": int(p), "name": t["names"].get(p), "starts": n} for p, n in t["starts"].most_common()],
                    "most_common_xi": {"players": sorted(int(p) for p in common), "times": n_common},
                    "most_used_xi": [int(p) for p, _ in t["starts"].most_common(11)]}
    return out


# ---------------------------------------------------------------- 243 firsts
def firsts(detail, ledger, history_rows):
    """Firsts inside the data we store: first-ever meeting (FotMob history since 2010/11), a player's first
    appearance / first goal for his club in this season's stored matches."""
    out = []
    h, a = detail["home"]["id"], detail["away"]["id"]
    before = [r for r in history_rows if {r["h"], r["a"]} == {h, a} and (r["ko"] or "") < (detail.get("kickoff_utc") or "")]
    if history_rows and not before:
        out.append({"kind": "first_meeting", "text_ar": "أول مواجهة بين الفريقين في بيانات المصدر (منذ 2010/2011)"})
    earlier = [e for e in ledger.values() if (e.get("ko") or "") < (detail.get("kickoff_utc") or "") and e["id"] != detail["id"]]
    seen_players = {pid for e in earlier for pid, pl in (e.get("players") or {}).items() if (pl[7] if len(pl) > 7 else 1)}
    scorers = {str(g.get("player")) for e in earlier for g in (e.get("goals") or []) if g.get("player") and g["type"] != "own_goal"}
    lu = detail.get("lineups") or {}
    for side in ("home", "away"):
        for p in ((lu.get(side) or {}).get("starters") or []) + ((lu.get(side) or {}).get("subs") or []):
            played = p in ((lu.get(side) or {}).get("starters") or []) or p.get("minutes_on") is not None
            if played and earlier and str(p.get("id")) not in seen_players:
                out.append({"kind": "first_appearance_season", "player": p.get("id"), "name": p.get("name"), "side": side})
    for e in detail.get("events") or []:
        if e["type"] in ("goal", "penalty_goal") and e.get("player") and earlier and str(e["player"]["id"]) not in scorers:
            out.append({"kind": "first_goal_season", "player": e["player"]["id"], "name": e["player"]["name"],
                        "minute": e.get("minute"), "side": e.get("team")})
            scorers.add(str(e["player"]["id"]))
    return out


# ---------------------------------------------------------------- 241 milestones, 274 career
MILESTONES = (50, 100, 150, 200, 250, 300)


def career(pd):
    """playerData careerHistory -> clubs [{team, start, end, apps, goals, assists, active, loan}] + season rows."""
    ci = ((pd.get("careerHistory") or {}).get("careerItems") or {})
    out = {}
    for kind in ("senior", "national team"):
        c = ci.get(kind) or {}
        out[kind.replace(" ", "_")] = [{"team": x.get("teamId"), "name": x.get("team"), "start": (x.get("startDate") or "")[:10] or None,
                                        "end": (x.get("endDate") or "")[:10] or None, "apps": _n(x.get("appearances")),
                                        "goals": _n(x.get("goals")), "assists": _n(x.get("assists")), "active": x.get("active"),
                                        "loan": ((x.get("transferType") or {}).get("text") or "") == "on loan"}
                                       for x in c.get("teamEntries") or []]
    return out


def _n(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def milestones(player, car):
    items = []
    for kind in ("senior", "national_team"):
        by_team = {}
        for x in car.get(kind) or []:
            t = by_team.setdefault(x["team"], {"name": x["name"], "apps": 0, "goals": 0})
            t["apps"] += x["apps"] or 0
            t["goals"] += x["goals"] or 0
        for tid, t in by_team.items():
            for stat in ("goals", "apps"):
                v = t[stat]
                nxt = next((m for m in MILESTONES if m > v), None)
                if nxt and v >= nxt - (5 if stat == "goals" else 10):
                    items.append({"player": player["id"], "name": player.get("name"), "team": tid, "team_name": t["name"],
                                  "scope": "national_team" if kind == "national_team" else "club", "stat": stat,
                                  "now": v, "target": nxt, "needs": nxt - v})
    return items


# ---------------------------------------------------------------- 277 two-legged ties
def ties(bracket, matches_by_id):
    out = []
    for rd in bracket or []:
        for t in rd["ties"]:
            legs = [matches_by_id.get(m) for m in t.get("matches") or []]
            legs = [m for m in legs if m]
            if len(legs) != 2:
                continue
            legs.sort(key=lambda m: m.get("kickoff_utc") or "")
            l1, l2 = legs
            a_id, b_id = l1["home"]["id"], l1["away"]["id"]
            agg = {str(a_id): 0, str(b_id): 0}
            for m in legs:
                if m.get("score") and m["status"] in ("finished", "live", "ht"):
                    agg[str(m["home"]["id"])] += m["score"]["home"]
                    agg[str(m["away"]["id"])] += m["score"]["away"]
            state = {"stage": rd["stage"], "first_leg": {"match": l1["id"], "home": a_id, "away": b_id, "score": l1.get("score"),
                                                         "status": l1["status"]},
                     "second_leg": {"match": l2["id"], "home": l2["home"]["id"], "away": l2["away"]["id"], "score": l2.get("score"),
                                    "status": l2["status"], "kickoff_utc": l2.get("kickoff_utc")},
                     "aggregate": agg, "away_goals_rule": False}
            if l1["status"] == "finished" and l2["status"] != "finished":
                diff = agg[str(a_id)] - agg[str(b_id)]
                lead = a_id if diff > 0 else b_id if diff < 0 else None
                state["needs"] = {"leader": lead, "margin": abs(diff),
                                  "trailing_needs_to_win_by": abs(diff) + 1 if lead else 1,
                                  "draw_on_aggregate_goes_to": "extra time and penalties",
                                  "live": l2["status"] in ("live", "ht")}
            out.append(state)
    return out
