"""Phase 1 of the transfers (docs/superpowers/specs/2026-10-09-transfers-design.md): one ledger of every club's moves from
FotMob's teams?id= -> transfers.allTransfers."""
from datetime import date

from db import transfers_world as T


def row(pid=1, day="2026-08-01", fr=10, fr_name="A", to=20, to_name="B", fee=None, **kw):
    x = {"playerId": pid, "name": "Player", "transferDate": day + "T10:00:00Z", "fromClubId": fr, "fromClub": fr_name, "toClubId": to,
         "toClub": to_name, "fee": fee or {"feeText": "free transfer", "localizedFeeText": "transfer_type_free_transfer"},
         "onLoan": False, "contractExtension": False, "marketValue": None, "position": {"label": "DM"}}
    x.update(kw)
    return x


def club(cid, moves, squad=()):
    return {"details": {"id": cid}, "transfers": {"allTransfers": list(moves)},
            "squad": {"squad": [{"title": "midfielders", "members": [{"id": p, "ccode": cc} for p, cc in squad]}]}}


def test_kind_and_fee():
    assert T.kind_of(row(fee={"feeText": "fee", "localizedFeeText": "transfer_fee", "value": 5000000})) == "fee"
    assert T.fee_of(row(fee={"feeText": "fee", "localizedFeeText": "transfer_fee", "value": 5000000})) == 5000000
    assert T.fee_of(row(amountEuroEstimated=1200000)) == 1200000
    assert T.kind_of(row(fee={"feeText": "on loan", "localizedFeeText": "on_loan"}, onLoan=True)) == "loan"
    assert T.kind_of(row()) == "free"
    assert T.kind_of(row(fee={"feeText": "undisclosed", "localizedFeeText": "undisclosed"})) == "undisclosed"
    assert T.kind_of(row(fee={"feeText": "?"}, onLoan=True)) == "loan"              # no known fee text: the loan flag
    assert T.kind_of(row(fee={"feeText": None, "localizedFeeText": None})) == ""
    assert T.kind_of(row(contractExtension=True)) is None                      # an extension is no move


def test_one_row_per_move_newest_first_with_nationality_and_arabic_names():
    m1 = row(pid=1, day="2026-08-01", fr=10, to=20)
    m2 = row(pid=2, day="2026-09-05", fr=20, fr_name="B", to=30, to_name="C", fee={"feeText": "fee", "localizedFeeText": "transfer_fee", "value": 3000000},
             marketValue=2500000)
    ext = row(pid=3, day="2026-09-01", fr=20, to=20, contractExtension=True)
    raws = [club(10, [m1]), club(20, [m1, m2, ext], squad=[(1, "KSA"), (2, "EGY")]), club(30, [m2])]
    L = T.ledger(raws, names={"1": "لاعب واحد", "30": "سي"})
    assert L == [["2026-09-05", 2, "Player", 20, "B", 30, "سي", 3000000, "fee", 2500000, "EGY", "DM"],
                 ["2026-08-01", 1, "لاعب واحد", 10, "A", 20, "B", None, "free", None, "KSA", "DM"]]


def test_window_and_season_start():
    assert [T.window_open(date(2026, m, 15)) for m in (1, 2, 3, 5, 6, 9, 10, 12)] == [True, True, False, False, True, True, False, False]
    assert T.season_since(date(2026, 10, 9)) == "2026-06-01"
    assert T.season_since(date(2027, 2, 1)) == "2026-06-01"
    assert T.season_since(date(2026, 6, 1)) == "2026-06-01"


def test_a_bad_row_or_club_is_skipped_not_fatal():
    raws = [None, {"transfers": None}, club(10, [{"playerId": None}, "x", row(pid=5)])]
    assert [r[1] for r in T.ledger(raws)] == [5]


def test_a_daily_budget_site_clubs_first_then_the_oldest():
    """FotMob answers 429 when pushed (2026-10-09: ~40 clubs a minute with 4 threads), so a run re-fetches at most `budget`
    clubs: the never-cached, then the site's own, then the stalest; a fresh one is never fetched, a stale one past the budget keeps its cache."""
    H = 3600
    ages = {1: 30 * H, 2: None, 3: 50 * H, 4: 2 * H, 5: 90 * H, 6: 25 * H}
    assert T.plan_fetch([1, 2, 3, 4, 5, 6], ages, priority={6}, budget=3, ttl=20 * H) == [2, 6, 5]   # never cached, the site's, the stalest
    assert T.plan_fetch([1, 2, 3, 4, 5, 6], ages, priority=set(), budget=10, ttl=20 * H) == [2, 5, 3, 1, 6]


def test_a_site_team_outside_the_encyclopedia_gets_its_squad_card():
    """276 team pages had no squad on 2026-10-09, most of them national teams (Croatia, Wales…): the daily run already reads
    their FotMob answer, so it writes them the world club card the site's squad fallback reads (world/club/<id>.json)."""
    raw = {"details": {"id": 10155, "name": "Croatia"}, "squad": {"squad": [
        {"title": "Coach", "members": [{"id": 9, "name": "Dalic", "ccode": "CRO"}]},
        {"title": "Keepers", "members": [{"id": 1, "name": "Livakovic", "shirtNumber": 1, "ccode": "CRO"}, {"name": "no id"}]}]}}
    c = T.squad_card(10155, raw, names={"1": "ليفاكوفيتش", "10155": "كرواتيا"})
    assert c == {"id": 10155, "name": "Croatia", "name_ar": "كرواتيا", "squad": [[9, "Dalic", None, "coach", "CRO"], [1, "ليفاكوفيتش", 1, "keepers", "CRO"]]}
    assert T.squad_card(5, {"squad": {"squad": []}}) is None and T.squad_card(5, None) is None
