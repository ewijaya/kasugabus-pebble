# Timetable v5 (schema 2) — bus minutes to JR Ibaraki and Hankyu Ibaraki-shi

Prepared 21 October 2026. **Not published.** It needs the app release that
carries schema 2 support (data level 2) to be on the RePebble store first;
installed 2.2.x apps ignore it by design. The bundled baseline is unchanged.

v5 is v4 plus, for each Kintetsu bus that ends at JR Ibaraki or Hankyu
Ibaraki-shi, the minutes from boarding to each station. Everything else is
identical to v4: stops, calendar, coverage (to 2026-12-27), verification and
review dates, and all 1,939 departures by time, route and stops.

| Item | v4 | v5 |
| --- | --- | --- |
| Binary schema | 1 | 2 |
| Minimum app/data level | 1 | 2 |
| Compiled bytes | 27,845 | 29,678 (feed limit 32,768) |
| Departures | 1,939 | 1,939 |
| Departures with station minutes | 0 | 1,199 |

## Where the minutes come from

Each time is read from the same printed column of the Kintetsu line matrix as
the departure itself (`data/extraction/kintetsu_*_tables.json`; the ＪＲ茨木駅
and 阪急茨木市駅 rows below the boarding row), as a difference in minutes.
`tools/data_build.py --station-times` writes `data/timetable_v5.json` and
asserts for every departure that the stations with a printed time are exactly
the stations in the pattern's own call list, that times are positive and at most
60 minutes, and that Hankyu follows JR. Buses to the university, Mihogaoka and
Handai Honbu, which are not destined for a station, carry none.

| | JR Ibaraki | Hankyu Ibaraki-shi |
| --- | --- | --- |
| Departures with a time | 1,199 | 1,034 |
| Ride, minutes | 12-29 | 17-37 |

Hankyu follows JR by 5, 6 or 8 minutes (4 / 96 / 934 departures). The route `[1]`
buses end at JR Ibaraki, which is why 165 departures have no Hankyu time.

## Room left

The payload has 3,090 bytes under the 32,768-byte limit. The station table
packs each row into one byte (JR minutes 1-31, Hankyu gap 4-10 minutes); a
two-byte-per-row layout would have left only 1,265 bytes, less than the 1,267
bytes that adding a single stop (v4) cost.

## Publication checklist (not yet done)

1. Release the app version that supports schema 2 and confirm it on the store.
2. Run `tools/publish_feed.py` for v5 with the usual review report and hosting
   validation. Do not publish v5 before step 1: an installed 2.2.x app would
   report the update as incompatible on every check and stay on v4.
3. Decide whether apps that cannot read schema 2 should keep receiving
   timetable corrections. The feed has one `current` release, so after v5 they
   would not.
