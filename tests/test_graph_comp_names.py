"""graph/load/comp_names.py: competitions known only by a code or a slug («TR1», «hungary», «ddr»: 589 holding a million
games on 22 Nov 2026) take their Arabic name from names/comps_ar.json, never over a name they have."""
import json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import comp_names


def test_a_competition_named_by_a_code_takes_its_arabic_name(tmp_path):
    (tmp_path / "names").mkdir()
    (tmp_path / "names" / "comps_ar.json").write_text(json.dumps({
        "TR1": {"ar": "الدوري التركي الممتاز", "source": "generated"}, "hungary": {"ar": "الدوري المجري", "source": "generated"}},
        ensure_ascii=False), encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    G.put("competition", {"cid": 1, "name": "TR1"}, "tm")
    G.put("competition", {"cid": 2, "name": "hungary"}, "sch")
    G.put("competition", {"cid": 3, "name": "hungary", "name_ar": "دوري المجر"}, "sch")
    out = comp_names.load(G, reg, Sources(str(tmp_path), mirror=str(tmp_path / "m"), s3=False))
    got = dict(G.c.execute("select cid, name_ar from competition").fetchall())
    assert got == {1: "الدوري التركي الممتاز", 2: "الدوري المجري", 3: "دوري المجر"} and out == {"named": 2, "clubs": 0}


def test_a_club_with_no_transfermarkt_id_takes_its_arabic_name_by_its_tifo_id_and_a_gone_one_is_not_made(tmp_path):
    # 23 Nov 2026: 11,067 clubs of the old leagues' datasets (Bristol Rovers, Hearts, Ferencváros) had no Arabic name
    (tmp_path / "names").mkdir()
    (tmp_path / "names" / "clubs_k_ar.json").write_text(json.dumps({
        "t35331": {"latin": "Bristol Rovers", "ar": "بريستول روفرز", "source": "generated"},
        "t99": {"latin": "Gone", "ar": "ذهب", "source": "generated"},
        "t5": {"latin": "Hearts", "ar": "هارتس", "source": "generated"}}, ensure_ascii=False), encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    G.put("team", {"tid": 35331, "name": "Bristol Rovers"}, "sch")
    G.put("team", {"tid": 5, "name": "Hearts", "name_ar": "قلوب ميدلوثيان"}, "sch")
    comp_names.load(G, reg, Sources(str(tmp_path), mirror=str(tmp_path / "m"), s3=False))
    assert dict(G.c.execute("select tid, name_ar from team").fetchall()) == {35331: "بريستول روفرز", 5: "قلوب ميدلوثيان"}
