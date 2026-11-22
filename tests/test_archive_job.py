"""tools/archive_job.py: the archive pages go up only where their bytes changed, and their sitemaps hold 45,000 URLs each."""
import os
from tools import archive_job as J


class S3:
    def __init__(self, fail=()):
        self.put, self.fail = [], set(fail)

    def put_object(self, Bucket, Key, Body, ContentType, CacheControl):
        if Key in self.fail:
            raise RuntimeError("slow down")
        self.put.append((Key, ContentType))


def pages(tmp_path, d):
    for k, body in d.items():
        p = tmp_path / k
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")


def test_only_new_and_changed_pages_go_up_and_a_failed_one_is_sent_again_next_run(tmp_path):
    pages(tmp_path, {"m/k1/index.html": "a", "m/k2/index.html": "b", "m/k3/index.html": "c", "_archive_urls.json": "[]", "sitemap-archive.xml": "<x/>"})
    old = {"m/k1/index.html": J.md5(tmp_path / "m/k1/index.html"), "m/k2/index.html": "stale"}
    s3 = S3(fail={"m/k3/index.html"})
    new, sent = J.upload(s3, "b", str(tmp_path), old)
    assert sorted(k for k, _ in s3.put) == ["m/k2/index.html", "sitemap-archive.xml"]
    assert ("sitemap-archive.xml", "application/xml; charset=utf-8") in s3.put
    assert "m/k3/index.html" not in new and "_archive_urls.json" not in new and sent == 2


def test_sitemaps_of_45000_urls_and_their_index(tmp_path):
    urls = [f"/m/k{i}/" for i in range(90001)]
    names = J.sitemaps(str(tmp_path), urls)
    assert names == ["sitemap-archive-1.xml", "sitemap-archive-2.xml", "sitemap-archive-3.xml"]
    idx = (tmp_path / "sitemap-archive.xml").read_text(encoding="utf-8")
    assert idx.count("<loc>") == 3 and "https://tifo.elyoxe.com/sitemap-archive-3.xml" in idx
    assert (tmp_path / "sitemap-archive-3.xml").read_text(encoding="utf-8").count("<loc>") == 1


def test_a_page_whose_only_change_is_the_sites_asset_names_is_not_sent_again(tmp_path):
    # every site deploy renames its hashed assets (app.fccd68cafc.css): 353,513 pages re-sent a run
    pages(tmp_path, {"m/k1/index.html": '<link href="/assets/app.aaaaaaaaaa.css"><main>2-1</main>',
                     "m/k2/index.html": '<link href="/assets/app.aaaaaaaaaa.css"><main>3-0</main>'})
    old_shell, new_shell = '<link href="/assets/app.bbbbbbbbbb.css">', '<link href="/assets/app.aaaaaaaaaa.css">'
    old = {"m/k1/index.html": J.content_md5('<link href="/assets/app.bbbbbbbbbb.css"><main>2-1</main>', J.tokens(old_shell)),
           "m/k2/index.html": J.content_md5('<link href="/assets/app.bbbbbbbbbb.css"><main>1-0</main>', J.tokens(old_shell))}
    s3 = S3()
    new, sent = J.upload(s3, "b", str(tmp_path), old, strip=J.tokens(new_shell))
    assert [k for k, _ in s3.put] == ["m/k2/index.html"]                 # its score changed; k1 only the asset name
    s3 = S3()
    J.upload(s3, "b", str(tmp_path), old, strip=J.tokens(new_shell), full=True)
    assert len(s3.put) == 2                                              # the weekly full refresh sends them all
