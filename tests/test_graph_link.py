from collections import Counter
from graph.db import Graph
from graph.ids import Registry
from graph.link import MatchIndex, twin, vote_alias


def g_with_match(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    G.put("match", {"mid": 1, "date": "2020-05-02T19:00:00Z", "home": 10, "away": 20, "hs": 2, "as_": 1}, "fotmob")
    return G


def test_find_one_day_off_and_swapped(tmp_path):
    idx = MatchIndex(g_with_match(tmp_path))
    assert idx.find("2020-05-03", 10, 20) == (1, False)
    assert idx.find("2020-05-02", 20, 10) == (1, True)
    assert idx.find("2020-05-05", 10, 20) == (None, None)


def test_twin_with_other_score_logs_conflict(tmp_path):
    G = g_with_match(tmp_path)
    idx = MatchIndex(G)
    assert twin(G, idx, "2020-05-02", 10, 20, 2, 0, "sch") == 1
    assert G.c.execute("select field, kept, other, other_src from conflict").fetchall() == [("score", "2-1", "2-0", "sch")]
    assert twin(G, idx, "2020-05-02", 20, 10, 1, 2, "sch") == 1          # swapped sides, same score: no new conflict
    assert G.c.execute("select count(*) from conflict").fetchone()[0] == 1


def test_vote_alias_needs_majority():
    reg = Registry()
    a, b = reg.mint("competition", "fotmob", 47), reg.mint("competition", "fotmob", 48)
    got = vote_alias(reg, "competition", {"england": Counter({a: 95, b: 5}), "mixed": Counter({a: 50, b: 50})}, "sch", min_n=20, share=0.9)
    assert got == {"england": a}
    assert reg.get("competition", "sch", "england") == a and reg.get("competition", "sch", "mixed") is None
