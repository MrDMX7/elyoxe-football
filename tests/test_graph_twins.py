"""graph/load/twins.py: one game held twice after the team merges (same day, same two teams, the same score) is one match."""
from graph.db import Graph
from graph.ids import Registry
from graph.load import twins


def world(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    for tid in (1, 2, 3):
        G.put("team", {"tid": tid, "name": f"T{tid}"}, "fotmob")
    for pid in (10, 11):
        G.put("player", {"pid": pid, "name": f"P{pid}"}, "fotmob")
    return G, Registry()


def test_a_game_held_by_two_sources_is_one_match_with_the_better_sources_record(tmp_path):
    G, reg = world(tmp_path)
    G.put("match", {"mid": 5, "date": "2003-01-10", "home": 1, "away": 2, "hs": 2, "as_": 1}, "rsssf")
    G.put("match", {"mid": 7, "date": "2003-01-10T16:00:00Z", "home": 1, "away": 2, "hs": 2, "as_": 1, "round": "12"}, "fotmob")
    G.xref("match", 5, "rsssf", "uae|2003|1", "rsssf-native")
    G.many("event", [{"mid": 5, "seq": 0, "minute": 9, "type": "goal", "side": "h", "tid": 1, "pid": 10}], "rsssf")
    G.many("event", [{"mid": 7, "seq": 0, "minute": 9, "type": "goal", "side": "h", "tid": 1, "pid": 10},
                     {"mid": 7, "seq": 1, "minute": 50, "type": "goal", "side": "h", "tid": 1, "pid": 11}], "fotmob")
    out = twins.load(G, reg, None)
    assert [r[0] for r in G.c.execute("select mid from match")] == [7]
    assert G.c.execute("select count(*) from event where mid=7").fetchone()[0] == 2           # never a goal counted twice
    assert G.c.execute("select tifo_id from xref where type='match' and source='rsssf'").fetchone() == (7,)
    assert out["merged"] == 1


def test_the_kept_record_takes_what_only_the_other_has(tmp_path):
    G, reg = world(tmp_path)
    G.put("match", {"mid": 5, "date": "2003-01-10", "home": 2, "away": 1, "hs": 1, "as_": 2}, "sch")    # filed the other way round
    G.put("match", {"mid": 6, "date": "2003-01-10", "home": 1, "away": 2, "hs": 2, "as_": 1}, "rsssf")
    G.many("appearance", [{"mid": 5, "pid": 10, "tid": 1, "played": 1}], "sch")
    G.c.execute("insert into match_award values(5, 'motm', 10, 1, NULL, 'official')")
    twins.load(G, reg, None)
    assert [r[0] for r in G.c.execute("select mid from match")] == [6]
    assert G.c.execute("select mid from appearance").fetchall() == [(6,)]
    assert G.c.execute("select mid from match_award").fetchall() == [(6,)]


def test_two_games_on_one_day_with_other_scores_stay_two(tmp_path):
    # Argentina and Uruguay played two games on 15 August 1916, one in each capital
    G, reg = world(tmp_path)
    G.put("match", {"mid": 5, "date": "1916-08-15", "home": 1, "away": 2, "hs": 3, "as_": 1}, "martj42")
    G.put("match", {"mid": 6, "date": "1916-08-15", "home": 2, "away": 1, "hs": 2, "as_": 1}, "martj42")
    assert twins.load(G, reg, None)["merged"] == 0
    assert G.c.execute("select count(*) from match").fetchone()[0] == 2


def test_three_records_of_one_day_are_left_alone(tmp_path):
    G, reg = world(tmp_path)
    for mid, src in ((5, "rsssf"), (6, "sch"), (7, "tm")):
        G.put("match", {"mid": mid, "date": "2003-01-10", "home": 1, "away": 2, "hs": 1, "as_": 0}, src)
    assert twins.load(G, reg, None)["merged"] == 0


def test_what_moves_from_a_record_filed_the_other_way_round_turns_its_sides(tmp_path):
    G, reg = world(tmp_path)
    G.put("match", {"mid": 5, "date": "2003-01-10", "home": 2, "away": 1, "hs": 1, "as_": 2}, "sch")
    G.put("match", {"mid": 6, "date": "2003-01-10", "home": 1, "away": 2, "hs": 2, "as_": 1}, "rsssf")
    G.many("event", [{"mid": 5, "seq": 0, "minute": 9, "type": "goal", "side": "a", "tid": 1, "pid": 10}], "sch")
    G.c.execute("insert into match_coach values(5, 'h', 77, 'sch')")
    twins.load(G, reg, None)
    assert G.c.execute("select mid, side from event").fetchall() == [(6, "h")]
    assert G.c.execute("select mid, side from match_coach").fetchall() == [(6, "a")]
    assert G.c.execute("select count(*) from conflict").fetchone()[0] == 0              # turned first: no false disagreement


def test_a_record_filed_the_other_way_round_with_both_coaches_turns_them_both(tmp_path):
    # the build of 21 Nov 17:32: «UNIQUE constraint failed: match_coach.mid, match_coach.side» swapping h and a in one pass
    G, reg = world(tmp_path)
    G.put("match", {"mid": 5, "date": "2003-01-10", "home": 2, "away": 1, "hs": 1, "as_": 2}, "sch")
    G.put("match", {"mid": 6, "date": "2003-01-10", "home": 1, "away": 2, "hs": 2, "as_": 1}, "rsssf")
    G.c.executemany("insert into match_coach values(5, ?, ?, 'sch')", [("h", 77), ("a", 88)])
    twins.load(G, reg, None)
    assert sorted(G.c.execute("select mid, side, kid from match_coach")) == [(6, "a", 77), (6, "h", 88)]


def test_the_kept_record_takes_the_others_competition_when_only_the_other_is_one_we_publish(tmp_path):
    # Argentina 2-0 Mexico, 2022: Transfermarkt's record (kept, it ranks first) sat in its «FIWC 2021/2022»; the World Cup's
    # record sat in the World Cup 2022, and the season page lost the game and Messi's man of the match with it
    G, reg = world(tmp_path)
    G.put("competition", {"cid": 77, "name": "World Cup"}, "fotmob")
    G.xref("competition", 77, "fotmob", 77, "fotmob-native")
    G.put("competition", {"cid": 900, "name": "FIWC"}, "tm")
    G.put("edition", {"eid": 1, "cid": 77, "season": "2022"}, "fotmob")
    G.put("edition", {"eid": 2, "cid": 900, "season": "2021/2022"}, "tm")
    G.put("match", {"mid": 5, "eid": 1, "date": "2022-11-26", "home": 1, "away": 2, "hs": 2, "as_": 0}, "martj42")
    G.put("match", {"mid": 6, "eid": 2, "date": "2022-11-26", "home": 1, "away": 2, "hs": 2, "as_": 0}, "tm")
    twins.load(G, reg, None)
    assert G.c.execute("select mid, eid from match").fetchall() == [(6, 1)]


def test_a_country_and_its_successor_are_one_side_of_a_game(tmp_path):
    # World Cup 1998: martj42 filed FR Yugoslavia's games as Serbia's, Fjelstul as Yugoslavia's; Euro 1960: FotMob's «Soviet Union»
    G, reg = world(tmp_path)
    for tid, nm in ((20, "Yugoslavia"), (21, "Serbia"), (22, "Iran"), (23, "Soviet Union"), (24, "Russia"), (25, "Yugoslavia"), (26, "Croatia")):
        G.put("team", {"tid": tid, "name": nm, "kind": "national"}, "fotmob")
    G.put("match", {"mid": 30, "date": "1998-06-14", "home": 20, "away": 22, "hs": 1, "as_": 0}, "fjelstul")
    G.put("match", {"mid": 31, "date": "1998-06-14", "home": 21, "away": 22, "hs": 1, "as_": 0}, "martj42")
    G.put("match", {"mid": 32, "date": "1960-07-10", "home": 23, "away": 25, "hs": 2, "as_": 1}, "fotmob")
    G.put("match", {"mid": 33, "date": "1960-07-10", "home": 24, "away": 25, "hs": 2, "as_": 1}, "martj42")
    G.put("match", {"mid": 34, "date": "1999-03-01", "home": 21, "away": 26, "hs": 1, "as_": 1}, "martj42")      # a game of one record
    out = twins.load(G, reg, None)
    assert out["merged"] == 2
    assert sorted(r[0] for r in G.c.execute("select mid from match")) == [30, 32, 34]
