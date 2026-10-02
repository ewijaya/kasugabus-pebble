"""Offline behavioral release tests. No account, SDK build, Git or remote write."""
import argparse
import copy
import datetime
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
release = importlib.import_module("release")
common = importlib.import_module("release_common")
audit = importlib.import_module("check_release")
capture = importlib.import_module("capture_runtime")


def synthetic_pbw(path, version="1.0.0", **changes):
    info = {"uuid": common.UUID, "versionLabel": version, "longName": "KasugaBus", "targetPlatforms": ["emery"], "watchapp": {"watchface": False}}
    info.update(changes)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("appinfo.json", json.dumps(info))
        archive.writestr("emery/pebble-app.bin", b"PBLAPP\0\0" + b"synthetic test-only binary")
        archive.writestr("pebble-js-app.js", "/* synthetic test only */")


class Response:
    def __init__(self, data=None, content=b"", text=""):
        self.data, self.content, self.text = data, content, text
        self.status_code = 200

    def json(self):
        return copy.deepcopy(self.data)

    def raise_for_status(self):
        return None


def catalog_platform_fixture(description="Fixture description"):
    watches = ("aplite", "basalt", "chalk", "diorite", "emery", "flint", "gabbro")
    compatibility = {name: {"supported": name == "emery"} for name in watches}
    compatibility["emery"]["firmware"] = {"major": 3}
    compatibility.update(android={"supported": True}, ios={"supported": True, "min_js_version": 1})
    return {"hardware_platforms": [{"name": "emery", "sdk_version": "5.106", "pebble_process_info_flags": 328,
        "description": description, "images": {"fixture": "image.png"}}], "compatibility": compatibility}


class CatalogPlatformTests(unittest.TestCase):
    def setUp(self):
        self.public = catalog_platform_fixture()
        self.config = {"platforms": ["emery"]}

    def check(self):
        release.require_catalog_platforms(self.public, self.config)

    def test_observed_object_array_and_explicit_emery_support_pass(self):
        self.check()

    def test_hardware_missing_empty_or_legacy_string_shape_fails(self):
        for value in (None, [], "emery", {}, ["emery"]):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.public["hardware_platforms"] = value
                self.check()
        self.public.pop("hardware_platforms")
        with self.assertRaises(RuntimeError):
            self.check()

    def test_hardware_malformed_name_fails(self):
        for value in (None, {}, {"name": None}, {"name": True}, {"name": ["emery"]}, {"name": "EMERY"}, {"name": "unknown"}, {"name": "android"}):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.public["hardware_platforms"] = [value]
                self.check()

    def test_wrong_extra_or_duplicate_hardware_fails(self):
        for names in (("basalt",), ("emery", "basalt"), ("emery", "emery")):
            with self.subTest(names=names), self.assertRaises(RuntimeError):
                self.public["hardware_platforms"] = [{"name": name} for name in names]
                self.check()

    def test_missing_or_wrong_compatibility_container_fails(self):
        for value in (None, [], True, "emery", {}):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.public["compatibility"] = value
                self.check()
        self.public.pop("compatibility")
        with self.assertRaises(RuntimeError):
            self.check()

    def test_every_watch_target_requires_explicit_boolean_support(self):
        for name in catalog_platform_fixture()["compatibility"]:
            for value in (None, {}, {"supported": None}, {"supported": 0}, {"supported": 1}, {"supported": "true"}, {"supported": []}):
                with self.subTest(name=name, value=value), self.assertRaises(RuntimeError):
                    self.public = catalog_platform_fixture()
                    self.public["compatibility"][name] = value
                    self.check()
        for name in ("aplite", "basalt", "chalk", "diorite", "emery", "flint", "gabbro"):
            with self.subTest(missing=name), self.assertRaises(RuntimeError):
                self.public = catalog_platform_fixture()
                del self.public["compatibility"][name]
                self.check()

    def test_emery_unsupported_or_another_supported_watch_fails(self):
        self.public["compatibility"]["emery"]["supported"] = False
        with self.assertRaises(RuntimeError):
            self.check()
        for name in ("aplite", "basalt", "chalk", "diorite", "flint", "gabbro"):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                self.public = catalog_platform_fixture()
                self.public["compatibility"][name]["supported"] = True
                self.check()

    def test_unknown_compatibility_target_fails_even_if_unsupported(self):
        for value in (True, False):
            with self.subTest(supported=value), self.assertRaises(RuntimeError):
                self.public = catalog_platform_fixture()
                self.public["compatibility"]["unknown"] = {"supported": value}
                self.check()

    def test_phone_support_does_not_count_as_a_watch_target(self):
        self.public["compatibility"]["android"]["supported"] = False
        self.public["compatibility"]["ios"]["supported"] = False
        self.check()


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kasugabus-release-fixtures-")
        self.root = Path(self.temp.name)
        self.folder = self.root / ".release/1.0.0"
        self.folder.mkdir(parents=True)
        (self.root / "docs/releases").mkdir(parents=True)
        (self.root / "tests").mkdir()
        (self.root / "src").mkdir()
        (self.root / "src/fixture.c").write_text("/* Synthetic test only source */\n")
        (self.root / "build").mkdir()
        self.config = json.loads((ROOT / "docs/release-config.json").read_text())
        self.config.update(github_repo="fixture-owner/kasugabus", store_app_id="a"*24, listing_patch_contract="partial-description")
        (self.root / "docs/release-config.json").write_text(json.dumps(self.config))
        (self.root / "tests/build-budgets.json").write_bytes((ROOT / "tests/build-budgets.json").read_bytes())
        (self.root / "README.md").write_text("KasugaBus 1.0.0\n<!-- kasugabus-release-status -->\nUnreleased.\n")
        synthetic_pbw(self.folder / common.ARTIFACT)
        self.artifact = common.inspect_pbw(self.folder / common.ARTIFACT, "1.0.0")
        (self.folder / "runtime.log").write_text("SYNTHETIC TEST ONLY INIT entered\nREADY storage=1048576 heap=40000 message=0\nUI screen1 heap39000\nUpdate commit session1 status3 heap38000\n")
        self.metrics = {"resources": 30000, "static_ram": 35000, "image_bytes": 35000, "native_binary": 32000, "linker_free_ram": 96000, "pbw": self.artifact["bytes"], "timetable": 24000, "measured_free_heap": 38000}
        self.audit = {"schema": 1, "version": "1.0.0", "clean_build": True, "tests_passed": True, "artifact": self.artifact, "metrics": self.metrics,
            "created_at": (datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(seconds=1)).isoformat(),
            "runtime": {"environment": "emulator", "scenarios": ["launch", "navigation", "update-transfer"], "evidence_path": str(self.folder / "runtime.log"), "evidence_sha256": common.digest((self.folder / "runtime.log").read_bytes())}}
        self.audit["source"] = dict(common.source_fingerprint(self.root), git_commit="fixture-commit")
        receipt_path = self.folder / "runtime-install.json"
        receipt_path.write_text(json.dumps({"schema": 1, "artifact": self.artifact, "environment": "emulator", "command": ["pebble", "install", "--emulator", "emery", "--logs", str(self.folder / common.ARTIFACT)], "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "log_sha256": self.audit["runtime"]["evidence_sha256"]}))
        self.audit["runtime"]["install_receipt_path"] = str(receipt_path)
        (self.folder / "audit.json").write_text(json.dumps(self.audit))
        (self.folder / "notes.md").write_text("Fixture release notes\n")
        (self.folder / "description.txt").write_text("Fixture description\n")
        self.state = {"schema": 1, "version": "1.0.0", "commit": "fixture-commit", "config": self.config, "artifact": self.artifact,
            "metrics": self.metrics, "notes": "Fixture release notes", "notes_sha256": common.digest((self.folder / "notes.md").read_bytes()),
            "description": "Fixture description", "description_sha256": common.digest((self.folder / "description.txt").read_bytes()),
            "destinations": ["github", "appstore"], "physical_installed": True, "status": {}, "approval": None}
        release.save(self.folder, self.state)
        self.root_patch = patch.object(release, "ROOT", self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def args(self, **changes):
        result = {"version": "1.0.0", "approve_publish": "1.0.0", "approve_sha256": self.artifact["sha256"], "approve_physical": True, "approve_destination": ["github", "appstore"]}
        result.update(changes)
        return argparse.Namespace(**result)

    def app(self):
        return {"id": self.config["store_app_id"], "app_uuid": common.UUID, "title": "KasugaBus fixture", "description": "Old fixture description", "visible": True,
            "source": "https://example.invalid/fixture", "website": None, "category_id": "fixture-category", "icon_small": "icon", "icon_large": "large",
            "companion_apps": [{"platform": "android", "name": "Fixture Android", "url": "android", "required": False}, {"platform": "ios", "name": "Fixture iOS", "url": "ios", "required": True}],
            "unknown_metadata": {"preserve": "yes"}, "releases": [], "latest_release": {},
            "assets": [{"platform": "emery", "description": "Old fixture description", "screenshots": ["image1"], "headers": ["header1"], "banner": "banner", "custom_art": "keep"}]}

    def preparation(self):
        shutil.copy2(self.folder / common.ARTIFACT, self.root / "build" / common.ARTIFACT)
        (self.root / "artifacts").mkdir()
        runtime = self.root / "artifacts/runtime-fixture.log"
        runtime.write_bytes((self.folder / "runtime.log").read_bytes())
        report = copy.deepcopy(self.audit)
        report["runtime"]["evidence_path"] = str(runtime)
        receipt = self.root / "artifacts/runtime-fixture.log.install.json"
        receipt.write_bytes((self.folder / "runtime-install.json").read_bytes())
        report["runtime"]["install_receipt_path"] = str(receipt)
        audit_path = self.root / "build/release-audit.json"
        audit_path.write_text(json.dumps(report))
        notes = self.root / "notes.md"
        notes.write_text("Fixture notes\n")
        (self.root / "package.json").write_text(json.dumps({"version": "1.0.0"}))
        (self.root / "package-lock.json").write_text(json.dumps({"version": "1.0.0", "packages": {"": {"version": "1.0.0"}}}))
        (self.root / "CHANGELOG.md").write_text("1.0.0 fixture notes\n")
        report["source"] = dict(common.source_fingerprint(self.root), git_commit="fixture-commit")
        audit_path.write_text(json.dumps(report))
        shutil.rmtree(self.folder)
        return argparse.Namespace(version="1.0.0", destination=["github"], physical=True, notes=notes, description=None, audit=audit_path)

    def test_import_and_help_do_not_build_or_authenticate(self):
        with patch.object(release, "run") as run, patch.object(release, "dashboard_session") as auth:
            with self.assertRaises(SystemExit) as stop:
                release.main(["--help"])
            self.assertEqual(stop.exception.code, 0)
            run.assert_not_called()
            auth.assert_not_called()

    def test_missing_registration_stops_before_auth_or_build(self):
        config = dict(self.config, store_app_id=None)
        with patch.object(release, "load_config", return_value=config), patch.object(release, "run") as run, patch.object(release, "dashboard_session") as auth:
            with self.assertRaisesRegex(RuntimeError, "not registered"):
                release.prepare(argparse.Namespace(destination=["appstore"]))
            run.assert_not_called()
            auth.assert_not_called()

    def test_unknown_listing_contract_stops_before_auth(self):
        config = dict(self.config, listing_patch_contract=None)
        with self.assertRaisesRegex(RuntimeError, "PATCH behavior"):
            common.require_destinations(config, ["appstore"])

    def test_preparation_freezes_the_audited_physical_pbw_without_rebuilding(self):
        args = self.preparation()
        calls = []
        def command(*argv, **kwargs):
            calls.append(argv)
            return "[]" if argv[:2] == ("gh", "api") else "fixture-commit" if argv == ("git", "rev-parse", "HEAD") else None
        with patch.object(release, "clean_tree"), patch.object(release, "run", side_effect=command), patch.object(release, "dashboard_session") as auth:
            state = release.prepare(args)
        self.assertEqual(state["artifact"], self.artifact)
        self.assertTrue(state["physical_installed"])
        self.assertIsNone(state["approval"])
        self.assertEqual((self.folder / common.ARTIFACT).read_bytes(), (self.root / "build" / common.ARTIFACT).read_bytes())
        self.assertTrue((self.folder / "runtime.log").is_file())
        self.assertEqual(sum(argv[:2] == ("pebble", "install") for argv in calls), 1)
        self.assertFalse(any("build" in argv or "clean" in argv or "push" in argv or "tag" in argv for argv in calls))
        auth.assert_not_called()
        release.read_manifest("1.0.0")

    def test_physical_install_failure_creates_no_candidate(self):
        args = self.preparation()
        def command(*argv, **kwargs):
            if argv[:2] == ("pebble", "install"):
                raise RuntimeError("fixture watch disconnected")
            return "[]" if argv[:2] == ("gh", "api") else "fixture-commit"
        with patch.object(release, "clean_tree"), patch.object(release, "run", side_effect=command):
            with self.assertRaisesRegex(RuntimeError, "disconnected"):
                release.prepare(args)
        self.assertFalse(self.folder.exists())

    def test_existing_candidate_is_never_overwritten(self):
        args = argparse.Namespace(version="1.0.0", destination=["github"])
        (self.root / "package.json").write_text('{"version":"1.0.0"}')
        (self.root / "package-lock.json").write_text('{"version":"1.0.0","packages":{"":{"version":"1.0.0"}}}')
        (self.root / "CHANGELOG.md").write_text("1.0.0 fixture notes")
        with patch.object(release, "clean_tree"), patch.object(release, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                release.prepare(args)
        run.assert_not_called()
        self.assertEqual(common.inspect_pbw(self.folder / common.ARTIFACT, "1.0.0"), self.artifact)

    def test_wrong_project_and_watchface_rejected(self):
        for change in ({"uuid": "other"}, {"targetPlatforms": ["emery", "gabbro"]}, {"watchapp": {"watchface": True}}, {"versionLabel": "2.0.0"}, {"longName": "Other app"}):
            with self.subTest(change=change):
                synthetic_pbw(self.folder / common.ARTIFACT, **change)
                with self.assertRaises(RuntimeError):
                    common.inspect_pbw(self.folder / common.ARTIFACT, "1.0.0")

    def test_candidate_artifact_notes_config_and_log_tampering_rejected(self):
        mutations = [lambda: (self.folder / common.ARTIFACT).write_bytes((self.folder / common.ARTIFACT).read_bytes()+b"changed"),
            lambda: (self.folder / "notes.md").write_text("different"), lambda: (self.folder / "description.txt").write_text("different"),
            lambda: (self.folder / "runtime.log").write_text("different"), lambda: (self.root / "docs/release-config.json").write_text(json.dumps(dict(self.config, github_repo="other/repo")))]
        originals = {path: path.read_bytes() for path in [self.folder / common.ARTIFACT, self.folder / "notes.md", self.folder / "description.txt", self.folder / "runtime.log", self.root / "docs/release-config.json"]}
        for mutation in mutations:
            mutation()
            with self.assertRaises(RuntimeError):
                release.read_manifest("1.0.0")
            for path, original in originals.items():
                path.write_bytes(original)

    def test_installation_does_not_replace_physical_digest_approval(self):
        for change in ({"approve_physical": False}, {"approve_sha256": "f"*64}, {"approve_publish": "2.0.0"}, {"approve_destination": ["github"]}):
            with patch.object(release, "upload_github") as github, patch.object(release, "upload_store") as store, patch.object(release, "clean_tree"):
                with self.assertRaises(RuntimeError):
                    release.publish(self.args(**change))
                github.assert_not_called()
                store.assert_not_called()

    def test_changed_source_stops_before_any_upload(self):
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="different-commit"), patch.object(release, "upload_github") as github:
            with self.assertRaisesRegex(RuntimeError, "Source changed"):
                release.publish(self.args())
            github.assert_not_called()

    def test_publication_uses_exact_artifact_and_never_builds_or_auths_directly(self):
        seen = []
        def upload(folder, state):
            seen.append((folder / common.ARTIFACT).read_bytes())
            self.assertEqual(common.digest(seen[-1]), state["artifact"]["sha256"])
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit") as run, patch.object(release, "upload_github", side_effect=upload), patch.object(release, "upload_store", side_effect=upload), patch.object(release, "verify"), patch.object(release, "record_docs"):
            state = release.publish(self.args())
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0], seen[1])
        self.assertEqual(state["approval"]["sha256"], self.artifact["sha256"])
        self.assertEqual([call.args for call in run.call_args_list], [("git", "rev-parse", "HEAD")])

    @staticmethod
    def sdk_double(upload):
        class Publisher:
            @classmethod
            def _post_with_wait_bar(cls, url, headers, data, files, timeout, label):
                raise AssertionError("This SDK double does not send HTTP")
            @classmethod
            def _upload_release(cls, api_base, app_id, firebase_id_token, pbw_path, version, release_notes, is_published, gif_paths, screenshot_paths, replace_screenshots=False):
                return upload(api_base, app_id, firebase_id_token, pbw_path, version, release_notes, is_published, gif_paths, screenshot_paths, replace_screenshots)
        return Publisher

    def store_app_with_history(self):
        app = self.app()
        app["description"] = self.state["description"]
        app["assets"][0]["description"] = self.state["description"]
        prior = {"id": "prior-release", "version": "0.9.0", "pbw_url": "/prior.pbw", "is_published": True, "release_notes": "Prior reviewed notes"}
        app["releases"] = [prior]
        candidate = {"id": "new-release", "version": self.state["version"], "pbw_url": "/candidate.pbw", "is_published": True, "release_notes": self.state["notes"]}
        return app, candidate

    def test_deleted_prior_release_cannot_be_rebaselined_on_retry(self):
        before, candidate = self.store_app_with_history()
        changed = copy.deepcopy(before)
        changed["releases"] = [candidate]
        upload = Mock()
        module = types.SimpleNamespace(PublishCommand=self.sdk_double(upload))
        with patch.dict(sys.modules, {"pebble_tool.commands.publish": module}), patch.object(release, "dashboard_session", return_value=(Mock(), "fixture-token")), patch.object(release, "dashboard_app", side_effect=[before, changed]):
            with self.assertRaisesRegex(RuntimeError, "previous release"):
                release.upload_store(self.folder, self.state)
        saved = json.loads((self.folder / "manifest.json").read_text())
        original_baseline = copy.deepcopy(saved["store_preservation"])
        self.assertEqual(set(original_baseline["history"]), {"prior-release"})
        with patch.dict(sys.modules, {"pebble_tool.commands.publish": module}), patch.object(release, "dashboard_session", return_value=(Mock(), "fixture-token")), patch.object(release, "dashboard_app", return_value=changed), patch.object(release, "get_public") as public:
            with self.assertRaisesRegex(RuntimeError, "previous release"):
                release.upload_store(self.folder, saved)
        public.assert_not_called()
        upload.assert_called_once()
        self.assertEqual(json.loads((self.folder / "manifest.json").read_text())["store_preservation"], original_baseline)

    def test_changed_artwork_cannot_be_rebaselined_and_restoration_allows_retry(self):
        before, candidate = self.store_app_with_history()
        changed = copy.deepcopy(before)
        changed["releases"].append(candidate)
        changed["assets"][0]["screenshots"] = []
        session, upload = Mock(), Mock()
        module = types.SimpleNamespace(PublishCommand=self.sdk_double(upload))
        with patch.dict(sys.modules, {"pebble_tool.commands.publish": module}), patch.object(release, "dashboard_session", return_value=(session, "fixture-token")), patch.object(release, "dashboard_app", side_effect=[before, changed]):
            with self.assertRaisesRegex(RuntimeError, "unrelated"):
                release.upload_store(self.folder, self.state)
        saved = json.loads((self.folder / "manifest.json").read_text())
        with patch.dict(sys.modules, {"pebble_tool.commands.publish": module}), patch.object(release, "dashboard_session", return_value=(session, "fixture-token")), patch.object(release, "dashboard_app", return_value=changed):
            with self.assertRaisesRegex(RuntimeError, "unrelated"):
                release.upload_store(self.folder, saved)
        restored = copy.deepcopy(before)
        restored["releases"].append(candidate)
        with patch.dict(sys.modules, {"pebble_tool.commands.publish": module}), patch.object(release, "dashboard_session", return_value=(session, "fixture-token")), patch.object(release, "dashboard_app", return_value=restored), patch.object(release, "get_public", return_value=Response(content=(self.folder / common.ARTIFACT).read_bytes())):
            release.upload_store(self.folder, saved)
        upload.assert_called_once()  # Matching candidate is reused after restoration.
        session.patch.assert_not_called()
        self.assertEqual(saved["store_preservation"]["metadata"], release.preserved_fields(before))

    def test_original_baseline_is_durable_before_upload_and_description_patch(self):
        before, candidate = self.store_app_with_history()
        before["description"] = "Old description"
        after_upload = copy.deepcopy(before)
        after_upload["releases"].append(candidate)
        after = copy.deepcopy(after_upload)
        after["description"] = self.state["description"]
        after["assets"][0]["description"] = self.state["description"]
        observed = []
        def assert_saved(*args, **kwargs):
            saved = json.loads((self.folder / "manifest.json").read_text())
            baseline = saved["store_preservation"]
            self.assertEqual(baseline["metadata"], release.preserved_fields(before))
            self.assertEqual(baseline["history"], release.prior_release_history(before))
            self.assertEqual(baseline["artifact_sha256"], self.artifact["sha256"])
            observed.append(baseline)
            return Response()
        session = Mock()
        session.patch.side_effect = assert_saved
        module = types.SimpleNamespace(PublishCommand=self.sdk_double(assert_saved))
        with patch.dict(sys.modules, {"pebble_tool.commands.publish": module}), patch.object(release, "dashboard_session", return_value=(session, "fixture-token")), patch.object(release, "dashboard_app", side_effect=[before, after_upload, after]):
            release.upload_store(self.folder, self.state)
        self.assertEqual(len(observed), 2)
        self.assertEqual(observed[0], observed[1])

    def test_baseline_save_failure_prevents_mutation_and_keeps_ram_uncommitted(self):
        before, _ = self.store_app_with_history()
        session, upload = Mock(), Mock()
        module = types.SimpleNamespace(PublishCommand=self.sdk_double(upload))
        with patch.dict(sys.modules, {"pebble_tool.commands.publish": module}), patch.object(release, "dashboard_session", return_value=(session, "fixture-token")), patch.object(release, "dashboard_app", return_value=before), patch.object(release, "save", side_effect=OSError("Fixture journal unavailable")):
            with self.assertRaisesRegex(OSError, "journal unavailable"):
                release.upload_store(self.folder, self.state)
        self.assertNotIn("store_preservation", self.state)
        upload.assert_not_called()
        session.patch.assert_not_called()

    def test_missing_or_wrong_candidate_baseline_never_resets_after_an_attempt(self):
        before, _ = self.store_app_with_history()
        self.state["status"]["appstore"] = {"state": "upload stopped; inspect remote before retry"}
        with self.assertRaisesRegex(RuntimeError, "Missing pre-mutation"):
            release.store_preservation(self.folder, self.state, before, self.config)
        self.state["status"] = {}
        baseline = release.store_preservation(self.folder, self.state, before, self.config)
        for changed in (None, dict(baseline, app_id="b"*24), dict(baseline, artifact_sha256="f"*64), dict(baseline, version="1.0.1"), dict(baseline, history=[])):
            with self.subTest(baseline=changed):
                self.state["store_preservation"] = changed
                with self.assertRaisesRegex(RuntimeError, "baseline"):
                    release.store_preservation(self.folder, self.state, before, self.config)

    @unittest.skipUnless((Path.home() / ".local/share/uv/tools/pebble-tool/bin/python").is_file(), "Installed SDK Python unavailable")
    def test_actual_sdk_upload_adapter_rejects_redirects_and_preserves_exact_pbw(self):
        script = r'''
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,sys.argv[1]);sys.path.insert(1,sys.argv[2])
import release
from pebble_tool.commands.publish import PublishCommand
import requests
config={"appstore_api":"https://appstore-api.repebble.com","store_app_id":"a"*24}
publisher=release.guarded_store_publisher(PublishCommand,config)
fixture=Path(sys.argv[3]);expected=fixture.read_bytes()
url=config["appstore_api"]+"/api/dashboard/apps/"+config["store_app_id"]+"/releases"
for code in (301,302,303,307,308,200):
    response=SimpleNamespace(status_code=code,json=lambda:{"fixture":"uploaded"},text="fixture",close=Mock())
    def post(actual_url,**kwargs):
        assert actual_url==url and kwargs["allow_redirects"] is False
        assert kwargs["headers"]=={"Authorization":"Bearer fixture-token"}
        assert kwargs["timeout"]==300
        assert kwargs["data"]["replaceScreenshots"]=="false"
        assert len(kwargs["files"])==1 and kwargs["files"][0][0]=="pbwFile"
        assert kwargs["files"][0][1][1].read()==expected
        return response
    mocked=Mock(side_effect=post)
    with patch.object(requests,"post",mocked):
        try:
            result=publisher._upload_release(api_base=config["appstore_api"],app_id=config["store_app_id"],firebase_id_token="fixture-token",pbw_path=str(fixture),version="1.0.1",release_notes="Fixture notes",is_published=True,gif_paths=[],screenshot_paths=[],replace_screenshots=False)
        except RuntimeError as error:
            assert code!=200 and "redirect rejected" in str(error)
            response.close.assert_called_once()
        else:
            assert code==200 and result=={"fixture":"uploaded"}
        mocked.assert_called_once()  # No redirected second destination/token.
assert fixture.read_bytes()==expected
print("PASS actual installed SDK adapter: all redirects refused, token sent only once to fixed host, exact PBW unchanged")
'''
        sdk_python = Path.home() / ".local/share/uv/tools/pebble-tool/bin/python"
        result = subprocess.run([str(sdk_python), "-B", "-c", script, str(Path(release.__file__).resolve().parent), str(ROOT / "scripts"), str(self.folder / common.ARTIFACT)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_store_request_preserves_android_ios_unknown_fields_and_artwork(self):
        before = self.app()
        after_upload = copy.deepcopy(before)
        after = copy.deepcopy(before)
        after["description"] = self.state["description"]
        after["assets"][0]["description"] = self.state["description"]
        session = Mock()
        session.patch.return_value = Response()
        upload_calls = []
        class Publisher:
            @classmethod
            def _post_with_wait_bar(cls, url, headers, data, files, timeout, label):
                raise AssertionError("This request-preservation double never sends HTTP")
            @classmethod
            def _upload_release(cls, api_base, app_id, firebase_id_token, pbw_path, version, release_notes, is_published, gif_paths, screenshot_paths, replace_screenshots=False):
                upload_calls.append({"path": pbw_path, "screenshots": screenshot_paths, "gifs": gif_paths, "replace": replace_screenshots})
        modules = {"pebble_tool": types.ModuleType("pebble_tool"), "pebble_tool.commands": types.ModuleType("pebble_tool.commands"), "pebble_tool.commands.publish": types.SimpleNamespace(PublishCommand=Publisher)}
        with patch.dict(sys.modules, modules), patch.object(release, "dashboard_session", return_value=(session, "fixture-token-never-saved")), patch.object(release, "dashboard_app", side_effect=[before, after_upload, after]):
            release.upload_store(self.folder, self.state)
        self.assertEqual(session.patch.call_args.kwargs["files"], {"description": (None, "Fixture description")})
        self.assertEqual(upload_calls, [{"path": str(self.folder / common.ARTIFACT), "screenshots": [], "gifs": [], "replace": False}])
        self.assertEqual(release.preserved_fields(before), release.preserved_fields(after))
        self.assertNotIn("fixture-token", (self.folder / "manifest.json").read_text())

    def test_full_form_contract_missing_companion_binding_fails_before_upload(self):
        config = dict(self.config, listing_patch_contract="dashboard-form-v1", listing_form_fields={"description": "description", "title": "title", "source": "source", "website": "website", "visible": "visible", "category": "category_id"})
        with self.assertRaisesRegex(RuntimeError, "companion"):
            release.listing_fields(self.app(), self.state["description"], config)
        fields = dict(config["listing_form_fields"])
        for platform in ("android", "ios"):
            for key in ("name", "url", "required"):
                fields[platform+key] = "companion_apps."+platform+"."+key
        config["listing_form_fields"] = fields
        result = release.listing_fields(self.app(), self.state["description"], config)
        self.assertEqual(result["iosrequired"], "true")
        self.assertEqual(result["androidname"], "Fixture Android")

    def test_unrelated_metadata_change_stops_without_second_patch(self):
        before = self.app()
        changed = copy.deepcopy(before)
        changed["assets"][0]["screenshots"] = []
        session = Mock()
        existing = {"version": "1.0.0", "is_published": True, "pbw_url": "/fixture.pbw"}
        before["releases"] = [existing]
        changed["releases"] = [existing]
        with patch.object(release, "dashboard_session", return_value=(session, "fixture-token")), patch.object(release, "dashboard_app", side_effect=[before, changed]), patch.object(release, "get_public", return_value=Response(content=(self.folder / common.ARTIFACT).read_bytes())), patch.dict(sys.modules, {"pebble_tool.commands.publish": types.SimpleNamespace(PublishCommand=object)}):
            with self.assertRaisesRegex(RuntimeError, "unrelated"):
                release.upload_store(self.folder, self.state)
        session.patch.assert_not_called()

    def test_partial_publication_failure_is_journaled_and_not_advertised(self):
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(release, "upload_github"), patch.object(release, "upload_store", side_effect=RuntimeError("fixture outage")), patch.object(release, "record_docs") as docs:
            with self.assertRaisesRegex(RuntimeError, "fixture outage"):
                release.publish(self.args())
        state = json.loads((self.folder / "manifest.json").read_text())
        self.assertEqual(state["status"]["github"]["state"], "uploaded; verification pending")
        self.assertEqual(state["status"]["appstore"]["state"], "upload stopped; inspect remote before retry")
        docs.assert_not_called()

    def test_verify_is_bounded_read_only_and_retains_partial_status(self):
        with patch.object(release, "verify_github", return_value={"fixture": "ok"}), patch.object(release, "verify_store", side_effect=RuntimeError("fixture propagation")), patch.object(release.time, "sleep") as sleep, patch.object(release, "upload_store") as upload:
            with self.assertRaisesRegex(RuntimeError, "partially live"):
                release.verify(self.folder, self.state, 2)
        self.assertEqual(self.state["status"]["github"]["state"], "verified")
        self.assertEqual(self.state["status"]["appstore"]["state"], "pending verification")
        sleep.assert_called_once_with(20)
        upload.assert_not_called()
        with self.assertRaises(RuntimeError):
            release.verify(self.folder, self.state, 6)

    def test_store_verifies_general_emery_and_canonical_surfaces_and_hashes(self):
        payload = (self.folder / common.ARTIFACT).read_bytes()
        app = self.app()
        app["description"] = self.state["description"]
        app["assets"][0]["description"] = self.state["description"]
        app["latest_release"] = {"version": "1.0.0", "is_published": True, "release_notes": self.state["notes"], "pbw_url": "/fixture.pbw"}
        catalog = {"data": [{"id": self.config["store_app_id"], "uuid": common.UUID, "visible": True, "description": self.state["description"], **catalog_platform_fixture(self.state["description"]), "latest_release": {"version": "1.0.0", "release_notes": self.state["notes"], "pbw_file": "/fixture.pbw"}}]}
        urls = []
        def get(url, max_bytes=2097152):
            urls.append(url)
            if "/api/v1/" in url:
                return Response(data=catalog)
            if url.endswith(".pbw"):
                return Response(content=payload)
            return Response(text="Fixture description /fixture.pbw 1.0.0 Fixture release notes")
        with patch.object(release, "dashboard_session", return_value=(Mock(), "fixture-token")), patch.object(release, "dashboard_app", return_value=app), patch.object(release, "get_public", side_effect=get):
            result = release.verify_store(self.state)
        self.assertEqual(result["catalog_emery"], "verified")
        self.assertTrue(any("?hardware=emery" in url for url in urls))
        self.assertTrue(any(url.endswith("/changelog") for url in urls))
        self.assertEqual(sum(url.endswith(".pbw") for url in urls), 3)

    def test_draft_or_unverified_destination_is_not_documented(self):
        self.state["status"] = {"github": {"state": "verified"}, "appstore": {"state": "pending verification"}}
        with self.assertRaisesRegex(RuntimeError, "unverified"):
            release.record_docs(self.folder, self.state)
        self.assertFalse((self.root / "docs/releases/latest-status.json").exists())

    def test_documentation_push_failure_journals_commit_and_retry_pushes_without_recommit(self):
        self.state["status"] = {destination: {"state": "verified"} for destination in self.state["destinations"]}
        release.save(self.folder, self.state)
        head = "fixture-commit"
        commits, pushes = [], []

        def run(*args, capture=False):
            nonlocal head
            if args == ("git", "rev-parse", "HEAD"):
                return head
            if args == ("git", "diff", "--cached", "--name-only"):
                return "README.md\ndocs/releases/latest-status.json\n" if not commits else ""
            if args[:2] == ("git", "commit"):
                commits.append(args)
                head = "fixture-documentation-commit"
            if args[:2] == ("git", "push"):
                pushes.append(args)
                # The exact new commit must be recorded before either push.
                journal = json.loads((self.folder / "manifest.json").read_text())
                self.assertEqual(journal["documentation_commit"], head)
                self.assertEqual(journal["commit"], "fixture-commit")
                self.assertEqual(journal["artifact"], self.artifact)
                if len(pushes) == 1:
                    raise RuntimeError("Fixture documentation push outage")
            return ""

        with patch.object(release, "clean_tree"), patch.object(release, "run", side_effect=run), patch.object(release, "verify"), patch.object(release, "upload_github") as github, patch.object(release, "upload_store") as store:
            with self.assertRaisesRegex(RuntimeError, "push outage"):
                release.publish(self.args())
            stopped = json.loads((self.folder / "manifest.json").read_text())
            self.assertEqual(stopped["documentation_commit"], head)
            self.assertEqual(stopped["approval"]["sha256"], self.artifact["sha256"])
            resumed = release.publish(self.args())
            github.assert_not_called()
            store.assert_not_called()
        self.assertEqual(len(commits), 1, "Retry must reuse the already authorized documentation commit")
        self.assertEqual(pushes, [("git", "push", "origin", "main")] * 2)
        self.assertEqual(resumed["documentation_commit"], "fixture-documentation-commit")
        self.assertEqual(common.inspect_pbw(self.folder / common.ARTIFACT, "1.0.0"), self.artifact)

    def test_runtime_requires_actual_bound_log_not_linker_heap(self):
        report = copy.deepcopy(self.audit)
        report["runtime"] = None
        with self.assertRaisesRegex(RuntimeError, "Runtime measurements"):
            audit.validate_audit(report, self.folder / common.ARTIFACT, "1.0.0", self.root)
        report = copy.deepcopy(self.audit)
        report["metrics"]["measured_free_heap"] = 96000
        with self.assertRaisesRegex(RuntimeError, "raw runtime log"):
            audit.validate_audit(report, self.folder / common.ARTIFACT, "1.0.0", self.root)
        budgets = json.loads((self.root / "tests/build-budgets.json").read_text())
        with self.assertRaisesRegex(RuntimeError, "headroom"):
            audit.check_budgets(dict(self.metrics, measured_free_heap=20000), budgets, True)

    def test_runtime_markers_require_current_complete_numeric_fields(self):
        original = (self.folder / "runtime.log").read_text()
        replacements = [
            ("launch", "READY storage=1048576 heap=40000 message=0", value) for value in (
                "READY init_ms=100 heap=40000",
                "READY storage=unknown heap=40000 message=0",
                "READY storage=1048576 heap=bad message=0",
                "READY storage=1048576 heap=40000",
                "READY storage=1048576 heap=40000 message=unknown",
                "NOTREADY storage=1048576 heap=40000 message=0",
                "READY storage=1048576 heap=40000 message=0 extra",
            )
        ] + [
            ("navigation", "UI screen1 heap39000", value) for value in (
                "UI screen1 render_ms10 heap39000",
                "UI screen1",
                "UI screen1 heapunknown",
                "NOTUI screen1 heap39000",
                "UI screen1 heap39000 extra",
            )
        ] + [
            ("update-transfer", "Update commit session1 status3 heap38000", value) for value in (
                "Update commit session1 status2 heap38000",
                "Update commit session1 status3",
                "Update commit session1 status3 heapunknown",
                "Update commit session1 status3 heap38000 extra",
            )
        ]
        for scenario, old, new in replacements:
            with self.subTest(scenario=scenario, marker=new):
                report = copy.deepcopy(self.audit)
                evidence = self.folder / "runtime.log"
                evidence.write_text(original.replace(old, new))
                report["runtime"]["evidence_sha256"] = common.digest(evidence.read_bytes())
                receipt_path = Path(report["runtime"]["install_receipt_path"])
                receipt = json.loads(receipt_path.read_text())
                receipt["log_sha256"] = report["runtime"]["evidence_sha256"]
                receipt_path.write_text(json.dumps(receipt))
                with self.assertRaisesRegex(RuntimeError, "runtime scenario: " + scenario):
                    audit.validate_audit(report, self.folder / common.ARTIFACT, "1.0.0", self.root)

    def test_budget_and_tool_output_failures_are_meaningful(self):
        output = "Total size of resources: 30000\nTotal footprint in RAM: 35000\nFree RAM available (heap): 96000\n"
        self.assertEqual(audit.parse_metrics(output)["static_ram"], 35000)
        self.assertEqual(audit.parse_metrics(output)["image_bytes"], 35000)
        with self.assertRaisesRegex(RuntimeError, "Missing/ambiguous"):
            audit.parse_metrics("build succeeded, no metric")
        budgets = json.loads((self.root / "tests/build-budgets.json").read_text())
        for field, value in (("native_binary", 104858), ("static_ram", 104858), ("resources", 209716), ("timetable", 24577)):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                audit.check_budgets(dict(self.metrics, **{field: value}), budgets)

    def test_image_size_budget_keeps_sdk_headroom(self):
        budgets = json.loads((self.root / "tests/build-budgets.json").read_text())
        self.assertEqual(budgets["sdk_image_limit_bytes"], 65535)
        self.assertLessEqual(budgets["max_image_bytes"], budgets["sdk_image_limit_bytes"] + 1 - 4096)
        audit.check_budgets(dict(self.metrics, image_bytes=budgets["max_image_bytes"]), budgets)
        for value, message in ((budgets["max_image_bytes"] + 1, "4 KiB headroom"), (65535, "4 KiB headroom"), (65536, "SDK hard limit")):
            with self.subTest(image_bytes=value), self.assertRaisesRegex(RuntimeError, message):
                audit.check_budgets(dict(self.metrics, image_bytes=value), budgets)
        for metrics in ({k: v for k, v in self.metrics.items() if k != "image_bytes"}, dict(self.metrics, image_bytes=None)):
            with self.assertRaisesRegex(RuntimeError, "not measured"):
                audit.check_budgets(metrics, budgets)

    def test_source_change_between_build_and_freeze_is_rejected(self):
        args = self.preparation()
        (self.root / "src/fixture.c").write_text("/* Changed synthetic source */\n")
        with patch.object(release, "clean_tree"), patch.object(release, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "source changed"):
                release.prepare(args)
        run.assert_not_called()

    def test_build_input_fingerprint_allows_later_reports_but_binds_code_and_tests(self):
        before = common.source_fingerprint(self.root)
        (self.root / "README.md").write_text("A later verified status report\n")
        (self.root / "docs/releases/latest-status.json").write_text("{}\n")
        self.assertEqual(common.source_fingerprint(self.root), before)
        audit.validate_audit(self.audit, self.folder / common.ARTIFACT, "1.0.0", self.root)
        for directory in ("src", "resources", "data", "tools", "scripts", "tests"):
            path = self.root / directory / "new-fixture-input.txt"
            path.parent.mkdir(exist_ok=True)
            path.write_text("Synthetic build/runtime/test input\n")
            self.assertNotEqual(common.source_fingerprint(self.root), before)
            path.unlink()
        for filename in ("package.json", "package-lock.json", "wscript"):
            path = self.root / filename
            path.write_text("Synthetic build input\n")
            self.assertNotEqual(common.source_fingerprint(self.root), before)
            path.unlink()

    def test_capture_installs_only_the_audited_artifact_and_binds_fresh_log(self):
        self.preparation()
        output = self.root / "artifacts/capture-fixture.log"
        process = Mock()
        process.poll.return_value = 0
        def start(command, cwd, stdout, stderr, env):
            self.assertEqual(env["PYTHONUNBUFFERED"], "1")
            stdout.write(b"SYNTHETIC TEST ONLY INIT entered\nREADY storage=1048576 heap=38000 message=0\n")
            return process
        with patch.object(capture.subprocess, "Popen", side_effect=start) as install:
            receipt = capture.capture(output, "emulator", 15, self.root)
        self.assertEqual(receipt["artifact"], self.artifact)
        self.assertEqual(receipt["log_sha256"], common.digest(output.read_bytes()))
        self.assertEqual(receipt["command"], ["pebble", "install", "--emulator", "emery", "--logs", str(self.root / "build" / common.ARTIFACT)])
        self.assertEqual(len(install.call_args_list), 1)
        self.assertTrue(output.with_suffix(".log.install.json").is_file())
        with patch.object(capture.subprocess, "Popen") as repeat:
            with self.assertRaisesRegex(RuntimeError, "overwrite"):
                capture.capture(output, "emulator", 15, self.root)
            repeat.assert_not_called()

    def test_capture_failed_install_never_seals_a_receipt(self):
        self.preparation()
        output = self.root / "artifacts/capture-failed-fixture.log"
        process = Mock()
        process.poll.return_value = 1
        with patch.object(capture.subprocess, "Popen", return_value=process):
            with self.assertRaisesRegex(RuntimeError, "command failed"):
                capture.capture(output, "emulator", 15, self.root)
        self.assertFalse(output.with_suffix(".log.install.json").exists())

    def test_deleted_or_changed_prior_release_is_rejected(self):
        before = self.app()
        before["releases"] = [{"id": "old", "version": "0.9.0", "pbw_url": "/old.pbw", "is_published": True, "release_notes": "Old fixture notes"}]
        after = copy.deepcopy(before)
        after["releases"].append({"id": "new", "version": "1.0.0"})
        release.require_prior_history(before, after)
        for changed in ({"releases": []}, {"releases": [dict(before["releases"][0], pbw_url="/different.pbw")]}, {"releases": [dict(before["releases"][0], is_published=False)]}):
            with self.assertRaisesRegex(RuntimeError, "previous release"):
                release.require_prior_history(before, dict(after, **changed))

    def test_newer_github_release_is_rejected_before_push_tag_or_latest(self):
        releases = json.dumps([{"tag_name": "v2.0.0", "draft": False, "prerelease": False}])
        with patch.object(release, "run", return_value=releases) as run:
            with self.assertRaisesRegex(RuntimeError, "newer/unknown"):
                release.upload_github(self.folder, self.state)
        self.assertEqual(len(run.call_args_list), 1)
        self.assertEqual(run.call_args.args[:2], ("gh", "api"))

    def test_newer_store_release_is_rejected_before_upload_or_patch(self):
        app = self.app()
        app["releases"] = [{"version": "2.0.0"}]
        session = Mock()
        with patch.dict(sys.modules, {"pebble_tool.commands.publish": types.SimpleNamespace(PublishCommand=object)}), patch.object(release, "dashboard_session", return_value=(session, "fixture-token")), patch.object(release, "dashboard_app", return_value=app):
            with self.assertRaisesRegex(RuntimeError, "newer store"):
                release.upload_store(self.folder, self.state)
        session.patch.assert_not_called()

    def test_auth_token_post_cannot_follow_a_redirect(self):
        session = Mock()
        session.headers = {}
        session.post.return_value = types.SimpleNamespace(status_code=307)
        request_module = types.SimpleNamespace(Session=lambda: session)
        account = types.SimpleNamespace(is_logged_in=True, get_access_token=lambda: "synthetic-test-token")
        with patch.dict(sys.modules, {"requests": request_module, "pebble_tool.account": types.SimpleNamespace(get_account=lambda **kwargs: account)}):
            with self.assertRaisesRegex(RuntimeError, "Auth redirect"):
                release.dashboard_session(self.config)
        self.assertFalse(session.post.call_args.kwargs["allow_redirects"])

    def test_public_fetch_enforces_size_deadline_and_https(self):
        class Raw:
            def __init__(self, chunks):
                self.chunks = iter(chunks)
            def read1(self, size, decode_content=False):
                return next(self.chunks, b"")
        def response(chunks, length=None):
            return types.SimpleNamespace(status_code=200, headers={} if length is None else {"Content-Length": str(length)}, raw=Raw(chunks), raise_for_status=lambda: None, close=Mock())
        for mocked in (response([b"abcdef"]), response([], 6)):
            request_module = types.SimpleNamespace(get=Mock(return_value=mocked))
            with patch.dict(sys.modules, {"requests": request_module}):
                with self.assertRaisesRegex(RuntimeError, "budget"):
                    release.get_public("https://example.invalid/fixture", 5)
            mocked.close.assert_called()
        with patch.dict(sys.modules, {"requests": types.SimpleNamespace(get=Mock(return_value=response([b"a"]))) }), patch.object(release.time, "monotonic", side_effect=[0, 61]):
            with self.assertRaisesRegex(RuntimeError, "deadline"):
                release.get_public("https://example.invalid/fixture", 5)
        with self.assertRaisesRegex(RuntimeError, "HTTPS"):
            release.get_public("http://example.invalid/fixture")


if __name__ == "__main__":
    unittest.main()
