import json,tempfile,unittest
from pathlib import Path
from app.modules.m20_general_cognitive_worker.venture_v2 import engines as e,policy as p,transforms as tr
from app.modules.m20_general_cognitive_worker.venture_v2.store import ReportStore
from test_engines import request

class AlternatePins(unittest.TestCase):
    def refusal(self,fn,code):
        with self.assertRaises(p.Refusal) as c:fn()
        self.assertEqual(c.exception.code,code)
    def test_alternate_frozen_outputs(self):
        for case in json.loads(Path(__file__).with_name('alternate-golden.json').read_text()):
            with self.subTest(unit=case['unit']):self.assertEqual(e.run(case['unit'],case['input']),case['output'])
    def test_default_and_refusal_details(self):
        self.assertEqual(str(p.Refusal('CODE')),'CODE');self.assertEqual(str(p.Refusal('CODE','detail')),'CODE: detail')
        for action in ['analyze','simulate']:self.assertIn('s1',p.guard(request(action=action)))
        self.assertEqual(p.validate_url('http://example.org'),'http://example.org')
        self.refusal(lambda:p.guard(request(sources=[{'id':'x'}])),'PLAN_REFUSED_SOURCE')
        self.refusal(lambda:e.run('unknown',request()),'PLAN_REFUSED_UNIT')
        self.refusal(lambda:e.run('problems',request(mode='bad')),'SOLVE_REFUSED_MODE')
        self.refusal(lambda:e.run('problems',request(mode='linear',matrix=[[1]],rhs=[1,2])),'SOLVE_REFUSED_DIMENSION')
        self.refusal(lambda:e.run('problems',request(mode='linear',matrix=[[1,2]],rhs=[1])),'SOLVE_REFUSED_DIMENSION')
        self.refusal(lambda:e.run('problems',request(mode='trends',series=[{'name':'x','values':[1]}])),'SOLVE_REFUSED_SERIES')
        self.refusal(lambda:e.run('patents',request(inventor='owner',invention={'title':'x','features':['x']},prior_art=[])),'INTEL_REFUSED_PRIORART_MISSING')
        self.refusal(lambda:e.run('anything',request(kind='bad',title='x')),'PROTO_REFUSED_KIND')
        self.refusal(lambda:e.run('news-create',request(feeds=[{'source_id':'s1','xml':'broken'}])),'INTEL_REFUSED_XML')
        for fn in ['min','max','mean','count','sum']:
            self.assertEqual(tr.validate_behavior({'operations':[{'op':'aggregate','field':'x','function':fn}]}),[{'op':'aggregate','field':'x','function':fn}])
        self.refusal(lambda:tr.transform([],[{'op':'aggregate','field':'x','function':'mean'}]),'PROTO_REFUSED_EMPTY')
        self.refusal(lambda:tr.transform([{}],[{'op':'sort','field':'x'}]),'PROTO_REFUSED_RECORDS')
        self.assertEqual(len(tr.transform([{'x':1}]*10000,[{'op':'sort','field':'x'}])),10000)
        for kind in ['project','sort']:
            op={'op':kind,'fields':['x'*100]} if kind=='project' else {'op':kind,'field':'x'*100}
            self.assertEqual(tr.validate_behavior({'operations':[op]}),[op])
            op={'op':kind,'fields':['x'*101]} if kind=='project' else {'op':kind,'field':'x'*101}
            self.refusal(lambda:tr.validate_behavior({'operations':[op]}),'PLAN_REFUSED_INPUT')
        with tempfile.TemporaryDirectory() as temp:
            store=ReportStore(temp+'/db');a=store.save('t','u',{'n':1});b=store.save('t','u',{'n':2})
            self.assertEqual(store.get('t','u'),b);self.assertEqual(store.get('t','u',a['run_id']),a)
            with self.assertRaises(KeyError) as c:store.get('bad','u')
            self.assertEqual(c.exception.args,('report not found',))
    def test_hustle_failure_codes_and_exact_bounds(self):
        occupation={'code':'x','title':'x','tasks':[{'id':'x','text':'x','source_id':'s1'}]}
        for row in [{'task_id':'missing','attempts':1,'successes':1},{'task_id':'x','attempts':1,'successes':2},{'task_id':'x','attempts':1.5,'successes':1}]:
            self.refusal(lambda:e.run('hustles',request(occupations=[occupation],results=[row])),'MONEY_REFUSED_RESULT')
        r=e.run('hustles',request(occupations=[occupation],results=[{'task_id':'x','attempts':1,'successes':1,'revenue':1,'cost':0}]))
        self.assertEqual(r['results'][0]['success_rate'],1)
        self.refusal(lambda:e.run('hustles',request(occupations=[occupation],results=[{'task_id':'x','attempts':1,'successes':1,'cost':1}])),'MONEY_REFUSED_SPEND')
    def test_additional_edges(self):
        self.refusal(lambda:tr.validate_behavior(None),'PROTO_REFUSED_BEHAVIOR')
        self.refusal(lambda:tr.validate_behavior({'operations':[{'op':'filter','field':'x','cmp':'eq'}]}),'PROTO_REFUSED_BEHAVIOR')
        self.refusal(lambda:tr.transform([1],[{'op':'sort','field':'x'}]),'PROTO_REFUSED_RECORDS')
        for licence in ['Apache-2.0','BSD-2-Clause','BSD-3-Clause']:
            base=json.loads(Path(__file__).with_name('golden-inputs.json').read_text())['rewrite'];base['tool']['license']=licence
            r=e.run('rewrite',base);self.assertIn(licence,r['files']['NOTICE.txt'])
        self.refusal(lambda:e.run('problems',request(mode='linear',matrix=[[1]],rhs=[1]*33)),'PLAN_REFUSED_INPUT')
        self.refusal(lambda:e.run('problems',request(mode='linear',matrix=[[1]]*33,rhs=[1])),'PLAN_REFUSED_INPUT')
        self.refusal(lambda:e.run('problems',request(mode='trends',series=[{'name':'x','values':[1,2]}]*101)),'PLAN_REFUSED_INPUT')
        self.assertEqual(e.run('problems',request(mode='trends',series=[{'name':'x','values':[1,2]}]*100))['ranked'][0]['slope'],1)
        self.refusal(lambda:e.run('problems',request(mode='trends',series=[{'name':'x','values':[1]*10001}])),'PLAN_REFUSED_INPUT')
        self.assertEqual(e.run('problems',request(mode='trends',series=[{'name':'x','values':[1]*10000}]))['ranked'][0]['slope'],0)
        base=json.loads(Path(__file__).with_name('golden-inputs.json').read_text())['rewrite'];base['cases']*=100
        self.assertEqual(len(e.run('rewrite',base)['parity']['cases']),100);base['cases'].append(base['cases'][0]);self.refusal(lambda:e.run('rewrite',base),'PLAN_REFUSED_INPUT')
        xml='<rss><item><title>sensor <b>water</b></title><link>https://example.org/a</link></item></rss>'
        self.assertEqual(e.run('news-create',request(feeds=[{'source_id':'s1','xml':xml}]))['ranked'][0]['title'],'sensor water')
        with tempfile.TemporaryDirectory() as temp:
            store=ReportStore(temp+'/db')
            with self.assertRaises((ValueError,TypeError)):store.save('t','u',{'x':float('nan')})
    def test_zero_cost_and_list_defaults(self):
        self.assertEqual(e.bounded_list([1]*1000),[1]*1000)
        self.refusal(lambda:e.bounded_list([1]*1001),'PLAN_REFUSED_INPUT')
        r=e.run('anything',request(kind='device',title='x',requirements=['x'],bom=[{'part':'x','quantity':1,'unit_cost':0,'source_id':'s1'}]));self.assertEqual(r['bom_total_estimate'],0)
        base=json.loads(Path(__file__).with_name('golden-inputs.json').read_text())['worldclass'];base['baselines']=[]
        self.assertEqual(e.run('worldclass',base)['baselines'],[])
