"""Exact ASCII control boundary regression; citation runtime remains frozen."""
import importlib.util
from pathlib import Path
import unittest
PATH=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/legal_citations1287.py'
s=importlib.util.spec_from_file_location('citations1287_boundary',PATH)
c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
def citation(case_name):
    return {'format':'reporter_case','case_name':case_name,'volume':12,'reporter':'R. 2d','page':34,'court':'Example Court','year':2026}
class AsciiControlBoundaryTests(unittest.TestCase):
    def test_u001f_refused_exact_code_and_message(self):
        with self.assertRaisesRegex(ValueError,r'^CITE1287: case_name must be text of 1\.\.500 characters without controls$'):
            c.normalize_citation(citation('Example\x1fv. Sample'))
    def test_u0000_refused_exact_code_and_message(self):
        with self.assertRaisesRegex(ValueError,r'^CITE1287: case_name must be text of 1\.\.500 characters without controls$'):
            c.normalize_citation(citation('Example\x00v. Sample'))
    def test_u0020_accepted_exact_output(self):
        out=c.normalize_citation(citation('Example\x20v. Sample'))
        self.assertEqual(out['components']['case_name'],'Example v. Sample')
        self.assertEqual(out['normalized'],'Example v. Sample, 12 R. 2d 34 (Example Court 2026)')
if __name__=='__main__':unittest.main(verbosity=2)
