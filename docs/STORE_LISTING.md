# KasugaBus store listing

KasugaBus **1.0.0** was published and verified on 1 October 2026 after the owner
approved the final installed PBW and listing. The authenticated Dashboard,
general and Emery-filtered public catalogs, public store/changelog, and exact
GitHub/store PBW downloads passed verification. The phone's My Apps cache was
not observed; the Emery catalog is a proxy. See the
[publication receipt](../artifacts/releases/1.0.0/publication.json).

## Published identity and approved text

| Item | Published value or evidence |
| --- | --- |
| Title / type | KasugaBus; interactive watchapp |
| Hardware | Pebble Time 2 / Emery only |
| App version | 1.0.0 |
| UUID | `d7ba77b0-d528-4cc8-b35c-7052798152c9` |
| Store App ID | `f63e6ed24301414a95909564`; saved in [release-config.json](release-config.json) |
| Public listing | [KasugaBus on RePebble](https://apps.repebble.com/f63e6ed24301414a95909564) |
| GitHub release | [v1.0.0](https://github.com/ewijaya/kasugabus-pebble/releases/tag/v1.0.0) |
| Source | [ewijaya/kasugabus-pebble](https://github.com/ewijaya/kasugabus-pebble); commit `3110deecde6d154a52b1d7971e6e3c5c1bd1a54d` |
| Selected design | 1 — Neon Express; preserve the selected bus identity |
| Description | [Approved store text](releases/store-description.txt); frozen wording preserved |
| Initial notes | [1.0.0 notes](releases/1.0.0.md); frozen wording preserved |
| Category | Daily, key `daily` |
| Website | Unset; the timetable-only Pages site is not a product homepage |
| Separate companions | None; PebbleKit JS and Clay use the Pebble companion, not a dedicated KasugaBus Android/iOS app |

The published PBW is **817,922 bytes**, SHA-256
`233627ffc63e0964bff272c3a56bac11e6f7634992b06cb45143524e2bc5330a`.
The [publication receipt](../artifacts/releases/1.0.0/publication.json) records
exact-artifact approval and limitations. Future releases use the saved
existing listing; **do not submit Dashboard New again**. Registration journals
remain available for first-time failure recovery in [releasing.md](releasing.md).

## Observed Dashboard requirements

The official [New App flow](https://developer.repebble.com/dashboard/submit)
and authenticated API/frontend were inspected on 1 October 2026. During setup,
browser automation was unavailable and no assets were uploaded; that evidence
is historical. During the later approved release, the actual Dashboard New
flow was completed once and the assigned ID immediately recorded. No Orationes
ID or artwork was reused.

| Field | Observed requirement or behavior |
| --- | --- |
| Type and hardware | Derived from PBW; interactive `watchapp`, Emery only |
| Small / large icons | Recommended 80×80 / 144×144; PNG, JPEG or GIF |
| Emery screenshots | 200×228; at most five; PNG, JPEG or GIF, at most 4.4 MB each |
| Emery banner | Optional, exactly 720×320; PNG or JPEG, at most 4.4 MB |
| PBW | Advertised maximum 4.4 MB; the published artifact is below it |
| Publication | New sends `isPublished=true` with listed visibility; registration is a public release action |

These are observed requirements, not a claim of an unpublished registration
option. Use the prepared own icons rather than automatic icon generation.
Reinspect official requirements when preparing changed artwork or another
registration; they do not authorize remote actions.

## Frozen uploaded artwork and screenshots

The six approved source files meet the observed dimensions and size limits.
Their paths, byte hashes, dimensions and order remain frozen in the
[published listing manifest](../artifacts/releases/1.0.0/listing.json).
The original `docs/releases/listing.json` and its asset evidence remain an
earlier local draft; the final freeze substituted fresh release-native captures.

| Approved source asset | Dimensions | Role |
| --- | --- | --- |
| [Small icon](releases/assets/icon-small.png) | 80×80 | Technical resize of the selected Neon Express concept |
| [Large icon](releases/assets/icon-large.png) | 144×144 | Same selected design |
| [Emery banner](releases/assets/emery-banner.png) | 720×320 | Promotional artwork, not an app screenshot |
| [Home](../artifacts/screenshots/release-1.0.0-home.png) | 200×228 | First uploaded native screenshot |
| [Board](../artifacts/screenshots/release-1.0.0-board.png) | 200×228 | Second uploaded native screenshot |
| [Details](../artifacts/screenshots/release-1.0.0-details.png) | 200×228 | Third uploaded native screenshot |

The uploaded screenshots are raw native captures of the approved release,
without device frames or simulated screens. The
[published-listing preview](releases/listing-preview.html) shows copies of the
same frozen uploaded screenshot files. Their hashes match the published
listing manifest; earlier development captures retain their original provenance.

RePebble optimizes PNGs. Downloaded artwork hashes differ from the uploaded
source hashes; some pixels also differ. All six downloaded assets were
visually compared with their approved sources at the same dimensions and
order. [Artwork read-back](../artifacts/releases/1.0.0/asset-readback.json)
records both hashes, pixel deltas and visual review. Do not claim downloaded
artwork is byte-identical. The downloaded **PBW must be exact**, and its
approved SHA-256 was verified on both destinations.

The [25×25 menu icon](../resources/images/kasugabus-menu-icon.png) remains the
transparent dark bus declared as `MENU_ICON`. The
[ten original concepts and gallery](../artifacts/icon-options/index.html),
[selected black master](../artifacts/icon-options/selected/neon-express-black-master.png),
[banner master](../artifacts/store-listing/banner-master.png) and
[generation prompt](../artifacts/store-listing/banner-prompt.txt) are retained.
[Selected](../artifacts/screenshots/emery_launcher_neon_selected.png) and
[unselected](../artifacts/screenshots/emery_launcher_neon_unselected.png)
launcher captures are historical emulator icon evidence, not in-app listing
screenshots. Physical icon/navigation confirmation on earlier builds remains
identified as earlier evidence; remote Quartz-watchface captures are not
KasugaBus screenshots.

## Canonical text and read-back

The browser New form submitted CRLF and a final notes presentation newline.
Frozen manifest notes and description use LF without a trailing presentation
newline. The approved correction changed only that formatting; exact wording,
metadata, artwork and release identifiers were preserved. See
[text read-back](../artifacts/releases/1.0.0/text-readback.json).

The reviewed
[official Dashboard frontend](https://developer.repebble.com/_next/static/chunks/app/dashboard/page-f19516b8a163b03f.js?dpl=dpl_A7sdvQuJbqvryha9wFETBg4A9zWT)
uses `PATCH /api/dashboard/apps/{appId}/releases` with JSON
`{releaseId, releaseNotes}` for notes. The description correction used the
reviewed existing listing-fields-preserving PATCH contract. This records the
actual technique; there is no invented helper command. Future text changes
require their own authorization, current contract inspection and preservation
read-back. Canonical text equality and exact PBW identity remain mandatory.

## Initial-release scope and remaining checks

The owner explicitly accepted publication with the stated initial-release
limitations. Production Pages serves data v2; the app bundles v1. The release
receipt records actual final-PBW emulator HTTPS/XHR delivery and persistence.
Physical v2/feed-success confirmation belongs to the preceding `2bddb0…` build;
it is not relabelled as final-PBW physical update evidence.

Broader physical GPS/permission behavior, Clay persistence, connection-loss,
future activation/interrupted-update recovery, outdoor readability, battery
observations and seven-day actual use remain outstanding. Phone My Apps cache
freshness is unobserved. Initial publication is complete; the first complete
personal-release milestone is not.

Do not claim live arrivals, bus positions/delays, automatic walking-time
estimates, verified Kintetsu pole coordinates, coverage after 27 December 2026,
other Pebble hardware or iOS companion compatibility, citywide coverage,
completed seven-day use, or full physical GPS/settings/recovery acceptance.
The approved description covers six stop groups around Minami-kasugaoka and
retains these limits. No listing asset is missing from the approved set.
