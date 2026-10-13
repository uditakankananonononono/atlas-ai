"""Independent frozen-output pins and one-sided boundary checks for repair."""
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.modules.m20_general_cognitive_worker.venture_v2 import engines as e,policy as p,transforms as tr
from app.modules.m20_general_cognitive_worker.venture_v2.store import ReportStore
from test_engines import request

INPUTS=json.loads(Path(__file__).with_name('golden-inputs.json').read_text())
OUTPUTS=json.loads(Path(__file__).with_name('golden-outputs.json').read_text())

class Pins(unittest.TestCase):
    def refusal(self,fn,code):
        with self.assertRaises(p.Refusal) as c:fn()
        self.assertEqual(c.exception.code,code)
    def case(self,name,**changes):return dict(copy.deepcopy(INPUTS[name]),**changes)
    def test_frozen_outputs_every_field(self):
        for name in INPUTS:
            with self.subTest(unit=name):self.assertEqual(e.run(name,copy.deepcopy(INPUTS[name])),OUTPUTS[name])
    def test_runtime_malformed_policy(self):
        for action in [[],{},1,None,True]:self.refusal(lambda:p.guard(request(action=action)),'POLICY_REFUSED_ACTION')
        for sid in [[],{},1,None,True]:self.refusal(lambda:p.guard(request(sources=[{'id':sid,'url':'https://example.org'}])),'PLAN_REFUSED_SOURCE')
        for action in [[],{}]:self.refusal(lambda:e.run('problems',request(action=action)),'POLICY_REFUSED_ACTION')
        for sid in [[],{}]:self.refusal(lambda:e.run('problems',request(sources=[{'id':sid,'url':'https://example.org'}])),'PLAN_REFUSED_SOURCE')
    def test_shared_boundaries(self):
        for effect,code in {'spend':'POLICY_REFUSED_SPEND','trade':'POLICY_REFUSED_TRADE','outreach':'POLICY_REFUSED_OUTREACH','file':'INTEL_REFUSED_FILE','install':'PROTO_REFUSED_INSTALL','fake_account':'POLICY_REFUSED_FAKEACCT','autopost':'POLICY_REFUSED_AUTOPOST','restricted_scrape':'POLICY_REFUSED_SCRAPE','impersonate':'MONEY_REFUSED_IMPERSONATE','guarantee_income':'MONEY_REFUSED_GUARANTEE'}.items():
            self.refusal(lambda:p.guard(request(action=effect)),code)
        self.assertEqual(p.text('x'*20000),'x'*20000)
        self.refusal(lambda:p.text('x'*20001),'PLAN_REFUSED_INPUT')
        sources=[{'id':str(i),'url':'https://example.org'} for i in range(1000)]
        self.assertEqual(len(p.guard(request(sources=sources))),1000)
        self.refusal(lambda:p.guard(request(sources=sources+[{'id':'extra','url':'https://example.org'}])),'PLAN_REFUSED_NOSOURCE')
        url='https://example.org/'+('x'*(4096-len('https://example.org/')))
        self.assertEqual(p.validate_url(url),url);self.refusal(lambda:p.validate_url(url+'x'),'PLAN_REFUSED_SOURCE')
        for url in ['ftp://example.org','https:///x','https://name@example.org','https://:pass@example.org']:
            self.refusal(lambda:p.validate_url(url),'PLAN_REFUSED_SOURCE')
        self.refusal(lambda:p.guard(request(sources=[{'id':'x','url':'file:///x'}])),'PLAN_REFUSED_SOURCE')
        base=request(mode='research',question='x',evidence=[{'claim':'x','source_id':'s1'}]);base['padding']=''
        size=len(json.dumps(base,allow_nan=False));base['padding']='x'*(2000000-size)
        self.assertEqual(len(json.dumps(base,allow_nan=False)),2000000)
        self.assertEqual(e.run('problems',base)['status'],'decomposed_not_solved')
        base['padding']+='x';self.refusal(lambda:e.run('problems',base),'PLAN_REFUSED_OVERSIZE')
    def test_hustle_numeric_bounds_and_fields(self):
        base=self.case('hustles');row=base['results'][0]
        self.assertEqual(e.run('hustles',base)['results'][0],dict(row,success_rate=.8,net_revenue=0,minutes=90,evidence_status='supplied_not_independently_verified'))
        for field,values in {'attempts':[0,-1,1.5,True,'1'],'successes':[-1,31,1.5,True,'1'],'revenue':[-1,True,'1',float('inf')],'minutes':[-1,True,'1'],'cost':[1,-1,True,'1']}.items():
            for value in values:
                r=dict(row,**{field:value})
                with self.subTest(field=field,value=value),self.assertRaises(p.Refusal):e.run('hustles',self.case('hustles',results=[r]))
        self.assertEqual(e.run('hustles',self.case('hustles',results=[dict(row,successes=0,revenue=15,minutes=0)]))['results'][0]['net_revenue'],15)
        tasks=[{'id':str(i),'text':'x','source_id':'s1'} for i in range(1000)]
        occupations=[{'code':'x','title':'x','tasks':tasks}]
        self.assertEqual(e.run('hustles',request(occupations=occupations))['catalog_count'],1000)
        occupations.append({'code':'y','title':'y','tasks':[{'id':'extra','text':'x','source_id':'s1'}]})
        self.refusal(lambda:e.run('hustles',request(occupations=occupations)),'MONEY_REFUSED_OVERSIZE')
        occupations[-1]['tasks'][0]['id']='0';self.refusal(lambda:e.run('hustles',request(occupations=occupations)),'MONEY_REFUSED_DUPLICATE')
    def test_patent_limits_arithmetic_and_sort(self):
        base=self.case('patents');base['invention']['features']=['a','b','c'];base['prior_art']=[{'id':'z','text':'a b','source_id':'fixture'},{'id':'a','text':'a b','source_id':'fixture'},{'id':'b','text':'c','source_id':'fixture'}]
        r=e.run('patents',base);self.assertEqual([x['id'] for x in r['prior_art']],['a','z','b']);self.assertEqual([x['feature_overlap'] for x in r['prior_art']],[2/3,2/3,1/3])
        self.assertEqual([x['number'] for x in r['claims']],[1,2,3,4]);self.assertTrue(all(x['requires_owner_detail'] for x in r['claims'][1:]))
        base['invention']['features']=['x'*2000]*100;self.assertEqual(len(e.run('patents',base)['claims']),101)
        base['invention']['features'].append('x');self.refusal(lambda:e.run('patents',base),'PLAN_REFUSED_INPUT')
        base['invention']['features']=['x'*2001];self.refusal(lambda:e.run('patents',base),'PLAN_REFUSED_INPUT')
        base['invention']['features']=['x'];base['inventor']='other';self.refusal(lambda:e.run('patents',base),'INTEL_REFUSED_INVENTOR')
    def test_solver_exact_boundaries_and_status(self):
        matrix=[[int(i==j) for j in range(32)] for i in range(32)]
        r=e.run('problems',request(mode='linear',matrix=matrix,rhs=list(range(32))))
        self.assertEqual(r['solution'],[str(i) for i in range(32)]);self.assertEqual(r['residual'],['0']*32);self.assertTrue(r['verified']);self.assertEqual(r['status'],'solved')
        self.refusal(lambda:e.run('problems',request(mode='linear',matrix=[[1]]*33,rhs=[1]*33)),'PLAN_REFUSED_INPUT')
        for value in [2**255,2**256-1]:self.assertEqual(e.run('problems',request(mode='linear',matrix=[[value]],rhs=[value]))['solution'],['1'])
        self.refusal(lambda:e.run('problems',request(mode='linear',matrix=[[2**256]],rhs=[1])),'SOLVE_REFUSED_LIMIT')
        # Fraction denominator boundary cannot be hit via binary64 alone: use direct
        # solver seam that changes only numeric admission, not Fraction arithmetic.
        with patch.object(e,'number',lambda x:x):
            self.assertEqual(e.linear({'matrix':[['1/'+str(2**255)]],'rhs':[1]})['solution'],[str(2**255)])
            self.refusal(lambda:e.linear({'matrix':[['1/'+str(2**256)]],'rhs':[1]}),'SOLVE_REFUSED_LIMIT')
        self.assertEqual(e.linear({'matrix':[[0]],'rhs':[1]}),{'status':'unsolved','reason':'inconsistent','verified':False})
        self.assertEqual(e.linear({'matrix':[[0]],'rhs':[0]}),{'status':'unsolved','reason':'underdetermined','verified':False})
        r=e.run('problems',request(mode='trends',series=[{'name':'z','values':[0,2,4]},{'name':'a','values':[0,2,4]},{'name':'b','values':[4,2,0]}]))
        self.assertEqual([(x['name'],x['slope']) for x in r['ranked']],[('a',2),('z',2),('b',-2)])
        for mode in ['research','strategy']:
            self.assertEqual(e.run('problems',request(mode=mode,question='x',evidence=[{'claim':'x','source_id':'s1'}]))['steps'],[
                {'goal':'Define measurable target','deliverable':{'question':'x','constraints':[]}},
                {'goal':'Reproduce observed evidence','deliverable':{'evidence':[{'claim':'x','source_id':'s1'}],'test':'independent reproduction'}},
                {'goal':'Compare bounded alternatives','deliverable':{'options':['change method','reduce one constraint with owner decision','collect missing evidence'],'score_axes':['correctness','cost','feasibility']}},
                {'goal':'Falsify proposed solution','deliverable':{'test':'holdout acceptance check','required':'predeclared criterion and measured result'}}])
    def test_codegen_literal_and_validator_limits(self):
        ops=[{'op':'sort','field':'x'}]*20
        self.assertEqual(tr.validate_behavior({'operations':ops}),ops)
        self.refusal(lambda:tr.validate_behavior({'operations':ops+[ops[0]]}),'PROTO_REFUSED_BEHAVIOR')
        fields=['x']*100;self.assertEqual(tr.validate_behavior({'operations':[{'op':'project','fields':fields}]}),[{'op':'project','fields':fields}])
        self.refusal(lambda:tr.validate_behavior({'operations':[{'op':'project','fields':fields+['x']}]}),'PROTO_REFUSED_BEHAVIOR')
        self.refusal(lambda:tr.validate_behavior({'operations':[{'op':'aggregate','field':'x','function':'sum'},{'op':'sort','field':'x'}]}),'PROTO_REFUSED_BEHAVIOR')
        # Golden output freezes the complete generated source and OPERATIONS literal.
        self.assertEqual(tr.generate(INPUTS['rewrite']['behavior']['operations']),OUTPUTS['rewrite']['files']['adapter.py'])
        for license_ in ['GPL-3.0','','proprietary']:
            base=self.case('rewrite');base['tool']['license']=license_;self.refusal(lambda:e.run('rewrite',base),'PROTO_REFUSED_UNLICENSED')
    def test_benchmark_pins_and_limit(self):
        base=self.case('worldclass');r=e.run('worldclass',base)
        self.assertEqual(r['suite_fingerprint'],hashlib.sha256(json.dumps(base['tasks'],sort_keys=True,allow_nan=False).encode()).hexdigest())
        self.assertEqual(r['candidate']['accuracy'],1);self.assertEqual(r['baselines'][0]['accuracy'],.5);self.assertEqual(r['comparisons'][0]['accuracy_delta'],.5)
        base['candidate']['outputs']={};self.refusal(lambda:e.run('worldclass',base),'BENCH_REFUSED_COVERAGE')
        base=self.case('worldclass');base['baselines']*=100;self.assertEqual(len(e.run('worldclass',base)['baselines']),100)
        base['baselines'].append(base['baselines'][0]);self.refusal(lambda:e.run('worldclass',base),'PLAN_REFUSED_INPUT')
    def test_redirect_file_sizes_and_count(self):
        base=self.case('redirect');base['files']={'x'*200:'y'*100000};r=e.run('redirect',base)
        self.assertEqual(r['packet']['files']['x'*200]['content'],'y'*100000)
        self.assertEqual(r['packet']['files']['x'*200]['sha256'],hashlib.sha256(('y'*100000).encode()).hexdigest())
        base['files']={'x'*201:'y'};self.refusal(lambda:e.run('redirect',base),'PLAN_REFUSED_INPUT')
        base['files']={'x':'y'*100001};self.refusal(lambda:e.run('redirect',base),'PLAN_REFUSED_INPUT')
        base['files']={str(i):'x' for i in range(100)};self.assertEqual(len(e.run('redirect',base)['packet']['files']),100)
        base['files']['extra']='x';self.refusal(lambda:e.run('redirect',base),'FLEET_REFUSED_FILES')
        base=self.case('redirect');base['failures']*=2;self.refusal(lambda:e.run('redirect',base),'FLEET_REFUSED_DUPLICATE')
    def test_news_exact_scoring_and_bounds(self):
        def feed(url='https://example.org/a',title='water sensor',body=''):
            return {'source_id':'s1','xml':f'<rss><item><title>{title}</title><link>{url}</link><description>{body}</description></item></rss>'}
        body=' '.join('n'+str(i) for i in range(30))+'x'*2100
        r=e.run('news-create',request(feeds=[feed(body=body),feed()],interests=['water','sensor']))
        self.assertEqual(r['ingested_count'],1);self.assertEqual(r['ranked'][0]['score'],16);self.assertEqual(len(r['ranked'][0]['new_concepts']),20);self.assertEqual(len(r['ranked'][0]['summary']),2000)
        r=e.run('news-create',request(feeds=[feed(title='water',body='new')],interests=['water'],prior_concepts=[]));self.assertEqual(r['ranked'][0]['score'],4)
        r=e.run('news-create',request(feeds=[feed('https://example.org/z'),feed('https://example.org/a')],interests=['water']));self.assertEqual([a['url'] for a in r['ranked']],['https://example.org/a','https://example.org/z'])
        for limit in [1,100]:self.assertEqual(e.run('news-create',request(feeds=[feed()],limit=limit))['selected_count'],1)
        for limit in [0,101,True,1.5]:self.refusal(lambda:e.run('news-create',request(feeds=[feed()],limit=limit)),'INTEL_REFUSED_LIMIT')
        self.assertEqual(e.run('news-create',request(feeds=[feed()]*100))['ingested_count'],1)
        self.refusal(lambda:e.run('news-create',request(feeds=[feed()]*101)),'PLAN_REFUSED_INPUT')
        xml='<rss>'+(' '* (1000000-len('<rss></rss>')) )+'</rss>'
        self.assertEqual(e.run('news-create',request(feeds=[{'source_id':'s1','xml':xml}]))['ingested_count'],0)
        self.refusal(lambda:e.run('news-create',request(feeds=[{'source_id':'s1','xml':xml+' '}])),'PLAN_REFUSED_INPUT')
        for xml in ['<!DOCTYPE rss><rss/>','<!ENTITY x "hi"><rss/>']:
            self.refusal(lambda:e.run('news-create',request(feeds=[{'source_id':'s1','xml':xml}])),'INTEL_REFUSED_XML')
        xml='<rss>'+''.join(f'<item><title>x</title><link>https://example.org/{i}</link></item>' for i in range(1000))+'</rss>'
        self.assertEqual(e.run('news-create',request(feeds=[{'source_id':'s1','xml':xml}]))['ingested_count'],1000)
        xml=xml.replace('</rss>','<item><title>x</title><link>https://example.org/extra</link></item></rss>')
        self.refusal(lambda:e.run('news-create',request(feeds=[{'source_id':'s1','xml':xml}])),'INTEL_REFUSED_OVERSIZE')
    def test_store_pins(self):
        with tempfile.TemporaryDirectory() as folder:
            path=folder+'/reports.db';store=ReportStore(path)
            for method in ['save','get']:
                for tenant,unit in [('', 'u'),('t',''),(None,'u'),('t',None)]:
                    fn=(lambda:store.save(tenant,unit,{'x':1})) if method=='save' else (lambda:store.get(tenant,unit))
                    self.refusal(fn,'PLAN_REFUSED_INPUT')
            report=store.save('tenant','unit',{'x':'report'});self.assertEqual(store.get('tenant','unit',report['run_id']),report)
            with sqlite3.connect(path) as db:
                row=db.execute('SELECT tenant,unit,run_id,created_at,report FROM venture_reports').fetchone()
                self.assertEqual(row[:4],('tenant','unit',report['run_id'],report['created_at']));self.assertEqual(json.loads(row[4]),report)
                index=db.execute("SELECT sql FROM sqlite_master WHERE name='venture_tenant_unit'").fetchone()[0]
                self.assertIn('tenant, unit, created_at',index)
