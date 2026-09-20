import json
import pytest
from app.modules.m15_document_generator.lane_api import DocumentBuilder, DocumentError, DocumentGeneratorService


def payload():
    return {
        "title": "Evidence brief",
        "created_at": "2026-09-20T10:00:00Z",
        "metadata": {"request_id": "r1"},
        "sources": [{"id": "s", "title": "Study", "content": "A sufficiently long exact quote.", "published_at": "2026-09-19"}],
        "sections": [{"heading": "Findings", "claims": [{"text": "Finding.", "evidence": [{"source_id": "s", "quote": "A sufficiently long exact quote"}]}]}],
    }


def test_builds_nested_document_from_api_mapping():
    document = DocumentBuilder().build(payload())
    assert document.sources[0].published_at.year == 2026
    assert document.created_at.tzinfo is not None
    assert document.sections[0].claims[0].evidence[0].source_id == "s"


def test_build_and_export_always_grounds():
    artifact = DocumentGeneratorService().build_and_export(payload(), "json")
    result = json.loads(artifact.data)
    assert result["citations"][0]["source_id"] == "s"


def test_unknown_fields_are_rejected_instead_of_ignored():
    data = payload()
    data["dangerous"] = True
    with pytest.raises(DocumentError, match="unknown fields"):
        DocumentBuilder().build(data)


def test_nested_type_errors_include_path():
    data = payload()
    data["sections"][0]["claims"] = "not-a-list"
    with pytest.raises(DocumentError, match=r"sections\[0\]\.claims"):
        DocumentBuilder().build(data)
