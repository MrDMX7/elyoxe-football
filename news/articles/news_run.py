"""The news pass (Phase 2a), after the match reports, on the same spend and state.

  journal state -> eligible stories (news_pick) -> the queue (20 min; the desk file) -> source texts (sources) -> sheet
  (facts.news_sheet) -> Sonnet 5.5 -> check_news (one rewrite) -> photo -> v1/news/a/n-<story id>.json

«عاجل» goes out at once, by Haiku 5.5, under the same id; the full article replaces it when its turn comes. It is for an
official announcement of a signing, a sacking, an injury or a sanction (spec, type 8), 15 a day at most. classify.py makes
every non-match post of an official account kind «official», a birthday greeting too, and classify.official() passes «OFFICIAL:
our new home kit»; so the official post must pass classify.official() and name one of those events (news_pick.event). An
injury from an official account needs no more.

A story that fails is tried again only when it grows, twice at most (desk_queue). Updates happen in place, at most hourly and
three times. Each story is checked against the last day's articles again just before it is written, so two halves of one
story queued together make one article. No rewrite starts past the deadline: the story waits for the next run. The desk's
«withdraw» takes an article off both lists for good."""
import json
from pathlib import Path
from news import classify as CL
from . import news_pick, desk_queue, sources, facts, check, photo, publish

TYPES = json.loads(Path(__file__).with_name("types.json").read_text(encoding="utf-8"))
STATE, DESK = "articles/state.json", "articles/desk.json"
PHOTO_MODEL = "claude-haiku-5-5"
BREAKING_DAILY = 15          # the spec's 5-15 a day
GRACE = 45                   # seconds past the deadline a rewrite may still start (the step is killed at minute 10)
LATER = "later"              # a story out of time: it stays queued for the next run
EDITED = "edited"            # the owner edited the article on the desk: never rewritten automatically (spec, «The desk»)
DUP = "duplicate"            # our written headline is an article of the last day (news_pick.headline_duplicate)
VIEW = "articles/desk-view.json"
VIEW_MAX = 150


class OutOfTime(Exception):
    pass


def breaking(story, items):
    offs = [items[i] for i in story.get("items") or [] if (items.get(i) or {}).get("tier") == "official"]
    if story.get("kind") == "injury":
        return bool(offs)
    return (story.get("kind") in ("transfer", "official") and any(CL.official(o.get("title")) for o in offs)
            and news_pick.event(story, items))


def _write(writer, sp, cfg, sheet, job, more=lambda: True):
    notes = None
    for attempt in (1, 2):
        if attempt == 2 and not more():
            raise OutOfTime()
        art, usage = writer.write("news", sheet, cfg["model"], notes=notes)
        sp.add(cfg["model"], usage, job); sp.save()       # a killed step keeps what was spent
        notes = check.check_news(art, sheet, tuple(cfg["words"]))
        if not notes:
            return art, None
    return None, notes


def run_news(store, journal, data_get, writer, now, sp, *, deadline, clock, collect=sources.collect, fetch=None, teams_json=None, ar=None,
             commons=photo.commons):
    out = {"queued": 0, "written": 0, "breaking": 0, "updated": 0, "failed": 0, "withdrawn": 0, "dupes": 0,
           "links": 0, "decoded": 0, "texts": 0}
    news, brk = TYPES.get("news") or {}, TYPES.get("breaking") or {}
    state, desk = store.get_state(STATE) or {}, store.get_state(DESK) or {}
    n = state.setdefault("news", {})

    gone = n.setdefault("withdrawn", [])
    for aid in desk.get("withdraw") or {}:
        if aid not in gone:
            publish.withdraw(store, aid, now.isoformat()); gone.append(aid); out["withdrawn"] += 1
    if not (news.get("on") or brk.get("on")):
        store.put_state(STATE, state); return out

    stories, items, pteam = journal["stories"], journal["items"], journal.get("pteam") or {}
    teams_json = teams_json if teams_json is not None else (data_get("teams.json") or {})
    teams = teams_json.get("teams", teams_json)
    if ar is None:
        from news import entities as E
        ar = E.load(teams_json).names
    q = desk_queue.Queue(state, desk, now, news)
    recent = n.setdefault("recent", [])
    names = lambda s: news_pick.words(" ".join(ar.get((k, int(i))) or "" for k, i in s.get("anchor") or []))
    dup = lambda s: s["id"] not in n["done"] and news_pick.near_duplicate(s, items, recent, now, names(s))
    cands = sorted((s for s in stories.values() if news_pick.eligible(s, teams, pteam, now, items=items) and f"n-{s['id']}" not in gone),
                   key=lambda s: news_pick.rank_key(s, items, teams), reverse=True)
    offered, dups = [], set()
    for s in cands:
        if dup(s):
            out["dupes"] += 1; dups.add(s["id"]); continue
        q.offer(s["id"], news_pick.rank_key(s, items, teams), items=len(s.get("items") or [])); offered.append(s)
    q.prune({s["id"] for s in offered})
    out["queued"] = len(q.n["queue"])

    def save():
        store.put_state(STATE, state); sp.save()

    def publish_story(s, is_breaking):
        """One story; whatever it raises is that story's failure, never the pass's (dry run 2026-11-19)."""
        try:
            return _publish_story(s, is_breaking)
        except OutOfTime:
            return LATER
        except Exception as e:
            out["failed"] += 1
            print(json.dumps({"news_error": s["id"], "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False))
            return None

    def _publish_story(s, is_breaking):
        aid = f"n-{s['id']}"
        if aid in gone:                                       # withdrawn from the desk: never back
            return None
        prev = store.get_json(f"news/a/{aid}.json")
        if prev and prev.get("edited"):                       # the owner's text stands; the desk flags the story's growth
            grew.add(s["id"])
            return EDITED
        texts, counts = collect(s, items)
        for k in ("links", "decoded", "texts"):
            out[k] += counts[k]
        sheet, meta = facts.news_sheet(s, items, texts, data_get, ar, teams, breaking=is_breaking)
        cfg = brk if is_breaking else news
        art, fails = _write(writer, sp, cfg, sheet, "breaking" if is_breaking else "news", more=lambda: clock() <= deadline + GRACE)
        if not art:
            out["failed"] += 1
            print(json.dumps({"news_failed": s["id"], "fails": (fails or [])[:4]}, ensure_ascii=False)); return None
        if prev is None:                                      # a first version only: an update of our own article is ours
            twin = news_pick.headline_duplicate(art["headline"], s.get("anchor"), recent, now, names(s), own=aid)
            if twin:
                out["dupes"] += 1
                print(json.dumps({"news_duplicate": s["id"], "of": twin, "headline": art["headline"]}, ensure_ascii=False)); return DUP
        def judge(headline, thumbs, sources):
            best, usage = writer.pick_photo(headline, thumbs, sources=sources)
            sp.add(PHOTO_MODEL, usage, "photo"); sp.save()
            return best
        cands = photo.news_candidates(texts, s, items, commons(meta["query"]) if meta.get("query") else [])
        img = photo.news_pick(aid, cands, meta["card_teams"], fetch or (lambda u: None), store, subject=meta["subject"],
                              headline=art["headline"], judge=judge)
        doc = publish.article_doc(aid, "news", art, meta, img, cfg["model"], now.isoformat(), prev)
        doc["breaking"] = is_breaking
        doc["topic"], doc["stage"] = s.get("kind"), s.get("stage")      # the news page's filters
        publish.publish(store, doc)
        store.put_state(f"articles/sheets/{aid}.json", {"at": now.isoformat(), "sheet": sheet, "photos": cands})   # the desk's editor
        first = items.get((s.get("items") or [""])[0]) or {}
        recent[:] = [r for r in recent if r["id"] != aid][-299:] + [
            {"id": aid, "anchor": s.get("anchor"), "words": sorted(news_pick.words(first.get("title")) - names(s)),
             "hw": sorted(news_pick.words(art["headline"]) - names(s)), "at": now.isoformat()}]
        return meta

    rej = set(desk.get("reject") or {})
    grew = set(n.get("grew") or [])
    if brk.get("on"):                                         # «عاجل» first, at once
        sent = n.setdefault("breaking", [])
        if n.get("breaking_day") != q.n["day"]:
            n["breaking_day"], n["breaking_count"] = q.n["day"], 0
        for s in offered:
            if clock() > deadline or not sp.allowed() or n["breaking_count"] >= BREAKING_DAILY:
                break
            if s["id"] not in sent and s["id"] not in n["done"] and s["id"] not in rej and breaking(s, items) and not dup(s):
                r = publish_story(s, True)
                if r == LATER:
                    break
                if r and r not in (DUP, EDITED):
                    out["breaking"] += 1; n["breaking_count"] += 1
                sent.append(s["id"]); del sent[:-500]; save()
    if news.get("on"):
        for sid in q.ready():
            if clock() > deadline or not sp.allowed():
                break
            s = stories[sid]
            if dup(s):                                         # its other half was written earlier in this run
                q.n["queue"].pop(sid, None); out["dupes"] += 1; continue
            r = publish_story(s, False)
            if r == LATER:
                break
            if r == EDITED:
                q.mark_written(sid, len(s.get("items") or []), s.get("stage"))
            elif r == DUP:
                q.mark_failed(sid, len(s.get("items") or []))  # the same news: back only if it grows, twice at most
            elif r:
                q.mark_written(sid, len(s.get("items") or []), s.get("stage")); out["written"] += 1
            else:
                q.mark_failed(sid, len(s.get("items") or []))  # back only when it grows, twice at most
            save()
        for sid in list(n["done"]):
            s = stories.get(sid)
            if not s or clock() > deadline or not sp.allowed():
                continue
            if q.wants_update(sid, len(s.get("items") or []), s.get("stage")):
                r = publish_story(s, False)
                if r == LATER:
                    break
                if r and r not in (EDITED, DUP):
                    out["updated"] += 1
                q.mark_written(sid, len(s.get("items") or []), s.get("stage"))   # tried: the next try is an hour away
                save()
    n["grew"] = sorted(g for g in grew if g in n["done"])
    store.put_state(VIEW, _view(cands, stories, items, ar, q, n, rej, set(desk.get("write") or {}), dups, gone, grew, news, now))
    save()
    return out


def _title(s, items):
    sm = s.get("summary") or {}
    its = [items[i] for i in s.get("items") or [] if i in items]
    return sm.get("title_ar") or next((i.get("title") for i in its if i.get("lang") == "ar"), None) or (its[0].get("title") if its else "")


def _view(cands, stories, items, ar, q, n, rej, now_, dups, gone, grew, cfg, now):
    """What the desk shows (spec, «The desk»): the day's candidates biggest first, each with its state."""
    from datetime import datetime, timedelta
    wait = timedelta(minutes=cfg.get("wait_minutes", 20))
    rows = []
    for s in cands[:VIEW_MAX]:
        sid, aid = s["id"], f"n-{s['id']}"
        its = [items[i] for i in s.get("items") or [] if i in items]
        row = {"id": sid, "title": _title(s, items), "kind": s.get("kind"), "stage": s.get("stage"),
               "outlets": len({i.get("source") for i in its}), "sources": list(dict.fromkeys(i.get("source") for i in its))[:4],
               "names": [ar[(k, int(i))] for k, i in s.get("anchor") or [] if ar.get((k, int(i)))][:4],
               "last_at": s.get("last_at"), "grew": sid in grew, "breaking": sid in (n.get("breaking") or [])}
        if aid in gone:
            row["status"] = "withdrawn"
        elif sid in n["done"]:
            row.update(status="written", article=aid)
        elif sid in rej:
            row["status"] = "rejected"
        elif sid in q.n["queue"]:
            due = now if sid in now_ else datetime.fromisoformat(q.n["queue"][sid]["first"]) + wait
            row.update(status="queued", due=due.isoformat(), now=sid in now_)
        elif sid in (n.get("failed") or {}):
            row["status"] = "failed"
        elif sid in dups:
            row["status"] = "duplicate"
        else:
            row["status"] = "waiting"
        rows.append(row)
    return {"generated": now.isoformat(), "day": q.n["day"], "written_today": q.n["count"], "daily": cfg.get("daily", 60),
            "breaking_today": n.get("breaking_count", 0), "stories": rows}
