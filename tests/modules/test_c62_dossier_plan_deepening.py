"""Row 62 deepening (c32 dossier, c31 replicate_plan): exact-value tests for behaviors the s27/s12 tests did not pin.
Offline; nothing is fetched."""
from app.modules.c31 import replicate_plan as rp
from app.modules.c32 import dossier as dz


def test_dossier_caps_facts_per_dimension_and_counts_only_kept_citations():
    text = " ".join("Ada Lovelace founded company number %d." % i for i in range(12))
    out = dz.dossier("Ada Lovelace", [{"url": "https://example.org/a", "text": text}])
    assert len(out["dimensions"]["career"]) == dz.MAX_FACTS_PER_DIM == 8
    assert len(out["dimensions"]["ventures"]) == 8
    assert out["citation_count"] == 16


def test_dossier_recognition_keywords_each_count():
    for kw in ("award", "recognition", "prize", "ranked", "honor"):
        out = dz.dossier("Ada Lovelace", [{"url": "https://example.org/a", "text": "Ada Lovelace got an %s." % kw}])
        assert list(out["dimensions"]) == ["recognition"], kw
        assert out["completeness"] == 0.2


def test_plan_bsd_is_open_gpl_is_not_and_unknown_defaults_to_build():
    out = rp.plan([{"name": "a", "license": "bsd", "capabilities": ["x"]},
                   {"name": "b", "license": "gpl", "capabilities": ["x"]},
                   {"name": "c", "capabilities": ["x"]},
                   {"name": "d", "license": "mit", "capabilities": ["x"]},
                   {"name": "e", "license": "apache", "capabilities": ["x"]}])
    routes = {t["tool"]: t["route"] for t in out["tickets"]}
    assert routes == {"a": "integrate", "b": "build_ourselves", "c": "build_ourselves", "d": "integrate", "e": "integrate"}
    assert out["integrate_count"] == 3 and out["build_ourselves_count"] == 2


def test_plan_merges_duplicate_capabilities_per_tool():
    out = rp.plan([{"name": "a", "license": "mit", "capabilities": ["x", "x", "y"]}])
    assert [t["capability"] for t in out["tickets"]] == ["x", "y"] and out["ticket_count"] == 2
