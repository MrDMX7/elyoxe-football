"""Samples for phase 5 kinds the owner has not approved (none is shown on the site; no approved.json key):
  206 dialects/{match}.json   the match summary in Egyptian, Saudi and Moroccan Arabic (deferred 2026-09-27; no lexicon
                              exists for these dialects and the Emirati pass is not applied)
196/197/231 and 369/372 (why, quick) moved into gen.py once approved.
Run:  python3 ai/samples.py [--match ID]
"""
import argparse, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen
S, OBJ, ARR = gen.S, gen.OBJ, gen.ARR
now = lambda: dt.datetime.utcnow().isoformat() + "Z"

DIAL = {
    "eg": "اكتب باللهجة المصرية العامية (القاهرية) مب فصحى: «إزاي»، «دلوقتي»، «أوي»، «مش». المخاطَب مذكّر مفرد.",
    "sa": "اكتب باللهجة السعودية النجدية/الحجازية المحكية المفهومة للجميع، مب فصحى: «وش»، «الحين»، «مرة»، «ما». المخاطَب مذكّر مفرد.",
    "ma": "اكتب بالدارجة المغربية المكتوبة بحروف عربية مب فصحى: «دابا»، «بزاف»، «ماشي»، «واش». المخاطَب مذكّر مفرد.",
}
DIAL_TAIL = """
المهمة: ملخص مباراة خلصت من 4 لين 5 جمل: النتيجة ومنو فاز، الأهداف (منو ومتى)، أبرز لاعب حسب التقييم.
- لا تخترع أي رقم أو اسم مب موجود في البيانات. الأرقام بالأرقام (0-9). بدون تنوين.
"""
DIAL_SCHEMA = OBJ({"summary": S(900)})

def dialects(md):
    ctx = gen.match_facts(md); res = {}
    for k, d in DIAL.items():
        out = gen.gemini(d + DIAL_TAIL, ctx, DIAL_SCHEMA, temp=0.5, tokens=6000)
        if out: res[k] = out["summary"]
    if not res: return "fail"
    gen.save("dialects", str(md["id"]), {"id": md["id"], "summaries": res, "review": "owner must review each dialect; no lexicon pass applied", "model": gen.MODEL, "generated": now()}); return "ok"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--match", type=int); a = ap.parse_args()
    fx = gen.get("comp/538/fixtures.json") or {"matches": []}
    mid = a.match or [m["id"] for m in fx["matches"] if m.get("status") == "finished"][-1]
    print(json.dumps({"206": dialects(gen.get(f"match/{mid}.json"))}))

if __name__ == "__main__":
    main()
