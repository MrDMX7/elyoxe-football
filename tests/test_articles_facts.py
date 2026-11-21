"""news/articles/facts.py on real recorded matches (tests/fixtures/articles/)."""
import copy, json
from pathlib import Path
from news.articles import facts as F

FX = Path(__file__).parent / "fixtures" / "articles"
J = lambda n: json.loads((FX / n).read_text(encoding="utf-8"))
NAMES = {"players": {}, "coaches": {}, "referees": {}}


def test_the_sheet_carries_the_result_the_goals_in_order_and_the_table_with_games_played():
    md = J("match_1000022237.json")
    sheet, meta = F.report_sheet(md, J("standings_538.json"), J("fixtures_538.json"), NAMES)
    h, a = md["home"]["name_ar"], md["away"]["name_ar"]
    assert sheet["النتيجة النهائية"] == f"{h} {md['score']['home']} - {md['score']['away']} {a}"
    goals = [e for e in sheet["الأحداث بالترتيب"] if e["حدث"].startswith("هدف")]
    assert len(goals) == md["score"]["home"] + md["score"]["away"]
    rows = sheet["الترتيب الحالي في البطولة"]
    assert {r["الفريق"] for r in rows} == {h, a} and all("لعب" in r and "النقاط" in r for r in rows)
    assert meta["match"] == md["id"] and meta["comp"] == md["comp"] and not meta["thin"]


def test_a_postponed_round_is_stated_next_to_the_table():
    sheet, _ = F.report_sheet(J("match_1000022237.json"), J("standings_538.json"), J("fixtures_538.json"), NAMES)
    post = sheet.get("جولات مؤجلة") or []
    assert any(p["الجولة"] == "الجولة 7" for p in post)                      # ADNOC round 7, moved to 29-30 December


def test_derived_numbers_are_ready_made():
    md = J("match_5181860.json")                                            # Spain 2-3 England
    sheet, _ = F.report_sheet(md, None, None, NAMES)
    d = sheet["أرقام محسوبة"]
    assert d["مجموع الأهداف"] == 5 and d["فارق الأهداف"] == 1
    assert d["الفائز"] == md["away"]["name_ar"]


def test_a_shootout_is_in_the_sheet():
    md = copy.deepcopy(J("match_5181860.json"))
    md["score"] = {"home": 1, "away": 1}; md["penalties"] = {"home": 4, "away": 3}
    sheet, _ = F.report_sheet(md, None, None, NAMES)
    assert sheet["ركلات الترجيح"] == f"{md['home']['name_ar']} 4 - 3 {md['away']['name_ar']}"
    assert sheet["أرقام محسوبة"]["الفائز"] == md["home"]["name_ar"]


def test_a_match_without_events_or_stats_is_thin():
    md = copy.deepcopy(J("match_5181860.json")); md["events"] = []; md["stats"] = []; md["lineups"] = {}
    _, meta = F.report_sheet(md, None, None, NAMES)
    assert meta["thin"]


def test_the_fingerprint_moves_when_a_goal_changes_scorer():
    md = J("match_5181860.json")
    _, m1 = F.report_sheet(md, None, None, NAMES)
    md2 = copy.deepcopy(md)
    g = next(e for e in md2["events"] if e["type"] in ("goal", "penalty_goal", "own_goal"))
    g["player"] = {"id": 1, "name": "Someone Else"}
    _, m2 = F.report_sheet(md2, None, None, NAMES)
    assert m1["fingerprint"] != m2["fingerprint"]


def test_a_team_without_an_arabic_name_falls_back_to_its_name():
    # final review: «"فوز " + None» crashed the sheet for a team FotMob has no Arabic name for
    md = copy.deepcopy(J("match_5181860.json")); md["home"]["name_ar"] = None
    sheet, _ = F.report_sheet(md, None, None, NAMES)
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "site", "ai")); import checks as AI
    assert sheet["صاحب الأرض"] and sheet["صاحب الأرض"] == (AI._clubs().get(str(md["home"]["id"])) or md["home"]["name"])   # Tifo's dictionary, else the name


def test_the_sheet_never_asks_for_a_transliteration(monkeypatch):
    # gen.py sets checks.TRANSLIT to a Gemini call that writes names/clubs_ar.json; the sheet must stay offline
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "site", "ai")); import checks as AI
    def no(*a, **k):
        raise AssertionError("transliteration called")
    monkeypatch.setattr(AI, "TRANSLIT", no)
    md = copy.deepcopy(J("match_5181860.json")); md["home"]["name_ar"] = None; md["home"]["id"] = 999999999
    sheet, _ = F.report_sheet(md, None, None, NAMES)
    assert sheet["صاحب الأرض"] == md["home"]["name"]


# phase 8 (Tifo graph): the sheet's «من أرشيف تيفو» comes from the graph's published files only
GRAPH = {
    "motm/index.json": {"since": "2026-07-01", "today": "2026-11-07", "counted": []},
    "motm/players.json": {"535603": {"name": "مالكوم", "total": 30, "now": 4}},
    "coaches/coaches.json": {"7": {"name": "Cosmin Olăroiu", "fotmob": 78656, "spells": [
        {"team": 102101, "m": 40, "w": 20, "d": 10, "l": 10, "start": "2023-07-01", "end": "2026-11-08"}, {"team": 9, "m": 60, "w": 40, "d": 10, "l": 10}]}},
    "editions/538.json": {"seasons": [{"season": "2026/2027", "champion": None},
                                      {"season": "2025/2026", "champion": {"fotmob": 102113, "name": "شباب الأهلي"}},
                                      {"season": "2020/2021", "champion": {"fotmob": 102101, "name": "الجزيرة"}},
                                      {"season": "2016/2017", "champion": {"fotmob": 102101, "name": "الجزيرة"}}]},
    "awards/index.json": {"awards": [{"key": "golden-ball", "name_ar": "الكرة الذهبية"}]},
    "awards/players.json": {"535603": [["golden-ball", "2019", "winner", 1, None], ["golden-ball", "2020", "winner", 2, None],
                                       [None, "2024/2025", "top_scorer", 1, 538]]},
}


def test_the_graph_adds_the_man_of_the_match_coaches_titles_and_awards():
    md = J("match_1000022237.json")
    g = F.graph_sheet(md, GRAPH_ALL.get, NAMES)
    assert g["رجل المباراة (أعلى تقييم)"] == {"اللاعب": "Malcom", "التقييم": 8.4, "مرات رجل المباراة هالموسم مع هالمباراة": 5,
                                               "مرات رجل المباراة في مسيرته مع هالمباراة": 31}
    assert g["سجل المدربين قبل هالمباراة"]["Cosmin Olăroiu"] == {"كل مسيرته": "100 مباراة: 60 فوز، 20 تعادل، 20 خسارة",
                                                                  "مع الجزيرة": "40 مباراة: 20 فوز، 10 تعادل، 10 خسارة",
                                                                  "مع الجزيرة ضد الوصل": "2 مباراة: 1 فوز، 1 تعادل، 0 خسارة"}
    assert "Rui Vitória" not in g["سجل المدربين قبل هالمباراة"]        # not in the graph: left out, never guessed
    assert g["ألقاب البطولة"] == {"الجزيرة": 2, "الوصل": 0} and g["آخر بطل"] == "شباب الأهلي (2025/2026)"
    assert g["ألقاب فردية للاعبين"] == {"Malcom": ["الكرة الذهبية 2019", "هداف هالبطولة 2024/2025"]}


def test_a_match_already_counted_is_not_counted_again_and_a_missing_file_costs_nothing():
    md = J("match_1000022237.json")
    files = dict(GRAPH, **{"motm/index.json": {"since": "2026-07-01", "today": "2026-11-09", "counted": [md["id"]]}})
    assert F.graph_sheet(md, files.get, NAMES)["رجل المباراة (أعلى تقييم)"]["مرات رجل المباراة هالموسم مع هالمباراة"] == 4

    def broken(path):
        raise OSError("no network")
    assert F.graph_sheet(md, broken, NAMES) == {}
    sheet, _ = F.report_sheet(md, J("standings_538.json"), J("fixtures_538.json"), NAMES, graph=F.graph_sheet(md, GRAPH.get, NAMES))
    assert sheet["من أرشيف تيفو"]["آخر بطل"] == "شباب الأهلي (2025/2026)"


# the graph's h2h-all/ and matches/ files: the fixture's whole history, before this match (graph phase 7)
H2H = {"teams": ["102101", "102111"], "names": ["الجزيرة", "الوصل"], "n": 5, "w": [2, 1, 2], "goals": [8, 7], "first": "1990-02-02",
       "matches": [["2026-11-08", "دوري أدنوك", "2026/2027", "102101", 2, 1, "102111", "1000022237"],     # this match: left out
                   ["2025-03-01", "دوري أدنوك", "2024/2025", "102111", 1, 1, "102101", "4000"],
                   ["2024-10-05", "كأس رئيس الدولة", "2024/2025", "102101", 3, 0, "102111", "3000"],
                   ["2023-01-10", "دوري أدنوك", "2022/2023", "102111", 4, 2, "102101", "2000"],
                   ["1990-02-02", "دوري أدنوك", "1989/1990", "102101", 0, 1, "102111", "k55"]]}
TEAM = {"team": 102101, "matches": [
    {"id": "1000022237", "date": "2026-11-08", "h": [102101, "الجزيرة"], "a": [102111, "الوصل"], "s": [2, 1],
     "ev": [[60, 0, "goal", "h", "Malcom", "535603"]], "lu": {"h": [["Malcom", "535603", 10, 1]]}},
    {"id": "4000", "date": "2025-03-01", "h": [102111, "الوصل"], "a": [102101, "الجزيرة"], "s": [1, 1],
     "ev": [[30, 0, "goal", "a", "Malcom", "535603"]], "lu": {"a": [["Malcom", "535603", 10, 0]]}},
    {"id": "3000", "date": "2024-10-05", "h": [102101, "الجزيرة"], "a": [102111, "الوصل"], "s": [3, 0],
     "ev": [[10, 0, "goal", "h", "Malcom", "535603"], [50, 0, "penalty_goal", "h", "Malcom", "535603"],
            [70, 0, "own_goal", "a", "Someone", "9"]], "lu": {"h": [["Malcom", "535603", 10, 1]]}},
    {"id": "5000", "date": "2024-01-01", "h": [102101, "الجزيرة"], "a": [102113, "شباب الأهلي"], "s": [1, 0],
     "ev": [[5, 0, "goal", "h", "Malcom", "535603"]], "lu": {"h": [["Malcom", "535603", 10, 1]]}}]}
GRAPH_ALL = dict(GRAPH, **{"h2h-all/102101-102111.json": H2H, "matches/index.json": {"teams": {"102101": 4}},
                           "matches/team-102101.json": TEAM})


def test_the_whole_fixture_history_before_this_match():
    g = F.graph_sheet(J("match_1000022237.json"), GRAPH_ALL.get, NAMES)
    assert g["المواجهات بين الفريقين في كل البطولات قبل هالمباراة"] == {
        "عدد المواجهات": 4, "فوز الجزيرة": 1, "تعادل": 1, "فوز الوصل": 2, "الأهداف": "الجزيرة 6 - 6 الوصل",
        "أول مواجهة": "الجزيرة 0 - 1 الوصل (1990-02-02، دوري أدنوك)",
        "آخر مواجهة": "الوصل 1 - 1 الجزيرة (2025-03-01، دوري أدنوك)",
        "أكبر فوز": "الجزيرة 3 - 0 الوصل (2024-10-05، كأس رئيس الدولة)"}


def test_a_scorer_record_against_this_opponent_from_the_team_file():
    g = F.graph_sheet(J("match_1000022237.json"), GRAPH_ALL.get, NAMES)
    assert g["سجل اللاعبين ضد هالمنافس قبل هالمباراة"] == {"Malcom ضد الوصل": "لعب 2 مباراة وسجل 3 هدف"}


def test_no_h2h_file_means_no_h2h_lines():
    g = F.graph_sheet(J("match_1000022237.json"), GRAPH.get, NAMES)
    assert "المواجهات بين الفريقين في كل البطولات قبل هالمباراة" not in g and "سجل اللاعبين ضد هالمنافس قبل هالمباراة" not in g
    assert "مع الجزيرة ضد الوصل" not in g["سجل المدربين قبل هالمباراة"]["Cosmin Olăroiu"]
