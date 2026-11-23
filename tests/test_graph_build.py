import gzip, json, os
from graph import build
from graph.src import Sources
from test_graph_rows import REC


def caches(tmp_path):
    mx = tmp_path / "db" / ".cache" / "fm" / "mx"
    mx.mkdir(parents=True)
    (mx / "900.json").write_bytes(gzip.compress(json.dumps(REC).encode()))
    return Sources(str(tmp_path), mirror=str(tmp_path / "mirror"), s3=False)


def test_build_twice_same_ids(tmp_path):
    S = caches(tmp_path)
    r1 = build.run(S, str(tmp_path / "o1"), str(tmp_path / "reg.json.gz"), fetch=False)
    b1 = (tmp_path / "reg.json.gz").read_bytes()
    r2 = build.run(S, str(tmp_path / "o2"), str(tmp_path / "reg.json.gz"), fetch=False)
    assert (tmp_path / "reg.json.gz").read_bytes() == b1
    assert r1["counts"]["match"] == r2["counts"]["match"] == 1 and r2["moved"] == 0


def test_missing_cache_skips_loader(tmp_path):
    S = caches(tmp_path)
    r = build.run(S, str(tmp_path / "o"), str(tmp_path / "reg.json.gz"), fetch=False)
    assert r["loaders"]["fotmob_matches"]["ok"] is True
    assert r["loaders"]["schochastics"]["ok"] is True and "skipped" in r["loaders"]["schochastics"]["out"]
    assert os.path.exists(tmp_path / "o" / "coverage.json")


def test_fotmob_failure_fails_build(tmp_path, monkeypatch):
    S = caches(tmp_path)
    from graph.load import fotmob_matches
    monkeypatch.setattr(fotmob_matches, "load", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r = build.run(S, str(tmp_path / "o"), str(tmp_path / "reg.json.gz"), fetch=False)
    assert r["ok"] is False and not os.path.exists(tmp_path / "reg.json.gz")


def test_a_link_that_arrives_later_merges_and_old_ids_resolve(tmp_path):
    from graph.ids import Registry
    S = caches(tmp_path)                                   # FotMob: Al Ain (10) v Al Wahda (20)
    m = tmp_path / "mirror" / "s365"
    (m / "comp").mkdir(parents=True)
    ix = {"countries": {"1": ["الإمارات", "United Arab Emirates"]}, "comps": [], "teams": [[77, "العين", "Al Ain", 1, None]]}
    (m / "index.json").write_text(json.dumps(ix), encoding="utf-8")
    reg_path = str(tmp_path / "reg.json.gz")
    build.run(S, str(tmp_path / "o1"), reg_path, loaders=["fotmob_matches", "s365"], fetch=False)
    old = Registry.load(reg_path)
    split = old.get("team", "s365", 77)
    assert split != old.get("team", "fotmob", 10)          # build 1: 365 had no FotMob id for it, a team of its own
    ix["teams"][0][4] = 10                                  # db/scores365.py's fmmap finds it
    (m / "index.json").write_text(json.dumps(ix), encoding="utf-8")
    r = build.run(S, str(tmp_path / "o2"), reg_path, loaders=["fotmob_matches", "s365"], fetch=False)
    new = Registry.load(reg_path)
    assert r["ok"] and r["moved"] == 0 and r["merges"] == 1
    one = new.get("team", "fotmob", 10)
    assert new.get("team", "s365", 77) == one and new.resolve("team", split) == one
    import sqlite3
    c = sqlite3.connect(str(tmp_path / "o2" / "tifo.db"))
    assert c.execute("select count(*) from team where name_ar='العين' or name='Al Ain'").fetchone()[0] == 1
    assert c.execute("select home from match").fetchone()[0] == one


def test_empty_fotmob_cache_fails_the_build(tmp_path):
    (tmp_path / "db" / ".cache" / "fm" / "mx").mkdir(parents=True)
    S = Sources(str(tmp_path), mirror=str(tmp_path / "mirror"), s3=False)
    r = build.run(S, str(tmp_path / "o"), str(tmp_path / "reg.json.gz"), fetch=False)
    assert r["ok"] is False and not os.path.exists(tmp_path / "reg.json.gz")


class FakeStore:
    def __init__(self, state=None):
        self.state, self.json = dict(state or {}), {}

    def get_state(self, k, default=None):
        return self.state.get(k, default)

    def put_state(self, k, v):
        self.state[k] = v

    def put_json(self, k, v, cache=None):
        self.json[k] = v


def test_upload_starts_from_the_published_registry(tmp_path):
    from graph.ids import Registry
    pub = Registry(); pub.mint("team", "fotmob", 99); pub.mint("team", "fotmob", 10)
    stale = Registry(); stale.mint("team", "fotmob", 10)               # a laptop's own numbering
    p = str(tmp_path / "reg.json.gz")
    stale.save(p)
    build.registry_for_upload(FakeStore({build.REG_STATE: pub.to_json()}), p)
    assert Registry.load(p).get("team", "fotmob", 10) == 2


def test_publish_guard_counts_fotmob_matches():
    st = FakeStore({"graph/last.json": {"matches": 1000, "fotmob_matches": 1000}})
    cov = {"counts": {"match": 1200}, "by_src": {"match": {"fotmob": 100, "sch": 1100}}}
    assert build.publish_allowed(st, cov) is False
    cov["by_src"]["match"]["fotmob"] = 990
    assert build.publish_allowed(st, cov) is True


def test_the_upload_takes_the_files_in_subfolders_too(tmp_path):
    from graph import build
    (tmp_path / "matches" / "538").mkdir(parents=True)
    (tmp_path / "matches" / "index.json").write_text("{}")
    (tmp_path / "matches" / "538" / "2016-2017.json").write_text("{}")
    (tmp_path / "awards").mkdir()
    (tmp_path / "awards" / "index.json").write_text("{}")
    (tmp_path / "awards" / "notes.txt").write_text("x")
    got = sorted(k for k, _ in build.upload_files(str(tmp_path), ("awards", "matches", "people")))
    assert got == ["awards/index.json", "matches/538/2016-2017.json", "matches/index.json"]


def test_a_build_the_guard_refuses_says_why_and_keeps_its_record():
    # the 22 Nov 01:05 build: rc=1 «ok» true, and the runner's tail (200 characters) never reached the reason
    st = FakeStore({"graph/last.json": {"matches": 1000, "fotmob_matches": 1000}})
    cov = {"counts": {"match": 900}, "by_src": {"match": {"fotmob": 1000}}}
    why = build.publish_refusal(st, cov)
    assert why == "matches 900 < 95% of the last build's 1000"
    assert build.publish_refusal(st, {"counts": {"match": 1000}, "by_src": {"match": {"fotmob": 1000}}}) is None


def test_games_dropped_on_purpose_are_no_loss():
    # 23 Nov 2026: the seasons pass dropped its 85,245 aside games (copies, another division's) and the build was refused
    st = FakeStore({"graph/last.json": {"matches": 1000, "fotmob_matches": 1000}})
    cov = {"counts": {"match": 900}, "by_src": {"match": {"fotmob": 1000}}}
    assert build.publish_refusal(st, cov, dropped=100) is None
    assert build.publish_refusal(st, cov, dropped=40) == "matches 900 < 95% of the last build's 1000 (40 dropped on purpose)"
