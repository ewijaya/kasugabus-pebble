"""Offline production-observer proofs. No network, emulator or SDK writes."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import Mock, patch
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("production", ROOT / "tools/verify_production_feed.py")
production = importlib.util.module_from_spec(spec)
spec.loader.exec_module(production)
PYTHON = Path(os.environ.get("KASUGABUS_PEBBLE_PYTHON", str(Path.home() / ".local/share/uv/tools/pebble-tool/bin/python")))


class ProductionFeedTests(unittest.TestCase):
    def setUp(self):
        self.raw = bytes(range(256)) + b"test-only remaining bytes"
        self.release = {"version": 2, "bytes": len(self.raw), "sha256": production.sha(self.raw), "crc32": zlib.crc32(self.raw) & 0xffffffff}
        self.proof = production.TransferProof(self.release)

    def begin(self):
        self.proof.watch({"0": 3, "7": 1, "8": 41})
        self.proof.phone({"0": 5, "8": 41, "1": 15, "3": 2, "4": len(self.raw), "5": self.release["crc32"]})
        self.proof.watch({"0": 8, "1": 15, "2": 0, "7": 0, "13": 5})

    def chunks(self):
        for seq, offset in enumerate(range(0, len(self.raw), 192)):
            self.proof.phone({"0": 6, "1": 15, "2": seq, "6": list(self.raw[offset:offset+192])})
            self.proof.watch({"0": 8, "1": 15, "2": seq, "7": 0, "13": 6})

    def test_success_requires_actual_request_all_bytes_native_acks_and_commit(self):
        self.begin()
        self.chunks()
        self.proof.phone({"0": 6, "1": 15, "2": 0, "6": list(self.raw[:192])})
        self.proof.watch({"0": 8, "1": 15, "2": 0, "7": 0, "13": 6})
        self.proof.phone({"0": 7, "1": 15})
        self.proof.watch({"0": 8, "1": 15, "2": 65535, "7": 3, "13": 7})
        self.proof.phone({"0": 4, "8": 41, "7": 3, "9": int(time.time())})
        result = self.proof.result()
        self.assertEqual(result["uniqueChunks"], 2)
        self.assertEqual(result["chunksSent"], 3)
        self.assertEqual(result["nativeChunkAcks"], 2)
        self.assertEqual(result["sha256"], production.sha(self.raw))

    def test_desktop_begin_without_native_manual_check_and_request_mismatch_rejected(self):
        begin = {"0": 5, "8": 41, "1": 15, "3": 2, "4": len(self.raw), "5": self.release["crc32"]}
        for message in ({"0": 3, "7": 0, "8": 41}, {"0": 2, "8": 41}):
            self.proof.watch(message)
            with self.assertRaisesRegex(ValueError, "native manual CHECK"):
                self.proof.phone(begin)
        self.proof.watch({"0": 3, "7": 1, "8": 42})
        with self.assertRaisesRegex(ValueError, "native manual CHECK"):
            self.proof.phone(begin)

    def test_missing_ack_flags_wrong_session_and_out_of_order_chunks_rejected(self):
        self.begin()
        with self.assertRaisesRegex(ValueError, "FLAGS"):
            self.proof.watch({"0": 8, "1": 15, "2": 0, "7": 0})
        with self.assertRaisesRegex(ValueError, "session"):
            self.proof.phone({"0": 6, "1": 16, "2": 0, "6": list(self.raw[:192])})
        with self.assertRaisesRegex(ValueError, "contiguous"):
            self.proof.phone({"0": 6, "1": 15, "2": 1, "6": list(self.raw[192:])})

    def test_corrupt_or_partial_payload_and_missing_chunk_ack_rejected(self):
        self.begin()
        with self.assertRaisesRegex(ValueError, "transferred bytes"):
            self.proof.phone({"0": 7, "1": 15})
        self.chunks()
        self.proof.acked.remove(1)
        with self.assertRaisesRegex(ValueError, "all native chunk ACKs"):
            self.proof.phone({"0": 7, "1": 15})
        self.proof.acked.add(1)
        self.proof.parts[1] = b"x" * len(self.proof.parts[1])
        with self.assertRaisesRegex(ValueError, "transferred bytes"):
            self.proof.phone({"0": 7, "1": 15})

    def test_feed_success_cannot_replace_native_commit_or_hide_failure(self):
        self.begin()
        with self.assertRaisesRegex(ValueError, "native commit"):
            self.proof.phone({"0": 4, "8": 41, "7": 3, "9": int(time.time())})
        for status in (4, 5, 6, 7):
            with self.assertRaisesRegex(ValueError, "feed failure"):
                self.proof.phone({"0": 4, "8": 41, "7": status})

    def test_production_fetch_has_no_url_override_and_rejects_live_hash_mismatch(self):
        with self.assertRaisesRegex(ValueError, "production URL"):
            production.read_https("http://127.0.0.1:8910/manifest.json", 8192)
        release = dict(self.release, url=production.URL.removesuffix("manifest.json") + "releases/2-test.bin")
        feed = {"current": release, "upcoming": None}
        with patch.object(production, "read_https", side_effect=[(json.dumps(feed).encode(), {}), (b"corrupt", {})]), patch.object(production.subprocess, "run") as validator, self.assertRaisesRegex(ValueError, "Live payload"):
            production.live_snapshot(2)
        validator.assert_not_called()

    def test_runner_cannot_send_appmessages_or_override_preferences(self):
        emulator = production.Emulator.__new__(production.Emulator)
        emulator.process = Mock()
        for op in ("send", "settings", "time", "bluetooth"):
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                emulator.command(op)
        emulator.process.stdin.write.assert_not_called()

    @unittest.skipUnless(PYTHON.is_file(), "Installed SDK Python unavailable")
    def test_real_sdk_xhr_fetch_preserves_every_binary_byte_with_one_response_read(self):
        script = r'''
import pypkjs
import json,time
from pathlib import Path
from types import SimpleNamespace
import gevent,gevent.pool,gevent.queue
import STPyV8 as v8
from pypkjs.javascript.events import EventExtension
from pypkjs.javascript.xhr import XHRExtension,prepare_xhr
from pypkjs.javascript.timers import Timers
payload=bytes(range(256))*95
calls={}
class Global(v8.JSClass):
    def exec(self,name,args):return calls[name](*args)
class Runtime:
    def __init__(self):
        self.context=v8.JSContext(Global());self.group=gevent.pool.Group();self.queue=gevent.queue.Queue();self.block_private_addresses=False
    def register_syscall(self,name,fn):calls[name]=fn
    def run_js(self,source):self.context.eval(source)
    def enqueue(self,fn,*args,**kwargs):self.queue.put((fn,args,kwargs))
    def log_output(self,message):raise AssertionError('Unexpected SDK JavaScript error: '+str(message))
class NoNetworkSession:
    def prepare_request(self,request):return request
    def send(self,request,timeout,verify):
        assert verify and timeout==1 and request.url=='https://ewijaya.github.io/kasugabus-pebble/timetables/fixture.bin'
        return SimpleNamespace(status_code=200,reason='OK',content=payload,text='deliberately wrong Unicode fallback')
runtime=Runtime()
with runtime.context:
    # These are the installed JSRuntime's exact proxy/property definitions.
    runtime.run_js("function _make_proxies(proxy,origin,names){names.forEach(function(name){proxy[name]=function(...args){return origin[name](...args);};});return proxy;}function _make_properties(proxy,origin,names){names.forEach(function(name){Object.defineProperty(proxy,name,{configurable:false,enumerable:true,get:function(){return origin[name];},set:function(value){origin[name]=value;}});});return proxy;}")
    EventExtension(runtime);XHRExtension(runtime);Timers(runtime);prepare_xhr(runtime)
    runtime.context.locals._init_xhr(runtime,NoNetworkSession())
    modules={path.stem:path.read_text() for path in Path('src/pkjs').glob('*.js')}
    runtime.run_js('var sources='+json.dumps(modules)+";var cache={};function req(name){name=name.replace('./','');if(cache[name])return cache[name].exports;var module=cache[name]={exports:{}};new Function('require','module','exports',sources[name])(req,module,module.exports);return module.exports;}var result=null;")
    def complete(expression):
        runtime.context.eval('result=null;'+expression)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline and runtime.context.eval('result===null'):
            try:
                function,args,kwargs=runtime.queue.get(timeout=.05);function(*args,**kwargs)
            except gevent.queue.Empty:pass
        assert not runtime.context.eval('result===null'),'Real SDK XHR callback did not finish'
        return json.loads(runtime.context.eval('JSON.stringify(result)'))
    fixed=complete("req('updater').xhrFetch('https://ewijaya.github.io/kasugabus-pebble/timetables/fixture.bin',32768,true,1000,function(error,bytes){result={error:error&&error.message,bytes:bytes};});")
    assert fixed['error'] is None and bytes(fixed['bytes'])==payload,('Fixed SDK extraction lost bytes',len(fixed.get('bytes',[])))
    # Demonstrate the observed host defect independently: repeated reads of a
    # fresh real SDK XHR convert the response to a zero-length typed array.
    broken=complete("var x=new XMLHttpRequest();x.open('GET','https://ewijaya.github.io/kasugabus-pebble/timetables/fixture.bin',true);x.timeout=1000;x.responseType='arraybuffer';x.onload=function(){var bytes=[];if(x.response&&typeof x.response!=='string'){var raw=new Uint8Array(x.response);for(var i=0;i<raw.length;i++)bytes.push(raw[i]);}result={bytes:bytes};};x.send(null);")
    assert broken['bytes']==[],'Installed repeated-getter regression no longer reproduces; review this fixture'
    oversized=complete("req('updater').xhrFetch('https://ewijaya.github.io/kasugabus-pebble/timetables/fixture.bin',128,true,1000,function(error,bytes){result={error:error&&error.message};});")
    assert oversized['error']=='Response exceeds size limit'
    runtime.group.kill()
print('PASS actual installed SDK XHR repeated-getter failure, cached extraction exact bytes, unsafe text unused and size guard retained')
'''
        result = subprocess.run([str(PYTHON), "-c", script], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout)

    @unittest.skipUnless(PYTHON.is_file(), "Installed SDK Python unavailable")
    def test_installed_sdk_passive_relay_decoder_signed_crc_fragmentation_and_privacy(self):
        script = r'''
import importlib.util,struct
from types import SimpleNamespace
from uuid import UUID
from libpebble2.protocol.appmessage import AppMessage,AppMessagePush,AppMessageTuple
spec=importlib.util.spec_from_file_location('bridge','tools/emu_update_bridge.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
target=UUID('d7ba77b0-d528-4cc8-b35c-7052798152c9')
def packet(kind,other=()):
    tuples=[AppMessageTuple(key=0,type=2,data=struct.pack('<I',kind))]+list(other)
    return AppMessage(transaction_id=9,data=AppMessagePush(uuid=target,dictionary=tuples)).serialise_packet()
events=[];observer=bridge.ProductionObserver(target,events.append)
raw=packet(5,[AppMessageTuple(key=5,type=3,data=struct.pack('<i',-1))])
observer.receive(SimpleNamespace(payload=raw[:3]));assert not events
observer.receive(SimpleNamespace(payload=raw[3:]));assert events[0]['message']['5']==0xffffffff
chunk=packet(6,[AppMessageTuple(key=6,type=0,data=b'public timetable')])
settings=packet(11,[AppMessageTuple(key=6,type=0,data=b'private prefs')])
observer.receive(SimpleNamespace(payload=chunk+settings))
assert len(events)==2 and events[1]['message']['6']==list(b'public timetable')
assert not observer.pending
try:observer.receive(SimpleNamespace(payload=b'\xff\xff\x00\x30'))
except ValueError:pass
else:raise AssertionError('unbounded relay packet accepted')
# Decoder has only a callback and byte buffer; no connection/service/send path.
assert set(observer.__dict__)=={'app_uuid','callback','pending'}
print('PASS real SDK packet framing, signed CRC, fragmented/multiple packets, privacy and passive-only decoder')
'''
        result = subprocess.run([str(PYTHON), "-c", script], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
