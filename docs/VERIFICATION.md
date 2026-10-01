# KasugaBus verification — 1 October 2026

KasugaBus **1.0.0** is published as an initial release with explicitly accepted
physical and seven-day validation limitations. The owner approved the installed
candidate and proposed listing before publication to GitHub and RePebble.
GitHub source and the production timetable feed are live. The broader PRD
personal-use acceptance checks remain open; publication does not mark them passed.

All ten [icon concepts](../artifacts/icon-options/index.html), generation prompts
and final Neon Express 25 × 25 asset are retained. Current release evidence and
earlier development/physical observations are identified separately below.

## Published artifact and exact approval

| Item | Release result |
| --- | --- |
| App | KasugaBus 1.0.0, interactive app, Emery only |
| Source / tag | `3110deecde6d154a52b1d7971e6e3c5c1bd1a54d`, `v1.0.0` |
| PBW | [Published PBW](https://github.com/ewijaya/kasugabus-pebble/releases/download/v1.0.0/kasugabus-pebble.pbw), **817,922 bytes** |
| SHA-256 | `233627ffc63e0964bff272c3a56bac11e6f7634992b06cb45143524e2bc5330a` |
| GitHub | [KasugaBus v1.0.0](https://github.com/ewijaya/kasugabus-pebble/releases/tag/v1.0.0) |
| RePebble | [KasugaBus](https://apps.repebble.com/f63e6ed24301414a95909564), App ID `f63e6ed24301414a95909564` |
| Package UUID | `d7ba77b0-d528-4cc8-b35c-7052798152c9`; distinct from the App ID |
| Native binary / static RAM / resources | 31,428 / 39,170 / 30,178 bytes |
| Linker free RAM | 91,902 bytes; not a runtime heap measurement |
| Minimum measured free heap | **32,400 bytes**, emulator launch/navigation/update-transfer |
| Timetable | 24,203-byte bundled baseline v1; production feed current v2 |

The owner's exact approval was: **“I approve the installed KasugaBus 1.0.0
candidate and listing. Publish it everywhere.”** The release receipt binds that
approval to this version, digest and both destinations. Both published PBW
downloads were hash-verified; the Dashboard and canonical public page are visible.

[Publication verification](../artifacts/releases/1.0.0/publication.json) passed for GitHub
(including the downloaded PBW and latest release), Dashboard, the general and
Emery-filtered catalogs, and the canonical public store page/changelog. The
phone's My Apps cache was not observed; the Emery catalog is a proxy for it.

[Build audit](../artifacts/releases/1.0.0/build-audit.json),
[clean build/test log](../artifacts/releases/1.0.0/build.log),
[runtime log](../artifacts/releases/1.0.0/runtime.log) and
[exact-artifact emulator installation receipt](../artifacts/releases/1.0.0/runtime-install.json)
bind the release checks to this PBW. The clean run passed **122 Python tests**,
**25 phone scenarios**, **5 Clay/settings integration checks**, **5 controlled
HTTP-feed scenarios** and strict portable C checks. Automated cases remain
isolated fixtures; the actual publication has separate
[publication](../artifacts/releases/1.0.0/publication.json),
[asset read-back](../artifacts/releases/1.0.0/asset-readback.json) and
[text read-back](../artifacts/releases/1.0.0/text-readback.json) evidence.

The public API represented hardware platforms as objects, so the read-only
publication verifier was corrected to recognize the observed shape. Corrected
verification passed on its first attempt, with **40 release unit tests**
(31 existing and nine new) passing. This later tooling check did not rebuild or
replace the approved PBW; its frozen clean-build result remains 122 Python tests.

The actual SDK pypkjs/XHR worker fetched the deployed HTTPS manifest and v2
payload. It transferred all **24,203 bytes in 127 chunks**, received **127 native
chunk acknowledgements**, and retained active v2 and the successful feed-check
timestamp across restart. Preferences were unchanged and the PBW was not
reinstalled for the update. This is emulator evidence, with no upcoming
production release in this focused check; it does not establish physical future
activation or interruption recovery. See the
[production-feed proof](../artifacts/releases/1.0.0/production-feed.json) and
[trace](../artifacts/releases/1.0.0/production-feed.log).

Release-artifact [Home](../artifacts/screenshots/release-1.0.0-home.png),
[board](../artifacts/screenshots/release-1.0.0-board.png) and
[details](../artifacts/screenshots/release-1.0.0-details.png) captures preserve the
actual native 200 × 228 framebuffer. Historical launcher, development and
physical observations below remain bound to their original packages.

## Development acceptance artifact (before release freeze)

| Item | Observed result |
| --- | --- |
| App | KasugaBus 1.0.0, interactive app, Emery only |
| UUID | `d7ba77b0-d528-4cc8-b35c-7052798152c9` |
| PBW | [KasugaBus-1.0.0-emery.pbw](../artifacts/KasugaBus-1.0.0-emery.pbw), 817,565 bytes |
| SHA-256 | `2bddb0b092d51c7cdab6944c56a11bb377f4a97932643ee37541450bfc8bdb09` |
| Toolchain | Pebble Tool 5.0.40 / SDK 4.33.1 / bundled ARM GCC 14.2.1 |
| Host runtimes | Python 3.13.5; Node 26.8.1; npm 11.19.0; uv 0.12.9 |
| Direct npm dependency | `@rebble/clay` 1.1.0, lockfile pinned |
| Native binary | 31,428 / 131,072 bytes |
| Static RAM | 39,170 / 131,072 bytes |
| Resources | 30,178 / 262,144 bytes |
| Minimum observed free heap | 32,400 bytes across launch/navigation/transfers; exceeds the 26,215-byte headroom gate |
| Timetable | 24,203 bytes; 32,768-byte format/storage ceiling |

[Clean build/test log](../artifacts/final-workflow-build.log),
[final audit](../artifacts/final-workflow-build-audit.json),
[raw runtime log](../artifacts/runtime-workflow-acceptance.log), and
[exact-artifact install receipt](../artifacts/runtime-workflow-acceptance.log.install.json)
bind measurements to this PBW. Static linker free RAM, 91,902 bytes, is not a
runtime allocation measurement. The known SDK linker RWX warning is nonfatal.
No SDK/compiler was replaced. This historical audit predates the later
authorized source/feed publication and final release-candidate freeze.

## Historical automated coverage (development PBW `2bddb0b0…`)

The preceding development clean-build run passed **113 Python tests**, **25 phone scenarios**, **5
Clay/settings integration checks**, **5 real loopback HTTP-feed scenarios**,
and strict portable C preference/control, policy and storage suites. The C
engine runs through the Python codec fixtures. Python cases include 21 hosting,
31 release-workflow, 32 first-registration, two clean-output and four installed-SDK
bridge/wire tests. Registration cases cover exact approval, lost responses,
durable ID capture before local/network failures, cross-version and concurrent
duplicate prevention, existing-listing adoption and partial-listing recovery.
The release suite includes recovery after a documentation commit and failed
push. Tests use isolated fixtures; no real publication was attempted.

| PRD acceptance group | Evidence and result |
| --- | --- |
| Exact departure minute, ceiling countdown, last service, overnight times, JST independence | `tests/test_engine.c`, `tests/test_codec.py`; Due spans the scheduled minute; expired trips leave selection; originating service dates are retained |
| Weekday/Saturday/Sunday, substitute holidays, exact-date exceptions, no-service and unknown coverage | Engine/storage fixtures; no fabricated weekday fallback; coverage limits remain visible even with a manual override |
| Boarded route/operator/direction, loop and route-number changes, downstream filter | Reconciliation and engine fixtures preserve independent identities and verified calls |
| Walk plus buffer and trip context | Explicit five-minute walk/two-minute buffer fixture yields 10:26 for 10:33; general and At stop contexts do not reuse that walk |
| Preferences and migration | Checksummed alternate banks, restart, torn writes, legacy migration, missing IDs, cancellation and invalid settings; durable Restore request barrier |
| Nearby | Good/poor/stale/unavailable/denied/timeout/outside, uncertain ties, late results, location opt-out; no inferred walking time or ranking of unverified coordinates |
| Daily/manual checks | Readiness, offline deferral, rolling 24-hour attempt throttle, manual bypass, disabled automatic checks, clock rollback and one active job |
| Candidate validation | Schema/app compatibility, dates, versions, SHA-256, CRC, length, references, UTF-8, calendars, sorting and malformed data rejected before use |
| Transfer/storage recovery | Duplicate/reordered/missing/wrong-session chunks, bounded retries, torn commits/directories, corrupt payloads, pending preservation, full slots, multiple future corrections and legacy migration |
| Restore races | Phone manifest/payload/transfer cancellation and late callbacks; native deferred BEGIN plus old/missing request rejection across restart; a new request remains usable |
| Release/hosting tooling | Exact-byte freeze/approval, first-registration and adoption recovery, metadata preservation, bounded verification, partial publication and docs-push retry fixtures, dedicated Pages site/history/allowlist guards; no real publication |

Run the maintained suite with `python3 scripts/test.py`. Fixtures which invent
times, versions or dates are isolated test inputs, never published timetable
data.

## Historical native Emery flows and visual inspection

The development PBW `2bddb0b0…` [controlled update run](../artifacts/native-update-workflow-acceptance.log) delivered
complete current **v28** and future **v29** copies of the reviewed data in
**254 chunks**, through the production phone updater/sender and real C
AppMessage receiver. The same installed UUID was stopped and started without
PBW reinstallation. Both snapshots persisted. A replacement interrupted after
two chunks retained them after restart. Corrupt/incompatible/interrupted HTTP
inputs produced zero candidate chunks, and failure did not advance the last
successful feed-check timestamp. These are artificial test versions, not
published releases.

[Monotonic timing](../artifacts/native-profile-workflow-acceptance.json) measured three
launches with retained snapshots: **598.59–602.80 ms from app initialization**,
or **632.55–637.32 ms including the start command**. Twelve ordinary buttons
rendered in **10.77–83.76 ms**. All samples met the PRD's 1-second / 200-ms
targets. They are emulator observations, not physical-watch timing claims.

Development-artifact [Home](../artifacts/screenshots/emery_workflow_home.png),
[board](../artifacts/screenshots/emery_workflow_board.png), and
[details](../artifacts/screenshots/emery_workflow_details.png) were captured and
visually inspected at native resolution. The preceding icon package's
[selected](../artifacts/screenshots/emery_launcher_neon_selected.png) /
[unselected](../artifacts/screenshots/emery_launcher_neon_unselected.png)
launcher rows were also captured and visually inspected at native resolution.
The black transparent bus stays visible on both launcher backgrounds. An
initial white candidate failed the unselected-row check and was replaced.

The owner-confirmed [Neon Express package](../artifacts/KasugaBus-1.0.0-emery-neon-installed.pbw),
SHA-256 `4679b90e11353358a85c629ceeb926cfd564556666158899d1d633bdd329f6d6`,
retains its [audit](../artifacts/final-neon-build-audit.json) and current24/future25
runtime evidence. The [development build comparison](../artifacts/workflow-build-comparison.json)
finds changes only in native metadata bytes 124/125, its manifest checksum and
ZIP timestamps. Native application code, phone JavaScript and resources are
identical between those preceding development packages. This comparison does
not include the published candidate's later XHR correction. Physical QA stays
reported under the package actually observed.

The first renewal attempt found that SDK `pebble clean` left old build output
when its environment-bearing Waf lock was absent; missing fresh build metrics
correctly stopped the audit. [That diagnostic](../artifacts/diagnostic-workflow-clean-noop.log)
is retained. The helper now removes leftover generated output, refuses a
symlinked build directory, and the fresh full build above passed.

The earlier full acceptance artifact is preserved as
[before-icon PBW](../artifacts/KasugaBus-1.0.0-emery-before-icon.pbw), SHA-256
`466df8dd233cb2886171eb44fe23f1188fd1b3f68bc1d872249be3262a8dff5b`.
Its [binary comparison](../artifacts/neon-build-comparison.json) shows identical
native bytes from offset 168 onward and identical phone JavaScript; the native
differences are app metadata for the launcher resource. The following broad
scenario evidence belongs to that earlier artifact, not a repeat on the
published PBW.

The earlier [navigation run](../artifacts/native-navigation-acceptance.log) verified
restart persistence and captured home, board, full/Japanese details,
favourites, all stops/directions, settings, disabled Nearby, saved-origin
leave-by, countdown boundaries, high contrast, local 12-hour clock/JST bus
labels, and source/feed/pending status. The [removed-trip
fixture](../artifacts/native-focus-acceptance.log) retained an explicit removed
selection instead of silently moving it to a different trip, then complete
reviewed data was restored through the feed harness.

The [rollover retry](../artifacts/native-rollover-acceptance-retry.log) activated
v21 offline on 3 October before any diagnostic STATE request. It preserved
preferences, showed Hankyu's weekend no-service condition, retained the
November source-review notice, and showed unconfirmed December coverage and
next-JST-day override expiry. [Restore acceptance](../artifacts/native-restore-acceptance.log)
returned to bundled v1 and rejected obsolete download sessions across restart.
The [native log](../artifacts/native-postreset-acceptance.log) explicitly records
`Restore cancelled deferred BEGIN session990024` before its ACK.

All 29 numbered pre-icon [native screenshots](../artifacts/screenshots/README.md) were
visually inspected at **200 × 228**. Text, route/direction separation, Japanese
glyphs and actionable status fit. Captures preserve the emulator's actual
backlight dimming; they are not recoloured or resized. Test dates/walking
allowances are labelled fixtures. The earlier cleanup restored the actual time
and original preferences and explicitly restored reviewed bundled v1. The
development update harness restored original preferences and retained its
complete test versions v28/v29 in the emulator. Production and bundled data
were v1 at that stage; production has since advanced to v2, while the bundled
baseline remains v1.

The first rollover attempt stalled in SDK emulator firmware logging. The
[read-only diagnosis](../artifacts/emulator-rollover-stall-diagnosis.md) found
KasugaBus waiting normally and firmware flash/logging tasks blocked; it did
not establish an app fault. A reset preserved saved v20/v21, and the full
rollover/Restore retry passed. Historical diagnostics and failed attempts are
retained, not relabelled as successful runs. A later icon-check diagnostic
also encountered the SDK logging stall while a separate platform probe was
active; [diagnosis](../artifacts/emulator-neon-stall-diagnosis.md) and failed
`native-update-neon-final*.log` attempts are retained. After emulator reset,
the fresh development-artifact run above passed and its runtime receipt was sealed.

## Data and physical observations

The baseline has **1,411 departures, 15 boarding points, six stop groups and 32
patterns**, reconciled to **81 official sources**. Review: 2026-10-01; next full
review: 2026-11-01; service coverage ends 2026-12-27 pending verified year-end
rules. Six Hankyu pole coordinates are rankable; nine unverified Kintetsu poles
remain manual choices. See [reconciliation](DATA_RECONCILIATION.md),
[editable data](../data/timetable.json) and [source evidence](../data/sources/catalog.json).
The integrated research PDF was not used as a validated dataset. No personal
address, invented real departure, inferred walk or live-arrival information
was added.

[Earlier physical evidence](../artifacts/physical-verification.json) records an actual
successful install of the pre-icon PBW on **Pebble Time 2 / Emery v4.38.4**, using
**Poco F4, Android 14 (UKQ1.231207.002), Pebble companion 1.14.0.1**. Firmware was
read back over the developer connection. The user confirmed readable Home →
board → details and working Select navigation. The physical runtime reported
1 MiB persistence capacity, successful AppMessage initialization and 32,400
bytes free heap. This is not a physical full-slot flash-write test.

The [icon installation](../artifacts/physical-neon-installation.json)
binds successful installation and a subsequent SDK stop/start to preceding PBW
`4679b90e…`. The owner answered **“Yes, the bus icon is visible and highlighted”**.
Both attempted remote icon captures returned the Quartz watchface, so they
remain diagnostic files and are not presented as physical launcher evidence.
That physical log missed the first READY marker and is installation evidence
only. The preceding `2bddb0b0…` development PBW also [installed successfully](../artifacts/physical-workflow-installation.json)
through Dev Connection. That development install did not repeat user navigation,
icon or broader physical QA; that development runtime audit is from the emulator.
The owner later approved the separately installed published candidate and listing;
that approval does not relabel these earlier physical observations.

## Remaining full personal-use acceptance checks

The owner explicitly accepted these limitations for the initial publication.
They remain unperformed requirements for the PRD's complete personal-use
milestone, rather than claims established by publication:

- Actual GPS permission/accuracy/latency/failure behavior, Clay settings and
  persistence, physical connection loss, future activation and interrupted
  update/recovery checks on the recorded phone/watch combination.
- Sunlight readability, the three-second glance task, battery behavior and
  seven days of actual use including a weekend.

Repository setup, live hosting, first registration and exact-candidate
publication approval are complete. The limited physical v2 update is recorded
separately below and does not complete the broader recovery checks.

## Initial publication scope — 1 October 2026

The owner explicitly chose “Publish an initial release with the limitations
stated.” This permits the initial 1.0.0 release while broader physical
GPS/settings/update recovery, outdoor/glance readability, battery and seven-day
use remain outstanding. It does not mark those PRD acceptance checks passed.
Source publication and production timetable hosting are complete. The installed
1.0.0 candidate and listing received explicit physical/publication approval, and
the exact `233627ff…` PBW is available from both release destinations.
The source tag remains on `3110dee`; subsequent publication documentation does
not change the tagged release artifact.

### Live source and timetable publication

The public source repository is `ewijaya/kasugabus-pebble`, branch `main`.
The owner-selected dedicated GitHub Pages site was created with Actions and
HTTPS, and its deployment environment permits only `main`. The reviewed v1
baseline and then version-only v2 reissue both deployed successfully. V2 changes
no departures, calendars, coordinates or source dates. Both immutable payloads
remain live; HTTPS 200 without redirects, exact lengths/SHA-256/CRC, JSON/binary
MIME types and wildcard CORS passed. Pages applies `max-age=600`, an accepted
ten-minute propagation/cache delay for this feed. See
[host evidence](../artifacts/hosting-v2-http.json) and
[data re-review](DATA_RELEASE_2.md). These checks do not claim physical-phone
HTTPS or seven-day acceptance.

### Actual Poco F4 / Time 2 timetable update

The owner opened KasugaBus Data status, performed a manual check, and reported
“Active dataset v2 and a feed-success time.” This establishes the actual phone
to watch timetable-only update on the previously installed development PBW
`2bddb0b092d51c7cdab6944c56a11bb377f4a97932643ee37541450bfc8bdb09`;
no app reinstall was performed for that update. See the
[physical observation record](../artifacts/physical-production-update-v2.json).
The limited native log captured launch only; it is not claimed as chunk/commit
trace evidence. The owner's displayed v2/success result is the physical evidence.
Future activation, interrupted-transfer recovery, GPS/settings behavior, outdoor
readability, battery and seven-day use on this device remain outstanding.

### SDK binary-response compatibility correction

The deployed manifest and payload passed independent HTTPS/SHA/CRC checks, but
the first actual pypkjs worker attempt rejected a zero-length payload before
BEGIN. Two independent actual-SDK probes traced this to repeated reads of the
XHR response getter. The corrected adapter caches the binary response once;
the actual installed XHR regression now preserves all 24,320 arbitrary fixture
bytes and retains the size guard, without using the unsafe text fallback. All
nine production-observer/SDK regression tests pass. The published candidate was
clean-built with the correction and repeated the actual SDK HTTPS/native v2
transfer described in the published-artifact section. The earlier failed attempts
remain historical evidence.
The earlier global emulator firmware stall is documented separately in
[the diagnosis](../artifacts/production-feed-emulator-stall.md).
