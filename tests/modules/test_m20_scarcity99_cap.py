import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/scarcity_creation99.py'
s=importlib.util.spec_from_file_location('cap99',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def packet():return {'claim':'claim','source_ref':'source','total':1,'allocated':0,'claimed_remaining':1,'observed_at':'2026-10-11T12:00:00+00:00','as_of':'2026-10-11T12:00:00+00:00','max_age_seconds':0}
class Caps(unittest.TestCase):
 def test_text_cap_first(self):
  import inspect,time
  self.assertIn('type(value)is not str or len(value)>2000 or not value.strip()',inspect.getsource(m.prepare_scarcity))
  for key in ['claim','source_ref']:
   self.assertEqual(m.prepare_scarcity(dict(packet(),**{key:'x'*2000}))[key],'x'*2000)
   for value in ['x'*2001,'x'*(10*1024*1024)]:
    t=time.perf_counter()
    with self.assertRaises(m.Scarcity99Error):m.prepare_scarcity(dict(packet(),**{key:value}))
    self.assertLess(time.perf_counter()-t,1)
 def test_timestamp_cap_first(self):
  for key in ['observed_at','as_of']:
   for value in ['x'*41,'x'*(10*1024*1024)]:
    with self.assertRaises(m.Scarcity99Error):m.prepare_scarcity(dict(packet(),**{key:value}))
if __name__=='__main__':unittest.main()
