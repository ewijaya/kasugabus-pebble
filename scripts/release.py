#!/usr/bin/env python3
"""Freeze, publish and verify one approved KasugaBus PBW. Never auto-register.

Imports and help are offline and unauthenticated. Publication is a separate,
explicit command and never builds or rewrites its approved artifact.
"""
import argparse
import copy
import datetime
import html
import inspect
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import urljoin
from release_common import ARTIFACT, ROOT, UUID, atomic_json, digest, inspect_pbw, load_config, require, require_destinations, semver
from check_release import validate_audit
import registration


def run(*args, capture=False):
    return subprocess.run(args, cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE if capture else None, timeout=120).stdout


def clean_tree(config, allowed_dirty=None):
    require((ROOT / ".git").exists(), "No Git repository exists; initialization is a separate authorized task")
    status = run("git", "status", "--porcelain", capture=True)
    for line in status.splitlines():
        path = line[3:]
        require(allowed_dirty and path in allowed_dirty and line[:2] in (" M", "M ", "MM") and digest((ROOT / path).read_bytes()) == allowed_dirty[path], "Review and commit the intended changes before preparing/publishing; do not discard unrelated work")
    require(run("git", "branch", "--show-current", capture=True).strip() == config["branch"], "Unexpected release branch")
    if config.get("github_repo"):
        remote = run("git", "remote", "get-url", "origin", capture=True).strip().removesuffix(".git")
        require(remote in ("https://github.com/" + config["github_repo"], "git@github.com:" + config["github_repo"]), "Unexpected/missing origin remote")
    for path in ("build/", "node_modules/", ".release/"):
        run("git", "check-ignore", "--quiet", path)
        require(not run("git", "ls-files", path, capture=True).strip(), "Generated/private candidate path is tracked: " + path)
    run("git", "diff", "--check")


def candidate_tree(state):
    config = load_config(ROOT)
    registration.check_config(state, config)
    if config != state["config"]:
        raw = (ROOT / "docs/release-config.json").read_bytes()
        clean_tree(config, {"docs/release-config.json": digest(raw)})
    else:
        clean_tree(config)
    require(run("git", "rev-parse", "HEAD", capture=True).strip() in (state["commit"], state.get("documentation_commit")), "Source changed after freezing; prepare and review a new candidate")


def candidate(version):
    semver(version)
    return ROOT / ".release" / version


def save(folder, state):
    atomic_json(Path(folder) / "manifest.json", state)


def read_manifest(version):
    folder = candidate(version)
    state = json.loads((folder / "manifest.json").read_text())
    require(state.get("schema") == 1 and state.get("version") == version, "Candidate schema/version mismatch")
    require(inspect_pbw(folder / ARTIFACT, version) == state.get("artifact"), "Frozen PBW changed; publication refused")
    config = load_config(ROOT)
    registration.check_config(state, config)
    require_destinations(config, state.get("destinations", []), state.get("store_mode", "existing"))
    require(digest((folder / "notes.md").read_bytes()) == state.get("notes_sha256") and (folder / "notes.md").read_text().strip() == state["notes"], "Frozen release notes changed")
    if "appstore" in state["destinations"]:
        require(digest((folder / "description.txt").read_bytes()) == state.get("description_sha256") and (folder / "description.txt").read_text().strip() == state["description"], "Frozen listing text changed")
    audit = json.loads((folder / "audit.json").read_text())
    validate_audit(audit, folder / ARTIFACT, version, ROOT, require_current_source=False)
    require(audit["metrics"] == state.get("metrics"), "Frozen audit metrics changed")
    if state.get("store_mode") == "create-or-resume":
        value = registration.frozen_listing(folder, state.get("listing"))
        require(value["metadata"]["description"] == state["description"], "Frozen description/listing disagree")
        reg = state.get("registration") or {}
        if reg.get("listing_confirmed") and reg.get("kind") != "adopted-existing":
            evidence = folder / "listing-confirmation.json"
            require(evidence.is_file() and digest(evidence.read_bytes()) == reg.get("confirmation_sha256"), "Listing read-back confirmation changed")
    return folder, state


def plan(args):
    config = load_config(ROOT)
    package = json.loads((ROOT / "package.json").read_text())
    summary = {"version": package["version"], "github_repo": config["github_repo"], "store_app_id": config["store_app_id"], "git_initialized": (ROOT / ".git").exists(), "registration": "existing listing" if config["store_app_id"] else "not registered; use approved first-registration flow"}
    if summary["git_initialized"]:
        summary["branch"] = run("git", "branch", "--show-current", capture=True).strip()
        summary["status"] = run("git", "status", "--short", capture=True)
        tags = run("git", "tag", "--sort=-version:refname", capture=True).splitlines()
        summary["previous_tag"] = tags[0] if tags else None
        summary["changes"] = run("git", "log", "--oneline", (tags[0] + "..HEAD") if tags else "HEAD", capture=True)
    if args.remote:
        require_destinations(config, args.destination)
        if "github" in args.destination:
            summary["github_releases"] = json.loads(run("gh", "api", "repos/" + config["github_repo"] + "/releases", capture=True))
        if "appstore" in args.destination:
            session, _ = dashboard_session(config)
            app = dashboard_app(session, config)
            summary["store_releases"] = [{"version": r["version"], "is_published": r.get("is_published")} for r in app.get("releases", [])]
    print(json.dumps(summary, indent=2))
    return summary


def prepare(args):
    config = load_config(ROOT)
    store_mode = getattr(args, "store_mode", "existing")
    require_destinations(config, args.destination, store_mode)  # Fail before build/auth if missing.
    if store_mode == "create-or-resume":
        require(registration.discover_owned(config) is None, "Existing KasugaBus listing found: use discover-registration --save-match, commit its verified config, then prepare in existing mode; preserve its artwork")
    clean_tree(config)
    package = json.loads((ROOT / "package.json").read_text())
    require(package["version"] == args.version, "Prepare the approved package version first; this helper never bumps it")
    lock = json.loads((ROOT / "package-lock.json").read_text())
    require(lock.get("version") == args.version and lock.get("packages", {}).get("", {}).get("version") == args.version, "Package/lockfile versions differ")
    for name in ("README.md", "CHANGELOG.md"):
        require(args.version in (ROOT / name).read_text(), "Review " + name + " for this version first")
    folder = candidate(args.version)
    require(not folder.exists(), "Candidate already exists; never overwrite its approval/evidence")
    notes = args.notes.read_text().strip()
    description = args.description.read_text().strip() if args.description else None
    listing = None
    if store_mode == "create-or-resume":
        require("appstore" in args.destination and getattr(args, "listing", None), "First publication requires an App Store destination and complete local listing")
        listing = registration.validate_listing(args.listing, ROOT)
        require(registration.repository_url(listing["metadata"]["source"]) == registration.repository_url("https://github.com/" + config["github_repo"]), "Initial listing source must match the configured frozen repository")
        proposed = listing["metadata"]["description"].strip()
        require(description is None or description == proposed, "Reviewed listing and description file disagree")
        description = proposed
    require(notes, "Release notes are empty")
    require("appstore" not in args.destination or description, "Store destination needs reviewed description text")
    audit = json.loads(args.audit.read_text())
    bundle = ROOT / "build" / ARTIFACT
    validate_audit(audit, bundle, args.version, ROOT)
    require(args.physical, "Physical installation of this exact candidate is required before freezing a publication candidate")
    commit = run("git", "rev-parse", "HEAD", capture=True).strip()
    require(audit["source"].get("git_commit") == commit, "The audited build was not made from this exact committed source")
    # Existing releases are checked before installation and candidate creation.
    if "github" in args.destination:
        releases = json.loads(run("gh", "api", "repos/" + config["github_repo"] + "/releases", capture=True))
        require(not any(r.get("tag_name") == "v" + args.version for r in releases), "This GitHub release already exists; inspect it instead of preparing an overwrite")
    if "appstore" in args.destination and store_mode == "existing":
        session, _ = dashboard_session(config)
        app = dashboard_app(session, config)
        listing_fields(app, description, config)  # Unsupported metadata shape fails before upload.
        require(all(semver(r["version"]) < semver(args.version) for r in app.get("releases", [])), "Store version must be newer than existing releases")
    run("pebble", "install", "--cloudpebble", str(bundle))
    clean_tree(config)
    require(inspect_pbw(bundle, args.version) == audit["artifact"], "PBW changed during physical installation")
    folder.mkdir(parents=True)
    shutil.copy2(bundle, folder / ARTIFACT)
    shutil.copy2(audit["runtime"]["evidence_path"], folder / "runtime.log")
    shutil.copy2(audit["runtime"]["install_receipt_path"], folder / "runtime-install.json")
    audit = copy.deepcopy(audit)
    audit["runtime"]["evidence_path"] = str((folder / "runtime.log").resolve())
    audit["runtime"]["install_receipt_path"] = str((folder / "runtime-install.json").resolve())
    atomic_json(folder / "audit.json", audit)
    (folder / "notes.md").write_text(notes + "\n")
    if description:
        (folder / "description.txt").write_text(description + "\n")
    state = {"schema": 1, "version": args.version, "commit": commit, "config": config, "artifact": audit["artifact"], "metrics": audit["metrics"], "notes": notes,
        "notes_sha256": digest((folder / "notes.md").read_bytes()), "description": description,
        "description_sha256": digest((folder / "description.txt").read_bytes()) if description else None,
        "destinations": [d for d in ("github", "appstore") if d in args.destination], "physical_installed": True, "status": {}, "approval": None}
    if listing:
        state["store_mode"] = store_mode
        state["listing"] = registration.freeze_listing(listing, folder, ROOT)
        state["registration"] = {"phase": "planned", "identity_verified": False, "listing_confirmed": False}
    save(folder, state)
    print("Candidate frozen:", folder, json.dumps(state["artifact"]), flush=True)
    print("Installation is recorded. Explicit physical approval of this SHA-256 and these destinations is still required.", flush=True)
    return state


def dashboard_session(config):
    import requests
    from pebble_tool.account import get_account
    account = get_account(auth_provider="firebase")
    require(account.is_logged_in, "Log into the existing developer account separately")
    token = account.get_access_token()  # In memory only; never printed/persisted.
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 KasugaBusRelease"
    response = session.post(config["dashboard"] + "/api/auth/firebase/session", json={"idToken": token}, timeout=30, allow_redirects=False)
    require(not 300 <= response.status_code < 400, "Auth redirect rejected; never forward a Firebase token to another URL")
    response.raise_for_status()
    return session, token


def dashboard_app(session, config):
    response = session.get(config["dashboard"] + "/api/dashboard/apps/" + config["store_app_id"], timeout=30, allow_redirects=False)
    require(not 300 <= response.status_code < 400, "Dashboard redirect rejected")
    response.raise_for_status()
    app = response.json()["app"]
    require(app.get("id") == config["store_app_id"] and app.get("app_uuid") == UUID, "Unexpected registered app identity")
    return app


def approve_candidate(args, folder, state):
    require(args.approve_publish == state["version"] and args.approve_sha256 == state["artifact"]["sha256"], "Publication approval must match the exact version and PBW SHA-256")
    require(len(args.approve_destination) == len(set(args.approve_destination)) and set(args.approve_destination) == set(state["destinations"]), "Publication approval must name exactly the frozen destinations")
    require(args.approve_physical and state["physical_installed"], "Installation alone is not physical approval of this exact candidate")
    candidate_tree(state)
    state["approval"] = {"version": args.version, "sha256": args.approve_sha256, "physical": True, "destinations": list(state["destinations"]), "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    save(folder, state)


def recorded_approval(state):
    approved = state.get("approval") or {}
    require(approved.get("version") == state["version"] and approved.get("sha256") == state["artifact"]["sha256"] and approved.get("physical") is True and approved.get("destinations") == state["destinations"] and state.get("physical_installed"), "Exact candidate physical/destination approval is missing")


def registration_candidate(version):
    folder, state = read_manifest(version)
    require(state.get("store_mode") == "create-or-resume" and "appstore" in state["destinations"], "Candidate does not authorize first registration")
    return folder, state


def record_assigned(folder, state, app_id, evidence=None):
    recorded_approval(state)
    reg = state["registration"]
    require(not reg.get("app_id") or reg["app_id"] == app_id, "A different assigned listing ID is already recorded; review before changing it")
    require(not state["config"].get("store_app_id") or state["config"]["store_app_id"] == app_id, "Assigned ID differs from the configured existing listing")
    url = registration.capture_id(ROOT, state, app_id)
    reg.update(app_id=app_id, listing_url=url, public_verification="pending", phase="assigned; identity verification pending")
    if reg.get("kind") == "adopted-existing":
        reg["listing_confirmed"] = False
    # This is the first action after UI response/App Information supplies ID.
    # A failed lookup cannot lose the assigned ID or authorize another create.
    save(folder, state)
    print("Assigned listing recorded:", app_id, url, flush=True)
    candidate_tree(state)
    require(registration.discover_owned(state["config"]) == app_id, "Assigned listing is not the authenticated owned UUID match; retain receipt and reconcile")
    config = dict(state["config"], store_app_id=app_id)
    session, _ = dashboard_session(config)
    app = dashboard_app(session, config)
    registration.validate_identity(app, config)
    reg.update(identity_verified=True, phase="created; listing confirmation pending")
    save(folder, state)
    registration.update_intent(ROOT, state)
    # Only these two receipt-bound identity fields may transition after freeze.
    atomic_json(ROOT / "docs/release-config.json", registration.transitioned_config(state))
    releases = [item for item in app.get("releases", []) if item.get("version") == state["version"]]
    require(len(releases) <= 1, "Multiple matching initial releases; inspect before continuing")
    if releases:
        require(digest(get_public(asset_url(releases[0].get("pbw_url"), config), state["artifact"]["bytes"]).content) == state["artifact"]["sha256"], "Initial release has a different PBW; keep assigned ID and stop")
        require(releases[0].get("is_published") is True, "Matching frozen initial draft needs Dashboard release review/publication on this same listing; retain ID, never use New again")
    if reg.get("kind") == "adopted-existing":
        require_destinations(registration.transitioned_config(state), state["destinations"])
        reg.update(listing_confirmed=True, confirmation_mode="existing metadata/assets preserved", preserved_sha256=digest(json.dumps(preserved_fields(app), sort_keys=True).encode()), phase="ready")
        save(folder, state)
        registration.update_intent(ROOT, state)
    if evidence is not None and reg.get("kind") != "adopted-existing":
        evidence = Path(evidence)
        value = json.loads(evidence.read_text())
        require(set(value) == {"schema", "confirmed", "app_id", "uuid", "listing_sha256", "artifact_sha256", "metadata", "assets", "dashboard_readback"}, "Use the bounded listing confirmation schema; do not copy credentials/account responses")
        require(value.get("schema") == 1 and value.get("confirmed") is True and value.get("app_id") == app_id and value.get("uuid") == UUID and value.get("listing_sha256") == state["listing"]["sha256"] and value.get("artifact_sha256") == state["artifact"]["sha256"], "Listing read-back evidence does not confirm all frozen metadata/assets and this artifact")
        frozen = registration.frozen_listing(folder, state["listing"])
        expected_assets = [{key: asset[key] for key in ("role", "sha256", "platform") if key in asset} for asset in frozen["assets"]]
        require(value["metadata"] == frozen["metadata"] and value["assets"] == expected_assets and value["dashboard_readback"] == {"app_id": app_id, "uuid": UUID, "source": frozen["metadata"]["source"], "type": "watchapp", "platforms": ["emery"]}, "Actual Dashboard metadata and every approved icon/banner/screenshot must be read back")
        destination = folder / "listing-confirmation.json"
        shutil.copy2(evidence, destination)
        reg.update(listing_confirmed=True, confirmation_sha256=digest(destination.read_bytes()), phase="ready")
        save(folder, state)
        registration.update_intent(ROOT, state)
    return state


def begin_registration(args):
    folder, state = registration_candidate(args.version)
    approve_candidate(args, folder, state)
    intent = registration.prior_intent(ROOT, state)
    found = registration.discover_owned(state["config"])
    if found:
        reg = state["registration"]
        if reg.get("phase") == "planned":
            if intent and intent.get("version") == state["version"] and intent.get("artifact_sha256") == state["artifact"]["sha256"] and intent.get("kind", "initial-new") == "initial-new":
                reg.update(origin="Dashboard New recovered", kind="initial-new")
            else:
                reg.update(origin="existing UUID discovered", kind="adopted-existing")
        return record_assigned(folder, state, found)
    reg = state["registration"]
    if reg.get("phase") != "planned" or state["config"].get("store_app_id"):
        reg["phase"] = "creation uncertain; reconcile only"
        save(folder, state)
        raise RuntimeError("Creation may already have been submitted. Do not submit again; reconcile the owned UUID/App Information first")
    registration.reserve_intent(ROOT, state)
    reg.update(phase="creation in flight", origin="Dashboard New", kind="initial-new", started_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save(folder, state)
    print("Registration intent saved before UI submission. Use Dashboard New once with the frozen PBW/listing/assets; immediately record the returned App ID. This command never submits or uploads.", flush=True)
    return state


def record_registration(args):
    # UI creation may have succeeded even if a local artifact or Git check is
    # now broken. Capture its identity first using only the approved manifest.
    folder = candidate(args.version)
    captured = json.loads((folder / "manifest.json").read_text())
    require(captured.get("schema") == 1 and captured.get("version") == args.version and captured.get("store_mode") == "create-or-resume" and captured.get("config", {}).get("uuid") == UUID, "No approved first-registration candidate")
    recorded_approval(captured)
    require(captured["registration"].get("phase") != "planned", "Begin and approve registration before recording the UI result")
    require(not captured["registration"].get("app_id") or captured["registration"]["app_id"] == args.app_id, "A different assigned ID is already recorded")
    url = registration.capture_id(ROOT, captured, args.app_id)
    captured["registration"].update(app_id=args.app_id, listing_url=url, public_verification="pending", phase="assigned; identity verification pending")
    save(folder, captured)
    folder, state = registration_candidate(args.version)
    require(not args.confirm_listing or args.evidence, "Confirming all listing assets requires exact read-back evidence")
    return record_assigned(folder, state, args.app_id, args.evidence if args.confirm_listing else None)


def discover_registration(args=None):
    config = load_config(ROOT)
    require_destinations(config, ["appstore"], "create-or-resume")
    found = registration.discover_owned(config)
    result = {"uuid": UUID, "github_repo": config["github_repo"], "app_id": found, "listing_url": registration.public_url(config, found) if found else None, "public_verification": "not checked", "releases": []}
    if found:
        selected = dict(config, store_app_id=found)
        session, _ = dashboard_session(selected)
        app = dashboard_app(session, selected)
        registration.validate_identity(app, selected)
        result["releases"] = [{key: item.get(key) for key in ("id", "version", "is_published", "pbw_url", "release_notes")} for item in app["releases"]]
        if args is not None and getattr(args, "save_match", False):
            path = registration.intent_path(ROOT)
            if path.exists():
                intent = json.loads(path.read_text())
                require(intent.get("schema") == 1 and intent.get("uuid") == UUID, "Unknown project registration receipt; inspect before adoption")
                require(intent.get("kind", "initial-new") != "initial-new" or intent.get("phase") == "ready", "Unresolved Dashboard New intent: use reconcile-registration " + str(intent.get("version")) + " for its original candidate before saving the discovered ID")
            require(not config.get("store_app_id") or config["store_app_id"] == found, "Configured ID differs from discovered owned app; review before adoption")
            atomic_json(ROOT / "docs/release-config.json", dict(config, store_app_id=found, store_listing_url=result["listing_url"]))
            result["saved_locally"] = True
    print(json.dumps(result, indent=2))
    return result


def reconcile_registration(args):
    folder, state = registration_candidate(args.version)
    recorded_approval(state)
    candidate_tree(state)
    registration.prior_intent(ROOT, state)
    found = registration.discover_owned(state["config"])
    if found:
        return record_assigned(folder, state, found)
    state["registration"]["phase"] = "creation uncertain; reconcile only"
    save(folder, state)
    raise RuntimeError("No authenticated UUID match is visible yet. Keep registration pending; never blindly repeat Dashboard New")


def preserved_fields(app):
    # Preserve all unknown metadata as well as known title/assets/companions.
    excluded = {"description", "releases", "latest_release", "updated_at", "updatedAt"}
    result = copy.deepcopy({k: v for k, v in app.items() if k not in excluded})
    if "assets" in result:
        for asset in result["assets"]:
            for key in ("description", "updated_at", "updatedAt"):
                asset.pop(key, None)
    return result


def prior_release_history(app):
    records = {}
    for record in app.get("releases", []):
        key = record.get("id") or record.get("version")
        require(key and key not in records, "Ambiguous prior release history")
        records[key] = {field: record.get(field) for field in ("id", "version", "pbw_url", "is_published", "release_notes")}
    return records


def require_prior_history(before, after):
    previous, current = prior_release_history(before), prior_release_history(after)
    require(all(current.get(key) == value for key, value in previous.items()), "A previous release was deleted or changed; stop for review")


def listing_fields(app, description, config):
    contract = config.get("listing_patch_contract")
    require(isinstance(description, str) and description, "Reviewed listing description is required")
    if contract == "partial-description":
        return {"description": description}
    if contract == "dashboard-form-2026-10-01":
        require(all(key in app for key in ("title", "website", "source", "visible", "companion_apps")), "Official Dashboard form metadata is incomplete")
        require(isinstance(app["visible"], bool) and isinstance(app.get("unlisted", False), bool), "Unknown Dashboard visibility shape")
        require(not (app.get("unlisted") and app["visible"]) and not app.get("dmca_takedown"), "Inconsistent/restricted Dashboard visibility; inspect before editing")
        require(isinstance(app["companion_apps"], list), "Unknown Dashboard companion shape")
        android = []
        for companion in app["companion_apps"]:
            require(isinstance(companion, dict) and companion.get("platform") == "android", "Current official form does not preserve nonempty iOS/unknown companion metadata; inspect before editing")
            android.append(companion)
        require(len(android) <= 1, "Duplicate Android companion metadata")
        if android:
            companion = android[0]
            require(isinstance(companion.get("name"), str) and isinstance(companion.get("url"), str) and isinstance(companion.get("required"), bool), "Unknown Android companion form metadata")
        else:
            companion = {"name": "", "url": "", "required": False}
        require(isinstance(app["title"], str) and all(app[key] is None or isinstance(app[key], str) for key in ("website", "source")), "Unknown Dashboard scalar form metadata")
        return {"title": app["title"], "description": description, "website": app["website"] or "", "source": app["source"] or "", "visibility": "listed" if app["visible"] else "unlisted" if app.get("unlisted") else "hidden", "companionAndroidName": companion["name"], "companionAndroidUrl": companion["url"], "companionAndroidRequired": str(companion["required"]).lower()}
    require(contract == "dashboard-form-v1", "Dashboard PATCH contract has not been verified")
    # Full-form contracts require explicit, currently verified field bindings.
    # No fabricated empty defaults, no unsupported companion platform resets.
    bindings = config.get("listing_form_fields")
    require(isinstance(bindings, dict) and bindings.get("description") == "description", "Full-form field bindings must be verified from the current official dashboard")
    result = {}
    for form_key, path in bindings.items():
        require(isinstance(form_key, str) and isinstance(path, str), "Invalid Dashboard form binding")
        if path == "description":
            value = description
        else:
            value = app
            for part in path.split("."):
                if isinstance(value, list):
                    matches = [item for item in value if isinstance(item, dict) and item.get("platform") == part]
                    require(len(matches) == 1, "Unsupported/missing companion form binding: " + path)
                    value = matches[0]
                else:
                    require(isinstance(value, dict) and part in value, "Missing official form field: " + path)
                    value = value[part]
        require(value is None or isinstance(value, (str, bool, int)), "Unsupported complex writable field: " + path)
        result[form_key] = str(value).lower() if isinstance(value, bool) else "" if value is None else str(value)
    required = {"title", "website", "source", "visible", "category_id"}
    require(required <= set(bindings.values()), "Full-form bindings omit preserved listing metadata")
    for companion in app.get("companion_apps", []):
        require(companion.get("platform") in ("android", "ios"), "Unsupported companion platform; use reviewed Dashboard UI")
        for key in ("name", "url", "required"):
            require("companion_apps." + companion["platform"] + "." + key in bindings.values(), "Full-form bindings omit companion metadata")
    return result


def github_release(state):
    repo = state["config"]["github_repo"]
    result = subprocess.run(["gh", "api", "repos/" + repo + "/releases/tags/v" + state["version"]], cwd=ROOT, capture_output=True, text=True, timeout=60)
    if result.returncode:
        require("404" in result.stderr, "GitHub lookup failed; not assuming the release is absent")
        return None
    return json.loads(result.stdout)


def get_public(url, max_bytes=2097152):
    import requests
    deadline = time.monotonic() + 60
    for attempt in range(5):
        require(time.monotonic() <= deadline, "Public read exceeded its total deadline")
        require(url.startswith("https://"), "Public read requires HTTPS")
        response = requests.get(url, timeout=(10, 5), headers={"User-Agent": "Mozilla/5.0 KasugaBusRelease"}, stream=True, allow_redirects=False)
        if 300 <= response.status_code < 400:
            location = response.headers.get("Location")
            response.close()
            require(location and attempt < 4, "Too many/missing public redirects")
            url = urljoin(url, location)
            continue
        try:
            response.raise_for_status()
        except Exception:
            response.close()
            raise
        content = bytearray()
        try:
            length = response.headers.get("Content-Length")
            require(length is None or (length.isdigit() and int(length) <= max_bytes), "Public response is larger than its bounded budget")
            while True:
                require(time.monotonic() <= deadline, "Public read exceeded its total deadline")
                chunk = response.raw.read1(65536, decode_content=True) if hasattr(response.raw, "read1") else response.raw.read(1, decode_content=True)
                if not chunk:
                    break
                content.extend(chunk)
                require(len(content) <= max_bytes, "Public response exceeded its bounded budget")
        finally:
            response.close()
        response._content = bytes(content)
        response._content_consumed = True
        return response
    raise RuntimeError("Public redirect bound exceeded")


def asset_url(value, config):
    require(isinstance(value, str) and bool(value), "Missing public PBW URL")
    url = urljoin(config["appstore_api"] + "/", value)
    require(url.startswith("https://"), "Public artifact must use HTTPS")
    return url


def verify_github(state):
    release = github_release(state)
    require(release and not release.get("draft") and not release.get("prerelease") and state["notes"] in release.get("body", ""), "GitHub release/version/notes are not public")
    assets = [a for a in release.get("assets", []) if a["name"] == ARTIFACT]
    require(len(assets) == 1 and assets[0]["size"] == state["artifact"]["bytes"], "GitHub PBW missing or wrong size")
    require(digest(get_public(assets[0]["browser_download_url"], state["artifact"]["bytes"]).content) == state["artifact"]["sha256"], "GitHub PBW digest mismatch; never overwrite")
    latest = json.loads(run("gh", "api", "repos/" + state["config"]["github_repo"] + "/releases/latest", capture=True))
    require(latest["tag_name"] == "v" + state["version"], "GitHub latest is a different release")
    return {"release_url": release["html_url"], "asset_url": assets[0]["browser_download_url"]}


def upload_github(folder, state):
    tag = "v" + state["version"]
    releases = json.loads(run("gh", "api", "repos/" + state["config"]["github_repo"] + "/releases", capture=True))
    for existing in releases:
        if existing.get("draft") or existing.get("prerelease"):
            continue
        label = existing.get("tag_name", "")
        require(label.startswith("v") and semver(label[1:]) <= semver(state["version"]), "A newer/unknown GitHub release exists; do not mark an older candidate latest")
    run("git", "push", "origin", state["config"]["branch"])
    found = subprocess.run(["git", "rev-parse", "--verify", "refs/tags/" + tag], cwd=ROOT, capture_output=True, timeout=30)
    if found.returncode == 0:
        require(run("git", "cat-file", "-t", tag, capture=True).strip() == "tag" and run("git", "rev-list", "-n", "1", tag, capture=True).strip() == state["commit"], "Existing tag differs from frozen source")
    else:
        run("git", "tag", "-a", tag, "-m", "KasugaBus " + tag, state["commit"])
    run("git", "push", "origin", tag)
    if not github_release(state):
        notes_path = folder / "github-notes.md"
        notes_path.write_text(state["notes"] + "\n\nPBW SHA-256: `" + state["artifact"]["sha256"] + "`.\n")
        run("gh", "release", "create", tag, str(folder / ARTIFACT), "--verify-tag", "--title", "KasugaBus " + tag, "--notes-file", str(notes_path), "--latest")


def upload_store(folder, state):
    from pebble_tool.commands.publish import PublishCommand
    config = registration.transitioned_config(state)
    session, token = dashboard_session(config)
    before = dashboard_app(session, config)
    if state.get("registration", {}).get("kind") == "adopted-existing":
        require(digest(json.dumps(preserved_fields(before), sort_keys=True).encode()) == state["registration"].get("preserved_sha256"), "Adopted listing metadata/assets changed; inspect before publication")
    require(all(semver(r["version"]) <= semver(state["version"]) for r in before.get("releases", [])), "A newer store release appeared; inspect it before publication")
    fields = listing_fields(before, state["description"], config) if before.get("description") != state["description"] else None
    preserved = preserved_fields(before)
    existing = next((r for r in before.get("releases", []) if r["version"] == state["version"]), None)
    if existing:
        require(existing.get("is_published"), "Existing draft needs review; never silently publish it")
        require(digest(get_public(asset_url(existing.get("pbw_url"), config), state["artifact"]["bytes"]).content) == state["artifact"]["sha256"], "Store version exists with a different artifact")
    else:
        expected = {"api_base", "app_id", "firebase_id_token", "pbw_path", "version", "release_notes", "is_published", "gif_paths", "screenshot_paths", "replace_screenshots"}
        require(set(inspect.signature(PublishCommand._upload_release).parameters) == expected, "Installed uploader signature changed; inspect the local implementation before proceeding")
        PublishCommand._upload_release(api_base=config["appstore_api"], app_id=config["store_app_id"], firebase_id_token=token,
            pbw_path=str(folder / ARTIFACT), version=state["version"], release_notes=state["notes"], is_published=True,
            gif_paths=[], screenshot_paths=[], replace_screenshots=False)
    after_upload = dashboard_app(session, config)
    require_prior_history(before, after_upload)
    require(preserved_fields(after_upload) == preserved, "Release upload changed unrelated listing metadata/assets; stop for review")
    if before.get("description") != state["description"]:
        response = session.patch(config["dashboard"] + "/api/dashboard/apps/" + config["store_app_id"], files={k: (None, value) for k, value in fields.items()}, timeout=30, allow_redirects=False)
        require(not 300 <= response.status_code < 400, "Dashboard PATCH redirect rejected")
        response.raise_for_status()
    after = dashboard_app(session, config)
    require_prior_history(before, after)
    require(preserved_fields(after) == preserved, "Listing update changed unrelated metadata/assets; stop for review")
    require(after.get("description") == state["description"], "Dashboard description has not synchronized")


def verify_store(state):
    if state.get("store_mode") == "create-or-resume":
        require(state["registration"].get("identity_verified") and state["registration"].get("listing_confirmed"), "First listing metadata/assets still need verified read-back confirmation")
    config = registration.transitioned_config(state)
    session, _ = dashboard_session(config)
    app = dashboard_app(session, config)
    release = app.get("latest_release") or {}
    require(app.get("visible") is True and release.get("version") == state["version"] and release.get("is_published") is True, "Dashboard version/publication is pending")
    require(release.get("release_notes") == state["notes"] and app.get("description") == state["description"], "Dashboard notes/description differ")
    emery = [a for a in app.get("assets", []) if a.get("platform") == "emery"]
    require(emery and all(a.get("description") == state["description"] for a in emery), "Dashboard Emery asset description is pending")
    require(digest(get_public(asset_url(release.get("pbw_url"), config), state["artifact"]["bytes"]).content) == state["artifact"]["sha256"], "Dashboard PBW hash mismatch")
    catalog_url = config["appstore_api"] + config["public_catalog_path"].format(uuid=UUID)
    for url in (catalog_url, catalog_url + "?hardware=emery"):
        items = get_public(url).json().get("data")
        require(isinstance(items, list), "Unknown public catalog response")
        matches = [a for a in items if a.get("id") == config["store_app_id"] and a.get("uuid") == UUID]
        require(len(matches) == 1, "KasugaBus public catalog identity is missing")
        public = matches[0]
        latest = public.get("latest_release") or {}
        require(public.get("visible") is True and public.get("description") == state["description"] and latest.get("version") == state["version"] and latest.get("release_notes") == state["notes"], "Public catalog version/description is pending: " + url)
        require("emery" in public.get("hardware_platforms", []), "Public catalog lacks Emery compatibility")
        require(digest(get_public(asset_url(latest.get("pbw_file"), config), state["artifact"]["bytes"]).content) == state["artifact"]["sha256"], "Public catalog PBW digest mismatch")
    store = config["public_store"] + "/" + config["store_app_id"]
    for url, expected in ((store, [state["description"], release["pbw_url"]]), (store + "/changelog", [state["version"], state["notes"]])):
        text = html.unescape(get_public(url).text).replace("\\r\\n", "\n").replace("\\n", "\n").replace("\r\n", "\n")
        require(all(value.replace("\r\n", "\n") in text for value in expected), "Canonical public page is pending: " + url)
    if state.get("store_mode") == "create-or-resume":
        state["registration"]["public_verification"] = "verified"
    return {"dashboard": "verified", "catalog_general": "verified", "catalog_emery": "verified", "public_store_url": store, "mobile_cache": "not observed; Emery catalog is a proxy"}


def verify(folder, state, attempts=1):
    require(1 <= attempts <= 5, "Use 1..5 bounded read-only verification attempts")
    for attempt in range(attempts):
        errors = []
        for destination in state["destinations"]:
            try:
                result = (verify_github if destination == "github" else verify_store)(state)
                state["status"][destination] = {"state": "verified", "details": result}
            except Exception as error:
                state["status"][destination] = {"state": "pending verification", "reason": str(error)}
                errors.append(destination)
        save(folder, state)
        print("Verification attempt", attempt + 1, json.dumps(state["status"]), flush=True)
        if not errors:
            return state
        if attempt + 1 < attempts:
            time.sleep(20)
    raise RuntimeError("Publication may be partially live; verification remains pending. Retry verify without rebuilding or uploading")


def record_docs(folder, state):
    require(all(state["status"].get(d, {}).get("state") == "verified" for d in state["destinations"]), "Do not advertise an unverified destination")
    candidate_tree(state)
    config = registration.transitioned_config(state)
    readme = ROOT / "README.md"
    text = readme.read_text()
    marker = "<!-- kasugabus-release-status -->"
    require(text.count(marker) == 1, "README publication marker needs review before documentation synchronization")
    destinations = []
    if "github" in state["destinations"]:
        destinations.append("[GitHub Releases](https://github.com/" + state["config"]["github_repo"] + "/releases/tag/v" + state["version"] + ")")
    if "appstore" in state["destinations"]:
        destinations.append("[Pebble App Store](" + config["public_store"] + "/" + config["store_app_id"] + ")")
    line = "KasugaBus **v" + state["version"] + "** for Emery is available from " + " and ".join(destinations) + "."
    text, count = re.subn(re.escape(marker) + r"\n[^\n]*", marker + "\n" + line, text)
    require(count == 1, "README publication marker is malformed")
    receipt_path = ROOT / "docs/releases/latest-status.json"
    atomic_json(receipt_path, {key: state[key] for key in ("version", "commit", "artifact", "metrics", "status")})
    readme.write_text(text)
    run("git", "add", "README.md", "docs/releases/latest-status.json")
    if config != state["config"]:
        run("git", "add", "docs/release-config.json")
    if run("git", "diff", "--cached", "--name-only", capture=True).strip():
        run("git", "commit", "-m", "docs: verify KasugaBus v" + state["version"] + " publication")
    state["documentation_commit"] = run("git", "rev-parse", "HEAD", capture=True).strip()
    # A failed push must leave the new, authorized docs commit recoverable.
    # Save it before network I/O; a retry also pushes it when no diff remains.
    save(folder, state)
    run("git", "push", "origin", state["config"]["branch"])


def publish(args):
    folder, state = read_manifest(args.version)
    approve_candidate(args, folder, state)
    if state.get("store_mode") == "create-or-resume":
        reg = state["registration"]
        require(reg.get("identity_verified") and reg.get("listing_confirmed"), "Complete approved Dashboard New registration/read-back using begin-registration, record-registration and reconcile-registration before publication continues")
        require(registration.discover_owned(state["config"]) == reg["app_id"], "Owned UUID registration changed; do not publish to another listing")
    for destination in state["destinations"]:
        if state["status"].get(destination, {}).get("state") == "verified":
            continue
        try:
            (upload_github if destination == "github" else upload_store)(folder, state)
            state["status"][destination] = {"state": "uploaded; verification pending"}
        except Exception:
            state["status"][destination] = {"state": "upload stopped; inspect remote before retry"}
            save(folder, state)
            raise
        save(folder, state)
    verify(folder, state, 3)
    record_docs(folder, state)
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("plan", help="Read-only release/version context; no build, bump or publication")
    p.add_argument("--remote", action="store_true")
    p.add_argument("--destination", action="append", choices=["github", "appstore"], default=[])
    p = commands.add_parser("prepare", help="Freeze an already audited exact PBW and install it physically; no public mutation")
    p.add_argument("version")
    p.add_argument("--audit", type=Path, required=True)
    p.add_argument("--notes", type=Path, required=True)
    p.add_argument("--description", type=Path)
    p.add_argument("--destination", action="append", choices=["github", "appstore"], required=True)
    p.add_argument("--physical", action="store_true")
    p.add_argument("--store-mode", choices=["existing", "create-or-resume"], default="existing")
    p.add_argument("--listing", type=Path)
    p = commands.add_parser("publish", help="Explicitly publish the frozen artifact; no build or auto-registration")
    p.add_argument("version")
    p.add_argument("--approve-publish", required=True)
    p.add_argument("--approve-sha256", required=True)
    p.add_argument("--approve-destination", action="append", choices=["github", "appstore"], required=True)
    p.add_argument("--approve-physical", action="store_true")
    p = commands.add_parser("verify", help="Read-only bounded verification, preserving partial status")
    p.add_argument("version")
    p.add_argument("--attempts", type=int, default=3)
    p = commands.add_parser("begin-registration", help="Approve frozen first listing and journal intent before Dashboard New; never submit/upload")
    p.add_argument("version")
    p.add_argument("--approve-publish", required=True)
    p.add_argument("--approve-sha256", required=True)
    p.add_argument("--approve-destination", action="append", choices=["github", "appstore"], required=True)
    p.add_argument("--approve-physical", action="store_true")
    p = commands.add_parser("record-registration", help="Immediately persist assigned ID, verify ownership/UUID, and record optional listing read-back")
    p.add_argument("version")
    p.add_argument("--app-id", required=True)
    p.add_argument("--confirm-listing", action="store_true")
    p.add_argument("--evidence", type=Path)
    p = commands.add_parser("reconcile-registration", help="Discover a possibly created owned UUID; never resubmit Dashboard New")
    p.add_argument("version")
    p = commands.add_parser("discover-registration", help="Read-only owned UUID/repository/release preflight; optional verified local ID adoption, never creation")
    p.add_argument("--save-match", action="store_true", help="Persist only verified existing App ID and expected listing URL locally")
    args = parser.parse_args(argv)
    if args.command == "plan":
        return plan(args)
    if args.command == "prepare":
        return prepare(args)
    if args.command == "publish":
        return publish(args)
    if args.command == "begin-registration":
        return begin_registration(args)
    if args.command == "record-registration":
        return record_registration(args)
    if args.command == "reconcile-registration":
        return reconcile_registration(args)
    if args.command == "discover-registration":
        return discover_registration(args)
    folder, state = read_manifest(args.version)
    return verify(folder, state, args.attempts)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Release stopped:", error, file=sys.stderr)
        sys.exit(1)
