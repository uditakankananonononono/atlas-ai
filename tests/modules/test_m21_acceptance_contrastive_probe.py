"""Exploratory evidence perturbation probes. No external-novelty claim."""
from app.modules.m21_claire.runtime.acceptance import evaluate
from app.modules.m21_claire.runtime.types import RunReport, ToolReceipt


CRITERIA = [{"kind":"tool_receipt", "tool":"lookup", "min_count":1}]


def receipt(**changes):
    return ToolReceipt(step=1, tool="lookup", arguments={"key":"k"}, ok=True, content={"value":"v"}, **changes)


def test_evidence_perturbations_reject_without_matching_success():
    report = RunReport(stop_reason="final", steps_used=2, final="done", receipts=[receipt()])
    assert evaluate(CRITERIA, report).accepted
    perturbations = [
        report.model_copy(update={"receipts":[]}),
        report.model_copy(update={"receipts":[receipt().model_copy(update={"ok":False})]}),
        report.model_copy(update={"receipts":[receipt().model_copy(update={"tool":"other"})]}),
        report.model_copy(update={"stop_reason":"model_unavailable"}),
    ]
    for changed in perturbations:
        assert not evaluate(CRITERIA, changed).accepted
    for final in ("I definitely finished!", "failed", "", "trust me without evidence"):
        assert evaluate(CRITERIA, report.model_copy(update={"final":final})).accepted


def test_duplicate_replayed_receipts_currently_count_as_two_characterization():
    # This demonstrates the present criterion is receipt-row count, not unique
    # effect count. Characterization only, not endorsement or a repaired bug.
    criteria = [{"kind":"tool_receipt", "tool":"lookup", "min_count":2}]
    original = receipt()
    replay = original.model_copy(update={"step":2, "replayed":True})
    report = RunReport(stop_reason="final", steps_used=3, receipts=[original, replay])
    verdict = evaluate(criteria, report)
    assert verdict.accepted and verdict.results[0]["observed"] == 2
