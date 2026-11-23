"""photos/build.py --archive: the archive men's portraits survive a stop. 23 Nov 2026: a 12,510-photo run was stopped after
4,610 uploads, and nothing of it was kept (its index and state are written at the end): the next run would check every man
again and send every picture again."""
import json
from types import SimpleNamespace
from photos import build as B


class Store:
    def __init__(self, have=(), state=None, people=None):
        self.json = {"people/qids.json": people or {}, "ph/index.json": {"players": {}}}
        self.state = {"photos_archive.json": state or {}}
        self.put, self.saves = [], []
        self.b = SimpleNamespace(put=lambda k, *a: self.put.append(k), have=set(have))

    def get_json(self, k):
        return json.loads(json.dumps(self.json.get(k))) if self.json.get(k) is not None else None

    def put_json(self, k, v, cache=None):
        self.json[k] = v
        self.saves.append(("json", k, len(v.get("players", {}))))

    def get_state(self, k, d=None):
        return self.state.get(k, d)

    def put_state(self, k, v):
        self.state[k] = json.loads(json.dumps(v))
        self.saves.append(("state", k, len(v)))


def lic(files):
    return {f: {"thumb": "t/" + f, "short": "CC BY", "license": "CC BY", "artist": "A", "page": "p/" + f} for f in files}


def test_portraits_are_saved_as_they_go_and_a_picture_already_up_is_not_sent_again(monkeypatch):
    monkeypatch.setattr(B, "commons", lic)
    got = []
    monkeypatch.setattr(B, "http", lambda u, timeout=60: got.append(u) or b"raw")
    monkeypatch.setattr(B, "portrait", lambda raw: b"webp")
    s = Store()
    cand = {f"k{i}": f"F{i}.jpg" for i in range(5)}
    st = {k: {} for k in cand}
    index = {"players": {}}
    saved = []
    made = B.portraits(s, cand, st, index, False, have={"k0", "k1"}, save=lambda: saved.append(len(index["players"])), every=2)
    assert made == 5 and sorted(index["players"]) == sorted(cand)
    assert got == ["t/F2.jpg", "t/F3.jpg", "t/F4.jpg"]                   # k0, k1 were up already
    assert s.put == ["v1/ph/k2.webp", "v1/ph/k3.webp", "v1/ph/k4.webp"]
    assert saved == [2, 4]                                              # every 2 men; the caller saves the last


def test_a_stopped_run_picks_up_the_men_whose_portrait_was_pending(monkeypatch):
    monkeypatch.setattr(B, "commons", lic)
    monkeypatch.setattr(B, "http", lambda u, timeout=60: b"raw")
    monkeypatch.setattr(B, "portrait", lambda raw: b"webp")
    monkeypatch.setattr(B, "wikidata", lambda qids, need_img=True: {})   # nobody new to check
    now = "2099-01-01T00:00:00Z"
    state = {"k1": {"qid": "Q1", "checked": now, "identity": "ok", "status": "pending", "img": "F1.jpg"},
             "k2": {"qid": "Q2", "checked": now, "identity": "ok", "status": "ok"}}
    s = Store(state=state, people={"k1": ["Q1", None, "A"], "k2": ["Q2", None, "B"]})
    monkeypatch.setattr(B, "uploaded", lambda store: set())
    B.archive_run(s, SimpleNamespace(limit=0, dry=False))
    assert s.put == ["v1/ph/k1.webp"]
    assert s.state["photos_archive.json"]["k1"]["status"] == "ok" and "k1" in s.json["ph/index.json"]["players"]
