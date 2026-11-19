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


def test_vote_teams_links_by_date_and_score(tmp_path):
    from graph.link import vote_teams
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    ain, wahda, jazira = (reg.mint("team", "fotmob", i) for i in (1, 2, 3))
    games = []
    for k in range(6):                       # six FotMob meetings of Al Ain, two with other clubs on the same days
        d = f"2020-0{k + 1}-1{k}"
        G.put("match", {"mid": reg.mint("match", "fotmob", 100 + k), "date": d + "T18:00:00Z", "home": ain, "away": wahda, "hs": k % 3, "as_": 1}, "fotmob")
        other = reg.mint("team", "fotmob", 10 + k)          # a chance match: same day, same score, a different club each day
        G.put("match", {"mid": reg.mint("match", "fotmob", 200 + k), "date": d + "T18:00:00Z", "home": other, "away": reg.mint("team", "fotmob", 50 + k), "hs": k % 3, "as_": 1}, "fotmob")
        games.append((d, "AIN", "WAH", k % 3, 1))
    got = vote_teams(G, reg, "tm", games)
    assert got == {"AIN": ain, "WAH": wahda}
    assert reg.get("team", "tm", "AIN") == ain


def test_vote_teams_needs_five_and_a_lead(tmp_path):
    from graph.link import vote_teams
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    a, b = reg.mint("team", "fotmob", 1), reg.mint("team", "fotmob", 2)
    games = []
    for k in range(4):
        d = f"2021-0{k + 1}-01"
        G.put("match", {"mid": reg.mint("match", "fotmob", k), "date": d, "home": a, "away": b, "hs": 1, "as_": 0}, "fotmob")
        games.append((d, "X", "Y", 1, 0))
    assert vote_teams(G, reg, "tm", games) == {}


def test_vote_teams_merges_a_key_the_source_minted_itself(tmp_path):
    from graph.link import vote_teams
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    ain, wahda = reg.mint("team", "fotmob", 1), reg.mint("team", "fotmob", 2)
    own = reg.mint("team", "tm", "AIN")               # minted earlier in the same loader (a player's season line)
    games = []
    for k in range(6):
        d = f"2020-0{k + 1}-1{k}"
        G.put("match", {"mid": reg.mint("match", "fotmob", 100 + k), "date": d, "home": ain, "away": wahda, "hs": k % 3, "as_": 1}, "fotmob")
        games.append((d, "AIN", "WAH", k % 3, 1))
    got = vote_teams(G, reg, "tm", games)
    assert got["AIN"] == min(ain, own) and reg.resolve("team", own) == reg.get("team", "fotmob", 1)


def test_edition_for_reuses_the_competitions_season(tmp_path):
    from graph.link import edition_for
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    wc = reg.mint("competition", "fotmob", 77)
    e = reg.mint("edition", "s365", "5930|2022")
    G.put("edition", {"eid": e, "cid": wc, "season": "2022"}, "s365")
    assert edition_for(G, reg, "martj42", "FIFA World Cup|2022", wc, "2022") == e
    assert reg.get("edition", "martj42", "FIFA World Cup|2022") == e
    new = edition_for(G, reg, "martj42", "FIFA World Cup|1930", wc, "1930")
    assert new != e and G.c.execute("select cid, season, src from edition where eid=?", (new,)).fetchone() == (wc, "1930", "martj42")
