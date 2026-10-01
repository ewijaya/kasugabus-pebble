#!/usr/bin/env python3
"""Read-only validation of a reviewed static feed before artifact staging.

No review is generated, no feed file is changed, and no deployment API is used.
Current/upcoming payloads must match exact reviewed JSON input bytes and an
in-memory compiler result. Historical payloads need the same archived source
proof, or an unchanged hash pin from the existing controlled live inventory.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://ewijaya.github.io/kasugabus-pebble/timetables"
COVERAGE = "minami-kasugaoka-v1"
MAX_PAYLOAD = 32768
MAX_MANIFEST = 8192
MAX_RELEASES = 4096
MAX_JSON = 5 * 1024 * 1024
FILENAME = re.compile(r"releases/([1-9][0-9]*)-([a-f0-9]{16})\.bin\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


publisher = load_module("kasugabus_publish_readonly", ROOT / "tools/publish_feed.py")


def json_bytes(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError("Non-finite JSON number")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=invalid_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid UTF-8 JSON") from error


def regular_bytes(path, limit):
    path = Path(path)
    # Check every path component as well as the final file: source directories
    # and artifact inputs cannot redirect outside the reviewed tree.
    path = path.absolute()
    for component in (path, *path.parents):
        # macOS exposes standard temporary directories through OS aliases.
        # Their canonical locations are outside the reviewed feed tree.
        if sys.platform == "darwin" and str(component) in ("/var", "/tmp"):
            continue
        if component.is_symlink():
            raise ValueError(f"Symlink input is forbidden: {path}")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
        raise ValueError(f"Expected bounded regular file without hard links: {path}")
    raw = path.read_bytes()
    if len(raw) > limit:
        raise ValueError(f"File exceeds bound: {path}")
    return raw


def read_json(path):
    return json_bytes(regular_bytes(path, MAX_JSON))


def integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def file_record(path, raw):
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def validate_inventory(value, coverage=COVERAGE):
    if not isinstance(value, dict) or set(value) != {"schema", "coverage", "files"} or type(value["schema"]) is not int or value["schema"] != 1 or value["coverage"] != coverage:
        raise ValueError("Invalid live inventory schema/coverage")
    files = value["files"]
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_RELEASES:
        raise ValueError("Invalid live inventory file count")
    paths, versions = {}, set()
    for record in files:
        if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
            raise ValueError("Invalid live inventory record")
        match = FILENAME.fullmatch(record["path"]) if isinstance(record["path"], str) else None
        digest = record["sha256"]
        if not match or not isinstance(digest, str) or not SHA256.fullmatch(digest) or match[2] != digest[:16] or not integer(record["bytes"], 128, MAX_PAYLOAD):
            raise ValueError("Invalid live inventory filename/checksum")
        version = int(match[1])
        if not integer(version, 1, 4294967295) or version in versions or record["path"] in paths:
            raise ValueError("Duplicate live inventory path/version")
        versions.add(version)
        paths[record["path"]] = record
    return paths


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def fetch_json(url):
    """Bounded HTTPS GET; only an actual 404 represents a missing first feed."""
    publisher.approved_base(url)
    request = Request(url, headers={"Accept": "application/json", "Cache-Control": "no-cache",
                                    "User-Agent": "KasugaBus-hosting-validator/1"})
    try:
        with build_opener(NoRedirect()).open(request, timeout=15) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError("Live feed changed URL or did not return HTTP 200")
            limit = MAX_MANIFEST if url.endswith("/manifest.json") else MAX_JSON
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise ValueError("Live JSON exceeds bound")
            return json_bytes(raw)
    except HTTPError as error:
        if error.code == 404:
            return None
        raise ValueError(f"Live feed HTTP failure: {error.code}") from error
    except (URLError, TimeoutError, OSError) as error:
        raise ValueError("Live feed could not be checked; refusing publication") from error


def phone_validate(feed, releases, base, validation_date, historical_date=False):
    """Use the shipped phone manifest and full binary parsers, without copies."""
    script = r"""
const fs=require('fs'),m=require(process.argv[1]+'/src/pkjs/manifest'),b=require(process.argv[1]+'/src/pkjs/binary');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const config={manifestUrl:input.base+'/manifest.json',coverage:input.coverage,appVersion:1,maxPayload:32768};
if(input.feed)m.validate(input.feed,config,Date.parse(input.date+'T03:00:00Z'));
input.releases.forEach(item=>b.validate(Array.from(fs.readFileSync(item.file)),config,item.metadata));
"""
    date = feed["published"] if historical_date else validation_date
    request = {"feed": feed, "releases": releases, "base": base, "coverage": COVERAGE, "date": date}
    result = subprocess.run(["node", "-e", script, str(ROOT)], input=json.dumps(request),
                            text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError("Production phone validation rejected the feed/payload: " + result.stderr.strip()[-1000:])


def get_live(base, today, fetcher=fetch_json):
    manifest = fetcher(base + "/manifest.json")
    inventory = fetcher(base + "/inventory.json")
    if manifest is None and inventory is None:
        return None, {}
    if manifest is None or inventory is None:
        raise ValueError("Live manifest/inventory missing; cannot prove preserved history")
    if not isinstance(manifest, dict):
        raise ValueError("Invalid live manifest")
    if publisher.strict_date(manifest.get("published")) > publisher.strict_date(today):
        raise ValueError("Live publication date is in the future")
    phone_validate(manifest, [], base, today, historical_date=True)
    pins = validate_inventory(inventory)
    for release in (manifest["current"], manifest.get("upcoming")):
        if not release:
            continue
        path = release["url"].removeprefix(base + "/")
        if release["url"] != base + "/" + path or path not in pins or pins[path]["sha256"] != release["sha256"] or pins[path]["bytes"] != release["bytes"]:
            raise ValueError("Live manifest payload is not pinned by its inventory")
    return manifest, pins


def guard_live(candidate, files, previous, pins, today):
    local = {record["path"]: record for record in files}
    for path, pin in pins.items():
        if local.get(path) != pin:
            raise ValueError("Previously published immutable payload missing or changed: " + path)
    if previous is None:
        return
    def key(release):
        return (release["effectiveFrom"], release["version"])
    effective = [r for r in (previous["current"], previous.get("upcoming")) if r and r["effectiveFrom"] <= today]
    old = max(effective, key=key)
    current = candidate["current"]
    if key(current) < key(old) or (key(current) == key(old) and current != old):
        raise ValueError("Refusing live effective-date/version downgrade or changed immutable metadata")
    future = previous.get("upcoming")
    if future and future["effectiveFrom"] > today:
        replacement = candidate.get("upcoming")
        # Installed watches retain pending releases. A different activation date
        # cannot cancel that release safely through the current feed protocol.
        if not replacement or replacement["effectiveFrom"] != future["effectiveFrom"] or replacement["version"] < future["version"] or (replacement["version"] == future["version"] and replacement != future):
            raise ValueError("Retain pending activation date and payload, or provide a higher version at that same date")
    if candidate["published"] < previous["published"]:
        raise ValueError("Refusing live publication-date downgrade")


def validate_existing(directory, base_url=BASE_URL, sources=(), validation_date=None,
                      check_live=False, fetcher=fetch_json, allow_first_deployment=False):
    base = publisher.approved_base(base_url)
    today = validation_date or (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).date().isoformat()
    publisher.strict_date(today)
    directory = Path(directory)
    manifest_raw = regular_bytes(directory / "manifest.json", MAX_MANIFEST)
    feed = json_bytes(manifest_raw)
    if not isinstance(feed, dict) or set(feed) != {"schema", "coverage", "published", "current", "upcoming"}:
        raise ValueError("Manifest must have the exact production fields")
    if feed.get("coverage") != COVERAGE:
        raise ValueError("Unsupported feed coverage")
    if publisher.strict_date(feed.get("published")) > publisher.strict_date(today):
        raise ValueError("Publication date follows validation date")
    previous, pins = get_live(base, today, fetcher) if check_live else (None, {})
    if check_live and previous is None and not allow_first_deployment:
        raise ValueError("First feed deployment requires explicit approval of a dedicated Pages site; missing timetable paths do not prove the whole site is empty")
    source_inputs = {}
    for path in sources:
        raw = regular_bytes(path, MAX_JSON)
        digest = hashlib.sha256(raw).hexdigest()
        if digest in source_inputs:
            continue
        document = json_bytes(raw)
        if not isinstance(document, dict):
            raise ValueError("Reviewed source must be a JSON object")
        source_inputs[digest] = (Path(path), document)
    active = {}
    for release in (feed["current"], feed.get("upcoming")):
        if not isinstance(release, dict) and release is not None:
            raise ValueError("Release must be an object")
        if release:
            if not isinstance(release.get("url"), str) or not release["url"].startswith(base + "/"):
                raise ValueError("Release URL must be under the exact feed base")
            path = release["url"][len(base) + 1:]
            if not FILENAME.fullmatch(path) or path in active:
                raise ValueError("Invalid manifest filename or duplicate release")
            active[path] = release
    if not feed["current"]:
        raise ValueError("Current release missing")
    release_dir = directory / "releases"
    if not release_dir.is_dir() or release_dir.is_symlink():
        raise ValueError("Release directory missing or symlinked")
    entries = sorted(release_dir.iterdir())
    if not 1 <= len(entries) <= MAX_RELEASES:
        raise ValueError("Invalid release file count")
    files, validations, seen_versions, source_proofs = [], [], set(), {}
    build = publisher.compiler()
    for path in entries:
        relative = "releases/" + path.name
        match = FILENAME.fullmatch(relative)
        if not match:
            raise ValueError("Unexpected file in immutable releases: " + path.name)
        raw = regular_bytes(path, MAX_PAYLOAD)
        if len(raw) < 128:
            raise ValueError("Payload is too short")
        record = file_record(relative, raw)
        metadata = publisher.release_metadata(raw, base + "/" + relative)
        version = metadata["version"]
        if str(version) != match[1] or match[2] != record["sha256"][:16] or version in seen_versions:
            raise ValueError("Filename/version/hash mismatch or reused release version")
        seen_versions.add(version)
        if relative in active and metadata != active[relative]:
            raise ValueError("Manifest metadata/checksum differs from frozen payload")
        if publisher.strict_date(metadata["sourceVerified"]) > publisher.strict_date(today):
            raise ValueError("Payload source verification follows validation date")
        report_path = directory / f"reports/{version}-review.json"
        report = read_json(report_path)
        if not isinstance(report, dict) or report.get("reconciled") is not True or not integer(report.get("releaseVersion"), 1, 4294967295) or report["releaseVersion"] != version or not isinstance(report.get("sourceSha256"), str) or not SHA256.fullmatch(report["sourceSha256"]) or not integer(report.get("departureCount"), 0, 65535) or not isinstance(report.get("reviewer"), str) or not report["reviewer"].strip():
            raise ValueError("Missing or incomplete exact-source review report")
        reviewed = publisher.strict_date(report.get("reviewedAt"))
        if not publisher.strict_date(metadata["sourceVerified"]) <= reviewed <= publisher.strict_date(today):
            raise ValueError("Review date does not follow source verification or is future")
        # Table 7 holds five-byte departure records; the phone parser checks the
        # table layout independently below before this count is trusted.
        if report["departureCount"] != struct.unpack_from("<H", raw, 68 + 7 * 6)[0]:
            raise ValueError("Review departure count differs from payload")
        source = source_inputs.get(report["sourceSha256"])
        if source:
            source_path, document = source
            publisher.verify_report(source_path, document, report_path)
            if build.compile_dataset(document) != raw:
                raise ValueError("Frozen payload differs from exact reviewed source compiler bytes")
            source_proofs[relative] = "exact_reviewed_source"
        elif relative not in active and pins.get(relative) == record:
            source_proofs[relative] = "unchanged_live_inventory_pin"
        else:
            raise ValueError("Exact reviewed source input required for active or unpinned historical payload: " + relative)
        files.append(record)
        validations.append({"file": str(path), "metadata": metadata})
    if not set(active).issubset({record["path"] for record in files}):
        raise ValueError("Manifest references a missing payload")
    phone_validate(feed, validations, base, today)
    if check_live:
        guard_live(feed, files, previous, pins, today)
    return {"validated": True, "baseUrl": base, "validationDate": today,
            "manifestSha256": hashlib.sha256(manifest_raw).hexdigest(),
            "currentVersion": feed["current"]["version"],
            "upcomingVersion": feed["upcoming"]["version"] if feed["upcoming"] else None,
            "liveChecked": check_live, "firstDeployment": check_live and previous is None,
            "sourceProofs": source_proofs,
            "inventory": {"schema": 1, "coverage": COVERAGE, "files": files}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--source", type=Path, action="append", default=[])
    parser.add_argument("--source-directory", type=Path, action="append", default=[])
    parser.add_argument("--validation-date", help="Explicit test/review date; workflow uses actual JST date")
    parser.add_argument("--check-live", action="store_true", help="Read controlled live manifest/inventory and enforce preservation")
    parser.add_argument("--allow-first-deployment", action="store_true", help="Owner confirms dedicated Pages site; absence of timetable files is not approval to replace unrelated site content")
    args = parser.parse_args()
    try:
        sources = list(args.source)
        for directory in args.source_directory:
            if directory.exists():
                if directory.is_symlink() or not directory.is_dir():
                    raise ValueError("Source archive must be a real directory")
                sources.extend(sorted(directory.glob("*.json")))
        if args.allow_first_deployment and not args.check_live:
            raise ValueError("First-deployment approval requires --check-live")
        result = validate_existing(args.directory, args.base_url, sources, args.validation_date,
                                   args.check_live, allow_first_deployment=args.allow_first_deployment)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Hosting validation failed: {error}\n")
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
