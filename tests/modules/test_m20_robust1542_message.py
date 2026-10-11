import importlib.util
from pathlib import Path
import re
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/robust_design1542.py'
s=importlib.util.spec_from_file_location('message1542',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class MessagePin(unittest.TestCase):
 def test_valid_grammar17_exact_raw_length_refusal(self):
  value='-12345678/1234567'
  self.assertEqual(len(value),17)
  self.assertIsNotNone(re.fullmatch(r'-?[0-9]+(?:/[1-9][0-9]*)?',value))
  with self.assertRaises(m.UnitError) as cm:m.rational(value)
  self.assertEqual(str(cm.exception),'ROBUST1542: rational raw length exceeds16')
if __name__=='__main__':unittest.main()
