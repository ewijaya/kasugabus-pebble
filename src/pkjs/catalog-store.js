'use strict';
// Remembers the last complete boarding-point list (id + label) the watch or a
// timetable download supplied, so settings can name stops added by timetable
// updates even when the live list is slow to arrive over Bluetooth.
var KEY = 'kasugabus.catalog';
function valid(points) {
  var seen = {};
  return Array.isArray(points) && points.length > 0 && points.length <= 64 && points.every(function(p) {
    var ok = p && typeof p.id === 'number' && Math.floor(p.id) === p.id && p.id >= 1 && p.id <= 65535 &&
      !seen[p.id] && typeof p.label === 'string' && p.label.length > 0 && p.label.length <= 200;
    if (ok) seen[p.id] = true;
    return ok;
  });
}
function load(storage) {
  try {
    var value = storage && JSON.parse(storage.getItem(KEY));
    if (value && valid(value.points)) return { points: value.points.map(function(p) { return { id: p.id, label: p.label }; }), version: value.version || 0 };
  } catch (ignore) {}
  return null;
}
function save(storage, points, version) {
  if (!storage || !valid(points)) return false;
  try {
    storage.setItem(KEY, JSON.stringify({ version: version || 0, points: points.map(function(p) { return { id: p.id, label: p.label }; }) }));
    return true;
  } catch (ignore) { return false; }
}
module.exports = { KEY: KEY, load: load, save: save, valid: valid };
