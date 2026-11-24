import json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import honours, fjelstul


def base(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    cid = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": cid, "name": "Pro League"}, "fotmob")
    G.xref("competition", cid, "fotmob", 538, "fotmob-native")
    eid = reg.mint("edition", "fotmob", "538|2025/2026")
    G.put("edition", {"eid": eid, "cid": cid, "season": "2025/2026"}, "fotmob")
    return G, reg, cid, eid


def match(G, reg, eid, k, h, a, hs, as_, rnd="1", goals=()):
    mid = reg.mint("match", "fotmob", k)
    G.put("match", {"mid": mid, "eid": eid, "round": rnd, "date": f"2026-01-{10 + k:02d}", "home": h, "away": a, "hs": hs, "as_": as_, "status": "finished"}, "fotmob")
    G.many("event", [{"mid": mid, "seq": i, "minute": 10 + i, "type": t, "side": "h", "pid": p} for i, (t, p) in enumerate(goals)], "fotmob")
    return mid


def test_top_scorer_from_events_counts_no_own_goals(tmp_path):
    G, reg, cid, eid = base(tmp_path)
    a, b = reg.mint("player", "fotmob", 1), reg.mint("player", "fotmob", 2)
    match(G, reg, eid, 1, 10, 20, 2, 0, goals=[("goal", a), ("own_goal", b)])
    match(G, reg, eid, 2, 20, 10, 2, 0, goals=[("goal", b), ("penalty_goal", b)])
    match(G, reg, eid, 3, 10, 30, 1, 0, goals=[("goal", a)])
    honours.load(G, reg, Sources(str(tmp_path), mirror=str(tmp_path / "m"), s3=False))
    got = G.c.execute("select rank, pid, value, src from honour where eid=? and kind='top_scorer' order by pid", (eid,)).fetchall()
    assert got == [(1, a, "2", "tifo"), (1, b, "2", "tifo")]


def test_runner_up_from_the_final(tmp_path):
    G, reg, cid, eid = base(tmp_path)
    match(G, reg, eid, 1, 10, 20, 2, 1, rnd="Final", goals=[("goal", 1), ("goal", 1), ("goal", 2)])
    honours.load(G, reg, Sources(str(tmp_path), mirror=str(tmp_path / "m"), s3=False))
    got = dict(G.c.execute("select kind, tid from honour where eid=? and kind in ('champion','runner_up')", (eid,)).fetchall())
    assert got == {"champion": 10, "runner_up": 20}


def test_scorers_file_and_rsssf_fill_the_older_seasons(tmp_path):
    G, reg, cid, eid = base(tmp_path)
    m = tmp_path / "m" / "history"
    (m / "scorers").mkdir(parents=True)
    (m / "arab").mkdir(parents=True)
    (m / "scorers" / "538.json").write_text(json.dumps({"seasons": {"2012/2013": {"goals": [[170716, "علي مبخوت", 23], [None, "X", 19]]}}}), encoding="utf-8")
    (m / "arab" / "uae.json").write_text(json.dumps({"league": 538, "seasons": [{"season": "1974/1975", "scorers": [["Suhail Salim", "Ahly", 102119, 14]]}]}), encoding="utf-8")
    honours.load(G, reg, Sources(str(tmp_path), mirror=str(tmp_path / "m"), s3=False), arab_codes=["uae"])
    e13 = G.c.execute("select eid from edition where cid=? and season='2012/2013'", (cid,)).fetchone()[0]
    assert G.c.execute("select rank, pid, value, src from honour where eid=? and kind='top_scorer' order by rank", (e13,)).fetchall()[0] == (1, reg.get("player", "fotmob", 170716), "23", "scorers")
    e75 = G.c.execute("select eid from edition where cid=? and season='1974/1975'", (cid,)).fetchone()[0]
    pid = G.c.execute("select pid from honour where eid=? and kind='top_scorer'", (e75,)).fetchone()[0]
    assert G.c.execute("select name from player where pid=?", (pid,)).fetchone()[0] == "Suhail Salim"


def test_fjelstul_golden_ball_podium(tmp_path):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    (db / "fjelstul_award_winners.csv").write_text(
        "key_id,tournament_id,tournament_name,award_id,award_name,shared,player_id,family_name,given_name,team_id,team_name,team_code\n"
        "1,WC-1930,1930 FIFA Men's World Cup,A-1,Golden Ball,0,P-1,Nasazzi,José,T-84,Uruguay,URY\n"
        "2,WC-1930,1930 FIFA Men's World Cup,A-2,Silver Ball,0,P-2,Stábile,Guillermo,T-03,Argentina,ARG\n"
        "3,WC-1930,1930 FIFA Men's World Cup,A-4,Golden Boot,0,P-2,Stábile,Guillermo,T-03,Argentina,ARG\n"
        "4,WC-1930,1930 FIFA Men's World Cup,A-9,FIFA Fair Play Trophy,0,,,,T-84,Uruguay,URY\n"
        "5,WC-1991,1991 FIFA Women's World Cup,A-1,Golden Ball,0,P-9,Akers,Michelle,T-90,United States,USA\n", encoding="utf-8")
    (db / "fjelstul_players.csv").write_text("key_id,player_id,family_name,given_name,birth_date,player_wikipedia_link\n"
                                             "1,P-1,Nasazzi,José,1901-05-24,https://en.wikipedia.org/wiki/Jos%C3%A9_Nasazzi\n"
                                             "2,P-2,Stábile,Guillermo,1905-01-17,https://en.wikipedia.org/wiki/Guillermo_St%C3%A1bile\n", encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    wc = reg.mint("competition", "fotmob", 77)
    fjelstul.load(G, reg, Sources(str(tmp_path), s3=False))
    e = G.c.execute("select eid from edition where cid=? and season='1930'", (wc,)).fetchone()[0]
    got = {(k, r): n for k, r, n in G.c.execute("select h.kind, h.rank, coalesce(p.name, t.name) from honour h left join player p on p.pid=h.pid "
                                                "left join team t on t.tid=h.tid where h.eid=?", (e,))}
    assert G.c.execute("select count(*) from edition where season='1991'").fetchone()[0] == 0     # the women's World Cup is not the men's
    assert got == {("best_player", 1): "José Nasazzi", ("best_player", 2): "Guillermo Stábile", ("top_scorer", 1): "Guillermo Stábile", ("fair_play", 1): "Uruguay"}


def test_a_qualification_competition_has_no_champion(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    cid = reg.mint("competition", "fotmob", 10611)
    G.put("competition", {"cid": cid, "name": "Champions League Qualification"}, "fotmob")
    eid = reg.mint("edition", "fotmob", "10611|2026/2027")
    G.put("edition", {"eid": eid, "cid": cid, "season": "2026/2027"}, "fotmob")
    match(G, reg, eid, 1, 10, 20, 2, 1, rnd="Final")
    honours.load(G, reg, Sources(str(tmp_path), mirror=str(tmp_path / "m"), s3=False))
    assert G.c.execute("select count(*) from honour where eid=? and kind in ('champion','runner_up')", (eid,)).fetchone()[0] == 0


def test_no_own_top_scorer_when_most_goals_have_no_scorer(tmp_path):
    # Bundesliga 2011/12: a goal event for each of 875 goals, 495 of them with no player (FotMob's old seasons): our count
    # crowned Harnik (17) over Huntelaar (29)
    G, reg, cid, eid = base(tmp_path)
    a = reg.mint("player", "fotmob", 1)
    match(G, reg, eid, 1, 10, 20, 2, 0, goals=[("goal", a), ("goal", None)])
    match(G, reg, eid, 2, 20, 10, 2, 0, goals=[("goal", None), ("goal", None)])
    match(G, reg, eid, 3, 10, 30, 1, 0, goals=[("goal", None)])
    honours.load(G, reg, Sources(str(tmp_path), mirror=str(tmp_path / "m"), s3=False))
    assert G.c.execute("select count(*) from honour where eid=? and kind='top_scorer'", (eid,)).fetchone()[0] == 0


def _table(G, eid, played):
    G.c.executemany("INSERT INTO standing(eid, grp, rank, tid, played, won, drawn, lost, gf, ga, pts, src) VALUES(?, '', ?, ?, ?, 0, 0, 0, 0, 0, ?, 's365')",
                    [(eid, r, t, played, 30 - r) for r, t in ((1, 10), (2, 20), (3, 30), (4, 40))])
    G.c.execute("INSERT INTO honour(eid, kind, rank, tid, src) VALUES(?, 'champion', 1, 10, 's365')", (eid,))


def test_a_finished_table_gives_the_runner_up(tmp_path):
    G, reg, cid, eid = base(tmp_path)
    _table(G, eid, 6)
    honours.load(G, reg, Sources(str(tmp_path), s3=False))
    assert G.c.execute("SELECT tid, src FROM honour WHERE eid=? AND kind='runner_up'", (eid,)).fetchall() == [(20, "table")]


def test_a_table_two_games_in_gives_no_runner_up(tmp_path):
    # Qatar 2013/14: 365Scores' table after two games (Al-Duhail 6, Al-Ahli 6) made Al-Ahli the runners-up; El Jaish were
    G, reg, cid, eid = base(tmp_path)
    _table(G, eid, 2)
    honours.load(G, reg, Sources(str(tmp_path), s3=False))
    assert G.c.execute("SELECT tid FROM honour WHERE eid=? AND kind='runner_up'", (eid,)).fetchall() == []


def test_no_top_scorer_counted_in_a_competition_that_is_not_one_of_ours(tmp_path):
    # 23 Nov 2026: Transfermarkt's «CL» (a competition named by its code, a slice of each season's games) crowned Messi top
    # scorer of 2012/13 with 4 goals; a count needs the whole season, and only our competitions are whole
    G, reg, cid, eid = base(tmp_path)
    tm = reg.mint("competition", "tm", "CL")
    G.put("competition", {"cid": tm, "name": "CL"}, "tm")
    te = reg.mint("edition", "tm", "CL|2012/2013")
    G.put("edition", {"eid": te, "cid": tm, "season": "2012/2013"}, "tm")
    a = reg.mint("player", "fotmob", 1)
    for k in (1, 2, 3):
        match(G, reg, te, k, 10, 20, 1, 0, goals=[("goal", a)])
    match(G, reg, te, 4, 10, 30, 2, 1, rnd="Final", goals=[("goal", a), ("goal", a), ("goal", 9)])    # nor a «بطل FAC» beside the FA Cup's
    honours.load(G, reg, Sources(str(tmp_path), mirror=str(tmp_path / "m"), s3=False))
    assert G.c.execute("select count(*) from honour where eid=?", (te,)).fetchone()[0] == 0


def test_the_fairs_cup_final_crowns_its_champion_and_away_goals_settle_a_level_one(tmp_path):
    G, reg, _, _ = base(tmp_path)
    cid = reg.mint("competition", "uefa", "fairs-cup")
    G.put("competition", {"cid": cid, "name": "Inter-Cities Fairs Cup"}, "uefa")
    G.xref("competition", cid, "uefa", "fairs-cup", "uefa-native")
    eid = reg.mint("edition", "uefa", "fairs-cup|1970/1971")
    G.put("edition", {"eid": eid, "cid": cid, "season": "1970/1971"}, "uefa")
    match(G, reg, eid, 1, 10, 20, 2, 2, rnd="final")             # Juventus 2-2 Leeds
    match(G, reg, eid, 2, 20, 10, 1, 1, rnd="final")             # Leeds 1-1 Juventus
    honours.load(G, reg, Sources(str(tmp_path), mirror=str(tmp_path / "m"), s3=False))
    got = dict(G.c.execute("select kind, tid from honour where eid=? and kind in ('champion','runner_up')", (eid,)).fetchall())
    assert got == {"champion": 20, "runner_up": 10}
