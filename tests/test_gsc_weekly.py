"""tools/gsc_weekly.py: Search Console rows grouped by article type (the id prefix after /news/)."""
from tools import gsc_weekly as G


def test_rows_are_grouped_by_the_article_type():
    rows = [{"keys": ["https://tifo.elyoxe.com/news/r-1/"], "clicks": 3, "impressions": 40},
            {"keys": ["https://tifo.elyoxe.com/news/r-2/"], "clicks": 1, "impressions": 10},
            {"keys": ["https://tifo.elyoxe.com/news/fpl-12/"], "clicks": 0, "impressions": 5},
            {"keys": ["https://tifo.elyoxe.com/m/9/"], "clicks": 9, "impressions": 90}]
    got = G.by_type(rows)
    assert got == {"report": {"clicks": 4, "impressions": 50, "pages": 2}, "fantasy": {"clicks": 0, "impressions": 5, "pages": 1}}
