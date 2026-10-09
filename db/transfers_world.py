"""The transfer market of every club in the world (owner 2026-10-09: «نخليه لجميع اندية العالم»; spec
docs/superpowers/specs/2026-10-09-transfers-design.md, phase 1). FotMob's teams?id= lists each club's moves of this
season's windows (transfers.allTransfers); a move appears under both clubs, so the ledger keeps one row per player, day,
from and to, and leaves contract extensions out.

    python -m db.transfers_world [--upload] [--limit N]

Clubs: every club of v1/world/index.json (db/world.py) and of v1/teams.json, read from the FotMob cache db/world.py and
db/fotmob_profiles.py share (db/.cache/fm/t/). A run re-fetches at most BUDGET of them: in a window (June–September,
January–February) those older than WINDOW_TTL, outside it those older than the cache's 6 days; the site's own clubs first,
then the stalest. FotMob answers 429 when pushed (2026-10-09: ~40 clubs a minute with 4 threads), so the rest keep their
cached answer (every club is fresh within about 3 days in a window). A failed request keeps the cached answer.
Out (public): v1/transfers/all.json {generated, since, clubs: {id: [name, league id]}, moves: [[date, player id, player name,
from id, from name, to id, to name, fee EUR | null, kind, market value | null, nationality | null, position | null]]}, newest first;
kind: fee, loan, free, undisclosed, or "" (FotMob did not say)."""
import argparse, gzip, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

WINDOW_TTL = 20 * 3600
BUDGET = 1200
KINDS = {"transfer_fee": "fee", "on_loan": "loan", "transfer_type_free_transfer": "free", "undisclosed": "undisclosed"}


def window_open(d):
    return d.month in (1, 2, 6, 7, 8, 9)


def season_since(d):
    """«هالموسم»: from 1 June (last year's June before June)."""
    return f"{d.year if d.month >= 6 else d.year - 1}-06-01"


def kind_of(x):
    """fee, loan, free, undisclosed or ""; None for a contract extension (no move)."""
    fee = x.get("fee") if isinstance(x.get("fee"), dict) else {}
    if x.get("contractExtension") or fee.get("localizedFeeText") == "contract_extension":
        return None
    k = KINDS.get(fee.get("localizedFeeText"))
    if k:
        return k
    return "loan" if x.get("onLoan") else ""


def fee_of(x):
    fee = x.get("fee") if isinstance(x.get("fee"), dict) else {}
    v = fee.get("value") or x.get("amountEuroEstimated")
    try:
        return int(v) if v else None
    except (TypeError, ValueError):
        return None


def plan_fetch(ids, ages, priority, budget, ttl):
    """The clubs to fetch again: none fresh (age <= ttl); never cached first, then the site's, then the stalest; at most `budget`."""
    due = [i for i in ids if ages.get(i) is None or ages[i] > ttl]
    due.sort(key=lambda i: (ages.get(i) is not None, i not in priority, -(ages.get(i) or 0)))
    return due[:budget]


def nationalities(raws):
    out = {}
    for raw in raws:
        for g in (((raw or {}).get("squad") or {}).get("squad") or []):
            for m in (g or {}).get("members") or []:
                if isinstance(m, dict) and m.get("id") and m.get("ccode"):
                    out[int(m["id"])] = m["ccode"]
    return out


def ledger(raws, names=None):
    names, raws = names or {}, [r for r in raws if isinstance(r, dict)]
    nat, seen, out = nationalities(raws), set(), []
    nm = lambda i, fb: names.get(str(i)) or fb
    for raw in raws:
        for x in ((raw.get("transfers") or {}).get("allTransfers") or []):
            if not isinstance(x, dict) or not x.get("playerId"):
                continue
            k = kind_of(x)
            if k is None:
                continue
            pid, day = int(x["playerId"]), (x.get("transferDate") or "")[:10]
            key = (pid, day, x.get("fromClubId"), x.get("toClubId"))
            if not day or key in seen:
                continue
            seen.add(key)
            out.append([day, pid, nm(pid, x.get("name")), x.get("fromClubId"), nm(x.get("fromClubId"), x.get("fromClub")), x.get("toClubId"),
                        nm(x.get("toClubId"), x.get("toClub")), fee_of(x), k, x.get("marketValue") or None, nat.get(pid),
                        ((x.get("position") or {}).get("label") if isinstance(x.get("position"), dict) else None)])
    out.sort(key=lambda r: (r[0], r[1]), reverse=True)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--budget", type=int, default=BUDGET)
    a = ap.parse_args(argv)
    from store import Store, S3Backend
    from db import fotmob_profiles as FP
    from sources.fotmob import FotMob
    store = Store(S3Backend(FP.BUCKET))
    today = date.today()
    idx = store.get_json("world/index.json") or {}
    clubs = {int(c[0]): [c[1], c[4] if len(c) > 4 else None] for c in idx.get("clubs") or []}
    site = {int(k) for k in ((store.get_json("teams.json") or {}).get("teams") or {})}
    for tid in site:
        clubs.setdefault(tid, [None, None])
    ids = sorted(clubs)[: a.limit or None]
    path = lambda i: os.path.join(FP.CACHE, "t", f"{i}.json.gz")
    ages = {i: (time.time() - os.path.getmtime(path(i))) if os.path.exists(path(i)) else None for i in ids}
    fetch = set(plan_fetch(ids, ages, site, a.budget, WINDOW_TTL if window_open(today) else FP.TTL))

    FP.TTL = 0                            # fm_get fetches every club handed to it (only the due ones are)

    def get(i):
        if i in fetch:
            raw = FP.fm_get("t", i)       # None when FotMob refused: the cached answer below
            if raw is not None:
                return raw
        try:
            return json.loads(gzip.open(path(i)).read()) if os.path.exists(path(i)) else None
        except (OSError, ValueError):
            return None
    names = FotMob().http.get_json("https://www.fotmob.com/api/translationmapping?locale=ar", min_ttl=3600).get("Participants") or {}
    t0 = time.time()
    with ThreadPoolExecutor(4) as ex:
        raws = list(ex.map(get, ids))
    L = ledger(raws, names)
    print(json.dumps({"clubs": len(ids), "fetched": len(fetch), "answered": sum(1 for r in raws if r), "moves": len(L), "with_fee": sum(1 for r in L if r[7]),
                      "s": round(time.time() - t0)}))
    if a.upload:
        store.put_json("transfers/all.json", {"generated": today.isoformat(), "since": season_since(today),
                                              "clubs": {str(k): v for k, v in clubs.items()}, "moves": L}, cache="warm")
        print("uploaded v1/transfers/all.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
