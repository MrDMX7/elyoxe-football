"""The article's own label (owner 2026-11-19: Getafe's stadium works went out as «انتقالات · إشاعة»): the chip on an article is
what Haiku reads in the finished article, not the journal's keyword guess about the story. A stage only for a transfer."""
import json, types
from datetime import datetime, timezone

import pytest

from news.articles import write as WR, relabel as RL
from store import Store, LocalBackend
from test_articles_news_check_photo import FakeClient

ART = {"headline": "خيتافي يستثمر 45 مليون يورو لتوسيع الكوليسيوم", "standfirst": "قال المدير العام لخيتافي إن النادي سيوسّع ملعب الكوليسيوم.",
       "sections": [{"subhead": "", "paragraphs": ["الأعمال تنتهي في 2027."]}]}


def test_label_reads_the_article_and_keeps_a_stage_for_transfers_only():
    c = FakeClient({"topic": "other", "stage": "rumour"})
    topic, stage, usage = WR.Writer(c).label(ART)
    assert (topic, stage) == ("other", None) and usage["in"] == 900
    kw = c.calls[0]
    assert kw["model"] == "claude-haiku-5-5" and kw["output_config"]["format"]["schema"] == WR.Writer.LABEL_SCHEMA
    text = kw["messages"][0]["content"]
    assert ART["headline"] in text and ART["standfirst"] in text and "الأعمال تنتهي في 2027." in text
    assert WR.Writer(FakeClient({"topic": "transfer", "stage": "official"})).label(ART)[:2] == ("transfer", "official")
    assert WR.Writer(FakeClient({"topic": "transfer", "stage": "none"})).label(ART)[:2] == ("transfer", None)


def test_an_unreadable_label_is_an_error():
    with pytest.raises(WR.WriteError):
        WR.Writer(FakeClient({"topic": "gossip", "stage": "none"})).label(ART)


class Labeller:
    def __init__(self, answers):
        self.answers, self.seen = answers, []

    def label(self, art, model="claude-haiku-5-5"):
        self.seen.append(art["headline"])
        a = self.answers[art["headline"]]
        if isinstance(a, Exception):
            raise a
        return a[0], a[1], {"in": 500, "out": 9, "cache_read": 0, "cache_write": 0}


class Spend:
    def __init__(self):
        self.added = []

    def add(self, model, usage, what):
        self.added.append((model, what))

    def allowed(self):
        return True

    def save(self):
        pass


def doc(aid, headline, topic, stage=None, **kw):
    return dict({"id": aid, "kind": "news", "headline": headline, "standfirst": "س", "sections": [{"subhead": "", "paragraphs": ["ف"]}],
                 "topic": topic, "stage": stage, "published": "2026-11-19T00:00:00+00:00", "modified": "m-" + aid}, **kw)


def test_the_backfill_labels_live_articles_once_and_rerenders_the_pages(tmp_path):
    st = Store(LocalBackend(tmp_path))
    docs = [doc("n-1", "خيتافي يوسع ملعبه", "transfer", "rumour"), doc("n-2", "غولر يمدد رسمياً", "transfer", "rumour"),
            doc("n-3", "تقرير", "report", kind="report"), doc("n-4", "فشل", "statement"), doc("n-5", "تم", "injury", labelled=1)]
    for d in docs:
        st.put_json(f"news/a/{d['id']}.json", d)
    st.put_json("news/articles.json", {"articles": [{k: d.get(k) for k in ("id", "kind", "headline", "topic", "stage", "modified")} for d in docs]})
    st.put_json("news/articles-all.json", {"articles": [{"id": d["id"], "kind": d["kind"], "modified": d["modified"]} for d in docs]})
    st.put_state("articles/pages.json", {"built": "k1", "pages": {"n-1": "m-n-1"}})
    w = Labeller({"خيتافي يوسع ملعبه": ("other", None), "غولر يمدد رسمياً": ("transfer", "official"), "فشل": RuntimeError("api")})
    sp = Spend()
    out = RL.run(st, w, sp, deadline=1e12, clock=lambda: 0.0)
    assert out == {"labelled": 2, "failed": 1, "left": 1}
    assert sorted(w.seen) == ["خيتافي يوسع ملعبه", "غولر يمدد رسمياً", "فشل"]                    # never a report, never twice
    d1 = st.get_json("news/a/n-1.json")
    assert (d1["topic"], d1["stage"], d1["labelled"], d1["modified"]) == ("other", None, 1, "m-n-1")
    assert st.get_json("news/a/n-2.json")["stage"] == "official" and "labelled" not in st.get_json("news/a/n-4.json")
    lst = {a["id"]: a for a in st.get_json("news/articles.json")["articles"]}
    assert (lst["n-1"]["topic"], lst["n-1"]["stage"]) == ("other", None) and lst["n-2"]["stage"] == "official"
    assert st.get_state("articles/pages.json")["built"] is None                              # the fast step re-renders every page
    assert sp.added == [("claude-haiku-5-5", "label"), ("claude-haiku-5-5", "label")]
    w2 = Labeller({"فشل": ("statement", None)})
    assert RL.run(st, w2, sp, deadline=1e12, clock=lambda: 0.0) == {"labelled": 1, "failed": 0, "left": 0} and w2.seen == ["فشل"]


def test_the_backfill_stops_at_its_limit_and_its_deadline(tmp_path):
    st = Store(LocalBackend(tmp_path))
    docs = [doc(f"n-{i}", f"خبر {i}", "transfer", "rumour") for i in range(5)]
    for d in docs:
        st.put_json(f"news/a/{d['id']}.json", d)
    st.put_json("news/articles.json", {"articles": [{"id": d["id"], "kind": "news", "topic": "transfer"} for d in docs]})
    st.put_json("news/articles-all.json", {"articles": [{"id": d["id"], "kind": "news"} for d in docs]})
    w = Labeller({f"خبر {i}": ("injury", None) for i in range(5)})
    assert RL.run(st, w, Spend(), deadline=1e12, clock=lambda: 0.0, limit=2)["labelled"] == 2
    t = iter([0.0, 99.0, 99.0, 99.0, 99.0])
    assert RL.run(st, w, Spend(), deadline=50.0, clock=lambda: next(t))["labelled"] == 1


def test_the_label_has_room_to_answer_and_says_why_it_stopped():
    """2026-11-19, first live run: 28 of 60 labels came back with no text at all (max_tokens was 100)."""
    c = FakeClient({"topic": "other", "stage": "none"})
    WR.Writer(c).label(ART)
    assert c.calls[0]["max_tokens"] >= 1024
    empty = types.SimpleNamespace(messages=types.SimpleNamespace(create=lambda **kw: types.SimpleNamespace(
        stop_reason="max_tokens", content=[], usage=types.SimpleNamespace(input_tokens=1, output_tokens=1))))
    with pytest.raises(WR.WriteError, match="max_tokens"):
        WR.Writer(empty).label(ART)
