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
    items[s["items"][0]].update({"tier": "official", "title": title})
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
