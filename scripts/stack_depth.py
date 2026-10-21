#!/usr/bin/env python3
"""Worst-case app stack depth from the built Emery ELF.

Each function's frame is read from its prologue (pushed registers, VFP
pushes and `sub sp` adjustments before the first branch); calls are `bl`/`blx`
to a named function and tail branches to a function's first instruction. The
deepest path over the call graph is the app-side stack use. Firmware routines
the app calls (text drawing, for example) run below that and are not counted,
so the budget is calibrated against builds known to run and to fault on the
watch, not against the firmware's nominal stack size.

Recursion and runtime-sized frames make the depth unknowable and are refused.
Calls through function pointers (`blx rN`) cannot be followed; their callers
are listed so a reviewer can see what the figure omits.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ELF = ROOT / "build/emery/pebble-app.elf"
TOOLCHAIN = Path.home() / ".local/share/pebble-sdk/SDKs/4.33.1/toolchain/arm-none-eabi/bin"

FUNCTION = re.compile(r"^([0-9a-f]+) <([^>]+)>:$")
INSTRUCTION = re.compile(r"^\s*([0-9a-f]+):\s+(\S+)\s*(.*)$")
TARGET = re.compile(r"\b[0-9a-f]+ <([^>+]+)(\+0x[0-9a-f]+)?>")
BRANCHES = {"b", "b.w", "b.n", "bx", "cbz", "cbnz", "bl", "blx"} | {f"b{c}{w}" for c in
    ("eq", "ne", "cs", "cc", "hs", "lo", "mi", "pl", "vs", "vc", "hi", "ls", "ge", "lt", "gt", "le") for w in ("", ".w", ".n")}


def register_count(operands: str) -> int:
    count = 0
    for part in operands.strip("{} ").split(","):
        part = part.strip()
        if "-" in part:
            low, high = (int(re.sub(r"\D", "", x)) for x in part.split("-"))
            count += high - low + 1
        elif part:
            count += 1
    return count


def parse(disassembly: str):
    """{name: {"frame": bytes, "calls": set, "dynamic": bool, "indirect": bool}}"""
    functions, order, current, prologue = {}, [], None, False
    for line in disassembly.splitlines():
        head = FUNCTION.match(line)
        if head:
            current = head.group(2)
            functions[current] = {"frame": 0, "calls": set(), "dynamic": False, "indirect": False}
            order.append(current)
            prologue = True
            continue
        insn = INSTRUCTION.match(line)
        if not current or not insn:
            continue
        op, args = insn.group(2), insn.group(3).split(";")[0].split("@")[0].strip()
        info = functions[current]
        if prologue:
            if op in ("push", "push.w") or (op.startswith("stmdb") and args.startswith("sp!")):
                info["frame"] += 4 * register_count(args.split("!")[-1].strip(", "))
            elif op == "vpush":
                regs = register_count(args)
                info["frame"] += regs * (8 if "d" in args else 4)
            elif op in ("sub", "sub.w", "subw") and args.startswith("sp,"):
                value = re.search(r"#(\d+)", args)
                if value:
                    info["frame"] += int(value.group(1))
                else:
                    info["dynamic"] = True
        if op in BRANCHES:
            prologue = False
        target = TARGET.search(args)
        if op in ("bl", "blx") and target:
            info["calls"].add(target.group(1))
        elif op == "blx":
            info["indirect"] = True
        elif op in ("b", "b.w", "b.n") and target and not target.group(2) and target.group(1) != current:
            info["calls"].add(target.group(1))  # tail call
        if op in ("sub", "sub.w") and args.startswith("sp,") and not re.search(r"#\d+", args):
            info["dynamic"] = True
    return functions


# Recursion the code relies on, with the bound that makes it finite. Anything
# else recursive is refused. send_next/failed (src/c/main.c): every failed()
# pass either schedules a retry and returns or drops one message from the
# 8-slot outbox queue before calling send_next(), which returns on an empty
# queue, so the pair repeats at most 8 times.
BOUNDED_RECURSION = {frozenset({"send_next", "failed"}): 8}


def deepest(functions, bounded=None):
    """(depth, path) of the deepest call chain; raises on unbounded recursion
    or a runtime-sized frame. Declared cycles are unrolled to their bound."""
    bounded = BOUNDED_RECURSION if bounded is None else bounded
    group_of = {name: group for group in bounded for name in group}
    memo, active, entries = {}, [], {}

    def visit(name):
        group = group_of.get(name)
        inside = any(entries.values())
        if not inside and name in memo:
            return memo[name]
        if group is not None:
            if entries.get((group, name), 0) >= bounded[group]:
                return 0, []  # the declared bound cuts the cycle here
        elif name in active:
            raise ValueError("recursion: " + " -> ".join(active[active.index(name):] + [name]))
        info = functions.get(name)
        if info is None:
            return 0, [name]
        if info["dynamic"]:
            raise ValueError(f"runtime-sized stack frame in {name}")
        active.append(name)
        if group is not None:
            entries[(group, name)] = entries.get((group, name), 0) + 1
        best = (0, [])
        for callee in sorted(info["calls"]):
            depth, path = visit(callee)
            if depth > best[0]:
                best = (depth, path)
        if group is not None:
            entries[(group, name)] -= 1
        active.pop()
        result = (info["frame"] + best[0], [name] + best[1])
        if not inside and group is None:
            memo[name] = result
        return result

    return max((visit(name) for name in sorted(functions)), key=lambda r: r[0])


def analyse(elf: Path = ELF, objdump: Path | None = None):
    objdump = objdump or TOOLCHAIN / "arm-none-eabi-objdump"
    text = subprocess.run([str(objdump), "-d", "--no-show-raw-insn", str(elf)], check=True,
                          capture_output=True, text=True, timeout=60).stdout
    functions = parse(text)
    depth, path = deepest(functions)
    frames = {name: functions[name]["frame"] for name in path}
    return {"stack_depth": depth, "path": path, "frames": frames,
            "indirect_callers": sorted(n for n, f in functions.items() if f["indirect"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("elf", nargs="?", type=Path, default=ELF)
    args = parser.parse_args()
    result = analyse(args.elf)
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as error:
        print("Stack analysis stopped:", error, file=sys.stderr)
        sys.exit(1)
