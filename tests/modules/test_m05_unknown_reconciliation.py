"""Reconciliation CAS seam, actual temporary DB writes; no email/provider."""
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m05_outreach_manager.campaigns import OutreachMessage,MessageEvent,InMemoryCampaignRepository
from app.modules.m05_outreach_manager.sql_repository import SqlCampaignRepository,MessageRow,MessageEventRow,DeliveryClaimRow

@pytest.mark.parametrize('kind',['memory','sqlite','postgres'])
def test_reconciliation_requires_claim_owner_status_version_and_one_winner(tmp_path,kind):
 if kind=='memory':
  repo=InMemoryCampaignRepository();factory=lambda:repo
 else:
  if kind=='postgres':
   pgserver=pytest.importorskip('pgserver');server=pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
   url=server.get_uri().replace('postgresql://','postgresql+psycopg://')
  else:url=f'sqlite:///{tmp_path}/reconcile.db'
  engine=create_engine(url)
  for model in (MessageRow,MessageEventRow,DeliveryClaimRow):model.__table__.create(engine)
  sessions=sessionmaker(bind=engine);factory=lambda:SqlCampaignRepository('a',sessions);repo=factory()
 now=datetime.now(timezone.utc)
 m=OutreachMessage(id='m',campaign_id='c',contact_id='u',sequence=1,subject='fixture',body='fixture',status='approved',approval_id='ap',created_at=now,updated_at=now)
 event=MessageEvent(message_id='m',event='delivery_reconciled',at=now,details={'provider_message_id':'source-id'})
 repo.save_message(m,MessageEvent(message_id='m',event='approved',at=now))
 assert repo.reconcile_delivery(m,event) is None
 assert repo.claim_delivery(m,MessageEvent(message_id='m',event='delivery_claimed',at=now))
 current=repo.get_message('m')
 assert repo.reconcile_delivery(current.model_copy(update={'version':999}),event) is None
 assert repo.reconcile_delivery(current.model_copy(update={'approval_id':'wrong'}),event) is None
 if kind!='memory':assert SqlCampaignRepository('other',sessions).reconcile_delivery(current,event) is None
 barrier=Barrier(2)
 def reconcile(_):
  worker=factory();candidate=worker.get_message('m');barrier.wait(timeout=5)
  return worker.reconcile_delivery(candidate,event)
 with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(reconcile,[1,2]))
 assert sum(x is not None for x in outcomes)==1
 assert repo.get_message('m').status=='sent'
 assert sum(e.event=='delivery_reconciled' for e in repo.events('m'))==1
 assert not repo.claim_delivery(m,event)
 if kind!='memory':engine.dispose()
