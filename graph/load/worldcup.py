"""The World Cup in full, 1930–2022 (spec §9; jfjelstul/worldcup, CC-BY-SA, fetched weekly into db/.cache/fjelstul_*.csv):
every men's World Cup match linked to ours by date and the two national teams, or added under the World Cup's editions
(FotMob 77), with its lineups (since 1970 in the source), goals (penalties, own goals), cards, substitutions, coaches and
referee. A match FotMob already holds in detail keeps FotMob's lineups and events."""
import csv, os
from collections import defaultdict
from graph.link import MatchIndex, edition_for, twin
from graph.load.fjelstul import WORLD_CUP, resolver


def rows(S, name):
    p = os.path.join(S.db, f"fjelstul_{name}.csv")
    if not os.path.exists(p):
        return []
    return [r for r in csv.DictReader(open(p, encoding="utf-8", newline="")) if (r.get("tournament_id") or "").startswith("WC-")]


def _i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def load(G, reg, S):
    matches = rows(S, "matches")
    if not matches:
        return {"skipped": "no fjelstul_matches.csv"}
    cid = reg.mint("competition", "fotmob", WORLD_CUP)
    G.put("competition", {"cid": cid, "name": "World Cup", "name_ar": "كأس العالم"}, "fotmob")
    person = resolver(G, reg, S)
    by = {k: defaultdict(list) for k in ("player_appearances", "goals", "bookings", "substitutions", "manager_appearances", "referee_appearances")}
    for k in by:
        for r in rows(S, k):
            by[k][r["match_id"]].append(r)
    written, idx = set(), MatchIndex(G)
    n = {"matches": 0, "new": 0, "linked": 0, "detailed": 0}

    def team(tid, name):
        t = reg.get("team", "martj42", name) or reg.get("team", "fjelstul", tid) or reg.mint("team", "fjelstul", tid)
        if t not in written:
            written.add(t)
            G.put("team", {"tid": t, "name": name, "kind": "national"}, "fjelstul")
        return t

    for m in matches:
        n["matches"] += 1
        h, a = team(m["home_team_id"], m["home_team_name"]), team(m["away_team_id"], m["away_team_name"])
        hs, as_ = _i(m["home_team_score"]), _i(m["away_team_score"])
        year = m["tournament_id"][3:7]
        mid = twin(G, idx, m["match_date"], h, a, hs, as_, "fjelstul")
        if mid:
            mid = reg.link("match", "fjelstul", m["match_id"], mid) or mid
            n["linked"] += 1
            G.xref("match", mid, "fjelstul", m["match_id"], "date+teams")
        else:
            mid = reg.mint("match", "fjelstul", m["match_id"])
            idx.add(mid, m["match_date"], h, a)
            n["new"] += 1
            G.xref("match", mid, "fjelstul", m["match_id"], "fjelstul-native")
        sid = reg.get("stadium", "fjelstul", m["stadium_id"]) or reg.mint("stadium", "fjelstul", m["stadium_id"])
        G.put("stadium", {"sid": sid, "name": m["stadium_name"], "city": m["city_name"], "country": m["country_name"]}, "fjelstul")
        pens = m.get("penalty_shootout") == "1"
        G.put("match", {"mid": mid, "eid": edition_for(G, reg, "fjelstul", f"{WORLD_CUP}|{year}", cid, year), "round": m["stage_name"],
                        "date": m["match_date"], "home": h, "away": a, "hs": hs, "as_": as_, "et": _i(m.get("extra_time")),
                        "pen_h": _i(m["home_team_score_penalties"]) if pens else None, "pen_a": _i(m["away_team_score_penalties"]) if pens else None,
                        "status": "finished", "sid": sid}, "fjelstul")
        for r in by["referee_appearances"].get(m["match_id"], [])[:1]:
            rid = reg.get("referee", "fjelstul", r["referee_id"]) or reg.mint("referee", "fjelstul", r["referee_id"])
            G.put("referee", {"rid": rid, "name": f"{r['given_name']} {r['family_name']}".strip(), "country": r.get("country_name")}, "fjelstul")
            G.put("match", {"mid": mid, "rid": rid}, "fjelstul")
        for r in by["manager_appearances"].get(m["match_id"], []):
            kid = reg.get("coach", "fjelstul", r["manager_id"]) or reg.mint("coach", "fjelstul", r["manager_id"])
            G.put("coach", {"kid": kid, "name": f"{r['given_name']} {r['family_name']}".strip(), "nationality": r.get("country_name")}, "fjelstul")
            G.c.execute("INSERT OR IGNORE INTO match_coach VALUES(?,?,?,?)", (mid, "h" if r["home_team"] == "1" else "a", kid, "fjelstul"))
        if G.c.execute("SELECT 1 FROM appearance WHERE mid=? LIMIT 1", (mid,)).fetchone():
            continue                                                  # FotMob's detail stands
        side_t = {"h": h, "a": a}

        def side(r):
            return "h" if r.get("home_team") == "1" else "a"

        goals, yel, red, events = defaultdict(int), defaultdict(int), defaultdict(int), []
        for r in by["goals"].get(m["match_id"], []):
            pid = person(r["player_id"], r["given_name"], r["family_name"])
            own = r["own_goal"] == "1"
            if not own:
                goals[pid] += 1
            tp = "own_goal" if own else "penalty_goal" if r["penalty"] == "1" else "goal"
            events.append((_i(r["minute_regulation"]), _i(r["minute_stoppage"]) or 0, tp, side(r), pid, None))
        for r in by["bookings"].get(m["match_id"], []):
            pid = person(r["player_id"], r["given_name"], r["family_name"])
            tp = "second_yellow" if r["second_yellow_card"] == "1" else "red" if r["red_card"] == "1" else "yellow"
            (yel if tp == "yellow" else red)[pid] += 1
            events.append((_i(r["minute_regulation"]), _i(r["minute_stoppage"]) or 0, tp, side(r), pid, None))
        offs = defaultdict(list)
        for r in by["substitutions"].get(m["match_id"], []):
            if r["going_off"] == "1":
                offs[(r["team_id"], r["minute_regulation"])].append(person(r["player_id"], r["given_name"], r["family_name"]))
        for r in by["substitutions"].get(m["match_id"], []):
            if r["coming_on"] == "1":
                off = offs[(r["team_id"], r["minute_regulation"])]
                events.append((_i(r["minute_regulation"]), _i(r["minute_stoppage"]) or 0, "sub", side(r),
                               person(r["player_id"], r["given_name"], r["family_name"]), off.pop(0) if off else None))
        apps = []
        for r in by["player_appearances"].get(m["match_id"], []):
            pid = person(r["player_id"], r["given_name"], r["family_name"])
            apps.append({"mid": mid, "pid": pid, "tid": side_t[side(r)], "played": 1, "started": 1 if r["starter"] == "1" else 0,
                         "shirt": r.get("shirt_number") or None, "goals": goals[pid], "yellow": yel[pid], "red": red[pid]})
        G.many("appearance", apps, "fjelstul")
        events.sort(key=lambda e: (e[0] if e[0] is not None else 999, e[1]))
        G.many("event", [{"mid": mid, "seq": i, "minute": e[0], "added": e[1], "type": e[2], "side": e[3], "tid": side_t[e[3]], "pid": e[4], "pid2": e[5]}
                         for i, e in enumerate(events)], "fjelstul")
        n["detailed"] += 1
    return n
