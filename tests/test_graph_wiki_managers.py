import gzip, os
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph import wiki_managers as WM
from graph.load import wiki_managers as LW

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "wiki_managers")


def page(name):
    return open(os.path.join(FIX, name), "rb").read()


def test_day_reads_wikipedia_dates():
    assert WM.day("1968") == "1968-01-01"
    assert WM.day("1971", end=True) == "1971-12-31"
    assert WM.day("14 July 2002") == "2002-07-14"
    assert WM.day("July 2004") == "2004-07-01"
    assert WM.day("Jan 2005", end=True) == "2005-01-31"
    assert WM.day("21 Oct 2004") == "2004-10-21"
    assert WM.day("October 4, 2025") == "2025-10-04"
    assert WM.day("present", end=True) is None and WM.day("?") is None


def test_parse_reads_only_the_managers_section():
    got = WM.parse(page("club.html"))
    assert [s["name"] for s in got] == ["Nasser Dhaen", "Bruno Metsu", "Alain Perrin", "Mohammad El Mansi", "Vladimir Ivić"]
    assert got[0] == {"name": "Nasser Dhaen", "title": None, "start": "1968-01-01", "end": "1971-12-31", "open": False}
    assert got[2]["title"] == "Alain_Perrin" and got[2]["end"] == "2004-10-21"
    assert got[3]["end"] == "2005-01-31"                       # «(caretaker)» is dropped from the name
    assert got[4]["end"] is None and got[4]["open"]            # «present»


def test_parse_reads_a_list_of_managers_page():
    assert WM.parse(page("list.html")) == []                     # an unheaded «Name|From|To» on a club article: anyone
    got = WM.parse(page("list.html"), listing=True)
    assert [(s["name"], s["start"], s["end"]) for s in got] == [("Gamil Osman", "1926-01-01", "1930-12-31"),
                                                                 ("Jess Thorup", "2025-10-08", "2026-06-04")]


def _setup(tmp_path):
    d = tmp_path / "graph" / ".cache" / "managers"
    (d / "pages").mkdir(parents=True)
    (d / "pages" / (WM._key("Al Ain FC") + ".html.gz")).write_bytes(gzip.compress(page("club.html")))
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    ain, opp = reg.mint("team", "fotmob", 102117), reg.mint("team", "fotmob", 999)
    G.xref("team", ain, "fotmob", 102117, "fotmob-native")
    mids = []
    for k, d_ in enumerate(("1969-03-01", "2003-01-10", "2004-08-01", "2004-10-22", "2026-01-01")):
        mid = reg.mint("match", "rsssf", k)
        G.put("match", {"mid": mid, "date": d_, "home": ain, "away": opp, "hs": 1, "as_": 0}, "rsssf")
        mids.append(mid)
    fm = reg.mint("coach", "fotmob", 77)
    G.put("coach", {"kid": fm, "name": "Vladimir Ivic"}, "fotmob")
    G.c.execute("insert into match_coach values(?, 'h', ?, 'fotmob')", (mids[4], fm))
    return G, reg, Sources(str(tmp_path), s3=False), mids, fm


def test_loader_fills_only_empty_benches_inside_a_spell(tmp_path):
    G, reg, S, mids, fm = _setup(tmp_path)
    out = LW.load(G, reg, S, clubs={102117: ["Al Ain FC"]})
    rows = {m: G.c.execute("select c.name, x.src from match_coach x join coach c on c.kid=x.kid where x.mid=? and x.side='h'", (m,)).fetchone()
            for m in mids}
    assert rows[mids[0]] == ("Nasser Dhaen", "wiki")
    assert rows[mids[1]] == ("Bruno Metsu", "wiki")
    assert rows[mids[2]] == ("Alain Perrin", "wiki")
    assert rows[mids[3]] is None                                  # 22 Oct 2004: between Perrin and El Mansi, nobody's
    assert rows[mids[4]] == ("Vladimir Ivic", "fotmob")           # FotMob's bench is never overridden
    assert out["matches_assigned"] == 3


def test_loader_reuses_the_clubs_fotmob_coach_by_name(tmp_path):
    G, reg, S, mids, fm = _setup(tmp_path)
    G.put("match", {"mid": reg.mint("match", "rsssf", 99), "date": "2025-11-01", "home": mids and G.c.execute("select home from match").fetchone()[0],
                    "away": reg.get("team", "fotmob", 999), "hs": 0, "as_": 0}, "rsssf")
    LW.load(G, reg, S, clubs={102117: ["Al Ain FC"]})
    m = reg.get("match", "rsssf", 99)
    assert G.c.execute("select kid from match_coach where mid=?", (m,)).fetchone()[0] == fm


def test_loader_skips_without_cache(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    assert "skipped" in LW.load(G, reg, Sources(str(tmp_path), s3=False), clubs={1: ["X"]})
