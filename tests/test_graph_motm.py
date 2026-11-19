import json
from graph.db import Graph
from graph.ids import Registry
from graph.load import motm


def app(mid, pid, tid, rating, goals=0, assists=0, minutes=90, played=1):
    return {"mid": mid, "pid": pid, "tid": tid, "rating": rating, "goals": goals, "assists": assists, "minutes": minutes, "played": played}


def test_the_highest_rating_is_the_man_of_the_match(tmp_path):
    G = Graph(str(tmp_path / "t.db"))
    G.many("appearance", [app(1, 10, 100, 7.9), app(1, 11, 100, 8.6), app(1, 12, 200, 6.1),
                          app(2, 10, 100, 8.0, goals=1), app(2, 13, 200, 8.0), app(2, 14, 200, 9.9, played=0),
                          app(3, 15, 100, None)], "fotmob")
    out = motm.load(G, Registry(), None)
    got = dict(G.c.execute("select mid, pid from match_award where kind='motm'").fetchall())
    assert got == {1: 11, 2: 10}                       # match 2: a tie on 8.0, the scorer wins; a non-player never; match 3: no ratings
    assert G.c.execute("select tid, value, src from match_award where mid=1").fetchone() == (100, "8.6", "fotmob-rating")
    assert out["matches"] == 2


def test_motm_files(tmp_path):
    from graph import publish
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League", "name_ar": "دوري أدنوك للمحترفين"}, "fotmob")
    G.xref("competition", lg, "fotmob", 538, "fotmob-native")
    ain, wahda = reg.mint("team", "fotmob", 102117), reg.mint("team", "fotmob", 102122)
    for t, f in ((ain, 102117), (wahda, 102122)):
        G.xref("team", t, "fotmob", f, "fotmob-native")
    mab = reg.mint("player", "fotmob", 170716)
    G.put("player", {"pid": mab, "name": "Ali Mabkhout", "name_ar": "علي مبخوت"}, "fotmob")
    G.xref("player", mab, "fotmob", 170716, "fotmob-native")
    for i, (season, date) in enumerate((("2024/2025", "2025-03-01"), ("2026/2027", "2026-10-01"), ("2026/2027", "2026-11-01"))):
        e = reg.mint("edition", "fotmob", f"538|{season}")
        G.put("edition", {"eid": e, "cid": lg, "season": season}, "fotmob")
        m = reg.mint("match", "fotmob", 900 + i)
        G.put("match", {"mid": m, "eid": e, "date": date + "T18:00:00Z", "home": ain, "away": wahda, "hs": 2, "as_": 0}, "fotmob")
        G.xref("match", m, "fotmob", 900 + i, "fotmob-native")
        G.c.execute("insert into match_award values(?, 'motm', ?, ?, '8.7', 'fotmob-rating')", (m, mab, ain))
    G.c.commit()
    publish.motm(G, str(tmp_path / "o"), today="2026-11-20")
    ix = json.load(open(tmp_path / "o" / "motm" / "index.json", encoding="utf-8"))
    assert ix["since"] == "2026-07-01" and ix["leaders"]["season"][0] == [170716, "علي مبخوت", 2]
    assert ix["leaders"]["all"][0] == [170716, "علي مبخوت", 3]
    assert ix["comps"]["538"]["all"][0][2] == 3 and ix["clubs"]["102117"]["season"][0][2] == 2
    pl = json.load(open(tmp_path / "o" / "motm" / "players.json", encoding="utf-8"))["170716"]
    assert pl["total"] == 3 and pl["seasons"] == {"2026/2027": 2, "2024/2025": 1} and pl["comps"] == {"538": 3}
    assert pl["opponents"] == {"102122": 3} and pl["recent"][0] == [902, "2026-11-01", "8.7", 102122]
    # phase 6: what the site needs to add the matches played since this build without counting any twice
    assert pl["now"] == 2 and pl["name"] == "علي مبخوت"
    assert ix["today"] == "2026-11-20" and ix["counted"] == [902]          # FotMob ids already counted in the last 21 days
