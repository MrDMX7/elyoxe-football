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

# Arabic club names: FotMob's name_ar, else names/clubs_ar.json, else teams_ar.yaml, else TRANSLIT (gen.py sets it: a Gemini
# transliteration cached into clubs_ar.json with source "generated"), else the Latin name
CLUBS_FILE = os.path.join(os.path.dirname(NAMES_FILE), "clubs_ar.json"); YAML_FILE = os.path.join(os.path.dirname(NAMES_FILE), "..", "teams_ar.yaml")
_CLUBS = {}; TRANSLIT = None
def _clubs():
    if not _CLUBS:
        try: _CLUBS.update({k: v.get("ar") for k, v in json.load(open(CLUBS_FILE)).items() if isinstance(v, dict) and v.get("ar")})
        except Exception: pass
        try:
            import yaml
            for k, v in ((yaml.safe_load(open(YAML_FILE)) or {}).get("teams") or {}).items(): _CLUBS.setdefault(str(k), v)
        except Exception: pass
        _CLUBS.setdefault("_", "")
    return _CLUBS
def club_ar(t):
    t = t or {}
    if t.get("name_ar"): return t["name_ar"]
    tid = str(t.get("id") or ""); hit = _clubs().get(tid)
    if hit: return hit
    if TRANSLIT and tid and t.get("name"):
        ar = TRANSLIT(tid, t["name"])
        if ar: _CLUBS[tid] = ar; return ar
    return t.get("name") or ""
def _team(md, side): return club_ar(md.get(side)) or side
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
        if e["type"] in RED_T: reds.append({"min": e.get("minute"), "side": e["team"], "type": e["type"], "pid": str((e.get("player") or {}).get("id") or "")}); continue
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
        # «طرد مباشر» only for a straight red; «إنذار ثاني/الأصفر الثاني» only for a second yellow
        if re.search(r"طرد(?:ة)? مباشر|الطرد المباشر|(?:الكرت|البطاقة) (?:الأحمر|الحمراء) المباشر", s) and t["reds"] and all(r["type"] == "second_yellow" for r in t["reds"]):
            return "straight red claimed but every red was a second yellow"
        if re.search(r"(?:الإنذار|إنذار|الأصفر|أصفر) (?:الثاني|ثاني)|إنذارين", s) and t["reds"] and all(r["type"] == "red" for r in t["reds"]):
            return "second yellow claimed but every red was straight"
        # «هدف عكسي … لصالح X»: X must be the side it counted for (FotMob files the own goal under that side)
        m = re.search(r"(?:هدف عكسي|في مرماه|بالخطأ في مرمى)[^.،]{0,70}?لصالح\s+(?:منتخب\s+)?(\S+(?:\s+\S+)?)", s)
        if m:
            og = [g for g in t["goals"] if g["type"] == "own_goal"]
            if og:
                named = H if m.group(1).startswith(H.split()[0]) or H.startswith(m.group(1).split()[0]) else A if m.group(1).startswith(A.split()[0]) or A.startswith(m.group(1).split()[0]) else None
                if named and all(_team(md, g["side"]) != named for g in og): return f"own goal said for {named}"
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
        if re.search(r"سج[ّ]?ل|هدف", s) and not re.search(r"طرد|إنذار|أصفر|أحمر|حمراء|ضي[ّ]?ع|ضايع|أهدر|تصد[ىي]|أنقذ", s):
            for a0, b0, pid in _name_spans(s, players):
                mm = re.search(r"^\D{0,25}?(?:في\s+)?الدقيقة\s+(\d+)", s[b0:])
                if not mm: continue
                mins = [g["min"] for g in t["goals"] if g["pid"] == pid]   # own goals count: «هدف عكسي من فلان في الدقيقة N»
                if int(mm.group(1)) not in mins: return f"{players[pid].get('lat')} did not score at {mm.group(1)}'"
    return None

def check_halves(text, md):
    """Checks «N أهداف في الشوط الأول/الثاني» per team against that half; returns (reason, text with those phrases removed)."""
    t = timeline(md); H, A = _team(md, "home"), _team(md, "away"); rest = text
    # a goal noun must follow the number («3-2 في الشوط الثاني» is a score, not a count)
    for m in re.finditer(r"(?:(\d+)\s+(?:أهداف|هدف)|(هدفين|هدف واحد|هدف وحيد))\s*(?:في|بـ?|خلال)\s*ال?شوط\s+(الأول|الثاني)", text):
        n = int(m.group(1)) if m.group(1) else 2 if m.group(2) == "هدفين" else 1
        near = text[max(0, m.start() - 25):m.start()]
        rest = rest.replace(m.group(0), "")
        if re.search(r"متأخر|تأخر|متخلف|خسران|مغلوب", near): continue   # «متأخر بهدفين في الشوط الأول» is a deficit, not goals scored
        conceded = bool(re.search(r"استقبل|تلقى|تلق[ّ]?ى|دخل(?:ت)? مرماه|استقبلت|تلقت", near))
        before = text[max(0, m.start() - 80):m.start()]; hp, ap = before.rfind(H), before.rfind(A)
        side = ("home" if hp > ap else "away") if max(hp, ap) >= 0 else None
        if side and conceded: side = "away" if side == "home" else "home"   # goals conceded = the other side's goals
        half = [g for g in t["goals"] if (g["min"] <= 45) == (m.group(3) == "الأول") and (side is None or g["side"] == side)]
        if len(half) != n: return f"{n} goals {'conceded ' if conceded else ''}in the {m.group(3)} half, data has {len(half)}", text
    return None, rest

HIST = [(r"أول فوز|أول انتصار", ("head_to_head", "h2h", "form", "firsts")), (r"أول مرة", ("firsts", "records_at_stake")),
        (r"ما فاز من|بدون فوز في|من غير فوز", ("form", "streak", "records_at_stake")), (r"أكبر فوز|أكبر خسارة", ("records_at_stake", "biggest_win", "records")),
        (r"سلسلة\s+\d+|\d+\s+(?:مباريات|انتصارات|فوز)\s+(?:ورا بعض|متتالية|على التوالي)", ("form", "streak", "records_at_stake"))]
def check_history(text, evidence):
    """History claims pass only if the model's input had the kind of data behind them (and, for «أول فوز», the h2h agrees)."""
    ev = evidence if isinstance(evidence, dict) else {}
    blob = json.dumps(ev, ensure_ascii=False)
    runs = check_runs(text, ev) or check_counts(text, ev) or check_generic(text, ev)
    if runs: return runs
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

RUN_W = {"خسارة": "L", "خسارات": "L", "خسارتين": "L", "هزائم": "L", "فوز": "W", "انتصارات": "W", "انتصارين": "W", "فوزين": "W", "تعادل": "D", "تعادلات": "D", "تعادلين": "D"}
DUAL_N = {"خسارتين": 2, "انتصارين": 2, "فوزين": 2, "تعادلين": 2}
def _forms(ev, out=None):
    out = [] if out is None else out
    if isinstance(ev, dict):
        for k, v in ev.items():
            if k == "form" and isinstance(v, (list, str)): out.append([x for x in (v if isinstance(v, list) else list(v)) if x in "WDL"])
            else: _forms(v, out)
    elif isinstance(ev, list):
        for v in ev: _forms(v, out)
    return out
def check_runs(text, evidence):
    """«N خسارات/انتصارات متتالية/ورا بعض/على التوالي» (and duals) must be a run of that length in a form list of the input."""
    forms = _forms(evidence)
    for m in re.finditer(r"(?:(\d+)\s+)?(خسارات|خسارتين|هزائم|انتصارات|انتصارين|فوزين|تعادلات|تعادلين)\s+(?:متتالية|متتاليتين|ورا بعض|على التوالي)", text):
        n = int(m.group(1)) if m.group(1) else DUAL_N.get(m.group(2))
        if not n: continue
        if not forms: return f"«{m.group(0)}» without form data in the input"
        r = RUN_W[m.group(2)]; runs = set()
        for f in forms:
            k = 0
            for x in f + ["-"]:
                if x == r: k += 1
                else:
                    if k: runs.add(k)
                    k = 0
        if n not in runs: return f"«{m.group(0)}» but the form runs are {sorted(runs)}"
    return None

CNT_W = {"انتصارات": "W", "انتصار": "W", "انتصارين": "W", "فوز": "W", "فوزين": "W", "فازات": "W", "خسارات": "L", "خسارة": "L", "خسارتين": "L", "هزائم": "L", "هزيمة": "L", "هزيمتين": "L",
         "خساير": "L", "تعادلات": "D", "تعادل": "D", "تعادلين": "D"}
def check_counts(text, evidence):
    """In a form sentence («فورمة»، «آخر 5»، «من آخر»), «N انتصارات/هزائم/…» and the duals must equal that result's count in a form list."""
    if not re.search(r"فورم|آخر\s*(?:5|خمس)|من آخر|آخر \d+ مباريات", text): return None
    forms = _forms(evidence)
    if not forms: return None
    for m in re.finditer(r"(?:(\d+)\s+)?(انتصارات|انتصارين|انتصار|فوزين|فازات|فوز|خسارات|خسارتين|خسارة|خساير|هزائم|هزيمتين|هزيمة|تعادلات|تعادلين|تعادل)(?!\w)", text):
        w = m.group(2); n = int(m.group(1)) if m.group(1) else 2 if w.endswith("ين") else None
        if n is None or n > 10: continue
        after = text[m.end():m.end() + 14]
        if re.match(r"\s*(?:متتالي|ورا بعض|على التوالي)", after): continue   # runs are check_runs' job
        r = CNT_W[w]
        if all(f.count(r) != n for f in forms): return f"«{m.group(0)}» but the form lists have {[f.count(r) for f in forms]}"
    return None

LABELS = ["الفريق الأول", "الفريق الثاني", "نقطة قوة", "نقطة ضعف", "نقطة الضعف", "نقطة القوة", "مفتاح المباراة", "توقع تيفو", "توقعات تيفو", "نتايج الأسبوع", "المباراة الياية"]
def check_generic(text, evidence):
    """Audit W1.3(a): home words at a neutral venue, «مب متوفرة», «فوزه رقم N», and a line that is only its own label."""
    ev = evidence if isinstance(evidence, dict) else {}
    if ev.get("neutral") and re.search(r"(?<!\w)(?:على |برا |خارج |في )?(?:أرضه|أرضها|جمهوره|جمهورها|جماهيره|ملعبه|ملعبها)(?!\w)", text):
        return "home/away wording at a neutral venue"
    if re.search(r"(?:مب|مش|غير|ما هي|مو) متوفر(?:ة)?", text): return "«مب متوفرة»"
    m = re.search(r"(?:مسجل |حسب |في |ب)ال?بيانات|نظافة شبك", text)
    if m: return f"talks about the data («{m.group(0)}»)"
    if re.search(r"فوز(?:ه|ها)? رقم \d+", text): return "«فوزه رقم N»"
    for lab in LABELS:
        m = re.match(r"\s*" + re.escape(lab) + r"\s*[:：،-]?\s*(.*)$", text)
        if m:
            rest = m.group(1).strip(" .،")
            if not rest or rest.startswith(lab) or len(rest.split()) < 4: return f"line repeats its label «{lab}»"
    return None

LATIN_OK = {"VAR", "xG", "FotMob", "Tifo"}
def arabic_names(text, players):
    """Replaces Latin player names with their Arabic names; returns (text, [Latin words left])."""
    for a0, b0, pid in sorted(_name_spans(text, players), key=lambda c: -c[0]):
        p = players[pid]
        if p.get("ar") and re.search(r"[A-Za-z]", text[a0:b0]): text = text[:a0] + p["ar"] + text[b0:]
    left = [w for w in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\-]+", text) if w not in LATIN_OK]
    return text, left
