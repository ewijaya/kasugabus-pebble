"""Source definitions and page parsers for the JR Ibaraki / Hankyu Ibaraki-shi
train data. Shared by train_fetch.py (network) and train_build.py (offline)."""
from __future__ import annotations

import html
import re
from urllib.parse import quote

JR_BASE = "https://timetable.jr-odekake.net"
HANKYU_BASE = "https://www.hankyu.co.jp"
JR_STATION_ID = {"Osaka": "2791011002", "Kyoto": "2791011001"}
# Sample dates inside the current JR/Hankyu revision. JR serves one list per
# date; Saturday is fetched only to prove it equals Sunday (no separate list).
JR_DATES = {"weekday": "20261020", "saturday": "20261024", "weekend": "20261025"}
HANKYU_PAGE = {("Osaka", "weekday"): "HK-69_ky_1_w", ("Osaka", "weekend"): "HK-69_ky_1_h",
               ("Kyoto", "weekday"): "HK-69_ky_2_w", ("Kyoto", "weekend"): "HK-69_ky_2_h"}

# Day types follow the bus data: 1 weekday, 2 Saturday/Sunday/holiday.
DAY_TYPE = {"weekday": 1, "weekend": 2}
# Stops whose arrival time is kept from every train's own page.
TARGET_STOPS = {"JR": ["大阪", "京都", "高槻"], "Hankyu": ["大阪梅田(阪急)", "京都河原町", "高槻市"]}
# (first, second) duration targets for each station and direction.
DURATION_STOPS = {("JR", "Osaka"): ("大阪", None), ("JR", "Kyoto"): ("京都", "高槻"),
                  ("Hankyu", "Osaka"): ("大阪梅田(阪急)", None), ("Hankyu", "Kyoto"): ("京都河原町", "高槻市")}

JR_TYPES = {"普通": "Local", "快速": "Rapid", "新快速": "Special Rapid"}
# The watch font holds only a small Japanese subset, so destinations are romaji.
JR_DESTINATIONS = {"加古川": "Kakogawa", "西明石": "Nishi-Akashi", "姫路": "Himeji", "尼崎": "Amagasaki",
                   "神戸": "Kobe", "網干": "Aboshi", "新三田": "Shin-Sanda", "大阪": "Osaka",
                   "甲子園口": "Koshienguchi", "須磨": "Suma", "宝塚": "Takarazuka", "播州赤穂": "Banshu-Ako",
                   "上郡": "Kamigori", "京都": "Kyoto", "長浜": "Nagahama", "米原": "Maibara",
                   "高槻": "Takatsuki", "草津": "Kusatsu", "野洲": "Yasu", "近江塩津": "Omi-Shiotsu"}


def service_minute(hour: int, minute: int) -> int:
    """Minutes since the service day began; 00:00-03:59 belong to the same day."""
    return (hour + 24 if hour < 4 else hour) * 60 + minute


def station_pages():
    """Every station-list page: id, network, direction, day, url, local name."""
    pages = []
    for direction, number in JR_STATION_ID.items():
        for day, date in JR_DATES.items():
            pages.append({"id": f"jr_{direction.lower()}_{day}", "network": "JR", "direction": direction,
                          "day": day, "url": f"{JR_BASE}/station-timetable/{number}?date={date}"})
    for (direction, day), name in HANKYU_PAGE.items():
        pages.append({"id": f"hankyu_{direction.lower()}_{day}", "network": "Hankyu", "direction": direction,
                      "day": day, "url": f"{HANKYU_BASE}/en/station/html/{name}.html"})
    for page in pages:
        page["path"] = page["id"] + ".html"
    return pages


def trip_url(network: str, ref: str) -> str:
    if network == "JR":
        return JR_BASE + ref
    return f"{HANKYU_BASE}/station/timetable.php?" + quote(ref, safe="=&-")


def parse_jr_list(page: str):
    """Trains on a JR Odekake station page: reference, minute, type, destination."""
    trains = []
    for match in re.finditer(r'href="(/train-timetable/\d+\?[^"]*)">(.*?)</a>', page, re.S):
        body = match.group(2)
        clock = re.search(r'departure-time[^"]*">\s*(\d+):(\d+)', body)
        if not clock:
            continue
        name = re.search(r'train-name"><span[^>]*>(.*?)</span>', body, re.S)
        dest = re.search(r'class="destination"\s*>(.*?)</div>', body, re.S)
        # Variants such as A快速（うれしート連結） or 快速（…通過） keep their base type.
        kind = re.sub(r"^A|（.*$", "", (name.group(1).strip() if name else "") or "普通")
        destination = re.sub(r"行.*$", "", dest.group(1).strip())
        trains.append({"ref": html.unescape(match.group(1)),
                       "minute": service_minute(int(clock.group(1)), int(clock.group(2))),
                       "type": JR_TYPES[kind], "destination": JR_DESTINATIONS[destination]})
    return trains


def parse_hankyu_list(page: str):
    trains = []
    for match in re.finditer(r'href="/station/timetable\.php\?([^"]+TM=(\d\d)(\d\d))"[^>]*>(.*?)</a>', page, re.S):
        body = match.group(4)
        kind = re.search(r'timetable_train_type">(?:<!--.*?-->)?［(.*?)］', body, re.S)
        dest = re.search(r'timetable_station_name">(?:<!--.*?-->)?(.*?)</p>', body, re.S)
        trains.append({"ref": html.unescape(match.group(1)),
                       "minute": service_minute(int(match.group(2)), int(match.group(3))),
                       "type": " ".join(kind.group(1).replace("&nbsp;", " ").split()),
                       "destination": dest.group(1).strip()})
    return trains


def parse_list(network: str, page: str):
    return parse_jr_list(page) if network == "JR" else parse_hankyu_list(page)


def _tokens(page: str):
    text = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    return [t.strip() for t in re.sub(r"<[^>]+>", "\n", text).split("\n") if t.strip()]


def parse_trip_stops(network: str, page: str):
    """Arrival minute at each target stop on one train's own page."""
    tokens = _tokens(page)
    clock = re.compile(r"\d\d:\d\d")
    found = {}
    for i, token in enumerate(tokens):
        if token not in TARGET_STOPS[network] or token in found:
            continue
        if network == "JR":
            # name, hh:mm, 着 (arrival), optionally followed by hh:mm 発
            if i + 2 < len(tokens) and clock.fullmatch(tokens[i + 1]) and tokens[i + 2] == "着":
                found[token] = tokens[i + 1]
        else:
            # name, 到着、, hh:mm
            if i + 2 < len(tokens) and tokens[i + 1] == "到着、" and clock.fullmatch(tokens[i + 2]):
                found[token] = tokens[i + 2]
    return {name: service_minute(*map(int, value.split(":"))) for name, value in found.items()}
