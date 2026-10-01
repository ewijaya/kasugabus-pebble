'use strict';
function crc32(bytes, start) {
  var crc = -1;
  for (var i = start || 0; i < bytes.length; i += 1) {
    crc ^= bytes[i];
    for (var j = 0; j < 8; j += 1) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  return (crc ^ -1) >>> 0;
}
function sha256(bytes) {
  var constants = [1116352408,1899447441,3049323471,3921009573,961987163,1508970993,2453635748,2870763221,
    3624381080,310598401,607225278,1426881987,1925078388,2162078206,2614888103,3248222580,
    3835390401,4022224774,264347078,604807628,770255983,1249150122,1555081692,1996064986,
    2554220882,2821834349,2952996808,3210313671,3336571891,3584528711,113926993,338241895,
    666307205,773529912,1294757372,1396182291,1695183700,1986661051,2177026350,2456956037,
    2730485921,2820302411,3259730800,3345764771,3516065817,3600352804,4094571909,275423344,
    430227734,506948616,659060556,883997877,958139571,1322822218,1537002063,1747873779,
    1955562222,2024104815,2227730452,2361852424,2428436474,2756734187,3204031479,3329325298];
  var h = [1779033703,3144134277,1013904242,2773480762,1359893119,2600822924,528734635,1541459225];
  var data = bytes.slice(), bitlen = data.length * 8, words = [], i;
  data.push(128); while (data.length % 64 !== 56) data.push(0);
  for (i = 0; i < 4; i += 1) data.push(0);
  data.push(bitlen >>> 24 & 255, bitlen >>> 16 & 255, bitlen >>> 8 & 255, bitlen & 255);
  function rotate(x, n) { return (x >>> n) | (x << (32 - n)); }
  for (var offset = 0; offset < data.length; offset += 64) {
    for (i = 0; i < 16; i += 1) words[i] = data[offset+i*4]<<24 | data[offset+i*4+1]<<16 | data[offset+i*4+2]<<8 | data[offset+i*4+3];
    for (i = 16; i < 64; i += 1) {
      var x = words[i - 15], y = words[i - 2];
      words[i] = ((rotate(x,7)^rotate(x,18)^(x>>>3)) + words[i-16] + (rotate(y,17)^rotate(y,19)^(y>>>10)) + words[i-7]) | 0;
    }
    var a=h[0], b=h[1], c=h[2], d=h[3], e=h[4], f=h[5], g=h[6], k=h[7];
    for (i=0;i<64;i+=1) {
      var t1 = (k + (rotate(e,6)^rotate(e,11)^rotate(e,25)) + ((e&f)^(~e&g)) + constants[i] + words[i]) | 0;
      var t2 = ((rotate(a,2)^rotate(a,13)^rotate(a,22)) + ((a&b)^(a&c)^(b&c))) | 0;
      k=g;g=f;f=e;e=(d+t1)|0;d=c;c=b;b=a;a=(t1+t2)|0;
    }
    var result=[a,b,c,d,e,f,g,k]; for(i=0;i<8;i+=1)h[i]=(h[i]+result[i])|0;
  }
  return h.map(function(x) { return ('00000000'+(x>>>0).toString(16)).slice(-8); }).join('');
}
module.exports = { crc32: crc32, sha256: sha256 };
