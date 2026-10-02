---
name: kasugabus-appstore
description: Prepare, register, update and verify KasugaBus's RePebble listing through the approved release workflow, with durable App ID recovery and preservation of existing metadata and artwork.
---

# KasugaBus App Store

Read `docs/release-config.json` before deciding whether a listing exists.
`uuid` is the package/PBW UUID, `d7ba77b0-d528-4cc8-b35c-7052798152c9`;
`store_app_id` is a separate server-assigned listing identifier.
`store_listing_url` records its canonical public URL after identity verification;
public-page reachability is verified separately. First publication is complete;
read the saved verified ID and update that existing listing. Missing local
configuration requires discovery, never automatic new registration. Never invent
an ID or reuse another project's identity.

If no ID is saved, inspect the authenticated Developer Dashboard and official
developer UUID lookup. Match UUID, source repository and release metadata,
not the name alone. A matching existing listing must be adopted and its
identity recorded with `discover-registration --save-match` before ordinary
existing-listing preparation. Skip New and preserve its artwork; the local
initial-listing draft does not authorize replacing an existing listing's
assets. Late adoption after freezing has a preservation branch described in
the release procedure. Ambiguous or conflicting identity stops
creation. Ask the user to log in if needed; never request their password or
tokens. Credentials stay outside the project and in-memory tokens go only to
the inspected official authentication/API hosts.

If no match exists, prepare [listing.json](../../../docs/releases/listing.json)
and [its preview](../../../docs/releases/listing-preview.html): KasugaBus,
watchapp, Daily, approved description/repository, own 80×80 and 144×144 icons,
720×320 Emery banner, up to five actual 200×228 screenshots, version/notes and
the tested Emery-only PBW. No separate Android/iOS KasugaBus companion exists;
PebbleKit JS/Clay does not create such a listing. Freeze all asset hashes with
the candidate. Do not use server-generated replacement branding.

The inspected Dashboard **New** route is `/dashboard/submit`. Its frontend
always sends `isPublished=true`; creation uploads the initial release. The
installed Pebble Tool 5.0.40 `_create_app` likewise hardcodes public creation,
and top-level `pebble publish` rebuilds and may normalize the PBW. Neither is an
unpublished registration shortcut. Use Dashboard New only after exact-PBW and
listing approval, uploading the frozen file without rebuilding.

An explicit **“publish this new app everywhere”** instruction can authorize
first registration, listing and publication subject to exact tested PBW approval.
KasugaBus has already completed that flow; future updates use its saved ID.
Maintaining this skill does not authorize another registration or publication.
Before Submit, write the durable creation-intent journal. Immediately after
the creation response or Dashboard App Information supplies an ID, save it
through the registration-record command before any other publication step.
Verify the Dashboard UUID/repository/release and canonical listing URL, then
persist the verified ID/URL in release configuration. Treat public propagation
as a separate status. If a response is lost or only part of the upload works,
resume by the saved ID or authenticated UUID discovery. Never submit New again
while creation is uncertain. See [releasing.md](../../../docs/releasing.md)
for the maintained commands and narrow configuration transition.

Read [docs/releasing.md](../../../docs/releasing.md). For releases, use the
frozen artifact and approval flow in [kasugabus-release](../kasugabus-release/SKILL.md).
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

Inspect the installed Pebble publisher code/help before invoking its private
upload method; check signature compatibility. The top-level `pebble publish`
rebuilds and may register an app, so it is excluded.

The configured `dashboard-form-2026-10-01` contract matches the official Edit
Listing frontend inspected read-only during setup; see its evidence in
[releasing.md](../../../docs/releasing.md). It sends existing title, website,
source, visibility and Android companion values with the requested description,
without replacing assets or category. It rejects iOS/unknown companion shapes
because the observed form does not submit those fields. Reinspect the current
official form if the contract changes; do not ask the user to design API
bindings or weaken the guard. The authorized 1.0.0 publication verified this PATCH contract with preservation
and exact text read-back; setup-only evidence predates that write. Use the
authorized Dashboard UI if unsupported metadata prevents a safe scripted edit,
checking all preserved fields before and after.

Read back the existing app first, match both ID and UUID, preserve title,
website/source, visibility/category, unknown metadata, both companions, icons,
banners/headers/screenshots and prior releases. Never supply guessed empty
defaults. Tokens remain in memory and go only to official auth/API hosts.
Existing draft or mismatched PBW needs review, not an automatic overwrite.

When the user specifically requests updated artwork, freeze the named new
assets with a version-specific hash manifest and obtain their approval with
the exact PBW. Complete the normal release/preservation flow first, then use
Dashboard Edit Listing for only those assets. Preserve all other fields and
record a separate before/after read-back. Follow the resumable artwork procedure
in `docs/releasing.md`; do not reset the uploader's original preservation
baseline or repeat New. A later `verify` is read-only and does not require an
artwork upload to be repeated.

Verify Dashboard app plus Emery assets, general and `?hardware=emery` public
catalog (`/api/v1/apps/uuid/UUID`), downloaded PBW digest and canonical public
listing/changelog. Match the returned app ID/UUID and actual latest version/
notes/description. A successful upload/PATCH is insufficient. Poll read-only
in bounded intervals and report pending surfaces. Emery catalog is a My Apps
proxy; claim observed phone cache freshness only after actual phone inspection.
