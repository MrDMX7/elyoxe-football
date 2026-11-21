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
from datetime import datetime, timezone
from pathlib import Path
from store import Store, S3Backend
from . import news_pick, sources, facts, check, photo, publish
from .news_run import TYPES, STATE, DESK, _title
from .run import BUCKET, http_bytes
from .write import NO_NEWS, Writer

MODEL = "claude-sonnet-5-5"


def _ctx():
    store = Store(S3Backend(BUCKET))
    get = lambda p: store.get_json(p)
    j = store.get_state("news/state.json") or {}
    teams_json = get("teams.json") or {}
    from news import entities as E
    return store, get, j.get("stories") or {}, j.get("items") or {}, teams_json.get("teams", teams_json), E.load(teams_json).names


def _names(ar, s):
    return news_pick.words(" ".join(ar.get((k, int(i))) or "" for k, i in s.get("anchor") or []))


def export(d: Path, n: int):
    store, get, stories, items, teams, ar = _ctx()
    now = datetime.now(timezone.utc)
    nn = (store.get_state(STATE) or {}).get("news") or {}
    desk = store.get_state(DESK) or {}
    skip = set(nn.get("done") or {}) | set(desk.get("reject") or {}) | {a[2:] for a in nn.get("withdrawn") or []}
    recent = nn.get("recent") or []
    (d / "sheets").mkdir(parents=True, exist_ok=True)
    order = sorted(((q.get("rank") or [], sid) for sid, q in (nn.get("queue") or {}).items()), reverse=True)
    picked = []
    for _, sid in order:
        s = stories.get(sid)
        if not s or sid in skip or (d / f"{sid}.json").exists():
            continue
        if news_pick.near_duplicate(s, items, recent, now, _names(ar, s)):
            continue
        picked.append(s)
        if len(picked) >= n:
            break

    def one(s):
        try:
            texts, _ = sources.collect(s, items)
            sheet, meta = facts.news_sheet(s, items, texts, get, ar, teams)
            cands = photo.news_candidates(texts, s, items, photo.commons(meta["query"]) if meta.get("query") else [])
            (d / "sheets" / f"{s['id']}.json").write_text(json.dumps(sheet, ensure_ascii=False, indent=1), encoding="utf-8")
            (d / f"{s['id']}.json").write_text(json.dumps({"story": s, "meta": meta, "cands": cands, "sheet": sheet, "title": _title(s, items)},
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
        fails = check.check_news(core, sheet, words)
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
        fails = check.check_news({k: art.get(k) for k in ("headline", "standfirst", "sections", "facts_box", "sources_cited")}, sheet, words)
        print(sid, "OK" if not fails else "FAIL " + json.dumps(fails, ensure_ascii=False))


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["export", "publish", "check"])
    p.add_argument("dir")
    p.add_argument("sids", nargs="*")
    p.add_argument("--n", type=int, default=40)
    a = p.parse_args(argv)
    d = Path(a.dir)
    {"export": lambda: export(d, a.n), "publish": lambda: publish_dir(d, set(a.sids)), "check": lambda: check_dir(d, a.sids)}[a.cmd]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
