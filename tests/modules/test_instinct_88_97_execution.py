from datetime import date
import hashlib
from pathlib import Path
import sys
import types
import pytest
from PIL import Image
from app.modules.c32.psyche import tag_evidence
from app.modules.c32.teardown import teardown_sources
from app.modules.c33.channel_adaptation import adapt
from app.modules.c36.workforce import execute_blueprint
from app.modules.c32.product_images import LocalProductImages, ImageUnavailable
from app.modules.m23_study_abroad.roadmap_progress import reconcile

def test_psyche_token_boundaries_negation_and_source_spans():
    text='I made a saddle. Not happy. I love my family.'
    report=tag_evidence(text)
    assert report['emotions']['anger']==report['emotions']['sadness']==0
    assert report['emotions']['joy']==1
    hit=report['evidence']['emotions']['joy'][0]
    assert hit['negated'] and text[hit['start']:hit['end']]=='happy'

def test_brand_source_spans_are_exact_and_missing_is_explicit():
    text='Brand founder Jane started it. Ingredients include rose. Affiliate commission is 5 percent.'
    report=teardown_sources('Brand',[{'url':'https://example.invalid/brand','text':text}])
    assert report['affiliate_mentions']
    for hit in report['dimensions']['founder_history']:
        assert text[hit['start']:hit['end']]==hit['quote']
    assert 'marketing_channels' in report['missing_dimensions']

def test_adaptation_reuses_owner_substance_and_respects_limits():
    text='Real field observations and project results. '*40
    report=adapt([{'id':'one','title':'Field notes','text':text,'owner_authored':True}],['x','linkedin'])
    for draft in report['drafts']:
        assert all(len(p)<=draft['limit'] for p in draft['parts'])
        assert 'Real field observations' in draft['parts'][0]
        assert draft['sent'] is False
    with pytest.raises(ValueError):
        adapt([{'id':'x','title':'copy','text':'not mine','owner_authored':False}],['x'])

def test_workforce_executes_graph_and_blocks_unimplemented_handlers():
    blueprint={'id':'company','offer':'Analyze samples','worker_graph':{'nodes':['researcher','analyst'],
                'edges':[{'from':'researcher','to':'analyst'}],'isolated':[]}}
    handlers={'researcher':lambda a,i,n,f: [2,3], 'analyst':lambda a,i,n,f: sum(i['researcher'])}
    assert execute_blueprint(blueprint,handlers).outputs['analyst']==5
    with pytest.raises(ValueError): execute_blueprint(blueprint,{})

def test_roadmap_reconciles_without_claiming_artifact_validation():
    curriculum={'domains':[{'id':'math','name':'Math'}],'steps':[
        {'id':'a','title':'Basics','domain':'math','hours':1},
        {'id':'b','title':'Advanced','domain':'math','hours':1,'after':['a']}]}
    roadmap={'schedule':{'steps':[{'id':'a'},{'id':'b'}]}}
    evidence=[{'step_id':'a','completed_at':'2026-10-11','artifact_url':'https://example.invalid/project'}]
    result=reconcile(roadmap,curriculum,evidence,today=date(2026,10,12))
    assert result['next_ready']==['b'] and roadmap['schedule']['steps'][0]['id']=='a'
    evidence[0]['completed_at']='2026-10-13'
    with pytest.raises(ValueError): reconcile(roadmap,curriculum,evidence,today=date(2026,10,12))

def test_image_missing_model_never_claims_generated(tmp_path):
    with pytest.raises(ImageUnavailable): LocalProductImages(tmp_path)

def test_image_adapter_calls_local_pipeline_and_writes_labeled_png(tmp_path,monkeypatch):
    model=tmp_path/'model';model.mkdir();(model/'model_index.json').write_text('{}')
    calls=[]
    class Pipeline:
        @classmethod
        def from_pretrained(cls,*args,**kwargs):
            calls.append((args,kwargs));return cls()
        def to(self,device): return self
        def __call__(self,**kwargs):
            return types.SimpleNamespace(images=[Image.new('RGB',(kwargs['width'],kwargs['height']),'pink')])
    class Generator:
        def __init__(self,**kw):pass
        def manual_seed(self,seed):return self
    monkeypatch.setitem(sys.modules,'torch',types.SimpleNamespace(float32='float32',Generator=Generator))
    monkeypatch.setitem(sys.modules,'diffusers',types.SimpleNamespace(DiffusionPipeline=Pipeline))
    output=tmp_path/'concept.png'
    engine=LocalProductImages(model)
    receipt=engine.generate({'subject':'Perfume bottle'},output)
    assert calls[0][1]['local_files_only'] is True
    assert calls[0][1]['trust_remote_code'] is False
    assert receipt['sha256']==hashlib.sha256(output.read_bytes()).hexdigest()
    assert receipt['realism_validated'] is False
    with Image.open(output) as image: assert image.info['AI-generated']=='true'
    with pytest.raises(ValueError):engine.generate({'subject':'bottle'},output)

def test_image_model_drift_blocks_inference(tmp_path):
    model=tmp_path/'model';model.mkdir();(model/'model_index.json').write_text('{}')
    engine=LocalProductImages(model);(model/'model_index.json').write_text('{"changed":true}')
    with pytest.raises(ImageUnavailable,match='identity changed'):
        engine.generate({'subject':'Bottle'},tmp_path/'x.png')

def test_audio_reasoning_composes_asr_and_cue_analysis(monkeypatch):
    from app.modules.c32 import audio_reasoning
    from app.ingest.offline_asr import Transcript
    class SyntheticASR:
        def __init__(self,config):pass
        def transcribe(self,audio):
            return Transcript('From first principles. A feedback loop.',
                              ({'text':'From first principles.','start_seconds':0.,'end_seconds':1.},
                               {'text':'A feedback loop.','start_seconds':1.,'end_seconds':2.}),
                              'en',hashlib.sha256(audio).hexdigest(),'test-synthetic-model')
    monkeypatch.setattr(audio_reasoning,'OfflineWhisper',SyntheticASR)
    result=audio_reasoning.AudioReasoning(None).analyze(b'synthetic-test-audio',document_id='audio',medium='podcast')
    assert result['move_totals']['first_principles']==1
    assert result['move_totals']['systems']==2
    assert result['transcription']['audio_sha256']==hashlib.sha256(b'synthetic-test-audio').hexdigest()
    assert 'not a learned model' in result['report_caveat']

def test_learning_experiment_trains_centroids_and_executes_heldout(tmp_path):
    from app.modules.c37.learning_experiment import experiment
    train=[{'id':'a1','features':[0.,0.],'label':'a'},{'id':'a2','features':[1.,1.],'label':'a'},
           {'id':'b1','features':[8.,8.],'label':'b'},{'id':'b2','features':[10.,10.],'label':'b'}]
    heldout=[{'id':'test-a','features':[0.7,0.3],'label':'a'},{'id':'test-b','features':[9.,8.5],'label':'b'}]
    result=experiment(train,heldout,model_output=tmp_path/'model.json')
    assert result['model']['centroids']=={'a':[0.5,0.5],'b':[9.,9.]}
    assert result['accuracy']==1 and result['majority_baseline_accuracy']==0.5
    assert result['breakthrough_claim'] is False
    heldout[0]['id']='a1'
    with pytest.raises(ValueError,match='overlap'):experiment(train,heldout)

def test_learning_rejects_boolean_nan_and_duplicate_split_observation():
    from app.modules.c37.learning_experiment import experiment
    train=[{'id':'a','features':[0.],'label':'a'},{'id':'b','features':[10.],'label':'b'}]
    for bad in (True,float('nan')):
        with pytest.raises(ValueError): experiment(train,[{'id':'c','features':[bad],'label':'a'}])
    with pytest.raises(ValueError,match='leaked'):experiment(train,[{'id':'c','features':[0.],'label':'a'}])
