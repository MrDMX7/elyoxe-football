"""graph/load/seasons.py: one season of a competition is one edition (22 Nov 2026: the seasons lists held «1914» and
«1913/1914», «2025» and «2024/2025», two «2025/2026», Chile's league as Copa Sudamericana 1944-2001, and Morocco's second
division in Botola 2006/07)."""
from graph.db import Graph
from graph.ids import Registry
from graph.load import seasons


def world(tmp_path, fid=54, kind="league"):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    cid = reg.mint("competition", "fotmob", fid)
    G.put("competition", {"cid": cid, "name": "C", "kind": kind}, "fotmob")
    G.xref("competition", cid, "fotmob", str(fid), "fotmob-native")
    for tid in range(1, 9):
        G.put("team", {"tid": tid, "name": f"T{tid}"}, "fotmob")
    return G, reg, cid


def ed(G, reg, cid, season, src, fid=54, champion=None, runner_up=None, scorer=None):
    eid = reg.mint("edition", src, f"{fid}|{season}|{src}")
    G.put("edition", {"eid": eid, "cid": cid, "season": season}, src)
    G.xref("edition", eid, src, f"{fid}|{season}", f"{src}-native")
    for kind, tid in (("champion", champion), ("runner_up", runner_up)):
        if tid:
            G.c.execute("INSERT INTO honour VALUES(?,?,1,?,NULL,NULL,NULL,?)", (eid, kind, tid, src))
    if scorer:
        G.put("player", {"pid": scorer, "name": f"P{scorer}"}, "fotmob")
        G.c.execute("INSERT INTO honour VALUES(?,'top_scorer',1,NULL,?,NULL,'20',?)", (eid, scorer, src))
    return eid


def game(G, mid, eid, date, h, a, hs=1, as_=0, src="sch", rnd=None):
    G.put("match", {"mid": mid, "eid": eid, "date": date, "home": h, "away": a, "hs": hs, "as_": as_, "round": rnd}, src)


def labels(G, cid):
    return sorted(s for (s,) in G.c.execute("SELECT season FROM edition WHERE cid=?", (cid,)))


def test_a_year_and_the_season_ending_in_it_are_one_season_in_fotmobs_form(tmp_path):
    G, reg, cid = world(tmp_path)
    ed(G, reg, cid, "1913/1914", "fotmob-trophy", runner_up=2)
    ed(G, reg, cid, "1963/1964", "fotmob-trophy", champion=3)
    ed(G, reg, cid, "1914", "s365", champion=1)
    ed(G, reg, cid, "1913", "s365", champion=4)                  # no «1912/1913» of FotMob's: relabelled, not lost
    seasons.load(G, reg, None)
    assert labels(G, cid) == ["1912/1913", "1913/1914", "1963/1964"]
    e = G.c.execute("SELECT eid FROM edition WHERE cid=? AND season='1913/1914'", (cid,)).fetchone()[0]
    assert sorted(G.c.execute("SELECT kind, tid FROM honour WHERE eid=?", (e,)).fetchall()) == [("champion", 1), ("runner_up", 2)]


def test_a_calendar_competitions_july_june_season_goes_to_the_year_its_games_were_played(tmp_path):
    G, reg, cid = world(tmp_path, fid=45, kind="cup")
    lib = ed(G, reg, cid, "2025", "fotmob", fid=45, champion=1)
    sch = ed(G, reg, cid, "2024/2025", "sch", fid=45)
    game(G, 1, lib, "2025-04-01T22:00:00Z", 1, 2, src="fotmob")
    game(G, 2, sch, "2025-02-05", 3, 4)
    game(G, 3, sch, "2025-03-05", 4, 3)
    seasons.load(G, reg, None)
    assert labels(G, cid) == ["2025"]
    assert G.c.execute("SELECT count(*) FROM match WHERE eid=?", (lib,)).fetchone()[0] == 3


def test_two_editions_with_one_label_are_one(tmp_path):
    G, reg, cid = world(tmp_path, fid=526, kind="cup")
    a = ed(G, reg, cid, "2025/2026", "fotmob", fid=526, champion=1, runner_up=2)
    b = ed(G, reg, cid, "2025/2026", "sch", fid=526, champion=5)      # a disagreement: FotMob's champion stays, logged
    game(G, 1, a, "2026-05-24T19:00:00Z", 1, 2, src="fotmob")
    game(G, 2, b, "2025-09-16", 5, 6)
    out = seasons.load(G, reg, None)
    assert labels(G, cid) == ["2025/2026"]
    assert G.c.execute("SELECT count(*) FROM match WHERE eid=?", (a,)).fetchone()[0] == 2
    assert G.c.execute("SELECT tid FROM honour WHERE eid=? AND kind='champion'", (a,)).fetchall() == [(1,)]
    assert G.c.execute("SELECT count(*) FROM conflict WHERE field='champion'").fetchone()[0] == 1
    assert G.c.execute("SELECT tifo_id FROM xref WHERE type='edition' AND source='sch'").fetchone() == (a,)
    assert out["merged"] == 1


def test_a_split_label_with_no_games_in_a_calendar_competition_joins_the_year_it_ended_in(tmp_path):
    # Brazil's scorers file held «2024/2025» and «2025/2026»: snapshots of 2025 and 2026 filed by the July-June rule
    G, reg, cid = world(tmp_path, fid=268)
    y25 = ed(G, reg, cid, "2025", "fotmob", fid=268, champion=1, scorer=100)
    ed(G, reg, cid, "2026", "fotmob", fid=268)
    ed(G, reg, cid, "2024/2025", "scorers", fid=268, scorer=101)
    seasons.load(G, reg, None)
    assert labels(G, cid) == ["2025", "2026"]
    assert G.c.execute("SELECT pid FROM honour WHERE eid=? AND kind='top_scorer'", (y25,)).fetchall() == [(100,)]   # the season's own list stays


def test_games_from_before_the_competition_existed_leave_it(tmp_path):
    # schochastics' «Copa Sud»: Chile's league of 1944-2001 voted onto Copa Sudamericana (first played 2002)
    G, reg, cid = world(tmp_path, fid=299, kind="cup")
    ed(G, reg, cid, "2002", "fotmob-trophy", fid=299, champion=1)
    old = ed(G, reg, cid, "1982/1983", "sch", fid=299)
    game(G, 1, old, "1982-07-04", 3, 4)
    game(G, 2, old, "1983-01-05", 4, 3)
    out = seasons.load(G, reg, None)
    assert labels(G, cid) == ["2002"]
    assert G.c.execute("SELECT count(*) FROM match").fetchone()[0] == 0          # not this competition's: counted, then dropped
    assert out["detached"] == 2                     # its two years (1982, 1983) once split


def test_a_calendar_leagues_games_filed_july_june_go_to_their_years(tmp_path):
    # Argentina played its league in calendar years until 1990: schochastics' «1936/1937» is the end of 1936 and the start of 1937
    G, reg, cid = world(tmp_path, fid=112)
    y36 = ed(G, reg, cid, "1936", "fotmob-trophy", fid=112, champion=1)
    y37 = ed(G, reg, cid, "1937", "fotmob-trophy", fid=112, champion=2)
    ed(G, reg, cid, "1935", "fotmob-trophy", fid=112, champion=3)
    sch = ed(G, reg, cid, "1936/1937", "sch", fid=112)
    game(G, 1, sch, "1936-08-16", 1, 2)
    game(G, 2, sch, "1937-03-07", 2, 1)
    seasons.load(G, reg, None)
    assert labels(G, cid) == ["1935", "1936", "1937"]
    assert G.c.execute("SELECT eid FROM match ORDER BY mid").fetchall() == [(y36,), (y37,)]


def test_a_league_seasons_second_source_brings_its_missing_games_not_another_divisions(tmp_path):
    # Botola 2006/07: schochastics held the 16 clubs' games, RSSSF's season held the second division's too
    G, reg, cid = world(tmp_path, fid=530)
    e = ed(G, reg, cid, "2006/2007", "s365", fid=530, champion=1)
    teams, mid = (1, 2, 3, 4), 0
    for h in teams:
        for a in teams:
            if h != a and (h, a) != (4, 3):                     # one game schochastics lacks
                mid += 1
                game(G, mid, e, f"2006-{9 + mid % 3:02d}-{1 + mid:02d}", h, a, 1, 0, src="sch")
    game(G, 50, e, "2007-05-01", 4, 3, 2, 2, src="rsssf")       # the missing game: kept
    game(G, 51, e, "2006-09-20", 1, 2, 1, 0, src="rsssf")       # sch's 1-2 of 2006-10-02, another date: one game
    game(G, 52, e, "2006-09-20", 7, 8, 3, 1, src="rsssf")       # the second division
    game(G, 53, e, "2006-09-27", 1, 7, 0, 0, src="rsssf")
    out = seasons.load(G, reg, None)
    left = {m for (m,) in G.c.execute("SELECT mid FROM match WHERE eid=?", (e,))}
    assert 50 in left and 51 not in left and 52 not in left and 53 not in left
    assert len(left) == 12
    assert G.c.execute("SELECT count(*) FROM match").fetchone()[0] == 14 - out["aside_dropped"]      # the strays counted, then dropped
    assert out["strays"] == 2 and out["pair_twins"] == 1


def test_play_offs_and_test_matches_are_never_strays(tmp_path):
    G, reg, cid = world(tmp_path, fid=47)
    e = ed(G, reg, cid, "1892/1893", "fotmob-trophy", fid=47, champion=1)
    mid = 0
    for h in (1, 2, 3, 4):
        for a in (1, 2, 3, 4):
            if h != a:
                mid += 1
                game(G, mid, e, f"1892-{9 + mid % 3:02d}-{1 + mid:02d}", h, a)
    game(G, 60, e, "1893-04-22", 4, 7, src="eng", rnd="test match")
    seasons.load(G, reg, None)
    assert G.c.execute("SELECT eid FROM match WHERE mid=60").fetchone() == (e,)


def test_dash_and_space_forms_of_one_label_are_one(tmp_path):
    G, reg, cid = world(tmp_path, fid=112)
    ed(G, reg, cid, "1936 - Copa de Honor", "fotmob-trophy", fid=112, champion=1)
    ed(G, reg, cid, "1936 Copa de Honor", "s365", fid=112, champion=1)
    seasons.load(G, reg, None)
    assert labels(G, cid) == ["1936 - Copa de Honor"]


def test_fotmobs_games_never_go_aside(tmp_path):
    # Bundesliga 2010/11: three clubs held a second FotMob record each, so FotMob's set was not a clean round robin and
    # schochastics' was: FotMob's 96 games of those records went aside
    G, reg, cid = world(tmp_path)
    e = ed(G, reg, cid, "2010/2011", "fotmob", champion=1)
    mid = 0
    for h in (1, 2, 3, 4):
        for a in (1, 2, 3, 4):
            if h != a:
                mid += 1
                game(G, mid, e, f"2010-{9 + mid % 3:02d}-{1 + mid:02d}", h, a, src="sch")
    game(G, 40, e, "2010-08-21", 7, 1, src="fotmob")             # 7: FotMob's second record of a club
    game(G, 41, e, "2010-08-28", 2, 7, src="fotmob")
    seasons.load(G, reg, None)
    assert G.c.execute("SELECT count(*) FROM match WHERE eid=? AND src='fotmob'", (e,)).fetchone()[0] == 2


def test_another_sources_game_on_another_day_is_another_game(tmp_path):
    # Argentina 2024: the Copa de la Liga (January-May) and the league (May-December) met the same pairs a few weeks apart
    G, reg, cid = world(tmp_path, fid=112)
    e = ed(G, reg, cid, "2024", "fotmob", fid=112, champion=1)
    mid = 0
    for h in (1, 2, 3, 4):
        for a in (1, 2, 3, 4):
            if h != a:
                mid += 1
                game(G, mid, e, f"2024-{5 + mid % 3:02d}-{10 + mid:02d}", h, a, src="fotmob")
    game(G, 30, e, "2024-05-02", 1, 2, 1, 0, src="sch")            # the 1-0 of 2024-06-11 a month later is the league's
    seasons.load(G, reg, None)
    assert G.c.execute("SELECT count(*) FROM match WHERE eid=?", (e,)).fetchone()[0] == 13


def test_a_game_goes_to_fotmobs_season_whose_games_span_its_day(tmp_path):
    # the Libertadores of 2020 ended on 30 January 2021: schochastics' «2020/2021» game of that week is 2020's
    G, reg, cid = world(tmp_path, fid=45, kind="cup")
    y20 = ed(G, reg, cid, "2020", "fotmob", fid=45, champion=1)
    y21 = ed(G, reg, cid, "2021", "fotmob", fid=45, champion=2)
    game(G, 1, y20, "2020-03-03T22:00:00Z", 1, 2, src="fotmob")
    game(G, 2, y20, "2021-01-30T20:00:00Z", 1, 3, src="fotmob")
    game(G, 3, y21, "2021-04-20T22:00:00Z", 2, 3, src="fotmob")
    sch = ed(G, reg, cid, "2020/2021", "sch", fid=45)
    game(G, 4, sch, "2021-01-13", 3, 4)
    game(G, 5, sch, "2021-03-02", 5, 6)
    seasons.load(G, reg, None)
    assert labels(G, cid) == ["2020", "2021"]
    assert G.c.execute("SELECT eid FROM match WHERE mid IN (4, 5) ORDER BY mid").fetchall() == [(y20,), (y21,)]


def test_a_cups_july_june_season_before_fotmob_splits_into_its_years(tmp_path):
    G, reg, cid = world(tmp_path, fid=45, kind="cup")
    ed(G, reg, cid, "2003", "fotmob-trophy", fid=45, champion=1)
    ed(G, reg, cid, "2002", "fotmob-trophy", fid=45, champion=2)
    ed(G, reg, cid, "2010", "fotmob", fid=45, champion=3)
    sch = ed(G, reg, cid, "2002/2003", "sch", fid=45)
    game(G, 1, sch, "2002-07-24", 1, 2)
    game(G, 2, sch, "2003-02-12", 3, 4)
    seasons.load(G, reg, None)
    assert labels(G, cid) == ["2002", "2003", "2010"]


def test_a_full_season_with_one_stray_line_is_still_the_season(tmp_path):
    # UAE 2004/05: RSSSF held all 14 clubs' games and one line its parser misread («Dibba Al-Hisn», one game); schochastics a
    # few of them, one club under another record (Khorfakkan for RSSSF's «Al-Khaleej»)
    G, reg, cid = world(tmp_path, fid=538)
    e = ed(G, reg, cid, "2004/2005", "s365", fid=538, champion=1)
    mid = 0
    for h in (1, 2, 3, 6):
        for a in (1, 2, 3, 6):
            if h != a:
                mid += 1
                game(G, mid, e, f"2004-{9 + mid % 3:02d}-{1 + mid:02d}", h, a, 2, 1, src="rsssf")
    game(G, 30, e, "2005-01-05", 8, 1, src="rsssf")              # the misread line
    game(G, 31, e, "2004-11-03", 5, 1, src="sch")                # 5: schochastics' record of RSSSF's 6
    game(G, 32, e, "2004-10-20", 1, 2, 2, 1, src="sch")          # RSSSF's 1-2 of 2004-10-02: one game
    out = seasons.load(G, reg, None)
    assert G.c.execute("SELECT eid FROM match WHERE mid=31").fetchone() != (e,)
    assert not G.c.execute("SELECT 1 FROM match WHERE mid=32").fetchone()
    assert out["strays"] == 1 and out["pair_twins"] == 1


def test_fotmobs_own_label_for_a_season_wins_in_either_form(tmp_path):
    # LaLiga's first season is FotMob's «1929» (February-June 1929); schochastics filed its games «1928/1929»
    G, reg, cid = world(tmp_path, fid=87)
    y29 = ed(G, reg, cid, "1929", "fotmob-trophy", fid=87, champion=1)
    ed(G, reg, cid, "1929/1930", "fotmob-trophy", fid=87, champion=2)
    ed(G, reg, cid, "1930/1931", "fotmob-trophy", fid=87, champion=3)
    sch = ed(G, reg, cid, "1928/1929", "sch", fid=87, scorer=100)
    game(G, 1, sch, "1929-02-10", 1, 2)
    seasons.load(G, reg, None)
    assert labels(G, cid) == ["1929", "1929/1930", "1930/1931"]
    assert G.c.execute("SELECT eid FROM match WHERE mid=1").fetchone() == (y29,)


def test_a_third_copy_of_a_game_on_its_own_day_is_one_game(tmp_path):
    # the twins pass leaves three records of one day alone: the FA's, schochastics' and RSSSF's of one UAE game
    G, reg, cid = world(tmp_path, fid=538)
    e = ed(G, reg, cid, "2005/2006", "s365", fid=538, champion=1)
    mid = 0
    for h in (1, 2, 3, 4):
        for a in (1, 2, 3, 4):
            if h != a:
                mid += 1
                game(G, mid, e, f"2005-{9 + mid % 3:02d}-{1 + mid:02d}", h, a, src="uaefa")
    game(G, 40, e, "2005-10-02", 1, 2, src="sch")                 # uaefa's mid 1 of that day
    out = seasons.load(G, reg, None)
    assert not G.c.execute("SELECT 1 FROM match WHERE mid=40").fetchone() and out["pair_twins"] == 1


def test_a_few_fotmob_games_do_not_decide_a_season_another_source_holds_whole(tmp_path):
    # Iraq 2010/11: FotMob held 2 games, schochastics the whole season: 513 league games went aside
    G, reg, cid = world(tmp_path, fid=524)
    e = ed(G, reg, cid, "2010/2011", "fotmob", fid=524, champion=1)
    mid = 0
    for h in (1, 2, 3, 4, 5, 6):
        for a in (1, 2, 3, 4, 5, 6):
            if h != a:
                mid += 1
                game(G, mid, e, f"2010-{9 + mid % 3:02d}-{1 + mid % 27:02d}", h, a, src="sch")
    game(G, 90, e, "2011-06-01T15:00:00Z", 1, 2, 2, 2, src="fotmob")
    seasons.load(G, reg, None)
    assert G.c.execute("SELECT count(*) FROM match WHERE eid=?", (e,)).fetchone()[0] == 31


def test_a_clubs_second_record_in_the_old_table_does_not_keep_its_copies(tmp_path):
    # UAE 2006/07: RSSSF's table and games named its own «Al-Shabab» record; the FA's full season has FotMob's: RSSSF's
    # 34 games of that record stayed beside the FA's own
    G, reg, cid = world(tmp_path, fid=538)
    e = ed(G, reg, cid, "2006/2007", "s365", fid=538, champion=1)
    mid = 0
    for h in (1, 2, 3, 4):
        for a in (1, 2, 3, 4):
            if h != a:
                mid += 1
                game(G, mid, e, f"2006-{9 + mid % 3:02d}-{1 + mid:02d}", h, a, src="uaefa")
    G.c.execute("insert into standing values(?, '', 1, 7, 6, 3, 2, 1, 9, 5, 11, 'rsssf')", (e,))        # 7: RSSSF's record of 4
    game(G, 40, e, "2006-10-20", 7, 1, 3, 0, src="rsssf")
    seasons.load(G, reg, None)
    assert G.c.execute("SELECT eid FROM match WHERE mid=40").fetchone() != (e,)


def test_in_a_complete_round_robin_a_second_sources_game_of_a_pair_already_played_is_a_copy(tmp_path):
    # UAE 2008/09: the FA's 132 games are every pair home and away; schochastics' «Sharjah 1-2 Al Wahda» of 12 Apr is the FA's of
    # 15 Mar (a month off), RSSSF's «Al Jazira 1-1 Al Wahda» the FA's 4-0 (another score): copies, not games
    G, reg, cid = world(tmp_path, fid=538)
    e = ed(G, reg, cid, "2008/2009", "s365", fid=538, champion=1)
    mid = 0
    for h in (1, 2, 3, 4):
        for a in (1, 2, 3, 4):
            if h != a:
                mid += 1
                game(G, mid, e, f"2008-{9 + mid % 3:02d}-{1 + mid:02d}", h, a, 1, 2, src="uaefa")
    game(G, 40, e, "2008-11-05", 1, 2, 1, 2, src="sch")               # the FA's 1-2 of 2008-10-02, 34 days off: one game
    game(G, 41, e, "2008-10-25", 1, 3, 1, 1, src="rsssf")             # another score: a wrong copy, aside
    out = seasons.load(G, reg, None)
    assert not G.c.execute("SELECT 1 FROM match WHERE mid=40").fetchone()
    assert G.c.execute("SELECT eid FROM match WHERE mid=41").fetchone() != (e,)
    assert G.c.execute("SELECT count(*) FROM match WHERE eid=?", (e,)).fetchone() == (12,)


def test_a_national_teams_tournament_is_one_edition_however_its_sources_name_it(tmp_path):
    # 23 Nov 2026, the Gulf Cup: 365Scores' «خليجي 2» held the champion, the games sat in calendar years (the 16th, Dec 2003-
    # Jan 2004, in «2003» and «2004» with the 17th of Dec 2004) and Wikipedia's scorer under «2003/2004»: 56 seasons for 27
    G, reg, cid = world(tmp_path, fid=329, kind="cup")
    G.c.execute("UPDATE team SET kind='national'")
    y70, y03, y04 = (ed(G, reg, cid, s, "martj42", fid=329) for s in ("1970", "2003", "2004"))
    for mid, (e, d) in enumerate(((y70, "1970-03-27"), (y70, "1970-04-03"), (y03, "2003-12-26"), (y03, "2003-12-30"),
                                  (y04, "2004-01-05"), (y04, "2004-01-10"), (y04, "2004-12-11"), (y04, "2004-12-24")), 1):
        game(G, mid, e, d, 1 + mid % 4, 5 + mid % 4, src="martj42")
    ed(G, reg, cid, "خليجي 1", "s365", fid=329, champion=1)
    ed(G, reg, cid, "خليجي 2", "s365", fid=329, champion=2)
    ed(G, reg, cid, "خليجي 3", "s365", fid=329, champion=3)
    ed(G, reg, cid, "2003/2004", "wiki", fid=329, scorer=100)
    seasons.load(G, reg, None)
    assert labels(G, cid) == ["1970", "2003", "2004"]
    eid = lambda s: G.c.execute("SELECT eid FROM edition WHERE cid=? AND season=?", (cid, s)).fetchone()[0]
    games = lambda s: [d for (d,) in G.c.execute("SELECT substr(date,1,10) FROM match WHERE eid=? ORDER BY date", (eid(s),))]
    assert games("2003") == ["2003-12-26", "2003-12-30", "2004-01-05", "2004-01-10"]
    assert games("2004") == ["2004-12-11", "2004-12-24"]
    hon = lambda s: sorted(G.c.execute("SELECT kind, coalesce(tid, pid) FROM honour WHERE eid=?", (eid(s),)).fetchall())
    assert hon("1970") == [("champion", 1)]
    assert hon("2003") == [("champion", 2), ("top_scorer", 100)]
    assert hon("2004") == [("champion", 3)]


def test_national_teams_games_all_year_round_are_no_tournament(tmp_path):
    # friendlies, qualifiers: a run longer than a tournament keeps its seasons as they are
    G, reg, cid = world(tmp_path, fid=114, kind="cup")
    G.c.execute("UPDATE team SET kind='national'")
    y1, y2 = (ed(G, reg, cid, s, "martj42", fid=114) for s in ("2003", "2004"))
    for mid, d in enumerate(("2003-09-01", "2003-10-15", "2003-11-20", "2003-12-30", "2004-02-10", "2004-03-25", "2004-05-01"), 1):
        game(G, mid, y1 if d < "2004" else y2, d, 1 + mid % 4, 5 + mid % 4, src="martj42")
    seasons.load(G, reg, None)
    assert labels(G, cid) == ["2003", "2004"]
    assert G.c.execute("SELECT count(*) FROM match m JOIN edition e ON e.eid=m.eid WHERE e.season='2004'").fetchone()[0] == 3


def test_what_goes_aside_leaves_the_graph_so_nothing_publishes_it(tmp_path):
    # 23 Nov 2026: 67 «Pro League (aside)» rows on the head-to-head pages, the copies a club's second record holds
    G, reg, cid = world(tmp_path, fid=299, kind="cup")
    ed(G, reg, cid, "2002", "fotmob-trophy", fid=299, champion=1)
    old = ed(G, reg, cid, "1982/1983", "sch", fid=299)
    game(G, 1, old, "1982-07-04", 3, 4)
    G.c.execute("INSERT INTO event(mid, seq, minute, type, side, src) VALUES(1, 0, 10, 'goal', 'h', 'sch')")
    out = seasons.load(G, reg, None)
    assert G.c.execute("SELECT count(*) FROM match").fetchone()[0] == 0
    assert G.c.execute("SELECT count(*) FROM event").fetchone()[0] == 0
    assert G.c.execute("SELECT count(*) FROM competition WHERE name LIKE '%(aside)'").fetchone()[0] == 0
    assert out["aside_dropped"] == 1
