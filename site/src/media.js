/* تيفو: official videos next to the goals and the match (owner 2026-09-30: «أول ما يتوفر فيديو رسمي سواء يوتيوب او سوشال ميديا فيه
   القول ينرفق عدال للهدف اضغط لمشاهدته، ونفس الشي ملخص المباراة للمباريات»).
   Reads /v1/media/<id>.json (news/media.py, every 15 min) in the browser, so a video that came out after the page was built still
   shows: «▶ شاهد» on each goal row that has a clip, «▶ الملخص» with the match's buttons once the highlights are out. A tap opens a
   bottom sheet that plays the video (youtube-nocookie, loaded only then) or links to the post on X. While the match is live or
   ended in the last 5 hours the file is read again every 2 minutes (not while the tab is hidden).
   Portable on purpose: its own few styles, the site's sheet system when there is one (window.TifoSheet) and its own otherwise.
   It finds goal rows by data-goal-key="<minute as shown, 45+2>-<playerId>" (render.js / v3.js; or the v3 rows' data-eid), and
   one «الملخص» only: the page's own button when the match file already has FotMob's highlights (the hero's .cta, #hlbtn's
   .hlbtn: they then open the sheet, their link stays the no-script way), else one of its own in .hero-acts or a
   [data-media-slot] element. /m/<id>/, /live/?id= and /db/match/?id=. */
(function(){
  "use strict";
  var D = document, B = D.body; if (!B || !window.fetch) return;
  var PAGE = B.dataset.page, db = PAGE === "world" && /\/db\/match\/?$/.test(location.pathname), qid = new URLSearchParams(location.search).get("id");
  var MID = PAGE === "match" ? B.dataset.id : db || PAGE === "live" ? qid : null;
  if (!MID || !/^\d+$/.test(MID)) return;
  var M = null, SUM = null, timer = null, busy = false, POLL = 120e3;
  var esc = function(s){ return s == null ? "" : String(s).replace(/[&<>"']/g, function(c){ return { "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]; }); };
  try { var ms = D.getElementById("msum"); if (ms) SUM = JSON.parse(ms.textContent); } catch (e){}

  // ---- styles: the site's tokens when present, readable values otherwise
  var css = ".mdw{display:inline-flex;align-items:center;gap:.3rem;margin-inline-start:.4rem;padding:.15rem .55rem;min-block-size:1.75rem;border:1px solid var(--line,#F6F7F22B);background:var(--surf,#14403A);color:var(--ink,#F6F7F2);font:600 .74rem/1.2 var(--font-text,inherit);cursor:pointer;white-space:nowrap;vertical-align:middle}" +
    ".mdw:hover,.mdw:focus-visible{background:var(--ink,#F6F7F2);color:var(--bg,#0A2620)}.mdw i,.mdh i{font-style:normal;font-size:.8em}" +
    ".mdh-slot{margin-block:.2rem 1rem}.mdh.alone{display:inline-flex;align-items:center;gap:.4rem;padding:.55rem 1.2rem;border:2px solid var(--ink,#F6F7F2);background:var(--ink,#F6F7F2);color:var(--bg,#0A2620);font-weight:800;cursor:pointer}" +
    ":where(.mvsh){position:fixed;inset-inline:0;inset-block-end:0;z-index:60;display:flex}:where(.mvsh)[hidden]{display:none}:where(.mvsh .sh-in){inline-size:100%;max-block-size:92svh;overflow:auto;background:var(--surf-2,#0F3129);color:var(--ink,#F6F7F2);padding:0 1rem 1.2rem}" +
    ":where(.mvsh .sh-h){display:flex;align-items:center;gap:.8rem;padding-block:1rem .8rem}" +
    ".mvsh .mvp{position:relative;inline-size:100%;aspect-ratio:16/9;background:#000}.mvsh .mvp.vert{aspect-ratio:9/16;inline-size:auto;block-size:min(62svh,34rem);max-inline-size:100%;margin-inline:auto}" +
    ".mvsh .mvp iframe{position:absolute;inset:0;inline-size:100%;block-size:100%;border:0}" +
    ".mvsh .mvx{position:relative;display:block;aspect-ratio:16/9;background:#000 center/cover no-repeat;color:#fff;text-decoration:none}.mvsh .mvx b{position:absolute;inset-inline:0;inset-block-end:0;padding:.8rem 1rem;background:linear-gradient(transparent,#000c);font-weight:800}" +
    ".mvsh .mvm{margin:.7rem 0 0;font-size:.85rem;color:var(--tert,#B9C7C0)}.mvsh .mvm a{color:inherit;text-decoration:underline}.mvsh .mvt{margin:.2rem 0 0;font-size:.8rem;color:var(--stone,#A7B6AF)}" +
    ".mvsh .mvl{display:flex;flex-wrap:wrap;gap:.4rem;margin-block-start:.9rem}.mvsh .mvl button{border:1px solid var(--line,#F6F7F22B);background:none;color:var(--ink,#F6F7F2);padding:.35rem .7rem;font:inherit;font-size:.8rem;cursor:pointer}.mvsh .mvl button[aria-pressed=true]{background:var(--ink,#F6F7F2);color:var(--bg,#0A2620)}" +
    "@media (min-width:880px){:where(.mvsh){inset:0;place-items:center;display:grid}:where(.mvsh .sh-in){inline-size:min(48rem,100%);max-block-size:88vh}.mvsh .sh-in{inline-size:min(48rem,100%)}}";
  var st = D.createElement("style"); st.textContent = css; D.head.appendChild(st);

  // ---- Arabic helpers (Western digits)
  function ago(t){ var m = Math.max(1, Math.round((Date.now() - Date.parse(t)) / 6e4)); if (!isFinite(m)) return "";
    var n = function(k, f){ return k === 1 ? f[0] : k === 2 ? f[1] : k + " " + (k <= 10 ? f[2] : f[3]); };
    return "قبل " + (m < 60 ? n(m, ["دقيقة", "دقيقتين", "دقايق", "دقيقة"]) : m < 1440 ? n(Math.round(m / 60), ["ساعة", "ساعتين", "ساعات", "ساعة"]) : n(Math.round(m / 1440), ["يوم", "يومين", "أيام", "يوم"])); }
  function ytid(u){ var m = /(?:v=|\/shorts\/|youtu\.be\/|\/embed\/)([\w-]{11})/.exec(u || ""); return m ? m[1] : null; }

  // ---- state of the match: the page's summary, then every refresh app.js announces (/live/ has neither: its board says live)
  function hot(){ var s = SUM; if (!s) return !!D.querySelector("#lvh .board.live"); if (s.status === "live" || s.status === "ht") return true;
    return s.status === "finished" && Date.now() - Date.parse(s.kickoff_utc || 0) < 5 * 36e5; }
  D.addEventListener("tifo:match", function(e){ var m = e.detail; if (m && String(m.id) === MID){ var was = hot(); SUM = { status:m.status, kickoff_utc:m.kickoff_utc }; if (!was && hot() && !timer) load(); paint(); } });

  // ---- the data
  function load(){ if (busy) return; busy = true;
    fetch("/v1/media/" + MID + ".json", { cache:"no-cache" }).then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; })
      .then(function(d){ busy = false; if (d && String(d.match) === MID){ M = d; paint(); } plan(); }); }
  function plan(){ clearTimeout(timer); timer = null; if (hot()) timer = setTimeout(function(){ timer = null; if (D.hidden) { plan(); return; } load(); }, POLL); }
  D.addEventListener("visibilitychange", function(){ if (!D.hidden && hot() && !timer) load(); });

  // ---- goal rows: data-goal-key («45+2-851198»), else the v3 row's event id («<match>-goal-<minute>-<added>-<player>»)
  function keyOf(el){ if (el.dataset.goalKey) return el.dataset.goalKey; var m = /-(?:goal|penalty_goal|own_goal)-(\d+)-(\d+)-(\d+)(?:-\d+)?$/.exec(el.dataset.eid || "");
    return m ? m[1] + (+m[2] ? "+" + m[2] : "") + "-" + m[3] : null; }
  // the encyclopedia's rows know the minute but not the added time («45-851198» for «45+2-851198»): the one key that fits
  function clips(G, k){ if (!k) return null; if (G[k]) return { k:k, list:G[k] }; var p = /^(\d+)-(\d+)$/.exec(k); if (!p) return null;
    var hits = Object.keys(G).filter(function(x){ return new RegExp("^" + p[1] + "\\+\\d+-" + p[2] + "$").test(x); }); return hits.length === 1 ? { k:hits[0], list:G[hits[0]] } : null; }
  function rows(){ return [].slice.call(D.querySelectorAll("[data-goal-key],ul.ev li.g[data-eid]")); }
  function who(el){ var n = el.querySelector(".who .lat,.who a,.lat,a"); return n ? n.textContent.trim() : ""; }
  // the page's own «الملخص» (FotMob's link, render.js R.hl and the hero's cta): reused, never doubled
  function theirs(){ return [].slice.call(D.querySelectorAll("a.hlbtn,.hero-acts a.cta")).filter(function(a){ return /الملخص/.test(a.textContent); }); }
  function paint(){
    if (!M) return;
    var G = M.goals || {};
    rows().forEach(function(el){ var c = clips(G, keyOf(el)), b = el.querySelector(".mdw");
      if (c && c.list.length){ if (!b){ b = D.createElement("button"); b.type = "button"; b.className = "mdw"; b.dataset.mk = c.k;
          var mn = c.k.split("-")[0], nm = who(el); b.setAttribute("aria-label", "شاهد هدف " + (nm ? nm + " " : "") + "في الدقيقة " + mn); b.innerHTML = '<i aria-hidden="true">▶</i>شاهد';
          (el.querySelector(".who") || el).appendChild(b); } }
      else if (b) b.remove(); });
    var hl = M.highlights || [], own = D.querySelector(".mdh-own"), ex = theirs();
    ex.forEach(function(a){ a.classList.toggle("mdh", !!hl.length); });
    // the search link («شوف الملخص الرسمي» on the channel) steps aside for a real video
    [].slice.call(D.querySelectorAll("p.hlink")).forEach(function(p){ if (!p.querySelector("a.hlbtn")) p.hidden = !!hl.length; });
    if (!hl.length || ex.length){ if (own) own.remove(); return; }
    if (own) return;
    var hb = D.createElement("button"); hb.type = "button"; hb.innerHTML = '<i aria-hidden="true">▶</i> الملخص';
    var slot = D.querySelector("[data-media-slot]"), acts = D.querySelector(".hero-acts");
    if (slot){ hb.className = "mdh mdh-own alone"; slot.appendChild(hb); }
    else if (acts){ hb.className = "cta mdh mdh-own"; acts.insertBefore(hb, acts.firstChild); }
    else { var box = D.createElement("p"); box.className = "mdh-slot"; hb.className = "mdh mdh-own alone"; box.appendChild(hb);
      var at = D.querySelector("#lvhl,.wmh,#events"); if (!at || !at.parentNode) return;
      if (at.id === "lvhl") at.appendChild(box); else at.parentNode.insertBefore(box, at.classList.contains("wmh") ? at.nextSibling : at); }
  }

  // ---- the sheet: the site's when it has one (history entry, scrim, back gesture), a plain one otherwise
  var SH = null, LIST = [], CUR = 0;
  function sheet(){
    if (SH) return SH;
    SH = D.createElement("div"); SH.className = "sheet mvsh"; SH.id = "mvsh"; SH.hidden = true; SH.setAttribute("role", "dialog"); SH.setAttribute("aria-modal", "true"); SH.setAttribute("aria-labelledby", "mvt");
    SH.innerHTML = '<div class="sh-in"><div class="sh-h"><h2 id="mvt"></h2><button type="button" class="x" data-close aria-label="سكّر">سكّر</button></div><div class="mvb"></div></div>';
    B.appendChild(SH);
    // closing stops the video: the player leaves the page with the sheet
    new MutationObserver(function(){ if (SH.hidden) SH.querySelector(".mvb").innerHTML = ""; }).observe(SH, { attributes:true, attributeFilter:["hidden"] });
    if (!window.TifoSheet){ SH.addEventListener("click", function(e){ if (e.target === SH || e.target.closest("[data-close]")) SH.hidden = true; });
      D.addEventListener("keydown", function(e){ if (e.key === "Escape") SH.hidden = true; }); }
    return SH;
  }
  function player(v){
    var id = v.source === "youtube" ? ytid(v.url) : null;
    if (id && v.embed !== false) return '<div class="mvp' + (v.vertical ? " vert" : "") + '"><iframe src="https://www.youtube-nocookie.com/embed/' + id + '?autoplay=1&playsinline=1&rel=0" title="' + esc(v.title || "فيديو") + '" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe></div>';
    return '<a class="mvx" href="' + esc(v.url) + '" target="_blank" rel="noopener"' + (v.image ? ' style="background-image:url(\'' + esc(v.image) + '\')"' : "") + "><b>▶ " + (v.source === "x" ? "شوف المقطع على إكس" : "شوف المقطع على يوتيوب") + "</b></a>";
  }
  function draw(){
    var v = LIST[CUR], body = SH.querySelector(".mvb"); if (!v) return;
    var src = v.source === "x" ? "إكس" : "يوتيوب";
    body.innerHTML = player(v) +
      '<p class="mvm">فيديو رسمي' + (v.channel ? " من " + esc(v.channel) : "") + (v.published ? " · " + ago(v.published) : "") + ' · <a href="' + esc(v.url) + '" target="_blank" rel="noopener">افتحه في ' + src + "</a></p>" +
      (v.title ? '<p class="mvt" dir="auto">' + esc(v.title) + "</p>" : "") +
      (LIST.length > 1 ? '<div class="mvl" role="group" aria-label="نفس اللقطة من قنوات ثانية">' + LIST.map(function(x, i){ return '<button type="button" data-mi="' + i + '" aria-pressed="' + (i === CUR) + '">' + esc(x.channel || (x.source === "x" ? "إكس" : "يوتيوب")) + (x.kind === "goals" ? " · الأهداف" : x.kind === "summary" && LIST.some(function(y){ return y.kind === "goals"; }) ? " · الملخص" : "") + (x.embed === false || x.source === "x" ? " ↗" : "") + "</button>"; }).join("") + "</div>" : "");
  }
  function open(list, title, from){
    if (!list || !list.length) return;
    sheet(); LIST = list; CUR = 0; SH.querySelector("#mvt").textContent = title; draw();
    if (window.TifoSheet) window.TifoSheet.open(SH, from); else { SH.hidden = false; var x = SH.querySelector(".x"); if (x) x.focus(); }
  }
  D.addEventListener("click", function(e){
    var b = e.target.closest(".mdw,.mdh,[data-mi]"); if (!b || !M) return;
    if (b.dataset.mi != null){ CUR = +b.dataset.mi; draw(); return; }
    e.preventDefault();
    if (b.classList.contains("mdh")) open(M.highlights, (M.highlights[0] || {}).kind === "goals" ? "أهداف المباراة" : "ملخص المباراة", b);
    else { var row = b.closest("[data-goal-key],li"), nm = row ? who(row) : "", mn = (b.dataset.mk || "").split("-")[0]; open((M.goals || {})[b.dataset.mk], "هدف" + (nm ? " " + nm : "") + (mn ? " · الدقيقة " + mn : ""), b); }
  });

  // ---- repaint whenever the events or the highlights link are drawn again (app.js re-renders them from fresh data; /live/
  // every 30 s; /db/ once its fetch is back)
  // (in the observer's own microtask: the buttons are back before the next frame, and a page in a background tab gets them too)
  function soon(){ paint(); if (!timer && hot()) plan(); }
  ["events", "hlbtn", "world", "lve", "lvhl", "lvh"].forEach(function(id){ var el = D.getElementById(id); if (el) new MutationObserver(soon).observe(el, { childList:true, subtree:true }); });
  load();
})();
