'use strict';
module.exports = {
  keys: { TYPE: 0, SESSION: 1, SEQ: 2, VERSION: 3, LENGTH: 4, CRC: 5,
    DATA: 6, STATUS: 7, REQUEST: 8, STAMP: 9, ACCURACY: 10, EFFECTIVE: 11,
    PENDING: 12, FLAGS: 13 },
  type: { HELLO: 1, STATE: 2, CHECK: 3, FEED: 4, BEGIN: 5, CHUNK: 6,
    COMMIT: 7, ACK: 8, LOCATION: 9, NEARBY: 10, SETTINGS: 11 },
  feed: { CHECKING: 0, DOWNLOADING: 1, CHECKED: 2, UPDATED: 3, UNAVAILABLE: 4,
    FAILED: 5, INCOMPATIBLE: 6, NOT_CONFIGURED: 7, TRANSFERRING: 8 },
  nearby: { GOOD: 0, ACCURACY: 1, STALE: 2, DENIED: 3, TIMEOUT: 4,
    UNAVAILABLE: 5, OUTSIDE: 6, NO_COORDINATES: 7, DISABLED: 8 },
  get: function(payload, name) {
    var value=typeof payload[name] !== 'undefined' ? payload[name] : payload[this.keys[name]];
    // PebbleKit hosts can expose a uint32 tuple through a signed JS integer.
    return typeof value==='number'&&value<0&&value>=-2147483648&&value===Math.floor(value)?value>>>0:value;
  },
  wire: function(message) {
    var result={};
    Object.keys(message).forEach(function(key){var value=message[key];
      // Preserve the same 32 bits through hosts whose API serializes Int32.
      // DATA arrays retain their bytes, including packed signed coordinates.
      result[key]=typeof value==='number'&&value>=2147483648&&value<=4294967295&&value===Math.floor(value)?value|0:value;
    });
    return result;
  }
};
