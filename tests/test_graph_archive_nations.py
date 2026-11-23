"""graph/archive_export.nation_ar: a nationality in Arabic on the archive's pages. Profiles showed «الجنسية: BRA» (the graph
keeps FotMob's three-letter code for players and an English name for coaches and referees)."""
from graph.db import Graph
from graph.ids import Registry
from graph import archive_export


def test_a_code_reads_as_the_national_team_its_men_played_for_and_a_name_as_that_team(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    ned, ned21, nedw = (reg.mint("team", "x", n) for n in ("ned", "ned21", "nedw"))
    for t, n, a in ((ned, "Netherlands", "هولندا"), (ned21, "Netherlands U21", "هولندا تحت 21"), (nedw, "Netherlands", "هولندا (W)")):
        G.put("team", {"tid": t, "name": n, "name_ar": a, "kind": "national"}, "fotmob")
    ps = [reg.mint("player", "x", i) for i in range(4)]
    for p in ps:
        G.put("player", {"pid": p, "name": f"P{p}", "nationality": "NED"}, "fotmob")
    m = [reg.mint("match", "x", i) for i in range(5)]
    for i, mid in enumerate(m):
        G.put("match", {"mid": mid, "date": f"2000-01-0{i + 1}", "home": ned21 if i == 4 else ned, "away": ned21, "hs": 1, "as_": 0}, "fotmob")
        G.many("appearance", [{"mid": mid, "pid": ps[i % 3], "tid": ned21 if i == 4 else ned, "played": 1}], "fotmob")
    G.c.commit()
    ar = archive_export.nation_ar(G)
    assert ar("NED") == "هولندا"
    assert ar("Netherlands") == "هولندا"
    assert ar("XYZ") == "XYZ" and ar(None) is None


def test_other_english_forms_and_states_that_no_longer_exist(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    t = reg.mint("team", "x", "usa")
    G.put("team", {"tid": t, "name": "USA", "name_ar": "أمريكا", "kind": "national"}, "fotmob")
    G.c.commit()
    ar = archive_export.nation_ar(G)
    assert ar("United States") == "أمريكا"
    assert ar("West Germany") == "ألمانيا الغربية" and ar("Soviet Union") == "الاتحاد السوفيتي"
