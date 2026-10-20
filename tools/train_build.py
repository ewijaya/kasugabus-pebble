#!/usr/bin/env python3
"""Build data/trains.bin (KTR1) from the saved train sources, offline.

Reads data/sources/trains (station pages hashed in catalog.json, plus the
per-train arrival times in train_stops.json) and writes the compact table the
watch will load per direction and day type, and a readable data/trains.json.
`--check` rebuilds in memory and fails if the committed outputs differ.

KTR1 layout, little endian:
  header 32 bytes: "KTR1", u16 schema 1, u16 header size 32, u32 total length,
    u32 CRC32 of bytes 16..end, u32 release version, i32 verified day,
    i32 review-due day (days since 1970-01-01), u16 section count,
    u16 pattern count
  patterns: count x {u16 type string offset, u16 destination string offset}
  sections: count x 12 bytes {u8 network 0 JR/1 Hankyu, u8 direction 0 Osaka/
    1 Kyoto, u8 day type 1 weekday/2 Sat-Sun-holiday, u8 record stride,
    u16 first departure minute, u16 train count, u32 record offset}
  records: stride-4 {u8 minutes since previous departure (0 for the first),
    u8 pattern id, u8 minutes to the first target, u8 minutes to the second
    target}; a duration of 0 means the train does not reach that stop
  strings: NUL-terminated pool, starting with a NUL byte
Offsets are absolute. Departure minutes are service-day minutes (24:xx > 1440).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import train_sources as src  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources" / "trains"
OUT_BIN = ROOT / "data" / "trains.bin"
OUT_JSON = ROOT / "data" / "trains.json"
NETWORKS = ["JR", "Hankyu"]
DIRECTIONS = ["Osaka", "Kyoto"]
STRIDE = 4
EPOCH = datetime.date(1970, 1, 1)


def day_number(text: str) -> int:
    return (datetime.date.fromisoformat(text) - EPOCH).days


def load_sources():
    catalog = json.loads((SOURCES / "catalog.json").read_text())
    for page in catalog:
        body = (SOURCES / page["path"]).read_bytes()
        if hashlib.sha256(body).hexdigest() != page["sha256"]:
            raise SystemExit(f"{page['path']} does not match its recorded SHA-256")
    stops = json.loads((SOURCES / "train_stops.json").read_text())
    return catalog, stops


def build_sections(catalog, stops):
    sections = {}
    saturday = {}
    for page in catalog:
        trains = src.parse_list(page["network"], (SOURCES / page["path"]).read_text(encoding="utf-8"))
        if page["day"] == "saturday":
            saturday[(page["network"], page["direction"])] = [(t["minute"], t["type"], t["destination"]) for t in trains]
            continue
        first, second = src.DURATION_STOPS[(page["network"], page["direction"])]
        rows = []
        for train in trains:
            record = stops["trains"].get(f"{page['id']}|{train['ref']}")
            if record is None:
                raise SystemExit(f"no fetched page for {page['id']} {train['ref']}")
            durations = []
            for stop in (first, second):
                arrive = record["stops"].get(stop) if stop else None
                durations.append(0 if arrive is None else arrive - train["minute"])
            rows.append((train["minute"], train["type"], train["destination"], *durations))
        rows.sort(key=lambda r: (r[0], r[1], r[2], r[3], r[4]))
        sections[(page["network"], page["direction"], src.DAY_TYPE[page["day"]])] = rows
    for (network, direction), rows in saturday.items():
        sunday = [(m, t, d) for m, t, d, *_ in sorted(sections[(network, direction, 2)], key=lambda r: (r[0], r[1], r[2]))]
        if sorted(rows) != sorted(sunday):
            raise SystemExit(f"{network} {direction}: Saturday differs from Sunday; a third day type is needed")
    return sections


def build(release_version: int = 1):
    catalog, stops = load_sources()
    sections = build_sections(catalog, stops)
    patterns = sorted({(t, d) for rows in sections.values() for _, t, d, *_ in rows})
    if len(patterns) > 255:
        raise SystemExit("more than 255 type/destination patterns")
    pattern_id = {p: i for i, p in enumerate(patterns)}
    order = sorted(sections, key=lambda k: (NETWORKS.index(k[0]), DIRECTIONS.index(k[1]), k[2]))

    pool = bytearray(b"\0")
    offsets = {}
    for text in sorted({s for p in patterns for s in p}):
        offsets[text] = len(pool)
        pool += text.encode() + b"\0"

    pattern_bytes = len(patterns) * 4
    directory_bytes = len(order) * 12
    records_at = 32 + pattern_bytes + directory_bytes
    directory, records = bytearray(), bytearray()
    for key in order:
        rows = sections[key]
        directory += struct.pack("<BBBBHHI", NETWORKS.index(key[0]), DIRECTIONS.index(key[1]), key[2], STRIDE,
                                 rows[0][0], len(rows), records_at + len(records))
        previous = rows[0][0]
        for minute, kind, destination, first, second in rows:
            delta = minute - previous
            if not (0 <= delta <= 255 and 0 <= first <= 255 and 0 <= second <= 255):
                raise SystemExit(f"value out of byte range in {key}: {minute} {delta} {first} {second}")
            records += struct.pack("<BBBB", delta, pattern_id[(kind, destination)], first, second)
            previous = minute
    strings_at = records_at + len(records)
    # Pattern string offsets are absolute, so they are known only now.
    pattern_table = b"".join(struct.pack("<HH", strings_at + offsets[t], strings_at + offsets[d]) for t, d in patterns)
    verified = day_number(stops["verified_on"])
    review_due = day_number("2027-03-01")  # JR and Hankyu usually revise in mid-March
    body = struct.pack("<IiiHH", release_version, verified, review_due, len(order), len(patterns))
    payload = body + pattern_table + bytes(directory) + bytes(records) + bytes(pool)
    total = 16 + len(payload)
    blob = bytearray(b"KTR1" + struct.pack("<HHII", 1, 32, total, 0) + payload)
    struct.pack_into("<I", blob, 12, zlib.crc32(bytes(blob[16:])) & 0xFFFFFFFF)
    return bytes(blob), sections


def decode(blob: bytes):
    """Independent reader used by the tests; mirrors the layout above."""
    magic, schema, header, total, crc = struct.unpack_from("<4sHHII", blob)
    if magic != b"KTR1" or schema != 1 or header != 32 or total != len(blob):
        raise ValueError("bad KTR1 header")
    if zlib.crc32(blob[16:]) & 0xFFFFFFFF != crc:
        raise ValueError("bad CRC")
    release, verified, review_due, section_count, pattern_count = struct.unpack_from("<IiiHH", blob, 16)

    def string(offset):
        return blob[offset:blob.index(b"\0", offset)].decode()

    patterns = [(string(a), string(b)) for a, b in struct.iter_unpack("<HH", blob[32:32 + 4 * pattern_count])]
    sections = {}
    directory_at = 32 + 4 * pattern_count
    for i in range(section_count):
        network, direction, day, stride, first, count, offset = struct.unpack_from("<BBBBHHI", blob, directory_at + 12 * i)
        minute, rows = first, []
        for j in range(count):
            delta, pid, d1, d2 = struct.unpack_from("<BBBB", blob, offset + stride * j)
            minute += delta
            rows.append((minute, *patterns[pid], d1, d2))
        sections[(NETWORKS[network], DIRECTIONS[direction], day)] = rows
    return {"release": release, "verified": verified, "review_due": review_due, "sections": sections}


def readable(sections):
    return {f"{n}|{d}|{'weekday' if day == 1 else 'weekend'}": [list(r) for r in rows]
            for (n, d, day), rows in sorted(sections.items(), key=lambda kv: (NETWORKS.index(kv[0][0]), DIRECTIONS.index(kv[0][1]), kv[0][2]))}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="fail if the committed outputs are stale")
    args = parser.parse_args()
    blob, sections = build()
    document = json.dumps(readable(sections), ensure_ascii=False, separators=(",", ":")) + "\n"
    if args.check:
        if OUT_BIN.read_bytes() != blob or OUT_JSON.read_text() != document:
            raise SystemExit("data/trains.bin or data/trains.json is stale; run tools/train_build.py")
        print("train data is current")
        return
    OUT_BIN.write_bytes(blob)
    OUT_JSON.write_text(document)
    count = sum(len(r) for r in sections.values())
    print(f"{OUT_BIN.relative_to(ROOT)}: {len(blob):,} bytes, {count} trains, "
          f"sha256 {hashlib.sha256(blob).hexdigest()}")


if __name__ == "__main__":
    main()
