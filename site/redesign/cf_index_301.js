// PROPOSED (not deployed): elyoxe-tifo-site-index with true 301s for the pages merged in audit wave 4 (W4.2/W4.3).
// Today these URLs are stub pages (canonical + location.replace + meta refresh, noindex). Publishing this function
// (CloudFront Functions, viewer-request, distribution E2BSJNNZS8B0WJ) turns them into real 301s; the stubs can stay as a fallback.
// Generated from the stubs in out/ on 2026-09-28.
var MOVED = {
 "/academy/": "/glossary/",
 "/match-of-week/": "/week/#mow",
 "/national/ae/": "/t/5789/#hist",
 "/national/bh/": "/t/5901/#hist",
 "/national/dj/": "/t/121285/#hist",
 "/national/dz/": "/t/6317/#hist",
 "/national/eg/": "/t/10255/#hist",
 "/national/iq/": "/t/5819/#hist",
 "/national/jo/": "/t/5816/#hist",
 "/national/km/": "/t/230692/#hist",
 "/national/kw/": "/t/5821/#hist",
 "/national/lb/": "/t/5897/#hist",
 "/national/ly/": "/t/6328/#hist",
 "/national/ma/": "/t/6262/#hist",
 "/national/mr/": "/t/68374/#hist",
 "/national/om/": "/t/5824/#hist",
 "/national/ps/": "/t/6333/#hist",
 "/national/qa/": "/t/5902/#hist",
 "/national/sa/": "/t/7795/#hist",
 "/national/sd/": "/t/5805/#hist",
 "/national/so/": "/t/287978/#hist",
 "/national/sy/": "/t/6320/#hist",
 "/national/tn/": "/t/6719/#hist",
 "/national/ye/": "/t/5892/#hist",
 "/uae/": "/t/5789/",
 "/w/": "/tv/?mine=1",
 "/year/": "/calendars/#year"
};
function handler(event) {
  var r = event.request, u = r.uri, to = MOVED[u] || MOVED[u + "/"];
  if (to) {
    var qs = Object.keys(r.querystring || {}).map(function (k) { return k + "=" + r.querystring[k].value; }).join("&");
    if (qs) { var h = to.indexOf("#"); to = h < 0 ? to + (to.indexOf("?") < 0 ? "?" : "&") + qs : to.slice(0, h) + (to.indexOf("?") < 0 ? "?" : "&") + qs + to.slice(h); }
    return { statusCode: 301, statusDescription: "Moved Permanently", headers: { location: { value: to }, "cache-control": { value: "max-age=86400" } } };
  }
  if (u.endsWith("/")) r.uri = u + "index.html";
  else if (u.lastIndexOf(".") < u.lastIndexOf("/")) {
    return { statusCode: 301, statusDescription: "Moved", headers: { location: { value: u + "/" } } };
  }
  return r;
}
