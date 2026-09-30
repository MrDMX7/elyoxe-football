"""Transfermarkt's player records (salimt/football-datasets on GitHub, refreshed from Transfermarkt: 92.7k profiles, 1.88M
season x competition x club lines, 168k injuries) for what FotMob doesn't give (owner 2026-09-30: «كل اللاعبين واحصائياتهم،
وكل الخانات تكون كاملة»): every season of a career by competition with minutes and cards, the full injury record,
birthplace, second nationality, agent, kit sponsor, contract option, the name in the player's own script.

    python -m db.tmdata [--upload] [--refetch]

Match: the same birth date, and Transfermarkt's name (without its «(1)» suffix) inside the FotMob name or the other way
round, one candidate only. Players: the site's (v1/history/fm/players.json) and the world encyclopedia's (v1/world/bios.json).
Out (public): v1/player/<fotmob id>/tm.json, v1/history/tm/index.json {fotmob id: transfermarkt id}.
Cache: db/.cache/tm/ (the CSVs; refetched every 30 days, the big ones from media.githubusercontent.com).
"""
import argparse, csv, gzip, json, os, re, sys, time, unicodedata, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
CACHE = os.path.join(HERE, ".cache", "tm")
RAW = "https://raw.githubusercontent.com/salimt/football-datasets/main/datalake/transfermarkt/"
MEDIA = "https://media.githubusercontent.com/media/salimt/football-datasets/main/datalake/transfermarkt/"
FILES = {"player_profiles": "player_profiles/player_profiles.csv", "player_performances": "player_performances/player_performances.csv",
         "player_injuries": "player_injuries/player_injuries.csv"}
BIG = {"player_performances"}
csv.field_size_limit(1 << 24)


def latest(name):
    """The newest CSV in the dataset's folder (the injuries come as player_injuries_updated_<date>.csv)."""
    try:
        d = FILES[name].split("/")[0]
        ls = json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.github.com/repos/salimt/football-datasets/contents/datalake/transfermarkt/{d}",
                                                                      headers={"User-Agent": "Mozilla/5.0"}), timeout=60))
        names = sorted(x["name"] for x in ls if x["name"].endswith(".csv"))
        dated = [x for x in names if re.search(r"\d{8}", x)]
        return d + "/" + (dated[-1] if dated else names[-1])
    except Exception:
        return FILES[name]


def fetch(name, refetch=False):
    p = os.path.join(CACHE, name + ".csv")
    if not refetch and os.path.exists(p) and time.time() - os.path.getmtime(p) < 30 * 86400:
        return p
    os.makedirs(CACHE, exist_ok=True)
    rel = latest(name)
    for base in ((MEDIA, RAW) if name in BIG else (RAW, MEDIA)):
        try:
            r = urllib.request.urlopen(urllib.request.Request(base + rel, headers={"User-Agent": "Mozilla/5.0"}), timeout=600)
            tmp = p + ".part"
            with open(tmp, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            if os.path.getsize(tmp) > 1000 and not open(tmp, "rb").read(200).startswith(b"version https://git-lfs"):
                os.replace(tmp, p); print("fetched", name, os.path.getsize(p) // 1024, "KB"); return p
        except Exception as e:
            print("fetch", name, base, e)
    if os.path.exists(p):
        return p
    raise SystemExit(f"can't fetch {name}")


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s.replace("-", " ")).split()


def stale(s):
    """The career file is a snapshot of about September 2025: its 25/26 lines (and calendar-year 2025) are partial, and
    FotMob has those seasons whole."""
    mm = re.match(r"(\d{2})/(\d{2})$", s or "")
    if mm:
        return 25 <= int(mm.group(1)) < 60
    mm = re.match(r"(\d{4})$", s or "")
    return bool(mm) and int(mm.group(1)) >= 2025


def num(x, f=int):
    try:
        return f(float(x)) if x not in (None, "", "nan", "N/A") else None
    except Exception:
        return None


def clean(x):
    return None if x in (None, "", "nan", "N/A", "None") else x


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); ap.add_argument("--refetch", action="store_true"); a = ap.parse_args(argv)
    paths = {k: fetch(k, a.refetch) for k in FILES}

    def jget(u):
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"}), timeout=120)
            b = r.read()
            return json.loads(gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b)
        except Exception as e:
            print("can't read", u, e); return {}
    fm = {int(k): (v.get("name"), v.get("born")) for k, v in (jget("https://tifo.elyoxe.com/v1/history/fm/players.json").get("players") or {}).items()}
    for k, v in (jget("https://tifo.elyoxe.com/v1/world/bios.json").get("players") or {}).items():
        fm.setdefault(int(k), (v[0], v[1]))
    by_dob = {}
    for fid, (nm, born) in fm.items():
        if born and nm:
            by_dob.setdefault(born, []).append(fid)
    print(len(fm), "FotMob players")
    # 1. profiles -> the match
    prof, taken = {}, {}
    with open(paths["player_profiles"], encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            d = (r.get("date_of_birth") or "")[:10]
            cands = by_dob.get(d)
            if not cands:
                continue
            tn = fold(re.sub(r"\s*\(\d+\)\s*$", "", r.get("player_name") or ""))
            if not tn:
                continue
            hits = [fid for fid in cands if (lambda fn: fn and (set(tn) <= set(fn) or set(fn) <= set(tn)))(fold(fm[fid][0]))]
            if len(hits) == 1:
                taken.setdefault(hits[0], []).append(r["player_id"]); prof[r["player_id"]] = r
    m = {fid: tms[0] for fid, tms in taken.items() if len(tms) == 1}
    tm2fm = {t: f for f, t in m.items()}
    print(len(m), "players matched to Transfermarkt")
    docs = {}
    for fid, t in m.items():
        r = prof[t]
        cit = [c.strip() for c in re.split(r"\s{2,}", r.get("citizenship") or "") if c.strip()]
        docs[fid] = {"player": fid, "tm": int(t), "born_in": [clean(r.get("place_of_birth")), clean(r.get("country_of_birth"))], "citizenship": cit,
                     "agent": clean(r.get("player_agent_name")), "outfitter": clean(r.get("outfitter")), "joined": clean(r.get("joined")),
                     "contract": clean(r.get("contract_expires")), "option": clean(r.get("contract_option")), "extended": clean(r.get("date_of_last_contract_extension")),
                     "native": clean(r.get("name_in_home_country")), "died": clean(r.get("date_of_death")), "position": clean(r.get("position")),
                     "loan_from": clean(r.get("on_loan_from_club_name")), "career": [], "injuries": [], "source": "Transfermarkt (salimt/football-datasets)"}
    # 2. every season x competition x club
    t0 = time.time()
    with open(paths["player_performances"], encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            fid = tm2fm.get(r.get("player_id"))
            if fid is None or stale(r.get("season_name")):
                continue
            apps = num(r.get("nb_on_pitch"))
            if not apps and not num(r.get("nb_in_group")):
                continue
            docs[fid]["career"].append([r.get("season_name"), r.get("competition_id"), r.get("competition_name"), num(r.get("team_id")), r.get("team_name"), num(r.get("nb_in_group")), apps,
                                        num(r.get("goals")), num(r.get("assists")), num(r.get("minutes_played")), num(r.get("yellow_cards")), num(r.get("second_yellow_cards")),
                                        num(r.get("direct_red_cards")), num(r.get("subed_in")), num(r.get("subed_out")), num(r.get("penalty_goals")), num(r.get("own_goals")),
                                        num(r.get("goals_conceded")), num(r.get("clean_sheets"))])
    print(f"career lines read ({round(time.time() - t0)}s)")
    # 3. injuries
    with open(paths["player_injuries"], encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            fid = tm2fm.get(r.get("player_id"))
            if fid is None:
                continue
            docs[fid]["injuries"].append([r.get("season_name"), clean(r.get("injury_reason")), clean((r.get("from_date") or "")[:10]), clean((r.get("end_date") or "")[:10]),
                                          num(r.get("days_missed")), num(r.get("games_missed"))])

    def season_key(s):   # "08/09" -> 2009, "2009" -> 2009
        mm = re.match(r"(\d{2})/(\d{2})$", s or "")
        if mm:
            y = int(mm.group(2)); return (2000 + y) if y < 60 else (1900 + y)
        mm = re.match(r"(\d{4})", s or "")
        return int(mm.group(1)) if mm else 0
    for d in docs.values():
        d["career"].sort(key=lambda x: (-season_key(x[0]), -(x[6] or 0)))
        d["injuries"].sort(key=lambda x: x[2] or "", reverse=True)
    # Arabic club names: Transfermarkt's English name folded like FotMob's (world index + site teams), one Arabic name only
    from db.scores365 import fold as ffold
    by = {}
    for c in jget("https://tifo.elyoxe.com/v1/world/index.json").get("clubs") or []:
        by.setdefault(ffold(c[2]), set()).add(c[1])
    for k, t in (jget("https://tifo.elyoxe.com/v1/teams.json").get("teams") or {}).items():
        if t.get("name_ar"):
            by.setdefault(ffold(t.get("name")), set()).add(t["name_ar"])
    arn = {k: next(iter(v)) for k, v in by.items() if k and len(v) == 1}
    for d in docs.values():
        d["names_ar"] = {str(r[3]): arn[ffold(r[4])] for r in d["career"] if ffold(r[4]) in arn}
    n_car = sum(1 for d in docs.values() if d["career"]); n_inj = sum(1 for d in docs.values() if d["injuries"])
    print(f"{len(docs)} players: {n_car} with a career, {n_inj} with injuries")
    if a.upload:
        store = Store(S3Backend(BUCKET))
        t0 = time.time()
        with ThreadPoolExecutor(12) as ex:
            list(ex.map(lambda d: store.put_json(f"player/{d['player']}/tm.json", d, cache="warm"), docs.values()))
        store.put_json("history/tm/index.json", {"generated": date.today().isoformat(), "players": {str(f): int(t) for f, t in m.items()}}, cache="warm")
        print(f"uploaded ({round(time.time() - t0)}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
