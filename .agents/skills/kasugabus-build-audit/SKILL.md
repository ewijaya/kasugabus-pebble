---
name: kasugabus-build-audit
description: Run KasugaBus local tests, a clean Emery build, PBW identity checks and measured resource/runtime budgets without publishing or changing versions.
---

# KasugaBus build audit

Use [docs/releasing.md](../../../docs/releasing.md), `scripts/test.py`,
`scripts/check_release.py` and `tests/build-budgets.json`. Ordinary auditing
never bumps, commits, tags, pushes or publishes.

Record package version, SDK/tool/compiler versions and Git state when a repo
exists. Check only Emery and interactive-app metadata, UUID and display name.
The PBW is `build/kasugabus-pebble.pbw`; inspect it instead of assuming its name
from the npm package. Consolidated tests include codec/calendar/data, portable
C preferences/storage/update policies, phone settings/location and controlled
feed behavior. Generated binary/catalogue freshness is required.

Run a real clean build and inspect compiler failures/warnings, native bytes,
static RAM, resources, timetable size, PBW bytes and digest. At least 20 percent
headroom is targeted against 128 KiB native binary/static RAM and 256 KiB
resources. The established RWX linker warning alone is not build failure.

Generated `.lock-waf*` files can contain the inherited host environment.
They are ignored and must be excluded from source/publication artifacts;
remove these generated locks after a completed build before a handoff or
credential scan. Never print their values or include them as build evidence.
The audit also removes leftover generated build output after SDK clean;
without its lock, Waf distclean can otherwise silently reuse old output.
Do not bypass the clean-output or exact build-metric checks.
Launcher icons need a real 25×25 PNG canvas on this SDK's Emery default
launcher; compile success does not validate that limit. Inspect the selected
icon in the actual launcher and preserve transparency/luminance legibility.

## Default: essential, change-based validation

Follow `docs/releasing.md` → “Essential validation” for incremental releases.
Run `check_release.py --plan`, then one `--static-only` audit; it already runs
all automated tests. Never run `scripts/test.py` again as a separate release step.
Use the audit's change-bound `validation_policy.required_scenarios`: launch and
navigation by default; transfer only for affected storage/updater/protocol/shared
entrypoint/build/dependency changes or unknown inputs. `--full` is opt-in.
Capture the exact PBW for 90 seconds, seal its actual logs, then freeze it once.
Review only the recorded targeted checks; at most five relevant screenshots for
layout changes, including largest text. No routine full theme/size/screen matrix.
No routine audit subagents. Read concise summaries and failure details only.
Target 5–10 minutes locally (not a guarantee); allow one emulator retry, then
report the gap instead of starting prolonged debugging. Required failures remain
failures; an exception requires explicit owner acceptance, never elapsed time.
Use two remote verification attempts, then report propagation pending.
Reuse unchanged source/PBW evidence; never attribute old tests to new bytes.
Listing-only edits require no new build or emulator. Broader device/endurance and
seven-day checks retain their honest status but do not block ordinary incremental
releases. Read first-complete acceptance gates only when making that claim.
Keep exact-artifact physical approval, PBW digest/identity, credentials,
existing-listing preservation and resumable publication guards unchanged.

Static-only audit leaves runtime incomplete. Seal actual exact-PBW logs with
`--complete-runtime`; measured heap must satisfy the budget on required paths.
Never substitute linker free RAM for measured heap or emulator results for
physical observations. See docs/releasing.md for capture and sealing commands.
