import importlib.util
from pathlib import Path
import hashlib
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/release_notes702.py'
s=importlib.util.spec_from_file_location('release702',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def request():return {'version':'1.0.0','audience':'operators','changes':[{'id':'c1','description':'New export','user_visible':True,'breaking':False},{'id':'c2','description':'Changed format','user_visible':False,'breaking':True}],'upgrade_steps':['Review format'],'known_issues':['Preview only']}
class Tests(unittest.TestCase):
 def refuse(self,reason,data):
  with self.assertRaises(ValueError) as cm:m.plan_release(data)
  self.assertEqual(str(cm.exception),'RELEAS702: '+reason)
 def test_draft(self):
  r=m.plan_release(request());self.assertEqual(r['highlights'],[{'id':'c1','description':'New export'}]);self.assertEqual(r['breaking_changes'],[{'id':'c2','description':'Changed format'}]);self.assertEqual(r['generated_from_change_ids'],['c1','c2']);self.assertFalse(r['published']);self.assertFalse(r['repository_verified']);self.assertFalse(r['release_authorized'])
 def test_nonmutation(self):
  d=request();r=m.plan_release(d);r['highlights'][0]['description']='other';self.assertEqual(d,request());self.assertEqual(m.plan_release(d),m.plan_release(d))
 def test_exact_flags(self):
  for field in ['user_visible','breaking']:
   for v in [1,0,'true',None]:
    d=request();d['changes'][0][field]=v;self.refuse('flag must be bool',d)
 def test_duplicate(self):
  d=request();d['changes'][1]['id']='c1';self.refuse('duplicate change id',d)
 def test_shape_unknown_missing(self):
  self.refuse('request must be object',[]);d=request();d['send']=True;self.refuse('request fields invalid',d)
  d=request();del d['audience'];self.refuse('request fields invalid',d)
  d=request();d['changes'][0]['extra']='x';self.refuse('change fields invalid',d)
 def test_text_boundary(self):
  for v in ['',' ','a\x00b','a\x1fb','x'*1001]:
   d=request();d['changes'][0]['description']=v;self.refuse('text must be 1..1000 characters without controls',d)
  d=request();d['changes'][0]['description']='x'*1000;self.assertEqual(len(m.plan_release(d)['highlights'][0]['description']),1000)
 def test_lists(self):
  d=request();d['changes']=[];self.assertEqual(m.plan_release(d)['generated_from_change_ids'],[])
  for field in ['changes','upgrade_steps','known_issues']:
   d=request();d[field]='x';self.refuse('list required',d)
  d=request();d['changes']=[d['changes'][0]]*10001;self.refuse('list exceeds 10000',d)
 def test_no_execution_api(self):
  for n in ['send','publish','execute','fetch','run_git']:self.assertFalse(hasattr(m,n))
class PolicyPins(unittest.TestCase):
 refuse=Tests.refuse
 def test_full_cf_and_explicit_pins(self):
  import unicodedata
  codes=[i for i in range(0x110000) if unicodedata.category(chr(i))=='Cf']
  self.assertIn(0xAD,codes);self.assertIn(0x2060,codes)
  for code in codes:
   d=request();d['changes'][0]['description']='a'+chr(code)+'b';self.refuse('text must be 1..1000 characters without controls',d)
 def test_zs_accepted(self):
  d=request();d['changes'][0]['description']='a\u00a0b';self.assertEqual(m.plan_release(d)['highlights'][0]['description'],'a\u00a0b')
 def test_count_before_set_exact_dict(self):
  from unittest.mock import patch
  def no_set(value):raise AssertionError('set constructed before count refusal')
  with patch.object(m,'set',no_set,create=True):
   self.refuse('request fields invalid',{str(i):None for i in range(65)})
  d=request();d['changes'][0]={str(i):None for i in range(65)}
  real_set=set
  def request_only_set(*args):
   if not args:return real_set()
   value=args[0]
   if value is d:return real_set(value)
   raise AssertionError('change set constructed before count refusal')
  with patch.object(m,'set',request_only_set,create=True):
   self.refuse('change fields invalid',d)
 def test_cap_before_strip(self):
  class NoStrip(str):
   def strip(self):raise AssertionError('strip too early')
  d=request();d['version']=NoStrip('x'*1001);self.refuse('text must be 1..1000 characters without controls',d)

class StrictTypePins(unittest.TestCase):
 refuse=Tests.refuse
 def test_request_dict_subclass_refused(self):
  class Sub(dict):pass
  self.refuse('request must be object',Sub(request()))
 def test_change_dict_subclass_refused(self):
  class Sub(dict):pass
  d=request();d['changes'][0]=Sub(d['changes'][0]);self.refuse('change fields invalid',d)
 def test_all_list_subclasses_refused(self):
  class Sub(list):pass
  for field in ['changes','upgrade_steps','known_issues']:
   with self.subTest(field=field):
    d=request();d[field]=Sub(d[field]);self.refuse('list required',d)
 def test_all_text_subclasses_refused(self):
  class Sub(str):pass
  for field in ['version','audience']:
   with self.subTest(field=field):
    d=request();d[field]=Sub(d[field]);self.refuse('text must be 1..1000 characters without controls',d)
  for field in ['id','description']:
   with self.subTest(field=field):
    d=request();d['changes'][0][field]=Sub(d['changes'][0][field]);self.refuse('text must be 1..1000 characters without controls',d)
  for field in ['upgrade_steps','known_issues']:
   with self.subTest(field=field):
    d=request();d[field][0]=Sub(d[field][0]);self.refuse('text must be 1..1000 characters without controls',d)

class StrictKeyPins(unittest.TestCase):
 refuse=Tests.refuse
 def test_request_str_subclass_key(self):
  class Sub(str):pass
  d=request();d[Sub('version')]=d.pop('version');self.refuse('unknown field',d)
 def test_change_str_subclass_key(self):
  class Sub(str):pass
  d=request();r=d['changes'][0];r[Sub('id')]=r.pop('id');self.refuse('unknown field',d)
 def test_nonstring_key_generic_refusal(self):
  d=request();d[7]=d.pop('version');self.refuse('unknown field',d)
  d=request();r=d['changes'][0];r[7]=r.pop('id');self.refuse('unknown field',d)

class ClosingPins(unittest.TestCase):
 refuse=Tests.refuse
 def test_list_cap_exactly_10000_accepted_10001_refused(self):
  d=request();d['changes']=[{'id':str(i),'description':'x','user_visible':False,'breaking':False} for i in range(10000)]
  self.assertEqual(len(m.plan_release(d)['generated_from_change_ids']),10000)
  d['changes'].append({'id':'10000','description':'x','user_visible':False,'breaking':False});self.refuse('list exceeds 10000',d)
  for field in ['upgrade_steps','known_issues']:
   with self.subTest(field=field):
    d=request();d[field]=['x']*10000;self.assertEqual(len(m.plan_release(d)[field]),10000)
    d[field]=['x']*10001;self.refuse('list exceeds 10000',d)
 def test_snapshot_independent_of_key_order(self):
  a=request()
  b={k:a[k] for k in reversed(list(a))}
  b['changes']=[{k:c[k] for k in reversed(list(c))} for c in a['changes']]
  self.assertNotEqual(list(a),list(b));self.assertNotEqual(list(a['changes'][0]),list(b['changes'][0]))
  self.assertEqual(m.plan_release(a)['snapshot_sha256'],m.plan_release(b)['snapshot_sha256'])
 def test_snapshot_literal_digest_ascii(self):
  self.assertEqual(m.plan_release(request())['snapshot_sha256'],'636689ec8c66db98429620d099a2004136fe64124b83a9481249b5cdeb891d4c')
 def test_snapshot_non_ascii_is_raw_utf8_sorted_compact_json(self):
  d=request();d['changes']=[d['changes'][0]];d['changes'][0]['description']='caf\u00e9'
  exact='{"audience":"operators","changes":[{"breaking":false,"description":"caf\u00e9","id":"c1","user_visible":true}],"known_issues":["Preview only"],"upgrade_steps":["Review format"],"version":"1.0.0"}'
  digest=m.plan_release(d)['snapshot_sha256']
  self.assertEqual(digest,hashlib.sha256(exact.encode('utf-8')).hexdigest())
  self.assertEqual(digest,'31dffa380dd3c1325c346aa9877d522aba5dedf952ba0caaa4e973b2ea9f012f')
  self.assertNotEqual(digest,'7f3080fcb9fd6198ed773ea9f76e29ff564944fc7c2214bbe44d12d6c7da61e5')

if __name__=='__main__':unittest.main(verbosity=2)
