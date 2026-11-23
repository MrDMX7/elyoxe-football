"""graph/load/fdata.py: football-data.co.uk's files give the archive's copies of the big five's games their half-time score,
referee and attendance; nothing is minted."""
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import fdata

HEAD = "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,Attendance,Referee\n"


def test_the_copy_of_a_game_takes_its_half_time_referee_and_attendance(tmp_path):
    d = tmp_path / "db" / ".cache" / "fdata"
    d.mkdir(parents=True)
    rows = "".join(f"E0,{12 + i}/08/00,Charlton,Man City,4,0,H,2,0,H,20043,Rob Harris\n" for i in range(3))
    (d / "E0-2000.csv").write_text(HEAD + rows + "E0,30/08/00,Nobody,Man City,1,0,H,1,0,H,,\n", encoding="latin-1")
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    cid = reg.mint("competition", "fotmob", 47)
    G.put("competition", {"cid": cid, "name": "Premier League"}, "fotmob")
    e = reg.mint("edition", "sch", "47|2000/2001")
    G.put("edition", {"eid": e, "cid": cid, "season": "2000/2001"}, "sch")
    t = {}
    for f in (8451, 8456):
        t[f] = reg.mint("team", "fotmob", f)
        G.put("team", {"tid": t[f], "name": str(f)}, "fotmob")
        G.xref("team", t[f], "fotmob", str(f), "fotmob-native")
    for i in range(3):
        G.put("match", {"mid": 10 + i, "eid": e, "date": f"2000-08-{12 + i}", "home": t[8451], "away": t[8456], "hs": 4, "as_": 0}, "sch")
    out = fdata.load(G, reg, Sources(root=str(tmp_path), s3=False))
    assert G.c.execute("SELECT ht_h, ht_a, attendance FROM match WHERE mid=10").fetchone() == (2, 0, 20043)
    assert G.c.execute("SELECT r.name FROM match m JOIN referee r ON r.rid=m.rid WHERE m.mid=10").fetchone() == ("Rob Harris",)
    assert G.c.execute("SELECT count(*) FROM match").fetchone() == (3,) and out["half_time"] == 3 and out["club_unknown"] == 1
