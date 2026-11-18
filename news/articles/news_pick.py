"""Which journal stories become news articles (spec, «A news story is big enough»):
- it names a club or player of a priority competition, or an Arab national team;
- it is any kind but «other» and «match» (a match is the match report's: a second page on it is the near-duplicate
  pattern Google penalises), seen in the last 24 hours.
Biggest first: most outlets, then an official source, then the size of the club (the big five and the Champions League,
then the Arab leagues), then the newest.
The journal's clusters can split one news item into two stories. The second is caught by its first headline's words,
against the last day's articles on the same club or player."""
from datetime import datetime, timedelta
from . import priority

BIG = {47, 87, 55, 54, 53, 42}
ARAB = {538, 536, 535, 519, 530, 525}
TIER = {"official": 3, "journalist": 2, "paper": 1, "aggregator": 0}


def _at(s):
    return datetime.fromisoformat((s or "1970-01-01T00:00:00+00:00").replace("Z", "+00:00"))


def words(text):
    from news.entities import norm
    return {w for w in norm(text or "").split() if len(w) > 3}


def _teams_of(story, pteam):
    out = {int(e[1]) for e in story.get("anchor") or [] if e[0] == "team"}
    out |= {int(pteam[str(e[1])]) for e in story.get("anchor") or [] if e[0] == "player" and str(e[1]) in pteam}
    return out


def eligible(story, teams, pteam, now):
    if story.get("kind") in (None, "other", "match") or not story.get("anchor"):
        return False
    if _at(story.get("last_at")) < now - timedelta(hours=24):
        return False
    pri, arab = priority.priority_comps(), priority.arab_teams()
    return any(t in arab or set((teams.get(str(t)) or {}).get("comps") or []) & pri for t in _teams_of(story, pteam))


def rank_key(story, items, teams):
    its = [items[i] for i in story.get("items") or [] if i in items]
    comps = set()
    for e in story.get("anchor") or []:
        if e[0] == "team":
            comps |= set((teams.get(str(e[1])) or {}).get("comps") or [])
    return [len({i.get("source") for i in its}), max((TIER.get(i.get("tier"), 0) for i in its), default=0),
            2 if comps & BIG else 1 if comps & ARAB else 0, _at(story.get("last_at")).timestamp()]


def near_duplicate(story, items, recent):
    first = next((items[i] for i in story.get("items") or [] if i in items), None)
    if not first:
        return None
    w, anc, own = words(first.get("title")), {tuple(e) for e in story.get("anchor") or []}, f"n-{story['id']}"
    for r in recent:
        if r["id"] == own or not anc & {tuple(e) for e in r.get("anchor") or []}:
            continue
        rw = set(r.get("words") or [])
        if w and rw and len(w & rw) / min(len(w), len(rw)) >= 0.6:
            return r["id"]
    return None
