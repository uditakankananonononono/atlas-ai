"""Local audio decoding followed by auditable reasoning-cue analysis.

Uses the existing pinned OfflineWhisper backend. No remote transcription,
model download, speaker/personality inference or claim of learned reasoning.
"""
from __future__ import annotations

from app.ingest.offline_asr import ASRConfig, OfflineWhisper
from app.modules.c30 import policy
from app.modules.c32.thought_chains import MEDIA, run


class AudioReasoning:
    def __init__(self, config: ASRConfig):
        self.backend = OfflineWhisper(config)

    def analyze(self, audio: bytes, *, document_id: str, medium: str) -> dict:
        policy.clean_text(document_id, 'TREND', 'id', 64)
        if medium not in MEDIA or type(medium) is not str:
            raise ValueError('TREND_REFUSED_BAD_TYPE:medium')
        # Validation completes before any model inference.
        transcript = self.backend.transcribe(audio)
        doc = {'id': document_id, 'kind': 'transcript', 'medium': medium,
               'text': transcript.text,
               'turns': [{'speaker': 'unknown', 'text': (' ' if index else '') + segment['text'],
                          't_start': segment['start_seconds']}
                         for index, segment in enumerate(transcript.segments)]}
        report = run({'docs': [doc]})
        report['transcription'] = transcript.provenance()
        report['report_caveat'] = (
            'Audio was transcribed with the configured local Whisper model. '
            'Reasoning moves are fixed cue tags, not a learned model of human thinking. '
            'Speaker identification and music interpretation are unavailable.')
        report['validity']['caveat'] = report['report_caveat']
        report['scope']['implemented'].append('local PCM16-WAV transcription with timestamps and model/audio hashes')
        report['scope']['not_implemented'] = ['validation of human thinking', 'speaker identification',
                                            'music understanding', 'all forms of media']
        report['scope']['data_source'] = 'supplied audio decoded by configured local model'
        return report
