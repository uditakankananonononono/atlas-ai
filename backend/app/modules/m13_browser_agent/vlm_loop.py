from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class VisionPlanner(Protocol):
    async def next_action(self, instruction: str, screenshot_path: str, history: list[dict[str, Any]]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class LoopPolicy:
    max_steps: int = 20
    allowed_actions: frozenset[str] = frozenset({"click", "extract", "scroll", "done"})


class NavigationLoop:
    def __init__(self, agent: Any, planner: VisionPlanner, policy: LoopPolicy = LoopPolicy()):
        self.agent = agent
        self.planner = planner
        self.policy = policy

    async def run(self, tenant_id: str, session_id: str, instruction: str, actor_id: str = "browser-agent") -> dict[str, Any]:
        history: list[dict[str, Any]] = []
        for _ in range(self.policy.max_steps):
            shot = await self.agent.screenshot(tenant_id, session_id)
            action = await self.planner.next_action(instruction, shot, list(history))
            kind = action.get("type")
            if kind not in self.policy.allowed_actions:
                raise ValueError("planner proposed forbidden action")
            if kind == "done":
                return {"status": "complete", "history": history, "result": action.get("result")}
            if kind == "click":
                if action.get("is_submit"):
                    result = await self.agent.request_submit(tenant_id, actor_id, session_id, action["selector"], action.get("form_values", {}))
                    return {**result, "history": history}
                await self.agent.click(tenant_id, session_id, action["selector"])
            elif kind == "extract":
                action = {**action, "result": await self.agent.extract(tenant_id, session_id)}
            elif kind == "scroll":
                page = await self.agent.sessions.page(tenant_id, session_id, False)
                amount = max(-5000, min(5000, int(action.get("pixels", 700))))
                await page.mouse.wheel(0, amount)
            history.append(action)
        return {"status": "max_steps", "history": history}
