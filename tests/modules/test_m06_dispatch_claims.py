"""Real SQLAlchemy/SQLite claim transactions plus isolated real Scheduler tests.

No live provider, FastAPI, M00 or full SqlSocialRepository import is exercised.
"""
import copy
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Column, JSON, MetaData, String, Table, create_engine, event, insert, select, update
from sqlalchemy.orm import sessionmaker

from app.modules.m06_social_media_manager.dispatch_claims import (
    claim_sql_schedule, claim_table, DispatchClaimSchemaError)
from app.modules.m06_social_media_manager.scheduler import (
    Scheduler, ScheduleEntry, ScheduleStateError, _ApprovalAuthority)
from app.modules.m06_social_media_manager.models import Platform
from app.modules.m06_social_media_manager.review_binding import publish_snapshot
from app.modules.m06_social_media_manager.adapters import PublishResult


def data(entry):
    return json.loads(json.dumps(asdict(entry), default=lambda v: v.isoformat()))


class ClaimTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.temp.name) / 'claims.db'))
        self.sessions = sessionmaker(bind=self.engine)
        meta = MetaData()
        self.table = Table('schedules', meta,
                           Column('tenant_id', String, primary_key=True),
                           Column('item_id', String, primary_key=True),
                           Column('status', String), Column('data', JSON))
        self.claims = claim_table(meta)
        self.assertIs(self.claims, claim_table(meta))
        meta.create_all(self.engine)
        self.entry = ScheduleEntry('s', 'p', Platform.LINKEDIN, 'article_post', 'Synthetic',
                                   datetime(2026, 10, 15, tzinfo=timezone.utc), 'a', status='approved',
                                   publish_target={'platform':'linkedin','account_id':'123'})
        self.seed('owner', data(self.entry))

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def seed(self, tenant, expected):
        with self.engine.begin() as db:
            db.execute(insert(self.table).values(tenant_id=tenant, item_id=expected['id'],
                                                status=expected['status'], data=expected))

    def claim(self, expected=None, tenant='owner'):
        return claim_sql_schedule(self.sessions, self.table, self.claims, tenant,
                                  expected if expected is not None else data(self.entry))

    def stored(self):
        with self.engine.connect() as db:
            return db.execute(select(self.table.c.data).where(
                self.table.c.tenant_id == 'owner')).scalar_one()

    def claim_count(self):
        with self.engine.connect() as db:
            return len(db.execute(select(self.claims)).all())

    def test_commit_dispatching_before_return_and_never_claim_twice(self):
        self.assertTrue(self.claim())
        self.assertEqual(self.stored()['status'], 'dispatching')
        self.assertEqual(self.stored()['failure'], 'publish_outcome_unconfirmed')
        self.assertFalse(self.claim())
        self.assertEqual(self.claim_count(), 1)

    def test_stale_payload_and_other_approval_refuse_without_ledger(self):
        for key, value in [('text', 'Changed'), ('approval_id', 'other'),
                           ('status', 'cancelled'), ('media_urls', ['https://example.invalid/a'])]:
            expected = data(self.entry)
            expected[key] = value
            self.assertFalse(self.claim(expected), key)
        self.assertEqual(self.claim_count(), 0)
        self.assertEqual(self.stored()['status'], 'approved')

    def test_missing_and_foreign_tenant_cannot_claim(self):
        self.assertFalse(self.claim(tenant='other'))
        expected = data(self.entry); expected['id'] = 'absent'
        self.assertFalse(self.claim(expected))
        self.assertEqual(self.claim_count(), 0)

    def test_same_schedule_id_different_tenants_independent(self):
        self.seed('other', data(self.entry))
        self.assertTrue(self.claim())
        self.assertTrue(self.claim(tenant='other'))
        self.assertEqual(self.claim_count(), 2)

    def test_ledger_prevents_replay_even_if_stale_writer_restores_approved(self):
        self.assertTrue(self.claim())
        expected = data(self.entry); expected['approval_id'] = 'new-review'
        with self.engine.begin() as db:
            db.execute(update(self.table).values(status='approved', data=expected))
        self.assertFalse(self.claim(expected))
        self.assertEqual(self.claim_count(), 1)

    def test_two_workers_read_same_row_only_one_claim_commits(self):
        barrier = threading.Barrier(2)
        def both_read(conn, cursor, statement, params, context, many):
            if statement.startswith('SELECT CAST('):
                barrier.wait(timeout=5)
        event.listen(self.engine, 'after_cursor_execute', both_read)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(lambda _: self.claim(), range(2)))
        finally:
            event.remove(self.engine, 'after_cursor_execute', both_read)
        self.assertEqual(sorted(outcomes), [False, True])
        self.assertEqual(self.claim_count(), 1)

    def test_changed_after_read_cas_rolls_back_claim(self):
        changed = False
        def mutate(conn, cursor, statement, params, context, many):
            nonlocal changed
            if statement.startswith('INSERT INTO m06_social_dispatch_claims') and not changed:
                changed = True
                new = dict(data(self.entry), text='Changed after read')
                with self.engine.begin() as other:
                    other.execute(update(self.table).values(data=new))
        event.listen(self.engine, 'before_cursor_execute', mutate)
        try:
            self.assertFalse(self.claim())
        finally:
            event.remove(self.engine, 'before_cursor_execute', mutate)
        self.assertEqual(self.claim_count(), 0)
        self.assertEqual(self.stored()['text'], 'Changed after read')
        # Losing CAS must not leave an orphan ledger that prevents a new review.
        self.assertTrue(self.claim(self.stored()))

    def test_commit_failure_never_returns_permission(self):
        def fail(session):
            raise RuntimeError('synthetic commit failure')
        event.listen(self.sessions, 'before_commit', fail)
        try:
            with self.assertRaisesRegex(RuntimeError, 'commit failure'):
                self.claim()
        finally:
            event.remove(self.sessions, 'before_commit', fail)
        self.assertEqual(self.claim_count(), 0)
        self.assertEqual(self.stored()['status'], 'approved')

    def test_same_approval_cannot_authorize_second_schedule(self):
        second = dict(data(self.entry), id='second-schedule')
        self.seed('owner', second)
        self.assertTrue(self.claim())
        self.assertFalse(self.claim(second))
        self.assertEqual(self.claim_count(), 1)
        with self.engine.connect() as db:
            statuses = dict(db.execute(select(self.table.c.item_id, self.table.c.status)).all())
        self.assertEqual(statuses, {'s': 'dispatching', 'second-schedule': 'approved'})

    def test_independently_reviewed_schedules_can_both_claim(self):
        second = dict(data(self.entry), id='second-schedule', approval_id='separate-approval')
        self.seed('owner', second)
        self.assertTrue(self.claim())
        self.assertTrue(self.claim(second))
        self.assertEqual(self.claim_count(), 2)

    def test_two_workers_different_schedule_same_approval_only_one_commits(self):
        second = dict(data(self.entry), id='second-schedule')
        self.seed('owner', second)
        barrier = threading.Barrier(2)
        def both_read(conn, cursor, statement, params, context, many):
            if statement.startswith('SELECT CAST('): barrier.wait(timeout=5)
        event.listen(self.engine, 'after_cursor_execute', both_read)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(self.claim, [data(self.entry), second]))
        finally:
            event.remove(self.engine, 'after_cursor_execute', both_read)
        self.assertEqual(sorted(outcomes), [False, True])
        self.assertEqual(self.claim_count(), 1)

    def legacy_claim_table(self):
        self.claims.drop(self.engine)
        old = Table(self.claims.name, MetaData(),
                    Column('tenant_id', String), Column('schedule_id', String),
                    Column('approval_id', String))
        old.create(self.engine)
        return old

    def test_preexisting_ledger_without_constraint_disables_claims(self):
        self.legacy_claim_table()
        with self.assertRaisesRegex(DispatchClaimSchemaError, 'explicit migration'):
            self.claim()
        self.assertEqual(self.claim_count(), 0)
        self.assertEqual(self.stored()['status'], 'approved')

    def test_preexisting_duplicate_approvals_not_deleted_or_grandfathered(self):
        old = self.legacy_claim_table()
        with self.engine.begin() as db:
            db.execute(insert(old), [dict(tenant_id='owner', schedule_id='old-first', approval_id='a'),
                                     dict(tenant_id='owner', schedule_id='old-second', approval_id='a')])
        with self.assertRaises(DispatchClaimSchemaError): self.claim()
        self.assertEqual(self.claim_count(), 2)
        self.assertEqual(self.stored()['status'], 'approved')

    def scheduler(self, *, adapter_error=None, fail_save=False, claim_allowed=True):
        outer = self
        effects = []
        class Repo:
            def list_schedules(self):
                d = outer.stored()
                return [ScheduleEntry(**dict(d, platform=Platform(d['platform']),
                     publish_at=datetime.fromisoformat(d['publish_at']),
                     created_at=datetime.fromisoformat(d['created_at'])))]
            def get_schedule(self, key): return self.list_schedules()[0]
            def claim_publish(self, expected):
                return outer.claim(data(expected)) if claim_allowed else False
            def save_schedule(self, entry):
                if fail_save: raise RuntimeError('synthetic receipt persistence failure')
                with outer.engine.begin() as db:
                    db.execute(update(outer.table).values(status=entry.status, data=data(entry)))
                return entry
            def save_publish_record(self, record): return record
        class Decisions:
            def status_of(self, key): return 'approved'
            def reviewed_payload(self, key): return {'publish_snapshot': publish_snapshot(outer.entry)}
        class Gate:
            def dispatch_outbound(self, action, declarations, **kwargs):
                return kwargs['effect'](action)
        class Adapter:
            async def account_identity(self): return {'platform':'linkedin','account_id':'123'}
            async def publish(self, request):
                effects.append(request)
                # Observe committed durable state at the precise effect boundary.
                outer.assertEqual(outer.stored()['status'], 'dispatching')
                if adapter_error: raise adapter_error
                return PublishResult(platform='linkedin', external_id='synthetic')
        class Factory:
            def for_platform(self, platform): return Adapter()
        s = Scheduler.__new__(Scheduler)
        s._repository = Repo(); s._decisions = Decisions(); s._enforcer = Gate()
        s._authority = _ApprovalAuthority(s._decisions); s._declarations = {}
        s._adapters = Factory(); s._clock = lambda: datetime(2026, 10, 17, tzinfo=timezone.utc)
        return s, effects

    def test_actual_scheduler_success_and_second_call_no_effect(self):
        s, effects = self.scheduler()
        self.assertEqual(len(s.execute_due()), 1)
        self.assertEqual(s.execute_due(), [])
        self.assertEqual(len(effects), 1)
        self.assertEqual(self.stored()['status'], 'published')

    def test_uncertain_adapter_exception_survives_restart_without_retry(self):
        s, effects = self.scheduler(adapter_error=RuntimeError('after-provider-write'))
        with self.assertRaisesRegex(RuntimeError, 'after-provider-write'): s.execute_due()
        self.assertEqual(len(effects), 1)
        self.assertEqual(self.stored()['status'], 'dispatching')
        restarted, next_effects = self.scheduler()
        self.assertEqual(restarted.execute_due(), [])
        self.assertEqual(next_effects, [])

    def test_receipt_save_failure_does_not_leave_republishable_approved_row(self):
        s, effects = self.scheduler(fail_save=True)
        with self.assertRaisesRegex(RuntimeError, 'receipt persistence'): s.execute_due()
        self.assertEqual(len(effects), 1)
        self.assertEqual(self.stored()['status'], 'dispatching')
        restarted, next_effects = self.scheduler()
        self.assertEqual(restarted.execute_due(), [])
        self.assertEqual(next_effects, [])

    def test_lost_claim_never_publishes_or_saves_stale_row(self):
        s, effects = self.scheduler(claim_allowed=False, fail_save=True)
        self.assertEqual(s.execute_due(), [])
        self.assertEqual(effects, [])
        self.assertEqual(self.stored()['status'], 'approved')

    def test_legacy_repository_without_claim_fails_closed(self):
        s, effects = self.scheduler()
        s._repository.claim_publish = None
        with self.assertRaisesRegex(ScheduleStateError, 'durable publish claims'): s.execute_due()
        self.assertEqual(effects, [])
        self.assertEqual(self.claim_count(), 0)

    def test_guardrail_failure_before_effect_does_not_burn_claim(self):
        s, effects = self.scheduler()
        class RefusingGate:
            def dispatch_outbound(self, *args, **kwargs):
                raise RuntimeError('gate stopped before effect')
        s._enforcer = RefusingGate()
        with self.assertRaisesRegex(RuntimeError, 'gate stopped'): s.execute_due()
        self.assertEqual(self.claim_count(), 0)
        self.assertEqual(self.stored()['status'], 'approved')
        self.assertEqual(effects, [])

    def test_scheduler_claim_commit_failure_cannot_select_adapter(self):
        s, effects = self.scheduler()
        def fail(session): raise RuntimeError('commit stopped')
        event.listen(self.sessions, 'before_commit', fail)
        try:
            with self.assertRaisesRegex(RuntimeError, 'commit stopped'): s.execute_due()
        finally:
            event.remove(self.sessions, 'before_commit', fail)
        self.assertEqual(effects, [])
        self.assertEqual(self.claim_count(), 0)

    def test_dispatching_schedule_cannot_cancel_reschedule_or_attach(self):
        s, _ = self.scheduler()
        self.assertTrue(self.claim())
        for action in [lambda: s.cancel('s'),
                       lambda: s.reschedule('s', datetime(2026, 10, 19, tzinfo=timezone.utc)),
                       lambda: s.attach_media('s', ['https://example.invalid/a'])]:
            with self.assertRaises(ScheduleStateError): action()
        self.assertEqual(self.stored()['status'], 'dispatching')


if __name__ == '__main__': unittest.main()
