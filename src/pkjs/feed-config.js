'use strict';
// Owner-selected production GitHub Pages timetable destination.
// Production never accepts HTTP. The isolated tools/test_feed.py harness does.
module.exports = { manifestUrl: 'https://ewijaya.github.io/kasugabus-pebble/timetables/manifest.json', coverage: 'minami-kasugaoka-v1',
  appVersion: 1, maxPayload: 32768, manifestMaxBytes: 8192, requestTimeout: 15000 };
