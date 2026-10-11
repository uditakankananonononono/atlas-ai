import importlib.util
from pathlib import Path
import re
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/response_surface_methodology1541.py'
s=importlib.util.spec_from_file_location('message1541',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class MessagePin(unittest.TestCase):
 def test_valid_grammar17_exact_raw_length_refusal(self):
  value='-12345678/1234567'
  self.assertEqual(len(value),17)
  self.assertIsNotNone(re.fullmatch(r'-?[0-9]+(?:/[1-9][0-9]*)?',value))
  with self.assertRaises(m.UnitError) as cm:m.rational(value)
  self.assertEqual(str(cm.exception),'RESPSU1541: rational raw length exceeds16')
 def test_previous_max16_still_accepted(self):
  value='-1234567/1234567';self.assertEqual(len(value),16)
  # Raw length passes, but components exceed the existing1000000 numeric cap.
  with self.assertRaises(m.UnitError) as cm:m.rational(value)
  self.assertEqual(str(cm.exception),'RESPSU1541: rational components exceed1000000')
  self.assertEqual(m.rational('-1000000/1000000'),-1)
if __name__=='__main__':unittest.main()
