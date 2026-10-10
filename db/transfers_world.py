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
Out (public): v1/transfers/rumours.json {generated, rumours: [...]} (merge_rumours below), and
v1/transfers/all.json {generated, since, clubs: {id: [name, league id]}, moves: [[date, player id, player name,
from id, from name, to id, to name, fee EUR | null, kind, market value | null, nationality | null, position | null]]}, newest first;
kind: fee, loan, free, undisclosed, or "" (FotMob did not say)."""
import argparse, gzip, json, os, re, sys, time
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


def squad_card(tid, raw, names=None):
    """The world club card's squad (db/world.py's shape: [id, name, shirt, group, nationality]) for a site team the
    encyclopedia does not cover (a national team, a small club); None without a squad."""
    names = names or {}
    if not isinstance(raw, dict):
        return None
    members = [[m["id"], names.get(str(m["id"])) or m.get("name"), m.get("shirtNumber"), (g.get("title") or "").lower(), m.get("ccode")]
               for g in ((raw.get("squad") or {}).get("squad") or []) if isinstance(g, dict)
               for m in g.get("members") or [] if isinstance(m, dict) and m.get("id")]
    if not members:
        return None
    return {"id": tid, "name": (raw.get("details") or {}).get("name"), "name_ar": names.get(str(tid)), "squad": members}


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


# ---- phase 3: rumours. FotMob's allRumours (with its probability: Low, Medium, High, Imminent) and the news journal's transfer
# stories (news/transfers.json, with their stage) become one lasting ledger: a rumour keeps the day it was first seen, takes the
# news about the same player, and closes on the season's moves: «done» when the ledger shows him moving (to its club when known)
# from two weeks before the rumour on, «no» once the window it belonged to shut without it. A year after its last word it goes.
KEEP_DAYS = 365
# the news journal tags renewals and gossip «transfer» too (2026-10-09 first run: «تمديد عقد هافيرتز», «prolonge jusqu'en 2028»,
# «ينضم لمعسكر الزمالك»): a renewal is no rumour, and a news-only rumour needs talks at least; «official» came true
RENEW = re.compile(r"تمديد|يمدد|تجديد|يجدد|prolong|extend|extension|renew|new deal|nouveau contrat|verlänger", re.I)
STAGES = ["rumour", "talks", "agreed", "here_we_go", "official"]


def window_end(d):
    """The last day of the window a rumour on day d is about: summer (to 30 September) or winter (to the end of February)."""
    if d.month <= 2 or d.month >= 10:
        y = d.year + 1 if d.month >= 10 else d.year
        return date(y, 3, 1).fromordinal(date(y, 3, 1).toordinal() - 1)
    return date(d.year, 9, 30)


def fotmob_rumours(raws, names=None):
    names, out = names or {}, {}
    for raw in raws:
        for x in (((raw or {}).get("transfers") or {}).get("allRumours") or []) if isinstance(raw, dict) else []:
            if not isinstance(x, dict) or not x.get("rumourId") or not x.get("playerId"):
                continue
            if x.get("fromClubId") and x.get("fromClubId") == x.get("toClubId"):     # staying (a renewal), no move
                continue
            out[f"fm{x['rumourId']}"] = {"pid": int(x["playerId"]), "name": names.get(str(x["playerId"])) or x.get("name"),
                                         "from": [x.get("fromClubId"), names.get(str(x.get("fromClubId"))) or x.get("fromClub")] if x.get("fromClubId") else None,
                                         "to": [x.get("toClubId"), names.get(str(x.get("toClubId"))) or x.get("toClub")] if x.get("toClubId") else None,
                                         "seen": (x.get("transferDate") or "")[:10], "prob": x.get("probability"), "fee": fee_of(x),
                                         "src": x.get("sourceName") or None}
    return out


def merge_rumours(prev, fm, news, moves, today):
    rows = {r["k"]: dict(r) for r in prev or [] if r.get("k")}
    for k, x in fm.items():
        if x.get("from") and x.get("to") and x["from"][0] == x["to"][0]:
            continue
        r = rows.get(k) or {"k": k, "first": x["seen"] or today.isoformat(), "stage": None, "stories": [], "out": None}
        r.update(pid=x["pid"], name=r.get("name") if r.get("named") else x["name"], to=x["to"], prob=x["prob"], fee=x["fee"] or r.get("fee"),
                 last=max(x["seen"] or "", r.get("last") or ""))
        r["from"] = x["from"]
        r["src"] = x.get("src") or r.get("src")       # who FotMob says carried it (the sources page ranks them)
        rows[k] = r
    by_pid = {}
    for r in rows.values():
        by_pid.setdefault(r["pid"], []).append(r)
    for p in news or []:
        pid = (p.get("player") or {}).get("id")
        if not pid:
            continue
        kept = [s for s in p.get("stories") or [] if not RENEW.search(s.get("title") or "")]
        if not kept:
            continue
        stage = max((s.get("stage") for s in kept if s.get("stage") in STAGES), key=STAGES.index, default=None)
        st = [[s.get("id"), s.get("title"), (s.get("at") or "")[:10], s.get("first")] for s in kept]
        last = max([s[2] for s in st] or [today.isoformat()])
        targets = by_pid.get(pid) or []
        if not targets and STAGES.index(stage or "rumour") < 1:
            continue
        if not targets:
            k = f"n{pid}"
            r = rows.get(k) or {"k": k, "pid": pid, "from": None, "to": None, "first": min([s[2] for s in st] or [last]), "prob": None, "fee": None, "out": None}
            rows[k] = r
            targets = [r]
        for r in targets:
            seen = {s[0] for s in r.get("stories") or []}
            r["stories"] = sorted((r.get("stories") or []) + [s for s in st if s[0] not in seen], key=lambda s: s[2], reverse=True)[:3]
            r.update(stage=stage or r.get("stage"), name=(p.get("player") or {}).get("name") or r.get("name"), named=True,
                     last=max(last, r.get("last") or ""))
            if stage == "official" and r.get("out") != "done":
                r.update(out="done", done=max(s[2] for s in st if any(k.get("id") == s[0] and k.get("stage") == "official" for k in kept)))
    out = []
    for r in rows.values():
        if (today - date.fromisoformat(r["last"] or r["first"])).days > KEEP_DAYS:
            continue
        if r.get("out") != "done":
            since = date.fromordinal(date.fromisoformat(r["first"]).toordinal() - 14).isoformat()
            hit = next((m for m in moves or [] if m[1] == r["pid"] and m[0] >= since and (not r.get("to") or m[5] == r["to"][0])), None)
            if hit:
                r.update(out="done", done=hit[0], fee=hit[7] or r.get("fee"))
            elif today > window_end(date.fromisoformat(r["last"] or r["first"])):
                r["out"] = "no"
        out.append(r)
    out.sort(key=lambda r: (r.get("last") or "", r["k"]), reverse=True)
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
    world = set(clubs)
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
        # the site's teams the encyclopedia does not cover (national teams, small clubs): their squad card for the team page
        cards = [c for i, raw in zip(ids, raws) if i in site and i not in world for c in [squad_card(i, raw, names)] if c]
        with ThreadPoolExecutor(8) as ex:
            list(ex.map(lambda c: store.put_json(f"world/club/{c['id']}.json", c, cache="warm"), cards))
        print(json.dumps({"squad_cards": len(cards)}))
        store.put_json("transfers/all.json", {"generated": today.isoformat(), "since": season_since(today),
                                              "clubs": {str(k): v for k, v in clubs.items()}, "moves": L}, cache="warm")
        print("uploaded v1/transfers/all.json")
        prev = (store.get_json("transfers/rumours.json") or {}).get("rumours") or []
        R = merge_rumours(prev, fotmob_rumours(raws, names), (store.get_json("news/transfers.json") or {}).get("players") or [], L, today)
        store.put_json("transfers/rumours.json", {"generated": today.isoformat(), "rumours": R}, cache="warm")
        print(json.dumps({"rumours": len(R), "open": sum(1 for r in R if not r.get("out")), "done": sum(1 for r in R if r.get("out") == "done"),
                          "no": sum(1 for r in R if r.get("out") == "no")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
