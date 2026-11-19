"""SofaScore's player of the match (owner 2026-11-20: «all of them», his explicit permission) for the matches FotMob has no
ratings for: graph/sofa.py keeps, per SofaScore league season, each finished match with its «player of the match» and his
rating (graph/.cache/sofa/<tournament>_<season>.json, S3 state/graph/sofa/cache.tar.gz). A SofaScore club is linked to ours
by date+score votes; a match by its twin; the player to one of our players in that match's lineup by his name (full name,
else a unique surname), else he is a player of SofaScore's own. A match with FotMob ratings keeps FotMob's pick."""
import io, json, os, re, tarfile, unicodedata
from graph.link import MatchIndex, twin, vote_teams

STATE_KEY = "state/graph/sofa/cache.tar.gz"


def fold(s):
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()).strip()


def restore(S, d):
    try:
        st = S.store()
        raw = st.b.s3.get_object(Bucket=st.b.bucket, Key=STATE_KEY)["Body"].read()
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
            tf.extractall(os.path.dirname(d), filter="data")
    except Exception as e:
        print(f"no sofascore cache in S3 ({type(e).__name__})", flush=True)


def load(G, reg, S):
    d = os.path.join(S.root, "graph", ".cache", "sofa")
    if not os.path.isdir(d) and S.s3:
        restore(S, d)
    if not os.path.isdir(d):
        return {"skipped": "no sofascore cache"}
    events = []
    for f in sorted(os.listdir(d)):
        if f.endswith(".json"):
            try:
                events += json.load(open(os.path.join(d, f), encoding="utf-8")).get("events") or []
            except ValueError:
                continue
    games = [(e["ts"][:10], str(e["home"][0]), str(e["away"][0]), e.get("hs"), e.get("as")) for e in events if e.get("hs") is not None]
    for k, tid in vote_teams(G, reg, "sofa", games).items():
        G.xref("team", tid, "sofa", k, "date+score-votes")
    idx = MatchIndex(G)
    rated = {mid for (mid,) in G.c.execute("SELECT DISTINCT mid FROM appearance WHERE rating IS NOT NULL")}
    n = {"events": len(events), "matched": 0, "picks": 0, "players_linked": 0, "players_new": 0}
    for e in events:
        p = e.get("potm") or {}
        h, a = reg.get("team", "sofa", str(e["home"][0])), reg.get("team", "sofa", str(e["away"][0]))
        if not (p.get("name") and h and a):
            continue
        mid = twin(G, idx, e["ts"][:10], h, a, e.get("hs"), e.get("as"), "sofa")
        if not mid:
            continue
        n["matched"] += 1
        reg.link("match", "sofa", str(e["id"]), mid)
        G.xref("match", mid, "sofa", e["id"], "date+teams")
        if mid in rated:
            continue
        want, last = fold(p["name"]), fold(p["name"]).split(" ")[-1:]
        lineup = G.c.execute("SELECT a.pid, a.tid, p.name FROM appearance a JOIN player p ON p.pid=a.pid WHERE a.mid=?", (mid,)).fetchall()
        hit = [r for r in lineup if fold(r[2]) == want] or [r for r in lineup if fold(r[2]).split(" ")[-1:] == last]
        if len(hit) == 1:
            pid, tid = hit[0][0], hit[0][1]
            reg.link("player", "sofa", str(p["id"]), pid)
            n["players_linked"] += 1
        else:
            pid = reg.get("player", "sofa", str(p["id"])) or reg.mint("player", "sofa", str(p["id"]))
            G.put("player", {"pid": pid, "name": p["name"]}, "sofa")
            tid = None
            n["players_new"] += 1
        if G.c.execute("INSERT OR IGNORE INTO match_award(mid, kind, pid, tid, value, src) VALUES(?, 'motm', ?, ?, ?, 'sofascore')",
                       (mid, pid, tid, str(p.get("value") or ""))).rowcount:
            n["picks"] += 1
    return n
