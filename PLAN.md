# KasugaBus

Interactive personal bus timetable app for Pebble Time 2 (Emery), not a watchface.

Detailed requirements: PRD.md version 0.3, updated 1 October 2026. Timetable updates without reinstalling are approved for the first complete release.

## Product direction (proposed)

Build for personal use first, with timetable data and preferences separated so a neighbourhood release remains possible. Start with the six stops already researched. A public release is a later decision.

The watch should answer: which scheduled bus can I catch next?

## Initial scope

- Offline scheduled departures, clearly distinguished from live arrivals.
- Favourite boarding points, with each operator and direction identified.
- Next departures with route, destination, departure time and countdown.
- Clay settings for favourite order and walking-time preferences.
- Weekday, Saturday, Sunday/public-holiday and special-date handling.
- Source revision dates and a documented maintainer review and publishing procedure.
- Phone-assisted timetable updates without reinstalling: daily-on-launch checks, manual checks, validated transfers, future service-date activation and offline fallback.
- Time and Bus clock-focused home layout with vibrant Neon Transit styling.
- Nearby ranking from phone location and verified boarding-point coordinates, with manual/offline fallback.
- English interface initially; verify Japanese font support before deciding label treatment.

## Stops

1. Kasugaoka Koen / 春日丘公園
2. Toge / 峠
3. Midorigaoka / 緑ヶ丘
4. Handai Higashiguchi / 阪大東口
5. Handai Igakubu Byoin-mae / 阪大医学部病院前
6. Handai Igakubu-mae / 阪大医学部前

Walking distances and nearest-stop ranking are not verified. Do not encode an exact home address in the app or repository.

## Implementation sequence

1. Verify the local toolchain and project conventions. Create a minimal Emery app and establish a successful build/emulator launch. Prove storage budgets for active, future and recovery timetable data before selecting the update format.
2. Create structured timetable data from the saved official sources. Preserve operators, directions, service days, route-number changes and provenance. Validate extracted times against originals; no inferred departures from blank cells.
3. Build the offline departure engine. Test boundaries: exact departure minute, last bus, next day, weekends, holidays, no-service days and walking-time cutoff. Define Japan-time behavior explicitly.
4. Prototype the selected Time and Bus home layout in Neon Transit colours. Show the clock and one next departure; Select opens the departure board. Add Favourites, Nearby, full details and data status according to the PRD.
5. Add Clay settings, persistence, one-shot phone location and Nearby ranking. Retain useful defaults when the phone is disconnected or settings have never been opened.
6. Add the approved timetable updater. Publish validated static data and a release manifest, add daily/manual phone checks and chunked transfer, and verify safe staging, activation, retries and recovery. Hosting selection and the maintainer source-review cadence are implementation decisions still to resolve.
7. Verify in the Emery emulator, inspect screenshots and package the PBW. Test installation and real-world use on the user's watch when connected; physical-device checks remain necessary.
8. Refine from daily use. Consider a public neighbourhood release only after timetable updates and core usability are reliable.

## Completion criteria for the first complete release

- Successful Emery build and usable offline screens.
- All six stops covered, including relevant boarding directions and service calendars.
- Timetable extraction and departure selection checks pass.
- No invented live-arrival information or unverified walking times.
- Settings survive restart and disconnect.
- A validated timetable-only update installs without reinstalling the PBW.
- Interrupted or corrupt updates preserve active data; future schedules activate on their service date without a phone connection.
- Successful update-feed checks do not erase source-staleness notices.
- Installable PBW with source/update documentation.

## Environment

Confirmed 1 October 2026: arm64 Mac; Pebble Tool 5.0.40 reports active SDK 4.33.1. Emery headers are installed.

User-reported baseline: ARM GCC 14.2.1, Python 3.13.5, Node 26.8.1, npm 11.19.0, uv 0.12.9; @rebble/clay 1.1.0 as the sole planned direct npm dependency. Compiler/runtime/package versions still need build-level verification.

CLI: ~/.local/bin/pebble
SDK: ~/Library/Application Support/Pebble SDK/SDKs/4.33.1/

Read-only CLI inspection triggers settings/analytics file writes on exit, which the current chat sandbox blocked. Subsequent build commands may need execution permission for the Desktop project and Pebble SDK state directory. This is not evidence of a broken SDK.

## Existing research

Working source files and PDF builder are currently in:
/Users/e_wijaya_ap/Documents/Codex/2026-10-01/i-l/work/pdfs/

Combined reference PDF:
/Users/e_wijaya_ap/Documents/Codex/2026-10-01/i-l/outputs/minami-kasugaoka-integrated-bus-timetables.pdf

Official source directories:
- https://www.kintetsu-bus.co.jp/route/timetables
- https://www.hankyubus.co.jp/rosen/timetable/

The integrated PDF is a reference, not a validated app dataset. Use the original source PDFs and current stop timetable records when extracting data.

## Implementation status — 1 October 2026

The original plan above is preserved as the starting record. Current status:

- The installed toolchain is verified and unchanged: Pebble Tool 5.0.40, SDK 4.33.1, ARM GCC 14.2.1, Python 3.13.5, Node 26.8.1, npm 11.19.0 and uv 0.12.9. Emulator persistence/AppMessage measurements remain separate from physical evidence; the installed physical app reports 1,048,576-byte persistence capacity.
- Reviewed official sources produced the editable baseline: six stop groups, 15 boarding points and 1,411 departures, with route/operator/direction/calendar provenance. Six Hankyu pole coordinates are verified; nine Kintetsu coordinates are excluded. Source review is due 2026-11-01; covered service dates end 2026-12-27 pending verified year-end rules.
- The offline JST engine, Time and Bus/watch screens, Clay settings, one-shot Nearby and timetable updater are implemented. Storage uses two 208-byte KBD2 directory banks at keys 90/91; control state uses two 108-byte KBW2 banks at keys 10/11. The durable request counter makes automatic/manual CHECK and Restore reject obsolete downloads across restart and clock changes. Ordinary startup metadata still uses four reads and no added launch write. Legacy KBW1/KBP1 compatibility, one-time migration and full payload validation remain in place. Host regression fixtures cover migration, read counts, torn writes, recovery and lazy validation.
- GitHub Pages is selected and configured locally at `https://ewijaya.github.io/kasugabus-pebble/timetables/manifest.json`. A reviewed immutable feed and manual workflow are prepared locally. No feed deployment or live endpoint verification has occurred.
- The user selected 1 — Neon Express. Its 25×25 transparent dark-bus PNG is integrated as MENU_ICON; all ten original concepts and the preview gallery are retained in `artifacts/icon-options/`. Actual Emery launcher captures show the bus in both unselected and selected cyan rows.
- The final 1.0.0 PBW is 817,565 bytes, SHA-256 `2bddb0b092d51c7cdab6944c56a11bb377f4a97932643ee37541450bfc8bdb09`. `artifacts/final-workflow-build.log` records 113 Python tests, including 31 release, 32 registration and two cleanup tests, plus 25 phone scenarios, five settings scenarios, five HTTP scenarios, strict C checks and a clean build/static audit. Its sealed emulator receipt and `artifacts/final-workflow-build-audit.json` pass launch, navigation and update-transfer checks, with minimum free heap 32,400 bytes. The monotonic profile records initialization within 602.80 ms, start commands within 637.32 ms and twelve buttons within 83.76 ms. Fresh native updates installed current/future test revisions 28/29 in 254 chunks without a PBW reinstall, retained them across restart and a two-chunk interrupted replacement, and rejected corrupt/incompatible/interrupted-HTTP candidates without sending chunks. Fresh 200×228 Home, board and details screenshots were visually reviewed.
- The pre-icon `466df8dd…` PBW retains its 29-scenario native suite, including offline future activation/restart, expiry/override, preferences and Restore rejecting obsolete request IDs across restart. The `4679b90e…` Neon package retains its own 24/25 update/profile evidence. These are historical exact-digest checks, not additional runs on the rebuilt package. `artifacts/workflow-build-comparison.json` verifies identical application code, phone JavaScript and resources relative to the installed Neon archive; only native metadata bytes 124/125, the manifest checksum and ZIP timestamps changed.
- The final rebuilt PBW was successfully installed on the user's Pebble Time 2 firmware 4.38.4, recorded in `artifacts/physical-workflow-installation.json` and its log. No new owner navigation/icon QA or publication approval is claimed. The owner's visible/highlighted icon confirmation belongs to the preceding `4679b90e…` package, preserved as `artifacts/KasugaBus-1.0.0-emery-neon-installed.pbw` with `artifacts/physical-neon-installation.json`. Remote captures returned the Quartz watchface, so no physical launcher screenshot is claimed. The pre-icon PBW's `artifacts/physical-verification.json` records Poco F4 Android 14 build UKQ1.231207.002 / companion 1.14.0.1 and readable Home → board → details with correct Select navigation. Actual GPS, physical settings/recovery, connection loss, outdoor/glance readability, battery impact and seven-day use remain unverified.
- The release workflow now implements durable first-registration intent/App ID, matching existing-listing adoption, resumable releases and clean-output recovery. The 31 release, 32 registration and two cleanup tests use isolated fixtures; no real KasugaBus registration or publication was performed.
- The diagnosed historical installation stall was in App Fetch before KasugaBus started, not a KasugaBus crash. Current acceptance is documented separately from that older emulator diagnostic.
- Pages/GitHub remain unpublished; the local project has no initialized Git repository, the intended remote cannot be viewed with current authentication, and authenticated `artifacts/store-discovery-final.json` still found no KasugaBus listing. No version bump, commit, registration or publication occurred.

Current evidence and remaining checks are documented in `docs/PLATFORM.md`, `docs/MILESTONES.md`, `docs/DATA_RECONCILIATION.md`, `docs/PUBLISHING.md`, and the physical verification records. The rebuilt package has fresh local acceptance and successful physical installation; owner navigation/icon observations remain bound to earlier packages with unchanged application code. Remaining field checks and production deployment/publication are separate open steps.

## Authorized initial release — 1 October 2026

The owner subsequently requested “publish this new app everywhere” and accepted
an initial release with named physical/seven-day limitations. The historical
setup status above is superseded for source and hosting: `main` is committed
and public at `ewijaya/kasugabus-pebble`; the dedicated GitHub Pages feed is
live. V2 is a reviewed version-only reissue with unchanged departures, dates
and source evidence, and retained v1 recovery bytes. Exact live HTTPS checks
passed; the owner confirmed active v2 and a feed-success time after a manual
check on the Poco F4 / Time 2 without app reinstallation.

The actual SDK worker exposed a repeated-XHR-response getter compatibility
issue that Node mocks did not catch. The adapter now retains one response
object; actual installed-SDK regressions verify exact arbitrary binary bytes
and preserved validation. The final 1.0.0 candidate is being clean-built from
committed source. Its physical approval remains the final gate before creating
the initial store listing and publishing the exact same PBW on both stores.
No release tag, GitHub Release or RePebble listing has been created at this
preparation stage. Broader physical GPS/settings/recovery, outdoor/battery and
seven-day use remain explicitly outstanding.
