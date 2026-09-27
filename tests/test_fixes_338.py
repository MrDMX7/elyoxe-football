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
    full2 = {"events": [dict(e) for e in d2["events"]], "coverage_events": P.coverage_events(d2)}
    p.plan_repoll(d2, full2, "repoll")
    assert "1" not in p.st["repoll"]                       # complete now
    ids = [e["event_id"] for e in full2["events"]]
    assert "1-half-11" in ids and "1-half-12" in ids       # the old event the new copy lacked is kept
    assert next(e for e in full2["events"] if e["event_id"] == "1-goal-10")["first_seen"] == "2026-09-27T17:10:00Z"


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
