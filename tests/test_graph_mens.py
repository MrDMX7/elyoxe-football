"""graph/load/mens.py: Tifo is men's football (the owner, 23 Nov 2026: «كرة القدم النسائية ماباها»). Every women's competition
or award leaves the graph with its editions and honours; a woman with no other record then has no profile."""
from graph.db import Graph
from graph.ids import Registry
from graph.load import mens


def test_womens_competitions_and_awards_leave_with_their_editions_and_honours(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    for cid, name, kind in ((1, "Bundesliga", "league"), (2, "Frauen Bundesliga", "league"), (3, "The Best FIFA Women's Player", "award"),
                            (4, "Ballon d'Or Féminin", "award"), (5, "Ballon d'Or", "award"), (9, "Supercopa (W)", "cup"), (6, "Icelandic Footballer of the Year — Men", "award")):
        G.put("competition", {"cid": cid, "name": name, "kind": kind}, "x")
        G.put("edition", {"eid": cid * 10, "cid": cid, "season": "2020"}, "x")
        G.c.execute("insert into honour(eid, kind, rank, pid, src) values(?, 'winner', 1, ?, 'x')", (cid * 10, cid))
    G.put("team", {"tid": 7, "name": "Netherlands", "name_ar": "هولندا (W)", "kind": "national"}, "x")
    G.put("competition", {"cid": 8, "name": "Algarve Cup", "kind": "cup"}, "x")            # a women's tournament by its teams
    G.put("edition", {"eid": 80, "cid": 8, "season": "2020"}, "x")
    G.c.execute("insert into honour(eid, kind, rank, tid, src) values(80, 'champion', 1, 7, 'x')")
    G.c.commit()
    out = mens.load(G, reg, None)
    assert sorted(c for (c,) in G.c.execute("select cid from competition")) == [1, 5, 6]
    assert sorted(e for (e,) in G.c.execute("select eid from edition")) == [10, 50, 60]
    assert sorted(e for (e,) in G.c.execute("select eid from honour")) == [10, 50, 60]
    assert out["competitions"] == 5


def squads(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    for tid, name in ((1, "Arsenal"), (2, "Chelsea"), (3, "Durham Women FC"), (4, "Arsenal"), (5, "Portland Thorns"), (6, "Frauenfeld")):
        G.put("team", {"tid": tid, "name": name, "kind": "club"}, "fotmob")
        G.xref("team", tid, "fotmob", tid, "fotmob-native")
    G.put("match", {"mid": 1, "date": "2020-01-01", "home": 1, "away": 2, "hs": 1, "as_": 0}, "fotmob")
    for pid in range(10, 20):
        G.put("player", {"pid": pid, "name": f"P{pid}"}, "fotmob")
        G.xref("player", pid, "fotmob", pid, "fotmob-native")
    spell = lambda pid, tid: G.many("spell", [{"pid": pid, "tid": tid, "start": f"20{pid}-01-01"}], "fotmob")
    return G, spell


def test_a_womens_side_and_its_players_leave_with_their_spells_and_honours(tmp_path):
    G, spell = squads(tmp_path)
    spell(10, 1)                                   # a man of Arsenal
    for pid in (11, 12, 13, 15):                   # four women: Durham, then the second «Arsenal» and Portland Thorns
        spell(pid, 3), spell(pid, 4), spell(pid, 5)
    spell(14, 5)                                   # known a woman by her squad alone
    spell(11, 1)                                   # FotMob filed one of her spells under the men's record
    G.put("competition", {"cid": 5, "name": "IFFHS World's Best Player", "kind": "award"}, "x")
    G.put("edition", {"eid": 50, "cid": 5, "season": "2020"}, "x")
    G.c.execute("insert into honour(eid, kind, rank, pid, src) values(50, 'winner', 1, 10, 'x')")
    G.c.execute("insert into honour(eid, kind, rank, pid, src) values(50, 'winner', 2, 12, 'x')")
    out = mens.load(G, Registry(), None)
    assert sorted(t for (t,) in G.c.execute("select tid from team")) == [1, 2, 6]
    assert sorted(p for (p,) in G.c.execute("select pid from player")) == [10, 16, 17, 18, 19]
    assert G.c.execute("select pid, tid from spell").fetchall() == [(10, 1)]
    assert G.c.execute("select pid from honour").fetchall() == [(10,)]
    assert not G.c.execute("select 1 from xref where (type='team' and tifo_id in (3, 4, 5)) or (type='player' and tifo_id in (11, 12, 13, 14, 15))").fetchone()
    assert (out["sides"], out["players"]) == (3, 5)


def test_a_man_with_games_keeps_his_record_and_a_side_with_games_is_never_a_womens_side(tmp_path):
    G, spell = squads(tmp_path)
    spell(10, 3)                                   # FotMob's slip: a man with a spell at a women's side
    G.many("appearance", [{"mid": 1, "pid": 10, "tid": 1, "played": 1}], "fotmob")
    G.put("team", {"tid": 7, "name": "Hibernian LFC", "kind": "club"}, "fotmob")
    G.put("match", {"mid": 2, "date": "2020-01-02", "home": 7, "away": 2, "hs": 1, "as_": 0}, "fotmob")
    for pid in (15, 16, 17):                       # a small club without a game and with a squad of men stays
        spell(pid, 6)
    mens.load(G, Registry(), None)
    assert sorted(t for (t,) in G.c.execute("select tid from team")) == [1, 2, 4, 5, 6, 7]
    assert G.c.execute("select count(*) from player").fetchone()[0] == 10
    assert G.c.execute("select tid from spell where pid=10").fetchall() == []


def test_the_leagues_and_awards_named_by_their_initials_leave_too(tmp_path):
    for name in ("NWSL", "NWSL Challenge Cup", "Liga F", "Liga F Golden Boot", "Eredivisie Vrouwen", "Copa De La Reina", "WSL Hall of Fame"):
        assert mens.WOMEN.search(name), name
    for name in ("LaLiga", "Liga FUTVE", "Liga Femsa", "Copa del Rey", "Eredivisie", "FC Frauenfeld Cup"):
        assert not mens.WOMEN.search(name), name
    for name in ("FC Frauenfeld", "Frauental", "Trefelin Boys & Girls Club", "Liverpool"):
        assert not mens.WOMENS_SIDE.search(name), name


def test_a_competition_only_its_arabic_name_calls_womens_leaves(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    G.put("competition", {"cid": 1, "name": "Toppserien", "name_ar": "الدوري النرويجي للسيدات", "kind": "league"}, "fotmob")
    G.put("competition", {"cid": 2, "name": "Northern Super League", "name_ar": "الدوري الكندي ( سيدات )"}, "fotmob")
    G.put("competition", {"cid": 3, "name": "Eliteserien", "name_ar": "الدوري النرويجي الممتاز", "kind": "league"}, "fotmob")
    mens.load(G, Registry(), None)
    assert [c for (c,) in G.c.execute("select cid from competition")] == [3]
