#!/usr/bin/env python3
"""Prototype: bus-to-train connections at JR Ibaraki and Hankyu Ibaraki-shi.

Not part of the release pipeline. Reads saved station timetable pages (JR
Odekake, Hankyu English station timetables) from --sources, joins them with the
Kintetsu route tables already extracted under data/extraction, and reports the
size of a compact on-watch train table plus sample connections.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# (station, direction) -> {day: source file}. Day 1 = weekday, 2 = Sat/Sun/holiday.
JR_PAGES = {("JR", "Osaka"): {1: "jr_2791011002_20261020.html", 2: "jr_2791011002_20261025.html"},
            ("JR", "Kyoto"): {1: "jr_2791011001_20261020.html", 2: "jr_2791011001_20261025.html"}}
JR_SATURDAY = {("JR", "Osaka"): "jr_2791011002_20261024.html", ("JR", "Kyoto"): "jr_2791011001_20261024.html"}
HK_PAGES = {("Hankyu", "Osaka"): {1: "HK-69_ky_1_w.html", 2: "HK-69_ky_1_h.html"},
            ("Hankyu", "Kyoto"): {1: "HK-69_ky_2_w.html", 2: "HK-69_ky_2_h.html"}}
STATION_ROWS = {"JR": "ＪＲ茨木駅", "Hankyu": "阪急茨木市駅"}
# Kintetsu services 1/3 weekday, 2 Sat+Sun/holiday, 4 Saturday, 5 Sunday/holiday.
SERVICE_DAY = {1: 1, 2: 2, 3: 1, 4: 2, 5: 2}
SERVICE_NAME = {1: "weekday", 2: "weekend", 3: "weekday", 4: "Saturday", 5: "Sunday"}
JR_TYPES = {"普通": "Local", "快速": "Rapid", "新快速": "Special Rapid"}
# The watch's Japanese font is a small subset, so destinations are shown in romaji.
JR_DESTINATIONS = {"加古川": "Kakogawa", "西明石": "Nishi-Akashi", "姫路": "Himeji", "尼崎": "Amagasaki",
                   "神戸": "Kobe", "網干": "Aboshi", "新三田": "Shin-Sanda", "大阪": "Osaka",
                   "甲子園口": "Koshienguchi", "須磨": "Suma", "宝塚": "Takarazuka", "播州赤穂": "Banshu-Ako",
                   "上郡": "Kamigori", "京都": "Kyoto", "長浜": "Nagahama", "米原": "Maibara",
                   "高槻": "Takatsuki", "草津": "Kusatsu", "野洲": "Yasu", "近江塩津": "Omi-Shiotsu"}


def service_minute(h, m):
    return (h + 24 if h < 4 else h) * 60 + m


def jr_trains(path):
    s = path.read_text(encoding="utf-8")
    trains = {}
    for m in re.finditer(r'href="/train-timetable/(\d+)\?[^"]*">(.*?)</a>', s, re.S):
        body = m.group(2)
        time = re.search(r'departure-time[^"]*">\s*(\d+):(\d+)', body)
        name = re.search(r'train-name"><span[^>]*>(.*?)</span>', body, re.S)
        dest = re.search(r'class="destination"\s*>(.*?)</div>', body, re.S)
        if not time:
            continue
        # Variants such as A快速（うれしート連結） or 快速（…通過） keep their base type.
        kind = re.sub(r"^A|（.*$", "", (name.group(1).strip() if name else "") or "普通")
        destination = re.sub(r"行.*$", "", dest.group(1).strip())
        trains[m.group(1)] = (service_minute(*map(int, time.groups())),
                              JR_TYPES[kind], JR_DESTINATIONS[destination])
    return sorted(trains.values())


def hk_trains(path):
    s = path.read_text(encoding="utf-8", errors="replace")
    trains = {}
    for m in re.finditer(r'TX=([^&]+)&amp;DW=\d&amp;TM=(\d\d)(\d\d)"[^>]*>(.*?)</a>', s, re.S):
        body = m.group(4)
        kind = re.search(r'timetable_train_type">(?:<!--.*?-->)?［(.*?)］', body, re.S)
        dest = re.search(r'timetable_station_name">(?:<!--.*?-->)?(.*?)</p>', body, re.S)
        trains[m.group(1)] = (service_minute(int(m.group(2)), int(m.group(3))),
                              " ".join(kind.group(1).replace("&nbsp;", " ").split()), dest.group(1).strip())
    return sorted(trains.values())


def load_trains(sources):
    lists = {}
    for key, days in JR_PAGES.items():
        for day, name in days.items():
            lists[key + (day,)] = jr_trains(sources / name)
        assert jr_trains(sources / JR_SATURDAY[key]) == lists[key + (2,)], f"{key}: Saturday differs from Sunday"
    for key, days in HK_PAGES.items():
        for day, name in days.items():
            lists[key + (day,)] = hk_trains(sources / name)
    return lists


def clock(text):
    m = re.fullmatch(r"(\d{1,2}):(\d\d)", text or "")
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def bus_arrivals(dataset):
    """Arrival minute at each station for every Ibaraki-bound Kintetsu departure,
    read from the same table column that is the departure's own evidence."""
    tables = {n: json.loads((DATA / "extraction" / f"kintetsu_{n}_tables.json").read_text()) for n in range(5)}
    patterns = {p["id"]: p for p in dataset["patterns"]}
    out = []
    for dep in dataset["departures"]:
        ev = dep["evidence"]
        pattern = patterns[dep["pattern_id"]]
        if not ev.get("source_id", "").startswith("kintetsu_") or pattern["destination_ja"] not in STATION_ROWS.values():
            continue
        rows = tables[int(ev["source_id"][-1])][ev["page"] - 1]["rows"]
        row, col = ev["row"] - 1, ev["column"]
        assert clock(rows[row][col]) == dep["minute"] % 1440
        arrive = {}
        for station, label in STATION_ROWS.items():
            hits = [clock(rows[r][col]) for r in range(row + 1, len(rows)) if rows[r][0] == label and clock(rows[r][col]) is not None]
            if hits:
                arrive[station] = hits[0] + (dep["minute"] - dep["minute"] % 1440)
        out.append({"boarding_point_id": dep["boarding_point_id"], "service_id": dep["service_id"],
                    "minute": dep["minute"], "route": pattern["boarding_route"], "arrive": arrive})
    return out


def next_train(trains, ready):
    return next((t for t in trains if t[0] >= ready), None)


def hm(minute):
    return f"{minute // 60}:{minute % 60:02}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=DATA / "timetable_v4.json")
    parser.add_argument("--transfer", type=int, default=4, help="minutes from bus stop to platform")
    parser.add_argument("--point", type=int, action="append", help="boarding point(s) for sample connections")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text())
    trains = load_trains(args.sources)
    buses = bus_arrivals(dataset)

    print("Trains")
    for key, items in sorted(trains.items()):
        print(f"  {key[0]:6} {key[1]:5} {'weekday' if key[2] == 1 else 'weekend':7} {len(items):3}  "
              f"{hm(items[0][0])}-{hm(items[-1][0])}  {dict(Counter(t[1] for t in items))}")
    total = sum(map(len, trains.values()))
    kinds = sorted({(t[1], t[2]) for items in trains.values() for t in items})
    strings = sorted({s for k in kinds for s in k})
    string_bytes = sum(len(s.encode()) + 1 for s in strings)
    deltas = [b[0] - a[0] for items in trains.values() for a, b in zip(items, items[1:])]
    print(f"  total {total}, {len(kinds)} type/destination patterns, largest gap {max(deltas)} min")

    with_arrival = [b for b in buses if b["arrive"]]
    by_point = defaultdict(list)
    for b in with_arrival:
        for station, minute in b["arrive"].items():
            by_point[(b["boarding_point_id"], station)].append(minute - b["minute"])
    print(f"\nBus arrivals: {len(with_arrival)}/{len(buses)} Ibaraki-bound Kintetsu departures matched")
    for (bp, station), rides in sorted(by_point.items()):
        print(f"  point {bp:2} -> {station:6} ride {min(rides)}-{max(rides)} min over {len(rides)} trips")
    max_ride = max(m for r in by_point.values() for m in r)

    header, lists = 16, 8 * 4
    pattern_table = len(kinds) * 4
    sizes = {"3-byte train records": header + lists + pattern_table + string_bytes + total * 3,
             "2-byte train records (delta)": header + lists + pattern_table + string_bytes + total * 2}
    offsets = len(with_arrival) * 2
    print("\nCompact train table (estimate)")
    for name, size in sizes.items():
        print(f"  {name}: {size:,} bytes")
    print(f"  bus arrival offsets (2 bytes per departure, max ride {max_ride} min fits u8): {offsets:,} bytes")

    names = {p["id"]: g["name_en"] for p in dataset["boarding_points"] for g in dataset["stop_groups"] if g["id"] == p["stop_group_id"]}
    for point in args.point or [3]:
      print(f"\nSample weekday Osaka-bound connections from {names[point]} (point {point}), {args.transfer} min transfer")
      for b in [b for b in with_arrival if b["boarding_point_id"] == point and SERVICE_DAY[b["service_id"]] == 1 and 420 <= b["minute"] <= 510]:
        legs = []
        for station in ("JR", "Hankyu"):
            if station in b["arrive"]:
                t = next_train(trains[(station, "Osaka", 1)], b["arrive"][station] + args.transfer)
                legs.append(f"{station} {hm(b['arrive'][station])} -> {hm(t[0])} {t[1]} for {t[2]}" if t else f"{station}: none")
        print(f"  bus {b['route']:>2} {hm(b['minute'])} | " + " | ".join(legs))

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "trains.json").write_text(json.dumps(
            {f"{k[0]}|{k[1]}|{'weekday' if k[2] == 1 else 'weekend'}": v for k, v in trains.items()},
            ensure_ascii=False, indent=1))
        (args.out / "bus_arrivals.json").write_text(json.dumps(buses, ensure_ascii=False, indent=1))
        print(f"\nWrote {args.out}/trains.json and bus_arrivals.json")


if __name__ == "__main__":
    main()
