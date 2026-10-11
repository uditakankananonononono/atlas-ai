import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/bargaining_power91.py'
s=importlib.util.spec_from_file_location('barcap',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Caps(unittest.TestCase):
 def test_text_actual_length_before_strip(self):
  import inspect,time
  self.assertIn('type(value)is not str or len(value)>limit or not value.strip()',inspect.getsource(m._text))
  m._text('x'*2000,'position',2000)
  for v in ['x'*2001,'x'*(10*1024*1024)]:
   t=time.perf_counter()
   with self.assertRaises(m.Bargain91Error):m._text(v,'position',2000)
   self.assertLess(time.perf_counter()-t,1)
 def test_weight_raw15_before_regex(self):
  self.assertEqual(m._weight('1000000/1000000'),1)
  for value in ['0'*15,'0'*16,'0'*(10*1024*1024)]:
   if len(value)<=15:continue
   with patch.object(m.re,'fullmatch',side_effect=AssertionError('regex before raw cap')):
    with self.assertRaises(m.Bargain91Error) as cm:m._weight(value)
    self.assertEqual(str(cm.exception),'BARGAIN91: weight raw length exceeds15')
 def test_utility_existing_raw128_before_regex(self):
  self.assertEqual(m._utility('1'*128),m.Fraction('1'*128))
  for value in ['1'*129,'1'*(10*1024*1024)]:
   with patch.object(m.re,'fullmatch',side_effect=AssertionError('regex before cap')):
    with self.assertRaises(m.Bargain91Error):m._utility(value)
 def test_existing_unicode_examples_preserved(self):
  for text,value in [('٣','3'),('٣/4','3/4'),('١٢','12')]:self.assertEqual(str(m._weight(text)),value)
  with self.assertRaises(m.Bargain91Error):m._weight('3/٤')
if __name__=='__main__':unittest.main()
