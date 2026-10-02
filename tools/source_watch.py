#!/usr/bin/env python3
"""Check official timetable sources for changes; never edits the dataset.

Fetches every catalogued source (same requests as data_fetch.py) and compares
it with the archived copy in data/sources. PDFs and CSVs compare exactly,
timetable pages compare their sequence of departure times, notice pages their
visible text and JSON its content without dates, so daily page churn such as
cache-busting stamps, breadcrumbs and news tickers is ignored. A
detected change is a prompt for the documented source review, not data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DATES = re.compile(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}(?:[T ][\d:.+-]*)?|\d{4}年\d{1,2}月\d{1,2}日")
STAMPS = re.compile(r"[?&](?:ver|v|_)=\w+")
TIMES = re.compile(r"(?<!\d)\d{1,2}:\d{2}(?!\d)")


def visible_text(payload):
    text = payload.decode("utf-8", "replace")
    text = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", text)
    return re.sub(r"\s+", " ", STAMPS.sub("", re.sub(r"(?s)<[^>]*>", " ", text)))


def normalize(source_id, kind, payload):
    """Content that matters for timetable review, without daily churn.

    Notice pages compare visible text; other pages compare their sequence of
    times; JSON compares content without dates; files compare exactly."""
    if kind == "html" and "notice" in source_id:
        value = DATES.sub("", visible_text(payload))
    elif kind == "html":
        value = " ".join(TIMES.findall(visible_text(payload)))
    elif kind == "json":
        value = DATES.sub("", payload.decode("utf-8", "replace"))
    else:
        return hashlib.sha256(payload).hexdigest()
    return hashlib.sha256(value.encode()).hexdigest()


ROOT = Path(__file__).resolve().parents[1]


def fetch(source):
    kind = source["path"].rsplit(".", 1)[-1]
    archived = ROOT / source["path"]
    request = source.get("request", {})
    method = request.get("method", "GET")
    body = urlencode(request.get("form", {})).encode() if method == "POST" else None
    try:
        with urlopen(Request(source["url"], data=body, method=method,
                             headers={"User-Agent": "KasugaBus source watch/1.0"}), timeout=45) as response:
            payload = response.read()
    except Exception as error:  # Report and continue: one outage must not hide other changes.
        return {"id": source["id"], "url": source["url"], "error": type(error).__name__}
    baseline = normalize(source["id"], kind, archived.read_bytes()) if archived.exists() else source["sha256"]
    return {"id": source["id"], "url": source["url"], "kind": kind,
            "name": source.get("name_en", source["id"]), "changed": normalize(source["id"], kind, payload) != baseline,
            "bytes": len(payload), "previous_bytes": source.get("bytes")}


def report(results, reviewed_on):
    files = [r for r in results if r.get("changed") and (r["kind"] != "html" or "notice" not in r["id"])]
    pages = [r for r in results if r.get("changed") and r["kind"] == "html" and "notice" in r["id"]]
    errors = [r for r in results if "error" in r]
    lines = ["# Timetable source watch", "",
             f"Checked {len(results)} official sources against the reviewed catalogue (retrieved {reviewed_on}).",
             f"Changed timetables: **{len(files)}**. Changed notice pages: {len(pages)}. Fetch errors: {len(errors)}.", ""]
    if files:
        lines += ["## Changed timetables (review first)", ""]
        lines += [f"- [{r['name']}]({r['url']}) `{r['id']}`: {r['previous_bytes']} → {r['bytes']} bytes" for r in files]
        lines.append("")
    if pages:
        lines += ["## Changed notice pages", ""]
        lines += [f"- [{r['name']}]({r['url']}) `{r['id']}`" for r in pages]
        lines.append("")
    if errors:
        lines += ["## Not checked", ""]
        lines += [f"- `{r['id']}`: {r['error']}" for r in errors]
        lines.append("")
    lines += ["Follow docs/DATA_RECONCILIATION.md before changing data/timetable.json. "
              "This report does not update any timetable."]
    return "\n".join(lines) + "\n", len(files)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True, help="Markdown report path")
    parser.add_argument("--json", type=Path, help="optional machine-readable results")
    args = parser.parse_args(argv)
    catalog = json.loads((ROOT / "data/sources/catalog.json").read_text())
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(fetch, catalog))
    text, files = report(results, max(s.get("retrieved_at", "") for s in catalog))
    args.report.write_text(text)
    if args.json:
        args.json.write_text(json.dumps(results, indent=2) + "\n")
    changed = sum(1 for r in results if r.get("changed"))
    print(json.dumps({"checked": len(results), "changed": changed, "changed_files": files,
                      "errors": sum(1 for r in results if "error" in r)}))


if __name__ == "__main__":
    main()
