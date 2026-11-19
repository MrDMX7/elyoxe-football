import json
from graph.ids import Registry
from graph.db import Graph


def test_mint_is_stable_and_per_type():
    r = Registry()
    assert r.mint("team", "fotmob", 8456) == 1
    assert r.mint("team", "fotmob", 9825) == 2
    assert r.mint("player", "fotmob", 8456) == 1
    assert r.mint("team", "fotmob", 8456) == 1


def test_alias_and_refusal():
    r = Registry()
    t = r.mint("team", "fotmob", 1)
    assert r.alias("team", "sch", "Al Ain (UAE)", t) is True
    assert r.get("team", "sch", "Al Ain (UAE)") == t
    u = r.mint("team", "fotmob", 2)
    assert r.alias("team", "sch", "Al Ain (UAE)", u) is False      # already names another entity: never silently merged
    assert r.get("team", "sch", "Al Ain (UAE)") == t


def test_merge_keeps_lower_and_old_ids_resolve():
    r = Registry()
    a, b = r.mint("player", "fotmob", 10), r.mint("player", "tm", "99")
    assert r.merge("player", b, a) == a
    assert r.get("player", "tm", "99") == a
    assert r.resolve("player", b) == a


def test_registry_roundtrip_identical(tmp_path):
    r = Registry()
    for i in (5, 3, 9):
        r.mint("team", "fotmob", i)
    p1, p2 = tmp_path / "a.json.gz", tmp_path / "b.json.gz"
    r.save(p1)
    Registry.load(p1).save(p2)
    assert p1.read_bytes() == p2.read_bytes()


def test_moved_reports_renumbering():
    old = Registry(); old.mint("team", "fotmob", 1); old.mint("team", "fotmob", 2)
    new = Registry(json.loads(json.dumps(old.to_json())))
    assert new.moved(old) == []
    new.map["team|fotmob|2"] = 7
    assert new.moved(old) == ["team|fotmob|2"]


def test_put_precedence_fill_and_conflict(tmp_path):
    g = Graph(str(tmp_path / "t.db"))
    assert g.put("match", {"mid": 1, "hs": 2, "as_": 1, "attendance": None}, "fotmob") is True
    assert g.put("match", {"mid": 1, "hs": 2, "as_": 0, "attendance": 9000}, "sch") is False
    row = g.c.execute("select hs, as_, attendance, src, filled from match where mid=1").fetchone()
    assert row[:4] == (2, 1, 9000, "fotmob")
    assert json.loads(row[4]) == {"attendance": "sch"}
    assert g.c.execute("select field, kept, kept_src, other, other_src from conflict").fetchall() == [("as_", "1", "fotmob", "0", "sch")]


def test_many_ignores_duplicates(tmp_path):
    g = Graph(str(tmp_path / "t.db"))
    rows = [{"mid": 1, "pid": 2, "tid": 3, "played": 1}, {"mid": 1, "pid": 2, "tid": 3, "played": 1}]
    g.many("appearance", rows, "fotmob")
    assert g.c.execute("select count(*) from appearance").fetchone()[0] == 1
