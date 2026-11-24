"""graph/load/same_comp.py: a competition held by several sources' records is one competition, under FotMob's record."""
from graph.build import ORDER
from graph.db import Graph
from graph.ids import Registry
from graph.load import same_comp

CLUBS = (1, 2, 3, 4)


def world(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    for tid in CLUBS:
        G.put("team", {"tid": tid, "name": f"T{tid}", "kind": "club"}, "fotmob")
    return G


def comp(G, cid, name, src, sid=None, kind="league", country="HU"):
    G.put("competition", {"cid": cid, "name": name, "kind": kind, "country": country}, src)
    if sid is not None:
        G.xref("competition", cid, src, sid, "native")


def champions(G, cid, years, src, winner=lambda y: CLUBS[y % 4], label=str):
    for y in years:
        eid = cid * 10000 + y
        G.put("edition", {"eid": eid, "cid": cid, "season": label(y)}, src)
        G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'champion', 1, ?, ?)", (eid, winner(y), src))


def tables(G, cid, years, src, winner=lambda y: CLUBS[y % 4]):
    """a round robin a season: the winner beats everyone, the rest draw"""
    mid = cid * 100000
    for y in years:
        eid = cid * 10000 + y
        G.put("edition", {"eid": eid, "cid": cid, "season": str(y)}, src)
        w = winner(y)
        for h in CLUBS:
            for a in CLUBS:
                if h != a:
                    mid += 1
                    G.put("match", {"mid": mid, "eid": eid, "date": f"{y}-03-{(mid % 27) + 1:02d}", "home": h, "away": a,
                                    "hs": 2 if h == w else 0, "as_": 2 if a == w else 0}, src)


def test_two_champion_lists_of_the_same_winners_are_one_competition_and_fotmobs_record_is_kept(tmp_path):
    G = world(tmp_path)
    comp(G, 900, "NB I", "fotmob", 212)
    comp(G, 50, "Hungarian League", "s365", 77)
    champions(G, 900, range(2001, 2008), "fotmob")
    champions(G, 50, range(2001, 2008), "s365")
    assert same_comp.candidates(G.c) == [(50, 900)]


def test_a_calendar_label_may_sit_a_year_off_a_split_season_one(tmp_path):
    G = world(tmp_path)
    comp(G, 900, "NB I", "fotmob", 212)
    comp(G, 50, "Hungarian League", "s365", 77)
    champions(G, 900, range(2001, 2008), "fotmob", label=lambda y: f"{y - 1}/{y}")
    champions(G, 50, range(2000, 2007), "s365", winner=lambda y: CLUBS[(y + 1) % 4])
    assert same_comp.candidates(G.c) == [(50, 900)]


def test_other_winners_are_another_competition(tmp_path):
    G = world(tmp_path)
    comp(G, 900, "NB I", "fotmob", 212)
    comp(G, 50, "Slovak League", "s365", 77)
    champions(G, 900, range(2001, 2008), "fotmob")
    champions(G, 50, range(2001, 2008), "s365", winner=lambda y: CLUBS[(y + 2) % 4])
    assert same_comp.candidates(G.c) == []


def test_the_games_whose_table_the_listed_champions_top_are_the_lists_competition(tmp_path):
    # schochastics' «hungary»: games and no champion; FotMob's trophy list: champions and no game
    G = world(tmp_path)
    comp(G, 900, "NB I", "fotmob", 212)
    comp(G, 50, "hungary", "sch", "hungary")
    champions(G, 900, range(1951, 1961), "fotmob")
    tables(G, 50, range(1951, 1961), "sch")
    why = []
    assert same_comp.candidates(G.c, explain=why) == [(50, 900)]
    assert why[0].startswith("table")


def test_two_numbers_of_one_source_are_two_competitions(tmp_path):
    # 365Scores lists the league's champions under Poland's Super Cup too (24 Nov 2026)
    G = world(tmp_path)
    comp(G, 50, "Ekstraklasa", "s365", 373, country="PL")
    comp(G, 51, "Super Cup", "s365", 375, country="PL")
    champions(G, 50, range(2001, 2008), "s365")
    champions(G, 51, range(2001, 2008), "s365")
    assert same_comp.candidates(G.c) == []


def test_a_league_and_a_cup_of_a_double_winners_country_stay_two(tmp_path):
    G = world(tmp_path)
    comp(G, 900, "Premier League", "fotmob", 47)
    comp(G, 50, "The FA Cup", "s365", 8, kind="cup")
    champions(G, 900, range(2001, 2008), "fotmob")
    champions(G, 50, range(2001, 2008), "s365")
    assert same_comp.candidates(G.c) == []


def test_a_curated_pair_is_one_and_a_pair_kept_apart_never(tmp_path):
    G = world(tmp_path)
    comp(G, 900, "NB I", "fotmob", 212)
    comp(G, 50, "hungary", "sch", "hungary")
    comp(G, 60, "Hungarian League", "s365", 77)
    champions(G, 900, range(2001, 2008), "fotmob")
    champions(G, 60, range(2001, 2008), "s365")
    assert same_comp.candidates(G.c, fixed=[(50, 900)], never={frozenset((60, 900))}) == [(50, 900)]


def test_a_curated_pair_joins_two_numbers_of_one_source_unless_kept_apart(tmp_path):
    G = world(tmp_path)
    comp(G, 900, "Premier League", "fotmob", 47)
    comp(G, 901, "Premier League Play-off", "fotmob", 9999)
    why = []
    assert same_comp.candidates(G.c, fixed=[(901, 900)], explain=why) == [(901, 900)]
    assert why and why[0].startswith("curated")
    assert same_comp.candidates(G.c, fixed=[(901, 900)], never={frozenset((901, 900))}) == []


def test_the_curated_list_joins_a_sources_league_to_fotmobs_and_makes_fotmobs_record_when_no_loader_did(tmp_path, monkeypatch):
    G, reg = world(tmp_path), Registry()
    cid = reg.mint("competition", "sch", "hungary")
    comp(G, cid, "hungary", "sch", "hungary")
    tables(G, cid, range(1951, 1953), "sch")
    monkeypatch.setattr(same_comp, "curated", lambda: ({"sch|hungary": 212, "sch|nowhere": 999}, []))
    out = same_comp.load(G, reg, None)
    fm = reg.get("competition", "fotmob", 212)
    assert (out["made"], out["merged"]) == (1, 1)
    assert {c for (c,) in G.c.execute("select cid from edition")} == {fm}
    assert [c for (c,) in G.c.execute("select cid from competition")] == [fm]
    assert G.c.execute("select tifo_id from xref where type='competition' and source='fotmob'").fetchall() == [(fm,)]
    assert G.c.execute("select tifo_id from xref where type='competition' and source='sch'").fetchall() == [(fm,)]


def test_a_joined_record_without_a_source_link_gets_one(tmp_path, monkeypatch):
    G, reg = world(tmp_path), Registry()
    cid = reg.mint("competition", "martj42", "AFF Championship")
    G.put("competition", {"cid": cid, "name": "AFF Championship", "kind": "cup"}, "martj42")
    tables(G, cid, range(1996, 1998), "martj42")
    monkeypatch.setattr(same_comp, "curated", lambda: ({"martj42|AFF Championship": 9265}, []))
    same_comp.load(G, reg, None)
    fm = reg.get("competition", "fotmob", 9265)
    assert G.c.execute("select tifo_id, method from xref where type='competition' and source='martj42'").fetchall() == [(fm, "same-comp")]


def test_the_curated_list_joins_a_sources_league_to_another_sources_where_fotmob_has_none(tmp_path, monkeypatch):
    G, reg = world(tmp_path), Registry()
    a, b = reg.mint("competition", "sch", "kenya"), reg.mint("competition", "s365", "5575")
    comp(G, a, "kenya", "sch", "kenya", country="KE")
    comp(G, b, "Premier League", "s365", 5575, country="KE")
    tables(G, a, range(2001, 2003), "sch")
    champions(G, b, range(2009, 2012), "s365")
    monkeypatch.setattr(same_comp, "curated", lambda: ({"sch|kenya": "s365|5575", "sch|nowhere": "s365|1"}, []))
    assert same_comp.load(G, reg, None)["merged"] == 1
    assert [c for (c,) in G.c.execute("select cid from competition")] == [b]         # 365Scores' record carries the name
    assert {c for (c,) in G.c.execute("select cid from edition")} == {b}
    assert G.c.execute("select tifo_id from xref where type='competition' and source='sch'").fetchall() == [(b,)]


def test_every_curated_id_is_a_number_and_no_key_is_listed_twice():
    same, apart = same_comp.curated()
    assert same and all((isinstance(v, int) or "|" in v) and "|" in k for k, v in same.items())
    raw = open(same_comp.CURATED, encoding="utf-8").read()
    keys = [line.split('":')[0].strip() for line in raw.splitlines() if line.startswith('  "')]
    assert len(keys) == len(set(keys))


def test_it_runs_after_every_loader_that_makes_competitions_and_before_the_seasons_are_made_one():
    assert ORDER.index("twins") < ORDER.index("motm") < ORDER.index("same_comp") < ORDER.index("comp_names") < ORDER.index("mens") < ORDER.index("seasons")
