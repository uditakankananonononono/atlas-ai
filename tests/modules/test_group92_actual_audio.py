from pathlib import Path
import hashlib,json,os,subprocess
import pytest
from app.ingest.offline_asr import ASRConfig
from app.modules.c32.audio_reasoning import AudioReasoning

@pytest.mark.skipif(not os.environ.get('ATLAS_GROUP92_MODEL_DIR'),reason='requires prepared pinned local CTranslate2 Whisper model')
def test_actual_asr_to_reasoning_cues_with_provenance(tmp_path):
    media=tmp_path/'reason.wav'
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i',"flite=text='Usually I tell a story. Instead I start from scratch and think about the system':voice=slt",'-ar','16000','-ac','1',str(media)],check=True)
    report=AudioReasoning(ASRConfig(Path(os.environ['ATLAS_GROUP92_MODEL_DIR']),model_size='tiny')).analyze(media.read_bytes(),document_id='actual-local-acceptance',medium='speech')
    assert report['transcription']['backend']=='faster-whisper-1.2.0'
    assert report['transcription']['audio_sha256']==hashlib.sha256(media.read_bytes()).hexdigest()
    assert 'story' in report['transcription']['segments'][0]['text'].lower()
    assert report['transcription']['segments'][0]['end_seconds']>0
    assert report['transcription']['speaker_identification']=='unavailable'
    assert report['report_caveat'].startswith('Audio was transcribed')
    (tmp_path/'receipt.json').write_text(json.dumps(report,indent=2))
