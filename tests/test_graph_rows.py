from graph.ids import Registry
from graph.rows import match_rows

REC = {"id": 900, "date": "2026-08-20T22:00:00.000Z", "comp": 538, "round": "1", "home": [10, "Al Ain", 2], "away": [20, "Al Wahda", 1],
       "stadium": ["Hazza Bin Zayed", "Al Ain"], "referee": "Ali X", "attendance": "12,345",
       "lineups": {"h": {"formation": "4-3-3", "players": [[1, "Keeper", "1", 11, 1, 7.1], [2, "Striker", "9", 115, 1, 8.4], [3, "Bench", "20", None, 0, None], [4, "Sub", "17", None, 0, 6.5]]},
                   "a": {"formation": "4-4-2", "players": [[5, "Away GK", "1", 11, 1, 6.0]]}},
       "events": [[30, "g", "h", 2, "Striker", 4, None], [55, "s", "h", 4, "Sub", 2, "Striker"], [60, "g", "a", 5, "Away GK", None, "own"],
                  [70, "y", "a", 5, "Away GK", None, "Yellow"], [80, "g", "a", 7, "Unknown", None, "pen"], [88, "r", "h", 4, "Sub", None, "YellowRed"]],
       "ps": {"2": {"r": 8.4, "min": 55, "g": 1, "a": 0, "t": 10}}}


def rows():
    return match_rows(REC, 1, Registry())


def test_match_row():
    m = rows()["match"][0]
    assert (m["hs"], m["as_"], m["date"], m["attendance"], m["status"]) == (2, 1, "2026-08-20T22:00:00Z", 12345, "finished")
    assert m["home"] == 1 and m["away"] == 2


def test_appearances_and_minutes():
    ap = {a["pid"]: a for a in rows()["appearance"]}
    assert ap[2]["minutes"] == 55 and ap[2]["goals"] == 1 and ap[2]["rating"] == 8.4 and ap[2]["started"] == 1
    assert ap[4]["played"] == 1 and ap[4]["started"] == 0 and ap[4]["red"] == 1


def test_unused_sub_not_played():
    ap = {a["pid"]: a for a in rows()["appearance"]}
    assert ap[3]["played"] == 0 and ap[3]["minutes"] in (None, 0)


def test_own_goal_not_credited_and_scorer_without_lineup_kept():
    r = rows()
    ap = {a["pid"]: a for a in r["appearance"]}
    assert ap[5]["goals"] == 0
    types = [e["type"] for e in r["event"]]
    assert types == ["goal", "sub", "own_goal", "yellow", "penalty_goal", "second_yellow"]
    assert any(a["pid"] for a in r["appearance"] if a["pid"] not in (1, 2, 3, 4, 5))   # player 7 scored with no lineup row


def test_xref_native():
    x = rows()["xref"]
    assert ("match", 1, "fotmob", "900", "fotmob-native", 1.0) in x


def test_the_lineups_coach_is_the_matchs_coach():
    from graph.ids import Registry
    rec = dict(REC, lineups={"h": dict(REC["lineups"]["h"], coach=[78656, "Cosmin Olăroiu"]), "a": {"formation": "4-4-2", "players": [], "coach": None}})
    reg = Registry()
    rows = match_rows(rec, 1, reg)
    kid = reg.get("coach", "fotmob", 78656)
    assert rows["match_coach"] == [(reg.get("match", "fotmob", 900), "h", kid)]
    assert rows["coach"] == [{"name": "Cosmin Olăroiu", "kid": kid}]


def test_db_matches_compact_keeps_the_coach():
    from db.matches import compact
    raw = {"general": {"matchTimeUTCDate": "2026-08-20T22:00:00.000Z", "parentLeagueId": 538},
           "header": {"teams": [{"id": 10, "name": "Al Ain", "score": 2}, {"id": 20, "name": "Al Wahda", "score": 1}]},
           "content": {"lineup": {"homeTeam": {"formation": "4-3-3", "starters": [{"id": 1, "name": "K", "shirtNumber": "1", "positionId": 11}],
                                               "coach": {"id": 78656, "name": "Cosmin Olăroiu"}},
                                  "awayTeam": {"formation": "4-4-2", "starters": [{"id": 2, "name": "S", "shirtNumber": "9", "positionId": 115}]}}}}
    m = compact(raw, "900")
    assert m["lineups"]["h"]["coach"] == [78656, "Cosmin Olăroiu"] and "coach" not in m["lineups"]["a"]
