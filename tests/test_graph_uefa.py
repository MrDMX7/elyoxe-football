"""graph/load/uefa.py: UEFA's own records of 1955-2011 give the competition's copies their squads, goals, coaches, ground and
attendance; a game no source held is UEFA's own, in the season its dates span; a man ties by his shirt or his birthday."""
import gzip, json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import uefa

REAL = {"id": "50051", "name": "Real Madrid", "official": "Real Madrid CF", "ar": "ريال مدريد", "country": "ESP", "national": False, "kind": "DOMESTIC_MEN_TEAM_A"}
REIMS = {"id": "50023", "name": "Reims", "official": "Stade de Reims", "ar": None, "country": "FRA", "national": False, "kind": "DOMESTIC_MEN_TEAM_A"}


def man(i, name, no, born=None, start=True, pos="FORWARD"):
    return {"id": str(i), "name": name, "ar": None, "born": born, "country": "ESP", "pos": pos, "sex": "MALE", "height": None, "no": no, "start": start, "gk": False}


def goal(minute, m, team, sub=None, phase="SECOND_HALF"):
    return {"type": "GOAL", "sub": sub, "phase": phase, "minute": minute, "added": None, "second": 0, "a": {"id": m["id"], "name": m["name"], "born": None, "team": team}, "b": None}


def rec(i, date, hs, as_, home=REAL, away=REIMS, comp="champions", year=1955, men=((), ()), events=None, **kw):
    return {"comp": comp, "year": year, "id": str(i), "date": date, "status": "FINISHED", "type": "SINGLE", "round": kw.get("round", "FIRST"), "phase": kw.get("phase", "TOURNAMENT"),
            "home": home, "away": away, "score": kw.get("score") or {"regular": {"home": hs, "away": as_}, "total": {"home": hs, "away": as_}}, "won": kw.get("won", "WIN_REGULAR"),
            "attendance": 38239, "stadium": {"id": "62", "name": "Parc des Princes", "ar": None, "city": "Paris", "country": "FRA", "capacity": 47929, "lat": 48.84, "lon": 2.25},
            "referees": [{"id": "9", "name": "Arthur Ellis", "country": "ENG", "role": "REFEREE"}], "scorers": [],
            "lineups": [{"team": home["id"], "men": list(men[0]), "coaches": [{"id": "77", "name": "José Villalonga", "born": "1919-12-12", "country": "ESP", "role": "COACH", "sex": "MALE"}]},
                        {"team": away["id"], "men": list(men[1]), "coaches": []}] if kw.get("lineups", True) else None, "events": events}


def world(tmp_path, rows):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    with gzip.open(db / "uefa.json.gz", "wt", encoding="utf-8") as z:
        json.dump({"matches": rows}, z)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    cid = reg.mint("competition", "fotmob", "42")
    G.put("competition", {"cid": cid, "name": "Champions League", "kind": "tournament"}, "fotmob")
    teams = {}
    for f, name in ((8633, "Real Madrid"), (9837, "Reims")):
        teams[f] = reg.mint("team", "fotmob", f)
        G.put("team", {"tid": teams[f], "name": name, "kind": "club"}, "fotmob")
        G.xref("team", teams[f], "fotmob", str(f), "fotmob-native")
    return G, reg, cid, teams, Sources(root=str(tmp_path), s3=False)


def held(G, reg, cid, teams, date, hs, as_, season="1955/1956", home=8633, away=9837, key="x"):
    e = reg.get("edition", "sch", f"42|{season}") or reg.mint("edition", "sch", f"42|{season}")
    G.put("edition", {"eid": e, "cid": cid, "season": season}, "sch")
    mid = reg.mint("match", "sch", key)
    G.put("match", {"mid": mid, "eid": e, "date": date, "home": teams[home], "away": teams[away], "hs": hs, "as_": as_, "status": "finished"}, "sch")
    return mid, e


def test_the_held_game_takes_uefas_squads_goals_coach_ground_and_crowd(tmp_path):
    gento, kopa = man(1, "Francisco Gento", 11, "1933-10-21"), man(2, "Raymond Kopa", 9, "1931-10-13")
    r = rec(100, "1956-06-13", 1, 1, men=([gento], [kopa]), events=[goal(67, gento, "50051"), goal(70, kopa, "50023", sub="PENALTY")], round="FINAL")
    G, reg, cid, teams, S = world(tmp_path, [r])
    mid, _ = held(G, reg, cid, teams, "1956-06-13", 1, 1)
    out = uefa.load(G, reg, S)
    assert out["games_joined"] == 1 and "games_own" not in out
    assert G.c.execute("SELECT count(*) FROM match").fetchone()[0] == 1
    assert G.c.execute("SELECT attendance, round FROM match WHERE mid=?", (mid,)).fetchone() == (38239, "final")
    assert G.c.execute("SELECT s.name, s.city FROM match m JOIN stadium s ON s.sid=m.sid").fetchone() == ("Parc des Princes", "Paris")
    assert G.c.execute("SELECT r.name FROM match m JOIN referee r ON r.rid=m.rid").fetchone() == ("Arthur Ellis",)
    assert G.c.execute("SELECT p.name, p.born, a.shirt, a.goals, a.started FROM appearance a JOIN player p ON p.pid=a.pid ORDER BY a.shirt").fetchall() == [
        ("Francisco Gento", "1933-10-21", "11", 1, 1), ("Raymond Kopa", "1931-10-13", "9", 1, 1)]
    assert G.c.execute("SELECT minute, type, side FROM event ORDER BY seq").fetchall() == [(67, "goal", "h"), (70, "penalty_goal", "a")]
    assert G.c.execute("SELECT k.name, c.side FROM match_coach c JOIN coach k ON k.kid=c.kid").fetchall() == [("José Villalonga", "h")]
    assert G.c.execute("SELECT name_ar FROM team WHERE tid=?", (teams[8633],)).fetchone() == ("ريال مدريد",)


def test_a_game_no_source_held_is_uefas_own_in_the_season_its_dates_span(tmp_path):
    rows = [rec(100, "1955-09-04", 2, 0), rec(101, "1956-06-13", 4, 3, round="FINAL")]
    G, reg, cid, teams, S = world(tmp_path, rows)
    out = uefa.load(G, reg, S)
    assert out["games_own"] == 2 and out["teams_named"] == 2
    assert G.c.execute("SELECT e.season, count(*) FROM match m JOIN edition e ON e.eid=m.eid GROUP BY 1").fetchall() == [("1955/1956", 2)]
    assert G.c.execute("SELECT home, away, hs, as_, round FROM match WHERE date='1956-06-13'").fetchone() == (teams[8633], teams[9837], 4, 3, "final")
    assert uefa.load(G, reg, S)["games_joined"] == 2                       # the second run finds its own games, mints none
    assert G.c.execute("SELECT count(*) FROM match").fetchone()[0] == 2


def test_an_own_game_joins_the_edition_the_seasons_other_games_sit_in(tmp_path):
    rows = [rec(100, "1955-09-04", 2, 0), rec(101, "1955-10-12", 1, 1)]
    G, reg, cid, teams, S = world(tmp_path, rows)
    _, e = held(G, reg, cid, teams, "1955-09-04", 2, 0, season="1955/56")
    uefa.load(G, reg, S)
    assert G.c.execute("SELECT DISTINCT eid FROM match").fetchall() == [(e,)]


def test_a_copy_dated_a_week_off_is_the_same_game_and_takes_uefas_date(tmp_path):
    G, reg, cid, teams, S = world(tmp_path, [rec(100, "1967-10-11", 2, 1, year=1967)])
    mid, _ = held(G, reg, cid, teams, "1967-10-04", 2, 1, season="1967/1968")
    out = uefa.load(G, reg, S)
    assert out["dates_corrected"] == 1 and "games_own" not in out
    assert G.c.execute("SELECT mid, date FROM match").fetchall() == [(mid, "1967-10-11")]


def test_the_same_day_with_another_score_is_the_same_game_and_the_organisers_score_is_kept(tmp_path):
    G, reg, cid, teams, S = world(tmp_path, [rec(100, "1969-05-28", 4, 1, year=1968, round="FINAL")])
    mid, _ = held(G, reg, cid, teams, "1969-05-28", 4, 0, season="1968/1969")
    out = uefa.load(G, reg, S)
    assert out["scores_differ"] == 1 and "games_own" not in out
    assert G.c.execute("SELECT mid, hs, as_ FROM match").fetchall() == [(mid, 4, 1)]
    assert G.c.execute("SELECT field, kept, other FROM conflict").fetchall() == [("as_", "1", "0")]


def test_an_own_goal_counts_for_the_other_side_and_goals_that_do_not_add_up_are_left_out(tmp_path):
    gento, kopa = man(1, "Francisco Gento", 11), man(2, "Raymond Kopa", 9)
    good = rec(100, "1955-09-04", 1, 0, men=([gento], [kopa]), events=[goal(30, kopa, "50023", sub="OWN")])
    bad = rec(101, "1955-10-12", 2, 0, men=([gento], [kopa]), events=[goal(30, gento, "50051")])
    G, reg, cid, teams, S = world(tmp_path, [good, bad])
    out = uefa.load(G, reg, S)
    assert out["goals_not_adding_up"] == 1
    assert G.c.execute("SELECT m.date, e.type, e.side, e.tid FROM event e JOIN match m ON m.mid=e.mid").fetchall() == [("1955-09-04", "own_goal", "h", teams[9837])]
    assert G.c.execute("SELECT sum(goals) FROM appearance").fetchone() == (0,)


def test_a_man_ties_by_his_shirt_in_a_game_both_hold_else_by_his_birthday_and_name(tmp_path):
    gento, kopa = man(1, "Francisco Gento López", 11), man(2, "Raymond Kopa", 9, "1931-10-13")
    rows = [rec(100, "1955-09-04", 2, 0, men=([gento], [kopa])), rec(101, "1955-10-12", 1, 1, men=([gento], [kopa]))]
    G, reg, cid, teams, S = world(tmp_path, rows)
    ours, born = reg.mint("player", "espn", "g"), reg.mint("player", "fotmob", "k")
    G.put("player", {"pid": ours, "name": "Gento"}, "espn")
    G.put("player", {"pid": born, "name": "Kopa", "born": "1931-10-13"}, "fotmob")
    for i, (d, hs, as_) in enumerate((("1955-09-04", 2, 0), ("1955-10-12", 1, 1))):
        mid, _ = held(G, reg, cid, teams, d, hs, as_, key=f"x{i}")
        G.many("appearance", [{"mid": mid, "pid": ours, "tid": teams[8633], "played": 1, "started": 1, "shirt": 11}], "espn")
    out = uefa.load(G, reg, S)
    assert out["men_shirt"] == 1 and out["men_born-name"] == 1 and "men_own" not in out
    assert reg.get("player", "uefa", "1") == ours and reg.get("player", "uefa", "2") == born
    assert G.c.execute("SELECT count(*) FROM player").fetchone()[0] == 2
    assert G.c.execute("SELECT name, position FROM player WHERE pid=?", (born,)).fetchone() == ("Kopa", "Forward")     # the name stays, the line is filled


def test_a_shoot_out_and_womens_and_cancelled_games(tmp_path):
    pens = rec(100, "1986-05-07", 0, 0, year=1985, round="FINAL", won="WIN_ON_PENALTIES",
               score={"regular": {"home": 0, "away": 0}, "total": {"home": 0, "away": 0}, "penalty": {"home": 2, "away": 0}})
    off = {**rec(101, "1985-09-18", 0, 0, year=1985), "status": "CANCELED", "score": {}}
    women = rec(102, "1985-09-18", 1, 0, year=1985, home={**REAL, "id": "9001", "kind": "DOMESTIC_WOMEN_TEAM_A"})
    G, reg, cid, teams, S = world(tmp_path, [pens, off, women])
    mid, _ = held(G, reg, cid, teams, "1986-05-07", 0, 0, season="1985/1986")
    uefa.load(G, reg, S)
    assert G.c.execute("SELECT count(*) FROM match").fetchone()[0] == 1
    assert G.c.execute("SELECT pen_h, pen_a, et FROM match WHERE mid=?", (mid,)).fetchone() == (2, 0, 1)


def test_the_season_a_group_of_dates_spans():
    assert uefa.season_of(["1955-09-04", "1956-06-13"]) == "1955/1956"
    assert uefa.season_of(["1955-06-04", "1958-05-01"]) == "1955/1958"
    assert uefa.season_of(["1973-01-09", "1973-01-16"]) == "1972/1973"
    assert uefa.season_of(["2008-08-29"]) == "2008/2009"
    assert uefa.season_of(["1958-10-01", "1960-07-10"], national=True) == "1960"


def test_nothing_without_the_pack(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    assert uefa.load(G, reg, Sources(root=str(tmp_path), s3=False)) == {"skipped": "no uefa.json.gz"}


def test_a_copy_that_counted_the_shoot_out_is_the_same_game_and_takes_the_organisers_score(tmp_path):
    # schochastics wrote the kicks alone (1-3) two days off, and for another final the kicks on top of the goals (8-7)
    sc = lambda p: {"regular": {"home": 1, "away": 1}, "total": {"home": 1, "away": 1}, "penalty": {"home": p[0], "away": p[1]}}
    rows = [rec(100, "1955-09-14", 1, 1, score=sc((1, 3)), won="WIN_ON_PENALTIES"), rec(101, "1956-06-13", 1, 1, score=sc((8, 7)), won="WIN_ON_PENALTIES", round="FINAL")]
    G, reg, cid, teams, S = world(tmp_path, rows)
    a, _ = held(G, reg, cid, teams, "1955-09-12", 1, 3, key="a")
    b, _ = held(G, reg, cid, teams, "1956-06-13", 9, 8, key="b")
    out = uefa.load(G, reg, S)
    assert out["games_joined"] == 2 and "games_own" not in out
    assert G.c.execute("SELECT mid, hs, as_, pen_h, pen_a FROM match ORDER BY mid").fetchall() == [(a, 1, 1, 1, 3), (b, 1, 1, 8, 7)]


def test_a_european_cup_game_schochastics_holds_under_its_own_competition_is_that_game(tmp_path):
    dukla = {"id": "2600880", "name": "Dukla", "official": "Dukla Praha", "ar": None, "country": "CZE", "national": False, "kind": "DOMESTIC_MEN_TEAM_A"}
    rows = [rec(100 + i, d, hs, as_, home=REAL, away=dukla, year=1957) for i, (d, hs, as_) in enumerate((("1957-11-20", 3, 0), ("1957-12-04", 0, 1), ("1958-03-05", 2, 2)))]
    G, reg, cid, teams, S = world(tmp_path, rows)
    own = reg.mint("competition", "sch", "UEFA CL")                        # one with FotMob's only at the end of the build
    G.put("competition", {"cid": own, "name": "UEFA CL", "kind": "tournament"}, "sch")
    teams["d"] = reg.mint("team", "sch", "ASVS Dukla Praha")
    G.put("team", {"tid": teams["d"], "name": "ASVS Dukla Praha", "kind": "club"}, "sch")
    mids = [held(G, reg, own, teams, d, hs, as_, season="1957/1958", away="d", key=d)[0] for d, hs, as_ in (("1957-11-20", 3, 0), ("1957-12-04", 0, 1), ("1958-03-05", 2, 2))]
    out = uefa.load(G, reg, S)
    assert out["games_joined"] == 3 and "games_own" not in out and "teams_own" not in out
    assert [m for (m,) in G.c.execute("SELECT mid FROM match ORDER BY date")] == mids
    assert reg.get("team", "uefa", "2600880") == teams["d"]


def test_the_fairs_cup_is_a_competition_of_its_own_wherever_a_source_filed_its_games(tmp_path):
    rows = [rec(100, "1964-09-02", 2, 0, comp="fairs-cup", year=1964), rec(101, "1965-06-23", 1, 0, comp="fairs-cup", year=1964, round="FINAL"),
            rec(102, "1971-09-15", 3, 1, comp="uefa-cup", year=1971)]
    G, reg, cid, teams, S = world(tmp_path, rows)
    el = reg.mint("competition", "fotmob", "73")
    G.put("competition", {"cid": el, "name": "Europa League", "kind": "tournament"}, "fotmob")
    fairs, e_old = held(G, reg, el, teams, "1964-09-02", 2, 0, season="1964/1965", key="a")       # schochastics: under the UEFA Cup
    cup, e_cup = held(G, reg, el, teams, "1971-09-15", 3, 1, season="1971/1972", key="b")
    out = uefa.load(G, reg, S)
    assert out["games_joined"] == 2 and out["games_own"] == 1 and out["games_moved"] == 1
    got = G.c.execute("SELECT m.mid, c.name, e.season FROM match m JOIN edition e ON e.eid=m.eid JOIN competition c ON c.cid=e.cid ORDER BY m.date").fetchall()
    assert got[0] == (fairs, "Inter-Cities Fairs Cup", "1964/1965") and got[1][1:] == ("Inter-Cities Fairs Cup", "1964/1965")
    assert got[2] == (cup, "Europa League", "1971/1972")
    assert uefa.load(G, reg, S)["games_joined"] == 3                       # the second run finds them where they are
    assert G.c.execute("SELECT count(*) FROM match").fetchone()[0] == 3
