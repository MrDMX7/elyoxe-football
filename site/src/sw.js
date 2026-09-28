/* تيفو service worker (feature 202, split in audit W1.11): pages you opened before still open with a weak signal at the stadium.
   Four caches, so a deploy no longer throws everything away:
   - tifo-assets-<V>: content-hashed /assets/, cache first; only older assets-* caches are deleted on activate.
   - tifo-crest: /logo/ and /lg/, cache first, the newest 300 kept.
   - tifo-pages: navigations, network first (navigation preload) with a 4 s budget, the newest 60 kept.
   - tifo-data: other /v1 files, network first with a 4 s budget, the newest 40 kept.
   Live data (/v1/live.json, /v1/match/*, /v1/day/*) is network only; the last copy is served only when the network fails
   outright (offline), never on a timeout, or a slow stadium connection would freeze the score. /og/ is never cached.
   Offline: a navigation that fails with nothing cached gets /offline/ (tifo-off, filled on install).
   Kill switch: on activate the worker reads /sw.json and unregisters itself (and clears its caches) when it says {"off":true}. */
// QA 15: one unversioned asset cache. /assets/ names carry their content hash, so a deploy adds files instead of dropping the ones
// the 60 cached pages still point at (an offline page kept its CSS/JS only until the next deploy); the newest 160 are kept.
const V = "__V__", A = "tifo-assets", CREST = "tifo-crest", PAGES = "tifo-pages", DATA = "tifo-data";
const LIMIT = { [A]:160, [CREST]:300, [PAGES]:60, [DATA]:40 };
// W3.6: the offline page (and the assets it links) is kept apart from the 60-page cache so it is never trimmed away
const OFF = "tifo-off";
self.addEventListener("install", e => { self.skipWaiting(); e.waitUntil((async () => { try {
  const r = await fetch("/offline/", { cache:"no-store" }); if (!r.ok) return; const h = await r.clone().text(); await (await caches.open(OFF)).put("/offline/", r);
  const a = await caches.open(A); for (const m of h.matchAll(/(?:href|src)="(\/assets\/[^"]+)"/g)) try { const x = await fetch(m[1]); if (x.ok) await a.put(m[1], x); } catch (err){}
} catch (err){} })()); });
self.addEventListener("activate", e => { e.waitUntil((async () => {
  try { const r = await fetch("/sw.json", { cache:"no-store" }); if (r.ok && (await r.json()).off){ for (const k of await caches.keys()) if (k.startsWith("tifo-")) await caches.delete(k); await self.registration.unregister(); return; } } catch (err){}
  for (const k of await caches.keys()){
    if (k.startsWith("tifo-assets-")){ try { const old = await caches.open(k), a = await caches.open(A); for (const q of await old.keys()){ if (!(await a.match(q))){ const r = await old.match(q); if (r) await a.put(q, r); } } } catch (err){} await caches.delete(k); }   // the per-version caches before QA 15 fold into the one cache
    else if (/^tifo-2-/.test(k)) await caches.delete(k);   // tifo-2-* = the pre-split single cache
  }
  if (self.registration.navigationPreload) try { await self.registration.navigationPreload.enable(); } catch (err){}
  await self.clients.claim();
})()); });
async function put(name, req, res){ const c = await caches.open(name); await c.put(req, res); const lim = LIMIT[name]; if (!lim) return; const ks = await c.keys(); for (let i = 0; i < ks.length - lim; i++) await c.delete(ks[i]); }   // keys come back oldest first
const LIVE = /^\/v1\/(live\.json|match\/|day\/)/;
// push (W3.6 + owner item 9a): payload {title, body, url, tag, team}; a push is always shown, even when the payload is not JSON
self.addEventListener("push", e => { let d = {}; try { d = e.data ? e.data.json() : {}; } catch (err){ try { d = { body:e.data.text() }; } catch (x){} }
  e.waitUntil(self.registration.showNotification(d.title || "تيفو", { body:d.body || "", tag:d.tag || "tifo", renotify:!!d.tag, lang:"ar", dir:"rtl", icon:"/icons/icon-192.png", badge:"/icons/badge-96.png", data:{ url:d.url || "/", team:d.team || null } })); });
self.addEventListener("notificationclick", e => { e.notification.close(); let u = "/";
  try { const x = new URL((e.notification.data && e.notification.data.url) || "/", self.location.origin); if (x.origin === self.location.origin) u = x.pathname + x.search + x.hash; } catch (err){}
  e.waitUntil((async () => { const all = await self.clients.matchAll({ type:"window", includeUncontrolled:true }), path = u.split(/[?#]/)[0];
    for (const c of all){ try { if (new URL(c.url).pathname === path && "focus" in c) return c.focus(); } catch (err){} }
    return self.clients.openWindow(u); })()); });
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
    const fallback = () => caches.match(e.request).then(hit => { if (hit) return hit; if (e.request.mode === "navigate") return caches.match("/offline/").then(o => { if (o) return o; throw new Error("offline"); }); throw new Error("offline"); });
    const slow = new Promise(ok => setTimeout(ok, 4000)).then(() => caches.match(e.request)).then(hit => hit || net.catch(fallback));   // QA 53: a connection that dies after 4 s still gets the offline page
    return Promise.race([net.catch(fallback), slow]);
  })());
});
