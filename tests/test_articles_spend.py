"""news/articles/spend.py: the month's total and the $180 stop (spec, «Guards»)."""
from datetime import datetime, timezone
from store import Store, LocalBackend
from news.articles import spend as S


def test_cost_counts_cache_reads_and_writes():
    u = {"in": 1_000_000, "out": 1_000_000, "cache_read": 1_000_000, "cache_write": 1_000_000}
    assert S.cost("claude-sonnet-5-5", u) == round(2.0 + 10.0 + 0.10 + 2.50, 6)


def test_the_cap_stops_at_180_and_a_new_month_starts_at_zero(tmp_path):
    st = Store(LocalBackend(tmp_path))
    nov = datetime(2026, 11, 20, tzinfo=timezone.utc)
    sp = S.Spend(st, nov)
    sp.add("claude-sonnet-5-5", {"in": 0, "out": 17_999_000, "cache_read": 0, "cache_write": 0}, "report")   # $179.99
    assert sp.allowed()
    sp.add("claude-sonnet-5-5", {"in": 0, "out": 10_000, "cache_read": 0, "cache_write": 0}, "report")
    assert not sp.allowed() and sp.capped_now()
    sp.save()
    assert not S.Spend(st, nov).allowed()
    assert S.Spend(st, datetime(2026, 12, 1, tzinfo=timezone.utc)).allowed()
