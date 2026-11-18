# tests/test_articles_queue.py (news/articles/desk_queue.py)
"""news/articles/desk_queue.py: 20 minutes in the queue, the desk's «ارفض» and «اكتب», 60 a day, updates at most hourly."""
from datetime import datetime, timedelta, timezone
from news.articles import desk_queue as Q

CFG = {"daily": 60, "wait_minutes": 20}
T0 = datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)


def q(state, desk=None, now=T0):
    return Q.Queue(state, desk or {}, now, CFG)


def test_a_story_waits_twenty_minutes_then_is_ready():
    st = {}
    q(st).offer("s1", [3, 1])
    assert q(st, now=T0 + timedelta(minutes=19)).ready() == []
    assert q(st, now=T0 + timedelta(minutes=21)).ready() == ["s1"]


def test_the_bigger_story_goes_first():
    st = {}
    q(st).offer("small", [1, 0, 0, 5.0]); q(st).offer("big", [4, 3, 2, 1.0])
    assert q(st, now=T0 + timedelta(minutes=21)).ready() == ["big", "small"]


def test_reject_stops_it_and_write_skips_the_wait():
    st = {}
    q(st).offer("s1", [1]); q(st).offer("s2", [1])
    desk = {"reject": {"s1": T0.isoformat()}, "write": {"s2": T0.isoformat()}}
    assert q(st, desk, now=T0 + timedelta(minutes=1)).ready() == ["s2"]


def test_the_61st_story_of_the_day_waits_even_with_write():
    st = {}
    first = q(st)
    for i in range(61):
        first.offer(f"s{i}", [i])
    later = q(st, {"write": {"s0": T0.isoformat()}}, now=T0 + timedelta(minutes=30))
    got = later.ready()
    assert len(got) == 60 and got[0] == "s0"
    for sid in got:
        later.mark_written(sid, 1, None)
    assert later.written_today() == 60 and later.ready() == []


def test_a_story_that_left_the_journal_window_leaves_the_queue():
    st = {}
    q(st).offer("old", [1]); q(st).offer("new", [1])
    qq = q(st, now=T0 + timedelta(minutes=21)); qq.prune({"new"})
    assert qq.ready() == ["new"]


def test_an_update_needs_two_new_items_or_a_higher_stage_and_an_hour():
    st = {}
    qq = q(st); qq.offer("s1", [1]); qq.mark_written("s1", 3, "rumour")
    assert not q(st, now=T0 + timedelta(minutes=90)).wants_update("s1", 4, "rumour")       # one new item
    assert not q(st, now=T0 + timedelta(minutes=30)).wants_update("s1", 5, "rumour")       # under an hour
    assert q(st, now=T0 + timedelta(minutes=90)).wants_update("s1", 5, "rumour")
    assert q(st, now=T0 + timedelta(minutes=90)).wants_update("s1", 3, "agreed")           # the stage rose


def test_done_entries_older_than_three_days_are_dropped():
    st = {}
    qq = q(st); qq.offer("s1", [1]); qq.mark_written("s1", 1, None)
    assert "s1" not in q(st, now=T0 + timedelta(days=4)).n["done"]


# ---- final review, findings 1 and 11
def test_a_failed_story_comes_back_only_when_it_grows_and_at_most_twice():
    st = {}
    qq = q(st); qq.offer("s1", [1], items=3); qq.mark_failed("s1", 3)
    later = q(st, now=T0 + timedelta(hours=2))
    later.offer("s1", [1], items=4)                                  # one new item: not back
    assert "s1" not in later.n["queue"]
    later.offer("s1", [1], items=5)                                  # two new items: one more try
    assert "s1" in later.n["queue"]
    later.mark_failed("s1", 5)
    q(st, now=T0 + timedelta(hours=3)).offer("s1", [1], items=9)     # failed twice: never again
    assert "s1" not in st["news"]["queue"]


def test_a_story_is_updated_three_times_at_most():
    st = {}
    qq = q(st); qq.offer("s1", [1]); qq.mark_written("s1", 2, None)
    for h in (2, 4, 6):
        qh = q(st, now=T0 + timedelta(hours=h)); assert qh.wants_update("s1", 2 * h + 2, None); qh.mark_written("s1", 2 * h + 2, None)
    assert not q(st, now=T0 + timedelta(hours=8)).wants_update("s1", 40, "official")
    assert st["news"]["count"] == 1
