"""tools/bing_submit.py: Bing's 100 URLs a day (a new site's quota, 2026-10-09) spent on what matters first: the hubs every
day, then today's/tomorrow's Arab matches, then the big leagues, clubs and stars not sent in the last 30 days."""
from tools import bing_submit as B


def test_pick_hubs_daily_then_unsent_in_priority_order_within_the_quota():
    pri = [("hub", ["/", "/today/"]), ("match", ["/m/1/", "/m/2/"]), ("league", ["/c/a/", "/c/b/"]), ("star", ["/p/9/"])]
    sent = {"/c/a/": "2026-10-08", "/m/1/": "2026-09-01"}
    got = B.pick(pri, sent, today="2026-10-09", quota=5)
    assert got == ["/", "/today/", "/m/1/", "/m/2/", "/c/b/"]           # /c/a/ went yesterday; /m/1/ more than 30 days ago
    assert B.pick(pri, {}, today="2026-10-09", quota=3) == ["/", "/today/", "/m/1/"]
    assert len(B.pick([("x", [f"/p/{i}/" for i in range(500)])], {}, "2026-10-09", 100)) == 100


def test_the_transfer_pages_go_to_bing(monkeypatch):
    """Owner 2026-10-10 item 5: the transfer market's pages (daily: the market and the rumours change every day; the tracked
    leagues' pages and the lists after the matches)."""
    monkeypatch.setattr(B, "_get", lambda p: {"competitions": [{"id": 536, "key": "saudi-pro-league"}]} if p == "index.json" else {})
    pri = dict(B.priorities(__import__("datetime").date(2026, 10, 10)))
    assert "/transfers/" in pri["hub"] and "/transfers/rumours/" in pri["hub"]
    assert "/transfers/saudi-pro-league/" in pri["transfers"] and "/transfers/free-agents/" in pri["transfers"]
    assert list(dict(B.priorities(__import__("datetime").date(2026, 10, 10)))).index("transfers") == 2   # after today's matches
