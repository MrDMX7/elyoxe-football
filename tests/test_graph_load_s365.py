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


def _add_comp(tmp_path, row, champions, fm_league=None):
    m = tmp_path / "mirror" / "s365"
    ix = json.loads((m / "index.json").read_text(encoding="utf-8"))
    ix["comps"].append(row)
    ix["countries"].setdefault(str(row[3]), ["", fm_league[0] if fm_league else "X"])
    (m / "index.json").write_text(json.dumps(ix), encoding="utf-8")
    (m / "comp" / ("%d.json" % row[0])).write_text(json.dumps({"id": str(row[0]), "champions": champions, "tables": {}, "live": {}}), encoding="utf-8")
    if fm_league:
        p = tmp_path / "db" / ".cache" / "fm_allleagues.json"
        al = json.loads(p.read_text())
        al["countries"].append({"name": fm_league[0], "leagues": [{"id": fm_league[1], "name": fm_league[2]}]})
        p.write_text(json.dumps(al))


def test_s365_skips_champions_of_competitions_with_unreliable_seasons(tmp_path):
    S = mk(tmp_path)
    _add_comp(tmp_path, [128, "كأس سومن", "Suomen Cup", 1, 0, 67, "1955", "2025", 0, 0, 0, 0], [["1988", 5, [], 1]])
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    out = s365.load(G, reg, S)
    suomen = reg.get("competition", "s365", 128)
    assert G.c.execute("select count(*) from honour h join edition e on e.eid=h.eid where e.cid=?", (suomen,)).fetchone()[0] == 0
    assert out["champions"] == 2


def test_s365_does_not_link_a_mens_competition_to_a_womens_one(tmp_path):
    S = mk(tmp_path)
    _add_comp(tmp_path, [23, "السوبر الإيطالي", "Supercoppa Italiana", 3, 1, 38, "1988/1989", "2025/2026", 0, 0, 0, 0], [], ("Italy", 11015, "Supercoppa Italiana"))
    _add_comp(tmp_path, [6215, "", "Frauen Bundesliga", 4, 0, 30, "1990", "2025", 0, 0, 0, 0], [], ("Germany", 9001, "Frauen Bundesliga"))
    _add_comp(tmp_path, [6216, "", "Bundesliga", 5, 0, 30, "1990", "2025", 0, 0, 0, 0], [], ("Austria", 9000, "Bundesliga Frauen"))
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    women = reg.mint("competition", "fotmob", 11015)
    frauen = reg.mint("competition", "fotmob", 9001)
    s365.load(G, reg, S)
    assert reg.get("competition", "s365", 23) != women
    assert reg.get("competition", "s365", 6215) == frauen
    assert reg.get("competition", "s365", 6216) != reg.mint("competition", "fotmob", 9000)
    assert s365.women("Eredivisie Vrouwen") and s365.women("Coupe de France Féminine") and s365.women("Damallsvenskan") \
        and s365.women("Toppserien Kvinner") and s365.women("Serie A Femminile") and not s365.women("Danish Superliga")


def test_a_side_of_a_table_the_index_does_not_list_takes_its_name_from_the_competitions_file(tmp_path):
    S = mk(tmp_path)
    f = tmp_path / "mirror" / "s365" / "comp" / "565.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["tables"]["2003/2004"] = [[1, 8276, 18, 12, 4, 2, 30, 10, 40.0], [2, 13397, 18, 10, 5, 3, 25, 12, 35.0]]
    d["names"], d["names_en"] = {"13397": "الجزيرة"}, {"13397": "Al Jazeera"}
    f.write_text(json.dumps(d), encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    s365.load(G, reg, S)
    assert G.c.execute("select name, name_ar, country from team where tid=?", (reg.get("team", "s365", 13397),)).fetchone() == ("Al Jazeera", "الجزيرة", "Jordan")
    assert G.c.execute("select count(*) from standing s left join team t using(tid) where t.name is null").fetchone()[0] == 0
