# tests/test_articles_news_check_photo.py
"""check.check_news, the news photo and Writer.pick_photo. The spec and the owner's plan review ask for:
- the source named once;
- the photo that fits the news best, from the outlets that carried it or from the internet, at least 1200 px, with a
  caption that says who it shows and where it is from; else Tifo's card."""
import io, json, types
from PIL import Image
from store import Store, LocalBackend
from news.articles import check as C, photo as P, write as WR

SHEET = {"النوع": "خبر", "نصوص المصادر (للحقائق فقط، لا تُنسخ)": [{"المصدر": "ماركا", "النص": "x"}]}
art = lambda *p: {"headline": "ع", "standfirst": "م", "sections": [{"subhead": "ق", "paragraphs": list(p)}], "facts_box": []}


def jpg(w, h):
    b = io.BytesIO(); Image.new("RGB", (w, h), (1, 2, 3)).save(b, "JPEG"); return b.getvalue()


IMGS = {"https://i/small.jpg": jpg(800, 450), "https://i/big.jpg": jpg(1600, 900), "https://i/wide.jpg": jpg(2000, 1125)}
CANDS = [{"url": "https://i/small.jpg", "source": "A"}, {"url": "https://i/big.jpg", "source": "B"}, {"url": "https://i/wide.jpg", "source": "ويكيميديا كومنز"}]


def test_the_source_named_again_and_again_fails():
    once = art("قال اللاعب بحسب ماركا إنه سعيد. " + "كلمة " * 260)
    thrice = art("بحسب ماركا وصل اللاعب. وبحسب ماركا وقّع. ونقلاً عن ماركا سيُقدَّم غداً. " + "كلمة " * 260)
    assert not [f for f in C.check_news(once, SHEET, (250, 450)) if "attribution" in f]
    assert [f for f in C.check_news(thrice, SHEET, (250, 450)) if "attribution" in f]


def test_candidates_come_from_the_sources_the_items_and_the_internet_once_each():
    texts = [{"source": "AS", "image": "https://i/a.jpg"}, {"source": "BBC", "image": None}]
    story = {"items": ["x", "y"], "image": "https://i/a.jpg"}
    items = {"x": {"source": "Kooora", "image": "https://i/k.jpg"}, "y": {"source": "AS", "image": "https://i/a.jpg"}}
    got = P.news_candidates(texts, story, items, [{"url": "https://c/1.jpg", "source": "ويكيميديا كومنز"}])
    assert [c["url"] for c in got] == ["https://i/a.jpg", "https://i/k.jpg", "https://c/1.jpg"]
    assert [c["source"] for c in got] == ["AS", "Kooora", "ويكيميديا كومنز"]


def test_commons_reads_the_search_api():
    api = {"query": {"pages": {"1": {"index": 2, "imageinfo": [{"thumburl": "https://u/2.jpg", "width": 3000}]},
                               "2": {"index": 1, "imageinfo": [{"thumburl": "https://u/1.jpg", "width": 2000}]}}}}
    got = P.commons("Mohamed Salah", get_json=lambda url: api)
    assert [c["url"] for c in got] == ["https://u/1.jpg", "https://u/2.jpg"] and got[0]["source"] == "ويكيميديا كومنز"
    assert P.commons("x", get_json=lambda url: None) == []


def test_the_judge_picks_among_the_big_ones_and_the_caption_says_who_and_where(tmp_path):
    st, seen = Store(LocalBackend(tmp_path)), []
    def judge(headline, thumbs):
        seen.append((headline, len(thumbs))); return 1
    got = P.news_pick("n-1", CANDS, [10], IMGS.get, st, subject="محمد صلاح", headline="صلاح يجدد", judge=judge)
    assert seen == [("صلاح يجدد", 2)]                        # the 800 px photo never reaches the judge
    assert not got["card"] and got["caption"] == "محمد صلاح — الصورة من ويكيميديا كومنز"
    assert (tmp_path / "v1" / "news" / "img" / "n-1.jpg").exists()


def test_none_fits_means_tifos_card_and_a_failing_judge_means_the_widest(tmp_path):
    st = Store(LocalBackend(tmp_path))
    assert P.news_pick("n-2", CANDS, [10], IMGS.get, st, judge=lambda h, t: -1)["card"]
    def boom(h, t):
        raise RuntimeError("api down")
    got = P.news_pick("n-3", CANDS, [10], IMGS.get, st, subject="صلاح", judge=boom)
    assert got["caption"] == "صلاح — الصورة من ويكيميديا كومنز"
    assert P.news_pick("n-4", [], [10], IMGS.get, st, judge=boom)["card"]


class FakeClient:
    def __init__(self, answer):
        self.calls, self.answer = [], answer
        self.messages = types.SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        u = types.SimpleNamespace(input_tokens=900, output_tokens=10, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return types.SimpleNamespace(stop_reason="end_turn", usage=u, content=[types.SimpleNamespace(type="text", text=json.dumps(self.answer))])


def test_pick_photo_sends_the_photos_and_the_headline_to_haiku():
    c = FakeClient({"best": 1})
    best, usage = WR.Writer(c).pick_photo("صلاح يجدد", [jpg(400, 225), jpg(400, 225)])
    kw = c.calls[0]
    blocks = kw["messages"][0]["content"]
    assert best == 1 and usage["in"] == 900 and kw["model"] == "claude-haiku-5-5"
    assert [b["type"] for b in blocks].count("image") == 2 and "صلاح يجدد" in blocks[-1]["text"]
    assert WR.Writer(FakeClient({"best": -1})).pick_photo("x", [jpg(400, 225)])[0] == -1    # none fits


def test_an_answer_that_cannot_be_read_is_an_error_not_a_none():
    """«none fits» gives Tifo's card; a broken answer must not (final review, finding 10): it raises, and news_pick keeps the
    widest photo."""
    import pytest
    for bad in ({"best": 7}, "not json"):
        with pytest.raises(WR.WriteError):
            WR.Writer(FakeClient(bad)).pick_photo("x", [jpg(400, 225)])


def test_a_date_written_in_a_sources_language_counts_as_in_the_sheet():
    """«30 de junio de 2032» in a Spanish source is the sheet's date: the dry run (2026-11-19) failed a correct «30 يونيو»,
    and the rewrite dropped the fact."""
    sheet = {"النوع": "خبر", "نصوص المصادر (للحقائق فقط، لا تُنسخ)": [
        {"المصدر": "Real Madrid", "النص": "queda vinculado al club hasta el 30 de junio de 2032"},
        {"المصدر": "BBC", "النص": "The deal runs until June 30, and he joined on 1 July 2023."},
        {"المصدر": "كووورة", "النص": "انضم في 5 أغسطس"}]}
    dates = lambda a: [f for f in C.check_news(art(a + " " + "كلمة " * 260), sheet, (250, 450)) if f.startswith("date")]
    assert dates("يمتد العقد حتى 30 يونيو 2032، وكان انضم في 1 يوليو 2023 ثم في 5 أغسطس.") == []
    assert dates("يمتد العقد حتى 29 يونيو 2032.") == ["date «29 يونيو» is not in the sheet"]


def test_the_judge_is_told_which_photos_cover_the_story_and_never_to_pick_artwork():
    c = FakeClient({"best": 0})
    WR.Writer(c).pick_photo("ريال مدريد يمدد", [jpg(400, 225), jpg(400, 225)], sources=["ماركا", "ويكيميديا كومنز"])
    texts = [b["text"] for b in c.calls[0]["messages"][0]["content"] if b["type"] == "text"]
    assert "news outlet" in texts[0] and "archive" in texts[1]
    assert "painting" in texts[-1] and "building" in texts[-1]


def test_news_pick_hands_the_judge_each_photos_source(tmp_path):
    st, seen = Store(LocalBackend(tmp_path)), []
    def judge(headline, thumbs, sources):
        seen.append(sources); return 0
    P.news_pick("n-9", CANDS, [10], IMGS.get, st, headline="ع", judge=judge)
    assert seen == [["B", "ويكيميديا كومنز"]]
