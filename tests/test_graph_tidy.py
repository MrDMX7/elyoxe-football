"""graph/load/tidy.py: the last pass, and graph/integrity.py: what is left, counted."""
import datetime
import os
import types

from graph import coverage, integrity
from graph.build import ORDER
from graph.db import Graph
from graph.ids import Registry
from graph.load import tidy


def move(G, pid, fr, to, date, season):
    G.c.execute("INSERT INTO transfer VALUES(?,?,?,?,?,?,?,?)", (pid, fr, to, date, season, None, None, "tm"))


def test_a_move_to_the_same_club_leaves_and_a_date_a_millennium_ahead_takes_its_seasons_year(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    move(G, 1, 10, 10, "2014-01-01", "2013/2014")
    move(G, 1, 10, 11, "2015-07-01", "2015/2016")
    move(G, 2, 10, 11, "3026-06-30", "2025/2026")
    move(G, 3, 10, 11, "3026-06-30", None)
    assert tidy.load(G, Registry(), None, today=datetime.date(2026, 11, 24)) == {"moves_to_itself": 1, "dates_set_right": 1, "dates_dropped": 1}
    assert G.c.execute("SELECT pid, date FROM transfer ORDER BY pid").fetchall() == [(1, "2015-07-01"), (2, "2026-06-30")]


def test_a_record_without_a_name_takes_the_one_the_source_gives_elsewhere(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    os.makedirs(tmp_path / "db" / "tm")
    (tmp_path / "db" / "tm" / "player_profiles.csv").write_text("player_id,player_name\n77,Danilo (3)\n78,Known Elsewhere\n", encoding="utf-8")
    (tmp_path / "db" / "tm" / "transfer_history.csv").write_text("player_id,from_team_id,from_team_name,to_team_id,to_team_name\n77,5722,FC Nowhere,9,Big Club\n", encoding="utf-8")
    a, b, c = reg.mint("player", "tm", "77"), reg.mint("player", "tm", "78"), reg.mint("player", "tm", "79")
    G.put("player", {"pid": a}, "tm")
    G.put("player", {"pid": b, "name": "His Own Name"}, "tm")
    G.put("player", {"pid": c}, "tm")
    t, s = reg.mint("team", "tm", "5722"), reg.mint("team", "sch", "Aiglon (Martinique)")
    G.put("team", {"tid": t}, "tm")
    G.put("team", {"tid": s, "kind": "club"}, "sch")
    out = tidy.load(G, reg, types.SimpleNamespace(db=str(tmp_path / "db")))
    assert (out["players_named"], out["clubs_named"]) == (1, 2)
    assert G.c.execute("SELECT name FROM player ORDER BY pid").fetchall() == [("Danilo",), ("His Own Name",), (None,)]
    assert G.c.execute("SELECT name FROM team ORDER BY tid").fetchall() == [("FC Nowhere",), ("Aiglon",)]


def test_what_should_not_be_there_is_counted(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    G.put("competition", {"cid": 1, "name": "Cup", "kind": "cup"}, "x")
    G.put("competition", {"cid": 2, "name": "FotMob 11036"}, "x")
    G.put("edition", {"eid": 10, "cid": 1, "season": "2001"}, "x")
    G.put("edition", {"eid": 11, "cid": 1, "season": "2002"}, "x")
    for tid in (1, 2):
        G.put("team", {"tid": tid, "name": f"T{tid}", "kind": "club"}, "x")
    G.put("team", {"tid": 3}, "x")
    for mid in (1, 2):
        G.put("match", {"mid": mid, "eid": 10, "date": "2001-03-01", "home": 1, "away": 2, "hs": 1, "as_": 0}, "x")
    G.put("match", {"mid": 3, "eid": 10, "date": "2001-03-08", "home": 2, "away": 2, "hs": 1, "as_": 0}, "x")
    for tid in (1, 2):
        G.c.execute("INSERT INTO honour(eid, kind, rank, tid, src) VALUES(10, 'champion', 1, ?, 'x')", (tid,))
    move(G, 1, 1, 1, "2001-01-01", "2000/2001")
    found = integrity.compute(G)
    assert {k: v for k, v in found.items() if v} == {"same_game": 1, "side_plays_itself": 1, "season_of_nothing": 1, "two_champions": 1, "nameless_team": 1,
                                                     "nameless_competition": 1, "competition_of_no_kind": 1, "transfer_to_itself": 1}
    cov = coverage.compute(G)
    assert cov["integrity"] == found and "| same_game |" in coverage.markdown(cov, "2026-11-24")


def test_it_is_the_last_pass():
    assert ORDER[-1] == "tidy"
