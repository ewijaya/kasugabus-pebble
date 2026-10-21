"""Stack-depth analyser on synthetic Thumb-2 disassembly; no build needed."""
import importlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
stack = importlib.import_module("stack_depth")
audit = importlib.import_module("check_release")


def listing(*functions):
    """objdump-style text: (name, [(op, operands), ...])."""
    lines, address = [], 0x1000
    for name, body in functions:
        lines.append(f"{address:08x} <{name}>:")
        for op, args in body:
            lines.append(f"    {address:x}:\t{op}\t{args}")
            address += 2
        lines.append("")
    return "\n".join(lines)


def call(target):
    return ("bl", f"2000 <{target}>")


class ParseTests(unittest.TestCase):
    def test_frame_counts_pushes_vpush_and_sub_before_first_branch(self):
        text = listing(("f", [("push", "{r4, r5, r6, r7, lr}"), ("vpush", "{d8-d9}"), ("subw", "sp, sp, #1052"),
                              call("g"), ("sub", "sp, #8")]), ("g", [("bx", "lr")]))
        functions = stack.parse(text)
        self.assertEqual(functions["f"]["frame"], 20 + 16 + 1052)
        self.assertEqual(functions["f"]["calls"], {"g"})

    def test_register_ranges(self):
        self.assertEqual(stack.register_count("{r4-r11, lr}"), 9)

    def test_tail_call_counts_but_internal_branch_does_not(self):
        text = listing(("f", [("push", "{lr}"), ("b.n", "1004 <f+0x4>"), ("b.w", "3000 <g>")]),
                       ("g", [("push", "{r4, lr}"), ("bx", "lr")]))
        functions = stack.parse(text)
        self.assertEqual(functions["f"]["calls"], {"g"})
        self.assertEqual(stack.deepest(functions, {})[0], 4 + 8)

    def test_indirect_calls_are_reported(self):
        functions = stack.parse(listing(("f", [("push", "{lr}"), ("blx", "r3")])))
        self.assertTrue(functions["f"]["indirect"])

    def test_runtime_sized_frame_is_refused(self):
        functions = stack.parse(listing(("f", [("push", "{r7, lr}"), ("sub", "sp, sp, r3")])))
        with self.assertRaisesRegex(ValueError, "runtime-sized"):
            stack.deepest(functions, {})


class DepthTests(unittest.TestCase):
    def test_deepest_path_wins(self):
        text = listing(("draw", [("push", "{lr}"), call("home"), call("list")]),
                       ("home", [("sub", "sp, #100"), ("bx", "lr")]),
                       ("list", [("sub", "sp, #300"), call("leaf")]),
                       ("leaf", [("push", "{r4, lr}"), ("bx", "lr")]))
        depth, path = stack.deepest(stack.parse(text), {})
        self.assertEqual((depth, path), (4 + 300 + 8, ["draw", "list", "leaf"]))

    def test_undeclared_recursion_is_refused(self):
        text = listing(("a", [("push", "{lr}"), call("b")]), ("b", [("push", "{lr}"), call("a")]))
        with self.assertRaisesRegex(ValueError, "recursion"):
            stack.deepest(stack.parse(text), {})

    def test_declared_recursion_is_unrolled_to_its_bound(self):
        text = listing(("send_next", [("push", "{r4, lr}"), call("failed")]),
                       ("failed", [("push", "{r4, r5, r6, lr}"), call("send_next")]))
        functions = stack.parse(text)
        depth, _ = stack.deepest(functions, {frozenset({"send_next", "failed"}): 3})
        self.assertEqual(depth, 3 * (8 + 16))

    def test_project_declares_the_outbox_retry_cycle(self):
        self.assertEqual(stack.BOUNDED_RECURSION, {frozenset({"send_next", "failed"}): 8})


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.budgets = json.loads((ROOT / "tests/build-budgets.json").read_text())
        self.metrics = {"resources": 30000, "static_ram": 35000, "image_bytes": 35000, "native_binary": 32000,
                        "pbw": 900000, "timetable": 24000}

    def test_limit_sits_between_running_and_faulting_builds(self):
        self.assertLess(3336, self.budgets["max_app_stack_depth_bytes"])
        self.assertLess(self.budgets["max_app_stack_depth_bytes"], 3984)

    def test_stack_depth_is_enforced_when_measured(self):
        audit.check_budgets(dict(self.metrics, stack_depth=self.budgets["max_app_stack_depth_bytes"]), self.budgets)
        with self.assertRaisesRegex(RuntimeError, "stack depth"):
            audit.check_budgets(dict(self.metrics, stack_depth=3984), self.budgets)

    def test_audits_from_before_the_check_still_validate(self):
        audit.check_budgets(self.metrics, self.budgets)


if __name__ == "__main__":
    unittest.main()
