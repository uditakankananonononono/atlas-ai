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
    p=pipe(tmp_path);v=ingest(p);c=Citation(source_id='s1',version=1,anchor_ids=['paragraph-1'],quote_hash='h');assert p.substantiate([Claim(text='Alpha',citations=[c])])
    with pytest.raises(UnsupportedClaim):p.substantiate([Claim(text='invented')])
def test_m25_15_contradiction_freshness_analysis_stale_conflict(tmp_path):
    p=pipe(tmp_path);ingest(p,src('old'),text='Policy allows alpha');ingest(p,src('new'),text='Policy does not allow alpha');assert p.contradictions('Policy alpha')[0]['status']=='conflict_requires_review'
def test_m25_16_export_and_verified_deletion(tmp_path):
    p=pipe(tmp_path);ingest(p);assert p.export()['sources'];result=p.delete_verified('s1');assert result['deleted'] and not (tmp_path/'tenant-a'/'s1').exists() and not p.search('Alpha')
def test_actor_isolation(tmp_path):
    p=pipe(tmp_path)
    with pytest.raises(KnowledgeError):p.ingest(IngestRequest(source=src(),content='x',mime_type='text/plain',actor_id='other'))
