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
