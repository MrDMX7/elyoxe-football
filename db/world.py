"""The world encyclopedia's data (owner 2026-09-30: «ابغي الموقع يشمل كل الاندية وكل تواريخها وكل اللاعبين»): every club of every
domestic league FotMob covers (~300 leagues in 94 countries), each with its full card, and every player of their squads.
The site's hourly build can't carry tens of thousands of pages, so these are read by one page template in the browser
(/db/), like the app the owner approved; clubs and players the live site already has keep their /t/ and /p/ pages.

    python -m db.world [--upload] [--players] [--only-country ENG]

Steps: api/data/allLeagues -> each domestic league (no cups, no women's) -> api/data/leagues?id= for its clubs -> each
club's teams?id= (shared cache with db/fotmob_profiles.py) -> with --players, each squad player's playerData.
Out (public):
  v1/world/club/<id>.json      the card: country, league, position, trophies, stadium, squad (id, name, number, role),
                               coaches, league position by season, transfers
  v1/world/index.json          search: clubs [id, name ar|en, country code, league id] and players [id, name, club id]
  v1/world/leagues.json        every league: id, names, country, club ids
  (players: v1/player/<id>/profile.json + bios, as db/fotmob_profiles.py writes them; v1/world/bios.json [name, born, club]
   for db/eafc.py's matching)
"""
import argparse, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from store import Store, S3Backend  # noqa: E402
from sources.fotmob import FotMob  # noqa: E402
from db.fotmob_profiles import fm_get, team_card, player_doc, BUCKET  # noqa: E402

SKIP = re.compile(r"women|femin|cup|copa|pokal|coupe|coppa|taça|beker|shield|super ?cup|supercopa|trophy|playoff|play-off|qualification|u1\d|u2\d|youth|reserve", re.I)


def league_teams(lid, http):
    p = os.path.join(HERE, ".cache", "fm", "l", f"{lid}.json")
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 6 * 86400:
        return json.load(open(p, encoding="utf-8"))
    try:
        raw = http.get_json(f"https://www.fotmob.com/api/data/leagues?id={lid}", min_ttl=0)
    except Exception:
        return []
    if not isinstance(raw, dict):          # FotMob answers «null» for a few leagues between seasons
        return []
    out = []
    for t in (raw.get("table") or []):
        if not isinstance(t, dict):
            continue
        for tb in ((t.get("data") or {}).get("table") or {}).values() if isinstance((t.get("data") or {}).get("table"), dict) else []:
            for r in tb or []:
                if isinstance(r, dict) and r.get("id"):
                    out.append([r["id"], r.get("name"), r.get("idx")])
        for grp in [g for g in ((t.get("data") or {}).get("tables") or []) if isinstance(g, dict)]:
            for tb in ((grp.get("table") or {}).values() if isinstance(grp.get("table"), dict) else []):
                for r in tb or []:
                    if isinstance(r, dict) and r.get("id"):
                        out.append([r["id"], r.get("name"), r.get("idx")])
    seen, uniq = set(), []
    for r in out:
        if r[0] not in seen:
            seen.add(r[0]); uniq.append(r)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(uniq, open(p, "w", encoding="utf-8", newline="\n"), ensure_ascii=False)
    return uniq


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); ap.add_argument("--players", action="store_true"); ap.add_argument("--only-country")
    a = ap.parse_args(argv)
    fm = FotMob(); http = fm.http
    al = http.get_json("https://www.fotmob.com/api/data/allLeagues", min_ttl=3600)
    tm = http.get_json("https://www.fotmob.com/api/translationmapping?locale=ar", min_ttl=3600)
    tt, parts, cc_ar = tm.get("TournamentTemplates") or {}, tm.get("Participants") or {}, tm.get("CountryCodes") or {}
    leagues = [(c["ccode"], l) for c in al.get("countries") or [] for l in c.get("leagues") or [] if not SKIP.search(l.get("name") or "")]
    if a.only_country:
        leagues = [x for x in leagues if x[0] == a.only_country]
    print(len(leagues), "domestic leagues")
    with ThreadPoolExecutor(4) as ex:
        lt = list(ex.map(lambda x: league_teams(x[1]["id"], http), leagues))
    club_league, lg_out = {}, []
    for (cc, l), teams in zip(leagues, lt):
        lg_out.append({"id": l["id"], "name": l.get("name"), "name_ar": tt.get(str(l["id"])), "cc": cc, "country_ar": cc_ar.get(cc), "clubs": [t[0] for t in teams]})
        for t in teams:
            club_league.setdefault(t[0], (l["id"], cc, t[2]))
    clubs = sorted(club_league)
    print(len(clubs), "clubs")
    t0 = time.time()
    with ThreadPoolExecutor(4) as ex:
        raws = dict(zip(clubs, ex.map(lambda i: fm_get("t", i), clubs)))
    cards, squads = {}, {}
    for cid, raw in raws.items():
        if not raw:
            continue
        try:
            c = team_card(raw, tt)
        except Exception as e:
            print("skip club", cid, e); continue
        lid, cc, pos = club_league[cid]
        members = []
        for g in ((raw.get("squad") or {}).get("squad") or []):
            for m in g.get("members") or []:
                if m.get("id"):
                    members.append([m["id"], parts.get(str(m["id"])) or m.get("name"), m.get("shirtNumber"), (g.get("title") or "").lower(), m.get("ccode")])
        cards[cid] = {"id": cid, "name": (raw.get("details") or {}).get("name"), "name_ar": parts.get(str(cid)), "cc": cc, "country_ar": cc_ar.get(cc), "league": lid,
                      "league_ar": tt.get(str(lid)), "position": pos, "trophies": c["trophies"], "venue": c["venue"], "coaches": c["coaches"], "ranks": c["ranks"],
                      "transfers": c["transfers"][:150], "squad": members, "colors": c["colors"]}
        squads[cid] = [m[0] for m in members if m[3] != "coach"]
    print(f"{len(cards)} club cards ({round(time.time() - t0)}s)")
    bios = {}
    if a.players:
        pl = sorted({p for v in squads.values() for p in v})
        print(len(pl), "players to fetch")
        t0 = time.time()
        profiles = {}
        with ThreadPoolExecutor(int(os.environ.get('FM_THREADS', '12'))) as ex:
            for pid, raw in zip(pl, ex.map(lambda i: fm_get("p", i), pl)):
                if raw:
                    try:
                        bios[pid], profiles[pid] = player_doc(raw, tt)
                    except Exception as e:
                        print("skip player", pid, e)
        print(f"{len(bios)} players ({round(time.time() - t0)}s)")
    idx = {"generated": date.today().isoformat(),
           "clubs": [[c["id"], c["name_ar"] or c["name"], c["name"], c["cc"], c["league"]] for c in cards.values()],
           "players": [[pid, parts.get(str(pid)) or b.get("name"), b.get("name"), b.get("team")] for pid, b in bios.items()]}
    if a.upload:
        store = Store(S3Backend(BUCKET))
        with ThreadPoolExecutor(8) as ex:
            list(ex.map(lambda c: store.put_json(f"world/club/{c['id']}.json", c, cache="warm"), cards.values()))
        store.put_json("world/leagues.json", {"generated": date.today().isoformat(), "leagues": lg_out}, cache="warm")
        store.put_json("world/index.json", idx, cache="warm")
        if bios:
            store.put_json("world/bios.json", {"generated": date.today().isoformat(), "players": {str(k): [b.get("name"), b.get("born"), b.get("team")] for k, b in bios.items()}}, cache="warm")
            with ThreadPoolExecutor(8) as ex:
                list(ex.map(lambda kv: store.put_json(f"player/{kv[0]}/profile.json", dict(kv[1], player=kv[0], bio=bios[kv[0]], source="FotMob"), cache="warm"), profiles.items()))
        print("uploaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
