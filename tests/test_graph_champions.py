"""graph/load/champions.py: the champions of graph/champions.yaml, on the editions whose games the club played."""
import yaml
from graph.build import ORDER
from graph.db import Graph
from graph.ids import Registry
from graph.load import champions


def world(tmp_path, data):
    p = tmp_path / "champions.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    cid = reg.mint("competition", "sch", "mauritania")
    G.put("competition", {"cid": cid, "name": "Mauritania Premier League"}, "sch")
    t = {nm: reg.mint("team", "sch", nm) for nm in ("A", "B", "C")}
    for nm, tid in t.items():
        G.put("team", {"tid": tid, "name": nm}, "sch")
    G.xref("team", t["A"], "sch", "A of the games", "sch-native")       # a club joined to A: the key's record is A now
    eds = {}
    for i, s in enumerate(("2010/2011", "2011/2012", "2012/2013")):
        eds[s] = reg.mint("edition", "sch", f"mauritania|{s}")
        G.put("edition", {"eid": eds[s], "cid": cid, "season": s}, "sch")
        G.put("match", {"mid": i + 1, "eid": eds[s], "date": f"{2011 + i}-01-01", "home": t["A"], "away": t["B"], "hs": 1, "as_": 0}, "sch")
    return G, reg, eds, t, str(p)


def test_a_champion_goes_on_the_edition_whose_games_he_played(tmp_path):
    G, reg, eds, t, p = world(tmp_path, {"sch|mauritania": {"2010/2011": "A of the games", "2011/2012": "C", "2012/2013": "B", "2013/2014": "A", "2014/2015": "Nobody"},
                                         "sch|nowhere": {"2010/2011": "A"}})
    G.c.execute("INSERT INTO honour(eid, kind, rank, tid, src) VALUES(?,?,?,?,?)", (eds["2012/2013"], "champion", 1, t["A"], "wiki"))
    out = champions.load(G, reg, None, path=p)
    assert G.c.execute("SELECT eid, tid, src FROM honour WHERE kind='champion' ORDER BY eid").fetchall() == [
        (eds["2010/2011"], t["A"], "rsssf"), (eds["2012/2013"], t["A"], "wiki")]
    assert out == {"champions": 1, "not_in_its_games": 1, "already": 1, "no_edition": 1, "no_club": 1, "no_competition": 1}


def test_the_file_is_read_and_the_step_runs_before_the_seasons():
    data = yaml.safe_load(open(champions.FILE, encoding="utf-8"))
    assert all("|" in k and all(isinstance(v, str) for v in d.values()) for k, d in data.items())
    assert ORDER.index("same_club") < ORDER.index("champions") < ORDER.index("seasons")
