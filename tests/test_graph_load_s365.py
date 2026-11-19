import json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import s365


def mk(tmp_path):
    m = tmp_path / "mirror" / "s365"
    (m / "comp").mkdir(parents=True)
    (m / "index.json").write_text(json.dumps({
        "countries": {"119": ["الأردن", "Jordan"], "1": ["إنجلترا", "England"]},
        "comps": [[565, "الدوري الأردني", "Pro League", 119, 0, 10, "1944", "2025/2026", 0, 0, 0, 0],
                  [7, "الدوري الإنجليزي", "Premier League", 1, 0, 127, "1888/1889", "2025/2026", 0, 0, 0, 0]],
        "teams": [[8285, "الحسين إربد", "Al Hussein", 119, None], [8276, "الفيصلي", "Al Faisaly", 119, None], [5, "أرسنال", "Arsenal", 1, 9825]]}), encoding="utf-8")
    (m / "comp" / "565.json").write_text(json.dumps({"id": "565", "champions": [["2024/2025", 8285, ["16", "5", "1", "53"], 135]],
        "tables": {"2024/2025": [[1, 8285, 22, 16, 5, 1, 50, 10, 53.0], [2, 8276, 22, 15, 5, 2, 45, 15, 50.0]]},
        "live": {"results": [[1, "2026-10-24T20:30", 137, 6, 8285, 8276, 2, 1, 4, 1]]}}), encoding="utf-8")
    (m / "comp" / "7.json").write_text(json.dumps({"id": "7", "champions": [["1888/1889", 5, [], 1]], "tables": {}, "live": {}}), encoding="utf-8")
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    (db / "fm_allleagues.json").write_text(json.dumps({"popular": [], "international": [], "countries": [{"ccode": "ENG", "name": "England", "leagues": [{"id": 47, "name": "Premier League"}]}]}))
    return Sources(str(tmp_path), mirror=str(tmp_path / "mirror"), s3=False)


def test_s365(tmp_path):
    S, G, reg = mk(tmp_path), Graph(str(tmp_path / "t.db")), Registry()
    arsenal = reg.mint("team", "fotmob", 9825)
    pl = reg.mint("competition", "fotmob", 47)
    out = s365.load(G, reg, S)
    assert reg.get("team", "s365", 5) == arsenal
    assert reg.get("competition", "s365", 7) == pl
    assert out["champions"] == 2
    jo = reg.get("competition", "s365", 565)
    assert G.c.execute("select count(*) from standing s join edition e on e.eid=s.eid where e.cid=?", (jo,)).fetchone()[0] == 2
    assert G.c.execute("select count(*) from match where src='s365'").fetchone()[0] == 1
    assert G.c.execute("select name_ar from team where tid=?", (reg.get("team", "s365", 8276),)).fetchone()[0] == "الفيصلي"


def test_s365_uses_the_curated_fotmob_map_and_season_labels(tmp_path):
    S = mk(tmp_path)
    m = tmp_path / "mirror" / "s365"
    ix = json.loads((m / "index.json").read_text(encoding="utf-8"))
    ix["comps"].append([5930, "كأس العالم", "World Cup", 1, 1, 23, "1930", "2026", 0, 0, 0, 0])
    ix["teams"].append([2378, "الأرجنتين", "Argentina", 1, 6706])
    (m / "index.json").write_text(json.dumps(ix), encoding="utf-8")
    (m / "comp" / "5930.json").write_text(json.dumps({"id": "5930", "champions": [["قطر 2022", 2378, [], 1]], "tables": {}, "live": {}}), encoding="utf-8")
    (m / "fm.json").write_text(json.dumps({"comps": {"77": {"id": 5930}}}), encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    wc = reg.mint("competition", "fotmob", 77)
    e22 = reg.mint("edition", "fotmob", "77|2022")
    G.put("edition", {"eid": e22, "cid": wc, "season": "2022"}, "fotmob")
    s365.load(G, reg, S)
    assert reg.get("competition", "s365", 5930) == wc
    assert G.c.execute("select eid from honour where kind='champion' and tid=?", (reg.get("team", "fotmob", 6706),)).fetchone()[0] == e22
