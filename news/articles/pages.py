"""The fast «Article pages» step (docs/superpowers/specs/2026-11-19-articles-pages-design.md §7), in the journal workflow after
«Tifo articles»: every article page written or changed since the last run is up within the minute, not at the next hourly build.

  - the full build's shells (state/site/shells.json: its own page() for an article and for /news/, tools/runner.py saves them);
  - what changed: an article whose `modified` differs from the last render (a new article, an update, a desk edit), or every
    article when the shells are new; an article gone from news/articles-all.json (withdrawn) has its page deleted;
  - site/lib/render_news.cjs fills the shells; the files go to the site bucket with the full build's headers
    (tools/s3push.py TYPES, public,max-age=60); every page is cached 60 s, so nothing needs invalidating;
  - the new URLs go to IndexNow (Bing), like the full build's.

The hourly build no longer uploads or deletes these paths (tools/runner.py FAST_OWNED). State: state/articles/pages.json.
  python -m news.articles.pages"""
import hashlib, json, subprocess, sys, tempfile, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.s3push import TYPES  # noqa: E402

SITE = "https://tifo.elyoxe.com"
STATE, SHELLS = "articles/pages.json", "site/shells.json"
RENDERER = ROOT / "site" / "lib" / "render_news.cjs"


def shell_key(shells):
    """What the pages are made of: the shells (not their hourly timestamp), the stylesheet and the page code. A change in any
    of them re-renders every page; the full build saving the same shells again re-renders nothing."""
    h = hashlib.sha1()
    for part in (shells.get("article") or "", shells.get("news") or ""):
        h.update(part.encode("utf-8"))
    for f in ("articles.css", "articles.cjs", "render_news.cjs"):
        h.update((ROOT / "site" / "lib" / f).read_bytes())
    return h.hexdigest()[:16]


def plan(all_, seen, built):
    pages = seen.get("pages") or {}
    fresh = built != seen.get("built")
    render = [a["id"] for a in all_ if fresh or pages.get(a["id"]) != a.get("modified")]
    ids = {a["id"] for a in all_}
    return render, sorted(k for k in pages if k not in ids)


def render_node(payload, out_dir):
    f = Path(out_dir) / "_input.json"
    f.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    subprocess.run(["node", str(RENDERER), str(f), str(out_dir)], check=True, timeout=180, capture_output=True)
    f.unlink()


def run(store, s3, bucket, *, teams, players, render=render_node, indexnow=None, now=None):
    shells = store.get_state(SHELLS)
    if not shells:
        return {"skipped": "no shells yet: the next full build saves them"}
    all_ = (store.get_json("news/articles-all.json") or {}).get("articles") or []
    lst = (store.get_json("news/articles.json") or {}).get("articles") or []
    seen = store.get_state(STATE) or {}
    key = shell_key(shells)
    rids, dels = plan(all_, seen, key)
    if not rids and not dels:
        return {"rendered": 0, "deleted": 0}
    with ThreadPoolExecutor(16) as ex:
        docs = [d for d in ex.map(lambda i: store.get_json(f"news/a/{i}.json"), rids) if d]
    tmp = Path(tempfile.mkdtemp())
    render({"shells": shells, "docs": docs, "list": lst, "teams": teams, "players": players, "now": int((now or time.time()) * 1000)}, tmp)
    files = [p for p in tmp.rglob("*") if p.is_file()]

    def put(p):
        key = p.relative_to(tmp).as_posix()
        cc = "public,max-age=31536000,immutable" if p.suffix == ".css" else "public,max-age=60"     # the CSS is named by its content
        s3.put_object(Bucket=bucket, Key=key, Body=p.read_bytes(), ContentType=TYPES.get(p.suffix.lower(), "application/octet-stream"), CacheControl=cc)

    with ThreadPoolExecutor(16) as ex:
        list(ex.map(put, files))
    for i in dels:
        s3.delete_object(Bucket=bucket, Key=f"news/{i}/index.html")
    known = seen.get("pages") or {}
    new = [f"{SITE}/news/{d['id']}/" for d in docs if d["id"] not in known]
    if new and indexnow:
        try:
            indexnow(new)
        except Exception as e:
            print(json.dumps({"indexnow_error": str(e)[:200]}))
    pages = {k: v for k, v in known.items() if k not in dels}
    pages.update({d["id"]: d.get("modified") for d in docs})
    store.put_state(STATE, {"built": key, "pages": pages})
    return {"rendered": len(docs), "deleted": len(dels), "uploaded": len(files), "new": len(new)}


def _indexnow(urls):
    from tools.runner import INDEXNOW_KEY
    body = json.dumps({"host": "tifo.elyoxe.com", "key": INDEXNOW_KEY, "keyLocation": f"{SITE}/{INDEXNOW_KEY}.txt", "urlList": urls}).encode()
    urllib.request.urlopen(urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                                  headers={"Content-Type": "application/json; charset=utf-8"}), timeout=30)


def main():
    import boto3
    from store import Store, S3Backend
    from news.articles.run import BUCKET
    cf = boto3.client("cloudformation", region_name="ap-south-1")
    outs = {o["OutputKey"]: o["OutputValue"] for o in cf.describe_stacks(StackName="elyoxe-tifo-site")["Stacks"][0]["Outputs"]}
    store = Store(S3Backend(BUCKET))
    tj = store.get_json("teams.json") or {}
    teams = {k: {"name_ar": v.get("name_ar")} for k, v in (tj.get("teams", tj) or {}).items() if isinstance(v, dict) and v.get("name_ar")}
    try:
        players = json.loads((ROOT / "names" / "players_ar.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        players = {}
    out = run(store, boto3.client("s3", region_name="ap-south-1"), outs["Bucket"], teams=teams, players=players, indexnow=_indexnow)
    print(json.dumps({"article_pages": out}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
