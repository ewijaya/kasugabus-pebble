#!/usr/bin/env python3
"""Fetch official source candidates without changing the reviewed dataset."""
from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new candidate directory")
    parser.add_argument("--source", action="append", help="source ID (repeatable; default all)")
    parser.add_argument("--query-date", help="YYYYMMDDHHMM for Jorudan form queries")
    args = parser.parse_args()
    output = args.output.resolve()
    active = ROOT / "data" / "sources"
    if output == active or active in output.parents:
        parser.error("candidate output must be outside the active source directory")
    if args.query_date and (len(args.query_date) != 12 or not args.query_date.isdigit()):
        parser.error("query date must be YYYYMMDDHHMM")
    catalog = json.loads((active / "catalog.json").read_text())
    if args.source:
        wanted = set(args.source)
        unknown = wanted - {s["id"] for s in catalog}
        if unknown:
            parser.error("unknown source IDs: " + ", ".join(sorted(unknown)))
        catalog = [s for s in catalog if s["id"] in wanted]
    output.mkdir(parents=True, exist_ok=False)

    def fetch(source):
        method = source.get("request", {}).get("method", "GET")
        form = dict(source.get("request", {}).get("form", {}))
        if args.query_date and "dt" in form:
            form["dt"] = args.query_date
        body = urlencode(form).encode() if method == "POST" else None
        request = Request(source["url"], data=body, method=method,
                          headers={"User-Agent": "KasugaBus source review/1.0"})
        with urlopen(request, timeout=45) as response:
            payload = response.read()
            final_url = response.url
        path = output / Path(source["path"]).name
        path.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        return {"id": source["id"], "path": path.name, "url": source["url"],
                "final_url": final_url, "sha256": digest, "bytes": len(payload),
                "changed": digest != source["sha256"], "reviewed": False}

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(fetch, catalog))
    (output / "fetch_results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"fetched": len(results), "changed": sum(r["changed"] for r in results),
                      "candidate_directory": str(output), "reviewed": False}, indent=2))


if __name__ == "__main__":
    main()
