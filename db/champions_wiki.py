"""Fill the champions lists Wikidata leaves short (the Arab competitions above all) from Wikipedia's tables.
Runs after db/champions.py; the owner allowed every source (2026-09-30).

    python -m db.champions_wiki [--upload] [--only 329] [--dir DIR]

Per competition: an English Wikipedia page; the table with a year/season column and a champion/winner column and the
most rows is read. A season «1973–74» counts for 1974 (as db/champions.py does with Wikidata's labels). The winner's
name is linked to one of our clubs or national teams by name (FotMob's English name), else it keeps the English name.
Years the list doesn't have are added, marked «wiki»; where both lists name linked teams for a year and they differ,
Wikipedia's winners replace Wikidata's.
--dir DIR reads the lists from DIR/<comp id>.json (db/champions.py --out DIR) and writes them back there, not to the bucket.

Audit 2026-09-30: the fill printed «Sharjah (2024–25 UAE Pro League Runners-up)» as a champion (21 rows), read per-club
summary tables («1», «4», «22» as winners: 38 rows), a sub-header («Saudi Categorization League 1974–1975»), «TBD» and
«(No champion crowned)»; it linked «Al Shabab» (Dubai, merged away in 2017) to Shabab Al Ahli because every word of the
name is in the club's (3 league titles, 4 President's Cups); it kept only the first of two editions ending in the same
year (the 17th Gulf Cup, Qatar 2004); and it filled the Saudi league with «His Majesty's League» 1957–74, the King's Cup.
Now: notes in parentheses are stripped; a winner needs letters and is not TBD / no champion; sub-header rows and per-club
summary tables are skipped; a name links by a two-way word score (shared words over the longer name's, at least 0.6 and
unique) plus an explicit table of renamed clubs; every edition of a year is kept; and nothing is filled before
365Scores' first season or into a season 365 lists with no winner (v1/s365/fm.json).
Wikipedia is asked at most once a second; pages are kept 6 days in db/.cache/wiki/.
"""
import argparse, hashlib, io, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from collections import Counter, defaultdict
from datetime import date

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from store import Store, S3Backend  # noqa: E402
from db.champions import end_year  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
UA = {"User-Agent": "elyoxe-tifo/0.1 (https://tifo.elyoxe.com; hello@elyoxe.com)"}
CACHE, TTL = os.path.join(HERE, ".cache", "wiki"), 6 * 86400
PAGES = {538: "UAE Pro League", 329: "Arabian Gulf Cup", 10474: "Arab Club Champions Cup", 10242: "FIFA Arab Cup", 11026: "UAE Super Cup",
         10074: "Saudi Super Cup", 519: "Egyptian Premier League", 529: "Kuwaiti Premier League", 544: "Tunisian Ligue Professionnelle 1",
         524: "Iraq Stars League", 9943: "UAE President's Cup", 9942: "King's Cup (Saudi Arabia)", 11018: "Emir of Qatar Cup", 9941: "Egypt Cup",
         10314: "Egyptian Super Cup", 11840: "Moroccan Throne Cup", 11027: "UAE League Cup", 10043: "Leagues Cup", 535: "Qatar Stars League",
         536: "Saudi Pro League", 526: "CAF Champions League", 525: "AFC Champions League Elite", 290: "AFC Asian Cup", 530: "Botola",
         516: "Algerian Ligue Professionnelle 1", 9468: "CAF Confederation Cup", 9469: "AFC Champions League Two", 299: "Copa Sudamericana",
         112: "Argentine Primera División"}


ALIAS = {"United Arab Emirates": "UAE", "South Korea": "Korea Republic", "Ivory Coast": "Côte d'Ivoire", "DR Congo": "Congo DR"}
# renamed or merged clubs whose titles the site counts for today's club (the UAE league's own convention, as in
# alltime.yaml and 365Scores): {country: {the name's words: FotMob id}}. Al Shabab (Dubai) is NOT here: it stays itself.
LINEAGE = {"AE": {"ahli": 102119, "ahly": 102119, "ahli dubai": 102119, "ahly dubai": 102119, "oroba": 102124}}
# words that say nothing about which club it is
GENERIC = {"fc", "sc", "cf", "ac", "afc", "cs", "ss", "sd", "cd", "fk", "sk", "club", "clube", "sporting", "sports", "sport", "cultural",
           "athletic", "football", "futbol", "calcio", "de", "du", "la", "le", "el", "al", "the", "saudi"}
# the first season (end year) a competition's list counts from, where the Wikipedia table reaches further back: the Saudi
# league began in 1974–75; its table opens with «His Majesty's League» 1957–74, which RSSSF lists as the King's Cup and the
# clubs' own title counts leave out (Al Hilal 19, Al Ahli 3). 365Scores' list has the same 14 seasons (to fix there too).
START = {536: 1975}
NOT_WINNER = re.compile(r"not (held|awarded|played|completed|finished)|cancel|abandon|suspend|void|no (winner|champion)|unfinished|"
                        r"to be (determined|decided)|^(tbd|tba|tbc|n/?a|none|nan|vacant|withheld)$|^[—–-]+$", re.I)


def words(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return {w for w in re.sub(r"[^a-z0-9]+", " ", s).split() if w not in GENERIC}


def score(a, b):
    """Shared words over the longer name's words: «Sharjah» ~ «Sharjah Cultural Club» 1, «Shabab Al Ahli» ~ «Shabab
    Al-Ahli Dubai FC» 0.67, «Al Shabab» ~ «Shabab Al Ahli» 0.5 (the old every-word rule linked that one)."""
    return len(a & b) / max(len(a), len(b)) if a and b else 0.0


def clean(v):
    v = re.sub(r"\[[^\]]*\]", "", str(v))                 # footnotes
    v = re.sub(r"\([^)]*\)", "", v)                        # title counts, and notes: «Al Ain (2008–09 UAE President's Cup winners)»
    return re.sub(r"\s+", " ", v).strip(" *†‡§")


def year_of(v):
    v = str(v)
    m = re.search(r"(\d{4})\s*[–\-/]\s*(\d{2,4})", v)
    if m:
        a, b = m.group(1), m.group(2)
        if len(b) == 4:
            return b
        y = int(a[:2] + b)
        return str(y + 100 if y < int(a) else y)          # «1999–00» ends in 2000, not 1900
    m = re.search(r"\d{4}", v)
    return m.group(0) if m else None


_last = [0.0]


def tables(page):
    p = os.path.join(CACHE, hashlib.sha1(page.encode()).hexdigest()[:20] + ".html")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < TTL:
        with open(p, encoding="utf-8") as f:
            h = f.read()
    else:
        time.sleep(max(0.0, 1.0 - (time.time() - _last[0])))
        u = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"action": "parse", "page": page, "prop": "text", "format": "json", "redirects": 1})
        try:
            h = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90).read())["parse"]["text"]["*"]
        finally:
            _last[0] = time.time()
        os.makedirs(CACHE, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(h)
    return pd.read_html(io.StringIO(h))


def pick(ts):
    best = None
    for t in ts:
        cols = [" ".join(str(x) for x in (c if isinstance(c, tuple) else (c,))).lower() for c in t.columns]
        # the year column: «season»/«year» before «edition»/«ed.» (Gulf Cup's first column is the edition number); never a
        # «founded» column. The winner column: any other column saying champion/winner (a caption like «Arab Club
        # Champions Cup» repeated over every column must not make the season column the winner column)
        yc = next((i for i, c in enumerate(cols) if re.search(r"season|year", c) and not re.search(r"found|establish", c)), None)
        if yc is None:
            yc = next((i for i, c in enumerate(cols) if re.search(r"edition|ed\.", c)), None)
        wc = next((i for i, c in enumerate(cols) if i != yc and re.search(r"champion|winner", c) and not re.search(r"runner|second|score|times|number|titles|found", c)), None)
        if yc is None or wc is None or yc == wc:
            continue
        rows, summary, counts = [], 0, 0
        for r in t.itertuples(index=False):
            ry, rw = str(r[yc]).strip(), str(r[wc]).strip()
            if ry == rw:                                    # a sub-header spanning the row («Saudi Categorization League 1974–1975»)
                continue
            if re.search(r"\d{4}\D{0,6}[,;]\s*\d{4}", ry):     # «1975, 1977, 1988»: a per-club summary («Club | Titles | Years won»)
                summary += 1; continue
            y, w = year_of(ry), clean(rw)
            if not y or not 1880 <= int(y) <= date.today().year or not w or w.lower() in ("nan", "no competition"):
                continue
            if not re.search(r"[^\W\d_]", w):              # «1», «22»: a count column, not a team
                counts += 1; continue
            if NOT_WINNER.search(w):
                continue
            rows.append((y, w))
        if summary + counts > len(t) * 0.3:
            continue
        if len(rows) >= 3 and (best is None or len(rows) > len(best)):
            best = rows
    return best or []


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); ap.add_argument("--only", type=int)
    ap.add_argument("--dir", help="read and write the lists in this folder (db/champions.py --out DIR) instead of the bucket"); a = ap.parse_args(argv)
    store = Store(S3Backend(BUCKET))
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    comps = {c["id"]: c for c in (store.get_json("index.json") or {}).get("competitions") or []}
    s365 = (store.get_json("s365/fm.json") or {}).get("comps") or {}
    tw = {k: words(t.get("name")) for k, t in teams.items()}

    def link(cid, w):
        """A winner's name -> one of our teams: a renamed club of LINEAGE, else the best two-way word score (at least 0.6,
        and no tie) among the competition's own teams, then its country's, then (continental cups) everywhere; never in
        another country (the UAE's «Al Ahli» is not Saudi Arabia's), never «Al Shabab» -> «Shabab Al Ahli»."""
        ws = words(ALIAS.get(w, w))
        cc = ((comps.get(cid) or {}).get("country") or {}).get("iso2")
        k = " ".join(sorted(ws))
        if k in LINEAGE.get(cc, {}):
            return LINEAGE[cc][k]
        pools = [[k for k, t in teams.items() if cid in (t.get("comps") or [])]]
        if cc:
            pools.append([k for k, t in teams.items() if (t.get("country") or {}).get("iso2") == cc or any(((comps.get(x) or {}).get("country") or {}).get("iso2") == cc for x in t.get("comps") or [])])
        else:
            pools.append(list(teams))
        for pool in pools:
            sc = sorted(((score(ws, tw[k]), k) for k in pool), reverse=True)
            sc = [x for x in sc if x[0] >= 0.6]
            if sc:
                return int(sc[0][1]) if len(sc) == 1 or sc[0][0] > sc[1][0] else None
        return None

    def load(cid):
        p = a.dir and os.path.join(a.dir, f"{cid}.json")
        if p:
            return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
        return store.get_json(f"history/champions/{cid}.json")
    for cid, page in PAGES.items():
        if a.only and cid != a.only:
            continue
        try:
            rows = pick(tables(page))
        except Exception as e:
            print(cid, page, "ERR", e); continue
        doc = load(cid) or {"comp": cid, "champions": [], "counts": [], "source": ""}
        doc["champions"] = [c for c in doc["champions"] if not (len(c) > 4 and c[4] == "wiki")]   # rebuilt every run
        # 365Scores is the referee for its span: nothing before its first season (the Saudi league's «His Majesty's League»
        # 1957–74 on Wikipedia is the King's Cup) and nothing in a season it lists with no winner. Only when every one of
        # its seasons names a year (the Gulf Cup's «خليجي 26» doesn't)
        x365 = (s365.get(str(cid)) or {}).get("champions") or []
        ys365 = [end_year(r[0]) for r in x365]
        if x365 and all(ys365):
            first, void = min(int(y) for y in ys365), {y for r, y in zip(x365, ys365) if not r[1]}
            rows = [(y, w) for y, w in rows if int(y) >= first and y not in void]
        if cid in START:
            rows = [(y, w) for y, w in rows if int(y) >= START[cid]]
            doc["champions"] = [c for c in doc["champions"] if int(c[0]) >= START[cid]]
        # a long Wikipedia list is the better judge of when the competition began: Wikidata items dated before it are
        # mis-dated (the UAE league «1900»)
        if len(rows) >= 20:
            y0 = min(int(y) for y, _ in rows)
            doc["champions"] = [c for c in doc["champions"] if int(c[0]) >= y0 - 1 or (len(c) > 4 and c[4] == "table")]
        # every edition of a year (the 16th and 17th Gulf Cups both end in 2004); a year the list lacks is added; where both
        # name linked teams and they differ, Wikipedia's winners replace the list's (Egypt 2005–06: Wikidata has Zamalek too)
        by_year = defaultdict(list)
        for y, w in rows:
            if w not in by_year[y]:
                by_year[y].append(w)
        added = replaced = 0
        for y, ws in by_year.items():
            new = []
            for w in ws:
                fid = link(cid, w)
                t = teams.get(str(fid)) or {}
                new.append([y, f"fm:{fid}" if fid else "w:" + w, t.get("name_ar") or w, fid, "wiki"])
            old = [c for c in doc["champions"] if c[0] == y]
            if not old:
                doc["champions"] += new; added += len(new)
            elif all(c[3] for c in old + new) and {c[3] for c in old} != {c[3] for c in new}:
                doc["champions"] = [c for c in doc["champions"] if c[0] != y] + new; replaced += 1
        doc["champions"].sort(key=lambda x: x[0])
        cnt = Counter((c[3] or c[1]) for c in doc["champions"])
        first = {}
        for c in doc["champions"]:
            first.setdefault(c[3] or c[1], c)
        doc["counts"] = [[first[k][1], n, first[k][2], first[k][3]] for k, n in cnt.most_common()]
        if "Wikipedia" not in doc.get("source", ""):
            doc["source"] = (doc.get("source") or "") + "; seasons marked «wiki» from English Wikipedia's tables"
        print(cid, page, f"table {len(rows)} rows, {added} added, {replaced} years replaced, now {len(doc['champions'])} ({doc['champions'][0][0] if doc['champions'] else ''}-{doc['champions'][-1][0] if doc['champions'] else ''})")
        if a.dir:
            with open(os.path.join(a.dir, f"{cid}.json"), "w", encoding="utf-8", newline="\n") as f:
                json.dump(doc, f, ensure_ascii=False)
        elif a.upload:
            store.put_json(f"history/champions/{cid}.json", doc, cache="warm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
