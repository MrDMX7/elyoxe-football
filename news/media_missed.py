"""Tifo's goals that ended without a clip of their own, the official posts that looked like each, and why the matcher turned
each down (owner 2026-11-19: Al Ain's 43' and 54' had clips on X that were all rejected, and only he noticed). media.step calls
build() every run with its trace and keeps the result in state news/media-missed.json; the 08:00 daily email
(automation/cost-report/report.py) lists the previous Dubai day's.

{"generated": iso, "days": {"2026-11-19": {"<match id>": {"home", "away", "score", "comp", "kickoff", "goals", "with_clip",
 "missed": [{"key", "minute", "scorer", "cands": [{"ch", "url", "title", "at", "why", "why_ar"}]}]}}}}

A post is a goal's candidate when it is about the match (names a side, comes from a side's own channel, or names one of its
scorers), came out between kickoff and 6 h after the final whistle, carries a goal word or names a scorer, is not a summary,
and is not already one of the match's clips. It goes to the goal whose scorer it names, else whose minute it gives, else the
latest goal before it (within 30 min); a post that goes to a goal that has its clip is about that goal and is nobody's
candidate."""
from datetime import timedelta
from news import media as M

MISSED = "news/media-missed.json"
KEEP_D = 8                 # Dubai days kept
FRESH_H = 36               # a match's entry is rebuilt while its posts are still in the matcher's video store (96 h)
LOOK_H = 6                 # a post this long after the final whistle can still be a goal's clip
NEAR_MIN = 30              # a post that names neither scorer nor minute goes to the goal scored up to this long before it
PER_GOAL = 3

# the matcher's reasons, in the owner's words (prefix match, first hit)
WHY_AR = [
    ("unrecognised", "ما عرف اللاعب ولا الهدف من العنوان"),
    ("no goal word", "ما فيه كلمة هدف"),
    ("video made before", "فيديو مرفوع قبل الهدف (صورة متحركة جاهزة)"),
    ("scorer not named", "ما عرف اسم اللاعب"),
    ("goals, one scored", "حسبه مقطع أكثر من هدف"),
    ("names the match's other scorers", "يذكر هدافين ثانيين: حسبه ملخص الأهداف"),
    ("which of his goals", "للاعب أكثر من هدف وما عرف أيهم"),
    ("two scorers named", "يذكر هدافين"),
    ("two matches", "ينطبق على مباراتين"),
    ("no: ", "كلمة تنفي الهدف: "),
    ("skip", "منشور مستبعد: "),
    ("score is not this goal's", "النتيجة بالعنوان مب نتيجة هالهدف"),
    ("minute is not this goal's", "الدقيقة بالعنوان مب دقيقة هالهدف"),
    ("goal number", "رقم الهدف بالعنوان ما يطابق"),
    ("equaliser words", "يقول تعادل والنتيجة مب تعادل"),
    ("penalty words", "يقول ضربة جزاء وهو مب جزاء"),
    ("free kick words", "يقول ضربة حرة وهو جزاء"),
    ("own-goal words", "يقول هدف عكسي وهو مب عكسي"),
    ("the match file may not have that goal yet", "ملف المباراة ما كان فيه الهدف بعد"),
    ("not tied to the match", "ما يربطه بالمباراة شي"),
    ("another team's channel", "قناة فريق ثاني"),
    ("not this channel's competition", "مب من بطولات هالقناة"),
    ("before the goal", "نزل قبل الهدف"),
    ("too late", "نزل متأخر وايد"),
    ("competition channel, long after the goal", "قناة البطولة وبعد الهدف بوقت طويل"),
    ("names another scorer", "يذكر هداف ثاني"),
]


def why_ar(why):
    for k, ar in WHY_AR:
        if why.startswith(k):
            rest = why[len(k):] if k.endswith(": ") else ""
            return ar + rest
    return why


def day_of(md):
    k = M.ptime(md.get("kickoff_utc"))
    return (k + timedelta(hours=4)).strftime("%Y-%m-%d") if k else None


def scorer_ar(names, p):
    pid = str(p.get("id"))
    return (names.players_ar.get(pid) or {}).get("ar") or (names.fm.get("players") or {}).get(pid) or p.get("name")


def used_ids(doc):
    return {c.get("id") for c in (doc or {}).get("highlights") or []} | \
           {c.get("id") for l in ((doc or {}).get("goals") or {}).values() for c in l}


def reason(notes, mid, g, tx, players):
    """The matcher's own word on this post for this goal: its note on the goal, else on the match, else its note that names no
    match, else why it never got that far."""
    mine = [n for n in notes if n["match"] == mid and str(g.get("minute")) + "'" in n["what"] and not isinstance(n["result"], int)]
    mine = mine or [n for n in notes if n["match"] == mid and not isinstance(n["result"], int)]
    mine = mine or [n for n in notes if n["match"] is None]
    if mine:
        r = mine[0]["result"]
        return r if isinstance(r, str) else str(r)
    weak = [n for n in notes if isinstance(n["result"], int) and n["match"] == mid]
    if weak:
        return f"confidence {weak[0]['result']} (under 70)"
    if not tx.goal and not players:
        return "no goal word"
    return "unrecognised"


def build(matches, docs, vids, names, chmap, trace, t):
    """-> {day: {match id (str): entry}} for the finished matches of `matches` kicked off in the last FRESH_H hours."""
    ctx = M.Ctx(matches, names)
    notes = {}
    for n in trace or []:
        notes.setdefault(n["video"], []).append(n)
    done = [md for md in matches if md.get("status") in M.DONE and M.ptime(md.get("kickoff_utc"))
            and t - M.ptime(md["kickoff_utc"]) <= timedelta(hours=FRESH_H)]
    if not done:
        return {}
    texts = []
    for v in vids:
        ch = chmap.get(v.get("ch"))
        t_pub = M.ptime(v.get("at"))
        if not ch or not t_pub:
            continue
        tx = M.Text(v.get("title"), v.get("desc"), ch.get("lang", "en"))
        if tx.hl or tx.neg or tx.women:
            continue
        teams, players = ctx.mentions(tx.al)
        texts.append((v, ch, t_pub, tx, teams, players))
    out = {}
    for md in done:
        mid = md["id"]
        h, a = md["home"]["id"], md["away"]["id"]
        gs = [g for g in ctx.goals[mid] if g.get("lb")]
        doc = docs.get(mid)
        have = M.own_clip_keys(doc) if doc else set()
        used = used_ids(doc)
        k0, end = M.ptime(md["kickoff_utc"]), M.match_end(md) or M.ptime(md["kickoff_utc"]) + timedelta(hours=2)
        scorers = {g["player"]["id"] for g in gs}
        cands = {}
        for v, ch, t_pub, tx, teams, players in texts:
            if v["id"] in used or not (k0 <= t_pub <= end + timedelta(hours=LOOK_H)):
                continue
            own = ch.get("team")
            if ch.get("comps") and md.get("comp") not in ch["comps"] and own not in (h, a):
                continue
            named = {p for p, st in players.items() if st >= 2} & scorers
            if not (h in teams or a in teams or own in (h, a) or named):
                continue
            if not tx.goal and not named:
                continue
            g = None
            if named:
                mine = [x for x in gs if x["player"]["id"] in named and x["lb"] <= t_pub + timedelta(minutes=2)]
                by_min = [x for x in mine if any(abs(mm - int(x.get("minute") or 0)) <= 1 for mm, _ in tx.minutes)]
                g = (by_min or mine or [None])[-1]
            elif tx.minutes:
                by_min = [x for x in gs if any(abs(mm - int(x.get("minute") or 0)) <= 1 for mm, _ in tx.minutes)]
                g = by_min[-1] if len(by_min) == 1 else None
            else:
                before = [x for x in gs if x["lb"] <= t_pub + timedelta(minutes=2)]
                g = before[-1] if before and t_pub - before[-1]["lb"] <= timedelta(minutes=NEAR_MIN) else None
            if not g or M.goal_key(g) in have:
                continue
            why = reason(notes.get(v["id"], []), mid, g, tx, players)
            cands.setdefault(M.goal_key(g), []).append(
                (0 if named else 1, abs((t_pub - g["lb"]).total_seconds()),
                 {"ch": ch.get("name"), "url": v.get("url"), "title": (v.get("title") or "")[:160], "at": v.get("at"), "why": why,
                  "why_ar": why_ar(why)}))
        missed = []
        for g in gs:
            k = M.goal_key(g)
            if k in have:
                continue
            cs = [c for _, _, c in sorted(cands.get(k, []), key=lambda x: x[:2])][:PER_GOAL]
            missed.append({"key": k, "minute": f"{g.get('minute')}{'+' + str(g['added']) if g.get('added') else ''}",
                           "scorer": scorer_ar(names, g["player"]), "type": g.get("type"), "cands": cs})
        sc = md.get("score") or {}
        out.setdefault(day_of(md), {})[str(mid)] = {
            "home": md["home"].get("name_ar") or md["home"].get("name"), "away": md["away"].get("name_ar") or md["away"].get("name"),
            "score": f"{sc.get('home')}-{sc.get('away')}", "comp": md.get("comp"), "kickoff": md.get("kickoff_utc"),
            "goals": len(gs), "with_clip": len([g for g in gs if M.goal_key(g) in have]), "missed": missed}
    return out


def merge(days, new, t):
    """The stored days with this run's entries over them, the days older than KEEP_D gone."""
    out = {d: dict(v) for d, v in (days or {}).items()}
    for d, ms in new.items():
        out.setdefault(d, {}).update(ms)
    cut = (t + timedelta(hours=4) - timedelta(days=KEEP_D)).strftime("%Y-%m-%d")
    return {d: v for d, v in out.items() if d > cut}
