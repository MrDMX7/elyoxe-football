"""«المعلقين» (item 3, owner 2026-10-06): one public index of who called which match, across days, so a commentator's page
and the «معلّقك المفضل» setting read one small file instead of a day file per day.

  python -m news.tvindex [--local DIR] [--rebuild] [--dry]     # by hand; the journal calls update() from
                                                                # news/commentators.run(), right after the day files

In:  v1/tv/<yyyymmdd>.json (news/commentators.py: Kooora's daily list of channels and commentators, tied to our fixtures),
     day/<ymd>.json and all/<ymd>.json through commentators.load_fixtures (team and competition ids, which matches have a
     page of their own).
State: state/tv/index.json  {days: {"2026-10-05": {mid: {ko, h, a, c, page, calls: [[name, channel], …]}}}}, KEEP_DAYS days.
     A day is re-read while it is today or tomorrow (the journal rewrites those files); older days are read once (backfill).
Out: v1/tv/commentators.json (public, written only when its content changes):
  {generated, since, until, days, source,
   commentators: {key: {name, slug, n, channels: [[channel, n]…], comps: [[comp id|null, name, n]…], first, last,
                        next: [[match, channel]…], recent: [[match, channel]…]}},     the famous voices (FAMOUS) only
   others: [[name, n]…],                                                           every other named voice, most calls first
   matches: {mid: {ko, h: [team id|null, name], a: […], c: [comp id|null, name], page}}}   the matches those lists name
  key: 8 hex of sha1 of the name's fold() key (stable whatever the spelling); slug: the Arabic name with hyphens.
  next: kickoff no earlier than 2 hours ago (live or to come), soonest first; recent: the rest, latest first (RECENT max).
Facts only, as the day files have them: the channel, the match, the competition, the date. No bios, nothing generated.
"""
import argparse, hashlib, json, os, re, sys, time
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from news import commentators as TV  # noqa: E402

STATE = "tv/index.json"
OUT = "tv/commentators.json"
FIRST_DAY = date(2026, 9, 30)          # the first v1/tv day file
KEEP_DAYS = 60
RECENT = 12
NEXT_GRACE = timedelta(hours=2)        # a match that kicked off less than this ago is still «today's»
OTHERS = 100
SOURCE = "جدول القنوات الناقلة والمعلقين في كووورة، مربوط بمباريات تيفو"
UTC = timezone.utc


def famous():
    """FAMOUS in its own order, once each (the list repeats a few names)."""
    return list(dict.fromkeys(TV.FAMOUS))


def canonical(name):
    """The famous spelling of a name when it is one of FAMOUS / VARIANTS, else the day file's spelling."""
    return TV._FAMOUS.get(TV._ckey(name), TV.clean(name))


def key_of(name):
    """Stable whatever the spelling: «حفيظ الدراجي» and «حفيظ دراجي» are one key."""
    return hashlib.sha1(TV._ckey(canonical(name)).encode("utf-8")).hexdigest()[:8]


def slug_of(name):
    return re.sub(r"\s+", "-", TV.clean(canonical(name))).strip("-")


def _iso(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if isinstance(t, datetime) else t


def compact(doc, fixtures):
    """One day file -> {mid: {ko, h, a, c, page, calls}} for the matches with at least one named commentator."""
    ours = {str(f["id"]): f for f in fixtures or []}
    out = {}
    for mid, es in ((doc or {}).get("matches") or {}).items():
        calls = []
        for e in es or []:
            names = e.get("commentators") or ([e["commentator"]] if e.get("commentator") else [])
            for n in names:
                ch = e.get("channel") or ""
                c = [canonical(n), "" if TV.BANNED_CH.search(ch) else ch]
                if c not in calls:
                    calls.append(c)
        if not calls:
            continue
        f = ((doc or {}).get("fixtures") or {}).get(mid) or {}
        o = ours.get(str(mid)) or {}
        team = lambda side, name: [((o.get(side) or {}).get("id")), name or ((o.get(side) or {}).get("names") or [None])[0]]   # noqa: E731
        ko = f.get("ko") or _iso(o.get("ko"))
        if not ko:
            continue
        out[str(mid)] = {"ko": ko, "h": team("home", f.get("home")), "a": team("away", f.get("away")),
                         "c": [o.get("comp"), f.get("comp") or o.get("comp_name_ar")], "page": o.get("src") == "day", "calls": calls}
    return out


def build(days, now):
    """The public document from the per-day entries."""
    per, n_other, seen_days = {}, {}, sorted(days)
    fam = {TV._ckey(n): n for n in famous()}
    for d in seen_days:
        for mid, m in days[d].items():
            for name, ch in m["calls"]:
                k = TV._ckey(name)
                if k not in fam:
                    n_other.setdefault(name, set()).add(mid)
                    continue
                p = per.setdefault(fam[k], {"matches": {}, "channels": {}, "comps": {}})
                if mid not in p["matches"]:
                    p["matches"][mid] = []
                    cid, cname = (m.get("c") or [None, None])[:2]
                    ck = (cid, cname or "")
                    p["comps"][ck] = p["comps"].get(ck, 0) + 1
                if ch and ch not in p["matches"][mid]:            # one voice on شاهد and MBC Action: one match, both channels
                    p["matches"][mid].append(ch)
                    p["channels"][ch] = p["channels"].get(ch, 0) + 1
    all_m = {mid: m for d in seen_days for mid, m in days[d].items()}
    cut = _iso(now - NEXT_GRACE)
    out, used = {}, set()
    for name in famous():
        p = per.get(name)
        if not p:
            continue
        ms = sorted(p["matches"], key=lambda mid: all_m[mid]["ko"])
        ref = lambda mid: [int(mid) if mid.isdigit() else mid, "، ".join(p["matches"][mid])]        # noqa: E731
        nxt = [ref(mid) for mid in ms if all_m[mid]["ko"] >= cut]
        rec = [ref(mid) for mid in reversed(ms) if all_m[mid]["ko"] < cut][:RECENT]
        used.update(str(x[0]) for x in nxt + rec)
        out[key_of(name)] = {"name": name, "slug": slug_of(name), "n": len(ms),
                             "channels": sorted(([c, n] for c, n in p["channels"].items() if c), key=lambda x: (-x[1], x[0])),
                             "comps": sorted(([c[0], c[1], n] for c, n in p["comps"].items()), key=lambda x: (-x[2], x[1])),
                             "first": all_m[ms[0]]["ko"][:10], "last": all_m[ms[-1]]["ko"][:10], "next": nxt, "recent": rec}
    others = sorted(([n, len(s)] for n, s in n_other.items()), key=lambda x: (-x[1], x[0]))[:OTHERS]
    matches = {mid: {k: all_m[mid][k] for k in ("ko", "h", "a", "c", "page")} for mid in sorted(used) if mid in all_m}
    return {"generated": _iso(now), "since": seen_days[0] if seen_days else None, "until": seen_days[-1] if seen_days else None,
            "days": len(seen_days), "source": SOURCE, "commentators": out, "others": others, "matches": matches}


def update(store, docs, fixtures_of, now=None, dry=False, rebuild=False, log=print):
    """docs: {date: day document} just built by news/commentators.run (today, tomorrow); fixtures_of(date) -> our fixtures.
    Missing older days are read once from v1/tv/. Writes state/tv/index.json and v1/tv/commentators.json (when it changed)."""
    now = now or datetime.now(UTC)
    st = {} if rebuild else (store.get_state(STATE) or {})
    days = st.setdefault("days", {})
    today = (now + timedelta(hours=4)).date()
    first = max(FIRST_DAY, today - timedelta(days=KEEP_DAYS))
    read = 0
    for d, doc in (docs or {}).items():
        dd = d if isinstance(d, date) else date.fromisoformat(str(d))
        if dd >= first:
            days[dd.isoformat()] = compact(doc, fixtures_of(dd))
    d = first
    while d < today:                                           # backfill: a day we never indexed (the first run, a gap)
        if d.isoformat() not in days:
            try:
                doc = store.get_json(f"tv/{d.strftime('%Y%m%d')}.json")
            except Exception:
                doc = None
            read += 1
            days[d.isoformat()] = compact(doc, fixtures_of(d)) if doc else {}
        d += timedelta(days=1)
    for k in [k for k in days if k < first.isoformat()]:
        del days[k]
    pub = build(days, now)
    if not dry:
        store.put_state(STATE, st)
        store.put_json(OUT, pub, cache="warm")
    log(json.dumps({"tvindex": {"days": len(days), "famous": len(pub["commentators"]), "others": len(pub["others"]),
                                "matches": len(pub["matches"]), "backfill_reads": read}}, ensure_ascii=False))
    return pub


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--local")
    ap.add_argument("--rebuild", action="store_true", help="forget the state and read every day file again")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from store import Store, S3Backend, LocalBackend
    store = Store(LocalBackend(a.local)) if a.local else Store(S3Backend(TV.BUCKET))
    clubs, cache = TV._clubs_ar(), {}

    def fixtures_of(d):
        if d not in cache:
            try:
                cache[d] = TV.load_fixtures(store, TV.ymd(d), clubs)
            except Exception:
                cache[d] = []
        return cache[d]
    today = (datetime.now(UTC) + timedelta(hours=4)).date()
    docs = {}
    for d in (today, today + timedelta(days=1)):
        doc = store.get_json(f"tv/{TV.ymd(d)}.json")
        if doc:
            docs[d] = doc
    pub = update(store, docs, fixtures_of, dry=a.dry, rebuild=a.rebuild)
    if a.dry:
        print(json.dumps({k: pub[k] for k in ("since", "until", "days")} | {"commentators": {k: {x: v[x] for x in ("name", "n", "next", "recent")}
                                                                                    for k, v in pub["commentators"].items()}}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
