"""Build alltime.yaml: UAE league champions since 1973-74 and the all-time top scorers.

FotMob starts in 2010/11, so older facts come from the English Wikipedia article "UAE Pro League"
(its champions table cites RSSSF, its scorers table cites FootballUAE.net / the league). Only facts
(season, champion, runner-up, scorer, goals, apps) are copied, no prose; each list records the
Wikipedia revision it was read from. The FotMob seasons 2010/11+ are cross-checked against FotMob's
own `seasons[].winner` and every disagreement is written into the file.
  python tools/build_alltime.py > alltime.yaml
"""
import json, re, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sources.fotmob import FotMob  # noqa: E402

UA = "elyoxe-tifo-data/0.1 (hello@elyoxe.com)"
API = "https://en.wikipedia.org/w/api.php?action=parse&page=UAE_Pro_League&prop=wikitext|revid&format=json&formatversion=2"

# Wikipedia club link target -> FotMob team id (clubs that still exist under FotMob ids)
CLUB_IDS = {"Sharjah": 102124, "Al Ain": 102117, "Al Nasr": 102123, "Al Wasl": 102111, "Al Wahda": 102122,
            "Al Jazira": 102101, "Shabab Al Ahli": 102119, "Al Ahli": 102119, "Al Shabab": 102115, "Al Shaab": 102120,
            "Baniyas": 182933, "Ajman": 149994, "Al Dhafra": 102118, "Emirates": 102121}
AR = {"Sharjah": "الشارقة", "Al Ain": "العين", "Al Nasr": "النصر", "Al Wasl": "الوصل", "Al Wahda": "الوحدة",
      "Al Jazira": "الجزيرة", "Shabab Al Ahli": "شباب الأهلي", "Al Ahli": "الأهلي", "Al Shabab": "الشباب",
      "Al Shaab": "الشعب", "Baniyas": "بني ياس", "Ajman": "عجمان", "Al Dhafra": "الظفرة", "Emirates": "الإمارات"}


def clean(cell):
    cell = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", cell, flags=re.S)
    cell = re.sub(r"\{\{ref\|[^}]*\}\}|\{\{n/a\}\}", "", cell)
    cell = re.sub(r"\[\[[^|\]]*\|([^\]]*)\]\]", r"\1", cell)
    cell = re.sub(r"\[\[([^\]]*)\]\]", r"\1", cell)
    cell = cell.replace("'''", "").replace("''", "").replace("&nbsp;", " ")
    return "\n".join(re.sub(r"[ \t]+", " ", x).strip() for x in cell.split("\n") if x.strip())


def table(section):
    """Wikitext table -> list of rows (lists of cleaned cells), rowspans expanded."""
    body = section[section.find("{|"):section.find("|}")]
    rows, pending = [], {}      # col -> (value, remaining)
    for raw in body.split("\n|-")[1:]:
        cells = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line or line.startswith("|-") or line.startswith("!"):
                continue
            if line.startswith("|"):
                for c in line[1:].split("||"):
                    cells.append(c)
            elif cells:
                cells[-1] += "\n" + line          # continuation (multi-club cell)
        out, col, i = [], 0, 0
        while i < len(cells) or col in pending:
            if col in pending:
                v, n = pending[col]
                out.append(v)
                pending[col] = (v, n - 1) if n > 1 else None
                if pending[col] is None:
                    del pending[col]
                col += 1
                continue
            c = cells[i]
            i += 1
            m = re.match(r'\s*((?:[a-z]+="[^"]*"\s*)+)\|(.*)$', c, re.S)
            attrs, val = (m.group(1), m.group(2)) if m else ("", c)
            val = clean(val)
            rs = re.search(r'rowspan="(\d+)"', attrs)
            cs = re.search(r'colspan="(\d+)"', attrs)
            if rs and int(rs.group(1)) > 1:
                pending[col] = (val, int(rs.group(1)) - 1)
            out.append(val)
            col += 1
            if cs:
                for _ in range(int(cs.group(1)) - 1):
                    out.append(val)
                    col += 1
        rows.append(out)
    return rows


def main():
    req = urllib.request.Request(API, headers={"User-Agent": UA})
    d = json.loads(urllib.request.urlopen(req, timeout=30).read())["parse"]
    w, rev = d["wikitext"], d["revid"]
    champs_sec = w[w.find("==List of champions=="):w.find("==Champions==", w.find("==List of champions==") + 5)]
    scor_sec = w[w.find("===All-time top scorers==="):w.find("===Top scorers by season===")]
    champs = []
    for r in table(champs_sec):
        if len(r) < 4:
            continue
        season, champ = r[2], r[3]
        runner = r[4] if len(r) > 4 else None
        if not re.match(r"\d{4}[–-]\d{2}", season):
            continue
        cancelled = "Cancelled" in champ
        champs.append({"season": season.replace("–", "-"), "champion": None if cancelled else champ,
                       "champion_id": CLUB_IDS.get(champ), "champion_ar": AR.get(champ),
                       "runner_up": None if cancelled else runner, "cancelled": cancelled or None})
    # FotMob cross-check 2010/11+
    fm = FotMob()
    raw = fm.league_raw(538)
    fm_w = {s["seasonName"]: (s.get("winner") or {}) for s in raw.get("seasons") or []}
    notes = []
    for c in champs:
        y1, y2 = c["season"].split("-")
        key = f"{y1}/{int(y1) + 1}"
        w_ = fm_w.get(key)
        if w_:
            c["fotmob_winner"] = w_.get("name")
            if c["champion_id"] and w_.get("id") and int(w_["id"]) != c["champion_id"]:
                notes.append(f"{c['season']}: Wikipedia {c['champion']} vs FotMob {w_.get('name')}")
    scorers = []
    for r in table(scor_sec):
        if len(r) >= 6 and r[0].isdigit():
            scorers.append({"rank": int(r[0]), "name": r[2], "clubs": [x.strip() for x in r[3].split("\n") if x.strip()],
                            "years": r[4], "goals": int(re.sub(r"\D", "", r[5]) or 0),
                            "apps": int(re.sub(r"\D", "", r[6]) or 0) if len(r) > 6 and re.sub(r"\D", "", r[6]) else None})
    counts = {}
    for c in champs:
        if c["champion"]:
            counts[c["champion"]] = counts.get(c["champion"], 0) + 1
    doc = {
        "source": {"wikipedia": f"https://en.wikipedia.org/w/index.php?title=UAE_Pro_League&oldid={rev}",
                   "wikipedia_revision": rev,
                   "champions_cited_source": "RSSSF, United Arab Emirates - List of Champions (https://www.rsssf.org/tablesu/uaechamp.html)",
                   "scorers_cited_source": "FootballUAE.net '100s' (archived) as cited by the Wikipedia table",
                   "cross_check": "FotMob leagues?id=538 seasons[].winner, 2010/11 onward", "facts_only": True},
        "cross_check_disagreements": notes,
        "titles_by_club": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "champions": champs,
        "top_scorers_all_time": scorers,
    }
    import yaml
    print("# UAE league champions since 1973-74 and all-time top scorers. Built by tools/build_alltime.py;")
    print("# facts only, sources and the Wikipedia revision below. Do not edit by hand, rerun the tool.")
    print(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=200))


if __name__ == "__main__":
    main()
