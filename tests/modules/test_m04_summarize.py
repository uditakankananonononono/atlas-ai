"""RED-first tests for M04 deterministic extractive section summarization.

Spec: Module 4 - "New papers are summarised, embedded, and clustered" and the
hypothesis agent "extracts methods and findings". Rows 217/224 currently only
echo caller-supplied sections. This unit adds a heuristic sentence classifier
as an opt-in fallback, honestly labelled as heuristic derivation - not
LLM-quality summarization.
"""

import pytest

from app.modules.m04_research_scientist.expanded_211_258 import run as m4
from app.modules.m04_research_scientist.summarize import extract_sections

ABSTRACT = (
    "We investigate whether treatment X improves outcome Y in solid tumors. "
    "We measured outcome Y in a randomized cohort using weekly assays. "
    "Treatment X increased outcome Y significantly compared with control. "
    "However, the small sample size limits generalization."
)


def test_extract_sections_classifies_sentences():
    sections = extract_sections(ABSTRACT)
    assert "treatment X improves outcome Y" in sections["objective"]
    assert "measured outcome Y" in sections["methods"]
    assert "increased outcome Y significantly" in sections["findings"]
    assert "small sample size limits" in sections["limitations"]


def test_extract_sections_deterministic_and_heuristic_labelled():
    first = extract_sections(ABSTRACT)
    second = extract_sections(ABSTRACT)
    assert first == second
    assert set(first) == {"objective", "methods", "findings", "limitations"}


def test_extract_sections_rejects_empty_abstract():
    with pytest.raises(ValueError):
        extract_sections("")


def test_row217_falls_back_to_derived_sections_when_absent():
    out = m4(217, {"paper": {"id": "p1", "abstract": ABSTRACT}})
    result = out["result"]
    assert result["paper_id"] == "p1"
    assert result["sections_derived"] is True
    assert result["extraction_heuristic"] is True
    assert "measured outcome Y" in result["methods"]


def test_row217_caller_supplied_sections_still_win():
    out = m4(217, {"paper": {"id": "p1", "abstract": ABSTRACT},
                   "sections": {"objective": "o", "methods": "caller-m", "findings": "f", "limitations": "l"}})
    assert out["result"]["methods"] == "caller-m"
    assert out["result"].get("sections_derived") is not True


def test_row224_falls_back_to_derived_extraction():
    out = m4(224, {"paper": {"id": "p1", "abstract": ABSTRACT}})
    result = out["result"]
    assert result["extraction_heuristic"] is True
    assert "measured outcome Y" in result["methods"]
    assert "increased outcome Y significantly" in result["findings"]


def test_row224_without_abstract_or_sections_fails_closed():
    with pytest.raises((ValueError, KeyError)):
        m4(224, {"paper": {"id": "p1"}})


def test_extract_sections_significant_cue_classifies_findings():
    sections = extract_sections("The effect remained significant across subgroups.")
    assert "significant" in sections["findings"]


def test_extract_sections_leading_no_cue_defaults_to_objective():
    sections = extract_sections("Cats are great.")
    assert sections["objective"] == "Cats are great."


def test_extract_sections_nonleading_no_cue_sentence_dropped():
    sections = extract_sections("We investigate cats. Cats are great.")
    assert "Cats are great." not in sections["objective"]
    assert all("Cats are great." not in value for value in sections.values())


def test_extract_sections_rejects_non_string_abstract():
    with pytest.raises(ValueError):
        extract_sections(123)
    with pytest.raises(ValueError):
        extract_sections(["We investigate cats."])


def test_row217_empty_sections_dict_falls_back_to_derivation():
    out = m4(217, {"paper": {"id": "p1", "abstract": ABSTRACT}, "sections": {}})
    assert out["result"]["sections_derived"] is True


def test_extract_sections_first_nocue_while_objective_empty_becomes_objective():
    sections = extract_sections("We measured outcome Y. Cats are great.")
    assert sections["methods"].startswith("We measured")
    assert sections["objective"] == "Cats are great."


def test_row217_rejects_non_dict_paper():
    with pytest.raises(ValueError, match="paper must be an object"):
        m4(217, {"paper": 123})
    with pytest.raises(ValueError, match="paper must be an object"):
        m4(217, {"paper": "x", "sections": {}})


def test_row217_rejects_non_dict_sections():
    with pytest.raises(ValueError, match="sections must be an object"):
        m4(217, {"paper": {"id": "p1", "abstract": ABSTRACT}, "sections": "x"})


def test_row224_rejects_non_dict_paper():
    with pytest.raises(ValueError, match="paper must be an object"):
        m4(224, {"paper": 123})


def test_mounted_route_bad_field_types_return_422_not_500():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.m04_research_scientist.routes import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    url = "/research-scientist/expanded-211-258/{}"
    valid = {"paper": {"id": "p1", "abstract": ABSTRACT}}
    assert client.post(url.format(217), json=valid).status_code == 200
    assert client.post(url.format(217), json={"paper": 123}).status_code == 422
    assert client.post(url.format(217), json={**valid, "sections": "x"}).status_code == 422
    assert client.post(url.format(224), json={"paper": 123}).status_code == 422
    assert client.post(url.format(217), json={"paper": {"id": "p1", "abstract": 123}}).status_code == 422


def test_extract_sections_rejects_whitespace_abstract():
    # Survivor pin S1: `not abstract or not abstract.strip()` mutated to `and`
    # lets whitespace through, returning four empty sections (fail-open).
    with pytest.raises(ValueError, match="abstract is required"):
        extract_sections("   ")


def test_row217_whitespace_abstract_fails_closed():
    with pytest.raises(ValueError, match="abstract is required"):
        m4(217, {"paper": {"id": "p1", "abstract": "   "}})


def test_row224_whitespace_abstract_fails_closed():
    with pytest.raises(ValueError, match="abstract is required"):
        m4(224, {"paper": {"id": "p1", "abstract": "   "}})


def test_row224_methods_only_without_abstract_retains_caller_value():
    # Survivor pin S2: `methods or findings` mutated to `and` refuses here.
    r = m4(224, {"paper": {"id": "p1", "methods": "M only"}})["result"]
    assert r["methods"] == "M only" and r["findings"] is None
    assert "extraction_heuristic" not in r


def test_row224_findings_only_without_abstract_retains_caller_value():
    r = m4(224, {"paper": {"id": "p1", "findings": "F only"}})["result"]
    assert r["findings"] == "F only" and r["methods"] is None
    assert "extraction_heuristic" not in r


def test_row224_methods_and_abstract_caller_methods_win():
    # Caller-owned pin of EXACT base behavior: methods present -> first branch;
    # the abstract is NOT consulted (silently unused), no derivation keys.
    r = m4(224, {"paper": {"id": "p1", "methods": "Caller M",
                            "abstract": "We investigate cats. We found dogs."}})["result"]
    assert r["methods"] == "Caller M"
    assert r["findings"] is None
    assert "extraction_heuristic" not in r


def test_extract_sections_rejects_bytes_abstract():
    # Survivor pin S3: isinstance str mutated to (str, bytes) admits bytes,
    # which dies as TypeError inside re.split instead of failing closed.
    with pytest.raises(ValueError, match="must be a string"):
        extract_sections(b"We investigate cats.")
    with pytest.raises(ValueError, match="must be a string"):
        extract_sections(123)


def test_row217_missing_paper_fails_closed_with_reason():
    # Survivor pin E5: without _need(d,'paper'), {} gives KeyError and
    # paper=None gives the wrong reason ('paper must be an object').
    with pytest.raises(ValueError, match="missing required fields: paper"):
        m4(217, {})
    with pytest.raises(ValueError, match="missing required fields: paper"):
        m4(217, {"paper": None})


def test_row217_missing_abstract_fails_closed_with_reason():
    # Survivor pin E7: without _need(d['paper'],'abstract') this is a KeyError.
    with pytest.raises(ValueError, match="missing required fields: abstract"):
        m4(217, {"paper": {"id": "p"}})


def test_row224_missing_sections_and_abstract_fails_closed_with_reason():
    # Survivor pin E8: without the explicit raise, {} gives KeyError and
    # abstract=None mis-reports 'abstract must be a string'.
    with pytest.raises(ValueError, match="paper.methods/findings or paper.abstract required"):
        m4(224, {"paper": {"id": "p"}})
    with pytest.raises(ValueError, match="paper.methods/findings or paper.abstract required"):
        m4(224, {"paper": {"id": "p", "abstract": None}})


def test_extract_sections_aim_cue_classifies_objective():
    # Survivor pin S11: dropping the 'aim' cue drops the second sentence.
    out = extract_sections("We investigate cats. We aim to quantify them. We found dogs.")
    assert out["objective"] == "We investigate cats. We aim to quantify them."


# Reviewer-authored coverage completion: one classifying sentence per cue, so
# every single-cue deletion mutant is pinned (source-script site map).
# Pairs are LITERAL, not imported: importing _CUES would let a cue-deletion
# mutant shrink the parametrization to match itself.
ALL_CUES_LITERAL = (
    ("limitations", "limitation"),
    ("limitations", "however"),
    ("limitations", "caution"),
    ("limitations", "small sample"),
    ("limitations", "future work"),
    ("limitations", "limited"),
    ("limitations", "bias"),
    ("limitations", "confound"),
    ("findings", "found"),
    ("findings", "showed"),
    ("findings", "increased"),
    ("findings", "reduced"),
    ("findings", "decreased"),
    ("findings", "associated"),
    ("findings", "significant"),
    ("findings", "observed"),
    ("findings", "improved"),
    ("findings", "no effect"),
    ("findings", "correlated"),
    ("findings", "result"),
    ("methods", "measured"),
    ("methods", "method"),
    ("methods", "assay"),
    ("methods", "protocol"),
    ("methods", "cohort"),
    ("methods", "randomized"),
    ("methods", "randomised"),
    ("methods", "model"),
    ("methods", "sample"),
    ("methods", "workflow"),
    ("methods", "sequenc"),
    ("methods", "pipeline"),
    ("methods", "we used"),
    ("methods", "we performed"),
    ("objective", "we investigate"),
    ("objective", "aim"),
    ("objective", "objective"),
    ("objective", "purpose"),
    ("objective", "hypothes"),
    ("objective", "we ask"),
    ("objective", "goal"),
    ("objective", "whether"),
)

@pytest.mark.parametrize("section,cue", ALL_CUES_LITERAL)
def test_every_cue_individually_classifies(section, cue):
    out = extract_sections(f"We {cue} the cats.")
    assert out[section] == f"We {cue} the cats."


OBJECTIVE_CUE_SENTENCES = (
    ("we investigate", "We investigate further."),
    ("objective", "The objective is clear."),
    ("purpose", "The purpose is clear."),
    ("hypothes", "We hypothesize loudly."),
    ("we ask", "We ask why."),
    ("goal", "The goal is clear."),
    ("whether", "Whether it works is unknown."),
)

@pytest.mark.parametrize("cue,sentence", OBJECTIVE_CUE_SENTENCES)
def test_objective_cue_distinguishes_from_fallback(cue, sentence):
    # Reviewer-authored: the fallback masks objective-cue deletion when the
    # objective bucket is still empty; with it filled, a no-cue sentence is
    # dropped while a cued sentence joins objective. ('aim' covered by S11 pin.)
    out = extract_sections("Cats are great. " + sentence)
    assert out["objective"] == "Cats are great. " + sentence


def test_row232_need_results_missing_none_empty_fail_closed():
    # Peer-refuted C1 claim: _need(d,'results') in row 232 is NOT redundant.
    # Without it, missing key crashes KeyError and None/'' reach
    # descriptive_stats with a different reason; with it, all three fail
    # closed with the SAME 'missing required fields: results' reason.
    # Mutant record: removing _need(d,'results') survives v3 (rc0, 94P),
    # dies here (rc1, assertion).
    for payload in ({}, {"results": None}, {"results": ""}):
        with pytest.raises(ValueError, match="missing required fields: results"):
            m4(232, payload)


def test_extract_sections_u04_splits_on_exclamation_and_question_boundaries():
    # u04 survivor pin: the sentence split must treat ! and ? as boundaries,
    # not only '.'; a period-only mutant lumps both sentences together and
    # the first matching bucket (findings) swallows the methods sentence.
    s = extract_sections("We found cats! We measured dogs.")
    assert s["findings"] == "We found cats!"
    assert s["methods"] == "We measured dogs."
    q = extract_sections("We ask whether cats improve? We found dogs.")
    assert q["objective"] == "We ask whether cats improve?"
    assert q["findings"] == "We found dogs."


def test_row217_u24_caller_sections_branch_flags_claims_need_source_check():
    # u24 branch 1 (caller sections win): claims_need_source_check must be
    # True - caller-supplied sections are unverified claims.
    r = m4(217, {"paper": {"id": "p"}, "sections": {"objective": "O", "methods": "M"}})["result"]
    assert r["claims_need_source_check"] is True
    assert r["objective"] == "O"
    assert r["methods"] == "M"


def test_row217_u24_derived_branch_flags_claims_need_source_check():
    # u24 branch 2 (derived from abstract): claims_need_source_check must be
    # True - heuristic extraction never verifies claims.
    r = m4(217, {"paper": {"id": "p", "abstract": "We found cats."}})["result"]
    assert r["claims_need_source_check"] is True
    assert r["sections_derived"] is True


def test_row224_u23_caller_branch_keeps_limitations_none():
    # u23 survivor pin: the caller branch must keep limitations=None when the
    # caller omits it; a mutant dropping the key breaks the explicit-None
    # contract downstream consumers rely on.
    r = m4(224, {"paper": {"id": "p1", "methods": "M"}})["result"]
    assert "limitations" in r
    assert r["limitations"] is None
    assert r["methods"] == "M"
    assert r["findings"] is None


def test_row224_u31_need_paper_fails_closed_with_reason():
    # u31 survivor pin: removing _need(d,'paper') turns the shared
    # missing-fields contract into a KeyError crash; pin the exact reason
    # (the older broad test accepted any ValueError/KeyError, no match).
    with pytest.raises(ValueError, match="missing required fields: paper"):
        m4(224, {})
