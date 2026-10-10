/* Arab-world pages of تيفو (items 207-211, 263, 279-287, 295-300, 306-312, 318-322, 337): built from the arabs/*,
   national/*, derbies, calendar and guide files (docs/SCHEMA.md). Called by build.cjs with its helpers; every page is
   written only when its file exists and has rows, and every field is shown only when present (no zeros for missing data).
   Returns home-page blocks and search entries for build.cjs to place. */
"use strict";
module.exports = async function(X){
  const { get, pool, write, page, urls, R, S, esc, index, teamsJson, teamPages, playerPages, matchPages, NAMES_AR, fs, path, OUT, CACHE } = X;
  const sec = S.sec, TJ = teamsJson.teams || {}, home = {}, search = [];
  const CN = {}; R.COUNTRIES.forEach(c => { CN[c[0]] = c[1]; });
  const cname = c => c ? esc(c.name_ar || CN[c.iso2] || c.iso2 || "") : "";
  const num = v => `<span class="num">${v}</span>`;
  const f1 = v => v != null ? Number(v).toFixed(1) : "";
  // logos for clubs outside the covered leagues (Arab players abroad): same cache as build.cjs, never hotlinked
  const logos = new Set();
  const tlogo = id => { if (!(+id > 0)) return ""; logos.add(+id); return R.logo({ id }, "sm"); };   /* QA 60: no crest request for id 0 or -1 */
  const tname = (id, ar, en) => esc(ar || (TJ[id] || {}).name_ar || en || (TJ[id] || {}).name || "");
  const tm = (id, ar, en) => { const n = tname(id, ar, en); return teamPages.has(+id) ? `<a class="tl" href="/t/${id}/">${tlogo(id)}<span>${n}</span></a>` : `<span class="tl">${tlogo(id)}<span>${n}</span></span>`; };
  const pn = (id, name) => { const ar = (NAMES_AR[id] || {}).ar, inner = ar ? esc(ar) : `<span class="lat">${esc(name || "")}</span>`; return playerPages.has(String(id)) ? `<a href="/p/${id}/">${inner}</a>` : inner; };
  const mrow = (m, o) => { if (!m.kickoff_uae && m.kickoff_utc) m = Object.assign({}, m, { kickoff_uae:new Date(Date.parse(m.kickoff_utc) + 4 * 3600e3).toISOString().slice(0, 19) + "+04:00" }); (m.home && logos.add(m.home.id)); (m.away && logos.add(m.away.id)); const h = R.matchRow(m, o || { date:true }); return matchPages.has(m.id) ? h : h.replace(/^<a /, "<div ").replace(/<\/a>$/, "</div>").replace(/ href="[^"]*"/, ""); };
  const tbl = (heads, rows, cls) => `<div class="tblwrap"><table class="st${cls ? " " + cls : ""}"><thead><tr>${heads.map((h, i) => `<th${i === 0 ? ' style="text-align:start"' : ""}>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
  const note = t => `<p class="src">${t}</p>`;
  const put = (p, title, desc, h1, lead, body, o) => { if (!body) return false; write(p.slice(1) + "index.html", page(Object.assign({ path:p, page:"ref", title:title + " | تيفو", desc, body:`${o && o.crumbs ? `<p class="crumbs">${o.crumbs}</p>` : ""}<h1>${h1}</h1>${lead ? `<p class="muted">${lead}</p>` : ""}` + body }, o && o.page ? { page:o.page } : {}))); urls.push(p); search.push(["r", h1, "", p]); return true; };
  const hubLink = '<a href="/arabs/">العرب</a>';
  const month = ["يناير","فبراير","مارس","أبريل","مايو","يونيو","يوليو","أغسطس","سبتمبر","أكتوبر","نوفمبر","ديسمبر"];
  const dmy = d => { if (!d) return ""; const [y, m, dd] = d.slice(0, 10).split("-").map(Number); return `<bdi dir="ltr" class="num">${dd}</bdi> ${month[m - 1]} <span class="num">${y}</span>`; };
  const dm = d => { if (!d) return ""; const [, m, dd] = d.slice(0, 10).split("-").map(Number); return `<span class="num">${dd}</span> ${month[m - 1]}`; };
  const cmpName = id => esc(R.compName(index, id) || "");

  const F = {}; const files = ["arabs/abroad", "arabs/week/latest", "arabs/tonight", "arabs/clashes", "arabs/national", "arabs/u21", "arabs/coefficients", "arabs/calendars", "arabs/streaks", "derbies", "archive/index-all", "arabs/continental-history", "arabs/coaches", "arabs/referees", "arabs/friendlies", "arabs/match-of-week", "arabs/golden-boot", "arabs/poty", "arabs/continental-odds", "arabs/nations-h2h", "arabs/happiness", "arabs/twins", "clubs/anniversaries", "calendar/year", "arabs/transitions", "arabs/worldcup", "national/archives", "transfers/latest"];
  await pool(files, 6, async f => { F[f] = await get(f + ".json"); });
  const wk = F["arabs/week/latest"] && F["arabs/week/latest"].path ? await get(F["arabs/week/latest"].path) : null;

  // ---- national teams (211/295, 191): index + one page per Arab national team
  const NAT = F["arabs/national"], H2HM = F["arabs/nations-h2h"], WC = F["arabs/worldcup"];
  const natTeams = NAT && NAT.teams ? NAT.teams.slice().sort((a, b) => (a.arab_rank || 99) - (b.arab_rank || 99)) : [];
  const nat = await pool(natTeams, 4, async t => { const [ar, ff, sq] = await Promise.all([get(`national/${t.team}/archive.json`, 2), get(`national/${t.team}/fifa.json`, 2), get(`national/${t.team}/squad.json`, 2)]); return { ar, ff, sq }; });
  const EN_AR = {}; nat.forEach(n => ((n.ar && n.ar.h2h) || []).forEach(h => { if (h.opponent && h.name_ar) EN_AR[h.opponent] = h.name_ar; }));
  const opp = en => EN_AR[en] ? esc(EN_AR[en]) : `<span class="lat">${esc(en)}</span>`;
  const CMP = { "Friendly":"ودية", "FIFA World Cup":"كأس العالم", "FIFA World Cup qualification":"تصفيات كأس العالم", "African Cup of Nations":"كأس أمم أفريقيا", "African Cup of Nations qualification":"تصفيات كأس أمم أفريقيا", "AFC Asian Cup":"كأس آسيا", "AFC Asian Cup qualification":"تصفيات كأس آسيا", "Arab Cup":"كأس العرب", "Arab Cup qualification":"تصفيات كأس العرب", "Gulf Cup":"كأس الخليج", "FIFA Arab Cup":"كأس العرب", "Confederations Cup":"كأس القارات", "Olympic Games":"الألعاب الأولمبية", "West Asian Championship":"بطولة غرب آسيا", "African Nations Championship":"بطولة أفريقيا للمحليين", "CECAFA Cup":"كأس سيكافا", "UNCAF Cup":"كأس أونكاف" };
  const compAr = c => CMP[c] ? CMP[c] : `<span class="lat">${esc(c || "")}</span>`;
  const res = r => ({ W:"فوز", D:"تعادل", L:"خسارة" })[r] || "";
  // QA 20/41: a national team's next/last match takes its sides, score and status from our own fixture when we hold it
  const fixM = m => m && m.id && X.msum && X.msum(m.id) ? Object.assign({}, m, X.msum(m.id)) : m;
  const natHist = {}, natSq = {}, natUrl = iso => { const t = natTeams.find(x => x.iso2 === String(iso).toUpperCase()); return t && teamPages.has(t.team) ? `/t/${t.team}/` : `/national/${String(iso).toLowerCase()}/`; };
  if (natTeams.length){
    const rows = natTeams.map(t => `<tr><td class="tm"><a class="tl" href="${natUrl(t.iso2)}">${tlogo(t.team)}<span>${esc(t.name_ar)}</span></a></td><td>${t.arab_rank || ""}</td><td>${t.tifo_world_rank || ""}</td><td>${t.fifa && t.fifa.rank ? t.fifa.rank : ""}</td></tr>`);
    put("/national/", "المنتخبات العربية: التصنيف والنتايج والتاريخ", "كل المنتخبات العربية الـ22: تصنيف تيفو وفيفا، وآخر نتيجة والمباراة الياية، وكل تاريخها الدولي.", "المنتخبات العربية", "",
      `<section class="blk natme" id="natme"><h2>منتخبك</h2><div id="natmeb"><p class="muted skel">نجيب منتخب بلدك…</p></div></section>` +
      (() => { const td = new Date(Date.now() + 4 * 3600e3).toISOString().slice(0, 10), seen = new Set(), ms = [];
        natTeams.forEach(t => [fixM(t.last_result), fixM(t.next_match)].forEach(m => { if (m && m.id && !seen.has(m.id) && new Date(Date.parse(m.kickoff_utc) + 4 * 3600e3).toISOString().slice(0, 10) === td){ seen.add(m.id); ms.push(m); } }));
        ms.sort((a, b) => (R.isLive(b) - R.isLive(a)) || a.kickoff_utc.localeCompare(b.kickoff_utc));
        return ms.length ? `<section class="blk natnow" id="natnow"><h2 id="natnowh">مباريات المنتخبات اليوم</h2><div id="natnowb" data-ids="${ms.map(m => m.id).join(",")}">${ms.map(m => mrow(m, { date:false })).join("")}</div></section>` : ""; })() +
      `<div class="natflags" data-ids="${natTeams.map(t => t.team).join(",")}">${natTeams.map(t => `<a href="${natUrl(t.iso2)}" data-cc="${t.iso2}">${tlogo(t.team).replace('class="logo sm"', 'class="logo md"')}<span>${esc(t.name_ar)}</span></a>`).join("")}</div>` +
      sec("الترتيب بتصنيف تيفو", "", tbl(["المنتخب", "عربياً", "تيفو عالمياً", "فيفا"], rows)) + note('<a href="/glossary/#tifo-rating">تصنيف تيفو</a> للمنتخبات من كل النتايج الدولية. تصنيف فيفا يظهر للمنتخبات اللي عندنا رقمها الحالي.') + '<p class="tools"><a class="btn" href="/nations-h2h/">مواجهات المنتخبات العربية</a>' + (WC && WC.teams ? '<a class="btn" href="/worldcup-arabs/">العرب في كأس العالم</a>' : "") + "</p>");
    natTeams.forEach((t, i) => {
      const { ar, ff, sq } = nat[i], iso = t.iso2.toLowerCase(), parts = [];
      const st = [t.arab_rank && `<div><b>${t.arab_rank}</b><span>عربياً بتصنيف تيفو</span></div>`, t.tifo_world_rank && `<div><b>${t.tifo_world_rank}</b><span>عالمياً بتصنيف تيفو</span></div>`, t.fifa && t.fifa.rank && `<div><b>${t.fifa.rank}</b><span>تصنيف فيفا</span></div>`, ar && ar.played && `<div><b>${ar.played}</b><span>مباراة دولية</span></div>`].filter(Boolean);
      if (st.length) parts.push(`<div class="pstats">${st.join("")}</div>`);
      const nx = [t.last_result && sec("آخر نتيجة", "", mrow(t.last_result)), t.next_match && sec("المباراة الياية", "", mrow(t.next_match))].filter(Boolean); parts.push(...nx);
      if (t.groups && t.groups.length) parts.push(sec("وين واقف في البطولات", "", tbl(["البطولة", "المجموعة", "المركز", "لعب", "النقاط"], t.groups.map(g => `<tr><td class="tm">${cmpName(g.comp) || esc(g.season || "")}</td><td>${esc(R.stageAr(g.group))}</td><td><bdi dir="ltr">${g.rank}/${g.of}</bdi></td><td>${g.played}</td><td>${g.pts}</td></tr>`))));
      if (ar && ar.matches && ar.matches.length){
        const last = ar.matches.slice(-10).reverse();
        parts.push(sec("آخر 10 نتايج", "", tbl(["التاريخ", "الخصم", "النتيجة", "البطولة"], last.map(m => `<tr><td>${dmy(m.date)}</td><td class="tm">${m.opponent && m.opponent.name_ar ? esc(m.opponent.name_ar) : opp(m.opponent && m.opponent.name)}</td><td class="r${m.result}"><bdi dir="ltr" class="num">${m.gf}-${m.ga}</bdi> ${res(m.result)}</td><td class="small">${compAr(m.competition)}</td></tr>`))));
        parts.push(sec("تاريخه الدولي", `من ${dmy(ar.first)}`, `<div class="pstats"><div><b>${ar.won}</b><span>فوز</span></div><div><b>${ar.drawn}</b><span>تعادل</span></div><div><b>${ar.lost}</b><span>خسارة</span></div></div>`));
      }
      const row = H2HM && H2HM.matrix && H2HM.matrix[t.iso2];
      if (row){ const rr = Object.entries(row).sort((a, b) => b[1].p - a[1].p);
        parts.push(sec("ضد المنتخبات العربية", "", tbl(["المنتخب", "لعب", "فوز", "تعادل", "خسارة", "الأهداف"], rr.map(([k, v]) => `<tr><td class="tm"><a href="${natUrl(k)}">${esc(CN[k] || k)}</a></td><td>${v.p}</td><td>${v.w}</td><td>${v.d}</td><td>${v.l}</td><td><bdi dir="ltr">${v.gf}-${v.ga}</bdi></td></tr>`)) + note('<a href="/nations-h2h/">قارن أي منتخبين</a>'))); }
      const wc = WC && WC.teams && WC.teams[t.iso2];
      if (wc && wc.summary) parts.push(sec("في كأس العالم", "", `<p>شارك في <b class="num">${wc.summary.tournaments}</b> نسخ: <b class="num">${wc.summary.won}</b> فوز و<b class="num">${wc.summary.drawn}</b> تعادل و<b class="num">${wc.summary.lost}</b> خسارة.</p><p><a class="btn" href="/worldcup-arabs/#${t.iso2}">كل مبارياته في كأس العالم</a></p>`));
      if (ff && ff.history && ff.history.length > 2) parts.push(sec("تصنيف فيفا", "من 1992", S.fifa(ff)));
      if (sq && sq.players && sq.players.length){ const G = { keepers:"الحراس", defenders:"الدفاع", midfielders:"الوسط", attackers:"الهجوم" }, by = {};
        sq.players.forEach(p => { (by[p.group] = by[p.group] || []).push(p); });
        natSq[t.team] = Object.keys(G).filter(k => by[k]).map(k => `<h3>${G[k]}</h3><ul class="sq">` + by[k].map(p => `<li>${pn(p.id, p.name)} <span class="muted small">${p.club_id ? tname(p.club_id, null, p.club) : esc(p.club || "")}${p.age ? "، " + p.age + " سنة" : ""}</span></li>`).join("") + "</ul>").join("");
        parts.push(sec("آخر قائمة", "", Object.keys(G).filter(k => by[k]).map(k => `<h3>${G[k]}</h3><ul class="sq">` + by[k].map(p => `<li>${pn(p.id, p.name)} <span class="muted small">${p.club_id ? tname(p.club_id, null, p.club) : esc(p.club || "")}${p.age ? "، " + p.age + " سنة" : ""}</span></li>`).join("") + "</ul>").join(""))); }
      // W4.3: this content is the التاريخ tab of /t/<id>/ now (the last result and next match are its first two tabs); the old URL points there
      if (teamPages.has(t.team) && X.stub){ natHist[t.team] = parts.filter(p => !/<h2>(آخر نتيجة|المباراة الياية|آخر قائمة)/.test(p)).join("");   /* QA 12: the squad lives in اللاعبين */ X.stub(`/national/${iso}/`, `/t/${t.team}/#hist`, `منتخب ${t.name_ar}`); return; }
      const link = teamPages.has(t.team) ? `<p class="tools"><a class="btn" href="/t/${t.team}/">المباريات والنتايج</a></p>` : "";
      put(`/national/${iso}/`, `منتخب ${t.name_ar}: التصنيف والنتايج والتاريخ`, `منتخب ${t.name_ar}: تصنيف تيفو وفيفا، وآخر النتايج، وسجله ضد المنتخبات العربية، وكأس العالم، وآخر قائمة.`, `منتخب ${esc(t.name_ar)}`, "", link + parts.join(""), { crumbs:'<a href="/national/">المنتخبات العربية</a>' });
    });
  }
  // 310: nations head-to-head (22x22): two selects and the record, never a 22-column grid on a phone
  if (H2HM && H2HM.teams && H2HM.matrix){
    const opts = H2HM.teams.map(t => `<option value="${t.iso2}">${esc(t.name_ar)}</option>`).join("");
    put("/nations-h2h/", "مواجهات المنتخبات العربية", "أي منتخبين عربيين: كم مرة تقابلوا، ومنو فاز أكثر، والأهداف، وآخر مواجهة.", "مواجهات المنتخبات العربية", "اختار منتخبين وشوف سجلهم في كل المباريات الدولية.",
      `<div class="cmpsel"><select id="nha" aria-label="المنتخب الأول">${opts}</select><select id="nhb" aria-label="المنتخب الثاني">${opts}</select></div><div id="nhout"></div><script type="application/json" id="nhdata">${JSON.stringify({ m:H2HM.matrix, n:Object.fromEntries(H2HM.teams.map(t => [t.iso2, t.name_ar])) }).replace(/</g, "\\u003c")}</script>` + note("المصدر: قاعدة نتايج المباريات الدولية المفتوحة (martj42)."), { page:"nh2h", crumbs:'<a href="/national/">المنتخبات العربية</a>' });
  }
  // 337: Arabs at the World Cup
  if (WC && WC.teams && Object.keys(WC.teams).length){
    const body = Object.entries(WC.teams).sort((a, b) => b[1].summary.played - a[1].summary.played).map(([iso, t]) => {
      const s = t.summary, trs = Object.entries(t.tournaments).sort((a, b) => b[0] - a[0]).map(([yr, ms]) => `<h3><span class="num">${yr}</span></h3><ul class="wcl">` + ms.map(m => { const sc = (m.goals || []).filter(g => !g.own_goal && g.team !== m.opponent).map(g => `<span class="lat">${esc(g.scorer)}</span> <span class="num">${esc(g.minute)}'</span>${g.penalty ? " (بلنتي)" : ""}`); return `<li><span class="r${m.result}"><bdi dir="ltr" class="num">${m.gf}-${m.ga}</bdi></span> ضد ${opp(m.opponent)}${sc.length ? ` <span class="muted small">${sc.join("، ")}</span>` : ""}</li>`; }).join("") + "</ul>").join("");
      return `<section class="blk" id="${iso}"><h2>${esc(t.name_ar)}<small>${s.tournaments} نسخ</small></h2><div class="pstats"><div><b>${s.played}</b><span>مباراة</span></div><div><b>${s.won}</b><span>فوز</span></div><div><b>${s.drawn}</b><span>تعادل</span></div><div><b>${s.lost}</b><span>خسارة</span></div></div><details class="more"><summary>كل المباريات</summary>${trs}</details></section>`; }).join("");
    put("/worldcup-arabs/", "العرب في كأس العالم: كل المباريات والنتايج", "كل مباريات المنتخبات العربية في نهائيات كأس العالم من 1934: النتايج والهدافين والحصيلة.", "العرب في كأس العالم", "كل مباريات المنتخبات العربية في النهائيات، والهدافين لما تكون أسماؤهم في المصدر.", body + note("المصدر: قاعدة نتايج المباريات الدولية المفتوحة (martj42). أسماء الهدافين كما في المصدر."), { crumbs:'<a href="/national/">المنتخبات العربية</a>' });
  }

  // ---- Arabs abroad (207/208), week star, coaches (298), referees (299), friendlies (300)
  const AB = F["arabs/abroad"], mins = p => p.league_season_stats && p.league_season_stats.mins_played;
  const starCard = s => `<div class="star"><span class="kicker">نجم الأسبوع</span><p class="big">${pn(s.player, s.name)}</p><p>${tm(s.team, s.team_ar)} <span class="muted">${cname(s.nationality)}</span></p><div class="pstats">${s.avg_rating ? `<div><b>${f1(s.avg_rating)}</b><span>التقييم</span></div>` : ""}<div><b>${s.goals}</b><span>أهداف</span></div><div><b>${s.assists}</b><span>صناعة</span></div></div></div>`;
  if (wk && wk.star){
    put("/arabs/week/", "نجوم العرب برا هالأسبوع", "أحسن 5 لاعبين عرب في الدوريات الأوروبية الكبيرة ودوري الأبطال في آخر 7 أيام.", "نجوم العرب برا هالأسبوع", "", starCard(wk.star) + sec("أحسن 5", "", '<ol class="lead">' + wk.top5.map((p, i) => `<li><span class="num muted">${i + 1}</span><span class="who">${tlogo(p.team)}${pn(p.player, p.name)} <span class="muted small">${tname(p.team, p.team_ar)}، ${cname(p.nationality)}، ${p.goals} أهداف، ${p.assists} صناعة</span></span><b>${f1(p.score)}</b></li>`).join("") + "</ol>") + note("النقاط = متوسط تقييم المباراة + هدف لكل هدف + 0.7 لكل صناعة، آخر 7 أيام."), { crumbs:hubLink });
  }
  const hub = [];
  // one card per Arab player in tonight's abroad matches: player, club, minute or kickoff, goals/assists (app.js keeps the live ones moving)
  const pnT = (id, name) => { const ar = (NAMES_AR[id] || {}).ar; return ar ? esc(ar) : `<span class="lat">${esc(name || "")}</span>`; };
  const tonightStrip = ms => { const rank = m => R.isLive(m) ? 0 : m.status === "scheduled" ? 1 : 2; const cards = [];
    ms.slice().sort((a, b) => rank(a) - rank(b) || (rank(a) === 2 ? b.kickoff_utc.localeCompare(a.kickoff_utc) : a.kickoff_utc.localeCompare(b.kickoff_utc))).forEach(m => { const id = m.match || m.id, perf = {};
      (m.performance || []).forEach(a => { perf[a.player] = a; });
      const st = R.isLive(m) ? R.minute(m) : m.status === "finished" && m.score ? `<bdi dir="ltr" class="num">${m.score.home} - ${m.score.away}</bdi>` : m.status === "scheduled" ? `<span class="num">${R.tt(m.kickoff_uae || new Date(Date.parse(m.kickoff_utc) + 4 * 3600e3).toISOString().slice(0, 19) + "+04:00")}</span>` : esc(R.statusText(m));
      (m.players || []).forEach(p => { const a = perf[p.id] || {}, ga = [a.goals ? (a.goals > 1 ? a.goals + " أهداف" : "هدف") : "", a.assists ? (a.assists > 1 ? a.assists + " صناعة" : "صناعة") : ""].filter(Boolean).join(" · ");
        const tag = matchPages.has(id) ? "a" : "div";
        cards.push(`<${tag} class="atr${R.isLive(m) ? " live" : ""}"${tag === "a" ? ` href="/m/${id}/"` : ""} data-m="${id}" data-p="${p.id}"><b class="atp">${pnT(p.id, p.name)}</b><span class="atc">${tlogo(p.team)}${tname(p.team)}</span><span class="atm">${st}</span><span class="atg">${ga}</span></${tag}>`); }); });
    return cards.length ? `<section class="blk atn" id="atn" data-slot="rail"><div class="rail-h"><h2>العرب الليلة</h2><span class="muted small">${R.n ? R.n(cards.length, ["لاعب واحد", "لاعبين", "لاعبين", "لاعب"]) : cards.length + " لاعب"}</span></div><div class="atl">${cards.slice(0, 30).join("")}</div></section>` : ""; };
  // W3.9: /arabs/ is a section front: the live «العرب الليلة» strip, the star, 4 group cards with one number each, then the rest;
  // the 92-row Europe table moved to /arabs/europe/ with the golden boot
  let starH = "", tonH = "", euroH = "";
  if (wk && wk.star) starH = starCard(wk.star) + '<p><a href="/arabs/week/">أحسن 5 هالأسبوع</a></p>';
  const TN = F["arabs/tonight"]; if (TN && TN.matches && TN.matches.length){ const tl = TN.matches.slice(0, 12).map(m => { const ms = Object.assign({ id:m.match || m.id }, m); const ps = (m.players || []).map(p => pn(p.player || p.id, p.name)).join("، "); return `<div class="gm">${mrow(ms)}${ps ? `<p class="bc muted small">${ps}</p>` : ""}</div>`; }).join(""); tonH = tonightStrip(TN.matches); void tl; home.tonight = sec("العرب الليلة برا", '<a href="/arabs/">الكل</a>', TN.matches.slice(0, 4).map(m => mrow(Object.assign({ id:m.match || m.id }, m))).join("")); }
  if (AB && AB.players && AB.players.length){
    const ps = AB.players.slice().sort((a, b) => (b.goals + b.assists) - (a.goals + a.assists) || (b.avg_rating || 0) - (a.avg_rating || 0));
    const isos = [...new Set(ps.map(p => p.nationality && p.nationality.iso2).filter(Boolean))].sort((a, b) => ps.filter(p => p.nationality.iso2 === b).length - ps.filter(p => p.nationality.iso2 === a).length);
    euroH = (sec("العرب في أوروبا هالموسم", `${ps.length} لاعب`, `<div class="cmpsel"><select id="abf" aria-label="الدولة"><option value="">كل الدول</option>${isos.map(i => `<option value="${i}">${esc(CN[i] || i)}</option>`).join("")}</select></div>` +
      tbl(["اللاعب", "لعب", "أهداف", "صناعة", "تقييم"], ps.map(p => `<tr data-c="${p.nationality && p.nationality.iso2}"><td class="tm">${tlogo(p.team)}${pn(p.id, p.name)}<br><span class="muted small">${tname(p.team, p.team_ar)}، ${cname(p.nationality)}</span></td><td>${p.apps}</td><td>${p.goals}</td><td>${p.assists}</td><td>${p.avg_rating ? f1(p.avg_rating) : ""}</td></tr>`), "wrapn") + note("اللاعبين العرب اللي لعبوا في الدوريات الخمس الكبيرة أو بطولات أوروبا هالموسم.")));
  }
  const CO = F["arabs/coaches"]; if (CO && CO.coaches && CO.coaches.length) hub.push(sec("مدربين عرب", "", '<ul class="facts-l">' + CO.coaches.map(c => `<li>${X.coachAr && X.coachAr({ id:c.coach || c.id }) ? esc(X.coachAr({ id:c.coach || c.id })) : `<span class="lat">${esc(c.name)}</span>`} <span class="muted">(${cname(c.nationality)})</span>: ${c.national_team ? "منتخب " : ""}${tname(c.team, c.team_ar)}</li>`).join("") + "</ul>" + ((CO.abroad || []).length ? "<h3>برا بلدانهم</h3><ul class=\"facts-l\">" + CO.abroad.map(c => `<li>${X.coachAr && X.coachAr({ id:c.coach || c.id }) ? esc(X.coachAr({ id:c.coach || c.id })) : `<span class="lat">${esc(c.name)}</span>`} <span class="muted">(${cname(c.nationality)})</span>: ${tname(c.team, c.team_ar)}</li>`).join("") + "</ul>" : "")));
  const RF = F["arabs/referees"]; if (RF && RF.referees && RF.referees.length) hub.push(sec("حكام عرب في البطولات القارية", "هالموسم", tbl(["الحكم", "الدولة", "مباريات"], RF.referees.slice().sort((a, b) => b.matches.length - a.matches.length).map(r => `<tr><td class="tm"><span class="lat">${esc(r.name)}</span></td><td>${cname(r.nationality)}</td><td>${r.matches.length}</td></tr>`))));
  const FR = F["arabs/friendlies"]; if (FR && FR.matches && FR.matches.length) hub.push(sec("ودّيات الأندية العربية", "", FR.matches.slice().sort((a, b) => b.kickoff_utc.localeCompare(a.kickoff_utc)).slice(0, 20).map(m => mrow(m)).join("")));
  const links = [["/arabs/week/", "نجوم الأسبوع", wk && wk.star], ["/golden-boot/", "الحذاء الذهبي العربي", 1], ["/poty/", "أحسن لاعب عربي", 1], ["/national/", "المنتخبات العربية", natTeams.length], ["/nations-h2h/", "مواجهات المنتخبات", H2HM], ["/worldcup-arabs/", "العرب في كأس العالم", WC], ["/derbies/", "الديربيات العربية", F.derbies], ["/clashes/", "مواجهات الأندية العربية", 1], ["/week/#mow", "مباراة الأسبوع", F["arabs/match-of-week"]], ["/streaks/", "السلاسل", F["arabs/streaks"]], ["/coefficients/", "أقوى دوري عربي", F["arabs/coefficients"]], ["/calendars/", "روزنامة الدوريات", F["arabs/calendars"]], ["/calendars/#year", "السنة الياية", F["calendar/year"]], ["/transfers/", "الانتقالات", F["transfers/latest"]], ["/break/", "فترة المنتخبات", 1], ["/guide/", "دليل القنوات", 1], ["/explore/", "أرشيف النتايج", F["archive/index-all"]]];
  const linkRow = () => '<div class="comps">' + links.filter(l => fs.existsSync(path.join(OUT, l[0].split("#")[0].slice(1), "index.html"))).map(l => `<a href="${l[0]}"><span>${l[1]}</span></a>`).join("") + "</div>";

  // ---- 306 match of the week (+ broadcasters by country via #wwbox), home block
  const MW = F["arabs/match-of-week"]; let mowWeek = "";
  if (MW && MW.pick){
    const pk = MW.pick, m = Object.assign({ id:pk.match, status:"scheduled" }, pk, (X.msum && X.msum(pk.match)) || {}),   /* the fixture's own status and score win over the Monday pick */ why = [pk.derby && "ديربي", pk.arab_vs_arab && "مواجهة عربية", pk.stage_bonus >= 0.5 && "دور حاسم"].filter(Boolean).join("، ");
    const body = `<div class="mow">${mrow(m)}<p class="muted">${esc(pk.comp_name_ar || cmpName(pk.comp))}${why ? "، " + why : ""}</p>${pk.probs ? S.probs(pk.probs, m) : ""}</div><div id="wwbox" data-comp="${pk.comp}">${X.BC && X.BC[pk.comp] && S.watchWhere(X.BC[pk.comp]) ? sec("وين تنقل في الإمارات", "", S.watchWhere(X.BC[pk.comp])) : ""}</div>` + ((sl => sl ? sec("مرشحة بعدها", "", sl) : "")(MW.shortlist && MW.shortlist.length ? MW.shortlist.filter(x => x.match !== pk.match && !(Date.parse(x.kickoff_utc) < Date.now())).map(x => mrow(Object.assign({ id:x.match, status:"scheduled" }, x, (X.msum && X.msum(x.match)) || {})))   /* QA 48: no played match listed as coming */.join("") : "")) + note("نختارها كل اثنين من مباريات الأسبوع الياي اللي فيها نادي أو منتخب عربي: المتعة، والديربي، والدور، والمواجهة العربية.");
    // W4.2: a pinned card at the top of /week/ (kickoff counting down, the row goes live), /match-of-week/ points there
    if (X.stub){ mowWeek = `<section class="blk mowpin" id="mow" data-kick="${esc(m.kickoff_utc || "")}"><h2>مباراة الأسبوع<small id="mowcd"></small></h2>${body}</section>`; X.stub("/match-of-week/", "/week/#mow", "مباراة الأسبوع"); }
    else put("/match-of-week/", "مباراة الأسبوع", "مباراة الأسبوع اللي تستاهل ما تفوتك، وموعدها بتوقيت بلدك ووين تنقل.", "مباراة الأسبوع", "", body, { crumbs:hubLink, page:"mow" });
    home.mow = sec("مباراة الأسبوع", `<a href="${X.stub ? "/week/#mow" : "/match-of-week/"}">ليش اخترناها؟</a>`, mrow(m));
  }
  // 209 derbies: every derby with its FotMob head-to-head, the full page is /h2h/{k}/
  const DB = F.derbies;
  if (DB && DB.derbies && DB.derbies.length){
    const hs = await pool(DB.derbies, 4, d => d.h2h ? get(d.h2h, 1) : null);
    const body = '<div class="derbies">' + DB.derbies.map((d, i) => { const h = hs[i], k = String(d.h2h || "").replace(/^h2h\/|\.json$/g, ""), [a, b] = d.teams, w = (h && h.wins) || {}, tag = h && X.H2H && X.H2H[k] ? "a" : "div";
      return `<${tag} class="derby"${tag === "a" ? ` href="/h2h/${k}/"` : ""}><h3>${esc(d.name_ar)}</h3><p class="muted small">${esc(d.city_ar || "")}، ${esc(CN[d.country] || "")}</p>${h ? `<div class="h2hsum"><div><b>${w[a] || 0}</b>${tname(a)}</div><div><b>${w.draws || 0}</b>تعادل</div><div><b>${w[b] || 0}</b>${tname(b)}</div></div>` : '<p class="muted small">ما عندنا سجل مواجهاتهم للحين.</p>'}</${tag}>`; }).join("") + "</div>" + note("كل المواجهات اللي يعرضها FotMob لكل ديربي ومعها أرشيف تيفو (بطولاتنا من 2010/11)، في كل البطولات.");
    put("/derbies/", "أكبر الديربيات العربية", "12 ديربي عربي كبير: القاهرة والرياض وجدة والدار البيضاء وتونس وغيرها، ومنو فاز أكثر في كل واحد.", "الديربيات العربية", "", body, { crumbs:hubLink });
  }
  // 210 Arab club clashes in AFC/CAF/Arab competitions (±45 days)
  const CL = F["arabs/clashes"];
  if (CL && CL.matches && CL.matches.length){
    const up = CL.matches.filter(m => m.status !== "finished").sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc)), dn = CL.matches.filter(m => m.status === "finished").sort((a, b) => b.kickoff_utc.localeCompare(a.kickoff_utc));
    const line = m => `<div class="gm">${mrow(m)}<p class="bc muted small">${esc(m.comp_name_ar || "")}، ${cname(m.home_country)} ضد ${cname(m.away_country)}</p></div>`;
    put("/clashes/", "مواجهات الأندية العربية في آسيا وأفريقيا", "كل مباراة بين ناديين عربيين في دوري أبطال آسيا وأفريقيا والبطولة العربية، قبل وبعد.", "مواجهات الأندية العربية", "مباريات بين ناديين عربيين في البطولات القارية والعربية.", (up.length ? sec("الياية", "", up.map(line).join("")) : "") + (dn.length ? sec("اللي خلصت", "", dn.map(line).join("")) : ""), { crumbs:hubLink });
  }
  // 287 streaks + home block
  const SK = F["arabs/streaks"];
  if (SK && SK.streaks){
    const K = [["unbeaten", "بدون خسارة"], ["winning", "فوز ورا فوز"], ["clean_sheets", "شباك نظيفة"], ["winless", "بدون فوز"], ["losing", "خسارة ورا خسارة"]];
    const body = K.filter(k => (SK.streaks[k[0]] || []).length).map(([k, t]) => sec(t, "", '<ol class="lead">' + SK.streaks[k].slice(0, 10).map((s, i) => `<li><span class="num muted">${i + 1}</span><span class="who">${tm(s.team, s.team_ar)} <span class="muted small">${cname(s.country)}</span></span><b>${s.length}</b></li>`).join("") + "</ol>")).join("");
    put("/streaks/", "السلاسل في الدوريات العربية", "منو ما خسر من زمان؟ ومنو ما فاز؟ السلاسل الشغالة الحين في كل الدوريات العربية.", "السلاسل الشغالة", "مباريات الدوري بس، والسلسلة 3 مباريات وأكثر.", body, { crumbs:hubLink });
    const top = K.slice(0, 3).map(([k, t]) => { const s = (SK.streaks[k] || [])[0]; return s ? `<li>${t}: ${tm(s.team, s.team_ar)} (${cname(s.country)}) <b>${esc(R.cnt(s.length, ["مباراة", "مباراتين", "مباريات", "مباراة"]))}</b></li>` : "";   /* QA 75 */ }).filter(Boolean);
    if (top.length) home.streaks = sec("سلاسل شغالة", '<a href="/streaks/">كل السلاسل</a>', '<ul class="facts-l">' + top.join("") + "</ul>");
  }
  // 280 «أقوى دوري عربي»: AFC and CAF association rankings (facts and sources only)
  const CF = F["arabs/coefficients"];
  if (CF && (CF.afc_associations_2026_27 || CF.caf_associations_2026_27)){
    const afc = (CF.afc_associations_2026_27 || []).filter(a => a.arab), caf = (CF.caf_associations_2026_27 || []).filter(a => a.arab), cc = (CF.caf_clubs_2026_27 || []).filter(a => a.arab);
    const mv = a => a.prev_rank && a.prev_rank !== a.rank ? (a.prev_rank > a.rank ? ' <span class="up">▲</span>' : ' <span class="dn">▼</span>') : "";
    const body = (afc.length ? sec("تصنيف الاتحاد الآسيوي للدول", "2026/27", tbl(["الدولة", "المركز في آسيا", "النقاط"], afc.map(a => `<tr><td class="tm">${esc(a.name_ar)}</td><td>${a.rank}${mv(a)}</td><td>${a.total.toFixed(1)}</td></tr>`)) + note(`المصدر: <a href="${esc(CF.sources.afc.url)}" rel="noopener">ويكيبيديا</a> ومراجعها.`)) : "") +
      (caf.length ? sec("تصنيف الاتحاد الأفريقي للدول", "آخر 5 مواسم", tbl(["الدولة", "المركز في أفريقيا", "النقاط"], caf.map(a => `<tr><td class="tm">${esc(a.name_ar)}</td><td>${a.rank}${mv(a)}</td><td>${a.total}</td></tr>`)) + note(`المصدر: <a href="${esc(CF.sources.caf.url)}" rel="noopener">ويكيبيديا</a> ومراجعها.`)) : "") +
      "";   // W1.8: the club table printed countries where the clubs should be; hidden until the source is fixed
    put("/coefficients/", "أقوى دوري عربي: تصنيف آسيا وأفريقيا", "ترتيب الدوريات العربية في تصنيف الاتحاد الآسيوي والأفريقي، ونقاط كل دولة.", "أقوى دوري عربي؟", "الجواب الرسمي: تصنيف الاتحادين القاريين من نتايج الأندية في البطولات القارية.", body, { crumbs:hubLink });
  }
  // 282 calendars + 322 the year ahead
  const CA = F["arabs/calendars"]; let calBody = "", yrBody = "";
  if (CA && CA.leagues){
    const body = Object.entries(CA.leagues).map(([id, l]) => sec(esc(l.name_ar), cname(l.country), `<dl class="facts"><div><dt>أول مباراة</dt><dd>${dmy(l.first_match)}</dd></div><div><dt>آخر مباراة منشورة</dt><dd>${dmy(l.last_published_match)}</dd></div><div><dt>مباريات منشورة</dt><dd>${num(l.matches_published)}</dd></div></dl>` + (l.breaks.length ? "<h3>التوقفات</h3><ul class=\"facts-l\">" + l.breaks.map(b => `<li>من ${dmy(b.from)} لين ${dmy(b.to)} <span class="muted">(${b.days} يوم)</span></li>`).join("") + "</ul>" : ""))).join("");
    calBody = body;
  }
  const YR = F["calendar/year"];
  if (YR && YR.events && YR.events.length){
    const ev = YR.events.filter(e => (e.to || e.date) >= YR.from).sort((a, b) => a.date.localeCompare(b.date)), by = {};
    ev.forEach(e => { const k = e.date.slice(0, 7); (by[k] = by[k] || []).push(e); });
    const lab = e => e.kind === "final" ? (e.match && matchPages.has(e.match) ? `<a href="/m/${e.match}/">نهائي ${esc(e.name_ar || cmpName(e.comp))}</a>` : `نهائي ${esc(e.name_ar || cmpName(e.comp))}`) : e.kind === "international_window" ? "فترة المنتخبات" : e.kind === "league_break" ? `توقف ${cmpName(e.comp) || esc(e.name_ar || "")}` : e.kind === "league_start" ? `بداية ${cmpName(e.comp) || esc(e.name_ar || "")}` : e.kind === "draw" ? `قرعة ${cmpName(e.comp) || esc(e.name_ar || "")}` : esc(e.name_ar || e.kind);
    const body = Object.keys(by).map(k => { const [y, m] = k.split("-").map(Number); return `<section class="blk"><h2>${month[m - 1]} <span class="num">${y}</span></h2><ul class="yl">` + by[k].map(e => `<li class="k-${e.kind}"><span class="muted small">${dm(e.date)}${e.to && e.to !== e.date ? " لين " + dm(e.to) : ""}</span> ${lab(e)}</li>`).join("") + "</ul></section>"; }).join("") + note("من المباريات المنشورة. فترات الانتقالات ومواعيد الجوائز مب فيها، لأننا ما لقينا لها مصدر نقدر نتحقق منه.");
    yrBody = body;
  }
  // W4.2: /year/ is the first half of /calendars/ now
  if (calBody || yrBody){ const sh = (h, t) => { const bl = X.blocks ? X.blocks(h) : null; return bl && bl.secs.length && X.shelf ? bl.rest + X.shelf(bl.secs, { title:t }) : h; };
    put("/calendars/", "الروزنامة: السنة الياية ومواعيد الدوريات العربية", "النهائيات وفترات المنتخبات وتوقفات الدوريات في الـ12 شهر الياية، ومتى يبدا ويخلص كل دوري عربي.", "الروزنامة", "", (yrBody ? `<div id="year"></div>` + sh(yrBody, "السنة الياية") : "") + (calBody ? `<div id="leagues"></div><p class="muted">من المباريات المنشورة للحين، والتوقف = 12 يوم وأكثر بدون مباريات.</p>` + sh(calBody, "روزنامة الدوريات العربية") : ""), { crumbs:hubLink });
    if (yrBody && X.stub) X.stub("/year/", "/calendars/#year", "السنة الياية"); }
  // 263 transfers (last 60 days, Arab leagues)
  const TR = F["transfers/latest"];
  // the world's transfer market (spec 2026-10-09 transfers, phase 1; build.cjs passes the ledger): /transfers/ and a page per tracked league
  const { TRT, TRW, TRS, TRL, TRR, TAR, FMP } = X, AR_ = /[؀-ۿ]/;
  const trNames = { pname:id => (NAMES_AR[id] || {}).ar, cname:id => ((teamsJson.teams || {})[id] || {}).name_ar || (TAR || {})[id] };
  if (TRT && TRW && TRS.length){
    // a page per league: the site's (/transfers/<key>/), then every league of the encyclopedia with an Arabic name and 10 moves
    // or more (/transfers/l/<id>/; owner 2026-10-10 item 2), cups out
    const WL = ((await get("world/leagues.json")) || {}).leagues || [], LGL = [], seenL = new Set();
    (X.comps || []).forEach(c => { if (c.kind === "league" && !c.dormant && c.key){ LGL.push({ id:+c.id, name_ar:c.name_ar, p:`/transfers/${c.key}/`, min:5 }); seenL.add(+c.id); } });
    WL.forEach(l => { if (!seenL.has(+l.id) && l.name_ar && !/كأس|السوبر/.test(l.name_ar)) LGL.push({ id:+l.id, name_ar:l.name_ar, p:`/transfers/l/${l.id}/`, min:10 }); });
    const lgName = {}; LGL.forEach(l => { lgName[l.id] = l.name_ar; });
    const lgs = [];
    for (const c of LGL){
      const ids = {}; Object.entries(TRW.clubs || {}).forEach(([id, v]) => { if (v && +v[1] === +c.id) ids[id] = 1; });
      const mv = TRT.league(TRS, ids); if (mv.length < c.min) continue;
      const clubs = Object.keys(ids).map(id => TRT.forClub(mv, id)).filter(x => x.in.length || x.out.length).sort((a, b) => (b.spent - a.spent) || (b.in.length + b.out.length - a.in.length - a.out.length));
      const cn = id => trNames.cname(id) || (TRW.clubs[id] || [])[0] || "";
      const p = c.p;
      const body = (TRT.top(mv, 10).length ? `<section class="blk"><h2>أغلى صفقاته</h2>${TRT.list(TRT.top(mv, 10), trNames)}</section>` : "") +
        clubs.map(x => `<section class="blk"><h2><a href="/t/${x.id}/">${esc(cn(x.id))}</a></h2>${TRT.clubSection(x, trNames)}</section>`).join("");
      put(p, `انتقالات ${c.name_ar} ${TRL}: كل الصفقات والقادمين والراحلين`, `كل لاعب انتقل من أندية ${c.name_ar} أو إليها في ${TRL}: النادي السابق والجديد، والمبلغ إذا أُعلن، وما صرفه كل نادي.`,
        `انتقالات ${esc(c.name_ar)}`, `${TRL}، <span class="num">${mv.length}</span> انتقال.`, body, { crumbs:'<a href="/transfers/">الانتقالات</a>', page:"transfers" });
      lgs.push([p, c.name_ar, mv.length]);
    }
    // phase 3: the rumours (open, came true, did not) and the contracts ending by next June, by club
    const rOpen = (TRR || []).filter(r => !r.out), rDone = (TRR || []).filter(r => r.out === "done"), rNo = (TRR || []).filter(r => r.out === "no");
    const hasR = put("/transfers/rumours/", "إشاعات الانتقالات: آخر أخبار الصفقات والمفاوضات", "إشاعات الانتقالات في أندية العالم: اللاعب والنادي المرتبط به، ومرحلة المفاوضات، والإشاعات التي تحققت والتي لم تتحقق.",
      "إشاعات الانتقالات", `<span class="num">${rOpen.length}</span> إشاعة شغالة. كل إشاعة تنقفل لما تصير الصفقة («صدقت») أو تخلص فترة الانتقالات بدونها («ما صدقت»).`,
      (rOpen.length ? `<section class="blk"><h2>شغالة</h2>${TRT.rumourList(rOpen.slice(0, 120), trNames)}</section>` : "") +
      (rDone.length ? `<section class="blk"><h2>صدقت</h2>${TRT.rumourList(rDone.slice(0, 60), trNames)}</section>` : "") +
      (rNo.length ? `<section class="blk"><h2>ما صدقت</h2>${TRT.rumourList(rNo.slice(0, 60), trNames)}</section>` : ""), { crumbs:'<a href="/transfers/">الانتقالات</a>', page:"transfers" });
    const EX = TRT.expiring(FMP, new Date(Date.now() + 4 * 36e5).toISOString().slice(0, 10)), exBy = {};
    EX.players.forEach(p => { (exBy[p[2]] = exBy[p[2]] || []).push(p); });
    // the site's leagues first, in their order (the UAE and the Arab leagues lead), then the most players
    const lrank = id => { const lid = ((TRW.clubs || {})[id] || [])[1], i = (X.comps || []).findIndex(c => +c.id === +lid); return i < 0 ? 1e4 : i; };
    const exClubs = Object.keys(exBy).filter(id => trNames.cname(id)).sort((a, b) => lrank(a) - lrank(b) || exBy[b].length - exBy[a].length);
    const hasE = exClubs.length && put("/transfers/expiring/", `اللاعبون الذين تنتهي عقودهم في ${EX.until.slice(0, 4)}: الصفقات المجانية القادمة`, `اللاعبون الذين تنتهي عقودهم قبل 30 يونيو ${EX.until.slice(0, 4)} في كل نادي، ويمكنهم الانتقال مجاناً.`,
      `ينتهي عقده قبل 30 يونيو ${EX.until.slice(0, 4)}`, `<span class="num">${EX.players.length}</span> لاعب يقدر يطلع مجاناً الصيف الياي.`,
      exClubs.map(id => `<section class="blk"><h2><a href="/t/${id}/">${esc(trNames.cname(id))}</a> <span class="muted small num">${exBy[id].length}</span></h2><ul class="wcl">${exBy[id].map(p => `<li><a href="/p/${p[0]}/">${(NAMES_AR[p[0]] || {}).ar ? esc(NAMES_AR[p[0]].ar) : `<span class="lat">${esc(p[1])}</span>`}</a> <span class="muted small">${dm(p[3])} <span class="num">${p[3].slice(0, 4)}</span></span></li>`).join("")}</ul></section>`).join(""),
      { crumbs:'<a href="/transfers/">الانتقالات</a>', page:"transfers" });
    // owner 2026-10-10 items 10 and 9: «منو صرف أكثر» and the players without a club now
    const SP = TRT.spending(TRS, TRW.clubs), cn0 = id => trNames.cname(id) || ((TRW.clubs || {})[id] || [])[0] || "";
    const spRow = (h, t, a, b) => `<li><a href="${h}">${t}</a> <span class="muted">صرف ${TRT.eur(a) || "<span class=\"num\">0</span>"}${b ? `، باع بـ${TRT.eur(b)}` : ""}</span></li>`;
    const hasS = SP.clubs.length && put("/transfers/spending/", `أكثر الأندية إنفاقاً في ${TRL}: ترتيب الصرف في سوق الانتقالات`, `ترتيب أندية العالم ودورياته حسب ما صرفته على الصفقات في ${TRL}، وما كسبته من البيع.`,
      "منو صرف أكثر", `${TRL}، الصفقات اللي انعلن مبلغها بس.`,
      `<section class="blk"><h2>الأندية</h2><ul class="wcl">${SP.clubs.slice(0, 50).map(c => spRow(`/t/${c.id}/`, AR_.test(cn0(c.id)) ? esc(cn0(c.id)) : `<span class="lat">${esc(cn0(c.id))}</span>`, c.spent, c.received)).join("")}</ul></section>` +
      `<section class="blk"><h2>الدوريات</h2><ul class="wcl">${SP.leagues.filter(l => lgName[l[0]]).slice(0, 30).map(l => spRow((LGL.find(x => +x.id === +l[0]) || {}).p || "/transfers/", esc(lgName[l[0]]), l[1], l[2])).join("")}</ul></section>`,
      { crumbs:'<a href="/transfers/">الانتقالات</a>', page:"transfers" });
    // item 8: which sources' rumours came true (the rumour ledger closes them: «صدقت» / «ما صدقت»)
    const SR = TRT.sources(TRR || []), pct = x => Math.round(100 * x[2] / x[1]);
    const srTbl = rows => tbl(["المصدر", "انقفلت", "صدقت", "ما صدقت", "النسبة"], rows.map(x => `<tr><td style="text-align:start">${AR_.test(x[0]) ? esc(x[0]) : `<span class="lat">${esc(x[0])}</span>`}</td><td class="num">${x[1]}</td><td class="num">${x[2]}</td><td class="num">${x[3]}</td><td class="num">${pct(x)}%</td></tr>`));
    const hasC = (SR.ranked.length || SR.few.length) && put("/transfers/sources/", "أصدق مصادر أخبار الانتقالات: نسبة الإشاعات التي تحققت", "ترتيب المواقع والصحفيين حسب نسبة إشاعات الانتقالات التي تحققت فعلاً، من سجل تيفو لكل إشاعة.",
      "أصدق مصدر في الانتقالات", "كل إشاعة نتابعها لين تصدق (تصير الصفقة) أو ما تصدق (تخلص فترة الانتقالات بدونها). كل مصدر نشرها ينحسب له. الترتيب يتعدل مع كل فترة.",
      (SR.ranked.length ? `<section class="blk"><h2>الترتيب</h2><p class="muted">المصادر اللي انقفلت لها 3 إشاعات أو أكثر.</p>${srTbl(SR.ranked)}</section>` : "") +
      (SR.few.length ? `<section class="blk"><h2>بعدها قليلة</h2><p class="muted">أقل من 3 إشاعات انقفلت، فما ندخلها الترتيب للحين.</p>${srTbl(SR.few.slice(0, 40))}</section>` : ""),
      { crumbs:'<a href="/transfers/">الانتقالات</a>', page:"transfers" });
    const FA = TRT.freeAgents(TRS);
    const hasF = FA.length && put("/transfers/free-agents/", "لاعبون بدون نادٍ: اللاعبون الأحرار المتاحون الآن", "اللاعبون الذين أصبحوا بدون نادٍ هذا الموسم ويمكنهم التوقيع مع أي نادٍ الآن، مع آخر نادٍ لعبوا له وقيمتهم السوقية.",
      "لاعبين بدون نادي الحين", `<span class="num">${FA.length}</span> لاعب طلع من ناديه هالموسم وما وقّع مع غيره، ويقدر يوقع مع أي نادي الحين.`,
      `<ul class="wcl">${FA.slice(0, 300).map(m => `<li><a href="/p/${m[1]}/">${AR_.test((NAMES_AR[m[1]] || {}).ar || m[2] || "") ? esc((NAMES_AR[m[1]] || {}).ar || m[2]) : `<span class="lat">${esc(m[2])}</span>`}</a> <span class="muted">آخر نادي: ${AR_.test(cn0(m[3]) || "") ? esc(cn0(m[3])) : `<span class="lat">${esc(cn0(m[3]) || m[4] || "")}</span>`}، من ${dm(m[0])}</span>${m[9] ? ` <b>قيمته ${TRT.eur(m[9])}</b>` : ""}</li>`).join("")}</ul>`,
      { crumbs:'<a href="/transfers/">الانتقالات</a>', page:"transfers" });
    const ar = TRT.arabs(TRS), nClubs = new Set(TRS.flatMap(m => [m[3], m[5]])).size;
    const body = `<p class="tools">${hasR ? `<a class="btn" href="/transfers/rumours/">الإشاعات (<span class="num">${rOpen.length}</span>)</a>` : ""}${hasC ? `<a class="btn" href="/transfers/sources/">أصدق مصدر</a>` : ""}${hasS ? `<a class="btn" href="/transfers/spending/">منو صرف أكثر</a>` : ""}${hasF ? `<a class="btn" href="/transfers/free-agents/">لاعبين بدون نادي</a>` : ""}${hasE ? `<a class="btn" href="/transfers/expiring/">ينتهي عقده الصيف الياي</a>` : ""}</p>` +
      `<section class="blk"><h2>أغلى الصفقات</h2>${TRT.list(TRT.top(TRS, 30), trNames)}</section>` +
      `<section class="blk"><h2>آخر الانتقالات</h2>${TRT.list(TRS.slice(0, 60), trNames)}</section>` +
      (ar.length ? `<section class="blk"><h2>اللاعبين العرب</h2><p class="muted">كل لاعب عربي انتقل هالموسم، في أي دوري.</p>${TRT.list(ar.slice(0, 80), trNames)}</section>` : "") +
      (lgs.length ? `<section class="blk"><h2>حسب الدوري</h2><ul class="mlist cols">${lgs.sort((a, b) => b[2] - a[2]).map(l => `<li><a href="${l[0]}">${esc(l[1])}</a> <span class="muted small num">${l[2]}</span></li>`).join("")}</ul></section>` : "");
    put("/transfers/", `سوق الانتقالات ${TRL}: كل صفقات أندية العالم`, `كل انتقال في ${TRL} لأكثر من ${Math.floor(nClubs / 100) * 100} نادي حول العالم: أغلى الصفقات، وآخرها، واللاعبين العرب، وانتقالات كل دوري.`,
      "سوق الانتقالات", `${TRL}: <span class="num">${TRS.length}</span> انتقال بين <span class="num">${nClubs}</span> نادي.`, body, { crumbs:hubLink, page:"transfers" });
  } else if (TR && TR.transfers && TR.transfers.length){
    const FEE = { "free transfer":"انتقال حر", "free agent":"لاعب حر", "loan":"إعارة", "on loan":"إعارة", "undisclosed":"مبلغ غير معلن", "loan fee":"إعارة بمقابل", "back from loan":"رجع من الإعارة" };
    const fee = t => t.loan ? "إعارة" : t.free_agent ? "لاعب حر" : FEE[String(t.fee || "").toLowerCase()] || "";
    const isos = [...new Set(TR.transfers.map(t => t.country && t.country.iso2).filter(Boolean))];
    const body = `<div class="cmpsel"><select id="trf" aria-label="الدوري"><option value="">كل الدول</option>${isos.map(i => `<option value="${i}">${esc(CN[i] || i)}</option>`).join("")}</select></div><ul class="trl" id="trl">` + TR.transfers.map(t => `<li data-c="${t.country && t.country.iso2}"><span class="muted small">${dm(t.date)}</span> ${pn(t.player.id, t.player.name)}${t.position ? ` <span class="muted small">${esc(R.pos ? R.pos(t.position) : t.position)}</span>` : ""}<br>${t.from && t.from.id ? tm(t.from.id, t.from.name_ar, t.from.name) : '<span class="muted">بدون نادي</span>'} ← ${tm(t.to.id, t.to.name_ar, t.to.name)}${fee(t) ? ` <span class="tag">${fee(t)}</span>` : ""}</li>`).join("") + "</ul>" + note("الانتقالات للأندية في الدوريات العربية آخر 60 يوم، من صفحات الدوريات في FotMob.");
    put("/transfers/", "آخر الانتقالات في الدوريات العربية", "كل لاعب انتقل لنادي في الدوريات العربية آخر 60 يوم: من وين ولوين، وإعارة أو انتقال حر.", "آخر الانتقالات", "", body, { crumbs:hubLink, page:"transfers" });
  }
  // 307 golden boot, 308 player of the season (weights shown only once the pipeline has league strengths)
  const GB = F["arabs/golden-boot"];
  if (GB && GB.players && GB.players.length){
    const wtd = GB.league_strength && Object.keys(GB.league_strength).length;
    put("/golden-boot/", "الحذاء الذهبي العربي", "هدافين العرب هالموسم في الدوريات العربية والأوروبية الكبيرة.", "الحذاء الذهبي العربي", "أهداف الدوري للاعبين العرب هالموسم، في الدوريات العربية والخمس الكبيرة.",
      '<ol class="lead">' + GB.players.slice(0, 40).map((p, i) => `<li><span class="num muted">${i + 1}</span><span class="who">${tlogo(p.team)}${pn(p.player, p.name)} <span class="muted small">${tname(p.team, p.team_ar)}، ${cname(p.nationality)}${wtd ? `، بالوزن ${f1(p.weighted_goals)}` : ""}</span></span><b>${p.goals}</b></li>`).join("") + "</ol>", { crumbs:hubLink });
  }
  const PT = F["arabs/poty"];
  if (PT && PT.players && PT.players.length){
    const wtd = PT.league_strength && Object.keys(PT.league_strength).length, wks = [...new Set(PT.players.flatMap(p => Object.keys(p.rank_history || {})))].sort();
    let chart = "";
    if (wks.length >= 2){ const top = PT.players.slice(0, 5), W = 600, H = 180, xs = i => W - 20 - i / (wks.length - 1) * (W - 40), ys = r => 10 + (Math.min(r, 20) - 1) / 19 * (H - 30);
      chart = `<div class="rchart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="ترتيب أول 5 كل أسبوع">` + top.map((p, j) => { const pts = wks.map((w, i) => p.rank_history[w] ? [xs(i), ys(p.rank_history[w])] : null).filter(Boolean); return `<path d="${pts.map((q, i) => (i ? "L" : "M") + q[0].toFixed(1) + " " + q[1].toFixed(1)).join(" ")}" stroke="${R.col(p.team, 0)}" fill="none" stroke-width="3"/>`; }).join("") + '</svg><p class="muted small">الترتيب كل أسبوع لأول 5، وأحدث أسبوع على اليسار.</p></div>'; }
    put("/poty/", "سباق أحسن لاعب عربي في الموسم", "ترتيب أحسن لاعب عربي هالموسم من التقييم والأهداف والصناعة والدقايق، ويتحدّث كل أسبوع.", "سباق أحسن لاعب عربي", "",
      '<ol class="lead">' + PT.players.slice(0, 30).map((p, i) => `<li><span class="num muted">${i + 1}</span><span class="who">${tlogo(p.team)}${pn(p.player, p.name)} <span class="muted small">${tname(p.team, p.team_ar)}، ${cname(p.nationality)}، تقييم ${f1(p.rating)}، ${p.goals} أهداف، ${p.assists} صناعة</span></span><b>${f1(p.score)}</b></li>`).join("") + "</ol>" + chart +
      note("النقاط = (التقييم ناقص 6) × 10 + 4 لكل هدف + 3 لكل صناعة، وتقل للي لعب أقل من 1800 دقيقة" + (wtd ? "، ومضروبة في قوة الدوري." : ".")), { crumbs:hubLink });
  }
  // 281 TV guide per country: prerendered for the UAE, the client swaps to the visitor's country (/v1/guide/{iso}.json)
  const gAE = await get("guide/AE.json");
  put("/guide/", "دليل القنوات: مباريات الأيام الياية ووين تنقل في بلدك", "مباريات الثلاث أيام الياية وقنواتها في كل دولة عربية، بتوقيت بلدك.", "دليل القنوات", "مباريات الثلاث أيام الياية والقنوات اللي تنقلها في بلدك.",
    `<div class="cmpsel"><select id="gsel" aria-label="الدولة">${R.COUNTRIES.map(c => `<option value="${c[0]}"${c[0] === "AE" ? " selected" : ""}>${c[1]}</option>`).join("")}</select></div><div id="guide">${R.guide(gAE)}</div>` + note("القنوات من بحث تيفو في مواقع الناقلين والأخبار، وممكن تتغيّر. تأكد من دليل قناتك."), { page:"guide" });
  // 284 explore every stored result (archive/all/{season}.json, fetched on demand)
  const AX = F["archive/index-all"];
  if (AX && AX.seasons && AX.seasons.length){
    const ss = AX.seasons.slice().sort((a, b) => b.season.localeCompare(a.season));
    put("/explore/", "أرشيف النتايج: كل مباراة من 2020", "دوّر في كل نتيجة مخزنة من موسم 2020/21: اختار الموسم والبطولة والفريق.", "أرشيف النتايج", "اختار الموسم، وبعدها البطولة أو الفريق.",
      `<div class="cmpsel"><select id="exs" aria-label="الموسم">${ss.filter(s => parseInt(s.season, 10) >= 2020).map(s => `<option value="${esc(s.season)}">${esc(s.season.replace("-", "/"))} (${s.matches})</option>`).join("")}</select><select id="exc" aria-label="البطولة"><option value="">كل البطولات</option></select><input id="ext" type="search" placeholder="اسم الفريق" aria-label="الفريق"></div><div id="exout"><p class="empty">نحمّل…</p></div><script type="application/json" id="excomps">${JSON.stringify(Object.fromEntries((index.competitions || []).map(c => [c.id, c.name_ar]))).replace(/</g, "\\u003c")}</script>`, { page:"explore" });
  }
  // 245 international break hub: every Arab national team's next and last match, shown on the home page while a window is on
  { const nx = natTeams.filter(t => t.next_match || t.last_result);
    if (nx.length){
      const up = nx.filter(t => t.next_match).map(t => fixM(t.next_match)).filter((m, i, a) => a.findIndex(x => x.id === m.id) === i).sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc));
      const dn = nx.filter(t => t.last_result).map(t => fixM(t.last_result)).filter((m, i, a) => a.findIndex(x => x.id === m.id) === i).sort((a, b) => b.kickoff_utc.localeCompare(a.kickoff_utc));
      put("/break/", "فترة المنتخبات: مباريات المنتخبات العربية", "كل مباريات المنتخبات العربية الياية وآخر نتايجها في فترة المنتخبات، بتوقيت بلدك.", "فترة المنتخبات", "مباريات المنتخبات العربية الياية وآخر نتايجها.", (up.length ? sec("الياية", "", up.map(m => mrow(m)).join("")) : "") + (dn.length ? sec("آخر النتايج", "", dn.map(m => mrow(m)).join("")) : "") + '<p class="tools"><a class="btn" href="/national/">المنتخبات العربية</a></p>', { crumbs:hubLink });
      const today = new Date(Date.now() + 4 * 3600e3).toISOString().slice(0, 10), win = YR && (YR.events || []).find(e => e.kind === "international_window" && e.date <= today && (e.to || e.date) >= today);
      if (win && up.length) home.brk = sec("فترة المنتخبات", '<a href="/break/">كل المباريات</a>', up.slice(0, 4).map(m => mrow(m)).join(""));
    } }
  // the hub
  const AB2 = F["arabs/abroad"], TRF = F["transfers/latest"], DRB = F.derbies, sum = (a, k) => a.reduce((s, x) => s + (x[k] || 0), 0);
  const gb10 = GB && GB.players && GB.players.length ? sec("الحذاء الذهبي العربي", '<a href="/golden-boot/">الترتيب كامل</a>', '<ol class="lead">' + GB.players.slice(0, 10).map((p, i) => `<li><span class="num muted">${i + 1}</span><span class="who">${tlogo(p.team)}${pn(p.player, p.name)} <span class="muted small">${tname(p.team, p.team_ar)}، ${cname(p.nationality)}</span></span><b>${p.goals}</b></li>`).join("") + "</ol>") : "";
  const euroOk = euroH ? put("/arabs/europe/", "العرب في أوروبا هالموسم", "كل لاعب عربي لعب في الدوريات الخمس الكبيرة أو بطولات أوروبا هالموسم: المباريات والأهداف والصناعة والتقييم، والحذاء الذهبي العربي.", "العرب في أوروبا", "", gb10 + euroH, { crumbs:hubLink }) : false;
  const wk7 = natTeams.filter(t => t.next_match && Date.parse(t.next_match.kickoff_utc) - Date.now() < 7 * 864e5 && Date.parse(t.next_match.kickoff_utc) > Date.now() - 3 * 3600e3).length;
  const nf = (n, f) => n === 1 ? f[0] : n === 2 ? f[1] : n % 100 >= 3 && n % 100 <= 10 ? f[2] : f[3];   // Arabic number agreement: 1 · 2 · 3–10 · 11+
  const card = (t, n, lbl, ls) => `<div class="agc"><h3>${t}</h3><p class="agn"><b class="num">${n}</b><span>${lbl}</span></p><div class="agl">${ls.filter(l => fs.existsSync(path.join(OUT, l[0].split("#")[0].slice(1), "index.html"))).map(l => `<a href="${l[0]}">${l[1]}</a>`).join("")}</div></div>`;
  const groups = '<div class="agrid">' + [
    card("اللاعبين برا", AB2 && AB2.players ? sum(AB2.players, "goals") : 0, nf(AB2 && AB2.players ? sum(AB2.players, "goals") : 0, ["هدف للعرب في أوروبا هالموسم", "هدفين للعرب في أوروبا هالموسم", "أهداف للعرب في أوروبا هالموسم", "هدف للعرب في أوروبا هالموسم"]), [["/arabs/europe/", "العرب في أوروبا"], ["/arabs/week/", "نجوم الأسبوع"], ["/golden-boot/", "الحذاء الذهبي"], ["/poty/", "أحسن لاعب عربي"]]),
    card("المنتخبات", wk7 || natTeams.length, wk7 ? nf(wk7, ["منتخب عربي يلعب هالأسبوع", "منتخبين عربيين يلعبون هالأسبوع", "منتخبات عربية تلعب هالأسبوع", "منتخب عربي يلعب هالأسبوع"]) : nf(natTeams.length, ["منتخب عربي", "منتخبين عربيين", "منتخبات عربية", "منتخب عربي"]), [["/national/", "المنتخبات العربية"], ["/break/", "فترة المنتخبات"], ["/nations-h2h/", "مواجهات المنتخبات"], ["/worldcup-arabs/", "العرب في كأس العالم"]]),
    card("الأندية والديربيات", DRB && DRB.derbies ? DRB.derbies.filter(d => d.h2h).length : 0, nf(DRB && DRB.derbies ? DRB.derbies.filter(d => d.h2h).length : 0, ["ديربي عربي نتابعه", "ديربيين عربيين نتابعهم", "ديربيات عربية نتابعها", "ديربي عربي نتابعه"]), [["/derbies/", "الديربيات"], ["/week/#mow", "مباراة الأسبوع"], ["/clashes/", "مواجهات الأندية"], ["/coefficients/", "أقوى دوري عربي"]]),
    card("الانتقالات والروزنامة", TRF && TRF.transfers ? TRF.transfers.length : 0, nf(TRF && TRF.transfers ? TRF.transfers.length : 0, ["انتقال", "انتقالين", "انتقالات", "انتقال"]) + " في آخر " + ((TRF && TRF.days) || 60) + " يوم", [["/transfers/", "الانتقالات"], ["/calendars/", "الروزنامة"], ["/explore/", "أرشيف النتايج"]])].join("") + "</div>";
  if (euroOk) links.unshift(["/arabs/europe/", "العرب في أوروبا", 1]);
  const fold = `<details class="allsec"><summary>كل الأقسام</summary>${linkRow()}</details>`;
  put("/arabs/", "العرب: المحترفين برا والمنتخبات والديربيات", "كل شي عن الكورة العربية: اللاعبين العرب في أوروبا، ونجم الأسبوع، والمنتخبات، والديربيات، والانتقالات.", "العرب", "", tonH + starH + groups + (() => { const hb = X.blocks ? X.blocks(hub.join("")) : null; return hb && hb.secs.length && X.shelf ? hb.rest + X.shelf(hb.secs, { title:"أكثر عن العرب" }) : hub.join(""); })() + fold, { page:"arabs" });

  // 320 founding anniversaries (1.5 KB, the client picks today's date) and 242 birthdays (fetched by the client)
  const AN = F["clubs/anniversaries"];
  home.days = `<div id="bdays"${AN && AN.by_day ? ` data-an='${JSON.stringify(Object.fromEntries(Object.entries(AN.by_day).map(([k, v]) => [k, v.map(x => [x.team, x.name_ar, x.year])]))).replace(/'/g, "&#39;")}'` : ""}></div>`;

  // logos referenced above that the main build did not fetch
  await pool([...logos].filter(Boolean), 8, async id => {
    const f = path.join(CACHE, "logo", id + ".png"), o = path.join(OUT, "logo", id + ".png"); if (fs.existsSync(o)) return;
    if (!fs.existsSync(f)){ try { const r = await fetch(`https://images.fotmob.com/image_resources/logo/teamlogo/${id}.png`, { signal:AbortSignal.timeout(20000) }); if (r.ok) fs.writeFileSync(f, Buffer.from(await r.arrayBuffer())); } catch (e){} }
    if (fs.existsSync(f)) fs.copyFileSync(f, o);
  });
  return { home, search, natHist, natSq, mowWeek };
};
