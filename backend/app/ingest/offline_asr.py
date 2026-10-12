"""Local PCM-WAV to Whisper text/timestamps. Never resolves a model name online."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import io
import math
from pathlib import Path
from threading import RLock
import wave
from app.modules.c30 import policy


class ASRError(ValueError):
    pass


@dataclass(frozen=True)
class ASRConfig:
    model_dir: Path
    model_size: str = 'small'

    def identity(self) -> str:
        """Hash actual local model files and the fixed decoding profile."""
        if type(self.model_dir) is not Path and not isinstance(self.model_dir, Path):
            raise ASRError('local model directory required')
        p = self.model_dir
        if self.model_size not in ('tiny', 'base', 'small', 'medium', 'large-v3'):
            raise ASRError('model size invalid')
        if not p.is_absolute() or any(x.is_symlink() for x in (p, *p.parents)):
            raise ASRError('local model directory required')
        try:
            if not p.is_dir():
                raise ASRError('local model directory required')
            names = sorted(p.iterdir(), key=lambda x: x.name)
            required = {'model.bin', 'config.json', 'tokenizer.json', 'preprocessor_config.json'}
            if not required <= {x.name for x in names}:
                raise ASRError('local model files incomplete')
            if len(names) > 32:
                raise ASRError('model file count exceeds bound')
            h = hashlib.sha256(('fw1.2.0-cpu-int8-beam1-temp0-v1:' + self.model_size).encode())
            for file in names:
                if file.is_symlink() or not file.is_file():
                    raise ASRError('local model files must be regular')
                if not 0 < file.stat().st_size <= 4_000_000_000:
                    raise ASRError('model file size exceeds bound')
                h.update(file.name.encode());h.update(b'\0')
                with file.open('rb') as stream:
                    while block := stream.read(1024 * 1024):
                        h.update(block)
                h.update(b'\0')
            return h.hexdigest()
        except OSError:
            raise ASRError('local model files unavailable') from None


@dataclass(frozen=True)
class Transcript:
    text: str
    segments: tuple[dict, ...]
    language: str
    audio_sha256: str
    model_identity: str

    def provenance(self) -> dict:
        return {'backend': 'faster-whisper-1.2.0', 'model_identity': self.model_identity,
                'audio_sha256': self.audio_sha256, 'language': self.language,
                'segments': [dict(s) for s in self.segments], 'speaker_identification': 'unavailable'}


class OfflineWhisper:
    MAX_AUDIO_BYTES = 20_000_000
    MAX_DURATION_SECONDS = 600
    MAX_SEGMENTS = 1000
    MAX_TEXT_CHARS = 100_000

    def __init__(self, config: ASRConfig):
        if type(config) is not ASRConfig:
            raise ASRError('ASR config required')
        self.config = config
        self.identity = config.identity()
        self._model = None
        self._lock = RLock()

    def _audio_duration(self, audio: bytes) -> float:
        if type(audio) is not bytes or not 0 < len(audio) <= self.MAX_AUDIO_BYTES:
            raise ASRError('audio size or type invalid')
        try:
            with wave.open(io.BytesIO(audio), 'rb') as w:
                channels, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
                if channels not in (1, 2) or width != 2 or not 8000 <= rate <= 48000 or w.getcomptype() != 'NONE':
                    raise ASRError('PCM16 WAV required')
                duration = frames / rate
                if not 0 < duration <= self.MAX_DURATION_SECONDS:
                    raise ASRError('audio duration exceeds bound')
                if len(w.readframes(frames)) != frames * channels * width:
                    raise ASRError('truncated WAV')
                return duration
        except (wave.Error, EOFError, OSError):
            raise ASRError('PCM16 WAV required') from None

    def transcribe(self, audio: bytes) -> Transcript:
        duration = self._audio_duration(audio)
        with self._lock:
            if self.config.identity() != self.identity:
                raise ASRError('model identity changed')
            try:
                if self._model is None:
                    from faster_whisper import WhisperModel
                    self._model = WhisperModel(str(self.config.model_dir.resolve()), device='cpu',
                                               compute_type='int8', local_files_only=True, use_auth_token=False)
                rows, info = self._model.transcribe(io.BytesIO(audio), beam_size=1, temperature=0.,
                                                   condition_on_previous_text=False, vad_filter=False)
                language = policy.clean_text(info.language, 'ASR', 'language', 16)
                result = []; total = 0; previous_end = 0.
                for row in rows:
                    if len(result) >= self.MAX_SEGMENTS:
                        raise ASRError('segment count exceeds bound')
                    start, end = row.start, row.end
                    if (type(start) not in (float, int) or type(end) not in (float, int)
                            or not math.isfinite(start) or not math.isfinite(end)
                            or not previous_end <= start < end <= duration):
                        raise ASRError('segment time invalid')
                    text = policy.clean_text(row.text, 'ASR', 'segment', 20_000, allow_ws=True).strip()
                    total += len(text)
                    if total > self.MAX_TEXT_CHARS:
                        raise ASRError('transcript text exceeds bound')
                    result.append({'text': text, 'start_seconds': float(start), 'end_seconds': float(end)})
                    previous_end = end
                if not result:
                    raise ASRError('no speech recognized')
                return Transcript(' '.join(s['text'] for s in result), tuple(result), language,
                                  hashlib.sha256(audio).hexdigest(), self.identity)
            except ASRError:
                raise
            except (ValueError, TypeError, AttributeError, ImportError, RuntimeError, OSError) as exc:
                # Preserve the local inference cause for trusted diagnostic logs.
                # Do not echo arbitrary provider/credential-bearing messages in public errors.
                raise ASRError('inference unavailable: ' + type(exc).__name__) from exc


class TextTranscriber:
    def __init__(self, backend: OfflineWhisper):
        self.backend = backend

    def transcribe_with_provenance(self, audio_bytes: bytes, *, media_type: str = '') -> Transcript:
        if media_type not in ('', 'audio/wav', 'audio/x-wav', 'audio/wave'):
            raise ASRError('PCM16 WAV required')
        return self.backend.transcribe(audio_bytes)

    def transcribe(self, audio_bytes: bytes, *, media_type: str = '') -> str:
        return self.transcribe_with_provenance(audio_bytes, media_type=media_type).text


class AdviceTranscriber:
    """M17's positional MIME protocol. Bind to the host's approved collection flow."""
    def __init__(self, backend: OfflineWhisper):
        self.text = TextTranscriber(backend)

    def transcribe(self, media: bytes, mime_type: str) -> str:
        return self.text.transcribe(media, media_type=mime_type)


class KnowledgeTranscriber:
    def __init__(self, backend: OfflineWhisper):
        self.backend = backend

    def transcribe(self, audio: bytes):
        from app.modules.m25_knowledge_copilot_training.schemas import Anchor, Segment
        result = self.backend.transcribe(audio)
        return [Segment(text=s['text'], start_seconds=s['start_seconds'], end_seconds=s['end_seconds'],
                        speaker='unknown', speaker_confidence=None,
                        anchors=[Anchor(anchor_id=f'asr-{i}', kind='timestamp',
                                        value=f"{s['start_seconds']}-{s['end_seconds']}")])
                for i, s in enumerate(result.segments, 1)]
