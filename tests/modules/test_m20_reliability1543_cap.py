import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/reliability_testing1543.py'
s=importlib.util.spec_from_file_location('cap1543',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Caps(unittest.TestCase):
 def test_text_raw_cap_and_large_input(self):
  for value in ['x'*101,'x'*(10*1024*1024)]:
   with patch.object(m,'any',side_effect=AssertionError('scan before cap'),create=True):
    with self.assertRaises(m.UnitError):m.text(value)
  self.assertEqual(m.text('x'*100),'x'*100)
 def test_numeric_raw_cap_before_regex_or_copy(self):
  for value in ['1'*17,'1'*(10*1024*1024)]:
   with patch.object(m.re,'fullmatch',side_effect=AssertionError('regex before cap')):
    with self.assertRaises(m.UnitError):m.rational(value)
  self.assertEqual(m.rational('-1000000/1000000'),-1)
 def test_first_operations_source_and_oversize_no_strip(self):
  import inspect,time
  self.assertIn('type(v)is not str or len(v)>100 or not v.strip()',inspect.getsource(m.text))
  value='x'*(10*1024*1024);start=time.perf_counter()
  with self.assertRaises(m.UnitError):m.text(value)
  self.assertLess(time.perf_counter()-start,1)
if __name__=='__main__':unittest.main()
