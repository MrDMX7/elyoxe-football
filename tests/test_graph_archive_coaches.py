"""graph/archive_export.coaches: every coach with a bench in the archive or a coach's award (the owner, 22 Nov 2026: «كل
المدربين»), for /coach/k<Tifo id>/: his spells club by club with their record, his awards and his last games."""
import json
from graph import archive_export
from test_graph_matches_publish import world


def test_every_coach_gets_his_spells_awards_and_last_games(tmp_path):
    G, m2, old = world(tmp_path)
    kid = G.c.execute("select kid from coach").fetchone()[0]
    G.c.execute("update coach set born='1954-12-09', nationality='Netherlands' where kid=?", (kid,))
    G.xref("coach", kid, "fotmob", 5, "fotmob-native")
    G.put("competition", {"cid": 9001, "name": "Coach of the Year", "name_ar": "مدرب العام", "kind": "award"}, "wiki")
    G.put("edition", {"eid": 9002, "cid": 9001, "season": "2017"}, "wiki")
    G.c.execute("insert into honour(eid, kind, rank, kid, src) values(9002, 'winner', 1, ?, 'wiki')", (kid,))
    G.c.commit()
    out = tmp_path / "d"
    out.mkdir()
    r = archive_export.coaches(G, str(out))
    c = json.load(open(out / "coaches.json", encoding="utf-8"))[str(kid)]
    assert r == {"coaches": 1}
    assert c["n"] == "Henk ten Cate" and c["fm"] == 5 and c["b"] == "1954-12-09" and c["nat"] == "Netherlands"
    assert c["sp"] == [["الجزيرة", 102101, "2016-10-01", "2016-10-01", 1, 1, 0, 0, 2, 1]]
    assert c["hon"] == [["winner", 1, "مدرب العام", None, "2017", None]]
    assert c["last"] == [["2600001", "2016-10-01", "الجزيرة", 102101, "العين", 102117, 2, 1, 538]]


def test_a_coachs_nationality_reads_in_arabic(tmp_path):
    G, m2, old = world(tmp_path)
    kid = G.c.execute("select kid from coach").fetchone()[0]
    G.c.execute("update coach set nationality='Netherlands' where kid=?", (kid,))
    G.c.commit()
    out = tmp_path / "d"
    out.mkdir()
    archive_export.coaches(G, str(out), nat=lambda v: {"Netherlands": "هولندا"}.get(v, v))
    assert json.load(open(out / "coaches.json", encoding="utf-8"))[str(kid)]["nat"] == "هولندا"


def test_the_fotmob_clubs_arabic_names_go_out_for_the_profiles(tmp_path):
    G, m2, old = world(tmp_path)
    out = tmp_path / "d"
    out.mkdir()
    archive_export.fm_teams(G, str(out))
    t = json.load(open(out / "fm_teams.json", encoding="utf-8"))
    assert t["102101"] == "الجزيرة" and t["5789"] == "الإمارات"


def test_a_fotmob_club_with_enough_games_gets_its_history_too(tmp_path):
    """24 Nov 2026: Transfermarkt's Djurgården (1,862 games) folds into FotMob's, whose club has no page on the site: the
    archive's club page goes to every club of 30 games, FotMob's too (with its FotMob id; the renderer leaves out the ones
    the site has a page for)"""
    G, m2, old = world(tmp_path)
    out = tmp_path / "d"
    out.mkdir()
    archive_export.clubs(G, str(out), min_matches=1)
    cl = json.load(open(out / "clubs.json", encoding="utf-8"))
    fm = {c.get("fm") for c in cl.values()}
    assert {102117, 102101} <= fm                                  # al Ain and al Jazira: FotMob's clubs, now written with their id
