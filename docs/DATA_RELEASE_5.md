# Timetable v5 (schema 2) — bus minutes to JR Ibaraki and Hankyu Ibaraki-shi

Prepared 21 October 2026. The feed files are prepared and validated locally
but **not deployed**: the live Pages feed still serves v4. KasugaBus 2.3.0,
which reads schema 2 (data level 2), is published, so v5 can now be deployed.
Installed 2.2.x apps ignore it by design. The bundled baseline is unchanged.

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

## Feed preparation (done 21 October 2026)

- `hosting/sources/5.json` is the exact reviewed input (a copy of
  `data/timetable_v5.json`); `hosting/reviews/5-review.json` is the review
  report tied to its SHA-256 `1b5e1f935e5b…`. The report states plainly that the
  station minutes were checked only against the Kintetsu line matrix and each
  pattern's own call list, and that no human has compared them with the
  printed timetable.
- `tools/publish_feed.py` wrote `hosting/public/releases/5-1bbd5a87fca4d66c.bin`
  (29,678 bytes), the review and diff reports, and a manifest whose `current` is
  v5 with `minAppVersion` 2 and no `upcoming`. The production phone validators
  accept it at data level 2 and refuse it at level 1 ("App update required").
  The diff report lists the 1,199 added station minutes under `stationMinutes`
  (it used to ignore them and would have said "no change").
- `tools/validate_hosting.py` passes offline and with `--check-live`: all five
  payloads match their exact reviewed sources and every file already live is
  preserved unchanged.
- Not done: the Pages deployment, and a check of the deployed feed from a phone.

## Effect on older apps

The feed has one `current` release, so once v5 is deployed an installed 2.2.x
app reports every check as "App update required" and stays on v4; it will not
receive later timetable corrections until updated. v4 and earlier files stay
on the host. Apps on 2.3.0 download v5 on their next daily check or from Data
status → Select; the host caches responses for up to ten minutes.

## Deployment (needs the owner's explicit approval)

1. Commit and push the prepared files to `main`.
2. Optional dry run: dispatch `timetables.yml` with `publish=false`. It
   validates and uploads a seven-day inspection artifact and deploys nothing.
3. Deploy: dispatch `timetables.yml` with `publish=true` (and
   `initialize_dedicated_site=false`). Then check the live manifest and
   payload, and on a phone with 2.3.0 run Data status → Select and open
   Train connection.
4. Rollback: publish a higher release version; never rewrite a payload.
