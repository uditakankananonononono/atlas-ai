"""Capture-bound, single-use submit approvals (M13 enhancement).

``request`` stages an M00 approval whose payload names a persisted pre-submit
capture (``capture_sha256``); the capture must exist for this tenant and
session, its destination must be the live page URL, and every value being
submitted must equal what the capture recorded. The owner reviews that capture.

``execute`` clicks only if all of these hold, checked in order:
the approval is approved and names this tenant/session/selector/values/capture;
a fresh read of the live page shows the same URL and the same field values as
the persisted capture; the approval has not been consumed; and no submit attempt
exists yet for this approval or this capture. The approval is consumed and the
attempt recorded before the click, so a failed or ambiguous click never
replays - it needs a new capture and a new approval. The attempt row keeps the
outcome (``clicked`` or ``click_failed``). Nothing here pays or sends by itself;
the gate only narrows the existing submit path.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from .domain import ActionType, AuditEvent
from .security import validate_public_url, values_digest


class SubmitAttemptRow(Base):
    __tablename__ = "m13_capture_submit_attempts"
    __table_args__ = (UniqueConstraint("tenant_id", "approval_id", name="uq_m13_attempt_approval"),
                      UniqueConstraint("tenant_id", "capture_sha256", name="uq_m13_attempt_capture"))
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    approval_id: Mapped[str] = mapped_column(String(200))
    capture_sha256: Mapped[str] = mapped_column(String(64))
    session_id: Mapped[str] = mapped_column(String(300))
    selector: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def _status(view) -> str:
    s = view.get("status")
    return s.value if hasattr(s, "value") else str(s)


async def _capture_for(service, tenant_id: str, session_id: str, capture_sha256: str) -> dict:
    row = await service.store.get_capture(tenant_id, capture_sha256)
    if row is None:
        raise PermissionError("capture is not persisted for this tenant")
    if row.session_id != session_id:
        raise PermissionError("capture belongs to a different browser session")
    return dict(row.artifact)


async def request_capture_bound_submit(service, tenant_id: str, actor_id: str, session_id: str, selector: str,
                                       values: dict[str, str], capture_sha256: str) -> dict:
    artifact = await _capture_for(service, tenant_id, session_id, capture_sha256)
    page = await service.sessions.page(tenant_id, session_id, False)
    page_url = validate_public_url(page.url, service.allowed_hosts)
    if artifact.get("destination") != page_url:
        raise PermissionError("live page URL differs from the captured destination; capture again")
    captured = artifact.get("fields", {})
    diff = sorted(k for k, v in values.items() if captured.get(k) != v)
    if diff:
        raise PermissionError(f"values differ from the capture for {diff}; capture again")
    payload = {"tenant_id": tenant_id, "actor_id": actor_id, "session_id": session_id, "selector": selector,
               "form_values": dict(values), "values_digest": values_digest(values), "page_url": page_url,
               "capture_sha256": capture_sha256, "dom_sha256": artifact.get("dom_sha256"),
               "screenshot_sha256": artifact.get("screenshot_sha256"), "captured_at": artifact.get("captured_at")}
    view = service.approvals.submit(module_id=13, action_type="browser_submit_capture_bound", user_id=tenant_id,
                                    payload=payload, ttl_seconds=3600)
    await service.store.append_audit(AuditEvent(tenant_id, session_id, ActionType.SUBMIT, {
        "phase": "staged_capture_bound", "approval_id": view["id"], "capture_sha256": capture_sha256}))
    return {"status": "awaiting_approval", "approval_id": view["id"], "capture_sha256": capture_sha256, "page_url": page_url}


async def execute_capture_bound_submit(service, sessions_factory, tenant_id: str, session_id: str, selector: str,
                                       values: dict[str, str], approval_id: str, capture_sha256: str) -> dict:
    view = service.approvals.get(approval_id)
    p = view.get("payload", {}) if view else {}
    expected = {"tenant_id": tenant_id, "session_id": session_id, "selector": selector, "form_values": values,
                "values_digest": values_digest(values), "capture_sha256": capture_sha256}
    if not view or _status(view) != "approved" or any(p.get(k) != v for k, v in expected.items()):
        raise PermissionError("approval is missing, not approved, or for a different capture or content")
    artifact = await _capture_for(service, tenant_id, session_id, capture_sha256)
    page = await service.sessions.page(tenant_id, session_id, False)
    page_url = validate_public_url(page.url, service.allowed_hosts)
    if page_url != artifact.get("destination") or page_url != p.get("page_url"):
        raise PermissionError("live page URL no longer matches the approved capture")
    captured = artifact.get("fields", {})
    live = await service.read_values(tenant_id, session_id, sorted(captured))
    changed = sorted(k for k in captured if live.get(k) != captured[k])
    if changed:
        raise PermissionError(f"live field values changed since the approved capture: {changed}")
    if await service.store.was_consumed(approval_id):
        raise PermissionError("approval was already consumed")
    now = datetime.now(timezone.utc)
    try:
        with sessions_factory.begin() as db:
            db.add(SubmitAttemptRow(tenant_id=tenant_id, approval_id=approval_id, capture_sha256=capture_sha256,
                                    session_id=session_id, selector=selector, state="clicking", started_at=now))
            db.flush()
    except IntegrityError as exc:
        raise PermissionError("a submit attempt already exists for this approval or capture") from exc
    await service.store.consume(approval_id, tenant_id)
    state, error = "clicked", None
    try:
        await page.locator(selector).click()
    except Exception as exc:  # noqa: BLE001 - record, never retry
        state, error = "click_failed", str(exc)[:1000]
    with sessions_factory.begin() as db:
        row = db.scalar(select(SubmitAttemptRow).where(SubmitAttemptRow.tenant_id == tenant_id,
                                                       SubmitAttemptRow.approval_id == approval_id))
        row.state, row.error, row.finished_at = state, error, datetime.now(timezone.utc)
    await service.store.append_audit(AuditEvent(tenant_id, session_id, ActionType.SUBMIT, {
        "phase": "executed_capture_bound", "approval_id": approval_id, "capture_sha256": capture_sha256, "state": state}))
    if state != "clicked":
        raise RuntimeError(f"click failed after the approval was consumed; capture and approve again ({error})")
    return {"status": "submitted", "approval_id": approval_id, "capture_sha256": capture_sha256}
