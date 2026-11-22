"""graph/load/rsssf_tops.py: Argentina's top scorer of every tournament since 1891 (RSSSF «Argentina - List of Topscorers»:
the amateur associations, Metropolitano/Nacional, Apertura/Clausura, Inicial/Final) on the tournament's own edition."""
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import rsssf_tops

PAGE = """<pre>Amateur Era
Year Ass. Name                           Club                               Goals
1896        Allen, Thomas Fearnley          Flores Athletic                    7
            Anderson, Juan O.               Lomas Athletic                     7
1912    AAF Ohaco, Alberto Bernardino       Racing Club                        9
1912    FAF Wilson, Ernesto                 Porteño                           12
1985 Met    Gareca, Ricardo                 Boca Juniors                      14
1991/92 Ape D&iacute;az, Ram&oacute;n &Aacute;ngel               River Plate                       14
        Cla Latorre, Diego Fernando         Boca Juniors                       9
1999/00 Ape Saviola, Javier Pedro           River Plate                       15
1995        N/A
</pre>"""


def test_the_list_reads_year_tournament_name_and_goals():
    rows = rsssf_tops.parse_arg(PAGE)
    assert rows[0] == ("1896", "", "Thomas Fearnley Allen", 7) and rows[1] == ("1896", "", "Juan O. Anderson", 7)
    assert ("1991/1992", "Ape", "Ramón Ángel Díaz", 14) in rows and ("1991/1992", "Cla", "Diego Fernando Latorre", 9) in rows
    assert not any(r[0] == "1995" for r in rows)
    assert ("1999/2000", "Ape", "Javier Pedro Saviola", 15) in rows                  # across the century


def test_each_scorer_lands_on_his_tournaments_edition(tmp_path):
    d = tmp_path / "db" / ".cache" / "rsssf_tops"
    d.mkdir(parents=True)
    (d / "arg.html").write_text(PAGE, encoding="latin-1")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    cid = reg.mint("competition", "fotmob", 112)
    G.put("competition", {"cid": cid, "name": "Liga Profesional"}, "fotmob")
    eds = {}
    for s in ("1896 (Amateur)", "1912 - Asociación Argentina de Football (Amateur)", "1912 - Federación Argentina de Football (Amateur)",
              "1985 Metropolitano", "1991/1992 Apertura", "1991/1992 Clausura", "1991/1992"):
        eds[s] = reg.mint("edition", "s365", s)
        G.put("edition", {"eid": eds[s], "cid": cid, "season": s}, "s365")
    out = rsssf_tops.load(G, reg, Sources(root=str(tmp_path), s3=False))
    who = lambda s: sorted(n for (n,) in G.c.execute("SELECT p.name FROM honour h JOIN player p ON p.pid=h.pid WHERE h.eid=? AND h.kind='top_scorer'", (eds[s],)))
    assert who("1896 (Amateur)") == ["Juan O. Anderson", "Thomas Fearnley Allen"]
    assert who("1912 - Federación Argentina de Football (Amateur)") == ["Ernesto Wilson"]
    assert who("1991/1992 Apertura") == ["Ramón Ángel Díaz"] and who("1991/1992") == []
    assert who("1985 Metropolitano") == ["Ricardo Gareca"]
    assert out["argentina"] == 7
