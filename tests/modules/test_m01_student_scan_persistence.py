"""Hermetic real Service/SQL integration, no live site or outreach claims."""
import unittest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.modules.m01_opportunity_discovery.service import Service, OpportunityRow
from app.modules.m01_opportunity_discovery.schemas import ProfileIn, ScanRequestIn
from app.modules.m01_opportunity_discovery.student_platforms import BY_ID


class StudentScanPersistenceTest(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        self.sessions=sessionmaker(bind=self.engine,expire_on_commit=False)
        self.calls=[];self.alerts=[]
        def discover(pid,query,limit):
            self.calls.append((pid,query,limit))
            p=BY_ID[pid]
            return {'platform':pid,'mode':p.mode,'items':[{'title':'Biology scholarship',
                'url':'https://example.org/biology','description':'Student biology scholarship',
                'platform':pid,'source_url':p.url}]}
        self.discover=discover
    def tearDown(self):self.engine.dispose()
    def service(self,tenant='alice',discover=None):
        return Service(session_factory=self.sessions,sources=[],tenant_id=tenant,
                       student_discoverer=discover or self.discover,notifier=self.alerts.append)
    def test_persists_and_rescans_real_tenant_sql(self):
        service=self.service()
        result=service.run_scan(student_platform_ids=['fastweb'],student_query='biology',
                                profile=ProfileIn(interests=['biology']),notify_threshold=0)
        self.assertEqual((result.scanned_sources,result.fetched,result.new,result.updated),(1,1,1,0))
        rows=service.list_opportunities();self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].source_id,'student-platform:fastweb')
        self.assertEqual(rows[0].url,'https://example.org/biology')
        self.assertEqual(rows[0].source_url,BY_ID['fastweb'].url)
        self.assertEqual(len(self.alerts),1)
        second=service.run_scan(student_platform_ids=['fastweb'],notify_threshold=0)
        self.assertEqual((second.new,second.updated,second.notified),(0,1,0))
        self.assertEqual(self.service('bob').list_opportunities(),[])
        other=self.service('bob').run_scan(student_platform_ids=['fastweb'])
        self.assertEqual(other.new,1)
        with self.sessions() as session:
            self.assertEqual(len(session.scalars(select(OpportunityRow)).all()),2)
    def test_opt_in_and_launch_only_never_fetch(self):
        service=self.service();self.assertEqual(service.run_scan().scanned_sources,0)
        result=service.run_scan(student_platform_ids=['ripplematch'])
        self.assertEqual(len(result.errors),1);self.assertEqual(result.fetched,0)
        self.assertEqual(self.calls,[]);self.assertEqual(service.list_opportunities(),[])
    def test_failed_source_does_not_abort_next(self):
        def discover(pid,query,limit):
            if pid=='fastweb':raise RuntimeError('blocked')
            return self.discover(pid,query,limit)
        service=self.service(discover=discover)
        result=service.run_scan(student_platform_ids=['fastweb','scholarshiproar'])
        self.assertEqual((len(result.errors),result.fetched,result.new),(1,1,1))
        self.assertEqual(result.errors[0].source_id,'student-platform:fastweb')
    def test_entire_selection_validated_before_io(self):
        for ids in [['fastweb','unknown'],['fastweb','fastweb'],'fastweb']:
            with self.assertRaises(ValueError):self.service().run_scan(student_platform_ids=ids)
        for kwargs in [dict(student_limit=True),dict(student_limit=101),dict(student_query='x'*201)]:
            with self.assertRaises(ValueError):self.service().run_scan(student_platform_ids=['fastweb'],**kwargs)
        self.assertEqual(self.calls,[])
    def test_bad_batch_provenance_cannot_partially_persist(self):
        for mode in ['provenance','unsafe']:
            def discover(pid,query,limit):
                out=self.discover(pid,query,limit)
                bad=dict(out['items'][0]);bad['url']='http://example.org/insecure' if mode=='unsafe' else bad['url']
                if mode=='provenance':bad['source_url']='https://not-source.invalid/'
                out['items'].append(bad);return out
            service=self.service(discover=discover)
            result=service.run_scan(student_platform_ids=['fastweb'])
            self.assertEqual(len(result.errors),1)
            self.assertEqual(service.list_opportunities(),[])
    def test_real_discovery_adapter_parses_feed_into_sql(self):
        import httpx
        from app.modules.m01_opportunity_discovery.student_platforms import discover
        payload=b'<rss><channel><item><title>Biology award</title><link>https://example.org/award</link><description>Biology scholarship</description></item></channel></rss>'
        requested=[]
        def transport(request):
            requested.append(str(request.url))
            return httpx.Response(200,content=payload,headers={'content-type':'application/rss+xml'})
        with httpx.Client(transport=httpx.MockTransport(transport)) as client:
            service=self.service(discover=lambda pid,query,limit:discover(pid,query,limit=limit,client=client))
            result=service.run_scan(student_platform_ids=['scholarshiproar'],student_query='biology')
        self.assertEqual((result.fetched,result.new,len(result.errors)),(1,1,0))
        self.assertEqual(requested,[BY_ID['scholarshiproar'].url])
        stored=service.list_opportunities()[0]
        self.assertEqual(stored.title,'Biology award')
        self.assertEqual(stored.source_url,BY_ID['scholarshiproar'].url)

    def test_mounted_existing_scan_route_persists_and_rejects_unknown(self):
        # Requires the real repository route dependencies, not substitute
        # module shims. Only tenant/service dependencies are overridden.
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.auth.context import TenantContext, require_tenant
        from app.modules.m01_opportunity_discovery.routes import router, get_service
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[require_tenant]=lambda:TenantContext('alice','alice')
        app.dependency_overrides[get_service]=lambda:self.service()
        with TestClient(app) as client:
            response=client.post('/opportunity-discovery/scans',json={
                'source_ids':[], 'student_platform_ids':['fastweb'],
                'student_query':'biology','student_limit':2})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['new'],1)
            listed=client.get('/opportunity-discovery/opportunities')
            self.assertEqual(listed.status_code,200,listed.text)
            self.assertEqual(listed.json()[0]['source_url'],BY_ID['fastweb'].url)
            bad=client.post('/opportunity-discovery/scans',json={
                'source_ids':[], 'student_platform_ids':['unknown']})
            self.assertEqual(bad.status_code,422,bad.text)
        self.assertEqual(len(self.calls),1)

    def test_request_schema_has_explicit_bounded_selection(self):
        request=ScanRequestIn(student_platform_ids=['fastweb'],student_query='biology',student_limit=2)
        self.assertEqual(request.student_platform_ids,['fastweb'])
        for kwargs in [dict(student_limit=101),dict(student_query='x'*201),dict(student_platform_ids=['fastweb']*28)]:
            with self.assertRaises(ValueError):ScanRequestIn(**kwargs)

if __name__=='__main__':unittest.main()
