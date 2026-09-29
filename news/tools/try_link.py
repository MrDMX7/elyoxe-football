"""Link real headlines from a few live feeds and print them, to eyeball the dictionary.
   python news/tools/try_link.py [source keys…]"""
import io, json, os, sys, urllib.request, gzip
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import yaml
from news import entities as E, readers as RD

raw = urllib.request.urlopen(urllib.request.Request("https://d1n5aqaqkowltp.cloudfront.net/teams.json", headers={"Accept-Encoding": "gzip"}), timeout=30).read()
teams = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
D = E.load(teams)
cfg = yaml.safe_load(open(os.path.join(os.path.dirname(HERE), "sources.yaml"), encoding="utf-8"))
want = sys.argv[1:] or ["bbc", "as", "skynewsarabia"]
srcs = [s for s in cfg["sources"] if s["key"] in want] + [RD.gnews_source(q, cfg["gnews"]) for q in ("النصر السعودي", "ميسي") if "gnews" in want or not sys.argv[1:]]
linked = total = 0
for s in srcs:
    items, err = RD.read_source(s)
    print(f"\n== {s['key']} {s.get('query') or ''} ({len(items)} items{', ' + err if err else ''})")
    for it in items[:12]:
        ents = E.link(D, it["title"] + " " + (it["desc"] or ""), it.get("query"))
        total += 1; linked += bool(ents)
        print(f"  {it['title'][:78]:78} -> {[D.names.get(e, e) for e in ents]}")
print(f"\nlinked {linked}/{total}")
