/* تيفو «كل مباراة لوحة فنية» (owner bold idea 10, 2026-10-06): a poster drawn from a finished match's own data, to save, share
   or print. One composition for every match, from what every match file has (the goals with their minute, scorer and how, the
   cards, the team stats), richer where FotMob gives the minute-by-minute momentum:
   - the ring: the match's minutes clockwise from the top (90, or 120 after extra time), a tick a minute, pushed out for the home
     side and in for the away side by the momentum when the file has it; each goal a spoke in its side's colour at its minute,
     the minute at its tip; the cards on the ring
   - inside: possession as two arcs, the crests, the score large (home on the right, each number drawn on its own so no reading
     order can swap them), the teams' names, the shootout under the score when there was one
   - below: the scorers by side, with how each goal went in when the file says and there is room, then three numbers side by
     side (possession, shots, on target); competition and round, date and city on top; «تيفو» and tifo.elyoxe.com at the foot
   1080×1350 (4:5: the size a phone shares, and it prints on A4), on paper with ink, each side in its club's colour (the site's
   own pairing, U5.pair, darkened where a colour would vanish on paper). Arabic names from the page (U5.pnameT, window.PN), the
   fonts v5 already serves (Noto Kufi Arabic 800, Readex Pro 400-600, Barlow Condensed 700 for the digits). Opened from the
   finished match page's share sheet («بوستر المباراة», data-sheet="sh-poster"); drawn the first time it opens. Light Emirati,
   Western digits. */
(function () {
  "use strict";
  var D = document, B = D.body, V = window.V5 || {}, U = window.U5;
  if (!B || B.dataset.page !== "match" || !V.id || !U || !window.HTMLCanvasElement || !window.fetch) return;
  var W = 1080, H = 1350, MD = null, BLOB = null, JOB = null;
  var PAPER = "#F4F2ED", INK = "#141A17", STONE = "#5F5E57", RED = "#D8343F", AMBER = "#E8A70C";
  var GOAL = /^(goal|penalty_goal|own_goal)$/;

  // ------------------------------------------------------------------ the sheet
  B.insertAdjacentHTML("beforeend", U.sheet("sh-poster", "بوستر المباراة",
    '<canvas id="pst-c" width="' + W + '" height="' + H + '" style="display:block;width:100%;height:auto;max-width:440px;margin:0 auto;border-radius:12px;background:' + PAPER + '" role="img" aria-label="بوستر المباراة"></canvas>' +
    '<div class="th-acts" style="flex-wrap:wrap"><button type="button" class="pill pri" id="pst-share">' + U.icon("share", "", 2) + 'شارك</button><button type="button" class="pill" id="pst-save">نزّل الصورة</button><button type="button" class="pill" id="pst-print">اطبع</button></div>' +
    '<p class="note" id="pst-msg" style="margin-top:14px">لوحة مرسومة من أرقام المباراة نفسها: الحلقة دقايق المباراة، وكل خط هدف في دقيقته.</p>'));
  var cv = D.getElementById("pst-c"), x = cv.getContext("2d");

  // ------------------------------------------------------------------ helpers
  var rgb = function (c) { c = String(c || "").replace("#", ""); if (c.length === 3) c = c.replace(/./g, "$&$&"); return c.length === 6 ? [parseInt(c.slice(0, 2), 16), parseInt(c.slice(2, 4), 16), parseInt(c.slice(4, 6), 16)] : [128, 128, 128]; };
  var lum = function (c) { var p = rgb(c); return (0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]) / 255; };
  var dist = function (a, b) { var p = rgb(a), q = rgb(b); return Math.abs(p[0] - q[0]) + Math.abs(p[1] - q[1]) + Math.abs(p[2] - q[2]); };
  // the site's pair of colours, each dark enough to read on paper: a colour that would vanish takes the club's second, else ink
  function colours(h, a) {
    var p = U.pair(h, a), ok = function (c) { return c && lum(c) < 0.78; };
    var paper = function (c, id) { if (ok(c)) return c; var s = U.col(id, 1); return ok(s) ? s : INK; };
    var hc = paper(p[0], h), ac = paper(p[1], a);
    if (dist(hc, ac) < 90) { var s = U.col(a, 1); ac = ok(s) && dist(hc, s) >= 90 ? s : dist(hc, INK) >= 90 ? INK : "#8F5400"; }
    return [hc, ac];
  }
  var tn = function (t) { return (t && (t.name_ar || t.name)) || ""; };
  // as the match header (U.scorers): the last name of a longer one, with its particle («دي ماريا», «فان دايك»)
  var PART = /^(دي|دا|دو|ديل|ديلا|دلا|فان|فون|دير|لا|لو|لي|بن|ابن|أبو|ابو|آل|إل|ال|سان|سانت|مك|ماك|دوس|داس)$/;
  var short = function (p) { var w = U.pnameT(p).split(" "); if (w.length <= 2) return w.join(" "); var k = w.length - 1; while (k > 1 && PART.test(w[k - 1])) k--; return w.slice(k).join(" "); };
  var minT = function (e) { return e.minute + (e.added ? "+" + e.added : "") + "'"; };
  var LRI = "⁦", PDI = "⁩";   // a minute inside Arabic text stays «30'», not «'30»
  var MON = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
  var dayAr = function (iso) { var m = /^(\d{4})-(\d\d)-(\d\d)/.exec(iso || ""); return m ? +m[3] + " " + MON[+m[2] - 1] + " " + m[1] : ""; };
  function stat(md, key) { var out = null; (md.stats || []).forEach(function (g) { (g.items || []).forEach(function (s) { if (!out && s.key === key && s.home != null && s.away != null) out = s; }); }); return out; }
  function font(w, px, fam) { return w + " " + px + 'px "' + fam + '"'; }
  // the largest size from max down to min at which the text fits; still too long at min, it is cut with «…»
  function fitText(t, w, fam, max, min, width) {
    for (var px = max; px >= min; px -= 2) { x.font = font(w, px, fam); if (x.measureText(t).width <= width) return t; }
    var s = String(t); while (s.length > 2 && x.measureText(s + "…").width > width) s = s.slice(0, -1); return s + "…";
  }
  function text(t, px, y, o) {   // o: {w, fam, size, min, width, color, align, dir, halo}
    o = o || {}; x.direction = o.dir || "rtl"; x.textAlign = o.align || "center"; x.fillStyle = o.color || INK;
    var s = o.width ? fitText(String(t), o.w || 400, o.fam || "Readex Pro", o.size, o.min || o.size, o.width) : (x.font = font(o.w || 400, o.size, o.fam || "Readex Pro"), String(t));
    if (o.halo) { x.strokeStyle = PAPER; x.lineWidth = 7; x.lineJoin = "round"; x.strokeText(s, px, y); }   // a label over the ring's lines stays readable
    x.fillText(s, px, y);
  }
  function crest(id) {
    return new Promise(function (ok) { var i = new Image(); i.onload = function () { ok(i); }; i.onerror = function () { ok(null); }; i.src = "/logo/" + id + ".png"; setTimeout(function () { ok(null); }, 6000); });
  }
  function momentum(md, span) {
    var m = md.momentum; if (!m || m.length < 5) return null;
    var out = [], top = 0;
    m.forEach(function (p, i) {
      var mi = Array.isArray(p) ? +p[0] : p && p.minute != null ? +p.minute : i, v = Array.isArray(p) ? +p[1] : p && p.value != null ? +p.value : +p;
      if (mi >= 0 && mi < span && isFinite(v)) { out[Math.floor(mi)] = v; top = Math.max(top, Math.abs(v)); }
    });
    if (!top) return null;
    var n = []; for (var i = 0; i < span; i++) n[i] = (out[i] || 0) / top;
    return n.map(function (v, i) { return ((n[i - 1] != null ? n[i - 1] : v) + 2 * v + (n[i + 1] != null ? n[i + 1] : v)) / 4; });   // lightly smoothed, a wave not a saw
  }

  // ------------------------------------------------------------------ the drawing
  function draw(md, crests) {
    var hs = md.score.home, as = md.score.away, cols = colours(md.home.id, md.away.id), hc = cols[0], ac = cols[1], ev = md.events || [];
    var et = ev.some(function (e) { return e.type === "half" && /^(AET|EHT|Pen)$/.test(e.detail || ""); }) || ev.some(function (e) { return e.minute > 90 && !e.added && e.type !== "half"; });
    var span = et ? 120 : 90;
    x.setTransform(1, 0, 0, 1, 0, 0); x.textBaseline = "alphabetic"; x.lineCap = "butt";
    x.fillStyle = PAPER; x.fillRect(0, 0, W, H);
    x.strokeStyle = "rgba(20,26,23,.16)"; x.lineWidth = 2; x.strokeRect(36, 36, W - 72, H - 72);

    // top: competition and round; date and city
    text([md.comp_name_ar, md.round_ar].filter(Boolean).join(" · "), W / 2, 110, { w: 600, size: 34, min: 24, width: W - 180 });
    text([dayAr(md.kickoff_uae || md.kickoff_utc), String(U.venueAr(md.venue) || "").replace(/^في /, "")].filter(Boolean).join(" · "), W / 2, 154, { size: 26, min: 20, width: W - 180, color: STONE });

    // the ring: a tick a minute, clockwise from the top
    var cx = W / 2, cy = 580, R = 320, r2 = 214, mom = momentum(md, span);
    var ang = function (m) { return -Math.PI / 2 + (Math.min(m, span + 5) / span) * 2 * Math.PI; };
    var at = function (a, r) { return [cx + Math.cos(a) * r, cy + Math.sin(a) * r]; };
    var line = function (a, r1, r2_, c, w) { var p = at(a, r1), q = at(a, r2_); x.strokeStyle = c; x.lineWidth = w; x.beginPath(); x.moveTo(p[0], p[1]); x.lineTo(q[0], q[1]); x.stroke(); };
    // the momentum, when the file has it: a wave around the ring, out for the home side's pressure and in for the away side's
    if (mom) {
      var wave = function (sign, c) {
        x.beginPath();
        for (var i = 0; i <= span; i++) { var v = Math.max(0, sign * (mom[Math.min(i, span - 1)] || 0)), p = at(ang(i), R + sign * (12 + v * 52)); if (i) x.lineTo(p[0], p[1]); else x.moveTo(p[0], p[1]); }
        for (var j = span; j >= 0; j--) { var q = at(ang(j), R + sign * 12); x.lineTo(q[0], q[1]); }
        x.closePath(); x.fillStyle = c; x.globalAlpha = 0.24; x.fill(); x.globalAlpha = 1;
      };
      wave(1, hc); wave(-1, ac);
    }
    for (var m = 0; m < span; m++) line(ang(m + 0.5), R - 10, R + 10, "rgba(20,26,23,.28)", 3);
    var marks = et ? [0, 45, 90, 105] : [0, 45];
    marks.forEach(function (mk) { line(ang(mk), R - 24, R + 24, INK, 3); });
    // possession: two arcs inside, home from the top clockwise
    var pos = stat(md, "BallPossesion"), hp = pos && +pos.home, ap = pos && +pos.away;
    if (hp > 0 && ap > 0) {
      var split = -Math.PI / 2 + (hp / (hp + ap)) * 2 * Math.PI;
      x.lineWidth = 14;
      x.strokeStyle = hc; x.beginPath(); x.arc(cx, cy, r2, -Math.PI / 2, split); x.stroke();
      x.strokeStyle = ac; x.beginPath(); x.arc(cx, cy, r2, split, Math.PI * 1.5); x.stroke();
    }
    // the cards, on the ring
    ev.forEach(function (e) {
      if (!/^(yellow|red|second_yellow)$/.test(e.type)) return;
      var a = ang(e.minute + (e.added ? Math.min(e.added, 9) / 10 : 0.5)), p = at(a, R);
      x.save(); x.translate(p[0], p[1]); x.rotate(a + Math.PI / 2); x.fillStyle = e.type === "yellow" ? AMBER : RED; x.fillRect(-6, -9, 12, 18); x.restore();
    });
    // the goals: a spoke from the possession ring out past the minute ring, a dot and the minute at its tip
    var goals = ev.filter(function (e) { return GOAL.test(e.type); });
    goals.forEach(function (e) {
      var a = ang(e.minute + (e.added ? Math.min(e.added, 9) / 10 : 0)), c = e.team === "away" ? ac : hc, tip = at(a, R + 26);
      x.lineCap = "round"; line(a, r2 + 14, R + 26, c, 7); x.lineCap = "butt";
      x.fillStyle = c; x.beginPath(); x.arc(tip[0], tip[1], 11, 0, 2 * Math.PI); x.fill();
      var lp = at(a, R + 62); text(minT(e), lp[0], lp[1] + 10, { w: 700, fam: "Barlow Condensed", size: 30, dir: "ltr", halo: 1 });
    });
    marks.forEach(function (mk) { var p = at(ang(mk), R - 50); text(mk + "'", p[0], p[1] + 8, { w: 700, fam: "Barlow Condensed", size: 24, color: STONE, dir: "ltr", halo: 1 }); });

    // inside: the crests, the score (home on the right), the names
    [[crests[0], cx + 104], [crests[1], cx - 104]].forEach(function (c) {
      if (!c[0]) return; var s = 76, k = Math.min(s / c[0].naturalWidth, s / c[0].naturalHeight), w = c[0].naturalWidth * k, h = c[0].naturalHeight * k;
      x.drawImage(c[0], c[1] - w / 2, cy - 118 - h / 2, w, h);
    });
    text(String(hs), cx + 98, cy + 46, { w: 700, fam: "Barlow Condensed", size: 168, dir: "ltr" });
    text(String(as), cx - 98, cy + 46, { w: 700, fam: "Barlow Condensed", size: 168, dir: "ltr" });
    x.fillStyle = INK; x.fillRect(cx - 15, cy - 18, 30, 9);
    var pen = md.penalties && md.penalties.home != null && md.penalties.away != null ? md.penalties : null;
    text(tn(md.home), cx + 104, cy + 98, { w: 800, fam: "Noto Kufi Arabic", size: 30, min: 18, width: 150, color: hc });
    text(tn(md.away), cx - 104, cy + 98, { w: 800, fam: "Noto Kufi Arabic", size: 30, min: 18, width: 150, color: ac });
    if (pen) text("الترجيح " + LRI + pen.away + " - " + pen.home + PDI, cx, cy + 148, { w: 600, size: 22, color: STONE });   // the away score first in LTR, so the home one reads on the right

    // below: the scorers by side, a line a scorer with all his minutes (in the order he first scored), and how the goal went in
    // under a one-goal line when there is room for it
    var y0 = 1036, LH = 38, HOWH = 28, ROOM = 4 * LH;
    ["home", "away"].forEach(function (side) {
      var by = {}, gs = [], px = side === "home" ? W * 0.73 : W * 0.27, c = side === "home" ? hc : ac;
      goals.forEach(function (e) {
        if ((e.team === "away" ? "away" : "home") !== side || !e.player) return;
        var k = e.player.id != null ? e.player.id + (e.type === "own_goal" ? "og" : "") : e.player.name;
        if (!by[k]) gs.push(by[k] = { p: e.player, ev: [] }); by[k].ev.push(e);
      });
      var more = gs.length > 4 ? gs.length - 3 : 0, shown = more ? gs.slice(0, 3) : gs;
      var how = function (g) { var e = g.ev[0]; return g.ev.length > 1 || e.type === "penalty_goal" || e.type === "own_goal" ? "" : (e.how && e.how.ar) || ""; };
      var withHow = shown.length * LH + shown.filter(how).length * HOWH <= ROOM, y = y0;
      shown.forEach(function (g) {
        var mins = g.ev.map(function (e) { return LRI + minT(e) + PDI + (e.type === "penalty_goal" ? " (ج)" : e.type === "own_goal" ? " (ع)" : ""); }).join("، ");
        text(short(g.p) + " " + mins, px, y, { w: 600, size: 26, min: 18, width: 410, color: c });
        y += LH;
        if (withHow && how(g)) { text(how(g), px, y - 12, { size: 20, min: 16, width: 410, color: STONE }); y += HOWH; }
      });
      if (more) text("و" + more + " غيرهم", px, y, { size: 22, color: STONE });
    });
    if (!goals.length) text("ما في أهداف", W / 2, y0, { w: 600, size: 26, color: STONE });

    // three numbers, side by side, home's on the right of each
    var rows = [["الاستحواذ", stat(md, "BallPossesion"), "%"], ["التسديدات", stat(md, "total_shots"), ""], ["على المرمى", stat(md, "ShotsOnTarget"), ""]].filter(function (r) { return r[1]; });
    rows.forEach(function (r, i) {
      var px = W / 2 + ((rows.length - 1) / 2 - i) * 300;
      text(r[0], px, 1206, { size: 22, color: STONE });
      text(r[1].home + r[2], px + 52, 1252, { w: 700, fam: "Barlow Condensed", size: 42, color: hc, dir: "ltr" });
      text("·", px, 1252, { w: 700, fam: "Barlow Condensed", size: 42, color: STONE, dir: "ltr" });
      text(r[1].away + r[2], px - 52, 1252, { w: 700, fam: "Barlow Condensed", size: 42, color: ac, dir: "ltr" });
    });

    // the mark
    text("تيفو", W - 72, H - 58, { w: 800, fam: "Noto Kufi Arabic", size: 28, align: "right" });
    text("tifo.elyoxe.com", 72, H - 58, { w: 400, size: 22, color: STONE, align: "left", dir: "ltr" });
  }

  // ------------------------------------------------------------------ open, save, share, print
  function render() {
    if (JOB) return JOB;
    var msg = D.getElementById("pst-msg");
    JOB = fetch("/v1/match/" + V.id + ".json").then(function (r) { return r.ok ? r.json() : null; }).then(function (md) {
      if (!md || !/^(finished|awarded)$/.test(md.status) || !md.score || md.score.home == null) throw new Error("no final score");
      // the ring says where every goal went in: drawn only when the file has every goal of the score, side by side (the build
      // offers the poster on the same test; the file can change after it)
      var n = { home: 0, away: 0 }; (md.events || []).forEach(function (e) { if (GOAL.test(e.type)) n[e.team === "away" ? "away" : "home"]++; });
      if (n.home !== +md.score.home || n.away !== +md.score.away) throw new Error("goals missing");
      MD = md;
      var fonts = D.fonts && D.fonts.load ? Promise.all([font(800, 30, "Noto Kufi Arabic"), font(600, 30, "Readex Pro"), font(400, 30, "Readex Pro"), font(700, 40, "Barlow Condensed")].map(function (f) { return D.fonts.load(f, "تيفو 0"); })).catch(function () {}) : null;
      return Promise.all([crest(md.home.id), crest(md.away.id), fonts]);
    }).then(function (r) {
      draw(MD, r);
      return new Promise(function (ok) { cv.toBlob(function (b) { BLOB = b; ok(); }, "image/png"); });
    }).catch(function (err) { JOB = null; if (msg) msg.textContent = err && err.message === "goals missing" ? "تفاصيل أهداف هالمباراة ناقصة عندنا، فما نرسم لها بوستر لين تكتمل." : "ما قدرنا نرسم البوستر الحين، جرّب بعد شوي."; });
    return JOB;
  }
  var fname = function () { return "tifo-" + V.id + ".png"; };
  function save() { var a = D.createElement("a"); a.href = URL.createObjectURL(BLOB); a.download = fname(); B.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 4000); }
  D.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest('[data-sheet="sh-poster"], #pst-save, #pst-share, #pst-print'); if (!t) return;
    if (t.dataset.sheet) { render(); return; }
    render().then(function () {
      if (!BLOB) return;
      if (t.id === "pst-save") return save();
      if (t.id === "pst-share") {
        var f = window.File ? new File([BLOB], fname(), { type: "image/png" }) : null;
        if (f && navigator.canShare && navigator.canShare({ files: [f] })) return navigator.share({ files: [f], title: tn(MD.home) + " " + MD.score.home + " - " + MD.score.away + " " + tn(MD.away) }).catch(function () {});
        return save();
      }
      var w = window.open("", "_blank"); if (!w) return save();
      w.document.write('<!doctype html><html lang="ar" dir="rtl"><title>' + U.esc(tn(MD.home) + " - " + tn(MD.away)) + '</title><style>@page{size:A4 portrait;margin:12mm}html,body{margin:0}img{display:block;width:100%;height:auto}</style><img src="' + cv.toDataURL("image/png") + '" onload="setTimeout(function(){print()},250)"></html>');
      w.document.close();
    });
  });
})();
