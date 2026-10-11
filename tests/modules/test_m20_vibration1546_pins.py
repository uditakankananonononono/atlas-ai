"""Test-only pins for the supplied modal calculation (row 1546). Core is frozen.

Oracles are independent closed forms (trace/determinant eigenvalues, (b, lambda-a)
eigenvectors), not the core's whitening path. Scope: bounded supplied-matrix
calculation only; no physical test and no science claim.
"""
import math
import unittest
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    'vibration1546_pins', Path(__file__).resolve().parents[2] / 'backend/app/modules/m20_general_cognitive_worker/vibration_modal1546.py')
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
analyze_modal = _module.analyze_modal
UNITS = {'mass': 'kg', 'stiffness': 'N/m'}


def req(M, K, **extra):
    d = dict(request_id='pin-1546', mass_matrix=M, stiffness_matrix=K, units=dict(UNITS), model='linear_undamped')
    d.update(extra)
    return d


def obs(mode_id, f=1.0, ref='lab-note'):
    return dict(mode_id=mode_id, frequency_hz=f, source_ref=ref)


def oracle_identity_mass(K):
    """Eigenpairs of symmetric 2x2 K with M=I: ascending, unit norm, largest |component| positive, first tie wins."""
    a, b, c = K[0][0], K[0][1], K[1][1]
    tr, det = a + c, a*c - b*b
    disc = math.sqrt(tr*tr/4 - det)
    out = []
    for lam in (tr/2 - disc, tr/2 + disc):
        v = [b, lam - a] if abs(b) > 0 else ([1.0, 0.0] if abs(lam - a) < abs(lam - c) else [0.0, 1.0])
        n = math.hypot(*v); v = [x/n for x in v]
        p = 0 if abs(v[0]) >= abs(v[1])*(1 - 1e-12) else 1
        if v[p] < 0:
            v = [-x for x in v]
        out.append((lam, v))
    return out


class Pins(unittest.TestCase):
    def refuse(self, data, message):
        with self.assertRaises(ValueError) as cm:
            analyze_modal(data)
        self.assertEqual(str(cm.exception), message)

    # ---- result record fields (L143, L147, L148) ----
    def test_record_constants(self):
        r = analyze_modal(req([[1]], [[1]]))
        self.assertIs(r['test_performed'], False)
        self.assertIs(r['structural_certification'], False)
        self.assertIs(r['source_authenticity_verified'], False)
        self.assertEqual(r['ledger_row'], 1546)
        self.assertEqual(r['capability'], 'Vibration Testing')
        self.assertEqual(r['dof_count'], 1)

    def test_missing_measurement_mode_ids(self):
        I2, K2 = [[1, 0], [0, 1]], [[2, 0], [0, 3]]
        cases = [([], [1, 2]), ([obs(1)], [2]), ([obs(2)], [1]), ([obs(1), obs(2)], [])]
        for observations, missing in cases:
            r = analyze_modal(req(I2, K2, measurements=observations, tolerance_hz=1.0))
            self.assertEqual(r['missing_measurement_mode_ids'], missing, observations)
        r = analyze_modal(req([[1]], [[1]]))
        self.assertEqual(r['missing_measurement_mode_ids'], [1])
        r = analyze_modal(req([[1]], [[1]], measurements=[obs(1)], tolerance_hz=1.0))
        self.assertEqual(r['missing_measurement_mode_ids'], [])

    # ---- measurement mode_id range (L128) ----
    def test_measurement_mode_id_range(self):
        for M, K, n in (([[1]], [[1]], 1), ([[1, 0], [0, 1]], [[2, 0], [0, 3]], 2)):
            message = f'measurement mode_id: expected unique integer in 1..{n}'
            for bad in (0, n + 1, -1):
                self.refuse(req(M, K, measurements=[obs(bad)], tolerance_hz=1.0), message)
            for ok in range(1, n + 1):
                analyze_modal(req(M, K, measurements=[obs(ok)], tolerance_hz=1.0))
        self.refuse(req([[1, 0], [0, 1]], [[2, 0], [0, 3]], measurements=[obs(1), obs(1)], tolerance_hz=1.0),
                    'measurement mode_id: expected unique integer in 1..2')

    # ---- non-diagonal 2x2 against an independent oracle (L41 L42 L69 L81 L82 L85) ----
    def test_nondiagonal_identity_mass(self):
        for K in ([[2, 1], [1, 2]], [[3, 1], [1, 1]], [[1, -1], [-1, 3]], [[5, 2], [2, 1]], [[1, 0.5], [0.5, 4]], [[4, -1], [-1, 1]]):
            r = analyze_modal(req([[1, 0], [0, 1]], K))
            for mode, (lam, v) in zip(r['modes'], oracle_identity_mass(K)):
                self.assertAlmostEqual(mode['eigenvalue_rad2_s2'], lam, places=12, msg=str(K))
                for got, want in zip(mode['shape'], v):
                    self.assertAlmostEqual(got, want, places=12, msg=str(K))
                self.assertAlmostEqual(mode['omega_rad_s'], math.sqrt(lam), places=12)
                self.assertAlmostEqual(mode['frequency_hz'], math.sqrt(lam)/(2*math.pi), places=12)

    def test_sign_convention_largest_component_positive(self):
        r = analyze_modal(req([[1, 0], [0, 1]], [[3, 1], [1, 1]]))
        lo, hi = (m['shape'] for m in r['modes'])
        self.assertLess(lo[0], 0); self.assertGreater(lo[1], 0); self.assertGreater(abs(lo[1]), abs(lo[0]))
        self.assertGreater(hi[0], 0); self.assertGreater(hi[1], 0); self.assertGreater(abs(hi[0]), abs(hi[1]))
        r = analyze_modal(req([[1, 0], [0, 1]], [[2, 1], [1, 2]]))
        self.assertAlmostEqual(r['modes'][0]['shape'][0], 1/math.sqrt(2), places=12)
        self.assertAlmostEqual(r['modes'][0]['shape'][1], -1/math.sqrt(2), places=12)

    def test_near_tie_first_component_wins(self):
        r = analyze_modal(req([[1, 0], [0, 1]], [[2, 1], [1, 2 + 1e-13]]))
        a, b = r['modes'][0]['shape']
        self.assertGreater(a, 0); self.assertLess(b, 0)

    def test_relative_residual_matches_its_definition(self):
        M, K = [[4, 2], [2, 10]], [[7, 1], [1, 9]]
        r = analyze_modal(req(M, K))
        for mode in r['modes']:
            x, lam = mode['shape'], mode['eigenvalue_rad2_s2']
            kx = [sum(K[i][j]*x[j] for j in range(2)) for i in range(2)]
            mx = [sum(M[i][j]*x[j] for j in range(2)) for i in range(2)]
            res = math.hypot(*(kx[i] - lam*mx[i] for i in range(2)))
            self.assertAlmostEqual(mode['residual_norm'], res, delta=1e-12)
            if mode['residual_norm'] > 0:
                self.assertTrue(math.isclose(mode['relative_residual'],
                                             mode['residual_norm']/(math.hypot(*kx) + abs(lam)*math.hypot(*mx)), rel_tol=1e-9))
            self.assertLess(mode['relative_residual'], 1e-12)

    # ---- positivity and conditioning guards (L34 L38 L41 L42 L43) ----
    def test_scale_floor_inclusive(self):
        analyze_modal(req([[1e-12]], [[1]]))
        analyze_modal(req([[1]], [[1e-12]]))
        self.refuse(req([[1]], [[9e-13]]), 'stiffness_matrix: must be positive definite and well conditioned')
        self.refuse(req([[9e-13]], [[1]]), 'mass_matrix: must be positive definite and well conditioned')
        self.refuse(req([[0]], [[1]]), 'mass_matrix: must be positive definite and well conditioned')

    def test_one_by_one_sign(self):
        self.refuse(req([[-3]], [[1]]), 'mass_matrix: must be positive definite and well conditioned')
        self.refuse(req([[3]], [[-1]]), 'stiffness_matrix: must be positive definite and well conditioned')

    def test_two_by_two_definiteness_with_offdiagonal(self):
        bad = 'mass_matrix: must be positive definite and well conditioned'
        for M in ([[1, 2], [2, 1]], [[1, 1], [1, 1]], [[1, -1], [-1, 1]], [[-2, 1], [1, -2]], [[1, 3], [3, 4]], [[4, 3], [3, 1]]):
            self.refuse(req(M, [[1, 0], [0, 1]]), bad)
            self.refuse(req([[1, 0], [0, 1]], M), bad.replace('mass', 'stiffness'))
        for M in ([[2, 1], [1, 2]], [[1, 0.9], [0.9, 1]], [[3, -2], [-2, 2]]):
            analyze_modal(req(M, [[1, 0], [0, 1]]))
            analyze_modal(req([[1, 0], [0, 1]], M))

    def test_condition_floor_is_strictly_greater(self):
        bad = 'mass_matrix: must be positive definite and well conditioned'
        self.refuse(req([[1, 0], [0, 1e-12]], [[1, 0], [0, 1]]), bad)
        self.refuse(req([[1, 0], [0, 5e-13]], [[1, 0], [0, 1]]), bad)
        analyze_modal(req([[1, 0], [0, 2e-12]], [[1, 0], [0, 1]]))

    def test_nonpositive_diagonal_with_zero_largest_eigenvalue_is_refused_not_a_crash(self):
        bad = 'mass_matrix: must be positive definite and well conditioned'
        for M in ([[0, 0], [0, -1]], [[-1, 0], [0, 0]]):
            self.refuse(req(M, [[1, 0], [0, 1]]), bad)

    def test_condition_floor_with_offdiagonal_coupling(self):
        # M=[[1,1-d],[1-d,1]] has eigenvalues 2-d and d: min/max ratio ~ d/2 against the 1e-12 floor.
        bad = 'mass_matrix: must be positive definite and well conditioned'
        for d in (5e-13, 1.5e-12):
            self.refuse(req([[1, 1 - d], [1 - d, 1]], [[1, 0], [0, 1]]), bad)
            self.refuse(req([[1, -(1 - d)], [-(1 - d), 1]], [[1, 0], [0, 1]]), bad)
        for d in (3e-12, 6e-12):
            # passes the conditioning guard; the solve then refuses on its own residual limit
            self.refuse(req([[1, 1 - d], [1 - d, 1]], [[1, 0], [0, 1]]), 'modal solve: residual exceeds 1e-8')

    # ---- one-dof formulas (L56) ----
    def test_one_dof_eigenvalue_uses_k_over_m(self):
        r = analyze_modal(req([[5]], [[20]]))
        self.assertAlmostEqual(r['modes'][0]['eigenvalue_rad2_s2'], 4.0, places=12)
        self.assertAlmostEqual(r['modes'][0]['shape'][0], 1/math.sqrt(5), places=15)
        self.assertEqual(r['modes'][0]['mode_id'], 1)

    # ---- numeric guards (L11) ----
    def test_magnitude_limit_inclusive(self):
        analyze_modal(req([[1]], [[1]], tolerance_hz=1e12))
        analyze_modal(req([[1]], [[1]], tolerance_hz=10**12))
        for v in (math.nextafter(1e12, math.inf), 10**12 + 1, -1.0000000000001e12):
            self.refuse(req([[1]], [[1]], tolerance_hz=v), 'tolerance_hz: expected finite number with magnitude <= 1e12')
        self.refuse(req([[1e12 + 1e5]], [[1]]), 'mass_matrix[0][0]: expected finite number with magnitude <= 1e12')

    # ---- text guards (L20) ----
    def test_request_id_text_arms(self):
        msg = 'request_id: expected nonblank string of length 1..128'
        for bad in ('', '   ', '\t\n', 'x'*129, 5, None, ['a'], b'abc'):
            self.refuse(req([[1]], [[1]], request_id=bad), msg)
        self.assertEqual(analyze_modal(req([[1]], [[1]], request_id='x'*128))['request_id'], 'x'*128)
        self.assertEqual(analyze_modal(req([[1]], [[1]], request_id='a'))['request_id'], 'a')

    def test_source_ref_text_arms(self):
        msg = 'source_ref: expected nonblank string of length 1..256'
        for bad in ('', ' ', 'y'*257, 7, None):
            self.refuse(req([[1]], [[1]], measurements=[obs(1, ref=bad)], tolerance_hz=1.0), msg)
        analyze_modal(req([[1]], [[1]], measurements=[obs(1, ref='y'*256)], tolerance_hz=1.0))

    # ---- matrix shape guards (L26) ----
    def test_matrix_shape_arms(self):
        msg = 'mass_matrix: expected 1 or 2 square rows'
        for bad in ((), (1,), {}, 'ab', 5, None, [], [[1], [2], [3]], [[1, 2, 3], [4, 5, 6]], [[1, 2]], [[1], [2]],
                    [1], [1, 2], [[1, 2], [3]], [[1, 2], 3], [[1, 0], (0, 1)], ([1],), [[1, 0], [0, 1], [0, 0]]):
            self.refuse(req(bad, [[1]]), msg)
        analyze_modal(req([[1]], [[1]]))
        self.refuse(req([[1, 0], [0, 1]], [[1]]), 'stiffness_matrix: dimension differs from mass_matrix')
        self.refuse(req([[1]], [[1, 0], [0, 1]]), 'stiffness_matrix: dimension differs from mass_matrix')
        self.refuse(req([[2, 1], [0, 2]], [[1, 0], [0, 1]]), 'mass_matrix: must be symmetric')

    # ---- modal-solve refusals reachable through public input (L74 L86) ----
    def test_modal_solve_nonpositive_eigenvalue_refusals(self):
        negative = req([[9.029166845528991e-06, -0.0011451981815461109], [-0.0011451981815461109, 0.14524954950793523]],
                       [[0.010561211035749673, -1.0144190897585674e-06], [-1.0144190897585674e-06, 9.746824489012674e-11]])
        zero = req([[0.0006099759963850218, 1.3471259974867653], [1.3471259974867653, 2977.3982164409886]],
                   [[37368.381782389515, -796.0387489316336], [-796.0387489316336, 16.957591151858434]])
        for data in (negative, zero):
            self.refuse(data, 'modal solve: positive finite eigenvalues required')

    def test_modal_solve_residual_refusal(self):
        data = req([[288.04936104103496, 166.5489074546985], [166.5489074546985, 96.29790689381174]],
                   [[0.0016913763420516167, -0.0009329073850009783], [-0.0009329073850009783, 0.0005145746922196188]])
        self.refuse(data, 'modal solve: residual exceeds 1e-8')


if __name__ == '__main__':
    unittest.main()
