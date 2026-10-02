"""Bounded, change-based release scope. No builds or network operations."""
import json
import subprocess
from release_common import ROOT, require

FULL = ["launch", "navigation", "update-transfer"]
SMOKE = ["launch", "navigation"]
TRANSFER_FILES = {"src/c/main.c", "src/c/app.h", "wscript"}
LIGHT_FILES = {"src/c/ui.c", "src/c/preferences.c", "src/c/preferences.h",
               "src/c/all_preferences.c", "src/c/all_preferences.h",
               "src/c/engine.c", "src/c/engine.h", "src/c/policies.c", "src/c/policies.h"}
PHONE_LIGHT = {"settings.js", "clay-config.js", "custom-clay.js", "nearby.js", "reference-location.js", "catalog.json"}


def classify(paths, full=False):
    reasons = []
    targeted = set()
    for path in paths:
        if path.startswith(("docs/", ".agents/", ".claude/", "artifacts/")) or path in {"README.md", "CHANGELOG.md", "PRD.md", "PLAN.md", ".gitignore"}:
            continue
        if path.startswith(("data/", "resources/timetable", "src/c/engine")) or path == "src/pkjs/catalog.json":
            targeted.add("schedule/calendar/provenance")
        if "preferences" in path or path.startswith("src/pkjs/") and path.rsplit("/", 1)[-1] in PHONE_LIGHT:
            targeted.add("settings/location/persistence")
        if path == "src/c/ui.c" or path.startswith("resources/") and "timetable" not in path:
            targeted.add("changed layouts: at most 5 screenshots, include largest text")
        light = (path in LIGHT_FILES or path.startswith(("data/", "resources/", "tests/")) or
                 path.startswith("src/pkjs/") and path.rsplit("/", 1)[-1] in PHONE_LIGHT)
        if not light or path in TRANSFER_FILES:
            reasons.append(path)
    return {"mode": "full" if full else "essential", "required_scenarios": FULL if full or reasons else SMOKE,
            "transfer_reasons": sorted(reasons), "targeted_checks": sorted(targeted)}


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, timeout=30).stdout.strip()


AUTO_BASE = object()


def make_policy(root=ROOT, full=False, commit=None, base=AUTO_BASE):
    commit = commit or git(root, "rev-parse", "HEAD")
    if base is AUTO_BASE:
        try:
            base = git(root, "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*", commit)
            base = git(root, "rev-parse", base + "^{commit}")
        except subprocess.CalledProcessError:
            base = None
    paths = git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit).splitlines() if base is None else git(root, "diff", "--name-only", base, commit, "--").splitlines()
    # A missing baseline cannot justify reducing coverage.
    effective = list(paths)
    for name in ("package.json", "package-lock.json"):
        if base and name in effective:
            try:
                before = json.loads(git(root, "show", base + ":" + name))
                after = json.loads(git(root, "show", commit + ":" + name))
                for obj in (before, after):
                    obj.pop("version", None)
                    if "" in obj.get("packages", {}):
                        obj["packages"][""].pop("version", None)
                if before == after:
                    effective.remove(name)
            except (subprocess.CalledProcessError, ValueError):
                pass
    policy = classify(effective, full or base is None)
    policy.update(schema=1, base_commit=base, source_commit=commit, changed_files=paths)
    return policy


def required_scenarios(report, budgets, root=ROOT):
    policy = report.get("validation_policy")
    if policy is None:  # Historical reports retain their original strict gate.
        return budgets["required_runtime_scenarios"]
    require(policy.get("schema") == 1 and policy.get("mode") in ("essential", "full"), "Invalid validation policy")
    require(policy.get("source_commit") == report["source"].get("git_commit"), "Validation scope does not match source commit")
    expected = make_policy(root, policy["mode"] == "full", policy["source_commit"], policy.get("base_commit"))
    require(policy == expected, "Validation scope changed or does not match Git evidence")
    return policy["required_scenarios"]
