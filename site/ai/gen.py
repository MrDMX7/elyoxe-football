"""تيفو phase 5 — written and voiced content from the data (docs/ROADMAP.md phase 5).

  python3 ai/gen.py [--samples] [--only summary,preview,podcast,daily5,commentary,digest,power,why,quick] [--limit N]

What it makes (cache/ai/…, read by build.cjs; shown on the site only for kinds switched on in ai/approved.json):
  9  + 78   summary/{match}.json   finished UAE matches: an Emirati summary (4-6 sentences) + a stats thread for X (4-6 posts)
  77        preview/{match}.json   UAE matches in the next 7 days: 5-line Emirati preview (strengths, weaknesses, key)
  161       podcast/{yyyy-ww}.json + .mp3      the weekly Tifo Cast: Hamed and Maha talking the round through, ~5 min
  (19, the voiced round recap, was dropped by the owner on 2026-09-27: it duplicated Tifo Cast)

Rules (the owner's): Emirati dialect from memory feedback_emirati_dialect + content/video/_system/EMIRATI-LEXICON.json,
applied again after generation; no tanween; male singular address, no ج suffix; facts only from the data handed over.
Nothing is published until the owner approves a sample of each kind (approved.json). Every Gemini schema string has a
maxLength (the loop-until-token-limit trap). Numbers become Emirati words only in the spoken (TTS) text.
"""
import argparse, datetime as dt, hashlib, json, os, re, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checks

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
CACHE = os.path.join(SITE, "cache", "ai")
DATA = os.environ.get("TIFO_DATA", "https://d1n5aqaqkowltp.cloudfront.net")
MODEL = os.environ.get("TIFO_MODEL", "gemini-3.5-flash")
LEX = json.load(open(os.path.expanduser("~/workspace/content/video/_system/EMIRATI-LEXICON.json")))
UAE_COMPS = [538, 11027, 9943, 11026]
ARAB = {"AE", "SA", "EG", "MA", "DZ", "TN", "IQ", "JO", "KW", "QA", "BH", "OM", "LB", "SY", "PS", "YE", "LY", "SD", "MR", "SO", "DJ", "KM"}
BIG5 = {47, 87, 55, 54, 53}

def key():
    for line in open(os.path.expanduser("~/workspace/content-pipeline/.env")):
        if line.startswith("GEMINI_API_KEY="): return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("no GEMINI_API_KEY")

def get(p):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{DATA}/{p}", headers={"Accept-Encoding": "identity"}), timeout=25) as r:
                raw = r.read()
                if raw[:2] == b"\x1f\x8b": import gzip; raw = gzip.decompress(raw)   # objects are stored gzip-encoded
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            if e.code in (403, 404): return None
        except Exception: pass
        time.sleep(1.5 * (i + 1))
    return None

STYLE = """اكتب باللهجة الإماراتية المحكية، مب فصحى ولا لهجة خليجية عامة. المخاطَب مذكّر مفرد دايماً.
قواعد إلزامية:
- «شو» مب «وش»، «منو» مب «مين»، «كيف» مب «شلون»، «جذيه» مب «كذا»، «الحين»، «وايد»، «مب» للنفي، «داخل» مب «جوّا»، «يراوي» مب «يوري»، «الياي» و«يديد» (بس هالكلمتين بالياء، والباقي يبقى بالجيم)، «شرات» مب «زي»، «انزين» مب «طيب»، «بروحه» مب «لحاله».
- لا تنوين ولا إعراب: «هدف واحد» مب «هدفاً»، «نص» مب «نصاً».
- كاف المخاطب تبقى كاف: عليك، لك، فريقك. ممنوع «عليج، لج، فريقج».
- خفيف على القلب بس كل جملة فيها معلومة من البيانات. ممنوع المبالغة والشعارات («ملحمة»، «تاريخي») إلا إذا الرقم يثبتها.
- لا تخترع أي رقم أو اسم أو حدث مب موجود في البيانات. إذا ما تعرف شي، لا تذكره.
- أسماء اللاعبين اكتبها بالعربي كما هي في البيانات بالضبط، ولا تكتب أي اسم بحروف لاتينية.
- في النص المكتوب اكتب كل الأرقام والنتايج والدقايق بالأرقام (0-9) مب بالكلمات: «فاز 3 - 1»، «في الدقيقة 9»، «61%».
- استعمل «فاز على» مب «هزم»، و«عقب» أو «بعدين» للترتيب.
- لا تكتب «رقم 1» أو «1 مرة»: قل «أول فوز»، «مرة وحدة»، «المتصدر».
- اذكر الأرقام بس، لا الدوافع ولا المشاعر ولا النصايح: ممنوع «معنويات»، «دفعة معنوية»، «لازم يثبت نفسه»، «حافز»، «ثقة». وبدون إيموجي.
"""

# ---- text provider: TIFO_TEXT=claude|gemini (env), else ai/provider.txt, else gemini. Claude = `claude -p` with Haiku on the
# owner's subscription (one process at a time: the phone is RAM-bound); any failure falls back to Gemini for that item, and
# 3 Claude failures in a row switch the rest of the run to Gemini (log: claude_stopped). TTS stays on Gemini.
def _provider():
    v = os.environ.get("TIFO_TEXT")
    if not v:
        try: v = open(os.path.join(HERE, "provider.txt")).read().strip()
        except OSError: v = ""
    return v if v.split(":")[0] in ("claude", "gemini") else "gemini"
PROVIDER = _provider()   # "claude", "claude:haiku", "claude:sonnet" or "gemini"
CLAUDE_FAILS = [0]; CLAUDE_STOPPED = []; CALLS = []; LAST_MODEL = [""]   # LAST_MODEL: what actually wrote the last item   # CALLS: (provider, seconds) per call, for timing reports
def _jschema(g):   # the Gemini schema dialect (OBJECT/STRING…) as JSON Schema
    if not isinstance(g, dict): return g
    o = {k: _jschema(v) for k, v in g.items() if k != "type"}
    if "type" in g: o["type"] = g["type"].lower()
    if "properties" in g: o["properties"] = {k: _jschema(v) for k, v in g["properties"].items()}; o["additionalProperties"] = False
    return o
def _fit(schema, v):   # maxLength / maxItems enforced in code, whatever the model returned
    t = (schema or {}).get("type")
    if t == "STRING": v = v if isinstance(v, str) else str(v); n = schema.get("maxLength"); return v[:n].rstrip() if n and len(v) > n else v
    if t == "ARRAY": v = v if isinstance(v, list) else []; v = v[:schema.get("maxItems", len(v))]; return [_fit(schema.get("items"), x) for x in v]
    if t == "OBJECT": v = v if isinstance(v, dict) else {}; return {k: _fit(sc, v.get(k)) for k, sc in schema.get("properties", {}).items() if k in v}
    if t == "INTEGER":
        try: return int(v)
        except Exception: return v
    return v
def claude_text(system, payload, schema, model="haiku"):
    import subprocess, shutil
    cmd = [os.environ.get("CLAUDE_BIN") or shutil.which("claude") or os.path.expanduser("~/.local/bin/claude"), "-p", "--model", model, "--output-format", "json", "--tools", "", "--strict-mcp-config", "--disable-slash-commands",
           "--no-session-persistence", "--setting-sources", "", "--settings", '{"alwaysThinkingEnabled":false}', "--system-prompt", system + "\n\nجاوب بـ JSON بس، مطابق للـ schema.", "--json-schema", json.dumps(_jschema(schema), ensure_ascii=False),
           json.dumps(payload, ensure_ascii=False)]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=int(os.environ.get("TIFO_CLAUDE_TIMEOUT") or 90), cwd="/tmp", env=dict(os.environ, MAX_THINKING_TOKENS="0"))   # no thinking: ~8 s instead of ~65 s
        out = json.loads(r.stdout or "{}")
        if r.returncode or out.get("is_error"): raise RuntimeError((out.get("result") or r.stderr or "")[:200])
        res = out.get("structured_output") or json.loads(out.get("result") or "")
        req = schema.get("required") or []
        if not isinstance(res, dict) or any(k not in res for k in req): raise ValueError("schema")
        CALLS.append(("claude:" + model, round(time.time() - t0, 1))); CLAUDE_FAILS[0] = 0
        return _fit(schema, res)
    except Exception as e:
        CLAUDE_FAILS[0] += 1; print("claude failed:", str(e)[:200], file=sys.stderr)
        if CLAUDE_FAILS[0] >= 3 and not CLAUDE_STOPPED: CLAUDE_STOPPED.append(str(e)[:120]); print("claude_stopped: Gemini for the rest of the run", file=sys.stderr)
        return None

GEMINI_OUT = []   # set on 402/429: the key is out of credit or quota; later calls return None at once instead of retrying
def provider_for(kind):
    """TIFO_TEXT (env) wins for every kind; else ai/provider.json {kind: provider, "default": …}; else ai/provider.txt; else gemini."""
    if os.environ.get("TIFO_TEXT"): return PROVIDER
    try: cfg = json.load(open(os.path.join(HERE, "provider.json")))
    except (OSError, ValueError): cfg = {}
    v = cfg.get(kind) or cfg.get("default") or PROVIDER
    return v if v.split(":")[0] in ("claude", "gemini") else "gemini"
def gemini(system, payload, schema, temp=0.6, tokens=4000, provider=None, kind=None):
    """Generated text from the provider chosen for this kind (name kept: every kind calls it). Claude first when chosen, Gemini as fallback."""
    prov = provider or (provider_for(kind) if kind else PROVIDER); LAST_MODEL[0] = MODEL
    if prov.startswith("claude") and not CLAUDE_STOPPED:
        cm = (prov.split(":") + ["haiku"])[1] or "haiku"; out = claude_text(system, payload, schema, cm)
        if out is not None: LAST_MODEL[0] = "claude-" + cm; return out
    t0 = time.time(); out = gemini_api(system, payload, schema, temp, tokens)
    if out is not None: CALLS.append(("gemini", round(time.time() - t0, 1)))
    return out
def gemini_api(system, payload, schema, temp=0.6, tokens=4000):
    if GEMINI_OUT: return None
    req = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}],
           "generationConfig": {"temperature": temp, "maxOutputTokens": tokens, "responseMimeType": "application/json", "responseSchema": schema}}
    for i in range(3):
        try:
            r = urllib.request.urlopen(urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent", json.dumps(req).encode(),
                                                              {"Content-Type": "application/json", "x-goog-api-key": key()}), timeout=90)
            out = json.loads(r.read())
            return json.loads(out["candidates"][0]["content"]["parts"][0]["text"])
        except Exception as e:
            print("gemini retry", i, str(e)[:200], file=sys.stderr)
            if getattr(e, "code", None) in (402, 429): GEMINI_OUT.append(e.code); print(f"gemini {e.code}: stopping generated text for this run", file=sys.stderr); return None
            time.sleep(4 * (i + 1))
    return None

S = lambda n: {"type": "STRING", "maxLength": n}
def OBJ(props): return {"type": "OBJECT", "properties": props, "required": list(props)}
def ARR(item, mx): return {"type": "ARRAY", "items": item, "maxItems": mx}

# ---- the dialect pass after generation (the lexicon, word-bounded; tanween out; masculine address)
FEM = {"عليج": "عليك", "لج": "لك", "إنج": "إنك", "انج": "انك", "فريقج": "فريقك", "بيتج": "بيتك", "راسج": "راسك"}
# deterministic grammar pass after generation (every kind): Arabic duals for a bare 2, and national teams (feminine
# country names) given «منتخب» when a masculine verb follows. `nations` = the national teams' Arabic names in the item.
DUAL = {"فرص": "فرصتين", "فرصة": "فرصتين", "أهداف": "هدفين", "هدف": "هدفين", "مباراة": "مباراتين", "مباريات": "مباراتين", "مرات": "مرتين", "مرة": "مرتين",
        "تسديدات": "تسديدتين", "تسديدة": "تسديدتين", "نقاط": "نقطتين", "نقطة": "نقطتين", "ركنيات": "ركنيتين", "ركنية": "ركنيتين", "مواجهات": "مواجهتين", "مواجهة": "مواجهتين",
        "تبديلات": "تبديلين", "تبديل": "تبديلين", "انتصارات": "انتصارين", "خسارات": "خسارتين", "تعادلات": "تعادلين", "جولات": "جولتين", "إنذارات": "إنذارين"}
MASC_VERBS = "فاز|خسر|تعادل|تقدم|تقدّم|سجل|سجّل|لعب|حقق|تصدر|تصدّر|يلعب|يواجه|يلاقي|يدخل"
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D\u2B00-\u2BFF]")
FIXES = [("اللمسات على المرمى", "التسديدات على المرمى")]
ALLOWED = {"إيي", "ييي", "يات", "ياي", "الياي", "يديد"}   # correct Emirati (ج→ي): never "fixed" by any pass (owner, 2026-09-27)
def grammar(t, nations=()):
    if not isinstance(t, str): return t
    t = re.sub(r"\s{2,}", " ", EMOJI.sub("", t)).strip()
    for a, b in FIXES: t = re.sub(r"(?<!\w)([وبل]?)" + re.escape(a) + r"(?!\w)", lambda m: m.group(1) + b, t)
    t = re.sub(r"(?<![\d.,])2\s+(?:فرص|فرصة)\s+محققة", "فرصتين محققتين", t)
    t = re.sub(r"(?<![\d.,])2\s+(" + "|".join(sorted(DUAL, key=len, reverse=True)) + r")(?!\w)", lambda m: DUAL[m.group(1)], t)
    for n in nations:
        if not n: continue
        t = re.sub(r"(?<!منتخب )(?<!\w)(و?)" + re.escape(n) + r"\s+(" + MASC_VERBS + r")(?!\w)", lambda m: m.group(1) + "منتخب " + n + " " + m.group(2), t)
    return t

def emirati(t):
    if not isinstance(t, str): return t
    for a, b in LEX["phrases"].items(): t = t.replace(a, b)
    for a, b in [(a, b) for a, b in list(LEX["words"].items()) + list(FEM.items()) if a not in ALLOWED] + [("مين", "منو"), ("كذا", "جذيه"), ("يرى", "يشوف"), ("أرى", "أشوف"), ("نرى", "نشوف"), ("بتقام", "بتستوي"), ("تقام", "تستوي"), ("يقام", "يستوي"), ("بيقام", "بيستوي")]:
        t = re.sub(r"(?<!\w)" + re.escape(a) + r"(?!\w)", b, t)
    return grammar(re.sub("[ً-ٍ]", "", t))
def deep(x, nations=()):
    if isinstance(x, dict): return {k: deep(v, nations) for k, v in x.items()}
    if isinstance(x, list): return [deep(v, nations) for v in x]
    return grammar(emirati(x), nations)
_TEAMS = {}
def nations(*sides):
    """Arabic names of the national teams among these match sides (teams.json `national`)."""
    if not _TEAMS: _TEAMS.update((get("teams.json") or {}).get("teams", {}) or {"_": {}})
    return [team_ar(t) for t in sides if t and ((_TEAMS.get(str(t.get("id"))) or {}).get("country") or {}).get("national")]
NAT_RULE = "\n- لو الفريق منتخب (اسم دولة مثل الإمارات أو البحرين)، اكتب «منتخب الإمارات» والفعل بعده مذكر («منتخب الإمارات فاز»).\n"

# ---- numbers as Emirati words, for the spoken text only (digits invite Polly/Gemini to read Fusha)
ONES = ["صفر", "واحد", "ثنين", "ثلاث", "أربع", "خمس", "ست", "سبع", "ثمان", "تسع", "عشر", "احدعش", "اثنعش", "ثلطعش", "ربعطعش", "خمسطعش", "سطعش", "سبعطعش", "ثمنطعش", "تسعطعش"]
TENS = {2: "عشرين", 3: "ثلاثين", 4: "أربعين", 5: "خمسين", 6: "ستين", 7: "سبعين", 8: "ثمانين", 9: "تسعين"}
def say(n):
    n = int(n)
    if n < 20: return ONES[n]
    if n < 100: return TENS[n // 10] if n % 10 == 0 else ONES[n % 10] + " و" + TENS[n // 10]
    if n < 1000:
        h = {1: "مية", 2: "ميتين"}.get(n // 100, ONES[n // 100] + "مية"); r = n % 100
        return h if not r else h + " و" + say(r)
    if 2000 <= n < 2100: return "ألفين" + (" و" + say(n - 2000) if n > 2000 else "")
    return str(n)
def spoken(t):
    t = re.sub(r"(\d+)\.(\d)\b", lambda m: say(m.group(1)) + " فاصلة " + say(m.group(2)), t)   # ratings 8.6
    t = re.sub(r"(\d+)\s*-\s*(\d+)", lambda m: say(m.group(1)) + " مقابل " + say(m.group(2)), t)
    t = re.sub(r"(\d+)%", lambda m: say(m.group(1)) + " بالمية", t)
    t = re.sub(r"(\d+)'", lambda m: "الدقيقة " + say(m.group(1)), t)
    return re.sub(r"\d+", lambda m: say(m.group(0)), t)

# ---- context builders: only facts from our files
def team_ar(t): return (t or {}).get("name_ar") or (t or {}).get("name")
def pname(p):   # a player's Arabic name (names/players_ar.json) when we have one, else FotMob's
    p = p or {}; return checks.names_ar().get(str(p.get("id"))) or p.get("name")
def match_facts(md):
    ev = [{"min": e.get("minute"), "type": e.get("type"), "team": team_ar(md[e["team"]]) if e.get("team") in ("home", "away") else None,
           "player": pname(e.get("player")), "assist": pname(e.get("assist")) if e.get("assist") else None, "score": e.get("score")} for e in md.get("events") or [] if e.get("type") not in ("sub", "added_time")]
    stats = {}
    for g in md.get("stats") or []:
        for i in g.get("items", []):
            if i["key"] in ("BallPossesion", "total_shots", "ShotsOnTarget", "big_chance", "corners", "expected_goals", "keeper_saves"): stats[i["key"]] = [i["home"], i["away"]]
    best = []
    for side in ("home", "away"):
        for p in ((md.get("lineups") or {}).get(side) or {}).get("starters") or []:
            if p.get("rating"): best.append({"name": pname(p), "team": team_ar(md[side]), "rating": p["rating"]})
    best.sort(key=lambda x: -x["rating"])
    return {"competition": md.get("comp_name_ar"), "round": md.get("round"), "date": (md.get("kickoff_uae") or "")[:10], "home": team_ar(md["home"]), "away": team_ar(md["away"]),
            "score": md.get("score"), "halftime": md.get("halftime_score"), "venue": (md.get("venue") or {}).get("name_ar"), "events": ev, "stats_home_away": stats, "top_rated": best[:4],
            "head_to_head": (md.get("h2h") or {}).get("summary")}

def table_ctx(st):
    rows = (st or {}).get("groups", [{}])[0].get("rows", [])
    return [{"rank": r["rank"], "team": team_ar(r["team"]), "played": r["played"], "pts": r["pts"], "gd": r["gd"], "form": r.get("form")} for r in rows]

def save(kind, name, obj):
    d = os.path.join(CACHE, kind); os.makedirs(d, exist_ok=True)
    json.dump(obj, open(os.path.join(d, name + ".json"), "w"), ensure_ascii=False, indent=1)

def cached(kind, name, sig):
    f = os.path.join(CACHE, kind, name + ".json")
    if not os.path.exists(f): return False
    try: return json.load(open(f)).get("sig") == sig
    except Exception: return False

# ---- 9 + 78: summary and stats thread for a finished match
SUM_SYS = STYLE + NAT_RULE + """
المهمة: عندك بيانات مباراة خلصت. اكتب:
1) summary: ملخص من 4 لين 6 جمل بالإماراتي، يبدا بالنتيجة ومنو فاز، وبعدين كيف انسجلت الأهداف (منو ومتى)، وأبرز لاعب حسب التقييم، ورقم واحد مهم من الإحصائيات، وسطر أخير عن شو يعني هالنتيجة.
2) thread: ثريد لإكس من 4 لين 6 تغريدات، كل وحدة أقل من 260 حرف، كل تغريدة فيها رقم من البيانات. الأولى فيها النتيجة. بدون هاشتاقات وبدون إيموجي زايد (وحدة بالكثير في التغريدة).
3) headline: عنوان قصير (أقل من 70 حرف).
"""
SUM_SCHEMA = OBJ({"headline": S(80), "summary": S(900), "thread": ARR(S(270), 6)})
def do_summary(md):
    ctx = match_facts(md); sig = hashlib.sha1(json.dumps(ctx, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    if cached("summary", str(md["id"]), sig): return "cached"
    out = gemini(SUM_SYS, ctx, SUM_SCHEMA, tokens=8000, kind="summary")
    if not out: return "fail"
    out = deep(out, nations(md["home"], md["away"]))
    out["summary"] = vet_text(out.get("summary", ""), md, ctx, f"summary {md['id']}")
    out["thread"] = vet(list(out.get("thread") or []), md, ctx, f"thread {md['id']}", 0) or []
    out["headline"] = (vet([out.get("headline", "")], md, ctx, f"headline {md['id']}") or [""])[0]
    if len(re.findall(r"[.!؟]", out["summary"])) < 2 or len(out["thread"]) < 3: print(f"summary {md['id']} dropped: too little left after checks", file=sys.stderr); return "dropped"
    bad = check_result(" ".join([out.get("headline", ""), out.get("summary", "")] + list(out.get("thread") or [])), md)
    bad = bad or check_table(" ".join([out.get("summary", "")] + list(out.get("thread") or [])), table_rows(get(f"comp/{md.get('comp')}/standings.json")))
    if bad: print(f"summary {md['id']} dropped: {bad}", file=sys.stderr); return "dropped"
    out.update({"id": md["id"], "sig": sig, "model": LAST_MODEL[0], "generated": dt.datetime.utcnow().isoformat() + "Z"})
    save("summary", str(md["id"]), out); return "new"

# ---- 77: preview for a coming match
PRE_SYS = STYLE + NAT_RULE + """
المهمة: عندك بيانات مباراة ياية: ترتيب الفريقين وفورمتهم، ونسب توقعات تيفو، والمواجهات السابقة، وأرقام على المحك، وضغط المباريات.
اكتب lines: 5 أسطر بالضبط، كل سطر جملة وحدة (أقل من 200 حرف):
1) الفريق الأول: نقطة قوة من الأرقام.  2) الفريق الثاني: نقطة قوة من الأرقام.  3) نقطة ضعف أو قلق لواحد منهم.  4) مفتاح المباراة.  5) توقع تيفو بالنسب مقرّبة لأقرب رقم صحيح (بدون فواصل عشرية)، بدون ما تجزم. إذا النسب مب موجودة في البيانات، خل السطر الخامس عن فورمة الفريقين أو أرقام على المحك بدل النسب، ولا تقول إنها مب متوفرة.
"""
PRE_SCHEMA = OBJ({"lines": ARR(S(220), 5)})
def do_preview(m, ctx):
    sig = hashlib.sha1(json.dumps(ctx, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    if cached("preview", str(m["id"]), sig): return "cached"
    out = gemini(PRE_SYS, ctx, PRE_SCHEMA, temp=0.5, kind="preview")
    if not out: return "fail"
    out = deep(out, nations(m["home"], m["away"]))
    rows = {t: {"rank": (ctx.get(k) or {}).get("rank"), "pts": (ctx.get(k) or {}).get("pts")} for t, k in ((team_ar(m["home"]), "home_table"), (team_ar(m["away"]), "away_table")) if ctx.get(k)}
    out["lines"] = keep_lines(out.get("lines") or [], rows, 4, f"preview {m['id']}", ctx)
    if not out["lines"]: return "dropped"
    out.update({"id": m["id"], "sig": sig, "model": LAST_MODEL[0], "generated": dt.datetime.utcnow().isoformat() + "Z"})
    save("preview", str(m["id"]), out); return "new"

# ---- 161: Tifo Cast, written for the ear, then voiced with Gemini TTS (ai/cast_voice.py)
POD_SYS = STYLE + """
المهمة: حلقة «تيفو كاست» الأسبوعية، حوار بين حامد ومها (صديقين يسولفون عن الجولة)، حوالي 5 دقايق (600 لين 750 كلمة).
- حامد يبدا: «هلا والله، معاكم حامد» ومها تسلّم.
- الاثنين يكلّمون المستمع بصيغة المذكر المفرد (عليك، لك، شفت).
- حامد ومها ما يخاطبون بعض أبداً (لا «انت» ولا «رايك» ولا «عليج» ولا «يا مها»). كل واحد يتكلم عن الثاني بصيغة الغايب وبالاسم، مثلاً «مها عندها رقم حلو هني» أو «حامد يقول إن…»، وكلامهم موجّه للمستمع.
- في سطور حامد (who = hamed) ممنوع كلمة «الحين» نهائياً: استعمل «يلا» أو غيّر صياغة الجملة. مها عادي تقولها.
- كل واحد يتكلم عن نفسه بصيغة المتكلم دايماً («أنا أتوقع»، «حابة أذكّرك»)، وما يذكر اسمه هو عن نفسه (لا «مها تتوقع» على لسان مها).
- اكتب عبارات عربية سليمة وواضحة، كل جملة لها معنى كامل. لا تركّب كلمات غريبة أو ناقصة.
- الأرقام تنكتب أرقام.
- أقسام: نتايج الجولة، أحلى لحظة، لاعب الجولة (من التقييمات)، الترتيب وتوقعات تيفو، مباراة الجولة الياية اللي لازم تنشاف.
- سطور قصيرة متبادلة (12 لين 24 سطر)، كل سطر أقل من 400 حرف. طنازة خفيفة مسموحة، بس لا تخترع أي معلومة.
"""
POD_SCHEMA = OBJ({"title": S(80), "lines": ARR(OBJ({"who": {"type": "STRING", "enum": ["hamed", "maha"]}, "text": S(420)}), 24)})

def round_ctx(fx, st, detail):
    rounds = {}
    for m in fx.get("matches", []): rounds.setdefault(m.get("round"), []).append(m)
    done = [k for k, ms in rounds.items() if k and all(x.get("status") == "finished" for x in ms)]
    if not done: return None, None
    k = max(done, key=lambda r: float(r))
    ms = []
    for m in rounds[k]:
        d = detail(m["id"]) or m
        goals = [{"min": e["minute"], "player": (e.get("player") or {}).get("name"), "team": team_ar(d[e["team"]])} for e in d.get("events") or [] if "goal" in (e.get("type") or "") and e.get("team") in ("home", "away")]
        ms.append({"home": team_ar(m["home"]), "away": team_ar(m["away"]), "score": m.get("score"), "goals": goals})
    nxt = [{"home": team_ar(m["home"]), "away": team_ar(m["away"]), "date": (m.get("kickoff_uae") or "")[:10]} for m in rounds.get(str(int(float(k)) + 1), [])]
    return k, {"round": k, "matches": ms, "table": table_ctx(st)[:14], "next_round": nxt}

def mail_held(jf):
    """341: tell the owner once per held week (SES ap-south-1, tifo@ -> hello@); the flag in the json stops repeats."""
    ep = json.load(open(jf))
    if not ep.get("held") or ep.get("held_mailed"): return
    try:
        import boto3
        body = f"تيفو كاست أسبوع {ep.get('week')} ما انتشر.\n\nالسبب: {ep['held']}\n\nالحلقة في cache/ai/podcast/{ep.get('week')}.json، والموقع يعرض حلقة الأسبوع الماضي."
        boto3.client("ses", region_name="ap-south-1").send_email(Source="تيفو <tifo@elyoxe.com>", Destination={"ToAddresses": ["hello@elyoxe.com"]},
            Message={"Subject": {"Data": f"تيفو كاست {ep.get('week')}: الحلقة موقوفة", "Charset": "UTF-8"}, "Body": {"Text": {"Data": body, "Charset": "UTF-8"}}})
        ep["held_mailed"] = dt.datetime.utcnow().isoformat() + "Z"; json.dump(ep, open(jf, "w"), ensure_ascii=False, indent=1)
    except Exception as e: print("podcast held mail failed:", str(e)[:200], file=sys.stderr)

def do_podcast(ctx, audio):
    wk = dt.date.today().strftime("%G-%V"); sig = hashlib.sha1(json.dumps(ctx, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    jf, mp3 = os.path.join(CACHE, "podcast", wk + ".json"), os.path.join(CACHE, "podcast", wk + ".mp3")
    if cached("podcast", wk, sig):
        if json.load(open(jf)).get("held"): mail_held(jf); return "held"   # mails only if the first send failed   # this week failed a gate: no new script or TTS spend until next week
        if not audio or os.path.exists(mp3): return "cached"
    # Orus reads «الحين» as «الآن»: a Hamed line with it means a new script (2 retries), else no episode this week
    for attempt in range(3):
        out = gemini(POD_SYS, ctx, POD_SCHEMA, temp=0.8, tokens=12000, kind="podcast")
        if not out: return "fail"
        # both hosts address the listener in the masculine and each other by name only, so one lexicon pass fits every line
        lines = []
        for l in out["lines"]:
            t = emirati(l["text"]); lines.append({"who": l["who"], "text": t, "spoken": spoken(t)})
        leak = [n for n, l in enumerate(lines) if l["who"] == "hamed" and "الحين" in l["text"]]
        if not leak: break
        print(f"podcast {wk}: «الحين» in Hamed lines {leak}, attempt {attempt + 1}", file=sys.stderr)
    rec = {"week": wk, "title": emirati(out["title"]), "lines": lines, "sig": sig, "model": LAST_MODEL[0], "generated": dt.datetime.utcnow().isoformat() + "Z"}
    if leak: rec["held"] = f"«الحين» still in Hamed lines {leak} after 3 scripts; no audio this week"
    save("podcast", wk, rec)
    if leak: print("podcast held:", rec["held"], file=sys.stderr); mail_held(jf); return "held"
    if audio:   # Gemini TTS (Orus = حامد, Aoede = مها): writes the mp3 next to the json and adds qa/voices
        from cast_voice import synth
        synth(jf)
        ep = json.load(open(jf)); bad = [q["line"] for q in ep.get("qa", []) if not q.get("take") or q.get("flags")]
        if bad:   # a flagged line: this week's mp3 is set aside, the site keeps last week's episode
            os.replace(mp3, os.path.join(CACHE, "podcast", wk + ".held.mp3")) if os.path.exists(mp3) else None
            ep["held"] = f"TTS QA flagged lines {bad}; mp3 kept as {wk}.held.mp3, not published"; json.dump(ep, open(jf, "w"), ensure_ascii=False, indent=1)
            print("podcast held:", ep["held"], file=sys.stderr); mail_held(jf); return "held"
    return "new"

# ---- 196: written live commentary for UAE matches, one line per event (substitutions of one team in one minute = one line)
COM_SYS = STYLE + """
المهمة: تعليق مباشر مكتوب. لكل حدث في events اكتب سطر واحد (أقل من 140 حرف) كأنك تكتب لحظة الحدث، بدون ما تعرف اللي بيصير بعده.
استعمل الدقيقة والنتيجة بعد الحدث إذا موجودة. نفس ترتيب الأحداث ونفس event_id.
- الحدث من نوع subs فيه أكثر من تبديل لنفس الفريق في نفس الدقيقة: سطر واحد يذكرهم كلهم، مثلاً «تبديلين للوحدة في الدقيقة 82: فلان وفلان».
- لا تكرر نفس صياغة البداية في سطرين ورا بعض.
"""
COM_SCHEMA = OBJ({"lines": ARR(OBJ({"event_id": S(80), "text": S(200)}), 60)})
def commentary_events(md):
    ev = []
    for e in md.get("events") or []:
        if not e.get("event_id") or e.get("type") in ("added_time",): continue
        side = e.get("team") if e.get("team") in ("home", "away") else None
        x = {"event_id": e["event_id"], "min": e.get("minute"), "type": e.get("type"), "team": team_ar(md[side]) if side else None, "player": (e.get("player") or {}).get("name"), "score": e.get("score")}
        if e.get("type") == "sub":
            prev = next((p for p in reversed(ev[-4:]) if p["type"] in ("sub", "subs") and p["team"] == x["team"] and p["min"] == x["min"]), None)
            if prev:
                if prev["type"] == "sub": prev.update(type="subs", players=[prev.pop("player")], event_ids=[prev["event_id"]]); prev.pop("player_off", None)
                prev["players"].append(x["player"]); prev["event_ids"].append(x["event_id"]); continue
            x["player_off"] = (e.get("player_out") or {}).get("name")
        ev.append(x)
    return ev
def do_commentary(md):
    ev = commentary_events(md)
    if not ev: return "none"
    ctx = {"home": team_ar(md["home"]), "away": team_ar(md["away"]), "competition": md.get("comp_name_ar"), "events": ev}
    sig = hashlib.sha1(json.dumps(ctx, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    if cached("commentary", str(md["id"]), sig): return "cached"
    out = gemini(COM_SYS, ctx, COM_SCHEMA, temp=0.6, tokens=12000, kind="commentary")
    if not out: return "fail"
    ids = {e["event_id"] for e in ev}; lines = [{"event_id": l["event_id"], "text": emirati(l["text"])} for l in out["lines"] if l["event_id"] in ids]
    by = {e["event_id"]: e for e in ev}
    for l in lines: l["min"] = by[l["event_id"]].get("min")
    save("commentary", str(md["id"]), {"id": md["id"], "status": md.get("status"), "lines": lines, "sig": sig, "model": LAST_MODEL[0], "generated": dt.datetime.utcnow().isoformat() + "Z"}); return "new"

# ---- 197: a club's week (UAE league clubs), facts only
DIG_SYS = STYLE + """
المهمة: نشرة أسبوعية لمشجع نادي واحد: title عنوان قصير، وparas 3 فقرات قصيرة (كل وحدة جملتين لين ثلاث):
1) نتايج الأسبوع.  2) وين واقف في ترتيب الدوري والفورمة.  3) المباراة الياية وموعدها بتوقيت الإمارات.
- league_table هو ترتيب الدوري. لو نتيجة الأسبوع من كأس، قول «في الدوري» صراحة لما تذكر المركز والنقاط، عشان ما يختلط الكأس بالدوري.
- كل جملة فيها معلومة من البيانات المرفقة. لا تتوقع ولا تفترض شي مب فيها (مثل ذهاب وإياب أو نظام البطولة)، ولا تكتب جمل حشو أو تمنيات.
- لو ما في نتايج هالأسبوع، قول إن الفريق ما لعب هالأسبوع بجملة وحدة.
- كل جملة لازم فيها رقم أو تاريخ أو اسم فريق من البيانات. ممنوع التشجيع والنصايح والتمنيات للمشجع («خلك جاهز»، «نتمنى»، «لازم يركز»، «هذي الكورة»).
- اكتب عربي سليم وواضح، ولا تذكر فارق الأهداف إلا بصيغة «فارق أهدافه +1» أو «فارق أهدافه -2».
"""
def facts_only(p):   # drops sentences that carry no number (the owner's no-filler rule for 197)
    parts = re.split(r"(?<=[.!؟])\s+", p.strip())
    return " ".join(x for x in parts if re.search(r"\d", x)) or p
DIG_SCHEMA = OBJ({"title": S(80), "paras": ARR(S(420), 3)})
def do_digest(team_id, st, league_name):
    t = get(f"team/{team_id}.json")
    if not t: return "none"
    fx = t.get("fixtures") or []; now = dt.datetime.utcnow(); cut = (now - dt.timedelta(days=7)).isoformat()
    past = [m for m in fx if m.get("status") == "finished" and (m.get("kickoff_utc") or "") >= cut]
    nxt = next((m for m in sorted(fx, key=lambda m: m.get("kickoff_utc") or "") if m.get("status") == "scheduled" and (m.get("kickoff_utc") or "") > now.isoformat()), None)
    row = next((r for r in table_ctx(st) if r["team"] == team_ar(t)), None)
    ctx = {"team": team_ar(t), "results_last_7_days": [{"home": team_ar(m["home"]), "away": team_ar(m["away"]), "score": m.get("score"), "competition": m.get("comp_name_ar")} for m in past],
           "league_table": row and dict(row, league=league_name), "next_match": nxt and {"home": team_ar(nxt["home"]), "away": team_ar(nxt["away"]), "kickoff_uae": nxt.get("kickoff_uae"), "competition": nxt.get("comp_name_ar")}}
    wk = dt.date.today().strftime("%G-%V"); sig = hashlib.sha1(json.dumps([wk, ctx], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    if cached("digest", str(team_id), sig): return "cached"
    out = gemini(DIG_SYS, ctx, DIG_SCHEMA, temp=0.3, tokens=6000, kind="digest")
    if not out: return "fail"
    out = deep(out); out["paras"] = keep_lines([facts_only(x) for x in out["paras"]], table_rows(st), 2, f"digest {team_id}", ctx)
    if not out["paras"]: return "dropped"
    out.update({"team": team_id, "week": wk, "sig": sig, "model": LAST_MODEL[0], "generated": dt.datetime.utcnow().isoformat() + "Z"}); save("digest", str(team_id), out); return "new"

# ---- 231: weekly power ranking; the order is the Tifo rating, the model only explains each place
POW_SYS = STYLE + """
المهمة: ترتيب القوة الأسبوعي. عندك الأندية مرتبة سلفاً بتصنيف تيفو (لا تغيّر الترتيب)، ومع كل نادي ترتيبه في الدوري وفورمته وكم تغيّر تصنيفه في آخر 5 مباريات (rating_change_last5).
لكل نادي اكتب line: جملة وحدة (أقل من 150 حرف) تشرح مكانه من الأرقام المرفقة بس. نفس الترتيب ونفس team_id.
- تغيّر التصنيف مجموع آخر 5 مباريات مب معدل: قول «ارتفع تصنيفه بـ 20.5 نقطة» ولا تقول «بمعدل».
"""
POW_SCHEMA = OBJ({"title": S(80), "rows": ARR(OBJ({"team_id": {"type": "INTEGER"}, "line": S(170)}), 24)})
POWER_SRC = {538: ("ratings/uae-clubs.json", "دوري أدنوك للمحترفين")}
def do_power(comp):
    src, league = POWER_SRC[comp]; rt = get(src) or {}; st = get(f"comp/{comp}/standings.json")
    teams = [t for t in rt.get("teams", []) if t.get("in_league")]
    if not teams: return "none"
    tab = {r["team"]: r for r in table_ctx(st)}
    rows = [{"team_id": t["team"], "team": t.get("name_ar"), "tifo_rating": round(t.get("rating") or 0), "rating_change_last5": t.get("change_5"), "league_table": tab.get(t.get("name_ar"))} for t in teams]
    wk = dt.date.today().strftime("%G-%V"); name = f"{comp}-{wk}"; sig = hashlib.sha1(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    if cached("power", name, sig): return "cached"
    out = gemini(POW_SYS, {"league": league, "clubs_in_order": rows}, POW_SCHEMA, temp=0.5, tokens=8000, kind="power")
    if not out: return "fail"
    tr = table_rows(st); lines = {}
    for r in out["rows"]:
        l = emirati(r["line"]).replace("بمعدل ", "بـ "); bad = check_table(l, tr) or checks.check_history(l, {"clubs_in_order": rows})
        if bad: print(f"power {comp}: line dropped ({bad}): {l[:80]}", file=sys.stderr)
        else: lines[r["team_id"]] = l
    if len(lines) < len(rows) / 2: return "dropped"
    save("power", name, {"comp": comp, "week": wk, "title": emirati(out["title"]), "rows": [dict(r, line=lines.get(r["team_id"], "")) for r in rows], "sig": sig, "model": LAST_MODEL[0], "generated": dt.datetime.utcnow().isoformat() + "Z"}); return "new"

# ---- 369 «ليش هالنتيجة؟» (why) and 372 «مباراة الليلة في 60 ثانية» (quick), approved 2026-09-27. Files:
#   why/{match}.json   {id, comp, home, away, score:{home,away}, lines:[2 strings], sig, model, generated}
#   quick/{match}.json {id, comp, home, away, kickoff_utc, lines:[4-6 strings], sig, model, generated}   (home/away = team ids)
WHY_SYS = STYLE + NAT_RULE + """
المهمة: «ليش هالنتيجة؟» لمباراة خلصت. اكتب lines: سطرين بالضبط، كل سطر جملة وحدة أقل من 150 حرف، تشرح ليش انتهت المباراة جذيه من الأرقام المرفقة بس
(الاستحواذ، التسديدات، التسديدات على المرمى، الفرص المحققة، الأهداف المتوقعة إذا موجودة، الطرد، البلنتي، توقيت الأهداف).
- كل سطر لازم فيه رقم واحد على الأقل من البيانات. مثال على الأسلوب: «سيطر الوحدة على الاستحواذ 61% بس ضيّع 3 فرص محققة».
- كل سطر عن فريق واحد بجملة قصيرة. لا تربط الفريقين في نفس الجملة بـ«بس» أو «رغم» (مثل «X سيطر… بس سجّل Y…»)، خلّ كل فريق في سطره.
- لا تفترض أي سبب مب ظاهر في الأرقام (تعب، معنويات، تكتيك، حكم)، ولا تكتب حشو أو مديح.
- stats_home_away: الرقم الأول للمستضيف (home) والثاني للضيف (away).
- الحدث own_goal: لاعب من scorer_team سجل بالخطأ في مرمى فريقه، والهدف ينحسب لـ goal_for. قول «هدف عكسي لصالح goal_for».
- انتبه لفريق كل لاعب (team) قبل ما تربطه بأي فريق.
- winner وloser فيهم الفايز والخسران وأهداف كل واحد (لو تعادل، draw صح). السطر الأول عن الفايز لو في فايز. لا تغيّر أي نتيجة.
- لا تذكر عدد صفر كإنجاز («0 فرص»، «أكثر عن 0»، «كانت 0»). قول «ما صنع أي فرصة محققة».
- لو ذكرت عدد التسديدات مع الأهداف، اكتبها عن الفريق بدون اسم الهداف وبدون «عقب» أو «من أصل»، بهالشكل بالضبط: «سجّل الشحانية هدفه الوحيد من 4 تسديدات على المرمى».
"""
WHY_SCHEMA = OBJ({"lines": ARR(S(170), 2)})
# deterministic checks on generated result text (369, summary): a named side's goal count and «فاز/خسر» must match the score
ZERO = re.compile(r"(?:أكثر (?:عن|من) 0|\b0 (?:فرص|فرصة|تسديدة|تسديدات|أهداف|هدف)|(?:كانت|كان|وصلت) 0(?!\.)(?!\d))")
def _goals_word(w):
    return {"هدفين": 2, "هدفه الوحيد": 1, "هدف واحد": 1, "هدف وحيد": 1}.get(w) if not w.isdigit() else int(w)
def check_result(text, md):
    """None when the text agrees with the score, else the reason. Uses both sides' Arabic names."""
    H, A = team_ar(md["home"]), team_ar(md["away"]); sc = md.get("score") or {}; g = {H: sc.get("home"), A: sc.get("away")}
    if g[H] is None or g[A] is None or H == A: return None
    win = H if g[H] > g[A] else A if g[A] > g[H] else None; lose = (A if win == H else H) if win else None
    for n in (H, A):
        N = re.escape(n)
        for m in re.finditer(r"سج[ّ]?ل\s+(?:منتخب\s+)?" + N + r"\s+(\d+|هدفين|هدفه الوحيد|هدف واحد)", text):
            if _goals_word(m.group(1)) != g[n]: return f"{n} goals {m.group(1)} != {g[n]}"
        for m in re.finditer(r"(?:منتخب\s+)?" + N + r"\s+(?:\S+\s+){0,3}?(?:سج[ّ]?ل\s+)?(\d+) (?:أهداف|هدف)(?!\s*(?:متوقع|من))", text):
            if int(m.group(1)) != g[n]: return f"{n} goals {m.group(1)} != {g[n]}"
        if re.search(r"(?:^|[\s،.])(?:منتخب\s+)?" + N + r"\s+(?:\S+\s+){0,1}?فاز", text) and win != n: return f"{n} فاز but result {sc}"
        if re.search(r"فاز\s+(?:منتخب\s+)?" + N + r"(?!\w)", text) and win != n: return f"فاز {n} but result {sc}"
        if re.search(r"(?:^|[\s،.])(?:منتخب\s+)?" + N + r"\s+(?:\S+\s+){0,1}?خسر", text) and lose != n: return f"{n} خسر but result {sc}"
    return None

# rank/points guard (preview, quick, digest, power, summary): «المركز/مركز N», «N نقاط/نقطة», «برصيد N», «نقطة وحدة» near a
# team name must match that team's row; «يتصدر/المتصدر» only for rank 1 (group leader in group competitions)
def table_rows(st):
    """{Arabic name: {rank, pts}} for every row of every group of a standings file."""
    out = {}
    for g in (st or {}).get("groups", []) or []:
        for r in g.get("rows", []): out[team_ar(r["team"])] = {"rank": r.get("rank"), "pts": r.get("pts")}
    return out
def check_table(text, rows):
    """None when every rank/points claim agrees with the table, else the reason."""
    names = sorted([n for n in rows if n], key=len, reverse=True)
    if not names or not isinstance(text, str): return None
    hits = sorted((m.start(), m.end(), n) for n in names for m in re.finditer(r"(?<!\w)(?:و|ل|ب)?" + re.escape(n) + r"(?!\w)", text))
    hits = [h for i, h in enumerate(hits) if not any(o[0] <= h[0] and h[1] <= o[1] and o != h for o in hits)]   # «الأهلي» inside «شباب الأهلي»
    for i, (a, b, n) in enumerate(hits):
        stop = min([h[0] for h in hits[i + 1:]] + [len(text)] + [b + k.start() for k in [re.search(r"[.؛!؟\n]", text[b:])] if k])
        win, pre, r = text[b:stop], text[max(0, a - 12):a], rows[n]
        for m in re.finditer(r"(?:ال)?مركز\s+(\d+)", win):
            if r["rank"] is not None and int(m.group(1)) != r["rank"]: return f"{n} rank {m.group(1)} != {r['rank']}"
        for m in re.finditer(r"(?:برصيد\s+|بـ\s*|وعنده\s+|عنده\s+)?(\d+)\s+(?:نقاط|نقطة)|برصيد\s+(\d+)", win):
            v = int(m.group(1) or m.group(2))
            if r["pts"] is not None and v != r["pts"] and not re.search(r"(?:فارق|بفارق|ب?ـ?\s*فرق)\s*$", win[:m.start()]): return f"{n} pts {v} != {r['pts']}"
        if re.search(r"نقطة وحدة", win) and r["pts"] not in (None, 1): return f"{n} pts 1 != {r['pts']}"
        if (re.search(r"(?<!عن )(?<!من )(?<!على )(?<!ورا )(?<!خلف )(?<!لـ)(?<!و)(?<!\w)(?:يتصدر|المتصدر|متصدر|تصد[ّ]?ر(?:ت)?|الصدارة)", win[:70]) or re.search(r"المتصدر\s*$|يتصدر\s*$|تصد[ّ]?ر(?:ت)?\s*$", pre)) and r["rank"] not in (None, 1): return f"{n} leader but rank {r['rank']}"
    return None
def keep_lines(lines, rows, minimum, what, evidence=None):
    ok = []
    for l in lines:
        bad = check_table(l, rows) or (checks.check_history(l, evidence) if evidence is not None else None)
        if bad: print(f"{what}: line dropped ({bad}): {l[:80]}", file=sys.stderr)
        else: ok.append(l)
    return ok if len(ok) >= minimum else None

def vet(lines, md=None, evidence=None, what="", minimum=1):
    """Every generated line through the fact checks (checks.py + check_result + check_table is done by callers).
    Returns the kept lines, or None when fewer than `minimum` survive. Drops are logged."""
    players = checks.match_players(md) if md else {}; out = []
    for l in lines:
        why = None
        if md:
            l, left = checks.arabic_names(l, players)
            if left: why = "Latin name left: " + " ".join(left[:3])
            if not why:
                why, rest = checks.check_halves(l, md)
                why = why or check_result(rest, md) or checks.check_events(l, md, players)
        why = why or checks.check_history(l, evidence)
        if why: print(f"{what}: line dropped ({why}): {l[:90]}", file=sys.stderr)
        else: out.append(l)
    return out if len(out) >= minimum else None
def vet_text(text, md=None, evidence=None, what=""):
    """Sentence-level vet for a paragraph (summary): failing sentences are cut out."""
    parts = re.split(r"(?<=[.!؟])\s+", text or ""); kept = vet(parts, md, evidence, what, 0) or []
    return " ".join(kept)

def do_why(md):
    ctx = match_facts(md)
    if not ctx.get("stats_home_away"): return "no stats"
    for e in ctx["events"]:   # own goals: FotMob files the event under the side it counted FOR (checked: 1000020522, 5868079)
        if e["type"] == "own_goal": e["goal_for"] = e["team"]; e["scorer_team"] = ctx["away"] if e["team"] == ctx["home"] else ctx["home"]
    sc = md.get("score") or {}; gh, ga = sc.get("home"), sc.get("away")
    if gh is None or ga is None: return "no score"
    H, A = ctx["home"], ctx["away"]
    ctx["result"] = {"draw": gh == ga, "winner": {"team": H if gh > ga else A, "goals": max(gh, ga)} if gh != ga else None, "loser": {"team": A if gh > ga else H, "goals": min(gh, ga)} if gh != ga else None,
                     "draw_goals_each": gh if gh == ga else None}
    sig = hashlib.sha1(json.dumps(ctx, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    if cached("why", str(md["id"]), sig): return "cached"
    out = gemini(WHY_SYS, ctx, WHY_SCHEMA, temp=0.3, tokens=4000, kind="why")
    if not out: return "fail"
    lines = [fix(grammar(emirati(l), nations(md["home"], md["away"]))) for l in out["lines"]]
    for l in [l for l in lines if ZERO.search(l)]: print(f"why {md['id']}: zero-count line dropped: {l[:80]}", file=sys.stderr)
    lines = [l for l in lines if not ZERO.search(l)]
    lines = vet(lines, md, ctx, f"why {md['id']}", 0) or []; bad = None
    win = ctx["result"]["winner"] and ctx["result"]["winner"]["team"]
    if not bad and win and lines and win not in lines[0] and len(lines) > 1 and win in lines[1]: lines.reverse()   # the winner first
    if bad or len(lines) < 2 or (win and win not in lines[0]):
        print(f"why {md['id']} dropped: {bad or 'zero-count or winner line'}", file=sys.stderr)
        f = os.path.join(CACHE, "why", f"{md['id']}.json")
        if os.path.exists(f): os.remove(f)
        return "dropped"
    save("why", str(md["id"]), {"id": md["id"], "comp": md.get("comp"), "home": md["home"]["id"], "away": md["away"]["id"], "score": md.get("score"), "lines": lines, "sig": sig, "model": LAST_MODEL[0], "generated": dt.datetime.utcnow().isoformat() + "Z"}); return "new"

QUICK_SYS = STYLE + NAT_RULE + """
المهمة: «مباراة الليلة في 60 ثانية»: بطاقة سريعة قبل مباراة كبيرة. اكتب lines: من 4 لين 6 أسطر، كل سطر جملة وحدة أقل من 140 حرف:
الموعد، وضع الفريقين في الترتيب وفورمتهم، المواجهات السابقة (h2h)، وتوقع تيفو بالنسب إذا موجود. بس هذي الأربعة، ولا شي غيرها.
- كل سطر فيه رقم من البيانات. لو ما في توقع تيفو، لا تذكر أي توقع. سمّها «توقعات تيفو» دايماً.
- الموعد اكتبه حرفياً كما في kickoff_label (مثلاً «الجمعة 16 أكتوبر، 17:05») مع «بتوقيت الإمارات»، وقول «الليلة» بس لو is_tonight صح.
- المجموعة اكتبها كما في group_ar.
- لو المعلومات ما تكفي لـ 6 أسطر، اكتب 4 بس. لا تكرر نفس المعلومة بصيغتين، ولا تكتب سطر بدون معلومة («عين الفريق على الفوز»).
- ممنوع أي لغة مراهنات (أودز، رهان، ضمان، «أكيد بيفوز»، نصايح توقع). ممنوع الحشو.
"""
QUICK_SCHEMA = OBJ({"lines": ARR(S(160), 6)})
AR_DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]; AR_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
GROUP_AR = {"A": "المجموعة الأولى", "B": "المجموعة الثانية", "C": "المجموعة الثالثة", "D": "المجموعة الرابعة"}
def label(iso):   # «الجمعة 16 أكتوبر، 17:05» (UAE time): the one date format of these cards
    if len(iso) < 16: return ""
    d = dt.date.fromisoformat(iso[:10]); return f"{AR_DAYS[d.weekday()]} {d.day} {AR_MONTHS[d.month - 1]}، {iso[11:16]}"
FIX = [("بتبدأ", "بتبدا"), ("تبدأ", "تبدا"), ("يبدأ", "يبدا"), ("بيبدأ", "بيبدا")]
def fix(t):
    for a, b in FIX: t = t.replace(a, b)
    return t
def do_quick(m, table):
    md = get(f"match/{m['id']}.json") or m
    rows = {}
    for g in (table or {}).get("groups", []):   # the group that holds either team (Gulf Cup has two)
        for r in g.get("rows", []): rows[team_ar(r["team"])] = {"rank": r["rank"], "played": r["played"], "pts": r["pts"], "gd": r.get("gd"), "form": r.get("form"), "group_ar": GROUP_AR.get(str(g.get("name") or "").replace("Grp. ", "").replace("Group ", "").strip())}
    H, A = team_ar(m["home"]), team_ar(m["away"])
    ctx = {"competition": m.get("comp_name_ar") or md.get("comp_name_ar"), "home": H, "away": A, "kickoff_label": label(m.get("kickoff_uae") or ""),
           "is_tonight": (m.get("kickoff_uae") or "")[:10] == (dt.datetime.utcnow() + dt.timedelta(hours=4)).strftime("%Y-%m-%d"),
           "tifo_probabilities": {k: v for k, v in (m.get("probs") or md.get("probs") or {}).items() if k in ("home", "draw", "away")} or None, "home_table": rows.get(H), "away_table": rows.get(A),
           "head_to_head": (md.get("h2h") or {}).get("summary")}
    sig = hashlib.sha1(json.dumps(ctx, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    if cached("quick", str(m["id"]), sig): return "cached"
    out = gemini(QUICK_SYS, ctx, QUICK_SCHEMA, temp=0.3, tokens=4000, kind="quick")
    if not out: return "fail"
    qall = [fix(grammar(emirati(l), nations(m["home"], m["away"]))) for l in out["lines"]]
    for x in [x for x in qall if ZERO.search(x)]: print(f"quick {m['id']}: zero-count line dropped: {x[:80]}", file=sys.stderr)
    qlines = keep_lines([x for x in qall if not ZERO.search(x)], table_rows(table), 4, f"quick {m['id']}", ctx)
    if not qlines: return "dropped"
    save("quick", str(m["id"]), {"id": m["id"], "comp": m.get("comp"), "home": m["home"]["id"], "away": m["away"]["id"], "kickoff_utc": m.get("kickoff_utc"), "lines": qlines, "sig": sig, "model": LAST_MODEL[0], "generated": dt.datetime.utcnow().isoformat() + "Z"}); return "new"


# ---- 301: «أهم 5 أشياء اليوم» on the home page (gated like every generated text)
D5_SYS = STYLE + """
المهمة: عندك مباريات اليوم (عربية أول) وأرقام على المحك. اكتب items: 5 أسطر بالضبط، كل سطر جملة وحدة أقل من 150 حرف،
كل سطر عن شي يستاهل المشجع العربي يعرفه اليوم (مباراة مهمة وموعدها بتوقيت الإمارات، رقم قياسي على المحك، مباراة منتخب).
الأولوية: منتخبات عربية، ديربيات، القمة في الدوريات العربية، ثم أبطال آسيا وأفريقيا، ثم أوروبا. لا تخترع أي شي.
"""
D5_SCHEMA = OBJ({"items": ARR(S(170), 5)})
def do_daily5():
    today = (dt.datetime.utcnow() + dt.timedelta(hours=4)).strftime("%Y%m%d")
    day = get(f"day/{today}.json") or {"matches": []}
    ms = [{"comp": m.get("comp_name_ar"), "home": team_ar(m["home"]), "away": team_ar(m["away"]), "kickoff_uae": (m.get("kickoff_uae") or "")[11:16], "probs": m.get("probs")} for m in day.get("matches", []) if m.get("status") == "scheduled"][:40]
    facts = []
    for c in (538,):
        fm = (get(f"comp/{c}/facts.json") or {}).get("matches", {})
        for m in day.get("matches", []):
            facts += [f.get("text_ar") for f in fm.get(str(m["id"]), []) if f.get("record_at_stake")]
    ctx = {"date": today, "matches": ms, "records_at_stake": facts[:10]}
    if not ms: return "none"
    sig = hashlib.sha1(json.dumps(ctx, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    if cached("daily5", today, sig): return "cached"
    out = gemini(D5_SYS, ctx, D5_SCHEMA, temp=0.5, tokens=4000, kind="daily5")
    if not out: return "fail"
    out = deep(out); out.update({"date": today, "sig": sig, "model": LAST_MODEL[0], "generated": dt.datetime.utcnow().isoformat() + "Z"}); save("daily5", today, out); return "new"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default="summary,preview,podcast,daily5,commentary,digest,power,why,quick"); ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--no-audio", action="store_true"); ap.add_argument("--any-time", action="store_true", help="run podcast outside its Thursday window"); ap.add_argument("--days", type=int, default=10)
    a = ap.parse_args(); only = set(a.only.split(","))
    class Tee:   # the cron job keeps only the last 2 lines; the full run log (drops, fallbacks) goes to cache/ai/_last_run.log
        def __init__(s, *f): s.f = f
        def write(s, x): [f.write(x) for f in s.f]
        def flush(s): [f.flush() for f in s.f]
    os.makedirs(CACHE, exist_ok=True); sys.stderr = Tee(sys.__stderr__, open(os.path.join(CACHE, "_last_run.log"), "w"))
    now = dt.datetime.utcnow(); log = {}
    fx = {c: get(f"comp/{c}/fixtures.json") or {"matches": []} for c in UAE_COMPS}
    st538 = get("comp/538/standings.json"); facts = (get("comp/538/facts.json") or {}).get("matches", {}); fat = (get("comp/538/fatigue.json") or {}).get("teams", {})
    nat = get("team/5789.json") or {"fixtures": []}
    allm = [m for c in UAE_COMPS for m in fx[c]["matches"]] + [m for m in nat.get("fixtures", []) if m.get("comp") not in UAE_COMPS]
    D = {}
    def detail(mid):
        if mid not in D: D[mid] = get(f"match/{mid}.json")
        return D[mid]
    n = 0
    if "summary" in only:
        for m in sorted(allm, key=lambda x: x.get("kickoff_utc") or "", reverse=True):
            if m.get("status") != "finished" or not m.get("kickoff_utc"): continue
            if (now - dt.datetime.fromisoformat(m["kickoff_utc"].replace("Z", ""))).days > a.days: continue
            md = detail(m["id"])
            if not md or not md.get("events"): continue
            r = do_summary(md); log[r] = log.get(r, 0) + 1; n += r == "new"
            if n >= a.limit: break
    if "preview" in only:
        rows = {r["team"]["id"]: r for r in (st538 or {}).get("groups", [{}])[0].get("rows", [])}
        for m in allm:
            if m.get("status") != "scheduled" or not m.get("kickoff_utc"): continue
            dd = (dt.datetime.fromisoformat(m["kickoff_utc"].replace("Z", "")) - now).days
            if dd < 0 or dd > 7: continue
            md = detail(m["id"]) or m
            ctx = {"competition": m.get("comp_name_ar"), "home": team_ar(m["home"]), "away": team_ar(m["away"]), "kickoff_uae": m.get("kickoff_uae"),
                   "tifo_probabilities": m.get("probs") or md.get("probs"), "home_table": rows.get(m["home"]["id"]), "away_table": rows.get(m["away"]["id"]),
                   "head_to_head": (md.get("h2h") or {}).get("summary"), "records_at_stake": [f.get("text_ar") for f in facts.get(str(m["id"]), [])],
                   "fatigue": {"home": fat.get(str(m["home"]["id"])), "away": fat.get(str(m["away"]["id"]))}}
            for k in ("home_table", "away_table"):
                if ctx[k]: ctx[k] = {x: ctx[k].get(x) for x in ("rank", "played", "won", "drawn", "lost", "gf", "ga", "pts", "form")}
            r = do_preview(m, ctx); log["pre-" + r] = log.get("pre-" + r, 0) + 1
    uae = now + dt.timedelta(hours=4)
    if "podcast" in only and not a.any_time and not (uae.weekday() == 3 and 3 <= uae.hour < 6):   # 342: Thursday 03:00-06:00 UAE only, away from the films' TTS quota
        only.discard("podcast"); log["podcast"] = "outside Thursday 03-06 UAE"
    if "podcast" in only:
        k, ctx = round_ctx(fx[538], st538, detail)
        if ctx:
            pc = dict(ctx); sim = get("comp/538/sim.json"); watch = get("comp/538/watch.json")
            if sim: pc["title_odds"] = sorted([{"team": team_ar(next((r["team"] for r in (st538 or {}).get("groups", [{}])[0].get("rows", []) if str(r["team"]["id"]) == t), {})), "title_pct": round(v["title"] * 100)} for t, v in sim["teams"].items()], key=lambda x: -x["title_pct"])[:4]
            if watch: pc["match_to_watch"] = max(watch["matches"].items(), key=lambda kv: kv[1]["score"])[0]
            top = []
            for m in [x for x in fx[538]["matches"] if x.get("round") == k]:
                d = detail(m["id"]) or {}
                for side in ("home", "away"):
                    for p in ((d.get("lineups") or {}).get(side) or {}).get("starters") or []:
                        if p.get("rating"): top.append({"name": p["name"], "team": team_ar(d[side]), "rating": p["rating"]})
            pc["best_players"] = sorted(top, key=lambda x: -x["rating"])[:5]
            log["podcast"] = do_podcast(pc, not a.no_audio)
    if "commentary" in only:   # finished in the last --days, and live now (the hourly run refreshes a live match's lines)
        for m in allm:
            live = m.get("status") not in ("finished", "scheduled", "postponed", "cancelled", None)
            if not live and (m.get("status") != "finished" or not m.get("kickoff_utc") or (now - dt.datetime.fromisoformat(m["kickoff_utc"].replace("Z", ""))).days > a.days): continue
            md = get(f"match/{m['id']}.json") if live else detail(m["id"])
            if md and md.get("events"): r = do_commentary(md); log["com-" + r] = log.get("com-" + r, 0) + 1
    if "digest" in only:
        for r in (st538 or {}).get("groups", [{}])[0].get("rows", []): x = do_digest(r["team"]["id"], st538, "دوري أدنوك للمحترفين"); log["dig-" + x] = log.get("dig-" + x, 0) + 1
    if "power" in only:
        for c in POWER_SRC: log[f"power-{c}"] = do_power(c)
    if "why" in only or "quick" in only:   # 369/372: every Arab league + the big five; 60 new items per kind per run (Gemini quota)
        idx = get("index.json") or {"competitions": []}
        leagues = [c for c in idx["competitions"] if c.get("kind") == "league" and (((c.get("country") or {}).get("iso2") in ARAB) or c["id"] in BIG5)]
        fxs = {c["id"]: (get(f"comp/{c['id']}/fixtures.json") or {"matches": []}) for c in idx["competitions"]}
        if "why" in only:
            fin = [m for c in leagues for m in fxs[c["id"]]["matches"] if m.get("status") == "finished" and m.get("kickoff_utc") and (now - dt.datetime.fromisoformat(m["kickoff_utc"].replace("Z", ""))).days <= a.days]
            n = 0
            for m in sorted(fin, key=lambda m: m["kickoff_utc"], reverse=True):
                if n >= 60: log["why-capped"] = True; break
                md = detail(m["id"])
                if not md or not md.get("stats"): log["why-nostats"] = log.get("why-nostats", 0) + 1; continue
                r = do_why(md); log["why-" + r] = log.get("why-" + r, 0) + 1; n += r == "new"
        if "quick" in only:
            mow = ((get("arabs/match-of-week.json") or {}).get("pick") or {}).get("match")
            pairs = {tuple(sorted(d["teams"])) for d in (get("derbies.json") or {}).get("derbies", [])} | {tuple(sorted(int(x) for x in k.split("-"))) for k in ((get("h2h/index.json") or {}).get("pairs") or {})}
            _ = nations(); tabs = {}
            def big(m):
                if m["id"] == mow or tuple(sorted((m["home"]["id"], m["away"]["id"]))) in pairs: return True
                if any(((_TEAMS.get(str(t["id"])) or {}).get("country") or {}).get("national") and ((_TEAMS.get(str(t["id"])) or {}).get("country") or {}).get("iso2") in ARAB for t in (m["home"], m["away"])): return True
                if m["comp"] not in tabs: tabs[m["comp"]] = get(f"comp/{m['comp']}/standings.json")
                g = ((tabs[m["comp"]] or {}).get("groups") or [{}])[0]; rk = {r["team"]["id"]: r["rank"] for r in g.get("rows", [])}
                return rk.get(m["home"]["id"], 99) <= 4 and rk.get(m["away"]["id"], 99) <= 4
            soon = [m for ms in fxs.values() for m in ms["matches"] if m.get("status") == "scheduled" and m.get("kickoff_utc") and 0 <= (dt.datetime.fromisoformat(m["kickoff_utc"].replace("Z", "")) - now).total_seconds() <= 48 * 3600]
            n = 0; seen = set()
            for m in sorted(soon, key=lambda m: m["kickoff_utc"]):
                if m["id"] in seen or not big(m): continue
                seen.add(m["id"])
                if n >= 60: log["quick-capped"] = True; break
                if m["comp"] not in tabs: tabs[m["comp"]] = get(f"comp/{m['comp']}/standings.json")
                r = do_quick(m, tabs[m["comp"]]); log["quick-" + r] = log.get("quick-" + r, 0) + 1; n += r == "new"
    if "daily5" in only: log["daily5"] = do_daily5()
    if GEMINI_OUT: log["gemini_stopped"] = GEMINI_OUT[0]
    if CLAUDE_STOPPED: log["claude_stopped"] = CLAUDE_STOPPED[0]
    log["provider"] = PROVIDER
    print(json.dumps(log, ensure_ascii=False))

if __name__ == "__main__":
    main()
