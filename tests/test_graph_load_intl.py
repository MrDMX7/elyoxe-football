import json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import martj42, transfers


def test_martj42_links_and_adds(tmp_path):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    (db / "martj42_results.csv").write_text("date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"
                                            "1972-03-17,United Arab Emirates,Qatar,1,0,Friendly,Dubai,United Arab Emirates,FALSE\n"
                                            "2019-01-05,United Arab Emirates,Bahrain,1,1,AFC Asian Cup,Abu Dhabi,United Arab Emirates,FALSE\n", encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    uae, bah = reg.mint("team", "fotmob", 5789), reg.mint("team", "fotmob", 5794)
    G.put("team", {"tid": uae, "name": "United Arab Emirates", "kind": "national"}, "fotmob")
    G.put("team", {"tid": bah, "name": "Bahrain", "kind": "national"}, "fotmob")
    G.put("match", {"mid": reg.mint("match", "fotmob", 1), "date": "2019-01-05T16:00:00Z", "home": uae, "away": bah, "hs": 1, "as_": 1}, "fotmob")
    out = martj42.load(G, reg, Sources(str(tmp_path), s3=False))
    assert out == {"rows": 2, "linked": 1, "new": 1, "teams_linked": 2}
    assert G.c.execute("select count(*) from match where src='martj42'").fetchone()[0] == 1


def test_transfers(tmp_path):
    h = tmp_path / "history" / ".cache"
    h.mkdir(parents=True)
    (h / "transfers.json").write_text(json.dumps({"players": {"5": [["2019-07-01", "19/20", "Al Ain", 10, "Al Hilal", None, 5000000, 9000000]]}}))
    m = tmp_path / "mirror" / "transfers"
    m.mkdir(parents=True)
    (m / "all.json").write_text(json.dumps({"moves": [["2026-11-16", 77, "Omar A", 10, "العين", 2, "Free agent", None, "free", 0, None, "FW"]]}), encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    pid = reg.mint("player", "fotmob", 77)
    reg.alias("player", "tm", "5", pid)
    reg.mint("team", "fotmob", 10)
    out = transfers.load(G, reg, Sources(str(tmp_path), mirror=str(tmp_path / "mirror"), s3=False))
    assert out == {"tm": 1, "fotmob": 1}
    assert G.c.execute("select fee, season from transfer where src='tm'").fetchone() == (5000000, "2019/2020")


def test_martj42_senior_team_wins_over_u23(tmp_path):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    (db / "martj42_results.csv").write_text("date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"
                                            "1990-01-01,Saudi Arabia,Qatar,1,0,Friendly,Riyadh,Saudi Arabia,FALSE\n", encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    u23, senior = reg.mint("team", "fotmob", 1), reg.mint("team", "fotmob", 2)      # the U23 side minted first
    G.put("team", {"tid": u23, "name": "Saudi Arabia U23", "kind": "national"}, "fotmob")
    G.put("team", {"tid": senior, "name": "Saudi Arabia", "kind": "national"}, "fotmob")
    martj42.load(G, reg, Sources(str(tmp_path), s3=False))
    assert reg.get("team", "martj42", "Saudi Arabia") == senior


def test_martj42_competitions_link_by_their_twins(tmp_path):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    wc = reg.mint("competition", "fotmob", 77)
    G.put("competition", {"cid": wc, "name": "World Cup"}, "fotmob")
    e = reg.mint("edition", "fotmob", "77|2026")
    G.put("edition", {"eid": e, "cid": wc, "season": "2026"}, "fotmob")
    lines = ["date,home_team,away_team,home_score,away_score,tournament,city,country,neutral"]
    for k in range(12):
        h, a = reg.mint("team", "fotmob", 100 + 2 * k), reg.mint("team", "fotmob", 101 + 2 * k)
        G.put("team", {"tid": h, "name": f"H{k}", "kind": "national"}, "fotmob")
        G.put("team", {"tid": a, "name": f"A{k}", "kind": "national"}, "fotmob")
        d = f"2026-06-{11 + k}"
        G.put("match", {"mid": reg.mint("match", "fotmob", k), "eid": e, "date": d + "T19:00:00Z", "home": h, "away": a, "hs": 1, "as_": 0}, "fotmob")
        lines.append(f"{d},H{k},A{k},1,0,FIFA World Cup,X,Y,TRUE")
    (db / "martj42_results.csv").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    martj42.load(G, reg, Sources(str(tmp_path), s3=False))
    assert reg.get("competition", "martj42", "FIFA World Cup") == wc
    assert reg.get("edition", "martj42", "FIFA World Cup|2026") == e


def test_martj42_major_tournaments_by_the_curated_map(tmp_path):
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    (db / "martj42_results.csv").write_text("date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"
                                            "1996-12-04,United Arab Emirates,Kuwait,1,0,AFC Asian Cup,Abu Dhabi,United Arab Emirates,FALSE\n", encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    ac = reg.mint("competition", "fotmob", 290)
    G.put("competition", {"cid": ac, "name": "Asian Cup"}, "fotmob")
    martj42.load(G, reg, Sources(str(tmp_path), s3=False))
    assert reg.get("competition", "martj42", "AFC Asian Cup") == ac
    assert G.c.execute("select e.cid from match m join edition e on e.eid=m.eid where m.src='martj42'").fetchone()[0] == ac


def test_a_curated_tournament_carries_fotmobs_id_in_xref_even_when_another_source_minted_it(tmp_path):
    # the Asian Cup: 365Scores' record (6196) came first and the registry ties FotMob's 290 to it, but no FotMob loader writes
    # 290 to xref (FotMob gave us none of its matches), so publish.matches, which reads xref, never saw the Asian Cup
    db = tmp_path / "db" / ".cache"
    db.mkdir(parents=True)
    (db / "martj42_results.csv").write_text("date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"
                                            "1996-12-04,United Arab Emirates,Kuwait,1,0,AFC Asian Cup,Abu Dhabi,United Arab Emirates,FALSE\n", encoding="utf-8")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    ac = reg.mint("competition", "s365", "6196")
    reg.link("competition", "fotmob", 290, ac)
    G.put("competition", {"cid": ac, "name": "Asian Cup"}, "s365")
    martj42.load(G, reg, Sources(str(tmp_path), s3=False))
    assert G.c.execute("select tifo_id from xref where type='competition' and source='fotmob' and source_id='290'").fetchone() == (ac,)
