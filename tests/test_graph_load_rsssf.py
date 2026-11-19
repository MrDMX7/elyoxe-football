import json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import rsssf

UAE = {"country": "uae", "league": 538, "source": "RSSSF (rsssf.org)", "seasons": [
    {"season": "1973/1974", "champion": "Al-Oroba", "table": [[1, "Oroba (Sharjah)", None, 2, 1, 1, 0, 4, 1, 3], [2, "Al-Ahly Dubai", 102119, 2, 0, 2, 0, 0, 0, 2]]},
    {"season": "2025/2026", "champion": "Al-Ain", "table": [[1, "Al-Ain", 102117, 26, 21, 5, 0, 62, 18, 68]]}]}


def mk(tmp_path):
    m = tmp_path / "mirror" / "history" / "arab"
    m.mkdir(parents=True)
    (m / "uae.json").write_text(json.dumps(UAE), encoding="utf-8")
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    (db / "rsssf_clubs.json").write_text(json.dumps({"102117": {"positions": [], "matches": [["1995-04-14", 102124, 1, 1, 1, "rsssf:uae:cup"]]}}))
    return Sources(str(tmp_path), mirror=str(tmp_path / "mirror"), s3=False)


def test_rsssf_tables_champions_and_matches(tmp_path):
    S, G, reg = mk(tmp_path), Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League"}, "fotmob")
    have = reg.mint("edition", "fotmob", "538|2025/2026")
    G.put("edition", {"eid": have, "cid": lg, "season": "2025/2026"}, "fotmob")
    out = rsssf.load(G, reg, S, codes=["uae"])
    assert out["standings"] == 3 and out["champions"] == 2 and out["matches"] == 1
    old = G.c.execute("select eid from edition where cid=? and season='1973/1974'", (lg,)).fetchone()[0]
    assert G.c.execute("select rank, played, won, drawn, lost, gf, ga, pts from standing where eid=? order by rank", (old,)).fetchall() == \
        [(1, 2, 1, 1, 0, 4, 1, 3), (2, 2, 0, 2, 0, 0, 0, 2)]
    assert G.c.execute("select tid from honour where eid=? and kind='champion'", (have,)).fetchone()[0] == reg.get("team", "fotmob", 102117)
    oroba = G.c.execute("select tid from standing where eid=? and rank=1", (old,)).fetchone()[0]
    assert G.c.execute("select name from team where tid=?", (oroba,)).fetchone()[0] == "Oroba (Sharjah)"
