# tests/test_articles_news_pick.py
"""news/articles/news_pick.py on a real slice of the journal (tests/fixtures/articles/news_state.json)."""
import copy, json
from datetime import datetime, timezone
from pathlib import Path
from news.articles import news_pick as N

S = json.loads((Path(__file__).parent / "fixtures" / "articles" / "news_state.json").read_text(encoding="utf-8"))
ITEMS = S["items"]
TRANSFER, OTHER, SMALL = S["stories"].values()
ANCH = [e for s in S["stories"].values() for e in s["anchor"]]
TEAMS = {"1": {"comps": [47]}, **{str(i): {"comps": [47]} for k, i in ANCH if k == "team"}}     # all: Premier League
PTEAM = {str(i): 1 for k, i in ANCH if k == "player"}
NOW = datetime.fromisoformat(TRANSFER["last_at"].replace("Z", "+00:00"))


def test_other_is_never_written_and_a_story_must_name_a_priority_club():
    assert N.eligible(TRANSFER, TEAMS, PTEAM, NOW)
    assert not N.eligible(OTHER, TEAMS, PTEAM, NOW)
    assert not N.eligible(TRANSFER, {k: {"comps": [999999]} for k in TEAMS}, {}, NOW)


def test_a_story_older_than_a_day_is_not_eligible():
    assert not N.eligible(TRANSFER, TEAMS, PTEAM, datetime(2030, 1, 1, tzinfo=timezone.utc))


def test_more_outlets_rank_first():
    assert N.rank_key(TRANSFER, ITEMS, TEAMS) > N.rank_key(SMALL, ITEMS, TEAMS)


def test_the_same_news_as_a_second_story_is_a_near_duplicate_but_not_of_itself():
    title = ITEMS[TRANSFER["items"][0]]["title"]
    recent = [{"id": "n-old", "anchor": TRANSFER["anchor"], "words": sorted(N.words(title)), "at": TRANSFER["last_at"]}]
    twin = copy.deepcopy(TRANSFER); twin["id"] = "twin"
    assert N.near_duplicate(twin, ITEMS, recent) == "n-old"
    assert N.near_duplicate(twin, ITEMS, [dict(recent[0], anchor=[["team", -1]])]) is None
    assert N.near_duplicate(TRANSFER, ITEMS, [dict(recent[0], id=f"n-{TRANSFER['id']}")]) is None
