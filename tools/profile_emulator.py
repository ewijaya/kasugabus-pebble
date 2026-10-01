#!/usr/bin/env python3
"""Measure an installed Emery app using host monotonic time and real UI logs.

Run with the installed pebble-tool Python. No build, PBW installation, date,
preference, or timetable change occurs. Repeated app starts end at Home.
Host timings include protocol and firmware overhead; SDK wall-clock time_ms
logs are retained separately and are not used as a monotonic stopwatch.
"""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import threading
import time
import uuid

from libpebble2.communication import PebbleConnection
from libpebble2.communication.transports.websocket import WebsocketTransport
from libpebble2.communication.transports.qemu.protocol import QemuButton
from libpebble2.protocol.apps import AppRunState, AppRunStateStart, AppRunStateStop
from libpebble2.protocol.logs import AppLogMessage, AppLogShippingControl
from pebble_tool.commands.emucontrol import send_data_to_qemu
from emu_update_bridge import existing_port

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.cycles <= 10:
        parser.error("Use 1..10 cycles")
    app_uuid = uuid.UUID(json.loads((ROOT / "package.json").read_text())["pebble"]["uuid"])
    connection = PebbleConnection(WebsocketTransport(f"ws://127.0.0.1:{existing_port()}/"))
    connection.connect()
    events = queue.Queue()

    def record(packet):
        if getattr(packet, "uuid", getattr(getattr(packet, "data", None), "uuid", None)) == app_uuid:
            events.put((time.perf_counter(), packet))

    connection.register_endpoint(AppRunState, record)
    connection.register_endpoint(AppLogMessage, record)
    threading.Thread(target=connection.run_sync, daemon=True).start()
    connection.send_packet(AppLogShippingControl(enable=True))

    def wait(predicate, seconds=15, observed=None):
        end = time.perf_counter() + seconds
        while True:
            received, packet = events.get(timeout=max(.01, end-time.perf_counter()))
            if observed is not None:
                observed.append((received, packet))
            if predicate(packet):
                return received, packet
            if time.perf_counter() >= end:
                raise TimeoutError("Native profiler event missing")

    def drain():
        while not events.empty():
            events.get_nowait()

    def rendered(screen):
        return lambda p: isinstance(p, AppLogMessage) and p.message.startswith(f"UI screen{screen} ")

    launches, initialization, interactions = [], [], []
    buttons = [("select", QemuButton.Button.Select, 1),
               ("select", QemuButton.Button.Select, 2),
               ("back", QemuButton.Button.Back, 1),
               ("back", QemuButton.Button.Back, 0)]
    try:
        for _ in range(args.cycles):
            drain()
            connection.send_packet(AppRunState(data=AppRunStateStop(uuid=app_uuid)))
            wait(lambda p: isinstance(p, AppRunState) and isinstance(p.data, AppRunStateStop))
            drain()
            started = time.perf_counter()
            connection.send_packet(AppRunState(data=AppRunStateStart(uuid=app_uuid)))
            observed = []
            received, _ = wait(rendered(0), observed=observed)
            launches.append(round((received-started)*1000, 2))
            entered = [at for at, packet in observed if isinstance(packet, AppLogMessage) and packet.message == "INIT entered"]
            if len(entered) != 1:
                raise RuntimeError("Expected exactly one native initialization marker")
            initialization.append(round((received-entered[0])*1000, 2))
            # Measure first paint above, then allow the firmware's app-entry
            # input handling and phone handshake to settle before each discrete
            # interaction. This delay is outside the press-to-render interval.
            time.sleep(.5)
            for name, button, screen in buttons:
                drain()
                started = time.perf_counter()
                send_data_to_qemu(connection.transport, QemuButton(state=button))
                time.sleep(.06)
                send_data_to_qemu(connection.transport, QemuButton(state=0))
                received, _ = wait(rendered(screen))
                interactions.append({"button": name, "screen": screen,
                                     "press_to_render_ms": round((received-started)*1000, 2)})
                time.sleep(.5)
    finally:
        connection.transport.ws.close()
    bundle = ROOT / "build/kasugabus-pebble.pbw"
    print(json.dumps({"environment": "Emery emulator", "clock": "host time.perf_counter",
                      "pbw_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
                      "artifact_binding": "Read beside exact-PBW capture receipt; this tool never installs",
                      "start_command_to_first_home_render_ms": launches,
                      "app_initialization_to_first_home_render_ms": initialization,
                      "interactions": interactions,
                      "all_launches_under_1000ms": max(launches) < 1000,
                      "all_buttons_under_200ms": max(x["press_to_render_ms"] for x in interactions) < 200}, indent=2))


if __name__ == "__main__":
    main()
