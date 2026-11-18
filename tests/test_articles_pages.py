"""news/articles/pages.py, the fast «Article pages» step (spec 2026-11-19 §7): what changed is rendered from the full build's
shells, uploaded with the full build's headers, withdrawn pages deleted, new URLs sent to IndexNow; nothing when nothing changed."""
from store import Store, LocalBackend
from news.articles import pages as PG

SHELL = ('<html><head><title>__TITLE__</title><meta name="description" content="__DESC__"><link rel="canonical" href="https://tifo.elyoxe.com/news/__ID__/">'
         '<meta property="og:image" content="__OGURL__"><script type="application/ld+json">{"__LD__":1}</script></head><body>__BODY__</body></html>')
DOC = {"id": "n-1", "kind": "news", "topic": "injury", "headline": "عنوان", "standfirst": "مقدمة", "sections": [{"subhead": "ق", "paragraphs": ["فقرة"]}],
       "facts_box": [], "image": {"url": "https://tifo.elyoxe.com/v1/news/img/n-1.jpg", "w": 1200, "h": 675, "caption": "ك"}, "entities": [],
       "published": "2026-11-19T10:00:00+00:00", "modified": "m1"}


class FakeS3:
    def __init__(self):
        self.puts, self.deleted = {}, []

    def put_object(self, **kw):
        self.puts[kw["Key"]] = kw

    def delete_object(self, **kw):
        self.deleted.append(kw["Key"])


def test_plan_renders_what_changed_everything_after_new_shells_and_deletes_the_withdrawn():
    all_ = [{"id": "n-1", "modified": "a"}, {"id": "n-2", "modified": "b"}]
    seen = {"built": "x", "pages": {"n-1": "a", "n-3": "z"}}
    assert PG.plan(all_, seen, "x") == (["n-2"], ["n-3"])
    assert PG.plan(all_, seen, "y") == (["n-1", "n-2"], ["n-3"])


def fresh(tmp_path):
    st = Store(LocalBackend(tmp_path))
    st.put_state("site/shells.json", {"article": SHELL, "news": SHELL.replace("/news/__ID__/", "/news/"), "built": "b1"})
    st.put_json("news/articles-all.json", {"articles": [{"id": "n-1", "modified": "m1"}]})
    st.put_json("news/articles.json", {"articles": [DOC]})
    st.put_json("news/a/n-1.json", DOC)
    st.put_state("articles/pages.json", {"built": "b1", "pages": {"n-old": "x"}})
    return st


def test_a_run_uploads_with_the_full_builds_headers_deletes_and_remembers(tmp_path):
    st, s3, sent = fresh(tmp_path), FakeS3(), []
    out = PG.run(st, s3, "site-bucket", teams={}, players={}, indexnow=sent.append)
    keys = set(s3.puts)
    assert {"news/n-1/index.html", "news/index.html", "sitemap-news.xml"} <= keys and any(k.startswith("news/a.") for k in keys)
    page = s3.puts["news/n-1/index.html"]
    assert page["ContentType"] == "text/html" and page["CacheControl"] == "public,max-age=60" and b"<title>" in page["Body"]
    css = next(v for k, v in s3.puts.items() if k.endswith(".css"))
    assert css["CacheControl"] == "public,max-age=31536000,immutable" and css["ContentType"] == "text/css"
    assert s3.deleted == ["news/n-old/index.html"]
    assert sent == [["https://tifo.elyoxe.com/news/n-1/"]]
    assert st.get_state("articles/pages.json") == {"built": PG.shell_key(st.get_state("site/shells.json")), "pages": {"n-1": "m1"}}
    assert out["rendered"] == 1 and out["deleted"] == 1


def test_nothing_changed_means_nothing_uploaded(tmp_path):
    st, sent = fresh(tmp_path), []
    PG.run(st, FakeS3(), "site-bucket", teams={}, players={}, indexnow=sent.append)
    s3 = FakeS3()
    assert PG.run(st, s3, "site-bucket", teams={}, players={}, indexnow=sent.append) == {"rendered": 0, "deleted": 0}
    assert s3.puts == {} and len(sent) == 1


def test_an_edit_on_the_desk_rerenders_the_page_but_is_not_new_to_indexnow(tmp_path):
    st, sent = fresh(tmp_path), []
    PG.run(st, FakeS3(), "site-bucket", teams={}, players={}, indexnow=sent.append)
    st.put_json("news/a/n-1.json", dict(DOC, headline="عنوان المحرر", modified="m2"))
    st.put_json("news/articles-all.json", {"articles": [{"id": "n-1", "modified": "m2"}]})
    s3 = FakeS3()
    PG.run(st, s3, "site-bucket", teams={}, players={}, indexnow=sent.append)
    assert "عنوان المحرر".encode() in s3.puts["news/n-1/index.html"]["Body"] and len(sent) == 1


def test_no_shells_yet_waits_for_the_full_build(tmp_path):
    st = Store(LocalBackend(tmp_path))
    assert "skipped" in PG.run(st, FakeS3(), "site-bucket", teams={}, players={})


def test_everything_is_rerendered_only_when_the_pages_would_change():
    """The full build saves its shells every hour; the pages change only with the shells, the stylesheet or the page code."""
    a = {"article": SHELL, "news": SHELL, "built": "10:00"}
    assert PG.shell_key(a) == PG.shell_key(dict(a, built="11:00"))
    assert PG.shell_key(a) != PG.shell_key(dict(a, article=SHELL + " "))
