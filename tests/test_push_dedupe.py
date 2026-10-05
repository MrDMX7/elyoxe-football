"""Web push never sends an event twice, even when a run dies half-way (item 7, owner 2026-10-06).

2026-10-02..06 the poller timed out at 58 s every minute and never saved its state, so every minute it handed the same goals
to the sender again. These tests run the real poller path (Poller.fetch_detail -> push.plan) minute after minute, kill each
run before its save(), kill the sender in the middle of a send, wipe the poller's memory completely, race two senders, and
re-run the journal's media step after it died; every subscriber gets each event once at most, and never twice."""
import gzip, json, threading
from datetime import datetime, timedelta, timezone

import pytest

import push as PUSH

MID = 6052086
H, A = 9991, 9992
T0 = datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)


class Killed(BaseException):
    """A Lambda timeout: nothing after it runs (not an Exception, so no handler in our code swallows it)."""


class Dynamo:
    """The cards table as the sender uses it: atomic conditional put on (pk, sk), consistent query by pk, delete."""
    class ConditionalCheckFailedException(Exception):
        pass

    def __init__(self, items=()):
        self.items = {(i["pk"], i["sk"]): dict(i) for i in items}
        self.lock = threading.Lock()
        self.before_query = None
        self.meta = type("M", (), {"client": type("C", (), {"exceptions": Dynamo})})

    def put_item(self, Item, ConditionExpression=None):
        with self.lock:
            k = (Item["pk"], Item["sk"])
            if ConditionExpression == "attribute_not_exists(pk)" and k in self.items:
                raise Dynamo.ConditionalCheckFailedException("ConditionalCheckFailedException")
            self.items[k] = dict(Item)

    def query(self, KeyConditionExpression, ConsistentRead=False, ExclusiveStartKey=None):
        pk = KeyConditionExpression.get_expression()["values"][1]
        if self.before_query:
            self.before_query(pk)
        with self.lock:
            return {"Items": [dict(v) for (p, s), v in sorted(self.items.items()) if p == pk]}

    def delete_item(self, Key):
        with self.lock:
            self.items.pop((Key["pk"], Key["sk"]), None)

    def claims(self):
        return sorted(s for p, s in self.items if p == f"TIFOPUSHSENT#{MID}")


def sub(team, name, events=("start", "goal", "end"), quiet=None):
    s = {"pk": f"TIFOPUSH#{team}", "sk": f"{team}-{name}", "team": team, "endpoint": f"https://fcm.googleapis.com/fcm/send/{name}",
         "p256dh": "x", "auth": "y", "events": list(events)}
    if quiet:
        s["quiet"] = quiet
    return s


SUBS = [sub(H, "a"),                                     # home fan, everything
        sub(A, "b", ("goal",)),                          # away fan, goals only
        sub(H, "c"), sub(A, "c"),                        # follows both teams: one push per event, not two
        sub(H, "d", ("start", "goal", "end", "video")),  # home fan who also wants the goal videos
        sub(A, "e", ("goal",), quiet={"s": 0, "e": 23 * 60 + 59, "o": 240})]   # asleep all day: nothing


class Phones:
    """What each endpoint received: [(kind, title)]."""
    def __init__(self):
        self.got = {}
        self.kill_after = None

    def send(self, s, data, urgency):
        if self.kill_after is not None:
            if self.kill_after == 0:
                raise Killed()
            self.kill_after -= 1
        self.got.setdefault(s["endpoint"].rsplit("/", 1)[-1], []).append(data["kind_"])
        return "ok"

    def twice(self):
        return {who: [k for k in set(got) if got.count(k) > 1] for who, got in self.got.items() if len(set(got)) != len(got)}


def sender_for(table, phones):
    """The Lambda elyoxe-football-push, invoked asynchronously: the poller never sees how it ends."""
    def invoke(event):
        jobs = json.loads(json.dumps(event["jobs"]))
        for j in jobs:                                    # tag each payload with what it announces, for the assertions
            for p in j["payloads"].values():
                p["kind_"] = j["kind"] if j["kind"] in ("start", "end") else f"{j['kind']}:{j['key'].split(':')[1].split('#')[0]}"
        try:
            PUSH.run_jobs(jobs, table, send=phones.send, now=NOWBOX[0].timestamp())
        except Killed:
            pass                                          # the sender died mid-send; the poller's invoke had returned long ago
    return invoke


NOWBOX = [T0]


def detail(minute, events=(), score=(0, 0), status="live", ended=None):
    return {"id": MID, "comp": 99999, "status": status, "minute": None if status == "finished" else minute,
            "kickoff_utc": "2026-09-30T18:00:00Z", "home": {"id": H, "name": "Home FC", "name_ar": "الأهلي"},
            "away": {"id": A, "name": "Away FC", "name_ar": "النصر"}, "score": {"home": score[0], "away": score[1]},
            "periods": {"firstHalfStarted": "2026-09-30T18:00:30Z", **({"gameEnded": ended} if ended else {})},
            "events": list(events), "lineups": None}


def goal(minute, h, a, pid=77, name="Omar", added=None):
    return {"type": "goal", "minute": minute, "added": added, "team": "home", "player": {"id": pid, "name": name},
            "score": {"home": h, "away": a}, "event_id": f"{MID}-goal-{minute}-{added or 0}-{pid}"}


TBD = {"id": 0, "name": "<TBD>"}
# minute by minute, as FotMob gave a real match: kickoff, a goal with «<TBD>», the name a minute later (new event_id), the
# minute moved 10' -> 11', a second goal, then full time twice
TIMELINE = [
    (1, detail("1")),
    (11, detail("11", [dict(goal(10, 1, 0, 0), player=TBD)], (1, 0))),
    (12, detail("12", [goal(10, 1, 0)], (1, 0))),
    (13, detail("13", [goal(11, 1, 0)], (1, 0))),
    (30, detail("30", [goal(11, 1, 0), goal(29, 2, 0, 88, "Ali")], (2, 0))),
    (31, detail("31", [goal(11, 1, 0), goal(29, 2, 0, 88, "Ali")], (2, 0))),
    (112, detail(None, [goal(11, 1, 0), goal(29, 2, 0, 88, "Ali")], (2, 0), "finished", "2026-09-30T19:51:00Z")),
    (113, detail(None, [goal(11, 1, 0), goal(29, 2, 0, 88, "Ali")], (2, 0), "finished", "2026-09-30T19:51:00Z")),
]
EXPECTED = {"a": ["start", "goal:1-0", "goal:2-0", "end"], "b": ["goal:1-0", "goal:2-0"], "c": ["start", "goal:1-0", "goal:2-0", "end"],
            "d": ["start", "goal:1-0", "goal:2-0", "end"]}


def run_minute(store, monkeypatch, at, d, invoke, save=False):
    """One poller invocation: load the state, fetch the match (the real fetch_detail, so the event stamps and push.plan run
    as in production), and die before save() unless told otherwise."""
    import poller as P
    NOWBOX[0] = at
    p = P.Poller(store, now_fn=lambda: at)
    p.load()
    monkeypatch.setattr(p.fm, "match_raw", lambda mid: {})
    monkeypatch.setattr(p.fm, "match_from_raw", lambda raw: json.loads(json.dumps(d)))
    monkeypatch.setattr(PUSH, "_invoke", invoke)
    p.fetch_detail(MID, "live" if d["status"] == "live" else "final")
    if save:
        p.save()
    return p


@pytest.fixture
def world(tmp_path, monkeypatch):
    from store import Store, LocalBackend
    monkeypatch.setenv("PUSH_FUNCTION", "elyoxe-football-push")
    store = Store(LocalBackend(tmp_path))
    table, phones = Dynamo(SUBS), Phones()
    return store, table, phones, tmp_path


def test_every_poller_run_dies_before_its_save_and_no_event_goes_out_twice(world, monkeypatch):
    store, table, phones, root = world
    invoke = sender_for(table, phones)
    handed = []
    for minute, d in TIMELINE:
        run_minute(store, monkeypatch, T0 + timedelta(minutes=minute), d, lambda ev: handed.append([j["key"] for j in ev["jobs"]]) or invoke(ev))
        assert not (root / "state" / "poller.json").exists()        # no run ever reached its save()
    assert phones.twice() == {} and phones.got == EXPECTED
    assert "e" not in phones.got                                       # quiet hours
    # the marks written right after each hand-over kept the poller from handing anything over twice
    assert handed == [["start"], ["goal:1-0"], ["goal:2-0"], ["end"]]
    assert table.claims() == ["end", "goal:1-0", "goal:2-0", "start"]


def test_poller_with_no_memory_at_all_still_sends_nothing_twice(world, monkeypatch):
    # worse than 2026-10-02: the poller's marks are lost too (the run died before the hand-over's state write, or state was
    # wiped). It hands the same events over again and again; the sender's claim turns every repeat away.
    store, table, phones, root = world
    invoke = sender_for(table, phones)
    handed = []
    for minute, d in TIMELINE:
        for f in ("push.json", "poller.json"):
            (root / "state" / f).unlink(missing_ok=True)
        run_minute(store, monkeypatch, T0 + timedelta(minutes=minute), d, lambda ev: handed.append([j["key"] for j in ev["jobs"]]) or invoke(ev))
    assert phones.twice() == {} and phones.got == EXPECTED
    assert sum(len(h) for h in handed) > 4                             # repeats were handed over...
    assert table.claims() == ["end", "goal:1-0", "goal:2-0", "start"]  # ...and every one of them lost its claim


def test_the_sender_dies_in_the_middle_of_a_send_and_nobody_gets_it_twice(world, monkeypatch):
    store, table, phones, root = world
    invoke = sender_for(table, phones)
    for i, (minute, d) in enumerate(TIMELINE):
        phones.kill_after = 1 if minute == 30 else None               # the 2-0: one phone gets it, then the Lambda times out
        if minute >= 30:                                               # and from then on the poller remembers nothing either
            for f in ("push.json", "poller.json"):
                (root / "state" / f).unlink(missing_ok=True)
        run_minute(store, monkeypatch, T0 + timedelta(minutes=minute), d, invoke)
    assert phones.twice() == {}
    got_20 = [who for who, g in phones.got.items() if "goal:2-0" in g]
    assert len(got_20) == 1                                            # at most once: the others lost that one goal, nobody got it twice
    assert all(g.count("goal:1-0") == 1 for who, g in phones.got.items() if who != "e")


def test_two_senders_racing_for_one_goal_send_it_once(world):
    store, table, phones, root = world
    gate = threading.Barrier(2, timeout=5)
    first = set()

    def hold(pk):                       # both senders read the claims before either writes one
        if pk.startswith("TIFOPUSHSENT#") and threading.current_thread().name not in first:
            first.add(threading.current_thread().name)
            gate.wait()
    table.before_query = hold
    job = {"match": MID, "key": "goal:1-0", "min": 10, "kind": "goal", "urgency": "high",
           "payloads": {str(H): {"kind_": "goal:1-0"}, str(A): {"kind_": "goal:1-0"}}}
    out = []
    ts = [threading.Thread(target=lambda n=n: out.append(PUSH.run_jobs([dict(job, min=10 + n)], table, send=phones.send)), name=f"s{n}")
          for n in (0, 1)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sorted(r[0].get("skipped", "sent") for r in out) == ["already sent", "sent"]
    assert phones.twice() == {} and table.claims() == ["goal:1-0"]


def test_a_second_goal_at_the_same_score_after_the_first_was_taken_back_is_sent(world):
    # 5181830 Greece v Netherlands, 2026-10-01: a 1-0 at 13' that the feed dropped, the real 1-0 at 23'
    store, table, phones, root = world
    job = lambda m: {"match": MID, "key": "goal:1-0", "min": m, "kind": "goal", "urgency": "high",            # noqa: E731
                     "payloads": {str(H): {"kind_": f"goal:1-0@{m}"}}}
    PUSH.run_jobs([job(13)], table, send=phones.send)
    PUSH.run_jobs([job(14)], table, send=phones.send)                  # the 13' one, moved a minute: the same goal
    PUSH.run_jobs([job(23)], table, send=phones.send)                  # a new goal at the same score
    PUSH.run_jobs([job(23)], table, send=phones.send)
    assert table.claims() == ["goal:1-0", "goal:1-0#2"]
    assert phones.got["a"] == ["goal:1-0@13", "goal:1-0@23"]


def test_claims_written_before_2026_10_06_still_count():
    table = Dynamo([{"pk": f"TIFOPUSHSENT#{MID}", "sk": f"goal:{MID}-home-87-0-2", "ttl": 0}])
    assert PUSH.claim(table, MID, "goal:0-2", 88) is None
    assert PUSH.claim(table, MID, "goal:0-2", 95) == "goal:0-2#2"


def _media_world(tmp_path, monkeypatch):
    from news import media as M
    from store import Store, LocalBackend
    from test_media import KSA_IRQ, TEAMS, PLAYERS, ALIASES, NATIONS
    store = Store(LocalBackend(str(tmp_path)))
    md = json.loads(json.dumps(KSA_IRQ))
    store.put_json("day/20260929.json", {"matches": [{k: md[k] for k in ("id", "comp", "kickoff_utc", "status", "score", "home", "away")}]})
    store.put_json("day/20260930.json", {"matches": []})
    store.put_json(f"match/{md['id']}.json", md)
    store.put_json("teams.json", {"teams": TEAMS})
    clip = {"url": "https://www.youtube.com/shorts/bbbbbbbbbbb", "title": "الهدف الثاني لمنتخبنا الوطني سجله اللاعب عبدالله الحمدان- السعودية 2- العراق 0",
            "desc": "", "at": "2026-09-29T19:11:10Z"}
    feed = {"items": []}
    monkeypatch.setattr(M, "fetch_feeds", lambda chs, prefetched=None, workers=6: ({"yt_ksasports": feed["items"]}, {}))
    monkeypatch.setattr(M, "oembed", lambda vid: {"s": 200, "title": "t", "author": "a"})
    monkeypatch.setattr(M, "load_names", lambda store, nat, cache_dir=None: M.Names(TEAMS, PLAYERS, {}, {}, ALIASES, NATIONS, {329}))
    cfg = {"youtube": [], "media": {"youtube": [{"key": "yt_ksasports", "channel": "UCLo2xigvxv9ksxp78AyCBTw", "name": "القنوات الرياضية السعودية",
                                                 "lang": "ar", "kind": "broadcaster"}]}, "x": {"accounts": []}}
    return M, store, md, clip, feed, cfg


def test_goal_video_goes_once_even_when_the_media_step_dies_after_handing_it_over(tmp_path, monkeypatch):
    M, store, md, clip, feed, cfg = _media_world(tmp_path, monkeypatch)
    ksa, irq = md["home"]["id"], md["away"]["id"]
    table = Dynamo([sub(ksa, "v", ("goal", "video")), sub(irq, "w", ("video",)), sub(ksa, "x", ("goal",))])
    phones = Phones()
    jobs_seen = []

    def push(jobs):
        jobs_seen.append([j["key"] for j in jobs])
        sender_for(table, phones)({"jobs": jobs})
    t = datetime(2026, 9, 29, 19, 5, tzinfo=timezone.utc)
    NOWBOX[0] = t
    assert M.step(store, cfg, t=t, push=push).get("video_push") == {"jobs": 0, "baseline": True}   # first run: records only
    feed["items"] = [clip]                                             # the federation's clip of the 69' goal comes out
    real_put = store.put_state

    def die_on_media_state(name, obj):
        if name == M.STATE:
            raise Killed()
        return real_put(name, obj)
    store.put_state = die_on_media_state
    NOWBOX[0] = t = datetime(2026, 9, 29, 19, 20, tzinfo=timezone.utc)
    with pytest.raises(Killed):                                        # handed over, then the run died before saving its state
        M.step(store, cfg, t=t, push=push)
    store.put_state = real_put
    NOWBOX[0] = t = datetime(2026, 9, 29, 19, 35, tzinfo=timezone.utc)
    assert M.step(store, cfg, t=t, push=push)["video_push"]["jobs"] == 1      # it does not know: hands it over again
    # FotMob moves the goal to 70': the page's goal key changes («70-102»), the media file follows, the score does not
    moved = json.loads(json.dumps(md))
    moved["events"][1]["minute"] = 70
    store.put_json(f"match/{md['id']}.json", moved)
    st = store.get_state(M.STATE)
    st["matches"] = {}                                                 # read the match file again
    store.put_state(M.STATE, st)
    NOWBOX[0] = t = datetime(2026, 9, 29, 19, 50, tzinfo=timezone.utc)
    M.step(store, cfg, t=t, push=push)
    assert jobs_seen == [["video:2-0"], ["video:2-0"], ["video:2-0"]]
    assert phones.twice() == {} and phones.got == {"v": ["video:2-0"], "w": ["video:2-0"]}
    assert sorted(s for p, s in table.items if p.startswith("TIFOPUSHSENT#")) == ["video:2-0"]


def test_old_goal_clips_are_history(tmp_path, monkeypatch):
    M, store, md, clip, feed, cfg = _media_world(tmp_path, monkeypatch)
    jobs_seen = []
    t = datetime(2026, 9, 29, 19, 5, tzinfo=timezone.utc)
    M.step(store, cfg, t=t, push=jobs_seen.append)
    feed["items"] = [clip]
    t = datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc)               # first seen 14 hours after the goal
    assert M.step(store, cfg, t=t, push=jobs_seen.append)["video_push"]["jobs"] == 0 and jobs_seen == []
    assert store.get_state(M.STATE)["video_push"]["done"][str(md["id"])] == ["69-102"]    # never later either


def test_media_step_pushes_nothing_outside_production_or_when_dry(tmp_path, monkeypatch):
    M, store, md, clip, feed, cfg = _media_world(tmp_path, monkeypatch)
    feed["items"] = [clip]
    t = datetime(2026, 9, 29, 19, 20, tzinfo=timezone.utc)
    assert "video_push" not in M.step(store, cfg, t=t)                 # a local store: the default never invokes anything
    assert "video_push" not in M.step(store, cfg, t=t, dry=True, push=lambda j: 1 / 0)
