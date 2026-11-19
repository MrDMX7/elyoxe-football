"""Tifo ids (spec §3.2): one integer sequence per entity type, never reused. The registry maps (type, source, source id)
to the id and keeps merges, so an id once published always leads to its entity."""
import gzip, json, os

TYPES = ("team", "player", "coach", "referee", "stadium", "competition", "edition", "match")


class Registry:
    def __init__(self, data=None):
        d = data or {}
        self.next = dict(d.get("next") or {})
        self.map = dict(d.get("map") or {})
        self.merged = dict(d.get("merged") or {})

    @staticmethod
    def key(t, src, sid):
        return f"{t}|{src}|{sid}"

    def resolve(self, t, i):
        for _ in range(64):
            j = self.merged.get(f"{t}|{i}")
            if j is None:
                return i
            i = j
        raise ValueError(f"merge cycle at {t} {i}")

    def get(self, t, src, sid):
        i = self.map.get(self.key(t, src, sid))
        return None if i is None else self.resolve(t, i)

    def mint(self, t, src, sid):
        if t not in TYPES:
            raise ValueError(f"unknown type {t}")
        i = self.get(t, src, sid)
        if i is not None:
            return i
        i = self.next.get(t, 0) + 1
        self.next[t] = i
        self.map[self.key(t, src, sid)] = i
        return i

    def alias(self, t, src, sid, tifo_id):
        """(src, sid) names entity tifo_id. False when it already names another one: a link is never turned into a merge."""
        cur = self.get(t, src, sid)
        if cur is None:
            self.map[self.key(t, src, sid)] = tifo_id
            return True
        return cur == self.resolve(t, tifo_id)

    def merge(self, t, a, b):
        a, b = self.resolve(t, a), self.resolve(t, b)
        if a == b:
            return a
        keep, drop = min(a, b), max(a, b)
        self.merged[f"{t}|{drop}"] = keep
        return keep

    def to_json(self):
        return {"next": dict(sorted(self.next.items())), "map": dict(sorted(self.map.items())), "merged": dict(sorted(self.merged.items()))}

    def save(self, path):
        body = json.dumps(self.to_json(), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        tmp = f"{path}.tmp"
        with open(tmp, "wb") as f, gzip.GzipFile(filename="", fileobj=f, mode="wb", mtime=0, compresslevel=6) as z:
            z.write(body)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path):
        if not os.path.exists(path):
            return cls()
        with gzip.open(path, "rb") as f:
            return cls(json.loads(f.read()))

    def moved(self, old):
        """Keys of the old registry whose entity changed: the old id no longer leads where the key now points."""
        out = []
        for k, i in old.map.items():
            t = k.split("|", 1)[0]
            if self.map.get(k) is None or self.resolve(t, self.map[k]) != self.resolve(t, old.resolve(t, i)):
                out.append(k)
        return sorted(out)
