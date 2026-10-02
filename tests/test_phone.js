'use strict';
var assert=require('assert'),crypto=require('crypto'),fixture=require('./phone-fixture'),hash=require('../src/pkjs/checksums'),manifest=require('../src/pkjs/manifest'),binary=require('../src/pkjs/binary'),settings=require('../src/pkjs/settings'),nearby=require('../src/pkjs/nearby'),createTransfer=require('../src/pkjs/transfer'),createUpdater=require('../src/pkjs/updater');
var config={manifestUrl:'https://feed.example/manifest.json',coverage:'minami-kasugaoka-v1',appVersion:1,maxPayload:32768,manifestMaxBytes:8192,requestTimeout:15000},now=Date.parse('2026-10-01T00:00:00Z');
function clone(v){return JSON.parse(JSON.stringify(v));}
function clock(){var time=now,timers=[],id=0;return{now:function(){return time;},schedule:function(fn,delay){timers.push({id:++id,at:time+delay,fn:fn});return id;},cancel:function(n){timers=timers.filter(function(t){return t.id!==n;});},advance:function(ms){var target=time+ms;while(true){timers.sort(function(a,b){return a.at-b.at;});if(!timers.length||timers[0].at>target)break;var timer=timers.shift();time=timer.at;timer.fn();}time=target;}};}
var count=0;function test(name,fn){fn();count+=1;console.log('PASS '+name);}
test('protocol preserves unsigned words through signed PebbleKit tuples',function(){var p=require('../src/pkjs/protocol'),message={TYPE:5,SESSION:4294967295,CRC:0xcbf43926,STAMP:2147483648,DATA:[255,128,0]},wire=p.wire(message);assert.strictEqual(wire.SESSION,-1);assert.strictEqual(wire.CRC,-873187034);assert.strictEqual(wire.STAMP,-2147483648);assert.strictEqual(p.get(wire,'SESSION'),4294967295);assert.strictEqual(p.get({'5':wire.CRC},'CRC'),0xcbf43926);assert.strictEqual(p.get(wire,'STAMP'),2147483648);assert.strictEqual(wire.DATA,message.DATA);assert.strictEqual(message.SESSION,4294967295);});
test('shared sender waits for transport callback after an early application ACK',function(){var c=clock(),wire=[],sender=require('../src/pkjs/sender')(Object.assign(c,{send:function(message,ok,fail){wire.push({message:message,ok:ok,fail:fail});}})),t=createTransfer(Object.assign({},c,{send:sender}));t.start([1,2],{version:2,crc32:0xcbf43926},function(){},0);assert.strictEqual(wire.length,1);assert.strictEqual(wire[0].message.CRC,-873187034);t.receive({TYPE:8,SESSION:wire[0].message.SESSION,SEQ:0,STATUS:0,FLAGS:5});assert.strictEqual(wire.length,1,'CHUNK must wait for BEGIN transport callback');assert.strictEqual(sender.pending(),2);wire[0].ok();assert.strictEqual(wire.length,2);assert.strictEqual(wire[1].message.TYPE,6);t.receive({TYPE:8,SESSION:wire[1].message.SESSION,SEQ:0,STATUS:0,FLAGS:6});assert.strictEqual(wire.length,2,'COMMIT must wait for CHUNK transport callback');wire[1].ok();assert.strictEqual(wire[2].message.TYPE,7);t.receive({TYPE:8,SESSION:wire[2].message.SESSION,SEQ:65535,STATUS:3,FLAGS:7});wire[2].ok();assert.strictEqual(sender.pending(),0);});
test('shared sender bounds FIFO and handles NACK without concurrent transactions',function(){var c=clock(),wire=[],results=[],sender=require('../src/pkjs/sender')(Object.assign(c,{maxQueue:2,send:function(message,ok,fail){wire.push({message:message,ok:ok,fail:fail});}}));sender({TYPE:1},function(){results.push('first');});sender({TYPE:2},null,function(error){results.push(error.message);});assert.strictEqual(sender({TYPE:3},null,function(error){results.push(error.message);}),false);assert.strictEqual(wire.length,1);assert.strictEqual(sender.pending(),2);wire[0].ok();assert.strictEqual(wire.length,2);assert.strictEqual(wire[1].message.TYPE,2);wire[1].fail(new Error('Native NACK'));assert.deepStrictEqual(results,['Transport queue is full','first','Native NACK']);assert.strictEqual(sender.pending(),0);});
test('shared sender timeout blocks new transactions until callback or reconnect',function(){var c=clock(),wire=[],errors=[],sender=require('../src/pkjs/sender')(Object.assign(c,{send:function(message,ok,fail){wire.push({message:message,ok:ok,fail:fail});}}));sender({TYPE:1},null,function(e){errors.push(e.message);});sender({TYPE:2},null,function(e){errors.push(e.message);});c.advance(10000);assert.deepStrictEqual(errors,['Transport acknowledgement timeout','Transport unavailable']);assert.strictEqual(sender({TYPE:3},null,function(e){errors.push(e.message);}),false);assert.strictEqual(wire.length,1);wire[0].ok();sender({TYPE:4});assert.strictEqual(wire.length,2);sender.reset();sender({TYPE:5});assert.strictEqual(wire.length,3);wire[1].ok();assert.strictEqual(sender.pending(),1,'old callback cannot complete a new transaction');wire[2].ok();assert.strictEqual(sender.pending(),0);});
test('shared sender reports immediate SDK exceptions once',function(){var c=clock(),errors=[],sender=require('../src/pkjs/sender')(Object.assign(c,{send:function(){throw new Error('SDK unavailable');}}));sender({TYPE:1},null,function(error){errors.push(error.message);});assert.deepStrictEqual(errors,['SDK unavailable']);assert.strictEqual(sender.pending(),0);c.advance(10000);assert.strictEqual(errors.length,1);});
test('standard CRC32 and SHA256 vectors',function(){[[],[97,98,99],Array.from({length:32768},function(_,n){return n&255;})].forEach(function(bytes){assert.strictEqual(hash.sha256(bytes),crypto.createHash('sha256').update(Buffer.from(bytes)).digest('hex'));});assert.strictEqual(hash.crc32(Array.from(Buffer.from('123456789'))),0xcbf43926);});
var bytes=fixture(2),release=fixture.release(bytes,'https://feed.example/releases/2.bin'),feed={schema:1,coverage:config.coverage,published:'2026-10-01',current:release,upcoming:null};
test('valid complete binary and manifest agree',function(){assert.strictEqual(manifest.validate(feed,config,now).current.version,2);var v=binary.validate(bytes,config,release);assert.strictEqual(v.departures.length,3);assert.strictEqual(v.catalog.length,2);});
test('reject malformed dates, versions, hosts, lengths, compatibility and future current',function(){[
  function(f){f.current.coverageThrough='2026-02-30';},function(f){f.current.url='http://feed.example/x.bin';},function(f){f.current.url='https://evil.example/x.bin';},function(f){f.current.url='https://feed.example/a/../x.bin';},function(f){f.current.url='https://feed.example/x.bin?redirect=1';},function(f){f.current.bytes=32769;},function(f){f.current.version=0;},function(f){f.current.minAppVersion=2;},function(f){f.schema=2;},function(f){f.coverage='other';},function(f){f.current.effectiveFrom='2026-11-01';},function(f){f.published='2026-02-30';}
].forEach(function(mutate){var f=clone(feed);mutate(f);assert.throws(function(){manifest.validate(f,config,now);});});assert.throws(function(){manifest.origin('http://127.0.0.1:8080/manifest.json',false);});});
function repair(b){var crc=hash.crc32(b,16);for(var i=0;i<4;i+=1)b[12+i]=crc>>>i*8&255;return b;}
test('binary rejects corrupt payload, references, sort, flags, time and UTF8',function(){[function(b){b[130]=255;},function(b){b[50]=1;},function(b){b[128+28+16+3]=2;},function(b){var o=b[64+7*6]+b[65+7*6]*256;b[o]=255;b[o+1]=255;},function(b){var o=b[64+7*6]+b[65+7*6]*256;b[o+2]=99;},function(b){b[b.length-2]=192;},function(b){b[64]=129;}].forEach(function(mutate){var b=bytes.slice();mutate(b);repair(b);assert.throws(function(){binary.validate(b,config);});});var b=bytes.slice();b[150]^=1;assert.throws(function(){binary.validate(b,config);});assert.throws(function(){binary.validate(bytes,config,Object.assign({},release,{sha256:'0'.repeat(64)}));});});
var catalog=[{id:1,label:'Stop one'},{id:2,label:'Stop two'}],preferences={flags:17,defaultId:1,buffer:2,textSize:1,theme:0,favourites:[2,1],walks:{1:5,2:0}};
test('fixed80B atomic preference roundtrip, explicit unset versus zero',function(){var b=settings.encode(preferences,catalog);assert.strictEqual(b.length,80);assert.deepStrictEqual(settings.decode(b,catalog),preferences);var v=settings.toClay(preferences,catalog);assert.deepStrictEqual(settings.fromClay(v,catalog),preferences);v.Walk1='';assert.strictEqual(settings.fromClay(v,catalog).walks[1],undefined);assert.strictEqual(settings.fromClay(v,catalog).walks[2],0);});
test('raw startup Nearby requires phone location while Clay turns startup off with location',function(){var s=clone(preferences);s.flags=4;assert.throws(function(){settings.encode(s,catalog);},/requires phone location/);s.flags=6;s.defaultId=0;assert.strictEqual(settings.decode(settings.encode(s,catalog),catalog).defaultId,0);var values=settings.toClay(s,catalog);values.LocationEnabled=false;assert.strictEqual(settings.fromClay(values,catalog).flags&6,0);var invalid=settings.encode(preferences,catalog);invalid[1]=4;assert.throws(function(){settings.decode(invalid,catalog);},/requires phone location/);});
test('all Clay Nearby dependency combinations preserve the other80B fields and never imply OS permission',function(){
  var s=clone(preferences);s.textSize=2;s.theme=3;s.flags=25;
  [false,true].forEach(function(location){[false,true].forEach(function(startup){
    var values=settings.toClay(s,catalog);values.LocationEnabled={value:location};values.NearbyStartup={value:startup};
    var parsed=settings.fromClay(values,catalog),encoded=settings.encode(parsed,catalog),expected=clone(s);
    expected.flags=25|(location?2:0)|(location&&startup?4:0);assert.deepStrictEqual(parsed,expected);assert.deepStrictEqual(settings.decode(encoded,catalog),expected);
    var visible=settings.toClay(parsed,catalog);assert.strictEqual(visible.LocationEnabled,location);assert.strictEqual(visible.NearbyStartup,location&&startup);
  });});
});
test('invalid duplicate/unknown/outofrange/padded preferences reject',function(){[function(s){s.favourites=[1,1];},function(s){s.defaultId=99;},function(s){s.walks[1]=121;},function(s){s.buffer=31;},function(s){s.flags=32;}].forEach(function(m){var s=clone(preferences);m(s);assert.throws(function(){settings.encode(s,catalog);});});var b=settings.encode(preferences,catalog);b[6]=3;assert.throws(function(){settings.decode(b,catalog);});b=settings.encode(preferences,catalog);b[34]=256;assert.throws(function(){settings.decode(b,catalog);});var v=settings.toClay(preferences,catalog);v.Walk99='4';assert.throws(function(){settings.fromClay(v,catalog);});});
test('all three text sizes and four themes roundtrip without changing other preferences',function(){
  var original=settings.encode(preferences,catalog);
  for(var size=0;size<3;size+=1)for(var theme=0;theme<4;theme+=1){
    var s=clone(preferences);s.textSize=size;s.theme=theme;s.flags=17|(theme>=2?8:0);
    var bytes=settings.encode(s,catalog),values=settings.toClay(s,catalog);
    assert.strictEqual(bytes[0],2);assert.strictEqual(bytes[6],size);assert.strictEqual(bytes[7],theme);
    assert.strictEqual(bytes[1]&8,theme>=2?8:0);assert.strictEqual(bytes[1]&~8,17);
    assert.deepStrictEqual(bytes.slice(2,6),original.slice(2,6));assert.deepStrictEqual(bytes.slice(8),original.slice(8));
    assert.deepStrictEqual(settings.decode(bytes,catalog),s);assert.deepStrictEqual(settings.fromClay(values,catalog),s);
    assert.strictEqual(values.HighContrast,undefined);
  }
});
test('v1 migration preserves flags and boarding allowances while selecting Large and the legacy theme',function(){
  [0,8].forEach(function(contrast){
    var legacy=settings.encode(preferences,catalog);legacy[0]=1;legacy[1]=23|contrast;legacy[6]=0;legacy[7]=0;
    var decoded=settings.decode(legacy,catalog),upgraded=settings.encode(decoded,catalog);
    assert.strictEqual(decoded.textSize,1);assert.strictEqual(decoded.theme,contrast?2:0);assert.strictEqual(decoded.flags,23|contrast);
    assert.deepStrictEqual(decoded.favourites,preferences.favourites);assert.deepStrictEqual(decoded.walks,preferences.walks);
    assert.strictEqual(upgraded[0],2);assert.strictEqual(upgraded[6],1);assert.strictEqual(upgraded[7],contrast?2:0);
    assert.strictEqual(upgraded[1],legacy[1]);assert.deepStrictEqual(upgraded.slice(2,6),legacy.slice(2,6));assert.deepStrictEqual(upgraded.slice(8),legacy.slice(8));
    [6,7].forEach(function(offset){var bad=legacy.slice();bad[offset]=1;assert.throws(function(){settings.decode(bad,catalog);});});
  });
});
test('theme canonicalizes the contrast mirror without mutating the caller or dropping flags',function(){
  for(var theme=0;theme<4;theme+=1){
    var s=clone(preferences);s.theme=theme;s.flags=23|(theme<2?8:0);var before=clone(s);
    var bytes=settings.encode(s,catalog);assert.deepStrictEqual(s,before);assert.strictEqual(bytes[1],23|(theme>=2?8:0));
    bytes[1]=s.flags;assert.strictEqual(settings.decode(bytes,catalog).flags,23|(theme>=2?8:0));
  }
});
test('appearance choices reject unknown schemas, invalid bytes and malformed Clay selections',function(){
  [undefined,null,-1,3,1.5,NaN,Infinity,'1',true].forEach(function(size){var s=clone(preferences);s.textSize=size;assert.throws(function(){settings.encode(s,catalog);});});
  [undefined,null,-1,4,1.5,NaN,Infinity,'2',false].forEach(function(theme){var s=clone(preferences);s.theme=theme;assert.throws(function(){settings.encode(s,catalog);});});
  [0,3,255].forEach(function(schema){var b=settings.encode(preferences,catalog);b[0]=schema;assert.throws(function(){settings.decode(b,catalog);});});
  [function(b){b[6]=3;},function(b){b[7]=4;},function(b){b[1]=32;},function(b){delete b[79];}].forEach(function(mutate){var b=settings.encode(preferences,catalog);mutate(b);assert.throws(function(){settings.decode(b,catalog);});});
  ['TextSize','Theme'].forEach(function(key){['',null,true,false,' ','1.5','-1','NaN',key==='Theme'?'4':'3'].forEach(function(value){var values=settings.toClay(preferences,catalog);values[key]=value;assert.throws(function(){settings.fromClay(values,catalog);});});});
  var wrapped=settings.toClay(preferences,catalog);wrapped.TextSize={value:'2'};wrapped.Theme={value:'3'};wrapped.HighContrast=false;
  var decoded=settings.fromClay(wrapped,catalog);assert.strictEqual(decoded.textSize,2);assert.strictEqual(decoded.theme,3);assert.strictEqual(decoded.flags,25);
});
test('portable C and phone agree on the complete80B appearance contract, migration and rejection',function(){
  var fs=require('fs'),os=require('os'),path=require('path'),child=require('child_process'),directory=fs.mkdtempSync(path.join(os.tmpdir(),'kasugabus-pref-contract-'));
  try{
    var harness=path.join(directory,'contract.c'),executable=path.join(directory,'contract');
    fs.writeFileSync(harness,'#include "preferences.h"\n#include <stdio.h>\nstatic bool exists(void *ctx,uint16_t id){(void)ctx;return id==1||id==2||id==513;}\nint main(int argc,char **argv){(void)argv;kb_preferences_t p;uint8_t bytes[80];if(argc>1){kb_preferences_default(&p,513);}else{for(unsigned i=0;i<80;i++){unsigned n;if(scanf("%u",&n)!=1||n>255)return 2;bytes[i]=(uint8_t)n;}if(!kb_preferences_parse(&p,bytes,80,exists,NULL)){puts("invalid");return 0;}}for(unsigned i=0;i<80;i++)printf("%02x",p.bytes[i]);putchar(10);return 0;}\n');
    var compiled=child.spawnSync('cc',['-std=c11','-Wall','-Wextra','-Werror','-I',path.resolve(__dirname,'../src/c'),harness,path.resolve(__dirname,'../src/c/preferences.c'),'-o',executable],{encoding:'utf8'});
    assert.strictEqual(compiled.status,0,compiled.stderr);
    function native(bytes){var result=child.spawnSync(executable,[],{input:bytes.join(' '),encoding:'utf8'});assert.strictEqual(result.status,0,result.stderr);return result.stdout.trim();}
    var fullCatalog=catalog.concat([{id:513,label:'Wide ID'}]);
    var vector={flags:23,defaultId:513,buffer:9,textSize:2,theme:3,favourites:[513,2],walks:{2:120,513:0}};
    var fixedHex='021f01020902020301020200'+'00'.repeat(20)+'0200780001020000'+'00'.repeat(40);
    assert.strictEqual(Buffer.from(settings.encode(vector,fullCatalog)).toString('hex'),fixedHex);assert.strictEqual(native(Array.from(Buffer.from(fixedHex,'hex'))),fixedHex);
    for(var size=0;size<3;size+=1)for(var theme=0;theme<4;theme+=1){
      var s=clone(vector);s.textSize=size;s.theme=theme;var bytes=settings.encode(s,fullCatalog);bytes[1]=23|(theme<2?8:0);
      assert.strictEqual(native(bytes),Buffer.from(settings.encode(settings.decode(bytes,fullCatalog),fullCatalog)).toString('hex'));
    }
    [23,31].forEach(function(flags){var b=settings.encode(vector,fullCatalog);b[0]=1;b[1]=flags;b[6]=0;b[7]=0;assert.strictEqual(native(b),Buffer.from(settings.encode(settings.decode(b,fullCatalog),fullCatalog)).toString('hex'));});
    [function(b){b[0]=3;},function(b){b[6]=3;},function(b){b[7]=4;},function(b){b[0]=1;b[6]=1;b[7]=0;},function(b){b[0]=1;b[6]=0;b[7]=1;},function(b){b[1]=4;},function(b){b[1]=32;},function(b){b[35]=1;}].forEach(function(mutate){var b=settings.encode(vector,fullCatalog);mutate(b);assert.throws(function(){settings.decode(b,fullCatalog);});assert.strictEqual(native(b),'invalid');});
    var defaultBytes=child.spawnSync(executable,['default'],{encoding:'utf8'});assert.strictEqual(defaultBytes.status,0,defaultBytes.stderr);
    assert.deepStrictEqual(settings.decode(Array.from(Buffer.from(defaultBytes.stdout.trim(),'hex')),fullCatalog),{flags:1,defaultId:513,buffer:2,textSize:1,theme:0,favourites:[513],walks:{}});
  }finally{fs.rmSync(directory,{recursive:true,force:true});}
});
function position(age,accuracy,latitude){return{timestamp:now-age,coords:{latitude:latitude||34.81,longitude:135.527,accuracy:accuracy}};}
test('Nearby good, stale, poor, outside, missing and stable uncertainty ties',function(){var points=[{id:2,lat:34.81001,lon:135.527,order:0},{id:1,lat:34.81,lon:135.527,order:1}];var result=nearby.rank(position(120000,100),points,now);assert.strictEqual(result.status,0);assert.strictEqual(result.data[0],2);assert.strictEqual(nearby.rank(position(120001,10),points,now).status,2);assert.strictEqual(nearby.rank(position(0,101),points,now).status,1);assert.strictEqual(nearby.rank(position(0,10,35.5),points,now).status,6);assert.strictEqual(nearby.rank(position(0,10),[],now).status,7);assert.strictEqual(nearby.rank({timestamp:now,coords:{latitude:NaN,longitude:135,accuracy:1}},points,now).status,5);});
test('Nearby stale and poor fixes retain real bounded metadata without ranking rows',function(){var points=[{id:1,lat:34.81,lon:135.527,order:0}],stale=position(120001,12.1),poor=position(0,101.2);[stale,poor].forEach(function(fix){var result=nearby.rank(fix,points,now);assert.strictEqual(result.status,fix===stale?2:1);assert.strictEqual(result.stamp,Math.floor(fix.timestamp/1000));assert.strictEqual(result.accuracy,Math.ceil(fix.coords.accuracy));assert.strictEqual(result.data,undefined);var c=clock(),out=[],n=nearby(Object.assign(c,{send:function(m){out.push(m);},geolocation:{getCurrentPosition:function(ok){ok(fix);}}}));n.request(9,2,[1,0,0,0,0,0,0,0,0,0],true);assert.strictEqual(out[0].STATUS,result.status);assert.strictEqual(out[0].STAMP,result.stamp);assert.strictEqual(out[0].ACCURACY,result.accuracy);assert.strictEqual(out[0].DATA,undefined);c.advance(15000);assert.strictEqual(out.length,1);});// Unusable companion fix times are treated as just received (fresh requests only).
[NaN,Infinity,-1,4294967296000].forEach(function(stamp){var fix=position(0,10);fix.timestamp=stamp;var result=nearby.rank(fix,points,now);assert.strictEqual(result.status,0);assert.strictEqual(result.stamp,Math.floor(now/1000));});var bad=position(0,10);bad.coords.accuracy=NaN;assert.strictEqual(nearby.rank(bad,points,now).status,5,'coordinates and accuracy stay strictly validated');var future=position(-5001,10);assert.strictEqual(nearby.rank(future,points,now).status,2);assert.strictEqual(nearby.rank(future,points,now).stamp,undefined);var oversized=position(0,4294967296);assert.strictEqual(nearby.rank(oversized,points,now).status,5);var zero=position(0,10);zero.timestamp=0;assert.strictEqual(nearby.rank(zero,points,now).stamp,Math.floor(now/1000),'a zero companion time means unknown, not 1970');});
test('Nearby denied, unavailable, timeout, missing/throwing API and NaN fix use explicit error states',function(){var fixtures=[{api:{getCurrentPosition:function(ok,error){error({code:1});}},status:3},{api:{getCurrentPosition:function(ok,error){error({code:2});}},status:9},{api:{getCurrentPosition:function(ok,error){error({code:3});}},status:4},{api:null,status:5},{api:{},status:5},{api:{getCurrentPosition:function(){throw new Error('GPS failure');}},status:5},{api:{getCurrentPosition:function(ok){var fix=position(0,1);fix.coords.accuracy=NaN;ok(fix);}},status:5}];fixtures.forEach(function(fixture){var c=clock(),out=[],n=nearby(Object.assign(c,{send:function(m){out.push(m);},geolocation:fixture.api}));n.request(11,2,[1,0,0,0,0,0,0,0,0,0],true);assert.strictEqual(out.length,1);assert.strictEqual(out[0].STATUS,fixture.status);assert.strictEqual(out[0].STAMP,undefined);assert.strictEqual(out[0].ACCURACY,undefined);assert.strictEqual(out[0].DATA,undefined);c.advance(15000);assert.strictEqual(out.length,1);});});
test('one-shot geolocation timeout and obsolete request suppression',function(){var c=clock(),out=[],callbacks=[],opts=Object.assign(c,{send:function(m){out.push(m);},geolocation:{getCurrentPosition:function(ok,error,opt){callbacks.push({ok:ok,error:error});assert.strictEqual(opt.maximumAge,0);}}});var n=nearby(opts),coords=[1,0,0,0,0,0,0,0,0,0];n.request(1,1,coords,true);n.request(2,1,coords,true);callbacks[0].ok(position(0,1));assert.strictEqual(out.length,0);c.advance(15000);assert.strictEqual(out[0].REQUEST,2);assert.strictEqual(out[0].STATUS,4);callbacks[1].ok(position(0,1));assert.strictEqual(out.length,1);n.request(3,1,coords,false);assert.strictEqual(out[1].STATUS,8);});
test('Nearby retries one coarse network fix when precise GPS has no position or times out',function(){[2,3].forEach(function(code){var c=clock(),out=[],calls=[],api={getCurrentPosition:function(ok,error,opts){calls.push(opts);if(opts.enableHighAccuracy)error({code:code});else ok(position(0,40));}},n=nearby(Object.assign(c,{send:function(m){out.push(m);},geolocation:api}));n.request(12,2,[1,0,0,0,0,0,0,0,0,0],true);assert.strictEqual(calls.length,2);assert.deepStrictEqual([calls[0].enableHighAccuracy,calls[1].enableHighAccuracy,calls[1].maximumAge],[true,false,60000]);assert.ok(calls[0].timeout+calls[1].timeout<15000);assert.strictEqual(out.length,1);assert.notStrictEqual(out[0].STATUS,9);});var c=clock(),out=[],calls=0,n=nearby(Object.assign(c,{send:function(m){out.push(m);},geolocation:{getCurrentPosition:function(ok,error){calls+=1;error({code:1});}}}));n.request(13,2,[1,0,0,0,0,0,0,0,0,0],true);assert.strictEqual(calls,1,'permission denial is not retried');assert.strictEqual(out[0].STATUS,3);});
test('Nearby accepts companion fix times as Date, string, seconds, micro/nanoseconds or missing',function(){var now=1790900000000,f=require('../src/pkjs/nearby').fixTime;[[now-2000,now-2000],[new Date(now-2000),now-2000],[String(now-2000),now-2000],[new Date(now-2000).toISOString(),now-2000],[(now-2000)/1000,now-2000],[(now-2000)*1000,now-2000],[(now-2000)*1e6,now-2000],[undefined,now],[null,now],['soon',now],[NaN,now],[-5,now],[now-30*86400000,now]].forEach(function(row){assert.ok(Math.abs(f(row[0],now)-row[1])<1,String(row[0]));});var fix=position(0,12);var points=[{id:1,lat:fix.coords.latitude,lon:fix.coords.longitude,order:0}];var c=clock();delete fix.timestamp;var r=require('../src/pkjs/nearby').rank(fix,points,c.now());assert.strictEqual(r.status,0,'a fix without a timestamp is ranked as just received');});
test('transfer ignores old session/sequence, acknowledges chunks, retries same bytes',function(){var c=clock(),out=[],complete=[],t=createTransfer(Object.assign(c,{send:function(m){out.push(m);}}));t.start(bytes,release,function(e,status){complete.push({error:e,status:status});},7);var begin=out[0];assert.ok(begin.SESSION>0&&begin.SESSION<=2147483647);assert.strictEqual(begin.REQUEST,7);t.receive({TYPE:8,SESSION:begin.SESSION+1,SEQ:0,STATUS:0,FLAGS:5});assert.strictEqual(out.length,1);c.advance(2000);assert.deepStrictEqual(out[1],begin);t.receive({TYPE:8,SESSION:begin.SESSION,SEQ:0,STATUS:0,FLAGS:5});assert.strictEqual(out[2].TYPE,6);t.receive({TYPE:8,SESSION:begin.SESSION,SEQ:0,STATUS:0,FLAGS:5});assert.strictEqual(out.length,3,'late BEGIN ACK cannot advance first chunk');t.receive({TYPE:8,SESSION:begin.SESSION,SEQ:99,STATUS:0,FLAGS:6});assert.strictEqual(out.length,3);while(t.busy()){var m=out[out.length-1];assert.ok(!m.DATA||m.DATA.length<=192);t.receive({TYPE:8,SESSION:m.SESSION,SEQ:m.TYPE===7?65535:m.SEQ||0,STATUS:m.TYPE===7?4:0,FLAGS:m.TYPE});}assert.strictEqual(complete[0].status,4);});
test('transfer gives up after bounded retries without COMMIT',function(){var c=clock(),out=[],error=null,t=createTransfer(Object.assign(c,{send:function(m){out.push(m);}}));t.start(bytes,release,function(e){error=e;},8);c.advance(8000);assert.ok(error);assert.strictEqual(out.length,4);assert.strictEqual(out.some(function(m){return m.TYPE===7;}),false);});
test('unconfigured feed never makes network attempt or successful stamp',function(){var c=clock(),out=[],calls=0,u=createUpdater(Object.assign(c,{config:Object.assign({},config,{manifestUrl:null}),send:function(m){out.push(m);},fetch:function(){calls+=1;}}));u.state({version:1,pending:0,flags:1});u.check(1,true);assert.strictEqual(calls,0);assert.strictEqual(out[0].STATUS,7);assert.strictEqual(out[0].STAMP,undefined);});
test('watch-owned one-inflight and no downgrade/rewrite',function(){var c=clock(),out=[],calls=[],callbacks=[],u=createUpdater(Object.assign(c,{config:config,send:function(m){out.push(m);},fetch:function(url,max,binary,timeout,cb){calls.push(url);callbacks.push(cb);}}));u.state({version:2,pending:3,flags:1});u.check(7,false);u.check(8,true);assert.strictEqual(calls.length,1);callbacks[0](null,JSON.stringify(feed));assert.strictEqual(out[out.length-1].STATUS,2);assert.ok(out[out.length-1].STAMP);assert.strictEqual(calls.length,1);});
test('transfer requires the explicit watch request including zero',function(){var c=clock(),out=[],errors=[],t=createTransfer(Object.assign(c,{send:function(m){out.push(m);}}));t.start(bytes,release,function(e){errors.push(e);});assert.strictEqual(out.length,0);assert.match(errors[0].message,/request/);t.start(bytes,release,function(){},0);assert.strictEqual(out[0].REQUEST,0);t.cancel();});
function updaterHarness(){
  var c=clock(),out=[],requests=[],u=createUpdater(Object.assign(c,{config:config,send:function(m){out.push(m);},fetch:function(url,max,binary,timeout,cb){var pending={url:url,binary:binary,callback:cb,aborted:0};requests.push(pending);return function(){pending.aborted+=1;cb(new Error('Aborted synchronously'));};}}));
  u.state({version:1,pending:0,flags:1,request:7});
  return{u:u,out:out,requests:requests,clock:c};
}
function completeTransfer(h,status){
  while(h.u.busy()){
    var m=h.out[h.out.length-1];if(m.TYPE!==5&&m.TYPE!==6&&m.TYPE!==7)break;
    h.u.receive({TYPE:8,SESSION:m.SESSION,SEQ:m.TYPE===7?65535:m.SEQ||0,STATUS:m.TYPE===7?status:0,FLAGS:m.TYPE});
  }
}
test('Restore during manifest or payload download aborts once and suppresses obsolete callbacks',function(){
  ['manifest','payload'].forEach(function(stage){
    var h=updaterHarness();h.u.check(7,true);
    if(stage==='payload')h.requests[0].callback(null,JSON.stringify(feed));
    var obsolete=h.requests[h.requests.length-1];h.u.cancel();
    assert.strictEqual(obsolete.aborted,1);assert.strictEqual(h.u.busy(),false);
    assert.strictEqual(h.out[h.out.length-1].STATUS,5);assert.strictEqual(h.out[h.out.length-1].REQUEST,7);
    h.u.state({version:1,pending:0,flags:1,request:8});h.u.check(8,true);
    var newRequest=h.requests[h.requests.length-1],sent=h.out.length,fetches=h.requests.length;
    obsolete.callback(null,stage==='manifest'?JSON.stringify(feed):bytes);obsolete.callback(new Error('Late abort'));
    assert.strictEqual(h.out.length,sent);assert.strictEqual(h.requests.length,fetches);assert.strictEqual(h.u.busy(),true);
    h.u.cancel();assert.strictEqual(newRequest.aborted,1,'old callback must not clear the new cancellation handle');
    assert.strictEqual(h.out.some(function(m){return m.TYPE===5;}),false);
  });
});
test('Restore during transfer rejects old ACKs after a new check and binds BEGIN to its request',function(){
  var h=updaterHarness();h.u.check(7,true);h.requests[0].callback(null,JSON.stringify(feed));h.requests[1].callback(null,bytes);
  var obsolete=h.out[h.out.length-1];assert.strictEqual(obsolete.TYPE,5);assert.strictEqual(obsolete.REQUEST,7);
  h.u.cancel();h.u.state({version:1,pending:0,flags:1,request:8});h.u.check(8,true);
  h.requests[2].callback(null,JSON.stringify(feed));h.requests[3].callback(null,bytes);
  var current=h.out[h.out.length-1],sent=h.out.length;assert.strictEqual(current.REQUEST,8);assert.notStrictEqual(current.SESSION,obsolete.SESSION);
  h.u.receive({TYPE:8,SESSION:obsolete.SESSION,SEQ:0,STATUS:0,FLAGS:5});assert.strictEqual(h.out.length,sent);
  completeTransfer(h,3);assert.strictEqual(h.u.busy(),false);assert.strictEqual(h.out[h.out.length-1].REQUEST,8);assert.strictEqual(h.out[h.out.length-1].STATUS,3);
});
test('Restore between future and current downloads prevents the remaining current transfer',function(){
  var h=updaterHarness(),futureBytes=fixture(3,'2026-10-03'),future=fixture.release(futureBytes,'https://feed.example/releases/3.bin'),two=clone(feed);two.upcoming=future;
  h.u.check(7,true);h.requests[0].callback(null,JSON.stringify(two));assert.strictEqual(h.requests[1].url,future.url);
  h.requests[1].callback(null,futureBytes);completeTransfer(h,4);
  assert.strictEqual(h.requests[2].url,release.url);var currentDownload=h.requests[2],begins=h.out.filter(function(m){return m.TYPE===5;}).length;
  h.u.cancel();assert.strictEqual(currentDownload.aborted,1);currentDownload.callback(null,bytes);
  assert.strictEqual(h.out.filter(function(m){return m.TYPE===5;}).length,begins);assert.strictEqual(h.u.busy(),false);
  h.clock.advance(30000);assert.strictEqual(h.out.filter(function(m){return m.TYPE===5;}).length,begins);
});
test('synchronous fetch completion cannot retain an obsolete abort handle',function(){
  var c=clock(),out=[],aborts=0,u=createUpdater(Object.assign(c,{config:config,send:function(m){out.push(m);},fetch:function(url,max,isBinary,timeout,cb){cb(null,JSON.stringify(feed));return function(){aborts+=1;};}}));
  u.state({version:2,pending:0,flags:1});u.check(0,true);assert.strictEqual(u.busy(),false);u.cancel();assert.strictEqual(aborts,0);assert.strictEqual(out[out.length-1].STATUS,2);
});
var createReference=require('../src/pkjs/reference-location');
function referenceHarness(api,cache){
  var c=clock(),out=[],data=cache||{},callbacks=[],calls=0,failWrite=false,failClear=false,mode='success',transports=[];
  var storage={getItem:function(key){return typeof data[key]==='undefined'?null:data[key];},setItem:function(key,value){if(failWrite||(failClear&&JSON.parse(value).home===null))throw new Error('Storage unavailable');data[key]=value;},removeItem:function(key){if(failClear)throw new Error('Storage unavailable');delete data[key];}};
  var options=Object.assign({},c,{send:function(message,ok,fail){out.push(message);if(message.TYPE===16){transports.push({message:message,ok:ok,fail:fail});if(mode==='success'){ok();return true;}if(mode==='fail'||mode==='full'){fail(new Error('Transport unavailable'));return mode!=='full';}}},storage:storage,geolocation:typeof api==='undefined'?{getCurrentPosition:function(ok,error,opt){calls+=1;callbacks.push({ok:ok,error:error});assert.deepStrictEqual(opt,{enableHighAccuracy:true,timeout:15000,maximumAge:0});}}:api});
  return{reference:createReference(options),clock:c,out:out,data:data,callbacks:callbacks,options:options,transports:transports,sendMode:function(value){mode=value;},calls:function(){return calls;},failWrite:function(v){failWrite=v;},failClear:function(v){failClear=v;}};
}
var referencePoles=[1,0,0,0,0,0,0,0,0,0];
function homeFix(timestamp){return{timestamp:timestamp,coords:{latitude:0.0012345,longitude:0.0004321,accuracy:12.25}};}
function assertPrivateWire(messages){messages.forEach(function(message){
  Object.keys(message).forEach(function(key){assert.ok(['TYPE','STATUS','FLAGS','REQUEST','VERSION','STAMP','ACCURACY','DATA'].indexOf(key)!==-1,key);});
  assert.ok(!/latitude|longitude|coords|savedAt|0\.0012345|0\.0004321/.test(JSON.stringify(message)));
  if(message.TYPE===16)assert.deepStrictEqual(Object.keys(message).sort(),['STATUS','TYPE']);
  if(message.DATA){assert.strictEqual(message.TYPE,15);assert.strictEqual(message.STATUS,0);assert.strictEqual(message.DATA.length%6,0);}
});}
test('private home persists only on the phone and ranks a fixed reference without aging or another GPS request',function(){
  var h=referenceHarness();assert.strictEqual(h.reference.hasHome(),false);h.reference.request(1,1,2,referencePoles,true);assert.strictEqual(h.out[0].STATUS,9);assert.strictEqual(h.calls(),0);
  h.reference.saveCurrent(true);assert.strictEqual(h.calls(),1);h.callbacks[0].ok(homeFix(h.clock.now()));
  assert.strictEqual(h.reference.hasHome(),true);assert.deepStrictEqual(h.out[1],{TYPE:16,STATUS:0});assert.strictEqual(Object.keys(h.data).length,1);
  var raw=h.data[Object.keys(h.data)[0]],record=JSON.parse(raw);assert.strictEqual(record.home.savedAt,now);assert.strictEqual(record.home.coords.latitude,0.0012345);assert.strictEqual(record.pending,null);
  var reloaded=createReference(h.options);assert.strictEqual(reloaded.hasHome(),true);h.clock.advance(86400000*365);
  reloaded.request(1,2,2,referencePoles,true);var result=h.out[h.out.length-1];assert.strictEqual(result.TYPE,15);assert.strictEqual(result.FLAGS,1);assert.strictEqual(result.STATUS,0);assert.strictEqual(result.STAMP,Math.floor(h.clock.now()/1000));assert.strictEqual(result.ACCURACY,13);assert.strictEqual(h.calls(),1);assert.strictEqual(h.data[Object.keys(h.data)[0]],raw);
  reloaded.request(1,3,2,referencePoles,false);assert.strictEqual(h.out[h.out.length-1].STATUS,8);assert.strictEqual(h.calls(),1);
  reloaded.clear();assert.strictEqual(reloaded.hasHome(),false);assert.deepStrictEqual(h.out[h.out.length-1],{TYPE:16,STATUS:9});assert.strictEqual(Object.keys(h.data).length,0);assertPrivateWire(h.out);
});
test('current reference preserves all Nearby outcomes and never saves a current fix implicitly',function(){
  var fixtures=[{status:0,fix:{timestamp:now,coords:{latitude:0,longitude:0,accuracy:5}}},{status:1,fix:{timestamp:now,coords:{latitude:0,longitude:0,accuracy:101}}},{status:2,fix:{timestamp:now-120001,coords:{latitude:0,longitude:0,accuracy:5}}},{status:2,fix:{timestamp:now+5001,coords:{latitude:0,longitude:0,accuracy:5}}},{status:3,error:1},{status:4,error:3},{status:5,error:2},{status:5,fix:{timestamp:now,coords:{latitude:NaN,longitude:0,accuracy:5}}},{status:6,fix:{timestamp:now,coords:{latitude:45,longitude:0,accuracy:5}}}];
  fixtures.forEach(function(f){var h=referenceHarness({getCurrentPosition:function(ok,error){if(f.fix)ok(f.fix);else error({code:f.error});}});h.reference.request(0,1,2,referencePoles,true);assert.strictEqual(h.out[0].STATUS,f.status);assert.strictEqual(h.out[0].TYPE,15);assert.strictEqual(h.out[0].FLAGS,0);assert.strictEqual(h.reference.hasHome(),false);assert.strictEqual(Object.keys(h.data).length,0);if(f.status!==0)assert.strictEqual(h.out[0].DATA,undefined);assertPrivateWire(h.out);});
  [null,{}, {getCurrentPosition:function(){throw new Error('Unavailable');}}].forEach(function(api){var h=referenceHarness(api);h.reference.request(0,1,2,referencePoles,true);assert.strictEqual(h.out[0].STATUS,5);});
  var h=referenceHarness();h.reference.request(0,1,2,referencePoles,false);assert.strictEqual(h.out[0].STATUS,8);h.reference.request(0,2,2,[],true);assert.strictEqual(h.out[1].STATUS,7);h.reference.request(0,3,2,[1],true);assert.strictEqual(h.out[2].STATUS,5);assert.strictEqual(h.calls(),0);
  h.reference.request(0,4,2,referencePoles,true);h.clock.advance(15000);assert.strictEqual(h.out[3].STATUS,4);h.callbacks[0].ok(homeFix(h.clock.now()));assert.strictEqual(h.out.length,4);
});
test('home save rejects stale poor denied unavailable timeout and disabled fixes without replacing the old home',function(){
  var h=referenceHarness();h.reference.saveCurrent(true);h.callbacks[0].ok(homeFix(now));var raw=h.data[Object.keys(h.data)[0]],messages=h.out.length;
  [{status:1,mutate:function(f){f.coords.accuracy=101;}},{status:2,mutate:function(f){f.timestamp=now-120001;}},{status:2,mutate:function(f){f.timestamp=now+5001;}},{status:5,mutate:function(f){f.coords.latitude=NaN;}},{status:3,error:1},{status:4,error:3},{status:5,error:2}].forEach(function(f){var status;h.reference.saveCurrent(true,function(s){status=s;});var callback=h.callbacks[h.callbacks.length-1];if(f.error)callback.error({code:f.error});else{var fix=homeFix(now);f.mutate(fix);callback.ok(fix);}assert.strictEqual(status,f.status);assert.strictEqual(h.reference.hasHome(),true);assert.strictEqual(h.data[Object.keys(h.data)[0]],raw);assert.strictEqual(h.out.length,messages);});
  var before=h.calls();h.reference.saveCurrent(false);assert.strictEqual(h.calls(),before);assert.strictEqual(h.reference.lastActionStatus(),8);
  h.reference.saveCurrent(true);h.clock.advance(15000);assert.strictEqual(h.reference.lastActionStatus(),4);assert.strictEqual(h.out.length,messages);
});
test('atomic private-storage failures preserve the old home and never emit a false home-changed notification',function(){
  var h=referenceHarness();h.reference.saveCurrent(true);h.callbacks[0].ok(homeFix(now));var raw=h.data[Object.keys(h.data)[0]],messages=h.out.length;
  h.failWrite(true);h.reference.saveCurrent(true);var changed=homeFix(now);changed.coords.latitude=0.002;h.callbacks[1].ok(changed);assert.strictEqual(h.reference.hasHome(),true);assert.strictEqual(h.reference.lastActionStatus(),5);assert.strictEqual(h.data[Object.keys(h.data)[0]],raw);assert.strictEqual(h.out.length,messages);
  h.failWrite(false);h.reference.saveCurrent(true);h.failClear(true);assert.strictEqual(h.reference.clear(),false);h.callbacks[2].ok(changed);assert.strictEqual(h.reference.hasHome(),true);assert.strictEqual(h.data[Object.keys(h.data)[0]],raw);assert.strictEqual(h.out.length,messages,'even a failed explicit clear cancels a pending save generation');
  h.failClear(false);assert.strictEqual(h.reference.clear(),true);assert.strictEqual(h.reference.hasHome(),false);assert.strictEqual(h.out.length,messages+1);assertPrivateWire(h.out);
});
test('explicitly saving a home outside service coverage succeeds but its later distance query reports Outside without GPS',function(){
  var h=referenceHarness(),fix=homeFix(now);fix.coords.latitude=45;h.reference.saveCurrent(true);h.callbacks[0].ok(fix);assert.strictEqual(h.reference.hasHome(),true);assert.strictEqual(h.out[0].STATUS,0);
  h.reference.request(1,1,1,referencePoles,true);assert.strictEqual(h.out[1].STATUS,6);assert.strictEqual(h.out[1].DATA,undefined);assert.strictEqual(h.calls(),1);
  h.reference.clear();assert.strictEqual(createReference(h.options).hasHome(),false,'clear survives a phone module restart');assertPrivateWire(h.out);
});
test('corrupt or unavailable private home storage is safely unset and never invokes GPS during load or a home query',function(){
  var record={schema:1,coords:{latitude:1,longitude:2,accuracy:10},savedAt:now};
  ['not JSON',JSON.stringify(null),JSON.stringify({}),JSON.stringify(Object.assign({},record,{schema:2})),JSON.stringify(Object.assign({},record,{savedAt:-1})),JSON.stringify(Object.assign({},record,{savedAt:now+0.5})),JSON.stringify(Object.assign({},record,{coords:{latitude:91,longitude:2,accuracy:10}})),JSON.stringify(Object.assign({},record,{coords:{latitude:1,longitude:181,accuracy:10}})),JSON.stringify(Object.assign({},record,{coords:{latitude:1,longitude:2,accuracy:101}})),JSON.stringify(Object.assign({},record,{coords:{latitude:'1',longitude:2,accuracy:10}}))].forEach(function(raw){var h=referenceHarness(undefined,{'kasugabus.saved-home.v1':raw});assert.strictEqual(h.reference.hasHome(),false);h.reference.request(1,1,1,referencePoles,true);assert.strictEqual(h.out[0].STATUS,9);assert.strictEqual(h.calls(),0);});
  var h=referenceHarness();h.options.storage={getItem:function(){throw new Error('Private storage unavailable');}};var reference=createReference(h.options);assert.strictEqual(reference.hasHome(),false);reference.request(1,1,1,referencePoles,true);assert.strictEqual(h.out[0].STATUS,9);reference.clear();assert.strictEqual(reference.lastActionStatus(),5);assert.strictEqual(h.calls(),0);
});
test('new requests disable version invalidation and clear suppress every obsolete reference or home-save completion',function(){
  var h=referenceHarness();h.reference.request(0,1,1,referencePoles,true);h.reference.request(0,2,1,referencePoles,true);h.callbacks[0].ok(homeFix(now));assert.strictEqual(h.out.length,0);h.reference.invalidate();h.callbacks[1].ok(homeFix(now));assert.strictEqual(h.out.length,0);
  h.reference.saveCurrent(true);assert.strictEqual(h.reference.clear(),true);h.callbacks[2].ok(homeFix(now));assert.strictEqual(h.reference.hasHome(),false);assert.strictEqual(h.out.length,1);assert.strictEqual(h.out[0].STATUS,9);
  h.reference.saveCurrent(true);h.reference.request(0,3,2,referencePoles,false);h.callbacks[3].ok(homeFix(now));assert.strictEqual(h.reference.hasHome(),false);assert.strictEqual(h.out.length,2);assert.strictEqual(h.out[1].STATUS,8);
  [[2,1,1],[null,1,1],[0,0,1],[0,1,0],[0,1.5,1],[0,1,4294967296]].forEach(function(args){h.reference.request(args[0],args[1],args[2],referencePoles,true);});assert.strictEqual(h.out.length,2);assertPrivateWire(h.out);
});
test('home notifications retry a dropped failed or full sender within a bound and resume without GPS',function(){
  ['drop','fail','full'].forEach(function(mode){
    var h=referenceHarness();h.sendMode(mode);h.reference.saveCurrent(true);h.callbacks[0].ok(homeFix(now));var key=Object.keys(h.data)[0];
    assert.strictEqual(JSON.parse(h.data[key]).pending,0);h.clock.advance(60000);assert.strictEqual(h.transports.length,3);h.clock.advance(60000);assert.strictEqual(h.transports.length,3,'exhaustion must not retry forever');
    h.sendMode('success');h.reference.retryNotification();assert.strictEqual(h.transports.length,4);assert.strictEqual(JSON.parse(h.data[key]).pending,null);assert.strictEqual(h.reference.hasHome(),true);assert.strictEqual(h.calls(),1);assertPrivateWire(h.out);
    h.transports[0].ok();h.transports[0].fail();assert.strictEqual(JSON.parse(h.data[key]).pending,null,'obsolete callbacks cannot revive pending state');
  });
});
test('pending home clear survives worker restart without storing coordinates and late older-worker callbacks cannot resurrect home',function(){
  var h=referenceHarness();h.sendMode('drop');h.reference.saveCurrent(true);h.callbacks[0].ok(homeFix(now));var key=Object.keys(h.data)[0];
  var restarted=referenceHarness(undefined,h.data);restarted.sendMode('drop');assert.strictEqual(restarted.reference.hasHome(),true);assert.strictEqual(restarted.calls(),0);
  restarted.reference.clear();var cleared=h.data[key];assert.strictEqual(JSON.parse(cleared).home,null);assert.strictEqual(JSON.parse(cleared).pending,9);assert.ok(!/coords|latitude|longitude|savedAt/.test(cleared));
  h.transports[0].ok();h.transports[0].fail();h.clock.advance(60000);assert.strictEqual(h.data[key],cleared,'old worker acknowledgement cannot erase or resurrect a newer clear');assert.strictEqual(h.transports.length,1);
  var fresh=referenceHarness(undefined,h.data);assert.strictEqual(fresh.reference.hasHome(),false);assert.strictEqual(fresh.calls(),0);fresh.reference.retryNotification();assert.deepStrictEqual(fresh.out,[{TYPE:16,STATUS:9}]);assert.strictEqual(Object.keys(h.data).length,0);assert.strictEqual(fresh.calls(),0);
  restarted.transports[0].ok();assert.strictEqual(Object.keys(h.data).length,0);assertPrivateWire(h.out.concat(restarted.out,fresh.out));
});
test('overlapping Save Clear Save notifications retain only the latest durable mutation despite stale success and failure callbacks',function(){
  var h=referenceHarness();h.sendMode('drop');h.reference.saveCurrent(true);h.callbacks[0].ok(homeFix(now));h.reference.clear();var clear=h.transports[1];
  h.reference.saveCurrent(true);var latest=homeFix(now);latest.coords.latitude=0.0023456;h.callbacks[1].ok(latest);var key=Object.keys(h.data)[0],raw=h.data[key];
  assert.strictEqual(JSON.parse(raw).revision,3);assert.strictEqual(JSON.parse(raw).pending,0);assert.strictEqual(JSON.parse(raw).home.coords.latitude,0.0023456);
  h.transports[0].fail();h.transports[0].ok();clear.ok();clear.fail();assert.strictEqual(h.data[key],raw);assert.strictEqual(h.reference.hasHome(),true);
  h.transports[2].ok();assert.strictEqual(JSON.parse(h.data[key]).pending,null);assert.strictEqual(JSON.parse(h.data[key]).home.coords.latitude,0.0023456);h.clock.advance(60000);assert.strictEqual(h.transports.length,3);assert.strictEqual(h.calls(),2);assertPrivateWire(h.out);
});
test('notification acknowledgement storage failures retain private pending status for a later retry without changing home',function(){
  var h=referenceHarness();h.sendMode('drop');h.reference.saveCurrent(true);h.callbacks[0].ok(homeFix(now));var key=Object.keys(h.data)[0],raw=h.data[key];
  h.failWrite(true);h.sendMode('success');h.transports[0].ok();h.clock.advance(2000);assert.strictEqual(h.transports.length,3);assert.strictEqual(h.data[key],raw);assert.strictEqual(h.reference.hasHome(),true);
  h.failWrite(false);h.reference.retryNotification();assert.strictEqual(JSON.parse(h.data[key]).pending,null);assert.strictEqual(h.calls(),1);
  h.sendMode('drop');h.reference.clear();var cleared=h.data[key];h.failClear(true);h.transports[h.transports.length-1].ok();assert.strictEqual(h.data[key],cleared);assert.strictEqual(h.reference.hasHome(),false);assert.ok(!/coords|latitude|longitude/.test(cleared));
  h.failClear(false);h.sendMode('success');h.clock.advance(500);assert.strictEqual(Object.keys(h.data).length,0);assertPrivateWire(h.out);
});
test('a real shared sender with a dropped SDK callback preserves pending home notification and succeeds after reconnect reset',function(){
  var h=referenceHarness(),sdk=[],sender=require('../src/pkjs/sender')(Object.assign({},h.clock,{send:function(message,ok,fail){sdk.push({message:message,ok:ok,fail:fail});}})),reference=createReference(Object.assign({},h.options,{send:sender}));
  reference.saveCurrent(true);h.callbacks[0].ok(homeFix(now));assert.strictEqual(sdk.length,1);assert.strictEqual(sdk[0].message.TYPE,16);h.clock.advance(60000);assert.strictEqual(sdk.length,1,'blocked sender never overlaps a hung SDK transaction');
  var key=Object.keys(h.data)[0];assert.strictEqual(JSON.parse(h.data[key]).pending,0);sender.reset();reference.retryNotification();assert.strictEqual(sdk.length,2);sdk[0].ok();assert.strictEqual(JSON.parse(h.data[key]).pending,0);sdk[1].ok();assert.strictEqual(JSON.parse(h.data[key]).pending,null);assert.strictEqual(h.calls(),1);
});
console.log(count+' phone unit scenarios passed');
