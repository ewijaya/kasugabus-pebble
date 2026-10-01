"""Hosting guards use isolated synthetic versions and mocked HTTPS reads only."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile
import textwrap
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hosting_validator_test", ROOT / "tools/validate_hosting.py")
hosting = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hosting)
publish = hosting.publisher
BASE = hosting.BASE_URL
TODAY = "2026-10-01"


class HostingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_temp = tempfile.TemporaryDirectory(prefix="kasugabus-hosting-fixture-")
        cls.fixture = Path(cls.fixture_temp.name).resolve()
        baseline = json.loads((ROOT / "data/timetable.json").read_text())
        paths, reports = [], []
        for version, effective in ((1, TODAY), (2, TODAY), (3, "2026-10-03")):
            doc = copy.deepcopy(baseline)
            doc["release_version"] = version
            doc["effective_from"] = effective
            source = cls.fixture / f"source-{version}.json"
            source.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            report = cls.fixture / f"review-{version}.json"
            report.write_text(json.dumps({"releaseVersion": version,
                "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "departureCount": len(doc["departures"]), "reconciled": True,
                "reviewer": "Synthetic hosting test fixture only", "reviewedAt": TODAY}))
            paths.append(source)
            reports.append(report)
        output = cls.fixture / "public"
        publish.prepare(paths[0], None, [reports[0]], BASE, output, TODAY)
        publish.prepare(paths[1], paths[2], reports[1:], BASE, output, TODAY)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kasugabus-hosting-test-")
        self.directory = Path(self.temp.name).resolve()
        shutil.copytree(self.fixture, self.directory / "input")
        self.input = self.directory / "input"
        self.public = self.input / "public"
        self.sources = [self.input / f"source-{version}.json" for version in (1, 2, 3)]
        self.feed = hosting.read_json(self.public / "manifest.json")

    def tearDown(self):
        self.temp.cleanup()

    def validate(self, **kwargs):
        return hosting.validate_existing(self.public, BASE,
            kwargs.pop("sources", self.sources), kwargs.pop("validation_date", TODAY), **kwargs)

    def write_manifest(self, feed):
        (self.public / "manifest.json").write_text(json.dumps(feed), encoding="utf-8")

    def inventory(self):
        return {"schema": 1, "coverage": hosting.COVERAGE, "files": [
            hosting.file_record("releases/" + path.name, path.read_bytes())
            for path in sorted((self.public / "releases").iterdir())]}

    def remote(self, manifest=None, inventory=None):
        values = copy.deepcopy({BASE + "/manifest.json": self.feed if manifest is None else manifest,
                                BASE + "/inventory.json": self.inventory() if inventory is None else inventory})
        return lambda url: copy.deepcopy(values[url])

    def test_reviewed_current_future_history_is_read_only(self):
        before = {str(path.relative_to(self.public)): path.read_bytes()
                  for path in self.public.rglob("*") if path.is_file()}
        result = self.validate()
        self.assertEqual((result["currentVersion"], result["upcomingVersion"]), (2, 3))
        self.assertEqual(len(result["inventory"]["files"]), 3)
        self.assertFalse(result["liveChecked"])
        after = {str(path.relative_to(self.public)): path.read_bytes()
                 for path in self.public.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_exact_active_source_bytes_are_required(self):
        self.sources[1].write_bytes(self.sources[1].read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Exact reviewed source"):
            self.validate()
        with self.assertRaisesRegex(ValueError, "Exact reviewed source"):
            self.validate(sources=self.sources[:1] + self.sources[2:], check_live=True, fetcher=self.remote())

    def test_archived_source_or_live_pin_required_for_history(self):
        with self.assertRaisesRegex(ValueError, "unpinned historical"):
            self.validate(sources=self.sources[1:])
        result = self.validate(sources=self.sources[1:], check_live=True, fetcher=self.remote())
        self.assertIn("unchanged_live_inventory_pin", result["sourceProofs"].values())

    def test_review_report_cannot_approve_unreconciled_or_wrong_count(self):
        path = self.public / "reports/2-review.json"
        original = hosting.read_json(path)
        for field, value in (("reconciled", False), ("departureCount", original["departureCount"] + 1), ("reviewer", ""), ("reviewedAt", "2026-10-02")):
            report = dict(original)
            report[field] = value
            path.write_text(json.dumps(report))
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate()

    def test_manifest_bound_matches_production_phone(self):
        raw = (self.public / "manifest.json").read_bytes()
        (self.public / "manifest.json").write_bytes(raw + b" " * (hosting.MAX_MANIFEST - len(raw) + 1))
        with self.assertRaisesRegex(ValueError, "bounded regular"):
            self.validate()

    def test_corrupt_frozen_payload_or_mismatched_metadata_rejects(self):
        path = self.public / self.feed["current"]["url"][len(BASE) + 1:]
        original = path.read_bytes()
        path.write_bytes(original[:-1] + b"X")
        with self.assertRaisesRegex(ValueError, "Filename/version/hash"):
            self.validate()
        path.write_bytes(original)
        self.feed["current"]["reviewDue"] = "2026-11-02"
        self.write_manifest(self.feed)
        with self.assertRaisesRegex(ValueError, "Manifest metadata"):
            self.validate()

    def test_every_pinned_historical_payload_uses_full_phone_parser(self):
        path = next((self.public / "releases").glob("1-*.bin"))
        payload = bytearray(path.read_bytes())
        payload[50] = 1  # Invalid reserved header; all outer checksums repaired.
        struct.pack_into("<I", payload, 12, zlib.crc32(payload[16:]) & 0xffffffff)
        replacement = path.with_name(f"1-{hashlib.sha256(payload).hexdigest()[:16]}.bin")
        path.unlink()
        replacement.write_bytes(payload)
        with self.assertRaisesRegex(ValueError, "Production phone validation"):
            self.validate(sources=self.sources[1:], check_live=True, fetcher=self.remote())

    def test_first_publish_requires_both_live_paths_actually_missing(self):
        with self.assertRaisesRegex(ValueError, "dedicated Pages site"):
            self.validate(check_live=True, fetcher=lambda url: None)
        result = self.validate(check_live=True, fetcher=lambda url: None, allow_first_deployment=True)
        self.assertTrue(result["firstDeployment"])
        for missing in ("manifest", "inventory"):
            remote = self.remote()
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, "manifest/inventory missing"):
                self.validate(check_live=True, fetcher=lambda url: None if url.endswith(f"/{missing}.json") else remote(url))

    def test_live_historical_files_cannot_be_removed(self):
        remote = self.remote()
        next((self.public / "releases").glob("1-*.bin")).unlink()
        with self.assertRaisesRegex(ValueError, "missing or changed"):
            self.validate(check_live=True, fetcher=remote)

    def test_changed_live_hash_pin_rejects(self):
        inventory = self.inventory()
        record = inventory["files"][0]
        digest = "a" * 64
        record.update(path="releases/1-" + digest[:16] + ".bin", sha256=digest)
        with self.assertRaisesRegex(ValueError, "missing or changed"):
            self.validate(check_live=True, fetcher=self.remote(inventory=inventory))

    def test_matured_future_release_prevents_old_current_downgrade(self):
        remote = self.remote()
        self.feed["upcoming"] = None
        self.write_manifest(self.feed)
        with self.assertRaisesRegex(ValueError, "effective-date/version downgrade"):
            self.validate(validation_date="2026-10-04", check_live=True, fetcher=remote)

    def test_higher_version_with_older_activation_date_is_still_downgrade(self):
        candidate = copy.deepcopy(self.feed)
        candidate["current"]["version"] = 20
        candidate["upcoming"] = None
        with self.assertRaisesRegex(ValueError, "effective-date/version downgrade"):
            hosting.guard_live(candidate, self.inventory()["files"], self.feed, {}, "2026-10-04")

    def test_pending_snapshot_cannot_disappear_or_change_activation_date(self):
        for replacement in (None, dict(self.feed["upcoming"], version=4, effectiveFrom="2026-10-04"), dict(self.feed["upcoming"], version=4, effectiveFrom="2026-10-02")):
            candidate = dict(self.feed, upcoming=replacement)
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, "pending activation date"):
                hosting.guard_live(candidate, self.inventory()["files"], self.feed, {}, TODAY)
        candidate = dict(self.feed, upcoming=dict(self.feed["upcoming"], version=4))
        hosting.guard_live(candidate, self.inventory()["files"], self.feed, {}, TODAY)

    def test_publication_date_cannot_move_back(self):
        candidate = dict(self.feed, published="2026-09-30")
        with self.assertRaisesRegex(ValueError, "publication-date downgrade"):
            hosting.guard_live(candidate, self.inventory()["files"], self.feed, {}, TODAY)

    def test_inventory_cannot_hide_duplicate_versions_or_paths(self):
        inventory = self.inventory()
        inventory["files"].append(dict(inventory["files"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            hosting.validate_inventory(inventory)

    def test_unexpected_release_and_symlink_inputs_reject(self):
        extra = self.public / "releases/notes.txt"
        extra.write_text("Not a release")
        with self.assertRaisesRegex(ValueError, "Unexpected file"):
            self.validate()
        extra.unlink()
        path = self.public / "manifest.json"
        actual = self.directory / "manifest-copy.json"
        path.replace(actual)
        path.symlink_to(actual)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.validate()

    def test_https_fetch_does_not_treat_failure_or_redirect_as_first_publish(self):
        for error in (HTTPError(BASE, 302, "redirect", {}, None), HTTPError(BASE, 503, "unavailable", {}, None), URLError("offline")):
            with self.subTest(error=error), patch.object(hosting, "build_opener") as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(ValueError):
                    hosting.fetch_json(BASE + "/manifest.json")
        with patch.object(hosting, "build_opener") as opener:
            opener.return_value.open.side_effect = HTTPError(BASE, 404, "missing", {}, None)
            self.assertIsNone(hosting.fetch_json(BASE + "/manifest.json"))
        self.assertIsNone(hosting.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://elsewhere.example"))

    def test_ambiguous_json_is_rejected(self):
        for raw in (b'{"schema":1,"schema":2}', b'{"value":NaN}', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                hosting.json_bytes(raw)

    def stage(self, result):
        workflow = (ROOT / ".github/workflows/timetables.yml").read_text()
        script = textwrap.dedent(workflow.split("# BEGIN PUBLIC ARTIFACT STAGING\n", 1)[1].split("          # END PUBLIC ARTIFACT STAGING", 1)[0])
        report = self.directory / "validation.json"
        report.write_text(json.dumps(result))
        target = self.directory / "site"
        with patch.dict(os.environ, INPUT_ROOT=str(self.public), OUTPUT_ROOT=str(target), REVIEW_FILE=str(report)):
            exec(compile(script, "workflow-public-staging", "exec"), {})
        return target

    def test_artifact_contains_only_index_manifest_inventory_and_all_payloads(self):
        (self.public / "private-notes.txt").write_text("Must stay outside public artifact")
        result = self.validate()
        site = self.stage(result)
        expected = {"index.html", "timetables/manifest.json", "timetables/inventory.json"}
        expected.update("timetables/" + record["path"] for record in result["inventory"]["files"])
        actual = {str(path.relative_to(site)) for path in site.rglob("*") if path.is_file()}
        self.assertEqual(expected, actual)
        self.assertEqual((site / "timetables/manifest.json").read_bytes(), (self.public / "manifest.json").read_bytes())

    def test_artifact_rejects_changes_after_validation(self):
        for target_name in ("manifest.json", self.feed["current"]["url"][len(BASE) + 1:]):
            result = self.validate()
            path = self.public / target_name
            original = path.read_bytes()
            path.write_bytes(original + b"\n")
            with self.subTest(target=target_name), self.assertRaisesRegex(ValueError, "changed after validation"):
                self.stage(result)
            path.write_bytes(original)
            shutil.rmtree(self.directory / "site")

    def test_workflow_is_manual_default_review_only_and_actions_pinned(self):
        workflow = (ROOT / ".github/workflows/timetables.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        for forbidden in ("  push:", "  pull_request:", "  schedule:", "  workflow_run:", "  release:"):
            self.assertNotIn(forbidden, workflow)
        self.assertIn("default: false", workflow)
        self.assertIn("if: inputs.publish == true", workflow)
        self.assertIn("needs: validate", workflow)
        self.assertIn("name: github-pages", workflow)
        self.assertIn("enablement: false", workflow)
        self.assertIn("--check-live", workflow)
        self.assertIn("github.event.repository.default_branch", workflow)
        for action in re.findall(r"uses: (\S+)", workflow):
            self.assertRegex(action, r"^actions/[a-z-]+@[a-f0-9]{40}$")


if __name__ == "__main__":
    unittest.main()
