"""تيفو phase 5 — written and voiced content from the data (docs/ROADMAP.md phase 5).

  python3 ai/gen.py [--samples] [--only summary,preview,round,podcast] [--limit N]

What it makes (cache/ai/…, read by build.cjs; shown on the site only for kinds switched on in ai/approved.json):
  9  + 78   summary/{match}.json   finished UAE matches: an Emirati summary (4-6 sentences) + a stats thread for X (4-6 posts)
  77        preview/{match}.json   UAE matches in the next 7 days: 5-line Emirati preview (strengths, weaknesses, key)
  19        round/{comp}-{round}.json + .mp3   the last completed Pro League round, voiced by Zayd (Polly neural, ar-AE)
  161       podcast/{yyyy-ww}.json + .mp3      the weekly Tifo Cast: Zayd and Hala talking the round through, ~5 min

Rules (the owner's): Emirati dialect from memory feedback_emirati_dialect + content/video/_system/EMIRATI-LEXICON.json,
applied again after generation; no tanween; male singular address, no ج suffix; facts only from the data handed over.
Nothing is published until the owner approves a sample of each kind (approved.json). Every Gemini schema string has a
maxLength (the loop-until-token-limit trap). Numbers become Emirati words only in the spoken (TTS) text.
"""
import argparse, datetime as dt, hashlib, json, os, re, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
CACHE = os.path.join(SITE, "cache", "ai")
DATA = os.environ.get("TIFO_DATA", "https://d1n5aqaqkowltp.cloudfront.net")
MODEL = os.environ.get("TIFO_MODEL", "gemini-3.5-flash")
LEX = json.load(open(os.path.expanduser("~/workspace/content/video/_system/EMIRATI-LEXICON.json")))
UAE_COMPS = [538, 11027, 9943, 11026]

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
- أسماء اللاعبين اكتبها بالعربي بالطريقة المشهورة في الإعلام الإماراتي.
- في النص المكتوب اكتب كل الأرقام والنتايج والدقايق بالأرقام (0-9) مب بالكلمات: «فاز 3 - 1»، «في الدقيقة 9»، «61%».
- استعمل «فاز على» مب «هزم»، و«عقب» أو «بعدين» للترتيب.
- لا تكتب «رقم 1» أو «1 مرة»: قل «أول فوز»، «مرة وحدة»، «المتصدر».
"""

def gemini(system, payload, schema, temp=0.6, tokens=4000):
    req = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}],
           "generationConfig": {"temperature": temp, "maxOutputTokens": tokens, "responseMimeType": "application/json", "responseSchema": schema}}
    for i in range(3):
        try:
            r = urllib.request.urlopen(urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent", json.dumps(req).encode(),
                                                              {"Content-Type": "application/json", "x-goog-api-key": key()}), timeout=90)
            out = json.loads(r.read())
            return json.loads(out["candidates"][0]["content"]["parts"][0]["text"])
        except Exception as e:
            print("gemini retry", i, str(e)[:200], file=sys.stderr); time.sleep(4 * (i + 1))
    return None

S = lambda n: {"type": "STRING", "maxLength": n}
def OBJ(props): return {"type": "OBJECT", "properties": props, "required": list(props)}
def ARR(item, mx): return {"type": "ARRAY", "items": item, "maxItems": mx}

# ---- the dialect pass after generation (the lexicon, word-bounded; tanween out; masculine address)
FEM = {"عليج": "عليك", "لج": "لك", "إنج": "إنك", "انج": "انك", "فريقج": "فريقك", "بيتج": "بيتك", "راسج": "راسك"}
def emirati(t):
    if not isinstance(t, str): return t
    for a, b in LEX["phrases"].items(): t = t.replace(a, b)
    for a, b in list(LEX["words"].items()) + list(FEM.items()) + [("مين", "منو"), ("كذا", "جذيه")]:
        t = re.sub(r"(?<!\w)" + re.escape(a) + r"(?!\w)", b, t)
    return re.sub("[ً-ٍ]", "", t)
def deep(x):
    if isinstance(x, dict): return {k: deep(v) for k, v in x.items()}
    if isinstance(x, list): return [deep(v) for v in x]
    return emirati(x)

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
    return str(n)
def spoken(t):
    t = re.sub(r"(\d+)\s*-\s*(\d+)", lambda m: say(m.group(1)) + " مقابل " + say(m.group(2)), t)
    t = re.sub(r"(\d+)%", lambda m: say(m.group(1)) + " بالمية", t)
    t = re.sub(r"(\d+)'", lambda m: "الدقيقة " + say(m.group(1)), t)
    return re.sub(r"\d+", lambda m: say(m.group(0)), t)

# ---- context builders: only facts from our files
def team_ar(t): return (t or {}).get("name_ar") or (t or {}).get("name")
def match_facts(md):
    ev = [{"min": e.get("minute"), "type": e.get("type"), "team": team_ar(md[e["team"]]) if e.get("team") in ("home", "away") else None,
           "player": (e.get("player") or {}).get("name"), "assist": (e.get("assist") or {}).get("name"), "score": e.get("score")} for e in md.get("events") or [] if e.get("type") not in ("sub", "added_time")]
    stats = {}
    for g in md.get("stats") or []:
        for i in g.get("items", []):
            if i["key"] in ("BallPossesion", "total_shots", "ShotsOnTarget", "big_chance", "corners", "expected_goals", "keeper_saves"): stats[i["key"]] = [i["home"], i["away"]]
    best = []
    for side in ("home", "away"):
        for p in ((md.get("lineups") or {}).get(side) or {}).get("starters") or []:
            if p.get("rating"): best.append({"name": p["name"], "team": team_ar(md[side]), "rating": p["rating"]})
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
SUM_SYS = STYLE + """
المهمة: عندك بيانات مباراة خلصت. اكتب:
1) summary: ملخص من 4 لين 6 جمل بالإماراتي، يبدا بالنتيجة ومنو فاز، وبعدين كيف انسجلت الأهداف (منو ومتى)، وأبرز لاعب حسب التقييم، ورقم واحد مهم من الإحصائيات، وسطر أخير عن شو يعني هالنتيجة.
2) thread: ثريد لإكس من 4 لين 6 تغريدات، كل وحدة أقل من 260 حرف، كل تغريدة فيها رقم من البيانات. الأولى فيها النتيجة. بدون هاشتاقات وبدون إيموجي زايد (وحدة بالكثير في التغريدة).
3) headline: عنوان قصير (أقل من 70 حرف).
"""
SUM_SCHEMA = OBJ({"headline": S(80), "summary": S(900), "thread": ARR(S(270), 6)})
def do_summary(md):
    ctx = match_facts(md); sig = hashlib.sha1(json.dumps(ctx, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    if cached("summary", str(md["id"]), sig): return "cached"
    out = gemini(SUM_SYS, ctx, SUM_SCHEMA, tokens=8000)
    if not out: return "fail"
    out = deep(out); out.update({"id": md["id"], "sig": sig, "model": MODEL, "generated": dt.datetime.utcnow().isoformat() + "Z"})
    save("summary", str(md["id"]), out); return "new"

# ---- 77: preview for a coming match
PRE_SYS = STYLE + """
المهمة: عندك بيانات مباراة ياية: ترتيب الفريقين وفورمتهم، ونسب توقعات تيفو، والمواجهات السابقة، وأرقام على المحك، وضغط المباريات.
اكتب lines: 5 أسطر بالضبط، كل سطر جملة وحدة (أقل من 200 حرف):
1) الفريق الأول: نقطة قوة من الأرقام.  2) الفريق الثاني: نقطة قوة من الأرقام.  3) نقطة ضعف أو قلق لواحد منهم.  4) مفتاح المباراة.  5) توقع تيفو بالنسب مقرّبة لأقرب رقم صحيح (بدون فواصل عشرية)، بدون ما تجزم. إذا النسب مب موجودة في البيانات، خل السطر الخامس عن فورمة الفريقين أو أرقام على المحك بدل النسب، ولا تقول إنها مب متوفرة.
"""
PRE_SCHEMA = OBJ({"lines": ARR(S(220), 5)})
def do_preview(m, ctx):
    sig = hashlib.sha1(json.dumps(ctx, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    if cached("preview", str(m["id"]), sig): return "cached"
    out = gemini(PRE_SYS, ctx, PRE_SCHEMA, temp=0.5)
    if not out: return "fail"
    out = deep(out); out.update({"id": m["id"], "sig": sig, "model": MODEL, "generated": dt.datetime.utcnow().isoformat() + "Z"})
    save("preview", str(m["id"]), out); return "new"

# ---- 19 + 161: the round, written for the ear, then voiced (Polly neural ar-AE: Zayd, Hala)
ROUND_SYS = STYLE + """
المهمة: نص صوتي لخلاصة جولة كاملة من دوري أدنوك، يقراه زايد (مذيع إماراتي) في حوالي دقيقتين (220 لين 300 كلمة).
- يبدا بتحية قصيرة: «هلا والله، هذي خلاصة الجولة …».
- يمر على كل مباراة بجملة أو جملتين: النتيجة، ومنو سجّل إذا مذكور، وأي شي لافت.
- بعدها وضع الصدارة والقاع من الترتيب.
- يختم بجملة عن الجولة الياية.
- جمل قصيرة تنقال بسهولة، بدون أقواس ولا رموز.
"""
ROUND_SCHEMA = OBJ({"title": S(80), "script": S(2600)})
POD_SYS = STYLE + """
المهمة: حلقة «تيفو كاست» الأسبوعية، حوار بين زايد وهلا (صديقين يسولفون عن الجولة)، حوالي 5 دقايق (600 لين 750 كلمة).
- زايد يبدا: «هلا والله، معاكم زايد» وهلا تسلّم. هلا تكلّم زايد بصيغة المذكر (عليك، لك)، وزايد يكلّم هلا بصيغة المؤنث بشكل طبيعي («عليج» مسموحة بس لما زايد يكلّم هلا).
- أقسام: نتايج الجولة، أحلى لحظة، لاعب الجولة (من التقييمات)، الترتيب وتوقعات تيفو، مباراة الجولة الياية اللي لازم تنشاف.
- سطور قصيرة متبادلة (12 لين 24 سطر)، كل سطر أقل من 400 حرف. طنازة خفيفة مسموحة، بس لا تخترع أي معلومة.
"""
POD_SCHEMA = OBJ({"title": S(80), "lines": ARR(OBJ({"who": {"type": "STRING", "enum": ["zayd", "hala"]}, "text": S(420)}), 24)})

def polly_mp3(chunks, out):
    import boto3
    pl = boto3.client("polly", region_name="ap-south-1"); parts = []
    for i, (voice, text) in enumerate(chunks):
        for j, piece in enumerate(re.findall(r".{1,2800}(?:\s|$)", text, re.S)):
            r = pl.synthesize_speech(Engine="neural", VoiceId=voice, OutputFormat="mp3", SampleRate="24000", Text=piece.strip())
            f = f"{out}.part{i:03d}{j}.mp3"; open(f, "wb").write(r["AudioStream"].read()); parts.append(f)
    lst = out + ".txt"; open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c:a", "libmp3lame", "-b:a", "64k", out], check=True)
    for p in parts + [lst]: os.remove(p)

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

def do_round(k, ctx, audio):
    sig = hashlib.sha1(json.dumps(ctx, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]; name = f"538-{k}"
    if cached("round", name, sig) and (not audio or os.path.exists(os.path.join(CACHE, "round", name + ".mp3"))): return "cached"
    out = gemini(ROUND_SYS, ctx, ROUND_SCHEMA, temp=0.7, tokens=9000)
    if not out: return "fail"
    out = deep(out); out.update({"round": k, "sig": sig, "spoken": spoken(out["script"]), "model": MODEL, "voice": "Zayd", "generated": dt.datetime.utcnow().isoformat() + "Z"})
    save("round", name, out)
    if audio: polly_mp3([("Zayd", out["spoken"])], os.path.join(CACHE, "round", name + ".mp3"))
    return "new"

def do_podcast(ctx, audio):
    wk = dt.date.today().strftime("%G-%V"); sig = hashlib.sha1(json.dumps(ctx, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    if cached("podcast", wk, sig) and (not audio or os.path.exists(os.path.join(CACHE, "podcast", wk + ".mp3"))): return "cached"
    out = gemini(POD_SYS, ctx, POD_SCHEMA, temp=0.8, tokens=12000)
    if not out: return "fail"
    # the lexicon pass must not "fix" Zayd addressing Hala in the feminine
    lines = []
    for l in out["lines"]:
        t = l["text"]
        if l["who"] == "hala": t = emirati(t)
        else:
            t2 = t
            for a, b in LEX["phrases"].items(): t2 = t2.replace(a, b)
            for a, b in list(LEX["words"].items()) + [("مين", "منو"), ("كذا", "جذيه")]: t2 = re.sub(r"(?<!\w)" + re.escape(a) + r"(?!\w)", b, t2)
            t = re.sub("[ً-ٍ]", "", t2)
        lines.append({"who": l["who"], "text": t, "spoken": spoken(t)})
    rec = {"week": wk, "title": emirati(out["title"]), "lines": lines, "sig": sig, "model": MODEL, "voices": {"zayd": "Zayd", "hala": "Hala"}, "generated": dt.datetime.utcnow().isoformat() + "Z"}
    save("podcast", wk, rec)
    if audio: polly_mp3([("Zayd" if l["who"] == "zayd" else "Hala", l["spoken"]) for l in lines], os.path.join(CACHE, "podcast", wk + ".mp3"))
    return "new"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default="summary,preview,round,podcast"); ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--no-audio", action="store_true"); ap.add_argument("--days", type=int, default=10)
    a = ap.parse_args(); only = set(a.only.split(",")); now = dt.datetime.utcnow(); log = {}
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
    if "round" in only or "podcast" in only:
        k, ctx = round_ctx(fx[538], st538, detail)
        if ctx:
            if "round" in only: log["round"] = do_round(k, ctx, not a.no_audio)
            if "podcast" in only:
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
    print(json.dumps(log, ensure_ascii=False))

if __name__ == "__main__":
    main()
