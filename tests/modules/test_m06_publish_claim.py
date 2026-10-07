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
