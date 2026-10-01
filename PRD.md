# KasugaBus Product Requirements Document

Status: Draft for review  
Version: 0.3  
Date: 1 October 2026  
Project: kasugabus-pebble  
Target: Pebble Time 2, Emery

## 1 Product summary

KasugaBus is a personal bus timetable app for checking the next useful departure around Minami-kasugaoka, Ibaraki. It combines a prominent clock, readable scheduled departures, and optional phone-assisted nearby-stop ranking. Its visual identity is colourful, vibrant and futuristic, using the proposed Neon Transit style.

The first version covers six previously researched stop names. These are the initial coverage set, not a verified ranking of the six closest stops to the user's home. The app must distinguish operators and boarding directions within those stops. It must remain useful when the phone is disconnected: timetables and departure selection run on the watch, while a connected phone supplies location, settings and validated timetable updates when available.

This document proposes a personal-first release with configurable favourites and separate timetable data. It preserves the option of a future neighbourhood release without making public onboarding or nationwide coverage part of the first build.

The intended outcome is simple: the user glances at KasugaBus, sees the current time and the next relevant scheduled bus, and can identify where to board without interpreting a large timetable.

## 2 Decisions and assumptions

| Topic | Status | Requirement or proposed decision |
| --- | --- | --- |
| Product identity | Confirmed | App name KasugaBus; local project folder kasugabus-pebble on Desktop. |
| Hardware | Confirmed | Pebble Time 2, targeting Emery. Other platforms are outside the first release. |
| Visual direction | Confirmed preference | Colourful, vibrant and futuristic. Neon Transit is the proposed implementation of that preference. |
| Main layout | Selected concept | Time and Bus: clock first, with useful departure information underneath. |
| Location | Requested capability | Use the connected phone's location to rank the covered boarding points. |
| Product type | Confirmed | An interactive watch app with a clock-focused home screen. It is not a watchface. |
| Audience | Proposed baseline | Personal use first; configurable structure for possible neighbourhood sharing. Public launch is undecided. |
| Data | Confirmed update direction | Bundled scheduled timetables plus phone-assisted data updates without reinstalling the app. No claim of live bus positions, delays or arrival predictions. |
| Timetable updates | Confirmed scope | Include automatic checks on app launch, at most once per day, and a manual check in the first complete release. Operator changes are reviewed before a dataset is published. |
| Configuration | Existing project direction | Clay for phone-side settings; proposed sole direct npm dependency is @rebble/clay 1.1.0. |
| Phone platform | Open | User's actual phone OS and companion-app version must be recorded during the platform spike. |
| Language | Proposed baseline | English navigation and verified abbreviated stop names; Japanese labels where glyph and layout checks pass. |

“Must” below defines the proposed first-release acceptance criteria. Numerical thresholds are engineering targets for this draft, not measured performance or additional user-approved decisions. Changes to those targets should be recorded before implementation depends on them.

## 3 Goals and success measures

### Goals

- Make the next scheduled bus understandable in one glance.
- Preserve predictable access to the user's usual stop and direction.
- Offer nearby boarding options when away from the usual starting point.
- Work without a network or phone connection for timetable browsing.
- Make schedule type, destination and location uncertainty visible when they affect a decision.
- Deliver validated timetable changes without reinstalling the app, with a repeatable and auditable publishing process.

### Acceptance targets

| Measure | Target and method |
| --- | --- |
| Glance comprehension | User identifies selected stop, destination and departure within 3 seconds during device testing. |
| Offline launch | Useful home screen within 1 second of app initialization in the emulator; measure on the watch separately. No location request blocks rendering. |
| Interaction | Ordinary button actions respond within 200 ms in emulator profiling, with no blocking phone wait. |
| Access to alternatives | Departure board and stop selection reachable within two button presses from home. |
| Schedule correctness | Every published departure in the supported boarding-point dataset reconciles with its source; all calendar and boundary test fixtures pass. |
| Location fallback | Permission denial, timeout or disconnect leaves manual timetable access intact and explains why Nearby is unavailable. |
| Update integrity | A complete validated dataset becomes usable without reinstalling; interrupted, incompatible or corrupt transfers cannot replace the active dataset. |
| Personal usefulness | Seven days of actual use, including a weekend, with no known wrong boarding direction, wrong service-day selection or disappearing settings. |

## 4 Scope

### First personal release

The release includes the Time and Bus home screen, a departure board, departure details, Nearby and Favourites stop selection, Clay settings, offline calendar-aware schedule lookup, operator/direction labels, source metadata and a reproducible Emery build.

It includes optional leave-by information using walking times explicitly configured by the user. The first complete release must check for and receive validated timetable data through the phone without rebuilding or reinstalling the app. A bundled timetable provides the initial offline baseline. The developer remains responsible for reviewing source changes and publishing validated data. App code or incompatible data-schema changes may still require a new PBW.

### Deferred

A dedicated watchface is outside the product scope. All-Japan stop discovery, walking-route navigation, transfers, fare calculation, live delay predictions, automated interpretation and publication of operator changes, continuous background location, accounts, analytics, public publishing and additional Pebble platforms are deferred.

Departure alerts and background wakeups are also deferred. The first release shows leave-by information while the app is open; it must not imply that an alarm has been scheduled.

## 5 Initial bus coverage

| Stop name | Japanese label | Services to validate for inclusion |
| --- | --- | --- |
| Kasugaoka Koen | 春日丘公園 | Kintetsu 1 and 2, including loop direction and terminal. |
| Toge | 峠 | Kintetsu 1 and 2. |
| Midorigaoka | 緑ヶ丘 | Kintetsu 1 and 2. |
| Handai Higashiguchi | 阪大東口 | Kintetsu university services identified as 22, 24 and 25/22; Hankyu 72, 164 and 171. |
| Handai Igakubu Byoin-mae | 阪大医学部病院前 | Kintetsu university services identified as 22, 24 and 25/22; Hankyu 72, 164 and 171. |
| Handai Igakubu-mae | 阪大医学部前 | Kintetsu university services identified as 22, 24 and 25/22; Hankyu 72, 164 and 171. |

This is a discovery inventory. It does not assert that every listed route serves every direction or day. Validate the route number displayed when boarding, destination, calling sequence and applicable calendar for each trip. In particular, do not flatten 25/22 into a single universal boarding label. Do not add route 12 merely because it appears in the same whole-route PDF.

The source material previously retrieved has Kintetsu weekday and weekend variants, with separate Saturday and Sunday/holiday university-route sheets. Hankyu's current relevant stop pages show weekday schedules. These distinctions must be rechecked when creating each dataset release. The [Kintetsu timetable directory](https://www.kintetsu-bus.co.jp/route/timetables) and [Hankyu timetable directory](https://www.hankyubus.co.jp/rosen/timetable/) are the starting points, not proof that an old downloaded file is still current.

A boarding point is one identifiable place to board for an operator and direction. A named stop may contain several boarding points. If two operators share a pole, retain separate service identities while allowing one shared physical coordinate.

## 6 Core journeys

### Check the usual bus at home

The user opens KasugaBus. The current time and saved favourite boarding point appear immediately, followed by its next departure and destination. Select opens the departure board. Configured walking time and a buffer can provide a leave-by time in details, when the user has explicitly selected the saved-origin context.

### Find a nearby option while out

The user opens the stop picker and chooses Nearby. With permission, the app requests one location fix from the phone. It ranks only verified boarding points in the bundled coverage area. The user chooses a stop and direction, then returns to the same clock-and-bus layout. Selecting a nearby stop does not alter the favourite order or permanent default.

### Check a later bus

The user opens the departure board, scrolls past the next three departures and chooses one. Details show its destination, route as boarded, scheduled departure and service day. Tomorrow's services are clearly separated from today's.

### Use the app without the phone

The user can browse favourites, select any supported boarding point and view timetables. Nearby reports that a fresh location is unavailable; it does not present an old position as current. Saved watch settings and timetable lookup remain available.

### Receive a revised timetable

On an eligible app launch, the phone checks for a published dataset while the watch immediately displays its stored timetable. A current compatible update is downloaded, verified and transferred. A future timetable is staged and used from its effective Japan service date, even if the phone is disconnected then. The user can manually check through Data Status. A failed update leaves the active timetable and preferences intact.

## 7 Screens and navigation

### Home screen

Use the selected Time and Bus hierarchy. The top region contains a short date and a large current clock. The next region identifies the selected stop and destination direction. The departure region contains the boarding route number, scheduled departure time and time remaining. A compact footer communicates the active service calendar or an actionable exception.

The clock should occupy roughly the upper third of the screen, subject to prototype testing. The default home view shows one departure. Following departures belong on the board so long names and important error states remain readable.

The home screen must answer four questions without scrolling: what time is it, which stop/direction is selected, where does the bus go, and when does it depart? Nearby mode adds approximate distance or fix age only if it fits without displacing those answers. Full operator names, complete Japanese names and provenance are available in details.

The clock follows the device's display preference. Bus departure times always refer to Japan local time. When device time is outside Japan, explicitly label both the clock context and bus times; never calculate departures by treating a non-Japan local clock as JST.

### Departure board

Show the next three departures by default, with scrolling for the rest of the selected service date. Every row contains scheduled time, boarding route, destination and countdown. An optional direct-destination filter only includes trips with a verified downstream call at that destination; no transfer planning is implied.

Preserve selection when a countdown changes. Reconcile expired departures without unexpectedly moving the focused item to another trip. Add a clear next-day divider after the last service today.

### Departure details

Show the full stop and boarding-direction labels, operator, route as boarded, downstream destination, departure date/time, schedule type and “Scheduled” status. Where known, include concise physical boarding guidance verified against the official map. Do not infer the roadside from GPS.

In the saved-origin context, show configured walk duration, buffer and leave-by time. In “At stop” context, omit the walk allowance. In general Nearby context, do not reuse a home walking time.

### Stop picker

Provide Favourites and Nearby modes, plus access to All Stops for the six named stop groups. Favourites retain a user-set order. Nearby presents approximate distance and a short direction label, with an explicit refresh action. All Stops can be used without location permission.

Default to Kasugaoka Koen toward Ibaraki after that boarding point is validated. If no usable default exists, open the picker rather than silently choosing a different stop. Save a user-selected default separately from the temporary current stop.

### Settings and data status

Provide lightweight watch controls for service-day override, trip context, location refresh and data status. Use Clay for favourite management and detailed preferences. Data status includes Check Timetable Updates and shows the active dataset version, source verification date, last successful update-feed check, calendar coverage, pending effective date and any unresolved schedule condition. A feed check does not prove that the operator has made no changes; keep that timestamp separate from source verification. The home footer shows only actionable notices, such as a known expired schedule or failed activation; ordinary checking does not displace departure information.

### Proposed button map

| Screen | Up and Down | Select | Back |
| --- | --- | --- | --- |
| Home | Cycle saved favourites | Open departure board | Exit app |
| Home long Select | Not applicable | Open menu for Stops, Context and Data status | Not applicable |
| Lists and board | Move selection or scroll | Open selected item | Return one level |
| Departure details | Scroll content | Open relevant local action if present | Return to board |

Show a brief first-use hint for the long-press menu; provide Stops as an ordinary selectable row on the board so the gesture is never essential. Button access is mandatory. Touch may be added as an equivalent after SDK and device verification, without changing the basic navigation contract.

## 8 Visual design

Neon Transit combines an opaque black base with cyan navigation, lime departure emphasis, amber walking-time urgency and limited magenta accents. Proposed palette references are black #000000, white #FFFFFF, cyan #00FFFF, lime #AAFF00, amber #FFAA00 and magenta #FF00FF. These are design starting points, not a claim about exact appearance on the watch; map them to supported GColor values and check outdoors on hardware.

Use bright text and sharply bounded blocks rather than gradients, simulated glow or continuous decorative animation. The clock uses the largest numerals; route badges remain strong but secondary. Display units beside countdowns and pair status colours with words. “Leave now” means the configured allowance has been reached, not that catching the bus is guaranteed.

Requirements:

- Design and review at Emery's native 200 by 228 pixel dimensions, confirmed in the installed SDK platform definition.
- Use actual available fonts and glyph subsets; browser concept typography is not a hardware specification.
- Reserve space for the longest supported stop label. Use an approved short label on home and full text in details; do not truncate the boarding direction into ambiguity.
- Ensure route, destination and time remain distinguishable in a monochrome screenshot.
- Provide a high-contrast reduced-accent option and a reduced-motion setting.
- Animate only user-initiated transitions; target at most 200 ms, with no idle animation or flashing.
- Japanese glyph support must be checked explicitly. If bilingual content cannot fit within resource and readability budgets, ship English short labels with Japanese names in a separate details view once supported.

## 9 Timetable and calendar behaviour

### Selection rules

The watch calculates upcoming departures from the applicable validated local dataset, using the bundled baseline until an update is installed. Phone availability must not affect the selected trip or schedule day.

Represent scheduled departures at minute precision. Normalize a timetable time to the start of that minute for ordering. While the current time is within its stated departure minute, display “Due” rather than implying second-level precision. Remove it when that minute ends. With no verified live feed, never label a departure late, cancelled, approaching or already departed based on anything other than the schedule.

A numeric countdown is the ceiling of positive seconds to the scheduled departure divided by 60. Recalculate on app resume, minute change, clock change and settings changes. The next departure is chronological; any walking feasibility indicator is a separate annotation, not a reason to silently remove earlier services.

Leave-by equals scheduled departure minus configured walking duration minus buffer. This calculation applies only to the explicit saved-origin context. Do not infer walking duration from straight-line distance. The user can switch to At Stop to use a zero walking allowance without changing the saved preference.

### Service calendars

Calendar precedence is exact-date operator exception, applicable public-holiday service, then normal weekday/Saturday/Sunday pattern. Support substitute holidays and other dates designated by the official Japanese holiday calendar. Operator-specific New Year or other special schedules must be represented as exceptions when verified.

Maintain explicit coverage dates for the holiday/exception dataset. Unknown coverage is not “no service.” If the app cannot determine the correct service calendar, show “Schedule unconfirmed” and allow an explicit temporary day-type choice with a visible override label.

Overrides expire on the next Japan service-date rollover. Schedule browsing for another date must not change the real current date. After the last bus, show the next verified service day and date within a proposed seven-day lookahead. If calendar coverage ends first, show that limitation. Distinguish “No service today” from missing or invalid data.

The parser must support timetable times beyond 24:00 if present in future source files, retaining their originating service date. Do not require a current source to contain such trips.

## 10 Nearby stop ranking

PebbleKit JS can request the connected phone's position and communicate with the watch. It requires the location capability and appropriate companion-app permission; it is not an autonomous watch GPS feature. Phone-specific permission and background behaviour must be tested on the user's device. [PebbleKit JS communication and geolocation documentation](https://developer.rebble.io/guides/communication/using-pebblekit-js/)

Use a single location request when entering Nearby and whenever the user explicitly refreshes. Default automatic lookup on app launch to off. Do not run continuous location tracking or silently request location after the user disables it.

For the first version, the phone calculates great-circle distances between the fix and the verified boarding coordinates from the dataset in use on the watch, then sends compact results keyed by boarding-point ID. The watch labels distances “Approx.”; these are straight-line metres, not walking distance, route guidance or travel time.

Proposed initial quality rules:

| Condition | Behaviour |
| --- | --- |
| Fix age at most 2 minutes and accuracy radius at most 100 m | Show approximate distances and distance ordering. |
| Older fix | Label as previous location with its age; request a fresh fix before claiming current nearest. |
| Accuracy radius greater than 100 m | Show low accuracy, avoid declaring a definitive nearest stop and keep manual selection available. |
| No permission, no connection or a 15 second request timeout | Show the cause and fallback options; do not block the app. |
| Nearest covered point farther than 2 km | Show “Outside saved area”; do not imply the app has searched all local stops. |
| No verified coordinate for a boarding point | Keep it available manually, but exclude it from automatic ranking. |

Distance ties within the reported uncertainty should retain stable previous/favourite order and indicate similar distance. Opposite sides of a road remain explicit user choices. Preserve focused boarding-point ID while applying results; do not move the selection to a different row because a new fix arrives.

Send fix timestamp, accuracy, dataset version and request ID with the result. Reject old requests and results containing unknown boarding IDs or mismatched datasets. Coordinates remain transient on the phone; persist only the minimum preference data, not a location history. Stale distances may remain visible within the current session with an age label, but must not survive as an unqualified current location on restart.

## 11 Settings and persistence

| Setting | Proposed default | Behaviour |
| --- | --- | --- |
| Default boarding point | Validated Kasugaoka Koen station-bound point | User can select another. |
| Favourites | Initial stop/direction selections after validation | Reorder, add or remove from the covered set. |
| Startup mode | Default favourite | Nearby startup is optional and requires location enabled. |
| Location | Off until enabled or Nearby explicitly requested | OS permission remains controlled by the phone. |
| Walk duration | Unset | No leave-by claim until explicitly configured for an origin and boarding point. |
| Boarding buffer | 2 minutes, proposed | Configurable independently of walk duration. |
| Current trip context | General / no walk assumption | Saved origin and At Stop are explicit alternatives. |
| Clock format | Follow watch preference | Departure formatting can remain 24-hour for timetable clarity. |
| Language | English | Optional bilingual labels after resource validation. |
| Visuals | Neon Transit, brief transitions | High-contrast and reduced-motion alternatives. |
| Timetable update checks | Enabled | Check on eligible app launches no more than once per rolling 24 hours. User may disable automatic checks; manual Check Timetable Updates remains available. |

Validate settings before applying them. Missing keys, unsupported values, cancelled Clay sessions or interrupted messages must preserve the last valid configuration. Save preferences with a versioned schema; upgrades and restarts must preserve favourites and walk settings. Reset settings must leave timetable data intact. Restoring the bundled timetable is a separate explicit recovery action, with its revision and validity shown. Clamp or reject negative and unreasonable durations rather than silently using them.

## 12 Data model and source validation

Use editable structured source data to generate both a bundled baseline and a compact transferable dataset. They must use the same validated schema and schedule semantics. The PDF is a human reference, not the canonical app database.

| Entity | Required information |
| --- | --- |
| Stop group | Stable ID, English/Japanese names, approved short labels. |
| Boarding point | Stable ID, stop group, operator, direction, verified coordinate if available, coordinate source and verification status. |
| Trip pattern | Operator, displayed route, destination, ordered downstream calls and any route-number transition. |
| Departure | Boarding-point ID, pattern ID, service ID and scheduled service-day minute. |
| Service calendar | Weekly pattern, exact-date exceptions, holiday mapping and coverage dates. |
| Source record | URL, retrieval date, printed revision, effective date if stated, source checksum and page/row or equivalent locator. |
| Dataset manifest | Schema version, monotonic release version, minimum app version, coverage ID, supported service dates, effective-from date, published/source-verified/review-due dates, immutable payload URL, byte length, checksum, generated counts and validation result. |
| User preferences | Favourite IDs, default ID, display options and explicitly scoped walking allowances. |

Every released departure must have traceable source evidence. Extraction must retain blank cells, continuation pages, directions and notes until interpreted; it must not invent a time from an empty cell or interpolate a trip without source support. Reconcile counts and every emitted time by boarding point, direction and service day. Where extraction is uncertain, review the source visually before accepting that row.

Coordinate validation requires a source for the actual boarding pole or a documented shared-pole location. A stop-name centroid is insufficient for a confident boarding-direction claim. The initial research did not establish exact coordinates or walking times; these remain implementation work.

Publishing procedure: check official directories and notices; obtain source files; compare revisions and checksums; extract candidate data; produce a departure/calendar diff; reconcile all changes; run tests; increment the release version; publish an immutable data payload; then update the release manifest. Timetable-only releases do not rebuild the PBW. Keep previously validated releases available for recovery and publish any intentional correction or rollback under a newer release version. Record a review-due date in the manifest. After that date, show an unobtrusive stale-data notice while retaining the last validated schedules; a known expired timetable or unsupported calendar date must instead be marked unconfirmed. A successful build or data publication alone does not establish that timetable data is current.

### Update delivery and activation

The updater retrieves only developer-published, validated KasugaBus data. It does not scrape or interpret bus company PDFs at runtime. Automatic detection of operator revisions and automatic publication are outside this release. The maintainer must document a regular source-review routine and how announced revisions are handled; app-side daily checking cannot eliminate delays in that review process.

1. Render the current offline timetable immediately on launch.
2. After phone communication becomes ready, make a background feed check if automatic updates are enabled and no automatic attempt has occurred within the previous 24 hours. Persist the attempt time to avoid repeated requests on rapid relaunches. Waiting for a disconnected phone does not count as an attempt; run the eligible check once communication becomes ready. Use bounded network timeouts and retries within the attempt. A failed attempt retains an error status and allows manual retry; it must not be labelled a successful check. No OS background job is required while KasugaBus is closed.
3. Manual Check Timetable Updates bypasses the daily throttle. Permit only one request/transfer at a time; a running request is shown instead of starting duplicates. Record attempts separately from successful checks.
4. Fetch a versioned manifest from the fixed project-controlled HTTPS endpoint. Reject incompatible schemas, coverage IDs, app-version requirements, malformed dates, invalid URLs and payloads beyond measured storage/transfer limits before starting the watch transfer. Never install executable code through a timetable update.
5. Download the complete payload to the phone and verify length, checksum, stop/trip references, calendars and departure values. Use the fixed approved host for the manifest and payloads; do not follow arbitrary untrusted payload locations. HTTPS establishes the transport trust; the checksum detects corruption, not publisher identity by itself.
6. Transfer into watch staging storage in acknowledged chunks. Identify the session, release version, sequence, total length and checksum; tolerate duplicate chunks and reject wrong-session or out-of-range chunks. Apply bounded retries and a documented inactivity timeout, then abandon the attempt without touching active data.
7. Validate the complete staged payload on the watch. Commit it with recoverable metadata so a crash or restart leaves either the complete old dataset or complete new dataset, never a mixture. Update preferences only through a separately validated ID migration after commit.
8. Select the correct validated timetable by Japan service date and dataset effective dates. Future data must not be used early, and must become available at the effective date without a phone connection. Cross-midnight trips retain their originating service date. Date browsing uses the same version-selection rule.
9. Recalculate departures and preserve focused boarding-point/trip identity where possible. Apply visible list changes at the next minute tick, screen entry or completed button action, without reassigning a focused row to another trip; indicate that the timetable changed. Retain favourite order and walking preferences. Report removed IDs or trips rather than silently substituting unrelated stops. Invalidate Nearby results tied to a superseded coordinate dataset and allow an explicit refresh.

Persist active and staged version metadata across restarts. Measure the total storage required for active data, future staged data, previous-data recovery and a partially received candidate during the foundation spike. Do not evict the only valid current or scheduled future dataset to make room for an unvalidated update. If capacity is insufficient, reject that candidate, explain the limitation, and require an engineering resolution before the first complete release. The exact storage arrangement is an implementation decision; safe replacement and offline future-date activation are release requirements.

When a newer candidate arrives while a future update is staged, retain the staged dataset until its replacement passes all checks. When an upcoming timetable is published, the release manifest must identify both the current and upcoming timetable so a fresh install can obtain the present schedule without jumping ahead. Version ordering and service-date applicability are separate checks. Ignore stale manifests and repeated identical payloads. Incompatible data requires an app update; it must not overwrite compatible stored data.

Each payload is a complete coverage snapshot, with operator-specific service validity and calendar exceptions. If operators change on different dates, preserve each operator's applicable schedules through the transition. Resolve overlapping revisions for the same operator and service date using the newest compatible published correction; reject contradictory records within one release. A gap remains Schedule unconfirmed. Retain the preceding service date's data while any verified departures beyond 24:00 still depend on it.

### Update states and recovery

| State | User-visible result |
| --- | --- |
| Checking or downloading | Non-blocking progress in Data Status; current timetable remains usable. |
| Feed checked and no applicable update | No new published timetable; show successful feed-check time without changing source verification date. |
| Current update installed | Show the new data version and effective date; departure lists recalculate. |
| Future timetable ready | Show activation date; keep current service dates on the current timetable. |
| Phone or internet unavailable | Check unavailable or failed; stored timetable remains accessible. |
| Interrupted transfer, corrupt payload or insufficient space | Update not installed; retain active data and any still-valid pending data. Offer manual retry. |
| App version too old | Explain that an app update is required; preserve the last compatible timetable. |
| Stored dataset is past review date | Show Needs timetable review; retain validated data with the limitation visible. |
| Known expiry or uncovered service date | Show Schedule unconfirmed; never relabel obsolete data as current. |

Recovery must never silently make an expired old timetable appear valid. Retain previous validated data where the measured storage strategy supports it, and keep the bundled baseline available as a clearly dated fallback. If neither applies to the requested service date, expose the unconfirmed state and manual day-type choice rather than asserting correctness.

## 13 Technical approach

Use a native C watch app, PebbleKit JS for phone communication/location/update downloads, and Clay for settings. Package the initial validated dataset with the PBW and support validated data overlays in persistent watch storage. Timetable updates require a project-controlled HTTPS location serving static manifest and data files; no custom application server, accounts or routing API is required. Select and configure hosting before the updater milestone. Never embed a private hosting credential in the watch app or phone-side JavaScript.

Keep schedule selection independent of rendering and device APIs so it can be exercised by deterministic fixtures. Keep phone-side work asynchronous, and wait for communication readiness before sending requests. Use request IDs, bounded retries and explicit error states. Consult installed SDK message-size and persistence limits rather than assuming a complete dataset fits in one message or one storage record.

The installed SDK 4.33.1 platform definition reports Emery colour/rectangular support, 200 by 228 pixels, a 128 KiB app binary limit, a 128 KiB app memory limit, and a separate 256 KiB Appstore resource budget. These are ceilings, not available heap measurements. Measure the compiled app, font resources and peak runtime allocation before choosing the final representation. A proposed engineering target is at least 20 percent measured headroom against each applicable ceiling; report exceptions rather than claiming free heap from binary size.

Suggested project responsibilities are watch UI, schedule engine, phone settings/location/updater, versioned persistent dataset storage, editable data, conversion/validation/publishing scripts and tests. Avoid hand-editing generated watch tables. Pin build dependencies and record compiler/SDK versions in the build instructions.

### Development baseline

Confirmed locally: Apple Silicon arm64; Pebble Tool 5.0.40 reporting active SDK 4.33.1; installed Emery platform definition and headers.

User-reported and still requiring build-level verification: ARM GCC 14.2.1, Python 3.13.5, Node 26.8.1, npm 11.19.0, uv 0.12.9 and @rebble/clay 1.1.0. The first build must verify these rather than reinstalling dependencies by default.

The CLI is at ~/.local/bin/pebble and the SDK at ~/Library/Application Support/Pebble SDK/SDKs/4.33.1/. CLI inspection in this chat encountered sandbox restrictions when Pebble tried to save its settings and analytics queue. That is an execution-permission issue, not proof of a broken SDK. Build and emulator commands need the appropriate local access.

## 14 Reliability and privacy

Render useful local content first. Expensive work must not block button handling or the first paint. Update the clock/countdowns on minute boundaries; do not poll GPS or redraw animation continuously. No battery-life percentage claim is a release requirement until measured on a real watch.

A timetable remains readable offline. Location, settings and update failures must be local failures, not app failures. Update traffic must not carry coordinates, favourite IDs, walking preferences or an exact home address; it only needs the public release feed and payload. If a bundled dataset fails integrity validation, show “Timetable unavailable” and keep diagnostics accessible rather than displaying fabricated defaults.

Store no exact home address or apartment number in app assets, source control or screenshots. The user can define a named walking-time context without storing an origin coordinate. Do not upload location to an application server, add behavioural analytics or log precise coordinates in production. Developer logs must be adequate for troubleshooting request outcomes and versions without retaining a travel history.

## 15 Verification and acceptance cases

| Case | Expected result |
| --- | --- |
| First launch with phone disconnected | Home or default-stop picker works from bundled data. |
| 10:32:01 before a 10:33 departure | Countdown says 1 min. |
| 10:33:00 through 10:33:59 for that trip | Due, explicitly scheduled; no live bus-status claim. |
| 10:34:00 | That departure is removed from upcoming selection. |
| Five-minute saved walk and two-minute buffer for 10:33 | Leave-by 10:26 only in that saved-origin context. |
| Same stop selected through general Nearby | No home walk duration applied automatically. |
| Saturday, Sunday, substitute holiday and operator exception | Fixture selects the correct service, with exact-date exceptions taking priority. |
| Last bus and an overnight service time beyond 24:00 | Correct service-date treatment; tomorrow is explicitly labelled. |
| Date outside supported calendar coverage | Schedule unconfirmed; override is visible and expires correctly. |
| Hankyu no-service day | No weekday departures inserted as fallback. |
| Route-number change and loop trip | Boarded route and actual downstream destination remain correct. |
| Identical route numbers from different operators | Operator identity remains visible and trips are not merged incorrectly. |
| Weekend when only one operator runs | No-service status for one operator does not hide the other operator's departures. |
| GPS error, denied permission, stale/poor fix, or out of area | Appropriate state and manual fallback; no false nearest claim. |
| Two nearby poles with uncertain ordering | Stable list and explicit direction choice. |
| Phone result arrives after user changes stop | Selection is preserved; stale request cannot replace it. |
| Cancelled or interrupted settings transfer | Previous valid settings remain in use. |
| Restart and dataset upgrade | Favourite IDs migrate or missing IDs are reported; no silent arbitrary substitution. |
| Long English/Japanese labels and monochrome screenshot | Essential information fits and remains understandable. |
| Device timezone change | JST bus calculations remain correct and clock context is clear. |
| Relaunch several times within 24 hours | At most one automatic feed attempt; manual checking remains available. |
| Phone reconnects after offline launch | Deferred eligible check runs once after readiness without blocking current screens. |
| New compatible timetable for the current date | Data changes without PBW reinstall and source metadata is preserved. |
| Operators revise schedules on different dates, with an overnight trip across a revision | Each operator uses the correct service-date schedule; the prior overnight trip remains valid. |
| Future timetable followed by restart and offline effective-date rollover | Current services stay correct until the effective service date; staged data is used then. |
| Power loss or disconnect during transfer or commit | Reopen with a complete valid dataset; never a partially applied timetable. |
| Missing, duplicate, reordered or wrong-session chunks | Acknowledgement/retry or clean rejection; no data corruption. |
| Bad checksum, oversized payload, invalid time or unknown stop reference | Candidate rejected; active and valid pending data remain intact. |
| Unsupported schema or minimum app version | Clear app-update-required state; no destructive replacement. |
| Stale manifest or repeated release | No downgrade or unnecessary rewrite. |
| New candidate while another future dataset is staged | Preserve pending data until candidate validation and date applicability checks succeed. |
| Dataset changes or removes a favourite boarding point | Safe preference migration or explicit unavailable item; no silent reassignment. |
| Successful feed check but source review date has passed | Needs-review notice remains; feed availability does not imply fresh operator data. |
| Automatic checks disabled | No launch-triggered network check; manual check works and timetables remain offline. |

Automated checks cover data reconciliation, schedule/calendar selection, countdown boundaries, preference migration, invalid messages, distance fixtures, version/effective-date selection, update throttling and corruption/restart recovery. Update integration tests exercise a controlled feed with current, future, incompatible and invalid releases before using the production endpoint. Emulator verification covers navigation, native-resolution screenshots, fonts, offline operation and repeated open/close cycles. Physical-device testing covers sunlight readability, button/touch behaviour if enabled, location permission and latency with the user's actual phone, connection loss and battery impact. Emulator success cannot substitute for those physical checks.

## 16 Delivery milestones

| Milestone | Deliverable | Exit criteria |
| --- | --- | --- |
| Foundation | Minimal Emery project and platform report | Clean build, emulator launch, recorded budgets and phone platform; prove a storage strategy for safe replacement, staged future data and recovery. |
| Design prototype | Time and Bus home, board and picker using clearly marked fixtures | Native-size screenshots reviewed; Neon Transit remains readable; button flow works. |
| Validated local data | Six-stop dataset, coordinate evidence and reconciliation report | Every included trip/calendar verified; unverified coordinates excluded from Nearby. |
| Offline core | Schedule engine and watch screens with real data | Required time/calendar tests pass; usable disconnected. |
| Phone integration | Clay, one-shot location, Nearby and fallback states | Permission/failure scenarios work; preferences persist; phone compatibility tested. |
| Timetable updater | Static release feed, maintainer publishing tools, phone fetch and safe watch activation | Compatible updates install without reinstall; daily/manual checks, future activation, failures and recovery tests pass. |
| Personal release | PBW, source, publishing/data-update instructions and test report | Physical checks, an end-to-end timetable-only update and seven-day use review complete; known limitations documented. |

The first useful incremental build can show verified Kasugaoka Koen departures offline. It is a milestone, not completion of the six-stop release. Public distribution is a separate later decision.

## 17 Risks and decisions to revisit

| Risk or decision | Response |
| --- | --- |
| Clock-first concept mistaken for a dedicated watchface | Product type is confirmed as an interactive watch app. Retain ordinary app navigation and exit behaviour. |
| Transit sources change or disagree | Block affected data from release until reconciled; retain provenance and update diffs. Daily app checks deliver published updates but do not replace maintainer source review. |
| Update hosting unavailable or watch storage insufficient | Preserve last valid data, expose freshness, and prove transfer/storage limits before release. |
| Japanese fonts exceed resource budget | Prototype a restricted glyph set early; retain readable English fallback. |
| Colour looks less vivid on hardware | Review exact palette outdoors and favour contrast over decorative detail. |
| GPS cannot distinguish roadside or shortest walk | Keep directions explicit; label straight-line distances and uncertainty. |
| Holiday or special-service coverage is incomplete | Show unconfirmed status; never treat missing data as an ordinary weekday. |
| User is away from the saved walking origin | Require explicit context before applying that walking allowance. |
| Phone OS limits location while companion app is suspended | Test actual device; preserve manual functionality and clear refresh/failure state. |
| Personal app grows into a public maintenance burden | Keep coverage local and release scope explicit; revisit data reuse and support requirements before publishing. |

Remaining decisions: update hosting and maintainer source-review cadence; personal-only versus later neighbourhood release; phone OS and companion version; preferred default boarding direction and favourite order; measured walking times; English versus bilingual home labels. These do not prevent a draft or offline prototype, but must be resolved before the dependent feature is called complete.

## 18 Reference material

- [Kintetsu official timetable directory](https://www.kintetsu-bus.co.jp/route/timetables)
- [Kintetsu route map](https://www.kintetsu-bus.co.jp/pdf/ibaraki.pdf)
- [Hankyu official timetable directory](https://www.hankyubus.co.jp/rosen/timetable/)
- [Hankyu Handai Higashiguchi stop](https://transfer-cloud.navitime.biz/hankyubus/courses?external-busstop=0838)
- [Hankyu hospital stop](https://transfer-cloud.navitime.biz/hankyubus/courses?external-busstop=1384)
- [Hankyu medical faculty stop](https://transfer-cloud.navitime.biz/hankyubus/courses?busstop=00021076)
- [PebbleKit JS communication and location guide](https://developer.rebble.io/guides/communication/using-pebblekit-js/)
- Local SDK evidence: SDK 4.33.1 sdk-core/pebble/common/tools/pebble_sdk_platform.py, emery_platform; Emery include/pebble.h for communication and persistence APIs.
- Project PLAN.md summarizes implementation order. This PRD defines the detailed requirements, including the selected Time and Bus home layout and approved timetable updates without reinstalling.
- Previously produced integrated timetable PDF and source downloads remain research references. They are not, by themselves, validation of a production dataset.
