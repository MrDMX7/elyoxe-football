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
    for k in ("c/premier-league/s/1990-1991/index.html", "c/laliga/seasons/index.html", "m/k123456/index.html"):
        assert hit(k), k
    for k in ("c/premier-league/index.html", "m/4813470/index.html", "p/k55/index.html", "t/8650/index.html"):
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
    for k in ("index.html", "c/laliga/index.html", "c/laliga/s/1929/index.html", "c/laliga/seasons/index.html", "m/k5/index.html", "m/42/index.html"):
        p = tmp_path / k
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    assert runner.own_pages(tmp_path) == 3
