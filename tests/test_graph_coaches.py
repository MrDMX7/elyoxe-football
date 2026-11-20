import gzip, json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import coaches


def setup(tmp_path):
    t = tmp_path / "db" / ".cache" / "fm" / "t"
    t.mkdir(parents=True)
    hist = {"coachHistory": [{"id": 1, "name": "Abel Braga", "season": "2015/2016", "leagueId": 538, "win": 1, "draw": 1, "loss": 0},
                             {"id": 2, "name": "Henk ten Cate", "season": "2015/2016", "leagueId": 538, "win": 1, "draw": 0, "loss": 0}],
            "trophyList": [{"name": "Pro League", "leagueId": "538", "won": 1, "runnerup": 1, "seasonsWon": "2015/2016", "seasonsRunnerup": "2013/2014"}]}
    (t / "102101.json.gz").write_bytes(gzip.compress(json.dumps({"details": {"id": 102101, "name": "Al Jazira"}, "history": hist}).encode()))
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    jaz, opp = reg.mint("team", "fotmob", 102101), reg.mint("team", "fotmob", 999)
    lg = reg.mint("competition", "fotmob", 538)
    e = reg.mint("edition", "fotmob", "538|2015/2016")
    G.put("edition", {"eid": e, "cid": lg, "season": "2015/2016"}, "fotmob")
    mids = []
    for k, (d, hs, as_) in enumerate((("2015-09-01", 2, 0), ("2015-10-01", 1, 1), ("2016-02-01", 3, 0))):
        mid = reg.mint("match", "fotmob", 10 + k)
        G.put("match", {"mid": mid, "eid": e, "date": d, "home": jaz, "away": opp, "hs": hs, "as_": as_}, "fotmob")
        mids.append(mid)
    tm_kid = reg.mint("coach", "tm-name", "henk ten cate")
    G.put("coach", {"kid": tm_kid, "name": "Henk ten Cate"}, "tm")
    G.c.execute("insert into match_coach values(?, 'h', ?, 'tm')", (mids[2], tm_kid))
    return G, reg, Sources(str(tmp_path), s3=False), mids, e, jaz


def test_fotmob_coach_history_assigns_matches_in_order(tmp_path):
    G, reg, S, mids, e, jaz = setup(tmp_path)
    out = coaches.load(G, reg, S)
    got = [G.c.execute("select c.name from match_coach x join coach c on c.kid=x.kid where x.mid=? and x.side='h'", (m,)).fetchone()[0] for m in mids]
    assert got == ["Abel Braga", "Abel Braga", "Henk ten Cate"]
    assert out["matches_assigned"] == 3
    assert reg.get("coach", "tm-name", "henk ten cate") == reg.get("coach", "fotmob", 2)     # Transfermarkt's name joins FotMob's coach


def test_fotmob_trophy_list_gives_champions_and_runners_up(tmp_path):
    G, reg, S, mids, e, jaz = setup(tmp_path)
    coaches.load(G, reg, S)
    assert G.c.execute("select tid from honour where eid=? and kind='champion'", (e,)).fetchone()[0] == jaz
    e14 = G.c.execute("select eid from edition where season='2013/2014'").fetchone()[0]
    assert G.c.execute("select tid, src from honour where eid=? and kind='runner_up'", (e14,)).fetchone() == (jaz, "fotmob")


def test_spells_from_the_matches(tmp_path):
    from graph import publish
    G, reg, S, mids, e, jaz = setup(tmp_path)
    coaches.load(G, reg, S)
    G.xref("team", jaz, "fotmob", 102101, "fotmob-native")
    out = publish.coaches(G, str(tmp_path / "o"))
    d = json.load(open(tmp_path / "o" / "coaches" / "teams.json", encoding="utf-8"))["102101"]
    assert [(s["name"], s["start"], s["end"], s["m"], s["w"], s["d"], s["l"]) for s in d] == [
        ("Henk ten Cate", "2016-02-01", "2016-02-01", 1, 1, 0, 0), ("Abel Braga", "2015-09-01", "2015-10-01", 2, 1, 1, 0)]


def test_a_name_only_coach_joins_the_clubs_fotmob_coach_of_that_name(tmp_path):
    G, reg, S, mids, e, jaz = setup(tmp_path)
    cwc = reg.mint("match", "tm", "777")                                  # a cup match: no coachHistory row covers it
    G.put("match", {"mid": cwc, "date": "2015-12-10", "home": jaz, "away": 5, "hs": 1, "as_": 0}, "tm")
    braga_tm = reg.mint("coach", "tm-name", "abel braga")
    G.put("coach", {"kid": braga_tm, "name": "Abel Braga"}, "tm")
    G.c.execute("insert into match_coach values(?, 'h', ?, 'tm')", (cwc, braga_tm))
    coaches.load(G, reg, S)
    assert reg.get("coach", "tm-name", "abel braga") == reg.get("coach", "fotmob", 1)


def test_a_national_team_spell_survives_the_gaps_between_tournaments(tmp_path):
    from graph import publish
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    ger, opp, kid = reg.mint("team", "fotmob", 8570), reg.mint("team", "fotmob", 1), reg.mint("coach", "fotmob", 78652)
    G.put("team", {"tid": ger, "name": "Germany", "kind": "national"}, "fotmob")
    G.put("coach", {"kid": kid, "name": "Joachim Löw"}, "fotmob")
    G.xref("team", ger, "fotmob", 8570, "fotmob-native")
    for k, d in enumerate(("2010-07-10", "2012-02-29", "2013-10-15")):          # 600 days between the first two: one spell on a national bench
        mid = reg.mint("match", "fotmob", 50 + k)
        G.put("match", {"mid": mid, "date": d, "home": ger, "away": opp, "hs": 1, "as_": 0}, "fotmob")
        G.c.execute("insert into match_coach values(?, 'h', ?, 'fotmob')", (mid, kid))
    publish.coaches(G, str(tmp_path / "o"))
    d = json.load(open(tmp_path / "o" / "coaches" / "teams.json", encoding="utf-8"))["8570"]
    assert [(s["start"], s["end"], s["m"]) for s in d] == [("2010-07-10", "2013-10-15", 3)]


def test_a_cup_match_between_two_of_a_coachs_league_matches_is_his():
    G, reg = Graph(str(tmp_path_db := __import__("tempfile").mkdtemp()) + "/t.db"), Registry()
    ain, opp, crespo, schreuder = 1, 2, 10, 11
    days = [("2023-09-01", schreuder), ("2023-11-26", crespo), ("2024-02-13", None), ("2024-03-01", crespo), ("2024-05-25", None),
            ("2024-06-30", None)]                       # Feb: an ACL tie between two league matches; May: after his last one, unknown
    for k, (d, kid) in enumerate(days):
        mid = reg.mint("match", "fotmob", 70 + k)
        G.put("match", {"mid": mid, "date": d + "T15:00:00Z", "home": ain, "away": opp, "hs": 1, "as_": 0}, "fotmob")
        if kid:
            G.c.execute("insert into match_coach values(?, 'h', ?, 'fotmob')", (mid, kid))
    out = coaches.fill_between(G)
    got = [r[0] for r in G.c.execute("select x.kid from match m left join match_coach x on x.mid=m.mid and x.side='h' order by m.date")]
    assert got == [schreuder, crespo, crespo, crespo, None, None] and out == 1
    G.c.execute("insert into match_coach values((select mid from match where date like '2024-06-30%'), 'h', ?, 'fotmob')", (schreuder,))
    assert coaches.fill_between(G) == 0                  # between Crespo and another coach: the handover is not guessed


def test_the_lineups_coach_is_never_replaced_by_the_league_history(tmp_path):
    G, reg, S, mids, e, jaz = setup(tmp_path)
    caretaker = reg.mint("coach", "fotmob", 99)
    G.put("coach", {"kid": caretaker, "name": "Caretaker"}, "fotmob")
    G.c.execute("insert into match_coach values(?, 'h', ?, 'fotmob-lineup')", (mids[1], caretaker))
    coaches.load(G, reg, S)
    got = [G.c.execute("select c.name from match_coach x join coach c on c.kid=x.kid where x.mid=? and x.side='h'", (m,)).fetchone()[0] for m in mids]
    assert got == ["Abel Braga", "Caretaker", "Henk ten Cate"]


def _trophies(tmp_path, lists):
    t = tmp_path / "db" / ".cache" / "fm" / "t"
    t.mkdir(parents=True)
    for fid, trophies in lists.items():
        (t / f"{fid}.json.gz").write_bytes(gzip.compress(json.dumps({"details": {"id": fid, "name": str(fid)}, "history": {"coachHistory": [], "trophyList": trophies}}).encode()))
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    for fid in lists:
        reg.mint("team", "fotmob", fid)
    return G, reg, Sources(str(tmp_path), s3=False)


def test_a_trophy_with_no_competition_is_not_a_title_of_one_shared_competition(tmp_path):
    G, reg, S = _trophies(tmp_path, {1: [{"name": "Regional Cup", "leagueId": "-1", "won": 1, "seasonsWon": "1950"}],
                                     2: [{"name": "Other Cup", "leagueId": "-1", "won": 1, "seasonsWon": "1950"}]})
    out = coaches.load(G, reg, S)
    assert G.c.execute("select count(*) from honour").fetchone()[0] == 0 and out["conflicts"] == 0


def test_two_clubs_fotmob_both_names_champions_of_one_season_are_co_champions(tmp_path):
    G, reg, S = _trophies(tmp_path, {451: [{"name": "Liga Profesional", "leagueId": "112", "won": 1, "seasonsWon": "2003/2004"}],
                                     453: [{"name": "Liga Profesional", "leagueId": "112", "won": 1, "seasonsWon": "2003/2004"}]})
    out = coaches.load(G, reg, S)                                         # Apertura and Clausura: two champions, no conflict
    got = sorted(t for (t,) in G.c.execute("select tid from honour where kind='champion'"))
    assert got == sorted([reg.get("team", "fotmob", 451), reg.get("team", "fotmob", 453)]) and out["conflicts"] == 0


def test_another_sources_champion_with_the_same_name_is_the_same_club(tmp_path):
    G, reg, S = _trophies(tmp_path, {8000: [{"name": "Carioca", "leagueId": "10272", "won": 1, "seasonsWon": "1989"}],
                                     8001: [{"name": "Carioca", "leagueId": "10272", "won": 1, "seasonsWon": "1990"}]})
    fm, other = reg.get("team", "fotmob", 8000), reg.get("team", "fotmob", 8001)
    G.put("team", {"tid": fm, "name": "Botafogo"}, "fotmob")
    G.put("team", {"tid": other, "name": "Flamengo"}, "fotmob")
    lg = reg.mint("competition", "fotmob", 10272)
    for season, (sid, name) in (("1989", ("365-bota", "Botafogo")), ("1990", ("365-vasco", "Vasco da Gama"))):
        t = reg.mint("team", "s365", sid)
        G.put("team", {"tid": t, "name": name}, "s365")
        G.xref("team", t, "s365", sid, "s365-native")
        e = reg.mint("edition", "s365", f"10272|{season}")
        G.put("edition", {"eid": e, "cid": lg, "season": season}, "s365")
        G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'champion', 1, ?, 's365')", (e, t))
    out = coaches.load(G, reg, S)
    assert reg.get("team", "s365", "365-bota") == reg.get("team", "fotmob", 8000)      # one Botafogo now
    assert out["conflicts"] == 1                                                     # Vasco against Flamengo stays a disagreement


def test_two_spellings_of_one_club_across_sources_are_one_club(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    a, b, c = reg.mint("team", "s365", "x"), reg.mint("team", "fotmob", 1), reg.mint("team", "fotmob", 2)
    G.put("team", {"tid": a, "name": "America MG"}, "s365")
    G.xref("team", a, "s365", "x", "s365-native")
    G.put("team", {"tid": b, "name": "America Mineiro"}, "fotmob")
    G.put("team", {"tid": c, "name": "KuPS"}, "fotmob")
    assert not coaches.same_club(G, reg, a, c)
    G.c.execute("update team set name='America-MG' where tid=?", (b,))
    assert coaches.same_club(G, reg, a, b)                                       # «America MG» and «America-MG»
    G.c.execute("update team set name='RoPS Rovaniemi' where tid=?", (b,))
    G.c.execute("update team set name='RoPS Rovaniemen' where tid=?", (a,))
    assert coaches.same_club(G, reg, a, b)
