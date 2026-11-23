"""graph/load/mens.py: Tifo is men's football (the owner, 23 Nov 2026: «كرة القدم النسائية ماباها»). Every women's competition
or award leaves the graph with its editions and honours; a woman with no other record then has no profile."""
from graph.db import Graph
from graph.ids import Registry
from graph.load import mens


def test_womens_competitions_and_awards_leave_with_their_editions_and_honours(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    for cid, name, kind in ((1, "Bundesliga", "league"), (2, "Frauen Bundesliga", "league"), (3, "The Best FIFA Women's Player", "award"),
                            (4, "Ballon d'Or Féminin", "award"), (5, "Ballon d'Or", "award"), (9, "Supercopa (W)", "cup"), (6, "Icelandic Footballer of the Year — Men", "award")):
        G.put("competition", {"cid": cid, "name": name, "kind": kind}, "x")
        G.put("edition", {"eid": cid * 10, "cid": cid, "season": "2020"}, "x")
        G.c.execute("insert into honour(eid, kind, rank, pid, src) values(?, 'winner', 1, ?, 'x')", (cid * 10, cid))
    G.put("team", {"tid": 7, "name": "Netherlands", "name_ar": "هولندا (W)", "kind": "national"}, "x")
    G.put("competition", {"cid": 8, "name": "Algarve Cup", "kind": "cup"}, "x")            # a women's tournament by its teams
    G.put("edition", {"eid": 80, "cid": 8, "season": "2020"}, "x")
    G.c.execute("insert into honour(eid, kind, rank, tid, src) values(80, 'champion', 1, 7, 'x')")
    G.c.commit()
    out = mens.load(G, reg, None)
    assert sorted(c for (c,) in G.c.execute("select cid from competition")) == [1, 5, 6]
    assert sorted(e for (e,) in G.c.execute("select eid from edition")) == [10, 50, 60]
    assert sorted(e for (e,) in G.c.execute("select eid from honour")) == [10, 50, 60]
    assert out["competitions"] == 5
