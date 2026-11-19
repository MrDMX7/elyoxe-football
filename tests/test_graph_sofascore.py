import json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import sofascore, motm


def setup(tmp_path, rated=False):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    ain, wahda = reg.mint("team", "fotmob", 102117), reg.mint("team", "fotmob", 102122)
    events = []
    for k in range(6):                                               # six meetings: the clubs link by date+score votes
        d = f"2018-0{k + 1}-1{k}"
        mid = reg.mint("match", "fotmob", 500 + k)
        G.put("match", {"mid": mid, "date": d + "T16:00:00Z", "home": ain, "away": wahda, "hs": k % 3, "as_": 1}, "fotmob")
        omar = reg.mint("player", "fotmob", 1)
        G.put("player", {"pid": omar, "name": "Omar Abdulrahman"}, "fotmob")
        G.many("appearance", [{"mid": mid, "pid": omar, "tid": ain, "played": 1, "rating": 7.5 if rated else None}], "fotmob")
        events.append({"id": 9000 + k, "ts": f"{d}T16:00:00Z", "home": [11, "Al-Ain"], "away": [22, "Al-Wahda"], "hs": k % 3, "as": 1,
                       "potm": {"id": 77, "name": "Omar Abdulrahman", "value": "8.4"}})
    d = tmp_path / "graph" / ".cache" / "sofa"
    d.mkdir(parents=True)
    (d / "971_15000.json").write_text(json.dumps({"ut": 971, "season": 15000, "year": "17/18", "events": events}), encoding="utf-8")
    return G, reg, Sources(str(tmp_path), s3=False), omar


def test_sofascore_pick_for_unrated_matches_links_our_player(tmp_path):
    G, reg, S, omar = setup(tmp_path)
    out = sofascore.load(G, reg, S)
    motm.load(G, reg, S)
    got = G.c.execute("select pid, value, src from match_award where kind='motm'").fetchall()
    assert len(got) == 6 and set(got) == {(omar, "8.4", "sofascore")}
    assert out["picks"] == 6 and out["players_linked"] == 6


def test_fotmob_ratings_win_where_they_exist(tmp_path):
    G, reg, S, omar = setup(tmp_path, rated=True)
    sofascore.load(G, reg, S)
    motm.load(G, reg, S)
    assert {r[0] for r in G.c.execute("select src from match_award")} == {"fotmob-rating"}
