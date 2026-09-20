"""Playwright browser agent with HAR audit and mandatory exact-content submit approval."""
from __future__ import annotations
import secrets
from pathlib import Path
from .domain import ActionType,AuditEvent,RunStatus
from .forms import FieldDescriptor,match_fields
from .security import validate_public_url,values_digest
class Service:
    def __init__(self,sessions,approval_service,store,artifact_root="/tmp/atlas-browser",allowed_hosts=None):
        self.sessions=sessions; self.approvals=approval_service; self.store=store; self.root=Path(artifact_root); self.allowed_hosts=allowed_hosts
    async def navigate(self,tenant_id,session_id,url,persistent=False):
        validate_public_url(url,self.allowed_hosts); page=await self.sessions.page(tenant_id,session_id,persistent); await page.goto(url)
        await self.store.append_audit(AuditEvent(tenant_id,session_id,ActionType.NAVIGATE,{"url":url,"persistent":persistent})); return {"status":"ok"}
    async def fill(self,tenant_id,session_id,fields,data):
        page=await self.sessions.page(tenant_id,session_id,False); mapping=match_fields(fields,data)
        for selector,value in mapping.items(): await page.fill(selector,value)
        await self.store.append_audit(AuditEvent(tenant_id,session_id,ActionType.FILL,{"selectors":list(mapping)})); return mapping
    async def screenshot(self,tenant_id,session_id):
        directory=self.root/tenant_id/session_id; directory.mkdir(parents=True,exist_ok=True); path=directory/f"{secrets.token_hex(8)}.png"
        page=await self.sessions.page(tenant_id,session_id,False); await page.screenshot(path=str(path),full_page=True)
        await self.store.append_audit(AuditEvent(tenant_id,session_id,ActionType.SCREENSHOT,{"path":str(path)})); return str(path)
    async def extract(self,tenant_id,session_id):
        page=await self.sessions.page(tenant_id,session_id,False); html=await page.content()
        await self.store.append_audit(AuditEvent(tenant_id,session_id,ActionType.EXTRACT,{"bytes":len(html)})); return html
    async def request_submit(self,tenant_id,actor_id,session_id,selector,values):
        snapshot=await self.screenshot(tenant_id,session_id); digest=values_digest(values)
        view=self.approvals.submit(module_id=13,action_type="browser_submit",user_id=tenant_id,payload={"tenant_id":tenant_id,"session_id":session_id,"selector":selector,"form_values":values,"values_digest":digest,"snapshot_path":snapshot},ttl_seconds=3600)
        return {"status":RunStatus.AWAITING_APPROVAL,"approval_id":view["id"],"snapshot_path":snapshot,"values_digest":digest}
    async def submit(self,tenant_id,session_id,selector,values,approval_id):
        view=self.approvals.get(approval_id); payload=view["payload"]
        status=view["status"].value if hasattr(view["status"],"value") else view["status"]
        expected={"tenant_id":tenant_id,"session_id":session_id,"selector":selector,"values_digest":values_digest(values)}
        if status!="approved" or any(payload.get(k)!=v for k,v in expected.items()): raise PermissionError("approval is missing, stale, denied, or for different content")
        if await self.store.was_consumed(approval_id): raise PermissionError("approval was already consumed")
        await self.store.consume(approval_id,tenant_id)
        page=await self.sessions.page(tenant_id,session_id,False); await page.click(selector)
        await self.store.append_audit(AuditEvent(tenant_id,session_id,ActionType.SUBMIT,{"selector":selector,"approval_id":approval_id,"digest":expected["values_digest"]})); return {"status":"submitted"}
