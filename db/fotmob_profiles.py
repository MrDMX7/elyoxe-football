"""Every club and every player on the site, complete (owner 2026-09-30: «كل الاندية وكل تواريخها وكل اللاعبين واحصائياتهم وكل
الخانات تكون كاملة»). FotMob already holds almost every field; the pipeline only kept part of it.

    python -m db.fotmob_profiles [--upload] [--teams-only] [--limit N]

Per club (teams?id=): every trophy with the seasons won and lost in the final/runner-up, the stadium (name, city,
coordinates, capacity, opened, surface), the league position every season, every coach, every transfer, the squad.
Per player of every squad (playerData?id=): bio (height, foot, shirt, country, market value, contract, birth date,
positions), trophies per club with seasons, the whole career season by season per competition (club, national team,
youth), market value history, injury.
Arabic names: FotMob's own Arabic site mapping (api/translationmapping?locale=ar: 60k teams and players, 579
competitions) for everything our curated names don't have yet.

Raw responses are cached on disk (db/.cache/fm/, 6 days) so a cut run resumes. Out (public):
  v1/history/fm/teams.json     {team id: card}          one file, the build reads it once
  v1/history/fm/players.json   {player id: bio}         one file, the build reads it once
  v1/history/fm/team/<id>.json coaches, ranks, transfers (the page loads it)
  v1/player/<id>/profile.json  trophies, career, market value (the page loads it)
  v1/history/fm/names_ar.json  {teams, players, comps}: FotMob Arabic names for ids we have no Arabic for
"""
import argparse, gzip, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from store import Store, S3Backend  # noqa: E402
from sources.fotmob import FotMob  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
CACHE = os.path.join(HERE, ".cache", "fm")
TTL = 6 * 86400
POS = {"goalkeeper": "حارس مرمى", "keeper": "حارس مرمى", "centre_back": "قلب دفاع", "center_back": "قلب دفاع", "right_back": "ظهير أيمن", "left_back": "ظهير أيسر",
       "right_wing_back": "ظهير أيمن", "left_wing_back": "ظهير أيسر", "defensive_midfielder": "وسط دفاعي", "central_midfielder": "وسط", "centre_midfielder": "وسط",
       "attacking_midfielder": "وسط هجومي", "right_midfielder": "وسط أيمن", "left_midfielder": "وسط أيسر", "right_winger": "جناح أيمن", "left_winger": "جناح أيسر",
       "striker": "مهاجم", "centre_forward": "مهاجم", "center_forward": "مهاجم", "defender": "مدافع", "midfielder": "وسط", "forward": "مهاجم", "coach": "مدرب"}
FM = None


def fm_get(kind, fid):
    """kind «t» (team) or «p» (player): the cached raw FotMob response, fetched when older than TTL."""
    global FM
    p = os.path.join(CACHE, kind, f"{fid}.json.gz")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < TTL:
        try:
            return json.loads(gzip.open(p).read())
        except (OSError, ValueError):
            pass
    FM = FM or FotMob()
    url = f"https://www.fotmob.com/api/data/teams?id={fid}" if kind == "t" else f"https://www.fotmob.com/api/data/playerData?id={fid}"
    for i in range(3):
        try:
            raw = FM.http.get_json(url, min_ttl=0)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with gzip.open(p + ".tmp", "wb") as f:
                f.write(json.dumps(raw, ensure_ascii=False).encode("utf-8"))
            os.replace(p + ".tmp", p)
            return raw
        except Exception as e:
            if "404" in str(e):
                return None
            time.sleep(3 * (i + 1))
    return None


def split(s):
    return [x for x in (s or "").split(",") if x]


def team_card(raw, tt):
    h, ov = raw.get("history") or {}, raw.get("overview") or {}
    tro = []
    for t in h.get("trophyList") or []:
        lid = str(t.get("leagueId") or "")
        tro.append({"lid": lid, "name": tt.get(lid) or t.get("name"), "won": int(t.get("won") or 0), "runnerup": int(t.get("runnerup") or 0),
                    "seasons": split(t.get("seasonsWon")), "lost": split(t.get("seasonsRunnerup"))})
    tro.sort(key=lambda x: (-x["won"], -x["runnerup"]))
    v = (ov.get("venue") or {})
    w, pairs = v.get("widget") or {}, dict((str(a).lower(), b) for a, b in (v.get("statPairs") or []) if a)
    loc = w.get("location") or []
    venue = {"name": w.get("name"), "city": w.get("city"), "capacity": pairs.get("capacity") or None, "opened": pairs.get("opened") or None, "surface": pairs.get("surface"),
             "lat": float(loc[0]) if len(loc) == 2 else None, "lon": float(loc[1]) if len(loc) == 2 else None} if w else None
    ranks = [[r.get("seasonName"), r.get("position"), r.get("numberOfTeams"), (r.get("stats") or {}).get("points"), (r.get("stats") or {}).get("wins"),
              (r.get("stats") or {}).get("draws"), (r.get("stats") or {}).get("loss"), r.get("templateId"), r.get("tournamentName")]
             for r in ((h.get("tables") or {}).get("ranks") or [])]
    # one row per coach per season in the league: [coach id, name, season, league id, wins, draws, losses, points per game]
    coaches = [[c.get("id"), c.get("name"), c.get("season"), c.get("leagueId"), c.get("win"), c.get("draw"), c.get("loss"), c.get("pointsPerGame")]
               for c in (h.get("coachHistory") or ov.get("coachHistory") or []) if isinstance(c, dict)]
    squad = []
    for g in ((raw.get("squad") or {}).get("squad") or []):
        for m in g.get("members") or []:
            if m.get("id") and (g.get("title") or "").lower() != "coach":
                squad.append(m["id"])
    tr = raw.get("transfers") or {}
    moves = []
    for grp in ("allTransfers",):
        for x in tr.get(grp) or []:
            fee = x.get("fee") or {}
            moves.append([(x.get("transferDate") or "")[:10], x.get("playerId"), x.get("name"), x.get("fromClubId"), x.get("fromClub"), x.get("toClubId"), x.get("toClub"),
                          fee.get("value") if isinstance(fee, dict) else fee, (fee.get("feeText") if isinstance(fee, dict) else None), x.get("onLoan")])
    return {"trophies": tro, "venue": venue, "ranks": ranks, "coaches": coaches, "squad": squad, "transfers": moves,
            "colors": (h.get("teamColors") or {}), "country": (raw.get("details") or {}).get("country")}


def player_doc(raw, tt):
    info = {i.get("translationKey") or i.get("title"): i.get("value") or {} for i in raw.get("playerInformation") or []}
    num = lambda k: (info.get(k) or {}).get("numberValue")
    pd = raw.get("positionDescription") or {}
    pk = lambda d: ((d or {}).get("key") or (d or {}).get("label") or "").lower().replace(" ", "_").replace("-", "_")
    posk = pk(pd.get("primaryPosition"))
    bio = {"h": num("height_sentencecase"), "foot": (info.get("preferred_foot") or {}).get("key"), "shirt": num("shirt"),
           "cc": next((i.get("countryCode") for i in raw.get("playerInformation") or [] if i.get("countryCode")), None),
           "mv": num("transfer_value"), "contract": ((raw.get("contractEnd") or {}).get("utcTime") or "")[:10] or None,
           "born": ((raw.get("birthDate") or {}).get("utcTime") or "")[:10] or None, "pos": POS.get(posk, (pd.get("primaryPosition") or {}).get("label")),
           "pos2": [POS.get(pk(p.get("strPos")), (p.get("strPos") or {}).get("label")) for p in pd.get("positions") or [] if not p.get("isMainPosition")][:3],
           "team": (raw.get("primaryTeam") or {}).get("teamId"), "loan": bool((raw.get("primaryTeam") or {}).get("onLoan"))}
    tro = []
    for t in ((raw.get("trophies") or {}).get("playerTrophies") or []):
        for tn in t.get("tournaments") or []:
            tro.append([t.get("teamId"), t.get("teamName"), str(tn.get("leagueId")), tt.get(str(tn.get("leagueId"))) or tn.get("leagueName"), tn.get("seasonsWon") or [], tn.get("seasonsRunnerUp") or []])
    career = {}
    for kind, v in (((raw.get("careerHistory") or {}).get("careerItems")) or {}).items():
        teams = [[e.get("teamId"), e.get("team"), (e.get("startDate") or "")[:10], (e.get("endDate") or "")[:10] or None, e.get("appearances"), e.get("goals"), e.get("assists"), e.get("transferType")]
                 for e in v.get("teamEntries") or []]
        seasons = [[s.get("seasonName"), s.get("teamId"), s.get("team"), s.get("appearances"), s.get("goals"), s.get("assists"), ((s.get("rating") or {}).get("rating")),
                    [[str(t.get("leagueId")), tt.get(str(t.get("leagueId"))) or t.get("leagueName"), t.get("appearances"), t.get("goals"), t.get("assists"), ((t.get("rating") or {}).get("rating"))]
                     for t in s.get("tournamentStats") or [] if not t.get("isFriendly")]]
                   for s in v.get("seasonEntries") or []]
        career[kind] = {"teams": teams, "seasons": seasons}
    mv = [[(x.get("date") or "")[:10], x.get("value")] for x in ((raw.get("marketValues") or {}).get("values") or [])]
    if len(mv) > 40:                       # a point per quarter is plenty for the chart
        keep, last = [], ""
        for d, val in mv:
            q = d[:4] + str((int(d[5:7]) - 1) // 3)
            if q != last:
                keep.append([d, val]); last = q
        mv = keep
    inj = raw.get("injuryInformation")
    return bio, {"trophies": tro, "career": career, "mv": mv, "injury": inj, "traits": raw.get("traits")}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); ap.add_argument("--teams-only", action="store_true"); ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    store = Store(S3Backend(BUCKET))
    tm = FotMob().http.get_json("https://www.fotmob.com/api/translationmapping?locale=ar", min_ttl=3600)
    tt, parts = tm.get("TournamentTemplates") or {}, tm.get("Participants") or {}
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    ids = [int(k) for k, t in teams.items() if t.get("name") and not any(c.isdigit() for c in (t.get("name") or "")[:2]) and not (t.get("name") or "").startswith("Winner")]
    if a.limit:
        ids = ids[:a.limit]
    t0 = time.time()
    with ThreadPoolExecutor(4) as ex:
        raws = dict(zip(ids, ex.map(lambda i: fm_get("t", i), ids)))
    cards, players = {}, set()
    for i, raw in raws.items():
        if not raw:
            continue
        c = team_card(raw, tt)
        cards[i] = c; players.update(c["squad"])
    print(f"{len(cards)} clubs fetched ({round(time.time() - t0)}s); {len(players)} squad players")
    bios, profiles = {}, {}
    if not a.teams_only:
        pl = sorted(players)
        t0 = time.time()
        with ThreadPoolExecutor(4) as ex:
            for pid, raw in zip(pl, ex.map(lambda i: fm_get("p", i), pl)):
                if raw:
                    bios[pid], profiles[pid] = player_doc(raw, tt)
        print(f"{len(bios)} players fetched ({round(time.time() - t0)}s)")
    names = {"teams": {str(i): parts[str(i)] for i in cards if str(i) in parts}, "players": {str(p): parts[str(p)] for p in bios if str(p) in parts},
             "comps": tt, "countries": tm.get("CountryCodes") or {}}
    print(f"Arabic from FotMob: {len(names['teams'])} clubs, {len(names['players'])} players, {len(tt)} competitions")
    if a.upload:
        compact = {i: {k: c[k] for k in ("trophies", "venue", "colors", "country")} | {"ranks_n": len(c["ranks"]), "coaches_n": len(c["coaches"])} for i, c in cards.items()}
        store.put_json("history/fm/teams.json", {"generated": date.today().isoformat(), "teams": compact, "source": "FotMob"}, cache="warm")
        for i, c in cards.items():
            store.put_json(f"history/fm/team/{i}.json", {"team": i, "ranks": c["ranks"], "coaches": c["coaches"], "transfers": c["transfers"], "source": "FotMob"}, cache="warm")
        if bios:
            store.put_json("history/fm/players.json", {"generated": date.today().isoformat(), "players": bios, "source": "FotMob"}, cache="warm")
            with ThreadPoolExecutor(8) as ex:
                list(ex.map(lambda kv: store.put_json(f"player/{kv[0]}/profile.json", dict(kv[1], player=kv[0], source="FotMob"), cache="warm"), profiles.items()))
        store.put_json("history/fm/names_ar.json", dict(names, generated=date.today().isoformat(), source="FotMob Arabic site mapping"), cache="warm")
        print("uploaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
