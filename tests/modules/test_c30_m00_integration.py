"""c30.policy <-> m00 approval center integration tests (auditor-4 R3 item 4).

Runs the REAL lazy m00 path: execute() with no injected consume, over a real
m00 Service backed by in-memory sqlite. Covers happy path, wrong status,
payload tamper, consumed-approval reuse, expiry and state drift.
Skipped only if sqlalchemy is unavailable.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.core.database import Base
    from app.core.models import ApprovalStatus
    from app.modules.c30 import policy
    from app.modules.m00_approval_center import impact, service as m00_service
    _OK = True
except ImportError:  # pragma: no cover
    _OK = False


@unittest.skipUnless(_OK, "sqlalchemy not available")
class M00Integration(unittest.TestCase):
    def setUp(self):
        from datetime import datetime, timezone
        engine = create_engine("sqlite+pysqlite:///:memory:",
                               connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.now = [datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)]
        self.svc = m00_service.Service(
            session_factory=sessionmaker(bind=engine, expire_on_commit=False),
            clock=lambda: self.now[0])
        self.descriptor = policy.bind_spend(
            tenant_id="u1", module_id=24, merchant="Acme", item="domain",
            amount=12.5, currency="USD", quantity=1, fees=0.0,
            undo_terms="refundable 30d", effect_id="eff-1")

    def _submit(self, payload=None, ttl=None):
        return self.svc.submit(module_id=24, action_type="spend",
                               payload=payload if payload is not None else self.descriptor["payload"],
                               user_id="u1", ttl_seconds=ttl)

    def test_happy_path_real_consume(self):
        view = self._submit()
        self.svc.decide(view["id"], ApprovalStatus.APPROVED, decided_by="her")
        out = policy.execute(self.descriptor, view["id"], actor="her", service=self.svc)
        self.assertTrue(out["allowed"])
        self.assertEqual(out["effect_id"], "eff-1")
        # identical re-execution is the idempotent replay, not a second effect
        out2 = policy.execute(self.descriptor, view["id"], actor="her", service=self.svc)
        self.assertTrue(out2["allowed"])

    def test_pending_status_rejected(self):
        view = self._submit()
        with self.assertRaises(m00_service.ApprovalConflictError):
            policy.execute(self.descriptor, view["id"], actor="her", service=self.svc)

    def test_tampered_payload_rejected(self):
        view = self._submit()
        self.svc.decide(view["id"], ApprovalStatus.APPROVED, decided_by="her")
        tampered = policy.bind_spend(
            tenant_id="u1", module_id=24, merchant="Acme", item="domain",
            amount=999.0, currency="USD", quantity=1, fees=0.0,  # changed cost
            undo_terms="refundable 30d", effect_id="eff-2")
        with self.assertRaises(m00_service.ApprovalConflictError) as cm:
            policy.execute(tampered, view["id"], actor="her", service=self.svc)
        self.assertIn("does not match", str(cm.exception))

    def test_consumed_effect_id_reuse_rejected(self):
        view = self._submit()
        self.svc.decide(view["id"], ApprovalStatus.APPROVED, decided_by="her")
        policy.execute(self.descriptor, view["id"], actor="her", service=self.svc)
        with self.assertRaises(m00_service.ApprovalConflictError) as cm:
            policy.execute(self.descriptor, view["id"], actor="her",
                           effect_id="eff-other", service=self.svc)
        self.assertIn("already been consumed", str(cm.exception))

    def test_expired_pending_decision_rejected(self):
        from datetime import timedelta
        view = self._submit(ttl=60)
        self.now[0] = self.now[0] + timedelta(hours=2)
        # m00 semantics: expiry gates the DECISION window of pending rows
        with self.assertRaises(m00_service.ApprovalConflictError):
            self.svc.decide(view["id"], ApprovalStatus.APPROVED, decided_by="her")
        self.assertEqual(self.svc.get(view["id"])["status"], "expired")
        with self.assertRaises(m00_service.ApprovalConflictError):
            policy.execute(self.descriptor, view["id"], actor="her", service=self.svc)

    def test_expired_approved_refused(self):
        from datetime import timedelta
        # Canonical semantics (auditor-4 ruling): an approved grant past
        # expires_at refuses at atomic permit consumption.
        view = self._submit(ttl=60)
        self.svc.decide(view["id"], ApprovalStatus.APPROVED, decided_by="her")
        self.now[0] = self.now[0] + timedelta(hours=2)
        with self.assertRaises(m00_service.ApprovalConflictError) as cm:
            policy.execute(self.descriptor, view["id"], actor="her", service=self.svc)
        self.assertEqual(str(cm.exception), "approval has expired")

    def test_idempotent_receipt_survives_expiry(self):
        from datetime import timedelta
        # consumed before expiry: the receipt is still returned after expiry
        view = self._submit(ttl=60)
        self.svc.decide(view["id"], ApprovalStatus.APPROVED, decided_by="her")
        first = policy.execute(self.descriptor, view["id"], actor="her", service=self.svc)
        self.now[0] = self.now[0] + timedelta(hours=2)
        again = policy.execute(self.descriptor, view["id"], actor="her", service=self.svc)
        self.assertTrue(again["allowed"])
        self.assertEqual(again["consumed_at"], first["consumed_at"])

    def test_state_drift_blocks_consume(self):
        registry = impact.ProbeRegistry()
        state = {"price": 12.5}
        registry.register("spend", lambda payload: dict(state), module_id=24)
        view = self._submit()
        impact.capture_review_state(self.svc, view["id"], registry=registry)
        self.svc.decide(view["id"], ApprovalStatus.APPROVED, decided_by="her")
        state["price"] = 15.0  # external state moved since review
        with self.assertRaises(impact.StateDriftError):
            policy.execute(self.descriptor, view["id"], actor="her",
                           service=self.svc, registry=registry)

    def test_hard_class_never_reaches_m00(self):
        d = {"class": "trade", "module_id": 24, "tenant_id": "u1",
             "action_type": "x", "payload": {}}
        view = self._submit()
        self.svc.decide(view["id"], ApprovalStatus.APPROVED, decided_by="her")
        with self.assertRaises(ValueError) as cm:
            policy.execute(d, view["id"], actor="her", service=self.svc)
        self.assertEqual(str(cm.exception), "POLICY_REFUSED_TRADE")

    def test_lazy_default_service_path(self):
        # auditor-4's scenario (adapted): execute with neither service nor
        # consume resolves m00 default_service lazily.
        import unittest.mock as mock
        with mock.patch.object(m00_service, "default_service",
                               side_effect=lambda: self.svc):
            view = self._submit()
            self.svc.decide(view["id"], ApprovalStatus.APPROVED, decided_by="her")
            result = policy.execute(self.descriptor, view["id"], actor="her")
            self.assertTrue(result["allowed"])


if __name__ == "__main__":
    unittest.main()
