"""Row 1513 Computational Fluid Dynamics: bounded exact supplied mass-flow balance.

Stdlib only. The module under test is loaded by file path so these tests do not
need the web framework that the package __init__ imports.
"""
import hashlib
import importlib.util
import json
import os
import random
import unittest
from fractions import Fraction

_CORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend", "app",
                     "modules", "m20_general_cognitive_worker", "computational_fluid_dynamics1513.py")


def load():
    spec = importlib.util.spec_from_file_location("cfd1513_under_test", _CORE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = load()
PREFIX = "COMPUT1513:"
DENOM_FLOOR = Fraction(1, 10 ** 12)  # cluster parity: max(abs(total_in), 1e-12)


def port(pid, direction, rate):
    return {"id": pid, "direction": direction, "mass_flow_kg_per_s": rate}


def fixture():
    return {
        "domain": "cooling-jacket",
        "turbulence_model": "k-epsilon",
        "boundary_conditions": ["inlet", "outlet", "wall"],
        "ports": [
            port("in-a", "in", "2.5"),
            port("out-a", "out", "2.4"),
            port("in-b", "in", "1.5"),
            port("out-b", "out", "1.5"),
        ],
        "closure_tolerance_percent": "5",
    }


def refusal(data):
    try:
        M.evaluate_flow_balance(data)
    except M.CfdBalanceRefusal as exc:
        return exc
    raise AssertionError("expected CfdBalanceRefusal")


def exact_dec(fr):
    """Test-side rendering oracle mirroring the contract: terminating decimals as
    decimal strings, otherwise 'num/den'."""
    fr = Fraction(fr)
    den = fr.denominator
    for p in (2, 5):
        while den % p == 0:
            den //= p
    if den != 1:
        return f"{fr.numerator}/{fr.denominator}"
    if fr.denominator == 1:
        return str(fr.numerator)
    num, d, scale = fr.numerator, fr.denominator, 0
    while d != 1:
        if d % 10 == 0:
            d //= 10
            scale += 1
        elif d % 2 == 0:
            d //= 2
            scale += 1
            num *= 5
        else:
            d //= 5
            scale += 1
            num *= 2
    s = str(abs(num)).rjust(scale + 1, "0")
    s = s[:-scale] + "." + s[-scale:]
    s = s.rstrip("0").rstrip(".")
    return ("-" if num < 0 else "") + s


def oracle(data):
    ports = data["ports"]
    tin = sum(Fraction(str(p["mass_flow_kg_per_s"])) for p in ports if p["direction"] == "in")
    tout = sum(Fraction(str(p["mass_flow_kg_per_s"])) for p in ports if p["direction"] == "out")
    denom = max(abs(tin), DENOM_FLOOR)
    imb = abs(tin - tout) / denom * 100
    tol = Fraction(str(data.get("closure_tolerance_percent", "5")))
    return {"mass_in": tin, "mass_out": tout, "imbalance": imb, "balanced": imb <= tol}


class TestKnownAnswer(unittest.TestCase):
    def test_evaluation(self):
        r = M.evaluate_flow_balance(fixture())
        self.assertEqual(r["row"], 1513)
        self.assertEqual(r["capability"], "Computational Fluid Dynamics")
        self.assertEqual(r["scope"], "supplied_mass_flow_balance")
        self.assertEqual(r["status"], "evaluation_complete")
        self.assertEqual(r["totals"]["mass_in_kg_per_s"], "4")
        self.assertEqual(r["totals"]["mass_out_kg_per_s"], "3.9")
        self.assertEqual(r["mass_imbalance_percent"], "2.5")
        self.assertEqual(r["closure_tolerance_percent"], "5")
        self.assertTrue(r["balanced_to_tolerance"])
        self.assertFalse(r["provenance"]["solver_run_claimed"])
        self.assertEqual(r["largest_inflow"], {"id": "in-a", "share_percent": "62.5"})
        self.assertEqual(r["largest_outflow"], {"id": "out-a", "share_percent": "800/13"})
        self.assertEqual([p["id"] for p in r["port_rows"]], ["in-a", "out-a", "in-b", "out-b"])
        self.assertEqual(r["port_rows"][0]["share_of_direction_percent"], "62.5")
        self.assertEqual(r["summary"]["port_count"], 4)
        self.assertEqual(r["summary"]["inflow_count"], 2)
        self.assertEqual(r["summary"]["outflow_count"], 2)


class TestSemantics(unittest.TestCase):
    def test_oracle_corpus(self):
        rng = random.Random(1513)
        corpus = [fixture()]
        for _ in range(6):
            n_in, n_out = rng.randint(1, 4), rng.randint(1, 4)
            ports = []
            for i in range(n_in):
                ports.append(port(f"i{i}", "in", f"{rng.randint(0, 900)}.{rng.randint(0, 99):02d}"))
            for i in range(n_out):
                ports.append(port(f"o{i}", "out", f"{rng.randint(0, 900)}.{rng.randint(0, 99):02d}"))
            corpus.append({"ports": ports,
                           "closure_tolerance_percent": f"{rng.randint(1, 50)}"})
        for data in corpus:
            r = M.evaluate_flow_balance(data)
            exp = oracle(data)
            self.assertEqual(Fraction(r["totals"]["mass_in_kg_per_s"]), exp["mass_in"])
            self.assertEqual(Fraction(r["totals"]["mass_out_kg_per_s"]), exp["mass_out"])
            self.assertEqual(Fraction(r["mass_imbalance_percent"]), exp["imbalance"])
            self.assertEqual(r["balanced_to_tolerance"], exp["balanced"])

    def test_permutation_independence_of_totals(self):
        base = fixture()
        rng = random.Random(7)
        for _ in range(25):
            d = dict(base)
            d["ports"] = list(base["ports"])
            rng.shuffle(d["ports"])
            r = M.evaluate_flow_balance(d)
            self.assertEqual(r["totals"]["mass_in_kg_per_s"], "4")
            self.assertEqual(r["mass_imbalance_percent"], "2.5")

    def test_zero_inflow_denominator_floor(self):
        # cluster parity: denominator max(abs(total_in), 1e-12)
        r = M.evaluate_flow_balance({"ports": [port("z", "in", "0"), port("o", "out", "0.000000000005")]})
        self.assertEqual(Fraction(r["mass_imbalance_percent"]), Fraction(500))
        r2 = M.evaluate_flow_balance({"ports": [port("z", "in", "0"), port("o", "out", "0")]})
        self.assertEqual(r2["mass_imbalance_percent"], "0")
        self.assertTrue(r2["balanced_to_tolerance"])

    def test_largest_tie_first_declared(self):
        # Pin found by mutation battery (M1513-13 residual): equal shares resolve
        # to the first-declared port.
        r = M.evaluate_flow_balance({"ports": [port("a", "in", "1"), port("b", "in", "1"),
                                               port("o", "out", "2")]})
        self.assertEqual(r["largest_inflow"], {"id": "a", "share_percent": "50"})
        self.assertEqual(r["largest_outflow"], {"id": "o", "share_percent": "100"})

    def test_tolerance_edge_inclusive(self):
        d = fixture()
        d["closure_tolerance_percent"] = "2.5"
        self.assertTrue(M.evaluate_flow_balance(d)["balanced_to_tolerance"])
        d["closure_tolerance_percent"] = "2.4999999"
        self.assertFalse(M.evaluate_flow_balance(d)["balanced_to_tolerance"])

    def test_exact_rendering(self):
        self.assertEqual(exact_dec(Fraction(5, 8)), "0.625")
        self.assertEqual(exact_dec(Fraction(4, 1)), "4")
        r = M.evaluate_flow_balance({"ports": [port("a", "in", "1"), port("b", "in", "2"),
                                               port("o", "out", "3")]})
        shares = {p["id"]: p["share_of_direction_percent"] for p in r["port_rows"] if p["direction"] == "in"}
        self.assertEqual(shares["a"], "100/3")
        self.assertEqual(shares["b"], "200/3")
        self.assertEqual(r["largest_inflow"], {"id": "b", "share_percent": "200/3"})


class TestRefusals(unittest.TestCase):
    def test_shape_details(self):
        for bad, why in [
            (None, "input must be an object"),
            ({"ports": [], "extra": 1}, "unknown key at input"),
            ({"ports": "x"}, "ports must be a list of 1..64 port objects"),
            ({"ports": []}, "ports must be a list of 1..64 port objects"),
            ({"ports": [["x"]]}, "ports[0] must be an object"),
        ]:
            with self.subTest(why=why):
                self.assertEqual(str(refusal(bad)), PREFIX + "invalid_input: " + why)

    def test_port_problems(self):
        self.assertEqual(str(refusal({"ports": [port("a", "in", "1"), port("a", "out", "1")]})),
                         PREFIX + "invalid_input: duplicate id in ports")
        self.assertEqual(str(refusal({"ports": [port("a", "sideways", "1")]})),
                         PREFIX + "invalid_input: ports[0].direction must be 'in' or 'out'")
        self.assertEqual(str(refusal({"ports": [port("a", "in", "-1")]})),
                         PREFIX + "invalid_input: ports[0].mass_flow_kg_per_s must be nonnegative")
        self.assertEqual(str(refusal({"ports": [port("a", "in", True)]})),
                         PREFIX + "invalid_input: ports[0].mass_flow_kg_per_s must be a finite number or numeric string")
        self.assertEqual(str(refusal({"ports": [port("a", "in", "abc")]})),
                         PREFIX + "invalid_input: ports[0].mass_flow_kg_per_s must be a finite number or numeric string")
        self.assertEqual(str(refusal({"ports": [port("a", "in", float("inf"))]})),
                         PREFIX + "invalid_input: ports[0].mass_flow_kg_per_s must be a finite number or numeric string")
        self.assertEqual(str(refusal({"ports": [{"id": "a", "direction": "in"}]})),
                         PREFIX + "invalid_input: ports[0].mass_flow_kg_per_s is required")
        self.assertEqual(str(refusal({"ports": [{"direction": "in", "mass_flow_kg_per_s": "1"}]})),
                         PREFIX + "invalid_input: ports[0].id requires a non-empty string")

    def test_tolerance_problems(self):
        self.assertEqual(str(refusal({"ports": [port("a", "in", "1")], "closure_tolerance_percent": "-1"})),
                         PREFIX + "invalid_input: closure_tolerance_percent must be within 0..100")
        self.assertEqual(str(refusal({"ports": [port("a", "in", "1")], "closure_tolerance_percent": "100.1"})),
                         PREFIX + "invalid_input: closure_tolerance_percent must be within 0..100")
        self.assertEqual(str(refusal({"ports": [port("a", "in", "1")], "closure_tolerance_percent": "loose"})),
                         PREFIX + "invalid_input: closure_tolerance_percent must be a finite number or numeric string")

    def test_prefix_exact(self):
        exc = refusal({"ports": []})
        self.assertEqual(exc.code, "COMPUT1513:invalid_input")
        self.assertTrue(str(exc).startswith(PREFIX))


class TestBounds(unittest.TestCase):
    def test_port_count_64_65(self):
        ok = [port(f"p{i}", "in" if i % 2 == 0 else "out", "1") for i in range(64)]
        self.assertEqual(M.evaluate_flow_balance({"ports": ok})["summary"]["port_count"], 64)
        exc = refusal({"ports": ok + [port("p64", "in", "1")]})
        self.assertEqual(str(exc), PREFIX + "resource_limit: ports count 65 exceeds limit 64")

    def test_bc_count_64_65(self):
        ok = [f"bc{i}" for i in range(64)]
        r = M.evaluate_flow_balance({"ports": [port("a", "in", "1")], "boundary_conditions": ok})
        self.assertEqual(len(r["boundary_conditions"]), 64)
        exc = refusal({"ports": [port("a", "in", "1")], "boundary_conditions": ok + ["bc64"]})
        self.assertEqual(str(exc), PREFIX + "resource_limit: boundary_conditions count 65 exceeds limit 64")

    def test_id_length_128_129(self):
        ok = port("a" * 128, "in", "1")
        self.assertEqual(M.evaluate_flow_balance({"ports": [ok]})["port_rows"][0]["id"], "a" * 128)
        exc = refusal({"ports": [port("a" * 129, "in", "1")]})
        self.assertEqual(str(exc), PREFIX + "resource_limit: ports[0].id is 129 characters, limit is 128")

    def test_string_length_256_257(self):
        ok = "d" * 256
        r = M.evaluate_flow_balance({"ports": [port("a", "in", "1")], "domain": ok})
        self.assertEqual(r["domain"], ok)
        exc = refusal({"ports": [port("a", "in", "1")], "domain": "d" * 257})
        self.assertEqual(str(exc), PREFIX + "resource_limit: domain is 257 characters, limit is 256")


class TestReceipt(unittest.TestCase):
    def test_full_receipt_boundary_and_provenance(self):
        data = fixture()
        r = M.evaluate_flow_balance(data)
        self.assertEqual(r["boundary"]["requires_engineer_review"], True)
        self.assertEqual(r["boundary"]["not_a_simulation_run"], True)
        self.assertEqual(r["boundary"]["no_machinery_control"], True)
        self.assertTrue(r["human_review_required"])
        self.assertIn("Qualified engineers", r["boundary"]["text"])
        self.assertEqual(r["provenance"]["declarations_not_simulation"], True)
        self.assertEqual(r["provenance"]["solver_run_claimed"], False)
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        self.assertEqual(r["provenance"]["input_sha256"], hashlib.sha256(canonical.encode()).hexdigest())
        self.assertEqual(r["input_trace"], [{"port_id": "in-a", "input_index": 0},
                                            {"port_id": "out-a", "input_index": 1},
                                            {"port_id": "in-b", "input_index": 2},
                                            {"port_id": "out-b", "input_index": 3}])
        self.assertEqual(r["domain"], "cooling-jacket")
        self.assertEqual(r["turbulence_model"], "k-epsilon")
        self.assertEqual(r["boundary_conditions"], ["inlet", "outlet", "wall"])

    def test_optional_fields_absent(self):
        r = M.evaluate_flow_balance({"ports": [port("a", "in", "1")]})
        self.assertIsNone(r["domain"])
        self.assertIsNone(r["turbulence_model"])
        self.assertEqual(r["boundary_conditions"], [])
        self.assertEqual(r["closure_tolerance_percent"], "5")
        self.assertEqual(r["largest_outflow"], None)


if __name__ == "__main__":
    unittest.main()
