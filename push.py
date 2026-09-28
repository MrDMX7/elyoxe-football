"""Per-team web push (item approved 2026-09-28): kickoff, goal and full-time notifications.

Two halves:
  * `plan(p, d, full)` runs inside the poller's fetch_detail (live and final details). It decides which events are
    new for this match (kickoff, each goal event, full time), builds one Arabic payload per team and hands them to
    the sender with ONE asynchronous Lambda invoke, so the poller never waits on push services.
  * `handler(event, ctx)` is the sender (Lambda elyoxe-football-push): for each team it queries the subscriptions
    (DynamoDB `cards`, pk TIFOPUSH#<team>, written by the cards stack's /api/tifo/push/sub), claims the
    (match, event) mark with a conditional put (so a retried invoke or a second poller pass never sends twice),
    and sends with pywebpush + the VAPID key from SSM. 404/410 from a push service deletes the subscription;
    any other error is logged and skipped.

Dedupe has two layers: `push_sent` in poller.json (no invoke at all for an event already handed over) and the
conditional TIFOPUSHSENT#<match> / <event key> item in DynamoDB (at-most-once per event, across retries).
A goal the VAR took back before we saw it is never sent: only goal events present in the current detail, with no
later "goal disallowed" VAR decision for that side, are pushed. Old events (first seen > 10 min ago, e.g. after a
deploy or a backfill) are not pushed.
"""
import json, os, time

TABLE = os.environ.get("PUSH_TABLE", "cards")
REGION = os.environ.get("PUSH_REGION", "ap-south-1")
SUBJECT = "mailto:hello@elyoxe.com"
FRESH_MINUTES = 10            # a goal first seen longer ago than this is history, not news
KICKOFF_WINDOW = 20           # minutes after kickoff within which a "start" push still makes sense
END_WINDOW = 60               # minutes after full time
GOAL_TYPES = ("goal", "own_goal", "penalty_goal")
DISALLOWED = ("goal_disallowed", "goal_disallowed_offside")
MAX_SENDS = 5000              # per invoke: the sender's 5-minute budget, ~40 ms per send with a pooled session


# ------------------------------------------------------------------ payloads (pure, tested)
def _name(t):
    return (t or {}).get("name_ar") or (t or {}).get("name") or ""


def _minute(e):
    m, a = e.get("minute"), e.get("added")
    return f"{m}+{a}" if a else f"{m}"


def _score(sc):
    return f"{sc['home']} - {sc['away']}" if sc else "-"


# FotMob sends a goal first with the scorer as «<TBD>» (player id 0) and fills the name about a minute later.
# Seen live 2026-09-28 on 6040346: the first push read «سجّل <TBD>», and the named event got a new event_id
# (…-goal-38-0-0 -> …-goal-38-0-854041), so the same goal was pushed twice.
PLACEHOLDERS = ("", "<tbd>", "tbd", "unknown")


def _known(pl):
    return bool(pl and pl.get("id") and str(pl.get("name") or "").strip().lower() not in PLACEHOLDERS)


def goal_key(mid, e):
    """A goal's identity without its scorer: team, minute and the score it made."""
    sc = e.get("score") or {}
    return f"goal:{mid}-{e.get('team')}-{_minute(e)}-{sc.get('home')}-{sc.get('away')}"


def player_ar(pl, names_ar):
    if not _known(pl):
        return None
    x = (names_ar or {}).get(str(pl.get("id")))
    return (x or {}).get("ar") if isinstance(x, dict) else x or pl.get("name")


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
    return {**base, "title": f"هدف! {h} {_score(sc)} {a}", "body": body}


# ------------------------------------------------------------------ which events are new (pure, tested)
def _age_min(ts, now):
    from timeutil import parse_utc
    t = parse_utc(ts) if ts else None
    return 1e9 if t is None else (now - t).total_seconds() / 60


def events_to_send(d, full, sent, now):
    """[(key, kind, event|None)] for this detail, minus keys already in `sent`."""
    out = []
    st = d.get("status")
    periods = d.get("periods") or {}
    if st in ("live", "ht") and "start" not in sent:
        started = periods.get("firstHalfStarted") or d.get("kickoff_utc")
        if _age_min(started, now) <= KICKOFF_WINDOW:
            out.append(("start", "start", None))
    evs = full.get("events") or []
    var = [e for e in evs if e.get("type") == "var" and e.get("var_outcome") in DISALLOWED]
    for e in evs:
        if e.get("type") not in GOAL_TYPES or not e.get("event_id"):
            continue
        key = goal_key(d.get("id"), e)
        # marks written before goal_key used the event_id, which ends in the player id: match it without that
        stem = f"goal:{e['event_id']}".rsplit("-", 1)[0] + "-"
        if key in sent or any(k.startswith(stem) for k in sent):
            continue
        if _age_min(e.get("first_seen"), now) > FRESH_MINUTES:
            continue
        if any(v.get("team") == e.get("team") and (v.get("minute") or 0) >= (e.get("minute") or 0) for v in var):
            continue            # the VAR took it back
        out.append((key, "goal", e))
    if st == "finished" and "end" not in sent:
        ended = periods.get("gameEnded") or periods.get("secondHalfEnded")
        if _age_min(ended, now) <= END_WINDOW:
            out.append(("end", "end", None))
    return out


def plan(p, d, full, invoke=None):
    """Called from Poller.fetch_detail. Marks and hands over new events; never raises into the poller."""
    if not os.environ.get("PUSH_FUNCTION") and invoke is None:
        return []
    mid = str(d["id"])
    sent_all = p.st.setdefault("push_sent", {})
    sent = sent_all.setdefault(mid, {"at": None, "keys": []})
    todo = events_to_send(d, full, set(sent["keys"]), p.now())
    if not todo:
        return []
    names_ar = _names_ar()
    teams = [t for t in ((d.get("home") or {}).get("id"), (d.get("away") or {}).get("id")) if t]
    jobs = []
    for key, kind, e in todo:
        jobs.append({"match": int(mid), "key": key, "kind": kind, "urgency": "high" if kind == "goal" else "normal",
                     "payloads": {str(t): payload(kind, d, t, e, names_ar) for t in teams}})
    try:
        (invoke or _invoke)({"jobs": jobs})
    except Exception as ex:          # not marked: the next pass tries again (the sender dedupes)
        p.store.fail("push", f"{mid}: invoke failed: {type(ex).__name__}: {ex}")
        return []
    sent["keys"] += [j["key"] for j in jobs]
    sent["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for k in [k for k, v in sent_all.items() if v.get("at") and _age_min(v["at"], p.now()) > 3 * 1440]:
        del sent_all[k]
    p.note(f"push: {mid} {', '.join(j['key'] for j in jobs)}")
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


def _invoke(event):
    import boto3
    boto3.client("lambda", region_name=REGION).invoke(FunctionName=os.environ["PUSH_FUNCTION"], InvocationType="Event",
                                                     Payload=json.dumps(event, ensure_ascii=False).encode())


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


def _send_one(sub, data, urgency, session=None):
    """-> 'ok' | 'gone' | 'error: ...'."""
    from pywebpush import webpush, WebPushException
    key = _vapid()          # outside the try: a problem on OUR side must never read as "this subscription is broken"
    try:
        webpush({"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
                data=json.dumps(data, ensure_ascii=False), vapid_private_key=key, vapid_claims={"sub": SUBJECT},
                ttl=600, headers={"Urgency": urgency}, timeout=10, requests_session=session)
        return "ok"
    except WebPushException as e:
        code = getattr(e.response, "status_code", None)
        if code is None and "encrypt" in str(e).lower():
            return "gone"               # keys that cannot encrypt: a fake or broken subscription, never deliverable
        return "gone" if code in (404, 410) else f"error: HTTP {code}: {str(e)[:120]}"
    except (ValueError, TypeError) as e:  # p256dh not a P-256 point / auth malformed: encryption fails before any request
        return "gone"
    except Exception as e:              # network trouble: keep the subscription
        return f"error: {type(e).__name__}: {str(e)[:120]}"


def _claim(table, match, key):
    """At-most-once per (match, event): a conditional put that a retried or duplicate invoke loses."""
    try:
        table.put_item(Item={"pk": f"TIFOPUSHSENT#{match}", "sk": key, "ttl": int(time.time()) + 3 * 86400},
                       ConditionExpression="attribute_not_exists(pk)")
        return True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return False


def _subs(table, team):
    from boto3.dynamodb.conditions import Key
    items, kw = [], {"KeyConditionExpression": Key("pk").eq(f"TIFOPUSH#{team}")}
    while True:
        r = table.query(**kw)
        items += r.get("Items") or []
        if not r.get("LastEvaluatedKey"):
            return items
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def run_jobs(jobs, table, send=None, subs_override=None):
    """Pure enough to test: table needs put_item/delete_item/query; send(sub, data, urgency) -> status."""
    import requests
    send = send or (lambda s, d, u, _sess=requests.Session(): _send_one(s, d, u, _sess))
    report = []
    n = 0
    for job in jobs:
        if not _claim(table, job["match"], job["key"]):
            report.append({"key": job["key"], "match": job["match"], "skipped": "already sent"})
            continue
        done_eps, stats = set(), {"ok": 0, "gone": 0, "error": 0}
        for team, data in job["payloads"].items():
            subs = subs_override if subs_override is not None else _subs(table, team)
            for s in subs:
                if job["kind"] not in (s.get("events") or ("start", "goal", "end")) or s["endpoint"] in done_eps:
                    continue
                if n >= MAX_SENDS:
                    break
                done_eps.add(s["endpoint"])
                r = send(s, data, job["urgency"])
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
        report.append({"key": job["key"], "match": job["match"], **stats})
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
    p.store.put_json("push.json", {"publicKey": key, "events": ["start", "goal", "end"],
                                   "subscribe": "/api/tifo/push/sub"}, cache="static")
    p.store.ok("push-key")
