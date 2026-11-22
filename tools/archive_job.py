"""The archive job (docs/superpowers/specs/2026-11-22-tifo-archive-static-design.md): every season of every competition we
publish, its seasons list and every archive match as static pages, from the published graph database, inside the site's own
shell, uploaded only where their bytes changed; and their sitemaps. .github/workflows/tifo-archive.yml runs it after each
graph build (and on dispatch); the hourly site publish leaves these paths alone (tools/runner.py ARCHIVE_OWNED).

  python -m tools.archive_job [--db tifo.db] [--comps 47,87] [--work DIR] [--force] [--dry]

The owner, 22 Nov 2026: «لما اضغط عالموسم اللي اباه يطلعلي كل شي كانه الموسم الحالي» and static pages «عشان تنتشر فقوقل».
"""
import argparse, gzip, hashlib, json, os, shutil, subprocess, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
REGION, STACK, SITE = "ap-south-1", "elyoxe-tifo-site", "https://tifo.elyoxe.com"
DB_KEY, MANIFEST, LAST = "graph/tifo.db.gz", "archive/manifest.json", "archive/last.json"
MAX_DELETE = 0.10              # more than a tenth of the archive gone in one run is a broken build, not a change
PER_MAP = 45000
INDEXNOW_KEY = "8a5d11d3194545d5a4750dc4ede4a7ad"      # public by design (served at /<key>.txt); tools/runner.py's


def say(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def clients():
    import boto3
    from botocore.config import Config
    cfg = Config(max_pool_connections=40, connect_timeout=20, read_timeout=60, retries={"max_attempts": 6, "mode": "standard"})
    return boto3.client("s3", region_name=REGION, config=cfg), boto3.client("cloudformation", region_name=REGION)


def site_bucket(cf):
    out = cf.describe_stacks(StackName=STACK)["Stacks"][0]["Outputs"]
    return next(o["OutputValue"] for o in out if o["OutputKey"] == "Bucket")


def state_get(s3, name, default=None):
    try:
        raw = s3.get_object(Bucket=DATA_BUCKET, Key="state/" + name)["Body"].read()
    except s3.exceptions.NoSuchKey:
        return default
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def state_put(s3, name, obj):
    s3.put_object(Bucket=DATA_BUCKET, Key="state/" + name, Body=gzip.compress(json.dumps(obj, separators=(",", ":")).encode()),
                  ContentType="application/json", ContentEncoding="gzip", CacheControl="no-store")


def known_pages(s3, bucket):
    """the site's own pages: a match, a man or a club with one links there (site/archive/build.cjs --known)"""
    out = {"m": set(), "p": set(), "t": set()}
    pages = s3.get_paginator("list_objects_v2")
    for kind, pres in (("m", [f"m/{d}" for d in "123456789"]), ("p", ["p/"]), ("t", ["t/"])):
        for pre in pres:
            for page in pages.paginate(Bucket=bucket, Prefix=pre):
                for o in page.get("Contents") or []:
                    parts = o["Key"].split("/")
                    if len(parts) == 3 and parts[2] == "index.html":
                        out[kind].add(parts[1])
    return {k: sorted(v) for k, v in out.items()}


def md5(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def upload(s3, bucket, out, old, dry=False):
    """{key: md5} of every page under out; sends the new and changed ones (40 at a time)"""
    new, todo = {}, []
    for root, _, files in os.walk(out):
        for f in files:
            if f.startswith("_"):
                continue
            p = os.path.join(root, f)
            k = os.path.relpath(p, out).replace("\\", "/")
            new[k] = md5(p)
            if old.get(k) != new[k]:
                todo.append((k, p))
    say(f"upload: {len(new)} pages, {len(todo)} new or changed")
    if dry:
        return new, 0

    def put(item):
        k, p = item
        ct = "application/xml; charset=utf-8" if k.endswith(".xml") else "text/html; charset=utf-8"
        with open(p, "rb") as fh:
            s3.put_object(Bucket=bucket, Key=k, Body=fh.read(), ContentType=ct, CacheControl="public,max-age=3600")
    failed, done, t0 = {}, 0, time.time()
    with ThreadPoolExecutor(40) as ex:
        futs = {ex.submit(put, it): it[0] for it in todo}
        for fu in as_completed(futs):
            try:
                fu.result()
            except Exception as e:
                failed[futs[fu]] = str(e)[:160]
            done += 1
            if done % 5000 == 0:
                say(f"upload: {done}/{len(todo)}, {done / max(1, time.time() - t0):.0f}/s")
    for k in failed:
        new.pop(k, None)                           # a page that did not go up is sent again next run
    if failed:
        say(f"upload: {len(failed)} failed, e.g. {next(iter(failed.values()))}")
    return new, len(todo) - len(failed)


def sitemaps(out, urls):
    """sitemap-archive-<n>.xml (45,000 URLs each) and their index sitemap-archive.xml, listed in robots.txt"""
    names = []
    for i in range(0, len(urls), PER_MAP):
        n = f"sitemap-archive-{i // PER_MAP + 1}.xml"
        body = "".join(f"<url><loc>{SITE}{u}</loc></url>" for u in urls[i:i + PER_MAP])
        open(os.path.join(out, n), "w", encoding="utf-8").write(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>')
        names.append(n)
    idx = "".join(f"<sitemap><loc>{SITE}/{n}</loc></sitemap>" for n in names)
    open(os.path.join(out, "sitemap-archive.xml"), "w", encoding="utf-8").write(
        f'<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{idx}</sitemapindex>')
    return names


def indexnow(urls):
    if not INDEXNOW_KEY or not urls:
        return
    body = json.dumps({"host": "tifo.elyoxe.com", "key": INDEXNOW_KEY, "keyLocation": f"{SITE}/{INDEXNOW_KEY}.txt",
                       "urlList": [SITE + u for u in urls[:10000]]}).encode()
    try:
        st = urllib.request.urlopen(urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                                           headers={"Content-Type": "application/json; charset=utf-8"}), timeout=30).status
        say(f"indexnow: {min(len(urls), 10000)} urls -> {st}")
    except Exception as e:
        say(f"indexnow: not sent ({e})")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db")
    ap.add_argument("--comps", default="")
    ap.add_argument("--work", default=os.path.join(ROOT, "archive-work"))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--shell", help="the archive shell from a local site build (_shells/archive.html) instead of the state's")
    a = ap.parse_args(argv)
    s3, cf = clients()
    bucket = site_bucket(cf)
    os.makedirs(a.work, exist_ok=True)
    head = s3.head_object(Bucket=DATA_BUCKET, Key=DB_KEY)
    last = state_get(s3, LAST, {})
    if not a.force and not a.db and last.get("etag") == head["ETag"]:
        say("the graph database has not changed since the last run: nothing to do")
        return 0
    db = a.db or os.path.join(a.work, "tifo.db")
    if not a.db:
        say("downloading the graph database")
        s3.download_file(DATA_BUCKET, DB_KEY, db + ".gz")
        with gzip.open(db + ".gz", "rb") as z, open(db, "wb") as f:
            shutil.copyfileobj(z, f, 1 << 24)
        os.remove(db + ".gz")
    shells = state_get(s3, "site/shells.json") or {}
    if a.shell:
        shells["archive"] = open(a.shell, encoding="utf-8").read()
    if not shells.get("archive"):
        say("no archive shell from the site build yet: nothing to do")
        return 1
    index = json.loads(gzip.decompress(raw) if (raw := s3.get_object(Bucket=DATA_BUCKET, Key="v1/index.json")["Body"].read())[:2] == b"\x1f\x8b" else raw)
    comps = [int(x) for x in a.comps.split(",") if x.strip()] or [int(c["id"]) for c in index["competitions"]]
    data, out = os.path.join(a.work, "data"), os.path.join(a.work, "out")
    for d in (data, out):
        shutil.rmtree(d, ignore_errors=True)
    sys.path.insert(0, ROOT)
    from graph import archive_export
    say("export", archive_export.export(db, data, comps))
    open(os.path.join(a.work, "shell.html"), "w", encoding="utf-8").write(shells["archive"])
    json.dump(index, open(os.path.join(a.work, "index.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(known_pages(s3, bucket), open(os.path.join(a.work, "known.json"), "w"))
    say("render")
    r = subprocess.run(["node", os.path.join(ROOT, "site", "archive", "build.cjs"), "--data", data, "--shell", os.path.join(a.work, "shell.html"),
                        "--index", os.path.join(a.work, "index.json"), "--known", os.path.join(a.work, "known.json"), "--out", out,
                        "--comps", ",".join(map(str, comps))], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        say("render failed", r.stderr[-3000:])
        return 1
    say("render", r.stdout.strip()[-400:])
    urls = json.load(open(os.path.join(out, "_archive_urls.json"), encoding="utf-8"))
    sitemaps(out, urls)
    old = state_get(s3, MANIFEST, {}) or {}
    new, sent = upload(s3, bucket, out, old, a.dry)
    gone = sorted(set(old) - set(new))
    if a.comps:                                    # a partial run (some competitions) deletes nothing of the others
        gone = []
        new = {**old, **new}
    if gone and not a.dry:
        if len(gone) > MAX_DELETE * max(len(old), 1):
            say(f"{len(gone)} of {len(old)} archive pages would go: not deleting (a broken build?)")
            new.update({k: old[k] for k in gone})
        else:
            for i in range(0, len(gone), 1000):
                s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in gone[i:i + 1000]], "Quiet": True})
            say(f"deleted {len(gone)} pages no longer in the archive")
    if not a.dry:
        state_put(s3, MANIFEST, new)
        state_put(s3, LAST, {"etag": head["ETag"], "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pages": len(new), "sent": sent})
        fresh = [u for u in urls if u.lstrip("/") + "index.html" not in old]          # new to the search engines
        indexnow(fresh)
    say(f"done: {len(new)} pages, {sent} sent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
