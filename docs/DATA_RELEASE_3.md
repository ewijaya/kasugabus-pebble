# Timetable v3 — adds 日本庭園前 (Nihon Teien-mae); romaji stop names

Prepared 2 October 2026 at the owner's request. Feed-only: the app's bundled
baseline (`data/timetable.json`, v1) is unchanged; watches receive v3 through
the timetable feed without an app update.

| Item | v2 | v3 |
| --- | --- | --- |
| Stop groups / boarding points | 6 / 15 | 7 / 17 |
| Departures | 1,411 | 1,766 (+355) |
| Compiled bytes | 24,203 | 26,578 (feed limit 32,768) |
| Located poles | 6 Hankyu (operator) | + 2 Kintetsu at 日本庭園前 (community-mapped) |

## The new stop

- **Point 11, Ibaraki** (`[12][22]` to JR Ibaraki and Hankyu Ibaraki-shi):
  weekday 84, Saturday 52, Sunday/holiday 45.
- **Point 10, University / Mihogaoka** (`[24][25]` towards Handai hospital):
  weekday 81, Saturday 50, Sunday/holiday 43.

Sources: the Kintetsu line matrices already in the baseline, plus the official
pole sheets `2022_hankyuibaraki` and `2022_handai`
(`data/sources/catalog_nihon_teien.json`). The owner's photograph of the
JR-bound pole matched the official sheet minute for minute.

Two weekday route-12 cells need care. 7:20 is printed on the Handai-bound row,
but that bus starts here for Ibaraki, so it is a departure from point 11. 21:03
arrives from Hankyu Ibaraki-shi and terminates here, so it is excluded.

## Romaji stop-group names

At the owner's request the seven stop groups display in romaji: Kasugaoka
Koen, Toge, Midorigaoka, Handai Higashiguchi, Handai Igakubu Byoin-mae, Handai
Igakubu-mae and Nihon Teien-mae. The operators' English sites mostly publish
translations (for example "Osaka University Hospital"); official romaji exists
only for Toge, Nihon Teien-mae (Kintetsu) and "Handai higashi-guchi" (Hankyu).
The others are Hepburn transliterations of the official kana readings, without
macrons. Destinations and intermediate stops that are not stop groups keep
their English labels. The bundled baseline keeps its English short names.

## Coordinates

Kintetsu publishes only a stop centre for 日本庭園前. With the owner's
approval, Nearby uses the two OpenStreetMap platforms, matched to directions
by the one-way carriageway each sits beside (left-hand traffic). They are
stored as `community_mapped_corroborated` with their node IDs and versions in
`data/sources/osm_nihon_teien_poles.json`, and are not presented as operator
pole records.

## Unchanged

All 1,411 baseline departures are identical by time, route and stops; many have
new internal pattern IDs because their stop lists now reference the new stop
group and romaji names. Calendar, coverage (to 27 December 2026), verification (1 October) and
review (1 November) dates are unchanged.

## Known limit

The watch's Japanese stop-name font lacks 本 and 庭 until the next app release,
which adds them; the English names and all times are unaffected.
