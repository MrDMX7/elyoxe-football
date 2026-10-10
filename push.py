"""Per-team web push (item approved 2026-09-28; video and subscriber choices item 7, 2026-10-06): kickoff, goal (with how it
was scored), full time, and «فيديو الهدف نزل» (an official clip of the goal came out).

Three parts:
  * `plan(p, d, full)` runs inside the poller's fetch_detail (live and final details). It decides which events are new for
    this match (kickoff, each goal, full time), builds one Arabic payload per team and hands them to the sender with ONE
    asynchronous Lambda invoke, so the poller never waits on push services.
  * `video_jobs(md, goals)` is called by news/media.py (the journal, every 15 min) for the goals whose first official clip
    just came out: one job per goal, handed over with `invoke`. Never from the poller's minute loop.
  * `handler(event, ctx)` is the sender (Lambda elyoxe-football-push): for each team it queries the subscriptions
    (DynamoDB `cards`, pk TIFOPUSH#<team>, written by the cards stack's /api/tifo/push/sub), CLAIMS the event (below), and
    sends with pywebpush + the VAPID key from SSM to every subscription that chose that event and is not in its quiet hours.
    404/410 from a push service deletes the subscription; any other error is logged (push service host only) and skipped.

Never the same event twice. 2026-10-01..06 (the sender's own logs): the poller timed out every minute and handed the same
events over again and again; the sender's claim turned away all 1,845 repeats of an unchanged key, but 21 goals were
claimed twice because FotMob had moved their minute (87' -> 88' and 17 more by one minute, 86' -> 90' by four), which made
a new key. So:
  1. one identity per event, stable across the feed's corrections: «start», «end», a goal by the score it made («goal:2-1»),
     a goal's clip by the same score («video:2-1»). The scorer (FotMob's «<TBD>» filled in later) and the minute are never
     part of it. The same score again is a second goal («goal:2-1#2») only on two independent signs: the poller SAW the
     first one taken back (the match score went below it after it was handed over: state/push.json `back`), and the two
     minutes are more than SAME_GOAL_SPREAD apart (seen: 13' then 23', 65' then 89', 35' then 83'). A correction is
     never both; a duplicate would need a score flicker and a correction of more than 6 minutes at once;
  2. the sender CLAIMS each event before its first send: a conditional put of TIFOPUSHSENT#<match> / <key> after a
     consistent read of the match's claims, which a retried invoke, a second poller pass, a re-run media step or a
     concurrent sender all lose; a second goal at a claimed score is claimed only when the job says the poller saw the
     takeback and every claim at that score is more than SAME_GOAL_SPREAD minutes away. A sender that dies mid-send keeps
     its claim: that event's remaining subscribers miss it (at most once, never twice);
  3. the poller keeps its own marks in state/push.json, written right after each hand-over or takeback, not at the end
     of the run, so a run that dies later does not hand the same events over again next minute. A goal the live minute
     has left STALE_MINUTES behind (a run that died before handing it over) is history, not news.
A goal the VAR took back before we saw it is never sent: only goal events present in the current detail, with no later
"goal disallowed" VAR decision for that side, are pushed. Old events (first seen > 10 min ago, e.g. after a deploy or a
backfill) are not pushed.
"""
import json, os, re, time

import pushplayer as PP       # «تابع اللاعب»: the followed players' match events (docs/superpowers/specs/2026-10-09-player-follow-design.md)

TABLE = os.environ.get("PUSH_TABLE", "cards")
REGION = os.environ.get("PUSH_REGION", "ap-south-1")
SENDER = "elyoxe-football-push"   # the sender's function name (the poller's PUSH_FUNCTION, media's default)
SUBJECT = "mailto:hello@elyoxe.com"
FRESH_MINUTES = 10            # a goal first seen longer ago than this is history, not news
STALE_MINUTES = 12            # a goal this many match minutes behind the live minute is history (a run died before it)
SAME_GOAL_SPREAD = 6          # minutes: the same score this close is the same goal (corrections seen: 1 and 4; re-scores: 10+)
KICKOFF_WINDOW = 20           # minutes after kickoff within which a "start" push still makes sense
END_WINDOW = 60               # minutes after full time
GOAL_TYPES = ("goal", "own_goal", "penalty_goal")
DISALLOWED = ("goal_disallowed", "goal_disallowed_offside")
TEAM_EVENTS = ("start", "goal", "end", "video", "transfer")   # transfer: the club's official moves (pushtransfers.py)
# a player subscription stores player kinds (pushplayer.KINDS; written out: pushplayer imports this module, so nothing here may
# read pushplayer while it loads; tests/test_pushplayer.py checks the two lists agree)
EVENTS = TEAM_EVENTS + ("soon", "start11", "squad_out", "subin", "subout", "assist", "card", "pen", "potm")
DEFAULT_EVENTS = ("start", "goal", "end")      # a subscription that never chose (before 2026-10-06), and the UI's «كل شي»
MAX_SENDS = 5000              # per invoke: the sender's 5-minute budget, ~40 ms per send with a pooled session
JOB_TTL = {"start": 600, "goal": 600, "end": 900, "video": 1800,   # seconds a handed-over job stays worth sending
           "soon": 1800, "start11": 1800, "squad_out": 1800, "subin": 600, "subout": 600, "assist": 600, "card": 600, "pen": 600,
           "potm": 3600, "transfer": 6 * 3600}
PLACEHOLDER_WAIT = 2          # minutes a «<TBD>» goal waits for its scorer's name when someone in the match is followed
PLAYER_DAILY_CAP = 20         # player alerts per device per UAE day (owner 2026-10-09: «اذا تشوف اشياء تسوي مشاكل»)
DATA = os.environ.get("TIFO_DATA", "https://d1n5aqaqkowltp.cloudfront.net")
CLAIM_DAYS = 3


# ------------------------------------------------------------------ payloads (pure, tested)
def _name(t):
    return (t or {}).get("name_ar") or (t or {}).get("name") or ""


def _minute(e):
    m, a = e.get("minute"), e.get("added")
    return f"{m}+{a}" if a else f"{m}"


def _score(sc):
    return f"{sc['home']} - {sc['away']}" if sc else "-"


def total_minute(minute, added=None):
    """67 -> 67, (45, 2) -> 47, "45+2" -> 47, "HT" -> 45; None when unknown."""
    if minute is None:
        return None
    if isinstance(minute, str):
        s = minute.strip().replace("'", "")
        if s.upper() == "HT":
            return 45
        m = re.fullmatch(r"(\d{1,3})(?:\s*\+\s*(\d{1,2}))?", s)
        if not m:
            return None
        return int(m.group(1)) + int(m.group(2) or 0) + int(added or 0)
    try:
        return int(minute) + int(added or 0)
    except (TypeError, ValueError):
        return None


# FotMob sends a goal first with the scorer as «<TBD>» (player id 0) and fills the name about a minute later.
# Seen live 2026-09-28 on 6040346: the first push read «سجّل <TBD>», and the named event got a new event_id
# (…-goal-38-0-0 -> …-goal-38-0-854041), so the same goal was pushed twice.
PLACEHOLDERS = ("", "<tbd>", "tbd", "unknown")


def _known(pl):
    return bool(pl and pl.get("id") and str(pl.get("name") or "").strip().lower() not in PLACEHOLDERS)


def score_key(kind, sc):
    """«goal:2-1» / «video:2-1»: a goal by the score it made; None while the feed gives no score."""
    sc = sc or {}
    if sc.get("home") is None or sc.get("away") is None:
        return None
    try:
        return f"{kind}:{int(sc['home'])}-{int(sc['away'])}"
    except (TypeError, ValueError):
        return None


def player_ar(pl, names_ar):
    if not _known(pl):
        return None
    x = (names_ar or {}).get(str(pl.get("id")))
    return (x or {}).get("ar") if isinstance(x, dict) else x or pl.get("name")


def _how(e):
    """«رأسية من ركنية» (compute/goal_how.py), unless it only repeats what the line says already (penalty, own goal)."""
    h = e.get("how") or {}
    k, ar = str(h.get("key") or ""), str(h.get("ar") or "").strip()
    if not ar or k.startswith("penalty") or k.startswith("own_goal"):
        return ""
    return ar


def payload(kind, d, team, e=None, names_ar=None):
    """{title, body, url, tag, team}. Titles read «هدف! الإمارات 1 - 0 قطر»; Western digits throughout."""
    mid, h, a = d["id"], _name(d.get("home")), _name(d.get("away"))
    base = {"url": f"/m/{mid}/", "tag": f"m-{mid}", "team": team}
    if kind == "start":
        return {**base, "title": "بدت المباراة", "body": f"{h} - {a}"}
    if kind == "end":
        return {**base, "title": f"انتهت: {h} {_score(d.get('score'))} {a}",
                "body": (d.get("comp_name_ar") or "").strip() or "النتيجة النهائية"}
    sc = e.get("score") or d.get("score")
    who = player_ar(e.get("player"), names_ar)
    side = _name(d.get(e.get("team"))) if e.get("team") in ("home", "away") else ""
    if e["type"] == "own_goal":
        body = f"هدف عكسي{f' من {who}' if who else ''} في الدقيقة {_minute(e)}'"
    elif who:
        body = f"سجّل {who}{' من ركلة جزاء' if e['type'] == 'penalty_goal' else ''} في الدقيقة {_minute(e)}'"
    else:            # scorer not known yet: the team, never a placeholder
        body = f"هدف {side}{' من ركلة جزاء' if e['type'] == 'penalty_goal' else ''} في الدقيقة {_minute(e)}'".replace("هدف  ", "هدف ")
    how = _how(e)
    return {**base, "title": f"هدف! {h} {_score(sc)} {a}", "body": body + (f" · {how}" if how else "")}


def video_payload(md, team, e, goal_key, names_ar=None):
    """«فيديو الهدف نزل»: the scorer and minute, then the score the goal made. The link opens the match page on that goal's clip
    (#v=<goal key>, the key the page's goal rows carry: «45+2-<playerId>»)."""
    mid, h, a = md["id"], _name(md.get("home")), _name(md.get("away"))
    who = player_ar(e.get("player"), names_ar) or (f"هدف {_name(md.get(e.get('team')))}" if e.get("team") in ("home", "away") else "الهدف")
    return {"url": f"/m/{mid}/#v={goal_key}", "tag": f"mv-{mid}", "team": team, "title": "فيديو الهدف نزل",
            "body": f"{who} {_minute(e)}' · {h} {_score(e.get('score'))} {a}"}


# ------------------------------------------------------------------ marks: what the poller already handed over
# state/push.json {match: {at, keys, back}}. keys: "start", "end", "goal:2-1@47" (the score the goal made @ its total minute;
# a second goal at that score is a second mark). back: "2-1" once for each time the poller saw the match score go below a
# score it had handed over (a goal taken back). Older marks, from before 2026-10-06, "goal:<match>-<side>-<minute[+added]>-
# <h>-<a>" (goal_key of 2026-09-28), are read as the same thing.
_MARK_NEW = re.compile(r"^goal:(\d+)-(\d+)(?:#\d+)?@(\d{1,3})$")
_MARK_OLD = re.compile(r"^goal:\d+-(?:home|away|None)-(\d{1,3})(?:\+(\d{1,2}))?-(\d+)-(\d+)$")


def goal_marks(keys):
    """[(home, away, total minute)] for the goal marks among `keys`."""
    out = []
    for k in keys or []:
        m = _MARK_NEW.match(k)
        if m:
            out.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
            continue
        m = _MARK_OLD.match(k)
        if m:
            out.append((int(m.group(3)), int(m.group(4)), int(m.group(1)) + int(m.group(2) or 0)))
    return out


def goal_verdict(marks, back, h, a, minute):
    """A goal at score h-a: "new" (nothing handed over at that score), "again" (every goal handed over at that score was
    seen taken back AND this minute is more than SAME_GOAL_SPREAD from each of theirs: a second goal), or None (the goal
    handed over already, under a corrected minute or scorer)."""
    at = [mm for mh, ma, mm in marks if (mh, ma) == (h, a)]
    if not at:
        return "new"
    if list(back or []).count(f"{h}-{a}") >= len(at) and minute is not None and all(abs(mm - minute) > SAME_GOAL_SPREAD for mm in at):
        return "again"
    return None


def takebacks(keys, back, cur):
    """The scores handed over that the match score no longer reaches (below it on a side), each counted once per goal."""
    if not cur or cur.get("home") is None or cur.get("away") is None:
        return []
    n = {}
    for h, a, _ in goal_marks(keys):
        n[(h, a)] = n.get((h, a), 0) + 1
    back = list(back or [])
    return [f"{h}-{a}" for (h, a), k in n.items() if back.count(f"{h}-{a}") < k and (int(cur["home"]) < h or int(cur["away"]) < a)]


# ------------------------------------------------------------------ which events are new (pure, tested)
def _age_min(ts, now):
    from timeutil import parse_utc
    t = parse_utc(ts) if ts else None
    return 1e9 if t is None else (now - t).total_seconds() / 60


def _match_minute(d, evs):
    """The match's minute now (total, 45+2 = 47): the live minute, or for a finished match the last event's (at least 90)."""
    st = d.get("status")
    if st in ("live", "ht"):
        return total_minute(d.get("minute") if d.get("minute") is not None else ("HT" if st == "ht" else None))
    if st == "finished":
        return max([90] + [total_minute(e.get("minute"), e.get("added")) or 0 for e in evs if e.get("type") != "added_time"])
    return None


def events_to_send(d, full, sent, now, back=()):
    """[(key, kind, event|None, total minute|None, again)] for this detail, minus what `sent` (marks) already has. `back`:
    the takebacks the poller saw (state/push.json); again = a second goal at a score already handed over."""
    out = []
    sent = list(sent or [])
    st = d.get("status")
    periods = d.get("periods") or {}
    if st in ("live", "ht") and "start" not in sent:
        started = periods.get("firstHalfStarted") or d.get("kickoff_utc")
        if _age_min(started, now) <= KICKOFF_WINDOW:
            out.append(("start", "start", None, None, False))
    evs = full.get("events") or []
    var = [e for e in evs if e.get("type") == "var" and e.get("var_outcome") in DISALLOWED]
    cur = d.get("score") or full.get("score") or {}
    marks = goal_marks(sent)
    now_min = _match_minute(d, evs)
    for e in evs:
        if e.get("type") not in GOAL_TYPES or not e.get("event_id"):
            continue
        es = e.get("score") or {}
        key = score_key("goal", es)
        if not key:                     # no score on the event yet: the next pass has it
            continue
        # 6040346, 2026-09-28 20:17Z: the feed listed a «<TBD>» away goal at 49' making 2-2 while the match stood 2-1, and it
        # was pushed. A goal the match score doesn't have yet waits (not marked, so the next pass retries).
        if cur and any((es.get(k) or 0) > (cur.get(k) or 0) for k in ("home", "away")):
            continue
        mn = total_minute(e.get("minute"), e.get("added"))
        verdict = goal_verdict(marks, back, int(es["home"]), int(es["away"]), mn)
        if verdict is None:
            continue                    # handed over already, whatever minute or scorer the feed gives it now
        if _age_min(e.get("first_seen"), now) > FRESH_MINUTES:
            continue
        if now_min is not None and mn is not None and now_min - mn > STALE_MINUTES:
            continue                    # the match moved on long ago: a run that died before this goal went out
        if any(v.get("team") == e.get("team") and (v.get("minute") or 0) >= (e.get("minute") or 0) for v in var):
            continue                    # the VAR took it back
        out.append((key, "goal", e, mn, verdict == "again"))
    if st == "finished" and "end" not in sent:
        ended = periods.get("gameEnded") or periods.get("secondHalfEnded")
        if _age_min(ended, now) <= END_WINDOW:
            out.append(("end", "end", None, None, False))
    return out


def mark(job):
    return f"{job['key']}@{job['min']}" if job["kind"] == "goal" and job.get("min") is not None else job["key"]


def _job(mid, key, kind, payloads, minute=None, now=None, again=False):
    j = {"match": int(mid), "key": key, "kind": kind, "urgency": "high" if kind == "goal" else "normal",
         "exp": int(now if now is not None else time.time()) + JOB_TTL[kind], "payloads": payloads}
    if minute is not None:
        j["min"] = int(minute)
    if again:
        j["again"] = True               # the poller saw the first goal at this score taken back
    return j


def _marks(p):
    """state/push.json {match: {at, keys}}, loaded once per run; the marks poller.json carried before 2026-10-06 move here."""
    marks = p.aux("push")
    old = p.st.pop("push_sent", None) if isinstance(getattr(p, "st", None), dict) else None
    for mid, v in (old or {}).items():
        cur = marks.setdefault(mid, {"at": v.get("at"), "keys": []})
        cur["keys"] = list(dict.fromkeys(cur["keys"] + list(v.get("keys") or [])))
    return marks


def _flush(p, mid):
    try:
        p.aux_flush("push")          # now, not at the end of the run: a run that dies later must not lose these
    except Exception as ex:          # the sender's claim still holds; the marks go out with the run's save()
        p.store.fail("push", f"{mid}: marks not saved now: {type(ex).__name__}: {ex}")


def plan(p, d, full, invoke=None):
    """Called from Poller.fetch_detail. Marks and hands over new events; never raises into the poller."""
    if not os.environ.get("PUSH_FUNCTION") and invoke is None:
        return []
    mid = str(d["id"])
    marks = _marks(p)
    sent = marks.get(mid) or {"at": None, "keys": []}     # stored only once something is handed over (prematch passes add nothing)
    back = sent.setdefault("back", [])
    gone = takebacks(sent["keys"], back, d.get("score") or full.get("score"))
    if gone:                         # a goal handed over is no longer in the score: the VAR (or the feed) took it back
        marks[mid] = sent
        back += gone
        p.note(f"push: {mid} taken back {', '.join(gone)}")
        _flush(p, mid)
    todo = events_to_send(d, full, sent["keys"], p.now(), back)
    followed, pev = p.aux("push_players"), []
    try:                             # «تابع اللاعب»: whatever goes wrong here, the team alerts still go out
        if followed:
            pev = PP.events_for(d, full, followed, sent["keys"], p.now())
            L = PP.lineup(full)
            if (set(L["start"]) | set(L["bench"])) & set(followed):
                # FotMob names the scorer about a minute after the goal («<TBD>» first): with someone in this match followed,
                # a nameless goal waits up to PLACEHOLDER_WAIT minutes so his followers get «هدف! <name>» (else it goes out nameless)
                todo = [x for x in todo if not (x[1] == "goal" and x[2] and not _known(x[2].get("player"))
                                                and _age_min(x[2].get("first_seen"), p.now()) < PLACEHOLDER_WAIT)]
    except Exception as ex:
        p.store.fail("push-player", f"{mid}: {type(ex).__name__}: {ex}")
        followed, pev = {}, []
    if not todo and not pev:
        return []
    names_ar = _names_ar()
    teams = [t for t in ((d.get("home") or {}).get("id"), (d.get("away") or {}).get("id")) if t]
    jobs = [_job(mid, key, kind, {str(t): payload(kind, d, t, e, names_ar) for t in teams}, mn, again=again)
            for key, kind, e, mn, again in todo]
    # the scorer's and the assister's followers ride on the team's goal job, and his full-time line on the team's «end» job
    # (one claim, one push per device, the player's text first); every other player event is a job of its own
    rode = []
    try:
        for j, (key, kind, e, mn, again) in zip(list(jobs), todo):
            if kind == "goal" and e and followed:
                aud = _player_goal_audiences(d, e, followed, names_ar)
                if aud:
                    j["payloads"] = {**aud, **j["payloads"]}
        endj = next((j for j in jobs if j["key"] == "end"), None)
        for key, kind, pid, e, extra in pev:
            pl = PP.payload(kind, d, pid, e, names_ar, extra)
            if kind == "end" and endj is not None:
                endj["payloads"] = {f"P{pid}": pl, **endj["payloads"]}
                rode.append(key)
            else:
                jobs.append(_job(mid, key, kind, {f"P{pid}": pl}))
    except Exception as ex:
        p.store.fail("push-player", f"{mid}: {type(ex).__name__}: {ex}")
    if not jobs:
        return []
    try:
        (invoke or _invoke)({"jobs": jobs})
    except Exception as ex:          # not marked: the next pass tries again (the sender dedupes)
        p.store.fail("push", f"{mid}: invoke failed: {type(ex).__name__}: {ex}")
        return []
    marks[mid] = sent
    sent["keys"] += [mark(j) for j in jobs] + rode           # a player job's mark is its key («p<pid>:<kind>…»)
    sent["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for k in [k for k, v in marks.items() if v.get("at") and _age_min(v["at"], p.now()) > CLAIM_DAYS * 1440]:
        del marks[k]
    _flush(p, mid)
    p.note(f"push: {mid} {', '.join(j['key'] + ('+' if j.get('again') else '') for j in jobs)}")
    return jobs


def _player_goal_audiences(d, e, followed, names_ar, video_key=None):
    """{"P<pid>": payload} for a goal's scorer and assister when someone follows them (a video: the scorer only)."""
    mid, h, a = d["id"], _name(d.get("home")), _name(d.get("away"))
    out = {}
    roles = (("goal", e.get("player")),) if video_key else (("goal", e.get("player")), ("assist", e.get("assist")))
    for role, who in roles:
        pid = str((who or {}).get("id") or "")
        if not pid or pid not in followed or not _known(who):
            continue
        n = player_ar(who, names_ar) or pid
        if video_key:
            out[f"P{pid}"] = {"title": f"فيديو هدف {n} نزل", "body": f"{h} {_score(e.get('score'))} {a}", "url": f"/m/{mid}/#v={video_key}",
                              "tag": f"pv-{pid}-{mid}", "kind": "video"}
        else:
            out[f"P{pid}"] = {"title": f"هدف! {n}" if role == "goal" else f"صناعة! {n}", "url": f"/m/{mid}/", "tag": f"p{pid}-{mid}", "kind": role,
                              "body": f"{h} {_score(e.get('score') or d.get('score'))} {a} · الدقيقة {_minute(e)}'"}
    return out


def video_jobs(md, goals, names_ar=None, now=None, followed=None):
    """news/media.py: goals whose first official clip just came out ({goal key «45+2-<playerId>»: event}) -> one sender job
    per goal, keyed by the score it made («video:2-1»). A goal without a score on its event gives no job."""
    names_ar = _names_ar() if names_ar is None else names_ar
    teams = [t for t in ((md.get("home") or {}).get("id"), (md.get("away") or {}).get("id")) if t]
    jobs = []
    for gk, e in goals.items():
        key = score_key("video", e.get("score"))
        if not key or not teams:
            continue
        aud = _player_goal_audiences(md, e, followed or {}, names_ar, video_key=gk)
        jobs.append(_job(md["id"], key, "video", {**aud, **{str(t): video_payload(md, t, e, gk, names_ar) for t in teams}},
                         total_minute(e.get("minute"), e.get("added")), now))
    return jobs


_NAMES = {}


def _names_ar():
    if "d" not in _NAMES:
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "names", "players_ar.json"), encoding="utf-8") as f:
                _NAMES["d"] = json.load(f)
        except (OSError, ValueError):
            _NAMES["d"] = {}
    return _NAMES["d"]


def invoke(jobs, function=None):
    """Hand jobs to the sender: one asynchronous invoke (the caller never waits on push services)."""
    import boto3
    boto3.client("lambda", region_name=REGION).invoke(FunctionName=function or os.environ.get("PUSH_FUNCTION") or SENDER,
                                                     InvocationType="Event",
                                                     Payload=json.dumps({"jobs": jobs}, ensure_ascii=False).encode())


def _invoke(event):
    invoke(event["jobs"], os.environ["PUSH_FUNCTION"])


# ------------------------------------------------------------------ subscriber choices (pure, tested)
def wants(sub, kind):
    ev = sub.get("events") or DEFAULT_EVENTS
    return kind in ev


def in_quiet(sub, now=None):
    """Quiet hours stored with the subscription: {"s": start, "e": end} in minutes after local midnight, "o" the device's UTC
    offset in minutes (UAE 240). 23:00-07:00 wraps midnight. No quiet hours, or a malformed value, never blocks."""
    q = sub.get("quiet")
    if not isinstance(q, dict):
        return False
    try:
        s, e, o = int(q["s"]), int(q["e"]), int(q.get("o", 240))
    except (KeyError, TypeError, ValueError):
        return False
    if not (0 <= s < 1440 and 0 <= e < 1440) or s == e or not -720 <= o <= 840:
        return False
    t = time.gmtime(now if now is not None else time.time())
    local = (t.tm_hour * 60 + t.tm_min + o) % 1440
    return s <= local < e if s < e else (local >= s or local < e)


# ------------------------------------------------------------------ the sender (Lambda elyoxe-football-push)
_VAPID = {}


def _vapid():
    if "v" not in _VAPID:
        import boto3
        from py_vapid import Vapid
        pem = boto3.client("ssm", region_name=REGION).get_parameter(
            Name=os.environ.get("VAPID_PRIVATE_PARAM", "/elyoxe/tifo/vapid_private"), WithDecryption=True)["Parameter"]["Value"]
        _VAPID["v"] = Vapid.from_pem(pem.encode())
    return _VAPID["v"]


def _send_one(sub, data, urgency, session=None, ttl=600):
    """-> 'ok' | 'gone' | 'error: ...'."""
    from pywebpush import webpush, WebPushException
    key = _vapid()          # outside the try: a problem on OUR side must never read as "this subscription is broken"
    try:
        webpush({"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
                data=json.dumps(data, ensure_ascii=False), vapid_private_key=key, vapid_claims={"sub": SUBJECT},
                ttl=ttl, headers={"Urgency": urgency}, timeout=10, requests_session=session)
        return "ok"
    except WebPushException as e:
        code = getattr(e.response, "status_code", None)
        if code is None and "encrypt" in str(e).lower():
            return "gone"               # keys that cannot encrypt: a fake or broken subscription, never deliverable
        return "gone" if code in (404, 410) else f"error: HTTP {code}: {str(e)[:120]}"
    except (ValueError, TypeError):     # p256dh not a P-256 point / auth malformed: encryption fails before any request
        return "gone"
    except Exception as e:              # network trouble: keep the subscription
        return f"error: {type(e).__name__}: {str(e)[:120]}"


def _conditional_failed(table, ex):
    exc = getattr(getattr(getattr(table, "meta", None), "client", None), "exceptions", None)
    cls = getattr(exc, "ConditionalCheckFailedException", None)
    return (cls is not None and isinstance(ex, cls)) or "ConditionalCheckFailed" in type(ex).__name__ + str(ex)


def _put_new(table, item):
    try:
        table.put_item(Item=item, ConditionExpression="attribute_not_exists(pk)")
        return True
    except Exception as ex:
        if _conditional_failed(table, ex):
            return False
        raise


def _claims(table, match):
    """Every claim of the match (a strongly consistent read: a claim written a moment ago by another sender counts)."""
    from boto3.dynamodb.conditions import Key
    items, kw = [], {"KeyConditionExpression": Key("pk").eq(f"TIFOPUSHSENT#{match}"), "ConsistentRead": True}
    while True:
        r = table.query(**kw)
        items += r.get("Items") or []
        if not r.get("LastEvaluatedKey"):
            return items
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]


_CLAIM = re.compile(r"^(goal|video):(\d+)-(\d+)(?:#(\d+))?$")


def _scored(item, kind):
    """A claim of `kind` with a score: (home, away, total minute or None, generation)."""
    sk = str(item.get("sk") or "")
    m = _CLAIM.match(sk)
    if m and m.group(1) == kind:
        mn = item.get("min")
        return int(m.group(2)), int(m.group(3)), (int(mn) if mn is not None else None), int(m.group(4) or 1)
    m = _MARK_OLD.match(sk) if kind == "goal" else None     # claims written before 2026-10-06: goal:<match>-<side>-<min>-<h>-<a>
    if m:
        return int(m.group(3)), int(m.group(4)), int(m.group(1)) + int(m.group(2) or 0), 1
    return None


def claim(table, match, key, minute=None, now=None, again=False):
    """At most once per event: -> the key claimed, or None when that event is claimed already. Written before anything is
    sent. A score already claimed is the same goal (a minute correction, a scorer filled in, a retry, a second planner),
    unless the job says the poller saw the first one taken back (`again`) and every claim at that score is more than
    SAME_GOAL_SPREAD minutes away: then it is a second goal, «goal:2-1#2». Videos have no second generation."""
    now = int(now if now is not None else time.time())

    def item(k):
        it = {"pk": f"TIFOPUSHSENT#{match}", "sk": k, "at": now, "ttl": now + CLAIM_DAYS * 86400}
        if minute is not None:
            it["min"] = int(minute)
        return it
    m = _CLAIM.match(key)
    if not m:                                   # start, end
        return key if _put_new(table, item(key)) else None
    kind, h, a = m.group(1), int(m.group(2)), int(m.group(3))
    base = f"{kind}:{h}-{a}"
    for _ in range(4):                          # a concurrent sender can take the generation we chose: look again
        same = [s for s in (_scored(c, kind) for c in _claims(table, match)) if s and (s[0], s[1]) == (h, a)]
        if same and (kind != "goal" or not again or minute is None
                     or any(s[2] is None or abs(s[2] - int(minute)) <= SAME_GOAL_SPREAD for s in same)):
            return None
        gen = max((s[3] for s in same), default=0) + 1
        k = base if gen == 1 else f"{base}#{gen}"
        if _put_new(table, item(k)):
            return k
    return None


def cap_ok(table, sk, day, cap=PLAYER_DAILY_CAP):
    """One more player alert for this device today? A conditional counter TIFOPUSHCAP#<device>/<UAE day>, kept 3 days."""
    try:
        table.update_item(Key={"pk": f"TIFOPUSHCAP#{sk}", "sk": day}, UpdateExpression="ADD n :one SET #t = :ttl",
                          ConditionExpression="attribute_not_exists(n) OR n < :cap", ExpressionAttributeNames={"#t": "ttl"},
                          ExpressionAttributeValues={":one": 1, ":cap": cap, ":ttl": int(time.time()) + 3 * 86400})
        return True
    except Exception as ex:
        if _conditional_failed(table, ex):
            return False
        # anything else (2026-10-09: AccessDenied on UpdateItem) must never stop the send: the event is claimed already, so
        # raising here loses it for every audience in the job; a missed count costs at most one alert over the cap
        print(json.dumps({"cap_error": f"{type(ex).__name__}: {str(ex)[:160]}"}))
        return True


_GUIDE = {}


def _guide_channel(cc, match):
    """The channel showing `match` in country `cc` (v1/guide/<CC>.json, the «وين أشوف» pages), or None: no row, no guess.
    One read per country per sender container."""
    cc = str(cc or "").upper()
    if len(cc) != 2:
        return None
    if cc not in _GUIDE:
        try:
            import gzip, urllib.request
            with urllib.request.urlopen(f"{DATA}/guide/{cc}.json", timeout=8) as r:
                raw = r.read()
            _GUIDE[cc] = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
        except Exception:
            _GUIDE[cc] = {}
    row = next((m for m in _GUIDE[cc].get("matches") or [] if str(m.get("match")) == str(match)), None)
    if not row or not row.get("channel_known"):
        return None
    return ((row.get("broadcasters") or [{}])[0] or {}).get("name_ar") or None


def _subs(table, team):
    from boto3.dynamodb.conditions import Key
    items, kw = [], {"KeyConditionExpression": Key("pk").eq(f"TIFOPUSH#{team}")}
    while True:
        r = table.query(**kw)
        items += r.get("Items") or []
        if not r.get("LastEvaluatedKey"):
            return items
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def _arity(fn):
    import inspect
    try:
        return len(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        return 3


def run_jobs(jobs, table, send=None, subs_override=None, now=None):
    """Pure enough to test: table needs put_item/delete_item/query; send(sub, data, urgency[, ttl]) -> status."""
    if send is None:
        import requests
        sess = requests.Session()
        send = lambda s, d, u, ttl=600: _send_one(s, d, u, sess, ttl)          # noqa: E731
    with_ttl = _arity(send) >= 4
    report = []
    n = 0
    t = time.time() if now is None else now
    for job in jobs:
        kind = job.get("kind")
        if kind not in EVENTS:
            report.append({"key": job.get("key"), "match": job.get("match"), "skipped": "unknown kind"})
            continue
        if job.get("exp") and t > job["exp"]:
            report.append({"key": job["key"], "match": job["match"], "skipped": "expired"})
            continue
        got = claim(table, job["match"], job["key"], job.get("min"), t, bool(job.get("again")))
        if not got:
            report.append({"key": job["key"], "match": job["match"], "skipped": "already sent"})
            continue
        done_eps, stats = set(), {"ok": 0, "gone": 0, "error": 0, "quiet": 0}
        day = time.strftime("%Y-%m-%d", time.gmtime(t + 4 * 3600))                  # the UAE day of the per-device cap
        # player audiences first: a device that follows the team AND the scorer gets the player's text, once
        for team, data in sorted(job["payloads"].items(), key=lambda kv: not str(kv[0]).startswith("P")):
            k = data.get("kind") or kind
            is_player = str(team).startswith("P")
            subs = subs_override if subs_override is not None else _subs(table, team)
            for s in subs:
                if not wants(s, k) or s["endpoint"] in done_eps:
                    continue
                if in_quiet(s, t):
                    done_eps.add(s["endpoint"])
                    stats["quiet"] += 1
                    continue
                if n >= MAX_SENDS:
                    break
                if is_player and subs_override is None and not cap_ok(table, s["sk"], day):
                    stats["capped"] = stats.get("capped", 0) + 1
                    continue
                done_eps.add(s["endpoint"])
                out = data
                if k == "soon" and s.get("cc"):
                    ch = _guide_channel(s["cc"], job["match"])
                    out = dict(data, body=f"{data['body']} · {ch}") if ch else data
                r = send(s, out, job["urgency"], JOB_TTL.get(k, 600)) if with_ttl else send(s, out, job["urgency"])
                n += 1
                if r == "ok":
                    stats["ok"] += 1
                elif r == "gone":
                    stats["gone"] += 1
                    if subs_override is None:
                        table.delete_item(Key={"pk": s["pk"], "sk": s["sk"]})
                else:
                    stats["error"] += 1
                    print(json.dumps({"push_error": r, "endpoint_host": s["endpoint"].split("/")[2], "match": job["match"]}))
        report.append({"key": got, "match": job["match"], **stats})
    return report


def handler(event, context):
    import boto3
    table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE)
    _vapid()                # fail before any event is claimed if the key cannot be loaded
    res = run_jobs(event.get("jobs") or [], table, subs_override=event.get("test_subscriptions"))
    print(json.dumps({"push": res}, ensure_ascii=False))
    return res


# ------------------------------------------------------------------ /v1/push.json
def publish_key(p):
    """Needs ssm:GetParameter on the public key for the analytics role (VAPID_PUBLIC_PARAM set in its environment)."""
    if not os.environ.get("VAPID_PUBLIC_PARAM"):
        return
    import boto3
    key = boto3.client("ssm", region_name=REGION).get_parameter(
        Name=os.environ.get("VAPID_PUBLIC_PARAM", "/elyoxe/tifo/vapid_public"))["Parameter"]["Value"]
    p.store.put_json("push.json", {"publicKey": key, "events": list(EVENTS), "default": list(DEFAULT_EVENTS),
                                   "subscribe": "/api/tifo/push/sub"}, cache="static")
    p.store.ok("push-key")
