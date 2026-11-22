"""graph/load/transfers.py: Transfermarkt's whole transfer history (salimt/football-datasets transfer_history.csv, 1.1M moves
since the 1980s; dcaribou held 6k of the 2000s) for the players the graph ties to Transfermarkt."""
import csv
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import transfers

HEAD = ["player_id", "season_name", "transfer_date", "from_team_id", "from_team_name", "to_team_id", "to_team_name", "transfer_type",
        "value_at_transfer", "transfer_fee"]


def world(tmp_path, rows):
    d = tmp_path / "db" / ".cache" / "tm"
    d.mkdir(parents=True)
    with open(d / "transfer_history.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEAD)
        w.writerows(rows)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    pid = reg.mint("player", "fotmob", 30981)
    G.put("player", {"pid": pid, "name": "Lionel Messi"}, "fotmob")
    reg.link("player", "tm", "28003", pid)
    barca = reg.mint("team", "fotmob", 8634)
    reg.link("team", "tm", "131", barca)
    return G, reg, pid, barca, Sources(root=str(tmp_path), s3=False)


def test_a_tied_players_moves_from_the_whole_history(tmp_path):
    G, reg, pid, barca, S = world(tmp_path, [
        ["28003", "21/22", "2021-08-10", "131", "Barcelona", "583", "Paris SG", "Transfer", "80000000", "0"],
        ["28003", "04/05", "2004-07-01", "2464", "Barcelona B", "131", "Barcelona", "Transfer", "0", "0"],
        ["28003", "23/24", "2023-07-15", "583", "Paris SG", "69261", "Inter Miami", "Transfer", "35000000", "0"],
        ["9999", "05/06", "2005-07-01", "1", "A", "2", "B", "Transfer", "0", "0"]])           # a man the graph does not tie: left out
    out = transfers.load(G, reg, S)
    rows = G.c.execute("SELECT date, season, from_tid, to_tid, src FROM transfer WHERE pid=? ORDER BY date", (pid,)).fetchall()
    assert [r[0] for r in rows] == ["2004-07-01", "2021-08-10", "2023-07-15"]
    assert rows[0][1] == "2004/2005" and rows[0][3] == barca and rows[1][2] == barca
    assert G.c.execute("SELECT count(*) FROM transfer").fetchone() == (3,)
    assert out["tm_history"] == 3


def test_retirement_and_a_loan_are_said_as_such(tmp_path):
    G, reg, pid, barca, S = world(tmp_path, [
        ["28003", "10/11", "2010-08-01", "131", "Barcelona", "1", "X", "Loan", "0", "0"],
        ["28003", "30/31", "2030-07-01", "131", "Barcelona", "123", "Retired", "Transfer", "0", "0"]])
    transfers.load(G, reg, S)
    got = dict(G.c.execute("SELECT date, coalesce(type,'') || '|' || coalesce(to_tid,'') FROM transfer WHERE pid=?", (pid,)).fetchall())
    assert got["2010-08-01"].startswith("loan|")
    assert got["2030-07-01"] == "retired|"
