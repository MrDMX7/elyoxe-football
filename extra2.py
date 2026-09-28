"""Analytics steps for items 306-322 (Arab focus pages, coaches, happiness, twins, finishing, anniversaries,
draws, year calendar). Called from poller.Poller.analytics_chores; outputs in docs/SCHEMA.md."""
import json, math, os, urllib.parse, urllib.request
from datetime import timedelta

import analytics as AN
import arabs as AR
import config
from compute import danger as DG, extras as EX, history as HI, rating as R
from sources import schema as S
from timeutil import iso, parse_utc, UAE

HERE = os.path.dirname(os.path.abspath(__file__))
ERRORS = (Exception,)
ARAB_LEAGUES = AR.ARAB_LEAGUES
BIG5 = (47, 87, 55, 54, 53)
UA = "elyoxe-tifo-data/0.1 (hello@elyoxe.com)"


def _arab_iso():
    return {c["iso2"] for c in config.countries() if c.get("arab")}


def is_arab_team(p, tid):
    c = p.team_country(tid)
    if c:
        return c.get("iso2") in _arab_iso()
    v = p.aux("team_country").get(str(tid)) or {}
    return v.get("iso2") in _arab_iso()


# ------------------------------------------------------------------ league strength
def league_strength(p):
    """Mean Tifo club rating of each league's current teams (one scale; Arab leagues and Europe are only
    weakly linked, via the Club World Cup / Intercontinental Cup) -> weight = 10^((mean - 1500)/800),
    i.e. +400 rating points = x3.2 ... documented in SCHEMA.md."""
    rat = p.aux("arab_ratings").get("ratings") or {}
    out = {}
    for cid in set(ARAB_LEAGUES) | set(BIG5):
        st = p.store.get_json(f"comp/{cid}/standings.json") if p.has_time(3) else None
        ids = [r["team"]["id"] for g in (st or {}).get("groups", []) for r in g["rows"]]
        vals = [rat[str(t)] for t in ids if str(t) in rat]
        if vals:
            mean = sum(vals) / len(vals)
            out[cid] = {"mean_rating": round(mean, 1), "weight": round(10 ** ((mean - 1500) / 800), 3), "teams_rated": len(vals)}
    return out


# ------------------------------------------------------------------ 306 match of the week
def match_of_week(p):
    now = p.now()
    y, w, wd = now.astimezone(UAE).isocalendar()        # the UAE week (Monday 00:00 UAE), not the UTC one
    cur = p.store.get_json("arabs/match-of-week.json") or {}
    pick_ko = parse_utc(((cur.get("pick") or {}).get("kickoff_utc")))
    if cur.get("week") == f"{y}-W{w:02d}" and pick_ko and pick_ko > now:
        return                  # this week's pick is still ahead; a pick that has kicked off is replaced by the next one
    derbies = {tuple(sorted(d["teams"])) for d in config.arab_derbies()}
    national_ids = {c["fotmob_team"] for c in config.countries() if c.get("arab")}
    cands = []
    comps = [c["id"] for c in p.comps]
    for cid in comps:
        watch = (p.store.get_json(f"comp/{cid}/watch.json") or {}).get("matches", {}) if cid in AN.analytics_leagues() else {}
        for m in p.fixtures(cid) or []:
            ko = parse_utc(m.get("kickoff_utc"))
            if not ko or m["status"] != S.SCHEDULED or not (now <= ko <= now + timedelta(days=7)):
                continue
            h, a = m["home"]["id"], m["away"]["id"]
            arab = (h in national_ids or a in national_ids) or is_arab_team(p, h) or is_arab_team(p, a)
            if not arab:
                continue
            pr = m.get("probs") or {}
            close = 1 - abs((pr.get("home") or 0.4) - (pr.get("away") or 0.3))
            wscore = (watch.get(str(m["id"])) or {}).get("score")
            rnd = str(m.get("round") or "").lower()
            stage = 1.0 if rnd == "final" else 0.7 if rnd in ("1/2", "semi-finals") else 0.5 if rnd in ("1/4", "quarter-finals") else \
                0.3 if cid in AR.CONTINENTAL or cid in (329, 290, 289, 10242) else 0.0
            derby = tuple(sorted((h, a))) in derbies
            both_arab = ((h in national_ids or is_arab_team(p, h)) and (a in national_ids or is_arab_team(p, a)))
            score = round((wscore if wscore is not None else 50 * close) * 0.6 + 20 * derby + 25 * stage + 10 * both_arab, 1)
            cands.append({"match": m["id"], "comp": cid, "comp_name_ar": m.get("comp_name_ar"), "kickoff_utc": m["kickoff_utc"],
                          "home": m["home"], "away": m["away"], "probs": pr or None, "watchability": wscore, "derby": derby,
                          "stage_bonus": stage, "arab_vs_arab": both_arab, "score": score})
    cands.sort(key=lambda c: -c["score"])
    p.store.put_json("arabs/match-of-week.json", {"week": f"{y}-W{w:02d}", "generated": iso(now), "pick": cands[0] if cands else None,
                                                  "shortlist": cands[1:6],
                                                  "method": "0.6 x watchability (or 50 x closeness) + 20 derby + 25 x stage "
                                                            "(final 1, semi 0.7, quarter 0.5, other continental/national 0.3) + 10 Arab-vs-Arab; "
                                                            "picked on Monday for the next 7 days"}, cache="static")


# ------------------------------------------------------------------ 307 golden boot, 308 player of the season, 309 per-90
def _arab_players(p):
    """{pid: (nationality, [(comp, player-table row)])} from the player tables and nationality in lineups/squads."""
    codes = AR.arab_codes()
    nat = {}
    for groups in p.aux("squads").values():
        for g in groups or []:
            for pl in g.get("players") or []:
                if pl.get("country") in codes:
                    nat[str(pl["id"])] = codes[pl["country"]]
    for cid in set(ARAB_LEAGUES) | set(BIG5) | {42}:
        for e in p.ledger(cid)["matches"].values():
            for pid, pl in (e.get("players") or {}).items():
                if pl[1] in codes:
                    nat[pid] = codes[pl[1]]
    out = {}
    for cid, t in p.aux("ptables").items():
        for pid, row in (t.get("players") or {}).items():
            if pid in nat:
                out.setdefault(pid, (nat[pid], []))[1].append((int(cid), row))
    return out


def golden_boot_and_poty(p):
    ls = league_strength(p)
    players = _arab_players(p)
    names = p.names["teams"]
    boot, poty = [], []
    for pid, (nat, rows) in players.items():
        goals = sum((r["stats"].get("goals") or {}).get("value") or 0 for c, r in rows if c != 42)
        wgoals = sum(((r["stats"].get("goals") or {}).get("value") or 0) * (ls.get(c) or {}).get("weight", 1.0) for c, r in rows if c != 42)
        name = rows[0][1]["name"]
        team = rows[0][1]["team"]
        if goals:
            boot.append({"player": int(pid), "name": name, "nationality": nat, "team": team, "team_ar": names.get(str(team)),
                         "comps": [c for c, _ in rows], "goals": goals, "weighted_goals": round(wgoals, 2)})
        mins = sum(r["minutes"] for _, r in rows)
        if mins >= 450:
            best = max(rows, key=lambda cr: cr[1]["minutes"])
            c, r = best
            st = r["stats"]
            rating = (st.get("rating") or {}).get("value") or 6.0
            g = sum((rr["stats"].get("goals") or {}).get("value") or 0 for _, rr in rows)
            a = sum((rr["stats"].get("goal_assist") or {}).get("value") or 0 for _, rr in rows)
            wt = (ls.get(c) or {}).get("weight", 1.0)
            score = wt * ((rating - 6.0) * 10 + 4 * g + 3 * a) * min(1.0, mins / 1800)
            poty.append({"player": int(pid), "name": name, "nationality": nat, "team": team, "team_ar": names.get(str(team)),
                         "comp": c, "minutes": mins, "rating": rating, "goals": g, "assists": a, "league_weight": wt,
                         "score": round(score, 2)})
    boot.sort(key=lambda x: (-x["weighted_goals"], -x["goals"]))
    poty.sort(key=lambda x: -x["score"])
    now = p.now()
    p.store.put_json("arabs/golden-boot.json", {"generated": iso(now), "players": boot, "league_strength": ls,
                                                "method": "league goals this season by Arab nationals (player tables of the Arab leagues and "
                                                          "the big five); weighted = goals x league weight, weight = 10^((mean Tifo club "
                                                          "rating of the league - 1500) / 800)"}, cache="static")
    y, w, _ = now.isocalendar()
    hist = p.aux("poty_history")
    wk = f"{y}-W{w:02d}"
    hist[wk] = {str(x["player"]): i for i, x in enumerate(poty[:50], 1)}
    for x in poty[:50]:
        x["rank_history"] = {k: v[str(x["player"])] for k, v in sorted(hist.items())[-12:] if str(x["player"]) in v}
    p.store.put_json("arabs/poty.json", {"week": wk, "generated": iso(now), "players": poty[:50], "league_strength": ls,
                                         "method": "league weight x ((rating - 6) x 10 + 4 x goals + 3 x assists) x min(1, minutes/1800); "
                                                   "rank_history = weekly ranks (last 12 weeks)"}, cache="static")


def abroad_per90(p):
    """Adds per-90 stats from the player tables to arabs/abroad.json (item 309)."""
    doc = p.store.get_json("arabs/abroad.json")
    if not doc:
        return
    tabs = p.aux("ptables")
    keys = ("goals", "goal_assist", "total_scoring_att", "ontarget_scoring_att", "big_chance_created", "accurate_pass",
            "won_contest", "total_tackle", "interception", "ball_recovery")
    for x in doc["players"]:
        row = None
        for c in x.get("comps") or []:
            row = ((tabs.get(str(c)) or {}).get("players") or {}).get(str(x["id"]))
            if row:
                break
        x["per90"] = {k: (row["stats"].get(k) or {}).get("per90") for k in keys} if row else None
        x["per90_minutes"] = row["minutes"] if row else None
    p.store.put_json("arabs/abroad.json", doc, cache="static")


# ------------------------------------------------------------------ 310 continental odds
def continental_odds(p):
    out = {}
    for cid in (525, 9469, 9470, 526, 9468):
        bs = p.store.get_json(f"comp/{cid}/bracket-sim.json") or {}
        teams = bs.get("teams") or {}
        rows = []
        for tid, v in teams.items():
            if is_arab_team(p, int(tid)):
                rows.append({"team": int(tid), "team_ar": p.names["teams"].get(tid), "country": (p.team_country(int(tid)) or
                                                                                                 p.aux("team_country").get(tid) or {}),
                             **{k: v[k] for k in v if k.startswith("reach_") or k == "group_positions"}})
        rows.sort(key=lambda r: -(r.get("reach_winner") or 0))
        out[str(cid)] = {"name_ar": (config.competition(cid) or {}).get("name_ar"), "season": bs.get("season"),
                         "teams": rows, "available": bool(teams),
                         "note": None if teams else "no bracket or fixture rounds yet (league phase / groups not simulated to the title)"}
    p.store.put_json("arabs/continental-odds.json", {"generated": iso(p.now()), "competitions": out,
                                                     "method": "comp/{id}/bracket-sim.json Monte Carlo on the Tifo club rating"},
                     cache="static")


# ------------------------------------------------------------------ 311 nations h2h
def nations_h2h(p, rows):
    teams = {c["martj42"]: c for c in config.countries() if c.get("arab")}
    grid = {}
    for date, h, a, hs, as_, *_ in rows:
        if h in teams and a in teams:
            for me, op, f, g in ((h, a, hs, as_), (a, h, as_, hs)):
                x = grid.setdefault(teams[me]["iso2"], {}).setdefault(teams[op]["iso2"], {"p": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0,
                                                                                         "last": None})
                x["p"] += 1
                x["w" if f > g else "d" if f == g else "l"] += 1
                x["gf"] += f
                x["ga"] += g
                x["last"] = date
    p.store.put_json("arabs/nations-h2h.json", {"generated": iso(p.now()),
                                                "teams": [{"iso2": c["iso2"], "name_ar": c["name_ar"], "team": c["fotmob_team"]} for c in teams.values()],
                                                "matrix": grid, "source": "github.com/martj42/international_results (CC0)",
                                                "note": "matrix[A][B] = A's record against B (all internationals in the dataset)"},
                     cache="static")


# ------------------------------------------------------------------ 312 champion's path
def champion_path(p):
    rat_months = p.aux("arab_ratings").get("months") or {}
    names = p.names["teams"]
    for cid in ARAB_LEAGUES:
        if not p.has_time(8):
            return
        st = p.store.get_json(f"comp/{cid}/standings.json") or {}
        magic = (st.get("magic") or {}).get("teams") or {}
        champ, season, rows, decided = None, None, None, None
        leader = next((t for t, v in magic.items() if (v.get("title") or {}).get("state") == "clinched"), None)
        if leader:
            champ, season, decided = int(leader), st.get("season"), "clinched"
            rows = [HI.slim(m, season) for m in p.fixtures(cid) if m.get("id")]
        else:
            hist = p.aux(f"history/{cid}")
            done = sorted(s for s in hist if HI.finished(hist[s]))
            cur = (p.st.get("comp_meta", {}).get(str(cid)) or {}).get("season")
            past = [s for s in done if s != cur]
            if not past:
                continue
            season = past[-1]
            rows = HI.finished(hist[season])
            from compute import insights as IN
            tab = IN.season_tables({season: rows})[season]
            champ, decided = tab["champion"], "season_end"
        if not champ:
            continue
        mine = sorted((r for r in HI.finished(rows) if champ in (r["h"], r["a"])), key=lambda r: r["ko"] or "")
        matches, by_month = [], {}
        for r in mine:
            home = r["h"] == champ
            gf, ga = (r["hs"], r["as"]) if home else (r["as"], r["hs"])
            x = {"match": r["id"], "date": (r["ko"] or "")[:10], "opponent": r["a"] if home else r["h"],
                 "opponent_ar": names.get(str(r["a"] if home else r["h"])), "home": home, "gf": gf, "ga": ga}
            matches.append(x)
            by_month.setdefault(x["date"][:7], []).append(x)
        key = {}
        L = p.ledger(cid)["matches"] if decided == "clinched" else {}
        for mth, xs in by_month.items():
            big = max(xs, key=lambda x: (x["gf"] - x["ga"], x["gf"]))
            late = None
            for x in xs:
                e = L.get(str(x["match"]))
                if not e:
                    continue
                side = "home" if e["home"] == champ else "away"
                for g in e.get("goals") or []:
                    if g["side"] == side and (g.get("m") or 0) >= 80 and x["gf"] - x["ga"] in (0, 1):
                        late = {"match": x["match"], "minute": g.get("m"), "player": g.get("player")}
            key[mth] = {"biggest_win": big if big["gf"] > big["ga"] else None, "decisive_late_goal": late}
        p.store.put_json(f"comp/{cid}/champion-path.json", {
            "comp": cid, "season": season, "champion": champ, "champion_ar": names.get(str(champ)), "status": decided,
            "generated": iso(p.now()), "matches": matches,
            "rating_by_month": rat_months.get(str(champ)), "key_moments": key,
            "note": "status clinched = this season's title is mathematically decided; season_end = last completed season; "
                    "late goals need stored match events (current season only)"}, cache="static")


# ------------------------------------------------------------------ 315/316 coaches
def coaches(p):
    per, team_of = {}, {}
    names = p.names["teams"]
    for tid, c in p.aux("coaches").items():
        cur = (c or {}).get("coach") or {}
        if cur.get("id"):
            team_of[str(cur["id"])] = int(tid)
            per.setdefault(str(cur["id"]), {"id": cur["id"], "name": cur.get("name"), "country": cur.get("country"), "rows": []})
        for row in (c or {}).get("history") or []:
            if row.get("id"):
                x = per.setdefault(str(row["id"]), {"id": row["id"], "name": row.get("name"), "country": None, "rows": []})
                x["rows"].append({"team": int(tid), "team_ar": names.get(tid), "season": row.get("season"), "comp": row.get("comp"),
                                  "won": row.get("won"), "drawn": row.get("drawn"), "lost": row.get("lost"), "ppg": row.get("ppg")})
    for cid_, co in p.aux("national_coaches").items():
        if co and co.get("id"):
            team_of.setdefault(str(co["id"]), int(cid_))
            per.setdefault(str(co["id"]), {"id": co["id"], "name": co.get("name"), "country": co.get("country"), "rows": []})
    index = []
    for k, x in per.items():
        seen, rows = set(), []
        for r in x["rows"]:
            sig = (r["team"], r["season"], r["comp"])
            if sig not in seen:
                seen.add(sig)
                rows.append(r)
        x["rows"] = sorted(rows, key=lambda r: r["season"] or "")
        x["current_team"] = team_of.get(k)
        g = sum((r["won"] or 0) + (r["drawn"] or 0) + (r["lost"] or 0) for r in rows)
        x["totals"] = {"games": g, "won": sum(r["won"] or 0 for r in rows), "ppg": round(sum(((r["won"] or 0) * 3 + (r["drawn"] or 0))
                                                                                             for r in rows) / g, 2) if g else None}
        if p.has_time(3):
            p.store.put_json(f"coaches/{k}.json", {**x, "generated": iso(p.now()),
                                                   "note": "career rows = FotMob coachHistory of the covered clubs (team, season, W/D/L, ppg)"},
                             cache="static")
        index.append({"id": x["id"], "name": x["name"], "current_team": x["current_team"], "games": g})
    # coach vs coach
    pairs = {}
    for cid in set(AN.analytics_leagues()) | set(AR.CONTINENTAL) | {9943, 11027, 9942, 9941}:
        for e in p.ledger(cid)["matches"].values():
            co = e.get("coaches") or {}
            h, a = (co.get("home") or {}).get("id"), (co.get("away") or {}).get("id")
            sc = e.get("score")
            if not h or not a or not sc:
                continue
            k = tuple(sorted((h, a)))
            x = pairs.setdefault(k, {"coaches": list(k), "names": {}, "matches": []})
            x["names"][str(h)] = (co.get("home") or {}).get("name")
            x["names"][str(a)] = (co.get("away") or {}).get("name")
            x["matches"].append({"match": e["id"], "date": (e.get("ko") or "")[:10], "comp": cid, "home_coach": h, "away_coach": a,
                                 "score": [sc["home"], sc["away"]]})
    h2h_index = []
    for (a, b), x in pairs.items():
        if not p.has_time(3):
            break
        wins = {str(a): 0, str(b): 0, "draws": 0}
        for m in x["matches"]:
            if m["score"][0] == m["score"][1]:
                wins["draws"] += 1
            else:
                wins[str(m["home_coach"] if m["score"][0] > m["score"][1] else m["away_coach"])] += 1
        p.store.put_json(f"coaches/h2h/{a}-{b}.json", {**x, "wins": wins, "generated": iso(p.now())}, cache="static")
        h2h_index.append({"pair": f"{a}-{b}", "matches": len(x["matches"]), "names": x["names"]})
    p.store.put_json("coaches/index.json", {"generated": iso(p.now()), "coaches": sorted(index, key=lambda x: -x["games"]),
                                            "h2h": h2h_index,
                                            "note": "coach-vs-coach from stored lineups (coach at match time), this season's ledgers"},
                     cache="static")


# ------------------------------------------------------------------ 317 happiness
def happiness(p):
    sp = p.aux("arab_ratings").get("season_preds") or []
    if not sp:
        return False                  # pre-match probabilities come from the Arab clubs rating run: not ready yet
    now = p.now()
    names = p.names["teams"]
    per = {}
    for mid, ko, comp, h, a, pr, out in sp:
        if comp not in ARAB_LEAGUES or not ko or now - parse_utc(ko) > timedelta(days=7):
            continue
        for tid, home in ((h, True), (a, False)):
            exp = 3 * (pr[0] if home else pr[2]) + pr[1]
            act = 3 if (out == 0 and home) or (out == 2 and not home) else 1 if out == 1 else 0
            x = per.setdefault(tid, {"team": tid, "team_ar": names.get(str(tid)), "comp": comp, "matches": 0, "pts": 0, "xpts": 0.0})
            x["matches"] += 1
            x["pts"] += act
            x["xpts"] += exp
    rows = []
    for x in per.values():
        x["xpts"] = round(x["xpts"], 2)
        x["index"] = round(x["pts"] - x["xpts"], 2)
        x["mood"] = "happy" if x["index"] > 0.5 else "unhappy" if x["index"] < -0.5 else "neutral"
        rows.append(x)
    rows.sort(key=lambda x: -x["index"])
    p.store.put_json("arabs/happiness.json", {"generated": iso(now), "days": 7, "clubs": rows,
                                              "method": "points won minus expected points (Tifo pre-match probabilities) in the last 7 days; "
                                                        "mood: > +0.5 happy, < -0.5 unhappy"}, cache="warm")


# ------------------------------------------------------------------ 318 twins
def twins(p):
    comps = sorted(set(ARAB_LEAGUES) | set(BIG5))
    styles = EX.team_style({c: p.ledger(c)["matches"] for c in comps})
    keys = ["possession", "shots", "passes", "directness", "crosses", "ppda", "opp_half_passes", "touches_box", "aerials"]
    pool = [(tid, s) for tid, s in styles.items() if all(k in s["style"] for k in keys)]
    if len(pool) < 10:
        return
    n = len(keys)
    mean = [sum(s["style"][k] for _, s in pool) / len(pool) for k in keys]
    sd = [math.sqrt(sum((s["style"][k] - mean[i]) ** 2 for _, s in pool) / len(pool)) or 1 for i, k in enumerate(keys)]
    z = {t: [(s["style"][k] - mean[i]) / sd[i] for i, k in enumerate(keys)] for t, s in pool}
    comp = {t: s["comp"] for t, s in pool}
    out = {}
    for t in z:
        if comp[t] not in ARAB_LEAGUES:
            continue
        d = sorted((math.dist(z[t], z[o]), o) for o in z if o != t)
        out[t] = {"comp": comp[t], "team_ar": p.names["teams"].get(t),
                  "twins": [{"team": int(o), "comp": comp[o], "team_ar": p.names["teams"].get(o), "distance": round(x, 2)} for x, o in d[:3]],
                  "twin_in_big5": next(({"team": int(o), "comp": comp[o], "distance": round(x, 2)} for x, o in d if comp[o] in BIG5), None)}
    p.store.put_json("arabs/twins.json", {"generated": iso(p.now()), "features": keys, "clubs": out, "pool": len(pool),
                                          "method": "per-match team averages, z-scored over every club in the Arab leagues and the big five, "
                                                    "Euclidean distance"}, cache="static")


# ------------------------------------------------------------------ 319 finishing
FIN_FEATURES = ("ontarget_scoring_att", "total_scoring_att", "big_chance_missed", "penalty_won")


def _season_total(stats, k):
    """Season count of a stat: FotMob's per-90 lists (shots, shots on target) carry `total` (rate x minutes / 90)."""
    s = stats.get(k) or {}
    return (s["total"] if "total" in s else s.get("value")) or 0


def finishing(p):
    tabs = {int(k): v for k, v in p.aux("ptables").items()}
    X, y = [], []
    for cid, t in tabs.items():
        for pid, r in t["players"].items():
            xg = (r["stats"].get("expected_goals") or {}).get("value")
            if xg is None:
                continue
            f = [_season_total(r["stats"], k) for k in FIN_FEATURES]
            if f[1] >= 10:
                X.append([1.0] + [float(v) for v in f])
                y.append(float(xg))
    model = None
    if len(y) >= 50:
        k = len(X[0])
        A = [[sum(r[i] * r[j] for r in X) for j in range(k)] for i in range(k)]
        b = [sum(r[i] * t for r, t in zip(X, y)) for i in range(k)]
        coef = DG._solve(A, b)
        if coef:
            pred = [sum(c * v for c, v in zip(coef, r)) for r in X]
            my = sum(y) / len(y)
            r2 = 1 - sum((t - q) ** 2 for t, q in zip(y, pred)) / sum((t - my) ** 2 for t in y)
            model = {"coef": dict(zip(("intercept",) + FIN_FEATURES, [round(c, 4) for c in coef])), "r2": round(r2, 3), "n": len(y)}
    written = 0
    for cid in set(ARAB_LEAGUES) | set(BIG5):
        t = tabs.get(cid)
        if not t:
            continue
        rows = []
        for pid, r in t["players"].items():
            st = r["stats"]
            shots = _season_total(st, "total_scoring_att")
            if shots < 10:
                continue
            goals = (st.get("goals") or {}).get("value") or 0
            xg = (st.get("expected_goals") or {}).get("value")
            proxy = False
            if xg is None and model:
                f = [1.0] + [float(_season_total(st, k)) for k in FIN_FEATURES]
                xg = max(0.0, sum(model["coef"][k] * v for k, v in zip(("intercept",) + FIN_FEATURES, f)))
                proxy = True
            if xg is None:
                continue
            rows.append({"player": int(pid), "name": r["name"], "team": r["team"], "shots": round(shots), "goals": goals,
                         "xg": round(xg, 2), "luck": round(goals - xg, 2), "proxy": proxy})
        rows.sort(key=lambda x: -x["luck"])
        if rows:
            p.store.put_json(f"comp/{cid}/finishing.json", {"comp": cid, "generated": iso(p.now()), "min_shots": 10, "players": rows,
                                                            "proxy_model": model if any(r["proxy"] for r in rows) else None,
                                                            "note": "goals minus xG; where FotMob has no player xG, a linear proxy from "
                                                                    "shots on target, shots, big chances missed and penalties won, fitted on "
                                                                    "players with xG in the other leagues; shots = FotMob's shots "
                                                                    "per 90 x minutes / 90"}, cache="static")
            written += 1
    return written > 0                  # False = not ready (no table reached 10 shots yet): analytics_chores retries soon


# ------------------------------------------------------------------ 320 anniversaries
def anniversaries(p, limit=10):
    try:
        with open(os.path.join(HERE, "arab_clubs.json"), encoding="utf-8") as f:
            research = json.load(f).get("clubs") or {}
    except OSError:
        research = {}
    found = p.aux("founded")
    for x in research.values():
        if x.get("fotmob_id") and (x.get("founded") or {}).get("year"):
            found[str(x["fotmob_id"])] = {"date": x["founded"].get("date"), "year": x["founded"]["year"],
                                          "source": x["founded"].get("source"), "name_ar": x.get("name_ar")}
    iso2_q = {}
    n = 0
    teams = sorted(k for k, v in p.st.get("team_comps", {}).items() if set(v) & set(ARAB_LEAGUES))
    for tid in teams:
        if tid in found or n >= limit or not p.has_time(6) or not p.due("wd_club", 30 * 1440, tid):
            continue
        n += 1
        p.mark("wd_club", tid)
        name = (p.st.get("teams", {}).get(tid) or [None])[0]
        c = p.team_country(int(tid)) or {}
        if not name or not c.get("iso2"):
            continue
        try:
            q = ('SELECT ?c ?inc WHERE { ?c wdt:P31/wdt:P279* wd:Q476028; wdt:P17 ?k. ?k wdt:P297 "%s". '
                 '?c rdfs:label|skos:altLabel ?l. FILTER(LCASE(STR(?l)) = LCASE("%s")) OPTIONAL { ?c wdt:P571 ?inc } } LIMIT 3'
                 % (c["iso2"], name.replace('"', "")))
            r = json.loads(urllib.request.urlopen(urllib.request.Request(
                "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q), headers={"User-Agent": UA}), timeout=30).read())
            b = [x for x in r["results"]["bindings"] if x.get("inc")]
            if len({x["c"]["value"] for x in b}) == 1:
                inc = b[0]["inc"]["value"][:10]
                found[tid] = {"date": inc if not inc.endswith("-01-01") else None, "year": int(inc[:4]),
                              "source": b[0]["c"]["value"]}
        except ERRORS as e:
            p.store.fail("wikidata-founded", e)
    by_day, years_only = {}, []
    for tid, f in found.items():
        row = {"team": int(tid), "name_ar": f.get("name_ar") or p.names["teams"].get(tid), "year": f["year"], "source": f.get("source")}
        if f.get("date") and len(f["date"]) == 10:
            by_day.setdefault(f["date"][5:], []).append({**row, "date": f["date"]})
        else:
            years_only.append(row)
    p.store.put_json("clubs/anniversaries.json", {"generated": iso(p.now()), "by_day": dict(sorted(by_day.items())),
                                                  "year_only": sorted(years_only, key=lambda r: r["year"]),
                                                  "sources": "research/tifo-2026-09-27/arab_clubs.json (Wikidata P571) + Wikidata "
                                                             "(exact label match, football club in the same country, one result only)"},
                     cache="static")


# ------------------------------------------------------------------ 322 year calendar
def year_calendar(p):
    now = p.now()
    events = []
    for c in p.comps:
        for m in p.fixtures(c["id"]) or []:
            if str(m.get("round") or "").lower() == "final" and m.get("kickoff_utc"):
                events.append({"date": m["kickoff_utc"][:10], "kind": "final", "comp": c["id"], "name_ar": c["name_ar"], "match": m["id"],
                               "source": "FotMob fixtures"})
    for cid, v in (p.st.get("draws") or {}).items():
        for d in v:
            events.append({"date": d["at"][:10], "kind": "draw_seen", "comp": int(cid), "source": "detected by the poller"})
    cal = p.store.get_json("arabs/calendars.json") or {}
    for w in cal.get("national_team_windows") or []:
        events.append({"date": w["from"], "to": w["to"], "kind": "international_window", "source": "covered national-team fixtures"})
    for cid, v in (cal.get("leagues") or {}).items():
        events.append({"date": v["first_match"], "kind": "league_start", "comp": int(cid), "source": "FotMob fixtures"})
        for b in v.get("breaks") or []:
            events.append({"date": b["from"], "to": b["to"], "kind": "league_break", "comp": int(cid), "source": "FotMob fixtures"})
    y0 = now.strftime("%Y-%m-%d")
    y1 = (now + timedelta(days=366)).strftime("%Y-%m-%d")
    events = sorted((e for e in events if y0 <= e["date"] <= y1 or e.get("to", "") >= y0 and e["date"] <= y1), key=lambda e: e["date"])
    p.store.put_json("calendar/year.json", {"generated": iso(now), "from": y0, "to": y1, "events": events,
                                            "not_included": "transfer windows and award dates: no machine-readable, verifiable source was "
                                                            "found (each association sets its own windows); FIFA/AFC/CAF draw dates appear "
                                                            "when the draw is detected in the data"}, cache="static")


# ------------------------------------------------------------------ 219 suspensions, 325 absences
def _rules():
    try:
        with open(os.path.join(HERE, "suspension_rules.json"), encoding="utf-8") as f:
            d = json.load(f)
    except OSError:
        return {}
    return {v["fotmob_id"]: dict(v, key=k) for k, v in d.items() if k != "_meta" and isinstance(v, dict) and v.get("fotmob_id")}


def _next_threshold(y, rules):
    ths = sorted((r["yellows"], r) for r in rules if r.get("yellows"))
    for t, r in ths:
        if t > y:
            return t, r
    if ths and ths[-1][1].get("repeat_every"):
        last, r = ths[-1]
        k = r["repeat_every"]
        return last + k * ((y - last) // k + 1), r
    return None, None


def _is_threshold(y, rules):
    ths = sorted((r["yellows"], r) for r in rules if r.get("yellows"))
    for t, r in ths:
        if y == t:
            return r
    if ths and ths[-1][1].get("repeat_every"):
        last, r = ths[-1]
        if y > last and (y - last) % r["repeat_every"] == 0:
            return r
    return None


def suspensions(p, cid):
    rule = _rules().get(cid)
    t = (p.aux("ptables").get(str(cid)) or {}).get("players") or {}
    if not t:
        return None
    L = p.ledger(cid)["matches"]
    last_match = {}
    for e in sorted(L.values(), key=lambda e: e.get("ko") or ""):
        for side in ("home", "away"):
            last_match[e[side]] = e
    out = {"suspended": [], "at_risk": [], "unknown_rules": not (rule and rule.get("rules"))}
    for pid, r in t.items():
        st = r["stats"]
        y = int((st.get("yellow_card") or {}).get("value") or 0)
        red = int((st.get("red_card") or {}).get("value") or 0)
        team = r["team"]
        lm = last_match.get(team)
        cards_last = [c for c in (lm or {}).get("cards_p", []) if str(c[0]) == pid] if lm else []
        row = {"player": int(pid), "name": r["name"], "team": team, "yellows": y, "reds": red}
        if any(c[1] in ("red", "second_yellow") for c in cards_last):
            out["suspended"].append({**row, "reason": "red_card_last_match", "ban_matches": ((rule or {}).get("red_ban") or {}).get("min_matches") or 1,
                                     "match": lm["id"]})
            continue
        if rule and rule.get("rules"):
            hit = _is_threshold(y, rule["rules"])
            if hit and any(c[1] == "yellow" for c in cards_last):
                out["suspended"].append({**row, "reason": "yellow_threshold", "ban_matches": hit.get("ban_matches"),
                                         "threshold": hit["yellows"], "until": hit.get("until"), "match": lm["id"]})
                continue
            nxt, r2 = _next_threshold(y, rule["rules"])
            if nxt and nxt - y == 1:
                out["at_risk"].append({**row, "next_threshold": nxt, "ban_matches": r2.get("ban_matches"), "until": r2.get("until")})
    return out, rule


def suspensions_and_absences(p):
    for cid in AN.analytics_leagues():
        if not p.has_time(8):
            return
        res = suspensions(p, cid)
        rule = res[1] if res else _rules().get(cid)
        if res:
            s, _ = res
            p.store.put_json(f"comp/{cid}/suspensions.json", {
                "comp": cid, "generated": iso(p.now()), **s,
                "rules": {"key": (rule or {}).get("key"), "rules": (rule or {}).get("rules"), "red_ban": (rule or {}).get("red_ban"),
                          "reset": (rule or {}).get("reset"), "confidence": (rule or {}).get("confidence"),
                          "sources": (rule or {}).get("sources")},
                "note": "yellow counts = FotMob season lists (league only); 'suspended' needs the card in the team's last stored "
                        "match (ledger); thresholds with an 'until' condition are listed but the condition is not evaluated"},
                cache="warm")
        # absences for the coming round
        fx = p.fixtures(cid) or []
        now = p.now()
        nxt = sorted((m for m in fx if m["status"] == S.SCHEDULED and m.get("kickoff_utc") and parse_utc(m["kickoff_utc"]) > now),
                     key=lambda m: m["kickoff_utc"])
        if not nxt:
            continue
        rnd = nxt[0].get("round")
        coming = [m for m in nxt if m.get("round") == rnd] if rnd else nxt[:10]
        susp = (res[0]["suspended"] if res else [])
        inj = p.aux("injuries")
        teams = {}
        for m in coming:
            det = p.store.get_json(f"match/{m['id']}.json") if p.has_time(3) else None
            for side in ("home", "away"):
                tid = m[side]["id"]
                unav = (((det or {}).get("lineups") or {}).get(side) or {}).get("unavailable") or []
                squad_inj = [{"id": pl["id"], "name": pl["name"], "type": "injury", "detail": pl.get("injury")}
                             for g in p.aux("squads").get(str(tid)) or [] for pl in g.get("players") or [] if pl.get("injury")]
                teams[str(tid)] = {"match": m["id"], "kickoff_utc": m["kickoff_utc"],
                                   "unavailable_from_match": unav, "injured_in_squad": squad_inj or inj.get(str(tid)) or [],
                                   "suspended": [x for x in susp if x["team"] == tid]}
        p.store.put_json(f"comp/{cid}/absences.json", {"comp": cid, "round": rnd, "generated": iso(now), "teams": teams,
                                                       "note": "match detail 'unavailable' (FotMob, published close to kickoff), squad "
                                                               "injury flags (team pages we hold) and suspensions from comp/{id}/suspensions.json"},
                         cache="warm")


# ------------------------------------------------------------------ 326-330
def league_books(p):
    from compute import insights as IN
    names = p.names["teams"]
    for cid in ARAB_LEAGUES:
        if not p.has_time(10):
            return
        seasons = (p.store.get_json(f"comp/{cid}/seasons.json") or {}).get("seasons") or {}
        if seasons:
            p.store.put_json(f"comp/{cid}/alltime-table.json", {"comp": cid, "generated": iso(p.now()), "since": min(seasons),
                                                                "table": IN.alltime_table(seasons),
                                                                "note": "sum of the computed season tables since 2010/11 (FotMob results); "
                                                                        "titles = first place in those computed tables"}, cache="static")
            st = p.store.get_json(f"comp/{cid}/standings.json") or {}
            if st.get("groups"):
                pr = IN.promoted(seasons, st["groups"][0]["rows"], st.get("season") or "")
                if pr:
                    n_now = max((x["played"] for x in pr["promoted_now"]), default=0)
                    hist = AN.all_history(p, comps=(cid,)).get(str(cid), {})
                    for x in pr["past_promoted"]:
                        games = sorted((r for r in HI.finished(hist.get(x["season"]) or []) if x["team"] in (r["h"], r["a"])),
                                       key=lambda r: r["ko"] or "")[:n_now]
                        pts = sum(3 if f > a else 1 if f == a else 0 for f, a in
                                  (((r["hs"], r["as"]) if r["h"] == x["team"] else (r["as"], r["hs"])) for r in games))
                        x["pts_after_same_games"] = pts if len(games) == n_now else None
                    pr["same_games"] = n_now
                    p.store.put_json(f"comp/{cid}/promoted.json", {"comp": cid, "season": st.get("season"), "generated": iso(p.now()), **pr,
                                                                   "note": "promoted = not in last season's table; past_promoted gives "
                                                                           "each earlier newcomer's final rank and points"}, cache="static")
        L = p.ledger(cid)["matches"]
        if L:
            p.store.put_json(f"comp/{cid}/late-goals.json", {"comp": cid, "generated": iso(p.now()), **IN.late_goals(L),
                                                             "note": "goals after 90 minutes that turned a draw into a win or a loss "
                                                                     "into a draw (this season's stored matches)"}, cache="static")


def club_records_step(p, limit=80):
    from compute import insights as IN
    comps = AN.history_comps()
    rows = HI.finished(HI.all_rows(AN.all_history(p, comps=comps)))
    teams = sorted(int(k) for k, v in p.st.get("team_comps", {}).items() if set(v) & set(ARAB_LEAGUES))
    cur = p.aux("cursor").get("club_records", 0)
    n = 0
    while teams and n < limit and p.has_time(6):
        tid = teams[cur % len(teams)]
        L = {}
        for cid in p.st.get("team_comps", {}).get(str(tid), []):
            L.update(p.ledger(cid)["matches"])
        rec = IN.club_records(rows, L, tid)
        if rec:
            p.store.put_json(f"team/{tid}/records.json", {"team": tid, "team_ar": p.names["teams"].get(str(tid)),
                                                         "generated": iso(p.now()), **rec,
                                                         "note": "results since 2010/11 (FotMob history); appearances and scorers from "
                                                                 "this season's stored lineups and events"}, cache="static")
        cur += 1
        n += 1
    p.aux("cursor")["club_records"] = cur



# ------------------------------------------------------------------ 337 World Cup
GOALS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/goalscorers.csv"


def worldcup(p, rows):
    import csv, io
    teams = {c["martj42"]: c for c in config.countries() if c.get("arab")}
    try:
        text = urllib.request.urlopen(urllib.request.Request(GOALS_URL, headers={"User-Agent": UA}), timeout=40).read().decode("utf-8")
        scorers = list(csv.DictReader(io.StringIO(text)))
    except ERRORS as e:
        p.store.fail("worldcup:goalscorers", e)
        scorers = []
    by_match = {}
    for g in scorers:
        by_match.setdefault((g["date"], g["home_team"], g["away_team"]), []).append(
            {"team": g["team"], "scorer": g["scorer"], "minute": g.get("minute"), "own_goal": g.get("own_goal") == "TRUE",
             "penalty": g.get("penalty") == "TRUE"})
    out = {}
    for date, h, a, hs, as_, tour, neutral, *venue in rows:
        if tour != "FIFA World Cup" or not (h in teams or a in teams):
            continue
        for me in (h, a):
            if me not in teams:
                continue
            c = teams[me]
            opp = a if me == h else h
            gf, ga = (hs, as_) if me == h else (as_, hs)
            t = out.setdefault(c["iso2"], {"team": c["fotmob_team"], "name_ar": c["name_ar"], "tournaments": {}})
            t["tournaments"].setdefault(date[:4], []).append({
                "date": date, "opponent": opp, "gf": gf, "ga": ga, "result": "W" if gf > ga else "D" if gf == ga else "L",
                "venue": {"city": venue[0], "country": venue[1]} if venue and venue[0] else None,
                "goals": [x for x in by_match.get((date, h, a), []) if x["team"] == me]})
    for t in out.values():
        allm = [m for ms in t["tournaments"].values() for m in ms]
        t["summary"] = {"tournaments": len(t["tournaments"]), "played": len(allm), "won": sum(m["result"] == "W" for m in allm),
                        "drawn": sum(m["result"] == "D" for m in allm), "lost": sum(m["result"] == "L" for m in allm),
                        "gf": sum(m["gf"] for m in allm), "ga": sum(m["ga"] for m in allm)}
    p.store.put_json("arabs/worldcup.json", {"generated": iso(p.now()), "teams": out,
                                             "source": "github.com/martj42/international_results results.csv + goalscorers.csv (CC0)",
                                             "note": "World Cup finals matches only; goals list scorers where the dataset has them"},
                     cache="static")
