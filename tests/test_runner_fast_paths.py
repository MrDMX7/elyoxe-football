"""The hourly site publish leaves alone what the fast «Article pages» step owns (spec 2026-11-19 §7): its `--delete` would
otherwise take down a page written while the build was running, for up to an hour."""
import fnmatch
from tools import runner


def test_the_full_build_leaves_the_fast_steps_pages_alone():
    ex = runner.page_excludes()
    hit = lambda k: any(fnmatch.fnmatchcase(k, p) for p in ex)
    for k in ("news/n-de85c6123d92cc/index.html", "news/r-6622721/index.html", "news/index.html", "news/a.0123456789.css",
              "sitemap-news.xml", "_shells/article.html"):
        assert hit(k), k
    for k in ("news/press/index.html", "about/index.html", "index.html", "m/1/index.html"):
        assert not hit(k), k
    assert "assets/*" in ex and "m/*/g/*" in ex                                    # what it excluded before stays excluded


def test_the_hourly_publish_leaves_the_archive_jobs_pages_alone():
    # docs/superpowers/specs/2026-11-22-tifo-archive-static-design.md: the archive job owns every season page, every season
    # list and every archive match; the site's --delete must never take them
    ex = runner.page_excludes()
    hit = lambda k: any(fnmatch.fnmatchcase(k, p) for p in ex)
    for k in ("c/premier-league/s/1990-1991/index.html", "c/laliga/seasons/index.html", "m/k123456/index.html", "p/k55/index.html"):
        assert hit(k), k
    for k in ("c/premier-league/index.html", "m/4813470/index.html", "p/30981/index.html", "t/8650/index.html"):
        assert not hit(k), k


def test_the_listing_never_reads_the_archive_matches():
    from tools import s3push

    class Fake:
        def __init__(self):
            self.prefixes = []

        def get_paginator(self, _):
            fake = self

            class P:
                def paginate(self, Bucket, Prefix="", Delimiter=None):
                    fake.prefixes.append((Prefix, Delimiter))
                    keys = ["index.html", "m/1/index.html", "m/k1/index.html", "c/x/index.html"]
                    if Delimiter:
                        yield {"Contents": [{"Key": k} for k in keys if "/" not in k], "CommonPrefixes": [{"Prefix": "m/"}, {"Prefix": "c/"}]}
                    else:
                        yield {"Contents": [{"Key": k} for k in keys if k.startswith(Prefix)]}
            return P()
    f = Fake()
    got = [o["Key"] for o in s3push.listing(f, "b")]
    assert sorted(got) == ["c/x/index.html", "index.html", "m/1/index.html"]
    assert ("m/k", None) not in f.prefixes and ("m/", None) not in f.prefixes


def test_the_page_count_guard_counts_the_sites_own_pages_only(tmp_path):
    # 22 Nov 2026: the archive's season and old-match pages are the archive job's; the site's «partial build» guard counted
    # them and refused two builds (127,609 vs 147,047) when the seasons merge left fewer of them
    for k in ("index.html", "c/laliga/index.html", "c/laliga/s/1929/index.html", "c/laliga/seasons/index.html", "m/k5/index.html", "m/42/index.html",
              "p/k9/index.html"):
        p = tmp_path / k
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    assert runner.own_pages(tmp_path) == 3


def test_held_deletes_are_not_handed_to_a_sync_that_deletes(tmp_path, monkeypatch):
    # 23 Nov 2026: s3push held 14,801 deletes (over 10 %) and returned ok=False, so the runner fell back to `s3fast sync
    # --delete`, which has no guard, and took 35,296 archive profiles (an old build without the p/k* exclude, listing the
    # bucket while the archive job was uploading them). The guard holds the deletes for every path: the uploads went up, the
    # publish is ok, nothing is deleted.
    import boto3
    from tools import s3push
    (tmp_path / "index.html").write_text("x")
    deleted = []

    class Fake:
        def get_paginator(self, _):
            class P:
                def paginate(self, Bucket, Prefix="", Delimiter=None):
                    keys = ["index.html"] + [f"p/{i}/index.html" for i in range(50)]
                    yield {"Contents": [{"Key": k, "Size": 1, "LastModified": __import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc),
                                         "ETag": '"x"'} for k in keys if k.startswith(Prefix) and (not Delimiter or "/" not in k[len(Prefix):])],
                           "CommonPrefixes": [{"Prefix": "p/"}] if Delimiter else []}
            return P()

        def put_object(self, **kw):
            pass

        def delete_objects(self, **kw):
            deleted.append(kw)
            return {}
    monkeypatch.setattr(boto3, "client", lambda *a, **k: Fake())
    ok, note = s3push.push(str(tmp_path), "b", "r", say=lambda *_: None)
    assert deleted == []
    assert ok, note
    assert "held" in note


def test_the_fallback_sync_uploads_and_never_deletes():
    # the fallback runs when s3push failed (uploads, listing); its `--delete` has no 10 % guard, so it only uploads and the
    # next hour's s3push does the deletes
    args = ["s3", "sync", "out", "s3://b", "--delete", "--exclude", "p/k*"]
    assert runner.fallback_args(args) == ["s3", "sync", "out", "s3://b", "--exclude", "p/k*"]
