"""graph/load/fifa.py: FIFA's own records give the World Cup's copies their squads, goals, coach, referee and crowd; a game no
source held is FIFA's own, in the tournament it is named for; an Olympic side of 1992 on is the country's under-23s."""
import gzip, json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import fifa


def side(i, name, code, score, age=7, gender=1, kind=1):
    return {"id": str(i), "name": name, "country": code, "type": kind, "age": age, "gender": gender, "score": score}


def squad(team, men, goals=(), cards=(), subs=(), coach=None):
    return {"team": str(team), "men": [{"id": str(i), "name": n, "no": no, "start": True, "pos": 3, "captain": False} for i, n, no in men],
            "coaches": [{"id": "900", "name": coach, "country": "ARG", "role": 0}] if coach else [],
            "goals": [{"type": t, "id": str(i), "minute": m, "period": p, "team": str(team)} for t, i, m, p in goals],
            "cards": [{"card": c, "id": str(i), "minute": m, "period": 5, "team": str(team)} for c, i, m in cards],
            "subs": [{"on": str(a), "off": str(b), "minute": m, "period": 5} for a, b, m in subs]}


def rec(i, date, home, away, comp="world-cup", season="255711", name="FIFA World Cup Qatar 2022", stage="Group Matches", lineups=None, **kw):
    return {"comp": comp, "id": str(i), "season": season, "season_name": name, "stage": "1", "stage_name": stage, "group": None, "date": date, "local": date,
            "status": kw.get("status", 0), "result": kw.get("result", 1), "leg": None, "home": home, "away": away, "pens": kw.get("pens", [None, None]),
            "attendance": kw.get("attendance"), "stadium": {"id": "5", "name": "Lusail Stadium", "city": "Lusail", "country": "QAT", "capacity": 88966, "lat": None, "lon": None},
            "officials": [{"id": "70", "name": "Szymon MARCINIAK", "country": "POL", "type": 1}, {"id": "71", "name": "Pawel SOKOLNICKI", "country": "POL", "type": 2}],
            "lineups": lineups}


def world(tmp_path, rows, men=None, comps=(("fotmob", "77", "World Cup"),), teams=((6706, "Argentina"), (6723, "France"))):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    with gzip.open(db / "fifa.json.gz", "wt", encoding="utf-8") as z:
        json.dump({"matches": rows, "men": men or {}}, z)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    cids = {}
    for src, k, name in comps:
        cids[k] = reg.mint("competition", src, k)
        G.put("competition", {"cid": cids[k], "name": name, "kind": "tournament"}, src)
    tids = {}
    for f, name in teams:
        tids[f] = reg.mint("team", "fotmob", f)
        G.put("team", {"tid": tids[f], "name": name, "kind": "national"}, "fotmob")
        G.xref("team", tids[f], "fotmob", str(f), "fotmob-native")
    return G, reg, cids, tids, Sources(root=str(tmp_path), s3=False)


def held(G, reg, cid, date, home, away, hs, as_, season="2022"):
    e = reg.get("edition", "fotmob", f"77|{season}") or reg.mint("edition", "fotmob", f"77|{season}")
    G.put("edition", {"eid": e, "cid": cid, "season": season}, "fotmob")
    mid = reg.mint("match", "fotmob", f"{date}{home}")
    G.put("match", {"mid": mid, "eid": e, "date": date, "home": home, "away": away, "hs": hs, "as_": as_, "status": "finished"}, "fotmob")
    return mid, e


ARG, FRA = side(43922, "Argentina", "ARG", 3), side(43946, "France", "FRA", 3)


def test_the_held_final_takes_fifas_squads_goals_coach_referee_and_crowd_and_no_shoot_out_kick(tmp_path):
    lineups = [squad(43922, [(1, "Lionel MESSI", 10), (2, "Angel DI MARIA", 11), (3, "Gonzalo MONTIEL", 4)], coach="Lionel SCALONI",
                     goals=[(1, 1, "23'", 3), (2, 2, "36'", 3), (2, 1, "108'", 9), (1, 3, None, 11)], subs=[(3, 2, "64'")]),
               squad(43946, [(7, "Kylian MBAPPE", 10)], goals=[(1, 7, "80'", 5), (2, 7, "81'", 5), (1, 7, "118'", 9), (1, 7, None, 11), (2, 99, "90'", 5)],
                     cards=[(1, 7, "45'+2'")])]
    r = rec(400, "2022-12-18", ARG, FRA, stage="Final", result=2, pens=[4, 2], attendance="88966", lineups=lineups)
    G, reg, cids, t, S = world(tmp_path, [r], men={"1": {"ar": "ليونيل ميسي", "born": "1987-06-24", "country": "ARG", "height": 170}})
    mid, _ = held(G, reg, cids["77"], "2022-12-18", t[6706], t[6723], 3, 3)
    out = fifa.load(G, reg, S)
    assert out["games_joined"] == 1 and G.c.execute("SELECT count(*) FROM match").fetchone()[0] == 1
    assert G.c.execute("SELECT attendance, round, pen_h, pen_a FROM match WHERE mid=?", (mid,)).fetchone() == (88966, "final", 4, 2)
    assert G.c.execute("SELECT r.name FROM match m JOIN referee r ON r.rid=m.rid").fetchone() == ("Szymon Marciniak",)
    assert G.c.execute("SELECT name, name_ar, born FROM player WHERE name LIKE '%Messi'").fetchone() == ("Lionel Messi", "ليونيل ميسي", "1987-06-24")
    assert G.c.execute("SELECT minute, type, side FROM event WHERE type LIKE '%goal' ORDER BY minute").fetchall() == [
        (23, "penalty_goal", "h"), (36, "goal", "h"), (80, "penalty_goal", "a"), (81, "goal", "a"), (108, "goal", "h"), (118, "penalty_goal", "a")]
    assert G.c.execute("SELECT k.name, c.side FROM match_coach c JOIN coach k ON k.kid=c.kid").fetchall() == [("Lionel Scaloni", "h")]


def test_an_own_goal_counts_for_the_other_side_wherever_fifa_lists_it(tmp_path):
    lineups = [squad(43922, [(1, "Lionel MESSI", 10)], goals=[(3, 7, "30'", 3)]), squad(43946, [(7, "Kylian MBAPPE", 10)])]
    G, reg, cids, t, S = world(tmp_path, [rec(401, "2022-12-01", {**ARG, "score": 1}, {**FRA, "score": 0}, lineups=lineups)])
    held(G, reg, cids["77"], "2022-12-01", t[6706], t[6723], 1, 0)
    fifa.load(G, reg, S)
    assert G.c.execute("SELECT minute, type, side FROM event").fetchall() == [(30, "own_goal", "h")]


def test_a_game_no_source_held_is_fifas_own_in_the_year_the_tournament_is_named_for(tmp_path):
    rows = [rec(402, "2021-02-11", side(1, "Bayern", "GER", 1, kind=0), side(2, "Tigres", "MEX", 0, kind=0), comp="club-world-cup", season="s20",
                name="FIFA Club World Cup Qatar 2020", stage="Final"),
            rec(403, "2024-12-18", side(3, "Real Madrid", "ESP", 3, kind=0), side(4, "Pachuca", "MEX", 0, kind=0), comp="club-world-cup", season="s24",
                name="FIFA Intercontinental Cup 2024", stage="FIFA Intercontinental Cup 2024 Final"),
            rec(404, "2023-07-20", side(5, "New Zealand", "NZL", 1, gender=2), side(6, "Norway", "NOR", 0, gender=2), comp="club-world-cup", season="s20"),
            rec(405, "2026-07-01", {**ARG, "score": None}, {**FRA, "score": None}, comp="club-world-cup", season="s20", status=1)]
    G, reg, cids, t, S = world(tmp_path, rows, comps=(("fotmob", "78", "Club World Cup"), ("fotmob", "10703", "Intercontinental Cup")), teams=())
    out = fifa.load(G, reg, S)
    assert out["games_own"] == 2
    assert G.c.execute("SELECT c.name, e.season, m.date, m.round FROM match m JOIN edition e ON e.eid=m.eid JOIN competition c ON c.cid=e.cid ORDER BY m.date").fetchall() == [
        ("Club World Cup", "2020", "2021-02-11", "final"), ("Intercontinental Cup", "2024", "2024-12-18", "final")]


def test_an_olympic_side_is_the_under_23s_from_1992_and_the_olympic_team_before(tmp_path):
    rows = [rec(500, "2024-08-09", side(1889000, "France", "FRA", 3, age=5), side(1889001, "Spain", "ESP", 5, age=5), comp="olympics", season="o24",
                name="Olympic Football Tournaments Paris 2024", stage="Gold Medal Match", result=3),
            rec(501, "1964-10-23", side(1889002, "Hungary", "HUN", 2, age=5), side(1889003, "Czechoslovakia", "TCH", 1, age=5), comp="olympics", season="o64",
                name="Olympic Football Tournament Tokyo 1964", stage="Final"),
            rec(502, "1936-08-15", side(43954, "Italy", "ITA", 2), side(43924, "Austria", "AUT", 1), comp="olympics", season="o36",
                name="Olympic Football Tournament Berlin 1936", stage="Final", result=3)]
    G, reg, cids, t, S = world(tmp_path, rows, comps=(("fotmob", "66", "Olympics"),),
                               teams=((6723, "France"), (6720, "Spain"), (5800, "France U23"), (8204, "Hungary"), (8498, "Italy")))
    e36 = reg.mint("edition", "fotmob", "66|1936 Berlin")
    G.put("edition", {"eid": e36, "cid": cids["66"], "season": "1936 Berlin"}, "fotmob")
    fifa.load(G, reg, S)
    got = G.c.execute("SELECT m.date, h.tid, h.name, a.name, e.season, m.round, m.et FROM match m JOIN team h ON h.tid=m.home JOIN team a ON a.tid=m.away "
                      "JOIN edition e ON e.eid=m.eid ORDER BY m.date").fetchall()
    assert [g[0:1] + g[2:] for g in got] == [("1936-08-15", "Italy", "Austria", "1936 Berlin", "final", 1),
                                             ("1964-10-23", "Hungary Olympic", "Czechoslovakia Olympic", "1964", "final", None),
                                             ("2024-08-09", "France U23", "Spain U23", "2024", "final", 1)]
    assert got[0][1] == t[8498] and got[2][1] == t[5800] and got[1][1] != t[8204]


def test_a_qualifier_no_source_held_goes_to_its_calendar_year(tmp_path):
    rows = [rec(600, "2025-03-25", {**ARG, "score": 4}, side(43924, "Brazil", "BRA", 1), comp="world-cup-qualifiers", season="q26",
                name="FIFA World Cup 26 Preliminary Competition", stage="Final")]
    G, reg, cids, t, S = world(tmp_path, rows, comps=(("martj42", "FIFA World Cup qualification", "World Cup qualification"),))
    fifa.load(G, reg, S)
    assert G.c.execute("SELECT e.season, m.round, m.hs, m.as_ FROM match m JOIN edition e ON e.eid=m.eid").fetchall() == [("2025", None, 4, 1)]


def test_one_fifa_side_is_the_national_team_until_1948_and_the_olympic_team_after(tmp_path):
    gb = side(1889010, "Great Britain", "GBR", 2, age=5)
    rows = [rec(510, "1948-08-05", gb, side(1889011, "France", "FRA", 0, age=5), comp="olympics", season="o48", name="Olympic Football Tournament London 1948"),
            rec(511, "1960-08-26", gb, side(1889012, "Brazil", "BRA", 0, age=5), comp="olympics", season="o60", name="Olympic Football Tournament Rome 1960")]
    G, reg, cids, t, S = world(tmp_path, rows, comps=(("fotmob", "66", "Olympics"),), teams=((8600, "Great Britain"), (6723, "France")))
    fifa.load(G, reg, S)
    got = G.c.execute("SELECT m.date, h.tid, h.name, a.name FROM match m JOIN team h ON h.tid=m.home JOIN team a ON a.tid=m.away ORDER BY m.date").fetchall()
    assert got == [("1948-08-05", t[8600], "Great Britain", "France"), ("1960-08-26", got[1][1], "Great Britain Olympic", "Brazil Olympic")]
    assert got[1][1] != t[8600]


def test_a_blank_fifa_record_keeps_the_held_score_and_joins_by_the_one_side_it_knows(tmp_path):
    liv, fla = side(1, "Liverpool", "ENG", 0, kind=0), side(2, "CR Flamengo", "BRA", 0, kind=0)
    lineups = [squad(1, [(1, "Roberto FIRMINO", 9)]), squad(2, [(7, "Gabriel BARBOSA", 9)])]
    rows = [rec(700, "2019-12-21", liv, fla, comp="club-world-cup", season="s19", name="FIFA Club World Cup Qatar 2019", stage="Final", pens=[0, 0], lineups=lineups)]
    G, reg, cids, t, S = world(tmp_path, rows, comps=(("fotmob", "78", "Club World Cup"),), teams=())
    for f, name in ((8650, "Liverpool"), (9770, "Flamengo")):
        t[f] = reg.mint("team", "fotmob", f)
        G.put("team", {"tid": t[f], "name": name, "kind": "club"}, "fotmob")
        G.xref("team", t[f], "fotmob", str(f), "fotmob-native")
    mid, _ = held(G, reg, cids["78"], "2019-12-21", t[8650], t[9770], 1, 0, season="2019")
    out = fifa.load(G, reg, S)
    assert out["games_joined"] == 1 and "scores_differ" not in out
    assert G.c.execute("SELECT mid, hs, as_ FROM match").fetchall() == [(mid, 1, 0)]
    assert G.c.execute("SELECT count(*) FROM team").fetchone()[0] == 2
    assert sorted(G.c.execute("SELECT tid FROM appearance").fetchall()) == sorted([(t[8650],), (t[9770],)])


def test_a_game_the_graph_holds_under_another_team_of_one_side_keeps_its_teams(tmp_path):
    srb, ned, arg2 = side(43969, "Serbia", "SRB", 0), side(43960, "Netherlands", "NED", 1), side(43922, "Argentina", "ARG", 6)
    rows = [rec(800 + i, d, srb, o, season="w06", name="2006 FIFA World Cup Germany", lineups=[squad(43969, [(1, "Dejan STANKOVIC", 10)]), squad(o["id"], [(9, "X Y", 9)])])
            for i, (d, o) in enumerate((("2006-06-11", ned), ("2006-06-16", arg2)))]
    rows += [rec(810 + i, f"2010-06-{13 + i}", {**srb, "score": 1}, {**ned, "score": 0}, season="w10", name="2010 FIFA World Cup South Africa") for i in range(3)]
    G, reg, cids, t, S = world(tmp_path, rows, teams=((1240, "Serbia"), (6708, "Netherlands"), (6706, "Argentina"), (17839, "Serbia and Montenegro")))
    for i in range(3):
        held(G, reg, cids["77"], f"2010-06-{13 + i}", t[1240], t[6708], 1, 0, season="2010")
    a, _ = held(G, reg, cids["77"], "2006-06-11", t[17839], t[6708], 0, 1, season="2006")
    b, _ = held(G, reg, cids["77"], "2006-06-16", t[6706], t[17839], 6, 0, season="2006")
    out = fifa.load(G, reg, S)
    assert out["games_joined_by_one_side"] == 2 and G.c.execute("SELECT count(*) FROM match").fetchone()[0] == 5
    assert G.c.execute("SELECT DISTINCT a.tid FROM appearance a JOIN player p ON p.pid=a.pid WHERE p.name='Dejan Stankovic'").fetchall() == [(t[17839],)]
    assert G.c.execute("SELECT home, away FROM match WHERE mid=?", (b,)).fetchone() == (t[6706], t[17839])


def test_a_game_the_graph_files_elsewhere_is_joined_not_made_twice(tmp_path):
    from graph.load import uefa
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    for name in ("FIFA World Cup qualification", "Oceania Nations Cup", "Friendlies"):
        c = reg.mint("competition", "martj42", name)
        G.put("competition", {"cid": c, "name": name}, "martj42")
    wcq, ofc, fr = (reg.get("competition", "martj42", k) for k in ("FIFA World Cup qualification", "Oceania Nations Cup", "Friendlies"))
    e1, e2 = reg.mint("edition", "martj42", "ofc|2016"), reg.mint("edition", "martj42", "fr|2016")
    G.put("edition", {"eid": e1, "cid": ofc, "season": "2016"}, "martj42")
    G.put("edition", {"eid": e2, "cid": fr, "season": "2016"}, "martj42")
    t = {}
    for name in ("New Zealand", "Fiji", "Tahiti"):
        t[name] = reg.mint("team", "fotmob", name)
        G.put("team", {"tid": t[name], "name": name, "kind": "national"}, "fotmob")
        G.xref("team", t[name], "fotmob", name, "fotmob-native")
    m1, m2 = reg.mint("match", "martj42", "a"), reg.mint("match", "martj42", "b")
    G.put("match", {"mid": m1, "eid": e1, "date": "2016-05-28", "home": t["New Zealand"], "away": t["Fiji"], "hs": 3, "as_": 1, "status": "finished"}, "martj42")
    G.put("match", {"mid": m2, "eid": e2, "date": "2016-05-29", "home": t["Fiji"], "away": t["Tahiti"], "hs": 2, "as_": 0, "status": "finished"}, "martj42")
    side = lambda i, name: {"id": i, "name": name, "national": True}
    game = lambda i, d, h, a, hs, as_: {"id": i, "comp": "q", "season": "2018", "date": d, "home": h, "away": a,
                                        "score": {"total": {"home": hs, "away": as_}}, "lineups": []}
    rows = [game("1", "2016-05-28", side("nz", "New Zealand"), side("fj", "Fiji"), 3, 1),
            game("2", "2016-05-29", side("fj", "Fiji"), side("th", "Tahiti"), 2, 0)]
    n = uefa.apply(G, reg, rows, "fifa", {"q": [("martj42", "FIFA World Cup qualification")]}, lambda r: r["season"],
                   lambda r, g, dates, cids: (cids["q"][0], f"q|{g}", g, False))
    assert n["games_joined_elsewhere"] == 2 and not n.get("games_own")
    assert G.c.execute("SELECT count(*) FROM match").fetchone()[0] == 2
    cid = lambda m: G.c.execute("SELECT e.cid FROM match m JOIN edition e ON e.eid=m.eid WHERE m.mid=?", (m,)).fetchone()[0]
    assert cid(m1) == ofc                                       # the championship that was the qualifier too keeps it
    assert cid(m2) == wcq                                       # out of the friendlies
