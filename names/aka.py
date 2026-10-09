"""«يُكتب أيضاً» (owner 2026-10-09): other Arabic spellings of a player's name, so a search typed the way beIN or a paper
spells him still finds his page. Source: the redirects Arabic Wikipedia keeps to his article (its editors add the spellings
people use). Measured 2026-10-09 on 300 players with a Wikidata id: 220 have an Arabic article, 30 a real variant (one that
differs beyond hamza/alif, ى/ي, ة/ه, which search engines fold already).

  python3 aka.py            refresh names/players_ar_aka.json (each player re-read after REFRESH_DAYS, BUDGET a run)

Output {pid: {"qid", "aka": [spellings], "checked": "YYYY-MM-DD"}}; read by site/build.cjs (/p/ pages, Person.alternateName).
Runs with the weekly names job (tools/runner.py job_names), committed with names/."""
import datetime as dt
import difflib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "players_ar_aka.json"
UA = {"User-Agent": "ElyoxeTifoNames/1.0 (https://tifo.elyoxe.com; hello@elyoxe.com)"}
REFRESH_DAYS = 30
BUDGET = 4000
MAX = 4
ARABIC = re.compile(r"^[ء-ي\s\-]+$")      # Arabic letters only: no Latin, no Persian/Urdu letters, no brackets


def _norm(s):
    s = re.sub("[إأآا]", "ا", s).replace("ى", "ي").replace("ة", "ه").replace("ـ", "")
    return re.sub(r"\s+", " ", s).strip()


def _same_words(m, n):
    """Every word of the name has a close spelling among the variant's words («غابرييل» ~ «جبريل», «أوليسه» ~ «أوليز»);
    a shared first name alone is not enough («محمد وعد» is not «محمد جدوع»)."""
    vs = n.split()
    return all(max(difflib.SequenceMatcher(None, w, v).ratio() for v in vs) >= 0.6 for w in m.split())


def variants(main, redirects):
    """The redirects worth showing: Arabic only, not the same as the name once search-folded, not one short word, no
    disambiguation copy; at most MAX, sorted, one per folded form."""
    seen, out, m = {_norm(main)}, [], _norm(main)
    for r in sorted(set(redirects)):
        if not ARABIC.match(r):
            continue
        n = _norm(r)
        if n in seen or (" " not in n and len(n) <= 4) or re.search(r"(.)\1\1|ةة|ىى", r):   # the typo check reads the redirect as written (_norm folds ة)
            continue
        # the same man: a fuller name holding every word of his, or a spelling close to it (2026-10-09: «محمد وعد» had a
        # redirect «محمد جدوع», another player; «حمزةة الركراكي» a typo)
        if not (set(m.split()) <= set(n.split()) or _same_words(m, n)):
            continue
        seen.add(n)
        out.append(r.strip())
    return out[:MAX]


def _get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.load(r)
        except Exception:
            time.sleep(3 * (i + 1))
    return {}


def _articles(qids):
    """{qid: Arabic Wikipedia article title}"""
    out = {}
    for i in range(0, len(qids), 50):
        e = _get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]), "props": "sitelinks", "sitefilter": "arwiki", "format": "json"})).get("entities") or {}
        for q, v in e.items():
            t = ((v.get("sitelinks") or {}).get("arwiki") or {}).get("title")
            if t:
                out[q] = t
    return out


def _redirects(titles):
    """{title: [redirect titles]}"""
    out = {}
    for i in range(0, len(titles), 50):
        r = _get("https://ar.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "query", "titles": "|".join(titles[i:i + 50]), "prop": "redirects", "rdlimit": "max", "format": "json"}))
        for p in ((r.get("query") or {}).get("pages") or {}).values():
            out[p.get("title")] = [x["title"] for x in p.get("redirects") or []]
    return out


def refresh(names, cache, today=None, budget=BUDGET):
    today = today or dt.date.today()
    due = [pid for pid, v in names.items() if isinstance(v, dict) and v.get("qid") and v.get("ar")
           and (pid not in cache or (today - dt.date.fromisoformat(cache[pid].get("checked", "2000-01-01"))).days > REFRESH_DAYS)][:budget]
    qid = {pid: names[pid]["qid"] for pid in due}
    arts = _articles(sorted(set(qid.values())))
    reds = _redirects(sorted(set(arts.values())))
    for pid in due:
        t = arts.get(qid[pid])
        cache[pid] = {"qid": qid[pid], "aka": variants(names[pid]["ar"], reds.get(t, [])) if t else [], "checked": today.isoformat()}
    return cache, len(due)


def main():
    names = json.loads((HERE / "players_ar.json").read_text(encoding="utf-8"))
    cache = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    cache, n = refresh(names, cache)
    OUT.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=0), encoding="utf-8")
    print(json.dumps({"checked": n, "with_aka": sum(1 for v in cache.values() if v["aka"]), "cached": len(cache)}))


if __name__ == "__main__":
    sys.exit(main())
