import json
from datetime import timedelta
import pytest
from test_m25_verified_rehydration import pipe,ingest,src,NOW,tree_hashes
from app.modules.m25_knowledge_copilot_training.recovery import RecoveryError
from app.modules.m25_knowledge_copilot_training.schemas import IngestRequest


def test_exact_timestamp_mime_recovery_and_read_only(tmp_path):
    first=pipe(tmp_path)
    original=ingest(first,mime='text/markdown')
    before=tree_hashes(tmp_path)
    fresh=pipe(tmp_path,clock=NOW+timedelta(days=1))
    report=fresh.restore_verified(same_adapters_attested=True)
    loaded=fresh.records['s1'].versions[0]
    assert loaded.created_at==original.created_at and loaded.mime_type=='text/markdown'
    assert loaded.metadata_known and not report.created_at_restamped
    assert fresh.chunks[0].created_at==original.created_at
    assert tree_hashes(tmp_path)==before
    fresh.ingest(IngestRequest(source=src(),content='new',mime_type='text/plain',actor_id='actor-a'))
    assert len(fresh.records['s1'].versions)==2


def test_legacy_fallback_not_promoted_to_historical_metadata(tmp_path):
    ingest(pipe(tmp_path))
    manifest=tmp_path/'tenant-a/s1/manifest.json';data=json.loads(manifest.read_text())
    data['versions']=[{k:v for k,v in row.items() if k in ('number','hash')} for row in data['versions']]
    manifest.write_text(json.dumps(data))
    fresh=pipe(tmp_path,clock=NOW+timedelta(days=2))
    report=fresh.restore_verified(same_adapters_attested=True)
    assert report.created_at_restamped and not fresh.records['s1'].versions[0].metadata_known
    fresh.ingest(IngestRequest(source=src(),content='new',mime_type='text/plain',actor_id='actor-a'))
    rows=json.loads(manifest.read_text())['versions']
    assert set(rows[0])=={'number','hash'} and rows[1]['metadata_version']==1

@pytest.mark.parametrize('field,value',[('metadata_version',True),('metadata_version',2),('created_at','2026-10-10'),('created_at','bad'),('mime_type','application/pdf')])
def test_invalid_metadata_fail_closed(tmp_path,field,value):
    ingest(pipe(tmp_path));manifest=tmp_path/'tenant-a/s1/manifest.json'
    data=json.loads(manifest.read_text());data['versions'][0][field]=value;manifest.write_text(json.dumps(data))
    fresh=pipe(tmp_path)
    with pytest.raises(RecoveryError):fresh.restore_verified(same_adapters_attested=True)
    assert not fresh.records and not fresh.chunks


def test_recorded_mime_not_guessed_on_mismatch(tmp_path):
    ingest(pipe(tmp_path),content='<b>text</b>',mime='text/html')
    manifest=tmp_path/'tenant-a/s1/manifest.json';data=json.loads(manifest.read_text())
    data['versions'][0]['mime_type']='text/plain';manifest.write_text(json.dumps(data))
    with pytest.raises(RecoveryError,match='MIME'):pipe(tmp_path).restore_verified(same_adapters_attested=True)


def test_contradiction_original_time_survives_restore_and_legacy_unknown(tmp_path):
    first=pipe(tmp_path)
    ingest(first,'a','fact is true')
    later=pipe(tmp_path,clock=NOW+timedelta(hours=1))
    ingest(later,'b','fact is not true')
    fresh=pipe(tmp_path,clock=NOW+timedelta(days=2))
    fresh.restore_verified(same_adapters_attested=True)
    conflicts=fresh.contradictions('fact')
    assert conflicts
    for row in conflicts:
        chosen=row[row['fresher']]
        assert chosen['source_id']=='b'
    manifest=tmp_path/'tenant-a/a/manifest.json';data=json.loads(manifest.read_text())
    data['versions']=[{k:v for k,v in row.items() if k in ('number','hash')} for row in data['versions']]
    manifest.write_text(json.dumps(data))
    old=pipe(tmp_path,clock=NOW+timedelta(days=3));old.restore_verified(same_adapters_attested=True)
    assert all(x['fresher']=='unknown' for x in old.contradictions('fact'))


def test_loaded_metadata_drift_refuses_append_without_overwrite(tmp_path):
    first=pipe(tmp_path);ingest(first)
    manifest=tmp_path/'tenant-a/s1/manifest.json';data=json.loads(manifest.read_text())
    data['versions'][0]['created_at']=(NOW+timedelta(hours=1)).isoformat();manifest.write_text(json.dumps(data))
    before=tree_hashes(tmp_path)
    from app.modules.m25_knowledge_copilot_training.pipeline import KnowledgeError
    with pytest.raises(KnowledgeError):first.ingest(IngestRequest(source=src(),content='new',mime_type='text/plain',actor_id='actor-a'))
    assert tree_hashes(tmp_path)==before and len(first.records['s1'].versions)==1


@pytest.mark.parametrize('entry',[5,None,'bad',[],True])
def test_nonobject_version_rows_typed_refusal(tmp_path,entry):
    first=pipe(tmp_path);ingest(first)
    manifest=tmp_path/'tenant-a/s1/manifest.json';data=json.loads(manifest.read_text())
    data['versions']=[entry];manifest.write_text(json.dumps(data))
    from app.modules.m25_knowledge_copilot_training.pipeline import KnowledgeError
    with pytest.raises(KnowledgeError):first.register(src())
    with pytest.raises(RecoveryError):pipe(tmp_path).restore_verified(same_adapters_attested=True)
