/* تيفو «الكاميرا الذكية» (owner bold idea 13, experimental, 2026-10-06): point the phone at the TV, and the match's live numbers
   sit over the picture: the score and the minute, the crests, possession, shots and shots on target, the last goal. A capture
   button makes one image of the picture and the numbers together, to share or save. The match is ?m=<id> (from a live match
   page), or picked from the matches live now (/v1/all/live.json). Its data: Tifo's match file (/v1/match/<id>.json), or for a
   match outside Tifo's competitions the on-demand route (/api/tifo/match?id=, the same shape), every 20 s while the page is
   seen. The camera starts on a tap (the browser asks), the back camera first; the picture never leaves the phone unless it is
   shared. Without a camera the numbers still show, on black. One canvas draws the numbers for both the screen and the capture.
   Light Emirati, Western digits. */
(function () {
  "use strict";
  var D = document, U = window.U5, root = D.getElementById("cam");
  if (!root || !U || !window.fetch || !window.HTMLCanvasElement) return;
  var MID = (location.search.match(/[?&]m=([0-9]+)/) || [])[1] || null, MD = null, STREAM = null, FACING = "environment", TIMER = null, CREST = {};
  var esc = U.esc, INK = "#FFFFFF", SOFT = "rgba(255,255,255,.78)", LIVE = "#E5261D";
  root.innerHTML = '<div id="cam-pick"></div>' +
    '<div id="cam-stage" style="position:relative;aspect-ratio:9/16;max-height:78vh;margin:0 auto;background:#0b0f0d;border-radius:16px;overflow:hidden">' +
    '<video id="cam-v" playsinline muted autoplay style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"></video>' +
    '<canvas id="cam-hud" style="position:absolute;inset:0;width:100%;height:100%" role="img" aria-label="أرقام المباراة فوق الصورة"></canvas></div>' +
    '<div class="th-acts" style="flex-wrap:wrap"><button type="button" class="pill pri" id="cam-on">' + U.icon("eye", "", 2) + 'شغّل الكاميرا</button><button type="button" class="pill" id="cam-shot" disabled>صوّر</button><button type="button" class="pill" id="cam-flip" hidden>بدّل الكاميرا</button></div>' +
    '<p class="note" id="cam-msg" style="margin-top:12px">وجّه جوالك على التلفزيون، والأرقام تطلع فوق الصورة وتتحدّث كل 20 ثانية. الصورة ما تطلع من جوالك إلا إذا شاركتها. الميزة تجريبية.</p>';
  var stage = D.getElementById("cam-stage"), video = D.getElementById("cam-v"), hud = D.getElementById("cam-hud"), x = hud.getContext("2d");
  var msg = function (t) { D.getElementById("cam-msg").textContent = t; };

  // ------------------------------------------------------------------ the match
  function stat(md, key) { var o = null; (md.stats || []).forEach(function (g) { (g.items || []).forEach(function (s) { if (!o && s.key === key && s.home != null && s.away != null) o = s; }); }); return o; }
  function load() {
    if (!MID || D.hidden) return;
    fetch("/v1/match/" + MID + ".json", { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : fetch("/api/tifo/match?id=" + MID).then(function (q) { return q.ok ? q.json() : null; }); })
      .then(function (md) { if (md && md.home) { MD = md; [md.home.id, md.away.id].forEach(crest); draw(); } }).catch(function () {});
  }
  function crest(id) { if (!id || CREST[id]) return; var i = new Image(); CREST[id] = i; i.onload = draw; i.src = "/logo/" + id + ".png"; }
  function pick() {
    var box = D.getElementById("cam-pick");
    if (MID) { box.innerHTML = ""; return; }
    fetch("/v1/all/live.json", { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      var rows = ((j && j.matches) || []).filter(function (r) { return (r.status === "live" || r.status === "ht") && /^\d+$/.test(String(r.id)); });
      box.innerHTML = rows.length ? U.grp("اختر المباراة اللي على التلفزيون", rows.slice(0, 30).map(function (r) {
        return '<button type="button" class="row" data-m="' + r.id + '"><span class="rt">' + esc(r.home[1]) + " ضد " + esc(r.away[1]) + '<small class="num">' + esc(r.minute ? r.minute + "'" : "") + "</small></span>" +
          '<span class="rv"><bdi dir="rtl" class="num">' + (+r.home[2] || 0) + " - " + (+r.away[2] || 0) + "</bdi></span></button>";
      }).join("")) : '<section class="grp"><div class="card lc"><p class="empty">ما في مباريات مباشرة الحين. افتح الكاميرا من صفحة أي مباراة وهي تنلعب.</p></div></section>';
    }).catch(function () {});
  }

  // ------------------------------------------------------------------ the numbers, drawn for the screen and the capture alike
  function paint(c, W, H) {
    c.clearRect(0, 0, W, H);
    var s = W / 1080, f = function (w, px, fam) { return w + " " + Math.round(px * s) + 'px "' + (fam || "Readex Pro") + '"'; };
    var txt = function (t, px, y, o) { o = o || {}; c.direction = o.dir || "rtl"; c.textAlign = o.align || "center"; c.fillStyle = o.color || INK; c.font = f(o.w || 600, o.size, o.fam); c.fillText(t, px, y); };
    // the corner: the mark and «تجريبية»
    c.fillStyle = "rgba(0,0,0,.45)"; c.fillRect(W - 300 * s, 36 * s, 264 * s, 64 * s);
    txt("تيفو · تجريبية", W - 168 * s, 80 * s, { size: 32, w: 600 });
    if (!MD) { txt(MID ? "نحمّل المباراة…" : "اختر المباراة", W / 2, H * 0.86, { size: 44 }); return; }
    var md = MD, cols = U.pair(md.home.id, md.away.id), y0 = H - 650 * s;
    var g = c.createLinearGradient(0, y0 - 160 * s, 0, H); g.addColorStop(0, "rgba(0,0,0,0)"); g.addColorStop(0.35, "rgba(0,0,0,.72)"); g.addColorStop(1, "rgba(0,0,0,.88)"); c.fillStyle = g; c.fillRect(0, y0 - 160 * s, W, H - y0 + 160 * s);
    // the minute
    var live = md.status === "live", st = live ? (md.minute != null ? md.minute + "'" : "مباشر") : md.status === "ht" ? "استراحة" : md.status === "finished" ? "انتهت" : "قبل البداية";
    c.fillStyle = live ? LIVE : "rgba(255,255,255,.2)"; var mw = 170 * s; c.fillRect(W / 2 - mw / 2, y0 - 34 * s, mw, 58 * s);
    txt(st, W / 2, y0 + 10 * s, { size: 34, w: 700, dir: live && md.minute != null ? "ltr" : "rtl" });
    // crests, names and the score (home on the right, each number on its own)
    [[md.home, W - 170 * s, cols[0]], [md.away, 170 * s, cols[1]]].forEach(function (t) {
      var im = CREST[t[0].id];
      if (im && im.complete && im.naturalWidth) { var k = Math.min(110 * s / im.naturalWidth, 110 * s / im.naturalHeight); c.drawImage(im, t[1] - im.naturalWidth * k / 2, y0 + 50 * s, im.naturalWidth * k, im.naturalHeight * k); }
      var n = t[0].name_ar || t[0].name || ""; c.font = f(800, 40, "Noto Kufi Arabic"); var px = 40; while (px > 24 && c.measureText(n).width > 300 * s) { px -= 2; c.font = f(800, px, "Noto Kufi Arabic"); }
      c.direction = "rtl"; c.textAlign = "center"; c.fillStyle = INK; c.fillText(n, t[1], y0 + 220 * s);
    });
    if (md.score && md.score.home != null) { txt(String(md.score.home), W / 2 + 110 * s, y0 + 170 * s, { size: 150, w: 700, fam: "Barlow Condensed", dir: "ltr" }); txt(String(md.score.away), W / 2 - 110 * s, y0 + 170 * s, { size: 150, w: 700, fam: "Barlow Condensed", dir: "ltr" }); c.fillStyle = INK; c.fillRect(W / 2 - 18 * s, y0 + 100 * s, 36 * s, 10 * s); }
    // three numbers, with a split bar each (home on the right)
    var rows = [["الاستحواذ", stat(md, "BallPossesion"), "%"], ["التسديدات", stat(md, "total_shots"), ""], ["على المرمى", stat(md, "ShotsOnTarget"), ""]].filter(function (r) { return r[1]; });
    rows.forEach(function (r, i) {
      var y = y0 + 300 * s + i * 80 * s, h = +r[1].home || 0, a = +r[1].away || 0, tot = h + a || 1, bw = 560 * s, bx = W / 2 - bw / 2;
      txt(r[0], W / 2, y, { size: 28, w: 400, color: SOFT });
      txt(h + r[2], W / 2 + bw / 2 + 70 * s, y + 22 * s, { size: 40, w: 700, fam: "Barlow Condensed", dir: "ltr" });
      txt(a + r[2], W / 2 - bw / 2 - 70 * s, y + 22 * s, { size: 40, w: 700, fam: "Barlow Condensed", dir: "ltr" });
      c.fillStyle = cols[1]; c.fillRect(bx, y + 12 * s, bw, 12 * s); c.fillStyle = cols[0]; c.fillRect(bx + bw * (1 - h / tot), y + 12 * s, bw * h / tot, 12 * s);
    });
    // the last goal
    var gl = (md.events || []).filter(function (e) { return /^(goal|penalty_goal|own_goal)$/.test(e.type) && e.player; }).pop();
    // the scorer by his Arabic name where the page has it (a match page's names), else his side's: never a Latin name over Arabic
    var who = gl && ((window.PN && window.PN[gl.player.id]) || ((gl.team === "away" ? md.away : md.home).name_ar || ""));
    if (gl && who) txt("آخر هدف: " + who + " ⁦" + gl.minute + (gl.added ? "+" + gl.added : "") + "'⁩", W / 2, H - 48 * s, { size: 32, w: 600, color: SOFT });
  }
  function draw() {
    var r = stage.getBoundingClientRect(), dpr = Math.min(2, window.devicePixelRatio || 1);
    if (!r.width) return;
    hud.width = Math.round(r.width * dpr); hud.height = Math.round(r.height * dpr);
    paint(x, hud.width, hud.height);
  }

  // ------------------------------------------------------------------ the camera and the capture
  function camera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { msg("متصفحك ما يسمح بالكاميرا هني. الأرقام باقية، وتقدر تصوّر الشاشة."); return; }
    if (STREAM) STREAM.getTracks().forEach(function (t) { t.stop(); });
    navigator.mediaDevices.getUserMedia({ video: { facingMode: FACING, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false }).then(function (s) {
      STREAM = s; video.srcObject = s; video.play().catch(function () {});
      D.getElementById("cam-shot").disabled = false; D.getElementById("cam-flip").hidden = false; D.getElementById("cam-on").hidden = true;
    }).catch(function () { msg("ما قدرنا نشغّل الكاميرا. اسمح للمتصفح يستعمل الكاميرا وجرّب مرة ثانية."); });
  }
  function shot() {
    var W = 1080, H = 1920, cv = D.createElement("canvas"); cv.width = W; cv.height = H; var c = cv.getContext("2d");
    c.fillStyle = "#000"; c.fillRect(0, 0, W, H);
    var vw = video.videoWidth, vh = video.videoHeight;
    if (vw && vh) { var k = Math.max(W / vw, H / vh); c.drawImage(video, (W - vw * k) / 2, (H - vh * k) / 2, vw * k, vh * k); }   // cover, as on the screen
    paint(c, W, H);
    cv.toBlob(function (b) {
      if (!b) return;
      var name = "tifo-cam-" + (MID || "match") + ".png", fl = window.File ? new File([b], name, { type: "image/png" }) : null;
      if (fl && navigator.canShare && navigator.canShare({ files: [fl] })) { navigator.share({ files: [fl], title: "تيفو" }).catch(function () {}); return; }
      var a = D.createElement("a"); a.href = URL.createObjectURL(b); a.download = name; D.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
    }, "image/png");
  }
  root.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest("button"); if (!t) return;
    if (t.dataset.m) { MID = t.dataset.m; history.replaceState(null, "", "?m=" + MID); pick(); load(); return; }
    if (t.id === "cam-on") return camera();
    if (t.id === "cam-shot") return shot();
    if (t.id === "cam-flip") { FACING = FACING === "environment" ? "user" : "environment"; camera(); }
  });
  var fonts = D.fonts && D.fonts.load ? Promise.all(['800 40px "Noto Kufi Arabic"', '600 30px "Readex Pro"', '700 60px "Barlow Condensed"'].map(function (q) { return D.fonts.load(q, "تيفو 0"); })).catch(function () {}) : Promise.resolve();
  fonts.then(draw);
  addEventListener("resize", draw);
  D.addEventListener("visibilitychange", function () { if (!D.hidden) load(); });
  pick(); load(); TIMER = setInterval(load, 20000);
})();
