"""The match-report fact sheet (spec: «Every article is written from one fact sheet»). Built from the public v1/ files only:
match/<id>.json, comp/<id>/standings.json, comp/<id>/fixtures.json. Keys are Arabic, as in the blind tests the owner judged
(content/social/tifo/articles-test/2026-11-18/build.py). The writer never does arithmetic: totals, differences, the winner
and each team's games played are in the sheet. A round played after a postponed one is stated (ADNOC 11-18: round 7 was
moved to 29-30 December, so after round 8 every team had played 7)."""
import hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "site" / "ai"))
import checks as AI   # noqa: E402


def _club(t):
    """FotMob's Arabic name, else names/clubs_ar.json / teams_ar.yaml (checks._clubs), else the name. Never checks.club_ar's last
    resort: when gen.py is loaded that asks Gemini for a transliteration and writes names/clubs_ar.json."""
    t = t or {}
    return t.get("name_ar") or AI._clubs().get(str(t.get("id") or "")) or t.get("name") or ""
STAT_AR = {"BallPossesion": "الاستحواذ (%)", "total_shots": "التسديدات", "ShotsOnTarget": "على المرمى", "big_chance": "الفرص الكبيرة",
           "big_chance_missed_title": "فرص كبيرة ضائعة", "accurate_passes": "تمريرات صحيحة", "corners": "الركنيات",
           "yellow_cards": "البطاقات الصفراء", "expected_goals": "الأهداف المتوقعة xG", "fouls": "الأخطاء", "Offsides": "التسلل"}
GOALS = ("goal", "penalty_goal", "own_goal")
GOAL_AR = {"goal": "هدف", "penalty_goal": "هدف من ركلة جزاء", "own_goal": "هدف عكسي"}
CARD_AR = {"red": "بطاقة حمراء مباشرة", "second_yellow": "بطاقة صفراء ثانية وطرد", "yellow": "بطاقة صفراء"}


def load_names(root: Path | None = None) -> dict:
    nd = (root or ROOT) / "names"
    def rd(f):
        try:
            return json.loads((nd / f).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    return {"players": rd("players_ar.json"), "coaches": rd("coaches_ar.json"), "referees": rd("referees_ar.json")}


def _ar(table, pid, latin):
    e = table.get(str(pid)) if pid else None
    v = (e or {}).get("ar") if isinstance(e, dict) else e
    return v or latin


def _minute(e):
    return f"{e['minute']}" + (f"+{e['added']}" if e.get("added") else "")


def _lineup_index(md):
    idx = {}
    for side in ("home", "away"):
        for k, v in ((md.get("lineups") or {}).get(side) or {}).items():
            if isinstance(v, list):
                for p in v:
                    if isinstance(p, dict) and p.get("id"):
                        idx[p["id"]] = (side, p)
    return idx


def _postponed(fixtures, md):
    """Rounds with a match not played while a later round of the same competition is finished."""
    ms = (fixtures or {}).get("matches") or []
    num = lambda r: int(r) if str(r).isdigit() else None
    done = [num(m.get("round")) for m in ms if m.get("status") == "finished" and num(m.get("round")) is not None]
    if not done:
        return []
    last = max(done)
    out = []
    for m in ms:
        r = num(m.get("round"))
        if r is not None and r < last and m.get("status") in ("scheduled", "postponed"):
            out.append({"الجولة": m.get("round_ar") or f"الجولة {r}", "المباراة": f"{_club(m['home'])} - {_club(m['away'])}",
                        "الموعد الجديد بتوقيت الإمارات": m.get("kickoff_uae")})
    return out


def report_sheet(md, standings, fixtures, names):
    PL, CO, RE = names.get("players", {}), names.get("coaches", {}), names.get("referees", {})
    person = lambda p: _ar(PL, p.get("id"), p.get("name")) if p else None
    idx = _lineup_index(md)
    team = {"home": _club(md["home"]), "away": _club(md["away"])}
    ev, fp = [], []
    for e in md.get("events") or []:
        t = e.get("type")
        if t in GOALS:
            pid = (e.get("player") or {}).get("id")
            side = idx.get(pid, (None,))[0]
            ev.append({"دقيقة": _minute(e), "حدث": GOAL_AR[t], "اللاعب": person(e.get("player")), "فريق اللاعب": team.get(side) if side else None,
                       "الصناعة": person(e.get("assist")),
                       "النتيجة بعده": f"{team['home']} {e['score']['home']} - {e['score']['away']} {team['away']}"})
            fp.append(f"g{_minute(e)}:{pid}")
        elif t in CARD_AR:
            ev.append({"دقيقة": _minute(e), "حدث": CARD_AR[t], "اللاعب": person(e.get("player")), "الفريق": team.get(e.get("team"))})
            if t != "yellow":
                fp.append(f"r{_minute(e)}:{(e.get('player') or {}).get('id')}")
        elif t == "sub":
            ev.append({"دقيقة": _minute(e), "حدث": "تبديل", "الفريق": team.get(e.get("team")),
                       "دخل": person(e.get("player")), "خرج": person(e.get("player_out"))})
    stats = {}
    for grp in md.get("stats") or []:
        for it in grp.get("items") or []:
            k = STAT_AR.get(it.get("key"))
            if k and k not in stats:
                stats[k] = {team["home"]: it.get("home"), team["away"]: it.get("away")}
    if md.get("xg"):
        stats["الأهداف المتوقعة xG"] = {team["home"]: md["xg"].get("home"), team["away"]: md["xg"].get("away")}
    sh, sa = md["score"]["home"], md["score"]["away"]
    pens = md.get("penalties") or None
    if sh != sa:
        winner = team["home"] if sh > sa else team["away"]
    elif pens and pens.get("home") is not None and pens.get("home") != pens.get("away"):
        winner = team["home"] if pens["home"] > pens["away"] else team["away"]
    else:
        winner = "تعادل"
    rated = sorted([(p.get("rating") or 0, side, p) for _, (side, p) in idx.items() if p.get("rating")], key=lambda x: -x[0])[:3]
    lu = md.get("lineups") or {}
    coach = {team[s]: _ar(CO, ((lu.get(s) or {}).get("coach") or {}).get("id"), ((lu.get(s) or {}).get("coach") or {}).get("name"))
             for s in ("home", "away")}
    wp = (md.get("winprob_prematch") or {}).get("p")
    table = None
    if standings:
        rows = [r for g in standings.get("groups") or [] for r in g.get("rows") or []]
        table = [{"الفريق": _club(r["team"]), "المركز": r["rank"], "لعب": r["played"], "النقاط": r.get("pts", r.get("points")),
                  "فوز": r.get("won"), "تعادل": r.get("drawn"), "خسارة": r.get("lost"), "له": r.get("gf"), "عليه": r.get("ga")}
                 for r in rows if r["team"]["id"] in (md["home"]["id"], md["away"]["id"])] or None
    ref = md.get("referee") or {}
    sheet = {
        "النوع": "تقرير مباراة", "البطولة": md.get("comp_name_ar"), "الجولة": md.get("round_ar"), "الموسم": md.get("season"),
        "الموعد بتوقيت الإمارات": md.get("kickoff_uae"),
        "الملعب": (md.get("venue") or {}).get("name_ar") or (md.get("venue") or {}).get("name_en"),
        "الحكم": _ar(RE, ref.get("id"), ref.get("name")), "الحضور": md.get("attendance"),
        "صاحب الأرض": team["home"], "الضيف": team["away"],
        "النتيجة النهائية": f"{team['home']} {sh} - {sa} {team['away']}",
        "نتيجة الشوط الأول": (f"{team['home']} {md['halftime_score']['home']} - {md['halftime_score']['away']} {team['away']}"
                              if md.get("halftime_score") else None),
        "ركلات الترجيح": f"{team['home']} {pens['home']} - {pens['away']} {team['away']}" if pens and pens.get("home") is not None else None,
        "أرقام محسوبة": {"مجموع الأهداف": sh + sa, "فارق الأهداف": abs(sh - sa), "الفائز": winner},
        "المدربان": coach, "الخطتان": {team[s]: (lu.get(s) or {}).get("formation") for s in ("home", "away")},
        "الأحداث بالترتيب": ev, "الإحصائيات": stats,
        "الأعلى تقييماً": [{"اللاعب": person(p), "الفريق": team[s], "التقييم": r} for r, s, p in rated],
        "احتمالات نموذج تيفو قبل المباراة (%)": ({"فوز " + team["home"]: round(wp[0] * 100), "تعادل": round(wp[1] * 100),
                                                 "فوز " + team["away"]: round(wp[2] * 100)} if wp else None),
        "الترتيب الحالي في البطولة": table,
        "جولات مؤجلة": _postponed(fixtures, md) or None,
    }
    sheet = {k: v for k, v in sheet.items() if v not in (None, [], {})}
    fp.append(f"s{sh}-{sa}" + (f"p{pens.get('home')}-{pens.get('away')}" if pens else ""))
    meta = {"match": md["id"], "comp": md.get("comp"), "teams": [md["home"]["id"], md["away"]["id"]],
            "players": sorted({pid for pid in idx} | {(e.get("player") or {}).get("id") for e in md.get("events") or []} - {None}),
            "thin": not (md.get("events") or md.get("stats")),
            "fingerprint": hashlib.sha1("|".join(sorted(fp)).encode()).hexdigest()[:12]}
    return sheet, meta
