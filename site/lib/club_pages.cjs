// A static page for every club of the encyclopedia (owner 2026-10-10 item 1): /db/club/<id>/ from its world card
// (db/world.py v1/world/club/<id>.json; db/transfers_world.py adds the site's teams it does not cover) and the season's
// ledger (lib/transfers.cjs). Before it these clubs lived only on the browser-drawn /db/club/?id= and the build unlinked
// ~26,000 links a run to them. A club with no Arabic name (Arabic search finds nothing) or nothing to show gets no page.
"use strict";
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const AR = /[؀-ۿ]/;
const nm = s => AR.test(s || "") ? esc(s) : `<span class="lat">${esc(s)}</span>`;
const GROUPS = [["keepers", "حراس المرمى"], ["defenders", "الدفاع"], ["midfielders", "الوسط"], ["attackers", "الهجوم"], ["coach", "المدرب"]];
const sec = (h, body, n) => `<section class="grp"><div class="gh"><h2>${h}</h2>${n ? `<span class="nn"><span class="num">${n}</span></span>` : ""}</div><div class="card">${body}</div></section>`;

// ctx: {TRT, moves (the season's ledger), rumours, season (label), site, leaguePath(id) -> its transfers page or null, pname(id)}
function clubPage(c, ctx) {
  if (!c || !AR.test(c.name_ar || "")) return null;
  const T = ctx.TRT, name = c.name_ar, sq = (c.squad || []).filter(m => Array.isArray(m) && m[0] && m[1]);
  const win = T.forClub(ctx.moves || [], c.id), rum = T.rumoursOf(ctx.rumours || [], { club: c.id, open: 1 }).slice(0, 10);
  const tro = (c.trophies || []).filter(t => t && t.won > 0);
  if (!sq.length && !win.in.length && !win.out.length && !tro.length) return null;
  const lp = c.league && ctx.leaguePath && ctx.leaguePath(+c.league);
  const league = c.league_ar ? (lp ? `<a href="${lp}">${esc(c.league_ar)}</a>` : esc(c.league_ar)) : "";
  const v = c.venue && c.venue.name ? c.venue : null;
  const intro = `<p class="intro">${esc(name)} نادي ${c.country_ar ? "من " + esc(c.country_ar) : ""}${c.league_ar ? `، يلعب في ${league}` : ""}${c.position ? `، وترتيبه <span class="num">${+c.position}</span> في آخر جدول` : ""}${v ? `، وملعبه ${nm(v.name)}${v.capacity ? ` (<span class="num">${(+v.capacity).toLocaleString("en")}</span> متفرج)` : ""}` : ""}.</p>`;
  const pname = id => (ctx.pname && ctx.pname(id)) || null;
  const squad = GROUPS.map(([g, label]) => { const l = sq.filter(m => m[3] === g); return l.length ? sec(label, l.map(m => `<a class="row" href="/p/${m[0]}/"><span class="rt"><b>${nm(pname(m[0]) || m[1])}</b></span><span class="rv num">${m[2] != null ? esc(m[2]) : ""}</span></a>`).join(""), g === "coach" ? 0 : l.length) : ""; }).join("");
  const window = T.clubSection(win, { pname, cname: ctx.cname });
  const titles = tro.length ? sec("البطولات", tro.map(t => `<div class="row"><span class="rt"><b>${nm(t.name)}</b><small>${esc((t.seasons || []).slice(0, 8).join("، "))}</small></span><span class="rv num">${t.won}</span></div>`).join(""), tro.reduce((a, t) => a + t.won, 0)) : "";
  const html = `<p class="crumbs"><a href="/db/">الموسوعة</a>${c.league_ar ? "، " + league : ""}</p><h1>${esc(name)}</h1>` +
    `<p class="season">${[c.country_ar && esc(c.country_ar), c.name && `<span class="lat">${esc(c.name)}</span>`].filter(Boolean).join(" · ")}</p><div class="sx">${intro}` +
    squad + (window ? `<section class="blk"><h2>انتقالات ${esc(ctx.season || "هالموسم")}</h2>${window}</section>` : "") +
    (rum.length ? `<section class="blk"><h2>إشاعات حوله</h2>${T.rumourList(rum, { pname, cname: ctx.cname })}</section>` : "") + titles +
    `<p class="src">اللاعبين والبطولات من FotMob، والانتقالات من سجل تيفو.</p></div>`;
  const ld = Object.assign({ "@context": "https://schema.org", "@type": "SportsTeam", name, sport: "Soccer", url: `${ctx.site}/db/club/${c.id}/` },
    c.name && c.name !== name ? { alternateName: c.name } : {}, v ? { location: { "@type": "Place", name: v.name } } : {});
  return { title: `${name}: اللاعبين والانتقالات والبطولات | تيفو`,
    desc: `${name}${c.country_ar ? " من " + c.country_ar : ""}${c.league_ar ? "، " + c.league_ar : ""}: قائمة اللاعبين، وانتقالات ${ctx.season || "الموسم"}، والبطولات.`, html, ld };
}

module.exports = { clubPage };
