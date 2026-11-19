"""news/articles/top.py, «الأكثر قراءة» (spec 2026-11-19 §5): the 10 most read articles of the last 24 hours from the visit
counter (TIFOHIT#<UAE day> / ART#<id>): today's counts and yesterday's, the latter weighed by its share of the 24 hours."""
from datetime import datetime, timezone

from boto3.dynamodb.conditions import Key

from news.articles import top as TOP

LST = [{"id": f"n-{i}", "headline": f"عنوان {i}", "image": {"url": f"https://tifo.elyoxe.com/v1/news/img/n-{i}.jpg"}, "kind": "news",
        "topic": "transfer", "breaking": i == 3} for i in range(15)]


def test_ranked_by_the_last_24_hours_and_only_live_articles():
    today = {"n-1": 5, "n-2": 1, "gone": 50}
    yday = {"n-2": 10, "n-3": 4}
    got = TOP.rank(today, yday, 0.5, LST)                 # half of yesterday falls in the last 24 hours
    assert [(a["id"], a["n"]) for a in got] == [("n-2", 6), ("n-1", 5), ("n-3", 2)]
    assert got[0] == {"id": "n-2", "headline": "عنوان 2", "image": "https://tifo.elyoxe.com/v1/news/img/n-2.jpg", "n": 6,
                      "kind": "news", "topic": "transfer", "breaking": False}


def test_ten_at_most_and_none_before_the_first_count():
    assert len(TOP.rank({f"n-{i}": i + 1 for i in range(15)}, {}, 1.0, LST)) == 10
    assert TOP.rank({}, {}, 1.0, LST) == []


def test_the_share_of_yesterday_and_the_uae_days():
    now = datetime(2026, 11, 19, 2, 0, tzinfo=timezone.utc)                # 06:00 in the UAE: a quarter of the day gone
    assert TOP.days(now) == ("2026-11-19", "2026-11-18", 0.75)


class FakeTable:
    def __init__(self, items):
        self.items, self.calls = items, []

    def query(self, KeyConditionExpression, ExclusiveStartKey=None):
        self.calls.append(KeyConditionExpression)
        return {"Items": [i for i in self.items if i["pk"] == KeyConditionExpression._values[0]._values[1]
                          and i["sk"].startswith("ART#")]}


def test_counts_read_one_day():
    t = FakeTable([{"pk": "TIFOHIT#2026-11-19", "sk": "ART#n-1", "n": 3}, {"pk": "TIFOHIT#2026-11-19", "sk": "N", "n": 99},
                   {"pk": "TIFOHIT#2026-11-18", "sk": "ART#n-1", "n": 7}])
    assert TOP.counts(t, "2026-11-19") == {"n-1": 3}
    assert t.calls[0] == Key("pk").eq("TIFOHIT#2026-11-19") & Key("sk").begins_with("ART#")
