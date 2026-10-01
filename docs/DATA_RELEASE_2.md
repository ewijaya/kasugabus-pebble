# Timetable v2 — prepared delivery-verification reissue

Prepared locally on **1 October 2026**. Neither v1 nor v2 is claimed deployed
by this preparation. The lead will publish and verify v1 first; v2 then tests
a genuine timetable-only download to a watch holding the bundled v1, without
changing the app version or reinstalling its PBW.

Only `release_version` changes from **1 to 2**. The editable app baseline
`data/timetable.json` and the prepared v1 `hosting/public` are untouched.
The exact v1 input is archived as [1.json](../hosting/sources/1.json), and the
v2 input is [2.json](../hosting/sources/2.json). Their bytes differ at one
position. Every departure, pattern, source, boarding identity, coordinate,
calendar and effective/validity/review date is identical.

| Item | Preserved value |
| --- | --- |
| Coverage / schema / minimum app version | `minami-kasugaoka-v1` / 1 / 1 |
| Effective date and coverage start | 2026-10-01 |
| Coverage end | 2026-12-27 inclusive; December 28 onward remains unconfirmed |
| Source verification / next review | 2026-10-01 / 2026-11-01 |
| Departures / boarding points / patterns | 1,411 / 15 / 32 |
| Operators | Kintetsu 1; Hankyu 2 |
| Calendars | Kintetsu weekday/Saturday/Sunday-holiday; covered Hankyu weekday only, verified no service on weekends/holidays |
| National calendar | All 35 official 2026/2027 rows retained; broader holiday coverage does not extend operator validity |
| Coordinate scope | Six verified Hankyu poles; nine Kintetsu coordinates remain excluded |
| Departure diff | No additions, removals or changed sections |

## Exact preparation evidence

The [v2 review report](../hosting/reviews/2-review.json) binds the complete
version-only audit to these exact input bytes. The
[preflight record](../artifacts/data-release-preflight.json) preserves all 81
reviewed source hashes, the live checks, zero-departure diff and production
manifest/binary validation result.

- v1 JSON SHA-256: `3d64bc01938493ac8f56ac17cd5a02b246a18df54c8e47bd9581d47c589cce9e`.
- v2 JSON SHA-256: `a2c4e85427ce754c6aafc4b077e9f2673718230d020ab4785fb0f78b3149ce71`.
- Compiled v2: **24,203 bytes**, SHA-256 `5c7adc806702a76ea4e97e35fc41227c1b1bcf6ca6daec28ca7a0b1d24cbff61`, full-payload CRC32 **4116084579**.
- Intended immutable payload: `releases/2-5c7adc806702a76e.bin`.

The five live Kintetsu matrix PDFs and Cabinet Office holiday CSV still match
their preserved bytes. All six live Hankyu timetable objects exactly match
the reviewed timetable objects, including their schedules. Some Hankyu HTML
bytes differ outside those objects; the preserved reviewed inputs were not
replaced. The [official Kintetsu directory](https://www.kintetsu-bus.co.jp/route/timetables)
still links the same five PDFs, and the
[Hankyu directory](https://www.hankyubus.co.jp/rosen/timetable/) retains the
covered Hospital service. The [national calendar](https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html)
remains consistent with the preserved CSV.

Both operators' notices were rechecked. Hankyu's news HTML is a JavaScript
shell, so its actual [216-item notice data](https://www.hankyubus.co.jp/news/news-data.json)
was read. The [1 October Suita change](https://www.hankyubus.co.jp/news/20261001_suita_jikokuhenko.html)
applies to the Suita line, not the covered Hospital 72/164/171 service. No
applicable new change was found in these checks. The earlier full review is
still suitable today for the unchanged, bounded snapshot; this does not
verify future year-end rules or defer the 1 November review.

`tools/data_validate.py` reconstructs the reviewed baseline with a hardcoded
release version 1. Its ordinary v2 CLI therefore fails on the release number.
This report uses a freshly passed complete v1 source audit plus equality of
the entire v2 JSON and input bytes except `release_version`. It does not claim
that the ordinary v2 CLI passed or manufacture a new operator revision.

## Lead's preparation command after v1 is live

This command prepares local immutable v2 files; it does not upload them. It
uses the actual JST date by default for the manifest publication date.

```sh
python3 tools/publish_feed.py hosting/sources/2.json \
  --review-report hosting/reviews/2-review.json \
  --previous hosting/sources/1.json \
  --base-url https://ewijaya.github.io/kasugabus-pebble/timetables \
  --output hosting/public

python3 tools/validate_hosting.py hosting/public \
  --base-url https://ewijaya.github.io/kasugabus-pebble/timetables \
  --source data/timetable.json \
  --source-directory hosting/sources \
  --check-live
```

Keep v1's immutable payload and reports. The source archive lets the hosting
validator prove both versions locally; `--check-live` additionally protects
the already published v1 inventory. There is no upcoming entry or fabricated
future activation date. Deploy through the manual Pages workflow only after
the lead's publication checks, then verify the live v2 payload and an actual
watch's update/status. Local preparation and emulator fixture revisions do
not establish that delivery result. Do not rebuild the PBW or replace its
bundled v1 merely to perform this test.
