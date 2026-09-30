"""The Arab leagues before the other databases start (owner 2026-09-30: «العين يعطيك مبارياته فقط من سنة 2000»), from RSSSF
(the Rec.Sport.Soccer Statistics Foundation): every season's page of each Arab league — final table, the matches it
lists (Super Cup rounds, cups, sometimes the whole season), top scorers — back to the 1970s.

    python -m db.rsssf [--upload] [--country uae]

Pages: tables<letter>/<code>champ.html lists the champions and links the seasons (<code>95.html…). Plain text; parsed
with the three shapes they use: table rows «1.Al-Shabab  18 12 5 1 26- 9 29», result rows «13/4  A  v  B  1-2», scorer
rows «22 Name (Club)» / «Name (Club) 22». A club name is linked to our FotMob id within its country (same folding and
«every word in one team's name» rule as the other stages, plus the country's old names below).
Out: v1/history/arab/<code>.json (every season: table, scorers, champion) and db/.cache/rsssf_clubs.json (per FotMob
club: positions per season and the dated matches) that db/history.py merges into the club histories.
"""
import argparse, html as H, json, os, re, sys, time, unicodedata, urllib.request
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from store import Store, S3Backend  # noqa: E402

BUCKET = os.environ.get("FOOTBALL_BUCKET", "elyoxe-football-574771023173-ap-south-1")
CACHE = os.path.join(HERE, ".cache", "rsssf")
# code, page folder letter, ISO for our teams, our league id, old names -> today's club
COUNTRIES = {
    # renamed clubs map to today's name; clubs absorbed in a merger (Al-Shabab and Al-Sha'ab, 2017) stay themselves.
    # Al-Ahli Dubai is the club FotMob carries on as Shabab Al-Ahli
    "uae": ("u", "AE", 538, {"al oroba": "sharjah", "al ahli dubai": "shabab al ahli", "al ahly dubai": "shabab al ahli", "al ahli": "shabab al ahli",
                             "al ahly": "shabab al ahli", "al ittihad kalba": "kalba", "ittihad kalba": "kalba", "kalba union": "kalba"}),
    "sau": ("s", "SA", 536, {}), "qat": ("q", "QA", 535, {}), "kuw": ("k", "KW", 529, {}), "egy": ("e", "EG", 519, {}),
    "maro": ("m", "MA", 530, {}), "alg": ("a", "DZ", 516, {}), "tun": ("t", "TN", 544, {}), "iraq": ("i", "IQ", 524, {}),
    "oman": ("o", "OM", None, {}), "jord": ("j", "JO", None, {}),
}


def get(path):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, path.replace("/", "_"))
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 20 * 86400:
        return open(p, encoding="utf-8").read()
    try:
        raw = urllib.request.urlopen(urllib.request.Request("https://www.rsssf.org/" + path, headers={"User-Agent": "Mozilla/5.0 (elyoxe-tifo)"}), timeout=60).read()
    except Exception:
        return None
    t = raw.decode("latin-1")
    open(p, "w", encoding="utf-8").write(t); time.sleep(0.5)
    return t


def text(h):
    return H.unescape(re.sub(r"<[^>]+>", "", h or ""))


def fold(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\b(fc|sc|club|cultural|saudi|dubai fc)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# spellings RSSSF and FotMob write differently, and North African prefixes (AS, CS, ES, JS, MC, CR, USM…) that one side drops
SPELL = {"ahly": "ahli", "sad": "sadd", "saad": "sadd", "masri": "masry", "ismaili": "ismaily", "mehalla": "mahalla", "mokaoulun": "mokawloon",
         "qadisiya": "qadsiah", "qadsia": "qadsiah", "qadissiyah": "qadsiah", "qadeseya": "qadsiah", "qadisiyah": "qadsiah", "ittifaq": "ettifaq",
         "taawon": "taawoun", "taawun": "taawoun", "shabab": "shabab", "nasr": "nassr", "hilal": "hilal", "zamalek": "zamalek", "wakra": "wakrah",
         "gharafa": "gharafa", "rayyan": "rayyan", "kuwait": "kuwait", "salmiya": "salmiyah", "fehayheel": "fahaheel", "arabi": "arabi"}
PREFIX = {"as", "cs", "es", "js", "mc", "cr", "usm", "us", "ca", "cb", "rc", "om", "usmh", "nrb", "ob", "mo", "ss", "ac", "fus", "far", "wac", "raja", "de", "du", "la", "le", "club", "sporting"}


def canon(f):
    ws = [SPELL.get(w, w) for w in f.split()]
    core = [w for w in ws if w not in PREFIX]
    return " ".join(core or ws)


ROW = re.compile(r"^\s*(\d{1,2})\.\s*(.+?)\s{2,}(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s*-\s*(\d{1,3})\s+(-?\d{1,3})")
ROW2 = re.compile(r"^\s*(\d{1,2})\.?\s+([A-Za-z][A-Za-z' .()/-]+?)\s{2,}(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(-?\d{1,3})")
RES = re.compile(r"^\s*(?:(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?)?\s+([A-Z][A-Za-z' .()-]+?)\s+v\s+([A-Z][A-Za-z' .()-]+?)\s{2,}(\d{1,2})\s*[-/]\s*(\d{1,2})\b")
SC1 = re.compile(r"^\s*(\d{1,2})\s+([A-Z][^()\d]+?)\s+\(([^)]+)\)")
SC2 = re.compile(r"^\s*([A-Z][^()\d]+?)\s+\(([^)]+)\)\s+(\d{1,2})\s*$")


def parse_season(t, label):
    lines = t.splitlines()
    table, results, scorers = [], [], []
    start = next((i for i, l in enumerate(lines) if re.search(r"final table|^\s*table\b|league table|standings", l, re.I)), None)
    if start is not None:
        for l in lines[start + 1:start + 60]:
            m = ROW.match(l) or ROW2.match(l)
            if m:
                table.append([int(m.group(1)), m.group(2).strip(), *[int(m.group(k)) for k in range(3, 10)]])
            elif table and not l.strip():
                break
    sc_at = next((i for i, l in enumerate(lines) if re.search(r"top ?scorers?|topscorer|goalscorers", l, re.I)), None)
    if sc_at is not None:
        for l in lines[sc_at + 1:sc_at + 25]:
            m = SC1.match(l)
            if m:
                scorers.append([m.group(2).strip(), m.group(3).strip(), int(m.group(1))]); continue
            m = SC2.match(l)
            if m:
                scorers.append([m.group(1).strip(), m.group(2).strip(), int(m.group(3))]); continue
            if scorers and not l.strip():
                break
    y1, y2 = season_years(label)
    section = "league"
    for l in lines:
        if re.search(r"cup|super|final|round|quarter|semi", l, re.I) and not RES.match(l):
            section = "cup" if re.search(r"cup|final|round|quarter|semi", l, re.I) else section
        m = RES.match(l)
        if m and y1:
            d, mo = m.group(1), m.group(2)
            if d and mo:
                y = y2 if int(mo) <= 7 else y1
                results.append([f"{y}-{int(mo):02d}-{int(d):02d}", m.group(4).strip(), m.group(5).strip(), int(m.group(6)), int(m.group(7)), section])
    return table, results, scorers


def season_years(label):
    m = re.search(r"(\d{4})\s*/\s*(\d{2,4})", label or "")
    if m:
        a = int(m.group(1)); b = m.group(2)
        return a, (int(b) if len(b) == 4 else a // 100 * 100 + int(b) + (100 if int(b) < a % 100 else 0))
    m = re.search(r"(\d{4})", label or "")
    return (int(m.group(1)), int(m.group(1))) if m else (None, None)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--upload", action="store_true"); ap.add_argument("--country"); a = ap.parse_args(argv)
    store = Store(S3Backend(BUCKET))
    teams = (store.get_json("teams.json") or {}).get("teams") or {}
    comps = {c["id"]: c for c in (store.get_json("index.json") or {}).get("competitions") or []}
    clubs_out = defaultdict(lambda: {"positions": [], "matches": []})
    for code, (letter, iso, lid, old) in COUNTRIES.items():
        if a.country and code != a.country:
            continue
        champ = get(f"tables{letter}/{code}champ.html")
        if not champ:
            print(code, "no champions page"); continue
        pool = [(int(k), canon(fold(t.get("name")))) for k, t in teams.items() if (t.get("country") or {}).get("iso2") == iso or (lid and lid in (t.get("comps") or []))]

        def link(name):
            """exact, then every word, then close spelling (RSSSF writes «Al Ahly», «Al Sad», «Al Masri» where FotMob writes
            Al-Ahli, Al-Sadd, Al-Masry); only a unique winner with a clear lead counts"""
            f = canon(fold(name)); f = old.get(f, f)
            ws = set(f.split()) - {"al"}
            ex = [k for k, n in pool if n == f] or [k for k, n in pool if ws and ws <= set(n.split())]
            if len(ex) == 1:
                return ex[0]
            if len(ex) > 1:
                return None
            import difflib
            sc = sorted(((difflib.SequenceMatcher(None, f, n).ratio(), k) for k, n in pool), reverse=True)
            if sc and sc[0][0] >= 0.84 and (len(sc) == 1 or sc[0][0] - sc[1][0] >= 0.08):
                return sc[0][1]
            return None
        seasons, linked, unl = [], set(), set()
        pages = sorted(set(re.findall(r'href="(%s\d{2,4}\.html)"' % code, champ)))
        for pg in pages:
            h = get(f"tables{letter}/{pg}")
            if not h:
                continue
            t = text(h)
            label = (re.search(r"\n\s*([^\n]*\d{4}[^\n]*)\n", t) or [None, pg])[1].strip()
            table, results, scorers = parse_season(t, label)
            y1, y2 = season_years(label)
            season = f"{y1}/{y2}" if y1 and y2 and y1 != y2 else str(y1 or pg)
            for r in table:
                fid = link(r[1]); (linked if fid else unl).add(r[1])
                if fid:
                    clubs_out[fid]["positions"].append([season, r[0], len(table), r[8], r[2], r[3], r[4], r[5], r[6], r[7], "rsssf"])
            for d, hn, an, hg, ag, sec in results:
                hi, ai = link(hn), link(an)
                for me, opp, oname, home, gf, ga in ((hi, ai, an, 1, hg, ag), (ai, hi, hn, 0, ag, hg)):
                    if me:
                        clubs_out[me]["matches"].append([d, opp if opp else "r:" + oname, home, gf, ga, f"rsssf:{code}:{sec}"])
            seasons.append({"season": season, "page": pg, "table": [[r[0], r[1], link(r[1])] + r[2:] for r in table],
                            "scorers": [[s[0], s[1], link(s[1]), s[2]] for s in scorers], "matches": len(results)})
        seasons.sort(key=lambda s: s["season"])
        print(code, len(pages), "season pages;", sum(1 for s in seasons if s["table"]), "with a table;", sum(s["matches"] for s in seasons), "matches;",
              sum(1 for s in seasons if s["scorers"]), "with scorers; clubs linked", len(linked), "not", len(unl), sorted(unl)[:8])
        if a.upload:
            store.put_json(f"history/arab/{code}.json", {"country": code, "league": lid, "seasons": seasons, "source": "RSSSF (rsssf.org)"}, cache="warm")
    json.dump(clubs_out, open(os.path.join(HERE, ".cache", "rsssf_clubs.json"), "w", encoding="utf-8", newline="\n"), ensure_ascii=False)
    print(len(clubs_out), "of our clubs get RSSSF seasons/matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
