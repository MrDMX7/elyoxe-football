"""Tifo analytics chores, run by the poller in idle minutes (each step checks the time budget).

History (UAE club competitions, every season FotMob has), the Tifo rating and probabilities, the
season simulator, facts, coach pressure, fatigue, coaches, watchability, fortress, player cards and
extras, similarity, league comparison, loans, record chase, national-team Elo + tournament
simulators, FIFA ranking, and the memorable-matches archive. Outputs are listed in docs/SCHEMA.md.
"""
import hashlib, json, os, urllib.request
from datetime import timedelta

import config
from compute import clubs as CL, extras as EX, facts as FA, history as HI, national as NA, players as PL
from compute import rating as R, season as SEASON, sim as SIM, tables as TB, tournament as TO
from sources import schema as S
from timeutil import iso, parse_utc

HERE = os.path.dirname(os.path.abspath(__file__))
LEAGUE = 538
NATIONAL = 5789
ERRORS = (Exception,)


def _load_json(name):
    try:
        with open(os.path.join(HERE, name), encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return None


def _seed(*parts):
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


# ------------------------------------------------------------------ history
def history_step(p, limit=2):
    """Fetch past seasons of the UAE club competitions, `limit` requests per call, each season once."""
    n = 0
    meta = p.aux("history_meta")
    for cid in R.UAE_CLUB_COMPS:
        m = meta.setdefault(str(cid), {"seasons": None, "done": []})
        if m["seasons"] is None:
            if n >= limit or not p.has_time(8):
                return
            try:
                cur, rows, seasons = HI.season_rows(p.fm, cid, None)
                m["seasons"], m["current"] = seasons, cur
                n += 1
            except ERRORS as e:
                p.store.fail(f"history:{cid}", e)
                continue
        for s in m["seasons"]:
            if s == m.get("current") or s in m["done"]:
                continue
            if n >= limit or not p.has_time(8):
                return
            try:
                ss, rows, _ = HI.season_rows(p.fm, cid, s)
                p.aux(f"history/{cid}")[ss] = rows
                m["done"].append(s)
                n += 1
                p.store.ok(f"history:{cid}")
            except ERRORS as e:
                p.store.fail(f"history:{cid}", f"{s}: {e}")
                m["done"].append(s)          # do not retry a broken season every minute
                n += 1


def history_complete(p):
    meta = p.aux("history_meta")
    return all((meta.get(str(c)) or {}).get("seasons") is not None and
               set((meta[str(c)]["seasons"])) - {meta[str(c)].get("current")} <= set(meta[str(c)]["done"])
               for c in R.UAE_CLUB_COMPS)


def all_history(p, include_current=True):
    hist = {str(c): dict(p.aux(f"history/{c}")) for c in R.UAE_CLUB_COMPS}
    if include_current:
        for c in R.UAE_CLUB_COMPS:
            fx = p.fixtures(c)
            if fx:
                season = next((m.get("season") for m in fx if m.get("season")), "current")
                hist[str(c)][season] = [HI.slim(m, season) for m in fx if m.get("id")]
    return hist


# ------------------------------------------------------------------ Tifo rating
def ratings(p):
    params = config.rating_params()
    hist = all_history(p)
    rows = HI.finished(HI.all_rows(hist))
    if len(rows) < 200:
        return
    rat, history, preds = R.run(rows, params)
    names = p.names["teams"]
    cur_season = (p.st.get("comp_meta", {}).get(str(LEAGUE)) or {}).get("season")
    league_teams = {r["h"] for r in hist.get(str(LEAGUE), {}).get(cur_season, [])} | \
                   {r["a"] for r in hist.get(str(LEAGUE), {}).get(cur_season, [])}
    table = []
    for tid, r in rat.items():
        h = history.get(tid) or []
        table.append({"team": tid, "name_ar": names.get(str(tid)), "rating": round(r, 1),
                      "change_5": round(r - h[-6][1], 1) if len(h) > 5 else None, "last_match": h[-1][0] if h else None,
                      "in_league": tid in league_teams})
    table.sort(key=lambda x: -x["rating"])
    for i, t in enumerate([t for t in table if t["in_league"]], 1):
        t["rank"] = i
    preds_cur = {str(x["id"]): [round(v, 4) for v in x["p"]] for x in preds if x["season"] == cur_season}
    p.aux("ratings").clear()
    p.aux("ratings").update({"params": params, "ratings": {str(k): v for k, v in rat.items()}, "preds": preds_cur,
                             "updated": iso(p.now())})
    p.store.put_json("ratings/uae-clubs.json", {
        "generated": iso(p.now()), "model": "tifo-elo v1", "params": {k: v for k, v in params.items() if not str(k).startswith(("brier", "n_", "test"))},
        "calibration": {k: params.get(k) for k in ("brier_test", "brier_base_rate", "n_test", "test_seasons")},
        "matches_rated": len(rows), "since": min((r["season"] for r in rows), default=None), "teams": table,
        "note": "Elo-style rating over every UAE club match FotMob has (Pro League since 2010/11); docs/TIFO-RATING.md"},
        cache="static")
    for tid, h in history.items():
        p.store.put_json(f"ratings/team/{tid}.json", {"team": tid, "name_ar": names.get(str(tid)), "history": h,
                                                      "fields": ["date", "rating_after", "match"]}, cache="static")
    p.mark("ratings")
    p.store.ok("ratings")


def probs_for(p, m):
    r = p.aux("ratings").get("ratings") or {}
    if m.get("comp") not in R.UAE_CLUB_COMPS or m.get("status") != S.SCHEDULED or not r:
        return None
    h, a = r.get(str(m["home"]["id"])), r.get(str(m["away"]["id"]))
    if h is None or a is None:
        return None
    params = {**R.DEFAULTS, **config.rating_params()}
    ph, pd, pa = R.probs(h, a, params, R.is_neutral(m))
    return {"home": round(ph, 3), "draw": round(pd, 3), "away": round(pa, 3), "model": "tifo-elo v1"}


# ------------------------------------------------------------------ club pages (coaches, all-competition fixtures)
def club_pages(p, limit=6):
    """Daily FotMob team page for every current Pro League club: current coach, coachHistory and the
    all-competition fixture list (fatigue, AFC trips). Owned by this function (state/coaches.json,
    state/team_fx.json); `limit` requests per run."""
    clubs = sorted(int(k) for k, v in p.st.get("team_comps", {}).items() if LEAGUE in v)
    n = 0
    for tid in clubs:
        if n >= limit or not p.has_time(8):
            break
        if not p.due("club_page", 1440, tid) and str(tid) in p.aux("coaches"):
            continue
        try:
            t = p.fm.team(tid)
            S.validate_team(t)
        except ERRORS as e:
            p.store.fail(f"club-page:{tid}", e)
            p.mark("club_page", tid)
            n += 1
            continue
        p.aux("coaches")[str(tid)] = {"coach": t.get("coach"), "history": t.get("coach_history")}
        p.aux("team_fx")[str(tid)] = [{k: m.get(k) for k in ("id", "comp", "kickoff_utc", "status", "home", "away", "score")}
                                      for m in t["fixtures"]]
        p.mark("club_page", tid)
        p.store.ok("club-pages")
        n += 1


def coaches_and_fatigue(p):
    st = p.store.get_json(f"comp/{LEAGUE}/standings.json")
    if not st:
        return
    now = p.now()
    coaches, team_fx = p.aux("coaches"), p.aux("team_fx")
    stadiums = {int(t): s for s in config.stadiums() for t in s.get("home_of") or []}
    fat, ctab = {}, {}
    for r in st["groups"][0]["rows"]:
        tid = r["team"]["id"]
        tf = team_fx.get(str(tid))
        if tf is not None:
            fat[str(tid)] = CL.fatigue(tf, now, stadiums.get(tid), p.st.get("venue_fm", {}), team_id=tid)
        c = coaches.get(str(tid))
        if c is not None:
            ctab[str(tid)] = {"current": c.get("coach"), "history": c.get("history") or []}
    if fat:
        p.store.put_json(f"comp/{LEAGUE}/fatigue.json", {"comp": LEAGUE, "generated": iso(now), "teams": fat,
                                                         "complete": len(fat) == len(st["groups"][0]["rows"])}, cache="static")
    if ctab:
        p.store.put_json(f"comp/{LEAGUE}/coaches.json", {"comp": LEAGUE, "generated": iso(now), "teams": ctab,
                                                         "complete": len(ctab) == len(st["groups"][0]["rows"]),
                                                         "note": "FotMob coachHistory: per coach and season, W/D/L and points per game"},
                         cache="static")


def prematch(p, m):
    """Pre-match (pH, pD, pA, source) for any match: Tifo club rating (UAE, then Arab clubs), national
    Elo, else None (the win-probability model then uses league base rates)."""
    h, a = m["home"]["id"], m["away"]["id"]
    neutral = R.is_neutral(m)
    for aux_name, params in (("ratings", {**R.DEFAULTS, **config.rating_params()}),
                             ("arab_ratings", {**R.DEFAULTS, **config.rating_params()})):
        r = (p.aux(aux_name).get("ratings") or {})
        if str(h) in r and str(a) in r:
            return (*R.probs(r[str(h)], r[str(a)], params, neutral), f"tifo-{aux_name}")
    ne = p.aux("national_elo").get("ratings") or {}
    ch, ca = config.country_of_team(h), config.country_of_team(a)
    names = {c["fotmob_team"]: c.get("martj42") for c in config.countries() if c.get("fotmob_team")}
    nh = names.get(h) or (NA.ALIASES.get(m["home"]["name"], m["home"]["name"]) if not ch else None)
    na = names.get(a) or (NA.ALIASES.get(m["away"]["name"], m["away"]["name"]) if not ca else None)
    if nh in ne and na in ne:
        return (*R.probs(ne[nh], ne[na], {**R.DEFAULTS, **NA.NATIONAL}, True), "national-elo")
    return None


# ------------------------------------------------------------------ league analytics (538)
def league(p):
    comp = config.competition(LEAGUE)
    st = p.store.get_json(f"comp/{LEAGUE}/standings.json")
    fx = p.fixtures(LEAGUE)
    if not st or not fx:
        return
    rows = st["groups"][0]["rows"]
    now = p.now()
    rat = {int(k): v for k, v in (p.aux("ratings").get("ratings") or {}).items()}
    params = {**R.DEFAULTS, **config.rating_params()}
    season = st.get("season")
    fin = [m for m in fx if m["status"] == S.FINISHED]
    seen, remaining = set(), []
    for m in fx:
        if m["status"] in (S.SCHEDULED, S.POSTPONED):
            key = (m["home"]["id"], m["away"]["id"])
            if key not in seen and all(key):
                seen.add(key)
                remaining.append((key[0], key[1], False))
    total = comp["matches_per_team"] * len(rows) // 2
    sim = None
    if rat and p.has_time(15):
        sim = SIM.simulate(rows, remaining, rat, params, n=10000, seed=_seed(season, len(fin)), legend=st.get("legend"))
        sim.update({"comp": LEAGUE, "season": season, "generated": iso(now), "played": len(fin),
                    "fixtures_check": {"played": len(fin), "remaining": len(remaining), "season_total": total,
                                       "complete": len(fin) + len(remaining) == total}})
        p.store.put_json(f"comp/{LEAGUE}/sim.json", sim, cache="static")
    # history rows for facts / fortress / pressure (league only)
    hist = all_history(p)
    lrows = HI.finished([r for rows_ in hist.get(str(LEAGUE), {}).values() for r in rows_])
    window = min((r["season"] for r in lrows if r["season"]), default=None)
    names = p.names["teams"]
    upcoming = [m for m in fx if m["status"] == S.SCHEDULED and m.get("id") and parse_utc(m.get("kickoff_utc"))
                and timedelta(0) < parse_utc(m["kickoff_utc"]) - now < timedelta(days=21)]
    facts, watch = {}, {}
    derbies = set(config.derbies())
    for m in upcoming:
        facts[str(m["id"])] = FA.match_facts(lrows, m, names, window)
        pr = probs_for(p, m)
        if pr:
            form = []
            for tid in (m["home"]["id"], m["away"]["id"]):
                g = FA.team_games(lrows, tid)[-5:]
                form.append(sum(3 if f > a else 1 if f == a else 0 for _, f, a, *_ in g))
            watch[str(m["id"])] = EX.watchability(m, (pr["home"], pr["draw"], pr["away"]),
                                                  tuple(sorted((m["home"]["id"], m["away"]["id"]))) in derbies,
                                                  (sim or {}).get("teams"), form)
    p.store.put_json(f"comp/{LEAGUE}/facts.json", {"comp": LEAGUE, "generated": iso(now), "since": window,
                                                   "matches": facts}, cache="static")
    p.store.put_json(f"comp/{LEAGUE}/watch.json", {"comp": LEAGUE, "generated": iso(now), "matches": watch,
                                                   "method": "35 closeness (1-|pH-pA|) + 20 derby + 30 table stakes "
                                                             "(max 4p(1-p) of the sim's title/Asia/relegation odds) + 15 form"},
                     cache="static")
    # coach pressure, fatigue, coaches
    preds = {int(k): v for k, v in (p.aux("ratings").get("preds") or {}).items()}
    coaches = p.aux("coaches")
    team_fx = p.aux("team_fx")
    stadiums = {int(t): s for s in config.stadiums() for t in s.get("home_of") or []}
    press, fat, coach_tables = {}, {}, {}
    for r in rows:
        tid = r["team"]["id"]
        games = [g + (mid,) for g, mid in _games_with_ids(lrows, tid)]
        c = coaches.get(str(tid)) or {}
        press[str(tid)] = CL.pressure(games, preds, c.get("coach"), c.get("history"), season)
        tf = team_fx.get(str(tid))
        if tf:
            fat[str(tid)] = CL.fatigue(tf, now, stadiums.get(tid), p.st.get("venue_fm", {}), team_id=tid)
        if c.get("history"):
            coach_tables[str(tid)] = {"current": c.get("coach"), "history": c["history"]}
    p.store.put_json(f"comp/{LEAGUE}/pressure.json", {"comp": LEAGUE, "generated": iso(now), "teams": press,
                                                      "method": CL.__doc__.split("FATIGUE")[0].strip()}, cache="static")
    p.store.put_json(f"comp/{LEAGUE}/fortress.json", {"comp": LEAGUE, "generated": iso(now),
                                                      **EX.fortress(lrows, config.stadiums(), window)}, cache="static")
    p.mark("league_analytics")


def _games_with_ids(rows, tid):
    out = []
    for r in sorted(rows, key=lambda r: r["ko"] or ""):
        if tid not in (r["h"], r["a"]):
            continue
        home = r["h"] == tid
        f, a = (r["hs"], r["as"]) if home else (r["as"], r["hs"])
        out.append(((r["ko"] or "", f, a, home, r["a"] if home else r["h"], r["season"]), r["id"]))
    return out


# ------------------------------------------------------------------ per-competition table tools
def comp_tables(p, cid, st, matches, kind):
    """bump (leagues), scenarios (any group with <= 8 games left). Called from refresh_comp."""
    now = iso(p.now())
    if kind == "league" and st and len(st["groups"]) == 1:
        p.store.put_json(f"comp/{cid}/bump.json", {"comp": cid, "generated": now, **TB.bump(matches)}, cache="static")
    if not st or p.comp_due_minutes(cid) == 2:
        return          # scenarios enumerate up to 3^8 outcomes: never inside a live competition's 2-minute refresh
    groups = []
    for g in st["groups"]:
        ids = {r["team"]["id"] for r in g["rows"]}
        rem = [(m["home"]["id"], m["away"]["id"]) for m in matches if m["status"] in (S.SCHEDULED, S.POSTPONED)
               and m["home"]["id"] in ids and m["away"]["id"] in ids]
        sc = TB.scenarios(g["rows"], rem)
        if sc:
            groups.append({"group": g.get("name"), **sc})
    if groups:
        p.store.put_json(f"comp/{cid}/scenarios.json", {"comp": cid, "generated": now, "groups": groups}, cache="warm")


def live_table(p, cid, live_matches):
    st = p.store.get_json(f"comp/{cid}/standings.json")
    if not st:
        return
    scores = {m["id"]: m["score"] for m in live_matches if m.get("score")}
    groups = [{"name": g.get("name"), "rows": TB.live_table(g["rows"], scores)} for g in st["groups"]]
    p.store.put_json(f"comp/{cid}/live-table.json", {"comp": cid, "generated": iso(p.now()), "groups": groups,
                                                     "order": TB.ORDER_NOTE + "; rank_before = source table"},
                     cache="live", heartbeat=True)


# ------------------------------------------------------------------ ledger-based extras (any competition)
def ledger_extras(p, cid):
    L = p.ledger(cid)["matches"]
    if not L:
        return
    base = {"comp": cid, "season": p.ledger(cid).get("season"), "generated": iso(p.now()), "matches_counted": len(L)}
    p.store.put_json(f"comp/{cid}/clutch.json", {**base, **EX.clutch(L)}, cache="static")
    p.store.put_json(f"comp/{cid}/minute-clock.json", {**base, **EX.minute_clock(L)}, cache="static")
    p.store.put_json(f"comp/{cid}/lineup-ages.json", {**base, **EX.lineup_ages(L)}, cache="static")
    p.store.put_json(f"comp/{cid}/rotation.json", {**base, **EX.rotation(L)}, cache="static")
    p.store.put_json(f"comp/{cid}/team-of-round.json", {**base, **PL.team_of_round(L)}, cache="static")


def style(p):
    comps = [LEAGUE, 47, 87, 55, 54, 53]
    styles = EX.team_style({c: p.ledger(c)["matches"] for c in comps})
    near = EX.nearest_styles(styles, LEAGUE, set(comps) - {LEAGUE})
    p.store.put_json(f"comp/{LEAGUE}/style.json", {"comp": LEAGUE, "generated": iso(p.now()),
                                                   "teams": {k: v for k, v in styles.items() if v["comp"] == LEAGUE},
                                                   "europe_pool": sum(1 for v in styles.values() if v["comp"] != LEAGUE),
                                                   **near}, cache="static")
    p.mark("style")


# ------------------------------------------------------------------ players
def player_extras(p, cid, table, raw):
    now = iso(p.now())
    slim = {pid: {"name": x["name"], "team": x["team"], "minutes": x["minutes"],
                  "stats": {k: {"per90": v.get("per90"), "value": v.get("value"), "pct": v.get("pct")} for k, v in x["stats"].items()}}
            for pid, x in table["players"].items()}
    p.aux("ptables")[str(cid)] = {"players": slim, "min_minutes": table["min_minutes"]}
    roles = {}
    for e in p.ledger(cid)["matches"].values():
        for pid, pl in (e.get("players") or {}).items():
            if len(pl) > 4 and pl[4]:
                roles[pid] = pl[4]
    cards = EX.cards(table, roles)
    p.store.put_json(f"comp/{cid}/cards.json", {"comp": cid, "generated": now, **cards}, cache="static")
    # most improved: previous season's rating list
    links = (raw.get("stats") or {}).get("seasonStatLinks") or []
    if len(links) > 1:
        try:
            prev = links[1]
            url = f"https://data.fotmob.com/stats/{cid}/season/{prev['TournamentId']}/rating.json"
            full = p.fm.http.get_json(url, min_ttl=86400)
            prev_list = [{"player": {"id": e.get("ParticiantId"), "name": e.get("ParticipantName")}, "team_id": e.get("TeamId"),
                          "value": e.get("StatValue"), "matches": e.get("MatchesPlayed")}
                         for tl in full.get("TopLists") or [] for e in tl.get("StatList") or []]
            cur = [{"player": e["player"], "team_id": e["team_id"], "value": e["value"], "matches": e.get("matches")}
                   for e in (table.get("_lists", {}).get("rating") or [])]
            if cur and prev_list:
                p.store.put_json(f"comp/{cid}/improved.json", {"comp": cid, "generated": now, "previous_season": prev.get("Name"),
                                                               **PL.improved(cur, prev_list)}, cache="static")
        except ERRORS as e:
            p.store.fail(f"improved:{cid}", e)
    if cid == LEAGUE:
        squads = {k: v for k, v in p.aux("squads").items() if int(k) != NATIONAL}
        from datetime import date
        p.store.put_json(f"comp/{cid}/young-uae.json", {"comp": cid, "generated": now,
                                                        **PL.young_uae(table, squads, date.fromisoformat(now[:10]))}, cache="static")
        tabs = {int(k): v for k, v in p.aux("ptables").items()}
        sim = PL.similar(tabs, LEAGUE)
        if sim:
            p.store.put_json(f"comp/{cid}/similar.json", {"comp": cid, "generated": now, "comps": sorted(tabs), **sim}, cache="static")
        clutch = EX.clutch(p.ledger(cid)["matches"])
        info = {}
        for tid, groups in squads.items():
            for g in groups or []:
                for pl in g.get("players") or []:
                    info[str(pl["id"])] = {"dob": pl.get("dob"), "country": pl.get("country"), "position": pl.get("position"),
                                           "number": pl.get("number")}
        for pid, summ in EX.summaries(table, cards, clutch, info).items():
            if p.has_time(3):
                p.store.put_json(f"player/{pid}.json", {"id": int(pid), "comp": cid, "season": p.ledger(cid).get("season"),
                                                       "generated": now, **summ}, cache="static")
        stats = p.store.get_json(f"comp/{cid}/stats.json") or {}
        active = {e["player"]["name"]: {"id": e["player"]["id"], "goals": e["value"]}
                  for e in (stats.get("lists") or {}).get("goals", [])}
        at = _alltime()
        if at:
            p.store.put_json(f"comp/{cid}/records.json", {"comp": cid, "generated": now, **EX.record_chase(at, active)}, cache="static")


_ALLTIME = {}


def _alltime():
    if "doc" not in _ALLTIME:
        import yaml
        try:
            with open(os.path.join(HERE, "alltime.yaml"), encoding="utf-8") as f:
                _ALLTIME["doc"] = yaml.safe_load(f)
        except OSError:
            _ALLTIME["doc"] = None
    return _ALLTIME["doc"]


def publish_alltime(p):
    at = _alltime()
    if at:
        p.store.put_json(f"comp/{LEAGUE}/alltime.json", {"comp": LEAGUE, **at}, cache="cold")


# ------------------------------------------------------------------ loans, league comparison
def loans(p, limit=8):
    out = p.aux("loans")
    n = 0
    for tid, items in list(p.aux("loans_out").items()):
        for it in items:
            pid = str(it["player"]["id"])
            if n >= limit or not p.has_time(4):
                break
            if not p.due("loan", 1440, pid):
                continue
            try:
                pl = p.fm.player(int(pid))
                out[pid] = {**pl, "parent_team": int(tid), "loan_date": it.get("date")}
                n += 1
            except ERRORS as e:
                p.store.fail("loans", e)
            p.mark("loan", pid)
    if out:
        p.store.put_json(f"comp/{LEAGUE}/loans.json", {"comp": LEAGUE, "generated": iso(p.now()),
                                                       "players": sorted(out.values(), key=lambda x: x.get("parent_team") or 0),
                                                       "note": "players the UAE clubs sent out on loan (FotMob team transfers), "
                                                               "with their current club and main-league stats"}, cache="static")


def league_squads_step(p, limit=2):
    """Weekly squad profile (size, ages, foreign share) of every team in the comparison leagues."""
    n = 0
    store = p.aux("league_squads")
    for cid in config.settings().get("compare_leagues", []):
        country = (p.st.get("comp_meta", {}).get(str(cid)) or {}).get("country")
        for tid_s, comps in p.st.get("team_comps", {}).items():
            if cid not in comps or n >= limit or not p.has_time(6):
                continue
            if not p.due("lsq", 7 * 1440, tid_s):
                continue
            sq = p.aux("squads").get(tid_s)
            try:
                if sq is None:
                    t = p.fm.team(int(tid_s))
                    sq = t["squad"]
                    n += 1
                players = [x for g in sq for x in g["players"]]
                league_country = p.cc_of(cid)
                store.setdefault(str(cid), {})[tid_s] = {
                    "n": len(players), "ages": [x["age"] for x in players if x.get("age")],
                    "foreign": sum(1 for x in players if x.get("country") and league_country and x["country"] != league_country)}
            except ERRORS as e:
                p.store.fail("league-squads", e)
            p.mark("lsq", tid_s)


def league_compare(p):
    out = {}
    for cid in config.settings().get("compare_leagues", []):
        fx = p.fixtures(cid) or []
        out[str(cid)] = {"name_ar": (config.competition(cid) or {}).get("name_ar"),
                         **PL.league_profile(fx, p.ledger(cid)["matches"], p.aux("league_squads").get(str(cid), {}), p.cc_of(cid))}
    p.store.put_json("leagues/compare.json", {"generated": iso(p.now()), "leagues": out,
                                              "note": "current season: goals per match and results from fixtures; ages and foreign "
                                                      "share from FotMob squads; attendance only where FotMob reports it"}, cache="static")
    p.mark("compare")


# ------------------------------------------------------------------ national teams
def national(p):
    try:
        text = urllib.request.urlopen(urllib.request.Request(NA.CSV_URL, headers={"User-Agent": "elyoxe-tifo/0.1"}),
                                      timeout=40).read().decode("utf-8")
        rows = NA.parse_csv(text)
        if len(rows) < 40000:
            raise S.Invalid(f"martj42 results has only {len(rows)} rows")
    except ERRORS as e:
        p.store.fail("national:martj42", e)
        p.mark("national")
        return
    known = {r[1] for r in rows} | {r[2] for r in rows}
    last = max(r[0] for r in rows)
    extra, unmatched = [], set()
    for cid in (329, 290, 10609, 10197, 77, 10242, 11156, 114):
        for m in p.fixtures(cid) or []:
            if m["status"] != S.FINISHED or not m.get("score") or (m.get("kickoff_utc") or "")[:10] <= last:
                continue
            h, a = NA.dataset_name(m["home"]["name"], known), NA.dataset_name(m["away"]["name"], known)
            if not h or not a:
                unmatched.update(x for x, y in ((m["home"]["name"], h), (m["away"]["name"], a)) if not y)
                continue
            tour = {329: "Gulf Cup", 290: "AFC Asian Cup", 77: "FIFA World Cup", 10242: "FIFA Arab Cup"}.get(cid, "qualification" if cid in (10609, 10197, 11156) else "Friendly")
            extra.append((m["kickoff_utc"][:10], h, a, m["score"]["home"], m["score"]["away"], tour, True, None, None))
    rat, _ = NA.elo(rows + extra)
    p.aux("national_elo").clear()
    p.aux("national_elo").update({"ratings": rat, "dataset_last": last, "fotmob_added": len(extra)})
    uae = rat.get("United Arab Emirates")
    top_asia = sorted(((n, r) for n, r in rat.items()), key=lambda x: -x[1])
    p.store.put_json("ratings/national.json", {
        "generated": iso(p.now()), "uae": round(uae, 1) if uae else None,
        "uae_world_rank": 1 + sum(1 for _, r in top_asia if uae and r > uae),
        "top": [{"team": n, "rating": round(r, 1)} for n, r in top_asia[:60]],
        "dataset": {"source": "github.com/martj42/international_results", "last_match": last, "fotmob_matches_added": len(extra),
                    "unmatched_names": sorted(unmatched)},
        "params": NA.NATIONAL}, cache="static")
    for cid in (329, 290):
        tournament(p, cid, rat, known)
    try:
        national_archives(p, text_rows=rows, extra=extra, known=known)
    except ERRORS as e:
        p.store.fail("national:archive", e)
    p.mark("national")
    p.store.ok("national:martj42")


def _name_to_fotmob(p, known):
    """martj42 team name -> FotMob national-team id, from every national competition's fixtures."""
    out = {c["martj42"]: c["fotmob_team"] for c in config.countries() if c.get("martj42") and c.get("fotmob_team")}
    for cid in (329, 290, 10609, 10197, 77, 10242, 11156, 289, 10608, 9571):
        for m in p.fixtures(cid) or []:
            for side in ("home", "away"):
                nm = NA.dataset_name(m[side]["name"], known)
                if nm and m[side]["id"] and nm not in out:
                    out[nm] = m[side]["id"]
    return out


def national_archives(p, text_rows, extra, known):
    """national/{id}/archive.json for the 22 Arab national teams: every result in martj42 (+ FotMob
    after its last date) and per-opponent head-to-head summaries."""
    to_id = _name_to_fotmob(p, known)
    ar = p.names["teams"]
    fotmob_ids = {}      # (date, fotmob team, fotmob opponent) -> FotMob match id, from national-team fixture lists
    for cid in (329, 290, 10609, 10197, 77, 10242, 11156, 289, 10608, 114):
        for m in p.fixtures(cid) or []:
            if m.get("kickoff_utc") and m.get("id"):
                d = m["kickoff_utc"][:10]
                fotmob_ids[(d, m["home"]["id"], m["away"]["id"])] = m["id"]
    rows = sorted(text_rows + extra)
    index = []
    for c in config.countries():
        if not c.get("arab"):
            continue
        me, tid = c["martj42"], c["fotmob_team"]
        games, h2h = [], {}
        for date, h, a, hs, as_, tour, neutral, *venue in rows:
            if me not in (h, a):
                continue
            home = h == me
            opp = a if home else h
            oid = to_id.get(opp)
            gf, ga = (hs, as_) if home else (as_, hs)
            res = "W" if gf > ga else "D" if gf == ga else "L"
            mid = fotmob_ids.get((date, tid, oid) if home else (date, oid, tid))
            games.append({"date": date, "opponent": {"name": opp, "id": oid, "name_ar": ar.get(str(oid)) if oid else None},
                          "home": home and not neutral, "neutral": neutral, "gf": gf, "ga": ga, "result": res,
                          "competition": tour, "match": mid,
                          "venue": {"city": venue[0], "country": venue[1]} if venue and venue[0] else None})
            s_ = h2h.setdefault(opp, {"opponent": opp, "id": oid, "name_ar": ar.get(str(oid)) if oid else None,
                                      "played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0, "first": date, "last": None})
            s_["played"] += 1
            s_[{"W": "won", "D": "drawn", "L": "lost"}[res]] += 1
            s_["gf"] += gf
            s_["ga"] += ga
            s_["last"] = {"date": date, "gf": gf, "ga": ga, "competition": tour}
        if not games:
            continue
        w = sum(1 for g in games if g["result"] == "W")
        d_ = sum(1 for g in games if g["result"] == "D")
        p.store.put_json(f"national/{tid}/archive.json", {
            "team": tid, "country": {"iso2": c["iso2"], "name_ar": c["name_ar"]}, "generated": iso(p.now()),
            "played": len(games), "won": w, "drawn": d_, "lost": len(games) - w - d_, "first": games[0]["date"],
            "matches": games, "h2h": sorted(h2h.values(), key=lambda x: -x["played"]),
            "source": "github.com/martj42/international_results (CC0) + FotMob results after its last date",
            "note": "venue = city and country from the dataset (FotMob-sourced rows after its last date have none); "
                    "match = FotMob match id where FotMob has the game in a covered competition"}, cache="static")
        index.append({"team": tid, "iso2": c["iso2"], "name_ar": c["name_ar"], "played": len(games), "first": games[0]["date"]})
    p.store.put_json("national/archives.json", {"generated": iso(p.now()), "teams": index}, cache="static")


def tournament(p, cid, rat_by_name, known):
    st = p.store.get_json(f"comp/{cid}/standings.json")
    fx = p.fixtures(cid) or []
    if not st or not fx:
        return
    ids = {}
    for m in fx:
        for side in ("home", "away"):
            nm = NA.dataset_name(m[side]["name"], known)
            if nm and m[side]["id"]:
                ids[m[side]["id"]] = rat_by_name.get(nm)
    ratings = {k: v for k, v in ids.items() if v is not None}
    groups = [{"letter": TO._grp_letter(g.get("name")), "rows": g["rows"]} for g in st["groups"]]
    rem = []
    for g in groups:
        tids = {r["team"]["id"] for r in g["rows"]}
        rem += [(m["home"]["id"], m["away"]["id"]) for m in fx if m["status"] == S.SCHEDULED
                and m["home"]["id"] in tids and m["away"]["id"] in tids]
    fin = sum(1 for m in fx if m["status"] == S.FINISHED)
    res = TO.simulate(groups, rem, st.get("bracket"), ratings, NA.NATIONAL, host=(config.competition(cid) or {}).get("host"),
                      n=10000, seed=_seed(cid, st.get("season"), fin))
    p.store.put_json(f"comp/{cid}/tournament-sim.json", {"comp": cid, "season": st.get("season"), "generated": iso(p.now()),
                                                         "rated_teams": len(ratings), **res}, cache="static")


def fifa(p):
    """UAE FIFA ranking: bundled history (tools/build_fifa_history.py) + FotMob's current ranking."""
    hist = _load_json("fifa_history.json") or {"history": []}
    snaps = p.aux("fifa")
    t = p.store.get_json(f"team/{NATIONAL}.json")
    fr = (t or {}).get("fifa_ranking")
    if fr and fr.get("updated"):
        snaps[fr["updated"]] = fr
    rows = list(hist["history"])
    known = {r["date"] for r in rows}
    for k, v in sorted(snaps.items()):
        d = "-".join(reversed(k.split(".")))       # 20.07.2026 -> 2026-07-20
        if d not in known:
            rows.append({"date": d, "rank": v.get("rank"), "points": v.get("points"), "afc_rank": v.get("afc_rank"),
                         "arab_rank": v.get("arab_rank"), "source": "fotmob"})
    p.store.put_json(f"national/{NATIONAL}/fifa.json", {"team": NATIONAL, "generated": iso(p.now()),
                                                        "source": hist.get("source"), "history": sorted(rows, key=lambda r: r["date"])},
                     cache="static")
    p.mark("fifa")


# ------------------------------------------------------------------ archive
def archive_queue(p):
    q = p.aux("archive")
    if q.get("built") == len(p.aux("history_meta").get(str(LEAGUE), {}).get("done", [])) and q.get("queue") is not None:
        return q
    derbies = set(config.derbies())
    queue = []
    hist = all_history(p, include_current=False)
    for cid, seasons in hist.items():
        for season, rows in seasons.items():
            if season < "2016/2017":
                continue                                  # FotMob has no events before 2016/17
            for r in HI.finished(rows):
                kind = None
                if tuple(sorted((r["h"], r["a"]))) in derbies:
                    kind = "derby"
                if int(cid) in (9943, 11027) and str(r.get("round") or "").lower() == "final":
                    kind = "final"
                if int(cid) == 11026:
                    kind = "super_cup"
                if kind:
                    queue.append({"id": r["id"], "kind": kind, "comp": int(cid), "season": season})
    done = set(q.get("done", []))
    q["queue"] = [x for x in queue if x["id"] not in done]
    q["built"] = len(p.aux("history_meta").get(str(LEAGUE), {}).get("done", []))
    q.setdefault("done", [])
    q.setdefault("index", [])
    return q


def archive_step(p, limit=2):
    q = archive_queue(p)
    n = 0
    while q["queue"] and n < limit and p.has_time(6):
        item = q["queue"].pop(0)
        try:
            d = p.fm.match(item["id"])
            S.validate_detail(d)
        except ERRORS as e:
            p.store.fail("archive", f"{item['id']}: {e}")
            q["done"].append(item["id"])
            n += 1
            continue
        n += 1
        q["done"].append(item["id"])
        if not d.get("events"):
            continue
        p.store.put_json(f"archive/{d['id']}.json", {**d, "archive_kind": item["kind"], "season": item["season"]}, cache="cold")
        q["index"].append({"id": d["id"], "kind": item["kind"], "comp": item["comp"], "season": item["season"],
                           "kickoff_utc": d.get("kickoff_utc"), "home": d["home"]["id"], "away": d["away"]["id"],
                           "score": d.get("score"), "events": len(d["events"])})
    if n:
        p.store.put_json("archive/index.json", {"generated": iso(p.now()), "matches": q["index"],
                                                "pending": len(q["queue"]),
                                                "note": "derbies (competitions.yaml `derbies`), cup finals and Super Cups since "
                                                        "2016/17 (FotMob has no match events before that); national-team "
                                                        "key games are the UAE matches in match/ and the tournament files"}, cache="static")
