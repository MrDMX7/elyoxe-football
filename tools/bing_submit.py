"""Bing URL submission (owner 2026-10-09: the site was imported into Bing Webmaster; before that Bing had 0 Tifo pages).
A new site gets 100 URLs a day (2,300 a month), so they go where an Arab football search lands first:
  hub      the home page, today, tomorrow, competitions, matches, national teams, the transfer market and its rumours (every day:
           they change every day)
  match    today's and tomorrow's matches in the Arab and Gulf competitions
  transfers the tracked leagues' transfer pages, who spent most, the players without a club, the contracts running out
  league   the big Arab, Asian and European leagues, and their scorers pages
  club     the top clubs of those leagues (their tables)
  star     the top scorers of those leagues
Only URLs in the live sitemap; anything but a hub is sent again only after RESEND_DAYS. State: site/cache/bing_sent.json.
The key: SSM /elyoxe/bing/webmaster-api-key.
  python -m tools.bing_submit [--dry]"""
import argparse, datetime as dt, gzip, json, os, re, urllib.request
from pathlib import Path

SITE = "https://tifo.elyoxe.com"
DATA = os.environ.get("TIFO_DATA", "https://d1n5aqaqkowltp.cloudfront.net")
STATE = Path(__file__).resolve().parents[1] / "site" / "cache" / "bing_sent.json"
QUOTA = 100
RESEND_DAYS = 30
LEAGUES = ["uae-pro-league", "saudi-pro-league", "qatar-stars-league", "egyptian-premier-league", "botola-pro", "iraq-stars-league",
           "kuwait-premier-league", "algeria-ligue-1", "tunisia-ligue-1", "afc-champions-league-elite", "caf-champions-league",
           "premier-league", "laliga", "champions-league", "serie-a", "bundesliga"]
SCORERS = ["uae-pro-league", "saudi-pro-league", "egyptian-premier-league", "qatar-stars-league", "botola-pro", "premier-league",
           "laliga", "champions-league"]
ARAB_ISO = {"AE", "SA", "QA", "KW", "BH", "OM", "EG", "MA", "DZ", "TN", "IQ", "JO", "LB", "LY", "SD", "SY", "PS", "YE"}


def pick(pri, sent, today, quota=QUOTA):
    """[(kind, [path])] in priority order -> the paths to send today: every hub, then what was never sent or not in
    RESEND_DAYS, in order, at most `quota`."""
    t = dt.date.fromisoformat(today)
    old = lambda p: p not in sent or (t - dt.date.fromisoformat(sent[p])).days > RESEND_DAYS
    out = []
    for kind, paths in pri:
        for p in paths:
            if p not in out and (kind == "hub" or old(p)):
                out.append(p)
    return out[:quota]


def _get(path):
    try:
        with urllib.request.urlopen(f"{DATA}/{path}", timeout=30) as r:
            raw = r.read()
        return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    except Exception:
        return None


def priorities(today):
    idx = _get("index.json") or {}
    comps = idx.get("competitions") or []
    by_key = {c.get("key"): c for c in comps}
    arab = {c["id"] for c in comps if c.get("scope") in ("uae", "gulf", "arab") or ((c.get("country") or {}).get("iso2") in ARAB_ISO)}
    matches = []
    for d in (today, today + dt.timedelta(days=1)):
        for m in ((_get(f"day/{d:%Y%m%d}.json") or {}).get("matches") or []):
            if m.get("comp") in arab and m.get("id") is not None:
                matches.append(f"/m/{m['id']}/")
    leagues = [f"/c/{k}/" for k in LEAGUES] + [f"/c/{k}/scorers/" for k in SCORERS]
    clubs, stars = [], []
    for k in LEAGUES[:11]:
        c = by_key.get(k)
        if not c:
            continue
        st = _get(f"comp/{c['id']}/standings.json") or {}
        rows = [r for g in st.get("groups") or [] for r in g.get("rows") or []]
        clubs += [f"/t/{r['team']['id']}/" for r in sorted(rows, key=lambda r: r.get("rank") or 99)[:6]]
        goals = (((_get(f"comp/{c['id']}/stats.json") or {}).get("lists") or {}).get("goals") or [])[:3]
        stars += [f"/p/{x['player']['id']}/" for x in goals if (x.get("player") or {}).get("id")]
    hubs = ["/", "/today/", "/tomorrow/", "/competitions/", "/matches/", "/national/", "/transfers/", "/transfers/rumours/"]
    # owner 2026-10-10: the transfer market (site/build_arabs.cjs): the tracked leagues' pages and the lists
    transfers = [f"/transfers/{k}/" for k in LEAGUES if k in by_key] + ["/transfers/spending/", "/transfers/free-agents/", "/transfers/sources/", "/transfers/expiring/"]
    return [("hub", hubs), ("match", matches), ("transfers", transfers), ("league", leagues), ("club", clubs), ("star", stars)]


def sitemap_paths():
    out = set()
    for sm in ("sitemap.xml", "sitemap-recent.xml", "sitemap-days.xml"):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{SITE}/{sm}", headers={"Accept-Encoding": "gzip"}), timeout=60) as r:
                raw = r.read()
            body = (gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw).decode("utf-8")
            out |= {u[len(SITE):] for u in re.findall(r"<loc>([^<]+)</loc>", body)}
        except Exception:
            pass
    return out


def submit(paths, key):
    body = json.dumps({"siteUrl": SITE + "/", "urlList": [SITE + p for p in paths]}).encode()
    req = urllib.request.Request(f"https://ssl.bing.com/webmaster/api.svc/json/SubmitUrlBatch?apikey={key}", data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--dry", action="store_true"); a = ap.parse_args(argv)
    today = dt.date.today()
    sent = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    if any(v == today.isoformat() for v in sent.values()) and not a.dry:
        print(json.dumps({"skipped": "already sent today"})); return 0
    live = sitemap_paths()
    pri = [(k, [p for p in ps if p in live or p == "/"]) for k, ps in priorities(today)]
    todo = pick(pri, sent, today.isoformat())
    if a.dry:
        print(json.dumps({"would_send": len(todo), "first": todo[:15]}, ensure_ascii=False)); return 0
    import boto3
    key = boto3.client("ssm", region_name="ap-south-1").get_parameter(Name="/elyoxe/bing/webmaster-api-key", WithDecryption=True)["Parameter"]["Value"]
    status = submit(todo, key)
    for p in todo:
        sent[p] = today.isoformat()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(sent, indent=0), encoding="utf-8")
    print(json.dumps({"sent": len(todo), "status": status, "by_kind": {k: sum(1 for p in ps if p in todo) for k, ps in pri}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
