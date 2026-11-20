"""The official clip of every goal of the last month, and every match's highlights (owner 2026-11-19: «اريدك تحط جميع الاهداف
خلال الشهر الماضي فتيفو سواء من اليوتيوب او من السوشال ميديا … بدون ما يستهلك api»).

  python -m news.media_backfill [--days 32] [--dry] [--explain MATCH_ID] [--relist] [--only-new]

news/media.py follows a match for 48 h (its highlights for 7 days) with what the channels' RSS feeds hold (their last 15
uploads) and the X reader's inbox (its last 800 posts): a league channel that posts 40 clips on a match night rotates its feed
faster than the journal reads it, and a goal whose clip went by in between never got one. This goes back `--days`:
  - the matches: the day files of those UAE days, finished; their final match files (the goal list complete);
  - YouTube: every channel of news/sources.yaml (`youtube:` and `media: youtube:`) listed through yt-dlp, its /videos and
    /shorts tabs (titles only, no API key); then, for each title that names a team or a scorer of one of those matches and
    reads as a summary or a goal, its watch page: the exact upload time and the description;
  - X: the posts with a video in state/news/x-inbox.json and state/news/x-history.json (news/xhistory.js reads further back);
  - the same attach(), FotMob links and embed check (oEmbed) as media.py: a clip goes on a goal only when its title passes
    every check there;
  - what it found is added to the published media files (nothing in them is removed) and kept in state/news/media-extra.json
    for the last 9 days, which media.py merges into every file it writes, so its next run does not take them away.
No paid API (no Gemini, no Claude, no YouTube Data API): YouTube's public pages and oEmbed, the X session's own page loads.
Cache (listings 6 h, pages for ever): news/.cache/backfill/."""
import argparse, concurrent.futures as CF, json, os, re, subprocess, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from news import media as M  # noqa: E402

UTC = timezone.utc
CACHE = os.path.join(HERE, ".cache", "backfill")
LIST_TTL_H = 6
LIMIT = {"videos": 1800, "shorts": 1800}       # a month of AD Sports or the MLS is ~900 uploads; older ones are cut by date
KEEP_EXTRA_D = 9                               # media.py's window (7 days) and its cache (a day), and a day more
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
DESC = re.compile(r'"shortDescription":"((?:[^"\\]|\\.)*)"')
DATE = re.compile(r'"(?:uploadDate|publishDate)":"(\d{4}-\d\d-\d\dT[^"]+)"')


def jload(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def jsave(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, p)


# ------------------------------------------------------------------------------------------------ matches
def matches_of(store, t, days):
    """The finished matches of the last `days` UAE days, from their final match files (slimmed as media.py keeps them)."""
    ds = [(t + timedelta(hours=4) - timedelta(days=d)).strftime("%Y%m%d") for d in range(days + 1)]
    with CF.ThreadPoolExecutor(16) as ex:
        dayfiles = list(ex.map(lambda d: store.get_json(f"day/{d}.json") or {}, ds))
    ms = {}
    for x in dayfiles:
        for m in x.get("matches") or []:
            if m.get("status") in M.DONE:
                ms[m["id"]] = m
    with CF.ThreadPoolExecutor(32) as ex:
        files = dict(zip(ms, ex.map(lambda i: store.get_json(f"match/{i}.json"), ms)))
    out = []
    for i, m in ms.items():
        md = files.get(i)
        if not md:
            continue
        d = M.slim(md)
        d["_fetched"], d["_fstatus"] = M.iso(t), md.get("status") or m.get("status")
        d["status"], d["score"] = m.get("status"), m.get("score") or d.get("score")
        out.append(d)
    return out


# ------------------------------------------------------------------------------------------------ YouTube
def ytdlp_tab(chid, tab, limit):
    url = f"https://www.youtube.com/channel/{chid}/{tab}"
    r = subprocess.run(["yt-dlp", "--flat-playlist", "--playlist-end", str(limit), "-J", "--no-warnings",
                        "--extractor-args", "youtubetab:approximate_date", url], capture_output=True, timeout=1200)
    try:
        d = json.loads(r.stdout.decode("utf-8", "replace") or "{}")
    except ValueError:
        d = {}
    items = [{"id": e["id"], "title": e.get("title") or "", "ts": e.get("timestamp")} for e in d.get("entries") or [] if e.get("id")]
    err = None if d else (r.stderr.decode("utf-8", "replace").strip().splitlines() or ["no output"])[-1][:200]
    return items, err


def listing(ch, t0, relist=False):
    """{tab: [{id, title, ts}]} for one channel back to t0, cached LIST_TTL_H hours. A tab is listed 200 deep, then 3 times
    deeper while its last upload is still after t0 (the videos tab's date is yt-dlp's «3 weeks ago», a short's comes from its
    page). A tab the channel does not have is an empty list."""
    p = os.path.join(CACHE, f"list-{ch['key']}.json")
    c = jload(p, {})
    if not relist and c.get("at") and time.time() - c["at"] < LIST_TTL_H * 3600 and c.get("t0", 1e18) <= t0.timestamp():
        return c
    out = {"at": time.time(), "t0": t0.timestamp(), "errors": {}}
    for tab in ("videos", "shorts"):
        n = 200
        while True:
            items, err = ytdlp_tab(ch["id"], tab, n)
            if len(items) < n or n >= LIMIT[tab]:
                break
            last = items[-1]
            ts = last.get("ts")
            if not ts:
                at = M.ptime(page_info(last["id"]).get("at"))
                ts = at.timestamp() if at else None
            if not ts or ts < t0.timestamp():
                break
            n = min(n * 3, LIMIT[tab])
        out[tab] = items
        if err and "does not have a" not in err:
            out["errors"][tab] = err
    jsave(p, out)
    return out


def page_info(vid):
    """A video's exact upload time (UTC), its description's head and whether it embeds, from YouTube's own player endpoint
    (youtubei/v1/player: its microformat has publishDate to the second even when it will not play the video here). The
    watch page carries the same, but YouTube answered it «429» after ~400 pages on 2026-11-19 while this endpoint went on.
    {"err": ...} when it answers something else."""
    body = json.dumps({"context": {"client": {"clientName": "WEB", "clientVersion": "2.20261101.00.00", "hl": "en", "gl": "US"}},
                       "videoId": vid}).encode()
    req = urllib.request.Request("https://www.youtube.com/youtubei/v1/player?prettyPrint=false", data=body,
                                 headers={"User-Agent": BROWSER_UA, "Content-Type": "application/json"})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=25).read())
    except urllib.error.HTTPError as e:
        return {"err": e.code}
    except Exception as e:
        return {"err": type(e).__name__}
    mf = (d.get("microformat") or {}).get("playerMicroformatRenderer") or {}
    at = next((x for x in (mf.get("publishDate"), mf.get("uploadDate")) if x and "T" in x), None)
    if not at:
        return {"err": "no date"}
    ps = d.get("playabilityStatus") or {}
    return {"at": M.iso(M.ptime(at)), "desc": ((d.get("videoDetails") or {}).get("shortDescription") or "")[:300],
            **({"embed": bool(ps["playableInEmbed"])} if "playableInEmbed" in ps else {})}


def watch_page_info(vid):
    """The same from the watch page (kept for a machine whose player endpoint is refused)."""
    req = urllib.request.Request("https://www.youtube.com/watch?v=" + vid, headers={
        "User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9", "Cookie": "CONSENT=YES+1"})
    try:
        h = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return {"err": e.code}
    except Exception as e:
        return {"err": type(e).__name__}
    m = DATE.search(h)
    if not m:
        return {"err": "no date"}
    d = DESC.search(h)
    try:
        desc = json.loads('"' + d.group(1) + '"') if d else ""
    except ValueError:
        desc = ""
    pe = re.search(r'"playableInEmbed":(true|false)', h)      # what oEmbed's 200/401 says, from the same page
    return {"at": M.iso(M.ptime(m.group(1))), "desc": desc[:300], **({"embed": pe.group(1) == "true"} if pe else {})}


TODO_KEY, SHARD_KEY = "news/backfill/todo.json", "news/backfill/pages-{}.json"


def read_pages_shard(store, shard, n, log=print):
    """A runner's part (.github/workflows/tifo-media-backfill.yml): the watch pages of ids[shard::n] of the laptop's to-do list
    (YouTube answered the laptop «429 Too Many Requests» after ~400 pages on 2026-11-19, and the laptop also downloads the
    goal clips). Two at a time; a 429 waits a minute once, a second one ends the shard with what it has."""
    ids = ((store.get_state(TODO_KEY) or {}).get("ids") or [])[shard::n]
    out, limited = {}, 0

    def one(vid):
        return vid, page_info(vid)

    i = 0
    while i < len(ids):
        batch = ids[i:i + 2]
        with CF.ThreadPoolExecutor(2) as ex:
            res = list(ex.map(one, batch))
        if any(r.get("err") == 429 for _, r in res):
            limited += 1
            if limited >= 2:
                log(json.dumps({"shard": shard, "stopped": "429", "read": len(out), "of": len(ids)}))
                break
            time.sleep(60)
            continue
        for vid, r in res:
            out[vid] = r
        i += 2
        time.sleep(0.3)
    store.put_state(SHARD_KEY.format(shard), {"at": M.iso(M.now()), "pages": out})
    ok = sum(1 for r in out.values() if r.get("at"))
    log(json.dumps({"shard": shard, "read": len(out), "with_date": ok, "of": len(ids)}))
    return ok


def youtube_videos(chs, ctx, t0, relist=False, workers=6, log=print, store=None, remote=False):
    """Every upload of the channels since t0 whose title could be a clip of one of ctx's matches, as media.py's videos.
    remote: the pages are read by the runners (read_pages_shard), never here: their results are merged in, and what is still
    unread is left in S3 as their next to-do list."""
    with CF.ThreadPoolExecutor(workers) as ex:
        lists = dict(zip([c["key"] for c in chs], ex.map(lambda c: listing(c, t0, relist), chs)))
    cands = []
    for ch in chs:
        L = lists[ch["key"]]
        for tab in ("videos", "shorts"):
            for it in L.get(tab) or []:
                if it.get("ts") and it["ts"] < (t0 - timedelta(days=3)).timestamp():   # «3 weeks ago»: approximate, so a margin
                    continue
                tx = M.Text(it["title"], "", ch.get("lang", "en"))
                kind = M.classify(tx, ch)
                if not kind or (kind == "goal" and (tx.neg_goal or tx.old or tx.youth or tx.hl)):
                    continue
                teams, players = ctx.mentions(tx.al, tx.flags)
                if teams or players:
                    cands.append((ch, tab, it))
        if L.get("errors"):
            log(json.dumps({"listing_error": ch["key"], "errors": L["errors"]}, ensure_ascii=False))
    pages_p = os.path.join(CACHE, "pages.json")
    pages = jload(pages_p, {})
    if store is not None:          # what the runners read (tifo-media-backfill.yml), if they did
        for k in range(16):
            sh = store.get_state(SHARD_KEY.format(k)) or {}
            for vid, r in (sh.get("pages") or {}).items():
                if r.get("at") or "at" not in (pages.get(vid) or {}):
                    pages[vid] = r
        jsave(pages_p, pages)
    # goal clips first, then summaries; each id once
    order, seen_ids = [], set()
    for kind in ("goal", "hl"):
        for ch, tab, it in cands:
            if it["id"] in seen_ids or "at" in (pages.get(it["id"]) or {}):
                continue
            if M.classify(M.Text(it["title"], "", ch.get("lang", "en")), ch) == kind:
                order.append(it["id"]); seen_ids.add(it["id"])
    todo = order
    log(json.dumps({"listed": {k: {t: len(v.get(t) or []) for t in ("videos", "shorts")} for k, v in lists.items()}}))
    log(json.dumps({"candidates": len(cands), "pages_to_read": len(todo)}))
    if remote:
        store.put_state(TODO_KEY, {"at": M.iso(M.now()), "ids": todo})
        todo = []
    # two at a time with a pause: this machine also downloads the evening's goal clips from YouTube, so the first «429»
    # stops the reading (what is read is kept; the next run goes on from there)
    done, stop = 0, None
    for i in range(0, len(todo), 2):
        batch = todo[i:i + 2]
        with CF.ThreadPoolExecutor(2) as ex:
            res = list(ex.map(page_info, batch))
        if any(r.get("err") in (429, 403) for r in res):
            stop = next(r["err"] for r in res if r.get("err") in (429, 403))
            break
        for vid, info in zip(batch, res):
            pages[vid] = info
        done += len(batch)
        if done % 200 == 0:
            jsave(pages_p, pages)
            log(json.dumps({"pages_read": done, "of": len(todo)}))
        time.sleep(0.4)
    if stop:
        log(json.dumps({"pages_stopped": stop, "read": done, "of": len(todo)}))
    jsave(pages_p, pages)
    bad = sum(1 for _, _, it in cands if "at" not in pages.get(it["id"], {}))
    if bad:
        log(json.dumps({"pages_without_date": bad}))
    out, cut = [], M.iso(t0)
    for ch, tab, it in cands:
        p = pages.get(it["id"]) or {}
        if not p.get("at") or p["at"] < cut:
            continue
        out.append({"id": it["id"], "source": "youtube", "url": "https://www.youtube.com/watch?v=" + it["id"], "vertical": tab == "shorts",
                    "title": it["title"][:300], "desc": p.get("desc") or "", "at": p["at"], "ch": ch["key"],
                    "image": f"https://i.ytimg.com/vi/{it['id']}/hqdefault.jpg"})
    return out


# ------------------------------------------------------------------------------------------------ the run
def run(store, cfg, t=None, days=32, dry=False, explain=None, relist=False, log=print, yt=True, remote=False):
    t = t or M.now()
    t0 = t - timedelta(days=days, hours=12)
    matches = matches_of(store, t, days)
    log(json.dumps({"matches": len(matches), "goals": sum(len(M.goals_of(m)) for m in matches)}))
    names = M.load_names(store, M.national_comps())
    chs = M.channels(cfg)
    xacc = (cfg.get("x") or {}).get("accounts") or []
    chmap = {c["key"]: c for c in chs + M.x_channels(xacc)}
    blocked = set(str(x) for x in ((cfg.get("media") or {}).get("block") or []))
    ctx = M.Ctx(matches, names)
    vids = {}
    if yt:
        for v in youtube_videos(M.needed(chs, matches), ctx, t0, relist=relist, log=log, store=store, remote=remote):
            vids[v["id"]] = v
    nyt = len(vids)
    for name in ("news/x-inbox.json", "news/x-history.json"):
        for v in M.x_videos(store.get_state(name) or {}, xacc):
            if v.get("at") and v["at"] >= M.iso(t0):
                vids.setdefault(v["id"], v)
    log(json.dumps({"videos": len(vids), "youtube": nyt, "x": len(vids) - nyt}))
    trace = [] if explain is not None else None
    found = M.attach(list(vids.values()), matches, names, chmap, trace, blocked)
    M.fotmob_links(found, matches, vids, blocked)
    oe_p = os.path.join(CACHE, "oembed.json")
    oe = jload(oe_p, {})
    pages = jload(os.path.join(CACHE, "pages.json"), {})
    todo = set()
    for vid in {v["id"] for r in found.values() for v, _ in r["highlights"] + [x for l in r["goals"].values() for x in l]
                if v.get("source") == "youtube"}:
        if oe.get(vid, {}).get("s") not in (None, 0, 429):
            continue
        if "embed" in (pages.get(vid) or {}):                # the watch page said it (a runner read it)
            oe[vid] = {"s": 200 if pages[vid]["embed"] else 401, "at": M.iso(t), "from": "page"}
        else:
            todo.add(vid)
    if remote:
        todo = set()             # YouTube rate-limits this machine: an unknown one is kept and plays on the page (media.py re-checks)
    with CF.ThreadPoolExecutor(4) as ex:
        for vid, r in zip(todo, ex.map(M.oembed, todo)):
            oe[vid] = dict(r, at=M.iso(t))
    jsave(oe_p, oe)
    added_list = []
    ex_doc = store.get_state(M.EXTRA) or {}
    extra = ex_doc.get("matches") or {}
    keep_after = M.iso(t - timedelta(days=KEEP_EXTRA_D))
    stats = {"written": 0, "goal_keys_added": 0, "clips_added": 0, "highlights_added": 0, "taken_off": 0}
    by_comp = {}
    for md in matches:
        mid = md["id"]
        gs = M.goals_of(md)
        r = found.get(mid) or {"highlights": [], "goals": {}}
        hl_new = M.pack(r["highlights"], oe, chmap, hl=True)
        goals_new = {k: c for k, c in ((k, M.pack(l, oe, chmap)) for k, l in r["goals"].items()) if c}
        cur = store.get_json(f"media/{mid}.json") or {}
        end = M.match_end(md)
        # what an earlier run filed that today's vetoes turn down (M.vetoed): off the page
        cur_hl = [c for c in cur.get("highlights") or [] if not M.vetoed(c, goal=False)]
        cur_goals_all = cur.get("goals") or {}
        cur_goals = {k: [c for c in l if not M.vetoed(c)] for k, l in cur_goals_all.items()}
        stats["taken_off"] += len(cur.get("highlights") or []) - len(cur_hl) +             sum(len(l) for l in cur_goals_all.values()) - sum(len(l) for l in cur_goals.values())
        # FotMob's copy of the summary under every goal (media.fotmob_links no longer files it there): to the highlights
        uses = {}
        for k, l in cur_goals.items():
            for c in l:
                uses.setdefault(c.get("url"), set()).add(k)
        hl_urls = {c.get("url") for c in cur_hl + hl_new}
        summary = [c for l in cur_goals.values() for c in l
                   if c.get("found_by") == "fotmob" and (c.get("url") in hl_urls or len(uses[c.get("url")]) > 1)]
        sid = {c["id"] for c in summary}
        hl = M.sort_highlights(M.merge_cards(M.merge_cards(cur_hl, hl_new, blocked),
                                             [dict(c, kind=c.get("kind") or "summary") for c in summary], blocked), end)
        goals = {k: [c for c in l if c.get("id") not in sid] for k, l in cur_goals.items()}
        for k, l in goals_new.items():
            goals[k] = M.sort_goal(M.merge_cards(goals.get(k), l, blocked))
        goals = {k: l for k, l in goals.items() if l}
        doc = {"generated": M.iso(t), "match": mid, "highlights": hl, "goals": goals}
        keys = {M.goal_key(g) for g in gs}
        own_before, own_after = keys & M.own_clip_keys(cur), keys & M.own_clip_keys(doc)
        bc = by_comp.setdefault(md.get("comp"), {"goals": 0, "before": 0, "after": 0})
        bc["goals"] += len(keys)
        bc["before"] += len(own_before)
        bc["after"] += len(own_after)
        new_keys = sorted(own_after - own_before)
        byk = {M.goal_key(g): g for g in gs}
        for k in new_keys:
            g = byk.get(k) or {}
            added_list.append({"match": mid, "comp": md.get("comp"), "teams": f"{md['home'].get('name')} - {md['away'].get('name')}",
                               "goal": k, "scorer": (g.get("player") or {}).get("name"), "score": g.get("score"), "type": g.get("type"),
                               "clips": [(c.get("channel"), c.get("title"), c.get("url"), c.get("published")) for c in goals[k]]})
        same = json.dumps({"h": cur.get("highlights") or [], "g": cur_goals_all}, sort_keys=True, ensure_ascii=False) == \
            json.dumps({"h": hl, "g": goals}, sort_keys=True, ensure_ascii=False)
        if not same:
            if not dry:
                store.put_json(f"media/{mid}.json", doc, cache="hot")
            stats["written"] += 1
            stats["goal_keys_added"] += len(new_keys)
            stats["clips_added"] += sum(max(0, len(goals.get(k) or []) - len(cur_goals.get(k) or [])) for k in goals)
            stats["highlights_added"] += max(0, len(hl) - len(cur_hl))
            stats["summaries_moved"] = stats.get("summaries_moved", 0) + len(sid)
        if (md.get("kickoff_utc") or "") >= keep_after and (hl_new or goals_new):
            e = extra.setdefault(str(mid), {"kickoff_utc": md.get("kickoff_utc"), "highlights": [], "goals": {}})
            e["highlights"] = M.merge_cards(e.get("highlights"), hl_new)
            for k, l in goals_new.items():
                e["goals"][k] = M.merge_cards(e["goals"].get(k), l)
    extra = {k: v for k, v in extra.items() if (v.get("kickoff_utc") or "") >= keep_after}
    for v in extra.values():
        v["highlights"] = [c for c in v.get("highlights") or [] if not M.vetoed(c, goal=False)]
        v["goals"] = {k: l for k, l in ((k, [c for c in l if not M.vetoed(c)]) for k, l in (v.get("goals") or {}).items()) if l}
    if not dry:
        store.put_state(M.EXTRA, {"generated": M.iso(t), "matches": extra})
    if explain is not None:
        for tr in trace:
            if explain in (True, "all") or str(tr.get("match")) == str(explain):
                log(json.dumps(tr, ensure_ascii=False))
    tot = {k: sum(v[k] for v in by_comp.values()) for k in ("goals", "before", "after")}
    jsave(os.path.join(CACHE, "added.json"), added_list)          # every goal given a clip this run, to read by eye
    return dict(stats, total=tot, by_comp=by_comp)


def main(argv=None):
    import yaml
    from store import Store, S3Backend
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=32)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--relist", action="store_true", help="list the channels again even if the cached listing is fresh")
    ap.add_argument("--no-youtube", action="store_true", help="only X and FotMob (after news/xhistory.js)")
    ap.add_argument("--explain", nargs="?", const="all")
    ap.add_argument("--remote-pages", action="store_true", help="the watch pages are read by the runners (tifo-media-backfill.yml)")
    ap.add_argument("--read-pages", help="I/N: a runner reads its share of the to-do list's pages, and nothing else")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    store = Store(S3Backend(os.environ.get("BUCKET", "elyoxe-football-574771023173-ap-south-1")))
    if a.read_pages:
        i, n = (int(x) for x in a.read_pages.split("/"))
        read_pages_shard(store, i, n)
        return 0
    cfg = yaml.safe_load(open(os.path.join(HERE, "sources.yaml"), encoding="utf-8"))
    res = run(store, cfg, days=a.days, dry=a.dry, explain=a.explain, relist=a.relist, yt=not a.no_youtube, remote=a.remote_pages)
    print(json.dumps({k: v for k, v in res.items() if k != "by_comp"}, ensure_ascii=False))
    import config
    names = {c["id"]: c.get("name_en") for c in config.competitions()}
    for comp, v in sorted(res["by_comp"].items(), key=lambda x: -x[1]["goals"]):
        print(f"{comp:>6} {names.get(comp, '')[:34]:34} goals {v['goals']:4}  with a clip {v['before']:4} -> {v['after']:4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
