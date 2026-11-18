# tests/test_articles_news_sheet.py
"""facts.news_sheet on the recorded transfer story. The sheet carries:
- the kind and stage, and the credibility mark;
- the source texts and the other headlines;
- the Arabic names from Tifo's dictionary;
- Tifo's data on the players and clubs the story names."""
import json
from pathlib import Path
from news.articles import facts as F

S = json.loads((Path(__file__).parent / "fixtures" / "articles" / "news_state.json").read_text(encoding="utf-8"))
TRANSFER = list(S["stories"].values())[0]
TEXTS = [{"source": "Club", "lang": "en", "url": "https://x.com/1", "tier": "official", "text": "Official.", "image": None}]
AR = {tuple(e): f"اسم {i}" for i, e in enumerate(TRANSFER["anchor"])}


def data_get(path):
    if path.startswith("player/"):
        return {"name": "P", "team": {"name_ar": "النادي"}, "minutes": 900, "goals": 4, "assists": 2, "rating": 7.1}
    return None


def test_the_sheet_carries_the_news_and_tifos_context():
    sheet, meta = F.news_sheet(TRANSFER, S["items"], TEXTS, data_get, AR, {})
    assert sheet["النوع"] == "خبر" and sheet["التصنيف"].startswith("انتقالات")
    assert sheet["نصوص المصادر (للحقائق فقط، لا تُنسخ)"][0]["النص"] == "Official."
    assert sheet["مؤشر المصداقية في تيفو (من 100)"] is not None
    assert set(sheet["الأسماء بالعربية (استعملها كما هي)"]) == set(AR.values())
    assert meta["story"] == TRANSFER["id"] and meta["items"] == len(TRANSFER["items"]) and meta["subject"] in AR.values()
    if TRANSFER["anchor"][0][0] == "player":
        assert meta["query"] == "P"                          # the Latin name, for the Commons photo search
    if any(e[0] == "player" for e in TRANSFER["anchor"]):
        assert any("هذا الموسم" in k for k in sheet["بيانات تيفو"])


def test_breaking_is_its_own_kind():
    sheet, _ = F.news_sheet(TRANSFER, S["items"], TEXTS, data_get, AR, {}, breaking=True)
    assert sheet["النوع"] == "عاجل"


def test_a_players_team_is_an_id_in_tifos_data():
    """player/<id>.json carries the team as its id (live data, dry run 2026-11-19): the club's name comes from the dictionary."""
    real = lambda path: {"name": "Weston McKennie", "team": 9885, "comp": 55, "minutes": 613, "goals": 1} if path.startswith("player/") else None
    sheet, _ = F.news_sheet(TRANSFER, S["items"], TEXTS, real, {**AR, ("team", 9885): "يوفنتوس"}, {})
    rows = [v for k, v in sheet["بيانات تيفو"].items() if "هذا الموسم" in k]
    assert rows and rows[0]["الفريق"] == "يوفنتوس" and rows[0]["الدقائق"] == 613


def test_the_subject_is_who_the_headline_is_about():
    """The journal's seed is who the first headline names; the anchor lists everyone (dry run 2026-11-19: an Arda Güler
    article's photo was captioned «كيليان مبابي», the first player in the anchor)."""
    story = dict(TRANSFER, seed=[TRANSFER["anchor"][-1]])
    _, meta = F.news_sheet(story, S["items"], TEXTS, data_get, AR, {})
    assert meta["subject"] == AR[tuple(TRANSFER["anchor"][-1])]


def test_the_table_is_the_league_and_every_number_names_its_competition():
    """Real Madrid's comps are [78 Club World Cup, 87 LaLiga, 42 Champions League]: the first one gave «يتصدر ريال مدريد الترتيب
    برصيد 7 نقاط من 3 مباريات» (dry run 2026-11-19). The table is the league's, and the player's numbers say which competition."""
    story = {"id": "x", "kind": "transfer", "anchor": [["player", 1], ["team", 8633]], "items": []}
    table = {"groups": [{"rows": [{"rank": 2, "team": {"id": 8633, "name_ar": "ريال مدريد"}, "played": 12, "pts": 30}]}]}
    def get(path):
        if path == "player/1.json":
            return {"name": "Arda Guler", "team": 8633, "comp": 42, "minutes": 109, "goals": 1}
        return table if path == "comp/87/standings.json" else {"groups": [{"rows": [{"rank": 1, "team": {"id": 8633}, "played": 3, "pts": 7}]}]}
    sheet, _ = F.news_sheet(story, {}, TEXTS, get, {("player", 1): "أردا غولر", ("team", 8633): "ريال مدريد"}, {"8633": {"comps": [78, 87, 42]}})
    tifo = sheet["بيانات تيفو"]
    assert tifo["ترتيب ريال مدريد في الدوري الإسباني"] == {"المركز": 2, "لعب": 12, "النقاط": 30}
    assert "أردا غولر هذا الموسم في دوري أبطال أوروبا" in tifo and len(tifo) == 2


def test_a_player_only_story_cards_the_players_club():
    """With no club named, Tifo's card used to be an empty dark frame (final review, finding 9): the player's club is used."""
    story = {"id": "x", "kind": "injury", "anchor": [["player", 1]], "items": []}
    _, meta = F.news_sheet(story, {}, TEXTS, lambda p: {"name": "A", "team": 8634} if p == "player/1.json" else None, {}, {})
    assert meta["teams"] == [] and meta["card_teams"] == [8634]
