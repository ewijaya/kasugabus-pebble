# KasugaBus communication contract (schema 1)

All key numbers fixed in package.json. AppMessage envelopes use TYPE=0, SESSION=1, SEQ=2, VERSION=3, LENGTH=4, CRC=5, DATA=6, STATUS=7, REQUEST=8, STAMP=9, ACCURACY=10, EFFECTIVE=11, PENDING=12, FLAGS=13. Dataset versions uint32; effective and coverage dates in binary are JST days since Unix epoch. CRC32 is corruption detection, transport trust is fixed-host HTTPS. Chunk payload 192 bytes; watch persistent record size256. Firmware minimum requires persist_get_max_size and measured enough capacity (8 complete payload slots plus metadata/preferences, 266240 bytes).

TYPE: HELLO1 phone->watch; STATE2 watch->phone (VERSION active, PENDING newest pending, FLAGS auto-check enabled bit0/location bit1, DATA preference bytes, LENGTH max payload); CHECK3 watch->phone REQUEST id STATUS0 automatic1 manual; FEED4 phone->watch REQUEST STATUS STAMP(success only); BEGIN5 phone->watch REQUEST SESSION VERSION LENGTH CRC; CHUNK6 phone->watch SESSION SEQ DATA; COMMIT7 phone->watch SESSION; ACK8 watch->phone SESSION SEQ STATUS (0 success,1 retry,2 reject,3 installed,4 staged,5 capacity,6 incompatible); LOCATION9 watch->phone REQUEST VERSION DATA coordinates; NEARBY10 phone->watch REQUEST VERSION STAMP ACCURACY STATUS DATA; SETTINGS11 phone->watch DATA full versioned settings bytes. RESTORE12 reserved.

BEGIN ACK SEQ=0; CHUNK ACK SEQ echoes zero-based chunk; COMMIT ACK SEQ=65535. Receiver advances expected sequence only on successfully persisted complete chunk; identical duplicates re-ack, reordered/wrong-session rejected without touching committed slots. Sender waits for ACK each step, retries max3 at2 seconds; timeout 30 seconds abandons staging. A repeated COMMIT after ACK loss re-acks committed session.

Every ACK includes FLAGS equal to the acknowledged original TYPE (5 BEGIN,
6 CHUNK or7 COMMIT). The sender rejects missing or mismatched phase flags;
this distinguishes a delayed duplicate BEGIN ACK from the first chunk ACK.

FEED status: 0 checking,1 downloading,2 checked(no new),3 updated,4 unavailable,5 failed,6 app-update-required,7 not-configured,8 transferring. Only 2 or3 STAMP sets successful feed-check timestamp; source review dates independent. A watch CHECK is sent only after HELLO (reconnect HELLO supported); watch persists automatic attempt timestamp when a CHECK is queued after phone readiness. Manual bypasses rolling24h; one request/transfer at once. Phone uses one bounded attempt.

LOCATION DATA carries verified poles from selected dataset as packed (id:u16,lat_e7:i32,lon_e7:i32) records. Phone must use these rather than old bundle coordinates. NEARBY DATA packed (id:u16,distance_metres:u32) records. status0 good,1 low accuracy,2 stale,3 denied,4 timeout,5 unavailable,6 outside area,7 no coordinates,8 disabled. Fix maxage120 seconds and accuracy<=100m; outside if nearest>2000m. Stable ties within uncertainty retain favourite/input order. No coordinates persisted or logged.

Settings bytes little-endian (fixed80 bytes): schema u8=1; flags u8 (auto1,location2,nearbyStartup4,highContrast8,reducedMotion16); default_id u16; buffer u8 (0..30); count u8 (0..12); reserved2 bytes; 12 favourite u16 ids at8; 12 scoped walk records (id:u16,minutes:u8 0..120, reserved:u8) at32. Zero id means unused, walk absent means unset. Full message validates atomically, duplicates/unknown ids reject, preserve previous. Saved-origin context selected explicitly watch-side; temporary Nearby selection never changes default/favourites.

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
