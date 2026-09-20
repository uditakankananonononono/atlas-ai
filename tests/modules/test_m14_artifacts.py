"""Tests for the Module 14 artifact manifest and validation framework."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from app.modules.m14_project_builder.artifacts import (
    ArtifactError,
    ArtifactRecord,
    KindRegistry,
    KindSpec,
    UnknownKindError,
    build_manifest,
    storage_path,
    validate_artifact,
    validate_manifest_set,
    validate_uri,
    verify_payload,
)

UTC = timezone.utc
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
PAST = (NOW - timedelta(hours=2)).isoformat()


def make_record(kind="dataset", uri="workspace://p1/t1/data.csv",
                payload=b"col1,col2\n1,2\n", provenance=None):
    prov = provenance if provenance is not None else {
        "source": "https://example.org/data", "retrieved_at": PAST,
    }
    return build_manifest("p1", "t1", kind, uri, payload, prov)


class TestUriValidation:
    @pytest.mark.parametrize("uri", [
        "workspace://p1/t1/out.csv", "file:///data/out.csv",
        "s3://bucket/key", "gs://bucket/key", "p1/t1/out.csv",
    ])
    def test_allowed_uris(self, uri):
        validate_uri(uri)

    @pytest.mark.parametrize("uri", [
        "", "  ", "http://example.org/x", "ftp://host/x",
        "workspace://../escape", "s3://bucket/../../x", "workspace://",
    ])
    def test_rejected_uris(self, uri):
        with pytest.raises(ArtifactError):
            validate_uri(uri)


class TestManifest:
    def test_hashes_exact_payload(self):
        payload = b"hello atlas"
        rec = build_manifest("p1", "t1", "notes", "workspace://p1/t1/n.md",
                             payload, {"author": "writer-agent"})
        assert rec.sha256 == sha256(payload).hexdigest()
        assert verify_payload(rec, payload)
        assert not verify_payload(rec, payload + b"!")

    def test_unknown_kind_rejected(self):
        with pytest.raises(UnknownKindError):
            build_manifest("p1", "t1", "mystery", "workspace://x", b"", {})

    def test_empty_ids_rejected(self):
        with pytest.raises(ArtifactError):
            build_manifest("", "t1", "notes", "workspace://x", b"", {"author": "a"})
        with pytest.raises(ArtifactError):
            build_manifest("p1", "", "notes", "workspace://x", b"", {"author": "a"})

    def test_storage_path_is_content_addressed(self):
        rec = make_record()
        path = storage_path(rec)
        assert path == f"p1/t1/dataset/{rec.sha256[:2]}/{rec.sha256}"

    def test_registry_extension(self):
        registry = KindRegistry()
        registry.register(KindSpec("model", required_provenance=("framework",)))
        rec = build_manifest("p1", "t1", "model", "workspace://p1/t1/m.bin",
                             b"weights", {"framework": "sklearn"}, registry=registry)
        assert rec.kind == "model"
        with pytest.raises(ArtifactError):
            registry.register(KindSpec("bad kind!"))


class TestArtifactValidation:
    def test_clean_record_passes(self):
        rec = make_record()
        report = validate_artifact(rec, payload=b"col1,col2\n1,2\n", now=NOW)
        assert report.passed
        assert report.score == 1.0
        assert report.findings == ()

    def test_bad_hash_format_fails(self):
        rec = make_record()
        bad = ArtifactRecord(**{**rec.__dict__, "sha256": "ZZZ"})
        report = validate_artifact(bad, now=NOW)
        assert not report.passed
        assert any(f.check == "sha256_format" for f in report.findings)

    def test_bad_uri_fails(self):
        rec = make_record()
        bad = ArtifactRecord(**{**rec.__dict__, "uri": "http://evil.org/x"})
        report = validate_artifact(bad, now=NOW)
        assert not report.passed
        assert any(f.check == "uri_safe" for f in report.findings)

    def test_missing_provenance_fails_with_remediation(self):
        rec = make_record(provenance={"source": "x"})
        report = validate_artifact(rec, now=NOW)
        assert not report.passed
        prov = next(f for f in report.findings if f.check == "provenance_complete")
        assert "retrieved_at" in prov.message
        assert "retrieved_at" in prov.remediation

    def test_unparseable_timestamp_fails(self):
        rec = make_record(provenance={"source": "x", "retrieved_at": "last tuesday"})
        report = validate_artifact(rec, now=NOW)
        assert any(f.check == "provenance_timestamps" for f in report.findings)
        assert not report.passed

    def test_future_timestamp_fails(self):
        future = (NOW + timedelta(days=1)).isoformat()
        rec = make_record(provenance={"source": "x", "retrieved_at": future})
        report = validate_artifact(rec, now=NOW)
        assert any("future" in f.message for f in report.findings)
        assert not report.passed

    def test_reproducibility_gap_warns_but_passes(self):
        rec = build_manifest("p1", "t1", "analysis", "workspace://p1/t1/a.ipynb",
                             b"nb", {"generator": "analyst-agent", "created_at": PAST})
        report = validate_artifact(rec, now=NOW)
        assert report.passed
        assert report.score < 1.0
        assert any(f.check == "reproducibility" and f.severity == "warning"
                   for f in report.findings)

    def test_payload_mismatch_fails(self):
        rec = make_record()
        report = validate_artifact(rec, payload=b"tampered", now=NOW)
        assert not report.passed
        assert any(f.check == "payload_integrity" for f in report.findings)

    def test_quality_result_shape(self):
        rec = make_record(provenance={"source": "x"})
        result = validate_artifact(rec, now=NOW).to_quality_result()
        assert set(result) == {"passed", "score", "findings", "remediation"}
        assert isinstance(result["passed"], bool)
        assert 0.0 <= result["score"] <= 1.0
        assert all(isinstance(s, str) for s in result["findings"])

    def test_remediation_deduplicated(self):
        rec = make_record(provenance={"source": "x"})
        report = validate_artifact(rec, now=NOW)
        assert len(report.remediation) == len(set(report.remediation))


class TestSetValidation:
    def test_foreign_project_artifact_fails(self):
        rec = make_record()
        foreign = ArtifactRecord(**{**rec.__dict__, "project_id": "p2"})
        report = validate_manifest_set((rec, foreign), "p1", now=NOW)
        assert not report.passed
        assert any(f.check == "project_consistency" for f in report.findings)

    def test_duplicate_uri_fails(self):
        a = make_record(uri="workspace://p1/t1/dup.csv")
        b = make_record(uri="workspace://p1/t1/dup.csv")
        report = validate_manifest_set((a, b), "p1", now=NOW)
        assert not report.passed
        assert any(f.check == "uri_unique" for f in report.findings)

    def test_duplicate_content_warns(self):
        payload = b"same bytes"
        a = make_record(uri="workspace://p1/t1/a.csv", payload=payload)
        b = make_record(uri="workspace://p1/t1/b.csv", payload=payload)
        report = validate_manifest_set((a, b), "p1", now=NOW)
        assert report.passed
        assert any(f.check == "duplicate_content" and f.severity == "warning"
                   for f in report.findings)

    def test_clean_set_passes(self):
        a = make_record(uri="workspace://p1/t1/a.csv", payload=b"aaa")
        b = make_record(uri="workspace://p1/t1/b.csv", payload=b"bbb")
        report = validate_manifest_set((a, b), "p1", now=NOW)
        assert report.passed
        assert report.score == 1.0
        assert len(report.artifact_reports) == 2
