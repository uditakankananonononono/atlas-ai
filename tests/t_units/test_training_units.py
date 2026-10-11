import unittest
import importlib.util, sys, pathlib
spec=importlib.util.spec_from_file_location('training_data_units', pathlib.Path(__file__).parents[2]/'backend/app/modules/m20_general_cognitive_worker/training_data_units.py')
m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)
globals().update({k:v for k,v in vars(m).items() if not k.startswith('_')})

class TrainingTests(unittest.TestCase):
    def setUp(self):
        self.permit = SourcePermit('fixture', 'https://example.org', 'CC-BY-4.0', 'https://example.org/terms', '2026-10-11', True)
        self.events=[]
        self.engine=TrainingUnits({'fixture':self.permit}, policy=lambda p:self.events.append(p))
        self.record={'source_id':'fixture','url':'https://example.org/case','text':'Outcome: admitted\nSAT: 1500\nEssay: I learned by listening.', 'as_of':'2026-10-11'}
    def test_cases(self):
        r=self.engine.run('T1',{'records':[self.record]})
        self.assertEqual(r['ingested_sites'],1);self.assertEqual(r['records'][0]['stats']['SAT'],'1500')
        self.assertEqual(r['records'][0]['outcomes'],['admitted']);self.assertTrue(self.events)
        self.assertEqual(r['records'][0]['license'],'CC-BY-4.0')
    def test_no_fake_outcome(self):
        self.record['text']='Essay: Reflection only'
        self.assertEqual(self.engine.run('T1',{'records':[self.record]})['records'][0]['outcomes'],[])
    def test_no_rights(self):
        e=TrainingUnits({}, policy=lambda p:None)
        with self.assertRaisesRegex(Refusal,'APPLY_REFUSED_SCRAPE'): e.run('T1',{'records':[self.record]})
    def test_paywall(self):
        self.record['paywalled']=True
        with self.assertRaisesRegex(Refusal,'APPLY_REFUSED_PAYWALL'):self.engine.run('T1',{'records':[self.record]})
    def test_wrong_host(self):
        self.record['url']='https://evil.example/case'
        with self.assertRaises(Refusal):self.engine.run('T1',{'records':[self.record]})
    def test_client_permission_does_not_authorize(self):
        self.record['license']='CC0';self.record['terms_allowed']=True
        with self.assertRaises(Refusal):TrainingUnits({},policy=lambda p:None).run('T1',{'records':[self.record]})
    def test_scope_and_dedupe(self):
        r=self.engine.run('T1',{'records':[self.record,self.record]})
        self.assertEqual(len(r['records']),1);self.assertEqual(r['scope']['data_source'],'supplied licensed documents')
        self.assertIn('not_implemented',r['scope']);self.assertEqual(r['scope']['as_of'],'2026-10-11')
    def test_feed(self):
        r=self.engine.run('T2',{'kind':'blog','source_id':'fixture','url':'https://example.org/rss','as_of':'2026-10-11','query':'learning','content':'<rss><channel><item><title>Learning</title><link>https://example.org/a</link><description>Reflection</description></item></channel></rss>'})
        self.assertEqual(len(r['results']),1)
    def test_podcast(self):
        r=self.engine.run('T2',{'kind':'podcast','source_id':'fixture','url':'https://example.org/rss','as_of':'2026-10-11','content':'<rss xmlns:p="https://podcastindex.org/namespace/1.0"><channel><item><title>Talk</title><p:transcript url="https://example.org/transcript"/></item></channel></rss>'})
        self.assertEqual(r['results'][0]['transcript_url'],'https://example.org/transcript');self.assertFalse(r['results'][0]['transcript_ingested'])
    def test_github(self):
        r=self.engine.run('T2',{'kind':'git','source_id':'fixture','url':'https://example.org/api','as_of':'2026-10-11','content':'{"items":[{"name":"A","html_url":"https://github.com/u/a","description":"test"}]}','query':'test'})
        self.assertEqual(r['results'][0]['title'],'A')
    def test_feed_private_link_excluded(self):
        r=self.engine.run('T2',{'kind':'blog','source_id':'fixture','url':'https://example.org/rss','as_of':'2026-10-11','content':'<rss><channel><item><title>X</title><link>http://127.0.0.1/a</link></item></channel></rss>'})
        self.assertEqual(r['results'],[])
    def test_books_extract(self):
        self.record['text']='Always test a hypothesis before you adopt it.\nThis is narrative.'
        r=self.engine.run('T3',{'records':[self.record]})
        self.assertEqual(len(r['concept_candidates']),1);self.assertFalse(r['model_trained'])
    def test_piracy(self):
        self.record['piracy']=True
        with self.assertRaisesRegex(Refusal,'TREND_REFUSED_PIRACY'):self.engine.run('T3',{'records':[self.record]})
    def test_advice_first(self):
        order=[]
        e=TrainingUnits({'fixture':self.permit},policy=lambda p:order.append('policy'))
        r=e.run('T4',{'task':'research college cases','action':{'outreach':True},'records':[self.record]})
        self.assertEqual([x['stage'] for x in r['log']],['advice','policy','prepared']);self.assertEqual(r['status'],'prepared_only');self.assertEqual(order,['policy'])
    def test_advice_missing_refused(self):
        with self.assertRaisesRegex(Refusal,'FLEET_REFUSED_NOADVICE'):self.engine.run('T4',{'records':[]})
    def test_policy_refusal_propagates(self):
        def deny(p):raise Refusal('POLICY_REFUSED_OUTREACH')
        with self.assertRaisesRegex(Refusal,'POLICY_REFUSED_OUTREACH'):TrainingUnits({'fixture':self.permit},policy=deny).run('T4',{'records':[self.record]})
    def test_policy_missing_fail_closed(self):
        with self.assertRaisesRegex(Refusal,'APPLY_REFUSED_(UNAVAILABLE|UNKNOWN:analyze)'):TrainingUnits({'fixture':self.permit}).run('T1',{'records':[self.record]})
    def test_limits(self):
        self.record['text']='a'*100001
        with self.assertRaises(Refusal):self.engine.run('T1',{'records':[self.record]})
        with self.assertRaises(Refusal):self.engine.run('T1',{'records':[{}]*501})
    def test_url_guard(self):
        for url in ['http://localhost/x','https://127.0.0.1','https://user:pass@example.org','file:///etc/passwd','http://169.254.169.254','https://[::1]','https://example.org:444/x']:
            with self.subTest(url=url),self.assertRaises(Refusal):public_url(url)
    def test_fetch_guard_robots_limits(self):
        calls=[]
        def transport(url,limit):
            calls.append(url)
            return FetchResponse(200,'User-agent: *\nDisallow: /' if url.endswith('robots.txt') else 'OK',{})
        f=PublicFetcher({'fixture':self.permit},transport,clock=lambda:100)
        with self.assertRaisesRegex(Refusal,'SCRAPE'):f.fetch('fixture','https://example.org/book')
        self.assertEqual(calls,['https://example.org/robots.txt'])
    def test_rate_and_success(self):
        def t(u,n):return FetchResponse(200,'User-agent: *\nAllow: /' if u.endswith('robots.txt') else 'book',{})
        f=PublicFetcher({'fixture':self.permit},t,clock=lambda:100)
        self.assertEqual(f.fetch('fixture','https://example.org/book'),'book')
        with self.assertRaisesRegex(Refusal,'RATELIMIT'):f.fetch('fixture','https://example.org/book')
    def test_fetch_redirect_denied(self):
        f=PublicFetcher({'fixture':self.permit},lambda u,n:FetchResponse(302,'',{'Location':'http://127.0.0.1'}))
        with self.assertRaises(Refusal):f.fetch('fixture','https://example.org/book')
    def test_registry_counts_honest(self):
        r=registry_report()
        self.assertEqual(r['college_candidate_sites'],20);self.assertGreaterEqual(r['book_collections'],200)
        self.assertEqual(r['college_verified_sites'],0);self.assertEqual(r['book_independent_domains'],1)

if __name__=='__main__':unittest.main()
