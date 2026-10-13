"""Group 80 math engine tests. Hermetic, stdlib unittest.

Covers every solver kind with independently known answers, the refusal
bounds, and tamper cases proving verify() rejects altered results.
"""
import copy
import importlib.util
import pathlib
import sys
import unittest

_P = pathlib.Path(__file__).resolve().parents[2] / \
    "backend/app/modules/m20_general_cognitive_worker/math_engine.py"
_spec = importlib.util.spec_from_file_location("math_engine_g80", _P)
m = importlib.util.module_from_spec(_spec)
sys.modules["math_engine_g80"] = m
_spec.loader.exec_module(m)


class LinearSystems(unittest.TestCase):
    def test_unique_3x3(self):
        r = m.solve({"kind": "linear_system",
                     "matrix": [[1, 1, 1], [0, 2, 5], [2, 5, -1]],
                     "vector": [6, -4, 27]})
        self.assertEqual(r["status"], "unique")
        self.assertEqual(r["solution"], ["5", "3", "-2"])
        self.assertTrue(r["verification"]["verified"])

    def test_fractional_solution(self):
        r = m.solve({"kind": "linear_system", "matrix": [[2, 1], [1, 3]],
                     "vector": [5, 10]})
        self.assertEqual(r["solution"], ["1", "3"])
        self.assertTrue(r["verification"]["verified"])

    def test_no_solution(self):
        r = m.solve({"kind": "linear_system", "matrix": [[1, 1], [2, 2]],
                     "vector": [3, 7]})
        self.assertEqual(r["status"], "no_solution")
        self.assertTrue(r["verification"]["verified"])

    def test_infinite_solutions(self):
        r = m.solve({"kind": "linear_system", "matrix": [[1, 1], [2, 2]],
                     "vector": [3, 6]})
        self.assertEqual(r["status"], "infinite_solutions")
        self.assertEqual(r["free_variables"], 1)
        self.assertTrue(r["verification"]["verified"])

    def test_size_refusal(self):
        with self.assertRaises(ValueError):
            m.solve({"kind": "linear_system", "matrix": [[1] * 9] * 9,
                     "vector": [1] * 9})


class Quadratics(unittest.TestCase):
    def test_rational_roots(self):
        r = m.solve({"kind": "quadratic", "a": 1, "b": -5, "c": 6})
        self.assertEqual(r["status"], "two_real_roots")
        self.assertEqual(sorted(r["roots"]), ["2", "3"])
        self.assertTrue(r["verification"]["verified"])

    def test_surd_roots_exact(self):
        r = m.solve({"kind": "quadratic", "a": 1, "b": 0, "c": -2})
        self.assertIn("sqrt(2)", r["roots"][0])
        self.assertTrue(r["verification"]["verified"])

    def test_repeated_root(self):
        r = m.solve({"kind": "quadratic", "a": 2, "b": -4, "c": 2})
        self.assertEqual(r["status"], "repeated_root")
        self.assertEqual(r["roots"], ["1"])
        self.assertTrue(r["verification"]["verified"])

    def test_no_real_roots(self):
        r = m.solve({"kind": "quadratic", "a": 3, "b": 1, "c": 1})
        self.assertEqual(r["status"], "no_real_roots")
        self.assertTrue(r["verification"]["verified"])

    def test_leading_coefficient_refusal(self):
        with self.assertRaises(ValueError):
            m.solve({"kind": "quadratic", "a": 0, "b": 1, "c": 1})


class Polynomials(unittest.TestCase):
    def test_derivative(self):
        r = m.solve({"kind": "polynomial_derivative", "coefficients": [1, 0, 3]})
        self.assertEqual([str(v) for v in r["coefficients_out"]], ["0", "6"])
        self.assertTrue(r["verification"]["verified"])

    def test_integral(self):
        r = m.solve({"kind": "polynomial_integral", "coefficients": [0, 2, 3]})
        self.assertEqual([str(v) for v in r["coefficients_out"]], ["0", "0", "1", "1"])
        self.assertTrue(r["verification"]["verified"])

    def test_eval(self):
        self.assertEqual(m.poly_eval([1, 2, 3], 2), 17)


class NumberTheory(unittest.TestCase):
    def test_diophantine_solvable(self):
        r = m.solve({"kind": "diophantine", "a": 3, "b": 5, "c": 1})
        x, y = r["particular"]
        self.assertEqual(3 * x + 5 * y, 1)
        self.assertTrue(r["verification"]["verified"])

    def test_diophantine_unsolvable(self):
        r = m.solve({"kind": "diophantine", "a": 6, "b": 3, "c": 7})
        self.assertEqual(r["status"], "no_solution")
        self.assertTrue(r["verification"]["verified"])

    def test_primality_true(self):
        r = m.solve({"kind": "is_prime", "n": 999999999989})
        self.assertTrue(r["prime"])
        self.assertTrue(r["verification"]["verified"])

    def test_primality_composite(self):
        r = m.solve({"kind": "is_prime", "n": 999999999989 * 999983})  # 9.99e17, semiprime
        self.assertFalse(r["prime"])
        self.assertTrue(r["verification"]["verified"])

    def test_factor_semiprime(self):
        r = m.solve({"kind": "factor", "n": 1000036000099})
        self.assertEqual(r["factors"], [1000003, 1000033])
        self.assertTrue(r["verification"]["verified"])

    def test_factor_with_small_primes(self):
        r = m.solve({"kind": "factor", "n": 2 * 2 * 3 * 101 * 103})
        self.assertEqual(r["factors"], [2, 2, 3, 101, 103])
        self.assertTrue(r["verification"]["verified"])

    def test_crt(self):
        r = m.solve({"kind": "crt", "remainders": [2, 3, 2], "moduli": [3, 5, 7]})
        self.assertEqual(r["solution"], 23)
        self.assertTrue(r["verification"]["verified"])

    def test_crt_non_coprime_refusal(self):
        with self.assertRaises(ValueError):
            m.solve({"kind": "crt", "remainders": [1, 2], "moduli": [4, 6]})


class Combinatorics(unittest.TestCase):
    def test_choose(self):
        r = m.solve({"kind": "combinatorics", "op": "choose", "n": 10, "k": 3})
        self.assertEqual(r["result"], 120)
        self.assertTrue(r["verification"]["verified"])

    def test_permute(self):
        r = m.solve({"kind": "combinatorics", "op": "permute", "n": 10, "k": 3})
        self.assertEqual(r["result"], 720)
        self.assertTrue(r["verification"]["verified"])

    def test_derangements(self):
        r = m.solve({"kind": "combinatorics", "op": "derangements", "n": 4})
        self.assertEqual(r["result"], 9)
        self.assertTrue(r["verification"]["verified"])

    def test_catalan(self):
        r = m.solve({"kind": "combinatorics", "op": "catalan", "n": 5})
        self.assertEqual(r["result"], 42)
        self.assertTrue(r["verification"]["verified"])

    def test_fibonacci(self):
        r = m.solve({"kind": "combinatorics", "op": "fibonacci", "n": 10})
        self.assertEqual(r["result"], 55)
        self.assertTrue(r["verification"]["verified"])

    def test_result_bound_refusal(self):
        with self.assertRaises(ValueError):
            m.solve({"kind": "combinatorics", "op": "fibonacci", "n": 10**5})


class SequencesStatsExpressions(unittest.TestCase):
    def test_arithmetic_sequence(self):
        r = m.solve({"kind": "sequence", "sequence_kind": "arithmetic",
                     "a1": 1, "step": 2, "n": 100})
        self.assertEqual(r["nth"], "199")
        self.assertEqual(r["sum_first_n"], "10000")
        self.assertTrue(r["verification"]["verified"])

    def test_geometric_sequence(self):
        r = m.solve({"kind": "sequence", "sequence_kind": "geometric",
                     "a1": 3, "step": 2, "n": 5})
        self.assertEqual(r["nth"], "48")
        self.assertEqual(r["sum_first_n"], "93")
        self.assertTrue(r["verification"]["verified"])

    def test_statistics_exact(self):
        r = m.solve({"kind": "statistics", "values": [1, "3/2", 2, 5]})
        self.assertEqual(r["mean"], "19/8")
        self.assertEqual(r["median"], "7/4")
        self.assertEqual(r["population_variance"], "155/64")
        self.assertTrue(r["verification"]["verified"])

    def test_expression(self):
        r = m.solve({"kind": "expression", "source": "(2+3**2)*4 - 10//3"})
        self.assertEqual(r["value"], "41")
        self.assertTrue(r["verification"]["verified"])

    def test_expression_right_assoc_power(self):
        r = m.solve({"kind": "expression", "source": "2**3**2"})
        self.assertEqual(r["value"], "512")
        self.assertTrue(r["verification"]["verified"])

    def test_expression_name_refusal(self):
        with self.assertRaises(ValueError):
            m.solve({"kind": "expression", "source": "__import__('os')"})

    def test_expression_zero_division(self):
        with self.assertRaises(ValueError):
            m.solve({"kind": "expression", "source": "1/0"})

    def test_expression_pow_bound(self):
        with self.assertRaises(ValueError):
            m.solve({"kind": "expression", "source": "2**100"})


class VerificationIntegrity(unittest.TestCase):
    """A result whose numbers were altered must fail verification."""

    def test_tamper_crt(self):
        task = {"kind": "crt", "remainders": [2, 3, 2], "moduli": [3, 5, 7]}
        core = m.solve_crt(task["remainders"], task["moduli"])
        core["solution"] += 1
        self.assertFalse(m.verify(task, core)["verified"])

    def test_tamper_quadratic_root(self):
        task = {"kind": "quadratic", "a": 1, "b": -5, "c": 6}
        core = m.solve_quadratic(1, -5, 6)
        core["_roots_exact"][0] = m.Surd(9)
        self.assertFalse(m.verify(task, core)["verified"])

    def test_tamper_linear_system(self):
        task = {"kind": "linear_system", "matrix": [[2, 1], [1, 3]], "vector": [5, 10]}
        core = m.solve_linear_system(task["matrix"], task["vector"])
        core["solution"] = ["1", "4"]
        self.assertFalse(m.verify(task, core)["verified"])

    def test_tamper_factor(self):
        task = {"kind": "factor", "n": 1000036000099}
        core = m.factor(task["n"])
        core["factors"] = [1000003, 1000037]
        self.assertFalse(m.verify(task, core)["verified"])

    def test_tamper_expression(self):
        task = {"kind": "expression", "source": "2+2"}
        core = m.evaluate_expression(task["source"])
        core["value"] = "5"
        self.assertFalse(m.verify(task, core)["verified"])

    def test_solver_never_returns_unverified_solved(self):
        for task in [
            {"kind": "linear_system", "matrix": [[1, 2], [3, 4]], "vector": [5, 11]},
            {"kind": "quadratic", "a": 1, "b": -3, "c": 2},
            {"kind": "diophantine", "a": 35, "b": 15, "c": 5},
            {"kind": "factor", "n": 99991 * 999983},
            {"kind": "crt", "remainders": [1, 4], "moduli": [7, 9]},
            {"kind": "combinatorics", "op": "choose", "n": 50, "k": 25},
            {"kind": "sequence", "sequence_kind": "arithmetic", "a1": 7, "step": -3, "n": 40},
            {"kind": "statistics", "values": [4, 8, 15, 16, 23, 42]},
            {"kind": "expression", "source": "7*(6+1)"},
            {"kind": "polynomial_derivative", "coefficients": [5, 4, 3, 2, 1]},
            {"kind": "polynomial_integral", "coefficients": [5, 4, 3]},
            {"kind": "is_prime", "n": 32416190071},
        ]:
            r = m.solve(task)
            self.assertTrue(r["verification"]["verified"], task)
            self.assertNotEqual(r["status"], "verification_failed", task)


class AuditorProbes(unittest.TestCase):
    """Regression tests from the independent auditor's probe list."""

    def test_crt_replaced_constraints_fail(self):
        task = {"kind": "crt", "remainders": [2, 3, 2], "moduli": [3, 5, 7]}
        r = m.solve(task)
        r.update(solution=0, congruences=[[0, 1]], modulus=1)
        self.assertFalse(m.verify(task, r)["verified"])

    def test_quadratic_display_and_status_tamper_fail(self):
        task = {"kind": "quadratic", "a": 1, "b": -5, "c": 6}
        r = m.solve_quadratic(1, -5, 6)
        r["roots"] = ["999", "999"]
        self.assertFalse(m.verify(task, r)["verified"])
        r = m.solve_quadratic(1, -5, 6)
        r["status"] = "no_real_roots"
        self.assertFalse(m.verify(task, r)["verified"])

    def test_stats_field_tamper_fails(self):
        task = {"kind": "statistics", "values": [1, 2, 9]}
        r = m.solve(task)
        r.update(median="999", count=999, min="999", max="999")
        self.assertFalse(m.verify(task, r)["verified"])

    def test_combinatorics_other_task_fields_fail(self):
        task = {"kind": "combinatorics", "op": "choose", "n": 10, "k": 3}
        r = m.solve(task)
        r.update(n=3, k=1, result=3)
        self.assertFalse(m.verify(task, r)["verified"])

    def test_diophantine_general_tamper_fails(self):
        task = {"kind": "diophantine", "a": 3, "b": 5, "c": 1}
        r = m.solve(task)
        r["general"] = ["x=0", "y=0"]
        self.assertFalse(m.verify(task, r)["verified"])

    def test_unary_expressions(self):
        cases = {"1*-2": "-2", "+2": "2", "2+-3": "-1", "1--2": "3", "-2**2": "-4"}
        for src, expected in cases.items():
            r = m.solve({"kind": "expression", "source": src})
            self.assertEqual(r["value"], expected, src)
            self.assertTrue(r["verification"]["verified"], src)
        with self.assertRaises(ValueError):
            m.solve({"kind": "expression", "source": "2**-1"})

    def test_non_integer_nk_refused(self):
        with self.assertRaises(ValueError):
            m.solve({"kind": "combinatorics", "op": "choose", "n": "7/2", "k": "3/2"})

    def test_catalan_bound_refusal(self):
        with self.assertRaises(ValueError):
            m.solve({"kind": "combinatorics", "op": "catalan", "n": 500})

    def test_derangements_20_verifies(self):
        r = m.solve({"kind": "combinatorics", "op": "derangements", "n": 20})
        self.assertEqual(r["result"], 895014631192902121)
        self.assertTrue(r["verification"]["verified"])

    def test_crt_large_coprime_moduli(self):
        r = m.solve({"kind": "crt", "remainders": [0, 1, 2],
                     "moduli": [1000000007, 1000000009, 1000000033]})
        self.assertEqual(r["status"], "solved")
        self.assertTrue(r["verification"]["verified"])

    def test_all_zero_matrix_ranks(self):
        r = m.solve({"kind": "linear_system",
                     "matrix": [[0, 0, 0]] * 3, "vector": [1, 2, 3]})
        self.assertEqual(r["status"], "no_solution")
        self.assertEqual(r["rank_coefficients"], 0)
        self.assertEqual(r["rank_augmented"], 1)
        self.assertTrue(r["verification"]["verified"])


class ResourceBounds(unittest.TestCase):
    def test_power_bomb_refused_fast(self):
        import time
        bomb = "10" + "**64" * 40  # nested powers, each within exponent bound
        start = time.monotonic()
        with self.assertRaises(ValueError):
            m.solve({"kind": "expression", "source": bomb})
        self.assertLess(time.monotonic() - start, 5)

    def test_geometric_sequence_bomb_refused(self):
        with self.assertRaises(ValueError):
            m.solve({"kind": "sequence", "sequence_kind": "geometric",
                     "a1": 1, "step": 2, "n": 1000000})

    def test_factor_budget_exists_and_semiprime_completes(self):
        self.assertEqual(m.RHO_ITERATION_BUDGET > 0, True)
        r = m.solve({"kind": "factor", "n": 999999937 * 999999929})
        self.assertEqual(len(r["factors"]), 2)
        self.assertTrue(r["verification"]["verified"])

    def test_squarefree_large_prime_squared(self):
        # rest = p**2 with p > 1e6: kernel must exclude p
        self.assertEqual(m._squarefree(1000003 * 1000003 * 2), 2)
        self.assertEqual(m._squarefree(1000003 * 1000033), 1000003 * 1000033)


class AuditorProbesV2(unittest.TestCase):
    """Auditor-7 round-2 probes: binding, status uniformity, re-verifiability,
    and verify()-side resource bounds."""

    def test_choice_large_k_kept_original(self):
        r = m.solve({'kind': 'combinatorics', 'op': 'choose', 'n': 10, 'k': 8})
        self.assertEqual(r['k'], 8)  # task k, never the normalized min(k, n-k)
        self.assertEqual(r['result'], 45)
        self.assertTrue(r['verification']['verified'])

    def test_no_real_roots_requires_empty_roots(self):
        t = {'kind': 'quadratic', 'a': 1, 'b': 0, 'c': 1}
        r = m.solve(t)
        self.assertEqual(r['status'], 'no_real_roots')
        r2 = copy.deepcopy(r)
        r2['roots'] = ['999']
        self.assertFalse(m.verify(t, r2)['verified'])

    def test_status_bound_uniformly(self):
        tasks = [
            {'kind': 'expression', 'source': '2+3*4'},
            {'kind': 'statistics', 'values': [1, 2, 9]},
            {'kind': 'crt', 'remainders': [2, 3, 2], 'moduli': [3, 5, 7]},
            {'kind': 'factor', 'n': 360},
            {'kind': 'is_prime', 'n': 97},
            {'kind': 'combinatorics', 'op': 'choose', 'n': 10, 'k': 3},
            {'kind': 'sequence', 'sequence_kind': 'arithmetic', 'a1': 1, 'step': 2, 'n': 5},
            {'kind': 'polynomial_derivative', 'coefficients': [1, 2, 3]},
            {'kind': 'polynomial_integral', 'coefficients': [1, 2, 3]},
        ]
        for task in tasks:
            r = m.solve(task)
            r2 = copy.deepcopy(r)
            r2['status'] = 'bogus'
            self.assertFalse(m.verify(task, r2)['verified'], task['kind'])

    def test_sequence_kind_bound_to_task(self):
        t = {'kind': 'sequence', 'sequence_kind': 'arithmetic', 'a1': 1, 'step': 1, 'n': 5}
        r = m.solve(t)
        r2 = copy.deepcopy(r)
        r2['sequence_kind'] = 'geometric'
        self.assertFalse(m.verify(t, r2)['verified'])

    def test_delivered_quadratic_reverifiable(self):
        t = {'kind': 'quadratic', 'a': 1, 'b': -5, 'c': 6}
        r = m.solve(t)
        self.assertNotIn('_roots_exact', r)
        self.assertTrue(m.verify(t, r)['verified'])

    def test_malformed_roots_exact_false_not_crash(self):
        t = {'kind': 'quadratic', 'a': 1, 'b': -5, 'c': 6}
        r = m.solve(t)
        r['_roots_exact'] = []
        self.assertFalse(m.verify(t, r)['verified'])
        r['_roots_exact'] = 'junk'
        self.assertFalse(m.verify(t, r)['verified'])

    def test_verify_applies_solve_bounds(self):
        # derangements beyond the result bound: fail fast, no factorial bomb
        t = {'kind': 'combinatorics', 'op': 'derangements', 'n': 100}
        fake = {'kind': 'combinatorics', 'op': 'derangements', 'n': 100,
                'k': None, 'status': 'computed', 'result': 1}
        self.assertFalse(m.verify(t, fake)['verified'])
        # choose with a value beyond the result bound
        t = {'kind': 'combinatorics', 'op': 'choose', 'n': 100000, 'k': 50000}
        fake = {'kind': 'combinatorics', 'op': 'choose', 'n': 100000, 'k': 50000,
                'status': 'computed', 'result': 1}
        self.assertFalse(m.verify(t, fake)['verified'])
        # catalan beyond its cap
        t = {'kind': 'combinatorics', 'op': 'catalan', 'n': 501}
        fake = {'kind': 'combinatorics', 'op': 'catalan', 'n': 501,
                'k': None, 'status': 'computed', 'result': 1}
        self.assertFalse(m.verify(t, fake)['verified'])
        # geometric sequence power beyond the size pre-check
        t = {'kind': 'sequence', 'sequence_kind': 'geometric', 'a1': 1, 'step': 2, 'n': 10 ** 6}
        fake = {'kind': 'sequence', 'sequence_kind': 'geometric', 'status': 'computed',
                'nth': '1', 'sum_first_n': '1', 'n': 10 ** 6}
        self.assertFalse(m.verify(t, fake)['verified'])
        # n beyond MAX_SEQ_N
        t = {'kind': 'sequence', 'sequence_kind': 'arithmetic', 'a1': 1, 'step': 1, 'n': 10 ** 7}
        fake = {'kind': 'sequence', 'sequence_kind': 'arithmetic', 'status': 'computed',
                'nth': '1', 'sum_first_n': '1', 'n': 10 ** 7}
        self.assertFalse(m.verify(t, fake)['verified'])
        # overlong expression source
        t = {'kind': 'expression', 'source': '1+' * 10 ** 5 + '1'}
        fake = {'kind': 'expression', 'status': 'computed',
                'source': t['source'], 'value': '1'}
        self.assertFalse(m.verify(t, fake)['verified'])
        # oversized linear system
        t = {'kind': 'linear_system', 'matrix': [[1] * 20] * 20, 'vector': [1] * 20}
        fake = {'kind': 'linear_system', 'status': 'unique', 'rank_coefficients': 1,
                'rank_augmented': 1, 'solution': [1] * 20}
        self.assertFalse(m.verify(t, fake)['verified'])
        # oversized statistics list
        t = {'kind': 'statistics', 'values': [1] * (10 ** 5 + 1)}
        fake = {'kind': 'statistics', 'status': 'computed', 'count': 10 ** 5 + 1,
                'mean': '1', 'median': '1', 'population_variance': '0',
                'min': '1', 'max': '1'}
        self.assertFalse(m.verify(t, fake)['verified'])
        # too many CRT congruences
        t = {'kind': 'crt', 'remainders': [0] * 9, 'moduli': [3, 5, 7, 11, 13, 17, 19, 23, 29]}
        fake = {'kind': 'crt', 'status': 'solved', 'solution': 0, 'modulus': 1,
                'congruences': []}
        self.assertFalse(m.verify(t, fake)['verified'])

    def test_valid_results_still_verify_after_bound_guards(self):
        for task in [
            {'kind': 'combinatorics', 'op': 'derangements', 'n': 20},
            {'kind': 'combinatorics', 'op': 'fibonacci', 'n': 100},
            {'kind': 'sequence', 'sequence_kind': 'geometric', 'a1': 3, 'step': 2, 'n': 10},
            {'kind': 'linear_system', 'matrix': [[2, 1], [1, 3]], 'vector': [5, 6]},
        ]:
            r = m.solve(task)
            self.assertTrue(r['verification']['verified'], task)


class AuditorProbesRound3(unittest.TestCase):
    """Auditor-7 round-3: integral constant, bool binding, linear shape
    boundary, caps-before-iteration, exact keys per family."""

    def test_polynomial_integral_constant_bound(self):
        t = {'kind': 'polynomial_integral', 'coefficients': [1]}
        r = m.solve(t)
        self.assertEqual(r['coefficients_out'], [0, 1])
        r2 = copy.deepcopy(r)
        r2['coefficients_out'][0] = 7  # same derivative, wrong constant
        self.assertFalse(m.verify(t, r2)['verified'])

    def test_is_prime_requires_real_bool(self):
        t = {'kind': 'is_prime', 'n': 97}
        r = m.solve(t)
        for bad in ('tampered', 1, [True]):
            r2 = copy.deepcopy(r)
            r2['prime'] = bad
            self.assertFalse(m.verify(t, r2)['verified'], repr(bad))
        t = {'kind': 'is_prime', 'n': 100}
        r = m.solve(t)
        r2 = copy.deepcopy(r)
        r2['prime'] = 0  # == False but not bool
        self.assertFalse(m.verify(t, r2)['verified'])

    def test_linear_shape_must_match_solve_boundary(self):
        # non-square matrix with a result that fits a smaller system
        t = {'kind': 'linear_system', 'matrix': [[1, 0]], 'vector': [2]}
        fake = {'kind': 'linear_system', 'status': 'unique', 'rank_coefficients': 1,
                'rank_augmented': 1, 'solution': ['2']}
        self.assertFalse(m.verify(t, fake)['verified'])
        # vector length mismatch
        t2 = {'kind': 'linear_system', 'matrix': [[1]], 'vector': [2, 3]}
        self.assertFalse(m.verify(t2, fake)['verified'])
        # ragged rows
        t3 = {'kind': 'linear_system', 'matrix': [[1, 2], [3]], 'vector': [1, 2]}
        self.assertFalse(m.verify(t3, fake)['verified'])

    def test_exact_result_keys_per_family(self):
        tasks = [
            {'kind': 'linear_system', 'matrix': [[2, 1], [1, 3]], 'vector': [5, 6]},
            {'kind': 'quadratic', 'a': 1, 'b': -5, 'c': 6},
            {'kind': 'polynomial_derivative', 'coefficients': [1, 2, 3]},
            {'kind': 'polynomial_integral', 'coefficients': [1, 2, 3]},
            {'kind': 'diophantine', 'a': 3, 'b': 5, 'c': 1},
            {'kind': 'is_prime', 'n': 97},
            {'kind': 'factor', 'n': 360},
            {'kind': 'crt', 'remainders': [2, 3, 2], 'moduli': [3, 5, 7]},
            {'kind': 'combinatorics', 'op': 'choose', 'n': 10, 'k': 3},
            {'kind': 'sequence', 'sequence_kind': 'arithmetic', 'a1': 1, 'step': 2, 'n': 5},
            {'kind': 'statistics', 'values': [1, 2, 9]},
            {'kind': 'expression', 'source': '2+3*4'},
        ]
        for task in tasks:
            r = m.solve(task)
            r2 = copy.deepcopy(r)
            r2['extra_claim'] = 'world best'
            self.assertFalse(m.verify(task, r2)['verified'], task['kind'])
            r3 = m.solve(task)
            victim = next(k for k in r3
                          if k not in ('kind', 'status', 'verification') and not k.startswith('_'))
            del r3[victim]
            self.assertFalse(m.verify(task, r3)['verified'], (task['kind'], victim))

    def test_valid_results_still_verify_round3(self):
        for task in [
            {'kind': 'linear_system', 'matrix': [[0, 0], [0, 0]], 'vector': [0, 0]},
            {'kind': 'linear_system', 'matrix': [[1, 2], [3, 4]], 'vector': [5, 11]},
            {'kind': 'diophantine', 'a': 4, 'b': 6, 'c': 3},
            {'kind': 'polynomial_integral', 'coefficients': [0]},
            {'kind': 'quadratic', 'a': 1, 'b': 0, 'c': 1},
        ]:
            r = m.solve(task)
            self.assertTrue(r['verification']['verified'], task)


if __name__ == "__main__":
    unittest.main()
