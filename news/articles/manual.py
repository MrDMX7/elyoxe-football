"""News articles written on the Claude subscription instead of the API (owner 2026-11-21: «اكتب مقالات بشكل يدوي بدون
الapi»). The same queue, sheet, checks, photo and publish as news_run; only the writer is replaced by files.

  python -m news.articles.manual export DIR [--n 40]
      the queue's biggest stories -> DIR/<sid>.json (story, meta, photo candidates) and DIR/sheets/<sid>.json (the sheet alone)
  (a writer reads style.md and a sheet and writes DIR/arts/<sid>.json: write.SCHEMA plus "topic" and "stage", or the headline
   «لا خبر» when the sheet holds no news)
  python -m news.articles.manual publish DIR
      check_news -> duplicate headline -> photo (the widest; no judge call) -> publish -> state; a failure's notes go to
      DIR/fails/<sid>.json for one rewrite

Hand-written articles are extra: they never count in the day's 60 or take a pacing slot. State is written only while no
journal run is in progress (it saves the same file), and re-read just before each write."""
import argparse, json, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from store import Store, S3Backend
from . import news_pick, sources, facts, check, photo, publish
from .news_run import TYPES, STATE, DESK, _title
from .run import BUCKET, http_bytes
from .write import NO_NEWS, Writer

MODEL = "claude-sonnet-5-5"
# The sheet's own words leaking into the text: style rule 9 («لا تكتب عن المصادر ولا عن عملك»). The older stories' note
# («أرقام بيانات تيفو هي أرقام اليوم لا ذلك اليوم») was copied into a thin article to reach the word floor (2026-11-21).
LEAKS = ("ورقة الحقائق", "الورقة", "أرقام اليوم", "لا ذلك اليوم", "أرقام محدثة حتى اليوم", "محدّثة حتى اليوم")


def _checks(core, sheet, words):
    fails = check.check_news(core, sheet, words)
    text = " ".join([core.get("standfirst") or ""] + [p for s in core.get("sections") or [] for p in s.get("paragraphs") or []]
                    + list(core.get("facts_box") or []))
    fails += [f"the sheet's words «{w}» in the text: write the news, never about the sheet or Tifo's data" for w in LEAKS if w in text]
    return fails


def _ctx():
    store = Store(S3Backend(BUCKET))
    get = lambda p: store.get_json(p)
    j = store.get_state("news/state.json") or {}
    teams_json = get("teams.json") or {}
    from news import entities as E
    return store, get, j.get("stories") or {}, j.get("items") or {}, teams_json.get("teams", teams_json), E.load(teams_json).names


def _names(ar, s):
    return news_pick.words(" ".join(ar.get((k, int(i))) or "" for k, i in s.get("anchor") or []))


MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]


def _at(s):
    return datetime.fromisoformat((s or "1970-01-01T00:00:00+00:00").replace("Z", "+00:00"))


def export(d: Path, n: int, days=None):
    """days: (from, to) in days before now, by the story's last item: the journal's older stories (owner 2026-11-21: «اكتب
    اخبار من اليوم اول شي بعدين انتقل لاهم الاخبار من الايام والاسابيع والشهور الماضية»), biggest first (news_pick.rank_key),
    eligible as on their own day. Without it, the API's queue."""
    store, get, stories, items, teams, ar = _ctx()
    now = datetime.now(timezone.utc)
    nn = (store.get_state(STATE) or {}).get("news") or {}
    desk = store.get_state(DESK) or {}
    skip = set(nn.get("done") or {}) | set(desk.get("reject") or {}) | {a[2:] for a in nn.get("withdrawn") or []}
    skip |= {a["id"][2:] for a in (store.get_json(publish.ALL) or {}).get("articles") or [] if a["id"].startswith("n-")}
    recent = list(nn.get("recent") or [])
    (d / "sheets").mkdir(parents=True, exist_ok=True)
    if days:
        lo, hi = now - timedelta(days=days[1]), now - timedelta(days=days[0])
        pteam = {}
        try:
            pteam = (store.get_state("news/state.json") or {}).get("pteam") or {}
        except Exception:
            pass
        cands = [s for s in stories.values() if lo <= _at(s.get("last_at")) < hi
                 and news_pick.eligible(s, teams, pteam, _at(s.get("last_at")), items=items)]
        order = sorted(((news_pick.rank_key(s, items, teams), s["id"]) for s in cands), reverse=True)
    else:
        order = sorted(((q.get("rank") or [], sid) for sid, q in (nn.get("queue") or {}).items()), reverse=True)
    picked = []
    for _, sid in order:
        s = stories.get(sid)
        if not s or sid in skip or (d / f"{sid}.json").exists():
            continue
        when = _at(s.get("last_at")) if days else now
        if news_pick.near_duplicate(s, items, recent, when, _names(ar, s)):
            continue
        picked.append(s)
        first = items.get((s.get("items") or [""])[0]) or {}
        recent.append({"id": f"n-{sid}", "anchor": s.get("anchor"), "at": when.isoformat(),
                       "words": sorted(news_pick.words(first.get("title")) - _names(ar, s))})
        if len(picked) >= n:
            break

    def one(s):
        try:
            texts, _ = sources.collect(s, items)
            sheet, meta = facts.news_sheet(s, items, texts, get, ar, teams)
            date = None
            if days and days[1] > 1:                     # an older story: its day, and Tifo's numbers are today's
                f = _at(s.get("first_at") or s.get("last_at")).astimezone(timezone(timedelta(hours=4)))
                sheet["تاريخ الخبر"] = f"{f.day} {MONTHS_AR[f.month - 1]} {f.year}"
                sheet["ملاحظة"] = "الخبر من تاريخه أعلاه: اكتبه بزمنه. أرقام «بيانات تيفو» هي أرقام اليوم لا ذلك اليوم."
                date = _at(s.get("first_at") or s.get("last_at")).isoformat()
            cands = photo.news_candidates(texts, s, items, photo.commons(meta["query"]) if meta.get("query") else [])
            (d / "sheets" / f"{s['id']}.json").write_text(json.dumps(sheet, ensure_ascii=False, indent=1), encoding="utf-8")
            (d / f"{s['id']}.json").write_text(json.dumps({"story": s, "meta": meta, "cands": cands, "sheet": sheet, "title": _title(s, items), "date": date},
                                                          ensure_ascii=False), encoding="utf-8")
            return s["id"], None
        except Exception as e:
            return s["id"], f"{type(e).__name__}: {str(e)[:160]}"

    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(one, picked))
    print(json.dumps({"exported": sum(1 for _, e in res if not e), "errors": {k: e for k, e in res if e}}, ensure_ascii=False))


def _journal_busy():
    try:
        out = subprocess.run(["gh", "run", "list", "--workflow", "tifo-journal.yml", "--status", "in_progress", "--json", "databaseId"],
                             capture_output=True, text=True, timeout=60).stdout
        return bool(json.loads(out or "[]"))
    except Exception:
        return False


def _save_state(store, change):
    """Re-read, change, write: only between journal runs (the run saves the same file after each story)."""
    for _ in range(40):
        if not _journal_busy():
            break
        time.sleep(30)
    st = store.get_state(STATE) or {}
    change(st.setdefault("news", {}))
    store.put_state(STATE, st)


def publish_dir(d: Path, sids=()):
    store, get, stories, items, teams, ar = _ctx()
    words = tuple((TYPES.get("news") or {}).get("words") or (250, 450))
    (d / "fails").mkdir(exist_ok=True); (d / "done").mkdir(exist_ok=True)
    out = {"published": 0, "no_news": 0, "failed": 0, "dupes": 0, "taken": 0}
    pub, none = [], []
    recent = ((store.get_state(STATE) or {}).get("news") or {}).get("recent") or []
    for f in sorted((d / "arts").glob("*.json")):
        sid = f.stem
        if (d / "done" / f"{sid}.json").exists() or (sids and sid not in sids):
            continue
        rec = json.loads((d / f"{sid}.json").read_text(encoding="utf-8"))
        s, meta, cands, sheet = rec["story"], rec["meta"], rec["cands"], rec["sheet"]
        try:
            art = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as e:
            (d / "fails" / f"{sid}.json").write_text(json.dumps([f"not JSON: {e}"]), encoding="utf-8"); out["failed"] += 1; continue
        aid, now = f"n-{sid}", datetime.now(timezone.utc)
        if str(art.get("headline") or "").strip(" «»\"") == NO_NEWS:
            none.append((sid, len(s.get("items") or []))); out["no_news"] += 1
            (d / "done" / f"{sid}.json").write_text('"no news"', encoding="utf-8"); continue
        core = {k: art.get(k) for k in ("headline", "standfirst", "sections", "facts_box", "sources_cited")}
        fails = _checks(core, sheet, words)
        if fails:
            (d / "fails" / f"{sid}.json").write_text(json.dumps(fails, ensure_ascii=False, indent=1), encoding="utf-8"); out["failed"] += 1; continue
        (d / "fails" / f"{sid}.json").unlink(missing_ok=True)
        if store.get_json(f"news/a/{aid}.json"):                       # the API wrote it meanwhile
            out["taken"] += 1; (d / "done" / f"{sid}.json").write_text('"taken"', encoding="utf-8"); continue
        names = _names(ar, s)
        if news_pick.headline_duplicate(core["headline"], s.get("anchor"), recent + [r for _, _, r in pub], now, names, own=aid):
            out["dupes"] += 1; (d / "done" / f"{sid}.json").write_text('"duplicate"', encoding="utf-8"); continue
        img = photo.news_pick(aid, cands, meta["card_teams"], http_bytes, store, subject=meta["subject"], headline=core["headline"])
        doc = publish.article_doc(aid, "news", core, meta, img, MODEL, now.isoformat(), None)
        doc["breaking"] = False
        if rec.get("date"):                                            # an older story stands at its own day in the lists
            doc["published"] = rec["date"]
        topic, stage = art.get("topic"), art.get("stage")
        doc["topic"] = topic if topic in Writer.TOPICS else s.get("kind")
        doc["stage"] = (stage if stage in Writer.STAGES else None) if doc["topic"] == "transfer" else None
        doc["labelled"] = 1 if topic in Writer.TOPICS else 0
        publish.publish(store, doc)
        store.put_state(f"articles/sheets/{aid}.json", {"at": now.isoformat(), "sheet": sheet, "photos": cands})
        first = items.get((s.get("items") or [""])[0]) or {}
        pub.append((sid, {"at": now.isoformat(), "items": len(s.get("items") or []), "stage": s.get("stage"), "updates": 0},
                    {"id": aid, "anchor": s.get("anchor"), "words": sorted(news_pick.words(first.get("title")) - names),
                     "hw": sorted(news_pick.words(core["headline"]) - names), "at": now.isoformat()}))
        (d / "done" / f"{sid}.json").write_text('"published"', encoding="utf-8"); out["published"] += 1

    def change(n):
        n.setdefault("done", {}); n.setdefault("queue", {}); n.setdefault("failed", {}); n.setdefault("recent", [])
        for sid, done, rec in pub:
            n["done"][sid] = done; n["queue"].pop(sid, None)
            n["recent"] = [r for r in n["recent"] if r["id"] != rec["id"]][-299:] + [rec]
        for sid, k in none:                                            # back only if it grows, as the API's «لا خبر»
            f = n["failed"].setdefault(sid, {"tries": 0})
            f.update({"at": datetime.now(timezone.utc).isoformat(), "items": k, "tries": f["tries"] + 1}); n["queue"].pop(sid, None)
    if pub or none:
        _save_state(store, change)
    print(json.dumps(out, ensure_ascii=False))


def check_dir(d: Path, sids):
    """The writer's own check before it hands over: the publish step's check_news, no network."""
    words = tuple((TYPES.get("news") or {}).get("words") or (250, 450))
    for sid in sids or [f.stem for f in sorted((d / "arts").glob("*.json"))]:
        sheet = json.loads((d / "sheets" / f"{sid}.json").read_text(encoding="utf-8"))
        try:
            art = json.loads((d / "arts" / f"{sid}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(sid, "ERROR", e); continue
        if str(art.get("headline") or "").strip(" «»\"") == NO_NEWS:
            print(sid, "no news"); continue
        fails = _checks({k: art.get(k) for k in ("headline", "standfirst", "sections", "facts_box", "sources_cited")}, sheet, words)
        print(sid, "OK" if not fails else "FAIL " + json.dumps(fails, ensure_ascii=False))


def web_import(d: Path):
    """Sheets a researcher built from the web (sheets/<id>.json with «date_iso», «teams_en», «الصور» and verbatim source
    texts) -> the publish records: teams by their name in teams.json, the photo candidates from the sheet."""
    store, get, stories, items, teams, ar = _ctx()
    by_name = {}
    for tid, t in teams.items():
        for k in ("name", "name_ar", "short", "name_en"):
            if (t or {}).get(k):
                by_name.setdefault(str(t[k]).lower(), int(tid))
    n = 0
    for f in sorted((d / "sheets").glob("*.json")):
        sid = f.stem
        if (d / f"{sid}.json").exists():
            continue
        try:
            sheet = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        tids = [by_name[x.lower()] for x in sheet.pop("teams_en", []) or [] if isinstance(x, str) and x.lower() in by_name]
        photos = [c for c in sheet.pop("الصور", []) or [] if isinstance(c, dict) and c.get("url")]
        day = sheet.pop("date_iso", None)
        f.write_text(json.dumps(sheet, ensure_ascii=False, indent=1), encoding="utf-8")
        story = {"id": sid, "anchor": [["team", t] for t in tids], "items": [], "kind": None, "stage": None}
        meta = {"story": sid, "teams": tids, "players": [], "stage": None, "items": 0,
                "subject": ar.get(("team", tids[0])) if tids else None, "query": None, "card_teams": tids}
        date = f"{day}T12:00:00+00:00" if day else None
        (d / f"{sid}.json").write_text(json.dumps({"story": story, "meta": meta, "cands": photos, "sheet": sheet, "title": "", "date": date},
                                                  ensure_ascii=False), encoding="utf-8")
        n += 1
    print(json.dumps({"imported": n}))


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["export", "publish", "check", "web-import"])
    p.add_argument("dir")
    p.add_argument("sids", nargs="*")
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--days", help="FROM-TO days back, e.g. 0-1 (today), 1-7, 7-30")
    a = p.parse_args(argv)
    d = Path(a.dir)
    days = tuple(float(x) for x in a.days.split("-")) if a.days else None
    {"export": lambda: export(d, a.n, days), "publish": lambda: publish_dir(d, set(a.sids)), "check": lambda: check_dir(d, a.sids), "web-import": lambda: web_import(d)}[a.cmd]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
