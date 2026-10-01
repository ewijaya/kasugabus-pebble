"""Shared local release checks; importing this module has no side effects."""
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
UUID = "d7ba77b0-d528-4cc8-b35c-7052798152c9"
ARTIFACT = "kasugabus-pebble.pbw"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_fingerprint(root=ROOT):
    """Hash build/runtime/test inputs; release text/config is bound separately."""
    root = Path(root)
    excluded = {".git", ".release", "build", "node_modules", "__pycache__", "artifacts"}
    paths = []
    for name in ("src", "resources", "data", "tools", "scripts", "tests"):
        for directory, dirs, names in os.walk(root / name):
            dirs[:] = sorted(name for name in dirs if name not in excluded)
            for filename in names:
                if filename.endswith(".pyc") or filename == ".DS_Store" or filename.startswith((".waf", ".lock-waf")):
                    continue
                paths.append(Path(directory) / filename)
    for name in ("package.json", "package-lock.json", "wscript"):
        if (root / name).is_file():
            paths.append(root / name)
    files = sorted(path.relative_to(root).as_posix() for path in paths)
    hasher = hashlib.sha256()
    for relative in files:
        hasher.update(relative.encode() + b"\0")
        hasher.update(bytes.fromhex(digest((root / relative).read_bytes())))
    return {"fingerprint": hasher.hexdigest(), "files": files}


def inspect_pbw(path, version):
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        require(len(archive.namelist()) == len(set(archive.namelist())), "PBW contains duplicate archive entries")
        info = json.loads(archive.read("appinfo.json"))
        require(info.get("uuid") == UUID and info.get("versionLabel") == version, "PBW UUID/version mismatch")
        require(info.get("targetPlatforms") == ["emery"] and info.get("watchapp", {}).get("watchface") is False, "Expected an Emery-only interactive app")
        require(info.get("longName", info.get("displayName")) == "KasugaBus", "PBW display name mismatch")
        require("pebble-js-app.js" in archive.namelist() and "emery/pebble-app.bin" in archive.namelist(), "Missing watch/phone binary")
        binary = archive.read("emery/pebble-app.bin")
        require(binary.startswith(b"PBLAPP\0\0"), "Missing Pebble process header")
        require(not any(name.split("/")[0] in ("aplite", "basalt", "chalk", "diorite", "flint", "gabbro") for name in archive.namelist()), "Unexpected platform payload")
    return {"sha256": digest(path.read_bytes()), "bytes": path.stat().st_size}


def semver(version):
    require(isinstance(version, str) and bool(re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version)), "Use a numeric semantic version")
    return tuple(map(int, version.split(".")))


def load_config(root=ROOT):
    config = json.loads((Path(root) / "docs/release-config.json").read_text())
    require(config.get("schema") == 1 and config.get("uuid") == UUID and config.get("display_name") == "KasugaBus" and config.get("platforms") == ["emery"] and config.get("artifact_name") == ARTIFACT, "Unexpected release project identity")
    require(config.get("appstore_api") == "https://appstore-api.repebble.com" and config.get("dashboard") == "https://developer.repebble.com" and config.get("public_store") == "https://apps.repebble.com", "Unexpected official store destination")
    return config


def require_destinations(config, destinations, store_mode="existing"):
    require(bool(destinations) and len(set(destinations)) == len(destinations) and set(destinations) <= {"github", "appstore"}, "Choose distinct release destinations")
    if "github" in destinations:
        require(isinstance(config.get("github_repo"), str) and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", config["github_repo"]), "GitHub repository is not configured")
    if "appstore" in destinations:
        require(store_mode in ("existing", "create-or-resume"), "Unknown store publication mode")
        if store_mode == "create-or-resume":
            require(config.get("store_app_id") is None or isinstance(config["store_app_id"], str) and re.fullmatch(r"[a-f0-9]{24}", config["store_app_id"]), "Invalid existing registration identity")
            require(config.get("public_catalog_path") == "/api/v1/apps/uuid/{uuid}", "Public catalog contract needs review")
            return
        require(isinstance(config.get("store_app_id"), str) and re.fullmatch(r"[a-f0-9]{24}", config["store_app_id"]), "KasugaBus is not registered: use the approved first-registration flow and record its own app ID")
        require(config.get("public_catalog_path") == "/api/v1/apps/uuid/{uuid}", "Public catalog contract needs review")
        require(config.get("listing_patch_contract") in ("partial-description", "dashboard-form-v1", "dashboard-form-2026-10-01"), "Confirm current official Dashboard PATCH behavior before store preparation; no guessed metadata update")


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
