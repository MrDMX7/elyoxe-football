"""Samples for four phase 5 kinds the owner has not approved yet (none is shown on the site: build.cjs has no renderer and
ai/approved.json has no key for them). Facts only from /v1 data; Emirati through gen.STYLE + the lexicon pass, except 206.
  196 commentary/{match}.json   one live line per match event (UAE matches), keyed by the stable event_id
  197 digest/{team}.json        a club's week: results, table position, next match (3 short paragraphs)
  206 dialects/{match}.json     the same match summary in Egyptian, Saudi and Moroccan Arabic (the owner must review
                                each dialect: no lexicon exists for them and the Emirati pass is not applied)
  231 power/{comp}-{week}.json  weekly power ranking: order fixed from the Tifo rating, one line of reasoning per club
Run:  python3 ai/samples.py [--match ID] [--team ID]
"""
import argparse, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen
S, OBJ, ARR = gen.S, gen.OBJ, gen.ARR
now = lambda: dt.datetime.utcnow().isoformat() + "Z"

COM_SYS = gen.STYLE + """
المهمة: تعليق مباشر مكتوب. لكل حدث في events اكتب سطر واحد (أقل من 140 حرف) كأنك تكتب لحظة الحدث، بدون ما تعرف اللي بيصير بعده.
استعمل الدقيقة والنتيجة بعد الحدث إذا موجودة. نفس ترتيب الأحداث ونفس event_id.
"""
COM_SCHEMA = OBJ({"lines": ARR(OBJ({"event_id": S(80), "text": S(160)}), 40)})

DIG_SYS = gen.STYLE + """
المهمة: نشرة أسبوعية لمشجع نادي واحد: title عنوان قصير، وparas 3 فقرات قصيرة (كل وحدة جملتين لين ثلاث):
1) نتايج الأسبوع.  2) وين واقف في الترتيب والفورمة.  3) المباراة الياية وموعدها بتوقيت الإمارات.
- كل جملة فيها معلومة من البيانات المرفقة. لا تتوقع ولا تفترض شي مب فيها (مثل ذهاب وإياب أو نظام البطولة)، ولا تكتب جمل حشو أو تمنيات.
"""
DIG_SCHEMA = OBJ({"title": S(80), "paras": ARR(S(420), 3)})

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

POW_SYS = gen.STYLE + """
المهمة: ترتيب القوة الأسبوعي. عندك الأندية مرتبة سلفاً بتصنيف تيفو (لا تغيّر الترتيب)، ومع كل نادي ترتيبه في الدوري وفورمته وتغيّر تصنيفه في آخر 5 مباريات.
لكل نادي اكتب line: جملة وحدة (أقل من 150 حرف) تشرح مكانه من الأرقام المرفقة بس. نفس الترتيب ونفس team_id.
"""
POW_SCHEMA = OBJ({"title": S(80), "rows": ARR(OBJ({"team_id": {"type": "INTEGER"}, "line": S(170)}), 20)})

def commentary(md):
    ev = [{"event_id": e.get("event_id"), "min": e.get("minute"), "type": e.get("type"), "team": gen.team_ar(md[e["team"]]) if e.get("team") in ("home", "away") else None,
           "player": (e.get("player") or {}).get("name"), "score": e.get("score")} for e in md.get("events") or [] if e.get("event_id") and e.get("type") not in ("added_time",)]
    if not ev: return "no events"
    out = gen.gemini(COM_SYS, {"home": gen.team_ar(md["home"]), "away": gen.team_ar(md["away"]), "competition": md.get("comp_name_ar"), "events": ev}, COM_SCHEMA, temp=0.6, tokens=9000)
    if not out: return "fail"
    out = gen.deep(out); out.update({"id": md["id"], "model": gen.MODEL, "generated": now()}); gen.save("commentary", str(md["id"]), out); return "ok"

def digest(team_id, st538):
    t = gen.get(f"team/{team_id}.json")
    if not t: return "no team"
    fx = t.get("fixtures") or []; cut = (dt.datetime.utcnow() - dt.timedelta(days=7)).isoformat()
    past = [m for m in fx if m.get("status") == "finished" and (m.get("kickoff_utc") or "") >= cut]
    nxt = next((m for m in sorted(fx, key=lambda m: m.get("kickoff_utc") or "") if m.get("status") == "scheduled"), None)
    row = next((r for r in gen.table_ctx(st538) if r["team"] == gen.team_ar(t)), None)
    ctx = {"team": gen.team_ar(t), "results_last_7_days": [{"home": gen.team_ar(m["home"]), "away": gen.team_ar(m["away"]), "score": m.get("score"), "competition": m.get("comp_name_ar")} for m in past],
           "table": row, "next_match": nxt and {"home": gen.team_ar(nxt["home"]), "away": gen.team_ar(nxt["away"]), "kickoff_uae": nxt.get("kickoff_uae"), "competition": nxt.get("comp_name_ar")}}
    out = gen.gemini(DIG_SYS, ctx, DIG_SCHEMA, temp=0.6, tokens=6000)
    if not out: return "fail"
    out = gen.deep(out); out.update({"team": team_id, "context": ctx, "model": gen.MODEL, "generated": now()}); gen.save("digest", str(team_id), out); return "ok"

def dialects(md):
    ctx = gen.match_facts(md); res = {}
    for k, d in DIAL.items():
        out = gen.gemini(d + DIAL_TAIL, ctx, DIAL_SCHEMA, temp=0.5, tokens=6000)
        if out: res[k] = out["summary"]
    if not res: return "fail"
    gen.save("dialects", str(md["id"]), {"id": md["id"], "summaries": res, "review": "owner must review each dialect; no lexicon pass applied", "model": gen.MODEL, "generated": now()}); return "ok"

def power(st538):
    rt = gen.get("ratings/uae-clubs.json") or {}
    teams = [t for t in rt.get("teams", []) if t.get("in_league")]
    if not teams: return "no ratings"
    tab = {r["team"]: r for r in gen.table_ctx(st538)}
    rows = [{"team_id": t["team"], "team": t.get("name_ar"), "tifo_rating": round(t.get("rating") or 0), "rating_change_last5": t.get("change_5"), "table": tab.get(t.get("name_ar"))} for t in teams]
    out = gen.gemini(POW_SYS, {"league": "دوري أدنوك للمحترفين", "clubs_in_order": rows}, POW_SCHEMA, temp=0.6, tokens=8000)
    if not out: return "fail"
    lines = {r["team_id"]: r["line"] for r in out["rows"]}
    wk = dt.date.today().strftime("%G-%V")
    gen.save("power", f"538-{wk}", {"title": gen.emirati(out["title"]), "rows": [dict(r, line=gen.emirati(lines.get(r["team_id"], ""))) for r in rows], "model": gen.MODEL, "generated": now()}); return "ok"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--match", type=int); ap.add_argument("--team", type=int); a = ap.parse_args()
    fx = gen.get("comp/538/fixtures.json") or {"matches": []}; st538 = gen.get("comp/538/standings.json")
    mid = a.match or [m["id"] for m in fx["matches"] if m.get("status") == "finished"][-1]
    md = gen.get(f"match/{mid}.json"); tid = a.team or md["home"]["id"]; log = {}
    log["196"] = commentary(md); log["197"] = digest(tid, st538); log["206"] = dialects(md); log["231"] = power(st538)
    print(json.dumps(log))

if __name__ == "__main__":
    main()
