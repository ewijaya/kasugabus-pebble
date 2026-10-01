"""Offline regressions against the installed PebbleKit JS host/tuple encoder."""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(os.environ.get("KASUGABUS_PEBBLE_PYTHON", str(Path.home() / ".local/share/uv/tools/pebble-tool/bin/python")))


class InstalledPhoneSDKTests(unittest.TestCase):
    @unittest.skipUnless(PYTHON.is_file(), "Installed pebble-tool Python is unavailable")
    def test_bridge_native_monitor_screenshot_and_protocol_raw(self):
        script = r'''
import importlib.util, tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from libpebble2.exceptions import TimeoutError
spec=importlib.util.spec_from_file_location('bridge','tools/emu_update_bridge.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
image=Image.new('RGB',(200,228),(39,78,100))
connection=SimpleNamespace(qemu_monitor_port=12345)
with tempfile.TemporaryDirectory() as directory, patch.object(bridge.ScreenshotCommand,'_grab_qemu_monitor_image_fast',return_value=image) as capture:
    event=bridge.control(connection,{'op':'screenshot','path':directory+'/native.png'})
    with Image.open(event['path']) as saved:
        assert saved.size==(200,228) and saved.getpixel((0,0))==(39,78,100)
    assert event['source']=='qemu-monitor' and event['backlight']=='as-captured' and event['rawRGB'] is False
    assert capture.call_count==1 # No watch-protocol method exists on this fake connection.
with tempfile.TemporaryDirectory() as directory, patch.object(bridge.ScreenshotCommand,'_grab_qemu_monitor_image_fast',return_value=Image.new('RGB',(201,228))):
    try: bridge.control(connection,{'op':'screenshot','path':directory+'/wrong.png'})
    except ValueError as error: assert '200x228' in str(error)
    else: raise AssertionError('Different monitor size was accepted')
    assert not Path(directory+'/wrong.png').exists()
closed=[];sent=[]
queue=SimpleNamespace(close=lambda:closed.append(True))
connection.get_endpoint_queue=lambda endpoint:queue
connection.send_packet=sent.append
rows=[bytearray([0,255,255]*200) for _ in range(228)]
with tempfile.TemporaryDirectory() as directory, patch.object(bridge.ScreenshotCommand,'_grab_qemu_monitor_image_fast',side_effect=AssertionError('raw must bypass monitor')), patch.object(bridge.Screenshot,'_read_screenshot',return_value=rows):
    event=bridge.control(connection,{'op':'screenshot','path':directory+'/raw.png','rawRGB':True})
    with Image.open(event['path']) as saved: assert saved.getpixel((0,0))==(0,255,255)
    assert event['source']=='watch-protocol' and event['colourCorrection']=='raw-RGB8' and closed
with tempfile.TemporaryDirectory() as directory, patch.object(bridge.ScreenshotCommand,'_grab_qemu_monitor_image_fast',side_effect=OSError('monitor unavailable')), patch.object(bridge.Screenshot,'_read_screenshot',return_value=rows):
    event=bridge.control(connection,{'op':'screenshot','path':directory+'/fallback.png'})
    with Image.open(event['path']) as saved: assert saved.getpixel((0,0))==(132,245,241)
    assert event['monitorError']=='OSError: monitor unavailable' and event['source']=='watch-protocol'
closed.clear()
with patch.object(bridge.Screenshot,'_read_screenshot',side_effect=TimeoutError()):
    try: bridge.screenshot_rows(connection,True)
    except TimeoutError as error: assert bridge.error_text(error)=='TimeoutError'
    else: raise AssertionError('Protocol timeout was ignored')
    assert closed # Timeout must not leak the SDK endpoint queue.
print('PASS native monitor pixels/dimensions, protocol raw/corrected fallback, queue cleanup and named timeout')
'''
        result = subprocess.run([str(PYTHON), "-c", script], cwd=ROOT, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout)

    @unittest.skipUnless(PYTHON.is_file(), "Installed pebble-tool Python is unavailable")
    def test_bridge_observes_pushes_without_duplicate_relay_ack(self):
        script = r'''
import importlib.util, struct
from uuid import UUID
from libpebble2.protocol.appmessage import AppMessage, AppMessageACK, AppMessagePush, AppMessageTuple
from libpebble2.services.appmessage import AppMessageService, Uint32
spec=importlib.util.spec_from_file_location('bridge','tools/emu_update_bridge.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
class NoConnection:
    def __init__(self): self.sent=[];self.registration=None;self.removed=None
    def register_endpoint(self,endpoint,handler): self.registration=(endpoint,handler);return 'registration'
    def unregister_endpoint(self,handle): self.removed=handle
    def send_packet(self,packet): packet.serialise();self.sent.append(packet)
connection=NoConnection();service=AppMessageService(bridge.RelayMessageConnection(connection))
assert connection.registration[0] is AppMessage
received=[];service.register_handler('appmessage',lambda tid,target,data:received.append((tid,target,data)))
target=UUID(int=1)
watch_push=AppMessage(transaction_id=77,data=AppMessagePush(uuid=target,dictionary=[
    AppMessageTuple(key=1,type=AppMessageTuple.Type.Uint,data=struct.pack('<I',0xffffffff))]))
watch_push=AppMessage.parse(watch_push.serialise())[0]
connection.registration[1](watch_push)
assert received==[(77,target,{1:0xffffffff})] and connection.sent==[] # SDK decoder worked, its automatic ACK was suppressed.
transaction=service.send_message(target,{1:Uint32(0xffffffff)})
assert len(connection.sent)==1 and isinstance(connection.sent[0].data,AppMessagePush)
callbacks=[];service.register_handler('ack',lambda tid,target:callbacks.append((tid,target)))
connection.registration[1](AppMessage(transaction_id=transaction,data=AppMessageACK()))
assert callbacks==[(transaction,target)] # Outbound transaction tracking still works.
service.shutdown();assert connection.removed=='registration'
print('PASS relay adapter decodes push without ACK, forwards own push/registration and tracks native ACK')
'''
        result = subprocess.run([str(PYTHON), "-c", script], cwd=ROOT, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout)

    @unittest.skipUnless(PYTHON.is_file(), "Installed pebble-tool Python is unavailable")
    def test_actual_sdk_unsigned_outgoing_and_incoming(self):
        script = r'''
import json, struct, subprocess, zlib
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
import STPyV8 as v8
from libpebble2.services.appmessage import AppMessageService
from pypkjs.javascript.pebble import Pebble
root=Path.cwd()
original={"TYPE":5,"SESSION":4294967295,"VERSION":2147483649,
          "CRC":0xcbf43926,"STAMP":2147483648,"REQUEST":4294967294,
          "DATA":[255,128,0,1]}
production_crc=zlib.crc32((root/"resources/timetable.bin").read_bytes())&0xffffffff
node="var p=require('./src/pkjs/protocol');process.stdout.write(JSON.stringify(p.wire(JSON.parse(process.argv[1]))));"
wire=json.loads(subprocess.check_output(["node","-e",node,json.dumps(original)],text=True,timeout=10))
class NoConnection:
    def register_endpoint(self,*args): return None
    def send_packet(self,packet):
        packet.serialise() # This executes the actual SDK's signed Int32 encoder.
        self.packet=packet
connection=NoConnection()
service=AppMessageService(connection)
fake=SimpleNamespace(_check_ready=lambda:None,app_keys={"TYPE":0,"SESSION":1,"VERSION":3,"CRC":5,"DATA":6,"REQUEST":8,"STAMP":9},uuid=UUID(int=1),
                     _appmessage=service,pending_acks={})
with v8.JSContext() as context:
    Pebble.sendAppMessage(fake,context.eval('('+json.dumps(wire)+')'))
    fields={tuple_.key:tuple_ for tuple_ in connection.packet.data.dictionary}
    keys={"TYPE":0,"SESSION":1,"VERSION":3,"CRC":5,"DATA":6,"REQUEST":8,"STAMP":9}
    # Production uses named appKeys; the real SDK maps them to numeric tuples.
    for key,value in original.items():
        data=fields[keys[key]].data
        assert (list(data) if key=="DATA" else struct.unpack('<I',data)[0])==value,(key,data,value)
    # Exercise the actual incoming SDK conversion and production decoder.
    context.eval('function Event(t){this.type=t;}')
    captured=[]
    incoming=SimpleNamespace(uuid=fake.uuid,app_keys=fake.app_keys,
                             runtime=SimpleNamespace(context=context),
                             triggerEvent=lambda name,event:captured.append(event))
    Pebble._handle_message(incoming,1,fake.uuid,{1:4294967295,5:production_crc,9:2147483648,6:bytearray([255,128,0])})
    context.locals.incoming=captured[0].payload
    assert context.eval('incoming.SESSION')==-1 # Reproduces the installed host's signed conversion.
    context.eval('var module={exports:{}};'+(root/'src/pkjs/protocol.js').read_text())
    assert context.eval("module.exports.get(incoming,'SESSION')")==4294967295
    assert context.eval("module.exports.get(incoming,'CRC')")==production_crc
    assert context.eval("module.exports.get(incoming,'STAMP')")==2147483648
    assert context.eval("module.exports.get(incoming,'DATA')[0]")==255
print('PASS actual installed SDK Int32 output preserves uint32 bits; incoming V8 signed words normalize')
'''
        result = subprocess.run([str(PYTHON), "-c", script], cwd=ROOT, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("PASS actual installed SDK", result.stdout)

    @unittest.skipUnless(PYTHON.is_file(), "Installed pebble-tool Python is unavailable")
    def test_bridge_reader_death_is_reported_without_transport(self):
        script = r'''
import importlib.util, threading
from types import SimpleNamespace
spec=importlib.util.spec_from_file_location('bridge','tools/emu_update_bridge.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
events=[];bridge.emit=events.append
stopping,ended=threading.Event(),threading.Event()
bridge.reader_loop(SimpleNamespace(run_sync=lambda:None),stopping,ended)
assert ended.is_set() and events[0]['fatal'] and events[0]['source']=='reader'
events.clear();ended.clear()
def fail(): raise RuntimeError('offline reader failure')
bridge.reader_loop(SimpleNamespace(run_sync=fail),stopping,ended)
assert ended.is_set() and events[0]['message']=='RuntimeError: offline reader failure'
events.clear();stopping.set()
bridge.reader_loop(SimpleNamespace(run_sync=lambda:None),stopping,ended)
assert not events # Normal close is not reported as a failure.
print('PASS reader return, reader exception and intentional close')
'''
        result = subprocess.run([str(PYTHON), "-c", script], cwd=ROOT, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
