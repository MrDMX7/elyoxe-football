import csv, gzip, io, json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import worldcup, intl_goals, tm_lineups


def W(path, header, rows, gz=False):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    data = buf.getvalue().encode()
    path.write_bytes(gzip.compress(data) if gz else data)


def test_world_cup_match_with_lineups_goals_cards_subs_coach_referee(tmp_path):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    W(db / "fjelstul_matches.csv", ["tournament_id", "tournament_name", "match_id", "stage_name", "match_date", "stadium_id", "stadium_name", "city_name", "country_name",
                                    "home_team_id", "home_team_name", "away_team_id", "away_team_name", "home_team_score", "away_team_score", "extra_time",
                                    "penalty_shootout", "home_team_score_penalties", "away_team_score_penalties"],
      [["WC-1970", "1970 FIFA Men's World Cup", "M-1970-01", "group stage", "1970-05-31", "S-1", "Azteca", "Mexico City", "Mexico", "T-46", "Mexico", "T-72", "Soviet Union", "1", "1", "0", "0", "0", "0"],
       ["WC-1991", "1991 FIFA Women's World Cup", "M-W", "final", "1991-11-30", "S-2", "X", "Y", "China", "T-9", "USA", "T-8", "Norway", "2", "1", "0", "0", "0", "0"]])
    W(db / "fjelstul_player_appearances.csv", ["tournament_id", "match_id", "team_id", "home_team", "player_id", "family_name", "given_name", "shirt_number", "position_code", "starter", "substitute"],
      [["WC-1970", "M-1970-01", "T-46", "1", "P-1", "Calderón", "Ignacio", "1", "GK", "1", "0"],
       ["WC-1970", "M-1970-01", "T-46", "1", "P-2", "Valdivia", "Javier", "9", "FW", "1", "0"],
       ["WC-1970", "M-1970-01", "T-46", "1", "P-3", "Borja", "Enrique", "14", "FW", "0", "1"],
       ["WC-1970", "M-1970-01", "T-72", "0", "P-4", "Asatiani", "Kakhi", "11", "MF", "1", "0"]])
    W(db / "fjelstul_goals.csv", ["tournament_id", "match_id", "team_id", "home_team", "player_id", "family_name", "given_name", "player_team_id", "minute_regulation", "minute_stoppage", "own_goal", "penalty"],
      [["WC-1970", "M-1970-01", "T-46", "1", "P-2", "Valdivia", "Javier", "T-46", "60", "0", "0", "1"],
       ["WC-1970", "M-1970-01", "T-72", "0", "P-1", "Calderón", "Ignacio", "T-46", "80", "0", "1", "0"]])
    W(db / "fjelstul_bookings.csv", ["tournament_id", "match_id", "team_id", "home_team", "player_id", "family_name", "given_name", "minute_regulation", "minute_stoppage", "yellow_card", "red_card", "second_yellow_card", "sending_off"],
      [["WC-1970", "M-1970-01", "T-72", "0", "P-4", "Asatiani", "Kakhi", "30", "0", "1", "0", "0", "0"]])
    W(db / "fjelstul_substitutions.csv", ["tournament_id", "match_id", "team_id", "home_team", "player_id", "family_name", "given_name", "minute_regulation", "minute_stoppage", "going_off", "coming_on"],
      [["WC-1970", "M-1970-01", "T-46", "1", "P-2", "Valdivia", "Javier", "70", "0", "1", "0"], ["WC-1970", "M-1970-01", "T-46", "1", "P-3", "Borja", "Enrique", "70", "0", "0", "1"]])
    W(db / "fjelstul_manager_appearances.csv", ["tournament_id", "match_id", "team_id", "home_team", "manager_id", "family_name", "given_name"],
      [["WC-1970", "M-1970-01", "T-46", "1", "M-1", "Cárdenas", "Raúl"]])
    W(db / "fjelstul_referee_appearances.csv", ["tournament_id", "match_id", "referee_id", "family_name", "given_name", "country_name"],
      [["WC-1970", "M-1970-01", "R-1", "Tschenscher", "Kurt", "West Germany"]])
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    out = worldcup.load(G, reg, Sources(str(tmp_path), s3=False))
    assert out["matches"] == 1 and out["new"] == 1                     # the women's final is not the men's World Cup
    mid = reg.get("match", "fjelstul", "M-1970-01")
    m = G.c.execute("select hs, as_, round, date from match where mid=?", (mid,)).fetchone()
    assert m == (1, 1, "group stage", "1970-05-31")
    assert G.c.execute("select season from edition e join match m on m.eid=e.eid where m.mid=?", (mid,)).fetchone()[0] == "1970"
    ap = {r[0]: r[1:] for r in G.c.execute("select p.name, a.started, a.played, a.goals, a.yellow from appearance a join player p on p.pid=a.pid where a.mid=?", (mid,))}
    assert ap["Javier Valdivia"] == (1, 1, 1, 0) and ap["Enrique Borja"] == (0, 1, 0, 0) and ap["Ignacio Calderón"][2] == 0 and ap["Kakhi Asatiani"][3] == 1
    ev = [r for r in G.c.execute("select type, minute, side from event where mid=? order by minute", (mid,))]
    assert ev == [("yellow", 30, "a"), ("penalty_goal", 60, "h"), ("sub", 70, "h"), ("own_goal", 80, "a")]
    assert G.c.execute("select c.name from match_coach x join coach c on c.kid=x.kid where x.mid=? and x.side='h'", (mid,)).fetchone()[0] == "Raúl Cárdenas"
    assert G.c.execute("select r.name from match m join referee r on r.rid=m.rid where m.mid=?", (mid,)).fetchone()[0] == "Kurt Tschenscher"


def test_international_scorers_fill_matches_without_events(tmp_path):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    W(db / "martj42_goalscorers.csv", ["date", "home_team", "away_team", "team", "scorer", "minute", "own_goal", "penalty"],
      [["1990-06-10", "United Arab Emirates", "Colombia", "Colombia", "Bernardo Redín", "50", "FALSE", "FALSE"],
       ["1990-06-10", "United Arab Emirates", "Colombia", "Colombia", "Carlos Valderrama", "85", "FALSE", "FALSE"],
       ["1990-06-15", "West Germany", "United Arab Emirates", "United Arab Emirates", "Khalid Ismail", "46", "FALSE", "FALSE"]])
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    for k, (h, a) in enumerate((("United Arab Emirates", "Colombia"), ("West Germany", "United Arab Emirates"))):
        d = ("1990-06-10", "1990-06-15")[k]
        mid = reg.mint("match", "martj42", f"{d}|{h}|{a}")
        G.put("match", {"mid": mid, "date": d, "home": 1, "away": 2, "hs": 0, "as_": 2}, "martj42")
    G.many("event", [{"mid": reg.get("match", "martj42", "1990-06-15|West Germany|United Arab Emirates"), "seq": 0, "type": "goal"}], "fotmob")
    out = intl_goals.load(G, reg, Sources(str(tmp_path), s3=False))
    m1 = reg.get("match", "martj42", "1990-06-10|United Arab Emirates|Colombia")
    assert [r for r in G.c.execute("select type, minute, side from event where mid=? order by minute", (m1,))] == [("goal", 50, "a"), ("goal", 85, "a")]
    assert out["matches"] == 1                                            # the other already had events
    assert G.c.execute("select name from player where pid=(select pid from event where mid=? and minute=85)", (m1,)).fetchone()[0] == "Carlos Valderrama"


def test_transfermarkt_lineups_for_matches_fotmob_lacks(tmp_path):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    W(db / "tm_game_lineups.csv.gz", ["game_lineups_id", "date", "game_id", "player_id", "club_id", "player_name", "type", "position", "number", "team_captain"],
      [["a", "2015-08-08", "100", "1", "10", "Starter One", "starting_lineup", "Goalkeeper", "1", "1"],
       ["b", "2015-08-08", "100", "2", "10", "Sub Used", "substitutes", "Centre-Forward", "9", "0"],
       ["c", "2015-08-08", "100", "3", "10", "Bench Only", "substitutes", "Goalkeeper", "12", "0"],
       ["d", "2015-08-08", "999", "4", "10", "Other Game", "starting_lineup", "Goalkeeper", "1", "0"]], gz=True)
    W(db / "tm_appearances.csv.gz", ["appearance_id", "game_id", "player_id", "player_club_id", "date", "player_name", "competition_id", "yellow_cards", "red_cards", "goals", "assists", "minutes_played"],
      [["x", "100", "1", "10", "2015-08-08", "Starter One", "NL1", "1", "0", "0", "0", "90"],
       ["y", "100", "2", "10", "2015-08-08", "Sub Used", "NL1", "0", "0", "1", "0", "25"]], gz=True)
    W(db / "tm_game_events.csv.gz", ["game_event_id", "date", "game_id", "minute", "type", "club_id", "player_id", "description", "player_in_id", "player_assist_id"],
      [["e1", "2015-08-08", "100", "65", "Substitutions", "10", "9", "", "2", ""], ["e2", "2015-08-08", "100", "80", "Goals", "10", "2", "", "", ""],
       ["e3", "2015-08-08", "100", "30", "Cards", "10", "1", "1. Yellow card", "", ""]], gz=True)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    home, away = reg.mint("team", "tm", "10"), reg.mint("team", "tm", "20")
    mid = reg.mint("match", "tm", "100")
    G.put("match", {"mid": mid, "date": "2015-08-08", "home": home, "away": away, "hs": 1, "as_": 0}, "tm")
    out = tm_lineups.load(G, reg, Sources(str(tmp_path), s3=False))
    ap = {r[0]: r[1:] for r in G.c.execute("select p.name, a.started, a.played, a.minutes, a.goals, a.yellow, a.captain from appearance a join player p on p.pid=a.pid where a.mid=?", (mid,))}
    assert ap["Starter One"] == (1, 1, 90, 0, 1, 1) and ap["Sub Used"] == (0, 1, 25, 1, 0, 0) and ap["Bench Only"][1] == 0
    assert "Other Game" not in ap and out["matches"] == 1
    assert [r for r in G.c.execute("select type, minute, side from event where mid=? order by minute", (mid,))] == [("yellow", 30, "h"), ("sub", 65, "h"), ("goal", 80, "h")]


def test_a_world_cup_match_held_the_other_way_round_turns_without_a_conflict(tmp_path):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    W(db / "fjelstul_matches.csv", ["tournament_id", "tournament_name", "match_id", "stage_name", "match_date", "stadium_id", "stadium_name", "city_name", "country_name",
                                    "home_team_id", "home_team_name", "away_team_id", "away_team_name", "home_team_score", "away_team_score", "extra_time",
                                    "penalty_shootout", "home_team_score_penalties", "away_team_score_penalties"],
      [["WC-1930", "1930 FIFA Men's World Cup", "M-1930-02", "group stage", "1930-07-13", "S-1", "Parque Central", "Montevideo", "Uruguay",
        "T-83", "United States", "T-07", "Belgium", "3", "0", "0", "0", "0", "0"]])
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    usa, bel = reg.mint("team", "martj42", "United States"), reg.mint("team", "martj42", "Belgium")
    mid = reg.mint("match", "martj42", "1930-07-13|Belgium|United States")
    G.put("match", {"mid": mid, "date": "1930-07-13", "home": bel, "away": usa, "hs": 0, "as_": 3}, "martj42")
    worldcup.load(G, reg, Sources(str(tmp_path), s3=False))
    assert G.c.execute("select home, away, hs, as_ from match where mid=?", (mid,)).fetchone() == (usa, bel, 3, 0)
    assert G.c.execute("select count(*) from conflict").fetchone()[0] == 0
