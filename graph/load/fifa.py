"""FIFA's own match records (graph/fifa_fetch.py): the World Cup and its qualifiers of every confederation, the men's Olympic
tournament, the Confederations Cup, the Club World Cup and the Intercontinental Cup of 2024 on. The graph's copy of a game
takes FIFA's squads, goals, cards, substitutions, coaches, referee, ground and attendance; a game no source held is FIFA's
own. The rules are UEFA's (graph/load/uefa.py: `apply`); this file reads FIFA's pack into the rows that takes.

  * an Olympic side is its country's under-23s from 1992 («Brazil U23», the one FotMob holds where it holds one) and its
    Olympic team of 1952-1988 («Hungary Olympic»); until 1948 it is the national team;
  * a qualifier no source held goes to the World Cup qualification of its calendar year, as martj42 files them;
  * a 0-0 FIFA recorded with squads and nothing else is no score: the graph's copy keeps its own;
  * a shoot-out's kicks are no goals; a goal or a card of a man in neither squad is left out.
research/tifo-sources-2026-11-24.md."""
import gzip, json, os, re
from collections import defaultdict
from graph.countries import canon
from graph.load import uefa
from graph.load.teams import squash

FILE = "fifa.json.gz"
SRC = "fifa"
# our label -> the registry keys of the competitions its games may sit in, the first for a game of our own
COMP = {"world-cup": [("fotmob", "77")],
        "world-cup-qualifiers": [("martj42", "FIFA World Cup qualification"), ("fotmob", "10199"), ("fotmob", "10197"), ("fotmob", "10196"),
                                 ("fotmob", "10198"), ("fotmob", "10195")],
        "confederations-cup": [("fotmob", "43")], "olympics": [("fotmob", "66"), ("martj42", "Olympic Games")],
        "club-world-cup": [("fotmob", "78")], "intercontinental": [("fotmob", "10703")]}
MEN, NATIONAL, OLYMPIC = 1, 1, 5                 # FIFA's Gender, TeamType and AgeType
FINISHED, PENALTIES, EXTRA = 0, 2, (3, 8)        # MatchStatus; ResultType (8 is a golden goal)
STAGE = {"final": "FINAL", "gold medal match": "FINAL", "semi-final": "SEMIFINAL", "semifinals": "SEMIFINAL", "quarter-final": "QUARTER_FINALS",
         "quarterfinals": "QUARTER_FINALS", "round of 16": "ROUND_OF_16", "round of 32": "ROUND_OF_32", "match for third place": "THIRD_PLACE_PLAY_OFF",
         "play-off for third place": "THIRD_PLACE_PLAY_OFF", "bronze final": "THIRD_PLACE_PLAY_OFF", "bronze medal match": "THIRD_PLACE_PLAY_OFF",
         "3rd place": "THIRD_PLACE_PLAY_OFF"}
POS = {0: "GOALKEEPER", 1: "DEFENDER", 2: "MIDFIELDER", 3: "FORWARD"}
# FIFA's Period: 3 and 5 the halves, 7 and 9 extra time's, the even numbers the breaks after each, 11 the shoot-out
PERIOD = {3: "FIRST_HALF", 4: "SECOND_HALF", 5: "SECOND_HALF", 6: "EXTRA_TIME_FIRST_HALF", 7: "EXTRA_TIME_FIRST_HALF", 8: "EXTRA_TIME_SECOND_HALF",
          9: "EXTRA_TIME_SECOND_HALF", 10: "EXTRA_TIME_SECOND_HALF", 11: "EXTRA_TIME_SECOND_HALF"}
SHOOT_OUT = 11
GOAL = {1: "PENALTY", 2: None, 3: "OWN"}
CARD = {1: "YELLOW_CARD", 2: "RED_CARD", 3: "RED_YELLOW_CARD"}
YEAR = re.compile(r"(?:18|19|20)\d\d")


def pretty(s):
    """«Sergio ROMERO» is Sergio Romero, «Gary O'NEILL» Gary O'Neill"""
    cap = lambda w: re.sub(r"[^\W\d_]+", lambda m: m.group().capitalize(), w) if len(w) > 1 and w.isupper() else w
    return " ".join(cap(w) for w in str(s).split()) if s else None


def minute(v):
    """«45'+2'» is the 45th minute and two added"""
    m = re.match(r"\s*(\d+)'?\s*(?:\+\s*(\d+))?", str(v or ""))
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (None, 0)


def day(r):
    return r.get("local") or r.get("date")


def label(r):
    return "intercontinental" if r["comp"] == "club-world-cup" and "intercontinental" in str(r.get("season_name") or "").lower() else r["comp"]


def year(r):
    """the year a tournament is named for: the Club World Cup «2020» was played in February 2021"""
    m = YEAR.search(str(r.get("season_name") or ""))
    return m.group() if m else day(r)[:4]


def era(r, t):
    """an Olympic side's: 2 the under-23s (1992 on), 1 the Olympic team (1952-1988), 0 the national team, as is every other side"""
    y = int(year(r))
    return 0 if r["comp"] != "olympics" or t.get("age") != OLYMPIC or y < 1952 else 2 if y >= 1992 else 1


def sides(G, reg, rows):
    """(FIFA's team id, era) -> the team as the rows carry it. An Olympic side of 1992 on is «<country> U23», tied to the one
    the graph holds of that country (FotMob's before another's); of 1952-1988 «<country> Olympic», a team of its own, one
    for a country whatever ids FIFA gave it (Egypt and the United Arab Republic)."""
    q = lambda s: G.c.execute(s).fetchall()
    fm = {t for (t,) in q("SELECT tifo_id FROM xref WHERE type='team' AND source='fotmob'")}
    senior, young = defaultdict(set), defaultdict(list)
    for tid, name, kind in q("SELECT tid, name, kind FROM team WHERE name IS NOT NULL AND (kind='national' OR name LIKE '% U23')"):
        if name.endswith(" U23"):
            for k in {canon(name[:-4]), squash(name)} - {None}:
                young[k].append((kind != "national", tid not in fm, tid))
        elif tid in fm and canon(name):
            senior[canon(name)].add(name)
    out = {}
    for r in rows:
        for s in ("home", "away"):
            t, at = r[s], era(r, r[s])
            if (t["id"], at) in out:
                continue
            e = {"id": str(t["id"]), "name": t["name"], "country": t.get("country"), "national": t.get("type") == NATIONAL}
            if at:
                land = canon(t.get("country"))
                land = land if len(senior.get(land) or ()) == 1 else canon(t["name"])      # «Egypt» of the code UAR
                one = next(iter(senior[land])) if len(senior.get(land) or ()) == 1 else None
                e["id"] = f"{one or t['id']}|{'u' if at == 2 else 'o'}"
                e["name"] = f"{one or t['name']} {'U23' if at == 2 else 'Olympic'}"
                hit = sorted(young.get(land) or young.get(squash(e["name"])) or ()) if at == 2 else ()
                if hit and reg.get("team", SRC, e["id"]) is None:
                    reg.link("team", SRC, e["id"], hit[0][2])
            out[(t["id"], at)] = e
    return out


def row(r, people, team):
    """a game of FIFA's pack as graph/load/uefa.py's `apply` reads one"""
    at = {r[s]["id"]: era(r, r[s]) for s in ("home", "away")}
    side = lambda i: team[(i, at[i])]["id"] if i in at else None
    pens, res, lb = r.get("pens") or [None, None], r.get("result"), label(r)
    sc = {"total": {"home": r["home"]["score"], "away": r["away"]["score"]}}
    if res == PENALTIES and None not in pens:
        sc["penalty"] = {"home": pens[0], "away": pens[1]}
    stage = str(r.get("stage_name") or "").lower().strip()
    ref = next((o for o in r.get("officials") or [] if o.get("type") == 1 and o.get("id") and o.get("name")), None)
    att = str(r.get("attendance") or "")
    squads, events, of = [], [], {}
    for sq in r.get("lineups") or []:
        men = []
        for p in sq.get("men") or []:
            if p.get("id") and p.get("name"):
                more = people.get(str(p["id"])) or {}
                of[p["id"]] = side(sq.get("team"))
                men.append({"id": str(p["id"]), "name": pretty(p["name"]), "ar": more.get("ar"), "born": more.get("born"), "country": more.get("country"),
                            "height": more.get("height"), "pos": POS.get(p.get("pos")), "no": p.get("no"), "start": bool(p.get("start")),
                            "captain": bool(p.get("captain"))})
        squads.append({"team": side(sq.get("team")), "men": men,
                       "coaches": [{"id": str(c["id"]), "name": pretty(c["name"]), "country": c.get("country"), "role": "COACH"}
                                   for c in sq.get("coaches") or [] if c.get("role") == 0 and c.get("id") and c.get("name")]})
    who = lambda i: {"id": str(i), "team": of[i]} if i in of else None
    # a record with its squads and not one goal, card or change, 0-0 with a 0-0 shoot-out (the Club World Cup of 2019): no score at all
    blank = bool(squads) and (r["home"]["score"], r["away"]["score"], res) == (0, 0, 1) and pens == [0, 0] and not any(
        sq.get(k) for sq in r["lineups"] for k in ("goals", "cards", "subs"))

    def event(kind, sub, e, a, b=None):
        mi, ad = minute(e.get("minute"))
        phase = PERIOD.get(e.get("period")) or ("FIRST_HALF" if mi is not None and mi <= 45 else "SECOND_HALF")
        if a:
            events.append({"type": kind, "sub": sub, "phase": phase, "minute": mi, "added": ad, "a": a, "b": b})

    for sq in r.get("lineups") or []:
        for g in sq.get("goals") or []:
            if g.get("period") != SHOOT_OUT and g.get("type") in GOAL:
                event("GOAL", GOAL[g["type"]], g, who(g.get("id")))
        for c in sq.get("cards") or []:
            if c.get("card") in CARD:
                event(CARD[c["card"]], None, c, who(c.get("id")))
        for s in sq.get("subs") or []:
            event("SUBSTITUTION", None, s, who(s.get("off")), who(s.get("on")))
    return {"id": str(r["id"]), "comp": lb, "season": r.get("season"), "year": year(r), "date": day(r), "home": team[(r["home"]["id"], at[r["home"]["id"]])],
            "away": team[(r["away"]["id"], at[r["away"]["id"]])], "score": sc, "unsure": blank, "won": "PENALTIES" if res == PENALTIES else "EXTRA_TIME" if res in EXTRA else None,
            "round": None if lb == "world-cup-qualifiers" else STAGE.get(stage) or ("FINAL" if stage.endswith(" final") else None),
            "stadium": r.get("stadium"), "referees": [{"id": str(ref["id"]), "name": pretty(ref["name"]), "country": ref.get("country"), "role": "REFEREE"}] if ref else [],
            "attendance": int(att) if att.isdigit() else None, "lineups": squads or None, "events": events}


def group(r):
    """the games of one tournament"""
    return (r["comp"], r.get("season"))


def own_in(G):
    def own(r, g, dates, cids):
        """(competition, edition key, season, whatever the tournament's other games sit in) for a game no source held"""
        lb, y = r["comp"], r["year"]
        if lb == "world-cup-qualifiers":
            return cids[lb][0], f"wcq|{r['date'][:4]}", r["date"][:4], True
        if lb == "olympics":                                 # «1936 Berlin» where the graph has the Games under that name
            had = sorted(s for (s,) in G.c.execute("SELECT season FROM edition WHERE cid=?", (cids[lb][0],)).fetchall() if s == y or str(s).startswith(y + " "))
            return cids[lb][0], f"{lb}|{y}", had[0] if had else y, False
        return cids[lb][0], f"{lb}|{y}", y, False
    return own


def load(G, reg, S):
    f = os.path.join(S.db, FILE)
    if not os.path.exists(f):
        return {"skipped": "no fifa.json.gz"}
    pack = json.load(gzip.open(f, "rt", encoding="utf-8"))
    have = {lb for lb, keys in COMP.items() if reg.get("competition", *keys[0]) is not None}
    ok = lambda t: t.get("id") and t.get("name") and t.get("gender") == MEN and t.get("score") is not None
    rows = [r for r in pack["matches"] if r.get("comp") and label(r) in have and r.get("status") == FINISHED and r.get("id") and day(r)
            and ok(r.get("home") or {}) and ok(r.get("away") or {})]
    team = sides(G, reg, rows)
    return uefa.apply(G, reg, [row(r, pack.get("men") or {}, team) for r in rows], SRC, COMP, group, own_in(G))
