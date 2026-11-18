"""desk/lambda/app.py: the desk's API (Phase 2b), on the repo's LocalBackend. The key, the queue's actions, «اسحب», editing by
hand with versions, the photo pick, and that the Lambda writes the store's own file format."""
import io, json, sys
from datetime import datetime, timezone
from pathlib import Path
import pytest
from PIL import Image
from store import Store, LocalBackend

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desk" / "lambda"))
import app as A          # noqa: E402
import s3store           # noqa: E402

KEY = "k" * 32
NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
DOC = {"id": "n-s1", "kind": "news", "headline": "عنوان", "standfirst": "مقدمة", "sections": [{"subhead": "ق", "paragraphs": ["فقرة 7"]}],
       "facts_box": ["حقيقة"], "image": {"url": "https://x/1.jpg", "w": 1200, "h": 675, "caption": "ك"}, "author": "تحرير تيفو",
       "published": "2026-11-19T10:00:00+00:00", "modified": "2026-11-19T10:00:00+00:00", "version": 1, "entities": [], "breaking": False}


def jpg(w, h):
    b = io.BytesIO(); Image.new("RGB", (w, h), (9, 9, 9)).save(b, "JPEG"); return b.getvalue()


@pytest.fixture
def env(tmp_path):
    repo = Store(LocalBackend(tmp_path))                       # the repo's store: what the journal and the site read
    repo.put_json("news/a/n-s1.json", DOC, cache="warm")
    repo.put_json("news/articles.json", {"articles": [{k: DOC[k] for k in ("id", "kind", "headline", "published", "modified")}]})
    repo.put_json("news/articles-all.json", {"articles": [{k: DOC[k] for k in ("id", "kind", "published", "modified")}]})
    repo.put_state("articles/desk-view.json", {"stories": [{"id": "s2", "status": "queued"}], "written_today": 1, "daily": 60})
    repo.put_state("articles/spend.json", {"2026-11": {"usd": 3.5, "calls": 90, "by_type": {"news": 3.0}, "capped": False}})
    repo.put_state("articles/sheets/n-s1.json", {"sheet": {"نص": "سجل 7 أهداف في 2031"}, "photos": [{"url": "https://p/big.jpg", "source": "ماركا"}]})
    desk = A.App(s3store.Store(LocalBackend(tmp_path)), KEY, now=lambda: NOW, fetch={"https://p/big.jpg": jpg(1600, 900)}.get)
    return repo, desk


def call(desk, method, path, body=None, key=KEY, query=None):
    return desk.handle(method, path, query or {}, json.dumps(body) if body is not None else "", {"x-desk-key": key} if key else {})


def test_no_key_or_a_wrong_key_is_refused_and_the_page_is_served(env):
    _, desk = env
    assert call(desk, "GET", "/api/view", key=None)[0] == 401
    assert call(desk, "GET", "/api/view", key="x" * 32)[0] == 401
    status, body, ctype = desk.handle("GET", "/", {}, "", {})
    assert status == 200 and ctype.startswith("text/html") and "لوحة تيفو" in body


def test_the_view_has_the_queue_what_was_published_and_the_spend(env):
    _, desk = env
    status, v, _ = call(desk, "GET", "/api/view")
    assert status == 200 and v["view"]["stories"][0]["id"] == "s2" and v["published"][0]["id"] == "n-s1"
    assert v["spend"]["usd"] == 3.5 and v["cap"] == 180


def test_reject_write_and_withdraw(env):
    repo, desk = env
    call(desk, "POST", "/api/act", {"action": "reject", "id": "s2"})
    assert "s2" in repo.get_state("articles/desk.json")["reject"]
    call(desk, "POST", "/api/act", {"action": "write", "id": "s2"})
    d = repo.get_state("articles/desk.json")
    assert "s2" in d["write"] and "s2" not in d["reject"]
    call(desk, "POST", "/api/act", {"action": "withdraw", "id": "n-s1"})
    assert "n-s1" in repo.get_state("articles/desk.json")["withdraw"]
    assert repo.get_json("news/articles.json")["articles"] == [] and repo.get_json("news/articles-all.json")["articles"] == []
    assert call(desk, "POST", "/api/act", {"action": "explode", "id": "s2"})[0] == 400


def test_an_edit_is_a_version_marks_the_article_edited_and_updates_the_lists(env):
    repo, desk = env
    status, out, _ = call(desk, "POST", "/api/edit", {"id": "n-s1", "headline": "عنوان جديد", "standfirst": "مقدمة",
                                                      "sections": [{"subhead": "ق", "paragraphs": ["فقرة 8"]}], "facts_box": []})
    doc = repo.get_json("news/a/n-s1.json")
    assert status == 200 and doc["headline"] == "عنوان جديد" and doc["edited"] is True and doc["version"] == 2
    assert doc["modified"] == NOW.isoformat() and doc["published"] == DOC["published"]
    assert repo.get_state("articles/versions/n-s1/1.json")["headline"] == "عنوان"
    assert repo.get_json("news/articles.json")["articles"][0]["headline"] == "عنوان جديد"
    assert call(desk, "POST", "/api/edit", {"id": "n-s1", "headline": " "})[0] == 400          # an empty headline is refused


def test_restore_puts_an_old_version_back_as_a_new_one(env):
    repo, desk = env
    call(desk, "POST", "/api/edit", {"id": "n-s1", "headline": "ثاني", "standfirst": "م", "sections": DOC["sections"], "facts_box": []})
    status, _, _ = call(desk, "POST", "/api/restore", {"id": "n-s1", "version": 1})
    doc = repo.get_json("news/a/n-s1.json")
    assert status == 200 and doc["headline"] == "عنوان" and doc["version"] == 3 and doc["edited"] is True
    _, art, _ = call(desk, "GET", "/api/article", query={"id": "n-s1"})
    assert [v["version"] for v in art["versions"]] == [1, 2]


def test_the_article_comes_with_its_photos_and_the_sheets_numbers(env):
    _, desk = env
    status, art, _ = call(desk, "GET", "/api/article", query={"id": "n-s1"})
    assert status == 200 and art["doc"]["headline"] == "عنوان" and art["photos"][0]["source"] == "ماركا"
    assert {"7", "2031"} <= set(art["numbers"])
    assert call(desk, "GET", "/api/article", query={"id": "n-zz"})[0] == 404


def test_a_photo_pick_is_cropped_stored_and_captioned(env, tmp_path):
    repo, desk = env
    status, out, _ = call(desk, "POST", "/api/photo", {"id": "n-s1", "url": "https://p/big.jpg", "source": "ماركا", "caption": "صلاح"})
    doc = repo.get_json("news/a/n-s1.json")
    assert status == 200 and doc["image"]["caption"] == "صلاح — الصورة من ماركا" and doc["edited"] is True
    stored = tmp_path / "v1" / "news" / "img" / "n-s1-2.jpg"
    assert stored.exists() and Image.open(stored).size == (1200, 675)
    assert call(desk, "POST", "/api/photo", {"id": "n-s1", "url": "https://p/missing.jpg", "source": "x"})[0] == 400


def test_the_lambda_writes_the_stores_own_format(tmp_path):
    s3store.Store(LocalBackend(tmp_path)).put_json("x.json", {"a": "ع"}, cache="hot")
    s3store.Store(LocalBackend(tmp_path)).put_state("y.json", {"b": 1})
    repo = Store(LocalBackend(tmp_path))
    assert repo.get_json("x.json") == {"a": "ع"} and repo.get_state("y.json") == {"b": 1}
    assert json.loads((tmp_path / "v1" / "x.json.meta").read_text())["CacheControl"] == "public, max-age=20, stale-while-revalidate=20"
