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
