"""The article as Tifo publishes it: v1/news/a/<id>.json and the list v1/news/articles.json (newest first, 500 kept). The
hourly site build turns both into /news/<id>/ pages (site/lib/articles.cjs)."""
AUTHOR = "تحرير تيفو"
KEEP = 500


def article_doc(aid, kind, art, meta, image, model, now_iso, prev=None):
    ents = [["team", t] for t in meta.get("teams") or []] + [["player", p] for p in (meta.get("players") or [])[:30]]
    return {"id": aid, "kind": kind, "headline": art["headline"], "standfirst": art["standfirst"], "sections": art["sections"],
            "facts_box": art.get("facts_box") or [], "image": image, "author": AUTHOR, "match": meta.get("match"),
            "comp": meta.get("comp"), "entities": ents, "model": model,
            "published": (prev or {}).get("published") or now_iso, "modified": now_iso,
            "version": ((prev or {}).get("version") or 0) + 1}


def summary(doc):
    return {k: doc.get(k) for k in ("id", "kind", "headline", "standfirst", "image", "published", "modified", "match", "comp", "entities")}


ALL = "news/articles-all.json"    # every article ever published, no limit: the site builds a page for each (final review, finding 3)


def _lists(store, aid, entry, now_iso):
    for path, keep, cache, item in (("news/articles.json", KEEP, "hot", entry), (ALL, None, "warm", entry and {k: entry[k] for k in ("id", "kind", "published", "modified", "match")})):
        lst = [a for a in (store.get_json(path) or {}).get("articles") or [] if a["id"] != aid] + ([item] if item else [])
        lst.sort(key=lambda a: a["published"], reverse=True)
        store.put_json(path, {"generated": now_iso, "articles": lst[:keep] if keep else lst}, cache=cache)


def publish(store, doc):
    store.put_json(f"news/a/{doc['id']}.json", doc, cache="warm")
    _lists(store, doc["id"], summary(doc), doc["modified"])


def withdraw(store, aid, now_iso):
    """Off both lists: the next site build drops its page (a report its corrected match could not be rewritten for)."""
    _lists(store, aid, None, now_iso)
