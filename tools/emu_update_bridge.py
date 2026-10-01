#!/usr/bin/env python3
"""JSON-lines AppMessage bridge to an existing local Emery emulator.

Use the installed pebble-tool Python. Does not install or launch an emulator.
Commands: send, stop, start, time, timeFormat, button, bluetooth, screenshot, close.
Time uses epoch UTC seconds and utcOffsetMinutes (default 540). Button uses
name, durationMs (default 60), repeat (default 1), intervalMs (default 200).
Screenshot uses path, with rawRGB:true to retain the original RGB values.
Default screenshots read the monitor's 200x228 display as rendered (including
backlight dimming); rawRGB requests use the watch screenshot protocol.
Only the project's already-installed UUID is addressed. Never prints account
configuration, process arguments or emulator OAuth information.
--observe-production requires --expected-pbw and adds passive envelope/log
events. It never replaces or evaluates the installed PBW's JavaScript.
--fixture-relay is an explicit native-test mode: temporarily swaps only the
SDK relay for a relay without JavaScript, then probes/restores the normal relay.
"""
import argparse
import ctypes
import errno
import hashlib
import json
import os
import queue
from pathlib import Path
import sys
if "--fixture-relay-child" in sys.argv:
    # The installed SDK patches sockets before its runner/network imports.
    import pypkjs.runner.websocket
import signal
import socket
import subprocess
import struct
import threading
import tempfile
import time
import uuid

import png
from libpebble2.communication import PebbleConnection
from libpebble2.communication.transports.websocket import WebsocketTransport
from libpebble2.communication.transports.qemu import QemuTransport
from libpebble2.communication.transports.qemu.protocol import QemuBluetoothConnection, QemuButton, QemuTimeFormat
from libpebble2.protocol.apps import AppRunState, AppRunStateStart, AppRunStateStop
from libpebble2.protocol.appmessage import AppMessage, AppMessageACK
from libpebble2.protocol.base import PebblePacket
from libpebble2.protocol.logs import AppLogMessage, AppLogShippingControl
from libpebble2.communication.transports.websocket import MessageTargetPhone
from libpebble2.communication.transports.websocket.protocol import WebSocketRelayToWatch, WebSocketPhoneAppLog
from libpebble2.protocol.system import TimeMessage, SetUTC
from libpebble2.protocol.screenshots import ScreenshotRequest, ScreenshotResponse
from libpebble2.services.appmessage import AppMessageService, ByteArray, Int32, Uint32
from libpebble2.services.screenshot import Screenshot
from pebble_tool.commands.emucontrol import send_data_to_qemu
from pebble_tool.commands.screenshot import ScreenshotCommand
from pebble_tool.sdk.emulator import get_all_emulator_info
from pebble_tool.sdk.emulator import get_emulator_info_path
from pebble_tool.sdk import get_sdk_persist_dir
from pebble_tool.util import get_persist_dir

ROOT = Path(__file__).resolve().parents[1]
KEYS = {"TYPE": 0, "SESSION": 1, "SEQ": 2, "VERSION": 3, "LENGTH": 4,
        "CRC": 5, "DATA": 6, "STATUS": 7, "REQUEST": 8, "STAMP": 9,
        "ACCURACY": 10, "EFFECTIVE": 11, "PENDING": 12, "FLAGS": 13}
LOCK = threading.Lock()
BUTTONS = {"back": QemuButton.Button.Back, "up": QemuButton.Button.Up,
           "select": QemuButton.Button.Select, "down": QemuButton.Button.Down}


def emit(event):
    with LOCK:
        print(json.dumps(event, separators=(",", ":")), flush=True)


def existing_emulator(version=None):
    candidates = []
    for sdk, info in get_all_emulator_info().get("emery", {}).items():
        if version and sdk != version:
            continue
        try:
            os.kill(info["qemu"]["pid"], 0)
            os.kill(info["pypkjs"]["pid"], 0)
            candidates.append(dict(info, sdkVersion=sdk))
        except (OSError, KeyError):
            continue
    if len(candidates) != 1:
        raise RuntimeError("Need exactly one already-running Emery emulator")
    return candidates[0]


def existing_port(version=None):
    return existing_emulator(version)["pypkjs"]["port"]


def error_text(error):
    detail = str(error).strip()
    return type(error).__name__ + (": " + detail if detail else "")


def process_running(pid):
    # Actual installed macOS headers: PROC_PIDT_SHORTBSDINFO=13, status at12,
    # 64-byte proc_bsdshortinfo; SZOMB=5. No process arguments are exposed.
    if sys.platform!="darwin":
        raise RuntimeError("Scoped fixture relay requires the inspected macOS process API")
    library=ctypes.CDLL("/usr/lib/libproc.dylib",use_errno=True)
    function=library.proc_pidinfo
    function.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_uint64,ctypes.c_void_p,ctypes.c_int]
    function.restype=ctypes.c_int
    buffer=ctypes.create_string_buffer(64)
    size=function(pid,13,0,buffer,64)
    if size==0:
        if ctypes.get_errno() in (0,errno.ESRCH):return False
        raise RuntimeError("Kernel process status unavailable; relay ownership cannot be proved")
    if size!=64 or struct.unpack_from("=I",buffer.raw,0)[0]!=pid:
        raise RuntimeError("Unexpected kernel process identity shape")
    return struct.unpack_from("=I",buffer.raw,12)[0]!=5


def process_arguments(pid):
    # KERN_PROCARGS2 is argc, executable NUL/padding, then exactly argc NUL-
    # terminated arguments. Deliberately stop before environment variables.
    if not process_running(pid):raise ProcessLookupError("SDK relay is no longer running")
    library=ctypes.CDLL(None,use_errno=True)
    function=library.sysctl
    function.argtypes=[ctypes.POINTER(ctypes.c_int),ctypes.c_uint,ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.c_void_p,ctypes.c_size_t]
    function.restype=ctypes.c_int
    names=(ctypes.c_int*3)(1,49,pid)
    size=ctypes.c_size_t(1048576);buffer=ctypes.create_string_buffer(size.value)
    if function(names,3,buffer,ctypes.byref(size),None,0)!=0:
        if ctypes.get_errno()==errno.ESRCH:raise ProcessLookupError("SDK relay is no longer running")
        raise RuntimeError("Kernel SDK relay argument read failed; arguments withheld")
    raw=buffer.raw[:size.value]
    count=struct.unpack_from("=i",raw,0)[0]
    if not 1<=count<=4096:raise RuntimeError("Invalid kernel SDK argument count")
    position=raw.find(b"\0",4)+1
    if position<5:raise RuntimeError("Invalid kernel executable record")
    while position<len(raw) and raw[position]==0:position+=1
    arguments=[]
    for _ in range(count):
        end=raw.find(b"\0",position)
        if end<0:raise RuntimeError("Truncated kernel SDK argument record")
        arguments.append(os.fsdecode(raw[position:end]));position=end+1
    return arguments


class FixtureRelay:
    """Opt-in native fixture transport; argv stays in memory, never evidence."""
    def __init__(self, emulator, cached, expected):
        self.emulator, self.cached, self.expected = emulator, cached, expected
        self.original_argv = None
        self.fixture = None
        self.stopped_original = False
        self.old_term = None
        self.restored = False
        self.expected_state = None

    def verify_cache(self):
        if not self.cached.is_file() or hashlib.sha256(self.cached.read_bytes()).hexdigest() != self.expected:
            raise RuntimeError("Fixture cached PBW changed; exact artifact proof failed")

    def metadata_pid(self, old, new):
        path = Path(get_emulator_info_path())
        value = json.loads(path.read_text())
        info = value.get("emery", {}).get(self.emulator["sdkVersion"], {})
        if info.get("qemu") != self.emulator["qemu"] or info.get("pypkjs", {}).get("pid") != old:
            raise RuntimeError("Fixture emulator ownership changed; metadata update refused")
        info["pypkjs"]["pid"] = new
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as temporary:
            target = Path(temporary.name)
            json.dump(value, temporary);temporary.flush();os.fsync(temporary.fileno())
        try:
            os.replace(target, path)
            descriptor = os.open(str(path.parent), os.O_RDONLY)
            try: os.fsync(descriptor)
            finally: os.close(descriptor)
        finally:
            target.unlink(missing_ok=True)

    @staticmethod
    def stop_process(pid):
        try:
            os.kill(pid,signal.SIGTERM)
        except ProcessLookupError:return
        end=time.monotonic()+5
        while time.monotonic()<end:
            try: os.waitpid(pid,os.WNOHANG)
            except ChildProcessError:pass
            if not process_running(pid):return
            time.sleep(.05)
        raise TimeoutError("Scoped SDK relay termination timed out")

    @staticmethod
    def probe(port, process=None):
        """SDK WebSocket PhoneInfo, without launch, clock or account requests."""
        from websocket import create_connection
        end = time.monotonic()+6
        while time.monotonic()<end:
            if process is not None and process.poll() is not None:
                raise RuntimeError("Fixture relay child exited before its bounded probe")
            connection = None
            try:
                connection = create_connection("ws://127.0.0.1:%d/" % port, timeout=1)
                connection.send_binary(bytes([6]))
                while time.monotonic()<end:
                    message = connection.recv()
                    if isinstance(message, bytes) and message == b"\x06pypkjs,0.0.0,qemu":
                        return
            except Exception:
                pass
            finally:
                if connection is not None: connection.close()
            time.sleep(.1)
        raise TimeoutError("Fixture relay SDK PhoneInfo probe timed out")

    @staticmethod
    def native_state(port,seconds=8):
        """One native HELLO/STATE roundtrip; no logs, clock or app launch."""
        from websocket import create_connection
        deadline=time.monotonic()+seconds
        connection=PebbleConnection(WebsocketTransport("ws://127.0.0.1:%d/"%port))
        connection.transport.ws=create_connection(connection.transport.url,timeout=min(2,seconds))
        connection.transport.ws.settimeout(None)
        app_uuid=uuid.UUID(json.loads((ROOT/"package.json").read_text())["pebble"]["uuid"])
        responses=queue.Queue(maxsize=1)
        service=AppMessageService(RelayMessageConnection(connection))
        def received(_transaction,target,data):
            if target!=app_uuid or data.get(0)!=2:return
            preferences=data.get(6)
            if not isinstance(preferences,(bytes,bytearray)) or len(preferences)!=80 or preferences[0] not in (1,2) or type(data.get(3)) is not int or not 1<=data[3]<=4294967295 or type(data.get(12,0)) is not int or not 0<=data.get(12,0)<=4294967295:
                value=RuntimeError("Native STATE identity/shape is invalid")
            else:value={"preferences":bytes(preferences),"version":data[3],"pending":data.get(12,0)}
            try:responses.put_nowait(value)
            except queue.Full:pass
        service.register_handler("appmessage",received)
        reader=threading.Thread(target=connection.run_sync,daemon=True)
        reader.start()
        try:
            service.send_message(app_uuid,{0:Uint32(1)})
            try:
                result=responses.get(timeout=max(.01,deadline-time.monotonic()))
                if isinstance(result,Exception):raise result
                return result
            except queue.Empty:raise TimeoutError("Native KasugaBus STATE health proof timed out") from None
        finally:
            service.shutdown();connection.transport.ws.close(timeout=1);reader.join(timeout=1)

    def verify_normal_state(self,port):
        deadline=time.monotonic()+30
        for attempt in range(1,4):
            remaining=deadline-time.monotonic()-2
            if remaining<=0:break
            try:actual=self.native_state(port,seconds=min(8,remaining))
            except TimeoutError:
                if attempt==3:break
                continue
            # Identity changes are failures, never transient retry candidates.
            if actual!=self.expected_state:
                raise RuntimeError("Normal relay native preferences/dataset identity differs")
            return actual,attempt
        raise TimeoutError("Normal native STATE health proof failed after bounded retries")

    @staticmethod
    def disconnect_bluetooth(port):
        from websocket import create_connection
        transport=WebsocketTransport("ws://127.0.0.1:%d/"%port)
        transport.ws=create_connection(transport.url,timeout=2)
        try:send_data_to_qemu(transport,QemuBluetoothConnection(connected=False))
        finally:transport.ws.close()

    @staticmethod
    def prime_bluetooth(qemu_port):
        # SDK PebbleManager.connect fetches WatchVersion before setting true.
        # Re-enable the recorded existing QEMU link before successor startup;
        # otherwise an explicit false boundary can block that first request.
        transport=QemuTransport(socket=socket.create_connection(("127.0.0.1",qemu_port),timeout=2))
        try:send_data_to_qemu(transport,QemuBluetoothConnection(connected=True))
        finally:transport.socket.close()

    def __enter__(self):
        self.verify_cache()
        info = self.emulator
        self.expected_state=self.native_state(info["pypkjs"]["port"])
        # Kernel-backed argument array, never ps/shlex and never printed.
        arguments = process_arguments(info["pypkjs"]["pid"])
        qemu = "localhost:%d" % info["qemu"]["port"]
        if "-m" not in arguments or arguments[arguments.index("-m")+1] != "pypkjs" or "--qemu" not in arguments or arguments[arguments.index("--qemu")+1] not in (qemu, "127.0.0.1:%d" % info["qemu"]["port"]):
            raise RuntimeError("Fixture refuses a process that is not the recorded SDK relay")
        if "--token" in arguments:
            raise RuntimeError("Fixture relay does not support a custom authenticated WebSocket")
        self.original_argv = arguments
        self.old_term = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        try:
            self.disconnect_bluetooth(info["pypkjs"]["port"])
            self.stopped_original = True
            self.stop_process(info["pypkjs"]["pid"])
            self.prime_bluetooth(info["qemu"]["port"])
            command = [sys.executable, str(Path(__file__).resolve()), "--fixture-relay-child", "--sdk-version", info["sdkVersion"],
                       "--fixture-qemu-port", str(info["qemu"]["port"]), "--fixture-ws-port", str(info["pypkjs"]["port"])]
            self.fixture = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            self.probe(info["pypkjs"]["port"], self.fixture)
            self.metadata_pid(info["pypkjs"]["pid"], self.fixture.pid)
            self.verify_cache()
            return self
        except BaseException:
            self.restore()
            raise

    def restore(self):
        if self.restored:return
        stage="metadata ownership"
        try:
            state=get_all_emulator_info().get("emery",{}).get(self.emulator["sdkVersion"],{})
            previous=state.get("pypkjs",{}).get("pid")
            if state.get("qemu")!=self.emulator["qemu"] or previous not in (self.emulator["pypkjs"]["pid"],self.fixture.pid if self.fixture else None):
                raise RuntimeError("Normal relay restoration ownership changed")
            stage="fixture termination"
            if self.fixture is not None:
                try:self.disconnect_bluetooth(self.emulator["pypkjs"]["port"])
                except Exception:
                    # A child whose frontend failed must still be stopped and
                    # replaced; the normal native STATE proof remains required.
                    pass
                self.stop_process(self.fixture.pid)
            if self.stopped_original:
                # Entry can have been interrupted while terminating the old
                # relay. Do not start a duplicate beside a surviving process.
                try:
                    previous_pid=self.emulator["pypkjs"]["pid"]
                    if process_arguments(previous_pid)!=self.original_argv:
                        raise RuntimeError("Original SDK relay PID ownership changed")
                    self.stop_process(previous_pid)
                except ProcessLookupError:
                    pass
                stage="native Bluetooth reconnect"
                self.prime_bluetooth(self.emulator["qemu"]["port"])
                stage="normal relay launch"
                try:
                    # macOS kernel argv[0] is the Python application launcher;
                    # executing it directly loses the SDK virtualenv packages.
                    # The inspected SDK spawn uses sys.executable. Preserve all
                    # original options, and verify kernel argv equality below.
                    command=[sys.executable,*self.original_argv[1:]]
                    normal = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                except Exception:
                    raise RuntimeError("Normal SDK relay restart failed; arguments withheld") from None
                stage="metadata transition"
                self.metadata_pid(previous, normal.pid)
                stage="normal relay PhoneInfo"
                self.probe(self.emulator["pypkjs"]["port"], normal)
                stage="normal native STATE"
                actual,attempts=self.verify_normal_state(self.emulator["pypkjs"]["port"])
                stage="normal relay kernel identity"
                if process_arguments(normal.pid) != self.original_argv:
                    raise RuntimeError("Normal SDK relay identity probe differs")
                stage="cached artifact identity"
                self.verify_cache()
                emit({"event": "fixtureRestored", "normalSdkRelayRestored": True, "nativeStateVerified":True,
                      "preferencesSha256":hashlib.sha256(actual["preferences"]).hexdigest(),
                      "nativeStateAttempts":attempts,"nativeStateTransientRetries":attempts-1,
                      "activeVersion":actual["version"],"pendingVersion":actual["pending"],"cachedPbwSha256": self.expected})
            self.restored=True
        except BaseException as error:
            emit({"event": "error", "fatal": True, "source": "fixture-restoration", "message": "Normal SDK relay restoration failed at "+stage+" ("+type(error).__name__+"); inspect emulator before further verification"})
            raise
        finally:
            if self.old_term is not None:signal.signal(signal.SIGTERM,self.old_term)

    def __exit__(self, *_):
        self.restore()


def run_fixture_relay_child(version, qemu_port, ws_port):
    from pypkjs.runner.websocket import WebsocketRunner
    class RelayOnlyRunner(WebsocketRunner):
        def start_js(self, pbw):
            # Retain SDK relay ACK ownership without evaluating any PBW JS.
            self.stop_js()
    runner = RelayOnlyRunner("127.0.0.1:%d" % qemu_port, [], ws_port,
                            persist_dir=get_sdk_persist_dir("emery",version))
    runner.run()


def screenshot_rows(connection, raw):
    """Capture native pixels; never scale or normalize panel brightness."""
    monitor = getattr(connection, "qemu_monitor_port", None)
    fallback = None
    if monitor and not raw:
        try:
            with tempfile.TemporaryDirectory(prefix="kasugabus-screen-") as directory:
                image = ScreenshotCommand._grab_qemu_monitor_image_fast(monitor, directory, 0)
                if image.size != (200, 228):
                    raise ValueError(f"Monitor framebuffer must be 200x228, received {image.size}")
                data = image.convert("RGB").tobytes()
            return [bytearray(data[i:i+600]) for i in range(0, len(data), 600)], {
                "source": "qemu-monitor", "colourCorrection": "emulator-rendered",
                "backlight": "as-captured"}
        except ValueError:
            raise # A different framebuffer must not become a resized screenshot.
        except Exception as error:
            fallback = error_text(error)
    # The SDK grab_image leaks its endpoint queue if queue.get times out.
    # Use that same decoder with a queue closed on both success and failure.
    queue = connection.get_endpoint_queue(ScreenshotResponse)
    try:
        connection.send_packet(ScreenshotRequest())
        rows = Screenshot(connection)._read_screenshot(queue)
    finally:
        queue.close()
    if not raw:
        rows = ScreenshotCommand._correct_colours(None, rows)
    metadata = {"source": "watch-protocol",
                "colourCorrection": "raw-RGB8" if raw else "sdk-palette-correction",
                "backlight": "not-in-framebuffer"}
    if fallback:
        metadata["monitorError"] = fallback
    return rows, metadata


def command_integer(command, name, default, low, high):
    value = command.get(name, default)
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")
    return value


def control(connection, command):
    """Use the existing connection, without constructing any CLI command."""
    op = command["op"]
    event = {"event": "command", "op": op}
    if op == "time":
        epoch = command_integer(command, "epoch", None, 0, 0xffffffff)
        offset = command_integer(command, "utcOffsetMinutes", 540, -1440, 1440)
        sign = "+" if offset >= 0 else "-"
        hours, minutes = divmod(abs(offset), 60)
        zone = "UTC" if offset == 0 else f"UTC{sign}{hours:02d}:{minutes:02d}"
        connection.send_packet(TimeMessage(message=SetUTC(
            unix_time=epoch, utc_offset=offset, tz_name=zone)))
        event.update(epoch=epoch, utcOffsetMinutes=offset)
    elif op == "button":
        name = command.get("name")
        if name not in BUTTONS:
            raise ValueError("name must be back, up, select or down")
        duration = command_integer(command, "durationMs", 60, 1, 10000)
        repeat = command_integer(command, "repeat", 1, 1, 100)
        interval = command_integer(command, "intervalMs", 200, 0, 10000)
        if duration * repeat + interval * (repeat - 1) > 30000:
            raise ValueError("Button sequence must finish within 30 seconds")
        for index in range(repeat):
            if index:
                time.sleep(interval / 1000)
            try:
                send_data_to_qemu(connection.transport, QemuButton(state=BUTTONS[name]))
                time.sleep(duration / 1000)
            finally:
                send_data_to_qemu(connection.transport, QemuButton(state=0))
        event.update(name=name, durationMs=duration, repeat=repeat, intervalMs=interval)
    elif op == "bluetooth":
        connected = command.get("connected")
        if type(connected) is not bool:
            raise ValueError("connected must be a boolean")
        send_data_to_qemu(connection.transport, QemuBluetoothConnection(connected=connected))
        event["connected"] = connected
    elif op == "timeFormat":
        is_24_hour = command.get("is24Hour")
        if type(is_24_hour) is not bool:
            raise ValueError("is24Hour must be a boolean")
        send_data_to_qemu(connection.transport, QemuTimeFormat(is_24_hour=is_24_hour))
        event["is24Hour"] = is_24_hour
    elif op == "screenshot":
        path = command.get("path")
        raw = command.get("rawRGB", False)
        if not isinstance(path, str) or not path:
            raise ValueError("path must be a nonempty PNG path")
        if type(raw) is not bool:
            raise ValueError("rawRGB must be a boolean")
        target = Path(path).expanduser().resolve()
        if target.suffix.lower() != ".png":
            raise ValueError("Screenshot path must end in .png")
        rows, metadata = screenshot_rows(connection, raw)
        if not rows or not rows[0] or len(rows[0]) % 3:
            raise ValueError("Screenshot returned no valid RGB image")
        height, width = len(rows), len(rows[0]) // 3
        if (width, height) != (200, 228):
            raise ValueError(f"Screenshot must be 200x228, received {width}x{height}")
        if any(len(row) != width * 3 for row in rows):
            raise ValueError("Screenshot returned inconsistent row widths")
        target.parent.mkdir(parents=True, exist_ok=True)
        png.from_array(rows, mode="RGB;8").save(str(target))
        event.update(path=str(target), width=width, height=height,
                     dimensions=[width, height], rawRGB=raw)
        event.update(metadata)
    else:
        raise ValueError("Unknown bridge control")
    return event


def reader_loop(connection, stopping, ended):
    """Surface the SDK reader's exceptions and silent disconnect return."""
    failure = None
    try:
        connection.run_sync()
    except Exception as error:
        failure = error_text(error)
    finally:
        ended.set()
        if not stopping.is_set():
            emit({"event": "error", "fatal": True, "source": "reader",
                  "message": failure or "Bridge transport reader stopped/disconnected"})


class RelayMessageConnection:
    """Observe a pypkjs relay without duplicating its watch-push ACKs.

    existing_port requires the live pypkjs process. Its Runner always installs
    one AppMessageService that owns ACKs, even without an active JS worker.
    Keep our SDK decoder/transaction tracking, forwarding all other packets.
    """
    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def send_packet(self, packet, *args, **kwargs):
        if isinstance(packet, AppMessage) and isinstance(packet.data, AppMessageACK):
            return
        return self.connection.send_packet(packet, *args, **kwargs)


class ProductionObserver:
    """Decode relay copies only. Never dispatch packets or acknowledge them."""
    def __init__(self, app_uuid, callback):
        self.app_uuid, self.callback, self.pending = app_uuid, callback, b""

    def receive(self, packet):
        data = self.pending + bytes(packet.payload)
        while len(data) >= 4:
            length = int.from_bytes(data[:2], "big") + 4
            if length > 4096:
                raise ValueError("Observed relay packet exceeds bound")
            if len(data) < length:
                break
            decoded, used = PebblePacket.parse_message(data[:length])
            if used != length:
                raise ValueError("Observed relay framing mismatch")
            data = data[length:]
            if not isinstance(decoded, AppMessage) or getattr(decoded.data, "uuid", None) != self.app_uuid:
                continue
            values = {}
            for item in decoded.data.dictionary:
                if item.type in (2, 3):
                    values[str(item.key)] = int.from_bytes(item.data, "little", signed=item.type == 3) & 0xffffffff
                elif item.type == 0 and item.key == 6:
                    values["6"] = list(item.data)
            # Exclude settings/location/personal state. CHUNK contains public
            # reviewed timetable bytes, used only for a bounded digest proof.
            if values.get("0") in (1, 4, 5, 6, 7):
                if values.get("0") != 6:
                    values.pop("6", None)
                self.callback({"event": "phoneappmessage", "message": values})
        self.pending = data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-version")
    parser.add_argument("--observe-production", action="store_true", help="Passively observe shipped worker envelopes and native logs")
    parser.add_argument("--expected-pbw", type=Path, help="Require the relay's cached PBW to match these exact bytes")
    parser.add_argument("--fixture-relay", action="store_true", help="Explicitly test native watch behavior with a simulated phone; restores the normal SDK relay")
    parser.add_argument("--fixture-relay-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--fixture-qemu-port", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--fixture-ws-port", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.fixture_relay_child:
        if not args.sdk_version or not all(type(p) is int and 1<=p<=65535 for p in (args.fixture_qemu_port,args.fixture_ws_port)):
            raise ValueError("Invalid fixture child relay arguments")
        return run_fixture_relay_child(args.sdk_version,args.fixture_qemu_port,args.fixture_ws_port)
    if args.fixture_relay and args.observe_production:
        raise ValueError("Native fixture and production-worker observation are distinct modes")
    app_uuid = uuid.UUID(json.loads((ROOT / "package.json").read_text())["pebble"]["uuid"])
    emulator = existing_emulator(args.sdk_version)
    proof = {}
    if args.observe_production or args.fixture_relay:
        if not args.expected_pbw:
            raise ValueError("Production observation requires --expected-pbw")
        cached = Path(get_persist_dir()) / emulator["sdkVersion"] / "emery" / "app_cache" / (str(app_uuid) + ".pbw")
        expected = hashlib.sha256(args.expected_pbw.read_bytes()).hexdigest()
        if not cached.is_file() or hashlib.sha256(cached.read_bytes()).hexdigest() != expected:
            raise ValueError("Emulator cached PBW differs from the exact expected artifact; do not substitute JavaScript")
        proof = {"cachedPbwSha256": expected, "sdkVersion": emulator["sdkVersion"], "observer": "native-fixture-relay" if args.fixture_relay else "installed-pypkjs-worker"}
    if args.fixture_relay:
        with FixtureRelay(emulator,cached,expected) as fixture:
            return run_bridge(app_uuid,emulator,proof,True,fixture)
    return run_bridge(app_uuid,emulator,proof,args.observe_production)


def run_bridge(app_uuid,emulator,proof,observe,fixture=None):
    connection = PebbleConnection(WebsocketTransport(f"ws://127.0.0.1:{emulator['pypkjs']['port']}/"))
    connection.qemu_monitor_port = emulator["qemu"].get("monitor")
    connection.connect()
    if observe:
        observer = ProductionObserver(app_uuid, emit)
        def outbound(packet):
            try:
                observer.receive(packet)
            except Exception as error:
                emit({"event": "error", "fatal": True, "source": "production-observer", "message": error_text(error)})
        connection.register_transport_endpoint(MessageTargetPhone, WebSocketRelayToWatch, outbound)
        connection.register_transport_endpoint(MessageTargetPhone, WebSocketPhoneAppLog, lambda packet: emit({"event": "phonelog", "message": str(packet.payload)[:4000]}))
        connection.register_endpoint(AppLogMessage, lambda packet: emit({"event": "watchlog", "filename": packet.filename, "message": packet.message}))
        connection.send_packet(AppLogShippingControl(enable=True))
    messages = AppMessageService(RelayMessageConnection(connection))

    def received(transaction, target, data):
        if target == app_uuid:
            if fixture is not None and data.get(0)==2 and isinstance(data.get(6),(bytes,bytearray)) and len(data[6])==80:
                fixture.expected_state={"preferences":bytes(data[6]),"version":data[3],"pending":data.get(12,0)}
            emit({"event": "appmessage", "message": {str(k): list(v) if isinstance(v, (bytes, bytearray)) else v for k, v in data.items()}})

    messages.register_handler("appmessage", received)
    # The relay also broadcasts transactions sent by its own phone worker.
    # Surface callbacks only for transactions this AppMessageService owns.
    messages.register_handler("ack", lambda transaction, target: emit({"event": "transportAck", "transaction": transaction}) if target == app_uuid else None)
    messages.register_handler("nack", lambda transaction, target: emit({"event": "transportNack", "transaction": transaction}) if target == app_uuid else None)
    connection.register_endpoint(AppRunState, lambda packet: emit({"event": "runState", "kind": type(packet.data).__name__, "uuid": str(getattr(packet.data, "uuid", ""))}))
    stopping, ended = threading.Event(), threading.Event()
    reader = threading.Thread(target=reader_loop, args=(connection, stopping, ended), daemon=True)
    reader.start()
    emit(dict(event="ready", uuid=str(app_uuid), **proof))
    try:
        for line in sys.stdin:
            op = None
            try:
                command = json.loads(line)
                op = command.get("op")
                if op != "close" and ended.is_set():
                    raise RuntimeError("Bridge transport reader is no longer running")
                if op == "send":
                    dictionary = {}
                    for key, value in command["message"].items():
                        number = KEYS[key] if key in KEYS else int(key)
                        if isinstance(value, list):
                            dictionary[number] = ByteArray(bytes(value))
                        elif type(value) is int and 0 <= value <= 0xffffffff:
                            dictionary[number] = Uint32(value)
                        elif type(value) is int and -2147483648 <= value < 0:
                            dictionary[number] = Int32(value)
                        else:
                            raise ValueError("Unsupported AppMessage value")
                    transaction = messages.send_message(app_uuid, dictionary)
                    emit({"event": "sent", "transaction": transaction})
                elif op == "stop":
                    connection.send_packet(AppRunState(data=AppRunStateStop(uuid=app_uuid)))
                    emit({"event": "command", "op": op})
                elif op == "start":
                    connection.send_packet(AppRunState(data=AppRunStateStart(uuid=app_uuid)))
                    emit({"event": "command", "op": op})
                elif op in ("time", "timeFormat", "button", "bluetooth", "screenshot"):
                    emit(control(connection, command))
                elif op == "close":
                    break
                else:
                    raise ValueError("Unknown bridge operation")
            except Exception as error:
                emit({"event": "error", "op": op, "errorType": type(error).__name__,
                      "message": f"{op or 'bridge'}: {error_text(error)}"})
    finally:
        stopping.set()
        messages.shutdown()
        connection.transport.ws.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        emit({"event":"error","message":"Bridge interrupted; fixture restoration was attempted before exit"})
        sys.exit(130)
    except Exception as error:
        emit({"event": "error", "errorType": type(error).__name__,
              "message": "bridge: " + error_text(error)})
        sys.exit(1)
