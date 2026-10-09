/* تيفو «تيفو ريوايند» (owner bold idea 5, 2026-10-06): the season's story of one fan, as stories to share, from what his
   device kept (no account, nothing sent):
   - «tifo.trail» (src/trail.js on every match page): the matches he opened, which ones around their live time, the goals he
     saw go in, the competitions
   - «tifo.picks»: his result picks on match pages, settled at the whistle (r: 1 right, 0 wrong)
   - «tifo.fan.<match>» / «tifo.motm.<match>»: his card in «اصنع التيفو», his man-of-the-match vote
   - «tifo.mine»: his team; its season record is the official one, its row in its league's table (/v1/comp/<id>/standings.json)
   Each story is a 1080×1920 canvas (the size of a phone story), shown one at a time and shared or saved as it is. A story shows
   only when its numbers exist; with nothing kept yet, the page says how the trail fills. Until the season ends it is «لين
   الحين»; from SEASON.end, the whole season. Light Emirati, Western digits. */
(function () {
  "use strict";
  var D = document, B = D.body, U = window.U5, root = D.getElementById("rw");
  if (!B || !root || !U || !window.HTMLCanvasElement) return;
  var SEASON = { from: "2026-07-01", end: "2027-06-01", label: "2026-27" };
  var W = 1080, H = 1920, NOW = Date.now(), DONE = NOW >= Date.parse(SEASON.end);
  var GREEN = "#0B3B26", GREEN2 = "#0B8246", MINT = "#7CF0B4", CHALK = "#FFFFFF", SOFT = "rgba(255,255,255,.72)", FAINT = "rgba(255,255,255,.16)";
  var ls = function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } };
  var json = function (k, d) { try { var v = JSON.parse(ls(k) || "null"); return v == null ? d : v; } catch (e) { return d; } };
  var MON = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
  var dayAr = function (t) { var d = new Date(t); return d.getDate() + " " + MON[d.getMonth()]; };
  var nf = function (n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ","); };
  // Arabic counting: the noun after a number is plural from 3 to 10 (by the last two digits), dual for 2, singular otherwise; under
  // a big numeral the singular stands for 2 as well («2 صوت»: the dual would say the number twice)
  var unit = function (n, one, two, few) { var r = n % 100; return n === 2 ? two : r >= 3 && r <= 10 ? few : one; };
  var count = function (n, one, two, few) { return n === 1 ? one : n === 2 ? two : n + " " + unit(n, one, two, few); };

  // ------------------------------------------------------------------ what the device kept, this season
  var from = Date.parse(SEASON.from), trail = json("tifo.trail", {}), M = [];
  Object.keys(trail).forEach(function (id) { var e = trail[id]; if (e && e.ko && Date.parse(e.ko) >= from && Date.parse(e.ko) <= NOW + 864e5) M.push(Object.assign({ id: +id }, e)); });
  M.sort(function (a, b) { return Date.parse(a.ko) - Date.parse(b.ko); });
  var live = M.filter(function (m) { return m.l; }), seen = M.reduce(function (s, m) { return s + (m.g || 0); }, 0);
  var comps = {}; M.forEach(function (m) { if (m.cn) comps[m.cn] = (comps[m.cn] || 0) + 1; });
  var topComps = Object.keys(comps).sort(function (a, b) { return comps[b] - comps[a]; }).slice(0, 3).map(function (k) { return [k, comps[k]]; });
  var mostSeen = live.filter(function (m) { return m.g; }).sort(function (a, b) { return b.g - a.g || Date.parse(b.ko) - Date.parse(a.ko); })[0] || null;
  var picks = json("tifo.picks", {}), P = Object.keys(picks).map(function (k) { return picks[k]; }).filter(function (p) { return p && p.r != null && Date.parse(p.ko) >= from; });
  P.sort(function (a, b) { return Date.parse(a.ko) - Date.parse(b.ko); });
  var right = P.filter(function (p) { return p.r; }).length, cards = 0, votes = 0;
  try { for (var i = 0; i < localStorage.length; i++) { var k = localStorage.key(i); if (/^tifo\.fan\.\d+$/.test(k)) cards++; else if (/^tifo\.motm\.\d+$/.test(k)) votes++; } } catch (e) {}
  var mine = +ls("tifo.mine") || 0, mineName = ls("tifo.mine.name") || "";
  M.forEach(function (m) { if (!mineName && m.h === mine) mineName = m.hn; if (!mineName && m.a === mine) mineName = m.an; });
  var firstT = M.reduce(function (t, m) { return Math.min(t, m.t || NOW); }, NOW);

  // ------------------------------------------------------------------ drawing
  var cv = D.createElement("canvas"); cv.width = W; cv.height = H; var x = cv.getContext("2d");
  function font(w, px, fam) { return w + " " + px + 'px "' + fam + '"'; }
  function fit(t, w, fam, max, min, width) { for (var px = max; px >= min; px -= 4) { x.font = font(w, px, fam); if (x.measureText(t).width <= width) return t; } var s = String(t); while (s.length > 2 && x.measureText(s + "…").width > width) s = s.slice(0, -1); return s + "…"; }
  function text(t, px, y, o) {
    o = o || {}; x.direction = o.dir || "rtl"; x.textAlign = o.align || "center"; x.fillStyle = o.color || CHALK;
    var s = o.width ? fit(String(t), o.w || 400, o.fam || "Readex Pro", o.size, o.min || o.size, o.width) : (x.font = font(o.w || 400, o.size, o.fam || "Readex Pro"), String(t));
    x.fillText(s, px, y);
  }
  var KUFI = function (size, extra) { return Object.assign({ w: 800, fam: "Noto Kufi Arabic", size: size, min: Math.round(size * 0.7), width: W - 160 }, extra || {}); };
  function ground(c1, c2) {
    var g = x.createLinearGradient(0, 0, 0, H); g.addColorStop(0, c1); g.addColorStop(1, c2); x.fillStyle = g; x.fillRect(0, 0, W, H);
    x.strokeStyle = "rgba(255,255,255,.07)"; x.lineWidth = 4;   // the pitch under it: halfway line and centre circle
    x.beginPath(); x.moveTo(0, H * 0.62); x.lineTo(W, H * 0.62); x.stroke();
    x.beginPath(); x.arc(W / 2, H * 0.62, 250, 0, 2 * Math.PI); x.stroke();
  }
  function frame(kicker) {   // the story's head and foot: «تيفو ريوايند · 2026-27», the mark and the address
    text("تيفو ريوايند · ⁦" + SEASON.label + "⁩", W / 2, 150, { w: 600, size: 36, color: MINT });   // isolated: «2026-27», not «27-2026»
    var s = 13, gap = 4, x0 = W / 2 - (3 * s + 2 * gap) / 2, y0 = H - 168;
    [CHALK, MINT, "rgba(255,255,255,.45)", CHALK, "rgba(255,255,255,.45)", MINT, MINT, CHALK, CHALK].forEach(function (c, i) { x.fillStyle = c; x.fillRect(x0 + (i % 3) * (s + gap), y0 + Math.floor(i / 3) * (s + gap), s, s); });
    text("tifo.elyoxe.com/rewind", W / 2, H - 90, { size: 30, color: SOFT, dir: "ltr" });
    if (kicker) text(kicker, W / 2, 330, KUFI(64));
  }
  function big(n, y, color) { text(nf(n), W / 2, y, { w: 700, fam: "Barlow Condensed", size: 380, color: color || CHALK, dir: "ltr" }); }
  function bars(rows, y) {   // a label, its bar and its number, the longest first
    rows.forEach(function (c, i) {
      var wbar = Math.max(40, Math.round((c[1] / rows[0][1]) * 700));
      x.fillStyle = i ? FAINT : "rgba(124,240,180,.32)"; x.fillRect(W / 2 + 350 - wbar, y - 46, wbar, 62);
      text(c[0], W / 2 + 330, y, { w: 600, size: 38, min: 28, width: 560, align: "right" });
      text(String(c[1]), W / 2 - 330, y, { w: 700, fam: "Barlow Condensed", size: 48, align: "left", dir: "ltr" });
      y += 96;
    });
  }
  function crest(id) { return new Promise(function (ok) { if (!id) return ok(null); var i = new Image(); i.onload = function () { ok(i); }; i.onerror = function () { ok(null); }; i.src = "/logo/" + id + ".png"; setTimeout(function () { ok(null); }, 6000); }); }
  var rgb = function (c) { c = String(c || "").replace("#", ""); if (c.length === 3) c = c.replace(/./g, "$&$&"); return c.length === 6 ? [parseInt(c.slice(0, 2), 16), parseInt(c.slice(2, 4), 16), parseInt(c.slice(4, 6), 16)] : [11, 130, 70]; };
  var shade = function (c, k) { return "rgb(" + rgb(c).map(function (v) { return Math.round(v * k); }).join(",") + ")"; };
  var vs = function (m) { return m.hn + " ضد " + m.an; };

  // ------------------------------------------------------------------ the stories (each only with its numbers)
  var S = [];
  S.push({ name: "season", draw: function () {
    ground(GREEN, "#06241A"); frame(DONE ? "موسمك مع تيفو" : "موسمك مع تيفو لين الحين");
    if (!M.length) { text("قصتك تبدأ من أول مباراة تفتحها", W / 2, 960, KUFI(56)); return; }
    big(M.length, 860); text(unit(M.length, "مباراة فتحتها", "مباراة فتحتها", "مباريات فتحتها"), W / 2, 980, KUFI(60));
    text("من " + dayAr(firstT) + (DONE ? " لين آخر الموسم" : " لين اليوم"), W / 2, 1070, { size: 40, color: SOFT });
    if (topComps.length) { text("أكثر بطولات تابعتها", W / 2, 1250, { w: 600, size: 38, color: MINT }); bars(topComps, 1360); }
  } });
  if (live.length) S.push({ name: "live", draw: function () {
    ground("#0E4D31", GREEN); frame("تابعتها وهي تنلعب");
    big(live.length, 1000, MINT); text(unit(live.length, "مباراة على المباشر", "مباراة على المباشر", "مباريات على المباشر"), W / 2, 1120, KUFI(60));
    var first = live[0], lastM = live[live.length - 1];
    text("أولها", W / 2, 1290, { size: 36, color: SOFT }); text(vs(first), W / 2, 1360, { w: 600, size: 46, min: 32, width: W - 160 });
    if (lastM !== first) { text("وآخرها", W / 2, 1470, { size: 36, color: SOFT }); text(vs(lastM), W / 2, 1540, { w: 600, size: 46, min: 32, width: W - 160 }); }
  } });
  if (seen) S.push({ name: "goals", draw: function () {
    ground("#0B3B26", "#041A12"); frame("شفتها تدخل بعيونك");
    big(seen, 1000); text(unit(seen, "هدف شفته مباشر", "هدف شفته مباشر", "أهداف شفتها مباشر"), W / 2, 1120, KUFI(60));
    if (mostSeen && seen > mostSeen.g) {
      text("أكثر مباراة", W / 2, 1290, { size: 36, color: SOFT });
      text(vs(mostSeen), W / 2, 1360, { w: 600, size: 46, min: 32, width: W - 160 });
      text("شفت فيها " + count(mostSeen.g, "هدف", "هدفين", "أهداف"), W / 2, 1430, { size: 40, color: MINT });
    }
  } });
  if (mine) S.push({ name: "team", team: 1, draw: function (img, row) {
    var c = U.col ? U.col(mine) : ""; if (!c || c === "#8E8E93") c = GREEN2;
    ground("#0D1F18", "#050D0A");   // night, and the club's colour as a glow behind its crest: any colour reads, none goes muddy
    var p = rgb(c), glow = x.createRadialGradient(W / 2, 570, 40, W / 2, 570, 760);
    glow.addColorStop(0, "rgba(" + p.join(",") + ",.62)"); glow.addColorStop(1, "rgba(" + p.join(",") + ",0)"); x.fillStyle = glow; x.fillRect(0, 0, W, H);
    frame("فريقك");
    if (img) { var k = Math.min(300 / img.naturalWidth, 300 / img.naturalHeight); x.drawImage(img, W / 2 - img.naturalWidth * k / 2, 420, img.naturalWidth * k, img.naturalHeight * k); }
    if (mineName) text(mineName, W / 2, 830, KUFI(72));
    var mt = M.filter(function (m) { return m.h === mine || m.a === mine; }).length;
    if (mt) text("تابعت له " + count(mt, "مباراة", "مباراتين", "مباريات"), W / 2, 920, { size: 42, color: SOFT });
    if (row) {
      text(row.comp + "، مركزه", W / 2, 1100, { size: 42, color: SOFT, width: W - 200, min: 30 });
      text(String(row.rank), W / 2, 1360, { w: 700, fam: "Barlow Condensed", size: 280, dir: "ltr" });
      [["فاز", row.won], ["تعادل", row.drawn], ["خسر", row.lost], ["نقطة", row.pts]].forEach(function (q, i) {
        var px = W / 2 + (1.5 - i) * 220; text(String(q[1]), px, 1560, { w: 700, fam: "Barlow Condensed", size: 96, dir: "ltr", color: i === 3 ? MINT : CHALK }); text(q[0], px, 1620, { size: 34, color: SOFT });
      });
      text("بعد " + count(row.played, "مباراة", "مباراتين", "مباريات") + "، لين " + dayAr(NOW), W / 2, 1700, { size: 30, color: SOFT });
    }
  } });
  if (P.length) S.push({ name: "picks", draw: function () {
    ground("#123F2C", GREEN); frame("توقعاتك");
    big(right, 860, MINT); text(unit(right, "توقع طلع صح", "توقع طلع صح", "توقعات طلعت صح"), W / 2, 980, KUFI(56));
    text("من " + count(P.length, "توقع", "توقعين", "توقعات"), W / 2, 1060, { size: 40, color: SOFT });
    var n = Math.min(P.length, 48), per = 8, sz = 64, g = 22, x0 = W / 2 + (Math.min(n, per) * (sz + g) - g) / 2;
    P.slice(-n).forEach(function (p, i) { var cx = x0 - (i % per) * (sz + g) - sz / 2, cy = 1170 + Math.floor(i / per) * (sz + g) + sz / 2; x.beginPath(); x.arc(cx, cy, sz / 2, 0, 2 * Math.PI); x.fillStyle = p.r ? MINT : FAINT; x.fill(); });
    text("كل دائرة توقع بالترتيب، والخضرا صح", W / 2, 1170 + Math.ceil(n / per) * (sz + g) + 60, { size: 30, color: SOFT });
  } });
  if (cards || votes) S.push({ name: "stand", draw: function () {
    ground("#0E4D31", "#06241A"); frame("في المدرّج");
    var y = 760;
    if (cards) { big(cards, y + 300, MINT); text(unit(cards, "مرة رفعت كرتك في «اصنع التيفو»", "مرة رفعت كرتك في «اصنع التيفو»", "مرات رفعت كرتك في «اصنع التيفو»"), W / 2, y + 400, { w: 600, size: 44, width: W - 160, min: 32 }); y += 560; }
    if (votes) { text(nf(votes), W / 2, y + 160, { w: 700, fam: "Barlow Condensed", size: 200, dir: "ltr" }); text(unit(votes, "صوت لرجل المباراة", "صوت لرجل المباراة", "أصوات لرجل المباراة"), W / 2, y + 240, { w: 600, size: 44 }); }
  } });
  S.push({ name: "end", draw: function () {
    ground(GREEN2, GREEN); frame("");
    text(DONE ? "شكراً على الموسم" : "الموسم ما خلص", W / 2, 860, KUFI(84));
    text(DONE ? "نشوفك الموسم الياي" : "والقصة تكمل مع كل مباراة", W / 2, 980, { w: 600, size: 52, color: MINT });
    text("كل هذا محفوظ على تلفونك بس، بدون حساب", W / 2, 1180, { size: 38, color: SOFT });
  } });

  // ------------------------------------------------------------------ the viewer
  if (!M.length && !P.length && !cards && !votes) {
    root.innerHTML = '<section class="grp"><div class="card lc"><p><b>ما تجمّع شي لين الحين.</b> ريوايند يتجمع على تلفونك من المباريات اللي تفتحها في تيفو: اللي تتابعها مباشر، والأهداف اللي تشوفها تدخل، وتوقعاتك. افتح أي مباراة وارجع هني، وآخر الموسم تطلع لك القصة كاملة.</p></div></section>' +
      U.grp("", U.row({ href: "/", icon: "ball", c: "#0B8246", t: "مباريات اليوم" }));
    return;
  }
  var at = 0, TEAM = null;
  root.innerHTML = '<div class="rw-v" style="max-width:420px;margin:0 auto">' +
    '<div class="rw-bars" style="display:flex;gap:4px;margin:0 0 10px" aria-hidden="true">' + S.map(function () { return '<i style="flex:1;height:4px;border-radius:2px;background:var(--fill2)"></i>'; }).join("") + "</div>" +
    '<div class="th-acts" style="margin:0 0 12px"><button type="button" class="pill" id="rw-prev">السابقة</button><button type="button" class="pill pri" id="rw-share">' + U.icon("share", "", 2) + 'شارك</button><button type="button" class="pill" id="rw-next">التالية</button></div>' +
    '<div id="rw-c" style="border-radius:16px;overflow:hidden;background:' + GREEN + '"></div>' +
    '<p class="note" style="margin-top:14px">اضغط على القصة للي بعدها، وعلى طرفها اليمين للي قبلها. القصص من اللي محفوظ على تلفونك بس، وما توصل لأحد إلا إذا شاركتها.</p></div>';
  var host = D.getElementById("rw-c"); cv.style.cssText = "display:block;width:100%;height:auto;cursor:pointer"; cv.setAttribute("role", "img"); host.appendChild(cv);
  // the team's season: its row in a table of this season, from its league (the team file's primary competition, when the team
  // has a file) or else the competitions of its matches the trail kept, the most followed first
  function team() {
    if (TEAM) return TEAM;
    var tally = {}; M.forEach(function (m) { if ((m.h === mine || m.a === mine) && m.c) { tally[m.c] = tally[m.c] || { c: m.c, cn: m.cn, n: 0 }; tally[m.c].n++; } });
    var cands = Object.keys(tally).map(function (k) { return tally[k]; }).sort(function (a, b) { return b.n - a.n; }), y0 = +SEASON.from.slice(0, 4);
    function tryC(list) {
      if (!list.length) return Promise.resolve(null);
      var c = list[0];
      return fetch("/v1/comp/" + c.c + "/standings.json").then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }).then(function (st) {
        var row = null, y = +((String((st && st.season) || "").match(/\d{4}/) || [0])[0]);   // «2026/2027» or «2026»: never last season's table
        if (st && y >= y0) (st.groups || []).forEach(function (g) { (g.rows || []).forEach(function (r) { if (!row && r.team && +r.team.id === mine) row = r; }); });
        return row && row.played ? Object.assign({ comp: c.cn || "الدوري" }, row) : tryC(list.slice(1));
      });
    }
    var tf = fetch("/v1/team/" + mine + ".json").then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    return (TEAM = Promise.all([crest(mine), tf.then(function (t) {
      if (t && t.primary_comp) {
        var cf = (t.fixtures || []).filter(function (f) { return f.comp === t.primary_comp && f.comp_name_ar; })[0];
        cands = [{ c: t.primary_comp, cn: (tally[t.primary_comp] && tally[t.primary_comp].cn) || (cf && cf.comp_name_ar) }].concat(cands.filter(function (c) { return c.c !== t.primary_comp; }));
      }
      return tryC(cands.slice(0, 3));
    })]));
  }
  var fonts = D.fonts && D.fonts.load ? Promise.all([font(800, 60, "Noto Kufi Arabic"), font(600, 40, "Readex Pro"), font(400, 40, "Readex Pro"), font(700, 200, "Barlow Condensed")].map(function (f) { return D.fonts.load(f, "تيفو 0"); })).catch(function () {}) : Promise.resolve();
  function show(i) {
    at = Math.max(0, Math.min(S.length - 1, i));
    var s = S[at];
    return fonts.then(function () { return s.team ? team() : null; }).then(function (t) {
      x.setTransform(1, 0, 0, 1, 0, 0); s.draw(t && t[0], t && t[1]);
      cv.setAttribute("aria-label", "قصة " + (at + 1) + " من " + S.length);
      [].forEach.call(root.querySelectorAll(".rw-bars i"), function (b, j) { b.style.background = j <= at ? "var(--accent)" : "var(--fill2)"; });
      D.getElementById("rw-prev").disabled = at === 0; D.getElementById("rw-next").disabled = at === S.length - 1;
    });
  }
  root.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest("#rw-prev, #rw-next, #rw-share, canvas"); if (!t) return;
    if (t.id === "rw-prev") return show(at - 1);
    if (t.id === "rw-next") return show(at + 1);
    if (t.tagName === "CANVAS") { var r = cv.getBoundingClientRect(); if (e.clientX > r.right - r.width * 0.3) return show(at - 1); return show(at === S.length - 1 ? 0 : at + 1); }   // RTL: the right edge goes back
    cv.toBlob(function (b) {
      if (!b) return;
      var name = "tifo-rewind-" + S[at].name + ".png", f = window.File ? new File([b], name, { type: "image/png" }) : null;
      if (f && navigator.canShare && navigator.canShare({ files: [f] })) { navigator.share({ files: [f], title: "تيفو ريوايند" }).catch(function () {}); return; }
      var a = D.createElement("a"); a.href = URL.createObjectURL(b); a.download = name; B.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
    }, "image/png");
  });
  D.addEventListener("keydown", function (e) { if (e.key === "ArrowLeft") show(at + 1); else if (e.key === "ArrowRight") show(at - 1); });   // RTL: the next story is to the left
  show(0);
})();
