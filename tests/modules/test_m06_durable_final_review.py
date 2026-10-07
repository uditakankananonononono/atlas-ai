"""Actual M00 durable review, local SQL media/account seam, no publish/provider."""
from datetime import datetime,timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest
from app.core.database import Base
from app.modules.m00_approval_center.service import Service as ApprovalService
from app.modules.m06_social_media_manager.sql_repository import SqlSocialRepository
from app.modules.m06_social_media_manager.scheduler import Scheduler,ScheduleEntry,ScheduleStateError
from app.modules.m06_social_media_manager.models import Platform

@pytest.mark.parametrize('kind',['sqlite','postgres'])
def test_exact_final_review_durable_m00_expiry_and_stale_media_binding(tmp_path,kind):
 if kind=='postgres':
  pgserver=pytest.importorskip('pgserver');server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
  url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
 else:url=f'sqlite:///{tmp_path}/review.db'
 engine=create_engine(url);Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False)
 repo=SqlSocialRepository('a',sessions);m00=ApprovalService(session_factory=sessions)
 class Factory:
  def account_id(self,platform):return 'fixture-verified-account'
  def for_platform(self,*args):raise AssertionError('no adapter effect permitted')
 class Decisions:
  def status_of(self,*args):return None
 scheduler=Scheduler(repository=repo,decisions=Decisions(),adapter_factory=Factory())
 entry=ScheduleEntry(id='s',plan_id='p',platform=Platform.INSTAGRAM,format='carousel',text='fixture',publish_at=datetime.now(timezone.utc),approval_id='old')
 repo.save_schedule(entry)
 with pytest.raises(ScheduleStateError,match='rendered media'):scheduler.request_final_review('s','a',m00)
 assert m00.list(user_id='a')==[]
 scheduler.attach_media('s',['https://fixture.invalid/rendered.png'],['Fixture alt'])
 card=scheduler.request_final_review('s','a',m00)
 assert card['status']=='pending' and card['expires_at'] is not None
 assert card['payload']['media_urls']==['https://fixture.invalid/rendered.png'] and card['payload']['account_id']=='fixture-verified-account'
 assert repo.get_schedule('s').approval_id==card['id'] and repo.get_schedule('s').status=='awaiting_approval'
 # Actual durable source after constructing a fresh M00 service.
 assert ApprovalService(session_factory=sessions).get(card['id'])['payload']==card['payload']
 snapshot=repo.get_schedule('s');scheduler.attach_media('s',['https://fixture.invalid/new.png'],['Changed'])
 assert not repo.bind_final_review(snapshot,'stale-card')
 assert repo.get_schedule('s').approval_id==card['id']
 assert SqlSocialRepository('b',sessions).bind_final_review(repo.get_schedule('s'),'other-card') is False
 engine.dispose()


def test_compatibility_facade_retains_expiry_for_real_final_review_grant(tmp_path,monkeypatch):
 from app.core.approvals import ApprovalStore
 from app.core.models import ApprovalStatus
 import app.core.approvals as facade
 from app.modules.m06_social_media_manager.routes import _ApprovalCenterLookup
 engine=create_engine(f'sqlite:///{tmp_path}/expiry.db');Base.metadata.create_all(engine)
 sessions=sessionmaker(bind=engine,expire_on_commit=False);m00=ApprovalService(session_factory=sessions)
 monkeypatch.setattr(facade,'default_service',lambda:m00)
 repo=SqlSocialRepository('a',sessions)
 entry=ScheduleEntry(id='s',plan_id='p',platform=Platform.TWITTER,format='thread',text='fixture',publish_at=datetime.now(timezone.utc),approval_id='old')
 repo.save_schedule(entry)
 class Factory:
  def account_id(self,p):return 'fixture-account'
 scheduler=Scheduler(repository=repo,decisions=None,adapter_factory=Factory())
 card=scheduler.request_final_review('s','a',m00)
 m00.decide(card['id'],ApprovalStatus.APPROVED,'fixture-owner')
 store=ApprovalStore();monkeypatch.setattr(facade,'approvals',store)
 observed=store.get(card['id'],user_id='a')
 assert observed.expires_at is not None
 lookup=_ApprovalCenterLookup('a')
 bound=repo.get_schedule('s')
 assert lookup.authorizes(bound,account_id='fixture-account')
 scheduler.attach_media('s',['https://fixture.invalid/unreviewed.png'])
 assert not lookup.authorizes(repo.get_schedule('s'),account_id='fixture-account')
 engine.dispose()


def test_runtime_final_review_refuses_unverified_environment_account_before_m00(tmp_path):
 from app.modules.m06_social_media_manager.routes import _EnvAdapterFactory
 from app.modules.m06_social_media_manager.service import MemorySocialRepository
 repo=MemorySocialRepository();repo.save_schedule(ScheduleEntry(id='s',plan_id='p',platform=Platform.TWITTER,format='thread',text='fixture',publish_at=datetime.now(timezone.utc),approval_id='old'))
 class NoSubmit:
  def submit(self,**kwargs):raise AssertionError('unverified account must not create review')
 scheduler=Scheduler(repository=repo,decisions=None,adapter_factory=_EnvAdapterFactory())
 with pytest.raises(ScheduleStateError,match='identity unavailable'):scheduler.request_final_review('s','a',NoSubmit())


@pytest.mark.parametrize('kind',['sqlite','postgres'])
def test_atomic_review_stale_snapshot_rollback_and_duplicate_proposal(tmp_path,kind,monkeypatch):
 from sqlalchemy import event,select,func
 from app.modules.m00_approval_center.service import ApprovalRequestRow,ApprovalEventRow
 if kind=='postgres':
  pgserver=pytest.importorskip('pgserver');server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
  url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
 else:url=f'sqlite:///{tmp_path}/atomic.db'
 engine=create_engine(url);Base.metadata.create_all(engine);sessions=sessionmaker(bind=engine,expire_on_commit=False)
 repo=SqlSocialRepository('a',sessions);m00=ApprovalService(session_factory=sessions)
 class Factory:
  def account_id(self,p):return 'fixture-account'
 scheduler=Scheduler(repository=repo,decisions=None,adapter_factory=Factory())
 entry=ScheduleEntry(id='s',plan_id='p',platform=Platform.TWITTER,format='thread',text='fixture',publish_at=datetime.now(timezone.utc),approval_id='old');repo.save_schedule(entry)
 original=scheduler.final_review_payload
 def interleave(sid,tenant,**kwargs):
  changed=repo.get_schedule(sid);changed.text='changed';repo.save_schedule(changed)
  return original(sid,tenant,**kwargs)
 monkeypatch.setattr(scheduler,'final_review_payload',interleave)
 with pytest.raises(ScheduleStateError):scheduler.request_final_review('s','a',m00)
 assert m00.list(user_id='a')==[] and repo.get_schedule('s').approval_id=='old'
 monkeypatch.setattr(scheduler,'final_review_payload',original)
 def fail(mapper,conn,target):raise RuntimeError('fixture approval insert fail')
 event.listen(ApprovalRequestRow,'before_insert',fail)
 try:
  with pytest.raises(ScheduleStateError):scheduler.request_final_review('s','a',m00)
 finally:event.remove(ApprovalRequestRow,'before_insert',fail)
 assert repo.get_schedule('s').approval_id=='old' and m00.list(user_id='a')==[]
 first=scheduler.request_final_review('s','a',m00);second=scheduler.request_final_review('s','a',m00)
 assert first['id']==second['id'] and len(m00.list(user_id='a'))==1
 with sessions() as db:assert db.scalar(select(func.count()).select_from(ApprovalEventRow))==1
 engine.dispose()
