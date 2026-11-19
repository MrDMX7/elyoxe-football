"""news/articles/push_jobs.py (spec 2026-11-19 §4): a push job for each article first put up in this run, to the followers of
every club and player in it, only for an article published in the last 3 hours, and never a backlog on the first run."""
from datetime import datetime, timedelta, timezone

from news.articles import push_jobs as PJ

NOW = datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)


def doc(aid, mins_ago=5, ents=(("team", 8634), ("player", 15403)), breaking=False, sf="مقدمة الخبر"):
    return {"id": aid, "headline": f"عنوان {aid}", "standfirst": sf, "entities": [list(e) for e in ents], "breaking": breaking,
            "published": (NOW - timedelta(minutes=mins_ago)).isoformat()}


def test_one_job_per_new_article_to_its_clubs_and_players():
    [j] = PJ.jobs([doc("n-1")], {"n-old": "x"}, NOW)
    assert j["match"] == "article:n-1" and j["key"] == "article" and j["kind"] == "article" and j["urgency"] == "normal"
    assert j["exp"] == int(NOW.timestamp()) + 3 * 3600 and set(j["payloads"]) == {"8634", "P15403"}
    p = j["payloads"]["8634"]
    assert p == {"title": "عنوان n-1", "body": "مقدمة الخبر", "url": "/news/n-1/", "tag": "art-n-1", "kind": "article", "team": 8634}
    assert "team" not in j["payloads"]["P15403"]


def test_only_first_publication_recent_and_never_on_an_empty_state():
    known = {"n-2": "m"}
    assert PJ.jobs([doc("n-2")], known, NOW) == []                                     # rewritten or edited: put up before
    assert PJ.jobs([doc("n-3", mins_ago=200)], known, NOW) == []                       # over 3 hours old
    assert PJ.jobs([doc("n-4", ents=())], known, NOW) == []                            # nobody to tell
    assert PJ.jobs([doc("n-5")], {}, NOW) == []                                        # the first run: no backlog of pushes


def test_breaking_is_urgent_and_first_the_body_is_cut_and_twenty_a_run_at_most():
    long = "كلمة " * 60
    docs = [doc(f"n-{i}", mins_ago=i) for i in range(30)] + [doc("b-1", mins_ago=50, breaking=True, sf=long)]
    js = PJ.jobs(docs, {"x": 1}, NOW)
    assert len(js) == 20 and js[0]["match"] == "article:b-1" and js[0]["urgency"] == "high"
    body = js[0]["payloads"]["8634"]["body"]
    assert len(body) <= 121 and body.endswith("…") and not body.endswith(" …")
    assert [j["match"] for j in js[1:4]] == ["article:n-0", "article:n-1", "article:n-2"]  # then the newest
