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


PUB = 2_000_000_000          # FotMob's numbers end at 1,000,000,000: above them, a number of ours


def publication_ids(G):
    """A competition FotMob has no number for is published under PUB + its Tifo id (24 Nov 2026: 1,568 competitions and
    1,143,246 matches had no page, the season files being named by FotMob's number). The numbers live in this connection only,
    as rows of xref never committed (export() rolls them back): every reader of graph/publish.py finds them where it finds
    FotMob's. An award is no competition: its winners are on the men's pages."""
    c = G.c
    have = {t for t, s in c.execute("SELECT tifo_id, source_id FROM xref WHERE type='competition' AND source='fotmob'") if str(s).isdigit()}
    rows = [(cid, str(PUB + cid)) for (cid,) in c.execute("SELECT cid FROM competition WHERE kind IS NULL OR kind <> 'award'") if cid not in have]
    c.executemany("INSERT INTO xref(type, tifo_id, source, source_id, method) VALUES('competition', ?, 'fotmob', ?, 'archive-key')", rows)
    return len(rows)


GONE_AR = {"SU": "الاتحاد السوفيتي", "DD": "ألمانيا الشرقية", "YU": "يوغوسلافيا", "CS": "تشيكوسلوفاكيا"}


def countries_ar():
    """a country's code -> its name in Arabic (news/nations.json: the shortest Arabic name that is not its national team's)"""
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "news", "nations.json"), encoding="utf-8") as f:
        names = json.load(f)["names"]
    out = dict(GONE_AR)
    for code, ns in names.items():
        ar = sorted((n for n in ns if re.search("[؀-ۿ]", n) and "منتخب" not in n), key=len)
        if ar:
            out[code] = ar[0]
    return out


def catalogue(G, out):
    """competitions.json: every competition with a season file, for the archive's own pages of the ones the site has none for
    (/c/k<Tifo id>/): [{id (the files' number), cid, name, name_ar, kind, scope, country, country_ar, tier, seasons, matches,
    first, last}]"""
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    car = countries_ar()
    pub = {t: int(s) for t, s in q("SELECT tifo_id, source_id FROM xref WHERE type='competition' AND source='fotmob'") if str(s).isdigit()}
    games = {c: (n, e) for c, n, e in q("SELECT e.cid, count(*), count(DISTINCT e.eid) FROM match m JOIN edition e ON e.eid=m.eid WHERE m.hs IS NOT NULL GROUP BY 1")}
    span = {c: (a, b, n) for c, a, b, n in q("SELECT cid, min(season), max(season), count(*) FROM edition GROUP BY 1")}
    rows = []
    for cid, name, name_ar, kind, scope, country, tier in q("SELECT cid, name, name_ar, kind, scope, country, tier FROM competition WHERE kind IS NULL OR kind <> 'award'"):
        if cid not in pub or not os.path.exists(os.path.join(out, "editions", f"{pub[cid]}.json")):
            continue
        r = {"id": pub[cid], "cid": cid, "name": name, "name_ar": name_ar, "kind": kind, "scope": scope, "country": country, "country_ar": car.get(country), "tier": tier,
             "seasons": span.get(cid, (None, None, 0))[2], "matches": games.get(cid, (0, 0))[0], "first": span.get(cid, (None,))[0], "last": span.get(cid, (None, None))[1]}
        rows.append({k: v for k, v in r.items() if v is not None})
    with open(os.path.join(out, "competitions.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
    return {"catalogue": len(rows)}


def competitions(G):
    """every competition with a number (FotMob's, else ours: publication_ids) and matches in the archive"""
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


ARABIC, CODE = re.compile("[%s-%s]" % (chr(0x600), chr(0x6FF))), re.compile(r"[A-Z0-9]{1,5}")


def GENERATED_TERMS():
    """names/career_terms_ar.json {comps: {"<name>|<club's country>": Arabic}, injuries: {kind: Arabic}} (names/career_terms.py,
    23 Nov 2026: 507k career lines and 149k injuries still in Latin letters)"""
    try:
        d = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "names", "career_terms_ar.json"), encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {"comps": d.get("comps") or {}, "injuries": d.get("injuries") or {}}


def career_names(G, cn):
    """(Transfermarkt's competition name, club) -> its name in Arabic, or None: one of our competitions of that name (the
    club's own where several share it), else graph/tm_comps_ar.yaml (23 Nov 2026: 850k of 1.29M career lines read in English)"""
    import yaml
    from collections import defaultdict
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()
    by_name = defaultdict(set)
    for cid, name in q("SELECT cid, name FROM competition WHERE kind IS NULL OR kind <> 'award'"):
        by_name[norm(name)].add(cid)
    club = defaultdict(set)
    for tid, cid in q("""SELECT m.home, e.cid FROM match m JOIN edition e ON e.eid=m.eid GROUP BY 1, 2
                         UNION SELECT m.away, e.cid FROM match m JOIN edition e ON e.eid=m.eid GROUP BY 1, 2"""):
        club[tid].add(cid)
    try:
        cur = yaml.safe_load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tm_comps_ar.yaml"), encoding="utf-8")) or {}
    except OSError:
        cur = {}

    def name(comp, tid):
        cand = by_name.get(norm(comp), set())
        mine = cand if len(cand) == 1 else cand & club.get(tid, set())
        return (cn.get(next(iter(mine))) if len(mine) == 1 else None) or cur.get(comp)
    return name


def persons(G, out, min_apps=3, last=10, nat=lambda v: v):
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
    comp_ar = career_names(G, cn)
    gen = GENERATED_TERMS()                        # names/career_terms_ar.json (names/career_terms.py): the rest, by the clubs' country
    country_of = {t: c for t, c in q("SELECT tid, country FROM team")}
    gen_ar = lambda comp, tid: gen["comps"].get(f"{comp}|{country_of.get(tid) or ''}") or gen["comps"].get(f"{comp}|")
    for pid, season, comp, cid, tid, a, mi, g, asst, y, r in q("""SELECT pid, season, comp, cid, tid, apps, minutes, goals, assists, yellow, red FROM player_season
                                                                  ORDER BY pid, season DESC"""):
        # Arabic first (ours, else by name), then a real name before a code: competitions made from Transfermarkt codes are
        # named by the code («FAC»), the line itself says «FA Cup»
        own = cn.get(cid)
        name = next((x for x in (own, comp_ar(comp, tid), gen_ar(comp, tid)) if x and ARABIC.search(x)), None) or             next((x for x in (comp, own) if x and not CODE.fullmatch(x)), None) or TM_CODES.get(comp) or comp
        P[pid]["car"].append([season, name, tn.get(tid), fm_t.get(tid), a, g, asst, mi, y, r])
    for pid, d, f, t, fee, typ in q("SELECT pid, date, from_tid, to_tid, fee, type FROM transfer ORDER BY pid, date DESC"):
        P[pid]["tr"].append([d, tn.get(f), fm_t.get(f), tn.get(t), fm_t.get(t), fee, typ])
    for pid, season, kind, s, e, days, games in q("SELECT pid, season, kind, start, end, days, games FROM injury ORDER BY pid, start DESC"):
        P[pid]["inj"].append([season, gen["injuries"].get(kind, kind), s, e, days, games])
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
    for pid, name, ar, born, died, nation, pos, h, foot, bp in q("SELECT pid, name, name_ar, born, died, nationality, position, height, foot, birthplace FROM player"):
        if pid in keep:
            d = P[pid]
            shards[pid % SHARDS][str(pid)] = {k: v for k, v in {"n": name, "ar": ar, "fm": fm_p.get(pid), "b": born, "d": died, "nat": nat(nation), "pos": pos,
                                                                "h": h, "ft": foot, "bp": bp, **{k: d.get(k) for k in ("car", "ms", "last", "tr", "inj", "hon", "intl")}}.items()
                                              if v not in (None, [], "")}
    os.makedirs(os.path.join(out, "people"), exist_ok=True)
    for s, d in shards.items():
        with open(os.path.join(out, "people", f"{s}.json"), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    return {"persons": len(keep), "shards": len(shards)}


def referees(G, out, min_matches=5, last=10, nat=lambda v: v):
    """referees.json {rid: {n, ar, c, fm, ms: [season, competition FotMob id, competition, matches, yellow, red], last: [...]}}:
    every referee of 5 games or more (the owner: «كل الحكام»), for /r/k<Tifo id>/"""
    from collections import defaultdict
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    fm = lambda t: {a: int(b) for a, b in q(f"SELECT tifo_id, source_id FROM xref WHERE type='{t}' AND source='fotmob'") if str(b).isdigit()}
    fm_r, fm_t, fm_c, fm_m = fm("referee"), fm("team"), fm("competition"), fm("match")
    tn = {t: (a or n) for t, n, a in q("SELECT tid, name, name_ar FROM team")}
    cn = {c: (a or n) for c, n, a in q("SELECT cid, name, name_ar FROM competition")}
    R = defaultdict(lambda: defaultdict(list))
    cards = {m: (y, r) for m, y, r in q("""SELECT mid, sum(type='yellow'), sum(type IN ('red','second_yellow')) FROM event WHERE type IN ('yellow','red','second_yellow')
                                          GROUP BY mid""")}
    rows = q("""SELECT m.rid, m.mid, substr(m.date,1,10), m.home, m.away, m.hs, m.as_, e.season, e.cid FROM match m JOIN edition e ON e.eid=m.eid
                WHERE m.rid IS NOT NULL AND m.hs IS NOT NULL ORDER BY m.date DESC""")
    n = defaultdict(int)
    for rid, *_ in rows:
        n[rid] += 1
    agg = defaultdict(lambda: [0, 0, 0])
    for rid, mid, d, h, a, hs, as_, season, cid in rows:
        if n[rid] < min_matches:
            continue
        y, r = cards.get(mid, (0, 0))
        k = agg[(rid, season, cid)]
        k[0] += 1; k[1] += y or 0; k[2] += r or 0
        if len(R[rid]["last"]) < last:
            R[rid]["last"].append([str(fm_m[mid]) if mid in fm_m else f"k{mid}", d, tn.get(h), fm_t.get(h), tn.get(a), fm_t.get(a), hs, as_, fm_c.get(cid)])
    for (rid, season, cid), (m, y, r) in agg.items():
        R[rid]["ms"].append([season, fm_c.get(cid), cn.get(cid), m, y, r])
    out_d = {}
    for rid, name, ar, country in q("SELECT rid, name, name_ar, country FROM referee"):
        if rid in R:
            out_d[str(rid)] = {k: v for k, v in {"n": name, "ar": ar, "c": nat(country), "fm": fm_r.get(rid), "ms": sorted(R[rid]["ms"], key=lambda x: str(x[0]), reverse=True),
                                                 "last": R[rid]["last"]}.items() if v not in (None, [], "")}
    with open(os.path.join(out, "referees.json"), "w", encoding="utf-8") as f:
        json.dump(out_d, f, ensure_ascii=False, separators=(",", ":"))
    return {"referees": len(out_d)}


def clubs(G, out, min_matches=30, last=10, nat=lambda v: v):
    """clubs.json {tid: {n, ar, c, f: founding year, st: [home ground, capacity, city] (Wikidata, graph/load/wikidata_facts), ss: [season, competition FotMob id, competition, p, w, d, l, gf, ga], hon: [kind, competition,
    competition FotMob id, season], last: [...], fm: FotMob id}}: every club with 30 games or more in the archive (the
    Wimbledon of 1990, Dubai CSC, Al Khaleej), for /t/k<Tifo id>/; FotMob's too since 24 Nov 2026 (Transfermarkt's Djurgården,
    1,862 games, folds into FotMob's, whose club the site has no page for), the renderer leaving out those the site has"""
    from collections import defaultdict
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    fm = lambda t: {a: int(b) for a, b in q(f"SELECT tifo_id, source_id FROM xref WHERE type='{t}' AND source='fotmob'") if str(b).isdigit()}
    fm_t, fm_c, fm_m = fm("team"), fm("competition"), fm("match")
    tn = {t: (a or n) for t, n, a in q("SELECT tid, name, name_ar FROM team")}
    cn = {c: (a or n) for c, n, a in q("SELECT cid, name, name_ar FROM competition")}
    rows = q("""SELECT m.mid, substr(m.date,1,10), m.home, m.away, m.hs, m.as_, e.season, e.cid FROM match m JOIN edition e ON e.eid=m.eid
                WHERE m.hs IS NOT NULL ORDER BY m.date DESC""")
    n = defaultdict(int)
    for mid, d, h, a, *_ in rows:
        n[h] += 1; n[a] += 1
    want = {t for t, k in n.items() if k >= min_matches}
    C = defaultdict(lambda: defaultdict(list))
    agg = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    for mid, d, h, a, hs, as_, season, cid in rows:
        for t, gf, ga in ((h, hs, as_), (a, as_, hs)):
            if t not in want:
                continue
            k = agg[(t, season, cid)]
            k[0] += 1; k[1] += gf > ga; k[2] += gf == ga; k[3] += gf < ga; k[4] += gf; k[5] += ga
            if len(C[t]["last"]) < last:
                C[t]["last"].append([str(fm_m[mid]) if mid in fm_m else f"k{mid}", d, tn.get(h), fm_t.get(h), tn.get(a), fm_t.get(a), hs, as_, fm_c.get(cid)])
    for (t, season, cid), v in agg.items():
        C[t]["ss"].append([season, fm_c.get(cid), cn.get(cid), *v])
    for t, kind, cid, season in q("SELECT h.tid, h.kind, e.cid, e.season FROM honour h JOIN edition e ON e.eid=h.eid WHERE h.kind IN ('champion','runner_up') AND h.tid IS NOT NULL"):
        if t in want:
            C[t]["hon"].append([kind, cn.get(cid), fm_c.get(cid), season])
    out_d = {}
    ground = {s: [a or n, cap, city] for s, n, a, cap, city in q("SELECT sid, name, name_ar, capacity, city FROM stadium") if a or n}
    for tid, name, ar, country, founded, sid in q("SELECT tid, name, name_ar, country, founded, sid FROM team"):
        if tid in want:
            c = C[tid]
            out_d[str(tid)] = {k: v for k, v in {"n": name, "ar": ar, "c": nat(country), "f": founded, "st": ground.get(sid), "ss": sorted(c["ss"], key=lambda x: str(x[0]), reverse=True),
                                                 "hon": sorted(c["hon"], key=lambda x: str(x[3]), reverse=True), "last": c["last"],
                                                 "fm": fm_t.get(tid)}.items() if v not in (None, [], "")}
    with open(os.path.join(out, "clubs.json"), "w", encoding="utf-8") as f:
        json.dump(out_d, f, ensure_ascii=False, separators=(",", ":"))
    return {"clubs": len(out_d)}


def nation_ar(G):
    """a nationality in Arabic (23 Nov: profiles showed «الجنسية: BRA»): the graph keeps FotMob's three-letter code for a player,
    which reads as the senior national team most of that code's men played for, and an English name for a coach or a
    referee, which reads as the senior national team of that name; anything else stays as it is"""
    import re
    from collections import Counter, defaultdict
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    senior = {t: (n, a) for t, n, a in q("SELECT tid, name, name_ar FROM team WHERE kind='national' AND name_ar IS NOT NULL")
              if not re.search(r"\d|\(W\)|women|olympic", f"{n} {a}", re.I)}
    by_name = {n: a for n, a in senior.values()}
    votes = defaultdict(Counter)
    for code, tid, k in q("""SELECT p.nationality, a.tid, count(*) FROM appearance a JOIN player p ON p.pid=a.pid JOIN team t ON t.tid=a.tid
                             WHERE t.kind='national' AND length(p.nationality)=3 GROUP BY 1, 2"""):
        if tid in senior:
            votes[code][tid] += k
    by_code = {}
    for code, c in votes.items():
        (tid, k), total = c.most_common(1)[0], sum(c.values())
        if k >= 3 and k >= 0.6 * total:
            by_code[code] = senior[tid][1]
    low = {n.lower(): a for n, a in by_name.items()}                     # «gibraltar», «libya»: some sources write them in lower case
    alias = {k.lower(): v for k, v in NATION_ALIAS.items()}
    gone = {k.lower(): v for k, v in NATION_GONE.items()}

    def ar(v):
        if not v:
            return v
        k = str(v).strip().lower()
        return by_code.get(v) or low.get(alias.get(k, k).lower()) or gone.get(k) or v
    return ar


# the English forms the coaches' and referees' sources use for a national team named otherwise, and the states gone since
NATION_ALIAS = {"United States": "USA", "Czech Republic": "Czechia", "Republic of Ireland": "Ireland", "Turkey": "Turkiye", "Türkiye": "Turkiye",
                "United Arab Emirates": "UAE", "Korea Republic": "South Korea", "IR Iran": "Iran", "China PR": "China",
                "Côte d'Ivoire": "Ivory Coast", "Bosnia-Herzegovina": "Bosnia and Herzegovina", "Macedonia": "North Macedonia",
                "Surinam": "Suriname", "Holland": "Netherlands", "Korea, South": "South Korea", "Cape Verde Islands": "Cape Verde",
                "Chinese Taipei": "Taiwan", "DR Congo": "Congo DR", "Bosnia & Herzegovina": "Bosnia and Herzegovina", "The Phillipines": "Philippines"}
NATION_GONE = {"Soviet Union": "الاتحاد السوفيتي", "West Germany": "ألمانيا الغربية", "East Germany": "ألمانيا الشرقية",
               "Yugoslavia": "يوغوسلافيا", "Czechoslovakia": "تشيكوسلوفاكيا", "United Arab Republic": "الجمهورية العربية المتحدة",
               "Zaire": "زائير", "Dutch East Indies": "جزر الهند الشرقية الهولندية", "Serbia and Montenegro": "صربيا والجبل الأسود"}


def coaches(G, out, last=10, nat=lambda v: v):
    """coaches.json {kid: {n, ar, b, nat, fm, pid, sp: [team, team FotMob id, start, end, m, w, d, l, gf, ga], hon: [kind, rank,
    competition, competition FotMob id, season, value], last: [...]}}: every coach with a bench in the archive or a coach's
    award (the owner, 22 Nov 2026: «كل المدربين»), for /coach/k<Tifo id>/"""
    from collections import defaultdict
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    fm = lambda t: {a: int(b) for a, b in q(f"SELECT tifo_id, source_id FROM xref WHERE type='{t}' AND source='fotmob'") if str(b).isdigit()}
    fm_k, fm_t, fm_c, fm_m = fm("coach"), fm("team"), fm("competition"), fm("match")
    tn = {t: (a or n) for t, n, a in q("SELECT tid, name, name_ar FROM team")}
    cn = {c: (a or n) for c, n, a in q("SELECT cid, name, name_ar FROM competition")}
    K = defaultdict(lambda: defaultdict(list))
    for s in sorted(P.coach_spells(G), key=lambda s: s["start"], reverse=True):
        K[s["kid"]]["sp"].append([tn.get(s["tid"]), fm_t.get(s["tid"]), *(s[k] for k in ("start", "end", "m", "w", "d", "l", "gf", "ga"))])
    for kid, mid, d, h, a, hs, as_, cid in q("""SELECT x.kid, m.mid, substr(m.date,1,10), m.home, m.away, m.hs, m.as_, e.cid FROM match_coach x
                                               JOIN match m ON m.mid=x.mid JOIN edition e ON e.eid=m.eid WHERE m.hs IS NOT NULL ORDER BY m.date DESC"""):
        if len(K[kid]["last"]) < last:
            K[kid]["last"].append([str(fm_m[mid]) if mid in fm_m else f"k{mid}", d, tn.get(h), fm_t.get(h), tn.get(a), fm_t.get(a), hs, as_, fm_c.get(cid)])
    for kid, kind, rank, cid, season, value in q("""SELECT h.kid, h.kind, h.rank, e.cid, e.season, h.value FROM honour h JOIN edition e ON e.eid=h.eid
                                                   WHERE h.kid IS NOT NULL ORDER BY e.season DESC"""):
        K[kid]["hon"].append([kind, rank, cn.get(cid), fm_c.get(cid), season, value])
    out_d = {}
    for kid, name, ar, born, nation, pid in q("SELECT kid, name, name_ar, born, nationality, pid FROM coach"):
        if kid in K:
            c = K[kid]
            out_d[str(kid)] = {k: v for k, v in {"n": name, "ar": ar, "b": born, "nat": nat(nation), "fm": fm_k.get(kid), "pid": pid,
                                                 "sp": c["sp"], "hon": c["hon"], "last": c["last"]}.items() if v not in (None, [], "")}
    with open(os.path.join(out, "coaches.json"), "w", encoding="utf-8") as f:
        json.dump(out_d, f, ensure_ascii=False, separators=(",", ":"))
    return {"coaches": len(out_d)}


def fm_teams(G, out):
    """fm_teams.json {FotMob team id: its Arabic name, else its name}: a FotMob man's club on his profile (23 Nov 2026)"""
    rows = G.c.execute("""SELECT x.source_id, t.name_ar, t.name FROM xref x JOIN team t ON t.tid=x.tifo_id
                          WHERE x.type='team' AND x.source='fotmob'""").fetchall()
    d = {str(k): (a or n) for k, a, n in rows if str(k).isdigit() and (a or n)}
    with open(os.path.join(out, "fm_teams.json"), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    return {"fm_teams": len(d)}


def export(db, out, comps=None):
    G = open_graph(db)
    os.makedirs(out, exist_ok=True)
    t = time.time()
    rec = {"ours": publication_ids(G)}
    rec["editions"] = P.editions(G, out)
    rec.update(catalogue(G, out))
    fids = comps or competitions(G)
    rec["matches"] = P.matches(G, out, comps=tuple(fids), teams=())
    rec["people"] = P.people(G, out)
    ar = nation_ar(G)                           # «الجنسية: هولندا», not «NED»
    rec["persons"] = persons(G, out, nat=ar)            # people/<shard>.json: every man's profile (/p/k<id>/)
    rec["referees"] = referees(G, out, nat=ar)          # referees.json: every referee of 5 games (/r/k<id>/)
    rec["clubs"] = clubs(G, out, nat=ar)                # clubs.json: every club FotMob has no page for, 30 games (/t/k<id>/)
    rec["coaches"] = coaches(G, out, nat=ar)
    rec["fm_teams"] = fm_teams(G, out)          # fm_teams.json: a FotMob man's club on his profile            # coaches.json: every coach with a bench or an award (/coach/k<id>/)
    if not comps:                               # vs/, elo/: every pair's meetings, every team's record and rating (/vs/, /elo/)
        from graph import features_export
        rec["versus"] = features_export.versus(G, out)
    rec["secs"] = round(time.time() - t)
    rec["competitions"] = len(fids)
    G.c.rollback()                              # publication_ids' rows: never written
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
