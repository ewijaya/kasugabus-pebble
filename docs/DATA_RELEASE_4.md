# Timetable v4 — adds 阪大本部前 (Handai Honbu-mae)

Prepared 2 October 2026 at the owner's request. Feed-only; the bundled
baseline is unchanged. v4 is v3 plus one stop.

| Item | v3 | v4 |
| --- | --- | --- |
| Stop groups / boarding points | 7 / 17 | 8 / 18 |
| Departures | 1,766 | 1,939 (+173) |
| Compiled bytes | 26,578 | 27,845 (feed limit 32,768) |

## The new stop

Point 12, **Handai Honbu-mae → Ibaraki** (Kintetsu `[22]` to JR Ibaraki and
Hankyu Ibaraki-shi): weekday 80, Saturday 50, Sunday/holiday 43. Buses marked
美 on the pole run via Ibaraki Mihogaoka; the dataset records them as
"via Mihogaoka". Buses turn at this stop, so there is no Handai-bound pole
(Kintetsu has no `2034_handai` sheet). The line matrices print the stop as an
arrival row and an unnamed departure row; buses that end here are arrivals and
are excluded.

Sources: the existing Kintetsu line matrices and the official pole sheet
`2034_hankyuibaraki` (`data/sources/catalog_handai_honbu.json`). The owner's
photograph of the pole matched the sheet and the dataset minute for minute,
including every 美 mark.

## Coordinate

Kintetsu publishes only a stop centre. Nearby uses the single OpenStreetMap
stop position named 阪大本部前 (node 2458236405), 13 m from that centre,
recorded as `community_mapped_corroborated`.

## Unchanged

All 1,766 v3 departures are identical by time, route and stops. Calendar,
coverage, verification and review dates are unchanged.
