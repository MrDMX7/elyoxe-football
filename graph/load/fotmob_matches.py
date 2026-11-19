"""Every finished match in FotMob detail (db/.cache/fm/mx/, 92k since 2010/11) with its competition, edition, teams,
players, referee and stadium. FotMob ids are minted first and in id order, so the first registry is deterministic."""
import os
from graph import fm
from graph.rows import match_rows

ENT = ("team", "player", "referee", "stadium", "match")


def load(G, reg, S, limit=None):
    base = os.path.join(S.db, "fm", "mx")
    files = sorted((f for f in os.listdir(base) if f.split(".")[0].isdigit()), key=lambda f: int(f.split(".")[0])) if os.path.isdir(base) else []
    if limit:
        files = files[:limit]
    labels, calendar = fm.season_map(S)
    comps, done_c, done_e = fm.comp_info(S), set(), set()
    n = skipped = 0
    for f in files:
        rec = S.read(os.path.join(base, f))
        if not rec or not rec.get("home") or not rec.get("away") or not rec.get("date") or rec["home"][0] is None:
            skipped += 1
            continue
        c = rec.get("comp")
        cid = reg.mint("competition", "fotmob", c)
        if cid not in done_c:
            done_c.add(cid)
            info = comps.get(int(c)) if c is not None else None
            G.put("competition", {"cid": cid, **(info or {"name": f"FotMob {c}"})}, "fotmob")
            G.xref("competition", cid, "fotmob", c, "fotmob-native")
        season = fm.season_of(rec["id"], rec["date"], c, labels, calendar)
        eid = reg.mint("edition", "fotmob", f"{c}|{season}")
        if eid not in done_e:
            done_e.add(eid)
            G.put("edition", {"eid": eid, "cid": cid, "season": season}, "fotmob")
            G.xref("edition", eid, "fotmob", f"{c}|{season}", "fotmob-native")
        rows = match_rows(rec, eid, reg)
        for t in ENT:
            for r in rows.get(t, ()):
                G.put(t, r, "fotmob")
        G.many("appearance", rows.get("appearance"), "fotmob")
        G.many("event", rows.get("event"), "fotmob")
        for x in rows.get("xref", ()):
            G.xref(*x)
        n += 1
        if n % 10000 == 0:
            print(f"fotmob matches: {n}", flush=True)
            G.c.commit()
    G.c.execute("""UPDATE edition SET start=(SELECT min(substr(date,1,10)) FROM match WHERE match.eid=edition.eid),
                   end=(SELECT max(substr(date,1,10)) FROM match WHERE match.eid=edition.eid)""")
    return {"matches": n, "skipped": skipped}
