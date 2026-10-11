import unittest
from app.modules.m20_general_cognitive_worker.venture_v2 import engines as e
from app.modules.m20_general_cognitive_worker.venture_v2.policy import Refusal
from app.modules.m20_general_cognitive_worker.venture_v2 import transforms as tr
from test_engines import request,META

class Edges(unittest.TestCase):
    def test_input_policy_and_limit(self):
        for p in [None,[],request(action='unknown'),request(sources=[]),request(as_of=''),request(sources=[{'id':'x','url':'file:///x'}]),request(sources=[{'id':'x','url':'https://a'},{'id':'x','url':'https://b'}]),request(sources=[{'id':'x','url':'https://u:p@a'}]),request(question='x'*2000001)]:
            with self.subTest(p=str(p)[:100]), self.assertRaises(Refusal): e.run('problems',p)
        for flag in ['spend','trade','outreach','file','install','fake_account','autopost','restricted_scrape','impersonate','guarantee_income']:
            with self.assertRaises(Refusal): e.run('problems',request(**{flag:True}))
        for p in [request(mode='linear',matrix=[[1]],rhs=[1,2]),request(mode='linear',matrix=[[1,2]],rhs=[1]),request(mode='linear',matrix=[[True]],rhs=[1]),request(mode='linear',matrix=[[10**100]],rhs=[1]),request(mode='linear',matrix=[[1]]*33,rhs=[1]*33),request(mode='trends',series=[{'name':'x','values':[1]}]),request(mode='bad')]:
            with self.assertRaises(Refusal):e.run('problems',p)
        calls=[]
        def shared(p): calls.append(p); raise Refusal('SHARED_REFUSED')
        with self.assertRaises(Refusal): e.run('problems',request(mode='linear',matrix=[[1]],rhs=[1]),shared_guard=shared)
        self.assertEqual(len(calls),1)
    def test_declared_transform_guards(self):
        for behavior in [None,{}, {'operations':[]},{'operations':[{'op':'filter','field':'x','cmp':'bad','value':1}]},{'operations':[{'op':'filter','field':'x','cmp':'eq'}]},{'operations':[{'op':'project','fields':[]}]},{'operations':[{'op':'sort','field':''}]},{'operations':[{'op':'aggregate','field':'x','function':'bad'}]},{'operations':[{'op':'aggregate','field':'x','function':'sum'},{'op':'sort','field':'x'}]},{'operations':[{'op':'sort','field':'x'}]*21}]:
            with self.subTest(behavior=behavior),self.assertRaises(Refusal):tr.validate_behavior(behavior)
        for records in [None,[1],[{}],[{'x':'a'}]*10001]:
            with self.assertRaises(Refusal):tr.transform(records,[{'op':'sort','field':'x'}])
        for fn in ['min','max','mean']:
            with self.assertRaises(Refusal):tr.transform([],[{'op':'aggregate','field':'x','function':fn}])
        for fn,expected in [('min',2),('max',4),('mean',3),('count',2)]:
            self.assertEqual(tr.transform([{'x':2},{'x':4}],[{'op':'aggregate','field':'x','function':fn}]),{fn:expected})
        for cmp,expected in [('eq',[2]),('ne',[1,3]),('gt',[3]),('gte',[2,3]),('lt',[1]),('lte',[1,2])]:
            out=tr.transform([{'x':i} for i in [1,2,3]],[{'op':'filter','field':'x','cmp':cmp,'value':2}])
            self.assertEqual([r['x'] for r in out],expected)
    def test_engine_rejection_edges(self):
        tasks=[{'id':'a','text':'x','source_id':'s1'},{'id':'a','text':'x','source_id':'s1'}]
        cases=[('hustles',request(occupations=[{'code':'x','title':'x','tasks':tasks}])),('hustles',request(occupations=[])),('hustles',request(occupations=[{'code':'x','title':'x','tasks':[dict(tasks[0],source_id='bad')]}])),('patents',request(inventor='owner',invention={'title':'x','features':[]} ,prior_art=[{'id':'a','text':'x','source_id':'s1'}])),('anything',request(kind='device',title='x',requirements=['x'],bom=[{'part':'x','quantity':1.5,'unit_cost':1,'source_id':'s1'}])),('anything',request(kind='device',title='x',requirements=['x'],bom=[{'part':'x','quantity':1,'unit_cost':-1,'source_id':'s1'}])),('redirect',request(project='x',failures=[{'id':'a','source_id':'s1','expected':'x','observed':'x','reproduce':'x'}]*2)),('redirect',request(project='x',failures=[{'id':'a','source_id':'s1','expected':'x','observed':'x','reproduce':'x'}],reviews=[{'failure_id':'bad','model':'m','response':'r','source_id':'s1'}])),('news-create',request(feeds=[{'source_id':'s1','xml':'broken'}])),('news-create',request(feeds=[{'source_id':'s1','xml':'<rss/>'}],limit=True))]
        for name,p in cases:
            with self.subTest(name=name,p=p),self.assertRaises(Refusal): e.run(name,p)
    def test_atom_intake(self):
        xml='<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Humidity research</title><link href="https://example.org/atom"/><summary>new sensor</summary></entry></feed>'
        r=e.run('news-create',request(feeds=[{'source_id':'s1','xml':xml}],interests=['humidity']))
        self.assertEqual(r['ranked'][0]['url'],'https://example.org/atom');self.assertEqual(r['selected_count'],1)
