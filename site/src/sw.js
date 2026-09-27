/* تيفو service worker (feature 202): pages you opened before still open with a weak signal at the stadium.
   Assets and crests: cache first (content-hashed / stable). Pages and /v1 data: network first with a 4 s budget, then the
   last copy. Live data is never served stale on purpose; the cached copy is only a fallback when the network fails. */
const V = "tifo-__V__";
self.addEventListener("install", e => { self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith("tifo-") && k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
function timeout(p, ms){ return new Promise((ok, no) => { const t = setTimeout(() => no(new Error("slow")), ms); p.then(r => { clearTimeout(t); ok(r); }, e => { clearTimeout(t); no(e); }); }); }
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url); if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.startsWith("/api/")) return;
  if (u.pathname.startsWith("/assets/") || u.pathname.startsWith("/logo/") || u.pathname.startsWith("/og/")){
    e.respondWith(caches.open(V).then(c => c.match(e.request).then(hit => hit || fetch(e.request).then(r => { if (r.ok) c.put(e.request, r.clone()); return r; })))); return;
  }
  e.respondWith(caches.open(V).then(c => timeout(fetch(e.request), 4000).then(r => { if (r.ok) c.put(e.request, r.clone()); return r; }).catch(() => c.match(e.request).then(hit => hit || fetch(e.request)))));
});
