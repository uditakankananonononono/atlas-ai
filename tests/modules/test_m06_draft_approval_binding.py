"""Actual create_entries method, isolated finite repository, no effects."""
import unittest
from datetime import datetime, timezone
from app.modules.m06_social_media_manager.scheduler import Scheduler, ScheduleStateError
from app.modules.m06_social_media_manager.models import ContentPlan, Platform, PlatformDraft


class DraftApprovalBindings(unittest.TestCase):
    def setUp(self):
        self.saved = []
        saved = self.saved
        class Repo:
            def save_schedule(self, row): saved.append(row); return row
        self.scheduler = Scheduler.__new__(Scheduler); self.scheduler._repository = Repo()
        self.plan = ContentPlan('plan', 'Synthetic', [
            PlatformDraft(Platform.LINKEDIN, 'article_post', 'Synthetic first'),
            PlatformDraft(Platform.LINKEDIN, 'article_post', 'Synthetic second')],
            datetime(2026, 10, 15, tzinfo=timezone.utc))
        self.moment = datetime(2026, 10, 20, tzinfo=timezone.utc)

    def test_repeated_platform_drafts_keep_distinct_indexed_approvals(self):
        targets = {Platform.LINKEDIN: {'platform': 'linkedin', 'account_id': '123'}}
        rows = self.scheduler.create_entries(self.plan, publish_at=self.moment,
                    approval_ids={Platform.LINKEDIN: 'second-review'},
                    draft_approval_ids=['first-review', 'second-review'], publish_targets=targets)
        self.assertEqual([(r.text, r.approval_id) for r in rows], [
            ('Synthetic first', 'first-review'), ('Synthetic second', 'second-review')])
        self.assertEqual(len({r.id for r in rows}), 2)
        targets[Platform.LINKEDIN]['account_id'] = '456'
        self.assertEqual([r.publish_target['account_id'] for r in rows], ['123', '123'])

    def test_ambiguous_legacy_platform_map_refuses_before_any_save(self):
        with self.assertRaises(ScheduleStateError):
            self.scheduler.create_entries(self.plan, publish_at=self.moment,
                                          approval_ids={Platform.LINKEDIN: 'same-review'})
        self.assertEqual(self.saved, [])

    def test_missing_empty_reused_or_wrong_length_ids_refuse_before_any_save(self):
        for ids in [[], ['only-one'], ['first', 'second', 'extra'], ['', 'second'],
                    ['same', 'same'], [None, 'second'], [1, 'second']]:
            with self.subTest(ids=ids):
                with self.assertRaises(ScheduleStateError):
                    self.scheduler.create_entries(self.plan, publish_at=self.moment,
                                                  approval_ids={}, draft_approval_ids=ids)
                self.assertEqual(self.saved, [])

    def test_unique_platform_legacy_mapping_remains_supported(self):
        self.plan.drafts[1] = PlatformDraft(Platform.TWITTER, 'post', 'Synthetic second')
        rows = self.scheduler.create_entries(self.plan, publish_at=self.moment,
                        approval_ids={Platform.LINKEDIN: 'li-review', Platform.TWITTER: 'x-review'})
        self.assertEqual([r.approval_id for r in rows], ['li-review', 'x-review'])


if __name__ == '__main__': unittest.main()
