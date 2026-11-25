"""graph/jleague_fetch.py and graph/load/jleague.py: the J.League's own record. A game we hold takes its attendance and its
shoot-out; a game of the second division is new; a J1 season another source dates a year late is put right."""
import gzip, json
from graph.db import Graph
from graph.ids import Registry
from graph.src import Sources
from graph.load import jleague
from graph.jleague_fetch import parse

PAGE = """<table><tbody>
<tr><td>2018</td><td>Ｊ１</td><td>第１節第１日</td><td>18/02/23(金)</td><td>20:03</td><td>鳥栖</td>
<td><a href="/SFMS02/?match_card_id=21001">1-1</a></td><td>神戸</td><td>ベアスタ</td><td>19,633</td><td>DAZN</td></tr>
<tr><td>2018</td><td>Ｊ１</td><td>第２節第１日</td><td>18/03/02(金)</td><td>19:03</td><td>Ｃ大阪</td>
<td><a href="/SFMS02/?match_card_id=21002">2-2<br />(PK4-3)</a></td><td>横浜FM</td><td>ヤンマー</td><td>23,049</td><td>DAZN</td></tr>
<tr><td>2018</td><td>Ｊ１</td><td>第３節第１日</td><td>18/03/10(土)</td><td>14:03</td><td>鳥栖</td>
<td>中止</td><td>神戸</td><td>ベアスタ</td><td></td><td></td></tr>
</tbody></table>"""


def test_a_page_of_the_record_is_read():
    assert parse(PAGE, 1, 2018) == [[1, 2018, 21001, "2018-02-23", "Sagan Tosu", "Vissel Kobe", 1, 1, None, None, "1", 19633],
                                    [1, 2018, 21002, "2018-03-02", "Cerezo Osaka", "Yokohama F. Marinos", 2, 2, 4, 3, "2", 23049]]


def world(tmp_path, rows):
    d = tmp_path / "db" / ".cache"
    d.mkdir(parents=True)
    with gzip.open(d / "jleague.json.gz", "wt", encoding="utf-8") as z:
        json.dump(rows, z)
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    cid = reg.mint("competition", "fotmob", 223)
    G.put("competition", {"cid": cid, "name": "J. League"}, "fotmob")
    G.xref("competition", cid, "fotmob", 223, "fotmob-native")
    e = {}
    for y in ("2000", "2001", "2002"):
        e[y] = reg.mint("edition", "sch", f"japan|{y}")
        G.put("edition", {"eid": e[y], "cid": cid, "season": y}, "sch")
    t = {}
    for nm in ("Kashima", "Iwata", "Kashiwa"):
        t[nm] = reg.mint("team", "sch", nm)
        G.put("team", {"tid": t[nm], "name": nm}, "sch")
    return G, reg, cid, e, t, Sources(root=str(tmp_path), s3=False)


def games(year, n=6, month=4, away=1):
    """n J1 games of one year between Kashima and Iwata, three days apart, each with its own score"""
    return [[1, year, year * 100 + i, f"{year}-{month:02d}-{1 + 3 * i:02d}", "Kashima Antlers", "Júbilo Iwata", i, away, None, None, str(i + 1), 10000 + i]
            for i in range(n)]


def test_a_game_we_hold_takes_its_attendance_and_shoot_out_and_the_second_division_is_new(tmp_path):
    rows = games(2000)
    rows[5][8:10] = [5, 4]
    rows.append([2, 2000, 900, "2000-05-01", "Mito HollyHock", "Kashima Antlers", 0, 2, None, None, "7", 2500])
    G, reg, cid, e, t, S = world(tmp_path, rows)
    for i in range(6):
        G.put("match", {"mid": 10 + i, "eid": e["2000"], "date": f"2000-04-{1 + 3 * i:02d}", "home": t["Kashima"], "away": t["Iwata"], "hs": i, "as_": 1}, "sch")
    mito = reg.mint("team", "fotmob", 162195)
    G.put("team", {"tid": mito, "name": "Mito Hollyhock"}, "fotmob")
    out = jleague.load(G, reg, S)
    assert out["linked"] == 6 and out["new"] == 1 and out["attendance"] == 6 and out["shootout"] == 1 and out["clubs_own"] == 0
    assert G.c.execute("SELECT attendance, pen_h, pen_a FROM match WHERE mid=15").fetchone() == (10005, 5, 4)
    assert reg.get("team", "jleague", "Kashima Antlers") == t["Kashima"] and reg.get("team", "jleague", "Mito HollyHock") == mito
    new = G.c.execute("""SELECT c.name, e.season, m.home, m.away, m.hs, m.as_, m.round, m.attendance, m.src FROM match m JOIN edition e ON e.eid=m.eid
                         JOIN competition c ON c.cid=e.cid WHERE m.mid NOT BETWEEN 10 AND 15""").fetchall()
    assert new == [("J2 League", "2000", mito, t["Kashima"], 0, 2, "7", 2500, "jleague")]
    assert G.c.execute("SELECT count(*) FROM match").fetchone() == (7,) and G.c.execute("SELECT count(*) FROM team").fetchone() == (4,)
    # a list of winners that starts later does not send the record's own season aside (25 Nov 2026: J2's 1999-2002 had no page)
    j2 = G.c.execute("SELECT cid FROM competition WHERE name='J2 League'").fetchone()[0]
    late = reg.mint("edition", "s365", "148|2003")
    G.put("edition", {"eid": late, "cid": j2, "season": "2003"}, "s365")
    G.c.execute("INSERT INTO honour(eid, kind, rank, tid, src) VALUES(?, 'champion', 1, ?, 's365')", (late, mito))
    from graph.load import seasons
    seasons.load(G, reg, S)
    assert G.c.execute("SELECT e.season FROM match m JOIN edition e ON e.eid=m.eid WHERE e.cid=?", (j2,)).fetchall() == [("2000",)]


def test_a_season_dated_a_year_late_is_dropped_where_we_hold_it_and_moved_where_we_do_not(tmp_path):
    rows = games(2000, 10) + games(2001, 10, month=6, away=2)
    G, reg, cid, e, t, S = world(tmp_path, rows)
    for i in range(10):          # 2000 on its days; 2000 again as «2001»; 2001 as «2002»
        G.put("match", {"mid": 10 + i, "eid": e["2000"], "date": f"2000-04-{1 + 3 * i:02d}", "home": t["Kashima"], "away": t["Iwata"], "hs": i, "as_": 1}, "sch")
        G.put("match", {"mid": 20 + i, "eid": e["2001"], "date": f"2001-04-{1 + 3 * i:02d}", "home": t["Kashima"], "away": t["Iwata"], "hs": i, "as_": 1}, "sch")
        G.put("match", {"mid": 30 + i, "eid": e["2002"], "date": f"2002-06-{1 + 3 * i:02d}", "home": t["Kashima"], "away": t["Iwata"], "hs": i, "as_": 2}, "sch")
    G.put("match", {"mid": 40, "eid": e["2002"], "date": "2002-12-08", "home": t["Iwata"], "away": t["Kashima"], "hs": 0, "as_": 0}, "sch")      # the play-off, not in the record
    out = jleague.load(G, reg, S)
    assert out["late_dropped"] == 10 and out["late_moved"] == 11 and out["linked"] == 20 and out["new"] == 0
    assert G.c.execute("SELECT count(*) FROM match WHERE mid BETWEEN 20 AND 29").fetchone() == (0,)
    assert G.c.execute("SELECT substr(date,1,10), eid, attendance FROM match WHERE mid=31").fetchone() == ("2001-06-04", e["2001"], 10001)
    assert G.c.execute("SELECT substr(date,1,10), eid FROM match WHERE mid=40").fetchone() == ("2001-12-08", e["2001"])
    assert G.c.execute("SELECT count(*) FROM match").fetchone() == (21,)
