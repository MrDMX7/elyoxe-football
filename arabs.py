"""Arab fans hub (analytics function): Arab players abroad (207), star of the week (208), Arab derbies
(209), Arab-vs-Arab continental clashes (210), Arab national teams (211). Outputs under arabs/ and
h2h/, listed in docs/SCHEMA.md.

Nationality: FotMob 3-letter country codes on lineups and squads, mapped to the 22 Arab League members
in countries.yaml. "Abroad" = a non-Arab competition we cover (big five, UCL/UEL/UECL).
"""
from datetime import date as _date, timedelta

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
    out, stored = [], None
    pairs = {tuple(sorted(d["teams"])) for d in config.arab_derbies()}
    for d in config.arab_derbies():
        a, b = sorted(d["teams"])
        entry = {"teams": [a, b], "name_ar": d["name_ar"], "city_ar": d.get("city_ar"), "country": d.get("country"),
                 "comp": d.get("comp"), "h2h": f"h2h/{a}-{b}.json"}
        out.append(entry)
        v2 = p.an_state.setdefault("derby_v2", {})
        if f"{a}-{b}" not in v2 or v2[f"{a}-{b}"] == "ok":   # "ok": written from FotMob's list alone: rebuild once, merged
            p.dues().pop(f"arab_derby:{a}-{b}", None)
        if limit <= 0 or not p.has_time(6) or not p.due("arab_derby", 7 * 1440, f"{a}-{b}"):
            continue
        mid = _last_meeting(p, a, b, d.get("comp"))
        if not mid:
            entry["h2h"] = None
            entry["missing"] = "no stored meeting to read the head-to-head from (club not in a covered league)"
            p.mark("arab_derby", f"{a}-{b}")
            v2[f"{a}-{b}"] = "no-meeting"
            continue
        try:
            m = p.fm.match(mid)
            limit -= 1
        except ERRORS as e:
            p.store.fail("arab-derbies", e)
            continue
        if stored is None:          # every meeting we hold ourselves, read once per run for all the derbies
            stored = stored_meetings(p.store, p.fixtures, [c["id"] for c in p.comps], pairs)
        h = m.get("h2h") or {}
        mine = stored.get((a, b)) or {}
        if not h.get("matches") and not mine:
            p.store.fail("arab-derbies", f"{a}-{b}: FotMob match {mid} has no head-to-head block yet")
            p.dues()[f"arab_derby:{a}-{b}"] = iso(p.now() - timedelta(days=6))     # again in a day, not a week
            v2.setdefault(f"{a}-{b}", "no-h2h")
            continue
        if h.get("matches"):
            p.mark("arab_derby", f"{a}-{b}")
        else:                       # FotMob lists nothing yet: our own meetings now, its list again in a day
            p.dues()[f"arab_derby:{a}-{b}"] = iso(p.now() - timedelta(days=6))
        v2[f"{a}-{b}"] = "merged"
        matches = list(h.get("matches") or [])
        if m.get("status") == "finished" and m.get("score") and all(x.get("id") != m["id"] for x in matches):
            # FotMob's head-to-head block lists the meetings before the match it hangs on: add that match itself
            matches.insert(0, {"id": m["id"], "kickoff_utc": m.get("kickoff_utc"), "comp": m.get("comp"),
                               "home": {k: m["home"].get(k) for k in ("id", "name", "name_ar", "logo")},
                               "away": {k: m["away"].get(k) for k in ("id", "name", "name_ar", "logo")}, "score": m["score"]})
        # FotMob's list is short (the Kuwait derby: 6 meetings since 2024 against 43 league meetings we store): every
        # meeting in our archive and this season's fixtures joins it, one per match id
        matches = merge_meetings(matches, mine, {t["id"]: t for t in (m.get("home"), m.get("away")) if t and t.get("id")},
                                 p.names.get("teams") or {})
        matches, upcoming = split_h2h(matches)
        wins = {str(a): 0, str(b): 0, "draws": 0}
        for x in matches:
            sc = x.get("score")
            if not sc:
                continue
            if sc["home"] == sc["away"]:
                wins["draws"] += 1
            else:
                wnr = x["home"]["id"] if sc["home"] > sc["away"] else x["away"]["id"]
                if str(wnr) in wins:
                    wins[str(wnr)] += 1
        listed = {x.get("id") for x in (h.get("matches") or [])} | {m.get("id")}
        p.store.put_json(f"h2h/{a}-{b}.json", {"teams": [a, b], "name_ar": d["name_ar"], "generated": iso(p.now()),
                                              "wins": wins, "matches": matches, "upcoming": upcoming, "via_match": mid,
                                              "since": min((x.get("kickoff_utc") or "")[:10] for x in matches) if matches else None,
                                              "from_fotmob_list": sum(1 for x in matches if x.get("id") in listed),
                                              "from_tifo_archive": sum(1 for x in matches if x.get("id") not in listed),
                                              "check": _h2h_check(p, a, b, d.get("comp"), matches),
                                              "sources": [f"https://www.fotmob.com/match/{mid}",
                                                          f"https://www.fotmob.com/api/data/matchDetails?matchId={mid}",
                                                          "Tifo archive (archive/all/<season>.json) and this season's fixtures"],
                                              "note": "every meeting FotMob lists for this pair (its depth, all competitions) plus every "
                                                      "meeting in Tifo's archive (covered competitions since 2010/11) and this season's "
                                                      "fixtures, one per match id; date_only = the archive keeps the day, not the time"},
                         cache="static")
    v2 = p.an_state.get("derby_v2", {})
    for e in out:               # derbies.json never points at a file that does not exist
        st = v2.get("-".join(map(str, e["teams"])))
        if st in ("no-meeting", "no-h2h") and e.get("h2h"):
            e["h2h"] = None
            e["missing"] = ("no stored meeting to read the head-to-head from (club not in a covered league)" if st == "no-meeting"
                            else "FotMob has no head-to-head for this pair yet (retried daily)")
    p.store.put_json("derbies.json", {"generated": iso(p.now()), "derbies": out}, cache="static")


def split_h2h(matches):
    """-> (played with a score, newest first; upcoming meetings, soonest first). FotMob's block can carry the next
    fixture too: it is not a result."""
    played = sorted([x for x in matches if x.get("score")], key=lambda x: x.get("kickoff_utc") or "", reverse=True)
    upcoming = sorted([{**x, "status": "scheduled"} for x in matches if not x.get("score")], key=lambda x: x.get("kickoff_utc") or "")
    return played, upcoming


def stored_meetings(store, fixtures, comp_ids, pairs, seasons=None):
    """{(a, b): {match id: meeting}} for the given pairs (a < b): every finished game between the two in our archive
    (archive/all/<season>.json: every covered competition since 2010/11, the League Cup and the other cups included)
    and in the current fixtures of comp_ids (fixtures(cid) -> normalized matches), in the h2h row shape. A fixture row
    replaces the archive's (it has the kickoff time; the archive keeps the day only: date_only)."""
    pairs = {tuple(sorted(x)) for x in pairs}
    out = {k: {} for k in pairs}
    if seasons is None:
        seasons = [s["season"] for s in ((store.get_json("archive/index-all.json") or {}).get("seasons") or [])
                   if s.get("season") and s["season"] != "unknown"]
    for s in seasons:
        for r in (store.get_json(f"archive/all/{s}.json") or {}).get("matches") or []:
            k = (min(r[3], r[4]), max(r[3], r[4])) if r[3] and r[4] else None
            if k in out and r[5] is not None and r[6] is not None:
                out[k][r[0]] = {"id": r[0], "kickoff_utc": f"{r[1][:10]}T00:00:00Z", "date_only": True, "comp": r[2],
                                "home": {"id": r[3]}, "away": {"id": r[4]}, "score": {"home": r[5], "away": r[6]}}
    for cid in comp_ids:
        for m in fixtures(cid) or []:
            if not (m.get("id") and m.get("status") == S.FINISHED and m.get("score") and m.get("home") and m.get("away")):
                continue
            k = tuple(sorted((m["home"].get("id"), m["away"].get("id"))))
            if k in out:
                out[k][m["id"]] = {"id": m["id"], "kickoff_utc": m.get("kickoff_utc"), "comp": m.get("comp"),
                                   "home": {f: m["home"].get(f) for f in ("id", "name", "name_ar", "logo")},
                                   "away": {f: m["away"].get(f) for f in ("id", "name", "name_ar", "logo")},
                                   "score": {"home": m["score"]["home"], "away": m["score"]["away"]}}
    return out


def merge_meetings(listed, stored, teams=None, names_ar=None):
    """FotMob's head-to-head list plus every stored meeting it lacks, one per match id: a stored fixture row (fresh)
    beats FotMob's row, FotMob's row beats an archive row (date only). Two meetings of the pair within a day with the
    same result are one game under two ids: the date-only copy goes. Archive rows get the teams' name/logo from the
    other rows (the pair is always the same two clubs), else the Arabic name and FotMob's logo."""
    teams, names_ar = dict(teams or {}), names_ar or {}
    stored = list(stored.values()) if isinstance(stored, dict) else list(stored or [])
    by_id = {}
    for x in [s for s in stored if s.get("date_only")] + list(listed) + [s for s in stored if not s.get("date_only")]:
        if x.get("id") is not None:
            by_id[x["id"]] = x
        for side in ("home", "away"):
            t = x.get(side) or {}
            if t.get("id") and t.get("name"):
                teams.setdefault(t["id"], t)
    rows = [x for x in listed if x.get("id") is None] + list(by_id.values())
    keep, seen = [], {}
    for x in sorted(rows, key=lambda x: (bool(x.get("date_only")), x.get("kickoff_utc") or "")):
        sc = x.get("score")
        if sc and x.get("kickoff_utc"):
            try:
                day = _date.fromisoformat(x["kickoff_utc"][:10]).toordinal()
            except ValueError:
                day = None
            key = ((x.get("home") or {}).get("id"), (x.get("away") or {}).get("id"), sc.get("home"), sc.get("away"))
            if day is not None and x.get("date_only") and any(k == key and abs(d - day) <= 1 for d, k in seen.get(key[:2], [])):
                continue            # the same game under another id
            if day is not None:
                seen.setdefault(key[:2], []).append((day, key))
        if x.get("date_only"):
            x = dict(x)
            for side in ("home", "away"):
                tid = (x.get(side) or {}).get("id")
                t = teams.get(tid) or {"id": tid, "name": None, "name_ar": names_ar.get(str(tid)), "logo": S.LOGO.format(id=tid)}
                x[side] = {f: t.get(f) for f in ("id", "name", "name_ar", "logo")}
        keep.append(x)
    return keep


def _h2h_check(p, a, b, comp, matches):
    """Cross-check against the league meetings in our own stored history (the same source, other endpoint)."""
    if not comp:
        return None
    by_id = {x.get("id"): x for x in matches}
    stored, missing, differ = 0, [], []
    for rows in p.aux(f"history/{comp}").values():
        for r in rows:
            if {r["h"], r["a"]} != {a, b} or r.get("hs") is None:
                continue
            stored += 1
            x = by_id.get(r["id"])
            if not x:
                missing.append(r["id"])
            elif x.get("score") and [x["score"]["home"], x["score"]["away"]] != ([r["hs"], r["as"]] if x["home"]["id"] == r["h"]
                                                                                 else [r["as"], r["hs"]]):
                differ.append(r["id"])
    return {"stored_league_meetings": stored, "missing_from_list": missing, "score_differs": differ,
            "note": "league meetings in our FotMob season history (competition " + str(comp) + ") compared with this list"}


def _last_meeting(p, a, b, comp):
    best, upcoming = None, None
    comps = [comp] if comp else []
    comps += [c for c in (525, 9469, 526, 9468, 10474) if c not in comps]
    for cid in comps:
        for rows in p.aux(f"history/{cid}").values():
            for r in rows:
                if {r["h"], r["a"]} == {a, b} and r.get("id") and (best is None or (r["ko"] or "") > best[0]):
                    best = (r["ko"] or "", r["id"])
        for m in p.fixtures(cid) or []:
            if {m["home"]["id"], m["away"]["id"]} == {a, b} and m.get("id") and m.get("status") == "finished" and \
                    (best is None or (m.get("kickoff_utc") or "") > best[0]):
                best = (m.get("kickoff_utc") or "", m["id"])
            elif {m["home"]["id"], m["away"]["id"]} == {a, b} and m.get("id") and not upcoming:
                upcoming = m["id"]      # a scheduled meeting only if none was played (FotMob may give it no h2h yet)
    return best[1] if best else upcoming


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
        nxt, last = _fresh(p, nxt), _fresh(p, last)
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


def _fresh(p, m):
    """A match from a (daily) team-page snapshot, overlaid with our tracked fixture when we have one: the page had
    Tunisia v Botswana with the sides swapped after FotMob corrected it (QA #20/#41)."""
    if not m or m.get("comp") not in p.comp_ids:
        return m
    f = next((x for x in p.fixtures(m["comp"]) or [] if x.get("id") == m.get("id")), None)
    return {**m, **{k: f.get(k) for k in ("kickoff_utc", "status", "score", "home", "away")}} if f else m


# ------------------------------------------------------------------ 279 tonight
def tonight(p):
    """Next 48 h of abroad-competition matches with Arab-nationality players in either club's squad,
    plus performance once played (from the stored lineups)."""
    codes = arab_codes()
    roster = p.aux("arab_rosters")          # team id -> [{id, name, nationality}], from squads + lineups
    for tid, groups in p.aux("squads").items():
        rs = [{"id": pl["id"], "name": pl["name"], "nationality": codes[pl["country"]]} for g in groups or []
              for pl in g.get("players") or [] if pl.get("country") in codes]
        if rs:
            roster[tid] = rs
    for a in appearances(p):
        lst = roster.setdefault(str(a["team"]), [])
        if all(x["id"] != a["player"] for x in lst):
            lst.append({"id": a["player"], "name": a["name"], "nationality": a["nationality"]})
    now = p.now()
    apps = {}
    for a in appearances(p):
        apps.setdefault(a["match"], []).append(a)
    out = []
    for cid in ABROAD_COMPS:
        for m in p.fixtures(cid) or []:
            ko = parse_utc(m.get("kickoff_utc"))
            if not ko or not (now - timedelta(hours=30) <= ko <= now + timedelta(hours=48)):
                continue
            ps = [dict(x, team=int(side_id)) for side_id in (str(m["home"]["id"]), str(m["away"]["id"])) for x in roster.get(side_id, [])]
            if not ps:
                continue
            out.append({"match": m["id"], "comp": cid, "comp_name_ar": m.get("comp_name_ar"), "kickoff_utc": m["kickoff_utc"],
                        "kickoff_uae": m.get("kickoff_uae"), "status": m["status"], "score": m.get("score"),
                        "home": m["home"], "away": m["away"], "players": ps, "performance": apps.get(m["id"])})
    out.sort(key=lambda x: x["kickoff_utc"])
    p.store.put_json("arabs/tonight.json", {"generated": iso(now), "matches": out,
                                            "note": "abroad competitions, 30 h back to 48 h ahead; players = Arab nationals on either "
                                                    "club's squad (FotMob squads we hold + every stored lineup); performance appears "
                                                    "after the match's final detail is stored"}, cache="warm")


# ------------------------------------------------------------------ 280 coefficients
def coefficients(p):
    import json, os
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "coefficients.json"), encoding="utf-8") as f:
            doc = json.load(f)
    except OSError:
        return
    p.store.put_json("arabs/coefficients.json", {"generated": iso(p.now()), **doc}, cache="static")


# ------------------------------------------------------------------ 282 calendars
ARAB_LEAGUES = (538, 536, 535, 529, 524, 519, 530, 516, 544, 10721)


def calendars(p):
    out = {}
    fifa_windows = []
    for cid in ARAB_LEAGUES:
        fx = [m for m in p.fixtures(cid) or [] if m.get("kickoff_utc")]
        if not fx:
            continue
        ds = sorted({m["kickoff_utc"][:10] for m in fx})
        gaps = []
        from datetime import date as D
        for a, b in zip(ds, ds[1:]):
            da, db = D.fromisoformat(a), D.fromisoformat(b)
            if (db - da).days >= 12:
                gaps.append({"from": a, "to": b, "days": (db - da).days})
        out[str(cid)] = {"name_ar": (config.competition(cid) or {}).get("name_ar"), "country": (config.competition(cid) or {}).get("country"),
                         "first_match": ds[0], "last_published_match": ds[-1], "matches_published": len(fx),
                         "breaks": gaps}
    for cid in (10608, 10197, 10609, 329, 290, 114):
        for m in p.fixtures(cid) or []:
            if m.get("kickoff_utc"):
                fifa_windows.append(m["kickoff_utc"][:10])
    cutoff = (p.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    fifa_windows = sorted(d for d in set(fifa_windows) if d >= cutoff)
    windows, cur = [], None
    from datetime import date as D
    for d in fifa_windows:
        if cur and (D.fromisoformat(d) - D.fromisoformat(cur["to"])).days <= 3:
            cur["to"] = d
        else:
            if cur:
                windows.append(cur)
            cur = {"from": d, "to": d}
    if cur:
        windows.append(cur)
    p.store.put_json("arabs/calendars.json", {"generated": iso(p.now()), "leagues": out, "national_team_windows": windows,
                                              "note": "breaks = gaps of 12+ days between published match dates; last_published_match "
                                                      "is not the season end where the league publishes a few rounds at a time; "
                                                      "national-team windows = dates of covered national-team matches"}, cache="static")


# ------------------------------------------------------------------ 284 archive index
def archive_index(p):
    by_season = {}
    for cid in set(config.settings().get("history_comps", [])):
        for season, rows in p.aux(f"history/{cid}").items():
            for r in HI.finished(rows):
                y = int(r["ko"][:4]) - (1 if int(r["ko"][5:7]) < 7 else 0) if r.get("ko") else None
                key = f"{y}-{y + 1}" if y else "unknown"
                by_season.setdefault(key, []).append([r["id"], (r["ko"] or "")[:10], r["comp"], r["h"], r["a"], r["hs"], r["as"]])
    for cid in [c["id"] for c in p.comps]:
        for m in p.fixtures(cid) or []:
            if m["status"] == S.FINISHED and m.get("id") and m.get("score") and m.get("kickoff_utc"):
                ko = m["kickoff_utc"]
                y = int(ko[:4]) - (1 if int(ko[5:7]) < 7 else 0)
                lst = by_season.setdefault(f"{y}-{y + 1}", [])
                lst.append([m["id"], ko[:10], m["comp"], m["home"]["id"], m["away"]["id"], m["score"]["home"], m["score"]["away"]])
    # our own permanent archive (owner 2026-09-30 item 14): merge into what is stored instead of rebuilding, so a
    # competition's past season survives after its fixtures file moves on to the next one (MLS, the Arab cups, …)
    for season in list(by_season) + [s["season"] for s in ((p.store.get_json("archive/index-all.json") or {}).get("seasons") or [])]:
        old = p.store.get_json(f"archive/all/{season}.json") or {}
        by_season.setdefault(season, []).extend(old.get("matches") or [])
    index = []
    for season, rows in sorted(by_season.items()):
        seen, uniq = set(), []
        for r in sorted(rows, key=lambda r: r[1]):
            if r[0] not in seen:
                seen.add(r[0])
                uniq.append(r)
        p.store.put_json(f"archive/all/{season}.json", {"season": season, "fields": ["id", "date", "comp", "home", "away", "hs", "as"],
                                                        "matches": uniq}, cache="static")
        index.append({"season": season, "matches": len(uniq), "file": f"archive/all/{season}.json"})
    p.store.put_json("archive/index-all.json", {"generated": iso(p.now()), "seasons": index,
                                                "note": "every stored match result (history competitions since 2010/11 + current fixtures), "
                                                        "split by July-June season; team names in teams.json"}, cache="static")


# ------------------------------------------------------------------ 287 streaks
def streaks(p):
    names = p.names["teams"]
    out = {k: [] for k in ("unbeaten", "winning", "clean_sheets", "winless", "losing")}
    tests = {"unbeaten": lambda f, a: f >= a, "winning": lambda f, a: f > a, "clean_sheets": lambda f, a: a == 0,
             "winless": lambda f, a: f <= a, "losing": lambda f, a: f < a}
    for cid in ARAB_LEAGUES:
        fx = [m for m in p.fixtures(cid) or [] if m["status"] == S.FINISHED and m.get("score") and m.get("id")]
        hist = [r for rs in p.aux(f"history/{cid}").values() for r in HI.finished(rs)]
        rows = {r["id"]: (r["ko"] or "", r["h"], r["a"], r["hs"], r["as"]) for r in hist}
        for m in fx:
            rows[m["id"]] = (m["kickoff_utc"] or "", m["home"]["id"], m["away"]["id"], m["score"]["home"], m["score"]["away"])
        games = sorted(rows.items(), key=lambda kv: kv[1][0])
        teams = {x for _, r in games for x in (r[1], r[2])}
        current = {m["home"]["id"] for m in fx} | {m["away"]["id"] for m in fx}
        for t in teams & current:
            seq = [(mid, r[3], r[4]) if r[1] == t else (mid, r[4], r[3]) for mid, r in games if t in (r[1], r[2])]
            for k, test in tests.items():
                n = 0
                for mid, f, a in reversed(seq):
                    if test(f, a):
                        n += 1
                    else:
                        break
                if n >= 3:
                    out[k].append({"team": t, "team_ar": names.get(str(t)), "comp": cid,
                                   "country": (config.competition(cid) or {}).get("country"), "length": n,
                                   "since_match": seq[-n][0], "last_match": seq[-1][0]})
    for k in out:
        out[k].sort(key=lambda x: -x["length"])
    p.store.put_json("arabs/streaks.json", {"generated": iso(p.now()), "streaks": out,
                                            "note": "league games only (domestic league of each club), running now, length >= 3, "
                                                    "counted across seasons from FotMob history"}, cache="warm")


# ------------------------------------------------------------------ 281 TV guide
def guide(p):
    import json, os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "broadcast_by_country.json")
    try:
        with open(path, encoding="utf-8") as f:
            bc = json.load(f)
    except OSError:
        return
    now = p.now()
    fx = {}
    for key in {k for c, v in bc.items() if c != "_meta" for k in (v.get("competitions") or {})}:
        if key.isdigit():
            fx[key] = [m for m in p.fixtures(int(key)) or [] if m.get("kickoff_utc")
                       and now - timedelta(hours=2) <= parse_utc(m["kickoff_utc"]) <= now + timedelta(days=3)]
    for iso2, v in bc.items():
        if iso2 == "_meta":
            continue
        items = []
        for key, info in (v.get("competitions") or {}).items():
            for m in fx.get(key, []):
                items.append({"match": m["id"], "comp": int(key), "comp_name_ar": m.get("comp_name_ar"), "kickoff_utc": m["kickoff_utc"],
                              "kickoff_uae": m.get("kickoff_uae"), "home": m["home"], "away": m["away"], "status": m["status"],
                              "broadcasters": info.get("broadcasters") or [], "confidence": info.get("confidence"),
                              "note": info.get("note"), "channel_known": bool(info.get("broadcasters"))})
        # W1.2c: this country's own teams (national team, its clubs) in a competition the research has no row for
        # still get listed, with the channel marked unknown instead of the match silently missing
        have = {it["match"] for it in items}
        for m in _own_matches(p, iso2, now):
            if m["id"] in have:
                continue
            items.append({"match": m["id"], "comp": m["comp"], "comp_name_ar": m.get("comp_name_ar"), "kickoff_utc": m["kickoff_utc"],
                          "kickoff_uae": m.get("kickoff_uae"), "home": m["home"], "away": m["away"], "status": m["status"],
                          "broadcasters": [], "confidence": None, "note": None, "channel_known": False,
                          "channel_ar": "القناة: ما تأكدنا"})
        items.sort(key=lambda x: x["kickoff_utc"])
        by_bc = {}
        for it in items:
            for b in it["broadcasters"]:
                by_bc.setdefault(b.get("name_en") or b.get("name_ar") or "?", []).append(it["match"])
        p.store.put_json(f"guide/{iso2}.json", {"country": iso2, "country_ar": v.get("country_ar"), "generated": iso(now),
                                                "days": 3, "matches": items, "by_broadcaster": by_bc,
                                                "source": "research/tifo-2026-09-27/broadcast_by_country.json (checked "
                                                          + str((bc.get("_meta") or {}).get("checked")) + ") x FotMob fixtures"},
                         cache="warm")


_OWN_CACHE = {}


def _own_matches(p, iso2, now):
    """Next 3 days (and the last 2 h) of tracked matches where a team from this country plays (its national team,
    or a club whose domestic league is in this country)."""
    key = iso(now)[:16]
    if _OWN_CACHE.get("at") != key:
        ms = []
        for c in p.comps:
            for m in p.fixtures(c["id"]) or []:
                ko = parse_utc(m.get("kickoff_utc"))
                if m.get("id") and ko and now - timedelta(hours=2) <= ko <= now + timedelta(days=3):
                    ms.append(m)
        _OWN_CACHE.update({"at": key, "matches": ms, "cc": {}})
    cc = _OWN_CACHE["cc"]

    def country(tid):
        if tid not in cc:
            cc[tid] = (p.team_country(tid) or {}).get("iso2") if tid else None
        return cc[tid]
    return [m for m in _OWN_CACHE["matches"] if iso2 in (country(m["home"]["id"]), country(m["away"]["id"]))]


# ------------------------------------------------------------------ 295 national team folders
def national_teams(p, limit=6):
    """national/{id}/team.json (squad, fixtures/results, coach, venue, FIFA rank) and national/{id}/fifa.json
    for the 22 Arab national teams; the UAE keeps its own richer files too."""
    import json as _j, os as _o
    try:
        with open(_o.path.join(_o.path.dirname(_o.path.abspath(__file__)), "fifa_history.json"), encoding="utf-8") as f:
            fh = _j.load(f).get("arab_teams") or {}
    except OSError:
        fh = {}
    n = 0
    for c in config.countries():
        if not c.get("arab"):
            continue
        tid = c["fotmob_team"]
        if n < limit and p.has_time(6) and p.due("natteam", 720, tid):
            try:
                t = p.fm.team(tid)
                p.note_time_tbd(t.get("fixtures"))
                t["fixtures"] = p.settle_fixtures(t.get("fixtures") or [])
                doc = {**t, "country_info": {"iso2": c["iso2"], "name_ar": c["name_ar"], "national": True}, "generated": iso(p.now())}
                p.store.put_json(f"national/{tid}/team.json", doc, cache="static")
                if tid != 5789:         # the UAE's team/5789.json is the poller's richer file; the other 21 get the same path
                    p.store.put_json(f"team/{tid}.json", doc, cache="static")   # (squad, friendlies included) for team pages
                p.aux("national_coaches")[str(tid)] = t.get("coach")
                fr = t.get("fifa_ranking")
                if fr and fr.get("updated"):
                    p.aux("fifa_arab").setdefault(str(tid), {})[fr["updated"]] = fr
            except ERRORS as e:
                p.store.fail("national-teams", e)
            p.mark("natteam", tid)
            n += 1
        hist = list(fh.get(c["fotmob_code"]) or [])
        known = {r["date"] for r in hist}
        for k, v in sorted((p.aux("fifa_arab").get(str(tid)) or {}).items()):
            d = "-".join(reversed(k.split(".")))
            if d not in known:
                hist.append({"date": d, "rank": v.get("rank"), "points": v.get("points"), "source": "fotmob"})
        if hist:
            p.store.put_json(f"national/{tid}/fifa.json", {"team": tid, "iso2": c["iso2"], "name_ar": c["name_ar"],
                                                           "history": sorted(hist, key=lambda r: r["date"]),
                                                           "source": "FIFA ranking API (inside.fifa.com) + FotMob's current rank"},
                             cache="static")


# ------------------------------------------------------------------ 297 continental history
def continental_history(p):
    arab = {c["iso2"] for c in config.countries() if c.get("arab")}
    if not p.aux("arab_ratings").get("club_country"):
        return False                  # club countries come from the Arab clubs rating run: not ready yet
    cc = dict((p.aux("arab_ratings").get("club_country") or {}))
    for k, v in p.aux("team_country").items():
        if v and v.get("iso2"):
            cc.setdefault(k, v["iso2"])
    names = p.names["teams"]
    rows = []
    for cid in CONTINENTAL:
        for season, rs in p.aux(f"history/{cid}").items():
            for r in HI.finished(rs):
                a, b = cc.get(str(r["h"])), cc.get(str(r["a"]))
                if a in arab and b in arab:
                    rows.append({"match": r["id"], "date": (r["ko"] or "")[:10], "comp": cid, "season": season,
                                 "home": r["h"], "home_ar": names.get(str(r["h"])), "home_country": a,
                                 "away": r["a"], "away_ar": names.get(str(r["a"])), "away_country": b,
                                 "score": [r["hs"], r["as"]], "same_country": a == b})
    rows.sort(key=lambda x: x["date"])
    pairs = {}
    for x in rows:
        k = tuple(sorted((x["home_country"], x["away_country"])))
        s = pairs.setdefault(f"{k[0]}-{k[1]}", {"matches": 0, k[0]: 0, k[1]: 0, "draws": 0}) if k[0] != k[1] else None
        if s is not None:
            s["matches"] += 1
            if x["score"][0] == x["score"][1]:
                s["draws"] += 1
            else:
                s[x["home_country"] if x["score"][0] > x["score"][1] else x["away_country"]] += 1
    p.store.put_json("arabs/continental-history.json", {"generated": iso(p.now()), "matches": rows, "by_country_pair": pairs,
                                                        "competitions": list(CONTINENTAL),
                                                        "note": "every AFC/CAF/Arab club-competition meeting of two clubs from Arab "
                                                                "countries that FotMob has (club country = its domestic league)"},
                     cache="static")


# ------------------------------------------------------------------ 298 coaches, 299 referees
def coaches(p):
    codes = arab_codes()
    names = p.names["teams"]
    out = []
    for tid, c in p.aux("coaches").items():
        co = (c or {}).get("coach") or {}
        if co.get("country") in codes:
            comps = p.st.get("team_comps", {}).get(tid, [])
            out.append({"coach": co.get("id"), "name": co.get("name"), "nationality": codes[co["country"]], "team": int(tid),
                        "team_ar": names.get(tid), "national_team": False, "comps": comps,
                        "team_country": (p.team_country(int(tid)) or {}).get("iso2")})
    for tid, co in p.aux("national_coaches").items():
        if co and co.get("country") in codes:
            out.append({"coach": co.get("id"), "name": co.get("name"), "nationality": codes[co["country"]], "team": int(tid),
                        "team_ar": names.get(tid), "national_team": True})
    out.sort(key=lambda x: (x["national_team"] is False, x["nationality"]["iso2"]))
    p.store.put_json("arabs/coaches.json", {"generated": iso(p.now()), "coaches": out,
                                            "abroad": [x for x in out if not x["national_team"] and x.get("team_country") != x["nationality"]["iso2"]],
                                            "note": "current head coaches (FotMob team pages) of clubs in the analytics leagues and the 22 "
                                                    "Arab national teams whose nationality is an Arab League country"}, cache="static")


INTL = (525, 10622, 9469, 9470, 526, 9468, 10474, 77, 78, 10703, 289, 290, 329, 10197, 10608, 10609, 10242, 11156, 9571)


def referees(p):
    codes = arab_codes()
    per = {}
    for cid in INTL:
        for e in p.ledger(cid)["matches"].values():
            ref = e.get("referee") or {}
            if ref.get("country") in codes:
                r = per.setdefault(str(ref.get("id") or ref.get("name")), {"id": ref.get("id"), "name": ref.get("name"),
                                                                            "nationality": codes[ref["country"]], "matches": []})
                r["matches"].append({"match": e["id"], "comp": cid, "date": (e.get("ko") or "")[:10], "home": e["home"], "away": e["away"]})
    rows = sorted(per.values(), key=lambda r: -len(r["matches"]))
    p.store.put_json("arabs/referees.json", {"generated": iso(p.now()), "referees": rows,
                                             "note": "Arab-nationality referees of stored AFC, CAF and FIFA matches this season "
                                                     "(FotMob lists the referee only for part of the matches)"}, cache="static")


# ------------------------------------------------------------------ 300 friendlies
def friendlies(p):
    arab = {c["iso2"] for c in config.countries() if c.get("arab")}
    out = []
    for tid, fx in p.aux("team_fx").items():
        c = p.team_country(int(tid))
        if not c or c.get("iso2") not in arab:
            continue
        for m in fx:
            if m.get("comp") == 489:
                out.append({**m, "club": int(tid), "club_country": c})
    seen, uniq = set(), []
    for m in sorted(out, key=lambda m: m.get("kickoff_utc") or ""):
        if m["id"] not in seen:
            seen.add(m["id"])
            uniq.append(m)
    p.store.put_json("arabs/friendlies.json", {"generated": iso(p.now()), "matches": uniq,
                                               "note": "FotMob 'Club Friendlies' (489) on the team pages of clubs in the covered Arab "
                                                       "leagues; pre-season camps show as friendly series abroad (venue in match files "
                                                       "when fetched)"}, cache="static")


# ------------------------------------------------------------------ 302 monthly club bundles
def monthly(p, limit=60):
    from compute import insights as IN
    months_r = p.aux("arab_ratings").get("months") or {}
    names = p.names["teams"]
    now = p.now()
    this_m = now.strftime("%Y-%m")
    prev_m = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    n = 0
    for cid in ARAB_LEAGUES:
        fx = p.fixtures(cid) or []
        L = p.ledger(cid)["matches"]
        bump = p.store.get_json(f"comp/{cid}/bump.json") or {}
        round_month = {}
        for m in fx:
            if str(m.get("round") or "").isdigit() and m.get("kickoff_utc"):
                round_month[int(m["round"])] = max(round_month.get(int(m["round"]), ""), m["kickoff_utc"][:7])
        for tid in {m["home"]["id"] for m in fx} | {m["away"]["id"] for m in fx}:
            for month in (prev_m, this_m):
                if n >= limit or not p.has_time(5):
                    return
                res = [m for m in fx if (m.get("kickoff_utc") or "")[:7] == month and tid in (m["home"]["id"], m["away"]["id"])
                       and m["status"] == S.FINISHED]
                if not res:
                    continue
                perf = {}
                for e in L.values():
                    if (e.get("ko") or "")[:7] != month or tid not in (e["home"], e["away"]):
                        continue
                    for pid, pl in (e.get("players") or {}).items():
                        if pl[2] == tid and pl[3]:
                            x = perf.setdefault(pid, {"player": int(pid), "name": pl[0], "ratings": [], "goals": 0, "assists": 0})
                            x["ratings"].append(pl[3])
                    for g in e.get("goals") or []:
                        if g["side"] in ("home", "away") and e[g["side"]] == tid:
                            for k, pid in (("goals", g.get("player")), ("assists", g.get("assist"))):
                                if pid and str(pid) in perf:
                                    perf[str(pid)][k] += 1
                top = sorted(({**{k: x for k, x in v.items() if k != "ratings"}, "matches": len(v["ratings"]),
                               "avg_rating": round(sum(v["ratings"]) / len(v["ratings"]), 2)}
                              for v in perf.values() if v["ratings"]), key=lambda v: -v["avg_rating"])[:5]
                rm = months_r.get(str(tid)) or {}
                before = [v for k, v in sorted(rm.items()) if k < month]
                pos = bump.get("positions", {}).get(str(tid)) or []
                rounds = bump.get("rounds") or []
                start = [pos[i] for i, r in enumerate(rounds) if round_month.get(r, "9999") < month and i < len(pos)]
                end = [pos[i] for i, r in enumerate(rounds) if round_month.get(r, "9999") <= month and i < len(pos)]
                p.store.put_json(f"team/{tid}/month/{month}.json", {
                    "team": tid, "team_ar": names.get(str(tid)), "comp": cid, "month": month, "generated": iso(now),
                    "results": [{"match": m["id"], "date": m["kickoff_utc"][:10], "home": m["home"], "away": m["away"],
                                 "score": m["score"], "comp": m["comp"]} for m in res],
                    "record": {r: sum(1 for m in res if IN._res(*((m["score"]["home"], m["score"]["away"]) if m["home"]["id"] == tid
                                                                   else (m["score"]["away"], m["score"]["home"]))) == r) for r in "WDL"},
                    "top_performers": top,
                    "rating": {"start": before[-1] if before else None, "end": rm.get(month)},
                    "table_position": {"start": start[-1] if start else None, "end": end[-1] if end else None}},
                    cache="static")
                n += 1
