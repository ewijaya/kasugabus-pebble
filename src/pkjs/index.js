'use strict';
var Clay=require('@rebble/clay'),p=require('./protocol'),settings=require('./settings'),extras=require('./extras'),config=require('./feed-config');
var catalog=require('./catalog.json').boardingPoints,snapshot=null,state=null,clay=null,catalogBatch=null,settingsOpening=false,settingsTimer=null,homeAction=null,settingsRequest=Math.floor(Date.now()%4294967295);
var send=require('./sender')({send:function(message,success,failure){Pebble.sendAppMessage(message,success,failure);},schedule:schedule,cancel:cancel});
function schedule(callback,delay){return setTimeout(callback,delay);}
function cancel(timer){clearTimeout(timer);}
var nearby=require('./nearby')({send:send,schedule:schedule,cancel:cancel,now:function(){return Date.now();},geolocation:typeof navigator!=='undefined'?navigator.geolocation:null});
var reference=require('./reference-location')({send:send,schedule:schedule,cancel:cancel,now:function(){return Date.now();},geolocation:typeof navigator!=='undefined'?navigator.geolocation:null,storage:typeof localStorage!=='undefined'?localStorage:null});
function cancelHomeAction(){if(homeAction&&homeAction.timer!==null)cancel(homeAction.timer);homeAction=null;}
function invalidateLocations(){cancelHomeAction();nearby.invalidate();reference.invalidate();}
function completeHomeAction(){
  if(!homeAction||!homeAction.acked||!homeAction.matched)return;
  var action=homeAction;cancelHomeAction();
  if(state&&state.version===action.version&&(state.flags&2))reference.saveCurrent(true);
}
var updater=require('./updater')({config:config,send:send,schedule:schedule,cancel:cancel,now:function(){return Date.now();},fetch:require('./updater').xhrFetch,
  catalog:function(value){catalog=value;invalidateLocations();}});
function openSettings(){
  if(!settingsOpening)return;settingsOpening=false;if(settingsTimer!==null)cancel(settingsTimer);settingsTimer=null;
  var walkKeys=catalog.map(function(p){return 'Walk'+p.id;});
  if(snapshot)Object.keys(snapshot.walks).forEach(function(id){if(walkKeys.indexOf('Walk'+id)===-1)walkKeys.push('Walk'+id);});
  clay=new Clay(require('./clay-config')(catalog,snapshot,reference.hasHome(),reference.lastActionStatus()),require('./custom-clay'),{autoHandleEvents:false,userData:{ids:catalog.map(function(p){return p.id;}),walkKeys:walkKeys}});
  // Clay is constructed after the ready event; initialize the documented meta
  // field used by the custom page without copying account/watch tokens.
  clay.meta.userData={ids:catalog.map(function(p){return p.id;}),walkKeys:walkKeys};
  if(Pebble.getActiveWatchInfo)clay.meta.activeWatchInfo=Pebble.getActiveWatchInfo();
  var values=snapshot?settings.toClay(snapshot,catalog):{},more=extras.toClay(snapshot&&snapshot.extras||extras.defaults());
  Object.keys(more).forEach(function(key){values[key]=more[key];});values.HomeAction='0';clay.setSettings(values);
  Pebble.openURL(clay.generateUrl());
}
function knownWithUnavailable(bytes){
  var known=catalog.slice(),seen={};known.forEach(function(x){seen[x.id]=true;});
  // Display watch-owned preferences for IDs removed by an update. Their removal
  // is explicit in the configuration form; no arbitrary replacement is chosen.
  if(bytes&&bytes.length===80){for(var i=0;i<12;i+=1){var id=settings.u16(bytes,8+i*2);if(id&&!seen[id]){known.push({id:id,label:'Unavailable #'+id});seen[id]=true;}}var defaultId=settings.u16(bytes,2);if(defaultId&&!seen[defaultId])known.push({id:defaultId,label:'Unavailable #'+defaultId});for(i=0;i<12;i+=1){id=settings.u16(bytes,32+i*4);if(id&&!seen[id]){known.push({id:id,label:'Unavailable #'+id});seen[id]=true;}}}
  return known;
}
Pebble.addEventListener('ready',function(){invalidateLocations();send.reset();send({TYPE:p.type.HELLO});reference.retryNotification();});
Pebble.addEventListener('showConfiguration',function(){invalidateLocations();settingsOpening=true;if(settingsTimer!==null)cancel(settingsTimer);settingsTimer=schedule(openSettings,2000);send({TYPE:p.type.HELLO});});
Pebble.addEventListener('webviewclosed',function(event){
  if(!event||!event.response||!clay)return;
  try{
    var text=event.response.charAt(0)==='{'?event.response:decodeURIComponent(event.response),values=JSON.parse(text);
    var candidate=settings.fromClay(values,catalog),bytes=settings.encode(candidate,catalog);
    // One SETTINGS message carries both records so the watch saves both or neither.
    var extraBytes=extras.encode(extras.fromClay(values,catalog,snapshot&&snapshot.extras),catalog);
    var action=typeof values.HomeAction==='undefined'?0:values.HomeAction;
    if(action&&typeof action==='object')action=action.value;
    if(!(typeof action==='number'||(typeof action==='string'&&/^[0-9]+$/.test(action)))||!settings.integer(Number(action),0,2))throw new Error('Invalid saved home action');
    action=Number(action);if(action===1&&!(candidate.flags&2))throw new Error('Phone location is disabled');
    invalidateLocations();
    if(action===2)reference.clear();
    var message={TYPE:p.type.SETTINGS,DATA:bytes.concat(extraBytes)};
    if(action===1){
      if(!state||!settings.integer(state.version,1,4294967295))throw new Error('Watch state is unavailable');
      settingsRequest=settingsRequest%4294967295+1;message.REQUEST=settingsRequest;
      homeAction={request:settingsRequest,version:state.version,bytes:bytes,acked:false,matched:false,timer:null};
      homeAction.timer=schedule(cancelHomeAction,15000);
    }
    send(message,null,function(){if(homeAction&&homeAction.request===message.REQUEST)cancelHomeAction();});
    // Do not mutate the confirmed snapshot until a valid watch STATE replies.
  }catch(e){console.log('KasugaBus preferences rejected.');cancelHomeAction();if(snapshot){var previous=settings.toClay(snapshot,catalog),old=extras.toClay(snapshot.extras||extras.defaults());Object.keys(old).forEach(function(key){previous[key]=old[key];});previous.HomeAction='0';clay.setSettings(previous);}}
});
Pebble.addEventListener('appmessage',function(event){
  var msg=event.payload||{},type=p.get(msg,'TYPE');
  if(type===p.type.STATE){
    if(p.get(msg,'STATUS')===1){invalidateLocations();send.reset();send({TYPE:p.type.HELLO});}
    if(p.get(msg,'STATUS')===2){updater.cancel();invalidateLocations();}
    var oldVersion=state&&state.version,oldFlags=state&&state.flags;
    state={version:p.get(msg,'VERSION')||0,pending:p.get(msg,'PENDING')||0,flags:p.get(msg,'FLAGS')||0,request:p.get(msg,'REQUEST')||0};
    var maximum=p.get(msg,'LENGTH');if(settings.integer(maximum,128,32768))config.maxPayload=maximum;
    updater.state(state);if((oldVersion&&oldVersion!==state.version)||((oldFlags&2)&&!(state.flags&2)))invalidateLocations();
    try{var data=p.get(msg,'DATA'),bytes=Array.isArray(data)?data.slice(0,80):data;snapshot=settings.decode(bytes,knownWithUnavailable(bytes));
      try{snapshot.extras=Array.isArray(data)&&data.length===80+extras.BYTES?extras.decode(data.slice(80)):extras.defaults();}catch(ignore){snapshot.extras=extras.defaults();}
      if(homeAction){var canonical=settings.encode(snapshot,knownWithUnavailable(bytes));homeAction.matched=canonical.every(function(value,index){return value===homeAction.bytes[index];})&&snapshot.flags===state.flags;completeHomeAction();}
    }catch(ignore){if(homeAction)homeAction.matched=false;}
    reference.retryNotification();
    // CATALOG will open with the complete live ID set; timeout is a safe fallback.
  }else if(type===13){
    var seq=p.get(msg,'SEQ'),version=p.get(msg,'VERSION'),data=p.get(msg,'DATA');
    if(seq===0)catalogBatch={next:0,version:version,points:[],seen:{}};
    if(!catalogBatch||version!==catalogBatch.version||seq!==catalogBatch.next||!Array.isArray(data))return;
    try{for(var i=0;i<data.length;){if(i+3>data.length)throw new Error('catalog');var id=settings.u16(data,i),length=data[i+2];i+=3;if(!id||!length||i+length>data.length||catalogBatch.seen[id])throw new Error('catalog');var text='';for(var j=0;j<length;j+=1)text+='%'+('0'+data[i+j].toString(16)).slice(-2);catalogBatch.points.push({id:id,label:decodeURIComponent(text)});catalogBatch.seen[id]=true;i+=length;}catalogBatch.next+=1;if(p.get(msg,'STATUS')===1&&state&&version===state.version){catalog=catalogBatch.points;catalogBatch=null;openSettings();}}catch(ignore){catalogBatch=null;}
  }else if(type===p.type.CHECK)updater.check(p.get(msg,'REQUEST'),p.get(msg,'STATUS')===1);
  else if(type===p.type.ACK){
    if(p.get(msg,'FLAGS')===p.type.SETTINGS){
      if(homeAction&&p.get(msg,'REQUEST')===homeAction.request){if(p.get(msg,'STATUS')===0){homeAction.acked=true;completeHomeAction();}else cancelHomeAction();}
    }else updater.receive(msg);
  }
  else if(type===p.type.LOCATION){
    if(!state||p.get(msg,'VERSION')!==state.version)return;
    cancelHomeAction();reference.invalidate();
    // Explicit Nearby requests are permitted with startup lookup disabled.
    nearby.request(p.get(msg,'REQUEST'),p.get(msg,'VERSION'),p.get(msg,'DATA'),!!(state.flags&2));
  }else if(type===p.type.REFERENCE_LOCATION){
    if(!state||p.get(msg,'VERSION')!==state.version)return;
    cancelHomeAction();nearby.invalidate();
    reference.request(p.get(msg,'FLAGS'),p.get(msg,'REQUEST'),p.get(msg,'VERSION'),p.get(msg,'DATA'),!!(state.flags&2));
  }
});
