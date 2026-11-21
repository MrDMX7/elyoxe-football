"""One club, one record (the teams side of graph/load/people.py): a club that reached us from a weaker source (365Scores,
RSSSF, Transfermarkt, schochastics...) under a name no crosswalk joined to its FotMob record is folded into the FotMob one.
365Scores' «Sporting KC», «Stabaek», «Hearts», «América Mineiro», «Odd BK» were clubs of their own beside FotMob's
«Sporting Kansas City», «Stabæk», «Heart of Midlothian», «America MG», «Odds Ballklubb»: a title was counted twice and
logged as a conflict between two names of one club.

Rules:
  * the record without a FotMob id goes into a FotMob record, never two FotMob records together (each has its own page);
  * the same country: the record's own, else the country of the leagues it played or won in;
  * clubs only (a national team is never folded), and two records that ever met in a match are two clubs;
  * the names, folded (accents, «æ», «ø», case, «FC», «BK», «SC» gone), are equal, or (8+ letters) 0.92 alike letter by
    letter, and neither is a reserve, youth or women's side the other is not; or graph/team_aliases.yaml names the pair
    (abbreviations: «KC», «MG», «Hearts»);
  * exactly one FotMob club fits (two: it stays apart);
  * two records neither of which is FotMob's (RSSSF's and schochastics' «Dubai», the old Dubai CSC) are joined only when
    graph/team_aliases.yaml names them in `same` by source key with a country (never by the name rule): the same country,
    clubs, never met, none FotMob's; the lower Tifo id is kept, and if it folds into a FotMob record the others follow it;
  * a historic UAE club (teams_ar.yaml `historic`, `rename`) and a club FotMob keeps under a later name (`era_names`: Shabab
    Al Ahli, the 2017 merger) are never folded by the name rule: Al Shabab, Al Ahli and Dubai stay three clubs.
Rebuilt in every build and never written to the registry (as the people merge), so a rule fixed tomorrow undoes today's merge."""
import os
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ALIASES = os.path.join(ROOT, "graph", "team_aliases.yaml")
FOLD = str.maketrans({"æ": "ae", "Æ": "ae", "ø": "o", "Ø": "o", "ß": "ss", "đ": "d", "ł": "l", "ı": "i", "œ": "oe"})
NOISE = re.compile(r"\b(club|fc|sc|cf|ac|cd|sd|afc|bk|fk|sk|if|ik|ff|sv|cfc|the)\b")
# a second team of a club (reserves, youth, women) is a team of its own
SIDE = re.compile(r"\b(w|women|womens|femenino|feminino|feminine|ii|iii|b|c|u\d+|res|reserves?|youth|juniors|academy|akatemia)\b")
STATE = re.compile(r"[-(]\s*[A-Z]{2}\)?\s*$")      # a Brazilian state's club: «Internacional-BA», «Botafogo (BA)»
RATIO, MIN_LEN = 0.92, 8


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "").translate(FOLD)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def squash(s):
    return "".join(NOISE.sub(" ", fold(s)).split())


def alike(a, b):
    """Two names of one club: the same once folded and the extras gone, or (8+ letters) close letter by letter. Stricter than
    awards.alike: no «same last word» («Inter Milan» is not «AC Milan»), no «one starts the other» («Olympiakos Volou» is not
    «Olympiakos»), no number dropped («Metalist 1925» is not «Metalist»), and a reserve, youth or women's side is apart."""
    if bool(SIDE.search(fold(a))) != bool(SIDE.search(fold(b))) or bool(STATE.search(a or "")) != bool(STATE.search(b or "")):
        return False
    ja, jb = squash(a), squash(b)
    if not ja or not jb:
        return False
    if ja == jb:
        return True
    return min(len(ja), len(jb)) >= MIN_LEN and SequenceMatcher(None, ja, jb).ratio() >= RATIO


def aliases(path=ALIASES):
    """{folded weaker name: folded FotMob name} from team_aliases.yaml `same` ([[weaker, fotmob], ...])."""
    try:
        d = yaml.safe_load(open(path, encoding="utf-8")) or {}
    except OSError:
        return {}
    return {fold(e[0]): fold(e[1]) for e in d.get("same") or [] if not isinstance(e, dict)}


def joins(path=ALIASES):
    """[(country, [source key, ...])] from team_aliases.yaml `same` entries {country, keys}: one club kept twice by two weaker
    sources. A key is «source:source_id» as in xref («rsssf-name:uae|Dubai», «sch:Dubai (United Arab Emirates)»)."""
    try:
        d = yaml.safe_load(open(path, encoding="utf-8")) or {}
    except OSError:
        return []
    return [(e["country"], list(e["keys"])) for e in d.get("same") or [] if isinstance(e, dict)]


def apart(path=ALIASES):
    """{(folded, folded)} of two clubs whose names are close but who are two clubs (team_aliases.yaml `apart`)."""
    try:
        d = yaml.safe_load(open(path, encoding="utf-8")) or {}
    except OSError:
        return set()
    return {tuple(sorted((fold(a), fold(b)))) for a, b in d.get("apart") or []}


def guarded():
    """Folded names the name rule never touches: the UAE's historic clubs and renames (teams_ar.yaml)."""
    try:
        d = yaml.safe_load(open(os.path.join(ROOT, "teams_ar.yaml"), encoding="utf-8")) or {}
    except OSError:
        return set(), set()
    names = {fold(k) for sec in ("historic", "rename") for k in (d.get(sec) or {})}
    return names, {int(k) for k in (d.get("era_names") or {})}


def joined(teams, keyed, groups, met=frozenset()):
    """[(drop, keep)] of the named groups of non-FotMob records (team_aliases.yaml `same` {country, keys}). A group with a key
    that names no record, a FotMob record, a national team, another country, or two records that met is left alone whole."""
    by = {t[0]: t for t in teams}
    out = []
    for country, keys in groups:
        ids = [keyed.get(k) for k in keys]
        if None in ids or any(i not in by for i in ids):
            continue
        ids = sorted(set(ids))
        if len(ids) < 2 or any(by[i][4] or by[i][3] == "national" or by[i][2] != country for i in ids):
            continue
        if any((a, b) in met for a in ids for b in ids if a < b):
            continue
        out += [(i, ids[0]) for i in ids[1:]]
    return out


def pairs(teams, met=frozenset(), alias=None, guard=frozenset(), era=frozenset(), never=frozenset(), keyed=None, groups=()):
    """[(drop, keep)]. teams: [(tid, name, country, kind, fotmob)]; met: {(a, b)} of teams that played each other;
    keyed: {«source:source_id»: tid}; groups: [(country, [key, ...])] of non-FotMob records named as one club."""
    joins_ = joined(teams, keyed or {}, groups, met)
    gone = {d for d, _ in joins_}
    fm = fotmob_pairs([t for t in teams if t[0] not in gone], met, alias or {}, guard, era, never)
    into = dict(fm)
    return sorted(fm + [(d, into.get(k, k)) for d, k in joins_])


def fotmob_pairs(teams, met, alias, guard, era, never):
    """[(drop, keep)] of non-FotMob records folded into a FotMob record (the alias list or the name rule)."""
    fm_by_c = defaultdict(list)
    for t in teams:
        if t[4] and t[2] and t[3] != "national":
            fm_by_c[t[2]].append(t)
    out = []
    for tid, name, country, kind, fm in teams:
        if fm or not country or kind == "national" or not name:
            continue
        f, cands = fold(name), fm_by_c.get(country, ())
        named = alias.get(f)
        if named:
            fits = [k for k in cands if fold(k[1]) == named]
        elif f in guard:
            continue
        else:
            fits = [k for k in cands if k[0] not in era and fold(k[1]) not in guard and tuple(sorted((f, fold(k[1])))) not in never
                    and alike(name, k[1])]
        fits = [k for k in fits if not (kind and k[3] and kind != k[3]) and (min(tid, k[0]), max(tid, k[0])) not in met]
        if len(fits) == 1:
            out.append((tid, fits[0][0]))
    return sorted(out)


def countries(q):
    """{tid: country}: the team's own, else the league country it played or won in most."""
    own = {tid: c for tid, c in q("SELECT tid, country FROM team")}
    seen = defaultdict(Counter)
    for tid, c, n in q("""SELECT t, c.country, count(*) FROM (SELECT home t, eid FROM match UNION ALL SELECT away, eid FROM match
                           UNION ALL SELECT tid, eid FROM honour WHERE tid IS NOT NULL UNION ALL SELECT tid, eid FROM standing) x
                           JOIN edition e ON e.eid=x.eid JOIN competition c ON c.cid=e.cid
                           WHERE c.kind='league' AND c.country IS NOT NULL GROUP BY 1, 2"""):
        seen[tid][c] += n
    return {tid: own.get(tid) or (seen[tid].most_common(1)[0][0] if seen.get(tid) else None) for tid in own}


def candidates(c, alias=None, guard=None, era=None):
    """The (drop, keep) pairs for one graph's connection (read-only: nothing is changed)."""
    q = lambda s, p=(): c.execute(s, p).fetchall()
    if guard is None or era is None:
        g, e = guarded()
        guard = g if guard is None else guard
        era = e if era is None else era
    fm = {t for (t,) in q("SELECT DISTINCT tifo_id FROM xref WHERE type='team' AND source='fotmob'")}
    cc = countries(q)
    teams = [(tid, name, cc.get(tid), kind, tid in fm) for tid, name, kind in q("SELECT tid, name, kind FROM team")]
    met = {(min(h, a), max(h, a)) for h, a in q("SELECT DISTINCT home, away FROM match WHERE home IS NOT NULL AND away IS NOT NULL")}
    keyed = {f"{s}:{i}": t for t, s, i in q("SELECT tifo_id, source, source_id FROM xref WHERE type='team'")}
    # era_names are keyed by FotMob id (102119): the Tifo record carrying that id is the one the name rule must not touch
    era = set(era) | {keyed[f"fotmob:{e}"] for e in era if f"fotmob:{e}" in keyed}
    return pairs(teams, met, aliases() if alias is None else alias, guard, era, apart(), keyed, joins())


def settle_conflicts(G, merged):
    """A champion or runner-up «conflict» between a record and the one it was folded into is one club: off the list."""
    m = {str(d): str(k) for d, k in merged}
    n = 0
    for rowid, kept, other in G.c.execute("SELECT rowid, kept, other FROM conflict WHERE type='honour' AND field IN ('champion', 'runner_up')").fetchall():
        if m.get(kept, kept) == m.get(other, other) and kept != other:
            G.c.execute("DELETE FROM conflict WHERE rowid=?", (rowid,))
            n += 1
    return n


def load(G, reg, S):
    merged = candidates(G.c)
    G.remap_many("team", merged)
    return {"merged": len(merged), "conflicts_settled": settle_conflicts(G, merged)}
