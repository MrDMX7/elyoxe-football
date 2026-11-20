"""The files the site reads (spec §7.6), from the built graph:
  awards/index.json     every award: key, names, group (world, continent, tournament, league, country, women), years held,
                        first and last, the most-winning player [name, wins, FotMob id]
  awards/<key>.json     every year (newest first) with its podium (rank, names, FotMob id when the player has one, team, value)
                        and the most wins
  awards/players.json   {FotMob player id: [[award key, season, "winner", rank, None] | [None, season, kind, rank, FotMob comp]]}
Keys are slugs of the English name, unique (the Tifo id is appended on a clash)."""
import json, os, re, unicodedata
from collections import Counter, defaultdict

GROUPS = [("women", re.compile(r"women|féminin|female|ladies|girls", re.I)),
          ("club", re.compile(r"\b(f\.?c\.?|a\.?f\.?c\.?|s\.?c\.?|c\.?f\.?)\b.*(player|season|year)|\b(united|city|rovers|athletic|wanderers|albion|hotspur|county|town|"
                              r"rangers|celtic|arsenal|chelsea|liverpool|everton|juventus|milan|inter|barcelona|real madrid|bayern|ajax|benfica|porto)\b.*player of the", re.I)),
          ("tournament", re.compile(r"world cup|euro\b|uefa euro|copa am|nations|asian cup|gulf cup|arab cup|african cup|cup of nations|olympic|"
                                    r"champions league|club world|confederations|gold cup|libertadores|tournament", re.I)),
          ("continent", re.compile(r"asia|afc\b|africa|caf\b|europe|uefa|south america|conmebol|concacaf|oceania|arab", re.I)),
          ("world", re.compile(r"fifa|ballon|world|golden boy|kopa|yashin|m[uü]ller|pusk[aá]s|iffhs|globe|golden foot|best", re.I)),
          ("league", re.compile(r"league|liga|serie a|bundesliga|ligue|eredivisie|primeira|s[uü]per lig|pichichi|capocannoniere|division", re.I))]


def slug(s):
    s = unicodedata.normalize("NFKD", (s or "").replace("'", "").replace("’", "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "award"


def group(name):
    for g, rx in GROUPS:
        if rx.search(name or ""):
            return g
    return "country"


def _dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(path + ".tmp", path)


def awards(G, out_dir):
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    fm_player = {tid: int(sid) for tid, sid in q("SELECT tifo_id, source_id FROM xref WHERE type='player' AND source='fotmob'") if str(sid).isdigit()}
    fm_comp = {tid: int(sid) for tid, sid in q("SELECT tifo_id, source_id FROM xref WHERE type='competition' AND source='fotmob'") if str(sid).isdigit()}
    pname = {pid: (n, a) for pid, n, a in q("SELECT pid, name, name_ar FROM player")}
    tname = {tid: (n, a) for tid, n, a in q("SELECT tid, name, name_ar FROM team")}
    d = os.path.join(out_dir, "awards")
    index, keys, players = [], set(), defaultdict(list)
    for cid, name, name_ar in q("SELECT cid, name, name_ar FROM competition WHERE kind='award' ORDER BY cid"):
        key = slug(name)
        if key in keys:
            key = f"{key}-{cid}"
        keys.add(key)
        years = defaultdict(list)
        for season, rank, pid, tid, kid, value in q("""SELECT e.season, h.rank, h.pid, h.tid, h.kid, h.value FROM honour h JOIN edition e ON e.eid=h.eid
                                                       WHERE e.cid=? AND h.kind='winner' ORDER BY e.season, h.rank""", (cid,)):
            who = pname.get(pid) if pid else (tname.get(tid) if tid else None)
            if kid:
                who = G.c.execute("SELECT name, name_ar FROM coach WHERE kid=?", (kid,)).fetchone()
            if not who:
                continue
            years[season].append({"rank": rank, "name": who[0], "name_ar": who[1], "fotmob": fm_player.get(pid) if pid else None,
                                  **({"tifo": pid} if pid and not fm_player.get(pid) and not kid else {}),
                                  "team": (tname.get(tid) or (None, None))[1] or (tname.get(tid) or (None, None))[0] if (tid and pid) else None,
                                  "value": value})
            if pid and not kid:                        # a player FotMob does not know is k<Tifo id> (his page: /p/k<id>/)
                players[str(fm_player[pid]) if fm_player.get(pid) else f"k{pid}"].append([key, season, "winner", rank, None])
        if not years:
            continue
        wins = Counter()
        for season, pod in years.items():
            for p in pod:
                if p["rank"] == 1:
                    wins[(p["name_ar"] or p["name"], p["fotmob"])] += 1
        most = [[n, c, f] for (n, f), c in sorted(wins.items(), key=lambda x: (-x[1], x[0][0]))[:10]]
        seasons = sorted(years, reverse=True)
        _dump(os.path.join(d, f"{key}.json"), {"key": key, "name": name, "name_ar": name_ar, "group": group(name),
                                               "years": [{"season": s, "podium": years[s]} for s in seasons], "most": most})
        index.append({"key": key, "name": name, "name_ar": name_ar, "group": group(name), "years": len(seasons), "first": seasons[-1], "last": seasons[0],
                      "top": most[0] if most else None})
    for pid, season, kind, rank, cid in q("""SELECT h.pid, e.season, h.kind, h.rank, e.cid FROM honour h JOIN edition e ON e.eid=h.eid
                                             JOIN competition c ON c.cid=e.cid WHERE h.pid IS NOT NULL AND coalesce(c.kind,'') <> 'award'"""):
        players[str(fm_player[pid]) if fm_player.get(pid) else f"k{pid}"].append([None, season, kind, rank, fm_comp.get(cid)])
    _dump(os.path.join(d, "index.json"), {"awards": sorted(index, key=lambda a: (-a["years"], a["key"]))})
    _dump(os.path.join(d, "players.json"), {k: sorted(v, key=lambda x: (x[1], x[2]), reverse=True) for k, v in sorted(players.items())})
    return {"awards": len(index), "players": len(players)}


def motm(G, out_dir, today=None, top=50):
    """motm/index.json (leaders this season, since 1 July, and all time: overall, per competition, per club) and
    motm/players.json ({FotMob player id: name, total, now (this season), seasons, comps, opponents, recent}) from
    match_award (spec §8). The index carries today and the FotMob ids it counted in the last 21 days, so the site can add
    the matches finished since this build without counting one twice (phase 6, site/lib/whistle.cjs)."""
    from datetime import date, timedelta
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    t = date.fromisoformat(today) if today else date.today()
    since = f"{t.year if t.month >= 7 else t.year - 1}-07-01"
    fm_p = {a: int(b) for a, b in q("SELECT tifo_id, source_id FROM xref WHERE type='player' AND source='fotmob'") if str(b).isdigit()}
    fm_t = {a: int(b) for a, b in q("SELECT tifo_id, source_id FROM xref WHERE type='team' AND source='fotmob'") if str(b).isdigit()}
    fm_c = {a: int(b) for a, b in q("SELECT tifo_id, source_id FROM xref WHERE type='competition' AND source='fotmob'") if str(b).isdigit()}
    fm_m = {a: int(b) for a, b in q("SELECT tifo_id, source_id FROM xref WHERE type='match' AND source='fotmob'") if str(b).isdigit()}
    name = {pid: (ar or n) for pid, n, ar in q("SELECT pid, name, name_ar FROM player")}
    rows = q("""SELECT w.mid, w.pid, w.tid, w.value, substr(m.date,1,10), m.home, m.away, e.season, e.cid FROM match_award w
                JOIN match m ON m.mid=w.mid LEFT JOIN edition e ON e.eid=m.eid WHERE w.kind='motm' ORDER BY m.date DESC""")
    allc, seasonc, counted = Counter(), Counter(), set()
    recent_from = (t - timedelta(days=21)).isoformat()
    comp_all, comp_now, club_all, club_now = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    players = {}
    for mid, pid, tid, value, d, home, away, season, cid in rows:
        fp = fm_p.get(pid)
        if fp is None:
            continue
        cur = (d or "") >= since
        if (d or "") >= recent_from and fm_m.get(mid):
            counted.add(fm_m[mid])
        allc[fp] += 1
        if cur:
            seasonc[fp] += 1
        fc, ft = fm_c.get(cid), fm_t.get(tid)
        if fc:
            comp_all[fc][fp] += 1
            if cur:
                comp_now[fc][fp] += 1
        if ft:
            club_all[ft][fp] += 1
            if cur:
                club_now[ft][fp] += 1
        opp = fm_t.get(away if tid == home else home)
        p = players.setdefault(str(fp), {"name": name.get(pid), "total": 0, "now": 0, "seasons": Counter(), "comps": Counter(), "opponents": Counter(), "recent": []})
        p["total"] += 1
        p["now"] += cur
        if season:
            p["seasons"][season] += 1
        if fc:
            p["comps"][str(fc)] += 1
        if opp:
            p["opponents"][str(opp)] += 1
        if len(p["recent"]) < 10 and fm_m.get(mid):
            p["recent"].append([fm_m[mid], d, value, opp])
    pid_of = {v: k for k, v in fm_p.items()}
    lead = lambda c, n=top: [[fp, name.get(pid_of.get(fp)), k] for fp, k in sorted(c.items(), key=lambda x: (-x[1], x[0]))[:n]]
    cname = {fm_c[c]: (ar or n) for c, n, ar in q("SELECT cid, name, name_ar FROM competition") if c in fm_c}
    index = {"since": since, "today": t.isoformat(), "counted": sorted(counted), "matches": len(rows), "leaders": {"season": lead(seasonc), "all": lead(allc)},
             "comps": {str(c): {"name": cname.get(c), "season": lead(comp_now[c], 20), "all": lead(comp_all[c], 20)} for c in sorted(comp_all)},
             "clubs": {str(t): {"season": lead(club_now[t], 10), "all": lead(club_all[t], 10)} for t in sorted(club_all) if sum(club_all[t].values()) >= 3}}
    for p in players.values():
        for k in ("seasons", "comps", "opponents"):
            p[k] = dict(sorted(p[k].items(), key=lambda x: (-x[1], x[0])))
    _dump(os.path.join(out_dir, "motm", "index.json"), index)
    _dump(os.path.join(out_dir, "motm", "players.json"), dict(sorted(players.items())))
    return {"matches": len(rows), "players": len(players)}


def coaches(G, out_dir, gap_days=180, national_gap_days=730):
    """coaches/teams.json ({FotMob team id: spells, newest first}) and coaches/coaches.json ({Tifo coach id: name, FotMob id,
    spells}): a spell is a coach's run of matches on one club's bench with no gap over gap_days (national_gap_days for a
    national team, which can go a year between tournaments in our data), with its record."""
    from datetime import date
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    fm_t = {a: int(b) for a, b in q("SELECT tifo_id, source_id FROM xref WHERE type='team' AND source='fotmob'") if str(b).isdigit()}
    fm_k = {a: int(b) for a, b in q("SELECT tifo_id, source_id FROM xref WHERE type='coach' AND source='fotmob'") if str(b).isdigit()}
    cname = {k: (n, a) for k, n, a in q("SELECT kid, name, name_ar FROM coach")}
    tname = {t: (a or n) for t, n, a in q("SELECT tid, name, name_ar FROM team")}
    national = {t for (t,) in q("SELECT tid FROM team WHERE kind='national'")}
    runs = defaultdict(list)
    for kid, side, d, home, away, hs, as_ in q("""SELECT x.kid, x.side, substr(m.date,1,10), m.home, m.away, m.hs, m.as_ FROM match_coach x
                                                 JOIN match m ON m.mid=x.mid WHERE m.hs IS NOT NULL AND m.date IS NOT NULL ORDER BY m.date"""):
        tid, gf, ga = (home, hs, as_) if side == "h" else (away, as_, hs)
        runs[(kid, tid)].append((d, gf, ga))
    spells = []
    for (kid, tid), ms in runs.items():
        cur = None
        for d, gf, ga in ms:
            if cur and (date.fromisoformat(d) - date.fromisoformat(cur["end"])).days > (national_gap_days if tid in national else gap_days):
                spells.append(cur)
                cur = None
            if cur is None:
                cur = {"kid": kid, "tid": tid, "start": d, "end": d, "m": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0}
            cur["end"] = d
            cur["m"] += 1
            cur["gf"] += gf
            cur["ga"] += ga
            cur["w" if gf > ga else "l" if gf < ga else "d"] += 1
        if cur:
            spells.append(cur)
    teams, people = defaultdict(list), defaultdict(lambda: {"spells": []})
    for s in sorted(spells, key=lambda s: s["start"], reverse=True):
        nm = cname.get(s["kid"]) or (None, None)
        row = {"kid": s["kid"], "name": nm[0], "name_ar": nm[1], **{k: s[k] for k in ("start", "end", "m", "w", "d", "l", "gf", "ga")}}
        if s["tid"] in fm_t:
            teams[str(fm_t[s["tid"]])].append(row)
        p = people[str(s["kid"])]
        p.update(name=nm[0], name_ar=nm[1], fotmob=fm_k.get(s["kid"]))
        p["spells"].append({"team": fm_t.get(s["tid"]), "team_name": tname.get(s["tid"]), **{k: s[k] for k in ("start", "end", "m", "w", "d", "l", "gf", "ga")}})
    _dump(os.path.join(out_dir, "coaches", "teams.json"), dict(sorted(teams.items())))
    _dump(os.path.join(out_dir, "coaches", "coaches.json"), dict(sorted(people.items())))
    return {"spells": len(spells), "teams": len(teams), "coaches": len(people)}


def editions(G, out_dir):
    """editions/<FotMob competition>.json: every season of each of our competitions with its champion, runner-up, final table,
    top scorers, season awards (best player, young player, goalkeeper, coach, local player), the champion's coach, the man of
    the match leaders and the matches held: the season pages' data (phase 7). Newest season first."""
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    fm = lambda t: {a: int(b) for a, b in q(f"SELECT tifo_id, source_id FROM xref WHERE type='{t}' AND source='fotmob'") if str(b).isdigit()}
    fm_c, fm_t, fm_p = fm("competition"), fm("team"), fm("player")
    tn = {t: (a or n) for t, n, a in q("SELECT tid, name, name_ar FROM team")}
    pn = {p: (a or n) for p, n, a in q("SELECT pid, name, name_ar FROM player")}
    kn = {k: (a or n) for k, n, a in q("SELECT kid, name, name_ar FROM coach")}
    team = lambda t: {"fotmob": fm_t.get(t), "name": tn.get(t)} if t else None
    n = 0
    for cid, fid in sorted(fm_c.items(), key=lambda x: x[1]):
        name, name_ar = q("SELECT name, name_ar FROM competition WHERE cid=?", (cid,))[0]
        seasons = []
        for eid, season, note in q("SELECT eid, season, note FROM edition WHERE cid=? ORDER BY season DESC", (cid,)):
            hon = defaultdict(list)
            for kind, rank, tid, pid, kid, value in q("SELECT kind, rank, tid, pid, kid, value FROM honour WHERE eid=? ORDER BY kind, rank", (eid,)):
                hon[kind].append((rank, tid, pid, kid, value))
            whole = lambda v: int(v) if isinstance(v, float) and v.is_integer() else v           # the points column is REAL: 68, not 68.0
            table = [[r, fm_t.get(t), tn.get(t), p, w, d, l, gf, ga, whole(pts)] for r, t, p, w, d, l, gf, ga, pts in
                     q("SELECT rank, tid, played, won, drawn, lost, gf, ga, pts FROM standing WHERE eid=? ORDER BY grp, rank", (eid,))]
            matches = q("SELECT count(*) FROM match WHERE eid=?", (eid,))[0][0]
            if not hon and not table and not matches and not note:
                continue
            champ = (hon.get("champion") or [(None, None)])[0][1]
            coach = q("""SELECT x.kid, count(*) n FROM match_coach x JOIN match m ON m.mid=x.mid WHERE m.eid=? AND
                         ((x.side='h' AND m.home=?) OR (x.side='a' AND m.away=?)) GROUP BY x.kid ORDER BY n DESC LIMIT 1""", (eid, champ, champ)) if champ else []
            motm = q("""SELECT w.pid, count(*) n FROM match_award w JOIN match m ON m.mid=w.mid WHERE m.eid=? AND w.kind='motm'
                        GROUP BY w.pid ORDER BY n DESC, w.pid LIMIT 5""", (eid,))
            people = lambda kind: [{"rank": r, "fotmob": fm_p.get(p), **({} if fm_p.get(p) else {"tifo": p}), "name": pn.get(p), "value": v}
                                   for r, t, p, k, v in hon.get(kind, []) if p]
            seasons.append({"season": season, "matches": matches, "champion": team(champ), "runner_up": team((hon.get("runner_up") or [(None, None)])[0][1]),
                            "table": table, "top_scorers": people("top_scorer")[:10],
                            **{k: people(k)[:3] for k in ("best_player", "best_young", "best_goalkeeper", "best_local", "top_assist")},
                            "best_coach": [{"kid": k, "name": kn.get(k)} for r, t, p, k, v in hon.get("best_coach", []) if k][:1],
                            "champion_coach": {"kid": coach[0][0], "name": kn.get(coach[0][0])} if coach else None,
                            "motm": [[fm_p.get(p), pn.get(p), c] for p, c in motm if fm_p.get(p)], **({"note": note} if note else {})})
        if seasons:
            _dump(os.path.join(out_dir, "editions", f"{fid}.json"), {"fotmob": fid, "name": name, "name_ar": name_ar, "seasons": seasons})
            n += 1
    return {"competitions": n}


def people(G, out_dir, min_wc=3):
    """people/index.json: the players the site has no FotMob page for whose record is worth one (graph phase 7, the old
    players): a title or an award won (rank 1), or min_wc World Cup matches. Only what the archive holds in full: the Arabic
    name, birth and death, the national team, and each World Cup with its matches and goals (Fjelstul is complete). Their
    honours are awards/players.json's k<Tifo id> entries; never a career total (internationals before FotMob are partial)."""
    q = lambda s, p=(): G.c.execute(s, p).fetchall()
    fm = {a for (a,) in q("SELECT tifo_id FROM xref WHERE type='player' AND source='fotmob'")}
    wc_cid = {a for (a,) in q("SELECT tifo_id FROM xref WHERE type='competition' AND source='fotmob' AND source_id IN ('77', 77)")}
    wc = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    nat = {}
    for pid, season, goals, tname in q(f"""SELECT a.pid, e.season, coalesce(a.goals,0), coalesce(t.name_ar, t.name) FROM appearance a
                                         JOIN match m ON m.mid=a.mid JOIN edition e ON e.eid=m.eid JOIN team t ON t.tid=a.tid
                                         WHERE a.played=1 AND e.cid IN ({",".join(map(str, wc_cid)) or "NULL"})"""):
        wc[pid][season][0] += 1
        wc[pid][season][1] += goals
        nat[pid] = tname
    won = {p for (p,) in q("SELECT DISTINCT pid FROM honour WHERE rank=1 AND pid IS NOT NULL")}
    keep = {p for p in won | {p for p, ys in wc.items() if sum(v[0] for v in ys.values()) >= min_wc} if p not in fm}
    for pid, tname in q("""SELECT a.pid, coalesce(t.name_ar, t.name) FROM appearance a JOIN team t ON t.tid=a.tid
                           WHERE t.kind='national' AND a.played=1 GROUP BY a.pid, t.tid ORDER BY count(*) DESC"""):     # his most-played side first
        if pid in keep and pid not in nat:
            nat[pid] = tname
    out = {}
    for pid, name, name_ar, born, died in q("SELECT pid, name, name_ar, born, died FROM player"):
        if pid in keep:
            out[f"k{pid}"] = {"name": name, "name_ar": name_ar, "born": born, "died": died, "nat": nat.get(pid),
                              "wc": [[y, v[0], v[1]] for y, v in sorted(wc.get(pid, {}).items(), reverse=True)]}
    _dump(os.path.join(out_dir, "people", "index.json"), dict(sorted(out.items())))
    return {"people": len(out)}

