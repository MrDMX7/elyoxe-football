"""graph/load/settle.py: the disagreements between sources that a rule settles — a score that counts the shootout, home and
away swapped, a birth date that is only a year — fixed in the data and taken off the conflict list. The rest stays for review."""
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import settle


def g(tmp_path):
    return Graph(str(tmp_path / "t.db")), Registry()


def match(G, mid, hs, as_, ph=None, pa=None):
    G.put("match", {"mid": mid, "date": "2022-12-09", "home": 1, "away": 2, "hs": hs, "as_": as_, "pen_h": ph, "pen_a": pa}, "tm")


def test_a_score_that_counts_the_shootout_is_the_draw(tmp_path):
    G, reg = g(tmp_path)
    match(G, 1, 5, 3, 4, 2)                                                  # Croatia-Brazil 2022: 1-1, 4-2 on penalties
    G.conflict("match", 1, "score", "5-3", "tm", "1-1", "fjelstul")
    match(G, 2, 0, 2)                                                        # Brazil-Paraguay 2011: 0-0, FotMob kept the shootout
    G.conflict("match", 2, "score", "0-2", "fotmob", "0-0", "martj42")
    out = settle.load(G, reg, Sources(str(tmp_path), s3=False))
    assert G.c.execute("select hs, as_, pen_h, pen_a from match where mid=1").fetchone() == (1, 1, 4, 2)
    assert G.c.execute("select hs, as_, pen_h, pen_a from match where mid=2").fetchone() == (0, 0, 0, 2)
    assert G.c.execute("select count(*) from conflict").fetchone()[0] == 0 and out["shootout"] == 2


def test_the_same_score_the_other_way_round_is_home_and_away_swapped(tmp_path):
    G, reg = g(tmp_path)
    match(G, 1, 0, 2)
    G.conflict("match", 1, "score", "0-2", "fotmob", "2-0", "sch")
    G.conflict("match", 1, "hs", "0", "sch", "2", "sch")                     # the same disagreement field by field
    G.conflict("match", 1, "as_", "2", "sch", "0", "sch")
    out = settle.load(G, reg, Sources(str(tmp_path), s3=False))
    assert G.c.execute("select hs, as_ from match where mid=1").fetchone() == (0, 2)
    assert G.c.execute("select count(*) from conflict").fetchone()[0] == 0 and out["swapped"] == 2


def test_a_real_difference_stays_for_review(tmp_path):
    G, reg = g(tmp_path)
    match(G, 1, 0, 1)                                                        # Karbala-Al Qasim 2022: 0-1 or 1-1
    G.conflict("match", 1, "score", "0-1", "fotmob", "1-1", "sch")
    settle.load(G, reg, Sources(str(tmp_path), s3=False))
    assert G.c.execute("select hs, as_ from match where mid=1").fetchone() == (0, 1)
    assert G.c.execute("select count(*) from conflict").fetchone()[0] == 1


def test_a_birth_date_that_is_only_a_year_gives_way_to_the_full_date(tmp_path):
    G, reg = g(tmp_path)
    G.put("player", {"pid": 1, "name": "A", "born": "2003-01-01"}, "wikidata")
    G.conflict("player", 1, "born", "2003-01-01", "wikidata", "2003-02-18", "fotmob")
    G.put("player", {"pid": 2, "name": "B", "born": "1992-03-16"}, "fotmob")
    G.conflict("player", 2, "born", "1992-03-16", "fotmob", "1992-01-01", "wikidata")
    G.put("player", {"pid": 3, "name": "Keno", "born": "1989-09-10"}, "fotmob")
    G.conflict("player", 3, "born", "1989-09-10", "fotmob", "1991-09-10", "wikidata")
    out = settle.load(G, reg, Sources(str(tmp_path), s3=False))
    assert dict(G.c.execute("select pid, born from player")) == {1: "2003-02-18", 2: "1992-03-16", 3: "1989-09-10"}
    assert [r[0] for r in G.c.execute("select tifo_id from conflict")] == [3] and out["birth_year_only"] == 2


def test_a_birth_date_with_month_zero_is_only_a_year_too(tmp_path):
    G, reg = g(tmp_path)
    G.put("player", {"pid": 1, "name": "A", "born": "1983-09-26"}, "tm")
    G.conflict("player", 1, "born", "1983-09-26", "tm", "1983-00-00", "wikidata")     # Wikidata's year-only, Fjelstul's copy
    G.conflict("player", 1, "born", "1983-09-26", "tm", "1983-00-00", "fjelstul")
    out = settle.load(G, reg, Sources(str(tmp_path), s3=False))
    assert G.c.execute("select born from player").fetchone()[0] == "1983-09-26"
    assert G.c.execute("select count(*) from conflict").fetchone()[0] == 0 and out["birth_year_only"] == 2


def test_one_winner_spelled_two_ways_is_the_same_honour(tmp_path):
    G, reg = g(tmp_path)
    G.conflict("honour", 1, "top_scorer", "bienve maranon", "tifo", "bienvenido maranon morejon", "wiki")
    G.conflict("honour", 2, "top_scorer", "alain kaluyituka dioko", "rsssf", "dioko kaluyituka", "wiki")
    G.conflict("honour", 3, "top_scorer", "mabululo", "tifo", "mabululu", "wiki")
    G.conflict("honour", 4, "top_scorer", "ahmed hassan", "tifo", "hossam salama", "wiki")              # two men: stays
    G.conflict("honour", 5, "top_scorer", "ganiyu bolayi oseni; bienve maranon", "tifo", "bienvenido maranon morejon", "wiki")   # a tie or one: stays
    G.conflict("honour", 6, "top_scorer", "ahmed ali", "tifo", "ahmed ali kamel; hassan ali", "wiki")
    G.conflict("honour", 7, "champion", "8704", "s365", "2663", "fotmob")                                # team ids: not names
    G.conflict("honour", 8, "top_scorer", "106908/None", "earlier", "106909/None", "fjelstul")          # one digit apart, two men
    out = settle.load(G, reg, Sources(str(tmp_path), s3=False))
    assert [r[0] for r in G.c.execute("select tifo_id from conflict order by 1")] == [4, 5, 6, 7, 8] and out["same_names"] == 3


def test_names_that_only_share_a_first_name_are_two_men(tmp_path):
    assert not settle._same_man("mohamed salah", "mohamed elneny") and not settle._same_man("ali", "ali mabkhout")
    assert settle._same_man("Jassim Al Dokhi", "jassim al-dokhi") and settle._same_man("Stabæk", "stabaek")


def test_a_champion_that_is_no_team_of_ours_gives_way_to_the_one_that_is(tmp_path):
    # 365Scores' women's and under-21 champions (Coupe de France Féminine, Eredivisie Vrouwen, Premier League 2) name a side
    # it never gave us; FotMob's is a team we hold
    G, reg = g(tmp_path)
    G.put("team", {"tid": 2663, "name": "Paris Saint Germain"}, "fotmob")
    G.put("team", {"tid": 10, "name": "Lille"}, "fotmob")
    G.put("team", {"tid": 11, "name": "Red Star"}, "fotmob")
    G.c.executemany("insert into honour(eid, kind, rank, tid, src) values(?, 'champion', 1, ?, 's365')", [(1, 8704), (2, 10)])
    G.conflict("honour", 1, "champion", "8704", "s365", "2663", "fotmob")
    G.conflict("honour", 2, "champion", "10", "s365", "11", "fotmob")       # two teams we hold: stays for review
    out = settle.load(G, reg, Sources(str(tmp_path), s3=False))
    assert G.c.execute("select eid, tid from honour order by eid").fetchall() == [(1, 2663), (2, 10)]
    assert [r[0] for r in G.c.execute("select tifo_id from conflict")] == [2] and out["no_such_team"] == 1


def test_a_second_leg_transfermarkt_scored_with_its_shootout_fills_the_shootout(tmp_path):
    # Lille 2-1 Aston Villa, 18 April 2024 (2-2 on aggregate, Villa 4-3 on penalties): Transfermarkt's «5-5» is 2-1 plus 3-4
    G, reg = g(tmp_path)
    for mid, hs, as_ in ((1, 2, 1), (2, 1, 0), (3, 2, 0)):
        G.put("match", {"mid": mid, "date": "2024-04-18", "home": 1, "away": 2, "hs": hs, "as_": as_, "round": "1/4"}, "fotmob")
    G.conflict("match", 1, "score", "2-1", "fotmob", "5-5", "tm")
    G.conflict("match", 2, "score", "1-0", "fotmob", "4-2", "tm")
    G.conflict("match", 3, "score", "2-0", "fotmob", "3-0", "tm")        # one goal more: another count, not a shootout
    out = settle.load(G, reg, Sources(str(tmp_path), s3=False))
    assert G.c.execute("select mid, hs, as_, pen_h, pen_a from match order by mid").fetchall() == [(1, 2, 1, 3, 4), (2, 1, 0, 3, 2), (3, 2, 0, None, None)]
    assert [r[0] for r in G.c.execute("select tifo_id from conflict")] == [3] and out["shootout"] == 2


def test_fotmobs_old_score_with_the_shootout_in_it_gives_way_to_the_real_one(tmp_path):
    # Real Madrid 2-1 Bayern, 25 April 2012 (Bayern 3-1 on penalties): FotMob's old record says «3-4», schochastics 2-1
    G, reg = g(tmp_path)
    G.put("match", {"mid": 1, "date": "2012-04-25", "home": 1, "away": 2, "hs": 3, "as_": 4}, "fotmob")
    G.conflict("match", 1, "score", "3-4", "fotmob", "2-1", "sch")
    settle.load(G, reg, Sources(str(tmp_path), s3=False))
    assert G.c.execute("select hs, as_, pen_h, pen_a from match").fetchone() == (2, 1, 1, 3)
    assert G.c.execute("select count(*) from conflict").fetchone()[0] == 0


def test_more_goal_events_than_goals_drops_the_shootout_kicks_and_the_doubles(tmp_path):
    # FotMob 2011 kept the shootout's kicks as goals at minute 121; a goal kept twice (minute 7, the same man)
    G, reg = g(tmp_path)
    G.put("match", {"mid": 1, "date": "2011-07-16", "home": 1, "away": 2, "hs": 1, "as_": 1}, "fotmob")
    G.put("match", {"mid": 2, "date": "2025-02-07", "home": 1, "away": 2, "hs": 0, "as_": 1}, "fotmob")
    G.put("match", {"mid": 3, "date": "2025-02-08", "home": 1, "away": 2, "hs": 2, "as_": 0}, "fotmob")
    G.many("event", [{"mid": 1, "seq": 0, "minute": 6, "type": "goal", "side": "a"}, {"mid": 1, "seq": 1, "minute": 18, "type": "goal", "side": "h"},
                     {"mid": 1, "seq": 2, "minute": 121, "type": "penalty_goal", "side": "h"}, {"mid": 1, "seq": 3, "minute": 121, "type": "penalty_goal", "side": "a"},
                     {"mid": 2, "seq": 0, "minute": 7, "type": "goal", "side": "a", "pid": 9}, {"mid": 2, "seq": 1, "minute": 7, "type": "goal", "side": "a", "pid": 9},
                     {"mid": 3, "seq": 0, "minute": 7, "type": "goal", "side": "h", "pid": 9}, {"mid": 3, "seq": 1, "minute": 7, "type": "goal", "side": "h", "pid": 9}], "fotmob")
    out = settle.load(G, reg, Sources(str(tmp_path), s3=False))
    got = [r for r in G.c.execute("select mid, count(*) from event group by mid")]
    assert got == [(1, 2), (2, 1), (3, 2)]              # a brace in one minute that the score holds stays
    assert out["extra_goals"] == 3


def test_one_club_under_its_initials_or_a_shorter_name_is_the_same_honour(tmp_path):
    from graph.load.settle import same_club
    assert same_club("kawkab athletique club de marrakech", "kacm") and same_club("kac marrakesh", "kacm")
    assert same_club("kenitra athletic club", "kac kenitra") and same_club("raja casablanca", "raja club athletic")
    assert not same_club("wydad casablanca", "wydad fes") and not same_club("maghreb association sportive fes", "fus rabat")
    assert not same_club("cr belouizdad", "na hussein dey") and not same_club("", "js saoura")
    G, reg = g(tmp_path)
    G.conflict("honour", 1, "runner_up", "kawkab athletic club de marrakech", "table", "kacm", "wiki")
    G.conflict("honour", 2, "runner_up", "maghreb association sportive fes", "table", "fus rabat", "wiki")
    out = settle.load(G, reg, Sources(str(tmp_path), s3=False))
    assert [r[0] for r in G.c.execute("select tifo_id from conflict")] == [2] and out["same_club"] == 1


def test_an_arab_name_in_two_transliterations_is_one_man():
    from graph.load.settle import _same_man
    assert _same_man("tareq al saeed", "tarek el said") and _same_man("mohammed salem al enazi", "mohamed salem al-enezi")
    assert not _same_man("hussein al meri", "mamoun diop") and not _same_man("ali daei", "adel khamis")


def test_a_group_winner_against_the_overall_champion_in_a_league_once_played_in_groups_is_no_disagreement(tmp_path):
    # Ligue 2 until 1992/93: FotMob names every group's winner, 365Scores the overall champion; both are right
    G, reg = g(tmp_path)
    G.put("competition", {"cid": 1, "name": "Ligue 2"}, "s365")
    for eid, season in ((10, "1985/1986"), (11, "1995/1996")):
        G.put("edition", {"eid": eid, "cid": 1, "season": season}, "s365")
        G.conflict("honour", eid, "champion", "5", "s365", "6", "fotmob")
    out = settle.load(G, reg, Sources(str(tmp_path), s3=False))
    assert [r[0] for r in G.c.execute("select tifo_id from conflict")] == [11] and out["group_era"] == 1
