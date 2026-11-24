"""Wikidata's facts (CC0) for what the graph already holds, asked of QLever's copy (qlever.dev/api/wikidata, one query a
property, seconds each): a club's founding year, country, Arabic name and home ground; the ground's capacity, city and
coordinates; a player's position, height, nationality, birthplace, and the day he died. 24 Nov 2026 the graph had no
founding year and no home ground for any of its 44,924 teams, no capacity for any of its 2,410 stadiums, and no position
for 193,819 of its 232,811 players.

Who is who:
  * a club by its Transfermarkt id (xref «tm» against P7223), one item to one club; a national team never;
  * a player by his Wikidata item (xref «wikidata»), else by his Transfermarkt id (P2446), else by the day he was born
    with his exact folded name, one man on each side (23,712 of FotMob's players on the first count): the last two write
    his item into xref, so his Arabic aliases and his photo follow;
  * a stadium by its name when one ground carries it on each side and the countries do not disagree, never a bare
    «Municipal Stadium»; a club's home ground the graph does not hold is minted by its item, unless its name is one the
    graph holds for a ground that is not it (load/tidy would join the two).
Only a man's item (P21), only a single value where two would be a guess (two founding years, two birthplaces), a field the
graph has is never touched (Graph.put: Wikidata is the last source), and a year alone is never a birthday.
Fetched weekly into db/.cache/wd/, each file's last copy kept in S3 state for a day QLever does not answer."""
import gzip
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

from graph.countries import canon

URL = "https://qlever.dev/api/wikidata"
STATE = "state/graph/wd/"
PRE = ("PREFIX wd: <http://www.wikidata.org/entity/> PREFIX wdt: <http://www.wikidata.org/prop/direct/> "
       "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> PREFIX p: <http://www.wikidata.org/prop/> "
       "PREFIX psv: <http://www.wikidata.org/prop/statement/value/> PREFIX wikibase: <http://wikiba.se/ontology#> ")
CLUB = "?c wdt:P7223 ?x0 ."
MAN = "?c wdt:P106 wd:Q937857 ."
VENUE = "?x wdt:P7223 ?x0 . ?x wdt:P115 ?c ."
QUERIES = {
    "club_tm": "SELECT ?c ?v WHERE { ?c wdt:P7223 ?v }",
    "club_founded": f"SELECT DISTINCT ?c ?v WHERE {{ {CLUB} ?c wdt:P571 ?v }}",
    "club_venue": f"SELECT DISTINCT ?c ?v WHERE {{ {CLUB} ?c wdt:P115 ?v }}",
    "club_country": f"SELECT DISTINCT ?c ?v WHERE {{ {CLUB} ?c wdt:P17 ?k . ?k wdt:P298 ?v }}",
    "club_ar": f"SELECT DISTINCT ?c ?v WHERE {{ {CLUB} ?c rdfs:label ?v FILTER(lang(?v)='ar') }}",
    "venue_cap": f"SELECT DISTINCT ?c ?v WHERE {{ {VENUE} ?c wdt:P1083 ?v }}",
    "venue_coord": f"SELECT DISTINCT ?c ?v WHERE {{ {VENUE} ?c wdt:P625 ?v }}",
    "venue_en": f"SELECT DISTINCT ?c ?v WHERE {{ {VENUE} ?c rdfs:label ?v FILTER(lang(?v)='en') }}",
    "venue_ar": f"SELECT DISTINCT ?c ?v WHERE {{ {VENUE} ?c rdfs:label ?v FILTER(lang(?v)='ar') }}",
    "venue_country": f"SELECT DISTINCT ?c ?v WHERE {{ {VENUE} ?c wdt:P17 ?k . ?k wdt:P298 ?v }}",
    "venue_city": f"SELECT DISTINCT ?c ?v WHERE {{ {VENUE} ?c wdt:P131 ?k . ?k rdfs:label ?v FILTER(lang(?v)='en') }}",
    "man_tm": "SELECT ?c ?v WHERE { ?c wdt:P2446 ?v }",
    "man_sex": f"SELECT ?c ?v WHERE {{ {MAN} ?c wdt:P21 ?v }}",
    "man_born": f"SELECT ?c ?v WHERE {{ {MAN} ?c wdt:P569 ?v }}",
    "man_died": f"SELECT ?c ?v WHERE {{ {MAN} ?c wdt:P570 ?v }}",
    "man_height": f"SELECT ?c ?v ?u WHERE {{ {MAN} ?c p:P2048/psv:P2048 ?n . ?n wikibase:quantityAmount ?v ; wikibase:quantityUnit ?u }}",
    "man_pos": f"SELECT ?c ?v WHERE {{ {MAN} ?c wdt:P413 ?v }}",
    "man_country": f"SELECT ?c ?v WHERE {{ {MAN} ?c wdt:P27 ?k . ?k wdt:P298 ?v }}",
    "man_sport": f"SELECT ?c ?v WHERE {{ {MAN} ?c wdt:P1532 ?k . ?k rdfs:label ?v FILTER(lang(?v)='en') }}",
    "man_en": f"SELECT ?c ?v WHERE {{ {MAN} ?c rdfs:label ?v FILTER(lang(?v)='en') }}",
    "man_ar": f"SELECT ?c ?v WHERE {{ {MAN} ?c rdfs:label ?v FILTER(lang(?v)='ar') }}",
    "man_place": f"SELECT ?c ?v WHERE {{ {MAN} ?c wdt:P19 ?k . ?k rdfs:label ?v FILTER(lang(?v)='en') }}",
}
MALE = "Q6581097"
# P413 in the words the pages read (site/lib/person_view.cjs POS, FotMob's where it has one)
POSITION = {"Q201330": "Goalkeeper", "Q172964": "Goalkeeper", "Q336286": "Defender", "Q90173132": "Defender", "Q904289": "Defender",
            "Q268258": "Center Back", "Q193592": "Midfielder", "Q8025128": "Midfielder", "Q16501245": "Midfielder",
            "Q18691898": "Defensive Midfielder", "Q6008848": "Central Midfielder", "Q90326494": "Attacking Midfielder",
            "Q280658": "Forward", "Q3446915": "Forward", "Q6037916": "Forward", "Q9731197": "Striker",
            "Q114358150": "Right Winger", "Q114358158": "Left Winger"}
LINE = {"Goalkeeper": "Goalkeeper", "Defender": "Defender", "Center Back": "Defender", "Midfielder": "Midfielder", "Defensive Midfielder": "Midfielder",
        "Central Midfielder": "Midfielder", "Attacking Midfielder": "Midfielder", "Forward": "Forward", "Striker": "Forward",
        "Right Winger": "Forward", "Left Winger": "Forward"}
UNIT = {"Q174728": 1.0, "Q11573": 100.0, "Q218593": 2.54}       # centimetre, metre, inch
GENERIC = re.compile(r"^(?:(?:estadio|stadion|stadium|stade|stadio|estadi|estadio de|arena|sports|city|central|national|olympic|municipal|"
                     r"comunale|communal|park|ground|field|complex|centre|center|the|de|del|do|da|la|el|al)\s*)+$")
_FOLD = str.maketrans({"æ": "ae", "Æ": "ae", "ø": "o", "Ø": "o", "ß": "ss", "đ": "d", "ł": "l", "ı": "i", "œ": "oe"})


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "").translate(_FOLD)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def parse(text):
    """{item: [value, ...]} of one answer (tab separated, a header line): an item or a unit as its Q number, a literal bare;
    a third column makes the value a pair"""
    out = defaultdict(list)

    def cell(v):
        v = v.strip()
        if v.startswith('"'):
            return v[1:v.rindex('"')]
        if v.startswith("<"):
            return v.rsplit("/", 1)[-1].rstrip(">")
        return v

    for line in text.split("\n")[1:]:
        p = line.split("\t")
        if len(p) < 2 or not p[0]:
            continue
        v = cell(p[1]) if len(p) == 2 else (cell(p[1]), cell(p[2]))
        k = cell(p[0])
        if v not in out[k]:
            out[k].append(v)
    return dict(out)


def fetch(S, max_age_days=7, get=None):
    """db/.cache/wd/<name>.tsv for every query: asked again after a week, kept in S3 state, read back from there when
    QLever does not answer and the build has no copy"""
    d = os.path.join(S.db, "wd")
    os.makedirs(d, exist_ok=True)

    def ask(q):
        req = urllib.request.Request(URL, data=urllib.parse.urlencode({"query": PRE + q, "action": "tsv_export"}).encode(),
                                     headers={"User-Agent": "elyoxe-tifo/0.1 (https://tifo.elyoxe.com; hello@elyoxe.com)", "Accept": "text/tab-separated-values"})
        return urllib.request.urlopen(req, timeout=600).read()

    n = {"fetched": 0, "kept": 0, "state": 0, "missing": 0}
    for name, q in QUERIES.items():
        p = os.path.join(d, name + ".tsv")
        if os.path.exists(p) and time.time() - os.path.getmtime(p) < max_age_days * 86400:
            n["kept"] += 1
            continue
        raw = None
        try:
            raw = (get or ask)(q)
            if raw.count(b"\n") < 3:
                raw = None
        except Exception as e:
            print(f"wikidata {name}: {type(e).__name__} {str(e)[:120]}", flush=True)
        if raw is not None:
            n["fetched"] += 1
            if S.s3:
                try:
                    S.store().b.put(STATE + name + ".tsv", gzip.compress(raw, 6, mtime=0), "text/tab-separated-values", "no-store", "gzip")
                except Exception as e:
                    print(f"wikidata {name} state: {type(e).__name__} {str(e)[:120]}", flush=True)
        elif os.path.exists(p):
            n["kept"] += 1
            continue
        elif S.s3:
            try:
                raw = S.store().b.get(STATE + name + ".tsv")
            except Exception:
                raw = None
            if raw and raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            n["state" if raw else "missing"] += 1
        else:
            n["missing"] += 1
        if raw:
            with open(p + ".tmp", "wb") as f:
                f.write(raw)
            os.replace(p + ".tmp", p)
    return n


def read(S):
    """{query: {item: [value, ...]}} of the files there are"""
    F = {}
    for name in QUERIES:
        try:
            with open(os.path.join(S.db, "wd", name + ".tsv"), encoding="utf-8") as f:
                F[name] = parse(f.read())
        except OSError:
            pass
    return F


def house(G, table, col):
    """{country in one spelling: the spelling this column uses most} («BR»: «BRA» for a player, «Brazil» for a coach or a club)"""
    c = defaultdict(Counter)
    for v, n in G.c.execute(f"SELECT {col}, count(*) FROM {table} WHERE {col} IS NOT NULL AND {col}<>'' GROUP BY 1").fetchall():
        k = canon(v)
        if k:
            c[k][v] += n
    return {k: sorted(vs.items(), key=lambda x: (-x[1], x[0]))[0][0] for k, vs in c.items()}


def one(vs):
    return vs[0] if vs and len(vs) == 1 else None


def day(vs):
    """the one day of the values, never a year alone (Wikidata writes it as its 1 January)"""
    ds = {str(v)[:10] for v in vs or ()}
    d = next(iter(ds)) if len(ds) == 1 else None
    return d if d and re.fullmatch(r"\d{4}-\d\d-\d\d", d) and not d.endswith("-01-01") else None


def country_of(codes, names=(), GB=False):
    """the one country of the values, as graph.countries writes it; the United Kingdom is no football country"""
    for vs in (names, codes):
        ks = {canon(v) for v in vs or ()} - {None}
        if len(ks) == 1:
            k = next(iter(ks))
            if k != "GB" or GB:
                return k
        if ks:
            return None
    return None


def height_of(vs):
    hs = set()
    for v in vs or ():
        try:
            h = float(v[0]) * UNIT[v[1]]
        except (KeyError, ValueError, TypeError, IndexError):
            continue
        if 150 <= h <= 215:
            hs.add(round(h))
    return next(iter(hs)) if len(hs) == 1 else None


def position_of(vs):
    """his one position, or the line his positions share"""
    ps = {POSITION[v] for v in vs or () if v in POSITION}
    if len(ps) == 1:
        return next(iter(ps))
    ls = {LINE[p] for p in ps}
    return next(iter(ls)) if len(ls) == 1 else None


def teams(G, reg, F):
    n = Counter()
    by_tm = defaultdict(set)
    for qid, ids in F.get("club_tm", {}).items():
        for i in ids:
            by_tm[str(i)].add(qid)
    of = defaultdict(set)
    kind = {}
    for tid, k, tmid in G.c.execute("SELECT t.tid, t.kind, x.source_id FROM team t JOIN xref x ON x.type='team' AND x.tifo_id=t.tid AND x.source='tm'").fetchall():
        kind[tid] = k
        of[tid] |= by_tm.get(str(tmid), set())
    used = Counter(q for qs in of.values() if len(qs) == 1 for q in qs)
    link = {tid: next(iter(qs)) for tid, qs in of.items() if len(qs) == 1 and used[next(iter(qs))] == 1 and kind[tid] != "national"}
    names = house(G, "team", "country")
    home = {}
    for tid, qid in sorted(link.items()):
        n["clubs"] += 1
        row = {"tid": tid}
        ys = {str(v)[:4] for v in F.get("club_founded", {}).get(qid, ())}
        y = next(iter(ys)) if len(ys) == 1 else ""
        if y.isdigit() and 1800 <= int(y) <= int(time.strftime("%Y")):
            row["founded"] = int(y)
            n["founded"] += 1
        c = names.get(country_of(F.get("club_country", {}).get(qid)))
        if c:
            row["country"] = c
        ar = one(F.get("club_ar", {}).get(qid))
        if ar:
            row["name_ar"] = ar
        if len(row) > 1:
            G.put("team", row, "wikidata")
        if reg.alias("team", "wikidata", qid, tid):
            G.xref("team", tid, "wikidata", qid, "tm-id", 0.95)
        v = one(F.get("club_venue", {}).get(qid))
        if v:
            home[tid] = v
    return n, home


def stadiums(G, reg, F, home):
    """the grounds: the graph's own by name, a club's home ground it does not hold minted; then each club's ground"""
    n = Counter()
    en, names = F.get("venue_en", {}), house(G, "stadium", "country")
    names.update({k: v for k, v in house(G, "team", "country").items() if k not in names})
    label = defaultdict(set)
    for qid, vs in en.items():
        for v in vs:
            label[fold(v)].add(qid)
    ours = defaultdict(list)
    for sid, name, country in G.c.execute("SELECT sid, name, country FROM stadium").fetchall():
        ours[fold(name)].append((sid, country))
    where = lambda qid: country_of(F.get("venue_country", {}).get(qid), GB=True)
    sid_of = {}
    for f, rows in ours.items():
        qs = label.get(f) or ()
        if len(rows) != 1 or len(qs) != 1 or not f or GENERIC.match(f + " ") or len(f) < 5:
            continue
        (sid, country), qid = rows[0], next(iter(qs))
        a, b = canon(country), where(qid)
        if a and b and a != b and not (b == "GB" and a.startswith("GB")):
            n["another_country"] += 1
            continue
        if reg.alias("stadium", "wikidata", qid, sid):
            sid_of[qid] = sid
            G.xref("stadium", sid, "wikidata", qid, "name", 0.9)
            n["known"] += 1
    new = sorted(set(home.values()) - set(sid_of))
    shared = Counter(fold((en.get(qid) or [""])[0]) for qid in new)
    held = {f for f, rows in ours.items() if not any(sid in set(sid_of.values()) for sid, _ in rows)}
    for qid in new:
        name = (en.get(qid) or [None])[0]
        if not name:
            continue
        f = fold(name)
        # tidy joins grounds of one name unless their towns differ: a name of ours that is not this ground, or a name two
        # of these share with a town missing, would be joined to it
        if not f or f in held or (shared[f] > 1 and not one(F.get("venue_city", {}).get(qid))):
            n["name_of_another"] += 1
            continue
        have = reg.get("stadium", "wikidata", qid)
        sid_of[qid] = have or reg.mint("stadium", "wikidata", qid)
        G.put("stadium", {"sid": sid_of[qid], "name": name}, "wikidata")
        G.xref("stadium", sid_of[qid], "wikidata", qid, "wikidata-native")
        n["new"] += 1
    for qid, sid in sorted(sid_of.items()):
        row = {"sid": sid, "name_ar": one(F.get("venue_ar", {}).get(qid)), "city": one(F.get("venue_city", {}).get(qid))}
        b = where(qid)
        if b and b != "GB":
            row["country"] = names.get(b)
        caps = []
        for v in F.get("venue_cap", {}).get(qid, ()):
            try:
                caps.append(int(float(v)))
            except (TypeError, ValueError):
                pass
        caps = [c for c in caps if 100 <= c <= 250000]
        if caps:
            row["capacity"] = max(caps)
            n["capacity"] += 1
        m = re.match(r"POINT\((-?[\d.]+) (-?[\d.]+)\)", str((F.get("venue_coord", {}).get(qid) or [""])[0]), re.I)
        if m:
            row["lon"], row["lat"] = float(m.group(1)), float(m.group(2))
        G.put("stadium", row, "wikidata")
    for tid, qid in sorted(home.items()):
        if qid in sid_of:
            G.put("team", {"tid": tid, "sid": sid_of[qid]}, "wikidata")
            n["home"] += 1
    return n


def players(G, reg, F):
    n = Counter()
    male = {q for q, v in F.get("man_sex", {}).items() if v == [MALE]}
    born, en = F.get("man_born", {}), F.get("man_en", {})
    rows = {r[0]: r for r in G.c.execute("SELECT pid, name, name_ar, born FROM player").fetchall()}
    link = {}
    of = defaultdict(set)
    for pid, qid in G.c.execute("SELECT tifo_id, source_id FROM xref WHERE type='player' AND source='wikidata'").fetchall():
        of[pid].add(qid)
    for pid, qs in of.items():
        if len(qs) == 1 and pid in rows:
            link[pid] = next(iter(qs))
    n["by_item"] = len(link)
    taken = {q for qs in of.values() for q in qs}
    by_tm = defaultdict(set)
    for qid, ids in F.get("man_tm", {}).items():
        for i in ids:
            by_tm[str(i)].add(qid)
    of = defaultdict(set)
    for pid, tmid in G.c.execute("SELECT tifo_id, source_id FROM xref WHERE type='player' AND source='tm'").fetchall():
        if pid not in link and pid in rows:
            of[pid] |= by_tm.get(str(tmid), set())
    used = Counter(q for qs in of.values() if len(qs) == 1 for q in qs)
    new = [(pid, next(iter(qs)), "tm-id") for pid, qs in of.items() if len(qs) == 1 and used[next(iter(qs))] == 1]
    seen = {p for p, _, _ in new}
    theirs = defaultdict(set)
    for qid in male:
        d = day(born.get(qid))
        if d:
            for nm in en.get(qid, ()):
                theirs[(d, fold(nm))].add(qid)
    mine = defaultdict(set)
    for pid, name, _, b in rows.values():
        if b and len(b) >= 10 and name and fold(name):
            mine[(b[:10], fold(name))].add(pid)
    for k, pids in mine.items():
        qs = theirs.get(k) or ()
        if len(pids) == 1 and len(qs) == 1:
            pid = next(iter(pids))
            if pid not in link and pid not in seen:
                new.append((pid, next(iter(qs)), "born-name"))
    for pid, qid, how in sorted(new):
        if qid in taken or qid not in male or not reg.alias("player", "wikidata", qid, pid):
            n["refused"] += 1
            continue
        taken.add(qid)
        link[pid] = qid
        G.xref("player", pid, "wikidata", qid, how, 0.95)
        n["by_" + how.replace("-", "_")] += 1
    codes = house(G, "player", "nationality")
    for pid, qid in sorted(link.items()):
        if qid not in male:
            n["not_a_man"] += 1
            continue
        _, name, ar, b = rows[pid]
        row = {"pid": pid, "died": day(F.get("man_died", {}).get(qid)), "birthplace": one(F.get("man_place", {}).get(qid)),
               "nationality": codes.get(country_of(F.get("man_country", {}).get(qid), F.get("man_sport", {}).get(qid))),
               "position": position_of(F.get("man_pos", {}).get(qid)), "height": height_of(F.get("man_height", {}).get(qid))}
        if not b:
            row["born"] = day(born.get(qid))
        a = one(F.get("man_ar", {}).get(qid))
        if a and not ar and len(a.split()) <= len((name or "").split()) + 1:
            row["name_ar"] = a
        row = {k: v for k, v in row.items() if v not in (None, "")}
        if len(row) > 1:
            G.put("player", row, "wikidata")
            n["filled"] += 1
    return n, male


def coaches(G, F, male):
    n = Counter()
    names = house(G, "coach", "nationality")
    names.update({k: v for k, v in house(G, "team", "country").items() if k not in names})
    for kid, qid in G.c.execute("""SELECT x.tifo_id, x.source_id FROM xref x JOIN coach c ON c.kid=x.tifo_id
                                   WHERE x.type='coach' AND x.source='wikidata' ORDER BY 1""").fetchall():
        if qid not in male:
            continue
        row = {"kid": kid, "born": day(F.get("man_born", {}).get(qid)),
               "nationality": names.get(country_of(F.get("man_country", {}).get(qid), F.get("man_sport", {}).get(qid)))}
        row = {k: v for k, v in row.items() if v not in (None, "")}
        if len(row) > 1:
            G.put("coach", row, "wikidata")
            n["filled"] += 1
    return n


def apply(G, reg, F):
    t, home = teams(G, reg, F)
    s = stadiums(G, reg, F, home)
    p, male = players(G, reg, F)
    c = coaches(G, F, male)
    out = {f"team_{k}": v for k, v in t.items()}
    out.update({f"stadium_{k}": v for k, v in s.items()})
    out.update({f"player_{k}": v for k, v in p.items()})
    out.update({f"coach_{k}": v for k, v in c.items()})
    return out


def load(G, reg, S):
    F = read(S)
    if "club_tm" not in F and "man_sex" not in F:
        return {"skipped": "no Wikidata files"}
    return apply(G, reg, F)
