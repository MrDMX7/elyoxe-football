"""Tifo analytics: rating, simulator, table tools, clutch, national Elo, tournament bracket."""
import pytest

from compute import extras as EX, national as NA, rating as R, sim as SIM, tables as TB, tournament as TO


def _m(i, h, a, hs, as_, ko, season="2020/2021", comp=538, rnd="1"):
    return {"id": i, "ko": ko, "comp": comp, "season": season, "round": rnd, "h": h, "a": a, "hs": hs, "as": as_, "st": "finished"}


def test_rating_moves_and_probabilities_sum_to_one():
    rows = [_m(1, 1, 2, 3, 0, "2020-09-01"), _m(2, 2, 1, 0, 1, "2020-09-08"), _m(3, 1, 3, 1, 1, "2020-09-15")]
    rat, hist, preds = R.run(rows, {"k": 20, "home": 50})
    assert rat[1] > 1500 > rat[2]
    assert len(hist[1]) == 3 and len(preds) == 3
    for x in preds:
        assert sum(x["p"]) == pytest.approx(1.0)
    ph, pd, pa = R.probs(1600, 1400, {**R.DEFAULTS})
    assert ph > pa and 0 < pd < 0.35
    # neutral venue removes home advantage
    assert R.probs(1500, 1500, {**R.DEFAULTS}, neutral=True)[0] == pytest.approx(R.probs(1500, 1500, {**R.DEFAULTS}, neutral=True)[2])


def test_rating_newcomer_starts_below_base():
    rows = [_m(1, 1, 2, 1, 0, "2019-09-01", "2019/2020"), _m(2, 1, 9, 1, 0, "2020-09-01", "2020/2021")]
    rat, hist, _ = R.run(rows, {"newcomer": 1350})
    assert hist[9][0][1] < 1350        # started at 1350, then lost


def test_brier_bounds():
    assert R.brier([{"p": (1, 0, 0), "outcome": 0}]) == 0
    assert R.brier([{"p": (0, 0, 1), "outcome": 0}]) == 2


def test_sim_is_seeded_and_consistent():
    rows = [{"team": {"id": t}, "pts": p, "gd": 0} for t, p in ((1, 30), (2, 10), (3, 9), (4, 0))]
    rem = [(1, 2, False), (3, 4, False), (2, 3, False)]
    a = SIM.simulate(rows, rem, {1: 1500, 2: 1500, 3: 1500, 4: 1500}, {}, n=2000, seed=7,
                     legend=[{"label": "Relegation", "key": "relegation", "ranks": [4]}])
    b = SIM.simulate(rows, rem, {1: 1500, 2: 1500, 3: 1500, 4: 1500}, {}, n=2000, seed=7,
                     legend=[{"label": "Relegation", "key": "relegation", "ranks": [4]}])
    assert a == b
    assert a["teams"]["1"]["title"] == 1.0                  # 30 points, nobody can reach it
    assert a["teams"]["4"]["relegation"] > 0.9
    for t in a["teams"].values():
        assert sum(t["positions"]) == pytest.approx(1.0, abs=1e-3)


def test_scenarios_final_round():
    rows = [{"team": {"id": t}, "pts": p} for t, p in ((1, 10), (2, 9), (3, 7), (4, 3))]
    sc = TB.scenarios(rows, [(1, 2), (3, 4)])
    assert sc["combinations"] == 9
    t1 = sc["teams"]["1"]
    assert t1["best"] == 1 and t1["next_result"]["W"] == {"best": 1, "worst": 1}
    assert sc["teams"]["4"]["best"] >= 3                     # 3 + 3 = 6 < 7, 9
    assert TB.scenarios(rows, [(1, 2)] * 9) is None           # too many games left


def test_live_table_applies_newer_score():
    rows = [{"rank": 1, "team": {"id": 1}, "pts": 4, "gf": 3, "ga": 1, "ongoing": {"match": 99, "home": 1, "away": 2, "hs": 1, "as": 0}},
            {"rank": 2, "team": {"id": 2}, "pts": 3, "gf": 2, "ga": 1, "ongoing": {"match": 99, "home": 1, "away": 2, "hs": 1, "as": 0}}]
    out = TB.live_table(rows, {99: {"home": 1, "away": 2}})         # the away side turned it round
    assert [r["team"]["id"] for r in out] == [2, 1]
    assert out[0]["pts"] == 6 and out[1]["pts"] == 1 and out[0]["rank_before"] == 2


def test_bump_positions():
    def m(i, rd, h, a, hs, as_):
        return {"id": i, "round": str(rd), "status": "finished", "score": {"home": hs, "away": as_},
                "home": {"id": h, "name": str(h)}, "away": {"id": a, "name": str(a)}}
    b = TB.bump([m(1, 1, 1, 2, 1, 0), m(2, 2, 2, 1, 2, 0)])
    assert b["rounds"] == [1, 2] and b["positions"]["1"] == [1, 2] and b["positions"]["2"] == [2, 1]


def test_clutch_counts_goals_and_assists():
    L = {"1": {"id": 1, "home": 10, "away": 20, "score": {"home": 2, "away": 1},
               "goals": [{"m": 10, "side": "home", "type": "goal", "player": 7, "assist": 8},
                         {"m": 50, "side": "away", "type": "goal", "player": 9, "assist": None},
                         {"m": 88, "side": "home", "type": "goal", "player": 7, "assist": 11}]}}
    c = {r["id"]: r for r in EX.clutch(L)["players"]}
    # home won 2-1: each home goal is worth 2 points (without it: 1-1); the away goal is worth nothing (lost anyway)
    assert c[7]["from_goals"] == 4 and c[8]["from_assists"] == 2 and c[11]["from_assists"] == 2
    assert 9 not in c


def test_national_elo_and_names():
    rows = [("2020-01-01", "United Arab Emirates", "Oman", 2, 0, "Gulf Cup", False),
            ("2020-02-01", "Oman", "United Arab Emirates", 1, 1, "Friendly", True)]
    r, _ = NA.elo(rows)
    assert r["United Arab Emirates"] > r["Oman"]
    assert NA.dataset_name("UAE", {"United Arab Emirates"}) == "United Arab Emirates"
    assert NA.k_for("FIFA World Cup qualification") == 40 and NA.k_for("Friendly") == 20


def test_tournament_bracket_resolves_slots():
    def g(letter, ids, pts):
        return {"letter": letter, "rows": [{"team": {"id": t}, "pts": p, "gd": 0} for t, p in zip(ids, pts)]}
    groups = [g("A", [1, 2, 3, 4], [9, 6, 3, 0]), g("B", [5, 6, 7, 8], [9, 6, 3, 0])]
    bracket = [{"stage": "1/2", "ties": [{"home": {"id": 1870, "name": "1A"}, "away": {"id": 1879, "name": "2B"}, "tbd": True},
                                         {"home": {"id": 1871, "name": "1B"}, "away": {"id": 1878, "name": "2A"}, "tbd": True}]},
               {"stage": "final", "ties": [{"home": {"id": None, "name": "Winner SF 1"}, "away": {"id": None, "name": "Winner SF 2"}, "tbd": True}]}]
    res = TO.simulate(groups, [], bracket, {i: 1500 for i in range(1, 9)}, NA.NATIONAL, n=500, seed=1)
    t = res["teams"]
    assert t["1"]["reach_1/2"] == 1.0 and t["3"]["reach_1/2"] == 0.0
    assert sum(t[str(i)]["reach_winner"] for i in (1, 2, 5, 6)) == pytest.approx(1.0)
