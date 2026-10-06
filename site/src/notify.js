/* تيفو «نبّهني» (item 7, owner 2026-10-06): web push per team, no account. Kickoff, every goal (how it was scored), full time
   and «فيديو الهدف نزل»; the visitor picks «الأهداف بس» or «كل شي», the goal videos on their own switch, and quiet hours, all
   stored with the subscription (saas/cards /api/tifo/push/sub; the sender is saas/football push.py).
   Markup: site/redesign/v5 (grouped inset list, one segmented control, UISwitch rows, <dialog class="sheet">), so it sits in
   the v5 shell as it is; a few rules of its own below, on the v5 tokens with fallbacks. The contract is docs/ENGAGEMENT.md:
     TifoNotify.sheet(team)          '<dialog class="sheet" id="sh-notify">…</dialog>' for a team ({id, name}): the shell adds
                                     it to the page and opens it from its «نبّهني» pill (data-sheet="sh-notify")
     TifoNotify.body(team)           the sheet's body only, for a sheet the shell draws itself
     TifoNotify.mount(root)          wires every [data-nf-team] block under root (idempotent); call after inserting the HTML
     TifoNotify.state(teamId)        {events, mode: "off"|"goals"|"all", video}
     TifoNotify.set(teamId, events)  Promise; from a tap only (Safari asks for permission only inside a user gesture)
     TifoNotify.quiet() / TifoNotify.setQuiet({s, e} | null)   quiet hours, minutes after local midnight, for every team
     TifoNotify.resync()             sends every team again (after «بدون حرق» changes, or a new time zone)
     TifoNotify.supported()          "yes" | "ios-install" (iPhone outside the installed app) | "no"
     TifoNotify.openClip()           on a match page opened from «فيديو الهدف نزل» (#v=<goal key>): plays that goal's clip
   Storage: localStorage tifo.push {teams: {id: [events]}, quiet: {s, e} | null}, the live site's key, so teams chosen there
   carry over. Event: document "tifo:notify" {team, events}. «بدون حرق» (tifo.nospoil): only kickoff alerts go out. */
(function (root) {
  "use strict";
  var EV_ALL = ["start", "goal", "end"], API = "/api/tifo/push/";
  var esc = function (s) { return s == null ? "" : String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var CLOSE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
  var QDEF = { s: 60, e: 420 };                       // 1:00 to 7:00, the default when the switch goes on

  function hourAr(m) {
    var h = Math.floor(m / 60), w = h === 0 ? 12 : h > 12 ? h - 12 : h;
    return w + (h < 5 ? " بالليل" : h < 12 ? " الصبح" : h === 12 ? " الظهر" : h < 18 ? " العصر" : " بالليل");
  }
  function modeOf(ev) { return ev.indexOf("start") >= 0 || ev.indexOf("end") >= 0 ? "all" : ev.indexOf("goal") >= 0 ? "goals" : "off"; }
  function eventsOf(mode, video) { var e = mode === "all" ? EV_ALL.slice() : mode === "goals" ? ["goal"] : []; if (video) e.push("video"); return e; }
  function options(sel) { var o = ""; for (var m = 0; m < 1440; m += 60) o += '<option value="' + m + '"' + (m === sel ? " selected" : "") + ">" + esc(hourAr(m)) + "</option>"; return o; }

  // ------------------------------------------------------------------ markup (pure: Node can prerender it)
  function body(team) {
    var t = team || {}, q = QDEF;
    var seg = '<div class="seg" role="tablist" data-seg="nf" style="--n:3;--i:0"><i class="seg-th" aria-hidden="true"></i>' +
      [["off", "لا شي"], ["goals", "الأهداف بس"], ["all", "كل شي"]].map(function (x, i) { return '<button type="button" role="tab" data-t="' + x[0] + '" aria-selected="' + (i === 0) + '"><span class="sl">' + x[1] + "</span></button>"; }).join("") + "</div>";
    return '<div class="nf" data-nf-team="' + esc(t.id) + '" data-nf-name="' + esc(t.name || "") + '">' +
      '<p class="note">تنبيه على جوالك لمباريات <b>' + esc(t.name || "فريقك") + "</b> بدون حساب.</p>" +
      '<p class="note nf-ios" data-nf-ios hidden>على الآيفون التنبيهات تشتغل من تيفو على الشاشة الرئيسية: اضغط «شارك» ثم «إضافة إلى الشاشة الرئيسية»، وافتحه من هناك.</p>' +
      '<section class="grp mt"><div class="gh"><h2>نبّهني</h2></div><div class="card nf-pad">' + seg + '</div><p class="gf" data-nf-hint>«كل شي»: بداية المباراة وكل هدف والنتيجة النهائية.</p></section>' +
      '<section class="grp"><div class="card"><button type="button" class="row" role="switch" aria-checked="false" data-nf="video"><span class="rt">فيديو الهدف لما ينزل<small>المقطع الرسمي من القناة أو البطولة</small></span><span class="sw" aria-hidden="true"></span></button></div></section>' +
      '<section class="grp"><div class="gh"><h2>أوقات الهدوء</h2></div><div class="card">' +
      '<button type="button" class="row" role="switch" aria-checked="false" data-nf="quiet"><span class="rt">لا تنبّهني وقت النوم<small data-nf-qtxt>من ' + esc(hourAr(q.s)) + " لين " + esc(hourAr(q.e)) + '</small></span><span class="sw" aria-hidden="true"></span></button>' +
      '<div class="row nf-q" data-nf-qrow hidden><label>من <select data-nf="qs">' + options(q.s) + '</select></label><label>لين <select data-nf="qe">' + options(q.e) + "</select></label></div>" +
      '</div><p class="gf">لكل فرقك. اللي ييي في هالوقت ما يوصلك.</p></section>' +
      '<p class="gf nf-msg" data-nf-msg aria-live="polite"></p></div>';
  }
  function sheet(team) {
    return '<dialog class="sheet" id="sh-notify" aria-labelledby="sh-notify-t"><div class="sh-grab" aria-hidden="true"></div><header class="sh-hd"><h2 id="sh-notify-t" tabindex="-1" autofocus>نبّهني</h2>' +
      '<button type="button" class="sh-x" data-close aria-label="سكّر">' + CLOSE + '</button></header><div class="sh-bd">' + body(team) + "</div></dialog>";
  }

  var N = { body: body, sheet: sheet, hourAr: hourAr, eventsOf: eventsOf, modeOf: modeOf };
  if (typeof module !== "undefined" && module.exports) { module.exports = N; return; }
  if (typeof document === "undefined") return;

  // ------------------------------------------------------------------ the browser
  var D = document, B = D.body;
  var ls = { get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };
  function st() { try { var s = JSON.parse(ls.get("tifo.push") || "{}"); s.teams = s.teams || {}; return s; } catch (e) { return { teams: {} }; } }
  function save(s) { ls.set("tifo.push", JSON.stringify(s)); }
  function ok() { return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window; }
  function supported() { return ok() ? "yes" : /iPhone|iPad|iPod/.test(navigator.userAgent) && !navigator.standalone ? "ios-install" : "no"; }
  function nospoil() { return (B && B.classList.contains("nospoil")) || ls.get("tifo.nospoil") === "1"; }
  function offset() { return -new Date().getTimezoneOffset(); }
  var KEY = ls.get("tifo.pushkey");
  function key() { return KEY ? Promise.resolve(KEY) : fetch(API + "key").then(function (r) { return r.json(); }).then(function (j) { KEY = j.publicKey; ls.set("tifo.pushkey", KEY); return KEY; }); }
  function u8(k) { var p = "=".repeat((4 - k.length % 4) % 4), s = atob((k + p).replace(/-/g, "+").replace(/_/g, "/")), a = new Uint8Array(s.length); for (var i = 0; i < s.length; i++) a[i] = s.charCodeAt(i); return a; }
  function ready() { return Promise.race([navigator.serviceWorker.ready, new Promise(function (y, n) { setTimeout(function () { n(new Error("no worker")); }, 10000); })]); }
  function subscription(create) { return ready().then(function (reg) { return reg.pushManager.getSubscription().then(function (s) { return s || (create ? key().then(function (k) { return reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: u8(k) }); }) : null); }); }); }
  function post(method, b) { return fetch(API + "sub", { method: method, headers: { "content-type": "application/json" }, body: JSON.stringify(b), keepalive: true }).then(function (r) { if (!r.ok && r.status !== 204) throw new Error(r.status); return r; }); }
  function wire(tid, ev) {                            // what the server keeps for this team: «بدون حرق» keeps the kickoff only
    var send = ev.filter(function (x) { return !nospoil() || x === "start"; }), s = st();
    if (!send.length) return subscription(false).then(function (x) { if (x) return post("DELETE", { team: +tid, endpoint: x.endpoint }); });
    return subscription(true).then(function (x) { var j = x.toJSON(), q = s.quiet ? { s: s.quiet.s, e: s.quiet.e, o: offset() } : null;
      return post("POST", { team: +tid, events: send, quiet: q, subscription: { endpoint: j.endpoint, keys: j.keys } }); });
  }
  function state(tid) { var ev = st().teams[tid] || []; return { events: ev.slice(), mode: modeOf(ev), video: ev.indexOf("video") >= 0 }; }
  function permit() {                                  // synchronous inside the tap: Safari refuses a prompt after an await
    if (!ok()) return Promise.reject(new Error(supported()));
    if (Notification.permission === "granted") return Promise.resolve();
    if (Notification.permission === "denied") return Promise.reject(new Error("denied"));
    var p = Notification.requestPermission();
    return (p && p.then ? p : Promise.resolve(Notification.permission)).then(function (r) { if (r !== "granted") throw new Error("denied"); });
  }
  function set(tid, events) {
    var s = st(), ev = events.filter(function (x, i) { return ["start", "goal", "end", "video"].indexOf(x) >= 0 && events.indexOf(x) === i; });
    var go = ev.length ? permit() : Promise.resolve();
    return go.then(function () { if (ev.length) s.teams[tid] = ev; else delete s.teams[tid]; save(s); D.dispatchEvent(new CustomEvent("tifo:notify", { detail: { team: +tid, events: ev } })); return wire(tid, ev); });
  }
  function resync() { var s = st(); if (!ok() || Notification.permission !== "granted") return Promise.resolve(); return Promise.all(Object.keys(s.teams).map(function (t) { return wire(t, s.teams[t]).catch(function () {}); })); }
  function quiet() { return st().quiet || null; }
  function setQuiet(q) { var s = st(); s.quiet = q && q.s !== q.e ? { s: +q.s, e: +q.e } : null; save(s); return resync(); }

  // ------------------------------------------------------------------ a sheet or block on the page
  (function () {
    if (D.getElementById("nf-css")) return;
    var c = D.createElement("style"); c.id = "nf-css";
    c.textContent = ".nf [hidden]{display:none!important}.nf .nf-pad{padding:12px}.nf .mt{margin-top:18px}.nf .grp + .grp{margin-top:18px}.nf .row small{display:block;color:var(--label2,#6b6b70);font-size:13px;line-height:18px}" +
      ".nf .nf-q{gap:16px;justify-content:flex-start;flex-wrap:wrap}.nf .nf-q label{display:flex;align-items:center;gap:8px;font-size:15px}" +
      ".nf .nf-q select{min-height:44px;padding:0 10px;border:0;border-radius:var(--r-s,10px);background:var(--fill,rgba(120,120,128,.12));color:var(--label,inherit);font:inherit}" +
      ".nf [aria-disabled=true]{opacity:.45;pointer-events:none}.nf .nf-msg:empty{display:none}.nf .nf-ios{margin-top:10px}";
    D.head.appendChild(c);
  })();
  function $(s, r) { return (r || D).querySelector(s); }
  function paint(el) {
    var tid = el.dataset.nfTeam, s = st(), cur = state(tid), seg = $(".seg", el), i = ["off", "goals", "all"].indexOf(cur.mode);
    if (seg) { seg.style.setProperty("--i", i); seg.querySelectorAll("button[data-t]").forEach(function (b, j) { b.setAttribute("aria-selected", String(j === i)); }); }
    var v = $('[data-nf="video"]', el), q = $('[data-nf="quiet"]', el), qr = $("[data-nf-qrow]", el), qq = s.quiet || QDEF;
    if (v) v.setAttribute("aria-checked", String(cur.video));
    if (q) q.setAttribute("aria-checked", String(!!s.quiet));
    if (qr) qr.hidden = !s.quiet;
    var qs = $('[data-nf="qs"]', el), qe = $('[data-nf="qe"]', el), qt = $("[data-nf-qtxt]", el);
    if (qs) qs.value = String(qq.s); if (qe) qe.value = String(qq.e); if (qt) qt.textContent = "من " + hourAr(qq.s) + " لين " + hourAr(qq.e);
    var sup = supported(), ios = $("[data-nf-ios]", el);
    if (ios) ios.hidden = sup !== "ios-install";
    el.querySelectorAll(".seg,[data-nf]").forEach(function (x) { if (sup !== "yes") x.setAttribute("aria-disabled", "true"); else x.removeAttribute("aria-disabled"); });
  }
  function say(el, t) { var m = $("[data-nf-msg]", el); if (m) m.textContent = t; }
  function fail(el, e) {
    var why = e && e.message;
    say(el, why === "denied" ? "التنبيهات مقفولة لتيفو. تقدر تسمح لها من إعدادات المتصفح." : why === "ios-install" ? "على الآيفون: أضف تيفو للشاشة الرئيسية وشغّل التنبيهات من هناك." : "ما قدرنا نشغّلها الحين، جرّب بعد شوي.");
  }
  function apply(el, events) {
    var tid = el.dataset.nfTeam;
    set(tid, events).then(function () { paint(el); say(el, events.length ? (nospoil() ? "تمام. «بدون حرق» شغّال: بس بداية المباراة توصلك." : "تمام، بتوصلك التنبيهات.") : "وقّفنا تنبيهات هالفريق."); })
      .catch(function (e) { paint(el); fail(el, e); });
  }
  function onClick(e) {
    var el = e.currentTarget, b = e.target.closest(".seg button[data-t]"), cur = state(el.dataset.nfTeam);
    if (b && el.contains(b)) { var seg = b.parentNode, i = [].indexOf.call(seg.querySelectorAll("button[data-t]"), b); seg.style.setProperty("--i", i);
      seg.querySelectorAll("button[data-t]").forEach(function (x) { x.setAttribute("aria-selected", String(x === b)); }); return apply(el, eventsOf(b.dataset.t, cur.video)); }
    var sw = e.target.closest("[data-nf]");
    if (!sw || sw.tagName === "SELECT") return;
    if (sw.dataset.nf === "video") return apply(el, eventsOf(cur.mode, !cur.video));
    if (sw.dataset.nf === "quiet") { var on = !quiet(); setQuiet(on ? QDEF : null).then(function () { say(el, on ? "ما بنزعجك من " + hourAr(QDEF.s) + " لين " + hourAr(QDEF.e) + "." : "التنبيهات توصلك أي وقت."); }); D.querySelectorAll("[data-nf-team]").forEach(paint); }
  }
  function onChange(e) {
    var s = e.target.closest('select[data-nf]'); if (!s) return; var el = e.currentTarget;
    var qs = +$('[data-nf="qs"]', el).value, qe = +$('[data-nf="qe"]', el).value;
    if (qs === qe) { say(el, "البداية والنهاية لازم يختلفون."); return; }
    setQuiet({ s: qs, e: qe }).then(function () { say(el, "ما بنزعجك من " + hourAr(qs) + " لين " + hourAr(qe) + "."); });
    D.querySelectorAll("[data-nf-team]").forEach(paint);
  }
  function mount(r) {
    (r || D).querySelectorAll("[data-nf-team]").forEach(function (el) { if (el.dataset.nfOn) return paint(el); el.dataset.nfOn = "1"; el.addEventListener("click", onClick); el.addEventListener("change", onChange); paint(el); });
  }
  // a «فيديو الهدف نزل» push opens /m/<id>/#v=<goal key>: the goal's «▶ شاهد» (site/src/media.js) once it is on the page
  function openClip() {
    var m = /^#v=([0-9+]+-\d+)$/.exec(location.hash || ""); if (!m) return;
    var k = m[1], t0 = Date.now();
    (function look() { var row = D.querySelector('[data-goal-key="' + k + '"]'), b = row && row.querySelector(".mdw,button[data-media],[data-clip]");
      if (b) { b.click(); return; } if (Date.now() - t0 < 12000) setTimeout(look, 400); })();
  }
  D.addEventListener("tifo:nospoil", function () { resync(); });
  root.TifoNotify = { body: body, sheet: sheet, mount: mount, state: state, set: set, quiet: quiet, setQuiet: setQuiet, resync: resync, supported: supported, openClip: openClip, hourAr: hourAr };
  if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", function () { mount(); openClip(); }); else { mount(); openClip(); }
})(typeof window !== "undefined" ? window : this);
