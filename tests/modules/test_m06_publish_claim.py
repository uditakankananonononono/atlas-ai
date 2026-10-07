"""SQL publish claims: hermetic SQLite and real temporary PG, no adapters."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from datetime import datetime,timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m06_social_media_manager.sql_repository import SqlSocialRepository,SocialScheduleRow
from app.modules.m06_social_media_manager.scheduler import ScheduleEntry
from app.modules.m06_social_media_manager.models import Platform

@pytest.mark.parametrize('kind',['sqlite','postgres'])
def test_sql_publish_claim_matches_tenant_payload_and_has_single_winner(tmp_path,kind):
 if kind=='postgres':
  pgserver=pytest.importorskip('pgserver')
  server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
  url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
 else:url=f'sqlite:///{tmp_path}/claims.db'
 engine=create_engine(url);SocialScheduleRow.__table__.create(engine)
 sessions=sessionmaker(bind=engine);repo=SqlSocialRepository('a',sessions)
 entry=ScheduleEntry(id='s',plan_id='p',platform=Platform.TWITTER,format='thread',text='fixture',publish_at=datetime.now(timezone.utc),approval_id='approval',status='approved')
 repo.save_schedule(entry)
 assert SqlSocialRepository('b',sessions).claim_publish(entry) is None
 changed=deepcopy(entry);changed.text='wrong text'
 assert repo.claim_publish(changed) is None
 barrier=Barrier(2)
 def claim(_):
  candidate=SqlSocialRepository('a',sessions).get_schedule('s');barrier.wait(timeout=5)
  return SqlSocialRepository('a',sessions).claim_publish(candidate)
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(claim,[1,2]))
 assert sum(x is not None for x in results)==1
 assert repo.get_schedule('s').status=='publishing'
 with pytest.raises(ValueError,match='cannot be reset'):repo.save_schedule(entry)
 claimed=next(x for x in results if x is not None);claimed.text='mutated';claimed.status='published'
 with pytest.raises(ValueError,match='payload cannot change'):repo.save_schedule(claimed)
 assert repo.get_schedule('s').text=='fixture'
 engine.dispose()


@pytest.mark.parametrize('kind',['sqlite','postgres'])
def test_sql_finalize_receipt_failure_rolls_back_claim_status(tmp_path,kind):
 from sqlalchemy import event
 from app.modules.m06_social_media_manager.sql_repository import SocialPublishRow
 from app.modules.m06_social_media_manager.scheduler import PublishRecord
 if kind=='postgres':
  pgserver=pytest.importorskip('pgserver');server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
  url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
 else:url=f'sqlite:///{tmp_path}/finalize.db'
 engine=create_engine(url)
 SocialScheduleRow.__table__.create(engine);SocialPublishRow.__table__.create(engine)
 sessions=sessionmaker(bind=engine);repo=SqlSocialRepository('a',sessions)
 entry=ScheduleEntry(id='s',plan_id='p',platform=Platform.TWITTER,format='thread',text='fixture',publish_at=datetime.now(timezone.utc),approval_id='approval',status='approved')
 repo.save_schedule(entry);claimed=repo.claim_publish(entry)
 claimed.status='published';claimed.external_id='receipt';claimed.published_at=entry.publish_at
 receipt=PublishRecord(schedule_id='s',platform='twitter',external_id='receipt',external_url=None,draft_only=False,published_at=entry.publish_at)
 def fail(mapper,conn,target):raise RuntimeError('fixture receipt insert failure')
 event.listen(SocialPublishRow,'before_insert',fail)
 try:
  with pytest.raises(RuntimeError,match='receipt insert failure'):repo.finalize_publish(claimed,receipt)
 finally:event.remove(SocialPublishRow,'before_insert',fail)
 assert repo.get_schedule('s').status=='publishing'
 assert repo.list_publish_records('s')==[]
 assert repo.claim_publish(entry) is None
 assert repo.finalize_publish(claimed,receipt).external_id=='receipt'
 assert repo.get_schedule('s').status=='published'
 assert len(repo.list_publish_records('s'))==1
 with pytest.raises(ValueError,match='no longer active'):repo.finalize_publish(claimed,receipt)
 assert len(repo.list_publish_records('s'))==1
 engine.dispose()


@pytest.mark.parametrize('kind',['memory','sqlite','postgres'])
def test_finalize_rejects_mismatched_receipt_and_state(tmp_path,kind):
 from dataclasses import replace
 from datetime import timedelta
 from app.modules.m06_social_media_manager.sql_repository import SocialPublishRow
 from app.modules.m06_social_media_manager.scheduler import PublishRecord
 from app.modules.m06_social_media_manager.service import MemorySocialRepository
 if kind=='memory':repo=MemorySocialRepository()
 else:
  if kind=='postgres':
   pgserver=pytest.importorskip('pgserver');server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
   url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
  else:url=f'sqlite:///{tmp_path}/mismatch.db'
  engine=create_engine(url);SocialScheduleRow.__table__.create(engine);SocialPublishRow.__table__.create(engine)
  repo=SqlSocialRepository('a',sessionmaker(bind=engine))
 entry=ScheduleEntry(id='s',plan_id='p',platform=Platform.TWITTER,format='thread',text='fixture',publish_at=datetime.now(timezone.utc),approval_id='approval',status='approved')
 repo.save_schedule(entry);claimed=repo.claim_publish(entry)
 claimed.status='published';claimed.external_id='receipt';claimed.external_url='https://fixture.invalid/post';claimed.published_at=entry.publish_at
 receipt=PublishRecord(schedule_id='s',platform='twitter',external_id='receipt',external_url=claimed.external_url,draft_only=False,published_at=entry.publish_at)
 for changes in ({'schedule_id':'other'},{'external_id':'other'},{'platform':'instagram'},{'external_url':'https://other.invalid/'},{'draft_only':True},{'published_at':entry.publish_at+timedelta(seconds=1)}):
  with pytest.raises(ValueError,match='receipt does not match'):repo.finalize_publish(claimed,replace(receipt,**changes))
 for status in ['approved','outcome_unknown','publishing']:
  with pytest.raises(ValueError,match='requires published'):repo.finalize_publish(replace(claimed,status=status),receipt)
 assert repo.get_schedule('s').status=='publishing' and repo.list_publish_records('s')==[]
 assert repo.finalize_publish(claimed,receipt)==receipt
 if kind!='memory':engine.dispose()
