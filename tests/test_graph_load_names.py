"""graph/load/names.py: a name the owner corrected by hand (names/players_ar.json source "manual") with a Wikidata id ties that
item to the FotMob player even when another record holds it (Ali Mabkhout: FotMob's «Al Hajeri Ahmad Mabkhout», and the
record his awards and his 85 international goals made under Q1089907)."""
import json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import names


def test_a_manual_name_with_a_wikidata_id_merges_the_record_that_holds_it(tmp_path):
    (tmp_path / "names").mkdir()
    (tmp_path / "names" / "players_ar.json").write_text(json.dumps({
        "170716": {"latin": "Al Hajeri Ahmad Mabkhout", "ar": "علي مبخوت", "source": "manual", "qid": "Q1089907"},
        "999": {"latin": "Someone", "ar": "أحد", "source": "generated", "qid": "Q5"}}, ensure_ascii=False), encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    fm = reg.mint("player", "fotmob", 170716)
    wd = reg.mint("player", "wikidata", "Q1089907")
    reg.link("player", "tm", "114150", wd)
    other, q5 = reg.mint("player", "fotmob", 999), reg.mint("player", "wikidata", "Q5")
    reg.link("player", "tm", "1", q5)
    names.load(G, reg, Sources(str(tmp_path), mirror=str(tmp_path / "m"), s3=False))
    assert reg.get("player", "wikidata", "Q1089907") == reg.get("player", "fotmob", 170716)          # one player now
    assert ("player", max(fm, wd), min(fm, wd)) in reg.run_merges                                   # the build moves the rows
    assert reg.get("player", "wikidata", "Q5") != reg.get("player", "fotmob", 999)                  # a generated name never merges
