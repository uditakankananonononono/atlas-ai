"""Artifact manifest and validation framework for Atlas Module 14.

Stdlib-only. Artifacts are content-addressed: every manifest carries the
SHA-256 of its payload, and storage layout derives from the hash. The
validation framework checks hash format, URI safety, provenance completeness
per artifact kind, timestamp sanity, and reproducibility evidence, producing
reports shaped for the module's QualityResult contract (passed/score/
findings/remediation).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Dict, Mapping, Optional, Tuple
from uuid import uuid4

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

ALLOWED_URI_SCHEMES = frozenset({"file", "s3", "gs", "workspace"})


class ArtifactError(ValueError):
    """Base error for artifact operations."""


class UnknownKindError(ArtifactError):
    """Artifact kind is not registered."""


@dataclass(frozen=True)
class KindSpec:
    """Registry entry describing one artifact kind."""

    kind: str
    required_provenance: Tuple[str, ...] = ()
    reproducibility_keys: Tuple[str, ...] = ()


_DEFAULT_KINDS: Dict[str, KindSpec] = {
    "dataset": KindSpec(
        "dataset",
        required_provenance=("source", "retrieved_at"),
        reproducibility_keys=("source",),
    ),
    "code": KindSpec(
        "code",
        required_provenance=("generator",),
        reproducibility_keys=("generator", "prompt_hash"),
    ),
    "analysis": KindSpec(
        "analysis",
        required_provenance=("generator", "created_at"),
        reproducibility_keys=("generator", "code_uri"),
    ),
    "figure": KindSpec(
        "figure",
        required_provenance=("generator", "created_at"),
        reproducibility_keys=("generator", "code_uri"),
    ),
    "paper_draft": KindSpec(
        "paper_draft",
        required_provenance=("generator", "created_at"),
        reproducibility_keys=("generator",),
    ),
    "notes": KindSpec("notes", required_provenance=("author",)),
    "export": KindSpec(
        "export",
        required_provenance=("generator", "created_at"),
        reproducibility_keys=("generator",),
    ),
}


class KindRegistry:
    """Known artifact kinds and their provenance contracts."""

    def __init__(self, defaults: Optional[Mapping[str, KindSpec]] = None):
        self._kinds: Dict[str, KindSpec] = dict(defaults or _DEFAULT_KINDS)

    def register(self, spec: KindSpec) -> None:
        if not spec.kind or not spec.kind.replace("_", "").isalnum():
            raise ArtifactError(f"invalid kind name {spec.kind!r}")
        self._kinds[spec.kind] = spec

    def get(self, kind: str) -> KindSpec:
        try:
            return self._kinds[kind]
        except KeyError as exc:
            raise UnknownKindError(
                f"unknown artifact kind {kind!r}; registered: "
                + ", ".join(sorted(self._kinds))
            ) from exc

    def kinds(self) -> Tuple[str, ...]:
        return tuple(sorted(self._kinds))


@dataclass(frozen=True)
class ArtifactRecord:
    """Manifest for one artifact. Mirrors the module's ArtifactManifest."""

    id: str
    project_id: str
    task_id: str
    kind: str
    uri: str
    sha256: str
    provenance: Mapping[str, object] = field(default_factory=dict)


def _parse_uri(uri: str) -> Tuple[str, str]:
    if "://" not in uri:
        # Bare workspace-relative path.
        return "workspace", uri
    scheme, rest = uri.split("://", 1)
    return scheme.lower(), rest


def validate_uri(uri: str) -> None:
    """URI must use an allowed scheme and must not escape its root."""
    if not uri or not uri.strip():
        raise ArtifactError("uri must be non-empty")
    scheme, rest = _parse_uri(uri)
    if scheme not in ALLOWED_URI_SCHEMES:
        raise ArtifactError(
            f"uri scheme {scheme!r} not allowed; allowed: "
            + ", ".join(sorted(ALLOWED_URI_SCHEMES))
        )
    segments = [seg for seg in rest.split("/") if seg]
    if any(seg == ".." for seg in segments):
        raise ArtifactError("uri must not contain '..' path segments")
    if not segments:
        raise ArtifactError("uri must name an object, not only a scheme/root")


def build_manifest(
    project_id: str,
    task_id: str,
    kind: str,
    uri: str,
    payload: bytes,
    provenance: Mapping[str, object],
    registry: Optional[KindRegistry] = None,
) -> ArtifactRecord:
    """Create a manifest for a payload, hashing the exact bytes given."""
    if not project_id:
        raise ArtifactError("project_id must be non-empty")
    if not task_id:
        raise ArtifactError("task_id must be non-empty")
    (registry or KindRegistry()).get(kind)  # raises on unknown kind
    validate_uri(uri)
    if provenance is None:
        raise ArtifactError("provenance is required, even if empty")
    return ArtifactRecord(
        id=str(uuid4()),
        project_id=project_id,
        task_id=task_id,
        kind=kind,
        uri=uri,
        sha256=sha256(payload).hexdigest(),
        provenance=dict(provenance),
    )


def verify_payload(record: ArtifactRecord, payload: bytes) -> bool:
    """True when the payload still hashes to the recorded digest."""
    return sha256(payload).hexdigest() == record.sha256


def storage_path(record: ArtifactRecord) -> str:
    """Content-addressed workspace-relative storage path."""
    return (
        f"{record.project_id}/{record.task_id}/{record.kind}/"
        f"{record.sha256[:2]}/{record.sha256}"
    )


# --- Validation -------------------------------------------------------------


@dataclass(frozen=True)
class ValidationFinding:
    check: str
    severity: str  # "error" | "warning"
    message: str
    remediation: str


@dataclass(frozen=True)
class ArtifactValidationReport:
    artifact_id: str
    passed: bool
    score: float
    findings: Tuple[ValidationFinding, ...]
    remediation: Tuple[str, ...]

    def to_quality_result(self) -> Dict[str, object]:
        """Shape for the module's QualityResult pydantic contract."""
        return {
            "passed": self.passed,
            "score": self.score,
            "findings": [f.message for f in self.findings],
            "remediation": list(self.remediation),
        }


def _iso_parse_ok(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    text = value.strip().replace("Z", "+00:00")
    try:
        datetime.fromisoformat(text)
    except ValueError:
        return False
    return True


def _iso_not_future(value: str, now: datetime) -> bool:
    text = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed <= now


def validate_artifact(
    record: ArtifactRecord,
    payload: Optional[bytes] = None,
    registry: Optional[KindRegistry] = None,
    now: Optional[datetime] = None,
) -> ArtifactValidationReport:
    """Run all per-artifact checks. Errors fail; warnings only lower score."""
    registry = registry or KindRegistry()
    now = now or datetime.now(timezone.utc)
    findings = []

    if not _SHA256_RE.match(record.sha256):
        findings.append(
            ValidationFinding(
                check="sha256_format",
                severity="error",
                message="sha256 must be 64 lowercase hex characters",
                remediation="recompute the digest with hashlib.sha256 over the payload bytes",
            )
        )
    try:
        validate_uri(record.uri)
    except ArtifactError as exc:
        findings.append(
            ValidationFinding(
                check="uri_safe",
                severity="error",
                message=f"uri rejected: {exc}",
                remediation="use a workspace/s3/gs/file URI without '..' segments",
            )
        )
    try:
        spec = registry.get(record.kind)
    except UnknownKindError as exc:
        findings.append(
            ValidationFinding(
                check="kind_registered",
                severity="error",
                message=str(exc),
                remediation="register the kind or use a registered one",
            )
        )
        spec = None

    if spec is not None:
        missing = [
            key
            for key in spec.required_provenance
            if not str(record.provenance.get(key, "")).strip()
        ]
        if missing:
            findings.append(
                ValidationFinding(
                    check="provenance_complete",
                    severity="error",
                    message="missing provenance keys: " + ", ".join(sorted(missing)),
                    remediation="record " + ", ".join(sorted(missing)) + " in provenance",
                )
            )
        for key in spec.required_provenance:
            if key.endswith("_at"):
                raw = record.provenance.get(key)
                if raw and not _iso_parse_ok(raw):
                    findings.append(
                        ValidationFinding(
                            check="provenance_timestamps",
                            severity="error",
                            message=f"provenance[{key!r}] is not ISO-8601: {raw!r}",
                            remediation="store timestamps in ISO-8601 format",
                        )
                    )
                elif raw and _iso_parse_ok(raw) and not _iso_not_future(str(raw), now):
                    findings.append(
                        ValidationFinding(
                            check="provenance_timestamps",
                            severity="error",
                            message=f"provenance[{key!r}] is in the future: {raw!r}",
                            remediation="check the clock of the recording component",
                        )
                    )
        if spec.reproducibility_keys:
            repro_missing = [
                key
                for key in spec.reproducibility_keys
                if not str(record.provenance.get(key, "")).strip()
            ]
            if repro_missing:
                findings.append(
                    ValidationFinding(
                        check="reproducibility",
                        severity="warning",
                        message=(
                            "reproducibility evidence missing: "
                            + ", ".join(sorted(repro_missing))
                        ),
                        remediation=(
                            "attach " + ", ".join(sorted(repro_missing))
                            + " so this artifact can be regenerated"
                        ),
                    )
                )
    if payload is not None and not verify_payload(record, payload):
        findings.append(
            ValidationFinding(
                check="payload_integrity",
                severity="error",
                message="payload bytes do not match the recorded sha256",
                remediation="re-register the artifact with the bytes actually stored",
            )
        )

    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    score = max(0.0, 1.0 - 0.34 * errors - 0.1 * warnings)
    return ArtifactValidationReport(
        artifact_id=record.id,
        passed=errors == 0,
        score=round(score, 6),
        findings=tuple(findings),
        remediation=tuple(dict.fromkeys(f.remediation for f in findings)),
    )


@dataclass(frozen=True)
class SetValidationReport:
    project_id: str
    passed: bool
    score: float
    artifact_reports: Tuple[ArtifactValidationReport, ...]
    findings: Tuple[ValidationFinding, ...]


def validate_manifest_set(
    records: Tuple[ArtifactRecord, ...],
    project_id: str,
    registry: Optional[KindRegistry] = None,
    payloads: Optional[Mapping[str, bytes]] = None,
    now: Optional[datetime] = None,
) -> SetValidationReport:
    """Validate a project's artifact set, including cross-artifact checks."""
    registry = registry or KindRegistry()
    payloads = payloads or {}
    findings = []
    seen_uris: Dict[str, str] = {}
    seen_hashes: Dict[str, str] = {}
    for rec in records:
        if rec.project_id != project_id:
            findings.append(
                ValidationFinding(
                    check="project_consistency",
                    severity="error",
                    message=(
                        f"artifact {rec.id} belongs to project "
                        f"{rec.project_id!r}, expected {project_id!r}"
                    ),
                    remediation="only include artifacts from this project",
                )
            )
        if rec.uri in seen_uris and seen_uris[rec.uri] != rec.id:
            findings.append(
                ValidationFinding(
                    check="uri_unique",
                    severity="error",
                    message=f"uri {rec.uri!r} registered by multiple artifacts",
                    remediation="give each stored object its own uri",
                )
            )
        seen_uris.setdefault(rec.uri, rec.id)
        if rec.sha256 in seen_hashes and seen_hashes[rec.sha256] != rec.id:
            findings.append(
                ValidationFinding(
                    check="duplicate_content",
                    severity="warning",
                    message=f"identical content stored at {rec.uri!r} and another uri",
                    remediation="deduplicate identical payloads",
                )
            )
        seen_hashes.setdefault(rec.sha256, rec.id)
    reports = tuple(
        validate_artifact(rec, payload=payloads.get(rec.id), registry=registry, now=now)
        for rec in records
    )
    errors = sum(1 for f in findings if f.severity == "error") + sum(
        1 for r in reports for f in r.findings if f.severity == "error"
    )
    warnings = sum(1 for f in findings if f.severity == "warning") + sum(
        1 for r in reports for f in r.findings if f.severity == "warning"
    )
    score = max(0.0, 1.0 - 0.34 * errors - 0.1 * warnings)
    return SetValidationReport(
        project_id=project_id,
        passed=errors == 0,
        score=round(score, 6),
        artifact_reports=reports,
        findings=tuple(findings),
    )
