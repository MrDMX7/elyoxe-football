"""Merge items that tell the same story into one: the same event reported by BBC, Marca and البيان is one card that
lists every outlet, shows who had it first, and carries the furthest transfer stage any of them reached.

Two items are the same story when they are of the same kind, within 48 hours of each other, and share the story's
people: the same player (or coach), or the same pair of clubs. A story with no linked entity is not merged (and not
published: news/run.py shows only stories it can put on a club, player or coach page)."""
import hashlib
from datetime import datetime, timedelta
from .classify import STAGE_RANK

WINDOW = timedelta(hours=48)
TIER_RANK = {"official": 3, "journalist": 2, "paper": 1, "aggregator": 0}


def _t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def _key_people(ents):
    return {tuple(e) for e in ents if e[0] in ("player", "coach")}


def _key_teams(ents):
    return {tuple(e) for e in ents if e[0] == "team"}


def _words(title):
    from .entities import norm
    return {w for w in norm(title).split() if len(w) > 3}


def same_story(story, item):
    """Merged on the ANCHOR (who the headline names), never on names that only appear in a description: a story
    about Félix that mentions Ronaldo in passing must not swallow every Ronaldo story of the week. General news
    («other», «match», «statement») also needs similar headlines in the same language."""
    if story["kind"] != item["kind"] or not item.get("anchor"):
        return False
    a, b = _t(story["last_at"]), _t(item["at"])
    if a and b and abs(a - b) > WINDOW:
        return False
    sp, ip = _key_people(story["anchor"]), _key_people(item["anchor"])
    st, it = _key_teams(story["anchor"]), _key_teams(item["anchor"])
    if sp or ip:
        same = bool(sp & ip) and (not st or not it or bool(st & it))
    else:
        same = len(st & it) >= 2 or (len(st) == 1 and st == it and story["kind"] in ("official", "presser", "injury"))
    if same and story["kind"] in ("other", "match", "statement"):
        w = _words(item["title"])
        near = [x for x in story.get("titles", []) if x["lang"] == item["lang"]]
        same = any(len(w & set(x["w"])) / max(1, len(w | set(x["w"]))) >= 0.3 for x in near)
    return same


def new_story(item):
    sid = hashlib.sha1(("s" + item["id"]).encode()).hexdigest()[:14]
    return {"id": sid, "kind": item["kind"], "stage": item.get("stage"), "here_we_go": item.get("here_we_go", False),
            "entities": [list(e) for e in item["entities"]], "anchor": [list(e) for e in item.get("anchor") or []], "titles": [],
            "items": [], "first_at": item["at"], "last_at": item["at"],
            "image": None, "summary": None, "summary_items": 0}


def add(story, item):
    if item["id"] in story["items"]:
        return False
    story["items"].append(item["id"])
    ents = {tuple(e) for e in story["entities"]} | {tuple(e) for e in item["entities"]}
    story["entities"] = [list(e) for e in sorted(ents)]
    anc = {tuple(e) for e in story.get("anchor") or []} | {tuple(e) for e in item.get("anchor") or []}
    story["anchor"] = [list(e) for e in sorted(anc)]
    story.setdefault("titles", []).append({"lang": item["lang"], "w": sorted(_words(item["title"]))})
    story["titles"] = story["titles"][-12:]
    if item.get("at"):
        if not story["first_at"] or item["at"] < story["first_at"]:
            story["first_at"] = item["at"]
        if not story["last_at"] or item["at"] > story["last_at"]:
            story["last_at"] = item["at"]
    if STAGE_RANK.get(item.get("stage"), -1) > STAGE_RANK.get(story.get("stage"), -1):
        story["stage"] = item["stage"]
    story["here_we_go"] = story.get("here_we_go") or item.get("here_we_go", False)
    story["image"] = story.get("image") or item.get("image")
    return True


def assign(stories, items):
    """Put each new item into a matching story (newest stories first) or a new one. Returns the stories touched."""
    touched = {}
    open_ = sorted(stories.values(), key=lambda s: s["last_at"] or "", reverse=True)
    for it in sorted(items, key=lambda i: i.get("at") or ""):
        if not it.get("anchor"):              # a story needs someone in its headline to belong to
            continue
        home = next((s for s in open_ if same_story(s, it)), None)
        if home is None:
            home = new_story(it)
            stories[home["id"]] = home
            open_.insert(0, home)
        if add(home, it):
            touched[home["id"]] = home
    return touched


def sources_of(story, items_by_id):
    """The story's outlets, earliest first, one line per outlet (its earliest item)."""
    seen, out = set(), []
    for it in sorted((items_by_id[i] for i in story["items"] if i in items_by_id), key=lambda i: i.get("at") or ""):
        if it["source"] in seen:
            continue
        seen.add(it["source"])
        out.append({"name": it["source"], "url": it["url"], "lang": it["lang"], "tier": it["tier"], "at": it["at"], "title": it["title"]})
    return out


def reliability(sources):
    return max((TIER_RANK.get(s["tier"], 0) for s in sources), default=0)
