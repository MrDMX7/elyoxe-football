"""graph/load/people.py: one player who reached us from several sources (Wikipedia's award lists, martj42's internationals,
Fjelstul's World Cups, FotMob) is one record. Rebuilt every build from the rules, never written to the registry."""
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import people

P = people.Person


def test_same_name_and_birth_date_is_one_player_the_fotmob_one_kept():
    got = people.pairs([P(1, "ismail matar", "1983-04-07", frozenset(), None, None, False),
                        P(2, "ismail matar", "1983-04-07", frozenset({8}), "2010-01-01", "2020-01-01", True)])
    assert got == [(1, 2)]                                        # (drop, keep): the record FotMob knows keeps its id


def test_two_birth_dates_are_two_players():
    assert people.pairs([P(1, "mohamed ahmed", "1990-01-01", frozenset({5}), "2010-01-01", "2012-01-01", False),
                         P(2, "mohamed ahmed", "1985-05-05", frozenset({5}), "2010-01-01", "2012-01-01", False)]) == []


def test_no_birth_date_joins_the_one_who_played_for_the_same_team_in_the_same_years():
    known = P(2, "adnan al talyani", "1964-10-30", frozenset({5789}), "1984-01-01", "1997-01-01", False)
    got = people.pairs([known, P(9, "adnan al talyani", None, frozenset({5789}), "1990-06-09", "1990-06-19", False)])
    assert got == [(9, 2)]
    far = P(9, "adnan al talyani", None, frozenset({5789}), "2015-01-01", "2016-01-01", False)       # 18 years later: not him
    assert people.pairs([known, far]) == []
    other_team = P(9, "adnan al talyani", None, frozenset({77}), "1990-06-09", "1990-06-19", False)
    assert people.pairs([known, other_team]) == []


def test_a_record_with_no_birth_date_and_two_possible_owners_stays_apart():
    a = P(1, "ali hassan", "1980-01-01", frozenset({5}), "2000-01-01", "2005-01-01", False)
    b = P(2, "ali hassan", "1982-01-01", frozenset({5}), "2001-01-01", "2006-01-01", False)
    c = P(3, "ali hassan", None, frozenset({5}), "2003-01-01", "2003-02-01", False)
    assert people.pairs([a, b, c]) == []


def test_names_fold_accents_hyphens_and_the_article():
    assert people.fold("Adnan Al-Talyani") == people.fold("adnan al talyani") == people.fold("Adnán Al Talyani")


def test_the_loader_moves_the_rows_to_the_kept_record(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    uae = reg.mint("team", "fotmob", 5789)
    G.put("team", {"tid": uae, "name": "UAE", "kind": "national"}, "fotmob")
    fm, wd = reg.mint("player", "fotmob", 131661), reg.mint("player", "wikidata", "Q1")
    G.put("player", {"pid": fm, "name": "Ismail Matar", "born": "1983-04-07"}, "fotmob")
    G.xref("player", fm, "fotmob", 131661, "fotmob-native")
    G.put("player", {"pid": wd, "name": "Ismail Matar", "name_ar": "إسماعيل مطر", "born": "1983-04-07"}, "wikidata")
    G.c.execute("insert into honour(eid, kind, rank, pid, src) values(1, 'best_player', 1, ?, 'wiki')", (wd,))
    out = people.load(G, reg, Sources(str(tmp_path), s3=False))
    assert out["merged"] == 1
    assert G.c.execute("select pid, name_ar from player").fetchall() == [(fm, "إسماعيل مطر")]
    assert G.c.execute("select pid from honour").fetchall() == [(fm,)]
    assert reg.get("player", "wikidata", "Q1") == wd                 # the registry is untouched: the next build decides again


def test_the_national_team_record_joins_the_one_who_played_for_that_countrys_clubs_then():
    club = P(6685, "ismail matar", None, frozenset({356}), "2010-12-15", "2024-05-24", True, frozenset({"UAE"}), frozenset())
    intl = P(224053, "ismail matar", None, frozenset({1320}), "2007-10-28", "2016-11-15", False, frozenset(), frozenset({"UAE"}))
    assert people.pairs([club, intl]) == [(224053, 6685)]
    elsewhere = intl._replace(nat_c=frozenset({"QAT"}))
    assert people.pairs([club, elsewhere]) == []


def test_a_profile_with_only_a_birth_date_joins_the_only_player_of_that_name_whose_years_fit():
    club = P(6685, "ismail matar", None, frozenset({356}), "2010-12-15", "2024-05-24", True, frozenset({"UAE"}), frozenset())
    wiki = P(107632, "ismail matar", "1983-04-07", frozenset(), None, None, False)
    assert people.pairs([club, wiki]) == [(107632, 6685)]
    assert people.pairs([club, wiki._replace(born="1940-01-01")]) == []          # 70 at his last match: someone else
    other = P(5, "ismail matar", None, frozenset({9}), "1990-01-01", "1995-01-01", False, frozenset({"EGY"}), frozenset())
    assert people.pairs([club, wiki, other]) == []                                # two players of that name: no guess


def test_two_profiles_of_one_name_never_both_join_one_player():
    club = P(6685, "ismail matar", None, frozenset({356}), "2010-12-15", "2024-05-24", True, frozenset({"UAE"}), frozenset())
    a, b = P(1, "ismail matar", "1983-04-07", frozenset(), None, None, False), P(2, "ismail matar", "1985-01-01", frozenset(), None, None, False)
    assert people.pairs([club, a, b]) == []


def test_remap_many_does_what_remap_does_one_by_one(tmp_path):
    def world(path):
        G, reg = Graph(str(path)), Registry()
        for i in range(1, 7):
            G.put("player", {"pid": i, "name": f"P{i}", "born": "1990-01-01" if i % 2 else None}, "fotmob" if i < 4 else "tm")
            G.xref("player", i, "src", str(i), "x")
        G.many("appearance", [{"mid": 1, "pid": 1, "tid": 9, "played": 1}, {"mid": 1, "pid": 4, "tid": 9, "played": 1},
                              {"mid": 2, "pid": 5, "tid": 9, "played": 1}], "fotmob")
        G.many("event", [{"mid": 2, "seq": 0, "type": "sub", "pid": 5, "pid2": 6}], "fotmob")
        G.c.execute("insert into honour(eid, kind, rank, pid, src) values(1, 'best_player', 1, 6, 'wiki')")
        return G
    a, b = world(tmp_path / "a.db"), world(tmp_path / "b.db")
    for d, k in ((4, 1), (5, 2), (6, 3)):
        a.remap("player", d, k)
    b.remap_many("player", [(4, 1), (5, 2), (6, 3)])
    for sql in ("select * from player order by pid", "select mid, pid from appearance order by 1, 2", "select pid, pid2 from event",
                "select pid from honour", "select tifo_id, source_id from xref order by 2"):
        assert a.c.execute(sql).fetchall() == b.c.execute(sql).fetchall(), sql
