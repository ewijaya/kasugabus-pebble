'use strict';
var protocol = require('./protocol'), integer = require('./settings').integer;
function signed32(bytes, i) { return (bytes[i] | bytes[i + 1] << 8 | bytes[i + 2] << 16 | bytes[i + 3] << 24); }
function parse(bytes) {
  if (!Array.isArray(bytes) || bytes.length % 10 || bytes.length > 250) throw new Error('Invalid coordinates');
  bytes.forEach(function(b){if(!integer(b,0,255))throw new Error('Invalid coordinate byte');});
  var points = [], seen = {};
  for (var i = 0; i < bytes.length; i += 10) {
    var id = bytes[i] + bytes[i + 1] * 256, lat = signed32(bytes, i + 2) / 1e7, lon = signed32(bytes, i + 6) / 1e7;
    if (!id || seen[id] || lat < -90 || lat > 90 || lon < -180 || lon > 180) throw new Error('Invalid pole');
    seen[id] = true; points.push({id: id, lat: lat, lon: lon, order: points.length});
  }
  return points;
}
function distance(a, b) {
  var rad = Math.PI / 180, dlat = (a.latitude - b.lat) * rad, dlon = (a.longitude - b.lon) * rad;
  var h = Math.sin(dlat / 2) * Math.sin(dlat / 2) + Math.cos(a.latitude * rad) * Math.cos(b.lat * rad) * Math.sin(dlon / 2) * Math.sin(dlon / 2);
  return 6371000 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(Math.max(0, 1 - h)));
}
function rank(position, points, now) {
  var c = position && position.coords, stamp = position && position.timestamp;
  if (!c || typeof c.latitude !== 'number' || !isFinite(c.latitude) || c.latitude < -90 || c.latitude > 90 ||
      typeof c.longitude !== 'number' || !isFinite(c.longitude) || c.longitude < -180 || c.longitude > 180 ||
      typeof c.accuracy !== 'number' || !isFinite(c.accuracy) || c.accuracy < 0 || c.accuracy > 4294967295 ||
      typeof stamp !== 'number' || !isFinite(stamp) || stamp < 0 || !integer(Math.floor(stamp / 1000),0,4294967295) ||
      typeof now !== 'number' || !isFinite(now) || now < 0) return { status: 5 };
  // A future clock mismatch is not qualified fix metadata. Keep its stale
  // state, without passing an implausible timestamp to the watch.
  if (stamp > now + 5000) return { status: 2 };
  var seconds=Math.floor(stamp / 1000),accuracy=Math.ceil(c.accuracy);
  if (now - stamp > 120000) return { status: 2, stamp: seconds, accuracy: accuracy };
  if (c.accuracy > 100) return { status: 1, stamp: seconds, accuracy: accuracy };
  if (!points.length) return { status: 7 };
  var rows = points.map(function(p) { var metres=distance(c,p);return {id: p.id, distance: Math.round(metres), rawDistance:metres, order: p.order}; });
  rows.sort(function(a, b) { return a.rawDistance - b.rawDistance || a.order - b.order; });
  if (rows[0].rawDistance > 2000) return {status: 6};
  // Form uncertainty groups around their nearest anchor; order inside a group is
  // the watch's input/favourite order, avoiding a non-transitive comparator.
  var stable = [], group = [], anchor = 0;
  rows.forEach(function(row) {
    if (group.length && row.rawDistance - anchor > c.accuracy * 2) {
      group.sort(function(a, b) { return a.order - b.order; }); stable = stable.concat(group); group = [];
    }
    if (!group.length) anchor = row.rawDistance;
    group.push(row);
  });
  group.sort(function(a, b) { return a.order - b.order; }); stable = stable.concat(group);
  var bytes = [];
  stable.forEach(function(r) { bytes.push(r.id & 255, r.id >>> 8, r.distance & 255, r.distance >>> 8 & 255, r.distance >>> 16 & 255, r.distance >>> 24); });
  return {status: 0, stamp: seconds, accuracy: accuracy, data: bytes};
}
module.exports = function(options) {
  var generation = 0, timer = null;
  return { request: function(request, version, bytes, enabled) {
    generation += 1; var token = generation, points;
    if (timer !== null) options.cancel(timer);
    function finish(result) {
      if (token !== generation) return;
      generation += 1; if (timer !== null) options.cancel(timer); timer = null;
      var msg = {TYPE: protocol.type.NEARBY, REQUEST: request, VERSION: version, STATUS: result.status};
      if ((result.status===0||result.status===1||result.status===2)&&integer(result.stamp,0,4294967295)&&integer(result.accuracy,0,4294967295)) {
        msg.STAMP=result.stamp;msg.ACCURACY=result.accuracy;
      }
      if (result.status === 0) msg.DATA = result.data;
      options.send(msg);
    }
    if (!integer(request, 1, 4294967295) || !integer(version, 1, 4294967295)) return;
    if (!enabled) return finish({status: 8});
    try { points = parse(bytes); } catch (e) { return finish({status: 5}); }
    if (!points.length) return finish({status: 7});
    if (!options.geolocation || !options.geolocation.getCurrentPosition) return finish({status: 5});
    timer = options.schedule(function() { finish({status: 4}); }, 15000);
    try {
      options.geolocation.getCurrentPosition(function(position) { finish(rank(position, points, options.now())); },
        function(error) { finish({status: error && error.code === 1 ? 3 : error && error.code === 3 ? 4 : 5}); },
        {enableHighAccuracy: true, timeout: 15000, maximumAge: 0});
    } catch (e) { finish({status: 5}); }
  }, invalidate: function() { generation += 1; if (timer !== null) options.cancel(timer); timer = null; } };
};
module.exports.parse = parse;
module.exports.rank = rank;
module.exports.distance = distance;
