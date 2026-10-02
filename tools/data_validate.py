#!/usr/bin/env python3
"""Audit every canonical departure against preserved source cells and trips."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path

from data_build import DATA, ROOT, build, clock_minute, nuxt_objects, pole_minutes


def validate(path=None, extended=None):
    path = Path(path or DATA / "timetable.json")
    raw = path.read_bytes()
    data = json.loads(raw)
    # The feed-only v3 snapshot adds 日本庭園前 (group 7, points 10/11) from
    # data/sources/catalog_nihon_teien.json; everything else is the baseline.
    extended = any(p["id"] in (10, 11) for p in data["boarding_points"]) if extended is None else extended
    errors = []

    def check(condition, description):
        if not condition:
            errors.append(description)

    def ids(name):
        rows = data[name]
        found = {r["id"]: r for r in rows}
        check(len(found) == len(rows), f"duplicate {name} ID")
        return found

    sources = ids("sources")
    points = ids("boarding_points")
    patterns = ids("patterns")
    services = ids("services")
    operators = ids("operators")
    groups = ids("stop_groups")
    review = json.loads((DATA / "review_evidence.json").read_text())
    reviewed = {s["id"]: s["sha256"] for s in review["sources"]}
    if extended:
        extension_review = json.loads((DATA / "review_evidence_nihon_teien.json").read_text())
        reviewed.update({s["id"]: s["sha256"] for s in extension_review["sources"]})
    check(review["reviewed_at"] == data["source_verified_at"], "source verification date does not match review")
    check(reviewed == {s["id"]: s["sha256"] for s in sources.values()},
          "sources changed since explicit visual and structured review")
    check(len(groups) == (7 if extended else 6), "stop group count changed")
    check(set(operators) == {1, 2}, "operator identities changed")
    check(len(points) == (17 if extended else 15), "boarding identity count changed")
    for source in sources.values():
        source_path = ROOT / source["path"]
        check(source_path.exists(), f"source missing: {source['id']}")
        if source_path.exists():
            check(hashlib.sha256(source_path.read_bytes()).hexdigest() == source["sha256"], f"source checksum changed: {source['id']}")
    for extraction in json.loads((DATA / "extraction" / "manifest.json").read_text()):
        grid_path = ROOT / extraction["path"]
        check(hashlib.sha256(grid_path.read_bytes()).hexdigest() == extraction["sha256"], f"extraction grid changed: {grid_path.name}")
        source_path = ROOT / extraction["source_path"]
        check(hashlib.sha256(source_path.read_bytes()).hexdigest() == extraction["source_sha256"], f"extraction source changed: {source_path.name}")
    coordinate_review = json.loads((DATA / "coordinate_review.json").read_text())
    for evidence in coordinate_review["evidence_files"]:
        evidence_path = ROOT / evidence["path"]
        check(hashlib.sha256(evidence_path.read_bytes()).hexdigest() == evidence["sha256"], "coordinate investigation evidence changed")
    for artifact in review["visual_artifacts"]:
        artifact_path = ROOT / artifact["path"]
        check(hashlib.sha256(artifact_path.read_bytes()).hexdigest() == artifact["sha256"], "visual review artifact changed")
    for point in points.values():
        check(point["stop_group_id"] in groups and point["operator_id"] in operators, f"bad boarding point reference: {point['id']}")
        coordinate = point.get("coordinate")
        if coordinate and point.get("coordinate_status") == "community_mapped_corroborated":
            ev = point["coordinate_evidence"]
            osm = json.loads((ROOT / sources[ev["source_id"]]["path"]).read_text())
            nodes = [n for n in osm["platforms"] if n["node_id"] == ev["node_id"]]
            check(extended and point["id"] in (10, 11) and len(nodes) == 1, f"community coordinate outside its reviewed scope: {point['id']}")
            if nodes:
                check(coordinate == {"latitude": nodes[0]["latitude"], "longitude": nodes[0]["longitude"]}, f"community coordinate altered: {point['id']}")
        elif coordinate:
            ev = point["coordinate_evidence"]
            poles = json.loads((ROOT / sources[ev["source_id"]]["path"]).read_text())
            matches = [pole for g in poles["generations"] if g["isCurrent"] for pole in g["poles"] if pole["id"] == ev["pole_id"]]
            check(len(matches) == 1, f"pole coordinate not uniquely evidenced: {point['id']}")
            if matches:
                pole = matches[0]
                check(coordinate == {"latitude": pole["latitude"], "longitude": pole["longitude"]}, f"pole coordinate altered: {point['id']}")
                check(pole["name"] == point["direction_ja"], f"pole direction mismatch: {point['id']}")
                check(any(cg["timetableId"] == ev["timetable_id"] for cg in pole["courseGroups"]), f"pole timetable mapping mismatch: {point['id']}")
        else:
            check(point.get("coordinate_status") == "excluded_unverified" and bool(point.get("coordinate_reason")), f"missing coordinate exclusion: {point['id']}")

    # Closure: every numeric source cell in the target rows must appear exactly
    # once, and no other cell may be emitted. Blank cells/arrows are excluded.
    target_rows = {0: {14: 1, 15: 2, 13: 3}, 1: {14: 1, 15: 2, 13: 3}}
    for i in [2, 3, 4]:
        target_rows[i] = {17: 4, 19: 6, 20: 8, 23: 9, 24: 7, 26: 5}
        if extended:
            target_rows[i].update({14: 10, 27: 11})
    expected = Counter()
    grids = {}
    for number, rows in target_rows.items():
        pages = json.loads((DATA / "extraction" / f"kintetsu_{number}_tables.json").read_text())
        for page in pages:
            for row_index, bp in rows.items():
                table = page["rows"]
                check(table[row_index][0] == groups[points[bp]["stop_group_id"]]["name_ja"], "source stop row changed")
                for column in range(1, len(table[0])):
                    value = clock_minute(table[row_index][column])
                    if value is not None:
                        target = bp
                        if bp == 10 and not any(clock_minute(table[r][column]) is not None for r in range(15, 26)):
                            # Route 12: starts here for Ibaraki (point 11) or terminates here.
                            check(table[0][column] == "12", "unexpected non-Handai cell on the Handai row")
                            if clock_minute(table[28][column]) is None:
                                continue
                            target = 11
                        expected[(f"kintetsu_{number}", page["page"], row_index + 1, column, target, value)] += 1
            grids[(f"kintetsu_{number}", page["page"])] = page["rows"]
    actual = Counter()
    independent = Counter()
    hankyu_actual = Counter()
    for departure in data["departures"]:
        bp, pid, sid, minute = (departure[k] for k in ["boarding_point_id", "pattern_id", "service_id", "minute"])
        check(bp in points and pid in patterns and sid in services, "departure references missing identity")
        if bp not in points or pid not in patterns or sid not in services:
            continue
        check(0 <= minute < 2880, "invalid service-day minute")
        check(patterns[pid]["operator_id"] == points[bp]["operator_id"] == services[sid]["operator_id"], "operator mismatch")
        ev = departure["evidence"]
        check(ev["source_id"] in sources, "departure source not preserved")
        if ev["source_id"].startswith("kintetsu_"):
            key = (ev["source_id"], ev["page"], ev["row"], ev["column"], bp, minute)
            actual[key] += 1
            table = grids[(ev["source_id"], ev["page"])]
            check(table[0][ev["column"]] == ev["source_route_label"], "matrix route evidence mismatch")
            pole = ev["independent_pole"]
            for day_type in services[sid]["day_types"]:
                independent[(bp, day_type, minute)] += 1
            stop = points[bp]["evidence"][0]["source_id"]
            stop_number, direction = map(int, re.match(r"kintetsu_stop_(\d+)_direction_(\d+)", stop).groups())
            first_day = services[sid]["day_types"][0]
            check(pole == pole_minutes(stop_number, direction).get((first_day, minute)), "independent pole locator or route marker differs from source")
            expected_mark = pole["mark"]
            source_route = ev["source_route_label"]
            if bp in [1, 2, 3]:
                route = "1" if expected_mark == "Ｊ" else "2"
            elif bp in [5, 7, 9, 11]:
                route = "12" if source_route == "12" else "22"
            elif expected_mark in ["★", "▲"]:
                route = "25"
            else:
                route = "24" if source_route == "24" else "22"
            check(patterns[pid]["boarding_route"] == route, f"wrong boarded route: bp{bp} minute{minute}")
            check(patterns[pid]["boarding_route"] != "12" or (extended and bp == 11), "out-of-scope route 12 included")
        else:
            obj = next(o for o in nuxt_objects(ROOT / sources[ev["source_id"]]["path"]) if "schedules" in o)
            col = obj["schedules"][ev["schedule_index"]]["columns"][ev["column_index"]]
            trip = col["trips"][ev["trip_index"]]
            check(trip["id"] == ev["operator_trip_id"], "Hankyu trip identity mismatch")
            check(clock_minute(trip["departureTime"][11:16]) == minute, "Hankyu trip time mismatch")
            sections = next(o["sections"] for o in nuxt_objects(ROOT / sources[ev["route_source_id"]]["path"]) if "sections" in o)
            section = sections[ev["section_index"]]
            check(section["departureTime"] == trip["departureTime"], "Hankyu detail departure differs from timetable")
            route = re.match(r"\[(\d+)\]", section["destination"]).group(1)
            check(patterns[pid]["boarding_route"] == route, "Hankyu 72/164 grouped-column route incorrectly flattened")
            check([s["arrival"]["name"] for s in sections[ev["section_index"]:]] == [c["name_ja"] for c in patterns[pid]["downstream_calls"]], "Hankyu downstream call mismatch")
            hankyu_actual[(ev["source_id"], ev["schedule_index"], ev["column_index"], ev["trip_index"])] += 1
    check(actual == expected, f"Kintetsu matrix closure failed: {len(actual)} emitted, {len(expected)} expected")

    mapping = {1: (1, 1), 2: (2, 1), 3: (3, 1), 4: (4, 1), 5: (4, 2),
               6: (5, 1), 7: (5, 2), 8: (6, 1), 9: (6, 2)}
    if extended:
        mapping.update({10: (7, 1), 11: (7, 2)})
    independent_expected = Counter()
    for bp, (stop, direction) in mapping.items():
        for day_type, minute in pole_minutes(stop, direction):
            independent_expected[(bp, day_type, minute)] += 1
    check(independent == independent_expected, "independent Kintetsu pole timetable closure failed")
    hankyu_expected = Counter()
    for source_id in ["hankyu_" + tid for tid in ["083801", "083802", "138401", "138402", "138501", "138502"]]:
        obj = next(o for o in nuxt_objects(ROOT / sources[source_id]["path"]) if "schedules" in o)
        for si, sch in enumerate(obj["schedules"]):
            check(sch["scheduleName"] == "平日", "unexpected Hankyu service day")
            for ci, col in enumerate(sch["columns"]):
                for ti, trip in enumerate(col["trips"]):
                    hankyu_expected[(source_id, si, ci, ti)] += 1
    check(hankyu_actual == hankyu_expected, "Hankyu source-trip closure failed")
    check(operators[2]["day_types"] == [1] and operators[2]["no_service_day_types"] == [2, 3], "Hankyu weekend fallback would invent service")

    holiday_csv = (ROOT / sources["holidays"]["path"]).read_bytes().decode("cp932")
    holiday_rows = list(csv.reader(io.StringIO(holiday_csv)))
    holiday_expected = []
    for number, row in enumerate(holiday_rows, 1):
        if not re.fullmatch(r"\d{4}/\d{1,2}/\d{1,2}", row[0]):
            continue
        y, m, d = map(int, row[0].split("/"))
        if y in [2026, 2027]:
            holiday_expected.append({"date": f"{y:04}-{m:02}-{d:02}", "name_ja": row[1], "source_id": "holidays", "csv_row": number})
    check(data["calendar"]["holidays"] == holiday_expected, "Cabinet Office holiday closure failed")
    for holiday in data["calendar"]["holidays"]:
        row = holiday_rows[holiday["csv_row"] - 1]
        y, m, d = map(int, row[0].split("/"))
        check(holiday["date"] == f"{y:04}-{m:02}-{d:02}" and holiday["name_ja"] == row[1], "Cabinet Office holiday row mismatch")
    check(any(h["date"] == "2026-09-22" for h in data["calendar"]["holidays"]), "citizens holiday omitted")
    check(any(h["date"] == "2026-05-06" for h in data["calendar"]["holidays"]), "substitute holiday omitted")
    check(data["calendar"]["coverage_from"] == "2026-10-01" and data["calendar"]["coverage_until"] == "2026-12-27", "calendar coverage silently extended")
    for operator in operators.values():
        check(operator["valid_from"] == data["valid_from"] and operator["valid_until"] == data["valid_until"], "operator validity silently extended")
    check(len(data["departures"]) == data["validation"]["departure_count"], "generated departure count mismatch")
    check(len(data["departures"]) == (1766 if extended else 1411), "reviewed snapshot count changed")
    check(len(patterns) == (37 if extended else 32), "reviewed pattern count changed")
    # Reconstruct the full ordered patterns from their original matrix rows and
    # trip sections. This includes names, route transitions, loop revisits,
    # calendar/service associations and every evidence locator, not only counts.
    reference = build(write=False, extended=extended)
    for field in ["schema_version", "release_version", "coverage_id", "minimum_app_version", "timezone", "effective_from", "valid_from", "valid_until", "source_verified_at", "review_due", "operators", "stop_groups", "boarding_points", "patterns", "services", "calendar", "departures", "sources", "validation"]:
        check(data[field] == reference[field], f"canonical {field} differs from complete source reconstruction")
    if errors:
        raise ValueError("\n".join(errors))
    counts = Counter((d["boarding_point_id"], d["service_id"]) for d in data["departures"])
    return {"releaseVersion": data["release_version"], "sourceSha256": hashlib.sha256(raw).hexdigest(),
            "departureCount": len(data["departures"]), "reconciled": True,
            "reviewer": review["reviewer"],
            "reviewedAt": review["reviewed_at"], "counts": [{"boarding_point_id": bp, "service_id": sid, "count": count}
                                                         for (bp, sid), count in sorted(counts.items())],
            "matrixCellCount": sum(actual.values()), "independentPoleDayCount": sum(independent.values()),
            "hankyuTripCount": sum(hankyu_actual.values()), "sourceCount": len(sources),
            "verifiedCoordinateCount": sum(bool(p.get("coordinate")) for p in points.values()),
            "checks": ["all source checksums", "all extraction checksums", "every numeric matrix cell",
                       "every independent pole minute and marker", "every Hankyu trip and boarded route",
                       "full ordered patterns and loop transitions", "all Hankyu downstream calls", "actual pole IDs and coordinates", "complete official holiday CSV coverage",
                       "operator and calendar coverage", "no weekday fallback on Hankyu weekends"]}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=str(DATA / "timetable.json"))
    parser.add_argument("--report", help="write an audit JSON for this already reviewed snapshot")
    args = parser.parse_args()
    result = validate(args.path)
    if args.report:
        Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "counts"}, indent=2))
