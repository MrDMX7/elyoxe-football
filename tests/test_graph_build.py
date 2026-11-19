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
