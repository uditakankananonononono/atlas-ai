"""Named independent-auditor residual pins; test-only child."""
import copy,json,tempfile,unittest,math
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from app.auth.context import require_tenant,TenantContext
from app.modules.m20_general_cognitive_worker.venture_v2 import engines as e,policy as p,transforms as tr
from app.modules.m20_general_cognitive_worker import venture_v2_routes as routes
from test_engines import request
INPUTS=json.loads(Path(__file__).with_name('golden-inputs.json').read_text())
class NamedPins(unittest.TestCase):
    def refusal(self,fn,code):
        with self.assertRaises(p.Refusal) as ctx:fn()
        self.assertEqual(ctx.exception.code,code)
    def test_policy_container_guards(self):
        for sources in [[1],[None]]:self.refusal(lambda:p.guard(request(sources=sources)),'PLAN_REFUSED_SOURCE')
        self.refusal(lambda:p.guard(request(sources=1)),'PLAN_REFUSED_NOSOURCE')
        with tempfile.TemporaryDirectory() as temp:
            app=FastAPI();app.include_router(routes.router,prefix='/api/v1')
            app.dependency_overrides[require_tenant]=lambda:TenantContext('t','owner')
            app.dependency_overrides[routes.get_store]=lambda:routes.ReportStore(temp+'/db')
            client=TestClient(app)
            for sources,code in [([1],'PLAN_REFUSED_SOURCE'),([None],'PLAN_REFUSED_SOURCE'),(1,'PLAN_REFUSED_NOSOURCE')]:
                result=client.post('/api/v1/c32/problems/run',json=request(sources=sources))
                self.assertEqual(result.status_code,422);self.assertEqual(result.json()['detail']['code'],code)
    def test_separate_xml_declarations(self):
        # Each document is parseable by ElementTree when declaration guard removed.
        for xml in ['<!DOCTYPE rss><rss/>','<?xml version="1.0"?><rss><!-- <!ENTITY harmless "x"> --></rss>']:
            self.refusal(lambda:e.run('news-create',request(feeds=[{'source_id':'s1','xml':xml}])),'INTEL_REFUSED_XML')
    def test_caps_and_minimums(self):
        for n in [9999,10000,10001]:
            tasks=[{'id':str(i),'expected':0} for i in range(n)]
            payload=request(suite_id='large',tasks=tasks,candidate={'name':'candidate','outputs':{str(i):0 for i in range(n)}})
            if n>10000:self.refusal(lambda:e.run('worldclass',payload),'PLAN_REFUSED_INPUT')
            else:self.assertEqual(e.run('worldclass',payload)['suite_size'],n)
        occupation={'code':'x','title':'x','tasks':[{'id':'x','text':'x','source_id':'s1'}]}
        self.assertEqual(e.run('hustles',request(occupations=[occupation],results=[{'task_id':'x','attempts':1,'successes':1,'cost':0}]))['results'][0]['success_rate'],1)
        self.refusal(lambda:e.run('hustles',request(occupations=[occupation],results=[{'task_id':'x','attempts':0,'successes':0,'cost':0}])),'PLAN_REFUSED_NUMBER')
        self.refusal(lambda:e.run('hustles',request(occupations=[occupation],results=[{'task_id':'x','attempts':1,'successes':1,'cost':-1}])),'PLAN_REFUSED_NUMBER')
        bom={'part':'x','quantity':1,'unit_cost':0,'source_id':'s1'}
        self.assertEqual(e.run('anything',request(title='x',kind='device',requirements=['x'],bom=[bom]))['bom'][0]['quantity'],1)
        bom['quantity']=0;self.refusal(lambda:e.run('anything',request(title='x',kind='device',requirements=['x'],bom=[bom])),'PLAN_REFUSED_NUMBER')
    def test_link_selection(self):
        xml='<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>A</title><link href="https://example.org/first"/><link href="https://example.org/last"/></entry></feed>'
        result=e.run('news-create',request(feeds=[{'source_id':'s1','xml':xml}]))
        self.assertEqual(result['ranked'][0]['url'],'https://example.org/first')
    def test_named_type_guards(self):
        for value in [1,None,{},'abc']:self.refusal(lambda:e.bounded_list(value),'PLAN_REFUSED_INPUT')
        base=copy.deepcopy(INPUTS['redirect']);base['files']=[];self.refusal(lambda:e.run('redirect',base),'FLEET_REFUSED_FILES')
        self.refusal(lambda:e.linear({'matrix':[[1],1],'rhs':[1,1]}),'SOLVE_REFUSED_DIMENSION')
        base=copy.deepcopy(INPUTS['worldclass']);base['candidate']['outputs']=[];self.refusal(lambda:e.run('worldclass',base),'BENCH_REFUSED_COVERAGE')
        base=copy.deepcopy(INPUTS['worldclass']);base['tasks']=[{'id':'duplicate','expected':1}]*2;self.refusal(lambda:e.run('worldclass',base),'BENCH_REFUSED_TASK')
        base=copy.deepcopy(INPUTS['rewrite']);base['cases']=[{'input':[{'score':99,'name':'x'}],'expected':[]}];self.refusal(lambda:e.run('rewrite',base),'PROTO_REFUSED_PARITY')
        # finite values can overflow the computed trend slope even though raw
        # input JSON allows them; pin the post-computation number() check.
        self.refusal(lambda:e.run('problems',request(mode='trends',series=[{'name':'x','values':[-1e308,1e308]}])),'PLAN_REFUSED_NUMBER')
    def test_required_field_presence(self):
        names={'hustles':['occupations'],'patents':['invention','prior_art','inventor'],'problems':['matrix','rhs'],'rewrite':['tool','behavior','cases'],'anything':['title','kind','behavior','sample'],'worldclass':['suite_id','tasks','candidate'],'redirect':['project','failures'],'news-create':['feeds']}
        for name,fields in names.items():
            for field in fields:
                base=copy.deepcopy(INPUTS[name]);base.pop(field,None)
                with self.subTest(name=name,field=field),self.assertRaises(p.Refusal):e.run(name,base)
        for field in ['expected','observed','reproduce','id']:
            base=copy.deepcopy(INPUTS['redirect']);base['failures'][0].pop(field)
            self.refusal(lambda:e.run('redirect',base),'PLAN_REFUSED_INPUT')
        base=copy.deepcopy(INPUTS['rewrite']);base['cases'][0].pop('expected');self.refusal(lambda:e.run('rewrite',base),'PROTO_REFUSED_PARITY')
        base=copy.deepcopy(INPUTS['worldclass']);base['tasks'][0].pop('expected');self.refusal(lambda:e.run('worldclass',base),'BENCH_REFUSED_TASK')
        base=copy.deepcopy(INPUTS['patents']);base['invention'].pop('features');self.refusal(lambda:e.run('patents',base),'PLAN_REFUSED_INPUT')
    def test_transform_types_and_post_aggregate_number(self):
        for ops in [1,{},'x']:self.refusal(lambda:tr.validate_behavior({'operations':ops}),'PROTO_REFUSED_BEHAVIOR')
        for op in [1,None,[]]:self.refusal(lambda:tr.validate_behavior({'operations':[op]}),'PROTO_REFUSED_BEHAVIOR')
        for fields in [1,{},'x']:self.refusal(lambda:tr.validate_behavior({'operations':[{'op':'project','fields':fields}]}),'PROTO_REFUSED_BEHAVIOR')
        self.refusal(lambda:tr.transform([{'x':1e308},{'x':1e308}],[{'op':'aggregate','field':'x','function':'sum'}]),'PLAN_REFUSED_NUMBER')
    def test_routes_store_refusal_and_cache_bound(self):
        routes._open_store.cache_clear()
        self.assertEqual(routes._open_store.cache_parameters()['maxsize'],8)
        with tempfile.TemporaryDirectory() as temp:
            for i in range(9):routes._open_store(temp+'/'+str(i)+'.db')
            self.assertEqual(routes._open_store.cache_info().currsize,8)
        routes._open_store.cache_clear()
        app=FastAPI();app.include_router(routes.router,prefix='/api/v1');app.dependency_overrides[require_tenant]=lambda:TenantContext('t','owner')
        client=TestClient(app)
        for path in ['',':memory:']:
            with patch.dict('os.environ',{'ATLAS_VENTURE_REPORT_DB':path}):
                result=client.get('/api/v1/c32/problems/report');self.assertEqual(result.status_code,503)
        import os
        with patch.dict(os.environ,{},clear=True):
            result=client.get('/api/v1/c32/problems/report');self.assertEqual(result.status_code,503)
    def test_citation_and_text_call_removal_pins(self):
        base=copy.deepcopy(INPUTS['redirect'])
        for value in [None,'missing']:
            payload=copy.deepcopy(base);payload['failures'][0]['source_id']=value
            self.refusal(lambda:e.run('redirect',payload),'PLAN_REFUSED_SOURCE')
            payload=copy.deepcopy(base);payload['reviews'][0]['source_id']=value
            self.refusal(lambda:e.run('redirect',payload),'PLAN_REFUSED_SOURCE')
        for field in ['model','response']:
            for value in ['',None,1,[]]:
                payload=copy.deepcopy(base);payload['reviews'][0][field]=value
                self.refusal(lambda:e.run('redirect',payload),'PLAN_REFUSED_INPUT')
        for field in ['expected','observed','reproduce']:
            for value in ['',None,1,[]]:
                payload=copy.deepcopy(base);payload['failures'][0][field]=value
                self.refusal(lambda:e.run('redirect',payload),'PLAN_REFUSED_INPUT')
        for mode in ['strategy','research']:
            for value in [None,'missing']:
                self.refusal(lambda:e.run('problems',request(mode=mode,question='x',evidence=[{'claim':'x','source_id':value}])),'PLAN_REFUSED_SOURCE')
            for value in ['',None,1,[]]:
                self.refusal(lambda:e.run('problems',request(mode=mode,question='x',evidence=[{'claim':value,'source_id':'s1'}])),'PLAN_REFUSED_INPUT')
    def test_nonfinite_public_payloads(self):
        base=copy.deepcopy(INPUTS['anything']);base['sample']=[{'score':float('nan')}]
        self.refusal(lambda:e.run('anything',base),'PLAN_REFUSED_INPUT')
        base=copy.deepcopy(INPUTS['worldclass']);base['tasks'][0]['expected']=float('inf')
        self.refusal(lambda:e.run('worldclass',base),'PLAN_REFUSED_INPUT')
    def test_nonlist_same_shape_and_nondict_matching_keys(self):
        self.refusal(lambda:e.linear({'matrix':[(1,)],'rhs':[1]}),'SOLVE_REFUSED_DIMENSION')
        self.refusal(lambda:e.linear({'matrix':[{0:1}],'rhs':[1]}),'SOLVE_REFUSED_DIMENSION')
        base=copy.deepcopy(INPUTS['worldclass']);base['candidate']['outputs']=['rational','mean']
        self.refusal(lambda:e.run('worldclass',base),'BENCH_REFUSED_COVERAGE')
