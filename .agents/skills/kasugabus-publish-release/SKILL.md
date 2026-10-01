---
name: kasugabus-publish-release
description: Prepare and publish one tested KasugaBus release to GitHub and RePebble, including resumable first-time Dashboard registration when explicitly requested. Maintaining this workflow does not authorize publication.
---

# Publish KasugaBus

Read the project-specific [release skill](../kasugabus-release/SKILL.md),
[store skill](../kasugabus-appstore/SKILL.md),
[build audit](../kasugabus-build-audit/SKILL.md) and
[release procedure](../../../docs/releasing.md) before executing the workflow.

Use package `kasugabus`, display `KasugaBus`, UUID
`d7ba77b0-d528-4cc8-b35c-7052798152c9`, Emery only, interactive app. Configuration
is `docs/release-config.json`. The approved future GitHub destination is
`ewijaya/kasugabus-pebble`. Read current configuration first; do not assume
registration status from this skill. The UUID in package.json identifies the
PBW; the store assigns a separate App ID. The current setup has no saved ID.

The user's future instruction **“publish this new app everywhere”** authorizes
first registration, the initial listing and app publication, subject to
explicit physical approval of the exact tested PBW and proposed listing.
Creating or validating this workflow authorizes none of those actions. Treat
repository/source pushes and Pages deployment as separately stated preparation
scope when they are needed before the production-feed release checks.

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

For the first complete personal release, read `docs/VERIFICATION.md` against
PRD sections 15 and 16. Review current per-operator/calendar validity and
source review dates; require configured and live-validated production HTTPS
hosting with a deployed timetable-only update; record actual phone OS,
companion version, watch firmware and physical acceptance, plus the seven-day
use review. Missing/failed/unobserved evidence remains a release blocker even
when the build audit passes. Follow the detailed preflight in `docs/releasing.md`.
Only a later explicit scoped-release decision can permit a named incremental
build with omissions; it must not be described as the completed first release.
Creating or validating this workflow does not establish release readiness.

Run the consolidated checks and clean build, seal actual runtime evidence for
that exact PBW, then freeze/install one physical candidate using `release.py
prepare`. Report source commit, PBW bytes/SHA-256, static metrics, measured
minimum heap and unresolved acceptance checks. Stop for explicit physical
approval of that exact digest and its destinations. Installation alone is not
approval. This pause comes from the release skill's exact-artifact requirement;
when asking, name and link that requirement.

After approval, publish only the frozen PBW with `--approve-publish`,
`--approve-sha256`, each `--approve-destination` and `--approve-physical`.
Never rebuild during publication.
Preserve unrelated listing metadata, companions and artwork. Verify GitHub,
Dashboard/Emery assets, general and Emery public catalog, and canonical public
listing/changelog with bounded read-only retries. Advertise only destinations
that verify, and distinguish observed phone My Apps from the catalog proxy.

Report version, commit/tag, artifact digest, budgets, emulator/physical evidence,
per-destination URLs/status, README changes, preserved metadata and final Git
state. Name any propagation or registration/hosting limitation honestly.
