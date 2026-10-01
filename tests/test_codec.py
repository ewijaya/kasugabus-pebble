"""Synthetic codec/calendar fixtures; these are never production timetables."""
import copy
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("compile_timetable", ROOT / "tools/compile_timetable.py")
COMPILER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPILER)


def fixture():
    return {
        "schema_version": 1, "release_version": 1, "minimum_app_version": 1,
        "coverage_id": "synthetic-fixture-only", "effective_from": "2026-10-01",
        "valid_from": "2026-10-01", "valid_until": "2026-11-30",
        "source_verified_at": "2026-10-01", "review_due": "2026-11-01",
        "operators": [{"id": 1, "name_en": "Fixture Kintetsu", "name_ja": "架空近鉄", "source_ids": ["fixture"]},
                      {"id": 2, "name_en": "Fixture Hankyu", "name_ja": "架空阪急", "no_service_day_types": [2, 3]}],
        "stop_groups": [{"id": 1, "name_en": "Fixture stop", "name_ja": "架空停留所"},
                        {"id": 2, "name_en": "Fixture destination", "name_ja": "架空目的地"},
                        {"id": 3, "name_en": "Fixture loop call", "name_ja": "架空循環"}],
        "boarding_points": [{"id": 1, "operator_id": 1, "stop_group_id": 1, "direction_en": "Fixture eastbound", "coordinate": None},
                            {"id": 101, "operator_id": 2, "stop_group_id": 1, "direction_en": "Fixture westbound", "coordinate_status": "verified_pole",
                             "coordinate": {"latitude": 34.8, "longitude": 135.5}}],
        "patterns": [{"id": 1, "operator_id": 1, "boarding_route": "25", "destination_en": "Fixture destination", "downstream_calls": [{"stop_group_id": 2}, {"stop_group_id": 3}],
                      "route_transitions": [{"at": "Fixture call", "route": "22"}]},
                     {"id": 2, "operator_id": 1, "boarding_route": "1", "destination_en": "Fixture loop", "downstream_calls": [{"stop_group_id": 3}]},
                     {"id": 3, "operator_id": 2, "boarding_route": "1", "destination_en": "Fixture destination", "downstream_calls": [{"stop_group_id": 2}]}],
        "services": [{"id": 1, "operator_id": 1, "day_types": [1]}, {"id": 2, "operator_id": 1, "day_types": [2]},
                     {"id": 3, "operator_id": 1, "day_types": [3]}, {"id": 4, "operator_id": 2, "day_types": [1]}],
        "calendar": {"coverage_from": "2026-10-01", "coverage_until": "2026-11-30",
                     "holidays": [{"date": "2026-10-12", "name": "Fixture holiday"}, {"date": "2026-11-03", "name": "Fixture substitute holiday scenario"}],
                     "exceptions": [{"date": "2026-10-12", "operator_id": 1, "day_type": 1},
                                    {"date": "2026-10-13", "operator_id": 1, "day_type": 0},
                                    {"date": "2026-10-14", "operator_id": 2, "day_type": 255}]},
        "departures": [{"boarding_point_id": 1, "pattern_id": 1, "service_id": 1, "minute": 633},
                       {"boarding_point_id": 1, "pattern_id": 2, "service_id": 1, "minute": 634},
                       {"boarding_point_id": 1, "pattern_id": 1, "service_id": 1, "minute": 1505},
                       {"boarding_point_id": 1, "pattern_id": 1, "service_id": 2, "minute": 700},
                       {"boarding_point_id": 1, "pattern_id": 1, "service_id": 3, "minute": 800},
                       {"boarding_point_id": 101, "pattern_id": 3, "service_id": 4, "minute": 640}],
        "sources": [{"id": "fixture", "name": "Synthetic fixture source", "url": "https://example.invalid/fixture", "revision_date": "2026-09-01"}],
    }


def fix_crc(payload):
    struct.pack_into("<I", payload, 12, zlib.crc32(payload[16:]) & 0xffffffff)
    return bytes(payload)


class CodecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="kasugabus-engine-tests-")
        cls.directory = Path(cls.temp.name)
        cls.executable = cls.directory / "test-engine"
        cls.library = cls.directory / "engine.so"
        flags = ["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic"]
        subprocess.run(flags + [str(ROOT / "src/c/engine.c"), str(ROOT / "tests/test_engine.c"), "-o", str(cls.executable)], check=True)
        subprocess.run(flags + ["-shared", "-fPIC", str(ROOT / "src/c/engine.c"), "-o", str(cls.library)], check=True)
        cls.lib = ctypes.CDLL(str(cls.library))
        cls.lib.kb_dataset_open.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
        cls.lib.kb_dataset_open.restype = ctypes.c_int
        cls.lib.kb_calendar_day.argtypes = [ctypes.c_void_p, ctypes.c_uint8, ctypes.c_int32]
        cls.lib.kb_calendar_day.restype = ctypes.c_int
        cls.lib.kb_crc32.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        cls.lib.kb_crc32.restype = ctypes.c_uint32

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def accepts(self, payload):
        output = ctypes.create_string_buffer(512)
        source = ctypes.create_string_buffer(bytes(payload))
        return self.lib.kb_dataset_open(output, source, len(payload))

    def test_crc32_standard_vectors_random_and_long_bytes_match_zlib(self):
        samples = [b"", b"123456789", bytes(range(256)), bytes(range(256))*256]
        rng = random.Random(20261001)
        for length in (1, 2, 3, 15, 16, 17, 191, 192, 193, 255, 256, 257,
                       1023, 4096, 24203, 32768, 65536):
            samples.append(bytes(rng.randrange(256) for _ in range(length)))
        samples.extend(bytes(rng.randrange(256) for _ in range(rng.randrange(32769))) for _ in range(64))
        for index, value in enumerate(samples):
            with self.subTest(sample=index, length=len(value)):
                source = ctypes.create_string_buffer(value)
                self.assertEqual(self.lib.kb_crc32(source, len(value)), zlib.crc32(value) & 0xffffffff)
        self.assertEqual(self.lib.kb_crc32(None, 0), 0)

    def test_engine_scenarios_and_timezone_independence(self):
        baseline = fixture()
        future = fixture()
        future.update(release_version=2, effective_from="2026-10-03")
        future["departures"] = [dep for dep in future["departures"] if dep["minute"] < 1440]
        unknown = fixture()
        unknown["calendar"].update(coverage_until="2026-10-02", holidays=[])
        none = fixture()
        none["calendar"]["exceptions"] = [{"date": f"2026-10-{day:02}", "operator_id": 1, "day_type": 0} for day in range(1, 9)]
        paths = []
        for name, doc in (("baseline", baseline), ("future", future), ("unknown", unknown), ("none", none)):
            path = self.directory / (name + ".bin")
            path.write_bytes(COMPILER.compile_dataset(doc))
            paths.append(str(path))
        for timezone in ("Asia/Tokyo", "America/Los_Angeles", "UTC"):
            result = subprocess.run([str(self.executable)] + paths, env=dict(os.environ, TZ=timezone), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("engine fixture tests passed", result.stdout)

    def test_valid_roundtrip_and_metadata(self):
        payload = COMPILER.compile_dataset(fixture())
        self.assertEqual(self.accepts(payload), 0)
        self.assertLess(len(payload), 24576)
        self.assertEqual(payload[:4], b"KBT1")
        self.assertIn("架空停留所".encode(), payload)
        self.assertEqual(struct.unpack_from("<I", payload, 12)[0], zlib.crc32(payload[16:]) & 0xffffffff)
        self.assertNotEqual(zlib.crc32(payload) & 0xffffffff, struct.unpack_from("<I", payload, 12)[0])

    def test_deterministic_order_and_evidence_ignored(self):
        doc = fixture()
        initial = COMPILER.compile_dataset(doc)
        for name in ("operators", "stop_groups", "boarding_points", "patterns", "services", "departures"):
            random.Random(42).shuffle(doc[name])
        doc["departures"][0]["evidence"] = {"source_id": "fixture", "row": 999}
        self.assertEqual(initial, COMPILER.compile_dataset(doc))

    def test_synthetic_overnight_max_and_empty_schedules(self):
        doc = fixture()
        doc["departures"][0]["minute"] = 4319
        self.assertEqual(self.accepts(COMPILER.compile_dataset(doc)), 0)
        doc["departures"] = []
        self.assertEqual(self.accepts(COMPILER.compile_dataset(doc)), 0)

    def test_unverified_day_type_is_unconfirmed(self):
        doc = fixture()
        del doc["operators"][1]["no_service_day_types"]
        payload = COMPILER.compile_dataset(doc)
        output = ctypes.create_string_buffer(512)
        source = ctypes.create_string_buffer(payload)
        self.assertEqual(self.lib.kb_dataset_open(output, source, len(payload)), 0)
        saturday = COMPILER.date("2026-10-03", "fixture date")
        self.assertEqual(self.lib.kb_calendar_day(output, 2, saturday), 255)

    def test_production_dataset_matches_c_structure_and_size_budget(self):
        doc = json.loads((ROOT / "data/timetable.json").read_text(encoding="utf-8"))
        payload = COMPILER.compile_dataset(doc)
        self.assertEqual(self.accepts(payload), 0)
        self.assertLessEqual(len(payload), 24576)
        count = struct.unpack_from("<H", payload, 68+7*6)[0]
        self.assertEqual(count, len(doc["departures"]))

    def test_compiler_rejects_invalid_references_values_and_identity(self):
        mutations = [lambda d: d.update(schema_version=2), lambda d: d.update(release_version=0),
            lambda d: d.update(valid_until="2026-02-30"), lambda d: d.update(valid_until="2026-09-30"),
            lambda d: d["boarding_points"][0].update(stop_group_id=99), lambda d: d["boarding_points"][0].update(operator_id=99),
            lambda d: d["patterns"][0].update(operator_id=2), lambda d: d["departures"][0].update(service_id=99),
            lambda d: d["departures"][0].update(minute=4320), lambda d: d["departures"][0].update(minute=-1),
            lambda d: d["departures"][0].update(minute=True), lambda d: d["services"][0].update(day_types=[0]),
            lambda d: d["services"][0].update(day_types=[1, 1]), lambda d: d["services"][0].update(valid_until="2026-12-01"),
            lambda d: d["calendar"]["holidays"].append(d["calendar"]["holidays"][0]),
            lambda d: d["calendar"]["exceptions"].append(d["calendar"]["exceptions"][0]),
            lambda d: d["departures"].append(d["departures"][0]), lambda d: d["stop_groups"].append(d["stop_groups"][0]),
            lambda d: d["patterns"][0]["downstream_calls"].append({"stop_group_id": 99}),
            lambda d: d["boarding_points"][1].update(coordinate_status="approximate"),
            lambda d: d["boarding_points"][1]["coordinate"].update(latitude=91),
            lambda d: d["stop_groups"][0].update(name_en="a"*1024),
            lambda d: d["stop_groups"][0].update(name_en="a\0b")]
        for change in mutations:
            doc = fixture()
            change(doc)
            with self.subTest(change=change), self.assertRaises(ValueError):
                COMPILER.compile_dataset(doc)

    def test_compiler_rejects_overlapping_duplicate_services(self):
        doc = fixture()
        doc["services"].append({"id": 5, "operator_id": 1, "day_types": [1]})
        dep = dict(doc["departures"][0], service_id=5)
        doc["departures"].append(dep)
        with self.assertRaises(ValueError):
            COMPILER.compile_dataset(doc)

    def test_binary_rejects_corruption(self):
        original = COMPILER.compile_dataset(fixture())
        self.assertNotEqual(self.accepts(original[:-1]), 0)
        self.assertNotEqual(self.accepts(original+b"\0"), 0)
        changes = [(0, b"BAD!", False), (4, b"\2\0", False), (16, b"\0\0\0\0", True),
                   (64, b"\0\0\0\0", True), (60, b"\xff\xff", True), (50, b"\1\0", True),
                   (124, b"\xff\xff\xff\x7f", True)]
        for offset, value, checksum in changes:
            payload = bytearray(original)
            payload[offset:offset+len(value)] = value
            if checksum:
                payload = fix_crc(payload)
            with self.subTest(offset=offset):
                self.assertNotEqual(self.accepts(payload), 0)
        payload = bytearray(original)
        payload[-2] ^= 1
        self.assertNotEqual(self.accepts(payload), 0)

    def test_binary_rejects_references_sort_and_strings(self):
        original = COMPILER.compile_dataset(fixture())
        point = struct.unpack_from("<I", original, 64+2*6)[0]
        group = struct.unpack_from("<I", original, 64+1*6)[0]
        departure = struct.unpack_from("<I", original, 64+7*6)[0]
        pool = struct.unpack_from("<I", original, 52)[0]
        changes = [(point+1, b"\x63"), (point+3, b"\2"), (point+4, b"\xff\xff"),
                   (group+8, b"\1"), (departure+2, b"\x63"), (departure+3, b"\3"),
                   (pool+1, b"\xff"), (pool, b"a"), (point+4, b"\2\0")]
        for offset, value in changes:
            payload = bytearray(original)
            payload[offset:offset+len(value)] = value
            with self.subTest(offset=offset):
                self.assertNotEqual(self.accepts(fix_crc(payload)), 0)
        payload = bytearray(original)
        payload[departure:departure+5], payload[departure+5:departure+10] = payload[departure+5:departure+10], payload[departure:departure+5]
        self.assertNotEqual(self.accepts(fix_crc(payload)), 0)

    def test_catalog_missing_coordinate_is_not_invented(self):
        catalog = COMPILER.make_catalog(fixture())
        self.assertIsNone(catalog["boardingPoints"][0]["coordinate"])
        self.assertEqual(catalog["boardingPoints"][1]["coordinate"]["latitude"], 34.8)

    def test_cli_emits_deterministic_payload_and_catalog(self):
        source = self.directory / "fixture.json"
        binary = self.directory / "cli.bin"
        catalog = self.directory / "catalog.json"
        source.write_text(json.dumps(fixture()), encoding="utf-8")
        result = subprocess.run(["python3", str(ROOT / "tools/compile_timetable.py"), str(source), "-o", str(binary), "--catalog", str(catalog)], check=True, text=True, capture_output=True)
        self.assertEqual(binary.read_bytes(), COMPILER.compile_dataset(fixture()))
        self.assertEqual(json.loads(catalog.read_text())["coverageId"], "synthetic-fixture-only")
        self.assertIn("6 departures", result.stdout)


if __name__ == "__main__":
    unittest.main()
