"""Arabic for the names the live pages still show in Latin letters (23 Nov 2026, the integrity check: /arabs/ 88 % Latin — the
Arab referees and coaches abroad —, /memorable/ 75 %, /messi/ 73 %, /worldcup-arabs/ 66 %, the transfers 44 %: names the
page data carries in English and no names file knows).

    python -m names.site_latin [--base https://tifo.elyoxe.com] [--every 400] [--sample 60]

1. the pages: every page of a kind with up to --every pages in the sitemaps (the editorial pages), --sample of a bigger kind;
2. the names: each <span class="lat"> the build's dictionary pass left (lib/latin_ar.cjs), not the Latin subtitle under an
   Arabic name; the most seen first;
3. Gemini, with the sections a name appears in as the hint (a referee on /arabs/, a club on /transfers/). A website, paper,
   channel or app keeps its Latin name: kept with an empty Arabic, never asked again.

Out: names/site_latin_ar.json {latin: {latin, ar, kinds, source, checked}}, saved after every batch; site/build.cjs reads it
over the other names files (lib/latin_ar.cjs extend)."""
import argparse, html as H, json, os, random, re, sys, time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "site_latin_ar.json")
ARABIC = re.compile("[%s-%s]" % (chr(0x600), chr(0x6FF)))
SPAN = re.compile(r'(<p class="muted">)?<span class="lat">([^<]{2,80})</span>')
PROMPT = """You are an Arabic sports editor (beIN Sports, Kooora, Al Ittihad). Each line is a name an Arabic football site still shows in
Latin letters, with the site's sections it appears in: a player, coach or referee; a club or national team; a country or city;
a competition or an award; a stadium. Write it in Arabic exactly as Arab sports media write it. An Arab's real Arabic name
("Mustapha Ghorbal" -> "مصطفى غربال", "Sami Al-Jaber" -> "سامي الجابر"); anyone else as Arab media transliterate him
("Harry Kane" -> "هاري كين", "Nicolás Otamendi" -> "نيكولاس أوتاميندي"); clubs, countries, competitions and awards by
their Arab media name ("Brighton & Hove Albion" -> "برايتون", "USA" -> "الولايات المتحدة", "South American Coach of the
Year" -> "أفضل مدرب في أمريكا الجنوبية"). A website, newspaper, TV channel, agency or app (Kooora, BBC Sport,
Transfermarkt, Sky Sports) keeps its Latin name: return an empty string for it. Arabic script only, no diacritics, no Latin
letters; digits are fine. Return one item per input, with the same id."""


def spans(page):
    """the Latin names a page still shows -> {name: times}; the subtitle under an Arabic name is the original, not a gap"""
    out = Counter()
    for sub, la in SPAN.findall(page):
        la = H.unescape(la).strip()
        if not sub and len(la) > 1:
            out[la] += 1
    return dict(out)


def pages(paths, every=400, sample=60, seed=1):
    from tools.integrity import kind
    by = defaultdict(list)
    for p in paths:
        by[kind(p)].append(p)
    rnd = random.Random(seed)
    return [p for k, ps in sorted(by.items()) for p in (ps if len(ps) <= every else rnd.sample(ps, sample))]


def accept(ar):
    ar = (ar or "").strip()
    return ar if ar and ARABIC.search(ar) and not re.search(r"[A-Za-z]", ar) else None


def todo(seen, have, kept=()):
    return [n for n in sorted(seen, key=lambda n: (-seen[n], n)) if n not in have and n not in kept]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://tifo.elyoxe.com")
    ap.add_argument("--every", type=int, default=400)
    ap.add_argument("--sample", type=int, default=60)
    ap.add_argument("--batch", type=int, default=60)
    a = ap.parse_args(argv)
    sys.path.insert(0, os.path.dirname(HERE))
    from tools.integrity import fetch, kind, sitemap_paths
    from names import build_names as B
    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}

    def save():
        tmp = OUT + ".tmp"
        for t in range(6):
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(out, f, ensure_ascii=False, indent=0, sort_keys=True)
                os.replace(tmp, OUT)
                return
            except OSError:
                time.sleep(2 * (t + 1))
        raise OSError(f"could not write {OUT}")
    ps = pages(sitemap_paths(a.base), a.every, a.sample)
    print(f"{len(ps)} pages to read", flush=True)
    seen, kinds = Counter(), defaultdict(set)
    with ThreadPoolExecutor(16) as ex:
        for p, (st, h) in zip(ps, ex.map(lambda p: fetch(a.base + p), ps)):
            if st == 200:
                for n, c in spans(h).items():
                    seen[n] += c
                    kinds[n].add(kind(p))
    names = todo(seen, out)
    print(f"{len(seen)} names in Latin letters on them; {len(names)} to name", flush=True)
    key = B.gemini_key()
    if not key:
        print("no Gemini key")
        return 1
    today = date.today().isoformat()
    for i in range(0, len(names), a.batch):
        chunk = names[i:i + a.batch]
        ids = {str(j): n for j, n in enumerate(chunk)}
        got = B.gemini_call(key, PROMPT + "\n\nid\tname\tsections\n" + "\n".join(f"{j}\t{n}\t{', '.join(sorted(kinds[n]))}" for j, n in ids.items()), len(chunk))
        if not got:
            continue
        for j, n in ids.items():
            ar = accept(got.get(j))
            out[n] = {"latin": n, "ar": ar or "", "kinds": sorted(kinds[n]), "source": "generated" if ar else "kept", "checked": today}
        save()
        print(f"  {min(i + a.batch, len(names))}/{len(names)}", flush=True)
        time.sleep(0.5)
    print(f"done: {sum(1 for v in out.values() if v['ar'])} named, {sum(1 for v in out.values() if not v['ar'])} kept in Latin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
