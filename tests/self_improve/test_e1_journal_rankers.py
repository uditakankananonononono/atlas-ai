"""Pins for experiment E1 rankers (experiments/e1_journal_retrieval). Not a journal test."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experiments" / "e1_journal_retrieval"))
import rankers as R  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


def _journal():
    return R.pj.PersistentJournal("t", "a", sessionmaker(bind=create_engine("sqlite://")))


def test_supersession_returns_corrected_text_not_original():
    j = _journal()
    j.capture("Use Acme for office catering", "fits budget", "ctx", "owner:chat")
    j.correction("Use Acme for office catering", "Use Birch for office catering", "ctx", "owner:chat")
    now = datetime.now(timezone.utc)
    assert R.h1a(j, "which office catering vendor", 3, now) == ["Use Birch for office catering"]
    # at ef1f6af the shipped retrieve returned the stale original; commit e2f5fb75 fixed that
    assert R.b0(j, "which office catering vendor", 3, now) == ["Use Birch for office catering"]


def test_all_rankers_return_empty_on_no_overlap():
    j = _journal()
    j.capture("Use Acme for office catering", "fits budget", "ctx", "owner:chat")
    now = datetime.now(timezone.utc)
    for fn in R.RANKERS.values():
        assert fn(j, "zzzz qqqq", 3, now) == []
