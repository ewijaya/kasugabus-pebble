# Platform and storage decisions

Inspected the installed Pebble SDK before implementation using `pebble-sdk-inspector`. Original project state: only PRD.md and PLAN.md, no AGENTS.md or Git repository. No user source was replaced. The dependency already installed in the neighbouring project was reused, with registry integrity recorded for reproducible future installs.

## Local evidence

- Host arm64; Pebble Tool 5.0.40 through uv, active SDK 4.33.1.
- Bundled ARM GCC 14.2.1 (20241119), Python 3.13.5, Node 26.8.1, npm 11.19.0, uv 0.12.9.
- SDK `sdk-core/pebble/common/tools/pebble_sdk_platform.py`, `emery_platform`: 200×228 rectangular colour, 128KiB binary and application memory limits, 256KiB Appstore resource limit. These limits do not represent free heap.
- Installed Emery `pebble.h`: `persist_get_max_size`, 256-byte persistent values, AppMessage runtime size queries, UTC `time()`, timezone-aware localtime, click-provider and custom-font APIs verified locally.
- Throwaway UUID/platform probe compiled and launched independently of the app. Runtime: **1,048,576 bytes persistent capacity**, **8,200-byte inbox/outbox maximum**, **262,144 bytes actually written and read back**, successful `app_message_open(1024,1024)`.
- Japanese subset: FreeType checked all 18 distinct characters used by the six stop names in installed Noto Sans JP. A 16px restricted font is bundled; the emulator renders the full Japanese names in the dedicated details view. Font license is in resources/fonts/OFL.txt.

Generated `.lock-waf*` files capture the host build environment and are excluded from Git and publication artifacts. They are not release evidence and must not carry account credentials into the repository.

## Published 1.0.0 artifact

The owner-approved [published PBW](https://github.com/ewijaya/kasugabus-pebble/releases/download/v1.0.0/kasugabus-pebble.pbw) is **817,922 bytes**, SHA-256 `233627ffc63e0964bff272c3a56bac11e6f7634992b06cb45143524e2bc5330a`, from source `3110dee` and tag `v1.0.0`. The same frozen file is available from [GitHub Releases](https://github.com/ewijaya/kasugabus-pebble/releases/tag/v1.0.0) and [RePebble](https://apps.repebble.com/f63e6ed24301414a95909564), assigned App ID `f63e6ed24301414a95909564`. The owner approved the installed candidate and listing explicitly before publication; broader physical and seven-day acceptance remains incomplete under the accepted initial-release scope.

The [release audit](../artifacts/releases/1.0.0/build-audit.json), [build log](../artifacts/releases/1.0.0/build.log), [runtime log](../artifacts/releases/1.0.0/runtime.log) and [emulator install receipt](../artifacts/releases/1.0.0/runtime-install.json) bind **122 Python tests** and the fresh launch/navigation/update-transfer run to these bytes. Sizes are **31,428 native**, **39,170 static RAM**, **30,178 resources** and **91,902 linker-free** bytes; runtime minimum free heap is **32,400 bytes**. Static free RAM does not establish runtime headroom.

The [real SDK XHR/native HTTPS proof](../artifacts/releases/1.0.0/production-feed.json) transferred production v2 in **127 native-acknowledged chunks**. Restart retained active v2 and the successful check timestamp, preferences were unchanged, and no PBW reinstall occurred for the update. The exact release worker caches the binary XHR response once for SDK compatibility. The menu icon/resources remain unchanged; earlier unchanged-JavaScript comparisons apply only to the preceding development packages.

[Publication verification](../artifacts/releases/1.0.0/publication.json) passed for GitHub
(including the downloaded PBW and latest release), Dashboard, the general and
Emery-filtered catalogs, and the canonical public store page/changelog. The
phone's My Apps cache was not observed; the Emery catalog is a proxy for it.

## Version 2 implementation changes awaiting final-candidate measurements

The bundled timetable and downloaded snapshots now share the existing 32 KiB
RAM cache through a resource-reader callback. The reader validates the bundle
on initialization and its complete CRC on reload; a resident baseline does
not reread. This removes the separate 24,203-byte baseline allocation. Short,
failed or altered resource reads invalidate the cache and preserve explicit
recovery behavior. Existing storage tests plus seven new resource suites
cover current/future alternation, interrupted/torn updates, corruption fallback,
read counts and 15-point merged queries. Actual runtime headroom is measured
separately on the final PBW.

Version 2 also loads the 16/24/28 px Japanese subset only while its screen is
open. All-departures selections use two additional 80-byte records at keys 12/13
and two startup reads, with no startup write. Its coordinates are never stored
on the watch: only selected IDs/reference persist, and approximate distances
remain in RAM. Explicitly saved home coordinates stay in private phone storage.

## Earlier development build evidence

The preceding development [PBW](../artifacts/KasugaBus-1.0.0-emery.pbw) is **817,565 bytes**, SHA-256 `2bddb0b092d51c7cdab6944c56a11bb377f4a97932643ee37541450bfc8bdb09`, version **1.0.0**. [Final workflow build acceptance](../artifacts/final-workflow-build.log) records 113 Python tests, including 31 release, 32 registration and two cleanup tests, plus 25 phone scenarios, five settings scenarios, five HTTP scenarios, strict C checks and a clean build/static audit. Sizes remain 30,178 resource bytes, 39,170 static RAM bytes, 31,428 native binary bytes and 91,902 linker-free bytes before runtime allocations. The [sealed emulator receipt](../artifacts/runtime-workflow-acceptance.log.install.json), [monotonic profile](../artifacts/native-profile-workflow-acceptance.json) and [final workflow audit](../artifacts/final-workflow-build-audit.json) bind to this exact PBW; minimum observed free heap is 32,400 bytes.

The user selected **1 — Neon Express**. Its 25×25 transparent PNG with a dark bus glyph remains bundled as `MENU_ICON`. All ten original concepts and the [preview gallery](../artifacts/icon-options/index.html) remain available. [The workflow rebuild comparison](../artifacts/workflow-build-comparison.json) confirms identical application code, phone JavaScript and resources relative to the installed `4679b90e…` package. Only native metadata bytes 124/125, the manifest checksum and ZIP timestamps changed. [The earlier icon comparison](../artifacts/neon-build-comparison.json) records the change from the pre-icon package.

## Safe dataset storage

The immutable resource baseline is 24,203 bytes. The update schema caps a complete snapshot at 32,768 bytes. Eight independent flash slots reserve 262,144 payload bytes plus less than 4 KiB for descriptors/preferences/status, below 26% of the measured 1 MiB capacity. Four roles are required—current, future, previous recovery and incomplete candidate—and additional slots allow overlapping pending revisions and retention of originating service dates for overnight services. A device reporting less than 266,240 bytes refuses downloads explicitly.

Each 192-byte transfer chunk maps to one bounded persistent record. Committed slot metadata now lives in two generation-numbered, checksummed **KBD2 directory banks at keys 90/91, 208 bytes each**. An ordinary initialized startup reads those two records without loading downloaded payloads. A candidate becomes committed only when all chunks and full payload checks pass and the alternate directory bank is written. Before reusing a slot, both banks must stop referencing its old payload; a failed exclusion write leaves that payload unchanged. Restore writes empty banks so stale legacy descriptors cannot reappear.

When both directory keys are absent, one-time migration scans the eight old KBS1 descriptors, writes the new banks, and retires old descriptors after both bank writes succeed. A torn first migration preserves the old records for retry; a read error is not treated as absence. Normal restarts do not scan legacy keys. The selected payload is still validated fully before use, and pending status validates its future payload before describing it as ready. Remaining snapshots are checked lazily, at most one per background event-loop turn; BEGIN validates every remaining candidate before deciding what can be reused. Corrupt newer metadata cannot hide and evict an older valid recovery copy. See the read-count, migration, torn-bank, slot-reuse and read-failure regressions in [test_storage.c](../tests/test_storage.c).

The receiver accepts identical duplicate chunks, requests the expected sequence after reordering, rejects wrong-session/out-of-range/conflicting duplicates, and abandons staging after 30 seconds of inactivity. ACKs identify both session and message phase so an old BEGIN ACK cannot masquerade as a CHUNK0 ACK. The sender retries each step at most 3 times, 2 seconds apart.

A resolver chooses the latest effective service date, then the newest correction at that same effective date. It resolves prior service dates separately for departures beyond 24:00. Publication transfers a newer future companion before its current correction; a current candidate cannot supersede a still-valid overlapping pending version. The resolver never extends an operator/calendar validity interval. An expired source remains unconfirmed even after recovery.

Historical payloads are deferred until needed or checked in the background; this reduces startup work without weakening validation. Every cache reload still checks the complete payload CRC, internal checksum, schema, references and applicability metadata. The home query stops once later service dates cannot beat its selected trip, while the full query retains lookahead diagnostics. A 64-byte read-only CRC table accelerates the same CRC32 calculation without changing the format. Only the baseline and one downloaded snapshot cache occupy RAM; persisted future/recovery/candidate copies do not each allocate another buffer. Committing validates in that cache. Trip references contain stable IDs and a service date, not borrowed pointers into a replaceable cache. The native evidence below distinguishes the rebuilt PBW's fresh checks from earlier unchanged application code's rollover and Restore checks; neither is a physical recovery test.

Slot selection protects the current and two preceding service dates, every distinct future effective date, and a previous current revision. For repeated corrections at one future date, it keeps the two newest validated copies and reuses older superseded copies. A regression test installs 18 successive future corrections, interrupts another, restarts, and corrupts the newest descriptor: current data and the preceding valid future copy remain usable. If all slots are needed for distinct dates, the watch refuses staging and explicitly reports full storage; it does not evict a necessary future timetable.

Control state uses two checksummed, generation-numbered **KBW2 records at keys 10/11, 108 bytes each**. Each contains the 80-byte preferences, automatic-attempt and successful-check timestamps, first-use hint state, and the durable `update_request` counter at byte 100 (CRC at byte 104). Automatic/manual CHECK and Restore persist an incremented request before proceeding, so a download from before Restore cannot be accepted after a restart or clock change. Ordinary startup still reads four metadata records in total, with no additional launch write.

The reader also accepts 104-byte KBW1 records with request zero and 92-byte KBP1 records; KBP1 alone triggers the one-time old timestamp/hint migration. Equal generations prefer KBW2, then KBW1, then KBP1. The validated candidate is written before RAM or success ACK changes; failed/torn writes retain the preceding bank. [test_preferences.c](../tests/test_preferences.c) covers two-read load, retained fields, compatibility, torn writes and corrupt records. Missing boarding IDs stay unavailable instead of being reassigned. Reset preferences and restore baseline are separate explicit watch actions. Restored baseline dates remain visible.

## Deliberate compatibility boundaries

Buttons are the supported input path. Emery touch hardware exists in the SDK but touch interactions were not added without device verification. No background worker, GPS polling, live-arrival feed or departure alarm is used. There are no idle animations; reduced-motion preferences are preserved for compatibility.

Updates use a fixed-host HTTPS feed. Source review and successful feed-check timestamps have separate meanings and storage. Automatic attempts are recorded when a CHECK is queued after the phone handshake, at most once per rolling 24 hours; an offline wait does not consume an attempt. Manual checks bypass this throttle and share the single active request limit.

Nearby uses only verified pole coordinates supplied by the watch's selected snapshot. Coordinates/fixes remain transient. No walking duration is inferred. Reviewed data excludes all 9 unverified Kintetsu coordinates; six Hankyu poles are rankable.

Maintainer decision: inspect official notices weekly, fully review sources monthly, and review sooner on relevant announcements. Review is due 2026-11-01. Operator coverage ends 2026-12-27 until year-end rules are verified. A phone feed check cannot reset that review date.

The preceding `2bddb0b0…` development PBW was successfully installed on the user's **Pebble Time 2, firmware v4.38.4**, as [physical workflow installation](../artifacts/physical-workflow-installation.json) and its [log](../artifacts/physical-workflow-installation.log) record. No new owner navigation or icon QA was claimed for that development digest, and publication approval was pending at that stage. The owner subsequently approved the separately installed published candidate and listing; this does not relabel the earlier physical observations.

The preceding [installed Neon archive](../artifacts/KasugaBus-1.0.0-emery-neon-installed.pbw), digest `4679b90e…`, retains its [physical installation record](../artifacts/physical-neon-installation.json) and the owner's confirmation that the icon is visible and highlighted. The pre-icon `466df8dd…` PBW's [physical verification](../artifacts/physical-verification.json) records readable Home → board → details and correct Select navigation, with a **Poco F4, Android 14 build UKQ1.231207.002, companion 1.14.0.1**, reported 1,048,576-byte persistence capacity and minimum observed free heap of 32,400 bytes. Those owner observations stay bound to their respective packages; the historical comparisons describe the preceding builds, while the published candidate includes the later phone-side XHR correction. Remote launcher captures returned the Quartz watchface, so no physical launcher screenshot is claimed. The owner's phone-version screenshot remains outside the project. Outdoor/three-second-glance readability, actual phone GPS behavior, physical Clay persistence, connection loss, update interruption/recovery, battery impact and seven-day use remain unverified. Emulator timings do not establish physical-watch timings.

GitHub Pages is deployed at `https://ewijaya.github.io/kasugabus-pebble/timetables/manifest.json`, with reviewed production v2 and preserved immutable v1/v2 payloads. HTTPS, exact hashes/lengths, JSON/binary MIME types and CORS were verified; the accepted `max-age=600` cache permits a ten-minute propagation delay. See [hosting evidence](../artifacts/hosting-v2-http.json) and the exact-release native transfer proof above.

The source repository `ewijaya/kasugabus-pebble` is live on `main`, with release tag `v1.0.0` on source `3110dee`. KasugaBus is registered as App ID `f63e6ed24301414a95909564` at [its canonical listing](https://apps.repebble.com/f63e6ed24301414a95909564); this ID is separate from package UUID `d7ba77b0-d528-4cc8-b35c-7052798152c9`. [The earlier no-match discovery](../artifacts/store-discovery-final.json) remains historical setup evidence, superseded by the [publication receipt](../artifacts/releases/1.0.0/publication.json).

## Emulator measurement and tooling

The installed SDK's UTC `time_ms` pairs produced occasional negative or extra-second intervals during emulator clock corrections. Acceptance timing uses `tools/profile_emulator.py`: host monotonic time from an app-start/button command to the real native UI-render log, including transport/firmware overhead. It never installs a PBW or changes dates/preferences. [Historical development timing evidence](../artifacts/native-profile-workflow-acceptance.json) binds to the exact preceding `2bddb0b0…` PBW: three start commands reached Home in 632.55–637.32 ms, initialization reached Home in 598.59–602.80 ms, and twelve button actions reached their render logs in 10.77–83.76 ms. These samples meet the 1,000/200 ms thresholds.

[Development native update acceptance](../artifacts/native-update-workflow-acceptance.log) installed isolated current/future test revisions 28/29 in 254 chunks without reinstalling the preceding `2bddb0b0…` PBW. Restart retained both; a two-chunk interrupted replacement and another restart retained them too. Corrupt payload, incompatible manifest and interrupted HTTP cases sent no chunks and preserved those snapshots. The sealed capture passed launch, navigation and update-transfer audit checks. These local test revisions are not published timetable releases.

The preceding Neon package retains its [24/25 update acceptance](../artifacts/native-update-neon-acceptance.log), [profile](../artifacts/native-profile-neon-acceptance.json) and [sealed receipt](../artifacts/runtime-neon-acceptance.log.install.json) as historical exact-digest evidence.

The pre-icon PBW, SHA-256 `466df8dd233cb2886171eb44fe23f1188fd1b3f68bc1d872249be3262a8dff5b`, retains its 29-scenario native suite as earlier evidence. [Its update acceptance](../artifacts/native-update-acceptance.log) covers current/future revisions 20/21 and interrupted/corrupt/incompatible recovery; [rollover acceptance](../artifacts/native-rollover-acceptance-retry.log) covers offline activation/restart and review/coverage/override scenarios. [Restore acceptance](../artifacts/native-restore-acceptance.log) and [post-reset evidence](../artifacts/native-postreset-acceptance.log) cover cancellation of deferred BEGIN, rejection of obsolete/missing request IDs across restart, acceptance of a new request, and restored bundled v1. The retained comparisons describe the preceding development packages; these additional scenarios were not rerun against the published digest and do not establish its physical recovery behavior.

The controlled updater harness shares the production bounded phone sender. One transport transaction is active at a time; the existing pypkjs relay owns watch-push ACKs. The observation bridge suppresses its duplicate ACKs. Installed-SDK tests cover signed Int32 wire encoding, incoming unsigned words, transaction ownership and reader failure.

The retained [installation-stall diagnosis](../artifacts/emulator-install-stall-diagnosis.md) identifies firmware flash/logging waits while **App <App Fetch>**, not KasugaBus, was running. KasugaBus had not started, and the exact missing signal remains unproven. This historical diagnostic is neither a KasugaBus crash nor a startup measurement of the new directory/control build.

Native screenshots use the installed SDK's QEMU monitor helper at 200×228. They preserve rendered colour and actual backlight dimming, with no synthetic brightness correction or resizing. The preceding development [Home](../artifacts/screenshots/emery_workflow_home.png), [board](../artifacts/screenshots/emery_workflow_board.png) and [details](../artifacts/screenshots/emery_workflow_details.png) captures were visually reviewed and recorded in [capture evidence](../artifacts/screenshots/workflow-capture.json). Earlier Neon [unselected](../artifacts/screenshots/emery_launcher_neon_unselected.png) and [selected cyan](../artifacts/screenshots/emery_launcher_neon_selected.png) launcher captures remain icon evidence for that earlier digest; the resource is unchanged. [Pre-icon navigation evidence](../artifacts/native-navigation-acceptance.log) records preference confirmation/restart, Japanese details and local 12-hour clock with JST bus times.

The release workflow now persists a creation intent and the returned App ID for first registration, supports adoption of a matching existing listing, and resumes subsequent releases. It journals a successful documentation commit before pushing so a failed push can retry the same approved candidate. The preceding development build includes 31 release, 32 registration and two clean-output tests; those tests use isolated fixtures and did not register or publish KasugaBus. The later actual publication has separate release evidence above. Build/runtime evidence was renewed after these tooling and cleanup changes. Earlier [Neon audit](../artifacts/final-neon-build-audit.json) and [pre-icon audit](../artifacts/acceptance-build-audit.json) remain historical evidence.
