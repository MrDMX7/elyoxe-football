"""push.py, kind «article» (spec 2026-11-19-articles-pages-design.md §4): a new article reaches the followers of each club and
player in it once, at most 3 article pushes a UAE day per club or player, quiet hours kept; on by default."""
from datetime import datetime, timezone

import push as PUSH
from test_push import _CapTable, _psub, _sub

NOON = datetime(2026, 11, 19, 8, 0, tzinfo=timezone.utc).timestamp()          # 12:00 in the UAE


def _job(aid, payloads, breaking=False):
    return {"match": f"article:{aid}", "key": "article", "kind": "article", "urgency": "high" if breaking else "normal",
            "exp": NOON + 3 * 3600, "payloads": payloads}


def _pay(aid):
    return {"title": "عنوان", "body": "مقدمة", "url": f"/news/{aid}/", "tag": f"art-{aid}", "kind": "article"}


def test_article_is_on_by_default_for_a_subscription_that_never_saw_the_switch():
    assert PUSH.wants({"events": ["start", "goal", "end"]}, "article")                   # saved before the switch existed
    assert PUSH.wants({"events": ["goal"]}, "article")
    assert PUSH.wants({}, "article")                                                      # never chose: goals, so articles
    assert not PUSH.wants({"events": ["start"]}, "article")                               # «بدون حرق» kept the kickoff only
    assert PUSH.wants({"events": ["goal", "article"], "art": 1}, "article")
    assert not PUSH.wants({"events": ["goal"], "art": 1}, "article")                      # the new page, switch off
    assert not PUSH.wants({"events": ["article"], "art": 1}, "goal")


def test_an_article_goes_out_once_to_each_device(monkeypatch):
    subs = {"TIFOPUSH#5789": [_sub(5789, 1), _sub(5789, 2)], "TIFOPUSH#P15403": [_psub(1, ["goal"])]}
    subs["TIFOPUSH#P15403"][0]["endpoint"] = subs["TIFOPUSH#5789"][0]["endpoint"]       # device 1 follows the club and the player
    monkeypatch.setattr(PUSH, "_subs", lambda table, aud: subs[f"TIFOPUSH#{aud}"])
    t, sent = _CapTable(), []
    job = _job("n-1", {"5789": _pay("n-1"), "P15403": _pay("n-1")})
    rep = PUSH.run_jobs([job], t, send=lambda s, d, u: sent.append((s["endpoint"][-1], d["url"], u)) or "ok", now=NOON)
    assert sorted(sent) == [("1", "/news/n-1/", "normal"), ("2", "/news/n-1/", "normal")] and rep[0]["ok"] == 2
    assert ("TIFOPUSHSENT#article:n-1", "article") in t.items
    again = PUSH.run_jobs([job], t, send=lambda s, d, u: sent.append(1) or "ok", now=NOON)
    assert again[0]["skipped"] == "already sent" and len(sent) == 2


def test_three_article_pushes_a_day_per_club(monkeypatch):
    monkeypatch.setattr(PUSH, "_subs", lambda table, aud: [_sub(5789, 1)])
    t, sent = _CapTable(), []
    jobs = [_job(f"n-{i}", {"5789": _pay(f"n-{i}")}) for i in range(4)]
    rep = PUSH.run_jobs(jobs, t, send=lambda s, d, u: sent.append(d["url"]) or "ok", now=NOON)
    assert sent == ["/news/n-0/", "/news/n-1/", "/news/n-2/"] and rep[3]["capped"] == 1 and rep[3]["ok"] == 0
    tomorrow = NOON + 86400
    PUSH.run_jobs([dict(_job("n-9", {"5789": _pay("n-9")}), exp=tomorrow + 60)], t, send=lambda s, d, u: sent.append(d["url"]) or "ok",
                  now=tomorrow)
    assert sent[-1] == "/news/n-9/"


def test_quiet_hours_and_the_choice_apply_and_breaking_is_urgent(monkeypatch):
    night = datetime(2026, 11, 19, 22, 0, tzinfo=timezone.utc).timestamp()             # 02:00 in the UAE
    subs = [_sub(5789, 1, quiet={"s": 0, "e": 7 * 60, "o": 240}), dict(_sub(5789, 2, ("goal",)), art=1), _sub(5789, 3)]
    monkeypatch.setattr(PUSH, "_subs", lambda table, aud: subs)
    got = []
    job = dict(_job("b-1", {"5789": _pay("b-1")}, breaking=True), exp=night + 600)
    rep = PUSH.run_jobs([job], _CapTable(), send=lambda s, d, u: got.append((s["sk"], u)) or "ok", now=night)
    assert got == [("h3", "high")] and rep[0]["quiet"] == 1
    assert PUSH.JOB_TTL["article"] == 3 * 3600 and "article" in PUSH.EVENTS
