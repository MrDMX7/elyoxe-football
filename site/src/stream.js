/* تيفو «شوفها مباشر ببلاش» (owner 2026-10-06: «هل في مكان داخل صفحة المباراة نفسها يخلي المتابع يجوفها لايف في حال كانت منقولة
   على منصة مجانية مثل يوتيوب…»): the match's free live streams on official YouTube channels, found by news/streams.py (the rights
   holders, leagues, federations and clubs of news/sources.yaml; live now; the title naming both teams) and published as
   /v1/streams.json. Here: on top of the overview, a 16:9 player that loads YouTube only on a tap (youtube-nocookie), the channel
   and the stream's own title (the commentator is often in it), and the other channels when there are more. A stream whose channel
   turned embedding off opens on YouTube. A national channel often blocks its stream abroad, so the viewer's own country's channel
   comes first (his time zone says which; the channel's `cc` is its country in news/sources.yaml). The file is read every 2
   minutes from 75 minutes before kickoff until 3.5 hours after
   (not while the tab is hidden); a file older than 30 minutes says nothing (its job stopped), and the section goes when its
   streams end unless someone is watching. Light Emirati, Western digits. */
(function () {
  "use strict";
  var D = document, B = D.body, U = window.U5, V = window.V5 || {};
  if (!B || B.dataset.page !== "match" || !U || !V.id || !V.ko || !window.fetch) return;
  var KO = Date.parse(V.ko), MIN = 60e3, BOX = null, LIST = [], CUR = null, PLAYING = false, TIMER = null, esc = U.esc;
  var TZC = { "Asia/Dubai": "ae", "Asia/Riyadh": "sa", "Asia/Qatar": "qa", "Asia/Kuwait": "kw", "Asia/Bahrain": "bh", "Asia/Muscat": "om",
    "Africa/Cairo": "eg", "Africa/Casablanca": "ma", "Africa/El_Aaiun": "ma", "Asia/Amman": "jo", "Asia/Baghdad": "iq", "Africa/Algiers": "dz",
    "Africa/Tunis": "tn", "Africa/Tripoli": "ly", "Asia/Beirut": "lb", "Asia/Damascus": "sy", "Asia/Gaza": "ps", "Asia/Hebron": "ps",
    "Asia/Aden": "ye", "Africa/Khartoum": "sd", "Africa/Nouakchott": "mr" }, MINE = null;
  try { MINE = TZC[Intl.DateTimeFormat().resolvedOptions().timeZone] || null; } catch (e) {}

  function css() {
    if (D.getElementById("fl-css")) return;
    var st = D.createElement("style"); st.id = "fl-css";
    st.textContent =
      "#freelive .flv{padding:0;overflow:hidden}" +
      "#freelive .flp{position:relative;display:block;width:100%;aspect-ratio:16/9;background:#000 center/cover no-repeat;border:0;padding:0;margin:0;cursor:pointer;color:#fff;text-decoration:none;font:inherit}" +
      "#freelive .flp::after{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0) 40%,rgba(0,0,0,.6))}" +
      "#freelive .flp i{position:absolute;left:50%;top:50%;width:64px;height:64px;margin:-32px 0 0 -32px;border-radius:50%;background:rgba(0,0,0,.6);z-index:1}" +
      "#freelive .flp i::before{content:'';position:absolute;left:25px;top:20px;border-style:solid;border-width:12px 0 12px 20px;border-color:transparent transparent transparent #fff}" +
      "#freelive .flp b{position:absolute;top:10px;inset-inline-start:10px;z-index:1;background:#FF3B30;color:#fff;font-size:12px;font-weight:700;padding:3px 8px;border-radius:6px}" +
      "#freelive .flp em{position:absolute;bottom:10px;inset-inline:12px;z-index:1;font-style:normal;font-size:13px;font-weight:600;text-align:start}" +
      "#freelive iframe{display:block;width:100%;aspect-ratio:16/9;border:0;background:#000}" +
      "#freelive button.row{width:100%;background:none;border:0;font:inherit;color:inherit;text-align:start;cursor:pointer}" +
      "#freelive button.row[aria-pressed=true] b{color:var(--accent)}" +
      "#freelive .rt small{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}";
    D.head.appendChild(st);
  }
  function mount() {
    var pane = D.querySelector('.pane[data-p="ov"]'), ww = D.getElementById("wwbox");
    if (!pane) return false;
    BOX = D.createElement("section"); BOX.className = "grp"; BOX.id = "freelive";
    if (ww && ww.parentNode === pane) pane.insertBefore(BOX, ww); else pane.insertBefore(BOX, pane.firstChild);
    css();
    BOX.addEventListener("click", click);
    return true;
  }
  function cur() { for (var i = 0; i < LIST.length; i++) if (LIST[i].id === CUR) return LIST[i]; return LIST[0]; }
  function viewers(s) { return s.watching ? '<span class="num">' + esc(s.watching) + "</span> يتابعون" : ""; }
  function poster(s) {
    var inner = "<b>مباشر</b><i></i><em>" + esc(s.channel) + "</em>", bg = ' style="background-image:url(\'https://i.ytimg.com/vi/' + s.id + '/hqdefault_live.jpg\')"';
    return s.embed !== false ? '<button type="button" class="flp" data-flp' + bg + ' aria-label="شغّل البث المباشر من ' + esc(s.channel) + '">' + inner + "</button>"
      : '<a class="flp" href="' + esc(s.url) + '" target="_blank" rel="noopener"' + bg + ' aria-label="افتح البث المباشر في يوتيوب">' + inner + "</a>";
  }
  function frame(s) {
    return '<iframe src="https://www.youtube-nocookie.com/embed/' + s.id + '?autoplay=1&playsinline=1&rel=0" title="' + esc(s.title || s.channel) + '" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>';
  }
  function draw() {
    var s = cur(); CUR = s.id;
    BOX.innerHTML = '<div class="gh"><h2>شوفها مباشر ببلاش</h2><span class="num" style="font-size:12px">بث رسمي على يوتيوب</span></div>' +
      '<div class="card flv"><div data-fls>' + (PLAYING ? frame(s) : poster(s)) + "</div>" +
      '<div class="row"><span class="rt"><b>' + esc(s.channel) + "</b>" + (LIST.length > 1 ? "" : '<small dir="auto">' + esc(s.title) + "</small>") + "</span>" +
      '<span class="rv"><a href="' + esc(s.url) + '" target="_blank" rel="noopener">يوتيوب</a></span></div></div>' +
      (LIST.length > 1 ? '<div class="card" style="margin-top:8px">' + LIST.map(function (x) {
        return '<button type="button" class="row" data-fli="' + x.id + '" aria-pressed="' + (x.id === s.id) + '"><span class="rt"><b>' + esc(x.channel) + '</b><small dir="auto">' + esc(x.title) + "</small></span>" +
          '<span class="rv">' + viewers(x) + "</span></button>";
      }).join("") + "</div>" : "") +
      '<p class="gf">من القنوات الرسمية بس.' + (LIST.length > 1 ? " بعض القنوات تحجب البث برّا بلدها، فإذا ما اشتغل عندك جرّب قناة ثانية." : " بعض القنوات تحجب البث برّا بلدها.") + "</p>";
  }
  function click(e) {
    var p = e.target.closest("[data-flp]"), r = e.target.closest("[data-fli]");
    if (p) { PLAYING = true; draw(); return; }
    if (r && r.dataset.fli !== CUR) {
      CUR = r.dataset.fli;
      var s = cur(); if (s.embed === false) PLAYING = false;
      draw();
    }
  }
  function show(list) {
    LIST = list.filter(function (s) { return MINE && s.cc === MINE; }).concat(list.filter(function (s) { return !(MINE && s.cc === MINE); }));
    if (!LIST.length) { if (BOX && !PLAYING) { BOX.remove(); BOX = null; CUR = null; } return; }
    if (PLAYING) return;                 /* never pull the player from under someone watching */
    if (!BOX && !mount()) return;
    draw();
  }
  function poll() {
    if (D.hidden) return;
    fetch("/v1/streams.json", { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      var fresh = j && j.matches && Date.now() - Date.parse(j.generated || 0) < 30 * MIN;
      show((fresh && j.matches[String(V.id)] || []).filter(function (s) { return s && /^[\w-]{11}$/.test(s.id || "") && s.channel; }));
    }).catch(function () {});
  }
  function start() {
    var now = Date.now();
    if (now < KO - 75 * MIN) { var w = KO - 75 * MIN - now; if (w < 30 * 60 * MIN) setTimeout(start, w + 1000); return; }   /* a page opened early waits for it */
    if (now > KO + 210 * MIN) return;
    poll();
    if (!TIMER) TIMER = setInterval(function () { if (Date.now() > KO + 210 * MIN) { clearInterval(TIMER); return; } poll(); }, 2 * MIN);
    D.addEventListener("visibilitychange", function () { if (!D.hidden) poll(); });
  }
  start();
})();
