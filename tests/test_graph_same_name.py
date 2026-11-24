"""graph/load/same_name.py: two records of one name in one domestic competition that never met are one club."""
from graph.build import ORDER
from graph.db import Graph
from graph.load import same_name


def test_one_name_in_one_league_is_one_club_and_two_countries_are_two(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    G.put("competition", {"cid": 1, "name": "Ligue 1", "kind": "league", "country": "DZ"}, "x")
    G.put("competition", {"cid": 2, "name": "Champions League", "kind": "cup", "scope": "africa"}, "x")
    G.put("competition", {"cid": 3, "name": "Premier League", "kind": "league", "country": "MW"}, "x")
    for eid in (1, 2, 3):
        G.put("edition", {"eid": eid, "cid": eid, "season": "1990"}, "x")
    for tid, name, src in ((1, "MA Hussein Dey", "rsssf"), (2, "MA Hussein-Dey", "rsssf"), (3, "Rivals", "rsssf"), (4, "Tigers FC", "sch"), (5, "Tigers FC", "sch"),
                           (6, "Twins", "rsssf"), (7, "Twins", "rsssf"), (8, "Alemannia", "tm"), (9, "Alemannia", "fotmob"), (10, "Lions", "x")):
        G.put("team", {"tid": tid, "name": name, "kind": "club"}, src)
    G.put("team", {"tid": 11, "name": "Lions", "kind": "national"}, "x")
    G.xref("team", 9, "fotmob", "900", "native")
    games = ((1, 1, 3), (1, 2, 3), (1, 4, 3), (3, 5, 3), (2, 4, 5), (1, 6, 7), (1, 8, 3), (1, 9, 3), (1, 10, 3), (1, 11, 3))
    for mid, (eid, h, a) in enumerate(games, 1):
        G.put("match", {"mid": mid, "eid": eid, "date": f"1990-03-{mid:02d}", "home": h, "away": a, "hs": 1, "as_": 0}, "x")
    assert same_name.candidates(G.c, era=set(), never=set(), kept=set()) == [(2, 1), (8, 9)]
    assert same_name.load(G, None, None)["merged"] == 2
    assert G.c.execute("SELECT home FROM match WHERE mid IN (2, 7) ORDER BY mid").fetchall() == [(1,), (9,)]


def test_it_runs_once_the_competitions_have_their_countries_and_the_games_are_paired_after():
    assert ORDER.index("comp_meta") < ORDER.index("same_name") < ORDER.index("twins_last") < ORDER.index("tidy")
