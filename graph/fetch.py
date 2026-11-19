"""The graph's one network step, before the loaders: martj42's internationals (CC0), weekly."""
import os, time, urllib.parse, urllib.request

MARTJ42 = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"


def martj42(S, max_age_days=7):
    p = os.path.join(S.db, "martj42_results.csv")
    if not os.path.exists(p) or time.time() - os.path.getmtime(p) > max_age_days * 86400:
        data = urllib.request.urlopen(urllib.request.Request(MARTJ42, headers={"User-Agent": "elyoxe-tifo/0.1"}), timeout=120).read()
        tmp = p + ".tmp"
        open(tmp, "wb").write(data)
        os.replace(tmp, p)
    return p


FJELSTUL = "https://raw.githubusercontent.com/jfjelstul/worldcup/master/data-csv/"


def fjelstul(S, max_age_days=7):
    """The World Cup database's award winners and players (CC-BY-SA), weekly."""
    for name in ("award_winners", "players", "matches", "goals", "bookings", "substitutions", "player_appearances",
                 "manager_appearances", "referee_appearances"):
        p = os.path.join(S.db, f"fjelstul_{name}.csv")
        if not os.path.exists(p) or time.time() - os.path.getmtime(p) > max_age_days * 86400:
            data = urllib.request.urlopen(urllib.request.Request(FJELSTUL + name + ".csv", headers={"User-Agent": "elyoxe-tifo/0.1"}), timeout=120).read()
            open(p + ".tmp", "wb").write(data)
            os.replace(p + ".tmp", p)


def wikidata_ar(S, qids, http=None, max_age_days=30):
    """{qid: {"label", "aliases", "at"}}: each player's Arabic label and aliases on Wikidata (graph/aliases.py), 50 items a
    request, at most one a second, kept in db/.cache/wd_ar.json and asked again after a month."""
    import json as _j
    from datetime import date
    p = os.path.join(S.db, "wd_ar.json")
    try:
        have = _j.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        have = {}
    today = date.today()
    todo = [q for q in qids if q and (q not in have or (today - date.fromisoformat(have[q].get("at", "2000-01-01"))).days > max_age_days)]
    if http is None:
        from graph.awards_fetch import HTTP
        http = HTTP()
    for i in range(0, len(todo), 50):
        ids = todo[i:i + 50]
        url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(ids), "props": "labels|aliases", "languages": "ar", "format": "json"})
        try:
            ents = _j.loads(http.get(url)).get("entities") or {}
        except Exception as e:
            print(f"wikidata ar: {e}", flush=True)
            continue
        for q in ids:
            e = ents.get(q) or {}
            have[q] = {"label": ((e.get("labels") or {}).get("ar") or {}).get("value"),
                       "aliases": [a.get("value") for a in ((e.get("aliases") or {}).get("ar") or []) if a.get("value")], "at": str(today)}
        if (i // 50) % 20 == 0:
            with open(p + ".tmp", "w", encoding="utf-8", newline="\n") as f:
                _j.dump(have, f, ensure_ascii=False)
            os.replace(p + ".tmp", p)
    with open(p + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        _j.dump(have, f, ensure_ascii=False)
    os.replace(p + ".tmp", p)
    return have


DCARIBOU = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/"


def depth(S, max_age_days=7):
    """Phase 4's other free sources, weekly: martj42's international scorers, and Transfermarkt's lineups, appearances and
    events (dcaribou, CC0)."""
    jobs = [(MARTJ42.replace("results.csv", "goalscorers.csv"), "martj42_goalscorers.csv")]
    jobs += [(DCARIBOU + f"{n}.csv.gz", f"tm_{n}.csv.gz") for n in ("game_lineups", "appearances", "game_events")]
    for url, name in jobs:
        p = os.path.join(S.db, name)
        if not os.path.exists(p) or time.time() - os.path.getmtime(p) > max_age_days * 86400:
            data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "elyoxe-tifo/0.1"}), timeout=600).read()
            open(p + ".tmp", "wb").write(data)
            os.replace(p + ".tmp", p)
