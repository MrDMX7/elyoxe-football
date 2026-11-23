"""The archive job's data step (docs/superpowers/specs/2026-11-22-tifo-archive-static-design.md): from a built tifo.db, the
season files (editions/<FotMob id>.json) and the match files (matches/<FotMob id>/<season>.json) of every competition — the
same files graph/publish.py gives the site for a few — into a local folder for site/archive/build.cjs. Nothing is uploaded.

    python -m graph.archive_export --db tifo.db --out work/data [--comps 47,87]
"""
import argparse, json, os, re, sqlite3, time
from collections import Counter

from graph import publish as P


def open_graph(path):
    """the built database, read as graph.db.Graph without recreating it"""
    from graph.db import Graph
    G = Graph.__new__(Graph)
    G.path, G.c = path, sqlite3.connect(path)
    G.cols = {t: [r[1] for r in G.c.execute(f"PRAGMA table_info({t})")] for (t,) in G.c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    G.stats = Counter()
    return G


def competitions(G):
    """every FotMob competition with matches in the archive"""
    return sorted({int(fid) for (fid,) in G.c.execute("""SELECT DISTINCT x.source_id FROM xref x JOIN edition e ON e.cid=x.tifo_id
                                                          JOIN match m ON m.eid=e.eid WHERE x.type='competition' AND x.source='fotmob'""")
                   if str(fid).isdigit()})


SHARDS = 500
# Transfermarkt's competition codes some career lines carry instead of a name (dcaribou): the big ones, the rest left out
TM_CODES = {"GB1": "Premier League", "GB2": "Championship", "GB3": "League One", "GB4": "League Two", "ES1": "LaLiga", "ES2": "LaLiga2",
            "IT1": "Serie A", "IT2": "Serie B", "L1": "Bundesliga", "L2": "2. Bundesliga", "FR1": "Ligue 1", "FR2": "Ligue 2", "NL1": "Eredivisie",
            "PO1": "Liga Portugal", "BE1": "Jupiler Pro League", "TR1": "Süper Lig", "SC1": "Scottish Premiership", "RU1": "Premier Liga",
            "GR1": "Super League 1", "UKR1": "Premier Liga", "DK1": "Superliga", "C1": "Super League", "A1": "Bundesliga", "SA1": "Saudi Pro League",
            "CL": "UEFA Champions League", "EL": "Europa League", "FAC": "FA Cup", "CDR": "Copa del Rey", "CIT": "Coppa Italia", "DFB": "DFB-Pokal",
            "FRC": "Coupe de France"}


def persons(G, out, min_apps=3, last=10):
    """people/<pid % 500>.json: every man the graph holds a record of beyond a name (3 games in the archive, a career line, an
    honour, caps, a move or an injury), for the archive's /p/k<Tifo id>/ pages (phase 2: «بروفايلات لكل اللاعبين»):
    n, ar, fm (FotMob id), b, d, nat, pos, h, ft, bp; car [season, competition, club, club FotMob id, apps, goals, assists,
    minutes, yellow, red] (Transfermarkt's career by competition); ms [season, competition FotMob id, competition, apps, goals]
    (his games in the archive); last [match key, date, home, home FotMob id, away, away FotMob id, hs, as, competition FotMob
    id]; tr [date, from, from FotMob id, to, to FotMob id, fee, type]; inj [season, kind, start, end, days, games];
    hon [kind, rank, competition, competition FotMob id, season, value]; intl [team, caps, goals, career]."""
    from collections import defaultdict
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    fm = lambda t: {a: int(b) for a, b in q(f"SELECT tifo_id, source_id FROM xref WHERE type='{t}' AND source='fotmob'") if str(b).isdigit()}
    fm_p, fm_t, fm_c, fm_m = fm("player"), fm("team"), fm("competition"), fm("match")
    tn = {t: (a or n) for t, n, a in q("SELECT tid, name, name_ar FROM team")}
    cn = {c: (a or n) for c, n, a in q("SELECT cid, name, name_ar FROM competition")}
    P = defaultdict(lambda: defaultdict(list))
    for pid, season, cid, n, g in q("""SELECT a.pid, e.season, e.cid, count(*), sum(coalesce(a.goals, 0)) FROM appearance a JOIN match m ON m.mid=a.mid
                                       JOIN edition e ON e.eid=m.eid WHERE a.played=1 OR a.started=1 GROUP BY a.pid, e.eid"""):
        P[pid]["ms"].append([season, fm_c.get(cid), cn.get(cid), n, g])
    apps = {p: sum(r[3] for r in d["ms"]) for p, d in P.items()}
    for pid in [p for p, n in apps.items() if n < min_apps]:
        del P[pid]["ms"]
    for pid, season, comp, cid, tid, a, mi, g, asst, y, r in q("""SELECT pid, season, comp, cid, tid, apps, minutes, goals, assists, yellow, red FROM player_season
                                                                  ORDER BY pid, season DESC"""):
        name = cn.get(cid) or (TM_CODES.get(comp) if re.fullmatch(r"[A-Z0-9]{1,5}", str(comp or "")) else comp)
        P[pid]["car"].append([season, name, tn.get(tid), fm_t.get(tid), a, g, asst, mi, y, r])
    for pid, d, f, t, fee, typ in q("SELECT pid, date, from_tid, to_tid, fee, type FROM transfer ORDER BY pid, date DESC"):
        P[pid]["tr"].append([d, tn.get(f), fm_t.get(f), tn.get(t), fm_t.get(t), fee, typ])
    for pid, season, kind, s, e, days, games in q("SELECT pid, season, kind, start, end, days, games FROM injury ORDER BY pid, start DESC"):
        P[pid]["inj"].append([season, kind, s, e, days, games])
    for pid, kind, rank, cid, season, value in q("""SELECT h.pid, h.kind, h.rank, e.cid, e.season, h.value FROM honour h JOIN edition e ON e.eid=h.eid
                                                  WHERE h.pid IS NOT NULL ORDER BY h.pid, e.season DESC"""):
        P[pid]["hon"].append([kind, rank, cn.get(cid), fm_c.get(cid), season, value])
    for pid, team, caps, goals, career in q("SELECT pid, team, caps, goals, career FROM intl_record ORDER BY coalesce(caps, 0)"):
        P[pid]["intl"] = [team, caps, goals, career]
    keep = {p for p, d in P.items() if any(d.get(k) for k in ("ms", "car", "tr", "inj", "hon", "intl"))}
    G.c.execute("DROP TABLE IF EXISTS exp_p")
    G.c.execute("CREATE TEMP TABLE exp_p(pid INTEGER PRIMARY KEY)")
    G.c.executemany("INSERT INTO exp_p VALUES(?)", [(p,) for p in keep if P[p].get("ms")])
    for pid, mid, d, h, a, hs, as_, cid in q(f"""SELECT pid, mid, d, home, away, hs, as_, cid FROM (
            SELECT a.pid, m.mid, substr(m.date,1,10) d, m.home, m.away, m.hs, m.as_, e.cid,
                   row_number() OVER (PARTITION BY a.pid ORDER BY m.date DESC) rn
            FROM exp_p CROSS JOIN appearance a ON a.pid=exp_p.pid JOIN match m ON m.mid=a.mid JOIN edition e ON e.eid=m.eid
            WHERE (a.played=1 OR a.started=1) AND m.hs IS NOT NULL) WHERE rn <= {int(last)}"""):
        P[pid]["last"].append([str(fm_m[mid]) if mid in fm_m else f"k{mid}", d, tn.get(h), fm_t.get(h), tn.get(a), fm_t.get(a), hs, as_, fm_c.get(cid)])
    G.c.execute("DROP TABLE exp_p")
    shards = defaultdict(dict)
    for pid, name, ar, born, died, nat, pos, h, foot, bp in q("SELECT pid, name, name_ar, born, died, nationality, position, height, foot, birthplace FROM player"):
        if pid in keep:
            d = P[pid]
            shards[pid % SHARDS][str(pid)] = {k: v for k, v in {"n": name, "ar": ar, "fm": fm_p.get(pid), "b": born, "d": died, "nat": nat, "pos": pos,
                                                                "h": h, "ft": foot, "bp": bp, **{k: d.get(k) for k in ("car", "ms", "last", "tr", "inj", "hon", "intl")}}.items()
                                              if v not in (None, [], "")}
    os.makedirs(os.path.join(out, "people"), exist_ok=True)
    for s, d in shards.items():
        with open(os.path.join(out, "people", f"{s}.json"), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    return {"persons": len(keep), "shards": len(shards)}


def export(db, out, comps=None):
    G = open_graph(db)
    os.makedirs(out, exist_ok=True)
    t = time.time()
    rec = {"editions": P.editions(G, out)}
    fids = comps or competitions(G)
    rec["matches"] = P.matches(G, out, comps=tuple(fids), teams=())
    rec["people"] = P.people(G, out)
    rec["persons"] = persons(G, out)            # people/<shard>.json: every man's profile (/p/k<id>/)
    rec["secs"] = round(time.time() - t)
    rec["competitions"] = len(fids)
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--comps", default="")
    a = ap.parse_args(argv)
    comps = [int(x) for x in a.comps.split(",") if x.strip()] or None
    print(export(a.db, a.out, comps), flush=True)


if __name__ == "__main__":
    main()
