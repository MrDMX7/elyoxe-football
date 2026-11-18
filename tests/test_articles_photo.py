"""news/articles/photo.py: a frame of the match first (the highlights video's YouTube thumbnail, 1280x720), then a goal clip's,
then Tifo's match card; a picture under 1200 px wide is skipped; the chosen one is copied to v1/news/img/<id>.jpg."""
import io
from PIL import Image
from store import Store, LocalBackend
from news.articles import photo as P

MD = {"id": 77, "home": {"name_ar": "أ"}, "away": {"name_ar": "ب"}}
MEDIA = {"highlights": [{"id": "abc", "source": "youtube", "channel": "beIN SPORTS", "image": "https://i.ytimg.com/vi/abc/hqdefault.jpg"}],
         "goals": {"12-5": [{"id": "def", "source": "youtube", "channel": "LaLiga", "image": "https://i.ytimg.com/vi/def/hqdefault.jpg"}]}}


def jpg(w, h):
    b = io.BytesIO(); Image.new("RGB", (w, h), (10, 120, 80)).save(b, "JPEG"); return b.getvalue()


def test_the_order_of_the_candidates():
    c = P.candidates(MD, MEDIA)
    assert c[0]["url"] == "https://i.ytimg.com/vi/abc/maxresdefault.jpg" and "beIN SPORTS" in c[0]["caption"]
    assert c[1]["url"] == "https://i.ytimg.com/vi/def/maxresdefault.jpg"
    assert c[-1]["source"] == "card" and c[-1]["url"].endswith("/og/m-77.png")


def test_a_small_picture_is_skipped_and_the_chosen_one_is_stored(tmp_path):
    st = Store(LocalBackend(tmp_path))
    sizes = {"https://i.ytimg.com/vi/abc/maxresdefault.jpg": jpg(480, 360), "https://i.ytimg.com/vi/def/maxresdefault.jpg": jpg(1280, 720)}
    got = P.pick("r-77", MD, MEDIA, sizes.get, st)
    assert got["url"].endswith("/v1/news/img/r-77.jpg") and got["w"] == 1200 and got["h"] == 675 and not got["card"]
    assert (tmp_path / "v1" / "news" / "img" / "r-77.jpg").exists()


def test_no_frame_means_the_match_card(tmp_path):
    got = P.pick("r-77", MD, None, lambda u: None, Store(LocalBackend(tmp_path)))
    assert got["card"] and got["w"] == 1200 and got["h"] == 630
