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

# «عاجل» is for a signing, a sacking, an injury or a sanction (spec, type 8). classify.official() also passes «OFFICIAL: our new
# home kit» (final review, finding 7), so the announcement must name one of these. Stems, matched in news.entities.norm form.
EVENT = ["sign", "join", "contract", "extend", "extension", "renew", "loan", "transfer", "sack", "dismiss", "part ways",
         "parted ways", "relieved", "appoint", "head coach", "manager", "injur", "ruled out", "surgery", "suspen", "ban ", "banned",
         "fined", "sanction", "ficha", "contrato", "renueva", "renovacion", "cesado", "destitu", "nuevo entrenador", "lesion",
         "sancion", "signe", "prolong", "limoge", "blessure", "unterschreibt", "verlanger", "verletz", "firma", "rinnov", "esoner",
         "infortun", "squalific", "تعاقد", "التعاقد", "يضم", "ضم اللاعب", "تجديد", "تمديد", "يوقع", "وقع", "ينضم", "انضمام",
         "اعاره", "اقاله", "يقيل", "فك الارتباط", "انهاء", "انفصال", "مدرب جديد", "تعيين", "اصابه", "مصاب", "جراحه", "ايقاف",
         "غرامه", "عقوبه"]

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


def announced(story, items):
    """An official account's post in the story says something is done (classify.official: «OFFICIAL: …», «رسمياً…»)."""
    from news import classify as CL
    return any((items.get(i) or {}).get("tier") == "official" and CL.official((items.get(i) or {}).get("title"))
               for i in story.get("items") or [])


def event(story, items):
    """An official post of the story names a signing, a sacking, an injury or a sanction."""
    from news.entities import norm
    stems = [norm(w) for w in EVENT]
    for i in story.get("items") or []:
        it = items.get(i) or {}
        if it.get("tier") == "official":
            t = " " + norm(f"{it.get('title') or ''} {it.get('desc') or ''}") + " "
            if any(w in t for w in stems):
                return True
    return False


def eligible(story, teams, pteam, now, items=None):
    if story.get("kind") in (None, "other", "match") or not story.get("anchor"):
        return False
    # classify.py makes every non-match post of an official account kind «official», a birthday greeting too (final review,
    # finding 2): a club's own posts alone are news only when they announce something done; an outlet carrying it is news.
    if items is not None and story.get("kind") == "official":
        its = [items[i] for i in story.get("items") or [] if i in items]
        if its and all(i.get("tier") == "official" for i in its) and not announced(story, items):
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


def near_duplicate(story, items, recent, now, names=frozenset()):
    """recent: the last articles, {"id", "anchor", "words", "at"}, their words without names. Names alone never make two
    headlines the same news («الهلال يعلن تجديد عقد سالم الدوسري» is not «سالم الدوسري يقود الهلال للفوز»: final review,
    finding 3), and only the last 24 hours count."""
    first = next((items[i] for i in story.get("items") or [] if i in items), None)
    if not first:
        return None
    w, anc, own = words(first.get("title")) - set(names), {tuple(e) for e in story.get("anchor") or []}, f"n-{story['id']}"
    cut = now - timedelta(hours=24)
    for r in recent:
        if r["id"] == own or _at(r.get("at")) < cut or not anc & {tuple(e) for e in r.get("anchor") or []}:
            continue
        rw = set(r.get("words") or [])
        sh = w & rw
        if len(sh) >= 2 and len(sh) / min(len(w), len(rw)) >= 0.6:
            return r["id"]
    return None
