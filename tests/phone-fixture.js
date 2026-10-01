'use strict';
// Synthetic records used only by isolated tests, never by the app baseline.
var crc=require('../src/pkjs/checksums'),date=require('../src/pkjs/manifest').date;
module.exports=function(version,effective){
  var pool=[0],strings={'':0};
  function text(s){if(typeof strings[s]!=='undefined')return strings[s];var n=pool.length;Buffer.from(s,'utf8').forEach(function(b){pool.push(b);});pool.push(0);strings[s]=n;return n;}
  function record(length){return new Array(length).fill(0);}
  function put(a,o,n,bytes){for(var j=0;j<bytes;j+=1)a[o+j]=n>>>8*j&255;}
  function str(a,o,s){put(a,o,text(s),2);}
  var from=date('2026-01-01'),until=date('2027-12-31'),verified=date('2026-09-30'),review=date('2026-11-01');
  var operator=record(28);operator[0]=1;operator[1]=14;str(operator,2,'Fixture operator');str(operator,4,'試験');str(operator,6,'Test');put(operator,8,from,4);put(operator,12,until,4);put(operator,16,verified,4);put(operator,20,review,4);put(operator,26,1,2);
  var groups=[],points=[],patterns=[],services=[],calls=[];
  for(var i=1;i<=2;i+=1){
    var g=record(8);g[0]=i;str(g,2,'Fixture '+i);str(g,4,'Synthetic fixture stop '+i);str(g,6,'試験'+i);groups=groups.concat(g);
    var point=record(24);point[0]=i;point[1]=i;point[2]=1;point[3]=1;str(point,4,'Fixture stop '+i);str(point,6,'Fixture '+i);str(point,8,'試験');str(point,10,i===1?'Ibaraki':'University');put(point,16,34810000+i*10,4);put(point,20,135527000,4);points=points.concat(point);
    var pattern=record(16);pattern[0]=i;pattern[1]=1;str(pattern,2,String(i));str(pattern,4,i===1?'Ibaraki':'University');pattern[8]=i;put(pattern,10,i-1,2);put(pattern,12,1,2);patterns=patterns.concat(pattern);calls.push(i,i);
  }
  for(i=1;i<=3;i+=1){var service=record(12);service[0]=i;service[1]=1;service[2]=1<<i;put(service,4,from,4);put(service,8,until,4);services=services.concat(service);}
  var holiday=record(4);put(holiday,0,date('2026-10-12'),4);
  var exception=record(6);put(exception,0,date('2026-12-31'),4);exception[4]=1;exception[5]=0;
  var departures=[];[[600,1,1,1],[1500,1,1,1],[620,2,2,2]].forEach(function(d){var a=record(5);put(a,0,d[0],2);a[2]=d[1];a[3]=d[2];a[4]=d[3];departures=departures.concat(a);});
  var source=record(16);str(source,0,'SYNTHETIC TEST ONLY');str(source,2,'https://example.invalid/fixture');put(source,4,from,4);put(source,8,verified,4);put(source,12,review,4);
  var tables=[operator,groups,points,patterns,services,holiday,exception,departures,source,calls],strides=[28,8,24,16,12,4,6,5,16,2],bytes=record(128),offset=128;
  [75,66,84,49].forEach(function(b,n){bytes[n]=b;});put(bytes,4,1,2);put(bytes,6,128,2);put(bytes,16,version||2,4);put(bytes,20,1,4);put(bytes,24,from,4);put(bytes,28,until,4);put(bytes,32,from,4);put(bytes,36,until,4);put(bytes,40,verified,4);put(bytes,44,review,4);str(bytes,48,'minami-kasugaoka-v1');put(bytes,60,1500,2);put(bytes,62,10,2);put(bytes,124,date(effective||'2026-01-01'),4);
  tables.forEach(function(a,n){put(bytes,64+n*6,offset,4);put(bytes,68+n*6,a.length/strides[n],2);offset+=a.length;bytes=bytes.concat(a);});
  put(bytes,52,offset,4);put(bytes,56,pool.length,4);bytes=bytes.concat(pool);put(bytes,8,bytes.length,4);put(bytes,12,crc.crc32(bytes,16),4);
  return bytes;
};
module.exports.release=function(bytes,url){function u32(o){return(bytes[o]+bytes[o+1]*256+bytes[o+2]*65536+bytes[o+3]*16777216)>>>0;}function day(o){return new Date((u32(o)|0)*86400000).toISOString().slice(0,10);}return{version:u32(16),minAppVersion:u32(20),effectiveFrom:day(124),coverageFrom:day(24),coverageThrough:day(28),sourceVerified:day(40),reviewDue:day(44),url:url,bytes:bytes.length,sha256:crc.sha256(bytes),crc32:crc.crc32(bytes)};};
