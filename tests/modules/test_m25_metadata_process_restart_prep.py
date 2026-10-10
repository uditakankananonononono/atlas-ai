"""ATLAS-5 - M25 metadata second-process canary, audited and landed.

Integrator and independent auditor ran the real child interpreter: 3 cases PASS.
Mutations A (legacy promotion) and B (new-row restamping) fail these tests;
some existing in-process M25 tests also fail under those mutations. The new
value is second-process proof, not exclusive detection. Mutation C is unrun.
Receipts and scope live in
backend/app/modules/m25_knowledge_copilot_training/METADATA_RESTART_CANARY_PREP.md.

What this pins beyond test_m25_version_metadata.py: the legacy-unknown /
new-exact pair must survive an ACTUAL second Python process restore. The
first process builds a legacy number/hash-only manifest, restores with an
attested adapter at a frozen clock, and appends exactly ONE new version at a
distinct timezone-aware clock and distinct MIME. A real subprocess (second
Python process) then restores from the same test root and reports its state
as JSON for the parent to assert.

Scope exclusions (per unit): no authenticity or signature claims for
MIME-equivalent tamper, no trusted-wall-clock claims, no historical
reconstruction claims, no deployment claims. Subprocess tests were executed and independently audited; no deployment.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from test_m25_verified_rehydration import (
    NOW,
    ingest,
    load_manifest,
    pipe,
    save_manifest,
    src,
    tree_hashes,
)
from app.modules.m25_knowledge_copilot_training.pipeline import LocalKnowledgePipeline
from app.modules.m25_knowledge_copilot_training.schemas import IngestRequest

RESTORE_STAMP = datetime(2026, 9, 21, 3, 0, tzinfo=timezone.utc)
APPEND_STAMP = datetime(2026, 9, 21, 5, 0, tzinfo=timezone.utc)
SECOND_STAMP = datetime(2026, 9, 21, 8, 0, tzinfo=timezone.utc)

# Second-process program: restores from the test root with an attested
# adapter and a frozen clock, then prints its resulting state as one JSON
# object on stdout. On a fail-closed refusal it reports the refusal and the
# (empty) in-memory state instead. It also attempts a second restore in the
# same process to pin the no-duplicate-append refusal.
CHILD_SOURCE = r'''
import json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from app.modules.m25_knowledge_copilot_training.pipeline import LocalKnowledgePipeline
from app.modules.m25_knowledge_copilot_training.recovery import RecoveryError

root = Path(sys.argv[2])
stamp = datetime.fromisoformat(sys.argv[3])
pipe = LocalKnowledgePipeline(root, 'tenant-a', 'actor-a', clock=lambda: stamp)
try:
    report = pipe.restore_verified(same_adapters_attested=True)
except RecoveryError as exc:
    print(json.dumps({'refused': True, 'check': exc.check,
                      'records': len(pipe.records), 'chunks': len(pipe.chunks)}))
    sys.exit(0)
versions = [{'number': v.number, 'metadata_known': v.metadata_known,
             'created_at': v.created_at.astimezone(timezone.utc).isoformat(),
             'mime_type': v.mime_type}
            for rec in pipe.records.values() for v in rec.versions]
chunks = [{'chunk_id': c.chunk_id, 'version': c.version,
           'created_at': c.created_at.astimezone(timezone.utc).isoformat()}
          for c in pipe.chunks]
try:
    pipe.restore_verified(same_adapters_attested=True)
    second_refused = False
except RecoveryError:
    second_refused = True
print(json.dumps({'refused': False, 'versions': versions, 'chunks': chunks,
                  'restamped': report.created_at_restamped, 'residue': report.residue,
                  'second_restore_refused': second_refused}))
'''


def run_child(tmp_path, stamp):
    """Run the second-process restore in a real subprocess and return its JSON report."""
    backend = Path(__file__).resolve().parents[2] / 'backend'
    proc = subprocess.run(
        [sys.executable, '-c', CHILD_SOURCE, str(backend), str(tmp_path), stamp.isoformat()],
        capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, f'second process exited {proc.returncode}: {proc.stderr}'
    assert proc.stderr == '', f'second process wrote stderr: {proc.stderr}'
    return json.loads(proc.stdout)


def build_legacy_new_pair(tmp_path):
    """First process: legacy number/hash-only manifest, verified restore at a
    frozen clock with attested adapter, then exactly ONE new version appended
    at a distinct timezone-aware clock and a distinct MIME (text/html)."""
    first = pipe(tmp_path)
    ingest(first)  # 'Alpha fact.', text/plain, clock NOW
    path, disk = load_manifest(tmp_path)
    legacy_row = {k: v for k, v in disk['versions'][0].items() if k in ('number', 'hash')}
    disk['versions'] = [legacy_row]
    save_manifest(path, disk)
    # One process must restore and then append; the pipeline clock is fixed at
    # construction, so a mutable clock cell supplies the distinct append time.
    clock_state = {'now': RESTORE_STAMP}
    live = LocalKnowledgePipeline(tmp_path, 'tenant-a', 'actor-a', clock=lambda: clock_state['now'])
    live.restore_verified(same_adapters_attested=True)
    legacy = live.records['s1'].versions[0]
    assert legacy.metadata_known is False
    assert legacy.created_at == RESTORE_STAMP
    assert legacy.mime_type == 'text/plain'
    clock_state['now'] = APPEND_STAMP
    live.ingest(IngestRequest(source=src(), content='<b>Beta</b> fact.',
                              mime_type='text/html', actor_id='actor-a'))
    assert len(live.records['s1'].versions) == 2, 'exactly one new version must be appended'
    return path, legacy_row


def test_legacy_unknown_new_exact_pair_survives_second_process_restore(tmp_path):
    path, legacy_row = build_legacy_new_pair(tmp_path)
    rows = json.loads(path.read_text())['versions']
    assert len(rows) == 2, 'no duplicate append: exactly two recorded versions'
    assert rows[0] == legacy_row, (
        'NAMED FAILURE (legacy promotion): the legacy row must remain number/hash-only '
        'after the append; promoting it to metadata-known rewrites history')
    assert rows[1]['metadata_version'] == 1
    assert rows[1]['created_at'] == APPEND_STAMP.astimezone(timezone.utc).isoformat()
    assert rows[1]['mime_type'] == 'text/html'
    tree_after_append = tree_hashes(tmp_path)

    out = run_child(tmp_path, SECOND_STAMP)
    assert out['refused'] is False
    assert out['versions'] == [
        {'number': 1, 'metadata_known': False,
         'created_at': SECOND_STAMP.astimezone(timezone.utc).isoformat(), 'mime_type': 'text/plain'},
        {'number': 2, 'metadata_known': True,
         'created_at': APPEND_STAMP.astimezone(timezone.utc).isoformat(), 'mime_type': 'text/html'},
    ], ('NAMED FAILURE (metadata pair): the legacy row must stay metadata-unknown '
        '(restamped per restore, by design) and the new row must restore with its exact '
        'recorded created_at/MIME; restamping the new created_at on restore loses persisted metadata')
    assert out['chunks'] == [
        {'chunk_id': 's1:v1:c1.1', 'version': 1,
         'created_at': SECOND_STAMP.astimezone(timezone.utc).isoformat()},
        {'chunk_id': 's1:v2:c1.1', 'version': 2,
         'created_at': APPEND_STAMP.astimezone(timezone.utc).isoformat()},
    ], ('NAMED FAILURE (chunk identity): no duplicate append - exactly one chunk per version, '
        'legacy chunk stamped at this restore, new-version chunk carrying the exact new time')
    assert out['restamped'] is True, 'a legacy row is present, so the report must say restamping happened'
    assert out['residue'] == []
    assert out['second_restore_refused'] is True, (
        'a second restore in the same process must refuse (pipeline-state), pinning no duplicate append')
    assert tree_hashes(tmp_path) == tree_after_append, (
        'the second-process restore is read-only: tree hash unchanged by restore')


@pytest.mark.parametrize('corrupt', [
    {'metadata_version': 2},
    {'created_at': '2026-09-21T05:00:00'},
], ids=['metadata_version_not_1', 'created_at_timezone_naive'])
def test_second_process_refuses_malformed_new_metadata(tmp_path, corrupt):
    path, _legacy_row = build_legacy_new_pair(tmp_path)
    data = json.loads(path.read_text())
    data['versions'][1].update(corrupt)
    path.write_text(json.dumps(data, sort_keys=True))
    before = tree_hashes(tmp_path)

    out = run_child(tmp_path, SECOND_STAMP)
    assert out['refused'] is True, 'malformed new-row metadata must fail closed in the second process'
    assert out['check'] == 'manifest-schema'
    assert out['records'] == 0 and out['chunks'] == 0, (
        'a refused restore must publish no records and no chunks')
    assert tree_hashes(tmp_path) == before, 'a refused restore must not write'
