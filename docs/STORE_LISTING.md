# KasugaBus initial store listing — local preparation

Prepared on 1 October 2026. KasugaBus is not registered or published. This
document inventories reviewable local text and assets; it does not authorize
registration, upload or publication. On this date the lead inspected the
official authenticated API and the frontend source for the
[New App submission flow](https://developer.repebble.com/dashboard/submit).
Browser automation was unavailable; this was source/API inspection, not a
visual walkthrough. The current account's app collection had no match for
KasugaBus's UUID or intended repository. No Orationes listing ID or artwork is
reused. Daily was selected for KasugaBus's commuting use from the current
category choices.

## Identity and text

| Item | Local candidate or evidence |
| --- | --- |
| Title | KasugaBus |
| Type | Interactive app, not a watchface |
| Hardware | Pebble Time 2 / Emery only |
| Version | 1.0.0; no version bump performed |
| UUID | `d7ba77b0-d528-4cc8-b35c-7052798152c9` |
| Selected design | 1 — Neon Express; keep the selected bus identity |
| Description | [store-description.txt](releases/store-description.txt), customer-facing draft with explicit coverage and unavailable online updates |
| Initial notes | [1.0.0.md](releases/1.0.0.md), unpublished draft with release limitations |
| Source destination | Intended `ewijaya/kasugabus-pebble`; repository access and public source URL are unverified |
| Website | No live website is verified; do not submit the configured feed URL as a functioning homepage |
| Category | Recommend **Daily**, key `daily`, observed in the current API/frontend choices; the app serves a commuting routine |
| Companion entries | Clay settings use the Pebble companion; no separate KasugaBus Android/iOS app is supplied |
| Store ID / public listing URL | Both remain unset until KasugaBus registration; no existing account listing matched during inspection |

The intended release artifact is
[KasugaBus-1.0.0-emery.pbw](../artifacts/KasugaBus-1.0.0-emery.pbw),
**817,565 bytes**, SHA-256
`2bddb0b092d51c7cdab6944c56a11bb377f4a97932643ee37541450bfc8bdb09`.
[Verification](VERIFICATION.md) distinguishes fresh exact-PBW native checks
from earlier unchanged-code scenarios and physical navigation. Installation
and icon visibility confirmation are not publication approval.

## Observed Dashboard requirements

The following requirements came from the official submission frontend source
inspected on 1 October 2026. They are not copied from Orationes.

| Field | Observed requirement or behavior |
| --- | --- |
| Type and hardware | Derived from the uploaded PBW; verify interactive `watchapp` and Emery only |
| Small / large listing icons | Recommended **80×80 / 144×144**; PNG, JPEG or GIF accepted |
| Emery screenshots | **200×228**; at most five; PNG, JPEG or GIF, maximum **4.4 MB each** |
| Emery banner | Optional, exactly **720×320**; PNG or JPEG, maximum **4.4 MB** |
| PBW | Frontend advertises a **4.4 MB** maximum; the 817,565-byte candidate is below it |
| Separate companions | No dedicated Android or iOS KasugaBus app; PebbleKit JS/Clay does not constitute a separate companion listing |
| Publication | The reviewed new-app flow sends `isPublished=true` with `listed` visibility; registration is a public publication action |

Use the two explicitly prepared listing icons rather than relying on automatic
icon generation from the PBW. Keep app ID and public listing URL unset until
the newly created record is returned and verified. This inspected flow does
not establish an unpublished empty-registration option.

## Available local images

Dimensions below were read from each PNG's IHDR header. All six proposed
listing assets were visually inspected locally and meet their observed
dimensions; each file is below 4.4 MB. This is asset review, not authorization
to submit them.

| Asset | Actual dimensions | Proposed role and limitation |
| --- | --- | --- |
| [Small listing icon](releases/assets/icon-small.png) | 80×80 | Technical resize of the selected original Neon Express concept; white bus on black |
| [Large listing icon](releases/assets/icon-large.png) | 144×144 | Same selected design, prepared for the recommended large-icon size |
| [Emery banner](releases/assets/emery-banner.png) | 720×320 | Optional promotional graphic matching the bus and Neon Transit palette; not an app screenshot |
| [Listing Home](releases/assets/emery_01_home.png) | 200×228 | First screenshot: fresh final-PBW native capture at the actual 15:18 clock, with verified route 2 at 15:34 |
| [Listing board](releases/assets/emery_02_board.png) | 200×228 | Second screenshot: actual 15:34, 16:04 and 16:34 scheduled departures |
| [Listing details](releases/assets/emery_03_details.png) | 200×228 | Third screenshot: Kintetsu route 2, destination, JST date and General/Nearby context |
| [Bundled menu icon](../resources/images/kasugabus-menu-icon.png) | 25×25 | Transparent dark-bus `MENU_ICON`; preserve in the PBW, but use dedicated 80×80 / 144×144 assets for the store |
| [Original Neon Express concept](../artifacts/icon-options/01-neon-express.png) | 1254×1254 | Source for the prepared listing-icon technical resizes; selected by the owner |
| [Selected black master](../artifacts/icon-options/selected/neon-express-black-master.png) | 1254×1254 | Transparent source for the final dark launcher glyph, retained separately from listing-icon derivatives |
| [Earlier master](../artifacts/icon-options/selected/neon-express-master.png) | 1254×1254 | Earlier white candidate; retained history, not the final launcher asset |
| [Selected launcher row](../artifacts/screenshots/emery_launcher_neon_selected.png) | 200×228 | Actual emulator icon QA evidence; not an in-app listing screenshot |
| [Unselected launcher row](../artifacts/screenshots/emery_launcher_neon_unselected.png) | 200×228 | Actual emulator icon QA evidence; not an in-app listing screenshot |
| [Earlier physical Home](../artifacts/screenshots/physical_01_current.png) | 200×228 | Real Time 2 capture from the preceding PBW; supporting evidence, not a final-digest screenshot |

Use actual raw app captures for the screenshot set, without device frames or
simulated screens. The proposed order is Home, board, details because Home is
the app's default entry screen. Preserve their original rendered colours and
backlight dimming. The fresh listing captures came from the final `2bddb0b0…`
PBW at the actual date/time with unchanged original preferences. Current v28
and future v29 are complete test copies of the reviewed timetable; neither is
a published timetable release. The bright Home is the actual backlight state,
not a recoloured image. [Screenshot provenance](../artifacts/screenshots/README.md)
labels historical fixtures and diagnostics; those are not proposed store
assets. Remote physical launcher captures returned the Quartz watchface and
must not be presented as KasugaBus screenshots.

All ten original icon concepts and their
[gallery](../artifacts/icon-options/index.html) are retained. The banner's
generation [master](../artifacts/store-listing/banner-master.png) and
[prompt](../artifacts/store-listing/banner-prompt.txt) are preserved. The
prepared [listing manifest](releases/listing.json) records the proposed fields
and files; [asset evidence](releases/assets/evidence.json) binds all six image
hashes, dimensions and the exact final PBW. Selection of Neon Express and this
local inventory do not alone authorize public registration or asset upload.

## Missing inputs and claims to avoid

- No missing image is identified for the proposed three-screenshot set, two
  listing icons and optional banner. Complete the owner's metadata/assets
  review before public submission.
- Verify the public source/homepage destinations before listing them as live.
  GitHub Pages is configured locally but has not been deployed or checked live.
- Complete or explicitly scope the pending physical release checks and obtain
  exact-artifact publication approval before a public first release.

Do not claim live arrivals, bus locations, delays, automatic walking-time
estimates, verified Kintetsu pole coordinates, coverage after 27 December 2026,
a working production update feed, support for other Pebble hardware, a
separate phone app, completed seven-day use, or full physical update/GPS
acceptance. The text is specific to six stop groups around Minami-kasugaoka;
it does not imply citywide or Japan-wide timetable coverage.

The Orationes publishing/listing skills were read as reference material. Their
existing-app update workflow preserves another app's metadata; it does not
define KasugaBus first-registration fields or authorize any external action.
