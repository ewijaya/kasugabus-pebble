'use strict';
// Settings must name stops added by timetable updates and never block saving
// when the watch's live boarding-point list arrives late over Bluetooth.
var assert = require('assert'), fs = require('fs'), path = require('path'), vm = require('vm');
var settings = require('../src/pkjs/settings'), store = require('../src/pkjs/catalog-store');
function test(name, fn) { fn(); console.log('PASS ' + name); }

test('catalogue store validates, round-trips and tolerates broken storage', function() {
  var data = {}, storage = { getItem: function(k) { return k in data ? data[k] : null; }, setItem: function(k, v) { data[k] = v; } };
  assert.strictEqual(store.load(storage), null);
  assert.ok(store.save(storage, [{ id: 11, label: 'Nihon Teien-mae | Ibaraki | Kintetsu Bus' }], 4));
  assert.deepStrictEqual(store.load(storage), { version: 4, points: [{ id: 11, label: 'Nihon Teien-mae | Ibaraki | Kintetsu Bus' }] });
  [[], [{ id: 0, label: 'x' }], [{ id: 1, label: '' }], [{ id: 1, label: 'a' }, { id: 1, label: 'b' }], 'nope'].forEach(function(bad) {
    assert.strictEqual(store.valid(bad), false);
  });
  data[store.KEY] = '{not json';
  assert.strictEqual(store.load(storage), null);
  var throwing = { getItem: function() { throw new Error('denied'); }, setItem: function() { throw new Error('denied'); } };
  assert.strictEqual(store.load(throwing), null);
  assert.strictEqual(store.save(throwing, [{ id: 1, label: 'a' }], 1), false);
});

function harness(saved) {
  var listeners = {}, sent = [], clays = [], timers = [], privateStore = {};
  if (saved) privateStore[store.KEY] = JSON.stringify(saved);
  function MockClay(config, custom, options) { this.config = config; this.options = options; this.meta = {}; clays.push(this); }
  MockClay.prototype.setSettings = function(v) { this.values = v; };
  MockClay.prototype.generateUrl = function() { return 'data:mock'; };
  var context = { require: function(name) { return name === '@rebble/clay' ? MockClay : require(path.resolve(__dirname, '../src/pkjs', name)); },
    Pebble: { addEventListener: function(n, fn) { listeners[n] = fn; }, sendAppMessage: function(m, ok) { sent.push(m); if (ok) ok(); }, openURL: function() {} },
    localStorage: { getItem: function(k) { return k in privateStore ? privateStore[k] : null; }, setItem: function(k, v) { privateStore[k] = v; }, removeItem: function(k) { delete privateStore[k]; } },
    setTimeout: function(fn, delay) { timers.push({ fn: fn, delay: delay }); return timers.length; },
    clearTimeout: function(id) { if (timers[id - 1]) timers[id - 1].fn = null; },
    console: { log: function() {} }, Date: Date, Math: Math, JSON: JSON, XMLHttpRequest: function() {} };
  vm.runInNewContext(fs.readFileSync(path.resolve(__dirname, '../src/pkjs/index.js'), 'utf8'), context);
  return { listeners: listeners, sent: sent, clays: clays, timers: timers, privateStore: privateStore };
}
// A watch on dataset v4 whose favourites include the v3/v4 stops 11 and 12.
var bundledIds = require('../src/pkjs/catalog.json').boardingPoints.map(function(p) { return p.id; });
var full = require('../src/pkjs/catalog.json').boardingPoints.concat([{ id: 10, label: 'Nihon Teien-mae | University / Mihogaoka | Kintetsu Bus' },
  { id: 11, label: 'Nihon Teien-mae | Ibaraki | Kintetsu Bus' }, { id: 12, label: 'Handai Honbu-mae | Ibaraki | Kintetsu Bus' }]);
var prefs = settings.encode({ flags: 1, defaultId: 11, buffer: 2, textSize: 1, theme: 0, favourites: [1, 11, 12], walks: {} }, full);
function state(h) { h.listeners.appmessage({ payload: { TYPE: 2, VERSION: 4, PENDING: 0, FLAGS: 1, LENGTH: 32768, DATA: prefs } }); }
function liveList(h) {
  var data = [];
  full.forEach(function(p) { var t = Array.from(Buffer.from(p.label)); data.push(p.id & 255, p.id >> 8, t.length); data = data.concat(t); });
  h.listeners.appmessage({ payload: { TYPE: 13, VERSION: 4, SEQ: 0, STATUS: 1, DATA: data } });
}
function openFor(h) {
  var before = h.timers.length; h.listeners.showConfiguration();
  var opened = h.timers.slice(before).filter(function(t) { return t.fn && t.delay === 8000; });
  assert.strictEqual(opened.length, 1, 'settings wait up to 8 s for the live list');
  return opened[0];
}
function optionLabels(clay) { return clay.config.find(function(s) { return s.items && s.items[0].defaultValue === 'Usual stop'; }).items[1].options.map(function(o) { return o.label; }); }

test('live list opens settings with every stop and is remembered for next time', function() {
  var h = harness(null);
  h.listeners.ready(); state(h); openFor(h); liveList(h);
  assert.strictEqual(h.clays.length, 1);
  assert.ok(optionLabels(h.clays[0]).indexOf('Handai Honbu-mae | Ibaraki | Kintetsu Bus') !== -1);
  assert.deepStrictEqual(store.load({ getItem: function(k) { return h.privateStore[k]; } }).points.map(function(p) { return p.id; }), full.map(function(p) { return p.id; }));
});

test('a slow watch falls back to the remembered list, not the bundled baseline', function() {
  var h = harness({ version: 4, points: full });
  h.listeners.ready(); state(h); openFor(h).fn();
  var labels = optionLabels(h.clays[0]);
  assert.ok(labels.indexOf('Nihon Teien-mae | Ibaraki | Kintetsu Bus') !== -1);
  assert.ok(!labels.some(function(l) { return /name not loaded|Unavailable/.test(l); }));
});

test('without any remembered list, stops the watch uses stay selectable and saveable', function() {
  var h = harness(null);
  h.listeners.ready(); state(h); openFor(h).fn();
  var clay = h.clays[0], labels = optionLabels(clay);
  assert.ok(labels.indexOf('Stop #11 (name not loaded)') !== -1 && labels.indexOf('Stop #12 (name not loaded)') !== -1);
  assert.ok(!labels.some(function(l) { return /remove to save/.test(l); }), 'no removal demanded');
  [11, 12].forEach(function(id) { assert.ok(clay.meta.userData.ids.indexOf(id) !== -1, 'validation treats ' + id + ' as known'); });
  assert.ok(bundledIds.indexOf(11) === -1, 'fixture really exercises a stop missing from the bundle');
  h.listeners.webviewclosed({ response: JSON.stringify(clay.values) });
  var saved = h.sent.filter(function(m) { return m.TYPE === 11; });
  assert.strictEqual(saved.length, 1, 'saving is not blocked');
  var decoded = settings.decode(saved[0].DATA.slice(0, 80), full);
  assert.deepStrictEqual([decoded.defaultId, decoded.favourites], [11, [1, 11, 12]], 'the watch keeps its new-stop favourites');
});
