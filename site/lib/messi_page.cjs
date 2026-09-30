// The Messi museum (/messi/; owner 2026-09-30: «حول صفحته لمتحف ومتعة بصرية… اخترع وابدع», 41 items approved, all but
// 21). Everything that can be drawn at build time is prerendered here (numbers, tables, SVG pitches), so the rooms read
// without JavaScript and search engines see them; src/messi.js adds the 3D and the games on top.
// Sources (each room names its own): StatsBomb open data, FotMob, Transfermarkt datasets (CC0), Wikidata (CC0),
// martj42 international results (CC0). No number here is typed by hand.
"use strict";

const f1 = v => (Math.round(v * 10) / 10).toFixed(1);
const pct = (a, b) => b ? Math.round(a / b * 100) : 0;
const num = v => `<span class="num">${v}</span>`;

// ---- pitches. Half: the goal at the top, StatsBomb x 60..120 -> SVG y 60..0, y 0..80 -> SVG x 0..80
const HX = (x, y) => [+(y).toFixed(1), +(120 - x).toFixed(1)];
function half(inner, cls){
  return `<svg class="mp ${cls || ""}" viewBox="-1 -3 82 64" role="img" aria-hidden="true"><rect x="0" y="0" width="80" height="60" class="g"/>` +
    '<path class="l" d="M0 0H80M18 0V18H62V0M30 0V6H50V0M34 60A10 10 0 0 1 46 60"/><path class="l" d="M31.6 18A10 10 0 0 0 48.4 18"/>' +
    '<circle cx="40" cy="12" r=".5" class="d"/><path class="gl" d="M36 0V-2H44V0"/>' + inner + "</svg>";
}
// Full: attacking to the left (the page reads right to left), StatsBomb x 0..120 -> SVG x 120..0
const FX = (x, y) => [+(120 - x).toFixed(1), +(y).toFixed(1)];
function full(inner, cls){
  return `<svg class="mp ${cls || ""}" viewBox="-1 -1 122 82" role="img" aria-hidden="true"><rect x="0" y="0" width="120" height="80" class="g"/>` +
    '<path class="l" d="M60 0V80M0 18H18V62H0M120 18H102V62H120M0 30H6V50H0M120 30H114V50H120"/><circle cx="60" cy="40" r="10" class="l"/>' + inner + "</svg>";
}

module.exports = function messiMuseum(D, H){
  const { esc, ar, eur, clubCell, ASSET_V } = H;
  const shots = D.shots, play = D.play || {}, M = (D.matches || {}).matches || [], X = D.extra || {};
  const goals = [], allShots = [];
  shots.matches.forEach(m => m.shots.forEach(s => { const r = Object.assign({ date:m.date, season:m.season, opp:m.opp, team:m.team, comp:m.comp, home:m.home, score:m.score }, s); allShots.push(r); if (s.goal) goals.push(r); }));
  const np = goals.filter(g => g.kind !== "Penalty");
  const car = X.career || null, tot = car && car.total;
  const secs = [], room = (id, no, title, lead, body, src) => secs.push({ id, no, title,
    html:`<section class="room" id="${id}" aria-labelledby="${id}-h"><header class="plaque"><span class="rno">القاعة ${no}</span><h2 id="${id}-h">${title}</h2>${lead ? `<p>${lead}</p>` : ""}</header>${body}${src ? `<p class="src">${src}</p>` : ""}</section>` });

  // ================= 0. the entrance
  const heroArcs = goals.map(g => { const [a, b] = HX(g.x, g.y), [c] = HX(120, Math.min(43.8, Math.max(36.2, g.ey == null ? 40 : g.ey))); return `<path d="M${a} ${b}Q${((a + c) / 2).toFixed(1)} ${(b / 2 - 4).toFixed(1)} ${c} 0" class="${g.body}"/>`; }).join("");
  const now = D.now || {};
  const entrance = `<div class="mentry"><svg class="harcs" viewBox="-1 -6 82 66" aria-hidden="true">${heroArcs}</svg>
<div class="mcount"><b class="num" data-count="${tot ? tot.goals : goals.length}">${tot ? tot.goals : goals.length}</b><span>هدف في مسيرته${tot ? ` مع الأندية والأرجنتين، في ${num(tot.apps)} مباراة، ومعها ${num(tot.assists)} تمريرة حاسمة` : ""}</span></div>
${car ? `<ul class="mteams">${car.teams.filter(t => t.kind !== "youth" && t.apps && !/U\d\d/.test(t.team)).map(t => `<li><b>${esc(ar(t.team))}</b> ${num(t.goals || 0)} هدف · ${num(t.apps)} مباراة</li>`).join("")}</ul>` : ""}
${now.next || now.last ? `<div class="mnow" id="mnow"><h3>ميسي الحين</h3>${now.last ? `<p>آخر مباراة: ${now.last}</p>` : ""}${now.next ? `<p>الياية: ${now.next}</p>` : ""}${now.season ? `<p>${now.season}</p>` : ""}</div>` : ""}</div>
<p class="small muted">العدد الكلي من FotMob ويتحدّث كل أسبوع. الخطوط الذهبية فوق: ${num(goals.length)} هدف عندنا مكانها بالضبط من StatsBomb، وهي اللي ترسمها قاعات الملعب.</p>`;

  // ================= 1. goals
  const byKind = k => goals.filter(g => g.kind === k).length;
  const left = goals.filter(g => g.body === "L").length, right = goals.filter(g => g.body === "R").length, head = goals.filter(g => g.body === "H").length;
  const outBox = goals.filter(g => g.x < 102 || g.y < 18 || g.y > 62).length;
  const r3d = `<div class="m3d-ctl" role="group" aria-label="زاوية الشوف"><button type="button" class="sa" data-v="behind" aria-pressed="true">من ورا</button><button type="button" class="sa" data-v="above" aria-pressed="false">من فوق</button><button type="button" class="sa" data-v="goal" aria-pressed="false">من داخل المرمى</button><button type="button" class="sa" id="m3dplay">شغّل مسيرته من البداية</button></div>
<div class="m3d-ctl" role="group" aria-label="أي أهداف"><button type="button" class="sa" data-f="all" aria-pressed="true">الكل ${num(goals.length)}</button><button type="button" class="sa" data-f="L" aria-pressed="false">اليسار ${num(left)}</button><button type="button" class="sa" data-f="R" aria-pressed="false">اليمين ${num(right)}</button><button type="button" class="sa" data-f="H" aria-pressed="false">الراس ${num(head)}</button><button type="button" class="sa" data-f="Free Kick" aria-pressed="false">ضربات حرة ${num(byKind("Free Kick"))}</button><button type="button" class="sa" data-f="Penalty" aria-pressed="false">جزاء ${num(byKind("Penalty"))}</button><label class="small"><input type="checkbox" id="m3dmiss" checked> التسديدات اللي ما دخلت</label></div>
<div id="m3dc" class="m3dc" data-src="/assets/messi3d.${ASSET_V}.js" data-json="/v1/legends/messi/shots.json" data-opp='${esc(JSON.stringify(Object.fromEntries([...new Set(goals.map(g => g.opp))].map(o => [o, ar(o)]).filter(x => x[1] !== x[0]))))}'><p class="empty">نحمّل الملعب…</p></div>
<input type="range" id="m3dr" min="0" max="${goals.length}" value="0" aria-label="لين أي هدف" dir="ltr"><p class="small" id="m3ds" aria-live="polite"></p>
<p>${num(left)} من أهدافه برجله اليسار، و${num(outBox)} من برا منطقة الجزاء، و${num(byKind("Penalty"))} من ضربات جزاء.</p>`;
  room("r-goals", 1, "من وين يسجل، ووين تروح الكورة", "كل خط هدف: يطلع من مكان التسديدة وينزل في النقطة اللي عبرت فيها الكورة خط المرمى، بارتفاعها. الذهبي اليسار، الأبيض اليمين، الأخضر الراس.", r3d, "البيانات: StatsBomb (بيانات مفتوحة).");

  // 5. free kicks: prerendered view from behind the wall is the 3D filter; here the list
  const fk = goals.filter(g => g.kind === "Free Kick");
  room("r-fk", 2, "معرض الضربات الحرة", `${num(fk.length)} ضربة حرة سجلها. اختر «ضربات حرة» في الملعب فوق وشوفها من ورا: الكورة تطلع فوق الحائط وتنزل تحت العارضة.`,
    half(fk.map(g => { const [a, b] = HX(g.x, g.y), [c] = HX(120, Math.min(43.8, Math.max(36.2, g.ey || 40))); return `<path d="M${a} ${b}Q${((a + c) / 2).toFixed(1)} ${(b / 2 - 3).toFixed(1)} ${c} 0" class="arc L"/><circle cx="${a}" cy="${b}" r=".7" class="pt"/>`; }).join(""), "fk") +
    `<ul class="mlist">${fk.slice().reverse().slice(0, 12).map(g => `<li>${num(g.season)} · ضد ${esc(ar(g.opp))} · من ${num(Math.round(Math.hypot(120 - g.x, 40 - g.y) * 0.9144))} متر</li>`).join("")}</ul>`, "البيانات: StatsBomb.");

  // 6. signature: the strike zone (8x8 yard cells) x the side of the goal it went in
  const side = g => { const near = g.y > 40 ? (g.ey > 41.3) : (g.ey < 38.7), far = g.y > 40 ? (g.ey < 38.7) : (g.ey > 41.3); return Math.abs(g.y - 40) < 4 ? "center" : near ? "near" : far ? "far" : "middle"; };
  // from 14 yards out and off the centre line: the tap-ins in front of goal outnumber everything and say nothing about him
  const sig = {}; np.filter(g => Math.hypot(120 - g.x, 40 - g.y) >= 14 && side(g) !== "center").forEach(g => { const k = `${Math.floor(g.x / 8)}|${Math.floor(g.y / 8)}|${side(g)}`; (sig[k] = sig[k] || []).push(g); });
  const tops = Object.values(sig).filter(v => v.length >= 5).sort((a, b) => b.length - a.length).slice(0, 3);
  const SIDE = { far:"للقائم البعيد", near:"للقائم القريب", middle:"لنص المرمى", center:"من قدام المرمى" };
  room("r-sig", 3, "توقيعه", "أهداف من نفس المربع ولنفس الجهة من المرمى، مكررة عبر السنين. هذي الحركة اللي يعرفها كل مدافع ويعجز عنها.",
    `<div class="mrow">${tops.map(v => { const ys = v.map(g => +g.season.slice(0, 4)); return `<figure>${half(v.map(g => { const [a, b] = HX(g.x, g.y), [c] = HX(120, Math.min(43.8, Math.max(36.2, g.ey || 40))); return `<path d="M${a} ${b}L${c} 0" class="arc L"/>`; }).join(""), "sm")}<figcaption>${num(v.length)} هدف ${SIDE[side(v[0])]}، من ${num(Math.min(...ys))} لين ${num(Math.max(...ys) + 1)}</figcaption></figure>`; }).join("")}</div>`, "البيانات: StatsBomb، بدون ضربات الجزاء.");

  // 7. eras
  const ERAS = [["برشلونة الشاب", g => g.team === "Barcelona" && g.season < "2009"], ["القمة", g => g.team === "Barcelona" && g.season >= "2009" && g.season < "2015"], ["برشلونة الأخير", g => g.team === "Barcelona" && g.season >= "2015"], ["باريس", g => g.team === "Paris Saint-Germain"], ["الأرجنتين", g => g.team === "Argentina"], ["ميامي", g => g.team === "Inter Miami"]];
  room("r-eras", 4, "حقب مسيرته", "نفس اللاعب، ست خرائط. شوف كيف قرّب من المرمى في القمة، وكيف رجع يسدد من أبعد في آخر برشلونة.",
    `<div class="mrow">${ERAS.map(([t, fn]) => { const v = np.filter(fn); if (v.length < 8) return ""; const d = v.reduce((a, g) => a + Math.hypot(120 - g.x, 40 - g.y), 0) / v.length * 0.9144; return `<figure>${half(v.map(g => { const [a, b] = HX(g.x, g.y); return `<circle cx="${a}" cy="${b}" r=".9" class="pt ${g.body}"/>`; }).join(""), "sm")}<figcaption><b>${t}</b> · ${num(v.length)} هدف · معدل ${num(f1(d))} متر</figcaption></figure>`; }).join("")}</div>`, "البيانات: StatsBomb، بدون ضربات الجزاء.");

  // 8. the hardest ten (lowest xG, no penalties): clicking one replays it in the 3D pitch
  const hard = np.slice().sort((a, b) => a.xg - b.xg).slice(0, 10);
  room("r-hard", 5, "أصعب 10 أهداف", "أقل احتمال تسجيل حسب StatsBomb: لاعب عادي من نفس المكان وبنفس الطريقة يسجلها أقل من مرة في كل عشرين محاولة. اضغط أي هدف ويعيده لك الملعب فوق.",
    `<ol class="mlist hard">${hard.map(g => `<li><button type="button" class="lnk" data-goal="${goals.indexOf(g)}">${num(g.season)} ضد ${esc(ar(g.opp))}، الدقيقة ${num(g.min)}</button> · احتمال ${num(Math.round(g.xg * 100))}٪ · ${g.body === "L" ? "باليسار" : g.body === "R" ? "باليمين" : "بالراس"} · ${num(Math.round(Math.hypot(120 - g.x, 40 - g.y) * 0.9144))} متر</li>`).join("")}</ol>`, "البيانات: StatsBomb (xG).");

  // 9. goals vs xG by season (SVG lines)
  const bySeason = {}; shots.matches.forEach(m => { const k = m.season; const r = bySeason[k] = bySeason[k] || { g:0, xg:0, sh:0 }; m.shots.forEach(s => { r.sh++; r.xg += s.xg; if (s.goal) r.g++; }); });
  const ss = Object.keys(bySeason).sort(), W = 300, Hh = 120, mx = Math.max(...ss.map(k => Math.max(bySeason[k].g, bySeason[k].xg)));
  const pxs = i => 10 + i * (W - 20) / Math.max(1, ss.length - 1), py = v => Hh - 10 - v / mx * (Hh - 25);
  const line = key => ss.map((k, i) => `${i ? "L" : "M"}${pxs(i).toFixed(1)} ${py(bySeason[k][key]).toFixed(1)}`).join("");
  const over = ss.reduce((a, k) => a + bySeason[k].g - bySeason[k].xg, 0);
  room("r-xg", 6, "فوق المتوقع", `الخط الذهبي أهدافه، والأبيض المتقطع كم كان المفروض يسجل لاعب عادي من نفس التسديدات. سجّل ${num(Math.round(over))} هدف زيادة على المتوقع في هالمباريات.`,
    `<svg class="chart" viewBox="0 0 ${W} ${Hh}" role="img" aria-label="الأهداف مقابل المتوقع موسم بموسم"><path d="${line("xg")}" class="xgl"/><path d="${line("g")}" class="gl2"/>${ss.map((k, i) => i % 3 === 0 ? `<text x="${pxs(i).toFixed(1)}" y="${Hh - 1}" class="ax">${k.slice(2, 4)}</text>` : "").join("")}</svg>
<table class="tbl"><thead><tr><th>الموسم</th><th>أهداف</th><th>المتوقع</th><th>الفرق</th></tr></thead><tbody>${ss.map(k => `<tr><td class="num">${esc(k)}</td><td class="num">${bySeason[k].g}</td><td class="num">${f1(bySeason[k].xg)}</td><td class="num"><bdi dir="ltr">${bySeason[k].g - bySeason[k].xg >= 0 ? "+" : ""}${f1(bySeason[k].g - bySeason[k].xg)}</bdi></td></tr>`).join("")}</tbody></table>`, "البيانات: StatsBomb.");

  // 10. the clock
  const bins = new Array(19).fill(0); goals.forEach(g => { bins[g.min >= 90 ? 18 : Math.floor(g.min / 5)]++; });
  const bmax = Math.max(...bins), cx = 60, cy = 60;
  const clock = bins.map((n, i) => { const a0 = (i / 19) * 2 * Math.PI - Math.PI / 2, a1 = ((i + 0.85) / 19) * 2 * Math.PI - Math.PI / 2, r = 18 + n / bmax * 38;
    const p = (a, rr) => `${(cx + rr * Math.cos(a)).toFixed(1)} ${(cy + rr * Math.sin(a)).toFixed(1)}`; return `<path d="M${p(a0, 16)}L${p(a0, r)}A${r} ${r} 0 0 1 ${p(a1, r)}L${p(a1, 16)}Z" class="${i === 18 ? "cb hot" : "cb"}"><title>${i === 18 ? "90+" : i * 5 + "-" + (i * 5 + 5)}: ${n}</title></path>`; }).join("");
  const peak = bins.indexOf(bmax);
  room("r-clock", 7, "ساعة المباراة", `متى يسجل: كل قطعة خمس دقايق، وطولها عدد أهدافه فيها. أكثر فترة: ${peak === 18 ? "الوقت بدل الضايع" : `من الدقيقة ${num(peak * 5)} لين ${num(peak * 5 + 5)}`} (${num(bmax)} هدف).`,
    `<svg class="clock" viewBox="-8 -8 136 136" role="img" aria-label="توزيع أهدافه على دقايق المباراة">${clock}${[0, 15, 30, 45, 60, 75, 90].map(m => { const a = (m / 5 / 19) * 2 * Math.PI - Math.PI / 2; return `<text x="${(60 + 64 * Math.cos(a)).toFixed(1)}" y="${(62 + 64 * Math.sin(a)).toFixed(1)}" class="c1">${m === 90 ? "90+" : m}</text>`; }).join("")}<text x="60" y="62" class="c2">الدقيقة</text></svg>`, "البيانات: StatsBomb.");

  // 11. victims (clubs), 12. hat-tricks, 13. the rare goals
  const vic = {}; goals.forEach(g => { vic[g.opp] = (vic[g.opp] || 0) + 1; }); const vt = Object.entries(vic).sort((a, b) => b[1] - a[1]).slice(0, 12), vmax = vt[0] ? vt[0][1] : 1;
  room("r-vic", 8, "ضحاياه", "الفرق اللي سجل عليها أكثر شي.", `<ul class="bars">${vt.map(([o, n]) => `<li><span>${esc(ar(o))}</span><i style="--w:${pct(n, vmax)}%"></i><b class="num">${n}</b></li>`).join("")}</ul>`, "البيانات: StatsBomb.");
  const hat = shots.matches.map(m => ({ m, g:m.shots.filter(s => s.goal).length })).filter(x => x.g >= 3).sort((a, b) => b.g - a.g || a.m.date.localeCompare(b.m.date));
  room("r-hat", 9, "الهاتريكات", `${num(hat.length)} مباراة سجل فيها ثلاثة أو أكثر.`, `<ul class="mlist cols">${hat.map(x => `<li>${num(x.m.date)} · ضد ${esc(ar(x.m.opp))} · <b class="num">${x.g}</b></li>`).join("")}</ul>`, "البيانات: StatsBomb.");
  const rare = goals.filter(g => g.body !== "L" && g.kind !== "Penalty");
  room("r-rare", 10, "النادر", `${num(right)} هدف برجله اليمين و${num(head)} براسه. اختر «اليمين» أو «الراس» في الملعب وشوفها لحالها.`,
    half(rare.map(g => { const [a, b] = HX(g.x, g.y); return `<circle cx="${a}" cy="${b}" r="1" class="pt ${g.body}"/>`; }).join(""), "sm"), "البيانات: StatsBomb.");

  // ================= 3. the creator
  const A = play.assists || [];
  const recv = {}; A.forEach(a => { if (a.to) recv[a.to] = (recv[a.to] || 0) + 1; }); const rt = Object.entries(recv).sort((a, b) => b[1] - a[1]).slice(0, 8);
  room("r-ast", 11, "تمريراته الحاسمة", `${num(A.length)} تمريرة حاسمة: الخط من مكان التمريرة لمكان اللي سجل. تشوف إنه يصنع من الجهة اليمين ومن قدام المنطقة.`,
    full(A.map(a => { const [x1, y1] = FX(a.x, a.y), [x2, y2] = FX(a.ex, a.ey); return `<path d="M${x1} ${y1}L${x2} ${y2}" class="as"/><circle cx="${x2}" cy="${y2}" r=".8" class="pt L"/>`; }).join(""), "wide") +
    `<p class="small">أكثر من صنع لهم: ${rt.map(([n, c]) => `${esc(ar(n))} (${num(c)})`).join("، ")}</p>`, "البيانات: StatsBomb.");
  const L = (play.links || []).slice(0, 10), lmax = L.length ? Math.max(...L.map(x => x[1] + x[2])) : 1;
  const net = L.map((x, i) => { const a = i / L.length * 2 * Math.PI - Math.PI / 2, px = 60 + 44 * Math.cos(a), py = 60 + 44 * Math.sin(a), w = 0.6 + (x[1] + x[2]) / lmax * 5;
    return `<line x1="60" y1="60" x2="${px.toFixed(1)}" y2="${py.toFixed(1)}" style="stroke-width:${w.toFixed(2)}" class="nl"/><circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="2.2" class="nn"/><text x="${px.toFixed(1)}" y="${(py + (py > 60 ? 6 : -3.5)).toFixed(1)}" class="nt">${esc(ar(x[0]))}</text>`; }).join("");
  room("r-net", 12, "الشراكات", "كل خط زميل، وسمكه عدد التمريرات بينهم. بوسكيتس وألفيش وتشافي وإنييستا: الكورة كانت تمر فيهم قبل ما توصله.",
    `<svg class="net" viewBox="0 0 120 120" role="img" aria-label="شبكة تمريراته مع زملائه">${net}<circle cx="60" cy="60" r="5" class="nm"/><text x="60" y="61.5" class="nmt">ميسي</text></svg>
<table class="tbl"><thead><tr><th>الزميل</th><th>من ميسي له</th><th>منه لميسي</th></tr></thead><tbody>${L.map(x => `<tr><td>${esc(ar(x[0]))}</td><td class="num">${x[1]}</td><td class="num">${x[2]}</td></tr>`).join("")}</tbody></table>`, "البيانات: StatsBomb، التمريرات الناجحة في المباريات اللي لعبها.");
  const grid = {}; (play.drib || []).forEach(d => { const k = Math.min(11, Math.floor(d[0] / 10)) + "|" + Math.min(7, Math.floor(d[1] / 10)); grid[k] = (grid[k] || 0) + 1; }); const gmax = Math.max(1, ...Object.values(grid));
  room("r-drib", 13, "خريطة المراوغات", `${num(play.drib_ok || 0)} مراوغة ناجحة من ${num(play.drib_try || 0)} (${num(pct(play.drib_ok, play.drib_try))}٪). المربع الأغمق وين يتخطى أكثر.`,
    full(Object.entries(grid).map(([k, n]) => { const [i, j] = k.split("|").map(Number); const [x] = FX(i * 10 + 10, 0); return `<rect x="${x}" y="${j * 10}" width="10" height="10" class="hm" style="opacity:${(0.08 + n / gmax * 0.85).toFixed(2)}"><title>${n}</title></rect>`; }).join(""), "wide"), "البيانات: StatsBomb.");
  // his carries as a flow: from each 10x10-yard cell, the average way he took the ball (arrow length) and how often (width)
  const flow = {}; Object.values(play.carries || {}).forEach(v => v.forEach(c => { const k = Math.min(11, Math.floor(c[0] / 10)) + "|" + Math.min(7, Math.floor(c[1] / 10)); const f = flow[k] = flow[k] || { n:0, dx:0, dy:0 }; f.n++; f.dx += c[2] - c[0]; f.dy += c[3] - c[1]; }));
  const fmax = Math.max(1, ...Object.values(flow).map(f => f.n));
  const arrows = Object.entries(flow).filter(([, f]) => f.n >= 4).map(([k, f]) => { const [i, j] = k.split("|").map(Number), cx0 = i * 10 + 5, cy0 = j * 10 + 5, ux = f.dx / f.n, uy = f.dy / f.n, len = Math.hypot(ux, uy) || 1, L = Math.min(9, len * 0.6);
    const [x1, y1] = FX(cx0 - ux / len * L / 2, cy0 - uy / len * L / 2), [x2, y2] = FX(cx0 + ux / len * L / 2, cy0 + uy / len * L / 2), w = 0.3 + f.n / fmax * 2.2;
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="fl" style="stroke-width:${w.toFixed(2)}" marker-end="url(#mah)"><title>${f.n}</title></line>`; }).join("");
  const nCar = Object.values(flow).reduce((a, f) => a + f.n, 0);
  room("r-carry", 14, "ميسي يمشي بالكورة", `${num(nCar)} ركضة بالكورة تقدّم فيها عشر ياردات أو دخل المنطقة. كل سهم: من هالمنطقة وين ياخذ الكورة عادةً، وسمكه كم مرة. تشوف الركض من اليمين للعمق، مب على الخط.`,
    full(`<defs><marker id="mah" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="3" markerHeight="3" orient="auto"><path d="M0 0L6 3L0 6Z" class="fh"/></marker></defs>` + arrows, "wide"), "البيانات: StatsBomb.");
  room("r-layers", 15, "كيف تغيّر مركزه", "الذروة الثانية: كل موسم طبقة من لمساته فوق الموسم اللي قبله، والزمن هو الارتفاع. من الجناح اليمين، للمهاجم الوهمي، لصانع اللعب. لفّ الطبقات بإصبعك.",
    `<div id="m3dl" class="m3dc" data-src="/assets/messi3d.${ASSET_V}.js" data-json="/v1/legends/messi/play.json"><p class="empty">نحمّل الطبقات…</p></div><p class="legend small"><i style="--c:#9FB8AE"></i>برشلونة لين 2009 <i style="--c:#F0BC5A"></i>القمة 2009-2015 <i style="--c:#E58A3A"></i>برشلونة 2015-2021 <i style="--c:#6FA3E0"></i>باريس <i style="--c:#8EC9EE"></i>الأرجنتين <i style="--c:#F5A3C7"></i>ميامي · تحت أول موسم، وفوق آخر موسم.</p>`, "البيانات: StatsBomb، كل لمسة سجّلها له.");

  // ================= 4. titles and records
  const TR = X.trophies || [], byTeam = {}; TR.forEach(t => { (byTeam[t.team] = byTeam[t.team] || []).push(t); });
  room("r-cab", 16, "خزانة الألقاب", `${num(TR.length)} لقب حسب ويكي داتا.`, Object.entries(byTeam).map(([tm, v]) => `<h3>${esc(tm)} · ${num(v.length)}</h3><ul class="cab">${v.map(t => `<li><b>${esc((t.name_ar || t.name).replace(/\s*\d{4}([–-]\d{2,4})?\s*/g, " ").trim())}</b><span class="num">${esc((t.name.match(/\d{4}([–-]\d{2,4})?/) || [""])[0])}</span></li>`).join("")}</ul>`).join(""), "المصدر: ويكي داتا (الفائز بكل نسخة). ممكن تنقصها بطولات ما سجّلها أحد هناك.");
  const bdo = (X.awards || []).filter(a => /Ballon d'Or$/.test(a.name) && a.year).map(a => a.year).sort();
  room("r-bdo", 17, "الكرات الذهبية", `${num(bdo.length)} كرات ذهبية.`, `<ol class="bdo">${bdo.map(y => `<li><span class="ball" aria-hidden="true"></span><b class="num">${y}</b></li>`).join("")}</ol>
<details><summary>كل جوائزه الفردية (${num((X.awards || []).length)})</summary><ul class="mlist cols">${(X.awards || []).filter(a => a.year).map(a => `<li>${num(a.year)} · ${esc(a.name_ar || a.name)}</li>`).join("")}</ul></details>`, "المصدر: ويكي داتا.");
  const LG = X.legends || {}, LN = { messi:"ميسي", pele:"بيليه", maradona:"مارادونا" };
  room("r-leg", 18, "مع الأساطير", "مع منتخب بلاده: المباريات والأهداف ومعدل التسجيل، كلهم من نفس المصدر.",
    `<table class="tbl"><thead><tr><th></th><th>مباريات</th><th>أهداف</th><th>هدف كل مباراة</th></tr></thead><tbody>${["messi", "pele", "maradona"].filter(k => LG[k]).map(k => `<tr${k === "messi" ? ' class="mine"' : ""}><td>${LN[k]}</td><td class="num">${LG[k].apps}</td><td class="num">${LG[k].goals}</td><td class="num">${LG[k].apps ? (LG[k].goals / LG[k].apps).toFixed(2) : "—"}</td></tr>`).join("")}</tbody></table>`, "المصدر: ويكي داتا.");
  const co = {}; M.forEach(m => { if (!m.coach) return; const r = co[m.coach] = co[m.coach] || { n:0, g:0, a:0, min:0 }; r.n++; r.g += m.g; r.a += m.a; r.min += m.min || 0; });
  const cot = Object.entries(co).filter(x => x[1].n >= 5).sort((a, b) => b[1].n - a[1].n);
  room("r-coach", 19, "مع كل مدرب", "في مبارياته اللي عندنا من StatsBomb.", `<table class="tbl"><thead><tr><th>المدرب</th><th>مباريات</th><th>أهداف</th><th>صناعة</th><th>كل 90 دقيقة</th></tr></thead><tbody>${cot.map(([n, r]) => `<tr><td>${esc(ar(n))}</td><td class="num">${r.n}</td><td class="num">${r.g}</td><td class="num">${r.a}</td><td class="num">${r.min ? ((r.g + r.a) / r.min * 90).toFixed(2) : "—"}</td></tr>`).join("")}</tbody></table>`, "البيانات: StatsBomb.");
  room("r-mates", 20, "أكثر من لعب معهم", "كم مرة بدا معه أساسي.", `<ul class="bars">${(play.costarts || []).slice(0, 12).map(([n, c]) => `<li><span>${esc(ar(n))}</span><i style="--w:${pct(c, (play.costarts[0] || [0, 1])[1])}%"></i><b class="num">${c}</b></li>`).join("")}</ul>`, "البيانات: StatsBomb.");

  // ================= 5. Argentina
  const I = X.intl || [], byCountry = {}; I.forEach(g => { if (g.country) byCountry[g.country] = (byCountry[g.country] || 0) + 1; });
  room("r-map", 21, "وين سجل للأرجنتين", `${num(I.length)} هدف دولي معروف مكانه: كل دايرة بلد لعب فيه، وحجمها عدد أهدافه هناك.`,
    `<div id="mmap" data-c='${esc(JSON.stringify(byCountry))}'><ul class="mlist cols">${Object.entries(byCountry).sort((a, b) => b[1] - a[1]).map(([c, n]) => `<li>${esc(ar(c))} ${num(n)}</li>`).join("")}</ul></div>`, `المصدر: martj42 (البطولات والتصفيات؛ الودية ناقصة، فالعدد أقل من ${tot ? "أهدافه الـ" + (car.teams.find(t => t.kind === "national team" && /Argentina$/.test(t.team)) || {}).goals : "مجموعه"} الدولية).`);
  const WC = M.filter(m => m.comp === 43 && m.season === "2022");
  const wcG = goals.filter(g => g.comp === 43 && g.season === "2022");
  room("r-qatar", 22, "رحلة قطر 2022", "مباراة بمباراة لين الكأس.", `<table class="tbl"><thead><tr><th>الدور</th><th>ضد</th><th>النتيجة</th><th>أهداف</th><th>صناعة</th><th>تسديدات</th><th>مراوغات</th></tr></thead><tbody>${WC.map(m => `<tr><td>${esc(({ "Group Stage":"المجموعات", "Round of 16":"دور الـ16", "Quarter-finals":"ربع النهائي", "Semi-finals":"نصف النهائي", "Final":"النهائي" })[m.stage] || m.stage || "")}</td><td>${esc(ar(m.opp))}</td><td class="num"><bdi dir="ltr">${m.home ? m.score[0] + "-" + m.score[1] : m.score[1] + "-" + m.score[0]}</bdi></td><td class="num">${m.g}</td><td class="num">${m.a}</td><td class="num">${m.sh}</td><td class="num">${m.dr}</td></tr>`).join("")}</tbody></table>` +
    half(wcG.map(g => { const [a, b] = HX(g.x, g.y), [c] = HX(120, Math.min(43.8, Math.max(36.2, g.ey || 40))); return `<path d="M${a} ${b}L${c} 0" class="arc L"/><circle cx="${a}" cy="${b}" r="1" class="pt ${g.body}"/>`; }).join(""), "sm"), "البيانات: StatsBomb. النتيجة بعد الوقت الإضافي، بدون ضربات الترجيح.");
  const copa = y => I.filter(g => g.date.startsWith(y) && /Copa Am/.test(g.tournament || ""));
  room("r-copa", 23, "كوبا أمريكا 2021 و2024", "أول لقب كبير مع الأرجنتين، وبعده الثاني.", ["2021", "2024"].map(y => `<h3>${y}</h3><ul class="mlist">${copa(y).map(g => `<li>${num(g.date)} · ضد ${esc(ar(g.opp))} · الدقيقة ${num(g.min)}${g.pen ? " · جزاء" : ""}</li>`).join("") || '<li class="muted">ما في أهداف مسجّلة له في هالنسخة بالمصدر.</li>'}</ul>`).join(""), "المصدر: martj42.");
  const nv = {}; I.forEach(g => { nv[g.opp] = (nv[g.opp] || 0) + 1; }); const nvt = Object.entries(nv).sort((a, b) => b[1] - a[1]);
  room("r-natv", 24, "المنتخبات اللي سجل عليها", `${num(nvt.length)} منتخب.`, `<ul class="mlist cols">${nvt.map(([o, n]) => `<li>${esc(ar(o))} ${num(n)}</li>`).join("")}</ul>`, "المصدر: martj42.");

  // ================= 6. the career
  const ct = car ? car.teams.filter(t => t.apps && t.kind !== "youth" && !/U\d\d/.test(t.team)) : [], y0 = 2004, y1 = new Date().getFullYear() + 1;
  const tx = y => ((y - y0) / (y1 - y0) * 100).toFixed(2);
  room("r-time", 25, "المسيرة", "من روساريو لبرشلونة لباريس لميامي، ومع الأرجنتين طول الطريق.",
    `<div class="tline">${ct.map(t => { const a = +(t.from || "").slice(0, 4) + ((+(t.from || "").slice(5, 7) || 1) - 1) / 12, b = t.to ? +t.to.slice(0, 4) + (+t.to.slice(5, 7) - 1) / 12 : y1; return `<div class="tl ${t.kind === "national team" ? "nat" : ""}" style="--a:${tx(a)}%;--b:${tx(b)}%"><b>${esc(ar(t.team))}</b><span>${num(t.apps)} مباراة · ${num(t.goals || 0)} هدف · ${num(t.assists || 0)} صناعة</span></div>`; }).join("")}<div class="ty"><span class="num">${y0}</span><span class="num">${y1 - 1}</span></div></div>`, "المصدر: FotMob.");
  const V = X.value || [], vmx = Math.max(1, ...V.map(v => v[1])), t0 = V.length ? Date.parse(V[0][0]) : 0, t1 = V.length ? Date.parse(V[V.length - 1][0]) : 1;
  const vx = d => (10 + (Date.parse(d) - t0) / (t1 - t0) * 280).toFixed(1), vy = v => (110 - v / vmx * 95).toFixed(1), vtop = V.reduce((a, v) => v[1] > a[1] ? v : a, V[0] || ["", 0]);
  room("r-value", 26, "قيمته السوقية", V.length ? `أعلى قيمة: ${eur(vtop[1])} في ${num(vtop[0].slice(0, 4))}.` : "",
    V.length ? `<svg class="chart" viewBox="0 0 300 120" role="img" aria-label="قيمته السوقية عبر السنين"><path d="${V.map((v, i) => `${i ? "L" : "M"}${vx(v[0])} ${vy(v[1])}`).join("")}" class="gl2"/>${V.filter((v, i) => i % 8 === 0).map(v => `<text x="${vx(v[0])}" y="119" class="ax">${v[0].slice(2, 4)}</text>`).join("")}</svg>` : "", "المصدر: Transfermarkt (transfermarkt-datasets).");
  room("r-moves", 27, "انتقالاته", "", D.transfersHtml || "", "المصدر: Transfermarkt.");

  // ================= 7. play with Messi (the games are wired by src/messi.js; their data is embedded once)
  const game = goals.filter(g => g.kind !== "Penalty" && g.ey != null && g.ez != null).map(g => [g.x, g.y, +(g.ey).toFixed(1), +(g.ez).toFixed(1), g.season, g.opp, g.min]);
  const quiz = [];
  if (vt.length >= 4) quiz.push({ q:"ضد أي فريق سجل ميسي أكثر شي (في بيانات StatsBomb)؟", a:[vt[0][0], vt[1][0], vt[2][0], vt[3][0]].map(ar), c:0 });
  if (rt.length >= 4) quiz.push({ q:"مين أكثر لاعب صنع له ميسي أهداف؟", a:[rt[0][0], rt[1][0], rt[2][0], rt[3][0]].map(ar), c:0 });
  if (L.length >= 4) quiz.push({ q:"مين أكثر زميل مرّر الكورة لميسي؟", a:L.slice().sort((a, b) => b[2] - a[2]).slice(0, 4).map(x => ar(x[0])), c:0 });
  if (cot.length >= 4) quiz.push({ q:"تحت أي مدرب لعب ميسي أكثر مباريات؟", a:cot.slice(0, 4).map(x => ar(x[0])), c:0 });
  quiz.push({ q:"كم هدف سجل ميسي برجله اليمين (في بيانات StatsBomb)؟", a:[right, right + 17, Math.max(1, right - 21), right + 40].map(String), c:0 });
  quiz.push({ q:"كم كرة ذهبية فاز فيها ميسي؟", a:[bdo.length, bdo.length - 1, bdo.length + 1, bdo.length - 2].map(String), c:0 });
  const days = {}; goals.forEach(g => { (days[g.date.slice(5)] = days[g.date.slice(5)] || []).push([g.date.slice(0, 4), g.opp, g.min]); });
  I.forEach(g => { (days[g.date.slice(5)] = days[g.date.slice(5)] || []).push([g.date.slice(0, 4), g.opp, g.min, 1]); });
  room("r-play", 28, "العب مع ميسي", "",
    `<div class="games"><section><h3>قف مكانه</h3><p class="small">اضغط أي نقطة في الملعب: كم مرة سدد ميسي من هنا، وكم سجل.</p><div id="spot">${half(allShots.map(s => { const [a, b] = HX(s.x, s.y); return `<circle cx="${a}" cy="${b}" r=".45" class="pt ${s.goal ? "L" : "miss"}"/>`; }).join(""), "tap")}</div><p id="spotr" class="small" aria-live="polite"></p></section>
<section><h3>وين بيسدد؟</h3><p class="small">هذا مكان التسديدة. اختار وين راحت الكورة في المرمى.</p><div id="guess"></div></section>
<section><h3>اختبار ميسي</h3><div id="quiz"></div></section>
<section><h3>هذا اليوم في مسيرته</h3><div id="today"></div></section></div>
<script type="application/json" id="mdata">${JSON.stringify({ game, quiz, days, dob:X.dob || null, names:Object.fromEntries([...new Set([...quiz.flatMap(q => q.a), ...Object.values(days).flat().map(d => d[1])])].map(n => [n, ar(n)]).filter(x => x[0] !== x[1])) }).replace(/</g, "\\u003c")}</script>`);
  room("r-keep", 29, "خذ ميسي معك", "", `<div class="keep"><button type="button" class="btn" id="mwall">خلفية للجوال: الـ${goals.length} هدف</button><button type="button" class="btn" id="mcard" disabled>صورة للهدف اللي واقف عليه في الملعب</button><a class="btn" href="/messi/poster/">بوستر المتحف للطباعة</a></div><p class="small muted">الصورة تنرسم على جهازك وتنحفظ عندك.</p>`);

  const nav = `<nav class="mrooms" aria-label="قاعات المتحف"><ol>${secs.map(s => `<li><a href="#${s.id}"><span class="num">${s.no}</span> ${esc(s.title)}</a></li>`).join("")}</ol></nav>`;
  const body = `<h1>متحف ميسي</h1><p class="season">${tot ? `${tot.goals} هدف، ${tot.assists} تمريرة حاسمة، ${tot.apps} مباراة` : ""}</p>
<div id="mbday" hidden></div>${entrance}<div class="museum">${nav}<div class="rooms">${secs.map(s => s.html).join("")}</div></div>
<p class="src">البيانات: StatsBomb (بيانات مفتوحة)، FotMob، Transfermarkt، ويكي داتا، martj42. كل رقم من مصدره المكتوب تحت قاعته.</p>`;

  // the print poster: every goal, top view, with the career line
  const poster = `<div class="poster mposter"><h1>ميسي</h1><p class="num">${tot ? tot.goals : goals.length}</p>${half(goals.map(g => { const [a, b] = HX(g.x, g.y), [c] = HX(120, Math.min(43.8, Math.max(36.2, g.ey == null ? 40 : g.ey))); return `<path d="M${a} ${b}Q${((a + c) / 2).toFixed(1)} ${(b / 2 - 4).toFixed(1)} ${c} 0" class="arc ${g.body}"/>`; }).join(""), "big")}<p>${goals.length} هدف من مكانها، ${ss[0]}–${ss[ss.length - 1]} · StatsBomb · tifo.elyoxe.com/messi/</p></div>`;
  return { body, poster, goals:goals.length, total:tot };
};
