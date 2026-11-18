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


def test_a_league_from_another_source_is_read_not_crashed_on():
    # 2026-11-18 dry run: v1/all/ also carries 365Scores leagues and teams with ids like "365:5635"; is_priority raised ValueError
    day = {"leagues": [{"id": "365:5635", "matches": [{"id": "365:9", "utc": "2026-11-18T10:00:00Z", "status": "finished",
                                                       "home": ["365:1", "أ", 1], "away": ["365:2", "ب", 0]}]},
                       {"id": "365:77", "matches": [{"id": 4242, "utc": "2026-11-18T11:00:00Z", "status": "finished",
                                                     "home": [5789, "الإمارات", 2], "away": ["365:3", "ج", 0]}]}]}
    assert D.finished_priority([day], awarded=set()) == [4242]           # an Arab national team still counts
