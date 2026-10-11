"""Stdlib-only analytical tests; FEA_BASE=1 exercises the unchanged diagnostic."""
import copy
import importlib.util
import math
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / 'backend/app/modules/m20_general_cognitive_worker/axial_fea1512.py'

def solve(data):
    path = CORE
    name = 'solve_axial_bar'
    if os.environ.get('FEA_BASE') == '1':
        path = CORE.with_name('engineering_1510_1559.py')
        name = '_fea'
    spec = importlib.util.spec_from_file_location('fea_under_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, name)(data)

def mesh(n=1, E=10.0, A=2.0, force=4.0):
    return {'model': '1d_axial_linear_elastic',
            'units': {'length': 'm', 'force': 'N', 'modulus': 'Pa', 'area': 'm^2'},
            'nodes': [{'id': str(i), 'x': i/n} for i in range(n+1)],
            'elements': [{'id': 'e'+str(i), 'nodes': [str(i), str(i+1)], 'E': E, 'A': A} for i in range(n)],
            'loads': [{'node': str(n), 'force': force}],
            'displacements': [{'node': '0', 'value': 0.0}], 'source_refs': ['supplied-case']}

def disp(r, node):
    return next(x['displacement'] for x in r['nodes'] if x['id'] == node)

class AxialTests(unittest.TestCase):
    def test_uniform_bar_behavioral_floor(self):
        r = solve(mesh())
        self.assertIn('nodes', r, 'base diagnostic has no solved displacement output')
        self.assertAlmostEqual(disp(r, '1'), .2)
        self.assertAlmostEqual(r['elements'][0]['strain'], .2)
        self.assertAlmostEqual(r['elements'][0]['stress'], 2)
        self.assertAlmostEqual(r['nodes'][0]['reaction'], -4)

    def test_two_elements(self):
        r = solve(mesh(2))
        self.assertAlmostEqual(disp(r, '1'), .1)
        self.assertAlmostEqual(disp(r, '2'), .2)

    def test_nonuniform_material(self):
        d = mesh(2); d['elements'][1]['E'] = 20
        r = solve(d)
        self.assertAlmostEqual(disp(r, '2'), .15)
        self.assertAlmostEqual(r['elements'][1]['stress'], 2)

    def test_prescribed_displacement(self):
        d = mesh(); d['loads'] = []; d['displacements'].append({'node': '1', 'value': .3})
        r = solve(d)
        self.assertAlmostEqual(r['nodes'][0]['reaction'], -6)
        self.assertAlmostEqual(r['nodes'][1]['reaction'], 6)
        self.assertAlmostEqual(r['strain_energy'], .9)

    def test_nonzero_bc_elimination(self):
        d = mesh(2); d['displacements'][0]['value'] = .7
        r = solve(d)
        self.assertAlmostEqual(disp(r, '2'), .9)
        self.assertAlmostEqual(r['nodes'][0]['reaction'], -4)

    def test_restrained_load_reaction(self):
        d = mesh(); d['loads'].append({'node': '0', 'force': 3})
        r = solve(d)
        self.assertAlmostEqual(r['nodes'][0]['reaction'], -7)

    def test_compression(self):
        r = solve(mesh(force=-4))
        self.assertAlmostEqual(disp(r, '1'), -.2)
        self.assertAlmostEqual(r['elements'][0]['stress'], -2)

    def test_force_balance_energy_identity(self):
        d = mesh(5); d['loads'].append({'node': '2', 'force': -1})
        r = solve(d)
        self.assertLess(abs(r['force_balance_residual']), 1e-10)
        self.assertLess(r['equilibrium_residual'], 1e-10)
        self.assertAlmostEqual(r['strain_energy'], r['external_work_half'])

    def test_refinement_smooth_benchmark(self):
        # EA=1, u''=-2, u(0)=0, end traction=0; u=2x-x^2.
        # Equivalent consistent nodal forces from constant axial body load 2.
        errors = []
        for n in (2, 4, 8, 16):
            d = mesh(n, E=1, A=1, force=0)
            d['loads'] = [{'node': str(i), 'force': (1 if i in (0,n) else 2)/n} for i in range(n+1)]
            r = solve(d)
            for i in range(n+1):
                self.assertAlmostEqual(disp(r, str(i)), 2*i/n-(i/n)**2)
            mid = .5/n
            errors.append(abs((disp(r,'0')+disp(r,'1'))/2-(2*mid-mid**2)))
        for a,b in zip(errors, errors[1:]): self.assertAlmostEqual(a/b, 4)

    def test_orientation_and_order_invariance(self):
        d = mesh(3); r = solve(d)
        d['nodes'].reverse(); d['elements'].reverse(); d['loads'].reverse()
        for e in d['elements']: e['nodes'].reverse()
        self.assertEqual(r, solve(d))

    def test_source_and_boundary_no_input_mutation(self):
        d = mesh(); before = copy.deepcopy(d); r = solve(d)
        self.assertEqual(d, before)
        self.assertEqual(r['source_refs'], ['supplied-case'])
        self.assertFalse(r['safety_certified'])
        self.assertEqual(r['model'], '1d_axial_linear_elastic')

    def test_exhaustive_serial_analytical(self):
        for n in (1,2,3,4):
            for E in (1,3,10):
                for F in (-7,0,5):
                    with self.subTest(n=n,E=E,F=F):
                        r = solve(mesh(n,E=E,A=2,force=F))
                        self.assertAlmostEqual(disp(r,str(n)), F/(2*E))

    def assert_refused(self, d, code):
        with self.assertRaisesRegex(ValueError, '^'+code+'$'): solve(d)

    def test_rigid_body(self):
        d = mesh(); d['displacements'] = []; self.assert_refused(d,'FEA1512_SINGULAR')
    def test_disconnected(self):
        d = mesh(); d['nodes'].append({'id':'z','x':3}); self.assert_refused(d,'FEA1512_SINGULAR')
    def test_duplicate_node(self):
        d = mesh(); d['nodes'][1]['id']='0'; self.assert_refused(d,'FEA1512_NODE')
    def test_duplicate_element(self):
        d = mesh(2); d['elements'][1]['id']='e0'; self.assert_refused(d,'FEA1512_ELEMENT')
    def test_unknown_connectivity(self):
        d = mesh(); d['elements'][0]['nodes'][1]='unknown'; self.assert_refused(d,'FEA1512_ELEMENT')
    def test_zero_length(self):
        d = mesh(); d['nodes'][1]['x']=0; self.assert_refused(d,'FEA1512_ELEMENT')
    def test_self_connectivity(self):
        d = mesh(); d['elements'][0]['nodes']=['0','0']; self.assert_refused(d,'FEA1512_ELEMENT')
    def test_material_domain(self):
        for field in ('E','A'):
            for value in (0,-1,float('nan'),float('inf'),True,'10'):
                d = mesh(); d['elements'][0][field]=value
                self.assert_refused(d,'FEA1512_MATERIAL')
    def test_numeric_domain(self):
        for value in (True,float('nan'),float('inf'),'x',1e101):
            d = mesh(); d['nodes'][0]['x']=value; self.assert_refused(d,'FEA1512_NODE')
    def test_units(self):
        d = mesh(); d['units']['length']='mm'; self.assert_refused(d,'FEA1512_UNITS')
    def test_model(self):
        d = mesh(); d['model']='3d'; self.assert_refused(d,'FEA1512_MODEL')
    def test_load_duplicate_or_unknown(self):
        for node in ('1','unknown'):
            d = mesh(); d['loads'].append({'node':node,'force':1}); self.assert_refused(d,'FEA1512_LOAD')
    def test_bc_duplicate_or_unknown(self):
        for node in ('0','unknown'):
            d = mesh(); d['displacements'].append({'node':node,'value':1}); self.assert_refused(d,'FEA1512_BC')
    def test_bounds(self):
        self.assert_refused(mesh(64),'FEA1512_BOUNDS')
        d=mesh(); d['elements']=[]; self.assert_refused(d,'FEA1512_BOUNDS')
    def test_finite_load_and_bc(self):
        d=mesh(); d['loads'][0]['force']=float('nan'); self.assert_refused(d,'FEA1512_LOAD')
        d=mesh(); d['displacements'][0]['value']=True; self.assert_refused(d,'FEA1512_BC')
    def test_exact_node_bound(self):
        self.assertAlmostEqual(disp(solve(mesh(63)), '63'), .2)
        self.assert_refused(mesh(64), 'FEA1512_BOUNDS')
    def test_exact_element_bound(self):
        d=mesh(); d['elements']=[{**d['elements'][0], 'id':str(i)} for i in range(128)]
        self.assertAlmostEqual(disp(solve(d),'1'), .2/128)
        d['elements'].append({**d['elements'][0], 'id':'extra'})
        self.assert_refused(d,'FEA1512_BOUNDS')
    def test_distinct_connected_components_anchored(self):
        d=mesh(); d['nodes'] += [{'id':'2','x':2},{'id':'3','x':3}]
        d['elements'].append({'id':'e1','nodes':['2','3'],'E':10,'A':2})
        d['displacements'].append({'node':'2','value':.5})
        d['loads'].append({'node':'3','force':2})
        self.assertAlmostEqual(disp(solve(d),'3'),.6)
    def test_all_fixed_force_balance(self):
        d=mesh(); d['displacements'].append({'node':'1','value':0})
        r=solve(d); self.assertAlmostEqual(r['nodes'][1]['reaction'],-4)
        self.assertEqual(r['force_balance_residual'],0)
    def test_parallel_elements(self):
        d=mesh(); d['elements'].append({**d['elements'][0],'id':'e1'})
        self.assertAlmostEqual(disp(solve(d),'1'),.1)
    def test_stiffness_underflow(self):
        d=mesh(); d['elements'][0]['E']=1e-300; d['elements'][0]['A']=1e-300
        self.assert_refused(d,'FEA1512_NUMERICAL')
    def test_numerical_overflow(self):
        d=mesh(E=1e-100,A=1e-100,force=1e100)
        self.assert_refused(d,'FEA1512_NUMERICAL')
    def test_unsupported_geometry(self):
        d=mesh(); d['contacts']=[{'type':'3d'}]; self.assert_refused(d,'FEA1512_INPUT')
    def test_input_shape(self):
        self.assert_refused([], 'FEA1512_INPUT')
    def test_source_shape(self):
        d=mesh(); d['source_refs']='url'; self.assert_refused(d,'FEA1512_SOURCE')

if __name__ == '__main__': unittest.main()
