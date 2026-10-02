'use strict';
var protocol=require('./protocol'),nearby=require('./nearby'),integer=require('./settings').integer;
var STORAGE_KEY='kasugabus.saved-home.v1';
function homeRecord(value){
  if(!value||value.schema!==1||!value.coords||
      typeof value.coords.latitude!=='number'||!isFinite(value.coords.latitude)||Math.abs(value.coords.latitude)>90||
      typeof value.coords.longitude!=='number'||!isFinite(value.coords.longitude)||Math.abs(value.coords.longitude)>180||
      typeof value.coords.accuracy!=='number'||!isFinite(value.coords.accuracy)||value.coords.accuracy<0||value.coords.accuracy>100||
      !integer(value.savedAt,0,4294967295999))return null;
  return {schema:1,coords:{latitude:value.coords.latitude,longitude:value.coords.longitude,accuracy:value.coords.accuracy},savedAt:value.savedAt};
}
module.exports=function(options){
  var generation=0,timer=null,home=null,lastStatus=null,storage=options.storage,
    revision=0,pending=null,storedRaw=null,notificationGeneration=0,flight=null,retryTimer=null,attempts=0;
  try{
    var raw=storage&&storage.getItem(STORAGE_KEY),value;
    if(typeof raw==='string'&&raw.length<=768){
      value=JSON.parse(raw);
      if(value&&value.schema===2){
        var loaded=homeRecord(value.home);
        if((value.home===null||loaded)&&integer(value.revision,1,4294967295)&&
          (value.pending===null||(value.pending===0&&loaded)||(value.pending===9&&value.home===null))){
          home=loaded;revision=value.revision;pending=value.pending;storedRaw=raw;
        }
      }else home=homeRecord(value);
    }
  }catch(ignore){}
  function invalidate(){generation+=1;if(timer!==null)options.cancel(timer);timer=null;}
  function once(callback){
    invalidate();var token=generation;
    return function(result){if(token!==generation)return;invalidate();callback(result);};
  }
  function fix(finish){
    if(!options.geolocation||typeof options.geolocation.getCurrentPosition!=='function')return finish({status:5});
    timer=options.schedule(function(){finish({status:4});},15000);
    try{options.geolocation.getCurrentPosition(function(position){finish({position:position});},
      function(error){finish({status:error&&error.code===1?3:error&&error.code===3?4:5});},
      {enableHighAccuracy:true,timeout:15000,maximumAge:0});}catch(ignore){finish({status:5});}
  }
  function envelope(record,nextRevision,status){return JSON.stringify({schema:2,home:record,revision:nextRevision,pending:status});}
  function cancelNotification(){
    notificationGeneration+=1;
    if(flight)options.cancel(flight.timer);flight=null;
    if(retryTimer!==null)options.cancel(retryTimer);retryTimer=null;
  }
  function retryLater(){
    if(pending===null||attempts>=3)return;
    retryTimer=options.schedule(function(){retryTimer=null;announce();},500);
  }
  function announce(){
    if(pending===null||flight||attempts>=3)return;
    var token=++notificationGeneration,sentRevision=revision,status=pending,settled=false;attempts+=1;
    try{if(storage.getItem(STORAGE_KEY)!==storedRaw){pending=null;return;}}catch(ignore){retryLater();return;}
    function finish(success){
      if(settled)return;settled=true;
      if(!flight||flight.token!==token)return;
      options.cancel(flight.timer);flight=null;
      if(sentRevision!==revision||status!==pending)return;
      if(success){
        try{
          // A previous worker's delayed callback must not erase a newer record.
          if(storage.getItem(STORAGE_KEY)!==storedRaw){pending=null;return;}
          if(home){var acknowledged=envelope(home,revision,null);storage.setItem(STORAGE_KEY,acknowledged);storedRaw=acknowledged;}
          else {storage.removeItem(STORAGE_KEY);storedRaw=null;}
          pending=null;return;
        }catch(ignore){}
      }
      retryLater();
    }
    flight={token:token,timer:options.schedule(function(){finish(false);},10000)};
    try{if(options.send({TYPE:protocol.type.HOME_CHANGED,STATUS:status},function(){finish(true);},function(){finish(false);})===false)finish(false);}catch(ignore){finish(false);}
  }
  function changed(record,status){
    var nextRevision=revision%4294967295+1;
    if(!storage||typeof storage.setItem!=='function')return false;
    var nextRaw=envelope(record,nextRevision,status);
    try{storage.setItem(STORAGE_KEY,nextRaw);}catch(ignore){return false;}
    // A single atomic record changes the home and its pending notification
    // together. A clear overwrites coordinates with a metadata-only tombstone.
    home=record;revision=nextRevision;pending=status;storedRaw=nextRaw;cancelNotification();attempts=0;announce();return true;
  }
  return {
    hasHome:function(){return !!home;},
    lastActionStatus:function(){return lastStatus;},
    retryNotification:function(){
      if(pending===null||flight||retryTimer!==null)return;
      attempts=0;announce();
    },
    invalidate:invalidate,
    request:function(reference,request,version,bytes,enabled){
      var finish=once(function(result){
        var message={TYPE:protocol.type.REFERENCE_RESULT,FLAGS:reference,REQUEST:request,VERSION:version,STATUS:result.status};
        if((result.status===0||result.status===1||result.status===2)&&integer(result.stamp,0,4294967295)&&integer(result.accuracy,0,4294967295)){
          message.STAMP=result.stamp;message.ACCURACY=result.accuracy;
        }
        if(result.status===0)message.DATA=result.data;
        options.send(message);
      }),points;
      if(!integer(reference,0,1)||!integer(request,1,4294967295)||!integer(version,1,4294967295))return;
      if(!enabled)return finish({status:8});
      if(reference===1&&!home)return finish({status:9});
      try{points=nearby.parse(bytes);}catch(ignore){return finish({status:5});}
      if(!points.length)return finish({status:7});
      if(reference===1){var now=options.now();return finish(nearby.rank({coords:home.coords,timestamp:now},points,now));}
      fix(function(result){finish(result.position?nearby.rank(result.position,points,options.now()):result);});
    },
    saveCurrent:function(enabled,callback){
      var finish=once(function(result){
        if(result.position){
          // Reuse Nearby's freshness/accuracy validation without requiring a
          // service-area pole: a home outside coverage can still be saved.
          var checked=nearby.rank(result.position,[],options.now());
          if(checked.status!==7)result=checked;
          else {
            var record=homeRecord({schema:1,coords:result.position.coords,savedAt:Math.floor(nearby.fixTime(result.position.timestamp,options.now()))});
            result={status:record&&changed(record,0)?0:5};
          }
        }
        lastStatus=result.status;if(callback)callback(result.status);
      });
      if(!enabled)return finish({status:8});
      fix(finish);
    },
    clear:function(){
      invalidate();
      if(!changed(null,9)){lastStatus=5;return false;}
      lastStatus=9;return true;
    }
  };
};
