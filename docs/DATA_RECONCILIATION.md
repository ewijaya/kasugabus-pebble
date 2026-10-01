# Timetable source reconciliation

Release 1 was reviewed on **2026-10-01, Japan time**. The editable production dataset is `data/timetable.json`; its release contract is `coverage_id: minami-kasugaoka-v1`, `schema_version: 1`, and numeric `minimum_app_version: 1`. It contains **1,411 departure records, 15 boarding points, 32 route patterns, and 81 preserved official source records**. `data/reconciliation.json` binds the passed audit to the exact SHA-256 of that JSON file.

The original research directory supplied the source inventory. The integrated reference PDF was not imported as data. Current official directories, notices, individual stop sheets, trip details and maps were checked independently. PRD.md and PLAN.md were preserved. No private address, stored user location, inferred walking time, or unverified coordinate is included.

## Source inventory and current revisions

The [Kintetsu official timetable directory](https://www.kintetsu-bus.co.jp/route/timetables) still links these matrix sheets. All covered source cells were extracted with pdfplumber 0.11.10 and reviewed as rendered images.

| Source ID | Service sheet | PDF pages | Numeric covered cells | Printed revision |
|---|---|---:|---:|---|
| `kintetsu_0` | Kasugaoka weekday | 2 | 138 | 2024-08-21 |
| `kintetsu_1` | Kasugaoka Saturday/Sunday/holiday | 2 | 111 | 2024-08-21 |
| `kintetsu_2` | University weekday | 7 | 486 | 2024-08-21 |
| `kintetsu_3` | University Saturday | 4 | 302 | 2024-08-21 |
| `kintetsu_4` | University Sunday/holiday | 3 | 260 | 2024-08-21 |
| Total | | 18 | **1,297** | |

The exact matrix PDF URLs and SHA-256 values are in `data/sources/catalog.json` and the canonical `sources` records. Matrix sources are supplemented by nine **current individual pole PDFs**, found through the official [Kintetsu stop search](https://kintetsu-bus.jorudan.biz/diagram). This second extraction independently closes every minute and route marker for the nine Kintetsu boarding directions. The three university outbound sheets are dated 2025-12-21; the other six are dated 2024-08-21. The six search forms, their POST parameters, and the downloaded PDFs are preserved.

The [Kintetsu notice effective 2025-12-21](https://www.kintetsu-bus.co.jp/topics/38), published 2025-12-09, changes university transfers into continuous loops and says stop times are unchanged. Its linked [current route-marker sheet](https://www.kintetsu-bus.co.jp/storage/uploads/pdf/management/topics_20251209.pdf) and current individual stop sheets resolve the older matrices' `25/22` labels. The matrix revision date therefore remains 2024-08-21, while route interpretation uses the newer sources.

The [Hankyu official timetable directory](https://www.hankyubus.co.jp/rosen/timetable/) lists the covered university 72/164/171 services as weekday service. Six current per-pole timetable pages provide **114 departures**, 19 at each pole. Their displayed timetable revision is **2026-02-16**. The provider's `updatedOn`/`revisionDate` fields say 2026-07-16; these are preserved separately and are not substituted for the displayed effective revision. The old directory-linked 2024 route PDF is retained as supplementary evidence, not used to override current departure pages.

All 114 Hankyu departures are reconciled with **38 distinct individual trip-detail pages**. These resolve every boarded route and complete ordered downstream stop list, including the mixed `[72][164]` return column. Route 171 reaches Senri-chuo through Handai Honbu and Kita-senri; it is distinct from direct return services. Six pole pages plus their trip URLs and original NUXT data are preserved.

The [Cabinet Office national holiday page](https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html) and its [official CSV](https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv) supply all **35 published 2026/2027 holiday rows**, with Japanese labels and original CSV row numbers. The parser uses CP932. It includes substitute holidays and citizens' holidays, including 2026-05-06 and 2026-09-22.

Official [Kintetsu notices](https://www.kintetsu-bus.co.jp/topics) and [Hankyu notices](https://www.hankyubus.co.jp/news/) were checked on the review date. No applicable announced change inside this dataset's forward coverage was found. Upcoming 2026/2027 year-end operating calendars have not been verified.

## Identity and count reconciliation

Operator IDs are fixed: **1 Kintetsu Bus; 2 Hankyu Bus**. Stop-group IDs are fixed: 1 春日丘公園 / Kasugaoka Koen, 2 峠 / Toge, 3 緑ヶ丘 / Midorigaoka, 4 阪大東口 / Handai Higashiguchi, 5 阪大医学部病院前 / Handai Igakubu Byoin-mae, 6 阪大医学部前 / Handai Igakubu-mae. English short labels are provided for the watch; Japanese labels are retained in full.

| Boarding ID | Operator | Stop and direction | Weekday | Saturday | Sunday/holiday |
|---:|---|---|---:|---:|---:|
| 1 | Kintetsu | Kasugaoka Koen, Ibaraki via Toge | 46 | 37 | 37 |
| 2 | Kintetsu | Toge, Ibaraki via Kita Sakuramachi | 46 | 37 | 37 |
| 3 | Kintetsu | Midorigaoka, Ibaraki via Kasugaoka Koen | 46 | 37 | 37 |
| 4 | Kintetsu | Handai East, university/Mihogaoka | 81 | 50 | 43 |
| 5 | Kintetsu | Handai East, Ibaraki | 83 | 52 | 45 |
| 6 | Kintetsu | Handai Hospital, university | 81 | 50 | 43 |
| 7 | Kintetsu | Handai Hospital, Ibaraki | 80 | 50 | 43 |
| 8 | Kintetsu | Handai Medical, university | 81 | 50 | 43 |
| 9 | Kintetsu | Handai Medical, Ibaraki | 80 | 50 | 43 |
| 101 | Hankyu | Handai East, university via hospital, north | 19 | 0 | 0 |
| 102 | Hankyu | Handai East, Senri-chuo direct, south | 19 | 0 | 0 |
| 103 | Hankyu | Handai Hospital, university, south | 19 | 0 | 0 |
| 104 | Hankyu | Handai Hospital, Senri-chuo direct, north | 19 | 0 | 0 |
| 105 | Hankyu | Handai Medical, university, west | 19 | 0 | 0 |
| 106 | Hankyu | Handai Medical, Senri-chuo direct, east | 19 | 0 | 0 |

The Saturday/Sunday Kasugaoka list is one shared service, stored once with `day_types: [2,3]`. Thus the canonical record count is **1,297 + 114 = 1,411**, not the sum of all expanded calendar columns above. The independent Kintetsu pole reconciliation compares **1,408 day/minute units**, because it expands those 111 shared weekend records into both Saturday and Sunday.

Service IDs are fixed: 1 Kasugaoka weekday, 2 Kasugaoka shared weekend/holiday, 3 university weekday, 4 university Saturday, 5 university Sunday/holiday, 6 Hankyu weekday. Pattern IDs are assigned through `data/identity_registry.json`, which retains prior keys rather than reusing deleted IDs. Pattern keys include the boarding point, boarded route, destination, ordered calls, transition evidence and via label.

## Boarded routes and downstream calls

Kasugaoka route **1** terminates at JR Ibaraki; route **2** continues to Hankyu Ibaraki-shi. The individual stop sheet's `Ｊ` marker independently confirms route 1. The loop is directional: no opposite Kasugaoka pole or reversed timetable is invented.

University matrix label **25/22 is not a boarded route number**. The generator stores the actual route at each covered pole:

- Morning `★` departures board **25**, run through Handai Honbu, and continue as **22** to Mihogaoka without a transfer. The official loop notice explicitly says to remain aboard at Honbu. The useful advertised destination and verified downstream extent are Mihogaoka. Hospital and Medical can legitimately appear again after Honbu in the ordered calls.
- Afternoon `▲` departures at Handai East board **25** via Mihogaoka toward Honbu. After Mihogaoka, the current Hospital/Medical outbound sheet identifies the same loop as **22**. Those unmarked outbound 22 departures continue through Honbu toward Ibaraki.
- Direct outbound **24** ends at Honbu. All covered university return departures board **22**. A `美` marker on Hospital/Medical return sheets distinguishes departures via Mihogaoka.

Route **12** is not emitted: its target rows contain passing arrows or blanks, not covered-stop departures. Every emitted Kintetsu downstream call is taken from a numeric cell in the same matrix trip column, preserving row order and repeated calls. No blank, arrow, merged-null row label or terminal waiting row becomes an invented stop call. Full Japanese and English external stop names remain in editable JSON even where the compact runtime only needs the covered stop-group filter.

## Coordinates

Six Hankyu boarding points have verified actual pole coordinates. The official map client's [pole timeline endpoint](https://transfer-cloud.navitime.biz/apiv1/hankyubus/busstops/timeline?busstop-id=00020633&language=ja) has separate named-stop centres and `generations[].poles[]`. Only the current generation's individual pole coordinates are used. Pole IDs are matched to the exact timetable ID and direction label; the validator repeats that match.

| Boarding ID | Actual pole ID | Latitude | Longitude | Timetable ID |
|---:|---|---:|---:|---|
| 101 | 000000004946 | 34.818748 | 135.529914 | 083801 |
| 102 | 000000004947 | 34.818464 | 135.530164 | 083802 |
| 103 | 000000005947 | 34.818914 | 135.529381 | 138401 |
| 104 | 000000005948 | 34.818898 | 135.529181 | 138402 |
| 105 | 000000005949 | 34.817864 | 135.527964 | 138501 |
| 106 | 000000005950 | 34.818098 | 135.527814 | 138502 |

The paired timetable pages' shared latitude/longitude and top-level busstop centres were rejected. The nine Kintetsu coordinates are **null**, with `coordinate_status: excluded_unverified` and a reason on every record. Investigation of the official Jorudan map found a named-stop centre with an empty actual-pole list; the official route diagram provides no georeferenced pole markers. An actual Kintetsu pole location or a shared-pole relationship with Hankyu was not verified. `data/coordinate_review.json` preserves those attempts and hashes the supporting map/client files. Nearby can therefore use the six verified Hankyu poles; all six stop groups remain available manually.

## Calendar coverage and uncertainty

Day types are **1 weekday, 2 Saturday, 3 Sunday/national holiday, 0 verified no service, 255 unknown**. National holidays override the weekday/Saturday classification. Hankyu's covered service explicitly has `no_service_day_types: [2,3]`; the official directory supports those weekend/holiday zeros. No weekday timetable fallback is applied.

Operator/service validity and calendar coverage are **2026-10-01 through 2026-12-27 inclusive**. Holiday source coverage is broader, **2026-01-01 through 2027-12-31**; that broader national calendar does not extend operator validity. Dates from **2026-12-28 onward are unconfirmed**, conservatively stopping before the unverified year-end period. Coverage starts after the 2026 Obon period, so historical Obon exceptions are not inferred. `calendar.exceptions` is empty for this reviewed forward window; it does not assert that an operator never has special schedules.

Future verified date exceptions use `{date, operator_id, day_type}` and require a preserved official source. `day_type: 0` means verified no service; `255` means unknown. Calendar overrides must not silently bypass expired operator/source coverage. The source review date and next review date remain separately visible.

## Evidence and automated checks

Kintetsu departure evidence records the source ID, **1-based page and row**, and **zero-based table column** (0 is the stop-name column; 1 is the first departure). It retains printed time and matrix route label, plus a second pole-sheet locator, calendar column, marker, and **1-based minute token**. Hankyu evidence records the per-pole page and zero-based NUXT schedule/column/trip indices, operator trip ID, full printed timestamp and the trip-detail section index. Sources include original URL, local path, retrieval/review dates, byte count, SHA-256 and known revision dates.

`tools/data_validate.py` checks source hashes against both the source catalog and the explicit reviewed snapshot in `data/review_evidence.json`; extraction grids are bound to their original PDF hashes by `data/extraction/manifest.json`. It proves exact multiset closure for every target matrix cell, every independent pole day/minute/marker and every Hankyu timetable trip. It reconstructs complete ordered patterns, labels, transitions, service associations and evidence locators from preserved sources. It also checks all 2026/2027 holiday CSV rows, actual pole IDs/directions/coordinates, validity bounds and the reviewed counts.

Mutation tests reject missing, duplicated or invented departures; altered route markers/downstream calls; omitted holidays; enlarged calendar coverage; unsupported Hankyu weekends; and changed coordinates. The time parser keeps service-day times above 24:00 as minutes above 1440, although this release has no such departures. It rejects invalid minute values rather than shifting dates.

The five data test cases passed. The production compiler accepted this canonical dataset: **24,203 bytes**, including source metadata and coordinates. The editable JSON is 870,359 bytes because evidence remains readable. Shared weekend service, shared route patterns, numeric identities and compact service-day minutes reduce the watch payload without discarding the editable evidence.

## Repeating a review

Scan both official notice indexes weekly. Recheck all directory links, pole sheets, trip detail pages, actual-pole map records and the national calendar monthly; the next full review is **2026-11-01**. Review sooner when either operator announces a relevant revision. Extend year-end coverage only after its operator rules are verified.

Download new evidence to a new candidate directory, preserving the active reviewed sources:

```sh
python3 tools/data_fetch.py --output /tmp/kasugabus-source-candidates
```

The fetch tool records changed hashes and always labels candidates `reviewed: false`. Jorudan sources use their recorded POST forms; `--query-date YYYYMMDDHHMM` can replace that form's query date. For a new service date, also review date-dependent Hankyu trip URLs and upcoming generations. Recheck current directory links manually: refreshing an old URL alone cannot discover a replacement source.

After reviewing replacement sources visually and structurally, update the source catalog, confirmed dates/exception rules and explicit review evidence. Preserve boarding and pattern identities. Re-extract PDFs using the pinned dependency in `data/requirements-extraction.txt`, then rebuild and reconcile:

```sh
python3 tools/data_build.py --extract
python3 tools/data_validate.py --report data/reconciliation.json
python3 -m unittest discover -s tests -p 'test_data*.py' -v
python3 tools/compile_timetable.py data/timetable.json -o /tmp/kasugabus-reviewed.bin
```

A changed source hash fails the reviewed-source gate until explicit review evidence is updated. A generated file or successful fetch alone is not a source review. The publishing gate should require `data/reconciliation.json` with matching `releaseVersion`, `sourceSha256`, `departureCount`, `reconciled: true`, `reviewer` and `reviewedAt`. Bump release_version for an accepted replacement, generate a fresh report for its exact bytes, and test the compiled candidate before publication.
