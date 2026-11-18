"""Tifo articles, Phase 1: match reports. A step of the 15-minute journal job (tools/runner.py job_journal):

  python -m news.articles.run                    # S3 (GitHub Actions)
  python -m news.articles.run --local DIR --dry  # read the live site over HTTP, write into DIR, publish nothing

For each finished priority match of today or yesterday (UAE days): fact sheet -> Sonnet 5.5 -> checks (one rewrite with the
failures, then drop) -> photo -> v1/news/a/r-<id>.json. State in state/articles/state.json: a written match is not written
again unless its fingerprint (score, goals, red cards) changes; a thin match (no events, no stats) is skipped once; API errors
leave it due, three tries at most. Spend is checked before every call; at $180 in a month nothing is written and one email
goes out. types.json «on» false: nothing is written (the switch the owner can flip without a deploy)."""
import argparse, gzip, json, os, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from store import Store, S3Backend, LocalBackend  # noqa: E402
from . import facts, due, check, spend, write, photo, publish  # noqa: E402

TYPES = json.loads(Path(__file__).with_name("types.json").read_text(encoding="utf-8"))
STATE = "articles/state.json"
BUCKET = os.environ.get("BUCKET", "elyoxe-football-574771023173-ap-south-1")
UAE = timezone(timedelta(hours=4))
MAX_TRIES = 3


def http_get(path):
    try:
        raw = urllib.request.urlopen(urllib.request.Request("https://tifo.elyoxe.com/v1/" + path,
                                     headers={"Accept-Encoding": "gzip", "User-Agent": "tifo-articles"}), timeout=60).read()
        return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    except Exception:
        return None


def http_bytes(url):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tifo-articles"}), timeout=30).read()
    except Exception:
        return None


def _mail_cap(total):
    try:
        import boto3
        boto3.client("ses", region_name="ap-south-1").send_email(
            Source="تيفو <hello@elyoxe.com>", Destination={"ToAddresses": ["hello@elyoxe.com"]},
            Message={"Subject": {"Data": f"مقالات تيفو توقفت: الصرف وصل ${total:.2f} هذا الشهر"},
                     "Body": {"Text": {"Data": "وصل صرف المقالات إلى سقف 180 دولار لهذا الشهر، فتوقفت الكتابة حتى بداية الشهر الجاي."}}})
    except Exception as e:
        print(json.dumps({"cap_mail_error": str(e)[:200]}))


def run(store, data_get, writer, now, *, dry=False, only=None, limit=None, fetch=None, budget=8 * 60, clock=time.monotonic):
    """budget: seconds; no new match is started after it (the runner kills the step at 10 min). The state and the spend are
    saved after every match, so a killed run loses at most the match it was on (final review, 2026-11-18)."""
    out = {"due": 0, "written": 0, "failed": 0, "thin": 0, "skipped": None, "stopped": None}
    cfg = TYPES.get("report") or {}
    if not cfg.get("on"):
        out["skipped"] = "report is off in types.json"; return out
    sp = spend.Spend(store, now)
    if not sp.allowed():
        out["skipped"] = f"cap: ${sp.month_total():.2f} this month"; return out
    state = store.get_state(STATE) or {}
    reps = state.setdefault("reports", {})
    deadline = clock() + budget
    uae = now.astimezone(UAE)
    days = [data_get(f"all/{(uae - timedelta(days=d)).strftime('%Y%m%d')}.json") for d in (0, 1)]
    ids = [only] if only else due.finished_priority(days, set(config.awarded()))
    names = facts.load_names()
    n = 0

    def save():
        store.put_state(STATE, state); sp.save()

    for mid in ids:
        if limit and n >= limit:
            break
        if clock() > deadline:
            out["stopped"] = "time budget"; break
        rec = reps.get(str(mid)) or {}
        if rec.get("status") == "failed" and not rec.get("fp"):
            continue                # three errors before its sheet could be built: dropped
        fp = None
        try:
            md = data_get(f"match/{mid}.json")
            if not md or md.get("status") != "finished":
                continue
            standings = data_get(f"comp/{md['comp']}/standings.json")
            fixtures = data_get(f"comp/{md['comp']}/fixtures.json")
            sheet, meta = facts.report_sheet(md, standings, fixtures, names)
            fp = meta["fingerprint"]
            if rec.get("status") in ("done", "thin", "failed") and rec.get("fp") == meta["fingerprint"]:
                continue
            out["due"] += 1
            if meta["thin"]:
                reps[str(mid)] = {"status": "thin", "fp": meta["fingerprint"], "at": now.isoformat()}; out["thin"] += 1; save(); continue
            if not sp.allowed():
                break
            n += 1
            art, notes, ok = None, None, False
            for attempt in (1, 2):
                art, usage = writer.write("report", sheet, cfg["model"], notes=notes)
                sp.add(cfg["model"], usage, "report")
                notes = check.check_article(art, sheet, md, words=cfg.get("words"))
                if not notes:
                    ok = True; break
            if not ok:
                if rec.get("status") == "done":     # a corrected match whose rewrite failed: its old report is now wrong
                    publish.withdraw(store, f"r-{mid}", now.isoformat())
                    print(json.dumps({"report_withdrawn": mid}))
                reps[str(mid)] = {"status": "failed", "fp": meta["fingerprint"], "at": now.isoformat(), "fails": notes[:5]}
                out["failed"] += 1; print(json.dumps({"report_failed": mid, "fails": notes[:5]}, ensure_ascii=False)); save(); continue
            aid = f"r-{mid}"
            img = photo.pick(aid, md, data_get(f"media/{mid}.json"), fetch or http_bytes, store)
            prev = store.get_json(f"news/a/{aid}.json")
            doc = publish.article_doc(aid, "report", art, meta, img, cfg["model"], now.isoformat(), prev)
            publish.publish(store, doc)
            reps[str(mid)] = {"id": aid, "status": "done", "fp": meta["fingerprint"], "at": now.isoformat(), "card": img["card"]}
            out["written"] += 1
        except Exception as e:      # API errors, refusals, a bad file, S3: this match stays due (three tries), the others go on
            tries = (rec.get("tries") or 0) + 1
            reps[str(mid)] = dict(rec, tries=tries, fp=fp or rec.get("fp"), at=now.isoformat(), status="failed" if tries >= MAX_TRIES else "retry",
                                  error=f"{type(e).__name__}: {str(e)[:200]}")
            out["failed"] += 1
        save()
    # a report published with the match card gets a frame of the match when the highlights come out (48 h)
    for mid, rec in reps.items():
        if clock() > deadline:
            break
        if rec.get("status") == "done" and rec.get("card") and rec.get("at", "") >= (now - timedelta(hours=48)).isoformat():
            try:
                md = data_get(f"match/{mid}.json"); media = data_get(f"media/{mid}.json")
                if md and media:
                    img = photo.pick(rec["id"], md, media, fetch or http_bytes, store)
                    if not img["card"]:
                        doc = store.get_json(f"news/a/{rec['id']}.json")
                        if doc:
                            doc["image"], doc["modified"] = img, now.isoformat(); publish.publish(store, doc); rec["card"] = False
            except Exception as e:
                print(json.dumps({"frame_upgrade_error": mid, "error": str(e)[:200]}))
    save()
    if sp.capped_now():
        _mail_cap(sp.month_total())
    out["spend_month"] = round(sp.month_total(), 4)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--local"); ap.add_argument("--dry", action="store_true"); ap.add_argument("--match", type=int); ap.add_argument("--limit", type=int)
    a = ap.parse_args(argv)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(json.dumps({"articles": "no ANTHROPIC_API_KEY, skipped"})); return 0
    if a.dry and not a.local:
        print(json.dumps({"articles": "--dry needs --local DIR (it would publish to S3)"})); return 2
    if a.local:
        store, get = Store(LocalBackend(a.local)), http_get
    else:
        store = Store(S3Backend(BUCKET)); get = lambda p: store.get_json(p)
    t0, now = time.monotonic(), datetime.now(timezone.utc)
    if a.dry:
        TYPES["report"]["on"] = True
    out = run(store, get, write.Writer(), now, dry=a.dry, only=a.match, limit=a.limit, budget=6 * 60)
    if not a.match:
        from . import news_run
        j = store.get_state("news/state.json") or {}
        sp = spend.Spend(store, now)                 # reads what run() saved
        if a.dry:
            news_run.TYPES["news"]["on"] = news_run.TYPES["breaking"]["on"] = True
        out["news"] = news_run.run_news(store, {k: j.get(k) or {} for k in ("stories", "items", "pteam")}, get, write.Writer(), now, sp,
                                        deadline=t0 + 8 * 60, clock=time.monotonic, fetch=http_bytes)
    print(json.dumps({"articles": out}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
