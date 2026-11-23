"""The graph's one network step, before the loaders: martj42's internationals (CC0), weekly."""
import os, re, time, urllib.parse, urllib.request
from datetime import datetime

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


ENGSOCCER = "https://raw.githubusercontent.com/jalapic/engsoccerdata/master/data-raw/"


def engsoccer(S, max_age_days=7):
    """England's four tiers since 1888, the play-offs and test matches, the FA Cup since 1871, the League Cup since 1960 (jalapic/engsoccerdata), weekly."""
    for name in ("england", "englandplayoffs", "facup", "leaguecup"):
        p = os.path.join(S.db, f"engsoccer_{name}.csv")
        if not os.path.exists(p) or time.time() - os.path.getmtime(p) > max_age_days * 86400:
            data = urllib.request.urlopen(urllib.request.Request(ENGSOCCER + name + ".csv", headers={"User-Agent": "elyoxe-tifo/0.1"}), timeout=180).read()
            open(p + ".tmp", "wb").write(data)
            os.replace(p + ".tmp", p)


def _wiki_name(v):
    """«[[Manchester United F.C.|Manchester United]]» -> «Manchester United»"""
    m = re.search(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", v or "")
    return (m.group(1) if m else re.sub(r"<[^>]+>|\{\{[^}]*\}\}", "", v or "")).strip()


def shield_row(raw):
    """[date, team1, team2, team1 goals, team2 goals] from a Charity/Community Shield edition's infobox (the shoot-out apart)"""
    f = {}
    for k, v in re.findall(r"^\s*\|\s*(team1|team2|team1score|team2score|score|date)\s*=\s*(.*?)\s*$", raw, re.M):
        f.setdefault(k, v)
    sd = re.search(r"\{\{\s*start date\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})", f.get("date", ""), re.I)   # {{Start date|2019|8|4}}
    try:
        d = (f"{sd.group(1)}-{int(sd.group(2)):02d}-{int(sd.group(3)):02d}" if sd else
             datetime.strptime(re.sub(r"<[^>]+>|\{\{[^}]*\}\}", "", f.get("date", "")).strip(), "%d %B %Y").date().isoformat())
    except ValueError:
        return None
    if f.get("team1score", "").strip().isdigit() and f.get("team2score", "").strip().isdigit():
        hs, as_ = int(f["team1score"]), int(f["team2score"])
    else:
        m = re.match(r"\s*(\d+)\s*[–\-]\s*(\d+)", f.get("score", ""))
        if not m:
            return None
        hs, as_ = int(m.group(1)), int(m.group(2))
    t1, t2 = _wiki_name(f.get("team1")), _wiki_name(f.get("team2"))
    return [d, t1, t2, hs, as_] if t1 and t2 else None


SHIELD_LIST = "List of FA Community Shield matches"


def _state_file(S, name, key):
    """a pack fetched once on the laptop and kept in the bucket's state (graph/<key>): db/.cache/<name> for its loader"""
    import gzip as _gz, json as _j
    p = os.path.join(S.db, name)
    if os.path.exists(p):
        return
    d = S.store().get_state(key)
    if d:
        os.makedirs(S.db, exist_ok=True)
        with _gz.open(p + ".tmp", "wt", encoding="utf-8") as z:
            _j.dump(d, z, ensure_ascii=False)
        os.replace(p + ".tmp", p)


def rsssf_tops(S, max_age_days=30):
    """RSSSF's top-scorer lists read by graph/load/rsssf_tops.py: Argentina per tournament since 1891 (monthly)"""
    p = os.path.join(S.db, "rsssf_tops", "arg.html")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < max_age_days * 86400:
        return
    os.makedirs(os.path.dirname(p), exist_ok=True)
    body = urllib.request.urlopen(urllib.request.Request("https://www.rsssf.org/tablesa/argtops.html", headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
    if len(body) > 5000:
        open(p + ".tmp", "wb").write(body)
        os.replace(p + ".tmp", p)


def football_data(S, first=1995, last=2009):
    """football-data.co.uk's results files of the big five, 1995/96-2009/10 (graph/load/fdata.py): half-time scores, the Premier
    League's referees, attendances. Finished seasons, so each file is fetched once and kept (db/.cache/fdata/). The UAE's ISP
    blocks the site as «gambling» (22 Nov 2026), so this runs on GitHub Actions only."""
    d = os.path.join(S.db, "fdata")
    os.makedirs(d, exist_ok=True)
    for div in ("E0", "SP1", "I1", "D1", "F1"):
        for y in range(first, last + 1):
            p = os.path.join(d, f"{div}-{y}.csv")
            if os.path.exists(p):
                continue
            code = f"{y % 100:02d}{(y + 1) % 100:02d}"
            try:
                body = urllib.request.urlopen(urllib.request.Request(f"https://www.football-data.co.uk/mmz4281/{code}/{div}.csv",
                                                                     headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
            except Exception as e:
                print(f"football-data {div} {code}: {e}", flush=True)
                continue
            if body.lstrip(b"\xef\xbb\xbf")[:3] == b"Div":
                open(p + ".tmp", "wb").write(body)
                os.replace(p + ".tmp", p)
            time.sleep(1)


def espn(S):
    """ESPN's records of 2001-2010 (graph/espn_fetch.py): db/.cache/espn.json.gz for graph/load/espn.py"""
    _state_file(S, "espn.json.gz", "graph/espn.json")


def uaefa(S):
    """the UAE FA's record of the top flight 2003/04-2016/17 (graph/uaefa_fetch.py, fetched once on the laptop and kept in
    the bucket's state/graph/uaefa.json): db/.cache/uaefa.json.gz for graph/load/uaefa.py"""
    import gzip as _gz, json as _j
    p = os.path.join(S.db, "uaefa.json.gz")
    if os.path.exists(p):
        return
    d = S.store().get_state("graph/uaefa.json")
    if d:
        os.makedirs(S.db, exist_ok=True)
        with _gz.open(p + ".tmp", "wt", encoding="utf-8") as z:
            _j.dump(d, z, ensure_ascii=False)
        os.replace(p + ".tmp", p)


def community_shield(S, max_age_days=7):
    """{edition article: shield_row}: the Charity/Community Shield since 1908, the list's links read once each (only new
    editions on later runs), kept in db/.cache/shield.json; engsoccerdata has no Shield"""
    import json as _j
    from graph.awards_fetch import HTTP
    p = os.path.join(S.db, "shield.json")
    try:
        have = _j.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        have = {}
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < max_age_days * 86400:
        return have
    http = HTTP()
    raw = lambda t: http.get("https://en.wikipedia.org/w/index.php?" + urllib.parse.urlencode({"title": t, "action": "raw"}))
    lst = raw(SHIELD_LIST)
    lst = lst.decode("utf-8", "replace") if isinstance(lst, bytes) else lst
    for t in sorted(set(re.findall(r"\[\[(\d{4} FA (?:Charity|Community) Shield)", lst))):
        if t in have and have[t]:
            continue
        try:
            body = raw(t)
            have[t] = shield_row(body.decode("utf-8", "replace") if isinstance(body, bytes) else body)
        except Exception as e:
            print(f"shield {t}: {e}", flush=True)
    with open(p + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        _j.dump(have, f, ensure_ascii=False)
    os.replace(p + ".tmp", p)
    return have


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
