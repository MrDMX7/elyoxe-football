"""The Arabic names of the Transfermarkt clubs FotMob never names (23 Nov 2026: 9,758 clubs — Port Vale FC, Juventus Primavera,
Real Valladolid Promesas — left 45 % of the profiles' career lines in Latin letters).

    python -m names.tm_clubs --db <graph tifo.db> [--limit N]

1. the pool: the graph's clubs with a Transfermarkt id and no Arabic name, with their country;
2. Wikidata: an item's Arabic label by its Transfermarkt team id (P7223), one query (QLever); a bot's spelling (پ/چ/ڤ/گ)
   is refused, as for the players (README.md);
3. the rest written by Gemini as Arab sports media write them (build_names.gemini_call), a youth or reserve side as
   «<club> تحت 19» / «<club> الرديف».

Out: names/clubs_tm_ar.json {tm id: {latin, ar, source}}, saved after every batch (a stopped run keeps what it did); the
graph's names loader (graph/load/names.py) fills the clubs' name_ar from it, never over a name they have."""
import argparse, json, os, re, sqlite3, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "clubs_tm_ar.json")
ARABIC = re.compile("[%s-%s]" % (chr(0x600), chr(0x6FF)))
BOT = re.compile("[%s]" % "".join(map(chr, (0x67E, 0x686, 0x6A4, 0x6AF))))      # پ چ ڤ گ
PROMPT = """You are an Arabic sports editor (beIN Sports, Kooora, Al Ittihad). Write each football CLUB's name in Arabic exactly as
Arab sports media write it.
Rules:
- Arabic script only, no diacritics, no Latin letters.
- Arab clubs: their real Arabic name ("Raja Casablanca" -> "الرجاء الرياضي", "Al Ahly" -> "الأهلي").
- Other clubs: the usual Arabic media form ("Bayern Munich" -> "بايرن ميونخ", "Port Vale FC" -> "بورت فايل").
- Drop FC, SC, CF, AC, BK, FK, SK, Club, Calcio unless Arab media keep them ("AC Milan" -> "ميلان").
- A youth or reserve side keeps its club's name: "Juventus Primavera"/"Juventus U19" -> "يوفنتوس تحت 19",
  "West Bromwich Albion U21" -> "وست بروميتش ألبيون تحت 21", "Real Valladolid Promesas"/"Barcelona B"/"Bayern Munich II"/
  "Reserves" -> "<club> الرديف".
- The country helps the pronunciation (Spanish j -> خ, Portuguese lh -> لي, German w -> ف).
Return one item per input, with the same id."""


def wd_map(rows):
    """QLever rows {tm, ar} -> {tm id: Arabic}, a bot's spelling (پ/چ/ڤ/گ) or a label with no Arabic refused"""
    out = {}
    for r in rows:
        tm, ar = r["tm"]["value"], r["ar"]["value"].strip()
        if ARABIC.search(ar) and not BOT.search(ar) and not re.search(r"[A-Za-z]", ar):
            out.setdefault(tm, ar)
    return out


def wikidata():
    q = """PREFIX wdt: <http://www.wikidata.org/prop/direct/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?tm ?ar WHERE { ?item wdt:P7223 ?tm . ?item rdfs:label ?ar FILTER(LANG(?ar)="ar") }"""
    u = "https://qlever.cs.uni-freiburg.de/api/wikidata?" + urllib.parse.urlencode({"query": q})
    req = urllib.request.Request(u, headers={"User-Agent": "elyoxe-tifo/0.1 (hello@elyoxe.com)", "Accept": "application/sparql-results+json"})
    return wd_map(json.loads(urllib.request.urlopen(req, timeout=300).read())["results"]["bindings"])


def pool(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = c.execute("""SELECT x.source_id, t.name, t.country FROM team t JOIN xref x ON x.type='team' AND x.source='tm' AND x.tifo_id=t.tid
                        WHERE (t.name_ar IS NULL OR t.name_ar='') AND t.name IS NOT NULL""").fetchall()
    return {str(k): (n, ctry) for k, n, ctry in rows}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=60)
    a = ap.parse_args(argv)
    sys.path.insert(0, os.path.dirname(HERE))
    from names import build_names as B
    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    save = lambda: json.dump(dict(sorted(out.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0)), open(OUT, "w", encoding="utf-8"),
                             ensure_ascii=False, indent=0)
    P = pool(a.db)
    todo = [k for k in P if k not in out]
    print(f"{len(P)} clubs with no Arabic name, {len(todo)} not done yet", flush=True)
    wd = wikidata()
    for k in todo:
        if k in wd:
            out[k] = {"latin": P[k][0], "ar": wd[k], "source": "wikidata"}
    save()
    todo = [k for k in todo if k not in out]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{sum(1 for k in P if out.get(k, {}).get('source') == 'wikidata')} from Wikidata; {len(todo)} for Gemini", flush=True)
    key = B.gemini_key()
    if not key:
        print("no Gemini key: Wikidata only")
        return 0
    for i in range(0, len(todo), a.batch):
        chunk = todo[i:i + a.batch]
        text = PROMPT + "\n\nid\tname\tcountry\n" + "\n".join(f"{k}\t{P[k][0]}\t{P[k][1] or 'unknown'}" for k in chunk)
        got = B.gemini_call(key, text, len(chunk))
        for k in chunk:
            ar = (got.get(k) or "").strip()
            if ar and ARABIC.search(ar) and not re.search(r"[A-Za-z]", ar):
                out[k] = {"latin": P[k][0], "ar": ar, "source": "generated"}
        save()
        print(f"  {min(i + a.batch, len(todo))}/{len(todo)}", flush=True)
        time.sleep(1)
    print(f"done: {len(out)} clubs named")
    return 0


if __name__ == "__main__":
    sys.exit(main())
