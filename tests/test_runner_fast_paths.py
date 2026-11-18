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
