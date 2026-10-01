#!/usr/bin/env python3
"""Prepare reviewed immutable snapshots and a static current/upcoming feed.

This writes local artifacts only. It neither uploads nor selects a hosting
destination. Production releases require an explicit owner-approved HTTPS URL
and a reconciliation report tied to the exact structured source bytes.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from urllib.parse import urlsplit
import zlib

ROOT = Path(__file__).resolve().parents[1]
EPOCH = dt.date(1970, 1, 1)


def compiler():
    spec = importlib.util.spec_from_file_location("kasugabus_compiler", ROOT / "tools/compile_timetable.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def strict_date(value):
    try:
        date = dt.date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError("Date must be YYYY-MM-DD") from None
    if date.isoformat() != value or not 1900 <= date.year <= 2200:
        raise ValueError("Date must be YYYY-MM-DD in 1900..2200")
    return date


def approved_base(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.port not in (None, 443):
        raise ValueError("An explicit controlled HTTPS base URL is required")
    if "%" in url or "\\" in url or any(part in (".", "..") for part in parsed.path.split("/")):
        raise ValueError("Ambiguous feed URL")
    return url.rstrip("/")


def release_metadata(payload, url):
    def day(offset):
        days = struct.unpack_from("<i", payload, offset)[0]
        if days == -2147483648:
            raise ValueError("Published releases require a known source review due date")
        return (EPOCH + dt.timedelta(days=days)).isoformat()
    return {
        "version": struct.unpack_from("<I", payload, 16)[0],
        "minAppVersion": struct.unpack_from("<I", payload, 20)[0],
        "effectiveFrom": day(124), "coverageFrom": day(24), "coverageThrough": day(28),
        "sourceVerified": day(40), "reviewDue": day(44), "url": url,
        "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
        "crc32": zlib.crc32(payload) & 0xffffffff,
    }


def verify_report(source_path, doc, report_path):
    report = read_json(report_path)
    if not isinstance(report, dict):
        raise ValueError("Review report must be an object")
    expected_hash = hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
    if report.get("releaseVersion") != doc.get("release_version") or report.get("sourceSha256") != expected_hash or report.get("departureCount") != len(doc.get("departures", [])) or report.get("reconciled") is not True:
        raise ValueError("Review report does not reconcile this exact source/release")
    if not isinstance(report.get("reviewer"), str) or not report["reviewer"].strip():
        raise ValueError("Review report must identify the reviewer")
    strict_date(report.get("reviewedAt", ""))
    return report


def departure_diff(previous, current):
    def entries(doc):
        return {(v["boarding_point_id"], v["minute"], v["pattern_id"], v["service_id"]) for v in doc.get("departures", [])}
    old, new = entries(previous or {}), entries(current)
    fields = ("operators", "stop_groups", "boarding_points", "patterns", "services", "calendar", "sources")
    return {"previousVersion": previous.get("release_version") if previous else None,
            "version": current["release_version"], "departuresAdded": sorted(new-old),
            "departuresRemoved": sorted(old-new),
            "changedSections": [name for name in fields if (previous or {}).get(name) != current.get(name)]}


def immutable_write(path, payload):
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"Immutable release already exists with different bytes: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidental concurrent overwrite of a release.
    with path.open("xb") as output:
        output.write(payload)


def prepare(current_path, upcoming_path, reports, base_url, output_dir, published, previous_path=None):
    base = approved_base(base_url)
    published_date = strict_date(published)
    build = compiler()
    docs = [read_json(current_path)] + ([read_json(upcoming_path)] if upcoming_path else [])
    if any(not isinstance(doc, dict) for doc in docs):
        raise ValueError("Timetable sources must be objects")
    paths = [current_path] + ([upcoming_path] if upcoming_path else [])
    if len(reports) != len(docs):
        raise ValueError("One exact review report is required for each release")
    coverage = docs[0].get("coverage_id")
    previous = read_json(previous_path) if previous_path else None
    releases, prepared = [], []
    for doc, path, report_path in zip(docs, paths, reports):
        report = verify_report(path, doc, report_path)
        if doc.get("coverage_id") != coverage:
            raise ValueError("Current and upcoming coverage IDs must match")
        payload = build.compile_dataset(doc)
        filename = f"releases/{doc['release_version']}-{hashlib.sha256(payload).hexdigest()[:16]}.bin"
        metadata = release_metadata(payload, base + "/" + filename)
        if strict_date(metadata["sourceVerified"]) > published_date:
            raise ValueError("Source verification cannot follow publication")
        if strict_date(metadata["reviewDue"]) < strict_date(metadata["sourceVerified"]):
            raise ValueError("Review due date precedes verification")
        releases.append(metadata)
        prepared.append((filename, payload, report, departure_diff(previous, doc)))
        previous = doc
    if strict_date(releases[0]["effectiveFrom"]) > published_date:
        raise ValueError("Current release is not yet effective")
    if len(releases) == 2 and (releases[1]["version"] <= releases[0]["version"] or strict_date(releases[1]["effectiveFrom"]) <= published_date):
        raise ValueError("Upcoming release must be newer and effective after publication")
    if previous_path and docs[0]["release_version"] <= read_json(previous_path)["release_version"]:
        raise ValueError("A correction/rollback requires a newer release version")
    feed = {"schema": 1, "coverage": coverage, "published": published,
            "current": releases[0], "upcoming": releases[1] if len(releases) == 2 else None}
    # Exercise the exact production phone validators before creating artifacts.
    with tempfile.TemporaryDirectory(prefix="kasugabus-publish-") as temp:
        feed_path = Path(temp) / "manifest.json"
        feed_path.write_text(json.dumps(feed), encoding="utf-8")
        payload_paths = []
        for n, (_, payload, _, _) in enumerate(prepared):
            path = Path(temp) / f"{n}.bin"
            path.write_bytes(payload)
            payload_paths.append(str(path))
        script = "const fs=require('fs'),m=require(process.argv[1]+'/src/pkjs/manifest'),b=require(process.argv[1]+'/src/pkjs/binary');const f=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),c={manifestUrl:process.argv[3]+'/manifest.json',coverage:f.coverage,appVersion:1,maxPayload:32768};m.validate(f,c,Date.parse(f.published+'T03:00:00Z'));[f.current,f.upcoming].filter(Boolean).forEach((r,i)=>b.validate(Array.from(fs.readFileSync(process.argv[4+i])),c,r));"
        subprocess.run(["node", "-e", script, str(ROOT), str(feed_path), base, *payload_paths], check=True, capture_output=True, text=True)
    output = Path(output_dir)
    existing_manifest = output / "manifest.json"
    if existing_manifest.exists():
        old_feed = read_json(existing_manifest)
        if releases[0]["version"] < old_feed["current"]["version"]:
            raise ValueError("Refusing a manifest downgrade")
        old_future = old_feed.get("upcoming")
        if old_future and strict_date(old_future["effectiveFrom"]) > published_date:
            if len(releases) != 2 or releases[1]["version"] < old_future["version"]:
                raise ValueError("Retain the validated upcoming release or supply a newer replacement")
    for filename, payload, _, diff in prepared:
        for existing in (output / "releases").glob(f"{diff['version']}-*.bin"):
            if existing.read_bytes() != payload:
                raise ValueError("An existing release version cannot be reused for different bytes")
    for filename, payload, report, diff in prepared:
        immutable_write(output / filename, payload)
        version = diff["version"]
        immutable_write(output / f"reports/{version}-review.json", (json.dumps(report, indent=2)+"\n").encode())
        immutable_write(output / f"reports/{version}-diff.json", (json.dumps(diff, indent=2)+"\n").encode())
    output.mkdir(parents=True, exist_ok=True)
    temp_manifest = output / "manifest.json.tmp"
    temp_manifest.write_text(json.dumps(feed, indent=2)+"\n", encoding="utf-8")
    temp_manifest.replace(output / "manifest.json")
    return feed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("current", type=Path)
    parser.add_argument("--upcoming", type=Path)
    parser.add_argument("--review-report", type=Path, action="append", required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "hosting/public")
    parser.add_argument("--published", default=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=9)).date().isoformat())
    args = parser.parse_args()
    try:
        feed = prepare(args.current, args.upcoming, args.review_report, args.base_url, args.output, args.published, args.previous)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Publication preparation failed: {error}\n")
    print(f"Prepared local current v{feed['current']['version']}" + (f" and upcoming v{feed['upcoming']['version']}" if feed["upcoming"] else "") + f" in {args.output}. Upload immutable files first; manifest last.")


if __name__ == "__main__":
    main()
