# Emery emulator stall after selecting the platform probe

On 2026-10-01, the launcher selected the task-created `kasugabus-platform`
probe at 14:12:49 JST. Its reported initial 262,144-byte persistence write
finished at 14:13:42. Subsequent attempts to start KasugaBus received no
`AppRunState` response; `native-update-neon-final.log` failed before a timetable
transfer. The installed Neon Express build has SHA-256 prefix `4679b90e`.
These timing and installation details come from the coordinating agent.

The bounded read-only GDB inspection completed successfully against the
existing Emery emulator on port 52508, and GDB detached. It made no reset,
register/memory write, build, installation, or physical-watch operation. Only
task metadata and symbol names were inspected; no raw memory, timetable
payloads, message contents, or credentials were saved.

The immediate state supports a firmware flash/logging wait rather than an
executing probe write or a KasugaBus application fault:

- The live CPU task was `IDLE`, in `vPortSuppressTicksAndSleep`. Only IDLE was
  ready; all higher-priority ready lists were empty. No fault handler was active.
- The suspended app task name was `App <kasugabus-`, truncated by the firmware's
  task-name field. Its saved PC was `xQueueGenericReceive`; stack candidates
  included `prv_app_task_main`. The name is consistent with the known probe
  selection, but the truncated name alone cannot establish the complete app
  identity. No `App <KasugaBus>` task was present in the inspected task lists.
- KernelBG's saved PC was also `xQueueGenericReceive`. Its consistent
  symbolized stack candidates were `prv_flash_erase_start`,
  `prv_flash_erase_blocking`, `flash_logging_log_start`, `handle_buffer_sync`,
  and `system_task_main`.
- The flash-erase semaphore had zero available tokens and exactly one waiting
  receiver: KernelBG. Flash logging was enabled.
- NewTimer and KernelMain were waiting in `xQueueGenericReceive`; PULSE was
  also waiting for an event.

The global erase context reported `in_progress=false`, `suspended=false`, and
zero retries, with completion callback `prv_blocking_erase_complete`. This
describes a firmware wait/signal inconsistency around flash/logging, matching
the earlier emulator incidents. It does not prove that a hardware flash erase
was active or identify the precise missing signal. The snapshot contains no
active persistence-writing app stack, busy loop, or executing app fault.

Saved-task stack words were resolved to symbols without replacing live CPU
registers. These are return-address candidates, not a fully unwound saved-task
backtrace; unrelated coincidental symbol matches were excluded from the
conclusion. Task-list traversal was capped at 16 entries per list and stack
candidate scans at 100 words. The inspection command exited successfully in
approximately 0.38 seconds and printed `[Inferior 1 (process 1) detached]`.

The installed tools used were:

```text
/Users/e_wijaya_ap/Library/Application Support/Pebble SDK/SDKs/4.33.1/toolchain/arm-none-eabi/bin/arm-none-eabi-gdb
/Users/e_wijaya_ap/Library/Application Support/Pebble SDK/SDKs/4.33.1/sdk-core/pebble/emery/qemu/emery_sdk_debug.elf
```

The inspection used `target remote 127.0.0.1:52508`, debugger-local convenience
variables for bounded task traversal, symbol-only stack candidates, and an
explicit `detach`. Missing local CMSIS source caused a source-location warning
but did not prevent task or symbol inspection.

This diagnosis does not complete the Neon build's emulator update acceptance.
The coordinating agent may now recover the emulator and repeat that phase.
The physical watch is independent; no physical-watch behavior was assessed by
this inspection.
