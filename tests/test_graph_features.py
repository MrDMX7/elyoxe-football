"""graph/features_export.versus: what one pass over every match gives the archive's /vs/ and /elo/ pages."""
import json

from graph.db import Graph
from graph.ids import Registry
from graph import features_export as F


def world(tmp_path, games):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    a, b = (reg.mint("team", "x", n) for n in ("a", "b"))
    G.put("team", {"tid": a, "name": "Alpha", "name_ar": "ألفا", "kind": "club"}, "fotmob")
    G.put("team", {"tid": b, "name": "Beta", "kind": "club"}, "fotmob")
    for i, (day, h, hs, as_) in enumerate(games):
        G.put("match", {"mid": reg.mint("match", "x", i), "date": day, "home": a if h else b, "away": b if h else a, "hs": hs, "as_": as_}, "fotmob")
    G.c.commit()
    return G, a, b


def read(tmp_path, *p):
    return json.loads((tmp_path / "out").joinpath(*p).read_text(encoding="utf-8"))


def test_a_pair_keeps_every_meeting_oldest_first_and_one_a_day(tmp_path):
    G, a, b = world(tmp_path, [("2001-05-01", 1, 2, 0), ("2000-05-01", 0, 1, 1), ("2001-05-01T18:00", 1, 2, 0)])
    r = F.versus(G, str(tmp_path / "out"), min_team=1)
    lo, hi = sorted((a, b))
    ms = read(tmp_path, "vs", "pairs", f"{lo % F.SHARDS}.json")[f"{lo}-{hi}"]
    assert [m[0] for m in ms] == ["2000-05-01", "2001-05-01"]
    assert ms[1][3] == (1 if a == lo else 0) and ms[1][4:6] == [2, 0]
    assert r["pairs"] == 1 and read(tmp_path, "vs", "index.json")["pairs"] == {f"{lo}-{hi}": 2}
    assert read(tmp_path, "vs", "names.json")[str(a)][0] == "ألفا"


def test_a_team_gets_its_totals_its_record_against_each_opponent_and_its_longest_runs(tmp_path):
    G, a, b = world(tmp_path, [(f"200{i}-05-01", i % 2, 1, 0) if i < 4 else ("2004-05-01", 1, 0, 3) for i in range(5)])
    F.versus(G, str(tmp_path / "out"), min_team=5)
    t = read(tmp_path, "vs", "teams", f"{a % F.SHARDS}.json")[str(a)]
    # Alpha at home in the odd years (won 1-0 twice), away in the even ones (lost 1-0 twice), then lost 0-3 at home
    assert t["tot"] == [5, 2, 0, 3, 2, 5]
    assert t["opp"] == [[b, 5, 2, 0, 3, 2, 5]]
    assert t["first"] == "2000-05-01" and t["last"] == "2004-05-01"
    assert "win" not in t["run"] and t["elo"]["now"] < 1500


def test_a_pair_that_met_once_gets_no_file(tmp_path):
    G, a, b = world(tmp_path, [("2000-05-01", 1, 1, 0)])
    assert F.versus(G, str(tmp_path / "out"))["pairs"] == 0


def test_the_winner_takes_what_the_loser_gives_and_a_big_win_counts_more():
    assert F.gd_weight(1) == 1.0 and F.gd_weight(-2) == 1.5 and F.gd_weight(4) == 15 / 8
    assert F.weight("FIFA World Cup", "cup", "world", True) == (60, 0)
    assert F.weight("World Cup Qualification UEFA", "cup", "continental", True) == (40, 100)
    assert F.weight("Premier League", "league", "domestic", False) == (20, 60)
