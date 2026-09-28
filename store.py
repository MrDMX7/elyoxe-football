"""Snapshot writer: S3 (production) or a local directory (tests, run.sh --local).

Public files live under PUBLIC ("v1/"), served by CloudFront with that origin path, so
https://<dist>.cloudfront.net/live.json is s3://<bucket>/v1/live.json. Poller state lives under
"state/", which the distribution cannot reach.

Rules enforced here, for every public file:
  * keep-last-good: a validator runs before the write; if it raises (empty, malformed) or the
    producing fetch failed, nothing is written and the previous object stays live. The failure is
    recorded in health.json with the time of the last good write.
  * JSON is gzip-compressed (Content-Encoding: gzip) with a deterministic header (mtime 0) so the
    same content always hashes the same; unchanged content is not re-uploaded.
  * Cache-Control by class: live 10 s ... cold 1 day (CACHE below).
  * .ics is stored uncompressed (calendar clients vary); CloudFront compresses on the fly.
"""
import gzip, hashlib, io, json, os
from pathlib import Path

from sources.schema import Invalid
from timeutil import iso, now_utc

PUBLIC = "v1/"
STATE = "state/"
CACHE = {
    "live": "public, max-age=10, stale-while-revalidate=10",
    "hot": "public, max-age=20, stale-while-revalidate=20",
    "warm": "public, max-age=300, stale-while-revalidate=60",
    "static": "public, max-age=3600, stale-while-revalidate=600",
    "cold": "public, max-age=86400, stale-while-revalidate=3600",
}
JSON_CT = "application/json; charset=utf-8"


def dumps(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=False).encode("utf-8")


def gz(data: bytes) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, compresslevel=6) as f:
        f.write(data)
    return buf.getvalue()


class LocalBackend:
    """Directory tree mirror of the bucket; metadata kept in a side file per object."""

    def __init__(self, root):
        self.root = Path(root)

    def put(self, key, body: bytes, content_type, cache_control, encoding=None):
        p = self.root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
        (p.parent / (p.name + ".meta")).write_text(json.dumps(
            {"ContentType": content_type, "CacheControl": cache_control, "ContentEncoding": encoding}))

    def get(self, key) -> bytes | None:
        p = self.root / key
        return p.read_bytes() if p.exists() else None

    def meta(self, key):
        p = self.root / (key + ".meta")
        return json.loads(p.read_text()) if p.exists() else None


class S3Backend:
    def __init__(self, bucket, client=None):
        import boto3
        self.bucket = bucket
        self.s3 = client or boto3.client("s3")
        self.puts = self.gets = 0

    def put(self, key, body: bytes, content_type, cache_control, encoding=None):
        kw = {"Bucket": self.bucket, "Key": key, "Body": body, "ContentType": content_type, "CacheControl": cache_control}
        if encoding:
            kw["ContentEncoding"] = encoding
        self.s3.put_object(**kw)
        self.puts += 1

    def get(self, key) -> bytes | None:
        self.gets += 1
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.s3.exceptions.NoSuchKey:
            return None
        except Exception as e:  # AccessDenied on a missing key when ListBucket is not granted
            if "NoSuchKey" in str(e) or "AccessDenied" in str(e) or "404" in str(e):
                return None
            raise


class Store:
    def __init__(self, backend, hashes: dict | None = None):
        self.b = backend
        self.hashes = hashes if hashes is not None else {}
        self.health: dict[str, dict] = {}
        self.written: list[str] = []
        self.skipped_same = 0
        self.refused: list[str] = []

    # ---- health ----
    def ok(self, name, **extra):
        self.health[name] = {"ok": True, "at": iso(now_utc()), "error": None, **extra}

    def fail(self, name, err, **extra):
        self.health[name] = {"ok": False, "at": iso(now_utc()), "error": str(err)[:300], **extra}

    # ---- public JSON ----
    def put_json(self, path, obj, cache="warm", validate=None, health_key=None, heartbeat=False) -> bool:
        """Write v1/<path> unless validation fails (keep last good) or content is unchanged.
        "Unchanged" ignores a top-level `generated` stamp (so `generated` = when the content last
        changed), except for heartbeat files (live.json, health.json) that must always move."""
        hk = health_key or path
        if validate is not None:
            try:
                validate(obj)
            except Invalid as e:
                self.refused.append(path)
                self.fail(hk, f"not written, kept last good: {e}")
                return False
        if health_key:
            self.ok(hk)             # a file that once failed validation must not stay «failing» after it succeeds again
        body = gz(dumps(obj))
        basis = body if heartbeat or not isinstance(obj, dict) or "generated" not in obj else \
            dumps({k: v for k, v in obj.items() if k != "generated"})
        h = hashlib.md5(basis).hexdigest()
        key = PUBLIC + path
        if self.hashes.get(key) == h + "|" + cache:
            self.skipped_same += 1
            return True
        self.b.put(key, body, JSON_CT, CACHE[cache], "gzip")
        self.hashes[key] = h + "|" + cache
        self.written.append(path)
        return True

    def put_text(self, path, text: str, content_type, cache="static") -> bool:
        body = text.encode("utf-8")
        h = hashlib.md5(body).hexdigest()
        key = PUBLIC + path
        if self.hashes.get(key) == h + "|" + cache:
            self.skipped_same += 1
            return True
        self.b.put(key, body, content_type, CACHE[cache])
        self.hashes[key] = h + "|" + cache
        self.written.append(path)
        return True

    def get_json(self, path, public=True):
        raw = self.b.get((PUBLIC if public else "") + path)
        if raw is None:
            return None
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return json.loads(raw)

    # ---- private state ----
    def get_state(self, name, default=None):
        raw = self.b.get(STATE + name)
        if raw is None:
            return default
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return json.loads(raw)

    def put_state(self, name, obj):
        self.b.put(STATE + name, gz(dumps(obj)), JSON_CT, "no-store", "gzip")


def local_store(root=None):
    return Store(LocalBackend(root or os.environ.get("FOOTBALL_OUT", "out")))
