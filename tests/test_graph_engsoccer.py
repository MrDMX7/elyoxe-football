"""graph/load/engsoccer.py: every English league game of the four tiers since 1888, the old test matches and the FA Cup
(jalapic/engsoccerdata). Liverpool–Manchester United held 182 league meetings for the 186 of the record: the Second
Division of 1895/96 and 1904/05 and the 1894 test match were in no source (Gemini's count, 22 Nov 2026)."""
import csv
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import engsoccer

ENG = ["Date", "Season", "home", "visitor", "FT", "hgoal", "vgoal", "division", "tier", "totgoal", "goaldif", "result"]
PO = ["Date", "Season", "home", "visitor", "FT", "hgoal", "vgoal", "division", "round", "tie", "htier", "vtier", "aet", "pen", "pens", "Venue", "attendance", "neutral"]
FA = ["Date", "Season", "home", "visitor", "FT", "hgoal", "vgoal", "round", "tie", "aet", "pen", "pens", "hp", "vp", "Venue", "attendance", "nonmatch", "notes", "neutral"]


def W(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def world(tmp_path):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    top = [[f"1907-{9 + i // 4:02d}-{1 + 7 * (i % 4):02d}", 1907, "Liverpool" if i % 2 else "Manchester United", "Manchester United" if i % 2 else "Liverpool",
            "1-0", 1, 0, "1", 1, 1, 1, "H"] for i in range(12)]
    W(db / "engsoccer_england.csv", ENG, top + [
        ["1895-10-12", 1895, "Liverpool", "Manchester United", "7-1", 7, 1, "2", 2, 8, 6, "H"],
        ["1904-12-24", 1904, "Manchester United", "Liverpool", "3-1", 3, 1, "2", 2, 4, 2, "H"]])
    W(db / "engsoccer_englandplayoffs.csv", PO, [
        ["1894-04-28", 1893, "Liverpool", "Manchester United", "2-0", 2, 0, "test match", "f", "initial", 2, 1, "NA", "NA", "NA", "Ewood Park", "5,000", "yes"]])
    W(db / "engsoccer_facup.csv", FA, [
        ["1898-02-12", 1897, "Liverpool", "Newcastle United", "3-1", 3, 1, "2", "initial", "NA", "NA", "NA", "NA", "NA", "NA", "NA", "NA", "NA", "NA"],
        ["NA", 1897, "X", "Y", "w/o", "NA", "NA", "1", "initial", "NA", "NA", "NA", "NA", "NA", "NA", "NA", "yes", "walkover", "NA"]])
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    pl = reg.mint("competition", "fotmob", 47)
    G.put("competition", {"cid": pl, "name": "Premier League", "country": "ENG", "kind": "league"}, "fotmob")
    e = reg.mint("edition", "sch", "England|1907/1908")
    G.put("edition", {"eid": e, "cid": pl, "season": "1907/1908"}, "sch")
    liv, mu = reg.mint("team", "fotmob", 8650), reg.mint("team", "fotmob", 10260)
    G.put("team", {"tid": liv, "name": "Liverpool"}, "fotmob")
    G.put("team", {"tid": mu, "name": "Manchester United"}, "fotmob")
    for i, r in enumerate(top):                                   # schochastics' top flight: the same games, ours already
        h, a = (liv, mu) if r[2] == "Liverpool" else (mu, liv)
        G.put("match", {"mid": reg.mint("match", "sch", f"t{i}"), "eid": e, "date": r[0], "home": h, "away": a, "hs": 1, "as_": 0, "status": "finished"}, "sch")
    return G, reg, liv, mu


def test_the_lower_tiers_and_the_test_matches_join_the_clubs_we_hold(tmp_path):
    G, reg, liv, mu = world(tmp_path)
    out = engsoccer.load(G, reg, Sources(str(tmp_path), s3=False))
    assert reg.get("team", "eng", "Liverpool") == liv and reg.get("team", "eng", "Manchester United") == mu
    meet = G.c.execute("select count(*) from match where (home=? and away=?) or (home=? and away=?)", (liv, mu, mu, liv)).fetchone()[0]
    assert meet == 12 + 3                                             # the top flight linked, not twice; two Second Division and the test match
    tier = lambda d: G.c.execute("""select x.source_id, e.season, m.round from match m join edition e on e.eid=m.eid
                                    join xref x on x.type='competition' and x.tifo_id=e.cid and x.source='fotmob' where substr(m.date,1,10)=?""", (d,)).fetchone()
    assert tier("1895-10-12") == ("48", "1895/1896", None)
    assert tier("1894-04-28") == ("47", "1893/1894", "test match")
    assert tier("1898-02-12") == ("132", "1897/1898", "2")
    assert out["linked"] == 12 and out["new"] == 4


def test_a_club_the_votes_miss_is_ours_of_that_name_with_english_games(tmp_path):
    # the 22 Nov trial made 15 top-flight clubs twice (Brentford, Reading, Bournemouth…): the votes missed them
    G, reg, liv, mu = world(tmp_path)
    bre, uru = reg.mint("team", "fotmob", 9937), reg.mint("team", "fotmob", 2219)
    G.put("team", {"tid": bre, "name": "Brentford"}, "fotmob")
    G.put("team", {"tid": uru, "name": "Newcastle United"}, "fotmob")              # a namesake with no English game: never
    e = G.c.execute("select eid from edition limit 1").fetchone()[0]
    G.put("match", {"mid": reg.mint("match", "sch", "b1"), "eid": e, "date": "1935-09-01", "home": bre, "away": liv, "hs": 3, "as_": 0, "status": "finished"}, "sch")
    engsoccer.load(G, reg, Sources(str(tmp_path), s3=False))
    assert reg.get("team", "eng", "Newcastle United") != uru
    db = tmp_path / "db" / ".cache"
    W(db / "engsoccer_england.csv", ENG, [["1950-01-01", 1949, "Brentford", "Liverpool", "1-1", 1, 1, "2", 2, 2, 0, "D"]])
    G2, reg2 = Graph(str(tmp_path / "t2.db")), Registry()
    l2, b2 = reg2.mint("team", "fotmob", 8650), reg2.mint("team", "fotmob", 9937)
    pl = reg2.mint("competition", "fotmob", 47)
    G2.put("competition", {"cid": pl, "name": "Premier League", "country": "ENG"}, "fotmob")
    e2 = reg2.mint("edition", "sch", "x")
    G2.put("edition", {"eid": e2, "cid": pl, "season": "1935/1936"}, "sch")
    for t, nm in ((l2, "Liverpool"), (b2, "Brentford")):
        G2.put("team", {"tid": t, "name": nm}, "fotmob")
    G2.put("match", {"mid": reg2.mint("match", "sch", "b1"), "eid": e2, "date": "1935-09-01", "home": b2, "away": l2, "hs": 3, "as_": 0, "status": "finished"}, "sch")
    engsoccer.load(G2, reg2, Sources(str(tmp_path), s3=False))
    assert reg2.get("team", "eng", "Brentford") == b2 and reg2.get("team", "eng", "Liverpool") == l2


def test_a_club_named_otherwise_by_fotmob_is_found_by_its_schochastics_key(tmp_path):
    G, reg, liv, mu = world(tmp_path)
    hull = reg.mint("team", "fotmob", 8667)
    G.put("team", {"tid": hull, "name": "Hull"}, "fotmob")
    G.xref("team", hull, "sch", "Hull City (England)", "vote")
    db = tmp_path / "db" / ".cache"
    W(db / "engsoccer_england.csv", ENG, [["1950-01-01", 1949, "Hull City", "Liverpool", "1-1", 1, 1, "2", 2, 2, 0, "D"]])
    engsoccer.load(G, reg, Sources(str(tmp_path), s3=False))
    assert reg.get("team", "eng", "Hull City") == hull
