"""FotMob's own Arabic names (www.fotmob.com/api/translationmapping?locale=ar, «Participants»: 63k players, coaches and
clubs by FotMob id, written by people) for a player, coach or club FotMob knows and the graph holds in Latin only (24,591
players and 2,220 coaches on 21 Nov). Never over a name the graph has (names/players_ar.json, Wikidata, manual: names/verify.py
checks those against FotMob instead); never a full legal name two words or more longer than the known one (Muriqui:
«لويز غيليرمي دا كونسيساو سيلفيا»). Fetched each build; the last copy kept in S3 state for a day FotMob does not answer."""
import json, urllib.request

URL = "https://www.fotmob.com/api/translationmapping?locale=ar"
STATE = "graph/fotmob_ar.json"
KEYS = {"player": "pid", "coach": "kid", "team": "tid"}


def fill(G, names):
    n = {"player": 0, "coach": 0, "team": 0, "too_long": 0}
    for t, k in KEYS.items():
        rows = G.c.execute(f"""SELECT a.{k}, a.name, x.source_id FROM {t} a JOIN xref x ON x.type=? AND x.tifo_id=a.{k} AND x.source='fotmob'
                               WHERE a.name_ar IS NULL OR a.name_ar=''""", (t,)).fetchall()
        put = []
        for i, latin, fid in rows:
            ar = (names.get(str(fid)) or "").strip()
            if not ar:
                continue
            if t != "team" and len(ar.split()) > len((latin or "").split()) + 1:
                n["too_long"] += 1
                continue
            put.append((ar, i))
        G.c.executemany(f"UPDATE {t} SET name_ar=? WHERE {k}=? AND (name_ar IS NULL OR name_ar='')", put)
        n[t] = len(put)
    return n


def load(G, reg, S):
    names = None
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        names = json.loads(urllib.request.urlopen(req, timeout=60).read())["Participants"]
        if S.s3:
            S.store().put_state(STATE, names)
    except Exception as e:
        print(f"fotmob ar names: {type(e).__name__}; the last copy", flush=True)
        if S.s3:
            names = S.store().get_state(STATE)
    if not names:
        return {"skipped": "no FotMob Arabic names"}
    return fill(G, names)
