#!/usr/bin/env python3
"""Capture the installed Emery app's appearance matrix; never build or install.

Native settings acknowledgments and restarts prove persistence. Native 200x228
captures still require visual review for clipping, contrast and readability.
Temporary preferences and the current host clock are restored on exit.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import struct
import time
import zipfile
from verify_emulator import Emulator, ROOT

UUID = "d7ba77b0-d528-4cc8-b35c-7052798152c9"
SIZES = ("Standard", "Large", "Extra Large")
THEMES = ("Neon Dark", "Neon Light", "High Contrast Dark", "High Contrast Light")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def normalized(data):
    if not isinstance(data, list) or len(data) != 80 or any(type(n) is not int or not 0 <= n <= 255 for n in data):
        raise ValueError("Expected an 80-byte native preferences packet")
    value = data.copy()
    if value[0] == 1:
        if value[6] or value[7]:
            raise ValueError("Schema 1 appearance bytes must be zero")
        value[0], value[6], value[7] = 2, 1, 2 if value[1] & 8 else 0
    if value[0] != 2 or value[6] > 2 or value[7] > 3:
        raise ValueError("Unknown preferences appearance schema/value")
    value[1] = (value[1] & ~8) | (8 if value[7] >= 2 else 0)
    return value


def appearance(data, size, theme):
    if type(size) is not int or not 0 <= size <= 2 or type(theme) is not int or not 0 <= theme <= 3:
        raise ValueError("Invalid appearance choice")
    value = normalized(data)
    value[6], value[7] = size, theme
    value[1] = (value[1] & ~8) | (8 if theme >= 2 else 0)
    return value


def artifact_proof(pbw, receipt_path, expected_version=None):
    raw, receipt_raw = Path(pbw).read_bytes(), Path(receipt_path).read_bytes()
    receipt = json.loads(receipt_raw)
    artifact = {"sha256": sha(raw), "bytes": len(raw)}
    with zipfile.ZipFile(pbw) as archive:
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError("PBW contains duplicate entries")
        info = json.loads(archive.read("appinfo.json"))
        if info.get("uuid") != UUID or info.get("targetPlatforms") != ["emery"] or info.get("watchapp", {}).get("watchface") is not False:
            raise ValueError("Expected the Emery-only KasugaBus interactive PBW")
        version = info.get("versionLabel")
        if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version) or expected_version is not None and version != expected_version:
            raise ValueError("PBW app version differs from the requested candidate")
        if not {"pebble-js-app.js", "emery/pebble-app.bin"} <= set(archive.namelist()):
            raise ValueError("PBW watch/phone payload missing")
    command = receipt.get("command", [])
    if receipt.get("schema") != 1 or receipt.get("environment") != "emulator" or receipt.get("artifact") != artifact or command[:2] != ["pebble", "install"] or "--emulator" not in command or "emery" not in command:
        raise ValueError("Installation receipt does not bind this exact PBW to Emery")
    started, finished = dt.datetime.fromisoformat(receipt["started_at"]), dt.datetime.fromisoformat(receipt["finished_at"])
    if started.tzinfo is None or finished.tzinfo is None or started > finished:
        raise ValueError("Installation receipt timestamps are invalid")
    return dict(artifact, appVersion=version, uuid=UUID, platform="emery", receiptSha256=sha(receipt_raw))


def catalog_points(path):
    raw = Path(path).read_bytes()
    value = json.loads(raw)
    points = value.get("boardingPoints", [])
    if not points or len(points) > 255 or len({p["id"] for p in points}) != len(points):
        raise ValueError("Capture catalogue has missing/duplicate boarding IDs")
    for point in points:
        if not 1 <= point["id"] <= 255 or not 1 <= point["groupId"] <= 255 or any(not isinstance(point.get(k), str) or not point[k] for k in ("label", "name", "nameJa", "direction")):
            raise ValueError("Capture catalogue labels/IDs are invalid")
    return sorted(points, key=lambda p: p["id"]), sha(raw)


def native_ui(emu):
    """Pair adjacent native draw diagnostics, never infer selection from clicks."""
    draw, complete = None, None
    for event in emu.observed:
        if event.get("event") != "watchlog":
            continue
        message = event.get("message", "")
        screen = re.search(r"\bUI screen(\d+) heap(\d+)\b", message)
        selection = re.search(r"\bUI selection(\d+) scroll(\d+) limit(\d+)\b", message)
        if screen:
            draw = {"screen": int(screen[1]), "heap": int(screen[2])}
        elif selection and draw is not None:
            complete = dict(draw, selection=int(selection[1]), scroll=int(selection[2]),
                            scrollLimit=int(selection[3]), observedAt=event.get("observedAt", 0))
            draw = None
    return complete


def await_ui(emu, screen=None, since=0):
    for attempt in range(2):
        end = time.monotonic() + 5
        try:
            while time.monotonic() < end:
                emu.drain()
                value = native_ui(emu)
                if value and value["observedAt"] >= since and (screen is None or value["screen"] == screen):
                    return value
                emu.wait(lambda e: e.get("event") == "watchlog" and "UI selection" in e.get("message", ""), max(.01, end-time.monotonic()))
        except TimeoutError:
            pass
        if attempt==0:
            # HELLO/STATE triggers a redraw without replaying a UI button.
            # Resume only from its fresh paired native screen/selection proof.
            since=time.monotonic()
            emu.state()
            emu.ui_resyncs=getattr(emu,"ui_resyncs",0)+1
    raise TimeoutError("Native screen/selection proof missing")


def ui_click(emu, name, screen=None, long=False):
    since = time.monotonic()
    emu.click(name, long=long)
    return await_ui(emu, screen, since)


def choose_row(emu, screen, target):
    if type(target) is not int or not 0 <= target <= 254:
        raise ValueError("Invalid native row target")
    value = await_ui(emu, screen)
    for _ in range(80):
        if value["selection"] == target:
            return value
        previous = (value["selection"], value["scroll"])
        value = ui_click(emu, "down" if value["selection"] < target else "up", screen)
        if (value["selection"], value["scroll"]) == previous:
            raise AssertionError("Native list cannot reach requested row")
    raise TimeoutError("Native list selection exceeded 80 single clicks")


def open_menu(emu, index, screen):
    ui_click(emu, "select", 3, long=True)
    choose_row(emu, 3, index)
    return ui_click(emu, "select", screen)


def home(emu):
    for _ in range(8):
        if await_ui(emu)["screen"] == 0:
            return
        ui_click(emu, "back")
    raise AssertionError("Native BACK did not return to Home")


def scroll_bottom(emu, screen):
    value = await_ui(emu, screen)
    for _ in range(80):
        if value["scroll"] == value["scrollLimit"]:
            return value
        previous = value["scroll"]
        value = ui_click(emu, "down", screen)
        if value["scroll"] <= previous:
            raise AssertionError("Native document scroll did not advance")
    raise TimeoutError("Native document exceeded 80 scroll clicks")


def capture(emu, captures, name, screen, **evidence):
    await_ui(emu, screen)
    result = emu.screenshot(name)
    draw = native_ui(emu)
    if draw is None or draw["screen"] != screen:
        raise AssertionError("Native screen differs from capture label")
    raw = Path(result["path"]).read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", raw[16:24]) != (200, 228):
        raise AssertionError("Capture is not a native 200x228 PNG")
    captures.append({"name": name, "path": str(Path(result["path"]).relative_to(ROOT)), "sha256": sha(raw),
        "nativeScreen": draw["screen"], "nativeSelection": draw["selection"], "nativeScroll": draw["scroll"],
        "nativeScrollLimit": draw["scrollLimit"], "heap": draw["heap"], "dimensions": [200, 228], "source": result.get("source"),
        "colourCorrection": result.get("colourCorrection"), "backlight": result.get("backlight"), **evidence})


def open_point_picker(emu, points, point):
    # Called from Home or the startup picker, never Board's refresh action.
    open_menu(emu, 0, 4)
    choose_row(emu, 4, 2)
    ui_click(emu, "select", 6)
    groups = sorted({p["groupId"] for p in points})
    index = groups.index(point["groupId"])
    choose_row(emu, 6, index)
    ui_click(emu, "select", 7)
    group = [p for p in points if p["groupId"] == point["groupId"]]
    index = next(i for i, p in enumerate(group) if p["id"] == point["id"])
    choose_row(emu, 7, index)
    return {"boardingPointId": point["id"], "groupId": point["groupId"], "catalogueRow": index,
            "pointProof": "native group/point selection indexes matched the supplied catalogue; not a point-ID STATE field"}


def install_point(emu, packet, point_id):
    value = packet.copy()
    value[2:4] = [point_id & 255, point_id >> 8]
    emu.settings(value)
    assert emu.restart()["6"] == value, "Temporary default boarding ID did not persist"
    await_ui(emu, 0)
    return value


def legacy_checks(emu, base):
    checks = []
    for contrast in (False, True):
        old = base.copy()
        old[0], old[6], old[7] = 1, 0, 0
        old[1] = (old[1] & ~8) | (8 if contrast else 0)
        expected = normalized(old)
        emu.settings(old, expected=expected)
        assert emu.restart()["6"] == expected, "Legacy migration did not survive restart"
        checks.append({"schema": 1, "contrast": contrast, "migratedSize": 1, "migratedTheme": expected[7], "prefsSha256": sha(bytes(expected))})
    return checks


def native_choice(emu, packet, row, target):
    open_menu(emu, 3, 10)
    choose_row(emu, 10, row)
    ui_click(emu, "select", 16 if row == 0 else 17)
    choose_row(emu, 16 if row == 0 else 17, target)
    ui_click(emu, "select", 10)
    expected = appearance(packet, target if row == 0 else packet[6], target if row == 1 else packet[7])
    assert emu.state()["6"] == expected, "Watch-side appearance choice was not accepted"
    assert emu.restart()["6"] == expected, "Watch-side choice did not survive restart"
    return expected


def matrix(emu, base, points, clock, captures, checks):
    primary = next(p for p in points if p["id"] == 1)
    longest = max(points, key=lambda p: (len(p["label"]), -p["id"]))
    japanese = max(points, key=lambda p: (len(p["nameJa"]), -p["id"]))
    for size in range(3):
        for theme in range(4):
            location_requests = emu.location_requests
            packet = install_point(emu, appearance(base, size, theme), primary["id"])
            emu.date(clock)
            tag = "size%d_theme%d" % (size, theme)
            def snap(name, screen, **evidence):
                capture(emu, captures, tag + "_" + name, screen, **evidence)
            proof = {"boardingPointId": primary["id"], "defaultPreferencesSha256": sha(bytes(packet)),
                     "pointProof": "acknowledged native default ID and exact preferences after restart; Home opens that default"}
            snap("home", 0, **proof)
            ui_click(emu, "select", 1); snap("board", 1, **proof)
            ui_click(emu, "select", 2); snap("details", 2, **proof)
            scroll_bottom(emu, 2); snap("details_scroll", 2, **proof)
            ui_click(emu, "select", 15); snap("japanese", 15, **proof)
            home(emu)
            open_menu(emu, 2, 11); snap("status", 11)
            scroll_bottom(emu, 11); snap("status_scroll", 11)
            home(emu)
            open_menu(emu, 3, 10); snap("settings", 10)
            choose_row(emu, 10, 0)
            ui_click(emu, "select", 16); snap("text_size_picker", 16)
            ui_click(emu, "back", 10); choose_row(emu, 10, 1)
            ui_click(emu, "select", 17); snap("theme_picker", 17)
            ui_click(emu, "back", 10); choose_row(emu, 10, 7)
            snap("settings_scroll", 10)  # Selected Restore row, never SELECT.
            home(emu)
            open_menu(emu, 0, 4); snap("stop_picker", 4)
            choose_row(emu, 4, 1); ui_click(emu, "select", 8)
            snap("nearby_location_off", 8)
            scroll_bottom(emu, 8); snap("nearby_location_off_scroll", 8)
            home(emu)
            assert emu.state()["6"] == packet, "Navigation changed appearance/nonappearance preferences"
            # Default ID + restart binds point-specific screenshots independently
            # of tall picker rows and of the favourites' saved ordering.
            long_packet = install_point(emu, packet, longest["id"])
            emu.date(clock)
            proof = dict(proof, boardingPointId=longest["id"], defaultPreferencesSha256=sha(bytes(long_packet)))
            snap("long_home", 0, **proof)
            ui_click(emu, "select", 1); snap("long_board", 1, **proof)
            home(emu)
            picker_proof = open_point_picker(emu, points, longest)
            snap("long_direction_picker", 7, **picker_proof)
            home(emu)
            japanese_packet = install_point(emu, long_packet, japanese["id"])
            emu.date(clock)
            ui_click(emu, "select", 1); ui_click(emu, "select", 2); ui_click(emu, "select", 15)
            snap("long_japanese", 15, **dict(proof, boardingPointId=japanese["id"], defaultPreferencesSha256=sha(bytes(japanese_packet))))
            state = emu.state()
            assert state["6"] == japanese_packet, "Navigation changed preferences"
            requests = emu.location_requests - location_requests
            assert requests == 0, "Location-off test emitted a native location request"
            checks.append({"textSize": SIZES[size], "theme": THEMES[theme], "prefsSha256": sha(bytes(packet)),
                           "temporaryDefaultIds": [primary["id"], longest["id"], japanese["id"]],
                           "persistedAfterRestart": True, "disabledLocationRequests": requests})
            print("PASS appearance", SIZES[size], THEMES[theme], flush=True)
    return captures, checks, {"longBoardingPoint": longest["id"], "longLabel": longest["label"], "longJapanesePoint": japanese["id"], "japaneseLabel": japanese["nameJa"]}


def route_cases(emu, base, captures):
    """Optional native route browsing; visible trip numbers need visual review."""
    raw = (ROOT / "data/timetable.json").read_bytes()
    data = json.loads(raw)
    patterns = {p["id"]: (p["operator_id"], p["boarding_route"]) for p in data["patterns"]}
    matching = {}
    for departure in data["departures"]:
        route = patterns[departure["pattern_id"]]
        matching.setdefault(route, set()).add(departure["boarding_point_id"])
    routes = sorted(matching, key=lambda r: (r[0], int(r[1])))
    if routes != [(1, "1"), (1, "2"), (1, "22"), (1, "24"), (1, "25"), (2, "72"), (2, "164"), (2, "171")]:
        raise AssertionError("Bus-number capture fixture differs from the eight reviewed routes")
    packet = install_point(emu, appearance(base, 0, 0), 1)
    checks = []
    for index, (operator, number) in enumerate(routes):
        home(emu)
        emu.date("2026-10-01T07:00:01+09:00")
        open_menu(emu, 0, 4); choose_row(emu, 4, 3)
        ui_click(emu, "select", 18); choose_row(emu, 18, index)
        tag = "route_%d_%s" % (operator, number)
        proof = {"operatorId": operator, "boardingNumber": number,
                 "pointProof": "native route/point list indexes matched the supplied timetable; Board/Details route labels require visual review"}
        capture(emu, captures, tag + "_list", 18, **proof)
        ui_click(emu, "select", 19); choose_row(emu, 19, 0)
        point_id = min(matching[(operator, number)])
        if (operator, number) == (1, "1") and point_id != 1:
            raise AssertionError("Kintetsu 1 first boarding point must be ID 1")
        proof["boardingPointId"] = point_id
        capture(emu, captures, tag + "_boarding_points", 19, **proof)
        draw = ui_click(emu, "select", 1)
        if draw["selection"] != 1:
            raise AssertionError("Route fixture has no focused trip; do not trigger a feed check")
        capture(emu, captures, tag + "_board", 1, **proof)
        if (operator, number) == (1, "1"):
            choose_row(emu, 1, 3)
            capture(emu, captures, tag + "_later_trips", 1, **proof)
        ui_click(emu, "select", 2)
        capture(emu, captures, tag + "_details", 2, **proof)
        ui_click(emu, "back", 1); ui_click(emu, "back", 19); ui_click(emu, "back", 18)
        assert emu.state()["6"] == packet, "Route browsing changed preferences"
        checks.append({"operatorId": operator, "boardingNumber": number, "firstBoardingPointId": point_id,
                       "backSequence": [1, 19, 18], "nativeSelectionConfirmed": True})
    return {"timetableSha256": sha(raw), "clockFixture": "2026-10-01T07:00:01+09:00", "routes": checks,
            "limits": "Manual review must confirm displayed route headers and boarding numbers; this does not inspect every unrendered trip or prove a different downloaded dataset's list order"}


def restore(emu, original):
    # Restoration is attempted even if one independent cleanup operation fails.
    emu.deadline = None
    errors = []
    clock_restored = prefs_restored = False
    try:
        now = dt.datetime.now().astimezone()
        emu.date(now.isoformat(), offset=int(now.utcoffset().total_seconds() // 60))
        clock_restored = True
    except Exception as error:
        errors.append("clock: " + str(error))
    try:
        expected = normalized(original)
        emu.settings(original, expected=expected)
        assert emu.restart()["6"] == expected
        prefs_restored = True
    except Exception as error:
        errors.append("preferences: " + str(error))
    try:
        emu.close()
    except Exception as error:
        errors.append("bridge close: " + str(error))
    return {"actualClockRestored": clock_restored, "originalPreferencesRestored": prefs_restored, "errors": errors}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbw", type=Path, required=True)
    parser.add_argument("--runtime-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--screenshot-prefix", required=True)
    parser.add_argument("--expect-version")
    parser.add_argument("--sdk-version")
    parser.add_argument("--bus-numbers", action="store_true", help="Also browse all eight reviewed routes; requires native screens 18/19")
    parser.add_argument("--catalog", type=Path, default=ROOT / "src/pkjs/catalog.json")
    parser.add_argument("--clock", default="2026-10-01T10:32:01+09:00")
    parser.add_argument("--max-seconds", type=int, default=1200)
    args = parser.parse_args(argv)
    proof = artifact_proof(args.pbw, args.runtime_receipt, args.expect_version)
    points, catalog_sha = catalog_points(args.catalog)
    if not 120 <= args.max_seconds <= 1800 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", args.screenshot_prefix):
        raise ValueError("Use a safe prefix and a 120..1800 second deadline")
    if dt.datetime.fromisoformat(args.clock).tzinfo is None:
        raise ValueError("Capture clock must include its UTC offset")
    if args.output.exists() or any((ROOT / "artifacts/screenshots").glob(args.screenshot_prefix + "_*.png")):
        raise FileExistsError("Never overwrite an accessibility report or capture namespace")
    emu = Emulator(screenshot_prefix=args.screenshot_prefix, expected_pbw=args.pbw, sdk_version=args.sdk_version, deadline=time.monotonic()+args.max_seconds)
    original = None
    report = {"schema": 1, "environment": "Emery emulator", "artifact": proof, "sdkCachedPbwSha256": emu.ready.get("cachedPbwSha256"), "sdkVersion": emu.ready.get("sdkVersion"),
        "catalogSha256": catalog_sha, "clockFixture": args.clock, "status": "failed", "visualReview": "REQUIRED: inspect every capture for clipping, wrapping, Japanese glyphs, contrast, focus and readability; native capture alone does not pass visual acceptance",
        "limits": ["Emulator only; no physical readability, GPS, phone settings, or battery acceptance", "Navigation labels use the supplied catalogue; dataset VERSION is not app identity", "No build, installation, feed replacement, or screenshot brightness/size editing"]}
    failure = None
    try:
        if emu.ready.get("cachedPbwSha256") != proof["sha256"]:
            raise AssertionError("SDK cached PBW identity is missing or differs")
        original = emu.state()["6"]
        base = normalized(original)
        # Suppress unrelated automatic/GPS actions during controlled screenshots.
        # Favourites/walking/buffer/motion remain intact; point captures use
        # explicit temporary default IDs, recorded below and restored on exit.
        base[1] &= ~(1 | 2 | 4)
        report["temporaryClearedFlags"] = ["automatic updates", "location", "Nearby startup"]
        report["navigationProof"] = "Native screen/selection/scroll logs; refuses older PBWs without selection diagnostics"
        report["legacyMigration"] = legacy_checks(emu, base)
        report["captures"], report["appearanceChecks"] = [], []
        _, _, report["longLabelCases"] = matrix(emu, base, points, args.clock, report["captures"], report["appearanceChecks"])
        packet = appearance(base, 0, 0)
        emu.settings(packet); emu.restart()
        native = []
        for size in (1, 2, 0):
            packet = native_choice(emu, packet, 0, size)
            native.append({"textSize": packet[6], "theme": packet[7], "persistedAfterRestart": True})
        for theme in (1, 2, 3, 0):
            packet = native_choice(emu, packet, 1, theme)
            native.append({"textSize": packet[6], "theme": packet[7], "persistedAfterRestart": True})
        report["watchPickerChecks"] = native
        if args.bus_numbers:
            report["busNumberChecks"] = route_cases(emu, base, report["captures"])
        if sha(args.pbw.read_bytes()) != proof["sha256"]:
            raise AssertionError("Supplied PBW changed during verification")
        report["status"] = "native checks passed; visual review required"
    except Exception as error:
        failure = error
        report["error"] = type(error).__name__ + ": " + str(error)
    finally:
        report["restoration"] = restore(emu, original) if original is not None else {"originalPreferencesRestored": False, "actualClockRestored": False, "errors": ["Original STATE unavailable; preferences/time were not changed"]}
        report["nativeUiRedrawResyncs"] = emu.ui_resyncs
        if original is None:
            emu.deadline = None
            emu.close()
        report["finishedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as destination:
            json.dump(report, destination, indent=2); destination.write("\n")
    if report["restoration"]["errors"]:
        raise RuntimeError("Native restoration incomplete; inspect report") from failure
    if failure:
        raise failure
    print("PASS native appearance/persistence checks; visual review REQUIRED:", args.output, flush=True)
    return report


if __name__ == "__main__":
    main()
