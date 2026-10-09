"""«تابع اللاعب»: the followed players' club and national team, for the poller (state/push_players.json; spec
docs/superpowers/specs/2026-10-09-player-follow-design.md §3.2). Runs after the journal (every 15 min, laptop): the follow
index TIFOFOLLOW (cards /api/tifo/push/sub) -> each player's profile.json -> the map. A transfer moves the follow by itself:
the next run maps his new club.
  python -m pushplayers"""
import gzip, json, os, time, urllib.request

DATA = os.environ.get("TIFO_DATA", "https://d1n5aqaqkowltp.cloudfront.net")
BUCKET = os.environ.get("BUCKET", "elyoxe-football-574771023173-ap-south-1")
NATIONAL_YEARS = 3            # a national team he has not played for in this many years is not «his» any more


def national_of(prof, year=None):
    s = (((prof or {}).get("career") or {}).get("national team") or {}).get("seasons") or []
    if not s or not s[0][1]:
        return None
    try:
        recent = (year or int(time.strftime("%Y"))) - int(str(s[0][0])[:4]) <= NATIONAL_YEARS
    except ValueError:
        return None
    return int(s[0][1]) if recent else None


def build_map(ids, get_profile):
    """{pid: {"club", "national", "cc"}}; cc stays None in phase 1 (the sender reads each subscription's own country)."""
    out = {}
    for pid in ids:
        p = get_profile(pid) or {}
        club = (p.get("bio") or {}).get("team")
        out[pid] = {"club": int(club) if club else None, "national": national_of(p), "cc": None}
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
            return sorted(str(i["sk"])[1:] for i in items if int(i.get("n", 0)) > 0)
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def main():
    import boto3
    from store import Store, S3Backend
    ids = followed_ids(boto3.resource("dynamodb", region_name="ap-south-1").Table("cards"))
    m = build_map(ids, _profile)
    Store(S3Backend(BUCKET)).put_state("push_players.json", m)
    print(json.dumps({"followed": len(ids), "mapped": sum(1 for v in m.values() if v["club"] or v["national"])}))


if __name__ == "__main__":
    main()
