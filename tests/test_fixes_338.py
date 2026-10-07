"""338 (empty/missing files), 340 (derby h2h retry), 343 (source outage alert)."""
from datetime import datetime, timedelta, timezone

from compute import season as SEASON


def test_player_table_keeps_fotmob_per90_lists():
    lists = {"mins_played": {"title": "Minutes played", "entries": [{"player": {"id": 1, "name": "A"}, "team_id": 9, "value": 180}]},
             "goals": {"title": "Top scorer", "entries": [{"player": {"id": 1, "name": "A"}, "team_id": 9, "value": 2}]},
             "total_scoring_att": {"title": "Shots per 90", "format": "fraction",
                                   "entries": [{"player": {"id": 1, "name": "A"}, "team_id": 9, "value": 4.5}]}}
    st = SEASON.player_table(lists)["players"]["1"]["stats"]
    assert (st["goals"]["value"], st["goals"]["per90"]) == (2, 1.0)
    assert st["total_scoring_att"]["per90"] == 4.5              # the source rate, not rate x 90 / minutes
    assert st["total_scoring_att"]["total"] == 9.0              # 4.5 x 180 / 90


def _poller(tmp_path, role="poller"):
    import poller as P
    from store import Store, LocalBackend
    p = P.Poller(Store(LocalBackend(tmp_path)), role=role)
    p.load()
    return p


def test_not_ready_step_is_retried_soon(tmp_path):
    p = _poller(tmp_path, "analytics")
    t = [datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)]
    p.now_fn = lambda: t[0]
    calls = []
    p.analytics_chores(only=[("arab_ratings", 360, lambda: calls.append(1) or False), ("twins", 1440, lambda: calls.append(2))])
    assert calls == [1, 2]
    assert not p.due("arab_ratings", 360) and not p.due("twins", 1440)
    t[0] += timedelta(minutes=31)
    assert p.due("arab_ratings", 360) and not p.due("twins", 1440)     # not ready: again in 30 min, not in 6 h


def test_draw_baseline_file(tmp_path):
    p = _poller(tmp_path)
    cid = next(c["id"] for c in p.comps if c.get("kind") == "tournament")
    st = {"groups": [{"name": "A", "rows": [{"team": {"id": t}} for t in (1, 2)]}], "bracket": []}
    p.detect_draw(cid, st)
    assert f"draws/{cid}.json" in p.store.written
    d = p.store.get_json(f"draws/{cid}.json")
    assert d["events"] == [] and d["current"]["groups"][0]["teams"] == [1, 2] and d["baseline_at"]
    st["groups"][0]["rows"].append({"team": {"id": 3}})
    p.detect_draw(cid, st)
    assert len(p.store.get_json(f"draws/{cid}.json")["events"]) == 1
    league = next(c["id"] for c in p.comps if c.get("kind") == "league")
    p.detect_draw(league, st)
    assert f"draws/{league}.json" not in p.store.written


class _Mail:
    def __init__(self, fail=0):
        self.sent, self.fail = [], fail

    def __call__(self, subject, body):
        if self.fail:
            self.fail -= 1
            raise RuntimeError("SES throttled")
        self.sent.append(subject)


def _minute(tmp_path, st, t, mail, outcome):
    """One simulated poller minute: outcome 'bad' (FetchError / refused payload), 'good' or 'neutral' (idle, no FotMob item)."""
    from store import Store, LocalBackend
    import poller as P
    p = P.Poller(Store(LocalBackend(tmp_path)))
    p.load()
    p.st = st
    p.now_fn = lambda: t
    p.mailer = mail
    if outcome == "bad":
        p.store.fail("day:today", "HTTP 503 (https://www.fotmob.com/api/data/matches)")
    elif outcome == "invalid":
        p.store.fail("comp:538:fotmob", "not written, kept last good: no matches")
    elif outcome == "good":
        p.store.ok("day:today")
    p.source_watch()
    return p


def test_source_outage_alert_once_and_recovery_once(tmp_path):
    st, mail = {}, _Mail()
    t0 = datetime(2026, 9, 27, 18, 0, tzinfo=timezone.utc)
    seq = ["good", "bad", "neutral", "bad", "invalid"] + ["bad", "neutral"] * 8 + ["neutral", "good", "good", "bad", "good"]
    for i, o in enumerate(seq):
        _minute(tmp_path, st, t0 + timedelta(minutes=i), mail, o)
    # first bad run at minute 1; minute 16 is neutral, so the mail goes at minute 17; recovery at 22
    assert mail.sent == ["Tifo: FotMob down for 16 min", "Tifo: FotMob back after 21 min"]
    assert st["source_watch"]["first_bad_at"] is None and st["source_watch"]["alerted_at"] is None


def test_source_alert_retries_a_failed_send(tmp_path):
    st, mail = {}, _Mail(fail=1)
    t0 = datetime(2026, 9, 27, 18, 0, tzinfo=timezone.utc)
    for i in range(18):
        _minute(tmp_path, st, t0 + timedelta(minutes=i), mail, "bad")
    assert mail.sent == ["Tifo: FotMob down for 16 min"]         # first send failed at 15, retried at 16
    p = _minute(tmp_path, st, t0 + timedelta(minutes=19), mail, "good")
    assert mail.sent[-1].startswith("Tifo: FotMob back") and p.store.health["source:fotmob"]["ok"]


def test_short_blip_sends_nothing(tmp_path):
    st, mail = {}, _Mail()
    t0 = datetime(2026, 9, 27, 18, 0, tzinfo=timezone.utc)
    for i, o in enumerate(["bad"] * 10 + ["good"] + ["bad"] * 10 + ["good"]):
        _minute(tmp_path, st, t0 + timedelta(minutes=i), mail, o)
    assert mail.sent == []


def test_source_alert_gives_up_then_clears_health(tmp_path):
    st, mail = {}, _Mail(fail=99)
    t0 = datetime(2026, 9, 27, 18, 0, tzinfo=timezone.utc)
    for i in range(25):
        _minute(tmp_path, st, t0 + timedelta(minutes=i), mail, "bad")
    assert mail.sent == [] and st["source_watch"]["send_failures"] == 5
    p = _minute(tmp_path, st, t0 + timedelta(minutes=26), mail, "good")
    assert p.store.health["source-alert"]["ok"] and st["source_watch"]["send_failures"] == 0


def _detail(status="finished", minute=None, types=("goal", "half"), lineups=True):
    ev = [{"type": t, "minute": 10 + i, "added": None, "event_id": f"1-{t}-{10 + i}"} for i, t in enumerate(types)]
    lu = {"home": {"starters": [{"id": 1}]}, "away": {"starters": [{"id": 2}]}} if lineups else None
    return {"id": 1, "status": status, "minute": minute, "events": ev, "lineups": lu}


def test_coverage_events_flags_thin_feeds():
    import poller as P
    assert P.coverage_events(_detail()) == {"subs": False, "cards": False}                        # Gulf Cup 6052084
    assert P.coverage_events(_detail(types=("goal", "yellow", "half"))) == {"subs": False, "cards": True}
    assert P.coverage_events(_detail(types=("goal", "sub", "half"))) == {"subs": True, "cards": True}   # full feed, 0 cards
    assert P.coverage_events(_detail(status="live", minute="45+2")) == {"subs": True, "cards": True}      # too early to say
    assert P.coverage_events(_detail(status="live", minute="68")) == {"subs": False, "cards": False}
    assert P.coverage_events(_detail(lineups=False)) == {"subs": True, "cards": True}


def test_repoll_schedule_and_merge(tmp_path):
    import poller as P
    p = _poller(tmp_path)
    t = [datetime(2026, 9, 27, 18, 0, tzinfo=timezone.utc)]
    p.now_fn = lambda: t[0]
    d = _detail()
    full = {"events": [dict(e, first_seen="2026-09-27T17:10:00Z") for e in d["events"]], "coverage_events": P.coverage_events(d)}
    p.plan_repoll(d, full, "final")
    assert "1" in p.st["repoll"]
    p.store.put_json("match/1.json", full)
    fetched = []
    p.fetch_detail = lambda mid, why: fetched.append((mid, why))
    t[0] += timedelta(minutes=31)
    p.repolls()
    t[0] += timedelta(minutes=5)
    p.repolls()
    assert fetched == [(1, "repoll")]                      # 30' once, not again at 36'
    d2 = _detail(types=("goal", "sub", "half"))
    full2 = {"events": [dict(e) for e in d2["events"]], "coverage_events": P.coverage_events(d2),
             "highlights": {"url": "https://www.youtube.com/watch?v=x", "image": None, "source": "www.youtube.com"}}
    p.plan_repoll(d2, full2, "repoll")
    assert "1" not in p.st["repoll"]                       # complete now (events and the highlights video)
    ids = [e["event_id"] for e in full2["events"]]
    assert "1-half-11" in ids and "1-half-12" in ids       # the old event the new copy lacked is kept
    assert next(e for e in full2["events"] if e["event_id"] == "1-goal-10")["first_seen"] == "2026-09-27T17:10:00Z"


def test_repoll_waits_for_the_highlights_video(tmp_path):
    """A full feed without FotMob's highlights link is fetched again after full time; a later copy without the link
    keeps the one an earlier copy had."""
    import poller as P
    p = _poller(tmp_path)
    t = [datetime(2026, 9, 27, 18, 0, tzinfo=timezone.utc)]
    p.now_fn = lambda: t[0]
    d = _detail(types=("goal", "sub", "yellow", "half"))
    full = {"events": [dict(e) for e in d["events"]], "coverage_events": P.coverage_events(d), "highlights": None}
    p.plan_repoll(d, full, "final")
    assert "1" in p.st["repoll"]                           # complete events, no video yet
    hl = {"url": "https://www.youtube.com/watch?v=abc", "image": "https://i.ytimg.com/vi/abc/maxresdefault.jpg", "source": "www.youtube.com"}
    p.store.put_json("match/1.json", dict(full, highlights=hl))
    again = {"events": [dict(e) for e in d["events"]], "coverage_events": P.coverage_events(d), "highlights": None}
    p.plan_repoll(d, again, "repoll")
    assert again["highlights"] == hl and "1" not in p.st["repoll"]
    full_hl = dict(full, highlights=hl)
    p.plan_repoll(d, full_hl, "final")
    # video already there: no early re-poll, only the two late looks for FotMob's corrections (audit 2026-09-30)
    assert p.st["repoll"]["1"]["kind"] == "late" and p.st["repoll"]["1"]["done"] == [30, 60]


def test_live_watchdog_once_per_match(tmp_path):
    p = _poller(tmp_path)
    mail = _Mail()
    p.mailer = mail
    t = datetime(2026, 9, 27, 19, 0, tzinfo=timezone.utc)
    p.now_fn = lambda: t
    p.st.update({"live_ids": ["6052085"], "live_written_at": "2026-09-27T18:59:30Z"})
    p.live_watchdog()
    assert mail.sent == [] and p.store.health["live-watchdog"]["ok"]            # 30 s: fine
    p.st["live_written_at"] = "2026-09-27T18:57:00Z"
    p.live_watchdog()
    p.live_watchdog()
    assert mail.sent == ["Tifo: live feed stalled 180 s"]                         # once per match
    p.st["live_ids"] = []
    p.live_watchdog()
    assert p.st["stall_alerted"] == {}


def test_live_watchdog_analytics_reads_live_json(tmp_path):
    p = _poller(tmp_path, "analytics")
    mail = _Mail()
    p.mailer = mail
    p.now_fn = lambda: datetime(2026, 9, 27, 19, 10, tzinfo=timezone.utc)
    lj = {"generated": "2026-09-27T19:00:00Z", "matches": [{"id": 1, "status": "live"}, {"id": 2, "status": "finished"}]}
    p.live_watchdog(lj)
    assert len(mail.sent) == 1 and p.an_state["stall_alerted"] == {"1": "2026-09-27T19:10:00Z"}


def test_http_backs_off_after_429():
    import urllib.error
    from sources import http as H
    t = [100.0]
    h = H.Http(clock=lambda: t[0])
    calls = []

    def boom(req, timeout):
        calls.append(req.full_url)
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {}, None)
    orig = H.urllib.request.urlopen
    H.urllib.request.urlopen = boom
    try:
        for _ in range(3):
            try:
                h.get_bytes("https://www.fotmob.com/api/data/matches?date=20260927")
            except H.FetchError:
                pass
        assert len(calls) == 1 and h.failed["www.fotmob.com"] == 3            # no request while backing off
        t[0] += 61
        try:
            h.get_bytes("https://www.fotmob.com/api/data/matches?date=20260927")
        except H.FetchError:
            pass
        assert len(calls) == 2 and h.backoff["www.fotmob.com"][1] == 120        # doubled
        calls.clear()

        def forbid(req, timeout):
            calls.append(req.full_url)
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
        H.urllib.request.urlopen = forbid
        h2 = H.Http(clock=lambda: t[0])
        for _ in range(2):
            try:
                h2.get_bytes("https://data.fotmob.com/stats/530/season/1/rating.json")
            except H.FetchError:
                pass
        assert len(calls) == 2 and not h2.backoff                               # one dead stats URL: no host backoff
    finally:
        H.urllib.request.urlopen = orig


def test_clock_of_live_periods():
    from sources import fotmob as F
    st = {"halfs": {"firstHalfStarted": "27.09.2026 20:01:38", "secondHalfStarted": "27.09.2026 21:08:48"}, "periodLength": 45}
    c = F.clock_of(st, "live")
    assert c == {"period": "2H", "period_start": "2026-09-27T19:08:48Z", "period_base": 45, "period_length": 45}
    assert F.clock_of(st, "ht")["period_start"] is None and F.clock_of(st, "scheduled") == {}


def test_career_dates_in_epoch_ms():
    from compute import insights as IN
    pd = {"careerHistory": {"careerItems": {"senior": {"teamEntries": [
        {"team": "MCO Oujda", "teamId": 102045, "startDate": 1600128000000, "endDate": "", "appearances": None},
        {"team": "X", "teamId": 1, "startDate": "2019-07-01T00:00:00Z", "endDate": None}]}}}}
    c = IN.career(pd)["senior"]
    assert c[0]["start"] == "2020-09-15" and c[0]["end"] is None           # FotMob sent milliseconds (player 1257567)
    assert c[1]["start"] == "2019-07-01"


def test_careers_skips_one_bad_player(tmp_path, monkeypatch):
    import more as MO
    p = _poller(tmp_path, "analytics")
    p.store.put_json("comp/538/stats.json", {"lists": {"goals": [{"player": {"id": 1}}, {"player": {"id": 2}}]}})
    monkeypatch.setattr(MO, "leagues", lambda: [538])
    good = {"name": "Good", "careerHistory": {"careerItems": {"senior": {"teamEntries": [{"teamId": 9, "startDate": "2020-01-01"}]}}}}
    bad = {"name": "Bad", "careerHistory": {"careerItems": {"senior": {"teamEntries": [{"teamId": 9, "startDate": {"odd": 1}}]}}}}
    monkeypatch.setattr(MO.IN, "career", lambda pd: (_ for _ in ()).throw(TypeError("boom")) if pd["name"] == "Bad" else {"senior": [], "national_team": [], "league_seasons": []})
    p.fm.http.get_json = lambda url, min_ttl=0: bad if url.endswith("id=1") else good
    MO.careers(p)
    assert "player/2/career.json" in p.store.written and "player/1/career.json" not in p.store.written
    assert p.store.health["careers"]["ok"] and "1" in p.store.health["careers"]["note"]


def test_team_file_patched_after_full_time(tmp_path):
    p = _poller(tmp_path)
    p.now_fn = lambda: datetime(2026, 9, 27, 21, 40, tzinfo=timezone.utc)
    fx = {"id": 6052085, "status": "live", "minute": "1", "score": {"home": 0, "away": 2}, "status_detail": None, "penalties": None}
    p.store.put_json("team/5789.json", {"id": 5789, "fixtures": [dict(fx)]})
    p.store.put_json("national/5789/team.json", {"id": 5789, "fixtures": [dict(fx, status="scheduled", score=None, minute=None)]})
    p.store.put_json("match/6052085.json", {"id": 6052085, "status": "finished", "status_detail": "FT",
                                            "score": {"home": 0, "away": 3}, "penalties": None})
    p.st["schedule"] = {"6052085": {"ko": "2026-09-27T18:00:00Z", "comp": 329, "status": "finished", "h": 5824, "a": 5789}}
    p.patch_team_files()                                               # the sweep finds it (finished < 24 h ago)
    for path in ("team/5789.json", "national/5789/team.json"):
        f = p.store.get_json(path)["fixtures"][0]
        assert (f["status"], f["score"], f["minute"]) == ("finished", {"home": 0, "away": 3}, None)
    assert "6052085" in p.st["team_settled"] and not p.st["team_patch"]


def test_status_change_queues_team_patch_and_settle(tmp_path):
    p = _poller(tmp_path)
    p.now_fn = lambda: datetime(2026, 9, 27, 18, 1, tzinfo=timezone.utc)
    m = {"id": 7, "comp": 329, "kickoff_utc": "2026-09-27T18:00:00Z", "status": "scheduled", "home": {"id": 1}, "away": {"id": 2}}
    p.remember_schedule([m])
    assert not p.st.get("team_patch")
    p.remember_schedule([dict(m, status="live")])
    assert "7" in p.st["team_patch"]
    p.store.put_json("match/7.json", {"status": "live", "status_detail": None, "score": {"home": 1, "away": 0}, "penalties": None})
    out = p.settle_fixtures([{"id": 7, "status": "scheduled", "minute": "1", "score": None, "period": "1H"}])[0]
    assert out["status"] == "live" and out["score"] == {"home": 1, "away": 0} and out["minute"] is None and "period" not in out


def test_ics_has_url_channel_and_alarm():
    from compute import ics as ICS
    ms = [{"id": 1000021961, "comp": 538, "round": "7", "status": "scheduled", "kickoff_utc": "2026-10-16T13:05:00Z",
           "home": {"name": "Al-Dhafra", "name_ar": "الظفرة"}, "away": {"name": "United FC", "name_ar": "يونايتد"}},
          {"id": 5, "comp": 538, "status": "finished", "kickoff_utc": "2026-09-01T13:05:00Z", "score": {"home": 1, "away": 0},
           "home": {"name": "A"}, "away": {"name": "B"}}]
    seqs = ICS.bump_sequences(ms, {})
    txt = ICS.team_calendar({"name": "x"}, ms, {538: "دوري أدنوك"}, seqs, channels={538: "القناة في الإمارات: أبوظبي الرياضية"})
    flat = txt.replace("\r\n ", "")
    assert "URL:https://tifo.elyoxe.com/m/1000021961/" in flat and "القناة في الإمارات: أبوظبي الرياضية" in flat
    assert flat.count("BEGIN:VALARM") == 1 and "TRIGGER:-PT30M" in flat                  # upcoming only
    assert all(len(line.encode()) <= 75 for line in txt.split("\r\n"))


def test_bump_never_written_empty(tmp_path):
    import analytics as AN
    p = _poller(tmp_path)
    st = {"groups": [{"rows": [{"team": {"id": 1}}]}]}
    AN.comp_tables(p, 47, st, [], "league")
    assert "comp/47/bump.json" not in p.store.written


def test_arab_club_squads_weekly_idle_only(tmp_path):
    p = _poller(tmp_path)
    p.st["team_comps"] = {"101": [536], "102": [519], "103": [47], "102117": [538]}
    done = []
    p.refresh_team = lambda tid: (done.append(tid), p.mark("team", tid))
    ids = p.arab_club_ids()
    assert set(ids) == {101, 102}                          # not the big five, not the focus (538) clubs
    p.dues()["team:102"] = "2026-09-01T00:00:00Z"
    assert p.arab_club_ids()[0] == 101                     # never refreshed first


def test_minimal_match_file_for_upcoming(tmp_path):
    p = _poller(tmp_path)
    p.now_fn = lambda: datetime(2026, 9, 28, 8, 0, tzinfo=timezone.utc)
    p.store.put_json("h2h/1-2.json", {"wins": {"1": 3, "2": 1, "draws": 2}, "matches": [{"id": 9, "score": {"home": 1, "away": 0}}]})
    m = {"id": 77, "status": "scheduled", "kickoff_utc": "2026-09-29T17:30:00Z", "home": {"id": 2}, "away": {"id": 1}}
    far = dict(m, id=78, kickoff_utc="2026-10-20T17:30:00Z")
    p.minimal_match_files([m, far])
    d = p.store.get_json("match/77.json")
    assert d["minimal"] and d["events"] == [] and d["h2h"]["summary"] == {"home_wins": 1, "draws": 2, "away_wins": 3}
    assert p.store.get_json("match/78.json") is None
    p.st["detail_at"] = {"77": "x"}
    p.store.written.clear()
    p.minimal_match_files([dict(m, kickoff_utc="2026-09-29T18:00:00Z")])
    assert "match/77.json" not in p.store.written          # never over a real detail


def test_a_match_fotmob_has_no_data_for_is_noted_rested_and_never_fails_the_feed(tmp_path):
    # 2026-10-05..07: FotMob answered {"error": true, "message": "Data not found"} for 5629268 (MAT Tetouan - Fath Casablanca,
    # a Moroccan cup tie of May); the backfill failed on it every day and the whole feed showed «FAILING match:backfill»
    p = _poller(tmp_path)
    p.now_fn = lambda: datetime(2026, 10, 7, 3, 0, tzinfo=timezone.utc)
    calls = []
    p.fm.match_raw = lambda mid: calls.append(mid) or {"error": True, "message": "Data not found", "matchId": str(mid)}
    p.store.fail("match:backfill", "5629268: match id None")        # what the feed said before
    assert p.fetch_detail(5629268, "backfill") is None
    assert p.store.health["match:backfill"]["ok"] is True and "no data" in p.store.health["match:backfill"]["note"]
    assert "5629268" in p.st["detail_gone"]
    # the backfill skips it for GONE_DAYS (and never counts it as a failure)
    cid = 11840
    p.st["dormant"] = {str(cid): False}
    p.fixture_cache[cid] = [{"id": 5629268, "status": "finished", "kickoff_utc": "2026-05-15T15:00:00Z"}]
    assert p.backfill(5) == 0 and calls == [5629268] and "5629268" not in p.st.get("backfill_bad", {})
    p.now_fn = lambda: datetime(2026, 11, 7, 3, 0, tzinfo=timezone.utc)      # a month on: asked again
    p.backfill(5)
    assert calls == [5629268, 5629268]


def test_match_of_the_week_with_a_club_whose_country_is_unknown(tmp_path, monkeypatch):
    # 2026-10-05..07: «unsupported operand type(s) for *: 'int' and 'NoneType'» — a club known Arab only through the aux
    # country map (team_country None) made the Arab-vs-Arab flag None, and no pick was made for the week
    import extra2 as X2
    p = _poller(tmp_path, "analytics")
    now = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)
    p.now_fn = lambda: now
    m = {"id": 9001, "status": "scheduled", "kickoff_utc": "2026-10-08T16:00:00Z", "round": "5",
         "home": {"id": 102117, "name": "Al-Ain"}, "away": {"id": 777001, "name": "Unknown FC"}, "probs": {"home": 0.5, "away": 0.25}}
    p.comps = [{"id": 538}]
    monkeypatch.setattr(p, "fixtures", lambda cid: [m] if cid == 538 else [])
    monkeypatch.setattr(p, "team_country", lambda tid: {"iso2": "AE"} if tid == 102117 else None)
    monkeypatch.setattr(p, "aux", lambda name: {"777001": {"iso2": "AE"}} if name == "team_country" else {})
    X2.match_of_week(p)
    doc = p.store.get_json("arabs/match-of-week.json")
    assert doc and doc["pick"]["match"] == 9001 and doc["pick"]["arab_vs_arab"] is False
