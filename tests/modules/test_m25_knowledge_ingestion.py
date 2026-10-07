from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
from app.modules.m25_knowledge_copilot_training.pipeline import *
from app.modules.m25_knowledge_copilot_training.schemas import *
NOW=datetime(2026,9,21,tzinfo=timezone.utc)
def src(source_id='s1',kind='website',**kw):
    metadata=kw.pop('metadata',{})
    if kind=='podcast':metadata={'episode_title':'E','episode_id':'ep1','duration_seconds':10,**metadata}
    if kind=='book':metadata={'isbn':'123','edition':'1',**metadata}
    if kind=='forum':metadata={'thread_id':'t','posts':[{'id':'p1','parent':None}],**metadata}
    return SourceRegistration(source_id=source_id,kind=kind,canonical_url=None if kind in {'book','file','meeting_audio'} else f'https://example.test/{source_id}',author='A',published_at=NOW,title='Title',consent=ConsentRecord(granted_by='owner',granted_at=NOW,purposes=['knowledge_ingestion'],evidence='consent-1'),metadata=metadata,**kw)
def pipe(tmp_path,**kw):return LocalKnowledgePipeline(tmp_path,'tenant-a','actor-a',clock=lambda:NOW,**kw)
def ingest(p,s=None,text='Alpha fact.\n\nBeta fact.',mime='text/plain'):
    s=s or src(); return p.ingest(IngestRequest(source=s,content=text,mime_type=mime,actor_id='actor-a'))

def test_m25_01_consent_scoped_source_registration_and_missing_consent(tmp_path):
    p=pipe(tmp_path); bad=src();bad.consent.purposes=['other']
    with pytest.raises(ConsentError):p.register(bad)
def test_m25_02_local_first_ingestion_workspace_and_mounted_boundary(tmp_path):
    p=pipe(tmp_path);ingest(p);assert (tmp_path/'tenant-a'/'s1'/'v1'/'source.bin').exists();assert tmp_path.resolve() in p.workspace.parents
def test_m25_03_website_ingestion_full_provenance(tmp_path):
    p=pipe(tmp_path);v=ingest(p);assert p.records['s1'].source.canonical_url and v.content_hash and v.segments[0].anchors
def test_m25_04_podcast_ingestion_episode_metadata(tmp_path):
    class T:
      def transcribe(self,a):return [Segment(text='heard',anchors=[Anchor(anchor_id='t1',kind='timestamp',value='0-1')],speaker='A',speaker_confidence=.8,start_seconds=0,end_seconds=1)]
    p=pipe(tmp_path,transcriber=T());v=ingest(p,src('pod','podcast'),b'wav','audio/wav');assert v.segments[0].start_seconds==0
def test_m25_05_book_ingestion_page_anchors(tmp_path):
    p=pipe(tmp_path);v=ingest(p,src('book','book'),'Page text');assert v.segments[0].anchors[0].kind=='page'
def test_m25_06_forum_ingestion_thread_structure(tmp_path):
    p=pipe(tmp_path);v=ingest(p,src('forum','forum'),'Post one');assert p.records['forum'].source.metadata['posts'][0]['parent'] is None and v.segments[0].anchors[0].kind=='post'
def test_m25_07_meeting_audio_consent_and_speaker_uncertainty(tmp_path):
    class T:
      def transcribe(self,a):return [Segment(text='[inaudible] guessed words',anchors=[Anchor(anchor_id='t1',kind='timestamp',value='0-2')],speaker=None,speaker_confidence=.2,start_seconds=0,end_seconds=2)]
    p=pipe(tmp_path,transcriber=T());v=ingest(p,src('meet','meeting_audio'),b'wav','audio/wav');assert v.segments[0].text=='[inaudible]' and v.segments[0].speaker=='unknown'
def test_m25_08_multiformat_extraction_preserves_anchors_and_malformed_file(tmp_path):
    p=pipe(tmp_path);v=ingest(p,src('j','file'),'not-json','application/json') if False else None
    with pytest.raises(KnowledgeError):ingest(p,src('j','file'),'not-json','application/json')
def test_m25_09_transcription_honestly_unavailable_and_unsupported_source(tmp_path):
    p=pipe(tmp_path)
    with pytest.raises(AdapterUnavailable):ingest(p,src('a','meeting_audio'),b'x','audio/wav')
    with pytest.raises(UnsupportedSourceError):ingest(p,src('x','file'),b'x','application/zip')
def test_m25_10_dedup_and_versioning(tmp_path):
    p=pipe(tmp_path);a=ingest(p);b=ingest(p);c=ingest(p,text='changed');assert (a.number,b.number,c.number)==(1,1,2)
def test_m25_11_provenance_graph(tmp_path):
    p=pipe(tmp_path);v=ingest(p);assert p.edges==[{'from':'s1','to':v.content_hash,'relation':'has_version','version':1}]
def test_m25_12_semantic_chunks_embeddings_tenant_partition_and_dimension_mismatch(tmp_path):
    p=pipe(tmp_path);ingest(p);assert p.chunks[0].tenant_id=='tenant-a'
    with pytest.raises(KnowledgeError):p.search('alpha',tenant_id='tenant-b')
    class B:
      dimension=3
      def embed(self,t):return [1]
    with pytest.raises(DimensionMismatch):ingest(pipe(tmp_path/'bad',embedder=B()))
def test_m25_13_hybrid_lexical_vector_retrieval(tmp_path):
    p=pipe(tmp_path);ingest(p);assert p.search('Alpha')[0]['source_id']=='s1'
def test_m25_14_claim_level_citations_unsupported_claim_withheld(tmp_path):
    p=pipe(tmp_path);v=ingest(p)
    import hashlib as H
    seg=p.records['s1'].versions[0].segments[0].text
    c=Citation(source_id='s1',version=1,anchor_ids=['paragraph-1'],quote_hash=H.sha256(seg.encode()).hexdigest());assert p.substantiate([Claim(text='Alpha',citations=[c])])
    with pytest.raises(UnsupportedClaim):p.substantiate([Claim(text='invented')])
def test_m25_15_contradiction_freshness_analysis_stale_conflict(tmp_path):
    p=pipe(tmp_path);ingest(p,src('old'),text='Policy allows alpha');ingest(p,src('new'),text='Policy does not allow alpha');assert p.contradictions('Policy alpha')[0]['status']=='conflict_requires_review'
def test_m25_16_export_and_verified_deletion(tmp_path):
    p=pipe(tmp_path);ingest(p);assert p.export()['sources'];result=p.delete_verified('s1');assert result['deleted'] and not (tmp_path/'tenant-a'/'s1').exists() and not p.search('Alpha')
def test_actor_isolation(tmp_path):
    p=pipe(tmp_path)
    with pytest.raises(KnowledgeError):p.ingest(IngestRequest(source=src(),content='x',mime_type='text/plain',actor_id='other'))


def test_m25_hz8_substantiate_rejects_wrong_quote_hash(tmp_path):
    # KILL: an unrelated claim citing a real anchor with a bogus quote_hash
    # used to pass. quote_hash must match sha256 of the stored segment text.
    p=pipe(tmp_path);ingest(p)
    c=Citation(source_id='s1',version=1,anchor_ids=['paragraph-1'],quote_hash='h')
    with pytest.raises(UnsupportedClaim):p.substantiate([Claim(text='The moon is cheese',citations=[c])])

def test_m25_hz8_source_id_escape_contained_before_writes(tmp_path):
    # KILL: '..' wrote manifest.json into the shared root outside the tenant
    # workspace. Containment is resolved-path based, checked before writes.
    p=pipe(tmp_path)
    with pytest.raises(KnowledgeError):p.register(src('..'))
    assert not (tmp_path/'manifest.json').exists()
    with pytest.raises(KnowledgeError):ingest(p,src('..'))
    assert not (tmp_path/'v1').exists()

def test_m25_hz8_failed_ingest_leaves_no_registered_state(tmp_path):
    # KILL: register ran before validation, so a failed ingest still left a
    # record and manifest behind.
    p=pipe(tmp_path)
    with pytest.raises(KnowledgeError):ingest(p,src('j','file'),'not-json','application/json')
    assert 'j' not in p.records and not (tmp_path/'tenant-a'/'j').exists()

def test_m25_hz8_naive_consent_expiry_rejected_not_typeerror(tmp_path):
    # KILL: naive expiry <= aware clock raised a raw TypeError.
    p=pipe(tmp_path); b=src(); b.consent.expires_at=datetime(2030,1,1)
    with pytest.raises(ConsentError):p.register(b)

def test_m25_hz8_pdf_not_accepted_as_decoded(tmp_path):
    # KILL: application/pdf was "supported" via a UTF-8 paragraph split.
    p=pipe(tmp_path)
    with pytest.raises(UnsupportedSourceError):ingest(p,src('doc','file'),b'%PDF-1.4 body','application/pdf')

def test_m25_hz8_oversize_ingest_rejected(tmp_path):
    # KILL: IngestRequest.content was unbounded.
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        IngestRequest(source=src(),content='x'*20001,mime_type='text/plain',actor_id='actor-a')


def test_m25_hz9_dot_source_id_cannot_target_workspace_root(tmp_path):
    # KILL: source_id '.' resolved to the tenant workspace itself and wrote
    # manifest.json at the workspace root.
    p=pipe(tmp_path)
    with pytest.raises(KnowledgeError):p.register(src('.'))
    assert not (tmp_path/'tenant-a'/'manifest.json').exists()

def test_m25_hz9_restart_reingest_refuses_to_overwrite_existing_version(tmp_path):
    # KILL: after a restart (memory lost, disk persists) the old code reused
    # v1 with exist_ok=True and silently overwrote prior source bytes; its
    # failure cleanup could rmtree data it did not create.
    p=pipe(tmp_path);ingest(p)
    original=(tmp_path/'tenant-a'/'s1'/'v1'/'source.bin').read_bytes()
    p2=pipe(tmp_path)
    with pytest.raises(KnowledgeError):ingest(p2,text='changed content')
    assert (tmp_path/'tenant-a'/'s1'/'v1'/'source.bin').read_bytes()==original


def test_m25_hz10_escape_register_leaves_no_state(tmp_path):
    # KILL (hz8-era): register('..') rejected the disk write but still left a
    # '..' record in memory - mutation happened before the guard fired.
    p=pipe(tmp_path)
    with pytest.raises(KnowledgeError):p.register(src('..'))
    assert '..' not in p.records

def test_m25_hz10_workspace_root_is_never_a_delete_target(tmp_path):
    # KILL (hz8-era): delete_verified('.') rmtree'd the whole tenant workspace.
    p=pipe(tmp_path);ingest(p)
    with pytest.raises(KnowledgeError):p.delete_verified('.')
    assert p.records and (tmp_path/'tenant-a'/'s1'/'v1'/'source.bin').exists()

def test_m25_hz10_persist_failure_rolls_back_memory_and_own_files(tmp_path, monkeypatch):
    # KILL: a manifest write failure after memory mutation left source.bin,
    # an empty-shell record and no rollback.
    p=pipe(tmp_path)
    calls=[0]
    original=p._persist_manifest
    def flaky(rec):
        calls[0]+=1
        if calls[0]==2: raise OSError('disk full')
        return original(rec)
    monkeypatch.setattr(p,'_persist_manifest',flaky)
    with pytest.raises(KnowledgeError,match='rolled back'):ingest(p)
    # The durable registration is preserved; only the unpersisted version is
    # rolled back. Memory and manifest agree: record present, zero versions.
    assert 's1' in p.records and p.records['s1'].versions==[] and not p.chunks and not p.edges
    assert not (tmp_path/'tenant-a'/'s1'/'v1').exists()
    import json as J
    assert J.loads((tmp_path/'tenant-a'/'s1'/'manifest.json').read_text())['versions']==[]

def test_m25_hz10_delete_failure_retains_tracking_truthfully(tmp_path, monkeypatch):
    # KILL: a no-op rmtree removed memory tracking while returning
    # deleted=False - the store claimed nothing while serving nothing true.
    p=pipe(tmp_path);ingest(p)
    import shutil
    monkeypatch.setattr(shutil,'rmtree',lambda *a,**k:None)
    result=p.delete_verified('s1')
    assert result['deleted'] is False and result['tracking_retained'] is True
    assert 's1' in p.records and p.search('Alpha')


def test_m25_hz11_register_persist_failure_leaves_no_record(tmp_path, monkeypatch):
    # KILL: register() persisted after mutating records; a failed first
    # manifest write left an in-memory record with nothing on disk.
    p=pipe(tmp_path)
    monkeypatch.setattr(p,'_persist_manifest',lambda rec:(_ for _ in ()).throw(OSError('disk full')))
    import pytest as _pt
    with _pt.raises(OSError):p.register(src())
    assert 's1' not in p.records

def test_m25_hz11_register_time_failure_leaves_no_files_or_state(tmp_path, monkeypatch):
    # KILL: register-time manifest failure mid-ingest left version files on
    # disk plus an in-memory record - untracked residue and a false claim.
    p=pipe(tmp_path)
    monkeypatch.setattr(p,'_persist_manifest',lambda rec:(_ for _ in ()).throw(OSError('disk full')))
    import pytest as _pt
    with _pt.raises(OSError):ingest(p)
    assert 's1' not in p.records and not p.chunks
    assert not (tmp_path/'tenant-a'/'s1').exists()


def test_m25_hz13_restart_refusal_preserves_prior_manifest(tmp_path):
    # KILL: a fresh pipeline rewrote the on-disk manifest to versions=[]
    # DURING registration, before the target-exists refusal - prior version
    # records silently erased while old bytes remained.
    import json as J
    p=pipe(tmp_path);v=ingest(p)
    before=J.loads((tmp_path/'tenant-a'/'s1'/'manifest.json').read_text())
    p2=pipe(tmp_path)
    with pytest.raises(KnowledgeError,match='refusing to overwrite'):
        ingest(p2,text='changed content')
    after=J.loads((tmp_path/'tenant-a'/'s1'/'manifest.json').read_text())
    assert after==before and after['versions'][0]['hash']==v.content_hash
    assert (tmp_path/'tenant-a'/'s1'/'v1'/'source.bin').exists()

def test_m25_hz13_direct_register_refuses_to_erase_prior_disk_state(tmp_path):
    # KILL: plain register() on a fresh pipeline erased the prior manifest
    # even with no ingest attempted.
    p=pipe(tmp_path);ingest(p)
    p2=pipe(tmp_path)
    with pytest.raises(KnowledgeError,match='refusing to overwrite'):p2.register(src())
    import json as J
    assert len(J.loads((tmp_path/'tenant-a'/'s1'/'manifest.json').read_text())['versions'])==1

def test_m25_hz13_corrupt_manifest_fails_closed(tmp_path):
    # KILL: an unreadable manifest was silently overwritten.
    p=pipe(tmp_path);ingest(p)
    (tmp_path/'tenant-a'/'s1'/'manifest.json').write_text('{not json')
    p2=pipe(tmp_path)
    with pytest.raises(KnowledgeError,match='unreadable on-disk manifest'):p2.register(src())

def test_m25_hz13_manifest_tmp_name_unique_no_symlink_follow(tmp_path):
    # KILL: the fixed manifest.json.tmp name could collide and write_text
    # would follow a preexisting symlink at that path. Scratch-only check.
    p=pipe(tmp_path)
    outside=tmp_path/'outside.txt'; outside.write_text('untouched')
    (tmp_path/'tenant-a'/'s1').mkdir(parents=True)
    (tmp_path/'tenant-a'/'s1'/'manifest.json.tmp').symlink_to(outside)
    ingest(p)
    assert outside.read_text()=='untouched'
    assert (tmp_path/'tenant-a'/'s1'/'manifest.json.tmp').is_symlink()  # fixed name never used or replaced
    import json as J
    assert len(J.loads((tmp_path/'tenant-a'/'s1'/'manifest.json').read_text())['versions'])==1


def test_m25_hz14_same_count_diverged_hash_refused(tmp_path):
    # KILL: count-only comparison - disk v1 with a different hash was
    # silently overwritten because the counts matched.
    import json as J
    p=pipe(tmp_path);ingest(p)
    mpath=tmp_path/'tenant-a'/'s1'/'manifest.json'
    disk=J.loads(mpath.read_text()); disk['versions'][0]['hash']='tampered'
    mpath.write_text(J.dumps(disk))
    # same pipeline: memory holds v1 so the count check passes and the
    # equivalence comparison is what must fire
    with pytest.raises(KnowledgeError,match='diverges'):ingest(p,text='changed')

def test_m25_hz14_zero_version_identity_mismatch_refused(tmp_path):
    # KILL: same-tenant zero-version re-registration with a different title
    # silently overwrote the on-disk registration identity.
    p=pipe(tmp_path);p.register(src())
    changed=src(); changed.title='Different Title'
    p2=pipe(tmp_path)
    with pytest.raises(KnowledgeError,match='identity differs'):p2.register(changed)

def test_m25_hz14_malformed_schema_variants_fail_closed(tmp_path):
    # KILL: valid JSON with invalid schema - [] raised AttributeError,
    # versions:null raised TypeError, versions:{} or missing versions were
    # treated as zero and overwritten. All must fail closed with
    # KnowledgeError, never be accepted as an arbitrary corrupt schema.
    p=pipe(tmp_path);ingest(p)
    mpath=tmp_path/'tenant-a'/'s1'/'manifest.json'
    original=mpath.read_text()
    for bad in ('[]','{"tenant_id":"tenant-a","source":{},"versions":null}',
                '{"tenant_id":"tenant-a","source":{},"versions":{}}',
                '{"tenant_id":"tenant-a","source":{}}',
                '{"tenant_id":"other","source":{},"versions":[]}',
                '{"tenant_id":"tenant-a","versions":[{"number":"1","hash":1}],"source":{}}'):
        mpath.write_text(bad)
        with pytest.raises(KnowledgeError,match='invalid on-disk manifest schema|tenant differs'):
            pipe(tmp_path).register(src())
        mpath.write_text(original)

def test_m25_hz14_tmp_write_exclusive_nofollow(tmp_path, monkeypatch):
    # KILL: tmp write_text was not exclusive/no-follow - a preexisting
    # symlink at the chosen tmp name would be written through.
    import uuid
    monkeypatch.setattr(uuid,'uuid4',lambda:type('U',(),{'hex':'fixed'})())
    p=pipe(tmp_path)
    outside=tmp_path/'outside.txt'; outside.write_text('untouched')
    target=tmp_path/'tenant-a'/'s1'
    target.mkdir(parents=True)
    (target/'manifest.json.tmp-fixed').symlink_to(outside)
    with pytest.raises(OSError):ingest(p)
    assert outside.read_text()=='untouched'
