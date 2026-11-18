"""The store's file format for the desk's Lambda (store.py, without its imports): public JSON under v1/ and private state under
state/, gzipped, with the same content type and cache headers, so the journal, the site and the desk read each other's files.
tests/test_desk_app.py checks the round trip against the repo's own Store."""
import gzip, io, json

PUBLIC, STATE = "v1/", "state/"
CACHE = {
    "live": "public, max-age=10, stale-while-revalidate=10",
    "hot": "public, max-age=20, stale-while-revalidate=20",
    "warm": "public, max-age=300, stale-while-revalidate=60",
    "static": "public, max-age=3600, stale-while-revalidate=600",
    "cold": "public, max-age=86400, stale-while-revalidate=3600",
}
JSON_CT = "application/json; charset=utf-8"


def _gz(data):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, compresslevel=6) as f:
        f.write(data)
    return buf.getvalue()


def _load(raw):
    if raw is None:
        return None
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


class S3Backend:
    def __init__(self, bucket, client=None):
        import boto3
        self.bucket, self.s3 = bucket, client or boto3.client("s3")

    def put(self, key, body, content_type, cache_control, encoding=None):
        kw = {"Bucket": self.bucket, "Key": key, "Body": body, "ContentType": content_type, "CacheControl": cache_control}
        if encoding:
            kw["ContentEncoding"] = encoding
        self.s3.put_object(**kw)

    def get(self, key):
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except Exception as e:
            if "NoSuchKey" in str(e) or "AccessDenied" in str(e) or "404" in str(e):
                return None
            raise

    def keys(self, prefix):
        out, tok = [], None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": prefix, **({"ContinuationToken": tok} if tok else {})}
            r = self.s3.list_objects_v2(**kw)
            out += [o["Key"] for o in r.get("Contents") or []]
            if not r.get("IsTruncated"):
                return out
            tok = r["NextContinuationToken"]


class Store:
    def __init__(self, backend):
        self.b = backend

    def get_json(self, path):
        return _load(self.b.get(PUBLIC + path))

    def put_json(self, path, obj, cache="warm"):
        self.b.put(PUBLIC + path, _gz(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")), JSON_CT, CACHE[cache], "gzip")
        return True

    def put_bytes(self, path, body, content_type, cache="static"):
        self.b.put(PUBLIC + path, body, content_type, CACHE[cache])
        return True

    def get_state(self, name, default=None):
        v = _load(self.b.get(STATE + name))
        return default if v is None else v

    def put_state(self, name, obj):
        self.b.put(STATE + name, _gz(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")), JSON_CT, "no-store", "gzip")

    def state_keys(self, prefix):
        """State file names under a prefix (the versions of an article)."""
        if hasattr(self.b, "keys"):
            return [k[len(STATE):] for k in self.b.keys(STATE + prefix)]
        root = getattr(self.b, "root", None)                     # the repo's LocalBackend, in the tests
        st = root / STATE.rstrip("/") if root is not None else None
        if st is None or not st.exists():
            return []
        return sorted(k for k in (p.relative_to(st).as_posix() for p in st.rglob("*") if p.is_file() and not p.name.endswith(".meta"))
                      if k.startswith(prefix))
