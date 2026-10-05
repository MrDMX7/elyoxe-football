/* Local preview of the v5 build: /next/* from site/redesign/v5/out, everything else (data /v1, crests /logo, league
   logos /lg, the live site's hashed /assets) proxied to https://tifo.elyoxe.com. node site/redesign/v5/serve.cjs [port] */
"use strict";
const http = require("http"), fs = require("fs"), path = require("path"), https = require("https");
const OUT = path.join(__dirname, "out"), PORT = +(process.argv[2] || 8795), UP = "tifo.elyoxe.com";
const TYPES = { ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".txt": "text/plain" };
http.createServer((req, res) => {
  const u = new URL(req.url, "http://x"); let p = decodeURIComponent(u.pathname);
  if (p === "/") { res.writeHead(302, { location: "/next/" }); return res.end(); }
  if (p.startsWith("/next")) {
    let f = path.join(OUT, p.replace(/^\/next\/?/, ""));
    if (!path.extname(f) && !p.endsWith("/")) { res.writeHead(301, { location: p + "/" + u.search }); return res.end(); }
    if (p.endsWith("/")) f = path.join(f, "index.html");
    fs.readFile(f, (e, b) => { if (e) { res.writeHead(404, { "content-type": TYPES[".html"] }); return res.end(fs.existsSync(path.join(OUT, "404.html")) ? fs.readFileSync(path.join(OUT, "404.html")) : "404"); }
      res.writeHead(200, { "content-type": TYPES[path.extname(f)] || "application/octet-stream", "cache-control": "no-cache" }); res.end(b); });
    return;
  }
  // /v1 files are stored gzip-encoded: pass the upstream encoding through untouched
  const up = https.request({ host: UP, path: req.url, method: "GET", headers: { "accept-encoding": req.headers["accept-encoding"] || "gzip", "user-agent": "tifo-v5-preview" } }, r => {
    const h = Object.assign({}, r.headers); delete h["transfer-encoding"]; delete h["connection"];
    res.writeHead(r.statusCode, h); r.pipe(res);
  });
  up.on("error", e => { res.writeHead(502); res.end(String(e.message)); }); up.end();
}).listen(PORT, () => console.log("v5 preview on http://localhost:" + PORT + "/next/"));
