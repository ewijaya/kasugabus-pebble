# KasugaBus binary timetable, version 1

`tools/compile_timetable.py` converts the editable, evidence-bearing JSON dataset
to a compact runtime snapshot. Evidence remains in the JSON and reconciliation
report; the watch snapshot retains operator, boarding direction, full English and
Japanese names, downstream calls, route transitions, source URLs/dates and
verified pole coordinates. A missing coordinate remains missing.

All integers are little endian. Dates are signed 32-bit Gregorian days since
1970-01-01; optional unknown dates use `INT32_MIN`. Supported dates are
1900-01-01 through 2200-12-31. UTF-8 strings use 16-bit offsets into a shared
NUL-terminated pool, whose first byte is NUL. Offsets must point at the start of
a string. A string is at most 1023 UTF-8 bytes. IDs are integers 1..255.
The maximum payload is 32768 bytes; releases target at most 24576 bytes.

## Header: 128 bytes

| Byte | Type | Meaning |
|---:|---|---|
| 0 | 4 bytes | ASCII `KBT1` |
| 4 | u16 | Schema version, 1 |
| 6 | u16 | Header size, 128 |
| 8 | u32 | Exact total payload length |
| 12 | u32 | Standard IEEE CRC32 of bytes 16 through the end |
| 16 | u32 | Monotonically increasing release version, nonzero |
| 20 | u32 | Minimum app version, nonzero |
| 24 | i32 | Earliest supported timetable date |
| 28 | i32 | Latest supported timetable date |
| 32 | i32 | First confirmed public-holiday/calendar date |
| 36 | i32 | Last confirmed public-holiday/calendar date |
| 40 | i32 | Source verification date |
| 44 | i32 | Source review due date, or unknown |
| 48 | u16 | Coverage ID string offset |
| 50 | u16 | Reserved, zero |
| 52 | u32 | String pool byte offset |
| 56 | u32 | String pool byte length |
| 60 | u16 | Maximum departure minute in this snapshot, zero if empty |
| 62 | u16 | Table count, 10 |
| 64 | 10 × 6 bytes | Table descriptors, each `{offset:u32,count:u16}` |
| 124 | i32 | Snapshot activation service date (`effective_from`) |

Tables are contiguous, in the order below, beginning at byte 128. The string
pool begins immediately after the final table and extends to the payload end.
This canonical layout avoids ambiguous overlap and hidden trailing data.
`effective_from` controls snapshot activation, while supported dates control
whether a timetable is confirmed. Those concepts remain separate.
Activation must fall within snapshot supported dates. Review dates, where
present, must be on or after the corresponding source verification date.

## Tables

Offsets in this table are relative to each record.

| Index | Table | Stride | Fields |
|---:|---|---:|---|
| 0 | Operators | 28 | `id:u8@0`, confirmed day-type mask@1; name string@2, Japanese@4, short name@6; valid from i32@8, until@12, verified@16, review due@20; first source u16@24, source count u16@26 |
| 1 | Stop groups | 8 | `id:u8@0`, reserved zero@1; short name string@2, full English@4, Japanese@6 |
| 2 | Boarding points | 24 | `id:u8@0`, group ID@1, operator ID@2, flags@3; name string@4, short@6, Japanese@8, direction English@10, Japanese@12, physical guidance@14; latitude i32@16, longitude i32@20 in degrees × 1e6 |
| 3 | Patterns | 16 | `id:u8@0`, operator ID@1; boarded route string@2, destination English@4, Japanese@6; destination group ID or zero@8, reserved zero@9; first call u16@10, call count u16@12; route-transition description string@14 |
| 4 | Services | 12 | `id:u8@0`, operator ID@1, day-type mask@2, reserved zero@3; valid from i32@4, until i32@8 |
| 5 | Public holidays | 4 | confirmed holiday date i32@0 |
| 6 | Operator exceptions | 6 | date i32@0, operator ID@4, day type@5 |
| 7 | Departures | 5 | minute u16@0, boarding-point ID@2, pattern ID@3, service ID@4 |
| 8 | Sources | 16 | source title string@0, URL string@2; revision date i32@4, verified date@8, review due@12 |
| 9 | Downstream calls | 2 | pattern ID@0, stop-group ID@1 |

Boarding point flag bit 0 means a verified coordinate is present; every other
bit is zero. Both coordinates must use `INT32_MIN` when absent. Coordinate
ranges are latitude ±90000000, longitude ±180000000.
Patterns can be shared by boarding points of the same operator. Their downstream
call lists describe verified direct calls; destination filters never infer a
transfer or merely match a similar label. Route-transition text preserves a
route change without rewriting the boarded route label.

Operator, group, point, pattern and service records are sorted by unique ID.
Holidays are sorted and unique. Exceptions are sorted and unique by date then
operator. Departures are sorted and unique by boarding point, minute, pattern,
then service. Calls are grouped by pattern, preserve source calling order, and
may repeat a stop-group ID when a loop calls there twice. Operator source slices and
pattern call slices refer to zero-based record indices. All references must
exist and agree on operator identity.
Two services cannot describe the same point/minute/pattern trip with overlapping
day masks and validity dates. Source URLs use HTTP or HTTPS.

Day types are `0=explicit no service`, `1=weekday`, `2=Saturday`,
`3=Sunday/public holiday`, `255=unknown`. Service masks use bits 1, 2 and 3
only, with at least one set; an exception can select 0..3 or 255. Exact-date
operator exceptions take precedence over holidays, then ordinary weekdays.
Absent calendar coverage, missing operator validity and a day type outside the
operator's confirmed mask produce unconfirmed state. The nonzero operator mask
uses bits 1, 2 and 3 and includes explicitly confirmed no-service types. An exact
NONE exception is confirmed no service. An operator with no services of a
known weekend type is also confirmed no service when its validity is covered.

Minutes are 0..4319 (`00:00`..`71:59`) and retain the originating service date.
Queries ask the dataset resolver for preceding originating dates as well as the
current date, preserving overnight trips across a snapshot revision. The
engine uses UTC epochs plus the fixed JST offset, independent of device/libc
timezone. A departure remains Due throughout its full scheduled minute.

## Validation and release generation

Both the C parser and phone validator check length, schema, CRC, canonical
layout, UTF-8 string boundaries, bounded values, ID uniqueness, sort order and
cross-table references before activation. Source extraction reconciliation is
a separate requirement: a valid binary does not prove the timetable agrees
with an operator's PDF. The compiler rejects invalid input instead of clipping,
repairing or inventing departures.

Example: `python3 tools/compile_timetable.py data/timetable.json -o data/timetable.bin`.
`--catalog PATH` optionally creates the phone's JSON label/coordinate catalogue.
The compiler prints payload size, departure count and SHA-256. A snapshot is
deterministic for the same canonical JSON content; evidence-only edits do not
change the binary. Holiday source evidence can cover a wider interval than the
confirmed operator calendar; only holidays within that calendar are compiled.
External calls without a covered stop-group ID remain in source JSON; repeated
covered calls retain their order in the binary.
