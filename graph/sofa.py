"""SofaScore's player of the match for the seasons FotMob has no ratings for (owner 2026-11-20, explicit permission). Runs on
the laptop (SofaScore answers a real browser, not a script): the leagues of graph/sofa.yaml, minus every season whose FotMob
matches are rated (80%+, from the published v1/graph/coverage.json), through graph/sofa_fetch.cjs (Playwright, one request a
second, a budget a run). The files ride S3 state/graph/sofa/cache.tar.gz to the nightly graph (graph/load/sofascore.py).

    python -m graph.sofa [--upload] [--budget 2500]
"""
import argparse, io, json, os, subprocess, sys, tarfile
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from graph.src import Sources  # noqa: E402
from graph.load.sofascore import STATE_KEY, restore  # noqa: E402

CACHE = os.path.join(HERE, ".cache", "sofa")


def skips(S, fids):
    """{FotMob competition id: [season labels FotMob already rates]} from the published coverage report."""
    cov = S.published("graph/coverage.json") or {}
    try:
        import config
        ar = {c["id"]: c.get("name_ar") for c in config.competitions()}
    except Exception:
        ar = {}
    out = {f: [] for f in fids}
    for e in cov.get("editions") or []:
        for f in fids:
            if ar.get(f) and e.get("name") == ar[f] and e.get("matches") and (e.get("ratings") or 0) >= 0.8 * e["matches"]:
                out[f].append(e["season"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--budget", type=int, default=2500)
    a = ap.parse_args(argv)
    S = Sources()
    if a.upload and not os.path.isdir(CACHE):
        restore(S, CACHE)
    m = yaml.safe_load(open(os.path.join(HERE, "sofa.yaml"), encoding="utf-8")) or {}
    sk = skips(S, list(m))
    jobs = [{"ut": ut, "fid": fid, "skip": sk.get(fid, [])} for fid, ut in m.items()]
    os.makedirs(CACHE, exist_ok=True)
    jf = os.path.join(CACHE, "..", "sofa_jobs.json")
    json.dump(jobs, open(jf, "w", encoding="utf-8"))
    root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, shell=os.name == "nt").stdout.strip()
    r = subprocess.run(["node", os.path.join(HERE, "sofa_fetch.cjs"), jf, CACHE, str(a.budget)], env=dict(os.environ, NODE_PATH=root))
    if a.upload:
        st = S.store()
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            tf.add(CACHE, arcname="sofa")
        st.b.s3.put_object(Bucket=st.b.bucket, Key=STATE_KEY, Body=buf.getvalue(), ContentType="application/gzip")
        print(f"uploaded {len(buf.getvalue()) // 1024} KB", flush=True)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
