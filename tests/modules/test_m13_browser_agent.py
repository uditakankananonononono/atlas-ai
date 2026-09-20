import pytest
from datetime import datetime,timezone
from app.core.models import ApprovalStatus
from app.modules.m13_browser_agent.forms import FieldDescriptor,match_fields
from app.modules.m13_browser_agent.service import Service
class Page:
 def __init__(self):self.clicked=[]
 async def screenshot(self,**kw):open(kw["path"],"wb").write(b"png")
 async def click(self,s):self.clicked.append(s)
 async def fill(self,s,v):pass
 async def content(self):return "<html/>"
class Sessions:
 def __init__(self):self.p=Page()
 async def page(self,*args):return self.p
class Store:
 def __init__(self):self.used=set();self.events=[]
 async def append_audit(self,e):self.events.append(e)
 async def was_consumed(self,x):return x in self.used
 async def consume(self,x,t):self.used.add(x)
class Approvals:
 def __init__(self):self.rows={}
 def submit(self,**kw):self.rows["a"]={"id":"a","payload":kw["payload"],"status":ApprovalStatus.PENDING};return self.rows["a"]
 def get(self,x):return self.rows[x]
def test_field_matching():assert match_fields([FieldDescriptor("#e",label="Email address",input_type="email")],{"email":"a@b.com"})=={"#e":"a@b.com"}
@pytest.mark.asyncio
async def test_exact_single_use_approval(tmp_path):
 a=Approvals();s=Sessions();store=Store();svc=Service(s,a,store,str(tmp_path));req=await svc.request_submit("t","u","r","#go",{"name":"Ada"})
 with pytest.raises(PermissionError):await svc.submit("t","r","#go",{"name":"Ada"},req["approval_id"])
 a.rows["a"]["status"]=ApprovalStatus.APPROVED
 with pytest.raises(PermissionError):await svc.submit("t","r","#go",{"name":"Changed"},"a")
 await svc.submit("t","r","#go",{"name":"Ada"},"a");assert s.p.clicked==["#go"]
 with pytest.raises(PermissionError):await svc.submit("t","r","#go",{"name":"Ada"},"a")
