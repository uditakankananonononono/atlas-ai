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
        browser = Browser(); finished = self.manager.execute_action(staged.id, browser)
        self.assertEqual(finished.state, ActionState.SUCCEEDED)
        self.assertEqual(finished.result["receipt"], "ABC123")
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
        with self.assertRaises(RuntimeError): self.manager.execute_action(staged.id, Browser(fail=True))
        failed = self.repo.get_action(staged.id)
        self.assertEqual(failed.state, ActionState.FAILED); self.assertEqual(failed.error, "browser failure")

    def test_status_monitor_history_and_terminal_guard(self):
        self.make_ready(); staged = self.manager.stage_browser_action(self.ws.id, "submit_application", "https://example.test/apply", {})
        self.manager.approve_action(staged.id, "approval-1", Verifier()); self.manager.execute_action(staged.id, Browser())
        accepted = StatusObservation(self.ws.id, ApplicationStatus.ACCEPTED, "portal", datetime(2026,11,2,tzinfo=timezone.utc), "Portal says accepted", "ABC")
        ws = self.manager.record_status_observation(accepted)
        self.assertEqual(ws.status, ApplicationStatus.ACCEPTED); self.assertEqual(self.manager.status_history(ws.id), [accepted])
        with self.assertRaisesRegex(ValueError, "terminal"):
            self.manager.record_status_observation(StatusObservation(ws.id, ApplicationStatus.REJECTED, "email", datetime(2026,11,3,tzinfo=timezone.utc), "Rejected"))

    def test_invalid_transition_and_http_only_url(self):
        with self.assertRaises(ValueError): self.manager.transition(self.ws.id, ApplicationStatus.SUBMITTED)
        self.make_ready()
        with self.assertRaisesRegex(ValueError, "https"):
            self.manager.stage_browser_action(self.ws.id, "fill_form", "http://unsafe.test", {})

if __name__ == "__main__": unittest.main()
