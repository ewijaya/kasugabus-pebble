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
create repositories or commit unrelated work to satisfy a guard. Version 1.0.0 was published on 1 October 2026 after exact-candidate approval.
Use the saved existing listing and choose any later version from the actual
diff; maintaining the workflow does not authorize another release.

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
mutable source artwork for a reviewed asset change. For an explicitly requested
existing-listing artwork update, follow the separate, hash-bound Dashboard
procedure in `docs/releasing.md`; the ordinary uploader preserves artwork.
Its original preservation baseline survives failed retries, and the installed
SDK upload adapter refuses redirects before forwarding credentials. Do not reset
that baseline to silence a mismatch. Do not substitute
mutable `build/` output, automatically overwrite differing releases or silently
publish a draft. `verify --attempts 2` is read-only remote verification with
bounded retry; it does not upload or build. Keep a partial release pending until
every selected destination verifies. The final publication-status doc commit
is allowed only by the actual release request, never workflow maintenance.
The user's later “publish this new app everywhere” instruction covers initial
registration/listing/publication subject to that exact-candidate approval;
do not request separate registration authorization again in that case.
