# Changelog

## 2.2.0

- Lists wrap around: Down on the last item returns to the top and Up on the
  first item goes to the bottom. Holding a button still stops at the end.
- Back on the home screen goes straight to the watchface instead of the app
  list. "Back on home closes to the app list" (phone settings, or Settings →
  Home buttons → Back on the watch) keeps the previous behaviour.
- New home button action: Exit to watchface.
- The Japanese stop-name screen can show 日本庭園前 (adds 本 and 庭 to the font).
- Frees about 1 KB of app memory by right-sizing the bus-number filter buffer.

## 2.1.1

- Nearby works on phones whose companion app reports location times in an
  unexpected format (observed on a Poco F4 running HyperOS); such fixes were
  rejected as "Phone unavailable". The same fix applies to All departures and
  saving a home location.
- If a precise GPS fix is not available, Nearby tries one network location
  (up to a minute old) before giving up.
- "No location fix - try outdoors" now separates a connected phone without a
  position from a genuinely unavailable phone.
- Nearby asks again automatically when the phone connects after the screen
  opened.

## 2.1.0

- Favourites on the watch: in a stop list, hold Select to add or remove a
  favourite (up to 12). Favourites show "Fav" in stop lists.
- Configurable home buttons. Defaults: Down shows the next bus, Up switches
  favourite stop (or flips direction with fewer than two favourites), hold Up
  flips direction, hold Down opens Nearby. Back returns to the soonest bus.
  Change them under Settings → Home buttons or in phone settings.
- Home lists up to two later buses ("Then 12:33 13:03") when there is room.
- App Glance: the launcher shows the next bus at your stop without opening
  KasugaBus.
- Leave-now reminders: hold Select on a departure's details for one buzz at
  your leave time (walking time + buffer), with an optional heads-up buzz.
  Quiet Time shows the reminder without vibrating.
- Daily commute alarm: one buzz on chosen days for the first bus at or after
  your time, following the weekday/Saturday/holiday timetable.
- Time profiles: open on one stop in the morning and another later in the day.
- Weekly source watch: a scheduled check of the official timetable sources
  opens a review issue when timetables or notices change.

Timetable content and the timetable feed format are unchanged. The phone and
watch exchange 28 additional settings bytes; see docs/PROTOCOL.md.

## 2.0.1

- Bigger bus information on the home screen in bundled Noto Sans Condensed
  Bold (SIL Open Font License), which continues past the system font's
  28 pt limit. Stop, direction and destination use the largest size that
  fits on one line. The departure time and countdown grow with each text
  size: Standard 32 pt beside a compact clock row; Large 36 pt and Extra
  Large 42 pt, with the countdown on its own line and the clock moved into
  the footer.
- Countdowns of 60 minutes or more show hours, such as `1 h 10 m` or `2 h`,
  on the home screen and departure boards.
- When the phone refuses location, Nearby's Refresh row explains that the
  Pebble app needs location allowed all the time.
- Phone settings show Preferences before Usual stop.
- The watch's Settings screen shows the app version.
- A Help screen (hold Select → Help) explains the buttons and menus.
- Phone settings label Large as the default text size.

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
