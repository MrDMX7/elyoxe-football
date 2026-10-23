"""The bridge between the laptop and the GitHub Actions runs of Tifo's jobs (2026-10-23: site, journal, names, newsletter moved
to .github/workflows/; the X reader and the streams stay on the laptop).

A few inputs live outside this repo, in the owner's workspace, and a few switches under ~/.elyoxe/. The laptop mirrors them
to s3://<football bucket>/ci/home/ (paths relative to ~, so nothing that joins a path onto ~ changes); a run pulls them into
its own ~ first. A run's Gemini usage lines go the other way, to ci/usage/, and the laptop folds them into
~/.elyoxe/usage.jsonl, the file the daily cost email sums. Small job state between runs (the journal's YouTube "seen" list,
the names job's Wikidata cache) is one tar per job under ci/state/; the site job's 1.1 GB cache rides actions/cache, and
ci/seed/site-cache.tar is the copy a run starts from only when that cache is gone (the database job's 1.9 GB likewise,
ci/seed/db-cache.tar).

    python -m tools.ci_bridge push                      laptop: inputs and switches up (only what changed), usage lines in
    python -m tools.ci_bridge pull                      runner: inputs and switches into ~
    python -m tools.ci_bridge usage                     runner: this run's ~/.elyoxe/usage.jsonl up for the laptop
    python -m tools.ci_bridge state-get <name> <root>   runner: ci/state/<name>.tar into <root> (missing = first run)
    python -m tools.ci_bridge state-put <name> <root> <path>...
    python -m tools.ci_bridge seed [site|db]            laptop, once: site/cache and the jobs' state (site: the tar alone; db: the database caches)
    python -m tools.ci_bridge seed-get [site|db]        runner: the seed into place when actions/cache has none

The laptop's push runs from tools/runner.py after every job it still runs there (streams, every 5 minutes), at most every
10 minutes, so an edit to the lexicon or the research reaches the next GitHub build within minutes.
"""
import hashlib, io, json, os, sys, tarfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
REGION = "ap-south-1"
HOME = Path.home()
PREFIX = "ci/home/"
# what the jobs read from outside the repo, relative to ~ (a directory ends in /)
INPUTS = ["workspace/content/video/_system/EMIRATI-LEXICON.json",        # site/ai/gen.py, at import
          "workspace/research/tifo-2026-09-27/",                         # site/build.cjs (broadcasters, stadiums, legends…)
          "workspace/tools/s3fast.py"]                                   # tools/runner.py s3(); the CLI when missing
FLAGS = [".elyoxe/gemini-off", ".elyoxe/claude-off", ".elyoxe/tifo-alerts-off"]   # the owner's switches (usage_log, runner)
STAMP = ROOT / "site" / "cache" / "ci_bridge.json"
EVERY = 600


def s3():
    import boto3
    from botocore.config import Config
    return boto3.client("s3", region_name=REGION, config=Config(retries={"max_attempts": 6, "mode": "standard"}))


def listing(c, prefix):
    out = {}
    for page in c.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix):
        for o in page.get("Contents") or []:
            out[o["Key"]] = o.get("ETag", "").strip('"')
    return out


def local_inputs():
    """{relative path under ~: absolute path} for every input file and every switch that is on."""
    files = {}
    for rel in INPUTS:
        p = HOME / rel
        if rel.endswith("/"):
            if p.is_dir():
                for f in sorted(p.rglob("*")):
                    if f.is_file() and not f.name.startswith("."):
                        files[f.relative_to(HOME).as_posix()] = f
        elif p.is_file():
            files[rel] = p
    for rel in FLAGS:
        if (HOME / rel).exists():
            files[rel] = HOME / rel
    return files


def push(force=False):
    """Laptop: mirror INPUTS and FLAGS to ci/home/ (a key goes up when its MD5 differs, and goes when its file or switch
    is gone), then fold ci/usage/*.jsonl into ~/.elyoxe/usage.jsonl. At most every EVERY seconds unless forced."""
    try:
        st = json.loads(STAMP.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    if not force and time.time() - float(st.get("at") or 0) < EVERY:
        return {"skipped": "recent"}
    c = s3()
    remote = listing(c, PREFIX)
    files, sent, gone = local_inputs(), 0, 0
    for rel, p in files.items():
        body = p.read_bytes()
        if remote.get(PREFIX + rel) != hashlib.md5(body).hexdigest():
            c.put_object(Bucket=BUCKET, Key=PREFIX + rel, Body=body)
            sent += 1
    for k in remote:
        if k[len(PREFIX):] not in files:
            c.delete_object(Bucket=BUCKET, Key=k)
            gone += 1
    folded = 0
    for k in sorted(listing(c, "ci/usage/")):
        lines = c.get_object(Bucket=BUCKET, Key=k)["Body"].read().decode("utf-8")
        log = HOME / ".elyoxe" / "usage.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8", newline="\n") as f:
            f.write(lines if lines.endswith("\n") or not lines else lines + "\n")
        c.delete_object(Bucket=BUCKET, Key=k)
        folded += 1
    STAMP.parent.mkdir(parents=True, exist_ok=True)
    STAMP.write_text(json.dumps({"at": time.time(), "files": len(files), "sent": sent, "removed": gone, "usage_files": folded}), encoding="utf-8")
    return {"files": len(files), "sent": sent, "removed": gone, "usage_files": folded}


def pull():
    """Runner: every key under ci/home/ to the same path under ~."""
    c, n = s3(), 0
    for k in listing(c, PREFIX):
        dst = HOME / k[len(PREFIX):]
        dst.parent.mkdir(parents=True, exist_ok=True)
        c.download_file(BUCKET, k, str(dst))
        n += 1
    missing = [r for r in INPUTS if not (HOME / r).exists()]
    return {"pulled": n, "missing": missing}


def usage():
    """Runner: ~/.elyoxe/usage.jsonl (what this run's Gemini calls wrote) to ci/usage/<run>.jsonl, for the laptop."""
    p = HOME / ".elyoxe" / "usage.jsonl"
    if not p.exists() or not p.stat().st_size:
        return {"usage": 0}
    key = f"ci/usage/{os.environ.get('GITHUB_RUN_ID', int(time.time()))}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}-{os.environ.get('GITHUB_JOB', 'job')}.jsonl"
    s3().put_object(Bucket=BUCKET, Key=key, Body=p.read_bytes())
    return {"usage": sum(1 for _ in open(p, encoding="utf-8")), "key": key}


def state_get(name, root):
    c = s3()
    try:
        body = c.get_object(Bucket=BUCKET, Key=f"ci/state/{name}.tar.gz")["Body"].read()
    except c.exceptions.NoSuchKey:
        return {"state": name, "found": False}
    Path(root).mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as t:
        t.extractall(root, filter="data")
    return {"state": name, "found": True, "bytes": len(body)}


def state_put(name, root, paths):
    buf, n = io.BytesIO(), 0
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for rel in paths:
            p = Path(root) / rel
            if p.exists():
                t.add(str(p), arcname=rel)
                n += 1
    if not n:
        return {"state": name, "put": False}
    s3().put_object(Bucket=BUCKET, Key=f"ci/state/{name}.tar.gz", Body=buf.getvalue())
    return {"state": name, "put": True, "bytes": len(buf.getvalue())}


SEED = "ci/seed/site-cache.tar"
SEED_SKIP = {"runner"}                       # logs stay where they were written


def seed(only_site=False):
    """Laptop, once (or to refresh a cold start): site/cache as one tar, the journal's and the names job's state, the
    inputs, and the page count the partial-build guard compares against. only_site: the tar alone (the jobs' state in S3
    is newer than the laptop's once GitHub runs them)."""
    import tempfile
    cache = ROOT / "site" / "cache"
    tmp = Path(tempfile.gettempdir()) / "tifo-site-cache.tar"
    with tarfile.open(tmp, "w") as t:
        for p in sorted(cache.iterdir()):
            if p.name in SEED_SKIP or p.name.endswith(".lock"):
                continue
            t.add(str(p), arcname=p.name)
    c = s3()
    c.upload_file(str(tmp), BUCKET, SEED)
    size = tmp.stat().st_size
    tmp.unlink()
    out = {"seed_bytes": size}
    if only_site:
        return out
    out["journal"] = state_put("journal", str(ROOT), ["news/.cache", "site/cache/bing_sent.json"])
    out["names"] = state_put("names", str(HOME / ".cache"), ["tifo-names"])
    out["inputs"] = push(force=True)
    lp = cache / "last_pages"
    if lp.exists():
        sys.path.insert(0, str(ROOT))
        from store import Store, S3Backend
        Store(S3Backend(BUCKET)).put_state("runner/site-pages.json", {"pages": int(lp.read_text().strip() or 0), "host": "laptop-seed",
                                                                     "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        out["pages"] = int(lp.read_text().strip() or 0)
    return out


DB_SEED = "ci/seed/db-cache.tar"
DB_DIRS = ["db/.cache", "history/.cache"]          # the database job's caches (FotMob, 365Scores, Transfermarkt, Wikidata…)


def seed_db():
    """Laptop, once: the database job's caches (~1.9 GB) for its first GitHub run."""
    import tempfile
    tmp = Path(tempfile.gettempdir()) / "tifo-db-cache.tar"
    with tarfile.open(tmp, "w") as t:
        for d in DB_DIRS:
            if (ROOT / d).is_dir():
                t.add(str(ROOT / d), arcname=d, filter=lambda ti: None if ti.name.endswith((".log", ".tmp")) else ti)
    s3().upload_file(str(tmp), BUCKET, DB_SEED)
    size = tmp.stat().st_size
    tmp.unlink()
    return {"db_seed_bytes": size}


def seed_get(kind="site"):
    """Runner: the seed into place (site: site/cache; db: db/.cache and history/.cache), when actions/cache had none."""
    key, dst = (SEED, ROOT / "site" / "cache") if kind == "site" else (DB_SEED, ROOT)
    dst.mkdir(parents=True, exist_ok=True)
    c = s3()
    try:
        c.head_object(Bucket=BUCKET, Key=key)
    except Exception:
        return {"seed": False, "kind": kind}
    tmp = ROOT / f"{kind}-cache-seed.tar"
    c.download_file(BUCKET, key, str(tmp))
    with tarfile.open(tmp) as t:
        t.extractall(dst, filter="data")
    size = tmp.stat().st_size
    tmp.unlink()
    return {"seed": True, "kind": kind, "bytes": size}


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "push":
        r = push(force="--force" in argv)
    elif cmd == "pull":
        r = pull()
    elif cmd == "usage":
        r = usage()
    elif cmd == "state-get":
        r = state_get(argv[1], argv[2])
    elif cmd == "state-put":
        r = state_put(argv[1], argv[2], argv[3:])
    elif cmd == "seed":
        r = seed_db() if argv[1:2] == ["db"] else seed(only_site=argv[1:2] == ["site"])
    elif cmd == "seed-get":
        r = seed_get(argv[1] if len(argv) > 1 else "site")
    else:
        print(__doc__)
        return 2
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
