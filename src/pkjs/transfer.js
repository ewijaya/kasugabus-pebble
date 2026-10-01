'use strict';
var p = require('./protocol'), integer = require('./settings').integer;
var nextSession = ((Math.floor(Math.random()*2147483647)^Date.now())&2147483647)||1;
module.exports = function(options) {
  var job = null, timer = null;
  function clear() { if (timer !== null) options.cancel(timer); timer = null; }
  function stop(error, status) {
    if (!job) return;
    var callback=job.callback; clear(); job=null; callback(error,status);
  }
  function send() {
    if (!job) return;
    if (options.now()-job.progress >= 30000 || job.tries > 3) return stop(new Error('Transfer acknowledgement timeout'));
    clear(); job.tries += 1; var token=job.token;
    timer=options.schedule(function() { if(job && job.token===token)send(); },2000);
    options.send(job.message, function() {}, function() { /* ACK timer retries; no parallel send. */ });
  }
  function step(type, seq, data) {
    clear(); job.tries=0;job.expected=seq;job.token+=1;
    job.message={TYPE:type,SESSION:job.session};
    if(type===p.type.BEGIN) { job.message.REQUEST=job.request;job.message.VERSION=job.release.version;job.message.LENGTH=job.bytes.length;job.message.CRC=job.release.crc32; }
    if(type===p.type.CHUNK) {job.message.SEQ=seq;job.message.DATA=data;}
    send();
  }
  return {
    start: function(bytes,release,callback,request) {
      if(job) {callback(new Error('Transfer already running'));return;}
      if(!integer(request,0,4294967295)){callback(new Error('Invalid transfer request'));return;}
      nextSession=(nextSession+1)&2147483647;
      if(!nextSession)nextSession=1;
      var session=nextSession;
      job={bytes:bytes,release:release,callback:callback,request:request,session:session,expected:0,index:0,progress:options.now(),token:0};
      step(p.type.BEGIN,0);
    },
    receive: function(msg) {
      if (!job || p.get(msg,'TYPE')!==p.type.ACK || p.get(msg,'SESSION')!==job.session || p.get(msg,'SEQ')!==job.expected || p.get(msg,'FLAGS')!==job.message.TYPE) return;
      var status=p.get(msg,'STATUS'),type=job.message.TYPE;
      if(status===1)return send();
      if(status===2 || status===5 || status===6)return stop(new Error('Watch rejected candidate: '+status),status);
      if(type===p.type.COMMIT) {if(status===3 || status===4)stop(null,status);return;}
      if(status!==0)return;
      job.progress=options.now();
      if(type===p.type.CHUNK)job.index+=192;
      if(job.index<job.bytes.length)step(p.type.CHUNK,Math.floor(job.index/192),job.bytes.slice(job.index,job.index+192));
      else step(p.type.COMMIT,65535);
    },
    cancel: function() {stop(new Error('Transfer cancelled'));},
    busy: function() {return !!job;}
  };
};
