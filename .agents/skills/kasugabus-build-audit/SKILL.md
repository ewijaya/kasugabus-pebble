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

`--static-only` truthfully leaves runtime release acceptance incomplete.
Install the exact artifact, exercise launch/navigation/update transfer, capture
actual logs after the build and use `--complete-runtime` to hash/bind them to
that digest. Require the minimum measured free heap from those paths; never
infer peak allocation from binary size or static free RAM. Label emulator and
physical evidence separately. Report unmeasured phone/device acceptance and
production-hosting limitations rather than claiming they passed.

A successful audit is build/runtime evidence, not release readiness. For an
actual first complete release, review `docs/VERIFICATION.md` against PRD
sections 15/16 and the full `docs/releasing.md` preflight: current dataset and
source-review validity, live production hosting, physical phone/watch/firmware
checks and seven-day use remain independent gates. Keep missing results as
release blockers unless a later explicit scoped-release decision records a
limited incremental build and its omissions.
