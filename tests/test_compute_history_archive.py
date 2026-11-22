"""compute/history.with_archive: the pre-match facts read the league's every season the archive holds (v1/league-history/*,
graph/publish.league_history), not FotMob's since 2010/11 only («Liverpool on a Sunday… since 2010/2011», 22 Nov 2026)."""
from compute import history as HI
from compute import facts as FA


def test_the_archive_adds_the_seasons_fotmob_does_not_hold():
    fotmob = [{"id": 1, "ko": "2011-01-02T16:00:00Z", "comp": 47, "season": "2010/2011", "round": "1", "h": 8650, "a": 10260, "hs": 1, "as": 0, "st": "finished"}]
    older = {"comp": 47, "seasons": {"1895/1896": [["1895-10-12T12:00:00Z", 8650, 10260, 2, 2], ["1895-11-02T12:00:00Z", "k77", 8650, 0, 1]],
                                     "2010/2011": [["2011-01-02T16:00:00Z", 8650, 10260, 1, 0]]}}
    rows = HI.with_archive(fotmob, older)
    assert [(r["season"], r["h"], r["a"]) for r in rows] == [("1895/1896", 8650, 10260), ("1895/1896", "k77", 8650), ("2010/2011", 8650, 10260)]
    assert HI.with_archive(fotmob, None) == fotmob


def test_the_facts_say_since_the_first_season_held():
    rows = HI.with_archive([], {"seasons": {"1888/1889": [[f"1888-{9 + i // 28:02d}-{1 + i % 28:02d}T15:00:00Z", 8650, 2, 1, 0] for i in range(40)]}})
    m = {"home": {"id": 8650, "name": "Liverpool"}, "away": {"id": 10260, "name": "Man Utd"}, "kickoff_utc": "2026-11-22T16:30:00Z"}
    txt = " ".join(f["text_ar"] for f in FA.match_facts(rows, m, {}, "1888/1889"))
    assert "منذ 1888/1889" in txt and "FotMob" not in txt
