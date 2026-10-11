"""Pure schema/robots-rule tests; not evidence of live source collection."""
import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[2]/'backend/app/modules/m23_study_abroad/public_source_audit.py'
s=importlib.util.spec_from_file_location('m23audit',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def row():return {'id':'source','publisher':'Source','url':'https://example.org/case','evidence_type':'student_reported_admission','outcome_basis':'publisher_or_student_reported','example_school':'College'}
class AuditTests(unittest.TestCase):
 def test_normalize_derived_only(self):
  d=row();d['title']='Personal name';d['essay']='do not retain'
  r=m.normalize_sources([d])[0]
  self.assertNotIn('title',r);self.assertNotIn('essay',r)
  self.assertEqual(r['license_status'],'not_granted');self.assertFalse(r['body_collection_allowed'])
  self.assertEqual(r['outcome_status'],'source_reported_not_independently_verified')
 def test_unstated_school_remains_null(self):
  self.assertIsNone(m.normalize_sources([dict(row(),example_school=None)])[0]['example_school'])
 def test_exact_twenty_distinct_hosts(self):
  rows=[dict(row(),id='s'+str(i),url='https://site'+str(i)+'.org/case') for i in range(20)]
  self.assertEqual(len(m.normalize_sources(rows,required_count=20)),20)
  with self.assertRaises(ValueError):m.normalize_sources(rows[:19],required_count=20)
  rows[1]['url']=rows[0]['url']
  with self.assertRaises(ValueError):m.normalize_sources(rows,required_count=20)
 def test_invalid_identity_and_url(self):
  for url in ['http://example.org','https://user:pass@example.org','https://127.0.0.1','https://localhost','https://example.org:8443','https://example.org/#a']:
   with self.subTest(url=url),self.assertRaises(ValueError):m.normalize_sources([dict(row(),url=url)])
  with self.assertRaises(ValueError):m.normalize_sources([row(),row()])
 def test_robots_specific_agent_rules_and_delay(self):
  self.assertEqual(m.robots_decision('User-agent: *\nDisallow: /case\n',row()['url'])['status'],'robots_denied')
  r=m.robots_decision('User-agent: *\nAllow: /\nCrawl-delay: 12\n',row()['url'])
  self.assertEqual(r['status'],'robots_allowed');self.assertEqual(r['pace_seconds'],12)
 def test_malformed_robots_cannot_allow(self):
  for text in ['', '<html>Login</html>', 'not robots rules']:
   self.assertEqual(m.robots_decision(text,row()['url'])['status'],'robots_unverified')
 def test_unknown_and_denied_are_not_success(self):
  records=[dict(row(),robots_status=x,body_collection_allowed=False) for x in ['robots_unverified','robots_denied','robots_allowed']]
  report=m.summarize(records)
  self.assertEqual(report['collected_case_count'],0);self.assertEqual(report['checked_source_count'],3)
  self.assertEqual(report['status_counts'],{'robots_unverified':1,'robots_denied':1,'robots_allowed':1})
 def test_safe_output_no_claimed_rights(self):
  r=m.normalize_sources([row()])[0]
  self.assertEqual(r['schema_version'],'1');self.assertEqual(r['terms_status'],'unreviewed')
  self.assertEqual(r['reading_mode'],'publisher_page');self.assertFalse(r['training_rights_granted'])
if __name__=='__main__':unittest.main()
