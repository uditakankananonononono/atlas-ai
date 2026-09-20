import pytest
from app.core.approvals import ApprovalStore
from app.modules.m22_tools_hub.service import Service
class Collector:
 name="official-registry"
 async def collect(self,q):
  for x in [{"name":"SafeTool","url":"https://example.org/tool","security":.9,"fit":.8,"maintenance":.9,"novelty":.7,"evidence":[{"url":"https://example.org"}]},{"name":"Bad","url":"https://bad.test","summary":"rotating proxy stealth scraping","security":1,"fit":1}]:yield x
@pytest.mark.asyncio
async def test_discovery_filters_and_install_is_approval_gated():
 s=Service(ApprovalStore(),[Collector()]);items=await s.discover("new research tools")
 assert [x.name for x in items]==["SafeTool"]
 p=s.propose_install(items[0].id,"api",{"token_secret":"hidden","region":"us"},["read"])
 assert p.approval_id and not s.installed
 req=s.approvals.list()[0];assert "token_secret" not in req.payload["config_preview"]
