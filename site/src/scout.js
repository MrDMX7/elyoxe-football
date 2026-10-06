/* تيفو «كشّاف تيفو» (owner bold idea 6, 2026-10-06): pick five young Arab players and score as they shine. The pool and its
   points are the site's (/scout/pool.json from lib/scout.cjs, every hour with the build); the scouts, their fives and the board
   are the Cards Lambda's (/api/tifo/scout/*, saas/cards src/tifo_scout.py) under the «توقعاتي» identity (localStorage
   tifo.predict, the same token as src/predict.js: one nickname for both games). The five is edited on the page and saved in one
   go; a dropped player is a change (3 a week), filling an empty place is free. On the v5 tokens; light Emirati, Western digits. */
(function () {
  "use strict";
  var D = document, U = window.U5, V = window.V5 || {}, root = D.getElementById("sc");
  if (!root || !U || !window.fetch) return;
  var API = "/api/tifo/scout/", SQUAD = 5, POOL = [], BY = {}, ME = null, DRAFT = null, CC = V.cc || (V.data && V.data.cc) || {}, FILTER = { c: "", q: "" }, SHOW = 40;
  var esc = U.esc, nf = function (n) { return U.nf ? U.nf(n) : String(n); };
  var ls = { get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: function (k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} } };
  var me0 = function () { try { return JSON.parse(ls.get("tifo.predict") || "null"); } catch (e) { return null; } };
  var token = function () { var m = me0(); return m && m.token || null; };
  function api(method, path, body) {
    var h = { "content-type": "application/json" }, t = token(); if (t) h["x-tifo-player"] = t;
    return fetch(path, { method: method, headers: h, body: body ? JSON.stringify(body) : undefined, cache: "no-store" }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (r.status === 401 && t) ls.set("tifo.predict", null);   // this device is not a player any more: start again
        if (!r.ok) { var e = new Error(j.error || "صار خطأ، جرّب بعد شوي"); e.status = r.status; throw e; }
        return j;
      });
    });
  }
  function toast(m) { var t = D.getElementById("sc-msg"); if (t) { t.textContent = m; t.hidden = !m; } }
  var line = function (p) { return [p.tn || (p.nt ? "مع المنتخب" : ""), CC[p.c] || "", p.age + " سنة"].filter(Boolean).join(" · "); };
  // Arabic counting: the plural from 3 to 10 (by the last two digits), the singular otherwise
  var n_ = function (n, one, few) { var r = n % 100; return nf(n) + " " + (r >= 3 && r <= 10 ? few : one); };
  var stats = function (p) { return n_(p.apps, "مباراة", "مباريات") + " · " + n_(p.mins, "دقيقة", "دقايق") + (p.g ? " · " + n_(p.g, "هدف", "أهداف") : "") + (p.a ? " · " + n_(p.a, "صناعة", "صناعات") : ""); };
  var ptsW = function (n) { var r = n % 100; return r >= 3 && r <= 10 ? "نقاط" : "نقطة"; };
  var name = function (p) { return p.pg ? '<a href="/p/' + p.id + '/">' + esc(p.n) + "</a>" : esc(p.n); };

  // ------------------------------------------------------------------ my five
  function saved() { return ME ? ME.squad.map(function (x) { return x.p; }) : []; }
  function dirty() { var a = saved().slice().sort(), b = (DRAFT || []).slice().sort(); return a.join() !== b.join(); }
  function paintFive() {
    var box = D.getElementById("sc-five"); if (!box) return;
    if (!token()) {
      box.innerHTML = '<div class="card lc"><p><b>ابدأ باسمك.</b> نفس اسمك في «توقعاتي»، بدون تسجيل ولا إيميل.</p>' +
        '<div class="sf" style="margin-top:12px"><input id="sc-nick" maxlength="20" placeholder="اسمك أو لقبك" aria-label="اسمك" autocomplete="nickname"></div>' +
        '<div class="th-acts"><button type="button" class="pill pri" id="sc-join">ابدأ</button></div></div>';
      return;
    }
    var pts = {}; (ME ? ME.squad : []).forEach(function (x) { pts[x.p] = x.pts; });
    var rows = (DRAFT || []).map(function (id) {
      var p = BY[id] || { id: id, n: "لاعب", c: "", age: "", tn: "" };
      var got = pts[id] != null ? '<span class="rv"><b class="num">' + pts[id] + "</b><small> " + ptsW(pts[id]) + " معك</small></span>" : '<span class="rv"><small>جديد</small></span>';
      return '<div class="row"><span class="rt">' + name(p) + "<small>" + esc(line(p)) + "</small></span>" + got + '<button type="button" class="pill" data-drop="' + id + '" style="min-height:36px;padding:0 12px;margin-inline-start:8px">شيله</button></div>';
    });
    for (var i = rows.length; i < SQUAD; i++) rows.push('<div class="row"><span class="rt" style="color:var(--label2)">مكان فاضي<small>اختر لاعب من القائمة تحت</small></span></div>');
    var head = ME ? '<div class="lc" style="padding:12px 16px 4px"><p style="margin:0"><b class="num" style="font-size:28px">' + nf(ME.total) + "</b> " + ptsW(ME.total) +
      (ME.rank ? " · مركزك <b class=\"num\">" + ME.rank + "</b> من " + nf(ME.n) : "") + (ME.banked ? '<br><small style="color:var(--label2)">منها ' + ME.banked + " من لاعبين بدّلتهم</small>" : "") + "</p></div>" : "";
    var foot = '<div class="th-acts" style="flex-wrap:wrap">' + (dirty() ? '<button type="button" class="pill pri" id="sc-save">احفظ خمستك</button>' : "") +
      '</div><p class="note" style="margin-top:10px">' + (ME ? "باقي لك " + (ME.changes_left === 1 ? "تبديل واحد" : ME.changes_left === 2 ? "تبديلين" : ME.changes_left + " تبديلات") + " هالأسبوع. تعبئة المكان الفاضي ما تحسب." : "") + "</p>";
    box.innerHTML = '<div class="card">' + head + rows.join("") + "</div>" + foot;
  }

  // ------------------------------------------------------------------ the pool
  function paintPool() {
    var box = D.getElementById("sc-pool"); if (!box) return;
    var q = FILTER.q.trim().toLowerCase(), inD = {}; (DRAFT || []).forEach(function (id) { inD[id] = 1; });
    var list = POOL.filter(function (p) { return (!FILTER.c || p.c === FILTER.c) && (!q || (p.n + " " + p.en + " " + (p.tn || "")).toLowerCase().indexOf(q) >= 0); });
    var full = (DRAFT || []).length >= SQUAD;
    box.innerHTML = '<div class="card">' + list.slice(0, SHOW).map(function (p) {
      var on = !!inD[p.id];
      return '<div class="row"><span class="rt">' + name(p) + "<small>" + esc(line(p)) + "</small><small>" + esc(stats(p)) + '</small></span><span class="rv"><b class="num">' + p.pts + "</b><small> " + ptsW(p.pts) + "</small></span>" +
        (token() ? '<button type="button" class="pill' + (on ? "" : " pri") + '" data-' + (on ? "drop" : "add") + '="' + p.id + '"' + (!on && full ? " disabled" : "") + ' style="min-height:36px;padding:0 12px;margin-inline-start:8px">' + (on ? "في خمستك" : "ضمّه") + "</button>" : "") + "</div>";
    }).join("") + (list.length ? "" : '<p class="empty">ما لقينا لاعب بهالبحث.</p>') + "</div>" +
      (list.length > SHOW ? '<div class="th-acts"><button type="button" class="pill" id="sc-more">اعرض أكثر (' + (list.length - SHOW) + ")</button></div>" : "");
  }
  function chips() {
    var n = {}; POOL.forEach(function (p) { n[p.c] = (n[p.c] || 0) + 1; });
    var cs = Object.keys(n).sort(function (a, b) { return n[b] - n[a]; });
    D.getElementById("sc-cc").innerHTML = ['<button type="button" class="ccb" data-cc="" aria-pressed="' + (!FILTER.c) + '">الكل</button>'].concat(cs.map(function (c) {
      return '<button type="button" class="ccb" data-cc="' + c + '" aria-pressed="' + (FILTER.c === c) + '">' + esc(CC[c] || c) + ' <span class="num" style="opacity:.6">' + n[c] + "</span></button>";
    })).join("");
  }

  // ------------------------------------------------------------------ the board
  function paintBoard() {
    var box = D.getElementById("sc-board"); if (!box) return;
    api("GET", API + "board").then(function (b) {
      if (!b.top || !b.top.length) { box.innerHTML = '<div class="card lc"><p class="empty">الترتيب يطلع أول ما يبدأ الكشّافين يجمعون نقاط. يتحدّث كل نص ساعة.</p></div>'; return; }
      box.innerHTML = '<div class="card">' + b.top.slice(0, 20).map(function (x, i) {
        return '<div class="row"' + (x.me ? ' style="background:var(--accent-bg)"' : "") + '><span class="rv" style="min-width:2em"><b class="num">' + (i + 1) + '</b></span><span class="rt">' + esc(x.nick) + (x.me ? " <small>(انت)</small>" : "") + '</span><span class="rv"><b class="num">' + nf(x.pts) + "</b></span></div>";
      }).join("") + "</div>" + (b.me && b.me.rank > 20 ? '<p class="note" style="margin-top:10px">انت في المركز ' + b.me.rank + " من " + nf(b.n) + " بـ" + nf(b.me.total) + " " + ptsW(b.me.total) + ".</p>" : "");
    }).catch(function () { box.innerHTML = ""; });
  }

  // ------------------------------------------------------------------ load and act
  function loadMe() {
    if (!token()) { ME = null; DRAFT = []; paintFive(); paintPool(); return Promise.resolve(); }
    return api("GET", API + "me").then(function (j) { ME = j; DRAFT = saved(); }).catch(function (e) { ME = null; DRAFT = DRAFT || []; if (e.status !== 401) toast(e.message); })
      .then(function () { paintFive(); paintPool(); });
  }
  root.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest("button"); if (!t) return;
    if (t.id === "sc-join") {
      var nick = (D.getElementById("sc-nick") || {}).value || ""; if (!nick.trim()) return toast("اكتب اسمك أول");
      t.disabled = true;
      return api("POST", "/api/tifo/predict/me", { nick: nick.trim() }).then(function (j) { ls.set("tifo.predict", JSON.stringify({ pid: j.pid, token: j.token, nick: j.nick, code: j.code, fresh: 1 })); toast("حيّاك يا " + j.nick + ". رمز استرجاع حسابك في «توقعاتي»."); return loadMe(); })
        .catch(function (x) { t.disabled = false; toast(x.message); });
    }
    if (t.dataset.add) { var id = +t.dataset.add; if ((DRAFT || []).length < SQUAD && DRAFT.indexOf(id) < 0) DRAFT.push(id); paintFive(); paintPool(); return; }
    if (t.dataset.drop) { var d = +t.dataset.drop; DRAFT = (DRAFT || []).filter(function (x) { return x !== d; }); paintFive(); paintPool(); return; }
    if (t.id === "sc-save") {
      if (!DRAFT.length) return toast("اختر لاعب واحد على الأقل");
      t.disabled = true;
      return api("PUT", API + "squad", { players: DRAFT }).then(function (j) { ME = j; DRAFT = saved(); ls.set("tifo.scout.saved", "1");   /* «كشّاف» badge (src/badges.js) */ toast("انحفظت خمستك. النقاط تنحسب من مبارياتهم الياية."); paintFive(); paintPool(); paintBoard(); })
        .catch(function (x) { t.disabled = false; toast(x.message); });
    }
    if (t.dataset.cc != null) { FILTER.c = t.dataset.cc; SHOW = 40; chips(); paintPool(); return; }
    if (t.id === "sc-more") { SHOW += 60; paintPool(); }
  });
  root.addEventListener("input", function (e) { if (e.target.id === "sc-q") { FILTER.q = e.target.value; SHOW = 40; paintPool(); } });

  fetch("/scout/pool.json").then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
    POOL = (j && j.players) || []; POOL.forEach(function (p) { BY[p.id] = p; });
    var w = D.getElementById("sc-when"); if (w && j && j.generated && U.tm) w.innerHTML = "القائمة والنقاط محدّثة " + U.tm(j.generated, "r"); if (w) w.hidden = false;   // U.tm: a <time> the app keeps current
    chips(); return loadMe();
  }).catch(function () { toast("ما قدرنا نحمّل قائمة المواهب، جرّب بعد شوي"); });
  paintBoard();
})();
