---
name: kasugabus-release
description: Freeze, publish or verify a KasugaBus release candidate, including the guarded first-registration handoff, when the user explicitly requests a release. Not for ordinary builds.
---

# KasugaBus candidate release

Read [docs/releasing.md](../../../docs/releasing.md) for maintained commands and
recovery. Preparation reuses the PBW already produced by `check_release.py` and
bound to measured runtime logs. Publication never rebuilds it.

Check configured project identity, version/lockfile consistency, clean committed
Git source/branch/origin, ignored build/candidate paths, prior tags/releases and
reviewed README/CHANGELOG/notes/listing description. Do not initialize Git,
create repositories or commit unrelated work to satisfy a guard. Version 1.0.0
has not been bumped or published by workflow creation.

Before freezing a first complete release, review `docs/VERIFICATION.md` and PRD
sections 15/16. Require current dataset/operator/calendar and source-review
validity, configured and live-validated production timetable hosting, a
deployed update without PBW reinstall, actual phone/companion/watch-firmware
physical checks and seven-day use results. The full preflight is in
`docs/releasing.md`; absent or incomplete evidence remains a release blocker.
A later explicit incremental-release scope must name its omissions and must
not imply the first complete release's criteria passed. Scripts do not certify
these acceptance results merely by passing the build/runtime audit.

Run `scripts/test.py`, a clean `check_release.py --static-only`, exercise the
actual runtime paths and seal logs with `--complete-runtime`. A missing raw log
or static linker free RAM cannot prove runtime headroom. Prepare with the sealed
`--audit`, notes, desired destinations and `--physical`. The same PBW is
physically installed and frozen under `.release/VERSION/`; an existing candidate
cannot be overwritten.

For a new store app, freeze the complete app-specific listing and artwork with
the PBW. A null store ID is permitted only through the explicit first-publication
mode; it must not weaken the existing-listing identity checks. Inspect the
authenticated Dashboard for an existing UUID/repository match before New.
Journal creation intent before submission and save the assigned ID immediately
after the response or App Information reveals it. An uncertain response requires
read-only discovery and recovery, not another submission. Follow the maintained
registration commands in `docs/releasing.md`.

**Publication requires the user's explicit physical approval of the exact
candidate SHA-256, version, destinations and proposed initial listing when
applicable. Installation alone is not approval.**
Loading or maintaining this skill does not provide that authorization. Stop
before app-release tag/push/publication if approval is missing, cite this exact requirement,
and provide the concrete candidate/hash and evidence for review.

Only record approval flags after consent was given. `release.py publish`
checks artifact, notes, config, audit/source fingerprint and source commit;
requires explicit approval of the exact frozen destination list; uses the installed
uploader on the frozen file; and journals partial progress. Do not substitute
mutable `build/` output, automatically overwrite differing releases or silently
publish a draft. `verify --attempts 3` is read-only remote verification with
bounded retry; it does not upload or build. Keep a partial release pending until
every selected destination verifies. The final publication-status doc commit
is allowed only by the actual release request, never workflow maintenance.
The user's later “publish this new app everywhere” instruction covers initial
registration/listing/publication subject to that exact-candidate approval;
do not request separate registration authorization again in that case.
