"""Arabic copy for the phase 4 reference pages, from the sourced research in research/tifo-2026-09-27/:
legends (106), memorable matches (108), this day in UAE football (40), the laws explainer «ليش ألغى الهدف؟» (53).
Facts come only from the research files (each item keeps its source URLs); Gemini writes them in Arabic with the
light Emirati register of the site (gen.py STYLE + lexicon pass). Output: cache/history/{legends,memorable,thisday,laws}.json
Run once per research refresh:  python3 ai/history_ar.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen
R = os.path.expanduser("~/workspace/research/tifo-2026-09-27")
OUT = os.path.join(gen.SITE, "cache", "history"); os.makedirs(OUT, exist_ok=True)
S, OBJ, ARR = gen.S, gen.OBJ, gen.ARR
BASE = gen.STYLE + "\nهالنص لصفحة مرجعية في الموقع: واضح وبسيط، لهجة إماراتية خفيفة، بدون مبالغة. اكتب بس اللي في البيانات.\n"

def run(name, items, sysp, schema, key):
    f = os.path.join(OUT, name + ".json"); done = json.load(open(f)) if os.path.exists(f) else {}
    for it in items:
        k = key(it)
        if k in done: continue
        out = gen.gemini(sysp, it, schema, temp=0.3, tokens=6000)
        if out: done[k] = gen.deep(out); json.dump(done, open(f, "w"), ensure_ascii=False, indent=1); print(name, k, "ok")
        else: print(name, k, "FAIL")
    return done

leg = json.load(open(os.path.join(R, "legends.json")))["players"]
run("legends", leg, BASE + "المهمة: نبذة عن أسطورة كورة إماراتي: bio من 3 لين 4 جمل (مسيرته وأهم إنجاز)، وfacts من 2 لين 4 حقائق قصيرة فيها أرقام. الأرقام بالأرقام.",
    OBJ({"bio": S(700), "facts": ARR(S(200), 4)}), lambda p: p.get("name_en") or p.get("name"))
mem = json.load(open(os.path.join(R, "memorable.json")))["matches"]
run("memorable", mem, BASE + "المهمة: مباراة تاريخية في كورة الإمارات: title عنوان قصير (أقل من 70 حرف)، وwhy جملتين تشرح ليش ما تنتسى، من why_it_matters_en وباقي البيانات.",
    OBJ({"title": S(90), "why": S(420)}), lambda m: m["id"])
td = json.load(open(os.path.join(R, "thisday.json")))
events = td.get("events") or td.get("items") or [v for k, v in td.items() if isinstance(v, list)][0]
run("thisday", events, BASE + "المهمة: حدث من «هذا اليوم في كورة الإمارات». line: سطر واحد (أقل من 160 حرف) يبدا بالسنة، مثلاً «في 1990، …». لا تذكر التاريخ باليوم والشهر.",
    OBJ({"line": S(180)}), lambda e: f"{e.get('mm-dd') or e.get('mmdd')}-{e.get('year')}-{(e.get('text_en_neutral') or '')[:30]}")
laws = json.load(open(os.path.join(R, "laws.json")))["topics"]
run("laws", laws, BASE + "المهمة: شرح قانون من قوانين الكورة (IFAB) بالإماراتي لمشجع عادي: title_ar عنوان، summary من 3 لين 5 جمل بسيطة، disallowed قائمة من 2 لين 5 حالات «ليش ألغى الهدف؟» كل وحدة جملة. التزم بالنص الرسمي المرفق بدون زيادة.",
    OBJ({"title_ar": S(60), "summary": S(900), "disallowed": ARR(S(220), 5)}), lambda t: t["id"])
