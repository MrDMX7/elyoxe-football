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
  function set(sel, html){ var el = $(sel); if (el){ el.innerHTML = html; R.localize(el); } }
  // ---- country (203, 199): time zone + what comes first; guessed from the browser's time zone, changeable in the header
  function country(){ try { var c = localStorage.getItem("tifo.country"); if (c) return c; } catch (e){} var tz = ""; try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e){} var hit = R.COUNTRIES.filter(function(c){ return c[2] === tz; })[0]; return hit ? hit[0] : "xx"; }
  function applyCountry(){ var c = country(), row = R.COUNTRIES.filter(function(x){ return x[0] === c; })[0]; try { R.TZ = row ? row[2] : Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e){ R.TZ = "Asia/Dubai"; }
    var b = $("#ctry"); if (b) b.textContent = row ? row[1] : "بلدك"; R.localize(document); }
  applyCountry();
  var cb = $("#ctry"); if (cb) cb.onclick = function(){ var box = $("#ctrybox"); if (box){ box.remove(); return; }
    box = document.createElement("div"); box.id = "ctrybox"; box.className = "ctrybox"; var cur = country();
    box.innerHTML = '<p class="small">اختار بلدك: المواعيد تطلع بتوقيته، ومبارياته أول شي.</p><div class="cgrid">' + R.COUNTRIES.map(function(c){ return '<button type="button" data-c="' + c[0] + '"' + (c[0] === cur ? ' aria-pressed="true"' : "") + ">" + c[1] + "</button>"; }).join("") + '<button type="button" data-c="xx"' + (cur === "xx" ? ' aria-pressed="true"' : "") + ">برا الوطن العربي</button></div>";
    box.onclick = function(e){ var t = e.target.closest("button[data-c]"); if (!t) return; try { localStorage.setItem("tifo.country", t.dataset.c); } catch (x){} box.remove(); applyCountry(); if (PAGE === "home") home(); };
    document.body.appendChild(box); };
  // ---- search (167): one small index, loaded on first open; Arabic normalised (أ إ آ ا، ة ه، ى ي) and Latin both matched
  var SIDX = null, sb0 = $("#srch");
  function norm(t){ return String(t || "").toLowerCase().replace(/[أإآ]/g, "ا").replace(/ة/g, "ه").replace(/ى/g, "ي").replace(/[\u064b-\u0652]/g, "").normalize("NFD").replace(/[\u0300-\u036f]/g, ""); }
  if (sb0) sb0.onclick = function(){ var box = $("#srchbox"); if (box){ box.remove(); return; }
    box = document.createElement("div"); box.id = "srchbox"; box.className = "ctrybox"; box.innerHTML = '<input id="sq" placeholder="نادي، لاعب، بطولة…" aria-label="بحث" autocomplete="off"><div id="sr"></div>'; document.body.appendChild(box);
    var q = $("#sq"); q.focus();
    (SIDX ? Promise.resolve(SIDX) : fetch("/assets/search." + sb0.dataset.v + ".json").then(function(r){ return r.json(); }).then(function(x){ SIDX = x.map(function(i){ return i.concat([norm(i[1]), norm(i[2])]); }); return SIDX; })).then(function(){
      var TY = { c:"بطولة", t:"نادي", p:"لاعب", r:"صفحة" };
      q.oninput = function(){ var v = norm(q.value.trim()); if (v.length < 2){ set("#sr", ""); return; }
        var hits = SIDX.filter(function(i){ return i[4].indexOf(v) >= 0 || i[5].indexOf(v) >= 0; }).sort(function(a, b){ var o = { c:0, t:1, r:2, p:3 }; return (a[4].indexOf(v) === 0 || a[5].indexOf(v) === 0 ? 0 : 1) - (b[4].indexOf(v) === 0 || b[5].indexOf(v) === 0 ? 0 : 1) || o[a[0]] - o[b[0]]; }).slice(0, 20);
        set("#sr", hits.length ? "<ul>" + hits.map(function(i){ return '<li><a href="' + i[3] + '"><span>' + R.esc(i[1] || i[2]) + (i[1] && i[2] ? ' <span class="muted small lat">' + R.esc(i[2]) + "</span>" : "") + '</span><span class="muted small">' + TY[i[0]] + "</span></a></li>"; }).join("") + "</ul>" : '<p class="muted small">ما لقينا شي.</p>'); };
    }); };
  document.addEventListener("keydown", function(e){ if (e.key === "Escape"){ ["#srchbox", "#ctrybox"].forEach(function(s){ var b = $(s); if (b) b.remove(); }); } });
  // ---- favourites (179): several clubs and players; the first club stays «فريقي»
  function favs(){ try { return JSON.parse(localStorage.getItem("tifo.favs") || "[]"); } catch (e){ return []; } }
  function setFavs(f){ try { localStorage.setItem("tifo.favs", JSON.stringify(f)); } catch (e){} }
  (function migrate(){ var m = mine(), f = favs(); if (m && !f.some(function(x){ return x.t === "team" && x.id === m; })){ f.unshift({ t:"team", id:m, n:(localStorage.getItem("tifo.mine.name") || "") }); setFavs(f); } })();
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
      if (arabOnly()){ var AT = window.ARABT || {}, ar = {}; R.COUNTRIES.forEach(function(c){ ar[c[0]] = 1; }); var cc = {}; (idx.competitions || []).forEach(function(c){ cc[c.id] = R.compCountry(c); }); ms = ms.filter(function(m){ return ar[cc[m.comp]] || AT[m.home.id] || AT[m.away.id]; }); }
      set("#daytitle", R.dayNav(uaeToday(dayOff), uaeToday(0)));
      var natIds = []; try { natIds = JSON.parse(localStorage.getItem("tifo.natids") || "{}")[country()] || []; } catch (e){}
      set("#day", R.dayList(ms, idx, { mine:mine(), country:country(), natIds:natIds, empty:"ما في مباريات في هاليوم." }));
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
    var el = $("#mine"); if (!el) return; var teams = favs().filter(function(x){ return x.t === "team"; });
    if (!teams.length){ el.innerHTML = '<div class="mine-card"><div class="h">مفضلتي</div><p class="small" style="margin:0">افتح صفحة أي نادي واضغط «هذا فريقي»، وضيف كم فريق تبا، ومبارياتهم تطلع لك أول شي هنا.</p></div>'; return; }
    // tn/{id}.json: next and last match per team, written by the build for every club on the site
    Promise.all(teams.slice(0, 6).map(function(x){ return fetch("/tn/" + x.id + ".json").then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; }); })).then(function(rs){
      var h = rs.map(function(t, i){ if (!t) return ""; return '<div class="favrow"><a class="h" href="/t/' + t.id + '/">' + R.logo(t) + " " + R.tname(t) + (i === 0 ? " <small>فريقي</small>" : "") + "</a>" + (t.next ? R.matchRow(t.next, { date:true }) : "") + (!t.next && t.last ? R.matchRow(t.last, { date:true }) : "") + "</div>"; }).join("");
      el.innerHTML = '<div class="mine-card">' + h + "</div>"; R.localize(el);
    });
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
    var ck = (location.pathname.match(/^\/c\/([^/]+)\//) || [])[1];
    el.innerHTML = (ck && !isNaN(parseFloat(curRound)) ? '<p class="small"><a href="/c/' + ck + "/r/" + R.esc(curRound) + '/">صفحة الجولة ' + R.esc(curRound) + "</a></p>" : "") + '<div class="chips">' + rr.order.map(function(k){ return '<button type="button" data-r="' + R.esc(k) + '"' + (k === curRound ? ' aria-pressed="true"' : "") + ">" + (isNaN(parseFloat(k)) ? R.esc(k) : k) + "</button>"; }).join("") + '</div><div id="roundlist">' + (rr.by[curRound] ? R.roundList(rr.by[curRound], { mine:mine() }) : "") + "</div>";
    var cur = el.querySelector('[aria-pressed="true"]'); if (cur) cur.scrollIntoView({ block:"nearest", inline:"center" });
    el.onclick = function(e){ var b = e.target.closest("button[data-r]"); if (!b) return; curRound = b.dataset.r; roundsUI(fx); };
  }

  // ---- match: detail, live every 20 s
  var MD = null; try { var ms0 = document.getElementById("msum"); if (ms0) MD = JSON.parse(ms0.textContent); } catch (e){}
  // 3D lineup pitch (103): three.js loads only on demand
  var FULL = null, P3 = null, pbtn = $("#p3dbtn");
  if (pbtn) pbtn.onclick = function(){
    var box = $("#p3d"); if (!FULL || !box) return;
    if (P3){ P3.dispose(); P3 = null; box.innerHTML = ""; box.classList.remove("p3d"); pbtn.textContent = "شوفها على ملعب ثلاثي الأبعاد"; return; }
    pbtn.disabled = true; pbtn.textContent = "نجهّز الملعب…";
    import(pbtn.dataset.src).then(function(m){ P3 = m.mount(box, FULL); pbtn.textContent = "سكّر الملعب"; pbtn.disabled = false; box.scrollIntoView({ block:"nearest" }); })
      .catch(function(){ pbtn.textContent = "ما قدرنا نفتح الملعب، جرّب مرة ثانية"; pbtn.disabled = false; });
  };
  var sb = $("#storybtn"); if (sb) sb.onclick = function(){ if (MD && window.TifoShare){ sb.disabled = true; window.TifoShare.story(MD).then(function(){ sb.disabled = false; }); } };
  function match(){
    return Promise.all([index(), get("match/" + ID + ".json")]).then(function(r){
      var idx = r[0], md = r[1];
      MD = md; FULL = md; setTimeout(dist, 0); var pb = $("#p3dbtn"); if (pb) pb.hidden = !(md.lineups && md.lineups.home);
      set("#mh", R.matchHead(md)); set("#facts", R.matchFacts(md, idx)); set("#catchup", R.catchup(md)); set("#events", R.events(md)); set("#lineups", R.lineups(md)); set("#stats", R.stats(md)); set("#h2h", R.h2h(md));
      stamp(md.generated);
      var t = Date.parse(md.kickoff_utc), soon = md.status === "scheduled" && t - Date.now() < 90 * 60e3 && t > Date.now() - 3 * 3600e3;
      if (R.isLive(md) || soon) poll(match, 20e3);
    }).catch(function(){ /* no detail yet: keep the prerendered summary */ });
  }

  // ---- team
  function team(){
    var btn = $("#mybtn");
    function isFav(){ return favs().some(function(x){ return x.t === "team" && x.id === +ID; }); }
    function paint(){ if (!btn) return; var on = isFav(); btn.textContent = on ? (mine() === +ID ? "فريقي ✓" : "في مفضلتي ✓") : (favs().length ? "ضيفه لمفضلتي" : "هذا فريقي"); btn.classList.toggle("on", on); }
    if (btn){ btn.onclick = function(){ var f = favs(); if (isFav()){ f = f.filter(function(x){ return !(x.t === "team" && x.id === +ID); }); if (mine() === +ID){ var nx = f.filter(function(x){ return x.t === "team"; })[0]; setMine(nx ? nx.id : null, nx ? nx.n : ""); } } else { f.push({ t:"team", id:+ID, n:B.dataset.name }); if (!mine()) setMine(+ID, B.dataset.name); } setFavs(f); paint(); }; paint(); }
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

  // distance from your emirate (45): remembered choice, rough driving time at ~90 km/h
  function dist(){ var em = "dubai"; try { em = localStorage.getItem("tifo.emirate") || "dubai"; } catch (e){}
    document.querySelectorAll(".dist").forEach(function(d){ var km = JSON.parse(d.dataset.km || "{}"), sel = d.querySelector("select"); if (!sel) return; sel.value = em;
      var paint = function(){ var k = km[sel.value];
        document.querySelectorAll(".leave[data-kick]").forEach(function(l){ if (k == null){ l.textContent = "—"; return; } var t = Date.parse(l.dataset.kick) - (Math.round(k / 90 * 60) + 45) * 6e4; l.textContent = R.hhmm(new Date(t).toISOString()); }); d.querySelector(".dk").textContent = k != null ? Math.round(k) : "—"; d.querySelector(".dt").textContent = k != null ? "حوالي " + Math.max(5, Math.round(k / 90 * 60 / 5) * 5) + " دقيقة سواقة" : ""; };
      sel.onchange = function(){ try { localStorage.setItem("tifo.emirate", sel.value); } catch (e){} em = sel.value; dist(); }; paint(); }); }
  // copy buttons (thread posts, press sheet)
  document.addEventListener("click", function(e){ var b = e.target.closest("[data-copy],[data-copy-from]"); if (!b) return; var t = b.dataset.copy || ((document.querySelector(b.dataset.copyFrom) || {}).innerText || "");
    (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(function(){ var o = b.textContent; b.textContent = "انسخ ✓"; setTimeout(function(){ b.textContent = o; }, 1500); }, function(){}); });
  // «اسأل تيفو» (76)
  var af = $("#askf"); if (af) af.onsubmit = function(e){ e.preventDefault(); var q = $("#askq").value.trim(); if (q.length < 4) return; set("#aska", '<p class="muted">لحظة…</p>');
    fetch("/api/tifo/ask", { method:"POST", headers:{ "content-type":"application/json" }, body:JSON.stringify({ q:q }) }).then(function(r){ return r.json().then(function(j){ return { ok:r.ok, j:j }; }); })
      .then(function(x){ set("#aska", x.ok ? '<div class="ai"><p>' + R.esc(x.j.answer) + "</p></div>" : '<p class="note">' + R.esc((x.j && (x.j.error || x.j.message)) || "ما قدرنا نجاوب الحين") + "</p>"); })
      .catch(function(){ set("#aska", '<p class="note">ما قدرنا نجاوب الحين، جرّب بعد شوي.</p>'); }); };
  // commentator mode (177): the press sheet full screen, big type, the live score on top, facts cycling every 8 s
  document.addEventListener("click", function(e){ var b = e.target.closest("#commbtn"); if (!b) return; var p = $(".press"); if (!p) return;
    var on = !document.body.classList.contains("comm"); document.body.classList.toggle("comm", on); b.textContent = on ? "سكّر وضع المعلّق" : "وضع المعلّق";
    clearInterval(window._commT); if (!on) return; var lis = p.querySelectorAll("li"), i = 0; lis.forEach(function(l){ l.classList.remove("hot1"); });
    window._commT = setInterval(function(){ lis.forEach(function(l){ l.classList.remove("hot1"); }); if (lis[i]) { lis[i].classList.add("hot1"); lis[i].scrollIntoView({ block:"center", behavior:"smooth" }); } i = (i + 1) % lis.length; }, 8000); });
  // service worker (202)
  if ("serviceWorker" in navigator) try { navigator.serviceWorker.register("/sw.js"); } catch (e){}
  // «بس مباريات العرب» (234)
  function arabOnly(){ try { return localStorage.getItem("tifo.arab") === "1"; } catch (e){ return false; } }
  var ab = $("#arabonly"); if (ab){ ab.setAttribute("aria-pressed", arabOnly()); ab.onclick = function(){ try { localStorage.setItem("tifo.arab", arabOnly() ? "" : "1"); } catch (e){} ab.setAttribute("aria-pressed", arabOnly()); home(); }; }
  // second screen (223): only the scoreboard, the match line and the numbers, big, screen kept awake
  var sb2 = $("#secondbtn"), wl = null;
  if (sb2) sb2.onclick = function(){ var on = !document.body.classList.contains("second"); document.body.classList.toggle("second", on); sb2.textContent = on ? "سكّر الشاشة الثانية" : "الشاشة الثانية";
    if (on && navigator.wakeLock) navigator.wakeLock.request("screen").then(function(l){ wl = l; }).catch(function(){}); else if (wl){ wl.release(); wl = null; } };
  function run(){ var f = { home:home, comp:comp, match:match, team:team, tv:tv, studio:studio }[PAGE]; if (f) f().catch(function(){}); if (PAGE === "team" && ID === "5789") countdown(); }
  tvFull();
  tabs(); run(); dist();
})();
