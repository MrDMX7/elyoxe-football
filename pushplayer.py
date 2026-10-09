"""«تابع اللاعب» phase 1 (docs/superpowers/specs/2026-10-09-player-follow-design.md §2 A): the match-time events of the
followed players in one match detail, and their Arabic payloads. Pure: push.plan() calls it with the followed players
(state/push_players.json, written by pushplayers.py) and hands the jobs to the same sender. Goals and assists are not here:
push.plan() adds the scorer's and the assister's audiences to the team goal job itself, so a device that follows both the
team and the scorer gets one push (spec §5)."""
from timeutil import parse_utc

import push as P

KINDS = ("soon", "start11", "squad_out", "subin", "subout", "goal", "assist", "card", "pen", "end", "potm", "video")
DEFAULTS = ("start11", "subin", "goal", "assist", "card", "end")
SOON = (50, 70)                       # «مباراته بعد ساعة»: once, while kickoff is 50-70 minutes away
CARDS = {"yellow": "إنذار لـ{n}", "second_yellow": "طرد! إنذار ثاني لـ{n}", "red": "طرد! بطاقة حمراء لـ{n}"}


def _pid(x):
    return str((x or {}).get("id") or "")


def lineup(full):
    lu = full.get("lineups") or {}
    out = {"start": {}, "bench": {}, "confirmed": lu.get("type") == "standard"}
    for side in ("home", "away"):
        s = lu.get(side) or {}
        for p in s.get("starters") or []:
            out["start"][_pid(p)] = side
        for p in s.get("subs") or []:
            out["bench"][_pid(p)] = side
    return out


def _rating(full, pid):
    lu = full.get("lineups") or {}
    for side in ("home", "away"):
        for p in ((lu.get(side) or {}).get("starters") or []) + ((lu.get(side) or {}).get("subs") or []):
            if _pid(p) == pid:
                return p.get("rating")
    return None


def minutes_played(full, pid, end_minute):
    """Starter: until he went off (or the end); substitute: from when he came on. None when he did not play."""
    L, evs = lineup(full), full.get("events") or []
    on = next((P.total_minute(e.get("minute"), e.get("added")) for e in evs if e.get("type") == "sub" and _pid(e.get("player")) == pid), None)
    off = next((P.total_minute(e.get("minute"), e.get("added")) for e in evs if e.get("type") == "sub" and _pid(e.get("player_out")) == pid), None)
    if pid in L["start"]:
        return int(off if off is not None else end_minute)
    if on is not None:
        return int((off if off is not None else end_minute) - on)
    return None


def _fresh(e, now, now_min):
    if P._age_min(e.get("first_seen"), now) > P.FRESH_MINUTES:
        return False
    mn = P.total_minute(e.get("minute"), e.get("added"))
    return not (now_min is not None and mn is not None and now_min - mn > P.STALE_MINUTES)


def events_for(d, full, followed, sent, now):
    """[(key, kind, pid, event | None, extra)] not in `sent`. followed: {pid: {"club", "national"}}."""
    if not followed:
        return []
    sent, out = set(sent or []), []
    teams = {(d.get("home") or {}).get("id"), (d.get("away") or {}).get("id")} - {None}
    mine = {pid for pid, t in followed.items() if t and ({t.get("club"), t.get("national")} - {None}) & teams}
    st, L = d.get("status"), lineup(full)
    ko = parse_utc(d.get("kickoff_utc"))

    def add(key, kind, pid, e=None, extra=None):
        if key not in sent:
            out.append((key, kind, pid, e, extra or {}))
    if st == "scheduled" and ko:
        to_ko = (ko - now).total_seconds() / 60
        if SOON[0] <= to_ko <= SOON[1]:
            for pid in sorted(mine):
                add(f"p{pid}:soon", "soon", pid)
    near = st == "scheduled" or (st in ("live", "ht") and P._age_min(d.get("kickoff_utc"), now) <= P.KICKOFF_WINDOW)
    if L["confirmed"] and near:
        for pid in sorted(followed):
            if pid in L["start"]:
                add(f"p{pid}:start11", "start11", pid)
            elif pid in mine and pid not in L["bench"]:
                add(f"p{pid}:squad_out", "squad_out", pid)
    evs = full.get("events") or []
    now_min = P._match_minute(d, evs)
    for e in evs:
        t = e.get("type")
        if t not in ("sub", "yellow", "second_yellow", "red", "missed_penalty") or not _fresh(e, now, now_min):
            continue
        pin, pout = _pid(e.get("player")), _pid(e.get("player_out"))
        if t == "sub":
            if pin in followed:
                add(f"p{pin}:subin", "subin", pin, e)
            if pout in followed:
                add(f"p{pout}:subout", "subout", pout, e)
        elif t == "missed_penalty" and pin in followed:
            add(f"p{pin}:pen:{P.total_minute(e.get('minute'), e.get('added'))}", "pen", pin, e)
        elif pin in followed:
            add(f"p{pin}:card:{t}", "card", pin, e)
    if st == "finished" and P._age_min((d.get("periods") or {}).get("gameEnded"), now) <= P.END_WINDOW:
        end_min = max(90, now_min or 90)
        goals = [e for e in evs if e.get("type") in ("goal", "penalty_goal")]
        for pid in sorted(followed):
            m = minutes_played(full, pid, end_min)
            if m is None:
                continue
            add(f"p{pid}:end", "end", pid, None, {"min": m, "r": _rating(full, pid),
                                                   "g": sum(1 for e in goals if _pid(e.get("player")) == pid),
                                                   "a": sum(1 for e in goals if _pid(e.get("assist")) == pid)})
        rated = [(r, pid) for pid in list(L["start"]) + list(L["bench"]) for r in [_rating(full, pid)] if r is not None]
        if rated:
            best = max(rated)[1]
            if best in followed:
                add(f"p{best}:potm", "potm", best, None, {"r": max(rated)[0]})
    return out


GAMES_MIN = ["دقيقة", "دقيقتين", "دقايق", "وحدة"]
GOALS = ["هدف", "هدفين", "أهداف", "واحد"]


def _count(k, w):
    return f"{w[0]} {w[3]}" if k == 1 else w[1] if k == 2 else f"{k} {w[2] if k <= 10 else w[0]}"


def payload(kind, d, pid, e, names_ar, extra):
    """{title, body, url, tag, kind} (+ cc_body for «soon»: the visitor's channel line by country)."""
    mid, h, a = d["id"], P._name(d.get("home")), P._name(d.get("away"))
    n = P.player_ar({"id": pid, "name": (e or {}).get("player", {}).get("name") if _pid((e or {}).get("player")) == pid else ""}, names_ar) \
        or (names_ar.get(pid) or {}).get("ar") or "لاعبك"
    sc = P._score(d.get("score"))
    mn = f"الدقيقة {P._minute(e)}'" if e else ""
    base = {"url": f"/m/{mid}/", "tag": f"p{pid}-{mid}", "kind": kind}
    if kind == "soon":
        line = f"{h} - {a}" + (f" · {d['comp_name_ar']}" if d.get("comp_name_ar") else "")
        cc = {c: f"{line} · {ch}" for c, ch in ((extra or {}).get("cc") or {}).items() if ch}
        return {**base, "title": f"{n} يلعب بعد ساعة", "body": line, **({"cc_body": cc} if cc else {})}
    if kind == "start11":
        return {**base, "title": f"{n} أساسي", "body": f"{h} - {a}"}
    if kind == "squad_out":
        return {**base, "title": f"{n} مب في القائمة", "body": f"{h} - {a}"}
    if kind == "subin":
        return {**base, "title": f"دخل {n}", "body": f"{mn} · {h} {sc} {a}"}
    if kind == "subout":
        hurt = " مصاب" if (e or {}).get("detail") == "injury" else ""
        return {**base, "title": f"طلع {n}{hurt}", "body": f"{mn} · {h} {sc} {a}"}
    if kind == "card":
        return {**base, "title": CARDS.get((e or {}).get("type"), "بطاقة لـ{n}").format(n=n), "body": f"{mn} · {h} {sc} {a}"}
    if kind == "pen":
        return {**base, "title": f"{n} ضيّع ركلة جزاء", "body": f"{mn} · {h} {sc} {a}"}
    if kind == "end":
        x = extra or {}
        did = [s for s in (x.get("g") and "سجّل " + _count(x["g"], GOALS), x.get("a") and "صنع " + _count(x["a"], GOALS)) if s]
        r = f" · تقييمه {x['r']}" if x.get("r") is not None else ""
        return {**base, "url": f"/p/{pid}/#m{mid}", "title": f"انتهت: {h} {sc} {a}",
                "body": f"{n} لعب {_count(int(x.get('min') or 0), GAMES_MIN)}{'، و' + ' و'.join(did) if did else ''}{r}"}
    if kind == "potm":
        r = (extra or {}).get("r")
        return {**base, "url": f"/p/{pid}/#m{mid}", "title": f"{n} أحسن لاعب في المباراة", "body": (f"تقييمه {r} · " if r is not None else "") + f"{h} {sc} {a}"}
    if kind in ("goal", "assist", "video"):          # built by push.py inside the team jobs; here only for completeness
        return {**base, "title": f"{n}", "body": f"{h} {sc} {a}"}
    return {**base, "title": n, "body": f"{h} - {a}"}
