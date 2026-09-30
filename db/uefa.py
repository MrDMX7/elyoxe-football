"""UEFA coefficients through history from kassiesa.net (the reference archive of every UEFA ranking since 1960s):
each country's rank (crank<year>.html) and each club's rank (trank<year>.html), one page per year under
data/method1..method5 (UEFA changed the formula; the year's page lives under the method of its time).
Owner's database, 2026-09-30 «كلها».

    python -m db.uefa [--upload]

Out: v1/history/uefa/countries.json {country: [[year, rank, points]]}; v1/history/uefa/club/<fotmob id>.json
{series: [[year, rank, points]]} for our clubs (linked by name within their country).
"""
import argparse, io, json, os, re, sys, time, unicodedata, urllib.request
from collections import defaultdict
from datetime import date

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
CACHE = os.path.join(HERE, ".cache", "uefa")
ABBR = {"Esp": "Spain", "Eng": "England", "Ger": "Germany", "Ita": "Italy", "Fra": "France", "Por": "Portugal", "Ned": "Netherlands", "Bel": "Belgium",
        "Tur": "Turkey", "Sco": "Scotland", "Gre": "Greece", "Frg": "Germany"}
ISO = {"England": "GB-ENG", "Spain": "ES", "Italy": "IT", "Germany": "DE", "France": "FR", "Portugal": "PT", "Netherlands": "NL", "Belgium": "BE",
       "Turkey": "TR", "Scotland": "GB-SCT", "Greece": "GR"}


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(fc|cf|sc|ac|afc|club|calcio|ssc|as|sv|vfl|vfb|tsg|1)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def page(kind, y):
    os.makedirs(CACHE, exist_ok=True)
    cf = os.path.join(CACHE, f"{kind}{y}.html")
    if os.path.exists(cf) and (y < date.today().year - 1 or time.time() - os.path.getmtime(cf) < 6 * 86400):
        return open(cf, encoding="utf-8").read()
    for m in (5, 4, 3, 2, 1):
        try:
            h = urllib.request.urlopen(urllib.request.Request(f"https://kassiesa.net/uefa/data/method{m}/{kind}{y}.html", headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read().decode("utf-8", "replace")
            if len(h) > 3000:
                open(cf, "w", encoding="utf-8").write(h); time.sleep(0.3); return h
        except Exception:
            pass
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); a = ap.parse_args(argv)
    countries, clubs = defaultdict(list), defaultdict(list)
    for y in range(1960, date.today().year + 1):
        h = page("crank", y)
        if h:
            t = max(pd.read_html(io.StringIO(h)), key=len)
            cols = [str(c).lower() for c in t.columns]
            ci, ri = cols.index("country") if "country" in cols else 2, next((i for i, c in enumerate(cols) if c == "ranking"), None)
            for i, r in enumerate(t.itertuples(index=False)):
                try:
                    countries[str(r[ci])].append([y, int(r[0]), float(r[ri]) if ri is not None else None])
                except (ValueError, TypeError):
                    pass
        h = page("trank", y)
        if h:
            t = max(pd.read_html(io.StringIO(h)), key=len)
            # older pages have a two-row header (the country's own coefficient in the second row): the first level names it
            cols = [str(c[0] if isinstance(c, tuple) else c).lower() for c in t.columns]
            # columns: rank, flag, club, 3-letter country, the five seasons, «Total Points», «Country Part» (unnamed first four)
            # older years have no flag column: find the country column by its content (Esp, Eng, Ger…), the club is left of it
            import re as _re
            ki = next((i for i in range(len(cols)) if t.iloc[:, i].astype(str).str.fullmatch(r"[A-Z][a-z]{2}").mean() > 0.8), 3)
            ni = ki - 1
            ri = next((i for i, c in enumerate(cols) if c in ("ranking", "points", "total", "total points")), len(cols) - 2)
            # the rank is recomputed over the whole table: before ~1999 the pages number clubs within their country
            yr = []
            for r in t.itertuples(index=False):
                try:
                    yr.append((ABBR.get(str(r[ki]), str(r[ki])), str(r[ni]), float(r[ri])))
                except (ValueError, TypeError):
                    pass
            yr.sort(key=lambda x: -x[2])
            for i, (k, n_, pts) in enumerate(yr):
                clubs[(k, n_)].append([y, i + 1, pts])
    print(len(countries), "countries,", len(clubs), "clubs in the archive")
    store = Store(S3Backend(BUCKET))
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    comps = {c["id"]: c for c in (store.get_json("index.json") or {}).get("competitions") or []}
    cc_of = lambda t: (t.get("country") or {}).get("iso2") or next((((comps.get(c) or {}).get("country") or {}).get("iso2") for c in t.get("comps") or [] if ((comps.get(c) or {}).get("country") or {}).get("iso2")), None)
    by_cc = defaultdict(list)
    for k, t in teams.items():
        cc = cc_of(t)
        if cc:
            by_cc[cc].append((int(k), fold(t.get("name"))))
    linked = {}
    for (country, name), S in clubs.items():
        pool = by_cc.get(ISO.get(country, ""), [])
        f = fold(name); ws = set(f.split())
        ex = [k for k, n in pool if n == f] or [k for k, n in pool if ws and ws <= set(n.split())]
        if len(ex) == 1:
            linked.setdefault(ex[0], []).extend(S)
    print(len(linked), "of our clubs linked")
    if a.upload:
        store.put_json("history/uefa/countries.json", {"generated": date.today().isoformat(), "countries": countries, "source": "kassiesa.net"}, cache="warm")
        for fid, S in linked.items():
            S = sorted({x[0]: x for x in S}.values())
            if not S:
                continue
            store.put_json(f"history/uefa/club/{fid}.json", {"club": fid, "series": S, "best": min(S, key=lambda x: x[1]), "source": "kassiesa.net"}, cache="warm")
        store.put_json("history/uefa/index.json", {"generated": date.today().isoformat(), "clubs": sorted(linked)}, cache="warm"); print("uploaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
