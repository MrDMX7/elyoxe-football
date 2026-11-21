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


def _setup(tmp_path, rows, items):
    (tmp_path / "names").mkdir()
    (tmp_path / "names" / "players_ar.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    d = tmp_path / "graph" / ".cache" / "awards"
    d.mkdir(parents=True)
    (d / "items.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return Graph(str(tmp_path / "t.db")), Sources(str(tmp_path), mirror=str(tmp_path / "m"), s3=False)


def test_a_wikidata_item_born_years_apart_is_another_man(tmp_path):
    """FotMob's «Mohamed Hamed» (1994) carried Mohamed Salah's item (1992) from an old names row: his birth date, his
    World Cup awards. A FotMob player and an item born more than a year apart are never tied, and an earlier build's tie
    is undone (the registry keeps keys between builds, so the awards loader would find the wrong man again)."""
    G, S = _setup(tmp_path, {
        "1596110": {"latin": "Mohamed Hamed", "ar": "محمد حامد", "source": "generated", "qid": "Q1354960"},
        "1248736": {"latin": "Antony", "ar": "أنتوني", "source": "wikidata", "qid": "Q59205608"},
        "7": {"latin": "Neymar", "ar": "نيمار", "source": "wikidata", "qid": "Q142794"}},
        {"Mohamed_Salah": {"qid": "Q1354960", "human": True, "born": "1992-06-15", "en": "Mohamed Salah"},
         "Antony_(footballer,_born_2000)": {"qid": "Q59205608", "human": True, "born": "2000-02-24", "en": "Antony"},
         "Neymar": {"qid": "Q142794", "human": True, "born": "1992-02-05", "en": "Neymar"}})
    reg = Registry()
    ham, ant, ney = (reg.mint("player", "fotmob", k) for k in (1596110, 1248736, 7))
    for pid, born in ((ham, "1994-10-30"), (ant, "2001-09-08"), (ney, "1992-02-05")):
        G.put("player", {"pid": pid, "name": "x", "born": born}, "fotmob")
    assert reg.link("player", "wikidata", "Q59205608", ant) == ant       # an earlier build tied it
    before = Registry(json.loads(json.dumps(reg.to_json())))
    out = names.load(G, reg, S)
    assert reg.get("player", "wikidata", "Q1354960") is None
    assert reg.get("player", "wikidata", "Q59205608") is None                            # the old tie is undone
    assert reg.get("player", "wikidata", "Q142794") == ney                               # the same man still ties
    assert out["wikidata_refused"] == 2
    assert reg.moved(before) == []                                                       # an undone tie is not a move
    assert not G.c.execute("SELECT 1 FROM xref WHERE source='wikidata' AND tifo_id IN (?, ?)", (ham, ant)).fetchall()


def test_a_wikidata_item_with_no_shared_surname_is_another_man(tmp_path):
    """No birth date to compare: «Amer Khalil» is not «Amer Deeb»; «Salem Aldawsari» is «Salem Al-Dawsari»."""
    G, S = _setup(tmp_path, {
        "1642094": {"latin": "Amer Khalil", "ar": "عامر خليل", "source": "generated", "qid": "Q2245359"},
        "8": {"latin": "Salem Aldawsari", "ar": "سالم الدوسري", "source": "wikidata", "qid": "Q3"}},
        {"Amer_Deeb": {"qid": "Q2245359", "human": True, "born": None, "en": "Amer Deeb"},
         "Salem_Al-Dawsari": {"qid": "Q3", "human": True, "born": None, "en": "Salem Al-Dawsari"}})
    reg = Registry()
    reg.mint("player", "fotmob", 1642094)
    salem = reg.mint("player", "fotmob", 8)
    names.load(G, reg, S)
    assert reg.get("player", "wikidata", "Q2245359") is None
    assert reg.get("player", "wikidata", "Q3") == salem


def test_plausible():
    assert names.plausible("Mohamed Hamed", "1994-10-30", "Mohamed Salah", "1992-06-15") is False
    assert names.plausible("Antony", "2001-09-08", "Antony", "2000-02-24") is False
    assert names.plausible("Antony", "2001-09-08", "Antony", "2001-01-01") is True       # within a year: a date slip
    assert names.plausible("Agustin Marchesin", "1988-03-16", "Agustin Marchesin", "1945-03-16") is True   # a year typo
    assert names.plausible("Jordi Valadon", "2003-03-04", "Jordi Valadon", "2002-01-01") is True           # year only
    assert names.plausible("Jonathan Herrera", "1991-09-16", "Jonathan Herrera", "1998-01-01") is False
    assert names.plausible("Amer Khalil", None, "Amer Deeb", None) is False
    assert names.plausible("Vinicius Junior", None, "Vinícius Júnior", None) is True
    assert names.plausible("Ali", "1990-01-01", None, None) is True                       # nothing to compare: allowed
