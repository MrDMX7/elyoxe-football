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
