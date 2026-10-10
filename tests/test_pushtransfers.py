"""Owner 2026-10-10 item 12: «انتقالات النادي»: a new move in the season's ledger (v1/transfers/all.json) reaches the
subscribers of both clubs (push kind "transfer"), once, in the day; the first run only learns what is there already."""
from datetime import datetime, timezone

import push
import pushtransfers as PT

# [date, pid, name, from id, from, to id, to, fee, kind, mv, cc, pos]
M1 = ["2026-10-09", 7, "Player", 10, "Bayern", 20, "Arsenal", 50000000, "fee", None, "ENG", None]
M2 = ["2026-10-08", 8, "Free", 2, "Free agent", 20, "Arsenal", None, "free", None, None, None]
M3 = ["2026-09-01", 9, "Old", 10, "Bayern", 30, "Other", None, "loan", None, None, None]
NOON = datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc).timestamp()          # 12:00 in the UAE


def test_the_kind_is_known_to_the_sender():
    assert "transfer" in push.EVENTS and "transfer" not in push.DEFAULT_EVENTS


def test_new_moves_of_the_sites_teams_only_recent_and_once():
    seen = {PT.move_key(M3)}
    new = PT.new_moves([M1, M2, M3], seen, "2026-10-10", site={10, 20})
    assert [m[1] for m in new] == [7, 8]
    assert PT.new_moves([M1], {PT.move_key(M1)}, "2026-10-10", site={20}) == []
    assert PT.new_moves([["2026-10-01"] + M1[1:]], set(), "2026-10-10", site={20}) == []   # older than 3 days: news, not an alert
    assert PT.new_moves([M1], set(), "2026-10-10", site={99}) == []                      # no site team, no subscriber


def test_a_job_tells_each_club_its_side():
    j = PT.job(M1, names={"20": "أرسنال", "10": "بايرن ميونخ", "7": "لاعب"}, came_true=True)
    assert j["kind"] == "transfer" and j["match"] == "tr-7" and j["key"] == "tr:10-20:2026-10-09"
    to, fr = j["payloads"]["20"], j["payloads"]["10"]
    assert to["title"] == "صفقة أرسنال: لاعب" and "من بايرن ميونخ" in to["body"] and "€50 مليون" in to["body"] and "صدقت" in to["body"]
    assert fr["title"] == "طلع من بايرن ميونخ: لاعب" and "لأرسنال" in fr["body"]
    assert to["url"] == "/p/7/" and to["team"] == 20 and fr["team"] == 10
    free = PT.job(M2, names={"20": "أرسنال"})
    assert list(free["payloads"]) == ["20"] and "لاعب حر" in free["payloads"]["20"]["body"]


def test_only_in_the_day():
    assert PT.daytime(NOON) and not PT.daytime(datetime(2026, 10, 10, 22, 0, tzinfo=timezone.utc).timestamp())   # 2 at night


def test_the_sender_delivers_a_transfer_to_its_subscribers_only():
    class Tab:
        def __init__(self): self.items = {}
        def put_item(self, Item, ConditionExpression=None):
            k = (Item["pk"], Item["sk"])
            if k in self.items: raise Exception("ConditionalCheckFailedException")
            self.items[k] = Item
        def query(self, **kw): return {"Items": []}
    j = dict(PT.job(M1, names={}), urgency="normal")
    sent = []
    subs = [{"pk": "TIFOPUSH#20", "sk": "a", "endpoint": "https://x/1", "events": ["goal", "transfer"]},
            {"pk": "TIFOPUSH#20", "sk": "b", "endpoint": "https://x/2", "events": ["goal"]}]
    push.run_jobs([j], Tab(), send=lambda s, d, u: sent.append(s["sk"]) or "ok", subs_override=subs, now=NOON)
    assert sent == ["a"]
