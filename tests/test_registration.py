"""Offline first-registration journals. No Dashboard UI, creation or Git action."""
import argparse
import copy
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import Mock, patch
import zlib

import test_release as fixtures
release, common = fixtures.release, fixtures.common
registration = release.registration


def png(width, height):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress((b"\0" + bytes(width * 4)) * height)) + chunk(b"IEND", b"")


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ReleaseTests()
        self.fixture.setUp()
        self.root, self.folder = self.fixture.root, self.fixture.folder
        self.state = copy.deepcopy(self.fixture.state)
        self.config = dict(self.state["config"], store_app_id=None, store_listing_url=None, listing_patch_contract=None)
        self.state.update(config=self.config, store_mode="create-or-resume", registration={"phase": "planned", "identity_verified": False, "listing_confirmed": False})
        common.atomic_json(self.root / "docs/release-config.json", self.config)
        self.app_id = "b" * 24
        directory = self.root / "docs/releases/assets"
        directory.mkdir()
        assets = []
        for role, dimensions in (("iconSmall", (80, 80)), ("iconLarge", (144, 144)), ("banner", (720, 320)), ("screenshot", (200, 228))):
            path = directory / (role + ".png")
            path.write_bytes(png(*dimensions))
            entry = {"role": role, "path": path.relative_to(self.root).as_posix()}
            if role in ("banner", "screenshot"):
                entry["platform"] = "emery"
            assets.append(entry)
        value = {"schema": 1, "uuid": common.UUID, "metadata": {"title": "KasugaBus", "type": "watchapp", "description": self.state["description"], "source": "https://github.com/fixture-owner/kasugabus", "website": None, "category": "daily", "visibility": "listed", "companion_android": None, "companion_ios": None}, "assets": assets}
        self.listing = self.root / "docs/releases/listing.json"
        common.atomic_json(self.listing, value)
        self.state["listing"] = registration.freeze_listing(registration.validate_listing(self.listing, self.root), self.folder, self.root)
        release.save(self.folder, self.state)

    def tearDown(self):
        self.fixture.tearDown()

    def args(self, **changes):
        return self.fixture.args(**changes)

    def app(self):
        value = self.fixture.app()
        value.update(id=self.app_id, description=self.state["description"], source="https://github.com/" + self.config["github_repo"], type="watchapp", supported_platforms=["emery"])
        return value

    def session(self, app=None):
        result = Mock()
        result.get.return_value = fixtures.Response({"app": app or self.app()})
        return result

    def begin(self):
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=None):
            return release.begin_registration(self.args())

    def record_args(self, confirm=False):
        return argparse.Namespace(version="1.0.0", app_id=self.app_id, confirm_listing=confirm, evidence=self.evidence() if confirm else None)

    def evidence(self, confirmed=True):
        path = self.folder / "observed-listing.json"
        frozen = registration.frozen_listing(self.folder, self.state["listing"])
        assets = [{key: item[key] for key in ("role", "sha256", "platform") if key in item} for item in frozen["assets"]]
        common.atomic_json(path, {"schema": 1, "confirmed": confirmed, "app_id": self.app_id, "uuid": common.UUID, "listing_sha256": self.state["listing"]["sha256"], "artifact_sha256": self.state["artifact"]["sha256"], "metadata": frozen["metadata"], "assets": assets, "dashboard_readback": {"app_id": self.app_id, "uuid": common.UUID, "source": frozen["metadata"]["source"], "type": "watchapp", "platforms": ["emery"]}})
        return path

    def test_first_candidate_freezes_all_assets_with_null_id_without_creation(self):
        args = self.fixture.preparation()
        common.atomic_json(self.root / "docs/release-config.json", self.config)
        args.store_mode, args.listing = "create-or-resume", self.listing
        args.destination = ["github", "appstore"]
        def run(*command, capture=False):
            return "[]" if command[:2] == ("gh", "api") else "fixture-commit"
        with patch.object(release, "clean_tree"), patch.object(release, "run", side_effect=run), patch.object(registration, "discover_owned", return_value=None), patch.object(release, "dashboard_session") as auth:
            result = release.prepare(args)
        auth.assert_not_called()
        self.assertEqual(result["registration"]["phase"], "planned")
        self.assertIsNone(result["config"]["store_app_id"])
        self.assertEqual(len(registration.frozen_listing(self.folder, result["listing"])["assets"]), 4)

    def test_begin_requires_exact_physical_and_destination_approval_before_lookup(self):
        for change in ({"approve_physical": False}, {"approve_sha256": "f" * 64}, {"approve_destination": ["github"]}):
            with patch.object(registration, "discover_owned") as discover, self.assertRaises(RuntimeError):
                release.begin_registration(self.args(**change))
            discover.assert_not_called()
        self.assertEqual(json.loads((self.folder / "manifest.json").read_text())["registration"]["phase"], "planned")

    def test_intent_is_durable_and_uncertain_repeat_never_authorizes_second_submit(self):
        result = self.begin()
        self.assertEqual(result["registration"]["phase"], "creation in flight")
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=None), self.assertRaisesRegex(RuntimeError, "Do not submit again"):
            release.begin_registration(self.args())
        self.assertEqual(json.loads((self.folder / "manifest.json").read_text())["registration"]["phase"], "creation uncertain; reconcile only")

    def test_receipt_precedes_lookup_failure_and_config_write(self):
        self.begin()
        def failed_lookup(config):
            saved = json.loads((self.folder / "manifest.json").read_text())["registration"]
            self.assertEqual(saved["app_id"], self.app_id)
            self.assertEqual(saved["listing_url"], self.config["public_store"] + "/" + self.app_id)
            self.assertFalse(saved["identity_verified"])
            self.assertIsNone(json.loads((self.root / "docs/release-config.json").read_text())["store_app_id"])
            raise RuntimeError("Fixture verification crash")
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", side_effect=failed_lookup), self.assertRaisesRegex(RuntimeError, "verification crash"):
            release.record_registration(self.record_args())
        self.assertIsNone(json.loads((self.root / "docs/release-config.json").read_text())["store_app_id"])

    def test_lost_response_reconciles_owned_uuid_and_persists_identity_without_resubmission(self):
        self.begin()
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "dashboard_session", return_value=(self.session(), "test-token")):
            result = release.reconcile_registration(argparse.Namespace(version="1.0.0"))
        self.assertTrue(result["registration"]["identity_verified"])
        config = json.loads((self.root / "docs/release-config.json").read_text())
        self.assertEqual(config["store_app_id"], self.app_id)
        self.assertEqual(config["store_listing_url"], self.config["public_store"] + "/" + self.app_id)
        self.assertFalse(result["registration"]["listing_confirmed"])
        self.assertIsNone(result["config"]["store_app_id"], "Frozen configuration is not rewritten")

    def test_unknown_creation_without_uuid_match_stays_pending(self):
        self.begin()
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=None), self.assertRaisesRegex(RuntimeError, "never blindly repeat"):
            release.reconcile_registration(argparse.Namespace(version="1.0.0"))

    def test_existing_owned_uuid_is_adopted_instead_of_new_creation(self):
        self.config["listing_patch_contract"] = "dashboard-form-2026-10-01"
        self.state["config"] = self.config
        common.atomic_json(self.root / "docs/release-config.json", self.config)
        release.save(self.folder, self.state)
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "dashboard_session", return_value=(self.session(), "test-token")):
            result = release.begin_registration(self.args())
        self.assertEqual(result["registration"]["origin"], "existing UUID discovered")
        self.assertEqual(result["registration"]["app_id"], self.app_id)
        self.assertEqual(result["registration"]["kind"], "adopted-existing")
        self.assertTrue(result["registration"]["listing_confirmed"])
        self.assertFalse((self.folder / "listing-confirmation.json").exists())

    def test_wrong_dashboard_uuid_retains_unverified_receipt_without_config_change(self):
        self.begin()
        app = self.app()
        app["app_uuid"] = "incorrect-uuid"
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "dashboard_session", return_value=(self.session(app), "test-token")), self.assertRaisesRegex(RuntimeError, "registered app identity"):
            release.record_registration(self.record_args())
        saved = json.loads((self.folder / "manifest.json").read_text())
        self.assertEqual(saved["registration"]["app_id"], self.app_id)
        self.assertFalse(saved["registration"]["identity_verified"])
        self.assertIsNone(json.loads((self.root / "docs/release-config.json").read_text())["store_app_id"])

    def test_frozen_artwork_and_listing_mutation_rejected_before_begin(self):
        asset = self.folder / "listing-assets/00-iconSmall.png"
        original = asset.read_bytes()
        asset.write_bytes(original[:-1] + b"x")
        with patch.object(registration, "discover_owned") as discover, self.assertRaisesRegex(RuntimeError, "asset changed"):
            release.begin_registration(self.args())
        discover.assert_not_called()
        asset.write_bytes(original)
        (self.folder / "listing.json").write_text("{}")
        with self.assertRaisesRegex(RuntimeError, "metadata changed"):
            release.read_manifest("1.0.0")

    def test_partial_listing_cannot_publish_or_recreate_and_false_confirmation_keeps_id(self):
        self.begin()
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "dashboard_session", return_value=(self.session(), "test-token")):
            release.record_registration(self.record_args())
            with patch.object(release, "upload_github") as github, patch.object(release, "upload_store") as store, self.assertRaisesRegex(RuntimeError, "read-back"):
                release.publish(self.args())
            github.assert_not_called()
            store.assert_not_called()
            args = self.record_args(True)
            args.evidence = self.evidence(False)
            with self.assertRaisesRegex(RuntimeError, "does not confirm"):
                release.record_registration(args)
        self.assertEqual(json.loads((self.root / "docs/release-config.json").read_text())["store_app_id"], self.app_id)

    def test_same_initial_version_and_pbw_are_verified_without_duplicate_upload(self):
        self.begin()
        app = self.app()
        app["releases"] = [{"id": "initial", "version": "1.0.0", "is_published": True, "pbw_url": "/same.pbw", "release_notes": self.state["notes"]}]
        content = (self.folder / common.ARTIFACT).read_bytes()
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "dashboard_session", return_value=(self.session(app), "test-token")), patch.object(release, "get_public", return_value=fixtures.Response(content=content)):
            state = release.record_registration(self.record_args(True))
            publisher = Mock()
            import types
            with patch.dict(sys.modules, {"pebble_tool.commands.publish": types.SimpleNamespace(PublishCommand=publisher)}):
                release.upload_store(self.folder, state)
            publisher._upload_release.assert_not_called()

    def test_config_transition_accepts_only_receipt_bound_identity_and_same_source_head(self):
        self.root.joinpath(".git").mkdir()
        self.state["registration"].update(identity_verified=True, app_id=self.app_id, listing_url=self.config["public_store"] + "/" + self.app_id)
        transitioned = registration.transitioned_config(self.state)
        common.atomic_json(self.root / "docs/release-config.json", transitioned)
        def run(*args, capture=False):
            if args == ("git", "status", "--porcelain"):
                return " M docs/release-config.json\n"
            if args == ("git", "branch", "--show-current"):
                return "main"
            if args == ("git", "remote", "get-url", "origin"):
                return "https://github.com/" + self.config["github_repo"]
            if args == ("git", "rev-parse", "HEAD"):
                return "fixture-commit"
            return ""
        with patch.object(release, "run", side_effect=run):
            release.candidate_tree(self.state)
        altered = dict(transitioned, github_repo="wrong/repository")
        common.atomic_json(self.root / "docs/release-config.json", altered)
        with self.assertRaisesRegex(RuntimeError, "config changed"):
            release.candidate_tree(self.state)
        common.atomic_json(self.root / "docs/release-config.json", transitioned)
        with patch.object(release, "run", return_value=" M src/fixture.c\n"), self.assertRaisesRegex(RuntimeError, "intended changes"):
            release.candidate_tree(self.state)
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="unexpected-head"), self.assertRaisesRegex(RuntimeError, "Source changed"):
            release.candidate_tree(self.state)

    def test_owned_uuid_ambiguity_and_redirects_are_rejected(self):
        import types
        account = types.SimpleNamespace(is_logged_in=True, get_access_token=lambda: "test-token")
        response = fixtures.Response({"app_lookup": {"by_app_uuid": {common.UUID: self.app_id, common.UUID.upper(): "c" * 24}}})
        response.status_code = 200
        with patch.dict(sys.modules, {"requests": types.SimpleNamespace(get=Mock(return_value=response)), "pebble_tool.account": types.SimpleNamespace(get_account=lambda **kwargs: account)}), self.assertRaisesRegex(RuntimeError, "Multiple owned"):
            registration.discover_owned(self.config)
        response.status_code = 302
        with patch.dict(sys.modules, {"requests": types.SimpleNamespace(get=Mock(return_value=response)), "pebble_tool.account": types.SimpleNamespace(get_account=lambda **kwargs: account)}), self.assertRaisesRegex(RuntimeError, "redirect rejected"):
            registration.discover_owned(self.config)

    def test_native_asset_constraints_and_corrupt_png_are_rejected(self):
        value = json.loads(self.listing.read_text())
        value["assets"] = [entry for entry in value["assets"] if entry["role"] != "banner"]
        common.atomic_json(self.listing, value)
        with self.assertRaisesRegex(RuntimeError, "one banner"):
            registration.validate_listing(self.listing, self.root)
        with self.assertRaisesRegex(RuntimeError, "Corrupt"):
            registration.png_dimensions(png(80, 80)[:-1] + b"x")

    def test_assigned_id_survives_a_broken_local_artifact_before_network_checks(self):
        self.begin()
        (self.folder / common.ARTIFACT).write_bytes(b"broken after UI creation")
        with patch.object(registration, "discover_owned") as discover, self.assertRaises(Exception):
            release.record_registration(self.record_args())
        discover.assert_not_called()
        intent = json.loads(registration.intent_path(self.root).read_text())
        self.assertEqual(intent["app_id"], self.app_id)
        self.assertEqual(json.loads((self.folder / "manifest.json").read_text())["registration"]["app_id"], self.app_id)

    def test_older_uncertain_candidate_and_existing_config_never_authorize_new(self):
        old = self.root / ".release/0.9.0"
        old.mkdir()
        common.atomic_json(old / "manifest.json", {"version": "0.9.0", "config": {"uuid": common.UUID}, "registration": {"phase": "creation in flight"}})
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=None), self.assertRaisesRegex(RuntimeError, "Another candidate"):
            release.begin_registration(self.args())
        self.assertFalse(registration.intent_path(self.root).exists())
        self.state["config"]["store_app_id"] = self.app_id
        common.atomic_json(self.root / "docs/release-config.json", self.state["config"])
        release.save(self.folder, self.state)
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=None), self.assertRaisesRegex(RuntimeError, "Do not submit again"):
            release.begin_registration(self.args())

    def test_two_concurrent_intent_contenders_grant_only_one_submit_permission(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        barrier = threading.Barrier(2)
        def reserve():
            barrier.wait()
            try:
                registration.reserve_intent(self.root, self.state)
                return "granted"
            except RuntimeError:
                return "blocked"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: reserve(), range(2)))
        self.assertEqual(sorted(results), ["blocked", "granted"])
        self.assertEqual(json.loads(registration.intent_path(self.root).read_text())["phase"], "creation in flight")

    def test_failed_intent_fsync_never_returns_submit_permission(self):
        with patch.object(registration.os, "fsync", side_effect=OSError("Fixture fsync failure")), self.assertRaisesRegex(OSError, "fsync failure"):
            registration.reserve_intent(self.root, self.state)
        self.assertTrue(registration.intent_path(self.root).exists())
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            registration.reserve_intent(self.root, self.state)

    def test_wrong_repository_type_or_platform_is_retained_as_unverified_identity(self):
        self.begin()
        for changes in ({"source": "https://github.com/unrelated/repo"}, {"type": "watchface"}, {"supported_platforms": ["basalt"]}):
            app = dict(self.app(), **changes)
            with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "dashboard_session", return_value=(self.session(app), "test-token")), self.assertRaises(RuntimeError):
                release.record_registration(self.record_args())
            self.assertFalse(json.loads((self.folder / "manifest.json").read_text())["registration"]["identity_verified"])
            self.assertIsNone(json.loads((self.root / "docs/release-config.json").read_text())["store_app_id"])

    def test_matching_draft_keeps_identity_and_requires_review_on_same_listing(self):
        self.begin()
        app = self.app()
        app["releases"] = [{"version": "1.0.0", "is_published": False, "pbw_url": "/draft.pbw"}]
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "dashboard_session", return_value=(self.session(app), "test-token")), patch.object(release, "get_public", return_value=fixtures.Response(content=(self.folder / common.ARTIFACT).read_bytes())), self.assertRaisesRegex(RuntimeError, "same listing.*never use New"):
            release.record_registration(self.record_args())
        self.assertEqual(json.loads((self.root / "docs/release-config.json").read_text())["store_app_id"], self.app_id)
        self.assertEqual(json.loads((self.folder / "manifest.json").read_text())["registration"]["public_verification"], "pending")

    def test_discovery_checks_owned_collection_and_blocks_same_repo_uuid_conflicts(self):
        import types
        account = types.SimpleNamespace(is_logged_in=True, get_access_token=lambda: "test-token")
        response = fixtures.Response({"app_lookup": {"by_app_uuid": {}}})
        session = Mock()
        for apps in ([dict(self.app(), app_uuid="wrong-uuid")], [self.app()]):
            session.get.return_value = fixtures.Response({"apps": apps})
            with patch.dict(sys.modules, {"requests": types.SimpleNamespace(get=Mock(return_value=response)), "pebble_tool.account": types.SimpleNamespace(get_account=lambda **kwargs: account)}), patch.object(release, "dashboard_session", return_value=(session, "test-token")), self.assertRaises(RuntimeError):
                registration.discover_owned(self.config)
        session.get.return_value = fixtures.Response({"apps": [self.app()]})
        response.data = {"app_lookup": {"by_app_uuid": {common.UUID: self.app_id}}}
        with patch.dict(sys.modules, {"requests": types.SimpleNamespace(get=Mock(return_value=response)), "pebble_tool.account": types.SimpleNamespace(get_account=lambda **kwargs: account)}), patch.object(release, "dashboard_session", return_value=(session, "test-token")):
            self.assertEqual(registration.discover_owned(self.config), self.app_id)
        self.assertFalse(session.get.call_args.kwargs["allow_redirects"])

    def test_early_discovery_requires_no_candidate_or_approval_and_changes_no_config(self):
        before = (self.root / "docs/release-config.json").read_bytes()
        with patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "dashboard_session", return_value=(self.session(), "test-token")):
            result = release.discover_registration()
        self.assertEqual(result["app_id"], self.app_id)
        self.assertEqual(result["public_verification"], "not checked")
        self.assertEqual((self.root / "docs/release-config.json").read_bytes(), before)
        self.assertFalse(registration.intent_path(self.root).exists())

    def test_early_verified_adoption_saves_only_local_identity_and_never_creates(self):
        with patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "dashboard_session", return_value=(self.session(), "test-token")), patch.object(release, "run") as command:
            result = release.discover_registration(argparse.Namespace(save_match=True))
        self.assertEqual(json.loads((self.root / "docs/release-config.json").read_text()), dict(self.config, store_app_id=self.app_id, store_listing_url=result["listing_url"]))
        self.assertTrue(result["saved_locally"])
        self.assertEqual(result["public_verification"], "not checked")
        self.assertFalse(registration.intent_path(self.root).exists())
        command.assert_not_called()

    def test_save_match_routes_unresolved_own_creation_to_original_reconciliation(self):
        self.begin()
        before = (self.root / "docs/release-config.json").read_bytes()
        with patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "dashboard_session", return_value=(self.session(), "test-token")):
            release.discover_registration()
            with self.assertRaisesRegex(RuntimeError, "reconcile-registration 1.0.0.*original candidate"):
                release.discover_registration(argparse.Namespace(save_match=True))
        self.assertEqual((self.root / "docs/release-config.json").read_bytes(), before)
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "dashboard_session", return_value=(self.session(), "test-token")):
            state = release.reconcile_registration(argparse.Namespace(version="1.0.0"))
        self.assertTrue(state["registration"]["identity_verified"])
        self.assertFalse(state["registration"]["listing_confirmed"])

    def test_prepare_found_listing_routes_to_existing_mode_before_freeze_or_install(self):
        args = self.fixture.preparation()
        common.atomic_json(self.root / "docs/release-config.json", self.config)
        args.store_mode, args.listing, args.destination = "create-or-resume", self.listing, ["github", "appstore"]
        with patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "run") as command, patch.object(release, "clean_tree") as tree, self.assertRaisesRegex(RuntimeError, "save-match.*existing mode"):
            release.prepare(args)
        command.assert_not_called()
        tree.assert_not_called()
        self.assertFalse(self.folder.exists())

    def test_late_existing_adoption_preserves_its_artwork_without_initial_asset_confirmation(self):
        import types
        self.config["listing_patch_contract"] = "dashboard-form-2026-10-01"
        self.state["config"] = self.config
        common.atomic_json(self.root / "docs/release-config.json", self.config)
        release.save(self.folder, self.state)
        app = self.app()
        app.update(description="Pre-existing description", companion_apps=[], icon_small="old-icon", icon_large="old-large")
        app["assets"][0]["screenshots"] = ["pre-existing-artwork"]
        session = self.session(app)
        session.patch.return_value = fixtures.Response()
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "dashboard_session", return_value=(session, "test-token")):
            state = release.begin_registration(self.args())
            self.assertTrue(state["registration"]["listing_confirmed"])
            release.read_manifest("1.0.0")
            def upload(api_base, app_id, firebase_id_token, pbw_path, version, release_notes, is_published, gif_paths, screenshot_paths, replace_screenshots):
                self.assertEqual(Path(pbw_path).read_bytes(), (self.folder / common.ARTIFACT).read_bytes())
                self.assertEqual((gif_paths, screenshot_paths, replace_screenshots), ([], [], False))
            upload_calls = Mock(wraps=upload)
            class Publisher:
                @classmethod
                def _post_with_wait_bar(cls, url, headers, data, files, timeout, label):
                    raise AssertionError("This adoption double never sends HTTP")
                @classmethod
                def _upload_release(cls, api_base, app_id, firebase_id_token, pbw_path, version, release_notes, is_published, gif_paths, screenshot_paths, replace_screenshots):
                    return upload_calls(api_base, app_id, firebase_id_token, pbw_path, version, release_notes, is_published, gif_paths, screenshot_paths, replace_screenshots)
            publisher = Publisher
            def observed_app(*_):
                result = copy.deepcopy(app)
                if session.patch.called:
                    result["description"] = state["description"]
                return result
            with patch.dict(sys.modules, {"pebble_tool.commands.publish": types.SimpleNamespace(PublishCommand=publisher)}), patch.object(release, "dashboard_app", side_effect=observed_app):
                release.upload_store(self.folder, state)
            upload_calls.assert_called_once()
        self.assertFalse((self.folder / "listing-confirmation.json").exists())
        fields = session.patch.call_args.kwargs["files"]
        self.assertEqual(set(fields), {"title", "description", "website", "source", "visibility", "companionAndroidName", "companionAndroidUrl", "companionAndroidRequired"})
        self.assertEqual(fields["title"], (None, app["title"]))
        self.assertEqual(app["assets"][0]["screenshots"], ["pre-existing-artwork"])
        changed = copy.deepcopy(app)
        changed["icon_small"] = "concurrently-changed"
        with patch.dict(sys.modules, {"pebble_tool.commands.publish": types.SimpleNamespace(PublishCommand=publisher)}), patch.object(release, "dashboard_session", return_value=(self.session(changed), "test-token")), self.assertRaisesRegex(RuntimeError, "Adopted listing metadata/assets changed"):
            release.upload_store(self.folder, state)

    def test_crash_after_exclusive_intent_is_own_new_recovery_not_existing_asset_adoption(self):
        registration.reserve_intent(self.root, self.state)
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "dashboard_session", return_value=(self.session(), "test-token")):
            state = release.begin_registration(self.args())
        self.assertEqual(state["registration"]["kind"], "initial-new")
        self.assertFalse(state["registration"]["listing_confirmed"])

    def test_conflicting_same_version_adoption_keeps_id_but_blocks_all_publication(self):
        self.config["listing_patch_contract"] = "dashboard-form-2026-10-01"
        self.state["config"] = self.config
        common.atomic_json(self.root / "docs/release-config.json", self.config)
        release.save(self.folder, self.state)
        app = self.app()
        app["releases"] = [{"version": "1.0.0", "is_published": True, "pbw_url": "/different.pbw"}]
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "dashboard_session", return_value=(self.session(app), "test-token")), patch.object(release, "get_public", return_value=fixtures.Response(content=b"different bytes")), self.assertRaisesRegex(RuntimeError, "different PBW"):
            release.begin_registration(self.args())
        state = json.loads((self.folder / "manifest.json").read_text())
        self.assertEqual(state["registration"]["app_id"], self.app_id)
        self.assertTrue(state["registration"]["identity_verified"])
        self.assertFalse(state["registration"]["listing_confirmed"])
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(release, "upload_github") as github, patch.object(release, "upload_store") as store, self.assertRaisesRegex(RuntimeError, "read-back"):
            release.publish(self.args())
        github.assert_not_called()
        store.assert_not_called()

    def test_older_uncertain_intent_with_discovered_app_cannot_transfer_approval(self):
        value = {"schema": 1, "uuid": common.UUID, "version": "0.9.0", "artifact_sha256": "e" * 64, "phase": "creation in flight", "kind": "initial-new", "app_id": None}
        common.atomic_json(registration.intent_path(self.root), value)
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned") as discover, self.assertRaisesRegex(RuntimeError, "earlier New attempt.*original candidate"):
            release.begin_registration(self.args())
        discover.assert_not_called()
        self.assertEqual(json.loads(registration.intent_path(self.root).read_text()), value)

    def test_missing_asset_confirmation_cannot_mark_initial_listing_ready(self):
        self.begin()
        args = self.record_args(True)
        value = json.loads(args.evidence.read_text())
        value["assets"].pop()
        common.atomic_json(args.evidence, value)
        with patch.object(release, "clean_tree"), patch.object(release, "run", return_value="fixture-commit"), patch.object(registration, "discover_owned", return_value=self.app_id), patch.object(release, "dashboard_session", return_value=(self.session(), "test-token")), self.assertRaisesRegex(RuntimeError, "every approved"):
            release.record_registration(args)
        saved = json.loads((self.folder / "manifest.json").read_text())
        self.assertEqual(saved["registration"]["app_id"], self.app_id)
        self.assertFalse(saved["registration"]["listing_confirmed"])
        self.assertNotEqual(json.loads(registration.intent_path(self.root).read_text())["phase"], "ready")

    def test_configured_observed_patch_contract_is_accepted_for_existing_mode(self):
        config = dict(self.config, store_app_id=self.app_id, listing_patch_contract="dashboard-form-2026-10-01")
        common.atomic_json(self.root / "docs/release-config.json", config)
        loaded = common.load_config(self.root)
        common.require_destinations(loaded, ["github", "appstore"])
        self.assertEqual(loaded, config)

    def test_current_observed_edit_form_preserves_visibility_and_android_without_assets(self):
        config = dict(self.config, listing_patch_contract="dashboard-form-2026-10-01")
        app = self.app()
        app["companion_apps"] = []
        for visible, unlisted, expected in ((True, False, "listed"), (False, True, "unlisted"), (False, False, "hidden")):
            app.update(visible=visible, unlisted=unlisted)
            fields = release.listing_fields(app, "Reviewed description", config)
            self.assertEqual(fields["visibility"], expected)
            self.assertEqual(set(fields), {"title", "description", "website", "source", "visibility", "companionAndroidName", "companionAndroidUrl", "companionAndroidRequired"})
            self.assertEqual(fields["companionAndroidRequired"], "false")
        app["companion_apps"] = [{"platform": "android", "name": "Existing Android", "url": "https://example.invalid/android", "required": True}]
        self.assertEqual(release.listing_fields(app, "Reviewed", config)["companionAndroidName"], "Existing Android")
        app["companion_apps"].append({"platform": "ios", "name": "Existing iOS"})
        with self.assertRaisesRegex(RuntimeError, "iOS"):
            release.listing_fields(app, "Reviewed", config)


if __name__ == "__main__":
    unittest.main()
