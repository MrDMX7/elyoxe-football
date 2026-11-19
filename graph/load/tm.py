"""Transfermarkt. salimt/football-datasets (db/.cache/tm/): bios, season × competition × club lines, injuries, for the
players db/tmdata.py and history/transfermarkt.py matched to FotMob (birth date + name rules). dcaribou games and events
(db/.cache/tm_games.csv.gz, 2012+): a game already in the graph becomes its xref, the rest are new matches; each side's
manager is recorded for the match as a coach of his own (a name alone never links; phase 5 links by club and dates)."""
import csv, gzip, os, re, unicodedata
from graph.link import MatchIndex, twin


def fold(s):
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()).strip()


def rows(path):
    if not os.path.exists(path):
        return
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def season(s):
    """«15/16» -> «2015/2016», «2015» (dcaribou: the start year) -> «2015/2016»."""
    s = str(s or "").strip()
    m = re.fullmatch(r"(\d{2})/(\d{2})", s)
    if m:
        a = int(m.group(1))
        y = (1900 if a > 50 else 2000) + a
        return f"{y}/{y + 1}"
    return f"{s}/{int(s) + 1}" if s.isdigit() else (s or None)


def _i(v):
    try:
        return int(float(str(v).replace(",", ".").strip())) if str(v).strip() else None
    except ValueError:
        return None


def load(G, reg, S):
    n = {"players_linked": 0, "seasons": 0, "injuries": 0, "games_linked": 0, "games_new": 0, "coaches": 0}
    pmap = {str(k): str(v) for k, v in (S.read(os.path.join(S.hist, "tm_playermap.json")) or {}).items()}
    for fid, tmid in ((S.published("history/tm/index.json") or {}).get("players") or {}).items():
        pmap.setdefault(str(tmid), str(fid))
    for tmid, fid in sorted(pmap.items()):
        pid = reg.get("player", "fotmob", int(fid)) if fid.isdigit() else None
        pid = reg.link("player", "tm", tmid, pid) if pid else None
        if pid:
            G.xref("player", pid, "tm", tmid, "birthdate+name")
            n["players_linked"] += 1
    cmap = {str(k): v for k, v in (S.read(os.path.join(S.hist, "tm_clubmap.json")) or {}).items()}
    for tmc, fid in sorted(cmap.items()):
        tid = reg.link("team", "tm", tmc, reg.mint("team", "fotmob", int(fid)))
        if tid is not None:
            G.xref("team", tid, "tm", tmc, "transfers-clubmap")

    def team(tmc, name=None):
        tid = reg.get("team", "tm", str(tmc))
        if tid is None:
            tid = reg.mint("team", "tm", str(tmc))
            G.put("team", {"tid": tid, "name": name}, "tm")
            G.xref("team", tid, "tm", tmc, "tm-native")
        return tid

    for r in rows(os.path.join(S.db, "tm", "player_profiles.csv")):
        pid = reg.get("player", "tm", r["player_id"])
        if not pid:
            continue
        cit = [c.strip() for c in re.split(r"\s{2,}", r.get("citizenship") or "") if c.strip()]
        h = r.get("height") or ""
        G.put("player", {"pid": pid, "name_native": r.get("name_in_home_country") or None, "born": (r.get("date_of_birth") or "")[:10] or None,
                         "birthplace": r.get("place_of_birth") or None, "nationality2": cit[1] if len(cit) > 1 else None,
                         "height": _i(h.replace(",", "")) if h else None, "foot": r.get("foot") or None, "died": r.get("date_of_death") or None}, "tm")
    for r in rows(os.path.join(S.db, "tm", "player_performances.csv")):
        pid = reg.get("player", "tm", r["player_id"])
        if not pid:
            continue
        G.many("player_season", [{"pid": pid, "season": season(r.get("season_name")), "comp": r.get("competition_name") or r.get("competition_id"),
                                  "cid": reg.get("competition", "tm", r.get("competition_id")), "tid": team(r["team_id"], r.get("team_name")) if r.get("team_id") else None,
                                  "apps": _i(r.get("nb_on_pitch")), "minutes": _i(r.get("minutes_played")), "goals": _i(r.get("goals")), "assists": _i(r.get("assists")),
                                  "yellow": _i(r.get("yellow_cards")), "red": (_i(r.get("second_yellow_cards")) or 0) + (_i(r.get("direct_red_cards")) or 0),
                                  "clean_sheets": _i(r.get("clean_sheets")), "conceded": _i(r.get("goals_conceded"))}], "tm")
        n["seasons"] += 1
    for r in rows(os.path.join(S.db, "tm", "player_injuries.csv")):
        pid = reg.get("player", "tm", r["player_id"])
        if pid:
            G.many("injury", [{"pid": pid, "season": season(r.get("season_name")), "kind": r.get("injury_reason"), "start": r.get("from_date") or None,
                               "end": r.get("end_date") or None, "days": _i(r.get("days_missed")), "games": _i(r.get("games_missed"))}], "tm")
            n["injuries"] += 1
    idx = MatchIndex(G)
    for r in rows(os.path.join(S.db, "tm_games.csv.gz")):
        if not r.get("home_club_goals") or not r.get("date"):
            continue
        th, ta, hs, as_ = team(r["home_club_id"], r.get("home_club_name")), team(r["away_club_id"], r.get("away_club_name")), _i(r["home_club_goals"]), _i(r["away_club_goals"])
        mid = twin(G, idx, r["date"], th, ta, hs, as_, "tm")
        if mid:
            mid = reg.link("match", "tm", r["game_id"], mid)
        if mid:
            G.xref("match", mid, "tm", r["game_id"], "date+teams")
            n["games_linked"] += 1
        else:
            cid = reg.get("competition", "tm", r["competition_id"]) or reg.mint("competition", "tm", r["competition_id"])
            G.put("competition", {"cid": cid, "name": r["competition_id"]}, "tm")
            eid = reg.get("edition", "tm", f"{r['competition_id']}|{r['season']}") or reg.mint("edition", "tm", f"{r['competition_id']}|{r['season']}")
            G.put("edition", {"eid": eid, "cid": cid, "season": season(r["season"])}, "tm")
            mid = reg.mint("match", "tm", r["game_id"])
            G.put("match", {"mid": mid, "eid": eid, "round": r.get("round"), "date": r["date"], "home": th, "away": ta, "hs": hs, "as_": as_,
                            "status": "finished", "attendance": _i(r.get("attendance"))}, "tm")
            G.xref("match", mid, "tm", r["game_id"], "tm-native")
            idx.add(mid, r["date"], th, ta)
            n["games_new"] += 1
        for side, col in (("h", "home_club_manager_name"), ("a", "away_club_manager_name")):
            nm = (r.get(col) or "").strip()
            if not nm:
                continue
            # a name alone never links (spec §3.3): phase 5 links these to FotMob's coaches by club and dates
            kid = reg.get("coach", "tm-name", fold(nm)) or reg.mint("coach", "tm-name", fold(nm))
            G.put("coach", {"kid": kid, "name": nm}, "tm")
            G.c.execute("INSERT OR IGNORE INTO match_coach VALUES(?,?,?,?)", (mid, side, kid, "tm"))
            n["coaches"] += 1
    return n
