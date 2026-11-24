"""graph/load/fbref.py: worldfootballR_data's results files give the graph's copies of their games the referee, the ground and
the attendance; no game, club or ground is minted."""
import gzip, json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import fbref
from graph.fbref_fetch import _goals, _side


def world(tmp_path, rows):
    d = tmp_path / "db" / ".cache"
    d.mkdir(parents=True)
    with gzip.open(d / "fbref.json.gz", "wt", encoding="utf-8") as z:
        json.dump(rows, z)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    cid = reg.mint("competition", "fotmob", 54)
    G.put("competition", {"cid": cid, "name": "Bundesliga"}, "fotmob")
    e = reg.mint("edition", "sch", "54|1995/1996")
    G.put("edition", {"eid": e, "cid": cid, "season": "1995/1996"}, "sch")
    t = {}
    for nm in ("Bayern München", "Borussia Dortmund", "Werder Bremen"):
        t[nm] = reg.mint("team", "sch", nm)
        G.put("team", {"tid": t[nm], "name": nm}, "sch")
    return G, reg, e, t, Sources(root=str(tmp_path), s3=False)


def test_the_copy_of_a_game_takes_its_referee_ground_and_attendance(tmp_path):
    rows = [["GER", f"1995-08-{12 + 7 * i}", "Bayern Munich", "Dortmund", 3, 1, "Markus Merk", "Olympiastadion", 63000] for i in range(3)]
    rows.append(["GER", "1995-09-02", "Dortmund", "Bayern Munich", 2, 2, "Hellmut Krug", "Westfalenstadion", 42800])       # filed the other way round
    rows.append(["GER", "1995-09-09", "Nobody", "Dortmund", 1, 0, "Markus Merk", None, None])
    G, reg, e, t, S = world(tmp_path, rows)
    by, bvb = t["Bayern München"], t["Borussia Dortmund"]
    for i in range(3):
        G.put("match", {"mid": 10 + i, "eid": e, "date": f"1995-08-{12 + 7 * i}", "home": by, "away": bvb, "hs": 3, "as_": 1}, "sch")
    G.put("match", {"mid": 20, "eid": e, "date": "1995-09-02", "home": by, "away": bvb, "hs": 2, "as_": 2, "attendance": 40000}, "sch")
    sid = reg.mint("stadium", "fotmob", "1")
    G.put("stadium", {"sid": sid, "name": "Olympiastadion"}, "fotmob")
    out = fbref.load(G, reg, S)
    assert G.c.execute("SELECT r.name, m.sid, m.attendance FROM match m JOIN referee r ON r.rid=m.rid WHERE m.mid=10").fetchone() == ("Markus Merk", sid, 63000)
    assert G.c.execute("SELECT r.name, m.sid, m.attendance FROM match m JOIN referee r ON r.rid=m.rid WHERE m.mid=20").fetchone() == ("Hellmut Krug", None, 40000)
    assert G.c.execute("SELECT count(*) FROM match").fetchone() == (4,) and G.c.execute("SELECT count(*) FROM stadium").fetchone() == (1,)
    assert out["games"] == 4 and out["team_unknown"] == 1 and out["referees_own"] == 2 and out["grounds_unknown"] == 1


def test_a_referee_is_the_one_our_copies_of_his_games_already_name(tmp_path):
    rows = [["GER", f"1995-08-{12 + 7 * i}", "Bayern Munich", "Dortmund", 3, 1, "M. Merk", None, None] for i in range(3)]
    G, reg, e, t, S = world(tmp_path, rows)
    rid = reg.mint("referee", "tm", "77")
    G.put("referee", {"rid": rid, "name": "Markus Merk"}, "tm")
    for i in range(3):
        G.put("match", {"mid": 10 + i, "eid": e, "date": f"1995-08-{12 + 7 * i}", "home": t["Bayern München"], "away": t["Borussia Dortmund"], "hs": 3, "as_": 1,
                        "rid": rid if i else None}, "sch")
    out = fbref.load(G, reg, S)
    assert G.c.execute("SELECT rid FROM match WHERE mid=10").fetchone() == (rid,)
    assert G.c.execute("SELECT count(*) FROM referee").fetchone() == (1,) and "referees_own" not in out


def test_a_side_with_few_games_is_found_against_one_already_known(tmp_path):
    rows = [["GER", f"1995-08-{12 + 7 * i}", "Bayern Munich", "Dortmund", 3, 1, "Markus Merk", None, None] for i in range(3)]
    rows.append(["GER", "1995-10-01", "Werder Bremen", "Dortmund", 0, 4, "Bernd Heynemann", None, 30000])
    G, reg, e, t, S = world(tmp_path, rows)
    for i in range(3):
        G.put("match", {"mid": 10 + i, "eid": e, "date": f"1995-08-{12 + 7 * i}", "home": t["Bayern München"], "away": t["Borussia Dortmund"], "hs": 3, "as_": 1}, "sch")
    G.put("match", {"mid": 30, "eid": e, "date": "1995-10-01", "home": t["Werder Bremen"], "away": t["Borussia Dortmund"], "hs": 0, "as_": 4}, "sch")
    out = fbref.load(G, reg, S)
    assert G.c.execute("SELECT attendance FROM match WHERE mid=30").fetchone() == (30000,) and out["teams_by_opponent"] == 1


def test_the_pack_reads_a_score_and_a_national_team():
    assert (_goals(2.0), _goals("(4) 1"), _goals(None)) == (2, 1, None)
    assert (_side("Iraq iq"), _side("th Thailand"), _side("England eng"), _side("Real Madrid")) == ("Iraq", "Thailand", "England", "Real Madrid")
