"""graph/load/old_names.py: clubs only the old sources know (RSSSF, 365Scores, Wikipedia), with no FotMob id, take their
Arabic name from teams_ar.yaml `historic` by their Latin name (UAE 2016/17 had «Al-Shabab Al-Arabi» and «Emirates»)."""
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import old_names


def test_a_latin_named_old_club_gets_its_arabic_name_and_a_named_one_keeps_it(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    a, b, c = (reg.mint("team", "rsssf", k) for k in ("x", "y", "z"))
    G.put("team", {"tid": a, "name": "Al-Shabab Al-Arabi"}, "rsssf")
    G.put("team", {"tid": b, "name": "Emirates", "name_ar": "نادي الإمارات"}, "rsssf")
    G.put("team", {"tid": c, "name": "Unknown FC"}, "rsssf")
    out = old_names.load(G, reg, Sources(str(tmp_path), s3=False), names={"Al-Shabab Al-Arabi": "الشباب", "Emirates": "الإمارات"})
    got = dict(G.c.execute("select name, name_ar from team"))
    assert got == {"Al-Shabab Al-Arabi": "الشباب", "Emirates": "نادي الإمارات", "Unknown FC": None} and out["teams"] == 1


def test_the_house_list_reads_from_teams_ar_yaml():
    names = old_names.historic()
    assert names["Al-Sha'ab"] == "الشعب" and names["Kalba Utd."] == "اتحاد كلباء"


def test_old_competitions_get_their_arabic_names_too(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    G.put("competition", {"cid": 1, "name": "FIFA World Cup qualification"}, "martj42")
    G.put("competition", {"cid": 2, "name": "Asian Games", "name_ar": "الألعاب الآسيوية"}, "martj42")
    out = old_names.load(G, reg, Sources(str(tmp_path), s3=False), names={}, comps={"FIFA World Cup qualification": "تصفيات كأس العالم", "Asian Games": "دورة الألعاب الآسيوية"})
    assert dict(G.c.execute("select name, name_ar from competition")) == {"FIFA World Cup qualification": "تصفيات كأس العالم", "Asian Games": "الألعاب الآسيوية"}
    assert (out["teams"], out["competitions"]) == (0, 1)
    assert old_names.historic_competitions()["Merdeka Tournament"] == "بطولة مرديكا"


def test_a_forced_rename_beats_another_sources_arabic_name(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    G.put("team", {"tid": 1, "name": "Al Shabab Al Arabi", "name_ar": "الشباب العربي"}, "s365")
    old_names.load(G, reg, Sources(str(tmp_path), s3=False), names={}, comps={}, rename={"Al Shabab Al Arabi": "الشباب"})
    assert G.c.execute("select name_ar from team").fetchone()[0] == "الشباب"
    assert old_names.renames()["Al Shabab Al Arabi"] == "الشباب"


def test_the_old_players_arabic_names_by_tifo_id(tmp_path):
    (tmp_path / "names").mkdir()
    (tmp_path / "names" / "people_ar.json").write_text(
        '{"k7": {"latin": "Ali Daei", "ar": "علي دائي", "source": "wikidata"}, "k8": {"latin": "X", "ar": "اكس", "source": "generated"}}', encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    G.put("player", {"pid": 7, "name": "Ali Daei"}, "rsssf")
    G.put("player", {"pid": 8, "name": "X", "name_ar": "اسم موجود"}, "wikidata")
    out = old_names.load(G, reg, Sources(str(tmp_path), s3=False), names={}, comps={}, rename={})
    assert dict(G.c.execute("select pid, name_ar from player")) == {7: "علي دائي", 8: "اسم موجود"} and out["players"] == 1
