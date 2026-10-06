/* تيفو «المعلقين» (item 3, owner 2026-10-06): a page per famous commentator and «معلّقك المفضل», read from
   /v1/tv/commentators.json (news/tvindex.py: Kooora's daily channel-and-commentator lists tied to our fixtures, kept 60 days).
   Facts from that data only, nothing written about a person: the channels he called on, the matches today and next, the
   recent ones, the competitions, and since when we have him. The source line says where it comes from.
   Markup: site/redesign/v5 (large title, grouped inset lists, rows, one pill, <dialog class="sheet">). Contract (docs/ENGAGEMENT.md):
     TifoVoices.load()               Promise<index> (one file, cached for the page)
     TifoVoices.page(index, id)      a commentator's page body (id: his key or slug); pure, the build can prerender it
     TifoVoices.list(index)          /commentators/: every famous voice, the ones with a match today first
     TifoVoices.picker(index)        the «معلّقك المفضل» sheet body (a switch per voice)
     TifoVoices.mount(root)          wires the [data-voice] follow pills and switches under root (idempotent)
     TifoVoices.favs() / setFavs([keys])     localStorage tifo.voices
     TifoVoices.decorate(root)       marks the match rows a favourite voice calls (.mr[data-mid] in v5, a.m[data-mid] on the
                                     live site): class "fav-voice" and a «🎙 name · channel» line
   Event: document "tifo:voices" {keys} after a change. */
(function (root) {
  "use strict";
  var SRC = "/v1/tv/commentators.json";
  var esc = function (s) { return s == null ? "" : String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var MON = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
  var dayAr = function (ymd) { var m = /^(\d{4})-(\d\d)-(\d\d)/.exec(ymd || ""); return m ? +m[3] + " " + MON[+m[2] - 1] + " " + m[1] : ""; };
  var CHEV = '<svg class="chev" viewBox="0 0 9 15" aria-hidden="true"><path d="M7.4 1.5L1.6 7.5l5.8 6" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var MIC = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5v3.5"/></svg>';
  var n = function (x, w) { return x === 1 ? w[0] : x === 2 ? w[1] : x >= 3 && x <= 10 ? x + " " + w[2] : x + " " + w[0]; };

  function find(ix, id) {
    var c = (ix && ix.commentators) || {}; if (c[id]) return [id, c[id]];
    for (var k in c) if (c[k].slug === id || c[k].name === id) return [k, c[k]];
    return null;
  }
  function href(id, m) { return m && m.page ? "/m/" + id + "/" : "/live/?id=" + id; }
  function koLabel(iso, opt) {
    if (opt && opt.when) return opt.when(iso);
    return '<time data-voice-time="' + esc(iso) + '">' + esc(String(iso || "").slice(11, 16)) + "</time>";
  }
  function matchRow(ix, ref, opt) {
    var id = ref[0], m = (ix.matches || {})[id]; if (!m) return "";
    var h = (m.h || [])[1] || "", a = (m.a || [])[1] || "", c = (m.c || [])[1] || "";
    return '<a class="row" href="' + esc(href(id, m)) + '" data-mid="' + esc(id) + '"><span class="rt">' + esc(h) + " ضد " + esc(a) + "<small>" + esc(ref[1]) + (c ? " · " + esc(c) : "") + "</small></span>" +
      '<span class="rv">' + koLabel(m.ko, opt) + "</span>" + CHEV + "</a>";
  }
  function grp(title, inner, foot) { return '<section class="grp"><div class="gh"><h2>' + title + '</h2></div><div class="card">' + inner + "</div>" + (foot ? '<p class="gf">' + foot + "</p>" : "") + "</section>"; }

  // ------------------------------------------------------------------ markup (pure: Node can prerender it)
  function page(ix, id, opt) {
    var hit = find(ix, id); if (!hit) return '<div class="card"><p class="empty">ما عندنا هالمعلّق في جداول الأيام الأخيرة.</p></div>';
    var key = hit[0], v = hit[1], top = (v.channels || [])[0];
    var fact = "علّق على " + n(v.n, ["مباراة", "مباراتين", "مباريات"]) + " من " + dayAr(ix.since) + (top ? "، أكثرها على " + esc(top[0]) : "") + ".";
    var head = '<header class="lt vc-head"><h1>' + esc(v.name) + '</h1><p class="sub">' + fact + '</p><div class="th-acts"><button type="button" class="pill pri" data-voice="' + esc(key) + '" aria-pressed="false">' + MIC + "<span>معلّقي المفضل</span></button></div></header>";
    var next = (v.next || []).map(function (r) { return matchRow(ix, r, opt); }).join("");
    var rec = (v.recent || []).map(function (r) { return matchRow(ix, r, opt); }).join("");
    var ch = (v.channels || []).map(function (c) { return '<div class="row"><span class="rt">' + esc(c[0]) + '</span><span class="rv num">' + c[1] + "</span></div>"; }).join("");
    var cs = (v.comps || []).map(function (c) { return '<div class="row"><span class="rt">' + esc(c[1] || "بطولات ثانية") + '</span><span class="rv num">' + c[2] + "</span></div>"; }).join("");
    return head + grp("اليوم والياي", next || '<p class="empty">ما انعلن له مباراة للحين. جدول المعلقين ينزل كل يوم بعد نص الليل.</p>') +
      (rec ? grp("آخر مبارياته", rec) : "") + (ch ? grp("القنوات", ch, "كم مباراة علّق عليها في كل قناة.") : "") + (cs ? grp("البطولات", cs) : "") +
      '<p class="gf vc-src">المصدر: ' + esc(ix.source || "") + ". المواعيد بتوقيت بلدك.</p>";
  }
  function list(ix, opt) {
    var c = (ix && ix.commentators) || {}, keys = Object.keys(c);
    keys.sort(function (a, b) { return (c[b].next.length ? 1 : 0) - (c[a].next.length ? 1 : 0) || c[b].n - c[a].n; });
    var rows = keys.map(function (k) { var v = c[k], nx = v.next[0], m = nx && (ix.matches || {})[nx[0]];
      return '<a class="row" href="/commentators/' + esc(encodeURIComponent(v.slug)) + '/"><span class="rt">' + esc(v.name) + "<small>" + (m ? "مباراته الياية: " + esc((m.h || [])[1]) + " ضد " + esc((m.a || [])[1]) + " · " + esc(nx[1]) : n(v.n, ["مباراة", "مباراتين", "مباريات"])) + "</small></span>" + CHEV + "</a>"; }).join("");
    return grp("المعلقين", rows || '<p class="empty">ما في جداول معلقين للحين.</p>', "من " + dayAr(ix.since) + ". المصدر: " + esc(ix.source || ""));
  }
  function picker(ix) {
    var c = (ix && ix.commentators) || {};
    return '<p class="note">نعلّم لك مبارياتهم في القوائم.</p><section class="grp"><div class="card">' + Object.keys(c).map(function (k) {
      return '<button type="button" class="row" role="switch" aria-checked="false" data-voice="' + esc(k) + '"><span class="rt">' + esc(c[k].name) + "<small>" + n(c[k].n, ["مباراة", "مباراتين", "مباريات"]) + '</small></span><span class="sw" aria-hidden="true"></span></button>';
    }).join("") + "</div></section>";
  }

  var V = { page: page, list: list, picker: picker, find: find };
  if (typeof module !== "undefined" && module.exports) { module.exports = V; return; }
  if (typeof document === "undefined") return;

  // ------------------------------------------------------------------ the browser
  var D = document, IX = null;
  function load() { return IX || (IX = fetch(SRC, { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).catch(function () { IX = null; return { commentators: {}, matches: {} }; })); }
  function favs() { try { return JSON.parse(localStorage.getItem("tifo.voices") || "[]"); } catch (e) { return []; } }
  function setFavs(keys) { try { localStorage.setItem("tifo.voices", JSON.stringify(keys)); } catch (e) {} D.dispatchEvent(new CustomEvent("tifo:voices", { detail: { keys: keys } })); }
  function when(iso) {
    if (root.U5 && root.U5.timeText) try { return root.U5.timeText(iso, "dt"); } catch (e) {}
    try { return new Date(iso).toLocaleString("ar-AE-u-nu-latn", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false }); } catch (e) { return ""; }
  }
  function times(r) { (r || D).querySelectorAll("time[data-voice-time]").forEach(function (t) { t.textContent = when(t.getAttribute("data-voice-time")); }); }
  function paint(r) { var f = favs(); (r || D).querySelectorAll("[data-voice]").forEach(function (b) { var on = f.indexOf(b.dataset.voice) >= 0; b.setAttribute(b.getAttribute("role") === "switch" ? "aria-checked" : "aria-pressed", String(on)); if (b.classList.contains("pill")) b.classList.toggle("on", on); }); }
  function mount(r) {
    r = r || D; times(r); paint(r);
    if (r.dataset && r.dataset.voiceOn) return; if (r.dataset) r.dataset.voiceOn = "1";
    r.addEventListener("click", function (e) {
      var b = e.target.closest("[data-voice]"); if (!b) return;
      var f = favs(), k = b.dataset.voice, i = f.indexOf(k); if (i >= 0) f.splice(i, 1); else f.push(k); setFavs(f); paint(D); decorate(D);
    });
  }
  (function () {
    if (D.getElementById("voice-css")) return;
    var c = D.createElement("style"); c.id = "voice-css";
    c.textContent = ".vc-head{padding:8px 4px 4px}.vc-head .sub{margin-top:6px;color:var(--label2,#6b6b70);font-size:15px}.vc-head .th-acts{margin-top:12px}.vc-head .pill svg{width:18px;height:18px}" +
      ".fav-voice{box-shadow:inset -3px 0 0 var(--accent,#0B8246)}.voice-cap{display:block;grid-column:1/-1;text-align:center;font-size:12px;color:var(--accent,#0B8246);font-weight:600;margin-top:2px}";
    D.head.appendChild(c);
  })();
  function decorate(r) {
    var f = favs(); if (!f.length) { (r || D).querySelectorAll(".fav-voice").forEach(function (x) { x.classList.remove("fav-voice"); var c = x.querySelector(".voice-cap"); if (c) c.remove(); }); return Promise.resolve(); }
    return load().then(function (ix) {
      var by = {};
      f.forEach(function (k) { var v = (ix.commentators || {})[k]; if (v) (v.next || []).concat(v.recent || []).forEach(function (x) { (by[x[0]] = by[x[0]] || []).push([v.name, x[1]]); }); });
      (r || D).querySelectorAll(".mr[data-mid],a.m[data-mid]").forEach(function (a) {
        var hit = by[a.dataset.mid], cap = a.querySelector(".voice-cap");
        a.classList.toggle("fav-voice", !!hit);
        if (!hit) { if (cap) cap.remove(); return; }
        var t = "🎙 " + hit.map(function (x) { return x[0]; }).join(" و") + " · " + hit[0][1];
        if (!cap) { cap = D.createElement("span"); cap.className = "voice-cap"; a.appendChild(cap); }
        if (cap.textContent !== t) cap.textContent = t;
      });
    });
  }
  root.TifoVoices = { load: load, page: page, list: list, picker: picker, mount: mount, favs: favs, setFavs: setFavs, decorate: decorate, when: when };
  // on its own: wires the pills and switches the page carries (a commentator's page, the picker in «المزيد»), marks the match rows
  // a favourite voice calls, and marks them again when a list redraws (v5's app.js, src/days.js); nothing to do without favourites
  function boot() {
    mount(D); if (!favs().length) return; decorate(D);
    var q = 0, main = D.getElementById("main");
    if (main && "MutationObserver" in window) new MutationObserver(function () { if (q) return; q = setTimeout(function () { q = 0; decorate(D); }, 300); }).observe(main, { childList: true, subtree: true });
  }
  if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", boot); else boot();
})(typeof window !== "undefined" ? window : this);
