"""Build tifo.db from the caches (spec §2, §4): loaders in precedence order, the registry checked for renumbering, the
coverage report written, then (--upload) published: the registry to S3 state, tifo.db.gz to S3 graph/ (private), the
coverage to v1/graph/coverage.json.

    python -m graph.build [--upload] [--out DIR] [--only fotmob_matches,names] [--no-fetch]
"""
import argparse, gzip, importlib, json, os, shutil, sys, time, traceback
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from graph import coverage, fetch, publish as P  # noqa: E402
from graph.db import Graph  # noqa: E402
from graph.ids import Registry  # noqa: E402
from graph.src import Sources  # noqa: E402

ORDER = ["fotmob_matches", "fotmob_profiles", "names", "s365", "tm", "rsssf", "schochastics", "martj42", "transfers",
         "honours", "fjelstul", "awards"]      # an edition honour's first source keeps it: our counts, Fjelstul, then Wikipedia
REQUIRED = {"fotmob_matches"}
CACHE = os.path.join(HERE, ".cache")       # the registry and the published mirror: kept between runs (actions/cache)
OUT = os.path.join(HERE, ".build")         # tifo.db and the report: rebuilt each run, never cached (1-2 GB)
REG_STATE = "graph/registry.json.gz"


def run(S, out_dir, reg_path, upload=False, loaders=None, fetch=True):
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    old = Registry.load(reg_path)
    reg = Registry(json.loads(json.dumps(old.to_json())))
    db_path = os.path.join(out_dir, "tifo.db")
    G = Graph(db_path)
    if fetch:
        for f in (fetch_mod().martj42, fetch_mod().fjelstul):
            try:
                f(S)
            except Exception as e:
                print(f"{f.__name__} fetch: {e}", flush=True)
    rec = {"started": datetime.now(timezone.utc).isoformat()[:19] + "Z", "loaders": {}, "ok": True}
    for name in loaders or ORDER:
        t = time.time()
        try:
            mod = importlib.import_module(f"graph.load.{name}")
            out = mod.load(G, reg, S)
            rec["loaders"][name] = {"ok": True, "secs": round(time.time() - t), "out": out}
        except Exception as e:
            traceback.print_exc()
            rec["loaders"][name] = {"ok": False, "secs": round(time.time() - t), "out": f"{type(e).__name__}: {str(e)[:300]}"}
            if name in REQUIRED:
                rec["ok"] = False
        G.c.commit()
        print(f"{name}: {rec['loaders'][name]}", flush=True)
    for t, drop, keep in reg.run_merges:          # links that arrived after a native mint: the rows follow the kept id
        G.remap(t, drop, keep)
    rec["merges"] = len(reg.run_merges)
    G.c.commit()
    moved = reg.moved(old)
    rec["moved"] = len(moved)
    if moved:
        rec["ok"] = False
        rec["moved_sample"] = moved[:20]
    cov = coverage.compute(G)
    rec["counts"] = cov["counts"]
    try:
        rec["awards_files"] = P.awards(G, out_dir)      # v1/awards/*: the pages' data (spec §7.6)
    except Exception as e:
        traceback.print_exc()
        rec["awards_files"] = f"{type(e).__name__}: {str(e)[:200]}"
    G.meta("build", {k: v for k, v in rec.items() if k != "loaders"})
    G.close()
    rec["secs"] = round(time.time() - t0)
    day = rec["started"][:10]
    json.dump({"generated": rec["started"], **cov}, open(os.path.join(out_dir, "coverage.json"), "w", encoding="utf-8", newline="\n"), ensure_ascii=False)
    open(os.path.join(out_dir, "coverage.md"), "w", encoding="utf-8", newline="\n").write(coverage.markdown(cov, day, rec))
    if rec["ok"]:
        reg.save(reg_path)
        if upload:
            publish(S, out_dir, reg_path, rec, cov)
    return rec


def fetch_mod():
    return fetch


def registry_for_upload(st, reg_path):
    """A publishing run starts from the published registry, never a local copy (a laptop's own numbering, an old cache)."""
    d = st.get_state(REG_STATE)
    if d:
        Registry(d).save(reg_path)
    return bool(d)


def publish_allowed(st, cov):
    """95% of the last published build's matches, counted in total and from FotMob alone: an empty FotMob cache would
    keep the total (every twin minted as a match of its own) and hide the loss."""
    prev = st.get_state("graph/last.json") or {}
    total, fm = cov["counts"]["match"], (cov.get("by_src", {}).get("match") or {}).get("fotmob", 0)
    for now, key in ((total, "matches"), (fm, "fotmob_matches")):
        if prev.get(key) and now < 0.95 * prev[key]:
            print(f"not published: {key} {now} < 95% of the last build's {prev[key]}", flush=True)
            return False
    return True


def publish(S, out_dir, reg_path, rec, cov):
    st = S.store()
    if not publish_allowed(st, cov):
        rec["published"] = False
        return
    st.put_state(REG_STATE, json.loads(gzip.decompress(open(reg_path, "rb").read())))
    gz = os.path.join(out_dir, "tifo.db.gz")
    with open(os.path.join(out_dir, "tifo.db"), "rb") as f, gzip.open(gz, "wb", compresslevel=6) as z:
        shutil.copyfileobj(f, z, 16 << 20)
    st.b.s3.upload_file(gz, st.b.bucket, "graph/tifo.db.gz")      # private: outside v1/, not served
    st.put_json("graph/coverage.json", {"generated": rec["started"], "counts": cov["counts"], "linked": cov["linked"], "arabic": cov["arabic"],
                                        "editions": cov["editions"]}, cache="static")
    ad = os.path.join(out_dir, "awards")
    sent = 0
    for name in sorted(os.listdir(ad)) if os.path.isdir(ad) else []:
        if name.endswith(".json"):
            st.put_json(f"awards/{name}", json.load(open(os.path.join(ad, name), encoding="utf-8")), cache="static")
            sent += 1
    rec["awards_sent"] = sent
    st.put_state("graph/last.json", {"at": rec["started"], "matches": cov["counts"]["match"], "fotmob_matches": cov["by_src"]["match"].get("fotmob", 0),
                                      "secs": rec["secs"]})
    rec["published"] = True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--only", default="")
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args(argv)
    S = Sources()
    reg_path = os.path.join(CACHE, "registry.json.gz")
    os.makedirs(CACHE, exist_ok=True)
    if a.upload:
        registry_for_upload(S.store(), reg_path)
    rec = run(S, a.out, reg_path, upload=a.upload, loaders=[x for x in a.only.split(",") if x] or None, fetch=not a.no_fetch)
    day = rec["started"][:10]
    if a.out == OUT:
        shutil.copyfile(os.path.join(a.out, "coverage.md"), os.path.join(os.path.dirname(HERE), "docs", f"GRAPH-COVERAGE-{day}.md"))
    print(json.dumps({k: v for k, v in rec.items() if k != "loaders"}, ensure_ascii=False))
    return 0 if rec["ok"] and rec.get("published", True) else 1


if __name__ == "__main__":
    sys.exit(main())
