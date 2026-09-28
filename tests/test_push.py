"""Web push: payload shape, which events are new, dedupe (state marks + DynamoDB claim), VAR, 404/410 cleanup."""
from datetime import datetime, timezone

import push as PUSH

NOW = datetime(2026, 9, 30, 18, 30, tzinfo=timezone.utc)


def _d(status="live", events=(), score=(1, 0)):
    return {"id": 6052086, "status": status, "comp_name_ar": "كأس الخليج", "kickoff_utc": "2026-09-30T17:30:00Z",
            "home": {"id": 5789, "name": "UAE", "name_ar": "الإمارات"}, "away": {"id": 5902, "name": "Qatar", "name_ar": "قطر"},
            "score": {"home": score[0], "away": score[1]} if score else None,
            "periods": {"firstHalfStarted": "2026-09-30T18:20:00Z", **({"gameEnded": "2026-09-30T18:29:00Z"} if status == "finished" else {})},
            "events": list(events)}


GOAL = {"type": "goal", "minute": 23, "added": None, "team": "home", "player": {"id": 1084245, "name": "Julimar"},
        "score": {"home": 1, "away": 0}, "event_id": "6052086-goal-23-0-1084245", "first_seen": "2026-09-30T18:28:00Z"}


def test_goal_payload_shape_arabic_western_digits():
    p = PUSH.payload("goal", _d(), 5789, GOAL, {"1084245": {"ar": "جوليمار"}})
    assert p == {"title": "هدف! الإمارات 1 - 0 قطر", "body": "سجّل جوليمار في الدقيقة 23'", "url": "/m/6052086/",
                 "tag": "m-6052086", "team": 5789}
    assert PUSH.payload("start", _d(), 5902)["title"] == "بدت المباراة"
    end = PUSH.payload("end", _d("finished", score=(2, 1)), 5789)
    assert end["title"] == "انتهت: الإمارات 2 - 1 قطر" and end["body"] == "كأس الخليج"
    pen = PUSH.payload("goal", _d(), 5789, dict(GOAL, type="penalty_goal", added=2, minute=90), {})
    assert pen["body"] == "سجّل Julimar من ركلة جزاء في الدقيقة 90+2'"          # no Arabic name: FotMob's
    import json
    assert not any(c in json.dumps([p, end, pen], ensure_ascii=False) for c in "٠١٢٣٤٥٦٧٨٩")   # Western digits only


def test_events_to_send_new_only_fresh_and_not_disallowed():
    d = _d(events=[GOAL])
    keys = [k for k, _, _ in PUSH.events_to_send(d, d, set(), NOW)]
    assert keys == ["start", "goal:6052086-home-23-1-0"]
    assert PUSH.events_to_send(d, d, set(keys), NOW) == []                          # dedupe: nothing twice
    old = dict(GOAL, first_seen="2026-09-30T17:00:00Z")                             # history (deploy/backfill)
    assert [k for k, *_ in PUSH.events_to_send(_d(events=[old]), _d(events=[old]), {"start"}, NOW)] == []
    var = {"type": "var", "minute": 24, "team": "home", "var_outcome": "goal_disallowed"}
    dv = _d(events=[GOAL, var])
    assert [k for k, *_ in PUSH.events_to_send(dv, dv, {"start"}, NOW)] == []      # VAR took it back: nothing
    fin = _d("finished", events=[GOAL])
    assert [k for k, *_ in PUSH.events_to_send(fin, fin, {"start", "goal:6052086-goal-23-0-1084245"}, NOW)] == ["end"]


def test_scorer_filled_later_is_the_same_goal_and_never_a_placeholder():
    # 6040346, 2026-09-28: «<TBD>» (player id 0) at 19:40:56Z, the name at 19:41:50Z with a new event_id
    tbd = dict(GOAL, player={"id": 0, "name": "<TBD>"}, event_id="6052086-goal-23-0-0")
    d = _d(events=[tbd])
    keys = [k for k, *_ in PUSH.events_to_send(d, d, {"start"}, NOW)]
    assert keys == ["goal:6052086-home-23-1-0"]
    named = dict(GOAL, first_seen="2026-09-30T18:29:00Z")
    dn = _d(events=[named])
    assert PUSH.events_to_send(dn, dn, {"start", *keys}, NOW) == []                 # one push per goal
    assert PUSH.events_to_send(dn, dn, {"start", "goal:6052086-goal-23-0-0"}, NOW) == []   # marks from the old key format
    body = PUSH.payload("goal", d, 5789, tbd, {})["body"]
    assert body == "هدف الإمارات في الدقيقة 23'" and "TBD" not in body
    assert PUSH.payload("goal", d, 5789, dict(tbd, type="penalty_goal"), {})["body"] == "هدف الإمارات من ركلة جزاء في الدقيقة 23'"
    assert PUSH.payload("goal", d, 5789, dict(GOAL, player=None), {})["body"] == "هدف الإمارات في الدقيقة 23'"


class _Table:
    """DynamoDB table stand-in: conditional put on (pk, sk), query, delete."""
    class _Exc(Exception):
        pass

    def __init__(self, subs):
        self.items = {(s["pk"], s["sk"]): s for s in subs}
        self.deleted = []
        cls = type("C", (), {"exceptions": type("E", (), {"ConditionalCheckFailedException": _Table._Exc})})
        self.meta = type("M", (), {"client": cls})

    def put_item(self, Item, ConditionExpression=None):
        k = (Item["pk"], Item["sk"])
        if ConditionExpression and k in self.items:
            raise _Table._Exc()
        self.items[k] = Item

    def delete_item(self, Key):
        self.deleted.append((Key["pk"], Key["sk"]))
        self.items.pop((Key["pk"], Key["sk"]), None)


def _sub(team, n, events=("start", "goal", "end")):
    return {"pk": f"TIFOPUSH#{team}", "sk": f"h{n}", "team": team, "endpoint": f"https://fcm.googleapis.com/fcm/send/{n}",
            "p256dh": "x", "auth": "y", "events": list(events)}


def test_run_jobs_dedupes_across_retries_and_cleans_gone(monkeypatch):
    subs = {"5789": [_sub(5789, 1), _sub(5789, 2), _sub(5789, 3, ("end",))], "5902": [_sub(5902, 1), _sub(5902, 4)]}
    t = _Table([s for v in subs.values() for s in v])
    monkeypatch.setattr(PUSH, "_subs", lambda table, team: subs[str(team)])
    sent = []

    def send(s, data, urgency):
        sent.append((s["endpoint"], data["team"], urgency))
        return "gone" if s["sk"] == "h2" else "ok"
    job = {"match": 6052086, "key": "goal:x", "kind": "goal", "urgency": "high",
           "payloads": {"5789": {"team": 5789}, "5902": {"team": 5902}}}
    rep = PUSH.run_jobs([job], t, send=send)
    # h3 wants only "end"; endpoint 1 follows both teams: one push, not two
    assert [e.split("/")[-1] for e, _, _ in sent] == ["1", "2", "4"] and all(u == "high" for *_, u in sent)
    assert rep[0]["ok"] == 2 and rep[0]["gone"] == 1 and t.deleted == [("TIFOPUSH#5789", "h2")]
    again = PUSH.run_jobs([job], t, send=send)                                      # a retried invoke
    assert again[0]["skipped"] == "already sent" and len(sent) == 3


def test_plan_marks_state_and_invokes_once(tmp_path):
    import poller as P
    from store import Store, LocalBackend
    p = P.Poller(Store(LocalBackend(tmp_path)))
    p.load()
    p.now_fn = lambda: NOW
    calls = []
    d = _d(events=[GOAL])
    jobs = PUSH.plan(p, d, d, invoke=calls.append)
    assert [j["key"] for j in jobs] == ["start", "goal:6052086-home-23-1-0"] and len(calls) == 1
    assert calls[0]["jobs"][1]["payloads"]["5902"]["title"] == "هدف! الإمارات 1 - 0 قطر"
    assert PUSH.plan(p, d, d, invoke=calls.append) == [] and len(calls) == 1          # next pass: no second invoke

    def boom(e):
        raise RuntimeError("throttled")
    d2 = _d(events=[GOAL, dict(GOAL, minute=30, event_id="6052086-goal-30-0-1", score={"home": 2, "away": 0})], score=(2, 0))
    assert PUSH.plan(p, d2, d2, invoke=boom) == []                                  # not marked: retried next pass
    assert [j["key"] for j in PUSH.plan(p, d2, d2, invoke=calls.append)] == ["goal:6052086-home-30-2-0"]


def test_undeliverable_keys_are_deleted_network_errors_kept(monkeypatch):
    subs = [_sub(5789, 1), _sub(5789, 2)]
    t = _Table(subs)
    monkeypatch.setattr(PUSH, "_subs", lambda table, team: subs)
    res = {"h1": "gone", "h2": "error: ConnectionError: reset"}
    job = {"match": 1, "key": "end", "kind": "end", "urgency": "normal", "payloads": {"5789": {"team": 5789}}}
    PUSH.run_jobs([job], t, send=lambda s, d, u: res[s["sk"]])
    assert t.deleted == [("TIFOPUSH#5789", "h1")]
