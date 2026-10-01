"""Frozen listing assets and durable first-registration state. No create API.

Dashboard New submission belongs to the authorized UI workflow. This module
only discovers owned UUIDs and records/reconciles the assigned identity.
"""
import copy
import json
from pathlib import Path
import re
import shutil
import struct
import zlib
import os
from release_common import UUID, atomic_json, digest, require, semver

METADATA = {"title", "type", "description", "source", "website", "category", "visibility", "companion_android", "companion_ios"}


def png_dimensions(raw):
    require(len(raw) >= 33 and raw[:8] == b"\x89PNG\r\n\x1a\n", "Listing artwork must be PNG")
    offset, dimensions, ended = 8, None, False
    while offset < len(raw):
        require(offset + 12 <= len(raw), "Truncated listing PNG")
        length = struct.unpack(">I", raw[offset:offset+4])[0]
        kind = raw[offset+4:offset+8]
        end = offset + 12 + length
        require(end <= len(raw), "Truncated listing PNG")
        require(zlib.crc32(raw[offset+4:end-4]) & 0xffffffff == struct.unpack(">I", raw[end-4:end])[0], "Corrupt listing PNG")
        if dimensions is None:
            require(kind == b"IHDR" and length == 13, "Missing listing PNG header")
            dimensions = struct.unpack(">II", raw[offset+8:offset+16])
        if kind == b"IEND":
            require(length == 0 and end == len(raw), "Trailing listing PNG bytes")
            ended = True
        offset = end
    require(ended, "Truncated listing PNG")
    return dimensions


def validate_listing(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    value = json.loads(path.read_text())
    require(value.get("schema") == 1 and value.get("uuid") == UUID, "Listing schema/UUID mismatch")
    metadata = value.get("metadata")
    require(isinstance(metadata, dict) and METADATA == set(metadata), "Complete reviewed listing metadata is required")
    require(metadata["title"] == "KasugaBus" and metadata["type"] == "watchapp" and metadata["visibility"] == "listed", "Unexpected new listing identity/type/visibility")
    require(all(isinstance(metadata[key], str) and metadata[key].strip() for key in ("description", "source", "category")), "Listing description/source/category are required")
    require(metadata["source"].startswith("https://") and (metadata["website"] is None or isinstance(metadata["website"], str) and metadata["website"].startswith("https://")), "Listing links must use HTTPS")
    require(all(metadata[key] is None for key in ("companion_android", "companion_ios")), "KasugaBus has no separate Android/iOS companion app")
    assets = value.get("assets")
    require(isinstance(assets, list) and assets, "Reviewed local listing artwork is required")
    bound, icons, screenshots, banners, seen = [], set(), 0, 0, set()
    for asset in assets:
        require(isinstance(asset, dict) and asset.get("role") in ("iconSmall", "iconLarge", "screenshot", "banner"), "Unknown listing asset role")
        relative = asset.get("path")
        require(isinstance(relative, str) and not Path(relative).is_absolute(), "Listing asset needs a repository-relative path")
        source = (root / relative).resolve()
        require(source.is_relative_to(root) and source.is_file() and source not in seen, "Missing/duplicate/outside-project listing asset")
        seen.add(source)
        raw = source.read_bytes()
        width, height = png_dimensions(raw)
        require(0 < width <= 4096 and 0 < height <= 4096 and len(raw) <= 4400000, "Listing artwork exceeds its bounded dimensions/bytes")
        role = asset["role"]
        if role in ("iconSmall", "iconLarge"):
            require(role not in icons, "Duplicate listing icon role")
            icons.add(role)
            require((width, height) == ((80, 80) if role == "iconSmall" else (144, 144)), "Use the reviewed store icon dimensions")
        else:
            require(asset.get("platform") == "emery", "Listing captures/artwork must target Emery")
            if role == "screenshot":
                require((width, height) == (200, 228), "Use native 200x228 Emery screenshots")
                screenshots += 1
            elif role == "banner":
                require((width, height) == (720, 320), "Use the exact 720x320 Emery banner")
                banners += 1
        bound.append(dict(asset, path=source.relative_to(root).as_posix(), sha256=digest(raw), bytes=len(raw), width=width, height=height))
    require(icons == {"iconSmall", "iconLarge"} and 1 <= screenshots <= 5 and banners == 1, "Both icons, one banner and 1..5 native Emery screenshots are required")
    return dict(value, assets=bound)


def freeze_listing(value, folder, root):
    result = copy.deepcopy(value)
    directory = Path(folder) / "listing-assets"
    directory.mkdir()
    for index, asset in enumerate(result["assets"]):
        destination = directory / ("%02d-%s.png" % (index, asset["role"]))
        shutil.copy2(Path(root) / asset["path"], destination)
        require(digest(destination.read_bytes()) == asset["sha256"], "Listing asset changed while freezing")
        asset["original_path"], asset["path"] = asset["path"], destination.relative_to(folder).as_posix()
    atomic_json(Path(folder) / "listing.json", result)
    return {"path": "listing.json", "sha256": digest((Path(folder) / "listing.json").read_bytes())}


def frozen_listing(folder, binding):
    require(isinstance(binding, dict) and binding.get("path") == "listing.json", "Missing frozen listing")
    path = Path(folder) / "listing.json"
    require(path.is_file() and digest(path.read_bytes()) == binding.get("sha256"), "Frozen listing metadata changed")
    value = json.loads(path.read_text())
    require(value.get("uuid") == UUID, "Frozen listing UUID changed")
    for asset in value["assets"]:
        path = (Path(folder) / asset["path"]).resolve()
        require(path.is_relative_to(Path(folder).resolve()) and path.is_file() and path.stat().st_size == asset["bytes"] and digest(path.read_bytes()) == asset["sha256"], "Frozen listing asset changed")
    return value


def discover_owned(config):
    """Authenticated read-only discovery, including unpublished owned apps."""
    import requests
    from pebble_tool.account import get_account
    account = get_account(auth_provider="firebase")
    require(account.is_logged_in, "Use the existing logged-in developer account")
    response = requests.get(config["appstore_api"] + "/api/v1/developer/me", headers={"Authorization": "Bearer " + account.get_access_token()}, timeout=30, allow_redirects=False)
    require(not 300 <= response.status_code < 400, "Authenticated UUID discovery redirect rejected")
    response.raise_for_status()
    payload = response.json()
    mapping = (payload.get("app_lookup") or {}).get("by_app_uuid")
    require(isinstance(mapping, dict), "Unknown authenticated app lookup; do not assume no listing exists")
    matches = [value for key, value in mapping.items() if str(key).lower() == UUID]
    require(len(matches) <= 1, "Multiple owned UUID matches; review before registration")
    from release import dashboard_session
    session, _ = dashboard_session(config)
    response = session.get(config["dashboard"] + "/api/dashboard/apps", timeout=30, allow_redirects=False)
    require(not 300 <= response.status_code < 400, "Authenticated Dashboard collection redirect rejected")
    response.raise_for_status()
    apps = response.json().get("apps")
    require(isinstance(apps, list) and all(isinstance(app, dict) for app in apps), "Unknown owned Dashboard collection; do not assume no listing exists")
    selected = []
    expected_source = "https://github.com/" + config["github_repo"]
    for app in apps:
        app_uuid = str(app.get("app_uuid") or "").lower()
        same_repo = repository_url(app.get("source")) == repository_url(expected_source)
        if app_uuid == UUID:
            selected.append(app)
        elif same_repo or app.get("title") == "KasugaBus":
            raise RuntimeError("Owned KasugaBus name/repository has a missing or conflicting UUID; inspect before New")
    require(len(selected) <= 1, "Multiple owned Dashboard UUID matches; inspect before New")
    require(bool(matches) == bool(selected), "Owned UUID mapping and Dashboard collection disagree; reconcile before New")
    if not selected:
        require(not config.get("store_app_id"), "Configured existing listing is not visible in owned discovery; reconcile, never create New")
        return None
    value = matches[0]
    require(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{24}", value) and selected[0].get("id") == value, "Owned UUID mapping and Dashboard listing identity disagree")
    return value


def repository_url(value):
    if not isinstance(value, str):
        return None
    return value.rstrip("/").removesuffix(".git").lower()


def validate_identity(app, config):
    require(isinstance(app.get("app_uuid"), str) and app["app_uuid"].lower() == UUID and app.get("id") == config.get("store_app_id"), "Registered app identity mismatch")
    require(repository_url(app.get("source")) == repository_url("https://github.com/" + config["github_repo"]), "Registered app source is not the frozen repository")
    require(app.get("type") == "watchapp" and app.get("supported_platforms") == ["emery"], "Registered app type/platform differs from Emery watchapp")
    require(isinstance(app.get("releases"), list) and all(isinstance(item, dict) and isinstance(item.get("version"), str) for item in app["releases"]), "Unknown registered release metadata")
    for item in app["releases"]:
        semver(item["version"])


def intent_path(root):
    return Path(root) / ".release" / "registration.json"


def prior_intent(root, state):
    """Keep an uncertain New attempt bound to its originally approved bytes."""
    path = intent_path(root)
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    require(value.get("schema") == 1 and value.get("uuid") == UUID, "Unknown project registration receipt; inspect before proceeding")
    if value.get("kind", "initial-new") == "initial-new" and value.get("phase") != "ready":
        require(value.get("version") == state["version"] and value.get("artifact_sha256") == state["artifact"]["sha256"], "An earlier New attempt is unresolved; reconcile its original candidate and approval before proceeding")
    return value


def reserve_intent(root, state):
    """One exclusive UUID-wide reservation; uncertain attempts never reset."""
    path = intent_path(root)
    path.parent.mkdir(exist_ok=True)
    for manifest in path.parent.glob("*/manifest.json"):
        other = json.loads(manifest.read_text())
        if other.get("version") != state["version"] and other.get("config", {}).get("uuid") == UUID and other.get("registration", {}).get("phase", "planned") != "planned":
            raise RuntimeError("Another candidate has pending/assigned registration; reconcile its UUID, never submit New again")
    value = {"schema": 1, "uuid": UUID, "version": state["version"], "artifact_sha256": state["artifact"]["sha256"], "kind": "initial-new", "phase": "creation in flight", "app_id": None}
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise RuntimeError("Project-wide registration intent already exists; reconcile instead of submitting New again")
    with os.fdopen(descriptor, "w") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def capture_id(root, state, app_id):
    """Persist UI's assigned ID before artifact, Git, or network validation."""
    url = public_url(state["config"], app_id)
    path = intent_path(root)
    current = prior_intent(root, state) or {"schema": 1, "uuid": UUID}
    require(current.get("uuid") == UUID and (not current.get("app_id") or current["app_id"] == app_id), "A different project-wide assigned ID exists; inspect before changing it")
    current.update(app_id=app_id, listing_url=url, phase="assigned; identity verification pending", version=state["version"], artifact_sha256=state["artifact"]["sha256"], kind=state["registration"].get("kind", current.get("kind", "initial-new")))
    atomic_json(path, current)
    return url


def update_intent(root, state):
    path = intent_path(root)
    current = prior_intent(root, state)
    require(current and current.get("app_id") == state["registration"]["app_id"], "Assigned registration receipt is missing or changed")
    current.update(phase=state["registration"]["phase"], kind=state["registration"].get("kind", "initial-new"))
    atomic_json(path, current)


def public_url(config, app_id):
    require(isinstance(app_id, str) and re.fullmatch(r"[a-f0-9]{24}", app_id), "Invalid assigned listing ID")
    return config["public_store"] + "/" + app_id


def transitioned_config(state):
    result = copy.deepcopy(state["config"])
    registration = state.get("registration") or {}
    if registration.get("identity_verified"):
        result["store_app_id"] = registration["app_id"]
        result["store_listing_url"] = registration["listing_url"]
    return result


def check_config(state, current):
    require(current == state["config"] or current == transitioned_config(state), "Release destinations/config changed after preparation")
