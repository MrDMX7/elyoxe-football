import csv, gzip, io, json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import tm


def write_csv(path, header, rows, gz=False):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    data = buf.getvalue().encode()
    path.write_bytes(gzip.compress(data) if gz else data)


def mk(tmp_path):
    db, h = tmp_path / "db" / ".cache", tmp_path / "history" / ".cache"
    (db / "tm").mkdir(parents=True)
    h.mkdir(parents=True)
    write_csv(db / "tm" / "player_profiles.csv", ["player_id", "player_name", "name_in_home_country", "date_of_birth", "place_of_birth", "citizenship", "height", "foot", "date_of_death"],
              [["5", "Omar A (1)", "عمر", "1991-10-01", "Al Ain", "United Arab Emirates  Bahrain", "1,82", "left", ""]])
    write_csv(db / "tm" / "player_performances.csv", ["player_id", "season_name", "competition_id", "competition_name", "team_id", "team_name", "nb_on_pitch", "goals", "assists",
              "yellow_cards", "second_yellow_cards", "direct_red_cards", "minutes_played", "goals_conceded", "clean_sheets"],
              [["5", "15/16", "UAE1", "UAE Pro League", "100", "Al Ain", "25", "10.0", "8", "2", "0", "0", "2100", "", "0"]])
    write_csv(db / "tm" / "player_injuries.csv", ["player_id", "season_name", "injury_reason", "from_date", "end_date", "days_missed", "games_missed"],
              [["5", "15/16", "Knee", "2016-01-01", "2016-02-01", "31", "4"]])
    (h / "tm_playermap.json").write_text(json.dumps({"5": "77"}))
    (h / "tm_clubmap.json").write_text(json.dumps({"100": 10, "200": 20}))
    write_csv(db / "tm_games.csv.gz", ["game_id", "competition_id", "season", "round", "date", "home_club_id", "away_club_id", "home_club_goals", "away_club_goals",
              "home_club_manager_name", "away_club_manager_name", "stadium", "attendance", "referee"],
              [["1", "UAE1", "2015", "1", "2016-01-10", "100", "200", "2", "1", "Zlatko D", "Coach B", "Hazza", "9000", "Ref"],
               ["2", "UAE1", "2015", "2", "2016-01-20", "200", "100", "0", "0", "Coach B", "Zlatko D", "X", "", ""]], gz=True)
    write_csv(db / "tm_game_events.csv.gz", ["game_event_id", "date", "game_id", "minute", "type", "club_id", "player_id", "description", "player_in_id", "player_assist_id"], [], gz=True)
    return Sources(str(tmp_path), s3=False)


def test_tm(tmp_path):
    S, G, reg = mk(tmp_path), Graph(str(tmp_path / "t.db")), Registry()
    pid = reg.mint("player", "fotmob", 77)
    G.put("player", {"pid": pid, "name": "Omar A"}, "fotmob")
    t10, t20 = reg.mint("team", "fotmob", 10), reg.mint("team", "fotmob", 20)
    G.put("match", {"mid": reg.mint("match", "fotmob", 1), "date": "2016-01-10T16:00:00Z", "home": t10, "away": t20, "hs": 2, "as_": 1}, "fotmob")
    zk = reg.mint("coach", "fotmob", 500)
    G.put("coach", {"kid": zk, "name": "Zlatko D"}, "fotmob")       # same name, no club evidence: never linked by name
    out = tm.load(G, reg, S)
    assert zk not in [k for (k,) in G.c.execute("select kid from match_coach")]
    assert reg.get("player", "tm", "5") == pid
    assert G.c.execute("select birthplace, nationality2, name_native, height from player where pid=?", (pid,)).fetchone() == ("Al Ain", "Bahrain", "عمر", 182)
    assert G.c.execute("select season, goals, minutes from player_season").fetchone() == ("2015/2016", 10, 2100)
    assert G.c.execute("select days, games from injury").fetchone() == (31, 4)
    assert out["games_linked"] == 1 and out["games_new"] == 1
    assert G.c.execute("select count(*) from match_coach").fetchone()[0] == 4
