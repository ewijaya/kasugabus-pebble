# Emery SDK emulator installation stall

Read-only inspection on 2026-10-01 used the installed Pebble SDK 4.33.1
`emery_sdk_debug.elf` and bundled ARM GDB 15.2.90 against port 52508.
GDB was detached after each inspection. No target register or memory writes,
reset, installation, application build, or physical-watch operation occurred.
GDB convenience variables were used only to traverse saved task metadata.

The emulator is stalled in firmware installation/logging, before KasugaBus
starts. The app task is **App <App Fetch>**, not App <KasugaBus>. The live CPU
backtrace is the FreeRTOS idle task in `vPortSuppressTicksAndSleep`; no fault
handler or KasugaBus frame is active.

Saved task PCs and the symbolized return-address sequence establish these
waits. The saved contexts were read without replacing the live CPU registers;
the sequence below is not presented as a fully unwound task backtrace.

| Task | Saved PC / return-address sequence | State |
| --- | --- | --- |
| KernelBG | `xQueueGenericReceive` ← `prv_flash_erase_start` ← `prv_flash_erase_blocking` ← `flash_logging_log_start` ← `handle_buffer_sync` ← `system_task_main` | Waiting indefinitely for the firmware flash-erase semaphore while processing advanced logs. |
| NewTimer | `xLightMutexLock` ← `handle_buffer_sync` ← `pbl_log_advanced` ← `prv_log_internal` ← `accel_cb_new_sample` | Waiting for the advanced-logging mutex. |
| App <App Fetch> | `xQueueGenericReceive` ← `app_event_loop_common` ← `s_main` ← `prv_app_task_main` | Firmware installation/progress app waiting for an event. |
| KernelMain | `xQueueGenericReceive` ← `event_take_timeout` ← `launcher_main_loop` | Waiting in the launcher event loop. |
| PULSE | `xQueueGenericReceive` | Waiting for a console event. |

The erase semaphore has capacity one, zero available messages, and exactly one
receiver: KernelBG. Flash logging is enabled. The firmware's global erase
context reports `in_progress=false`, `suspended=false`, retries zero and a
blocking-erase callback. This does **not** prove that a flash chip operation is
still active; it shows a firmware wait/signal inconsistency around flash/logging.
The exact missing signal or dependency that caused the stall remains unproven.

This closely matches the earlier emulator stall recorded in
`emulator-stall-blocked-stacks.txt`: the same flash/logging chain blocked
KernelBG and other firmware tasks. It is independent of the newly compiled
KBD2 directory code because KasugaBus is not running in this snapshot.

Evidence files contain task metadata, addresses and symbol names, without
application-message contents, credentials or personal text:

- `emulator-install-stall-overview.txt`: live idle backtrace and scheduler lists.
- `emulator-install-stall-saved-contexts.txt`: saved PCs, LRs and stack words.
- `emulator-install-stall-symbols.txt`: offline symbol resolution of return addresses.
- `emulator-install-stall-flash-state.txt`: firmware flash-erase context.
- `emulator-install-stall-semaphore.txt`: empty erase semaphore and KernelBG waiter.

This is emulator diagnostic evidence only. It does not measure the journal
build's startup performance and makes no claim about the physical Time 2.
