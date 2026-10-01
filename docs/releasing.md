# KasugaBus release workflow

This workflow is prepared and tested locally. Version **1.0.0** has not been
bumped, committed, tagged, pushed or published by this setup task. The intended
GitHub destination is `ewijaya/kasugabus-pebble`; there is no initialized local
Git repository. GitHub Pages is configured locally and remains undeployed.
KasugaBus has no saved store App ID. Authenticated read-only checks on
2026-10-01 found no Dashboard listing matching its UUID or repository.

The package/PBW UUID and store App ID are different identities. Package UUID
`d7ba77b0-d528-4cc8-b35c-7052798152c9` is known now; RePebble assigns its own App
ID when a listing is created. `store_app_id` and `store_listing_url` remain
null until a matching existing record is adopted or first registration returns
an ID and identity is verified. Never derive an App ID from the UUID, guess
one, or reuse the reference app's ID.

The user's later **“publish this new app everywhere”** instruction authorizes
registration, the initial listing and publication, subject to physical
approval of the exact tested PBW and review of the initial listing/assets.
Workflow setup authorizes none of these external changes. Repository/source
pushes and timetable hosting can be authorized as preparation independently
of the final app-release tag and uploads; the complete future prompt below
makes that sequence explicit.

First registration is a public release action. The official Dashboard New
flow at `/dashboard/submit` uploads the PBW and sends `isPublished=true` with
the chosen visibility. The inspected Pebble Tool5.0.40 `_create_app` also
hardcodes public creation; top-level `pebble publish` rebuilds and may normalize
the PBW. Use neither as an unpublished registration shortcut. New registration
uses the Dashboard only after candidate approval, with the exact frozen PBW.
The helper journals the submission and assigned ID; it does not submit the
Dashboard form or create a developer account.

[New-flow evidence](../artifacts/store-new-form-inspection.json) and
[account discovery](../artifacts/store-discovery-2026-10-01.json) contain no
credentials. Browser automation was unavailable during setup, so the New
requirements were inspected from authenticated official frontend source and
API responses, not a completed browser walkthrough. No PBW or listing asset
was uploaded. If sign-in is required later, let the owner complete it without
requesting passwords or tokens.

The maintained configuration is [release-config.json](release-config.json).
Project identity is package `kasugabus`, display `KasugaBus`, UUID
`d7ba77b0-d528-4cc8-b35c-7052798152c9`, Emery only, interactive app. The actual
build output is `build/kasugabus-pebble.pbw` because the Pebble tool names the
PBW after this project directory. No identifier or listing copy from the
reference project is used.

## Scope and preflight

Loading a release skill or asking to maintain this workflow does not authorize
a release. A future explicit request must identify destinations and authorize
the release's version/doc edits, commit, tag, push and publication. Review
`git status`, branch, origin, tags, changes since the previous tag, and existing
GitHub/store releases. Do not initialize Git, create a remote, commit unrelated
changes or discard work to satisfy a preflight guard without authorization.

`python3 scripts/release.py plan` is offline and read-only. `plan --remote
--destination github` adds a read-only existing-release check, using the actual
configured repository. A GitHub profile URL alone is not a repository remote.
For an unregistered app, use the installed Pebble Tool interpreter for
`scripts/release.py discover-registration`. It inspects authenticated UUID
lookup and the Dashboard collection without a candidate, physical approval,
registration or publication. Its output is discovery evidence, not permission
to submit New. If a matching listing exists, `discover-registration --save-match`
saves its verified ID and canonical URL locally; it does not edit the listing.
Review and include that configuration change in the authorized source commit
before building/freezing with the ordinary `existing` mode.
Use patch for compatible fixes, minor for new user-facing functionality, and
major for an intentional incompatible change. For the first release retain the
already selected 1.0.0 unless the user explicitly approves another version.
The helper proposes context; it never changes a version automatically.

Review and commit the intended package version, both lockfile version fields,
README, CHANGELOG, `docs/releases/VERSION.md` and the proposed store description
before freezing. Derive notes from the actual diff. The draft initial notes
record incomplete phone/device checks and undeployed hosting; remove those
limitations only after the corresponding work is done. README publication
status uses one `<!-- kasugabus-release-status -->` marker followed by a single
status line. Preparation requires a clean committed source on the configured
branch and matching origin, with `build/`, `node_modules/` and `.release/`
ignored and untracked.

Before preparing the **first complete personal release**, review the current
[verification report](VERIFICATION.md) against [PRD sections 15 and 16](../PRD.md),
including every acceptance case and milestone exit criterion. Record passed,
failed and unobserved results with dates and evidence; a missing report is an
incomplete gate. Check these requirements explicitly:

- Reconcile the current dataset against the official operator sources and
  review its effective date, per-operator validity, holiday/exception calendar
  coverage, source verification dates and review due date. Confirm coverage
  includes the release's intended service dates, with verified exceptions or
  visible unconfirmed states for gaps. A responding feed or passing compiler
  does not make expired source review current; perform and record the required
  source review before claiming fresh data.
- Configure the approved project-controlled production HTTPS timetable origin
  consistently in the phone and hosting configuration. Follow
  [PUBLISHING.md](PUBLISHING.md), run the maintained live-host validation and
  retain its result. A loopback feed, null URL or local static files do not
  satisfy this gate. Prove an end-to-end timetable-only update through the
  deployed feed without reinstalling the PBW, including current/future
  applicability and recovery behavior.
- Record the actual watch model and firmware, phone OS and companion-app
  version. Complete physical readability and navigation checks, location
  permission/latency/failure behavior, Clay settings and persistence,
  connection loss/offline operation, and update/recovery checks on that setup.
  Bind candidate-specific observations to its PBW SHA-256; emulator results
  and an installation alone do not prove these physical outcomes.
- Complete the seven-day actual-use review required by the personal-release
  milestone, recording stability, battery observations and known limitations.
  Do not invent a battery-life percentage or treat a short emulator run as an
  endurance result.

These are release-agent preflight gates in addition to the scripted build and
publication guards. A passing build/runtime audit does not certify them.
Missing, failed or unobserved results remain **release blockers**. Only a
later explicit scoped-release decision may authorize an incremental build
with named omissions; record that scope and its limitations in verification,
notes and listing claims, and do not call it the completed first release.
Workflow creation and validation itself makes no release-readiness claim.

## One clean build and actual memory evidence

Run `python3 scripts/test.py` for all data/codec/calendar, C preference/storage,
phone and controlled HTTP-feed suites. This also checks the bundled binary and
phone catalogue against the editable dataset; regenerate only from reviewed
source data when stale.

```sh
python3 scripts/check_release.py --static-only
```

This runs the tests and a real `pebble clean`/`pebble build`, verifies PBW
identity/platform/app metadata, records the build log and digest in
`build/release-audit.json`, and enforces [build-budgets.json](../tests/build-budgets.json).
It explicitly removes any remaining generated `build/` directory after the
SDK clean: Tool 5.0.40's Waf `distclean` can leave stale output when its
environment-bearing lock has been removed. A redirected/symlinked build
directory is refused. Keep runtime logs and installation receipts outside
`build/`, as in the commands below.
Native binary and static RAM each target at least 20 percent headroom from
128 KiB; resources target the same headroom from 256 KiB. The 24 KiB timetable
target is enforced. PBW zip size has a separate 2 MiB engineering guard because
phone JS and source maps are not the native memory footprint.

The known linker RWX warning is recorded and nonfatal if the build succeeds.
Static linker free RAM is not a runtime heap measurement. Capture a fresh
installation of the exact audited PBW and actual logs outside `build/`:

```sh
python3 scripts/capture_runtime.py --environment emulator \
  --output artifacts/release-runtime.log --seconds 900 \
  --stop-file artifacts/runtime-capture.stop
```

While capture runs, exercise navigation and a complete controlled update.
The capture script calls `pebble install --logs` on the named, hash-checked
artifact, then records a SHA-bound installation receipt alongside the raw log.
It never rebuilds. Use `--environment physical` for a phone-connected watch.
Stop early with Ctrl-C or by creating the named stop file; both finalize the
receipt. Capture lasts at most 1800 seconds and never overwrites old evidence.
Record
the minimum observed `heapNN`, `heap=NN` or `heap NN` value, including the
transfer path rather than only an idle launch. Then seal the existing audit:

```sh
python3 scripts/check_release.py \
  --complete-runtime artifacts/release-runtime.log \
  --environment emulator --scenarios launch,navigation,update-transfer
```

The raw log and receipt must be captured after the clean build. They are hashed
and bound to the same PBW digest and installed environment. The raw log must
contain launch, UI-render and successful update-commit markers and meet 20
percent measured free-heap headroom. Scenario names still attest the exact
interactions exercised; the helper does not drive the human QA or turn
fabricated logs into evidence. It does not
substitute emulator success for physical readability, location permission,
companion compatibility, disconnect and seven-day use checks. A plain
`check_release.py` invocation records the static audit then fails while runtime
evidence is missing, so that incomplete checks cannot appear release ready.

The verified local toolchain at creation was Pebble Tool 5.0.40 / SDK 4.33.1,
bundled ARM GCC 14.2.1, Python 3.13.5, Node 26.8.1, npm 11.19.0 and Clay 1.1.0.
Record the versions actually used for each candidate.

## Freeze and physically approve

After the authorized repository/hosting preparation and acceptance review,
use the sealed audit. Preparation reuses its exact PBW; rebuilding here would
invalidate the runtime evidence. Authenticated release commands use the
installed Pebble Tool interpreter, not an unrelated system Python:

```sh
KASUGABUS_RELEASE_PYTHON="$HOME/.local/share/uv/tools/pebble-tool/bin/python"
```

For this unregistered app, prepare the complete initial listing and artwork
from [listing.json](releases/listing.json) and its [preview](releases/listing-preview.html).
Use the explicit first-publication mode:

```sh
"$KASUGABUS_RELEASE_PYTHON" scripts/release.py prepare 1.0.0 \
  --store-mode create-or-resume --listing docs/releases/listing.json \
  --audit build/release-audit.json --notes docs/releases/1.0.0.md \
  --description docs/releases/store-description.txt \
  --destination github --destination appstore --physical
```

Preparation validates existing destination releases, source/lockfile/doc
versions and the measured audit, installs the same artifact on the physical
watch, and freezes it with notes, description, runtime log and audit under
`.release/1.0.0/`. First-publication mode also freezes the full listing and
every icon/banner/screenshot with byte size and SHA-256. Existing registered
releases use the default `existing` mode and preserve their current artwork.
No public mutation occurs. An existing candidate is never
overwritten; an unavailable watch stops preparation before freezing. Report
PBW SHA-256/bytes, source commit, static budgets, measured minimum heap and
device/phone limitations. The user must approve the physical behavior of
**this exact SHA-256**, including home/board/details/picker navigation,
operator/direction labels, offline operation and settings/update recovery.
An installation success is not this approval. Review the frozen listing and
artwork alongside the PBW before initial publication.

## Register once and resume safely

Inspect saved configuration before opening New. Use authenticated read-only
UUID lookup and the Dashboard collection to find existing listings, including
unpublished ones. Verify the package UUID, configured source repository,
watchapp type and available release/hardware metadata. A title match alone
is not enough; a conflicting source/UUID or ambiguous match blocks creation.
A saved App ID always means resume/verify, never create another listing.
Before freezing, run the read-only check:

```sh
"$KASUGABUS_RELEASE_PYTHON" scripts/release.py discover-registration
```

If it finds a verified existing listing, save the match locally with
`discover-registration --save-match`, skip New, and use `prepare` in its
default `existing` mode, without `--listing`. Existing metadata, icons, banners
and screenshots are preserved; the initial-listing draft is not a replacement
instruction. Review existing versions before choosing the next release.
`prepare --store-mode create-or-resume` refuses an already discovered match
before physical installation or candidate freezing.
If this project already has an unresolved New attempt, do not adopt its newly
visible ID with `--save-match`. That shortcut is refused: reconcile the original
candidate first so its exact approval and receipt remain intact.

After the candidate and proposed initial listing are approved, journal intent:

```sh
"$KASUGABUS_RELEASE_PYTHON" scripts/release.py begin-registration 1.0.0 \
  --approve-publish 1.0.0 --approve-sha256 THE_REPORTED_SHA256 \
  --approve-destination github --approve-destination appstore \
  --approve-physical
```

This command does not submit a form. If a matching listing appeared only after
the candidate was frozen and there is no prior New intent, it adopts that
listing and binds a snapshot of its unrelated metadata/assets. This late
adoption uses existing-listing preservation checks on the same frozen PBW;
it does not demand replacement artwork or the initial-listing attestation
below. If there was a prior New intent, a discovered match instead recovers
that attempt and still requires its full listing read-back. Only a newly saved creation intent permits
one Dashboard **New** submission. A pending or uncertain earlier intent blocks
another submission even if the operator changes the proposed app version.
Do not delete a candidate or its registration journal to bypass that protection.
The project-wide guard is `.release/registration.json`; each candidate also
retains its own `.release/VERSION/manifest.json`. The guard is created with an
exclusive filesystem operation and flushed to disk before New is permitted.
Keep both journals after a timeout, crash or partial publication. Starting a
new candidate/version does not reset an uncertain registration.

Open `https://developer.repebble.com/dashboard` and choose **New**. Use the
frozen PBW and files in `.release/1.0.0/listing-assets/`, with the frozen
`listing.json` and notes. Check extracted UUID, version, watchapp type and
Emery-only hardware before continuing. Set the approved title, description,
Daily category, source repository and listed visibility. Supply both own icons
to avoid automatic icon generation, three native screenshots and the Emery
banner. Leave separate companion-app fields empty. Review the complete form
before **Submit App**; submission publishes the initial release.

Immediately after the creation response or Dashboard **App Information**
shows the assigned ID, record it before any other publication action:

```sh
"$KASUGABUS_RELEASE_PYTHON" scripts/release.py record-registration 1.0.0 \
  --app-id THE_ASSIGNED_ID
```

The ID is journaled first. Subsequent authenticated identity checks and the
narrow configuration transition must not erase that receipt on failure.
The verified ID and canonical listing URL are saved in
`docs/release-config.json`; authentication cookies/tokens are never saved there.
Public reachability and catalog propagation remain separate verification
states. Do not claim an assigned ID alone proves that every public surface is
current.

For a listing created by this workflow's New submission, compare the Dashboard
listing with every frozen metadata field and asset.
Check both icons, the banner and screenshot order, UUID, repository, hardware,
version, notes and the downloaded PBW SHA-256. Record the bounded confirmation
file expected by `record-registration --confirm-listing --evidence FILE` only
after that actual read-back. Keep incomplete artwork or release processing
pending. Complete missing approved content on the same assigned listing with
the frozen assets; never start New again.

The confirmation JSON has exactly these fields: `schema: 1`, `confirmed: true`,
the assigned `app_id`, package `uuid`, frozen `listing_sha256`, exact
`artifact_sha256`, `metadata`, `assets`, and `dashboard_readback`. `metadata`
must equal every value in the frozen listing. `assets` preserves its order,
with each asset's `role`, full `sha256` and `platform` when present.
`dashboard_readback` contains the observed `app_id`, `uuid`, `source`,
`type: "watchapp"` and `platforms: ["emery"]`. Record this small attestation
only after comparing the actual Dashboard and downloaded release; do not
generate it merely by copying the proposed listing, or save account responses
or credentials. Then run:

```sh
"$KASUGABUS_RELEASE_PYTHON" scripts/release.py record-registration 1.0.0 \
  --app-id THE_ASSIGNED_ID --confirm-listing \
  --evidence .release/1.0.0/observed-listing.json
```

If the response is lost or a later step fails, recover read-only:

```sh
"$KASUGABUS_RELEASE_PYTHON" scripts/release.py reconcile-registration 1.0.0
```

Use the saved ID first and compare authenticated UUID/repository discovery.
If no matching record is visible after an uncertain submission, stop with
registration pending; absence at that moment does not establish that creation
failed. Never blindly retry Submit. A same-version release with the exact PBW
is reused; a different PBW, draft or conflicting identity requires review.

## Publish the approved artifact

Only when the user has explicitly approved this version, SHA-256, physical
candidate and recorded destinations, run with the installed Pebble Python
environment (the interpreter in `pebble`'s shebang):

```sh
"$KASUGABUS_RELEASE_PYTHON" scripts/release.py publish 1.0.0 \
  --approve-publish 1.0.0 --approve-sha256 THE_REPORTED_SHA256 \
  --approve-destination github --approve-destination appstore \
  --approve-physical
```

These flags record actual consent; supplying them is not a substitute for it.
Publication verifies that source commit/config/frozen notes/audit/artifact
remain unchanged and that explicit approval names exactly the frozen
destinations. A fingerprint of `src`, `resources`, `data`, `tools`, `scripts`,
`tests`, package/lock files and `wscript` is recorded before the tests/build and
checked afterward and during preparation. Generated verification reports and
release documentation can be written later; config, notes and listing text
are separately frozen and checked. Assigning a later HEAD cannot
relabel an older build. Publication rechecks remote version ordering before
mutation so a newly published higher version cannot be displaced. It pushes
the source before an annotated tag, attaches that
same PBW to the GitHub Release, and uses the installed
`PublishCommand._upload_release` method to upload that same file to the
configured **existing** KasugaBus listing. Its signature is checked at runtime.
The top-level `pebble publish` rebuilds, can normalize a PBW and auto-create
accounts/listings, so it is excluded from this workflow. Existing differing
versions, drafts and assets stop the workflow rather than being overwritten.
Auth imports are lazy. Firebase tokens stay in memory and are never printed,
saved in a receipt, passed as shell text or sent to a nonofficial endpoint.

## Listing contract and preservation

The installed CLI handles existing-release uploads. The official authenticated
Dashboard record and Edit Listing frontend were also inspected read-only on
2026-10-01; [the evidence](../artifacts/store-edit-form-inspection.json) records
the source hash and response shape without another app's ID or credentials.
`listing_patch_contract: "dashboard-form-2026-10-01"` selects those observed
multipart fields: title, description, website, source, visibility and Android
companion name/URL/required. All values except the requested description come
from the current authenticated record. Icons, screenshots, banners and
category are omitted exactly as in an edit with no changes to those fields.

The observed frontend loads iOS companion state but does not submit it. The
helper therefore refuses nonempty iOS or unknown companion shapes, duplicate
Android companions, restricted visibility and incomplete metadata before
uploading; it does not guess a payload. KasugaBus has no separate companion
app listing. Reinspect the current official form before future releases if
its shape changes. The older `partial-description` and `dashboard-form-v1`
alternatives require their own verified server semantics/field bindings;
they are not selected by this configuration.

The helper compares all unrelated metadata, including unknown fields and
assets, before and after upload/PATCH. Every prior release ID/version/artifact
URL/publication state/notes must remain an unchanged subset after adding a
release. It never replaces screenshots, icons,
banners, headers, companion metadata, category, visibility or previous
releases. If the contract is unavailable, use a separately reviewed official
Dashboard edit flow for the exact description and read-back preservation check;
do not weaken the script guard or borrow another app's listing ID. Offline
mocks verify our request/preservation behavior. No live PATCH was made during
setup; the later authorized write still requires read-back comparison.

## Verify and recover

Upload success is not completion. Verification downloads/hashes GitHub and
store PBWs and checks the GitHub latest release, authenticated Dashboard app
and Emery asset description, public catalog general and `?hardware=emery`,
and canonical public listing/changelog. The verified public response is
`GET https://appstore-api.repebble.com/api/v1/apps/uuid/UUID`, with a `data`
array containing matching ID/UUID, description, hardware platforms and a
`latest_release` with `version`, `release_notes` and `pbw_file`. The Emery
catalog is a My Apps proxy; phone cache state requires observation on the
actual phone. A successful API response cannot prove that phone display is fresh.

```sh
python3 scripts/release.py verify 1.0.0 --attempts 3
```

Each attempt prints per-destination status; retries are bounded to 1..5 attempts
with 20-second intervals. Public reads enforce HTTPS, bounded redirects,
response byte limits and a total deadline; subprocess API calls also have
timeouts. Auth/metadata requests reject redirects so a Firebase token cannot
be forwarded with a redirected POST body. Verification reads remote state and updates only the
local receipt. Partial publication is preserved in the candidate journal. Do
not rebuild, replace an asset or declare all destinations updated while a
surface remains pending. After propagation, rerun the approved publish command
to verify matching existing uploads and synchronize README availability and
`docs/releases/latest-status.json`. Only verified destinations are advertised.
That final documentation commit/push is part of an explicitly authorized
publication, never part of maintaining this workflow. The helper journals the
documentation commit before pushing it; if that push fails, an approved retry
pushes the same saved commit even when no new documentation diff remains.

## Future invocation

For the current uninitialized repository, undeployed feed and unregistered
listing, use this exact request later:

> Publish this new app everywhere using $kasugabus-publish-release for
> ewijaya/kasugabus-pebble and RePebble. Retain 1.0.0. I authorize repository
> initialization/creation, reviewed source/documentation commits and source
> pushes, and dedicated GitHub Pages setup/deployment for the reviewed
> timetable feed. Verify live hosting and the timetable-only update, and
> review PRD acceptance evidence; keep missing physical/seven-day checks as
> blockers. Inspect my authenticated Dashboard for an existing listing by
> UUID, repository and release metadata. If none exists, prepare Dashboard
> New with KasugaBus's complete listing and artwork. Build, audit and freeze
> one candidate, install those exact bytes on my watch, and report its full
> SHA-256 and listing preview. Wait for my physical approval of that candidate
> before submitting New, creating/pushing a release tag, or publishing a
> GitHub Release. Then publish the same frozen PBW, immediately record and
> verify the assigned App ID/public URL, resume safely after failures, and
> verify every Dashboard/public/catalog surface without rebuilding.

The phrase “publish this new app everywhere” authorizes first registration,
initial listing and publication subject to approval of the exact tested PBW;
it must not trigger a second redundant registration-permission request. The
expanded prompt also states the repository/source-push and Pages preparation
scope needed to verify hosting before freezing. First-publication submission
and app-release tags/uploads remain behind the exact-candidate approval.
Loading this skill or maintaining its files does not authorize any of them.

After registration, the workflow reads the saved verified App ID and uses the
existing-listing mode. Re-discover and verify identity if configuration is
missing; never treat a missing local ID as proof that no remote listing exists.
Do not overwrite the initial published version or recreate a listing merely
because an earlier command failed.
