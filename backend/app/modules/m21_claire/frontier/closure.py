from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Callable

class CompletionRejected(ValueError):
    pass

class GapClosureEngine:
    """Turns an audit into a closure queue; never marks a gap done on prose alone.

    A normal row needs a passing automated test, an integration test, observed
    behavior, and a named reviewer. Forbidden/unbounded goals must be closed by
    recording a bounded safe substitute, not by falsely marking the original done.
    """
    def __init__(self, requirements: list[dict[str, Any]] | None = None, *,
                 receipt_verifier: Callable[[str, str], bool] | None = None):
        # receipt_verifier(kind, sha256) must confirm a stored artifact/receipt with that
        # digest exists. Without it, caller-supplied hashes are only attestations and a
        # row can never reach verified_complete.
        self.receipt_verifier = receipt_verifier
        if requirements is None:
            path = Path(__file__).with_name("requirements_backlog.json")
            requirements = json.loads(path.read_text("utf-8")) if path.exists() else []
        self.rows = {int(r["requirement_id"]): dict(r) for r in requirements}
        if len(self.rows) != len(requirements):
            raise ValueError("duplicate requirement ids")
        # Preseeded verified_complete is a claim, not a fact: keep it only when a verifier
        # confirms every digest in the row's own acceptance evidence.
        _hex=lambda v: isinstance(v,str) and len(v)==64 and all(c in "0123456789abcdef" for c in v.lower())
        for row in self.rows.values():
            if row.get("state") == "verified_complete":
                digests = [(k, str(e.get(k, "")).lower()) for e in row.get("acceptance_evidence", []) if isinstance(e, dict)
                           for k in ("automated_test_receipt_sha256", "integration_test_receipt_sha256", "artifact_sha256")]
                ok = (bool(digests) and all(_hex(v) for _, v in digests) and self.receipt_verifier is not None
                      and all(self.receipt_verifier(k, v) is True for k, v in digests))
                if not ok: row["state"] = "attested_unverified"
            elif row.get("state") == "safe_substitute":
                dg = str((row.get("safe_substitute_record") or {}).get("test_receipt_sha256", "")).lower()
                ok = _hex(dg) and self.receipt_verifier is not None and self.receipt_verifier("substitute_test_receipt_sha256", dg) is True
                if not ok: row["state"] = "substitute_proposed"

    def status(self) -> dict[str, Any]:
        counts = {"open": 0, "needs_verification": 0, "attested_unverified": 0, "substitute_proposed": 0, "verified_complete": 0, "safe_substitute": 0}
        for r in self.rows.values():
            s = r.get("state", "open")
            counts[s] = counts.get(s, 0) + 1
        return {"total": len(self.rows), "counts": counts,
                "complete_means": "test + integration test + observed result + reviewer",
                "claim": "Audit state only; this does not assert source-repository deployment."}

    def _priority_record(self, row: dict[str, Any]) -> dict[str, Any]:
        title=str(row.get("title", "")).casefold(); boundary=str(row.get("current_boundary", "")).casefold()
        previous=row.get("previous_status", "❌")
        impact=0.75 + (0.15 if any(k in title for k in ("research", "application", "persistent", "verification", "evidence", "preference")) else 0.0)
        if previous=="✅": feasibility=0.92; cost=0.8; recommended="verify actual integration and production behavior"
        elif previous=="🟨": feasibility=0.78; cost=1.0; recommended="implement the explicitly listed boundary and add regression tests"
        elif previous=="⛔": feasibility=0.90; cost=0.45; recommended="record and test a bounded safe substitute; do not implement the prohibited form"
        else: feasibility=0.58; cost=1.15; recommended="implement a bounded capability, provider adapter, or verified manual-review workflow"
        if any(k in title+" "+boundary for k in ("every", "all posts", "universe", "millions", "superintelligence", "guaranteed", "classified", "any industry")):
            feasibility*=0.55; cost*=1.6
            recommended="decompose into finite, measurable sub-capabilities; do not claim universal coverage"
        if any(k in title+" "+boundary for k in ("send", "publish", "submit", "email", "invest", "trade")):
            risk=0.22
        else: risk=0.08
        downstream=1.0 + 0.08 * sum(1 for other in self.rows.values() if str(row["requirement_id"]) in str(other.get("current_boundary", "")))
        score=impact*feasibility*downstream/cost*(1-risk)
        result=dict(row)
        result["priority_score"]=round(score,5)
        result["priority_factors"]={"impact":round(impact,3),"feasibility":round(feasibility,3),"downstream_leverage":round(downstream,3),"cost_index":round(cost,3),"risk_discount":round(risk,3)}
        result["recommended_next_action"]=recommended
        return result

    def list_gaps(self, limit: int = 20) -> list[dict[str, Any]]:
        rows=[self._priority_record(r) for r in self.rows.values() if r.get("state") not in {"verified_complete", "safe_substitute"}]
        return sorted(rows,key=lambda r:(-r["priority_score"],int(r["requirement_id"])))[:max(1,min(limit,65))]

    def record_progress(self, requirement_id: int, *, automated_test: bool,
                        automated_test_receipt_sha256: str, integration_test: str,
                        integration_test_receipt_sha256: str, observed_result: str,
                        reviewer_id: str, artifact_sha256: str,
                        notes: str = "") -> dict[str, Any]:
        if requirement_id not in self.rows: raise KeyError(requirement_id)
        if not automated_test or not integration_test.strip() or not observed_result.strip() or not reviewer_id.strip():
            raise CompletionRejected("Need a passing automated test, integration evidence, observed result, and reviewer")
        hashes={"automated_test_receipt_sha256":automated_test_receipt_sha256,
                "integration_test_receipt_sha256":integration_test_receipt_sha256,"artifact_sha256":artifact_sha256}
        for name,digest in hashes.items():
            if len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest.lower()):
                raise CompletionRejected(f"{name} must be a 64-character SHA-256 digest")
        row = self.rows[requirement_id]
        if row.get("previous_status") == "⛔":
            raise CompletionRejected("This request is intentionally excluded; record a safe substitute instead")
        evidence = {"automated_test": True, "automated_test_receipt_sha256": automated_test_receipt_sha256.lower(),
                    "integration_test": integration_test, "integration_test_receipt_sha256":integration_test_receipt_sha256.lower(),
                    "observed_result": observed_result, "reviewer_id": reviewer_id,
                    "artifact_sha256": artifact_sha256.lower(), "notes": notes}
        row.setdefault("acceptance_evidence", []).append(evidence)
        verified = self.receipt_verifier is not None and all(
            self.receipt_verifier(name, digest.lower()) is True for name, digest in hashes.items())
        row["state"] = "verified_complete" if verified else "attested_unverified"
        return dict(row)

    def record_safe_substitute(self, requirement_id: int, *, substitute: str,
                               boundary: str, test_evidence: str, reviewer_id: str,
                               test_receipt_sha256: str = "") -> dict[str, Any]:
        if requirement_id not in self.rows: raise KeyError(requirement_id)
        if not all(x.strip() for x in (substitute, boundary, test_evidence, reviewer_id)):
            raise ValueError("substitute, boundary, test evidence, and reviewer are required")
        row = self.rows[requirement_id]
        digest = test_receipt_sha256.lower()
        verified = (len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
                    and self.receipt_verifier is not None and self.receipt_verifier("substitute_test_receipt_sha256", digest) is True)
        # Prose test evidence alone never closes a row.
        row["state"] = "safe_substitute" if verified else "substitute_proposed"
        row["safe_substitute_record"] = {"test_receipt_sha256": digest, "substitute": substitute, "boundary": boundary,
                                         "test_evidence": test_evidence, "reviewer_id": reviewer_id}
        return dict(row)

    def export(self) -> list[dict[str, Any]]:
        return [dict(self.rows[i]) for i in sorted(self.rows)]
