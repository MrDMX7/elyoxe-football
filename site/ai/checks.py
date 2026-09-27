"""Deterministic fact checks on generated Tifo text (owner's options 2+3, 2026-09-27), used by gen.py for every kind and
provider. Each check returns None when the text agrees with the match data, else a short reason; callers drop the line.
  timeline(md)                   goals in order, who led when, the decisive goal, whether the winner trailed
  check_events(text, md, names)  «بعد/عقب/قبل» a red card, «هدف الفوز/الحسم/الذهبي», «قلب النتيجة/ريمونتادا», named scorers
  check_halves(text, md)         «N أهداف في الشوط الأول/الثاني» against that half; returns (reason, text without those phrases)
  check_history(text, evidence)  «أول فوز/أول مرة/ما فاز من/أكبر فوز/سلسلة N» only when the input carries the evidence
  arabic_names(text, names)      Latin player names -> Arabic from names/players_ar.json; (text, leftover Latin words)
FotMob files an own goal under the side it counted FOR (checked on 1000020522, 5868079)."""
import json, os, re

GOAL_T = ("goal", "own_goal", "penalty_goal")
RED_T = ("red", "second_yellow")
NAMES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "names", "players_ar.json")
_NAMES = {}
def names_ar():
    """{player id (str): Arabic name} from names/players_ar.json (Wikidata-checked)."""
    if not _NAMES:
        try: _NAMES.update({k: v["ar"] for k, v in json.load(open(NAMES_FILE)).items() if v.get("ar")})
        except Exception: _NAMES["_"] = ""
    return _NAMES

def _team(md, side): return (md.get(side) or {}).get("name_ar") or (md.get(side) or {}).get("name") or side
def _mm(e): return (e.get("minute") or 0) + (e.get("added") or 0) / 100   # 90+3 sorts after 90

def match_players(md):
    """{pid: {"lat", "ar", "side"}} for everyone in the lineups and events."""
    out, ar = {}, names_ar()
    for side in ("home", "away"):
        lu = (md.get("lineups") or {}).get(side) or {}
        for p in (lu.get("starters") or []) + (lu.get("subs") or lu.get("bench") or []):
            if p.get("id"): out[str(p["id"])] = {"lat": p.get("name") or "", "ar": ar.get(str(p["id"])), "side": side}
    for e in md.get("events") or []:
        for k in ("player", "assist", "player_out"):
            p = e.get(k) or {}
            if p.get("id") and str(p["id"]) not in out: out[str(p["id"])] = {"lat": p.get("name") or "", "ar": ar.get(str(p["id"])), "side": e.get("team")}
    return out

def timeline(md):
    ev = sorted([e for e in md.get("events") or [] if e.get("type") in GOAL_T + RED_T and e.get("team") in ("home", "away")], key=_mm)
    h = a = 0; goals = []; reds = []; trailed = {"home": False, "away": False}; lead_changes = []
    for e in ev:
        if e["type"] in RED_T: reds.append({"min": e.get("minute"), "side": e["team"], "pid": str((e.get("player") or {}).get("id") or "")}); continue
        if e["team"] == "home": h += 1
        else: a += 1
        goals.append({"min": e.get("minute"), "added": e.get("added"), "side": e["team"], "type": e["type"], "pid": str((e.get("player") or {}).get("id") or ""), "score": (h, a)})
        if h < a: trailed["home"] = True
        if a < h: trailed["away"] = True
    sc = md.get("score") or {}; fh, fa = sc.get("home"), sc.get("away")
    win = None if fh is None or fa is None or fh == fa else ("home" if fh > fa else "away")
    decisive = None
    if win:   # the winner's goal after which it led for good
        for i, g in enumerate(goals):
            if g["side"] != win: continue
            lead = (g["score"][0] - g["score"][1]) * (1 if win == "home" else -1)
            if lead > 0 and all(((x["score"][0] - x["score"][1]) * (1 if win == "home" else -1)) > 0 for x in goals[i:]): decisive = g; break
    return {"goals": goals, "reds": reds, "win": win, "trailed": trailed, "decisive": decisive}

def _name_spans(text, players):
    """[(start, end, pid)] for every Arabic or Latin player name in the text (longest names first, no overlaps)."""
    cands = []
    for pid, p in players.items():
        for n in {p.get("ar"), p.get("lat")} | {(p.get("lat") or "").split(" ")[-1] if len((p.get("lat") or "").split(" ")[-1]) > 3 else None}:
            if n and len(n) > 2:
                for m in re.finditer(r"(?<!\w)" + re.escape(n) + r"(?!\w)", text): cands.append((m.start(), m.end(), pid))
    cands.sort(key=lambda c: (c[0], -(c[1] - c[0]))); out = []
    for c in cands:
        if not out or c[0] >= out[-1][1]: out.append(c)
    return out

def _sentences(text): return [s for s in re.split(r"(?<=[.!؟؛\n])\s+|،\s*و?(?=\S)", text) if s.strip()]

RED_W = r"(?:طرد|انطرد|الطرد|طردة|البطاقة الحمراء|بطاقة حمراء|الكرت الأحمر)"
def check_events(text, md, players=None):
    t = timeline(md); players = players if players is not None else match_players(md)
    H, A = _team(md, "home"), _team(md, "away"); side_of = lambda s: "home" if H in s and A not in s else "away" if A in s and H not in s else None
    for s in _sentences(text):
        # goals «بعد/عقب» or «قبل» a red card
        m = re.search(r"(بعد|عقب|قبل)\s+(?:ما\s+)?(?:\S+\s+){0,2}?" + RED_W, s)
        if m and t["reds"] and re.search(r"سج[ّ]?ل|هدف|أهداف", s[:m.start()] + s[m.end():]):
            side = side_of(s) or (t["win"] if t["win"] else None); r = min(x["min"] for x in t["reds"])
            gs = [g["min"] for g in t["goals"] if side is None or g["side"] == side]
            if gs and m.group(1) in ("بعد", "عقب") and all(g <= r for g in gs): return f"goals before the red card ({r}') said after"
            if gs and m.group(1) == "قبل" and all(g > r for g in gs): return f"goals after the red card ({r}') said before"
        # the winning goal
        m = re.search(r"هدف (?:الفوز|الحسم|الانتصار)|الهدف الذهبي|الهدف الحاسم", s)
        if m and t["decisive"]:
            d, near = t["decisive"], s[m.end():m.end() + 60]
            mins = [int(x) for x in re.findall(r"الدقيقة\s+(\d+)", near)]
            if mins and mins[0] != d["min"]: return f"winning goal said {mins[0]}' but it was {d['min']}'"
            if re.search(r"(?:ضربة|ركلة)\s+(?:جزاء|يزاء|يزا|جزا)|بلنتي|من نقطة الجزاء", near) and d["type"] != "penalty_goal": return f"winning goal said from a penalty but it was open play ({d['min']}')"
            before = _name_spans(s[max(0, m.start() - 40):m.start()], players)
            after = _name_spans(re.split(r"تمريرة|صناعة|عرضية|بعد|عقب|،", s[m.end():])[0], players)
            who = before[-1][2] if before else after[0][2] if after else None
            if who and who != d["pid"]: return "winning goal credited to the wrong player"
        # comebacks
        if re.search(r"قلب(?:ها)? (?:النتيجة|الطاولة)|قلبها|ريمونتادا|يقلب(?:ها)?|رجع (?:في النتيجة|بقوة|من ورا)", s) and t["win"] and not t["trailed"][t["win"]]:
            return "comeback claimed but the winner never trailed"
        # named scorer at a minute
        if re.search(r"سج[ّ]?ل|هدف", s) and not re.search(r"طرد|إنذار|أصفر|ضي[ّ]?ع|ضايع|أهدر", s):
            for a0, b0, pid in _name_spans(s, players):
                mm = re.search(r"^\D{0,25}?(?:في\s+)?الدقيقة\s+(\d+)", s[b0:])
                if not mm: continue
                mins = [g["min"] for g in t["goals"] if g["pid"] == pid]   # own goals count: «هدف عكسي من فلان في الدقيقة N»
                if int(mm.group(1)) not in mins: return f"{players[pid].get('lat')} did not score at {mm.group(1)}'"
    return None

def check_halves(text, md):
    """Checks «N أهداف في الشوط الأول/الثاني» per team against that half; returns (reason, text with those phrases removed)."""
    t = timeline(md); H, A = _team(md, "home"), _team(md, "away"); rest = text
    for m in re.finditer(r"(\d+|هدفين|هدف واحد)\s+(?:أهداف|هدف)?\s*(?:في|بـ?|خلال)\s*ال?شوط\s+(الأول|الثاني)", text):
        n = 2 if m.group(1) == "هدفين" else 1 if m.group(1) == "هدف واحد" else int(m.group(1))
        before = text[max(0, m.start() - 60):m.start()]; side = "home" if before.rfind(H) > before.rfind(A) else "away" if before.rfind(A) >= 0 else None
        half = [g for g in t["goals"] if (g["min"] <= 45) == (m.group(2) == "الأول") and (side is None or g["side"] == side)]
        if len(half) != n: return f"{n} goals in the {m.group(2)} half, data has {len(half)}", text
        rest = rest.replace(m.group(0), "")
    return None, rest

HIST = [(r"أول فوز|أول انتصار", ("head_to_head", "h2h", "form", "firsts")), (r"أول مرة", ("firsts", "records_at_stake")),
        (r"ما فاز من|بدون فوز في|من غير فوز", ("form", "streak", "records_at_stake")), (r"أكبر فوز|أكبر خسارة", ("records_at_stake", "biggest_win", "records")),
        (r"سلسلة\s+\d+|\d+\s+(?:مباريات|انتصارات|فوز)\s+(?:ورا بعض|متتالية|على التوالي)", ("form", "streak", "records_at_stake"))]
def check_history(text, evidence):
    """History claims pass only if the model's input had the kind of data behind them (and, for «أول فوز», the h2h agrees)."""
    ev = evidence if isinstance(evidence, dict) else {}
    blob = json.dumps(ev, ensure_ascii=False)
    for pat, keys in HIST:
        m = re.search(pat, text)
        if not m: continue
        if not any(ev.get(k) not in (None, [], {}, "") for k in keys) and not any(f'"{k}"' in blob and f'"{k}": null' not in blob for k in keys): return f"«{m.group(0)}» without evidence in the input"
        if m.group(0) in ("أول فوز", "أول انتصار"):
            h = ev.get("head_to_head") or {}
            if h and max(h.get("home_wins") or 0, h.get("away_wins") or 0) > 1: return f"«{m.group(0)}» but the h2h has {h}"
        n = re.search(r"\d+", text[m.start():m.end() + 20])
        if n and n.group(0) not in blob: return f"«{m.group(0)}»: {n.group(0)} is not in the input"
    return None

LATIN_OK = {"VAR", "xG", "FotMob", "Tifo"}
def arabic_names(text, players):
    """Replaces Latin player names with their Arabic names; returns (text, [Latin words left])."""
    for a0, b0, pid in sorted(_name_spans(text, players), key=lambda c: -c[0]):
        p = players[pid]
        if p.get("ar") and re.search(r"[A-Za-z]", text[a0:b0]): text = text[:a0] + p["ar"] + text[b0:]
    left = [w for w in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\-]+", text) if w not in LATIN_OK]
    return text, left
