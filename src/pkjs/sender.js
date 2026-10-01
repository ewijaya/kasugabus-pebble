'use strict';
var protocol=require('./protocol');
// App-level acknowledgements may arrive before the SDK transport callback.
// Keep one SDK send active and release FIFO work only on that callback.
module.exports=function(options){
  var queue=[],active=null,timer=null,blocked=false,resetting=false;
  var limit=options.maxQueue||8,timeout=options.transportTimeout||10000;
  function fail(entry,error){if(!entry.finished){entry.finished=true;entry.failure(error);}}
  function clear(){if(timer!==null)options.cancel(timer);timer=null;}
  function complete(entry,success,value){
    if(active!==entry)return;
    clear();active=null;blocked=false;
    if(!entry.finished){entry.finished=true;if(success)entry.success(value);else entry.failure(value);}
    pump();
  }
  function pump(){
    if(active||blocked||resetting||!queue.length)return;
    var entry=active=queue.shift();
    timer=options.schedule(function(){
      if(active!==entry)return;
      timer=null;blocked=true;
      var abandoned=queue;queue=[];
      fail(entry,new Error('Transport acknowledgement timeout'));
      abandoned.forEach(function(item){fail(item,new Error('Transport unavailable'));});
      // The old transaction may still exist in the SDK. Do not overlap it;
      // a late callback or explicit reconnect reset will permit another send.
    },timeout);
    try{options.send(protocol.wire(entry.message),function(value){complete(entry,true,value);},function(error){complete(entry,false,error);});}
    catch(error){complete(entry,false,error);}
  }
  function send(message,success,failure){
    var entry={message:message,success:success||function(){},failure:failure||function(){},finished:false};
    if(blocked||resetting){fail(entry,new Error('Transport unavailable'));return false;}
    if(queue.length+(active?1:0)>=limit){fail(entry,new Error('Transport queue is full'));return false;}
    queue.push(entry);pump();return true;
  }
  send.reset=function(){
    resetting=true;clear();var abandoned=queue;queue=[];var previous=active;active=null;blocked=false;
    if(previous)fail(previous,new Error('Transport reset'));
    abandoned.forEach(function(item){fail(item,new Error('Transport reset'));});
    resetting=false;pump();
  };
  send.pending=function(){return queue.length+(active?1:0);};
  return send;
};
