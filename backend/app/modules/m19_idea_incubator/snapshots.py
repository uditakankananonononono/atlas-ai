"""Explicit captured current ranking inputs. Checksum only, not an archive."""
import hashlib,json,uuid
from datetime import datetime,timezone
from sqlalchemy import JSON,String,Integer,UniqueConstraint,select
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError
from app.core.database import Base,SessionLocal
from app.auth.context import TenantContext
from .repository import IdeaRow,EvidenceRow,FeasibilityRow,ExperimentRow,_idea,_evidence,_feasibility,_experiment
from .historical_ranking import rank_portfolio_as_of
class SnapshotError(ValueError):pass
class SnapshotCounterRow(Base):
    __tablename__='m19_snapshot_counters'
    tenant_id:Mapped[str]=mapped_column(String(120),primary_key=True)
    revision:Mapped[int]=mapped_column(Integer)
class SnapshotRow(Base):
    __tablename__='m19_ranking_snapshots'
    __table_args__=(UniqueConstraint('tenant_id','revision'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(120),index=True)
    actor_id:Mapped[str]=mapped_column(String(120))
    revision:Mapped[int]=mapped_column(Integer)
    parameters_hash:Mapped[str]=mapped_column(String(64),index=True)
    payload:Mapped[dict]=mapped_column(JSON)
    content_hash:Mapped[str]=mapped_column(String(64))

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def checksum(value):return hashlib.sha256(canonical(value)).hexdigest()
def parameters(as_of,half_life_days=90.0,include_terminal=False,limit=None,stale_experiment_policy='exclude'):
    if not isinstance(as_of,datetime) or as_of.tzinfo is None:raise SnapshotError('timezone-aware as_of required')
    import math
    if type(half_life_days) not in (int,float) or not math.isfinite(half_life_days) or not 0<half_life_days<=3650:raise SnapshotError('finite positive bounded half-life required')
    if type(include_terminal)!=bool or (limit is not None and (type(limit)!=int or not 1<=limit<=500)) or stale_experiment_policy not in ('exclude','current'):raise SnapshotError('invalid snapshot parameters')
    return {'as_of':as_of.astimezone(timezone.utc).isoformat(),'half_life_days':float(half_life_days),'include_terminal':include_terminal,'limit':limit,'stale_experiment_policy':stale_experiment_policy}
def identity(context):
    if not isinstance(context,TenantContext) or not context.tenant_id or not context.actor_id:raise SnapshotError('authenticated owner required')

class SessionRepository:
    def __init__(self,db,tenant):self.db=db;self.tenant=tenant;self.visited={}
    def _rows(self,model,convert,kind,idea=None):
        query=select(model).where(model.tenant_id==self.tenant)
        if idea is not None:query=query.where(model.idea_id==idea)
        rows=[convert(r) for r in self.db.scalars(query)]
        for row in rows:self.visited[(kind,row.id)]=row.model_dump(mode='json')
        return rows
    def list_ideas(self):return self._rows(IdeaRow,_idea,'idea')
    def list_evidence(self,i):return self._rows(EvidenceRow,_evidence,'evidence',i)
    def list_tests(self,i):return self._rows(FeasibilityRow,_feasibility,'test',i)
    def list_experiments(self,i):return self._rows(ExperimentRow,_experiment,'experiment',i)

class SnapshotService:
    def __init__(self,sessions=SessionLocal,*,code_version,max_bytes=4000000,max_records=1000):
        if type(max_bytes)!=int or not 1<=max_bytes<=4000000 or type(max_records)!=int or not 1<=max_records<=1000:raise SnapshotError('limits may only be lowered')
        if not isinstance(code_version,str) or not code_version:raise SnapshotError('code version required')
        self.sessions=sessions;self.code_version=code_version;self.max_bytes=max_bytes;self.max_records=max_records
    def _rank(self,db,ctx,params):
        repo=SessionRepository(db,ctx.tenant_id)
        result=rank_portfolio_as_of(repo,datetime.fromisoformat(params['as_of']),params['half_life_days'],params['include_terminal'],params['limit'],params['stale_experiment_policy'])
        excluded=[{'row':repo.visited[(d.kind,d.row_id)],'reason':d.reason,'timestamp':d.timestamp.isoformat(),'kind':d.kind} for d in result.diagnostics]
        kinds={'ideas':'idea','evidence':'evidence','tests':'test','experiments':'experiment'}
        included={k:[repo.visited[(kind,id)] for id in result.provenance.included[k]] for k,kind in kinds.items()}
        return result.model_dump(mode='json'),included,excluded
    def capture(self,context,**kwargs):
        identity(context);params=parameters(**kwargs)
        for attempt in range(3):
            try:
                with self.sessions() as db:
                    if db.get_bind().dialect.name!='postgresql':raise SnapshotError('REPEATABLE READ PostgreSQL capture required')
                    db.connection(execution_options={'isolation_level':'REPEATABLE READ'})
                    db.execute(insert(SnapshotCounterRow).values(tenant_id=context.tenant_id,revision=0).on_conflict_do_nothing())
                    counter=db.scalar(select(SnapshotCounterRow).where(SnapshotCounterRow.tenant_id==context.tenant_id).with_for_update())
                    if counter.revision>=self.max_records:raise SnapshotError('snapshot capacity reached; no eviction')
                    result,included,excluded=self._rank(db,context,params)
                    revision=counter.revision+1;sid=str(uuid.uuid4())
                    payload={'snapshot_id':sid,'tenant_id':context.tenant_id,'actor_id':context.actor_id,'revision':revision,'captured_at':datetime.now(timezone.utc).isoformat(),'parameters':params,'schema_version':1,'code_version':self.code_version,'consistent_read':True,'census_scope':'visited_rows_only','source_state_caveat':'CURRENT rows read at captured_at; no earlier history reconstructed','reconstruction_claimed':False,'included':included,'excluded':excluded,'result':result}
                    content_hash=checksum(payload)
                    if len(canonical({**payload,'content_hash':content_hash}))>self.max_bytes:raise SnapshotError('snapshot exceeds bytes limit')
                    db.add(SnapshotRow(id=sid,tenant_id=context.tenant_id,actor_id=context.actor_id,revision=revision,parameters_hash=checksum(params),payload=payload,content_hash=content_hash));counter.revision=revision;db.commit()
                    return {**payload,'content_hash':content_hash}
            except OperationalError as exc:
                if getattr(exc.orig,'sqlstate',None)!='40001' or attempt==2:raise SnapshotError('capture transaction conflict; retry explicitly') from exc
        raise SnapshotError('capture not completed')
    def _read(self,row,ctx):
        if row is None or row.tenant_id!=ctx.tenant_id or row.actor_id!=ctx.actor_id:raise SnapshotError('snapshot unavailable')
        if row.payload.get('schema_version')!=1 or row.payload.get('snapshot_id')!=row.id or row.payload.get('tenant_id')!=row.tenant_id or row.payload.get('actor_id')!=row.actor_id or row.payload.get('revision')!=row.revision or checksum(row.payload)!=row.content_hash:raise SnapshotError('unknown snapshot format or checksum mismatch')
        return {**row.payload,'content_hash':row.content_hash}
    def get(self,context,sid):
        identity(context)
        with self.sessions() as db:return self._read(db.get(SnapshotRow,sid),context)
    def find(self,context,**kwargs):
        identity(context);params=parameters(**kwargs)
        with self.sessions() as db:
            row=db.scalar(select(SnapshotRow).where(SnapshotRow.tenant_id==context.tenant_id,SnapshotRow.actor_id==context.actor_id,SnapshotRow.parameters_hash==checksum(params)).order_by(SnapshotRow.revision.desc()).limit(1))
            return {'snapshot_available':False} if row is None else {'snapshot_available':True,'snapshot':self._read(row,context)}
    def live(self,context,**kwargs):
        identity(context);params=parameters(**kwargs)
        with self.sessions() as db:result,_,_=self._rank(db,context,params)
        return {'label':'current_filter','result':result}
    def compare(self,context,sid):
        captured=self.get(context,sid);params={**captured['parameters'],'as_of':datetime.fromisoformat(captured['parameters']['as_of'])}
        with self.sessions() as db:result,included,_=self._rank(db,context,parameters(**params))
        return {'snapshot':captured,'current_filter':result,'diverged':checksum(included)!=checksum(captured['included'])}
