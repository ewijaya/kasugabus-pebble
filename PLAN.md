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

## Implementation and publication status — 1 October 2026

The original plan above is preserved as the starting record. The initial release
is now published with the owner's explicit acceptance of the remaining physical
and seven-day checks. Current evidence is in
[the release report](docs/releases/1.0.0-verification.md) and
[full verification history](docs/VERIFICATION.md).

- Installed toolchain verified and retained: Pebble Tool 5.0.40, SDK 4.33.1,
  bundled ARM GCC 14.2.1, Python 3.13.5, Node 26.8.1 and npm 11.19.0.
- Six stop groups, 15 boarding points and 1,411 departures were reconciled with
  official operator sources. Six Hankyu coordinates are verified; nine Kintetsu
  points remain manual. Source review is due 2026-11-01; coverage ends
  2026-12-27 pending verified year-end rules.
- The offline JST engine, Time and Bus screens, favourites, Clay settings,
  one-shot Nearby and validated current/future updater are implemented.
  Native recovery experiments and automated tests cover interrupted transfers,
  corrupt candidates, future activation and transactional storage; evidence
  remains bound to each tested digest.
- The selected Neon Express launcher icon is integrated. All ten concepts,
  native screenshots, data/provenance and publishing tools are retained.
- The source repository is public at `ewijaya/kasugabus-pebble`. The dedicated
  GitHub Pages feed is deployed at
  `https://ewijaya.github.io/kasugabus-pebble/timetables/manifest.json`.
  Production v2 is a reviewed version-only reissue; departure/source dates are
  unchanged, and immutable v1/v2 payloads remain available.
- The published **1.0.0** PBW is **817,922 bytes**, SHA-256
  `233627ffc63e0964bff272c3a56bac11e6f7634992b06cb45143524e2bc5330a`,
  from source `3110deecde6d154a52b1d7971e6e3c5c1bd1a54d` / tag `v1.0.0`.
  Its clean build passed 122 Python tests, 25 phone scenarios, five Clay checks,
  five HTTP checks and strict C suites. Native runtime minimum free heap was
  32,400 bytes. Native release screenshots preserve 200×228 pixels.
- The exact release worker's real HTTPS transfer delivered v2 in 127
  acknowledged chunks and retained active data/success time after restart,
  with unchanged preferences and no PBW reinstall. This is emulator evidence.
  The owner's physical v2 observation belongs to the earlier `2bddb0b0…` PBW.
- The owner approved the installed final candidate and listing. Those frozen
  bytes were published unchanged to
  [GitHub](https://github.com/ewijaya/kasugabus-pebble/releases/tag/v1.0.0)
  and [RePebble](https://apps.repebble.com/f63e6ed24301414a95909564).
  Assigned App ID `f63e6ed24301414a95909564` is saved separately from the
  package UUID. Dashboard, general/Emery catalogs, public listing/changelog
  and both PBW downloads verified. The phone's My Apps cache was not observed.
- Release tooling retains first-registration recovery and now uses the saved
  listing for future releases. A catalog object-shape correction passed 40
  release-workflow tests after publication; it did not rebuild the app.

The owner's environment is Time 2 firmware 4.38.4, Poco F4 Android 14
(UKQ1.231207.002), companion 1.14.0.1. Earlier navigation and icon confirmations
remain tied to their original builds. Broader physical GPS/permission, settings
persistence, connection-loss, future activation/update recovery, outdoor/glance
readability, battery and seven-day use remain outstanding. The accepted initial
publication does not mark the full personal-use milestone complete.
