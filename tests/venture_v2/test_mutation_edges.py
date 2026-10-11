import unittest
from app.modules.m20_general_cognitive_worker.venture_v2 import engines as e,transforms as tr
from app.modules.m20_general_cognitive_worker.venture_v2.policy import Refusal
from test_engines import request

class MutationEdges(unittest.TestCase):
    def refusal(self,fn,code):
        with self.assertRaises(Refusal) as ctx:fn()
        self.assertEqual(ctx.exception.code,code)
    def test_exact_limits_and_refusals(self):
        self.refusal(lambda:tr.validate_behavior({'operations':[{'op':'exec','code':'bad'}]}),'PROTO_REFUSED_BEHAVIOR')
        self.refusal(lambda:tr.validate_behavior({'operations':[{'op':'project','fields':[]}]}),'PROTO_REFUSED_BEHAVIOR')
        self.refusal(lambda:tr.validate_behavior({'operations':[{'op':'project','fields':['x']*101}]}),'PROTO_REFUSED_BEHAVIOR')
        tasks=[{'id':str(i),'text':'x','source_id':'s1'} for i in range(501)]
        other=[{'id':str(i+501),'text':'x','source_id':'s1'} for i in range(500)]
        self.refusal(lambda:e.run('hustles',request(occupations=[{'code':'a','title':'a','tasks':tasks},{'code':'b','title':'b','tasks':other}])),'MONEY_REFUSED_OVERSIZE')
        base=request(tool={'name':'x','license':'MIT','author':'a','source_id':'s1'},behavior={'operations':[{'op':'sort','field':'x'}]},cases=[{'input':[{'x':1}]}])
        self.refusal(lambda:e.run('rewrite',base),'PROTO_REFUSED_PARITY')
        self.refusal(lambda:e.run('anything',request(kind='device',title='x',requirements=['x'],bom=[{'part':'x','quantity':1.5,'unit_cost':2,'source_id':'s1'}])),'PROTO_REFUSED_BOM')
        self.refusal(lambda:e.run('worldclass',request(suite_id='x',tasks=[{'id':'x'}],candidate={'name':'x','outputs':{'x':1}})),'BENCH_REFUSED_TASK')
        self.refusal(lambda:e.run('redirect',request(project='x',failures=[{'id':'x','source_id':'s1','expected':'x','observed':'x','reproduce':'x'}],reviews=[{'failure_id':'bad','source_id':'s1','model':'m','response':'r'}])),'FLEET_REFUSED_REVIEW')
        self.refusal(lambda:e.run('worldclass',request(suite_id='x',tasks=[{'id':'x','expected':1}],candidate={'name':'x','outputs':{}})),'BENCH_REFUSED_COVERAGE')
        self.refusal(lambda:e.run('redirect',request(project='x',failures=[{'id':'x','source_id':'s1','expected':'x','observed':'x','reproduce':'x'}],files={str(i):'x' for i in range(101)})),'FLEET_REFUSED_FILES')
        self.refusal(lambda:e.run('hustles',request(occupations=[42])),'PLAN_REFUSED_INPUT')
        items=''.join('<item><title>X</title><link>https://example.org/'+str(i)+'</link></item>' for i in range(1001))
        self.refusal(lambda:e.run('news-create',request(feeds=[{'source_id':'s1','xml':'<rss>'+items+'</rss>'}])),'INTEL_REFUSED_OVERSIZE')
        self.refusal(lambda:e.run('problems',None),'PLAN_REFUSED_INPUT')
        self.refusal(lambda:e.run('problems',request(question='x'*2000001)),'PLAN_REFUSED_OVERSIZE')
        self.refusal(lambda:e.run('problems',request(matrix=[[float('nan')]])),'PLAN_REFUSED_INPUT')
