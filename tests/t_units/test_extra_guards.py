import test_training_units as t
from test_training_units import SourcePermit, Refusal, TrainingUnits, PublicFetcher, FetchResponse, public_url
import unittest
class ExtraGuards(unittest.TestCase):
    def setUp(self):t.TrainingTests.setUp(self)
    def test_terms_and_license(self):
        from dataclasses import replace
        for p in [replace(self.permit,terms_allowed=False),replace(self.permit,license='copyright'),replace(self.permit,checked_at=''),replace(self.permit,terms_url='http://localhost/terms')]:
            with self.subTest(p=p),self.assertRaises(Refusal):TrainingUnits({'fixture':p},policy=lambda p:None).run('T3',{'records':[self.record]})
    def test_auth_wall_and_type(self):
        for patch in [{'logged_in':True},{'credentials':'x'},{'text':None},{'as_of':None},{'as_of':'today'}]:
            with self.subTest(patch=patch),self.assertRaises(Refusal):self.engine.run('T1',{'records':[dict(self.record,**patch)]})
        for p in [None,{}, {'records':'bad'}, {'records':[None]}]:
            if p=={}:continue
            with self.subTest(p=p),self.assertRaises(Refusal):self.engine.run('T1',p)
    def test_transport_oversize_status_delay(self):
        fixtures=[FetchResponse(404,'',{}),FetchResponse(200,'x'*100001,{}),FetchResponse(200,'User-agent: *\nAllow: /\nCrawl-delay: 120',{})]
        for response in fixtures:
            with self.subTest(response=response.status),self.assertRaises(Refusal):PublicFetcher({'fixture':self.permit},lambda u,n:response).fetch('fixture','https://example.org/book')
        def big(u,n):return FetchResponse(200,'User-agent: *\nAllow: /' if u.endswith('robots.txt') else 'a'*100001,{})
        with self.assertRaises(Refusal):PublicFetcher({'fixture':self.permit},big).fetch('fixture','https://example.org/book')
        for interval,limit in [(1,100),(60,0),(60,100001)]:
            with self.assertRaises(Refusal):PublicFetcher({},None,interval=interval,limit=limit)
    def test_parse_guards(self):
        base={'kind':'blog','source_id':'fixture','url':'https://example.org/rss','as_of':'2026-10-11','content':'<rss/>'}
        for patch in [{'kind':'evil'},{'content':1},{'content':'<!DOCTYPE rss><rss/>'},{'content':'<!ENTITY x><rss/>'},{'content':'<'},{'query':1},{'query':'x'*1001}]:
            with self.subTest(patch=patch),self.assertRaises(Refusal):self.engine.run('T2',dict(base,**patch))
    def test_feed_limit_and_query(self):
        content='<rss><channel>'+''.join('<item><title>Match</title><link>https://example.org/%d</link></item>'%i for i in range(101))+'</channel></rss>'
        base={'kind':'blog','source_id':'fixture','url':'https://example.org/rss','as_of':'2026-10-11','content':content}
        r=self.engine.run('T2',base);self.assertEqual(len(r['results']),100);self.assertEqual(r['matched_in_input'],101)
        self.assertEqual(self.engine.run('T2',dict(base,query='absent'))['results'],[])
    def test_policy_on_search(self):
        def deny(p):raise Refusal('POLICY_REFUSED_SCRAPE')
        e=TrainingUnits({'fixture':self.permit},policy=deny)
        with self.assertRaisesRegex(Refusal,'POLICY_REFUSED_SCRAPE'):e.run('T2',{'kind':'blog','source_id':'fixture','url':'https://example.org/rss','as_of':'2026-10-11','content':'<rss/>'})
    def test_record_count_independent(self):
        with self.assertRaisesRegex(Refusal,'OVERSIZE'):self.engine.run('T1',{'records':[self.record]*501})
    def test_robots_status_independent(self):
        f=PublicFetcher({'fixture':self.permit},lambda u,n:FetchResponse(404,'User-agent: *\nAllow: /',{}))
        with self.assertRaisesRegex(Refusal,'SCRAPE'):f.fetch('fixture','https://example.org/book')
    def test_https_independent(self):
        with self.assertRaises(Refusal):public_url('http://example.org/book')
    def test_policy_false_denies(self):
        for result in [False,{'allowed':False}]:
            e=TrainingUnits({'fixture':self.permit},policy=lambda p:result)
            with self.assertRaises(Refusal):e.run('T1',{'records':[self.record]})
