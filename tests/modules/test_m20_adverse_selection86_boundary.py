"""Row86 boundary pins for the 31 survivor sites of the peer's mutation
campaign (104 generated, 94 compiled and ran, 10 skipped, 63 killed,
31 survived). Tests only; the core blob is unchanged. Each pin states the
exact boundary behavior of the real module; every survivor mutant violates
at least one pin.
"""
from __future__ import annotations

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
    spec = importlib.util.spec_from_file_location("adverse_selection86_boundary_uut", MODULE_PATH)
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

NUM = 10 ** 12
DEN = 10 ** 6


def run(**overrides):
    return m.check_adverse_selection({**BASE, **overrides})


def _signals(n):
    return [{"id": f"s{i:02d}", "class": "adverse" if i % 2 else "favorable"} for i in range(n)]


class ConstantBoundaries(unittest.TestCase):
    # L15: MAX_SIGNALS = 32 (mutants 32->33, 32->31)
    def test_32_signals_accepted(self):
        r = run(signals=_signals(32), actor_signal_ids=["s00", "s01"],
                thresholds={"concentration": "1/2", "pool_gap_margin": "1/4", "min_declared": 1})
        self.assertIn("flags", r)

    def test_33_signals_refused(self):
        with self.assertRaises(ValueError) as ctx:
            run(signals=_signals(33), actor_signal_ids=["s00", "s01"])
        self.assertIn("exceeds", str(ctx.exception))

    # L16: MAX_ACTOR_SIGNALS = 32 (mutants 32->33, 32->31)
    def test_32_actor_signals_accepted(self):
        sigs = _signals(32)
        r = run(signals=sigs, actor_signal_ids=[x["id"] for x in sigs])
        self.assertEqual(r["present_total"], 32)

    def test_33_actor_signals_refused(self):
        sigs = _signals(32)
        with self.assertRaises(ValueError) as ctx:
            run(signals=sigs, actor_signal_ids=[x["id"] for x in sigs] + ["s00"])
        self.assertIn("exceeds", str(ctx.exception))

    # L17/L54: MAX_SOURCE_REF = 200, strict > (mutants 200->201, 200->199, > -> >=)
    def test_source_ref_len_200_accepted(self):
        r = run(source_ref="x" * 200)
        self.assertIn("flags", r)

    def test_source_ref_len_201_refused(self):
        with self.assertRaises(ValueError):
            run(source_ref="x" * 201)

    # L18/L73: MAX_NUM = 10**12, strict > on int path
    # every _rational field is also bounded to [0,1], so the MAX_NUM boundary
    # is pinned by WHICH refusal fires: exactly MAX_NUM passes the bounds
    # check and refuses on range; MAX_NUM+1 refuses on bounds.
    def test_numerator_exactly_max_num_passes_bounds_check(self):
        with self.assertRaises(ValueError) as ctx:
            run(pool={"adverse_share": NUM, "source_ref": "p"})
        self.assertIn("within [0, 1]", str(ctx.exception))

    def test_numerator_max_num_plus_one_refused_on_bounds(self):
        with self.assertRaises(ValueError) as ctx:
            run(pool={"adverse_share": NUM + 1, "source_ref": "p"})
        self.assertIn("exceeds", str(ctx.exception))

    # L19: MAX_DEN = 10**6 (mutants 10->11, 10->9, 6->7, 6->5)
    def test_denominator_exactly_max_den_accepted(self):
        r = run(pool={"adverse_share": f"1/{DEN}", "source_ref": "p"})
        self.assertEqual(r["pool_adverse_share"], f"1/{DEN}")

    def test_denominator_max_den_plus_one_refused(self):
        with self.assertRaises(ValueError):
            run(pool={"adverse_share": f"1/{DEN + 1}", "source_ref": "p"})


class FractionConstruction(unittest.TestCase):
    # L75: int path returns Fraction(v, 1) (mutants 1->2, 1->0)
    def test_int_share_is_exact(self):
        r = run(pool={"adverse_share": 1, "source_ref": "p"},
                actor_signal_ids=["prior_lapse"],
                thresholds={"concentration": 1, "pool_gap_margin": 0, "min_declared": 1})
        self.assertEqual(r["pool_adverse_share"], "1")
        self.assertIn("ADVERSE86-R3", [f["rule_id"] for f in r["flags"]])  # 1 - 1 >= 0

    # L78: plain integer string has implicit denominator 1 (mutant 1->2)
    def test_plain_integer_string_denominator_is_one(self):
        r = run(pool={"adverse_share": "1", "source_ref": "p"})
        self.assertEqual(r["pool_adverse_share"], "1")

    # L81: strict > on both bounds, or-separated (mutants > -> >=, or -> and)
    def test_string_numerator_exactly_max_num_passes_bounds_check(self):
        with self.assertRaises(ValueError) as ctx:
            run(pool={"adverse_share": f"{NUM}/1", "source_ref": "p"})
        self.assertIn("within [0, 1]", str(ctx.exception))

    def test_string_denominator_exactly_max_den_accepted(self):
        r = run(pool={"adverse_share": f"1/{DEN}", "source_ref": "p"})
        self.assertIn("flags", r)

    def test_string_numerator_over_refused_even_with_fine_denominator(self):
        with self.assertRaises(ValueError):
            run(pool={"adverse_share": f"{NUM + 1}/1", "source_ref": "p"})

    def test_string_denominator_over_refused_even_with_fine_numerator(self):
        with self.assertRaises(ValueError):
            run(pool={"adverse_share": f"1/{DEN + 1}", "source_ref": "p"})


class ThresholdInclusivity(unittest.TestCase):
    # L110: signals non-list refuses via or-separation (mutant or -> and)
    def test_non_list_signals_refused(self):
        with self.assertRaises(ValueError) as ctx:
            run(signals="notalist")
        self.assertIn("signals must be a non-empty list", str(ctx.exception))

    # L143: pool_share endpoints 0 and 1 accepted (mutants <= -> <)
    def test_pool_share_zero_accepted(self):
        r = run(pool={"adverse_share": 0, "source_ref": "p"})
        self.assertEqual(r["pool_adverse_share"], "0")

    def test_pool_share_one_accepted(self):
        r = run(pool={"adverse_share": 1, "source_ref": "p"})
        self.assertEqual(r["pool_adverse_share"], "1")

    # L153: margin fraction [0,1]: 0 and 1 accepted, > 1 refused (mutant 1 -> 2)
    def test_margin_zero_accepted(self):
        r = run(thresholds={"concentration": "1/2", "pool_gap_margin": 0, "min_declared": 1})
        self.assertIn("flags", r)

    def test_margin_one_accepted(self):
        r = run(thresholds={"concentration": "1/2", "pool_gap_margin": 1, "min_declared": 1})
        self.assertIn("flags", r)

    def test_margin_over_one_refused(self):
        with self.assertRaises(ValueError):
            run(thresholds={"concentration": "1/2", "pool_gap_margin": 2, "min_declared": 1})

    # L156: bool min_declared refuses via or-separation (mutant or -> and)
    def test_bool_min_declared_refused(self):
        with self.assertRaises(ValueError) as ctx:
            run(thresholds={"concentration": "1/2", "pool_gap_margin": "1/4", "min_declared": True})
        self.assertIn("min_declared must be an integer", str(ctx.exception))

    # L158: min_declared == len(signals) accepted (mutant <= -> <)
    def test_min_declared_equal_to_signal_count_accepted(self):
        r = run(thresholds={"concentration": "1/2", "pool_gap_margin": "1/4", "min_declared": 4})
        self.assertIn("ADVERSE86-R4", [f["rule_id"] for f in r["flags"]])


class ZeroAdverseR2(unittest.TestCase):
    # L169: R2 requires at least one adverse present (mutant >= 1 -> >= 0).
    # A zero-adverse actor with concentration 0 must NOT fire R2; with the
    # mutant, share 0 >= concentration 0 would fire it.
    def test_zero_adverse_actor_never_fires_r2_at_zero_concentration(self):
        r = run(actor_signal_ids=["long_tenure", "verified_income"],
                pool={"adverse_share": "1/4", "source_ref": "p"},
                thresholds={"concentration": 0, "pool_gap_margin": "1/4", "min_declared": 1})
        rule_ids = [f["rule_id"] for f in r["flags"]]
        self.assertNotIn("ADVERSE86-R2", rule_ids)
        self.assertEqual(r["flags_total"], 0)
        self.assertTrue(r["ok"])


if __name__ == "__main__":
    unittest.main()
