from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Protocol
class VisionPlanner(Protocol):
    async def next_action(self,instruction:str,screenshot_path:str,history:list[dict[str,Any]])->dict[str,Any]: ...
@dataclass(frozen=True)
class LoopPolicy: max_steps:int=20; allowed_actions:frozenset[str]=frozenset({"click","extract","scroll","done"})
class NavigationLoop:
    def __init__(self,agent,planner:VisionPlanner,policy:LoopPolicy=LoopPolicy()): self.agent=agent; self.planner=planner; self.policy=policy
    async def run(self,tenant_id:str,session_id:str,instruction:str):
        history=[]
        for _ in range(self.policy.max_steps):
            shot=await self.agent.screenshot(tenant_id,session_id); action=await self.planner.next_action(instruction,shot,history)
            kind=action.get("type")
            if kind not in self.policy.allowed_actions: raise ValueError("planner proposed forbidden action")
            if kind=="done": return {"status":"complete","history":history,"result":action.get("result")}
            if kind=="click":
                if action.get("is_submit"): return await self.agent.request_submit(tenant_id,session_id,action["selector"],action.get("form_values",{}))
                page=await self.agent.sessions.page(tenant_id,session_id,False); await page.click(action["selector"])
            history.append(action)
        return {"status":"max_steps","history":history}
