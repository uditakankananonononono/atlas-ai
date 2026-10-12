"""Row 62 part b deepening: text-cleaning refusals in c37/patents.py. Offline."""
import copy, importlib.util, pathlib, sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
spec = importlib.util.spec_from_file_location("c37_patents_deep", ROOT / "backend/app/modules/c37/patents.py")
pat = importlib.util.module_from_spec(spec)
sys.modules["c37_patents_deep"] = pat
spec.loader.exec_module(pat)

BASE = {"as_of": "2026-10-01",
        "invention": {"id": "i1", "owner": "self", "title": "widget", "summary": "a widget",
                      "components": ["a frame", "a motor"], "novel_features": ["it folds"]},
        "prior_art": [{"id": "p1", "title": "Prior widget", "url": "https://example.org/p1"}], "novelty_input": None}


@pytest.mark.parametrize("bad", ["   ", "\t\n", "x\x00y", "x\u200by", "x\u2028y", "x\u2029y", ""])
@pytest.mark.parametrize("field", ["title", "summary", "id"])
def test_blank_or_control_text_is_refused_in_invention_fields(field, bad):
    req = copy.deepcopy(BASE)
    req["invention"][field] = bad
    with pytest.raises(ValueError, match="INTEL_REFUSED_BAD_TYPE"):
        pat.run(req)


def test_unicode_text_helper_refuses_blank_and_controls_directly():
    for bad in ("  ", "a\x00", "a\u200b", "a\u2028", "a\u2029"):
        with pytest.raises(ValueError):
            pat._unicode_text(bad, "title")
    assert pat._unicode_text("ok text", "title") == "ok text"
