import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/scarcity_creation99.py'
s=importlib.util.spec_from_file_location('scarci',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def packet():return {'claim':'Declared stock','source_ref':'inventory declaration','total':100,'allocated':99,'claimed_remaining':1,'observed_at':'2026-10-11T12:00:00+00:00','as_of':'2026-10-11T12:01:00+00:00','max_age_seconds':60}
class Tests(unittest.TestCase):
 def refuse(self,d,code):
  with self.assertRaises(m.Scarcity99Error) as c:m.prepare_scarcity(d)
  self.assertEqual(str(c.exception),'SCARCI99: '+code)
 def test_exact_remaining_and_no_execution(self):
  r=m.prepare_scarcity(packet());self.assertEqual(r['remaining'],1);self.assertTrue(r['arithmetic_consistent']);self.assertTrue(r['within_caller_age_limit']);self.assertFalse(r['deployment_authorized']);self.assertFalse(r['real_world_verified'])
 def test_count_edges(self):
  for n in [0,1000000]:
   d=packet();d.update(total=n,allocated=n,claimed_remaining=0);self.assertEqual(m.prepare_scarcity(d)['remaining'],0)
  for n in [-1,1000001,True,1.0,'1']:
   self.refuse(dict(packet(),total=n),'counts must be integer0..1000000')
  self.refuse(dict(packet(),total=98),'allocated exceeds total')
 def test_text_n_nplus1_and_controls(self):
  for k in ['claim','source_ref']:
   self.assertEqual(m.prepare_scarcity(dict(packet(),**{k:'x'*2000}))[k],'x'*2000)
   for v in ['x'*2001,'',None,'x\n','x'+chr(31),'x'+chr(127)]:
    self.refuse(dict(packet(),**{k:v}),'invalid '+k)
 def test_more_exact_time_and_text_edges(self):
  for c in [32,126,160]:self.assertEqual(m.prepare_scarcity(dict(packet(),claim='x'+chr(c)))['claim'],'x'+chr(c))
  d=dict(packet(),observed_at='2026-10-10T12:00:00+00:00',as_of='2026-10-11T12:00:00+00:00',max_age_seconds=86400)
  self.assertEqual(m.prepare_scarcity(d)['age_seconds'],'86400');self.assertTrue(m.prepare_scarcity(d)['within_caller_age_limit'])
  self.assertEqual(m.prepare_scarcity(dict(packet(),as_of=packet()['observed_at']))['age_seconds'],'0')
  stamp='2026-10-11T12:00:00.000000+00:00'
  self.assertEqual(len(stamp),32);self.assertEqual(m.prepare_scarcity(dict(packet(),observed_at=stamp))['age_seconds'],'60')
  self.refuse(dict(packet(),observed_at='2026-10-11T12:00:00.0000000+00:00'),'invalid observed_at')
 def test_age_edges_and_mismatch(self):
  self.assertEqual(m.prepare_scarcity(packet())['age_seconds'],'60')
  self.assertEqual(m.prepare_scarcity(dict(packet(),max_age_seconds=0))['max_age_seconds'],0)
  self.assertFalse(m.prepare_scarcity(dict(packet(),max_age_seconds=59))['within_caller_age_limit'])
  self.assertFalse(m.prepare_scarcity(dict(packet(),claimed_remaining=2))['arithmetic_consistent'])
  self.assertEqual(m.prepare_scarcity(dict(packet(),max_age_seconds=86400))['max_age_seconds'],86400)
  for n in [-1,86401,True]:self.refuse(dict(packet(),max_age_seconds=n),'max_age_seconds must be integer0..86400')
 def test_schema_time_and_immutability(self):
  d=packet();before=d.copy();m.prepare_scarcity(d);self.assertEqual(d,before)
  self.refuse(dict(d,extra=1),'packet schema')
  self.refuse(dict(d,observed_at='2026-10-11T12:00:00'),'invalid observed_at')
  self.refuse(dict(d,observed_at='2026-10-11T12:02:00+00:00'),'observation is in future')
if __name__=='__main__':unittest.main()
