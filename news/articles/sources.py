"""The source texts of a story (spec: «the main text of up to 3 sources»).

Measured 2026-11-19 on the laptop:
- googlenewsdecoder decodes 11 of 12 Google News links;
- trafilatura extracts the text of 8 of 12, and the og:image of most.
Whether GitHub's servers may decode is measured before news goes on, and every run logs its counts.

An X post is its own text. Whatever cannot be read keeps its headline and description, so a story is never written from
nothing. The texts are for facts only (the style guide tells the writer not to copy) and are cut at 4000 characters."""
TIER = {"official": 3, "journalist": 2, "paper": 1, "aggregator": 0}
CAP = 4000


def _resolve(url):
    try:
        from googlenewsdecoder import gnewsdecoder
        r = gnewsdecoder(url, interval=1) or {}
        return r.get("decoded_url") if r.get("status") or r.get("success") else None
    except Exception:
        return None


def _fetch_html(url):
    try:
        import trafilatura
        return trafilatura.fetch_url(url)
    except Exception:
        return None


def _extract(html):
    try:
        import trafilatura
        meta = trafilatura.extract_metadata(html)
        return trafilatura.extract(html, include_comments=False) or "", (getattr(meta, "image", None) if meta else None)
    except Exception:
        return "", None


def collect(story, items, *, resolve=None, fetch_html=None, limit=3):
    resolve, fetch_html = resolve or _resolve, fetch_html or _fetch_html
    its = sorted((items[i] for i in story.get("items") or [] if i in items), key=lambda i: -TIER.get(i.get("tier"), 0))
    seen, cands = set(), []
    for it in its:
        if it.get("source") not in seen:
            seen.add(it.get("source")); cands.append(it)
    out, n = [], {"links": 0, "decoded": 0, "texts": 0}
    for it in cands[: limit + 2]:                 # two spare: an outlet that yields nothing may be beaten by the next
        url, head = it.get("url") or "", "\n".join(x for x in (it.get("title"), it.get("desc")) if x)
        text, image = "", None
        if "x.com/" in url or "twitter.com/" in url:
            text = it.get("desc") or it.get("title") or ""
        else:
            n["links"] += 1
            real = url
            if "news.google.com" in url:
                real = resolve(url)
                n["decoded"] += bool(real)
            html = fetch_html(real) if real else None
            if html:
                text, image = _extract(html)
                n["texts"] += len(text) > len(head)
            url = real or url
        out.append({"source": it.get("source"), "lang": it.get("lang"), "url": url, "tier": it.get("tier"),
                    "text": (text if len(text) > len(head) else head)[:CAP], "image": image})
    out.sort(key=lambda o: (-TIER.get(o["tier"], 0), -len(o["text"])))
    return out[:limit], n
