"""Samples for phase 5 kinds the owner has not approved (none is shown on the site; no approved.json key):
  206 dialects/{match}.json   the match summary in Egyptian, Saudi and Moroccan Arabic (deferred 2026-09-27; no lexicon
                              exists for these dialects and the Emirati pass is not applied)
  369 why/{match}.json        «ليش هالنتيجة؟»: two lines explaining a finished result from our numbers only
  372 quick/{match}.json      «مباراة الليلة في 60 ثانية»: 4-6 lines before a big match (numbers, h2h, Tifo's prediction)
196/197/231 moved into gen.py once approved.
Run:  python3 ai/samples.py [--match ID] [--kind dialects|why|quick]
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

WHY_SYS = gen.STYLE + gen.NAT_RULE + """
المهمة: «ليش هالنتيجة؟» لمباراة خلصت. اكتب lines: سطرين بالضبط، كل سطر جملة وحدة أقل من 150 حرف، تشرح ليش انتهت المباراة جذيه من الأرقام المرفقة بس
(الاستحواذ، التسديدات، التسديدات على المرمى، الفرص المحققة، الأهداف المتوقعة إذا موجودة، الطرد، البلنتي، توقيت الأهداف).
- كل سطر لازم فيه رقم واحد على الأقل من البيانات. مثال على الأسلوب: «سيطر الوحدة على الاستحواذ 61% بس ضيّع 3 فرص محققة».
- لا تفترض أي سبب مب ظاهر في الأرقام (تعب، معنويات، تكتيك، حكم)، ولا تكتب حشو أو مديح.
- stats_home_away: الرقم الأول للمستضيف (home) والثاني للضيف (away).
- الحدث own_goal: اللاعب سجل بالخطأ في مرمى فريقه، والهدف ينحسب للفريق المذكور في goal_for. قول «هدف عكسي من فلان لصالح الفريق».
- انتبه لفريق كل لاعب (team) قبل ما تربطه بأي فريق.
- لو ذكرت عدد التسديدات مع الأهداف، اكتبها عن الفريق بدون اسم الهداف وبدون «عقب» أو «من أصل»، بهالشكل بالضبط: «سجّل الشحانية هدفه الوحيد من 4 تسديدات على المرمى».
"""
WHY_SCHEMA = OBJ({"lines": ARR(S(170), 2)})
def why(md):
    ctx = gen.match_facts(md)
    if not ctx.get("stats_home_away"): return "no stats"
    for e in ctx["events"]:   # own goals: name the side the goal counted for (the event's team is the scorer's own side)
        if e["type"] == "own_goal": e["goal_for"] = ctx["away"] if e["team"] == ctx["home"] else ctx["home"]
    out = gen.gemini(WHY_SYS, ctx, WHY_SCHEMA, temp=0.3, tokens=4000)
    if not out: return "fail"
    gen.save("why", str(md["id"]), {"id": md["id"], "match": f"{ctx['home']} {md['score']['home']}-{md['score']['away']} {ctx['away']}", "competition": ctx.get("competition"), "lines": [fix(gen.grammar(gen.emirati(l), gen.nations(md["home"], md["away"]))) for l in out["lines"]], "model": gen.MODEL, "generated": now()}); return "ok"

QUICK_SYS = gen.STYLE + gen.NAT_RULE + """
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
def quick(m, table, facts):
    md = gen.get(f"match/{m['id']}.json") or m
    rows = {}
    for g in (table or {}).get("groups", []):   # the group that holds either team (Gulf Cup has two)
        for r in g.get("rows", []): rows[gen.team_ar(r["team"])] = {"rank": r["rank"], "played": r["played"], "pts": r["pts"], "gd": r.get("gd"), "form": r.get("form"), "group_ar": GROUP_AR.get(str(g.get("name") or "").replace("Grp. ", "").replace("Group ", "").strip())}
    H, A = gen.team_ar(m["home"]), gen.team_ar(m["away"])
    ctx = {"competition": m.get("comp_name_ar") or md.get("comp_name_ar"), "home": H, "away": A, "kickoff_label": label(m.get("kickoff_uae") or ""),
           "is_tonight": (m.get("kickoff_uae") or "")[:10] == (dt.datetime.utcnow() + dt.timedelta(hours=4)).strftime("%Y-%m-%d"),
           "tifo_probabilities": m.get("probs") or md.get("probs"), "home_table": rows.get(H), "away_table": rows.get(A),
           "head_to_head": (md.get("h2h") or {}).get("summary")}
    out = gen.gemini(QUICK_SYS, ctx, QUICK_SCHEMA, temp=0.3, tokens=4000)
    if not out: return "fail"
    gen.save("quick", str(m["id"]), {"id": m["id"], "match": f"{H} ضد {A}", "lines": [fix(gen.grammar(gen.emirati(l), gen.nations(m["home"], m["away"]))) for l in out["lines"]], "context": ctx, "model": gen.MODEL, "generated": now()}); return "ok"

def samples_369_372():
    log = {}
    f538 = gen.get("comp/538/fixtures.json") or {"matches": []}
    fin = [m["id"] for m in f538["matches"] if m.get("status") == "finished"][-3:]
    for c in (536, 535): fin += [m["id"] for m in (gen.get(f"comp/{c}/fixtures.json") or {"matches": []})["matches"] if m.get("status") == "finished"][-1:]
    for mid in fin: log[f"369-{mid}"] = why(gen.get(f"match/{mid}.json"))
    f329 = gen.get("comp/329/fixtures.json") or {"matches": []}
    ton = next((m for m in f329["matches"] if {m["home"]["id"], m["away"]["id"]} == {5789, 5901} and m.get("status") == "scheduled"), None)
    st329, st538 = gen.get("comp/329/standings.json"), gen.get("comp/538/standings.json"); facts = (gen.get("comp/538/facts.json") or {}).get("matches", {})
    if ton: log[f"372-{ton['id']}"] = quick(ton, st329, {})
    for m in [m for m in f538["matches"] if m.get("status") == "scheduled" and m.get("probs")][:2]: log[f"372-{m['id']}"] = quick(m, st538, facts)
    return log

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--match", type=int); ap.add_argument("--kind", default="why"); a = ap.parse_args()
    if a.kind in ("why", "quick"): print(json.dumps(samples_369_372())); return
    fx = gen.get("comp/538/fixtures.json") or {"matches": []}
    mid = a.match or [m["id"] for m in fx["matches"] if m.get("status") == "finished"][-1]
    print(json.dumps({"206": dialects(gen.get(f"match/{mid}.json"))}))

if __name__ == "__main__":
    main()
