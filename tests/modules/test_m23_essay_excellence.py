"""m23.essay_excellence tests (row 98): rubric scoring, measured revision
improvement, package assembly with enforced student authorship."""
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "backend"))
from app.modules.m23_study_abroad import essay_excellence as x  # noqa: E402

WEAK = ("Since I was young I have always been passionate about science. "
        "It changed my life. At the end of the day science is great. "
        "I like it very much and it is very interesting to me and my school.")
STRONG = ("The first circuit I soldered at the Bangalore makerspace in March 2024 "
          "burned a hole through my thumb and the PCB. I rebuilt it eleven times "
          "before the LED stayed lit. I learned that iteration beats inspiration: "
          "each failed board taught me one specific thing about heat, solder or "
          "patience. Looking back, the scar is the certificate. I grew into someone "
          "who debugs before despairing, and the robotics team noticed - we won "
          "the regional finals with a robot I had redesigned three times. "
          "That is when I decided engineering was not a subject but a method. "
          "I still keep the first burned board on my desk.")

EVIDENCE = [{"id": "ev1", "description": "regional robotics finals winner 2024",
             "tags": ["robotics", "soldering", "iteration"]},
            {"id": "ev2", "description": "makerspace member since 2024",
             "tags": ["makerspace"]}]


def test_strong_draft_beats_weak_draft():
    weak = x.analyze_draft(WEAK, word_limit=650)
    strong = x.analyze_draft(STRONG, evidence=EVIDENCE, word_limit=650)
    assert strong["overall"] > weak["overall"]
    assert weak["stats"]["cliches_found"]  # cliches detected
    assert strong["criteria"]["specificity"] > weak["criteria"]["specificity"]
    assert strong["criteria"]["reflection"] >= weak["criteria"]["reflection"]


def test_revision_delta_measured():
    d = x.compare_revisions(WEAK, STRONG, evidence=EVIDENCE)
    assert d["overall_delta"] > 0
    assert "specificity" in d["improved"] or "originality" in d["improved"]
    assert d["measured"] is True


def test_evidence_linkage_uses_supplied_evidence():
    r = x.analyze_draft(STRONG, evidence=EVIDENCE)
    assert r["criteria"]["evidence_linkage"] is not None
    assert r["criteria"]["evidence_linkage"] > 0
    none = x.analyze_draft(STRONG, evidence=[])
    assert none["criteria"]["evidence_linkage"] is None


def test_over_limit_scores_zero_length_fit():
    long = "word " * 700
    r = x.analyze_draft(long, word_limit=650)
    assert r["criteria"]["length_fit"] == 0.0
    assert r["stats"]["within_limit"] is False


def test_package_requires_student_confirmation():
    college = {"name": "Example U", "prompts": [{"id": "p1", "prompt": "Why us?"}]}
    essays = [{"id": "e1", "prompt_id": "p1", "student_text": STRONG,
               "student_confirmed": False}]
    with pytest.raises(ValueError, match="ESSAY_REFUSED_STUDENT_AUTHORSHIP"):
        x.assemble_package(college, essays)


def test_package_completeness():
    college = {"name": "Example U",
               "prompts": [{"id": "p1", "prompt": "Why us?"},
                           {"id": "p2", "prompt": "Community"}]}
    essays = [{"id": "e1", "prompt_id": "p1", "student_text": STRONG,
               "student_confirmed": True}]
    out = x.assemble_package(college, essays,
                             analyses=[{"essay_id": "e1", "overall": 0.71}])
    assert out["status"] == "incomplete" and out["missing_prompts"] == ["p2"]
    assert out["submitted"] is False
    assert out["rubric_scores"] == {"e1": 0.71}
    full = x.assemble_package(
        college, essays + [{"id": "e2", "prompt_id": "p2", "student_text": STRONG,
                            "student_confirmed": True}])
    assert full["status"] == "complete"


def test_no_prose_generation_surface():
    assert not hasattr(x, "generate_essay") and not hasattr(x, "write_draft")
