"""graph/load/fotmob_ar.py: FotMob's own Arabic names (api/translationmapping) fill a player, coach or club FotMob knows
and the graph holds in Latin only; never over a name we have, never a full legal name much longer than his known one."""
from graph.db import Graph
from graph.ids import Registry
from graph.load import fotmob_ar


def test_an_empty_arabic_name_is_filled_and_a_held_one_never_overwritten(tmp_path):
    G, reg = Graph(str(tmp_path / "t.db")), Registry()
    for pid, fm, name, ar in ((1, 30981, "Lionel Messi", None), (2, 170716, "Ali Mabkhout", "علي مبخوت"), (3, 999, "Muriqui", None), (4, 5, "Nobody", None)):
        G.put("player", {"pid": pid, "name": name, "name_ar": ar}, "fotmob")
        G.xref("player", pid, "fotmob", fm, "fotmob-native")
    G.put("coach", {"kid": 7, "name": "Paulo Bento"}, "fotmob")
    G.xref("coach", 7, "fotmob", 40000, "fotmob-native")
    G.put("team", {"tid": 8, "name": "Ahli Dubai"}, "fotmob")
    G.xref("team", 8, "fotmob", 102119, "fotmob-native")
    names = {"30981": "ليونيل ميسي", "170716": "علي أحمد مبخوت", "999": "لويز غيليرمي دا كونسيساو سيلفيا", "40000": "باولو بينتو", "102119": "شباب الأهلي"}
    out = fotmob_ar.fill(G, names)
    got = dict(G.c.execute("select pid, name_ar from player"))
    assert got == {1: "ليونيل ميسي", 2: "علي مبخوت", 3: None, 4: None}     # Muriqui's legal name is five words for one: left
    assert G.c.execute("select name_ar from coach").fetchone() == ("باولو بينتو",)
    assert G.c.execute("select name_ar from team").fetchone() == ("شباب الأهلي",)
    assert out == {"player": 1, "coach": 1, "team": 1, "too_long": 1}
