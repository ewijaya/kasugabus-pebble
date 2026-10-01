'use strict';
// Actual emulator integration. Requires an existing built/installed watch app.
// Unlike run_phone_feed.js, every ACK and STATE comes from native watch C.
var fs=require('fs'),http=require('http'),child=require('child_process'),readline=require('readline'),assert=require('assert'),updater=require('../src/pkjs/updater'),createSender=require('../src/pkjs/sender'),p=require('../src/pkjs/protocol');
var base=process.argv[2],current=Number(process.argv[3]||2),pending=current+1,root=require('path').resolve(__dirname,'..');
if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(base))throw new Error('Controlled loopback feed URL required');
var python=process.env.KASUGABUS_PEBBLE_PYTHON||'/Users/e_wijaya_ap/.local/share/uv/tools/pebble-tool/bin/python';
var bridge=child.spawn(python,[root+'/tools/emu_update_bridge.py'],{stdio:['pipe','pipe','inherit']}),listeners=[],watchState=null,activePhone=null,savedPrefs=null,originalPreferences=null,interrupted=false,chunkCount=0,closing=false,bridgeFailed=false;
var tracing=process.env.KASUGABUS_EMU_TRACE==='1';
var activeTransport=null;
var serializedSend=createSender({schedule:setTimeout,cancel:clearTimeout,send:function(message,success,failure){
  assert.strictEqual(activeTransport,null,'Only one bridge transport transaction may be active');
  activeTransport={success:success,failure:failure,transaction:null,early:[]};command({op:'send',message:message});
}});
function transportResult(event){
  var active=activeTransport;if(!active)return;
  if(active.transaction===null){active.early.push(event);return;}
  if(event.transaction!==active.transaction)return;
  activeTransport=null;
  if(event.event==='transportAck')active.success();else active.failure(new Error('Native transport NACK'));
}
function trace(direction,message){if(!tracing)return;var entry={direction:direction};['TYPE','SESSION','SEQ','STATUS','FLAGS','VERSION','LENGTH'].forEach(function(key){var value=p.get(message,key);if(typeof value!=='undefined')entry[key]=value;});console.error('EMU_TRACE '+JSON.stringify(entry));}
function command(value){if(value.op==='close')closing=true;if(bridgeFailed||!bridge.stdin.writable)return;bridge.stdin.write(JSON.stringify(value)+'\n');}
function notify(event){if(event.event==='error'&&event.fatal)bridgeFailed=true;listeners.slice().forEach(function(callback){callback(event);});}
bridge.on('error',function(error){notify({event:'error',fatal:true,message:'Bridge process error: '+error.message});});
bridge.on('exit',function(code,signal){if(!closing)notify({event:'error',fatal:true,message:'Bridge process exited: '+code+' '+(signal||'')});});
bridge.stdin.on('error',function(error){if(!closing)notify({event:'error',fatal:true,message:'Bridge input error: '+error.message});});
function send(message,success,failure){
  if(interrupted&&message.TYPE===6&&message.SEQ>=2){setImmediate(function(){if(activePhone)activePhone.cancel();});return;}
  if(message.TYPE===6)chunkCount+=1;
  trace('send',message);
  serializedSend(message,success,failure);
}
function waitFor(predicate,timeout){return new Promise(function(resolve,reject){if(bridgeFailed)return reject(new Error('Bridge transport is unavailable'));var timer=setTimeout(function(){listeners=listeners.filter(function(x){return x!==receive;});reject(new Error('Emulator event timeout'));},timeout||15000);function receive(event){if(event.event==='error'&&event.fatal||predicate(event)){clearTimeout(timer);listeners=listeners.filter(function(x){return x!==receive;});if(event.fatal)reject(new Error(event.message));else resolve(event);}}listeners.push(receive);});}
readline.createInterface({input:bridge.stdout}).on('line',function(line){
  var event;try{event=JSON.parse(line);}catch(e){return;}
  if(event.event==='error'){console.error('BRIDGE '+event.message);notify(event);return;}
  if(event.event==='sent'&&activeTransport){var transaction=activeTransport;transaction.transaction=event.transaction;transaction.early.forEach(transportResult);}
  if(event.event==='transportAck'||event.event==='transportNack')transportResult(event);
  if(tracing&&(event.event==='transportAck'||event.event==='transportNack'))console.error('EMU_TRACE '+JSON.stringify(event));
  if(event.event==='appmessage'){
    var msg=event.message,type=p.get(msg,'TYPE');
    if(type===2||type===8)trace('receive',msg);
    if(type===2){if(p.get(msg,'STATUS')===2&&activePhone)activePhone.cancel();watchState={version:p.get(msg,'VERSION'),pending:p.get(msg,'PENDING')||0,flags:p.get(msg,'FLAGS')||0,request:p.get(msg,'REQUEST')||0,lastSuccess:p.get(msg,'STAMP')||0};if(p.get(msg,'DATA'))savedPrefs=p.get(msg,'DATA');if(activePhone)activePhone.state(watchState);}
    if(type===8&&activePhone)activePhone.receive(msg);
  }
  notify(event);
});
function fetch(url,maximum,isBinary,timeout,cb){
  if(url.indexOf(base+'/')!==0)return cb(new Error('Uncontrolled URL'));
  var done=false,parts=[],size=0,request=http.get(url,function(response){
    if(response.statusCode!==200){response.resume();return finish(new Error('HTTP '+response.statusCode));}
    response.on('data',function(part){size+=part.length;if(size>maximum){request.destroy();finish(new Error('Too large'));}else parts.push(part);});
    response.on('end',function(){var data=Buffer.concat(parts);finish(null,isBinary?Array.from(data):data.toString('utf8'));});response.on('aborted',function(){finish(new Error('Interrupted payload'));});response.on('error',finish);
  });
  request.setTimeout(timeout,function(){request.destroy(new Error('Network timeout'));});request.on('error',finish);
  function finish(error,value){if(done)return;done=true;cb(error,value);}
  return function(){request.destroy();finish(new Error('Cancelled'));};
}
async function state(){var response=waitFor(function(e){return e.event==='appmessage'&&p.get(e.message,'TYPE')===2;});send({TYPE:1});await response;return watchState;}
async function restart(){
  var stopped=waitFor(function(e){return e.event==='runState'&&e.kind==='AppRunStateStop';},5000);command({op:'stop'});await stopped;
  var started=waitFor(function(e){return e.event==='runState'&&e.kind==='AppRunStateStart';},5000);command({op:'start'});await started;return state();
}
async function runFeed(name,path,expected,interrupt){
  var previousSuccess=watchState.lastSuccess;
  interrupted=!!interrupt;chunkCount=0;var statuses=[];
  var phone=updater({config:{manifestUrl:base+'/'+path,coverage:'minami-kasugaoka-v1',appVersion:1,maxPayload:32768,manifestMaxBytes:8192,requestTimeout:15000},testInsecure:true,fetch:fetch,send:function(message,success,failure){if(message.TYPE===4){statuses.push(message.STATUS);if([2,3,5,6].indexOf(message.STATUS)!==-1)setImmediate(done);}send(message,success,failure);},now:Date.now,schedule:setTimeout,cancel:clearTimeout});
  activePhone=phone;phone.state(watchState);
  var done=function(){};
  var outcome=new Promise(function(resolve,reject){function clean(){clearTimeout(timer);listeners=listeners.filter(function(x){return x!==failed;});}function failed(event){if(event.event==='error'&&event.fatal){clean();reject(new Error(event.message));}}var timer=setTimeout(function(){clean();reject(new Error(name+' timeout'));},120000);listeners.push(failed);done=function(){clean();try{assert.strictEqual(statuses[statuses.length-1],expected);resolve();}catch(e){reject(e);}};});
  phone.check(watchState.request,true);await outcome;activePhone=null;interrupted=false;
  var snapshot=await state();assert.strictEqual(snapshot.version,current,name+' active');assert.strictEqual(snapshot.pending,pending,name+' pending');
  if(expected===3)assert.ok(snapshot.lastSuccess>0,'Successful check timestamp must be stored by native watch');
  else assert.strictEqual(snapshot.lastSuccess,previousSuccess,'Failed check must preserve previous successful timestamp');
  console.log('PASS native emulator '+name+' active='+snapshot.version+' pending='+snapshot.pending+' chunksSent='+chunkCount);
}
(async function(){
  await waitFor(function(e){return e.event==='ready';});await state();
  assert.ok(watchState.version<current,'Choose a test current version greater than installed version');
  // Keep the production phone worker from starting a production automatic
  // feed check. The watch validates/acknowledges these same 80 preference bytes.
  originalPreferences=savedPrefs.slice();var preferences=savedPrefs.slice();preferences[1]&=~5;
  var confirmed=waitFor(function(e){return e.event==='appmessage'&&p.get(e.message,'TYPE')===2;});send({TYPE:11,DATA:preferences});await confirmed;
  await runFeed('current + future update without PBW reinstall','manifest.json',3,false);
  var reopened=await restart();assert.strictEqual(reopened.version,current);assert.strictEqual(reopened.pending,pending);console.log('PASS native emulator stop/start preserved active and pending');
  if(process.env.KASUGABUS_EMU_PROFILE){
    var measured=child.spawnSync(python,[root+'/tools/profile_emulator.py'],{cwd:root,encoding:'utf8',timeout:60000});
    assert.strictEqual(measured.status,0,measured.stderr);
    fs.writeFileSync(process.env.KASUGABUS_EMU_PROFILE,measured.stdout,{flag:'wx'});
    var profile=JSON.parse(measured.stdout);
    assert.ok(profile.all_launches_under_1000ms,'Offline first home exceeds one second');
    assert.ok(profile.all_buttons_under_200ms,'Ordinary button response exceeds 200 ms');
    await state();
    console.log('PASS native monotonic launch and button profiling before interrupted candidate');
  }
  await runFeed('interrupted partial replacement','replacement.json',5,true);
  reopened=await restart();assert.strictEqual(reopened.version,current);assert.strictEqual(reopened.pending,pending);console.log('PASS native emulator partial candidate restart kept active and pending');
  await runFeed('corrupt full payload','corrupt.json',5,false);
  await runFeed('incompatible manifest','incompatible.json',6,false);
  await runFeed('interrupted HTTP','interrupted.json',5,false);
  var restored=waitFor(function(e){return e.event==='appmessage'&&p.get(e.message,'TYPE')===2;});send({TYPE:11,DATA:originalPreferences});await restored;assert.strictEqual(savedPrefs[1],originalPreferences[1]);
  console.log('Emulator checks passed; no PBW installation occurred during this harness.');
  serializedSend.reset();
  command({op:'close'});bridge.stdin.end();
})().catch(function(error){console.error(error.stack);if(activePhone)activePhone.cancel();serializedSend.reset();command({op:'close'});bridge.stdin.end();process.exitCode=1;});
