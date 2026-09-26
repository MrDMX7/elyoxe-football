"""Local preview: serves out/ and proxies /v1/* to the data CloudFront (same-origin like production)."""
import http.server, os, sys, urllib.request
DATA = os.environ.get("TIFO_DATA", "https://d1n5aqaqkowltp.cloudfront.net")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith("/v1/"):
            try:
                with urllib.request.urlopen(DATA + self.path[3:].split("?")[0], timeout=20) as r:
                    body = r.read(); self.send_response(200); self.send_header("Content-Type", r.headers.get("Content-Type", "application/json"))
                    if r.headers.get("Content-Encoding"): self.send_header("Content-Encoding", r.headers["Content-Encoding"])
                    self.end_headers(); self.wfile.write(body)
            except urllib.error.HTTPError as e: self.send_error(e.code)
            return
        return super().do_GET()
http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8793), H).serve_forever()
