import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/reciprocity_triggers100.py'
s=importlib.util.spec_from_file_location('cap100',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def packet():return {'benefit':'gift','strings_attached':False,'expected_return':None,'disclosed_to_recipient':True,'decline_without_penalty':True}
class Caps(unittest.TestCase):
 def test_text_cap_first(self):
  import inspect,time
  self.assertIn('type(value)is not str or len(value)>2000 or not value.strip()',inspect.getsource(m.prepare_reciprocity))
  for key in ['benefit','expected_return']:
   self.assertEqual(m.prepare_reciprocity(dict(packet(),**{key:'x'*2000}))[key],'x'*2000)
   for value in ['x'*2001,'x'*(10*1024*1024)]:
    t=time.perf_counter()
    with self.assertRaises(m.Reciprocity100Error):m.prepare_reciprocity(dict(packet(),**{key:value}))
    self.assertLess(time.perf_counter()-t,1)
if __name__=='__main__':unittest.main()
