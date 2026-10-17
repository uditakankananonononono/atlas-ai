import asyncio
import copy
import unittest
from datetime import datetime

import httpx
from sqlalchemy import update

from app.modules.m06_social_media_manager.adapters import (
    AdapterAuthError, MetaGraphAdapter, LinkedInAdapter, XApiV2Adapter,
    TikTokContentPostingAdapter)
from app.modules.m06_social_media_manager.models import Platform
from app.modules.m06_social_media_manager.publish_targets import publish_target, valid_target
from app.modules.m06_social_media_manager.review_binding import publish_snapshot
import test_m06_dispatch_claims as claim_fixtures
from test_m06_dispatch_claims import data


class ProviderTargets(unittest.TestCase):
    def test_explicit_ig_and_linkedin_destination_ids_without_network(self):
        def no_network(request): self.fail('explicit destination does not need account lookup')
        transport = httpx.MockTransport(no_network)
        ig = MetaGraphAdapter(access_token='synthetic', ig_user_id='123', transport=transport)
        li = LinkedInAdapter(access_token='synthetic', organization_id='456', transport=transport)
        self.assertEqual(asyncio.run(ig.account_identity()), publish_target('instagram', '123'))
        self.assertEqual(asyncio.run(li.account_identity()), publish_target('linkedin', '456'))

    def test_x_reads_authenticated_subject_not_token_fingerprint(self):
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(200, json={'data': {'id': '123', 'username': 'synthetic'}})
        adapter = XApiV2Adapter(bearer_token='synthetic-not-an-account', transport=httpx.MockTransport(respond))
        self.assertEqual(asyncio.run(adapter.account_identity()), publish_target('twitter', '123'))
        self.assertEqual([(r.method, r.url.path) for r in calls], [('GET', '/2/users/me')])

    def test_x_unverifiable_or_partial_error_identity_fails_closed(self):
        for body in [{}, {'data': []}, {'data': {'id': 123}}, {'data': {'id': True}},
                     {'data': {'id': ''}}, {'data': {'id': 'a'}},
                     {'data': {'id': '123'}, 'errors': [{'title': 'forbidden'}]}]:
            with self.subTest(body=body):
                adapter = XApiV2Adapter(bearer_token='synthetic', transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, json=body)))
                with self.assertRaises(AdapterAuthError): asyncio.run(adapter.account_identity())

    def test_tiktok_uses_open_id_from_official_user_info(self):
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(200, json={'data': {'user': {'open_id': 'synthetic-open-id'}},
                                             'error': {'code': 'ok'}})
        adapter = TikTokContentPostingAdapter(access_token='synthetic', transport=httpx.MockTransport(respond))
        self.assertEqual(asyncio.run(adapter.account_identity()), publish_target('tiktok', 'synthetic-open-id'))
        self.assertEqual([(r.method, r.url.path) for r in calls], [('GET', '/v2/user/info/')])
        self.assertEqual(dict(calls[0].url.params), {'fields': 'open_id'})

    def test_tiktok_identity_requires_success_envelope_and_string_subject(self):
        for body in [{}, {'data': []}, {'data': {'user': []}, 'error': {'code': 'ok'}},
                     {'data': {'user': {'open_id': 'synthetic'}}},
                     {'data': {'user': {'open_id': 'synthetic'}}, 'error': {'code': 'denied'}},
                     {'data': {'user': {'open_id': 123}}, 'error': {'code': 'ok'}},
                     {'data': {'user': {'open_id': '  '}}, 'error': {'code': 'ok'}}]:
            with self.subTest(body=body):
                adapter = TikTokContentPostingAdapter(access_token='synthetic', transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, json=body)))
                with self.assertRaises(AdapterAuthError): asyncio.run(adapter.account_identity())

    def test_no_credentials_never_attempt_identity_network(self):
        def no_network(request): self.fail('missing credentials must not send')
        transport = httpx.MockTransport(no_network)
        for adapter in [MetaGraphAdapter(access_token=None, ig_user_id='123', transport=transport),
                        LinkedInAdapter(access_token=None, organization_id='123', transport=transport),
                        XApiV2Adapter(bearer_token=None, transport=transport),
                        TikTokContentPostingAdapter(access_token=None, transport=transport)]:
            with self.assertRaises(AdapterAuthError): asyncio.run(adapter.account_identity())

    def test_target_validation_rejects_platform_confusion_secret_fields_and_bad_ids(self):
        for target in [None, {}, {'platform': 'twitter', 'account_id': '123'},
                       {'platform': 'linkedin', 'account_id': 123},
                       {'platform': 'linkedin', 'account_id': '123', 'token': 'synthetic'},
                       {'platform': 'linkedin', 'account_id': '123\n'},
                       {'platform': 'linkedin', 'account_id': 'x' * 257}]:
            self.assertFalse(valid_target('linkedin', target))
        self.assertTrue(valid_target('linkedin', {'platform': 'linkedin', 'account_id': '123'}))


class AccountFlow(unittest.TestCase):
    def setUp(self):
        self.sql = claim_fixtures.ClaimTests(methodName='runTest')
        self.sql.setUp()
        self.addCleanup(self.sql.tearDown)

    def test_review_snapshot_copies_target_and_binds_exact_account(self):
        row = self.sql.entry
        snapshot = publish_snapshot(row)
        self.assertEqual(snapshot['version'], 2)
        row.publish_target['account_id'] = '456'
        self.assertEqual(snapshot['publish_target']['account_id'], '123')
        self.assertNotEqual(snapshot, publish_snapshot(row))

    def test_review_target_resolver_returns_detached_non_secret_identity(self):
        s, _ = self.sql.scheduler()
        target = {'platform': 'linkedin', 'account_id': '123'}
        class Adapter:
            async def account_identity(self): return target
        s._adapters.for_platform = lambda _: Adapter()
        resolved = s.resolve_publish_target(Platform.LINKEDIN)
        target['account_id'] = '456'
        self.assertEqual(resolved, {'platform': 'linkedin', 'account_id': '123'})

    def test_missing_legacy_target_requires_new_review_before_adapter_or_claim(self):
        self.sql.entry.publish_target = None
        with self.sql.engine.begin() as db:
            db.execute(update(self.sql.table).values(data=data(self.sql.entry)))
        s, effects = self.sql.scheduler()
        s._adapters.for_platform = lambda _: self.fail('legacy unbound target must not resolve at dispatch')
        self.assertEqual(s.execute_due(), [])
        self.assertEqual(effects, [])
        self.assertEqual(self.sql.claim_count(), 0)
        self.assertEqual(self.sql.stored()['status'], 'awaiting_approval')
        self.assertEqual(self.sql.stored()['approval_id'], '')

    def test_changed_current_account_invalidates_review_without_claim_or_post(self):
        s, effects = self.sql.scheduler()
        class ChangedAdapter:
            async def account_identity(self): return {'platform': 'linkedin', 'account_id': '456'}
            async def publish(self, request): raise AssertionError('wrong account must never publish')
        s._adapters.for_platform = lambda _: ChangedAdapter()
        self.assertEqual(s.execute_due(), [])
        self.assertEqual(effects, [])
        self.assertEqual(self.sql.claim_count(), 0)
        self.assertEqual(self.sql.stored()['status'], 'awaiting_approval')
        self.assertEqual(self.sql.stored()['failure'], 'publish_target_changed')

    def test_unverifiable_current_subject_fails_closed_without_secret_diagnostics(self):
        s, effects = self.sql.scheduler()
        class UnverifiedAdapter:
            async def account_identity(self): raise AdapterAuthError('synthetic-do-not-store-token')
            async def publish(self, request): raise AssertionError('must not publish')
        s._adapters.for_platform = lambda _: UnverifiedAdapter()
        self.assertEqual(s.execute_due(), [])
        self.assertEqual(effects, [])
        self.assertEqual(self.sql.claim_count(), 0)
        self.assertEqual(self.sql.stored()['failure'], 'publish_target_unverified')
        self.assertNotIn('synthetic-do-not-store-token', str(self.sql.stored()))

    def test_missing_identity_capability_cannot_publish(self):
        s, effects = self.sql.scheduler()
        s._adapters.for_platform = lambda _: object()
        self.assertEqual(s.execute_due(), [])
        self.assertEqual(effects, [])
        self.assertEqual(self.sql.claim_count(), 0)
        self.assertEqual(self.sql.stored()['failure'], 'publish_target_unverified')

    def test_same_captured_adapter_is_used_after_identity_read_not_factory_reload(self):
        s, _ = self.sql.scheduler()
        original = s._adapters.for_platform
        calls = []
        def once(platform):
            calls.append(platform)
            if len(calls) > 1: self.fail('must not reload changed env credentials after identity verification')
            return original(platform)
        s._adapters.for_platform = once
        self.assertEqual(len(s.execute_due()), 1)
        self.assertEqual(calls, [Platform.LINKEDIN])


if __name__ == '__main__': unittest.main()
