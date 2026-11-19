"""Every men's international since 1872 (martj42/international_results). A national team links when FotMob's name maps to
the dataset's (compute/national.py's aliases); a result FotMob already has becomes its xref, the rest are new matches in
a competition per tournament name."""
import csv, os
from graph.link import MatchIndex, twin


def load(G, reg, S):
    from compute.national import dataset_name
    p = os.path.join(S.db, "martj42_results.csv")
    if not os.path.exists(p):
        return {"skipped": "no martj42_results.csv"}
    data = list(csv.DictReader(open(p, encoding="utf-8", newline="")))
    known = {r["home_team"] for r in data} | {r["away_team"] for r in data}
    tl = 0
    for tid, name in G.c.execute("SELECT tid, name FROM team WHERE kind='national' ORDER BY tid").fetchall():
        dn = dataset_name(name, known)
        if dn and reg.alias("team", "martj42", dn, tid):
            G.xref("team", tid, "martj42", dn, "fotmob-name-alias")
            tl += 1
    idx = MatchIndex(G)
    linked = new = 0
    for r in data:
        try:
            hs, as_ = int(r["home_score"]), int(r["away_score"])
        except (ValueError, KeyError):
            continue
        h, a = (reg.get("team", "martj42", r["home_team"]) or reg.mint("team", "martj42", r["home_team"]),
                reg.get("team", "martj42", r["away_team"]) or reg.mint("team", "martj42", r["away_team"]))
        for tid, nm in ((h, r["home_team"]), (a, r["away_team"])):
            G.put("team", {"tid": tid, "name": nm, "kind": "national"}, "martj42")
        key = f"{r['date']}|{r['home_team']}|{r['away_team']}"
        mid = twin(G, idx, r["date"], h, a, hs, as_, "martj42")
        if mid:
            G.xref("match", mid, "martj42", key, "date+teams")
            linked += 1
            continue
        cid = reg.get("competition", "martj42", r["tournament"]) or reg.mint("competition", "martj42", r["tournament"])
        G.put("competition", {"cid": cid, "name": r["tournament"], "scope": "international"}, "martj42")
        y = r["date"][:4]
        eid = reg.get("edition", "martj42", f"{r['tournament']}|{y}") or reg.mint("edition", "martj42", f"{r['tournament']}|{y}")
        G.put("edition", {"eid": eid, "cid": cid, "season": y}, "martj42")
        mid = reg.mint("match", "martj42", key)
        G.put("match", {"mid": mid, "eid": eid, "date": r["date"], "home": h, "away": a, "hs": hs, "as_": as_, "status": "finished"}, "martj42")
        G.xref("match", mid, "martj42", key, "martj42-native")
        idx.add(mid, r["date"], h, a)
        new += 1
    return {"rows": len(data), "linked": linked, "new": new, "teams_linked": tl}
