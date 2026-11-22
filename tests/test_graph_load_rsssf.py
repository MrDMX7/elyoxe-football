import json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import rsssf

UAE = {"country": "uae", "league": 538, "source": "RSSSF (rsssf.org)", "seasons": [
    {"season": "1973/1974", "champion": "Al-Oroba", "table": [[1, "Oroba (Sharjah)", None, 2, 1, 1, 0, 4, 1, 3], [2, "Al-Ahly Dubai", 102119, 2, 0, 2, 0, 0, 0, 2]]},
    {"season": "2025/2026", "champion": "Al-Ain", "table": [[1, "Al-Ain", 102117, 26, 21, 5, 0, 62, 18, 68]]}]}


def mk(tmp_path):
    m = tmp_path / "mirror" / "history" / "arab"
    m.mkdir(parents=True)
    (m / "uae.json").write_text(json.dumps(UAE), encoding="utf-8")
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    (db / "rsssf_clubs.json").write_text(json.dumps({"102117": {"positions": [], "matches": [["1995-04-14", 102124, 1, 1, 1, "rsssf:uae:cup"]]}}))
    return Sources(str(tmp_path), mirror=str(tmp_path / "mirror"), s3=False)


def test_rsssf_tables_champions_and_matches(tmp_path):
    S, G, reg = mk(tmp_path), Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League"}, "fotmob")
    have = reg.mint("edition", "fotmob", "538|2025/2026")
    G.put("edition", {"eid": have, "cid": lg, "season": "2025/2026"}, "fotmob")
    out = rsssf.load(G, reg, S, codes=["uae"])
    assert out["standings"] == 3 and out["champions"] == 2 and out["matches"] == 1
    old = G.c.execute("select eid from edition where cid=? and season='1973/1974'", (lg,)).fetchone()[0]
    assert G.c.execute("select rank, played, won, drawn, lost, gf, ga, pts from standing where eid=? order by rank", (old,)).fetchall() == \
        [(1, 2, 1, 1, 0, 4, 1, 3), (2, 2, 0, 2, 0, 0, 0, 2)]
    assert G.c.execute("select tid from honour where eid=? and kind='champion'", (have,)).fetchone()[0] == reg.get("team", "fotmob", 102117)
    oroba = G.c.execute("select tid from standing where eid=? and rank=1", (old,)).fetchone()[0]
    assert G.c.execute("select name from team where tid=?", (oroba,)).fetchone()[0] == "Oroba (Sharjah)"


def test_rsssf_second_build_writes_the_unlinked_clubs_again(tmp_path):
    S, reg = mk(tmp_path), Registry()
    got = []
    for i in range(2):
        G = Graph(str(tmp_path / f"t{i}.db"))
        lg = reg.mint("competition", "fotmob", 538)
        G.put("competition", {"cid": lg, "name": "Pro League"}, "fotmob")
        rsssf.load(G, reg, S, codes=["uae"])
        got.append(G.c.execute("select count(*) from team where src='rsssf'").fetchone()[0])
    assert got[0] == got[1] == 1


def test_the_league_round_by_round_with_its_scorers(tmp_path):
    league = [["1999-12-05", "Al-Wahda", 102122, "Al-Sha'ab", None, 2, 1,
               [["h", "Bouri Lah", 66, "goal"], ["h", "Bouri Lah", 87, "goal"], ["a", "Roberto Nilson", 60, "goal"]]],
              ["2004-01-25", "Al-Nasr", 102123, "Al-Ain", 102117, 0, 5, [["a", "Isaac Nassib", 3, "goal"]] * 5],
              ["2004-02-05", "Sharjah", 102124, "Al-Shabab", None, 1, 2, [["h", "Abdulrahman Fadhel", 78, "own_goal"], ["a", "Giraldo", 68, "goal"], ["a", "Jadilson", 88, "goal"]]]]
    data = dict(UAE, seasons=[{"season": "1999/2000", "champion": "Al-Ain", "table": [], "league_matches": league[:1]},
                              {"season": "2003/2004", "champion": "Al-Ain", "table": [], "league_matches": league[1:]}])
    S = mk(tmp_path)
    (tmp_path / "mirror" / "history" / "arab" / "uae.json").write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / "db" / ".cache" / "rsssf_clubs.json").write_text("{}")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League"}, "fotmob")
    nasr, ain = reg.mint("team", "fotmob", 102123), reg.mint("team", "fotmob", 102117)
    have = reg.mint("match", "sch", "x")                                  # another source has Al-Nasr 0-5 Al-Ain, with no scorers
    G.put("match", {"mid": have, "date": "2004-01-25T15:00:00Z", "home": nasr, "away": ain, "hs": 0, "as_": 5}, "sch")
    out = rsssf.load(G, reg, S, codes=["uae"])
    assert out["league_matches"] == 2 and out["league_linked"] == 1
    assert G.c.execute("select count(*) from match").fetchone()[0] == 3
    assert G.c.execute("select count(*) from event where mid=? and type='goal'", (have,)).fetchone()[0] == 5      # the scorers join it
    m99 = G.c.execute("select m.mid from match m join edition e on e.eid=m.eid where e.season='1999/2000'").fetchone()[0]
    ev = G.c.execute("select e.minute, e.type, e.side, p.name from event e join player p on p.pid=e.pid where e.mid=? order by e.minute", (m99,)).fetchall()
    assert ev == [(60, "goal", "a", "Roberto Nilson"), (66, "goal", "h", "Bouri Lah"), (87, "goal", "h", "Bouri Lah")]
    assert G.c.execute("select goals from appearance a join player p on p.pid=a.pid where a.mid=? and p.name='Bouri Lah'", (m99,)).fetchone()[0] == 2
    own = G.c.execute("select type, side from event where minute=78").fetchone()
    assert own == ("own_goal", "h")


def test_one_bad_row_never_stops_the_loader(tmp_path):
    data = dict(UAE, seasons=[{"season": "2001/2002", "champion": "Al-Ain", "table": [[1, "Al-Ain", 102117, 1, 1, 0, 0, 1, 0, 3]],
                               "league_matches": [["2002-02-30", "Al-Ain", 102117, "Al-Nasr", 102123, 1, 0, []],
                                                  ["2002-03-03", "Al-Ain", 102117, "Al-Wasl", 102111, 2, 0, []]]}])
    S = mk(tmp_path)
    (tmp_path / "mirror" / "history" / "arab" / "uae.json").write_text(json.dumps(data), encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    out = rsssf.load(G, reg, S, codes=["uae"])
    assert out["league_matches"] == 1 and out["league_bad"] == 1 and out["champions"] == 1


def _league(tmp_path, rows):
    data = dict(UAE, seasons=[{"season": "1999/2000", "champion": "Al-Ain", "table": [], "league_matches": rows}])
    S = mk(tmp_path)
    (tmp_path / "mirror" / "history" / "arab" / "uae.json").write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / "db" / ".cache" / "rsssf_clubs.json").write_text("{}")
    return S


def test_two_meetings_of_one_source_stay_two_matches(tmp_path):
    """RSSSF dates both legs of a pairing the same (or next) day: A v B and B v A, or the same pairing listed twice with
    another score, are two meetings, never one match with a score conflict between RSSSF and itself"""
    rows = [["1999-11-05", "Kirkuk", 1, "Al-Jaish", 2, 2, 3, []],
            ["1999-11-05", "Al-Jaish", 2, "Kirkuk", 1, 1, 0, []],          # the return leg, dated the same day
            ["1999-11-06", "Kirkuk", 1, "Al-Jaish", 2, 4, 1, []],          # the pairing again, another score, a day off
            ["1999-11-05", "Kirkuk", 1, "Al-Jaish", 2, 2, 3, []]]          # a true duplicate of row 1: still one match
    S, reg = _league(tmp_path, rows), Registry()
    for i in range(2):                                                   # the second build reuses the registry's ids
        G = Graph(str(tmp_path / f"t{i}.db"))
        out = rsssf.load(G, reg, S, codes=["uae"])
        got = sorted(G.c.execute("select date, hs, as_ from match").fetchall())
        assert got == [("1999-11-05", 1, 0), ("1999-11-05", 2, 3), ("1999-11-06", 4, 1)], got
        assert G.c.execute("select count(*) from conflict where field='score'").fetchone()[0] == 0
        assert out["league_matches"] == 3


def test_a_stale_registry_collapse_is_split(tmp_path):
    """an older build linked the return leg's key to the first leg's id: the return leg now gets an id of its own"""
    rows = [["1999-11-05", "Kirkuk", 1, "Al-Jaish", 2, 2, 3, []],
            ["1999-11-05", "Al-Jaish", 2, "Kirkuk", 1, 1, 0, []]]
    S, G, reg = _league(tmp_path, rows), Graph(str(tmp_path / "t.db")), Registry()
    first = reg.mint("match", "rsssf", "uae|1999-11-05|Kirkuk|Al-Jaish")
    reg.link("match", "rsssf", "uae|1999-11-05|Al-Jaish|Kirkuk", first)
    rsssf.load(G, reg, S, codes=["uae"])
    mids = [r[0] for r in G.c.execute("select mid from match order by hs")]
    assert len(set(mids)) == 2 and first in mids


def test_an_edition_with_a_champion_keeps_it_and_a_different_one_is_a_conflict(tmp_path):
    # Qatar 2010/11 showed «Al-Duhail SC (365Scores) + Lekhwiya (RSSSF)», Tunisia 2022/23 «Etoile du Sahel + Espérance»: one champion
    S, G, reg = mk(tmp_path), Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League"}, "fotmob")
    have = reg.mint("edition", "fotmob", "538|2025/2026")
    G.put("edition", {"eid": have, "cid": lg, "season": "2025/2026"}, "fotmob")
    other = reg.mint("team", "fotmob", 102119)
    G.put("team", {"tid": other, "name": "Shabab Al Ahli"}, "fotmob")
    G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'champion', 1, ?, 's365')", (have, other))
    rsssf.load(G, reg, S, codes=["uae"])
    assert G.c.execute("select tid, src from honour where eid=? and kind='champion'", (have,)).fetchall() == [(other, "s365")]
    assert G.c.execute("select kept, kept_src, other, other_src from conflict where tifo_id=? and field='champion'", (have,)).fetchall() == \
        [("shabab al ahli", "s365", "al ain", "rsssf")]


def test_a_years_season_in_a_league_of_split_seasons_is_the_one_ending_that_year(tmp_path):
    # RSSSF's Kuwait «2001» (March to June 2001) made an edition beside 2000/2001
    S, G, reg = mk(tmp_path), Graph(str(tmp_path / "t.db")), Registry()
    m = tmp_path / "mirror" / "history" / "arab"
    (m / "uae.json").write_text(json.dumps({"country": "uae", "league": 538, "seasons": [
        {"season": "2001", "table": [[1, "Al-Ain", 102117, 2, 1, 1, 0, 3, 1, 4]],
         "league_matches": [["2001-03-11", "Al-Ain", 102117, "Al-Wahda", None, 2, 1, []]]}]}), encoding="utf-8")
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League"}, "fotmob")
    for i, s in enumerate(("1999/2000", "2000/2001", "2001/2002")):
        e = reg.mint("edition", "fotmob", f"538|{s}")
        G.put("edition", {"eid": e, "cid": lg, "season": s}, "fotmob")
        G.put("match", {"mid": reg.mint("match", "fotmob", 80 + i), "eid": e, "date": f"{s[5:]}-02-01", "home": 1, "away": 2, "hs": 1, "as_": 0}, "fotmob")
    rsssf.load(G, reg, S, codes=["uae"])
    assert [r[0] for r in G.c.execute("select season from edition where cid=? order by season", (lg,))] == ["1999/2000", "2000/2001", "2001/2002"]
