"""m00 consume_effect expiry semantics (auditor-4 round-4 child work order).

Canonical permission semantics: an APPROVED grant past expires_at must refuse
at ATOMIC permit consumption (inside the consume transaction, race-safe),
while the effect-id idempotent receipt semantics are preserved.
"""
import pathlib
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.core.database import Base
    from app.core.models import ApprovalStatus
    from app.modules.m00_approval_center import service as m00_service
    _OK = True
except ImportError:  # pragma: no cover
    _OK = False


@unittest.skipUnless(_OK, "sqlalchemy not available")
class ConsumeExpiry(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite+pysqlite:///:memory:",
                               connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.now = [datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)]
        self.svc = m00_service.Service(
            session_factory=sessionmaker(bind=engine, expire_on_commit=False),
            clock=lambda: self.now[0])

    def _approved(self, ttl=60):
        view = self.svc.submit(module_id=24, action_type="spend",
                               payload={"a": 1}, user_id="u1", ttl_seconds=ttl)
        self.svc.decide(view["id"], ApprovalStatus.APPROVED, decided_by="her")
        return view["id"]

    def _consume(self, approval_id, effect_id="e1"):
        return self.svc.consume_effect(
            approval_id, module_id=24, action_type="spend",
            payload={"a": 1}, user_id="u1", effect_id=effect_id, actor="her")

    def test_approved_not_expired_consumes(self):
        aid = self._approved()
        result = self._consume(aid)
        self.assertTrue(result["allowed"])

    def test_approved_expired_refuses_atomically(self):
        aid = self._approved(ttl=60)
        self.now[0] = self.now[0] + timedelta(hours=2)
        with self.assertRaises(m00_service.ApprovalConflictError) as cm:
            self._consume(aid)
        self.assertEqual(str(cm.exception), "approval has expired")
        # nothing was consumed
        with self.assertRaises(m00_service.ApprovalConflictError):
            self._consume(aid, effect_id="e2")

    def test_expiry_boundary_refuses(self):
        # expires_at == now exactly is expired (<= semantics)
        aid = self._approved(ttl=60)
        self.now[0] = self.now[0] + timedelta(seconds=60)
        with self.assertRaises(m00_service.ApprovalConflictError) as cm:
            self._consume(aid)
        self.assertEqual(str(cm.exception), "approval has expired")

    def test_no_expiry_set_consumes_anytime(self):
        view = self.svc.submit(module_id=24, action_type="spend",
                               payload={"a": 1}, user_id="u1")
        self.svc.decide(view["id"], ApprovalStatus.APPROVED, decided_by="her")
        self.now[0] = self.now[0] + timedelta(days=365)
        self.assertTrue(self._consume(view["id"])["allowed"])

    def test_idempotent_receipt_survives_expiry(self):
        # consumed BEFORE expiry: the receipt must still be returned after
        # expiry (existing effect-id idempotent semantics preserved)
        aid = self._approved(ttl=60)
        first = self._consume(aid)
        self.now[0] = self.now[0] + timedelta(hours=2)
        again = self._consume(aid)
        self.assertTrue(again["allowed"])
        self.assertEqual(again["effect_id"], first["effect_id"])
        self.assertEqual(again["consumed_at"], first["consumed_at"])

    def test_consumed_then_expired_other_effect_still_consumed_conflict(self):
        # receipt check precedes expiry: a different effect_id on an
        # already-consumed grant reports the consumption, not the expiry
        aid = self._approved(ttl=60)
        self._consume(aid)
        self.now[0] = self.now[0] + timedelta(hours=2)
        with self.assertRaises(m00_service.ApprovalConflictError) as cm:
            self._consume(aid, effect_id="e2")
        self.assertEqual(str(cm.exception), "approval has already been consumed")

    def _file_service(self):
        # File-backed sqlite with per-session connections: real transaction
        # isolation for the race tests (in-memory StaticPool shares one
        # physical connection, which serializes into one transaction).
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        engine = create_engine(f"sqlite+pysqlite:///{tmp.name}",
                               connect_args={"check_same_thread": False, "timeout": 30})
        Base.metadata.create_all(engine)
        return m00_service.Service(
            session_factory=sessionmaker(bind=engine, expire_on_commit=False),
            clock=lambda: self.now[0])

    def test_clock_crosses_expiry_during_transaction(self):
        # auditor-4's controlled-clock defect repro (adapted): the entry clock
        # is stale - time crossing expires_at during fetch must still refuse.
        from unittest import mock
        aid = self._approved(ttl=60)
        real_fetch = m00_service.Service._fetch
        def delayed(self_, *a, **kw):
            row = real_fetch(self_, *a, **kw)
            self.now[0] = self.now[0] + timedelta(seconds=61)
            return row
        with mock.patch.object(m00_service.Service, "_fetch", delayed):
            with self.assertRaises(m00_service.ApprovalConflictError) as cm:
                self._consume(aid)
        self.assertIn("expired", str(cm.exception))

    def test_consumed_at_uses_refreshed_clock(self):
        # the refreshed in-transaction timestamp is what gets recorded/returned
        from unittest import mock
        aid = self._approved(ttl=120)
        real_fetch = m00_service.Service._fetch
        def delayed(self_, *a, **kw):
            row = real_fetch(self_, *a, **kw)
            self.now[0] = self.now[0] + timedelta(seconds=30)
            return row
        with mock.patch.object(m00_service.Service, "_fetch", delayed):
            result = self._consume(aid)
        self.assertTrue(result["allowed"])
        self.assertEqual(result["consumed_at"], self.now[0])

    def test_concurrent_expired_race_both_refuse(self):
        svc = self._file_service()
        view = svc.submit(module_id=24, action_type="spend", payload={"a": 1},
                          user_id="u1", ttl_seconds=60)
        svc.decide(view["id"], ApprovalStatus.APPROVED, decided_by="her")
        aid = view["id"]
        self.now[0] = self.now[0] + timedelta(hours=2)
        results = {}
        def worker(n):
            try:
                r = svc.consume_effect(
                    aid, module_id=24, action_type="spend", payload={"a": 1},
                    user_id="u1", effect_id=f"e{n}", actor="her")
                results[n] = ("ok", r)
            except m00_service.ApprovalConflictError as exc:
                results[n] = ("conflict", str(exc))
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(len(results), 4)
        for n, (kind, val) in results.items():
            self.assertEqual(kind, "conflict", f"thread {n} consumed past expiry: {val}")
            self.assertEqual(val, "approval has expired")

    def test_concurrent_valid_race_exactly_one_wins(self):
        svc = self._file_service()
        view = svc.submit(module_id=24, action_type="spend", payload={"a": 1},
                          user_id="u1")
        svc.decide(view["id"], ApprovalStatus.APPROVED, decided_by="her")
        aid = view["id"]
        results = {}
        lock = threading.Lock()
        def worker(n):
            try:
                r = svc.consume_effect(
                    aid, module_id=24, action_type="spend", payload={"a": 1},
                    user_id="u1", effect_id=f"e{n}", actor="her")
                with lock: results[n] = ("ok", r)
            except m00_service.ApprovalConflictError as exc:
                with lock: results[n] = ("conflict", str(exc))
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads: t.start()
        for t in threads: t.join()
        oks = [n for n, (k, _) in results.items() if k == "ok"]
        self.assertEqual(len(oks), 1, f"expected exactly one winner, got {results}")



if __name__ == "__main__":
    unittest.main()
