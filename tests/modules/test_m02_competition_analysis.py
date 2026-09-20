import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.modules.m02_competition_manager.lane_api import (parse_competition_document, grounding_conflicts,
    checklist_dependency_order)
from app.modules.m02_competition_manager.models import ChecklistItem

class GroundingAnalysisTests(unittest.TestCase):
    def test_conflicting_deadlines_are_explicit(self):
        a = parse_competition_document("Application deadline: October 10, 2026", "official-page")
        b = parse_competition_document("Applications close October 12, 2026", "faq")
        conflicts = grounding_conflicts(a + b)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].kind, "deadline")
        self.assertEqual(conflicts[0].source_ids, ("faq", "official-page"))
        self.assertIn("2026-10-10", conflicts[0].values[0])

    def test_same_deadline_is_not_conflict(self):
        a = parse_competition_document("Deadline: 2026-10-10", "a")
        b = parse_competition_document("Applications close 2026-10-10", "b")
        self.assertEqual(grounding_conflicts(a + b), [])

    def test_conflicting_rubric_weight_is_explicit(self):
        a = parse_competition_document("Originality: 20%", "a")
        b = parse_competition_document("Originality: 30%", "b")
        conflict = grounding_conflicts(a + b)[0]
        self.assertEqual(conflict.kind, "rubric")
        self.assertEqual(conflict.values, (20, 30))

    def test_dependency_order(self):
        draft = ChecklistItem("Draft", id="a")
        review = ChecklistItem("Review", id="b", dependency_ids={"a"})
        submit = ChecklistItem("Submit", id="c", dependency_ids={"b"})
        self.assertEqual(checklist_dependency_order([submit, review, draft]), ["a", "b", "c"])

    def test_dependency_cycle_rejected(self):
        a = ChecklistItem("A", id="a", dependency_ids={"b"})
        b = ChecklistItem("B", id="b", dependency_ids={"a"})
        with self.assertRaisesRegex(ValueError, "cycle"):
            checklist_dependency_order([a, b])

    def test_unknown_dependency_rejected(self):
        a = ChecklistItem("A", id="a", dependency_ids={"missing"})
        with self.assertRaisesRegex(ValueError, "unknown"):
            checklist_dependency_order([a])

if __name__ == "__main__": unittest.main()
