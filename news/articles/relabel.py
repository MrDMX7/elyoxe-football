"""The labels of the articles written before they labelled themselves (owner 2026-11-19: «خيتافي يستثمر 45 مليون يورو لتوسيع
الكوليسيوم» carried «انتقالات · إشاعة»: the journal's keyword rules read «renovación» in the source as a contract renewal).

Every journal run, after the news: each live news article without `labelled` gets its label from Haiku (Writer.label, the same
call a new article makes), its doc and the list's summary are updated, and the fast «Article pages» step is told to re-render
every page (state articles/pages.json `built` cleared). `modified` is left alone: a label is not an edit. An article whose call
fails is tried again next run. Ends by itself once every article is labelled."""
import json

LIMIT = 80
MODEL = "claude-haiku-5-5"
PAGES = "articles/pages.json"


def run(store, writer, sp, *, deadline, clock, limit=LIMIT):
    all_ = (store.get_json("news/articles-all.json") or {}).get("articles") or []
    todo, done, failed = [], {}, 0
    for a in all_:
        if a.get("kind") != "news":
            continue
        d = store.get_json(f"news/a/{a['id']}.json")
        if d and not d.get("labelled"):
            todo.append(d)
    for d in todo[:limit]:
        if clock() > deadline or not sp.allowed():
            break
        try:
            topic, stage, usage = writer.label(d, model=MODEL)
        except Exception as e:
            failed += 1
            print(json.dumps({"relabel_error": d["id"], "error": f"{type(e).__name__}: {str(e)[:120]}"}, ensure_ascii=False))
            continue
        sp.add(MODEL, usage, "label")
        d["topic"], d["stage"], d["labelled"] = topic, stage, 1
        store.put_json(f"news/a/{d['id']}.json", d, cache="warm")
        done[d["id"]] = (topic, stage)
    if done:
        sp.save()
        lst = store.get_json("news/articles.json") or {}           # read now: the run may have added articles meanwhile
        for a in lst.get("articles") or []:
            if a["id"] in done:
                a["topic"], a["stage"] = done[a["id"]]
        store.put_json("news/articles.json", lst, cache="hot")
        pages = store.get_state(PAGES)
        if pages:
            pages["built"] = None                                    # the fast step renders every page again this run
            store.put_state(PAGES, pages)
    return {"labelled": len(done), "failed": failed, "left": len(todo) - len(done)}
