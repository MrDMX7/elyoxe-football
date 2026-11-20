"""graph/publish.h2h: every meeting of two teams in every competition the archive holds — the clubs of our league against each
other, and our national teams against every opponent — with the totals, the split by competition, the first meeting and each
side's biggest win."""
import json
from graph.db import Graph
from graph.ids import Registry
from graph import publish


def world(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    comps = {}
    for fid, name, ar in ((538, "Pro League", "دوري أدنوك للمحترفين"), (9943, "President's Cup", "كأس رئيس الدولة"), (290, "Asian Cup", "كأس آسيا")):
        c = reg.mint("competition", "fotmob", fid)
        G.put("competition", {"cid": c, "name": name, "name_ar": ar}, "fotmob")
        G.xref("competition", c, "fotmob", fid, "fotmob-native")
        comps[fid] = c
    teams = {}
    for fid, ar, kind in ((102101, "الجزيرة", "club"), (102117, "العين", "club"), (102111, "الوصل", "club"), (5789, "الإمارات", "national"), (7804, "كوريا الجنوبية", "national")):
        t = reg.mint("team", "fotmob", fid)
        G.put("team", {"tid": t, "name": str(fid), "name_ar": ar, "kind": kind}, "fotmob")
        G.xref("team", t, "fotmob", fid, "fotmob-native")
        teams[fid] = t
    eds = {}
    for fid, season in ((538, "2016/2017"), (9943, "2017/2018"), (290, "2019")):
        e = reg.mint("edition", "fotmob", f"{fid}|{season}")
        G.put("edition", {"eid": e, "cid": comps[fid], "season": season}, "fotmob")
        eds[fid] = e
    n = [0]

    def match(fid, d, h, a, hs, as_):
        n[0] += 1
        m = reg.mint("match", "fotmob", 7000 + n[0])
        G.put("match", {"mid": m, "eid": eds[fid], "date": d + "T15:00:00Z", "home": teams[h], "away": teams[a], "hs": hs, "as_": as_}, "fotmob")
        G.xref("match", m, "fotmob", 7000 + n[0], "fotmob-native")
    match(538, "2016-10-01", 102101, 102117, 2, 1)
    match(538, "2017-03-01", 102117, 102101, 4, 0)
    match(9943, "2018-01-10", 102101, 102117, 1, 1)
    match(538, "2016-11-01", 102101, 102111, 3, 0)          # Al Wasl played our league too
    match(290, "2019-01-10", 5789, 7804, 0, 2)
    G.c.commit()
    return G


def test_the_clubs_meet_in_every_competition(tmp_path):
    G = world(tmp_path)
    out = publish.h2h(G, str(tmp_path / "o"), league=538, nationals=(5789,), min_meetings=1)
    d = json.load(open(tmp_path / "o" / "h2h-all" / "102101-102117.json", encoding="utf-8"))
    assert d["teams"] == ["102101", "102117"] and d["names"] == ["الجزيرة", "العين"]
    assert d["n"] == 3 and d["w"] == [1, 1, 1] and d["goals"] == [3, 6] and d["first"] == "2016-10-01"
    assert d["by_comp"] == [["دوري أدنوك للمحترفين", 2, 1, 0, 1], ["كأس رئيس الدولة", 1, 0, 1, 0]]
    assert d["biggest"] == [["2016-10-01", "2-1", "7001"], ["2017-03-01", "4-0", "7002"]]
    assert d["matches"][0] == ["2018-01-10", "كأس رئيس الدولة", "2017/2018", "102101", 1, 1, "102117", "7003"]     # newest first
    ix = json.load(open(tmp_path / "o" / "h2h-all" / "index.json", encoding="utf-8"))
    assert ix["pairs"] == {"102101-102111": 1, "102101-102117": 3, "5789-7804": 1}
    assert ix["teams"]["102101"] == [["102117", 3, 1, 1, 1], ["102111", 1, 1, 0, 0]]     # opponent, meetings, w, d, l: most first
    assert out == {"pairs": 3}


def test_a_pair_below_the_floor_has_no_file(tmp_path):
    G = world(tmp_path)
    publish.h2h(G, str(tmp_path / "o"), league=538, nationals=(5789,), min_meetings=2)
    ix = json.load(open(tmp_path / "o" / "h2h-all" / "index.json", encoding="utf-8"))
    assert ix["pairs"] == {"102101-102117": 3}


def test_a_competition_fotmob_left_unnamed_reads_as_another_competition(tmp_path):
    G = world(tmp_path)
    G.c.execute("update competition set name='FotMob 0', name_ar=NULL where name='President''s Cup'")
    publish.h2h(G, str(tmp_path / "o"), league=538, nationals=(5789,), min_meetings=1)
    d = json.load(open(tmp_path / "o" / "h2h-all" / "102101-102117.json", encoding="utf-8"))
    assert [b[0] for b in d["by_comp"]] == ["دوري أدنوك للمحترفين", "بطولة ثانية"]
