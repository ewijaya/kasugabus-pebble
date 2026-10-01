# KasugaBus verification — 1 October 2026

The six-stop application, selected **Neon Express** launcher icon, timetable
publishing tools and app-release workflow are implemented. The development PBW below
passed fresh automated and native emulator checks and was installed on the
owner's Time 2. The owner confirmed the identical bus icon on the preceding
Neon Express package; that observation retains its original digest.
Basic physical Home → board → details checks were performed on the earlier
pre-icon build. This is an unpublished development build; the PRD's broader
physical and seven-day release checks remain open.

All ten [icon concepts](../artifacts/icon-options/index.html), generation prompts
and final 25 × 25 asset are retained. The final source audit includes first-time
registration/recovery, existing-listing adoption and the SDK clean-output fix.
Those development checks preceded source publication. The owner later authorized
an initial release with named limitations; see the publication section below.
GitHub source and the timetable feed are now live. Store registration and
exact release-candidate approval are separate steps.

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

## Automated coverage

The final clean-build run passed **113 Python tests**, **25 phone scenarios**, **5
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

## Native Emery flows and visual inspection

The final [controlled update run](../artifacts/native-update-workflow-acceptance.log) delivered
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

Final-artifact [Home](../artifacts/screenshots/emery_workflow_home.png),
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
runtime evidence. The [new build comparison](../artifacts/workflow-build-comparison.json)
finds changes only in native metadata bytes 124/125, its manifest checksum and
ZIP timestamps. Native application code, phone JavaScript and resources are
identical. Physical QA is still reported under the package actually observed.

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
scenario evidence belongs to that earlier artifact, not a second run on the
final PBW.

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
final update harness restored original preferences and retained its complete
test versions v28/v29 in the emulator; production and bundled data remain v1.

The first rollover attempt stalled in SDK emulator firmware logging. The
[read-only diagnosis](../artifacts/emulator-rollover-stall-diagnosis.md) found
KasugaBus waiting normally and firmware flash/logging tasks blocked; it did
not establish an app fault. A reset preserved saved v20/v21, and the full
rollover/Restore retry passed. Historical diagnostics and failed attempts are
retained, not relabelled as successful runs. A later icon-check diagnostic
also encountered the SDK logging stall while a separate platform probe was
active; [diagnosis](../artifacts/emulator-neon-stall-diagnosis.md) and failed
`native-update-neon-final*.log` attempts are retained. After emulator reset,
the fresh final-artifact run above passed and its runtime receipt was sealed.

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
only. The newest `2bddb0b0…` PBW also [installed successfully](../artifacts/physical-workflow-installation.json)
through Dev Connection. This latest install did not repeat user navigation,
icon or broader physical QA; the complete final runtime audit is from the emulator.

## Remaining release checks

- Set up the agreed `ewijaya/kasugabus-pebble` repository and deploy/verify its
  dedicated GitHub Pages timetable feed after authorization. There is no local
  Git repository; the intended remote is not accessible to current GitHub
  authentication. Local configuration is not a live feed.
- KasugaBus remains unregistered. Authenticated UUID/repository discovery
  found no matching listing; `store_app_id` and `store_listing_url` remain
  null. The official New/Edit form contracts were inspected read-only, and
  the complete [local listing](releases/listing-preview.html) is prepared.
  Registration publishes the initial release and awaits exact-candidate
  approval under [releasing.md](releasing.md).
- Test actual GPS permissions/accuracy/latency and failures, Clay settings and
  persistence, connection loss, production HTTPS timetable-only updates and
  physical interruption/recovery on the recorded phone/watch combination.
- Record sunlight readability, the three-second glance task, battery behaviour
  and seven days of actual use including a weekend.
- Obtain explicit physical approval of the exact frozen final PBW SHA-256 and
  named publication destinations. The owner's navigation/icon confirmation is not
  release-publication approval.

## Initial publication scope — 1 October 2026

The owner explicitly chose “Publish an initial release with the limitations
stated.” This permits the initial 1.0.0 release while broader physical
GPS/settings/update recovery, outdoor/glance readability, battery and seven-day
use remain outstanding. It does not mark those PRD acceptance checks passed.
Source publication and production timetable hosting are complete. The final
candidate is being prepared from committed source. Exact physical approval remains a separate gate.

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
nine production-observer/SDK regression tests pass. The final candidate will be
clean-built from this correction and must repeat the live native transfer.
The earlier global emulator firmware stall is documented separately in
[the diagnosis](../artifacts/production-feed-emulator-stall.md).
