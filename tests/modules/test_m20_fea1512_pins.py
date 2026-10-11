"""Test-only pins for row 1512 axial bar (core backend/.../axial_fea1512.py is NOT modified).

Written by the pin auditor-owner from the frozen source at 83ac9702. Stdlib unittest.
Section A pins current behavior to kill surviving mutants. Section B pins documented limits
and ordering (classified not-defects by a peer-stated ruling, not owner words; core unchanged).
"""
import importlib.util
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / 'backend/app/modules/m20_general_cognitive_worker/axial_fea1512.py'
_spec = importlib.util.spec_from_file_location('fea1512_pins_under_test', CORE)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
solve = _mod.solve_axial_bar

UNITS = {'length': 'm', 'force': 'N', 'modulus': 'Pa', 'area': 'm^2'}


def mesh(n=1, E=10.0, A=2.0, force=4.0):
    return {'model': '1d_axial_linear_elastic', 'units': dict(UNITS),
            'nodes': [{'id': str(i), 'x': i / n} for i in range(n + 1)],
            'elements': [{'id': 'e' + str(i), 'nodes': [str(i), str(i + 1)], 'E': E, 'A': A} for i in range(n)],
            'loads': [{'node': str(n), 'force': force}],
            'displacements': [{'node': '0', 'value': 0.0}], 'source_refs': ['supplied-case']}


def chain(Es, force=1.0):
    n = len(Es)
    d = mesh(n)
    for el, e in zip(d['elements'], Es):
        el['E'] = e
        el['A'] = 1.0
    for i, nd in enumerate(d['nodes']):
        nd['x'] = i
    d['loads'] = [{'node': str(n), 'force': force}]
    return d


def disp(r, node):
    return next(x['displacement'] for x in r['nodes'] if x['id'] == node)


class Pins(unittest.TestCase):
    def refused(self, d, code):
        with self.assertRaises(ValueError) as cm:
            solve(d)
        self.assertEqual(str(cm.exception), code)

    # ---- honesty flags (L189, L190)
    def test_honesty_flags_exact(self):
        r = solve(mesh())
        self.assertIs(r['source_verified'], False)
        self.assertIs(r['safety_certified'], False)
        self.assertIs(r['requires_engineer_review'], True)
        self.assertEqual(r['solver'], 'bounded_scaled_gaussian_elimination')
        self.assertTrue(r['boundary'].startswith('Supplied 1D linear-elastic axial bar only'))

    # ---- numeric exactness (L172, L175, L186)
    def test_axial_force_is_stress_times_area(self):
        e = solve(mesh())['elements'][0]
        self.assertAlmostEqual(e['stress'], 2.0, places=12)
        self.assertAlmostEqual(e['axial_force'], 4.0, places=12)   # stress*A with A=2 (not stress/A = 1)
        self.assertAlmostEqual(e['length'], 1.0, places=12)

    def test_external_work_half_with_nonzero_support_displacement(self):
        d = mesh(2); d['displacements'][0]['value'] = 0.7
        r = solve(d)
        # u0=.7, u1=.8, u2=.9 ; f2=4 ; reaction0=-4. work = .5*(.7*-4 + .9*4) = .4
        self.assertAlmostEqual(r['external_work_half'], 0.4, places=12)
        self.assertAlmostEqual(r['strain_energy'], 0.4, places=12)

    def test_prescribed_motion_work_matches_energy_exactly(self):
        d = mesh(); d['loads'] = []; d['displacements'].append({'node': '1', 'value': .3})
        r = solve(d)
        self.assertAlmostEqual(r['external_work_half'], 0.9, places=12)
        self.assertAlmostEqual(r['strain_energy'], 0.9, places=12)

    def test_restrained_flags_per_node(self):
        r = solve(mesh(2))
        self.assertEqual([(n['id'], n['restrained']) for n in r['nodes']],
                         [('0', True), ('1', False), ('2', False)])
        d = mesh(); d['displacements'].append({'node': '1', 'value': 0.0})
        self.assertEqual([n['restrained'] for n in solve(d)['nodes']], [True, True])

    def test_multi_free_node_exact_chain(self):
        # series chain E=[1,2,4,8], A=1, L=1, force 1 at the end: u_k = sum_{j<=k} 1/E_j
        r = solve(chain([1.0, 2.0, 4.0, 8.0]))
        expect = [0, 1, 1.5, 1.75, 1.875]
        for i, v in enumerate(expect):
            self.assertAlmostEqual(disp(r, str(i)), v, places=12)

    # ---- numerical gates (L42, L112, L182)
    def test_small_but_positive_stiffness_is_accepted(self):
        d = mesh(); d['nodes'][1]['x'] = 2.0
        d['elements'][0]['E'] = 1.0; d['elements'][0]['A'] = 1.0   # EA/L = 0.5
        d['loads'][0]['force'] = 1.0
        self.assertAlmostEqual(disp(solve(d), '1'), 2.0, places=12)

    def test_pivot_ratio_boundary(self):
        r = solve(chain([1.0, 9e11]))
        self.assertTrue(all(math.isfinite(n['displacement']) for n in r['nodes']))
        self.refused(chain([1.0, 1e12]), 'FEA1512_SINGULAR')
        self.refused(chain([1.0, 1e13]), 'FEA1512_SINGULAR')

    def test_residual_tolerance_scales_with_load_magnitude(self):
        r = solve(chain([1e8, 1.0, 1e8], force=1e9))
        self.assertGreater(r['equilibrium_residual'], 1.0)          # nonzero residual accepted
        self.assertLess(r['equilibrium_residual'], 1e-8 * 1e9)      # below 1e-8*|f|

    def test_documented_conditioning_refusal(self):
        d = mesh(); d['nodes'].append({'id': 'c', 'x': 2})
        d['elements'].append({'id': 'f', 'nodes': ['1', 'c'], 'E': 1e9, 'A': 2.0})
        d['loads'] = [{'node': 'c', 'force': 4.0}]
        self.refused(d, 'FEA1512_NUMERICAL')

    # ---- identifier guard (L28) for nodes and elements
    def test_node_id_guard_arms(self):
        for bad in (5, None, '', 'a' * 129, ['a']):
            d = mesh(); d['nodes'][1]['id'] = bad
            self.refused(d, 'FEA1512_NODE')
        d = mesh(); d['nodes'][1]['id'] = 'b' * 128
        d['elements'][0]['nodes'][1] = 'b' * 128
        d['loads'][0]['node'] = 'b' * 128
        self.assertAlmostEqual(disp(solve(d), 'b' * 128), 0.2)

    def test_element_id_guard_arms(self):
        for bad in (5, None, '', 'e' * 129):
            d = mesh(); d['elements'][0]['id'] = bad
            self.refused(d, 'FEA1512_ELEMENT')
        d = mesh(); d['elements'][0]['id'] = 'e' * 128
        self.assertAlmostEqual(disp(solve(d), '1'), 0.2)

    # ---- node and element count guards (L74)
    def test_node_count_bounds(self):
        for nodes in ([], [{'id': '0', 'x': 0.0}], None, ()):
            d = mesh(); d['nodes'] = nodes
            self.refused(d, 'FEA1512_BOUNDS')

    # ---- element shape (L97)
    def test_element_end_list_shape(self):
        for ends in (['0'], ['0', '1', '1'], [], '01', ('0', '1'), {'0': 1, '1': 2}, None):
            d = mesh(); d['elements'][0]['nodes'] = ends
            self.refused(d, 'FEA1512_ELEMENT')
        d = mesh(2); d['elements'][1]['id'] = 'e0'
        self.refused(d, 'FEA1512_ELEMENT')

    # ---- loads / displacements container shape (L129)
    def test_load_and_bc_container_shape(self):
        for bad in ({}, (), '', None, 0, {'node': '1', 'force': 1}):
            d = mesh(); d['loads'] = bad
            self.refused(d, 'FEA1512_LOAD')
            d = mesh(); d['displacements'] = bad
            self.refused(d, 'FEA1512_BC')
        d = mesh(); d['loads'] = [{'node': '1', 'force': 1.0}] * 3
        self.refused(d, 'FEA1512_LOAD')

    # ---- source refs (L155)
    def test_source_refs_bounds(self):
        d = mesh(); d['source_refs'] = ['r'] * 128
        self.assertEqual(len(solve(d)['source_refs']), 128)
        d['source_refs'] = ['r'] * 129
        self.refused(d, 'FEA1512_SOURCE')
        d['source_refs'] = ['x' * 2048]
        self.assertEqual(len(solve(d)['source_refs'][0]), 2048)
        d['source_refs'] = ['x' * 2049]
        self.refused(d, 'FEA1512_SOURCE')
        for bad in ([5], ['ok', None], {}, (), None, 'url', 0):
            d['source_refs'] = bad
            self.refused(d, 'FEA1512_SOURCE')
        d.pop('source_refs')
        self.assertEqual(solve(d)['source_refs'], [])


class DocumentedBehavior(unittest.TestCase):
    """Behavior pins for documented limits and ordering (peer-stated classification, not owner words; core unchanged)."""

    def test_element_stiffness_underflow_is_checked_at_element_stage(self):
        # Contract (amended): element stiffness overflow/underflow reports NUMERICAL while elements are read,
        # before loads, BCs, anchors and source refs.
        for field, bad in (('loads', 'x'), ('displacements', 'x'), ('source_refs', 'bad')):
            d = mesh(); d['elements'][0]['E'] = 1e-300; d['elements'][0]['A'] = 1e-300
            d[field] = bad
            with self.assertRaises(ValueError) as cm:
                solve(d)
            self.assertEqual(str(cm.exception), 'FEA1512_NUMERICAL')
        d = mesh(); d['elements'][0]['E'] = 1e-300; d['elements'][0]['A'] = 1e-300
        d['displacements'] = []                       # also unanchored: NUMERICAL still first
        with self.assertRaises(ValueError) as cm:
            solve(d)
        self.assertEqual(str(cm.exception), 'FEA1512_NUMERICAL')
        # ordinary stiffness keeps the documented order
        d = mesh(); d['loads'] = 'x'; d['source_refs'] = 'bad'
        with self.assertRaises(ValueError) as cm:
            solve(d)
        self.assertEqual(str(cm.exception), 'FEA1512_LOAD')

    def test_nested_unknown_fields_are_ignored_not_refused(self):
        # Contract residual: nested unknown fields are ignored; thermal strain is not modeled and not detected.
        base = solve(mesh())
        for section, key in (('elements', 'thermal_strain'), ('nodes', 'y'),
                             ('loads', 'follower'), ('displacements', 'rotation')):
            d = mesh(); d[section][0][key] = 1e-3
            self.assertEqual(solve(d), base)

    def test_large_rigid_offset_limit_is_documented_wrong_answer_without_refusal(self):
        # Documented limit: cancellation at a 1e15 prescribed displacement; no certified error bound.
        d = mesh(); d['displacements'][0]['value'] = 1e15
        r = solve(d)                                   # not refused
        self.assertIs(r['requires_engineer_review'], True)
        self.assertGreater(abs(r['elements'][0]['stress'] - 2.0), 0.1)   # exact is 2.0
        d['displacements'][0]['value'] = 1e9           # mild offset stays close to exact
        self.assertAlmostEqual(solve(d)['elements'][0]['stress'], 2.0, places=3)


if __name__ == '__main__':
    unittest.main()
