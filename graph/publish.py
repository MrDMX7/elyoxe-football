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
                                  "team": (tname.get(tid) or (None, None))[1] or (tname.get(tid) or (None, None))[0] if (tid and pid) else None,
                                  "value": value})
            if pid and fm_player.get(pid):
                players[str(fm_player[pid])].append([key, season, "winner", rank, None])
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
        if fm_player.get(pid):
            players[str(fm_player[pid])].append([None, season, kind, rank, fm_comp.get(cid)])
    _dump(os.path.join(d, "index.json"), {"awards": sorted(index, key=lambda a: (-a["years"], a["key"]))})
    _dump(os.path.join(d, "players.json"), {k: sorted(v, key=lambda x: (x[1], x[2]), reverse=True) for k, v in sorted(players.items())})
    return {"awards": len(index), "players": len(players)}


def motm(G, out_dir, today=None, top=50):
    """motm/index.json (leaders this season, since 1 July, and all time: overall, per competition, per club) and
    motm/players.json ({FotMob player id: total, seasons, comps, opponents, recent}) from match_award (spec §8)."""
    from datetime import date
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
    allc, seasonc = Counter(), Counter()
    comp_all, comp_now, club_all, club_now = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    players = {}
    for mid, pid, tid, value, d, home, away, season, cid in rows:
        fp = fm_p.get(pid)
        if fp is None:
            continue
        cur = (d or "") >= since
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
        p = players.setdefault(str(fp), {"total": 0, "seasons": Counter(), "comps": Counter(), "opponents": Counter(), "recent": []})
        p["total"] += 1
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
    index = {"since": since, "matches": len(rows), "leaders": {"season": lead(seasonc), "all": lead(allc)},
             "comps": {str(c): {"name": cname.get(c), "season": lead(comp_now[c], 20), "all": lead(comp_all[c], 20)} for c in sorted(comp_all)},
             "clubs": {str(t): {"season": lead(club_now[t], 10), "all": lead(club_all[t], 10)} for t in sorted(club_all) if sum(club_all[t].values()) >= 3}}
    for p in players.values():
        for k in ("seasons", "comps", "opponents"):
            p[k] = dict(sorted(p[k].items(), key=lambda x: (-x[1], x[0])))
    _dump(os.path.join(out_dir, "motm", "index.json"), index)
    _dump(os.path.join(out_dir, "motm", "players.json"), dict(sorted(players.items())))
    return {"matches": len(rows), "players": len(players)}
