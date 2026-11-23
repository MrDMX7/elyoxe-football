"""The site's integrity, counted (the owner, 23 Nov 2026: «نحل جميع مشاكل عدم التكامل + التخبيص»): a sample of every page kind
from every sitemap, every internal link on them followed once, and four counts per kind —

  broken    a link that lands on the 404 page;
  old       a link into the encyclopedia (/db/match, /db/player, /db/club) where the archive or the site has the page;
  twin      a page whose man or match has another page too (an encyclopedia player with an archive profile);
  latin     names left in Latin letters (<span class="lat">), with the strings that come back most, for the Arabic names work.

    python -m tools.integrity [--per 30] [--out integrity.json] [--base https://tifo.elyoxe.com]

HTTP only (no browser: site/qa/site_qa.cjs checks the layout), 16 at a time. The archive's maps (v1/archive/fm2k.json,
fm2p.json) say which FotMob match or man has an archive page."""
import argparse, gzip, json, random, re, sys, time, urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

UA = "elyoxe-tifo-integrity/0.1 (hello@elyoxe.com)"
SITEMAPS = ("sitemap.xml", "sitemap-players.xml", "sitemap-archive.xml")
LAT = re.compile(r'<span class="lat">([^<]{2,60})</span>')
HREF = re.compile(r'<a\b[^>]*\shref="(/[^"#]*)"')
NOT_FOUND = "الصفحة مب موجودة"


def kind(path):
    p = path.strip("/").split("/")
    if not p[0]:
        return "home"
    if p[0] == "c" and len(p) > 2:
        return "c/*/" + p[2]
    if p[0] == "db" and len(p) > 1:
        return "db/" + p[1]
    if p[0] in ("m", "p", "t", "r", "coach") and len(p) > 1:
        return p[0] + ("/k" if p[1].startswith("k") else "")
    return p[0]


def fetch(url, tries=3):
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"}), timeout=30)
            body = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return r.status, body.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, ""
            time.sleep(1 + i)
        except Exception:
            time.sleep(1 + i)
    return 0, ""


def sitemap_paths(base):
    out = []
    for sm in SITEMAPS:
        _, x = fetch(f"{base}/{sm}")
        subs = re.findall(r"<loc>([^<]*sitemap[^<]*\.xml)</loc>", x)
        for u in subs or [f"{base}/{sm}"]:
            _, y = fetch(u) if subs else (200, x)
            out += [re.sub(r"^https?://[^/]+", "", u2) for u2 in re.findall(r"<loc>([^<]+)</loc>", y) if not u2.endswith(".xml")]
    return sorted(set(out))


def audit(pages, base, maps, links_cap=4000):
    fm2k, fm2p = maps
    rep = defaultdict(lambda: {"pages": 0, "broken": Counter(), "old": Counter(), "twin": [], "latin": 0, "names": 0})
    latin, where = Counter(), defaultdict(list)
    with ThreadPoolExecutor(16) as ex:
        got = dict(zip(pages, ex.map(lambda p: fetch(base + p), pages)))
    targets = set()
    for p, (st, h) in got.items():
        k = rep[kind(p)]
        k["pages"] += 1
        if st != 200 or NOT_FOUND in h[:3000]:
            k["broken"]["(the page itself)"] += 1
            continue
        names = LAT.findall(h)
        k["latin"] += len(names)
        k["names"] += len(names) + h.count('class="rt"')
        latin.update(n.strip() for n in names)
        for n in set(x.strip() for x in names):
            if len(where[n]) < 3:
                where[n].append(p)
        for href in set(HREF.findall(h)):
            if href.startswith(("/v1/", "/assets/", "/logo/", "/og/", "/api/")):
                continue
            m = re.match(r"^/db/match/\?id=(\d+)", href)
            if m and m.group(1) in fm2k:
                k["old"][f"/db/match -> /m/k{fm2k[m.group(1)]}/"] += 1
            m = re.match(r"^/db/player/(\d+)/", href)
            if m and m.group(1) in fm2p:
                k["old"]["/db/player -> /p/k"] += 1
            targets.add(href.split("?")[0] if not href.startswith("/db/") else href)
        m = re.match(r"^/db/player/(\d+)/$", p)
        if m and m.group(1) in fm2p:
            k["twin"].append([p, f"/p/k{fm2p[m.group(1)]}/"])
    targets = sorted(targets)[:links_cap]
    with ThreadPoolExecutor(16) as ex:
        st = dict(zip(targets, ex.map(lambda u: fetch(base + u)[0] if not u.startswith("/db/") else 200, targets)))
    for p, (s0, h) in got.items():
        if s0 != 200:
            continue
        for href in set(HREF.findall(h)):
            if st.get(href.split("?")[0]) == 404:
                rep[kind(p)]["broken"][href] += 1
    return rep, latin, where


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://tifo.elyoxe.com")
    ap.add_argument("--per", type=int, default=30)
    ap.add_argument("--out", default="integrity.json")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    paths = sitemap_paths(a.base)
    by = defaultdict(list)
    for p in paths:
        by[kind(p)].append(p)
    random.seed(a.seed)
    pages = [p for k, ps in sorted(by.items()) for p in random.sample(ps, min(a.per, len(ps)))]
    maps = []
    for name in ("fm2k", "fm2p"):
        st, x = fetch(f"{a.base}/v1/archive/{name}.json")
        maps.append({str(k): v for k, v in (json.loads(x) if st == 200 and x else {}).items()})
    t0 = time.time()
    rep, latin, where = audit(pages, a.base, maps)
    summary = {k: {"pages": v["pages"], "broken": sum(v["broken"].values()), "old": sum(v["old"].values()), "twin": len(v["twin"]),
                   "latin_share": round(v["latin"] / max(1, v["names"]), 2)} for k, v in sorted(rep.items())}
    json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sitemap_pages": len(paths), "sampled": len(pages), "summary": summary,
               "broken": {k: dict(v["broken"].most_common(15)) for k, v in rep.items() if v["broken"]},
               "old": {k: dict(v["old"].most_common(5)) for k, v in rep.items() if v["old"]},
               "twins": {k: v["twin"][:5] for k, v in rep.items() if v["twin"]}, "latin_top": [[n, k, where[n]] for n, k in latin.most_common(80)]},
              open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(paths)} pages in the sitemaps, {len(pages)} sampled in {time.time() - t0:.0f}s")
    print(f"{'kind':18} {'pages':>5} {'broken':>6} {'old':>5} {'twin':>5} {'latin':>6}")
    for k, v in summary.items():
        print(f"{k:18} {v['pages']:>5} {v['broken']:>6} {v['old']:>5} {v['twin']:>5} {v['latin_share']:>6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
