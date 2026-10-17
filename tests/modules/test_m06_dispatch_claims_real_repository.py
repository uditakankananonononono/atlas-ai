"""Genuine SqlSocialRepository/Service smoke pins. Not locally executed here.

Run with normal project dependencies installed; no source or module shims.
All database work is redirected to a temporary SQLite engine before construction.
"""
from datetime import datetime, timezone
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.m06_social_media_manager import sql_repository as storage
from app.modules.m06_social_media_manager.scheduler import ScheduleEntry, ScheduleStateError
from app.modules.m06_social_media_manager.models import Platform
from app.modules.m06_social_media_manager.service import Service


class RealRepositoryClaims(unittest.TestCase):
    def test_real_repository_constructor_serializer_and_claim_wiring(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = create_engine('sqlite:///' + str(Path(folder) / 'actual-repository.db'))
            sessions = sessionmaker(bind=engine)
            try:
                with patch.object(storage, 'engine', engine):
                    repo = storage.SqlSocialRepository('synthetic-owner', sessions)
                    foreign = storage.SqlSocialRepository('synthetic-other', sessions)
                entry = ScheduleEntry('s', 'p', Platform.LINKEDIN, 'article_post', 'Synthetic',
                    datetime(2026, 10, 15, tzinfo=timezone.utc), 'a', status='approved')
                repo.save_schedule(entry)
                self.assertFalse(foreign.claim_publish(entry))
                self.assertTrue(repo.claim_publish(entry))
                self.assertFalse(repo.claim_publish(entry))
                loaded = repo.get_schedule('s')
                self.assertEqual(loaded.status, 'dispatching')
                self.assertEqual(loaded.failure, 'publish_outcome_unconfirmed')
                self.assertEqual(loaded.text, 'Synthetic')
                self.assertIsNone(foreign.get_schedule('s'))
                service = Service.__new__(Service)
                class Scheduler:
                    def get_entry(self, key): return loaded
                service._scheduler = Scheduler()
                # Method must refuse before plan lookup or filing any review.
                service.get_plan = lambda _: self.fail('dispatching cannot be re-reviewed')
                with self.assertRaises(ScheduleStateError):
                    service.request_schedule_review('s')
            finally:
                engine.dispose()


if __name__ == '__main__': unittest.main()
