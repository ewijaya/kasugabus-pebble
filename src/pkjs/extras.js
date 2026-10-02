'use strict';
// Mirrors src/c/extras.c: 28 wire bytes sent after the 80 preference bytes.
var settings = require('./settings'), integer = settings.integer, u16 = settings.u16, put16 = settings.put16;
var BYTES = 28, ACTIONS = 9, PROFILES = 1, COMMUTE = 2, BACK_LAUNCHER = 4;
var ACTION_LABELS = ['Nothing', 'Next departure', 'Previous departure', 'Switch favourite stop',
  'Flip direction', 'Open Nearby', 'Open All departures', 'Open departure board', 'Exit to watchface'];
var BUTTON_KEYS = ['ButtonUp', 'ButtonDown', 'ButtonHoldUp', 'ButtonHoldDown'];
var DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
function defaults() {
  return { buttons: [3, 1, 4, 5], flags: 0, more: 2, headsUp: 0, profileA: 0, profileAHour: 4,
    profileB: 0, profileBHour: 15, commutePoint: 0, commuteMinute: 480, commuteDays: 0x3e };
}
function validate(e, catalog) {
  var known = {};
  catalog.forEach(function(p) { known[p.id] = true; });
  if (!Array.isArray(e.buttons) || e.buttons.length !== 4 || !e.buttons.every(function(a) { return integer(a, 0, ACTIONS - 1); }) ||
      !integer(e.flags, 0, PROFILES | COMMUTE | BACK_LAUNCHER) || !integer(e.more, 0, 2) || !integer(e.headsUp, 0, 30) ||
      !integer(e.profileA, 0, 65535) || !integer(e.profileB, 0, 65535) ||
      !integer(e.profileAHour, 0, 23) || !integer(e.profileBHour, 0, 23) ||
      !integer(e.commutePoint, 0, 65535) || !integer(e.commuteMinute, 0, 1439) || !integer(e.commuteDays, 0, 127)) {
    throw new Error('Invalid extra settings');
  }
  if (e.flags & PROFILES) {
    if (!known[e.profileA] || !known[e.profileB]) throw new Error('Choose both profile stops');
    if (e.profileAHour === e.profileBHour) throw new Error('Profile start hours must differ');
  }
  if (e.flags & COMMUTE) {
    if (!known[e.commutePoint]) throw new Error('Choose the commute stop');
    if (!e.commuteDays) throw new Error('Choose at least one commute day');
  }
  return e;
}
function encode(e, catalog) {
  validate(e, catalog);
  var b = [], i;
  for (i = 0; i < BYTES; i += 1) b[i] = 0;
  b[0] = 1;
  for (i = 0; i < 4; i += 1) b[1 + i] = e.buttons[i];
  b[5] = e.flags; b[6] = e.more; b[7] = e.headsUp;
  put16(b, 8, e.profileA); b[10] = e.profileAHour;
  put16(b, 12, e.profileB); b[14] = e.profileBHour;
  put16(b, 16, e.commutePoint); put16(b, 18, e.commuteMinute); b[20] = e.commuteDays;
  return b;
}
// Watch records are checked structurally; points removed by a timetable
// update are reported by the form instead of discarding every extra.
function decode(b) {
  if (!Array.isArray(b) || b.length !== BYTES || b[0] !== 1 || !b.every(function(v) { return integer(v, 0, 255); }) ||
      b[11] || b[15] || b.slice(21).some(function(v) { return v; })) throw new Error('Invalid extra settings envelope');
  var e = { buttons: b.slice(1, 5), flags: b[5], more: b[6], headsUp: b[7], profileA: u16(b, 8), profileAHour: b[10],
    profileB: u16(b, 12), profileBHour: b[14], commutePoint: u16(b, 16), commuteMinute: u16(b, 18), commuteDays: b[20] };
  return validate(e, []
    .concat(e.flags & PROFILES ? [{ id: e.profileA }, { id: e.profileB }] : [])
    .concat(e.flags & COMMUTE ? [{ id: e.commutePoint }] : []));
}
function unwrap(v) { return v && typeof v === 'object' && !Array.isArray(v) ? v.value : v; }
function number(v, min, max, message) {
  v = unwrap(v);
  if (!(typeof v === 'number' || (typeof v === 'string' && /^[0-9]+$/.test(v))) || !integer(Number(v), min, max)) throw new Error(message);
  return Number(v);
}
function toggle(v) {
  v = unwrap(v);
  if (v === true || v === 1 || v === '1') return true;
  if (v === false || v === 0 || v === '0' || typeof v === 'undefined') return false;
  throw new Error('Invalid switch');
}
// Keys missing from the form keep the watch's current value (base), so a
// page without these sections cannot reset them.
function fromClay(values, catalog, base) {
  base = base || defaults();
  var current = toClay(base), merged = {};
  Object.keys(current).forEach(function(key) { merged[key] = typeof values[key] === 'undefined' ? current[key] : values[key]; });
  values = merged;
  var e = defaults(), time = unwrap(values.CommuteTime), days = unwrap(values.CommuteDays);
  e.buttons = BUTTON_KEYS.map(function(key) { return number(values[key], 0, ACTIONS - 1, 'Invalid button action'); });
  e.more = number(values.HomeMore, 0, 2, 'Invalid departure count');
  e.headsUp = number(values.HeadsUp === '' ? 0 : values.HeadsUp, 0, 30, 'Heads-up must be 0 to 30 minutes');
  e.profileA = number(values.ProfileA, 0, 65535, 'Invalid profile stop');
  e.profileB = number(values.ProfileB, 0, 65535, 'Invalid profile stop');
  e.profileAHour = number(values.ProfileAHour, 0, 23, 'Invalid profile hour');
  e.profileBHour = number(values.ProfileBHour, 0, 23, 'Invalid profile hour');
  e.commutePoint = number(values.CommutePoint, 0, 65535, 'Invalid commute stop');
  var match = /^([01][0-9]|2[0-3]):([0-5][0-9])$/.exec(typeof time === 'string' ? time : '');
  if (!match) throw new Error('Commute time must be HH:MM');
  e.commuteMinute = Number(match[1]) * 60 + Number(match[2]);
  if (!Array.isArray(days) || days.length !== 7) throw new Error('Invalid commute days');
  e.commuteDays = days.reduce(function(mask, on, i) { return mask | (toggle(on) ? 1 << i : 0); }, 0);
  e.flags = (toggle(values.ProfilesEnabled) ? PROFILES : 0) | (toggle(values.CommuteEnabled) ? COMMUTE : 0) |
    (toggle(values.BackToAppList) ? BACK_LAUNCHER : 0);
  return validate(e, catalog);
}
function pad(n) { return (n < 10 ? '0' : '') + n; }
function toClay(e) {
  var v = { HomeMore: String(e.more), HeadsUp: String(e.headsUp), ProfilesEnabled: !!(e.flags & PROFILES),
    ProfileA: String(e.profileA), ProfileAHour: String(e.profileAHour), ProfileB: String(e.profileB),
    ProfileBHour: String(e.profileBHour), CommuteEnabled: !!(e.flags & COMMUTE), CommutePoint: String(e.commutePoint),
    CommuteTime: pad(Math.floor(e.commuteMinute / 60)) + ':' + pad(e.commuteMinute % 60),
    CommuteDays: DAY_NAMES.map(function(name, i) { return !!(e.commuteDays & (1 << i)); }),
    BackToAppList: !!(e.flags & BACK_LAUNCHER) };
  BUTTON_KEYS.forEach(function(key, i) { v[key] = String(e.buttons[i]); });
  return v;
}
module.exports = { BYTES: BYTES, ACTION_LABELS: ACTION_LABELS, BUTTON_KEYS: BUTTON_KEYS, DAY_NAMES: DAY_NAMES,
  defaults: defaults, validate: validate, encode: encode, decode: decode, fromClay: fromClay, toClay: toClay };
