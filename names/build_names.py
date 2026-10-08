#!/usr/bin/env python3
"""Arabic player-name dictionary for tifo.elyoxe.com.

FotMob gives player names in Latin script only. This script collects every
player the site shows (from the public /v1 feed), then finds the Arabic
spelling Arab sports media use, most reliable source first:

  1. Wikidata  - search footballers by name, match on nationality / birth
                 year / club, take the `ar` label           -> source "wikidata"
  2. arwiki    - the Arabic Wikipedia title (sitelink)      -> source "arwiki"
     (Egyptian-Arabic `arz` labels are NOT used: bot transliterations)
  3. Gemini    - transliterate the rest, 50 per call, with
                 nationality as a hint                      -> source "generated"

Incremental: ids already in players_ar.json are skipped, so the hourly job
can call it and only new players are looked up.

    python3 build_names.py                 # collect + resolve + write
    python3 build_names.py --stage collect # only refresh the player pool
    python3 build_names.py --no-gemini     # wikidata only, leave the rest
    python3 build_names.py --retry-generated  # re-try wikidata for generated ids
    python3 build_names.py --kind coaches  # coaches (coaches/index.json + team coaches) -> coaches_ar.json

Network: forces IPv4 (the phone's resolver stalls ~5 s on AAAA lookups).
Caches (HTTP responses, the pool) go to --cache (default ~/.cache/tifo-names).
"""
import argparse
import csv
import datetime as dt
import gzip
import json
import os
import random
import re
import socket
import sys
import time
import unicodedata
from pathlib import Path

import requests
import urllib3.util.connection as _uc

sys.path.append(str(Path(__file__).resolve().parent.parent))   # repo root: usage_log
import usage_log

_uc.allowed_gai_family = lambda: socket.AF_INET  # IPv4 only

HERE = Path(__file__).resolve().parent
OUT = HERE / "players_ar.json"
REVIEW = HERE / "review_uae.csv"
FEED = "https://tifo.elyoxe.com/v1"
UA = "ElyoxeTifoNames/1.0 (https://tifo.elyoxe.com; hello@elyoxe.com)"
WD_API = "https://www.wikidata.org/w/api.php"
WD_SPARQL = "https://query.wikidata.org/sparql"
GEMINI_MODEL = "gemini-3.1-flash-lite"   # owner 2026-10-09: Tifo's one model (site/ai/gen.py MODEL)
UAE_LEAGUE = 538
UAE_NATIONAL = 5789
FOOTBALLER = "Q937857"  # association football player
TODAY = dt.date.today().isoformat()

S = requests.Session()
S.headers["User-Agent"] = UA


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, file=sys.stderr, flush=True)


def get_json(url, params=None, tries=4, pause=0.0, timeout=40):
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=timeout)
            if r.status_code == 404:
                return None
            if r.status_code in (429, 503, 502, 504):
                wait = int(r.headers.get("Retry-After", 0) or 0) or 5 * (i + 1)
                log(f"  {r.status_code}, waiting {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            if pause:
                time.sleep(pause)
            return r.json()
        except (requests.RequestException, ValueError) as e:
            log(f"  retry {i + 1}: {url} {e}")
            time.sleep(3 * (i + 1))
    return None


# --------------------------------------------------------------------------
# 1. collect the pool of players from the feed
# --------------------------------------------------------------------------

def collect(cache: Path, match_days: int):
    """Returns {pid: {name, teams:set, country, birth_years:set, comps:set}}."""
    pool = {}

    def add(pid, name, team=None, country=None, age=None, comp=None, uae=False):
        if not pid or not name:
            return
        pid = str(pid)
        p = pool.setdefault(pid, {"name": name, "teams": [], "country": None,
                                  "ages": [], "comps": [], "uae": False})
        if team and team not in p["teams"]:
            p["teams"].append(team)
        if country and not p["country"]:
            p["country"] = country
        if age and age not in p["ages"]:
            p["ages"].append(age)
        if comp and comp not in p["comps"]:
            p["comps"].append(comp)
        if uae:
            p["uae"] = True

    index = get_json(f"{FEED}/index.json")
    teams = (get_json(f"{FEED}/teams.json") or {}).get("teams", {})
    comps = [c["id"] for c in index["competitions"]]
    log(f"collect: {len(comps)} competitions, {len(teams)} teams")

    for cid in comps:
        pj = get_json(f"{FEED}/comp/{cid}/players.json")
        for pid, p in ((pj or {}).get("players") or {}).items():
            add(pid, p.get("name"), p.get("team"), comp=cid, uae=(cid == UAE_LEAGUE))
        sj = get_json(f"{FEED}/comp/{cid}/stats.json")
        for lst in ((sj or {}).get("lists") or {}).values():
            for row in lst or []:
                pl = row.get("player") or {}
                add(pl.get("id"), pl.get("name"), (row.get("team") or {}).get("id"),
                    comp=cid, uae=(cid == UAE_LEAGUE))

    squads = 0
    for tid in teams:
        tj = get_json(f"{FEED}/team/{tid}.json")
        if not tj:
            continue
        squads += 1
        uae_team = UAE_LEAGUE in (teams[tid].get("comps") or []) or int(tid) == UAE_NATIONAL
        for grp in tj.get("squad") or []:
            for p in grp.get("players") or []:
                add(p.get("id"), p.get("name"), int(tid), p.get("country"), p.get("age"),
                    uae=uae_team)
                if int(tid) == UAE_NATIONAL:
                    pool[str(p["id"])]["national"] = UAE_NATIONAL
                    if p.get("club_id"):
                        add(p["id"], p["name"], p["club_id"])
    log(f"collect: {squads} squad files")

    # recent match lineups: finished matches of the last N days in every
    # competition (all finished ones for the UAE league)
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=match_days)).strftime("%Y-%m-%dT")
    mids = []
    for cid in comps:
        fj = get_json(f"{FEED}/comp/{cid}/fixtures.json")
        for m in (fj or {}).get("matches") or []:
            if m.get("status") == "finished" and (
                    cid == UAE_LEAGUE or (m.get("kickoff_utc") or "") >= since):
                mids.append(m["id"])
    mids = list(dict.fromkeys(mids))
    got = 0
    for mid in mids:
        mj = get_json(f"{FEED}/match/{mid}.json")
        if not mj:
            continue
        lu = mj.get("lineups") or {}
        if not isinstance(lu, dict):
            continue
        cid = mj.get("comp")
        for side in ("home", "away"):
            s = lu.get(side) or {}
            tid = s.get("team_id")
            for key in ("starters", "subs", "unavailable"):
                for p in s.get(key) or []:
                    add(p.get("id"), p.get("name"), tid, p.get("country"), p.get("age"),
                        comp=cid, uae=(cid == UAE_LEAGUE))
                    got += 1
    log(f"collect: {len(mids)} finished matches in {match_days} days, {got} lineup rows")
    log(f"collect: pool = {len(pool)} players")
    (cache / "pool.json").write_text(json.dumps(pool, ensure_ascii=False))
    (cache / "teams.json").write_text(json.dumps(teams, ensure_ascii=False))
    return pool, teams


def collect_referees(cache: Path):
    """Referees named in the competition referee files (comp/{id}/referees.json)."""
    pool = {}
    index = get_json(f"{FEED}/index.json")
    for c in index["competitions"]:
        rj = get_json(f"{FEED}/comp/{c['id']}/referees.json") or {}
        for r in rj.get("referees") or []:
            if r.get("id") and r.get("name"):
                pool.setdefault(str(r["id"]), {"name": r["name"], "teams": [], "country": r.get("country"), "ages": [], "comps": [c["id"]], "uae": c["id"] == UAE_LEAGUE})
    log(f"collect referees: pool = {len(pool)}")
    return pool, {}


def collect_clubs(cache: Path):
    """Clubs the feed has no Arabic name for (teams.json without name_ar, plus clubs seen only in fixtures)."""
    pool = {}
    teams = (get_json(f"{FEED}/teams.json") or {}).get("teams", {})
    for tid, t in teams.items():
        if not t.get("name_ar") and t.get("name"):
            pool[str(tid)] = {"name": t["name"], "teams": [], "country": t.get("country"), "ages": [], "comps": [], "uae": False, "club": True}
    index = get_json(f"{FEED}/index.json")
    for c in index["competitions"]:
        fj = get_json(f"{FEED}/comp/{c['id']}/fixtures.json") or {}
        for m in fj.get("matches") or []:
            for side in (m.get("home") or {}, m.get("away") or {}):
                if side.get("id") and side.get("name") and not side.get("name_ar") and str(side["id"]) not in pool:
                    pool[str(side["id"])] = {"name": side["name"], "teams": [], "country": (c.get("country") or {}).get("iso2"), "ages": [], "comps": [c["id"]], "uae": False, "club": True}
    log(f"collect clubs: pool = {len(pool)}")
    return pool, teams


def collect_coaches(cache: Path):
    """Coaches the site names: coaches/index.json (with each coach file's country and clubs) + every team's current coach."""
    pool = {}
    teams = (get_json(f"{FEED}/teams.json") or {}).get("teams", {})
    idx = get_json(f"{FEED}/coaches/index.json") or {}
    for c in idx.get("coaches") or []:
        cj = get_json(f"{FEED}/coaches/{c['id']}.json") or {}
        pool[str(c["id"])] = {"name": cj.get("name") or c.get("name"), "teams": sorted({r["team"] for r in cj.get("rows") or [] if r.get("team")}),
                              "country": cj.get("country"), "ages": [], "comps": [], "uae": any(r.get("comp") == UAE_LEAGUE for r in cj.get("rows") or [])}
    for tid in teams:
        tj = get_json(f"{FEED}/team/{tid}.json") or {}
        co = tj.get("coach") or {}
        if co.get("id") and str(co["id"]) not in pool:
            pool[str(co["id"])] = {"name": co.get("name"), "teams": [int(tid)], "country": co.get("country"), "ages": [], "comps": [], "uae": int(tid) == UAE_NATIONAL}
    pool = {k: v for k, v in pool.items() if v.get("name")}
    log(f"collect coaches: pool = {len(pool)}")
    (cache / "coach_pool.json").write_text(json.dumps(pool, ensure_ascii=False))
    (cache / "teams.json").write_text(json.dumps(teams, ensure_ascii=False))
    return pool, teams


# --------------------------------------------------------------------------
# helpers: names, countries
# --------------------------------------------------------------------------

def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("ø", "o").replace("ß", "ss").replace("ł", "l").replace("đ", "d").replace("ı", "i")
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower().replace("-", " ").replace("'", ""))
    return re.sub(r"\s+", " ", s).strip()


def name_score(latin, labels):
    """0..1 how well a candidate's labels/aliases fit the FotMob name."""
    a = fold(latin)
    ta = set(a.split())
    best = 0.0
    for lab in labels:
        b = fold(lab)
        if not b:
            continue
        if a == b:
            return 1.0
        tb = set(b.split())
        # al/el prefixes: "Al Dhanhani" vs "Al-Dhanhani" handled by fold
        inter = len(ta & tb)
        if not inter:
            continue
        sc = inter / max(len(ta), 1)
        if ta <= tb or tb <= ta:
            sc = max(sc, 0.85)
        best = max(best, sc)
    return best


AR_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
ARABIC = re.compile(r"[؀-ۿ]")


def clean_ar(s):
    if not s:
        return None
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)  # "(لاعب كرة قدم)"
    s = AR_DIACRITICS.sub("", s)
    s = re.sub(r"[\u200b-\u200f\u00a0]", " ", s).replace("_", " ")
    s = s.replace("\u06cc", "\u064a").replace("\u06a9", "\u0643")  # Persian yeh/keheh
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", " ", s).strip()
    # پ چ ڤ ژ گ: Persian / Egyptian-Wikipedia letters Arab sports media do not use
    if not ARABIC.search(s) or re.search(r"[A-Za-z\u067e\u0686\u06a4\u0698\u06af]", s):
        return None
    return s


def fifa_codes(cache: Path):
    """FIFA 3-letter code -> set of Wikidata country QIDs (and reverse)."""
    f = cache / "fifa_codes.json"
    if f.exists():
        return json.loads(f.read_text())
    # P3441 sits on the national *teams*; map through their country (P17/P1532),
    # and add ISO alpha-3 codes (P298) of countries as a fallback.
    q = """SELECT ?code ?c WHERE {
      { ?t wdt:P3441 ?code . ?t wdt:P17|wdt:P1532 ?c }
      UNION { ?c wdt:P298 ?code . ?c wdt:P31 wd:Q6256 } }"""
    r = S.get(WD_SPARQL, params={"query": q, "format": "json"}, timeout=90).json()
    m = {}
    for b in r["results"]["bindings"]:
        code = b["code"]["value"].upper()
        c = b["c"]["value"].rsplit("/", 1)[1]
        if c not in m.setdefault(code, []):
            m[code].append(c)
    # home nations: players carry England/Scotland/... or the UK
    for code, q_ in {"ENG": "Q21", "SCO": "Q22", "WAL": "Q25", "NIR": "Q26"}.items():
        m.setdefault(code, [])
        m[code] += [q_, "Q145"]
    f.write_text(json.dumps(m))
    return m


# --------------------------------------------------------------------------
# 2. Wikidata
# --------------------------------------------------------------------------

class WD:
    def __init__(self, cache: Path, pause: float):
        self.dir = cache / "wd"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.pause = pause
        self.ent_file = self.dir / "entities.jsonl"
        self.ents = {}
        if self.ent_file.exists():
            for line in self.ent_file.open():
                e = json.loads(line)
                self.ents[e["id"]] = e
        self.search_file = self.dir / "search.jsonl"
        self.searches = {}
        if self.search_file.exists():
            for line in self.search_file.open():
                k, v = json.loads(line)
                self.searches[k] = v

    def search(self, name):
        """CirrusSearch restricted to footballers. Returns QIDs."""
        key = fold(name)
        if key in self.searches:
            return self.searches[key]
        qids = []
        for q in (f'{name} haswbstatement:P106={FOOTBALLER}',):
            j = get_json(WD_API, {"action": "query", "list": "search", "srsearch": q,
                                  "srlimit": 10, "srnamespace": 0, "format": "json"},
                         pause=self.pause)
            for hit in ((j or {}).get("query") or {}).get("search") or []:
                if hit["title"] not in qids:
                    qids.append(hit["title"])
            if j is None:
                return []  # do not cache failures
        self.searches[key] = qids
        with self.search_file.open("a") as f:
            f.write(json.dumps([key, qids], ensure_ascii=False) + "\n")
        return qids

    def fetch(self, qids):
        need = [q for q in dict.fromkeys(qids) if q not in self.ents]
        for i in range(0, len(need), 50):
            chunk = need[i:i + 50]
            j = get_json(WD_API, {"action": "wbgetentities", "ids": "|".join(chunk),
                                  "props": "labels|aliases|claims|sitelinks",
                                  "languages": "en|ar|arz|fr|es|pt|de|it",
                                  "sitefilter": "enwiki|arwiki", "format": "json"},
                         pause=self.pause)
            with self.ent_file.open("a") as f:
                for qid, e in ((j or {}).get("entities") or {}).items():
                    slim = slim_entity(qid, e)
                    self.ents[qid] = slim
                    f.write(json.dumps(slim, ensure_ascii=False) + "\n")
        return [self.ents[q] for q in qids if q in self.ents]


def _claim_ids(e, prop):
    out = []
    for c in (e.get("claims") or {}).get(prop, []):
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(v, dict) and "id" in v:
            out.append(v["id"])
    return out


def slim_entity(qid, e):
    labels = {k: v["value"] for k, v in (e.get("labels") or {}).items()}
    aliases = [a["value"] for lang in ("en", "fr", "es", "pt", "de", "it")
               for a in (e.get("aliases") or {}).get(lang, [])]
    dob = None
    for c in (e.get("claims") or {}).get("P569", []):
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if v and v.get("time"):
            m = re.match(r"[+-](\d{4})", v["time"])
            if m:
                dob = int(m.group(1))
                break
    return {
        "id": qid,
        "labels": labels,
        "aliases": aliases,
        "ar_aliases": [a["value"] for lang in ("ar",) for a in (e.get("aliases") or {}).get(lang, [])],
        "dob": dob,
        "country": sorted(set(_claim_ids(e, "P1532") + _claim_ids(e, "P27"))),
        "clubs": _claim_ids(e, "P54"),
        "occ": _claim_ids(e, "P106"),
        "enwiki": ((e.get("sitelinks") or {}).get("enwiki") or {}).get("title"),
        "arwiki": ((e.get("sitelinks") or {}).get("arwiki") or {}).get("title"),
    }


def team_qids(wd: WD, teams, cache: Path):
    """FotMob team id -> set of candidate Wikidata QIDs (by name search).
    Also searches "<name> national football team" so that stats-only players
    of a national side (no age, no nationality in the feed) match on P54."""
    f = cache / "team_qids2.json"
    m = json.loads(f.read_text()) if f.exists() else {}
    for tid, t in teams.items():
        if tid in m:
            continue
        ids = []
        for q in (t["name"], f'{t["name"]} national football team'):
            j = get_json(WD_API, {"action": "wbsearchentities", "search": q, "language": "en",
                                  "type": "item", "limit": 7, "format": "json"}, pause=wd.pause)
            ids += [h["id"] for h in (j or {}).get("search") or [] if h["id"] not in ids]
        m[tid] = ids
        if len(m) % 50 == 0:
            f.write_text(json.dumps(m))
    f.write_text(json.dumps(m))
    return {k: set(v) for k, v in m.items()}


def score(p, e, fifa, tq):
    """Score one candidate entity for FotMob player p. Returns (score, why)."""
    labels = [e["labels"].get(l) for l in ("en", "fr", "es", "pt", "de", "it") if e["labels"].get(l)]
    ns = name_score(p["name"], labels + e["aliases"])
    if ns < 0.5:
        return -99, "name"
    sc, why = ns * 3, [f"n{ns:.2f}"]
    if FOOTBALLER in e["occ"]:
        sc += 0.5
    # nationality
    if p.get("country"):
        cq = set(fifa.get(p["country"].upper(), []))
        if cq and e["country"]:
            if cq & set(e["country"]):
                sc += 2; why.append("nat+")
            else:
                sc -= 1.5; why.append("nat-")
    # birth year from age
    if p.get("ages") and e["dob"]:
        by = {int(TODAY[:4]) - a - k for a in p["ages"] for k in (0, 1)}
        if e["dob"] in by:
            sc += 2.5; why.append("dob+")
        elif min(abs(e["dob"] - b) for b in by) <= 1:
            sc += 1; why.append("dob~")
        else:
            sc -= 3; why.append("dob-")
    elif e["dob"] and e["dob"] < 1978:
        sc -= 2; why.append("old")
    # club
    clubs = set(e["clubs"])
    for t in p.get("teams") or []:
        if clubs & tq.get(str(t), set()):
            sc += 2.5; why.append("club+")
            break
    return sc, " ".join(why)


LATIN_JOIN = {"al", "el", "ad", "as", "ash", "ar", "at", "az", "abdul", "abdel", "abd"}


def latin_parts(name):
    """Word count as Arabic would write it: 'Ali Al Hosani' -> 2."""
    toks = fold(name).split()
    n, skip = 0, False
    for t in toks:
        if skip:
            skip = False
            continue
        n += 1
        if t in LATIN_JOIN:
            skip = True
    return max(n, 1)


def ar_parts(s):
    toks = s.split()
    n, skip = 0, False
    for t in toks:
        if skip:
            skip = False
            continue
        n += 1
        if t in ("عبد", "ال", "أبو", "ابو"):
            skip = True
    return n


def pick_ar(e, latin):
    """Best Arabic form. Wikidata often labels players with their full legal
    name ('فابيو فيرجينيو دي ليما' for 'Fábio Lima'), so prefer a label, alias
    or arwiki title with as many words as the name FotMob uses; otherwise
    return the label and flag it for trimming.  -> (ar, source, needs_trim)"""
    want = latin_parts(latin)
    forms = []  # (text, source)
    for txt, src in ([(e["labels"].get("ar"), "wikidata")]
                     + [(e.get("arwiki"), "arwiki")]
                     + [(a, "wikidata") for a in e.get("ar_aliases", [])]):
        # arz (Egyptian Wikipedia) labels were tried and dropped: they are bot
        # transliterations («ديجو», «جورتنير», ڤ/پ) not media spellings
        t = clean_ar(txt)
        if t and t not in [f[0] for f in forms]:
            forms.append((t, src))
    if not forms:
        return None, None, False
    for t, src in forms:
        if ar_parts(t) == want:
            return t, src, False
    t, src = forms[0]
    return t, src, ar_parts(t) > want


def resolve_wikidata(todo, pool, teams, cache, pause, out, save):
    wd = WD(cache, pause)
    fifa = fifa_codes(cache)
    tq = team_qids(wd, teams, cache)
    audit = (cache / "wd_audit.jsonl").open("a")
    found = 0
    for n, pid in enumerate(todo, 1):
        p = pool[pid]
        qids = wd.search(p["name"])
        # short mononyms ("Erik", "Julimar"): the search is noisy, still try
        cands = wd.fetch(qids)
        scored = sorted(((score(p, e, fifa, tq), e) for e in cands), key=lambda x: -x[0][0])
        scored = [x for x in scored if x[0][0] > -99]
        choice = None
        if scored:
            (s1, why1), e1 = scored[0]
            s2 = scored[1][0][0] if len(scored) > 1 else -99
            evidence = any(k in why1 for k in ("nat+", "dob+", "club+"))
            mono = len(fold(p["name"]).split()) == 1
            ok = (s1 - s2 >= 1.5 or (s1 >= 6 and s1 - s2 >= 0.75))
            ns1 = float(why1.split()[0][1:])
            # a nationality mismatch is real evidence of another person, but
            # Gulf leagues are full of naturalised players whose Wikidata
            # citizenship lags: accept it only with a club match, or an exact
            # birth year + close name + no rival candidate.
            if "nat-" in why1 and "club+" not in why1:
                ok = ok and "dob+" in why1 and ns1 >= 0.85 and s1 - s2 >= 3 and not mono
            if "dob-" in why1:
                ok = False
            if mono:
                ok = ok and evidence and s1 >= 5.5
            else:
                ok = ok and (evidence or (s1 >= 3 and len(scored) == 1 and not p.get("ages")
                                          and not p.get("country")))
            if ok:
                ar, src, trim = pick_ar(e1, p["name"])
                # matched through an alias or a longer label: the Arabic may
                # render another form of the name (Diney Borges -> ديني إديلسون)
                trim = trim or fold(e1["labels"].get("en", "")) != fold(p["name"])
                choice = (e1["id"], ar, src, s1, why1, trim)
        audit.write(json.dumps({"pid": pid, "name": p["name"],
                                "cands": [(e["id"], round(s[0], 2), s[1]) for s, e in scored[:4]],
                                "choice": choice}, ensure_ascii=False) + "\n")
        if choice and choice[1]:
            out[pid] = {"latin": p["name"], "ar": choice[1], "source": choice[2],
                        "qid": choice[0], "checked": TODAY}
            if choice[5]:
                out[pid]["_trim"] = True
            found += 1
        elif choice:
            p["_qid"] = choice[0]  # matched, but no Arabic label: keep qid for the generated row
        if n % 100 == 0:
            log(f"wikidata {n}/{len(todo)} found {found}")
            save()
    audit.close()
    save()
    log(f"wikidata done: {found}/{len(todo)}")


# --------------------------------------------------------------------------
# 3. Gemini transliteration
# --------------------------------------------------------------------------

def gemini_key():
    """TIFO_GEMINI_API_KEY if one ever exists, else the films' GEMINI_API_KEY (owner 2026-10-09: «استعمل مال السينما»).
    None while ~/.elyoxe/gemini-off exists (owner's switch, 2026-10-01): the run then fills names from Wikidata only."""
    off = os.environ.get("ELYOXE_GEMINI_OFF") or os.path.expanduser("~/.elyoxe/gemini-off")
    if os.path.exists(off) and not os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    f = Path.home() / "workspace/content-pipeline/.env"
    lines = f.read_text().splitlines() if f.exists() else []
    for name in ("TIFO_GEMINI_API_KEY", "GEMINI_API_KEY"):
        if os.environ.get(name):
            return os.environ[name]
        for l in lines:
            if l.startswith(name + "="):
                v = l.split("=", 1)[1].strip().strip('"\'')
                if v:
                    return v
    return None


PROMPT = """You are an Arabic sports editor (think beIN Sports, Al Kass, Kooora, Al Ittihad).
Write each footballer's name in Arabic exactly as Arab sports media commonly spell it.

Rules:
- Arabic script only, no diacritics (no tashkeel), no Latin letters.
- If the player is Arab (Emirati, Saudi, Qatari, Egyptian, Moroccan, etc.), write his real Arabic name:
  "Ali Mabkhout" -> "علي مبخوت", "Khalid Eissa" -> "خالد عيسى", "Mohamed Salah" -> "محمد صلاح".
  Arab family prefixes: "Al" -> "ال" joined to the word ("Al Dhanhani" -> "الظنحاني"), "bin"/"ben" -> "بن".
  "Abdulla"/"Abdullah"/"Abdalla" -> "عبدالله" (one word); "Abdul"/"Abdel" + name -> "عبد" + name
  as two words ("Abdul Rahman" -> "عبد الرحمن", "Abdulsalam" -> "عبد السلام").
- Otherwise transliterate by the pronunciation of his nationality's language, as Arab media do:
  Spanish/Latin American: "Nicolás Giménez" -> "نيكولاس خيمينيز", "j" -> "خ";
  Portuguese/Brazilian: "Júnior" -> "جونيور", "Rodrigues" -> "رودريغيز", "lh" -> "لي";
  French: silent final letters ("Mbappé" -> "مبابي", "Dembélé" -> "ديمبيلي");
  English: "Harry Kane" -> "هاري كين".
- Keep particles as media write them: "de"/"di" -> "دي", "da" -> "دا", "van" -> "فان", "dos" -> "دوس".
- Use "غ" for hard "g", "ج" for "j" in English/French/Portuguese, "تش" for "ch" (Spanish/English), "ف" for "v".
- Keep the same number of name parts as the Latin name (a mononym stays one word).
Return one item per input, with the same id."""


def gemini_call(key, text, n):
    """One structured call -> {id: ar}. Every string has a maxLength (without
    it Gemini can loop inside a string until the token limit)."""
    schema = {
        "type": "OBJECT",
        "properties": {"names": {"type": "ARRAY", "maxItems": n + 2, "items": {
            "type": "OBJECT",
            "properties": {"id": {"type": "STRING", "maxLength": 12},
                           "ar": {"type": "STRING", "maxLength": 60}},
            "required": ["id", "ar"]}}},
        "required": ["names"],
    }
    body = {
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": schema,
                             "temperature": 0.2, "maxOutputTokens": 8192},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    for i in range(4):
        try:
            r = S.post(url, params={"key": key}, json=body, timeout=180)
            if r.status_code in (429, 500, 503):
                log(f"  gemini {r.status_code}, waiting"); time.sleep(10 * (i + 1)); continue
            r.raise_for_status()
            j = r.json()
            usage_log.record_gemini("names", GEMINI_MODEL, j, round(r.elapsed.total_seconds(), 1))
            txt = j["candidates"][0]["content"]["parts"][0]["text"]
            return {str(x["id"]): x["ar"] for x in json.loads(txt)["names"]}
        except Exception as e:  # noqa: BLE001
            log(f"  gemini retry {i + 1}: {str(e)[:200]}")
            time.sleep(5 * (i + 1))
    return {}


KIND = "players"
CLUB_PROMPT = """You are an Arabic sports editor (beIN Sports, Kooora, Al Ittihad). Write each football CLUB's name in Arabic
exactly as Arab sports media write it. Arab clubs: their real Arabic name ("Widad Temara" -> "وداد تمارة",
"Raja Casablanca" -> "الرجاء الرياضي", "Al Ahly" -> "الأهلي"). Other clubs: the usual Arabic media form ("Bayern Munich" ->
"بايرن ميونخ"). Arabic script only, no diacritics. Drop words like FC/SC/Club unless Arab media keep them."""


def gemini_batch(key, items):
    lines = "\n".join(f'{it["id"]}\t{it["latin"]}\tnationality={it["nat"] or "unknown"}'
                      + (f'\tclub={it["club"]}' if it.get("club") else "") for it in items)
    return gemini_call(key, (CLUB_PROMPT if KIND == "clubs" else PROMPT) + "\n\nid\tname\thints\n" + lines, len(items))


def resolve_gemini(todo, pool, teams, out, save, batch=50):
    key = gemini_key()
    done = 0
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        items = []
        for pid in chunk:
            p = pool[pid]
            club = next((teams[str(t)]["name"] for t in p.get("teams") or [] if str(t) in teams), None)
            items.append({"id": pid, "latin": p["name"], "nat": p.get("country"), "club": club})
        res = gemini_batch(key, items)
        for pid in chunk:
            ar = clean_ar(res.get(pid))
            if ar:
                prev = out.get(pid) or {}
                out[pid] = {"latin": pool[pid]["name"], "ar": ar, "source": "generated",
                            "qid": prev.get("qid") or pool[pid].get("_qid"), "checked": TODAY}
                if prev.get("wd_label") or (prev.get("ar") and prev.get("source") != "generated"):
                    out[pid]["wd_label"] = prev.get("wd_label") or prev["ar"]
                done += 1
        log(f"gemini {min(i + batch, len(todo))}/{len(todo)} ok {done}")
        save()


TRIM_PROMPT = """Each line gives a footballer's name as FotMob shows it (Latin script) and an
Arabic name for him from Wikidata. The Arabic may be his full legal name, or a different
form of his name than the one FotMob uses.
Return the Arabic words that render the FotMob name, in the same order, copied exactly
from the Arabic (for example "Fábio Lima" + "فابيو فيرجينيو دي ليما" -> "فابيو ليما";
"Talisca" + "أندرسون تاليسكا" -> "تاليسكا"; "Mohammed Khalaf" + "محمد خلف الحمادي" -> "محمد خلف").
If the Arabic already renders the FotMob name, return it unchanged.
If some word of the FotMob name has no rendering in the Arabic (for example
"Diney Borges" + "ديني إديلسون": Borges is missing), return an empty string. Do not invent words."""

_HAMZA = str.maketrans("أإآة", "اااه")


def resolve_trim(out, save, batch=50):
    todo = [pid for pid, o in out.items() if o.get("_trim")]
    if not todo:
        return
    key = gemini_key()
    fixed = dropped = 0
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        lines = "\n".join(f'{pid}\t{out[pid]["latin"]}\t{out[pid]["ar"]}' for pid in chunk)
        res = gemini_call(key, TRIM_PROMPT + "\n\nid\tshort\tarabic_full\n" + lines, len(chunk))
        for pid in chunk:
            o = out[pid]
            o.pop("_trim", None)
            if pid not in res:
                o["_trim"] = True  # call failed, retry next run
                continue
            t = clean_ar(res.get(pid))
            full = o["ar"].translate(_HAMZA).split()
            if t and all(w.translate(_HAMZA) in full for w in t.split()):
                if t != o["ar"]:
                    o["wd_label"] = o["ar"]
                    o["ar"] = t
                    fixed += 1
            else:
                # the Wikidata Arabic is another name form: transliterate instead
                o["_gen"] = True
                dropped += 1
        log(f"check {min(i + batch, len(todo))}/{len(todo)} trimmed {fixed}, sent to generate {dropped}")
        save()


# --------------------------------------------------------------------------
# 4. outputs
# --------------------------------------------------------------------------

def write_review(out, pool, teams):
    rows = []
    for pid, p in pool.items():
        in_league = UAE_LEAGUE in p.get("comps", []) or any(
            UAE_LEAGUE in (teams.get(str(t), {}).get("comps") or []) for t in p.get("teams") or [])
        national = p.get("national") == UAE_NATIONAL or UAE_NATIONAL in (p.get("teams") or [])
        if not (in_league or national):
            continue
        uae_clubs = [t for t in p.get("teams") or []
                     if UAE_LEAGUE in (teams.get(str(t), {}).get("comps") or [])]
        if uae_clubs:
            team = teams[str(uae_clubs[0])].get("name_ar") or teams[str(uae_clubs[0])]["name"]
        else:
            team = teams.get(str(UAE_NATIONAL), {}).get("name_ar") or "منتخب الإمارات"
        if national and uae_clubs:
            team += " + المنتخب"
        o = out.get(pid, {})
        rows.append([pid, p["name"], o.get("ar", ""), o.get("source", ""), team])
    rows.sort(key=lambda r: (r[4], r[1]))
    with REVIEW.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "latin", "ar", "source", "team"])
        w.writerows(rows)
    log(f"review_uae.csv: {len(rows)} rows")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["all", "collect"], default="all")
    ap.add_argument("--cache", default=str(Path.home() / ".cache/tifo-names"))
    ap.add_argument("--match-days", type=int, default=21)
    ap.add_argument("--pause", type=float, default=0.3, help="seconds between Wikidata calls")
    ap.add_argument("--no-gemini", action="store_true")
    ap.add_argument("--reuse-pool", action="store_true", help="use cached pool.json")
    ap.add_argument("--retry-generated", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--kind", choices=["players", "coaches", "referees", "clubs"], default="players")
    ap.add_argument("--no-wikidata", action="store_true", help="skip the Wikidata pass (Gemini only; --retry-generated later)")
    a = ap.parse_args()
    global OUT, KIND
    KIND = a.kind
    if a.kind != "players":
        OUT = HERE / f"{a.kind}_ar.json"
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)

    if a.kind in ("referees", "clubs"):
        pool, teams = (collect_referees if a.kind == "referees" else collect_clubs)(cache)
    elif a.kind == "coaches":
        pool, teams = (json.loads((cache / "coach_pool.json").read_text()), json.loads((cache / "teams.json").read_text())) if a.reuse_pool and (cache / "coach_pool.json").exists() else collect_coaches(cache)
    elif a.reuse_pool and (cache / "pool.json").exists():
        pool = json.loads((cache / "pool.json").read_text())
        teams = json.loads((cache / "teams.json").read_text())
    else:
        pool, teams = collect(cache, a.match_days)
    if a.stage == "collect":
        return

    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    # FotMob can rename a player; keep latin fresh
    for pid, o in out.items():
        if pid in pool and pool[pid]["name"] != o["latin"]:
            o["latin"] = pool[pid]["name"]

    def save():
        tmp = OUT.with_suffix(".tmp")
        tmp.write_text(json.dumps(dict(sorted(out.items(), key=lambda kv: int(kv[0]))),
                                  ensure_ascii=False, indent=1))
        tmp.replace(OUT)

    todo = [pid for pid in pool if pid not in out
            or (a.retry_generated and out[pid]["source"] == "generated"
                and not out[pid].get("qid"))]
    # UAE players first so a partial run still serves the league
    todo.sort(key=lambda pid: (not pool[pid].get("uae"), int(pid)))
    if a.limit:
        todo = todo[:a.limit]
    log(f"{len(out)} already done, {len(todo)} to resolve")
    if todo and not a.no_wikidata:
        resolve_wikidata(todo, pool, teams, cache, a.pause, out, save)
    if not a.no_gemini and not gemini_key():
        log("no TIFO_GEMINI_API_KEY: Gemini step skipped (wikidata only)")
    elif not a.no_gemini:
        resolve_trim(out, save)
        rest = [pid for pid in todo if pid not in out] + \
               [pid for pid, o in out.items() if o.get("_gen") and pid in pool]
        if rest:
            resolve_gemini(rest, pool, teams, out, save)
    save()
    if a.kind == "players":
        write_review(out, pool, teams)
    counts = {}
    for o in out.values():
        counts[o["source"]] = counts.get(o["source"], 0) + 1
    log(f"total {len(out)} of pool {len(pool)}: {counts}")


if __name__ == "__main__":
    main()
