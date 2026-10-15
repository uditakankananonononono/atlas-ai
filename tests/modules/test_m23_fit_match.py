"""M23 school-fit program matching: whole-word goal matching and the stated basis of the band."""
import ast, pathlib, sys, unittest
REPO = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))
from app.modules.m23_study_abroad._fit_match import program_match, FIT_BASIS

SVC = REPO / "backend/app/modules/m23_study_abroad/service.py"


def legacy(goal_text, program):
    """Independent copy of the OLD rule, kept only to show what changed."""
    g, p = goal_text.lower(), program.lower()
    return 1 if p in g or any(w in p for w in g.split()) else 0


class Match(unittest.TestCase):
    def test_short_filler_words_no_longer_match_any_program(self):
        goals = ["become a doctor"]
        self.assertEqual(legacy("become a doctor", "Art History"), 1)  # old false positive
        self.assertEqual(program_match(goals, ["Art History"]), 0)

    def test_exact_program_words_match(self):
        self.assertEqual(program_match(["computer science"], ["Computer Science"]), 1)
        self.assertEqual(program_match(["biology research"], ["Marine Biology"]), 1)

    def test_substring_inside_other_word_does_not_match(self):
        self.assertEqual(legacy("biology", "Biologyx Studies"), 1)
        self.assertEqual(program_match(["biology"], ["Biologyx Studies"]), 0)
        self.assertEqual(program_match(["art"], ["Smart Systems"]), 0)

    def test_punctuation_and_case_ignored(self):
        self.assertEqual(program_match(["Computer-Science, AI!"], ["computer science"]), 1)

    def test_short_whole_program_name_matches_as_phrase(self):
        self.assertEqual(program_match(["ai ethics"], ["AI"]), 1)
        self.assertEqual(program_match(["paint"], ["AI"]), 0)

    def test_goal_word_length_threshold_is_four(self):
        self.assertEqual(program_match(["data"], ["Data Science"]), 1)
        self.assertEqual(program_match(["art"], ["Art History"]), 0)
        self.assertEqual(program_match(["become a doctor"], ["Plan A Studies"]), 0)

    def test_empty_inputs_zero(self):
        self.assertEqual(program_match([], ["Physics"]), 0)
        self.assertEqual(program_match(["physics"], []), 0)
        self.assertEqual(program_match([""], [""]), 0)

    def test_best_over_programs(self):
        self.assertEqual(program_match(["physics"], ["Art", "Applied Physics"]), 1)

    def test_basis_statement_disclaims_admission_likelihood(self):
        self.assertIn("not an admission", FIT_BASIS)
        self.assertIn("budget", FIT_BASIS)


class Wiring(unittest.TestCase):
    def test_service_fit_uses_helper_and_emits_basis(self):
        src = SVC.read_text()
        self.assertIn("program_match(", src)
        self.assertIn("FIT_BASIS", src)
        self.assertIn("'basis':FIT_BASIS", src.replace('"', "'").replace(" ", ""))
        ast.parse(src)

    def test_essay_coaching_states_cliche_check_scope(self):
        src = SVC.read_text()
        self.assertIn("cliche_check_scope", src)


if __name__ == "__main__":
    unittest.main()
