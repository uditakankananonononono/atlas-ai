"""Real SQLite interleavings beyond decide. No production isolation claim."""
from datetime import datetime,timedelta,timezone
from sqlalchemy import create_engine,event,select
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.modules.m16_executive_dashboard.repository import SqlDashboardRepository,ApprovalRow,EventRow
from app.modules.m16_executive_dashboard.schemas import Approval,ApprovalState,Event
NOW=datetime(2026,10,8,12,tzinfo=timezone.utc)
def rig(tmp_path):
 engine=create_engine(f'sqlite:///{tmp_path / "residual.db"}')
 Base.metadata.create_all(engine)
 factory=sessionmaker(bind=engine,expire_on_commit=False)
 return engine,factory,SqlDashboardRepository('t','u',session_factory=factory)
def test_expiry_cannot_overwrite_concurrent_approval(tmp_path):
 engine,factory,repo=rig(tmp_path)
 repo.save_approval(Approval(id='a',module_id=16,action_type='x',title='x',summary='x',risk='low',evidence={},proposed_payload={},created_at=NOW,expires_at=NOW-timedelta(seconds=1)))
 fired=[]
 @event.listens_for(engine,'after_cursor_execute')
 def race(conn,cursor,stmt,params,ctx,many):
  if not fired and stmt.lstrip().upper().startswith('SELECT') and 'm16_approvals' in stmt:
   fired.append(True)
   assert repo.decide('a',ApprovalState.APPROVED,'winner',NOW)
 @event.listens_for(engine,'before_cursor_execute')
 def race_update(conn,cursor,stmt,params,ctx,many):
  if not fired and stmt.lstrip().upper().startswith('UPDATE') and 'm16_approvals' in stmt:
   fired.append(True);assert repo.decide('a',ApprovalState.APPROVED,'winner',NOW)
 expired=repo.expire_approvals_before(NOW)
 with factory() as db:row=db.scalar(select(ApprovalRow).where(ApprovalRow.id=='a'));assert row.state=='approved' and row.review_note=='winner'
 assert expired==[]
def test_same_event_id_race_cannot_insert_twice(tmp_path):
 engine,factory,repo=rig(tmp_path)
 def e():return Event(id='e',sequence=0,topic='task.completed',aggregate_type='task',aggregate_id='a',payload={},occurred_at=NOW)
 fired=[]
 @event.listens_for(engine,'after_cursor_execute')
 def race(conn,cursor,stmt,params,ctx,many):
  if not fired and stmt.lstrip().upper().startswith('SELECT') and 'm16_events.id = ' in stmt:
   fired.append(True);repo.append_event(e())
 repo.append_event(e())
 with factory() as db:assert len(db.scalars(select(EventRow)).all())==1
def test_migration_upgrades_existing_table_and_refuses_duplicates(tmp_path):
 import importlib.util
 from sqlalchemy import text
 from alembic.migration import MigrationContext
 from alembic.operations import Operations
 spec=importlib.util.spec_from_file_location('m16_migration','migrations/versions/20261008_m16_event_identity.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 engine=create_engine(f'sqlite:///{tmp_path / "migration.db"}')
 with engine.begin() as conn:
  conn.execute(text('CREATE TABLE m16_events (tenant_id TEXT, id TEXT, sequence INTEGER)'))
  conn.execute(text("INSERT INTO m16_events VALUES ('t','e',1),('t','e',2)"))
  module.op=Operations(MigrationContext.configure(conn))
  import pytest
  with pytest.raises(RuntimeError,match='owner-reviewed'):module.upgrade()
  assert conn.execute(text('SELECT count(*) FROM m16_events')).scalar()==2
  conn.execute(text('DELETE FROM m16_events WHERE sequence=2'))
  module.upgrade();module.upgrade()
  from sqlalchemy.exc import IntegrityError
  with pytest.raises(IntegrityError):conn.execute(text("INSERT INTO m16_events VALUES ('t','e',2)"))
