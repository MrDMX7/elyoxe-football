// node --test site/lib/h2h_all.test.cjs — every meeting of two teams in every competition (v1/h2h-all/*, graph/publish.h2h)
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), X = require("./h2h_all.cjs");

const D = { teams: ["102101", "102117"], names: ["الجزيرة", "العين"], n: 56, w: [19, 12, 25], goals: [83, 101], first: "2000-12-14",
  by_comp: [["دوري أدنوك للمحترفين", 51, 18, 12, 21], ["كأس رئيس الدولة", 2, 1, 0, 1]],
  biggest: [["2019-04-03", "5-1", "2956909"], ["2022-05-11", "5-0", "3849782"]],
  matches: [["2022-05-11", "دوري أدنوك للمحترفين", "2021/2022", "102117", 5, 0, "102101", "3849782"],
            ["2000-12-14", "دوري أدنوك للمحترفين", "2000/2001", "102101", 2, 1, "102117", "k638598"]] };
const o = { team: id => ["102101", "102117"].includes(String(id)), match: id => id === "3849782" || id === "k638598" };

test("a pair: totals, competitions, biggest wins, every meeting linked", () => {
  const h = X.pairBody(D, o);
  assert.match(h, /كل المواجهات في كل البطولات/);
  assert.match(h, /<span class="num">56<\/span> مواجهة من <span class="num">2000<\/span>/);
  assert.match(h, /الجزيرة <span class="num">19<\/span>/);
  assert.match(h, /العين <span class="num">25<\/span>/);
  assert.match(h, /تعادل <span class="num">12<\/span>/);
  assert.match(h, /كأس رئيس الدولة/);
  assert.match(h, /أكبر فوز/);
  assert.match(h, /href="\/m\/3849782\/"/);
  assert.match(h, /href="\/m\/k638598\/"/);
});

test("a team's record against every opponent", () => {
  const h = X.teamBody("102101", [["102117", 56, 19, 12, 25], ["k77", 3, 1, 1, 1]], { "102117": "العين", k77: "الشعب" }, Object.assign({}, o, { pair: (a, b) => `/h2h/${a}-${b}/` }));
  assert.match(h, /<a href="\/h2h\/102101-102117\/">العين<\/a>/);
  assert.match(h, /الشعب/);
  assert.match(h, /<span class="num">19<\/span>/);
});

test("the pair key is the two ids sorted as text", () => {
  assert.equal(X.key("5789", "102101"), "102101-5789");
  assert.equal(X.key(102117, 102101), "102101-102117");
});
