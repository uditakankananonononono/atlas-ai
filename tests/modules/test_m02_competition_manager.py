import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.modules.m02_competition_manager.lane_api import *
from app.modules.m02_competition_manager.models import ActionState, ApplicationStatus, StatusObservation

DOC = """Eligibility: Applicants must be enrolled in high school.
Required materials: submit an essay, transcript, and recommendation.
Application deadline: October 31, 2026 at 5:00 pm.
Rubric:
Scientific merit: 50%
Originality: 30%
Communication: 20%
"""

class Verifier:
    def __init__(self, valid=True): self.valid = valid
    def verify(self, approval_id, *, action_id, payload_digest):
        return self.valid and approval_id == "approval-1" and len(payload_digest) == 64

class Browser:
    def __init__(self, fail=False): self.fail = fail; self.calls = []
    def execute(self, action, target_url, payload):
        self.calls.append((action, target_url, payload))
        if self.fail: raise RuntimeError("browser failure")
        return {"receipt": "ABC123"}

class EvidenceVerifier:
    def __init__(self, answer=True): self.answer = answer
    def verify(self, action, evidence): return self.answer

def success_receipt(action):
    return {"action_id": action.id, "payload_digest": action.approved_digest,
            "outcome": "confirmed_success", "attempt_terminal": True,
            "source": "browser_readback", "external_reference": "receipt-1",
            "evidence": "portal readback captured"}

class ParserTests(unittest.TestCase):
    def test_grounded_extraction_and_rubric(self):
        facts = parse_competition_document(DOC, "rules-v1", url="https://example.test/rules")
        self.assertTrue(any(f.kind == "rule" for f in facts))
        materials = {f.value["name"] for f in facts if f.kind == "material"}
        self.assertEqual(materials, {"essay", "transcript", "recommendation"})
        deadline = next(f for f in facts if f.kind == "deadline")
        self.assertEqual(deadline.value, "2026-10-31T17:00:00+00:00")
        self.assertEqual(DOC[deadline.evidence.start:deadline.evidence.end], deadline.evidence.quote)
        self.assertEqual(validate_rubric(facts), {"total_weight_percent":100,"complete":True,"criteria_count":3})

    def test_bad_or_empty_input(self):
        with self.assertRaises(ValueError): parse_competition_document("", "s")
        facts = parse_competition_document("Deadline: February 30, 2026", "s")
        self.assertFalse(any(f.kind == "deadline" for f in facts))

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryCompetitionRepository(); self.manager = CompetitionManager(self.repo)
        self.ws = self.manager.create_workspace("comp-1", "Science Prize", [{"id":"rules-v1","text":DOC,"url":"https://example.test/rules"}])

    def test_workspace_has_grounded_checklist_and_completion(self):
        self.assertEqual(self.ws.status, ApplicationStatus.PREPARING)
        self.assertEqual(len(self.ws.checklist), 3)
        for item in self.ws.checklist:
            self.assertEqual(item.evidence_ids, ["rules-v1"])
            self.ws = self.manager.complete_item(self.ws.id, item.id, material_ref=f"drive://{item.id}")
        self.assertEqual(self.ws.status, ApplicationStatus.READY)
        self.assertEqual(len(self.ws.materials), 3)

    def test_dependency_enforcement(self):
        first = self.manager.add_checklist_item(self.ws.id, "Draft")
        second = self.manager.add_checklist_item(self.ws.id, "Review", dependency_ids={first.id})
        with self.assertRaisesRegex(ValueError, "incomplete dependencies"):
            self.manager.complete_item(self.ws.id, second.id)
        self.manager.complete_item(self.ws.id, first.id)
        result = self.manager.complete_item(self.ws.id, second.id)
        self.assertTrue(next(i for i in result.checklist if i.id == second.id).completed)

    def make_ready(self):
        ws = self.repo.get_workspace(self.ws.id)
        for item in ws.checklist: ws = self.manager.complete_item(ws.id, item.id)
        return ws

    def test_approval_bound_execution_and_submission(self):
        self.make_ready()
        staged = self.manager.stage_browser_action(self.ws.id, "submit_application", "https://example.test/apply", {"confirm":True})
        self.assertEqual(staged.state, ActionState.APPROVAL_REQUIRED)
        with self.assertRaises(PermissionError): self.manager.execute_action(staged.id, Browser())
        with self.assertRaises(PermissionError): self.manager.approve_action(staged.id, "wrong", Verifier())
        approved = self.manager.approve_action(staged.id, "approval-1", Verifier())
        self.assertEqual(approved.state, ActionState.APPROVED)
        browser = Browser(); returned = self.manager.execute_action(staged.id, browser)
        # New contract: an executor return value is retained but is NOT
        # independent site confirmation, so the attempt is EXECUTOR_RETURNED
        # (not SUCCEEDED) and the workspace stays STAGED until verified
        # reconciliation. (Old expectations SUCCEEDED/SUBMITTED replaced.)
        self.assertEqual(returned.state, ActionState.EXECUTOR_RETURNED)
        self.assertEqual(self.repo.get_workspace(self.ws.id).status, ApplicationStatus.STAGED)
        # Kept guards: return value retained; executor invoked exactly once.
        self.assertEqual(returned.result["receipt"], "ABC123")
        self.assertEqual(len(browser.calls), 1)
        # Kept end-to-end guard, new mechanism: verified reconciliation drives
        # the action to SUCCEEDED and the workspace to SUBMITTED.
        action = self.repo.get_action(staged.id)
        reconciled = self.manager.reconcile_action(staged.id, success_receipt(action), EvidenceVerifier())
        self.assertEqual(reconciled.state, ActionState.SUCCEEDED)
        self.assertEqual(self.repo.get_workspace(self.ws.id).status, ApplicationStatus.SUBMITTED)
        self.assertEqual(len(browser.calls), 1)

    def test_tampering_after_approval_is_rejected(self):
        self.make_ready(); staged = self.manager.stage_browser_action(self.ws.id, "fill_form", "https://example.test/apply", {"name":"U"})
        self.manager.approve_action(staged.id, "approval-1", Verifier())
        action = self.repo.get_action(staged.id); action.payload["name"] = "Attacker"; self.repo.save_action(action)
        with self.assertRaisesRegex(PermissionError, "changed after approval"):
            self.manager.execute_action(staged.id, Browser())

    def test_browser_failure_recorded(self):
        self.make_ready(); staged = self.manager.stage_browser_action(self.ws.id, "fill_form", "https://example.test/apply", {})
        self.manager.approve_action(staged.id, "approval-1", Verifier())
        browser = Browser(fail=True)
        # Kept guard: the executor exception still propagates to the caller.
        with self.assertRaises(RuntimeError): self.manager.execute_action(staged.id, browser)
        failed = self.repo.get_action(staged.id)
        # New contract: an executor raise can occur AFTER an external effect, so
        # the attempt is OUTCOME_UNKNOWN (not known FAILED) and the stored error
        # is a fixed sanitized marker, never the raw provider error.
        self.assertEqual(failed.state, ActionState.OUTCOME_UNKNOWN)
        self.assertEqual(failed.error, "executor raised; external outcome requires reconciliation")
        self.assertNotIn("browser failure", failed.error)
        # Kept guards: recorded in the lane repository (in-memory; not production durability).
        with self.assertRaises(PermissionError): self.manager.execute_action(staged.id, browser)
        self.assertEqual(len(browser.calls), 1)
        # Kept terminal-state guard, new mechanism: verified no-effect evidence
        # reconciles the attempt to terminal FAILED.
        receipt = success_receipt(failed); receipt["outcome"] = "confirmed_no_effect"
        resolved = self.manager.reconcile_action(staged.id, receipt, EvidenceVerifier())
        self.assertEqual(resolved.state, ActionState.FAILED)

    def test_status_monitor_history_and_terminal_guard(self):
        self.make_ready(); staged = self.manager.stage_browser_action(self.ws.id, "submit_application", "https://example.test/apply", {})
        self.manager.approve_action(staged.id, "approval-1", Verifier()); self.manager.execute_action(staged.id, Browser())
        # New contract: observations cannot advance a workspace through
        # submission; a SUBMITTED observation before reconciliation is refused.
        with self.assertRaises(PermissionError):
            self.manager.record_status_observation(StatusObservation(self.ws.id, ApplicationStatus.SUBMITTED, "portal", datetime(2026,11,2,tzinfo=timezone.utc), "Portal receipt"))
        action = self.repo.get_action(staged.id)
        self.manager.reconcile_action(staged.id, success_receipt(action), EvidenceVerifier())
        self.assertEqual(self.repo.get_workspace(self.ws.id).status, ApplicationStatus.SUBMITTED)
        # Kept guards (unchanged contract): observation history + terminal guard.
        accepted = StatusObservation(self.ws.id, ApplicationStatus.ACCEPTED, "portal", datetime(2026,11,2,tzinfo=timezone.utc), "Portal says accepted", "ABC")
        ws = self.manager.record_status_observation(accepted)
        self.assertEqual(ws.status, ApplicationStatus.ACCEPTED); self.assertEqual(self.manager.status_history(ws.id), [accepted])
        with self.assertRaisesRegex(ValueError, "terminal"):
            self.manager.record_status_observation(StatusObservation(ws.id, ApplicationStatus.REJECTED, "email", datetime(2026,11,3,tzinfo=timezone.utc), "Rejected"))

    def test_invalid_transition_and_http_only_url(self):
        # Kept guard, stronger class: callers can never self-declare submission.
        # It is now refused categorically (PermissionError, not ValueError)
        # because submission requires verified action reconciliation.
        with self.assertRaises(PermissionError): self.manager.transition(self.ws.id, ApplicationStatus.SUBMITTED)
        # Kept guard: invalid non-submission transitions still raise ValueError.
        with self.assertRaises(ValueError): self.manager.transition(self.ws.id, ApplicationStatus.ACCEPTED)
        self.make_ready()
        # Kept guard: https-only staging (unchanged contract).
        with self.assertRaisesRegex(ValueError, "https"):
            self.manager.stage_browser_action(self.ws.id, "fill_form", "http://unsafe.test", {})
        # Kept guard, extended: even from STAGED, where SUBMITTED is otherwise
        # a listed transition, manual submission is refused.
        self.manager.stage_browser_action(self.ws.id, "submit_application", "https://example.test/apply", {})
        self.assertEqual(self.repo.get_workspace(self.ws.id).status, ApplicationStatus.STAGED)
        with self.assertRaises(PermissionError): self.manager.transition(self.ws.id, ApplicationStatus.SUBMITTED)

if __name__ == "__main__": unittest.main()


def test_core_spec_cannot_self_attest_external_approval():
    from app.modules.m02_competition_manager.core_spec_round6 import CapabilityRequest, execute
    result = execute(65, CapabilityRequest(objective="Submit an application", inputs={"approved": True}))
    assert result.status == "approval_required"
    assert result.artifact["effect_executed"] is False
