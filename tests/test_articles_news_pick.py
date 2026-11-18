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
    assert N.near_duplicate(twin, ITEMS, recent, NOW) == "n-old"
    assert N.near_duplicate(twin, ITEMS, [dict(recent[0], anchor=[["team", -1]])], NOW) is None
    assert N.near_duplicate(TRANSFER, ITEMS, [dict(recent[0], id=f"n-{TRANSFER['id']}")], NOW) is None


def test_a_match_story_is_left_to_the_match_report():
    """«تعادل شباب الأهلي وكلباء 1-1» (live journal, 2026-11-19) is the match report's job; a second page on it is the
    near-duplicate pattern Google penalises (spec, «One page per match»)."""
    match = dict(TRANSFER, kind="match")
    assert not N.eligible(match, TEAMS, PTEAM, NOW)


# ---- final review, findings 2 and 3
def test_a_clubs_own_post_alone_is_news_only_when_it_announces_something_done():
    """classify.py makes every non-match post of an official account kind «official»: a birthday greeting from the club alone is
    not news; the same post carried by an outlet, or an official announcement, is."""
    items = {"o": {"source": "Club", "tier": "official", "title": "Happy birthday to our legend!"},
             "p": {"source": "Marca", "tier": "paper", "title": "El club felicita a su leyenda"},
             "d": {"source": "Club", "tier": "official", "title": "OFFICIAL: Club completes the signing of X"}}
    st = lambda *ids: dict(TRANSFER, kind="official", items=list(ids))
    assert not N.eligible(st("o"), TEAMS, PTEAM, NOW, items=items)
    assert N.eligible(st("o", "p"), TEAMS, PTEAM, NOW, items=items)
    assert N.eligible(st("d"), TEAMS, PTEAM, NOW, items=items)


def test_shared_names_alone_are_not_the_same_news_and_old_articles_do_not_count():
    """«الهلال يعلن تجديد عقد سالم الدوسري» is not «سالم الدوسري يقود الهلال للفوز»: the names are left out of the overlap.
    And an article older than a day never makes a new story a duplicate."""
    names = N.words("الهلال سالم الدوسري")
    s = {"id": "a", "anchor": [["team", 1]], "items": ["x"]}
    items = {"x": {"title": "الهلال يعلن تجديد عقد سالم الدوسري حتى 2029"}}
    other = [{"id": "n-b", "anchor": [["team", 1]], "words": sorted(N.words("سالم الدوسري يقود الهلال للفوز") - names), "at": NOW.isoformat()}]
    assert N.near_duplicate(s, items, other, NOW, names) is None
    same = [{"id": "n-c", "anchor": [["team", 1]], "words": sorted(N.words("الهلال يعلن رسمياً تجديد عقد الدوسري حتى 2029") - names), "at": NOW.isoformat()}]
    assert N.near_duplicate(s, items, same, NOW, names) == "n-c"
    old = [dict(same[0], at="2020-01-01T00:00:00+00:00")]
    assert N.near_duplicate(s, items, old, NOW, names) is None
