import json
from graph.db import Graph
from graph.ids import Registry
from graph import publish


def graph(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    bd = reg.mint("competition", "wiki", "Ballon d'Or")
    G.put("competition", {"cid": bd, "name": "Ballon d'Or", "name_ar": "الكرة الذهبية", "kind": "award"}, "wikidata")
    messi = reg.mint("player", "fotmob", 30981)
    G.put("player", {"pid": messi, "name": "Lionel Messi", "name_ar": "ليونيل ميسي"}, "fotmob")
    G.xref("player", messi, "fotmob", 30981, "fotmob-native")
    old = reg.mint("player", "wikidata", "Q1")
    G.put("player", {"pid": old, "name": "Stanley Matthews"}, "wikidata")
    for y, podium in (("1956", [old]), ("2009", [messi]), ("2010", [messi]), ("2011", [messi])):
        e = reg.mint("edition", "wiki", f"bd|{y}")
        G.put("edition", {"eid": e, "cid": bd, "season": y}, "wiki")
        for r, p in enumerate(podium, 1):
            G.c.execute("insert into honour(eid, kind, rank, pid, value, src) values(?, 'winner', ?, ?, '47', 'wiki')", (e, r, p))
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League", "name_ar": "دوري أدنوك للمحترفين"}, "fotmob")
    G.xref("competition", lg, "fotmob", 538, "fotmob-native")
    e = reg.mint("edition", "fotmob", "538|2012/2013")
    G.put("edition", {"eid": e, "cid": lg, "season": "2012/2013"}, "fotmob")
    G.c.execute("insert into honour(eid, kind, rank, pid, value, src) values(?, 'top_scorer', 1, ?, '23', 'scorers')", (e, messi))
    G.c.commit()
    return G, messi


def test_award_files(tmp_path):
    G, messi = graph(tmp_path)
    out = publish.awards(G, str(tmp_path / "o"))
    ix = json.load(open(tmp_path / "o" / "awards" / "index.json", encoding="utf-8"))
    a = next(x for x in ix["awards"] if x["key"] == "ballon-dor")
    assert (a["name_ar"], a["years"], a["first"], a["last"], a["group"]) == ("الكرة الذهبية", 4, "1956", "2011", "world")
    assert a["top"] == ["ليونيل ميسي", 3, 30981]
    d = json.load(open(tmp_path / "o" / "awards" / "ballon-dor.json", encoding="utf-8"))
    assert d["years"][0]["season"] == "2011" and d["years"][0]["podium"][0]["fotmob"] == 30981
    assert d["years"][-1]["podium"][0] == {"rank": 1, "name": "Stanley Matthews", "name_ar": None, "fotmob": None, "team": None, "value": "47"}
    assert d["most"][0] == ["ليونيل ميسي", 3, 30981]
    pl = json.load(open(tmp_path / "o" / "awards" / "players.json", encoding="utf-8"))
    assert ["ballon-dor", "2011", "winner", 1, None] in pl["30981"]                  # an award: its key
    assert [None, "2012/2013", "top_scorer", 1, 538] in pl["30981"]                   # an edition honour: the FotMob competition
    assert out["awards"] == 1


def test_a_missing_fotmob_id_does_not_break_publishing(tmp_path):
    G, messi = graph(tmp_path)
    G.xref("competition", 999, "fotmob", None, "fotmob-native")          # the archive has matches with no competition
    G.xref("player", 998, "fotmob", None, "fotmob-native")
    assert publish.awards(G, str(tmp_path / "o"))["awards"] == 1


def test_club_awards_have_their_own_group():
    assert publish.group("Arsenal F.C. Player of the Season") == "club"
    assert publish.group("Chelsea F.C. Player of the Season award recipients") == "club"
    assert publish.group("Ballon d'Or") == "world"
    assert publish.group("FWA Footballer of the Year") == "country"


def test_edition_files_for_season_pages(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League", "name_ar": "دوري أدنوك للمحترفين"}, "fotmob")
    G.xref("competition", lg, "fotmob", 538, "fotmob-native")
    ain, jaz = reg.mint("team", "fotmob", 102117), reg.mint("team", "fotmob", 102101)
    for t, f, ar in ((ain, 102117, "العين"), (jaz, 102101, "الجزيرة")):
        G.put("team", {"tid": t, "name": str(f), "name_ar": ar}, "fotmob")
        G.xref("team", t, "fotmob", f, "fotmob-native")
    mab = reg.mint("player", "fotmob", 170716)
    G.put("player", {"pid": mab, "name": "Ali Mabkhout", "name_ar": "علي مبخوت"}, "fotmob")
    G.xref("player", mab, "fotmob", 170716, "fotmob-native")
    e = reg.mint("edition", "fotmob", "538|2016/2017")
    G.put("edition", {"eid": e, "cid": lg, "season": "2016/2017"}, "fotmob")
    G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'champion', 1, ?, 's365')", (e, jaz))
    G.c.execute("insert into honour(eid, kind, rank, tid, src) values(?, 'runner_up', 1, ?, 'table')", (e, ain))
    G.c.execute("insert into honour(eid, kind, rank, pid, value, src) values(?, 'top_scorer', 1, ?, '33', 'tifo')", (e, mab))
    G.c.execute("insert into standing values(?, '', 1, ?, 26, 22, 2, 2, 70, 20, 68, 's365')", (e, jaz))
    m = reg.mint("match", "fotmob", 1)
    G.put("match", {"mid": m, "eid": e, "date": "2017-01-01", "home": jaz, "away": ain, "hs": 2, "as_": 0}, "fotmob")
    G.c.execute("insert into match_award values(?, 'motm', ?, ?, '9.1', 'fotmob-rating')", (m, mab, jaz))
    k = reg.mint("coach", "fotmob", 150526)
    G.put("coach", {"kid": k, "name": "Henk ten Cate"}, "fotmob")
    G.c.execute("insert into match_coach values(?, 'h', ?, 'fotmob')", (m, k))
    G.c.commit()
    out = publish.editions(G, str(tmp_path / "o"))
    d = json.load(open(tmp_path / "o" / "editions" / "538.json", encoding="utf-8"))
    s = d["seasons"][0]
    assert (s["season"], s["champion"]["fotmob"], s["champion"]["name"], s["runner_up"]["name"]) == ("2016/2017", 102101, "الجزيرة", "العين")
    assert s["top_scorers"][0] == {"rank": 1, "fotmob": 170716, "name": "علي مبخوت", "value": "33"}
    assert s["table"][0][:3] == [1, 102101, "الجزيرة"] and s["motm"][0] == [170716, "علي مبخوت", 1]
    assert s["champion_coach"] == {"kid": k, "name": "Henk ten Cate"} and s["matches"] == 1
    assert out["competitions"] == 1
