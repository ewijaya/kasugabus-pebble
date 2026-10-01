import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from data_build import clock_minute
from data_validate import validate


class TimetableSourceTests(unittest.TestCase):
    def test_complete_source_reconciliation(self):
        report = validate()
        self.assertEqual(report["departureCount"], 1411)
        self.assertEqual(report["matrixCellCount"], 1297)
        self.assertEqual(report["hankyuTripCount"], 114)
        self.assertEqual(report["verifiedCoordinateCount"], 6)

    def test_missing_and_invented_departures_rejected(self):
        original = json.loads((ROOT / "data" / "timetable.json").read_text())
        for transform in [lambda d: d["departures"].pop(),
                          lambda d: d["departures"].append(copy.deepcopy(d["departures"][0])),
                          lambda d: d["departures"][0].__setitem__("minute", 999)]:
            candidate = copy.deepcopy(original)
            transform(candidate)
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "candidate.json"
                path.write_text(json.dumps(candidate, ensure_ascii=False))
                with self.assertRaises(ValueError):
                    validate(path)

    def test_calendar_and_operator_claims_rejected(self):
        original = json.loads((ROOT / "data" / "timetable.json").read_text())
        for transform in [lambda d: d["calendar"].__setitem__("coverage_until", "2027-12-31"),
                          lambda d: d["calendar"]["holidays"].pop(),
                          lambda d: d["operators"][1].__setitem__("day_types", [1, 2, 3]),
                          lambda d: d["boarding_points"][-1]["coordinate"].__setitem__("latitude", 34.8)]:
            candidate = copy.deepcopy(original)
            transform(candidate)
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "candidate.json"
                path.write_text(json.dumps(candidate, ensure_ascii=False))
                with self.assertRaises(ValueError):
                    validate(path)

    def test_downstream_and_route_evidence_changes_rejected(self):
        original = json.loads((ROOT / "data" / "timetable.json").read_text())
        for transform in [lambda d: d["patterns"][0]["downstream_calls"].pop(),
                          lambda d: d["departures"][0]["evidence"]["independent_pole"].__setitem__("mark", "★")]:
            candidate = copy.deepcopy(original)
            transform(candidate)
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "candidate.json"
                path.write_text(json.dumps(candidate, ensure_ascii=False))
                with self.assertRaises(ValueError):
                    validate(path)

    def test_service_day_time_parser(self):
        self.assertEqual(clock_minute("24:05"), 1445)
        self.assertEqual(clock_minute("26:10"), 1570)
        self.assertIsNone(clock_minute(""))
        self.assertIsNone(clock_minute("↓"))
        with self.assertRaises(ValueError):
            clock_minute("25:60")


if __name__ == "__main__":
    unittest.main()
