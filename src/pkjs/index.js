'use strict';
var Clay=require('@rebble/clay'),p=require('./protocol'),settings=require('./settings'),config=require('./feed-config');
var catalog=require('./catalog.json').boardingPoints,snapshot=null,state=null,clay=null,catalogBatch=null,settingsOpening=false,settingsTimer=null;
var send=require('./sender')({send:function(message,success,failure){Pebble.sendAppMessage(message,success,failure);},schedule:schedule,cancel:cancel});
function schedule(callback,delay){return setTimeout(callback,delay);}
function cancel(timer){clearTimeout(timer);}
var nearby=require('./nearby')({send:send,schedule:schedule,cancel:cancel,now:function(){return Date.now();},geolocation:typeof navigator!=='undefined'?navigator.geolocation:null});
var updater=require('./updater')({config:config,send:send,schedule:schedule,cancel:cancel,now:function(){return Date.now();},fetch:require('./updater').xhrFetch,
  catalog:function(value){catalog=value;nearby.invalidate();}});
function openSettings(){
  if(!settingsOpening)return;settingsOpening=false;if(settingsTimer!==null)cancel(settingsTimer);settingsTimer=null;
  var walkKeys=catalog.map(function(p){return 'Walk'+p.id;});
  if(snapshot)Object.keys(snapshot.walks).forEach(function(id){if(walkKeys.indexOf('Walk'+id)===-1)walkKeys.push('Walk'+id);});
  clay=new Clay(require('./clay-config')(catalog,snapshot),require('./custom-clay'),{autoHandleEvents:false,userData:{ids:catalog.map(function(p){return p.id;}),walkKeys:walkKeys}});
  // Clay is constructed after the ready event; initialize the documented meta
  // field used by the custom page without copying account/watch tokens.
  clay.meta.userData={ids:catalog.map(function(p){return p.id;}),walkKeys:walkKeys};
  if(Pebble.getActiveWatchInfo)clay.meta.activeWatchInfo=Pebble.getActiveWatchInfo();
  if(snapshot)clay.setSettings(settings.toClay(snapshot,catalog));
  Pebble.openURL(clay.generateUrl());
}
function knownWithUnavailable(bytes){
  var known=catalog.slice(),seen={};known.forEach(function(x){seen[x.id]=true;});
  // Display watch-owned preferences for IDs removed by an update. Their removal
  // is explicit in the configuration form; no arbitrary replacement is chosen.
  if(bytes&&bytes.length===80){for(var i=0;i<12;i+=1){var id=settings.u16(bytes,8+i*2);if(id&&!seen[id]){known.push({id:id,label:'Unavailable #'+id});seen[id]=true;}}var defaultId=settings.u16(bytes,2);if(defaultId&&!seen[defaultId])known.push({id:defaultId,label:'Unavailable #'+defaultId});for(i=0;i<12;i+=1){id=settings.u16(bytes,32+i*4);if(id&&!seen[id]){known.push({id:id,label:'Unavailable #'+id});seen[id]=true;}}}
  return known;
}
Pebble.addEventListener('ready',function(){send.reset();send({TYPE:p.type.HELLO});});
Pebble.addEventListener('showConfiguration',function(){settingsOpening=true;if(settingsTimer!==null)cancel(settingsTimer);settingsTimer=schedule(openSettings,2000);send({TYPE:p.type.HELLO});});
Pebble.addEventListener('webviewclosed',function(event){
  if(!event||!event.response||!clay)return;
  try{
    var text=event.response.charAt(0)==='{'?event.response:decodeURIComponent(event.response),values=JSON.parse(text);
    var candidate=settings.fromClay(values,catalog),bytes=settings.encode(candidate,catalog);
    send({TYPE:p.type.SETTINGS,DATA:bytes});
    // Do not mutate the confirmed snapshot until a valid watch STATE replies.
  }catch(e){console.log('KasugaBus preferences rejected: '+e.message);if(snapshot)clay.setSettings(settings.toClay(snapshot,catalog));}
});
Pebble.addEventListener('appmessage',function(event){
  var msg=event.payload||{},type=p.get(msg,'TYPE');
  if(type===p.type.STATE){
    if(p.get(msg,'STATUS')===1){send.reset();send({TYPE:p.type.HELLO});}
    if(p.get(msg,'STATUS')===2)updater.cancel();
    var oldVersion=state&&state.version,oldFlags=state&&state.flags;
    state={version:p.get(msg,'VERSION')||0,pending:p.get(msg,'PENDING')||0,flags:p.get(msg,'FLAGS')||0,request:p.get(msg,'REQUEST')||0};
    var maximum=p.get(msg,'LENGTH');if(settings.integer(maximum,128,32768))config.maxPayload=maximum;
    updater.state(state);if((oldVersion&&oldVersion!==state.version)||((oldFlags&2)&&!(state.flags&2)))nearby.invalidate();
    try{var bytes=p.get(msg,'DATA');snapshot=settings.decode(bytes,knownWithUnavailable(bytes));}catch(ignore){}
    // CATALOG will open with the complete live ID set; timeout is a safe fallback.
  }else if(type===13){
    var seq=p.get(msg,'SEQ'),version=p.get(msg,'VERSION'),data=p.get(msg,'DATA');
    if(seq===0)catalogBatch={next:0,version:version,points:[],seen:{}};
    if(!catalogBatch||version!==catalogBatch.version||seq!==catalogBatch.next||!Array.isArray(data))return;
    try{for(var i=0;i<data.length;){if(i+3>data.length)throw new Error('catalog');var id=settings.u16(data,i),length=data[i+2];i+=3;if(!id||!length||i+length>data.length||catalogBatch.seen[id])throw new Error('catalog');var text='';for(var j=0;j<length;j+=1)text+='%'+('0'+data[i+j].toString(16)).slice(-2);catalogBatch.points.push({id:id,label:decodeURIComponent(text)});catalogBatch.seen[id]=true;i+=length;}catalogBatch.next+=1;if(p.get(msg,'STATUS')===1&&state&&version===state.version){catalog=catalogBatch.points;catalogBatch=null;openSettings();}}catch(ignore){catalogBatch=null;}
  }else if(type===p.type.CHECK)updater.check(p.get(msg,'REQUEST'),p.get(msg,'STATUS')===1);
  else if(type===p.type.ACK)updater.receive(msg);
  else if(type===p.type.LOCATION){
    if(!state||p.get(msg,'VERSION')!==state.version)return;
    // Explicit Nearby requests are permitted with startup lookup disabled.
    nearby.request(p.get(msg,'REQUEST'),p.get(msg,'VERSION'),p.get(msg,'DATA'),!!(state.flags&2));
  }
});
