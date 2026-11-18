// node --test news/xreader.test.cjs: when the X reader starts the journal at once
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const { shouldDispatch } = require("./xreader.js");
const off = t => [{ tier: "official", text: t }];
test("an official announcement starts the journal, not more than every 5 minutes, and only with «عاجل» on", () => {
  assert.equal(shouldDispatch(off("OFFICIAL: Club completes the signing of X"), 0, 10 * 60e3, true), true);
  assert.equal(shouldDispatch([{ tier: "paper", text: "OFFICIAL: X joins" }], 0, 10 * 60e3, true), false);
  assert.equal(shouldDispatch(off("OFFICIAL: Club completes the signing of X"), 8 * 60e3, 10 * 60e3, true), false);
  assert.equal(shouldDispatch(off("OFFICIAL: Club completes the signing of X"), 0, 10 * 60e3, false), false);
});
test("a club's everyday post does not (final review, finding 5)", () => {
  assert.equal(shouldDispatch(off("Happy birthday to our legend! 🎂"), 0, 10 * 60e3, true), false);
  assert.equal(shouldDispatch(off("Matchday! 🔴⚪️ Kick-off 20:00"), 0, 10 * 60e3, true), false);
  assert.equal(shouldDispatch(off("رسمياً.. النادي يعلن التعاقد مع اللاعب"), 0, 10 * 60e3, true), true);
});
