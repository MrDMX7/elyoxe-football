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


def test_one_name_and_the_same_men_are_one_club_and_a_name_of_one_word_needs_more(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    for tid, name, src in ((1, "Wuhan Three Towns", "fotmob"), (2, "Wuhan Three Towns", "tm"), (3, "Nacional", "fotmob"), (4, "Nacional", "tm"),
                           (5, "FC Odesa", "fotmob"), (6, "FC Odesa", "names"), (7, "Real Bamako", "fotmob"), (8, "Real Bamako", "tm")):
        G.put("team", {"tid": tid, "name": name}, src)
    spell = lambda pid, tid: G.c.execute("INSERT INTO spell(pid, tid, start, src) VALUES(?,?,?,'x')", (pid, tid, "2020"))
    move = lambda pid, tid: G.c.execute("INSERT INTO transfer(pid, from_tid, to_tid, date, src) VALUES(?,?,?,?,'tm')", (pid, 99, tid, "2020-01-01"))
    for pid in (1, 2):
        spell(pid, 1), move(pid, 2), spell(pid, 3), move(pid, 4)
    spell(3, 5), move(3, 6)
    for pid in range(10, 20):
        spell(pid, 7), move(pid + 10, 8)
    spell(30, 7), move(30, 8)
    assert same_name.candidates(G.c, era=set(), never=set(), kept=set()) == [(2, 1), (6, 5)]


def test_a_record_with_no_game_and_no_man_is_the_one_club_of_its_name_unless_the_country_is_against_it(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    G.put("competition", {"cid": 1, "name": "Serie A", "kind": "league", "country": "BR"}, "x")
    G.put("edition", {"eid": 1, "cid": 1, "season": "1990"}, "x")
    for tid, name, country, src in ((1, "Real Brasília", None, "fotmob"), (2, "Real Brasilia", "Brazil", "s365"), (3, "Olaria", None, "fotmob"),
                                    (4, "Olaria", "Brazil", "s365"), (5, "Olaria", None, "wikidata"), (6, "San Pedro", "Ivory Coast", "fotmob"),
                                    (7, "San Pedro", "Guatemala", "s365"), (8, "Rio Branco", None, "fotmob"), (9, "Rio Branco", None, "sch"),
                                    (10, "Rio Branco", "Brazil", "s365"), (11, "Real Brasília B", None, "wikidata")):
        G.put("team", {"tid": tid, "name": name, "country": country}, src)
    for mid, (h, a) in enumerate(((1, 3), (3, 6), (8, 9)), 1):
        G.put("match", {"mid": mid, "eid": 1, "date": f"1990-03-{mid:02d}", "home": h, "away": a, "hs": 1, "as_": 0}, "x")
    assert same_name.candidates(G.c, era=set(), never=set(), kept=set()) == [(2, 1), (4, 3)]


def test_it_runs_once_the_competitions_have_their_countries_and_the_games_are_paired_after():
    assert ORDER.index("comp_meta") < ORDER.index("same_name") < ORDER.index("twins_last") < ORDER.index("tidy")
