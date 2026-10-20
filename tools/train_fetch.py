#!/usr/bin/env python3
"""Fetch JR Ibaraki and Hankyu Ibaraki-shi train sources into data/sources/trains.

Saves the station-list pages verbatim (hashed in catalog.json) and, for every
train on them, its own page's arrival times at Osaka, Kyoto and Takatsuki with
the page's URL and SHA-256 in train_stops.json. Individual train pages are not
stored: each one is reproducible from its URL and recorded hash. Network access
is only here; train_build.py runs offline from what this writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import train_sources as src  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sources" / "trains"


def get(url: str, cache: Path | None) -> bytes:
    path = cache / hashlib.sha256(url.encode()).hexdigest() if cache else None
    if path and path.exists():
        return path.read_bytes()
    for attempt in range(4):
        try:
            request = Request(url, headers={"User-Agent": "KasugaBus source review/1.0"})
            with urlopen(request, timeout=45) as response:
                body = response.read()
            if path:
                path.write_bytes(body)
            return body
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1 + attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verified-on", required=True, help="YYYY-MM-DD the pages were read")
    parser.add_argument("--cache", type=Path, help="directory for raw per-train pages (resume)")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.cache:
        args.cache.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    catalog = []
    lists = {}
    for page in src.station_pages():
        body = get(page["url"], None)
        (OUT / page["path"]).write_bytes(body)
        catalog.append({**page, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
                        "verified_on": args.verified_on})
        lists[page["id"]] = src.parse_list(page["network"], body.decode("utf-8", "replace"))
        print(f"{page['id']}: {len(lists[page['id']])} trains", flush=True)
    (OUT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=1, sort_keys=True) + "\n")

    jobs = []
    for page in catalog:
        if page["day"] == "saturday":
            continue  # compared with Sunday by train_build.py; no per-train fetch needed
        for train in lists[page["id"]]:
            jobs.append((page["id"], page["network"], train["ref"]))

    def fetch(job):
        page_id, network, ref = job
        url = src.trip_url(network, ref)
        body = get(url, args.cache)
        return f"{page_id}|{ref}", {"url": url, "sha256": hashlib.sha256(body).hexdigest(),
                                    "stops": src.parse_trip_stops(network, body.decode("utf-8", "replace"))}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        stops = dict(pool.map(fetch, jobs))
    document = {"verified_on": args.verified_on, "trains": stops}
    (OUT / "train_stops.json").write_text(json.dumps(document, ensure_ascii=False, sort_keys=True,
                                                     separators=(",", ":")) + "\n")
    print(f"fetched {len(stops)} train pages")


if __name__ == "__main__":
    main()
