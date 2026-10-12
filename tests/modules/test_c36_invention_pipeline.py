"""c36.invention_pipeline tests (row 106): corpus -> concept graph ->
cross-document invention briefs with provenance; honest coverage counts."""
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.modules.c36 import invention_pipeline as ip  # noqa: E402

DOC_A = ("Photosynthesis converts sunlight into chemical energy. Chlorophyll "
         "absorbs sunlight in leaves. Engineers study photosynthesis for solar "
         "cells; sunlight harvesting and energy storage remain hard. Energy "
         "storage and sunlight capture define the field.")
DOC_B = ("Microfluidic chips move tiny fluid volumes through etched channels. "
         "Microfluidic devices enable cheap diagnostics. Channels and pumps "
         "make microfluidic systems precise. Fluid control and channel design "
         "matter for diagnostics and for cooling electronics.")
DOCS = [{"id": "d1", "title": "Photosynthesis review", "text": DOC_A,
         "source_url": "https://example.org/a"},
        {"id": "d2", "title": "Microfluidics review", "text": DOC_B,
         "source_url": "https://example.org/b"}]


def test_end_to_end_briefs_with_provenance():
    out = ip.run({"as_of": "2026-10-12", "documents": DOCS, "max_briefs": 5})
    assert out["coverage"]["documents_supplied"] == 2
    assert out["coverage"]["universal_coverage"] is False
    assert out["briefs"]
    for b in out["briefs"]:
        assert b["status"] == "hypothesis_for_owner_review"
        prov = b["provenance"]
        assert prov["documents"] and prov["spans"]
        for concept, spans in prov["spans"].items():
            for s in spans:
                assert s["doc"] in {"d1", "d2"} and s["end"] > s["start"]


def test_briefs_combine_cross_document_concepts():
    out = ip.run({"as_of": "2026-10-12", "documents": DOCS})
    for b in out["briefs"]:
        docs = b["provenance"]["documents"]
        assert len(docs) >= 2  # cross-document by construction


def test_graph_counts_deterministic():
    a = ip.run({"as_of": "2026-10-12", "documents": DOCS})
    b = ip.run({"as_of": "2026-10-12", "documents": DOCS})
    assert a["concept_graph"] == b["concept_graph"]
    assert [x["id"] for x in a["briefs"]] == [x["id"] for x in b["briefs"]]


def test_empty_docs_refused():
    with pytest.raises(ValueError, match="INVENT_REFUSED_BAD_TYPE:documents"):
        ip.run({"as_of": "2026-10-12", "documents": []})


def test_brief_cap_enforced():
    docs = [{"id": "d%d" % i, "title": "t", "text": (DOC_A + DOC_B) * 2}
            for i in range(4)]
    out = ip.run({"as_of": "2026-10-12", "documents": docs, "max_briefs": 3})
    assert len(out["briefs"]) <= 3
