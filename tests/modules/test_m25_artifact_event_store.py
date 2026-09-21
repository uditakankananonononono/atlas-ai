import base64,hashlib,pytest
from app.modules.m25_knowledge_copilot.artifact_events import ArtifactEventStore
def event(tenant='a'):
 blob=b'reproducible result';return blob,{'event_id':'e1','tenant_id':tenant,'module_id':4,'artifact_id':'a1','artifact_kind':'result','content_sha256':hashlib.sha256(blob).hexdigest(),'observed_at':'2026-09-22T00:00:00Z','producer_version':'commit','source_refs':[]}
def test_store_persists_bytes_verified_event_and_idempotent_replay(tmp_path):
 store=ArtifactEventStore(tmp_path/'events.db');blob,e=event();encoded=base64.b64encode(blob).decode()
 first=store.put(e,encoded);second=store.put(e,encoded)
 assert first['created'] and first['bytes_verified'] and not second['created']
 reopened=ArtifactEventStore(tmp_path/'events.db');assert reopened.get('a','e1')['event']['artifact_id']=='a1'
def test_store_is_tenant_scoped_and_conflicting_replay_fails(tmp_path):
 store=ArtifactEventStore(tmp_path/'events.db');blob,e=event();store.put(e)
 with pytest.raises(KeyError):store.get('b','e1')
 changed={**e,'artifact_kind':'other'}
 with pytest.raises(ValueError,match='different content'):store.put(changed)
def test_store_rejects_bad_base64_and_byte_hash_mismatch(tmp_path):
 store=ArtifactEventStore(tmp_path/'events.db');_,e=event()
 with pytest.raises(ValueError,match='valid base64'):store.put(e,'%%%')
 with pytest.raises(ValueError,match='hash mismatch'):store.put(e,base64.b64encode(b'wrong').decode())
