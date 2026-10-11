import copy
import importlib.util
from pathlib import Path
import unittest
CORE=Path(__file__).resolve().parents[2]/'backend/app/modules/m20_general_cognitive_worker/criminal_appeals1261.py'
s=importlib.util.spec_from_file_location('crimin1261',CORE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
BOUNDARY="Legal work product for review, not legal advice. Licensed counsel must verify jurisdiction, currency, citations, facts, duties, deadlines and strategy before use."
def issue(id='i1',order_id='o1',status='preserved',cites=('c1',),std='caller label',ref='ref text',sought='vacatur',note='limit note'):
 return {'id':id,'order_id':order_id,'label':'Issue label','preservation':{'status':status,'cite_ids':list(cites)},'review_standard':{'label':std,'authority_ref':ref},'remedy':{'sought':sought,'limit_note':note}}
def packet(**kw):
 d={'jurisdiction':'Synthetic Jurisdiction','as_of':'2026-01-15','orders':[{'id':'o1','kind':'judgment','entered_on':'2025-12-01','court':'Synthetic Court'}],'record_cites':[{'id':'c1','document':'Transcript volume','page':12}],'issues':[issue()]}
 d.update(kw);return d
def refusal(test,d,field,reason=None):
 with test.assertRaises(m.Crimin1261Error) as cm:m.map_appeal_preservation(d)
 msg=str(cm.exception);test.assertTrue(msg.startswith('CRIMIN1261:'+field+':'),msg)
 if reason:test.assertEqual(msg,'CRIMIN1261:'+field+':'+reason)
 return msg
class T(unittest.TestCase):
 def test_happy_map_and_boundaries(self):
  r=m.map_appeal_preservation(packet())
  self.assertEqual(r['scope'],'caller_declared_appeal_bookkeeping_only')
  self.assertEqual(r['boundary'],BOUNDARY)
  for k in ('merit_assessed','outcome_predicted','deadlines_computed','authority_verified','record_verified','filing_or_external_effect'):self.assertIs(r[k],False,k)
  self.assertIsNone(r['legal_conclusion']);self.assertEqual(r['review_state'],'counsel_review_required')
  row=r['issues'][0];self.assertEqual(row['gaps'],[])
  self.assertEqual(row['record_cites'],[{'id':'c1','document':'Transcript volume','page':12}])
  self.assertEqual(row['order']['id'],'o1');self.assertEqual(r['summary']['issue_count'],1)
 def test_gaps_flagged(self):
  d=packet(record_cites=[{'id':'c1','document':'Doc','page':1}],issues=[
   issue('a',status='preserved',cites=()),issue('b',status='unknown'),issue('c',status='not_preserved'),
   issue('d',ref=None),issue('e',sought=None),issue('f',note=None)])
  g={x['id']:x['gaps'] for x in m.map_appeal_preservation(d)['issues']}
  self.assertEqual(g['a'],['preserved_declared_without_record_cite'])
  self.assertEqual(g['b'],['preservation_status_unknown'])
  self.assertEqual(g['c'],['declared_not_preserved'])
  self.assertEqual(g['d'],['review_standard_authority_ref_missing'])
  self.assertEqual(g['e'],['remedy_sought_missing']);self.assertEqual(g['f'],['remedy_limit_note_missing'])
  r=m.map_appeal_preservation(d);self.assertEqual(r['summary']['issues_with_gaps'],6)
 def test_deterministic_sorted_and_no_mutation(self):
  d=packet(issues=[issue('z'),issue('a')]);c=copy.deepcopy(d)
  r1=m.map_appeal_preservation(d);r2=m.map_appeal_preservation(d)
  self.assertEqual(d,c);self.assertEqual(r1,r2);self.assertEqual([x['id'] for x in r1['issues']],['a','z'])
  r1['issues'][0]['gaps'].append('x');self.assertEqual(m.map_appeal_preservation(d)['issues'][0]['gaps'],[])
 def test_unknown_references_refused(self):
  refusal(self,packet(issues=[issue(order_id='nope')]),'issues.order_id','unknown order id')
  refusal(self,packet(issues=[issue(cites=('nope',))]),'issues.preservation.cite_ids','unknown record cite id')
 def test_duplicates_refused(self):
  refusal(self,packet(issues=[issue('a'),issue('a')]),'issues.id','duplicate id')
  o=packet()['orders'][0];refusal(self,packet(orders=[o,dict(o)]),'orders.id','duplicate id')
  refusal(self,packet(record_cites=[{'id':'c1','document':'D','page':1}]*2),'record_cites.id','duplicate id')
  refusal(self,packet(issues=[issue(cites=('c1','c1'))]),'issues.preservation.cite_ids','duplicate cite id')
 def test_schema_exactness(self):
  d=packet();d['extra']=1;refusal(self,d,'packet','unexpected or missing keys')
  d=packet();del d['jurisdiction'];refusal(self,d,'packet','unexpected or missing keys')
  d=packet();d['issues'][0]['merit']='strong';refusal(self,d,'issues','unexpected or missing keys')
  d=packet();d['issues'][0]['preservation']['x']=1;refusal(self,d,'issues.preservation','unexpected or missing keys')
  d=packet();d['orders'][0]['x']=1;refusal(self,d,'orders','unexpected or missing keys')
  for bad in (None,[],'x',1):
   with self.assertRaises(m.Crimin1261Error):m.map_appeal_preservation(bad)
 def test_enums(self):
  refusal(self,packet(issues=[issue(status='strong')]),'issues.preservation.status','not an allowed value')
  d=packet();d['orders'][0]['kind']='verdict';refusal(self,d,'orders.kind','not an allowed value')
  for k in ('judgment','sentence','post_trial_order','suppression_ruling','other_declared'):
   d=packet();d['orders'][0]['kind']=k;m.map_appeal_preservation(d)
 def test_dates(self):
  for bad in ('2026-1-5','2026-13-01','2026-02-30','20260115','2026-01-15T00:00','',' 2026-01-15','٢٠٢٦-٠١-١٥',20260115,None):
   d=packet(as_of=bad)
   with self.assertRaises(m.Crimin1261Error):m.map_appeal_preservation(d)
  d=packet();d['orders'][0]['entered_on']='2027-01-01';refusal(self,d,'orders.entered_on','after as_of')
  d=packet();d['orders'][0]['entered_on']='2026-01-15';m.map_appeal_preservation(d)
 def test_page_strict_int(self):
  for bad in (True,0,-1,1.0,'3',100001,None):
   d=packet();d['record_cites'][0]['page']=bad;refusal(self,d,'record_cites.page')
  for ok in (1,100000):
   d=packet();d['record_cites'][0]['page']=ok;m.map_appeal_preservation(d)
 def test_text_rules(self):
  for bad in ('','   ','a\x00b','a\nb','a\x7fb',5,None,'x'*2001):
   refusal(self,packet(jurisdiction=bad),'jurisdiction')
  m.map_appeal_preservation(packet(jurisdiction='x'*2000))
  for bad in ('a\u2028b','a\u200bb','a\u202eb','a\x85b'):
   refusal(self,packet(jurisdiction=bad),'jurisdiction')
 def test_id_rules(self):
  for bad in ('','a b','a'*101,'a/b','\u00e9',5,None):
   d=packet();d['orders'][0]['id']=bad;refusal(self,d,'orders.id')
  d=packet(issues=[issue(id='a'*100)]);m.map_appeal_preservation(d)
 def test_optional_fields_none_only(self):
  refusal(self,packet(issues=[issue(ref='')]),'issues.review_standard.authority_ref')
  refusal(self,packet(issues=[issue(sought=5)]),'issues.remedy.sought')
 def test_caps(self):
  refusal(self,packet(orders=[]),'orders','must have 1..50 entries')
  refusal(self,packet(issues=[]),'issues','must have 1..100 entries')
  refusal(self,packet(record_cites=[]),'record_cites','must have 1..500 entries')
  o=[{'id':'o%d'%i,'kind':'judgment','entered_on':'2025-12-01','court':'C'} for i in range(51)]
  refusal(self,packet(orders=o),'orders','must have 1..50 entries')
  refusal(self,packet(issues=[issue('i%d'%i) for i in range(101)]),'issues','must have 1..100 entries')
  refusal(self,packet(issues=[issue(cites=['c%d'%i for i in range(51)])]),'issues.preservation.cite_ids','must have 0..50 entries')
  cs=[{'id':'c%d'%i,'document':'D','page':1} for i in range(501)];refusal(self,packet(record_cites=cs),'record_cites','must have 1..500 entries')
  m.map_appeal_preservation(packet(issues=[issue('i%d'%i) for i in range(100)]))
 def test_cap_before_scan(self):
  refusal(self,packet(issues=[issue('i%d'%i) for i in range(101)],orders=[{'bad':1}]),'issues','must have 1..100 entries')
 def test_no_request_text_in_refusal(self):
  secret='SENTINEL-TEXT-XYZ'
  d=packet();d['orders'][0]['court']=secret+'\x00'
  self.assertNotIn(secret,refusal(self,d,'orders.court'))
  d=packet();d['bogus_'+secret]=1;self.assertNotIn(secret,refusal(self,d,'packet'))
 def test_merit_keys_never_emitted(self):
  r=m.map_appeal_preservation(packet());s=repr(r).lower()
  for w in ('likely','strong','weak','prevail','probab','reversible','harmless'):self.assertNotIn(w,s)
 def test_bool_not_accepted_as_container_or_text(self):
  refusal(self,packet(orders=True),'orders');refusal(self,packet(issues={'a':1}),'issues')
  refusal(self,packet(issues=[issue(cites='c1')]),'issues.preservation.cite_ids')
 def test_tuple_cites_not_accepted(self):
  d=packet();d['issues'][0]['preservation']['cite_ids']=('c1',);refusal(self,d,'issues.preservation.cite_ids')
 def test_unhandled_exceptions_never_leak(self):
  for bad in ({'jurisdiction':{}},):
   with self.assertRaises(m.Crimin1261Error):m.map_appeal_preservation(dict(packet(),**bad))
 def test_dict_subclass_refused(self):
  class D(dict):pass
  with self.assertRaises(m.Crimin1261Error):m.map_appeal_preservation(D(packet()))
  d=packet();d['orders'][0]=D(d['orders'][0]);refusal(self,d,'orders')
 def test_output_cites_not_shared_between_issues(self):
  r=m.map_appeal_preservation(packet(issues=[issue('a'),issue('b')]))
  r['issues'][0]['record_cites'][0]['page']=999
  self.assertEqual(r['issues'][1]['record_cites'][0]['page'],12)
 def test_policy_count_before_set_construction(self):
  seen=[]
  def spy(*a):
   if a and hasattr(a[0],'__len__'):seen.append(len(a[0]))
   return set(*a)
  big={('k%d'%i):1 for i in range(1000)}
  m.set=spy
  try:
   for d in (big,packet(orders=[big]),packet(issues=[dict(big)]),packet(record_cites=[dict(big)])):
    with self.assertRaises(m.Crimin1261Error):m.map_appeal_preservation(d)
  finally:del m.set
  self.assertEqual([n for n in seen if n>10],[])
 def test_policy_cf_pins_and_full_category(self):
  import sys
  cf=[chr(c) for c in range(sys.maxunicode+1) if __import__('unicodedata').category(chr(c))=='Cf']
  self.assertGreater(len(cf),100)
  for ch in ['\u00ad','\u2060']+cf:
   with self.assertRaises(m.Crimin1261Error):m.map_appeal_preservation(packet(jurisdiction='a'+ch+'b'))
 def test_policy_zl_zp_refused_zs_accepted(self):
  for ch in ('\u2028','\u2029'):refusal(self,packet(jurisdiction='a'+ch+'b'),'jurisdiction')
  for ch in ('\u00a0','\u2003','\u3000',' '):m.map_appeal_preservation(packet(jurisdiction='a'+ch+'b'))
 def test_policy_surrogate_not_a_new_refusal(self):
  r=m.map_appeal_preservation(packet(jurisdiction='a\ud800b'));self.assertEqual(r['jurisdiction'],'a\ud800b')
 def test_enum_type_then_raw_cap_before_membership(self):
  calls=[]
  class Spy:
   def __eq__(self,o):calls.append('eq');return False
   __hash__=None
  def kind(v):
   d=packet();d['orders'][0]['kind']=v;return d
  def status(v):return packet(issues=[issue(status=v)])
  for bad in (Spy(),b'judgment',5,None,['judgment'],True,'x'*33,'x'*100000,'judgment'+'\u00ad'*40):
   refusal(self,kind(bad),'orders.kind','must be bounded enum text')
   refusal(self,status(bad),'issues.preservation.status','must be bounded enum text')
  self.assertEqual(calls,[])
  refusal(self,kind('verdict'),'orders.kind','not an allowed value')
  refusal(self,status('strong'),'issues.preservation.status','not an allowed value')
  refusal(self,kind('x'*32),'orders.kind','not an allowed value')
 def test_str_subclass_key_refused_everywhere(self):
  class K(str):pass
  def swap(d,name):
   d[K(name)]=d.pop(name);return d
  d=swap(packet(),'jurisdiction');refusal(self,d,'packet','unexpected or missing keys')
  d=packet();d['orders'][0]=swap(d['orders'][0],'court');refusal(self,d,'orders','unexpected or missing keys')
  d=packet();d['record_cites'][0]=swap(d['record_cites'][0],'page');refusal(self,d,'record_cites','unexpected or missing keys')
  d=packet();d['issues'][0]=swap(d['issues'][0],'label');refusal(self,d,'issues','unexpected or missing keys')
  d=packet();d['issues'][0]['preservation']=swap(d['issues'][0]['preservation'],'status');refusal(self,d,'issues.preservation','unexpected or missing keys')
  d=packet();d['issues'][0]['review_standard']=swap(d['issues'][0]['review_standard'],'label');refusal(self,d,'issues.review_standard','unexpected or missing keys')
  d=packet();d['issues'][0]['remedy']=swap(d['issues'][0]['remedy'],'sought');refusal(self,d,'issues.remedy','unexpected or missing keys')
  d={K(k):v for k,v in packet().items()};refusal(self,d,'packet','unexpected or missing keys')
  class E(str):
   def __eq__(self,o):raise AssertionError('key eq called')
   __hash__=str.__hash__
  d=packet();d[E('jurisdiction')]=d.pop('jurisdiction');refusal(self,d,'packet','unexpected or missing keys')
 def test_review_standard_output_pinned_exactly(self):
  r=m.map_appeal_preservation(packet(issues=[issue(std='Std label',ref='Ref text')]))
  self.assertEqual(r['issues'][0]['review_standard'],{'label':'Std label','authority_ref':'Ref text','declared_by_caller':True,'verified':False})
  self.assertIs(r['issues'][0]['review_standard']['verified'],False)
  self.assertIs(r['issues'][0]['review_standard']['declared_by_caller'],True)
 def test_review_standard_null_authority_ref_pinned(self):
  r=m.map_appeal_preservation(packet(issues=[issue(std='Std label',ref=None)]))
  self.assertEqual(r['issues'][0]['review_standard'],{'label':'Std label','authority_ref':None,'declared_by_caller':True,'verified':False})
  self.assertEqual(r['issues'][0]['gaps'],['review_standard_authority_ref_missing'])
if __name__=='__main__':unittest.main()
