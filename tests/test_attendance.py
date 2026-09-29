"""449: crowds from the ledger (compute/extras.attendance)."""
from compute import extras as EX


def _e(mid, home, away, att, ko="2026-09-01T18:00:00Z"):
    return {"id": mid, "home": home, "away": away, "att": att, "score": {"home": 1, "away": 0}, "ko": ko}


def test_none_below_the_floor_and_zeros_or_missing_ignored():
    assert EX.attendance([_e(1, 10, 20, 5000), _e(2, 20, 10, None), _e(3, 10, 30, 0)]) is None       # 1 real crowd < 5
    assert EX.attendance([]) is None
    assert EX.attendance([_e(i, 10, 20, True) for i in range(6)]) is None                            # a bool is not a crowd


def test_league_average_home_averages_and_biggest_games():
    rows = [_e(1, 10, 20, 40000), _e(2, 10, 30, 20000), _e(3, 20, 10, 9000), _e(4, 30, 20, 1000),
            _e(5, 20, 30, 11000), _e(6, 30, 10, None)]
    a = EX.attendance(rows)
    assert a["matches"] == 5 and a["total"] == 81000 and a["avg"] == 16200
    assert [t["team"] for t in a["teams"]] == [10, 20, 30]                                           # by home average
    assert a["teams"][0] == {"team": 10, "avg": 30000, "max": 40000, "n": 2}
    assert [m["id"] for m in a["top"]][:3] == [1, 2, 5] and a["top"][0]["att"] == 40000
    assert len(EX.attendance(rows, top=2)["top"]) == 2
