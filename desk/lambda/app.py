"""The desk's API (Phase 2b; spec, «The desk»): one Lambda behind an HTTP API, ap-south-1, stack tifo-desk (desk/deploy.py).

  GET  /                the page (desk.html); it holds no data
  GET  /api/view        the queue (state/articles/desk-view.json, written by every journal run), what was published, the spend
  POST /api/act         {action: reject | unreject | write | unwrite | withdraw, id} -> state/articles/desk.json; withdraw also
                        takes the article off both lists at once (the static page goes with the next hourly build)
  GET  /api/article     ?id= -> the article, its versions, its photo candidates and the numbers its fact sheet holds
  POST /api/edit        {id, headline, standfirst, sections, facts_box} -> a new version, marked edited (never rewritten)
  POST /api/restore     {id, version} -> that version back, as a new version
  POST /api/photo       {id, url, source, caption} -> one of the sheet's photo candidates, cropped and stored at Tifo

Every /api call carries the key in x-desk-key; the key is the SSM SecureString /tifo/desk-key, never in the repo, and the
owner's link carries it in the fragment (#k=…), which no server log sees. The Lambda writes the store's own format
(s3store.py) and the lists through news/articles/publish.py itself (copied into the bundle)."""
import base64, hmac, io, json, os, re, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
try:
    import publish                      # the bundle's copy of news/articles/publish.py
except ImportError:                     # the tests, from the repo
    from news.articles import publish
import s3store

HERE = Path(__file__).resolve().parent
SITE = "https://tifo.elyoxe.com"
CAP = 180.0
DESK, VIEW, SPEND = "articles/desk.json", "articles/desk-view.json", "articles/spend.json"
ACTIONS = {"reject", "unreject", "write", "unwrite", "withdraw"}
ID = re.compile(r"[A-Za-z0-9_-]{1,80}")
JSON = "application/json; charset=utf-8"


def _fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (tifo-desk)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read()
    except Exception:
        return None


class App:
    def __init__(self, store, key, now=None, fetch=None):
        self.store, self.key = store, key
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.fetch = fetch or _fetch

    # ---- plumbing
    def handle(self, method, path, query, body, headers):
        path = path.rstrip("/") or "/"
        if method == "GET" and path in ("/", "/desk"):
            return 200, (HERE / "desk.html").read_text(encoding="utf-8"), "text/html; charset=utf-8"
        if not path.startswith("/api/"):
            return 404, {"error": "not found"}, JSON
        given = (headers or {}).get("x-desk-key") or ""
        if not self.key or not hmac.compare_digest(given.encode(), self.key.encode()):
            return 401, {"error": "key"}, JSON
        try:
            b = json.loads(body) if body else {}
        except ValueError:
            return 400, {"error": "body is not JSON"}, JSON
        route = {("GET", "/api/view"): self.view, ("POST", "/api/act"): self.act, ("GET", "/api/article"): self.article,
                 ("POST", "/api/edit"): self.edit, ("POST", "/api/restore"): self.restore, ("POST", "/api/photo"): self.photo}.get((method, path))
        if not route:
            return 404, {"error": "not found"}, JSON
        status, out = route(query or {}, b)
        return status, out, JSON

    def _doc(self, aid):
        return self.store.get_json(f"news/a/{aid}.json") if ID.fullmatch(aid or "") else None

    def _version(self, doc):
        self.store.put_state(f"articles/versions/{doc['id']}/{doc.get('version') or 1}.json", doc)

    def _publish(self, doc, **change):
        new = dict(doc, **change, edited=True, modified=self.now().isoformat(), version=(doc.get("version") or 1) + 1)
        publish.publish(self.store, new)
        return new

    # ---- routes
    def view(self, q, b):
        sp = (self.store.get_state(SPEND) or {}).get(self.now().strftime("%Y-%m")) or {"usd": 0.0, "calls": 0, "by_type": {}, "capped": False}
        pub = (self.store.get_json("news/articles.json") or {}).get("articles") or []
        return 200, {"view": self.store.get_state(VIEW) or {}, "desk": self.store.get_state(DESK) or {}, "published": pub[:150],
                     "spend": sp, "cap": CAP, "now": self.now().isoformat()}

    def act(self, q, b):
        a, i = b.get("action"), str(b.get("id") or "")
        if a not in ACTIONS or not ID.fullmatch(i):
            return 400, {"error": "action or id"}
        now = self.now()
        d = self.store.get_state(DESK) or {}
        for k in ("reject", "write", "withdraw"):
            d.setdefault(k, {})
        old = (now - timedelta(days=3)).isoformat()
        for k in ("reject", "write"):                        # the queue forgets a story after a day; keep three
            d[k] = {s: at for s, at in d[k].items() if at >= old}
        if a == "reject":
            d["reject"][i] = now.isoformat(); d["write"].pop(i, None)
        elif a == "unreject":
            d["reject"].pop(i, None)
        elif a == "write":
            d["write"][i] = now.isoformat(); d["reject"].pop(i, None)
        elif a == "unwrite":
            d["write"].pop(i, None)
        elif a == "withdraw":
            d["withdraw"][i] = now.isoformat()
            publish.withdraw(self.store, i, now.isoformat())
        self.store.put_state(DESK, d)
        return 200, {"desk": d}

    def article(self, q, b):
        aid = str(q.get("id") or "")
        doc = self._doc(aid)
        if not doc:
            return 404, {"error": "no such article"}
        kept = self.store.get_state(f"articles/sheets/{aid}.json") or {}
        nums = sorted(set(re.findall(r"\d+(?:[.,]\d+)?", json.dumps(kept.get("sheet") or {}, ensure_ascii=False))), key=lambda x: (len(x), x))
        versions = []
        for k in self.store.state_keys(f"articles/versions/{aid}/"):
            m = re.search(r"/(\d+)\.json$", k)
            v = self.store.get_state(k) if m else None
            if v:
                versions.append({"version": int(m.group(1)), "headline": v.get("headline"), "modified": v.get("modified"), "edited": bool(v.get("edited"))})
        versions.sort(key=lambda v: v["version"])
        return 200, {"doc": doc, "versions": versions, "photos": kept.get("photos") or [], "numbers": nums}

    def edit(self, q, b):
        doc = self._doc(str(b.get("id") or ""))
        if not doc:
            return 404, {"error": "no such article"}
        change = {}
        if "headline" in b:
            h = str(b["headline"] or "").strip()
            if not h or len(h) > 200:
                return 400, {"error": "headline"}
            change["headline"] = h
        if "standfirst" in b:
            change["standfirst"] = str(b["standfirst"] or "").strip()
        if "sections" in b:
            secs = b["sections"]
            if not isinstance(secs, list) or not all(isinstance(s, dict) and isinstance(s.get("paragraphs"), list) for s in secs):
                return 400, {"error": "sections"}
            change["sections"] = [{"subhead": str(s.get("subhead") or "").strip(),
                                   "paragraphs": [str(p).strip() for p in s["paragraphs"] if str(p).strip()]} for s in secs]
            change["sections"] = [s for s in change["sections"] if s["paragraphs"]]
            if not change["sections"]:
                return 400, {"error": "an article needs a paragraph"}
        if "facts_box" in b:
            change["facts_box"] = [str(f).strip() for f in b["facts_box"] or [] if str(f).strip()]
        self._version(doc)
        return 200, {"doc": self._publish(doc, **change)}

    def restore(self, q, b):
        doc = self._doc(str(b.get("id") or ""))
        try:
            n = int(b.get("version"))
        except (TypeError, ValueError):
            return 400, {"error": "version"}
        old = self.store.get_state(f"articles/versions/{doc['id']}/{n}.json") if doc else None
        if not old:
            return 404, {"error": "no such version"}
        self._version(doc)
        keep = {k: old.get(k) for k in ("headline", "standfirst", "sections", "facts_box", "image") if k in old}
        return 200, {"doc": self._publish(doc, **keep)}

    def photo(self, q, b):
        from PIL import Image
        doc = self._doc(str(b.get("id") or ""))
        if not doc:
            return 404, {"error": "no such article"}
        kept = self.store.get_state(f"articles/sheets/{doc['id']}.json") or {}
        url = str(b.get("url") or "")
        if url not in {p.get("url") for p in kept.get("photos") or []}:      # only the photos the sources carried
            return 400, {"error": "not one of this article's photos"}
        raw = self.fetch(url)
        try:
            im = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:
            return 400, {"error": "the photo could not be read"}
        if im.width < 600:
            return 400, {"error": "the photo is too small"}
        w, h = im.size
        if w * 9 > h * 16:
            nw = round(h * 16 / 9); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = round(w * 9 / 16); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
        im = im.resize((1200, 675), Image.LANCZOS)
        out = io.BytesIO(); im.save(out, "JPEG", quality=86, optimize=True)
        name = f"news/img/{doc['id']}-{(doc.get('version') or 1) + 1}.jpg"     # a new key: no cached copy of the old one
        self.store.put_bytes(name, out.getvalue(), "image/jpeg", cache="static")
        who = str(b.get("caption") or "").strip()
        src = str(b.get("source") or "").strip()
        cap = (f"{who} — " if who else "") + (f"الصورة من {src}" if src else "")
        self._version(doc)
        img = {"url": f"{SITE}/v1/{name}", "w": 1200, "h": 675, "caption": cap, "source": "desk", "card": False}
        return 200, {"doc": self._publish(doc, image=img)}


_app = None


def handler(event, context):
    global _app
    if _app is None:
        import boto3
        key = boto3.client("ssm").get_parameter(Name=os.environ["KEY_PARAM"], WithDecryption=True)["Parameter"]["Value"]
        _app = App(s3store.Store(s3store.S3Backend(os.environ["BUCKET"])), key)
    http = (event.get("requestContext") or {}).get("http") or {}
    body = event.get("body") or ""
    if event.get("isBase64Encoded") and body:
        body = base64.b64decode(body).decode("utf-8")
    status, out, ctype = _app.handle(http.get("method", "GET"), event.get("rawPath") or "/", event.get("queryStringParameters") or {},
                                     body, {k.lower(): v for k, v in (event.get("headers") or {}).items()})
    return {"statusCode": status, "body": out if isinstance(out, str) else json.dumps(out, ensure_ascii=False),
            "headers": {"content-type": ctype, "cache-control": "no-store", "x-robots-tag": "noindex, nofollow", "referrer-policy": "no-referrer"}}
