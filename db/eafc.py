"""EA SPORTS FC 27 ratings (drop-api.ea.com, the feed of EA's own ratings site: ~17.8k men, 29 attributes and PlayStyles)
matched to our FotMob players, for a player card on every player page (owner 2026-09-30: «ابغي… كل الخانات تكون كاملة»).

    python -m db.eafc [--upload] [--refetch]

Match: the same birth date (FotMob's «0001-01-01» is none), and EA's full or common name inside the FotMob name, or the
other way round; one candidate only. EA's surname alone counts only with a compatible given name (Joe / Joseph, Tino /
Valentino) or the same club: «Isaac Lee» of Shrewsbury is not «Myung-Dong Lee» of Chuncheon. Players: the site's (v1/history/fm/players.json) and, when db/world.py has run with --players, the world
encyclopedia's (v1/world/bios.json).
Out (public): v1/ea/cards.json {fotmob id: card} for the build, v1/ea/s/<id % 100>.json for the encyclopedia's pages.
card = [overall, position, [6 face stats], skill moves, weak foot, foot (1 right, 2 left), [29 attributes], [PlayStyles, + marks
the PlayStyle+], EA id, EA team, goalkeeper (1/0), [5 goalkeeping attributes]]
Cache: db/.cache/ea_fc.json (refetched every 30 days: EA updates ratings during the season).
"""
import argparse, gzip, json, os, re, sys, time, unicodedata, urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
CACHE = os.path.join(HERE, ".cache", "ea_fc.json")
API = "https://drop-api.ea.com/rating/ea-sports-fc?locale=en&limit=100&offset={}"
H = {"drop-referrer": "https://www.ea.com/games/ea-sports-fc/ratings", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/140.0 Safari/537.36"}
FACE = ["pac", "sho", "pas", "dri", "def", "phy"]
ATTR = ["acceleration", "sprintSpeed", "positioning", "finishing", "shotPower", "longShots", "volleys", "penalties", "vision", "crossing", "freeKickAccuracy",
        "shortPassing", "longPassing", "curve", "agility", "balance", "reactions", "ballControl", "dribbling", "composure", "interceptions", "headingAccuracy",
        "defensiveAwareness", "standingTackle", "slidingTackle", "jumping", "stamina", "strength", "aggression"]
GK = ["gkDiving", "gkHandling", "gkKicking", "gkReflexes", "gkPositioning"]


def fetch(refetch=False):
    if not refetch and os.path.exists(CACHE) and time.time() - os.path.getmtime(CACHE) < 30 * 86400:
        return json.load(open(CACHE, encoding="utf-8"))
    items, off = [], 0
    while True:
        for i in range(4):
            try:
                d = json.load(urllib.request.urlopen(urllib.request.Request(API.format(off), headers=H), timeout=60)); break
            except Exception as e:
                if i == 3:
                    raise
                time.sleep(3 + 5 * i)
        items += d.get("items") or []
        off += 100
        if off >= (d.get("totalItems") or 0) or not d.get("items"):
            break
        time.sleep(0.25)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(items, open(CACHE, "w", encoding="utf-8", newline="\n"), ensure_ascii=False)
    print("EA ratings fetched:", len(items))
    return items


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s.replace("-", " ")).split()


def dob(s):   # EA: "12/20/1998 0:00"
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s or "")
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else None


def card(x):
    st = {k: (v or {}).get("value") for k, v in (x.get("stats") or {}).items()}
    pos = (x.get("position") or {}).get("shortLabel") or ""
    ps = [a.get("label") for a in x.get("playerAbilities") or [] if a.get("label")]
    return [x.get("overallRating"), pos, [st.get(k) for k in FACE], x.get("skillMoves"), x.get("weakFootAbility"), x.get("preferredFoot"),
            [st.get(k) for k in ATTR], ps, x.get("id"), (x.get("team") or {}).get("label"), 1 if pos == "GK" else 0, [st.get(k) for k in GK]]


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); ap.add_argument("--refetch", action="store_true"); a = ap.parse_args(argv)
    items = [x for x in fetch(a.refetch) if (x.get("gender") or {}).get("id") == 0]
    print(len(items), "EA men")

    def jget(u):
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": H["User-Agent"], "Accept-Encoding": "gzip"}), timeout=90)
            b = r.read()
            return json.loads(gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b)
        except Exception as e:
            print("can't read", u, e); return {}
    fm = {int(k): (v.get("name"), v.get("born"), v.get("team")) for k, v in (jget("https://tifo.elyoxe.com/v1/history/fm/players.json").get("players") or {}).items()}
    for k, v in (jget("https://tifo.elyoxe.com/v1/world/bios.json").get("players") or {}).items():
        fm.setdefault(int(k), (v[0], v[1], v[2]))
    by_dob = {}
    for fid, (nm, born, team) in fm.items():
        if born and born >= "1900":
            by_dob.setdefault(born, []).append(fid)
    print(len(fm), "FotMob players,", sum(1 for v in fm.values() if v[1]), "with a birth date")
    tname = {str(c[0]): c[2] for c in jget("https://tifo.elyoxe.com/v1/world/index.json").get("clubs") or []}
    for k, t in (jget("https://tifo.elyoxe.com/v1/teams.json").get("teams") or {}).items():
        tname.setdefault(k, t.get("name"))
    STOP = {"fc", "cf", "afc", "sc", "ac", "club", "de", "united", "utd", "city", "ii", "u21", "u23", "u19", "b", "sk", "fk", "cd", "ca", "real", "sporting",
            "al", "the", "if", "bk", "sv", "1", "2"}

    def same_club(ea_team, team):
        import difflib
        a, b = set(fold(ea_team)) - STOP, set(fold(tname.get(str(team), ""))) - STOP
        return bool(a and b) and (bool(a & b) or difflib.SequenceMatcher(None, " ".join(sorted(a)), " ".join(sorted(b))).ratio() >= 0.7)

    def given_ok(x, fn):
        """EA's first names and FotMob's other words: one starts like the other (Joe / Joseph, Jake / Jacob), is inside it (Tino /
        Valentino) or is a close spelling with the same initial (Tom / Thomas, Mishal / Meshal)"""
        import difflib
        last = set(fold(x.get("lastName")))
        g, h = fold(x.get("firstName")), [w for w in fn if w not in last]
        return any(a == b or a in b or b in a or (len(a) >= 2 and len(b) >= 2 and a[:2] == b[:2])
                   or (a[0] == b[0] and difflib.SequenceMatcher(None, a, b).ratio() >= 0.6) for a in g for b in h)
    cards, taken = {}, {}
    for x in items:
        d = dob(x.get("birthdate"))
        cands = by_dob.get(d) or []
        if not cands:
            continue
        keys = [fold(x.get("commonName")), fold((x.get("firstName") or "") + " " + (x.get("lastName") or ""))]
        last = fold(x.get("lastName"))
        hits = []
        for fid in cands:
            fn = fold(fm[fid][0])
            if not fn:
                continue
            if any(k and (set(k) <= set(fn) or set(fn) <= set(k)) for k in keys):
                hits.append(fid)
            elif last and (set(last) <= set(fn) or set(fn) <= set(last)) and (given_ok(x, fn) or same_club((x.get("team") or {}).get("label"), fm[fid][2])):
                hits.append(fid)                  # the surname alone: a given name that fits, or the same club
        if len(hits) == 1:
            taken.setdefault(hits[0], []).append(x)
    who = {}
    for fid, xs in taken.items():
        if len(xs) == 1:
            cards[fid] = card(xs[0])
            who[fid] = [" ".join(filter(None, [xs[0].get("firstName"), xs[0].get("lastName")])), (xs[0].get("nationality") or {}).get("label")]
    print(len(cards), "cards matched")
    if a.upload:
        store = Store(S3Backend(BUCKET))
        # who: EA's name and nationality, for the daily identity check (the site reads cards; the shards stay as they were)
        store.put_json("ea/cards.json", {"generated": date.today().isoformat(), "edition": "EA SPORTS FC 27", "cards": {str(k): v for k, v in cards.items()},
                                         "who": {str(k): v for k, v in who.items()}}, cache="warm")
        shards = {}
        for k, v in cards.items():
            shards.setdefault(k % 100, {})[str(k)] = v
        for n, sh in shards.items():
            store.put_json(f"ea/s/{n}.json", {"cards": sh}, cache="warm")
        print("uploaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
