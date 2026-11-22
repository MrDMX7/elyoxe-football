"""graph/publish.matches: the archive's match pages' data — every match of the chosen competitions (season by season) and of
the chosen national teams, with its score, scorers, cards, lineups and coaches where the archive has them."""
import json
from graph.db import Graph
from graph.ids import Registry
from graph import publish


def world(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    lg = reg.mint("competition", "fotmob", 538)
    G.put("competition", {"cid": lg, "name": "Pro League", "name_ar": "دوري أدنوك للمحترفين"}, "fotmob")
    G.xref("competition", lg, "fotmob", 538, "fotmob-native")
    e = reg.mint("edition", "fotmob", "538|2016/2017")
    G.put("edition", {"eid": e, "cid": lg, "season": "2016/2017"}, "fotmob")
    ain, jaz, uae, kor = (reg.mint("team", "fotmob", f) for f in (102117, 102101, 5789, 7804))
    for t, f, ar in ((ain, 102117, "العين"), (jaz, 102101, "الجزيرة"), (uae, 5789, "الإمارات"), (kor, 7804, "كوريا الجنوبية")):
        G.put("team", {"tid": t, "name": str(f), "name_ar": ar, "kind": "national" if f in (5789, 7804) else "club"}, "fotmob")
        G.xref("team", t, "fotmob", f, "fotmob-native")
    mab = reg.mint("player", "fotmob", 170716)
    G.put("player", {"pid": mab, "name": "Ali Mabkhout", "name_ar": "علي مبخوت"}, "fotmob")
    G.xref("player", mab, "fotmob", 170716, "fotmob-native")
    old = reg.mint("player", "martj42", "Adnan")
    G.put("player", {"pid": old, "name": "Adnan Al Talyani", "name_ar": "عدنان الطلياني"}, "martj42")
    m1 = reg.mint("match", "fotmob", 2600001)
    G.put("match", {"mid": m1, "eid": e, "round": "5", "date": "2016-10-01T15:00:00Z", "home": jaz, "away": ain, "hs": 2, "as_": 1, "status": "finished"}, "fotmob")
    G.xref("match", m1, "fotmob", 2600001, "fotmob-native")
    G.many("event", [{"mid": m1, "seq": 0, "minute": 23, "type": "goal", "side": "h", "tid": jaz, "pid": mab},
                     {"mid": m1, "seq": 1, "minute": 70, "type": "yellow", "side": "a", "tid": ain, "pid": None}], "fotmob")
    G.many("appearance", [{"mid": m1, "pid": mab, "tid": jaz, "played": 1, "started": 1, "shirt": "7"}], "fotmob")
    k = reg.mint("coach", "fotmob", 5)
    G.put("coach", {"kid": k, "name": "Henk ten Cate"}, "fotmob")
    G.c.execute("insert into match_coach values(?, 'h', ?, 'fotmob')", (m1, k))
    m2 = reg.mint("match", "martj42", "1990-06-09|UAE")
    G.put("match", {"mid": m2, "date": "1990-06-09", "home": kor, "away": uae, "hs": 0, "as_": 2, "pen_h": None, "status": "finished"}, "martj42")
    G.many("event", [{"mid": m2, "seq": 0, "minute": 40, "type": "goal", "side": "a", "tid": uae, "pid": old}], "martj42")
    G.c.commit()
    return G, m2, old



def plain(f):
    """a match file without the Tifo ids the archive job reads (k, the clubs' third field, the men's last)"""
    out = []
    for m in f["matches"]:
        m = {k: v for k, v in m.items() if k != "k"}
        m["h"], m["a"] = m["h"][:2], m["a"][:2]
        if "ev" in m:
            m["ev"] = [e[:6] for e in m["ev"]]
        if "lu" in m:
            m["lu"] = {k: [p[:4] for p in v] for k, v in m["lu"].items()}
        out.append(m)
    return dict(f, matches=out)

def test_season_files_and_the_national_teams_file(tmp_path):
    G, m2, old = world(tmp_path)
    out = publish.matches(G, str(tmp_path / "o"), comps=(538,), teams=(5789,))
    d = tmp_path / "o" / "matches"
    s = json.load(open(d / "538" / "2016-2017.json", encoding="utf-8"))
    m0 = s["matches"][0]
    assert isinstance(m0["k"], int) and isinstance(m0["h"][2], int) and isinstance(m0["ev"][0][6], int) and isinstance(m0["lu"]["h"][0][4], int)
    s = plain(s)                                   # the archive's Tifo ids apart (graph/archive_export, the site's own reading unchanged)
    assert s == {"comp": 538, "season": "2016/2017", "matches": [{
        "id": "2600001", "date": "2016-10-01", "comp": 538, "season": "2016/2017", "round": "5",
        "h": [102101, "الجزيرة"], "a": [102117, "العين"], "s": [2, 1],
        "ev": [[23, 0, "goal", "h", "علي مبخوت", "170716"], [70, 0, "yellow", "a", None, None]],
        "lu": {"h": [["علي مبخوت", "170716", "7", 1]]}, "co": {"h": "Henk ten Cate"}}]}
    t = json.load(open(d / "team-5789.json", encoding="utf-8"))
    assert t["matches"][0]["id"] == f"k{m2}" and plain(t)["matches"][0]["ev"] == [[40, 0, "goal", "a", "عدنان الطلياني", f"k{old}"]]
    ix = json.load(open(d / "index.json", encoding="utf-8"))
    assert ix == {"comps": {"538": ["2016-2017"]}, "teams": {"5789": 1}}
    assert out == {"matches": 2}


def test_one_match_twice_from_two_sources_is_written_once_with_the_more_detailed_record(tmp_path):
    G, m2, old = world(tmp_path)
    from graph.ids import Registry
    uae = G.c.execute("select tifo_id from xref where type='team' and source='fotmob' and source_id='5789'").fetchone()[0]
    wg, de = 900, 901
    G.put("team", {"tid": wg, "name": "West Germany", "kind": "national"}, "fjelstul")
    G.put("team", {"tid": de, "name": "Germany", "name_ar": "ألمانيا", "kind": "national"}, "martj42")
    G.put("match", {"mid": 950, "date": "1990-06-15", "home": wg, "away": uae, "hs": 5, "as_": 1}, "fjelstul")
    G.many("event", [{"mid": 950, "seq": 0, "minute": 46, "type": "goal", "side": "a", "tid": uae, "pid": old}], "fjelstul")
    G.put("match", {"mid": 951, "date": "1990-06-15", "home": de, "away": uae, "hs": 5, "as_": 1}, "martj42")
    G.c.commit()
    publish.matches(G, str(tmp_path / "o"), comps=(), teams=(5789,))
    t = json.load(open(tmp_path / "o" / "matches" / "team-5789.json", encoding="utf-8"))["matches"]
    assert [m["id"] for m in t if m["date"] == "1990-06-15"] == ["k950"]          # the record with the goal stays


def test_a_match_before_a_clubs_merger_uses_the_name_it_had(tmp_path):
    G, m2, old = world(tmp_path)
    publish.matches(G, str(tmp_path / "o"), comps=(538,), teams=(), eras={102101: [["2017-07-01", "الجزيرة القديمة"]]})
    s = json.load(open(tmp_path / "o" / "matches" / "538" / "2016-2017.json", encoding="utf-8"))
    assert s["matches"][0]["h"][:2] == [102101, "الجزيرة القديمة"]


def test_by_default_every_arab_top_league_in_the_archive_is_published(tmp_path):
    G, m2, old = world(tmp_path)
    sa, e = 9536, 9537                                            # RSSSF's Saudi league, 1980/81
    G.put("competition", {"cid": sa, "name": "Saudi Pro League"}, "fotmob")
    G.xref("competition", sa, "fotmob", 536, "fotmob-native")
    G.put("edition", {"eid": e, "cid": sa, "season": "1980/1981"}, "rsssf")
    tid = lambda f: G.c.execute("select tifo_id from xref where type='team' and source='fotmob' and source_id=?", (str(f),)).fetchone()[0]
    G.put("match", {"mid": 960, "eid": e, "date": "1981-01-02", "home": tid(102117), "away": tid(102101), "hs": 1, "as_": 0}, "rsssf")
    G.c.commit()
    assert {536, 538} <= set(publish.ARAB_LEAGUES)
    publish.matches(G, str(tmp_path / "o"))
    ix = json.load(open(tmp_path / "o" / "matches" / "index.json", encoding="utf-8"))
    assert ix == {"comps": {"538": ["2016-2017"], "536": ["1980-1981"]}, "teams": {"5789": 1}}
    s = json.load(open(tmp_path / "o" / "matches" / "536" / "1980-1981.json", encoding="utf-8"))
    assert [m["id"] for m in s["matches"]] == ["k960"] and s["matches"][0]["comp"] == 536


def test_a_match_carries_its_man_of_the_match(tmp_path):
    G, m2, old = world(tmp_path)
    G.c.execute("insert into match_award values(?, 'motm', ?, NULL, NULL, 'official')", (m2, old))
    G.c.commit()
    publish.matches(G, str(tmp_path / "o"), comps=(538,), teams=(5789,))
    t = json.load(open(tmp_path / "o" / "matches" / "team-5789.json", encoding="utf-8"))
    assert t["matches"][0]["motm"] == ["عدنان الطلياني", f"k{old}"]


def test_by_default_the_big_tournaments_are_published_too(tmp_path):
    G, m2, old = world(tmp_path)
    wc, e = 9600, 9601
    G.put("competition", {"cid": wc, "name": "World Cup"}, "fotmob")
    G.xref("competition", wc, "fotmob", 77, "fotmob-native")
    G.put("edition", {"eid": e, "cid": wc, "season": "2002"}, "fjelstul")
    tid = lambda f: G.c.execute("select tifo_id from xref where type='team' and source='fotmob' and source_id=?", (str(f),)).fetchone()[0]
    G.put("match", {"mid": 961, "eid": e, "date": "2002-06-03", "home": tid(5789), "away": tid(7804), "hs": 2, "as_": 1}, "fjelstul")
    G.c.commit()
    assert {77, 50, 290, 289, 44, 78, 10242, 329} <= set(publish.TOURNAMENTS)
    publish.matches(G, str(tmp_path / "o"))
    ix = json.load(open(tmp_path / "o" / "matches" / "index.json", encoding="utf-8"))
    assert ix["comps"]["77"] == ["2002"]
