---
name: kasugabus-publish-release
description: Prepares and publishes a tested KasugaBus release to its existing GitHub and RePebble destinations, preserving saved listing identity and resumable first-registration recovery when needed. Use when the user asks to ship, release or publish a new KasugaBus version end to end. Loading or maintaining this workflow does not authorize publication.
---

# Publish KasugaBus

Read the project-specific [release skill](../kasugabus-release/SKILL.md),
[store skill](../kasugabus-appstore/SKILL.md),
[build audit](../kasugabus-build-audit/SKILL.md) and
[release procedure](../../../docs/releasing.md) before executing the workflow.

Use package `kasugabus`, display `KasugaBus`, UUID
`d7ba77b0-d528-4cc8-b35c-7052798152c9`, Emery only, interactive app. Configuration
is `docs/release-config.json`. The GitHub destination is
`ewijaya/kasugabus-pebble`. Read current configuration first; do not assume
registration status from this skill. The UUID in package.json identifies the
PBW; the store assigns a separate App ID. Read the saved ID and registration
journals instead of hardcoding a registration assumption here. KasugaBus's
1.0.0 first publication is complete and verified. Ordinary future releases
use the saved **existing** listing; do not submit Dashboard New again.

A future release request authorizes only its stated destinations and scope.
Choose the next suitable version from the actual diff; do not repeat the
initial-release version or New flow. Exact-artifact approval is required for
new installed PBW bytes. Creating or validating this workflow authorizes no
external changes. Treat source pushes and Pages deployment as separately
stated preparation scope when needed for production-feed release checks.

If no store ID is saved, inspect the authenticated Dashboard collection and
UUID lookup for a matching listing. Verify UUID, source repository and release
metadata; name alone is insufficient. Adopt a verified existing ID instead of
creating another app: use `discover-registration --save-match`, then ordinary
existing-listing preparation and preservation. Do not replace its artwork with
the initial-listing draft. If absent, prepare the complete local listing and assets
in `docs/releases/listing.json`, freeze them with the exact PBW, and use the
Dashboard **New** flow only after approval. Never invent an ID or use another
project's listing. Read [registration procedure](../../../docs/releasing.md)
for durable creation intent, immediate assigned-ID recording and lost-response
recovery. Never repeat New while creation is uncertain.

For an actual release request, inspect Git state, remotes, tags, changes since
the previous tag and existing releases. Choose semver from that diff and
communicate the proposed version before editing it. Update package/lockfile,
README, CHANGELOG, release notes and the proposed listing description only
within the approved scope. Preserve data and runtime code during release prep.
Do not invent live predictions, physical test results or production hosting.

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

Run the consolidated checks and clean build, seal actual runtime evidence for
that exact PBW, then freeze/install one physical candidate using `release.py
prepare`. Report source commit, PBW bytes/SHA-256, static metrics, measured
minimum heap and unresolved acceptance checks. Stop for explicit physical
approval of that exact digest and its destinations. Installation alone is not
approval. This pause comes from the release skill's exact-artifact requirement;
when asking, name and link that requirement. If the session already contains
approval for this exact frozen digest and destinations, continue without
asking again; an older version's approval does not approve different bytes.

After approval, publish only the frozen PBW with `--approve-publish`,
`--approve-sha256`, each `--approve-destination` and `--approve-physical`.
Never rebuild during publication.
Preserve unrelated listing metadata, companions, artwork and previous releases.
Frozen notes/description are canonical LF strings without a trailing
presentation newline. RePebble may optimize uploaded PNGs: keep frozen source
hashes and separately record downloaded dimensions/order, differences and
visual comparison. Do not demand byte-identical downloaded artwork or weaken
exact PBW hash equality. For manual text normalization, use only the reviewed
official contract documented in `docs/releasing.md`; do not invent a command.
Verify GitHub,
Dashboard/Emery assets, general and Emery public catalog, and canonical public
listing/changelog with bounded read-only retries. Advertise only destinations
that verify, and distinguish observed phone My Apps from the catalog proxy.

Report version, commit/tag, artifact digest, budgets, emulator/physical evidence,
per-destination URLs/status, README changes, preserved metadata and final Git
state. Name any propagation or registration/hosting limitation honestly.
