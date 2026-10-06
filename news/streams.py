"""«شوفها مباشر ببلاش» (owner 2026-10-06: «هل في مكان داخل صفحة المباراة نفسها يخلي المتابع يجوفها لايف في حال كانت منقولة
على منصة مجانية مثل يوتيوب…»): the free live streams of our matches on the official YouTube channels of news/sources.yaml (the
rights holders, leagues, federations and clubs), never anyone else's: no re-streams, no watch-alongs.

  python -m news.streams [--local DIR] [--dry] [--explain]      # also a step of news.run, and the runner's `streams` job

For every match live or kicking off within the next 75 minutes, the channels worth reading (media.needed: the broadcasters, the
competition's, the two teams') are read on their Live tab. A stream counts when YouTube marks it live now, its title names both
teams (media's name matching: Arabic and Latin forms, clitics, «🇸🇦 🆚 🇦🇪») and nothing in it makes it something else (a
studio, a preview, a press conference, highlights, a replay, women's or youth football). Its oEmbed says whether it plays on
the page (200) or opens on YouTube (401); a gone one (404) is left out. On 2026-10-06 the Gulf Cup final was live on أبوظبي
الرياضية (with its commentator in the title) and on both Saudi sports channels.

Published (public, v1/):
  streams.json   {generated, matches: {"<matchId>": [{id, url, title, channel, lang, embed, watching, cc}]}}
                 cc: the channel's country (sources.yaml `country:`), so the page puts the viewer's own channel first (a
                 national channel often blocks its stream abroad)
State (private): state/news/streams.json — what the last run published and why."""
import argparse, concurrent.futures as CF, hashlib, json, os, re, sys, time
from datetime import timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from news import readers as RD
from news import media as M

STATE = "news/streams.json"
AHEAD_MIN = 75            # a channel opens its stream before kickoff (the studio, then the match)
BEHIND_H = 3.5            # a match is followed this long after kickoff (extra time, penalties)
OFF = {"postponed", "cancelled", "canceled", "abandoned", "suspended"}   # a finished match stays: its stream goes on to the cup and the
                                                                          # interviews, and it is listed while the channel is still live
# media's never-a-highlights words, less the ones a match stream is made of («مباشر», «live», «full match»), plus replays
LIVE_OK = set(M.phrases(["live", "livestream", "live stream", "watch live", "en vivo", "en directo", "en direct", "in diretta",
                         "diretta", "مباشر", "بث مباشر", "البث المباشر", "full match", "full game", "المباراة كاملة",
                         "partido completo", "match complet", "partita completa", "jogo completo", "ganzes spiel"]))
NEG = [p for p in M.NEG_ALWAYS if p not in LIVE_OK] + M.phrases(["replay", "re-live", "إعادة", "اعادة", "مسجل", "مسجلة"])


def window(store, t):
    """The matches a stream may be on now: live, kicking off within AHEAD_MIN, or kicked off in the last BEHIND_H (the UAE
    dates of yesterday and today)."""
    out = {}
    for d in (0, 1):
        day = (t + timedelta(hours=4) - timedelta(days=d)).strftime("%Y%m%d")
        try:
            doc = store.get_json(f"day/{day}.json") or {}
        except Exception:
            doc = {}
        for m in doc.get("matches") or []:
            k = M.ptime(m.get("kickoff_utc"))
            if not k or m.get("status") in OFF:
                continue
            if m.get("status") in M.LIVE or (t - timedelta(hours=BEHIND_H) <= k <= t + timedelta(minutes=AHEAD_MIN)):
                out[m["id"]] = m
    return list(out.values())


def live_now(cid):
    """A channel's Live tab -> [(video id, title, watching)] of the streams YouTube marks live right now."""
    out = []
    for lv in RD._all(RD._yt_data(RD._yt_html(cid, "streams")), "lockupViewModel", []):
        s = json.dumps(lv, ensure_ascii=False)
        if "THUMBNAIL_OVERLAY_BADGE_STYLE_LIVE" not in s:
            continue
        md = (lv.get("metadata") or {}).get("lockupMetadataViewModel") or {}
        title = ((md.get("title") or {}).get("content") or "").strip()
        w = re.search(r'"content":\s*"([\d.,]+[KM]?) watching"', s)
        if lv.get("contentId") and title:
            out.append((lv["contentId"], title, w.group(1) if w else None))
    return out


def match_of(title, ch, ctx):
    """The one match a live title is about, or (None, why)."""
    tx = M.Text(title, "", ch.get("lang", "en"))
    bad = next((" ".join(p) for p in NEG if M.has(tx.al, p)), None)
    if bad or tx.hl or tx.women or tx.youth:
        return None, "not the match: " + (bad or ("highlights" if tx.hl else tx.women or tx.youth))
    teams, _ = ctx.mentions(tx.al, tx.flags)
    hits = [mid for mid, md in ctx.matches.items()
            if (md["home"]["id"] in teams or ch.get("team") == md["home"]["id"]) and (md["away"]["id"] in teams or ch.get("team") == md["away"]["id"])]
    if len(hits) != 1:
        return None, ("names both teams of " + ",".join(map(str, hits))) if hits else "no match named"
    return hits[0], None


def step(store, cfg, t=None, dry=False, explain=False, log=print):
    t0 = time.time()
    t = t or M.now()
    st = store.get_state(STATE) or {}
    matches = window(store, t)
    found, trace, errs = {}, [], {}
    want = M.needed(M.channels(cfg), matches) if matches else []
    cc = {y["key"]: y["country"] for y in (cfg.get("youtube") or []) + ((cfg.get("media") or {}).get("youtube") or []) if y.get("country")}
    if want:
        def one(ch):
            try:
                return ch, live_now(ch["id"]), None
            except Exception as e:
                return ch, [], f"{type(e).__name__}: {str(e)[:80]}"
        with CF.ThreadPoolExecutor(max_workers=6) as ex:
            got = list(ex.map(one, want))
        ctx = M.Ctx(matches, M.load_names(store, M.national_comps()))
        for ch, lives, err in got:
            if err:
                errs[ch["key"]] = err
            for vid, title, watching in lives:
                mid, why = match_of(title, ch, ctx)
                trace.append({"ch": ch["key"], "video": vid, "title": title, "match": mid, "why": why})
                if mid:
                    found.setdefault(mid, []).append({"id": vid, "url": "https://www.youtube.com/watch?v=" + vid, "title": title[:200],
                                                      "channel": ch["name"], "lang": ch.get("lang"), "watching": watching, "ch": ch["key"],
                                                      **({"cc": cc[ch["key"]]} if ch["key"] in cc else {})})
    # plays on the page (200) or opens on YouTube (401); gone or private (400/403/404) is left out; unknown (0) is tried
    oe = st.setdefault("oembed", {})
    for lst in found.values():
        for s in lst:
            if s["id"] not in oe and not dry:
                oe[s["id"]] = dict(M.oembed(s["id"]), at=M.iso(t))
    for k in [k for k, v in oe.items() if (v.get("at") or "") < M.iso(t - timedelta(days=2))]:
        del oe[k]
    out = {}
    for mid, lst in found.items():
        keep, seen = [], set()
        for s in lst:
            o = oe.get(s["id"], {})
            if s["id"] in seen or o.get("s") in (400, 403, 404):
                continue
            seen.add(s["id"])
            keep.append(dict(s, embed=o.get("s") != 401))
        # one that plays on the page first, then Arabic, then the most watched
        num = lambda w: float((w or "0").replace(",", "").rstrip("KM")) * (1e6 if (w or "").endswith("M") else 1e3 if (w or "").endswith("K") else 1)
        keep.sort(key=lambda s: (0 if s["embed"] else 1, 0 if s.get("lang") == "ar" else 1, -num(s.get("watching"))))
        if keep:
            out[str(mid)] = keep
    doc = {"generated": M.iso(t), "matches": out}
    h = hashlib.md5(json.dumps(out, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    written = False
    # rewritten when what it holds changed, and at least every 10 minutes while a stream is on (the page reads `generated`)
    if not dry and (st.get("hash") != h or (out and (M.ptime(st.get("at")) or t) < t - timedelta(minutes=10))):
        store.put_json("streams.json", doc, cache="hot")
        st["hash"], st["at"], written = h, M.iso(t), True
    st["run"] = {"at": M.iso(t), "matches": len(matches), "channels": len(want), "streams": sum(len(v) for v in out.values()),
                 "written": written, "errors": errs, "secs": round(time.time() - t0, 1)}
    if not dry:
        store.put_state(STATE, st)
    if explain:
        for tr in trace:
            log(json.dumps(tr, ensure_ascii=False))
    return dict(st["run"], found={k: [s["channel"] for s in v] for k, v in out.items()})


def main(argv=None):
    import yaml
    from store import Store, S3Backend, LocalBackend
    ap = argparse.ArgumentParser()
    ap.add_argument("--local"); ap.add_argument("--dry", action="store_true"); ap.add_argument("--explain", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    bucket = os.environ.get("BUCKET", "elyoxe-football-574771023173-ap-south-1")
    store = Store(LocalBackend(a.local)) if a.local else Store(S3Backend(bucket))
    cfg = yaml.safe_load(open(os.path.join(HERE, "sources.yaml"), encoding="utf-8"))
    print(json.dumps(step(store, cfg, dry=a.dry, explain=a.explain), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
