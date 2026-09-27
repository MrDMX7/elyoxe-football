/* تيفو service worker (feature 202, split in audit W1.11): pages you opened before still open with a weak signal at the stadium.
   Four caches, so a deploy no longer throws everything away:
   - tifo-assets-<V>: content-hashed /assets/, cache first; only older assets-* caches are deleted on activate.
   - tifo-crest: /logo/ and /lg/, cache first, the newest 300 kept.
   - tifo-pages: navigations, network first (navigation preload) with a 4 s budget, the newest 60 kept.
   - tifo-data: other /v1 files, network first with a 4 s budget, the newest 40 kept.
   Live data (/v1/live.json, /v1/match/*, /v1/day/*) is network only; the last copy is served only when the network fails
   outright (offline), never on a timeout, or a slow stadium connection would freeze the score. /og/ is never cached.
   Kill switch: on activate the worker reads /sw.json and unregisters itself (and clears its caches) when it says {"off":true}. */
const V = "__V__", A = "tifo-assets-" + V, CREST = "tifo-crest", PAGES = "tifo-pages", DATA = "tifo-data";
const LIMIT = { [CREST]:300, [PAGES]:60, [DATA]:40 };
self.addEventListener("install", e => { self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil((async () => {
  try { const r = await fetch("/sw.json", { cache:"no-store" }); if (r.ok && (await r.json()).off){ for (const k of await caches.keys()) if (k.startsWith("tifo-")) await caches.delete(k); await self.registration.unregister(); return; } } catch (err){}
  for (const k of await caches.keys()) if ((k.startsWith("tifo-assets-") && k !== A) || /^tifo-2-/.test(k)) await caches.delete(k);   // tifo-2-* = the pre-split single cache
  if (self.registration.navigationPreload) try { await self.registration.navigationPreload.enable(); } catch (err){}
  await self.clients.claim();
})()); });
async function put(name, req, res){ const c = await caches.open(name); await c.put(req, res); const lim = LIMIT[name]; if (!lim) return; const ks = await c.keys(); for (let i = 0; i < ks.length - lim; i++) await c.delete(ks[i]); }   // keys come back oldest first
const LIVE = /^\/v1\/(live\.json|match\/|day\/)/;
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url); if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.startsWith("/api/") || u.pathname.startsWith("/og/") || u.pathname === "/sw.json") return;
  if (u.pathname.startsWith("/assets/") || u.pathname.startsWith("/logo/") || u.pathname.startsWith("/lg/")){
    const name = u.pathname.startsWith("/assets/") ? A : CREST;
    e.respondWith(caches.open(name).then(c => c.match(e.request).then(hit => hit || fetch(e.request).then(r => { if (r.ok) e.waitUntil(put(name, e.request, r.clone())); return r; })))); return;
  }
  if (LIVE.test(u.pathname)){
    e.respondWith(fetch(e.request).then(r => { if (r.ok) e.waitUntil(put(DATA, e.request, r.clone())); return r; }, err => caches.match(e.request).then(hit => { if (hit) return hit; throw err; }))); return;
  }
  const name = e.request.mode === "navigate" ? PAGES : DATA;
  e.respondWith((async () => {
    const net = (async () => { const pre = e.request.mode === "navigate" && e.preloadResponse ? await e.preloadResponse : null; const r = pre || await fetch(e.request); if (r.ok) e.waitUntil(put(name, e.request, r.clone())); return r; })();
    e.waitUntil(net.catch(() => {}));   // a response that lands after the budget still refreshes the cache
    const slow = new Promise(ok => setTimeout(ok, 4000)).then(() => caches.match(e.request)).then(hit => hit || net);
    return Promise.race([net.catch(() => caches.match(e.request).then(hit => { if (hit) return hit; throw new Error("offline"); })), slow]);
  })());
});
