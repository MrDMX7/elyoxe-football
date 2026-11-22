"""RSSSF's Arab league seasons before the other sources start (db/rsssf.py publishes v1/history/arab/<code>.json: every
season's final table, its champion and the FotMob id of each club it could link): the tables as standings of the
country's FotMob league, the champion as an honour, the league round by round with its scorers (league_matches: linked to the source that has
the match, its scorers added when it has none), and the dated cup games of db/.cache/rsssf_clubs.json as matches. A
season whose table the graph already has (365Scores) keeps it; a club RSSSF could not link is a team of its own
(`rsssf-name`, «<code>|<name>»)."""
import os
from graph.link import MatchIndex, twin



def _label(G, tid, name=None):
    """a club's name as the disagreements list folds it («Espérance de Tunis» -> «esperance de tunis»): ours, else the table's"""
    import re, unicodedata
    r = G.c.execute("SELECT name FROM team WHERE tid=?", (tid,)).fetchone()
    t = (r[0] if r else None) or name or ""
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()).strip()

def load(G, reg, S, codes=None):
    if codes is None:
        try:
            from db.rsssf import COUNTRIES
            codes = sorted(COUNTRIES)
        except Exception as e:
            print(f"db.rsssf not importable: {e}", flush=True)
            codes = []
    n = {"seasons": 0, "standings": 0, "champions": 0, "champion_conflicts": 0, "matches": 0, "matches_linked": 0, "league_matches": 0, "league_linked": 0, "league_bad": 0, "goals": 0}
    written, idx = set(), MatchIndex(G)
    mine = {}            # the matches RSSSF's own league rows claimed in this build: {mid: (hs, as_) as the row gave it}

    def fresh(key, mid):
        """the row's registry key, or «key#2», «key#3»… when the key already names a match another RSSSF row of this build
        claimed: two meetings one key (or an older build's collapse of A v B and B v A) get an id each"""
        k, i = key, 1
        while (cur := reg.get("match", "rsssf", k)) is not None and cur != mid and cur in mine:
            i += 1
            k = f"{key}#{i}"
        return k

    def scorer(code, name):
        k = f"{code}|{name}"
        pid = reg.get("player", "rsssf-name", k) or reg.mint("player", "rsssf-name", k)
        if ("p", pid) not in written:
            written.add(("p", pid))
            G.put("player", {"pid": pid, "name": name}, "rsssf")
            G.xref("player", pid, "rsssf-name", k, "rsssf-native")
        return pid

    def league_match(code, eid, d, hn, hid, an, aid, hs, as_, goals):
        """one league match of RSSSF's rounds: linked to the source that has it (FotMob, 365Scores) or added; its scorers as
        goals and appearances, unless the match has its own events already"""
        h, a = team(code, hn, hid), team(code, an, aid)
        if h == a:
            return
        mid = twin(G, idx, d, h, a, hs, as_, "rsssf", mine)
        key = fresh(f"{code}|{d}|{hn}|{an}", mid)
        if mid:
            mid = reg.link("match", "rsssf", key, mid) or mid
            G.xref("match", mid, "rsssf", key, "date+teams")
            n["league_linked"] += 1
            flip = G.c.execute("SELECT home FROM match WHERE mid=?", (mid,)).fetchone()[0] == a
            mine.setdefault(mid, (as_, hs) if flip else (hs, as_))
            if G.c.execute("SELECT 1 FROM event WHERE mid=? LIMIT 1", (mid,)).fetchone():
                return                                   # the match's own scorers stand
        else:
            mid = reg.mint("match", "rsssf", key)
            mine[mid] = (hs, as_)
            idx.add(mid, d, h, a)
            G.put("match", {"mid": mid, "eid": eid, "date": d, "home": h, "away": a, "hs": hs, "as_": as_, "status": "finished"}, "rsssf")
            G.xref("match", mid, "rsssf", key, "rsssf-native")
            n["league_matches"] += 1
            flip = False
        side_t = {"h": a if flip else h, "a": h if flip else a}
        other = {"h": "a", "a": "h"}
        events, apps = [], {}
        for seq, (side, name, minute, kind) in enumerate(sorted(goals, key=lambda g: (g[2] if g[2] is not None else 999))):
            pid = scorer(code, name)
            sd = other[side] if flip else side                 # the side as the match row has it
            events.append({"mid": mid, "seq": seq, "minute": minute, "added": 0, "type": kind, "side": sd, "tid": side_t[side], "pid": pid})
            own_team = side_t[other[side]] if kind == "own_goal" else side_t[side]
            ap = apps.setdefault(pid, {"mid": mid, "pid": pid, "tid": own_team, "played": 1, "goals": 0})
            ap["goals"] += kind != "own_goal"
        G.many("event", events, "rsssf")
        G.many("appearance", list(apps.values()), "rsssf")
        n["goals"] += len(events)

    def team(code, name, fid):
        if fid:
            return reg.mint("team", "fotmob", int(fid))
        k = f"{code}|{name}"
        tid = reg.get("team", "rsssf-name", k) or reg.mint("team", "rsssf-name", k)
        if tid not in written:                         # once a build, minted now or in an earlier build
            written.add(tid)
            G.put("team", {"tid": tid, "name": name, "kind": "club"}, "rsssf")
            G.xref("team", tid, "rsssf-name", k, "rsssf-native")
        return tid

    for code in codes:
        d = S.published(f"history/arab/{code}.json")
        if not d:
            continue
        lid = d.get("league")
        if lid:
            cid = reg.mint("competition", "fotmob", int(lid))
            G.put("competition", {"cid": cid, "name": f"FotMob {lid}"}, "fotmob")
        else:
            cid = reg.get("competition", "rsssf", code) or reg.mint("competition", "rsssf", code)
            G.put("competition", {"cid": cid, "name": f"{code} top league (RSSSF)", "kind": "league"}, "rsssf")
            G.xref("competition", cid, "rsssf", code, "rsssf-native")
        own = [r[0] for r in G.c.execute("SELECT e.season FROM edition e WHERE e.cid=? AND EXISTS(SELECT 1 FROM match m WHERE m.eid=e.eid)", (cid,))]
        is_split = bool(own) and sum("/" in x for x in own) >= 0.8 * len(own)
        for s in d.get("seasons") or []:
            season = s.get("season")
            if not season:
                continue
            days = [m[0] for m in s.get("league_matches") or [] if m and m[0]]
            if is_split and season.isdigit() and season not in own and all(x < f"{season}-07-01" for x in days):
                season = f"{int(season) - 1}/{season}"      # Kuwait «2001» (March to June 2001) is 2000/2001
            hit = G.c.execute("SELECT eid FROM edition WHERE cid=? AND season=?", (cid, season)).fetchone()
            if hit:
                eid = hit[0]
            else:
                eid = reg.get("edition", "rsssf", f"{code}|{season}") or reg.mint("edition", "rsssf", f"{code}|{season}")
                G.put("edition", {"eid": eid, "cid": cid, "season": season}, "rsssf")
                G.xref("edition", eid, "rsssf", f"{code}|{season}", "rsssf-native")
            n["seasons"] += 1
            table = s.get("table") or []
            if table and not G.c.execute("SELECT 1 FROM standing WHERE eid=?", (eid,)).fetchone():
                for pos, name, fid, p, w, dr, l, gf, ga, pts in table:
                    G.c.execute("INSERT OR IGNORE INTO standing VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                (eid, "", pos, team(code, name, fid), p, w, dr, l, gf, ga, pts, "rsssf"))
                    n["standings"] += 1
            for d, hn, hid, an, aid, hs, as_, goals in s.get("league_matches") or []:
                try:
                    league_match(code, eid, d, hn, hid, an, aid, hs, as_, goals)
                except (ValueError, TypeError) as e:      # one bad row (a date that does not exist) never stops the loader
                    n["league_bad"] += 1
                    if n["league_bad"] <= 5:
                        print(f"rsssf {code} {season} {d} {hn}-{an}: {e}", flush=True)
            if table and table[0][0] == 1:     # db/rsssf.py keeps a table only when its first club is the champions page's
                tid = team(code, table[0][1], table[0][2])
                cur = G.c.execute("SELECT tid, src FROM honour WHERE eid=? AND kind='champion' AND rank=1", (eid,)).fetchall()
                if cur:                        # the first source keeps the title; another club is a disagreement, never a second champion
                    if tid not in [c[0] for c in cur]:
                        G.conflict("honour", eid, "champion", _label(G, cur[0][0]), cur[0][1], _label(G, tid, table[0][1]), "rsssf")
                        n["champion_conflicts"] += 1
                elif G.c.execute("INSERT OR IGNORE INTO honour(eid, kind, rank, tid, src) VALUES(?,?,?,?,?)",
                                 (eid, "champion", 1, tid, "rsssf")).rowcount:
                    n["champions"] += 1
    clubs = S.read(os.path.join(S.db, "rsssf_clubs.json")) or {}
    for fid in sorted(clubs, key=lambda x: int(x) if x.isdigit() else 0):
        if not fid.isdigit():
            continue
        me = reg.mint("team", "fotmob", int(fid))
        for d, opp, home, gf, ga, comp in clubs[fid].get("matches") or []:
            if not isinstance(opp, int):
                continue
            other = reg.mint("team", "fotmob", opp)
            h, a, hs, as_ = (me, other, gf, ga) if home else (other, me, ga, gf)
            mid = twin(G, idx, d, h, a, hs, as_, "rsssf")
            key = f"{d}|{min(int(fid), opp)}|{max(int(fid), opp)}"
            if mid:
                mid = reg.link("match", "rsssf", key, mid)
            if mid:
                G.xref("match", mid, "rsssf", key, "date+teams")
                n["matches_linked"] += 1
                continue
            ck = comp.split(":", 1)[1] if ":" in comp else comp
            cid = reg.get("competition", "rsssf", ck) or reg.mint("competition", "rsssf", ck)
            G.put("competition", {"cid": cid, "name": ck, "kind": "cup" if ck.endswith("cup") else None}, "rsssf")
            y, mo = int(d[:4]), int(d[5:7])
            season = f"{y}/{y + 1}" if mo >= 7 else f"{y - 1}/{y}"
            eid = reg.get("edition", "rsssf", f"{ck}|{season}") or reg.mint("edition", "rsssf", f"{ck}|{season}")
            G.put("edition", {"eid": eid, "cid": cid, "season": season}, "rsssf")
            mid = reg.mint("match", "rsssf", key)
            G.put("match", {"mid": mid, "eid": eid, "date": d, "home": h, "away": a, "hs": hs, "as_": as_, "status": "finished"}, "rsssf")
            G.xref("match", mid, "rsssf", key, "rsssf-native")
            idx.add(mid, d, h, a)
            n["matches"] += 1
    return n
