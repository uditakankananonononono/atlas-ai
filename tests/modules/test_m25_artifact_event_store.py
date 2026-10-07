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


def test_m25_hz8_conflicting_duplicate_is_valueerror_not_integrityerror(tmp_path):
    # KILL: the INSERT path had no IntegrityError boundary; a lost race leaked
    # a raw sqlite3.IntegrityError (500). Policy unchanged: same content
    # idempotent, different content rejected.
    from app.modules.m25_knowledge_copilot.artifact_events import ArtifactEventStore
    st=ArtifactEventStore(str(tmp_path/'e.db'))
    ev={'event_id':'e1','tenant_id':'t1','module_id':25,'artifact_id':'a','artifact_kind':'k','content_sha256':'a'*64,'observed_at':'t','producer_version':'1'}
    st.put(ev)
    import pytest
    with pytest.raises(ValueError): st.put({**ev,'artifact_kind':'other'})
    assert st.put(ev)['created'] is False


def test_m25_hz10_integrity_error_handler_exercised(tmp_path, monkeypatch):
    # Discriminating handler evidence (policy unchanged): force the INSERT to
    # lose the race against an already-committed row; the handler must re-read
    # and apply the same idempotency policy instead of leaking IntegrityError.
    import sqlite3
    from app.modules.m25_knowledge_copilot.artifact_events import ArtifactEventStore
    st=ArtifactEventStore(str(tmp_path/'e.db'))
    ev={'event_id':'e1','tenant_id':'t1','module_id':25,'artifact_id':'a','artifact_kind':'k','content_sha256':'a'*64,'observed_at':'t','producer_version':'1'}
    st.put(ev)
    class FlakyDB:
        def __init__(self,real): self._real=real
        def execute(self,sql,*a,**k):
            if str(sql).lstrip().upper().startswith('INSERT'):
                raise sqlite3.IntegrityError('UNIQUE constraint failed')
            return self._real.execute(sql,*a,**k)
        def __enter__(self): self._real.__enter__(); return self
        def __exit__(self,*a): return self._real.__exit__(*a)
    real_db=st._db
    monkeypatch.setattr(st,'_db',lambda:FlakyDB(real_db()))
    same=st.put(ev)
    assert same['created'] is False and same['event']['event_id']=='e1'
    import pytest
    with pytest.raises(ValueError): st.put({**ev,'artifact_kind':'other'})
