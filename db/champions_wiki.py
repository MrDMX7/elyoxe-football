"""Fill the champions lists Wikidata leaves short (the Arab competitions above all) from Wikipedia's tables.
Runs after db/champions.py; the owner allowed every source (2026-09-30).

    python -m db.champions_wiki [--upload] [--only 329]

Per competition: an English Wikipedia page; the table with a year/season column and a champion/winner column and the
most rows is read. A season «1973–74» counts for 1974 (as db/champions.py does with Wikidata's end dates). The winner's
name is linked to one of our clubs or national teams by name (FotMob's English name), else it keeps Wikidata's Arabic
label when one exact English label exists, else the English name. Only the years the list doesn't already have are
added, marked «wiki».
"""
import argparse, io, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from collections import Counter
from datetime import date

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
UA = {"User-Agent": "elyoxe-tifo/0.1 (https://tifo.elyoxe.com; hello@elyoxe.com)"}
PAGES = {538: "UAE Pro League", 329: "Arabian Gulf Cup", 10474: "Arab Club Champions Cup", 10242: "FIFA Arab Cup", 11026: "UAE Super Cup",
         10074: "Saudi Super Cup", 519: "Egyptian Premier League", 529: "Kuwaiti Premier League", 544: "Tunisian Ligue Professionnelle 1",
         524: "Iraq Stars League", 9943: "UAE President's Cup", 9942: "King's Cup (Saudi Arabia)", 11018: "Emir of Qatar Cup", 9941: "Egypt Cup",
         10314: "Egyptian Super Cup", 11840: "Moroccan Throne Cup", 11027: "UAE League Cup", 10043: "Leagues Cup", 535: "Qatar Stars League",
         536: "Saudi Pro League", 526: "CAF Champions League", 525: "AFC Champions League Elite", 290: "AFC Asian Cup", 530: "Botola",
         516: "Algerian Ligue Professionnelle 1", 9468: "CAF Confederation Cup", 9469: "AFC Champions League Two", 299: "Copa Sudamericana",
         112: "Argentine Primera División"}


ALIAS = {"United Arab Emirates": "UAE", "South Korea": "Korea Republic", "Ivory Coast": "Côte d'Ivoire", "DR Congo": "Congo DR"}


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(fc|sc|club|al)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def clean(v):
    v = re.sub(r"\[[^\]]*\]", "", str(v))                 # footnotes
    v = re.sub(r"\(\d+\)", "", v)                          # title counts
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


def tables(page):
    u = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"action": "parse", "page": page, "prop": "text", "format": "json", "redirects": 1})
    h = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90).read())["parse"]["text"]["*"]
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
        rows = [(year_of(r[yc]), clean(r[wc])) for r in t.itertuples(index=False)]
        rows = [(y, w) for y, w in rows if y and 1880 <= int(y) <= date.today().year and w and w.lower() not in ("nan", "not held", "cancelled", "abandoned", "—", "-", "no competition") and not re.search(r"not (held|awarded|played|completed|finished)|cancel|abandon|suspend|void|no winner|unfinished", w, re.I)]
        if len(rows) >= 3 and (best is None or len(rows) > len(best)):
            best = rows
    return best or []


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); ap.add_argument("--only", type=int); a = ap.parse_args(argv)
    store = Store(S3Backend(BUCKET))
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    comps = {c["id"]: c for c in (store.get_json("index.json") or {}).get("competitions") or []}

    def link(cid, w):
        """A winner's name -> one of our teams: exact (folded) name, else every word of it in exactly one team's name.
        Looked for among the competition's own teams, then its country's, then (continental cups) everywhere; never in
        another country (the UAE's «Al Ahli» is not Saudi Arabia's)."""
        f = fold(ALIAS.get(w, w)); ws = set(f.split())
        cc = ((comps.get(cid) or {}).get("country") or {}).get("iso2")
        pools = [[k for k, t in teams.items() if cid in (t.get("comps") or [])]]
        if cc:
            pools.append([k for k, t in teams.items() if (t.get("country") or {}).get("iso2") == cc or any(((comps.get(x) or {}).get("country") or {}).get("iso2") == cc for x in t.get("comps") or [])])
        else:
            pools.append(list(teams))
        for pool in pools:
            exact = [k for k in pool if fold(teams[k].get("name")) == f]
            if len(exact) == 1:
                return int(exact[0])
            sub = [k for k in pool if ws and ws <= set(fold(teams[k].get("name")).split())]
            if len(sub) == 1:
                return int(sub[0])
        return None
    for cid, page in PAGES.items():
        if a.only and cid != a.only:
            continue
        try:
            rows = pick(tables(page))
        except Exception as e:
            print(cid, page, "ERR", e); continue
        doc = store.get_json(f"history/champions/{cid}.json") or {"comp": cid, "champions": [], "counts": [], "source": ""}
        # a long Wikipedia list is the better judge of when the competition began: Wikidata items dated before it are
        # mis-dated (the UAE league «1900»)
        if len(rows) >= 20:
            y0 = min(int(y) for y, _ in rows)
            doc["champions"] = [c for c in doc["champions"] if int(c[0]) >= y0 - 1 or (len(c) > 4 and c[4] == "table")]
        have = {c[0] for c in doc["champions"]}
        added = 0
        for y, w in rows:
            if y in have:
                continue
            fid = link(cid, w)
            t = teams.get(str(fid)) or {}
            doc["champions"].append([y, f"fm:{fid}" if fid else "w:" + w, t.get("name_ar") or w, fid, "wiki"]); have.add(y); added += 1
        doc["champions"].sort(key=lambda x: x[0])
        cnt = Counter((c[3] or c[1]) for c in doc["champions"])
        first = {}
        for c in doc["champions"]:
            first.setdefault(c[3] or c[1], c)
        doc["counts"] = [[first[k][1], n, first[k][2], first[k][3]] for k, n in cnt.most_common()]
        if "Wikipedia" not in doc.get("source", ""):
            doc["source"] = (doc.get("source") or "") + "; seasons marked «wiki» from English Wikipedia's tables"
        print(cid, page, f"table {len(rows)} rows, {added} added, now {len(doc['champions'])} ({doc['champions'][0][0] if doc['champions'] else ''}-{doc['champions'][-1][0] if doc['champions'] else ''})")
        if a.upload and added:
            store.put_json(f"history/champions/{cid}.json", doc, cache="warm")
        time.sleep(0.5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
