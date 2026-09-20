from __future__ import annotations
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from .schemas import *
class Service:
    def __init__(self,repository,parser=None,executor=None):self.repository=repository;self.parser=parser or self._parse;self.executor=executor or (lambda intent,params:{"items":[],"intent":intent,"parameters":params})
    def snapshot(self):return self.repository.snapshot()
    def events_after(self,cursor):return self.repository.events_after(cursor)
    def pending_approvals(self):
        now=datetime.now(timezone.utc);return [a for a in self.repository.pending_approvals() if not a.expires_at or a.expires_at>now]
    def decide(self,aid,data):
        pending=next((a for a in self.repository.pending_approvals() if a.id==aid),None)
        if not pending:raise LookupError(aid)
        if pending.expires_at and pending.expires_at<datetime.now(timezone.utc):raise RuntimeError("approval expired")
        return self.repository.decide(aid,ApprovalState.APPROVED if data.approve else ApprovalState.REJECTED,data.note,datetime.now(timezone.utc))
    def preview(self,utterance):
        parsed=self.parser(utterance);now=datetime.now(timezone.utc);return self.repository.save_command(CommandPreview(id=str(uuid4()),utterance=utterance,expires_at=now+timedelta(minutes=10),created_at=now,**parsed))
    def execute(self,cid):
        row,p=self.repository.get_command(cid)
        if not p:raise LookupError(cid)
        now=datetime.now(timezone.utc)
        if row.executed_at:raise RuntimeError("command already executed")
        if p.expires_at<now:raise RuntimeError("command preview expired")
        if not p.read_only:
            a=Approval(id=str(uuid4()),module_id=16,action_type=p.intent,title=f"Command: {p.intent}",summary=p.utterance,risk="medium",evidence={"command_preview_id":p.id,"plan":p.plan},proposed_payload=p.parameters,created_at=now,expires_at=now+timedelta(hours=24));self.repository.save_approval(a);return {"status":"approval_required","approval_id":a.id}
        result=self.executor(p.intent,p.parameters);self.repository.mark_command(cid,now);return {"status":"completed","result":result}
    @staticmethod
    def _parse(text):
        lowered=text.casefold();mutations=("send ","email ","schedule ","create ","update ","delete ","approve ","publish ","submit ")
        read_only=not any(x in lowered for x in mutations)
        return {"intent":"search_dashboard" if read_only else "proposed_action","parameters":{"query":text},"plan":[{"action":"search" if read_only else "prepare_for_approval","input":text}],"read_only":read_only,"confidence":.55}
def critical_path(items:list[TimelineItem])->list[str]:
    by={i.id:i for i in items};memo={};visiting=set()
    def walk(i):
        if i in memo:return memo[i]
        if i in visiting:raise ValueError("timeline dependency cycle")
        visiting.add(i);best=(0,[])
        for d in by[i].dependencies:
            if d in by and walk(d)[0]>best[0]:best=walk(d)
        visiting.remove(i);duration=max(0,(by[i].end-by[i].start).total_seconds());memo[i]=(best[0]+duration,best[1]+[i]);return memo[i]
    return max((walk(i) for i in by),default=(0,[]),key=lambda x:x[0])[1]
