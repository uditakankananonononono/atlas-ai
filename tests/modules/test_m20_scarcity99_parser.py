import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/scarcity_creation99.py'
s=importlib.util.spec_from_file_location('parse99',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def packet():return {'claim':'a','source_ref':'b','total':1,'allocated':0,'claimed_remaining':1,'observed_at':'2026-10-10T00:00:00Z','as_of':'2026-10-11T00:00:10Z','max_age_seconds':86400}
class Parser(unittest.TestCase):
 def test_day_microseconds(self):
  r=m.prepare_scarcity(packet());self.assertEqual(r['age_seconds'],'86410');self.assertFalse(r['within_caller_age_limit'])
  d=packet();d.update(observed_at='2026-10-11T00:00:00.1Z',as_of='2026-10-11T00:00:00.123456Z')
  self.assertEqual(m.prepare_scarcity(d)['age_seconds'],'733/31250')
 def test_pass_z_offsets_and_fraction(self):
  for value in ['2026-10-11T10:00:00Z','2026-10-11T10:00:00+05:30','2026-10-11T10:00:00-08:00','2026-10-11T10:00:00.1Z','2026-10-11T10:00:00.123456Z']:
   d=packet();d.update(observed_at=value,as_of=value);self.assertEqual(m.prepare_scarcity(d)['age_seconds'],'0')
  d=packet();d.update(observed_at='2026-10-11T10:00:00Z',as_of='2026-10-11T10:00:00+00:00');self.assertEqual(m.prepare_scarcity(d)['age_seconds'],'0')
 def test_refuse_exact_field_no_value(self):
  bad=['2026-10-11T00:00:00.1234567Z','2026-10-11 00:00:00Z','2026-10-11t00:00:00Z','2026-10-11T00:00:00z','2026-10-11T24:00:00Z','2026-10-11T00:00:60Z','2026-W41-7T00:00:00Z','20261011T000000+0000','٢٠٢٦-10-11T00:00:00Z','2026-10-11T00:00:00Z\n','2026-10-11T00:00:00',None,'2026-02-30T00:00:00Z','2026-10-11T00:00:00+24:00','2026-10-11T00:00:00+00:60']
  for field in ['observed_at','as_of']:
   for value in bad:
    with self.subTest(field=field,value=value):
     with self.assertRaises(m.Scarcity99Error) as cm:m.prepare_scarcity(dict(packet(),**{field:value}))
     self.assertEqual(str(cm.exception),'SCARCI99: invalid '+field)
 def test_unicode_echo_hygiene(self):
  for field in ['claim','source_ref']:
   for code in [0x85,0x200B,0x202E,0x2028,0x2029,0xFEFF,127]:
    with self.assertRaises(m.Scarcity99Error):m.prepare_scarcity(dict(packet(),**{field:'a'+chr(code)+'b'}))
   value='a\u00a0b';self.assertEqual(m.prepare_scarcity(dict(packet(),**{field:value}))[field],value)
 def test_raw40_and41_before_regex_and_str_subclass(self):
  from unittest.mock import patch
  class S(str):pass
  self.assertEqual(m.prepare_scarcity(dict(packet(),observed_at=S('2026-10-10T00:00:00Z')))['age_seconds'],'86410')
  for value in ['x'*41,'x'*(10*1024*1024)]:
   with patch.object(m.re,'fullmatch',side_effect=AssertionError('regex before raw cap')):
    with self.assertRaises(m.Scarcity99Error):m.prepare_scarcity(dict(packet(),observed_at=value))
if __name__=='__main__':unittest.main()
