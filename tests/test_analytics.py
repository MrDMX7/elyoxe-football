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


def test_scenarios_skipped_while_competition_is_live(tmp_path):
    import analytics as AN
    import poller as P
    from store import Store, LocalBackend
    p = P.Poller(Store(LocalBackend(tmp_path)))
    p.load()
    p.st["schedule"] = {"1": {"ko": "2026-09-26T18:00:00Z", "comp": 329, "status": "live", "h": 1, "a": 2}}
    st = {"groups": [{"name": "A", "rows": [{"team": {"id": t}, "pts": 0} for t in (1, 2, 3, 4)]}]}
    AN.comp_tables(p, 329, st, [{"status": "scheduled", "home": {"id": 1}, "away": {"id": 2}}], "tournament")
    assert "comp/329/scenarios.json" not in p.store.written
    p.st["schedule"] = {}
    AN.comp_tables(p, 329, st, [{"status": "scheduled", "home": {"id": 1}, "away": {"id": 2}}], "tournament")
    assert "comp/329/scenarios.json" in p.store.written


def test_coaches_and_fatigue_written(tmp_path, fx):
    import analytics as AN
    import poller as P
    from sources.fotmob import FotMob
    from store import Store, LocalBackend
    p = P.Poller(Store(LocalBackend(tmp_path)), role="analytics")
    p.load()
    st = FotMob().competition_from_raw({"id": 538}, fx("fotmob_league_538.json"), with_leaders=False)["standings"]
    p.store.put_json("comp/538/standings.json", st)
    tid = st["groups"][0]["rows"][0]["team"]["id"]
    p.aux("coaches")[str(tid)] = {"coach": {"id": 1, "name": "C"}, "history": [{"season": "2026/2027", "won": 4, "ppg": 2.6}]}
    p.aux("team_fx")[str(tid)] = [{"id": 9, "comp": 525, "kickoff_utc": "2026-09-20T16:00:00Z", "status": "finished",
                                   "home": {"id": 8}, "away": {"id": tid}, "score": {"home": 1, "away": 1}}]
    AN.coaches_and_fatigue(p)
    assert "comp/538/coaches.json" in p.store.written and "comp/538/fatigue.json" in p.store.written


def test_winprob_curve(fx):
    from compute import winprob as W
    from sources.fotmob import FotMob
    d = FotMob().match_from_raw(fx("fotmob_match_uae_5898782.json"))     # 2-2, away led 0-2 at half-time
    c = W.curve(d["events"], (0.5, 0.25, 0.25))
    assert c[0][1:] == [0.5, 0.25, 0.25]
    for pt in c:
        assert abs(sum(pt[1:]) - 1) < 0.01
    ht = [pt for pt in c if pt[0] == 45][-1]
    assert ht[3] > 0.7                                   # away far ahead at 0-2
    assert c[-1][2] > 0.85                               # 2-2 at 90: draw
    live = W.curve(d["events"], None, upto=30)
    assert live[-1][0] == 30
    lh, la = W.rates((0.6, 0.25, 0.15))
    assert lh > la


def test_danger_fit_recovers_linear_model():
    from compute import danger as DG
    L = {}
    for i in range(150):
        sot, bc, sib, co = i % 7, i % 3, (i % 11) + 2, i % 5
        sot2, bc2, sib2, co2 = (i + 3) % 7, (i + 1) % 3, (i % 9) + 1, (i + 2) % 5
        xg = lambda a, b, c, d: 0.05 + 0.04 * a + 0.25 * b + 0.08 * c  # noqa: E731
        L[str(i)] = {"stats": {"ShotsOnTarget": [sot, sot2], "big_chance": [bc, bc2], "shots_inside_box": [sib, sib2],
                               "corners": [co, co2], "expected_goals": [xg(sot, bc, sib, co), xg(sot2, bc2, sib2, co2)]},
                     "score": {"home": bc, "away": bc2}}
    m = DG.fit([L], min_rows=100)
    assert m["r2_vs_xg"] > 0.99 and abs(m["coef"]["big_chances"] - 0.25) < 0.01
    p = DG.with_proxy_xg({"x": {"stats": {k: v for k, v in L["5"]["stats"].items() if k != "expected_goals"}}}, m)
    assert p["x"]["xg"]["home"] > 0


def _led():
    return {"1": {"id": 1, "ko": "2026-09-01T16:00:00Z", "home": 10, "away": 20, "score": {"home": 2, "away": 1},
                  "goals": [{"m": 10, "side": "away", "type": "goal", "player": 5, "assist": None},
                            {"m": 60, "side": "home", "type": "goal", "player": 7, "assist": 9},
                            {"m": 80, "side": "home", "type": "penalty_goal", "player": 7, "assist": None}],
                  "reds": [[55, None, "away"]],
                  "players": {"7": ["A", "UAE", 10, 7.5, "FW", 24, False, 40, 50], "9": ["B", "BRA", 10, 7.0, "MF", 27, True, 90, None],
                              "5": ["C", "UAE", 20, 6.9, "FW", 22, True, 90, None]}}}


def test_insights_first_goal_dropped_red_subs():
    from compute import insights as IN
    L = _led()
    fg = IN.first_goal(L)
    assert fg["10"]["conceded_first"]["W"] == 1 and fg["10"]["comebacks_won"] == 1
    d = IN.dropped(L)
    assert d["20"]["dropped_from_winning"] == 3 and d["10"]["won_from_losing"] == 3
    ri = IN.red_impact(L)
    assert ri["10"]["11v10"]["W"] == 1 and ri["20"]["10v11"]["L"] == 1
    sb = IN.subs(L)
    assert sb["players"]["7"]["goals"] == 2 and sb["result_changing_sub_goals"] >= 1
    assert IN.dependence(L)["10"]["top1_share"] == 100.0
    lm = IN.local_minutes(L, "UAE")
    assert lm["teams"][10]["national"] == 40 and lm["teams"][10]["foreign"] == 90


def test_score_grid_and_ties():
    from compute import insights as IN
    g = IN.score_grid(1.5, 1.0)
    assert abs(sum(map(sum, g)) - 1) < 0.1 and g[1][1] > g[5][5]
    legs = {1: {"id": 1, "kickoff_utc": "2026-09-01", "status": "finished", "score": {"home": 2, "away": 0},
                "home": {"id": 10}, "away": {"id": 20}},
            2: {"id": 2, "kickoff_utc": "2026-09-08", "status": "scheduled", "score": None, "home": {"id": 20}, "away": {"id": 10}}}
    t = IN.ties([{"stage": "1/8", "ties": [{"matches": [1, 2]}]}], legs)
    assert t[0]["aggregate"] == {"10": 2, "20": 0} and t[0]["needs"]["trailing_needs_to_win_by"] == 3


def test_season_tables_metrics():
    from compute import insights as IN
    rows = [{"id": 1, "ko": "x", "h": 1, "a": 2, "hs": 2, "as": 0}, {"id": 2, "ko": "y", "h": 2, "a": 1, "hs": 1, "as": 1}]
    s = IN.season_tables({"2020/2021": rows})["2020/2021"]
    assert s["champion"] == 1 and s["title_margin"] == 3 and s["goals_per_game"] == 2.0
