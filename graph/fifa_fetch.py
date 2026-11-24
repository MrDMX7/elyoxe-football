"""FIFA's own match records (api.fifa.com/api/v3, no key): the World Cup and every qualifier of every confederation since
1933, the men's Olympic tournament, the Confederations Cup and the Club World Cup. Per game: both squads with the
starters, substitutions, goals with minute, cards, the coaches, the referee, the ground, the attendance. A man's birthday
and his Arabic name come from the squad list of his team in that season, else from his own record.

  python -m graph.fifa_fetch --cache DIR fetch       # resumable: one compact file a game
  python -m graph.fifa_fetch --cache DIR men         # resumable: squad lists, then the men they leave out
  python -m graph.fifa_fetch --cache DIR pack OUT    # one gz file for the graph build (graph/load/fifa.py)

Run where FIFA answers (the laptop, 24 Nov 2026), four requests at a time."""
import argparse, gzip, http.client, json, os, re, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://api.fifa.com/api/v3"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}
# FIFA's competition id -> our label. 107 is the Club World Cup of 2000-2023 and the Intercontinental Cup after it.
WANT = {"17": "world-cup", "520": "world-cup-qualifiers", "101": "confederations-cup", "512": "olympics", "107": "club-world-cup"}
WORKERS, GAP = 4, 0.25
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


def text(v):
    """FIFA's localised field: a list of {Locale, Description}"""
    return ((v or [{}])[0].get("Description") or "").strip() or None


def arabic(v):
    """the Arabic answer falls back to the Latin name: only a name in Arabic letters is one"""
    s = text(v)
    return s if s and ARABIC.search(s) else None


def day(v):
    return v[:10] if v else None


def side(t):
    t = t or {}
    return {"id": t.get("IdTeam"), "name": text(t.get("TeamName")), "country": t.get("IdCountry") or t.get("IdAssociation"), "type": t.get("TeamType"),
            "age": t.get("AgeType"), "gender": t.get("Gender"), "score": t.get("Score")}


def squad(t):
    t = t or {}
    return {"team": t.get("IdTeam"),
            "men": [{"id": p.get("IdPlayer"), "name": text(p.get("PlayerName")), "no": p.get("ShirtNumber"), "start": p.get("Status") == 1,
                     "pos": p.get("Position"), "captain": bool(p.get("Captain"))} for p in t.get("Players") or []],
            "coaches": [{"id": c.get("IdCoach"), "name": text(c.get("Name")), "country": c.get("IdCountry"), "role": c.get("Role")} for c in t.get("Coaches") or []],
            "goals": [{"type": g.get("Type"), "id": g.get("IdPlayer"), "minute": g.get("Minute"), "period": g.get("Period"), "team": g.get("IdTeam")}
                      for g in t.get("Goals") or []],
            "cards": [{"card": b.get("Card"), "id": b.get("IdPlayer"), "minute": b.get("Minute"), "period": b.get("Period"), "team": b.get("IdTeam")}
                      for b in t.get("Bookings") or [] if b.get("IdPlayer")],
            "subs": [{"on": s.get("IdPlayerOn"), "off": s.get("IdPlayerOff"), "minute": s.get("Minute"), "period": s.get("Period")}
                     for s in t.get("Substitutions") or []]}


def compact(m, live):
    """what the loader reads of a match: the calendar row, and the live record's squads and events where FIFA has one"""
    st = (live or {}).get("Stadium") or m.get("Stadium") or {}
    return {"id": m.get("IdMatch"), "season": m.get("IdSeason"), "season_name": text(m.get("SeasonName")), "stage": m.get("IdStage"),
            "stage_name": text(m.get("StageName")), "group": text(m.get("GroupName")), "date": day(m.get("Date")), "local": day(m.get("LocalDate")),
            "status": m.get("MatchStatus"), "result": m.get("ResultType"), "leg": m.get("Leg"), "home": side(m.get("Home")), "away": side(m.get("Away")),
            "pens": [m.get("HomeTeamPenaltyScore"), m.get("AwayTeamPenaltyScore")], "attendance": (live or {}).get("Attendance") or m.get("Attendance"),
            "stadium": {"id": st.get("IdStadium"), "name": text(st.get("Name")), "city": text(st.get("CityName")), "country": st.get("IdCountry"),
                        "capacity": st.get("Capacity"), "lat": st.get("Latitude"), "lon": st.get("Longitude")} if st else None,
            "officials": [{"id": o.get("OfficialId"), "name": text(o.get("Name")), "country": o.get("IdCountry"), "type": o.get("OfficialType")}
                          for o in (live or m).get("Officials") or []],
            "lineups": [squad(live.get(k)) for k in ("HomeTeam", "AwayTeam")] if live else None}


def calendar(cid, sid):
    out, token = [], None
    while True:
        d = get(f"{API}/calendar/matches?idCompetition={cid}&idSeason={sid}&count=500&language=en" + (f"&continuationToken={token}" if token else "")) or {}
        out += d.get("Results") or []
        token = d.get("ContinuationToken")
        if not token or not d.get("Results"):
            return out


def games(cache):
    """every game of the wanted competitions: label -> {match id: (competition id, calendar row)}"""
    out = {}
    for cid, label in WANT.items():
        seasons = cached(os.path.join(cache, "list", label, "seasons.json"),
                         lambda: (get(f"{API}/seasons?idCompetition={cid}&count=400&language=en") or {}).get("Results") or [])
        out[label] = {}
        for s in seasons:
            f = os.path.join(cache, "list", label, f"{s['IdSeason']}.json")
            if os.path.exists(f):
                ms = json.load(open(f, encoding="utf-8"))
            else:
                ms = calendar(cid, s["IdSeason"])
                if ms:                                   # an empty answer is asked again next run: a season is not lost to one bad reply
                    cached(f, lambda: ms)
            for m in ms:
                out[label][m["IdMatch"]] = (cid, m)
    return out


def fetch(cache):
    for label, held in games(cache).items():
        todo = [(i, c, m) for i, (c, m) in held.items() if not os.path.exists(os.path.join(cache, "ev", label, f"{i}.json"))]
        print(f"{label}: {len(held)} games, {len(todo)} to fetch", flush=True)

        def one(item):
            i, c, m = item
            done = m.get("MatchStatus") == 0
            try:
                return cached(os.path.join(cache, "ev", label, f"{i}.json"),
                              lambda: compact(m, get(f"{API}/live/football/{c}/{m['IdSeason']}/{m['IdStage']}/{i}?language=en") if done else None))
            except (urllib.error.URLError, OSError, ValueError) as e:      # one game FIFA will not answer for: the next run asks again
                print(f"{label}: {i} left out ({e})", flush=True)
        for k in range(0, len(todo), 400):
            with ThreadPoolExecutor(WORKERS) as ex:
                list(ex.map(one, todo[k:k + 400]))
            print(f"{label}: {min(k + 400, len(todo))}/{len(todo)}", flush=True)


def records(cache):
    for label in WANT.values():
        d = os.path.join(cache, "ev", label)
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if f.endswith(".json"):
                yield label, json.load(open(os.path.join(d, f), encoding="utf-8"))


def man(p, name="PlayerName"):
    return {"ar": arabic(p.get(name)), "born": day(p.get("BirthDate")), "country": p.get("IdCountry"), "height": p.get("Height") or None}


def men(cache):
    """the birthday and the Arabic name of every man in a line-up: one squad list a team a season, then one record a man"""
    cid = {label: c for c, label in WANT.items()}
    squads, wanted = {}, set()
    for label, r in records(cache):
        for sq in r.get("lineups") or []:
            if sq.get("men"):
                squads[(cid[label], r["season"], sq["team"])] = 1
                wanted.update(p["id"] for p in sq["men"] if p.get("id"))
    todo = [k for k in squads if not os.path.exists(os.path.join(cache, "squad", "-".join(k) + ".json"))]
    print(f"squads: {len(squads)}, {len(todo)} to fetch", flush=True)

    def one(k):
        c, s, t = k
        def ask():
            d = get(f"{API}/teams/{t}/squad?idCompetition={c}&idSeason={s}&language=ar") or {}
            return {p["IdPlayer"]: man(p) for p in d.get("Players") or [] if p.get("IdPlayer")}
        return cached(os.path.join(cache, "squad", "-".join(k) + ".json"), ask)
    for k in range(0, len(todo), 400):
        with ThreadPoolExecutor(WORKERS) as ex:
            list(ex.map(one, todo[k:k + 400]))
        print(f"squads: {min(k + 400, len(todo))}/{len(todo)}", flush=True)
    known = set()
    for k in squads:
        known.update(i for i, p in one(k).items() if p.get("born"))
    todo = sorted(i for i in wanted - known if not os.path.exists(os.path.join(cache, "man", i[-2:], f"{i}.json")))
    print(f"men: {len(wanted)} in line-ups, {len(known & wanted)} in squad lists, {len(todo)} to fetch", flush=True)

    def solo(i):
        return cached(os.path.join(cache, "man", i[-2:], f"{i}.json"), lambda: man(get(f"{API}/players/{i}?language=ar") or {}, "Name"))
    for k in range(0, len(todo), 400):
        with ThreadPoolExecutor(WORKERS) as ex:
            list(ex.map(solo, todo[k:k + 400]))
        print(f"men: {min(k + 400, len(todo))}/{len(todo)}", flush=True)


def pack(cache, out):
    rows = [{"comp": label, **r} for label, r in records(cache)]
    people = {}
    for root in ("man", "squad"):                        # a squad list is the later word: it is of the season the man played in
        for d, _, fs in os.walk(os.path.join(cache, root)):
            for f in fs:
                if f.endswith(".json"):
                    got = json.load(open(os.path.join(d, f), encoding="utf-8"))
                    for i, p in ({f[:-5]: got} if root == "man" else got).items():
                        people[i] = {**people.get(i, {}), **{k: v for k, v in p.items() if v}}
    with gzip.open(out, "wt", encoding="utf-8") as z:
        json.dump({"source": "api.fifa.com", "matches": rows, "men": people}, z, ensure_ascii=False)
    print(f"packed {len(rows)} games, {len(people)} men -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("stage", choices=["fetch", "men", "pack"])
    ap.add_argument("out", nargs="?")
    a = ap.parse_args()
    {"fetch": fetch, "men": men}[a.stage](a.cache) if a.stage != "pack" else pack(a.cache, a.out)
