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
    assert got == {"Al-Shabab Al-Arabi": "الشباب", "Emirates": "نادي الإمارات", "Unknown FC": None} and out == {"teams": 1}


def test_the_house_list_reads_from_teams_ar_yaml():
    names = old_names.historic()
    assert names["Al-Sha'ab"] == "الشعب" and names["Kalba Utd."] == "اتحاد كلباء"
