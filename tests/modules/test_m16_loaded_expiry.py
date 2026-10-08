"""SQLAlchemy result barrier AFTER SQLite cursor exhausted, no synthetic DB writes."""
from datetime import datetime,timedelta,timezone
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker,Session
from app.core.database import Base
from app.modules.m16_executive_dashboard.repository import SqlDashboardRepository,ApprovalRow
from app.modules.m16_executive_dashboard.schemas import Approval,ApprovalState
NOW=datetime(2026,10,8,12,tzinfo=timezone.utc)
def test_expiry_loaded_result_preserves_competing_commit(tmp_path):
 engine=create_engine(f'sqlite:///{tmp_path / "expiry.db"}')
 Base.metadata.create_all(engine);plain=sessionmaker(bind=engine,expire_on_commit=False)
 winner=SqlDashboardRepository('t','winner',session_factory=plain)
 winner.save_approval(Approval(id='a',module_id=16,action_type='x',title='x',summary='x',risk='low',evidence={},proposed_payload={},created_at=NOW,expires_at=NOW-timedelta(seconds=1)))
 fired=[]
 class BarrierSession(Session):
  def scalars(self,statement,*args,**kwargs):
   if statement.is_select and not fired:
    # Fully exhaust result to release SQLite cursor before competing commit.
    loaded=super().scalars(statement,*args,**kwargs).all();fired.append(True)
    accepted=winner.decide('a',ApprovalState.APPROVED,'committed winner',NOW)
    assert accepted.state==ApprovalState.APPROVED
    class LoadedResult:
     def all(self):return loaded
    return LoadedResult()
   if statement.is_update and not fired:
    fired.append(True);assert winner.decide('a',ApprovalState.APPROVED,'committed winner',NOW)
   return super().scalars(statement,*args,**kwargs)
 sweeper=SqlDashboardRepository('t','sweeper',session_factory=sessionmaker(bind=engine,class_=BarrierSession,expire_on_commit=False))
 expired=sweeper.expire_approvals_before(NOW)
 with plain() as db:
  r=db.scalar(select(ApprovalRow).where(ApprovalRow.id=='a'))
  assert r.state=='approved',f'actual stored state {r.state}; review note {r.review_note}'
 assert expired==[] and fired==[True]
