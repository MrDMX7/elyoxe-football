"""«الأكثر قراءة» (docs/superpowers/specs/2026-11-19-articles-pages-design.md §5): v1/news/top.json, the 10 most read Tifo
articles of the last 24 hours, written by the fast «Article pages» step every journal run.

The visit counter (saas/cards /api/tifo/hit) adds one to TIFOHIT#<UAE day> / ART#<id> for each visit to /news/<id>/. The last
24 hours are today's counts plus yesterday's weighed by the share of yesterday still inside them. Only articles in
v1/news/articles.json count (a withdrawn one leaves the list). Before the first count the file is empty and the pages show
nothing."""
from datetime import datetime, timedelta, timezone

UAE = timezone(timedelta(hours=4))
N = 10


def days(now):
    """(today, yesterday, the share of yesterday inside the last 24 hours), UAE days."""
    t = now.astimezone(UAE)
    gone = (t.hour * 60 + t.minute) / 1440
    return t.date().isoformat(), (t.date() - timedelta(days=1)).isoformat(), round(1 - gone, 4)


def rank(today, yday, frac, lst, n=N):
    by = {a["id"]: a for a in lst}
    score = {}
    for i, c in today.items():
        score[i] = score.get(i, 0) + c
    for i, c in yday.items():
        score[i] = score.get(i, 0) + c * frac
    ids = sorted((i for i, v in score.items() if i in by and round(v) > 0), key=lambda i: (-score[i], i))[:n]
    return [{"id": i, "headline": by[i].get("headline") or "", "image": (by[i].get("image") or {}).get("url"), "n": round(score[i]),
             "kind": by[i].get("kind"), "topic": by[i].get("topic"), "breaking": bool(by[i].get("breaking"))} for i in ids]


def counts(table, day):
    from boto3.dynamodb.conditions import Key
    out, kw = {}, {"KeyConditionExpression": Key("pk").eq(f"TIFOHIT#{day}") & Key("sk").begins_with("ART#")}
    while True:
        r = table.query(**kw)
        for it in r.get("Items") or []:
            out[it["sk"][4:]] = int(it.get("n") or 0)
        if not r.get("LastEvaluatedKey"):
            return out
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def write(store, table, now=None):
    now = now or datetime.now(timezone.utc)
    today, yday, frac = days(now)
    lst = (store.get_json("news/articles.json") or {}).get("articles") or []
    top = rank(counts(table, today), counts(table, yday), frac, lst)
    store.put_json("news/top.json", {"generated": now.isoformat(), "articles": top}, cache="hot")
    return len(top)
