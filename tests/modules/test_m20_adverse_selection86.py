"""Row86 [Adverse Selection Detection]: bounded adverse-selection rule flags
over supplied actor/attributes and declared signals.

The unit under test is stdlib-only; it is loaded by file path so the suite
runs in an isolated stdlib+pytest environment. In the integrated repo the
same file is importable as
app.modules.m20_general_cognitive_worker.adverse_selection86.
ADVERSE86_MODULE_PATH overrides the path so mutation runs can point this
suite at a mutated copy.
"""
from __future__ import annotations

import ast
import importlib.util
import os
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(
    os.environ.get(
        "ADVERSE86_MODULE_PATH",
        Path(__file__).resolve().parents[2]
        / "backend" / "app" / "modules" / "m20_general_cognitive_worker" / "adverse_selection86.py",
    )
)


def _load():
    spec = importlib.util.spec_from_file_location("adverse_selection86_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


m = _load()

BASE = {
    "source_ref": "unit-test",
    "signal_basis": "declared_signals",
    "actor": {"id": "actor-1", "source_ref": "intake-1"},
    "signals": [
        {"id": "prior_lapse", "class": "adverse"},
        {"id": "missed_payments", "class": "adverse"},
        {"id": "long_tenure", "class": "favorable"},
        {"id": "verified_income", "class": "favorable"},
    ],
    "actor_signal_ids": ["long_tenure", "verified_income"],
    "pool": {"adverse_share": "1/4", "source_ref": "pool-q3"},
    "thresholds": {"concentration": "1/2", "pool_gap_margin": "1/4", "min_declared": 1},
}


def run(**overrides):
    data = {**BASE, **overrides}
    return m.check_adverse_selection(data)


class CleanPathTests(unittest.TestCase):
    def test_favorable_actor_is_ok_with_no_flags(self):
        r = run()
        self.assertTrue(r["ok"])
        self.assertEqual(r["flags"], [])
        self.assertEqual(r["flags_total"], 0)
        self.assertEqual(r["adverse_present"], 0)
        self.assertEqual(r["favorable_present"], 2)
        self.assertEqual(r["adverse_share"], "0")
        self.assertEqual(r["pool_adverse_share"], "1/4")

    def test_share_is_exact_and_normalized(self):
        r = run(actor_signal_ids=["prior_lapse", "missed_payments", "long_tenure", "verified_income"],
                thresholds={"concentration": "3/4", "pool_gap_margin": "1/2", "min_declared": 1})
        self.assertEqual(r["adverse_share"], "1/2")  # 2/4 normalized, not 0.5

    def test_zero_present_signals_gives_null_share_and_skips_share_rules(self):
        r = run(actor_signal_ids=[], thresholds={"concentration": "0", "pool_gap_margin": "0", "min_declared": 0})
        self.assertIsNone(r["adverse_share"])
        self.assertEqual(r["flags"], [])
        self.assertTrue(r["ok"])


class RuleFlagTests(unittest.TestCase):
    def test_r1_adverse_majority_fires(self):
        r = run(actor_signal_ids=["prior_lapse", "missed_payments", "long_tenure"])
        ids = [f["rule_id"] for f in r["flags"]]
        self.assertIn("ADVERSE86-R1", ids)
        self.assertFalse(r["ok"])

    def test_r1_does_not_fire_on_tie(self):
        r = run(actor_signal_ids=["prior_lapse", "long_tenure"],
                thresholds={"concentration": "3/4", "pool_gap_margin": "1", "min_declared": 1})
        self.assertNotIn("ADVERSE86-R1", [f["rule_id"] for f in r["flags"]])

    def test_r2_concentration_boundary_is_inclusive(self):
        r = run(actor_signal_ids=["prior_lapse", "long_tenure"])  # share 1/2, threshold 1/2
        self.assertIn("ADVERSE86-R2", [f["rule_id"] for f in r["flags"]])

    def test_r2_below_threshold_does_not_fire(self):
        r = run(actor_signal_ids=["prior_lapse", "long_tenure", "verified_income"])  # share 1/3
        self.assertNotIn("ADVERSE86-R2", [f["rule_id"] for f in r["flags"]])

    def test_r3_pool_gap_boundary_is_inclusive(self):
        # share 1/2, pool 1/4, margin 1/4: gap 1/4 >= margin -> fires
        r = run(actor_signal_ids=["prior_lapse", "long_tenure"])
        self.assertIn("ADVERSE86-R3", [f["rule_id"] for f in r["flags"]])

    def test_r3_below_margin_does_not_fire(self):
        r = run(actor_signal_ids=["prior_lapse", "long_tenure", "verified_income"])  # share 1/3, gap 1/12
        self.assertNotIn("ADVERSE86-R3", [f["rule_id"] for f in r["flags"]])

    def test_r4_insufficient_disclosure_fires(self):
        r = run(actor_signal_ids=["long_tenure"], thresholds={"concentration": "1", "pool_gap_margin": "1", "min_declared": 3})
        self.assertEqual([f["rule_id"] for f in r["flags"]], ["ADVERSE86-R4"])

    def test_flag_order_is_rule_id_order(self):
        r = run(actor_signal_ids=["prior_lapse", "missed_payments"],
                thresholds={"concentration": "1/2", "pool_gap_margin": "0", "min_declared": 3})
        self.assertEqual(
            [f["rule_id"] for f in r["flags"]],
            ["ADVERSE86-R1", "ADVERSE86-R2", "ADVERSE86-R3", "ADVERSE86-R4"],
        )

    def test_flag_details_name_the_quantities(self):
        r = run(actor_signal_ids=["prior_lapse", "missed_payments", "long_tenure"])
        r2 = next(f for f in r["flags"] if f["rule_id"] == "ADVERSE86-R2")
        self.assertIn("2/3", r2["detail"])  # exact share in the detail


class RefusalTests(unittest.TestCase):
    def _refusal(self, data):
        with self.assertRaises(ValueError) as ctx:
            m.check_adverse_selection(data)
        self.assertTrue(str(ctx.exception).startswith("ADVERSE86:"), str(ctx.exception))
        return str(ctx.exception)

    def test_unknown_top_level_key(self):
        self._refusal({**BASE, "surprise": 1})

    def test_wrong_basis_refuses(self):
        self._refusal({**BASE, "signal_basis": "observed"})

    def test_row88_shaped_input_refuses(self):
        # no overlap with landed screening: utility-table/menu keys are unknown
        self._refusal({**BASE, "utilities": [], "menus": []})

    def test_protected_trait_signal_id_refuses(self):
        self._refusal({**BASE, "signals": [{"id": "age", "class": "adverse"}]})

    def test_protected_trait_actor_id_refuses(self):
        self._refusal({**BASE, "actor": {"id": "race-1", "source_ref": "x"}})

    def test_invalid_actor_id_refuses(self):
        self._refusal({**BASE, "actor": {"id": "has space", "source_ref": "x"}})

    def test_unknown_actor_signal_id_refuses(self):
        self._refusal({**BASE, "actor_signal_ids": ["prior_lapse", "ghost"]})

    def test_duplicate_actor_signal_id_refuses(self):
        self._refusal({**BASE, "actor_signal_ids": ["prior_lapse", "prior_lapse"]})

    def test_duplicate_signal_id_refuses(self):
        self._refusal({**BASE, "signals": [{"id": "s1", "class": "adverse"}, {"id": "s1", "class": "favorable"}]})

    def test_bad_signal_class_refuses(self):
        self._refusal({**BASE, "signals": [{"id": "s1", "class": "spicy"}]})

    def test_empty_signals_refuses(self):
        self._refusal({**BASE, "signals": []})

    def test_too_many_signals_refuses(self):
        self._refusal({**BASE, "signals": [{"id": f"s{i}", "class": "adverse"} for i in range(33)]})

    def test_float_threshold_refuses(self):
        self._refusal({**BASE, "thresholds": {"concentration": 0.5, "pool_gap_margin": "0", "min_declared": 1}})

    def test_bool_threshold_refuses(self):
        self._refusal({**BASE, "thresholds": {"concentration": True, "pool_gap_margin": "0", "min_declared": 1}})

    def test_threshold_above_one_refuses(self):
        self._refusal({**BASE, "thresholds": {"concentration": "3/2", "pool_gap_margin": "0", "min_declared": 1}})

    def test_pool_share_above_one_refuses(self):
        self._refusal({**BASE, "pool": {"adverse_share": "5/4", "source_ref": "p"}})

    def test_blank_source_ref_refuses(self):
        self._refusal({**BASE, "source_ref": "   "})

    def test_min_declared_out_of_range_refuses(self):
        self._refusal({**BASE, "thresholds": {"concentration": "0", "pool_gap_margin": "0", "min_declared": 5}})

    def test_negative_min_declared_refuses(self):
        self._refusal({**BASE, "thresholds": {"concentration": "0", "pool_gap_margin": "0", "min_declared": -1}})


class ModuleShapeTests(unittest.TestCase):
    def test_module_imports_stdlib_only(self):
        tree = ast.parse(MODULE_PATH.read_text())
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
        roots.discard("__future__")
        self.assertLessEqual(roots, sys.stdlib_module_names)

    def test_limits_and_interpretation_present(self):
        r = run()
        self.assertTrue(any("declared" in line for line in r["limits"]))
        self.assertIn("declared", r["interpretation"])
        self.assertTrue(any("rule" in line for line in r["limits"]))


if __name__ == "__main__":
    unittest.main()
