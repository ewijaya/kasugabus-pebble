# Production-feed emulator stall — 1 October 2026

The first production observer run timed out waiting for `AppRunStateStop`,
before any native manual CHECK or timetable transfer. The failure is recorded
in [production-feed-emulator-v2.log](production-feed-emulator-v2.log). Separate
host HTTPS checks succeeded; this failed run establishes no installed-worker
download or transfer acceptance.

A bounded independent SDK connection to the existing relay received no
`AppRunStateRequest` or `WatchVersionRequest` replies over three seconds. Its
WebSocket remained connected and its reader thread remained alive. That check
installed no production observer or AppMessage service and sent no clock,
button, reset, installation or preference action.

Read-only GDB inspection used the installed SDK 4.33.1 Emery firmware debug ELF
on the existing debugger port 52508. GDB detached after each successful
inspection. The observed state matches the earlier firmware flash/logging wait
described in [the rollover diagnosis](emulator-rollover-stall-diagnosis.md):

- The current CPU backtrace was FreeRTOS IDLE in
  `vPortSuppressTicksAndSleep`; no active fault handler was observed.
- Flash logging was enabled. The erase context reported `in_progress=false`
  and `suspended=false`.
- The erase semaphore had zero tokens and exactly one waiting receiver,
  `KernelBG`.
- KernelBG's saved-stack symbol candidates included `xQueueGenericReceive`,
  `prv_flash_erase_start`, `prv_flash_erase_blocking`,
  `flash_logging_log_start`, `handle_buffer_sync` and `system_task_main`.
- NewTimer's saved-stack candidates included `xLightMutexLock`,
  `handle_buffer_sync`, `pbl_log_advanced`, `accel_cb_new_sample` and timer
  callback functions.
- `App <KasugaBus>` was present with queue-wait candidates. The snapshot
  contained no evidence of an executing application fault or busy loop.

Task traversal was capped at 16 entries and saved-stack scans at 90 words per
task. Only task names, firmware state, semaphore counts and resolved symbols
were reported. The saved-stack candidates are not a fully unwound task
backtrace. The evidence supports a firmware logging/erase wait inconsistency;
it does not identify its precise missing signal or prove that a flash erase
was active. No raw message contents, credentials or memory dumps were saved.

The inspection made no target register or memory writes, reset, kill,
installation, UI navigation or physical-watch operation. The coordinating
agent subsequently issued `system_reset` through the existing monitor 52509
while retaining flash. The unchanged production observer must be rerun to
establish actual installed-worker HTTPS transfer and persistence.

The production runner's eight offline cases and the four existing installed-SDK
bridge/wire regressions passed. Those tests validate decoding and evidence
guards, not live acceptance. Emulator evidence also remains separate from the
Poco F4 / Time 2 companion path, CORS, GPS and seven-day actual use.

## Recovery and separate download diagnosis

The monitor reset retained flash but the existing relay remained unresponsive.
The lead stopped only the SDK4.33.1 Emery QEMU and relay with the SDK's scoped
SIGTERM helper, backed up the retained flash outside Git, then reinstalled the
same development PBW to restore the SDK transport. No physical watch reset or
emulator data wipe occurred. The next attempt reached the actual native manual
check and fetched the manifest, then failed before BEGIN.

That second failure was traced independently by two agents to repeated reads of
`xhr.response` in the installed SDK's V8 getter bridge: the original extraction
returned an empty array, while one cached response returned all 24,320 offline
fixture bytes exactly. The app now caches that response once. Full binary,
SHA-256/CRC, size, URL and compatibility validation remain unchanged. The new
installed-SDK regression exercises the actual unmodified xhrFetch implementation
with SDK XHR and a bounded offline response. A new PBW/runtime run must establish
that the fix works through the complete production path.
