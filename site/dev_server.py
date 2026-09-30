"""Local preview: serves out/ and proxies /v1/* to the data CloudFront (same-origin like production) and /api/* to the
site (TIFO_API, default https://tifo.elyoxe.com: the cards Lambda behind it; point it at a local handler to test
/api/tifo/match before it is deployed)."""
import http.server, os, sys, urllib.request
DATA = os.environ.get("TIFO_DATA", "https://d1n5aqaqkowltp.cloudfront.net")
API = os.environ.get("TIFO_API", "https://tifo.elyoxe.com").rstrip("/")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def log_message(self, *a): pass
    def _proxy(self, url):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept-Encoding": "gzip"}), timeout=20) as r:
                body = r.read(); self.send_response(200); self.send_header("Content-Type", r.headers.get("Content-Type", "application/json"))
                for h in ("Content-Encoding", "Cache-Control"):
                    if r.headers.get(h): self.send_header(h, r.headers[h])
                self.end_headers(); self.wfile.write(body)
        except urllib.error.HTTPError as e: self.send_error(e.code)
    def do_GET(self):
        if self.path.startswith("/v1/"):
            return self._proxy(DATA + self.path[3:].split("?")[0])
        if self.path.startswith("/api/"):
            return self._proxy(API + self.path)
        return super().do_GET()
http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8793), H).serve_forever()
