'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {BrowserStore, validateProject} = require('./browser-store.js');
const sample = JSON.parse(fs.readFileSync(path.join(__dirname, 'sample-project.json'), 'utf8').replace(/^\uFEFF/, ''));
const clone = value => JSON.parse(JSON.stringify(value));
let passed = 0;
function test(name, fn) { fn(); passed++; console.log(`PASS ${name}`); }
function reject(edit, pattern) { const bad = clone(sample); edit(bad); assert.throws(() => validateProject(bad), pattern); }
test('example and direct schema preset accepted', () => {
  assert.equal(new BrowserStore(sample).metadata().floors.length, 20);
  assert.equal(new BrowserStore(sample.wave_preset).metadata().floors.length, 20);
  assert.equal(BrowserStore.fromText('\uFEFF' + JSON.stringify(sample)).floor(1).floor, 1);
});
test('stage and round trip retain extras, metadata, every floor and inactive topology', () => {
  const source = clone(sample); source.compiler = {path:'local-only', extras:['keep', {flag:true}]};
  source.wave_preset.extras = {name:'retain'}; const f = source.wave_preset.floors[0];
  f.extra = '<script>alert(1)</script>'; f.waves[19].extra = {hidden:true}; f.waves[19].groups[3].extra = 'preserve';
  const store = new BrowserStore(source);
  store.patch(1, [{path:'wave_count', expected:f.wave_count, value:1}]);
  const expected = clone(source); expected.wave_preset.floors[0].wave_count = 1;
  assert.deepEqual(JSON.parse(store.serialize()), expected);
  assert.deepEqual(BrowserStore.fromText(store.serialize()).document, expected);
  assert.deepEqual(source.wave_preset.floors[0], f);
  const returned = store.floor(1); returned.waves[0].groups[0].count = 8;
  assert.notEqual(store.floor(1).waves[0].groups[0].count, 8);
});
test('inactive group edits remain explicit and preserve other fields', () => {
  const store = new BrowserStore(sample), original = store.floor(1);
  store.patch(1, [{path:'waves/20/groups/4/count', expected:original.waves[19].groups[3].count, value:7}]);
  const expected = clone(original); expected.waves[19].groups[3].count = 7;
  assert.deepEqual(store.floor(1), expected);
});
test('invalid patch is atomic and conflicts rejected', () => {
  const store = new BrowserStore(sample), before = store.serialize();
  assert.throws(() => store.patch(1, [{path:'wave_count', expected:3, value:1}, {path:'waves/1/groups/1/count', expected:4, value:0}]), /active total/);
  assert.equal(store.serialize(), before);
  assert.throws(() => store.patch(1, [{path:'wave_count', expected:99, value:1}]), /conflict/);
  assert.equal(store.serialize(), before);
});
test('unsupported, duplicate, noninteger and out of catalog patch rejected', () => {
  const store = new BrowserStore(sample), change = {path:'wave_count', expected:3, value:1};
  assert.throws(() => store.patch(1, [{path:'__proto__/polluted', expected:3, value:1}]), /Unsupported/);
  assert.throws(() => store.patch(1, [change, change]), /Duplicate/);
  assert.throws(() => store.patch(1, [{...change, value:true}]), /integers/);
  assert.throws(() => store.patch(1, [{path:'waves/1/groups/1/mob_id', expected:1002, value:199999}]), /catalog/);
  assert.throws(() => store.patch(1, []), /1–181/);
  assert.equal({}.polluted, undefined);
});
test('malformed project, schema and floors rejected', () => {
  assert.throws(() => validateProject([]), /object/);
  reject(p => p.wave_preset.schema_version = 2, /schema/);
  reject(p => p.wave_preset.floors = [], /stored floors/);
  reject(p => p.wave_preset.floors.push(p.wave_preset.floors[0]), /Duplicate floor/);
  reject(p => p.wave_preset.floors[0].floor = true, /integer/);
  reject(p => p.wave_preset.floors[0].wave_count = 21, /integer/);
});
test('hidden waves and groups also receive full structural validation', () => {
  reject(p => p.wave_preset.floors[0].waves.pop(), /20 waves/);
  reject(p => p.wave_preset.floors[0].waves[19].wave = 1, /ordered/);
  reject(p => p.wave_preset.floors[0].waves[19].groups.pop(), /four groups/);
  reject(p => p.wave_preset.floors[0].waves[19].groups[3].mob_id = '1002', /integer/);
  reject(p => p.wave_preset.floors[0].waves[19].groups[3].count = 9, /integer/);
  reject(p => p.wave_preset.floors[0].waves[19].group_count = 0, /integer/);
  reject(p => p.wave_preset.floors[0].waves[19].groups.forEach(g => { g.count = 0; }), /active total/);
});
test('catalog topology and malformed JSON rejected', () => {
  reject(p => p.monsters = {}, /array/);
  reject(p => p.monsters.push(p.monsters[0]), /Duplicate catalog/);
  reject(p => p.monsters[0].id = false, /integer/);
  reject(p => p.monsters[0].label = {}, /text/);
  assert.throws(() => BrowserStore.fromText('{'), SyntaxError);
  assert.throws(() => BrowserStore.fromText(' '.repeat(16000001)), /16 MB/);
});
test('catalog names cover all sample IDs without changing IDs', () => {
  const names = JSON.parse(fs.readFileSync(path.join(__dirname, 'monster-names.ko.json'), 'utf8').replace(/^\uFEFF/, ''));
  assert.equal(sample.monsters.length, 55);
  sample.monsters.forEach(m => { assert.equal(typeof names[String(m.id)], 'string'); assert.ok(names[String(m.id)].length); });
});
console.log(`${passed} browser-store tests passed`);
