"""Cross-domain evaluation and provenance for Atlas autonomy mechanisms."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from app.modules.m25_knowledge_copilot.artifact_events import ArtifactEventStore


@dataclass(frozen=True)
class TransferCase:
    id: str
    domain: str
    problem: dict[str, Any]
    expected: Any
    source_domain: str | None = None


@dataclass(frozen=True)
class TransferResult:
    case_id: str
    domain: str
    source_domain: str | None
    passed: bool
    score: float
    output_hash: str
    error: str | None = None


class CrossDomainTransferBenchmark:
    """Scores one learned strategy on held-out domains.

    A benchmark must contain at least two domains and at least one explicitly
    transferred case. Coverage, accuracy and worst-domain accuracy are exposed
    separately so high volume in one easy domain cannot hide collapse elsewhere.
    """

    def __init__(self, cases: list[TransferCase]) -> None:
        domains = {c.domain for c in cases}
        if len(domains) < 2 or not any(c.source_domain and c.source_domain != c.domain for c in cases):
            raise ValueError("benchmark needs two domains and a cross-domain transfer case")
        if len({c.id for c in cases}) != len(cases):
            raise ValueError("case ids must be unique")
        self.cases = tuple(cases)

    def run(self, strategy: Callable[[dict[str, Any]], Any],
            scorer: Callable[[Any, Any], float] | None = None) -> dict[str, Any]:
        scorer = scorer or (lambda actual, expected: 1.0 if actual == expected else 0.0)
        results = []
        for case in self.cases:
            try:
                output = strategy(case.problem)
                score = float(scorer(output, case.expected))
                if not math.isfinite(score) or not 0 <= score <= 1:
                    raise ValueError("scorer must return a finite value in [0,1]")
                result = TransferResult(case.id, case.domain, case.source_domain, score == 1.0,
                                        score, self._hash(output))
            except Exception as exc:
                result = TransferResult(case.id, case.domain, case.source_domain, False, 0.0,
                                        self._hash(None), f"{type(exc).__name__}: {exc}")
            results.append(result)
        by_domain = {}
        for domain in sorted({c.domain for c in self.cases}):
            selected = [r.score for r in results if r.domain == domain]
            by_domain[domain] = sum(selected) / len(selected)
        transfers = [r.score for r in results if r.source_domain and r.source_domain != r.domain]
        return {"case_count": len(results), "domain_count": len(by_domain),
                "accuracy": sum(r.score for r in results) / len(results),
                "transfer_accuracy": sum(transfers) / len(transfers),
                "worst_domain_accuracy": min(by_domain.values()), "by_domain": by_domain,
                "results": [r.__dict__ for r in results],
                "benchmark_hash": self._hash([c.__dict__ for c in self.cases])}

    @staticmethod
    def _hash(value: Any) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class AGIProvenanceRecorder:
    """Records measured AGI-lane artifacts in the shared M25 event contract."""

    def __init__(self, store: ArtifactEventStore, tenant_id: str,
                 producer_version: str) -> None:
        self.store, self.tenant_id, self.producer_version = store, tenant_id, producer_version

    def record(self, *, artifact_kind: str, artifact: dict[str, Any],
               source_refs: list[dict[str, str]], execution_state: str = "simulated",
               receipt_ids: list[str] | None = None) -> dict[str, Any]:
        blob = json.dumps(artifact, sort_keys=True, separators=(",", ":"), default=str).encode()
        artifact_id, event_id = str(uuid4()), str(uuid4())
        event = {"event_id": event_id, "tenant_id": self.tenant_id, "module_id": 20,
                 "artifact_id": artifact_id, "artifact_kind": artifact_kind,
                 "content_sha256": hashlib.sha256(blob).hexdigest(),
                 "observed_at": datetime.now(timezone.utc).isoformat(),
                 "producer_version": self.producer_version, "source_refs": source_refs,
                 "execution_state": execution_state, "receipt_ids": receipt_ids or [],
                 "metadata": {"lane": "agi-runtime", "schema": 1}}
        import base64
        return self.store.put(event, artifact_base64=base64.b64encode(blob).decode())
