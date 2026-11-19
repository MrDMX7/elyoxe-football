"""Coaches by FotMob's own ids (spec phase 5): each club's coachHistory (FotMob team pages, db/.cache/fm/t/: coach, season,
league, W/D/L) puts its coach on the bench of that club's league matches of that season: one coach takes them all; several
take them in their listed order, each his own count of games (only when the counts add up to the matches we hold). A
Transfermarkt manager (a name) on the same bench joins that FotMob coach when the surnames agree. The same files' trophyList
gives the club's titles and runner-up places in each league, as honours (the first source of an honour keeps it)."""
import os, re, unicodedata
from collections import Counter, defaultdict
from graph.fm import norm_season
from graph.link import edition_for


def fold(s):
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()).strip()


def load(G, reg, S):
    base = os.path.join(S.db, "fm", "t")
    if not os.path.isdir(base):
        return {"skipped": "no FotMob team cache"}
    n = {"teams": 0, "coaches": 0, "matches_assigned": 0, "ambiguous_seasons": 0, "tm_linked": 0, "titles": 0, "conflicts": 0}
    pairs, written = Counter(), set()
    for f in sorted(os.listdir(base), key=lambda x: int(x.split(".")[0]) if x.split(".")[0].isdigit() else 0):
        if not f.split(".")[0].isdigit():
            continue
        d = S.read(os.path.join(base, f)) or {}
        hist, ov = d.get("history") or {}, d.get("overview") or {}
        ch = hist.get("coachHistory") or ov.get("coachHistory") or []
        trophies = hist.get("trophyList") or []
        if not ch and not trophies:
            continue
        n["teams"] += 1
        fid = int(f.split(".")[0])
        tid = reg.mint("team", "fotmob", fid)
        groups = defaultdict(list)
        for c in ch:
            if not isinstance(c, dict) or not c.get("id"):
                continue
            kid = reg.mint("coach", "fotmob", c["id"])
            if kid not in written:
                written.add(kid)
                G.put("coach", {"kid": kid, "name": c.get("name")}, "fotmob")
                G.xref("coach", kid, "fotmob", c["id"], "fotmob-native")
                n["coaches"] += 1
            games = sum(int(c.get(k) or 0) for k in ("win", "draw", "loss"))
            groups[(c.get("leagueId"), norm_season(c.get("season")))].append((kid, games))
        for (lid, season), lst in groups.items():
            cid = reg.get("competition", "fotmob", lid) if lid else None
            e = G.c.execute("SELECT eid FROM edition WHERE cid=? AND season=?", (cid, season)).fetchone() if cid else None
            if not e:
                continue
            ms = G.c.execute("SELECT mid, home FROM match WHERE eid=? AND (home=? OR away=?) AND hs IS NOT NULL ORDER BY date", (e[0], tid, tid)).fetchall()
            if len(lst) == 1:
                plan = [lst[0][0]] * len(ms)
            elif sum(g for _, g in lst) == len(ms):
                plan = [kid for kid, g in lst for _ in range(g)]
            else:
                n["ambiguous_seasons"] += 1
                continue
            for (mid, home), kid in zip(ms, plan):
                side = "h" if home == tid else "a"
                cur = G.c.execute("SELECT kid FROM match_coach WHERE mid=? AND side=?", (mid, side)).fetchone()
                if cur and cur[0] != kid:
                    pairs[(cur[0], kid)] += 1
                G.c.execute("INSERT OR REPLACE INTO match_coach VALUES(?,?,?,?)", (mid, side, kid, "fotmob"))
                n["matches_assigned"] += 1
        for t in trophies:
            try:
                lid = int(t.get("leagueId"))
            except (TypeError, ValueError):
                continue
            cid = reg.mint("competition", "fotmob", lid)
            for kind, field in (("champion", "seasonsWon"), ("runner_up", "seasonsRunnerup")):
                for s in filter(None, (x.strip() for x in str(t.get(field) or "").split(","))):
                    season = norm_season(s)
                    eid = edition_for(G, reg, "fotmob-trophy", f"{lid}|{season}", cid, season)
                    cur = G.c.execute("SELECT tid, src FROM honour WHERE eid=? AND kind=?", (eid, kind)).fetchall()
                    if cur:
                        if tid not in [c[0] for c in cur]:
                            G.conflict("honour", eid, kind, str(cur[0][0]), cur[0][1], str(tid), "fotmob")
                            n["conflicts"] += 1
                        continue
                    G.c.execute("INSERT OR IGNORE INTO honour(eid, kind, rank, tid, src) VALUES(?,?,1,?, 'fotmob')", (eid, kind, tid))
                    n["titles"] += 1
    # a Transfermarkt name on a club's bench in matches no coachHistory row covers (cups, the Club World Cup): FotMob's coach of
    # that club with the same name (accents and all folded, else the same surname, and only one such coach) is the man
    club_coaches = defaultdict(set)
    for kid, tid in G.c.execute("""SELECT x.kid, CASE x.side WHEN 'h' THEN m.home ELSE m.away END FROM match_coach x JOIN match m ON m.mid=x.mid
                                   WHERE x.src='fotmob'""").fetchall():
        club_coaches[tid].add(kid)
    names = {kid: fold(nm) for kid, nm in G.c.execute("SELECT kid, name FROM coach")}
    for kid, tid, nm in G.c.execute("""SELECT DISTINCT x.kid, CASE x.side WHEN 'h' THEN m.home ELSE m.away END, c.name FROM match_coach x
                                       JOIN match m ON m.mid=x.mid JOIN coach c ON c.kid=x.kid WHERE c.src='tm'""").fetchall():
        me = fold(nm)
        hits = [k for k in club_coaches.get(tid, ()) if names.get(k) == me] or                [k for k in club_coaches.get(tid, ()) if names.get(k, "").split()[-1:] == me.split()[-1:]]
        if len(set(hits)) == 1 and reg.link("coach", "tm-name", me, hits[0]) is not None:
            n["tm_linked"] += 1
    for (old, new), k in pairs.items():                           # a Transfermarkt name on FotMob's coach's bench
        a = G.c.execute("SELECT name, src FROM coach WHERE kid=?", (old,)).fetchone()
        b = G.c.execute("SELECT name FROM coach WHERE kid=?", (new,)).fetchone()
        if a and b and a[1] == "tm" and fold(a[0]).split()[-1:] == fold(b[0]).split()[-1:]:
            if reg.link("coach", "tm-name", fold(a[0]), new) is not None:
                n["tm_linked"] += 1
    return n
