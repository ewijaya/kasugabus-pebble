#!/usr/bin/env python3
"""Compile evidence-bearing timetable JSON into deterministic KBT1 snapshots.

No timetable values or pole coordinates are inferred. Runtime validation is
structural; source reconciliation is a separate publishing requirement.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import zlib

SCHEMA_VERSION = 1
HEADER_SIZE = 128
MAX_BYTES = 32768
MAX_MINUTE = 4319
UNKNOWN = -2147483648
STRIDES = (28, 8, 24, 16, 12, 4, 6, 5, 16, 2)
EPOCH = dt.date(1970, 1, 1)


def integer(value, where, low=1, high=255):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{where}: expected integer {low}..{high}")
    return value


def date(value, where, optional=False):
    if optional and value in (None, ""):
        return UNKNOWN
    try:
        result = dt.date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError(f"{where}: expected YYYY-MM-DD") from None
    if result.isoformat() != value or not 1900 <= result.year <= 2200:
        raise ValueError(f"{where}: date outside supported 1900..2200 range")
    return (result - EPOCH).days


def field(obj, *names, default=None):
    for name in names:
        if name in obj:
            return obj[name]
    return default


class Strings:
    def __init__(self):
        self.data = bytearray(b"\0")
        self.offsets = {"": 0}

    def add(self, value, where="string", required=False):
        if value is None:
            value = ""
        if not isinstance(value, str) or (required and not value):
            raise ValueError(f"{where}: expected {'nonempty ' if required else ''}string")
        encoded = value.encode("utf-8")
        if b"\0" in encoded or len(encoded) > 1023 or any(ord(c) < 32 and c not in "\n\t" for c in value):
            raise ValueError(f"{where}: invalid or oversized UTF-8 string")
        if value not in self.offsets:
            if len(self.data) + len(encoded) + 1 > 65535:
                raise ValueError("string pool exceeds u16 offsets")
            self.offsets[value] = len(self.data)
            self.data += encoded + b"\0"
        return self.offsets[value]


def indexed(doc, name, required=False):
    values = doc.get(name, [])
    if not isinstance(values, list) or (required and not values):
        raise ValueError(f"{name}: expected {'nonempty ' if required else ''}array")
    result = {}
    for value in values:
        if not isinstance(value, dict):
            raise ValueError(f"{name}: expected record objects")
        identity = integer(value.get("id"), f"{name}.id")
        if identity in result:
            raise ValueError(f"{name}: duplicate id {identity}")
        result[identity] = value
    return dict(sorted(result.items()))


def compile_dataset(doc):
    if not isinstance(doc, dict) or doc.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    release = integer(doc.get("release_version"), "release_version", 1, 4294967295)
    min_app = integer(doc.get("minimum_app_version", 1), "minimum_app_version", 1, 4294967295)
    valid_from = date(doc.get("valid_from"), "valid_from")
    valid_until = date(doc.get("valid_until"), "valid_until")
    effective = date(doc.get("effective_from", doc.get("valid_from")), "effective_from")
    verified = date(field(doc, "source_verified_at", "source_verified_on"), "source_verified_at")
    review = date(field(doc, "review_due", "review_by"), "review_due", True)
    calendar = doc.get("calendar", {})
    calendar_from = date(calendar.get("coverage_from"), "calendar.coverage_from")
    calendar_until = date(calendar.get("coverage_until"), "calendar.coverage_until")
    if valid_from > valid_until or calendar_from > calendar_until or not valid_from <= effective <= valid_until or (review != UNKNOWN and review < verified):
        raise ValueError("reversed validity/calendar interval")
    operators = indexed(doc, "operators", True)
    groups = indexed(doc, "stop_groups", True)
    points = indexed(doc, "boarding_points", True)
    patterns = indexed(doc, "patterns")
    services = indexed(doc, "services")
    pool = Strings()
    coverage = pool.add(doc.get("coverage_id"), "coverage_id", True)
    tables = [bytearray() for _ in STRIDES]
    ranges = {}

    sources = doc.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("sources: expected array")
    source_by_id = {}
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("sources: expected objects")
        sid = source.get("id")
        if sid is None or str(sid) in source_by_id:
            raise ValueError("sources: missing/duplicate id")
        source_by_id[str(sid)] = source
    assigned = set()
    ordered_sources = []
    source_slices = {}
    for oid, op in operators.items():
        ids = op.get("source_ids")
        if ids is None:
            ids = [key for key, src in source_by_id.items() if src.get("operator_id") == oid]
        if not isinstance(ids, list) or len(set(map(str, ids))) != len(ids):
            raise ValueError("operator.source_ids: expected unique array")
        first = len(ordered_sources)
        for sid in ids:
            key = str(sid)
            if key not in source_by_id:
                raise ValueError(f"operator {oid}: unknown source {key}")
            # Shared sources can occur in more than one operator's contiguous slice.
            ordered_sources.append(source_by_id[key])
            assigned.add(key)
        source_slices[oid] = (first, len(ids))
    ordered_sources += [source_by_id[key] for key in sorted(source_by_id) if key not in assigned]

    for oid, op in operators.items():
        start = date(op.get("valid_from", doc["valid_from"]), f"operator {oid}.valid_from")
        end = date(op.get("valid_until", doc["valid_until"]), f"operator {oid}.valid_until")
        if not valid_from <= start <= end <= valid_until:
            raise ValueError(f"operator {oid}: validity outside snapshot")
        ranges[oid] = (start, end)
        name = field(op, "name_en", "name")
        declared = op.get("day_types")
        if declared is None:
            declared = sorted({day for svc in services.values() if svc.get("operator_id") == oid for day in svc.get("day_types", [])})
        no_service = op.get("no_service_day_types", [])
        if not isinstance(declared, list) or not isinstance(no_service, list) or len(set(declared)) != len(declared) or len(set(no_service)) != len(no_service) or set(declared) & set(no_service):
            raise ValueError(f"operator {oid}: invalid/overlapping day type declarations")
        known_mask = sum(1 << integer(day, "operator confirmed day_type", 1, 3) for day in declared + no_service)
        if not known_mask:
            raise ValueError(f"operator {oid}: no confirmed calendar types")
        tables[0] += struct.pack("<BBHHHiiiiHH", oid, known_mask, pool.add(name, "operator name", True),
            pool.add(op.get("name_ja")), pool.add(field(op, "short_name_en", "short_name", default=name), "operator short name", True),
            start, end, date(field(op, "source_verified_at", "source_verified_on", default=field(doc, "source_verified_at", "source_verified_on")), "operator verified"),
            date(field(op, "review_due", "review_by", default=field(doc, "review_due", "review_by")), "operator review", True), *source_slices[oid])
    for gid, group in groups.items():
        name = field(group, "name_en", "name")
        tables[1] += struct.pack("<BBHHH", gid, 0,
            pool.add(field(group, "short_name_en", "short_name", default=name), "group short name", True),
            pool.add(name, "group name", True), pool.add(group.get("name_ja")))
    for pid, point in points.items():
        gid = integer(field(point, "stop_group_id", "group_id"), "boarding_point.stop_group_id")
        oid = integer(point.get("operator_id"), "boarding_point.operator_id")
        if gid not in groups or oid not in operators:
            raise ValueError(f"boarding point {pid}: unknown group/operator")
        group = groups[gid]
        coordinate = point.get("coordinate")
        flags, lat, lon = 0, UNKNOWN, UNKNOWN
        if coordinate is not None:
            if not isinstance(coordinate, dict):
                raise ValueError(f"boarding point {pid}: coordinate must be object or null")
            # community_mapped_corroborated: owner-approved (2026-10-02) for points
            # whose operator publishes no pole location; see data_validate.py.
            if point.get("coordinate_status") not in ("verified", "verified_pole", "official_pole", "shared_verified_pole", "community_mapped_corroborated"):
                raise ValueError(f"boarding point {pid}: coordinate is not explicitly verified")
            if "latitude_e6" in coordinate:
                lat = integer(coordinate.get("latitude_e6"), "latitude_e6", -90000000, 90000000)
                lon = integer(coordinate.get("longitude_e6"), "longitude_e6", -180000000, 180000000)
            else:
                la = field(coordinate, "latitude", "lat")
                lo = field(coordinate, "longitude", "lon", "lng")
                if type(la) not in (float, int) or type(lo) not in (float, int) or not math.isfinite(la) or not math.isfinite(lo) or not -90 <= la <= 90 or not -180 <= lo <= 180:
                    raise ValueError(f"boarding point {pid}: coordinate out of range")
                lat, lon = round(la * 1e6), round(lo * 1e6)
            flags = 1
        name = field(point, "name_en", "name", default=field(group, "name_en", "name"))
        tables[2] += struct.pack("<BBBBHHHHHHii", pid, gid, oid, flags,
            pool.add(name, "boarding point name", True),
            pool.add(field(point, "short_name_en", "short_name", default=field(group, "short_name_en", "short_name", default=name)), "boarding point short name", True),
            pool.add(point.get("name_ja", group.get("name_ja"))),
            pool.add(field(point, "direction_en", "direction"), "boarding direction", True),
            pool.add(point.get("direction_ja")), pool.add(field(point, "boarding_guidance_en", "guidance_en", "guidance")), lat, lon)
    for pid, pattern in patterns.items():
        oid = integer(pattern.get("operator_id"), "pattern.operator_id")
        if oid not in operators:
            raise ValueError(f"pattern {pid}: unknown operator")
        destination_group = integer(pattern.get("destination_group_id", 0), "destination_group_id", 0, 255)
        if destination_group and destination_group not in groups:
            raise ValueError(f"pattern {pid}: unknown destination group")
        calls = pattern.get("downstream_calls", [])
        if not isinstance(calls, list):
            raise ValueError("downstream_calls: expected array")
        call_ids = []
        for call in calls:
            gid = call.get("stop_group_id") if isinstance(call, dict) else call
            # External terminal calls retain their label in source JSON; covered
            # destination filtering only indexes known covered stop groups.
            if gid is None:
                continue
            gid = integer(gid, "downstream stop_group_id")
            if gid not in groups:
                raise ValueError(f"pattern {pid}: unknown downstream group")
            call_ids.append(gid)
        first = len(tables[9]) // 2
        tables[9] += b"".join(struct.pack("<BB", pid, gid) for gid in call_ids)
        transition = pattern.get("route_transitions", [])
        if isinstance(transition, (list, dict)):
            transition = json.dumps(transition, ensure_ascii=False, separators=(",", ":"), sort_keys=True) if transition else ""
        tables[3] += struct.pack("<BBHHHBBHHH", pid, oid,
            pool.add(field(pattern, "boarding_route", "route"), "boarded route", True),
            pool.add(field(pattern, "destination_en", "destination"), "destination", True),
            pool.add(pattern.get("destination_ja")), destination_group, 0, first, len(call_ids), pool.add(transition, "route transitions"))
    normalized_services = {}
    for sid, service in services.items():
        oid = integer(service.get("operator_id"), "service.operator_id")
        if oid not in operators:
            raise ValueError(f"service {sid}: unknown operator")
        days = service.get("day_types")
        if not isinstance(days, list) or not days or len(set(days)) != len(days):
            raise ValueError(f"service {sid}: expected unique nonempty day_types")
        mask = sum(1 << integer(day, "service.day_type", 1, 3) for day in days)
        op = operators[oid]
        if op.get("day_types") is not None and any(day not in op["day_types"] for day in days):
            raise ValueError(f"service {sid}: day type outside operator service declarations")
        if any(day in op.get("no_service_day_types", []) for day in days):
            raise ValueError(f"service {sid}: day type declared no service")
        start = date(service.get("valid_from", operators[oid].get("valid_from", doc["valid_from"])), "service.valid_from")
        end = date(service.get("valid_until", operators[oid].get("valid_until", doc["valid_until"])), "service.valid_until")
        if not ranges[oid][0] <= start <= end <= ranges[oid][1]:
            raise ValueError(f"service {sid}: validity outside operator")
        normalized_services[sid] = (oid, mask, start, end)
        tables[4] += struct.pack("<BBBBii", sid, oid, mask, 0, start, end)
    holidays = []
    holiday_source_from = date(calendar.get("holiday_source_coverage_from", calendar.get("coverage_from")), "holiday_source_coverage_from")
    holiday_source_until = date(calendar.get("holiday_source_coverage_until", calendar.get("coverage_until")), "holiday_source_coverage_until")
    if holiday_source_from > calendar_from or holiday_source_until < calendar_until:
        raise ValueError("calendar coverage outside holiday source coverage")
    for holiday in calendar.get("holidays", []):
        value = date(holiday.get("date") if isinstance(holiday, dict) else holiday, "holiday.date")
        if value in holidays or not holiday_source_from <= value <= holiday_source_until:
            raise ValueError("holiday duplicate or outside source coverage")
        holidays.append(value)
    tables[5] += b"".join(struct.pack("<i", value) for value in sorted(holidays) if calendar_from <= value <= calendar_until)
    exceptions = []
    for exception in calendar.get("exceptions", []):
        value = date(exception.get("date"), "exception.date")
        oid = integer(exception.get("operator_id"), "exception.operator_id")
        dtype = integer(exception.get("day_type"), "exception.day_type", 0, 255)
        if oid not in operators or dtype not in (0, 1, 2, 3, 255):
            raise ValueError("exception unknown operator/day type")
        if not ranges[oid][0] <= value <= ranges[oid][1] or any(item[:2] == (value, oid) for item in exceptions):
            raise ValueError("exception duplicate or outside operator validity")
        exceptions.append((value, oid, dtype))
    tables[6] += b"".join(struct.pack("<iBB", *value) for value in sorted(exceptions))
    departures = []
    by_trip = {}
    for departure in doc.get("departures", []):
        bp = integer(departure.get("boarding_point_id"), "departure.boarding_point_id")
        pat = integer(departure.get("pattern_id"), "departure.pattern_id")
        svc = integer(departure.get("service_id"), "departure.service_id")
        minute = integer(departure.get("minute"), "departure.minute", 0, MAX_MINUTE)
        if bp not in points or pat not in patterns or svc not in services:
            raise ValueError("departure unknown boarding point/pattern/service")
        oid = points[bp]["operator_id"]
        if patterns[pat]["operator_id"] != oid or services[svc]["operator_id"] != oid:
            raise ValueError("departure operator identity mismatch")
        identity = (bp, minute, pat, svc)
        if identity in departures:
            raise ValueError("duplicate departure")
        key = identity[:3]
        service_range = normalized_services[svc]
        for previous_svc in by_trip.get(key, []):
            previous = normalized_services[previous_svc]
            if previous[1] & service_range[1] and max(previous[2], service_range[2]) <= min(previous[3], service_range[3]):
                raise ValueError("overlapping service records duplicate the same trip")
        by_trip.setdefault(key, []).append(svc)
        departures.append(identity)
    tables[7] += b"".join(struct.pack("<HBBB", minute, bp, pat, svc) for bp, minute, pat, svc in sorted(departures))
    for source in ordered_sources:
        if not isinstance(source.get("url"), str) or not source["url"].startswith(("https://", "http://")):
            raise ValueError("source URL must use HTTP(S)")
        tables[8] += struct.pack("<HHiii", pool.add(field(source, "name_en", "name", "title", default=str(source["id"])), "source title", True),
            pool.add(source.get("url"), "source URL", True),
            date(field(source, "revision_date", "revision_on", "effective_date", "timetable_effective_from"), "source revision", True),
            date(field(source, "verified_at", "verified_on", "source_verified_at", default=field(doc, "source_verified_at", "source_verified_on")), "source verified"),
            date(field(source, "review_due", "review_by", default=field(doc, "review_due", "review_by")), "source review", True))
    header = bytearray(HEADER_SIZE)
    payload = b"".join(tables) + pool.data
    total = HEADER_SIZE + len(payload)
    if total > MAX_BYTES:
        raise ValueError(f"payload {total} exceeds {MAX_BYTES}-byte maximum")
    struct.pack_into("<4sHHIIIIiiiiiiHHIIHH", header, 0, b"KBT1", SCHEMA_VERSION, HEADER_SIZE,
        total, 0, release, min_app, valid_from, valid_until, calendar_from, calendar_until, verified, review,
        coverage, 0, total-len(pool.data), len(pool.data), max((item[1] for item in departures), default=0), len(STRIDES))
    offset = HEADER_SIZE
    for index, (table, stride) in enumerate(zip(tables, STRIDES)):
        count = len(table) // stride
        if count > 65535:
            raise ValueError("table count exceeds u16")
        struct.pack_into("<IH", header, 64 + index*6, offset, count)
        offset += len(table)
    struct.pack_into("<i", header, 124, effective)
    result = header + payload
    struct.pack_into("<I", result, 12, zlib.crc32(result[16:]) & 0xffffffff)
    # Review-order validation applies to all operator/source records too.
    for index, verified_offset, review_offset in ((0, 16, 20), (8, 8, 12)):
        table = tables[index]
        for offset in range(0, len(table), STRIDES[index]):
            source_verified = struct.unpack_from("<i", table, offset + verified_offset)[0]
            source_review = struct.unpack_from("<i", table, offset + review_offset)[0]
            if source_review != UNKNOWN and source_review < source_verified:
                raise ValueError("source review date precedes verification")
    return bytes(result)


def make_catalog(doc):
    groups = {value["id"]: value for value in doc["stop_groups"]}
    operators = {value["id"]: value for value in doc["operators"]}
    result = {"schemaVersion": 1, "releaseVersion": doc["release_version"], "coverageId": doc["coverage_id"], "boardingPoints": []}
    for point in sorted(doc["boarding_points"], key=lambda value: value["id"]):
        group = groups[point["stop_group_id"]]
        name = field(point, "short_name_en", "name_en", default=field(group, "short_name_en", "name_en"))
        operator = operators[point["operator_id"]]
        operator_name = field(operator, "short_name_en", "name_en", default="Operator " + str(point["operator_id"]))
        result["boardingPoints"].append({"id": point["id"], "groupId": point["stop_group_id"], "operatorId": point["operator_id"],
            "name": name, "label": name + " / " + operator_name + " / " + point["direction_en"],
            "nameJa": point.get("name_ja", group.get("name_ja", "")), "direction": point["direction_en"],
            "coordinate": point.get("coordinate")})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--catalog", type=Path)
    args = parser.parse_args(argv)
    try:
        doc = json.loads(args.source.read_text(encoding="utf-8"))
        payload = compile_dataset(doc)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
        if args.catalog:
            args.catalog.parent.mkdir(parents=True, exist_ok=True)
            args.catalog.write_text(json.dumps(make_catalog(doc), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{args.output}: {len(payload)} bytes, {len(doc.get('departures', []))} departures, sha256 {hashlib.sha256(payload).hexdigest()}")
    except (ValueError, OSError, KeyError, TypeError, struct.error) as error:
        print(f"compile_timetable: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
