import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/c36/concepts.py'
s=importlib.util.spec_from_file_location('s57',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def page(i='1',title='Alpha',cats=None,links=None):return {'id':i,'title':title,'categories':[] if cats is None else cats,'links':[] if links is None else links}
def run(pages=None):return m.run(dict(as_of='2026-10-11',pages=[page()] if pages is None else pages))
class ConceptsTests(unittest.TestCase):
 def refuse(self,code,request):
  with self.assertRaises(ValueError) as cm:m.run(request)
  self.assertEqual(str(cm.exception),'VENT_REFUSED_'+code)
 def test_labelled_pair_and_ranking(self):
  r=run([page(cats=['Beta','Beta'],links=['Beta']),page('2','Gamma',links=['Delta'])])
  self.assertEqual(r['coverage'],{'pages_supplied':2,'nodes':4,'stubs':2,'edges':3})
  self.assertEqual(r['edges'],[{'source':'alpha','target':'beta','kind':'category'},{'source':'alpha','target':'beta','kind':'link'},{'source':'gamma','target':'delta','kind':'link'}])
  self.assertEqual(r['top_concepts'],['alpha','beta','delta','gamma']);self.assertEqual({n['key']:n['degree'] for n in r['nodes']},{'alpha':2,'beta':2,'delta':1,'gamma':1})
  self.assertEqual(r['clusters'],[{'id':'alpha','nodes':['alpha','beta']},{'id':'delta','nodes':['delta','gamma']}])
 def test_merge_promote_first_title(self):
  r=run([page('1',' A   B ',links=['c']),page('2','a b'),page('3','C')]);self.assertEqual(len(r['nodes']),2);self.assertEqual(r['nodes'][0]['title'],' A   B ');self.assertFalse(r['nodes'][1]['stub'])
 def test_fixture40(self):
  pages=[page(str(i),'topic '+str(i),links=['stub']) for i in range(38)]+[page('38','TOPIC 0'),page('39','isolated')]
  r=run(pages);self.assertEqual(r['coverage'],{'pages_supplied':40,'nodes':40,'stubs':1,'edges':38});self.assertEqual(len(r['clusters']),2)
 def test_forbidden_precedence_recursive(self):
  self.refuse('SEND:approval',{'pages':[{'PAY':1,'Fetch':1,'APPROVAL':1,'send':1}],7:0})
  for k,reason in [('fetch','EFFECT'),('token','SEND'),('api-key','NOCREDS'),('checkout','SPEND')]:self.refuse(reason+':'+k.replace('-','_'),{'x':[{'deep':{k:True}}]})
 def test_unknown_no_echo(self):
  self.refuse('UNKNOWN:request',{'not_secret_user_label':1});self.refuse('UNKNOWN:pages',{'as_of':'2026-10-11','pages':[dict(page(),odd=1)]});self.refuse('BAD_TYPE:key',{'as_of':'2026-10-11','pages':[{1:'x'}]})
 def test_duplicate(self):self.refuse('BAD_TYPE:pages',{'as_of':'2026-10-11','pages':[page(),page()]})
 def test_caps_before_unicode(self):
  for field,cap in [('title',200),('id',128)]:
   row=page();row[field]='x'*cap;run([row]);row[field]='\x00'+'x'*cap;self.refuse('OVERSIZE:'+field,{'as_of':'2026-10-11','pages':[row]})
  for field,count in [('categories',50),('links',200)]:
   row=page();row[field]=['x']*count;run([row]);row[field]=['x']*(count+1);self.refuse('OVERSIZE:'+field,{'as_of':'2026-10-11','pages':[row]})
   row[field]=['x'*201];self.refuse('OVERSIZE:'+field,{'as_of':'2026-10-11','pages':[row]})
  self.refuse('OVERSIZE:pages',{'as_of':'2026-10-11','pages':[page()]*20001})
 def test_caps_global_before_unicode(self):self.refuse('OVERSIZE:title',{'as_of':'2026-10-11','pages':[page('1','bad\x00'),page('2','x'*201)]})
 def test_types_empty_date(self):
  for val in [None,[],True]:self.refuse('BAD_TYPE:request',val)
  self.refuse('EMPTY',{'as_of':'2026-10-11','pages':[]});self.refuse('BAD_TYPE:pages',{'as_of':'2026-10-11','pages':[False]});self.refuse('BAD_TYPE:as_of',{'as_of':'2026-02-30','pages':[page()]});self.refuse('EMPTY:title',{'as_of':'2026-10-11','pages':[page(title=' ')]})
 def test_unicode(self):
  self.refuse('CONTROL_CHARS:title',{'as_of':'2026-10-11','pages':[page(title='a\x1fb')]});self.assertEqual(run([page(title='Café')])['nodes'][0]['key'],'café')
 def test_deterministic_nonmutation(self):
  p=[page()];self.assertEqual(run(p),run(p));self.assertEqual(p,[page()]);self.assertEqual(run()['scope']['data_source'],'supplied-page-exports')
 def test_no_effect_api(self):
  for n in ['send','spend','fetch','post','trade','create_account']:self.assertFalse(hasattr(m,n))
 def test_nested_unknown_before_type(self):
  row=page();row['categories']=[{'unexpected':1}];self.refuse('UNKNOWN:categories',{'as_of':'2026-10-11','pages':[row]})
 def test_text_too_long_unreachable(self):
  for field in ['title','categories','links']:
   row=page();row[field]='x'*201 if field=='title' else ['x'*201]
   self.refuse('OVERSIZE:'+field,{'as_of':'2026-10-11','pages':[row]})
 def test_top50_and_self_degree(self):
  r=run([page(str(i),'n'+str(i)) for i in range(60)])
  self.assertEqual(len(r['top_concepts']),50);self.assertEqual(r['top_concepts'],sorted(n['key'] for n in r['nodes'])[:50])
  self.assertEqual(run([page(links=['Alpha'])])['nodes'][0]['degree'],2)
 def test_supplied_limit_not_total_nodes(self):
  r=run([page('1','x',links=[str(i) for i in range(200)])]);self.assertEqual(r['coverage']['nodes'],201)

class AcceptedInputBoundaryPins(unittest.TestCase):
 refuse=ConceptsTests.refuse
 def test_supplied_page_limit_exactly_20000(self):
  pages=[page(str(i),'Same') for i in range(20000)]
  r=run(pages);self.assertEqual(r['coverage'],{'pages_supplied':20000,'nodes':1,'stubs':0,'edges':0})
 def test_as_of_oversize_exact(self):
  self.refuse('OVERSIZE:as_of',{'as_of':'2026-10-111','pages':[page()]})
 def test_id_numeric_exact(self):
  self.refuse('BAD_TYPE:id',{'as_of':'2026-10-11','pages':[page(5)]})
 def test_lists_wrong_type_exact(self):
  for field,value in [('categories','x'),('links',None)]:
   row=page();row[field]=value;self.refuse('BAD_TYPE:'+field,{'as_of':'2026-10-11','pages':[row]})
 def test_list_entries_numeric_exact(self):
  for field in ['categories','links']:
   row=page();row[field]=[5];self.refuse('BAD_TYPE:'+field,{'as_of':'2026-10-11','pages':[row]})
 def test_entry_200_exact_accepted(self):
  for field in ['categories','links']:
   row=page();row[field]=['x'*200];r=run([row]);self.assertEqual(r['coverage']['nodes'],2);self.assertIn('x'*200,[n['key'] for n in r['nodes']])

if __name__=='__main__':unittest.main(verbosity=2)
