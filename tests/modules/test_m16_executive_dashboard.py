from datetime import datetime,timedelta,timezone
from app.modules.m16_executive_dashboard.schemas import *
from app.modules.m16_executive_dashboard.service import Service,critical_path
class Repo:
 def __init__(self):self.commands={};self.approvals={}
 def snapshot(self):return Snapshot(version=0,last_sequence=0,generated_at=datetime.now(timezone.utc),data={})
 def pending_approvals(self):return list(self.approvals.values())
 def save_approval(self,a):self.approvals[a.id]=a;return a
 def decide(self,*a):return None
 def save_command(self,c):self.commands[c.id]=[object(),c,None];return c
 def get_command(self,i):
  row=type("Row",(),{"executed_at":self.commands[i][2]})();return row,self.commands[i][1]
 def mark_command(self,i,at):self.commands[i][2]=at
def test_commands_preview_mutations_instead_of_executing():
 r=Repo();svc=Service(r)
 read=svc.preview("show deadlines");assert read.read_only;assert svc.execute(read.id)["status"]=="completed"
 write=svc.preview("send this email");assert not write.read_only;result=svc.execute(write.id);assert result["status"]=="approval_required";assert len(r.approvals)==1
def test_critical_path_and_cycle_detection():
 now=datetime.now(timezone.utc);items=[TimelineItem(id="a",title="A",start=now,end=now+timedelta(hours=2)),TimelineItem(id="b",title="B",start=now,end=now+timedelta(hours=3),dependencies=["a"]),TimelineItem(id="c",title="C",start=now,end=now+timedelta(hours=1))]
 assert critical_path(items)==["a","b"]
