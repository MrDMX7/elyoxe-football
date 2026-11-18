"""news/articles/due.py on a recorded all-day file (tests/fixtures/articles/all_20261117.json)."""
import json
from pathlib import Path
from news.articles import due as D, priority as P

DAY = json.loads((Path(__file__).parent / "fixtures" / "articles" / "all_20261117.json").read_text(encoding="utf-8"))


def _matches():
    return [(lg["id"], m) for lg in DAY["leagues"] for m in lg.get("matches") or []]


def test_only_finished_priority_matches_are_due():
    ids = D.finished_priority([DAY], awarded=set())
    assert ids
    by = {m["id"]: (cid, m) for cid, m in _matches()}
    for mid in ids:
        cid, m = by[mid]
        assert m["status"] == "finished"
        assert P.is_priority(cid, m["home"][0], m["away"][0])


def test_awarded_and_postponed_matches_are_never_due():
    ids = D.finished_priority([DAY], awarded=set())
    first = ids[0]
    assert first not in D.finished_priority([DAY], awarded={first})
    post = [m["id"] for _, m in _matches() if m["status"] == "postponed"]
    assert not set(post) & set(D.finished_priority([DAY], awarded=set()))


def test_oldest_first_and_no_duplicates():
    ids = D.finished_priority([DAY, DAY], awarded=set())
    assert len(ids) == len(set(ids))
    utc = {m["id"]: m["utc"] for _, m in _matches()}
    assert [utc[i] for i in ids] == sorted(utc[i] for i in ids)
