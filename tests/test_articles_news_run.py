# tests/test_articles_news_run.py
"""The news pass end to end with a LocalBackend, a fake writer and fake sources."""
import copy, json
from datetime import datetime, timedelta
from pathlib import Path
import pytest
from store import Store, LocalBackend
from news.articles import news_run as NR, spend

S = json.loads((Path(__file__).parent / "fixtures" / "articles" / "news_state.json").read_text(encoding="utf-8"))
TRANSFER = list(S["stories"].values())[0]
SMALL_ID = list(S["stories"])[2]
ANCH = [e for s in S["stories"].values() for e in s["anchor"]]
TEAMS = {"teams": {"1": {"comps": [47]}, **{str(i): {"comps": [47]} for k, i in ANCH if k == "team"}}}
PTEAM = {str(i): 1 for k, i in ANCH if k == "player"}
NOW = datetime.fromisoformat(TRANSFER["last_at"].replace("Z", "+00:00"))
TEXTS = [{"source": "Club", "lang": "en", "url": "u", "tier": "official", "text": "Official text.", "image": None}]


class W:
    def __init__(self): self.calls = []
    def write(self, kind, sheet, model, notes=None):
        self.calls.append((sheet["النوع"], model))
        n = 120 if sheet["النوع"] == "عاجل" else 300
        return ({"headline": "عنوان", "standfirst": "مقدمة", "sections": [{"subhead": "ق", "paragraphs": ["كلمة " * n]}], "facts_box": [], "sources_cited": []},
                {"in": 4000, "out": 1500, "cache_read": 0, "cache_write": 0})
    def pick_photo(self, headline, thumbs):
        self.calls.append(("photo", len(thumbs)))
        return 0, {"in": 900, "out": 10, "cache_read": 0, "cache_write": 0}


@pytest.fixture(autouse=True)
def on(monkeypatch):
    monkeypatch.setattr(NR, "TYPES", {"news": {"on": True, "model": "claude-sonnet-5-5", "words": [250, 450], "daily": 60, "wait_minutes": 20},
                                      "breaking": {"on": True, "model": "claude-haiku-5-5", "words": [80, 160]}})


def go(st, now, w, j=None):
    return NR.run_news(st, j or {"stories": S["stories"], "items": S["items"], "pteam": PTEAM}, lambda p: None, w, now,
                       spend.Spend(st, now), deadline=1e12, clock=lambda: 0.0,
                       collect=lambda *a, **k: (TEXTS, {"links": 0, "decoded": 0, "texts": 0}), fetch=lambda u: None,
                       teams_json=TEAMS, ar={}, commons=lambda q: [])


def official_story(title, kind):
    """The transfer story alone, its first item an official account's post with this headline, its others not official."""
    s, items = copy.deepcopy(TRANSFER), copy.deepcopy(S["items"])
    s["kind"] = kind
    items[s["items"][0]].update({"tier": "official", "title": title, "desc": title})   # an official post: its text is its title
    for i in s["items"][1:]:
        if i in items:
            items[i]["tier"] = "paper"
    return s, {"stories": {s["id"]: s}, "items": items, "pteam": PTEAM}


def test_a_story_is_queued_then_written_by_sonnet_after_twenty_minutes(tmp_path, monkeypatch):
    monkeypatch.setattr(NR, "breaking", lambda s, items: False)
    st, w = Store(LocalBackend(tmp_path)), W()
    assert go(st, NOW, w)["written"] == 0
    assert go(st, NOW + timedelta(minutes=25), w)["written"] >= 1
    doc = st.get_json(f"news/a/n-{TRANSFER['id']}.json")
    assert doc["kind"] == "news" and doc["breaking"] is False and ("خبر", "claude-sonnet-5-5") in w.calls


def test_an_official_signing_goes_out_at_once_as_breaking_by_haiku(tmp_path):
    st, w = Store(LocalBackend(tmp_path)), W()
    s, j = official_story("Official: the club completes the signing", "transfer")
    assert go(st, NOW, w, j)["breaking"] == 1
    assert w.calls == [("عاجل", "claude-haiku-5-5")] and st.get_json(f"news/a/n-{s['id']}.json")["breaking"] is True
    assert st.get_json("news/articles.json")["articles"][0]["breaking"] is True


def test_a_birthday_post_from_an_official_account_is_not_breaking(tmp_path):
    st, w = Store(LocalBackend(tmp_path)), W()
    _, j = official_story("Happy birthday to our legend!", "official")            # what classify.py makes of it
    assert go(st, NOW, w, j)["breaking"] == 0 and w.calls == []


def test_withdraw_from_the_desk_takes_an_article_off_for_good(tmp_path, monkeypatch):
    monkeypatch.setattr(NR, "breaking", lambda s, items: False)
    st, w = Store(LocalBackend(tmp_path)), W()
    go(st, NOW, w); go(st, NOW + timedelta(minutes=25), w)
    aid = f"n-{TRANSFER['id']}"
    st.put_state("articles/desk.json", {"withdraw": {aid: NOW.isoformat()}})
    assert go(st, NOW + timedelta(minutes=30), w)["withdrawn"] == 1
    assert aid not in [a["id"] for a in st.get_json("news/articles-all.json")["articles"]]
    grown = copy.deepcopy(S["stories"]); grown[TRANSFER["id"]]["stage"] = "official"   # the story grows: no rewrite
    go(st, NOW + timedelta(hours=2), w, {"stories": grown, "items": S["items"], "pteam": PTEAM})
    assert aid not in [a["id"] for a in st.get_json("news/articles-all.json")["articles"]]


def test_one_failing_story_does_not_stop_the_others(tmp_path, monkeypatch):
    """A story whose sheet or photo raises is counted as failed; the pass goes on and saves (dry run 2026-11-19: a player file
    in an unexpected shape stopped the whole pass)."""
    monkeypatch.setattr(NR, "breaking", lambda s, items: False)
    st, w = Store(LocalBackend(tmp_path)), W()
    def collect(s, items):
        if s["id"] == TRANSFER["id"]:
            raise AttributeError("'int' object has no attribute 'get'")
        return TEXTS, {"links": 0, "decoded": 0, "texts": 0}
    go(st, NOW, w)
    out = NR.run_news(st, {"stories": S["stories"], "items": S["items"], "pteam": PTEAM}, lambda p: None, w, NOW + timedelta(minutes=25),
                      spend.Spend(st, NOW), deadline=1e12, clock=lambda: 0.0, collect=collect, fetch=lambda u: None,
                      teams_json=TEAMS, ar={}, commons=lambda q: [])
    assert out["failed"] >= 1 and out["written"] >= 1
    assert st.get_json(f"news/a/n-{TRANSFER['id']}.json") is None


# ---- final review
class Short(W):
    """A writer whose every article fails the length check."""
    def write(self, kind, sheet, model, notes=None):
        self.calls.append((sheet["النوع"], model))
        return ({"headline": "ع", "standfirst": "م", "sections": [{"subhead": "ق", "paragraphs": ["قصير"]}], "facts_box": [], "sources_cited": []},
                {"in": 4000, "out": 100, "cache_read": 0, "cache_write": 0})


def alone(story=TRANSFER, **kw):
    s = dict(copy.deepcopy(story), **kw)
    return {"stories": {s["id"]: s}, "items": S["items"], "pteam": PTEAM}


def test_a_story_that_fails_is_not_rewritten_every_run(tmp_path, monkeypatch):
    """Finding 1: a story failing twice was popped and re-offered, due again 20 minutes later: 64 calls a day."""
    monkeypatch.setattr(NR, "breaking", lambda s, items: False)
    st, w = Store(LocalBackend(tmp_path)), Short()
    for m in range(0, 24 * 60, 15):
        go(st, NOW + timedelta(minutes=m), w, alone())
    assert len(w.calls) == 2                                        # one try: the article and its one rewrite


def test_a_kit_announcement_is_not_breaking(tmp_path):
    """Finding 7: «OFFICIAL: our new home kit» passes classify.official(); «عاجل» is for a signing, a sacking, an injury or
    a sanction (spec, type 8)."""
    st, w = Store(LocalBackend(tmp_path)), W()
    _, j = official_story("OFFICIAL: our new home kit for 2027 is here", "official")
    assert go(st, NOW, w, j)["breaking"] == 0


def test_breaking_stops_at_fifteen_a_day(tmp_path):
    st, w = Store(LocalBackend(tmp_path)), W()
    st.put_state("articles/state.json", {"news": {"breaking_day": NR.desk_queue.Queue({}, {}, NOW, {"daily": 60, "wait_minutes": 20}).n["day"], "breaking_count": 15}})
    _, j = official_story("Official: the club completes the signing", "transfer")
    assert go(st, NOW, w, j)["breaking"] == 0


def test_two_halves_of_one_story_in_one_run_make_one_article(tmp_path, monkeypatch):
    """Finding 3: the duplicate check ran only when stories were offered, so two halves offered together were both written."""
    monkeypatch.setattr(NR, "breaking", lambda s, items: False)
    st, w = Store(LocalBackend(tmp_path)), W()
    a = copy.deepcopy(TRANSFER); b = dict(copy.deepcopy(TRANSFER), id="twin")
    j = {"stories": {a["id"]: a, "twin": b}, "items": S["items"], "pteam": PTEAM}
    go(st, NOW, w, j)
    out = go(st, NOW + timedelta(minutes=25), w, j)
    assert out["written"] == 1 and out["dupes"] >= 1


def test_a_story_out_of_time_before_its_rewrite_waits_for_the_next_run(tmp_path, monkeypatch):
    """Finding 6: no second attempt is started past the deadline; the story stays queued, not failed."""
    monkeypatch.setattr(NR, "breaking", lambda s, items: False)
    st, t = Store(LocalBackend(tmp_path)), [0.0]
    class Slow(Short):
        def write(self, *a, **k):
            t[0] = 1000.0                                           # the first attempt takes the run past its deadline
            return super().write(*a, **k)
    w = Slow()
    go(st, NOW, w, alone())
    out = NR.run_news(st, alone(), lambda p: None, w, NOW + timedelta(minutes=25), spend.Spend(st, NOW), deadline=10.0,
                      clock=lambda: t[0], collect=lambda *a, **k: (TEXTS, {"links": 0, "decoded": 0, "texts": 0}),
                      fetch=lambda u: None, teams_json=TEAMS, ar={}, commons=lambda q: [])
    assert len(w.calls) == 1 and out["failed"] == 0
    assert TRANSFER["id"] in st.get_state("articles/state.json")["news"]["queue"]


def test_the_cap_email_goes_when_the_news_pass_crosses_it(tmp_path, monkeypatch):
    """Finding 4: only the reports' pass sent the email; news, most of the spend, would cross the cap silently."""
    from news.articles import run as R
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(R, "run", lambda *a, **k: {})
    monkeypatch.setattr(R.write, "Writer", lambda *a, **k: None)
    def news(store, journal, data_get, writer, now, sp, **kw):
        sp.add("claude-sonnet-5-5", {"in": 0, "out": 20_000_000, "cache_read": 0, "cache_write": 0}, "news"); return {}
    monkeypatch.setattr(NR, "run_news", news)
    sent = []
    monkeypatch.setattr(R, "_mail_cap", lambda total: sent.append(total))
    assert R.main(["--local", str(tmp_path)]) == 0 and sent and sent[0] >= 180


# ---- Phase 2b: the desk
def test_the_desk_view_shows_each_story_its_state_and_when_it_is_due(tmp_path, monkeypatch):
    monkeypatch.setattr(NR, "breaking", lambda s, items: False)
    st, w = Store(LocalBackend(tmp_path)), W()
    go(st, NOW, w)
    view = st.get_state("articles/desk-view.json")
    row = next(r for r in view["stories"] if r["id"] == TRANSFER["id"])
    assert row["status"] == "queued" and row["due"] == (NOW + timedelta(minutes=20)).isoformat()
    assert row["title"] and row["outlets"] >= 3 and row["kind"] == "transfer" and view["daily"] == 60
    assert all(r["id"] != list(S["stories"])[1] for r in view["stories"])            # «other»: never a candidate
    go(st, NOW + timedelta(minutes=25), w)
    row = next(r for r in st.get_state("articles/desk-view.json")["stories"] if r["id"] == TRANSFER["id"])
    assert row["status"] == "written" and row["article"] == f"n-{TRANSFER['id']}"
    st.put_state("articles/desk.json", {"reject": {SMALL_ID: NOW.isoformat()}})
    go(st, NOW + timedelta(minutes=26), w)
    rows = {r["id"]: r for r in st.get_state("articles/desk-view.json")["stories"]}
    assert SMALL_ID not in rows or rows[SMALL_ID]["status"] in ("rejected", "written")


def test_each_article_keeps_its_sheet_and_photo_candidates_for_the_desk(tmp_path, monkeypatch):
    monkeypatch.setattr(NR, "breaking", lambda s, items: False)
    st, w = Store(LocalBackend(tmp_path)), W()
    go(st, NOW, w); go(st, NOW + timedelta(minutes=25), w)
    kept = st.get_state(f"articles/sheets/n-{TRANSFER['id']}.json")
    assert kept["sheet"]["النوع"] == "خبر" and "photos" in kept


def test_an_article_the_owner_edited_is_never_rewritten_and_its_growth_is_flagged(tmp_path, monkeypatch):
    """Spec, «The desk»: an article he edited is never rewritten automatically; when its story gains new facts, the desk shows
    them to him instead."""
    monkeypatch.setattr(NR, "breaking", lambda s, items: False)
    st, w = Store(LocalBackend(tmp_path)), W()
    go(st, NOW, w); go(st, NOW + timedelta(minutes=25), w)
    aid = f"n-{TRANSFER['id']}"
    doc = st.get_json(f"news/a/{aid}.json"); doc.update(headline="عنوان المحرر", edited=True); st.put_json(f"news/a/{aid}.json", doc)
    grown = copy.deepcopy(S["stories"]); grown[TRANSFER["id"]]["stage"] = "official"
    calls = len(w.calls)
    go(st, NOW + timedelta(hours=2), w, {"stories": grown, "items": S["items"], "pteam": PTEAM})
    assert len(w.calls) == calls and st.get_json(f"news/a/{aid}.json")["headline"] == "عنوان المحرر"
    row = next(r for r in st.get_state("articles/desk-view.json")["stories"] if r["id"] == TRANSFER["id"])
    assert row["grew"] is True


def test_a_news_article_carries_its_storys_kind_and_stage(tmp_path, monkeypatch):
    monkeypatch.setattr(NR, "breaking", lambda s, items: False)
    st, w = Store(LocalBackend(tmp_path)), W()
    go(st, NOW, w); go(st, NOW + timedelta(minutes=25), w)
    doc = st.get_json(f"news/a/n-{TRANSFER['id']}.json")
    assert doc["topic"] == TRANSFER["kind"] and doc["stage"] == TRANSFER.get("stage")
    row = next(a for a in st.get_json("news/articles.json")["articles"] if a["id"] == doc["id"])
    assert row["topic"] == TRANSFER["kind"] and "stage" in row
