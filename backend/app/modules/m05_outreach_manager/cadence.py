"""Relationship-aware contact cadence across campaigns (M05 enhancement).

Campaigns are independent, but the person on the other end is not. Before a
message goes to review, the guard looks at every campaign's messages to the
same person (matched by normalised email, so duplicate contact records in
different projects still count as one human) and refuses when outreach would
be duplicate or socially excessive:

- ``opted_out`` / ``do_not_contact`` on the contact: never.
- a bounce to that address: fix the address first.
- a live conversation (they replied inside ``live_thread_days``): a new cold
  message from another campaign is refused; answer in that thread instead.
- duplicate: another campaign already has a message in review/approved for
  the same person.
- minimum gap since the last send to that person, and a rolling 30-day cap,
  both set by relationship (``metadata.relationship`` = cold | warm | close;
  unknown means cold, the strictest).

Pure computation over stored state: nothing is sent, nothing is changed.
The decision is attached to the approval payload so the reviewer sees it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

IN_FLIGHT = {"pending_approval", "approved"}
DELIVERED = {"sent", "replied"}


@dataclass(frozen=True)
class CadenceRule:
    min_gap_days: int
    max_per_30_days: int


RULES: dict[str, CadenceRule] = {
    "cold": CadenceRule(min_gap_days=7, max_per_30_days=2),
    "warm": CadenceRule(min_gap_days=3, max_per_30_days=4),
    "close": CadenceRule(min_gap_days=1, max_per_30_days=8),
}
LIVE_THREAD_DAYS = 21


def _aware(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def person_key(contact: Any) -> str:
    email = (getattr(contact, "email", None) or "").strip().lower()
    return f"email:{email}" if email else f"contact:{contact.id}"


def relationship(contact: Any) -> str:
    value = str((getattr(contact, "metadata", None) or {}).get("relationship", "cold")).strip().lower()
    return value if value in RULES else "cold"


def evaluate(*, contact: Any, message: Any, messages: list[Any], contacts: Any, now: datetime,
             live_thread_days: int = LIVE_THREAD_DAYS, campaign_follow_up_days: int | None = None,
             rules: dict[str, CadenceRule] | None = None) -> dict[str, Any]:
    """Decide whether ``message`` to ``contact`` may go to review.

    ``messages`` is every message this tenant has (all campaigns); ``contacts``
    resolves contact ids so other records with the same email count too.
    A follow-up whose previous send was in its own campaign uses that
    campaign's owner-set follow-up window as the gap; every other pairing uses
    the relationship gap. The 30-day cap always applies across campaigns."""
    meta = getattr(contact, "metadata", None) or {}
    key = person_key(contact)
    rules = rules or RULES
    rel = relationship(contact)
    rule = rules[rel]
    cache: dict[str, Any] = {contact.id: contact}

    def same_person(item: Any) -> bool:
        if item.contact_id not in cache:
            cache[item.contact_id] = contacts.get(item.contact_id)
        other = cache[item.contact_id]
        return other is not None and person_key(other) == key

    history = [m for m in messages if m.id != message.id and same_person(m)]
    reasons: list[dict[str, Any]] = []

    if meta.get("opted_out") or meta.get("do_not_contact"):
        reasons.append({"code": "opted_out", "detail": "contact asked not to be contacted"})
    bounced = [m for m in history if m.status == "bounced"]
    if bounced:
        reasons.append({"code": "bounced", "detail": "an earlier message to this address bounced",
                        "message_ids": [m.id for m in bounced]})

    replies = [m for m in history if m.status == "replied"
               and (_aware(m.updated_at) or now) >= now - timedelta(days=live_thread_days)]
    other_campaign_replies = [m for m in replies if m.campaign_id != message.campaign_id]
    if other_campaign_replies:
        reasons.append({"code": "live_conversation",
                        "detail": "they replied recently in another campaign; continue that thread instead",
                        "message_ids": [m.id for m in other_campaign_replies]})

    in_flight = [m for m in history if m.status in IN_FLIGHT and m.campaign_id != message.campaign_id]
    if in_flight:
        reasons.append({"code": "duplicate",
                        "detail": "another campaign already has a message in review or approved for this person",
                        "message_ids": [m.id for m in in_flight]})

    sent_msgs = sorted((m for m in history if m.status in DELIVERED | {"bounced"} and m.sent_at),
                       key=lambda m: _aware(m.sent_at), reverse=True)
    sends = [_aware(m.sent_at) for m in sent_msgs]
    last = sends[0] if sends else None
    gap = rule.min_gap_days
    if (sent_msgs and message.kind == "follow_up" and campaign_follow_up_days is not None
            and sent_msgs[0].campaign_id == message.campaign_id):
        gap = campaign_follow_up_days
    next_allowed = None
    if last and last + timedelta(days=gap) > now:
        next_allowed = last + timedelta(days=gap)
        reasons.append({"code": "too_soon",
                        "detail": f"{rel} contact: at least {gap} day(s) between messages",
                        "last_sent_at": last.isoformat(), "next_allowed_at": next_allowed.isoformat()})
    window = [s for s in sends if s >= now - timedelta(days=30)]
    pending_same = [m for m in history if m.status in IN_FLIGHT and m.campaign_id == message.campaign_id]
    if len(window) + len(pending_same) + 1 > rule.max_per_30_days:
        oldest = min(window) if window else now
        cap_clear = oldest + timedelta(days=30)
        next_allowed = max(next_allowed or cap_clear, cap_clear)
        reasons.append({"code": "over_cap",
                        "detail": f"{rel} contact: at most {rule.max_per_30_days} message(s) per 30 days",
                        "sent_last_30_days": len(window), "in_review": len(pending_same),
                        "next_allowed_at": cap_clear.isoformat()})

    hard = {"opted_out", "bounced"}
    return {
        "allowed": not reasons,
        "person": key,
        "relationship": rel,
        "rule": {"min_gap_days": rule.min_gap_days, "max_per_30_days": rule.max_per_30_days},
        "reasons": reasons,
        "next_allowed_at": None if any(r["code"] in hard | {"live_conversation", "duplicate"} for r in reasons)
        else (next_allowed.isoformat() if next_allowed else None),
        "sent_last_30_days": len(window),
        "evaluated_at": now.isoformat(),
    }


# -- owner-editable per-tenant policy ------------------------------------------------
from sqlalchemy import JSON, DateTime, Integer, String, select  # noqa: E402
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402

BOUNDS = {"min_gap_days": (0, 90), "max_per_30_days": (1, 60), "live_thread_days": (0, 180)}


class CadencePolicyRow(Base):
    """Append-only: the latest version per tenant is the policy in force."""
    __tablename__ = "m05_cadence_policies"
    pk: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    version: Mapped[int] = mapped_column(Integer)
    rules: Mapped[dict] = mapped_column(JSON)
    live_thread_days: Mapped[int] = mapped_column(Integer)
    actor: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(String(2000))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CadencePolicyError(ValueError):
    pass


def default_policy() -> dict[str, Any]:
    return {"version": 0, "source": "default", "live_thread_days": LIVE_THREAD_DAYS,
            "rules": {k: {"min_gap_days": r.min_gap_days, "max_per_30_days": r.max_per_30_days} for k, r in RULES.items()}}


class CadencePolicyStore:
    def __init__(self, tenant_id: str, session_factory: sessionmaker = SessionLocal,
                 clock=lambda: datetime.now(timezone.utc)):
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        self.tenant_id, self.sessions, self.clock = tenant_id.strip(), session_factory, clock
        Base.metadata.create_all(engine)

    def current(self) -> dict[str, Any]:
        with self.sessions() as db:
            row = db.scalar(select(CadencePolicyRow).where(CadencePolicyRow.tenant_id == self.tenant_id)
                            .order_by(CadencePolicyRow.version.desc()).limit(1))
        if row is None:
            return default_policy()
        return {"version": row.version, "source": "owner", "rules": row.rules, "live_thread_days": row.live_thread_days,
                "actor": row.actor, "reason": row.reason, "at": row.at.isoformat()}

    def history(self) -> list[dict[str, Any]]:
        with self.sessions() as db:
            rows = list(db.scalars(select(CadencePolicyRow).where(CadencePolicyRow.tenant_id == self.tenant_id)
                                   .order_by(CadencePolicyRow.version)))
        return [{"version": r.version, "rules": r.rules, "live_thread_days": r.live_thread_days, "actor": r.actor,
                 "reason": r.reason, "at": r.at.isoformat()} for r in rows]

    def set(self, *, rules: dict[str, dict[str, int]], live_thread_days: int, actor: str, reason: str) -> dict[str, Any]:
        if set(rules) != set(RULES):
            raise CadencePolicyError(f"rules must cover exactly {sorted(RULES)}")
        clean = {}
        for rel, r in rules.items():
            clean[rel] = {}
            for key in ("min_gap_days", "max_per_30_days"):
                lo, hi = BOUNDS[key]
                v = int(r.get(key, -1))
                if not lo <= v <= hi:
                    raise CadencePolicyError(f"{rel}.{key} must be between {lo} and {hi}")
                clean[rel][key] = v
        lo, hi = BOUNDS["live_thread_days"]
        if not lo <= int(live_thread_days) <= hi:
            raise CadencePolicyError(f"live_thread_days must be between {lo} and {hi}")
        if not reason.strip():
            raise CadencePolicyError("a policy change needs a reason")
        version = self.current()["version"] + 1
        with self.sessions.begin() as db:
            db.add(CadencePolicyRow(tenant_id=self.tenant_id, version=version, rules=clean,
                                    live_thread_days=int(live_thread_days), actor=actor, reason=reason.strip(),
                                    at=self.clock()))
        return self.current()


def rules_from(policy: dict[str, Any]) -> tuple[dict[str, CadenceRule], int]:
    return ({k: CadenceRule(**v) for k, v in policy["rules"].items()}, int(policy["live_thread_days"]))
