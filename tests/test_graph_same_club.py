"""graph/load/same_club.py: two records that hold the same games are one club, whatever their names."""
from graph.build import ORDER
from graph.db import Graph
from graph.ids import Registry
from graph.load import same_club

DAYS = ("2003-01-10", "2003-01-17", "2003-01-24", "2003-01-31")


def world(tmp_path, teams):
    G = Graph(str(tmp_path / "t.db"))
    for tid, name, src in teams:
        G.put("team", {"tid": tid, "name": name, "kind": "club"}, src)
        if src in ("fotmob", "tm"):
            G.xref("team", tid, src, tid, "native")
    return G, Registry()


def season(G, mid, home, away, src, days=DAYS, score=(2, 1)):
    for i, d in enumerate(days):
        G.put("match", {"mid": mid + i, "date": d, "home": home, "away": away, "hs": score[0], "as_": score[1] + i}, src)


def test_two_records_with_the_same_games_are_one_club_and_the_fotmob_record_is_kept(tmp_path):
    # Royal Antwerp under FotMob, «Antwerp» under schochastics: three days, the same side, score and opponent
    G, reg = world(tmp_path, [(1, "Royal Antwerp", "fotmob"), (2, "Gent", "fotmob"), (50, "Antwerp", "sch")])
    season(G, 100, 1, 2, "fotmob", DAYS[:3])
    season(G, 200, 50, 2, "sch", DAYS[:3])
    out = same_club.load(G, reg, None)
    assert out["merged"] == 1 and out["clubs"] == 1
    assert {r[0] for r in G.c.execute("select home from match")} == {1}
    assert not G.c.execute("select 1 from team where tid=50").fetchone()


def test_two_days_are_enough_only_under_one_name(tmp_path):
    G, reg = world(tmp_path, [(1, "Rochdale", "tm"), (2, "Bury", "tm"), (50, "Rochdale AFC", "eng"), (51, "Dale", "sch")])
    season(G, 100, 1, 2, "tm", DAYS[:2])
    season(G, 200, 50, 2, "eng", DAYS[:2])
    season(G, 300, 51, 2, "sch", DAYS[:2])
    assert same_club.candidates(G.c) == [(50, 1)]


def test_the_opponent_held_twice_votes_by_its_name_and_joins_in_the_same_pass(tmp_path):
    # both clubs of the game are held twice: the first join is by the opponent's folded name
    G, reg = world(tmp_path, [(1, "Twente", "fotmob"), (2, "Vitesse", "fotmob"), (50, "FC Twente", "sch"), (51, "Vitesse", "sch")])
    season(G, 100, 1, 2, "fotmob", DAYS[:3])
    season(G, 200, 50, 51, "sch", DAYS[:3])
    assert same_club.candidates(G.c) == [(50, 1), (51, 2)]


def test_two_clubs_of_one_league_playing_the_same_days_stay_two(tmp_path):
    G, reg = world(tmp_path, [(1, "Ajax", "fotmob"), (2, "Feyenoord", "fotmob"), (50, "PSV", "sch"), (51, "Feyenoord", "sch")])
    season(G, 100, 1, 2, "fotmob")
    season(G, 200, 50, 51, "sch", score=(0, 5))
    assert same_club.candidates(G.c) == []


def test_two_records_that_met_are_two_clubs(tmp_path):
    G, reg = world(tmp_path, [(1, "Sporting", "fotmob"), (2, "Braga", "fotmob"), (50, "Sporting B", "sch")])
    season(G, 100, 1, 2, "fotmob", DAYS[:3])
    season(G, 200, 50, 2, "sch", DAYS[:3])
    G.put("match", {"mid": 900, "date": "2004-05-01", "home": 1, "away": 50, "hs": 1, "as_": 0}, "sch")
    assert same_club.candidates(G.c) == []


def test_two_numbers_of_one_source_are_two_clubs_and_never_meet_through_a_third_record(tmp_path):
    # Tigres and Pumas (23 Nov): schochastics' one record agreed with each on other days and would have chained them
    G, reg = world(tmp_path, [(1, "Tigres", "fotmob"), (2, "Pumas", "fotmob"), (3, "America", "fotmob"), (50, "Universidad", "sch")])
    season(G, 100, 1, 3, "fotmob", DAYS)
    season(G, 200, 50, 3, "sch", DAYS)
    late = ("2005-02-01", "2005-02-08", "2005-02-15")
    season(G, 300, 2, 3, "fotmob", late)
    season(G, 400, 50, 3, "sch", late)
    assert same_club.candidates(G.c) == [(50, 1)]


def test_a_national_team_a_guarded_uae_name_and_an_apart_pair_are_left_alone(tmp_path):
    G, reg = world(tmp_path, [(1, "Shabab Al Ahli", "fotmob"), (2, "Al Wasl", "fotmob"), (50, "Al Ahli", "uaefa"),
                              (3, "Inter", "fotmob"), (51, "Internacional", "sch")])
    G.put("team", {"tid": 60, "name": "Serbia", "kind": "national"}, "fotmob")
    G.put("team", {"tid": 61, "name": "Yugoslavia", "kind": "national"}, "martj42")
    season(G, 100, 1, 2, "fotmob", DAYS[:3])
    season(G, 200, 50, 2, "uaefa", DAYS[:3])
    season(G, 300, 3, 2, "fotmob", DAYS[:3], score=(4, 0))
    season(G, 400, 51, 2, "sch", DAYS[:3], score=(4, 0))
    season(G, 500, 60, 2, "fotmob", DAYS[:3], score=(7, 0))
    season(G, 600, 61, 2, "martj42", DAYS[:3], score=(7, 0))
    assert same_club.candidates(G.c, era=set(), never={("inter", "internacional")}, kept={"al ahli"}) == []
    assert same_club.candidates(G.c, era={1}, never=set(), kept=set()) == [(51, 3)]


def test_it_runs_after_the_name_rule_and_before_the_games_held_twice_are_made_one():
    assert ORDER.index("teams") < ORDER.index("same_club") < ORDER.index("people_again") < ORDER.index("twins")
