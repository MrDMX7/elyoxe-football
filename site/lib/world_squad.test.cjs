// node --test site/lib/world_squad.test.cjs — where the site's post-build link check sends a link to a page it did not write
"use strict";
const test = require("node:test"), assert = require("node:assert/strict"), W = require("./world_squad.cjs");

test("an old match the archive has goes to its archive page, the same match page as today's; the rest to the match card", () => {
  const has = { written: new Set(), clubs: new Set(), fm2k: { 4813470: 86169 } };
  assert.equal(W.relink("/m/4813470/", has), "/m/k86169/");
  assert.equal(W.relink("/m/5000000/", has), "/db/match/?id=5000000");
  assert.equal(W.relink("/m/5000000/", { written: new Set(), clubs: new Set() }), "/db/match/?id=5000000");
});

test("a FotMob man the archive has goes to his profile before the encyclopedia's card", () => {
  const has = { written: new Set(["/db/player/1526227"]), clubs: new Set(), fm2p: { 1526227: 5 } };
  assert.equal(W.relink("/p/1526227/", has), "/p/k5/");
  assert.equal(W.relink("/p/1526227/", { written: new Set(["/db/player/1526227"]), clubs: new Set() }), "/db/player/1526227/");
});

test("a link to the encyclopedia's page of a man or a match the archive has becomes a link to the one page", () => {
  const has = { written: new Set(), clubs: new Set(), fm2p: { 214353: 68213 }, fm2k: { 4813470: 86169 } };
  assert.equal(W.canonical("/db/player/214353/", has), "/p/k68213/");
  assert.equal(W.canonical("/db/match/?id=4813470", has), "/m/k86169/");
  assert.equal(W.canonical("/db/player/1/", has), null);
  assert.equal(W.canonical("/t/8650/", has), null);
});
