"""The article push (docs/superpowers/specs/2026-11-19-articles-pages-design.md §4): the jobs the fast «Article pages» step
hands to the sender (push.py, Lambda elyoxe-football-push) once the pages are up.

One job per article put up for the first time: a rewrite, an update or a desk edit was put up before and never pushes again.
Its audiences are the article's clubs ("<team>") and players ("P<id>"); the sender claims the job once
(TIFOPUSHSENT#article:<id>), keeps quiet hours and each subscriber's choice, sends one push a device, and at most 3 article
pushes a UAE day per club or player. Only an article published in the last 3 hours, at most 20 a run, «عاجل» first; and none
when the pages state is empty, so a first run never pushes the backlog."""
from datetime import datetime, timedelta

FRESH = timedelta(hours=3)
MAX_RUN = 20
BODY = 120
TTL = 3 * 3600          # push.JOB_TTL["article"]


def cut(s, n=BODY):
    s = " ".join(str(s or "").split())
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0].rstrip("،,.؛:") + "…"


def jobs(docs, known, now):
    """docs: the article docs this run put up; known: {id: modified} of the pages put up before it."""
    if not known:
        return []
    out = []
    for d in docs:
        if d["id"] in known:
            continue
        try:
            age = now - datetime.fromisoformat(d["published"])
        except (KeyError, TypeError, ValueError):
            continue
        if age > FRESH:
            continue
        base = {"title": d.get("headline") or "", "body": cut(d.get("standfirst")), "url": f"/news/{d['id']}/",
                "tag": f"art-{d['id']}", "kind": "article"}
        pay = {}
        for kind, i in d.get("entities") or []:
            if kind == "team":
                pay[str(i)] = dict(base, team=int(i))
            elif kind == "player":
                pay[f"P{i}"] = dict(base)
        if pay:
            out.append((not d.get("breaking"), -datetime.fromisoformat(d["published"]).timestamp(),
                        {"match": f"article:{d['id']}", "key": "article", "kind": "article",
                         "urgency": "high" if d.get("breaking") else "normal", "exp": int(now.timestamp()) + TTL,
                         "payloads": pay}))
    return [j for *_, j in sorted(out, key=lambda x: x[:2])][:MAX_RUN]
