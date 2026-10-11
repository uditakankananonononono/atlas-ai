import unittest
from app.modules.m20_general_cognitive_worker.venture_v2 import policy as p
from test_engines import request

class Policy(unittest.TestCase):
    def refuses(self,fn,code):
        with self.assertRaises(p.Refusal) as ctx:fn()
        self.assertEqual(ctx.exception.code,code)
    def test_exact_policy_codes(self):
        for effect,code in p.EFFECTS.items():
            self.refuses(lambda:p.guard(request(action=effect,approved=True)),code)
            self.refuses(lambda:p.guard(request(**{effect:True})),code)
        for payload,code in [(request(action='unknown'),'POLICY_REFUSED_ACTION'),(request(as_of=''),'PLAN_REFUSED_ASOF'),(request(sources=[]),'PLAN_REFUSED_NOSOURCE'),(request(sources=[{'id':'','url':'https://example.org'}]),'PLAN_REFUSED_SOURCE'),(request(sources=[{'id':'x','url':'https://a'},{'id':'x','url':'https://b'}]),'PLAN_REFUSED_SOURCE')]:
            self.refuses(lambda:p.guard(payload),code)
        for url in ['','file:///a','https://u:p@a',123,'x'*4097]:self.refuses(lambda:p.validate_url(url),'PLAN_REFUSED_SOURCE')
        for value in ['',None,123,'x'*20001]:self.refuses(lambda:p.text(value),'PLAN_REFUSED_INPUT')
        for value in [True,'2',float('inf'),float('nan')]:self.refuses(lambda:p.number(value),'PLAN_REFUSED_NUMBER')
        self.refuses(lambda:p.number(-1,minimum=0),'PLAN_REFUSED_NUMBER')
        self.refuses(lambda:p.citation({'source_id':'missing'},{'s1':{}}),'PLAN_REFUSED_SOURCE')
