"""Web push: payload shape, which events are new, dedupe (state marks + DynamoDB claim), VAR, 404/410 cleanup, subscriber
choices (events, quiet hours). The runs that die half-way are in test_push_dedupe.py."""
import json
from datetime import datetime, timezone

import push as PUSH

NOW = datetime(2026, 9, 30, 18, 30, tzinfo=timezone.utc)


def _d(status="live", events=(), score=(1, 0), minute="24"):
    return {"id": 6052086, "status": status, "comp_name_ar": "كأس الخليج", "kickoff_utc": "2026-09-30T17:30:00Z",
            "home": {"id": 5789, "name": "UAE", "name_ar": "الإمارات"}, "away": {"id": 5902, "name": "Qatar", "name_ar": "قطر"},
            "score": {"home": score[0], "away": score[1]} if score else None, "minute": minute if status == "live" else None,
            "periods": {"firstHalfStarted": "2026-09-30T18:20:00Z", **({"gameEnded": "2026-09-30T18:29:00Z"} if status == "finished" else {})},
            "events": list(events)}


GOAL = {"type": "goal", "minute": 23, "added": None, "team": "home", "player": {"id": 1084245, "name": "Julimar"},
        "score": {"home": 1, "away": 0}, "event_id": "6052086-goal-23-0-1084245", "first_seen": "2026-09-30T18:28:00Z"}


def keys(todo):
    return [k for k, *_ in todo]


def test_goal_payload_shape_arabic_western_digits():
    p = PUSH.payload("goal", _d(), 5789, GOAL, {"1084245": {"ar": "جوليمار"}})
    assert p == {"title": "هدف! الإمارات 1 - 0 قطر", "body": "سجّل جوليمار في الدقيقة 23'", "url": "/m/6052086/",
                 "tag": "m-6052086", "team": 5789}
    assert PUSH.payload("start", _d(), 5902)["title"] == "بدت المباراة"
    end = PUSH.payload("end", _d("finished", score=(2, 1)), 5789)
    assert end["title"] == "انتهت: الإمارات 2 - 1 قطر" and end["body"] == "كأس الخليج"
    pen = PUSH.payload("goal", _d(), 5789, dict(GOAL, type="penalty_goal", added=2, minute=90), {})
    assert pen["body"] == "سجّل Julimar من ركلة جزاء في الدقيقة 90+2'"          # no Arabic name: FotMob's
    assert not any(c in json.dumps([p, end, pen], ensure_ascii=False) for c in "٠١٢٣٤٥٦٧٨٩")   # Western digits only


def test_goal_payload_says_how_it_was_scored_unless_the_line_says_it_already():
    hd = dict(GOAL, how={"key": "header+corner", "ar": "رأسية من ركنية"})
    assert PUSH.payload("goal", _d(), 5789, hd, {"1084245": {"ar": "جوليمار"}})["body"] == "سجّل جوليمار في الدقيقة 23' · رأسية من ركنية"
    pen = dict(GOAL, type="penalty_goal", how={"key": "penalty", "ar": "ضربة جزاء"})
    assert PUSH.payload("goal", _d(), 5789, pen, {})["body"] == "سجّل Julimar من ركلة جزاء في الدقيقة 23'"
    og = dict(GOAL, type="own_goal", how={"key": "own_goal", "ar": "هدف عكسي"})
    assert PUSH.payload("goal", _d(), 5789, og, {})["body"] == "هدف عكسي من Julimar في الدقيقة 23'"


def test_video_payload_opens_the_goal_on_the_match_page():
    v = PUSH.video_payload(_d(), 5902, dict(GOAL, minute=45, added=2), "45+2-1084245", {"1084245": {"ar": "جوليمار"}})
    assert v == {"url": "/m/6052086/#v=45+2-1084245", "tag": "mv-6052086", "team": 5902, "title": "فيديو الهدف نزل",
                 "body": "جوليمار 45+2' · الإمارات 1 - 0 قطر"}
    tbd = PUSH.video_payload(_d(), 5789, dict(GOAL, player={"id": 0, "name": "<TBD>"}), "23-0", {})
    assert tbd["body"].startswith("هدف الإمارات 23'") and "TBD" not in tbd["body"]


def test_total_minute_and_score_keys():
    assert [PUSH.total_minute(x) for x in (67, "67", "45+2", "HT", "90 + 4", None, "x")] == [67, 67, 47, 45, 94, None, None]
    assert PUSH.total_minute(45, 3) == 48
    assert PUSH.score_key("goal", {"home": 2, "away": 1}) == "goal:2-1" and PUSH.score_key("video", {"home": 0, "away": 0}) == "video:0-0"
    assert PUSH.score_key("goal", {"home": None, "away": 1}) is None and PUSH.score_key("goal", None) is None


def test_events_to_send_new_only_fresh_and_not_disallowed():
    d = _d(events=[GOAL])
    todo = PUSH.events_to_send(d, d, set(), NOW)
    assert keys(todo) == ["start", "goal:1-0"] and todo[1][3] == 23
    marks = ["start", "goal:1-0@23"]
    assert PUSH.events_to_send(d, d, marks, NOW) == []                              # dedupe: nothing twice
    old = dict(GOAL, first_seen="2026-09-30T17:00:00Z")                             # history (deploy/backfill)
    assert keys(PUSH.events_to_send(_d(events=[old]), _d(events=[old]), {"start"}, NOW)) == []
    var = {"type": "var", "minute": 24, "team": "home", "var_outcome": "goal_disallowed"}
    dv = _d(events=[GOAL, var])
    assert keys(PUSH.events_to_send(dv, dv, {"start"}, NOW)) == []                 # VAR took it back: nothing
    fin = _d("finished", events=[GOAL])
    assert keys(PUSH.events_to_send(fin, fin, {"start", "goal:6052086-home-23-1-0"}, NOW)) == ["end"]   # a mark of 2026-09-28's format


def test_a_minute_correction_is_the_same_goal_a_later_same_score_after_a_takeback_is_a_new_one():
    # 2026-10-01..06 (the sender's logs): 21 goals claimed twice under a moved minute: 5071384 87'/88' twenty seconds apart,
    # 17 more by one minute, 1000019556 86'/90' by four. 5181830 (Greece v Netherlands): a 1-0 at 13' the feed then dropped
    # (the score back to 0-0), and the real 1-0 at 23'; its 2-2 at 65' went to the VAR, the real 2-2 came at 89'
    d = _d(events=[dict(GOAL, minute=24)], minute="25")
    assert PUSH.events_to_send(d, d, ["start", "goal:1-0@23"], NOW) == []
    d = _d(events=[dict(GOAL, minute=27)], minute="28")
    assert PUSH.events_to_send(d, d, ["start", "goal:1-0@23"], NOW) == []                       # +4: a correction, never a goal
    assert PUSH.events_to_send(d, d, ["start", "goal:1-0@13"], NOW) == []                       # far, but nobody saw it go
    todo = PUSH.events_to_send(d, d, ["start", "goal:1-0@13"], NOW, back=["1-0"])
    assert keys(todo) == ["goal:1-0"] and todo[0][4] is True                                   # seen taken back and far: again
    d = _d(events=[dict(GOAL, minute=17)], minute="18")
    assert PUSH.events_to_send(d, d, ["start", "goal:1-0@13"], NOW, back=["1-0"]) == []         # a flicker and +4: the same
    assert PUSH.takebacks(["goal:1-0@13", "goal:2-0@30"], [], {"home": 1, "away": 0}) == ["2-0"]
    assert PUSH.takebacks(["goal:1-0@13", "goal:2-0@30"], ["2-0"], {"home": 1, "away": 0}) == []    # counted once
    assert PUSH.takebacks(["goal:1-0@13"], [], {"home": 1, "away": 1}) == [] and PUSH.takebacks(["goal:1-0@13"], [], None) == []


def test_a_goal_the_live_minute_left_far_behind_is_history():
    # a run that died before the hand-over keeps the goal's first_seen at "now": the match minute tells it is old news
    d = _d(events=[dict(GOAL, first_seen="2026-09-30T18:29:30Z")], minute="41")
    assert keys(PUSH.events_to_send(d, d, ["start"], NOW)) == []
    d = _d(events=[dict(GOAL, first_seen="2026-09-30T18:29:30Z")], minute="33")
    assert keys(PUSH.events_to_send(d, d, ["start"], NOW)) == ["goal:1-0"]


def test_scorer_filled_later_is_the_same_goal_and_never_a_placeholder():
    # 6040346, 2026-09-28: «<TBD>» (player id 0) at 19:40:56Z, the name at 19:41:50Z with a new event_id
    tbd = dict(GOAL, player={"id": 0, "name": "<TBD>"}, event_id="6052086-goal-23-0-0")
    d = _d(events=[tbd])
    assert keys(PUSH.events_to_send(d, d, {"start"}, NOW)) == ["goal:1-0"]
    named = dict(GOAL, first_seen="2026-09-30T18:29:00Z")
    dn = _d(events=[named])
    assert PUSH.events_to_send(dn, dn, ["start", "goal:1-0@23"], NOW) == []         # one push per goal
    assert PUSH.events_to_send(dn, dn, ["start", "goal:6052086-home-23-1-0"], NOW) == []   # marks from the 09-28 key format
    body = PUSH.payload("goal", d, 5789, tbd, {})["body"]
    assert body == "هدف الإمارات في الدقيقة 23'" and "TBD" not in body
    assert PUSH.payload("goal", d, 5789, dict(tbd, type="penalty_goal"), {})["body"] == "هدف الإمارات من ركلة جزاء في الدقيقة 23'"
    assert PUSH.payload("goal", d, 5789, dict(GOAL, player=None), {})["body"] == "هدف الإمارات في الدقيقة 23'"


def test_goal_the_score_does_not_have_waits():
    # 6040346, 2026-09-28: a «<TBD>» away goal at 49' with score 2-2 while the match stood 2-1
    real = dict(GOAL, minute=49, score={"home": 2, "away": 1}, event_id="x-goal-49-0-1311408")
    ghost = dict(GOAL, minute=49, team="away", player={"id": None, "name": "<TBD>"}, score={"home": 2, "away": 2},
                 event_id="x-goal-49-0-0")
    d = _d(events=[real, ghost], score=(2, 1), minute="50")
    assert keys(PUSH.events_to_send(d, d, {"start"}, NOW)) == ["goal:2-1"]
    d2 = _d(events=[real, ghost], score=(2, 2), minute="50")                        # the score catches up: it goes
    assert keys(PUSH.events_to_send(d2, d2, ["start", "goal:2-1@49"], NOW)) == ["goal:2-2"]


class _Table:
    """DynamoDB table stand-in: conditional put on (pk, sk), query by pk, delete."""
    class _Exc(Exception):
        pass

    def __init__(self, subs=()):
        self.items = {(s["pk"], s["sk"]): s for s in subs}
        self.deleted = []
        cls = type("C", (), {"exceptions": type("E", (), {"ConditionalCheckFailedException": _Table._Exc})})
        self.meta = type("M", (), {"client": cls})

    def put_item(self, Item, ConditionExpression=None):
        k = (Item["pk"], Item["sk"])
        if ConditionExpression and k in self.items:
            raise _Table._Exc()
        self.items[k] = dict(Item)

    def delete_item(self, Key):
        self.deleted.append((Key["pk"], Key["sk"]))
        self.items.pop((Key["pk"], Key["sk"]), None)

    def query(self, KeyConditionExpression, ConsistentRead=False, ExclusiveStartKey=None):
        pk = KeyConditionExpression.get_expression()["values"][1]
        return {"Items": [dict(v) for (p, s), v in sorted(self.items.items()) if p == pk]}


def _sub(team, n, events=("start", "goal", "end"), quiet=None):
    s = {"pk": f"TIFOPUSH#{team}", "sk": f"h{n}", "team": team, "endpoint": f"https://fcm.googleapis.com/fcm/send/{n}",
         "p256dh": "x", "auth": "y", "events": list(events)}
    if quiet:
        s["quiet"] = quiet
    return s


def test_run_jobs_dedupes_across_retries_and_cleans_gone(monkeypatch):
    subs = {"5789": [_sub(5789, 1), _sub(5789, 2), _sub(5789, 3, ("end",))], "5902": [_sub(5902, 1), _sub(5902, 4)]}
    t = _Table([s for v in subs.values() for s in v])
    monkeypatch.setattr(PUSH, "_subs", lambda table, team: subs[str(team)])
    sent = []

    def send(s, data, urgency):
        sent.append((s["endpoint"], data["team"], urgency))
        return "gone" if s["sk"] == "h2" else "ok"
    job = {"match": 6052086, "key": "goal:1-0", "min": 23, "kind": "goal", "urgency": "high",
           "payloads": {"5789": {"team": 5789}, "5902": {"team": 5902}}}
    rep = PUSH.run_jobs([job], t, send=send)
    # h3 wants only "end"; endpoint 1 follows both teams: one push, not two
    assert [e.split("/")[-1] for e, _, _ in sent] == ["1", "2", "4"] and all(u == "high" for *_, u in sent)
    assert rep[0]["ok"] == 2 and rep[0]["gone"] == 1 and t.deleted == [("TIFOPUSH#5789", "h2")]
    again = PUSH.run_jobs([job], t, send=send)                                      # a retried invoke
    assert again[0]["skipped"] == "already sent" and len(sent) == 3
    moved = PUSH.run_jobs([dict(job, min=27)], t, send=send)                        # FotMob moved the goal to 27'
    assert moved[0]["skipped"] == "already sent" and len(sent) == 3
    flicker = PUSH.run_jobs([dict(job, min=27, again=True)], t, send=send)          # «again» but 4 minutes: the same goal
    assert flicker[0]["skipped"] == "already sent" and len(sent) == 3


def test_subscriber_choices_events_video_and_quiet_hours(monkeypatch):
    # 22:30 UTC = 02:30 in the UAE (+240), 01:30 in Riyadh (+180)
    late = datetime(2026, 10, 6, 22, 30, tzinfo=timezone.utc).timestamp()
    night = {"s": 0, "e": 7 * 60, "o": 240}
    subs = [_sub(5789, 1, ("goal",)), _sub(5789, 2, ("start", "goal", "end", "video")), _sub(5789, 3, ("goal", "video"), quiet=night),
            _sub(5789, 4, ("goal",), quiet={"s": 23 * 60, "e": 60, "o": 180}), _sub(5789, 5, ("goal",), quiet={"s": "x"})]
    t = _Table(subs)
    monkeypatch.setattr(PUSH, "_subs", lambda table, team: subs)
    got = []
    send = lambda s, data, urgency: got.append((s["sk"], data["kind"])) or "ok"      # noqa: E731
    goal = {"match": 1, "key": "goal:1-0", "min": 10, "kind": "goal", "urgency": "high", "payloads": {"5789": {"kind": "goal"}}}
    video = {"match": 1, "key": "video:1-0", "min": 10, "kind": "video", "urgency": "normal", "payloads": {"5789": {"kind": "video"}}}
    rep = PUSH.run_jobs([goal, video], t, send=send, now=late)
    assert got == [("h1", "goal"), ("h2", "goal"), ("h4", "goal"), ("h5", "goal"), ("h2", "video")]   # h3 asleep; h4's 23-01 is over
    assert rep[0]["quiet"] == 1 and rep[1]["quiet"] == 1
    assert PUSH.in_quiet({"quiet": {"s": 23 * 60, "e": 7 * 60, "o": 240}}, datetime(2026, 10, 6, 20, 0, tzinfo=timezone.utc).timestamp())
    assert not PUSH.in_quiet({"quiet": {"s": 23 * 60, "e": 7 * 60, "o": 240}}, datetime(2026, 10, 6, 4, 0, tzinfo=timezone.utc).timestamp())
    assert not PUSH.in_quiet({}) and not PUSH.in_quiet({"quiet": {"s": 60, "e": 60}})
    assert PUSH.wants({}, "goal") and not PUSH.wants({}, "video")                    # never chose: kickoff, goals, full time


def test_expired_and_unknown_jobs_are_never_claimed():
    t = _Table()
    old = {"match": 1, "key": "end", "kind": "end", "urgency": "normal", "exp": 100, "payloads": {}}
    assert PUSH.run_jobs([old], t, send=lambda *a: "ok", subs_override=[], now=200)[0]["skipped"] == "expired"
    assert PUSH.run_jobs([dict(old, kind="spam", exp=None)], t, send=lambda *a: "ok", subs_override=[])[0]["skipped"] == "unknown kind"
    assert not t.items


def test_plan_marks_state_and_invokes_once(tmp_path):
    import poller as P
    from store import Store, LocalBackend
    p = P.Poller(Store(LocalBackend(tmp_path)))
    p.load()
    p.now_fn = lambda: NOW
    calls = []
    d = _d(events=[GOAL])
    jobs = PUSH.plan(p, d, d, invoke=calls.append)
    assert [j["key"] for j in jobs] == ["start", "goal:1-0"] and len(calls) == 1 and jobs[1]["min"] == 23
    assert calls[0]["jobs"][1]["payloads"]["5902"]["title"] == "هدف! الإمارات 1 - 0 قطر"
    # the marks are on disk right after the hand-over, before the run's save() (a run that dies later keeps them)
    assert json.loads(__import__("gzip").decompress((tmp_path / "state" / "push.json").read_bytes()))["6052086"]["keys"] == ["start", "goal:1-0@23"]
    assert PUSH.plan(p, d, d, invoke=calls.append) == [] and len(calls) == 1          # next pass: no second invoke

    def boom(e):
        raise RuntimeError("throttled")
    d2 = _d(events=[GOAL, dict(GOAL, minute=30, event_id="6052086-goal-30-0-1", score={"home": 2, "away": 0})], score=(2, 0), minute="31")
    assert PUSH.plan(p, d2, d2, invoke=boom) == []                                  # not marked: retried next pass
    assert [j["key"] for j in PUSH.plan(p, d2, d2, invoke=calls.append)] == ["goal:2-0"]


def test_plan_sees_a_goal_taken_back_and_hands_the_next_one_at_that_score_over(tmp_path):
    import poller as P
    from store import Store, LocalBackend
    p = P.Poller(Store(LocalBackend(tmp_path)))
    p.load()
    calls = []
    at = lambda h, m: datetime(2026, 9, 30, h, m, tzinfo=timezone.utc)                  # noqa: E731
    p.now_fn = lambda: at(18, 30)
    g13 = dict(GOAL, minute=13, first_seen="2026-09-30T18:29:30Z")
    d = _d(events=[g13], minute="14")
    assert [j["key"] for j in PUSH.plan(p, d, d, invoke=calls.append)] == ["start", "goal:1-0"]
    p.now_fn = lambda: at(18, 33)
    d0 = _d(events=[], score=(0, 0), minute="17")                                      # the VAR took it: 0-0
    assert PUSH.plan(p, d0, d0, invoke=calls.append) == [] and p.aux("push")["6052086"]["back"] == ["1-0"]
    p.now_fn = lambda: at(18, 41)
    g23 = dict(GOAL, minute=23, event_id="6052086-goal-23-0-99", first_seen="2026-09-30T18:40:30Z")
    d1 = _d(events=[g23], minute="24")
    jobs = PUSH.plan(p, d1, d1, invoke=calls.append)
    assert [(j["key"], j.get("again")) for j in jobs] == [("goal:1-0", True)]
    assert PUSH.plan(p, d1, d1, invoke=calls.append) == [] and len(calls) == 2              # once


def test_plan_takes_over_the_marks_poller_json_carried(tmp_path):
    import poller as P
    from store import Store, LocalBackend
    p = P.Poller(Store(LocalBackend(tmp_path)))
    p.load()
    p.now_fn = lambda: NOW
    p.st["push_sent"] = {"6052086": {"at": "2026-09-30T18:28:30Z", "keys": ["start", "goal:6052086-home-23-1-0"]}}
    d = _d(events=[GOAL])
    assert PUSH.plan(p, d, d, invoke=lambda e: None) == [] and "push_sent" not in p.st


def test_video_jobs_one_per_goal_keyed_by_the_score():
    md = _d("finished", events=[GOAL], score=(1, 0))
    jobs = PUSH.video_jobs(md, {"23-1084245": GOAL, "50-9": dict(GOAL, score=None)}, {"1084245": {"ar": "جوليمار"}}, now=1000)
    assert [(j["key"], j["kind"], j["min"], j["exp"]) for j in jobs] == [("video:1-0", "video", 23, 1000 + 1800)]
    assert set(jobs[0]["payloads"]) == {"5789", "5902"} and jobs[0]["payloads"]["5789"]["url"] == "/m/6052086/#v=23-1084245"


def test_undeliverable_keys_are_deleted_network_errors_kept(monkeypatch):
    subs = [_sub(5789, 1), _sub(5789, 2)]
    t = _Table(subs)
    monkeypatch.setattr(PUSH, "_subs", lambda table, team: subs)
    res = {"h1": "gone", "h2": "error: ConnectionError: reset"}
    job = {"match": 1, "key": "end", "kind": "end", "urgency": "normal", "payloads": {"5789": {"team": 5789}}}
    PUSH.run_jobs([job], t, send=lambda s, d, u: res[s["sk"]])
    assert t.deleted == [("TIFOPUSH#5789", "h1")]


def test_poller_time_summary():
    from tools.poller_time import summary
    assert summary([]) == {"n": 0}
    s = summary(list(range(1, 101)))
    assert s == {"n": 100, "p50": 50, "p95": 95, "max": 100}
