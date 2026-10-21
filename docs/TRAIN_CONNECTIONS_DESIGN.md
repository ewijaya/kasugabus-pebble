# Train connections — design (draft, not implemented)

Answers one question on the watch: *if I take this bus, which train do I catch
and when do I reach Osaka (or Kyoto)?* It is not a station timetable.

Basis: `tools/train_prototype.py` (feasibility study, 2026-10-20). Findings it
established, all weekday, Kintetsu buses that call at both stations:

- Osaka-bound: JR is first on every trip (median 12 min ahead of Hankyu).
- Kyoto-bound to Kyoto/Kawaramachi: JR first on ~75%, Hankyu first on ~25%
  (Handai stops only). To Takatsuki the two are within ~3-5 min.
- Route 1 buses end at JR Ibaraki; buses to Hankyu Ibaraki-shi (routes 2, 12,
  22) call at JR first and reach Hankyu 5-8 min later.

So the screen recommends one station and mentions the other only when it wins
or is the only choice. It never shows a side-by-side table.

## Where it appears

| Place | Change |
|---|---|
| Details (existing) | A short "Train" block after the route lines, no new navigation |
| Train screen (new, `KB_SCREEN_TRAINS`) | Full connection for one bus; opened from the menu or a bound home button |
| Hold-SELECT menu | New row **Train connection** for the bus on home / selected on the board |
| Home buttons | New action `KB_ACTION_TRAIN` (count 9 → 10); unbound by default |

Home itself is unchanged. It already packs stop, direction, time, countdown and
later buses into 200 × 228 px at three text sizes, and a fifth line would
force a smaller tier.

## Mockups (Large text, 200 × 228 px, ~16 characters per line)

Train screen, Osaka-bound, JR recommended:

```
Train connection
Bus 22  8:11 JST
────────────────
JR Ibaraki   8:35
 bus arrives
▶ 8:40 Local
  Osaka  8:59
  then 8:44 Rapid
       Osaka  8:52
────────────────
SELECT: to Kyoto
```

Hankyu wins (Kyoto-bound only):

```
Train connection
Bus 22  7:49 JST
────────────────
Hankyu       8:03
 stay on bus
▶ 8:08 Ltd Exp
  Kawaramachi
  9:00  (9 min
  earlier than JR)
────────────────
JR Ibaraki   7:57
  8:09 Local → 9:19
```

Route 1 bus (ends at JR, no Hankyu option) and the Details block:

```
JR Ibaraki   8:35        Train
▶ 8:40 Local             JR 8:40 Local
  Osaka  8:59            Osaka 8:59
  (route 1 ends          Select > more
   at JR)
```

Rules for the text:

- Destination names are romaji ("Osaka", "Umeda", "Kyoto", "Kawaramachi").
  The watch's Japanese font is a small subset, so no kanji here.
- Always labelled *Scheduled*; arrival times are timetable values, not live.
- No train in the evening: "No more trains tonight. First train 5:06."
- Times after midnight reuse the existing 24:xx service-day handling.

Buttons: UP/DOWN scroll later trains, SELECT flips Osaka ↔ Kyoto for this
view, hold SELECT sets a leave-now reminder (the existing one, for the bus),
BACK returns.

## Decision rule

For each station S that the bus calls at, with arrival `a_S` from the bus data:

1. `ready = a_S + walk_S` (default 4 min each, user-adjustable).
2. Take the first train in S's list for the chosen direction and day type
   with `departure >= ready` that reaches the target. Hankyu trains for
   Tengachaya and Shojaku never reach Umeda and are skipped; JR trains
   that stop short of the target are skipped.
3. `arrival_S = departure + duration`. The station with the earlier
   `arrival_S` is shown first. The other is shown only if it exists and
   either wins by itself or the user turned on "always show both".
4. Ties go to JR; it is the shorter ride on the bus.

Target stations: Osaka → JR Osaka / Hankyu Osaka-umeda; Kyoto → JR Kyoto /
Hankyu Kyoto-kawaramachi. These are different places, so the screen names the
arrival station and never claims they are equivalent.

## Data

**Bus arrival offsets, in the timetable binary (built: schema 2).** One new
table, one byte per Kintetsu departure up to the last that has times: JR
Ibaraki minutes (1-31) plus a 3-bit code for the Hankyu Ibaraki-shi gap
(4-10 min after JR). Ride times differ by trip (route 22 spans 12-29 min to
JR), so a per-route value is not enough. Layout and compatibility:
`docs/DATA_FORMAT.md`; the data release: `docs/DATA_RELEASE_5.md`.

- Needs a 136-byte header and data level 2. Apps that predate it keep using
  the previous feed revision and report the update as incompatible.
- Costs 1,833 bytes: 27,845 (v4) -> 29,678, leaving 3,090 under the 32,768 cap.
- Stays in sync with bus changes because it travels in the same feed payload.

**Train table, a bundled resource (`data/trains.bin`, 8,826 bytes; moves to
`resources/` when the watch loads it).** Layout: `tools/train_build.py`. Trains
change about once a year (mid-March), so this ships with the app and is
refreshed in a spring release. It holds, per station × direction × day type:
departure minutes as 1-byte deltas, a type/destination id, and two 1-byte
durations (Osaka-bound lists use one; Kyoto-bound lists use both: Kyoto /
Kawaramachi and Takatsuki). 4 bytes per train.
Header carries `valid_from` / `valid_until`.

The screen reads only the two sections it needs (JR + Hankyu for the chosen
direction and day type, ≈ 2 KB) with `resource_load_byte_range`, so the free
heap is not cut by the whole table. *Check that the call exists in the
installed SDK 4.33.1 before building on it.*

When the table is past `valid_until` the screen still works but says "Train
times from March 2026; check for changes" in the footer, in the same spirit as
the existing review-date warnings.

**Settings** (phone Clay, stored in the existing extras record, which has
spare flag/byte capacity): default direction (Osaka / Kyoto), walk minutes
per station (JR, Hankyu; default 4), show both stations always (off).

## Edge cases

- Bus late or early: add a note that a 4-min buffer is used; the screen also
  shows the next train so a miss is not a dead end.
- Hankyu "stay on bus" only applies when the bus calls at Hankyu Ibaraki-shi;
  for route 1 buses the station row is JR only.
- Holidays and the bus data's day-type overrides: use the same resolver as
  buses, then map Saturday/Sunday/holiday → the trains' weekend list (JR's
  Saturday and Sunday pages are identical; Hankyu publishes weekday and
  Saturday/holiday only).
- Dataset has no data for a trip (new feed trip without offsets): the block is
  omitted, nothing breaks.

## Build plan

1. **Done.** `tools/train_fetch.py` saves the station pages and per-train
   arrival times (with hashes) under `data/sources/trains/`;
   `tools/train_build.py` builds `data/trains.bin` offline; `tests/test_trains.py`.
2. Schema 2: compiler writes the offsets table; `engine.c` gets
   `kb_arrival_offsets(trip, &jr, &hk)`; validator and phone checks updated.
3. A pure-C solver (`src/c/trains.c`) for the decision rule, with host tests
   in the style of `tests/test_engine.c`, including midnight and no-train cases.
4. UI: `KB_SCREEN_TRAINS`, Details block, menu row, `KB_ACTION_TRAIN`, help text.
5. Settings: Clay fields, extras record, phone validation.
6. Emulator captures at all three text sizes; record sizes against
   `tests/build-budgets.json`; release as 2.3.0 with timetable v5.

## Owner decisions (2026-10-20)

1. **Source terms:** approved. The saved JR Odekake and Hankyu pages may be
   committed under `data/sources/trains/` and refreshed yearly.
2. **Walking time:** 4 minutes for both stations, as the default setting.
3. **Kyoto target:** mostly Kawaramachi. Kyoto-bound defaults to Hankyu
   Kyoto-kawaramachi, with JR Kyoto as the JR arrival shown beside it. The
   screen names both arrival stations; it does not call them equivalent. A
   setting can switch the Kyoto target to Kyoto station only.
4. **Entry point:** nothing bound by default. The menu row and the Details
   block are the only ways in until the owner binds `KB_ACTION_TRAIN`.
