"""graph/archive_export.persons: a career line names its competition in Arabic. Transfermarkt's names («League One», «Serie
B», «Premier League») showed in English on 850k of 1.29M lines: one of ours by name (the club's own where several share it),
else the curated graph/tm_comps_ar.yaml, else Transfermarkt's own."""
import json
from graph import archive_export
from test_graph_matches_publish import world


def test_a_career_line_names_its_competition_in_arabic(tmp_path):
    G, m2, old = world(tmp_path)
    pid = G.c.execute("select pid from player where name='Ali Mabkhout'").fetchone()[0]
    jaz = G.c.execute("select tid from team where name_ar='الجزيرة'").fetchone()[0]
    G.put("competition", {"cid": 7001, "name": "Pro League", "name_ar": "الدوري السعودي"}, "fotmob")      # a namesake of ours elsewhere
    for season, comp in (("2016/2017", "Pro League"), ("2015/2016", "League One"), ("2014/2015", "Some Cup")):
        G.c.execute("insert into player_season(pid, season, comp, tid, apps, src) values(?, ?, ?, ?, 10, 'tm')", (pid, season, comp, jaz))
    G.c.commit()
    out = tmp_path / "d"
    out.mkdir()
    archive_export.persons(G, str(out))
    p = json.load(open(out / "people" / f"{pid % 500}.json", encoding="utf-8"))[str(pid)]
    assert [c[1] for c in p["car"]] == ["دوري أدنوك للمحترفين", "دوري الدرجة الأولى الإنجليزي", "Some Cup"]


def test_a_competition_named_by_its_transfermarkt_code_gives_way_to_the_lines_own_name(tmp_path):
    # live 23 Nov: «FAC», «CGB», «CDR» on 441k lines (competitions made from Transfermarkt codes, named by the code)
    G, m2, old = world(tmp_path)
    pid = G.c.execute("select pid from player where name='Ali Mabkhout'").fetchone()[0]
    jaz = G.c.execute("select tid from team where name_ar='الجزيرة'").fetchone()[0]
    G.put("competition", {"cid": 899, "name": "FAC"}, "tm")
    G.put("competition", {"cid": 7002, "name": "FA Cup", "name_ar": "كأس الاتحاد الإنجليزي"}, "fotmob")
    G.put("competition", {"cid": 900, "name": "CGB"}, "tm")
    G.c.execute("insert into player_season(pid, season, comp, cid, tid, apps, src) values(?, '2016/2017', 'FA Cup', 899, ?, 3, 'tm')", (pid, jaz))
    G.c.execute("insert into player_season(pid, season, comp, cid, tid, apps, src) values(?, '2015/2016', 'EFL Cup', 900, ?, 2, 'tm')", (pid, jaz))
    G.c.commit()
    out = tmp_path / "d"
    out.mkdir()
    archive_export.persons(G, str(out))
    p = json.load(open(out / "people" / f"{pid % 500}.json", encoding="utf-8"))[str(pid)]
    assert [c[1] for c in p["car"]] == ["كأس الاتحاد الإنجليزي", "EFL Cup"]
