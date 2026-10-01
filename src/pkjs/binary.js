'use strict';
var hash = require('./checksums'), dates = require('./manifest'), integer = require('./settings').integer;
function validate(bytes, config, release) {
  function fail(reason) { throw new Error('Invalid timetable: '+reason); }
  if (!Array.isArray(bytes) || bytes.length < 128 || bytes.length > config.maxPayload) fail('length');
  bytes.forEach(function(b) { if(!integer(b,0,255))fail('non-byte'); });
  if(release&&(bytes.length!==release.bytes||hash.crc32(bytes)!==release.crc32||hash.sha256(bytes)!==release.sha256))fail('manifest checksum');
  function u16(o) { return bytes[o]+bytes[o+1]*256; }
  function u32(o) { return (bytes[o]+bytes[o+1]*256+bytes[o+2]*65536+bytes[o+3]*16777216)>>>0; }
  function i32(o) { return u32(o)|0; }
  function date(o, optional) { var n=i32(o);if(optional && n===-2147483648)return n;if(n<dates.date('1900-01-01')||n>dates.date('2200-12-31'))fail('date');return n; }
  if(String.fromCharCode.apply(null,bytes.slice(0,4))!=='KBT1')fail('magic');
  if(u16(4)!==1){var schemaError=new Error('Timetable schema requires app update');schemaError.incompatible=true;throw schemaError;}
  if(u16(6)!==128||u32(8)!==bytes.length||u16(50)!==0||u16(62)!==10)fail('header');
  if(!u32(16)||!u32(20))fail('version');
  if(u32(20)>config.appVersion){var e=new Error('Timetable requires app update');e.incompatible=true;throw e;}
  if(hash.crc32(bytes,16)!==u32(12))fail('CRC');
  var from=date(24),until=date(28),calFrom=date(32),calUntil=date(36),verified=date(40),review=date(44,true),effective=date(124);
  if(from>until||calFrom>calUntil||(review!==-2147483648&&review<verified)||effective<from||effective>until)fail('date ordering');
  var strides=[28,8,24,16,12,4,6,5,16,2],tables=[],end=128;
  for(var t=0;t<10;t+=1){var offset=u32(64+t*6),count=u16(68+t*6);if(offset!==end)fail('table layout');end+=count*strides[t];if(end>bytes.length)fail('table bounds');tables.push({offset:offset,count:count});}
  var pool=u32(52),poolLength=u32(56),starts={0:''};
  if(pool!==end||poolLength<1||pool+poolLength!==bytes.length||bytes[pool]!==0||bytes[bytes.length-1]!==0)fail('string pool');
  var pos=1;
  while(pos<poolLength){var start=pos,raw=[];
    while(pos<poolLength&&bytes[pool+pos]!==0){if(pos-start>=1023)fail('long string');if(bytes[pool+pos]<32&&bytes[pool+pos]!==9&&bytes[pool+pos]!==10)fail('control character');raw.push(bytes[pool+pos]);pos+=1;}
    if(pos===poolLength)fail('unterminated string');
    var escaped='';raw.forEach(function(b){escaped+='%'+('0'+b.toString(16)).slice(-2);});
    try{starts[start]=decodeURIComponent(escaped);}catch(e){fail('UTF-8');}pos+=1;
  }
  function string(o, required) {var s=starts[u16(o)];if(typeof s==='undefined'||(required&&!s))fail('string reference');return s;}
  var coverage=string(48,true);if(coverage!==config.coverage)fail('coverage');
  if(!tables[0].count||!tables[1].count||!tables[2].count)fail('empty coverage tables');var maps=[{},{},{},{},{}],catalog=[],departures=[];
  function record(table,index){return tables[table].offset+strides[table]*index;}
  for(t=0;t<5;t+=1){var previous=0;for(var i=0;i<tables[t].count;i+=1){var o=record(t,i),id=bytes[o];if(!id||id<=previous)fail('IDs');maps[t][id]=o;previous=id;}}
  function ref(table,id){if(!maps[table][id])fail('unknown reference');return maps[table][id];}
  for(i=0;i<tables[0].count;i+=1){o=record(0,i);if(!bytes[o+1]||(bytes[o+1]&~14))fail('operator day-type mask');string(o+2,true);string(o+4);string(o+6,true);var a=date(o+8),b=date(o+12),v=date(o+16),r=date(o+20,true);if(a>b||a<from||b>until||(r!==-2147483648&&r<v))fail('operator dates');if(u16(o+24)+u16(o+26)>tables[8].count)fail('operator sources');}
  for(i=0;i<tables[1].count;i+=1){o=record(1,i);if(bytes[o+1])fail('group padding');string(o+2,true);string(o+4,true);string(o+6);}
  for(i=0;i<tables[2].count;i+=1){o=record(2,i);ref(1,bytes[o+1]);var operator=ref(0,bytes[o+2]);if(bytes[o+3]>1)fail('coordinate flags');string(o+4,true);var short=string(o+6,true);string(o+8);var direction=string(o+10,true);string(o+12);string(o+14);var lat=i32(o+16),lon=i32(o+20);if(bytes[o+3]?(lat<-90000000||lat>90000000||lon<-180000000||lon>180000000):(lat!==-2147483648||lon!==-2147483648))fail('coordinates');catalog.push({id:bytes[o],label:short+' / '+string(operator+6,true)+' / '+direction});}
  var expectedCall=0;for(i=0;i<tables[3].count;i+=1){o=record(3,i);ref(0,bytes[o+1]);string(o+2,true);string(o+4,true);string(o+6);if(bytes[o+8])ref(1,bytes[o+8]);if(bytes[o+9]||u16(o+10)!==expectedCall||u16(o+10)+u16(o+12)>tables[9].count)fail('pattern calls');expectedCall+=u16(o+12);string(o+14);for(var j=0;j<u16(o+12);j+=1){var call=record(9,u16(o+10)+j),group=bytes[call+1];if(bytes[call]!==bytes[o])fail('pattern call slice');ref(1,group);}}
  if(expectedCall!==tables[9].count)fail('call layout');for(i=0;i<tables[4].count;i+=1){o=record(4,i);operator=ref(0,bytes[o+1]);if(!bytes[o+2]||(bytes[o+2]&~14)||(bytes[o+2]&~bytes[operator+1])||bytes[o+3]||date(o+4)>date(o+8)||i32(o+4)<i32(operator+8)||i32(o+8)>i32(operator+12))fail('service');}
  previous=-Infinity;
  for(i=0;i<tables[5].count;i+=1){o=record(5,i);a=date(o);if(a<=previous||a<calFrom||a>calUntil)fail('holiday ordering');previous=a;}
  var prevDate=-Infinity,prevOperator=0;
  for(i=0;i<tables[6].count;i+=1){o=record(6,i);a=date(o);operator=bytes[o+4];var opRecord=ref(0,operator);var day=bytes[o+5];if((day>3&&day!==255)||a<i32(opRecord+8)||a>i32(opRecord+12)||a<prevDate||(a===prevDate&&operator<=prevOperator))fail('exception');prevDate=a;prevOperator=operator;}
  var previousKey=null,maxMinute=0,tripServices={};
  for(i=0;i<tables[7].count;i+=1){o=record(7,i);var minute=u16(o),point=bytes[o+2],pattern=bytes[o+3],service=bytes[o+4],pointRecord=ref(2,point),patternRecord=ref(3,pattern),serviceRecord=ref(4,service);if(minute>4319||bytes[pointRecord+2]!==bytes[patternRecord+1]||bytes[pointRecord+2]!==bytes[serviceRecord+1])fail('departure reference');var key=[point,minute,pattern,service];if(previousKey){var ordered=false;for(j=0;j<4;j+=1){if(key[j]>previousKey[j]){ordered=true;break;}if(key[j]<previousKey[j])break;}if(!ordered)fail('departure ordering');}var tripKey=point+':'+minute+':'+pattern,prior=tripServices[tripKey]||[];prior.forEach(function(s){if((bytes[s+2]&bytes[serviceRecord+2])&&Math.max(i32(s+4),i32(serviceRecord+4))<=Math.min(i32(s+8),i32(serviceRecord+8)))fail('contradictory services');});prior.push(serviceRecord);tripServices[tripKey]=prior;previousKey=key;maxMinute=Math.max(maxMinute,minute);departures.push(key);}
  if(u16(60)!==maxMinute)fail('maximum minute');
  for(i=0;i<tables[8].count;i+=1){o=record(8,i);string(o,true);var sourceUrl=string(o+2,true);if(!/^https?:\/\//.test(sourceUrl))fail('source URL');date(o+4,true);v=date(o+8);r=date(o+12,true);if(r!==-2147483648&&r<v)fail('source review date');}
  var priorPattern=0,callCoverage={};
  for(i=0;i<tables[9].count;i+=1){o=record(9,i);pattern=bytes[o];ref(3,pattern);ref(1,bytes[o+1]);if(pattern<priorPattern)fail('call ordering');var pr=maps[3][pattern];if(i<u16(pr+10)||i>=u16(pr+10)+u16(pr+12))fail('unreferenced call');priorPattern=pattern;callCoverage[pattern]=true;}
  var metadata={version:u32(16),minAppVersion:u32(20),effectiveFrom:effective,coverageFrom:from,coverageThrough:until,sourceVerified:verified,reviewDue:review,coverage:coverage,catalog:catalog,departures:departures};
  if(release){if(metadata.version!==release.version||metadata.minAppVersion!==release.minAppVersion)fail('manifest version');['effectiveFrom','coverageFrom','coverageThrough','sourceVerified','reviewDue'].forEach(function(f){if(metadata[f]!==dates.date(release[f]))fail('manifest '+f);});}
  return metadata;
}
module.exports = {validate:validate};
