/* تيفو service worker (feature 202): pages you opened before still open with a weak signal at the stadium.
   Assets and crests: cache first (content-hashed / stable). Live data (/v1/live.json, /v1/match/*, /v1/day/*): network
   only, and the last copy is served only when the network fails outright (offline); never a timeout fallback, or a slow
   stadium connection would freeze the score. Pages and other /v1 files: network first with a 4 s budget, then the last
   copy, and a response that arrives after the budget still refreshes the cache. */
const V = "tifo-2-__V__";
self.addEventListener("install", e => { self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith("tifo-") && k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
const LIVE = /^\/v1\/(live\.json|match\/|day\/)/;
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url); if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.startsWith("/api/")) return;
  if (u.pathname.startsWith("/assets/") || u.pathname.startsWith("/logo/") || u.pathname.startsWith("/og/")){
    e.respondWith(caches.open(V).then(c => c.match(e.request).then(hit => hit || fetch(e.request).then(r => { if (r.ok) c.put(e.request, r.clone()); return r; })))); return;
  }
  if (LIVE.test(u.pathname)){
    e.respondWith(caches.open(V).then(c => fetch(e.request).then(r => { if (r.ok) c.put(e.request, r.clone()); return r; }, err => c.match(e.request).then(hit => { if (hit) return hit; throw err; })))); return;
  }
  e.respondWith(caches.open(V).then(c => {
    const net = fetch(e.request).then(r => { if (r.ok) c.put(e.request, r.clone()); return r; });   // caches the response even when it lands after the budget
    e.waitUntil(net.catch(() => {}));
    const slow = new Promise(ok => setTimeout(ok, 4000)).then(() => c.match(e.request)).then(hit => hit || net);
    return Promise.race([net.catch(() => c.match(e.request).then(hit => { if (hit) return hit; throw new Error("offline"); })), slow]);
  }));
});
