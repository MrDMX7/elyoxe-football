"""Every national team's FIFA ranking since 1992 (owner's database, 2026-09-30 «كلها»). One pass over FIFA's own ranking
dates: each date returns the whole table (tools/build_fifa_history.py does the same for the UAE alone).

    python -m db.fifa_rank [--upload]

A FIFA team (3-letter code + English name) is linked to our FotMob national team by name, through the aliases the
two sources disagree on. Out: v1/history/fifa/<fotmob id>.json {series: [[date, rank, points]], best, worst, now}.
Resumable: every fetched date is cached in db/.cache/fifa/<dateId>.json.
"""
import argparse, json, os, re, sys, time, unicodedata
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
from store import Store, S3Backend  # noqa: E402
import build_fifa_history as B  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
CACHE = os.path.join(HERE, ".cache", "fifa")
ALIAS = {"korea republic": "south korea", "ir iran": "iran", "cote d ivoire": "ivory coast", "turkiye": "turkey", "czechia": "czech republic",
         "usa": "usa", "united states": "usa", "china pr": "china", "korea dpr": "north korea", "cabo verde": "cape verde", "congo dr": "dr congo",
         "kyrgyz republic": "kyrgyzstan", "united arab emirates": "uae", "republic of ireland": "ireland", "bosnia and herzegovina": "bosnia and herzegovina",
         "north macedonia": "north macedonia", "chinese taipei": "chinese taipei", "st kitts and nevis": "saint kitts and nevis", "curacao": "curacao"}


def fold(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return ALIAS.get(s, s)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); a = ap.parse_args(argv)
    os.makedirs(CACHE, exist_ok=True)
    html = B.get(B.PAGE)
    nd = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S).group(1))
    out = []; B.find(nd, "dates", out)
    dates = sorted((x for y in out[0] for x in y["dates"]), key=lambda d: d["matchWindowEndDate"])
    series, names = defaultdict(list), {}
    for d in dates:
        cf = os.path.join(CACHE, d["id"] + ".json")
        if os.path.exists(cf):
            r = json.load(open(cf, encoding="utf-8"))
        else:
            try:
                r = json.loads(B.get(B.API.format(d["id"]))).get("rankings") or []
            except Exception as e:
                print("#", d["id"], e); continue
            json.dump(r, open(cf, "w", encoding="utf-8", newline="\n")); time.sleep(0.4)
        for x in r:
            it = x.get("rankingItem") or {}
            if it.get("rank") is None:
                continue
            code = it.get("countryCode"); names[code] = it.get("name")
            series[code].append([d["matchWindowEndDate"][:10], it["rank"], round(it.get("totalPoints") or 0, 2)])
    print(len(dates), "dates,", len(series), "teams")
    store = Store(S3Backend(BUCKET))
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    fm = {fold(t.get("name")): int(k) for k, t in teams.items() if not t.get("country")}     # national teams carry no country
    idx, missing = {}, []
    for code, S in series.items():
        fid = fm.get(fold(names.get(code)))
        if not fid:
            missing.append(names.get(code)); continue
        S.sort()
        best, worst = min(S, key=lambda x: (x[1], x[0])), max(S, key=lambda x: (x[1], x[0]))
        doc = {"team": fid, "code": code, "name": names[code], "series": S, "best": best, "worst": worst, "now": S[-1], "source": "FIFA (inside.fifa.com ranking API)"}
        idx[fid] = {"rank": S[-1][1], "best": best[1], "best_date": best[0][:4]}
        if a.upload:
            store.put_json(f"history/fifa/{fid}.json", doc, cache="warm")
    print(len(idx), "linked;", len(missing), "not on the site (e.g.", missing[:8], ")")
    if a.upload:
        store.put_json("history/fifa/index.json", {"generated": date.today().isoformat(), "teams": idx}, cache="warm"); print("uploaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
