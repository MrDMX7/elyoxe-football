"""Season aggregates from the per-competition LEDGER: one compact line per finished match, written
when the poller fetches that match's final detail (live transition or the backfill cursor).
Everything here is computed from normalized data, so it survives a provider switch.

Outputs (docs/SCHEMA.md):
  referees      per referee: matches, yellow/red cards, penalties given, VAR decisions (+ FotMob's own
                referee stats block when it exists)
  xg_table      xG for/against, expected points (independent Poisson on match xG), luck = pts - xPts.
                Only where FotMob has "xG" coverage; UAE competitions are "ratings"/"lower" -> unavailable
  ht_table      the table if every match had ended at half-time
  goal_bands    goals for/against per team in 15-minute bands (45+ stoppage counts in 31-45, 90+ in 76-90)
  shots         per player season shot list (only with "xG" coverage)
  last_season   points and goals after the same number of games last season
  players       per-90 values and league percentiles from FotMob's per-player stat lists (radar)
  foreigners    best non-national players per league; uae_abroad: UAE nationals at clubs outside the UAE
"""
import math

BANDS = [(1, 15, "1-15"), (16, 30, "16-30"), (31, 45, "31-45+"), (46, 60, "46-60"), (61, 75, "61-75"), (76, 90, "76-90+")]


def ledger_entry(d: dict) -> dict:
    """Normalized match detail -> compact ledger line."""
    hid, aid = d["home"]["id"], d["away"]["id"]
    cards = {"home": {"yellow": 0, "second_yellow": 0, "red": 0}, "away": {"yellow": 0, "second_yellow": 0, "red": 0}}
    pens = {"home": {"scored": 0, "missed": 0}, "away": {"scored": 0, "missed": 0}}
    goals, var = [], []
    prev = {"home": 0, "away": 0}
    for e in d.get("events") or []:
        side = e.get("team")
        t = e["type"]
        if t in ("yellow", "second_yellow", "red") and side in cards:
            cards[side][t] += 1
        elif t in ("goal", "own_goal", "penalty_goal"):
            sc = e.get("score")
            benef = side
            if sc:   # the side whose score went up (own goals credit the other team)
                benef = "home" if sc["home"] > prev["home"] else "away" if sc["away"] > prev["away"] else side
                prev = sc
            elif t == "own_goal" and side:
                benef = "away" if side == "home" else "home"
            goals.append({"m": e.get("minute"), "add": e.get("added"), "side": benef, "type": t,
                          "player": (e.get("player") or {}).get("id") if t != "own_goal" else None,
                          "assist": (e.get("assist") or {}).get("id")})
            if t == "penalty_goal" and side in pens:
                pens[side]["scored"] += 1
        elif t == "missed_penalty" and side in pens:
            pens[side]["missed"] += 1
        elif t == "var":
            var.append({"m": e.get("minute"), "side": side, "outcome": e.get("var_outcome"), "key": e.get("reason_key")})
    shots = None
    if d.get("shotmap"):
        shots = {}
        for pid, p in d["shotmap"].items():
            tid = hid if p["team"] == "home" else aid
            shots[pid] = {"name": p["name"], "team": tid,
                          "s": [[x["minute"], x["xg"], x["result"], x["x"], x["y"], x.get("xgot")] for x in p["shots"]]}
    players = {}
    for side in ("home", "away"):
        lu = (d.get("lineups") or {}).get(side) or {}
        tid = hid if side == "home" else aid
        starters = {p.get("id") for p in lu.get("starters") or []}
        for p in (lu.get("starters") or []) + (lu.get("subs") or []):
            if p.get("id"):   # [name, country, team, rating, role, age, starter, minutes]
                st_ = p.get("id") in starters
                on, off = p.get("minutes_on"), p.get("minutes_off")
                mins = ((off or 90) if st_ else ((off or 90) - on if on is not None else 0))
                players[str(p["id"])] = [p.get("name"), p.get("country"), tid, p.get("rating"), p.get("role"),
                                         p.get("age"), st_, max(0, mins)]
    stats = {}
    for g in d.get("stats") or []:
        for it in g["items"]:
            h, a = _statnum(it["home"]), _statnum(it["away"])
            if h is not None and a is not None and it["key"] not in stats:
                stats[it["key"]] = [h, a]
    lus = d.get("lineups") or {}
    coaches = {side: ((lus.get(side) or {}).get("coach")) for side in ("home", "away")}
    formations = {side: (lus.get(side) or {}).get("formation") for side in ("home", "away")}
    return {
        "v": LEDGER_VERSION, "stats": stats or None, "coaches": coaches, "formations": formations,
        "id": d["id"], "ko": d.get("kickoff_utc"), "round": d.get("round"), "home": hid, "away": aid,
        "score": d.get("score"), "ht": d.get("halftime_score"), "xg": d.get("xg"), "coverage": d.get("coverage"),
        "referee": ({k: d["referee"].get(k) for k in ("id", "name", "country")} if d.get("referee") else None),
        "referee_stats": (d.get("referee") or {}).get("source_stats"),
        "cards": cards, "pens": pens, "goals": goals, "var": var, "shots": shots, "players": players,
        "att": d.get("attendance"),
    }


LEDGER_VERSION = 3   # 3: refetch so every finished match file carries its win-probability curve


def _statnum(v):
    """12 -> 12, "1.31" -> 1.31, "356 (85%)" -> 356; anything else None."""
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        import re
        m = re.match(r"\s*(-?\d+(?:\.\d+)?)", v)
        if m:
            f = float(m.group(1))
            return int(f) if f.is_integer() else f
    return None


def _band(minute, added):
    if minute is None:
        return None
    if minute > 90:
        return "extra-time"
    for lo, hi, label in BANDS:
        if lo <= minute <= hi:
            return label
    return "1-15" if minute < 1 else None


def goal_bands(ledger: dict) -> dict:
    labels = [b[2] for b in BANDS] + ["extra-time"]
    teams = {}
    for e in ledger.values():
        for side, other in (("home", "away"), ("away", "home")):
            tid = e[side]
            teams.setdefault(str(tid), {"for": dict.fromkeys(labels, 0), "against": dict.fromkeys(labels, 0), "matches": 0})
            teams[str(tid)]["matches"] += 1
        for g in e.get("goals") or []:
            b = _band(g["m"], g.get("add"))
            if not b or g["side"] not in ("home", "away"):
                continue
            scorer = str(e[g["side"]])
            conceder = str(e["away" if g["side"] == "home" else "home"])
            teams[scorer]["for"][b] += 1
            teams[conceder]["against"][b] += 1
    return {"bands": labels, "teams": teams, "note": "45+x counts in 31-45+, 90+x in 76-90+; own goals credit the benefiting team"}


def _table(results):
    """results [(home, away, hg, ag)] -> rows sorted pts, gd, gf (a computed table, not the official order)."""
    t = {}
    for h, a, hg, ag in results:
        for tid, gf, ga in ((h, hg, ag), (a, ag, hg)):
            r = t.setdefault(tid, {"team": tid, "played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0, "pts": 0})
            r["played"] += 1
            r["gf"] += gf
            r["ga"] += ga
            if gf > ga:
                r["won"] += 1
                r["pts"] += 3
            elif gf == ga:
                r["drawn"] += 1
                r["pts"] += 1
            else:
                r["lost"] += 1
    rows = sorted(t.values(), key=lambda r: (-r["pts"], -(r["gf"] - r["ga"]), -r["gf"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
        r["gd"] = r["gf"] - r["ga"]
    return rows


def ht_table(ledger: dict) -> dict:
    res = [(e["home"], e["away"], e["ht"]["home"], e["ht"]["away"]) for e in ledger.values() if e.get("ht")]
    return {"rows": _table(res), "matches": len(res), "order": "computed: pts, goal difference, goals for"}


def _poisson(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def xpts(xg_h, xg_a, cap=10):
    ph = [_poisson(i, max(xg_h, 0.001)) for i in range(cap + 1)]
    pa = [_poisson(i, max(xg_a, 0.001)) for i in range(cap + 1)]
    win = sum(ph[i] * pa[j] for i in range(cap + 1) for j in range(cap + 1) if i > j)
    draw = sum(ph[i] * pa[i] for i in range(cap + 1))
    loss = 1 - win - draw
    return 3 * win + draw, 3 * loss + draw


def xg_table(ledger: dict) -> dict:
    with_xg = [e for e in ledger.values() if e.get("xg") and e.get("score")]
    if not with_xg:
        cov = sorted({e.get("coverage") for e in ledger.values() if e.get("coverage")})
        return {"available": False, "reason": f"source has no xG for this competition (coverage: {', '.join(cov) or 'unknown'})"}
    t = {}
    for e in with_xg:
        xh, xa = float(e["xg"]["home"]), float(e["xg"]["away"])
        ph, pa = xpts(xh, xa)
        sh, sa = e["score"]["home"], e["score"]["away"]
        for tid, xf, xa_, xp, gf, ga in ((e["home"], xh, xa, ph, sh, sa), (e["away"], xa, xh, pa, sa, sh)):
            r = t.setdefault(tid, {"team": tid, "played": 0, "xg_for": 0.0, "xg_against": 0.0, "xpts": 0.0, "pts": 0, "gf": 0, "ga": 0})
            r["played"] += 1
            r["xg_for"] += xf
            r["xg_against"] += xa_
            r["xpts"] += xp
            r["gf"] += gf
            r["ga"] += ga
            r["pts"] += 3 if gf > ga else 1 if gf == ga else 0
    rows = []
    for r in t.values():
        rows.append({**r, "xg_for": round(r["xg_for"], 2), "xg_against": round(r["xg_against"], 2),
                     "xg_diff": round(r["xg_for"] - r["xg_against"], 2), "xpts": round(r["xpts"], 2),
                     "luck": round(r["pts"] - r["xpts"], 2)})
    rows.sort(key=lambda r: (-r["xpts"], -r["xg_diff"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return {"available": True, "rows": rows, "matches": len(with_xg),
            "method": "expected points from independent Poisson goals with the match xG as means; luck = pts - xPts"}


def referees(ledger: dict) -> dict:
    out = {}
    for e in ledger.values():
        ref = e.get("referee")
        if not ref or not ref.get("name"):
            continue
        k = str(ref.get("id") or ref["name"])
        r = out.setdefault(k, {"id": ref.get("id"), "name": ref["name"], "country": ref.get("country"), "matches": 0,
                               "yellow": 0, "second_yellow": 0, "red": 0, "penalties": 0, "var": 0, "match_ids": [],
                               "source_stats": None})
        r["matches"] += 1
        r["match_ids"].append(e["id"])
        for side in ("home", "away"):
            c = e["cards"][side]
            r["yellow"] += c["yellow"]
            r["second_yellow"] += c["second_yellow"]
            r["red"] += c["red"] + c["second_yellow"]
            r["penalties"] += e["pens"][side]["scored"] + e["pens"][side]["missed"]
        r["var"] += len(e.get("var") or [])
        if e.get("referee_stats") and (r["source_stats"] is None or (e.get("ko") or "") >= r.get("_ss_ko", "")):
            r["source_stats"], r["_ss_ko"] = e["referee_stats"], e.get("ko") or ""
    for r in out.values():
        r.pop("_ss_ko", None)
        m = r["matches"] or 1
        r["yellow_per_match"] = round(r["yellow"] / m, 2)
        r["penalties_per_match"] = round(r["penalties"] / m, 2)
    return {"referees": sorted(out.values(), key=lambda r: -r["matches"]),
            "note": "counted from match events we stored (penalties = scored + missed, second yellow counted as red); "
                    "source_stats = FotMob's own referee block (its scope may be another competition)"}


def shots(ledger: dict) -> dict:
    per = {}
    for e in ledger.values():
        for pid, p in (e.get("shots") or {}).items():
            r = per.setdefault(pid, {"name": p["name"], "team": p["team"], "shots": 0, "goals": 0, "xg": 0.0, "list": []})
            for s in p["s"]:
                r["shots"] += 1
                r["goals"] += 1 if s[2] == "Goal" else 0
                r["xg"] += s[1] or 0
                r["list"].append([e["id"]] + s)
    for r in per.values():
        r["xg"] = round(r["xg"], 2)
    if not per:
        return {"available": False, "reason": "source publishes no shot map for this competition"}
    return {"available": True, "fields": ["match", "minute", "xg", "result", "x", "y", "xgot"], "players": per}


def last_season_same_round(prev_matches: list[dict], played_now: dict) -> dict:
    """prev_matches: last season's normalized league matches; played_now {team_id: games played now}.
    -> {team_id: {played, pts, gf, ga} after that many games last season} (absent if not in the league)."""
    per = {}
    for m in sorted((m for m in prev_matches if m["status"] == "finished" and m.get("score")), key=lambda m: m["kickoff_utc"] or ""):
        for side, other in (("home", "away"), ("away", "home")):
            tid = m[side]["id"]
            per.setdefault(tid, []).append((m["score"][side], m["score"][other]))
    out = {}
    for tid, n in played_now.items():
        games = per.get(int(tid))
        if not games or n == 0:
            continue
        g = games[:n]
        pts = sum(3 if a > b else 1 if a == b else 0 for a, b in g)
        out[str(tid)] = {"played": len(g), "pts": pts, "gf": sum(a for a, _ in g), "ga": sum(b for _, b in g)}
    return out


def player_table(stat_lists: dict, min_minutes=270) -> dict:
    """FotMob per-player season lists -> per player {stat: value, per90, percentile} + league averages.
    Percentiles are among players with >= min_minutes minutes (the radar population)."""
    mins = {}
    for e in (stat_lists.get("mins_played") or {}).get("entries", []):
        mins[str(e["player"]["id"])] = e["value"] or e.get("minutes") or 0
    players, averages = {}, {}
    for stat, sl in stat_lists.items():
        vals = []
        for e in sl["entries"]:
            pid = str(e["player"]["id"])
            m = mins.get(pid) or e.get("minutes") or 0
            p = players.setdefault(pid, {"name": e["player"]["name"], "team": e.get("team_id"), "minutes": m, "stats": {}})
            v = e["value"]
            per90 = None
            if v is not None and m and not stat.endswith("_per_90") and stat not in ("rating", "mins_played") \
                    and not stat.startswith("_save") and "percent" not in (sl.get("format") or ""):
                per90 = round(v * 90 / m, 3)
            p["stats"][stat] = {"value": v, "per90": per90}
            if m >= min_minutes and v is not None:
                vals.append((pid, per90 if per90 is not None else v))
        if vals:
            srt = sorted(x[1] for x in vals)
            n = len(srt)
            averages[stat] = round(sum(srt) / n, 3)
            for pid, v in vals:
                below = sum(1 for x in srt if x < v)
                players[pid]["stats"][stat]["pct"] = round(100 * below / max(n - 1, 1), 1)
    return {"min_minutes": min_minutes, "averages": averages, "players": players,
            "note": "per90 = value x 90 / minutes (not for ratings, percentages or lists that are already per 90); "
                    "pct = percentile among players with >= min_minutes"}


def nationality_map(ledgers: list[dict], squads: list[dict]) -> dict:
    """{player_id: country} from squads (FotMob ccode) and every lineup in the ledgers."""
    nat = {}
    for L in ledgers:
        for e in L.values():
            for pid, pl in (e.get("players") or {}).items():
                name, cc, tid = pl[:3]
                if cc:
                    nat[pid] = cc
    for sq in squads:
        if sq.get("national"):
            continue
        for g in sq.get("squad") or []:
            for p in g["players"]:
                if p.get("country"):
                    nat[str(p["id"])] = p["country"]
    return nat


def foreigners(players: dict, nat: dict, league_country: str, top=25) -> dict:
    """Best non-national players of a league, from the player table (rating, goals, assists)."""
    rows = []
    for pid, p in players.get("players", {}).items():
        cc = nat.get(pid)
        if not cc or cc == league_country:
            continue
        s = p["stats"]
        rows.append({"id": int(pid), "name": p["name"], "team": p["team"], "country": cc, "minutes": p["minutes"],
                     "rating": (s.get("rating") or {}).get("value"), "goals": (s.get("goals") or {}).get("value") or 0,
                     "assists": (s.get("goal_assist") or {}).get("value") or 0})
    rows.sort(key=lambda r: (-(r["rating"] or 0), -(r["goals"] + r["assists"])))
    return {"league_country": league_country, "players": rows[:top], "count": len(rows),
            "unknown_nationality": sum(1 for pid in players.get("players", {}) if pid not in nat),
            "note": "ranked by FotMob season rating, then goals + assists; nationality from squads and lineups"}
