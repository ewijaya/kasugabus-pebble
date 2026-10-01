#!/usr/bin/env python3
"""Exercise the already-installed Emery app; never builds or installs a PBW.

Uses temporary test preferences and emulator dates, restores preferences and
the actual current time on exit. Screenshots are actual 200x228 watch renders. Requires the
installed pebble-tool Python for emu_update_bridge.py; no physical claims.
"""
import argparse
import copy
import datetime as dt
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import zlib

ROOT = Path(__file__).resolve().parents[1]


class Emulator:
    def __init__(self):
        python = os.environ.get("KASUGABUS_PEBBLE_PYTHON", str(Path.home() / ".local/share/uv/tools/pebble-tool/bin/python"))
        self.events = queue.Queue()
        self.proc = subprocess.Popen([python, "tools/emu_update_bridge.py"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        def read():
            for line in self.proc.stdout:
                try:
                    self.events.put(json.loads(line))
                except ValueError:
                    pass
        threading.Thread(target=read, daemon=True).start()
        self.wait(lambda e: e.get("event") == "ready")

    def wait(self, predicate, seconds=15):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            event = self.events.get(timeout=max(.01, end-time.monotonic()))
            if event.get("event") == "error":
                raise RuntimeError(event["message"])
            if predicate(event):
                return event
        raise TimeoutError("Emulator event missing")

    def drain(self):
        while not self.events.empty():
            self.events.get_nowait()

    def command(self, op, **kw):
        self.proc.stdin.write(json.dumps(dict(op=op, **kw)) + "\n")
        self.proc.stdin.flush()

    def state(self):
        self.drain()
        self.command("send", message={"TYPE": 1})
        return self.wait(lambda e: e.get("event") == "appmessage" and e["message"].get("0") == 2)["message"]

    def settings(self, data):
        self.drain()
        self.command("send", message={"TYPE": 11, "DATA": data})
        result = self.wait(lambda e: e.get("event") == "appmessage" and e["message"].get("0") == 2)["message"]
        assert result["6"] == data, "Native preferences were not accepted atomically"

    def restart(self, get_state=True):
        self.drain()
        self.command("stop")
        self.wait(lambda e: e.get("kind") == "AppRunStateStop")
        self.command("start")
        self.wait(lambda e: e.get("kind") == "AppRunStateStart")
        time.sleep(.4)
        return self.state() if get_state else None

    def action(self, op, **kw):
        self.drain()
        self.command(op, **kw)
        return self.wait(lambda e: e.get("event") == "command" and e.get("op") == op)

    def date(self, text, offset=540):
        self.action("time", epoch=int(dt.datetime.fromisoformat(text).timestamp()), utcOffsetMinutes=offset)
        time.sleep(1.2)

    def click(self, name, repeat=1, long=False):
        self.action("button", name=name, durationMs=800 if long else 60, repeat=repeat, intervalMs=200)
        time.sleep(.15)

    def screenshot(self, name):
        target = ROOT / "artifacts/screenshots" / (name + ".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Screenshot reads the framebuffer while the app may still be drawing.
        # Let the latest requested render complete rather than capture a tear.
        time.sleep(.4)
        result = self.action("screenshot", path=str(target))
        assert result["width"] == 200 and result["height"] == 228
        print("Captured", target.relative_to(ROOT), flush=True)

    def menu(self, index):
        self.click("select", long=True)
        if index:
            self.click("down", index)
        self.click("select")

    def close(self):
        self.command("close")
        self.proc.stdin.close()
        self.proc.wait(timeout=5)


def preferences(point=1, contrast=False):
    data = [0] * 80
    data[:6] = [1, 8 if contrast else 0, point, 0, 2, 4]
    for i, value in enumerate([1, 102, 6, 105]):
        data[8+2*i] = value
    data[32:36] = [1, 0, 5, 0]  # Controlled five-minute fixture, never an inferred walk.
    return data


def navigation(emu):
    data = preferences()
    emu.settings(data)
    assert emu.restart()["6"] == data
    emu.date("2026-10-01T10:32:01+09:00")
    emu.screenshot("emery_01_home")
    emu.click("select")
    emu.screenshot("emery_02_board")
    emu.click("select")
    emu.screenshot("emery_03_details")
    emu.click("select")
    emu.screenshot("emery_04_japanese")
    emu.click("select", long=True)
    emu.screenshot("emery_05_menu")
    emu.click("select")
    emu.click("select")
    emu.screenshot("emery_06_favourites")
    emu.click("back")
    emu.click("down", 2)
    emu.click("select")
    emu.screenshot("emery_07_all_stops")
    emu.click("down", 4)
    emu.click("select")
    emu.screenshot("emery_08_directions")
    emu.click("down", 3)
    emu.screenshot("emery_09_direction_long")
    emu.settings(preferences(102))
    emu.restart()
    emu.screenshot("emery_10_home_long")
    emu.settings(preferences(102, True))
    emu.restart()
    emu.screenshot("emery_11_monochrome")
    emu.menu(3)
    emu.screenshot("emery_12_settings")
    emu.settings(preferences())
    emu.restart()
    emu.menu(0)
    emu.click("down")
    emu.click("select")
    time.sleep(1)
    emu.screenshot("emery_13_nearby_disabled")
    emu.click("back")
    emu.click("back")
    emu.menu(1)
    emu.click("down")
    emu.click("select")
    emu.click("select")
    emu.click("select")
    emu.click("down", 5)
    emu.screenshot("emery_14_saved_origin")
    emu.restart()
    emu.date("2026-10-01T10:33:10+09:00")
    emu.screenshot("emery_15_due")
    emu.date("2026-10-01T10:34:00+09:00")
    emu.screenshot("emery_16_next_minute")
    emu.action("timeFormat", is24Hour=False)
    emu.date("2026-10-01T10:32:01+09:00", offset=0)
    emu.restart()
    emu.screenshot("emery_25_local_12h_jst_bus")
    emu.action("timeFormat", is24Hour=True)
    emu.date("2026-10-01T10:32:01+09:00")
    emu.restart()
    emu.menu(2)
    emu.screenshot("emery_17_data_status")
    emu.click("down", 4)
    emu.screenshot("emery_18_data_dates")
    print("PASS native preference confirmation/restart and screen navigation (screens require visual review)", flush=True)


def rollover(emu, current, future):
    emu.settings(preferences(102))
    emu.date("2026-10-01T10:30:00+09:00")
    before = emu.restart()
    assert before["3"] == current and before["12"] == future
    emu.action("bluetooth", connected=False)
    emu.date("2026-10-03T10:30:00+09:00")
    emu.restart(False)
    emu.screenshot("emery_19_offline_future_weekend")
    emu.menu(2)
    emu.screenshot("emery_20_future_status_offline")
    # Diagnostic STATE is requested after offline rendering; no feed transfer.
    after = emu.state()
    assert after["3"] == future and after["12"] == 0
    assert after["6"] == preferences(102)
    emu.settings(preferences())
    emu.date("2026-11-02T10:30:00+09:00")
    emu.restart(False)
    emu.screenshot("emery_21_source_review_due")
    emu.date("2026-12-28T10:30:00+09:00")
    emu.restart(False)
    emu.screenshot("emery_22_calendar_unconfirmed")
    emu.menu(3)
    emu.click("select")
    emu.click("down")
    emu.click("select")
    emu.screenshot("emery_23_unconfirmed_override")
    emu.date("2026-12-29T10:30:00+09:00")
    emu.screenshot("emery_24_override_expired")
    print("PASS native offline future activation/restart and preferences; expiry/staleness/override screenshots captured", flush=True)


def focus_removal(emu, current, future):
    # This deliberately incomplete timetable is an isolated regression fixture,
    # never written to data/, resources/ or a publishing directory. Follow it
    # with the complete real-data feed harness before using the emulator.
    from compile_timetable import compile_dataset
    baseline = json.loads((ROOT / "data/timetable.json").read_text())
    def transfer(doc):
        payload = compile_dataset(doc)
        session = 810000 + doc["release_version"]
        def exchange(message, seq, phase, accepted):
            emu.drain()
            emu.command("send", message=message)
            reply = emu.wait(lambda e: e.get("event") == "appmessage" and e["message"].get("0") == 8 and e["message"].get("1") == session and e["message"].get("2") == seq and e["message"].get("13") == phase)["message"]
            assert reply["7"] in accepted, reply
        request = emu.state()["8"]
        exchange({"TYPE":5,"SESSION":session,"REQUEST":request,"VERSION":doc["release_version"],"LENGTH":len(payload),"CRC":zlib.crc32(payload)&0xffffffff},0,5,{0})
        for seq, offset in enumerate(range(0,len(payload),192)):
            exchange({"TYPE":6,"SESSION":session,"SEQ":seq,"DATA":list(payload[offset:offset+192])},seq,6,{0})
        exchange({"TYPE":7,"SESSION":session},65535,7,{3,4})
    emu.settings(preferences())
    emu.date("2026-10-01T10:32:01+09:00")
    assert emu.restart()["3"] < current
    emu.click("select")
    emu.screenshot("emery_26_focus_before_fixture")
    upcoming = copy.deepcopy(baseline)
    upcoming.update(release_version=future,effective_from="2026-10-03")
    transfer(upcoming)
    changed = copy.deepcopy(baseline)
    changed["release_version"] = current
    changed["departures"] = [row for row in changed["departures"] if not(row["boarding_point_id"]==1 and row["service_id"]==1 and row["minute"]==633)]
    assert len(changed["departures"]) == len(baseline["departures"])-1
    transfer(changed)
    after=emu.state()
    assert after["3"]==current and after["12"]==future
    emu.screenshot("emery_27_focus_removed_fixture")
    emu.click("down")
    emu.screenshot("emery_28_focus_next_fixture")
    print("PASS native removed-trip fixture transfer; review explicit removed row and following B/C screenshots", flush=True)


def restore_during_begin(emu, version):
    """Explicitly restore this app's baseline during deferred validation.

    Run after the update/profile scenarios with several retained snapshots.
    A matching retry and stale chunk must stay rejected after confirmation.
    The native log distinguishes cancelling a pending job from a begun transfer.
    """
    from compile_timetable import compile_dataset
    emu.settings(preferences())
    emu.date("2026-10-01T10:32:01+09:00")
    before = emu.restart()
    assert before["3"] > 1 and before["12"] > 1
    emu.menu(3)
    emu.click("down", 6)
    emu.click("select")
    emu.click("down")
    doc = json.loads((ROOT / "data/timetable.json").read_text())
    doc["release_version"] = version
    payload = compile_dataset(doc)
    session = 990000 + version
    begin = {"TYPE": 5, "SESSION": session, "REQUEST": before["8"], "VERSION": version,
             "LENGTH": len(payload), "CRC": zlib.crc32(payload) & 0xffffffff}
    emu.drain()
    emu.command("send", message=begin)
    # The confirmation was selected before BEGIN. Do not await its ACK before
    # pressing SELECT: this exercises the asynchronous validation/cancel path.
    emu.command("button", name="select", durationMs=60)
    emu.wait(lambda e: e.get("event") == "command" and e.get("op") == "button")
    time.sleep(.8)
    after = emu.state()
    assert after["3"] == 1 and after["12"] == 0, after
    assert after["8"] != before["8"], "Restore must invalidate the phone's old check"
    for message, seq, phase in [(begin, 0, 5),
                                ({"TYPE": 6, "SESSION": session, "SEQ": 0,
                                  "DATA": list(payload[:192])}, 0, 6)]:
        emu.drain()
        emu.command("send", message=message)
        reply = emu.wait(lambda e: e.get("event") == "appmessage" and
                         e["message"].get("0") == 8 and e["message"].get("1") == session and
                         e["message"].get("2") == seq and e["message"].get("13") == phase)["message"]
        assert reply["7"] == 2, reply
    # A download still in XHR has no known session at the instant of Restore.
    # Its later fresh session must also fail, even if already queued in JS.
    for stale in [dict(begin, SESSION=session+1),
                  {k:v for k,v in dict(begin, SESSION=session+2).items() if k!="REQUEST"}]:
        emu.drain()
        emu.command("send", message=stale)
        reply = emu.wait(lambda e: e.get("event") == "appmessage" and
                         e["message"].get("0") == 8 and e["message"].get("1") == stale["SESSION"] and
                         e["message"].get("13") == 5)["message"]
        assert reply["7"] == 2, reply
    # A later explicit request remains possible. Restart abandons this empty
    # candidate without touching the newly restored baseline.
    resumed = dict(begin, SESSION=session+3, REQUEST=after["8"])
    emu.drain()
    emu.command("send", message=resumed)
    reply = emu.wait(lambda e: e.get("event") == "appmessage" and
                     e["message"].get("0") == 8 and e["message"].get("1") == resumed["SESSION"] and
                     e["message"].get("13") == 5)["message"]
    assert reply["7"] == 0, reply
    after = emu.restart()
    assert after["3"] == 1 and after["12"] == 0
    assert after["8"] == resumed["REQUEST"], "Restore cancellation must survive restart"
    obsolete = dict(begin, SESSION=session+4)
    emu.drain()
    emu.command("send", message=obsolete)
    reply = emu.wait(lambda e: e.get("event") == "appmessage" and
                     e["message"].get("0") == 8 and e["message"].get("1") == obsolete["SESSION"] and
                     e["message"].get("13") == 5)["message"]
    assert reply["7"] == 2, reply
    emu.screenshot("emery_29_restored_baseline")
    print("PASS native Restore cancels deferred update and late download sessions; old/missing request BEGINs rejected; new request accepted; bundled v1 survives restart", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["navigation", "rollover", "focus-removal", "restore-during-begin"])
    parser.add_argument("--current", type=int, default=6)
    parser.add_argument("--future", type=int, default=7)
    args = parser.parse_args()
    emu = Emulator()
    original = emu.state()["6"]
    try:
        if args.phase == "navigation":
            navigation(emu)
        elif args.phase == "rollover":
            rollover(emu, args.current, args.future)
        elif args.phase == "restore-during-begin":
            restore_during_begin(emu, args.future + 3)
        else:
            focus_removal(emu, args.current, args.future)
    finally:
        emu.action("bluetooth", connected=True)
        emu.action("timeFormat", is24Hour=True)
        emu.date(dt.datetime.now(dt.timezone.utc).isoformat())
        emu.settings(original)
        emu.restart()
        emu.close()


if __name__ == "__main__":
    main()
