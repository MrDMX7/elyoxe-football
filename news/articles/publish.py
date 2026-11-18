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


def publish(store, doc):
    store.put_json(f"news/a/{doc['id']}.json", doc, cache="warm")
    lst = (store.get_json("news/articles.json") or {}).get("articles") or []
    lst = [a for a in lst if a["id"] != doc["id"]] + [summary(doc)]
    lst.sort(key=lambda a: a["published"], reverse=True)
    store.put_json("news/articles.json", {"generated": doc["modified"], "articles": lst[:KEEP]}, cache="hot")
