"""M23 identity-interview answer boundary: expected-question guard and HTTP error mapping."""
import ast, os, sys, tempfile, unittest, pathlib
HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
ROOT = REPO / "backend"
_tmp = tempfile.mkdtemp()
os.environ["ATLAS_DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "t.db")
sys.path.insert(0, str(ROOT))
from sqlalchemy import select, func
from app.core.database import SessionLocal
from app.modules.m23_study_abroad.interview import (
    IdentityInterviewRepository as Repo, IdentityTurnRow, IdentityInterviewRow)
from app.modules.m23_study_abroad import _http_boundary as hb
from app.modules.m23_study_abroad._commit_contract import (
    CommitOutcomeUnknown, IntegrityWriteError, UnclassifiedIntegrityError)

TEXT = "a concrete answer long enough"
MOD = ROOT / "app/modules/m23_study_abroad"


def turns(sid):
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(IdentityTurnRow).where(IdentityTurnRow.session_id == sid))


def index(sid):
    with SessionLocal() as db:
        return db.get(IdentityInterviewRow, sid).question_index


class ExpectedIndex(unittest.TestCase):
    def setUp(self):
        self.repo = Repo("tenant-a")
        self.sid = self.repo.start("college")["id"]

    def test_matching_expected_index_commits(self):
        v = self.repo.answer(self.sid, TEXT, expected_question_index=0)
        self.assertEqual(v["question_index"], 1)

    def test_late_duplicate_with_expected_index_is_rejected_without_write(self):
        self.repo.answer(self.sid, TEXT, expected_question_index=0)
        with self.assertRaises(ValueError) as cm:
            self.repo.answer(self.sid, TEXT, expected_question_index=0)
        self.assertIn("expected question", str(cm.exception))
        self.assertEqual(turns(self.sid), 1)
        self.assertEqual(index(self.sid), 1)

    def test_future_expected_index_rejected(self):
        with self.assertRaises(ValueError):
            self.repo.answer(self.sid, TEXT, expected_question_index=3)
        self.assertEqual(turns(self.sid), 0)

    def test_bad_expected_values_refused_before_any_read_write(self):
        for bad in (True, False, -1, 5, 1.0, "0", [0]):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self.repo.answer(self.sid, TEXT, expected_question_index=bad)
        self.assertEqual(turns(self.sid), 0)

    def test_out_of_range_message_names_valid_range(self):
        for bad in (-1, 5, 99):
            with self.assertRaises(ValueError) as cm:
                self.repo.answer(self.sid, TEXT, expected_question_index=bad)
            self.assertIn("0 to 4", str(cm.exception))

    def test_omitted_keeps_legacy_behaviour(self):
        self.repo.answer(self.sid, TEXT)
        v = self.repo.answer(self.sid, TEXT)
        self.assertEqual(v["question_index"], 2)

    def test_expected_index_checked_after_tenant_scope(self):
        other = Repo("tenant-b")
        with self.assertRaises(LookupError):
            other.answer(self.sid, TEXT, expected_question_index=0)

    def test_completed_interview_still_reports_complete(self):
        for i in range(5):
            self.repo.answer(self.sid, TEXT, expected_question_index=i)
        with self.assertRaises(ValueError) as cm:
            self.repo.answer(self.sid, TEXT, expected_question_index=4)
        self.assertIn("complete", str(cm.exception))
        self.assertEqual(turns(self.sid), 5)


class Mapper(unittest.TestCase):
    def test_commit_outcome_unknown(self):
        e = CommitOutcomeUnknown("x")
        e.__cause__ = RuntimeError("driver secret dsn=postgres://u:p@h/db")
        status, detail = hb.map_answer_error(e)
        self.assertEqual(status, 500)
        self.assertEqual(detail["code"], "commit_outcome_unknown")
        self.assertIn("read the interview", detail["message"].lower())
        self.assertNotIn("secret", repr(detail))
        self.assertNotIn("postgres", repr(detail))

    def test_integrity_classes(self):
        s1, d1 = hb.map_answer_error(IntegrityWriteError("x"))
        s2, d2 = hb.map_answer_error(UnclassifiedIntegrityError("x"))
        self.assertEqual((s1, d1["code"]), (500, "integrity_write_failed"))
        self.assertEqual((s2, d2["code"]), (500, "integrity_unclassified"))
        self.assertIn("not written", d1["message"])
        self.assertNotEqual(d1["message"], d2["message"])

    def test_existing_mappings_preserved(self):
        self.assertEqual(hb.map_answer_error(LookupError("s")), (404, "identity interview not found"))
        self.assertEqual(hb.map_answer_error(ValueError("bad")), (409, "bad"))

    def test_unknown_exception_not_swallowed(self):
        self.assertIsNone(hb.map_answer_error(KeyError("k")))
        self.assertIsNone(hb.map_answer_error(RuntimeError("k")))

    def test_commit_unknown_precedes_generic_runtime(self):
        self.assertIsNotNone(hb.map_answer_error(CommitOutcomeUnknown("x")))


class Wiring(unittest.TestCase):
    def test_route_uses_mapper_and_passes_expected_index(self):
        t = ast.parse((MOD / "routes.py").read_text())
        fn = next(n for n in ast.walk(t) if isinstance(n, ast.FunctionDef) and n.name == "answer_identity_interview")
        src = ast.unparse(fn)
        self.assertIn("map_answer_error", src)
        self.assertIn("expected_question_index", src)

    def test_schema_field_declared_optional_bounded(self):
        t = ast.parse((MOD / "schemas.py").read_text())
        cls = next(n for n in t.body if isinstance(n, ast.ClassDef) and n.name == "IdentityInterviewTurnIn")
        names = [n.target.id for n in cls.body if isinstance(n, ast.AnnAssign)]
        self.assertIn("expected_question_index", names)
        src = ast.unparse(cls)
        self.assertIn("None", src)
        self.assertIn("le=4", src)
        self.assertIn("StrictInt", src)

    def test_http_schema_rejects_coercible_values(self):
        try:
            import pydantic
        except ImportError:
            self.skipTest("pydantic not installed here; run in the project environment")
        try:
            from app.modules.m23_study_abroad.schemas import IdentityInterviewTurnIn as M
        except ImportError:
            self.skipTest("schema module needs the project environment")
        base = {"student_response": TEXT}
        for ok in (None, 0, 4):
            M(**base, expected_question_index=ok)
        M(**base)
        for bad in (True, False, "0", 1.0, -1, 5, [0]):
            with self.subTest(bad=bad):
                with self.assertRaises(pydantic.ValidationError):
                    M(**base, expected_question_index=bad)


if __name__ == "__main__":
    unittest.main()
