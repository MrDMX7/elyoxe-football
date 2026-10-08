"""«تيفو الأسبوع» (417, with 407's player card): the Arab football week in 5 numbers, from our data files only (no AI).
Thursday 15:00 UAE (run-job.sh tifo-week), before the 18:00 newsletter. Writes to cache/week/ (out/ is rebuilt every hour;
og.py copies these into out/og/ on each build):
  week-<yyyy-ww>.json, week-latest.json        {week, from, to, generated, items:[{kind, label, value, text, team, player, match, comp}]}
  week-<yyyy-ww>-story.png / -feed.png          1080x1920 / 1080x1350, og.py style
  week-latest-story.png / week-latest-feed.png
  arab-star-<yyyy-ww>.png, arab-star-latest.png 1080x1350 card of the Arab player of the week (arabs/week)
Items, in order, each only when the data has it:
  biggest_win   largest margin in the Arab competitions this week (then most goals)
  top_scorer    most goals in the week's Arab-competition matches (match events: goals and penalties, no own goals)
  arab_star     /v1/arabs/week/latest.json -> star
  streak        the longest running winning streak (≥5), else unbeaten, from arabs/streaks.json
  leader_change a league whose leader changed this week (both tables computed from our results; shown only when the
                leader is clear on points in both and matches the published standings)
Names: clubs through ai/checks.club_ar (FotMob, names/clubs_ar.json, teams_ar.yaml), players through names/players_ar.json.
Run: python3 weekly.py [--today YYYY-MM-DD]"""
import argparse, concurrent.futures as cf, datetime as dt, json, os, shutil, sys, urllib.request, gzip
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "ai"))
import og, checks
DATA = os.environ.get("TIFO_DATA", "https://d1n5aqaqkowltp.cloudfront.net")
OUTD = os.path.join(HERE, "cache", "week")
ARAB = {"AE", "SA", "EG", "MA", "DZ", "TN", "IQ", "JO", "KW", "QA", "BH", "OM", "LB", "SY", "PS", "YE", "LY", "SD", "MR", "SO", "DJ", "KM"}
MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]

def get(p):
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{DATA}/{p}", headers={"Accept-Encoding": "identity"}), timeout=25) as r:
                raw = r.read(); return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
        except urllib.error.HTTPError as e:
            if e.code in (403, 404): return None
        except Exception: pass
    return None

club = lambda t: checks.club_ar(t)
TRANSLIT_F = os.path.join(HERE, "cache", "week", "players_translit.json")   # players missing from names/players_ar.json
def player(pid, latin):
    ar = checks.names_ar().get(str(pid))
    if ar or not latin: return ar or latin or ""
    try: cache = json.load(open(TRANSLIT_F))
    except Exception: cache = {}
    if str(pid) not in cache:   # a spelling, not a fact: Gemini writes the name in Arabic letters once; kept for the names agent to review
        try:
            import gen
            out = gen.gemini_api("اكتب اسم لاعب كرة القدم هذا بالحروف العربية كما يكتبه الإعلام العربي. JSON بس.", {"player": latin}, gen.OBJ({"ar": gen.S(60)}), temp=0.1, tokens=2000, kind="player-name")
            ar = (out or {}).get("ar", "").strip()
        except Exception: ar = ""
        if ar and not any("a" <= ch.lower() <= "z" for ch in ar):
            cache[str(pid)] = {"latin": latin, "ar": ar, "source": "generated"}; os.makedirs(os.path.dirname(TRANSLIT_F), exist_ok=True)
            json.dump(cache, open(TRANSLIT_F, "w"), ensure_ascii=False, indent=1)
    return (cache.get(str(pid)) or {}).get("ar") or latin

def table_at(matches, cut):
    """{team_id: [pts, gd, gf]} from finished results up to `cut` (ISO UTC)."""
    t = {}
    for m in matches:
        if m.get("status") != "finished" or not m.get("score") or (m.get("kickoff_utc") or "") > cut: continue
        h, a, sh, sa = m["home"]["id"], m["away"]["id"], m["score"]["home"], m["score"]["away"]
        for x, gf, ga in ((h, sh, sa), (a, sa, sh)):
            r = t.setdefault(x, [0, 0, 0]); r[0] += 3 if gf > ga else 1 if gf == ga else 0; r[1] += gf - ga; r[2] += gf
    return t
def clear_leader(t):
    rank = sorted(t.items(), key=lambda kv: (-kv[1][0], -kv[1][1], -kv[1][2]))
    return rank[0][0] if len(rank) > 1 and rank[0][1][0] > rank[1][1][0] else None

def collect(today):
    end = dt.datetime.combine(today, dt.time(11, 0))   # Thursday 15:00 UAE = 11:00 UTC
    start = end - dt.timedelta(days=7); s_iso, e_iso = start.isoformat() + "Z", end.isoformat() + "Z"
    index = get("index.json") or {"competitions": []}
    comps = [c for c in index["competitions"] if ((c.get("country") or {}).get("iso2") in ARAB)]
    fx = {c["id"]: (get(f"comp/{c['id']}/fixtures.json") or {}).get("matches", []) for c in comps}
    week = [dict(m, comp=c["id"], comp_name_ar=c["name_ar"]) for c in comps for m in fx[c["id"]]
            if m.get("status") == "finished" and m.get("score") and s_iso <= (m.get("kickoff_utc") or "") <= e_iso]
    items = []
    # 1) biggest win
    if week:
        w = max(week, key=lambda m: (abs(m["score"]["home"] - m["score"]["away"]), m["score"]["home"] + m["score"]["away"], m["kickoff_utc"]))
        if w["score"]["home"] != w["score"]["away"]:
            win, lose = (w["home"], w["away"]) if w["score"]["home"] > w["score"]["away"] else (w["away"], w["home"])
            gw, gl = max(w["score"].values()), min(w["score"].values())
            items.append({"kind": "biggest_win", "label": "أكبر فوز", "value": f"{gw}-{gl}", "text": f"{club(win)} على {club(lose)}",
                          "sub": w["comp_name_ar"], "team": win["id"], "match": w["id"], "comp": w["comp"]})
    # 2) top scorer (match events)
    with cf.ThreadPoolExecutor(8) as ex: details = list(ex.map(lambda m: get(f"match/{m['id']}.json"), week))
    goals = {}
    for m, md in zip(week, details):
        for e in (md or {}).get("events") or []:
            if e.get("type") in ("goal", "penalty_goal") and (e.get("player") or {}).get("id") and e.get("team") in ("home", "away"):
                g = goals.setdefault(str(e["player"]["id"]), {"n": 0, "name": e["player"].get("name"), "team": md[e["team"]], "comp": m["comp_name_ar"]}); g["n"] += 1
    if goals:
        pid, g = max(goals.items(), key=lambda kv: kv[1]["n"])
        tied = [(p, x) for p, x in goals.items() if x["n"] == g["n"]]
        if g["n"] >= 2 and len(tied) == 1:
            items.append({"kind": "top_scorer", "label": "هداف الأسبوع", "value": str(g["n"]), "text": f"{player(pid, g['name'])} ({club(g['team'])})",
                          "sub": g["comp"], "team": g["team"].get("id"), "player": int(pid)})
        elif g["n"] >= 2 and len(tied) <= 3:   # a shared top: name them all, no single crest
            items.append({"kind": "top_scorer", "label": "هدافين الأسبوع", "value": str(g["n"]), "text": "، ".join(player(p, x["name"]) for p, x in tied),
                          "sub": "، ".join(dict.fromkeys(club(x["team"]) for p, x in tied)), "team": None, "players": [int(p) for p, x in tied]})
    # 3) Arab player of the week (arabs/week)
    iso = today.isocalendar(); wk = get(f"arabs/week/{iso[0]}-{iso[1]:02d}.json")
    if not (wk or {}).get("star"):
        ptr = get("arabs/week/latest.json"); wk = get(ptr["path"]) if ptr and ptr.get("path") else None
    star = (wk or {}).get("star")
    if star:
        items.append({"kind": "arab_star", "label": "نجم العرب برا", "value": f"{star['avg_rating']:.1f}" if star.get("avg_rating") else str(star.get("goals", "")),
                      "text": f"{player(star['player'], star.get('name'))} ({star.get('team_ar') or ''})", "sub": (star.get("nationality") or {}).get("name_ar", ""),
                      "team": star.get("team"), "player": star.get("player"), "goals": star.get("goals"), "assists": star.get("assists"), "rating": star.get("avg_rating")})
    # 4) streak
    sk = (get("arabs/streaks.json") or {}).get("streaks") or {}
    for kind, word, minimum in (("winning", "فوز ورا فوز", 5), ("unbeaten", "بدون خسارة", 3)):
        s = (sk.get(kind) or [None])[0]
        if s and s.get("length", 0) >= minimum:
            items.append({"kind": "streak", "label": "سلسلة شغالة", "value": str(s["length"]), "text": f"{club({'id': s['team'], 'name_ar': s.get('team_ar')})}: {s['length']} {og.count_word(s['length'], 'match')} {word}",
                          "sub": (s.get("country") or {}).get("name_ar", ""), "team": s["team"]}); break
    # 5) league leader change (computed tables, cross-checked with the published standings)
    for c in comps:
        if c.get("kind") != "league": continue
        before, now = clear_leader(table_at(fx[c["id"]], s_iso)), clear_leader(table_at(fx[c["id"]], e_iso))
        if not before or not now or before == now: continue
        st = get(f"comp/{c['id']}/standings.json") or {}; g = (st.get("groups") or [{}])
        if len(g) != 1 or not g[0].get("rows") or g[0]["rows"][0]["team"]["id"] != now: continue
        new = g[0]["rows"][0]["team"]; old = next((r["team"] for r in g[0]["rows"] if r["team"]["id"] == before), {"id": before})
        items.append({"kind": "leader_change", "label": "صدارة يديدة", "value": str(g[0]["rows"][0]["pts"]), "text": f"{club(new)} تصدّر {c['name_ar']} بدل {club(old)}",
                      "sub": c["name_ar"], "team": new["id"], "comp": c["id"]}); break
    return {"from": start.date().isoformat(), "to": today.isoformat(), "items": items}

# ---- images (og.py primitives: night pitch, the stand mosaic, Kufi/Barlow/Readex, crests, the tifo mark)
def _crest(im, tid, size, x, y):
    lg = og.logo(os.path.join(HERE, "cache", "logo", f"{tid}.png"), size) if tid else None
    if not lg and tid:   # a club outside the covered leagues (e.g. the Arab star's European club): fetch its crest once
        try:
            f = os.path.join(HERE, "cache", "logo", f"{tid}.png")
            open(f, "wb").write(urllib.request.urlopen(f"https://images.fotmob.com/image_resources/logo/teamlogo/{tid}.png", timeout=20).read()); lg = og.logo(f, size)
        except Exception: lg = None
    if lg: im.paste(lg, (int(x - lg.width / 2), int(y - lg.height / 2)), lg)

def _date_label(d0, d1):
    a, b = dt.date.fromisoformat(d0), dt.date.fromisoformat(d1)
    return f"{a.day} {MONTHS[a.month - 1]} - {b.day} {MONTHS[b.month - 1]} {b.year}" if a.month != b.month else f"{a.day} - {b.day} {MONTHS[b.month - 1]} {b.year}"

UNITS = {"top_scorer": "goal", "streak": "match", "leader_change": "point"}   # count nouns through og.count_word; arab_star's value is a rating
def unit_for(it):
    k = UNITS.get(it["kind"])
    if k: return og.count_word(it["value"], k) if str(it["value"]).isdigit() else None
    return "التقييم" if it["kind"] == "arab_star" and "." in str(it["value"]) else None
def render_week(data, w, h):
    im = Image.new("RGB", (w, h), og.NIGHT); d = ImageDraw.Draw(im); u = w / 1080
    band = int(h * (0.16 if h > 1500 else 0.13)); og.stand(d, 0, 0, w, band, int(40 * u), [og.NIGHT2, og.DUNE], [og.NIGHT2, og.CHALK], "week" + data["week"])
    d.rectangle([0, band, w, h], fill=og.NIGHT)
    y = band + int(95 * u)
    d.text((w / 2, y), "تيفو الأسبوع", font=og.KUFI(int(84 * u)), fill=og.CHALK, anchor="mm", direction="rtl", language="ar")
    d.text((w / 2, y + int(80 * u)), _date_label(data["from"], data["to"]), font=og.TXT(int(34 * u)), fill=(185, 199, 192), anchor="mm", direction="rtl", language="ar")
    items = data["items"][:5]; top = y + int(150 * u); bottom = h - int(150 * u)
    rh = (bottom - top) / max(len(items), 1); rh = min(rh, 300 * u)
    for i, it in enumerate(items):
        cy = top + rh * i + rh / 2; x0, x1 = int(60 * u), w - int(60 * u)
        d.rectangle([x0, cy - rh / 2 + 10 * u, x1, cy + rh / 2 - 10 * u], fill=og.NIGHT2)
        _crest(im, it.get("team"), int(min(120, rh * 0.5) * u), x1 - int(90 * u), cy)
        tx = x1 - int(175 * u); maxw = tx - int(300 * u)
        d.text((tx, cy - int(42 * u)), it["label"], font=og.KUFI(int(32 * u)), fill=og.DUNE, anchor="rm", direction="rtl", language="ar")
        d.text((tx, cy + int(8 * u)), it["text"], font=og.fit(d, it["text"], og.TXT, int(38 * u), maxw), fill=og.CHALK, anchor="rm", direction="rtl", language="ar")
        if it.get("sub"): d.text((tx, cy + int(52 * u)), it["sub"], font=og.TXT(int(26 * u)), fill=(185, 199, 192), anchor="rm", direction="rtl", language="ar")
        unit = unit_for(it)
        d.text((x0 + int(130 * u), cy - (int(14 * u) if unit else 0)), it["value"], font=og.DIG(int(110 * u)), fill=og.CHALK, anchor="mm")
        if unit: d.text((x0 + int(130 * u), cy + int(50 * u)), unit, font=og.TXT(int(24 * u)), fill=(185, 199, 192), anchor="mm", direction="rtl", language="ar")
    fy = h - int(80 * u); og.mark(d, w - int(160 * u), fy - int(28 * u), int(18 * u))
    d.text((w - int(200 * u), fy), "تيفو", font=og.KUFI(int(44 * u)), fill=og.CHALK, anchor="rm", direction="rtl", language="ar")
    d.text((int(60 * u), fy), "tifo.elyoxe.com/week", font=og.DIG(int(36 * u)), fill=(185, 199, 192), anchor="lm")
    return im

def render_star(it, week):
    w, h = 1080, 1350; im = Image.new("RGB", (w, h), og.NIGHT); d = ImageDraw.Draw(im)
    og.stand(d, 0, 0, w, 380, 45, [og.NIGHT2, og.DUNE], None, "star" + week); d.rectangle([0, 380, w, h], fill=og.NIGHT)
    d.text((w / 2, 450), "نجم العرب هالأسبوع", font=og.KUFI(60), fill=og.DUNE, anchor="mm", direction="rtl", language="ar")
    _crest(im, it.get("team"), 220, w / 2, 640)
    name = it["text"].split(" (")[0]
    d.text((w / 2, 830), name, font=og.fit(d, name, og.KUFI, 92, w - 140), fill=og.CHALK, anchor="mm", direction="rtl", language="ar")
    club_line = "، ".join(x for x in (it["text"].split(" (")[1].rstrip(")") if " (" in it["text"] else "", it.get("sub")) if x)
    d.text((w / 2, 920), club_line, font=og.TXT(40), fill=(185, 199, 192), anchor="mm", direction="rtl", language="ar")
    stats = [(f"{it['rating']:.1f}" if it.get("rating") else None, "التقييم"),
             (str(it["goals"]) if it.get("goals") is not None else None, og.count_word(it.get("goals") or 0, "goal")),
             (str(it["assists"]) if it.get("assists") is not None else None, og.count_word(it.get("assists") or 0, "assist"))]
    stats = [s for s in stats if s[0]]
    for i, (v, lab) in enumerate(stats):
        x = w - (i + 0.5) * (w - 160) / len(stats) - 80
        d.text((x, 1060), v, font=og.DIG(130), fill=og.CHALK, anchor="mm"); d.text((x, 1150), lab, font=og.TXT(36), fill=(185, 199, 192), anchor="mm", direction="rtl", language="ar")
    og.mark(d, w - 160, h - 108, 18); d.text((w - 200, h - 80), "تيفو", font=og.KUFI(44), fill=og.CHALK, anchor="rm", direction="rtl", language="ar")
    d.text((60, h - 80), "tifo.elyoxe.com/arabs/week", font=og.DIG(36), fill=(185, 199, 192), anchor="lm")
    return im

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--today"); a = ap.parse_args()
    today = dt.date.fromisoformat(a.today) if a.today else (dt.datetime.utcnow() + dt.timedelta(hours=4)).date()
    data = collect(today); iso = today.isocalendar(); data["week"] = f"{iso[0]}-{iso[1]:02d}"; data["generated"] = dt.datetime.utcnow().isoformat() + "Z"
    os.makedirs(OUTD, exist_ok=True); wk = data["week"]
    if not data["items"]: print("weekly: no items; nothing written"); return
    json.dump(data, open(os.path.join(OUTD, f"week-{wk}.json"), "w"), ensure_ascii=False, indent=1)
    for size, (w, h) in (("story", (1080, 1920)), ("feed", (1080, 1350))):
        render_week(data, w, h).save(os.path.join(OUTD, f"week-{wk}-{size}.png"), optimize=True)
    star = next((i for i in data["items"] if i["kind"] == "arab_star"), None)
    if star: render_star(star, wk).save(os.path.join(OUTD, f"arab-star-{wk}.png"), optimize=True)
    for f in [f"week-{wk}.json", f"week-{wk}-story.png", f"week-{wk}-feed.png"] + ([f"arab-star-{wk}.png"] if star else []):
        shutil.copyfile(os.path.join(OUTD, f), os.path.join(OUTD, f.replace(wk, "latest")))
    print(f"weekly {wk}: {len(data['items'])} items -> {OUTD}")

if __name__ == "__main__":
    main()
