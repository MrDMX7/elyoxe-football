"""The World Cup's awards since 1930 (jfjelstul/worldcup, CC-BY-SA: award_winners.csv, players.csv; fetched weekly by
graph/fetch.py into db/.cache): Golden/Silver/Bronze Ball -> best_player 1-3, Golden/Silver/Bronze Boot -> top_scorer 1-3,
Golden Glove -> best_goalkeeper, Best Young Player -> best_young, on the World Cup editions (FotMob 77). A player reaches
ours through his Wikipedia article's Wikidata item (the awards cache), else he is a player of his own."""
import csv, os, urllib.parse
from graph import awards_fetch as AF
from graph.link import edition_for

AWARD = {"Golden Ball": ("best_player", 1), "Silver Ball": ("best_player", 2), "Bronze Ball": ("best_player", 3),
         "Golden Boot": ("top_scorer", 1), "Silver Boot": ("top_scorer", 2), "Bronze Boot": ("top_scorer", 3),
         "Golden Glove": ("best_goalkeeper", 1), "Best Young Player": ("best_young", 1), "FIFA Fair Play Trophy": ("fair_play", 1)}
WORLD_CUP = 77


def load(G, reg, S):
    aw, pl = os.path.join(S.db, "fjelstul_award_winners.csv"), os.path.join(S.db, "fjelstul_players.csv")
    if not os.path.exists(aw):
        return {"skipped": "no fjelstul_award_winners.csv"}
    d = os.path.join(S.root, "graph", ".cache", "awards")
    if not os.path.exists(os.path.join(d, "items.json")) and S.s3:
        AF.restore(S, d)
    items = AF._jload(os.path.join(d, "items.json"), {})
    people = {r["player_id"]: r for r in csv.DictReader(open(pl, encoding="utf-8", newline=""))} if os.path.exists(pl) else {}
    cid = reg.mint("competition", "fotmob", WORLD_CUP)
    G.put("competition", {"cid": cid, "name": "World Cup", "name_ar": "كأس العالم"}, "fotmob")
    n = {"honours": 0, "linked": 0, "conflicts": 0}

    def player(pid_f, row):
        p = people.get(pid_f) or {}
        name = f"{row.get('given_name') or ''} {row.get('family_name') or ''}".strip()
        link = p.get("player_wikipedia_link") or ""
        title = urllib.parse.unquote(link.rsplit("/wiki/", 1)[1]) if "/wiki/" in link else None
        f = (items.get(title) or {}) if title else {}
        pid = reg.get("player", "fjelstul", pid_f)
        if pid is None and f.get("qid") and f.get("human"):
            pid = reg.get("player", "wikidata", f["qid"])
            if pid is None and f.get("tm_player"):
                pid = reg.get("player", "tm", str(f["tm_player"]))
            if pid is None:
                pid = reg.mint("player", "wikidata", f["qid"])
            pid = reg.link("player", "fjelstul", pid_f, pid) or pid
            n["linked"] += 1
        if pid is None:
            pid = reg.mint("player", "fjelstul", pid_f)
        G.put("player", {"pid": pid, "name": f.get("en") or name, "name_ar": f.get("ar"), "born": f.get("born") or p.get("birth_date") or None}, "fjelstul")
        G.xref("player", pid, "fjelstul", pid_f, "wikipedia-link" if f.get("qid") else "fjelstul-native")
        return pid

    for r in csv.DictReader(open(aw, encoding="utf-8", newline="")):
        kind = AWARD.get(r["award_name"])
        tour = r.get("tournament_id") or ""
        if not kind or not tour.startswith("WC-"):
            continue
        year = tour[3:7]
        eid = edition_for(G, reg, "fjelstul", f"{WORLD_CUP}|{year}", cid, year)
        if r.get("player_id"):
            pid, tid = player(r["player_id"], r), None
        else:
            tid = reg.get("team", "martj42", r["team_name"]) or reg.get("team", "fjelstul", r["team_id"]) or reg.mint("team", "fjelstul", r["team_id"])
            G.put("team", {"tid": tid, "name": r["team_name"], "kind": "national"}, "fjelstul")
            pid = None
        cur = G.c.execute("SELECT pid, tid FROM honour WHERE eid=? AND kind=? AND rank=?", (eid, kind[0], kind[1])).fetchall()
        if cur and (pid, tid) not in cur and r.get("shared") != "1":
            G.conflict("honour", eid, kind[0], f"{cur[0][0]}/{cur[0][1]}", "earlier", f"{pid}/{tid}", "fjelstul")
            n["conflicts"] += 1
            continue
        if G.c.execute("INSERT OR IGNORE INTO honour(eid, kind, rank, tid, pid, src) VALUES(?,?,?,?,?,?)", (eid, kind[0], kind[1], tid, pid, "fjelstul")).rowcount:
            n["honours"] += 1
    return n
