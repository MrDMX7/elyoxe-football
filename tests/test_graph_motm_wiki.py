import os
from graph.motm_wiki import official_motm

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def test_a_world_cup_group_page_gives_each_match_its_official_man_of_the_match():
    rows = official_motm(open(os.path.join(FIX, "motm_wc2022_group_a.html"), "rb").read())
    assert [(r["date"], r["home"], r["away"], r["person"], r["name"]) for r in rows] == [
        ("2022-11-20", "Qatar", "Ecuador", "Enner Valencia", "Enner Valencia"),
        ("2022-11-21", "Senegal", "Netherlands", "Cody Gakpo", "Cody Gakpo")]
    assert rows[0]["score"] == (0, 2)


def test_a_box_with_no_man_of_the_match_gives_no_row_and_does_not_borrow_the_next_ones():
    h = (b'<html><body><div class="footballbox"><span class="bday dtstart">2010-06-11</span><table><tr><th class="fhome"><a title="A">A</a></th>'
         b'<th class="fscore">1\xe2\x80\x931</th><th class="faway"><a title="B">B</a></th></tr></table></div>'
         b'<div class="footballbox"><span class="bday dtstart">2010-06-12</span><table><tr><th class="fhome"><a title="C">C</a></th>'
         b'<th class="fscore">2\xe2\x80\x930</th><th class="faway"><a title="D">D</a></th></tr></table></div>'
         b'<p><b>Player of the Match:</b><br/><a rel="mw:WikiLink" href="./X_Y" title="X Y">X Y</a> (C)</p></body></html>')
    assert [(r["home"], r["person"]) for r in official_motm(h)] == [("C", "X Y")]


import gzip, json
from graph.awards_fetch import _key
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import official_motm as OM, motm


def _world(tmp_path, items=None):
    d = tmp_path / "graph" / ".cache" / "awards"
    (d / "pages").mkdir(parents=True)
    (d / "pages" / (_key("2022 FIFA World Cup Group A") + ".html.gz")).write_bytes(
        gzip.compress(open(os.path.join(FIX, "motm_wc2022_group_a.html"), "rb").read()))
    (d / "pages.json").write_text(json.dumps({"2022 FIFA World Cup Group A": {"fetched": "2026-11-21"}}))
    (d / "items.json").write_text(json.dumps(items or {}), encoding="utf-8")
    S = Sources(str(tmp_path), mirror=str(tmp_path / "mirror"), s3=False)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    for tid, n in ((1, "Qatar"), (2, "Ecuador"), (3, "Senegal"), (4, "Netherlands")):
        G.put("team", {"tid": tid, "name": n, "kind": "national"}, "fotmob")
    G.put("match", {"mid": 10, "date": "2022-11-20", "home": 1, "away": 2, "hs": 0, "as_": 2}, "fotmob")
    G.put("match", {"mid": 11, "date": "2022-11-21", "home": 3, "away": 4, "hs": 0, "as_": 2}, "fotmob")
    for pid, n in ((100, "Enner Valencia"), (101, "Moisés Caicedo"), (200, "Cody Gakpo")):
        G.put("player", {"pid": pid, "name": n}, "fotmob")
    G.c.executemany("INSERT INTO appearance(mid, pid, tid, played, rating, src) VALUES(?,?,?,1,?,'fotmob')",
                    [(10, 100, 2, 8.1), (10, 101, 2, 8.9)])
    return S, G, reg


def test_the_official_award_ties_to_the_match_and_the_man_in_its_lineup_and_outranks_the_rating(tmp_path):
    S, G, reg = _world(tmp_path)
    out = OM.load(G, reg, S, titles=["2022 FIFA World Cup Group A"])
    motm.load(G, reg, S)                                  # Caicedo rated higher: the organiser's award stays
    assert G.c.execute("select pid, tid, src from match_award where mid=10 and kind='motm'").fetchone() == (100, 2, "official")
    assert out["linked"] >= 1


def test_a_man_not_in_the_lineup_is_found_by_his_wikidata_item(tmp_path):
    S, G, reg = _world(tmp_path, {"Cody_Gakpo": {"qid": "Q7", "en": "Cody Gakpo", "ar": "كودي خاكبو", "human": True, "born": "1999-05-07", "tm_player": None}})
    reg.link("player", "wikidata", "Q7", reg.mint("player", "fotmob", 9))
    pid = reg.get("player", "wikidata", "Q7")
    OM.load(G, reg, S, titles=["2022 FIFA World Cup Group A"])
    assert G.c.execute("select pid, tid from match_award where mid=11 and kind='motm'").fetchone() == (pid, 4)


def test_an_award_whose_match_or_score_is_not_ours_is_left_out(tmp_path):
    S, G, reg = _world(tmp_path)
    G.c.execute("update match set as_=3 where mid=10")   # 0-3 in our match, 0-2 on the page: not the same game
    out = OM.load(G, reg, S, titles=["2022 FIFA World Cup Group A"])
    assert G.c.execute("select count(*) from match_award where mid=10").fetchone()[0] == 0
    assert out["no_match"] >= 1


def test_one_surname_is_not_one_man():
    assert OM.same_man("Enner Valencia", "Enner Valencia") and OM.same_man("Júlio César", "Julio Cesar")
    assert OM.same_man("Cristiano Ronaldo", "Cristiano Ronaldo dos Santos Aveiro")
    assert not OM.same_man("Enner Valencia", "Antonio Valencia") and not OM.same_man("Valencia", "Enner Valencia")


def test_the_page_list_spells_every_group_and_stage():
    from graph.motm_wiki import pages
    ps = pages()
    assert "2022 FIFA World Cup Group H" in ps and "2002 FIFA World Cup knockout stage" in ps and "UEFA Euro 2024 Group F" in ps
    assert "2023 AFC Asian Cup Group F" in ps and "2015 FIFA Club World Cup" in ps and "2025 FIFA Club World Cup Group H" in ps
    assert len(ps) == len(set(ps)) > 200


def test_a_box_dated_only_in_words_still_has_its_date():
    from graph.motm_wiki import _date
    assert _date("9 January 2015") == "2015-01-09" and _date("June 3, 2002") == "2002-06-03" and _date("tbd") is None


def test_a_country_spelled_two_ways_is_one_team():
    assert OM.same_team("United States", "USA") and OM.same_team("Czech Republic", "Czechia") and OM.same_team("Turkey", "Türkiye")
    assert OM.same_team("United Arab Emirates", "UAE") and OM.same_team("Qatar", "Qatar") and not OM.same_team("Qatar", "Oman")


def test_one_game_held_twice_gets_the_award_on_the_record_with_its_lineup(tmp_path):
    S, G, reg = _world(tmp_path)
    G.put("match", {"mid": 9, "date": "2022-11-20", "home": 1, "away": 2, "hs": 0, "as_": 2}, "tm")   # the same game, no lineup
    OM.load(G, reg, S, titles=["2022 FIFA World Cup Group A"])
    assert G.c.execute("select mid, pid from match_award where kind='motm' and mid in (9, 10)").fetchall() == [(10, 100)]
