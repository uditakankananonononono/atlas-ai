"""Audit regressions through real Service and SQL, no production shims."""
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.modules.m01_opportunity_discovery.service import Service
from app.modules.m01_opportunity_discovery.student_platforms import BY_ID

class BatchValidationRegression(unittest.TestCase):
    def item(self,url='https://example.org/a',**changes):
        return dict(title='Scholarship',url=url,description='lead',platform='fastweb',source_url=BY_ID['fastweb'].url,**changes)
    def scan(self,items):
        engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        self.addCleanup(engine.dispose);alerts=[]
        service=Service(session_factory=sessionmaker(bind=engine,expire_on_commit=False),sources=[],tenant_id='a',notifier=alerts.append,
            student_discoverer=lambda *a,**kw:{'platform':'fastweb','mode':BY_ID['fastweb'].mode,'items':items})
        result=service.run_scan(student_platform_ids=['fastweb'],notify_threshold=0)
        return service,result,alerts
    def test_all_raw_ingest_fields_rejected_before_batch_effects(self):
        for changes in [dict(extra_tags=[{}]),dict(extra_tags=[1]),dict(extra_tags=None),dict(extra_tags='tag'),dict(description=[]),dict(title=3),dict(url=4)]:
            with self.subTest(changes=changes):
                bad=self.item('https://example.org/b');bad.update(changes)
                service,result,alerts=self.scan([self.item(),bad])
                self.assertTrue(result.errors);self.assertEqual(service.list_opportunities(),[])
                self.assertEqual((result.new,result.updated,result.notified),(0,0,0));self.assertEqual(alerts,[])
    def test_local_literal_and_ambiguous_hosts_rejected(self):
        for host in ['127.0.0.1','10.0.0.1','169.254.169.254','0.0.0.0','[::1]','[fc00::1]','[::ffff:127.0.0.1]','localhost','foo.local','foo.internal','2130706433','127.1','0x7f000001','0177.0.0.1','999.999.999.999']:
            with self.subTest(host=host):
                service,result,alerts=self.scan([self.item('https://'+host+'/private')])
                self.assertTrue(result.errors);self.assertEqual(service.list_opportunities(),[]);self.assertEqual(alerts,[])
    def test_valid_tags_and_public_dns_preserve_rescan_and_alerts(self):
        service,result,alerts=self.scan([self.item(extra_tags=['biology','grant'])])
        self.assertFalse(result.errors);self.assertEqual(result.new,1);self.assertEqual(len(alerts),1)
        self.assertIn('biology',service.list_opportunities()[0].tags)
        again=service.run_scan(student_platform_ids=['fastweb'],notify_threshold=0)
        self.assertEqual((again.new,again.updated,again.notified),(0,1,0));self.assertEqual(len(alerts),1)
if __name__=='__main__':unittest.main()
