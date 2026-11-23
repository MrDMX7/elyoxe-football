// An archive man's profile (/p/k<Tifo id>/, the archive job: site/archive/build.cjs) from graph/archive_export.persons:
// his facts, honours, every season of his career, his games in the archive, his moves, injuries and caps, in the current
// page's design (src/v5/ui.js). The owner, 22 Nov 2026: «بروفايلات لكل اللاعبين… تاريخ الكورة بكبره في تيفو».
"use strict";
const U = require("../src/v5/ui.js");

const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const AR = /[؀-ۿ]/;
const num = v => `<span class="num">${esc(v)}</span>`;
const txt = s => (AR.test(s || "") ? esc(s) : `<span class="lat">${esc(s || "")}</span>`);
const nameOf = p => (p.ar && AR.test(p.ar) ? p.ar : p.n) || "";
const FOOT = { left: "اليسرى", right: "اليمنى", both: "الاثنتين" };
const POS = { Goalkeeper: "حارس مرمى", Defender: "مدافع", Midfield: "وسط", Midfielder: "وسط", Attack: "مهاجم", Forward: "مهاجم", attack: "مهاجم",
  "Centre-Back": "قلب دفاع", "Left-Back": "ظهير أيسر", "Right-Back": "ظهير أيمن", "Defensive Midfield": "وسط دفاعي", "Central Midfield": "وسط",
  "Attacking Midfield": "وسط هجومي", "Left Winger": "جناح أيسر", "Right Winger": "جناح أيمن", "Centre-Forward": "رأس حربة", "Second Striker": "مهاجم ثاني" };
const COMP = { "Premier League": "الدوري الإنجليزي الممتاز", Championship: "دوري البطولة الإنجليزية", LaLiga: "الدوري الإسباني", "Serie A": "الدوري الإيطالي",
  Bundesliga: "الدوري الألماني", "Ligue 1": "الدوري الفرنسي", "UEFA Champions League": "دوري أبطال أوروبا", "Champions League": "دوري أبطال أوروبا",
  "Europa League": "الدوري الأوروبي", "UEFA Cup": "كأس الاتحاد الأوروبي", "FA Cup": "كأس الاتحاد الإنجليزي", "EFL Cup": "كأس الرابطة الإنجليزية",
  "Copa del Rey": "كأس ملك إسبانيا", "Coppa Italia": "كأس إيطاليا", "DFB-Pokal": "كأس ألمانيا", "Coupe de France": "كأس فرنسا", Eredivisie: "الدوري الهولندي",
  "Liga Portugal": "الدوري البرتغالي", "Süper Lig": "الدوري التركي", "Saudi Pro League": "دوري روشن السعودي", "Stars League": "دوري نجوم قطر",
  "UAE Pro League": "دوري أدنوك للمحترفين", "Libertadores": "كأس ليبرتادوريس", "Copa Libertadores": "كأس ليبرتادوريس", "World Cup": "كأس العالم" };
const INJ = { "unknown injury": "إصابة", concussion: "ارتجاج", "hamstring injury": "إصابة في العضلة الخلفية", "knee injury": "إصابة في الركبة",
  "ankle injury": "إصابة في الكاحل", "muscle injury": "إصابة عضلية", "groin injury": "إصابة في الفخذ", "calf injury": "إصابة في عضلة السمانة",
  "cruciate ligament rupture": "قطع في الرباط الصليبي", "thigh muscle strain": "شد في عضلة الفخذ", "back injury": "إصابة في الظهر", "foot injury": "إصابة في القدم",
  "Corona virus": "كورونا", "ill": "مرض", "flu": "إنفلونزا", "fracture": "كسر", "torn muscle fibre": "تمزق عضلي" };
const HON = { top_scorer: "الهداف", best_player: "أفضل لاعب", best_young: "أفضل لاعب شاب", best_goalkeeper: "أفضل حارس", best_local: "أفضل لاعب محلي" };

const comp = c => (c ? (COMP[c] ? esc(COMP[c]) : txt(c)) : "");
const club = (name, fm, o) => (!name ? '<span class="muted">—</span>' : fm && o.team && o.team(fm) ? `<a href="/t/${fm}/">${txt(name)}</a>` : txt(name));
const fee = v => (v == null ? "" : v >= 1e6 ? `${(v / 1e6).toFixed(v % 1e6 ? 1 : 0)} مليون €` : v >= 1e3 ? `${Math.round(v / 1e3)} ألف €` : `${v} €`);

function facts(p) {
  const f = [p.b && ["تاريخ الميلاد", U.dateAr(p.b)], p.d && ["توفي", U.dateAr(p.d)], p.bp && ["مكان الميلاد", txt(p.bp)],
    p.nat && ["الجنسية", txt(p.nat)], p.pos && ["المركز", POS[p.pos] ? esc(POS[p.pos]) : txt(p.pos)], p.h && ["الطول", `${num(p.h)} سم`],
    p.ft && ["القدم", esc(FOOT[p.ft] || p.ft)]].filter(Boolean);
  return f.length ? U.grp("", `<ul class="lc">${f.map(x => `<li><span class="muted">${x[0]}:</span> ${x[1]}</li>`).join("")}</ul>`) : "";
}

function honours(p, o) {
  const hs = (p.hon || []).filter(h => h[1] === 1);
  if (!hs.length) return "";
  return U.grp("ألقابه وجوائزه", hs.map(h => U.row({ t: h[0] === "winner" ? txt(h[2]) : `${esc(HON[h[0]] || h[0])} · ${comp(h[2])}`,
    sub: [h[4] && num(h[4]), h[5] && h[0] === "top_scorer" ? `${num(h[5])} هدف` : ""].filter(Boolean).join(" · "),
    href: h[3] && o.comp && o.comp(h[3]) ? `/c/${o.comp(h[3]).key}/` : null })).join(""));
}

function career(p, o) {
  const rows = p.car || [];
  if (!rows.length) return "";
  const td = v => `<td>${v == null ? "" : num(v)}</td>`;
  return U.grp("مسيرته موسم بموسم", `<div class="tblw"><table class="tbl"><thead><tr><th>الموسم</th><th class="tm">النادي</th><th>البطولة</th><th>مباريات</th><th>أهداف</th><th>صناعة</th><th>دقائق</th><th>إنذار</th><th>طرد</th></tr></thead><tbody>${
    rows.map(r => `<tr><td>${num(r[0])}</td><td>${club(r[2], r[3], o)}</td><td>${comp(r[1])}</td>${[r[4], r[5], r[6], r[7], r[8], r[9]].map(td).join("")}</tr>`).join("")}</tbody></table></div>`,
    { foot: "من سجلات Transfermarkt المفتوحة: كل موسم بكل بطولة لعب فيها." });
}

function archive(p, o) {
  const ms = p.ms || [];
  if (!ms.length) return "";
  const tot = ms.reduce((a, r) => [a[0] + r[3], a[1] + r[4]], [0, 0]);
  const by = U.grp(`مبارياته في أرشيف تيفو <span class="num">${tot[0]}</span>`, `<p class="note">${num(tot[0])} مباراة و${num(tot[1])} هدف في المباريات اللي يحفظها الأرشيف.</p>` +
    ms.slice().sort((a, b) => String(b[0]).localeCompare(String(a[0]))).map(r => U.row({ t: `${num(r[0])} · ${comp(r[2])}`, sub: `${num(r[3])} مباراة · ${num(r[4])} هدف`,
      href: r[1] && o.comp && o.comp(r[1]) ? `/c/${o.comp(r[1]).key}/s/${String(r[0]).replace(/\//g, "-")}/` : null })).join(""));
  const last = (p.last || []).map(m => U.row({ href: `/m/${m[0]}/`, t: `${txt(m[2])} ${num(`${m[6]}-${m[7]}`)} ${txt(m[4])}`, sub: U.dateAr(m[1]) })).join("");
  return by + (last ? U.grp("آخر مبارياته في الأرشيف", last) : "");
}

function moves(p, o) {
  const tr = p.tr || [];
  if (!tr.length) return "";
  const kind = t => (t === "loan" ? "إعارة" : t === "loan_end" ? "نهاية إعارة" : t === "retired" ? "اعتزل" : t === "without club" ? "بدون نادي" : t === "career break" ? "توقف" : "");
  return U.grp("انتقالاته", tr.map(t => U.row({ t: `${club(t[1], t[2], o)} ← ${t[6] === "retired" ? "اعتزل" : club(t[3], t[4], o)}`,
    sub: [U.dateAr(t[0]), kind(t[6]) && t[6] !== "retired" ? kind(t[6]) : "", fee(t[5])].filter(Boolean).join(" · ") })).join(""));
}

function injuries(p) {
  const inj = p.inj || [];
  if (!inj.length) return "";
  return U.grp(`إصاباته <span class="num">${inj.length}</span>`, inj.slice(0, 30).map(i => U.row({ t: INJ[i[1]] ? esc(INJ[i[1]]) : txt(i[1]),
    sub: [num(i[0]), i[4] && `${num(i[4])} يوم`, i[5] && `غاب ${num(i[5])} مباراة`].filter(Boolean).join(" · ") })).join(""), inj.length > 30 ? { foot: `وغيرها ${num(inj.length - 30)}.` } : {});
}

function caps(p) {
  const r = p.intl;
  if (!r) return "";
  return U.grp("مع المنتخب", `<p>${txt(r[0])}: ${num(r[1] || 0)} مباراة دولية و${num(r[2] || 0)} هدف${r[3] ? ` (${esc(r[3])})` : ""}.</p>`);
}

// a free photo (photos.build --archive: Wikidata/Commons, face-cropped, grey) beside the name, with its author and licence;
// the coach pages (lib/entity_view.cjs) use it too
const figure = ph => (ph ? `<div class="lt-x"><figure class="pph" style="--pc:#1B4A3F"><img src="${esc(ph.src)}" alt="" width="400" height="500"><figcaption><a href="${esc(ph.page || "")}" rel="noopener">${
  esc(((ph.artist || "").replace(/\s+/g, " ").trim().slice(0, 40)) + (ph.license ? " · " + ph.license : ""))}</a></figcaption></figure></div>` : "");
const header = (p, ph) => { const fig = figure(ph);
  return `<div class="lt${fig ? " lt-row" : ""}"><div><h1>${txt(nameOf(p))}</h1>${p.ar && p.n && p.ar !== p.n ? `<p class="muted"><span class="lat">${esc(p.n)}</span></p>` : ""}</div>${fig}</div>`; };

function body(p, o) {
  o = o || {};
  return header(p, o.photo) + facts(p) + honours(p, o) + career(p, o) + archive(p, o) + moves(p, o) + injuries(p) + caps(p);
}

// worth the search engines: a career of three seasons, twenty games in the archive, a title or award, or ten caps
const indexable = p => (p.car || []).length >= 3 || (p.ms || []).reduce((a, r) => a + r[3], 0) >= 20 || (p.hon || []).some(h => h[1] === 1) || ((p.intl || [])[1] || 0) >= 10;
const title = p => `${nameOf(p)}: مسيرته وأرقامه وانتقالاته | تيفو`;
const desc = p => `${nameOf(p)}${p.b ? `، مواليد ${p.b.slice(0, 4)}` : ""}: مسيرته موسم بموسم${(p.tr || []).length ? " وانتقالاته" : ""}${(p.inj || []).length ? " وإصاباته" : ""} ومبارياته في أرشيف تيفو.`;
const ld = (p, pth) => Object.assign({ "@context": "https://schema.org", "@type": "Person", name: nameOf(p), url: "https://tifo.elyoxe.com" + pth },
  p.n && p.n !== nameOf(p) ? { alternateName: p.n } : {}, p.b ? { birthDate: p.b } : {}, p.d ? { deathDate: p.d } : {}, p.bp ? { birthPlace: p.bp } : {},
  p.nat ? { nationality: p.nat } : {}, p.h ? { height: `${p.h} cm` } : {}, { jobTitle: "لاعب كرة قدم" });

module.exports = { body, header, indexable, title, desc, ld, nameOf };
