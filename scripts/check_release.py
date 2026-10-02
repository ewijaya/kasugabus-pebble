#!/usr/bin/env python3
"""Clean local build/test audit, then bind actual runtime logs to that PBW."""
import argparse
import datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile
from release_policy import make_policy, required_scenarios
from release_common import ARTIFACT, ROOT, atomic_json, digest, inspect_pbw, require, source_fingerprint


def parse_metrics(output):
    patterns = {"resources": r"Total size of resources:\s*(\d+)", "static_ram": r"Total footprint in RAM:\s*(\d+)", "linker_free_ram": r"Free RAM available \(heap\):\s*(\d+)"}
    metrics = {}
    for key, pattern in patterns.items():
        matches = re.findall(pattern, output)
        require(len(matches) == 1, "Missing/ambiguous Emery build metric: " + key)
        metrics[key] = int(matches[0])
    # The footprint is text+data+bss, which the SDK caps at 65,535 bytes (uint16 virtual_size).
    metrics["image_bytes"] = metrics["static_ram"]
    return metrics


def check_budgets(metrics, budgets, runtime=False):
    for metric, limit in (("native_binary", "max_native_binary_bytes"), ("static_ram", "max_static_ram_bytes"), ("resources", "max_resources_bytes"), ("pbw", "max_pbw_bytes"), ("timetable", "max_payload_bytes")):
        require(0 <= metrics[metric] <= budgets[limit], metric + " exceeds its release budget")
    image = metrics.get("image_bytes")
    require(isinstance(image, int) and image >= 0, "App image size (text+data+bss) was not measured")
    require(image <= budgets["sdk_image_limit_bytes"], "App image exceeds the SDK hard limit of {} bytes".format(budgets["sdk_image_limit_bytes"]))
    require(image <= budgets["max_image_bytes"], "App image exceeds its release budget; at least 4 KiB headroom below the SDK limit is required")
    if runtime:
        require(metrics["measured_free_heap"] >= budgets["minimum_measured_free_heap_bytes"], "Measured runtime heap has less than 20 percent headroom")


def validate_audit(report, bundle, version, root=ROOT, require_runtime=True, require_current_source=True):
    require(report.get("schema") == 1 and report.get("clean_build") is True and report.get("tests_passed") is True, "Clean build/test audit is missing")
    require(report.get("version") == version and inspect_pbw(bundle, version) == report.get("artifact"), "Audit does not describe this exact PBW")
    require(isinstance(report.get("source"), dict) and report["source"].get("fingerprint"), "Source-bound build audit is missing")
    if require_current_source:
        require(source_fingerprint(root) == {k: report["source"][k] for k in ("fingerprint", "files")}, "Project source changed after the audited build")
    budgets = json.loads((Path(root) / "tests/build-budgets.json").read_text())
    check_budgets(report["metrics"], budgets)
    scenarios = required_scenarios(report, budgets, root)
    if require_runtime:
        runtime = report.get("runtime") or {}
        require(runtime.get("environment") in ("emulator", "physical") and set(scenarios) <= set(runtime.get("scenarios", [])), "Runtime measurements do not cover required scenarios")
        evidence = Path(runtime.get("evidence_path", ""))
        require(evidence.is_file() and digest(evidence.read_bytes()) == runtime.get("evidence_sha256"), "Runtime evidence is missing or changed")
        receipt_path = Path(runtime.get("install_receipt_path", ""))
        require(receipt_path.is_file(), "Missing exact-artifact installation/capture receipt")
        receipt = json.loads(receipt_path.read_text())
        require(receipt.get("schema") == 1 and receipt.get("artifact") == report["artifact"] and receipt.get("environment") == runtime["environment"] and receipt.get("log_sha256") == runtime["evidence_sha256"], "Runtime installation receipt does not match the exact artifact/log")
        command = receipt.get("command", [])
        require(command[:2] == ["pebble", "install"] and "--logs" in command and Path(command[-1]).name == ARTIFACT and ((runtime["environment"] == "emulator" and "--emulator" in command and "emery" in command) or (runtime["environment"] == "physical" and "--cloudpebble" in command)), "Capture receipt lacks an explicit matching artifact install")
        started = datetime.datetime.fromisoformat(receipt["started_at"])
        finished = datetime.datetime.fromisoformat(receipt["finished_at"])
        require(datetime.datetime.fromisoformat(report["created_at"]) <= started <= finished, "Runtime capture predates this clean build")
        text = evidence.read_text(errors="replace")
        markers = {
            "launch": r"\bREADY storage=[0-9]+ heap=[0-9]+ message=-?[0-9]+[ \t]*$",
            "navigation": r"\bUI screen[0-9]+ heap[0-9]+[ \t]*$",
            "update-transfer": r"\bUpdate commit session[0-9]+ status[34] heap[0-9]+[ \t]*$",
        }
        for scenario in scenarios:
            require(re.search(markers[scenario], text, re.MULTILINE), "Raw log does not evidence runtime scenario: " + scenario)
        heaps = [int(n) for n in re.findall(r"\bheap(?:=|:|\s)*([0-9]+)", text)]
        require(heaps and min(heaps) == report["metrics"].get("measured_free_heap"), "Heap measurement does not match raw runtime log")
        check_budgets(report["metrics"], budgets, True)
    return report


def clean_build_output(root):
    root = Path(root).resolve()
    output = root / "build"
    require(not output.is_symlink(), "Build output is a symlink; inspect it before cleaning")
    subprocess.run(["pebble", "clean"], cwd=root, check=True, timeout=60)
    # Waf distclean is a no-op without its environment-bearing lock file.
    # We deliberately remove that file after builds, so also clear this
    # project's generated output before claiming a clean acceptance build.
    if output.exists():
        require(output.is_dir(), "Unexpected build output; inspect it before cleaning")
        shutil.rmtree(output)


def build_audit(static_only=False, root=ROOT, full=False):
    root = Path(root)
    package = json.loads((root / "package.json").read_text())
    require(package["name"] == "kasugabus" and package["pebble"]["targetPlatforms"] == ["emery"], "Unexpected package/platform")
    require(not subprocess.run(["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True, text=True).stdout.strip(), "Commit intended source before the release audit; preserve unrelated work")
    policy = make_policy(root, full)
    source = source_fingerprint(root)
    source["git_commit"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, text=True, capture_output=True, timeout=30).stdout.strip() if (root / ".git").exists() else None
    tests = subprocess.run([sys.executable, "scripts/test.py"], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600)
    if tests.returncode:
        print(tests.stdout[-12000:], flush=True)
        tests.check_returncode()
    clean_build_output(root)
    result = subprocess.run(["pebble", "build"], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
    if result.returncode:
        print(result.stdout[-12000:], flush=True)
    result.check_returncode()
    (root / "build/release-build.log").write_text(result.stdout)
    (root / "build/release-tests.log").write_text(tests.stdout)
    metrics = parse_metrics(result.stdout)
    bundle = root / "build" / ARTIFACT
    artifact = inspect_pbw(bundle, package["version"])
    with zipfile.ZipFile(bundle) as archive:
        metrics["native_binary"] = len(archive.read("emery/pebble-app.bin"))
    metrics["pbw"] = artifact["bytes"]
    metrics["timetable"] = (root / "resources/timetable.bin").stat().st_size
    check_budgets(metrics, json.loads((root / "tests/build-budgets.json").read_text()))
    require(source_fingerprint(root) == {k: source[k] for k in ("fingerprint", "files")}, "Project source changed during tests/build; audit refused")
    toolchain = subprocess.run(["pebble", "--version"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    report = {"schema": 1, "version": package["version"], "clean_build": True, "tests_passed": True,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "artifact": artifact, "metrics": metrics, "toolchain": toolchain, "source": source, "runtime": None, "validation_policy": policy}
    atomic_json(root / "build/release-audit.json", report)
    if (root / ".git").exists():
        subprocess.run(["git", "diff", "--check"], cwd=root, check=True)
    print("Static audit passed:", json.dumps(metrics), "PBW SHA-256:", artifact["sha256"], flush=True)
    require(static_only, "Runtime headroom remains unmeasured for this exact PBW. Capture actual emulator/physical logs, then use --complete-runtime; static free RAM is not runtime evidence")
    return report


def complete_runtime(path, environment, scenarios, root=ROOT):
    root = Path(root)
    report_path = root / "build/release-audit.json"
    report = json.loads(report_path.read_text())
    bundle = root / "build" / ARTIFACT
    validate_audit(report, bundle, report["version"], root, False)
    path = Path(path).resolve()
    require(path.is_file() and path.stat().st_mtime >= datetime.datetime.fromisoformat(report["created_at"]).timestamp(), "Capture runtime evidence after this clean build")
    require(environment in ("emulator", "physical"), "Choose the actual runtime environment")
    heaps = [int(n) for n in re.findall(r"\bheap(?:=|:|\s)*([0-9]+)", path.read_text(errors="replace"))]
    require(heaps, "No actual heap measurements found in runtime log")
    report["metrics"]["measured_free_heap"] = min(heaps)
    receipt_path = path.with_suffix(path.suffix + ".install.json")
    report["runtime"] = {"environment": environment, "scenarios": scenarios, "evidence_path": str(path), "evidence_sha256": digest(path.read_bytes()), "install_receipt_path": str(receipt_path), "measured_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    validate_audit(report, bundle, report["version"], root)
    atomic_json(report_path, report)
    print("Exact-artifact runtime audit passed:", report["artifact"], "minimum free heap:", min(heaps))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="Print change-based scope without tests/builds")
    parser.add_argument("--full", action="store_true", help="Explicitly request full runtime coverage")
    parser.add_argument("--static-only", action="store_true", help="Pass static checks while honestly leaving runtime release gate incomplete")
    parser.add_argument("--complete-runtime", type=Path)
    parser.add_argument("--environment", choices=["emulator", "physical"])
    parser.add_argument("--scenarios", help="Comma-separated scenarios actually exercised in the raw log")
    args = parser.parse_args(argv)
    if args.plan:
        require(not args.complete_runtime and not args.static_only, "Use --plan separately from build/runtime operations")
        print("Scope for committed HEAD only; working-tree edits are excluded.", file=sys.stderr)
        print(json.dumps(make_policy(full=args.full), indent=2))
    elif args.complete_runtime:
        require(args.environment and args.scenarios and not args.static_only and not args.full, "Runtime completion requires environment/scenarios and no --static-only")
        complete_runtime(args.complete_runtime, args.environment, args.scenarios.split(","))
    else:
        build_audit(args.static_only, full=args.full)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Release audit stopped:", error, file=sys.stderr)
        sys.exit(1)
