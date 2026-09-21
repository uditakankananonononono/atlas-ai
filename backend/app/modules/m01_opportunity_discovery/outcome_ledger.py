"""Consented first-party application outcome ledger.

This module records user-reported outcomes with provenance and bounded
retention. It deliberately exposes no feature matrix, export-for-training, or
model fitting API. Declines and awards follow the same validation path.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from threading import RLock
from typing import Iterable
from uuid import uuid4


class OutcomeStatus(StrEnum):
    PENDING = "pending"
    AWARDED = "awarded"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"
    WAITLISTED = "waitlisted"


class ProvenanceKind(StrEnum):
    USER_REPORTED = "user_reported"
    OFFICIAL_NOTICE = "official_notice"
    PROVIDER_READBACK = "provider_readback"


@dataclass(frozen=True, slots=True)
class OutcomeProvenance:
    kind: ProvenanceKind
    source_reference: str
    observed_at: datetime
    recorded_by: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip() or not self.recorded_by.strip():
            raise ValueError("source_reference and recorded_by are required")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class OutcomeConsent:
    purpose: str
    granted_at: datetime
    expires_at: datetime
    evidence_reference: str

    def __post_init__(self) -> None:
        if self.purpose != "application_outcome_history":
            raise ValueError("consent purpose must be application_outcome_history")
        if self.granted_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("consent timestamps must be timezone-aware")
        if self.expires_at <= self.granted_at:
            raise ValueError("consent expiry must follow grant time")
        if not self.evidence_reference.strip():
            raise ValueError("consent evidence_reference is required")

    def valid_at(self, moment: datetime) -> bool:
        return self.granted_at <= moment < self.expires_at


@dataclass(frozen=True, slots=True)
class ApplicationOutcome:
    id: str
    owner_id: str
    opportunity_id: str
    sponsor: str
    mechanism: str
    cycle: str
    geography: str
    status: OutcomeStatus
    provenance: OutcomeProvenance
    consent: OutcomeConsent
    recorded_at: datetime
    retain_until: datetime
    decision_at: datetime | None = None
    amount: float | None = None
    currency: str | None = None
    advisory_only: bool = True
    training_enabled: bool = False

    def __post_init__(self) -> None:
        required = (self.owner_id, self.opportunity_id, self.sponsor, self.mechanism, self.cycle, self.geography)
        if not all(value.strip() for value in required):
            raise ValueError("owner, opportunity and program key fields are required")
        if self.recorded_at.tzinfo is None or self.retain_until.tzinfo is None:
            raise ValueError("ledger timestamps must be timezone-aware")
        if self.retain_until <= self.recorded_at:
            raise ValueError("retain_until must follow recorded_at")
        if self.status in {OutcomeStatus.AWARDED, OutcomeStatus.DECLINED, OutcomeStatus.WITHDRAWN} and self.decision_at is None:
            raise ValueError(f"decision_at is required for {self.status.value}")
        if self.decision_at is not None and self.decision_at.tzinfo is None:
            raise ValueError("decision_at must be timezone-aware")
        if self.amount is not None and self.amount < 0:
            raise ValueError("amount cannot be negative")
        if self.amount is not None and not (self.currency or "").strip():
            raise ValueError("currency is required when amount is recorded")
        if self.training_enabled or not self.advisory_only:
            raise ValueError("outcome ledger is advisory-only and cannot enable training")


class OutcomeLedger:
    """Thread-safe tenant-isolated ledger with consent and retention checks."""
    def __init__(self, *, max_retention_days: int = 1095) -> None:
        if max_retention_days < 1:
            raise ValueError("max_retention_days must be positive")
        self.max_retention_days = max_retention_days
        self._items: dict[str, ApplicationOutcome] = {}
        self._lock = RLock()

    def record(self, *, owner_id: str, opportunity_id: str, sponsor: str, mechanism: str,
               cycle: str, geography: str, status: OutcomeStatus, provenance: OutcomeProvenance,
               consent: OutcomeConsent, recorded_at: datetime | None = None,
               retention_days: int = 365, decision_at: datetime | None = None,
               amount: float | None = None, currency: str | None = None) -> ApplicationOutcome:
        now = recorded_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        if not consent.valid_at(now):
            raise PermissionError("active outcome-history consent is required")
        if not 1 <= retention_days <= self.max_retention_days:
            raise ValueError(f"retention_days must be between 1 and {self.max_retention_days}")
        retain_until = min(now + timedelta(days=retention_days), consent.expires_at)
        item = ApplicationOutcome(
            id=str(uuid4()), owner_id=owner_id, opportunity_id=opportunity_id,
            sponsor=sponsor, mechanism=mechanism, cycle=cycle, geography=geography,
            status=OutcomeStatus(status), provenance=provenance, consent=consent,
            recorded_at=now, retain_until=retain_until, decision_at=decision_at,
            amount=amount, currency=currency.upper() if currency else None,
        )
        with self._lock:
            self._items[item.id] = item
        return item

    def revise_status(self, owner_id: str, item_id: str, status: OutcomeStatus,
                      provenance: OutcomeProvenance, *, decision_at: datetime | None = None,
                      amount: float | None = None, currency: str | None = None,
                      at: datetime | None = None) -> ApplicationOutcome:
        now = at or datetime.now(timezone.utc)
        with self._lock:
            current = self._owned(owner_id, item_id)
            if now >= current.retain_until:
                raise LookupError(item_id)
            if not current.consent.valid_at(now):
                raise PermissionError("active outcome-history consent is required")
            revised = replace(current, status=OutcomeStatus(status), provenance=provenance,
                              decision_at=decision_at, amount=amount,
                              currency=currency.upper() if currency else None)
            self._items[item_id] = revised
            return revised

    def list(self, owner_id: str, *, at: datetime | None = None) -> tuple[ApplicationOutcome, ...]:
        self.purge_expired(at=at)
        with self._lock:
            return tuple(sorted((x for x in self._items.values() if x.owner_id == owner_id), key=lambda x: x.recorded_at))

    def delete(self, owner_id: str, item_id: str) -> bool:
        with self._lock:
            self._owned(owner_id, item_id)
            del self._items[item_id]
            return True

    def revoke_consent(self, owner_id: str, evidence_reference: str) -> int:
        """Delete rows covered by the revoked consent evidence immediately."""
        with self._lock:
            ids = [x.id for x in self._items.values() if x.owner_id == owner_id and x.consent.evidence_reference == evidence_reference]
            for item_id in ids:
                del self._items[item_id]
            return len(ids)

    def purge_expired(self, *, at: datetime | None = None) -> int:
        now = at or datetime.now(timezone.utc)
        with self._lock:
            ids = [x.id for x in self._items.values() if now >= x.retain_until or not x.consent.valid_at(now)]
            for item_id in ids:
                del self._items[item_id]
            return len(ids)

    def _owned(self, owner_id: str, item_id: str) -> ApplicationOutcome:
        item = self._items.get(item_id)
        if item is None or item.owner_id != owner_id:
            raise LookupError(item_id)
        return item
