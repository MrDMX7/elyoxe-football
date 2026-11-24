"""UEFA's own match records (match.uefa.com/v5, no key) for the seasons before FotMob's detail: the European Cup and
Champions League, the UEFA Cup, the Cup Winners' Cup, the Intertoto Cup, the Super Cup, the Intercontinental Cup, the
Fairs Cup and the EURO with its qualifiers, 1955/56-2009/10; 2010/11 too (and EURO 2012), so its men tie to FotMob's by
the shirt each wore in a game both hold. Per game: both squads with the starters, each man's birthday, substitutions,
goals with minute, cards, the ground, the attendance.

  python -m graph.uefa_fetch --cache DIR fetch       # resumable: one compact file a game
  python -m graph.uefa_fetch --cache DIR pack OUT    # one gz file for the graph build (graph/load/uefa.py)

Run where UEFA answers (the laptop, 24 Nov 2026), four requests at a time."""
import argparse, gzip, http.client, json, os, re, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://match.uefa.com/v5/matches"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}
# UEFA's competition id -> (our label, seasonYears). A seasonYear is the year a season starts in until 2006/07 and the year
# it ends in from 2007/08, and the Fairs Cup's run over two and three years: every year is asked, the dates say the season.
WANT = {"1": ("champions", range(1955, 2012)), "14": ("uefa-cup", range(1971, 2012)), "2": ("cup-winners", range(1960, 2000)),
        "16": ("intertoto", range(1995, 2010)), "9": ("super-cup", range(1972, 2012)), "4": ("intercontinental", range(1960, 2005)),
        "41": ("fairs-cup", range(1955, 1972)), "3": ("euro", range(1958, 2013))}
WORKERS, GAP, PAGE = 4, 0.25, 100
ARABIC = re.compile(r"[؀-ۿ]")


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                time.sleep(GAP)
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            if i == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError, http.client.IncompleteRead, OSError):
            if i == tries - 1:
                raise
        time.sleep(4 * (i + 1))


def cached(f, fetch):
    if os.path.exists(f):
        return json.load(open(f, encoding="utf-8"))
    d = fetch()
    os.makedirs(os.path.dirname(f), exist_ok=True)
    json.dump(d, open(f + ".tmp", "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(f + ".tmp", f)
    return d


def tr(o, key, lang="EN"):
    return (((o or {}).get("translations") or {}).get(key) or {}).get(lang)


def arabic(o, key):
    """UEFA's Arabic field often repeats the Latin name: only a name in Arabic letters is one"""
    v = tr(o, key, "AR")
    return v if v and ARABIC.search(v) else None


def day(v):
    """«1901-01-01» and its like stand for «unknown»"""
    return v if v and not v.endswith("-01-01") else None


def person(p):
    p = p or {}
    return {"id": p.get("id"), "name": p.get("internationalName") or tr(p, "name"), "ar": arabic(p, "name"), "born": day(p.get("birthDate")),
            "country": p.get("countryCode"), "pos": p.get("fieldPosition"), "sex": p.get("gender"), "height": p.get("height")}


def side(t):
    t = t or {}
    return {"id": t.get("id"), "name": t.get("internationalName"), "official": tr(t, "displayOfficialName"), "ar": arabic(t, "displayName"),
            "country": t.get("countryCode"), "national": t.get("typeIsNational"), "kind": t.get("teamTypeDetail")}


def squad(t):
    t = t or {}
    row = lambda x, start: {**person(x.get("player")), "no": x.get("jerseyNumber"), "start": start, "gk": x.get("type") == "GOALKEEPER"}
    return {"team": (t.get("team") or {}).get("id"), "men": [row(x, True) for x in t.get("field") or []] + [row(x, False) for x in t.get("bench") or []],
            "coaches": [{**person(c.get("person")), "role": c.get("role")} for c in t.get("coaches") or []]}


def actor(a):
    a = a or {}
    p = a.get("person") or {}
    return {"id": p.get("id"), "name": p.get("internationalName"), "born": day(p.get("birthDate")), "team": (a.get("team") or {}).get("id")} if p else None


def compact(m, lineups, events):
    """what the loader reads of a match (logos and nine languages of every label otherwise)"""
    st, rd = m.get("stadium") or {}, m.get("round") or {}
    city, geo = st.get("city") or {}, st.get("geolocation") or {}
    return {"id": m.get("id"), "date": (m.get("kickOffTime") or {}).get("date"), "status": m.get("status"), "type": m.get("type"),
            "round": (rd.get("metaData") or {}).get("type"), "round_name": (rd.get("metaData") or {}).get("name"), "round_ar": arabic(rd, "name"),
            "phase": rd.get("phase"), "group": ((m.get("group") or {}).get("metaData") or {}).get("groupName"), "leg": (m.get("leg") or {}).get("number"),
            "home": side(m.get("homeTeam")), "away": side(m.get("awayTeam")), "score": m.get("score"),
            "won": ((m.get("winner") or {}).get("match") or {}).get("reason"), "attendance": m.get("matchAttendance"),
            "stadium": {"id": st.get("id"), "name": tr(st, "officialName") or tr(st, "name") or tr(st, "mediaName"), "ar": arabic(st, "name"),
                        "city": tr(city, "name"), "city_ar": arabic(city, "name"), "country": st.get("countryCode"), "capacity": st.get("capacity"),
                        "lat": geo.get("latitude"), "lon": geo.get("longitude")} if st else None,
            "referees": [{**person(r.get("person")), "role": r.get("role")} for r in m.get("referees") or []],
            "scorers": [{"type": s.get("goalType"), "phase": s.get("phase"), "minute": (s.get("time") or {}).get("minute"),
                         "added": (s.get("time") or {}).get("injuryMinute"), "team": s.get("teamId"), **{k: v for k, v in person(s.get("player")).items()
                                                                                                     if k in ("id", "name", "born")}}
                        for s in (m.get("playerEvents") or {}).get("scorers") or []],
            "lineups": [squad((lineups or {}).get(k)) for k in ("homeTeam", "awayTeam")] if lineups else None,
            "events": [{"type": e.get("type"), "sub": e.get("subType"), "phase": e.get("phase"), "minute": (e.get("time") or {}).get("minute"),
                        "added": (e.get("time") or {}).get("injuryMinute"), "second": (e.get("time") or {}).get("second"),
                        "a": actor(e.get("primaryActor")), "b": actor(e.get("secondaryActor"))} for e in events or []] if events is not None else None}


def season(cid, year):
    out, off = [], 0
    while True:
        page = get(f"{API}?competitionId={cid}&seasonYear={year}&limit={PAGE}&offset={off}&order=ASC") or []
        out += page
        if len(page) < PAGE:
            return out
        off += PAGE


def fetch(cache):
    for cid, (label, years) in WANT.items():
        games = {}
        for y in years:
            f = os.path.join(cache, "list", label, f"{y}.json")
            if os.path.exists(f):
                ms = json.load(open(f, encoding="utf-8"))
            else:
                ms = season(cid, y)
                if ms:                                   # an empty answer is asked again next run: a season is not lost to one bad reply
                    cached(f, lambda: ms)
            for m in ms:
                games[m["id"]] = (y, m)
        todo = [(i, y, m) for i, (y, m) in games.items() if not os.path.exists(os.path.join(cache, "ev", label, f"{i}.json"))]
        print(f"{label}: {len(games)} games, {len(todo)} to fetch", flush=True)

        def one(item):
            i, y, m = item
            def both():
                has = m.get("lineupStatus") in ("AVAILABLE", "TACTICAL_AVAILABLE")
                lu = get(f"{API}/{i}/lineups") if has else None
                ev = get(f"{API}/{i}/events?filter=LINEUP&offset=0&limit=200") if has or m.get("playerEvents") else None
                return {"year": y, **compact(m, lu, ev)}
            try:
                return cached(os.path.join(cache, "ev", label, f"{i}.json"), both)
            except (urllib.error.URLError, OSError, ValueError) as e:      # one game UEFA will not answer for: the next run asks again
                print(f"{label}: {i} left out ({e})", flush=True)
        for k in range(0, len(todo), 400):
            with ThreadPoolExecutor(WORKERS) as ex:
                list(ex.map(one, todo[k:k + 400]))
            print(f"{label}: {min(k + 400, len(todo))}/{len(todo)}", flush=True)


def pack(cache, out):
    rows = []
    for label, _ in WANT.values():
        d = os.path.join(cache, "ev", label)
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if f.endswith(".json"):
                rows.append({"comp": label, **json.load(open(os.path.join(d, f), encoding="utf-8"))})
    with gzip.open(out, "wt", encoding="utf-8") as z:
        json.dump({"source": "match.uefa.com", "matches": rows}, z, ensure_ascii=False)
    print(f"packed {len(rows)} -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("stage", choices=["fetch", "pack"])
    ap.add_argument("out", nargs="?")
    a = ap.parse_args()
    fetch(a.cache) if a.stage == "fetch" else pack(a.cache, a.out)
