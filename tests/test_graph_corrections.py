"""graph/load/corrections.py: what a person decided from official sources (graph/corrections.yaml) beats every source, every
build: an honour's winners replaced, a match or a birth date set, a disagreement closed when the value shown was right."""
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import corrections


def world(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League"}, "fotmob")
    eds = {}
    for season in ("1991/1992", "2015/2016", "2023/2024"):
        e = reg.mint("edition", "fotmob", f"538|{season}")
        G.put("edition", {"eid": e, "cid": lg, "season": season}, "fotmob")
        eds[season] = e
    zb, atiq = reg.mint("player", "rsssf", "zb"), reg.mint("player", "wiki-name", "atiq")
    G.put("player", {"pid": zb, "name": "Zoheir Bakhit"}, "rsssf")
    G.put("player", {"pid": atiq, "name": "Youssouf Atiq"}, "wikidata")
    G.c.execute("insert into honour(eid, kind, rank, pid, value, src) values(?, 'top_scorer', 1, ?, '22', 'rsssf')", (eds["1991/1992"], zb))
    G.conflict("honour", eds["1991/1992"], "top_scorer", "zoheir bakhit", "rsssf", "youssouf atiq", "wiki")
    tag = reg.mint("player", "fotmob", 141647)
    G.put("player", {"pid": tag, "name": "Sebastian Tagliabue"}, "fotmob")
    G.conflict("honour", eds["2023/2024"], "top_scorer", "omar khribin", "tifo", "soufiane rahimi", "wiki")
    jaz = reg.mint("player", "fotmob", 713207)
    G.put("player", {"pid": jaz, "name": "Seifeddine Jaziri", "born": "1993-02-11"}, "fotmob")
    G.conflict("player", jaz, "born", "1993-02-11", "fotmob", "1993-02-12", "wikidata")
    G.c.commit()
    return G, reg, eds, atiq, tag, jaz


CONF = {
    "honours": [{"comp": 538, "season": "1991/1992", "kind": "top_scorer", "value": "25", "players": [{"name": "Youssouf Atiq"}], "source": "RSSSF"},
                {"comp": 538, "season": "2015/2016", "kind": "top_scorer", "value": "25", "players": [{"fotmob": 141647}, {"name": "New Man"}], "source": "x"}],
    "keep": [{"comp": 538, "season": "2023/2024", "kind": "top_scorer", "source": "Pro League awards"}],
    "players": [{"fotmob": 713207, "born": "1993-02-12", "source": "Wikipedia"}],
}


def test_decisions_beat_the_sources_and_close_the_disagreements(tmp_path):
    G, reg, eds, atiq, tag, jaz = world(tmp_path)
    out = corrections.load(G, reg, Sources(str(tmp_path), s3=False), conf=CONF)
    assert G.c.execute("select pid, value, src from honour where eid=? and kind='top_scorer'", (eds["1991/1992"],)).fetchall() == [(atiq, "25", "correction")]
    got = sorted(p for (p,) in G.c.execute("select pid from honour where eid=? and kind='top_scorer'", (eds["2015/2016"],)))
    assert tag in got and len(got) == 2                                  # a name the archive lacks is added as a player
    assert G.c.execute("select born from player where pid=?", (jaz,)).fetchone()[0] == "1993-02-12"
    assert G.c.execute("select count(*) from conflict").fetchone()[0] == 0
    assert out == {"honours": 2, "kept": 1, "players": 1}


def test_the_file_reads():
    c = corrections.read()
    assert any(h["season"] == "1999/2000" and len(h["players"]) == 3 for h in c["honours"])


def test_a_player_without_a_fotmob_id_is_named_by_his_wikidata_id(tmp_path):
    G, reg, eds, atiq, tag, jaz = world(tmp_path)
    pepe = reg.mint("player", "wikidata", "Q485697")
    G.put("player", {"pid": pepe, "name": "Pepe", "born": "1984-02-26"}, "wikidata")
    G.conflict("player", pepe, "born", "1984-02-26", "wikidata", "1983-02-26", "tm")
    G.c.commit()
    conf = {"players": [{"wikidata": "Q485697", "born": "1983-02-26", "source": "FPF"},
                        {"wikidata": "Q1", "born": "1900-01-01", "source": "nobody here"}]}
    out = corrections.load(G, reg, Sources(str(tmp_path), s3=False), conf=conf)
    assert G.c.execute("select born from player where pid=?", (pepe,)).fetchone()[0] == "1983-02-26"
    assert G.c.execute("select count(*) from conflict where tifo_id=? and field='born'", (pepe,)).fetchone()[0] == 0
    assert out["players"] == 1


def test_a_club_honour_is_replaced_by_its_fotmob_club(tmp_path):
    # Botola 2002/03: Raja were second (Wikipedia's table), not the table source's CODM Meknès
    G, reg, eds, *_ = world(tmp_path)
    codm, raja = reg.mint("team", "rsssf", "codm"), reg.mint("team", "fotmob", 9925)
    G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'runner_up', 1, ?, 'table')", (eds["2015/2016"], codm))
    G.conflict("honour", eds["2015/2016"], "runner_up", "codm meknes", "table", "raja club athletic", "wiki")
    corrections.load(G, reg, None, {"honours": [{"comp": 538, "season": "2015/2016", "kind": "runner_up", "teams": [9925], "source": "x"}]})
    assert G.c.execute("select tid, src from honour where eid=? and kind='runner_up'", (eds["2015/2016"],)).fetchall() == [(raja, "correction")]
    assert not G.c.execute("select 1 from conflict where tifo_id=? and field='runner_up'", (eds["2015/2016"],)).fetchall()
