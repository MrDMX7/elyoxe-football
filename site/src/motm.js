/* تيفو «رجل المباراة بصوت الجمهور» (owner's second list, 2, 2026-10-06): after the final whistle the fans pick the man of the
   match with one tap, no signup (the device key of «اصنع التيفو», localStorage tifo.fan), one vote a match; the result shows
   beside the match's highest FotMob rating, named as such. Server: saas/cards src/tifo_fans.py (POST /api/tifo/fans/vote; the
   votes ride on GET /api/tifo/fans/tiles?match=, cached 10 s at the edge). The players are the ones who played: the match
   file's starters and the substitutes who came on, Arabic names from the page (window.PN). Open from the whistle until 48 h
   after the end, as the server; the results show once the fan has voted, so they don't lead the vote. On the v5 tokens;
   light Emirati, Western digits. */
(function () {
  "use strict";
  var D = document, B = D.body;
  if (!B || B.dataset.page !== "match" || !window.fetch) return;
  var V = window.V5 || {}, MID = +(V.id || B.dataset.id || 0);
  if (!MID || !V.ko) return;
  var API = "/api/tifo/fans/", HOUR = 36e5, BOX = null, PL = {}, OFF = null, POLL = null;
  var ls = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var finished = function (st) { return st === "finished" || st === "awarded"; };
  var inWindow = function () { var ko = Date.parse(V.ko); return !!ko && Date.now() < ko + 50 * HOUR; };
  var votes = function (n) { return n === 1 ? "صوت واحد" : n === 2 ? "صوتين" : n <= 10 ? n + " أصوات" : n + " صوت"; };
  var nm = function (p) { return (window.PN && window.PN[p.id]) || p.name || ""; };
  var mine = function () { var v = +ls.get("tifo.motm." + MID); return v || null; };

  function dev() {
    var k = ls.get("tifo.fan");
    if (!k || !/^[A-Za-z0-9_-]{16,64}$/.test(k)) {
      var a = new Uint8Array(18); (window.crypto || {}).getRandomValues ? crypto.getRandomValues(a) : a.forEach(function (_, i) { a[i] = Math.random() * 256; });
      k = "f" + Array.prototype.map.call(a, function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
      ls.set("tifo.fan", k);
    }
    return k;
  }

  // who played, per side, and the highest rating among them (FotMob's, named as the highest rating, not as an award)
  function players(md) {
    var out = { home: [], away: [] };
    ["home", "away"].forEach(function (s) {
      var lu = (md.lineups || {})[s] || {};
      (lu.starters || []).forEach(function (p) { if (p && p.id) out[s].push(p); });
      (lu.subs || []).forEach(function (p) { if (p && p.id && (p.minutes_on != null || p.rating != null)) out[s].push(p); });
      out[s].forEach(function (p) { PL[p.id] = p; if (p.rating != null && (!OFF || p.rating > OFF.rating)) OFF = p; });
    });
    return out;
  }

  function results(j) {
    var res = D.getElementById("motm-res"), n = D.getElementById("motm-n"), me = mine();
    if (!res || !j || !j.n) return;
    if (n) n.textContent = votes(j.n);
    res.innerHTML = (j.top || []).map(function (x) {
      var p = PL[x[0]] || { id: x[0], name: "" }, pc = Math.round(x[1] * 100 / j.n);
      return '<div class="motm-r' + (x[0] === me ? " me" : "") + '"><span class="motm-rn">' + esc(nm(p)) + (x[0] === me ? " <small>صوتك</small>" : "") + '</span><span class="motm-bar"><i style="width:' + pc + '%"></i></span><b class="num">' + pc + "%</b></div>";
    }).join("");
    res.hidden = false;
  }
  function refresh() { if (D.hidden) return; fetch(API + "tiles?match=" + MID).then(function (r) { return r.ok ? r.json() : null; }).then(results).catch(function () {}); }
  function voted() {
    var q = D.getElementById("motm-q"), cols = D.getElementById("motm-cols");
    if (cols) cols.hidden = true;
    if (q) q.textContent = "صوتك وصل. هذي النتيجة للحين:";
    refresh();
    if (!POLL) POLL = setInterval(refresh, 30000);
  }
  function cast(pid) {
    var q = D.getElementById("motm-q"), cols = D.getElementById("motm-cols");
    if (cols) [].forEach.call(cols.querySelectorAll("button"), function (b) { b.disabled = true; });
    fetch(API + "vote", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ match: MID, player: pid, dev: dev() }) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (x) {
        if (!x.ok) throw new Error((x.j && x.j.error) || "");
        ls.set("tifo.motm." + MID, String(x.j.p));
        voted(); results(x.j);
      })
      .catch(function (e) {
        if (cols) [].forEach.call(cols.querySelectorAll("button"), function (b) { b.disabled = false; });
        if (q) q.textContent = e && e.message ? e.message : "ما قدرنا نسجّل صوتك، جرّب بعد شوي";
      });
  }

  function start(md) {
    if (BOX || !inWindow() || !md || !md.lineups) return;
    var ps = players(md); if (!ps.home.length && !ps.away.length) return;
    var css = D.createElement("style"); css.id = "motm-css";
    css.textContent = "#motm .motm-q{margin:0;padding:14px 16px 6px;color:var(--label,#000);font-size:15px}" +
      "#motm .motm-cols{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:6px 12px 12px}#motm .motm-cols h3{margin:0 4px 6px;color:var(--label2,#6b6b70);font-size:13px;font-weight:500}" +
      "#motm .motm-p{display:flex;align-items:center;justify-content:space-between;gap:6px;width:100%;min-height:44px;margin:0 0 6px;padding:0 12px;border-radius:var(--r-s,10px);background:var(--fill,#7878801f);color:var(--label,#000);font-size:14px;text-align:start}" +
      "#motm .motm-p b{color:var(--label2,#6b6b70);font-size:12px;font-weight:500}#motm .motm-res{padding:4px 16px 6px}" +
      "#motm .motm-r{display:grid;grid-template-columns:minmax(0,1fr) 34% 42px;align-items:center;gap:8px;min-height:40px;font-size:14px}#motm .motm-r.me .motm-rn{font-weight:700}#motm .motm-r small{color:var(--accent,#0B8246);font-size:11px}" +
      "#motm .motm-rn{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}#motm .motm-bar{height:8px;border-radius:4px;background:var(--fill,#7878801f);overflow:hidden}#motm .motm-bar i{display:block;height:100%;border-radius:4px;background:var(--accent,#0B8246)}" +
      "#motm .motm-r b{text-align:end;font-weight:600}#motm .motm-off{margin:0;padding:8px 16px 14px;color:var(--label2,#6b6b70);font-size:13px}";
    D.head.appendChild(css);
    var col = function (side) {
      return "<div><h3>" + esc(side === "home" ? V.hn || "" : V.an || "") + "</h3>" + ps[side].map(function (p) {
        return '<button type="button" class="motm-p" data-p="' + p.id + '"><span>' + esc(nm(p)) + "</span>" + (p.rating != null ? '<b class="num">' + (+p.rating).toFixed(1) + "</b>" : "") + "</button>";
      }).join("") + "</div>";
    };
    BOX = D.createElement("section"); BOX.className = "grp"; BOX.id = "motm";
    BOX.innerHTML = '<div class="gh"><h2>رجل المباراة بصوت الجمهور</h2><span class="num" id="motm-n"></span></div><div class="card">' +
      '<p class="motm-q" id="motm-q" aria-live="polite">منو رجل المباراة؟ صوّت بضغطة.</p><div class="motm-cols" id="motm-cols">' + col("home") + col("away") + "</div>" +
      '<div class="motm-res" id="motm-res" hidden></div>' +
      (OFF ? '<p class="motm-off">الأعلى تقييماً في المباراة: ' + esc(nm(OFF)) + ' <b class="num">' + (+OFF.rating).toFixed(1) + "</b></p>" : "") + "</div>";
    var after = D.getElementById("fanmosaic") || D.querySelector("[data-predict]") || (D.getElementById("ev") && D.getElementById("ev").closest("section"));
    var pane = D.querySelector('.pane[data-g="m"][data-p="ov"]');
    if (after && after.parentNode) after.parentNode.insertBefore(BOX, after.nextSibling);
    else if (pane) pane.insertBefore(BOX, pane.firstChild);
    else { BOX = null; return; }
    BOX.addEventListener("click", function (e) { var b = e.target.closest && e.target.closest("button[data-p]"); if (b) cast(+b.dataset.p); });
    if (mine()) voted();
  }

  // a page built after the whistle, or a live page that reaches it (v5's app.js fires tifo:match on every poll)
  if (finished(V.status)) fetch("/v1/match/" + MID + ".json").then(function (r) { return r.ok ? r.json() : null; }).then(start).catch(function () {});
  D.addEventListener("tifo:match", function (e) { var md = e.detail || {}; if (finished(md.status)) start(md); });
  D.addEventListener("visibilitychange", function () { if (!D.hidden && BOX && mine()) refresh(); });
})();
