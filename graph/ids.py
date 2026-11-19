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
        self.run_merges = []          # (type, dropped id, kept id) done by this build: graph.build remaps their rows
        self._rev = None              # {(type, id): sources whose keys name it}, built on first need

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
        self._note(t, i, src)
        return i

    def _sources(self, t, i):
        if self._rev is None:
            self._rev = {}
            for k, j in self.map.items():
                tt, s_, _ = k.split("|", 2)
                self._rev.setdefault((tt, self.resolve(tt, j)), set()).add(s_)
        return self._rev.get((t, self.resolve(t, i)), set())

    def _note(self, t, i, src):
        if self._rev is not None:
            self._rev.setdefault((t, self.resolve(t, i)), set()).add(src)

    def linked(self, t, src, sid):
        """The key's entity is named by another source too (a link, not just this source's own mint)."""
        cur = self.get(t, src, sid)
        return cur is not None and bool(self._sources(t, cur) - {src})

    def link(self, t, src, sid, tifo_id):
        """(src, sid) is entity tifo_id, by a trusted link (a crosswalk, a match twin). Returns the entity's id, or None when
        the key already names another entity that other sources name too: two real entities are never merged by a link.
        When the key's entity is only this source's own (minted before the link existed), the two are merged, the lower id
        kept (spec §3.2), and the merge is listed in run_merges so the build moves the rows written under the other id."""
        cur = self.get(t, src, sid)
        tgt = self.resolve(t, tifo_id)
        if cur is None:
            self.map[self.key(t, src, sid)] = tgt
            self._note(t, tgt, src)
            return tgt
        if cur == tgt:
            return cur
        if self._sources(t, cur) - {src}:
            return None
        keep, drop = min(cur, tgt), max(cur, tgt)
        src_keep, src_drop = self._sources(t, keep), self._sources(t, drop)
        self.merge(t, keep, drop)
        self._rev[(t, keep)] = src_keep | src_drop
        self._rev.pop((t, drop), None)
        self.run_merges.append((t, drop, keep))
        return keep

    def alias(self, t, src, sid, tifo_id):
        """(src, sid) names entity tifo_id. False when it already names another one: a link is never turned into a merge."""
        cur = self.get(t, src, sid)
        if cur is None:
            self.map[self.key(t, src, sid)] = tifo_id
            self._note(t, tifo_id, src)
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
