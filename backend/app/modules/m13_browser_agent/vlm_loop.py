from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Protocol

from .domain import ActionType, AuditEvent

_SUBMIT_WORDS = re.compile(r"\b(submit|pay|payment|buy|purchase|checkout|check out|place order|confirm order|send|apply|donate|delete)\b|type=.?submit")


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
                if action.get("is_submit") or await self._submit_like(tenant_id, session_id, action):
                    result = await self.agent.request_submit(tenant_id, actor_id, session_id, action["selector"], action.get("form_values", {}))
                    return {**result, "history": history}
                await self.agent.click(tenant_id, session_id, action["selector"])
            elif kind == "extract":
                action = {**action, "result": await self.agent.extract(tenant_id, session_id)}
            elif kind == "scroll":
                page = await self.agent.sessions.page(tenant_id, session_id, False)
                amount = max(-5000, min(5000, int(action.get("pixels", 700))))
                await page.mouse.wheel(0, amount)
                await self._audit_scroll(tenant_id, session_id, amount)
            history.append(action)
        return {"status": "max_steps", "history": history}

    async def _submit_like(self, tenant_id: str, session_id: str, action: dict[str, Any]) -> bool:
        """Fail closed: a click that looks like a submit goes through the approval path even if the planner did not say so (ATLAS-m13.A01).

        Checks the planner's own selector/label text and, when the page supports it, the element's real type.
        """
        text = " ".join(str(action.get(key, "")) for key in ("selector", "label", "text", "description")).lower()
        if _SUBMIT_WORDS.search(text):
            return True
        # Anything we cannot positively classify as inert goes to approval.
        try:
            page = await self.agent.sessions.page(tenant_id, session_id, False)
            probe = getattr(page.locator(action["selector"]), "evaluate", None)
            if probe is None:
                return True
            info = await probe(
                "e => ({tag:(e.tagName||'').toLowerCase(), type:(e.type||'').toLowerCase(), inForm:!!(e.form||e.closest('form')),"
                " href:e.getAttribute('href')||'', handler:!!(e.getAttribute('onclick')||e.getAttribute('onsubmit')||e.getAttribute('formaction')||e.getAttribute('data-action')),"
                " text:(e.innerText||e.value||'').toLowerCase()})"
            )
        except Exception:
            return True
        if not isinstance(info, dict):
            return True
        if info.get("type") in {"submit", "image", "button"} or info.get("inForm") or info.get("handler"):
            return True
        if _SUBMIT_WORDS.search(str(info.get("text", ""))):
            return True
        tag, kind = info.get("tag"), info.get("type")
        href = str(info.get("href") or "").strip()
        scheme = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):", re.sub(r"[\x00-\x20]", "", href))
        safe_href = bool(href) and (scheme is None or scheme.group(1).lower() in {"http", "https"})
        inert = (tag == "a" and safe_href) or tag in {"select", "textarea"} or (
            tag == "input" and kind in {"text", "search", "email", "tel", "url", "number", "checkbox", "radio", "password", ""})
        return not inert

    async def _audit_scroll(self, tenant_id: str, session_id: str, amount: int) -> None:
        store = getattr(self.agent, "store", None)
        if store is not None:
            await store.append_audit(AuditEvent(tenant_id, session_id, ActionType.SCROLL, {"pixels": amount}))
