"""Independent analytic and boundary checks for supplied modal calculations."""
import copy
import math
import unittest
import importlib.util
from pathlib import Path
_spec = importlib.util.spec_from_file_location('vibration1546', Path(__file__).resolve().parents[2] / 'backend/app/modules/m20_general_cognitive_worker/vibration_modal1546.py')
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
analyze_modal = _module.analyze_modal


def payload(n=1):
    return dict(request_id='fresh-modal-21', mass_matrix=[[2]] if n == 1 else [[1, 0], [0, 1]],
                stiffness_matrix=[[8]] if n == 1 else [[2, -1], [-1, 2]],
                units={'mass': 'kg', 'stiffness': 'N/m'}, model='linear_undamped')


class ModalTests(unittest.TestCase):
    def refuse(self, p, error):
        with self.assertRaisesRegex(ValueError, '^' + __import__('re').escape(error) + '$'):
            analyze_modal(p)

    def test_analytic_one(self):
        r = analyze_modal(payload())
        self.assertAlmostEqual(r['modes'][0]['omega_rad_s'], 2)
        self.assertAlmostEqual(r['modes'][0]['frequency_hz'], 1 / math.pi)
        self.assertAlmostEqual(r['modes'][0]['shape'][0], 1 / math.sqrt(2))
        self.assertFalse(r['test_performed'])
        self.assertFalse(r['structural_certification'])
        self.assertEqual(r['artifact_status'], 'supplied_modal_calculation')

    def test_symmetric_two_and_sign(self):
        r = analyze_modal(payload(2))
        self.assertEqual([m['mode_id'] for m in r['modes']], [1, 2])
        for m, value in zip(r['modes'], [1, 3]):
            self.assertAlmostEqual(m['eigenvalue_rad2_s2'], value)
            self.assertGreater(m['shape'][0], 0)
            self.assertLess(m['relative_residual'], 1e-12)
        a, b = [m['shape'] for m in r['modes']]
        self.assertAlmostEqual(sum(x*y for x, y in zip(a, b)), 0)

    def test_generalized_mass_oracle(self):
        # L diag(a,b) L^T has generalized eigenvalues a,b for M=L L^T.
        for a in [0.25, 1, 3, 10]:
            for b in [0.5, 2, 7, 11]:
                p = payload(2)
                p['mass_matrix'] = [[4, 2], [2, 10]]
                p['stiffness_matrix'] = [[4*a, 2*a], [2*a, a+9*b]]
                r = analyze_modal(p)
                for m, expected in zip(r['modes'], sorted([a, b])):
                    self.assertAlmostEqual(m['eigenvalue_rad2_s2'], expected, places=10)
                    x = m['shape']; M = p['mass_matrix']
                    self.assertAlmostEqual(sum(x[i]*M[i][j]*x[j] for i in range(2) for j in range(2)), 1)
                    self.assertLess(m['relative_residual'], 1e-12)

    def test_repeated_eigenvalues_deterministic(self):
        p = payload(2); p['stiffness_matrix'] = [[2, 0], [0, 2]]
        self.assertEqual(analyze_modal(p)['modes'][0]['shape'], [1.0, 0.0])
        self.assertEqual(analyze_modal(p), analyze_modal(copy.deepcopy(p)))

    def test_comparison_sorted_exact_tolerance(self):
        p = payload(2); r = analyze_modal(p)
        p['tolerance_hz'] = .125
        p['measurements'] = [{'mode_id': 2, 'frequency_hz': r['modes'][1]['frequency_hz']+.125, 'source_ref': 'lab-b'},
                             {'mode_id': 1, 'frequency_hz': r['modes'][0]['frequency_hz'], 'source_ref': 'lab-a'}]
        out = analyze_modal(p)
        self.assertTrue(all(x['within_tolerance'] for x in out['comparisons']))
        p['measurements'].reverse(); self.assertEqual(out, analyze_modal(p))
        p['measurements'][0]['frequency_hz'] += .125001
        self.assertFalse(analyze_modal(p)['comparisons'][0]['within_tolerance'])
        self.assertEqual(analyze_modal(payload())['comparison_status'], 'no_supplied_measurements')

    def test_dimension_n_nplus1(self):
        analyze_modal(payload(2))
        p = payload(); p['mass_matrix'] = [[1,0,0],[0,1,0],[0,0,1]]
        self.refuse(p, 'mass_matrix: expected 1 or 2 square rows')

    def test_singular_nonpositive_and_nonsymmetric(self):
        for name in ['mass_matrix', 'stiffness_matrix']:
            for value in [[[0]], [[-1]], [[1,1],[1,1]], [[1,2],[0,1]]]:
                p = payload(len(value)); p[name] = value
                error = name + (': must be symmetric' if value == [[1,2],[0,1]] else ': must be positive definite and well conditioned')
                self.refuse(p, error)

    def test_nonfinite_bool_string_and_shape(self):
        for value in [float('nan'),float('inf'),True,'2',10**500]:
            p=payload(); p['mass_matrix']=[[value]]
            self.refuse(p, 'mass_matrix[0][0]: expected finite number with magnitude <= 1e12')
        p=payload(2);p['stiffness_matrix']=[[1]]
        self.refuse(p,'stiffness_matrix: dimension differs from mass_matrix')

    def test_fresh_id_exact_errors_and_bounds(self):
        p=payload();p['request_id']='x'*128; analyze_modal(p)
        p['request_id']='x'*129; self.refuse(p,'request_id: expected nonblank string of length 1..128')
        p=payload();p['request_id']='brand-new-unknown-mode'
        p['measurements']=[{'mode_id':2,'frequency_hz':1,'source_ref':'source'}];p['tolerance_hz']=0
        self.refuse(p,'measurement mode_id: expected unique integer in 1..1')

    def test_measurement_bounds_sources_and_tolerance(self):
        p=payload(2);p['measurements']=[{'mode_id':i,'frequency_hz':1,'source_ref':'s'*256} for i in [1,2]];p['tolerance_hz']=0
        analyze_modal(p)
        p['measurements'].append({'mode_id':1,'frequency_hz':1,'source_ref':'s'})
        self.refuse(p,'measurements: expected at most 2 records')
        p['measurements']=p['measurements'][:1];p['measurements'][0]['source_ref']='s'*257
        self.refuse(p,'source_ref: expected nonblank string of length 1..256')
        p['measurements'][0]['source_ref']='s';p.pop('tolerance_hz')
        self.refuse(p,'tolerance_hz: required for measurements')
        p['tolerance_hz']=-1;self.refuse(p,'tolerance_hz: must be nonnegative')
        p['tolerance_hz']=0;p['measurements']*=2
        self.refuse(p,'measurement mode_id: expected unique integer in 1..2')

    def test_model_units_and_unsupported_fields(self):
        for key in ['damping_matrix','nonlinear','test_performed']:
            p=payload();p[key]=False;self.refuse(p,'unsupported fields: '+key)
        p=payload();p['model']='damped';self.refuse(p,'model: only linear_undamped supported')
        p=payload();p['units']['mass']='g';self.refuse(p,'units: exactly mass=kg and stiffness=N/m required')

    def test_tiny_scale_and_extra_measurement_refusal(self):
        p=payload();p['mass_matrix']=[[1e-13]]
        self.refuse(p,'mass_matrix: must be positive definite and well conditioned')
        p=payload();p['measurements']=[{'mode_id':True,'frequency_hz':1,'source_ref':'s'}];p['tolerance_hz']=0
        self.refuse(p,'measurement mode_id: expected unique integer in 1..1')
        p['measurements'][0]['mode_id']=1;p['measurements'][0]['frequency_hz']=0
        self.refuse(p,'measured frequency_hz: must be positive')
        p['measurements'][0]['frequency_hz']=1;p['measurements'][0]['extra']='x'
        self.refuse(p,'measurement: exactly mode_id,frequency_hz,source_ref required')

    def test_scaled_matrix_domain_floor(self):
        for scale in [1e-6,1,1e6]:
            p=payload(2);p['mass_matrix']=[[scale,0],[0,scale]];p['stiffness_matrix']=[[2*scale,-scale],[-scale,2*scale]]
            self.assertAlmostEqual(analyze_modal(p)['modes'][0]['eigenvalue_rad2_s2'],1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
