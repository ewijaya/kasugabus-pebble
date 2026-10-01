'use strict';
// Real loopback HTTP + the production updater/validators/ACK sender. The watch
// model is explicit; this is not a claim about actual firmware persistence.
var http=require('http'),assert=require('assert'),updater=require('../src/pkjs/updater'),binary=require('../src/pkjs/binary'),hash=require('../src/pkjs/checksums');
var base=process.argv[2],fixedNow=Date.parse('2026-10-01T00:00:00Z');
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(base))throw new Error('Harness requires isolated loopback HTTP');
function fetch(url,maximum,isBinary,timeout,cb){
  if(url.indexOf(base+'/')!==0)return cb(new Error('Uncontrolled test URL'));
  var done=false,parts=[],length=0,request=http.get(url,function(response){
    if(response.statusCode!==200){response.resume();return finish(new Error('HTTP '+response.statusCode));}
    response.on('data',function(part){length+=part.length;if(length>maximum){request.destroy();finish(new Error('Size limit'));}else parts.push(part);});
    response.on('end',function(){var value=Buffer.concat(parts);finish(null,isBinary?Array.from(value):value.toString('utf8'));});
    response.on('aborted',function(){finish(new Error('Interrupted download'));});response.on('error',finish);
  });
  request.setTimeout(1000,function(){request.destroy(new Error('Network timeout'));});request.on('error',finish);
  function finish(error,value){if(done)return;done=true;cb(error,value);}
  return function(){request.destroy();finish(new Error('Cancelled'));};
}
async function scenario(name,path,expected,dropAck){
  var config={manifestUrl:base+'/'+path,coverage:'minami-kasugaoka-v1',appVersion:1,maxPayload:32768,manifestMaxBytes:8192,requestTimeout:15000};
  var watch={current:1,pending:0,staging:null,received:[],commitOrder:[]},messages=[],phone,timers=[];
  return new Promise(function(resolve,reject){
    function ack(message,status){if(dropAck)return;setImmediate(function(){phone.receive({TYPE:8,SESSION:message.SESSION,SEQ:message.TYPE===7?65535:message.SEQ||0,STATUS:status,FLAGS:message.TYPE});});}
    function send(message){
      messages.push(message);
      try{
        if(message.TYPE===4 && [2,3,5,6,7].indexOf(message.STATUS)!==-1){
          assert.strictEqual(message.STATUS,expected,name);
          if(expected===3){assert.strictEqual(watch.current,2);assert.strictEqual(watch.pending,3);assert.deepStrictEqual(watch.commitOrder,[3,2]);assert.ok(message.STAMP);}
          else {assert.strictEqual(watch.current,1);assert.strictEqual(watch.pending,0);assert.strictEqual(message.STAMP,undefined);}
          timers.forEach(clearTimeout);console.log('PASS controlled HTTP '+name+'; commits '+watch.commitOrder.join(','));resolve();
        }else if(message.TYPE===5){watch.staging={session:message.SESSION,version:message.VERSION,length:message.LENGTH,crc:message.CRC,bytes:[],next:0};ack(message,0);}
        else if(message.TYPE===6){assert.ok(message.DATA.length<=192);assert.strictEqual(message.SESSION,watch.staging.session);if(message.SEQ===watch.staging.next){watch.staging.bytes=watch.staging.bytes.concat(message.DATA);watch.staging.next+=1;}else assert.strictEqual(message.SEQ,watch.staging.next-1);ack(message,0);}
        else if(message.TYPE===7){assert.strictEqual(watch.staging.bytes.length,watch.staging.length);assert.strictEqual(hash.crc32(watch.staging.bytes),watch.staging.crc);var metadata=binary.validate(watch.staging.bytes,config);var future=metadata.effectiveFrom>Math.floor((fixedNow+32400000)/86400000);if(future)watch.pending=metadata.version;else watch.current=metadata.version;watch.commitOrder.push(metadata.version);ack(message,future?4:3);}
      }catch(error){timers.forEach(clearTimeout);reject(error);}
    }
    phone=updater({config:config,testInsecure:true,send:send,fetch:fetch,now:function(){return fixedNow;},schedule:function(fn,delay){var timer=setTimeout(fn,dropAck?5:delay);timers.push(timer);return timer;},cancel:clearTimeout});
    phone.state({version:watch.current,pending:watch.pending,flags:1});phone.check(1,true);
    var watchdog=setTimeout(function(){reject(new Error(name+' harness timeout'));},5000);timers.push(watchdog);
  });
}
(async function(){await scenario('current + future staged before current','manifest.json',3,false);await scenario('corrupt checksum','corrupt.json',5,false);await scenario('incompatible schema','incompatible.json',6,false);await scenario('interrupted HTTP payload','interrupted.json',5,false);await scenario('lost ACK bounded transfer','manifest.json',5,true);console.log('5 real HTTP integration scenarios passed; production endpoint unchanged');})().catch(function(error){console.error(error.stack);process.exitCode=1;});
