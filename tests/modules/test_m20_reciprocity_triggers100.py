import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/reciprocity_triggers100.py'
s=importlib.util.spec_from_file_location('recipr',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def packet():return {'benefit':'Free guide','strings_attached':False,'expected_return':None,'disclosed_to_recipient':True,'decline_without_penalty':True}
class Tests(unittest.TestCase):
 def refuse(self,d,code):
  with self.assertRaises(m.Reciprocity100Error) as c:m.prepare_reciprocity(d)
  self.assertEqual(str(c.exception),'RECIPR100: '+code)
 def test_transparent_optional_offer(self):
  r=m.prepare_reciprocity(packet());self.assertEqual(r['declared_risk'],'0');self.assertTrue(r['transparent_optional_offer']);self.assertFalse(r['send_authorized']);self.assertFalse(r['real_world_intent_verified']);self.assertEqual(r['no_obligation_language'],'This is offered without obligation. You may decline without penalty.')
 def test_all_declared_risk_combinations_exact(self):
  for strings,expected,want in [(False,None,'0'),(True,None,'3/5'),(False,'reply','2/5'),(True,'reply','1')]:
   r=m.prepare_reciprocity(dict(packet(),strings_attached=strings,expected_return=expected));self.assertEqual(r['declared_risk'],want);self.assertEqual(r['transparent_optional_offer'],want=='0')
 def test_consent_declarations_gate(self):
  for k in ['disclosed_to_recipient','decline_without_penalty']:
   self.assertFalse(m.prepare_reciprocity(dict(packet(),**{k:False}))['transparent_optional_offer'])
 def test_text_n_nplus1(self):
  for k in ['benefit','expected_return']:
   self.assertEqual(m.prepare_reciprocity(dict(packet(),**{k:'x'*2000}))[k],'x'*2000)
   for v in ['x'*2001,'',' ','x\x7f','x'+chr(31),12]:self.refuse(dict(packet(),**{k:v}),'invalid '+k)
 def test_strict_bool_schema_no_mutation(self):
  for k in ['strings_attached','disclosed_to_recipient','decline_without_penalty']:
   for v in [1,0,None,'false']:self.refuse(dict(packet(),**{k:v}),'invalid '+k)
  d=packet();before=d.copy();m.prepare_reciprocity(d);self.assertEqual(d,before)
  self.refuse(dict(d,extra=1),'packet schema');self.refuse(dict(d,benefit=None),'invalid benefit')
if __name__=='__main__':unittest.main()
