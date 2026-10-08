"""`aws s3 sync out s3://… --delete` for the site's pages, with boto3 and many uploads at a time (2026-10-08).

The CLI's sync sent the laptop's pages at about 1 file a second (a 1,000-file build took 18 minutes, a full one 2 hours)
while the line takes 3-4 MB/s. Same rules as the sync it replaces: a file goes up when its key is missing, its size
differs, or the local file is newer than the object; a key under no local file is deleted; the excludes apply to both.
Content-Type per extension is what the CLI gave the live objects. Deletes stop at 10 % of what is up (the runner's
partial-build guard is the first line; this is the second). Any failure returns ok=False and the runner falls back to the CLI.

    python -m tools.s3push <dir> <bucket> [--dry]
"""
import fnmatch, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

TYPES = {".html": "text/html", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".webp": "image/webp", ".svg": "image/svg+xml", ".xml": "text/xml", ".txt": "text/plain", ".css": "text/css",
         ".js": "text/javascript", ".webmanifest": "application/manifest+json", ".mp3": "audio/mpeg", ".ico": "image/x-icon"}
MAX_DELETE = 0.10


def push(src, bucket, region, excludes=(), cache_control=None, delete=True, workers=32, dry=False, say=print):
    """(ok, note)"""
    import boto3
    from botocore.config import Config
    s3 = boto3.client("s3", region_name=region, config=Config(max_pool_connections=workers + 4,
                                                              retries={"max_attempts": 6, "mode": "standard"}))
    skip = lambda k: any(fnmatch.fnmatchcase(k, p) for p in excludes)
    t0 = time.time()
    remote = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for o in page.get("Contents") or []:
            if not skip(o["Key"]):
                remote[o["Key"]] = (o["Size"], o["LastModified"])
    local, todo = set(), []
    for root, _, files in os.walk(src):
        for f in files:
            p = os.path.join(root, f)
            k = os.path.relpath(p, src).replace("\\", "/")
            if skip(k):
                continue
            local.add(k)
            st = os.stat(p)
            r = remote.get(k)
            if r is None or r[0] != st.st_size or datetime.fromtimestamp(st.st_mtime, timezone.utc) > r[1]:
                todo.append((k, p))
    gone = sorted(k for k in remote if k not in local)
    say(f"s3push: {len(remote)} up, {len(local)} local, {len(todo)} to send, {len(gone)} to delete ({time.time() - t0:.0f}s to compare)")
    if dry:
        return True, "dry run"

    def put(item):
        k, p = item
        with open(p, "rb") as fh:
            kw = {"Bucket": bucket, "Key": k, "Body": fh.read()}
        if cache_control:
            kw["CacheControl"] = cache_control
        ct = TYPES.get(os.path.splitext(k)[1].lower())
        if ct:
            kw["ContentType"] = ct
        s3.put_object(**kw)

    t1, failed = time.time(), []
    with ThreadPoolExecutor(workers) as ex:
        for fu in as_completed([ex.submit(put, it) for it in todo]):
            try:
                fu.result()
            except Exception as e:
                failed.append(str(e)[:160])
    say(f"s3push: sent {len(todo) - len(failed)} of {len(todo)} in {time.time() - t1:.0f}s")
    if failed:
        return False, f"{len(failed)} uploads failed, e.g. {failed[0]}"
    if delete and gone:
        if len(gone) > MAX_DELETE * max(len(remote), 1):
            return False, f"{len(gone)} deletes of {len(remote)} objects is over {MAX_DELETE:.0%}; nothing deleted"
        for i in range(0, len(gone), 1000):
            r = s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in gone[i:i + 1000]], "Quiet": True})
            if r.get("Errors"):
                return False, f"{len(r['Errors'])} deletes failed, e.g. {r['Errors'][0]}"
        say(f"s3push: deleted {len(gone)}")
    return True, f"{len(todo)} sent, {len(gone) if delete else 0} deleted in {time.time() - t0:.0f}s"


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    ok, note = push(a[0], a[1], "ap-south-1", excludes=["assets/*", "logo/*", "next/*", "google*.html", "db/player/[0-9]*", "og/s/*", "m/*/g/*"],
                    cache_control="public,max-age=60", dry="--dry" in sys.argv)
    print(ok, note)
    sys.exit(0 if ok else 1)
