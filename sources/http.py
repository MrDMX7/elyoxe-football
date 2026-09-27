"""A polite HTTP client shared by every adapter (stdlib only: the Lambda bundle stays tiny).

* Browser User-Agent, gzip accepted, 15 s timeout, one retry on 5xx/timeout (never on 4xx).
* Honours the source's own cache: a response is reused until its Cache-Control max-age runs out
  (FotMob: 10 s during live matches, 40 s otherwise, 7 days for the translation map). A warm Lambda
  container keeps the cache across invocations, so polling faster than the source refreshes costs
  FotMob nothing. `min_ttl` lets a caller ask for at least that much reuse.
* data.fotmob.com answers gzip even when not asked; bodies are un-gzipped by magic bytes.
* Every call is counted per host (for health.json and the cost model).
"""
import gzip, json, re, time, urllib.error, urllib.request
from urllib.parse import urlparse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/140.0.0.0 Safari/537.36")
_MAXAGE = re.compile(r"(?:s-)?max-age=(\d+)")
# a 403 on these means the source is refusing us (not one dead stats URL): back the whole host off
CORE_FEEDS = ("/api/data/matches?", "/api/data/matchDetails?", "/api/data/leagues?")


class FetchError(Exception):
    def __init__(self, url, msg, status=None):
        super().__init__(f"{msg} ({url})")
        self.url, self.status = url, status


class Http:
    def __init__(self, timeout=15, clock=time.monotonic):
        self.timeout = timeout
        self.clock = clock
        self._cache: dict[str, tuple[float, bytes]] = {}
        self.calls: dict[str, int] = {}
        self.ok: dict[str, int] = {}          # per host: fetches that returned a body (after the retry)
        self.failed: dict[str, int] = {}      # per host: fetches that raised FetchError (HTTP error, timeout, bad JSON)
        self.backoff: dict[str, tuple[float, float]] = {}   # host -> (until, seconds): after a 429, or a 403 on a core feed
        self.network_calls = 0

    def _ttl(self, headers) -> int:
        cc = headers.get("cache-control") or ""
        if "no-cache" in cc or "no-store" in cc:
            return 0
        m = _MAXAGE.findall(cc)
        return min(int(x) for x in m) if m else 0

    def get_bytes(self, url, headers=None, min_ttl=0) -> bytes:
        now = self.clock()
        if len(self._cache) > 20:   # a warm container lives for hours: drop expired bodies (memory)
            for k in [k for k, v in self._cache.items() if v[0] <= now]:
                del self._cache[k]
        hit = self._cache.get(url)
        if hit and hit[0] > now:
            return hit[1]
        host = urlparse(url).netloc
        bo = self.backoff.get(host)
        if bo and bo[0] > now:      # rate-limited or refused: no request, the caller keeps its last good file
            self.failed[host] = self.failed.get(host, 0) + 1
            raise FetchError(url, f"backing off {host} for {bo[0] - now:.0f} s after a 429/403", 429)
        h = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
             "Accept-Encoding": "gzip", "Accept-Language": "en-US,en;q=0.9,ar;q=0.8"}
        h.update(headers or {})
        last = None
        for attempt in (1, 2):
            self.calls[host] = self.calls.get(host, 0) + 1
            self.network_calls += 1
            try:
                req = urllib.request.Request(url, headers=h)
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    body = r.read()
                    ttl = self._ttl(r.headers)
                if body[:2] == b"\x1f\x8b":
                    body = gzip.decompress(body)
                ttl = max(ttl, min_ttl)
                if ttl > 0:
                    self._cache[url] = (self.clock() + ttl, body)
                self.ok[host] = self.ok.get(host, 0) + 1
                self.backoff.pop(host, None)
                return body
            except urllib.error.HTTPError as e:
                last = FetchError(url, f"HTTP {e.code}", e.code)
                if e.code == 429 or (e.code == 403 and any(k in url for k in CORE_FEEDS)):
                    prev = (self.backoff.get(host) or (0, 0))[1]
                    secs = min(600, max(60, 2 * prev))           # 60 s, 120 s ... 10 min
                    self.backoff[host] = (self.clock() + secs, secs)
                if e.code < 500:
                    break
            except Exception as e:  # timeout, DNS, reset
                last = FetchError(url, f"{type(e).__name__}: {e}")
            if attempt == 1:
                time.sleep(1.0)
        self.failed[host] = self.failed.get(host, 0) + 1
        raise last

    def get_json(self, url, headers=None, min_ttl=0):
        body = self.get_bytes(url, headers, min_ttl)
        try:
            return json.loads(body)
        except ValueError as e:
            self._cache.pop(url, None)
            host = urlparse(url).netloc
            self.ok[host] = max(0, self.ok.get(host, 0) - 1)
            self.failed[host] = self.failed.get(host, 0) + 1
            raise FetchError(url, f"bad JSON: {e}")
