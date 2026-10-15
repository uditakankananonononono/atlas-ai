import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.modules.m01_opportunity_discovery.service import Service
from app.modules.m01_opportunity_discovery.student_platforms import BY_ID

def setup(items):
 p=BY_ID['fastweb'];e=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
 def discover(*a,**kw):return {'platform':'fastweb','mode':p.mode,'items':items}
 return Service(session_factory=sessionmaker(bind=e,expire_on_commit=False),sources=[],tenant_id='a',student_discoverer=discover)
def item(url='https://example.org/a',**kw):return dict(title='Scholarship',url=url,description='lead',platform='fastweb',source_url=BY_ID['fastweb'].url,**kw)
def test_malformed_second_row_cannot_partially_commit():
 s=setup([item(),item('https://example.org/b',extra_tags=[{}])]);r=s.run_scan(student_platform_ids=['fastweb']);assert r.errors
 assert s.list_opportunities()==[], 'malformed batch partially persisted'
def test_private_https_is_not_public_listing():
 s=setup([item('https://127.0.0.1/private')]);r=s.run_scan(student_platform_ids=['fastweb']);assert r.errors,'private link admitted by public-HTTPS validator'
def test_invalid_batches_fail_before_store():
 for raw in [[item(),dict(item(),source_url='https://wrong.test')],[item(),dict(item(),url='http://example.org')],[item(),dict(item(),title=' ')]]:
  s=setup(raw);r=s.run_scan(student_platform_ids=['fastweb']);assert r.errors and not s.list_opportunities()
def test_returned_url_never_fetched():
 s=setup([item()]);r=s.run_scan(student_platform_ids=['fastweb']);assert r.new==1

def test_url_syntax_userinfo_and_legacy_hex_pin():
 from app.modules.m01_opportunity_discovery.service import _validate_listing_url
 for u in ['https://0x7f.0.0.0x1/a','https://user:secret@example.org/a','https://@example.org/a','https://example.org/a\\b','https://example.org/a\tb','https://example.org:70000/a']:
  with pytest.raises(ValueError):_validate_listing_url(u)
 for u in ['https://example.org/a','https://8.8.8.8/a','https://[2606:4700:4700::1111]/a']:_validate_listing_url(u)
def test_batch_and_each_item_provenance_pin():
 for wrong in ['platform','mode']:
  s=setup([item()]);p=BY_ID['fastweb'];batch={'platform':'fastweb','mode':p.mode,'items':[item()]};batch[wrong]='wrong'
  s._student_discoverer=lambda *a,**k:batch
  r=s.run_scan(student_platform_ids=['fastweb']);assert r.errors and not s.list_opportunities()
 s=setup([dict(item(),platform='wrong')]);r=s.run_scan(student_platform_ids=['fastweb']);assert r.errors and not s.list_opportunities()
def test_snapshot_copy_survives_mutation_between_notifications():
 items=[item(),item('https://example.org/b')];s=setup(items)
 def notify(row):items[-1]['extra_tags']=[{}]
 s._notifier=notify
 r=s.run_scan(student_platform_ids=['fastweb'],notify_threshold=0)
 assert not r.errors and r.new==2 and len(s.list_opportunities())==2
