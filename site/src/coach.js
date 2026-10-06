/* تيفو «مدرّب الدكة» (owner's second list, 3, 2026-10-06): before kickoff the fan sets his XI and formation for one of the two
   teams, and after the match it is set beside the coach's: how many of his eleven started, the two formations, and once the
   whistle went the FotMob ratings of his picks who played against the coach's starters («تشكيلتك أحسن؟»), as an image to share.
   Kept on the phone only (localStorage tifo.coach.<match>: {t, f, p: {slot: player}, at}); it locks at kickoff (an edit after
   it is refused, the page's clock against the match's). The squads: the team's file (/v1/team/<id>.json, a team the build
   marked hc/ac), Arabic names from the page (window.PN). The real lineup and the ratings: the match file, as the page polls it
   (v5's app.js fires tifo:match). On the v5 tokens and the lineup builder's pitch; light Emirati, Western digits. */
(function () {
  "use strict";
  var D = document, B = D.body, U = window.U5, V = window.V5 || {};
  if (!B || B.dataset.page !== "match" || !U || !V.id || !V.ko || !window.fetch) return;
  var MID = V.id, KO = Date.parse(V.ko), K = "tifo.coach." + MID, BOX = null, MD = null, SQ = {}, EDIT = false, SLOT = null;
  var F = { "4-3-3": [1, 4, 3, 3], "4-4-2": [1, 4, 4, 2], "4-2-3-1": [1, 4, 2, 3, 1], "3-5-2": [1, 3, 5, 2], "3-4-3": [1, 3, 4, 3], "5-3-2": [1, 5, 3, 2] };
  var TEAMS = [V.hc ? { id: V.h, n: V.hn, side: "home" } : null, V.ac ? { id: V.a, n: V.an, side: "away" } : null].filter(Boolean);
  var ls = { get: function (k) { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (e) { return null; } }, set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} } };
  var S = ls.get(K), esc = U.esc;
  var locked = function () { return Date.now() >= KO; };
  if (!TEAMS.length || (locked() && !S) || /postponed|cancelled|abandoned/.test(V.status || "")) return;
  var nm = function (id) { var p = (SQ[S && S.t] || {}).by || {}; return (window.PN && window.PN[id]) || (p[id] && p[id].name) || ""; };
  var short = function (n) { var w = String(n || "").trim().split(/\s+/); return w.length < 2 ? w[0] || "" : w[w.length - 1]; };
  var iso = function (s) { return "⁦" + s + "⁩"; };   // a formation in Arabic text stays «4-2-3-1», not «1-3-2-4»
  function slots(f) { var out = [], n = 0; F[f].forEach(function (k, r) { for (var i = 0; i < k; i++) out.push({ r: r, i: i, k: k, n: n++ }); }); return out; }
  function picked() { return S ? Object.keys(S.p || {}).filter(function (k) { return S.p[k]; }).length : 0; }

  // ------------------------------------------------------------------ the squad
  function squad(tid) {
    if (SQ[tid]) return Promise.resolve(SQ[tid]);
    return fetch("/v1/team/" + tid + ".json").then(function (r) { return r.ok ? r.json() : null; }).then(function (t) {
      var list = [], by = {};
      ((t && t.squad) || []).forEach(function (g) { if (g.group === "coach") return; (g.players || []).forEach(function (p) { var q = { id: p.id, name: (window.PN && window.PN[p.id]) || p.name, no: p.number, gk: g.group === "keepers" }; list.push(q); by[p.id] = q; }); });
      return (SQ[tid] = { list: list, by: by });
    });
  }

  // ------------------------------------------------------------------ the real lineup, when the file has it
  function real() {
    if (!MD || !S || !MD.lineups) return null;
    var side = S.t === MD.home.id ? "home" : S.t === MD.away.id ? "away" : null, lu = side && MD.lineups[side];
    if (!lu || !(lu.starters || []).length) return null;
    var st = {}, rt = {}; (lu.starters || []).forEach(function (p) { st[p.id] = 1; if (p.rating != null) rt[p.id] = +p.rating; });
    (lu.subs || []).forEach(function (p) { if (p.rating != null) rt[p.id] = +p.rating; });
    var mine = Object.keys(S.p).map(function (k) { return +S.p[k]; }).filter(Boolean), hit = mine.filter(function (id) { return st[id]; });
    var avg = function (ids) { var r = ids.map(function (id) { return rt[id]; }).filter(function (x) { return x != null; }); return r.length ? { v: r.reduce(function (s, x) { return s + x; }, 0) / r.length, n: r.length } : null; };
    var done = MD.status === "finished" || MD.status === "awarded";
    return { side: side, f: lu.formation || "", starters: (lu.starters || []).map(function (p) { return p.id; }), hit: hit, mine: mine, done: done, me: done ? avg(mine) : null, coach: done ? avg(Object.keys(st).map(Number)) : null, rt: rt };
  }

  // ------------------------------------------------------------------ drawing
  function pitch(f, p, hits, rt) {
    var rows = F[f], col = U.col(S.t);
    return '<div class="pitch" dir="ltr" style="max-width:420px"><i class="ln out"></i><i class="ln half"></i><i class="ln cc"></i><i class="ln box1"></i><i class="ln box2"></i>' + slots(f).map(function (s) {
      var id = p[s.n], y = 92 - s.r * (82 / (rows.length - 1)), x = (s.i + 1) * 100 / (s.k + 1), pl = id && (SQ[S.t] && SQ[S.t].by[id]), hit = hits && hits[id];
      return '<button type="button" class="pp" data-slot="' + s.n + '" style="left:' + x.toFixed(1) + "%;top:" + y.toFixed(1) + '%"' + (EDIT ? "" : " disabled") + ' aria-label="' + (id ? esc(nm(id)) : s.r === 0 ? "اختر الحارس" : "اختر لاعب") + '">' +
        '<span class="sh" style="--pc:' + (id ? (hit === false ? "rgba(255,255,255,.55)" : col) : "rgba(255,255,255,.25)") + ";--pci:" + U.ink(col) + (SLOT === s.n ? ";box-shadow:0 0 0 3px #fff" : "") + '">' + (pl && pl.no != null ? pl.no : id ? "" : "+") + "</span>" +
        (rt && rt[id] != null ? '<span class="rtg">' + rt[id].toFixed(1) + "</span>" : "") + '<span class="nm">' + (id ? esc(short(nm(id))) : "") + "</span></button>";
    }).join("") + "</div>";
  }
  function picker() {
    var sq = SQ[S.t]; if (!sq || SLOT == null) return "";
    var gk = SLOT === 0, where = {}; Object.keys(S.p).forEach(function (k) { if (S.p[k]) where[S.p[k]] = +k; });
    return U.grp(gk ? "اختر الحارس" : "اختر لاعب لهالمركز", (S.p[SLOT] ? U.row({ btn: 1, t: "شيل اللاعب من المركز", cls: "link", attrs: " data-rm" }) : "") +
      sq.list.filter(function (q) { return gk ? q.gk : !q.gk; }).map(function (q) {
        return U.row({ btn: 1, t: '<span class="num" style="color:var(--label2)">' + (q.no != null ? q.no : "") + "</span> " + esc(nm(q.id) || q.name), sub: where[q.id] != null && where[q.id] !== SLOT ? "في تشكيلتك" : "", attrs: ' data-pl="' + q.id + '"' });
      }).join(""), { cls: "mt" });
  }
  function paint() {
    if (!BOX) return;
    var team = S && TEAMS.filter(function (t) { return t.id === S.t; })[0];
    if (!S || !team) {
      BOX.innerHTML = '<div class="gh"><h2>مدرّب الدكة</h2></div><div class="card lc"><p>قبل صافرة البداية سوّ تشكيلتك وخطتك، وبعد المباراة نحطها جنب تشكيلة المدرب الحقيقية: تشكيلتك أحسن؟</p>' +
        '<div class="th-acts" style="flex-wrap:wrap">' + TEAMS.map(function (t) { return '<button type="button" class="pill pri" data-team="' + t.id + '">تشكيلة ' + esc(t.n) + "</button>"; }).join("") + "</div></div>";
      return;
    }
    var R = locked() ? real() : null, hits = null;
    if (R) { hits = {}; R.mine.forEach(function (id) { hits[id] = R.starters.indexOf(id) >= 0; }); }
    var head = '<div class="gh"><h2>مدرّب الدكة: ' + esc(team.n) + '</h2><span class="num">' + S.f + "</span></div>";
    var body = "";
    if (!locked()) {
      body = (EDIT ? U.seg("cf", Object.keys(F).map(function (f) { return [f, f]; }), S.f, { sm: 1 }) : "") + '<div class="card pitchw mt">' + pitch(S.f, S.p, null, null) + '<p class="gf">' + picked() + " من 11" + (EDIT ? " · اضغط مركز واختر لاعب" : "") + "</p></div>" +
        '<div class="th-acts" style="flex-wrap:wrap">' + (EDIT ? '<button type="button" class="pill pri" data-done>تمام</button>' : '<button type="button" class="pill" data-edit>عدّل</button>') + (picked() === 11 ? '<button type="button" class="pill" data-share>شارك تشكيلتي</button>' : "") + '<button type="button" class="pill" data-reset>غيّر الفريق</button></div>' +
        '<p class="note" style="margin-top:10px">تنقفل مع صافرة البداية، وبعدها نقارنها بتشكيلة المدرب.</p>' + (EDIT ? '<div id="co-pick">' + picker() + "</div>" : "");
    } else if (!R) {
      body = '<div class="card pitchw">' + pitch(S.f, S.p, null, null) + '</div><p class="note" style="margin-top:10px">تشكيلتك انقفلت. أول ما تنزل تشكيلة المدرب نحطها جنبها هني.</p>';
    } else {
      var verdict = "";
      if (R.done && R.me && R.coach && R.me.n >= 6) {
        var d = R.me.v - R.coach.v;
        verdict = '<p style="font-size:20px;margin:6px 0"><b>' + (d > 0.05 ? "تشكيلتك أحسن" : d < -0.05 ? "تشكيلة المدرب أحسن" : "تعادل") + "</b></p>" +
          '<p class="gf">متوسط تقييم اختياراتك اللي لعبوا <b class="num">' + R.me.v.toFixed(2) + "</b> (" + R.me.n + " من 11) · أساسيين المدرب <b class=\"num\">" + R.coach.v.toFixed(2) + "</b>، على تقييمات FotMob</p>";
      } else if (R.done) {   // fewer than six of his picks played: no fair verdict, and he is told why
        verdict = '<p class="gf">ما نحكم منو أحسن: ' + (R.me ? R.me.n : 0) + " بس من اختياراتك لعبوا، ونحتاج 6 على الأقل.</p>";
      }
      body = '<div class="card lc" style="text-align:center"><p style="margin:4px 0"><b class="num" style="font-size:34px">' + R.hit.length + "</b> من 11 من تشكيلتك لعبوا أساسيين</p>" +
        '<p class="gf">خطتك ' + S.f + (R.f ? " · خطة المدرب " + esc(R.f) + (R.f === S.f ? " (نفسها)" : "") : "") + "</p>" + verdict + "</div>" +
        '<div class="card pitchw mt">' + pitch(S.f, S.p, hits, R.done ? R.rt : null) + '<p class="gf">الملوّن لعب أساسي، والباهت ما بدأ.</p></div>' +
        '<div class="th-acts"><button type="button" class="pill pri" data-share>شارك المقارنة</button></div>';
    }
    BOX.innerHTML = head + body;
  }

  // ------------------------------------------------------------------ the share image: the two elevens side by side
  function share() {
    var R = locked() ? real() : null, team = TEAMS.filter(function (t) { return t.id === S.t; })[0], W = 1080, H = 1350, c = D.createElement("canvas"); c.width = W; c.height = H; var x = c.getContext("2d");
    var draw = function () {
    x.fillStyle = "#123F2C"; x.fillRect(0, 0, W, H);
    var t = function (s, px, y, o) { o = o || {}; x.direction = o.dir || "rtl"; x.textAlign = o.align || "center"; x.fillStyle = o.color || "#F6F7F2"; x.font = (o.w || 600) + " " + o.size + 'px "' + (o.fam || "Readex Pro") + '"'; x.fillText(s, px, y); };
    t("مدرّب الدكة · " + (team ? team.n : ""), W / 2, 100, { w: 800, size: 50, fam: "Noto Kufi Arabic" });
    t((V.hn || "") + " ضد " + (V.an || ""), W / 2, 160, { size: 32, color: "#C7D5CD" });
    var mine = slots(S.f).map(function (s) { return S.p[s.n]; }).filter(Boolean), col = function (ids, cx, title, hit) {
      t(title, cx, 250, { w: 700, size: 36, color: "#7CF0B4" });
      ids.forEach(function (id, i) { var on = hit ? hit.indexOf(id) >= 0 : true; t(short(nm(id)) || "—", cx, 320 + i * 72, { size: 38, color: on ? "#F6F7F2" : "rgba(246,247,242,.45)" }); });
    };
    col(mine, W * 0.75, "تشكيلتي " + iso(S.f), R ? R.starters : null);
    if (R) col(R.starters, W * 0.25, "تشكيلة المدرب " + iso(R.f || ""), mine);
    else t("قبل صافرة البداية", W * 0.25, 600, { size: 36, color: "#C7D5CD" });
    if (R) t(R.hit.length + " من 11 لعبوا أساسيين" + (R.done && R.me && R.coach && R.me.n >= 6 ? " · " + (R.me.v - R.coach.v > 0.05 ? "تشكيلتي أحسن" : R.me.v - R.coach.v < -0.05 ? "تشكيلة المدرب أحسن" : "تعادل") : ""), W / 2, H - 150, { w: 700, size: 42 });
    t("tifo.elyoxe.com", 60, H - 50, { size: 30, color: "#C7D5CD", align: "left", dir: "ltr" }); t("تيفو", W - 60, H - 48, { w: 800, size: 46, fam: "Noto Kufi Arabic", align: "right" });
    };
    (D.fonts && D.fonts.load ? Promise.all(['800 50px "Noto Kufi Arabic"', '600 38px "Readex Pro"', '700 36px "Readex Pro"'].map(function (q) { return D.fonts.load(q, "تيفو 0"); })).catch(function () {}) : Promise.resolve()).then(function () { draw(); c.toBlob(function (b) {
      if (!b) return; var name = "tifo-coach-" + MID + ".png", fl = window.File ? new File([b], name, { type: "image/png" }) : null;
      if (fl && navigator.canShare && navigator.canShare({ files: [fl] })) { navigator.share({ files: [fl], title: "مدرّب الدكة" }).catch(function () {}); return; }
      var a = D.createElement("a"); a.href = URL.createObjectURL(b); a.download = name; B.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
    }, "image/png"); });
  }

  // ------------------------------------------------------------------ the section and its taps
  function save() { if (!locked()) { S.at = new Date().toISOString(); ls.set(K, S); } }
  function mount() {
    BOX = D.createElement("section"); BOX.className = "grp"; BOX.id = "coach";
    var after = D.getElementById("motm") || D.getElementById("fanmosaic") || D.querySelector("[data-predict]") || (D.getElementById("ev") && D.getElementById("ev").closest("section"));
    var pane = D.querySelector('.pane[data-p="ov"]');
    if (after && after.parentNode) after.parentNode.insertBefore(BOX, after.nextSibling); else if (pane) pane.appendChild(BOX); else return false;
    BOX.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest("button"); if (!b) return;
      if (locked() && !b.hasAttribute("data-share")) { paint(); return; }   // the whistle went: nothing changes any more
      if (b.dataset.team) { var tid = +b.dataset.team; S = { t: tid, f: "4-3-3", p: {} }; EDIT = true; SLOT = 0; squad(tid).then(function () { save(); paint(); }).catch(function () { BOX.innerHTML = '<div class="card">' + U.empty("ما قدرنا نحمّل اللاعبين.") + "</div>"; }); return; }
      if (b.dataset.slot != null && EDIT) { SLOT = +b.dataset.slot; paint(); var pk = D.getElementById("co-pick"); if (pk) pk.scrollIntoView({ block: "nearest" }); return; }
      if (b.dataset.pl) { var pid = +b.dataset.pl; Object.keys(S.p).forEach(function (k) { if (S.p[k] === pid) delete S.p[k]; }); S.p[SLOT] = pid; var next = slots(S.f).filter(function (s) { return !S.p[s.n]; })[0]; SLOT = next ? next.n : null; save(); paint(); return; }
      if (b.hasAttribute("data-rm")) { delete S.p[SLOT]; save(); paint(); return; }
      if (b.dataset.t && b.closest('.seg[data-seg="cf"]')) { var old = slots(S.f), gk = S.p[0], rest = old.filter(function (s) { return s.r > 0; }).map(function (s) { return S.p[s.n]; }).filter(Boolean); S.f = b.dataset.t; S.p = {}; if (gk) S.p[0] = gk; slots(S.f).filter(function (s) { return s.r > 0; }).forEach(function (s, i) { if (rest[i]) S.p[s.n] = rest[i]; }); save(); paint(); return; }
      if (b.hasAttribute("data-done")) { EDIT = false; SLOT = null; paint(); return; }
      if (b.hasAttribute("data-edit")) { EDIT = true; SLOT = slots(S.f).filter(function (s) { return !S.p[s.n]; }).map(function (s) { return s.n; })[0]; if (SLOT == null) SLOT = 0; paint(); return; }
      if (b.hasAttribute("data-reset")) { if (confirm("تمسح تشكيلتك وتختار الفريق من جديد؟")) { S = null; try { localStorage.removeItem(K); } catch (x) {} EDIT = false; SLOT = null; paint(); } return; }
      if (b.hasAttribute("data-share")) share();
    });
    return true;
  }
  if (!mount()) return;
  (S ? squad(S.t) : Promise.resolve()).catch(function () {}).then(paint);
  if (locked()) fetch("/v1/match/" + MID + ".json").then(function (r) { return r.ok ? r.json() : null; }).then(function (md) { if (md) { MD = md; paint(); } }).catch(function () {});
  D.addEventListener("tifo:match", function (e) { var md = e.detail || {}; if (md.lineups || md.status) { MD = md; if (locked()) { EDIT = false; SLOT = null; } paint(); } });
  if (!locked() && KO - Date.now() < 864e5) setTimeout(function () { EDIT = false; SLOT = null; paint(); }, KO - Date.now() + 1000);   // the lock, on a page kept open
})();
