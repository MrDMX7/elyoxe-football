"""graph/load/void.py: seasons that ended with no champion (graph/void_seasons.yaml) beat every source's «champion»."""
import json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import void


def test_a_cancelled_season_loses_any_champion_and_says_why(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League"}, "fotmob")
    e = reg.mint("edition", "rsssf", "538|2019/2020")
    G.put("edition", {"eid": e, "cid": lg, "season": "2019/2020"}, "rsssf")
    G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'champion', 1, 7, 'rsssf')", (e,))
    G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'runner_up', 1, 8, 'table')", (e,))
    G.c.execute("insert into honour(eid, kind, rank, pid, value, src) values(?, 'top_scorer', 1, 9, '20', 'tifo')", (e,))
    out = void.load(G, reg, Sources(str(tmp_path), s3=False), seasons={538: {"2019/2020": "انلغى بسبب كورونا بدون بطل", "1990/1991": "ما انلعب بسبب حرب الخليج"}})
    assert out == {"seasons": 2, "honours_removed": 2}
    assert [k for (k,) in G.c.execute("select kind from honour where eid=?", (e,))] == ["top_scorer"]       # the goals were scored
    assert G.c.execute("select status, note from edition where eid=?", (e,)).fetchone() == ("void", "انلغى بسبب كورونا بدون بطل")
    assert G.c.execute("select status from edition where cid=? and season='1990/1991'", (lg,)).fetchone() == ("void",)   # made when no source had it


def test_the_published_season_carries_the_note(tmp_path):
    from graph import publish
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League"}, "fotmob")
    G.xref("competition", lg, "fotmob", 538, "fotmob-native")
    void.load(G, reg, Sources(str(tmp_path), s3=False), seasons={538: {"1990/1991": "ما انلعب بسبب حرب الخليج"}})
    publish.editions(G, str(tmp_path / "o"))
    s = json.load(open(tmp_path / "o" / "editions" / "538.json", encoding="utf-8"))["seasons"][0]
    assert s["season"] == "1990/1991" and s["champion"] is None and s["note"] == "ما انلعب بسبب حرب الخليج"
