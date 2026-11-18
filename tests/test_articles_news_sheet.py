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
        assert any(k.endswith("هذا الموسم") for k in sheet["بيانات تيفو"])


def test_breaking_is_its_own_kind():
    sheet, _ = F.news_sheet(TRANSFER, S["items"], TEXTS, data_get, AR, {}, breaking=True)
    assert sheet["النوع"] == "عاجل"
