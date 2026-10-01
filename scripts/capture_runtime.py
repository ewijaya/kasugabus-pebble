#!/usr/bin/env python3
"""Install the audited PBW and capture bounded real logs with a digest receipt.

Exercise navigation and the controlled update while logs run. This never
builds or publishes. It does not assert that human/device QA passed.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from release_common import ARTIFACT, ROOT, atomic_json, digest, inspect_pbw, require
from check_release import validate_audit


def capture(output, environment, seconds, root=ROOT, stop_file=None):
    root = Path(root)
    require(environment in ("emulator", "physical") and 15 <= seconds <= 1800, "Use emulator/physical and 15..1800 capture seconds")
    report = json.loads((root / "build/release-audit.json").read_text())
    bundle = root / "build" / ARTIFACT
    validate_audit(report, bundle, report["version"], root, False)
    output = Path(output).resolve()
    receipt_path = output.with_suffix(output.suffix + ".install.json")
    require(not output.exists() and not receipt_path.exists(), "Never overwrite runtime evidence")
    if stop_file:
        stop_file = Path(stop_file).resolve()
        require(not stop_file.exists(), "Stop file already exists; use a fresh capture stop path")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = ["pebble", "install"] + (["--emulator", "emery"] if environment == "emulator" else ["--cloudpebble"]) + ["--logs", str(bundle)]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with output.open("wb") as logfile:
        process = subprocess.Popen(command, cwd=root, stdout=logfile, stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONUNBUFFERED="1"))
        deadline = time.monotonic() + seconds
        try:
            while process.poll() is None and time.monotonic() < deadline and not (stop_file and stop_file.exists()):
                try:
                    code = process.wait(timeout=max(0.01, min(2, deadline-time.monotonic())))
                    require(code == 0, "Runtime install/log command failed; inspect raw evidence")
                except subprocess.TimeoutExpired:
                    pass
            require(process.poll() in (None, 0), "Runtime install/log command failed; inspect raw evidence")
        except KeyboardInterrupt:
            pass  # Explicit stop still seals the evidence captured so far.
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    require(inspect_pbw(bundle, report["version"]) == report["artifact"], "Audited PBW changed during capture")
    require("READY" in output.read_text(errors="replace"), "No KasugaBus launch was observed after the explicit artifact installation")
    receipt = {"schema": 1, "artifact": report["artifact"], "environment": environment, "command": command,
        "started_at": started, "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "log_sha256": digest(output.read_bytes())}
    atomic_json(receipt_path, receipt)
    print("Runtime log captured:", output, "receipt:", receipt_path, "PBW:", report["artifact"]["sha256"])
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--environment", choices=["emulator", "physical"], required=True)
    parser.add_argument("--seconds", type=int, default=90)
    parser.add_argument("--stop-file", type=Path, help="Stop cleanly when this previously absent file is created; Ctrl-C also seals capture")
    args = parser.parse_args(argv)
    capture(args.output, args.environment, args.seconds, stop_file=args.stop_file)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Runtime capture stopped:", error, file=sys.stderr)
        sys.exit(1)
