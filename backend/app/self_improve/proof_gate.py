"""ProofCarryingGate: an ImprovementGate that also requires every attached conclusion to be VERIFIED by the sandboxed
checker in proof_carrying.py. Confidence is recorded separately and never changes the outcome.

Scope: this subclass cannot stop a caller from instantiating plain ImprovementGate directly (improvement_gate.py is
unchanged in this patch); it makes the proof requirement impossible to skip *through this class*.
"""
from __future__ import annotations

import json

from .improvement_gate import ChangePlan, ImprovementGate, PlanRefused
from .proof_carrying import Conclusion, IMPOSSIBLE, VERIFIED, Limits, verify

CODE_UNPROVEN = "PLAN_REFUSED_UNPROVEN"


class ProofCarryingGate(ImprovementGate):
    def __init__(self, *a, limits: Limits = Limits(), **kw) -> None:
        super().__init__(*a, **kw)
        self._limits = limits

    def _refuse(self, plan, detail: str, verdicts=()):
        self._append({"event": "refused", "at": self._now(), "code": CODE_UNPROVEN, "detail": detail,
                      "digest": plan.digest() if isinstance(plan, ChangePlan) else None, "module": self.module_slug,
                      "proofs": list(verdicts)})
        raise PlanRefused(CODE_UNPROVEN, detail)

    def authorize(self, plan, evidence, conclusions=None, advisory=()):
        """conclusions: non-empty list of Conclusion, each bound to this plan (plan_digest) and VERIFIED.
        advisory: conclusions recorded with their real status but not gating (e.g. opinions -> IMPOSSIBLE)."""
        if not isinstance(plan, ChangePlan):
            return super().authorize(plan, evidence)      # base class refuses the bad plan and logs it
        if not isinstance(conclusions, (list, tuple)) or len(conclusions) == 0:
            self._refuse(plan, "at least one proof-carrying conclusion is required")
        digest = plan.digest()
        verdicts = []
        failed = None
        for c in conclusions:
            if not isinstance(c, Conclusion):
                v = {"claim": None, "status": "UNVERIFIED", "reason": "not a Conclusion", "confidence": None}
            elif c.plan_digest != digest:
                v = {"claim": c.claim, "status": "UNVERIFIED", "reason": "conclusion is not bound to this plan",
                     "confidence": None}
            else:
                r = verify(c, self._limits)
                v = {"claim": c.claim, "kind": c.kind, "status": r.status, "reason": r.reason, "confidence": r.confidence}
            verdicts.append(v)
            if v["status"] != VERIFIED and failed is None:
                failed = v
        for c in advisory or ():
            if isinstance(c, Conclusion):
                r = verify(c, self._limits)
                verdicts.append({"claim": c.claim, "kind": c.kind, "status": r.status, "reason": r.reason,
                                 "confidence": r.confidence, "advisory": True})
        if failed is not None:
            self._refuse(plan, f"conclusion not verified: {failed['status']}: {failed['reason']}", verdicts)
        self._append({"event": "proofs_verified", "at": self._now(), "digest": digest, "module": self.module_slug,
                      "proofs": verdicts})
        return super().authorize(plan, evidence)
