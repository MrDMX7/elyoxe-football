"""graph/load/uaefa.py: the UAE FA's record of the top flight (2003/04-) joins the league's games, takes over RSSSF's and
schochastics' copies, never FotMob's, and ties its men to FotMob's by the shirt numbers of a game both hold."""
import gzip, json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import uaefa

AIN, WAHDA = {"id": "1", "name_en": "Al Ain", "name_ar": "العين"}, {"id": "2", "name_en": "Al Wahda", "name_ar": "الوحدة"}


def man(pid, en, ar, no=None, **kw):
    at = {"player_id": str(pid), "shortname_en": en, "name_en": en, "shortname_ar": ar, "nationality_id": "1"}
    if no:
        at["j_no"] = str(no)
    return {"attributes": at, **kw}


def rec(fa, season, date, hs, as_, home_men, away_men, events, time="20:00"):
    team = lambda club, s, men: {"attributes": {**club, "score": str(s)}, "active": {"player": [m for m in men if "bench" not in m]},
                                 "substitute": {"player": [{k: v for k, v in m.items() if k != "bench"} for m in men if "bench" in m]}}
    return {"fa": fa, "season": season, "uaepl": None,
            "report": {"attributes": {"match_date": date, "match_time": time, "week": "3", "Stadium_en": "Al Ain Club / Hazza Bin Zayed Stadium",
                                      "Stadium_ar": "نادي العين / استاد هزاع بن زايد"},
                       "team1": team(AIN, hs, home_men), "team2": team(WAHDA, as_, away_men),
                       "match_official": [{"person_id": "9", "shortname_en": "Ali Hamad", "shortname_ar": "علي حمد", "title_id": "1"}]},
            "en": {"event": events}, "ar": None}


def world(tmp_path, rows):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    with gzip.open(db / "uaefa.json.gz", "wt", encoding="utf-8") as z:
        json.dump({"matches": rows}, z, ensure_ascii=False)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    cid = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": cid, "name": "Pro League", "kind": "league"}, "fotmob")
    G.xref("competition", cid, "fotmob", "538", "fotmob-native")
    teams = {}
    for f in (102117, 102109):
        teams[f] = reg.mint("team", "fotmob", f)
        G.put("team", {"tid": teams[f], "name": str(f)}, "fotmob")
        G.xref("team", teams[f], "fotmob", str(f), "fotmob-native")
    return G, reg, cid, teams, Sources(root=str(tmp_path), s3=False)


def ed(G, reg, cid, season, src):
    e = reg.mint("edition", src, f"538|{season}")
    G.put("edition", {"eid": e, "cid": cid, "season": season}, src)
    return e


def test_the_fas_record_takes_over_rsssfs_copy_with_its_line_ups_and_goals(tmp_path):
    rows = [rec(100 + d, "2005/2006", "2005-10-0" + str(d), 2, 1,
                [man(11, "Ismail Matar", "إسماعيل مطر"), man(12, "Subait Khater", "سبيت خاطر")], [man(21, "Faisal Khalil", "فيصل خليل")],
                [{"type": "goal", "time": "10", "fulltime": "10", "club_dir": "H", "player_id": "11"},
                 {"type": "goal", "time": "93", "fulltime": "90+3", "club_dir": "H", "player_id": "21"},      # Faisal's own goal
                 {"type": "goal", "time": "50", "fulltime": "50", "club_dir": "A", "player_id": "21"}]) for d in (1, 2, 3)]
    G, reg, cid, teams, S = world(tmp_path, rows)
    e = ed(G, reg, cid, "2005/2006", "rsssf")
    for d in (1, 2, 3):
        G.put("match", {"mid": 500 + d, "eid": e, "date": f"2005-10-0{d}", "home": teams[102117], "away": teams[102109], "hs": 2, "as_": 1}, "rsssf")
    G.many("event", [{"mid": 501, "seq": 0, "minute": 10, "type": "goal", "side": "h", "tid": teams[102117], "pid": None}], "rsssf")
    out = uaefa.load(G, reg, S)
    assert out["games_joined"] == 3 and not out.get("games_own")
    assert G.c.execute("SELECT src FROM match WHERE mid=501").fetchone() == ("uaefa",)
    ev = G.c.execute("SELECT minute, added, type, side FROM event WHERE mid=501 ORDER BY seq").fetchall()
    assert ev == [(10, 0, "goal", "h"), (50, 0, "goal", "a"), (90, 3, "own_goal", "h")]
    assert G.c.execute("SELECT count(*) FROM appearance WHERE mid=501").fetchone() == (3,)
    assert G.c.execute("SELECT name_ar FROM player p JOIN appearance a ON a.pid=p.pid WHERE a.mid=501 AND a.shirt IS NULL ORDER BY p.name LIMIT 1").fetchone() == ("فيصل خليل",)
    assert G.c.execute("SELECT r.name_ar FROM match m JOIN referee r ON r.rid=m.rid WHERE m.mid=501").fetchone() == ("علي حمد",)
    assert G.c.execute("SELECT date FROM match WHERE mid=501").fetchone() == ("2005-10-01T16:00:00Z",)    # 20:00 in the UAE


def test_a_game_no_source_held_is_the_fas_own_in_its_season(tmp_path):
    rows = [rec(200 + d, "2004/2005", f"2004-11-1{d}", 1, 0, [man(11, "Ismail Matar", "إسماعيل مطر")], [man(21, "Faisal Khalil", "فيصل خليل")],
                [{"type": "goal", "time": "5", "club_dir": "H", "player_id": "11"}]) for d in (1, 2, 3)]
    rows.append(rec(300, "2004/2005", "2004-12-01", 0, 0, [man(11, "Ismail Matar", "إسماعيل مطر")], [man(21, "Faisal Khalil", "فيصل خليل")], []))
    G, reg, cid, teams, S = world(tmp_path, rows)
    e = ed(G, reg, cid, "2004/2005", "sch")
    for d in (1, 2, 3):
        G.put("match", {"mid": 600 + d, "eid": e, "date": f"2004-11-1{d}", "home": teams[102117], "away": teams[102109], "hs": 1, "as_": 0}, "sch")
    out = uaefa.load(G, reg, S)
    assert out["games_own"] == 1
    m = G.c.execute("SELECT e.season, m.home, m.away, m.src FROM match m JOIN edition e ON e.eid=m.eid WHERE m.date LIKE '2004-12-01%'").fetchone()
    assert m == ("2004/2005", teams[102117], teams[102109], "uaefa")          # the clubs the league's games voted for


def test_fotmobs_game_keeps_its_own_and_ties_the_fas_men_by_shirt(tmp_path):
    rows = [rec(400 + d, "2015/2016", f"2015-09-1{d}", 1, 0, [man(11, "Omar Abdulrahman", "عمر عبدالرحمن", no=10)], [man(21, "Ismail Matar", "إسماعيل مطر", no=10)],
                [{"type": "goal", "time": "5", "club_dir": "H", "player_id": "11"}]) for d in (1, 2, 3)]
    G, reg, cid, teams, S = world(tmp_path, rows)
    e = ed(G, reg, cid, "2015/2016", "fotmob")
    omar = reg.mint("player", "fotmob", 1)
    G.put("player", {"pid": omar, "name": "Omar Abdulrahman"}, "fotmob")
    for d in (1, 2, 3):
        G.put("match", {"mid": 700 + d, "eid": e, "date": f"2015-09-1{d}T15:00:00Z", "home": teams[102117], "away": teams[102109], "hs": 1, "as_": 0}, "fotmob")
        G.many("appearance", [{"mid": 700 + d, "pid": omar, "tid": teams[102117], "played": 1, "started": 1, "shirt": "10"}], "fotmob")
    out = uaefa.load(G, reg, S)
    assert reg.get("player", "uaefa", "11") == omar
    assert G.c.execute("SELECT src FROM match WHERE mid=701").fetchone() == ("fotmob",)
    assert G.c.execute("SELECT count(*) FROM appearance WHERE mid=701").fetchone() == (1,)    # FotMob's line-up stays whole
    assert G.c.execute("SELECT count(*) FROM event WHERE mid=701").fetchone() == (1,)         # it had no goals: the FA's
    assert out["men_linked"] >= 1


def test_goals_that_do_not_add_up_to_the_score_are_left_out(tmp_path):
    rows = [rec(800 + d, "2006/2007", f"2007-01-0{d}", 3, 0, [man(11, "A B", "أ ب")], [man(21, "C D", "ج د")],
                [{"type": "goal", "time": "5", "club_dir": "H", "player_id": "11"}]) for d in (1, 2, 3)]
    G, reg, cid, teams, S = world(tmp_path, rows)
    out = uaefa.load(G, reg, S)
    assert G.c.execute("SELECT count(*) FROM event WHERE type='goal'").fetchone() == (0,)
    assert out["goals_not_adding_up"] == 3
