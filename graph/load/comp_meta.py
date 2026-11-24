"""A competition's name, kind, country and scope, set right once every source is in (24 Nov 2026: 262 competitions were
called «FotMob 9515», 83 by schochastics' slug («burkina-faso»), 55 «Super Cup» with nothing to tell them apart; the country
was written five ways («TUR», «TR», «Brazil», «INT», nothing: 471) and 23 leagues were typed a cup or the other way round).

In this order:
  1. stages: FotMob files a round under a stage's number («FotMob 901234», the competition's Arabic name). A record with such
     a name and a stage's number is joined to the one competition of that Arabic name with a name and a number of its own,
     or to the one graph/comp_meta.yaml `stages` gives; with no Arabic name and nothing filed under it, it is removed;
  2. a league known by schochastics' slug takes its country's name («Burkina Faso Premier League»);
  3. the country is written one way (graph/countries.py); a region is a scope, not a country; a competition with none takes
     the country of its clubs when 85% of 3 or more are of one, and is international when they are of three or more;
  4. the kind: games between national teams make a tournament (whatever the kind was); a «cup» played as a league is a league, a «league» named a
     cup is a cup, a super cup by name is a super cup. Never the competitions of the index (competitions.yaml);
  5. graph/comp_meta.yaml `names`, over everything;
  6. a name two competitions share takes the country: «Moldova Super Cup», «كأس السوبر (مولدوفا)».
  7. a record that holds several FotMob numbers (a stage joined to it) keeps one as `fotmob`: the index's, else its own
     lowest; the others stay as `fotmob_stage`. The files of a competition are written under its FotMob number, and with two
     the last read won: the Champions League under a qualifying stage's number.
Rebuilt in every build; runs after graph/load/comp_names.py (the Arabic names) and before graph/load/mens.py."""
import json
import os
import re
from collections import Counter, defaultdict
from statistics import median

import yaml

from graph.countries import NATIONS, canon
from graph.load.same_comp import CUP
from graph.load.teams import fold

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CURATED = os.path.join(ROOT, "graph", "comp_meta.yaml")
PLACEHOLDER = re.compile(r"^FotMob \S+$")
SLUG = re.compile(r"^[a-z]+(-[a-z]+)*$")
SUPER = re.compile(r"\b(super ?cup|supercopa|supercoppa|supertaca|supercupa|superpokal|superkupa|community shield|charity shield|trophee des champions)\b")
STAGE = re.compile(r"\b(qualif\w*|play ?offs?|preliminary)\b")
LEAGUE = re.compile(r"\b(league|liga|ligue|lig|division|divisao|serie|bundesliga|championship|premier|eredivisie|superliga)\b")
REGION = {"int": "international", "international": "international", "world": "world", "asia": "asia", "europe": "europe",
          "africa": "africa", "south america": "americas", "north america": "americas", "oceania": "oceania"}
FIELDS = ("name", "name_ar", "kind", "country", "scope", "tier")
SHARE, CLUBS, HOME = 0.85, 3, 0.6           # a competition's country: this share of this many clubs; a club's: of its games
NATIONAL = 0.8                             # games between national teams
SEASONS, PLAYED, GAMES, SIDES = 3, 0.8, 10, 6


def curated(path=CURATED):
    d = yaml.safe_load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    return (d or {}).get("names") or {}, (d or {}).get("stages") or {}


def arabic(s):
    s = re.sub(r"[ً-ْـ]", "", s or "")
    return " ".join(s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه").split())


def lands():
    """code -> (the country in English, in Arabic): news/nations.json, whose Arabic spellings hold a national team's names too
    («المنتخب اللبناني», «الفراعنة»): the shortest one that is not a team's is the country"""
    nat = json.load(open(NATIONS, encoding="utf-8"))
    en, ar = {}, {}
    for name, code in nat["en"].items():
        en.setdefault(code, name.replace(" & ", " and "))
    for code, names in nat["names"].items():
        own = [x for x in names if re.search(r"[؀-ۿ]", x) and "منتخب" not in x]
        if own:
            ar[code] = min(own, key=len)
    en.update({"SU": "Soviet", "YU": "Yugoslav", "DD": "East German", "CS": "Czechoslovak", "HK": "Hong Kong", "MO": "Macau", "CD": "DR Congo",
               "CG": "Congo", "MM": "Myanmar", "PS": "Palestine", "GB-ENG": "England", "GB-SCT": "Scotland", "GB-WLS": "Wales",
               "GB-NIR": "Northern Ireland", "PF": "Tahiti", "AE": "UAE", "US": "USA", "TR": "Turkey"})
    ar.update({"SU": "الاتحاد السوفيتي", "YU": "يوغوسلافيا", "DD": "ألمانيا الشرقية", "CS": "تشيكوسلوفاكيا", "CD": "الكونغو الديمقراطية",
               "CG": "الكونغو", "KR": "كوريا الجنوبية"})
    return en, ar


def index_ids():
    try:
        import config
        return {str(c["id"]) for c in config.competitions()}
    except Exception:
        return set()


def is_stage(sid):
    return not re.fullmatch(r"\d+", sid) or int(sid) == 0 or int(sid) >= 100000


def load(G, reg, S, path=CURATED):
    names, stages = curated(path)
    c = G.c
    q = lambda s, p=(): c.execute(s, p).fetchall()
    out = Counter()

    def cid_of(key):
        src, sid = str(key).split("|", 1)
        row = c.execute("SELECT tifo_id FROM xref WHERE type='competition' AND source=? AND source_id=?", (src, sid)).fetchone()
        cid = row[0] if row else reg.get("competition", src, sid)
        gone = G.merged.get("competition", {})
        while cid in gone:
            cid = gone[cid]
        return cid if cid is not None and c.execute("SELECT 1 FROM competition WHERE cid=?", (cid,)).fetchone() else None

    fixed = {cid_of(k): v for k, v in names.items()}
    fixed.pop(None, None)
    fm = defaultdict(set)
    for cid, sid in q("SELECT tifo_id, source_id FROM xref WHERE type='competition' AND source='fotmob'"):
        fm[cid].add(str(sid))
    listed = index_ids()
    index = {cid for cid, ids in fm.items() if ids & listed}

    # 1. stages
    rows = q("SELECT cid, name, name_ar FROM competition")
    real = defaultdict(set)                    # an Arabic name -> the competitions of that name with a name and a number
    for cid, name, name_ar in rows:
        if name and not PLACEHOLDER.match(name) and name_ar and any(not is_stage(x) for x in fm[cid]):
            real[arabic(name_ar)].add(cid)
    parent = {arabic(k): cid_of(f"fotmob|{v}") for k, v in stages.items()}
    join, drop = [], []
    for cid, name, name_ar in rows:
        if not name or not PLACEHOLDER.match(name) or cid in fixed or not fm[cid] or not all(is_stage(x) for x in fm[cid]):
            continue
        ar = arabic(name_ar)
        keep = parent.get(ar) or (next(iter(real[ar])) if ar and len(real[ar]) == 1 else None)
        if keep and keep != cid:
            join.append((cid, keep))
        elif not ar and not c.execute("""SELECT 1 FROM edition e WHERE e.cid=? AND (EXISTS(SELECT 1 FROM match m WHERE m.eid=e.eid)
                                          OR EXISTS(SELECT 1 FROM honour h WHERE h.eid=e.eid) OR EXISTS(SELECT 1 FROM standing s WHERE s.eid=e.eid))""",
                                      (cid,)).fetchone() and not c.execute("SELECT 1 FROM player_season WHERE cid=?", (cid,)).fetchone():
            drop.append(cid)
    for cid, _ in join:                        # the stage's record brings its games, never its name or kind
        c.execute("UPDATE competition SET name=NULL, name_ar=NULL, kind=NULL, country=NULL, scope=NULL, tier=NULL WHERE cid=?", (cid,))
    G.remap_many("competition", join)
    for cid in drop:
        c.execute("DELETE FROM xref WHERE type='edition' AND tifo_id IN (SELECT eid FROM edition WHERE cid=?)", (cid,))
        c.execute("DELETE FROM edition WHERE cid=?", (cid,))
        c.execute("DELETE FROM xref WHERE type='competition' AND tifo_id=?", (cid,))
        c.execute("DELETE FROM competition WHERE cid=?", (cid,))
    out["stages_joined"], out["stages_removed"] = len(join), len(drop)

    # 3a. one spelling of the country; a region is a scope
    for cid, country, scope in q("SELECT cid, country, scope FROM competition WHERE country IS NOT NULL"):
        code = canon(country)
        if code != country:
            region = REGION.get(fold(country) or "")
            c.execute("UPDATE competition SET country=?, scope=COALESCE(scope, ?) WHERE cid=?", (code, region, cid))
            out["countries_respelt" if code else "regions" if region else "countries_unknown"] += 1

    # 2. schochastics' slug
    en, ar = lands()
    for cid, name, name_ar, country, slug in q("""SELECT c.cid, c.name, c.name_ar, c.country, x.source_id FROM competition c
                                                  JOIN xref x ON x.type='competition' AND x.tifo_id=c.cid AND x.source='sch'"""):
        if name != slug or not SLUG.match(slug or "") or (fixed.get(cid) or {}).get("name"):
            continue
        land = en.get(country) or slug.replace("-", " ").title()
        c.execute("UPDATE competition SET name=? WHERE cid=?", (f"{land} Premier League" if "الممتاز" in (name_ar or "") else f"{land} League", cid))
        out["slugs_named"] += 1

    # the games: who played in what
    national = {tid for (tid,) in q("SELECT tid FROM team WHERE kind='national'")}
    comp = {cid: [name, name_ar, kind, country, scope] for cid, name, name_ar, kind, country, scope in
            q("SELECT cid, name, name_ar, kind, country, scope FROM competition")}
    sides = defaultdict(set)                    # competition -> its clubs
    nats = defaultdict(lambda: [0, 0])          # competition -> [games between national teams, games]
    home = defaultdict(Counter)                 # club -> the countries of its games
    played = defaultdict(Counter)               # edition -> club -> games
    of = {}
    for eid, cid, h, a in q("SELECT m.eid, e.cid, m.home, m.away FROM match m JOIN edition e ON e.eid=m.eid WHERE m.home IS NOT NULL AND m.away IS NOT NULL"):
        if cid not in comp:
            continue
        of[eid] = cid
        sides[cid] |= {h, a}
        nats[cid][1] += 1
        nats[cid][0] += h in national and a in national
        played[eid][h] += 1
        played[eid][a] += 1
        if comp[cid][3]:
            home[h][comp[cid][3]] += 1
            home[a][comp[cid][3]] += 1
    for cid, tid in q("SELECT DISTINCT e.cid, h.tid FROM honour h JOIN edition e ON e.eid=h.eid WHERE h.tid IS NOT NULL"):
        if cid in comp and not nats[cid][1]:
            sides[cid].add(tid)
    land_of = {t: n.most_common(1)[0][0] for t, n in home.items() if t not in national and n.most_common(1)[0][1] >= HOME * sum(n.values())}

    # 4. the kind, by the games and the name
    league_like = Counter()                    # competition -> seasons played as a league; seasons with games enough
    seasons = Counter()
    for eid, n in played.items():
        games = sum(n.values()) // 2
        if games >= GAMES:
            seasons[of[eid]] += 1
            league_like[of[eid]] += len(n) >= SIDES and median(n.values()) >= len(n) - 1
    for cid, (name, name_ar, kind, country, scope) in comp.items():
        if kind == "award" or cid in index or (fixed.get(cid) or {}).get("kind"):
            continue
        f, a = fold(name or ""), arabic(name_ar)
        cup = bool(CUP.search(f)) or (a.startswith(("كاس ", "كأس ")) and not LEAGUE.search(f))
        by_play = seasons[cid] >= SEASONS and league_like[cid] >= PLAYED * seasons[cid]
        new = kind
        if kind in (None, "cup", "league") and nats[cid][1] and nats[cid][0] >= NATIONAL * nats[cid][1]:
            new = "tournament"
            if not scope:
                c.execute("UPDATE competition SET scope='international' WHERE cid=?", (cid,))
                comp[cid][4] = "international"
        elif SUPER.search(f) or a.startswith("كاس السوبر"):
            new = "supercup" if not by_play else kind
        elif kind in ("cup", None) and by_play and not cup:
            new = "league"
        elif kind == "league" and cup and not by_play:
            new = "cup"
        elif kind is None and LEAGUE.search(f) and not cup and not STAGE.search(f):
            new = "league"
        if new != kind:
            c.execute("UPDATE competition SET kind=? WHERE cid=?", (new, cid))
            comp[cid][2] = new
            out[f"kind_{new}"] += 1

    # 3b. the country of a competition with none: its clubs'
    for cid, (name, name_ar, kind, country, scope) in comp.items():
        if country or kind in ("award", "tournament") or cid in fixed:
            continue
        n = Counter(land_of[t] for t in sides[cid] if t in land_of)
        total = sum(n.values())
        if total < CLUBS:
            continue
        top, k = n.most_common(1)[0]
        if k >= SHARE * total and not scope:
            c.execute("UPDATE competition SET country=?, scope='national' WHERE cid=?", (top, cid))
            out["countries_found"] += 1
        elif len(n) >= 3 and k < 0.5 * total and not scope:
            c.execute("UPDATE competition SET scope='international' WHERE cid=?", (cid,))
            out["international"] += 1

    # 5. the curated names, over everything
    for cid, d in fixed.items():
        d = {k: (canon(v) or v if k == "country" else v) for k, v in d.items() if k in FIELDS}
        if d:
            c.execute(f"UPDATE competition SET {', '.join(k + '=?' for k in d)} WHERE cid=?", list(d.values()) + [cid])
            out["curated"] += 1

    c.execute("UPDATE competition SET scope='national' WHERE scope IS NULL AND country IS NOT NULL AND (kind IS NULL OR kind!='award')")

    # 6. a name two competitions share takes the country
    rows = q("SELECT cid, name, name_ar, country FROM competition WHERE kind IS NULL OR kind!='award'")
    for col, how in ((1, lambda n, code: f"{en[code]} {n}" if en.get(code) and fold(en[code]) not in fold(n) else None),
                     (2, lambda n, code: f"{n} ({ar[code]})" if ar.get(code) and arabic(ar[code]) not in arabic(n) else None)):
        shared = Counter(r[col] for r in rows if r[col])
        for r in rows:
            cid, n, code = r[0], r[col], r[3]
            if not n or shared[n] < 2 or not code or cid in index or (fixed.get(cid) or {}).get(FIELDS[col - 1]):
                continue
            new = how(n, code)
            if new:
                c.execute(f"UPDATE competition SET {FIELDS[col - 1]}=? WHERE cid=?", (new, cid))
                out["names_told_apart"] += 1
    # 7. one FotMob number a competition: every reader takes a record's FotMob id as the one it is published under
    held = defaultdict(list)
    for cid, sid in q("SELECT tifo_id, source_id FROM xref WHERE type='competition' AND source='fotmob'"):
        held[cid].append(str(sid))
    for cid, ids in held.items():
        if len(ids) < 2:
            continue
        own = min(ids, key=lambda x: (x not in listed, is_stage(x), int(x) if x.isdigit() else 0, x))
        for sid in ids:
            if sid != own:
                c.execute("UPDATE OR REPLACE xref SET source='fotmob_stage' WHERE type='competition' AND tifo_id=? AND source='fotmob' AND source_id=?", (cid, sid))
                out["numbers_set_aside"] += 1
    out["unnamed"] = sum(bool(PLACEHOLDER.match(n or "")) for (n,) in q("SELECT name FROM competition"))
    c.commit()
    return dict(out)
