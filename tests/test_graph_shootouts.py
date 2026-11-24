"""graph/load/shootouts.py: a shoot-out held inside the score becomes a draw and its penalties."""
from graph.build import ORDER
from graph.db import Graph
from graph.ids import Registry
from graph.load import shootouts, twins


def world(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    G.merged = {}
    G.put("competition", {"cid": 1, "name": "World Cup", "kind": "tournament"}, "x")
    G.put("competition", {"cid": 2, "name": "Serie A", "kind": "league"}, "x")
    G.put("edition", {"eid": 10, "cid": 1, "season": "2014"}, "x")
    G.put("edition", {"eid": 20, "cid": 2, "season": "2014"}, "x")
    return G


def game(G, mid, hs, as_, goals="", eid=10, rnd="Round of 16", src="tm", events=True, date="2014-06-28"):
    """goals: the sides of the goals the events hold («ha» = one each)"""
    G.put("match", {"mid": mid, "eid": eid, "round": rnd, "date": date, "home": 1, "away": 2, "hs": hs, "as_": as_}, src)
    if events:
        G.c.execute("INSERT INTO event(mid, seq, minute, type, side, src) VALUES(?, 0, 10, 'yellow', 'h', ?)", (mid, src))
    for i, side in enumerate(goals, 1):
        G.c.execute("INSERT INTO event(mid, seq, minute, type, side, src) VALUES(?, ?, ?, 'goal', ?, ?)", (mid, i, 10 * i, side, src))


def score(G, mid):
    return G.c.execute("SELECT hs, as_, pen_h, pen_a, et FROM match WHERE mid=?", (mid,)).fetchone()


def test_the_kicks_leave_the_score(tmp_path):
    G = world(tmp_path)
    game(G, 1, 4, 3, "ha")                     # 1-1, 3-2 on penalties
    game(G, 2, 5, 3)                           # 0-0, 5-3
    game(G, 3, 8, 9, "hhaa")                   # 2-2, 6-7
    assert shootouts.load(G, Registry(), None) == {"shootouts": 3}
    assert [score(G, m) for m in (1, 2, 3)] == [(1, 1, 3, 2, 1), (0, 0, 5, 3, 1), (2, 2, 6, 7, 1)]


def test_a_game_that_is_not_a_shoot_out_keeps_its_score(tmp_path):
    G = world(tmp_path)
    game(G, 1, 2, 1, "hha")                    # its goals are its score
    game(G, 2, 3, 1, "h")                      # events short of goals, not level
    game(G, 3, 6, 0)                           # no shoot-out ends 6-0
    game(G, 4, 4, 3, events=False)             # no event at all
    game(G, 5, 3, 0, eid=20, rnd="12. Matchday")
    game(G, 6, 4, 2, eid=20, rnd="Group A")
    game(G, 7, 5, 4, "ha", src="fotmob")
    assert shootouts.load(G, Registry(), None) == {"shootouts": 0}
    assert score(G, 1) == (2, 1, None, None, None) and score(G, 5) == (3, 0, None, None, None)


def test_with_the_true_score_two_sources_hold_one_game(tmp_path):
    G = world(tmp_path)
    for tid in (1, 2):
        G.put("team", {"tid": tid, "name": f"T{tid}", "kind": "national"}, "x")
    game(G, 1, 4, 3, "ha")
    game(G, 2, 1, 1, src="martj42", events=False)
    G.c.commit()
    shootouts.load(G, Registry(), None)
    assert twins.load(G, Registry(), None)["merged"] == 1
    assert G.c.execute("SELECT count(*), max(pen_h) FROM match").fetchone() == (1, 3)


def test_a_shoot_outs_shape():
    assert all(shootouts.shootout(*x) for x in ((3, 0), (5, 4), (2, 4), (7, 6), (10, 11)))
    assert not any(shootouts.shootout(*x) for x in ((0, 0), (5, 0), (5, 2), (7, 5), (4, 4)))


def test_it_runs_before_the_twins():
    assert ORDER.index("tm") < ORDER.index("shootouts") < ORDER.index("twins")
