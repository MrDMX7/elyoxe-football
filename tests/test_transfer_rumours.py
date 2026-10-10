"""Phase 3 of the transfers (spec docs/superpowers/specs/2026-10-09-transfers-design.md): a lasting rumour ledger from FotMob's
allRumours (with its probability) and the news journal's transfer stories (with their stage), each closed by the season's
moves: «صدقت» when the move happens, «ما صدقت» when its window shuts without it."""
from datetime import date

from db import transfers_world as T


def rum(rid=1, pid=7, fr=10, to=20, day="2026-09-10", prob="Low", value=5000000):
    return {"rumourId": rid, "playerId": pid, "name": "Player", "fromClubId": fr, "fromClub": "A", "toClubId": to, "toClub": "B",
            "transferDate": day + "T10:00:00Z", "probability": prob, "fee": {"localizedFeeText": "transfer_fee", "value": value}}


def raw(*rs):
    return {"transfers": {"allRumours": list(rs)}}


def test_fotmob_rumours_once_each():
    R = T.fotmob_rumours([raw(rum(1), rum(2, pid=8)), raw(rum(1)), None, raw({"rumourId": None})], names={"7": "لاعب"})
    assert sorted(R) == ["fm1", "fm2"]
    assert R["fm1"] == {"pid": 7, "name": "لاعب", "from": [10, "A"], "to": [20, "B"], "seen": "2026-09-10", "prob": "Low", "fee": 5000000, "src": None}


def test_window_end():
    assert [T.window_end(date.fromisoformat(d)).isoformat() for d in ("2026-07-10", "2026-10-09", "2027-01-15", "2027-04-01")] == \
        ["2026-09-30", "2027-02-28", "2027-02-28", "2027-09-30"]


def test_merge_keeps_first_seen_attaches_the_news_and_closes():
    prev = [{"k": "fm1", "pid": 7, "name": "Player", "from": [10, "A"], "to": [20, "B"], "first": "2026-08-01", "last": "2026-08-20", "prob": "Low",
             "fee": None, "stage": None, "stories": [], "out": None}]
    fm = {"fm1": {"pid": 7, "name": "Player", "from": [10, "A"], "to": [20, "B"], "seen": "2026-09-10", "prob": "High", "fee": 5000000},
          "fm3": {"pid": 9, "name": "Nine", "from": [30, "C"], "to": [40, "D"], "seen": "2026-09-12", "prob": "Low", "fee": None}}
    news = [{"player": {"id": 7, "name": "بلاير"}, "stage": "agreed", "stories": [{"id": "s1", "stage": "agreed", "at": "2026-09-11T08:00:00Z", "first": "Fabrizio", "title": "اتفاق"}]},
            {"player": {"id": 11, "name": "إيليفن"}, "stage": "talks", "stories": [{"id": "s2", "stage": "talks", "at": "2026-09-12T08:00:00Z", "first": "Marca", "title": "مفاوضات"}]}]
    moves = [["2026-09-14", 9, "Nine", 30, "C", 40, "D", 3000000, "fee", None, None, None]]
    out = {r["k"]: r for r in T.merge_rumours(prev, fm, news, moves, date(2026, 9, 20))}
    a = out["fm1"]
    assert (a["first"], a["last"], a["prob"], a["fee"], a["stage"], a["out"]) == ("2026-08-01", "2026-09-11", "High", 5000000, "agreed", None)   # its last word: the news on the 11th
    assert a["stories"] == [["s1", "اتفاق", "2026-09-11", "Fabrizio"]] and a["name"] == "بلاير"          # the site's Arabic name
    assert out["fm3"]["out"] == "done" and out["fm3"]["done"] == "2026-09-14"                       # the move happened
    assert out["n11"]["to"] is None and out["n11"]["stage"] == "talks"                             # a news-only rumour


def test_a_rumour_whose_window_shut_without_the_move_did_not_come_true_and_old_ones_go():
    prev = [{"k": "fm5", "pid": 5, "name": "P", "from": [1, "A"], "to": [2, "B"], "first": "2026-07-01", "last": "2026-08-01", "prob": "Low",
             "fee": None, "stage": None, "stories": [], "out": None},
            {"k": "fm6", "pid": 6, "name": "Q", "from": [1, "A"], "to": [2, "B"], "first": "2025-07-01", "last": "2025-08-01", "prob": "Low",
             "fee": None, "stage": None, "stories": [], "out": "no"}]
    out = {r["k"]: r for r in T.merge_rumours(prev, {}, [], [], date(2026, 10, 9))}
    assert out["fm5"]["out"] == "no" and "fm6" not in out                                          # a year after its last word: gone


def test_renewals_and_bare_gossip_are_no_rumours_and_official_came_true():
    """2026-10-09 first run: «أرسنال يخطط لتمديد عقد هافيرتز», «prolonge jusqu'en 2028», Olise «from Bayern to Bayern» showed as
    rumours, and «ينضم لمعسكر الزمالك» (a story tagged rumour, no talks) too; «نادي السيلية يعلن التعاقد» stayed open."""
    fm = {"fm8": {"pid": 8, "name": "Olise", "from": [9823, "Bayern"], "to": [9823, "Bayern"], "seen": "2026-10-09", "prob": "Low", "fee": None}}
    st = lambda i, stage, title: {"id": i, "stage": stage, "at": "2026-10-09T08:00:00Z", "first": "X", "title": title}
    news = [{"player": {"id": 1, "name": "هافيرتز"}, "stage": "rumour", "stories": [st("a", "rumour", "أرسنال يخطط لتمديد عقد هافيرتز")]},
            {"player": {"id": 2, "name": "كامارا"}, "stage": "talks", "stories": [st("b", "talks", "Adama Camara prolonge jusqu'en 2028")]},
            {"player": {"id": 3, "name": "بانزا"}, "stage": "rumour", "stories": [st("c", "rumour", "شيكو بانزا ينضم لمعسكر الزمالك")]},
            {"player": {"id": 4, "name": "البطاط"}, "stage": "official", "stories": [st("d", "official", "نادي السيلية يعلن التعاقد مع اللاعب مصعب البطاط")]},
            {"player": {"id": 5, "name": "ماكتوميناي"}, "stage": "talks", "stories": [st("e", "talks", "Real Madrid eye McTominay as Napoli talks stall")]}]
    out = {r["k"]: r for r in T.merge_rumours([], fm, news, [], date(2026, 10, 9))}
    assert sorted(out) == ["n4", "n5"]
    assert out["n4"]["out"] == "done" and out["n4"]["done"] == "2026-10-09" and out["n5"]["out"] is None


def test_a_fotmob_rumour_keeps_its_source():
    R = T.fotmob_rumours([raw(dict(rum(1), sourceName="Sky Sports"))])
    assert R["fm1"]["src"] == "Sky Sports"
    out = T.merge_rumours([], R, [], [], date(2026, 9, 20))
    assert out[0]["src"] == "Sky Sports"
