"""Argentina's top scorer of every tournament since 1891 (RSSSF «Argentina - List of Topscorers», tablesa/argtops.html,
fetched by graph/fetch.rsssf_tops into db/.cache/rsssf_tops/arg.html) on the tournament's own edition: the amateur
associations (AAF, FAF, LAF…), the Metropolitano and Nacional, the Apertura and Clausura, the Inicial and Final. Written where
the edition has no top scorer yet (the first source keeps its list); ties share the first place. 82 Argentine seasons had a
champion and no scorer on 22 Nov 2026 (the owner: «ما في هدافين لوايد مواسم»)."""
import html, os, re

ARG = 112
TOURNAMENT = {"AAF": "Asociación Argentina de Football (Amateur)", "FAF": "Federación Argentina de Football (Amateur)",
              "AAm": "Asociación Amateurs de Football (Amateur)", "LAF": "Liga Argentina de Football", "Ape": "Apertura",
              "Cla": "Clausura", "Met": "Metropolitano", "Nac": "Nacional", "Ini": "Torneo Inicial", "Fin": "Torneo Final"}
ROW = re.compile(r"^(\d{4}(?:/\d{2})?)?\s{1,12}([A-Z][A-Za-z]{2})?\s+([^\s,][^,]*?,\s*[^\s].*?)\s{2,}\S.*?\s(\d+)\s*$")


def parse_arg(text):
    """[(season, tournament code or "", «First Last», goals)]: a line with no year is the year above, with no code its code"""
    t = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\t", "    ")
    out, year, code = [], None, ""
    for line in t.splitlines():
        m = ROW.match(line)
        if not m:
            y = re.match(r"^(\d{4}(?:/\d{2})?)\s", line)
            if y:
                year, code = y.group(1), ""
            continue
        if m.group(1):
            year, code = m.group(1), m.group(2) or ""
        elif m.group(2):
            code = m.group(2)
        if not year:
            continue
        last, first = [x.strip() for x in m.group(3).split(",", 1)]
        y = year if "/" not in year else f"{year[:4]}/{int(year[:4]) + 1}"          # «1999/00» -> «1999/2000»
        out.append((y, code, f"{first} {last}", int(m.group(4))))
    return out


def load(G, reg, S):
    p = os.path.join(S.db, "rsssf_tops", "arg.html")
    cid = reg.get("competition", "fotmob", ARG)
    if not os.path.exists(p) or cid is None:
        return {"skipped": "no page or no Argentine league"}
    label = {s: e for e, s in G.c.execute("SELECT eid, season FROM edition WHERE cid=?", (cid,))}
    have = {e for (e,) in G.c.execute("SELECT DISTINCT h.eid FROM honour h JOIN edition e ON e.eid=h.eid WHERE e.cid=? AND h.kind='top_scorer'", (cid,))}
    n = 0
    for season, code, name, goals in parse_arg(open(p, encoding="latin-1").read()):
        t = TOURNAMENT.get(code)
        cands = [f"{season} - {t}", f"{season} {t}"] if t else [f"{season} (Amateur)", season]
        eid = next((label[c] for c in cands if c in label), None)
        if eid is None or eid in have:
            continue
        pid = reg.get("player", "rsssf-name", f"arg|{name}") or reg.mint("player", "rsssf-name", f"arg|{name}")
        G.put("player", {"pid": pid, "name": name}, "rsssf")
        n += G.c.execute("INSERT OR IGNORE INTO honour VALUES(?, 'top_scorer', 1, NULL, ?, NULL, ?, 'rsssf')", (eid, pid, str(goals))).rowcount
    return {"argentina": n}
