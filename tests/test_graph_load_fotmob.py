import gzip, json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import fotmob_matches
from test_graph_rows import REC


def test_loads_two_matches(tmp_path):
    mx = tmp_path / "db" / ".cache" / "fm" / "mx"
    mx.mkdir(parents=True)
    (mx / "900.json").write_bytes(gzip.compress(json.dumps(REC).encode()))
    other = dict(REC, id=901, home=[20, "Al Wahda", 0], away=[10, "Al Ain", 0], date="2027-01-10T15:00:00.000Z")
    (mx / "901.json").write_text(json.dumps(other))
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    n = fotmob_matches.load(G, reg, Sources(str(tmp_path), s3=False))
    assert n["matches"] == 2
    assert G.c.execute("select count(*) from team").fetchone()[0] == 2
    assert G.c.execute("select season from edition order by season").fetchall() == [("2026/2027",)]
    assert G.c.execute("select count(*) from appearance where played=1").fetchone()[0] >= 5
    assert G.c.execute("select count(*) from xref where type='match'").fetchone()[0] == 2
