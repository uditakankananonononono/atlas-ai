"""Claire claim path: no claim is labelled verified/supported unless a sandboxed proof checker accepted its evidence.

Claire's existing helpers label claims 'verified_from_cited_source' (tool_discovery: the cited source id exists) or
'supported' (advice: some source id exists). Those are lookups, not proofs. enforce_claim_labels() takes a payload those
helpers return plus proofs keyed by claim id, and downgrades any strong label that has no VERIFIED proof, keeping the
original label on the record (nothing is edited quietly). Action-driving claims that are not VERIFIED are blocked.
Confidence is carried alongside and never changes a label.
"""
from __future__ import annotations

import copy
from typing import Any

from app.self_improve.proof_carrying import Conclusion, Limits, VERIFIED, verify

STRONG = {"verified", "verified_from_cited_source", "supported", "known", "supported by current evidence"}
DOWNGRADE_TO = "unverified"


class ClaimBlocked(PermissionError):
    def __init__(self, claim_id, status, reason):
        self.claim_id, self.status, self.reason = claim_id, status, reason
        super().__init__(f"action-driving claim {claim_id!r} is {status}: {reason}")


def prove(claims: list[dict], limits: Limits = Limits()) -> dict[str, dict]:
    """claims: dicts with id, claim, kind, evidence, confidence. Returns {id: verdict-dict}."""
    out = {}
    for c in claims:
        cid = c.get("id")
        if cid in out:
            out[cid] = {"status": "UNVERIFIED", "reason": "duplicate claim id", "confidence": None}
            continue
        v = verify(Conclusion(str(c.get("claim", "")), c.get("kind"), c.get("evidence") or {},
                              c.get("confidence", 0.5)), limits)
        out[cid] = {"status": v.status, "reason": v.reason, "confidence": v.confidence}
    return out


def enforce_claim_labels(payload: dict[str, Any], proofs: dict[str, dict]) -> dict[str, Any]:
    """Return a deep copy of payload with every claim in payload['claims'] (or each product's 'claims') relabelled."""
    res = copy.deepcopy(payload)
    def fix(c: dict):
        cid = c.get("id") or c.get("claim_id")
        pr = proofs.get(cid) if cid is not None else None
        status = pr["status"] if pr else "VERIFICATION_IMPOSSIBLE"
        c["proof"] = pr or {"status": status, "reason": "no proof supplied", "confidence": None}
        old = c.get("status")
        if isinstance(old, str) and old.lower() in STRONG and status != VERIFIED:
            c["status"] = DOWNGRADE_TO
            c["status_corrected"] = {"original_label": old, "reason": f"proof {status}: {c['proof']['reason']}"}
        if c.get("action_driving") and status != VERIFIED:
            c["blocked"] = True
    for c in res.get("claims", []) or []:
        if isinstance(c, dict):
            fix(c)
    for p in res.get("products", []) or []:
        for c in (p.get("claims", []) if isinstance(p, dict) else []):
            if isinstance(c, dict):
                fix(c)
    return res


def require_verified(claims: list[dict], proofs: dict[str, dict]) -> None:
    """Raise ClaimBlocked on the first action-driving claim without a VERIFIED proof."""
    for c in claims:
        if c.get("action_driving"):
            pr = proofs.get(c.get("id"))
            if not pr or pr["status"] != VERIFIED:
                raise ClaimBlocked(c.get("id"), pr["status"] if pr else "VERIFICATION_IMPOSSIBLE",
                                   pr["reason"] if pr else "no proof supplied")


# ---- consequential-action path: Orchestrator(policy=ProofGatedActionPolicy()) -------------------------------------
from .models import ActionRequest  # noqa: E402
from .policy import ActionPolicy, PolicyDecision  # noqa: E402


class ProofGatedActionPolicy(ActionPolicy):
    """ActionPolicy that refuses a consequential action (approval-required or HIGH risk) unless every claim in
    request.parameters['claims'] marked action_driving is VERIFIED by the sandboxed checker, and at least one such
    claim is declared. The base policy runs first, so hard blocks and the approval requirement are unchanged.
    Orchestrator re-calls require_allowed at execution time, so the proofs are re-run then too.
    Scope: only requests that go through this policy are gated; a caller can still build Orchestrator() with the plain
    ActionPolicy, and a caller can omit the 'claims' key (which is refused for consequential actions here)."""

    def __init__(self, limits: Limits = Limits()) -> None:
        self._limits = limits

    def evaluate(self, request: ActionRequest) -> PolicyDecision:
        base = super().evaluate(request)
        if not base.allowed or not base.requires_approval:
            return base
        claims = request.parameters.get("claims") if hasattr(request.parameters, "get") else None
        if not isinstance(claims, (list, tuple)) or not all(isinstance(c, dict) for c in claims):
            return PolicyDecision(False, False, "consequential action carries no claims list")
        driving = [c for c in claims if c.get("action_driving") is True]
        if not driving:
            return PolicyDecision(False, False, "consequential action declares no action-driving claim")
        proofs = prove(list(driving), self._limits)
        for c in driving:
            pr = proofs[c.get("id")]
            if pr["status"] != VERIFIED:
                return PolicyDecision(False, False, f"unproven action-driving claim {c.get('id')!r}: "
                                                    f"{pr['status']}: {pr['reason']}")
        return base
