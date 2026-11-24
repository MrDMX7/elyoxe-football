"""graph/load/comp_meta.py: a competition's name, kind, country and scope, set right once every source is in."""
from graph.build import ORDER
from graph.countries import canon
from graph.db import Graph
from graph.ids import Registry
from graph.load import comp_meta


def world(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    G.merged = {}
    return G


def comp(G, cid, name, src=None, sid=None, **more):
    G.put("competition", {"cid": cid, "name": name, **more}, src or "x")
    if src:
        G.xref("competition", cid, src, sid, "native")


def games(G, cid, years, clubs, league=True, national=False):
    """a round robin a season (a league), or one game a pair of clubs (a cup)"""
    for tid in clubs:
        G.put("team", {"tid": tid, "name": f"Club {tid}", "kind": "national" if national else "club"}, "x")
    mid = cid * 100000
    for y in years:
        eid = cid * 10000 + y
        G.put("edition", {"eid": eid, "cid": cid, "season": str(y)}, "x")
        for i, h in enumerate(clubs):
            for a in clubs[i + 1:] if not league else clubs:
                if h != a and (league or (h + a) % 2):
                    mid += 1
                    G.put("match", {"mid": mid, "eid": eid, "date": f"{y}-03-{(mid % 27) + 1:02d}", "home": h, "away": a, "hs": 1, "as_": 0}, "x")


def run(G, tmp_path, text="names: {}\nstages: {}\n"):
    p = tmp_path / "meta.yaml"
    p.write_text(text, encoding="utf-8")
    G.c.commit()
    return comp_meta.load(G, Registry(), None, path=str(p))


def row(G, cid):
    return G.c.execute("SELECT name, name_ar, kind, country, scope FROM competition WHERE cid=?", (cid,)).fetchone()


def test_a_stage_of_a_competition_is_the_competition(tmp_path):
    G = world(tmp_path)
    comp(G, 1, "Major League", "fotmob", 99130, name_ar="الدوري الكبير", kind="league", country="US")
    comp(G, 2, "FotMob 901234", "fotmob", 901234, name_ar="الدوري الكبير")
    G.put("edition", {"eid": 20, "cid": 2, "season": "2024"}, "x")
    G.put("match", {"mid": 5, "eid": 20, "date": "2024-03-01", "home": 1, "away": 2, "hs": 1, "as_": 0}, "x")
    out = run(G, tmp_path)
    assert out["stages_joined"] == 1 and out["unnamed"] == 0
    assert row(G, 2) is None and row(G, 1)[:3] == ("Major League", "الدوري الكبير", "league")
    assert G.c.execute("SELECT cid FROM edition WHERE eid=20").fetchone() == (1,)


def test_a_stage_two_competitions_could_own_stays_and_an_empty_nameless_one_leaves(tmp_path):
    G = world(tmp_path)
    comp(G, 1, "Cup A", "fotmob", 99131, name_ar="الكأس")
    comp(G, 2, "Cup B", "fotmob", 99132, name_ar="الكأس")
    comp(G, 3, "FotMob 901235", "fotmob", 901235, name_ar="الكأس")
    comp(G, 4, "FotMob 901236", "fotmob", 901236)
    out = run(G, tmp_path)
    assert out["stages_joined"] == 0 and out["stages_removed"] == 1
    assert row(G, 3) is not None and row(G, 4) is None


def test_the_list_names_the_parent_of_a_stage(tmp_path):
    G = world(tmp_path)
    comp(G, 1, "Champions League", "fotmob", 99525, name_ar="دوري أبطال آسيا للنخبة")
    comp(G, 2, "FotMob 901237", "fotmob", 901237, name_ar="دوري أبطال آسيا")
    out = run(G, tmp_path, 'names: {}\nstages:\n  "دوري أبطال آسيا": 99525\n')
    assert out["stages_joined"] == 1 and row(G, 2) is None


def test_the_country_is_written_one_way_and_a_region_is_a_scope(tmp_path):
    G = world(tmp_path)
    comp(G, 1, "Süper Lig", country="TUR")
    comp(G, 2, "Série A", country="Brazil")
    comp(G, 3, "Asian Cup", country="Asia")
    comp(G, 4, "World Thing", country="INT")
    run(G, tmp_path)
    assert row(G, 1)[3:] == ("TR", "national") and row(G, 2)[3:] == ("BR", "national")
    assert row(G, 3)[3:] == (None, "asia") and row(G, 4)[3:] == (None, "international")


def test_the_home_nations_and_the_countries_that_are_no_more_keep_their_codes():
    assert [canon(x) for x in ("GB-ENG", "gb-sct", "SU", "USSR", "Yugoslavia", "TAH", "TCH")] == ["GB-ENG", "GB-SCT", "SU", "SU", "YU", "PF", "CS"]
    assert canon("Asia") is None and canon(canon("England")) == canon("England")


def test_a_league_known_by_its_slug_takes_the_name_of_its_country(tmp_path):
    G = world(tmp_path)
    comp(G, 1, "burkina-faso", "sch", "burkina-faso", country="BF", name_ar="الدوري البوركيني الممتاز")
    comp(G, 2, "guam", "sch", "guam", country="GU")
    run(G, tmp_path)
    assert row(G, 1)[0] == "Burkina Faso Premier League" and row(G, 2)[0] == "Guam League"


def test_the_kind_follows_the_games_and_the_name(tmp_path):
    G = world(tmp_path)
    comp(G, 1, "Liga Mayor", kind="cup", country="DO")
    games(G, 1, range(2001, 2005), [11, 12, 13, 14, 15, 16])
    comp(G, 2, "Taça Nacional", kind="league", country="PT")
    games(G, 2, range(2001, 2005), [21, 22, 23, 24, 25, 26, 27, 28], league=False)
    comp(G, 3, "Supercopa Norte", kind="cup", country="CL")
    comp(G, 4, "Gulf Nations", kind="cup")
    games(G, 4, range(2001, 2003), [41, 42, 43, 44], national=True)
    comp(G, 5, "Second Division")
    comp(G, 6, "Champions League Qualification")
    out = run(G, tmp_path)
    assert [row(G, i)[2] for i in (1, 2, 3, 4, 5, 6)] == ["league", "cup", "supercup", "tournament", "league", None]
    assert row(G, 4)[4] == "international"
    assert (out["kind_league"], out["kind_cup"], out["kind_supercup"], out["kind_tournament"]) == (2, 1, 1, 1)


def test_an_award_is_never_retyped(tmp_path):
    G = world(tmp_path)
    comp(G, 1, "Super Cup Player of the Year", kind="award")
    run(G, tmp_path)
    assert row(G, 1)[2] == "award"


def test_a_competition_without_a_country_takes_its_clubs(tmp_path):
    G = world(tmp_path)
    comp(G, 1, "Primera", kind="league", country="CL")
    games(G, 1, range(2001, 2003), [11, 12, 13, 14])
    comp(G, 2, "Copa Vieja", kind="cup")
    games(G, 2, range(2001, 2003), [11, 12, 13, 14], league=False)
    out = run(G, tmp_path)
    assert row(G, 2)[3:] == ("CL", "national") and out["countries_found"] == 1


def test_the_list_is_written_over_everything(tmp_path):
    G = world(tmp_path)
    comp(G, 1, "FotMob 99463", "fotmob", 99463, kind="league")
    comp(G, 2, "Friendly Things", "martj42", "Friendly Things")
    out = run(G, tmp_path, 'names:\n  "fotmob|99463": {name: "Armenian Cup", name_ar: "كأس أرمينيا", kind: cup, country: ARM}\n'
                           '  "martj42|Friendly Things": {kind: friendly}\n  "tm|GONE": {name: "Nothing"}\nstages: {}\n')
    assert row(G, 1) == ("Armenian Cup", "كأس أرمينيا", "cup", "AM", "national") and row(G, 2)[2] == "friendly"
    assert out["curated"] == 2 and out["unnamed"] == 0


def test_a_name_two_competitions_share_takes_the_country(tmp_path):
    G = world(tmp_path)
    comp(G, 1, "Super Cup", name_ar="كأس السوبر", country="MD")
    comp(G, 2, "Super Cup", name_ar="كأس السوبر", country="LB")
    comp(G, 3, "Lebanon Cup", name_ar="كأس لبنان", country="LB")
    comp(G, 4, "Lebanon Cup", name_ar="كأس النخبة", country="LB")
    out = run(G, tmp_path)
    assert row(G, 1)[:2] == ("Moldova Super Cup", "كأس السوبر (مولدوفا)")
    assert row(G, 2)[:2] == ("Lebanon Super Cup", "كأس السوبر (لبنان)")
    assert row(G, 3)[:2] == ("Lebanon Cup", "كأس لبنان")          # the country is in the name already
    assert out["names_told_apart"] == 4


def test_a_competition_keeps_one_fotmob_number_its_own(tmp_path, monkeypatch):
    G = world(tmp_path)
    comp(G, 1, "Major League", "fotmob", 99130, name_ar="الدوري الكبير", kind="league", country="US")
    comp(G, 2, "FotMob 901234", "fotmob", 901234, name_ar="الدوري الكبير")
    comp(G, 3, "Old Cup", "fotmob", 99700, kind="cup")
    G.xref("competition", 3, "fotmob", 99200, "same-comp")
    G.xref("competition", 3, "fotmob", 99500, "same-comp")
    monkeypatch.setattr(comp_meta, "index_ids", lambda: {"99500"})
    out = run(G, tmp_path)
    ids = lambda src: sorted(G.c.execute("SELECT tifo_id, source_id FROM xref WHERE type='competition' AND source=?", (src,)).fetchall())
    assert ids("fotmob") == [(1, "99130"), (3, "99500")]          # its own before a stage's; the index's before any
    assert ids("fotmob_stage") == [(1, "901234"), (3, "99200"), (3, "99700")] and out["numbers_set_aside"] == 3


def test_it_runs_once_the_competitions_are_one_and_before_the_womens_leave():
    assert ORDER.index("same_comp") < ORDER.index("comp_names") < ORDER.index("comp_meta") < ORDER.index("mens") < ORDER.index("seasons")
