'use strict';
function integer(n, min, max) {
  return typeof n === 'number' && isFinite(n) && Math.floor(n) === n && n >= min && n <= max;
}
function u16(bytes, offset) { return bytes[offset] + bytes[offset + 1] * 256; }
function put16(bytes, offset, n) { bytes[offset] = n & 255; bytes[offset + 1] = n >>> 8; }
function validate(s, catalog) {
  var known = {}, used = {}, i, walks = s.walks || {};
  catalog.forEach(function(p) { known[p.id] = true; });
  if (!integer(s.flags, 0, 31) || !integer(s.buffer, 0, 30) ||
      !integer(s.defaultId, 0, 65535) || !Array.isArray(s.favourites) || s.favourites.length > 12) {
    throw new Error('Invalid preferences');
  }
  if ((s.flags & 4) && !(s.flags & 2)) throw new Error('Startup Nearby requires startup location permission');
  if (s.defaultId && !known[s.defaultId]) throw new Error('Unknown default boarding point');
  for (i = 0; i < s.favourites.length; i += 1) {
    var id = s.favourites[i];
    if (!integer(id, 1, 65535) || !known[id] || used[id]) throw new Error('Invalid or duplicate favourite');
    used[id] = true;
  }
  var count = 0;
  Object.keys(walks).forEach(function(id) {
    if (!known[id] || !integer(Number(id), 1, 65535) || !integer(walks[id], 0, 120)) {
      throw new Error('Invalid scoped walking duration');
    }
    count += 1;
  });
  if (count > 12) throw new Error('Too many walking allowances');
  return s;
}
function encode(s, catalog) {
  validate(s, catalog);
  var bytes = [], i;
  for (i = 0; i < 80; i += 1) bytes[i] = 0;
  bytes[0] = 1; bytes[1] = s.flags; put16(bytes, 2, s.defaultId);
  bytes[4] = s.buffer; bytes[5] = s.favourites.length;
  s.favourites.forEach(function(id, n) { put16(bytes, 8 + n * 2, id); });
  Object.keys(s.walks || {}).sort(function(a, b) { return Number(a) - Number(b); }).forEach(function(id, n) {
    put16(bytes, 32 + n * 4, Number(id)); bytes[34 + n * 4] = s.walks[id];
  });
  return bytes;
}
function decode(bytes, catalog) {
  if (!Array.isArray(bytes) || bytes.length !== 80 || bytes[0] !== 1 || bytes[6] || bytes[7]) {
    throw new Error('Invalid preference envelope');
  }
  bytes.forEach(function(b) { if(!integer(b,0,255))throw new Error('Invalid preference byte'); });
  var s = { flags: bytes[1], defaultId: u16(bytes, 2), buffer: bytes[4], favourites: [], walks: {} }, i;
  if (bytes[5] > 12) throw new Error('Too many favourites');
  for (i = 0; i < 12; i += 1) {
    var id = u16(bytes, 8 + i * 2);
    if (i < bytes[5]) s.favourites.push(id);
    else if (id) throw new Error('Unexpected favourite padding');
    id = u16(bytes, 32 + i * 4);
    if (bytes[35 + i * 4] || (!id && bytes[34 + i * 4])) throw new Error('Invalid walking padding');
    if (id) {
      if (typeof s.walks[id] !== 'undefined') throw new Error('Duplicate walk ID');
      s.walks[id] = bytes[34 + i * 4];
    }
  }
  return validate(s, catalog);
}
function unwrap(v) { return v && typeof v === 'object' ? v.value : v; }
function fromClay(values, catalog) {
  var s = { flags: 0, defaultId: Number(unwrap(values.DefaultId)), buffer: Number(unwrap(values.Buffer)),
    favourites: [], walks: {} };
  ['AutoChecks', 'LocationEnabled', 'NearbyStartup', 'HighContrast', 'ReducedMotion'].forEach(function(key, i) {
    var v = unwrap(values[key]);
    if (v === true || v === 1 || v === '1') s.flags |= 1 << i;
    else if (!(v === false || v === 0 || v === '0')) throw new Error('Invalid switch');
  });
  for (var i = 0; i < 12; i += 1) {
    var v = Number(unwrap(values['Favourite' + i]));
    if (!integer(v, 0, 65535)) throw new Error('Invalid favourite');
    if (v) s.favourites.push(v);
  }
  Object.keys(values).forEach(function(key) {
    if(!/^Walk[1-9][0-9]*$/.test(key))return;
    var v = unwrap(values[key]);
    if (v !== '' && typeof v !== 'undefined' && v !== null) s.walks[Number(key.slice(4))] = Number(v);
  });
  return validate(s, catalog);
}
function toClay(s, catalog) {
  var v = { DefaultId: s.defaultId, Buffer: s.buffer };
  ['AutoChecks', 'LocationEnabled', 'NearbyStartup', 'HighContrast', 'ReducedMotion'].forEach(function(key, i) {
    v[key] = !!(s.flags & (1 << i));
  });
  for (var i = 0; i < 12; i += 1) v['Favourite' + i] = s.favourites[i] || 0;
  catalog.forEach(function(p) { v['Walk' + p.id] = typeof s.walks[p.id] === 'undefined' ? '' : String(s.walks[p.id]); });
  Object.keys(s.walks).forEach(function(id) { v['Walk'+id]=String(s.walks[id]); });
  return v;
}
module.exports = { validate: validate, encode: encode, decode: decode, fromClay: fromClay,
  toClay: toClay, integer: integer, u16: u16, put16: put16 };
