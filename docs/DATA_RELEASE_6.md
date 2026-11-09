# Timetable v6 — November source review

Prepared on **9 November 2026**, at the owner's request, for the existing
[GitHub Pages feed](https://ewijaya.github.io/kasugabus-pebble/timetables/manifest.json).
Publication and delivery evidence are recorded below once observed.

v6 retains all **1,939 departures, 18 boarding points, eight stop groups,
39 route patterns and 1,199 station-minute records** from v5. Only the release
number, source verification date (**9 November**) and review due date
(**1 December**) change. Coverage remains **1 October–27 December 2026**.
The app remains 2.3.0; no PBW or store release is needed. Apps older than 2.3.0
must update to receive schema 2 data.

## Source review

The review fetched all 86 catalogued sources, then checked 38 Hankyu individual
trips using **9 November**, three OpenStreetMap nodes through their JSON API,
the two additional Kintetsu stop directories, and Hankyu's current homepage,
notice-loader JavaScript and underlying notice JSON. The fetch inventory records
132 responses, their URLs, redirects, content types, byte counts and SHA-256s.
Raw responses are retained in a compressed archive; older extraction sources
and release snapshots are preserved unchanged.

- All 19 Kintetsu PDFs (five line matrices, 12 pole timetables, the route map
  and loop legend), the line directory, loop notice and Cabinet Office holiday
  page/CSV are byte-identical to the reviewed evidence. The current line and
  stop directories still select exactly those five matrices and 12 pole sheets.
  Existing visual review and extraction evidence therefore remain applicable.
- All six Hankyu pole schedules retain their complete structured content,
  including trips, routes, revision metadata and weekday-only service, after
  changing only the query day from 1 October to 9 November.
- All 38 current-date Hankyu trip details retain times, route IDs, ordered calls
  and boarding restrictions. Two downstream coordinates differ by 0.000001°:
  Handai-guchi longitude 135.516864 → 135.516865 and 2-chome South latitude
  34.819296 → 34.819297. Neither is a KasugaBus boarding coordinate. These are
  the only permitted non-date differences in the reproducible comparison.
- The three Hankyu pole APIs retain all six actual boarding coordinates and
  course mappings. Each exposes one current generation and no future generation.
- All three community-mapped boarding nodes retain their coordinates, tags and
  versions. The source-watch alerts compared live HTML pages with saved JSON
  summaries; the direct OpenStreetMap node API resolves that format mismatch.
- The supplementary 2024 Hankyu route PDF and old directory now redirect to
  the operator's Navitime search page. They supply no new timetable evidence.
  The six current pole schedules and 38 individual trips are the authoritative
  sources for this review; the historical supplementary PDF remains archived.

The source entries inside v6 retain their original extraction dates, URLs and
hashes. They describe the evidence used to construct the departures. The new
top-level verification date is supported by the separate November review.
No new human visual review or independent station-arrival review is claimed.

## Notices and year-end coverage

The [Kintetsu notice index](https://www.kintetsu-bus.co.jp/topics) and
[Hankyu notice data](https://www.hankyubus.co.jp/news/news-data.json) were inspected.
Hankyu's new notice index loads its entries from JSON; fetching the empty HTML
shell alone would miss them.

Hankyu's 11 notices dated 1 October onward concern recruitment, the Kobe
Marathon, Funasaka market, Nagaokakyo festival, Nishinomiya route 24,
Inagawa/Itami fireworks, a JR Suita–Daikin temporary service and the Nishinomiya
festival. None applies to the covered Handai routes. Kintetsu's recent entries
concern express buses, recruitment, airport buses and sightseeing; the web
index also exposed a November 8 delay notice for Shijonawate/Hanna-Ikoma, outside
this app's coverage. No applicable schedule revision was identified.

No **2026–27 year-end operator schedule** was verified. The Hankyu index still
contains the prior 2025–26 notice; it cannot establish this year's exceptions.
Coverage is deliberately not extended beyond December 27. Continue weekly
notice checks and complete the next full review on December 1, checking for
year-end rules again then. Bundled railway timetables are a separate resource
and are not refreshed by this bus-feed release.

## Reproduce and validate

```sh
python3 data/reviews/2026-11-09/verify.py > /tmp/v6-review.json
python3 scripts/test.py
python3 tools/validate_hosting.py hosting/public \
  --source data/timetable_v6.json --source-directory hosting/sources --check-live
```

The review verifier first reruns full v5 reconciliation against the preserved
matrices, independent pole sheets, Hankyu trip data, calendar and station-minute
extraction. It then checks the captured current sources and requires v6 to equal
v5 except for its three allowed metadata fields. It does not infer notice
applicability or claim human approval. The exact-input report is
[6-review.json](../hosting/reviews/6-review.json); evidence and the verifier are
in [the November review directory](../data/reviews/2026-11-09/).

Publication retains every v1–v5 immutable payload. The bundled recovery dataset
is unchanged and will still show its original review date if restored.

Local validation passed: all 232 Python tests, phone/settings/catalog tests,
five HTTP integration scenarios and native C storage/preferences suites
([test log](../artifacts/timetable-v6-tests.log)). Two SDK tests initially failed
because the installed Pebble tool 5.1.2 uses pypkjs 3's different JavaScript
engine. The complete passing run used an isolated Pebble tool 5.0.40 environment
with pypkjs 2.0.7 and STPyV8, leaving the system installation unchanged.
The captured source audit passed; its negative check rejects an altered departure.
[Live-preservation preflight](../artifacts/hosting-v6-preflight.json) passed
against the existing v5 feed.

The candidate is **29,678 bytes**, SHA-256
`e3db6a033ccb4ea312e977e8f7c6dce57f4f86d093e65337617e208318d2db56`.
