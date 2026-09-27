"""Arab fans hub (analytics function): Arab players abroad (207), star of the week (208), Arab derbies
(209), Arab-vs-Arab continental clashes (210), Arab national teams (211). Outputs under arabs/ and
h2h/, listed in docs/SCHEMA.md.

Nationality: FotMob 3-letter country codes on lineups and squads, mapped to the 22 Arab League members
in countries.yaml. "Abroad" = a non-Arab competition we cover (big five, UCL/UEL/UECL).
"""
from datetime import timedelta

import config
from compute import history as HI
from sources import schema as S
from timeutil import iso, parse_utc, uae_date

ABROAD_COMPS = (47, 87, 55, 54, 53, 42, 73, 10216)
CONTINENTAL = (525, 10622, 9469, 9470, 526, 9468, 10474)
QUALIFYING = (10608, 10197, 10609, 11156, 290, 289, 329, 10242)
ERRORS = (Exception,)


def arab_codes():
    return {c["fotmob_code"]: {"iso2": c["iso2"], "name_ar": c["name_ar"]} for c in config.countries() if c.get("arab")}


# ------------------------------------------------------------------ 207 / 208
def appearances(p):
    """Every stored appearance of an Arab national in an abroad competition this season."""
    codes = arab_codes()
    out = []
    for cid in ABROAD_COMPS:
        for e in p.ledger(cid)["matches"].values():
            goals, assists = {}, {}
            for g in e.get("goals") or []:
                if g.get("player") and g["type"] != "own_goal":
                    goals[str(g["player"])] = goals.get(str(g["player"]), 0) + 1
                if g.get("assist"):
                    assists[str(g["assist"])] = assists.get(str(g["assist"]), 0) + 1
            for pid, pl in (e.get("players") or {}).items():
                cc = codes.get(pl[1])
                if not cc:
                    continue
                mins = pl[7] if len(pl) > 7 else None
                if mins == 0:
                    continue
                out.append({"player": int(pid), "name": pl[0], "nationality": cc, "team": pl[2], "comp": cid,
                            "match": e["id"], "kickoff_utc": e.get("ko"), "minutes": mins, "rating": pl[3],
                            "goals": goals.get(pid, 0), "assists": assists.get(pid, 0), "starter": pl[6] if len(pl) > 6 else None})
    return out


def abroad(p):
    apps = appearances(p)
    names = p.names["teams"]
    tabs = p.aux("ptables")
    per = {}
    for a in apps:
        r = per.setdefault(a["player"], {"id": a["player"], "name": a["name"], "nationality": a["nationality"], "team": a["team"],
                                         "team_ar": names.get(str(a["team"])), "comps": set(), "apps": 0, "minutes": 0,
                                         "goals": 0, "assists": 0, "_r": []})
        r["comps"].add(a["comp"])
        r["apps"] += 1
        r["minutes"] += a["minutes"] or 0
        r["goals"] += a["goals"]
        r["assists"] += a["assists"]
        if a["rating"]:
            r["_r"].append(a["rating"])
        r["team"], r["team_ar"] = a["team"], names.get(str(a["team"]))
    rows = []
    for r in per.values():
        rr = r.pop("_r")
        r["avg_rating"] = round(sum(rr) / len(rr), 2) if rr else None
        r["comps"] = sorted(r["comps"])
        league = next((c for c in r["comps"] if c in (47, 87, 55, 54, 53)), None)
        pt = ((tabs.get(str(league)) or {}).get("players") or {}).get(str(r["id"])) if league else None
        r["league"] = league
        r["league_season_stats"] = ({k: (pt["stats"].get(k) or {}).get("value") for k in ("rating", "goals", "goal_assist", "mins_played")}
                                    if pt else None)
        rows.append(r)
    rows.sort(key=lambda r: (-(r["goals"] + r["assists"]), -(r["avg_rating"] or 0)))
    now = p.now()
    p.store.put_json("arabs/abroad.json", {"generated": iso(now), "players": rows, "count": len(rows),
                                           "competitions": list(ABROAD_COMPS),
                                           "note": "Arab nationals (22 Arab League countries, FotMob nationality code) who played "
                                                   "in the big five or the UEFA club competitions this season, from stored lineups"},
                     cache="static")
    days = {}
    for a in apps:
        if a["kickoff_utc"]:
            days.setdefault(uae_date(parse_utc(a["kickoff_utc"])), []).append(a)
    for d, xs in days.items():
        if (now - parse_utc(f"{d[:4]}-{d[4:6]}-{d[6:]}T12:00:00Z")).days <= 10:
            p.store.put_json(f"arabs/day/{d}.json", {"date": d, "tz": "Asia/Dubai", "generated": iso(now),
                                                     "appearances": sorted(xs, key=lambda x: -(x["rating"] or 0))}, cache="static")
    week_start = now - timedelta(days=7)
    recent = [a for a in apps if a["kickoff_utc"] and parse_utc(a["kickoff_utc"]) >= week_start]
    score = {}
    for a in recent:
        s_ = score.setdefault(a["player"], {"player": a["player"], "name": a["name"], "nationality": a["nationality"],
                                            "team": a["team"], "team_ar": names.get(str(a["team"])), "matches": [],
                                            "goals": 0, "assists": 0, "minutes": 0, "_r": []})
        s_["matches"].append(a["match"])
        s_["goals"] += a["goals"]
        s_["assists"] += a["assists"]
        s_["minutes"] += a["minutes"] or 0
        if a["rating"]:
            s_["_r"].append(a["rating"])
    top = []
    for s_ in score.values():
        rr = s_.pop("_r")
        s_["avg_rating"] = round(sum(rr) / len(rr), 2) if rr else None
        s_["score"] = round((s_["avg_rating"] or 6.0) + 1.0 * s_["goals"] + 0.7 * s_["assists"], 2)
        top.append(s_)
    top.sort(key=lambda s_: -s_["score"])
    y, w, _ = now.isocalendar()
    p.store.put_json(f"arabs/week/{y}-{w:02d}.json", {"week": f"{y}-W{w:02d}", "from": iso(week_start), "to": iso(now),
                                                      "generated": iso(now), "star": top[0] if top else None, "top5": top[:5],
                                                      "method": "score = average FotMob match rating + 1 x goals + 0.7 x assists, last 7 days"},
                     cache="static")
    p.store.put_json("arabs/week/latest.json", {"week": f"{y}-W{w:02d}", "path": f"arabs/week/{y}-{w:02d}.json"}, cache="warm")
    p.mark("arabs_abroad")


# ------------------------------------------------------------------ 209
def derbies(p, limit=4):
    out = []
    for d in config.arab_derbies():
        a, b = sorted(d["teams"])
        entry = {"teams": [a, b], "name_ar": d["name_ar"], "city_ar": d.get("city_ar"), "country": d.get("country"),
                 "comp": d.get("comp"), "h2h": f"h2h/{a}-{b}.json"}
        out.append(entry)
        if limit <= 0 or not p.has_time(6) or not p.due("arab_derby", 7 * 1440, f"{a}-{b}"):
            continue
        mid = _last_meeting(p, a, b, d.get("comp"))
        if not mid:
            entry["h2h"] = None
            entry["missing"] = "no stored meeting to read the head-to-head from (club not in a covered league)"
            p.mark("arab_derby", f"{a}-{b}")
            continue
        try:
            m = p.fm.match(mid)
            limit -= 1
        except ERRORS as e:
            p.store.fail("arab-derbies", e)
            continue
        h = m.get("h2h")
        p.mark("arab_derby", f"{a}-{b}")
        if not h:
            continue
        wins = {str(a): 0, str(b): 0, "draws": 0}
        for x in h["matches"]:
            sc = x.get("score")
            if not sc:
                continue
            if sc["home"] == sc["away"]:
                wins["draws"] += 1
            else:
                wnr = x["home"]["id"] if sc["home"] > sc["away"] else x["away"]["id"]
                if str(wnr) in wins:
                    wins[str(wnr)] += 1
        p.store.put_json(f"h2h/{a}-{b}.json", {"teams": [a, b], "name_ar": d["name_ar"], "generated": iso(p.now()),
                                              "wins": wins, "matches": h["matches"], "via_match": mid,
                                              "note": "all meetings FotMob lists for this pair (its depth, all competitions)"},
                         cache="static")
    p.store.put_json("derbies.json", {"generated": iso(p.now()), "derbies": out}, cache="static")


def _last_meeting(p, a, b, comp):
    best = None
    comps = [comp] if comp else []
    comps += [c for c in (525, 9469, 526, 9468, 10474) if c not in comps]
    for cid in comps:
        for rows in p.aux(f"history/{cid}").values():
            for r in rows:
                if {r["h"], r["a"]} == {a, b} and r.get("id") and (best is None or (r["ko"] or "") > best[0]):
                    best = (r["ko"] or "", r["id"])
        for m in p.fixtures(cid) or []:
            if {m["home"]["id"], m["away"]["id"]} == {a, b} and m.get("id") and (best is None or (m.get("kickoff_utc") or "") > best[0]):
                best = (m.get("kickoff_utc") or "", m["id"])
    return best[1] if best else None


# ------------------------------------------------------------------ 210
def club_country(p, tid):
    arab = {c["iso2"] for c in config.countries() if c.get("arab")}
    c = p.team_country(tid)
    if c:
        return c, c["iso2"] in arab
    tc = p.aux("team_country")
    if str(tid) in tc:
        v = tc[str(tid)]
        return v, bool(v and v.get("iso2") in arab)
    return None, None


def resolve_countries(p, ids, limit=10):
    """FotMob team page country for clubs outside the covered leagues (Jordan, Oman, Syria ...)."""
    by_code = {c["fotmob_code"]: {"iso2": c["iso2"], "name_ar": c["name_ar"]} for c in config.countries() if c.get("fotmob_code")}
    tc = p.aux("team_country")
    n = 0
    for tid in ids:
        if n >= limit or not p.has_time(5):
            break
        if p.team_country(tid) or str(tid) in tc:
            continue
        try:
            det = p.fm.team_raw(tid).get("details") or {}
            code = det.get("country")
            tc[str(tid)] = by_code.get(code) or ({"iso2": None, "fotmob_code": code} if code else None)
            n += 1
        except ERRORS as e:
            p.store.fail("team-country", e)
            n += 1


def clashes(p):
    now = p.now()
    matches = []
    for cid in CONTINENTAL:
        matches += [m for m in p.fixtures(cid) or [] if m.get("kickoff_utc")
                    and abs((parse_utc(m["kickoff_utc"]) - now).days) <= 45]
    resolve_countries(p, {m[s]["id"] for m in matches for s in ("home", "away") if m[s]["id"]})
    out = []
    for m in matches:
        ch, ah = club_country(p, m["home"]["id"])
        ca, aa = club_country(p, m["away"]["id"])
        if ah and aa:
            out.append({**{k: m.get(k) for k in ("id", "comp", "comp_name_ar", "round", "stage", "kickoff_utc", "kickoff_uae",
                                                  "status", "score", "home", "away", "probs")},
                        "home_country": ch, "away_country": ca, "same_country": ch["iso2"] == ca["iso2"]})
    out.sort(key=lambda m: m["kickoff_utc"])
    p.store.put_json("arabs/clashes.json", {"generated": iso(now), "matches": out, "window_days": 45,
                                            "competitions": list(CONTINENTAL),
                                            "note": "AFC, CAF and Arab club competitions, both clubs from Arab League countries; "
                                                    "±45 days around today"}, cache="warm")


# ------------------------------------------------------------------ 211
def national_hub(p, limit=6):
    ne = p.aux("national_elo").get("ratings") or {}
    ranked = sorted(ne.values(), reverse=True)
    teams = []
    for c in config.countries():
        if not c.get("arab"):
            continue
        tid = c["fotmob_team"]
        page = p.aux("national_pages").get(str(tid))
        if (page is None or p.due("natpage", 1440, tid)) and limit > 0 and p.has_time(6):
            try:
                t = p.fm.team(tid)
                page = {"fifa": t.get("fifa_ranking"), "fixtures": [{k: m.get(k) for k in ("id", "comp", "comp_name", "kickoff_utc",
                                                                                          "status", "score", "home", "away")}
                                                                     for m in t["fixtures"]]}
                p.aux("national_pages")[str(tid)] = page
                limit -= 1
            except ERRORS as e:
                p.store.fail("national-hub", e)
            p.mark("natpage", tid)
        page = page or {}
        fx = page.get("fixtures") or []
        now = p.now()
        nxt = min((m for m in fx if m["status"] == S.SCHEDULED and parse_utc(m.get("kickoff_utc")) and parse_utc(m["kickoff_utc"]) > now),
                  key=lambda m: m["kickoff_utc"], default=None)
        last = max((m for m in fx if m["status"] == S.FINISHED and m.get("kickoff_utc")), key=lambda m: m["kickoff_utc"], default=None)
        groups = []
        for cid in QUALIFYING:
            st = p.store.get_json(f"comp/{cid}/standings.json") if p.has_time(3) else None
            for g in (st or {}).get("groups") or []:
                row = next((r for r in g["rows"] if r["team"]["id"] == tid), None)
                if row:
                    groups.append({"comp": cid, "season": st.get("season"), "group": g.get("name"), "rank": row["rank"],
                                   "played": row["played"], "pts": row["pts"], "of": len(g["rows"])})
        elo = ne.get(c.get("martj42"))
        teams.append({"team": tid, "iso2": c["iso2"], "name_ar": c["name_ar"], "name_en": c["name_en"],
                      "fifa": page.get("fifa"), "tifo_rating": round(elo, 1) if elo else None,
                      "tifo_world_rank": 1 + sum(1 for r in ranked if elo and r > elo) if elo else None,
                      "next_match": nxt, "last_result": last, "groups": groups,
                      "archive": f"national/{tid}/archive.json"})
    teams.sort(key=lambda t: -(t["tifo_rating"] or 0))
    for i, t in enumerate(teams, 1):
        t["arab_rank"] = i
    p.store.put_json("arabs/national.json", {"generated": iso(p.now()), "teams": teams,
                                             "note": "FIFA rank from FotMob (the national team's page); Tifo rating = national Elo "
                                                     "(ratings/national.json); groups = current tables of covered qualifying competitions"},
                     cache="static")
