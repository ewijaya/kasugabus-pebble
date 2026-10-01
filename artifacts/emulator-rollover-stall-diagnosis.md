# Emery emulator stall before rollover verification

On 2026-10-01, the native rollover verifier timed out waiting for
`AppRunStateStop` before it changed the date. The earlier update, navigation and
monotonic profiling phases used PBW SHA-256
`466df8dd233cb2886171eb44fe23f1188fd1b3f68bc1d872249be3262a8dff5b`.
Those profiling results show three starts at 552–558 ms and ordinary button
responses at 10–85 ms. The rollover phase remains incomplete.

Read-only GDB inspection used the installed SDK 4.33.1 Emery firmware debug ELF
against port 52508. The debugger was detached after inspection. No reset,
register/memory write, build, app installation or physical-watch operation was
performed. Only task metadata and symbol names were saved; raw memory and
message contents were not dumped.

The immediate stall is the same firmware flash/logging wait seen in the earlier
emulator incidents:

- The live CPU backtrace is FreeRTOS idle in `vPortSuppressTicksAndSleep`, with
  no fault handler active.
- KernelBG's saved PC is `xQueueGenericReceive`. Its return-address candidates
  include `prv_flash_erase_start`, `prv_flash_erase_blocking`,
  `flash_logging_log_start`, `handle_buffer_sync`, and `system_task_main`.
- The flash-erase semaphore has no available token and exactly one waiting
  receiver: KernelBG.
- NewTimer's saved PC is `xLightMutexLock`. Its return-address candidates include
  `handle_buffer_sync`, `pbl_log_advanced`, `prv_log_internal`,
  `accel_cb_new_sample`, and timer-service functions.
- App <KasugaBus> is present, but its saved PC is `xQueueGenericReceive`.
  KernelMain is also waiting for an event. This snapshot contains no evidence
  of an executing KasugaBus fault or busy loop.

Flash logging is enabled. The global erase context says `in_progress=false`
and `suspended=false`, with retries zero. Therefore the evidence describes a
firmware wait/signal inconsistency around flash/logging, not a proven active
flash erase. The precise missing signal or dependency remains unproven.

`emulator-rollover-stall-symbolized.txt` contains the sanitized diagnostic.
Stack candidates were resolved without replacing live CPU registers; they are
not claimed to be a fully unwound saved-task backtrace. Some scanned words can
coincidentally resolve to unrelated symbols, so only the consistent firmware
flash/logging sequence is used in the conclusion.

This diagnosis does not complete rollover acceptance and makes no claim about
the physical Time 2 or its firmware.
