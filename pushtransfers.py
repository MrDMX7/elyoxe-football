"""«انتقالات النادي» (owner 2026-10-10, item 12): a new move in the season's ledger (v1/transfers/all.json, db/transfers_world.py)
reaches the subscribers of both clubs who switched «انتقالات النادي» on (push kind "transfer"; the sender, push.run_jobs,
claims it once per move and keeps quiet hours). Runs with the journal (every 15 min, laptop); sends only in the UAE day
(09:00-23:00), so a ledger refreshed at 04:30 waits for the morning. The first run only learns what is there already.
State: state/push_transfers.json {"seen": [move keys]}.
  python -m pushtransfers"""
import gzip, json, os, time, urllib.request
from datetime import date, timedelta

DATA = os.environ.get("TIFO_DATA", "https://d1n5aqaqkowltp.cloudfront.net")
BUCKET = os.environ.get("BUCKET", "elyoxe-football-574771023173-ap-south-1")
RECENT_DAYS = 3               # an older move is news, not an alert (a club the ledger reached late)
DAY = (9, 23)                 # UAE hours the alerts go out
NO_CLUB = {None, 0, 2}        # FotMob's «Free agent» is team 2


def move_key(m):
    return f"{m[1]}:{m[3]}:{m[5]}:{m[0]}"


def new_moves(moves, seen, today, site):
    since = (date.fromisoformat(today) - timedelta(days=RECENT_DAYS)).isoformat()
    return [m for m in moves or [] if m[0] >= since and move_key(m) not in seen and (m[3] in site or m[5] in site)]


def daytime(now=None):
    h = time.gmtime((now if now is not None else time.time()) + 4 * 3600).tm_hour
    return DAY[0] <= h < DAY[1]


def _eur(v):
    return f"€{round(v / 1e6, 1):g} مليون" if v >= 1e6 else f"€{round(v / 1e3):g} ألف"


def job(m, names=None, came_true=False):
    names = names or {}
    nm = lambda i, fb: names.get(str(i)) or fb
    player, fr, to = nm(m[1], m[2]), nm(m[3], m[4]), nm(m[5], m[6])
    what = _eur(m[7]) if m[8] == "fee" and m[7] else {"loan": "إعارة", "free": "انتقال حر", "undisclosed": "مبلغ ما انعلن"}.get(m[8], "")
    tail = "".join(x for x in [f" · {what}" if what else "", " · الإشاعة صدقت" if came_true else ""])
    to_ar = ("لل" + to[2:]) if to.startswith("ال") else "ل" + to      # «للهلال», «لأرسنال»: plain text, no tatweel
    base = {"url": f"/p/{m[1]}/", "tag": f"tr-{m[1]}"}
    pay = {}
    if m[5] not in NO_CLUB:
        pay[str(m[5])] = {**base, "team": m[5], "title": f"صفقة {to}: {player}", "body": ("لاعب حر" if m[3] in NO_CLUB else f"من {fr}") + tail}
    if m[3] not in NO_CLUB:
        pay[str(m[3])] = {**base, "team": m[3], "title": f"طلع من {fr}: {player}", "body": ("صار بدون نادي" if m[5] in NO_CLUB else to_ar) + tail}
    return {"match": f"tr-{m[1]}", "key": f"tr:{m[3]}-{m[5]}:{m[0]}", "kind": "transfer", "urgency": "normal", "payloads": pay,
            "exp": int(time.time()) + 6 * 3600}


def _get(path):
    try:
        with urllib.request.urlopen(f"{DATA}/{path}", timeout=30) as r:
            raw = r.read()
        return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    except Exception:
        return None


def main():
    from store import Store, S3Backend
    import push
    store = Store(S3Backend(BUCKET))
    L = (_get("transfers/all.json") or {}).get("moves") or []
    st = store.get_state("push_transfers.json", None)
    if st is None:                                   # the first run learns the ledger: no alert for what happened before
        store.put_state("push_transfers.json", {"seen": [move_key(m) for m in L]})
        print(json.dumps({"seeded": len(L)})); return
    if not daytime():
        print(json.dumps({"waiting": "night"})); return
    seen = set(st.get("seen") or [])
    site = {int(k) for k in ((_get("teams.json") or {}).get("teams") or {})}
    new = new_moves(L, seen, time.strftime("%Y-%m-%d", time.gmtime(time.time() + 4 * 3600)), site)
    if new:
        done = {r["pid"] for r in ((_get("transfers/rumours.json") or {}).get("rumours") or []) if r.get("out") == "done"}
        jobs = [job(m, came_true=m[1] in done) for m in new]     # the ledger's names are FotMob's Arabic ones already
        for i in range(0, len(jobs), 50):
            push.invoke(jobs[i:i + 50])
    st["seen"] = sorted(seen | {move_key(m) for m in L})[-50000:]
    store.put_state("push_transfers.json", st)
    print(json.dumps({"new": len(new), "seen": len(st["seen"])}))


if __name__ == "__main__":
    main()
