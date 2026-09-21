"""Deterministic contradiction inbox for source-grounded knowledge claims."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class ClaimEvidence(BaseModel):
    evidence_id: str = Field(min_length=1, max_length=200)
    claim_key: str = Field(min_length=1, max_length=500)
    value: str = Field(min_length=1, max_length=4000)
    source_uri: HttpUrl
    observed_at: datetime
    confidence: float = Field(ge=0, le=1)


class ContradictionDecision(BaseModel):
    claim_key: str = Field(min_length=1, max_length=500)
    action: Literal["retain_both", "prefer"]
    preferred_evidence_id: str | None = None
    rationale: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def preferred_required(self):
        if self.action == "prefer" and not self.preferred_evidence_id:
            raise ValueError("preferred_evidence_id is required when action is prefer")
        if self.action == "retain_both" and self.preferred_evidence_id is not None:
            raise ValueError("retain_both cannot name preferred evidence")
        return self


class ContradictionInboxRequest(BaseModel):
    evidence: list[ClaimEvidence] = Field(min_length=1, max_length=2000)
    decisions: list[ContradictionDecision] = Field(default_factory=list, max_length=500)
    stale_after_days: int = Field(default=30, ge=1, le=3650)
    as_of: datetime | None = None

    @model_validator(mode="after")
    def unique_ids_and_decisions(self):
        evidence_ids = [row.evidence_id for row in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("duplicate evidence_id")
        keys = [decision.claim_key.casefold().strip() for decision in self.decisions]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate decision for claim_key")
        return self


def build_contradiction_inbox(request: ContradictionInboxRequest) -> dict:
    as_of = request.as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    as_of = as_of.astimezone(timezone.utc)
    evidence_by_id = {row.evidence_id: row for row in request.evidence}
    grouped: dict[str, list[ClaimEvidence]] = defaultdict(list)
    display_keys: dict[str, str] = {}
    for row in request.evidence:
        if row.observed_at.tzinfo is None:
            raise ValueError(f"observed_at must be timezone-aware: {row.evidence_id}")
        key = row.claim_key.casefold().strip()
        display_keys.setdefault(key, row.claim_key.strip())
        grouped[key].append(row)

    decisions = {row.claim_key.casefold().strip(): row for row in request.decisions}
    unknown_decisions = sorted(set(decisions) - set(grouped))
    if unknown_decisions:
        raise ValueError(f"decision references unknown claim_key: {unknown_decisions[0]}")

    inbox = []
    stale_total = 0
    for key in sorted(grouped):
        rows = sorted(grouped[key], key=lambda row: row.evidence_id)
        distinct_values = {" ".join(row.value.casefold().split()) for row in rows}
        if len(distinct_values) < 2:
            continue
        evidence = []
        row_ids = {row.evidence_id for row in rows}
        for row in rows:
            age_days = max(0, (as_of - row.observed_at.astimezone(timezone.utc)).days)
            stale = age_days > request.stale_after_days
            stale_total += int(stale)
            evidence.append({
                "evidence_id": row.evidence_id,
                "value": row.value,
                "source_uri": str(row.source_uri),
                "observed_at": row.observed_at.astimezone(timezone.utc).isoformat(),
                "age_days": age_days,
                "stale": stale,
                "confidence": row.confidence,
            })
        decision = decisions.get(key)
        if decision and decision.preferred_evidence_id not in row_ids and decision.action == "prefer":
            raise ValueError(f"preferred evidence is not part of contradiction: {decision.preferred_evidence_id}")
        inbox.append({
            "claim_key": display_keys[key],
            "evidence": evidence,
            "status": "decided" if decision else "unresolved",
            "decision": decision.model_dump(mode="json") if decision else None,
            "recommended_review_order": [
                row["evidence_id"] for row in sorted(
                    evidence, key=lambda item: (item["stale"], -item["confidence"], -datetime.fromisoformat(item["observed_at"]).timestamp())
                )
            ],
        })

    canonical = json.dumps(inbox, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    unresolved = sum(item["status"] == "unresolved" for item in inbox)
    return {
        "as_of": as_of.isoformat(),
        "stale_after_days": request.stale_after_days,
        "contradiction_count": len(inbox),
        "unresolved_count": unresolved,
        "decided_count": len(inbox) - unresolved,
        "stale_evidence_count": stale_total,
        "inbox": inbox,
        "inbox_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "boundary": "Contradictions compare supplied claim values and source metadata only; Atlas does not authenticate sources or decide which claim is true.",
    }
