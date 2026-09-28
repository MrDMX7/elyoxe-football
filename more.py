"""Analytics steps for items 237-287 (insights from the ledger and history, player cursors, Arab extras).
Every step is budget-checked by the caller (poller.Poller.analytics_chores). Outputs: docs/SCHEMA.md."""
import json, os, urllib.parse, urllib.request
from datetime import date, timedelta

import analytics as AN
import config
from compute import history as HI, insights as IN, rating as R, tournament as TO, winprob as WP
from sources import schema as S
from sources.http import FetchError
from timeutil import iso, parse_utc, uae_date

HERE = os.path.dirname(os.path.abspath(__file__))
ERRORS = (Exception,)
ARAB_LEAGUES = (538, 536, 535, 529, 524, 519, 530, 516, 544, 10721)
CUPS = (9943, 11027, 11026, 9942, 9941, 10314, 11840, 11018, 525, 9469, 9470, 10622, 526, 9468, 10474, 42, 73, 10216)
CONTINENTAL_GROUPS = (525, 9469, 9470, 526, 9468, 10474)


def leagues():
    return AN.analytics_leagues()


def ledgers(p, comps):
    return {c: p.ledger(c)["matches"] for c in comps}


# ------------------------------------------------------------------ per-league insights
def comp_insights(p, cid):
    L = p.ledger(cid)["matches"]
    now = iso(p.now())
    base = {"comp": cid, "season": p.ledger(cid).get("season"), "generated": now, "matches_counted": len(L)}
    if L:
        # what the source gives this competition: some Arab leagues have results only (no lineups, no substitutions)
        lu = sum(1 for e in L.values() if e.get("players"))
        cov = {"matches": len(L), "with_lineups": lu, "with_subs": sum(1 for e in L.values() if e.get("subs"))}
        gt = IN.goal_types(L)
        gt_ok = bool((gt["coverage"].get("coverage_pct") or 0) > 0)
        p.store.put_json(f"comp/{cid}/first-goal.json", {**base, "teams": IN.first_goal(L)}, cache="static")
        p.store.put_json(f"comp/{cid}/dropped.json", {**base, "teams": IN.dropped(L)}, cache="static")
        p.store.put_json(f"comp/{cid}/red-impact.json", {**base, "teams": IN.red_impact(L),
                                                         "note": "state after the first red card; pts_after_red = final points "
                                                                 "minus the points the score gave at the red card"}, cache="static")
        p.store.put_json(f"comp/{cid}/goal-types.json", {**base, **gt, "available": gt_ok,
                                                         **({} if gt_ok else {"reason": "FotMob gives this competition neither a shot map "
                                                                              "nor a goal description (body part), only penalties"}),
                                                         "note": "body part/situation from the shot map (xG coverage) or FotMob's goal "
                                                                 "description; coverage says how many goals have a type"}, cache="static")
        p.store.put_json(f"comp/{cid}/dependence.json", {**base, "teams": IN.dependence(L)}, cache="static")
        p.store.put_json(f"comp/{cid}/subs.json", {**base, **IN.subs(L), "available": cov["with_subs"] > 0, "source_coverage": cov,
                                                   **({} if cov["with_subs"] else {"reason": "FotMob lists no substitutions for "
                                                                                   "this competition's matches"})}, cache="static")
        p.store.put_json(f"comp/{cid}/xi.json", {**base, "teams": IN.xi(L)}, cache="static")
        cc = p.cc_of(cid)
        if cc and cc != "INT":
            lm_ = IN.local_minutes(L, cc)
            p.store.put_json(f"comp/{cid}/local-minutes.json", {**base, "country_code": cc, **lm_,
                                                               "available": lu > 0, "source_coverage": cov,
                                                               **({} if lu else {"reason": "FotMob publishes no lineups for this "
                                                                                 "competition's matches"}),
                                                               "note": "minutes by players whose FotMob nationality is the league's "
                                                                       "country vs everyone else (unknown = no nationality in lineup)"},
                             cache="static")
    st = p.store.get_json(f"comp/{cid}/standings.json")
    fx = p.fixtures(cid)
    comp = config.competition(cid) or {}
    if st and fx and len(st.get("groups") or []) == 1:
        rows = st["groups"][0]["rows"]
        preds = {int(k): v for k, v in (p.aux(AN.rating_source(cid)).get("preds") or {}).items()}
        p.store.put_json(f"comp/{cid}/games-in-hand.json", {"comp": cid, "generated": now,
                                                           **IN.games_in_hand(rows, fx, p.now(), preds),
                                                           "note": "overdue = kickoff passed but not played; projected adds each "
                                                                   "overdue game's expected points from the Tifo rating (1.35 if unrated)"},
                         cache="static")
        stats = p.store.get_json(f"comp/{cid}/stats.json") or {}
        played = {r["team"]["id"]: r["played"] or 0 for r in rows}
        mpt = comp.get("matches_per_team")
        if mpt and stats.get("lists"):
            p.store.put_json(f"comp/{cid}/projections.json", {"comp": cid, "generated": now,
                                                             "goals": IN.projections(stats["lists"].get("goals"), played, mpt),
                                                             "assists": IN.projections(stats["lists"].get("assists"), played, mpt),
                                                             "method": "current per-match rate x the team's remaining league games"},
                             cache="static")
    # season tables and metrics since 2010/11
    hist = AN.all_history(p, comps=(cid,)).get(str(cid), {})
    if hist and comp.get("kind") == "league":
        seasons = IN.season_tables({s: HI.finished(rs) for s, rs in hist.items() if HI.finished(rs)})
        sq = p.aux("league_squads").get(str(cid)) or {}
        ages = [a for v in sq.values() for a in v.get("ages", [])]
        cur = max(seasons) if seasons else None
        if cur and ages:
            n = sum(v.get("n", 0) for v in sq.values())
            seasons[cur]["avg_age"] = round(sum(ages) / len(ages), 1)
            seasons[cur]["foreign_squad_pct"] = round(100 * sum(v.get("foreign", 0) for v in sq.values()) / n, 1) if n else None
        if cur and L and p.cc_of(cid) not in (None, "INT"):
            # share of league MINUTES by non-nationals (lineups), what the site's label says; headcount is foreign_squad_pct
            lg_ = IN.local_minutes(L, p.cc_of(cid))["league"]
            tot_ = lg_["national"] + lg_["foreign"]
            seasons[cur]["foreign_share_pct"] = round(100 * lg_["foreign"] / tot_, 1) if tot_ else None
        p.store.put_json(f"comp/{cid}/seasons.json", {"comp": cid, "generated": now, "seasons": seasons,
                                                     "note": "tables computed from FotMob results (points, goal difference, goals for); "
                                                             "the official order can differ on tie-breaks, deductions or play-offs; "
                                                             "age and foreign share only for the current season (FotMob squads)"},
                         cache="static")
    p.mark("insights", cid)


# ------------------------------------------------------------------ players: form, workload, teammates, U21, signings
def players_step(p):
    comps = set(leagues()) | set(CUPS)
    L = ledgers(p, comps)
    apps = IN.appearances(L)
    now = p.now()
    p.aux("player_forms").clear()
    p.aux("player_forms").update({pid: IN.form(v) for pid, v in apps.items()})
    for cid in leagues():
        st = p.store.get_json(f"comp/{cid}/standings.json")
        if not st:
            continue
        team_ids = {r["team"]["id"] for g in st["groups"] for r in g["rows"]}
        wl = IN.workload(apps, team_ids, now)
        p.store.put_json(f"comp/{cid}/workload.json", {"comp": cid, "generated": iso(now),
                                                       "players": wl, "available": bool(wl),
                                                       **({} if wl else {"reason": "no stored lineups with minutes for this league "
                                                                         "(FotMob publishes none for it)"}),
                                                       "thresholds": {"minutes_30d": IN.WORKLOAD_30D, "minutes_last5": IN.WORKLOAD_LAST5,
                                                                      "last5_within_days": 18},
                                                       "note": "all covered competitions count; overload = >= 540 min in 30 days, "
                                                               "or >= 450 min in the last 5 matches played within 18 days"},
                         cache="static")
    tm = IN.teammates(L)
    cur = p.aux("cursor").get("teammates", 0)
    keys = sorted(tm)
    n = 0
    while keys and n < min(len(keys), 3000) and p.has_time(120):     # the whole list in a few runs; leave time for later steps
        pid = keys[cur % len(keys)]
        p.store.put_json(f"player/{pid}/teammates.json", {"player": int(pid), "generated": iso(now), "teammates": tm[pid],
                                                          "fields": ["player", "matches_together"],
                                                          "note": "matches in stored lineups (this season's ledgers)"}, cache="static")
        cur += 1
        n += 1
    p.aux("cursor")["teammates"] = cur
    u21(p)
    signings(p)
    p.mark("players_step")


def _dobs(p):
    d = dict(p.aux("dobs"))
    for groups in p.aux("squads").values():
        for g in groups or []:
            for pl in g.get("players") or []:
                if pl.get("dob"):
                    d[str(pl["id"])] = pl["dob"]
    return d


def u21(p, max_age=21, min_minutes=450):
    dobs = _dobs(p)
    if not dobs or not any(p.aux("ptables").get(str(c)) for c in ARAB_LEAGUES):
        return False                  # dates of birth (squads, Wikidata) or player tables not loaded yet
    today = date.fromisoformat(iso(p.now())[:10])
    rows = []
    for cid in ARAB_LEAGUES:
        t = p.aux("ptables").get(str(cid))
        if not t:
            continue
        for pid, pl in t["players"].items():
            dob = dobs.get(pid)
            if not dob or pl["minutes"] < min_minutes:
                continue
            y, m, d = map(int, dob[:10].split("-"))
            age = today.year - y - ((today.month, today.day) < (m, d))
            if age > max_age:
                continue
            s = pl["stats"]
            ga90 = sum(((s.get(k) or {}).get("per90") or 0) for k in ("goals", "goal_assist"))
            rows.append({"player": int(pid), "name": pl["name"], "team": pl["team"], "comp": cid, "age": age, "dob": dob,
                         "minutes": pl["minutes"], "rating": (s.get("rating") or {}).get("value"), "ga_per90": round(ga90, 2)})
    rows.sort(key=lambda r: (-(r["rating"] or 0), -r["ga_per90"]))
    p.store.put_json("arabs/u21.json", {"generated": iso(p.now()), "max_age": max_age, "min_minutes": min_minutes,
                                        "players": rows[:100], "dob_known": len(dobs),
                                        "note": "players in the Arab leagues aged <= 21 today with >= 450 league minutes, by FotMob "
                                                "season rating then (goals + assists) per 90; age from FotMob/Wikidata date of birth"},
                     cache="static")


def signings(p):
    for cid in leagues():
        tr = p.store.get_json(f"comp/{cid}/transfers.json") or {}
        t = (p.aux("ptables").get(str(cid)) or {}).get("players") or {}
        season_start = (p.st.get("comp_meta", {}).get(str(cid)) or {}).get("season", "")[:4]
        rows = []
        for tid, v in (tr.get("teams") or {}).items():
            for x in v.get("in") or []:
                if season_start and (x.get("date") or "")[:4] < season_start:
                    continue
                pl = t.get(str(x["player"]["id"]))
                if not pl or pl["team"] != int(tid):
                    continue
                s = pl["stats"]
                rating = (s.get("rating") or {}).get("value")
                rows.append({"player": x["player"], "team": int(tid), "from": x.get("from"), "date": x.get("date"), "fee": x.get("fee"),
                             "loan": x.get("loan"), "minutes": pl["minutes"], "rating": rating,
                             "goals": (s.get("goals") or {}).get("value") or 0, "assists": (s.get("goal_assist") or {}).get("value") or 0,
                             "score": round((rating or 6.0) * min(1.0, pl["minutes"] / 900), 2)})
        rows.sort(key=lambda r: -r["score"])
        if rows:
            p.store.put_json(f"comp/{cid}/signings.json", {"comp": cid, "generated": iso(p.now()), "signings": rows,
                                                           "method": "this season's incoming transfers (league transfer feed), ranked by "
                                                                     "FotMob season rating x min(1, minutes / 900) at the new club"},
                             cache="static")


# ------------------------------------------------------------------ team history, upsets
def team_histories(p, limit=150):
    comps = AN.history_comps()
    hist = AN.all_history(p, comps=comps)
    rows = HI.finished(HI.all_rows(hist))
    seen, uniq = set(), []
    for r in rows:
        if r["id"] not in seen:
            seen.add(r["id"])
            uniq.append(r)
    teams = sorted({int(k) for k, v in p.st.get("team_comps", {}).items() if set(v) & set(leagues())})
    cur = p.aux("cursor").get("team_history", 0)
    n = 0
    while teams and n < limit and p.has_time(8):
        tid = teams[cur % len(teams)]
        h = IN.team_history(uniq, tid, None)
        if h:
            p.store.put_json(f"team/{tid}/history.json", {"team": tid, "generated": iso(p.now()), "since": h[0][0],
                                                         "fields": ["date", "comp", "opponent", "gf", "ga", "result", "venue", "match"],
                                                         "matches": h}, cache="static")
        cur += 1
        n += 1
    p.aux("cursor")["team_history"] = cur


def upsets(p, preds):
    by = {}
    for x in preds:
        by.setdefault(x.get("comp"), []).append(x)
    for cid, xs in by.items():
        if cid not in leagues() and cid not in CUPS:
            continue
        u = IN.upsets(xs)
        if u:
            p.store.put_json(f"comp/{cid}/upsets.json", {"comp": cid, "generated": iso(p.now()), "threshold": 0.20, "seasons": u,
                                                         "note": "winner's pre-match win probability (Tifo rating, predicted before the "
                                                                 "match) below 20%"}, cache="static")


# ------------------------------------------------------------------ cups: bracket sim, ties, AFC/CAF scenarios
def cups(p):
    rat = {int(k): v for k, v in (p.aux("arab_ratings").get("ratings") or {}).items()}
    uae = {int(k): v for k, v in (p.aux("ratings").get("ratings") or {}).items()}
    params = {**R.DEFAULTS, **(config.settings().get("arab_rating") or {})}
    for cid in CUPS:
        if not p.has_time(10):
            return
        st = p.store.get_json(f"comp/{cid}/standings.json") or {}
        fx = p.fixtures(cid) or []
        bracket = st.get("bracket")
        if not bracket:
            bracket = _bracket_only(p, cid)
        if not bracket:
            fb = _fixture_cup(p, cid, fx, ratings={**rat, **uae}, params=params, st=st)
            if fb:
                p.store.put_json(f"comp/{cid}/bracket-sim.json", fb, cache="static")
            continue
        by_id = {m["id"]: m for m in fx if m.get("id")}
        ties_ = IN.ties(bracket, by_id)
        ratings = {**rat, **uae}
        groups = [{"letter": TO._grp_letter(g.get("name")), "rows": g["rows"]} for g in (st.get("groups") or [])]
        rem = []
        for g in groups:
            tids = {r["team"]["id"] for r in g["rows"]}
            rem += [(m["home"]["id"], m["away"]["id"]) for m in fx if m["status"] == S.SCHEDULED
                    and m["home"]["id"] in tids and m["away"]["id"] in tids]
        fin = sum(1 for m in fx if m["status"] == S.FINISHED)
        res = TO.simulate(groups, rem, bracket, ratings, params, n=5000, seed=AN._seed(cid, st.get("season"), fin))
        p.store.put_json(f"comp/{cid}/bracket-sim.json", {"comp": cid, "season": st.get("season"), "generated": iso(p.now()),
                                                          "rated_teams": sum(1 for t in res["teams"] if int(t) in ratings),
                                                          **res, "ties": ties_,
                                                          "note": "two-legged ties: aggregate and what each side needs; Monte Carlo with "
                                                                  "the Tifo club rating (unrated clubs at 1400)"}, cache="static")


def _bracket_only(p, cid):
    try:
        raw = p.fm.league_raw(cid)
        st = p.fm.standings_from_raw(cid, None, {**raw, "table": raw.get("table") or []}) if raw.get("table") else None
        if st and st.get("bracket"):
            return st["bracket"]
        po = raw.get("playoff")
        if po and po.get("rounds"):
            fake = p.fm.standings_from_raw(cid, None, {"table": [{"data": {"table": {"all": [{"id": 1, "name": "x", "idx": 1, "pts": 0},
                                                                                               {"id": 2, "name": "y", "idx": 2, "pts": 0}]}}}],
                                                                 "playoff": po})
            return fake["bracket"]
    except ERRORS as e:
        p.store.fail(f"bracket:{cid}", e)
    return None


# ------------------------------------------------------------------ national squads and call-ups (244)
def callups(p):
    clubs = {}
    for c in config.countries():
        if not c.get("arab"):
            continue
        tid = c["fotmob_team"]
        page = p.aux("national_squads").get(str(tid))
        if (page is None or p.due("natsquad", 1440, tid)) and p.has_time(6):
            try:
                t = p.fm.team(tid)
                page = t["squad"]
                p.aux("national_squads")[str(tid)] = page
            except ERRORS as e:
                p.store.fail("callups", e)
            p.mark("natsquad", tid)
        if not page:
            continue
        players = [{**{k: pl.get(k) for k in ("id", "name", "position", "club", "club_id", "age", "dob")}, "group": g["group"]}
                   for g in page for pl in g["players"]]
        p.store.put_json(f"national/{tid}/squad.json", {"team": tid, "country": {"iso2": c["iso2"], "name_ar": c["name_ar"]},
                                                        "generated": iso(p.now()), "players": players,
                                                        "note": "FotMob's current national-team squad (the latest announced call-up)"},
                         cache="static")
        for pl in players:
            if pl.get("club_id"):
                clubs.setdefault(pl["club_id"], []).append({"player": pl["id"], "name": pl["name"], "team": tid,
                                                            "iso2": c["iso2"], "name_ar": c["name_ar"]})
                if pl.get("dob"):
                    p.aux("dobs")[str(pl["id"])] = pl["dob"]
    for club, xs in clubs.items():
        p.store.put_json(f"callups/{club}.json", {"club": club, "generated": iso(p.now()), "callups": xs}, cache="static")


# ------------------------------------------------------------------ careers + milestones (241, 274)
def careers(p, limit=25):
    """playerData for the players who matter most (league top-30 scorers and appearances, Arab players abroad),
    weekly per player."""
    want = []
    for cid in leagues():
        stats = p.store.get_json(f"comp/{cid}/stats.json") or {}
        for k in ("goals", "assists"):
            want += [(cid, e["player"]["id"]) for e in ((stats.get("lists") or {}).get(k) or [])[:30]]
    ab = p.store.get_json("arabs/abroad.json") or {}
    want += [(None, x["id"]) for x in ab.get("players", [])]
    for cid in leagues():          # every regular (>= 900 league minutes) for the league-transition study (336)
        for pid, r in ((p.aux("ptables").get(str(cid)) or {}).get("players") or {}).items():
            if r["minutes"] >= 900:
                want.append((cid, int(pid)))
    cache = p.aux("careers")
    n, skipped = 0, []
    for cid, pid in want:
        if n >= limit or not p.has_time(6):
            break
        if not p.due("career", 7 * 1440, pid) and str(pid) in cache:
            continue
        try:
            raw = p.fm.http.get_json(f"https://www.fotmob.com/api/data/playerData?id={int(pid)}", min_ttl=3600)
            car = IN.career(raw)
            info = {"id": pid, "name": raw.get("name"), "comp": cid, "birth_date": ((raw.get("birthDate") or {}).get("utcTime") or "")[:10] or None}
            cache[str(pid)] = {"info": info, "career": car}
            if info["birth_date"]:
                p.aux("dobs")[str(pid)] = info["birth_date"]
            p.store.put_json(f"player/{pid}/career.json", {"player": pid, "name": info["name"], "generated": iso(p.now()),
                                                           **car, "note": "FotMob career history; club city/country: see teams.json "
                                                                          "(country) for covered clubs"}, cache="static")
            n += 1
        except FetchError as e:
            p.store.fail("careers", f"{pid}: {e}")      # the source failed: health says so
            n += 1
        except ERRORS as e:                             # one unreadable payload: skip this player, keep the step green
            skipped.append(pid)
            p.note(f"careers: skipped {pid} ({type(e).__name__}: {e})")
            n += 1
        p.mark("career", pid)
    if n and not skipped and (p.store.health.get("careers") or {}).get("ok", True):
        p.store.ok("careers")           # clears an old failure once a run fetched careers without one
    if skipped and (p.store.health.get("careers") or {}).get("ok", True):
        p.store.ok("careers", note=f"skipped {len(skipped)} player(s) with unreadable career data: "
                                  + ", ".join(map(str, skipped[:10])))
    for cid in leagues():
        items = []
        for pid, v in cache.items():
            if v["info"].get("comp") == cid:
                items += IN.milestones(v["info"], v["career"])
        if items:
            p.store.put_json(f"comp/{cid}/milestones.json", {"comp": cid, "generated": iso(p.now()),
                                                             "items": sorted(items, key=lambda x: x["needs"]),
                                                             "note": "career apps/goals per club and national team from FotMob "
                                                                     "careerHistory; milestones 50/100/150/200/250/300; only players within "
                                                                     "5 goals or 10 apps of the next one"}, cache="static")


# ------------------------------------------------------------------ birthdays (242)
def birthdays(p):
    dobs = _dobs(p)
    names = {}
    path = os.path.join(HERE, "names", "players_ar.json")
    try:
        with open(path, encoding="utf-8") as f:
            names = json.load(f)
    except OSError:
        pass
    wd = p.aux("wikidata_dob")
    todo = [v["qid"] for pid, v in names.items() if v.get("qid") and v["qid"] not in wd][:200]
    if todo and p.has_time(20):
        q = "SELECT ?p ?dob WHERE { VALUES ?p { %s } ?p wdt:P569 ?dob }" % " ".join(f"wd:{x}" for x in todo)
        try:
            url = "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q)
            r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "elyoxe-tifo/0.1 (hello@elyoxe.com)"}),
                                                  timeout=40).read())
            got = {b["p"]["value"].rsplit("/", 1)[-1]: b["dob"]["value"][:10] for b in r["results"]["bindings"]}
            for x in todo:
                wd[x] = got.get(x)
        except ERRORS as e:
            p.store.fail("wikidata-dob", e)
    for pid, v in names.items():
        if v.get("qid") and wd.get(v["qid"]) and pid not in dobs:
            dobs[pid] = wd[v["qid"]]
    days = {}
    teams = {}
    for groups in p.aux("squads").values():
        for g in groups or []:
            for pl in g.get("players") or []:
                teams[str(pl["id"])] = pl.get("name")
    for pid, dob in dobs.items():
        if not dob or len(dob) < 10:
            continue
        days.setdefault(dob[5:10], []).append({"player": int(pid), "name": teams.get(pid) or (names.get(pid) or {}).get("latin"),
                                               "name_ar": (names.get(pid) or {}).get("ar"), "dob": dob,
                                               "source": "wikidata" if (names.get(pid) or {}).get("qid") and wd.get(names[pid]["qid"]) == dob else "fotmob"})
    d0 = date(2024, 1, 1)                   # a leap year: all 366 days, empty ones as an empty list (no 404)
    for i in range(366):
        md = (d0 + timedelta(days=i)).strftime("%m-%d")
        p.store.put_json(f"players/birthdays/{md}.json", {"date": md, "players": sorted(days.get(md) or [], key=lambda x: x["dob"])},
                         cache="static")
    p.mark("birthdays")


# ------------------------------------------------------------------ transfers feed (263)
def transfers_feed(p):
    now = p.now()
    items = []
    for cid in ARAB_LEAGUES:
        tr = p.store.get_json(f"comp/{cid}/transfers.json") or {}
        for tid, v in (tr.get("teams") or {}).items():
            for x in v.get("in") or []:
                d = parse_utc(x.get("date"))
                if d and now - d <= timedelta(days=60):
                    items.append({**x, "comp": cid, "country": (config.competition(cid) or {}).get("country")})
    seen, out = set(), []
    for x in sorted(items, key=lambda x: x.get("date") or "", reverse=True):
        k = (x["player"]["id"], x.get("date"))
        if k not in seen:
            seen.add(k)
            out.append(x)
    p.store.put_json("transfers/latest.json", {"generated": iso(now), "days": 60, "transfers": out,
                                               "note": "incoming moves at clubs in the Arab leagues (FotMob league transfer feeds, "
                                                       "the latest ~100 per league)"}, cache="warm")


ROUND_ORDER = ["1/64", "1/32", "1/16", "1/8", "1/4", "1/2", "final"]


def _round_key(r):
    r = str(r or "").lower().replace("round of 16", "1/8").replace("quarter-finals", "1/4").replace("semi-finals", "1/2")
    return r


def _fixture_cup(p, cid, fx, ratings, params, st, n=5000):
    """Knockout cup without a FotMob bracket: rounds from the fixtures' round labels; the current round's
    known ties are simulated, later rounds are a random redraw of the survivors (as cup draws are)."""
    import random
    rounds = {}
    for m in fx:
        k = _round_key(m.get("round"))
        if k in ROUND_ORDER and m.get("id"):
            rounds.setdefault(k, []).append(m)
    if not rounds:
        return None
    order = [k for k in ROUND_ORDER if k in rounds]
    cur = next((k for k in order if any(m["status"] != S.FINISHED for m in rounds[k])), None)
    by_id = {m["id"]: m for m in fx if m.get("id")}
    ties_ = []
    for k in order:
        pairs = {}
        for m in rounds[k]:
            pairs.setdefault(frozenset((m["home"]["id"], m["away"]["id"])), []).append(m["id"])
        ties_ += IN.ties([{"stage": k, "ties": [{"matches": v} for v in pairs.values()]}], by_id)
    out = {"comp": cid, "season": (st or {}).get("season"), "generated": iso(p.now()), "rounds": order, "current_round": cur,
           "ties": ties_, "source": "fixtures"}
    if not cur:
        out["note"] = "cup finished (latest season on FotMob); no simulation"
        return out
    base = params.get("newcomer", 1400)
    known = [m for m in rounds[cur]]
    alive_now = {m["home"]["id"] for m in known} | {m["away"]["id"] for m in known}
    later = ROUND_ORDER[ROUND_ORDER.index(cur) + 1:]
    reach = {t: dict.fromkeys(later + ["winner"], 0) for t in alive_now}
    rng = random.Random(AN._seed(cid, cur, sum(1 for m in fx if m["status"] == S.FINISHED)))

    def play(h, a, neutral):
        ph, pd, pa = R.probs(ratings.get(h, base), ratings.get(a, base), params, neutral)
        return h if rng.random() < ph + pd / 2 else a
    for _ in range(n):
        surv = []
        for m in known:
            if m["status"] == S.FINISHED and m.get("score"):
                sc = m["score"]
                pen = m.get("penalties")
                if sc["home"] != sc["away"]:
                    surv.append(m["home"]["id"] if sc["home"] > sc["away"] else m["away"]["id"])
                elif pen:
                    surv.append(m["home"]["id"] if pen["home"] > pen["away"] else m["away"]["id"])
                else:
                    surv.append(rng.choice([m["home"]["id"], m["away"]["id"]]))
            else:
                surv.append(play(m["home"]["id"], m["away"]["id"], R.is_neutral(m)))
        for k in later:
            for t in surv:
                reach[t][k] += 1
            rng.shuffle(surv)
            surv = [play(surv[i], surv[i + 1], k == "final") for i in range(0, len(surv) - 1, 2)] + (surv[-1:] if len(surv) % 2 else [])
        if len(surv) == 1:
            reach[surv[0]]["winner"] += 1
    out["teams"] = {str(t): {f"reach_{k}": round(v / n, 4) for k, v in r.items()} for t, r in reach.items()}
    out["sims"] = n
    out["method"] = ("current round from FotMob fixtures, later rounds a random redraw of the survivors each simulation; "
                     "Tifo club rating; knockout draws settled 50/50")
    return out



def transitions(p):
    covered = set(leagues()) | {42}
    res = IN.transitions(p.aux("careers"), covered)
    names = {c["id"]: c["name_ar"] for c in p.comps}
    summary = sorted(({"pair": k, "from": int(k.split("->")[0]), "to": int(k.split("->")[1]),
                       "from_ar": names.get(int(k.split("->")[0])), "to_ar": names.get(int(k.split("->")[1])),
                       **{kk: v[kk] for kk in ("n", "median_rating_change", "median_ga_per_app_change")}}
                      for k, v in res.items()), key=lambda x: -x["n"])
    if not summary:
        return False                  # careers still filling in (30 per run): not ready, retried soon
    p.store.put_json("arabs/transitions.json", {"generated": iso(p.now()), "pairs": summary, "detail": res,
                                                "players_with_careers": len(p.aux("careers")),
                                                "method": "FotMob career rows per player, league and season (apps, goals, assists, FotMob "
                                                          "season rating); a transition = consecutive seasons with >= 8 league apps in two "
                                                          "different covered leagues since 2016; change = after - before; per appearance, "
                                                          "not per 90 (career rows carry no minutes)",
                                                "limits": "selection bias (only players still good enough to be a regular in a covered league "
                                                          "now, whose careers we fetched); small n for most pairs; ratings are league-relative, "
                                                          "so a drop after moving up can mean a harder league, not a worse player"},
                     cache="static")
