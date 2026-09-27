"""UAE FIFA ranking history since 1992 -> fifa_history.json (committed; the poller appends FotMob's
current ranking after each FIFA update).

Source: FIFA's own ranking API behind inside.fifa.com (public, no key):
  dates:   the ranking page's __NEXT_DATA__ (https://inside.fifa.com/fifa-rankings/world-ranking/men)
  ranking: https://inside.fifa.com/api/ranking-overview?locale=en&dateId=<id>
The newest dates (ids "FRS_Male_Football_*", 2026) return an empty list on that endpoint; those come
from FotMob (teams?id=5789 details.fifaRanking), which the poller records going forward.
Per date: UAE rank and points, rank among AFC members (FIFA's own confederation tag) and among the
22 Arab League members. Sequential, 0.4 s apart (~350 requests, once).
  python tools/build_fifa_history.py > fifa_history.json
"""
import json, re, sys, time, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
PAGE = "https://inside.fifa.com/fifa-rankings/world-ranking/men"
API = "https://inside.fifa.com/api/ranking-overview?locale=en&dateId={}"
ARAB = {"ALG", "BHR", "COM", "DJI", "EGY", "IRQ", "JOR", "KUW", "LBN", "LBY", "MTN", "MAR", "OMA", "PLE", "QAT",
        "KSA", "SOM", "SDN", "SYR", "TUN", "UAE", "YEM"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")


def find(o, key, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                out.append(v)
            find(v, key, out)
    elif isinstance(o, list):
        for x in o:
            find(x, key, out)


def main():
    html = get(PAGE)
    nd = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S).group(1))
    out = []
    find(nd, "dates", out)
    dates = [x for y in out[0] for x in y["dates"]]
    rows, empty, by_team = [], [], {}
    for d in sorted(dates, key=lambda d: d["matchWindowEndDate"]):
        try:
            r = json.loads(get(API.format(d["id"]))).get("rankings") or []
        except Exception as e:
            print(f"# {d['id']}: {e}", file=sys.stderr)
            r = []
        time.sleep(0.4)
        if not r:
            empty.append(d["id"])
            continue
        items = [x["rankingItem"] | {"conf": (x.get("tag") or {}).get("id")} for x in r if x["rankingItem"].get("rank") is not None]
        arab = sorted([x for x in items if x.get("countryCode") in ARAB], key=lambda x: x["rank"])
        for team in arab:
            conf = sorted([x for x in items if x["conf"] == team["conf"]], key=lambda x: x["rank"])
            by_team.setdefault(team["countryCode"], []).append({
                "date": d["matchWindowEndDate"], "rank": team["rank"], "points": team.get("totalPoints"),
                "confederation": team["conf"], "conf_rank": 1 + sum(1 for x in conf if x["rank"] < team["rank"]),
                "conf_teams": len(conf), "arab_rank": 1 + sum(1 for x in arab if x["rank"] < team["rank"]), "arab_teams": len(arab)})
        uae = next((x for x in items if x.get("countryCode") == "UAE"), None)
        if not uae:
            continue
        afc = sorted([x for x in items if x["conf"] == "AFC"], key=lambda x: x["rank"])
        rows.append({"date": d["matchWindowEndDate"], "rank": uae["rank"], "points": uae.get("totalPoints"),
                     "afc_rank": 1 + sum(1 for x in afc if x["rank"] < uae["rank"]), "afc_teams": len(afc),
                     "arab_rank": 1 + sum(1 for x in arab if x["rank"] < uae["rank"]), "arab_teams": len(arab)})
        print(f"# {d['matchWindowEndDate']} UAE {uae['rank']}", file=sys.stderr)
    print(json.dumps({"team": 5789, "source": "FIFA ranking API (inside.fifa.com/api/ranking-overview), FIFA's AFC tag, "
                      "Arab League membership list in tools/build_fifa_history.py",
                      "dates_without_data": empty, "history": rows, "arab_teams": by_team}, ensure_ascii=False, indent=0))


if __name__ == "__main__":
    main()
