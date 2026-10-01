"""Host guards only: synthetic files/fake bridge, no native acceptance claims."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import queue
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import verify_accessibility as accessibility
import verify_emulator as native


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kasugabus-harness-only-")
        self.root = Path(self.temp.name)
        self.pbw = self.root / "kasugabus-pebble.pbw"
        self.receipt = self.root / "runtime.install.json"
        self.make_fixture()

    def tearDown(self):
        self.temp.cleanup()

    def make_fixture(self, **changes):
        info = {"uuid": accessibility.UUID, "versionLabel": "2.0.0", "targetPlatforms": ["emery"], "watchapp": {"watchface": False}}
        info.update(changes)
        with zipfile.ZipFile(self.pbw, "w") as archive:
            archive.writestr("appinfo.json", json.dumps(info))
            archive.writestr("emery/pebble-app.bin", b"PBLAPP\0\0SYNTHETIC TEST ONLY")
            archive.writestr("pebble-js-app.js", "/* SYNTHETIC TEST ONLY */")
        stamp = dt.datetime.now(dt.timezone.utc).isoformat()
        self.record = {"schema": 1, "artifact": {"sha256": accessibility.sha(self.pbw.read_bytes()), "bytes": self.pbw.stat().st_size}, "environment": "emulator", "command": ["pebble", "install", "--emulator", "emery", str(self.pbw)], "started_at": stamp, "finished_at": stamp}
        self.receipt.write_text(json.dumps(self.record))

    def test_schema2_fixture_and_all_combinations_preserve_nonappearance_bytes(self):
        base = native.preferences(point=102)
        self.assertEqual(base[:8], [2, 0, 102, 0, 2, 4, 1, 0])
        base[1] = 16
        original = base.copy()
        for size in range(3):
            for theme in range(4):
                packet = accessibility.appearance(base, size, theme)
                self.assertEqual(packet[0], 2)
                self.assertEqual(packet[6:8], [size, theme])
                self.assertEqual(packet[1], 16 | (8 if theme >= 2 else 0))
                self.assertEqual(packet[2:6] + packet[8:], base[2:6] + base[8:])
        self.assertEqual(base, original)

    def test_legacy_migration_expects_large_and_original_dark_contrast(self):
        for contrast in (False, True):
            packet = native.preferences(102, contrast)
            packet[0], packet[6], packet[7] = 1, 0, 0
            value = accessibility.normalized(packet)
            self.assertEqual(value[6:8], [1, 2 if contrast else 0])
            self.assertEqual(value[2:6] + value[8:], packet[2:6] + packet[8:])
        for changes in ({0: 3}, {6: 3}, {7: 4}):
            packet = native.preferences()
            for index, value in changes.items():
                packet[index] = value
            with self.assertRaises(ValueError):
                accessibility.normalized(packet)
        with self.assertRaises(ValueError):
            accessibility.normalized([0] * 79)

    def test_receipt_binds_pbw_app_version_not_dataset_version(self):
        result = accessibility.artifact_proof(self.pbw, self.receipt, "2.0.0")
        self.assertEqual(result["appVersion"], "2.0.0")
        self.assertEqual(result["receiptSha256"], accessibility.sha(self.receipt.read_bytes()))
        with self.assertRaises(ValueError):
            accessibility.artifact_proof(self.pbw, self.receipt, "1.0.0")
        for changes in ({"environment": "physical"}, {"artifact": {"sha256": "f"*64, "bytes": self.pbw.stat().st_size}}, {"command": ["pebble", "build"]}):
            self.receipt.write_text(json.dumps(dict(self.record, **changes)))
            with self.assertRaises(ValueError):
                accessibility.artifact_proof(self.pbw, self.receipt)

    def test_wrong_receipt_stops_before_emulator_connection(self):
        self.record["artifact"]["sha256"] = "f" * 64
        self.receipt.write_text(json.dumps(self.record))
        with patch.object(accessibility, "Emulator") as emulator, self.assertRaises(ValueError):
            accessibility.main(["--pbw", str(self.pbw), "--runtime-receipt", str(self.receipt), "--output", str(self.root / "report.json"), "--screenshot-prefix", "fixture_only"])
        emulator.assert_not_called()

    def test_capture_namespace_cannot_overwrite_old_evidence_or_escape_directory(self):
        with patch.object(native.subprocess, "Popen") as process, self.assertRaises(ValueError):
            native.Emulator(screenshot_prefix="../published")
        process.assert_not_called()
        target = self.root / "artifacts/screenshots/old_home.png"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"published evidence")
        emu = native.Emulator.__new__(native.Emulator)
        emu.screenshot_prefix = "old"
        emu.action = Mock()
        with patch.object(native, "ROOT", self.root), self.assertRaises(FileExistsError):
            emu.screenshot("home")
        emu.action.assert_not_called()
        self.assertEqual(target.read_bytes(), b"published evidence")

    def test_capture_refuses_wrong_native_dimensions(self):
        image = self.root / "wrong.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + struct.pack(">II", 201, 228))
        emu = Mock()
        emu.observed = [{"event": "watchlog", "message": "UI screen0 heap32000"},
                        {"event": "watchlog", "message": "UI selection0 scroll0 limit0"}]
        emu.screenshot.return_value = {"path": str(image)}
        with self.assertRaisesRegex(AssertionError, "native 200x228"):
            accessibility.capture(emu, [], "fixture_only", 0)

    def test_native_selection_proof_consumes_scroll_before_advancing_row(self):
        emu = Mock()
        emu.observed = []
        draws = iter([(0, 0, 140), (0, 64, 140), (0, 128, 140),
                      (0, 140, 140), (1, 0, 0), (2, 0, 0)])
        def emit():
            selected, scroll, limit = next(draws)
            emu.observed.extend([
                {"event": "watchlog", "message": "UI screen10 heap32000", "observedAt": time.monotonic()},
                {"event": "watchlog", "message": "UI selection%d scroll%d limit%d" % (selected, scroll, limit), "observedAt": time.monotonic()}])
        emit()
        emu.click.side_effect = lambda *_args, **_kw: emit()
        result = accessibility.choose_row(emu, 10, 2)
        self.assertEqual(result["selection"], 2)
        self.assertEqual(emu.click.call_count, 5)
        self.assertTrue(all(call.args == ("down",) for call in emu.click.call_args_list))
        emu.wait.assert_not_called()

    def test_point_capture_default_binding_preserves_other_preferences(self):
        packet = native.preferences(102, True)
        original = packet.copy()
        expected = packet.copy()
        expected[2:4] = [101, 0]
        emu = Mock()
        emu.restart.return_value = {"6": expected}
        emu.observed = [{"event": "watchlog", "message": "UI screen0 heap32000"},
                        {"event": "watchlog", "message": "UI selection0 scroll0 limit0"}]
        self.assertEqual(accessibility.install_point(emu, packet, 101), expected)
        emu.settings.assert_called_once_with(expected)
        self.assertEqual(packet, original)

    def test_missing_draw_log_resyncs_once_without_replaying_button(self):
        emu=Mock();emu.observed=[];emu.ui_resyncs=0
        emu.wait.side_effect=TimeoutError("isolated dropped native log")
        def redraw():
            stamp=time.monotonic()
            emu.observed.extend([
                {"event":"watchlog","message":"UI screen10 heap32000","observedAt":stamp},
                {"event":"watchlog","message":"UI selection7 scroll64 limit140","observedAt":stamp}])
        emu.state.side_effect=redraw
        result=accessibility.await_ui(emu,10)
        self.assertEqual((result["selection"],result["scroll"]),(7,64))
        self.assertEqual(emu.ui_resyncs,1)
        emu.state.assert_called_once();emu.click.assert_not_called()
        emu.observed=[];emu.state.side_effect=lambda:None
        with self.assertRaisesRegex(TimeoutError,"proof missing"):
            accessibility.await_ui(emu,10)
        self.assertEqual(emu.state.call_count,2)  # One resync per failed wait.

    def test_cleanup_restores_preferences_even_if_clock_transport_fails(self):
        original = native.preferences(102, True)
        emu = Mock()
        emu.date.side_effect = RuntimeError("Fixture clock transport failed")
        emu.restart.return_value = {"6": original}
        result = accessibility.restore(emu, original)
        self.assertFalse(result["actualClockRestored"])
        self.assertTrue(result["originalPreferencesRestored"])
        emu.settings.assert_called_once_with(original, expected=original)
        emu.close.assert_called_once()
        self.assertEqual(len(result["errors"]), 1)

    def test_bridge_timeout_and_eof_have_bounded_named_failures(self):
        emu = native.Emulator.__new__(native.Emulator)
        emu.events = queue.Queue()
        emu.observed = []
        emu.deadline = None
        with self.assertRaisesRegex(TimeoutError, "event missing"):
            emu.wait(lambda e: True, .01)
        emu.events.put({"event": "error", "message": "Emulator bridge stdout closed"})
        with self.assertRaisesRegex(RuntimeError, "stdout closed"):
            emu.wait(lambda e: True, .01)


if __name__ == "__main__":
    unittest.main()
