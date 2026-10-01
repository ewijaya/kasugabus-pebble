# Timetable release publishing

The owner selected GitHub Pages at
`https://ewijaya.github.io/kasugabus-pebble/timetables/` on 2026-10-01.
`src/pkjs/feed-config.js` now pins its HTTPS `manifest.json` URL. This is a
**local configuration change, not a deployment**: the feed has not been
published or verified live. Until the endpoint serves a valid feed, updates
report the normal HTTP/network failure and retain the installed timetable;
failed requests never advance the successful-check timestamp. Hosting setup
and deployment still need the owner's authorization. There is no hosting
credential in the app, and the preparation tools do not upload anything.

Serve the manifest and immutable payloads on the same exact
HTTPS origin, without redirects. Apply the vendor-neutral header rules in
`hosting/headers.json` using the chosen static host's native configuration.
The manifest is briefly cached; immutable release files retain their URLs.
The phone validates the final origin when the companion exposes responseURL.
Never use a host that redirects payloads to arbitrary origins.

## Review and prepare

1. Review the official directories and notices at least weekly and promptly
   after an announced revision. The app's daily check only finds maintainer
   releases. It does not check operator source freshness.
2. Download sources, compare revision dates and SHA-256 checksums, reconcile
   every changed departure/calendar/direction against the actual source, and
   document unclear or excluded data. Pole coordinates require boarding-pole
   evidence. A successful compiler check alone is not reconciliation.
3. Set a newer `release_version`, source verification/review dates, the
   supported interval and separate `effective_from` date. Retain operator
   schedules and originating service dates through staggered/overnight changes.
4. Create a review JSON report tied to the **exact input file bytes**. It has
   `releaseVersion`, `sourceSha256`, `departureCount`, `reconciled: true`,
   nonempty `reviewer` and ISO `reviewedAt`. Keep the detailed source report with
   the data; this signed-off gate records the maintainer's review, not automatic
   approval of operator information.
5. Run engine, phone, data and storage checks, then prepare the local feed:

```sh
python3 tools/publish_feed.py data/timetable.json \
  --review-report path/to/current-review.json \
  --upcoming path/to/future-timetable.json \
  --review-report path/to/future-review.json \
  --previous path/to/previous-timetable.json \
  --base-url "$APPROVED_TIMETABLE_BASE_URL" \
  --output hosting/public
```

Omit `--upcoming` and its second report when none exists. `--previous` generates
a departure/calendar/metadata diff and enforces a newer correction version.
The tool compiles both snapshots, runs the production phone validators,
matches checksums/dates/versions, rejects an incomplete review and writes an
immutable payload plus review/diff reports. It never rewrites an existing URL
with different bytes. The current manifest always contains the present
snapshot and an optional complete upcoming snapshot; a fresh watch receives
both. The binary's internal CRC covers bytes 16 onward; manifest and transfer
CRC cover the whole payload. SHA-256 also covers the whole payload.

Upload all immutable files first, verify HTTP 200, exact length/checksum,
content type and HTTPS on the controlled origin, then upload `manifest.json`
last. Keep prior payloads available for recovery. Corrections and intentional
rollbacks use a new higher release version. The selected manifest URL is
`https://ewijaya.github.io/kasugabus-pebble/timetables/manifest.json`.
Keep the locally configured endpoint separate from a claim of successful live
publication: verify the deployed feed and actual companion before recording
that deployment as complete. Endpoint changes require
a PBW because the trusted host is fixed in phone code; timetable-only updates
afterward do not require a PBW.

## Controlled feed checks

`node tests/test_phone.js` exercises production validation, settings, Nearby,
obsolete requests, retries and transfer chunk bounds.
`python3 tools/test_feed.py` starts a loopback HTTP server in a temporary
directory and runs the real phone updater against synthetic current/future,
corrupt, incompatible and interrupted feeds. This harness's injected local
transport cannot be enabled by Clay, watch messages or production config.
It neither changes production data nor writes hosting/public. The emulator
bridge can use the same generated feed and AppMessage envelopes; emulator and
physical-phone results are recorded separately in the project test report.

For actual watch storage checks, first build/install the app and start an Emery
emulator. In separate terminals run:

```sh
python3 tools/test_feed.py --serve --real-data --port 8910 \
  --directory /tmp/kasugabus-emulator-feed --current-version 2 \
  --today 2026-10-01 --future-date 2026-10-03
node tests/run_emulator_feed.js http://127.0.0.1:8910 2
```

These files are isolated copies of the baseline with artificial release and
activation dates. Choose a current version higher than the emulator's installed
release. The harness uses the locally installed Pebble Python and existing
emulator websocket, transfers through actual C ACKs, then stops/starts the same
UUID without installing a PBW. It checks complete current/future persistence
and partial replacement recovery. It never changes production config/data.
It uses the same bounded phone sender as the shipped companion and waits for
the actual SDK transport callback before sending the next AppMessage. The
existing pypkjs relay owns watch-push transport acknowledgements; the bridge
observes those messages without sending a duplicate acknowledgement.
This command operates the emulator and should be run after any concurrent UI
inspection finishes. The second test argument is the expected current version.
Set `KASUGABUS_EMU_TRACE=1` for protocol type/session/sequence/status and
transport ACK/NACK diagnostics; trace output omits byte payloads and settings.

A failed check never sets the successful-check timestamp. Daily automatic
attempt throttling belongs to the watch and is recorded when CHECK is queued after phone readiness;
manual checks bypass it but share the one-request/transfer limit. The phone
uses one bounded 15-second fetch per manifest or payload within an attempt.
Transfers wait for every ACK, retry at most three times at two
seconds, and abandon stalled staging. Existing current and valid pending data
remain intact. Future activation and recovery belong to watch storage.
The phone sender permits one transport transaction at a time with at most eight
queued/active messages. A ten-second missing transport callback fails queued
work and blocks overlapping transactions until that callback or a reconnect.
Protocol words preserve their unsigned bits through SDK hosts that expose or
serialize signed Int32 values; byte arrays and packed coordinates are unchanged.

Nearby keeps fixes and coordinates transient, accepts fixes no older than
120 seconds and accuracy at most 100 m, and reports outside coverage when the
nearest verified pole is over 2 km away. Explicit Nearby refresh can request a
fix while startup lookup is off. No location is included in feed traffic.

## Recorded integration evidence

The final rebuilt PBW, SHA-256
`2bddb0b092d51c7cdab6944c56a11bb377f4a97932643ee37541450bfc8bdb09`,
repeated the controlled update checks in
[native-update-workflow-acceptance.log](../artifacts/native-update-workflow-acceptance.log).
Complete current v28/future v29 snapshots transferred in 254 chunks without a
PBW reinstall. Restart preserved both; a replacement interrupted after two
chunks and corrupt/incompatible/interrupted HTTP attempts preserved them and
the successful-check timestamp. Its [sealed audit](../artifacts/final-workflow-build-audit.json)
binds the fresh runtime to these exact bytes. All versions here are isolated
test fixtures; the production and bundled dataset remains v1.

On 2026-10-01, the controlled Emery run in
[`artifacts/native-update-acceptance.log`](../artifacts/native-update-acceptance.log)
installed the isolated complete current v20/future v21 snapshots in 254 chunks,
then restarted the same UUID without reinstalling a PBW. A replacement stopped
after two chunks; restart retained v20 and v21. Corrupt payload, incompatible
manifest and interrupted HTTP attempts also retained those snapshots and the
prior successful-check timestamp. Corrupt/incompatible responses were rejected
by the phone validators before candidate transfer. These artificial versions
are test fixtures, not published timetable releases. The exact PBW was
`466df8dd233cb2886171eb44fe23f1188fd1b3f68bc1d872249be3262a8dff5b`.
The [offline rollover retry](../artifacts/native-rollover-acceptance-retry.log)
activated v21 on 3 October after restarting with Bluetooth disconnected;
the [Restore regression](../artifacts/native-restore-acceptance.log) cancelled
a deferred BEGIN and rejected obsolete downloads even after restart. Its
[native log](../artifacts/native-postreset-acceptance.log) records the actual
deferred cancellation, not merely a completed transfer followed by Restore.

The final harness uses the production updater and bounded sender in Node,
controlled loopback HTTP, the installed SDK relay and actual watch C storage
ACKs. Earlier raw, overlapping harness sends and duplicate bridge/relay ACKs
exposed a firmware inbox overflow and communication stall. The harness now
waits for each SDK transport callback and lets the relay own watch-push ACKs;
it adds no timing sleeps to hide that ordering problem. Offline regression
tests cover the early application-ACK ordering, FIFO bound, NACK, timeout and
reconnect behavior. Four installed-SDK tests additionally exercise real
Int32 encoding/incoming V8 conversion, bridge ACK suppression/transaction
tracking, screenshot fallback/cleanup, and reader termination reporting
without connecting to a watch. The final phone suite has 25 unit scenarios,
five settings integration checks and five real HTTP-feed scenarios.

This evidence does not establish physical-phone HTTPS/XHR, CORS, GPS behavior
or live GitHub Pages headers. The selected production feed is locally
configured and remains unpublished/unverified live. Those companion and
hosting checks must be recorded separately before claiming deployment or
physical-device validation complete.
