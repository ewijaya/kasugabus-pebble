'use strict';
var assert=require('assert'),fs=require('fs'),path=require('path'),vm=require('vm'),settings=require('../src/pkjs/settings'),custom=require('../src/pkjs/custom-clay');
var ids=Array.from({length:15},function(_,i){return i+1;}),items={},build,disabled=false;
function item(key,value){items[key]={value:value,get:function(){return this.value;},set:function(v){this.value=v;},on:function(event,fn){this.changed=fn;},disable:function(){disabled=true;},enable:function(){disabled=false;}};}
item('DefaultId','1');item('Buffer','2');item('save-preferences','');item('validation-message','');
item('NearbyStartup',false);item('LocationEnabled',false);
for(var i=0;i<12;i+=1)item('Favourite'+i,i===0?'1':'0');ids.forEach(function(id){item('Walk'+id,'');});
custom.call({EVENTS:{AFTER_BUILD:'build'},on:function(event,fn){build=fn;},meta:{userData:{ids:ids,walkKeys:ids.map(function(id){return 'Walk'+id;})}},getItemById:function(id){return items[id];},getItemByMessageKey:function(key){return items[key];}});
build();assert.strictEqual(disabled,false);items.Favourite1.value='1';items.Favourite1.changed();assert.strictEqual(disabled,true);assert.match(items['validation-message'].value,/once/);items.Favourite1.value='0';items.Favourite1.changed();assert.strictEqual(disabled,false);
items.NearbyStartup.value=true;items.NearbyStartup.changed();assert.strictEqual(disabled,true);items.LocationEnabled.value=true;items.LocationEnabled.changed();assert.strictEqual(disabled,false);items.NearbyStartup.value=false;items.LocationEnabled.value=false;items.LocationEnabled.changed();assert.strictEqual(disabled,false);
items.Walk1.value='0';items.Walk1.changed();assert.strictEqual(disabled,false);items.Walk1.value='121';items.Walk1.changed();assert.strictEqual(disabled,true);items.Walk1.value='';items.Walk1.changed();assert.strictEqual(disabled,false);
for(i=1;i<=13;i+=1)items['Walk'+i].value='5';items.Walk1.changed();assert.strictEqual(disabled,true);items.Walk13.value='';items.Walk13.changed();assert.strictEqual(disabled,false);
console.log('PASS Clay page prevents duplicate, invalid and excessive walking preferences');
var listeners={},sent=[],opened=[],clays=[],timers=[],locationCalls=0,locationCallbacks=[],deferLocation=false,feedRequests=[];
var createUpdater=require('../src/pkjs/updater');
function controlledFetch(url,max,binary,timeout,callback){var request={callback:callback,aborts:0};feedRequests.push(request);return function(){request.aborts+=1;callback(new Error('Aborted'));};}
function updaterModule(options){return createUpdater(options);}
updaterModule.xhrFetch=controlledFetch;
function MockClay(config,customFn,options){this.config=config;this.options=options;this.meta={};clays.push(this);}
MockClay.prototype.setSettings=function(value){this.values=value;};MockClay.prototype.generateUrl=function(){return 'data:mock-clay';};
var context={require:function(name){return name==='@rebble/clay'?MockClay:name==='./updater'?updaterModule:require(path.resolve(__dirname,'../src/pkjs',name));},Pebble:{addEventListener:function(name,fn){listeners[name]=fn;},sendAppMessage:function(m,ok){sent.push(m);if(ok)ok();},openURL:function(url){opened.push(url);}},navigator:{geolocation:{getCurrentPosition:function(success){locationCalls+=1;if(deferLocation)locationCallbacks.push(success);else success({coords:{latitude:0,longitude:0,accuracy:10},timestamp:Date.now()});}}},setTimeout:function(fn){timers.push(fn);return timers.length;},clearTimeout:function(){},Date:Date,console:{log:function(){}}};
vm.runInNewContext(fs.readFileSync(path.resolve(__dirname,'../src/pkjs/index.js'),'utf8'),context);
listeners.ready();assert.strictEqual(sent[0].TYPE,1);
var catalog=[{id:1,label:'Fixture / Test / Ibaraki'},{id:2,label:'Fixture / Test / University'}],old={flags:17,defaultId:1,buffer:2,favourites:[1,2],walks:{1:5}},bytes=settings.encode(old,catalog);
function state(data){listeners.appmessage({payload:{TYPE:2,VERSION:1,PENDING:0,FLAGS:17,LENGTH:32768,DATA:data}});}
function catalogue(){var data=[];catalog.forEach(function(p){var text=Array.from(Buffer.from(p.label));data.push(p.id,0,text.length);data=data.concat(text);});listeners.appmessage({payload:{TYPE:13,VERSION:1,SEQ:0,STATUS:1,DATA:data}});}
state(bytes);listeners.showConfiguration();catalogue();assert.strictEqual(opened.length,1);assert.strictEqual(clays[0].values.Buffer,2);
var before=sent.length;listeners.webviewclosed({response:''});assert.strictEqual(sent.length,before);
var values=settings.toClay(old,catalog);values.Favourite1=1;listeners.webviewclosed({response:JSON.stringify(values)});assert.strictEqual(sent.length,before);
values=settings.toClay(old,catalog);values.Buffer=7;listeners.webviewclosed({response:JSON.stringify(values)});assert.strictEqual(sent[sent.length-1].TYPE,11);assert.strictEqual(sent[sent.length-1].DATA.length,80);
listeners.showConfiguration();catalogue();assert.strictEqual(clays[1].values.Buffer,2,'unconfirmed settings must not replace previous snapshot');
state(settings.encode(settings.fromClay(values,catalog),catalog));listeners.showConfiguration();catalogue();assert.strictEqual(clays[2].values.Buffer,7);
var helloCount=sent.filter(function(m){return m.TYPE===1;}).length;listeners.appmessage({payload:{TYPE:2,STATUS:1,VERSION:1,FLAGS:17,LENGTH:32768,DATA:bytes}});assert.strictEqual(sent.filter(function(m){return m.TYPE===1;}).length,helloCount+1);state(bytes);assert.strictEqual(sent.filter(function(m){return m.TYPE===1;}).length,helloCount+1);
console.log('PASS phone configuration cancellation, invalid responses, atomic confirmation and reconnect handshake');
var coordinates=[1,0,0,0,0,0,0,0,0,0];
listeners.appmessage({payload:{TYPE:9,REQUEST:1,VERSION:1,DATA:coordinates}});
assert.strictEqual(locationCalls,0,'disabled location must not access geolocation');assert.strictEqual(sent[sent.length-1].STATUS,8);
listeners.appmessage({payload:{TYPE:2,VERSION:1,FLAGS:19,LENGTH:32768,DATA:bytes}});
listeners.appmessage({payload:{TYPE:9,REQUEST:2,VERSION:1,DATA:coordinates}});
assert.strictEqual(locationCalls,1,'explicit Nearby works when location is enabled and startup is disabled');assert.strictEqual(sent[sent.length-1].STATUS,0);
listeners.appmessage({payload:{TYPE:2,VERSION:1,FLAGS:23,LENGTH:32768,DATA:bytes}});
listeners.appmessage({payload:{TYPE:9,REQUEST:3,VERSION:1,DATA:coordinates}});
assert.strictEqual(locationCalls,2,'startup setting does not block explicit Nearby');
listeners.appmessage({payload:{TYPE:9,REQUEST:4,VERSION:2,DATA:coordinates}});
assert.strictEqual(locationCalls,2,'old version location requests are rejected');
console.log('PASS phone Nearby respects location opt-in independently of startup');
deferLocation=true;
listeners.appmessage({payload:{TYPE:9,REQUEST:5,VERSION:1,DATA:coordinates}});
assert.strictEqual(locationCallbacks.length,1);
listeners.appmessage({payload:{TYPE:2,VERSION:1,FLAGS:17,LENGTH:32768,DATA:bytes}});
var beforeFix=sent.length;
locationCallbacks[0]({coords:{latitude:0,longitude:0,accuracy:10},timestamp:Date.now()});
assert.strictEqual(sent.length,beforeFix,'turning location off must invalidate an in-flight fix');
console.log('PASS disabling location suppresses an in-flight result');
listeners.appmessage({payload:{TYPE:3,REQUEST:10,STATUS:1}});
assert.strictEqual(feedRequests.length,1);
listeners.appmessage({payload:{TYPE:2,STATUS:2,REQUEST:11,VERSION:1,FLAGS:17,LENGTH:32768,DATA:bytes}});
assert.strictEqual(feedRequests[0].aborts,1,'Restore STATE must abort the pending production updater');
var afterRestore=sent.length;
feedRequests[0].callback(null,'{}');
assert.strictEqual(sent.length,afterRestore,'obsolete feed completion must be ignored');
listeners.appmessage({payload:{TYPE:3,REQUEST:11,STATUS:1}});
assert.strictEqual(feedRequests.length,2,'Restore allows a subsequent explicit update check');
console.log('PASS Restore STATE cancels downloading and permits a new explicit check');
