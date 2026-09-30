"""Every match of every competition on the site since 2010, in detail (owner 2026-09-30: «متى بيكتمل كل شي من نتايج
ومباريات وكروت ولمسات وصناعات»), then every player's match log and season totals built from them.

    python -m db.matches [--upload] [--season 2024-2025] [--limit N] [--comp 538] [--no-pages]

Source: FotMob matchDetails for each match id in our own archive (v1/archive/all/<season>.json). What FotMob has depends
on the season and the league: in the UAE league 2010/11 the result only; from about 2014-2017 lineups, goals with the
assist, cards and substitutions; in recent seasons every player's stats (touches, passes, shots, dribbles, tackles…).
A finished match never changes: its compact record is cached for good in db/.cache/fm/mx/<id>.json and never fetched
again, so the daily run only asks for new matches.

Audit fixes (db/audit.py, 2026-09-30):
  * season labels are FotMob's own (each competition's season pages, cached for good in db/.cache/fm/seasons/): a July cut
    split the calendar-year competitions in two (MLS 2026 showed as «2025/2026» and «2026/2027», the World Cup 2026 as two
    seasons, AFCON 2023, played in 2024, as 2023/2024);
  * a player's minutes in a match without FotMob player stats come from the lineup and the substitutions (a starter
    until he is replaced or sent off, a substitute from his minute on), so a season line doesn't show 900 minutes for 30
    matches; a scorer or assister in a match without lineups still gets the match in his log;
  * the upload sends only what changed: the objects already published are listed with their ETag (= md5 of our
    deterministic gzip), so the daily run no longer re-sends 70k files and dies half way (5,012 logs of ~60k were live);
  * the site's finished matches with no match page (the poller backfills only the competitions in play: 1,575 of 4,124
    finished matches of the current seasons had no events or lineups, the World Cup 2026 among them) get one, in the
    poller's schema (--no-pages skips it);
  * the match pages of the last --refresh-days days (3) take FotMob's later corrections (scorer, assist, card player, a
    missing goal) and the results decided after the match (competitions.yaml awarded:), keeping what the poller computed.
Out (public):
  v1/matchx/<id>.json          one match: teams, score, date, round, stadium, referee, lineups, events, player stats
  v1/player/<id>/log.json      every match of the player (club and country) and his totals per season and competition
  v1/match/<id>.json           (pages) the match page's detail for finished site matches that had none
"""
import argparse, json, os, re, sys, threading, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import config  # noqa: E402
from sources import schema as S  # noqa: E402
from sources.fotmob import FotMob  # noqa: E402
from store import Store, S3Backend  # noqa: E402
from timeutil import iso, now_utc  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
MX = os.path.join(HERE, ".cache", "fm", "mx")
SEASONS = os.path.join(HERE, ".cache", "fm", "seasons")
# player stats kept per match (FotMob keys); the rest of FotMob's thirty-odd lines stay out of the files
KEEP = {"rating_title": "r", "minutes_played": "min", "goals": "g", "assists": "a", "total_shots": "sh", "ShotsOnTarget": "sot", "touches": "tch",
        "accurate_passes": "pas", "chances_created": "kp", "expected_goals": "xg", "expected_assists": "xa", "dribbles_succeeded": "dr",
        "successful_dribbles": "dr", "tackles_won": "tk", "matchstats.headers.tackles": "tk", "interceptions": "int", "clearances": "clr", "recoveries": "rec",
        "duel_won": "dw", "ground_duels_won": "gdw", "aerials_won": "aw", "was_fouled": "fd", "fouls": "fc", "saves": "sv", "goals_conceded": "gc",
        "accurate_crosses": "cr", "accurate_long_balls": "lb", "dispossessed": "dsp", "blocked_shots": "blk"}
FM = None
_LOCK = threading.Lock()


class Gentle:
    """At most `per_sec` FotMob requests a second across the fetch threads."""

    def __init__(self, per_sec):
        self.gap, self.next = 1.0 / per_sec, 0.0

    def wait(self):
        with _LOCK:
            now = time.monotonic()
            at = max(now, self.next)
            self.next = at + self.gap
        if at > now:
            time.sleep(at - now)


PACE = Gentle(float(os.environ.get("FM_PER_SEC", "4")))


def fm():
    global FM
    with _LOCK:
        FM = FM or FotMob()
    return FM


def val(stat):
    s = stat.get("stat") or {}
    v, t = s.get("value"), s.get("total")
    return [v, t] if t is not None else v


def compact(raw, mid):
    c, g, hd = raw.get("content") or {}, raw.get("general") or {}, raw.get("header") or {}
    teams = hd.get("teams") or [{}, {}]
    info = (c.get("matchFacts") or {}).get("infoBox") or {}
    stad, ref = info.get("Stadium") or {}, info.get("Referee") or {}
    m = {"id": mid, "date": g.get("matchTimeUTCDate") or (info.get("Match Date") or {}).get("utcTime") or g.get("matchTimeUTC"), "comp": g.get("parentLeagueId") or g.get("leagueId"),
         "round": g.get("leagueRoundName") or (info.get("Tournament") or {}).get("roundName"),
         "home": [teams[0].get("id"), teams[0].get("name"), teams[0].get("score")], "away": [teams[1].get("id"), teams[1].get("name"), teams[1].get("score")],
         "stadium": [stad.get("name"), stad.get("city")] if stad else None, "referee": ref.get("text") if isinstance(ref, dict) else None,
         "attendance": info.get("Attendance"), "lineups": {}, "events": [], "ps": {}}
    lu = c.get("lineup") or {}
    for side in ("homeTeam", "awayTeam"):
        t = lu.get(side) or {}
        rows = []
        for starter, grp in ((1, t.get("starters") or []), (0, t.get("subs") or [])):
            for p in grp:
                rows.append([p.get("id"), p.get("name"), p.get("shirtNumber"), p.get("positionId"), starter, ((p.get("performance") or {}).get("rating"))])
        if rows:
            m["lineups"]["h" if side == "homeTeam" else "a"] = {"formation": t.get("formation"), "players": rows}
    for e in ((c.get("matchFacts") or {}).get("events") or {}).get("events") or []:
        tp, side = e.get("type"), "h" if e.get("isHome") else "a"
        if tp == "Goal" and not e.get("isPenaltyShootoutEvent"):
            ap = re.search(r"/players/(\d+)", e.get("assistProfileUrl") or "")
            row = [e.get("time"), "g", side, e.get("playerId"), e.get("nameStr") or e.get("fullName"), int(ap.group(1)) if ap else None,
                   "own" if e.get("ownGoal") else ("pen" if (e.get("goalDescriptionKey") or "").startswith("pen") or e.get("suffixKey") == "penalty" else None)]
            how = GH.describe(e)                                  # how it was scored: «رأسية من ركنية» (appended, optional)
            if how:
                row += [how["ar"], how["key"]]
            m["events"].append(row)
        elif tp == "Card":
            m["events"].append([e.get("time"), "y" if e.get("card") == "Yellow" else "r" if e.get("card") in ("Red", "YellowRed") else "c", side, e.get("playerId"),
                                (e.get("player") or {}).get("name"), None, e.get("card")])
        elif tp == "Substitution":
            sw = e.get("swap") or [{}, {}]
            m["events"].append([e.get("time"), "s", side, int(sw[0].get("id") or 0) or None, sw[0].get("name"), int(sw[1].get("id") or 0) or None, sw[1].get("name")])
    for pid, p in (c.get("playerStats") or {}).items():
        row = {}
        for grp in p.get("stats") or []:
            for st in (grp.get("stats") or {}).values():
                k = KEEP.get(st.get("key"))
                if k and k not in row and (st.get("stat") or {}).get("value") is not None:
                    row[k] = val(st)
        if row:
            row["t"] = p.get("teamId")
            m["ps"][str(pid)] = row
    return m


def _save(mid, m):
    os.makedirs(MX, exist_ok=True)
    p = os.path.join(MX, f"{mid}.json")
    with open(p + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        json.dump(m, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(p + ".tmp", p)


def raw_detail(mid):
    for i in range(3):
        PACE.wait()
        try:
            return fm().http.get_json(f"https://www.fotmob.com/api/data/matchDetails?matchId={mid}", min_ttl=0)
        except Exception as e:
            if "404" in str(e):
                return None
            time.sleep(3 * (i + 1))
    return None


def fetch(mid):
    p = os.path.join(MX, f"{mid}.json")
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except ValueError:
            pass
    raw = raw_detail(mid)
    if raw is None:
        return None
    m = compact(raw, mid)
    if (raw.get("general") or {}).get("finished"):
        _save(mid, m)                    # not over yet: not cached, asked again next run
    with _LOCK:
        _FETCHED[0] += 1
        if _FETCHED[0] % 1000 == 0:
            print(f"  fetched {_FETCHED[0]}", flush=True)
    return m


_FETCHED = [0]


# ------------------------------------------------------------------ FotMob's season labels
def _label(s):
    """«2026», «2025/2026», «2023/2025»; «2025 Qatar» -> «2025»."""
    m = re.match(r"^\s*(\d{4}(?:/\d{4})?)", str(s or ""))
    return m.group(1) if m else (str(s) if s else None)


def season_labels(store, comp_ids):
    """({match id: FotMob season label}, {calendar-year competitions}): every season FotMob lists for each competition,
    each past season's match ids cached for good (db/.cache/fm/seasons/<comp>/<season>.json), the current season from
    our published fixtures."""
    out, calendar = {}, set()
    for cid in comp_ids:
        cur = store.get_json(f"comp/{cid}/fixtures.json") or {}
        cur_label = cur.get("season")
        for m in cur.get("matches") or []:
            if m.get("id") and (m.get("season") or cur_label):
                out[m["id"]] = _label(m.get("season") or cur_label)
        d = os.path.join(SEASONS, str(cid))
        os.makedirs(d, exist_ok=True)
        ip = os.path.join(d, "_seasons.json")
        labels = None
        if os.path.exists(ip) and time.time() - os.path.getmtime(ip) < 7 * 86400:
            labels = json.load(open(ip, encoding="utf-8"))
        else:
            try:
                PACE.wait()
                labels = fm().league_raw(cid).get("allAvailableSeasons") or []
                json.dump(labels, open(ip, "w", encoding="utf-8", newline="\n"))
            except Exception as e:
                print(f"seasons {cid}: {e}")
                labels = json.load(open(ip, encoding="utf-8")) if os.path.exists(ip) else []
        singles = [x for x in labels if "/" not in str(x)]
        if labels and len(singles) * 2 >= len(labels):
            calendar.add(cid)
        for lab in labels:
            if lab == cur_label or int((_label(lab) or "0")[:4] or 0) < 2009:      # the archive starts in 2010/11
                continue
            f = os.path.join(d, re.sub(r"[^0-9A-Za-z]+", "-", str(lab)) + ".json")
            ids = None
            if os.path.exists(f):
                try:
                    ids = json.load(open(f, encoding="utf-8"))
                except ValueError:
                    ids = None
            if ids is None:
                try:
                    PACE.wait()
                    raw = fm().league_raw(cid, lab)
                    ids = [int(x["id"]) for x in ((raw.get("fixtures") or {}).get("allMatches") or []) if str(x.get("id") or "").isdigit()]
                    json.dump(ids, open(f, "w", encoding="utf-8", newline="\n"))
                except Exception as e:
                    print(f"season {cid} {lab}: {e}")
                    continue
            for i in ids:
                out.setdefault(i, _label(lab))
    return out, calendar


def season_of(mid, d, comp, labels, calendar):
    lab = labels.get(mid)
    if lab:
        return lab
    y, mo = int(d[:4]), int(d[5:7])
    if comp in calendar:
        return str(y)
    return f"{y}/{y + 1}" if mo >= 7 else f"{y - 1}/{y}"


# ------------------------------------------------------------------ logs
def _min(t):
    try:
        return int(str(t).split("+")[0])
    except (TypeError, ValueError):
        return None


def est_minutes(m, pid, started):
    """Minutes from the lineup and the substitutions, for a match without FotMob player stats; None when the feed has no
    substitution at all (it doesn't report them, so a starter's 90 would be a guess)."""
    evs = m["events"]
    if not any(e[1] == "s" for e in evs):
        return None
    end = 120 if any((_min(e[0]) or 0) > 100 for e in evs) else 90
    on = 0 if started else next((_min(e[0]) for e in evs if e[1] == "s" and e[3] == pid), None)
    if on is None:
        return None
    off = next((_min(e[0]) for e in evs if e[1] == "s" and e[5] == pid), None)
    if off is None:
        off = next((_min(e[0]) for e in evs if e[1] == "r" and e[3] == pid), None)
    return max(0, min(end, off if off is not None else end) - on)


def resolve_ids(m):
    """Older FotMob feeds name a scorer or a booked player with id 0 (one goal in six): find him in the match's lineup by
    his name (exact, else a surname only one player of those sides has), so the goal lands in his log (Firmino's 2013/14
    Bundesliga showed 7 goals of 16)."""
    lu = {s: (m["lineups"].get(s) or {}).get("players") or [] for s in ("h", "a")}

    def find(name, sides):
        if not name:
            return None
        hit = {p[0] for s in sides for p in lu[s] if p[0] and p[1] == name}
        if len(hit) == 1:
            return hit.pop()
        last = str(name).split()[-1].lower()
        hit = {p[0] for s in sides for p in lu[s] if p[0] and p[1] and str(p[1]).split()[-1].lower() == last}
        return hit.pop() if len(hit) == 1 else None
    for e in m["events"]:
        if e[1] in ("g", "y", "r") and not e[3]:
            pid = find(e[4], ("h", "a") if (e[1] == "g" and e[6] == "own") else (e[2],))
            if pid:
                e[3] = pid
    return m


def build_logs(ms):
    logs = defaultdict(list)
    for m in ms:
        resolve_ids(m)
        on = defaultdict(dict)
        for side in ("h", "a"):
            team = m["home"] if side == "h" else m["away"]
            opp = m["away"] if side == "h" else m["home"]
            for p in ((m["lineups"].get(side) or {}).get("players") or []):
                if p[0]:
                    on[p[0]] = {"team": team[0], "opp": opp[0], "side": side, "start": p[4], "r": p[5]}
        for e in m["events"]:
            if e[1] == "s" and e[3] and e[3] not in on:            # a substitute the lineup left out
                on[e[3]] = {"team": (m["home"] if e[2] == "h" else m["away"])[0], "opp": (m["away"] if e[2] == "h" else m["home"])[0], "side": e[2], "start": 0}
        for e in m["events"]:                                       # no lineup for his side: a scorer or assister still played
            if e[1] == "g" and not (m["lineups"].get(e[2]) or {}).get("players"):
                side = e[2] if e[6] != "own" else ("a" if e[2] == "h" else "h")
                for pid in ((e[3], e[5]) if e[6] != "own" else (e[3],)):
                    if pid and pid not in on:
                        on[pid] = {"team": (m["home"] if side == "h" else m["away"])[0], "opp": (m["away"] if side == "h" else m["home"])[0], "side": side, "start": None}
        for pid, x in list(on.items()):
            st = m["ps"].get(str(pid)) or {}
            if x["start"] == 0 and not st.get("min") and not any(e[1] == "s" and e[3] == pid for e in m["events"]):
                continue                                           # an unused substitute
            # goals and assists: the player's own stat line when the match has one (FotMob credits assists there even when the
            # goal event names none), else the events
            g = st.get("g") if st.get("g") is not None else sum(1 for e in m["events"] if e[1] == "g" and e[3] == pid and e[6] != "own")
            a_ = st.get("a") if st.get("a") is not None else sum(1 for e in m["events"] if e[1] == "g" and e[5] == pid)
            y = sum(1 for e in m["events"] if e[1] == "y" and e[3] == pid)
            rd = sum(1 for e in m["events"] if e[1] == "r" and e[3] == pid)
            gs = m["home"][2] if x["side"] == "h" else m["away"][2]
            ga = m["away"][2] if x["side"] == "h" else m["home"][2]
            extra = {k: v for k, v in st.items() if k not in ("r", "min", "g", "a", "t")}
            mins = st.get("min")
            if mins is None and x["start"] is not None:
                mins = est_minutes(m, pid, x["start"])
                if mins is not None:
                    extra["min_est"] = 1                              # counted in the season line: how many were estimated
            logs[pid].append([m["id"], (m["date"] or "")[:10], m["comp"], x["team"], x["opp"], gs, ga, x["start"], mins, g, a_, y, rd, st.get("r") or x.get("r"), extra])
    return logs


def season_totals(L, labels, calendar):
    tot = {}
    for r in L:
        season = season_of(r[0], r[1], r[2], labels, calendar)
        k = f"{season}|{r[2]}"
        t = tot.setdefault(k, {"season": season, "comp": r[2], "apps": 0, "starts": 0, "min": 0, "g": 0, "a": 0, "y": 0, "r": 0, "rs": 0, "rn": 0})
        t["apps"] += 1
        t["starts"] += 1 if r[7] else 0
        t["min"] += r[8] or 0
        t["g"] += r[9]
        t["a"] += r[10]
        t["y"] += r[11]
        t["r"] += r[12]
        if r[13]:
            t["rs"] += float(r[13])
            t["rn"] += 1
        for sk, sv in (r[14] or {}).items():
            t[sk] = round(t.get(sk, 0) + (sv[0] if isinstance(sv, list) else (sv or 0)), 2)
    return sorted(tot.values(), key=lambda t: (t["season"][:4], t["season"]), reverse=True)


# ------------------------------------------------------------------ publishing
def remote_hashes(store, prefix, suffix, cache):
    """Store hashes for what is already published under v1/<prefix>: an unchanged file is not sent again (put_json
    compares the md5 of the gzipped body, which is the S3 ETag of a single-part upload)."""
    b = store.b
    out = {}
    if not isinstance(b, S3Backend):
        return out
    for page in b.s3.get_paginator("list_objects_v2").paginate(Bucket=b.bucket, Prefix="v1/" + prefix):
        for o in page.get("Contents") or []:
            if o["Key"].endswith(suffix):
                out[o["Key"]] = o["ETag"].strip('"') + "|" + cache
    return out


def put_all(store, items, threads=8):
    """[(path, obj, cache)] -> (sent, unchanged, failed); a failure is retried once, then counted, never fatal."""
    before_w, before_s = len(store.written), store.skipped_same
    failed = []

    def one(it):
        for i in range(2):
            try:
                store.put_json(it[0], it[1], cache=it[2])
                return
            except Exception as e:
                if i:
                    failed.append((it[0], f"{type(e).__name__}: {e}"))
                time.sleep(2)
    with ThreadPoolExecutor(threads) as ex:
        list(ex.map(one, items))
    return len(store.written) - before_w, store.skipped_same - before_s, failed


def pages(store, comp_ids, names):
    """match/<id>.json for the site's finished matches with none (poller schema: sources/fotmob.py + coverage_events)."""
    from poller import coverage_events
    have = set()
    for page in store.b.s3.get_paginator("list_objects_v2").paginate(Bucket=store.b.bucket, Prefix="v1/match/"):
        for o in page.get("Contents") or []:
            k = o["Key"][len("v1/match/"):-5]
            if k.isdigit():
                have.add(int(k))
    todo = []
    for cid in comp_ids:
        for m in (store.get_json(f"comp/{cid}/fixtures.json") or {}).get("matches") or []:
            if m.get("id") and m.get("status") == S.FINISHED and m["id"] not in have:
                todo.append(m["id"])
    print(f"pages: {len(todo)} finished site matches without a match page")
    src = FotMob(fm().http, names)
    now = iso(now_utc())

    def one(mid):
        raw = raw_detail(mid)
        if not raw:
            return None
        try:
            d = src.match_from_raw(raw)
            if d.get("status") != S.FINISHED:
                return None
            d["coverage_events"] = coverage_events(d)
            d["generated"] = now
            d["filled_by"] = "db.matches"          # the poller's backfill covers only competitions in play
            S.validate_detail(d)
        except Exception as e:
            print("page", mid, type(e).__name__, e)
            return None
        if (raw.get("general") or {}).get("finished") and not os.path.exists(os.path.join(MX, f"{mid}.json")):
            _save(mid, compact(raw, mid))
        return (f"match/{mid}.json", d, "static")
    with ThreadPoolExecutor(4) as ex:
        items = [x for x in ex.map(one, todo) if x]
    sent, same, failed = put_all(store, items)
    print(f"pages: {sent} match pages written, {len(failed)} failed")
    return sent


SOURCE_KEYS = ("score", "status", "status_detail", "penalties", "events", "halftime_score", "lineups", "stats", "xg", "shotmap", "momentum",
               "referee", "attendance", "coverage")


def refresh_pages(store, comp_ids, names, days):
    """FotMob corrects a finished match for hours (a scorer named, an assist moved, a card's player, a goal the feed lacked):
    the site's match pages of the last `days` days take FotMob's detail now when it differs. Only the source's own keys are
    replaced; what the poller computed (win probability, venue, weather, firsts…) stays, and so do the live stamps of
    events we already had. (audit 2026-09-30: 14 of 40 sampled pages differed from FotMob's detail a day later)"""
    from poller import coverage_events
    from compute import awarded as AW
    from timeutil import parse_utc
    now = now_utc()
    todo = []
    for cid in comp_ids:
        for m in (store.get_json(f"comp/{cid}/fixtures.json") or {}).get("matches") or []:
            ko = parse_utc(m.get("kickoff_utc"))
            if m.get("id") and m.get("status") in (S.FINISHED, S.AWARDED) and ko and 3 * 3600 < (now - ko).total_seconds() < days * 86400:
                todo.append(m["id"])
    src = FotMob(fm().http, names)
    aw = config.awarded()

    def one(mid):
        cur = store.get_json(f"match/{mid}.json")
        if not cur or cur.get("minimal"):
            return None
        raw = raw_detail(mid)
        if not raw:
            return None
        try:
            d = AW.apply_to_match(src.match_from_raw(raw), aw)
        except Exception:
            return None
        bare = lambda evs: [{k: v for k, v in e.items() if k != "first_seen"} for e in evs or []]
        if d.get("status") not in (S.FINISHED, S.AWARDED) or all((bare(d.get(k)) == bare(cur.get(k))) if k == "events" else d.get(k) == cur.get(k)
                                                                  for k in SOURCE_KEYS):
            return None
        seen = {e.get("event_id"): e.get("first_seen") for e in cur.get("events") or [] if e.get("first_seen")}
        for e in d.get("events") or []:
            if e.get("event_id") in seen:
                e["first_seen"] = seen[e["event_id"]]
        new = dict(cur, **{k: d.get(k) for k in SOURCE_KEYS}, coverage_events=coverage_events(d), refreshed=iso(now))
        return (f"match/{mid}.json", new, "static")
    with ThreadPoolExecutor(4) as ex:
        items = [x for x in ex.map(one, todo) if x]
    sent, same, failed = put_all(store, items)
    print(f"refresh: {len(todo)} finished site matches of the last {days} days checked, {sent} pages took FotMob's corrections, {len(failed)} failed")
    return sent


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--season")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--comp", type=int)
    ap.add_argument("--no-pages", action="store_true")
    ap.add_argument("--refresh-days", type=int, default=3, help="match pages of the last N days take FotMob's later corrections (0: off)")
    ap.add_argument("--pages-only", action="store_true", help="only the match-page steps (missing pages, corrections), no matchx/logs")
    a = ap.parse_args(argv)
    store = Store(S3Backend(BUCKET))
    comp_ids = [c["id"] for c in config.competitions()]
    if a.upload and not a.no_pages:
        names = store.get_state("names_ar.json", None) or {"teams": {}, "competitions": {}, "countries": {}}
        names.setdefault("teams", {}).update(config.team_overrides())       # the poller's own Arabic names
        pages(store, comp_ids, names)
        if a.refresh_days:
            refresh_pages(store, comp_ids, names, a.refresh_days)
    if a.pages_only:
        return 0
    seasons = [s["season"] for s in ((store.get_json("archive/index-all.json") or {}).get("seasons") or []) if s["season"] != "unknown"]
    if a.season:
        seasons = [a.season]
    ids, arch_comp = [], {}
    for s in seasons:
        for r in (store.get_json(f"archive/all/{s}.json") or {}).get("matches") or []:
            if r[5] is not None and (not a.comp or r[2] == a.comp):
                ids.append(r[0])
                arch_comp[r[0]] = r[2]
    ids = sorted(set(ids), reverse=True)
    if a.limit:
        ids = ids[:a.limit]
    todo = [i for i in ids if not os.path.exists(os.path.join(MX, f"{i}.json"))]
    print(f"{len(ids)} finished matches; {len(todo)} to fetch")
    t0 = time.time()
    with ThreadPoolExecutor(int(os.environ.get("FM_THREADS", "4"))) as ex:
        ms = [m for m in ex.map(fetch, ids) if m]
    fixed = 0
    for m in ms:     # the archive knows the competition; matchDetails gives a stage id when parentLeagueId is missing (505 log rows)
        c_ = arch_comp.get(m["id"])
        if c_ and m.get("comp") != c_:
            m["comp"] = c_
            fixed += 1
    if fixed:
        print(f"{fixed} matches took the archive's competition id (FotMob gave a stage id)")
    print(f"{len(ms)} matches ({round(time.time() - t0)}s); with lineups {sum(1 for m in ms if m['lineups'])}, with player stats {sum(1 for m in ms if m['ps'])}")
    logs = build_logs(ms)
    print(len(logs), "players with a match log")
    labels, calendar = season_labels(store, sorted({m["comp"] for m in ms if m.get("comp")} | set(comp_ids)))
    print(f"season labels for {len(labels)} matches; calendar-year competitions: {sorted(calendar)}")
    tm = fm().http.get_json("https://www.fotmob.com/api/translationmapping?locale=ar", min_ttl=3600)
    TT, PP = tm.get("TournamentTemplates") or {}, tm.get("Participants") or {}
    if a.upload:
        t0 = time.time()
        store.hashes.update(remote_hashes(store, "matchx/", ".json", "static"))
        store.hashes.update(remote_hashes(store, "player/", "/log.json", "warm"))
        print(f"{len(store.hashes)} published files listed ({round(time.time() - t0)}s)")
        items = [(f"matchx/{m['id']}.json", dict(m, names={"comp": TT.get(str(m["comp"])), "home": PP.get(str(m["home"][0])), "away": PP.get(str(m["away"][0]))}), "static") for m in ms]
        sent, same, failed = put_all(store, items)
        print(f"matchx: {sent} sent, {same} unchanged, {len(failed)} failed {failed[:3]}")
        items = []
        for pid, L in logs.items():
            L.sort(key=lambda r: r[1], reverse=True)
            items.append((f"player/{pid}/log.json", {
                "player": pid, "fields": ["match", "date", "comp", "team", "opp", "for", "against", "started", "minutes", "goals", "assists", "yellow", "red", "rating", "stats"],
                "matches": L, "seasons": season_totals(L, labels, calendar), "source": "FotMob",
                # Arabic names for what the log shows (FotMob's own mapping), so the page needs nothing else
                "comps": {str(c): TT.get(str(c)) for c in {r[2] for r in L} if TT.get(str(c))},
                "teams": {str(t): PP.get(str(t)) for t in {x for r in L for x in (r[3], r[4])} if PP.get(str(t))}}, "warm"))
        sent, same, failed = put_all(store, items)
        print(f"logs: {sent} sent, {same} unchanged, {len(failed)} failed {failed[:3]}")
        print("uploaded")
        if failed:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
