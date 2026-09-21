import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.m09_knowledge_workspace.humanities_support_1860_1909 import HANDLERS, METHOD_SPECS, humanities_support_1860_1909

SOURCE = {"id": "s1", "title": "Archive item", "source_url": "https://archive.example/item", "provenance": "catalogue record A-1"}

def golden(row: int) -> dict:
    field = METHOD_SPECS[row]["input_field"]
    return {
        "sources": [SOURCE],
        field: [{
            "id": f"e-{row}", "source_ids": ["s1"], "citation": "Archive item, fol. 2r",
            "quotation": "supplied excerpt", "observations": [f"observed for {row}"],
            "interpretations": [f"reading for {row}"], "alternatives": [f"alternative for {row}"],
            "uncertainty": "dating remains uncertain", "data": {"row": row},
        }],
    }

ROWS = list(range(1860, 1910))
ROW_IDS = [f"row_{row}_{METHOD_SPECS[row]['handler']}" for row in ROWS]

@pytest.mark.parametrize("row", ROWS, ids=ROW_IDS)
def test_row_level_golden_fixture_has_distinct_method_and_exact_wording(row):
    result = humanities_support_1860_1909(row, golden(row))
    spec = METHOD_SPECS[row]
    assert result["feature_id"] == row
    assert result["concept"] == spec["name"]
    assert result["method"] == spec["handler"]
    assert result["operation"] == spec["operation"]
    assert result["input_field"] == spec["input_field"]
    assert result["citation_index"] == {"Archive item, fol. 2r": 1}
    assert result["interpretive_alternatives"] == [f"alternative for {row}"]
    assert result["uncertainties"] == ["dating remains uncertain"]
    assert result["no_fabricated_evidence"] is True

def test_registry_exposes_fifty_distinct_named_handlers_and_mechanisms():
    assert len(HANDLERS) == len(METHOD_SPECS) == 50
    assert len({handler.__name__ for handler in HANDLERS.values()}) == 50
    assert len({spec["operation"] for spec in METHOD_SPECS.values()}) == 50
    assert len({spec["input_field"] for spec in METHOD_SPECS.values()}) == 50

@pytest.mark.parametrize("row", ROWS, ids=ROW_IDS)
def test_row_fails_when_its_required_corpus_is_missing(row):
    with pytest.raises(ValueError, match="non-empty corpus"):
        humanities_support_1860_1909(row, {"sources": [SOURCE]})

@pytest.mark.parametrize("row", ROWS, ids=ROW_IDS)
def test_row_fails_when_citation_is_missing(row):
    payload = golden(row)
    payload[METHOD_SPECS[row]["input_field"]][0].pop("citation")
    with pytest.raises(ValueError, match="requires a citation"):
        humanities_support_1860_1909(row, payload)

@pytest.mark.parametrize("row", ROWS, ids=ROW_IDS)
def test_row_rejects_unsupported_inference(row):
    payload = golden(row)
    payload[METHOD_SPECS[row]["input_field"]][0]["source_ids"] = ["invented-source"]
    with pytest.raises(ValueError, match="unsupported inference"):
        humanities_support_1860_1909(row, payload)

def test_never_synthesizes_a_missing_quotation():
    payload = golden(1860)
    payload["narrative_units"][0].pop("quotation")
    result = humanities_support_1860_1909(1860, payload)
    assert result["evidence"][0]["quotation"] is None

def test_interpretation_requires_an_alternative():
    payload = golden(1894)
    payload["art_objects"][0]["alternatives"] = []
    with pytest.raises(ValueError, match="interpretive alternatives"):
        humanities_support_1860_1909(1894, payload)

def test_exact_route_mount_and_tenant_actor_isolation():
    client = TestClient(app)
    payload = {"feature_id": 1909, "data": golden(1909)}
    one = client.post("/api/v1/knowledge-workspace/humanities-1860-1909/support", headers={"x-atlas-tenant": "tenant-a", "x-atlas-actor": "actor-a"}, json=payload)
    two = client.post("/api/v1/knowledge-workspace/humanities-1860-1909/support", headers={"x-atlas-tenant": "tenant-b", "x-atlas-actor": "actor-b"}, json=payload)
    assert one.status_code == two.status_code == 200
    assert one.json()["tenant_id"] == "tenant-a" and one.json()["actor_id"] == "actor-a"
    assert two.json()["tenant_id"] == "tenant-b" and two.json()["actor_id"] == "actor-b"
    assert one.json()["operation"] == "reproducible corpus encoding and network analysis"
