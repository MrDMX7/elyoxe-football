/* تيفو «أوسمة المشجع» (owner's second list, 9, 2026-10-06): quiet badges for what the fan did on Tifo, counted from what his phone
   already keeps (no account, nothing sent): the season's trail (tifo.trail, src/trail.js: matches opened, followed live, goals
   seen go in, competitions), his settled picks (tifo.picks), his card in «اصنع التيفو» (tifo.fan.<match>), his man-of-the-match
   votes (tifo.motm.<match>), his couch-coach elevens (tifo.coach.<match>) and his scout five (tifo.scout.saved, src/scout.js).
   On /badges/ every badge with its progress; elsewhere (the pages where one can be earned) a badge earned since the last visit
   shows once, quietly, in the shell's toast with a link to /badges/ (tifo.badges.seen). Light Emirati, Western digits. */
(function () {
  "use strict";
  var D = document, B = D.body;
  if (!B || /bot|crawl|spider|lighthouse/i.test(navigator.userAgent || "")) return;
  var ls = function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } };
  var json = function (k, d) { try { var v = JSON.parse(ls(k) || "null"); return v == null ? d : v; } catch (e) { return d; } };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };

  // ------------------------------------------------------------------ what the phone kept
  function facts() {
    var t = json("tifo.trail", {}), picks = json("tifo.picks", {}), f = { opened: 0, live: 0, goals: 0, comps: 0, late: 0, right: 0, cards: 0, votes: 0, coach: 0, scout: ls("tifo.scout.saved") ? 1 : 0 }, cs = {};
    Object.keys(t).forEach(function (id) {
      var e = t[id] || {}; f.opened++; if (e.l) f.live++; f.goals += +e.g || 0; if (e.cn) cs[e.cn] = 1;
      if (e.l && e.ko) { var h = new Date(e.ko).getHours(); if (h >= 0 && h < 4) f.late++; }   // a kickoff after midnight, his own clock
    });
    f.comps = Object.keys(cs).length;
    Object.keys(picks).forEach(function (k) { if (picks[k] && picks[k].r === 1) f.right++; });
    try { for (var i = 0; i < localStorage.length; i++) { var k = localStorage.key(i); if (/^tifo\.fan\.\d+$/.test(k)) f.cards++; else if (/^tifo\.motm\.\d+$/.test(k)) f.votes++; else if (/^tifo\.coach\.\d+$/.test(k)) f.coach++; } } catch (e) {}
    return f;
  }
  var LIST = [
    ["first", "أول مباراة", "فتحت أول مباراة في تيفو", "opened", 1],
    ["follow10", "متابع", "تابعت 10 مباريات وهي تنلعب", "live", 10],
    ["follow50", "ما تفوته مباراة", "تابعت 50 مباراة وهي تنلعب", "live", 50],
    ["goals10", "شاهد عيان", "شفت 10 أهداف تدخل على المباشر", "goals", 10],
    ["goals50", "عين ما تنام", "شفت 50 هدف تدخل على المباشر", "goals", 50],
    ["comps5", "رحّال", "تابعت مباريات من 5 بطولات", "comps", 5],
    ["late", "سهران", "تابعت مباراة بدت بعد نص الليل", "late", 1],
    ["right5", "متوقع", "5 توقعات طلعت صح", "right", 5],
    ["right20", "قارئ الملعب", "20 توقع طلع صح", "right", 20],
    ["card1", "في المدرّج", "رفعت كرتك في «اصنع التيفو»", "cards", 1],
    ["card10", "ألتراس", "رفعت كرتك في 10 مباريات", "cards", 10],
    ["vote1", "صوت الجمهور", "صوّت لرجل المباراة", "votes", 1],
    ["coach1", "مدرّب الدكة", "سوّيت تشكيلتك قبل مباراة", "coach", 1],
    ["scout1", "كشّاف", "اخترت خمستك في «كشّاف تيفو»", "scout", 1]
  ];
  var F = facts(), EARNED = LIST.filter(function (b) { return F[b[3]] >= b[4]; }).map(function (b) { return b[0]; });

  // ------------------------------------------------------------------ the page
  var root = D.getElementById("bdg");
  if (root) {
    root.innerHTML = '<section class="grp"><div class="gh"><h2>أوسمتك</h2><span class="num">' + EARNED.length + " من " + LIST.length + '</span></div><div class="card">' + LIST.map(function (b) {
      var have = Math.min(F[b[3]], b[4]), on = have >= b[4], pct = Math.round(have / b[4] * 100);
      return '<div class="row ins"' + (on ? "" : ' style="opacity:.62"') + '><span class="ic" style="--c:' + (on ? "#FF9F0A" : "#8E8E93") + '">' + (window.U5 ? window.U5.icon(on ? "medal" : "target", "", 2) : "") + "</span>" +
        '<span class="rt">' + esc(b[1]) + "<small>" + esc(b[2]) + "</small></span>" +
        '<span class="rv">' + (on ? "<b>✓</b>" : '<span class="num">' + have + " من " + b[4] + '</span><span style="display:block;width:56px;height:5px;margin-top:4px;border-radius:3px;background:var(--fill2);overflow:hidden"><i style="display:block;height:100%;width:' + pct + '%;background:var(--accent)"></i></span>') + "</span></div>";
    }).join("") + '</div><p class="note" style="margin-top:12px">الأوسمة من اللي محفوظ على جوالك بس: المباريات اللي تفتحها وتتابعها، وتوقعاتك، والمدرّج، وتشكيلاتك. ما في حساب وما ترسل لأحد.</p></section>';
    try { localStorage.setItem("tifo.badges.seen", JSON.stringify(EARNED)); } catch (e) {}
    return;
  }

  // ------------------------------------------------------------------ elsewhere: a new badge, once, quietly
  function check() {
    var seen = json("tifo.badges.seen", null), now = LIST.filter(function (b) { return facts()[b[3]] >= b[4]; }).map(function (b) { return b[0]; });
    if (seen === null) { try { localStorage.setItem("tifo.badges.seen", JSON.stringify(now)); } catch (e) {} return; }   // the first visit since badges: no flood of old ones
    var fresh = now.filter(function (id) { return seen.indexOf(id) < 0; });
    if (!fresh.length) return;
    try { localStorage.setItem("tifo.badges.seen", JSON.stringify(now)); } catch (e) {}
    var b = LIST.filter(function (x) { return x[0] === fresh[0]; })[0], el = D.getElementById("toast"); if (!el || !b) return;
    el.innerHTML = '<a href="/badges/">وسام جديد: ' + esc(b[1]) + (fresh.length > 1 ? " وغيره" : "") + "</a>"; el.classList.add("lnk", "on");
    setTimeout(function () { el.classList.remove("on"); }, 5000);
  }
  setTimeout(check, 2500);
  D.addEventListener("tifo:match", function () { setTimeout(check, 500); });   // a goal seen, a card raised, a vote: the page's own events
  D.addEventListener("visibilitychange", function () { if (!D.hidden) check(); });
})();
