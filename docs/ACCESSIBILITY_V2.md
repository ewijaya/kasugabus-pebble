# KasugaBus 2.0.0 accessibility update

Requested on 1 October 2026 after the initial release: make small watch text
easier to read, provide vibrant and high-contrast dark/light themes, and make
the store banner identify the app's actual local coverage. The owner explicitly
requested version **2.0.0** through the full release workflow.

## Scope and implementation decisions

- Text size: Standard, Large and Extra Large, configurable on the watch and
  through Clay. Large is the new-install and version 1 upgrade default.
- Themes: Neon Dark, Neon Light, High Contrast Dark and High Contrast Light.
  Dark text and accents must remain legible on light backgrounds. The two
  high-contrast themes use monochrome foregrounds and inverse selection.
- Larger text changes wrapping and the number of visible list rows. Essential
  boarding information must not be silently clipped or reduced to tiny text.
  Details and data status use measured content height and bounded scrolling.
- Preserve the existing 80-byte preferences and 108-byte control banks. Schema
  2 uses reserved bytes 6/7 for text size/theme. Schema 1 migrates in memory,
  preserving favourites, walking allowances, flags, timestamps and the durable
  update request. Ordinary startup gains no persistence write.
- Keep the package UUID, existing store App ID, scheduled timetable contents,
  data compatibility level and live feed unchanged. App version 2.0.0 is
  separate from production timetable version 2.
- The banner says "Minami-kasugaoka" and "Local bus timetables · Ibaraki,
  Osaka, Japan". It does not imply all-Osaka or nationwide coverage.
- "Use phone location for Nearby" controls both manual and startup requests.
  "Open Nearby on startup" is available only while that main switch is on;
  turning location off also turns startup Nearby off. Enabling the app option
  does not grant Android location permission. Ordinary settings open/save does
  not request a location; saving the current location as home is a separate,
  explicit action. Existing flag bits and message keys remain unchanged.
- The watch distinguishes "Location is off" from permission denied, phone
  unavailable, timeout and low accuracy. The full phone-settings guidance must
  remain reachable at every text size and theme.
- The offline Bus numbers browser is part of the same update. Keys are the
  operator plus exact boarded number, deduplicated across patterns and sorted
  numerically. Only actually served boarding points appear. A session-only
  filter follows the selected number across current/future pattern IDs and
  clears when returning to ordinary Home/stop browsing; preferences and the
  binary timetable schema do not change. Production data currently has eight
  keys: Kintetsu 1, 2, 22, 24, 25; Hankyu 72, 164, 171.
- **All departures** is an additional board, reached through Stops. Choose
  Current phone location, Saved home location or manual/favourite selection,
  select the boarding points, then merge their scheduled departures. Absolute
  departure time sorts first, approximate straight-line distance breaks ties,
  and stable trip identity resolves remaining ties. Each boarding opportunity
  remains a separate row with its operator, number, stop and direction.
- Location ranking uses only the six verified Hankyu boarding-point
  coordinates. The nine Kintetsu points remain manually selectable with
  **Distance unknown**. Distances are not walking times or walking routes.
- Saved home coordinates, accuracy and save time live only in phone-local
  storage. Explicit phone settings actions save the current phone location as
  home or clear it. Normal settings open/save does not acquire a location.
  The watch receives only point IDs, approximate metres and status metadata;
  it never receives or persists the reference coordinates. Watch selection
  and reference are separately journalled on keys 12/13 without changing the
  existing preference packet. Manual is the initial reference.
- Current-location rankings become stale after two minutes; saved home is a
  fixed reference until cleared or replaced. App-disabled, permission denied,
  unavailable, timeout, stale, low-accuracy and home-not-set states remain
  explicit. Switching references or datasets invalidates old distances.
- Reordering keeps the selected boarding/trip identity. Removed trips remain
  labelled, and the next action can reach surviving equal-time departures.
  A point removed by a new snapshot may still have a verified after-midnight
  departure from a retained preceding service date; that trip remains usable
  while today's missing point/calendar is explicitly unconfirmed.

## Verification to complete

1. Validate migration, all text/theme combinations, phone/watch settings
   round-trips, malformed values and restart/torn-write persistence.
2. Build with the installed Emery SDK; measure resources and runtime heap.
3. Inspect native 200×228 captures of every text size and theme, long labels,
   details/data-status scrolling, Japanese names, both setting pickers and the
   disabled Nearby guidance. Check manual location with startup off, startup
   with both switches on, and zero requests while location is off.
4. Recheck offline schedules, the live production update and interrupted/future
   transfer recovery on the final candidate. Preserve exact-artifact evidence.
   Include merged time/distance ties, independent operator calendars,
   overnight/future boundaries, selection persistence and manual fallback.
5. Freeze and install one version 2.0.0 PBW. Obtain the owner's approval of
   those bytes and the updated listing before publishing the same artifact to
   GitHub and the existing RePebble listing.

The broader physical GPS/settings/recovery, outdoor readability, battery and
seven-day use checks remain independent requirements. The full release
workflow does not imply that unperformed personal-use checks have passed.

### Repeatable native checks

Use an Emery emulator with the exact audited PBW already installed and an
installation receipt from `scripts/capture_runtime.py`. Keep evidence paths
unique. `tools/verify_accessibility.py` checks all twelve appearance
combinations and, with `--bus-numbers`, the route browser. Both harnesses
refuse to overwrite screenshots and restore the original ordinary settings
and real clock after their controlled checks.

`tools/verify_all_departures.py` additionally requires the exact active
timetable binary and explicit `--fixture-relay --allow-all-selection-changes`
consent for a controlled emulator. It temporarily uses simulated phone
distance/status replies, drives the real watch UI, checks trip order against
the native schedule engine, and restores the prior All selection/reference
through that UI. Journal generations advance; transient ranks are not restored.
No real home coordinates are needed. The normal SDK relay must respond with
the expected native preferences and dataset before restoration is declared
successful. A frontend connection alone is insufficient.

These captures are native 200×228 images. Inspect their text, wrapping,
scrolling and contrast; a passing script does not replace visual review or
physical phone/watch acceptance. See each tool's `--help` for exact arguments
and the version-specific verification report for the candidate actually run.

## Banner source

[New 720×320 banner](releases/assets/emery-banner-local.png), generated using
the built-in imagegen tool from the original banner and technically resized
with ImageMagick. The [full prompt](../artifacts/store-listing/banner-local-prompt.txt)
and [new master](../artifacts/store-listing/banner-local-master.png) are retained.
The frozen 1.0.0 artwork and publication receipts remain unchanged.
