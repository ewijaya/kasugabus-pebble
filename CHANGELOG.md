# Changelog

## 2.0.1

- Bigger bus information on the home screen. Standard now uses the former
  Large sizes, Large the former Extra Large sizes, and Extra Large enlarges
  the direction, destination and countdown further with a larger departure
  time. A compact clock with the date beside it frees height for the bus
  information; it is the same at every text size. Spare height is spread
  between rows instead of left empty below the destination.
- Countdowns of 60 minutes or more show hours, such as `1 h 10 m` or `2 h`,
  on the home screen and departure boards.
- When the phone refuses location, Nearby's Refresh row explains that the
  Pebble app needs location allowed all the time.
- Phone settings show Preferences before Usual stop.

Timetable content, storage and the phone–watch protocol are unchanged.

## 2.0.0 — in preparation

- Standard, Large and Extra Large text choices in watch and phone settings;
  Large is the default for new installations and upgrades.
- Neon Dark, Neon Light, High Contrast Dark and High Contrast Light themes.
- Layouts adapt to larger text, with fewer visible rows and scrollable details.
- Preserve existing favourites, walking allowances and update settings when
  migrating version 1 preferences.
- Store banner explicitly identifies Minami-kasugaoka, Ibaraki, Osaka, Japan.
- Offline bus-number browser: operator/number → boarding point/direction →
  filtered departures and full details, using the number when boarding.
- All departures merges selected boarding points by time, then approximate
  distance. Current phone, saved home and manual/favourite references preserve
  explicit availability states and Distance unknown for unverified coordinates.
  Home coordinates stay on the phone and can be cleared in phone settings.
- Clearer Nearby location/startup controls and readable disabled-state guidance;
  turning location off also turns off startup Nearby, without changing the
  saved preference layout or location protocol.

The app update is being validated. Version 1.0.0 remains the published release
until the exact 2.0.0 candidate receives physical approval. Timetable contents
and coverage are unchanged; physical and seven-day checks remain separately
recorded in the verification report.

## 1.0.0 — initial release

- Interactive Neon Transit clock-and-departure home for Pebble Time 2 / Emery.
- Offline scheduled departures across six stop groups, with separate operators,
  boarding points, routes, directions and service calendars.
- Departure board, details, favourites, settings, trip context and data status.
- Optional phone-assisted Nearby and Clay preferences.
- Reviewed timetable downloads without app reinstallation, safe current/future
  storage and interrupted-transfer recovery.
- Selected Neon Express bus icon and app-specific store artwork.

Released as an initial build with the owner's accepted limitations: broader
physical GPS/settings/update recovery, outdoor readability, battery and
seven-day use checks remain outstanding. See [verification](docs/VERIFICATION.md)
and the [release notes](docs/releases/1.0.0.md). Publication status and artifact
identity are recorded independently; this changelog alone is not upload evidence.
