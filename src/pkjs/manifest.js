'use strict';
var integer = require('./settings').integer;
function date(s) {
  if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(s)) throw new Error('Invalid date');
  var y = Number(s.slice(0,4)), m = Number(s.slice(5,7)), d = Number(s.slice(8,10));
  var ms = Date.UTC(y,m-1,d), dt = new Date(ms);
  if (y<1900 || y>2200 || dt.getUTCFullYear()!==y || dt.getUTCMonth()!==m-1 || dt.getUTCDate()!==d) throw new Error('Invalid date');
  return ms / 86400000;
}
function url(s, insecure) {
  // Reject credentials, fragments, escapes, ambiguous slashes and nonstandard ports.
  var match = typeof s === 'string' && /^(https?):\/\/([a-z0-9.-]+)(?::([0-9]+))?(\/[^\s?#\\]*)$/i.exec(s);
  if (!match || /%/.test(s) || /\/\.\.?\//.test(s) || /[?#]/.test(s)) throw new Error('Invalid feed URL');
  var scheme=match[1].toLowerCase(),host=match[2].toLowerCase();
  if (scheme !== 'https' && !(insecure && scheme === 'http' && (host === '127.0.0.1' || host === 'localhost'))) {
    throw new Error('HTTPS feed required');
  }
  if (scheme === 'https' && match[3] && match[3] !== '443') throw new Error('Invalid HTTPS port');
  return scheme+'://'+host+(match[3] && !(scheme==='https'&&match[3]==='443') ? ':'+match[3] : '');
}
function validate(value, config, now, testInsecure) {
  var origin = url(config.manifestUrl, testInsecure), today = Math.floor((now + 9*3600000)/86400000);
  if (!value || value.schema !== 1 || value.coverage !== config.coverage || !value.current) {
    var err = new Error('Incompatible manifest'); err.incompatible = true; throw err;
  }
  var published = date(value.published);
  if (published > today+1) throw new Error('Manifest publication date is in the future');
  function release(r) {
    if (!r || !integer(r.version,1,4294967295) || !integer(r.minAppVersion,1,4294967295)) throw new Error('Invalid release version');
    if (r.minAppVersion > config.appVersion) { var e=new Error('App update required');e.incompatible=true;throw e; }
    if (!integer(r.bytes,128,config.maxPayload) || !integer(r.crc32,0,4294967295) || typeof r.sha256!=='string' || !/^[a-f0-9]{64}$/.test(r.sha256)) throw new Error('Invalid payload bounds/checksum');
    if (url(r.url,testInsecure)!==origin) throw new Error('Unapproved payload host');
    var fields=['effectiveFrom','coverageFrom','coverageThrough','sourceVerified','reviewDue'];
    fields.forEach(function(f) { date(r[f]); });
    if (date(r.coverageFrom)>date(r.coverageThrough) || date(r.effectiveFrom)<date(r.coverageFrom) || date(r.effectiveFrom)>date(r.coverageThrough) || date(r.reviewDue)<date(r.sourceVerified) || date(r.sourceVerified)>published) throw new Error('Contradictory release dates');
    return r;
  }
  var current = release(value.current), upcoming = value.upcoming ? release(value.upcoming) : null;
  if (date(current.effectiveFrom)>today) throw new Error('Current release is not effective');
  if (upcoming && (date(upcoming.effectiveFrom)<=today || date(upcoming.effectiveFrom)<=date(current.effectiveFrom) || upcoming.version<=current.version)) throw new Error('Invalid upcoming release');
  return {current:current,upcoming:upcoming,published:published};
}
module.exports = { validate: validate, date: date, origin: url };
