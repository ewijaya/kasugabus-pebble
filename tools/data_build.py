#!/usr/bin/env python3
"""Rebuild editable timetable from preserved official evidence (no network).

Requires pdfplumber only for the extraction stage. Canonical reconciliation in
data_validate.py uses the preserved extraction grids and standard library.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FROM = "2026-10-01"
UNTIL = "2026-12-27"
VERIFIED = "2026-10-01"
REVIEW = "2026-11-01"

GROUPS = [
    (1, "Kasugaoka Koen", "春日丘公園", "Kasugaoka Koen"),
    (2, "Toge", "峠", "Toge"),
    (3, "Midorigaoka", "緑ヶ丘", "Midorigaoka"),
    (4, "Handai Higashiguchi", "阪大東口", "Handai East"),
    (5, "Handai Igakubu Byoin-mae", "阪大医学部病院前", "Handai Hospital"),
    (6, "Handai Igakubu-mae", "阪大医学部前", "Handai Medical"),
]
NAMES = {ja: en for _, en, ja, _ in GROUPS}
NAMES.update({
    "ＪＲ茨木駅": "JR Ibaraki", "阪急茨木市駅": "Hankyu Ibaraki-shi",
    "茨木市役所前": "Ibaraki City Hall", "駅前通り": "Ekimae-dori",
    "中穂積一丁目": "Nakahozumi 1-chome", "茨木みどりヶ丘病院前": "Ibaraki Midorigaoka Hospital",
    "中穂積三丁目": "Nakahozumi 3-chome", "紫明園東": "Shimeien East",
    "北春日丘": "Kita Kasugaoka", "松沢池": "Matsuzawa Pond", "翠湖園": "Suikoen",
    "北桜町": "Kita Sakuramachi", "春光園": "Shunkoen", "紫明園": "Shimeien",
    "南春日丘": "Minami Kasugaoka", "南春日丘西": "Minami Kasugaoka West",
    "日本庭園前": "Japanese Garden", "記念公園西口": "Memorial Park West",
    "阪大南口": "Handai South", "茨木美穂ヶ丘": "Ibaraki Mihogaoka",
    "阪大本部前": "Handai Honbu", "千里中央": "Senri-chuo",
    "阪大歯学部病院前": "Handai Dental Hospital", "阪大口": "Handai-guchi",
    "金蘭会学園前": "Kinrankai Gakuen", "藤白台四丁目": "Fujishirodai 4-chome",
    "阪急北千里駅": "Hankyu Kita-senri", "青山台四丁目": "Aoyamadai 4-chome",
    "青山幼稚園前": "Aoyama Kindergarten", "青山台二丁目": "Aoyamadai 2-chome",
    "二丁目南口": "2-chome South", "樫ノ木公園前": "Kashinoki Park",
    "北町二丁目": "Kitamachi 2-chome", "北町一丁目": "Kitamachi 1-chome",
    "東町二丁目": "Higashimachi 2-chome",
})
GROUP_BY_JA = {ja: gid for gid, _, ja, _ in GROUPS}
TIME = re.compile(r"^(\d{1,2}):(\d{2})$")
MARK_TIME = re.compile(r"([★▲美Ｊ]?)\s*(\d{1,2})")


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def nuxt_objects(path):
    html = path.read_text()
    match = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not match:
        raise ValueError(f"No NUXT data in {path}")
    values = json.loads(match.group(1))

    def resolve(i, stack=()):
        if i < 0:
            return None
        if i in stack:
            raise ValueError("cyclic NUXT evidence")
        value = values[i]
        if isinstance(value, dict):
            return {k: resolve(v, stack + (i,)) for k, v in value.items()}
        if isinstance(value, list):
            return [resolve(v, stack + (i,)) if isinstance(v, int) and v >= 0 else v for v in value]
        return value

    return [resolve(i) for i, v in enumerate(values) if isinstance(v, dict)]


def clock_minute(text):
    match = TIME.fullmatch(text or "")
    if not match:
        return None
    h, m = map(int, match.groups())
    if m > 59 or h > 47:
        raise ValueError(f"invalid service-day time {text}")
    return h * 60 + m


def call(name):
    if name not in NAMES:
        raise ValueError(f"English label missing: {name}")
    item = {"name_en": NAMES[name], "name_ja": name}
    if name in GROUP_BY_JA:
        item["stop_group_id"] = GROUP_BY_JA[name]
    return item


def extract():
    import pdfplumber

    manifest = []

    def save_extraction(path, obj, source):
        dump(path, obj)
        manifest.append({"path": str(path.relative_to(ROOT)),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "source_path": str(source.relative_to(ROOT)),
                         "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                         "extractor": f"pdfplumber{pdfplumber.__version__} extract_tables default line strategy"})

    for number in range(5):
        pages = []
        source = DATA / "sources" / f"kintetsu_{number}.pdf"
        with pdfplumber.open(source) as pdf:
            for index, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                assert len(tables) == 1
                rows = tables[0]
                assert rows[0][0] == "方向幕番号"
                assert len(set(map(len, rows))) == 1
                pages.append({"page": index + 1, "rows": rows})
        save_extraction(DATA / "extraction" / f"kintetsu_{number}_tables.json", pages, source)
    for path in sorted((DATA / "sources").glob("kintetsu_stop_*_direction_*.pdf")):
        with pdfplumber.open(path) as pdf:
            tables = pdf.pages[0].extract_tables()
            assert len(tables) == 1
            save_extraction(DATA / "extraction" / f"{path.stem}_table.json", tables[0], path)
    dump(DATA / "extraction" / "manifest.json", manifest)


def pole_minutes(stop, direction):
    """Independent individual-stop evidence; blanks remain blanks."""
    source_id = f"kintetsu_stop_{stop}_direction_{direction}"
    table = json.loads((DATA / "extraction" / f"{source_id}_table.json").read_text())
    types = {"月～金曜日用": [1], "土日祝用": [2, 3], "土曜日用": [2], "日祝用": [3]}
    result = {}
    for row_index, row in enumerate(table):
        if not (row[0] or "").isdigit():
            continue
        hour = int(row[0])
        for col in range(1, len(row)):
            cell = row[col] or ""
            tokens = list(MARK_TIME.finditer(cell))
            leftover = MARK_TIME.sub("", cell).strip()
            assert not leftover, (source_id, hour, cell, leftover)
            for token_index, match in enumerate(tokens):
                mark, minute = match.groups()
                assert int(minute) < 60
                for day_type in types[table[1][col]]:
                    key = (day_type, 60 * hour + int(minute))
                    assert key not in result
                    result[key] = {"mark": mark, "source_id": source_id,
                                   "page": 1, "row": row_index + 1, "column": col,
                                   "token": token_index + 1, "printed_cell": cell}
    return result


def build(write=True):
    catalog = json.loads((DATA / "sources" / "catalog.json").read_text())
    for source in catalog:
        source.setdefault("name_en", source["id"].replace("_", " "))
        source["verified_at"] = VERIFIED
        source["review_due"] = REVIEW
        if source["id"].startswith("kintetsu"):
            source["operator_id"] = 1
            source.setdefault("revision_date", None)
            if re.fullmatch(r"kintetsu_stop_\d_direction_\d", source["id"]):
                source["revision_date"] = "2025-12-21" if "direction_1" in source["id"] and any(f"stop_{i}_" in source["id"] for i in [4, 5, 6]) else "2024-08-21"
            if re.fullmatch(r"kintetsu_[0-4]", source["id"]):
                source["revision_date"] = "2024-08-21"
        elif source["id"].startswith("hankyu"):
            source["operator_id"] = 2
            source["revision_date"] = "2026-02-16" if re.fullmatch(r"hankyu_\d{6}", source["id"]) else None
    groups = [{"id": i, "name_en": en, "name_ja": ja, "short_name_en": short}
              for i, en, ja, short in GROUPS]
    points = []
    point_specs = [
        (1, 1, "Ibaraki via Toge", "峠経由 茨木方面", 1, 1),
        (2, 2, "Ibaraki via Kita Sakuramachi", "北桜町経由 茨木方面", 2, 1),
        (3, 3, "Ibaraki via Kasugaoka Koen", "春日丘公園経由 茨木方面", 3, 1),
        (4, 4, "University / Mihogaoka", "阪大病院・本部前／茨木美穂ヶ丘方面", 4, 1),
        (5, 4, "Ibaraki", "ＪＲ茨木駅・阪急茨木市駅方面", 4, 2),
        (6, 5, "University", "阪大本部前方面", 5, 1),
        (7, 5, "Ibaraki", "ＪＲ茨木駅・阪急茨木市駅方面", 5, 2),
        (8, 6, "University", "阪大本部前方面", 6, 1),
        (9, 6, "Ibaraki", "ＪＲ茨木駅・阪急茨木市駅方面", 6, 2),
    ]
    pole_lookup = {}
    for pid, gid, en, ja, stop, direction in point_specs:
        points.append({"id": pid, "stop_group_id": gid, "operator_id": 1,
                       "direction_en": en, "direction_ja": ja,
                       "coordinate": None, "coordinate_status": "excluded_unverified",
                       "coordinate_reason": "No actual pole location or shared-pole relationship was verified for this boarding direction. The official Jorudan map investigation exposed a named-stop centre and an empty pole list; the operator route diagram has no georeferenced pole markers. See data/coordinate_review.json.",
                       "evidence": [{"source_id": f"kintetsu_stop_{stop}_direction_{direction}", "page": 1}]})
        pole_lookup[pid] = pole_minutes(stop, direction)

    registry_path = DATA / "identity_registry.json"
    registry = json.loads(registry_path.read_text()) if registry_path.exists() else {"patterns": {}}
    patterns = {}
    departures = []

    def pattern(operator, bp, route, destination, names, transitions=(), note=None):
        record = {"operator_id": operator, "boarding_route": route,
                  "destination_en": NAMES[destination], "destination_ja": destination,
                  "downstream_calls": [call(name) for name in names],
                  "route_transitions": list(transitions)}
        if note:
            record["via_en"] = note
        key = json.dumps([bp, record], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if key not in registry["patterns"]:
            registry["patterns"][key] = max(registry["patterns"].values(), default=0) + 1
        pid = registry["patterns"][key]
        record["id"] = pid
        patterns[pid] = record
        return pid

    matrix_rows = {0: [(1, 14), (2, 15), (3, 13)], 1: [(1, 14), (2, 15), (3, 13)]}
    for number in range(2, 5):
        matrix_rows[number] = [(4, 17), (6, 19), (8, 20), (9, 23), (7, 24), (5, 26)]
    service_ids = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}
    for number in range(5):
        pages = json.loads((DATA / "extraction" / f"kintetsu_{number}_tables.json").read_text())
        day_type = 1 if number in [0, 2] else (2 if number in [1, 3] else 3)
        for page in pages:
            rows = page["rows"]
            for bp, row_index in matrix_rows[number]:
                for column in range(1, len(rows[0])):
                    minute = clock_minute(rows[row_index][column])
                    if minute is None:
                        assert rows[row_index][column] in [None, "", "↓"]
                        continue
                    ev = pole_lookup[bp][(day_type, minute)]
                    source_route = rows[0][column]
                    transitions = []
                    note = None
                    if number < 2:
                        route = source_route
                        assert route in ["1", "2"]
                        assert (ev["mark"] == "Ｊ") == (route == "1")
                        destination = "ＪＲ茨木駅" if route == "1" else "阪急茨木市駅"
                        last_row = 22 if route == "1" else 25
                    elif row_index >= 23:
                        route, destination, last_row = "22", "阪急茨木市駅", 38
                        assert source_route in ["22", "25/22"]
                        assert (ev["mark"] == "美") == (clock_minute(rows[25][column]) is not None) if bp in [7, 9] else not ev["mark"]
                        if ev["mark"] == "美":
                            note = "via Mihogaoka"
                    elif source_route == "24":
                        route, destination, last_row = "24", "阪大本部前", 21
                        assert not ev["mark"]
                    elif source_route == "25/22":
                        morning = clock_minute(rows[25][column]) is not None
                        if morning:
                            if row_index == 17:
                                assert ev["mark"] == "★"
                            else:
                                assert ev["mark"] == "★"
                            route, destination, last_row = "25", "茨木美穂ヶ丘", 25
                            note = "via Handai Honbu (remain aboard)"
                            transitions = [{"at_name_ja": "阪大本部前", "from_route": "25", "to_route": "22",
                                            "source_ids": ["kintetsu_loop_notice", f"kintetsu_stop_{5 if bp == 6 else 6 if bp == 8 else 4}_direction_2"],
                                            "transfer_required": False}]
                        elif bp == 4:
                            assert ev["mark"] == "▲"
                            route, destination, last_row = "25", "阪大本部前", 21
                            note = "via Mihogaoka"
                            transitions = [{"at_name_ja": "茨木美穂ヶ丘", "from_route": "25", "to_route": "22",
                                            "source_ids": ["kintetsu_stop_4_direction_1", "kintetsu_stop_5_direction_1"],
                                            "transfer_required": False}]
                        else:
                            route, destination, last_row = "22", "阪急茨木市駅", 38
                            note = "via Handai Honbu"
                            assert not ev["mark"]
                    else:
                        raise ValueError((bp, source_route, row_index))
                    names = [rows[r][0] for r in range(row_index + 1, last_row + 1)
                             if rows[r][0] and clock_minute(rows[r][column]) is not None]
                    assert names and names[-1] == destination
                    pid = pattern(1, bp, route, destination, names, transitions, note)
                    departures.append({"boarding_point_id": bp, "pattern_id": pid,
                                       "service_id": service_ids[number], "minute": minute,
                                       "evidence": {"source_id": f"kintetsu_{number}", "page": page["page"],
                                                    "row": row_index + 1, "column": column,
                                                    "source_route_label": source_route,
                                                    "printed_time": rows[row_index][column],
                                                    "independent_pole": ev}})

    hankyu_specs = [(101, 4, "083801", "00020633", "University via hospital (north)"),
                    (102, 4, "083802", "00020633", "Senri-chuo direct (south)"),
                    (103, 5, "138401", "00021075", "University (south)"),
                    (104, 5, "138402", "00021075", "Senri-chuo direct (north)"),
                    (105, 6, "138501", "00021076", "University (west)"),
                    (106, 6, "138502", "00021076", "Senri-chuo direct (east)")]
    for bp, gid, timetable_id, stop_id, direction in hankyu_specs:
        source_id = "hankyu_" + timetable_id
        obj = next(o for o in nuxt_objects(DATA / "sources" / (source_id + ".html")) if "schedules" in o)
        poles = json.loads((DATA / "sources" / ("hankyu_poles_" + stop_id + ".json")).read_text())
        gen = next(g for g in poles["generations"] if g["isCurrent"])
        pole = next(p for p in gen["poles"] if p["id"] == obj["poleId"])
        assert any(c["timetableId"] == timetable_id for c in pole["courseGroups"])
        points.append({"id": bp, "stop_group_id": gid, "operator_id": 2,
                       "direction_en": direction, "direction_ja": obj["poleName"],
                       "coordinate": {"latitude": pole["latitude"], "longitude": pole["longitude"]},
                       "coordinate_status": "verified_pole",
                       "coordinate_evidence": {"source_id": "hankyu_poles_" + stop_id,
                                               "locator": "generations[isCurrent=true].poles[id=" + pole["id"] + "]",
                                               "pole_id": pole["id"], "timetable_id": timetable_id,
                                               "verified_at": VERIFIED},
                       "evidence": [{"source_id": source_id, "locator": "NUXT timetable.poleName"}]})
        for si, schedule in enumerate(obj["schedules"]):
            assert schedule["scheduleName"] == "平日" and schedule["scheduleType"] == "weekday"
            for ci, col in enumerate(schedule["columns"]):
                for ti, trip in enumerate(col["trips"]):
                    tid = trip["id"]
                    sections = next(o["sections"] for o in nuxt_objects(DATA / "sources" / ("hankyu_trip_" + tid + ".html")) if "sections" in o)
                    section_index = next(i for i, s in enumerate(sections) if s["departure"]["id"] == stop_id and s["departure"]["sequence"] == trip["sequence"])
                    section = sections[section_index]
                    route = re.match(r"\[(\d+)\]", section["destination"]).group(1)
                    assert "[" + route + "]" in col["routeName"]
                    assert section["departureTime"] == trip["departureTime"]
                    names = [s["arrival"]["name"] for s in sections[section_index:]]
                    destination = col["destination"]
                    assert names[-1] == destination
                    note = "via Handai Honbu and Kita-senri" if route == "171" else None
                    pid = pattern(2, bp, route, destination, names, (), note)
                    h, m = map(int, trip["departureTime"][11:16].split(":"))
                    departures.append({"boarding_point_id": bp, "pattern_id": pid,
                                       "service_id": 6, "minute": 60 * h + m,
                                       "evidence": {"source_id": source_id, "schedule_index": si,
                                                    "column_index": ci, "trip_index": ti,
                                                    "operator_trip_id": tid,
                                                    "printed_time": trip["departureTime"],
                                                    "route_source_id": "hankyu_trip_" + tid,
                                                    "section_index": section_index}})

    holidays = []
    text = (DATA / "sources" / "holidays.csv").read_bytes().decode("cp932")
    for csv_row, row in enumerate(csv.reader(io.StringIO(text)), 1):
        if not re.fullmatch(r"\d{4}/\d{1,2}/\d{1,2}", row[0]):
            continue
        year, month, day = map(int, row[0].split("/"))
        if year in [2026, 2027]:
            holidays.append({"date": f"{year:04}-{month:02}-{day:02}", "name_ja": row[1],
                             "source_id": "holidays", "csv_row": csv_row})
    services = [{"id": i, "operator_id": op, "day_types": types, "valid_from": FROM, "valid_until": UNTIL}
                for i, op, types in [(1, 1, [1]), (2, 1, [2, 3]), (3, 1, [1]),
                                     (4, 1, [2]), (5, 1, [3]), (6, 2, [1])]]
    dataset = {"schema_version": 1, "release_version": 1, "coverage_id": "minami-kasugaoka-v1",
               "minimum_app_version": 1, "timezone": "Asia/Tokyo", "effective_from": FROM,
               "valid_from": FROM, "valid_until": UNTIL, "source_verified_at": VERIFIED,
               "review_due": REVIEW,
               "operators": [{"id": 1, "name_en": "Kintetsu Bus", "name_ja": "近鉄バス",
                              "valid_from": FROM, "valid_until": UNTIL, "day_types": [1, 2, 3],
                              "source_ids": [s["id"] for s in catalog if s.get("operator_id") == 1]},
                             {"id": 2, "name_en": "Hankyu Bus", "name_ja": "阪急バス",
                              "valid_from": FROM, "valid_until": UNTIL, "day_types": [1],
                              "no_service_day_types": [2, 3],
                              "no_service_evidence": {"source_id": "hankyu_directory", "locator": "阪大病院線 / 72、164、171系統 / 平日"},
                              "source_ids": [s["id"] for s in catalog if s.get("operator_id") == 2]}],
               "stop_groups": groups, "boarding_points": sorted(points, key=lambda x: x["id"]),
               "patterns": [patterns[i] for i in sorted(patterns)], "services": services,
               "calendar": {"coverage_from": FROM, "coverage_until": UNTIL,
                            "holiday_source_coverage_from": "2026-01-01",
                            "holiday_source_coverage_until": "2027-12-31", "holidays": holidays,
                            "exceptions": [],
                            "limitations": ["Upcoming 2026/2027 year-end operator schedules are not yet verified. Dates from 2026-12-28 are outside operator and calendar coverage and must be unconfirmed.",
                                            "No historical operator exceptions are inferred. Coverage begins on the retrieval date, after the 2026 Obon period."]},
               "departures": sorted(departures, key=lambda x: (x["boarding_point_id"], x["service_id"], x["minute"], x["pattern_id"])),
               "sources": catalog,
               "validation": {"status": "reconciled", "departure_count": len(departures),
                              "boarding_point_count": len(points), "pattern_count": len(patterns),
                              "verified_coordinate_count": sum(p["coordinate"] is not None for p in points)}}
    if write:
        dump(registry_path, registry)
        dump(DATA / "timetable.json", dataset)
    return dataset


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", action="store_true", help="refresh preserved PDF grids with pdfplumber")
    args = parser.parse_args()
    if args.extract:
        extract()
    result = build()
    print(json.dumps(result["validation"], indent=2))
