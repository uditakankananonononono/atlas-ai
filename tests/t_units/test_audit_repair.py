import unittest,sys,types,json,hashlib,dataclasses
from unittest.mock import patch
import test_training_units as t
m=t.m
class AuditRepair(unittest.TestCase):
    def setUp(self):
        t.TrainingTests.setUp(self)
        self.search={'kind':'blog','source_id':'fixture','url':'https://example.org/rss','as_of':'2026-10-11','content':'<rss><channel><item><title>A</title><link>https://example.org/a</link><description>Text</description></item></channel></rss>'}
    def test_t2_rights_security_flags(self):
        for patch_ in [{'source_id':'unknown'},{'url':'https://other.org/rss'},{'as_of':'invalid'},{'paywalled':True},{'piracy':True},{'credentials':'x'},{'logged_in':True}]:
            with self.subTest(patch_=patch_),self.assertRaises(m.Refusal):self.engine.run('T2',dict(self.search,**patch_))
        self.engine.permits['fixture']=dataclasses.replace(self.permit,license='GPL')
        with self.assertRaises(m.Refusal):self.engine.run('T2',self.search)
    def test_actions_each_unit(self):
        for u in ['T1','T2','T3','T4']:
            events=[];e=m.TrainingUnits({'fixture':self.permit},policy=lambda action:events.append(action))
            action={'type':'research','spend':False}
            e.run(u,dict(self.search,action=action) if u=='T2' else {'records':[self.record],'action':action})
            self.assertEqual(events,[action])
    def test_shared_guard_called_and_missing(self):
        import tunit_routes_fixture.training_data_units as real
        name='app.modules.c30.policy';stub=types.ModuleType(name);events=[]
        def check(action,prefix):
            events.append((action,prefix));raise ValueError(prefix+'_REFUSED_SPEND')
        stub.check=check
        parent=types.ModuleType('app.modules.c30');parent.__path__=[]
        with patch.dict(sys.modules,{'app.modules.c30':parent,name:stub}):
            for unit,prefix in [('T1','APPLY'),('T2','TREND'),('T3','TREND'),('T4','FLEET')]:
                e=real.TrainingUnits({'fixture':real.SourcePermit(**dataclasses.asdict(self.permit))})
                p=dict(self.search,action={'spend':True}) if unit=='T2' else {'records':[self.record],'action':{'spend':True}}
                with self.assertRaisesRegex(ValueError,prefix+'_REFUSED_SPEND'):e.run(unit,p)
            self.assertEqual(events,[('spend','APPLY'),('spend','TREND'),('spend','TREND'),('spend','FLEET')])
        with patch.dict(sys.modules,{'app.modules.c30.policy':None}):
            with self.assertRaisesRegex(ValueError,'APPLY_REFUSED_UNAVAILABLE'):real.shared_policy({},'APPLY')
    def test_policy_return_strict(self):
        for result in [0,1,'yes',[],{}, {'allowed':1},{'allowed':'true'}, {'allowed':False}]:
            with self.subTest(result=result),self.assertRaises(m.Refusal):m.TrainingUnits({'fixture':self.permit},policy=lambda p:result).run('T1',{'records':[self.record]})
        for result in [None,True,{'allowed':True}]:m.TrainingUnits({'fixture':self.permit},policy=lambda p:result).run('T1',{'records':[self.record]})
    def test_action_shape(self):
        for action in [None,[],True,{'nested':{'spend':True}},{'spend':[True]}]:
            with self.subTest(action=action),self.assertRaises(m.Refusal):self.engine.run('T1',{'records':[self.record],'action':action})
    def test_url_exact_and_boundary(self):
        for url in [None,42,'https://example.org:abc','https://single','https://foo.local','https://foo.internal','https://foo.localhost','https://example.org.','https://127.1/','https://example.org/\n','https://example.org/'+'x'*4077]:
            with self.subTest(url=url),self.assertRaises(m.Refusal):m.public_url(url)
        url='https://example.org/'+'x'*(4096-len('https://example.org/'))
        self.assertEqual(m.public_url(url),url)
    def test_permit_positive_and_invalid_origin(self):
        for license in ['CC0','CC-BY-4.0','CC-BY-SA-4.0','public-domain','permission-granted']:
            dataclasses.replace(self.permit,license=license).allows(self.record['url'])
        for p in [dataclasses.replace(self.permit,origin='http://example.org'),dataclasses.replace(self.permit,terms_url='http://example.org/terms'),dataclasses.replace(self.permit,terms_allowed='yes')]:
            with self.subTest(p=p),self.assertRaises(m.Refusal):p.allows(self.record['url'])
        with self.assertRaises(dataclasses.FrozenInstanceError):self.permit.origin='https://other.org'
        f=m.FetchResponse(200,'a',{})
        with self.assertRaises(dataclasses.FrozenInstanceError):f.status=404
    def test_fetch_permit_and_status(self):
        calls=[]
        def transport(u,n):calls.append((u,n));return m.FetchResponse(200,'User-agent: *\nAllow: /' if u.endswith('robots.txt') else 'body',{})
        for permit,url in [(None,'https://example.org/a'),(dataclasses.replace(self.permit,terms_allowed=False),'https://example.org/a'),(self.permit,'https://other.org/a'),(self.permit,'http://example.org/a')]:
            with self.assertRaises(m.Refusal):m.PublicFetcher({} if permit is None else {'fixture':permit},transport).fetch('fixture',url)
        self.assertEqual(calls,[])
        for status in [201,302,403,500]:
            def tr(u,n):return m.FetchResponse(200,'User-agent: *\nAllow: /',{}) if u.endswith('robots.txt') else m.FetchResponse(status,'body',{})
            with self.assertRaisesRegex(m.Refusal,'FETCH'):m.PublicFetcher({'fixture':self.permit},tr).fetch('fixture',self.record['url'])
    def test_fetch_boundaries_agents_delay(self):
        for robots in ['User-agent: AtlasPublicCorpus\nDisallow: /\nUser-agent: *\nAllow: /','User-agent: AtlasPublicCorpus\nAllow: /\nCrawl-delay: 61\nUser-agent: *\nAllow: /','User-agent: *\nAllow: /\nCrawl-delay: 61']:
            with self.assertRaises(m.Refusal):m.PublicFetcher({'fixture':self.permit},lambda u,n:m.FetchResponse(200,robots if u.endswith('robots.txt') else 'a',{})).fetch('fixture',self.record['url'])
        clock=[0];calls=[]
        def tr(u,n):calls.append(u);return m.FetchResponse(200,'User-agent: *\nAllow: /\nCrawl-delay: 60' if u.endswith('robots.txt') else 'x'*100000,{})
        f=m.PublicFetcher({'fixture':dataclasses.replace(self.permit,origin='https://example.org/')},tr,clock=lambda:clock[0])
        self.assertEqual(len(f.fetch('fixture',self.record['url'])),100000);clock[0]=60;f.fetch('fixture',self.record['url'])
        self.assertEqual(calls[0],'https://example.org/robots.txt')
        one=m.PublicFetcher({'fixture':self.permit},tr,limit=1);self.assertEqual(one.limit,1)
    def test_plain_full(self):
        self.assertEqual(m.plain('A<script>HIDDEN</script>B<style>HIDDEN</style>C'), 'ABC')
        self.assertEqual(m.plain('<script>hidden<style>hidden</style>hidden</script>visible'),'visible')
        self.assertEqual(m.plain('A<p>B</p>C<div>D</div>E<br>F</br>G<li>H</li>I<h1>J</h1>K<h2>L</h2>M'),'AB\nCD\nEF\nGH\nIJ\nKL\nM')
    def test_normalization_fields_and_limits(self):
        record=dict(self.record,text='SAT: 1500\nACT: 34\nGPA: 4.0\nOutcome: yes\nEssay: '+('x '*300))
        r=self.engine.run('T1',{'records':[record]})['records'][0]
        self.assertEqual(r,{'source_id':'fixture','url':record['url'],'license':'CC-BY-4.0','terms_url':self.permit.terms_url,'rights_checked_at':'2026-10-11','as_of':'2026-10-11','sha256':hashlib.sha256(record['text'].encode()).hexdigest(),'stats':{'SAT':'1500','ACT':'34','GPA':'4.0'},'outcomes':['yes'],'essay_summary':' '.join(record['text'].split())[:500],'summary_method':'bounded extractive excerpt, not generative','outcome_verified':False})
        self.assertEqual(len(self.engine.run('T1',{'records':[dict(self.record,text='x'*100000)]})['records']),1)
        self.assertEqual(len(self.engine.run('T1',{'records':[dict(self.record,text=str(i)) for i in range(500)]})['records']),500)
        for u,prefix in [('T3','TREND'),('T4','FLEET')]:
            with self.assertRaisesRegex(m.Refusal,prefix+'_REFUSED_SCRAPE'):self.engine.run(u,{'records':[dict(self.record,source_id='bad')]})
    def test_output_scope_concepts_advice(self):
        rec=dict(self.record,text='Always '+('x '*300))
        r=self.engine.run('T3',{'records':[rec]});candidate=r['concept_candidates'][0]
        self.assertEqual(candidate,{'technique':rec['text'].strip()[:500],'source_url':rec['url'],'source_sha256':hashlib.sha256(rec['text'].encode()).hexdigest(),'status':'candidate_not_installed'})
        self.assertEqual(r['scope'],{'implemented':'bounded supplied-source normalization and preparation','not_implemented':['model training','live accounts','automatic online actions','complete internet coverage'],'data_source':'supplied licensed documents','as_of':'2026-10-11'})
        action={'type':'research'};r=self.engine.run('T4',{'records':[rec],'task':'plan','action':action})
        self.assertEqual(r['log'],[{'stage':'advice','sources':[rec['url']],'summaries':[rec['text'][:500]]},{'stage':'policy','status':'passed'},{'stage':'prepared','action':action}]);self.assertEqual(r['task'],'plan')
        rec=dict(self.record,text='\n'.join('Test '+str(i) for i in range(501)));self.assertEqual(len(self.engine.run('T3',{'records':[rec]})['concept_candidates']),500)
    def test_atom_and_search_scope(self):
        content='<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Advice</title><link href="https://example.org/advice"/><summary>'+('x '*300)+'</summary></entry><unknown>ignore</unknown></feed>'
        r=self.engine.run('T2',dict(self.search,content=content));self.assertEqual(r,{'unit':'T2','kind':'blog','results':[{'title':'Advice','url':'https://example.org/advice','summary':('x '*300).strip()[:500]}],'matched_in_input':1,'scope':{'implemented':'RSS/Atom and GitHub public-search-response adapters over supplied payloads','not_implemented':['live GitHub credentials','automatic transcript retrieval','unbounded crawling'],'data_source':self.search['url'],'as_of':'2026-10-11'}})
        self.assertEqual(self.engine.run('T2',dict(self.search,query='A Text'))['matched_in_input'],1)
        self.assertEqual(self.engine.run('T2',dict(self.search,query='x'*1000))['results'],[])
        for c in ['<!ENTITY x><rss/>','<!DOCTYPE rss><rss/>']:
            with self.assertRaisesRegex(m.Refusal,'XML'):self.engine.run('T2',dict(self.search,content=c))
        bad='<rss xmlns:p="https://podcastindex.org/namespace/1.0"><channel><item><title>A</title><p:transcript url="http://127.0.0.1"/></item></channel></rss>'
        self.assertEqual(self.engine.run('T2',dict(self.search,kind='podcast',content=bad))['results'],[])
    def test_registry_ingested_and_verified(self):
        r=m.registry_report();self.assertEqual(r['ingested_records'],0)
        real=m.Path.read_text
        def fake(path,*args,**kwargs):
            if path.name=='college_candidates.json':return json.dumps([{'url':'https://example.org','status':'verified'}])
            return real(path,*args,**kwargs)
        with patch.object(m.Path,'read_text',fake):self.assertEqual(m.registry_report()['college_verified_sites'],1)
    def test_boundary_positive_ipv4_and_origin_whitespace(self):
        self.assertEqual(m.public_url('https://8.8.8.8/'),'https://8.8.8.8/')
        with self.assertRaises(m.Refusal):dataclasses.replace(self.permit,origin='https://example.org/\n').allows(self.record['url'])
    def test_fetch_robot_body_exact_limit(self):
        robots='User-agent: *\nAllow: /\n#'+'x'*100
        f=m.PublicFetcher({'fixture':self.permit},lambda u,n:m.FetchResponse(200,robots if u.endswith('robots.txt') else 'a',{}),limit=len(robots))
        self.assertEqual(f.fetch('fixture',self.record['url']),'a')
    def test_atom_nonentry_not_extracted(self):
        content='<feed xmlns="http://www.w3.org/2005/Atom"><unknown><title>not entry</title><link href="https://example.org/notentry"/></unknown><entry><title>real</title><link href="https://example.org/real"/></entry></feed>'
        self.assertEqual([r['title'] for r in self.engine.run('T2',dict(self.search,content=content))['results']],['real'])
