import hashlib,io,json,sys,wave
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.ingest.offline_asr import (ASRConfig,ASRError,OfflineWhisper,TextTranscriber,KnowledgeTranscriber,AdviceTranscriber)
from app.modules.m20_general_cognitive_worker.sensory import SensoryLayer
from app.modules.m25_knowledge_copilot_training.service_factory import KnowledgeServiceFactory,provision,ServiceUnavailable
from app.modules.m25_knowledge_copilot_training.schemas import IngestRequest
from test_m25_verified_rehydration import src


def wav(seconds=.01):
    f=io.BytesIO()
    with wave.open(f,'wb')as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*int(16000*seconds))
    return f.getvalue()

@pytest.fixture
def config(tmp_path):
    p=tmp_path/'small';p.mkdir()
    for name in ('model.bin','config.json','tokenizer.json','preprocessor_config.json'):(p/name).write_bytes(b'{}')
    return ASRConfig(p)

class FakeModel:
    def __init__(self):self.calls=[];self.rows=[SimpleNamespace(start=0.,end=.005,text=' hello ')]
    def transcribe(self,audio,**kw):
        self.calls.append((audio.read(),kw));return iter(self.rows),SimpleNamespace(language='en')

@pytest.fixture
def model(monkeypatch):
    f=FakeModel();calls=[]
    def load(path,**kw):calls.append((path,kw));return f
    monkeypatch.setitem(sys.modules,'faster_whisper',SimpleNamespace(WhisperModel=load))
    f.loads=calls;return f


def test_local_constructor_and_laziness(config,model):
    a=OfflineWhisper(config);assert model.loads==[]
    r=a.transcribe(wav())
    assert model.loads==[(str(config.model_dir.resolve()),{'device':'cpu','compute_type':'int8','local_files_only':True,'use_auth_token':False})]
    assert model.calls[0][0]==wav()
    assert model.calls[0][1]=={'beam_size':1,'temperature':0.,'condition_on_previous_text':False,'vad_filter':False}
    assert r.text=='hello' and r.language=='en'
    assert r.segments==({'text':'hello','start_seconds':0.,'end_seconds':.005},)
    assert r.audio_sha256==hashlib.sha256(wav()).hexdigest()
    assert r.model_identity==config.identity()
    a.transcribe(wav());assert len(model.loads)==1

@pytest.mark.parametrize('data',[b'',b'junk',bytearray(b'123'),None,'url'])
def test_audio_refuses_before_loading(config,model,data):
    with pytest.raises(ASRError):OfflineWhisper(config).transcribe(data)
    assert not model.loads


def test_byte_cap_inclusive(config,model,monkeypatch):
    monkeypatch.setattr(OfflineWhisper,'MAX_AUDIO_BYTES',len(wav()))
    assert OfflineWhisper(config).transcribe(wav()).text=='hello'
    with pytest.raises(ASRError,match='audio size'):OfflineWhisper(config).transcribe(wav()+b'x')

@pytest.mark.parametrize('start,end',[(True,.005),(-1,.005),(float('nan'),.005),(0,float('inf')),(.008,.005),(0,.02)])
def test_invalid_model_times(config,model,start,end):
    model.rows=[SimpleNamespace(start=start,end=end,text='hi')]
    with pytest.raises(ASRError,match='segment'):OfflineWhisper(config).transcribe(wav())

@pytest.mark.parametrize('text',[None,5,'','   ','bad\u200btext'])
def test_invalid_model_text(config,model,text):
    model.rows=[SimpleNamespace(start=0.,end=.005,text=text)]
    with pytest.raises(ASRError):OfflineWhisper(config).transcribe(wav())


def test_nonmonotonic_segments(config,model):
    model.rows=[SimpleNamespace(start=.003,end=.005,text='one'),SimpleNamespace(start=.001,end=.002,text='two')]
    with pytest.raises(ASRError):OfflineWhisper(config).transcribe(wav())


def test_no_speech_and_lazy_failure(config,model):
    model.rows=[]
    with pytest.raises(ASRError,match='no speech'):OfflineWhisper(config).transcribe(wav())
    def bad(*a,**k):
        def rows():raise RuntimeError('private');yield
        return rows(),SimpleNamespace(language='en')
    model.transcribe=bad
    with pytest.raises(ASRError,match='inference unavailable')as e:OfflineWhisper(config).transcribe(wav())
    assert 'private'not in str(e.value)


def test_missing_and_changed_weights(config,model):
    a=OfflineWhisper(config);before=config.identity()
    (config.model_dir/'model.bin').write_bytes(b'changed')
    assert config.identity()!=before
    with pytest.raises(ASRError,match='model identity'):a.transcribe(wav())
    assert not model.loads
    (config.model_dir/'tokenizer.json').unlink()
    with pytest.raises(ASRError):OfflineWhisper(config)


def test_symlink_or_relative_or_remote_directory(config,tmp_path):
    p=tmp_path/'link';p.symlink_to(config.model_dir,target_is_directory=True)
    for x in (p,Path('small'),Path('https://models.invalid'),tmp_path/'missing'):
        with pytest.raises(ASRError):OfflineWhisper(ASRConfig(x))


def test_bridges_source_time_metadata_and_dedupe(config,model):
    layer=SensoryLayer(asr_config=config,allowed_sources={'voice'})
    assert layer.ingest_audio(wav(),source='denied')is None and not model.loads
    event=layer.ingest_audio(wav(),source='voice',external_id='clip',media_type='audio/wav',metadata={'asr':{'fake':True}})
    assert event.text=='hello' and event.source=='voice' and event.external_id=='clip'
    assert event.metadata['asr']['segments'][0]['end_seconds']==.005
    assert event.metadata['asr']['audio_sha256']==event.content_hash
    assert event.metadata['asr']['model_identity']==config.identity()
    assert layer.ingest_audio(wav(),source='voice')is None
    assert len(model.calls)==1
    assert TextTranscriber(OfflineWhisper(config)).transcribe(wav(),media_type='audio/wav')=='hello'
    assert AdviceTranscriber(OfflineWhisper(config)).transcribe(wav(),'audio/wav')=='hello'
    segments=KnowledgeTranscriber(OfflineWhisper(config)).transcribe(wav())
    assert segments[0].start_seconds==0 and segments[0].end_seconds==.005
    assert segments[0].speaker=='unknown' and segments[0].speaker_confidence is None
    assert segments[0].anchors[0].kind=='timestamp'


def test_mutually_exclusive_config(config):
    with pytest.raises(ValueError):SensoryLayer(asr_config=config,transcriber=object())


def test_factory_profile_and_restart(config,model,tmp_path):
    root=tmp_path/'root';root.mkdir(mode=0o700)
    provision(root,'t','owner',known_new=True,allow_test_scratch=True,asr_config=config)
    f=KnowledgeServiceFactory(root,allow_test_scratch=True,asr_config=config)
    with f.service('t','owner')as s:
        s.ingest(IngestRequest(source=src(),content=wav(),mime_type='audio/wav',actor_id='owner'))
        version=s.records['s1'].versions[0]
        assert version.segments[0].anchors[0].value=='0.0-0.005'
        assert s.chunks[0].source_id=='s1'
    with KnowledgeServiceFactory(root,allow_test_scratch=True,asr_config=config).service('t','owner')as s:
        assert s.records['s1'].versions[0].segments[0].text=='hello'
    with pytest.raises(ServiceUnavailable):
        with KnowledgeServiceFactory(root,allow_test_scratch=True).service('t','owner'):pass
    (config.model_dir/'model.bin').write_bytes(b'different')
    with pytest.raises(ServiceUnavailable):
        with KnowledgeServiceFactory(root,allow_test_scratch=True,asr_config=config).service('t','owner'):pass


def test_old_registry_not_upgraded(config,tmp_path):
    root=tmp_path/'root';root.mkdir(mode=0o700)
    provision(root,'t','owner',known_new=True,allow_test_scratch=True)
    with pytest.raises(ServiceUnavailable):
        with KnowledgeServiceFactory(root,allow_test_scratch=True,asr_config=config).service('t','owner'):pass


def test_duration_and_segment_caps(config,model,monkeypatch):
    monkeypatch.setattr(OfflineWhisper,'MAX_DURATION_SECONDS',.01)
    assert OfflineWhisper(config).transcribe(wav(.01)).text=='hello'
    with pytest.raises(ASRError,match='duration'):OfflineWhisper(config).transcribe(wav(.02))
    monkeypatch.setattr(OfflineWhisper,'MAX_SEGMENTS',1)
    model.rows=[SimpleNamespace(start=0.,end=.003,text='a')]
    assert OfflineWhisper(config).transcribe(wav()).text=='a'
    model.rows.append(SimpleNamespace(start=.003,end=.005,text='b'))
    with pytest.raises(ASRError,match='segment count'):OfflineWhisper(config).transcribe(wav())


def test_transcript_total_cap_and_segment_text(config,model,monkeypatch):
    monkeypatch.setattr(OfflineWhisper,'MAX_TEXT_CHARS',3)
    model.rows=[SimpleNamespace(start=0.,end=.005,text='abc')]
    assert OfflineWhisper(config).transcribe(wav()).text=='abc'
    model.rows[0].text='abcd'
    with pytest.raises(ASRError,match='text exceeds'):OfflineWhisper(config).transcribe(wav())
    model.rows[0].text='a'*20001
    with pytest.raises(ASRError):OfflineWhisper(config).transcribe(wav())


def test_identity_includes_all_assets_size_and_decoder(config):
    before=config.identity()
    assert ASRConfig(config.model_dir,model_size='base').identity()!=before
    for name in ('model.bin','config.json','tokenizer.json','preprocessor_config.json'):
        p=config.model_dir/name;old=p.read_bytes();p.write_bytes(b'different')
        assert config.identity()!=before;p.write_bytes(old)
    assert config.identity()==before
    with pytest.raises(ASRError):ASRConfig(config.model_dir,model_size='remote').identity()


def test_mime_and_truncation(config,model):
    bridge=TextTranscriber(OfflineWhisper(config))
    with pytest.raises(ASRError):bridge.transcribe(wav(),media_type='audio/ogg')
    with pytest.raises(ASRError):bridge.transcribe(wav()[:-1])
    assert not model.loads


def test_model_load_failure_is_private(config,model,monkeypatch):
    def bad(*a,**kw):raise RuntimeError('secret-path')
    monkeypatch.setitem(sys.modules,'faster_whisper',SimpleNamespace(WhisperModel=bad))
    with pytest.raises(ASRError,match='inference unavailable')as e:OfflineWhisper(config).transcribe(wav())
    assert 'secret-path'not in str(e.value)


def test_model_tree_refusals(config):
    p=config.model_dir/'tokenizer.json';p.unlink();p.symlink_to(config.model_dir/'config.json')
    with pytest.raises(ASRError):OfflineWhisper(config)
    p.unlink();p.write_bytes(b'')
    with pytest.raises(ASRError):OfflineWhisper(config)


def test_segment_exact_boundary_two_segments(config,model):
    model.rows=[SimpleNamespace(start=0.,end=.005,text='one'),SimpleNamespace(start=.005,end=.01,text='two')]
    r=OfflineWhisper(config).transcribe(wav())
    assert r.text=='one two' and r.segments[1]['end_seconds']==.01
    segments=KnowledgeTranscriber(OfflineWhisper(config)).transcribe(wav())
    assert [s.anchors[0].anchor_id for s in segments]==['asr-1','asr-2']


def test_cached_factory_model_change_refuses(config,model,tmp_path):
    root=tmp_path/'root';root.mkdir(mode=0o700)
    provision(root,'t','owner',known_new=True,allow_test_scratch=True,asr_config=config)
    f=KnowledgeServiceFactory(root,allow_test_scratch=True,asr_config=config)
    with f.service('t','owner')as s:
        assert s.transcriber.transcribe(wav())[0].text=='hello'
        (config.model_dir/'model.bin').write_bytes(b'new')
        with pytest.raises(ASRError):s.transcriber.transcribe(wav())


def test_service_constructor_wires_config(config,model):
    from app.modules.m20_general_cognitive_worker.service import CognitiveWorkerService
    worker=CognitiveWorkerService(asr_config=config,seed_judgment_skills=False)
    assert worker.sensory.ingest_audio(wav(),source='voice').metadata['asr']['segments']


def test_valid_bytearray_and_relative_model_refused(config,model,monkeypatch):
    with pytest.raises(ASRError):OfflineWhisper(config).transcribe(bytearray(wav()))
    monkeypatch.chdir(config.model_dir.parent)
    with pytest.raises(ASRError):OfflineWhisper(ASRConfig(Path('small')))


def test_invalid_pcm_properties(config,model):
    for channels,width,rate in ((3,2,16000),(1,1,16000),(1,2,4000),(1,2,96000)):
        f=io.BytesIO()
        with wave.open(f,'wb')as w:
            w.setnchannels(channels);w.setsampwidth(width);w.setframerate(rate);w.writeframes(b'\0'*(channels*width*10))
        with pytest.raises(ASRError):OfflineWhisper(config).transcribe(f.getvalue())
    assert not model.loads


def test_factory_identity_change_before_first_service(config,tmp_path):
    root=tmp_path/'root';root.mkdir(mode=0o700)
    provision(root,'t','owner',known_new=True,allow_test_scratch=True,asr_config=config)
    factory=KnowledgeServiceFactory(root,allow_test_scratch=True,asr_config=config)
    (config.model_dir/'tokenizer.json').write_bytes(b'changed')
    with pytest.raises(ServiceUnavailable):
        with factory.service('t','owner'):pass


def test_default_caps_and_real_duration_boundary(config,model):
    assert OfflineWhisper.MAX_AUDIO_BYTES==20_000_000
    assert OfflineWhisper.MAX_DURATION_SECONDS==600
    assert OfflineWhisper.MAX_SEGMENTS==1000
    assert OfflineWhisper.MAX_TEXT_CHARS==100_000
    backend=OfflineWhisper(config)
    assert backend._audio_duration(wav(600))==600
    with pytest.raises(ASRError):backend._audio_duration(wav(600.001))
    assert backend.transcribe(wav()+b'\0'*(20_000_000-len(wav()))).text=='hello'
    with pytest.raises(ASRError):backend.transcribe(wav()+b'\0'*(20_000_001-len(wav())))


def test_actual_segment_count_and_total_text_boundaries(config,model):
    model.rows=[SimpleNamespace(start=i*.00001,end=(i+1)*.00001,text='x')for i in range(1000)]
    assert len(OfflineWhisper(config).transcribe(wav(.02)).segments)==1000
    model.rows.append(SimpleNamespace(start=.01,end=.01001,text='x'))
    with pytest.raises(ASRError):OfflineWhisper(config).transcribe(wav(.02))
    model.rows=[SimpleNamespace(start=i*.001,end=(i+1)*.001,text='x'*20000)for i in range(5)]
    assert sum(len(s['text'])for s in OfflineWhisper(config).transcribe(wav()).segments)==100000
    model.rows.append(SimpleNamespace(start=.005,end=.006,text='x'))
    with pytest.raises(ASRError):OfflineWhisper(config).transcribe(wav())


def test_model_file_count_32_33(config):
    for i in range(28):(config.model_dir/f'extra{i}').write_bytes(b'x')
    assert config.identity()
    (config.model_dir/'extra28').write_bytes(b'x')
    with pytest.raises(ASRError):config.identity()


def test_model_declared_file_size_boundary(config,monkeypatch):
    # Metadata boundary injection avoids allocating/reading4GB in CI.
    original=Path.stat;size=4_000_000_000
    def stat(p,*a,**kw):
        real=original(p,*a,**kw)
        if p==config.model_dir/'model.bin':return SimpleNamespace(st_mode=real.st_mode,st_size=size)
        return real
    monkeypatch.setattr(Path,'stat',stat)
    assert config.identity()
    size=4_000_000_001
    with pytest.raises(ASRError):config.identity()
    size=0
    with pytest.raises(ASRError):config.identity()

@pytest.mark.parametrize('length',[16,17])
def test_language_length_boundary(config,model,length):
    model.transcribe=lambda *a,**kw:(iter(model.rows),SimpleNamespace(language='x'*length))
    if length==16:assert len(OfflineWhisper(config).transcribe(wav()).language)==16
    else:
        with pytest.raises(ASRError):OfflineWhisper(config).transcribe(wav())

@pytest.mark.parametrize('length',[20000,20001])
def test_segment_text_raw_boundary(config,model,length):
    model.rows[0].text='x'*length
    if length==20000:assert len(OfflineWhisper(config).transcribe(wav()).text)==20000
    else:
        with pytest.raises(ASRError):OfflineWhisper(config).transcribe(wav())


def pcm(rate=16000,channels=1,frames=160):
    b=io.BytesIO()
    with wave.open(b,'wb')as w:
        w.setnchannels(channels);w.setsampwidth(2);w.setframerate(rate);w.writeframes(b'\0'*(frames*channels*2))
    return b.getvalue()

@pytest.mark.parametrize('rate,accepted',[(7999,False),(8000,True),(48000,True),(48001,False)])
def test_sample_rate_all_edges(config,model,rate,accepted):
    audio=pcm(rate=rate,frames=480)
    if accepted:assert OfflineWhisper(config).transcribe(audio).text=='hello'
    else:
        with pytest.raises(ASRError):OfflineWhisper(config).transcribe(audio)


def test_stereo_truncation_zero_frames_and_compression(config,model,monkeypatch):
    backend=OfflineWhisper(config)
    assert backend.transcribe(pcm(channels=2)).text=='hello'
    for audio in (pcm(channels=3),pcm(frames=0),pcm(channels=2)[:-2]):
        with pytest.raises(ASRError):backend.transcribe(audio)
    monkeypatch.setattr(wave.Wave_read,'getcomptype',lambda self:'ULAW')
    with pytest.raises(ASRError):backend.transcribe(wav())


def test_equal_times_overlap_whitespace_and_int_float(config,model):
    model.rows=[SimpleNamespace(start=.005,end=.005,text='x')]
    with pytest.raises(ASRError):OfflineWhisper(config).transcribe(wav())
    model.rows=[SimpleNamespace(start=0.,end=.006,text='one'),SimpleNamespace(start=.005,end=.008,text='two')]
    with pytest.raises(ASRError):OfflineWhisper(config).transcribe(wav())
    model.rows=[SimpleNamespace(start=0,end=1,text='one\n\ttwo')]
    r=OfflineWhisper(config).transcribe(wav(1))
    assert r.text=='one\n\ttwo'
    assert type(r.segments[0]['start_seconds'])is float and type(r.segments[0]['end_seconds'])is float

@pytest.mark.parametrize('error',[TypeError,AttributeError,ImportError,RuntimeError])
def test_each_inference_exception_mapping(config,model,error):
    def bad(*a,**kw):raise error('secret')
    model.transcribe=bad
    with pytest.raises(ASRError)as e:OfflineWhisper(config).transcribe(wav())
    assert str(e.value)=='inference unavailable'

@pytest.mark.parametrize('size',['tiny','medium','large-v3'])
def test_allowed_model_sizes(config,size):assert ASRConfig(config.model_dir,size).identity()


def test_bogus_large_and_nonpath(config):
    for c in (ASRConfig(config.model_dir,'large'),ASRConfig(str(config.model_dir))):
        with pytest.raises(ASRError):OfflineWhisper(c)
    with pytest.raises(ASRError):OfflineWhisper(object())

@pytest.mark.parametrize('filename',['model.bin','config.json','preprocessor_config.json'])
def test_each_required_asset(config,filename):
    (config.model_dir/filename).unlink()
    with pytest.raises(ASRError):OfflineWhisper(config)


def test_symlinked_ancestor(config,tmp_path):
    link=tmp_path/'parent-link';link.symlink_to(config.model_dir.parent,target_is_directory=True)
    with pytest.raises(ASRError):OfflineWhisper(ASRConfig(link/'small'))


def test_identity_exact_sorted_delimiters_profile(config,monkeypatch):
    names=list(config.model_dir.iterdir())
    h=hashlib.sha256(b'fw1.2.0-cpu-int8-beam1-temp0-v1:small')
    for p in sorted(names,key=lambda x:x.name):h.update(p.name.encode()+b'\0'+p.read_bytes()+b'\0')
    expected=h.hexdigest();assert config.identity()==expected
    original=Path.iterdir
    monkeypatch.setattr(Path,'iterdir',lambda p:iter(reversed(list(original(p)))))
    assert config.identity()==expected


def test_model_read_oserror_mapping(config,monkeypatch):
    original=Path.open
    def bad(p,*a,**kw):
        if p==config.model_dir/'model.bin':raise OSError('secret')
        return original(p,*a,**kw)
    monkeypatch.setattr(Path,'open',bad)
    with pytest.raises(ASRError)as e:config.identity()
    assert str(e.value)=='local model files unavailable'

@pytest.mark.parametrize('mime',['audio/x-wav','audio/wave'])
def test_accepted_mime_aliases(config,model,mime):
    assert TextTranscriber(OfflineWhisper(config)).transcribe(wav(),media_type=mime)=='hello'
    assert AdviceTranscriber(OfflineWhisper(config)).transcribe(wav(),mime)=='hello'


def test_provenance_and_advice_mime(config,model):
    r=OfflineWhisper(config).transcribe(wav()).provenance()
    assert r['backend']=='faster-whisper-1.2.0' and r['speaker_identification']=='unavailable'
    with pytest.raises(ASRError):AdviceTranscriber(OfflineWhisper(config)).transcribe(wav(),'audio/mpeg')
    class Recorder:
        def transcribe_with_provenance(self,audio_bytes,*,media_type):
            assert media_type=='audio/x-wav'
            return SimpleNamespace(text='hi',provenance=lambda:r)
    e=SensoryLayer(transcriber=Recorder()).ingest_audio(wav(),source='s',media_type='audio/x-wav')
    assert e.metadata['media_type']=='audio/x-wav'


def test_factory_profile_guards(config,tmp_path):
    from app.modules.m25_knowledge_copilot_training.service_factory import _asr_profile
    tmp_path.chmod(0o700)
    with pytest.raises(ServiceUnavailable):provision(tmp_path,'t','o',known_new=True,allow_test_scratch=True,profile='custom')
    for c in (object(),ASRConfig(tmp_path/'missing')):
        with pytest.raises(ServiceUnavailable)as e:_asr_profile(c)
        assert str(e.value)=='knowledge service unavailable'


def test_zero_frame_guard_direct(config):
    with pytest.raises(ASRError,match='audio duration'):OfflineWhisper(config)._audio_duration(pcm(frames=0))
