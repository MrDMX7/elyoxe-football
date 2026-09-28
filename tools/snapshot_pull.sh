#!/usr/bin/env bash
# snapshot_pull.sh: unpack the `data-snapshot` branch (made by snapshot_push.sh) and serve the data locally.
#   bash tools/snapshot_pull.sh [dest]        dest defaults to ./.snapshot (gitignored via .git/info/exclude)
#   it starts a local data server in the background (SNAP_PORT, default 8765); then build against it:
#          TIFO_DATA=http://127.0.0.1:8765 node site/build.cjs
#   site/cache is restored in place (files in git are kept); the research dir goes to ~/workspace/research/
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$(realpath -m "${1:-$REPO/.snapshot}")" PORT="${SNAP_PORT:-8765}"
grep -qx '.snapshot/' "$REPO/.git/info/exclude" 2>/dev/null || echo '.snapshot/' >> "$REPO/.git/info/exclude"
git -C "$REPO" fetch origin data-snapshot
rm -rf "$DEST"; mkdir -p "$DEST/parts" "$DEST/snap"
git -C "$REPO" archive FETCH_HEAD | tar -x -C "$DEST/parts"
( cd "$DEST/parts" && sha256sum -c --quiet SHA256SUMS )
cat "$DEST/parts/MANIFEST.txt"
cat "$DEST/parts"/snap.tgz.* | tar -xz -C "$DEST/snap"
rm -rf "$DEST/parts"/snap.tgz.*
[ -d "$DEST/snap/site-cache" ] && cp -a "$DEST/snap/site-cache/." "$REPO/site/cache/"
[ -d "$DEST/snap/research" ] && { mkdir -p "$HOME/workspace/research"; rm -rf "$HOME/workspace/research/tifo-2026-09-27"; cp -a "$DEST/snap/research" "$HOME/workspace/research/tifo-2026-09-27"; }
[ -d "$DEST/snap/v1" ] || { echo "no v1/ in the snapshot (made with SNAP_NO_S3=1?)"; exit 0; }

# the bucket stores JSON as gzip bytes; send them with Content-Encoding: gzip like CloudFront does
cat > "$DEST/serve.py" <<'PY'
import http.server, os, sys
ROOT = sys.argv[1]
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def log_message(self, *a): pass
    def end_headers(self):
        p = self.translate_path(self.path)
        if os.path.isfile(p):
            with open(p, "rb") as f:
                if f.read(2) == b"\x1f\x8b": self.send_header("Content-Encoding", "gzip")
        self.send_header("Access-Control-Allow-Origin", "*"); super().end_headers()
    def guess_type(self, p): return "application/json" if p.endswith(".json") else super().guess_type(p)
http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[2])), H).serve_forever()
PY
pkill -f "$DEST/serve.py" 2>/dev/null || true
nohup python3 "$DEST/serve.py" "$DEST/snap/v1" "$PORT" > "$DEST/serve.log" 2>&1 &
sleep 1
curl -s --compressed -o /dev/null -w "data server: %{http_code} http://127.0.0.1:$PORT/index.json\n" "http://127.0.0.1:$PORT/index.json"
echo "build: TIFO_DATA=http://127.0.0.1:$PORT node site/build.cjs"
