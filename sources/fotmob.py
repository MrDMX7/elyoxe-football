"""FotMob public JSON (www.fotmob.com/api/data/...) -> normalized schema. The main source.

Endpoints (docs: research/league-2026-09-26.md):
  matches?date=YYYYMMDD&timezone=Asia/Dubai   every match on a UAE calendar day (all competitions)
  leagues?id=N                                 table(s), all fixtures, stat leaders, season
  matchDetails?matchId=N                       header, events, lineups, stats, h2h, venue
  teams?id=N                                   squad, fixtures across competitions, venue
  data.fotmob.com/stats/...json                full leader lists (fetchAllUrl)
  translationmapping?locale=ar                 Arabic team/competition names (2.5 MB, weekly cache)

Traps handled here:
  * kickoff comes from status.utcTime only; the dd.mm.yyyy strings are Europe/Oslo (timeutil).
  * the day scoreboard lists group ids (Gulf Cup Grp. A = 943992); `primaryId` is the competition.
  * liveTime.short carries U+200E marks and a curly apostrophe ("16‎’‎").
  * substitution swap = [player in, player out].
  * group tournaments have `table[0].data.composite` with `tables[]` instead of `table`.
"""
import re
from urllib.parse import quote

from timeutil import parse_utc, parse_fotmob_local, iso, kickoff_pair
from . import schema as S
from .base import Source
from .http import Http

API = "https://www.fotmob.com/api/data"
TRANSLATIONS = "https://www.fotmob.com/api/translationmapping?locale=ar"


def _clean_minute(s):
    if s is None:
        return None
    s = str(s)
    if s.strip().upper() in ("HT", "FT", "PEN", "AET", "ET", "BREAK"):
        return s.strip().upper()
    s = re.sub(r"[^0-9+]", "", s)
    return s or None


def status_of(st: dict) -> tuple[str, str | None, str | None]:
    """FotMob status block -> (status, detail, minute)."""
    st = st or {}
    reason = (st.get("reason") or {}).get("short")
    live = st.get("liveTime") or {}
    if st.get("awarded"):
        return S.AWARDED, reason or "AW", None
    if st.get("cancelled"):
        r = (reason or "").upper()
        if r.startswith("PP") or "postpon" in ((st.get("reason") or {}).get("longKey") or ""):
            return S.POSTPONED, reason, None
        if r.startswith("AB"):
            return S.ABANDONED, reason, None
        return S.CANCELLED, reason, None
    if st.get("finished"):
        return S.FINISHED, reason or "FT", None
    if st.get("started"):
        short = live.get("short") or reason
        if (short or "").strip().upper() == "HT" or live.get("shortKey") == "halftime_short":
            return S.HALFTIME, "HT", "HT"
        return S.LIVE, None, _clean_minute(short)
    return S.SCHEDULED, None, None


_KO_KEYS = [(r"^(1/64|1/32|1/16|1/8|1/4|1/2)$", None), (r"^(final)$", "final"), (r"^(bronze|3rd place( final)?|third place.*)$", "3rd"),
            (r"^quarter-?finals?$", "1/4"), (r"^semi-?finals?$", "1/2"), (r"^(8th finals|round of 16)$", "1/8"),
            (r"^(16th finals|round of 32)$", "1/16"), (r"^(1st preliminary round)$", "prelim-1"),
            (r"^(2nd preliminary round)$", "prelim-2"), (r"^(preliminary round)$", "prelim"),
            (r"^(qualifying round|play-?off( round)?s?)$", "playoff")]
ROUND_AR = {"1/64": "دور الـ128", "1/32": "دور الـ64", "1/16": "دور الـ32", "1/8": "دور الـ16", "1/4": "ربع النهائي",
            "1/2": "نص النهائي", "final": "النهائي", "3rd": "مباراة المركز الثالث", "prelim-1": "الدور التمهيدي الأول",
            "prelim-2": "الدور التمهيدي الثاني", "prelim": "الدور التمهيدي", "playoff": "الملحق"}


def round_key(r):
    """FotMob round labels -> one key per round: matchdays "1", "2" ...; knockouts 1/16 ... 1/2, final, 3rd;
    prelim-1, prelim-2, prelim, playoff. "Group Stage - Round 3" -> "3", "Quarter-finals" -> "1/4",
    "8th Finals" -> "1/8", "3rd Place Final"/"bronze" -> "3rd". No spaces, so it is safe in a URL."""
    if r in (None, ""):
        return None
    t = str(r).strip()
    if t.isdigit():
        return t
    low = t.lower()
    m = re.match(r"^(?:group stage\s*-\s*)?(?:round|matchday|group stage round)\s*(\d+)$", low)
    if m:
        return m.group(1)
    for pat, key in _KO_KEYS:
        if re.match(pat, low):
            return key or low
    return re.sub(r"\s+", "-", low)


def round_ar(key):
    if not key:
        return None
    return f"الجولة {key}" if key.isdigit() else ROUND_AR.get(key)


def placeholder_ar(name):
    """Bracket placeholders FotMob leaves in English: "Winner SF 1" -> «الفايز من نص النهائي 1»."""
    m = re.match(r"^(Winner|Loser)\s+(SF|QF|R16|R32)\s*(\d+)$", str(name or "").strip(), re.I)
    if not m:
        return None
    stage = {"SF": "نص النهائي", "QF": "ربع النهائي", "R16": "دور الـ16", "R32": "دور الـ32"}[m.group(2).upper()]
    return f"{'الفايز' if m.group(1).lower() == 'winner' else 'الخاسر'} من {stage} {m.group(3)}"


PERIODS = (("1H", "firstHalfStarted", "firstHalfEnded", 0), ("2H", "secondHalfStarted", "secondHalfEnded", 45),
           ("ET1", "firstExtraHalfStarted", None, 90), ("ET2", "secondExtraHalfStarted", None, 105))


def clock_of(st: dict, status: str) -> dict:
    """Live clock anchor from FotMob's period start times (Oslo wall clock -> UTC): the running period, when it
    started and its base minute, so a client can tick the minute locally (base + elapsed). period_start is null
    while the clock is stopped (half-time, the break before extra time, penalties) or unknown."""
    if status not in S.LIVE_STATUSES:
        return {}
    halfs = (st or {}).get("halfs") or {}
    cur = None
    for name, start, end, base in PERIODS:
        if halfs.get(start):
            cur = (name, start, end, base)
    if not cur or status == S.HALFTIME or (cur[2] and halfs.get(cur[2])):
        return {"period": "HT" if status == S.HALFTIME else "break" if cur else None, "period_start": None,
                "period_base": None, "period_length": None}
    started = parse_fotmob_local(halfs.get(cur[1]))
    return {"period": cur[0], "period_start": iso(started) if started else None, "period_base": cur[3],
            "period_length": 15 if cur[0].startswith("ET") else (st.get("periodLength") or 45)}


def score_of(score_str, home=None, away=None):
    if isinstance(home, int) and isinstance(away, int) and not score_str:
        return {"home": home, "away": away}
    if not score_str:
        return None
    m = re.match(r"\s*(\d+)\s*-\s*(\d+)\s*$", str(score_str))
    return {"home": int(m.group(1)), "away": int(m.group(2))} if m else None


class FotMob(Source):
    name = "fotmob"

    def __init__(self, http: Http | None = None, names: dict | None = None):
        self.http = http or Http()
        self.names = names or {"teams": {}, "competitions": {}, "countries": {}}

    # ---------- helpers ----------
    def _team(self, tid, name):
        tid = S._int(tid)
        return S.team_ref(tid, name, self.names.get("teams", {}).get(str(tid)) if tid else placeholder_ar(name))

    def _match(self, *, mid, comp, status_block, home, away, round_=None, stage=None, season=None,
               home_score=None, away_score=None, pens=None, time_tbd=False):
        status, detail, minute = status_of(status_block)
        ko = parse_utc((status_block or {}).get("utcTime"))
        score = None
        if status not in (S.SCHEDULED, S.POSTPONED, S.CANCELLED):
            score = score_of((status_block or {}).get("scoreStr"), home_score, away_score)
        return {
            "id": S._int(mid), "comp": S._int(comp), "season": season,
            "round": round_key(round_), "round_ar": round_ar(round_key(round_)), "stage": stage or None,
            **kickoff_pair(ko), "time_tbd": bool(time_tbd or (status_block or {}).get("matchTimeTbd")),
            "status": status, "status_detail": detail, "minute": minute,
            "score": score, "penalties": pens,
            "home": self._team(home.get("id"), home.get("name") or home.get("longName")),
            "away": self._team(away.get("id"), away.get("name") or away.get("longName")),
            **clock_of(status_block, status),
            "source": self.name,
        }

    # ---------- day scoreboard ----------
    def day_raw(self, yyyymmdd):
        return self.http.get_json(f"{API}/matches?date={yyyymmdd}&timezone={quote('Asia/Dubai', safe='')}")

    def day(self, yyyymmdd, comp_filter=lambda m: True):
        raw = self.day_raw(yyyymmdd)
        return self.day_from_raw(raw, comp_filter)

    def day_from_raw(self, raw, comp_filter=lambda m: True):
        out = []
        for lg in raw.get("leagues") or []:
            comp = lg.get("primaryId") or lg.get("parentLeagueId") or lg.get("id")
            is_group = bool(lg.get("isGroup")) or (lg.get("id") != comp)   # isGroup is absent with &timezone=
            for m in lg.get("matches") or []:
                h, a = m.get("home") or {}, m.get("away") or {}
                pens = None
                if h.get("penScore") is not None and a.get("penScore") is not None:
                    pens = {"home": h["penScore"], "away": a["penScore"]}
                mm = self._match(mid=m.get("id"), comp=comp, status_block=m.get("status"), home=h, away=a,
                                 round_=m.get("tournamentStage"), stage=lg.get("name") if is_group else None,
                                 home_score=h.get("score"), away_score=a.get("score"), pens=pens)
                mm["group_id"] = S._int(lg.get("id")) if is_group else None
                if comp_filter(mm):
                    out.append(mm)
        return out

    # ---------- competition ----------
    def league_raw(self, comp_id, season=None):
        url = f"{API}/leagues?id={int(comp_id)}"
        if season:
            url += "&season=" + quote(season, safe="")
        return self.http.get_json(url)

    def competition(self, comp: dict, with_leaders=True) -> dict:
        raw = self.league_raw(comp["id"], comp.get("season"))
        return self.competition_from_raw(comp, raw, with_leaders)

    def competition_from_raw(self, comp, raw, with_leaders=True):
        det = raw.get("details") or {}
        cid = S._int(det.get("id") or comp["id"])
        season = det.get("selectedSeason")
        fx = raw.get("fixtures") or {}
        matches = []
        for f in fx.get("allMatches") or []:
            matches.append(self._match(mid=f.get("id"), comp=cid, status_block=f.get("status"),
                                       home=f.get("home") or {}, away=f.get("away") or {},
                                       round_=f.get("round") if f.get("round") is not None else f.get("roundName"),
                                       season=season))
        teams = {}
        for t in (fx.get("fixtureInfo") or {}).get("teams") or []:
            teams[S._int(t.get("id"))] = self._team(t.get("id"), t.get("name"))
        for m in matches:
            for side in ("home", "away"):
                if m[side]["id"] and m[side]["id"] not in teams:
                    teams[m[side]["id"]] = m[side]
        standings = self.standings_from_raw(cid, season, raw)
        leaders = self.leaders_from_raw(cid, season, raw, fetch_full=with_leaders) if with_leaders else None
        return {
            "competition": {
                "id": cid, "name": det.get("name"), "name_ar": self.names.get("competitions", {}).get(str(cid)),
                "short_name": det.get("shortName"), "country": det.get("country"), "season": season,
                "latest_season": det.get("latestSeason"), "seasons": (raw.get("allAvailableSeasons") or [])[:10],
                "color": det.get("leagueColor"), "has_table": standings is not None,
                "next_round": round_key(((fx.get("fixtureInfo") or {}).get("activeRound") or {}).get("roundId")),
                "source": self.name,
            },
            "matches": matches, "standings": standings, "leaders": leaders,
            "teams": [t for t in teams.values() if t["id"]],
        }

    def _rows(self, table_all, form_map, legend):
        zone = {}
        for lg in legend or []:
            for i in lg.get("indices") or []:
                zone[i] = {"label": lg.get("title"), "key": lg.get("tKey"), "color": lg.get("color")}
        rows = []
        for pos, r in enumerate(table_all or []):
            gf = ga = None
            m = re.match(r"\s*(\d+)\s*-\s*(\d+)", str(r.get("scoresStr") or ""))
            if m:
                gf, ga = int(m.group(1)), int(m.group(2))
            tid = S._int(r.get("id"))
            form = [x.get("resultString") for x in (form_map or {}).get(str(tid), []) if x.get("resultString")]
            rows.append({
                "rank": S._int(r.get("idx")) or pos + 1, "team": self._team(tid, r.get("name")),
                "played": r.get("played"), "won": r.get("wins"), "drawn": r.get("draws"), "lost": r.get("losses"),
                "gf": gf, "ga": ga, "gd": r.get("goalConDiff"), "pts": r.get("pts"),
                "deduction": r.get("deduction"), "form": form or None,
                "zone": zone.get(pos), "live": bool(r.get("ongoing")),
                # the live match FotMob already counted in this row, with the score it counted
                "ongoing": ({"match": S._int(r["ongoing"].get("id")), "home": S._int(r["ongoing"].get("hId")),
                             "away": S._int(r["ongoing"].get("aId")), "hs": r["ongoing"].get("hScore"),
                             "as": r["ongoing"].get("aScore")} if isinstance(r.get("ongoing"), dict) else None),
            })
        return rows

    def standings_from_raw(self, cid, season, raw):
        tabs = raw.get("table") or []
        if not tabs:
            return None
        t0 = tabs[0] or {}
        data = t0.get("data") or {}
        form_map = t0.get("teamForm") or {}
        groups = []
        if data.get("composite") or data.get("tables"):
            for g in data.get("tables") or []:
                tb = g.get("table") or {}
                rows = self._rows(tb.get("all"), form_map, g.get("legend") or data.get("legend"))
                groups.append({"id": S._int(g.get("leagueId")), "name": g.get("leagueName"), "rows": rows,
                               "home_rows": self._rows(tb.get("home"), {}, None) or None,
                               "away_rows": self._rows(tb.get("away"), {}, None) or None})
        else:
            tb = data.get("table") or {}
            rows = self._rows(tb.get("all"), form_map, data.get("legend"))
            groups.append({"id": cid, "name": None, "rows": rows,
                           "home_rows": self._rows(tb.get("home"), {}, None) or None,     # home games only
                           "away_rows": self._rows(tb.get("away"), {}, None) or None})
        groups = [g for g in groups if g["rows"]]
        if not groups:
            return None
        legend = [{"label": lg.get("title"), "key": lg.get("tKey"), "color": lg.get("color"),
                   "ranks": [i + 1 for i in lg.get("indices") or []]} for lg in data.get("legend") or []]
        bracket = None
        po = raw.get("playoff")
        if po and po.get("rounds"):
            bracket = []
            for rd in po["rounds"]:
                ties = []
                for mu in rd.get("matchups") or []:
                    ties.append({
                        "home": self._team(mu.get("homeTeamId"), mu.get("homeTeam")),
                        "away": self._team(mu.get("awayTeamId"), mu.get("awayTeam")),
                        "tbd": bool(mu.get("tbdTeam1") or mu.get("tbdTeam2")),
                        "matches": [S._int(x.get("matchId")) for x in mu.get("matches") or []],
                        "aggregate": mu.get("aggregatedResult"),
                        "winner": S._int((mu.get("aggregatedWinner") or {}).get("id")) if isinstance(mu.get("aggregatedWinner"), dict) else S._int(mu.get("aggregatedWinner")),
                    })
                bracket.append({"stage": round_key(rd.get("stage")), "stage_ar": round_ar(round_key(rd.get("stage"))), "ties": ties})
        return {"comp": cid, "season": season, "composite": len(groups) > 1 or bool(data.get("composite")),
                "groups": groups, "legend": legend, "bracket": bracket,
                "order": "source", "source": self.name}

    def leaders_from_raw(self, cid, season, raw, fetch_full=True, keys=("goals", "goal_assist", "_goals_and_goal_assist")):
        st = raw.get("stats") or {}
        lists = {}
        by_name = {p.get("name"): p for p in st.get("players") or []}
        out_key = {"goals": "goals", "goal_assist": "assists", "_goals_and_goal_assist": "goals_assists"}
        for k in keys:
            p = by_name.get(k)
            if not p:
                continue
            entries = None
            if fetch_full and p.get("fetchAllUrl"):
                try:
                    full = self.http.get_json(p["fetchAllUrl"], min_ttl=600)
                    entries = []
                    for tl in full.get("TopLists") or []:
                        for e in tl.get("StatList") or []:
                            entries.append({
                                "rank": e.get("Rank"),
                                "player": {"id": e.get("ParticiantId") or e.get("ParticipantId"), "name": e.get("ParticipantName")},
                                "team": self._team(e.get("TeamId"), e.get("TeamName")),
                                "value": _num(e.get("StatValue")), "matches": e.get("MatchesPlayed"),
                                "minutes": e.get("MinutesPlayed"),
                            })
                        break
                except Exception:
                    entries = None
            if entries is None:
                entries = [{"rank": e.get("rank"), "player": {"id": e.get("id"), "name": e.get("name")},
                            "team": self._team(e.get("teamId"), e.get("teamName")), "value": _num(e.get("value")),
                            "matches": None, "minutes": None} for e in p.get("topThree") or []]
            lists[out_key[k]] = entries
        if not lists:
            return None
        return {"comp": cid, "season": season, "lists": lists, "source": self.name}

    # ---------- match detail ----------
    def match_raw(self, match_id):
        return self.http.get_json(f"{API}/matchDetails?matchId={int(match_id)}")

    def match(self, match_id):
        return self.match_from_raw(self.match_raw(match_id))

    def match_from_raw(self, raw):
        g, h, c = raw.get("general") or {}, raw.get("header") or {}, raw.get("content") or {}
        teams = h.get("teams") or [{}, {}]
        st = dict(h.get("status") or {})
        st.setdefault("utcTime", g.get("matchTimeUTCDate"))
        home, away = teams[0] if teams else {}, teams[1] if len(teams) > 1 else {}
        pens = None
        if home.get("penScore") is not None:
            pens = {"home": home.get("penScore"), "away": away.get("penScore")}
        m = self._match(mid=g.get("matchId"), comp=g.get("parentLeagueId") or g.get("leagueId"), status_block=st,
                        home=home, away=away, round_=g.get("matchRound") or g.get("leagueRoundName"),
                        stage=g.get("leagueName"), home_score=home.get("score"), away_score=away.get("score"), pens=pens)
        m["group_id"] = S._int(g.get("leagueId")) if g.get("leagueId") != g.get("parentLeagueId") else None
        halfs = st.get("halfs") or {}
        m["periods"] = {k: iso(parse_fotmob_local(halfs.get(k))) for k in
                        ("firstHalfStarted", "firstHalfEnded", "secondHalfStarted", "secondHalfEnded",
                         "firstExtraHalfStarted", "secondExtraHalfStarted", "gameEnded") if halfs.get(k)}
        mf = c.get("matchFacts") or {}
        info = mf.get("infoBox") or {}
        stad = info.get("Stadium") or {}
        m["venue"] = {"name": stad.get("name"), "city": stad.get("city"), "country": stad.get("country"),
                      "lat": stad.get("lat"), "lon": stad.get("long"), "capacity": stad.get("capacity")} if stad.get("name") else None
        m["coverage"] = g.get("coverageLevel")          # "xG" (shotmap, momentum, xG) | "ratings" | "lower"
        m["referee"] = self._referee(info.get("Referee"))
        m["attendance"] = info.get("Attendance")
        raw_events = (mf.get("events") or {}).get("events") or []
        m["events"] = self._events(raw_events, m)
        m["halftime_score"] = next(({"home": e.get("homeScore"), "away": e.get("awayScore")} for e in raw_events
                                    if e.get("type") == "Half" and e.get("halfStrShort") == "HT"), None)
        m["lineups"] = self._lineups(c.get("lineup"))
        m["stats"] = self._stats(c.get("stats"))
        m["xg"] = self._xg(m["stats"])
        m["shotmap"] = self._shotmap((c.get("shotmap") or {}).get("shots"), m)
        mo = c.get("momentum")
        m["momentum"] = ([{"minute": p.get("minute"), "value": p.get("value")} for p in (mo.get("main") or {}).get("data") or []]
                         if isinstance(mo, dict) else None) or None   # + = home pressure, - = away
        hl = mf.get("highlights") or None
        m["highlights"] = {"url": hl.get("url"), "image": hl.get("image"), "source": hl.get("source")} if isinstance(hl, dict) and hl.get("url") else None
        m["h2h"] = self._h2h(c.get("h2h"))
        w = c.get("weather") or None
        m["weather_source"] = ({"temp_c": w.get("temperature"), "humidity": w.get("relativeHumidity"),
                                "wind_kmh": w.get("windSpeed"), "description": w.get("description"),
                                "at": w.get("lastUpdated")} if w else None)
        return m

    def _referee(self, ref):
        if not isinstance(ref, dict) or not ref.get("text"):
            return None
        stats = {}
        for s in ref.get("stats") or []:
            t = s.get("type")
            if t in ("matches", "redCards", "penalties"):
                stats[{"matches": "matches", "redCards": "red", "penalties": "penalties"}[t]] = s.get("value")
            elif t in ("yellowCards", "fouls"):
                k = "yellow" if t == "yellowCards" else "fouls"
                stats[k] = s.get("total")
                stats[k + "_per_match"] = s.get("value")
                stats[k + "_league_avg_per_match"] = s.get("average")
        return {"id": ref.get("id"), "name": ref.get("text"), "country": ref.get("countryCode") or None,
                "source_stats": ({"scope_comp": ref.get("leagueId"), "scope_name": ref.get("leagueName"), **stats}
                                 if stats else None)}

    def _xg(self, stats_groups):
        for g in stats_groups or []:
            for it in g["items"]:
                if it["key"] == "expected_goals" and it["home"] is not None:
                    return {"home": _num(it["home"]), "away": _num(it["away"])}
        return None

    def _shotmap(self, shots, m):
        """{player_id: [shot]} — FotMob publishes shots only at "xG" coverage (not the UAE leagues)."""
        if not shots:
            return None
        out = {}
        for s in shots:
            pid = str(s.get("playerId"))
            side = "home" if s.get("teamId") == m["home"]["id"] else "away"
            out.setdefault(pid, {"name": s.get("playerName"), "team": side, "shots": []})["shots"].append({
                "minute": s.get("min"), "added": s.get("minAdded"), "result": s.get("eventType"),
                "xg": _round(s.get("expectedGoals")), "xgot": _round(s.get("expectedGoalsOnTarget")),
                "x": s.get("x"), "y": s.get("y"), "on_target": s.get("isOnTarget"), "blocked": s.get("isBlocked"),
                "body": s.get("shotType"), "situation": s.get("situation"), "own_goal": s.get("isOwnGoal"),
                "inside_box": s.get("isFromInsideBox"),
                # goal-mouth: where the ball crossed the goal line (y across, z height; FotMob units, goal 0-2.44 m high)
                "goal_y": s.get("goalCrossedY"), "goal_z": s.get("goalCrossedZ"),
                "on_goal": {"x": (s.get("onGoalShot") or {}).get("x"), "y": (s.get("onGoalShot") or {}).get("y")} if s.get("onGoalShot") else None,
                "keeper_id": s.get("keeperId"), "saved_off_line": s.get("isSavedOffLine")})
        return out

    def _events(self, evs, m):
        out = []
        seen = {}
        hid, aid = m["home"]["id"], m["away"]["id"]
        for e in evs:
            t = e.get("type")
            side = "home" if e.get("isHome") is True else "away" if e.get("isHome") is False else None
            base = {"minute": e.get("time"), "added": e.get("overloadTime") or None, "team": side,
                    "team_id": hid if side == "home" else aid if side == "away" else None,
                    "player": None, "assist": None, "player_out": None, "score": None, "detail": None}
            p = e.get("player") or {}
            if p.get("name"):
                base["player"] = {"id": S._int(p.get("id")) or None, "name": p.get("name")}
            if t == "Goal":
                if e.get("isPenaltyShootoutEvent"):
                    typ = "shootout_goal" if not e.get("penShootoutMiss") else "shootout_miss"
                elif e.get("ownGoal"):
                    typ = "own_goal"
                elif (e.get("goalDescription") or "").lower().startswith("penalty"):
                    typ = "penalty_goal"
                else:
                    typ = "goal"
                if e.get("assistInput"):
                    base["assist"] = {"id": e.get("assistPlayerId"), "name": e.get("assistInput")}
                ns = e.get("newScore")
                if isinstance(ns, list) and len(ns) == 2:
                    base["score"] = {"home": ns[0], "away": ns[1]}
                gd = e.get("goalDescription")
                base["detail"] = gd if gd and typ == "goal" else None     # Header, Direct freekick ...
            elif t == "Card":
                card = (e.get("card") or "").lower()
                typ = "second_yellow" if ("yellowred" in card or "second" in card) else "red" if "red" in card else "yellow"
                cr = e.get("cardReason") or {}
                base["detail"] = cr.get("defaultText") or e.get("cardDescription") or None
                base["reason_key"] = cr.get("localizedKey")
            elif t == "Substitution":
                typ = "sub"
                sw = e.get("swap") or []
                if len(sw) >= 1:
                    base["player"] = {"id": S._int(sw[0].get("id")) or None, "name": sw[0].get("name")}
                if len(sw) >= 2:
                    base["player_out"] = {"id": S._int(sw[1].get("id")) or None, "name": sw[1].get("name")}
                base["detail"] = "injury" if e.get("injuredPlayerOut") else None
            elif t == "Half":
                typ = "half"
                base["detail"] = e.get("halfStrShort")
            elif t == "AddedTime":
                typ = "added_time"
                base["detail"] = e.get("minutesAddedInput")
            elif t in ("MissedPenalty", "PenaltyMissed"):
                typ = "missed_penalty"
            elif t and t.lower().startswith("var"):
                typ = "var"
                dec = ((e.get("VAR") or {}).get("decision") or {}) if isinstance(e.get("VAR"), dict) else {}
                keys, vals = dec.get("key") or [], dec.get("value") or []
                base["reason_key"] = keys[0] if keys else None           # var_penalty_cancelled, var_goal_cancelled ...
                base["detail"] = vals[0] if vals else None                # "Penalty cancelled"
                base["var_outcome"] = _var_outcome(base["reason_key"])
            else:
                continue  # comments and anything new: skip rather than guess
            base["type"] = typ
            pid = (base.get("player") or {}).get("id") or 0
            key = f"{m['id']}-{typ}-{base['minute']}-{base['added'] or 0}-{pid}"
            seen[key] = seen.get(key, 0) + 1
            base["event_id"] = key if seen[key] == 1 else f"{key}-{seen[key]}"
            hl = e.get("highlight")
            if isinstance(hl, dict) and hl.get("url"):
                base["clip"] = hl.get("url")
            out.append(base)
        return out

    def _player(self, p):
        perf = p.get("performance") or {}
        vl, hl = p.get("verticalLayout") or {}, p.get("horizontalLayout") or {}
        return {"id": S._int(p.get("id")) or None, "name": p.get("name"), "number": p.get("shirtNumber"),   # FotMob sends id 0 for a player it has no page for
                "position_id": p.get("positionId") if p.get("positionId") is not None else p.get("usualPlayingPositionId"),
                "role": {0: "GK", 1: "DF", 2: "MF", 3: "FW"}.get(p.get("usualPlayingPositionId")),
                "country": p.get("countryCode"), "captain": bool(p.get("isCaptain")), "age": p.get("age"),
                "rating": perf.get("rating"),
                "minutes_on": next((x.get("time") for x in perf.get("substitutionEvents") or [] if x.get("type") == "subIn"), None),
                "minutes_off": next((x.get("time") for x in perf.get("substitutionEvents") or [] if x.get("type") == "subOut"), None),
                # pitch position for a 3D view: 0-1 fractions of the pitch as FotMob draws it
                "xy": {"x": vl.get("x"), "y": vl.get("y")} if vl else None,
                "xy_h": {"x": hl.get("x"), "y": hl.get("y")} if hl else None}

    def _lineups(self, lu):
        if not lu:
            return None
        out = {"type": lu.get("lineupType")}
        for side, key in (("home", "homeTeam"), ("away", "awayTeam")):
            t = lu.get(key) or {}
            coach = t.get("coach") or None
            out[side] = {
                "team_id": t.get("id"), "formation": t.get("formation"),
                "coach": {"id": coach.get("id"), "name": coach.get("name")} if isinstance(coach, dict) else None,
                "starters": [self._player(p) for p in t.get("starters") or []],
                "subs": [self._player(p) for p in t.get("subs") or []],
                "unavailable": [{"id": p.get("id"), "name": p.get("name"),
                                 "type": (p.get("unavailability") or {}).get("type"),
                                 "expected_return": (p.get("unavailability") or {}).get("expectedReturn")}
                                for p in t.get("unavailable") or []],
            }
        return out

    def _stats(self, st):
        if not st:
            return None
        groups = []
        for g in ((st.get("Periods") or {}).get("All") or {}).get("stats") or []:
            items = [{"key": s.get("key"), "title": s.get("title"), "home": (s.get("stats") or [None, None])[0],
                      "away": (s.get("stats") or [None, None])[1]}
                     for s in g.get("stats") or [] if s.get("type") != "title"]
            if items:
                groups.append({"key": g.get("key"), "title": g.get("title"), "items": items})
        return groups or None

    def _h2h(self, h):
        if not h or not h.get("summary"):
            return None
        s = h["summary"]
        ms = []
        for x in h.get("matches") or []:
            st = x.get("status") or {}
            ms.append({"id": S._int(str(x.get("matchUrl") or "").rsplit("#", 1)[-1]),
                       "kickoff_utc": iso(parse_utc((x.get("time") or {}).get("utcTime") or st.get("utcTime"))),
                       "comp": S._int((x.get("league") or {}).get("id")),
                       "home": self._team((x.get("home") or {}).get("id"), (x.get("home") or {}).get("name")),
                       "away": self._team((x.get("away") or {}).get("id"), (x.get("away") or {}).get("name")),
                       "score": score_of(st.get("scoreStr"))})
        return {"summary": {"home_wins": s[0], "draws": s[1], "away_wins": s[2]}, "matches": ms}

    # ---------- team ----------
    def team_raw(self, team_id):
        return self.http.get_json(f"{API}/teams?id={int(team_id)}")

    def team(self, team_id):
        return self.team_from_raw(self.team_raw(team_id))

    def team_from_raw(self, raw):
        det = raw.get("details") or {}
        tid = S._int(det.get("id"))
        ref = self._team(tid, det.get("name"))
        squad = []
        coach = None
        for grp in ((raw.get("squad") or {}).get("squad") or []):
            title = grp.get("title")
            if title == "coach":
                c = (grp.get("members") or [None])[0]
                if c:
                    coach = {"id": c.get("id"), "name": c.get("name"), "country": c.get("ccode")}
                continue
            players = []
            for p in grp.get("members") or []:
                inj = p.get("injury")
                players.append({"id": p.get("id"), "name": p.get("name"), "number": p.get("shirtNumber"),
                                "position": p.get("positionIdsDesc"), "country": p.get("ccode") if len(str(p.get("ccode") or "")) == 3 else None,
                                "club": p.get("cname") if raw.get("squad", {}).get("isNationalTeam") else None,
                                "club_id": S._int(p.get("ccode")) if raw.get("squad", {}).get("isNationalTeam") else None,
                                "age": p.get("age"), "dob": p.get("dateOfBirth"), "height": p.get("height"),
                                "market_value_eur": p.get("transferValue"),
                                "goals": p.get("goals"), "assists": p.get("assists"),
                                "yellow": p.get("ycards"), "red": p.get("rcards"),
                                "injury": ({"type": inj.get("name") or inj.get("id"), "expected_return": inj.get("expectedReturn")}
                                           if isinstance(inj, dict) else None)})
            squad.append({"group": title, "players": players})
        fixtures = []
        for f in ((raw.get("fixtures") or {}).get("allFixtures") or {}).get("fixtures") or []:
            tour = f.get("tournament") or {}
            m = self._match(mid=f.get("id"), comp=tour.get("leagueId"), status_block=f.get("status"),
                            home=f.get("home") or {}, away=f.get("away") or {}, stage=tour.get("name"),
                            home_score=(f.get("home") or {}).get("score"), away_score=(f.get("away") or {}).get("score"))
            m["comp_name"] = tour.get("name")
            fixtures.append(m)
        venue = ((raw.get("overview") or {}).get("venue") or {}).get("widget") or {}
        loc = venue.get("location") or [None, None]
        coach_history = [{"id": c.get("id"), "name": c.get("name"), "season": c.get("season"), "comp": c.get("leagueId"),
                          "won": c.get("win"), "drawn": c.get("draw"), "lost": c.get("loss"), "ppg": c.get("pointsPerGame")}
                         for c in ((raw.get("overview") or {}).get("coachHistory") or [])]
        tdata = (raw.get("transfers") or {}).get("data") or {}
        transfers = {"in": [self._transfer(x) for x in tdata.get("Players in") or []],
                     "out": [self._transfer(x) for x in tdata.get("Players out") or []]} if tdata else None
        return {
            **ref, "short_name": det.get("shortName"), "country": det.get("country"),
            "national": bool((raw.get("squad") or {}).get("isNationalTeam")),
            "primary_comp": S._int(det.get("primaryLeagueId")),
            "venue": {"name": venue.get("name"), "city": venue.get("city"),
                      "lat": _num(loc[0]), "lon": _num(loc[1])} if venue.get("name") else None,
            "fifa_ranking": ({"rank": (det.get("fifaRanking") or {}).get("rank"), "points": (det.get("fifaRanking") or {}).get("points"),
                              "updated": (det.get("fifaRanking") or {}).get("updated")} if det.get("fifaRanking") else None),
            "coach": coach, "coach_history": coach_history, "squad": squad, "fixtures": fixtures,
            "transfers": transfers, "source": self.name,
        }

    def _transfer(self, x):
        fee = x.get("fee") or {}
        return {"player": {"id": x.get("playerId"), "name": x.get("name")},
                "position": (x.get("position") or {}).get("label"), "date": x.get("transferDate"),
                "from": self._team(x.get("fromClubId"), x.get("fromClub")) if x.get("fromClubId") not in (None, 2) else None,
                "to": self._team(x.get("toClubId"), x.get("toClub")) if x.get("toClubId") not in (None, 2) else None,
                "free_agent": x.get("fromClubId") == 2 or x.get("toClubId") == 2,
                "fee": fee.get("feeText"), "fee_eur": x.get("amountEuroEstimated"), "loan": bool(x.get("onLoan")),
                "type": (x.get("transferType") or {}).get("text"), "extension": bool(x.get("contractExtension"))}

    def league_transfers_from_raw(self, cid, raw):
        """League page `transfers` (latest ~100 moves) grouped per team: {team_id: {"in": [...], "out": [...]}}."""
        per = {}
        for x in ((raw.get("transfers") or {}).get("data") or []):
            t = self._transfer(x)
            if t["to"]:
                per.setdefault(str(t["to"]["id"]), {"in": [], "out": []})["in"].append(t)
            if t["from"]:
                per.setdefault(str(t["from"]["id"]), {"in": [], "out": []})["out"].append(t)
        return {"comp": cid, "teams": per, "source": self.name} if per else None

    def player_stat_lists(self, raw, only=None):
        """Every per-player season list the league page links (goals, rating, mins_played, per-90 ...):
        {stat_name: {"title", "entries": [{player, team, value, matches, minutes}]}}. One request per list."""
        out = {}
        for p in ((raw.get("stats") or {}).get("players") or []):
            name, url = p.get("name"), p.get("fetchAllUrl")
            if not url or (only and name not in only):
                continue
            full = self.http.get_json(url, min_ttl=3600)
            for tl in full.get("TopLists") or []:
                out[name] = {"title": tl.get("Title") or p.get("header"), "format": tl.get("StatFormat"),
                             "entries": [{"player": {"id": e.get("ParticiantId") or e.get("ParticipantId"),
                                                     "name": e.get("ParticipantName")},
                                          "team_id": e.get("TeamId"), "value": _num(e.get("StatValue")),
                                          "sub_value": _num(e.get("SubStatValue")),
                                          "matches": e.get("MatchesPlayed"), "minutes": e.get("MinutesPlayed")}
                                         for e in tl.get("StatList") or []]}
                break
        return out

    def player(self, player_id):
        """Player card: nationality, club, main-league season stats (used for UAE players abroad)."""
        raw = self.http.get_json(f"{API}/playerData?id={int(player_id)}", min_ttl=3600)
        info = {i.get("translationKey"): i for i in raw.get("playerInformation") or []}
        ctry = info.get("country_sentencecase") or {}
        pt = raw.get("primaryTeam") or {}
        ml = raw.get("mainLeague") or {}
        return {"id": raw.get("id"), "name": raw.get("name"), "country": ctry.get("countryCode"),
                "team": self._team(pt.get("teamId"), pt.get("teamName")) if pt.get("teamId") else None,
                "on_loan": bool(pt.get("onLoan")),
                "position": ((raw.get("positionDescription") or {}).get("primaryPosition") or {}).get("label"),
                "league": {"id": ml.get("leagueId"), "name": ml.get("leagueName"), "season": ml.get("season"),
                           "stats": {s.get("localizedTitleId"): s.get("value") for s in ml.get("stats") or []}} if ml else None,
                "source": self.name}

    # ---------- Arabic names ----------
    def arabic_names(self):
        raw = self.http.get_json(TRANSLATIONS, min_ttl=3600)
        teams = raw.get("Participants") or {}
        comps = raw.get("TournamentTemplates") or {}
        if len(teams) < 1000:
            raise S.Invalid(f"translation map has only {len(teams)} teams")
        return {"teams": teams, "competitions": comps, "countries": raw.get("CountryCodes") or {}}


def _num(v):
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return None


def _round(v, n=3):
    return round(v, n) if isinstance(v, (int, float)) else None


def _var_outcome(key):
    """Coarse class of a VAR decision key, for counting (disallowed goals, offside, penalties)."""
    k = (key or "").lower()
    if not k:
        return None
    if "offside" in k:
        return "goal_disallowed_offside" if "goal" in k else "offside"
    if "goal" in k and ("cancel" in k or "disallow" in k or "no_goal" in k):
        return "goal_disallowed"
    if "goal" in k:
        return "goal_confirmed"
    if "penalty" in k:
        return "penalty_cancelled" if ("cancel" in k or "no_penalty" in k) else "penalty_awarded"
    if "red" in k or "card" in k:
        return "card_changed" if ("cancel" in k or "downgrade" in k or "upgrade" in k) else "card"
    return "other"
