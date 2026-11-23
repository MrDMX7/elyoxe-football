"""tools/integrity.py: what each page is, for the counts by kind."""
from tools import integrity as I


def test_page_kinds():
    assert I.kind("/") == "home"
    assert I.kind("/c/premier-league/s/1990-1991/") == "c/*/s"
    assert I.kind("/db/player/123/") == "db/player"
    assert I.kind("/m/k5/") == "m/k" and I.kind("/m/5/") == "m"
    assert I.kind("/coach/k7/") == "coach/k" and I.kind("/coach/500/") == "coach"
    assert I.kind("/awards/x/") == "awards"
