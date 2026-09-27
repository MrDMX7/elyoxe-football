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
from compute import danger as DG
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
def history_comps():
    return [int(c) for c in config.settings().get("history_comps", R.UAE_CLUB_COMPS)]


def history_step(p, limit=2):
    """Fetch past seasons of the history competitions, `limit` requests per call, each season once."""
    n = 0
    meta = p.aux("history_meta")
    for cid in history_comps():
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


def history_complete(p, comps=R.UAE_CLUB_COMPS):
    meta = p.aux("history_meta")
    return all((meta.get(str(c)) or {}).get("seasons") is not None and
               set((meta[str(c)]["seasons"])) - {meta[str(c)].get("current")} <= set(meta[str(c)]["done"])
               for c in comps)


def all_history(p, include_current=True, comps=R.UAE_CLUB_COMPS):
    hist = {str(c): dict(p.aux(f"history/{c}")) for c in comps}
    if include_current:
        for c in comps:
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
    if m.get("status") != S.SCHEDULED:
        return None
    src = rating_source(m.get("comp"))
    r = p.aux(src).get("ratings") or {}
    h, a = r.get(str(m["home"]["id"])), r.get(str(m["away"]["id"]))
    if h is None or a is None:
        return None
    params = {**R.DEFAULTS, **(config.rating_params() if src == "ratings" else (config.settings().get("arab_rating") or {}))}
    ph, pd, pa = R.probs(h, a, params, R.is_neutral(m))
    from compute import insights as IN, winprob as WP
    lh, la = WP.rates((ph, pd, pa))
    return {"home": round(ph, 3), "draw": round(pd, 3), "away": round(pa, 3),
            "model": "tifo-elo v1" if src == "ratings" else "tifo-elo clubs v1",
            "scores": IN.score_grid(lh, la), "expected_goals": [round(lh, 2), round(la, 2)]}


# ------------------------------------------------------------------ club pages (coaches, all-competition fixtures)
def club_pages(p, limit=12):
    """Daily FotMob team page for every current Pro League club: current coach, coachHistory and the
    all-competition fixture list (fatigue, AFC trips). Owned by this function (state/coaches.json,
    state/team_fx.json); `limit` requests per run."""
    leagues = set(analytics_leagues())
    clubs = sorted(int(k) for k, v in p.st.get("team_comps", {}).items() if leagues & set(v))
    clubs.sort(key=lambda t: 0 if LEAGUE in p.st["team_comps"].get(str(t), []) else 1)
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
        if (t.get("venue") or {}).get("lat") is not None:
            p.aux("home_venues")[str(tid)] = {"lat": t["venue"]["lat"], "lon": t["venue"]["lon"], "name": t["venue"]["name"]}
        p.aux("team_fx")[str(tid)] = [{k: m.get(k) for k in ("id", "comp", "kickoff_utc", "status", "home", "away", "score")}
                                      for m in t["fixtures"]]
        p.mark("club_page", tid)
        p.store.ok("club-pages")
        n += 1


def coaches_and_fatigue(p):
    for cid in analytics_leagues():
        if p.has_time(6):
            _coaches_and_fatigue(p, cid)


def _coaches_and_fatigue(p, cid):
    st = p.store.get_json(f"comp/{cid}/standings.json")
    if not st or len(st.get("groups") or []) != 1:
        return
    now = p.now()
    coaches, team_fx = p.aux("coaches"), p.aux("team_fx")
    stadiums = {int(t): s for s in config.stadiums() for t in s.get("home_of") or []}
    home_venue = p.aux("home_venues")
    fat, ctab = {}, {}
    rows = st["groups"][0]["rows"]
    for r in rows:
        tid = r["team"]["id"]
        tf = team_fx.get(str(tid))
        if tf is not None:
            fat[str(tid)] = CL.fatigue(tf, now, stadiums.get(tid) or home_venue.get(str(tid)), p.st.get("venue_fm", {}), team_id=tid)
        c = coaches.get(str(tid))
        if c is not None:
            ctab[str(tid)] = {"current": c.get("coach"), "history": c.get("history") or []}
    if fat:
        p.store.put_json(f"comp/{cid}/fatigue.json", {"comp": cid, "generated": iso(now), "teams": fat,
                                                      "complete": len(fat) == len(rows)}, cache="static")
    if ctab:
        p.store.put_json(f"comp/{cid}/coaches.json", {"comp": cid, "generated": iso(now), "teams": ctab,
                                                      "complete": len(ctab) == len(rows),
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
def rating_source(cid):
    return "ratings" if cid in R.UAE_CLUB_COMPS else "arab_ratings"


def analytics_leagues():
    return [int(c) for c in config.settings().get("analytics_leagues", [LEAGUE])]


def complete_round_robin(rows, fx, matches_per_team):
    """Remaining fixtures = FotMob's unplayed ones plus, for a double round robin, every ordered pair
    FotMob has not published yet (Botola, Algeria, Tunisia, Qatar ... publish a few rounds at a time)."""
    teams = [r["team"]["id"] for r in rows]
    seen, remaining = set(), []
    for m in fx:
        key = (m["home"]["id"], m["away"]["id"])
        if all(key):
            if m["status"] in (S.SCHEDULED, S.POSTPONED) and key not in seen:
                remaining.append((key[0], key[1], False))
            seen.add(key)
    added = 0
    if matches_per_team == 2 * (len(teams) - 1):
        for h in teams:
            for a in teams:
                if h != a and (h, a) not in seen:
                    remaining.append((h, a, False))
                    added += 1
    return remaining, added


def league(p, cid=LEAGUE):
    comp = config.competition(cid)
    st = p.store.get_json(f"comp/{cid}/standings.json")
    fx = p.fixtures(cid)
    if not comp or not st or not fx or len(st.get("groups") or []) != 1:
        return
    rows = st["groups"][0]["rows"]
    now = p.now()
    src = rating_source(cid)
    rat = {int(k): v for k, v in (p.aux(src).get("ratings") or {}).items()}
    params = {**R.DEFAULTS, **(config.rating_params() if src == "ratings" else (config.settings().get("arab_rating") or {}))}
    season = st.get("season")
    fin = [m for m in fx if m["status"] == S.FINISHED]
    sim = None
    mpt = comp.get("matches_per_team")
    if rat and mpt and comp.get("magic", True) and p.has_time(15) and all(r["team"]["id"] in rat for r in rows):
        if cid == LEAGUE:       # 538: FotMob fixtures + official uaepl.ae pairings (already merged)
            seen, remaining, added = set(), [], 0
            for m in fx:
                key = (m["home"]["id"], m["away"]["id"])
                if m["status"] in (S.SCHEDULED, S.POSTPONED) and key not in seen and all(key):
                    seen.add(key)
                    remaining.append((key[0], key[1], False))
        else:
            remaining, added = complete_round_robin(rows, fx, mpt)
        total = mpt * len(rows) // 2
        played = sum((r.get("played") or 0) for r in rows) // 2
        sim = SIM.simulate(rows, remaining, rat, params, n=10000, seed=_seed(cid, season, played), legend=st.get("legend"))
        sim.update({"comp": cid, "season": season, "generated": iso(now), "played": played, "rating": src,
                    "fixtures_check": {"played": played, "remaining": len(remaining), "season_total": total,
                                       "pairings_added_not_yet_published": added,
                                       "complete": played + len(remaining) == total}})
        p.store.put_json(f"comp/{cid}/sim.json", sim, cache="static")
    hist = all_history(p, comps=(cid,))
    lrows = HI.finished([r for rows_ in hist.get(str(cid), {}).values() for r in rows_])
    window = min((r["season"] for r in lrows if r["season"]), default=None)
    names = p.names["teams"]
    upcoming = [m for m in fx if m["status"] == S.SCHEDULED and m.get("id") and parse_utc(m.get("kickoff_utc"))
                and timedelta(0) < parse_utc(m["kickoff_utc"]) - now < timedelta(days=21)]
    facts, watch = {}, {}
    derbies = set(config.derbies()) | {tuple(sorted(d["teams"])) for d in config.arab_derbies()}
    for m in upcoming:
        if lrows:
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
    if facts:
        p.store.put_json(f"comp/{cid}/facts.json", {"comp": cid, "generated": iso(now), "since": window,
                                                    "matches": facts}, cache="static")
    if watch:
        p.store.put_json(f"comp/{cid}/watch.json", {"comp": cid, "generated": iso(now), "matches": watch,
                                                    "method": "35 closeness (1-|pH-pA|) + 20 derby + 30 table stakes "
                                                              "(max 4p(1-p) of the sim's title/Asia/relegation odds) + 15 form"},
                         cache="static")
    preds = {int(k): v for k, v in (p.aux(src).get("preds") or {}).items()}
    coaches = p.aux("coaches")
    press = {}
    for r in rows:
        tid = r["team"]["id"]
        games = [g + (mid,) for g, mid in _games_with_ids(lrows, tid)]
        c = coaches.get(str(tid)) or {}
        press[str(tid)] = CL.pressure(games, preds, c.get("coach"), c.get("history"), season)
    if lrows and preds:
        p.store.put_json(f"comp/{cid}/pressure.json", {"comp": cid, "generated": iso(now), "teams": press,
                                                       "method": CL.__doc__.split("FATIGUE")[0].strip()}, cache="static")
    if lrows:
        stadiums = config.stadiums() if cid in R.UAE_CLUB_COMPS else \
            [{"id": None, "name_ar": None, "home_of": [r["team"]["id"]]} for r in rows]
        p.store.put_json(f"comp/{cid}/fortress.json", {"comp": cid, "generated": iso(now),
                                                       **EX.fortress(lrows, stadiums, window)}, cache="static")
    p.mark("league_analytics", cid)


def leagues_step(p):
    for cid in analytics_leagues():
        if not p.has_time(20):
            return
        if p.due("league_analytics", 60, cid) and history_complete(p, (cid,)):
            try:
                league(p, cid)
            except ERRORS as e:
                p.store.fail(f"league-analytics:{cid}", f"{type(e).__name__}: {e}")
                p.mark("league_analytics", cid)


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
            arab = [r["team"]["id"] for r in g["rows"] if (p.team_country(r["team"]["id"]) or {}).get("iso2") in _ARAB_ISO()]
            groups.append({"group": g.get("name"), "arab_clubs": arab, **sc})
    if groups:
        p.store.put_json(f"comp/{cid}/scenarios.json", {"comp": cid, "generated": now, "groups": groups}, cache="warm")


def _ARAB_ISO():
    return {c["iso2"] for c in config.countries() if c.get("arab")}


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
    europe = [47, 87, 55, 54, 53]
    comps = sorted(set(analytics_leagues()) | set(europe))
    styles = EX.team_style({c: p.ledger(c)["matches"] for c in comps})
    for cid in analytics_leagues():
        if cid in europe:
            continue
        near = EX.nearest_styles(styles, cid, set(europe))
        teams = {k: v for k, v in styles.items() if v["comp"] == cid}
        if teams:
            p.store.put_json(f"comp/{cid}/style.json", {"comp": cid, "generated": iso(p.now()), "teams": teams,
                                                        "europe_pool": sum(1 for v in styles.values() if v["comp"] in europe),
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
            if "403" in str(e) or "404" in str(e):
                p.store.ok(f"improved:{cid}", note="no previous-season rating list on FotMob for this league")
            else:
                p.store.fail(f"improved:{cid}", e)
    squads = {k: v for k, v in p.aux("squads").items() if int(k) != NATIONAL}
    tabs = {int(k): v for k, v in p.aux("ptables").items()}
    if cid not in (47, 87, 55, 54, 53, 42):
        sim_ = PL.similar(tabs, cid)
        if sim_:
            p.store.put_json(f"comp/{cid}/similar.json", {"comp": cid, "generated": now, "comps": sorted(tabs), **sim_}, cache="static")
    clutch_ = EX.clutch(p.ledger(cid)["matches"])
    info_ = {}
    for tid, groups in squads.items():
        for g in groups or []:
            for pl in g.get("players") or []:
                info_[str(pl["id"])] = {"dob": pl.get("dob"), "country": pl.get("country"), "position": pl.get("position"),
                                        "number": pl.get("number")}
    for pid, summ in EX.summaries(table, cards, clutch_, info_).items():
        if not p.has_time(3):
            break
        p.store.put_json(f"player/{pid}.json", {"id": int(pid), "comp": cid, "season": p.ledger(cid).get("season"),
                                               "generated": now, **summ, "form": p.aux("player_forms").get(pid, []),
                                               "form_fields": ["match", "date", "rating", "minutes", "goals", "assists"]},
                         cache="static")
    if cid == LEAGUE:
        from datetime import date
        p.store.put_json(f"comp/{cid}/young-uae.json", {"comp": cid, "generated": now,
                                                        **PL.young_uae(table, squads, date.fromisoformat(now[:10]))}, cache="static")
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
                    injured = []
                    for g in sq:
                        for pl_ in g["players"]:
                            if pl_.get("dob"):
                                p.aux("dobs")[str(pl_["id"])] = pl_["dob"]
                            if pl_.get("injury"):
                                injured.append({"id": pl_["id"], "name": pl_["name"], "type": "injury", "detail": pl_["injury"]})
                    p.aux("injuries")[tid_s] = injured
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
        import extra2
        extra2.nations_h2h(p, rows + extra)
        extra2.worldcup(p, rows)
    except ERRORS as e:
        p.store.fail("national:h2h", e)
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


# ------------------------------------------------------------------ records book
def records_book(p, cid):
    """comp/{id}/records-book.json from the league's history (every FotMob season) and the event ledger."""
    hist = all_history(p, comps=(cid,)).get(str(cid), {})
    rows = HI.finished([r for rs in hist.values() for r in rs])
    if len(rows) < 50:
        return
    names = p.names["teams"]
    nm = lambda t: names.get(str(t))  # noqa: E731

    def item(r, **kw):
        return {"match": r["id"], "date": (r["ko"] or "")[:10], "season": r["season"], "home": r["h"], "home_ar": nm(r["h"]),
                "away": r["a"], "away_ar": nm(r["a"]), "score": [r["hs"], r["as"]], **kw}
    biggest = sorted(rows, key=lambda r: (-abs(r["hs"] - r["as"]), -(r["hs"] + r["as"])))[:10]
    highest = sorted(rows, key=lambda r: (-(r["hs"] + r["as"]), -abs(r["hs"] - r["as"])))[:10]
    teams = {x for r in rows for x in (r["h"], r["a"])}
    streaks = {"winning": [], "unbeaten": [], "losing": [], "winless": []}
    tests = {"winning": lambda f, a: f > a, "unbeaten": lambda f, a: f >= a, "losing": lambda f, a: f < a,
             "winless": lambda f, a: f <= a}
    for t in teams:
        games = [(r["ko"] or "", r["hs"] if r["h"] == t else r["as"], r["as"] if r["h"] == t else r["hs"], r["id"])
                 for r in sorted(rows, key=lambda r: r["ko"] or "") if t in (r["h"], r["a"])]
        for k, test in tests.items():
            cur, start, best = 0, None, (0, None, None)
            for ko, f, a, mid in games:
                if test(f, a):
                    cur += 1
                    start = start or mid
                    if cur > best[0]:
                        best = (cur, start, mid)
                else:
                    cur, start = 0, None
            if best[0]:
                streaks[k].append({"team": t, "team_ar": nm(t), "length": best[0], "from_match": best[1], "to_match": best[2],
                                   "current": cur})
    for k in streaks:
        streaks[k] = sorted(streaks[k], key=lambda x: -x["length"])[:10]
    season_goals = {}
    for r in rows:
        for t, g in ((r["h"], r["hs"]), (r["a"], r["as"])):
            key = (t, r["season"])
            season_goals[key] = season_goals.get(key, 0) + g
    most = sorted(({"team": t, "team_ar": nm(t), "season": s_, "goals": g} for (t, s_), g in season_goals.items()),
                  key=lambda x: -x["goals"])[:10]
    hat, fastest = [], []
    for e in p.ledger(cid)["matches"].values():
        per = {}
        for g in e.get("goals") or []:
            if g.get("player") and g["type"] != "own_goal":
                per.setdefault(g["player"], []).append(g.get("m"))
            if g.get("m") is not None and g["type"] != "own_goal":
                fastest.append({"match": e["id"], "player": g.get("player"), "minute": g["m"], "team": e[g["side"]]})
        for pid, mins in per.items():
            if len(mins) >= 3:
                name = ((e.get("players") or {}).get(str(pid)) or [None])[0]
                hat.append({"match": e["id"], "player": pid, "name": name, "goals": len(mins), "minutes": mins,
                            "date": (e.get("ko") or "")[:10]})
    fastest = sorted(fastest, key=lambda x: x["minute"])[:10]
    p.store.put_json(f"comp/{cid}/records-book.json", {
        "comp": cid, "generated": iso(p.now()), "since": min(hist) if hist else None, "matches": len(rows),
        "biggest_wins": [item(r, margin=abs(r["hs"] - r["as"])) for r in biggest],
        "highest_scoring": [item(r, goals=r["hs"] + r["as"]) for r in highest],
        "streaks": streaks, "most_goals_in_season": most,
        "hat_tricks": sorted(hat, key=lambda x: x["date"], reverse=True), "fastest_goals": fastest,
        "events_scope": f"hat-tricks and fastest goals: this season's stored match events ({p.ledger(cid).get('season')}); "
                        "results records: every season FotMob has"}, cache="static")


# ------------------------------------------------------------------ danger index (xG proxy)
def danger(p):
    comps = [c["id"] for c in p.comps]
    ledgers = {cid: p.ledger(cid)["matches"] for cid in comps}
    model = DG.fit([L for L in ledgers.values()])
    if not model:
        p.store.fail("danger", "fewer than 200 team-matches with xG and stats in the ledgers yet")
        return
    p.aux("danger").clear()
    p.aux("danger").update(model)
    p.store.put_json("models/danger.json", {"generated": iso(p.now()), **model, "features": [f for f, _ in DG.FEATURES],
                                            "method": DG.__doc__.strip()}, cache="static")
    for cid, L in ledgers.items():
        if not L or any(e.get("xg") for e in L.values()):
            continue
        prox = DG.with_proxy_xg(L, model)
        xt = SEASON.xg_table(prox)
        if xt.get("available"):
            p.store.put_json(f"comp/{cid}/xg.json", {"comp": cid, "season": p.ledger(cid).get("season"),
                                                     "generated": iso(p.now()), "matches_counted": len(L), **xt, "proxy": True,
                                                     "proxy_note": "no source xG for this competition: xg_for/against are the "
                                                                   "Tifo danger index (models/danger.json), fitted on leagues with xG"},
                             cache="static")
    p.store.ok("danger")


# ------------------------------------------------------------------ Arab clubs rating (192)
def arab_ratings(p):
    """One Elo scale over every Arab league and the AFC/CAF/Arab club competitions that link them."""
    comps = history_comps()
    if not history_complete(p, comps):
        return
    hist = all_history(p, comps=comps)
    seen, rows = set(), []
    for r in HI.finished(HI.all_rows(hist)):
        if r["id"] in seen or not r["ko"]:
            continue
        seen.add(r["id"])
        y = int(r["ko"][:4]) - (1 if int(r["ko"][5:7]) < 7 else 0)
        rows.append({**r, "season": f"{y}/{y + 1}"})
    params = {**R.DEFAULTS, **(config.settings().get("arab_rating") or {})}
    rat, history, preds = R.run(rows, params)
    cur = max((r["season"] for r in rows), default=None)
    p.aux("arab_ratings")["preds"] = {str(x["id"]): [round(v, 4) for v in x["p"]] for x in preds if x["season"] == cur}
    # every pre-match prediction of the season with its outcome (the private accuracy report reads this)
    p.aux("arab_ratings")["season_preds"] = [[x["id"], x["ko"], x.get("comp"), x["h"], x["a"], [round(v, 4) for v in x["p"]], x["outcome"]]
                                             for x in preds if x["season"] == cur]
    # club country (domestic league) for continental history / monthly bundles
    comp_cc_ = {c["id"]: (c.get("country") or {}).get("iso2") for c in p.comps}
    cc_map = {}
    for r in sorted(rows, key=lambda r: r["ko"]):
        cc = comp_cc_.get(r["comp"])
        if cc:
            cc_map[str(r["h"])] = cc
            cc_map[str(r["a"])] = cc
    p.aux("arab_ratings")["club_country"] = cc_map
    months = {}
    for tid, h in history.items():
        mm = {}
        for d_, r_, _m in h:
            if d_:
                mm[d_[:7]] = r_
        months[str(tid)] = dict(list(sorted(mm.items()))[-24:])
    p.aux("arab_ratings")["months"] = months
    import more
    more.upsets(p, preds)
    # a club's country = the country of the domestic league it played in most recently
    comp_cc = {c["id"]: c.get("country") for c in p.comps}
    home_cc = {}
    for r in sorted(rows, key=lambda r: r["ko"]):
        cc = comp_cc.get(r["comp"])
        if cc:
            home_cc[r["h"]] = cc
            home_cc[r["a"]] = cc
    arab_iso = {c["iso2"] for c in config.countries() if c.get("arab")}
    now = p.now()
    names = p.names["teams"]
    table = []
    for tid, r in rat.items():
        cc = home_cc.get(tid)
        if not cc or cc["iso2"] not in arab_iso:
            continue
        h = history.get(tid) or []
        last = h[-1][0] if h else None
        if not last or (now - parse_utc(last + "T00:00:00Z")).days > 400:
            continue                           # not active in the last season
        past = [x for x in h if x[0] and (now - parse_utc(x[0] + "T00:00:00Z")).days >= 90]
        table.append({"team": tid, "name_ar": names.get(str(tid)), "country": cc, "rating": round(r, 1),
                      "change_5": round(r - h[-6][1], 1) if len(h) > 5 else None,
                      "change_90d": round(r - past[-1][1], 1) if past else None, "last_match": last})
    table.sort(key=lambda x: -x["rating"])
    for i, t in enumerate(table, 1):
        t["rank"] = i
    p.aux("arab_ratings").update({"ratings": {str(k): v for k, v in rat.items()}, "updated": iso(now)})
    p.store.put_json("ratings/arab-clubs.json", {
        "generated": iso(now), "model": "tifo-elo arab v1", "params": params,
        "calibration": config.settings().get("arab_rating_calibration"), "matches_rated": len(rows),
        "competitions": comps, "teams": table[:100], "active_clubs": len(table),
        "note": "one scale: domestic leagues are linked by AFC, CAF and Arab club competitions; country = the "
                "domestic league the club played in most recently; clubs inactive for 400 days are left out"},
        cache="static")
    p.store.ok("arab-ratings")
