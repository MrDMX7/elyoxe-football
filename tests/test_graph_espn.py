"""graph/load/espn.py: ESPN's games of 2001-2010 give the competition's copies their squads, goals, cards, substitutions,
referee and ground; FotMob's games keep their own; ESPN's men tie to FotMob's by the shirt of a game both hold."""
import gzip, json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import espn


def man(i, name, no, start=True, plays=(), **kw):
    return {"id": str(i), "name": name, "no": str(no), "start": start, "in": kw.get("sub_in", False), "out": kw.get("sub_out", False), "plays": list(plays)}


def rec(i, season, date, hs, as_, home, away, league="eng.1", referee="M Halsey", venue="Highbury"):
    return {"league": league, "id": str(i), "season": season, "date": date + "T15:00Z", "venue": venue, "attendance": 38014, "referee": referee,
            "teams": [{"id": "359", "name": "Arsenal", "side": "home", "score": str(hs)}, {"id": "368", "name": "Everton", "side": "away", "score": str(as_)}],
            "rosters": [{"team": "359", "side": "home", "men": home}, {"team": "368", "side": "away", "men": away}], "key": []}


def world(tmp_path, rows):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    with gzip.open(db / "espn.json.gz", "wt", encoding="utf-8") as z:
        json.dump({"matches": rows}, z)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    cid = reg.mint("competition", "fotmob", 47)
    G.put("competition", {"cid": cid, "name": "Premier League", "kind": "league"}, "fotmob")
    teams = {}
    for f in (9825, 8668):
        teams[f] = reg.mint("team", "fotmob", f)
        G.put("team", {"tid": teams[f], "name": str(f)}, "fotmob")
        G.xref("team", teams[f], "fotmob", str(f), "fotmob-native")
    return G, reg, cid, teams, Sources(root=str(tmp_path), s3=False)


def ed(G, reg, cid, season, src):
    e = reg.mint("edition", src, f"47|{season}")
    G.put("edition", {"eid": e, "cid": cid, "season": season}, src)
    return e


def test_schochastics_copy_takes_espns_squads_goals_and_cards(tmp_path):
    home = [man(1, "Thierry Henry", 14, plays=[{"t": "34'", "scoringPlay": True, "penaltyKick": True}]),
            man(2, "Martin Keown", 5, start=False, sub_in=True, plays=[{"t": "30'", "substitution": True}]),
            man(3, "Sylvain Wiltord", 11, sub_out=True, plays=[{"t": "30'", "substitution": True}, {"t": "20'", "yellowCard": True}])]
    away = [man(4, "Wayne Rooney", 18, plays=[{"t": "76'", "yellowCard": True}, {"t": "90'+2'", "scoringPlay": True, "ownGoal": True}])]
    rows = [rec(100 + d, "2003/2004", f"2003-08-1{d}", 2, 0, home, away) for d in (6, 7, 8)]
    G, reg, cid, teams, S = world(tmp_path, rows)
    e = ed(G, reg, cid, "2003/2004", "sch")
    for d in (6, 7, 8):
        G.put("match", {"mid": 500 + d, "eid": e, "date": f"2003-08-1{d}", "home": teams[9825], "away": teams[8668], "hs": 2, "as_": 0}, "sch")
    out = espn.load(G, reg, S)
    assert out["games_joined"] == 3 and not out.get("games_own")
    ev = G.c.execute("SELECT minute, added, type, side FROM event WHERE mid=506 ORDER BY seq").fetchall()
    assert ev == [(20, 0, "yellow", "h"), (30, 0, "sub", "h"), (34, 0, "penalty_goal", "h"), (76, 0, "yellow", "a"), (90, 2, "own_goal", "h")]
    assert G.c.execute("SELECT count(*), sum(started) FROM appearance WHERE mid=506").fetchone() == (4, 3)
    assert G.c.execute("SELECT r.name, m.attendance, s.name FROM match m JOIN referee r ON r.rid=m.rid JOIN stadium s ON s.sid=m.sid WHERE m.mid=506").fetchone() == ("M Halsey", 38014, "Highbury")
    assert G.c.execute("SELECT date FROM match WHERE mid=506").fetchone() == ("2003-08-16T15:00:00Z",)


def test_fotmobs_game_keeps_its_own_and_ties_espns_man_by_shirt(tmp_path):
    rows = [rec(200 + d, "2010/2011", f"2010-09-1{d}", 1, 0, [man(1, "Cesc Fabregas", 4, plays=[{"t": "5'", "scoringPlay": True}])], [man(4, "Tim Cahill", 17)])
            for d in (1, 2, 3)]
    G, reg, cid, teams, S = world(tmp_path, rows)
    e = ed(G, reg, cid, "2010/2011", "fotmob")
    cesc = reg.mint("player", "fotmob", 1)
    G.put("player", {"pid": cesc, "name": "Cesc Fàbregas"}, "fotmob")
    for d in (1, 2, 3):
        G.put("match", {"mid": 700 + d, "eid": e, "date": f"2010-09-1{d}T14:00:00Z", "home": teams[9825], "away": teams[8668], "hs": 1, "as_": 0}, "fotmob")
        G.many("appearance", [{"mid": 700 + d, "pid": cesc, "tid": teams[9825], "played": 1, "started": 1, "shirt": "4"}], "fotmob")
    espn.load(G, reg, S)
    assert reg.get("player", "espn", "1") == cesc
    assert G.c.execute("SELECT count(*) FROM appearance WHERE mid=701").fetchone() == (1,)      # FotMob's squad stays whole
    assert G.c.execute("SELECT date FROM match WHERE mid=701").fetchone() == ("2010-09-11T14:00:00Z",)


def test_a_game_no_source_held_is_espns_own_in_its_season(tmp_path):
    rows = [rec(300 + d, "2004/2005", f"2004-10-0{d}", 1, 1, [man(1, "A", 9, plays=[{"t": "10'", "scoringPlay": True}])],
                [man(4, "B", 9, plays=[{"t": "80'", "scoringPlay": True}])]) for d in (1, 2, 3)]
    rows.append(rec(399, "2004/2005", "2004-12-26", 0, 0, [man(1, "A", 9)], [man(4, "B", 9)]))
    G, reg, cid, teams, S = world(tmp_path, rows)
    e = ed(G, reg, cid, "2004/2005", "sch")
    for d in (1, 2, 3):
        G.put("match", {"mid": 800 + d, "eid": e, "date": f"2004-10-0{d}", "home": teams[9825], "away": teams[8668], "hs": 1, "as_": 1}, "sch")
    out = espn.load(G, reg, S)
    assert out["games_own"] == 1
    assert G.c.execute("SELECT e.season, m.home, m.src FROM match m JOIN edition e ON e.eid=m.eid WHERE m.date LIKE '2004-12-26%'").fetchone() == ("2004/2005", teams[9825], "espn")


def test_a_game_with_no_squads_is_not_a_game(tmp_path):
    # ESPN's eng.1 scoreboard of 2009/10 also lists squad-less games with made-up scores (Wolves 7-1 West Ham, 15 Aug 2009)
    rows = [rec(400, "2009/2010", "2009-08-15", 7, 1, [], [])]
    G, reg, cid, teams, S = world(tmp_path, rows)
    out = espn.load(G, reg, S)
    assert G.c.execute("SELECT count(*) FROM match").fetchone() == (0,) and not out.get("games_own")
