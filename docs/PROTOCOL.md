# KasugaBus communication contract

All key numbers fixed in package.json. AppMessage envelopes use TYPE=0, SESSION=1, SEQ=2, VERSION=3, LENGTH=4, CRC=5, DATA=6, STATUS=7, REQUEST=8, STAMP=9, ACCURACY=10, EFFECTIVE=11, PENDING=12, FLAGS=13. Dataset versions uint32; effective and coverage dates in binary are JST days since Unix epoch. CRC32 is corruption detection, transport trust is fixed-host HTTPS. Chunk payload 192 bytes; watch persistent record size256. Firmware minimum requires persist_get_max_size and measured enough capacity (8 complete payload slots plus metadata/preferences, 266240 bytes).

TYPE: HELLO1 phone->watch; STATE2 watch->phone (VERSION active, PENDING newest pending, FLAGS auto-check enabled bit0/location bit1, DATA preference bytes, LENGTH max payload); CHECK3 watch->phone REQUEST id STATUS0 automatic1 manual; FEED4 phone->watch REQUEST STATUS STAMP(success only); BEGIN5 phone->watch REQUEST SESSION VERSION LENGTH CRC; CHUNK6 phone->watch SESSION SEQ DATA; COMMIT7 phone->watch SESSION; ACK8 watch->phone SESSION SEQ STATUS (0 success,1 retry,2 reject,3 installed,4 staged,5 capacity,6 incompatible); LOCATION9 watch->phone REQUEST VERSION DATA coordinates; NEARBY10 phone->watch REQUEST VERSION STAMP ACCURACY STATUS DATA; SETTINGS11 phone->watch DATA full versioned settings bytes. RESTORE12 reserved.

BEGIN ACK SEQ=0; CHUNK ACK SEQ echoes zero-based chunk; COMMIT ACK SEQ=65535. Receiver advances expected sequence only on successfully persisted complete chunk; identical duplicates re-ack, reordered/wrong-session rejected without touching committed slots. Sender waits for ACK each step, retries max3 at2 seconds; timeout 30 seconds abandons staging. A repeated COMMIT after ACK loss re-acks committed session.

Every ACK includes FLAGS equal to the acknowledged original TYPE (5 BEGIN,
6 CHUNK or7 COMMIT). The sender rejects missing or mismatched phase flags;
this distinguishes a delayed duplicate BEGIN ACK from the first chunk ACK.

FEED status: 0 checking,1 downloading,2 checked(no new),3 updated,4 unavailable,5 failed,6 app-update-required,7 not-configured,8 transferring. Only 2 or3 STAMP sets successful feed-check timestamp; source review dates independent. A watch CHECK is sent only after HELLO (reconnect HELLO supported); watch persists automatic attempt timestamp when a CHECK is queued after phone readiness. Manual bypasses rolling24h; one request/transfer at once. Phone uses one bounded attempt.

LOCATION DATA carries verified poles from selected dataset as packed (id:u16,lat_e7:i32,lon_e7:i32) records. Phone must use these rather than old bundle coordinates. NEARBY DATA packed (id:u16,distance_metres:u32) records. status0 good,1 low accuracy,2 stale,3 denied,4 timeout,5 unavailable,6 outside area,7 no coordinates,8 disabled. Fix maxage120 seconds and accuracy<=100m; outside if nearest>2000m. Stable ties within uncertainty retain favourite/input order. Current phone fixes remain transient and are not logged or sent to the watch.

Settings bytes little-endian (fixed80 bytes): schema u8=2; flags u8 (auto1,location2,nearbyStartup4,highContrast8,reducedMotion16); default_id u16; buffer u8 (0..30); count u8 (0..12); text size u8 at6 (0 Standard,1 Large,2 Extra Large); theme u8 at7 (0 Neon Dark,1 Neon Light,2 High Contrast Dark,3 High Contrast Light); 12 favourite u16 ids at8; 12 scoped walk records (id:u16,minutes:u8 0..120, reserved:u8) at32. HighContrast mirrors themes2/3. Schema1 with zero reserved bytes migrates to Large and its equivalent dark theme. Zero id means unused, walk absent means unset. Full message validates atomically, duplicates/unknown ids reject, preserve previous. Saved-origin context selected explicitly watch-side; temporary Nearby selection never changes default/favourites. Startup bit4 requires location bit2; Clay clears startup when location is turned off.

## Version 2 reference-location extension

Existing key numbers, timetable format, update phases and Nearby9/10 remain
unchanged. TYPE14 REFERENCE_LOCATION carries REQUEST, VERSION, FLAGS0 current
phone or1 saved home, and the same verified-pole DATA as LOCATION9. TYPE15
REFERENCE_RESULT echoes REQUEST/VERSION/FLAGS; STATUS0–8 has the same meaning
as Nearby, with9 meaning home not set. A successful result contains only
6-byte point/distance rows, STAMP and ACCURACY. No reference coordinate appears
in an AppMessage. Non-success states carry no ranked distances.

TYPE16 HOME_CHANGED contains only STATUS0 saved or9 cleared. It invalidates
cached home distances and never requests another location automatically.
The phone stores a pending notification atomically with a changed home record.
Delivery uses three bounded attempts and resumes on reconnect/STATE or worker
restart. A Clear immediately replaces the coordinates with a private metadata
tombstone; successful delivery removes the tombstone. Delayed callbacks cannot
erase a newer Save/Clear. No coordinates or per-pole distances enter diagnostics.
Current reference data ages out after 120 seconds. Saved home is a fixed
reference: the phone computes its distances using the saved accuracy and a
fresh calculation timestamp, so it does not age out as a mobile fix would.
Both references require the main location preference. Android permission
remains separate; granting the app preference cannot grant OS permission.

An explicit Save current phone location as home action adds REQUEST to
SETTINGS11. The watch returns ACK8 with FLAGS11, the same REQUEST and STATUS0
only after durable settings storage (nonzero on failure), followed by STATE.
The phone starts that one-shot fix only after both the correlated successful
ACK and exactly matching valid STATE. Ordinary settings open/save and saved
home queries do not acquire a fix. Clear is an independent explicit action
that also works with location disabled.

The private home record is phone-localStorage only. It is never copied into
Clay URLs/meta/settings values, logs, watch persistence, timetable feeds or
published artifacts. All-departures selection uses separate 80-byte KBA1 banks
at keys 12/13: generation, schema/reference/count, up to 32 boarding IDs and CRC.
No distances or coordinates are persisted in those banks.

TYPE13 CATALOG watch->phone: VERSION selected dataset, SEQ contiguous starting at0, STATUS1 on final frame. DATA is repeated `{id:u16,label_bytes:u8,label:UTF8}` records; frames contain complete records. Sequence0 starts a new catalogue. The phone applies only a complete catalogue matching STATE.VERSION. Labels identify stop, operator and boarding direction. Missing saved preference IDs appear as unavailable in Clay until explicitly removed. Watch replies STATE after accepting a SETTINGS envelope; the phone retains its previous confirmed preferences until that reply.

STATE STATUS1 is a reconnect handshake request: the phone replies HELLO once;
ordinary STATE has no STATUS1 and does not cause a loop. On receipt of HELLO,
the watch sends ordinary STATE/CATALOG and dispatches an eligible deferred CHECK.
STATE also includes REQUEST for the watch's current check request ID and STAMP
for its persisted last successful feed check. Request zero is valid before the
first watch-owned check; production CHECK IDs normally begin at1. The request
counter is persisted with preferences and advances before CHECK or Restore;
clock changes and app restarts cannot reauthorize a pre-Restore download.

STATE STATUS2 cancels the phone updater after Restore bundled timetable. Restore advances REQUEST before sending that state. Every BEGIN must include the current watch REQUEST; a delayed BEGIN from an old download is rejected even if its session was not yet known when Restore ran. CHUNK/COMMIT remain bound to the accepted session. The phone cancels fetch/transfer work and ignores callbacks belonging to a cancelled job, including callbacks arriving after a new check starts.

## Version 2.1 extra settings

SETTINGS11 DATA may carry 108 bytes: the 80 preference bytes above followed by
28 extra-settings bytes. The watch validates both records before writing either
and still accepts an 80-byte message, which leaves the extras unchanged. STATE2
DATA always carries the same 108 bytes. The phone keeps the watch's current
extras for any key missing from a submitted form.

Extras bytes (little-endian): schema u8=1; home button actions u8 ×4 at1 (Up,
Down, hold Up, hold Down: 0 nothing, 1 next departure, 2 previous departure,
3 switch favourite (flip direction with fewer than two), 4 flip direction,
5 Nearby, 6 All departures, 7 departure board); flags u8 at5 (profiles1,
commute2); later departures on home u8 at6 (0..2); heads-up minutes u8 at7
(0..30, 0 off); profile A point u16 at8 and start hour u8 at10; profile B point
u16 at12 and start hour u8 at14; commute point u16 at16, earliest JST minute
u16 at18 (0..1439) and day mask u8 at20 (bit0 Sunday..bit6 Saturday). Bytes 11,
15 and 21..27 are reserved zero. Enabled profiles need two known points with
different hours; an enabled commute needs a known point and at least one day.
The watch stores the record as KBX1 with a generation and CRC32 in two banks
(keys 14/15). Reminder state is a separate local record (key 16) that never
leaves the watch.
