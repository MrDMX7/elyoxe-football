"""Where the loaders read: the stages' caches (db/.cache, history/.cache, names/) and our own published files (v1/...),
read from a local mirror (graph/.cache/v1/) refreshed from S3 once a build. Loaders never reach other sites."""
import gzip, json, os, time
from graph import ROOT


class Sources:
    def __init__(self, root=ROOT, mirror=None, s3=True):
        self.root = root
        self.db = os.path.join(root, "db", ".cache")
        self.hist = os.path.join(root, "history", ".cache")
        self.names = os.path.join(root, "names")
        self.mirror = mirror or os.path.join(root, "graph", ".cache", "v1")
        self.s3 = s3
        self._store = None

    @staticmethod
    def read(path):
        try:
            raw = open(path, "rb").read()
        except OSError:
            return None
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        try:
            return json.loads(raw)
        except ValueError:
            return None

    def store(self):
        if self._store is None:
            import sys
            sys.path.insert(0, self.root)
            from store import Store, S3Backend
            self._store = Store(S3Backend(os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")))
        return self._store

    def published(self, key, max_age_h=20):
        """v1/<key>: the mirror when fresh, else S3 (saved to the mirror), else a stale mirror copy, else None."""
        p = os.path.join(self.mirror, key)
        if os.path.exists(p) and (not self.s3 or time.time() - os.path.getmtime(p) < max_age_h * 3600):
            return self.read(p)
        if self.s3:
            try:
                d = self.store().get_json(key)
            except Exception as e:
                print(f"published {key}: {type(e).__name__} {str(e)[:120]}", flush=True)
                d = None
            if d is not None:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8", newline="\n") as f:
                    json.dump(d, f, ensure_ascii=False)
                return d
        return self.read(p) if os.path.exists(p) else None
