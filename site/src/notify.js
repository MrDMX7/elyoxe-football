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
  // transfer: the club's official moves (owner 2026-10-10 item 12), a switch of its own like the goal videos
  function eventsOf(mode, video, transfer) { var e = mode === "all" ? EV_ALL.slice() : mode === "goals" ? ["goal"] : []; if (video) e.push("video"); if (transfer) e.push("transfer"); return e; }
  function options(sel) { var o = ""; for (var m = 0; m < 1440; m += 60) o += '<option value="' + m + '"' + (m === sel ? " selected" : "") + ">" + esc(hourAr(m)) + "</option>"; return o; }

  // ------------------------------------------------------------------ markup (pure: Node can prerender it)
  function body(team) {
    var t = team || {}, q = QDEF;
    var seg = '<div class="seg" role="tablist" data-seg="nf" style="--n:3;--i:0"><i class="seg-th" aria-hidden="true"></i>' +
      [["off", "لا شي"], ["goals", "الأهداف بس"], ["all", "كل شي"]].map(function (x, i) { return '<button type="button" role="tab" data-t="' + x[0] + '" aria-selected="' + (i === 0) + '"><span class="sl">' + x[1] + "</span></button>"; }).join("") + "</div>";
    return '<div class="nf" data-nf-team="' + esc(t.id) + '" data-nf-name="' + esc(t.name || "") + '">' +
      '<p class="note">تنبيه على تلفونك لمباريات <b>' + esc(t.name || "فريقك") + "</b> بدون حساب.</p>" +
      '<p class="note nf-ios" data-nf-ios hidden>على الآيفون التنبيهات تشتغل من تيفو على الشاشة الرئيسية: اضغط «شارك» ثم «إضافة إلى الشاشة الرئيسية»، وافتحه من هناك.</p>' +
      '<section class="grp mt"><div class="gh"><h2>نبّهني</h2></div><div class="card nf-pad">' + seg + '</div><p class="gf" data-nf-hint>«كل شي»: بداية المباراة وكل هدف والنتيجة النهائية.</p></section>' +
      '<section class="grp"><div class="card"><button type="button" class="row" role="switch" aria-checked="false" data-nf="video"><span class="rt">فيديو الهدف لما ينزل<small>المقطع الرسمي من القناة أو البطولة</small></span><span class="sw" aria-hidden="true"></span></button>' +
      '<button type="button" class="row" role="switch" aria-checked="false" data-nf="transfer"><span class="rt">انتقالات النادي<small>لما يوقّع لاعب أو يطلع، رسمياً</small></span><span class="sw" aria-hidden="true"></span></button></div></section>' +
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

  // «تابع اللاعب» (spec 2026-10-09 player follow): his alerts in three groups; the owner's defaults ticked until the visitor
  // chooses. Kinds = saas/cards TIFOPUSH_PEVENTS = football pushplayer.KINDS
  var PGROUPS = [["قبل المباراة", [["soon", "مباراته بعد ساعة", "مع القناة في دولتك"], ["start11", "أساسي", "لما تنزل التشكيلة الرسمية"], ["squad_out", "مب في القائمة", "لا أساسي ولا احتياط"]]],
    ["في المباراة", [["subin", "دخل بديل"], ["subout", "طلع تبديل", "ولو طلع مصاب"], ["goal", "هدف"], ["assist", "صناعة"], ["card", "بطاقة"], ["pen", "ضيّع ركلة جزاء"]]],
    ["بعد المباراة", [["end", "دقايقه وأرقامه", "كم لعب وسجّل وتقييمه"], ["potm", "أحسن لاعب في المباراة"], ["video", "فيديو هدفه لما ينزل"]]]];
  var PKINDS = PGROUPS.reduce(function (a, g) { return a.concat(g[1].map(function (x) { return x[0]; })); }, []);
  var PDEF = ["start11", "subin", "goal", "assist", "card", "end"];
  function playerBody(p, on) {
    var x = p || {}, ev = on || PDEF;
    return '<div class="nf" data-nf-player="' + esc(x.id) + '" data-nf-name="' + esc(x.name || "") + '">' +
      '<p class="note">تنبيه على تلفونك عن <b>' + esc(x.name || "لاعبك") + "</b> مع ناديه ومنتخبه، بدون حساب.</p>" +
      '<p class="note nf-ios" data-nf-ios hidden>على الآيفون التنبيهات تشتغل من تيفو على الشاشة الرئيسية: اضغط «شارك» ثم «إضافة إلى الشاشة الرئيسية»، وافتحه من هناك.</p>' +
      PGROUPS.map(function (g) { return '<section class="grp mt"><div class="gh"><h2>' + g[0] + '</h2></div><div class="card">' + g[1].map(function (k) {
        return '<button type="button" class="row" data-pe="' + k[0] + '" role="switch" aria-checked="' + (ev.indexOf(k[0]) >= 0) + '"><span class="rt">' + k[1] + (k[2] ? "<small>" + k[2] + "</small>" : "") + '</span><span class="sw" aria-hidden="true"></span></button>'; }).join("") + "</div></section>"; }).join("") +
      '<p class="gf">أوقات الهدوء و«بدون حرق» نفسها اللي للفرق. وحد أقصى 20 تنبيه لاعب باليوم.</p><p class="gf nf-msg" data-nf-msg aria-live="polite"></p></div>';
  }
  function playerSheet(p) {
    return '<dialog class="sheet" id="sh-pnotify" aria-labelledby="sh-pnotify-t"><div class="sh-grab" aria-hidden="true"></div><header class="sh-hd"><h2 id="sh-pnotify-t" tabindex="-1" autofocus>تابع اللاعب</h2>' +
      '<button type="button" class="sh-x" data-close aria-label="سكّر">' + CLOSE + '</button></header><div class="sh-bd">' + playerBody(p) + "</div></dialog>";
  }

  // «نبّهني» asked at the moment a visitor cares (owner 2026-10-09: 2 team-alert subscriptions in total, both ours): a team's
  // page opened the second time, or a live match watched a minute. Once per team; 14 days after «لا» or after it was shown.
  var ASK_GAP = 14 * 864e5;
  function askTeams(kind, teams, s, now, subscribed) {
    s = s || {}; var V = s.views || {}, NO = s.no || {}, AS = s.asked || {}, sub = subscribed || {};
    var ok = teams.filter(function (t) { var k = String(t); return t != null && !sub[k] && !(NO[k] && now - NO[k] < ASK_GAP) && !(AS[k] && now - AS[k] < ASK_GAP); });
    if (kind === "team") return ok.filter(function (t) { return (V[String(t)] || 0) >= 2; });
    var best = ok.slice().sort(function (a, b) { return (V[String(b)] || 0) - (V[String(a)] || 0); });
    return best.length && (V[String(best[0])] || 0) > 0 ? [best[0]] : best.slice(0, 2);   // a live match: his team if we know it, else both
  }
  function askBar(teams, sup) {
    var la = function (n) { n = String(n || ""); return /^ال/.test(n) ? "لل" + n.slice(2) : "لـ" + n; };   // «للوحدة», «لـعجمان»
    var who = teams.map(function (t) { return "<b>" + esc(la(t.name)) + "</b>"; }).join(" أو ");
    if (sup === "ios-install") return '<div class="nf-ask" role="dialog" aria-label="تنبيهات تيفو"><p>يوصلك كل هدف ' + who + ' على تلفونك: أضف تيفو للشاشة الرئيسية أول («شارك» ثم «إضافة إلى الشاشة الرئيسية») وفعّلها من هناك.</p><div class="nf-ask-b"><button type="button" class="pill" data-ask-no>تمام</button></div></div>';
    return '<div class="nf-ask" role="dialog" aria-label="تنبيهات تيفو"><p>يوصلك كل هدف ' + who + ' على تلفونك؟</p><div class="nf-ask-b">' +
      teams.map(function (t) { return '<button type="button" class="pill pri" data-ask-yes="' + esc(t.id) + '">نبّهني' + (teams.length > 1 ? " " + esc(la(t.name)) : "") + "</button>"; }).join("") +
      '<button type="button" class="pill" data-ask-no>لا، شكراً</button></div></div>';
  }

  var N = { body: body, sheet: sheet, askTeams: askTeams, askBar: askBar, hourAr: hourAr, eventsOf: eventsOf, modeOf: modeOf, playerBody: playerBody, playerSheet: playerSheet, PKINDS: PKINDS, PDEF: PDEF };
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
    var send = ev.filter(function (x) { return !nospoil() || x === "start" || x === "transfer"; }), s = st();   // a transfer spoils no match
    if (!send.length) return subscription(false).then(function (x) { if (x) return post("DELETE", { team: +tid, endpoint: x.endpoint }); });
    return subscription(true).then(function (x) { var j = x.toJSON(), q = s.quiet ? { s: s.quiet.s, e: s.quiet.e, o: offset() } : null;
      return post("POST", { team: +tid, events: send, quiet: q, subscription: { endpoint: j.endpoint, keys: j.keys } }); });
  }
  function state(tid) { var ev = st().teams[tid] || []; return { events: ev.slice(), mode: modeOf(ev), video: ev.indexOf("video") >= 0, transfer: ev.indexOf("transfer") >= 0 }; }
  function permit() {                                  // synchronous inside the tap: Safari refuses a prompt after an await
    if (!ok()) return Promise.reject(new Error(supported()));
    if (Notification.permission === "granted") return Promise.resolve();
    if (Notification.permission === "denied") return Promise.reject(new Error("denied"));
    var p = Notification.requestPermission();
    return (p && p.then ? p : Promise.resolve(Notification.permission)).then(function (r) { if (r !== "granted") throw new Error("denied"); });
  }
  function set(tid, events) {
    var s = st(), ev = events.filter(function (x, i) { return ["start", "goal", "end", "video", "transfer"].indexOf(x) >= 0 && events.indexOf(x) === i; });
    var go = ev.length ? permit() : Promise.resolve();
    return go.then(function () { if (ev.length) s.teams[tid] = ev; else delete s.teams[tid]; save(s); D.dispatchEvent(new CustomEvent("tifo:notify", { detail: { team: +tid, events: ev } })); return wire(tid, ev); });
  }
  // players: localStorage tifo.push.players {pid: [events]}; «بدون حرق» keeps «بعد ساعة» and «أساسي» only
  function pst() { try { return JSON.parse(ls.get("tifo.push.players") || "{}") || {}; } catch (e) { return {}; } }
  function playerState(pid) { var ev = pst()[pid]; return { events: ev ? ev.slice() : null }; }
  function country() { var c = (ls.get("tifo.country") || "").toUpperCase(); return /^[A-Z]{2}$/.test(c) ? c : null; }
  function wireP(pid, ev) {
    var send = ev.filter(function (x) { return !nospoil() || x === "start11" || x === "soon"; }), s = st();
    if (!send.length) return subscription(false).then(function (x) { if (x) return post("DELETE", { player: +pid, endpoint: x.endpoint }); });
    return subscription(true).then(function (x) { var j = x.toJSON(), q = s.quiet ? { s: s.quiet.s, e: s.quiet.e, o: offset() } : null;
      return post("POST", { player: +pid, events: send, quiet: q, cc: country(), subscription: { endpoint: j.endpoint, keys: j.keys } }); });
  }
  function setPlayer(pid, events) {
    var ev = events.filter(function (x, i) { return PKINDS.indexOf(x) >= 0 && events.indexOf(x) === i; }), go = ev.length ? permit() : Promise.resolve();
    return go.then(function () { var s = pst(); if (ev.length) s[pid] = ev; else delete s[pid]; ls.set("tifo.push.players", JSON.stringify(s));
      D.dispatchEvent(new CustomEvent("tifo:notify-player", { detail: { player: +pid, events: ev } })); return wireP(pid, ev); });
  }
  function resync() { var s = st(), P = pst(); if (!ok() || Notification.permission !== "granted") return Promise.resolve();
    return Promise.all(Object.keys(s.teams).map(function (t) { return wire(t, s.teams[t]).catch(function () {}); })
      .concat(Object.keys(P).map(function (p) { return wireP(p, P[p]).catch(function () {}); }))); }
  function quiet() { return st().quiet || null; }
  function setQuiet(q) { var s = st(); s.quiet = q && q.s !== q.e ? { s: +q.s, e: +q.e } : null; save(s); return resync(); }

  // ------------------------------------------------------------------ a sheet or block on the page
  (function () {
    if (D.getElementById("nf-css")) return;
    var c = D.createElement("style"); c.id = "nf-css";
    c.textContent = ".nf [hidden]{display:none!important}.nf .nf-pad{padding:12px}.nf .mt{margin-top:18px}.nf .grp + .grp{margin-top:18px}.nf .row small{display:block;color:var(--label2,#6b6b70);font-size:13px;line-height:18px}" +
      ".nf .nf-q{gap:16px;justify-content:flex-start;flex-wrap:wrap}.nf .nf-q label{display:flex;align-items:center;gap:8px;font-size:15px}" +
      ".nf .nf-q select{min-height:44px;padding:0 10px;border:0;border-radius:var(--r-s,10px);background:var(--fill,rgba(120,120,128,.12));color:var(--label,inherit);font:inherit}" +
      ".nf [aria-disabled=true]{opacity:.45;pointer-events:none}.nf .nf-msg:empty{display:none}.nf .nf-ios{margin-top:10px}" +
      ".nf-ask{position:fixed;inset-inline:12px;bottom:calc(84px + env(safe-area-inset-bottom));z-index:60;background:var(--bg-grouped2,var(--bg,#fff));color:var(--label,#111);border-radius:16px;box-shadow:0 10px 30px rgba(0,0,0,.2);padding:12px 14px;font-size:15px;line-height:22px}" +
      ".nf-ask p{margin:0 0 10px}.nf-ask-b{display:flex;gap:8px;flex-wrap:wrap}";
    D.head.appendChild(c);
  })();
  function $(s, r) { return (r || D).querySelector(s); }
  function paint(el) {
    var tid = el.dataset.nfTeam, s = st(), cur = state(tid), seg = $(".seg", el), i = ["off", "goals", "all"].indexOf(cur.mode);
    if (seg) { seg.style.setProperty("--i", i); seg.querySelectorAll("button[data-t]").forEach(function (b, j) { b.setAttribute("aria-selected", String(j === i)); }); }
    var v = $('[data-nf="video"]', el), q = $('[data-nf="quiet"]', el), qr = $("[data-nf-qrow]", el), qq = s.quiet || QDEF;
    if (v) v.setAttribute("aria-checked", String(cur.video));
    var tr = $('[data-nf="transfer"]', el); if (tr) tr.setAttribute("aria-checked", String(cur.transfer));
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
      seg.querySelectorAll("button[data-t]").forEach(function (x) { x.setAttribute("aria-selected", String(x === b)); }); return apply(el, eventsOf(b.dataset.t, cur.video, cur.transfer)); }
    var sw = e.target.closest("[data-nf]");
    if (!sw || sw.tagName === "SELECT") return;
    if (sw.dataset.nf === "video") return apply(el, eventsOf(cur.mode, !cur.video, cur.transfer));
    if (sw.dataset.nf === "transfer") return apply(el, eventsOf(cur.mode, cur.video, !cur.transfer));
    if (sw.dataset.nf === "quiet") { var on = !quiet(); setQuiet(on ? QDEF : null).then(function () { say(el, on ? "ما بنزعجك من " + hourAr(QDEF.s) + " لين " + hourAr(QDEF.e) + "." : "التنبيهات توصلك أي وقت."); }); D.querySelectorAll("[data-nf-team]").forEach(paint); }
  }
  function onChange(e) {
    var s = e.target.closest('select[data-nf]'); if (!s) return; var el = e.currentTarget;
    var qs = +$('[data-nf="qs"]', el).value, qe = +$('[data-nf="qe"]', el).value;
    if (qs === qe) { say(el, "البداية والنهاية لازم يختلفون."); return; }
    setQuiet({ s: qs, e: qe }).then(function () { say(el, "ما بنزعجك من " + hourAr(qs) + " لين " + hourAr(qe) + "."); });
    D.querySelectorAll("[data-nf-team]").forEach(paint);
  }
  function paintP(el) {
    var on = playerState(el.dataset.nfPlayer).events || PDEF, sup = supported(), ios = $("[data-nf-ios]", el);   // not followed yet: the defaults
    el.querySelectorAll("[data-pe]").forEach(function (b) { b.setAttribute("aria-checked", String(on.indexOf(b.dataset.pe) >= 0));
      if (sup !== "yes") b.setAttribute("aria-disabled", "true"); else b.removeAttribute("aria-disabled"); });
    if (ios) ios.hidden = sup !== "ios-install";
  }
  function onClickP(e) {
    var el = e.currentTarget, b = e.target.closest("[data-pe]"); if (!b || !el.contains(b)) return;
    b.setAttribute("aria-checked", String(b.getAttribute("aria-checked") !== "true"));
    var ev = [].map.call(el.querySelectorAll('[data-pe][aria-checked="true"]'), function (x) { return x.dataset.pe; });
    setPlayer(el.dataset.nfPlayer, ev).then(function () { paintP(el); say(el, ev.length ? (nospoil() ? "تمام. «بدون حرق» شغّال: بس «بعد ساعة» و«أساسي» توصلك." : "تمام، بتوصلك التنبيهات.") : "وقّفنا تنبيهات هاللاعب."); })
      .catch(function (er) { paintP(el); fail(el, er); });
  }
  function mount(r) {
    (r || D).querySelectorAll("[data-nf-team]").forEach(function (el) { if (el.dataset.nfOn) return paint(el); el.dataset.nfOn = "1"; el.addEventListener("click", onClick); el.addEventListener("change", onChange); paint(el); });
    (r || D).querySelectorAll("[data-nf-player]").forEach(function (el) { if (el.dataset.nfOn) return paintP(el); el.dataset.nfOn = "1"; el.addEventListener("click", onClickP); paintP(el); });
  }
  // a «فيديو الهدف نزل» push opens /m/<id>/#v=<goal key>: the goal's «▶ شاهد» (site/src/media.js) once it is on the page
  function openClip() {
    var m = /^#v=([0-9+]+-\d+)$/.exec(location.hash || ""); if (!m) return;
    var k = m[1], t0 = Date.now();
    (function look() { var row = D.querySelector('[data-goal-key="' + k + '"]'), b = row && row.querySelector(".mdw,button[data-media],[data-clip]");
      if (b) { b.click(); return; } if (Date.now() - t0 < 12000) setTimeout(look, 400); })();
  }
  // the ask: views per team, «لا» and «shown» times in localStorage tifo.ask
  function askSt() { try { var s = JSON.parse(ls.get("tifo.ask") || "{}") || {}; s.views = s.views || {}; s.no = s.no || {}; s.asked = s.asked || {}; return s; } catch (e) { return { views: {}, no: {}, asked: {} }; } }
  function askSave(s) { ls.set("tifo.ask", JSON.stringify(s)); }
  function askShow(teams) {
    if (D.querySelector(".nf-ask")) return;
    var s = askSt(); teams.forEach(function (t) { s.asked[t.id] = Date.now(); }); askSave(s);
    var w = D.createElement("div"); w.innerHTML = askBar(teams, supported()); var bar = w.firstChild; B.appendChild(bar);
    bar.addEventListener("click", function (e) {
      var y = e.target.closest("[data-ask-yes]"), n = e.target.closest("[data-ask-no]");
      if (y) {
        set(y.dataset.askYes, ["start", "goal", "end"]).then(function () { bar.innerHTML = "<p>تمام، بيوصلك كل هدف.</p>"; D.querySelectorAll("[data-nf-team]").forEach(paint); setTimeout(function () { bar.remove(); }, 2500); })
          .catch(function (er) { bar.innerHTML = "<p>" + (er && er.message === "denied" ? "التنبيهات مقفولة لتيفو في إعدادات المتصفح." : "ما قدرنا نشغّلها الحين، جرّب بعد شوي.") + "</p>"; setTimeout(function () { bar.remove(); }, 3500); });
      } else if (n) { var s2 = askSt(); teams.forEach(function (t) { s2.no[t.id] = Date.now(); }); askSave(s2); bar.remove(); }
    });
  }
  function ask() {
    if (supported() === "no" || (ok() && Notification.permission === "denied")) return;
    var page = B.dataset.page;
    if (page === "team") {
      var el = D.querySelector("[data-nf-team]"); if (!el) return;
      var tid = el.dataset.nfTeam, s = askSt(); s.views[tid] = (s.views[tid] || 0) + 1; askSave(s);
      if (askTeams("team", [tid], s, Date.now(), st().teams).length) setTimeout(function () { askShow([{ id: tid, name: el.dataset.nfName }]); }, 4000);
    } else if (page === "match") {
      var md = {}; try { md = JSON.parse((D.getElementById("msum") || {}).textContent || "{}"); } catch (e2) {}
      D.addEventListener("tifo:match", function (e3) { md = Object.assign({}, md, e3.detail || {}); });
      setTimeout(function () {
        if (!(md.status === "live" || md.status === "ht") || !md.home || !md.away) return;
        var nm = {}; nm[md.home.id] = md.home.name_ar || md.home.name; nm[md.away.id] = md.away.name_ar || md.away.name;
        var pick = askTeams("live", [md.home.id, md.away.id], askSt(), Date.now(), st().teams);
        if (pick.length) askShow(pick.map(function (t) { return { id: t, name: nm[t] }; }));
      }, 60000);
    }
  }
  D.addEventListener("tifo:nospoil", function () { resync(); });
  root.TifoNotify = { body: body, sheet: sheet, mount: mount, state: state, set: set, quiet: quiet, setQuiet: setQuiet, resync: resync, supported: supported, openClip: openClip, hourAr: hourAr,
    playerBody: playerBody, playerSheet: playerSheet, playerState: playerState, setPlayer: setPlayer };
  if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", function () { mount(); openClip(); ask(); }); else { mount(); openClip(); ask(); }
})(typeof window !== "undefined" ? window : this);
