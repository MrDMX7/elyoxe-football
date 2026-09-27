/* تيفو client: refreshes the prerendered blocks from /v1 JSON, polls live data every 20 s while something is live,
   and keeps «فريقي» (my team) in localStorage. The page type and ids come from <body data-page data-id data-comp>. */
(function(){
  "use strict";
  var R = window.TR, B = document.body, PAGE = B.dataset.page, ID = B.dataset.id, V = "/v1/";
  var $ = function(s){ return document.querySelector(s); };
  function get(p){ return fetch(V + p, { cache:"no-cache" }).then(function(r){ if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function mine(){ try { return +localStorage.getItem("tifo.mine") || null; } catch (e){ return null; } }
  function setMine(id, name){ try { if (id) { localStorage.setItem("tifo.mine", id); localStorage.setItem("tifo.mine.name", name || ""); } else { localStorage.removeItem("tifo.mine"); } } catch (e){} }
  function uaeToday(off){ var d = new Date(Date.now() + 4 * 3600e3 + (off || 0) * 864e5); return d.toISOString().slice(0, 10); }
  function set(sel, html){ var el = $(sel); if (el) el.innerHTML = html; }
  function stamp(g){ var el = $("#updated"); if (el && g) el.textContent = "آخر تحديث " + new Date(g).toLocaleTimeString("ar-AE-u-nu-latn", { hour:"2-digit", minute:"2-digit", timeZone:"Asia/Dubai" }); }
  function tabs(root){ (root || document).querySelectorAll(".tabs[data-tabs]").forEach(function(t){ t.addEventListener("click", function(e){ var b = e.target.closest("button[data-t]"); if (!b) return; t.querySelectorAll("button").forEach(function(x){ x.setAttribute("aria-selected", x === b ? "true" : "false"); }); document.querySelectorAll("[data-pane]").forEach(function(p){ if (p.dataset.group === t.dataset.tabs) p.hidden = p.dataset.pane !== b.dataset.t; }); try { history.replaceState(null, "", "#" + b.dataset.t); } catch (e){} }); var h = location.hash.slice(1), b = h && t.querySelector('button[data-t="' + h + '"]'); if (b) b.click(); }); }
  var timer = null; function poll(fn, ms){ clearTimeout(timer); timer = setTimeout(function(){ if (document.hidden){ poll(fn, ms); return; } fn(); }, ms); }
  document.addEventListener("visibilitychange", function(){ if (!document.hidden && timer){ clearTimeout(timer); run(); } });

  var INDEX = null;
  function index(){ return INDEX ? Promise.resolve(INDEX) : get("index.json").then(function(x){ INDEX = x; return x; }); }

  // ---- home: day list + live polling + my team
  var dayOff = 0;
  function home(){
    return Promise.all([index(), get("day/" + uaeToday(dayOff).replace(/-/g, "") + ".json").catch(function(){ return { matches:[] }; }), get("live.json").catch(function(){ return { matches:[] }; })]).then(function(r){
      var idx = r[0], day = r[1], live = r[2], by = {}; (live.matches || []).forEach(function(m){ by[m.id] = m; });
      var ms = (day.matches || []).map(function(m){ return by[m.id] || m; });
      set("#daytitle", R.dayNav(uaeToday(dayOff), uaeToday(0)));
      set("#day", R.dayList(ms, idx, { mine:mine(), empty:"ما في مباريات في هاليوم." }));
      var lv = (live.matches || []); set("#livecount", lv.length ? '<i class="cardflip"></i>' + lv.length + " مباراة مباشرة الحين" : "");
      if (dayOff === 0) stand(R.featured(ms));
      stamp(live.generated || day.generated);
      myCard(idx); countdown();
      poll(home, lv.length || ms.some(function(m){ var t = Date.parse(m.kickoff_utc); return m.status === "scheduled" && t - Date.now() < 15 * 60e3 && t > Date.now() - 3 * 3600e3; }) ? 20e3 : 120e3);
    });
  }
  var ST = null;
  function stand(m){
    var box = $("#stand"); if (!box || !m || !window.TifoStand) return;
    set("#standcap", R.standCap(m)); var k = $("#standkick"); if (k) k.textContent = R.isLive(m) ? "مباشر الحين" : m.status === "finished" ? "انتهت" : "مباراة اليوم";
    if (!ST) ST = window.TifoStand.mount(box.querySelector("canvas"));
    ST.set(m);
  }
  function myCard(idx){
    var el = $("#mine"); if (!el) return; var id = mine();
    if (!id){ el.innerHTML = '<div class="mine-card"><div class="h">اختار فريقك</div><p class="small" style="margin:0">افتح صفحة ناديك واضغط «هذا فريقي»، ومبارياته تطلع لك أول شي هنا.</p></div>'; return; }
    get("team/" + id + ".json").then(function(t){
      var f = R.teamFixtures(t), n = f.next[0], p = f.past[0];
      el.innerHTML = '<div class="mine-card"><a class="h" href="/t/' + t.id + '/">' + R.logo(t) + " " + R.tname(t) + " <small>فريقي</small></a>" + (n ? '<div class="lbl">المباراة الياية</div>' + R.matchRow(n, { date:true }) : "") + (p ? '<div class="lbl">آخر نتيجة</div>' + R.matchRow(p, { date:true }) : "") + "</div>";
    }).catch(function(){});
  }

  // ---- competition: standings (live), fixtures, leaders
  function comp(){
    var cid = +B.dataset.comp;
    return Promise.all([get("comp/" + cid + "/standings.json").catch(function(){ return null; }), get("comp/" + cid + "/fixtures.json").catch(function(){ return null; }), get("comp/" + cid + "/stats.json").catch(function(){ return null; }), get("live.json").catch(function(){ return { matches:[] }; })]).then(function(r){
      var st = r[0], fx = r[1], stats = r[2], live = (r[3].matches || []).filter(function(m){ return m.comp === cid; });
      if (st){ var lt = R.liveTable(st, live); set("#table", (lt.is_live ? '<p class="note"><i class="cardflip"></i>الترتيب اللحظي: لو انتهت المباريات الحين</p>' : "") + R.standings(lt, { mine:mine() })); }
      if (fx){ var by = {}; live.forEach(function(m){ by[m.id] = m; }); fx.matches = fx.matches.map(function(m){ return by[m.id] || m; }); roundsUI(fx); }
      if (stats){ set("#goals", R.leaders(stats, "goals")); set("#assists", R.leaders(stats, "assists")); }
      if (st && fx) whatif(st, fx);
      stamp((fx && fx.generated) || (st && st.generated));
      poll(comp, live.length ? 20e3 : 300e3);
    });
  }
  // «شو لو؟» (feature 11) and final day (118): pick 1/X/2 for the coming rounds, the table re-sorts
  var WI = { picks:{}, round:null, st:null, fx:null };
  function whatif(st, fx){
    var box = $("#whatif"); if (!box) return; WI.st = st; WI.fx = fx;
    var rounds = box.dataset.rounds.split(","), rr = R.rounds(fx); if (!WI.round || rounds.indexOf(WI.round) < 0) WI.round = rounds[0];
    set("#wi-r", rounds.map(function(k){ return '<button type="button" data-r="' + R.esc(k) + '"' + (k === WI.round ? ' aria-pressed="true"' : "") + ">" + R.roundLabel(k) + "</button>"; }).join(""));
    var ms = (rr.by[WI.round] || []).filter(function(m){ return m.status === "scheduled"; });
    set("#wi-m", ms.map(function(m){ var p = WI.picks[m.id]; var b = function(v, t){ return '<button type="button" data-m="' + m.id + '" data-v="' + v + '" aria-pressed="' + (p === v) + '">' + t + "</button>"; };
      return '<div class="wi"><span class="t">' + R.logo(m.home, "sm") + " " + R.tname(m.home) + '</span><span class="pick">' + b("H", "فوز") + b("D", "تعادل") + b("A", "فوز") + '</span><span class="t a">' + R.tname(m.away) + " " + R.logo(m.away, "sm") + "</span></div>"; }).join("") || '<p class="empty">ما في مباريات باقية في هالجولة.</p>');
    var rows = JSON.parse(JSON.stringify(st.groups[0].rows)), by = {}; rows.forEach(function(r){ r.was = r.rank; by[r.team.id] = r; });
    (fx.matches || []).forEach(function(m){ var p = WI.picks[m.id]; if (!p) return; var h = by[m.home.id], a = by[m.away.id]; if (!h || !a) return;
      var hs = p === "H" ? 1 : 0, as = p === "A" ? 1 : 0; [[h, hs, as], [a, as, hs]].forEach(function(x){ var r = x[0]; r.played++; r.gf += x[1]; r.ga += x[2]; r.gd = r.gf - r.ga; r.pts += x[1] > x[2] ? 3 : x[1] === x[2] ? 1 : 0; }); });
    rows.sort(function(x, y){ return y.pts - x.pts || y.gd - x.gd || y.gf - x.gf || x.was - y.was; });
    set("#wi-t", '<div class="tblwrap"><table class="st"><thead><tr><th>#</th><th style="text-align:start">الفريق</th><th>لعب</th><th>الفرق</th><th>نقاط</th></tr></thead><tbody>' + rows.map(function(r, i){ var d = r.was - (i + 1); return '<tr class="' + (mine() === r.team.id ? "mine" : "") + '"><td>' + (i + 1) + (d ? '<span class="mv ' + (d > 0 ? "up" : "dn") + '">' + (d > 0 ? "▲" : "▼") + Math.abs(d) + "</span>" : "") + '</td><td class="tm">' + R.logo(r.team, "sm") + " " + R.tname(r.team) + "</td><td>" + r.played + '</td><td><bdi dir="ltr">' + (r.gd > 0 ? "+" : "") + r.gd + '</bdi></td><td class="pts">' + r.pts + "</td></tr>"; }).join("") + "</tbody></table></div>");
    if (!box._wired){ box._wired = true; box.addEventListener("click", function(e){ var b = e.target.closest("button"); if (!b) return; if (b.dataset.r){ WI.round = b.dataset.r; } else if (b.dataset.m){ WI.picks[b.dataset.m] = WI.picks[b.dataset.m] === b.dataset.v ? undefined : b.dataset.v; } whatif(WI.st, WI.fx); }); }
  }
  var curRound = null;
  function roundsUI(fx){
    var rr = R.rounds(fx), el = $("#rounds"); if (!el) return;
    if (curRound == null || rr.order.indexOf(curRound) < 0) curRound = fx.next_round && rr.by[fx.next_round] ? fx.next_round : (function(){ var k = rr.order.filter(function(k){ return rr.by[k].some(function(m){ return m.status !== "finished"; }); })[0]; return k || rr.order[rr.order.length - 1]; })();
    el.innerHTML = '<div class="chips">' + rr.order.map(function(k){ return '<button type="button" data-r="' + R.esc(k) + '"' + (k === curRound ? ' aria-pressed="true"' : "") + ">" + (isNaN(parseFloat(k)) ? R.esc(k) : k) + "</button>"; }).join("") + '</div><div id="roundlist">' + (rr.by[curRound] ? R.roundList(rr.by[curRound], { mine:mine() }) : "") + "</div>";
    var cur = el.querySelector('[aria-pressed="true"]'); if (cur) cur.scrollIntoView({ block:"nearest", inline:"center" });
    el.onclick = function(e){ var b = e.target.closest("button[data-r]"); if (!b) return; curRound = b.dataset.r; roundsUI(fx); };
  }

  // ---- match: detail, live every 20 s
  var MD = null; var sb = $("#storybtn"); if (sb) sb.onclick = function(){ if (MD && window.TifoShare){ sb.disabled = true; window.TifoShare.story(MD).then(function(){ sb.disabled = false; }); } };
  function match(){
    return Promise.all([index(), get("match/" + ID + ".json")]).then(function(r){
      var idx = r[0], md = r[1];
      MD = md; set("#mh", R.matchHead(md)); set("#facts", R.matchFacts(md, idx)); set("#catchup", R.catchup(md)); set("#events", R.events(md)); set("#lineups", R.lineups(md)); set("#stats", R.stats(md)); set("#h2h", R.h2h(md));
      stamp(md.generated);
      var t = Date.parse(md.kickoff_utc), soon = md.status === "scheduled" && t - Date.now() < 90 * 60e3 && t > Date.now() - 3 * 3600e3;
      if (R.isLive(md) || soon) poll(match, 20e3);
    }).catch(function(){ /* no detail yet: keep the prerendered summary */ });
  }

  // ---- team
  function team(){
    var btn = $("#mybtn");
    function paint(){ if (!btn) return; var on = mine() === +ID; btn.textContent = on ? "فريقي ✓" : "هذا فريقي"; btn.classList.toggle("on", on); }
    if (btn){ btn.onclick = function(){ setMine(mine() === +ID ? null : +ID, B.dataset.name); paint(); }; paint(); }
    return get("team/" + ID + ".json").then(function(t){
      var f = R.teamFixtures(t);
      set("#next", f.next.length ? f.next.slice(0, 6).map(function(m){ return R.matchRow(m, { date:true }); }).join("") : '<p class="empty">ما في مباريات ياية منشورة.</p>');
      set("#past", f.past.length ? f.past.slice(0, 10).map(function(m){ return R.matchRow(m, { date:true }); }).join("") : '<p class="empty">ما في نتايج.</p>');
      set("#squad", R.squad(t)); stamp(t.generated);
      var wp = $("#wpbtn"); if (wp && window.TifoShare){ wp.hidden = !f.next.length; wp.onclick = function(){ wp.disabled = true; window.TifoShare.wallpaper({ id:t.id, name:t.name_ar || t.name }, f.next).then(function(){ wp.disabled = false; }); }; }
    }).catch(function(){});
  }

  var pv = $("#prev"), nx = $("#next");
  if (pv && nx && PAGE === "home"){ pv.onclick = function(){ dayOff--; home(); }; nx.onclick = function(){ dayOff++; home(); }; }
  var ics = $("#ics"); if (ics) ics.href = "webcal://" + location.host + "/v1/team/" + ID + ".ics";
  // ---- countdown to the national team's next match (62), on home and /uae/
  var CD = null;
  function countdown(){
    var el = $("#uaecd"); if (!el) return;
    (CD ? Promise.resolve(CD) : get("team/5789.json").then(function(t){ CD = R.teamFixtures(t).next.filter(function(m){ return m.kickoff_utc && !m.time_tbd; })[0] || null; return CD; })).then(function(m){
      if (!m){ el.innerHTML = ""; return; }
      if (R.isLive(m) || Date.parse(m.kickoff_utc) <= Date.now()){ el.innerHTML = '<a class="cd" href="/m/' + m.id + '/"><b>المنتخب يلعب الحين</b><span class="dg">مباشر</span></a>'; return; }
      var tick = function(){ var d = Math.max(0, Date.parse(m.kickoff_utc) - Date.now()), dd = Math.floor(d / 864e5), hh = Math.floor(d / 36e5) % 24, mm = Math.floor(d / 6e4) % 60, ss = Math.floor(d / 1e3) % 60, p2 = function(n){ return n < 10 ? "0" + n : n; };
        var opp = m.home.id === 5789 ? m.away : m.home;
        el.innerHTML = '<a class="cd" href="/m/' + m.id + '/"><span><b>الإمارات ضد ' + R.tname(opp) + '</b><br><span class="small">' + R.esc(R.dayLabel(R.ymd(m.kickoff_uae))) + " " + R.hhmm(m.kickoff_uae) + '</span></span><span class="dg">' + (dd ? dd + " يوم " : "") + p2(hh) + ":" + p2(mm) + ":" + p2(ss) + "</span></a>"; };
      tick(); clearInterval(el._t); el._t = setInterval(tick, 1000);
    }).catch(function(){});
  }

  // ---- majlis TV (22) and matches side by side (131): /tv/ and /tv/?m=id,id
  function tv(){
    var pins = []; try { pins = (new URLSearchParams(location.search).get("m") || "").split(",").filter(Boolean).map(Number); } catch (e){}
    var box = $("#tv"); if (!box) return Promise.resolve();
    var load = pins.length ? Promise.all(pins.map(function(id){ return get("match/" + id + ".json").catch(function(){ return null; }); })) : Promise.all([get("day/" + uaeToday(0).replace(/-/g, "") + ".json").catch(function(){ return { matches:[] }; }), get("live.json").catch(function(){ return { matches:[] }; })]).then(function(r){ var by = {}; (r[1].matches || []).forEach(function(m){ by[m.id] = m; }); return (r[0].matches || []).map(function(m){ return by[m.id] || m; }).sort(function(a, b){ return (R.isLive(b) - R.isLive(a)) || (a.kickoff_utc || "").localeCompare(b.kickoff_utc || ""); }); });
    return load.then(function(ms){
      ms = ms.filter(Boolean); box.className = "tvgrid" + (pins.length ? " pin" : "");
      box.innerHTML = ms.length ? ms.map(function(m){ var live = R.isLive(m), big = m.score ? m.score.home + " - " + m.score.away : R.hhmm(m.kickoff_uae);
        var ev = pins.length ? "<ul>" + (m.events || []).filter(function(e){ return /goal|red|second_yellow/.test(e.type) && e.player; }).reverse().map(function(e){ return "<li>" + e.minute + "' " + (/goal/.test(e.type) ? "⚽ " : "🟥 ") + R.esc(e.player.name) + " (" + R.tname(e.team === "home" ? m.home : m.away) + ")</li>"; }).join("") + "</ul>" : "";
        return '<a class="tvt' + (live ? " live" : "") + '" href="/m/' + m.id + '/"><span class="cmp">' + R.esc(m.comp_name_ar || "") + '</span><span class="row"><span class="tn">' + R.logo(m.home) + R.tname(m.home) + '</span><span class="big">' + big + '</span><span class="tn a">' + R.logo(m.away) + R.tname(m.away) + '</span></span><span class="st">' + (live ? R.minute(m) + (R.hot(m) ? " حامي" : "") : R.statusText(m)) + "</span>" + ev + "</a>"; }).join("") : '<p class="empty">ما في مباريات اليوم.</p>';
      stamp(new Date().toISOString()); poll(tv, 20e3);
    });
  }
  function tvFull(){ var b = $("#fsbtn"); if (b) b.onclick = function(){ var d = document.documentElement; if (!document.fullscreenElement && d.requestFullscreen) d.requestFullscreen(); else if (document.exitFullscreen) document.exitFullscreen(); }; }

  // ---- Tifo studio (152)
  function studio(){
    var sel = $("#sclub"), txt = $("#stext"), cv = $("#sprev"), btn = $("#sdl"); if (!sel || !window.TifoShare) return Promise.resolve();
    var draw = function(){ window.TifoShare.banner(+sel.value, txt.value.trim()).then(function(c){ var x = cv.getContext("2d"); cv.width = 1500; cv.height = 500; x.drawImage(c, 0, 0, 1500, 500); cv._full = c; }); };
    var t = null; sel.onchange = draw; txt.oninput = function(){ clearTimeout(t); t = setTimeout(draw, 250); };
    btn.onclick = function(){ if (cv._full) window.TifoShare.out(cv._full, "tifo-banner.png"); };
    draw(); return Promise.resolve();
  }

  // ---- no-spoiler mode (41): scores blurred until tapped
  var sp = $("#spoil");
  function spoilSet(on){ document.body.classList.toggle("nospoil", on); if (sp) sp.setAttribute("aria-pressed", on); try { localStorage.setItem("tifo.nospoil", on ? "1" : ""); } catch (e){} }
  try { spoilSet(localStorage.getItem("tifo.nospoil") === "1"); } catch (e){}
  if (sp) sp.onclick = function(){ spoilSet(!document.body.classList.contains("nospoil")); };
  document.addEventListener("click", function(e){ if (!document.body.classList.contains("nospoil")) return; var t = e.target.closest(".chip,.board .dg"); if (t && !t.classList.contains("shown")){ e.preventDefault(); t.classList.add("shown"); } }, true);

  function run(){ var f = { home:home, comp:comp, match:match, team:team, tv:tv, studio:studio }[PAGE]; if (f) f().catch(function(){}); if (PAGE === "team" && ID === "5789") countdown(); }
  tvFull();
  tabs(); run();
})();
