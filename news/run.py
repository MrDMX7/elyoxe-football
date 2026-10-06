"""Tifo news: fetch every source, link each item to clubs/players/coaches, classify, merge into stories, write an
Arabic headline and summary per story, publish.

  python -m news.run                 # production: state and output in the data bucket (BUCKET env or the default below)
  python -m news.run --local DIR     # everything under DIR (tests, a dry look)
  python -m news.run --no-llm        # skip the Claude summaries (stories keep their best original headline)
  python -m news.run --no-media      # skip the official-videos step (news/media.py: v1/media/<match>.json)

Published (public, under v1/):
  news/latest.json              the newest stories, every kind
  news/e/<kind>-<id>.json       one per club, national team, player or coach: its stories
  news/transfers.json           transfer stories by player, with the furthest stage and who reported each step
State (private): state/news/state.json  items of the last days (dedupe, clustering), stories, the Google News cursor."""
import argparse, gzip, json, os, sys, time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import yaml
from store import Store, S3Backend, LocalBackend
from news import readers as RD, entities as E, classify as C, cluster as K, summarize as SM

BUCKET = os.environ.get("BUCKET", "elyoxe-football-574771023173-ap-south-1")
STATE = "news/state.json"


def now():
    return datetime.now(timezone.utc)


def iso(t):
    return t.isoformat().replace("+00:00", "Z")


def player_teams(store, comps):
    """player id -> team id from the league player tables (for weak mentions: «Kelly» counts only with her club)."""
    out = {}
    for cid in comps:
        try:
            d = store.get_json(f"comp/{cid}/players.json") or {}
        except ValueError:            # an empty or half-written file: that league just gives no mapping this run
            continue
        for pid, p in (d.get("players") or {}).items():
            if p.get("team"):
                out[int(pid)] = int(p["team"])
    return out


def display(story, items_by_id, D):
    srcs = K.sources_of(story, items_by_id)
    sm = story.get("summary") or {}
    ar = next((s for s in srcs if s["lang"] == "ar"), None)
    title, tlang = (sm.get("title_ar"), "ar") if sm.get("title_ar") else ((ar["title"], "ar") if ar else ((srcs[0]["title"], srcs[0]["lang"]) if srcs else ("", "")))
    return {"id": story["id"], "kind": story["kind"], "stage": story.get("stage"), "here_we_go": bool(story.get("here_we_go")),
            "title": title, "title_lang": tlang, "summary": sm.get("summary_ar"), "image": story.get("image"),
            "entities": [{"kind": k, "id": i, "name": D.names.get((k, i), "")} for k, i in (story.get("anchor") or story["entities"])],
            "mentions": [{"kind": k, "id": i, "name": D.names.get((k, i), "")} for k, i in story["entities"] if [k, i] not in (story.get("anchor") or [])],
            "sources": srcs, "reliability": K.reliability(srcs), "first_at": story["first_at"], "last_at": story["last_at"]}


def social(store, items, D, gen, n):
    """Official videos: news/social.json (every channel) and news/social/<team|comp>-<id>.json (one club's or league's)."""
    vids = sorted((v for v in items.values() if v.get("social")), key=lambda v: v.get("at") or "", reverse=True)
    card = lambda v: {"id": v["id"], "title": v["title"], "platform": "x" if "x.com/" in v["url"] else "youtube", "lang": v["lang"], "url": v["url"], "image": v.get("image"), "at": v["at"],
                      "channel": v["source"], "kind": v["kind"], "owner": v.get("owner"),
                      "entities": [{"kind": k, "id": i, "name": D.names.get((k, i), "")} for k, i in v.get("anchor") or [] if (k, i) in D.names]}
    store.put_json("news/social.json", {"generated": gen, "videos": [card(v) for v in vids[: max(60, n)]]}, cache="hot")
    groups = {}
    for v in vids:
        keys = {tuple(v["owner"])} if v.get("owner") else set()
        keys |= {tuple(e) for e in v.get("anchor") or [] if e[0] in ("team", "player")}
        for k in keys:
            groups.setdefault(k, []).append(v)
    for (k, i), vs in groups.items():
        store.put_json(f"news/social/{k}-{i}.json", {"generated": gen, "owner": {"kind": k, "id": i, "name": D.names.get((k, i), "")},
                                                     "videos": [card(v) for v in vs[:n]]}, cache="warm")


def transfers(stories, items_by_id, D):
    by_player = {}
    for s in stories:
        if s["kind"] != "transfer":
            continue
        for k, i in (s.get("anchor") or []):
            if k != "player":
                continue
            p = by_player.setdefault(i, {"player": {"id": i, "name": D.names.get(("player", i), "")}, "stage": None, "stories": []})
            srcs = K.sources_of(s, items_by_id)
            p["stories"].append({"id": s["id"], "stage": s.get("stage"), "at": s["first_at"], "first": srcs[0]["name"] if srcs else None,
                                 "title": (s.get("summary") or {}).get("title_ar") or (srcs[0]["title"] if srcs else "")})
            if C.STAGE_RANK.get(s.get("stage"), -1) > C.STAGE_RANK.get(p["stage"], -1):
                p["stage"] = s.get("stage")
    for p in by_player.values():
        p["stories"].sort(key=lambda x: x["at"] or "")
    return sorted(by_player.values(), key=lambda p: (-C.STAGE_RANK.get(p["stage"], -1), -(len(p["stories"]))))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--local"); ap.add_argument("--no-llm", action="store_true"); ap.add_argument("--no-media", action="store_true")
    ap.add_argument("--no-tv", action="store_true", help="skip «منو يعلّق؟» (news/commentators.py)")
    ap.add_argument("--no-push", action="store_true", help="the media step hands no goal clip to the web push sender")
    a = ap.parse_args(argv)
    t0 = time.time()
    store = Store(LocalBackend(a.local)) if a.local else Store(S3Backend(BUCKET))
    cfg = yaml.safe_load(open(os.path.join(HERE, "sources.yaml"), encoding="utf-8"))
    st = cfg.get("settings") or {}
    state = store.get_state(STATE) or {}
    items = state.get("items") or {}
    stories = state.get("stories") or {}
    teams = store.get_json("teams.json") or {}
    D = E.load(teams)
    if state.get("pteam_day") != now().date().isoformat() or not state.get("pteam"):
        import config
        state["pteam"] = {str(k): v for k, v in player_teams(store, config.settings().get("player_stats_comps", [])).items()}
        state["pteam_day"] = now().date().isoformat()
    D.player_team = {int(k): v for k, v in (state.get("pteam") or {}).items()}

    # ---- fetch: every feed, plus a rotating slice of the Google News queries
    srcs = list(cfg["sources"]) + [RD.youtube_source(y) for y in cfg.get("youtube") or []]
    qs = (cfg.get("gnews") or {}).get("queries") or []
    per = (cfg.get("gnews") or {}).get("per_run", 12)
    cur = state.get("gcursor", 0) % max(1, len(qs))
    for q in (qs[cur:] + qs[:cur])[:per]:
        srcs.append(RD.gnews_source(q, cfg["gnews"]))
    state["gcursor"] = (cur + per) % max(1, len(qs))
    errors, fresh = {}, []
    cutoff = iso(now() - timedelta(days=st.get("keep_items_days", 5)))
    # X: the laptop's reader uploads its inbox to state/news/x-inbox.json; a local inbox (a hand run on this machine) counts too
    s3box = store.get_state("news/x-inbox.json") or {}
    try:
        xbox = {"items": s3box.get("items", []) + json.load(open(os.path.join(HERE, ".x-inbox.json"), encoding="utf-8")).get("items", [])}
    except (OSError, ValueError):
        xbox = s3box
    state["x"] = {"reader_last_run": s3box.get("last_run"), "reader_errors": s3box.get("errors"), "posts": len(xbox.get("items") or [])}
    # where a run's time goes (2026-10-06: runs grew from ~90 s to 10-20 min and half of them timed out at 20)
    t1 = time.time(); steps = {"start": round(t1 - t0, 1)}
    batches = [RD.read_source(s) + (s,) for s in srcs] + [(RD.x_posts(xbox), None, {"key": "x"})]
    steps["fetch"] = round(time.time() - t1, 1); t1 = time.time()
    for got, err, s in batches:
        if err:
            errors[s.get("query") or s["key"]] = err
        for it in got:
            if it["id"] in items or not it.get("at") or it["at"] < cutoff or C.other_sport(it):
                continue
            it["anchor"] = [list(e) for e in E.link(D, it["title"], it.get("query"))]      # who the headline is about
            it["entities"] = [list(e) for e in E.link(D, it["title"] + " " + (it.get("desc") or ""), it.get("query"))]
            if it["kind"] == "youtube" or (it["kind"] == "x" and it["tier"] == "official"):
                # an official video or post: its channel's club or league is always one of its subjects; it is classified like any
                # headline (not "official" for being on the club's channel), and only news-like titles join the stories
                own = it.get("owner")
                if own and own[0] == "team" and own not in it["anchor"]:
                    it["anchor"].append(own)
                if own and own[0] == "team" and own not in it["entities"]:
                    it["entities"].append(own)
                if C.womens(it):       # the club id is the men's side: a women's-team video would land on the wrong page
                    continue
                # the title only: a channel's description is boilerplate («the official channel of…», «deal» in a sponsor line)
                it.update(C.classify({"title": it["title"], "tier": "paper"}))
                it["social"] = True
                items[it["id"]] = it
                if it["kind"] in ("injury", "presser") or (it["kind"] == "transfer" and C.STAGE_RANK[it["stage"]] >= C.STAGE_RANK["agreed"]):
                    fresh.append(it)
                continue
            it.update(C.classify(it))
            items[it["id"]] = it
            fresh.append(it)

    steps["link"] = round(time.time() - t1, 1); t1 = time.time()
    # ---- stories
    touched = K.assign(stories, fresh)
    steps["cluster"] = round(time.time() - t1, 1); t1 = time.time()
    # ---- Arabic headline + summary: new stories and stories that gained two or more items since their summary
    todo = [s for s in touched.values() if not s.get("summary") or len(s["items"]) >= s.get("summary_items", 0) + 2]
    todo.sort(key=lambda s: s["last_at"] or "", reverse=True)
    done = 0
    if not a.no_llm:
        for s in todo[: st.get("summarize_per_run", 25)]:
            names = [D.names.get(tuple(e), "") for e in s["entities"]]
            res = SM.summarize(s, K.sources_of(s, items), [n for n in names if n])
            if res:
                s["summary"], s["summary_items"] = res, len(s["items"])
                if C.STAGE_RANK.get(res.get("stage"), -1) > C.STAGE_RANK.get(s.get("stage"), -1):
                    s["stage"] = res["stage"]
                done += 1

    steps["summaries"] = round(time.time() - t1, 1); t1 = time.time()
    # ---- prune, then publish
    items = {k: v for k, v in items.items() if (v.get("at") or "") >= cutoff}
    scut = iso(now() - timedelta(days=st.get("keep_clusters_days", 10)))
    stories = {k: v for k, v in stories.items() if (v.get("last_at") or "") >= scut}
    newest = sorted(stories.values(), key=lambda s: s["last_at"] or "", reverse=True)
    gen = iso(now())
    store.put_json("news/latest.json", {"generated": gen, "stories": [display(s, items, D) for s in newest[: st.get("latest_count", 150)]]}, cache="hot")
    ents = {tuple(e) for s in touched.values() for e in (s.get("anchor") or [])}
    for k, i in ents:     # a page lists the stories whose HEADLINE names it
        mine = [s for s in newest if [k, i] in (s.get("anchor") or [])][: st.get("entity_count", 40)]
        store.put_json(f"news/e/{k}-{i}.json", {"generated": gen, "entity": {"kind": k, "id": i, "name": D.names.get((k, i), "")},
                                                "stories": [display(s, items, D) for s in mine]}, cache="warm")
    social(store, items, D, gen, st.get("social_count", 24))
    store.put_json("news/transfers.json", {"generated": gen, "players": transfers(newest, items, D)[:200]}, cache="warm")
    steps["publish"] = round(time.time() - t1, 1)
    state.update({"items": items, "stories": stories, "run": {"at": gen, "fresh": len(fresh), "stories_touched": len(touched),
                  "summaries": done, "errors": errors, "secs": round(time.time() - t0, 1), "steps": steps, "entities": len(ents)}})
    store.put_state(STATE, state)
    print(json.dumps(state["run"], ensure_ascii=False))
    # ---- official videos by the matches and their goals (news/media.py): the journal's YouTube feeds are reused, never fatal
    if not a.no_media:
        try:
            from news import media
            yt = {s["key"]: got for got, err, s in batches if s and s.get("kind") == "youtube" and not err}
            res = media.step(store, cfg, prefetched=yt, xbox=xbox, push=None if a.no_push else "auto")   # «فيديو الهدف نزل»
            print(json.dumps({"media": {k: v for k, v in res.items() if k != "found"}}, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"media_error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False))
    # «منو يعلّق؟»: channels and commentators per match (v1/tv/<ymd>.json). Its own state and pace (the sitemap every 30 min,
    # an article at most hourly); a failure there never costs the news run
    if not a.no_tv:
        try:
            from news import commentators as TV
            TV.run(store)
        except Exception as e:
            print(json.dumps({"tv_error": str(e)[:300]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
