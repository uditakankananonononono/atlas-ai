"""Returned commits outrank cleanup integrity classification. SQLite path pins,
not crash/race closure or a production-schema guarantee."""
import sqlite3
import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.modules.m23_study_abroad import _commit_contract
from app.modules.m23_study_abroad._commit_contract import CommitOutcomeUnknown
from test_m23_hz28_error_boundary_characterization import (
    local, _story, _interview, _story_versions, ANSWER,
)

@pytest.mark.parametrize('kind', ['story', 'interview'])
@pytest.mark.parametrize('signal', ['unique', 'non_unique', 'unknown'])
def test_cleanup_integrity_never_classified_or_retried(local, kind, signal, monkeypatch):
    repo, ident, engine, sessions = _story(local) if kind == 'story' else _interview(local)
    call = (lambda: repo.add_student_version(ident, ANSWER, {})) if kind == 'story' else (lambda: repo.answer(ident, ANSWER))
    original_close = Session.close
    committed = []; faults = []
    cause = (sqlite3.IntegrityError('UNIQUE constraint failed: cleanup.v') if signal == 'unique'
             else sqlite3.IntegrityError('CHECK constraint failed: cleanup') if signal == 'non_unique'
             else RuntimeError('unidentified cleanup driver'))
    fault = IntegrityError('postcommit close', {}, cause)
    def mark(session):
        if sessions.armed: committed.append(session)
    def close(session):
        original_close(session)
        if sessions.armed and session in committed:
            faults.append(fault)
            raise fault
    def refuse_classification(exc):
        pytest.fail('post-commit cleanup was sent to write classifier')
    event.listen(Session, 'after_commit', mark)
    monkeypatch.setattr(Session, 'close', close)
    monkeypatch.setattr(_commit_contract, 'classify_integrity_error', refuse_classification)
    sessions.armed = True
    try:
        with pytest.raises(CommitOutcomeUnknown) as caught: call()
    finally:
        sessions.armed = False
        event.remove(Session, 'after_commit', mark)
    assert caught.value.__cause__ is fault
    assert sessions.attempts == 1
    assert len(faults) == 1
    assert 'rolled back' not in str(caught.value)
    if kind == 'story': assert _story_versions(sessions, ident) == [1]
    else: assert len(repo.get(ident)['turns']) == 1
