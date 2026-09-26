"""uaepl.ae parsing: the reversed Arabic score, goals-against-first standings, UAE local time."""
from sources.uaepl import parse_fixtures, parse_score_ar, parse_score_en, parse_standings, UaePL


def test_arabic_score_string_is_away_home():
    # «عجمان 3:2 كلباء» on the Arabic page = Ajman 2-3 Kalba
    assert parse_score_ar("3:2") == {"home": 2, "away": 3}
    assert parse_score_en("2:3") == {"home": 2, "away": 3}
    assert parse_score_ar("‎0:1") == {"home": 1, "away": 0}
    assert parse_score_ar("") is None and parse_score_en(None) is None


def test_week5_arabic_scores_reversed_equal_english(fx):
    rows = parse_fixtures(fx("uaepl_fixtures_w5_en.json")["html"], fx("uaepl_fixtures_w5_ar.json")["html"])
    assert len(rows) == 7
    for r in rows:
        assert r["score_ar"] and r["score_en"]
        assert parse_score_ar(r["score_ar"]) == parse_score_en(r["score_en"]), r
    ajman = next(r for r in rows if r["home_slug"] == "ajman")
    assert ajman["away_slug"] == "kalba" and ajman["score_ar"] == "3:2" and ajman["score_en"] == "2:3"
    assert ajman["home_ar"] == "عجمان" and ajman["stadium_ar"] == "استاد راشد بن سعيد"
    # asymmetric scores prove the direction: Hatta 1-2 Al Dhafra, Al Wahda 1-0 Sharjah
    hatta = next(r for r in rows if r["home_slug"] == "hatta")
    assert parse_score_ar(hatta["score_ar"]) == {"home": 1, "away": 2}
    wahda = next(r for r in rows if r["home_slug"] == "al-wahda")
    assert parse_score_ar(wahda["score_ar"]) == {"home": 1, "away": 0}


def test_arabic_only_fallback_uses_reversal(fx):
    """With no /en/ score, the normalizer must reverse the Arabic string, not read it positionally."""
    up = UaePL()
    rows = parse_fixtures(fx("uaepl_fixtures_w5_en.json")["html"], fx("uaepl_fixtures_w5_ar.json")["html"])
    ajman = dict(next(r for r in rows if r["home_slug"] == "ajman"))
    ajman["score_en"] = None
    m = up.normalize_fixture(538, ajman)
    assert m["score"] == {"home": 2, "away": 3}
    assert m["home"]["id"] == 149994 and m["away"]["id"] == 209190


def test_uaepl_local_time_to_utc(fx):
    up = UaePL()
    rows = parse_fixtures(fx("uaepl_fixtures_w5_en.json")["html"], fx("uaepl_fixtures_w5_ar.json")["html"])
    ajman = next(r for r in rows if r["home_slug"] == "ajman")
    m = up.normalize_fixture(538, ajman)
    # Fri 11 Sep 2026 20:15 in the UAE (UTC+4)
    assert m["kickoff_utc"] == "2026-09-11T16:15:00Z"
    assert m["kickoff_uae"] == "2026-09-11T20:15:00+04:00"
    assert m["status"] == "finished" and m["round"] == "5"


def test_standings_goals_against_column_comes_first(fx):
    rows = parse_standings(fx("uaepl_standings_en.json")["html"], fx("uaepl_standings_ar.json")["html"])
    assert [r["name"] for r in rows] == ["Al Jazira", "Al Ain", "Shabab AlAhli"]
    jaz = rows[0]
    # the page prints "Goal Against 2 | Goal For 11": mapped by label, not by position
    assert (jaz["gf"], jaz["ga"], jaz["gd"], jaz["pts"]) == (11, 2, 9, 13)
    assert jaz["name_ar"] == "الجزيرة"
    for r in rows:
        assert r["gf"] - r["ga"] == r["gd"]


def test_standings_normalized_team_ids(fx, monkeypatch):
    up = UaePL()
    pages = {"en": fx("uaepl_standings_en.json")["html"], "ar": fx("uaepl_standings_ar.json")["html"]}
    monkeypatch.setattr(up, "_get_html", lambda lang, path, params: pages[lang])
    st = up.standings({"id": 538, "uaepl": "x"})
    ids = [r["team"]["id"] for r in st["groups"][0]["rows"]]
    assert ids == [102101, 102117, 102119]
    assert st["source"] == "uaepl" and st["order"] == "source"
