/* تيفو «توقع وتحدى ربعك» (item 8, owner 2026-10-06): guess the score, private leagues joined by a WhatsApp link, no signup.
   The server is saas/cards src/tifo_predict.py (/api/tifo/predict/*): a nickname and a device key (localStorage tifo.predict,
   sent as X-Tifo-Player), a recovery code for another phone, picks locked at kickoff by the server's clock, points from
   Tifo's own final results: 5 for the exact score, 3 for the goal difference, 2 for the winner or the draw.
   Markup: site/redesign/v5 (grouped inset lists, rows, pills, <dialog class="sheet">) plus a few rules of its own on the v5
   tokens. The contract is docs/ENGAGEMENT.md:
     TifoPredict.block(md)        a match page's «توقعك للنتيجة» group (md: the match file or a fixture row); pure, the build
                                  can prerender it; the browser fills in the player's pick, the lock and the points
     TifoPredict.mount(root)      wires every [data-predict] block under root (idempotent)
     TifoPredict.page(root)       «توقعاتي» into root: the player, the points, the leagues and their tables, the picks, the
                                  recovery code; /predict/?j=<invite> opens the join card first (a WhatsApp link)
     TifoPredict.me()             Promise<player | null>;  TifoPredict.token()  the device's token or null
     TifoPredict.NAMES, .COMPS    the league names (the server's order) and the competition presets
   Copy: light Emirati, Western digits, a score between two names is one dir="rtl" run «2 - 1». */
(function (root) {
  "use strict";
  var API = "/api/tifo/predict/";
  var NAMES = ["دوري الربع", "دوري الشباب", "دوري العايلة", "دوري الدوام", "دوري الشلة", "دوري الديوانية", "دوري المجلس", "دوري الفريج", "دوري الجامعة", "دوري الكشتة"];
  var COMPS = [[[], "كل المباريات"], [[538, 11027, 9943, 11026], "الكورة الإماراتية"], [[536, 9942, 10074], "الكورة السعودية"], [[47], "الدوري الإنجليزي"],
    [[42], "دوري أبطال أوروبا"], [[525, 9469], "دوري أبطال آسيا"]];
  var RULES = "5 نقاط للنتيجة بالضبط، 3 للفارق، 2 للفايز أو التعادل.";
  var KIND = { x: "النتيجة بالضبط", d: "الفارق صح", o: "الفايز صح", m: "ما ضبطت", v: "ألغيت المباراة" };
  var esc = function (s) { return s == null ? "" : String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var CLOSE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
  var tn = function (t) { return (t && (t.name_ar || t.name)) || ""; };
  var sc = function (h, a) { return '<span class="sc num" dir="rtl">' + (+h) + " - " + (+a) + "</span>"; };
  var pts = function (n) { return n === 1 ? "نقطة" : n === 2 ? "نقطتين" : n >= 3 && n <= 10 ? n + " نقاط" : n + " نقطة"; };
  var players = function (n) { return n === 1 ? "لاعب واحد" : n === 2 ? "لاعبين" : n >= 3 && n <= 10 ? n + " لاعبين" : n + " لاعب"; };

  // ------------------------------------------------------------------ markup (pure: Node can prerender it)
  function stepper(side, label, v) {
    return '<div class="tp-step" dir="ltr"><button type="button" data-tp="' + side + '-" aria-label="' + esc("نقّص أهداف " + label) + '">−</button>' +
      '<output class="num" data-tp-' + side + ' aria-live="polite">' + v + '</output><button type="button" data-tp="' + side + '+" aria-label="' + esc("زيد أهداف " + label) + '">+</button></div>';
  }
  function block(md) {
    var m = md || {}, h = tn(m.home), a = tn(m.away);
    return '<section class="grp tp" data-predict data-mid="' + esc(m.id) + '" data-kick="' + esc(m.kickoff_utc || "") + '" data-status="' + esc(m.status || "scheduled") +
      '" data-hn="' + esc(h) + '" data-an="' + esc(a) + '"><div class="gh"><h2>توقعك للنتيجة</h2><a href="/predict/">توقعاتي</a></div>' +
      '<div class="card tp-card"><div class="tp-row"><div class="tp-side"><span class="tp-n">' + esc(h) + "</span>" + stepper("h", h, 0) + '</div><span class="tp-dash" aria-hidden="true">-</span>' +
      '<div class="tp-side"><span class="tp-n">' + esc(a) + "</span>" + stepper("a", a, 0) + "</div></div>" +
      '<div class="tp-who" data-tp-who hidden><input type="text" maxlength="20" autocomplete="nickname" data-tp-nick placeholder="اسمك في الدوري (مثلاً بو راشد)" aria-label="اسمك في الدوري"></div>' +
      '<button type="button" class="pill pri tp-save" data-tp="save">احفظ توقعي</button><p class="tp-msg" data-tp-msg aria-live="polite">ينقفل التوقع مع صافرة البداية.</p></div>' +
      '<p class="gf">' + RULES + ' <a href="/predict/">تحدّى ربعك</a></p></section>';
  }
  function dialog(id, title, inner) {
    return '<dialog class="sheet tp-sheet" id="' + id + '" aria-labelledby="' + id + '-t"><div class="sh-grab" aria-hidden="true"></div><header class="sh-hd"><h2 id="' + id + '-t" tabindex="-1" autofocus>' + title +
      '</h2><button type="button" class="sh-x" data-close aria-label="سكّر">' + CLOSE + '</button></header><div class="sh-bd">' + inner + "</div></dialog>";
  }
  function row(o) {
    var tag = o.href ? "a" : o.btn ? "button" : "div";
    return "<" + tag + ' class="row' + (o.cls ? " " + o.cls : "") + '"' + (o.href ? ' href="' + esc(o.href) + '"' : o.btn ? ' type="button"' : "") + (o.attrs || "") + '><span class="rt">' + o.t +
      (o.sub ? "<small>" + o.sub + "</small>" : "") + "</span>" + (o.v != null ? '<span class="rv">' + o.v + "</span>" : "") + "</" + tag + ">";
  }
  function pickRow(p) {
    var line = esc(tn(p.home)) + " " + sc(p.h, p.a) + " " + esc(tn(p.away)), sub, v = "";
    if (p.k === "v") sub = KIND.v;
    else if (p.res) { sub = "النتيجة " + sc(p.res[0], p.res[1]) + " · " + KIND[p.k]; v = '<b class="tp-pts num">' + (p.pts || 0) + "</b>"; }
    else sub = Date.parse(p.ko) > Date.now() ? '<time data-tp-time="' + esc(p.ko) + '"></time>' : "بانتظار النتيجة";
    return row({ href: "/m/" + p.match + "/", t: line, sub: sub, v: v });
  }
  function board(lv) {
    return lv.members.map(function (m) {
      return '<div class="row tp-lb' + (m.me ? " me" : "") + '"><span class="tp-rk num">' + m.rank + '</span><span class="rt">' + esc(m.nick) + (m.tag ? ' <span class="tp-tag num">#' + esc(m.tag) + "</span>" : "") +
        "<small>" + "بالضبط " + m.ex + " · الفارق " + m.df + " · الفايز " + m.oc + "</small></span>" + '<span class="rv num tp-pts">' + m.pts + "</span></div>";
    }).join("");
  }

  var P = { block: block, board: board, pickRow: pickRow, NAMES: NAMES, COMPS: COMPS, RULES: RULES };
  if (typeof module !== "undefined" && module.exports) { module.exports = P; return; }
  if (typeof document === "undefined") return;

  // ------------------------------------------------------------------ the browser
  var D = document;
  var ls = { get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: function (k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} } };
  function me0() { try { return JSON.parse(ls.get("tifo.predict") || "null"); } catch (e) { return null; } }
  function keep(o) { ls.set("tifo.predict", o ? JSON.stringify(o) : null); }
  function token() { var m = me0(); return m && m.token || null; }
  function api(method, path, body, q) {
    var h = { "content-type": "application/json" }, t = token(); if (t) h["x-tifo-player"] = t;
    var url = API + path + (q ? "?" + Object.keys(q).map(function (k) { return k + "=" + encodeURIComponent(q[k]); }).join("&") : "");
    return fetch(url, { method: method, headers: h, body: body ? JSON.stringify(body) : undefined, cache: "no-store" }).then(function (r) {
      if (r.status === 204) return {};
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (r.status === 401 && t) keep(null);           // this device is not a player any more: start again
        if (!r.ok) { var e = new Error(j.error || "صار خطأ، جرّب بعد شوي"); e.status = r.status; throw e; }
        return j;
      });
    });
  }
  function register(nick) { return api("POST", "me", { nick: nick }).then(function (j) { keep({ pid: j.pid, token: j.token, nick: j.nick, code: j.code, fresh: 1 }); return j; }); }
  function me() { return token() ? api("GET", "me").catch(function () { return null; }) : Promise.resolve(null); }
  function when(iso) {
    if (root.U5 && root.U5.timeText) try { return root.U5.timeText(iso, "dt"); } catch (e) {}
    try { return new Date(iso).toLocaleString("ar-AE-u-nu-latn", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false }); } catch (e) { return ""; }
  }
  function times(r) { (r || D).querySelectorAll("time[data-tp-time]").forEach(function (t) { t.textContent = when(t.getAttribute("data-tp-time")); }); }
  function toast(t) { var el = D.getElementById("toast"); if (el) { el.textContent = t; el.classList.add("on"); setTimeout(function () { el.classList.remove("on"); }, 1800); } }
  function copy(t) { return (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(function () { toast("انتسخ"); }, function () { toast(t); }); }

  (function () {
    if (D.getElementById("tp-css")) return;
    var c = D.createElement("style"); c.id = "tp-css";
    c.textContent = ".tp [hidden],.tp-page [hidden],.tp-sheet [hidden]{display:none!important}.tp-card{padding:14px 12px 12px}.tp-row{display:grid;grid-template-columns:1fr auto 1fr;align-items:end;gap:8px}.tp-side{display:flex;flex-direction:column;align-items:center;gap:8px;min-width:0}" +
      ".tp-n{font-weight:600;font-size:15px;text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%}.tp-dash{font-size:28px;font-weight:800;line-height:44px;color:var(--label2,#6b6b70)}" +
      ".tp-step{display:flex;align-items:center;gap:6px}.tp-step button{width:44px;height:44px;border-radius:22px;background:var(--fill,rgba(120,120,128,.12));font-size:22px;font-weight:600;color:var(--label,inherit)}" +
      ".tp-step button:active{transform:scale(.94)}.tp-step output{min-width:40px;text-align:center;font-size:30px;font-weight:800}.tp-save{display:flex;width:100%;margin-top:14px}" +
      ".tp-msg{margin-top:8px;color:var(--label2,#6b6b70);font-size:13px;text-align:center}.tp-msg:empty{display:none}.tp-who{margin-top:12px}" +
      ".tp input[type=text],.tp-sheet input[type=text],.tp-page input[type=text]{width:100%;min-height:44px;padding:0 12px;border:0;border-radius:var(--r-s,10px);background:var(--fill,rgba(120,120,128,.12));color:var(--label,inherit);font:inherit}" +
      ".tp.locked .tp-step button{visibility:hidden}.tp.locked .tp-save,.tp.locked .tp-who{display:none}.tp-res{margin-top:10px;text-align:center;font-size:15px}.tp-res b{font-weight:800}" +
      ".tp-lb .tp-rk{flex:none;width:26px;text-align:center;font-weight:700;color:var(--label2,#6b6b70)}.tp-lb.me{background:var(--accent-bg,rgba(11,130,70,.12))}.tp-pts{font-weight:800;color:var(--label,inherit)}" +
      ".tp-tag{color:var(--label3,#999);font-size:12px}.tp-hero{padding:16px;text-align:center}.tp-hero b{display:block;font-size:44px;font-weight:800;line-height:1.1}.tp-hero small{color:var(--label2,#6b6b70);font-size:13px}" +
      ".tp-code{font:700 22px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;direction:ltr;unicode-bidi:isolate}.tp-form{display:flex;flex-direction:column;gap:10px;padding:12px}" +
      ".tp-opts{display:flex;flex-wrap:wrap;gap:8px;padding:12px}.tp-opts .pill[aria-pressed=true]{background:var(--accent,#0B8246);color:var(--on-accent,#fff)}.tp-page .grp{margin-top:22px}.tp-page .grp:first-child{margin-top:0}";
    D.head.appendChild(c);
  })();

  // ------------------------------------------------------------------ a match page: [data-predict]
  function locked(el) { var ko = Date.parse(el.dataset.kick || ""); return el.dataset.status !== "scheduled" || !ko || Date.now() >= ko; }
  function val(el, side) { return +el.querySelector("[data-tp-" + side + "]").textContent || 0; }
  function setv(el, side, v) { el.querySelector("[data-tp-" + side + "]").textContent = Math.max(0, Math.min(20, v)); }
  function msg(el, t) { var m = el.querySelector("[data-tp-msg]"); if (m) m.innerHTML = t; }
  function paintMatch(el, v) {
    el.classList.toggle("locked", !!(v && v.locked) || locked(el));
    if (v && v.pick) { setv(el, "h", v.pick.h); setv(el, "a", v.pick.a); }
    var old = el.querySelector(".tp-res"); if (old) old.remove();
    if (el.classList.contains("locked")) {
      var r = D.createElement("p"); r.className = "tp-res";
      r.innerHTML = !v || !v.pick ? "ما توقعت هالمباراة." : v.result && v.result.st === "void" ? "ألغيت المباراة، ما تنحسب." :
        v.result ? "النتيجة " + sc(v.result.h, v.result.a) + " · " + KIND[v.k || "m"] + " · <b>" + esc(pts(v.pts || 0)) + "</b>" : "توقعك محفوظ. النقاط بعد صافرة النهاية.";
      el.querySelector(".tp-card").appendChild(r);
      if (!v || !v.pick) { el.querySelectorAll("output").forEach(function (o) { o.textContent = "–"; }); }
      msg(el, "");
    } else msg(el, v && v.pick ? "توقعك محفوظ. تقدر تعدّله لين صافرة البداية." : "ينقفل التوقع مع صافرة البداية.");
    var s = el.querySelector('[data-tp="save"]'); if (s) s.textContent = v && v.pick ? "عدّل توقعي" : "احفظ توقعي";
  }
  function saveMatch(el) {
    var who = el.querySelector("[data-tp-who]"), nickIn = el.querySelector("[data-tp-nick]"), go;
    if (!token()) {
      if (who.hidden) { who.hidden = false; nickIn.focus(); msg(el, "اكتب اسمك اللي يبين لربعك، بدون حساب ولا إيميل."); return; }
      go = register(nickIn.value).then(function (j) { who.hidden = true; msg(el, "رمز الاسترجاع: <b class=\"tp-code\">" + esc(j.code) + "</b> اكتبه عندك، تحتاجه لو غيرت تلفونك."); });
    } else go = Promise.resolve();
    var b = el.querySelector('[data-tp="save"]'); b.disabled = true;
    go.then(function () { return api("PUT", "pick", { match: +el.dataset.mid, h: val(el, "h"), a: val(el, "a") }); })
      .then(function (j) { toast("توقعك انحفظ"); if (token() && !(me0() || {}).fresh) msg(el, "توقعك محفوظ. تقدر تعدّله لين صافرة البداية."); var m = me0(); if (m && m.fresh) { delete m.fresh; keep(m); }
        var s = el.querySelector('[data-tp="save"]'); if (s) s.textContent = "عدّل توقعي"; })
      .catch(function (e) { msg(el, esc(e.message)); if (e.status === 409) paintMatch(el, { locked: true }); })
      .then(function () { b.disabled = false; });
  }
  function mountOne(el) {
    if (el.dataset.tpOn) return; el.dataset.tpOn = "1";
    el.addEventListener("click", function (e) {
      var b = e.target.closest("[data-tp]"); if (!b || el.classList.contains("locked")) return;
      var k = b.dataset.tp;
      if (k === "save") return saveMatch(el);
      var side = k[0], d = k[1] === "+" ? 1 : -1; setv(el, side, val(el, side) + d);
    });
    paintMatch(el, null);
    if (token()) api("GET", "match", null, { id: el.dataset.mid }).then(function (v) { paintMatch(el, v); }).catch(function () {});
  }
  function mount(r) { (r || D).querySelectorAll("[data-predict]").forEach(mountOne); }

  // ------------------------------------------------------------------ «توقعاتي»
  var PAGE = null;
  function sheetOpen(id, title, inner) {
    var old = D.getElementById(id); if (old) old.remove();
    var w = D.createElement("div"); w.innerHTML = dialog(id, title, inner); var d = w.firstElementChild; D.body.appendChild(d);
    d.addEventListener("click", function (e) { if (e.target === d || e.target.closest("[data-close]")) { if (d.close) d.close(); d.remove(); D.body.style.overflow = ""; } });
    if (d.showModal) { try { d.showModal(); } catch (e) { d.setAttribute("open", ""); } } else d.setAttribute("open", "");
    return d;
  }
  function intro(err) {
    return '<section class="grp"><div class="card tp-form"><p>توقع نتايج المباريات وتحدّى ربعك في دوري خاص فيكم. بدون حساب ولا إيميل: اسم بس.</p>' +
      '<input type="text" maxlength="20" data-tp-nick placeholder="اسمك في الدوري (مثلاً بو راشد)" aria-label="اسمك في الدوري">' +
      '<button type="button" class="pill pri" data-tp-act="register">يلا نبدا</button>' + (err ? '<p class="tp-msg">' + esc(err) + "</p>" : "") + "</div><p class=\"gf\">" + RULES + "</p></section>" +
      '<section class="grp"><div class="gh"><h2>عندك رمز استرجاع؟</h2></div><div class="card tp-form"><input type="text" maxlength="14" dir="ltr" data-tp-code placeholder="XXXXX-XXXXX" aria-label="رمز الاسترجاع">' +
      '<button type="button" class="pill" data-tp-act="recover">استرجع توقعاتي</button></div></section>';
  }
  function joinCard(inv, pre) {
    return '<section class="grp" data-tp-join="' + esc(inv) + '"><div class="card tp-form"><p>عزموك على <b>' + esc(pre.name) + "</b> مع " + esc(pre.owner_nick) + " · " + esc(players(pre.n)) + "</p>" +
      (pre.full ? '<p class="tp-msg">الدوري مليان.</p>' : '<button type="button" class="pill pri" data-tp-act="join">انضم للدوري</button>') + "</div></section>";
  }
  function renderPage(r, j, pre, inv, err) {
    var html = "";
    if (pre) html += joinCard(inv, pre);
    if (!j) { r.innerHTML = html + intro(err); return; }
    var m = me0() || {};
    html += '<section class="grp"><div class="card tp-hero"><small>' + esc(j.nick) + "</small><b class=\"num\">" + j.pts + "</b><small>" + esc(pts(j.pts)).replace(/^\d+ /, "") +
      " · بالضبط " + j.ex + " · الفارق " + j.df + " · الفايز " + j.oc + "</small></div></section>";
    html += '<section class="grp"><div class="gh"><h2>دورياتي</h2></div><div class="card">' + j.leagues.map(function (L) {
      return row({ btn: 1, t: esc(L.name), sub: "مع " + esc(L.owner_nick) + " · " + esc(players(L.n)), attrs: ' data-tp-league="' + esc(L.lid) + '"' });
    }).join("") + row({ btn: 1, t: "سوّ دوري لربعك", cls: "link", attrs: ' data-tp-act="create"' }) + row({ btn: 1, t: "ادخل دوري برابط أو رمز", cls: "link", attrs: ' data-tp-act="joinask"' }) + "</div></section>";
    var up = j.picks.filter(function (p) { return !p.res && p.k !== "v"; }), done = j.picks.filter(function (p) { return p.res || p.k === "v"; });
    html += '<section class="grp"><div class="gh"><h2>توقعاتك الياية</h2></div><div class="card">' + (up.length ? up.map(pickRow).join("") : '<p class="empty">ما عندك توقعات الحين. افتح أي مباراة ياية وتوقع نتيجتها.</p>') + "</div></section>";
    if (done.length) html += '<section class="grp"><div class="gh"><h2>النتايج</h2></div><div class="card">' + done.map(pickRow).join("") + "</div></section>";
    html += '<section class="grp"><div class="gh"><h2>حسابك</h2></div><div class="card">' +
      row({ btn: 1, t: "رمز الاسترجاع", sub: "تحتاجه لو غيرت تلفونك", v: m.code ? '<span class="tp-code">' + esc(m.code) + "</span>" : "سوّ رمز", attrs: ' data-tp-act="code"' }) +
      row({ btn: 1, t: "غيّر اسمك", v: esc(j.nick), attrs: ' data-tp-act="rename"' }) + "</div><p class=\"gf\">" + RULES + " ينقفل كل توقع مع صافرة البداية.</p></section>";
    r.innerHTML = html; times(r);
  }
  function leagueSheet(lid) {
    api("GET", "league", null, { id: lid }).then(function (lv) {
      var L = lv.league, text = "تعال توقع معنا نتايج المباريات في «" + L.name + "» على تيفو\n" + L.url;
      var d = sheetOpen("sh-tp-league", esc(L.name), '<p class="note">مع ' + esc(L.owner_nick) + " · " + esc(players(L.n)) + " من " + L.cap + (L.comps.length ? "" : " · كل المباريات") + "</p>" +
        '<section class="grp"><div class="card">' + board(lv) + "</div></section>" +
        '<section class="grp"><div class="card">' + row({ btn: 1, t: "شارك رابط الدوري", sub: "واتساب أو أي مكان", cls: "link", attrs: ' data-tp-share="1"' }) +
        row({ btn: 1, t: "انسخ الرابط", v: '<span class="num" dir="ltr">' + esc(L.invite) + "</span>", attrs: ' data-tp-copy="1"' }) + row({ btn: 1, t: "اطلع من الدوري", attrs: ' data-tp-leave="1"' }) + "</div></section>");
      d.addEventListener("click", function (e) {
        if (e.target.closest("[data-tp-share]")) { if (navigator.share) navigator.share({ text: text }).catch(function () {}); else location.href = "https://wa.me/?text=" + encodeURIComponent(text); }
        else if (e.target.closest("[data-tp-copy]")) copy(L.url);
        else if (e.target.closest("[data-tp-leave]") && confirm("أكيد تبا تطلع من " + L.name + "؟")) api("POST", "leave", { lid: lid }).then(function () { d.remove(); D.body.style.overflow = ""; load(); }).catch(function (x) { toast(x.message); });
      });
    }).catch(function (e) { toast(e.message); });
  }
  function createSheet() {
    var pick = { name: 0, comps: 0 };
    var opts = function (list, k) { return '<div class="tp-opts">' + list.map(function (x, i) { return '<button type="button" class="pill" aria-pressed="' + (i === 0) + '" data-' + k + '="' + i + '">' + esc(Array.isArray(x) ? x[1] : x) + "</button>"; }).join("") + "</div>"; };
    var d = sheetOpen("sh-tp-create", "دوري لربعك", '<section class="grp"><div class="gh"><h2>اسم الدوري</h2></div><div class="card">' + opts(NAMES, "n") + "</div></section>" +
      '<section class="grp"><div class="gh"><h2>أي مباريات تنحسب؟</h2></div><div class="card">' + opts(COMPS, "c") + '</div><p class="gf">لين 50 لاعب في الدوري. الرابط يدخلهم بدون حساب.</p></section>' +
      '<section class="grp"><button type="button" class="pill pri tp-save" data-tp-act="create-go">سوّ الدوري</button></section>');
    d.addEventListener("click", function (e) {
      var b = e.target.closest("[data-n],[data-c]");
      if (b) { var k = b.hasAttribute("data-n") ? "n" : "c"; b.parentNode.querySelectorAll("[data-" + k + "]").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); }); pick[k === "n" ? "name" : "comps"] = +b.getAttribute("data-" + k); return; }
      if (e.target.closest('[data-tp-act="create-go"]')) api("POST", "league", { name: pick.name, comps: COMPS[pick.comps][0] }).then(function (L) { d.remove(); D.body.style.overflow = ""; load().then(function () { leagueSheet(L.lid); }); }).catch(function (x) { toast(x.message); });
    });
  }
  function joinAsk() {
    var d = sheetOpen("sh-tp-join", "ادخل دوري", '<div class="tp-form"><input type="text" dir="ltr" data-tp-inv placeholder="الرابط أو الرمز" aria-label="رابط الدوري أو رمزه"><button type="button" class="pill pri" data-tp-act="join-go">ادخل</button></div>');
    d.addEventListener("click", function (e) {
      if (!e.target.closest('[data-tp-act="join-go"]')) return;
      var v = d.querySelector("[data-tp-inv]").value, m = /[?&]j=([0-9A-Za-z]{8})/.exec(v) || /\b([0-9A-Za-z]{8})\b/.exec(v);
      if (!m) { toast("الرابط مب صالح"); return; }
      api("POST", "join", { invite: m[1] }).then(function (L) { d.remove(); D.body.style.overflow = ""; toast("دخلت " + L.name); load(); }).catch(function (x) { toast(x.message); });
    });
  }
  function load() {
    var r = PAGE; if (!r) return Promise.resolve();
    var inv = (/[?&]j=([0-9A-Za-z]{8})/.exec(location.search) || [])[1];
    return Promise.all([me(), inv ? api("GET", "invite", null, { code: inv }).catch(function () { return null; }) : null]).then(function (x) {
      var j = x[0], pre = x[1];
      if (pre && j && j.leagues.some(function (L) { return L.invite === inv.toUpperCase(); })) pre = null;   // a member already
      renderPage(r, j, pre, inv);
    });
  }
  function act(e) {
    var r = PAGE, b = e.target.closest("[data-tp-act],[data-tp-league]"); if (!b) return;
    if (b.dataset.tpLeague) return leagueSheet(b.dataset.tpLeague);
    var a = b.dataset.tpAct;
    if (a === "register") return register((r.querySelector("[data-tp-nick]") || {}).value).then(function () { return load(); }).then(function () { var m = me0(); if (m && m.code) toast("احفظ رمز الاسترجاع: " + m.code); }).catch(function (x) { renderPage(r, null, null, null, x.message); });
    if (a === "recover") return api("POST", "recover", { code: (r.querySelector("[data-tp-code]") || {}).value }).then(function (j) { keep({ pid: j.pid, token: j.token, nick: j.nick }); return load(); }).catch(function (x) { toast(x.message); });
    if (a === "join") { var inv = b.closest("[data-tp-join]").dataset.tpJoin;
      if (!token()) { toast("اكتب اسمك تحت أول"); var n = r.querySelector("[data-tp-nick]"); if (n) n.focus(); return; }
      return api("POST", "join", { invite: inv }).then(function (L) { history.replaceState(null, "", location.pathname); toast("دخلت " + L.name); return load().then(function () { leagueSheet(L.lid); }); }).catch(function (x) { toast(x.message); }); }
    if (a === "create") return createSheet();
    if (a === "joinask") return joinAsk();
    if (a === "code") { var m = me0() || {};
      if (m.code) return copy(m.code);
      return api("POST", "code").then(function (j) { m.code = j.code; keep(m); load(); toast("رمزك: " + j.code); }).catch(function (x) { toast(x.message); }); }
    if (a === "rename") return renameSheet();
  }
  function renameSheet() {
    var d = sheetOpen("sh-tp-name", "غيّر اسمك", '<div class="tp-form"><input type="text" maxlength="20" data-tp-new value="' + esc((me0() || {}).nick || "") + '" aria-label="اسمك اليديد">' +
      '<button type="button" class="pill pri" data-tp-act="name-go">احفظ</button><p class="tp-msg" data-tp-err aria-live="polite"></p></div>');
    d.addEventListener("click", function (e) {
      if (!e.target.closest('[data-tp-act="name-go"]')) return;
      api("PATCH", "me", { nick: d.querySelector("[data-tp-new]").value }).then(function (j) { var m = me0() || {}; m.nick = j.nick; keep(m); d.remove(); D.body.style.overflow = ""; load(); })
        .catch(function (x) { d.querySelector("[data-tp-err]").textContent = x.message; });
    });
  }
  function page(r) { PAGE = r; if (!r.dataset.tpOn) { r.dataset.tpOn = "1"; r.classList.add("tp-page"); r.addEventListener("click", act); } return load(); }

  root.TifoPredict = { block: block, mount: mount, page: page, me: me, token: token, NAMES: NAMES, COMPS: COMPS, RULES: RULES };
  // the match blocks on a page, and «توقعاتي» where the page has its element (/predict/, data-predict-page)
  function boot() { mount(); var pg = D.querySelector("[data-predict-page]"); if (pg) page(pg); }
  if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", boot); else boot();
})(typeof window !== "undefined" ? window : this);
