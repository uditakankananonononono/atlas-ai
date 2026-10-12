"""Transcript adapter tests with supplied fake transcript, no ASR quality claim."""
import types
import pytest
from app.modules.c32.audio_reasoning import AudioReasoning


def engine():
    obj=object.__new__(AudioReasoning)
    transcript=types.SimpleNamespace(text='Usually I tell a story.',segments=[{'text':'Usually I tell a story.','start_seconds':0}],provenance=lambda:{'audio_sha256':'a'*64,'speaker_identification':'unavailable'})
    obj.backend=types.SimpleNamespace(transcribe=lambda audio:transcript)
    return obj


def test_validation_precedes_transcription_and_retains_honest_scope():
    obj=engine();out=obj.analyze(b'fixture',document_id='fixture',medium='speech')
    assert out['transcription']['audio_sha256']=='a'*64
    assert out['scope']['not_implemented']==['validation of human thinking','speaker identification','music understanding','all forms of media']
    assert out['validity']['caveat']==out['report_caveat']
    assert 'fixed cue tags' in out['report_caveat']
    def forbidden(audio):raise AssertionError('inference occurred before validation')
    obj.backend.transcribe=forbidden
    with pytest.raises(ValueError):obj.analyze(b'fixture',document_id='fixture',medium='unknown')
