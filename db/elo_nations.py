"""Every national team's Elo rating through its history, from eloratings.net (World Football Elo Ratings), stage 3 of the
owner's database (2026-09-30 «كلها»).

    python -m db.elo_nations [--upload]

eloratings.net keeps one tab-separated file per team (<English_Name>.tsv): every match since the team's first, with
both teams' rating and world rank after it. A FotMob national team is linked when its English name equals the site's
team name (en.teams.tsv), after a short alias list. Out: v1/history/elo/<fotmob id>.json {series: [[date, rating,
rank]] (one point per month, the last match of it), peak, low, now, first}; v1/history/elo/index.json.
"""
import argparse, json, os, sys, time, urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
UA = {"User-Agent": "Mozilla/5.0 (elyoxe-tifo; hello@elyoxe.com)"}
ALIAS = {"USA": "United States", "Korea Republic": "South Korea", "Côte d'Ivoire": "Ivory Coast", "Congo DR": "DR Congo", "IR Iran": "Iran",
         "China PR": "China", "Türkiye": "Turkey", "Czechia": "Czech Republic", "Cabo Verde": "Cape Verde", "Korea DPR": "North Korea",
         "Kyrgyz Republic": "Kyrgyzstan", "Palestine": "Palestine", "United Arab Emirates": "United Arab Emirates"}


def get(path):
    return urllib.request.urlopen(urllib.request.Request("https://www.eloratings.net/" + path, headers=UA), timeout=60).read().decode("utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); a = ap.parse_args(argv)
    store = Store(S3Backend(BUCKET))
    names = {}
    for line in get("en.teams.tsv").splitlines():
        p = line.split("\t")
        if len(p) >= 2:
            names[p[1].strip()] = p[0].strip()
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    idx = {}
    for fid, t in teams.items():
        nm = ALIAS.get(t.get("name"), t.get("name"))
        code = names.get(nm)
        if not code or not ({77, 50, 44, 289, 290, 329, 10242, 114, 10195, 10196, 10197, 10198, 10199, 10609, 10608, 9806, 11156, 9571} & set(t.get("comps") or [])):   # national teams only, known by their competitions
            continue
        try:
            raw = get(nm.replace(" ", "_") + ".tsv")
        except Exception as e:
            print(nm, "failed", e); continue
        pts, first = {}, None
        for line in raw.splitlines():
            p = line.split("\t")
            if len(p) < 16 or not p[0].isdigit():
                continue
            d = f"{p[0]}-{p[1]}-{p[2]}"; first = first or d
            me = 0 if p[3] == code else 1 if p[4] == code else None
            if me is None:
                continue
            try:
                r, rk = int(p[10 + me]), int(p[14 + me])
            except ValueError:
                continue
            pts[d[:7]] = [d, r, rk]                # the month's last match
        if not pts:
            continue
        series = [pts[k] for k in sorted(pts)]
        peak, low = max(series, key=lambda x: x[1]), min(series, key=lambda x: x[1])
        doc = {"team": int(fid), "name": nm, "code": code, "first": first, "now": series[-1], "peak": peak, "low": low, "series": series,
               "source": "eloratings.net (World Football Elo Ratings)"}
        idx[fid] = {"now": series[-1][1], "rank": series[-1][2], "peak": peak[1], "peak_date": peak[0][:4]}
        if a.upload:
            store.put_json(f"history/elo/{fid}.json", doc, cache="warm")
        time.sleep(0.4)
    print(len(idx), "national teams with an Elo history")
    if a.upload:
        store.put_json("history/elo/index.json", {"generated": date.today().isoformat(), "teams": idx}, cache="warm"); print("uploaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
