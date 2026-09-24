"""Deliverable obligation tracker (M07 enhancement).

Every promise in a brand contract becomes an obligation row linked to:

- the contract clause it came from (text + locator, e.g. "Section 3.2");
- its deadline and quantity (e.g. 2 Reels by 30 Oct);
- delivery evidence (live post URLs, screenshots by hash, reports);
- the Module 0 approvals gating its outward actions (brand review, sends);
- the invoice artifact that bills it and owner-recorded payment.

Status is derived, never typed in, so it cannot drift from the evidence:
``open`` -> ``due_soon`` -> ``overdue``, or ``delivered`` once evidence
covers the quantity and every linked approval is approved; ``waived`` only
by an explicit owner event. Billing is derived the same way:
``not_invoiced`` / ``invoiced`` / ``paid`` / ``payment_overdue``. Flags
catch the usual money leaks: delivered but never invoiced, invoiced before
delivery, payment late, and exclusivity windows still in force.

Nothing here sends, posts or charges; it only records and derives. Payment
is an owner-recorded fact, not a bank read. Every row is tenant-scoped and
every change is an append-only event.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Literal
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.core.database import Base, SessionLocal, engine

ObligationKind = Literal["deliverable", "usage_rights", "exclusivity", "disclosure", "report", "other"]
DUE_SOON = timedelta(days=3)


class ObligationRow(Base):
    __tablename__ = "m07_obligations"
    pk: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    id: Mapped[str] = mapped_column(String(36), index=True)
    brand_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(Text)
    clause_text: Mapped[str] = mapped_column(Text)
    clause_locator: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    amount_minor: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ObligationEventRow(Base):
    __tablename__ = "m07_obligation_events"
    pk: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    id: Mapped[str] = mapped_column(String(36))
    obligation_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data: Mapped[dict] = mapped_column(JSON)


class ObligationNotFound(LookupError):
    pass


class ObligationError(ValueError):
    pass


def _aware(v: datetime | None) -> datetime | None:
    if v is None:
        return None
    return v if v.tzinfo else v.replace(tzinfo=timezone.utc)


class ObligationTracker:
    def __init__(self, tenant_id: str, *, brands: Any, artifacts: Any, approvals: Any,
                 session_factory: sessionmaker = SessionLocal, clock: Callable[[], datetime] | None = None):
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        self.tenant_id = tenant_id.strip()
        self.brands, self.artifacts, self.approvals = brands, artifacts, approvals
        self.sessions = session_factory
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        Base.metadata.create_all(engine)

    # -- writes (append-only events) ------------------------------------
    def create(self, *, brand_id: str, kind: str, title: str, clause_text: str, clause_locator: str,
               quantity: int = 1, due_at: datetime | None = None, ends_at: datetime | None = None,
               amount_minor: int = 0, currency: str = "USD") -> dict[str, Any]:
        if not self.brands(brand_id):
            raise ObligationNotFound(f"brand {brand_id}")
        if not clause_text.strip():
            raise ObligationError("an obligation must quote the contract clause it comes from")
        if quantity < 1:
            raise ObligationError("quantity must be at least 1")
        now = self.clock()
        oid = str(uuid4())
        with self.sessions.begin() as db:
            db.add(ObligationRow(tenant_id=self.tenant_id, id=oid, brand_id=brand_id, kind=kind, title=title,
                                 clause_text=clause_text.strip(), clause_locator=clause_locator, quantity=quantity,
                                 due_at=_aware(due_at), ends_at=_aware(ends_at), amount_minor=amount_minor,
                                 currency=currency, created_at=now))
            db.add(self._ev(oid, "created", {"clause_locator": clause_locator}, now))
        return self.get(oid)

    def add_evidence(self, obligation_id: str, *, url: str | None = None, sha256: str | None = None,
                     note: str = "") -> dict[str, Any]:
        if not (url or sha256):
            raise ObligationError("evidence needs a URL or a content hash")
        return self._append(obligation_id, "evidence_added", {"url": url, "sha256": sha256, "note": note})

    def link_approval(self, obligation_id: str, approval_id: str) -> dict[str, Any]:
        if self.approvals.get(approval_id, user_id=self.tenant_id) is None:
            raise ObligationNotFound(f"approval {approval_id}")
        return self._append(obligation_id, "approval_linked", {"approval_id": approval_id})

    def link_invoice(self, obligation_id: str, artifact_id: str, *, payment_due_at: datetime) -> dict[str, Any]:
        art = self.artifacts(artifact_id)
        if art is None or getattr(art, "kind", None) != "invoice":
            raise ObligationNotFound(f"invoice artifact {artifact_id}")
        ob = self._row(obligation_id)
        if art.brand_id != ob.brand_id:
            raise ObligationError("invoice belongs to a different brand")
        return self._append(obligation_id, "invoice_linked",
                            {"artifact_id": artifact_id, "sha256": art.sha256,
                             "payment_due_at": _aware(payment_due_at).isoformat()})

    def record_payment(self, obligation_id: str, *, amount_minor: int, note: str = "") -> dict[str, Any]:
        """Owner-recorded payment received (not a bank read)."""
        if amount_minor <= 0:
            raise ObligationError("payment amount must be positive")
        return self._append(obligation_id, "payment_recorded", {"amount_minor": amount_minor, "note": note})

    def waive(self, obligation_id: str, *, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise ObligationError("waiving needs a reason (e.g. the brand's written release)")
        return self._append(obligation_id, "waived", {"reason": reason.strip()})

    # -- reads ----------------------------------------------------------
    def get(self, obligation_id: str) -> dict[str, Any]:
        row = self._row(obligation_id)
        return self._derive(row, self._events(obligation_id))

    def brand_tracker(self, brand_id: str) -> dict[str, Any]:
        with self.sessions() as db:
            rows = list(db.scalars(select(ObligationRow).where(ObligationRow.tenant_id == self.tenant_id,
                                                               ObligationRow.brand_id == brand_id)
                                   .order_by(ObligationRow.due_at, ObligationRow.created_at)))
        items = [self._derive(r, self._events(r.id)) for r in rows]
        open_items = [i for i in items if i["status"] in {"open", "due_soon", "overdue"}]
        deadlines = sorted(i["due_at"] for i in open_items if i["due_at"])
        billed = [i for i in items if i["billing"] in {"invoiced", "payment_overdue"}]
        return {
            "brand_id": brand_id,
            "obligations": items,
            "summary": {
                "total": len(items),
                "open": len(open_items),
                "overdue": sum(i["status"] == "overdue" for i in items),
                "next_deadline": deadlines[0] if deadlines else None,
                "outstanding_minor": sum(i["amount_minor"] - i["paid_minor"] for i in billed),
                "unbilled_delivered_minor": sum(i["amount_minor"] for i in items
                                                if "delivered_not_invoiced" in i["flags"]),
                "flags": sorted({f for i in items for f in i["flags"]}),
            },
        }

    def attention(self) -> dict[str, Any]:
        """Items needing the owner across every brand: due soon, overdue, money leaks.
        Read-only digest meant for the owner's daily brief."""
        with self.sessions() as db:
            rows = list(db.scalars(select(ObligationRow).where(ObligationRow.tenant_id == self.tenant_id)))
        wanted = {"deliverable_overdue", "payment_overdue", "delivered_not_invoiced", "approval_blocked",
                  "invoiced_before_delivery"}
        items = []
        for r in rows:
            d = self._derive(r, self._events(r.id))
            reasons = sorted(set(d["flags"]) & wanted) + (["due_soon"] if d["status"] == "due_soon" else [])
            if reasons:
                items.append({"id": d["id"], "brand_id": d["brand_id"], "title": d["title"], "status": d["status"],
                              "billing": d["billing"], "due_at": d["due_at"], "reasons": reasons,
                              "clause_locator": d["clause"]["locator"]})
        items.sort(key=lambda i: (0 if "deliverable_overdue" in i["reasons"] or "payment_overdue" in i["reasons"] else 1,
                                  i["due_at"] or "9999"))
        return {"as_of": self.clock().isoformat(), "count": len(items), "items": items}

    # -- internals ------------------------------------------------------
    def _ev(self, oid: str, kind: str, data: dict[str, Any], at: datetime) -> ObligationEventRow:
        return ObligationEventRow(tenant_id=self.tenant_id, id=str(uuid4()), obligation_id=oid, kind=kind, at=at, data=data)

    def _append(self, obligation_id: str, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        self._row(obligation_id)
        with self.sessions.begin() as db:
            db.add(self._ev(obligation_id, kind, data, self.clock()))
        return self.get(obligation_id)

    def _row(self, obligation_id: str) -> ObligationRow:
        with self.sessions() as db:
            row = db.scalar(select(ObligationRow).where(ObligationRow.tenant_id == self.tenant_id,
                                                        ObligationRow.id == obligation_id))
        if row is None:
            raise ObligationNotFound(obligation_id)
        return row

    def _events(self, obligation_id: str) -> list[ObligationEventRow]:
        with self.sessions() as db:
            return list(db.scalars(select(ObligationEventRow).where(
                ObligationEventRow.tenant_id == self.tenant_id,
                ObligationEventRow.obligation_id == obligation_id).order_by(ObligationEventRow.at, ObligationEventRow.pk)))

    def _derive(self, row: ObligationRow, events: list[ObligationEventRow]) -> dict[str, Any]:
        now = self.clock()
        evidence = [e.data | {"at": _aware(e.at).isoformat()} for e in events if e.kind == "evidence_added"]
        approval_ids = list(dict.fromkeys(e.data["approval_id"] for e in events if e.kind == "approval_linked"))
        approvals = []
        for aid in approval_ids:
            a = self.approvals.get(aid, user_id=self.tenant_id)
            approvals.append({"approval_id": aid, "status": getattr(getattr(a, "status", None), "value",
                                                                    getattr(a, "status", "missing")) if a else "missing"})
        invoices = [e for e in events if e.kind == "invoice_linked"]
        paid = sum(int(e.data["amount_minor"]) for e in events if e.kind == "payment_recorded")
        waived = next((e.data["reason"] for e in events if e.kind == "waived"), None)
        due, ends = _aware(row.due_at), _aware(row.ends_at)

        approvals_ok = all(a["status"] == "approved" for a in approvals)
        needs_evidence = row.kind in {"deliverable", "disclosure", "report"}
        covered = len(evidence) >= row.quantity if needs_evidence else True
        if waived:
            status = "waived"
        elif covered and approvals_ok and (needs_evidence or evidence or approvals or (ends and ends <= now)):
            status = "delivered"
        elif due and due < now:
            status = "overdue"
        elif due and due - now <= DUE_SOON:
            status = "due_soon"
        else:
            status = "open"

        pay_due = max((datetime.fromisoformat(e.data["payment_due_at"]) for e in invoices), default=None)
        if row.amount_minor and paid >= row.amount_minor:
            billing = "paid"
        elif invoices and pay_due and pay_due < now:
            billing = "payment_overdue"
        elif invoices:
            billing = "invoiced"
        else:
            billing = "not_invoiced"

        flags: list[str] = []
        if status == "delivered" and billing == "not_invoiced" and row.amount_minor:
            flags.append("delivered_not_invoiced")
        if invoices and status in {"open", "due_soon", "overdue"}:
            flags.append("invoiced_before_delivery")
        if billing == "payment_overdue":
            flags.append("payment_overdue")
        if status == "overdue":
            flags.append("deliverable_overdue")
        if any(a["status"] in {"denied", "missing"} for a in approvals):
            flags.append("approval_blocked")
        if row.kind == "exclusivity" and ends and ends > now:
            flags.append("exclusivity_active")
        if covered and needs_evidence and not approvals_ok and not waived:
            flags.append("evidence_awaiting_approval")

        return {
            "id": row.id, "brand_id": row.brand_id, "kind": row.kind, "title": row.title,
            "clause": {"text": row.clause_text, "locator": row.clause_locator},
            "quantity": row.quantity, "due_at": due.isoformat() if due else None,
            "ends_at": ends.isoformat() if ends else None,
            "amount_minor": row.amount_minor, "currency": row.currency, "paid_minor": paid,
            "status": status, "billing": billing, "flags": flags,
            "evidence": evidence, "approvals": approvals,
            "invoices": [e.data for e in invoices], "waived_reason": waived,
            "events": [{"kind": e.kind, "at": _aware(e.at).isoformat()} for e in events],
        }
