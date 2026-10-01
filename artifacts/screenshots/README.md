# Native screenshots

The published **1.0.0** PBW is SHA-256
`233627ffc63e0964bff272c3a56bac11e6f7634992b06cb45143524e2bc5330a`.
Its native **200 × 228** Emery emulator captures were visually reviewed and
uploaded as the approved store screenshot set:

| Image | Observation |
| --- | --- |
| [Published Home](release-1.0.0-home.png) | Time and Bus hierarchy, operator and scheduled departure |
| [Published board](release-1.0.0-board.png) | Scheduled departures and Stops & tools access |
| [Published details](release-1.0.0-details.png) | Route, operator, destination and trip context |

The [frozen listing](../releases/1.0.0/listing.json) records the approved source
hashes; [read-back evidence](../releases/1.0.0/asset-readback.json) records the
store's optimized PNG representations and visual comparison. The released PBW
was not rebuilt during publication. See the [release report](../../docs/releases/1.0.0-verification.md).

Earlier development captures below belong to PBW `2bddb0b0…`, not the released digest:

| Image | Observation |
| --- | --- |
| [Development Home](emery_workflow_home.png) | Actual 15:18 clock, selected direction and scheduled departure |
| [Development board](emery_workflow_board.png) | Three departures and Stops & tools access |
| [Development details](emery_workflow_details.png) | Full boarded route, operator, destination, date and context |

Their [capture receipt](workflow-capture.json) records that exact installed PBW
and unchanged preferences. They formed an earlier store draft, now superseded.

The following captures belong to the earlier Neon Express package `4679b90e…`.
Its icon resources remain unchanged; its phone JavaScript predates the published
XHR correction:

| Image | Observation |
| --- | --- |
| [Earlier Neon Home](emery_neon_home.png) | Home verification on the owner-confirmed icon package |
| [Earlier Neon board](emery_neon_board.png) | Departure-board verification on that same package |
| [Earlier Neon details](emery_neon_details.png) | Full route/context verification on that same package |
| [Selected launcher row](emery_launcher_neon_selected.png) | Neon Express bus visible on the cyan row |
| [Unselected launcher row](emery_launcher_neon_unselected.png) | The same black transparent bus visible on white |

The owner separately confirmed that icon is visible and highlighted on
the physical Time 2. Remote captures returned the Quartz watchface and are
labelled diagnostic; no physical launcher screenshot is claimed.

The numbered images below were captured from the earlier pre-icon acceptance PBW
`466df8dd233cb2886171eb44fe23f1188fd1b3f68bc1d872249be3262a8dff5b`
and visually reviewed at **200 × 228 pixels**. They preserve rendered pixels
and actual backlight dimming. They are not mockups or resized concept images.

`physical_01_current.png` is the physical Time 2 v4.38.4 home screen after
installation through the Poco F4 developer connection. Numbered `emery_*`
images are emulator observations with controlled dates/preferences.

| Image | What it verifies |
| --- | --- |
| [01 Home](emery_01_home.png) | Time and Bus hierarchy, one scheduled departure, explicit operator/direction |
| [02 Board](emery_02_board.png) | Three-departure view and focused trip |
| [03 Details](emery_03_details.png) | Full route, destination, date and Scheduled status |
| [04 Japanese](emery_04_japanese.png) | Restricted font renders the complete stop label |
| [05 Menu](emery_05_menu.png) | Stops, trip context and data-status access |
| [06 Favourites](emery_06_favourites.png) | Saved ordering, operator and direction |
| [07 All stops](emery_07_all_stops.png) | Six-group manual selection |
| [08 Directions](emery_08_directions.png) | Independent boarding/operator choices |
| [09 Long direction](emery_09_direction_long.png) | Long boarding label remains readable |
| [10 Long home label](emery_10_home_long.png) | Approved stop abbreviation and explicit direction |
| [11 High contrast](emery_11_monochrome.png) | Meaning survives the reduced-accent mode |
| [12 Settings](emery_12_settings.png) | Watch settings and visible state |
| [13 Nearby disabled](emery_13_nearby_disabled.png) | Explicit unavailable state; no fabricated ranking |
| [14 Saved origin](emery_14_saved_origin.png) | Synthetic configured walk 5 + buffer 2 → leave 10:26 for 10:33 |
| [15 Due](emery_15_due.png) | Scheduled 10:33 remains Due during that minute |
| [16 Following minute](emery_16_next_minute.png) | 10:33 removed at 10:34; actual next verified service displayed |
| [17 Data status](emery_17_data_status.png) | Dataset/source/review/feed timestamps separate |
| [18 Data dates](emery_18_data_dates.png) | Coverage and pending v21 effective date |
| [19 Offline future weekend](emery_19_offline_future_weekend.png) | No Hankyu service today; next verified date labelled |
| [20 Offline future status](emery_20_future_status_offline.png) | Staged v21 active without phone/feed contact |
| [21 Source review due](emery_21_source_review_due.png) | Source review notice survives successful feed checks |
| [22 Coverage unconfirmed](emery_22_calendar_unconfirmed.png) | No invented December 28 timetable |
| [23 Explicit override](emery_23_unconfirmed_override.png) | Override visible; expired coverage remains unconfirmed |
| [24 Override expired](emery_24_override_expired.png) | Temporary override expires on the next JST date |
| [25 Local clock / JST bus](emery_25_local_12h_jst_bus.png) | Local 12-hour clock distinct from Japan bus time |
| [26 Before removal fixture](emery_26_focus_before_fixture.png) | Focused 10:33 trip before isolated update |
| [27 Removed trip fixture](emery_27_focus_removed_fixture.png) | Explicit timetable-change/removed row, no silent selection jump |
| [28 Following trip fixture](emery_28_focus_next_fixture.png) | User can move from removed row to the actual following trip |
| [29 Restored baseline](emery_29_restored_baseline.png) | Bundled v1 usable after cancellation and restart |
| [Physical home](physical_01_current.png) | Actual watch capture, not an emulator image |

Images 26–28 deliberately use an incomplete isolated regression fixture;
complete reviewed data was transferred immediately afterward. Artificial
update revisions and future activation fixtures were never published.
`emery_store_home/board/details.png` are the earlier 14:41 listing captures on
`4679b90e…`, preserved with [their asset evidence](../store-listing/neon-assets-evidence.json).
Other unlisted, unnumbered images are development diagnostics. No outdoor readability or glance-time result is inferred
from these captures. See [verification](../../docs/VERIFICATION.md).
