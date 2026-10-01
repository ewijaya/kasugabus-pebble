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
"""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import tempfile
import time
import uuid

import png
from libpebble2.communication import PebbleConnection
from libpebble2.communication.transports.websocket import WebsocketTransport
from libpebble2.communication.transports.qemu.protocol import QemuBluetoothConnection, QemuButton, QemuTimeFormat
from libpebble2.protocol.apps import AppRunState, AppRunStateStart, AppRunStateStop
from libpebble2.protocol.appmessage import AppMessage, AppMessageACK
from libpebble2.protocol.system import TimeMessage, SetUTC
from libpebble2.protocol.screenshots import ScreenshotRequest, ScreenshotResponse
from libpebble2.services.appmessage import AppMessageService, ByteArray, Int32, Uint32
from libpebble2.services.screenshot import Screenshot
from pebble_tool.commands.emucontrol import send_data_to_qemu
from pebble_tool.commands.screenshot import ScreenshotCommand
from pebble_tool.sdk.emulator import get_all_emulator_info

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
            candidates.append(info)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-version")
    args = parser.parse_args()
    app_uuid = uuid.UUID(json.loads((ROOT / "package.json").read_text())["pebble"]["uuid"])
    emulator = existing_emulator(args.sdk_version)
    connection = PebbleConnection(WebsocketTransport(f"ws://127.0.0.1:{emulator['pypkjs']['port']}/"))
    connection.qemu_monitor_port = emulator["qemu"].get("monitor")
    connection.connect()
    messages = AppMessageService(RelayMessageConnection(connection))

    def received(transaction, target, data):
        if target == app_uuid:
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
    emit({"event": "ready", "uuid": str(app_uuid)})
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
    except Exception as error:
        emit({"event": "error", "errorType": type(error).__name__,
              "message": "bridge: " + error_text(error)})
        sys.exit(1)
