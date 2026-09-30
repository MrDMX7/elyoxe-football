"""How a goal was scored, in short Gulf Arabic (owner 2026-09-30: «اريد الهدف اللي يتسجل من اليوم ورايح ينكتب عداله كيف
اتسجل، من رأسية ولا ضربة حرة ولا دبل كيك…»).

Stdlib only: the poller bundles it (compute/ is copied whole) and saas/cards vendors an identical copy for
/api/tifo/match. Keep the two files the same (tests/test_goal_how.py checks the copy when it sits next to this repo).

Evidence, strongest first (study of 410 FotMob matches / 1,314 goals played 2026-09-12..29):
  1. the goal event (matchFacts.events.events[], type Goal): goalDescriptionKey is set on ~12 % of goals and only ever
     said penalty (102), owngoal (31), header (19) or direct_free_kick (1); ownGoal is a flag of its own;
  2. its shotmapEvent (FotMob "xG" coverage only, 639 of the 1,314 goals): shotType RightFoot | LeftFoot | Header |
     OtherBodyParts; situation RegularPlay | FromCorner | FastBreak | SetPiece | ThrowInSetPiece | FreeKick | Penalty |
     IndividualPlay; x/y on a 105 x 68 pitch with the goal at x = 105, y = 34 (penalties are shot from 94, 34);
     isFromInsideBox;
  3. the English live ticker (data.fotmob.com/webcl/ltc/gsm/<match>_<lang>.json.gz; content.liveticker.langs lists them):
       en_gen = Opta's auto commentary, a fixed template («X (Team) left footed shot from outside the box to the bottom
                right corner. Assisted by Y following a fast break.»), read in full: foot or header, place, situation.
                It is what the "ratings" coverage matches have instead of a shot map;
       en     = human commentary (big matches, national teams): free text, trusted only for what a shot map cannot show
                (volley, bicycle kick, chip, backheel, scorpion, diving header, a direct free kick) and only in a sentence
                that names the scorer BEFORE the word (so a saved volley before a tap-in is not the scorer's volley).
     ar_gen is a machine translation of `en` and adds nothing.

describe() -> {"key": "header+corner", "ar": "رأسية من ركنية"}, or None when nothing is known (most lower-league goals:
FotMob has neither a shot map nor a ticker for them).
key = technique [+ foot for a volley] [+ place] [+ situation]
  technique  own_goal penalty free_kick bicycle scorpion backheel volley chip diving_header header right_foot left_foot
             other_body shot
  place      close (<= 5.5 m: the six-yard box) outside (outside the box) long (25 m or more) angle (difficult angle)
  situation  corner fast_break set_piece throw_in solo
"""
import math
import re
import unicodedata

GOAL_X, GOAL_Y = 105.0, 34.0
LONG_M, CLOSE_M = 25.0, 5.5

TECH_AR = {
    "own_goal": "هدف عكسي", "penalty": "ضربة جزاء", "free_kick": "ضربة حرة مباشرة", "bicycle": "دبل كيك",
    "scorpion": "ضربة العقرب", "backheel": "بالكعب", "chip": "لوب", "diving_header": "رأسية طايرة", "header": "رأسية",
    "right_foot": "تسديدة باليمين", "left_foot": "تسديدة باليسار", "other_body": "بجسمه", "shot": "تسديدة",
    "volley": "طايرة",
}
VOLLEY_AR = {"right_foot": "طايرة باليمين", "left_foot": "طايرة باليسار"}
PLACE_AR = {"close": "من قريب", "outside": "من برا المنطقة", "long": "من بعيد", "angle": "من زاوية صعبة"}
SIT_AR = {"corner": "من ركنية", "fast_break": "من هجمة مرتدة", "set_piece": "من كرة ثابتة", "throw_in": "من رمية تماس",
          "solo": "مجهود فردي"}
SIT_AFTER = {"corner": "بعد ركنية", "fast_break": "بعد هجمة مرتدة", "set_piece": "بعد كرة ثابتة", "throw_in": "بعد رمية تماس"}
SHOT_BODY = {"RightFoot": "right_foot", "LeftFoot": "left_foot", "Header": "header", "OtherBodyParts": "other_body"}
SHOT_SIT = {"FromCorner": "corner", "FastBreak": "fast_break", "SetPiece": "set_piece", "ThrowInSetPiece": "throw_in",
            "IndividualPlay": "solo"}
# goalDescriptionKey values seen (penalty, owngoal, header, direct_free_kick) + a few FotMob may add, mapped defensively
KEY_TECH = {"header": "header", "direct_free_kick": "free_kick", "free_kick": "free_kick", "volley": "volley",
            "bicycle_kick": "bicycle", "overhead_kick": "bicycle", "chip": "chip", "lob": "chip", "backheel": "backheel"}
FOOT = ("right_foot", "left_foot")
RARE = ("volley", "chip", "backheel", "bicycle", "scorpion")

# ---- Opta auto commentary (en_gen)
_A_OWN = re.compile(r"\bown goal by\b", re.I)
_A_PEN = re.compile(r"converts the penalty with a (right|left) footed shot", re.I)
_A_FK = re.compile(r"from a (?:direct )?free kick with a (right|left) footed shot", re.I)
_A_SHOT = re.compile(r"\)\s+(right footed shot|left footed shot|header|shot)\s+from\s+(.+?)\s+to\s+(?:the\s+)?", re.I)
_A_SIT = [(re.compile(r"following a corner", re.I), "corner"), (re.compile(r"following a fast break", re.I), "fast_break"),
          (re.compile(r"following a set piece situation", re.I), "set_piece"),
          (re.compile(r"following a throw[- ]in", re.I), "throw_in")]

# ---- human commentary (en)
_H_TECH = [
    ("bicycle", r"\b(?:bicycle|overhead|scissors?)[- ]kick"),
    ("scorpion", r"\bscorpion\b"),
    ("backheel", r"\bback-?heel(?:s|ed)?\b|\bwith (?:his|her|the) heel\b"),
    ("diving_header", r"\bdiving header\b"),
    ("volley", r"\b(?:half-)?volley(?:s|ed)?\b"),
    ("chip", r"\b(?:chip(?:s|ped)?|lob(?:s|bed)?|dink(?:s|ed)?)\b(?! in with)|\bloops? (?:an effort|the ball|it|a finish) over\b"),
    ("free_kick", r"\bfree[- ]kick\b"),
]
_H_TECH = [(t, re.compile(p, re.I), p) for t, p in _H_TECH]
_H_LONG = re.compile(r"\b(?:2[5-9]|[34]\d)[- ]yards?\b|\blong[- ]range\b|\bfrom distance\b", re.I)
_SENT = re.compile(r"(?<=[.!?])\s+")


def _fold(s):
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()


def _dist(shot):
    try:
        return math.hypot(GOAL_X - float(shot["x"]), GOAL_Y - float(shot["y"]))
    except (KeyError, TypeError, ValueError):
        return None


def _names(ev):
    """Tokens the commentary uses for the scorer: his last name as FotMob writes it and the last word of his name."""
    out = []
    full = ev.get("nameStr") or ev.get("fullName") or (ev.get("player") or {}).get("name")
    for v in (_fold(ev.get("lastName")), (_fold(ev.get("lastName")).split() or [""])[-1], (_fold(full).split() or [""])[-1]):
        if v and len(v) >= 3 and v not in out:
            out.append(v)
    return out


def parse_auto(text):
    """Opta auto commentary of one goal -> {tech, foot, place, sit} (the keys it could read)."""
    t = text or ""
    if _A_OWN.search(t):
        return {"tech": "own_goal"}
    m = _A_PEN.search(t)
    if m:
        return {"tech": "penalty", "foot": m.group(1).lower() + "_foot"}
    f = {}
    m = _A_FK.search(t)
    if m:
        f = {"tech": "free_kick", "foot": m.group(1).lower() + "_foot"}
    else:
        m = _A_SHOT.search(t)
        if m:
            body, where = m.group(1).lower(), m.group(2).lower()
            f["tech"] = "header" if body == "header" else "right_foot" if body.startswith("right") else "left_foot" if body.startswith("left") else "shot"
            if "very close range" in where or "six yard box" in where:
                f["place"] = "close"
            elif "outside the box" in where:
                f["place"] = "outside"
            elif "long range" in where or "35 yards" in where:
                f["place"] = "long"
            elif "difficult angle" in where:
                f["place"] = "angle"
    for rx, s in _A_SIT:
        if rx.search(t):
            f["sit"] = s
            break
    return f


def parse_human(text, ev):
    """Human commentary -> {tech, place}: a rare technique or a long-range strike, read only after the scorer's name in the
    same sentence, or as «<technique> by/from <scorer>»."""
    names = _names(ev)
    if not text or not names:
        return {}
    f = {}
    for sent in _SENT.split(text):
        low = _fold(sent)
        for nm in names:
            i = low.find(nm)
            if i < 0:
                continue
            tail = low[i + len(nm):]
            for tech, rx, pat in _H_TECH:
                if "tech" not in f and (rx.search(tail) or re.search("(?:" + pat + r")\s+(?:by|from)\s+(?:\w+\s+)?" + re.escape(nm), low, re.I)):
                    f["tech"] = tech
            if "place" not in f and _H_LONG.search(tail):
                f["place"] = "long"
    return f


def _compose(tech, place=None, sit=None, foot=None):
    if tech in ("own_goal", "penalty"):
        return {"key": tech, "ar": TECH_AR[tech]}
    if tech == "free_kick":
        place = "long" if place == "long" else None
        return {"key": "+".join(x for x in (tech, place) if x), "ar": TECH_AR[tech] + (" " + PLACE_AR[place] if place else "")}
    if tech in ("chip", "bicycle", "scorpion", "backheel") and place == "close":
        place = None
    ar = VOLLEY_AR.get(foot, TECH_AR["volley"]) if tech == "volley" else TECH_AR[tech]
    key = "+".join(x for x in (tech, foot if tech == "volley" else None, place, sit) if x)
    if place:
        ar += " " + PLACE_AR[place]
    if sit == "solo":
        ar += "، " + SIT_AR[sit]
    elif sit:
        ar += " " + (SIT_AFTER[sit] if place else SIT_AR[sit])      # «رأسية من ركنية», «تسديدة باليسار من قريب بعد ركنية»
    return {"key": key, "ar": ar}


def describe(ev, shot=None, text=None, auto=None):
    """ev: a FotMob goal event (raw); shot: its shotmapEvent (default ev["shotmapEvent"]); text: this goal's ticker line;
    auto: True = Opta auto commentary (en_gen), False = human commentary (en). -> {"key", "ar"} or None."""
    if not isinstance(ev, dict) or ev.get("isPenaltyShootoutEvent"):
        return None
    if not isinstance(shot, dict):
        shot = ev.get("shotmapEvent") if isinstance(ev.get("shotmapEvent"), dict) else None
    gk = (ev.get("goalDescriptionKey") or "").lower().strip()
    sk = ev.get("suffixKey") or ""
    if ev.get("ownGoal") or gk == "owngoal" or sk == "own_goal_short" or (shot or {}).get("isOwnGoal"):
        return _compose("own_goal")
    if gk.startswith("penalt") or sk == "penalties_short" or (shot or {}).get("situation") == "Penalty":
        return _compose("penalty")
    tech, body, place, sit, foot = KEY_TECH.get(gk), None, None, None, None
    if shot:
        body = SHOT_BODY.get(shot.get("shotType"))
        if shot.get("situation") == "FreeKick":
            tech = "free_kick"
        sit = SHOT_SIT.get(shot.get("situation"))
        d = _dist(shot)
        if shot.get("isFromInsideBox") is False:
            place = "long" if d is not None and d >= LONG_M else "outside"
        elif d is not None and d <= CLOSE_M and body in FOOT + ("other_body",):
            place = "close"
        if tech is None or (tech == "header" and body not in (None, "header")):
            tech = body                              # the shot's body part wins over a header key it contradicts
    if text and auto:
        a = parse_auto(text)
        if a.get("tech") in ("own_goal", "penalty"):
            return _compose(a["tech"])
        if not shot:                                 # no shot map: the template is the evidence
            if a.get("tech") and tech != "free_kick":
                tech = a["tech"] if not (tech == "header" and a["tech"] in FOOT) else tech
            place, sit = a.get("place"), a.get("sit")
        else:
            sit = sit or a.get("sit")
            place = place or (a.get("place") if a.get("place") == "angle" else None)
    elif text and auto is False:
        h = parse_human(text, ev)
        ht = h.get("tech")
        if ht == "free_kick":
            if not shot or shot.get("situation") == "FreeKick":
                tech = "free_kick"
        elif ht == "diving_header":
            if body in (None, "header") and tech in (None, "header"):
                tech = "diving_header"
        elif ht in RARE and body != "header" and tech not in ("header", "free_kick"):
            if ht == "volley":
                foot = body if body in FOOT else tech if tech in FOOT else None
            tech = ht
        if h.get("place") == "long" and not shot and tech not in (None, "header", "diving_header"):
            place = "long"
    if not tech:
        return None
    return _compose(tech, place, sit, foot)


# ---------------------------------------------------------------- the ticker
def ticker_url(match_id, lang):
    return f"https://data.fotmob.com/webcl/ltc/gsm/{int(match_id)}_{lang}.json.gz"


def ticker_lang(langs):
    """content.liveticker.langs ("de_gen,en_gen,...") -> the English ticker to read ("en_gen" | "en"), or None."""
    ls = [x.strip() for x in str(langs or "").split(",")]
    return "en_gen" if "en_gen" in ls else "en" if "en" in ls else None


def goal_lines(ticker):
    """The ticker's goal entries: [(minute, added or None, code, text)]."""
    out = []
    for e in (ticker or {}).get("Events") or []:
        c = (e.get("IncidentCode") or "").upper()
        d = e.get("Description") or ""
        if c in ("G", "PSG", "OG") or d.startswith("Goal!") or d.startswith("Own Goal"):
            plus = e.get("ElapsedPlus")
            out.append((e.get("Elapsed"), plus if isinstance(plus, int) and plus > 0 else None, c, d))
    return out


def assign(goals, lines):
    """Each goal's ticker entry -> {index in goals: text}. A line is used once. First pass: the scorer's name in the
    text, at the goal's minute or one minute either side (Opta's minute is at times one off FotMob's); second pass: the
    only line left at exactly the goal's minute (a name spelt differently)."""
    out, used = {}, set()
    for i, ev in enumerate(goals):
        t, names = ev.get("time"), _names(ev)
        if not isinstance(t, int) or not names:
            continue
        for dm in (0, 1, -1):
            cands = [j for j, l in enumerate(lines) if j not in used and l[0] == t + dm and any(n in _fold(l[3]) for n in names)]
            if dm == 0 and ev.get("overloadTime") and len(cands) > 1:
                cands = [j for j in cands if lines[j][1] == ev.get("overloadTime")] or cands
            if len(cands) == 1:
                out[i] = lines[cands[0]][3]
                used.add(cands[0])
                break
    for i, ev in enumerate(goals):
        if i in out or not isinstance(ev.get("time"), int):
            continue
        cands = [j for j, l in enumerate(lines) if j not in used and l[0] == ev["time"]]
        same = [g for g in goals if g.get("time") == ev["time"]]
        if len(cands) == 1 and len(same) == 1:
            out[i] = lines[cands[0]][3]
            used.add(cands[0])
    return out


def goal_key(ev):
    """<minute>-<player id>, the site's data-goal-key (added time as <minute>+<added>). Raw FotMob events (time,
    overloadTime, playerId) and our normalized ones (minute, added, player.id) give the same key."""
    t = ev.get("time", ev.get("minute"))
    add = ev.get("overloadTime", ev.get("added"))
    pid = ev.get("playerId") or (ev.get("player") or {}).get("id") or 0
    return f"{t}{'+' + str(add) if add else ''}-{pid}"


def describe_all(raw, ticker=None):
    """Every goal of a FotMob matchDetails payload -> {goal_key: {"key", "ar"}}. `ticker`: the parsed English ticker
    (optional; its AutoCommentaries flag picks the reader)."""
    evs = ((((raw or {}).get("content") or {}).get("matchFacts") or {}).get("events") or {}).get("events") or []
    goals = [e for e in evs if e.get("type") == "Goal" and not e.get("isPenaltyShootoutEvent")]
    lines = goal_lines(ticker) if ticker else []
    auto = bool(ticker.get("AutoCommentaries")) if ticker else None
    texts = assign(goals, lines) if lines else {}
    out = {}
    for i, e in enumerate(goals):
        h = describe(e, None, texts.get(i), auto)
        if h:
            out[goal_key(e)] = h
    return out


def needs_ticker(raw):
    """Whether the English ticker can add anything: human commentary (rare techniques), or goals without a shot map."""
    lang = ticker_lang((((raw or {}).get("content") or {}).get("liveticker") or {}).get("langs"))
    if not lang:
        return None
    evs = ((((raw or {}).get("content") or {}).get("matchFacts") or {}).get("events") or {}).get("events") or []
    goals = [e for e in evs if e.get("type") == "Goal" and not e.get("isPenaltyShootoutEvent")]
    if not goals:
        return None
    if lang == "en" or any(not e.get("shotmapEvent") and not e.get("ownGoal") and not (e.get("goalDescriptionKey") or "").startswith("pen") for e in goals):
        return lang
    return None
