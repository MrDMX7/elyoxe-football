"""news/articles/run.py end to end with a LocalBackend and a fake writer: a due match is written, checked, photographed and
published; a thin match is skipped once; API errors leave the match due and stop after 3 tries; a changed match is written
again under the same id; the $180 cap and types.json «on» stop everything."""
import copy, json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from store import Store, LocalBackend
from news.articles import run as R

FX = Path(__file__).parent / "fixtures" / "articles"
MD = json.loads((FX / "match_5181860.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
DAY = {"leagues": [{"id": 42, "matches": [{"id": MD["id"], "utc": MD["kickoff_utc"], "status": "finished",
                                           "home": [MD["home"]["id"], MD["home"]["name_ar"], 2], "away": [MD["away"]["id"], MD["away"]["name_ar"], 3]}]}]}


def data(md=MD):
    files = {f"match/{md['id']}.json": md, "all/20261116.json": DAY, "all/20261115.json": {"leagues": []}}
    return lambda p: copy.deepcopy(files.get(p))


class FakeWriter:
    def __init__(self, texts=None, error=None):
        self.texts, self.error, self.calls = list(texts or []), error, []
    def write(self, kind, sheet, model, notes=None):
        self.calls.append(notes)
        if self.error:
            raise self.error
        line = self.texts.pop(0) if self.texts else f"فاز {MD['away']['name_ar']} 3-2. " + "كلمة " * 330    # a report-length text
        return ({"headline": "عنوان", "standfirst": "مقدمة", "sections": [{"subhead": "ق", "paragraphs": [line]}], "facts_box": [], "sources_cited": ["بيانات تيفو"]},
                {"in": 5000, "out": 2000, "cache_read": 0, "cache_write": 0})


@pytest.fixture(autouse=True)
def on(monkeypatch):
    monkeypatch.setattr(R, "TYPES", {"report": {"on": True, "model": "claude-sonnet-5-5", "words": [300, 400]}})


def test_a_due_match_is_published(tmp_path):
    st = Store(LocalBackend(tmp_path))
    out = R.run(st, data(), FakeWriter(), NOW, fetch=lambda u: None)
    assert out["written"] == 1
    doc = st.get_json(f"news/a/r-{MD['id']}.json")
    assert doc["author"] == "تحرير تيفو" and doc["image"]["card"] and doc["match"] == MD["id"]
    lst = st.get_json("news/articles.json")["articles"]
    assert lst[0]["id"] == f"r-{MD['id']}"
    assert R.run(st, data(), FakeWriter(), NOW, fetch=lambda u: None)["written"] == 0       # done: not written twice


def test_a_failed_check_is_rewritten_once_then_dropped(tmp_path):
    st = Store(LocalBackend(tmp_path))
    w = FakeWriter(texts=["سجل 973 هدفاً.", "سجل 973 هدفاً."])
    out = R.run(st, data(), w, NOW, fetch=lambda u: None)
    assert out["written"] == 0 and len(w.calls) == 2 and w.calls[1]                      # the second call carries the failures
    assert st.get_state("articles/state.json")["reports"][str(MD["id"])]["status"] == "failed"


def test_api_errors_keep_the_match_due_three_times(tmp_path):
    st = Store(LocalBackend(tmp_path))
    for i in range(3):
        R.run(st, data(), FakeWriter(error=RuntimeError("529 overloaded")), NOW, fetch=lambda u: None)
    s = st.get_state("articles/state.json")["reports"][str(MD["id"])]
    assert s["tries"] == 3 and s["status"] == "failed"
    assert R.run(st, data(), FakeWriter(), NOW, fetch=lambda u: None)["written"] == 0


def test_a_thin_match_is_skipped_and_remembered(tmp_path):
    st = Store(LocalBackend(tmp_path))
    thin = copy.deepcopy(MD); thin["events"] = []; thin["stats"] = []; thin["lineups"] = {}
    w = FakeWriter()
    R.run(st, data(thin), w, NOW, fetch=lambda u: None)
    assert not w.calls and st.get_state("articles/state.json")["reports"][str(MD["id"])]["status"] == "thin"


def test_a_changed_match_is_written_again_under_the_same_id(tmp_path):
    st = Store(LocalBackend(tmp_path))
    R.run(st, data(), FakeWriter(), NOW, fetch=lambda u: None)
    md2 = copy.deepcopy(MD)
    g = next(e for e in md2["events"] if e["type"] in ("goal", "penalty_goal", "own_goal")); g["player"] = {"id": 1, "name": "X"}
    later = datetime(2026, 11, 16, 13, 0, tzinfo=timezone.utc)
    assert R.run(st, data(md2), FakeWriter(), later, fetch=lambda u: None)["written"] == 1
    doc = st.get_json(f"news/a/r-{MD['id']}.json")
    assert doc["modified"] > doc["published"] and doc["version"] == 2


def test_the_cap_and_the_switch_stop_everything(tmp_path, monkeypatch):
    st = Store(LocalBackend(tmp_path))
    st.put_state("articles/spend.json", {"2026-11": {"usd": 180.0, "calls": 1, "by_type": {}, "capped": True}})
    assert R.run(st, data(), FakeWriter(), NOW, fetch=lambda u: None)["written"] == 0
    monkeypatch.setattr(R, "TYPES", {"report": {"on": False, "model": "claude-sonnet-5-5", "words": [300, 400]}})
    assert R.run(Store(LocalBackend(tmp_path / "b")), data(), FakeWriter(), NOW, fetch=lambda u: None)["written"] == 0


# ---- final review, finding 1: a killed or crashed run must not lose its state or its spend
MD2 = json.loads((FX / "match_1000022237.json").read_text(encoding="utf-8"))
DAY2 = {"leagues": [{"id": 42, "matches": [{"id": MD["id"], "utc": "2026-11-16T10:00:00Z", "status": "finished",
                                            "home": [MD["home"]["id"], "", 2], "away": [MD["away"]["id"], "", 3]}]},
                    {"id": 538, "matches": [{"id": MD2["id"], "utc": "2026-11-16T11:00:00Z", "status": "finished",
                                             "home": [MD2["home"]["id"], "", 2], "away": [MD2["away"]["id"], "", 1]}]}]}


def data2(md_a=MD, md_b=MD2):
    files = {f"match/{md_a['id']}.json": md_a, f"match/{md_b['id']}.json": md_b, "all/20261116.json": DAY2, "all/20261115.json": {"leagues": []}}
    return lambda p: copy.deepcopy(files.get(p))


def test_one_bad_match_does_not_stop_the_others_or_lose_the_state(tmp_path, monkeypatch):
    st = Store(LocalBackend(tmp_path))
    real = R.photo.pick
    def pick(aid, md, *a, **k):
        if md["id"] == MD["id"]:
            raise RuntimeError("S3 503")
        return real(aid, md, *a, **k)
    monkeypatch.setattr(R.photo, "pick", pick)
    out = R.run(st, data2(), FakeWriter(), NOW, fetch=lambda u: None)
    reps = st.get_state("articles/state.json")["reports"]
    assert out["written"] == 1 and reps[str(MD2["id"])]["status"] == "done"
    assert reps[str(MD["id"])]["status"] == "retry" and "S3 503" in reps[str(MD["id"])]["error"]


def test_the_state_and_spend_are_saved_after_each_match(tmp_path):
    st = Store(LocalBackend(tmp_path))
    class Killed(FakeWriter):
        def write(self, kind, sheet, model, notes=None):
            if len(self.calls) == 1:
                raise KeyboardInterrupt          # the runner kills the process mid-run
            return super().write(kind, sheet, model, notes)
    with pytest.raises(KeyboardInterrupt):
        R.run(st, data2(), Killed(), NOW, fetch=lambda u: None)
    assert st.get_state("articles/state.json")["reports"][str(MD["id"])]["status"] == "done"
    assert st.get_state("articles/spend.json")["2026-11"]["calls"] == 1


def test_a_run_stops_starting_matches_after_its_time_budget(tmp_path):
    st = Store(LocalBackend(tmp_path))
    t = [0.0]
    def clock():
        t[0] += 100.0; return t[0]
    out = R.run(st, data2(), FakeWriter(), NOW, fetch=lambda u: None, budget=150, clock=clock)
    assert out["written"] == 1 and out["stopped"] == "time budget"
