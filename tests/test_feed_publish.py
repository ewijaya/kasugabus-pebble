import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("publish_feed", ROOT / "tools/publish_feed.py")
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kasugabus-publish-test-")
        self.directory = Path(self.temp.name)
        self.doc = json.loads((ROOT / "data/timetable.json").read_text())
        self.doc["release_version"] = 2
        self.current, self.current_report = self.write_review(self.doc, "current")
        future = copy.deepcopy(self.doc)
        future["release_version"] = 3
        future["effective_from"] = "2026-10-03"
        self.future, self.future_report = self.write_review(future, "future")

    def tearDown(self):
        self.temp.cleanup()

    def write_review(self, doc, name):
        source = self.directory / f"{name}.json"
        source.write_text(json.dumps(doc, ensure_ascii=False))
        report = self.directory / f"{name}-review.json"
        report.write_text(json.dumps({"releaseVersion": doc["release_version"],
            "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "departureCount": len(doc["departures"]), "reconciled": True,
            "reviewer": "Synthetic test review only", "reviewedAt": "2026-10-01"}))
        return source, report

    def prepare(self, upcoming=True):
        return publish.prepare(self.current, self.future if upcoming else None,
            [self.current_report, self.future_report] if upcoming else [self.current_report],
            "https://test.example/feed", self.directory / "public", "2026-10-01")

    def test_current_future_immutable_artifacts_and_diff(self):
        feed = self.prepare()
        self.assertEqual(feed["current"]["version"], 2)
        self.assertEqual(feed["upcoming"]["version"], 3)
        output = self.directory / "public"
        self.assertEqual(len(list((output / "releases").glob("*.bin"))), 2)
        self.assertEqual(json.loads((output / "reports/2-diff.json").read_text())["version"], 2)
        self.assertEqual(self.prepare(), feed)  # exact repeat is safe
        with self.assertRaisesRegex(ValueError, "upcoming"):
            self.prepare(upcoming=False)

    def test_diff_reports_station_minutes_that_move_no_departure(self):
        # Schema 2 adds minutes to existing departures; the diff must not call that "no change".
        before = json.loads((ROOT / "data/timetable_v4.json").read_text())
        after = json.loads((ROOT / "data/timetable_v5.json").read_text())
        diff = publish.departure_diff(before, after)
        self.assertEqual((diff["departuresAdded"], diff["departuresRemoved"], diff["changedSections"]), ([], [], []))
        self.assertEqual(diff["stationMinutes"], {"previous": 0, "current": 1199, "added": 1199, "removed": 0, "changed": 0})
        later = copy.deepcopy(after)
        later["release_version"] = 6
        timed = [d for d in later["departures"] if d.get("station_minutes")]
        timed[0]["station_minutes"] = dict(timed[0]["station_minutes"], jr=timed[0]["station_minutes"]["jr"] + 1)
        del timed[1]["station_minutes"]
        self.assertEqual(publish.departure_diff(after, later)["stationMinutes"],
                         {"previous": 1199, "current": 1198, "added": 0, "removed": 1, "changed": 1})
        # Datasets without station minutes keep the exact diff shape older reports have.
        self.assertNotIn("stationMinutes", publish.departure_diff(before, before))

    def test_exact_review_hash_required(self):
        self.current.write_text(self.current.read_text()+"\n")
        with self.assertRaisesRegex(ValueError, "exact source"):
            self.prepare()
        self.assertFalse((self.directory / "public/manifest.json").exists())

    def test_review_must_be_reconciled(self):
        report = json.loads(self.current_report.read_text())
        report["reconciled"] = False
        self.current_report.write_text(json.dumps(report))
        with self.assertRaises(ValueError):
            self.prepare()

    def test_insecure_and_uncontrolled_urls_reject(self):
        for url in ("http://127.0.0.1:8080", "https://person:password@test.example", "https://test.example/../x", "https://test.example/feed?x=1"):
            with self.assertRaises(ValueError):
                publish.approved_base(url)

    def test_reused_version_never_changes_manifest(self):
        self.prepare()
        manifest = self.directory / "public/manifest.json"
        previous = manifest.read_bytes()
        changed = copy.deepcopy(self.doc)
        changed["review_due"] = "2026-11-02"
        self.current, self.current_report = self.write_review(changed, "changed")
        with self.assertRaisesRegex(ValueError, "existing release version"):
            self.prepare()
        self.assertEqual(manifest.read_bytes(), previous)


if __name__ == "__main__":
    unittest.main()
