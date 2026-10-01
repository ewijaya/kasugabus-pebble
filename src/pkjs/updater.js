'use strict';
var p=require('./protocol'), manifest=require('./manifest'), binary=require('./binary'), transfer=require('./transfer');
var integer=require('./settings').integer;
// The injectable fetcher exists for tests; production uses xhrFetch, which never
// permits local HTTP. Test transport policy cannot be selected through settings.
function xhrFetch(url, maxBytes, binaryResponse, timeout, callback) {
  var xhr=new XMLHttpRequest(),done=false,timer=null;
  function finish(error,value){if(done)return;done=true;if(timer!==null)clearTimeout(timer);callback(error,value);}
  try {
    manifest.origin(url,false);xhr.open('GET',url,true);
    if(binaryResponse){try{xhr.responseType='arraybuffer';}catch(ignore){}if(xhr.overrideMimeType)xhr.overrideMimeType('text/plain; charset=x-user-defined');}
    xhr.timeout=timeout;
    xhr.onprogress=function(event){if(event.loaded>maxBytes){xhr.abort();finish(new Error('Response exceeds size limit'));}};
    xhr.onload=function(){
      if(xhr.status!==200)return finish(new Error('Feed HTTP '+xhr.status));
      try{if(xhr.responseURL&&manifest.origin(xhr.responseURL,false)!==manifest.origin(url,false))throw new Error('Feed redirect leaves approved host');}catch(e){return finish(e);}
      var value;
      if(binaryResponse){
        value=[];
        // Some SDK hosts change the ArrayBuffer proxy on a repeated getter.
        // Keep the first response object for both detection and extraction.
        var rawResponse=xhr.response;
        if(rawResponse&&typeof rawResponse!=='string'&&typeof Uint8Array!=='undefined'){
          var bytes=new Uint8Array(rawResponse);for(var i=0;i<bytes.length;i+=1)value.push(bytes[i]);
        }else{var response=xhr.responseText||'';for(i=0;i<response.length;i+=1)value.push(response.charCodeAt(i)&255);}
      }else value=xhr.responseText;
      if(value.length>maxBytes)return finish(new Error('Response exceeds size limit'));
      finish(null,value);
    };
    xhr.onerror=function(){finish(new Error('Network unavailable'));};
    xhr.ontimeout=function(){finish(new Error('Network timeout'));};
    xhr.onabort=function(){finish(new Error('Network request aborted'));};
    timer=setTimeout(function(){xhr.abort();finish(new Error('Network timeout'));},timeout);
    xhr.send(null);
  }catch(e){finish(e);}
  return function(){xhr.abort();finish(new Error('Cancelled'));};
}
module.exports=function(options){
  var config=options.config,job=null,state=null,transport=transfer(options),cancelFetch=null;
  function feed(current,status,stamp){if(job!==current)return;current.status=status;var msg={TYPE:p.type.FEED,REQUEST:current.request,STATUS:status};if(stamp)msg.STAMP=stamp;options.send(msg);}
  function finish(current,error){
    if(job!==current)return;
    var msg={TYPE:p.type.FEED,REQUEST:current.request,STATUS:error?(error.incompatible?p.feed.INCOMPATIBLE:p.feed.FAILED):(current.updated?p.feed.UPDATED:p.feed.CHECKED)};
    if(!error)msg.STAMP=Math.floor(options.now()/1000);
    job=null;cancelFetch=null;options.send(msg);
  }
  function fetchFor(current,url,maxBytes,isBinary,callback){
    if(job!==current)return;
    var completed=false,handle;
    function receive(error,value){
      if(completed)return;
      completed=true;
      // Aborting an XHR may deliver a callback after the next check starts.
      if(job!==current)return;
      cancelFetch=null;callback(error,value);
    }
    try{handle=options.fetch(url,maxBytes,isBinary,config.requestTimeout,receive);}catch(error){receive(error);}
    if(!completed&&job===current)cancelFetch=handle;
  }
  function download(current,queue){
    if(job!==current)return;
    if(!queue.length)return finish(current,null);
    var release=queue.shift();feed(current,p.feed.DOWNLOADING);
    fetchFor(current,release.url,release.bytes,true,function(error,bytes){
      if(error)return finish(current,error);
      var metadata;try{metadata=binary.validate(bytes,config,release);}catch(e){return finish(current,e);}
      feed(current,p.feed.TRANSFERRING);
      if(job!==current)return;
      transport.start(bytes,release,function(error,status){if(job!==current)return;if(error){if(status===6)error.incompatible=true;return finish(current,error);}current.updated=true;if(status===3)state.version=Math.max(state.version,release.version);else state.pending=Math.max(state.pending,release.version);if(options.catalog&&status===3)options.catalog(metadata.catalog);download(current,queue);},current.request);
    });
  }
  return {
    state:function(value){state=value;},
    check:function(request,manual){
      if(!integer(request,0,4294967295)||!state)return;
      if(job){options.send({TYPE:p.type.FEED,REQUEST:request,STATUS:job.status});return;}
      job={request:request,updated:false,status:p.feed.CHECKING};var current=job;
      if(!config.manifestUrl){feed(current,p.feed.NOT_CONFIGURED);job=null;return;}
      try{manifest.origin(config.manifestUrl,!!options.testInsecure);}catch(e){feed(current,p.feed.NOT_CONFIGURED);job=null;return;}
      // Eligibility is watch-owned. A settings change cannot manufacture checks.
      if(!manual&&!(state.flags&1)){job=null;return;}
      feed(current,p.feed.CHECKING);
      fetchFor(current,config.manifestUrl,config.manifestMaxBytes,false,function(error,text){
        if(error)return finish(current,error);
        var feedValue;try{feedValue=manifest.validate(JSON.parse(text),config,options.now(),!!options.testInsecure);}catch(e){return finish(current,e);}
        var queue=[];
        // Preserve the watch's valid scheduled future snapshot if a replacement
        // is interrupted. Stage its newer replacement before the current one.
        if(feedValue.upcoming&&feedValue.upcoming.version>Math.max(state.version,state.pending))queue.push(feedValue.upcoming);
        if(feedValue.current.version>state.version)queue.push(feedValue.current);
        download(current,queue);
      });
    },
    receive:function(msg){transport.receive(msg);},
    busy:function(){return !!job;},
    cancel:function(){
      var cancelled=job,abort=cancelFetch;
      // Clear identity before abort/transport callbacks, which may be immediate.
      job=null;cancelFetch=null;
      if(abort){try{abort();}catch(ignore){}}transport.cancel();
      if(cancelled)options.send({TYPE:p.type.FEED,REQUEST:cancelled.request,STATUS:p.feed.FAILED});
    }
  };
};
module.exports.xhrFetch=xhrFetch;
