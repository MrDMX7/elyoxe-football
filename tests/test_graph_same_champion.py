"""graph/load/same_champion.py: a champion list's record of a club (titles, no game) is the club of the games."""
from graph.build import ORDER
from graph.db import Graph
from graph.ids import Registry
from graph.load import same_champion

CLUBS = {1: "Gor Mahia", 2: "AFC Leopards", 3: "Tusker", 4: "Ulinzi Stars"}


def world(tmp_path, clubs=CLUBS):
    G = Graph(str(tmp_path / "t.db"))
    for tid, name in clubs.items():
        G.put("team", {"tid": tid, "name": name, "kind": "club"}, "sch")
        G.xref("team", tid, "sch", f"{name} (Kenya)", "native")
    return G


def comp(G, cid, name, kind="league", country="KE"):
    G.put("competition", {"cid": cid, "name": name, "kind": kind, "country": country}, "x")


def tables(G, cid, years, winner=lambda y: 1 + y % 4, clubs=(1, 2, 3, 4)):
    """a round robin a season: the winner beats everyone, the rest draw"""
    mid = cid * 100000
    for y in years:
        eid = cid * 10000 + y
        G.put("edition", {"eid": eid, "cid": cid, "season": str(y)}, "sch")
        w = winner(y)
        for h in clubs:
            for a in clubs:
                if h != a:
                    mid += 1
                    G.put("match", {"mid": mid, "eid": eid, "date": f"{y}-03-{(mid % 27) + 1:02d}", "home": h, "away": a,
                                    "hs": 2 if h == w else 0, "as_": 2 if a == w else 0}, "sch")


def listed(G, tid, name, cid, years, sid=None, country="Kenya"):
    """a champion list's record: the titles of `years` and no game"""
    G.put("team", {"tid": tid, "name": name, "country": country}, "s365")
    G.xref("team", tid, "s365", sid or tid, "native")
    for y in years:
        eid = cid * 10000 + y
        G.put("edition", {"eid": eid, "cid": cid, "season": str(y)}, "s365")
        G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'champion', 1, ?, 's365')", (eid, tid))


def test_the_lists_record_of_the_same_name_is_the_club_of_the_games(tmp_path):
    G = world(tmp_path)
    comp(G, 50, "kenya"), comp(G, 60, "Premier League")
    tables(G, 50, range(2001, 2009))
    listed(G, 90, "Gor Mahia", 60, (2001, 2005))
    why = []
    assert same_champion.candidates(G.c, explain=why) == [(90, 1)]
    assert why[0].startswith("name ")


def test_a_name_another_source_knows_the_club_by_is_its_name(tmp_path):
    G = world(tmp_path)
    comp(G, 50, "kenya"), comp(G, 60, "Premier League")
    tables(G, 50, range(2001, 2009))
    G.xref("team", 3, "rsssf-name", "kenya|Kenya Breweries", "native")
    listed(G, 90, "Kenya Breweries", 60, (2003, 2007))
    assert same_champion.candidates(G.c) == [(90, 3)]


def test_a_namesake_of_the_country_is_the_club_whatever_the_seasons_of_its_games(tmp_path):
    G = world(tmp_path)
    comp(G, 50, "kenya"), comp(G, 61, "Super League")
    tables(G, 50, range(2001, 2009))
    listed(G, 90, "Tusker", 61, (1990,))                 # a second-division title of a season without a game
    why = []
    assert same_champion.candidates(G.c, explain=why) == [(90, 3)]
    assert why[0].startswith("namesake")


def test_a_namesake_of_another_country_is_another_club(tmp_path):
    G = world(tmp_path)
    comp(G, 50, "kenya"), comp(G, 61, "Liga", country="UG")
    tables(G, 50, range(2001, 2009))
    listed(G, 90, "Tusker", 61, (1990,), country="Uganda")
    assert same_champion.candidates(G.c) == []


def test_the_champion_of_the_tables_under_another_name_is_the_club(tmp_path):
    G = world(tmp_path)
    comp(G, 50, "kenya"), comp(G, 60, "Premier League")
    tables(G, 50, range(2004, 2021))
    listed(G, 90, "K'Ogalo", 60, range(2004, 2021, 4))   # Gor Mahia's five seasons on top, under a nickname
    why = []
    assert same_champion.candidates(G.c, explain=why) == [(90, 1)]
    assert why[0].startswith("table")


def test_three_seasons_on_top_under_another_name_are_not_enough(tmp_path):
    G = world(tmp_path)
    comp(G, 50, "kenya"), comp(G, 60, "Premier League")
    tables(G, 50, range(2001, 2013))
    listed(G, 90, "K'Ogalo", 60, (2004, 2008, 2012))
    assert same_champion.candidates(G.c) == []


def test_a_loose_name_needs_the_club_in_the_seasons_of_the_titles(tmp_path):
    G = world(tmp_path)
    comp(G, 50, "kenya"), comp(G, 60, "Premier League")
    tables(G, 50, range(2001, 2009))
    listed(G, 90, "Ulinzi Stars Nakuru", 60, (2003, 2004))
    listed(G, 91, "Ulinzi Stars Nakuru", 60, (1971, 1972), sid=911)
    assert same_champion.candidates(G.c) == [(90, 4)]


def test_two_clubs_of_the_name_leave_the_record_alone(tmp_path):
    G = world(tmp_path, {**CLUBS, 5: "Tusker"})
    comp(G, 50, "kenya"), comp(G, 60, "Premier League")
    tables(G, 50, range(2001, 2009), clubs=(1, 2, 3, 4, 5))
    listed(G, 90, "Tusker", 60, (2003, 2007))
    why = []
    assert same_champion.candidates(G.c, explain=why) == []
    assert why[0].startswith("AMBIGUOUS")


def test_one_list_never_names_a_club_twice(tmp_path):
    G = world(tmp_path)
    comp(G, 50, "kenya"), comp(G, 60, "Premier League")
    tables(G, 50, range(2001, 2009))
    listed(G, 90, "Gor Mahia", 60, (2001, 2005))
    listed(G, 91, "Gor Mahia FC", 60, (2002, 2006))      # the same list holds both: two numbers, two clubs
    assert same_champion.candidates(G.c) == [(90, 1)]


def test_a_reserve_side_a_national_team_and_a_record_known_alone_are_never_joined(tmp_path):
    G = world(tmp_path)
    comp(G, 50, "kenya"), comp(G, 60, "Premier League")
    tables(G, 50, range(2001, 2009))
    listed(G, 90, "Gor Mahia U20", 60, (2001, 2005))
    listed(G, 91, "Tusker", 60, (2003, 2007), sid=next(iter(same_champion.ALONE_IDS)))
    G.put("team", {"tid": 92, "name": "Ulinzi Stars", "kind": "national"}, "s365")
    G.put("edition", {"eid": 600004, "cid": 60, "season": "2004"}, "s365")
    G.c.execute("insert into honour(eid, kind, rank, tid, src) values(600004, 'champion', 1, 92, 's365')")
    assert same_champion.candidates(G.c) == []


def test_a_record_of_365scores_alone_with_games_of_its_own_is_a_lists_record_unless_the_two_met(tmp_path):
    G = world(tmp_path, {**CLUBS, 7: "Sofapaka"})
    comp(G, 50, "kenya"), comp(G, 60, "Premier League")
    tables(G, 50, range(2001, 2009))
    listed(G, 90, "Gor Mahia", 60, (2001, 2005))
    listed(G, 91, "Tusker", 60, (2003, 2007))
    for i in range(6):                                   # this season's games, filed under the list's records
        G.put("match", {"mid": 900 + i, "eid": 600001, "date": f"2009-05-{i + 1:02d}", "home": 90, "away": 7, "hs": 1, "as_": 0}, "s365")
        G.put("match", {"mid": 950 + i, "eid": 600001, "date": f"2009-06-{i + 1:02d}", "home": 91, "away": 3, "hs": 1, "as_": 0}, "s365")
    assert same_champion.candidates(G.c) == [(90, 1)]    # the list's Tusker played the Tusker of the games: two clubs


def test_the_club_of_the_games_keeps_its_record_and_takes_the_titles(tmp_path):
    G = world(tmp_path)
    comp(G, 50, "kenya"), comp(G, 60, "Premier League")
    tables(G, 50, range(2001, 2009))
    listed(G, 90, "Gor Mahia", 60, (2001, 2005))
    G.c.commit()
    out = same_champion.load(G, Registry(), None)
    assert out["merged"] == 1
    assert G.c.execute("select distinct tid from honour").fetchall() == [(1,)]
    assert not G.c.execute("select 1 from team where tid=90").fetchone()
    assert G.c.execute("select tifo_id from xref where type='team' and source='s365'").fetchall() == [(1,)]


def test_it_runs_before_the_competitions_are_made_one():
    assert ORDER.index("same_club") < ORDER.index("same_champion") < ORDER.index("twins_again") < ORDER.index("same_comp")
