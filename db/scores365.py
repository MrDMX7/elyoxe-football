"""365Scores (webws.365scores.com: open JSON, Arabic with langId=27) for what FotMob and our other sources lack
(owner 2026-09-30: «اريد كل كرة القدم فموقعي»):

  1. champions of every competition 365Scores keeps a history for (~640): the Premier League from 1888/89, the UAE league
     from 1973/74, the President's Cup from 1974-75, every Arab league and cup, with the winner's id and W-D-L-points;
  2. final tables of the Arab competitions for every season 365Scores has one (Jordan from 2010/11);
  3. this season and last in full for the Arab leagues FotMob doesn't cover (Jordan, Lebanon, Syria, Libya, Sudan,
     Palestine, Yemen, Bahrain, Oman, their cups): results, fixtures, lineups and events, top scorers, squads with Arabic
     names, and every squad player's card (bio, career by season, trophies, transfers).

Past seasons' matches are not served (results page back one season only; seasonNum and dates are ignored).

    python -m db.scores365 [--upload] [--only champions,tables,live,players] [--comp 565]

Out (public, v1/s365/):
  index.json           competitions [id, ar, en, country id, knockout, titles, first, last, women, tables, live],
                       countries {id: [ar, en]}, teams [id, ar, en, country id, fotmob id], players [id, ar, en, team id]
  comp/<id>.json       champions [[season, winner id, [values]]] + cols, tables {season: [[pos, team, p, w, d, l, gf, ga, pts]]},
                       live: results, fixtures, scorers; names {team id: ar}
  team/<id>.json       titles [[comp id, comp ar, [seasons]]], fotmob id; live teams: squad, games
  game/<id>.json       lineups, events, venue, referee (live competitions)
  player/<id>.json     bio, career, trophies, transfers (live competitions' squads)
  fmmap.json           {fotmob team id: 365 team id} (English or Arabic name within the same country, one to one)
Cache: db/.cache/s365/ (history 6 days, finished games for good, the rest 20 hours).
"""
import argparse, gzip, hashlib, json, os, re, sys, time, unicodedata, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
BASE = "https://webws.365scores.com"
QA = "appTypeId=5&langId=27&timezoneName=Asia/Dubai&userCountryId=-1"
QE = "appTypeId=5&langId=1&timezoneName=Asia/Dubai&userCountryId=-1"
CACHE = os.path.join(HERE, ".cache", "s365")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36",
     "Accept": "application/json", "Accept-Encoding": "gzip", "Origin": "https://www.365scores.com", "Referer": "https://www.365scores.com/"}
DAY = 86400
# 365Scores country ids of the Arab world
ARAB = {122, 131, 124, 127, 135, 115, 161, 119, 123, 125, 139, 130, 114, 116, 117, 126, 226, 170}
# ... and those FotMob has no league for: their competitions get the full live season
LIVE_CC = {161, 119, 123, 125, 130, 116, 117, 226, 170}
WOMEN = re.compile(r"women|femin|ladies|سيدات|نسائي|للسيدات|السيدات", re.I)
NOWIN = re.compile(r"^(no winner|not held|not played|not completed|cancel|abandon|void|tbd|unknown|n/a)", re.I)   # 365's placeholder «winners»
YOUTH = re.compile(r"u-?1\d|u-?2\d|youth|junior|reserve|تحت \d\d|الشباب تحت|الناشئين|الأولمبي", re.I)


def fetch(path, ttl):
    """GET BASE+path as JSON through a gzip file cache; None when 365Scores has nothing (404/500) or keeps failing."""
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, hashlib.sha1(path.encode()).hexdigest()[:20] + ".json.gz")
    if os.path.exists(f) and (ttl is None or time.time() - os.path.getmtime(f) < ttl):
        try:
            d = json.loads(gzip.open(f, "rt", encoding="utf-8").read())
            return None if isinstance(d, dict) and d.get("_err") else d
        except Exception:
            pass
    for i in range(3):
        try:
            r = urllib.request.urlopen(urllib.request.Request(BASE + path, headers=H), timeout=30)
            b = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                b = gzip.decompress(b)
            d = json.loads(b)
            with gzip.open(f, "wt", encoding="utf-8") as g:
                g.write(json.dumps(d, ensure_ascii=False))
            return d
        except urllib.error.HTTPError as e:
            if e.code in (400, 404, 500):
                with gzip.open(f, "wt", encoding="utf-8") as g:
                    g.write(json.dumps({"_err": e.code}))
                return None
            time.sleep(2 + 3 * i)
        except Exception:
            time.sleep(2 + 3 * i)
    return None


def pmap(fn, items, n=4):
    with ThreadPoolExecutor(n) as ex:
        return list(ex.map(fn, items))


# ------------------------------------------------------------------ names, for the FotMob map
STOP = {"fc", "sc", "cf", "ac", "afc", "club", "cd", "sd", "ud", "fk", "sk", "bk", "if", "ik", "calcio", "clube", "de", "al", "el", "the", "sv",
        "vfb", "vfl", "tsg", "as", "ss", "us", "rc", "rcd", "ca", "cr", "ec", "se", "sa", "saudi", "club", "kv", "krc", "nk", "hnk", "gnk", "fk", "pfc"}


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join(w for w in s.split() if w not in STOP)


def fold_ar(s):
    s = str(s or "")
    s = re.sub("[ً-ْـ]", "", s)
    s = re.sub("[أإآ]", "ا", s).replace("ة", "ه").replace("ى", "ي")
    s = re.sub(r"^ال|\sال", " ", " " + s)
    return " ".join(s.split())


CC_ALIAS = {"turkiye": "turkey", "usa": "united states", "uae": "united arab emirates", "south korea": "korea republic", "republic of korea": "korea republic",
            "czechia": "czech republic", "ivory coast": "cote d ivoire", "bosnia herzegovina": "bosnia and herzegovina", "the phillipines": "philippines",
            "north macedonia": "macedonia", "chinese taipei": "taiwan", "dr congo": "congo dr", "cape verde islands": "cape verde"}


def cc_key(name):
    k = " ".join(re.sub(r"[^a-z0-9 ]+", " ", unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()).split())
    return CC_ALIAS.get(k, k)


# the site's competitions (FotMob ids) -> 365Scores', for their champions through history
SITE_COMPS = {538: 549, 11027: 6181, 9943: 6346, 11026: 5447, 329: 5452, 290: 6196, 77: 5930, 10242: 7674, 9571: 6332, 525: 623, 9469: 568,
              9470: 8135, 10474: 6840, 78: 5096, 10703: 8268, 536: 649, 9942: 5501, 10074: 6164, 535: 408, 519: 552, 47: 7, 87: 11, 55: 17, 54: 25,
              53: 35, 42: 572, 73: 573, 10216: 7685, 530: 557, 11840: 5420, 516: 560, 544: 554, 9941: 553, 10314: 5595, 524: 6822, 529: 5473,
              10721: 5502, 11018: 6242, 526: 624, 9468: 627, 289: 167, 130: 104, 10043: 7242, 297: 171, 44: 595, 45: 102, 299: 389, 112: 72,
              268: 113, 9806: 7016, 50: 6316}

EN_ALIAS = {"wolves": "wolverhampton wanderers", "spurs": "tottenham hotspur", "sheffield utd": "sheffield united", "sheffield wed": "sheffield wednesday",
            "man utd": "manchester united", "man city": "manchester city", "west brom": "west bromwich albion", "nottm forest": "nottingham forest",
            "psg": "paris saint germain", "qpr": "queens park rangers", "brighton": "brighton hove albion", "wba": "west bromwich albion"}


def fotmob_map(teams, countries):
    """365 team id -> FotMob team id, by folded English name (or Arabic) inside the same country, one to one only."""
    def jget(u):
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": H["User-Agent"], "Accept-Encoding": "gzip"}), timeout=60)
            b = r.read()
            return json.loads(gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b)
        except Exception as e:
            print("fotmob map: can't read", u, e); return {}
    wi = jget("https://tifo.elyoxe.com/v1/world/index.json").get("clubs") or []
    st = jget("https://tifo.elyoxe.com/v1/teams.json").get("teams") or {}
    al = jget("https://www.fotmob.com/api/data/allLeagues")
    fm_cc = {c.get("ccode"): cc_key(c.get("name")) for c in (al.get("countries") or [])}
    iso_cc = {}
    fm = {}                                   # fotmob id -> (en fold, ar fold, country key or None)
    side = lambda en, ar: YOUTH.search(en or "") or WOMEN.search((en or "") + " " + (ar or "")) or re.search(r"\s(ii|b)$|\(w\)|\bwfc\b", (en or "").lower()) or "تحت" in (ar or "")
    for c in wi:
        if not side(c[2], c[1]):
            fm[int(c[0])] = (fold(c[2]), fold_ar(c[1]), fm_cc.get(c[3]))
    for k, t in st.items():
        k = int(k)
        if k not in fm and not side(t.get("name"), t.get("name_ar")):
            fm[k] = (fold(t.get("name")), fold_ar(t.get("name_ar")), cc_key((t.get("country") or {}).get("name")) if (t.get("country") or {}).get("name") else None)
    by_en, by_ar, by_cc = {}, {}, {}
    for fid, (en, ar, ck) in fm.items():
        if en:
            by_en.setdefault((en, ck), []).append(fid)
        if ar:
            by_ar.setdefault((ar, ck), []).append(fid)
        if ck:
            by_cc.setdefault(ck, []).append(fid)
    nat = {}                                  # national teams: the site's teams with no club country, by name alone
    for fid, (en, ar, ck) in fm.items():
        if ck is None:
            if en:
                nat.setdefault(en, []).append(fid)
            if ar:
                nat.setdefault(ar, []).append(fid)

    def subset(x, y):
        x, y = set(x.split()), set(y.split())
        return bool(x) and bool(y) and (x <= y or y <= x)

    out, used = {}, {}
    for sid, row in teams.items():
        ar, en, cid = row[0], row[1], row[2]
        ck = cc_key((countries.get(cid) or ["", ""])[1]) if cid in countries else None
        e, r, cand = fold(en), fold_ar(ar), None
        e = EN_ALIAS.get(e, e)
        national = len(row) > 3 and row[3] == 2
        if ck and not national:
            for src, key in ((by_en, (e, ck)), (by_ar, (r, ck))):     # 1. the same name in the same country
                hits = (src.get(key) or []) if key[0] else []
                if len(hits) == 1:
                    cand = hits[0]; break
            if cand is None:                                          # 2. one name's words inside the other's, one club only
                hits = {f for f in by_cc.get(ck, []) if (e and subset(e, fm[f][0])) or (r and subset(r, fm[f][1]))}
                if len(hits) == 1:
                    cand = hits.pop()
        # 3. a national team: its name is its country's (never a club across borders)
        if cand is None and national:
            hits = set(nat.get(e, [])) | set(nat.get(r, []))
            if len(hits) == 1:
                cand = hits.pop()
        if cand is not None:
            used.setdefault(cand, []).append(sid)
            out[sid] = cand
    for fid, sids in used.items():            # one to one
        if len(sids) > 1:
            for s_ in sids:
                out.pop(s_, None)
    return out


# ------------------------------------------------------------------ 1. champions
def champions(only=None):
    ca, ce = fetch(f"/web/competitions/?{QA}&sports=1", 7 * DAY), fetch(f"/web/competitions/?{QE}&sports=1", 7 * DAY)
    if not ca:
        raise SystemExit("365Scores: no competitions list")
    countries = {c["id"]: [c.get("name"), ""] for c in ca.get("countries") or []}
    for c in (ce or {}).get("countries") or []:
        if c["id"] in countries:
            countries[c["id"]][1] = c.get("name")
    en_comp = {c["id"]: c.get("name") for c in (ce or {}).get("competitions") or []}
    comps = [c for c in ca.get("competitions") or [] if c.get("hasHistory") and c.get("sportId", 1) == 1]
    if only:
        comps = [c for c in comps if c["id"] in only]
    print(len(comps), "competitions with a history")
    t0 = time.time()
    ha = pmap(lambda c: fetch(f"/web/competitions/history/?{QA}&competitions={c['id']}", 6 * DAY), comps)
    he = pmap(lambda c: fetch(f"/web/competitions/history/?{QE}&competitions={c['id']}", 30 * DAY), comps)
    teams, out = {}, {}
    for c, a, e in zip(comps, ha, he):
        if not a or not (a.get("table") or {}).get("rows"):
            continue
        for t in a.get("competitors") or []:
            teams.setdefault(t["id"], [t.get("name"), "", t.get("countryId"), t.get("type")])
        for t in (e or {}).get("competitors") or []:
            if t["id"] in teams and not teams[t["id"]][1]:
                teams[t["id"]][1] = t.get("name")
        tb = a["table"]
        cols = [x.get("name") for x in sorted(tb.get("columns") or [], key=lambda x: x.get("order", 0))]
        order = [x.get("num") for x in sorted(tb.get("columns") or [], key=lambda x: x.get("order", 0))]
        rows = []
        for r in tb["rows"]:
            vals = {v.get("columnNum"): v.get("value") for v in r.get("values") or []}
            w = r.get("entityId") or None
            if w and (NOWIN.search((teams.get(w) or ["", ""])[1] or "") or (teams.get(w) or [""])[0] in ("لا فائز", "بدون فائز")):
                w = None
            rows.append([r.get("title"), w, [vals.get(n, "") for n in order] if vals and w else [], r.get("seasonNum") if r.get("hasTable") else 0])
        nm = c.get("name") or ""
        out[c["id"]] = {"id": c["id"], "name": nm, "name_en": en_comp.get(c["id"]) or "", "cc": c.get("countryId"),
                        "country": (countries.get(c.get("countryId")) or [""])[0], "ko": 1 if tb.get("isChampionByKnockout") else 0,
                        "women": 1 if WOMEN.search(nm + " " + (en_comp.get(c["id"]) or "")) else 0,
                        "youth": 1 if YOUTH.search(nm + " " + (en_comp.get(c["id"]) or "")) else 0,
                        "cols": cols, "champions": rows}
    print(f"{len(out)} champion lists, {len(teams)} teams ({round(time.time() - t0)}s)")
    return out, teams, countries


# ------------------------------------------------------------------ 2. final tables (Arab competitions)
def tables(comps, teams):
    jobs = [(cid, r[3], r[0]) for cid, c in comps.items() if c["cc"] in ARAB for r in c["champions"] if r[3]]
    print(len(jobs), "Arab final tables")
    t0 = time.time()
    res = pmap(lambda j: fetch(f"/web/standings/?{QA}&competitions={j[0]}&seasonNum={j[1]}", 30 * DAY), jobs)
    n = 0
    for (cid, sn, title), j in zip(jobs, res):
        rows = []
        for i, st in enumerate((j or {}).get("standings") or []):
            for r in st.get("rows") or []:
                t = r.get("competitor") or {}
                if not t.get("id"):
                    continue
                teams.setdefault(t["id"], [t.get("name"), "", t.get("countryId"), t.get("type")])
                rows.append([r.get("position"), t["id"], r.get("gamePlayed"), r.get("gamesWon"), r.get("gamesEven"), r.get("gamesLost"), r.get("for"), r.get("against"),
                             r.get("points")] + ([st.get("groupName") or st.get("displayName") or i + 1] if len(j["standings"]) > 1 else []))
        if rows:
            comps[cid].setdefault("tables", {})[title] = rows; n += 1
    print(f"{n} tables ({round(time.time() - t0)}s)")


# ------------------------------------------------------------------ 3. the live season (Arab leagues FotMob lacks)
EV = {1: "g", 2: "y", 3: "r", 4: "s"}


def paged(first, key, maxp):
    out, j, n = [], fetch(first, 20 * 3600), 0
    while j and n < maxp:
        out += j.get("games") or []
        nxt = (j.get("paging") or {}).get(key)
        n += 1
        if not nxt or not (j.get("games") or []):
            break
        j = fetch(nxt, 20 * 3600)
    return out


def gshort(g):
    h, a = g.get("homeCompetitor") or {}, g.get("awayCompetitor") or {}
    sc = lambda x: None if x.get("score") is None or x.get("score") < 0 else int(x["score"])
    return [g["id"], (g.get("startTime") or "")[:16], g.get("seasonNum"), g.get("roundNum"), h.get("id"), a.get("id"), sc(h), sc(a), g.get("statusGroup"),
            1 if g.get("hasLineups") else 0]


def game_doc(j):
    g = (j or {}).get("game")
    if not g:
        return None
    mem = {m["id"]: m for m in g.get("members") or [] if m.get("id")}
    h, a = g.get("homeCompetitor") or {}, g.get("awayCompetitor") or {}
    side = lambda cid: "h" if cid == h.get("id") else "a"
    who = lambda mid: ((mem.get(mid) or {}).get("athleteId"), (mem.get(mid) or {}).get("name"))
    lu = {}
    for s, t in (("h", h), ("a", a)):
        L = t.get("lineups") or {}
        ps = []
        for x in L.get("members") or []:
            m = mem.get(x.get("id")) or {}
            st = {s_.get("type"): s_.get("value") for s_ in x.get("stats") or []}
            mins = str(st.get(30) or "").replace("'", "")
            ps.append([m.get("athleteId"), m.get("name"), m.get("jerseyNumber"), ((x.get("formation") or {}).get("name") or (x.get("position") or {}).get("name") or ""),
                       1 if x.get("status") == 1 else 0, int(mins) if mins.isdigit() else None, st.get(27), st.get(26), x.get("ranking")])
        if ps:
            lu[s] = {"formation": L.get("formation"), "players": ps}
    ev = []
    for e in g.get("events") or []:
        et = e.get("eventType") or {}
        k = EV.get(et.get("id")) or ("s" if "تبديل" in (et.get("name") or "") else None)
        if not k:
            continue
        p1 = who(e.get("playerId"))
        p2 = who((e.get("extraPlayers") or [None])[0]) if e.get("extraPlayers") else (None, None)
        mn = int(e.get("gameTime") or 0)
        ev.append([str(mn) + (f"+{e['addedTime']}" if e.get("addedTime") else ""), k, side(e.get("competitorId")), p1[0], p1[1], p2[0], p2[1], et.get("subTypeName") or ""])
    sc = lambda x: None if x.get("score") is None or x.get("score") < 0 else int(x["score"])
    off = [o.get("name") for o in g.get("officials") or [] if o.get("name")]
    return {"id": g["id"], "comp": g.get("competitionId"), "comp_name": g.get("competitionDisplayName"), "season": g.get("seasonNum"), "round": g.get("roundNum"),
            "date": g.get("startTime"), "status": g.get("statusText"), "home": [h.get("id"), h.get("name"), sc(h)], "away": [a.get("id"), a.get("name"), sc(a)],
            "venue": (g.get("venue") or {}).get("name"), "referee": off[0] if off else None, "lineups": lu, "events": ev, "source": "365Scores"}


def live(comps, teams, only=None):
    ca = fetch(f"/web/competitions/?{QA}&sports=1", 7 * DAY) or {}
    targets = [c for c in ca.get("competitions") or [] if c.get("countryId") in LIVE_CC and not WOMEN.search(c.get("name") or "")]
    if only:
        targets = [c for c in targets if c["id"] in only]
    print(len(targets), "live competitions:", ", ".join(c["name"] for c in targets))
    games, team_games, docs = {}, {}, {}
    for c in targets:
        cid = c["id"]
        res = paged(f"/web/games/results/?{QA}&competitions={cid}", "previousPage", 14)
        fix = paged(f"/web/games/fixtures/?{QA}&competitions={cid}", "nextPage", 4)
        st = fetch(f"/web/stats/?{QA}&competitions={cid}", 20 * 3600) or {}
        cur = fetch(f"/web/standings/?{QA}&competitions={cid}", 20 * 3600) or {}
        for g in res + fix:
            for t in (g.get("homeCompetitor") or {}, g.get("awayCompetitor") or {}):
                if t.get("id"):
                    teams.setdefault(t["id"], [t.get("name"), "", t.get("countryId"), t.get("type")])
        R = {g["id"]: gshort(g) for g in res}
        F = {g["id"]: gshort(g) for g in fix if g["id"] not in R}
        sc = {}
        for cat in ((st.get("stats") or {}).get("athletesStats") or [])[:3]:
            sc[cat.get("name") or ""] = [[(r.get("entity") or {}).get("id"), (r.get("entity") or {}).get("name"), (r.get("entity") or {}).get("competitorId"),
                                          ((r.get("stats") or [{}])[0]).get("value")] for r in (cat.get("rows") or [])[:20]]
        table = []
        for s in cur.get("standings") or []:
            for r in s.get("rows") or []:
                t = r.get("competitor") or {}
                table.append([r.get("position"), t.get("id"), r.get("gamePlayed"), r.get("gamesWon"), r.get("gamesEven"), r.get("gamesLost"), r.get("for"), r.get("against"), r.get("points")])
        d = comps.setdefault(cid, {"id": cid, "name": c.get("name"), "name_en": "", "cc": c.get("countryId"), "country": "", "ko": 0, "women": 0, "youth": 0, "cols": [], "champions": []})
        d["live"] = {"results": sorted(R.values(), key=lambda x: x[1], reverse=True), "fixtures": sorted(F.values(), key=lambda x: x[1]), "scorers": sc, "table": table}
        for g in list(R.values()) + list(F.values()):
            games[g[0]] = g
            for t in (g[4], g[5]):
                team_games.setdefault(t, []).append(g[0])
        print(f"  {c['name']}: {len(R)} results, {len(F)} fixtures, {len(table)} in the table")
    done = [g for g in games.values() if g[8] == 4]
    t0 = time.time()
    raw = pmap(lambda g: fetch(f"/web/game/?{QA}&gameId={g[0]}", None), done)
    for g, j in zip(done, raw):
        d = game_doc(j)
        if d:
            docs[g[0]] = d
    print(f"{len(docs)} match pages ({round(time.time() - t0)}s)")
    return games, team_games, docs, targets


def squads(team_ids, teams):
    t0 = time.time()
    raw = pmap(lambda t: fetch(f"/web/squads/?{QA}&competitors={t}", 20 * 3600), team_ids)
    out = {}
    for tid, j in zip(team_ids, raw):
        sq = ((j or {}).get("squads") or [{}])[0].get("athletes") or []
        out[tid] = [[a.get("id"), a.get("name"), a.get("jerseyNum"), (a.get("position") or {}).get("name"), (a.get("formationPosition") or {}).get("name"), a.get("age"),
                     (a.get("birthdate") or "")[:10], a.get("height"), a.get("nationalityId"), (a.get("nameForURL") or "").replace("-", " ").title()] for a in sq if a.get("id")]
    print(f"{sum(len(v) for v in out.values())} squad players in {len(out)} teams ({round(time.time() - t0)}s)")
    return out


def player_doc(j, sq_row=None):
    a = ((j or {}).get("athletes") or [None])[0]
    if not a:
        return None
    det = {x.get("title"): x.get("value") for x in a.get("playerDetails") or []}
    career = []
    for s in (a.get("careerStats") or {}).get("seasons") or []:
        cats = ((s.get("stats") or {}).get("categories") or [])
        for i, tb in enumerate((s.get("stats") or {}).get("tables") or []):
            cols = {c.get("num"): (c.get("entity") or {}).get("id") for c in tb.get("columns") or []}
            for r in tb.get("rows") or []:
                v = {cols.get(x.get("columnNum")): x.get("value") for x in r.get("values") or []}
                career.append([s.get("name"), (cats[i].get("name") if i < len(cats) else ""), r.get("title"), v.get(5), v.get(6), v.get(1), v.get(2), v.get(3), v.get(4)])
    tro = []
    for cat in (a.get("trophies") or {}).get("categories") or []:
        for t in cat.get("trophies") or []:
            tro.append([cat.get("name"), t.get("displayName") or t.get("name"), t.get("count"),
                        [[r.get("title"), r.get("secondaryTitle")] for r in ((t.get("stats") or {}).get("rows") or [])]])
    tr = [[(t.get("date") or "")[:10], t.get("competitorId"), t.get("transferTitle"), t.get("price")] for t in a.get("transfers") or []]
    born = sq_row[6] if sq_row and sq_row[6] else None
    return {"id": a["id"], "name": a.get("name"), "en": (a.get("nameForURL") or "").replace("-", " ").title(), "age": a.get("age"), "born": born,
            "pos": (a.get("position") or {}).get("name"), "pos2": (a.get("formationPosition") or {}).get("name"), "nat": a.get("nationalityName"),
            "height": det.get("الطول"), "foot": det.get("القدم المفضلة"), "club": a.get("clubId"), "national": a.get("nationalTeamId"),
            "shirt": a.get("jerseyNum"), "contract": (a.get("contractUntil") or "")[:10] or None, "bio": a.get("shortBio"), "nat_text": a.get("nationalTeamStatsText"),
            "career": career, "trophies": tro, "transfers": tr,
            "names": {str(c["id"]): c.get("name") for c in (j.get("competitors") or []) if c and c.get("id")}, "source": "365Scores"}


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); ap.add_argument("--only", default="champions,tables,live,players")
    ap.add_argument("--comp", default=""); ap.add_argument("--index-only", action="store_true", help="upload only index.json, fmmap.json and fm.json")
    a = ap.parse_args(argv)
    steps = set(a.only.split(",")); only = {int(x) for x in a.comp.split(",") if x.strip()} or None
    comps, teams, countries = champions(only)
    if "tables" in steps:
        tables(comps, teams)
    games, team_games, gdocs, targets, sq, pdocs = {}, {}, {}, [], {}, {}
    if "live" in steps:
        games, team_games, gdocs, targets = live(comps, teams, only)
        sq = squads(sorted(t for t in team_games if t), teams)
        if "players" in steps:
            rows = {p[0]: p for v in sq.values() for p in v}
            t0 = time.time()
            raw = pmap(lambda p: fetch(f"/web/athletes/?{QA}&athletes={p}&fullDetails=true", 6 * DAY), sorted(rows))
            for pid, j in zip(sorted(rows), raw):
                try:
                    d = player_doc(j, rows[pid])
                except Exception as e:
                    print("skip player", pid, e); d = None
                if d:
                    pdocs[pid] = d
            print(f"{len(pdocs)} player cards ({round(time.time() - t0)}s)")
    fmm = fotmob_map(teams, countries)
    print(len(fmm), "teams linked to FotMob")
    # titles per team
    titles = {}
    for cid, c in comps.items():
        if c.get("youth"):
            continue
        for r in c["champions"]:
            if r[1]:
                titles.setdefault(r[1], {}).setdefault(cid, []).append(r[0])
    team_docs = {}
    for tid in set(titles) | set(team_games):
        nm = teams.get(tid) or ["", "", None]
        d = {"id": tid, "name": nm[0], "name_en": nm[1], "cc": nm[2], "country": (countries.get(nm[2]) or [""])[0], "fotmob": fmm.get(tid),
             "titles": sorted([[cid, comps[cid]["name"], s] for cid, s in (titles.get(tid) or {}).items()], key=lambda x: -len(x[2]))}
        if tid in team_games:
            d["squad"] = sq.get(tid) or []
            d["games"] = sorted([games[g] for g in set(team_games[tid])], key=lambda x: x[1], reverse=True)
            d["names"] = {str(k): (teams.get(k) or [""])[0] for g in d["games"] for k in (g[4], g[5])}
        team_docs[tid] = d
    for c in comps.values():
        ids = {r[1] for r in c["champions"] if r[1]} | {r[1] for rows in (c.get("tables") or {}).values() for r in rows}
        L = c.get("live") or {}
        ids |= {g[4] for g in L.get("results", []) + L.get("fixtures", [])} | {g[5] for g in L.get("results", []) + L.get("fixtures", [])} | {r[1] for r in L.get("table", [])}
        c["names"] = {str(k): (teams.get(k) or [""])[0] for k in ids if k}
        c["names_en"] = {str(k): (teams.get(k) or ["", ""])[1] for k in ids if k}
        c["generated"] = date.today().isoformat()
    live_ids = {c["id"] for c in targets}
    idx = {"generated": date.today().isoformat(), "countries": {str(k): v for k, v in countries.items()},
           "comps": [[c["id"], c["name"], c.get("name_en", ""), c["cc"], c["ko"], sum(1 for r in c["champions"] if r[1]),
                      (c["champions"][-1][0] if c["champions"] else ""), (c["champions"][0][0] if c["champions"] else ""), c.get("women", 0), len(c.get("tables") or {}),
                      1 if c["id"] in live_ids else 0, c.get("youth", 0)] for c in comps.values()],
           "teams": [[tid, d["name"], d["name_en"], d["cc"], d["fotmob"]] for tid, d in team_docs.items()],
           "players": [[pid, d["name"], d["en"], d["club"]] for pid, d in pdocs.items()]}
    print(f"{len(comps)} competitions, {len(team_docs)} teams, {len(gdocs)} matches, {len(pdocs)} players")
    # for the site's build: each linked club's titles, and each site competition's champions with FotMob ids
    fm = {"generated": date.today().isoformat(), "teams": {str(f): s_ for s_, f in fmm.items()},
          "titles": {str(fmm[t]): team_docs[t]["titles"] for t in fmm if t in team_docs and team_docs[t]["titles"]},
          "comps": {str(fid): {"id": sid, "name": comps[sid]["name"], "ko": comps[sid]["ko"], "cols": comps[sid]["cols"],
                               "champions": [[r[0], (teams.get(r[1]) or [""])[0], fmm.get(r[1]), r[2], r[1]] for r in comps[sid]["champions"]]}
                    for fid, sid in SITE_COMPS.items() if sid in comps}}
    print(len(fm["titles"]), "linked clubs with titles,", len(fm["comps"]), "site competitions with champions")
    if a.upload and a.index_only:
        store = Store(S3Backend(BUCKET))
        store.put_json("s365/fmmap.json", {"generated": date.today().isoformat(), "map": {str(f): s_ for s_, f in fmm.items()}}, cache="warm")
        store.put_json("s365/fm.json", fm, cache="warm")
        store.put_json("s365/index.json", idx, cache="warm")
        print("uploaded the index files")
    elif a.upload:
        store = Store(S3Backend(BUCKET))
        t0 = time.time()
        store.put_json("s365/fm.json", fm, cache="warm")
        pmap(lambda c: store.put_json(f"s365/comp/{c['id']}.json", c, cache="warm"), list(comps.values()), 8)
        pmap(lambda d: store.put_json(f"s365/team/{d['id']}.json", d, cache="warm"), list(team_docs.values()), 8)
        pmap(lambda d: store.put_json(f"s365/game/{d['id']}.json", d, cache="warm"), list(gdocs.values()), 8)
        pmap(lambda d: store.put_json(f"s365/player/{d['id']}.json", d, cache="warm"), list(pdocs.values()), 8)
        store.put_json("s365/fmmap.json", {"generated": date.today().isoformat(), "map": {str(f): s for s, f in fmm.items()}}, cache="warm")
        store.put_json("s365/index.json", idx, cache="warm")
        print(f"uploaded ({round(time.time() - t0)}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
