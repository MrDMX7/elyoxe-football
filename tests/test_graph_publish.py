import json
from graph.db import Graph
from graph.ids import Registry
from graph import publish


def graph(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    bd = reg.mint("competition", "wiki", "Ballon d'Or")
    G.put("competition", {"cid": bd, "name": "Ballon d'Or", "name_ar": "الكرة الذهبية", "kind": "award"}, "wikidata")
    messi = reg.mint("player", "fotmob", 30981)
    G.put("player", {"pid": messi, "name": "Lionel Messi", "name_ar": "ليونيل ميسي"}, "fotmob")
    G.xref("player", messi, "fotmob", 30981, "fotmob-native")
    old = reg.mint("player", "wikidata", "Q1")
    G.put("player", {"pid": old, "name": "Stanley Matthews"}, "wikidata")
    for y, podium in (("1956", [old]), ("2009", [messi]), ("2010", [messi]), ("2011", [messi])):
        e = reg.mint("edition", "wiki", f"bd|{y}")
        G.put("edition", {"eid": e, "cid": bd, "season": y}, "wiki")
        for r, p in enumerate(podium, 1):
            G.c.execute("insert into honour(eid, kind, rank, pid, value, src) values(?, 'winner', ?, ?, '47', 'wiki')", (e, r, p))
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League", "name_ar": "دوري أدنوك للمحترفين"}, "fotmob")
    G.xref("competition", lg, "fotmob", 538, "fotmob-native")
    e = reg.mint("edition", "fotmob", "538|2012/2013")
    G.put("edition", {"eid": e, "cid": lg, "season": "2012/2013"}, "fotmob")
    G.c.execute("insert into honour(eid, kind, rank, pid, value, src) values(?, 'top_scorer', 1, ?, '23', 'scorers')", (e, messi))
    G.c.commit()
    return G, messi


def test_award_files(tmp_path):
    G, messi = graph(tmp_path)
    out = publish.awards(G, str(tmp_path / "o"))
    ix = json.load(open(tmp_path / "o" / "awards" / "index.json", encoding="utf-8"))
    a = next(x for x in ix["awards"] if x["key"] == "ballon-dor")
    assert (a["name_ar"], a["years"], a["first"], a["last"], a["group"]) == ("الكرة الذهبية", 4, "1956", "2011", "world")
    assert a["top"] == ["ليونيل ميسي", 3, 30981]
    d = json.load(open(tmp_path / "o" / "awards" / "ballon-dor.json", encoding="utf-8"))
    assert d["years"][0]["season"] == "2011" and d["years"][0]["podium"][0]["fotmob"] == 30981
    old = d["years"][-1]["podium"][0]
    assert old == {"rank": 1, "name": "Stanley Matthews", "name_ar": None, "fotmob": None, "tifo": old["tifo"], "team": None, "value": "47"}
    assert d["most"][0] == ["ليونيل ميسي", 3, 30981]
    pl = json.load(open(tmp_path / "o" / "awards" / "players.json", encoding="utf-8"))
    assert ["ballon-dor", "2011", "winner", 1, None] in pl["30981"]                  # an award: its key
    assert [None, "2012/2013", "top_scorer", 1, 538] in pl["30981"]                   # an edition honour: the FotMob competition
    assert pl[f"k{old['tifo']}"] == [["ballon-dor", "1956", "winner", 1, None]]          # a player FotMob does not know: k<Tifo id>
    assert out["awards"] == 1


def test_a_missing_fotmob_id_does_not_break_publishing(tmp_path):
    G, messi = graph(tmp_path)
    G.xref("competition", 999, "fotmob", None, "fotmob-native")          # the archive has matches with no competition
    G.xref("player", 998, "fotmob", None, "fotmob-native")
    assert publish.awards(G, str(tmp_path / "o"))["awards"] == 1


def test_club_awards_have_their_own_group():
    assert publish.group("Arsenal F.C. Player of the Season") == "club"
    assert publish.group("Chelsea F.C. Player of the Season award recipients") == "club"
    assert publish.group("Ballon d'Or") == "world"
    assert publish.group("FWA Footballer of the Year") == "country"


def test_edition_files_for_season_pages(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League", "name_ar": "دوري أدنوك للمحترفين"}, "fotmob")
    G.xref("competition", lg, "fotmob", 538, "fotmob-native")
    ain, jaz = reg.mint("team", "fotmob", 102117), reg.mint("team", "fotmob", 102101)
    for t, f, ar in ((ain, 102117, "العين"), (jaz, 102101, "الجزيرة")):
        G.put("team", {"tid": t, "name": str(f), "name_ar": ar}, "fotmob")
        G.xref("team", t, "fotmob", f, "fotmob-native")
    mab = reg.mint("player", "fotmob", 170716)
    G.put("player", {"pid": mab, "name": "Ali Mabkhout", "name_ar": "علي مبخوت"}, "fotmob")
    G.xref("player", mab, "fotmob", 170716, "fotmob-native")
    e = reg.mint("edition", "fotmob", "538|2016/2017")
    G.put("edition", {"eid": e, "cid": lg, "season": "2016/2017"}, "fotmob")
    G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'champion', 1, ?, 's365')", (e, jaz))
    G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'runner_up', 1, ?, 'table')", (e, ain))
    G.c.execute("insert into honour(eid, kind, rank, pid, value, src) values(?, 'top_scorer', 1, ?, '33', 'tifo')", (e, mab))
    zb = reg.mint("player", "rsssf", "Zoheir Bakhit")
    G.put("player", {"pid": zb, "name": "Zoheir Bakhit"}, "rsssf")
    G.c.execute("insert into honour(eid, kind, rank, pid, value, src) values(?, 'top_scorer', 2, ?, '20', 'rsssf')", (e, zb))
    G.c.execute("insert into standing values(?, '', 1, ?, 26, 22, 2, 2, 70, 20, 68.0, 's365')", (e, jaz))
    m = reg.mint("match", "fotmob", 1)
    G.put("match", {"mid": m, "eid": e, "date": "2017-01-01", "home": jaz, "away": ain, "hs": 2, "as_": 0}, "fotmob")
    G.c.execute("insert into match_award values(?, 'motm', ?, ?, '9.1', 'fotmob-rating')", (m, mab, jaz))
    m2 = reg.mint("match", "fotmob", 2)                   # an organiser's award to a man FotMob never had: his archive page
    G.put("match", {"mid": m2, "eid": e, "date": "2017-01-08", "home": ain, "away": jaz, "hs": 1, "as_": 0}, "fotmob")
    G.c.execute("insert into match_award values(?, 'motm', ?, ?, NULL, 'official')", (m2, zb, ain))
    k = reg.mint("coach", "fotmob", 150526)
    G.put("coach", {"kid": k, "name": "Henk ten Cate"}, "fotmob")
    G.c.execute("insert into match_coach values(?, 'h', ?, 'fotmob')", (m, k))
    G.c.commit()
    out = publish.editions(G, str(tmp_path / "o"))
    d = json.load(open(tmp_path / "o" / "editions" / "538.json", encoding="utf-8"))
    s = d["seasons"][0]
    assert (s["season"], s["champion"]["fotmob"], s["champion"]["name"], s["runner_up"]["name"]) == ("2016/2017", 102101, "الجزيرة", "العين")
    assert s["top_scorers"][0] == {"rank": 1, "fotmob": 170716, "name": "علي مبخوت", "value": "33"}
    assert s["top_scorers"][1] == {"rank": 2, "fotmob": None, "tifo": zb, "name": "Zoheir Bakhit", "value": "20"}   # links to /p/k<id>/
    assert s["table"][0] == [1, 102101, "الجزيرة", 26, 22, 2, 2, 70, 20, 68] and type(s["table"][0][9]) is int and s["motm"][0] == [170716, "علي مبخوت", 1]
    assert s["motm"][1] == [None, "Zoheir Bakhit", 1, zb]
    assert s["champion_coach"] == {"kid": k, "name": "Henk ten Cate"} and s["matches"] == 2
    assert out["competitions"] == 1


def test_people_files_for_the_players_the_site_has_no_page_for(tmp_path):
    G, messi = graph(tmp_path)
    old = G.c.execute("select pid from player where name='Stanley Matthews'").fetchone()[0]
    G.c.execute("update player set born='1915-02-01', name_ar='ستانلي ماثيوز' where pid=?", (old,))
    eng = 500
    G.put("team", {"tid": eng, "name": "England", "name_ar": "إنجلترا", "kind": "national"}, "fjelstul")
    wc = 600
    G.put("competition", {"cid": wc, "name": "World Cup", "name_ar": "كأس العالم"}, "fotmob")
    G.xref("competition", wc, "fotmob", 77, "fotmob-native")
    for i, y in enumerate(("1950", "1954", "1954")):
        e = 700 + int(y)
        G.c.execute("insert or ignore into edition(eid, cid, season, src) values(?, ?, ?, 'fjelstul')", (e, wc, y))
        G.put("match", {"mid": 800 + i, "eid": e, "date": f"{y}-06-1{i}", "home": eng, "away": 1, "hs": 1, "as_": 0}, "fjelstul")
        G.many("appearance", [{"mid": 800 + i, "pid": old, "tid": eng, "played": 1, "goals": 1 if i == 2 else 0}], "fjelstul")
    out = publish.people(G, str(tmp_path / "o"))
    ix = json.load(open(tmp_path / "o" / "people" / "index.json", encoding="utf-8"))
    assert ix[f"k{old}"] == {"name": "Stanley Matthews", "name_ar": "ستانلي ماثيوز", "born": "1915-02-01", "died": None,
                             "nat": "إنجلترا", "wc": [["1954", 2, 1], ["1950", 1, 0]]}
    assert "30981" in ix                  # FotMob knows him: keyed by his FotMob id, a page wherever the site has no current one
    assert out == {"people": 2, "intl": 0}


def test_caps_and_goals_from_the_national_teams_records(tmp_path):
    G, messi = graph(tmp_path)
    old = G.c.execute("select pid from player where name='Stanley Matthews'").fetchone()[0]
    G.c.execute("insert into intl_record values(?, 'England', 54, 11, '1934–1957', 'wikipedia')", (old,))
    G.c.execute("insert into intl_record values(?, 'Argentina', 196, 116, '2005–present', 'wikipedia')", (messi,))
    caps_only = 900
    G.put("player", {"pid": caps_only, "name": "Subait Khater"}, "wikidata")
    G.c.execute("insert into intl_record values(?, 'United Arab Emirates', 120, 11, '1999–2011', 'wikipedia')", (caps_only,))
    publish.people(G, str(tmp_path / "o"))
    intl = json.load(open(tmp_path / "o" / "people" / "intl.json", encoding="utf-8"))
    assert intl == {"30981": ["Argentina", 196, 116, "2005–present"], f"k{old}": ["England", 54, 11, "1934–1957"],
                    f"k{caps_only}": ["United Arab Emirates", 120, 11, "1999–2011"]}
    ix = json.load(open(tmp_path / "o" / "people" / "index.json", encoding="utf-8"))
    assert f"k{caps_only}" in ix and ix[f"k{caps_only}"]["nat"] == "United Arab Emirates"     # 30 caps or more: a page of his own


def test_a_club_keeps_the_name_it_had_in_that_season(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League"}, "fotmob")
    G.xref("competition", lg, "fotmob", 538, "fotmob-native")
    sa = reg.mint("team", "fotmob", 102119)
    G.put("team", {"tid": sa, "name": "Al-Ahli", "name_ar": "شباب الأهلي"}, "fotmob")
    G.xref("team", sa, "fotmob", 102119, "fotmob-native")
    for season in ("2015/2016", "2022/2023"):
        e = reg.mint("edition", "fotmob", f"538|{season}")
        G.put("edition", {"eid": e, "cid": lg, "season": season}, "fotmob")
        G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'champion', 1, ?, 'fotmob')", (e, sa))
    G.c.commit()
    publish.editions(G, str(tmp_path / "o"), eras={102119: [["2017-07-01", "الأهلي"]]})
    d = json.load(open(tmp_path / "o" / "editions" / "538.json", encoding="utf-8"))
    assert {s["season"]: s["champion"]["name"] for s in d["seasons"]} == {"2022/2023": "شباب الأهلي", "2015/2016": "الأهلي"}
    assert publish.era_names()[102119] == [["2017-07-01", "الأهلي"]]


def _league(tmp_path, season, results, champion, country="ENG"):
    """a league season of three clubs, its matches only (no standings), and its champion"""
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 47)
    G.put("competition", {"cid": lg, "name": "Premier League", "name_ar": "الدوري الإنجليزي الممتاز", "kind": "league", "country": country}, "fotmob")
    G.xref("competition", lg, "fotmob", 47, "fotmob-native")
    t = {}
    for f, ar in ((8650, "ليفربول"), (10260, "مانشستر يونايتد"), (8668, "إيفرتون")):
        t[f] = reg.mint("team", "fotmob", f)
        G.put("team", {"tid": t[f], "name": str(f), "name_ar": ar}, "fotmob")
        G.xref("team", t[f], "fotmob", f, "fotmob-native")
    e = reg.mint("edition", "fotmob", f"47|{season}")
    G.put("edition", {"eid": e, "cid": lg, "season": season}, "fotmob")
    for i, (h, a, hs, as_) in enumerate(results):
        G.put("match", {"mid": reg.mint("match", "sch", f"m{i}"), "eid": e, "date": f"{season[:4]}-10-{i + 1:02d}", "home": t[h], "away": t[a], "hs": hs, "as_": as_, "status": "finished"}, "sch")
    G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'champion', 1, ?, 's365')", (e, t[champion]))
    G.c.commit()
    publish.editions(G, str(tmp_path / "o"))
    return json.load(open(tmp_path / "o" / "editions" / "47.json", encoding="utf-8"))["seasons"][0]


RESULTS = [(8650, 10260, 2, 0), (10260, 8650, 1, 1), (8650, 8668, 3, 1), (8668, 8650, 0, 0), (10260, 8668, 2, 1), (8668, 10260, 2, 2)]


def test_a_league_season_with_no_standings_gets_its_table_from_its_matches(tmp_path):
    # the Premier League's 2015/16 and every season before showed no table: the DB holds the matches, not the standings
    s = _league(tmp_path, "2015/2016", RESULTS, 8650)
    assert s["table"][0] == [1, 8650, "ليفربول", 4, 2, 2, 0, 6, 2, 8]          # three points a win
    assert [r[1] for r in s["table"]] == [8650, 10260, 8668] and s["table_from_matches"] is True


def test_two_points_a_win_before_the_three_point_rule(tmp_path):
    s = _league(tmp_path, "1975/1976", RESULTS, 8650)
    assert s["table"][0][9] == 6                                                # England: three points from 1981/82


def test_a_computed_table_whose_first_is_not_the_champion_is_not_shown(tmp_path):
    # a season decided by play-offs, groups or a split: the matches' table is not the final standing
    s = _league(tmp_path, "2015/2016", RESULTS, 10260)
    assert not s.get("table")


def test_a_season_that_plays_as_a_league_gets_its_table_whatever_its_competitions_kind():
    from graph.publish import looks_like_league
    assert looks_like_league([(h, a, 1, 0) for h, a, *_ in RESULTS])                       # each plays each, home and away
    assert not looks_like_league([(1, 2, 1, 0), (3, 4, 2, 0), (1, 3, 0, 0)])                 # a cup: unequal games, pairs missing


def test_a_strict_round_robin_shows_its_table_with_no_champion_known():
    from graph.publish import strict_round_robin
    assert strict_round_robin([(h, a, 1, 0) for h, a, *_ in RESULTS])                       # each pair twice, each club four games
    assert not strict_round_robin([(h, a, 1, 0) for h, a, *_ in RESULTS] + [(8650, 10260, 1, 0)])   # a play-off on top


def test_a_seasons_tournaments_are_parts_of_its_row_not_seasons_of_their_own(tmp_path):
    # Argentina: 365Scores' «2009/2010 Apertura» and «2009/2010 Clausura» beside FotMob's «2009/2010» were three seasons in the list
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 112)
    G.put("competition", {"cid": lg, "name": "Liga Profesional", "name_ar": "الدوري الأرجنتيني", "kind": "league"}, "fotmob")
    G.xref("competition", lg, "fotmob", 112, "fotmob-native")
    ids = {}
    for f, ar in ((10077, "بانفيلد"), (10087, "أرجنتينوس جونيورز"), (10083, "ريفر بليت")):
        t = ids[f] = reg.mint("team", "fotmob", f)
        G.put("team", {"tid": t, "name": str(f), "name_ar": ar}, "fotmob")
        G.xref("team", t, "fotmob", f, "fotmob-native")
    eds = {}
    for season, champ in (("2009/2010", 10087), ("2009/2010 Apertura", 10077), ("2009/2010 Clausura", 10087), ("1985 Metropolitano", 10083)):
        e = eds[season] = reg.mint("edition", "s365", f"112|{season}")
        G.put("edition", {"eid": e, "cid": lg, "season": season}, "s365")
        G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'champion', 1, ?, 's365')", (e, ids[champ]))
    G.put("match", {"mid": 1, "eid": eds["2009/2010"], "date": "2009-08-10", "home": ids[10077], "away": ids[10087], "hs": 1, "as_": 0}, "sch")
    G.c.commit()
    publish.editions(G, str(tmp_path / "o"))
    d = json.load(open(tmp_path / "o" / "editions" / "112.json", encoding="utf-8"))
    by = {s["season"]: s for s in d["seasons"]}
    assert sorted(by) == ["1985 Metropolitano", "2009/2010"]          # a tournament with no season row of its own stays a row
    assert by["2009/2010"]["parts"] == [{"name": "Apertura", "champion": {"fotmob": 10077, "name": "بانفيلد"}, "runner_up": None},
                                        {"name": "Clausura", "champion": {"fotmob": 10087, "name": "أرجنتينوس جونيورز"}, "runner_up": None}]


def test_every_man_with_a_wikidata_item_is_listed_for_the_photo_stage(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    p = reg.mint("player", "wikidata", "Q193464")
    G.put("player", {"pid": p, "name": "Alan Smith", "born": "1962-11-21"}, "wikidata")
    G.xref("player", p, "wikidata", "Q193464", "wikidata-native")
    q = reg.mint("player", "rsssf", "x")
    G.put("player", {"pid": q, "name": "No Item"}, "rsssf")
    G.c.commit()
    out = publish.person_qids(G, str(tmp_path / "o"))
    d = json.load(open(tmp_path / "o" / "people" / "qids.json", encoding="utf-8"))
    assert d == {f"k{p}": ["Q193464", "1962-11-21", "Alan Smith"]} and out["qids"] == 1


def test_every_coach_with_a_wikidata_item_is_listed_for_the_photo_stage_as_c_his_id(tmp_path):
    # «كلهم بصورهم» (22 Nov): the archive's coach pages, /coach/k<id>/, carry v1/ph/c<id>.webp
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    k = reg.mint("coach", "wikidata", "Q55")
    G.put("coach", {"kid": k, "name": "George Graham", "born": "1944-11-30"}, "wikidata")
    G.xref("coach", k, "wikidata", "Q55", "wikidata-native")
    G.c.commit()
    out = publish.person_qids(G, str(tmp_path / "o"))
    d = json.load(open(tmp_path / "o" / "people" / "qids.json", encoding="utf-8"))
    assert d == {f"c{k}": ["Q55", "1944-11-30", "George Graham"]} and out["qids"] == 1
