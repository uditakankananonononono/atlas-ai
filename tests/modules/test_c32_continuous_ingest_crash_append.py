"""Real interruption and append regressions for supplied-file ingestion."""
import json
from pathlib import Path

import pytest

from app.modules.c32 import continuous_ingest as ci


def setup(tmp_path, content='{"id":1}\n{"id":2}\n'):
    inbox = tmp_path / 'inbox'
    inbox.mkdir()
    path = inbox / 'a.jsonl'
    path.write_text(content)
    return inbox, path, str(tmp_path / 'state.json')


def test_actual_interruption_keeps_checkpoint_and_counts(monkeypatch, tmp_path):
    inbox, _, state = setup(tmp_path)
    save = ci._save_state
    calls = 0

    def crash_after_persist(path, data):
        nonlocal calls
        save(path, data)
        calls += 1
        if calls == 1:
            raise RuntimeError('injected interruption after durable checkpoint')

    monkeypatch.setattr(ci, '_save_state', crash_after_persist)
    with pytest.raises(RuntimeError):
        ci.run(str(inbox), state, batch_size=1)
    monkeypatch.setattr(ci, '_save_state', save)
    result = ci.run(str(inbox), state, batch_size=1)
    assert result['run']['records'] == 1
    assert result['run']['resumed_files'] == 1
    assert result['cumulative']['records_ingested'] == 2
    assert result['cumulative']['bytes_ingested'] == len('{"id":1}\n{"id":2}\n'.encode())
    assert json.loads(Path(state).read_text())['dedupe_count'] == 2


def test_append_completed_file_is_ingested(tmp_path):
    inbox, path, state = setup(tmp_path, '{"id":1}\n')
    ci.run(str(inbox), state, batch_size=1)
    with path.open('a') as stream:
        stream.write('{"id":2}\n')
    result = ci.run(str(inbox), state, batch_size=1)
    assert result['run']['records'] == 1
    assert result['cumulative']['records_ingested'] == 2


def test_incomplete_last_line_waits_for_completion(tmp_path):
    inbox, path, state = setup(tmp_path, '{"id":1}\n{"id":')
    result = ci.run(str(inbox), state, batch_size=1)
    assert result['run']['records'] == 1
    assert result['run']['malformed'] == 0
    with path.open('a') as stream:
        stream.write('2}\n')
    result = ci.run(str(inbox), state, batch_size=1)
    assert result['run']['records'] == 1
    assert result['cumulative']['records_ingested'] == 2


def test_completed_file_replacement_is_not_silently_skipped(tmp_path):
    inbox, path, state = setup(tmp_path, '{"id":1}\n')
    ci.run(str(inbox), state)
    path.unlink()
    path.write_text('{"id":99999}\n')
    result = ci.run(str(inbox), state)
    assert result['run']['records'] == 1
    assert result['cumulative']['records_ingested'] == 2


def test_truncation_restarts_from_zero_with_dedupe(tmp_path):
    inbox, path, state = setup(tmp_path)
    ci.run(str(inbox), state)
    path.write_text('{"id":3}\n')
    result = ci.run(str(inbox), state)
    assert result['run']['records'] == 1
    assert result['cumulative']['records_ingested'] == 3


def test_os_exit_after_commit_then_resume(tmp_path):
    import os
    import subprocess
    import sys
    inbox, _, state = setup(tmp_path)
    script = '''
import os, sys
from app.modules.c32 import continuous_ingest as ci
save = ci._save_state
def exit_after_save(path, data):
    save(path, data)
    os._exit(71)
ci._save_state = exit_after_save
ci.run(sys.argv[1], sys.argv[2], batch_size=1)
'''
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / 'backend'))
    result = subprocess.run([sys.executable, '-c', script, str(inbox), state], env=env)
    assert result.returncode == 71
    result = ci.run(str(inbox), state, batch_size=1)
    assert result['run']['records'] == 1
    assert result['cumulative']['records_ingested'] == 2


def test_batch_transaction_rolls_back_on_failure(monkeypatch, tmp_path):
    inbox, _, state = setup(tmp_path)
    original = ci._record_hash
    calls = 0

    def fail_second(line):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('injected failure inside transaction')
        return original(line)

    monkeypatch.setattr(ci, '_record_hash', fail_second)
    with pytest.raises(RuntimeError):
        ci.run(str(inbox), state, batch_size=2)
    monkeypatch.setattr(ci, '_record_hash', original)
    result = ci.run(str(inbox), state, batch_size=2)
    assert result['run']['records'] == 2
    assert result['run']['deduped'] == 0
    assert result['cumulative']['records_ingested'] == 2


def test_deleted_json_mirror_does_not_erase_recovery(tmp_path):
    inbox, path, state = setup(tmp_path)
    ci.run(str(inbox), state)
    Path(state).unlink()
    with path.open('a') as stream:
        stream.write('{"id":3}\n')
    result = ci.run(str(inbox), state)
    assert result['run']['records'] == 1
    assert result['cumulative']['records_ingested'] == 3


def test_lock_fails_closed_for_another_worker(tmp_path):
    inbox, _, state = setup(tmp_path)
    with ci._database(state):
        with pytest.raises(ValueError, match='INGEST_REFUSED_BUSY'):
            ci.run(str(inbox), state)
    assert ci.run(str(inbox), state)['run']['records'] == 2


def test_legacy_migration_preserves_counts_and_dedupe(tmp_path):
    inbox, _, state = setup(tmp_path)
    Path(state).write_text(json.dumps({'version': 1, 'files': {},
        'seen': [ci._record_hash('{"id":1}')],
        'ledger': {'runs': 4, 'records_ingested': 1, 'records_deduped': 0,
                   'bytes_ingested': 9, 'elapsed_s': 2.0}}))
    result = ci.run(str(inbox), state)
    assert result['run']['records'] == 1
    assert result['run']['deduped'] == 1
    assert result['cumulative']['records_ingested'] == 2
    assert result['cumulative']['runs'] == 5
    assert json.loads(Path(state).read_text())['version'] == 2


def test_legacy_oversize_refuses_before_json_parse(monkeypatch, tmp_path):
    inbox, _, state = setup(tmp_path)
    Path(state).write_bytes(b' ' * (ci.MAX_LEGACY_BYTES + 1))
    def reject_parse(_):
        raise AssertionError('oversized state parsed')
    monkeypatch.setattr(ci.json, 'loads', reject_parse)
    with pytest.raises(ValueError, match='INGEST_REFUSED_OVERSIZE:legacy_state'):
        ci.run(str(inbox), state)


def test_oversize_line_preserves_previous_committed_batch(tmp_path):
    inbox, path, state = setup(tmp_path, '{"id":1}\n' + 'x' * (ci.MAX_LINE + 1) + '\n')
    result = ci.run(str(inbox), state, batch_size=1)
    assert result['quarantined'][0]['reason'] == 'INGEST_REFUSED_OVERSIZE:line'
    path.write_text('{"id":1}\n{"id":2}\n')
    result = ci.run(str(inbox), state, batch_size=1)
    assert result['run']['records'] == 1
    assert result['cumulative']['records_ingested'] == 2


@pytest.mark.parametrize('field,value', [('max_pending', True), ('max_pending', 0),
    ('max_pending', '3'), ('max_files_per_run', True), ('max_files_per_run', 0),
    ('batch_size', True), ('batch_size', 10001)])
def test_exact_parameter_validation(tmp_path, field, value):
    inbox, _, state = setup(tmp_path)
    with pytest.raises(ValueError, match='INGEST_REFUSED_BAD_TYPE:' + field):
        ci.run(str(inbox), state, **{field: value})
    assert not Path(state + '.sqlite3').exists()


def test_input_and_state_symlinks_refused(tmp_path):
    inbox, path, state = setup(tmp_path)
    real = tmp_path / 'source'
    path.rename(real)
    path.symlink_to(real)
    with pytest.raises(ValueError, match='INGEST_REFUSED_PATH:input'):
        ci.run(str(inbox), state)
    path.unlink()
    path.write_text('{"id":1}\n')
    target = tmp_path / 'other'
    target.write_text('private')
    Path(state).symlink_to(target)
    with pytest.raises(ValueError, match='INGEST_REFUSED_PATH:symlink'):
        ci.run(str(inbox), state)
    assert target.read_text() == 'private'


def test_pending_bound_checked_before_opening_records(tmp_path, monkeypatch):
    inbox, path, state = setup(tmp_path)
    (inbox / 'b.jsonl').write_text('{}\n')
    monkeypatch.setattr(ci, 'MAX_PENDING_REPORT', 1)
    with pytest.raises(ValueError, match='INGEST_REFUSED_OVERSIZE:pending'):
        ci.run(str(inbox), state, max_pending=1)
    assert not Path(state + '.sqlite3').exists()


def test_disk_dedupe_not_json_hash_array(tmp_path):
    import sqlite3
    inbox, path, state = setup(tmp_path, ''.join(json.dumps({'id': i}) + '\n' for i in range(2500)))
    result = ci.run(str(inbox), state, batch_size=50)
    assert result['run']['records'] == 2500
    mirror = json.loads(Path(state).read_text())
    assert 'seen' not in mirror
    assert mirror['dedupe_count'] == 2500
    with sqlite3.connect(state + '.sqlite3') as conn:
        assert conn.execute('SELECT count(*) FROM seen').fetchone()[0] == 2500
    assert Path(state).stat().st_size < 1024


def test_unchanged_completed_files_do_not_consume_run_limit(tmp_path):
    inbox, _, state = setup(tmp_path)
    ci.run(str(inbox), state)
    (inbox / 'b.jsonl').write_text('{"id":3}\n')
    result = ci.run(str(inbox), state, max_files_per_run=1)
    assert result['run']['records'] == 1
    assert result['run']['files_touched'] == 1


def test_blank_and_invalid_utf8_counting(tmp_path):
    inbox, path, state = setup(tmp_path)
    path.write_bytes(b'\n\xff\n{"id":1}\n')
    result = ci.run(str(inbox), state)
    assert result['run']['records'] == 1
    assert result['run']['malformed'] == 1
    assert result['run']['bytes'] == path.stat().st_size


def test_touch_completed_file_does_not_recount_duplicates(tmp_path):
    import os
    inbox, path, state = setup(tmp_path)
    ci.run(str(inbox), state)
    prior = path.stat()
    os.utime(path, ns=(prior.st_atime_ns, prior.st_mtime_ns + 1000000000))
    result = ci.run(str(inbox), state)
    assert result['run']['deduped'] == 0
    assert result['run']['files_touched'] == 0
    assert result['cumulative']['records_deduped'] == 0


def test_poison_file_quarantined_without_blocking_later_file(tmp_path):
    inbox, path, state = setup(tmp_path, '{"id":1}\n' + 'x' * (ci.MAX_LINE + 1) + '\n')
    (inbox / 'b.jsonl').write_text('{"id":2}\n')
    first = ci.run(str(inbox), state, batch_size=100)
    assert first['run']['records'] == 2  # good prefix committed even below batch size
    assert first['quarantined'] == [{'file': 'a.jsonl', 'reason': 'INGEST_REFUSED_OVERSIZE:line'}]
    again = ci.run(str(inbox), state, batch_size=100)
    assert again['run']['records'] == again['run']['deduped'] == 0
    assert again['run']['files_touched'] == 0
    assert again['quarantined'] == first['quarantined']
    path.write_text('{"id":1}\n{"id":3}\n')
    repaired = ci.run(str(inbox), state)
    assert repaired['run']['records'] == 1
    assert repaired['quarantined'] == []
    assert repaired['cumulative']['records_ingested'] == 3


def test_quarantine_survives_process_exit_before_mirror(monkeypatch, tmp_path):
    inbox, path, state = setup(tmp_path, 'x' * (ci.MAX_LINE + 1) + '\n')
    save = ci._save_state
    def crash_after_save(path, data):
        save(path, data)
        raise RuntimeError('interruption after poison checkpoint')
    monkeypatch.setattr(ci, '_save_state', crash_after_save)
    with pytest.raises(RuntimeError):
        ci.run(str(inbox), state)
    monkeypatch.setattr(ci, '_save_state', save)
    result = ci.run(str(inbox), state)
    assert result['run']['files_touched'] == 0
    assert result['quarantined'][0]['file'] == 'a.jsonl'


def test_same_size_completed_rewrite_new_mtime_reingested(tmp_path):
    import os
    inbox, path, state = setup(tmp_path, '{"a":1}\n{"a":2}\n')
    ci.run(str(inbox), state)
    stat = path.stat()
    path.write_text('{"z":1}\n{"z":2}\n')
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000000000))
    result = ci.run(str(inbox), state)
    assert result['run']['records'] == 2
    assert result['run']['deduped'] == 0
    assert result['cumulative']['records_ingested'] == 4
