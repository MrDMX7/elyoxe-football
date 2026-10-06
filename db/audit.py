"""The numbers audit (owner 2026-09-30: «واهم شي تدقيق الارقام… تصليح الاخطاء فقواعد البيانات وتكميل كل شي ناقص»): every day,
after the other stages, the numbers the site prints are checked against themselves, against FotMob now and against an
independent second source (365Scores), and what is missing is counted.

    python -m db.audit [--sample 60] [--days 14] [--area matches,standings,...] [--no-upload] [--local out/]

Areas (visitor impact first):
  freshness   the poller and the analytics function alive, health items failing, each laptop stage run on time, each
              competition's fixtures/table not older than its last result
  matches     the last --days days in the 61 competitions: our fixtures (status, score) vs FotMob now; the final score vs
              365Scores (paired by date + teams); a sample of --sample match pages (events: goals, scorers, assists, cards,
              subs) vs FotMob's detail now; every published match file's goal events vs its score (a merge must never
              add a goal); finished matches with no match page, and no matchx record (player logs are built from those)
  standings   P=W+D+L, points = 3W+D+deduction, GD = GF-GA, ranks, sums; the table vs our own results; vs FotMob now;
              vs 365Scores, and on a disagreement 365Scores' table vs its own results (which side is inconsistent)
  scorers     leaderboards vs FotMob now and vs 365Scores; the top scorers' season line in their match log (player page
              «أرقامه موسم بموسم») vs the leaderboard, season labels (calendar-year competitions) and log coverage
  derived     every head-to-head file (wins = the listed results, index counts, duplicates, this season's and last
              season's meetings all listed) and every club history (totals add up, no match twice, no club against itself,
              every match of our archive in it, one league position per season, no national team)
  champions   junk and placeholder winners, duplicated seasons, titles on national teams, our list vs 365Scores' (winners,
              year offsets, champions of seasons 365Scores marks void), the all-time tables' title counts
  identity    who is who: national teams carrying a club's card/lead/transfers, one Wikidata id on two clubs or players,
              Arabic Wikipedia leads of an unchecked or another person (birth year), RSSSF rows of two clubs on one id,
              365Scores' women's/youth/B sides in the club map, placeholder birth dates
  gaps       what is missing that a source has: match pages, scorers of low-coverage matches, player bio fields,
              club cards, Arabic names

Verdicts: ours (our code is wrong), stale (the source moved on, our copy didn't), gap (missing, fillable), source (the
sources disagree; `favors` says which one the evidence supports and `evidence` why), unknown.
Levels: error (a visitor sees a wrong number), warn (probably wrong or out of date), info.

Out: state/audit/<yyyy-mm-dd>.json (private, Store.put_state) and docs/AUDIT-DATA-<yyyy-mm-dd>.md; after a full run (every
area, uploads on) also v1/audit/latest.json, public, counts only, for the site's «الأرقام مدققة» badge (public_summary).
Gentle: FotMob and 365Scores each at most 2 requests a second; 365Scores answers are cached on disk (db/.cache/audit/).
"""
import argparse, difflib, gzip, hashlib, json, os, re, sys, threading, time, urllib.error, urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import config  # noqa: E402
from compute import awarded as AWARDED  # noqa: E402
from db import scores365 as S365  # noqa: E402
from sources import schema as S  # noqa: E402
from sources.fotmob import FotMob, placeholder_ar  # noqa: E402
from sources.http import Http  # noqa: E402
from store import Store, S3Backend, LocalBackend  # noqa: E402
from timeutil import now_utc, parse_utc, iso, UAE  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
CACHE = os.path.join(HERE, ".cache", "audit")
AREAS = ("freshness", "matches", "standings", "scorers", "derived", "champions", "identity", "gaps")
FOCUS = (538, 11027, 9943, 11026)                  # UAE competitions: sampled first
NONSTD_POINTS = {10043}                             # Leagues Cup: a drawn match goes to penalties (2 points / 1 point)
G = ("goal", "own_goal", "penalty_goal")
CARDS = ("yellow", "second_yellow", "red")
NOWIN = re.compile(r"^\s*(no winner|not held|not played|not completed|cancel|abandon|void|tbd|unknown|n/?a|-+|—)\s*$|لا فائز|بدون فائز|ألغيت|لم تكتمل", re.I)
PAGE = {"match": "/m/{}/", "team": "/t/{}/", "player": "/p/{}/"}


# ------------------------------------------------------------------ gentle clients
class Throttle:
    def __init__(self, per_sec):
        self.gap, self.next, self.lock = 1.0 / per_sec, 0.0, threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            at = max(now, self.next)
            self.next = at + self.gap
        if at > now:
            time.sleep(at - now)


class GentleHttp(Http):
    """sources.http.Http, at most `per_sec` network requests a second (a cached body is served without waiting)."""

    def __init__(self, per_sec=2.0):
        super().__init__(timeout=25)
        self.throttle = Throttle(per_sec)

    def get_bytes(self, url, headers=None, min_ttl=0):
        hit = self._cache.get(url)
        if not (hit and hit[0] > self.clock()):
            self.throttle.wait()
        return super().get_bytes(url, headers, min_ttl)


class S365Client:
    """365Scores' open JSON with a disk cache; an HTTP 500 or a timeout is never cached (db/scores365.py once kept a 500 for
    days: 69 champion histories went missing)."""

    def __init__(self, per_sec=2.0, cache=CACHE):
        self.throttle, self.cache, self.calls, self.errors = Throttle(per_sec), cache, 0, Counter()
        os.makedirs(cache, exist_ok=True)
        for fn in os.listdir(cache):             # the longest ttl asked for is 7 days: older answers are dead weight
            p = os.path.join(cache, fn)
            if fn.startswith("s365-") and time.time() - os.path.getmtime(p) > 8 * 86400:
                os.remove(p)

    def get(self, path, ttl):
        f = os.path.join(self.cache, "s365-" + hashlib.sha1(path.encode()).hexdigest()[:20] + ".json.gz")
        if ttl and os.path.exists(f) and time.time() - os.path.getmtime(f) < ttl:
            try:
                return json.loads(gzip.open(f, "rt", encoding="utf-8").read())
            except (OSError, ValueError):
                pass
        for i in range(3):
            self.throttle.wait()
            self.calls += 1
            try:
                r = urllib.request.urlopen(urllib.request.Request(S365.BASE + path, headers=S365.H), timeout=45)
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    b = gzip.decompress(b)
                d = json.loads(b)
                with gzip.open(f + ".tmp", "wt", encoding="utf-8") as g:
                    g.write(json.dumps(d, ensure_ascii=False))
                os.replace(f + ".tmp", f)
                return d
            except urllib.error.HTTPError as e:
                self.errors[e.code] += 1
                if e.code in (400, 404):
                    return None
            except Exception as e:  # timeout, reset, bad JSON
                self.errors[type(e).__name__] += 1
            time.sleep(2 + 3 * i)
        return None


class Pub:
    """The published files (what visitors get), read once per run."""

    def __init__(self, store):
        self.store, self._c, self.reads = store, {}, 0

    def get(self, path):
        if path not in self._c:
            try:
                self._c[path] = self.store.get_json(path)
            except Exception:
                self._c[path] = None
            self.reads += 1
        return self._c[path]

    def many(self, paths, threads=16):
        todo = [p for p in dict.fromkeys(paths) if p not in self._c]
        if todo:
            with ThreadPoolExecutor(threads) as ex:
                list(ex.map(self.get, todo))
        return {p: self._c.get(p) for p in paths}

    def keys(self, prefix):
        """[(path under v1/, size, last modified datetime)] of the published files under v1/<prefix>."""
        b = self.store.b
        if isinstance(b, S3Backend):
            out = []
            for page in b.s3.get_paginator("list_objects_v2").paginate(Bucket=b.bucket, Prefix="v1/" + prefix):
                out += [(o["Key"][3:], o["Size"], o["LastModified"]) for o in page.get("Contents") or []]
            return out
        root = os.path.join(str(b.root), "v1")
        out = []
        for dp, _, fs in os.walk(os.path.join(root, prefix)):
            for fn in fs:
                if not fn.endswith(".meta"):
                    p = os.path.join(dp, fn)
                    out.append((os.path.relpath(p, root).replace("\\", "/"), os.path.getsize(p), None))
        return out


# ------------------------------------------------------------------ names and pairing (FotMob <-> 365Scores)
def _fold(name):
    f = S365.fold(name)
    return S365.EN_ALIAS.get(f, f)


def name_sim(a, b):
    """0..1: the same club/nation under two spellings (token containment, national-team aliases, near-identical)."""
    fa, fb = _fold(a), _fold(b)
    if not fa or not fb:
        return 0.0
    if fa == fb or S365.cc_key(a) == S365.cc_key(b):
        return 1.0
    ta, tb = set(fa.split()), set(fb.split())
    inter = len(ta & tb)
    if inter:
        return inter / min(len(ta), len(tb)) * (1.0 if len(ta) == len(tb) else 0.9)
    r = difflib.SequenceMatcher(None, fa.replace(" ", ""), fb.replace(" ", "")).ratio()
    return 0.7 * r if r >= 0.8 else 0.0


def person_sim(a, b):
    """0..1 for two spellings of one person: the same surname and a compatible first name, or one name inside the other.
    Teammates sharing a word («Ali Saleh», «Almoez Ali») score 0."""
    fa, fb = S365.fold(a).split(), S365.fold(b).split()
    if not fa or not fb:
        return 0.0
    if fa == fb:
        return 1.0
    if fa[-1] == fb[-1] and (len(fa) == 1 or len(fb) == 1 or fa[0][0] == fb[0][0]):
        return 0.9
    if set(fa) <= set(fb) or set(fb) <= set(fa):
        return 0.8 if min(len(fa), len(fb)) > 1 or fa[-1] == fb[-1] else 0.6
    if fa[0] == fb[0] and len(fa) > 1 and len(fb) > 1 and difflib.SequenceMatcher(None, fa[-1], fb[-1]).ratio() >= 0.8:
        return 0.8                                        # Walid Azarou / Walid Azaro
    if fa[0][0] == fb[0][0] and (fa[-1] in fb or fb[-1] in fa):
        return 0.8                                        # Nico Paz / Nicolás Paz Martínez (two surnames), Dani Olmo / Daniel Olmo Carvajal
    return 0.0


def team_score(fm_team, t365, fmmap):
    if not t365:
        return 0.0
    if fm_team.get("id") and fmmap.get(str(fm_team["id"])) == t365.get("id"):
        return 1.5
    return max(name_sim(fm_team.get("name"), t365.get("name")), name_sim(fm_team.get("name"), t365.get("longName")))


def pair_teams(ours, theirs, fmmap, floor=0.5):
    """ours {fotmob id: name}, theirs {365 id: name} -> {fotmob id: 365 id}, one to one, best first."""
    out, used = {}, set()
    for fid in ours:
        sid = fmmap.get(str(fid))
        if sid in theirs and sid not in used:
            out[fid] = sid
            used.add(sid)
    cand = sorted(((name_sim(ours[f], theirs[s]), f, s) for f in ours if f not in out for s in theirs if s not in used), reverse=True)
    for sc, f, s in cand:
        if sc < floor:
            break
        if f not in out and s not in used:
            out[f] = s
            used.add(s)
    return out


def pair_games(ms, games, fmmap, window_h=3.0):
    """FotMob matches -> 365 games, by kickoff (within window_h hours) and both teams; also the swapped orientation.
    Returns {fotmob match id: (game, swapped)}."""
    cands = []
    for m in ms:
        ko = parse_utc(m.get("kickoff_utc"))
        if not ko:
            continue
        for g in games:
            try:
                gt = datetime.fromisoformat(g["startTime"])
            except (KeyError, ValueError):
                continue
            dt = abs((gt - ko).total_seconds()) / 3600
            if dt > window_h:
                continue
            hc, ac = g.get("homeCompetitor") or {}, g.get("awayCompetitor") or {}
            for swapped, (x, y) in ((False, (hc, ac)), (True, (ac, hc))):
                a, b = team_score(m["home"], x, fmmap), team_score(m["away"], y, fmmap)
                if a >= 0.5 and b >= 0.5:
                    cands.append((a + b - (0.3 if swapped else 0) - dt / 10, m["id"], g["id"], swapped, g))
    out, used = {}, set()
    for sc, mid, gid, swapped, g in sorted(cands, key=lambda x: -x[0]):
        if mid not in out and gid not in used:
            out[mid] = (g, swapped)
            used.add(gid)
    return out


def _score365(g):
    h, a = (g.get("homeCompetitor") or {}).get("score"), (g.get("awayCompetitor") or {}).get("score")
    if h is None or a is None or h < 0 or a < 0:
        return None
    return int(h), int(a)


def _pid(p):
    """A player id, with FotMob's 0 for «no page» read as none."""
    try:
        return int((p or {}).get("id") or 0) or None
    except (TypeError, ValueError):
        return None


def season_label_calendar(label):
    """FotMob season names: «2026», «2025 Qatar» are calendar-year editions; «2026/2027», «2023/2025» span years."""
    return bool(re.match(r"^\d{4}(\s|$)", str(label or ""))) and "/" not in str(label or "")


# ------------------------------------------------------------------ the audit
class Audit:
    def __init__(self, store, days=14, sample=60, per_sec=2.0, verbose=True):
        self.store, self.pub = store, Pub(store)
        self.days, self.sample, self.verbose = days, sample, verbose
        self.http = GentleHttp(per_sec)
        self.fm = FotMob(self.http, {"teams": {}, "competitions": {}, "countries": {}})
        self.s365 = S365Client(per_sec)
        self.now = now_utc()
        self.comps = config.competitions()
        self.comp = {c["id"]: c for c in self.comps}
        self.awarded = config.awarded()
        self.findings, self.checked, self.notes = [], defaultdict(Counter), []
        self._league, self._detail, self._keys = {}, {}, {}
        self.t0 = time.time()

    # ---- bookkeeping
    def add(self, area, check, level, verdict, key, msg, url=None, **data):
        f = {"area": area, "check": check, "level": level, "verdict": verdict, "key": key, "msg": msg}
        if url:
            f["url"] = url
        f.update({k: v for k, v in data.items() if v is not None})
        self.findings.append(f)
        return f

    def count(self, area, check, n=1):
        self.checked[area][check] += n

    def log(self, msg):
        self.notes.append(msg)
        if self.verbose:
            print(f"[{time.time() - self.t0:6.0f}s] {msg}", flush=True)

    # ---- sources
    def league(self, cid):
        """FotMob's competition page now (current season), once per run."""
        if cid not in self._league:
            try:
                self._league[cid] = self.fm.league_raw(cid)
            except Exception as e:
                self._league[cid] = None
                self.add("freshness", "source_unavailable", "info", "unknown", f"fotmob:league:{cid}", f"FotMob competition {cid}: {e}")
        return self._league[cid]

    def fm_detail(self, mid):
        if mid not in self._detail:
            try:
                self._detail[mid] = self.fm.match_from_raw(self.fm.match_raw(mid))
            except Exception:
                self._detail[mid] = None
        return self._detail[mid]

    def keys(self, prefix):
        if prefix not in self._keys:
            self._keys[prefix] = self.pub.keys(prefix)
        return self._keys[prefix]

    def fmmap(self):
        return (self.pub.get("s365/fmmap.json") or {}).get("map") or {}

    def fixtures(self, cid):
        return (self.pub.get(f"comp/{cid}/fixtures.json") or {}).get("matches") or []

    def window(self):
        return self.now - timedelta(days=self.days), self.now + timedelta(hours=1)


# ------------------------------------------------------------------ freshness
def area_freshness(A):
    now = A.now
    h = A.pub.get("health.json") or {}
    age = (now - (parse_utc(h.get("generated")) or now - timedelta(days=9))).total_seconds() / 60
    A.count("freshness", "poller_alive")
    if age > 10:
        A.add("freshness", "poller_alive", "error", "stale", "health.json", f"the minute poller last wrote health.json {age:.0f} min ago")
    ha = A.pub.get("health-analytics.json") or {}
    age_a = (now - (parse_utc(ha.get("generated")) or now - timedelta(days=9))).total_seconds() / 60
    A.count("freshness", "analytics_alive")
    if age_a > 60:
        A.add("freshness", "analytics_alive", "warn", "stale", "health-analytics.json", f"the analytics function last wrote {age_a:.0f} min ago")
    for name, doc in (("health.json", h), ("health-analytics.json", ha)):
        items = doc.get("items") or {}
        for k in doc.get("failing") or []:
            it = items.get(k) or {}
            A.count("freshness", "health_items")
            A.add("freshness", "health_failing", "warn", "stale", f"{name}:{k}", f"{k}: {str(it.get('error'))[:160]} (last ok {it.get('last_ok') or 'never'})")
    live = A.pub.get("live.json") or {}
    lage = (now - (parse_utc(live.get("generated")) or now - timedelta(days=9))).total_seconds() / 60
    A.count("freshness", "live_json")
    if lage > 15:
        A.add("freshness", "live_json", "warn", "stale", "live.json", f"live.json is {lage:.0f} min old")
    # live statuses that can't be true any more (a match «live» 4 h after kickoff)
    for m in live.get("matches") or []:
        ko = parse_utc(m.get("kickoff_utc"))
        A.count("freshness", "stuck_live")
        if m.get("status") in S.LIVE_STATUSES and ko and now - ko > timedelta(hours=4):
            A.add("freshness", "stuck_live", "error", "stale", f"match:{m.get('id')}", f"live.json still shows {m['home']['name']} v {m['away']['name']} as {m['status']} {((now - ko).total_seconds() / 3600):.1f} h after kickoff", url=PAGE["match"].format(m.get("id")))
    # laptop stages (db/refresh.py state)
    st_path = os.path.join(HERE, ".cache", "refresh.json")
    if os.path.exists(st_path):
        from db import refresh as RF
        st = json.load(open(st_path, encoding="utf-8"))
        for name, mod, args, every in RF.STAGES:
            if name == "audit":
                continue
            s = st.get(name) or {}
            A.count("freshness", "db_stage")
            ok = s.get("ok_at") or 0
            if s.get("rc") not in (None, 0):
                A.add("freshness", "db_stage_failed", "warn", "stale", f"stage:{name}", f"stage {name} ({mod}) exited {s.get('rc')}: {s.get('tail')}")
            if not ok:
                A.add("freshness", "db_stage_late", "warn", "stale", f"stage:{name}", f"stage {name} never succeeded")
            elif time.time() - ok > (every + 1) * 86400:
                A.add("freshness", "db_stage_late", "warn", "stale", f"stage:{name}", f"stage {name} last succeeded {((time.time() - ok) / 86400):.1f} days ago (every {every} d)")
    # each competition: fixtures refreshed, the table newer than its last result
    for c in A.comps:
        cid = c["id"]
        fxd = A.pub.get(f"comp/{cid}/fixtures.json") or {}
        ms = fxd.get("matches") or []
        A.count("freshness", "comp_files")
        if not ms:
            A.add("freshness", "comp_fixtures_missing", "error", "gap", f"comp:{cid}", f"{c['name_ar']} ({cid}): no fixtures file")
            continue
        kos = [parse_utc(m.get("kickoff_utc")) for m in ms if m.get("kickoff_utc")]
        active = any(k and now - timedelta(days=3) <= k <= now + timedelta(days=30) for k in kos)
        gen = parse_utc(fxd.get("generated"))
        lim = timedelta(hours=4 if active else 50)
        if gen and now - gen > lim + timedelta(hours=24):     # `generated` = last content change: allow a quiet day
            A.add("freshness", "comp_fixtures_old", "info", "stale", f"comp:{cid}", f"{c['name_ar']} ({cid}): fixtures unchanged since {fxd.get('generated')}")
        if c.get("kind") != "league":
            continue
        fin = [parse_utc(m["kickoff_utc"]) for m in ms if m.get("status") == S.FINISHED and m.get("kickoff_utc")]
        st = A.pub.get(f"comp/{cid}/standings.json")
        if fin and st:
            last = max(fin)
            sg = parse_utc(st.get("generated"))
            if sg and sg < last + timedelta(minutes=100) and now - last > timedelta(hours=5):
                A.add("freshness", "table_behind_results", "error", "stale", f"comp:{cid}",
                      f"{c['name_ar']} ({cid}): the table was last updated {st.get('generated')}, before the result of {last.isoformat()[:16]}")


# ------------------------------------------------------------------ matches
def _goal_sig(evs):
    return sorted((e["type"], e.get("minute"), e.get("added") or 0, _pid(e.get("player")), _pid(e.get("assist")))
                  for e in evs or [] if e.get("type") in G)


def _card_sig(evs):
    return sorted((e["type"], e.get("minute"), e.get("added") or 0, _pid(e.get("player"))) for e in evs or [] if e.get("type") in CARDS)


def _side_goals(evs):
    h = sum(1 for e in evs or [] if e.get("type") in G and e.get("team") == "home")
    a = sum(1 for e in evs or [] if e.get("type") in G and e.get("team") == "away")
    return h, a


def score_evidence(A, mid, g, swapped):
    """Which source's final score the evidence supports: an explicit «Awarded» status, and each source's own goal events."""
    d = A.fm_detail(mid)
    j = A.s365.get(f"/web/game/?{S365.QE}&gameId={g['id']}", 7 * 86400) or {}
    gg = j.get("game") or {}
    status = (gg.get("statusText") or g.get("statusText") or "")
    fsc = (d or {}).get("score")
    f_ev = _side_goals((d or {}).get("events")) if d else None
    hid = (gg.get("homeCompetitor") or {}).get("id")
    goals365 = [e for e in gg.get("events") or [] if ((e.get("eventType") or {}).get("name") or "").lower() in ("goal", "own goal", "penalty goal")
                or (e.get("eventType") or {}).get("id") == 1]
    s_ev = (sum(1 for e in goals365 if e.get("competitorId") == hid), sum(1 for e in goals365 if e.get("competitorId") != hid))
    s_sc = _score365(gg) or _score365(g)
    if swapped and s_sc:
        s_sc, s_ev = (s_sc[1], s_sc[0]), (s_ev[1], s_ev[0])
    ev = []
    favors = "unknown"
    if "award" in status.lower() and (d or {}).get("status") != S.AWARDED:
        favors = "365"
        ev.append("365Scores marks the result «Awarded» (a decision after the match); FotMob keeps the score played on the pitch")
    f_ok = fsc is not None and f_ev == (fsc["home"], fsc["away"]) and sum(f_ev) > 0
    s_ok = s_sc is not None and s_ev == s_sc and sum(s_ev) > 0
    if f_ev is not None:
        ev.append(f"FotMob's goal events add up to {f_ev[0]}-{f_ev[1]}")
    ev.append(f"365Scores' goal events add up to {s_ev[0]}-{s_ev[1]}")
    if favors == "unknown":
        if f_ok and not s_ok:
            favors = "fotmob"
        elif s_ok and not f_ok:
            favors = "365"
    return favors, "; ".join(ev), status


def area_matches(A):
    lo, hi = A.window()
    fmmap = A.fmmap()
    ours = {}
    for c in A.comps:
        for m in A.fixtures(c["id"]):
            if m.get("id"):
                ours[m["id"]] = (c["id"], m)
    # 1. fixtures (status, score) vs FotMob's competition page now
    fm_now = {}
    for c in A.comps:
        cid = c["id"]
        raw = A.league(cid)
        if not raw:
            continue
        try:
            data = A.fm.competition_from_raw(c, raw, with_leaders=False)
        except Exception as e:
            A.add("matches", "fotmob_parse", "warn", "ours", f"comp:{cid}", f"FotMob competition {cid} did not parse: {type(e).__name__}: {e}")
            continue
        now_by = {m["id"]: m for m in data["matches"] if m.get("id")}
        fm_now.update({k: (cid, v) for k, v in now_by.items()})
        our_ids = set()
        for m in A.fixtures(cid):
            ko = parse_utc(m.get("kickoff_utc"))
            if not m.get("id") or not ko or not (lo <= ko <= hi):
                continue
            our_ids.add(m["id"])
            n = AWARDED.apply_to_match(now_by.get(m["id"]), A.awarded) if now_by.get(m["id"]) else None   # FotMob now + the decisions we apply
            A.count("matches", "fixture_vs_fotmob")
            if n is None:
                if m.get("season") == data["competition"].get("season"):
                    A.add("matches", "fixture_gone", "warn", "stale", f"match:{m['id']}", f"{m['home']['name']} v {m['away']['name']} ({cid}) is in our fixtures but no longer in FotMob's", url=PAGE["match"].format(m["id"]))
                continue
            live_now = n["status"] in S.LIVE_STATUSES or m.get("status") in S.LIVE_STATUSES
            if n["status"] != m.get("status") and not live_now:
                A.add("matches", "fixture_status", "error" if {S.FINISHED, S.AWARDED} & {n["status"], m.get("status")} else "warn", "stale", f"match:{m['id']}",
                      f"{m['home']['name']} v {m['away']['name']} ({cid}, {m.get('kickoff_utc', '')[:10]}): ours «{m.get('status')}» {m.get('score')}, FotMob now «{n['status']}» {n.get('score')}"
                      + (" (a decision listed in competitions.yaml awarded:, applied by the poller once deployed)" if m["id"] in A.awarded else ""),
                      url=PAGE["match"].format(m["id"]), ours=m.get("status"), fotmob=n["status"])
            elif n["status"] == S.FINISHED and (n.get("score") != m.get("score") or (n.get("penalties") or None) != (m.get("penalties") or None)):
                A.add("matches", "fixture_score", "error", "stale", f"match:{m['id']}",
                      f"{m['home']['name']} v {m['away']['name']} ({cid}): ours {m.get('score')} pens {m.get('penalties')}, FotMob now {n.get('score')} pens {n.get('penalties')}",
                      url=PAGE["match"].format(m["id"]), ours=m.get("score"), fotmob=n.get("score"))
        for n in now_by.values():
            ko = parse_utc(n.get("kickoff_utc"))
            if ko and lo <= ko <= A.now - timedelta(hours=3) and n["id"] not in our_ids and n["id"] not in ours:
                A.count("matches", "fixture_vs_fotmob")
                A.add("matches", "fixture_missing", "error", "gap", f"match:{n['id']}", f"{n['home']['name']} v {n['away']['name']} ({cid}, {n['kickoff_utc'][:10]}) is in FotMob's fixtures, not in ours", url=PAGE["match"].format(n["id"]))
    A.log(f"matches: fixtures checked against FotMob ({A.checked['matches']['fixture_vs_fotmob']})")

    # 1b. the day files the home page and the day pages read (yesterday and today, UAE days) vs FotMob's scoreboard now
    for off in (-1, 0):
        ymd = (A.now + timedelta(days=off)).astimezone(UAE).strftime("%Y%m%d")
        ours_day = {m["id"]: m for m in (A.pub.get(f"day/{ymd}.json") or {}).get("matches") or [] if m.get("id")}
        try:
            now_day = [m for m in A.fm.day_from_raw(A.fm.day_raw(ymd)) if m.get("comp") in A.comp]
        except Exception:
            continue
        for n in now_day:
            A.count("matches", "day_file")
            o = ours_day.get(n["id"])
            name = f"{n['home']['name']} v {n['away']['name']} ({n['comp']})"
            if o is None:
                A.add("matches", "day_file_missing", "warn", "stale", f"match:{n['id']}", f"day/{ymd}.json lacks {name}", url=PAGE["match"].format(n["id"]))
            elif n["status"] == S.FINISHED and (o.get("status") != n["status"] or o.get("score") != n.get("score")) and n["id"] not in A.awarded:
                A.add("matches", "day_file_result", "error", "stale", f"match:{n['id']}", f"day/{ymd}.json shows {name} {o.get('status')} {o.get('score')}, FotMob {n['status']} {n.get('score')}",
                      url=PAGE["match"].format(n["id"]))

    # 2. final scores vs 365Scores (every game of each UAE day in the window)
    fin = []
    for mid, (cid, m) in ours.items():
        ko = parse_utc(m.get("kickoff_utc"))
        n = AWARDED.apply_to_match((fm_now.get(mid) or (None, m))[1], A.awarded)
        if ko and lo <= ko <= A.now - timedelta(hours=2) and n.get("status") in (S.FINISHED, S.AWARDED) and n.get("score"):
            fin.append(dict(n, comp=cid))
    days, d = [], (lo - timedelta(days=1)).astimezone(UAE).date()
    while d <= A.now.astimezone(UAE).date():
        days.append(d)
        d += timedelta(days=1)
    games = []
    for d in days:
        ds = d.strftime("%d/%m/%Y")
        ttl = 3 * 3600 if (A.now.astimezone(UAE).date() - d).days <= 1 else 20 * 3600
        j = A.s365.get(f"/web/games/allscores/?{S365.QE}&sports=1&startDate={ds}&endDate={ds}&showOdds=false&onlyMajorGames=false&withTop=true", ttl) or {}
        games += j.get("games") or []
    pairs = pair_games(fin, games, fmmap)
    A.count("matches", "score_vs_365", len(fin))
    A.count("matches", "score_vs_365_paired", len(pairs))
    for m in fin:
        p = pairs.get(m["id"])
        if not p:
            continue
        g, swapped = p
        s3 = _score365(g)
        if s3 is None:
            continue
        if swapped:
            s3 = (s3[1], s3[0])
        if s3 != (m["score"]["home"], m["score"]["away"]):
            favors, evidence, status = score_evidence(A, m["id"], g, swapped)
            A.add("matches", "score_vs_365", "error" if favors == "365" else "warn", "source", f"match:{m['id']}",
                  f"{m['home']['name']} v {m['away']['name']} ({m['comp']}, {m['kickoff_utc'][:10]}): FotMob (ours) {m['score']['home']}-{m['score']['away']}, 365Scores {s3[0]}-{s3[1]} «{status}»"
                  + (" (365 lists the teams the other way round)" if swapped else ""),
                  url=PAGE["match"].format(m["id"]), favors=favors, evidence=evidence, s365_game=g.get("id"))
    A.log(f"matches: {len(pairs)}/{len(fin)} finished matches paired with 365Scores")

    # 3. a sample of match pages vs FotMob's match detail now
    fin_ids = sorted(fin, key=lambda m: (m["comp"] not in FOCUS and 5789 not in (m["home"]["id"], m["away"]["id"]), m["kickoff_utc"]), reverse=False)
    fin_ids = [m for m in fin_ids if m["comp"] in FOCUS or 5789 in (m["home"]["id"], m["away"]["id"])] + \
        sorted([m for m in fin_ids if not (m["comp"] in FOCUS or 5789 in (m["home"]["id"], m["away"]["id"]))], key=lambda m: m["kickoff_utc"], reverse=True)
    docs = A.pub.many([f"match/{m['id']}.json" for m in fin_ids[:A.sample]])
    for m in fin_ids[:A.sample]:
        mid = m["id"]
        ours_d = docs.get(f"match/{mid}.json")
        now_d = A.fm_detail(mid)
        now_d = AWARDED.apply_to_match(now_d, A.awarded) if now_d else None
        A.count("matches", "detail_vs_fotmob")
        url = PAGE["match"].format(mid)
        name = f"{m['home']['name']} v {m['away']['name']} ({m['comp']}, {m['kickoff_utc'][:10]})"
        if not ours_d or ours_d.get("minimal"):
            A.add("matches", "detail_missing", "error", "gap", f"match:{mid}", f"{name}: finished, but {'no match file' if not ours_d else 'the match file is still the pre-match stub'} (no events, no lineups on the page)", url=url)
            continue
        if not now_d:
            continue
        if ours_d.get("score") != now_d.get("score") or ours_d.get("status") != now_d.get("status"):
            A.add("matches", "detail_score", "error", "stale", f"match:{mid}", f"{name}: page {ours_d.get('status')} {ours_d.get('score')}, FotMob now {now_d.get('status')} {now_d.get('score')}", url=url)
        og, ng = _goal_sig(ours_d.get("events")), _goal_sig(now_d.get("events"))
        if og != ng:
            gone, new = [x for x in og if x not in ng], [x for x in ng if x not in og]
            A.add("matches", "detail_goals", "warn", "stale", f"match:{mid}",
                  f"{name}: goals/scorers/assists changed at the source after our last fetch: ours-only {gone[:4]}, FotMob-now-only {new[:4]} (type, minute, added, scorer id, assist id)", url=url)
        oc, nc = _card_sig(ours_d.get("events")), _card_sig(now_d.get("events"))
        if oc != nc:
            A.add("matches", "detail_cards", "warn", "stale", f"match:{mid}",
                  f"{name}: cards changed at the source: ours-only {[x for x in oc if x not in nc][:4]}, FotMob-now-only {[x for x in nc if x not in oc][:4]}", url=url)
        os_ = sum(1 for e in ours_d.get("events") or [] if e.get("type") == "sub")
        ns_ = sum(1 for e in now_d.get("events") or [] if e.get("type") == "sub")
        if os_ != ns_:
            A.add("matches", "detail_subs", "info", "stale", f"match:{mid}", f"{name}: {os_} substitutions on the page, {ns_} at FotMob now", url=url)
    A.log(f"matches: {min(len(fin_ids), A.sample)} match pages compared with FotMob's detail")

    # 4. every published match file: goal events vs the score (a merge must never add a goal), finished stubs
    mkeys = [k for k, _, _ in A.keys("match/") if k.endswith(".json")]
    docs = A.pub.many(mkeys)
    have_file = set()
    low_cov = []
    for k, d in docs.items():
        if not d:
            continue
        mid = d.get("id")
        have_file.add(mid)
        if d.get("status") not in (S.FINISHED,) or not d.get("score") or d.get("minimal"):
            continue
        A.count("matches", "file_goals_vs_score")
        h, a = _side_goals(d.get("events"))
        sc = d["score"]
        name = f"{d['home']['name']} v {d['away']['name']} ({d.get('comp')}, {str(d.get('kickoff_utc'))[:10]})"
        if h > sc["home"] or a > sc["away"]:
            A.add("matches", "file_goals_exceed_score", "error", "ours", f"match:{mid}", f"{name}: {h}-{a} goal events on the page for a {sc['home']}-{sc['away']} score (duplicated goal)", url=PAGE["match"].format(mid))
        elif (h, a) != (sc["home"], sc["away"]):
            low_cov.append((mid, d.get("comp"), d.get("coverage"), name, (h, a), sc))
    A.count("matches", "low_coverage_scorers", len(low_cov))
    by_cov = Counter(x[2] or "none" for x in low_cov)
    for mid, cid, cov, name, ev, sc in low_cov:
        if cov not in ("lower", None):
            A.add("matches", "file_goals_missing", "warn", "stale", f"match:{mid}", f"{name}: the page names {ev[0]}+{ev[1]} scorers for a {sc['home']}-{sc['away']} score (coverage {cov})", url=PAGE["match"].format(mid))
    if low_cov:
        A.add("gaps", "scorers_missing", "info", "gap", "matches:low-coverage",
              f"{len(low_cov)} finished match pages name fewer scorers than goals ({dict(by_cov)}): FotMob gives these matches a score only; 365Scores often has the scorers",
              examples=[x[0] for x in low_cov[:20]])
    # 5. finished matches of the current seasons with no match page at all
    per = Counter()
    ex = defaultdict(list)
    for mid, (cid, m) in ours.items():
        if m.get("status") == S.FINISHED and mid not in have_file:
            per[cid] += 1
            ex[cid].append(mid)
    A.count("matches", "finished_without_page", sum(1 for _, (c_, m) in ours.items() if m.get("status") == S.FINISHED))
    for cid, n in per.most_common():
        A.add("matches", "finished_without_page", "warn", "gap", f"comp:{cid}", f"{A.comp[cid]['name_ar']} ({cid}): {n} finished matches have no match file (no events or lineups on their pages)", examples=ex[cid][:10])
    # 6. matchx (player logs are built from them): finished over 36 h ago and still missing
    mx = {int(k[len("matchx/"):-5]) for k, _, _ in A.keys("matchx/") if k.endswith(".json") and k[len("matchx/"):-5].isdigit()}
    per = Counter()
    for mid, (cid, m) in ours.items():
        ko = parse_utc(m.get("kickoff_utc"))
        if m.get("status") == S.FINISHED and ko and A.now - ko > timedelta(hours=36):
            A.count("matches", "matchx_present")
            if mid not in mx:
                per[cid] += 1
    for cid, n in per.most_common():
        A.add("matches", "matchx_missing", "warn", "gap", f"comp:{cid}", f"{A.comp[cid]['name_ar']} ({cid}): {n} finished matches (older than 36 h) have no matchx record, so no player's match log counts them")
    A.log("matches: files scanned")


# ------------------------------------------------------------------ standings
def _row_tuple(r):
    return (r.get("played"), r.get("won"), r.get("drawn"), r.get("lost"), r.get("gf"), r.get("ga"), r.get("pts"))


def table_from_results(results):
    """[(home id, away id, hs, as)] -> {team: [P, W, D, L, GF, GA, Pts]}"""
    T = defaultdict(lambda: [0, 0, 0, 0, 0, 0, 0])
    for h, a, hs, as_ in results:
        for t, f, g in ((h, hs, as_), (a, as_, hs)):
            r = T[t]
            r[0] += 1
            r[4] += f
            r[5] += g
            if f > g:
                r[1] += 1
                r[6] += 3
            elif f == g:
                r[2] += 1
                r[6] += 1
            else:
                r[3] += 1
    return T


def s365_results(A, sid, pages=12):
    out, j, n = [], A.s365.get(f"/web/games/results/?{S365.QE}&competitions={sid}", 6 * 3600), 0
    while j and n < pages:
        out += j.get("games") or []
        nxt = (j.get("paging") or {}).get("previousPage")
        n += 1
        if not nxt or not j.get("games"):
            break
        j = A.s365.get(nxt, 6 * 3600)
    return out


def area_standings(A):
    fmmap = A.fmmap()
    for c in A.comps:
        cid = c["id"]
        st = A.pub.get(f"comp/{cid}/standings.json")
        if not st:
            continue
        A.count("standings", "tables")
        league = c.get("kind") == "league" and not st.get("composite")
        # 1. internal
        for g in st.get("groups") or []:
            rows = g.get("rows") or []
            gname = g.get("name") or ""
            ranks = [r.get("rank") for r in rows]
            if sorted(x for x in ranks if isinstance(x, int)) != list(range(1, len(rows) + 1)):
                A.add("standings", "ranks", "warn", "ours", f"comp:{cid}", f"{c['name_ar']} ({cid}) {gname}: ranks {ranks}")
            sw = sl = sgf = sga = 0
            for r in rows:
                A.count("standings", "rows")
                P, W, D, L, gf, ga, pts = _row_tuple(r)
                gd, ded = r.get("gd"), r.get("deduction") or 0
                tn = r["team"]["name"]
                if None in (P, W, D, L):
                    A.add("standings", "row_incomplete", "warn", "gap", f"comp:{cid}", f"{c['name_ar']} ({cid}) {gname} {tn}: played/won/drawn/lost missing")
                    continue
                if P != W + D + L:
                    A.add("standings", "row_pwdl", "error", "ours", f"comp:{cid}", f"{c['name_ar']} ({cid}) {gname} {tn}: played {P} but W+D+L = {W + D + L}")
                if pts is not None and cid not in NONSTD_POINTS and pts not in (3 * W + D + ded, 3 * W + D - ded):
                    A.add("standings", "row_points", "error", "ours", f"comp:{cid}", f"{c['name_ar']} ({cid}) {gname} {tn}: {pts} points but 3W+D = {3 * W + D} (deduction {ded})")
                if gf is not None and ga is not None and gd is not None and gd != gf - ga:
                    A.add("standings", "row_gd", "error", "ours", f"comp:{cid}", f"{c['name_ar']} ({cid}) {gname} {tn}: goal difference {gd} but {gf}-{ga}")
                sw, sl, sgf, sga = sw + W, sl + L, sgf + (gf or 0), sga + (ga or 0)
            if league and (sw != sl or sgf != sga):
                A.add("standings", "table_sums", "error", "ours", f"comp:{cid}", f"{c['name_ar']} ({cid}): wins {sw} vs losses {sl}, goals for {sgf} vs against {sga}")
        # 2. the table vs our own finished results (plain leagues)
        if league:
            season = st.get("season")
            res = [(m["home"]["id"], m["away"]["id"], m["score"]["home"], m["score"]["away"]) for m in A.fixtures(cid)
                   if m.get("status") in (S.FINISHED, S.AWARDED) and m.get("score") and m.get("season", season) == season]
            T = table_from_results(res)
            for r in st["groups"][0]["rows"]:
                A.count("standings", "table_vs_results")
                mine = T.get(r["team"]["id"]) or [0] * 7
                ours = _row_tuple(r)
                ded = r.get("deduction") or 0
                if not ours[0] and not mine[0]:
                    continue
                if list(ours[:6]) != mine[:6] or ours[6] not in (mine[6] + ded, mine[6] - ded):
                    A.add("standings", "table_vs_results", "error", "ours", f"comp:{cid}",
                          f"{c['name_ar']} ({cid}) {r['team']['name']}: table P{ours[0]} W{ours[1]} D{ours[2]} L{ours[3]} {ours[4]}-{ours[5]} {ours[6]} pts, "
                          f"our published results give P{mine[0]} W{mine[1]} D{mine[2]} L{mine[3]} {mine[4]}-{mine[5]} {mine[6]} pts")
        # 3. vs FotMob now
        raw = A.league(cid)
        now_st = None
        if raw:
            try:
                now_st = A.fm.standings_from_raw(cid, (raw.get("details") or {}).get("selectedSeason"), raw)
                if now_st and A.awarded:     # FotMob's table + the decisions we apply (compute/awarded.py)
                    AWARDED.apply_to_standings(now_st, A.fm.competition_from_raw(c, raw, with_leaders=False)["matches"], A.awarded)
            except Exception:
                now_st = None
        if now_st:
            live_teams = set()
            for m in A.fixtures(cid):
                ko = parse_utc(m.get("kickoff_utc"))
                if ko and A.now - timedelta(hours=3) <= ko <= A.now:     # playing now or just finished: the poller catches up within the hour
                    live_teams |= {m["home"]["id"], m["away"]["id"]}
            nowrows = {((g.get("name") or ""), r["team"]["id"]): r for g in now_st["groups"] for r in g["rows"]}
            n_diff, ex = 0, []
            for g in st["groups"]:
                for r in g["rows"]:
                    n = nowrows.get(((g.get("name") or ""), r["team"]["id"]))
                    if not n or r["team"]["id"] in live_teams or n.get("live"):
                        continue
                    A.count("standings", "table_vs_fotmob")
                    if _row_tuple(n) != _row_tuple(r):
                        n_diff += 1
                        ex.append(f"{r['team']['name']} ours {_row_tuple(r)} FotMob {_row_tuple(n)}")
            if n_diff:
                A.add("standings", "table_vs_fotmob", "error", "stale", f"comp:{cid}", f"{c['name_ar']} ({cid}): {n_diff} rows differ from FotMob's table now (our copy {st.get('generated')}): " + "; ".join(ex[:3]))
        # 4. vs 365Scores
        sid = S365.SITE_COMPS.get(cid)
        if not sid:
            continue
        j = A.s365.get(f"/web/standings/?{S365.QE}&competitions={sid}", 3 * 3600) or {}
        rows365 = {}
        for s_ in j.get("standings") or []:
            for r in s_.get("rows") or []:
                t = r.get("competitor") or {}
                if t.get("id"):
                    rows365.setdefault(t["id"], []).append(r)
        if not rows365:
            continue
        ours_names = {r["team"]["id"]: r["team"]["name"] for g in st["groups"] for r in g["rows"] if r["team"]["id"]}
        theirs = {sid_: rs[0]["competitor"].get("name") for sid_, rs in rows365.items()}
        tmap = pair_teams(ours_names, theirs, fmmap)
        A.count("standings", "vs_365_teams", len(ours_names))
        A.count("standings", "vs_365_paired", len(tmap))
        diffs = []
        for g in st["groups"]:
            for r in g["rows"]:
                s_ = tmap.get(r["team"]["id"])
                if not s_:
                    continue
                cands = rows365.get(s_) or []
                x = min(cands, key=lambda x: abs((x.get("gamePlayed") or 0) - (r.get("played") or 0)))
                theirs_t = tuple(int(x.get(k)) if isinstance(x.get(k), (int, float)) else x.get(k) for k in ("gamePlayed", "gamesWon", "gamesEven", "gamesLost", "for", "against", "points"))
                if theirs_t[0] != r.get("played") and not league:
                    A.count("standings", "vs_365_other_stage")
                    continue
                A.count("standings", "vs_365_rows")
                if theirs_t != _row_tuple(r):
                    diffs.append((r, g, s_, theirs_t, x))
        if diffs:
            res365 = None
            for r, g, s_, theirs_t, x in diffs:
                # evidence: 365's own results for the team this season (365's results pages are not split by season:
                # keep the games since our season's first fixture)
                if res365 is None:
                    season_start = min((parse_utc(m["kickoff_utc"]) for m in A.fixtures(cid) if m.get("kickoff_utc")), default=None)
                    res365 = [gm for gm in s365_results(A, sid) if season_start is None or datetime.fromisoformat(gm["startTime"]) >= season_start - timedelta(days=2)]
                own = table_from_results([((gm.get("homeCompetitor") or {}).get("id"), (gm.get("awayCompetitor") or {}).get("id"), *_score365(gm))
                                          for gm in res365 if gm.get("statusGroup") == 4 and _score365(gm)]).get(s_)
                ours_t = _row_tuple(r)
                favors, evidence = "unknown", []
                if own and tuple(own) == ours_t:
                    favors = "fotmob"
                    evidence.append("365Scores' own results add up to our row: its table is out of step with its results")
                else:
                    if own and tuple(own) == theirs_t:
                        evidence.append("365Scores' table agrees with its own results: a match result differs between the sources")
                    elif own:
                        evidence.append(f"365Scores' own results give P{own[0]} W{own[1]} D{own[2]} L{own[3]} {own[4]}-{own[5]}, neither its table nor ours")
                    # the match(es) whose result differs
                    team_games = [gm for gm in res365 if s_ in ((gm.get("homeCompetitor") or {}).get("id"), (gm.get("awayCompetitor") or {}).get("id")) and gm.get("statusGroup") == 4]
                    my = [dict(m, comp=cid) for m in A.fixtures(cid) if r["team"]["id"] in (m["home"]["id"], m["away"]["id"]) and m.get("status") == S.FINISHED and m.get("score")]
                    pr = pair_games(my, team_games, fmmap, window_h=30)
                    favs = []
                    for m in my:
                        p = pr.get(m["id"])
                        if not p:
                            continue
                        s3 = _score365(p[0])
                        if s3 and p[1]:
                            s3 = (s3[1], s3[0])
                        if s3 and s3 != (m["score"]["home"], m["score"]["away"]):
                            fav, evd, stt = score_evidence(A, m["id"], p[0], p[1])
                            favs.append(fav)
                            evidence.append(f"{m['home']['name']} v {m['away']['name']} {m['kickoff_utc'][:10]}: FotMob {m['score']['home']}-{m['score']['away']}, 365Scores {s3[0]}-{s3[1]} «{stt}» ({evd})")
                    if favs and len(set(favs)) == 1:
                        favors = favs[0]
                    elif not favs and theirs_t[:4] == ours_t[:4]:
                        favors = "fotmob"
                        evidence.append("every result agrees; only 365Scores' goal totals differ")
                A.add("standings", "table_vs_365", "warn", "source", f"comp:{cid}",
                      f"{c['name_ar']} ({cid}) {g.get('name') or ''} {r['team']['name']}: ours P{ours_t[0]} W{ours_t[1]} D{ours_t[2]} L{ours_t[3]} {ours_t[4]}-{ours_t[5]} {ours_t[6]} pts; 365Scores P{theirs_t[0]} W{theirs_t[1]} D{theirs_t[2]} L{theirs_t[3]} {theirs_t[4]}-{theirs_t[5]} {theirs_t[6]} pts",
                      url=f"/c/{c.get('key')}/", favors=favors, evidence="; ".join(evidence) or None)
    A.log(f"standings: {A.checked['standings']['tables']} tables, {A.checked['standings']['vs_365_rows']} rows compared with 365Scores")


# ------------------------------------------------------------------ scorers
def scorers_vs_365(A, c, sid, cat, ours, comp_names, names365, fmmap):
    """365Scores' top scorers vs our leaderboard (same player: same team, name alike); on a difference, the match where
    FotMob's goal events and 365Scores' credit the player differently."""
    cid = c["id"]
    for g in (A.s365.get(f"/web/games/results/?{S365.QE}&competitions={sid}", 6 * 3600) or {}).get("games") or []:
        for side in ("homeCompetitor", "awayCompetitor"):
            t = g.get(side) or {}
            names365.setdefault(t.get("id"), t.get("name"))
    tmap = {v: k for k, v in pair_teams({k: v for k, v in comp_names.items() if k}, {k: v for k, v in names365.items() if k}, fmmap).items()}
    top = {}
    for r in (cat.get("rows") or [])[:15]:
        e = r.get("entity") or {}
        try:
            v = float(((r.get("stats") or [{}])[0]).get("value"))
        except (TypeError, ValueError):
            continue
        top[(e.get("name"), tmap.get(e.get("competitorId")))] = v
    A.count("scorers", "vs_365", len(top))
    for (nm, tid), v in top.items():
        if tid is None:
            continue
        best = None
        for pid, e in ours.items():
            if (e.get("team") or {}).get("id") != tid:
                continue
            sc = person_sim(nm, e["player"]["name"])
            if sc >= 0.6 and (best is None or sc > best[0]):
                best = (sc, pid, e)
        if not best or float(best[2].get("value") or 0) == v:
            continue
        pid, e = best[1], best[2]
        # evidence: his team's finished matches, his goals in our match page (FotMob) and in 365Scores' game
        ms = [dict(m, comp=cid) for m in A.fixtures(cid) if m.get("status") == S.FINISHED and tid in (m["home"]["id"], m["away"]["id"])]
        docs = A.pub.many([f"match/{m['id']}.json" for m in ms])
        res = [g for g in s365_results(A, sid, pages=4) if g.get("statusGroup") == 4]
        pr = pair_games(ms, res, fmmap, window_h=30)
        ev = []
        for m in ms:
            d = docs.get(f"match/{m['id']}.json") or {}
            n_fm = sum(1 for x in d.get("events") or [] if x.get("type") in ("goal", "penalty_goal") and _pid(x.get("player")) == pid)
            p = pr.get(m["id"])
            if not p:
                continue
            gg = (A.s365.get(f"/web/game/?{S365.QE}&gameId={p[0]['id']}", 7 * 86400) or {}).get("game") or {}
            mem = {x.get("id"): x for x in gg.get("members") or []}
            n_365 = sum(1 for x in gg.get("events") or [] if (x.get("eventType") or {}).get("id") == 1
                        and "own" not in str((x.get("eventType") or {}).get("subTypeName") or "").lower()
                        and person_sim((mem.get(x.get("playerId")) or {}).get("name"), nm) >= 0.6)
            if n_fm != n_365:
                ev.append(f"{m['home']['name']} v {m['away']['name']} {m['kickoff_utc'][:10]}: FotMob credits him {n_fm}, 365Scores {n_365}")
        A.add("scorers", "vs_365", "warn", "source", f"player:{pid}", f"{c['name_ar']} ({cid}) {e['player']['name']}: {e.get('value')} goals on our leaderboard (FotMob), {v:g} at 365Scores",
              url=PAGE["player"].format(pid), favors="unknown", evidence="; ".join(ev) or "no single match differs in the paired games (the lists count different matches)")


def area_scorers(A):
    fmmap = A.fmmap()
    for c in A.comps:
        cid = c["id"]
        st = A.pub.get(f"comp/{cid}/stats.json")
        goals = ((st or {}).get("lists") or {}).get("goals") or []
        if not goals:
            continue
        A.count("scorers", "lists")
        ours = {(e.get("player") or {}).get("id"): e for e in goals if (e.get("player") or {}).get("id")}
        # 1. vs FotMob now (the full list behind the competition page)
        raw = A.league(cid)
        if raw and (raw.get("details") or {}).get("selectedSeason") == st.get("season"):
            p = next((x for x in (raw.get("stats") or {}).get("players") or [] if x.get("name") == "goals"), None)
            now_list = None
            if p and p.get("fetchAllUrl"):
                try:
                    full = A.http.get_json(p["fetchAllUrl"], min_ttl=3600)
                    now_list = {e.get("ParticiantId") or e.get("ParticipantId"): e.get("StatValue") for tl in (full.get("TopLists") or [])[:1] for e in tl.get("StatList") or []}
                except Exception:
                    now_list = None
            if now_list:
                diff = [(pid, e["player"]["name"], e.get("value"), now_list.get(pid)) for pid, e in list(ours.items())[:20]
                        if now_list.get(pid) is not None and float(now_list.get(pid)) != float(e.get("value") or 0)]
                A.count("scorers", "vs_fotmob", min(20, len(ours)))
                if diff:
                    A.add("scorers", "vs_fotmob", "warn", "stale", f"comp:{cid}", f"{c['name_ar']} ({cid}): {len(diff)} of our top scorers' goals differ from FotMob now (ours {st.get('generated')}): " +
                          "; ".join(f"{n} {a}→{b}" for _, n, a, b in diff[:5]))
        # 2. vs 365Scores
        sid = S365.SITE_COMPS.get(cid)
        if sid:
            j = A.s365.get(f"/web/stats/?{S365.QE}&competitions={sid}", 6 * 3600) or {}
            cats = (j.get("stats") or {}).get("athletesStats") or []
            cat = next((x for x in cats if (x.get("name") or "").lower() == "goals"), None)
            if cat:
                comp_names = {}
                for m in A.fixtures(cid):
                    for side in ("home", "away"):
                        comp_names[m[side]["id"]] = m[side]["name"]
                std = A.s365.get(f"/web/standings/?{S365.QE}&competitions={sid}", 3 * 3600) or {}
                names365, p365 = {}, 0
                for s_ in std.get("standings") or []:
                    for r in s_.get("rows") or []:
                        t = r.get("competitor") or {}
                        names365[t.get("id")] = t.get("name")
                        p365 = max(p365, r.get("gamePlayed") or 0)
                ours_st = A.pub.get(f"comp/{cid}/standings.json") or {}
                p_ours = max((r.get("played") or 0 for g in ours_st.get("groups") or [] for r in g.get("rows") or []), default=0)
                if p365 and p_ours and p_ours - p365 > 2:
                    # 365's current stage is another table (Argentina's Clausura against FotMob's whole season): its scorers too
                    A.count("scorers", "vs_365_other_stage")
                else:
                    scorers_vs_365(A, c, sid, cat, ours, comp_names, names365, fmmap)
        # 3. the top scorers' match logs (player page «أرقامه موسم بموسم», db/matches.py)
        calendar = season_label_calendar(st.get("season"))
        want = str(st.get("season") or "")[:4] if calendar else st.get("season")     # «2025 Qatar» -> «2025»
        logs = A.pub.many([f"player/{pid}/log.json" for pid in list(ours)[:5]])
        for pid in list(ours)[:5]:
            e = ours[pid]
            A.count("scorers", "log_vs_leaders")
            lg = logs.get(f"player/{pid}/log.json")
            if not lg:
                A.add("scorers", "log_missing", "warn", "gap", f"player:{pid}", f"{e['player']['name']} ({c['name_ar']} top scorer): no match log, the player page shows no season table", url=PAGE["player"].format(pid))
                continue
            rows = [s for s in lg.get("seasons") or [] if s.get("comp") == cid]
            labels = {s.get("season") for s in rows}
            y = int(want[:4]) if calendar and str(want or "")[:4].isdigit() else None
            cut = {f"{y - 1}/{y}", f"{y}/{y + 1}"} & labels if y else set()      # the current calendar season under a July cut
            if cut:
                A.add("scorers", "log_season_label", "error", "ours", f"player:{pid}", f"{e['player']['name']}: {c['name_ar']} {want} is one calendar-year season but the log labels it {sorted(cut)} (a July cut splits it in two)", url=PAGE["player"].format(pid))
            row = next((s for s in rows if s.get("season") == want), None)
            if row is not None and e.get("value") is not None and row.get("g") != e.get("value") and A.now - (parse_utc(st.get("generated")) or A.now) < timedelta(days=3):
                A.add("scorers", "log_vs_leaders", "warn", "stale", f"player:{pid}", f"{e['player']['name']}: {e.get('value')} goals in {c['name_ar']} {want} on the leaderboard, {row.get('g')} in his match log", url=PAGE["player"].format(pid))
    A.log(f"scorers: {A.checked['scorers']['lists']} leaderboards")


# ------------------------------------------------------------------ derived numbers
def _archive(A, last=None):
    """Our archive of finished results [(id, date, comp, home, away, hs, as)], every season or the last `last`."""
    seasons = [s["file"] for s in (A.pub.get("archive/index-all.json") or {}).get("seasons") or [] if s.get("file")]
    rows = []
    for f, d in A.pub.many(seasons[-last:] if last else seasons).items():
        rows += [r for r in (d or {}).get("matches") or [] if r[5] is not None]
    return rows


def area_derived(A):
    # 1. head-to-head files (all of them, and the derbies'): wins = the listed results, the index count, no meeting twice,
    #    every finished meeting of this season and last in the list
    idx = A.pub.get("h2h/index.json") or {}
    der = A.pub.get("derbies.json") or {}
    keys = sorted(set(idx.get("pairs") or {}) | {str(d["h2h"])[4:-5] for d in der.get("derbies") or [] if str(d.get("h2h") or "").startswith("h2h/")})
    docs = A.pub.many([f"h2h/{k}.json" for k in keys])
    fin = defaultdict(list)
    for r in _archive(A, 2):
        fin[tuple(sorted((r[3], r[4])))].append(r)
    bad = defaultdict(list)
    for k in keys:
        h = docs.get(f"h2h/{k}.json")
        if not h:
            bad["h2h_file_missing"].append(k)
            continue
        A.count("derived", "h2h")
        ms = [m for m in h.get("matches") or [] if m.get("score")]
        w = Counter(str(m["home"]["id"] if m["score"]["home"] > m["score"]["away"] else m["away"]["id"] if m["score"]["home"] < m["score"]["away"] else "draws") for m in ms)
        wins = {str(a): b for a, b in (h.get("wins") or {}).items() if b}
        if wins and dict(w) != wins:
            bad["h2h_wins"].append(f"{k}: wins {wins}, the list gives {dict(w)}")
        ids = [m.get("id") for m in ms]
        days = Counter(str(m.get("kickoff_utc"))[:10] for m in ms)
        if len(set(ids)) != len(ids) or any(n > 1 for n in days.values()):
            bad["h2h_duplicates"].append(k)
        if k in (idx.get("pairs") or {}) and idx["pairs"][k] != len(ms):
            bad["h2h_index_count"].append(f"{k}: index {idx['pairs'][k]}, file {len(ms)}")
        if any(str(m.get("kickoff_utc")) > str(h.get("generated")) for m in ms):
            bad["h2h_future_in_results"].append(k)
        a, b = (h.get("teams") or [None, None])[:2]
        miss = [r[0] for r in fin.get(tuple(sorted((a, b))), []) if r[0] not in set(ids) and r[1] < str(h.get("generated"))[:10]]
        if miss:
            bad["h2h_missing_meetings"].append(f"{k}: {len(miss)} ({', '.join(map(str, miss[:3]))})")
    labels = {"h2h_wins": ("error", "head-to-head wins don't add up to the listed results"), "h2h_duplicates": ("error", "a meeting listed twice"),
              "h2h_index_count": ("warn", "h2h/index.json counts differ from the files"), "h2h_future_in_results": ("warn", "a future fixture sits among the results"),
              "h2h_missing_meetings": ("error", "finished meetings of this season or last (our archive) are missing"), "h2h_file_missing": ("warn", "listed but no file")}
    for chk, items in bad.items():
        lv, txt = labels[chk]
        A.add("derived", chk, lv, "stale" if chk in ("h2h_missing_meetings", "h2h_index_count") else "ours", f"h2h:{chk}", f"{len(items)} of {len(keys)} head-to-head files: {txt}: " + "; ".join(map(str, items[:8])),
              examples=[str(x).split(":")[0] for x in items[:40]])
    # 2. club histories (every club with one): the totals add up, and the match list is clean and complete: no match twice
    #    (the dataset repeats 2025-06-06..09-15), no two matches on one date, no club against itself, no nameless opponent,
    #    every match of our own archive in it (±1 day), one league position per season, no national team
    hidx = (A.pub.get("history/index.json") or {}).get("clubs") or {}
    nat = national_ids(A)
    ids = sorted(hidx)
    docs = A.pub.many([f"history/club/{i}.json" for i in ids] + [f"history/club/{i}/matches.json" for i in ids])
    arch = defaultdict(list)
    for r in _archive(A):
        arch[r[3]].append(r)
        arch[r[4]].append(r)
    bad = defaultdict(list)
    for i in ids:
        h, mf = docs.get(f"history/club/{i}.json"), docs.get(f"history/club/{i}/matches.json")
        if not h:
            continue
        A.count("derived", "club_history")
        tot = h.get("total") or {}
        if tot and tot.get("p") != tot.get("w", 0) + tot.get("d", 0) + tot.get("l", 0):
            bad["history_totals"].append(f"{i} played {tot.get('p')} but W+D+L {tot.get('w', 0) + tot.get('d', 0) + tot.get('l', 0)}")
        for part in ("by_comp", "by_decade"):
            parts = h.get(part) or {}
            if parts and tot:
                s = {k: sum((v or {}).get(k, 0) for v in parts.values()) for k in ("p", "w", "d", "l", "gf", "ga")}
                if s != {k: tot.get(k) for k in s}:
                    bad["history_totals"].append(f"{i} {part} sums differ from the total")
        if str(i) in nat:
            bad["history_national_team"].append(str(i))
        ms = (mf or {}).get("matches") or []
        c2 = Counter((m[0], str(m[1])) for m in ms)
        n2 = sum(n - 1 for n in c2.values() if n > 1)
        if n2:
            bad["history_duplicate_rows"].append(f"{i} ({h.get('name')}): {n2}")
        if any(str(m[1]) == str(i) for m in ms):
            bad["history_self_match"].append(f"{i} ({h.get('name')})")
        names = h.get("names") or {}
        if any(not str(v).strip() or re.fullmatch(r"s?:?\d*", str(v)) for v in names.values()):
            bad["history_blank_opponent"].append(f"{i} ({h.get('name')})")
        have = defaultdict(list)
        for m in ms:
            try:
                have[datetime.fromisoformat(m[0]).toordinal()].append(m)
            except (TypeError, ValueError):
                pass
        miss = 0
        for r in arch.get(int(i), []):
            home = r[3] == int(i)
            gf, ga, opp = (r[5], r[6], r[4]) if home else (r[6], r[5], r[3])
            try:
                d0 = datetime.fromisoformat(r[1]).toordinal()
            except (TypeError, ValueError):
                continue
            if not any(str(x[1]) == str(opp) or (x[3], x[4]) == (gf, ga) for dd in (-1, 0, 1) for x in have.get(d0 + dd, [])):
                miss += 1
        A.count("derived", "history_archive_rows", len(arch.get(int(i), [])))
        if miss:
            bad["history_archive_missing"].append((miss, f"{i} ({h.get('name')}): {miss}"))
        pos = Counter(p[0] for p in h.get("positions") or [])
        if any(n > 1 for n in pos.values()):
            bad["history_two_positions"].append(f"{i} ({h.get('name')})")
    labels = {"history_totals": ("error", "totals don't add up"), "history_national_team": ("error", "a national team has a club history"),
              "history_duplicate_rows": ("error", "the same match (date + opponent) listed twice"), "history_self_match": ("error", "a club plays itself"),
              "history_blank_opponent": ("warn", "an opponent without a name"), "history_archive_missing": ("error", "matches of our own archive missing"),
              "history_two_positions": ("error", "two league positions in one season (two clubs merged)")}
    for chk, items in bad.items():
        if chk == "history_archive_missing":
            items = [x[1] for x in sorted(items, reverse=True)]
        lv, txt = labels[chk]
        A.add("derived", chk, lv, "ours", f"history:{chk}", f"{len(items)} of {len(ids)} club histories: {txt}: " + "; ".join(items[:8]), examples=[str(x).split(" ")[0] for x in items[:40]])


# ------------------------------------------------------------------ champions
JUNK = re.compile(r"^\W*\d+\W*$|^(tbd|tba|n/?a|none|nan|-|—)$|no (champion|winner)|not (held|awarded|played|completed|finished)|cancel|abandon|void|"
                  r"league \d{4}|\(.*(winner|runner|cup|league|champion).*\)|لا فائز|بدون فائز|ألغي", re.I)
SPLIT_YEARS = {112, 268, 55, 44, 130, 329}  # genuinely two champions in one year: Argentina's Apertura/Clausura, Brazil's old splits, Serie A 1922, Copa 1959, MLS, the Gulf Cup's two 2004 editions


def y365(t):
    """365's season title -> the year our lists use (a season 1973-74 counts for 1974)."""
    m = re.search(r"(\d{4})\s*[/\-–]\s*(\d{2,4})", str(t))
    if m:
        a, b = m.group(1), m.group(2)
        if len(b) == 4:
            return b
        y = int(a[:2] + b)
        return str(y + 100 if y < int(a) else y)
    m = re.search(r"\d{4}", str(t))
    return m.group(0) if m else None


def national_ids(A):
    """Team ids that are national teams (teams.json's country.national, or a team of a national-team competition)."""
    nat_comps = {c["id"] for c in A.comps if c.get("scope") == "national"} | {77, 329, 10242, 11156}
    teams = (A.pub.get("teams.json") or {}).get("teams") or {}
    return {k for k, t in teams.items() if (t.get("country") or {}).get("national") or t.get("national") or any(c in nat_comps for c in t.get("comps") or [])}


def area_champions(A):
    nat = national_ids(A)
    nat_comps = {c["id"] for c in A.comps if c.get("scope") == "national"} | {77, 329, 10242, 11156}
    fm = A.pub.get("s365/fm.json") or {}
    for c in A.comps:
        cid = c["id"]
        url = f"/c/{c.get('key')}/"
        d = A.pub.get(f"history/champions/{cid}.json")
        A.count("champions", "lists")
        if not d:
            A.add("gaps", "champions_missing", "info", "gap", f"comp:{cid}", f"{c['name_ar']} ({cid}): no champions list")
            continue
        rows = d.get("champions") or []
        years = Counter(str(r[0]) for r in rows)
        for y, n in years.items():
            if n > 1 and cid not in SPLIT_YEARS:
                A.add("champions", "duplicate_season", "error", "ours", f"comp:{cid}", f"{c['name_ar']} ({cid}): season {y} listed {n} times: " +
                      ", ".join(str(r[2]) for r in rows if str(r[0]) == y), url=url)
        for r in rows:
            A.count("champions", "winners")
            nm = r[2] if len(r) > 2 else None
            if nm is None or JUNK.search(str(nm)) or NOWIN.search(str(nm)):
                A.add("champions", "junk_winner", "error", "ours", f"comp:{cid}", f"{c['name_ar']} ({cid}) {r[0]}: winner «{nm}»", url=url)
            if len(r) > 3 and r[3] and str(r[3]) in nat and cid not in nat_comps:
                A.add("champions", "title_on_national_team", "error", "ours", f"comp:{cid}", f"{c['name_ar']} ({cid}) {r[0]}: a club title credited to national team {r[3]} ({nm})", url=url)
        # our list vs 365Scores' (when both exist): the same years, the same winners, no year offset
        x = (fm.get("comps") or {}).get(str(cid))
        if not x:
            continue
        ours = defaultdict(set)
        for r in rows:
            if len(r) > 3 and r[3]:
                ours[str(r[0])].add(r[3])
        th, void = defaultdict(set), set()
        for r in x.get("champions") or []:
            y = y365(r[0])
            if not r[1]:
                void.add(y)
            elif len(r) > 2 and r[2]:
                th[y].add(r[2])
        agree = lambda off: sum(1 for y, s in ours.items() if th.get(str(int(y) + off)) and s & th[str(int(y) + off)])
        a0, am, ap = agree(0), agree(-1), agree(1)
        both = [y for y in ours if th.get(y)]
        dis = [y for y in both if not (ours[y] & th[y])]
        A.count("champions", "vs_365_seasons", len(both))
        if max(am, ap) >= 3 and max(am, ap) > a0:
            A.add("champions", "year_offset", "error", "ours", f"comp:{cid}", f"{c['name_ar']} ({cid}): our years look shifted against 365Scores' (agree at 0: {a0}, at -1: {am}, at +1: {ap})", url=url)
        if dis:
            A.add("champions", "winner_vs_365", "warn", "source", f"comp:{cid}", f"{c['name_ar']} ({cid}): {len(dis)} of {len(both)} seasons name another champion than 365Scores: " +
                  ", ".join(sorted(dis)[:8]), url=url, favors="365" if len(dis) * 4 < len(both) else "unknown",
                  evidence="365Scores checked against RSSSF for the 9 Arab leagues: right in every season but one swapped pair (audit 2026-09-30)")
        for y in sorted(void):
            if y in years:
                A.add("champions", "champion_in_void_season", "error", "ours", f"comp:{cid}", f"{c['name_ar']} ({cid}) {y}: 365Scores has no winner that season (cancelled/void/revoked), our list names " +
                      ", ".join(str(r[2]) for r in rows if str(r[0]) == y), url=url)
    # 365Scores' lists: placeholder «winners» must have been dropped by db/scores365.py
    for fid, cc in (fm.get("comps") or {}).items():
        for r in cc.get("champions") or []:
            A.count("champions", "s365_winners")
            if r[1] and NOWIN.search(str(r[1])):
                A.add("champions", "placeholder_winner_365", "error", "ours", f"comp:{fid}", f"365Scores list for {fid} {r[0]}: winner «{r[1]}»")
    idx = A.pub.get("s365/index.json") or {}
    for t in idx.get("teams") or []:
        A.count("champions", "s365_teams")
        if any(NOWIN.search(str(n or "")) for n in t[1:3]):
            A.add("champions", "placeholder_team_365", "error", "ours", f"s365team:{t[0]}", f"365Scores team {t[0]} «{t[1]}» / «{t[2]}» is a placeholder and has a team page")
    # all-time tables: titles = completed, non-void seasons (not the season in play)
    for cid in (538, 536, 535, 529, 519, 530, 516, 544, 524):
        at = A.pub.get(f"comp/{cid}/alltime-table.json") or {}
        ss = (A.pub.get(f"comp/{cid}/seasons.json") or {}).get("seasons") or {}
        if not at or not ss:
            continue
        A.count("champions", "alltime_titles")
        n_titles = sum(r.get("titles") or 0 for r in at.get("table") or [])
        cur = max(ss)
        x = (fm.get("comps") or {}).get(str(cid)) or {"champions": []}
        void = {str(r[0]).replace("-", "/") for r in x.get("champions") or [] if not r[1]}
        done = [s for s in ss if s != cur and s not in void]
        if n_titles != len(done):
            A.add("champions", "alltime_titles", "error", "ours", f"comp:{cid}", f"{A.comp[cid]['name_ar']} ({cid}): the all-time table counts {n_titles} titles for {len(done)} completed, non-void seasons (the season in play or a cancelled one counted)")


# ------------------------------------------------------------------ identity links (who is who)
LEAD_MON = {"يناير": 1, "كانون الثاني": 1, "جانفي": 1, "فبراير": 2, "شباط": 2, "فيفري": 2, "مارس": 3, "آذار": 3, "أبريل": 4, "إبريل": 4, "نيسان": 4, "أفريل": 4,
            "مايو": 5, "أيار": 5, "ماي": 5, "يونيو": 6, "حزيران": 6, "جوان": 6, "يوليو": 7, "تموز": 7, "جويلية": 7, "يوليوز": 7, "أغسطس": 8, "آب": 8, "أوت": 8,
            "غشت": 8, "سبتمبر": 9, "أيلول": 9, "شتنبر": 9, "أكتوبر": 10, "تشرين الأول": 10, "نوفمبر": 11, "تشرين الثاني": 11, "نونبر": 11, "ديسمبر": 12,
            "كانون الأول": 12, "دجنبر": 12}
_MRE = "|".join(sorted(map(re.escape, LEAD_MON), key=len, reverse=True))
LEAD_BIRTH = re.compile(r"(?:ولد|وُلد|مواليد|مولود|ولدت)[^0-9٠-٩]{0,25}?(\d{1,2})\s+(?:من\s+)?(" + _MRE + r")(?:\s*\([^)]*\))?\s*(?:من\s+)?(?:عام\s+|سنة\s+)?(\d{4})")
WOMEN_SIDE = re.compile(r"\(W\)|women|femin|ladies|سيدات|نسائي|\bII$|\bU-?\d\d\b|juniorit|reserve|تحت \d\d", re.I)


def area_identity(A):
    nat = national_ids(A)
    teams = (A.pub.get("teams.json") or {}).get("teams") or {}
    tname = lambda k: (teams.get(str(k)) or {}).get("name") or str(k)
    # 1. national teams must not carry a club's identity (card, Wikipedia lead, transfers)
    cards = (A.pub.get("history/clubs.json") or {}).get("clubs") or {}
    wiki = A.pub.get("history/wiki_ar.json") or {}
    trans = (A.pub.get("history/transfers.json") or {}).get("clubs") or {}
    for label, keys in (("club card (history/clubs.json)", cards), ("club Wikipedia lead", wiki.get("clubs") or {}), ("club transfers", trans)):
        bad = sorted(k for k in keys if k in nat)
        A.count("identity", "national_as_club", len(keys))
        if bad:
            A.add("identity", "national_as_club", "error", "ours", f"national:{label}", f"{len(bad)} national teams carry a {label}: " + ", ".join(f"{tname(k)} ({k})" for k in bad[:10]),
                  examples=bad[:40])
    # 2. one external identity per FotMob id and vice versa
    qids = defaultdict(list)
    for k, cc in cards.items():
        if cc.get("qid"):
            qids[cc["qid"]].append(k)
    shared = {q: ks for q, ks in qids.items() if len(ks) > 1}
    A.count("identity", "club_qid_shared", len(qids))
    if shared:
        A.add("identity", "club_qid_shared", "error", "ours", "clubs:qid", f"{len(shared)} Wikidata clubs are on two FotMob clubs: " +
              "; ".join(f"{q} -> {', '.join(tname(k) + ' (' + k + ')' for k in ks)}" for q, ks in list(shared.items())[:6]))
    try:
        photos = A.store.get_state("photos.json", None) or {}
    except Exception:
        photos = {}
    pq = defaultdict(list)
    for k, s in photos.items():
        if isinstance(s, dict) and s.get("qid") and str(s.get("status", "")).startswith(("ok", "no clear face")):
            pq[s["qid"]].append(k)
    sh = {q: ks for q, ks in pq.items() if len(ks) > 1}
    A.count("identity", "player_qid_shared", len(pq))
    if sh:
        A.add("identity", "player_qid_shared", "error", "ours", "players:qid", f"{len(sh)} Wikidata people give their photo/lead to two FotMob players: " +
              "; ".join(f"{q} -> {', '.join(ks)}" for q, ks in list(sh.items())[:6]), examples=[k for ks in sh.values() for k in ks][:40])
    # 3. every Arabic Wikipedia player lead: the identity check passed, and the lead's birth date is FotMob's
    bios = (A.pub.get("history/fm/players.json") or {}).get("players") or {}
    wb = (A.pub.get("world/bios.json") or {}).get("players") or {}
    trans_d = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    unchecked, conflict = [], []
    for k, v in (wiki.get("players") or {}).items():
        A.count("identity", "wiki_leads")
        rec = photos.get(k) or {}
        passed = rec.get("identity") == "ok" if "identity" in rec else str(rec.get("status", "none")).startswith(("ok", "no clear face"))
        if photos and not passed:
            unchecked.append(k)
        born = (bios.get(k) or {}).get("born") or ((wb.get(k) or [None, None])[1] if isinstance(wb.get(k), list) else None)
        m = LEAD_BIRTH.search(str(v[1] if isinstance(v, list) and len(v) > 1 else v).translate(trans_d))
        if born and m and born > "1900":
            lb = f"{int(m.group(3)):04d}-{LEAD_MON[m.group(2)]:02d}-{int(m.group(1)):02d}"
            if lb[:4] != born[:4] and abs(int(lb[:4]) - int(born[:4])) > 1:
                conflict.append((k, (bios.get(k) or {}).get("name"), born, lb))
    if unchecked:
        A.add("identity", "wiki_lead_unchecked", "warn", "ours", "wiki:players", f"{len(unchecked)} Arabic Wikipedia player leads come from a Wikidata person whose identity check did not pass", examples=unchecked[:40])
    if conflict:
        A.add("identity", "wiki_lead_other_person", "error", "ours", "wiki:players", f"{len(conflict)} Arabic Wikipedia player leads give another birth year than FotMob (another person): " +
              "; ".join(f"{n} ({k}) FotMob {b}, lead {lb}" for k, n, b, lb in conflict[:6]), examples=[x[0] for x in conflict[:60]])
    # 4. RSSSF: one table row per club per season
    dup = []
    for code in ("uae", "sau", "qat", "kuw", "egy", "maro", "alg", "tun", "iraq", "oman", "jord"):
        d = A.pub.get(f"history/arab/{code}.json") or {}
        for s in d.get("seasons") or []:
            seen = defaultdict(list)
            for row in s.get("table") or []:
                A.count("identity", "rsssf_rows")
                if len(row) > 2 and row[2]:
                    seen[row[2]].append(row[1])
            dup += [(code, s.get("season"), fid, ns) for fid, ns in seen.items() if len(ns) > 1]
    if dup:
        A.add("identity", "rsssf_two_clubs_one_id", "error", "ours", "rsssf", f"{len(dup)} RSSSF season tables link two different clubs to one FotMob club: " +
              "; ".join(f"{c} {s} {tname(f)} <- {ns}" for c, s, f, ns in dup[:6]))
    # 5. the 365 club map: no women's, youth or B side stands for a senior club
    idx = {t[0]: t for t in (A.pub.get("s365/index.json") or {}).get("teams") or []}
    bad = [(f, s, idx[s][1], idx[s][2]) for f, s in (A.fmmap() or {}).items() if s in idx and WOMEN_SIDE.search(f"{idx[s][1] or ''} {idx[s][2] or ''}")]
    A.count("identity", "fmmap_side", len(A.fmmap()))
    if bad:
        A.add("identity", "fmmap_women_youth", "error", "ours", "s365:fmmap", f"{len(bad)} FotMob clubs are linked to a 365Scores women's/youth/B side: " +
              "; ".join(f"{tname(f)} ({f}) -> {n2 or n1}" for f, s, n1, n2 in bad[:8]))
    # 6. EA FC cards and Transfermarkt records: the linked person's name must be ours (db/eafc.py and db/tmdata.py publish who
    #    they matched: a one-word or surname-only match at another club was a namesake, e.g. Isaac Lee for Myung-Dong Lee)
    for label, path in (("EA FC card", "ea/cards.json"), ("Transfermarkt record", "history/tm/index.json")):
        who = (A.pub.get(path) or {}).get("who") or {}
        odd = []
        for k, w in who.items():
            A.count("identity", "linked_names")
            ours_n = (bios.get(k) or {}).get("name") or ((wb.get(k) or [None])[0] if isinstance(wb.get(k), list) else None)
            # a one-word name (Rodri, Pedri, Vitinha) is a nickname of the full name: nothing to compare
            if ours_n and w and w[0] and len(S365.fold(ours_n).split()) > 1 and person_sim(ours_n, w[0]) < 0.6:
                odd.append(f"{ours_n} ({k}) = {w[0]}")
        if odd:     # mostly nicknames and full legal names (Taty / Valentín Castellanos): a list to eyeball, not errors
            A.add("identity", "linked_name_differs", "info", "unknown", f"identity:{path}", f"{len(odd)} {label}s carry a name unlike ours (nicknames, or namesakes to look at): " + "; ".join(odd[:8]),
                  examples=[x.split("(")[1].split(")")[0] for x in odd[:60]])
    # 7. placeholder birth dates (FotMob's 0001-01-01 shows «age 2025»)
    ph = [k for k, b in bios.items() if b.get("born") and b["born"] < "1900"]
    phw = [k for k, b in wb.items() if isinstance(b, list) and len(b) > 1 and b[1] and b[1] < "1900"]
    A.count("identity", "birth_dates", len(bios) + len(wb))
    if ph or phw:
        A.add("identity", "placeholder_birth_date", "warn", "gap", "players:born", f"{len(ph)} site players and {len(phw)} encyclopedia players have a placeholder birth date (0001-01-01): it must show as unknown, never as an age",
              examples=ph[:20])


# ------------------------------------------------------------------ gaps (missing data we could fill)
def area_gaps(A):
    teams = (A.pub.get("teams.json") or {}).get("teams") or {}
    miss_ar = []
    for c in A.comps:
        for m in A.fixtures(c["id"]):
            for side in ("home", "away"):
                t = m[side]
                if t.get("id") and not t.get("name_ar") and not (teams.get(str(t["id"])) or {}).get("name_ar") and not t.get("placeholder") \
                        and not placeholder_ar(t.get("name")):
                    miss_ar.append((t["id"], t.get("name"), c["id"]))
    miss_ar = sorted(set(miss_ar))
    A.count("gaps", "team_names_ar", len({t for c in A.comps for m in A.fixtures(c['id']) for t in (m['home']['id'], m['away']['id'])}))
    if miss_ar:
        A.add("gaps", "team_name_ar_missing", "warn", "gap", "teams", f"{len(miss_ar)} teams in our competitions have no Arabic name: " + ", ".join(f"{n} ({i})" for i, n, _ in miss_ar[:15]),
              examples=[i for i, _, _ in miss_ar[:40]])
    # player bios (the player page's card): what is still empty after FotMob, 365Scores' fill and Transfermarkt's fill
    bios = (A.pub.get("history/fm/players.json") or {}).get("players") or {}
    fill = {}
    for src in ("s365/fill.json", "history/tm/fill.json"):
        for k, v in ((A.pub.get(src) or {}).get("players") or {}).items():
            fill.setdefault(str(k), {}).update(v or {})
    if bios:
        fields, after = Counter(), Counter()
        alias = {"h": ("h", "height"), "foot": ("foot",), "shirt": ("shirt",), "contract": ("contract",), "born": ("born",), "mv": ("mv", "value"), "cc": ("cc",), "pos": ("pos",)}
        for pid, b in bios.items():
            for f, names in alias.items():
                if b.get(f) in (None, "", 0, []):
                    fields[f] += 1
                    if not any((fill.get(str(pid)) or {}).get(n) for n in names):
                        after[f] += 1
        A.count("gaps", "player_bios", len(bios))
        A.add("gaps", "player_bio_fields", "info", "gap", "players",
              f"{len(bios)} site players; empty in FotMob: " + ", ".join(f"{f} {n}" for f, n in fields.most_common()) +
              "; still empty after the 365Scores/Transfermarkt fills: " + ", ".join(f"{f} {n}" for f, n in after.most_common()),
              counts=dict(fields), after_fill=dict(after))
    # club cards: stadium (FotMob) and founded year (Wikidata card)
    tcards = (A.pub.get("history/fm/teams.json") or {}).get("teams") or {}
    cards = (A.pub.get("history/clubs.json") or {}).get("clubs") or {}
    if tcards:
        fields = Counter()
        for tid, t in tcards.items():
            if not ((t.get("venue") or {}).get("name") or ((cards.get(str(tid)) or {}).get("stadium") or {}).get("en")):
                fields["stadium"] += 1
            if not (cards.get(str(tid)) or {}).get("founded"):
                fields["founded"] += 1
            if not t.get("trophies"):
                fields["trophies"] += 1
        A.count("gaps", "club_cards", len(tcards))
        A.add("gaps", "club_card_fields", "info", "gap", "clubs", f"{len(tcards)} site clubs; empty: " + ", ".join(f"{f} {n}" for f, n in fields.most_common()), counts=dict(fields))


# ------------------------------------------------------------------ report
def summary(A):
    by = defaultdict(lambda: defaultdict(Counter))
    for f in A.findings:
        by[f["area"]][f["check"]][f["verdict"] + "/" + f["level"]] += 1
    return {a: {"checked": dict(A.checked.get(a, {})), "findings": {k: dict(v) for k, v in by.get(a, {}).items()}} for a in sorted(set(A.checked) | set(by))}


def markdown(A, doc):
    L = [f"# Tifo data audit — {doc['date']}", "",
         f"Generated {doc['generated']} by `python -m db.audit` in {doc['seconds']} s ({', '.join(f'{k} {v} s' for k, v in doc['timing'].items())}); "
         f"{doc['requests']['fotmob']} FotMob requests ({doc['requests']['fotmob_failed']} failed), {doc['requests']['s365']} 365Scores requests "
         f"(errors: {doc['requests']['s365_errors'] or 'none'}), {doc['requests']['published']} published files read. Window: the last {A.days} days; sample {A.sample}.", "",
         "Verdicts: **ours** = our code is wrong · **stale** = the source moved on and our copy didn't · **gap** = missing, fillable · "
         "**source** = the sources disagree (`favors` = which one the evidence supports) · **unknown**.", "", "## Summary", "",
         "| area | checked | errors | warnings | info |", "|---|---|---|---|---|"]
    for a, s in doc["summary"].items():
        lv = Counter()
        for f in A.findings:
            if f["area"] == a:
                lv[f["level"]] += 1
        L.append(f"| {a} | {sum(s['checked'].values())} | {lv['error']} | {lv['warn']} | {lv['info']} |")
    order = {"error": 0, "warn": 1, "info": 2}
    for a in AREAS:
        fs = [f for f in A.findings if f["area"] == a]
        if not fs:
            continue
        L += ["", f"## {a}", ""]
        by = defaultdict(list)
        for f in fs:
            by[(order[f["level"]], f["check"])].append(f)
        for (lv, chk), items in sorted(by.items()):
            L.append(f"### {chk} — {len(items)} ({items[0]['level']}, {Counter(i['verdict'] for i in items).most_common(1)[0][0]})")
            cap = 70 if all(str(i["key"]).startswith("comp:") for i in items) else 15     # one line per competition: all of them
            for f in items[:cap]:
                extra = ""
                if f.get("favors"):
                    extra += f" — favors **{f['favors']}**"
                if f.get("evidence"):
                    extra += f" — {f['evidence']}"
                L.append(f"- {f['msg']}{extra}" + (f" ({f['url']})" if f.get("url") else ""))
            if len(items) > cap:
                L.append(f"- … and {len(items) - cap} more (state/audit/{doc['date']}.json)")
    return "\n".join(L) + "\n"


AREA_AR = {"freshness": "تحديث البيانات", "matches": "المباريات", "standings": "جداول الترتيب", "scorers": "الهدافين",
           "derived": "المواجهات وتاريخ الأندية", "champions": "الأبطال", "identity": "هوية اللاعبين والأندية", "gaps": "النواقص"}


def public_summary(doc):
    """«الأرقام مدققة» (item 16, 2026-10-06): the day's audit as counts only, for the site's badge (v1/audit/latest.json).
    {generated, ok, checked, errors, warnings, areas: {area: {ar, checked, errors, warnings, ok}}}. No findings, no keys,
    no URLs, no messages, no timings: a visitor sees how much was checked and how much is still wrong, nothing internal.
    `ok` = no error left (a warning is a doubt or a source disagreement, an error is a number a visitor would see wrong);
    an area whose checks crashed, or that checked nothing, is never ok."""
    lv = {}
    crashed = set()
    for f in doc.get("findings") or []:
        a = f.get("area")
        c = lv.setdefault(a, {"error": 0, "warn": 0})
        if f.get("level") in c:
            c[f["level"]] += 1
        if f.get("check") == "audit_crashed":
            crashed.add(a)
    areas = {}
    for a in AREAS:
        if a not in (doc.get("params") or {}).get("areas", AREAS):
            continue
        s = (doc.get("summary") or {}).get(a) or {}
        n = sum(int(v) for v in (s.get("checked") or {}).values())
        e, w = lv.get(a, {}).get("error", 0), lv.get(a, {}).get("warn", 0)
        areas[a] = {"ar": AREA_AR[a], "checked": n, "errors": e, "warnings": w, "ok": e == 0 and n > 0 and a not in crashed}
    errors, warnings = sum(x["errors"] for x in areas.values()), sum(x["warnings"] for x in areas.values())
    return {"generated": doc.get("generated"), "ok": all(x["ok"] for x in areas.values()) and bool(areas),
            "checked": sum(x["checked"] for x in areas.values()), "errors": errors, "warnings": warnings, "areas": areas}


def publish(store, doc, areas):
    """Public only after a full audit (every area): a partial or local run never replaces the day's badge."""
    if set(areas) != set(AREAS):
        return None
    pub = public_summary(doc)
    store.put_json("audit/latest.json", pub, cache="static", heartbeat=True)    # heartbeat: `generated` = this audit's
    return pub


def run(store, areas, days=14, sample=60, verbose=True):
    A = Audit(store, days=days, sample=sample, verbose=verbose)
    fns = {"freshness": area_freshness, "matches": area_matches, "standings": area_standings, "scorers": area_scorers,
           "derived": area_derived, "champions": area_champions, "identity": area_identity, "gaps": area_gaps}
    timing = {}
    for a in AREAS:
        if a in areas:
            t0 = time.time()
            try:
                fns[a](A)
            except Exception as e:     # one broken area must not cost the others
                import traceback
                traceback.print_exc()
                A.add(a, "audit_crashed", "warn", "ours", f"audit:{a}", f"the {a} checks crashed: {type(e).__name__}: {e}")
            timing[a] = round(time.time() - t0)
    doc = {"date": A.now.astimezone(UAE).strftime("%Y-%m-%d"), "generated": iso(A.now), "seconds": round(time.time() - A.t0),
           "params": {"days": days, "sample": sample, "areas": sorted(areas)},
           "requests": {"fotmob": A.http.network_calls, "fotmob_failed": sum(A.http.failed.values()), "s365": A.s365.calls,
                        "s365_errors": {str(k): v for k, v in A.s365.errors.items()}, "published": A.pub.reads}, "timing": timing,
           "summary": None, "findings": A.findings, "notes": A.notes}
    doc["summary"] = summary(A)
    return A, doc


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=60)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--area", default=",".join(AREAS))
    ap.add_argument("--no-upload", action="store_true", help="don't write state/audit/<date>.json")
    ap.add_argument("--local", help="read a local mirror of the bucket instead of S3 (tests)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    store = Store(LocalBackend(a.local)) if a.local else Store(S3Backend(BUCKET))
    areas = {x.strip() for x in a.area.split(",") if x.strip()}
    A, doc = run(store, areas, a.days, a.sample, not a.quiet)
    md = markdown(A, doc)
    out = os.path.join(ROOT, "docs", f"AUDIT-DATA-{doc['date']}.md")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(md)
    if not a.no_upload:
        store.put_state(f"audit/{doc['date']}.json", doc)
        publish(store, doc, areas)                       # «الأرقام مدققة»: v1/audit/latest.json, counts only
    lv = Counter(f["level"] for f in A.findings)
    print(f"audit {doc['date']}: {lv['error']} errors, {lv['warn']} warnings, {lv['info']} info in {doc['seconds']} s -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
