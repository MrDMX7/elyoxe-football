"""Transfer history from the Transfermarkt datasets (github.com/dcaribou/transfermarkt-datasets, CC0, refreshed weekly on
a public R2 bucket): every move with its fee and the player's market value at the time, since the 1990s. Owner 2026-09-30:
history and records from open datasets, not FotMob.

    python -m history.transfermarkt [--upload]

Matching, never by name alone: a Transfermarkt player is one of ours when the folded name AND the date of birth agree
(FotMob dates: state/dobs.json + squads). A Transfermarkt club becomes a FotMob team by vote: the current club of every
matched player, kept when at least 3 players and 70% of them agree.

Out (public, v1/history/): transfers.json {players: {fotmob id: [moves]}, clubs: {fotmob team id: {in, out}}}.
A move is [date, season, from name, from team id|null, to name, to team id|null, fee EUR|null (0 = free), market value|null].
"""
import argparse, csv, gzip, io, json, os, re, sys, unicodedata, urllib.request
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from store import Store, S3Backend  # noqa: E402

R2 = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/"
BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")


def fold(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]+", " ", s).strip()


def table(name):
    raw = urllib.request.urlopen(urllib.request.Request(R2 + name + ".csv.gz", headers={"User-Agent": "elyoxe-tifo/0.1"}), timeout=300).read()
    return list(csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(raw)), encoding="utf-8")))


def money(v):
    try:
        return None if v in ("", None) else int(float(v))
    except ValueError:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); a = ap.parse_args(argv)
    store = Store(S3Backend(BUCKET))
    names = json.load(open(os.path.join(os.path.dirname(HERE), "names", "players_ar.json"), encoding="utf-8"))
    dobs, team_of = dict(store.get_state("dobs.json", {}) or {}), {}
    for tid, groups in (store.get_state("squads.json", {}) or {}).items():
        for g in groups or []:
            for pl in g.get("players") or []:
                if pl.get("dob"):
                    dobs[str(pl["id"])] = pl["dob"][:10]
                team_of[str(pl["id"])] = int(tid)
    # the big leagues have no squad files: their player tables say each player's team
    import config
    for cid in config.settings().get("player_stats_comps", []):
        try:
            for pid, v in ((store.get_json(f"comp/{cid}/players.json") or {}).get("players") or {}).items():
                if v.get("team"):
                    team_of.setdefault(str(pid), int(v["team"]))
        except ValueError:
            pass
    ours = defaultdict(list)                      # (folded name, dob) -> fotmob ids
    for pid, v in names.items():
        if dobs.get(pid):
            ours[(fold(v.get("latin")), dobs[pid])].append(pid)
    print(len(ours), "of our players have a name and a birth date")

    tmp = table("players")
    tm2fm = {}
    for p in tmp:
        dob = (p.get("date_of_birth") or "")[:10]
        if not dob:
            continue
        for nm in {fold(p["name"]), fold(p["first_name"] + " " + p["last_name"])}:
            hit = ours.get((nm, dob))
            if hit and len(hit) == 1:
                tm2fm[p["player_id"]] = hit[0]; break
    print(len(tm2fm), "Transfermarkt players matched (name + birth date)")

    # Transfermarkt club -> FotMob team, by the vote of matched players' current clubs
    votes = defaultdict(Counter)
    for p in tmp:
        fm = tm2fm.get(p["player_id"])
        if fm and team_of.get(fm) and p.get("current_club_id"):
            votes[p["current_club_id"]][team_of[fm]] += 1
    club = {}
    for c, cnt in votes.items():
        (t, n), tot = cnt.most_common(1)[0], sum(cnt.values())
        if n >= 3 and n / tot >= 0.7:
            club[c] = t
    # the league clubs Transfermarkt describes (Europe's big five, Saudi, MLS, Argentina, Brazil): by name within the same league
    TM2FM = {"GB1": 47, "ES1": 87, "IT1": 55, "L1": 54, "FR1": 53, "SA1": 536, "MLS1": 130, "ARG1": 112, "BRA1": 268}
    STOP = {"fc", "cf", "afc", "club", "football", "de", "sc", "ac", "as", "ss", "sv", "the", "calcio", "cd", "ud", "sd", "rc", "real", "sporting",
            "atletico", "athletic", "united", "city", "saudi", "al", "cr", "ec", "se", "esporte", "clube", "futebol", "regatas", "ca", "club", "u"}
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    SAME = {"munchen": "munich", "koln": "cologne", "internazionale": "inter", "milano": "milan"}
    toks = lambda n: {SAME.get(w, w) for w in fold(n).split()}
    by_comp = defaultdict(list)
    for tid, t in teams.items():
        for c in t.get("comps") or []:
            by_comp[c].append((int(tid), toks(t.get("name")), toks(t.get("name")) - STOP))
    named = 0
    for c in table("clubs"):
        cand = by_comp.get(TM2FM.get(c["domestic_competition_id"]), [])
        if not cand or c["club_id"] in club:
            continue
        mine, core = toks(c["name"]), toks(c["name"]) - STOP
        def score(x):
            full, cr = x[1], x[2]
            if cr and core:
                return len(cr & core) / min(len(cr), len(core))
            return len(full & mine) / max(1, min(len(full), len(mine)))
        # tie between «Real Madrid» and «Atlético de Madrid» (or the two Manchesters) on the core words: the full names decide
        jac = lambda x: len(x[1] & mine) / max(1, len(x[1] | mine))
        ranked = sorted(cand, key=lambda x: (score(x), jac(x)), reverse=True)
        if score(ranked[0]) >= 0.99 and (len(ranked) == 1 or score(ranked[1]) < 0.99 or jac(ranked[0]) >= jac(ranked[1]) + 0.15):
            club[c["club_id"]] = ranked[0][0]; named += 1
    print(named, "more clubs mapped by name within their league;", len(club), "in all")
    pass  # (counted above)
    # second pass for players FotMob gave no birth date: same folded name AND the same (mapped) current club
    by_team = defaultdict(list)
    for pid, v in names.items():
        if team_of.get(pid):
            by_team[(fold(v.get("latin")), team_of[pid])].append(pid)
    taken, more = set(tm2fm.values()), 0
    for p in tmp:
        if p["player_id"] in tm2fm or club.get(p.get("current_club_id")) is None:
            continue
        hit = by_team.get((fold(p["name"]), club[p["current_club_id"]]))
        if hit and len(hit) == 1 and hit[0] not in taken:
            tm2fm[p["player_id"]] = hit[0]; taken.add(hit[0]); more += 1
    print(more, "more matched by name + current club")

    json.dump(club, open(os.path.join(HERE, ".cache", "tm_clubmap.json"), "w", encoding="utf-8", newline="
"))   # db/clubs.py links through it
    players, clubs = defaultdict(list), defaultdict(lambda: {"in": [], "out": []})
    for t in table("transfers"):
        fee, mv = money(t["transfer_fee"]), money(t["market_value_in_eur"])
        f_id, t_id = club.get(t["from_club_id"]), club.get(t["to_club_id"])
        move = [t["transfer_date"][:10], t["transfer_season"], t["from_club_name"], f_id, t["to_club_name"], t_id, fee, mv]
        fm = tm2fm.get(t["player_id"])
        if fm:
            players[fm].append(move)
        if fee:                                   # club records: paid transfers only
            rec = [t["transfer_date"][:10], fm, t["player_name"], fee]
            if t_id:
                clubs[t_id]["in"].append(rec + [t["from_club_name"], f_id])
            if f_id:
                clubs[f_id]["out"].append(rec + [t["to_club_name"], t_id])
    for v in players.values():
        v.sort(key=lambda m: m[0])
    out_clubs = {}
    for tid, v in clubs.items():
        out_clubs[str(tid)] = {k: sorted(v[k], key=lambda r: -r[3])[:10] for k in ("in", "out")}
    doc = {"source": "Transfermarkt via github.com/dcaribou/transfermarkt-datasets (CC0)", "players": players, "clubs": out_clubs,
           "matched": {"players": len(tm2fm), "clubs": len(club)}, "note": "move: [date, season, from, from_team, to, to_team, fee_eur, market_value_eur]; fee 0 = free, null = unknown"}
    path = os.path.join(HERE, ".cache", "transfers.json"); os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(doc, open(path, "w", encoding="utf-8", newline="\n"), separators=(",", ":"))
    print(f"{len(players)} players with moves, {len(out_clubs)} clubs with records; {os.path.getsize(path) // 1024} KB")
    if a.upload:
        store.put_json("history/transfers.json", doc, cache="static")
        print("uploaded v1/history/transfers.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
