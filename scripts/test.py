#!/usr/bin/env python3
"""Run KasugaBus data, portable C, phone and controlled feed tests locally."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    spec = importlib.util.spec_from_file_location("timetable_compiler", ROOT / "tools/compile_timetable.py")
    compiler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compiler)
    doc = json.loads((ROOT / "data/timetable.json").read_text())
    expected = compiler.compile_dataset(doc)
    if (ROOT / "resources/timetable.bin").read_bytes() != expected:
        raise RuntimeError("Bundled timetable is stale; regenerate from reviewed data before testing")
    catalog = json.loads((ROOT / "src/pkjs/catalog.json").read_text())
    if catalog != compiler.make_catalog(doc):
        raise RuntimeError("Phone catalogue is stale; regenerate with --catalog src/pkjs/catalog.json")
    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py")
    run("node", "tests/test_phone.js")
    run("node", "tests/test_phone_settings_ui.js")
    run("node", "tests/test_phone_catalog.js")
    run(sys.executable, "tools/test_feed.py")
    with tempfile.TemporaryDirectory(prefix="kasugabus-host-") as folder:
        for name, sources in (("preferences", ["src/c/preferences.c"]), ("all_preferences", ["src/c/all_preferences.c"]), ("policies", ["src/c/policies.c"]), ("extras", ["src/c/extras.c"]), ("storage", ["src/c/storage.c", "src/c/engine.c"]), ("storage_resource", ["src/c/storage.c", "src/c/engine.c"])):
            target = str(Path(folder) / name)
            run("cc", "-std=c99", "-Wall", "-Wextra", "-Werror", *sources, "tests/test_" + name + ".c", "-o", target)
            run(target, *([str(ROOT / "resources/timetable.bin")] if name.startswith("storage") else []))
    print("All local KasugaBus test suites passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Tests stopped:", error, file=sys.stderr)
        sys.exit(1)
