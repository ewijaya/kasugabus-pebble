#!/usr/bin/env python3
"""Reproduce the November source comparisons and metadata-only v6 audit.

Raw HTTP responses are preserved in sources.tar.gz. The notice applicability
decisions are documented in docs/DATA_RELEASE_6.md; this script checks evidence,
not human approval. Original extraction files and historical releases stay intact.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from data_build import nuxt_objects
from data_validate import validate


def require(ok, description):
    if not ok:
        raise ValueError(description)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def current_date(value):
    # Replace only the original query day, retaining revision dates and times.
    return json.loads(json.dumps(value).replace("2026-10-01", "2026-11-09"))


def trip_coordinates(value):
    # Two independently inspected provider changes at downstream stops, neither
    # used as a KasugaBus boarding coordinate. No other differences are ignored.
    for section in value["sections"]:
        for endpoint in ("arrival", "departure"):
            stop = section[endpoint]
            if stop["id"] == "00021061":
                require(stop["longitude"] in (135.516864, 135.516865), "Unexpected Handai-guchi longitude")
                stop["longitude"] = 135.516865
            if stop["id"] == "00020764":
                require(stop["latitude"] in (34.819296, 34.819297), "Unexpected 2-chome South latitude")
                stop["latitude"] = 34.819297
    return value


def main():
    baseline = ROOT / "data/timetable_v5.json"
    original = json.loads(baseline.read_text())
    # Re-run full matrix, independent pole, route, holiday and station-minute
    # reconstruction, rather than trusting the prior release's audit flag.
    report = validate(baseline)
    candidate_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/timetable_v6.json"
    candidate_raw = candidate_path.read_bytes()
    candidate = json.loads(candidate_raw)
    expected = dict(original, release_version=6, source_verified_at="2026-11-09", review_due="2026-12-01")
    require(candidate == expected, "v6 must change only release and source-review dates")
    fetched = json.loads((HERE / "fetch.json").read_text())
    archive = HERE / "sources.tar.gz"
    require(sha(archive.read_bytes()) == fetched["archiveSha256"], "Source archive digest mismatch")
    records = {r["id"]: r for r in fetched["records"]}
    require(len(records) == len(fetched["records"]), "Duplicate fetch IDs")
    sources = {s["id"]: s for s in original["sources"]}
    require(set(sources) <= records.keys(), "Incomplete original-source fetch")
    require(fetched["checkedAt"] == "2026-11-09", "Unexpected review date")
    with tarfile.open(archive) as tar:
        content = {}
        for r in records.values():
            member = tar.getmember(r["path"])
            require(member.isfile() and member.size == r["bytes"], "Unexpected archive entry")
            raw = tar.extractfile(member).read()
            require(sha(raw) == r["sha256"], "Fetched source digest mismatch: " + r["id"])
            content[r["id"]] = raw

    checks = []
    pdf_ids = [s["id"] for s in sources.values() if s["id"].startswith("kintetsu") and s["path"].endswith(".pdf")]
    for sid in pdf_ids + ["holidays", "holiday_calendar_page", "kintetsu_directory", "kintetsu_loop_notice"]:
        require(records[sid]["sha256"] == sources[sid]["sha256"], "Reviewed source changed: " + sid)
        require(records[sid]["url"] == records[sid]["final_url"], "Primary source redirected: " + sid)
    checks.append(f"{len(pdf_ids)} Kintetsu PDFs, national calendar, line directory and loop notice byte-identical")
    directory = content["kintetsu_directory"].decode()
    for n in range(5):
        require(sources[f"kintetsu_{n}"]["url"] in directory, "Current matrix link replaced")
    for n in range(1, 9):
        links = set(re.findall(r'https://[^\s\"<>]+\.pdf', content[f"kintetsu_stop_{n}"].decode()))
        expected_links = {s["url"] for sid, s in sources.items() if sid.startswith(f"kintetsu_stop_{n}_direction_")}
        require(links == expected_links, f"Current pole links changed at stop {n}")
    checks.append("Current Kintetsu directory links resolve to all five matrices and all 12 boarding-pole sheets")

    with tempfile.TemporaryDirectory() as folder:
        def structured(sid, key, old=False):
            if old:
                path = ROOT / sources[sid]["path"]
            else:
                path = Path(folder) / (sid + ".html")
                path.write_bytes(content[sid])
            return next(o for o in nuxt_objects(path) if key in o)

        for sid in sources:
            if re.fullmatch(r"hankyu_\d{6}", sid):
                old = current_date(structured(sid, "schedules", True))
                new = structured(sid, "schedules")
                require(old == new, "Hankyu schedule/revision changed: " + sid)
                require(all(s["scheduleName"] == "平日" for s in new["schedules"]), "Unexpected service days")
            elif sid.startswith("hankyu_trip_"):
                old = trip_coordinates(current_date(structured(sid, "sections", True)))
                new = trip_coordinates(structured(sid + "_current", "sections"))
                require("2026-11-09" in records[sid + "_current"]["url"], "Trip query used historical date")
                require(old == new, "Hankyu trip route/time/calls changed: " + sid)
    checks.append("All six Hankyu schedules and 38 individual trips checked for November 9; route IDs, times, calls and service days unchanged")
    for sid in sources:
        if sid.startswith("hankyu_poles_"):
            old = current_date(json.loads((ROOT / sources[sid]["path"]).read_text()))
            new = json.loads(content[sid])
            require(old == new, "Hankyu pole/generation changed")
            require(len(new["generations"]) == 1 and new["generations"][0]["isCurrent"], "Future generation needs review")
        if sid.startswith("osm_"):
            for old in json.loads((ROOT / sources[sid]["path"]).read_text())["platforms"]:
                new = json.loads(content["osm_node_" + str(old["node_id"])])["elements"][0]
                require((old["latitude"], old["longitude"], old["tags"], old["version"]) ==
                        (new["lat"], new["lon"], new["tags"], new["version"]), "OSM boarding node changed")
    checks.append("Six Hankyu poles have no announced future generation; all three community-mapped boarding nodes unchanged")
    news = json.loads(content["hankyu_news"])
    require(len(news) == 227, "Unexpected Hankyu notice evidence")
    checks.append("Operator notice decisions and retained year-end coverage documented in docs/DATA_RELEASE_6.md")
    report.update(releaseVersion=6, sourceSha256=sha(candidate_raw), reviewedAt="2026-11-09",
                  reviewer="Codex, owner-requested monthly source review; byte and structured comparisons against official current sources; no new human visual review claimed",
                  releasePurpose="monthly_source_review", baseReleaseVersion=5,
                  baseSourceSha256=sha(baseline.read_bytes()),
                  reviewEvidence="data/reviews/2026-11-09/fetch.json",
                  evidenceArchiveSha256=fetched["archiveSha256"])
    report["checks"] += checks
    report["limitations"] = [
        "No 2026-27 operator year-end schedule verified; coverage remains through 2026-12-27.",
        "Original source entries retain their extraction provenance; fresh review evidence is archived separately.",
        "The old supplementary Hankyu route PDF now redirects to the search site; current pole timetables and individual trips supply the evidence.",
        "Station minutes retain v5's line-matrix-only verification; no new independent station-arrival evidence.",
        "Train timetable resources bundled in the PBW are outside this bus-feed release."
    ]
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
