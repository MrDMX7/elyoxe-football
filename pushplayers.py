"""«تابع اللاعب»: the followed players' club and national team, for the poller (state/push_players.json; spec
docs/superpowers/specs/2026-10-09-player-follow-design.md §3.2). Runs after the journal (every 15 min, laptop): the follow
index TIFOFOLLOW (cards /api/tifo/push/sub) -> each player's profile.json -> the map. A transfer moves the follow by itself:
the next run maps his new club.
  python -m pushplayers"""
import gzip, json, os, time, urllib.request

DATA = os.environ.get("TIFO_DATA", "https://d1n5aqaqkowltp.cloudfront.net")
BUCKET = os.environ.get("BUCKET", "elyoxe-football-574771023173-ap-south-1")
NATIONAL_YEARS = 3            # a national team he has not played for in this many years is not «his» any more
FRESH_S = 24 * 3600           # a mapped player is read again after a day (a transfer moves the follow within a day)
BUDGET = 300                  # profiles read per run: a flood of follows cannot turn a 15-minute job into thousands of requests


def national_of(prof, year=None):
    s = (((prof or {}).get("career") or {}).get("national team") or {}).get("seasons") or []
    if not s or not s[0][1]:
        return None
    try:
        recent = (year or int(time.strftime("%Y"))) - int(str(s[0][0])[:4]) <= NATIONAL_YEARS
    except ValueError:
        return None
    return int(s[0][1]) if recent else None


def build_map(ids, get_profile, prev=None, budget=BUDGET, now=None):
    """{pid: {"club", "national", "cc", "at"}} for `ids` only. Read: the never-mapped first, then the oldest past FRESH_S,
    `budget` a run; the rest keep their previous entry (or wait, unmapped, for the next run). cc stays None in phase 1."""
    prev, now = prev or {}, now if now is not None else time.time()
    due = sorted((pid for pid in ids if pid not in prev or now - (prev[pid].get("at") or 0) > FRESH_S),
                 key=lambda pid: (pid in prev, (prev.get(pid) or {}).get("at") or 0))[:budget]
    out = {pid: prev[pid] for pid in ids if pid in prev}
    for pid in due:
        p = get_profile(pid) or {}
        club = (p.get("bio") or {}).get("team")
        out[pid] = {"club": int(club) if club else None, "national": national_of(p), "cc": None, "at": int(now)}
    return out


def _profile(pid):
    try:
        with urllib.request.urlopen(f"{DATA}/player/{pid}/profile.json", timeout=20) as r:
            raw = r.read()
        return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    except Exception:
        return None


def followed_ids(table):
    from boto3.dynamodb.conditions import Key
    items, kw = [], {"KeyConditionExpression": Key("pk").eq("TIFOFOLLOW")}
    while True:
        r = table.query(**kw)
        items += r.get("Items") or []
        if not r.get("LastEvaluatedKey"):
            break
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]
    # the index counts follows but not subscriptions that expired (DynamoDB TTL): keep a player only while one exists
    ids = sorted(str(i["sk"])[1:] for i in items if int(i.get("n", 0)) > 0)
    return [pid for pid in ids if (table.query(KeyConditionExpression=Key("pk").eq(f"TIFOPUSH#P{pid}"), Limit=1).get("Items"))]


def main():
    import boto3
    from store import Store, S3Backend
    ids = followed_ids(boto3.resource("dynamodb", region_name="ap-south-1").Table("cards"))
    store = Store(S3Backend(BUCKET))
    m = build_map(ids, _profile, prev=store.get_state("push_players.json", {}) or {})
    store.put_state("push_players.json", m)
    print(json.dumps({"followed": len(ids), "mapped": sum(1 for v in m.values() if v["club"] or v["national"])}))


if __name__ == "__main__":
    main()
