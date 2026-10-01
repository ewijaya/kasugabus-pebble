"""Boarded-route queries: synthetic schedules and read-only production reconciliation."""
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("routes_compiler", ROOT / "tools/compile_timetable.py")
COMPILER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPILER)


def route_fixture():
    """Every date/time/name here is synthetic; no fixture becomes production data."""
    doc = {
        "schema_version": 1, "release_version": 1, "minimum_app_version": 1,
        "coverage_id": "synthetic-routes-only", "effective_from": "2026-10-01",
        "valid_from": "2026-10-01", "valid_until": "2026-11-30",
        "source_verified_at": "2026-10-01", "review_due": "2026-11-01",
        "operators": [
            {"id": 1, "name_en": "Fixture Kintetsu", "day_types": [1, 2, 3]},
            {"id": 2, "name_en": "Fixture Hankyu", "day_types": [1], "no_service_day_types": [2, 3]},
        ],
        "stop_groups": [{"id": i, "name_en": f"Fixture group {i}"} for i in range(1, 5)],
        "boarding_points": [
            {"id": i, "operator_id": op, "stop_group_id": group,
             "direction_en": f"Fixture point {i}", "coordinate": None}
            for i, op, group in [(1, 1, 1), (2, 1, 2), (3, 1, 3), (4, 1, 4), (101, 2, 1), (102, 2, 2)]
        ],
        "patterns": [],
        "services": [{"id": i, "operator_id": 1, "day_types": [i]} for i in (1, 2, 3)] +
                    [{"id": 4, "operator_id": 2, "day_types": [1]}],
        "calendar": {"coverage_from": "2026-10-01", "coverage_until": "2026-11-30",
                     "holidays": ["2026-10-12", "2026-11-03"],
                     "exceptions": [{"date": "2026-10-12", "operator_id": 1, "day_type": 1},
                                    {"date": "2026-10-13", "operator_id": 1, "day_type": 0}]},
        "sources": [{"id": "fixture", "name": "Synthetic route fixture", "url": "https://example.invalid/routes"}],
        "departures": [],
    }
    # IDs deliberately disagree with numeric route order; ID 11 is unreferenced.
    for identity, operator, number in [(1, 1, "25"), (2, 1, "2"), (3, 1, "1"),
                                       (4, 1, "22"), (5, 1, "24"), (6, 1, "25"),
                                       (7, 2, "171"), (8, 2, "72"), (9, 2, "164"),
                                       (10, 2, "2"), (11, 1, "999")]:
        pattern = {"id": identity, "operator_id": operator, "boarding_route": number,
                   "destination_en": f"Fixture destination {identity}", "downstream_calls": [{"stop_group_id": 2}]}
        if identity == 1:
            pattern["downstream_calls"].append({"stop_group_id": 3})
            pattern["route_transitions"] = [{"at": "Fixture group 3", "route": "22"}]
        doc["patterns"].append(pattern)
    for point, pattern, service, minute in [
        (1, 3, 1, 620), (1, 2, 1, 621), (1, 5, 1, 622),
        (1, 2, 2, 730), (1, 2, 3, 830),
        (2, 1, 1, 633), (2, 6, 1, 634), (2, 1, 1, 1505),
        (2, 1, 2, 700), (2, 1, 3, 800), (3, 4, 1, 650),
        (101, 9, 4, 640), (101, 10, 4, 645), (102, 8, 4, 630), (102, 7, 4, 635),
    ]:
        doc["departures"].append({"boarding_point_id": point, "pattern_id": pattern,
                                  "service_id": service, "minute": minute})
    return doc


def snapshots():
    baseline = route_fixture()
    future = copy.deepcopy(baseline)
    future.update(release_version=2, effective_from="2026-10-03")
    future["operators"][0]["name_en"] = "A" * 512 + " Fixture future"
    later = copy.deepcopy(baseline)
    later.update(release_version=3, effective_from="2026-10-05")
    later["operators"][0]["name_en"] = "B" * 600 + " Fixture later"
    # Change IDs, never the stable operator/boarding-number identity.
    for doc, delta in [(future, 40), (later, 80)]:
        for pattern in doc["patterns"]:
            pattern["id"] += delta
        for departure in doc["departures"]:
            departure["pattern_id"] += delta
    # Route 25 disappears from the later snapshot; route 22 replaces its point.
    later["departures"] = [d for d in later["departures"] if d["pattern_id"] not in (81, 86)]
    later["departures"].append({"boarding_point_id": 2, "pattern_id": 84, "service_id": 1, "minute": 633})
    unknown = copy.deepcopy(baseline)
    unknown["calendar"].update(coverage_until="2026-10-02", holidays=[])
    none = copy.deepcopy(baseline)
    none["calendar"]["exceptions"] = [{"date": f"2026-10-{day:02}", "operator_id": 1, "day_type": 0}
                                        for day in range(1, 9)]
    return [baseline, future, later, unknown, none]


def expected_routes(doc):
    patterns = {p["id"]: p for p in doc["patterns"]}
    return {(patterns[d["pattern_id"]]["operator_id"], patterns[d["pattern_id"]]["boarding_route"])
            for d in doc["departures"]}


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="kasugabus-routes-")
        cls.directory = Path(cls.temp.name)
        cls.paths = []
        for name, doc in zip(("baseline", "future", "later", "unknown", "none"), snapshots()):
            path = cls.directory / f"{name}.bin"
            path.write_bytes(COMPILER.compile_dataset(doc))
            cls.paths.append(str(path))
        cls.flags = ["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic"]
        cls.sources = [str(ROOT / "src/c/engine.c"), str(ROOT / "tests/test_routes.c")]
        cls.executable = cls.directory / "routes"
        subprocess.run(cls.flags + cls.sources + ["-o", str(cls.executable)], check=True, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_fixture(self, executable=None, environment=None):
        result = subprocess.run([str(executable or self.executable), "fixtures", *self.paths],
                                env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("route fixtures passed", result.stdout)

    def inspect(self, doc):
        path = self.directory / "inspection.bin"
        path.write_bytes(COMPILER.compile_dataset(doc))
        result = subprocess.run([str(self.executable), "inspect", str(path)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        routes, memberships = [], {}
        for row in result.stdout.splitlines():
            parts = row.split()
            if parts[0] == "R":
                routes.append((int(parts[1]), parts[2]))
            elif parts[0] == "M":
                memberships[(int(parts[1]), int(parts[2]), parts[3])] = bool(int(parts[4]))
            else:
                self.fail(f"Unexpected route inspector row: {row}")
        return routes, memberships

    def query_rows(self, doc, point, operator, number, date):
        path = self.directory / "queried.bin"
        path.write_bytes(COMPILER.compile_dataset(doc))
        instant = int(dt.datetime.fromisoformat(date + "T00:00:00+09:00").timestamp())
        result = subprocess.run([str(self.executable), "query", str(path), str(point), str(operator), number, str(instant)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [tuple(map(int, row.split()[1:])) for row in result.stdout.splitlines()]

    def test_portable_calendar_filter_due_transition_and_reused_future_cache(self):
        for timezone in ("UTC", "Asia/Tokyo", "America/Los_Angeles"):
            with self.subTest(timezone=timezone):
                self.run_fixture(environment=dict(os.environ, TZ=timezone))

    def test_production_routes_and_every_point_membership_match_reconciled_json(self):
        doc = json.loads((ROOT / "data/timetable.json").read_text())
        routes, memberships = self.inspect(doc)
        expected = expected_routes(doc)
        self.assertEqual(expected, {(1, "1"), (1, "2"), (1, "22"), (1, "24"), (1, "25"),
                                    (2, "72"), (2, "164"), (2, "171")})
        self.assertEqual(routes, sorted(expected, key=lambda key: (key[0], int(key[1]))))
        patterns = {p["id"]: p for p in doc["patterns"]}
        by_point = {point["id"]: {(patterns[d["pattern_id"]]["operator_id"], patterns[d["pattern_id"]]["boarding_route"])
                                  for d in doc["departures"] if d["boarding_point_id"] == point["id"]}
                    for point in doc["boarding_points"]}
        self.assertEqual(len(memberships), len(by_point) * len(expected))
        for (point, operator, number), actual in memberships.items():
            self.assertEqual(actual, (operator, number) in by_point[point], (point, operator, number))
        self.assertTrue(memberships[(4, 1, "25")])
        self.assertFalse(memberships[(4, 1, "22")])
        self.assertTrue(memberships[(5, 1, "22")])
        self.assertFalse(memberships[(5, 1, "25")])
        self.assertTrue(memberships[(102, 2, "72")])
        self.assertFalse(memberships[(102, 1, "2")])

    def test_leading_zero_labels_stay_distinct_and_filter_exactly(self):
        doc = route_fixture()
        doc["patterns"].append({"id": 12, "operator_id": 1, "boarding_route": "02", "destination_en": "Leading-zero fixture"})
        doc["departures"].append({"boarding_point_id": 4, "pattern_id": 12, "service_id": 1, "minute": 600})
        routes, memberships = self.inspect(doc)
        self.assertEqual(len(routes), 10)
        self.assertIn((1, "02"), routes)
        self.assertIn((1, "2"), routes)
        self.assertTrue(memberships[(4, 1, "02")])
        self.assertFalse(memberships[(4, 1, "2")])
        self.assertFalse(memberships[(1, 1, "02")])
        self.assertEqual(self.query_rows(doc, 4, 1, "02", "2026-10-01"), [(600, 12, 1, 1)])
        self.assertEqual(self.query_rows(doc, 4, 1, "2", "2026-10-01"), [])

    def test_production_filtered_rows_equal_source_json_on_weekday_saturday_and_sunday(self):
        doc = json.loads((ROOT / "data/timetable.json").read_text())
        patterns = {p["id"]: p for p in doc["patterns"]}
        services = {s["id"]: s for s in doc["services"]}
        # Reconcile every emitted row, including exact pattern/service identity.
        for point, operator, number in [(1, 1, "2"), (4, 1, "25"), (5, 1, "25"), (102, 2, "72")]:
            for date, dtype in [("2026-10-01", 1), ("2026-10-03", 2), ("2026-10-04", 3)]:
                with self.subTest(point=point, route=number, date=date):
                    expected = sorted((d["minute"], d["pattern_id"], d["service_id"], dtype)
                                      for d in doc["departures"]
                                      if d["boarding_point_id"] == point
                                      and patterns[d["pattern_id"]]["operator_id"] == operator
                                      and patterns[d["pattern_id"]]["boarding_route"] == number
                                      and dtype in services[d["service_id"]]["day_types"]
                                      and services[d["service_id"]]["valid_from"] <= date <= services[d["service_id"]]["valid_until"])
                    self.assertEqual(self.query_rows(doc, point, operator, number, date), expected)

    def test_address_and_undefined_sanitizers(self):
        target = self.directory / "routes-sanitized"
        subprocess.run(self.flags + ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"] +
                       self.sources + ["-o", str(target)], check=True, capture_output=True, text=True)
        # Apple ASan supports address/UB checks but not LeakSanitizer.
        options = "detect_leaks=0" if sys.platform == "darwin" else "detect_leaks=1"
        self.run_fixture(executable=target, environment=dict(os.environ, ASAN_OPTIONS=options, UBSAN_OPTIONS="halt_on_error=1"))


if __name__ == "__main__":
    unittest.main()
