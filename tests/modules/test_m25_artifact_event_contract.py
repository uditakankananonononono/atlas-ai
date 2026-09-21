import pytest
from app.modules.m25_knowledge_copilot.artifact_events import ingest_artifact_event
def base():return {'event_id':'evt-1','tenant_id':'t','module_id':4,'artifact_id':'bundle-1','artifact_kind':'reproducibility_bundle','content_sha256':'a'*64,'observed_at':'2026-09-22T00:00:00Z','producer_version':'e1e667b','source_refs':[{'uri':'https://example.org/data','sha256':'b'*64}],'execution_state':'planned'}
def test_common_artifact_event_canonicalizes_and_hashes_provenance():
 out=ingest_artifact_event(base())
 assert out['accepted'] and len(out['event']['event_sha256'])==64
 assert out['event']['module_id']==4 and 'separate verification' in out['boundary']
def test_effect_states_require_receipts_and_contract_rejects_bad_hashes_sources():
 e=base();e['execution_state']='externally_executed'
 with pytest.raises(ValueError,match='receipt_ids'):ingest_artifact_event(e)
 e=base();e['content_sha256']='bad'
 with pytest.raises(ValueError,match='SHA-256'):ingest_artifact_event(e)
 e=base();e['source_refs']=[{}]
 with pytest.raises(ValueError,match='uri'):ingest_artifact_event(e)
