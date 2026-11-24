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
    assert tidy.load(G, Registry(), None, today=datetime.date(2026, 11, 24)) == {
        "moves_to_itself": 1, "dates_set_right": 1, "dates_dropped": 1, "empty_seasons": 0, "empty_competitions": 0, "births_dropped": 0, "namesakes": 0,
        "referees_joined": 0, "grounds_joined": 0, "coaches_joined": 0}
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
        G.c.execute("INSERT INTO honour(eid, kind, rank, tid, src) VALUES(10, 'champion', 1, ?, ?)", (tid, f"x{tid}"))
    move(G, 1, 1, 1, "2001-01-01", "2000/2001")
    found = integrity.compute(G)
    assert {k: v for k, v in found.items() if v} == {"same_game": 1, "side_plays_itself": 1, "season_of_nothing": 1, "two_champions": 1, "nameless_team": 1,
                                                     "nameless_competition": 1, "competition_of_no_kind": 1, "transfer_to_itself": 1}
    cov = coverage.compute(G)
    assert cov["integrity"] == found and "| same_game |" in coverage.markdown(cov, "2026-11-24")


def test_a_season_of_nothing_leaves_and_one_sources_two_champions_are_no_fault(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    G.put("competition", {"cid": 1, "name": "Cup", "kind": "cup"}, "x")
    for eid in (10, 11, 12):
        G.put("edition", {"eid": eid, "cid": 1, "season": str(1990 + eid)}, "x")
        G.xref("edition", eid, "x", str(eid), "native")
    G.c.execute("UPDATE edition SET note='not held' WHERE eid=12")
    for tid in (1, 2):
        G.c.execute("INSERT INTO honour(eid, kind, rank, tid, src) VALUES(10, 'champion', 1, ?, 'x')", (tid,))
    assert tidy.load(G, Registry(), None)["empty_seasons"] == 1
    assert [e for (e,) in G.c.execute("SELECT eid FROM edition ORDER BY eid")] == [10, 12]
    assert [i for (i,) in G.c.execute("SELECT tifo_id FROM xref WHERE type='edition' ORDER BY 1")] == [10, 12]
    assert not any(integrity.compute(G).values())


def test_a_man_too_young_for_a_game_is_a_namesake_or_his_birth_date_is_wrong(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    G.put("competition", {"cid": 5, "name": "FotMob 11036"}, "x")
    assert [reg.mint("player", "fotmob", i) for i in "abc"] == [1, 2, 3]
    G.put("player", {"pid": 1, "name": "Hassan El Shazly", "born": "1995-02-02"}, "fotmob")
    G.put("player", {"pid": 2, "name": "Young Regular", "born": "2002-01-26"}, "fotmob")
    G.put("player", {"pid": 3, "name": "No Date", "born": "not available"}, "fjelstul")
    G.put("match", {"mid": 1, "date": "1963-11-24", "home": 1, "away": 2, "hs": 1, "as_": 0}, "martj42")
    G.put("match", {"mid": 2, "date": "2019-11-24", "home": 1, "away": 2, "hs": 1, "as_": 0}, "fotmob")
    G.put("match", {"mid": 3, "date": "2013-09-14", "home": 1, "away": 2, "hs": 1, "as_": 0}, "fotmob")
    for mid, pid, src in ((1, 1, "martj42"), (2, 1, "fotmob"), (3, 2, "fotmob")):
        G.c.execute("INSERT INTO appearance(mid, pid, tid, src) VALUES(?,?,1,?)", (mid, pid, src))
    G.c.execute("INSERT INTO event(mid, seq, type, pid, src) VALUES(1, 1, 'goal', 1, 'martj42')")
    out = tidy.load(G, reg, None)
    assert (out["namesakes"], out["births_dropped"], out["empty_competitions"]) == (1, 2, 1)
    other = reg.get("player", "namesake", "1")
    assert G.c.execute("SELECT pid FROM appearance ORDER BY mid").fetchall() == [(other,), (1,), (2,)]
    assert G.c.execute("SELECT pid FROM event").fetchall() == [(other,)]
    assert G.c.execute("SELECT name, born FROM player ORDER BY pid").fetchall() == [
        ("Hassan El Shazly", "1995-02-02"), ("Young Regular", None), ("No Date", None), ("Hassan El Shazly", None)]
    assert integrity.compute(G)["born_after_playing"] == 0


def test_a_referee_or_a_ground_written_twice_is_one(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    assert [reg.mint("referee", "x", i) for i in "abcdef"] == [1, 2, 3, 4, 5, 6]
    assert [reg.mint("stadium", "x", i) for i in "abcdef"] == [1, 2, 3, 4, 5, 6]
    for cid in (1, 2):
        G.put("competition", {"cid": cid, "name": f"C{cid}", "kind": "league"}, "x")
        G.put("edition", {"eid": cid, "cid": cid, "season": "2001"}, "x")
    for rid, name, country in ((1, "Benoit Bastien", None), (2, "Benoît Bastien", "France"), (3, "A Romeo", None), (4, "A. Romeo", None), (5, "B Knight", None), (6, "B. Knight", None)):
        G.put("referee", {"rid": rid, "name": name, "country": country}, "x")
    for sid, name, city in ((1, "Parc des Princes", None), (2, "Parc des Princes", "Paris"), (3, "Markaziy Stadion", "Qarshi (Karshi)"), (4, "Markaziy Stadion", "Namangan"),
                            (5, "Markaziy stadion", "Qarshi"), (6, "Markaziy Stadion", None)):
        G.put("stadium", {"sid": sid, "name": name, "city": city}, "x")
    for mid, eid, rid, sid in ((1, 1, 2, 2), (2, 1, 3, 5), (3, 1, 4, 6), (4, 1, 5, 1), (5, 2, 6, 4)):
        G.put("match", {"mid": mid, "eid": eid, "date": f"2001-03-0{mid}", "home": 1, "away": 2, "hs": 1, "as_": 0, "rid": rid, "sid": sid}, "x")
    assert [reg.mint("coach", "x", i) for i in "abcde"] == [1, 2, 3, 4, 5]
    for kid, name, born in ((1, "Dusan Bajevic", None), (2, "Dušan Bajević", "1948-12-10"), (3, "Gary Smith", None), (4, "Gary Smith", None), (5, "Dušan Bajević", None)):
        G.put("coach", {"kid": kid, "name": name, "born": born}, "x")
    for mid, kid in ((1, 1), (2, 5), (3, 3), (3, 4)):
        G.c.execute("INSERT INTO match_coach(mid, side, kid, src) VALUES(?,?,?,'x')", (mid, "h" if kid != 4 else "a", kid))
    out = tidy.load(G, reg, None)
    assert (out["referees_joined"], out["grounds_joined"], out["coaches_joined"]) == (2, 2, 2)
    assert G.c.execute("SELECT kid, born FROM coach ORDER BY kid").fetchall() == [(1, "1948-12-10"), (3, None), (4, None)]
    assert G.c.execute("SELECT mid, kid FROM match_coach ORDER BY mid, kid").fetchall() == [(1, 1), (2, 1), (3, 3), (3, 4)]
    assert G.c.execute("SELECT rid, name, country FROM referee ORDER BY rid").fetchall() == [(1, "Benoit Bastien", "France"), (3, "A Romeo", None), (5, "B Knight", None), (6, "B. Knight", None)]
    assert G.c.execute("SELECT sid, city FROM stadium ORDER BY sid").fetchall() == [(1, "Paris"), (3, "Qarshi (Karshi)"), (4, "Namangan"), (6, None)]
    assert G.c.execute("SELECT rid, sid FROM match ORDER BY mid").fetchall() == [(1, 1), (3, 3), (3, 6), (5, 1), (6, 4)]


def test_it_is_the_last_pass():
    assert ORDER[-1] == "tidy"
